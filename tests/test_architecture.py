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
    "portfolio",
    "backtesting",
}


def test_active_modules_and_dependencies():
    source = ROOT / "src/tcc_crypto"
    assert {p.stem for p in source.glob("*.py")} == MODULES
    assert not [p for p in source.rglob("*.py") if p.parent != source]
    forbidden = {
        "portfolio": {"experiment", "results", "collection", "backtesting"},
        "backtesting": {"experiment", "results", "collection", "training"},
        "preparation": {"experiment", "results", "collection"},
        "dataset": {"experiment", "results", "collection"},
        "training": {"experiment", "results", "collection"},
        "results": {
            "experiment",
            "dataset",
            "training",
            "collection",
            "portfolio",
            "backtesting",
        },
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
                if path.stem in {
                    "preparation",
                    "dataset",
                    "training",
                    "portfolio",
                    "backtesting",
                }:
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
        "portfolio.json",
    }


def test_notebook_is_an_explicit_stage_client():
    notebooks = sorted((ROOT / "notebooks").glob("*.ipynb"))
    assert [p.name for p in notebooks] == [
        "17_binance_daily_svm_experiment_walkthrough.ipynb",
        "18_binance_daily_svm_results_visual_report.ipynb",
        "19_binance_daily_portfolio_results_visual_report.ipynb",
    ]
    for notebook_path in notebooks:
        if notebook_path.name in {
            "18_binance_daily_svm_results_visual_report.ipynb",
            "19_binance_daily_portfolio_results_visual_report.ipynb",
        }:
            _check_metrics_notebook(notebook_path)
        else:
            _check_notebook_calls(notebook_path)


def _check_notebook_calls(notebook_path):
    notebook = json.loads(notebook_path.read_text())
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
        "load_report",
        "preview",
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
                    assert node.func.value.id in {"experiment", "paths", "results"}


def _check_metrics_notebook(path):
    notebook = json.loads(path.read_text())
    assert notebook["metadata"]["tcc_crypto"] == {
        "kind": "metrics",
        "language": "pt-BR",
    }
    imports = {
        "IPython.display",
        "matplotlib.pyplot",
        "numpy",
        "pandas",
        "matplotlib.colors",
        "tcc_crypto",
        "tcc_crypto.paths",
    }
    forbidden = {
        "collect",
        "prepare",
        "build_datasets",
        "train",
        "run",
        "main",
        "consolidate",
        "fit",
        "fit_transform",
        "fit_predict",
        "read_csv",
        "to_csv",
        "open",
        "write_text",
        "exec",
        "eval",
        "__import__",
        "execute_portfolio",
        "allocate_portfolios",
        "simulate_capital",
        "minimum_variance_weights",
        "plot_report",
        "report_slice",
        "report_summary",
    }
    charts = []
    for cell in notebook["cells"]:
        if cell["cell_type"] != "code":
            continue
        tree = ast.parse("".join(cell["source"]))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                assert all(alias.name in imports for alias in node.names)
            if isinstance(node, ast.ImportFrom):
                assert node.module in imports
                if node.module == "tcc_crypto":
                    assert [alias.name for alias in node.names] == ["experiment"]
            if isinstance(node, ast.Call):
                name = getattr(node.func, "attr", getattr(node.func, "id", ""))
                assert name not in forbidden
                if isinstance(node.func, ast.Attribute) and isinstance(
                    node.func.value, ast.Name
                ):
                    if node.func.value.id == "experiment":
                        assert node.func.attr == (
                            "load_portfolio_report"
                            if path.name.startswith("19_")
                            else "load_report"
                        )
        if "report-chart" in cell.get("metadata", {}).get("tags", []):
            charts.append(cell)
            assert any(
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Attribute)
                and node.func.attr == "subplots"
                for node in ast.walk(tree)
            )
    assert len(charts) == (3 if path.name.startswith("19_") else 18)
