"""把外部图片/视频导入图库，分两段：

1. `import_files()`：计算 hash → 识别来源 → 复制并校验 → 写库。**永远不删源文件。**
2. `delete_sources()`：用户确认后才调用。删除前再校验一次"图库副本完好、源文件没被改过"。

这样"删不删源文件"是导入完成后、看过结果再做的独立决定（CLI 里的确认提示，界面里的复选框）。
视频和图片走同一套文件名识别与收件箱导入；只是不读取宽高（不引入视频解析依赖）。
"""

from __future__ import annotations

import json
import os
import re
import sqlite3
import uuid
from collections import Counter
from collections.abc import Iterable
from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path, PurePosixPath

from PIL import Image

from artist_gallery.core import db
from artist_gallery.core.fileops import copy_verified, sha256_file
from artist_gallery.core.layout import INBOX
from artist_gallery.core.media import IMAGE_EXTS, MEDIA_EXTS
from artist_gallery.core.recognize import Confidence, Recognition, RuleSet, load_rules, recognize
from artist_gallery.core.sources import record_filename


class Action(StrEnum):
    HINT = "hint"  # 高／中置信均进收件箱并附待审建议
    INBOX = "inbox"  # 未识别，进收件箱
    DUP = "dup"  # 复用已有文件并记录新线索，源文件不动
    ERROR = "error"


IMPORTED = frozenset({Action.HINT, Action.INBOX})


@dataclass
class ImportItem:
    src: Path
    action: Action
    rel_path: str | None = None
    recognition: Recognition | None = None
    message: str = ""
    sha256: str | None = None
    file_id: int | None = None
    evidence_added: bool = False


@dataclass
class ImportReport:
    root: Path
    items: list[ImportItem] = field(default_factory=list)
    dry_run: bool = False
    batch_id: str = ""

    def counts(self) -> Counter[Action]:
        return Counter(i.action for i in self.items)

    def deletable(self) -> list[ImportItem]:
        """本次真正入库、源文件可以考虑删除的条目。重复、失败、预演的都不在内。"""
        if self.dry_run:
            return []
        return [i for i in self.items if i.action in IMPORTED and i.sha256 and i.rel_path]


@dataclass
class DeleteResult:
    item: ImportItem
    deleted: bool
    message: str = ""


def _within(path: Path, base: Path) -> bool:
    """path 是否等于 base 或在其之下。按平台规则比较大小写（Windows 不区分）。"""
    p, b = os.path.normcase(path), os.path.normcase(base)
    return p == b or p.startswith(b.rstrip(os.sep) + os.sep)


def _hidden(path: Path, base: Path) -> bool:
    """base 之下的任何一级以 '.' 开头即视为隐藏（如 Android 的 DCIM/.thumbnails、.trash）。"""
    return any(part.startswith(".") for part in path.relative_to(base).parts)


def iter_media_files(paths: Iterable[Path], recursive: bool = True) -> list[Path]:
    """展开参数里的文件和文件夹，保留图片和视频，跳过隐藏文件/文件夹，按路径排序。

    直接点名的文件不受"隐藏"规则限制——用户明确指定了就导入。
    """
    found: set[Path] = set()
    for p in paths:
        if p.is_dir():
            it = p.rglob("*") if recursive else p.glob("*")
            found.update(
                f
                for f in it
                if f.suffix.lower() in MEDIA_EXTS and f.is_file() and not _hidden(f, p)
            )
        elif p.is_file() and p.suffix.lower() in MEDIA_EXTS:
            found.add(p)
    return sorted(found)


# Windows / Android(FAT/exFAT/FUSE) 都不允许的字符，以及 Windows 的保留名
_BAD_CHARS = re.compile(r'[<>:"/\\|?*\x00-\x1f]')
_RESERVED = re.compile(r"^(con|prn|aux|nul|com[1-9]|lpt[1-9])(?:\.|$)", re.IGNORECASE)
_MAX_STEM_BYTES = 250  # 支持格式最长扩展名 5 字节，重名后缀再按实际长度截断


def _safe_stem(stem: str) -> str:
    """收件箱里保留原文件名，但要保证在 Windows 和 Android 上都合法、不过长。"""
    s = _BAD_CHARS.sub("_", stem).rstrip(" .")
    if _RESERVED.match(s):
        s = f"_{s}"
    raw = s.encode("utf-8")
    if len(raw) > _MAX_STEM_BYTES:
        s = raw[:_MAX_STEM_BYTES].decode("utf-8", "ignore").rstrip(" .")
    return s or "unnamed"


