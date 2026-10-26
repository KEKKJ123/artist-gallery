"""命令行入口。M0 只有 init；import / scan 等后续加入。"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from artist_gallery import __version__, db


def _cmd_init(args: argparse.Namespace) -> int:
    try:
        path = db.init_library(Path(args.root))
    except FileExistsError as e:
        print(f"错误：{e}", file=sys.stderr)
        return 1
    print(f"已创建图库：{path}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="artist-gallery", description="本地画师作品图库")
    p.add_argument("--version", action="version", version=__version__)
    sub = p.add_subparsers(dest="cmd", required=True)

    p_init = sub.add_parser("init", help="在指定目录新建图库")
    p_init.add_argument("root", help="图库根目录")
    p_init.set_defaults(func=_cmd_init)

    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)
