"""守护 AGENTS.md 规则 7：core/ 不得依赖 Web 层或 Web 框架。"""

import ast
from pathlib import Path

import artist_gallery.core

FORBIDDEN = ("artist_gallery.server", "starlette", "uvicorn", "fastapi", "pydantic")


def test_core_has_no_web_imports():
    core_dir = Path(artist_gallery.core.__file__).parent
    offenders = []
    for py in core_dir.rglob("*.py"):
        tree = ast.parse(py.read_text("utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                names = [a.name for a in node.names]
            elif isinstance(node, ast.ImportFrom) and node.module:
                names = [node.module]
            else:
                continue
            for name in names:
                if name.startswith(FORBIDDEN):
                    offenders.append(f"{py.name}: {name}")
    assert not offenders, offenders
