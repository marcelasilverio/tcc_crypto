"""Keep reusable implementations in domain layers, without flat compatibility bridges."""

from __future__ import annotations

import ast
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / "src/tcc_crypto"
ENTRYPOINTS = {"__init__", "daily", "explore", "migrate", "paths"}
LAYERS = {
    "analysis",
    "collection",
    "data",
    "features",
    "modeling",
    "reporting",
    "targets",
    "visualization",
    "workflows",
}


def test_package_root_contains_only_entrypoints_and_paths():
    assert {path.stem for path in PACKAGE.glob("*.py")} == ENTRYPOINTS
    assert not list(PACKAGE.rglob("*compat*.py"))


def test_python_and_notebook_imports_use_existing_layers():
    """Reject stale or reintroduced flat imports in code, tests, scripts and notebooks."""
    sources = [
        (str(path), path.read_text())
        for directory in (PACKAGE, ROOT / "tests", ROOT / "scripts")
        for path in directory.rglob("*.py")
    ]
    for path in (ROOT / "notebooks").glob("*.ipynb"):
        notebook = json.loads(path.read_text())
        sources.extend(
            (f"{path.name}:{index}", "".join(cell["source"]))
            for index, cell in enumerate(notebook["cells"])
            if cell["cell_type"] == "code"
        )
    for origin, source in sources:
        for node in ast.walk(ast.parse(source)):
            names = (
                [alias.name for alias in node.names]
                if isinstance(node, ast.Import)
                else [node.module]
                if isinstance(node, ast.ImportFrom) and node.module
                else []
            )
            for name in names:
                if name.startswith("tcc_crypto."):
                    assert name.split(".")[1] in ENTRYPOINTS | LAYERS, (origin, name)
            if isinstance(node, ast.ImportFrom) and node.module == "tcc_crypto":
                assert {alias.name for alias in node.names} <= ENTRYPOINTS | LAYERS, (
                    origin
                )
