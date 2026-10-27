"""把外部图片/视频导入图库，分两段：

1. `import_files()`：计算 hash → 识别来源 → 复制并校验 → 写库。**永远不删源文件。**
2. `delete_sources()`：用户确认后才调用。删除前再校验一次"图库副本完好、源文件没被改过"。

这样"删不删源文件"是导入完成后、看过结果再做的独立决定（CLI 里的确认提示，界面里的复选框）。
视频和图片走同一套文件名识别与归档；只是不读取宽高（不引入视频解析依赖）。
"""

from __future__ import annotations

import json
import os
import re
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


class Action(StrEnum):
    AUTO = "auto"  # 高置信，已归档到 images/{platform}/
    HINT = "hint"  # 中置信，进收件箱并附建议
    INBOX = "inbox"  # 未识别，进收件箱
    DUP = "dup"  # 图库里已有相同文件，跳过（源文件不动）
    ERROR = "error"


IMPORTED = frozenset({Action.AUTO, Action.HINT, Action.INBOX})


@dataclass
class ImportItem:
    src: Path
    action: Action
    rel_path: str | None = None
    recognition: Recognition | None = None
    message: str = ""
    sha256: str | None = None


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


def _safe_id(s: str) -> str:
    """文件名里只保留 [0-9A-Za-z-]，保证能被 OWN_FORMAT 反解析。"""
    return "".join(c if c.isascii() and (c.isalnum() or c == "-") else "-" for c in s)


# Windows / Android(FAT/exFAT/FUSE) 都不允许的字符，以及 Windows 的保留名
_BAD_CHARS = re.compile(r'[<>:"/\\|?*\x00-\x1f]')
_RESERVED = re.compile(r"^(con|prn|aux|nul|com[1-9]|lpt[1-9])$", re.IGNORECASE)
_MAX_STEM_BYTES = 150  # 多数文件系统单个文件名上限 255 字节，留出后缀和 _N 的余量


def _safe_stem(stem: str) -> str:
    """收件箱里保留原文件名，但要保证在 Windows 和 Android 上都合法、不过长。"""
    s = _BAD_CHARS.sub("_", stem).rstrip(" .")
    if _RESERVED.match(s):
        s = f"_{s}"
    raw = s.encode("utf-8")
    if len(raw) > _MAX_STEM_BYTES:
        s = raw[:_MAX_STEM_BYTES].decode("utf-8", "ignore").rstrip(" .")
    return s or "unnamed"


def _target_dir_and_stem(rec: Recognition, src: Path) -> tuple[PurePosixPath, str]:
    if rec.confidence is Confidence.HIGH:
        assert rec.platform and rec.post_id is not None
        return (
            PurePosixPath("images", rec.platform),
            f"{rec.platform}_{_safe_id(rec.post_id)}_p{rec.page or 0}",
        )
    return INBOX, _safe_stem(src.stem)


class _Importer:
    def __init__(self, root: Path, *, dry_run: bool) -> None:
        self.root = root
        self.dry_run = dry_run
        self.conn = db.open_library(root)
        self.rules: RuleSet = load_rules(self.conn)
        self.batch_id = uuid.uuid4().hex
        # 本批次已占用的 rel_path（小写）。dry-run 时文件没真的落盘，只能靠它防重名。
        self.reserved: set[str] = set()
        self.seen_sha: set[str] = set()

    def close(self) -> None:
        self.conn.close()

    def _taken(self, rel: str) -> bool:
        # 一律按"不区分大小写"判断：Windows 和 Android 共享存储都不区分，
        # 否则 A.jpg 和 a.jpg 在 Linux 上各占一行、复制到手机就互相覆盖。
        if rel.lower() in self.reserved or (self.root / rel).exists():
            return True
        return (
            self.conn.execute(
                "SELECT 1 FROM image WHERE rel_path = ? COLLATE NOCASE", (rel,)
            ).fetchone()
            is not None
        )

    def _unique_rel(self, folder: PurePosixPath, stem: str, ext: str) -> str:
        rel = str(folder / f"{stem}{ext}")
        n = 1
        while self._taken(rel):
            n += 1
            rel = str(folder / f"{stem}_{n}{ext}")
        self.reserved.add(rel.lower())
        return rel

    def _work_for(self, platform: str, post_id: str) -> int:
        row = self.conn.execute(
            "SELECT work_id FROM source WHERE platform = ? AND post_id = ?", (platform, post_id)
        ).fetchone()
        if row:
            return row[0]
        work_id = self.conn.execute("INSERT INTO work DEFAULT VALUES").lastrowid
        self.conn.execute(
            "INSERT INTO source (work_id, platform, post_id) VALUES (?, ?, ?)",
            (work_id, platform, post_id),
        )
        return work_id

    def import_one(self, src: Path) -> ImportItem:
        try:
            sha = sha256_file(src)
        except OSError as e:
            return ImportItem(src, Action.ERROR, message=f"读取失败：{e}")

        dup = self.conn.execute("SELECT rel_path FROM image WHERE sha256 = ?", (sha,)).fetchone()
        if dup or sha in self.seen_sha:
            where = dup[0] if dup else "本批次中的另一文件"
            return ImportItem(src, Action.DUP, message=f"与 {where} 相同")

        width = height = None
        if src.suffix.lower() in IMAGE_EXTS:
            try:
                with Image.open(src) as im:
                    width, height = im.size
            except Image.DecompressionBombError:
                pass  # 超大图：头部合法，只是像素数超过 Pillow 默认上限
            except Exception as e:  # noqa: BLE001 —— 任何解析失败都视为"不是图片"
                return ImportItem(src, Action.ERROR, message=f"无法识别为图片：{e}")

        rec = recognize(src.stem, self.rules)
        action = {
            Confidence.HIGH: Action.AUTO,
            Confidence.MEDIUM: Action.HINT,
            Confidence.NONE: Action.INBOX,
        }[rec.confidence]
        folder, stem = _target_dir_and_stem(rec, src)
        rel = self._unique_rel(folder, stem, src.suffix.lower())
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
                work_id = page = hint = None
                if action is Action.AUTO:
                    assert rec.platform and rec.post_id is not None
                    work_id = self._work_for(rec.platform, rec.post_id)
                    page = rec.page
                elif action is Action.HINT:
                    hint = json.dumps(
                        {"platform": rec.platform, "post_id": rec.post_id, "page": rec.page}
                    )
                image_id = self.conn.execute(
                    "INSERT INTO image (work_id, rel_path, sha256, page, width, height,"
                    " orig_name, source_hint) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                    (work_id, rel, sha, page, width, height, src.name, hint),
                ).lastrowid
                self.conn.execute(
                    "INSERT INTO op_log (batch_id, kind, payload) VALUES (?, 'import', ?)",
                    (
                        self.batch_id,
                        json.dumps(
                            {"image_id": image_id, "from": str(src), "to": rel},
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
    （唯一例外：旧版图库仍会被升级数据库结构，这和打开图库时的行为一致）。
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
            copy = report.root / it.rel_path
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