class _Importer:
    def __init__(self, root: Path, *, dry_run: bool) -> None:
        self.root = root
        self.dry_run = dry_run
        self.conn = db.open_library(root, readonly=dry_run)
        try:
            self.rules: RuleSet = load_rules(self.conn)
        except BaseException:
            self.conn.close()
            raise
        self.batch_id = uuid.uuid4().hex
        # 一次读取占用名称，避免导入 N 个文件时反复遍历整个目录（O(N²)）。
        parent = root / INBOX
        try:
            occupied = (
                {str(INBOX / p.name).casefold() for p in parent.iterdir()}
                if parent.is_dir()
                else set()
            )
            occupied.update(
                r[0].casefold() for r in self.conn.execute("SELECT rel_path FROM image_file")
            )
        except BaseException:
            self.conn.close()
            raise
        self.reserved: set[str] = occupied
        self.seen_sha: set[str] = set()

    def close(self) -> None:
        self.conn.close()

    def _taken(self, rel: str) -> bool:
        # 一律按"不区分大小写"判断：Windows 和 Android 共享存储都不区分，
        # 否则 A.jpg 和 a.jpg 在 Linux 上各占一行、复制到手机就互相覆盖。
        return rel.casefold() in self.reserved or (self.root / rel).exists()

    def _unique_rel(self, folder: PurePosixPath, stem: str, ext: str) -> str:
        n = 1
        while True:
            suffix = "" if n == 1 else f"_{n}"
            budget = 255 - len((suffix + ext).encode("utf-8"))
            name = stem.encode("utf-8")[:budget].decode("utf-8", "ignore").rstrip(" .")
            rel = str(folder / f"{name}{suffix}{ext}")
            if not self._taken(rel):
                break
            n += 1
        self.reserved.add(rel.casefold())
        return rel

    def _record(self, image_id: int, file_id: int, src: Path, rec: Recognition) -> bool:
        self.conn.execute(
            "INSERT INTO import_record (batch_id, file_id, orig_name) VALUES (?, ?, ?)",
            (self.batch_id, file_id, src.name),
        )
        return record_filename(self.conn, image_id, file_id, src.name, rec)

    def import_one(self, src: Path) -> ImportItem:
        try:
            sha = sha256_file(src)
        except OSError as e:
            return ImportItem(src, Action.ERROR, message=f"读取失败：{e}")

        rec = recognize(src.stem, self.rules)
        dup = self.conn.execute(
            "SELECT id, image_id, rel_path FROM image_file WHERE sha256=?", (sha,)
        ).fetchone()
        if dup:
            target = (self.root / dup["rel_path"]).resolve()
            if not target.is_relative_to(self.root / "images"):
                return ImportItem(src, Action.ERROR, message="已有文件路径异常，未写入或覆盖")
            try:
                if not target.is_file() or sha256_file(target) != sha:
                    return ImportItem(
                        src,
                        Action.ERROR,
                        message="已有图库副本缺失或校验不一致，请先修复；源文件保留",
                    )
                added = False
                if not self.dry_run:
                    with self.conn:
                        added = self._record(dup["image_id"], dup["id"], src, rec)
                return ImportItem(
                    src,
                    Action.DUP,
                    dup["rel_path"],
                    rec,
                    "已有文件，保留原整理结果",
                    sha,
                    dup["id"],
                    added,
                )
            except (OSError, sqlite3.Error) as e:
                return ImportItem(src, Action.ERROR, message=f"检查或记录已有文件失败：{e}")
        if sha in self.seen_sha:  # 只用于预演；正式导入在前一条成功提交后按库查询
            return ImportItem(src, Action.DUP, recognition=rec, message="与本批次中的另一文件相同")

        width = height = None
        if src.suffix.lower() in IMAGE_EXTS:
            try:
                with Image.open(src) as im:
                    width, height = im.size
            except Image.DecompressionBombError:
                pass  # 超大图：头部合法，只是像素数超过 Pillow 默认上限
            except Exception as e:  # noqa: BLE001 —— 任何解析失败都视为"不是图片"
                return ImportItem(src, Action.ERROR, message=f"无法识别为图片：{e}")

        action = Action.INBOX if rec.confidence is Confidence.NONE else Action.HINT
        # 合法原名与扩展名大小写尽量不变；识别建议永远不决定目录。
        try:
            rel = self._unique_rel(INBOX, _safe_stem(src.stem), src.suffix)
            target = (self.root / rel).resolve()
            if not target.is_relative_to(self.root / "images"):
                raise ValueError("收件箱目录指向图库之外，未复制")
        except (OSError, ValueError) as e:
            return ImportItem(src, Action.ERROR, message=str(e))
        item = ImportItem(src, action, rel, rec, sha256=sha)
        if self.dry_run:
            self.seen_sha.add(sha)
            return item

        dst = self.root / rel
        try:
            copy_verified(src, dst, sha)
        except OSError as e:
            return ImportItem(src, Action.ERROR, message=f"复制失败：{e}")

        try:
            with self.conn:
                image_id = self.conn.execute("INSERT INTO image DEFAULT VALUES").lastrowid
                file_id = self.conn.execute(
                    "INSERT INTO image_file (image_id, rel_path, sha256, width, height, orig_name)"
                    " VALUES (?, ?, ?, ?, ?, ?)",
                    (image_id, rel, sha, width, height, src.name),
                ).lastrowid
                item.file_id = file_id
                item.evidence_added = self._record(image_id, file_id, src, rec)
                self.conn.execute(
                    "INSERT INTO op_log (batch_id, kind, payload) VALUES (?, 'import', ?)",
                    (
                        self.batch_id,
                        json.dumps(
                            {"image_id": image_id, "file_id": file_id, "to": rel},
                            ensure_ascii=False,
                        ),
                    ),
                )
        except BaseException as e:
            dst.unlink(missing_ok=True)  # 删的是刚复制进来的副本，源文件还在
            if not isinstance(e, Exception):
                raise  # Ctrl+C 等：清理完副本后照常中断
            return ImportItem(src, Action.ERROR, message=f"写入数据库失败：{e}")

        # 只有真正入库成功才算"见过"：否则第一份失败时，同批次里内容相同的第二份会被误判为重复而跳过
        self.seen_sha.add(sha)
        return item


