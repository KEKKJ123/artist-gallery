"""守护 AGENTS.md "分层"规则：core/ 不得依赖 Web 层或 Web 框架。"""

import ast
from pathlib import Path

import artist_gallery.core

FORBIDDEN = ("artist_gallery.server", "starlette", "uvicorn", "fastapi", "pydantic")


def _imports(py: Path) -> set[str]:
    """包括函数内 import；处理 from 包 import 模块，避免漏掉隐性依赖。"""
    names = set()
    for node in ast.walk(ast.parse(py.read_text("utf-8"))):
        if isinstance(node, ast.Import):
            names.update(a.name for a in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.add(node.module)
            names.update(f"{node.module}.{a.name}" for a in node.names)
    return names


def test_read_queries_do_not_import_write_pipeline_or_image_decoder():
    core_dir = Path(artist_gallery.core.__file__).parent
    forbidden = ("artist_gallery.core.importer", "artist_gallery.core.thumbnail", "PIL")
    for name in ("browse", "inbox", "images", "layout", "media", "platforms"):
        deps = _imports(core_dir / f"{name}.py")
        assert not {dep for dep in deps if dep.startswith(forbidden)}, (name, deps)


def test_python_modules_have_no_import_cycles():
    package = Path(artist_gallery.core.__file__).parent.parent
    modules = {
        "artist_gallery." + ".".join(p.relative_to(package).with_suffix("").parts): p
        for p in package.rglob("*.py")
        if p.name != "__init__.py"
    }
    edges = {name: _imports(path) & modules.keys() for name, path in modules.items()}
    done = set()

    def visit(name: str, stack: tuple[str, ...]) -> None:
        assert name not in stack, " → ".join((*stack, name))
        if name in done:
            return
        for dep in edges[name]:
            visit(dep, (*stack, name))
        done.add(name)

    for name in modules:
        visit(name, ())


def test_core_has_no_web_imports():
    core_dir = Path(artist_gallery.core.__file__).parent
    offenders = []
    for py in core_dir.rglob("*.py"):
        offenders.extend(
            f"{py.name}: {name}" for name in _imports(py) if name.startswith(FORBIDDEN)
        )
    assert not offenders, offenders
