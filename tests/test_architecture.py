"""Enforce the deliberately approved module and presentation boundaries."""

import ast
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MODULES = {
    "__init__",
    "collection",
    "preparation",
    "dataset",
    "training",
    "results",
    "experiment",
    "config",
    "paths",
}


def test_active_modules_and_dependencies():
    source = ROOT / "src/tcc_crypto"
    assert {p.stem for p in source.glob("*.py")} == MODULES
    assert not [p for p in source.rglob("*.py") if p.parent != source]
    forbidden = {
        "preparation": {"experiment", "results", "collection"},
        "dataset": {"experiment", "results", "collection"},
        "training": {"experiment", "results", "collection"},
        "results": {"experiment", "dataset", "training", "collection"},
    }
    for path in source.glob("*.py"):
        tree = ast.parse(path.read_text())
        for node in ast.walk(tree):
            if (
                isinstance(node, ast.ImportFrom)
                and node.module
                and node.module.startswith("tcc_crypto")
            ):
                names = set(node.module.split(".")) | {n.name for n in node.names}
                assert not names & forbidden.get(path.stem, set())
            if isinstance(node, ast.Call):
                name = getattr(node.func, "attr", getattr(node.func, "id", ""))
                assert name not in {"to_excel", "read_excel", "ExcelWriter"}
                if path.stem in {"preparation", "dataset", "training"}:
                    assert name not in {
                        "open",
                        "read_csv",
                        "to_csv",
                        "write_text",
                        "mkdir",
                    }
    assert {p.name for p in (ROOT / "configs").glob("*.json")} == {
        "experiment.json",
        "svm_grid.json",
    }


def test_notebook_is_an_explicit_stage_client():
    notebooks = list((ROOT / "notebooks").glob("*.ipynb"))
    assert [p.name for p in notebooks] == [
        "17_binance_daily_svm_experiment_walkthrough.ipynb"
    ]
    notebook = json.loads(notebooks[0].read_text())
    allowed = {"load_config", "select_symbols", "Paths", "display"}
    methods = {
        "collect",
        "prepare",
        "build_datasets",
        "train",
        "consolidate",
        "inspect",
        "inspect_windows",
        "main",
    }
    for cell in notebook["cells"]:
        if cell["cell_type"] != "code":
            continue
        tree = ast.parse("".join(cell["source"]))
        for node in ast.walk(tree):
            assert not isinstance(
                node,
                (
                    ast.For,
                    ast.While,
                    ast.If,
                    ast.ListComp,
                    ast.DictComp,
                    ast.SetComp,
                    ast.GeneratorExp,
                    ast.FunctionDef,
                ),
            )
            if isinstance(node, ast.Call):
                if isinstance(node.func, ast.Name):
                    assert node.func.id in allowed
                else:
                    assert isinstance(node.func, ast.Attribute)
                    assert node.func.attr in methods
                    assert isinstance(node.func.value, ast.Name)
                    assert node.func.value.id in {"experiment", "paths"}