def import_files(
    root: Path,
    sources: Iterable[Path],
    *,
    dry_run: bool = False,
    recursive: bool = True,
) -> ImportReport:
    """把图片/视频复制进图库。不删除任何源文件——要删请在用户确认后调用 delete_sources()。

    dry_run=True 时只生成计划，不动任何文件、不写任何记录
    使用只读连接，不升级数据库或同步平台。
    """
    root = root.resolve()
    if not (root / db.DB_NAME).is_file():
        raise db.NotALibraryError(f"不是图库（找不到 {db.DB_NAME}）：{root}")
    sources = [Path(s).resolve() for s in sources]
    for s in sources:
        if _within(s, root):
            raise ValueError(f"不能从图库内部导入：{s}")

    # 图库在源文件夹里面时（如从 E:\ 导入、图库在 E:\lib），扫描要绕开图库本身
    files = [f for f in iter_media_files(sources, recursive) if not _within(f, root)]
    imp = _Importer(root, dry_run=dry_run)
    report = ImportReport(root=root, dry_run=dry_run, batch_id=imp.batch_id)
    try:
        for f in files:
            report.items.append(imp.import_one(f))
    finally:
        imp.close()
    return report


def delete_sources(report: ImportReport) -> list[DeleteResult]:
    """删除本次已导入文件的源文件。只应在用户明确确认后调用。

    每个文件删除前再查一遍，任何一项不满足就跳过、保留源文件：
    - 图库里的副本还在，且内容和导入时一致；
    - 源文件还在，且内容和导入时一致（导入后被编辑过的不删）。
    """
    results: list[DeleteResult] = []
    conn = db.open_library(report.root)
    try:
        for it in report.deletable():
            assert it.sha256 and it.rel_path
            row = conn.execute(
                "SELECT rel_path, sha256 FROM image_file WHERE id=?", (it.file_id,)
            ).fetchone()
            if row is None or row["sha256"] != it.sha256:
                results.append(DeleteResult(it, False, "图库记录已变化，保留源文件"))
                continue
            copy = (report.root / row["rel_path"]).resolve()
            if not copy.is_relative_to(report.root.resolve() / "images"):
                results.append(DeleteResult(it, False, "图库路径异常，保留源文件"))
                continue
            try:
                if not copy.is_file() or sha256_file(copy) != it.sha256:
                    results.append(DeleteResult(it, False, "图库副本缺失或已变化，保留源文件"))
                    continue
                if not it.src.is_file():
                    results.append(DeleteResult(it, False, "源文件已不在"))
                    continue
                if sha256_file(it.src) != it.sha256:
                    results.append(DeleteResult(it, False, "源文件在导入后被修改过，保留"))
                    continue
                it.src.unlink()
            except OSError as e:
                results.append(DeleteResult(it, False, f"删除失败：{e}"))
                continue
            with conn:
                conn.execute(
                    "INSERT INTO op_log (batch_id, kind, payload) VALUES (?, 'delete_source', ?)",
                    (
                        report.batch_id,
                        json.dumps({"from": str(it.src), "kept": it.rel_path}, ensure_ascii=False),
                    ),
                )
            results.append(DeleteResult(it, True))
    finally:
        conn.close()
    return results
