"""命令行入口：init / import / status。"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from artist_gallery import __version__
from artist_gallery.core import db
from artist_gallery.core.importer import Action, import_files

_ACTION_LABEL = {
    Action.AUTO: "自动归档",
    Action.HINT: "收件箱(有建议)",
    Action.INBOX: "收件箱",
    Action.DUP: "重复跳过",
    Action.SKIP: "暂不支持",
    Action.ERROR: "失败",
}


def _cmd_init(args: argparse.Namespace) -> int:
    try:
        path = db.init_library(Path(args.root))
    except FileExistsError as e:
        print(f"错误：{e}", file=sys.stderr)
        return 1
    print(f"已创建图库：{path}")
    return 0


def _cmd_import(args: argparse.Namespace) -> int:
    try:
        report = import_files(
            Path(args.library),
            [Path(p) for p in args.paths],
            move=not args.copy,
            dry_run=args.dry_run,
            recursive=not args.no_recursive,
        )
    except (FileNotFoundError, ValueError) as e:
        print(f"错误：{e}", file=sys.stderr)
        return 1

    if not report.items:
        print("没有找到图片文件。")
        return 0

    for it in report.items:
        if it.action is Action.AUTO or (it.action in (Action.HINT, Action.INBOX) and args.verbose):
            line = f"[{_ACTION_LABEL[it.action]}] {it.src.name} -> {it.rel_path}"
        elif it.action is Action.HINT:
            r = it.recognition
            guess = f"{r.platform}:{r.post_id}" if r.post_id else f"{r.platform}（需手动补链接）"
            line = f"[{_ACTION_LABEL[it.action]}] {it.src.name}  可能是 {guess}"
        elif it.action in (Action.DUP, Action.SKIP, Action.ERROR) or args.verbose:
            line = f"[{_ACTION_LABEL[it.action]}] {it.src.name}  {it.message}"
        else:
            continue
        if it.message and it.action not in (Action.DUP, Action.SKIP, Action.ERROR):
            line += f"  ({it.message})"
        print(line)

    c = report.counts()
    summary = "，".join(f"{_ACTION_LABEL[a]} {c[a]}" for a in Action if c[a])
    prefix = "【预演，未做任何改动】" if report.dry_run else ""
    print(f"\n{prefix}共 {len(report.items)} 个文件：{summary}")
    if not report.dry_run and not args.copy and (c[Action.AUTO] + c[Action.HINT] + c[Action.INBOX]):
        print("源文件已移入图库（校验通过后才删除原文件）。")
    return 1 if c[Action.ERROR] else 0


def _cmd_status(args: argparse.Namespace) -> int:
    root = Path(args.library)
    if not (root / db.DB_NAME).exists():
        print(f"错误：不是图库：{root}", file=sys.stderr)
        return 1
    conn = db.connect(root)
    try:
        db.migrate(conn)

        def count(table: str, where: str = "1") -> int:
            return conn.execute(f"SELECT COUNT(*) FROM {table} WHERE {where}").fetchone()[0]

        inbox = count("image", "work_id IS NULL")
        hinted = count("image", "work_id IS NULL AND source_hint IS NOT NULL")
        print(f"图库：{root.resolve()}")
        print(f"  图片      {count('image')}")
        print(f"  作品      {count('work')}")
        print(f"  收件箱    {inbox}（其中有来源建议 {hinted}）")
        print(f"  画师      {count('artist')}")
        print(f"  tag       {count('tag')}")
        for row in conn.execute(
            "SELECT platform, COUNT(*) FROM source GROUP BY platform ORDER BY 2 DESC"
        ):
            print(f"  来源 {row[0]:<8}{row[1]}")
    finally:
        conn.close()
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="artist-gallery", description="本地画师作品图库")
    p.add_argument("--version", action="version", version=__version__)
    sub = p.add_subparsers(dest="cmd", required=True)

    p_init = sub.add_parser("init", help="在指定目录新建图库")
    p_init.add_argument("root", help="图库根目录")
    p_init.set_defaults(func=_cmd_init)

    p_imp = sub.add_parser("import", help="导入图片（默认移动进图库）")
    p_imp.add_argument("library", help="图库根目录")
    p_imp.add_argument("paths", nargs="+", help="要导入的文件或文件夹")
    p_imp.add_argument("--copy", action="store_true", help="复制而不是移动，保留源文件")
    p_imp.add_argument("-n", "--dry-run", action="store_true", help="只显示计划，不做任何改动")
    p_imp.add_argument("--no-recursive", action="store_true", help="不进入子文件夹")
    p_imp.add_argument("-v", "--verbose", action="store_true", help="逐个列出所有文件")
    p_imp.set_defaults(func=_cmd_import)

    p_st = sub.add_parser("status", help="显示图库统计")
    p_st.add_argument("library", help="图库根目录")
    p_st.set_defaults(func=_cmd_status)

    return p


def main(argv: list[str] | None = None) -> int:
    # Windows 控制台默认 GBK，统一用 UTF-8 输出，避免中文文件名乱码或报错
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")
    args = build_parser().parse_args(argv)
    return args.func(args)
