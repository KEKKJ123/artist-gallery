"""把外部图片/视频导入图库：计算 hash → 识别来源 → 复制校验 → 写库 →（移动模式下）删除源文件。

视频和图片走同一套文件名识别与归档；只是不读取宽高（不引入视频解析依赖）。
"""

from __future__ import annotations

import json
import uuid
from collections import Counter
from collections.abc import Iterable
from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path, PurePosixPath

from PIL import Image

from artist_gallery.core import db
from artist_gallery.core.fileops import copy_verified, sha256_file
from artist_gallery.core.recognize import Confidence, Recognition, RuleSet, load_rules, recognize

IMAGE_EXTS = frozenset({".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp"})
VIDEO_EXTS = frozenset({".mp4", ".webm", ".mov", ".mkv", ".avi", ".m4v"})
MEDIA_EXTS = IMAGE_EXTS | VIDEO_EXTS
INBOX = PurePosixPath("images/_inbox")


class Action(StrEnum):
    AUTO = "auto"  # 高置信，已归档到 images/{platform}/
    HINT = "hint"  # 中置信，进收件箱并附建议
    INBOX = "inbox"  # 未识别，进收件箱
    DUP = "dup"  # 图库里已有相同文件，跳过（源文件不动）
    ERROR = "error"


@dataclass
class ImportItem:
    src: Path
    action: Action
    rel_path: str | None = None
    recognition: Recognition | None = None
    message: str = ""


@dataclass
class ImportReport:
    items: list[ImportItem] = field(default_factory=list)
    dry_run: bool = False

    def counts(self) -> Counter[Action]:
        return Counter(i.action for i in self.items)


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


def _target_dir_and_stem(rec: Recognition, src: Path) -> tuple[PurePosixPath, str]:
    if rec.confidence is Confidence.HIGH:
        assert rec.platform and rec.post_id is not None
        return (
            PurePosixPath("images", rec.platform),
            f"{rec.platform}_{_safe_id(rec.post_id)}_p{rec.page or 0}",
        )
    return INBOX, src.stem


class _Importer:
    def __init__(self, root: Path, *, move: bool, dry_run: bool) -> None:
        self.root = root
        self.move = move
        self.dry_run = dry_run
        self.conn = db.connect(root)
        db.migrate(self.conn)
        self.rules: RuleSet = load_rules(self.conn)
        self.batch_id = uuid.uuid4().hex
        self.reserved: set[str] = set()  # 本批次已占用的 rel_path（dry-run 时尤其需要）
        self.seen_sha: set[str] = set()

    def close(self) -> None:
        self.conn.close()

    def _taken(self, rel: str) -> bool:
        if rel in self.reserved or (self.root / rel).exists():
            return True
        return (
            self.conn.execute("SELECT 1 FROM image WHERE rel_path = ?", (rel,)).fetchone()
            is not None
        )

    def _unique_rel(self, folder: PurePosixPath, stem: str, ext: str) -> str:
        rel = str(folder / f"{stem}{ext}")
        n = 1
        while self._taken(rel):
            n += 1
            rel = str(folder / f"{stem}_{n}{ext}")
        self.reserved.add(rel)
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
        self.seen_sha.add(sha)
        item = ImportItem(src, action, rel, rec)
        if self.dry_run:
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
                            {"image_id": image_id, "from": str(src), "to": rel, "moved": self.move},
                            ensure_ascii=False,
                        ),
                    ),
                )
        except Exception as e:
            dst.unlink(missing_ok=True)  # 删的是刚复制进来的副本，源文件还在
            return ImportItem(src, Action.ERROR, message=f"写入数据库失败：{e}")

        if self.move:
            try:
                src.unlink()
            except OSError as e:
                item.message = f"已导入，但删除源文件失败：{e}"
        return item


def import_files(
    root: Path,
    sources: Iterable[Path],
    *,
    move: bool = True,
    dry_run: bool = False,
    recursive: bool = True,
) -> ImportReport:
    """导入图片到图库。move=False 时保留源文件；dry_run=True 时只生成计划，不改动任何东西。"""
    root = root.resolve()
    if not (root / db.DB_NAME).exists():
        raise FileNotFoundError(f"不是图库（找不到 {db.DB_NAME}）：{root}")
    sources = [Path(s).resolve() for s in sources]
    for s in sources:
        if s == root or s.is_relative_to(root):
            raise ValueError(f"不能从图库内部导入：{s}")

    files = iter_media_files(sources, recursive)
    report = ImportReport(dry_run=dry_run)
    imp = _Importer(root, move=move, dry_run=dry_run)
    try:
        for f in files:
            report.items.append(imp.import_one(f))
    finally:
        imp.close()
    return report
