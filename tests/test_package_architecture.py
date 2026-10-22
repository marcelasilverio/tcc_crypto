"""Keep reusable implementations in domain layers, without flat compatibility bridges."""

from __future__ import annotations

import ast
import json
from importlib.util import resolve_name
from pathlib import Path

import pytest

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


def internal_imports(source: str, module: str, *, is_package: bool = False):
    """Resolve absolute and relative imports without importing research code."""
    package = module if is_package else module.rpartition(".")[0]
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Import):
            names = [alias.name for alias in node.names]
        elif isinstance(node, ast.ImportFrom):
            base = node.module or ""
            if node.level:
                base = resolve_name("." * node.level + base, package)
            names = [base, *(f"{base}.{alias.name}" for alias in node.names)]
        else:
            continue
        for name in names:
            if name.startswith("tcc_crypto."):
                yield name


def module_exists(name: str) -> bool:
    path = PACKAGE.joinpath(*name.split(".")[1:])
    return path.with_suffix(".py").is_file() or (path / "__init__.py").is_file()


def forbidden_dependencies(layer: str, imports: list[str]) -> list[str]:
    """Enforce known boundaries without inventing a universal dependency graph."""
    forbidden = ENTRYPOINTS - {"__init__", "paths"}
    if layer not in {"workflows", "reporting"}:
        forbidden = forbidden | {"workflows"}
    if layer in {"features", "targets", "modeling"}:
        forbidden = forbidden | {"analysis", "collection", "reporting", "visualization"}
    violations = [name for name in imports if name.split(".")[1] in forbidden]
    if layer == "reporting":
        # Existing result types and a column-list helper are not orchestration.
        allowed_workflow_imports = {
            "tcc_crypto.workflows.datasets",
            "tcc_crypto.workflows.datasets.modeling_feature_columns",
            "tcc_crypto.workflows.exploration_context",
            "tcc_crypto.workflows.exploration_context.ExplorationContext",
            "tcc_crypto.workflows.exploration_inputs",
            "tcc_crypto.workflows.exploration_inputs.ExplorationInputs",
            "tcc_crypto.workflows.exploration_calculations",
            "tcc_crypto.workflows.exploration_calculations.ExplorationResult",
        }
        violations.extend(
            name
            for name in imports
            if name.startswith("tcc_crypto.workflows")
            and name not in allowed_workflow_imports
        )
    return violations


def notebook_violations(source: str) -> list[str]:
    """Allow literal settings, imported workflow/presentation calls and display."""
    tree = ast.parse(source)
    allowed_nodes = (
        ast.Module,
        ast.Import,
        ast.ImportFrom,
        ast.alias,
        ast.Assign,
        ast.AnnAssign,
        ast.Expr,
        ast.Name,
        ast.Load,
        ast.Store,
        ast.Call,
        ast.Attribute,
        ast.Constant,
        ast.keyword,
        ast.Tuple,
        ast.List,
        ast.Dict,
        ast.Set,
        ast.UnaryOp,
        ast.USub,
        ast.UAdd,
    )
    errors = [
        type(node).__name__
        for node in ast.walk(tree)
        if not isinstance(node, allowed_nodes)
    ]
    imports = set()
    for node in tree.body:
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            base = node.module if isinstance(node, ast.ImportFrom) else None
            for alias in node.names:
                name = f"{base}.{alias.name}" if base else alias.name
                if (
                    getattr(node, "level", 0)
                    or alias.name == "*"
                    or not (
                        name == "IPython.display.display"
                        or name.startswith("tcc_crypto.workflows.")
                        or name.startswith("tcc_crypto.visualization.")
                    )
                ):
                    errors.append(f"Import: {name}")
                imports.add(alias.asname or alias.name.split(".")[0])
        for child in ast.walk(node):
            if isinstance(child, ast.Attribute) and isinstance(child.ctx, ast.Store):
                errors.append("Result mutation")
            if isinstance(child, ast.UnaryOp) and not (
                isinstance(child.operand, ast.Constant)
                and isinstance(child.operand.value, (int, float))
            ):
                errors.append("Calculated unary expression")
            if isinstance(child, ast.Name) and isinstance(child.ctx, ast.Store):
                if child.id in imports:
                    errors.append(f"Reassigned import: {child.id}")
            if isinstance(child, ast.Call):
                function = child.func
                # One attribute supports workflow.calculate(...); chained calls
                # such as workflow.calculate(...).mean() implement notebook logic.
                root = (
                    function.value if isinstance(function, ast.Attribute) else function
                )
                if not isinstance(root, ast.Name) or root.id not in imports:
                    errors.append(f"Call: {ast.unparse(function)}")
    return errors


def test_package_root_contains_only_entrypoints_and_paths():
    assert {path.stem for path in PACKAGE.glob("*.py")} == ENTRYPOINTS
    assert {
        path.name
        for path in PACKAGE.iterdir()
        if path.is_dir() and not path.name.startswith((".", "__"))
    } == LAYERS
    assert not list(PACKAGE.rglob("*compat*.py"))


def test_domain_imports_preserve_responsibility_boundaries():
    for path in PACKAGE.rglob("*.py"):
        relative = path.relative_to(PACKAGE)
        if len(relative.parts) < 2:
            continue
        module = "tcc_crypto." + ".".join(relative.with_suffix("").parts)
        is_package = path.name == "__init__.py"
        if is_package:
            module = module.removesuffix(".__init__")
        imports = list(
            internal_imports(path.read_text(), module, is_package=is_package)
        )
        assert not forbidden_dependencies(relative.parts[0], imports), relative


@pytest.mark.parametrize(
    "source",
    [
        "import tcc_crypto.workflows.svm",
        "from tcc_crypto import workflows",
        "from ..workflows import svm",
        "from .. import workflows",
        "from .. import daily",
    ],
)
def test_boundary_guard_detects_absolute_and_relative_imports(source):
    imports = list(internal_imports(source, "tcc_crypto.modeling.example"))
    assert forbidden_dependencies("modeling", imports)


@pytest.mark.parametrize("layer", ["features", "targets", "modeling"])
@pytest.mark.parametrize(
    "dependency", ["analysis", "collection", "reporting", "visualization"]
)
def test_calculation_layers_reject_external_responsibilities(layer, dependency):
    assert forbidden_dependencies(layer, [f"tcc_crypto.{dependency}.example"])


def test_reporting_guard_rejects_workflow_execution_imports():
    imports = list(
        internal_imports(
            "from tcc_crypto.workflows.exploration_calculations import calculate",
            "tcc_crypto.reporting.example",
        )
    )
    assert forbidden_dependencies("reporting", imports)


def test_notebooks_have_only_configuration_calls_and_display():
    for path in (ROOT / "notebooks").glob("*.ipynb"):
        notebook = json.loads(path.read_text())
        source = "\n".join(
            "".join(cell["source"])
            for cell in notebook["cells"]
            if cell["cell_type"] == "code"
        )
        assert not notebook_violations(source), (path.name, notebook_violations(source))


@pytest.mark.parametrize(
    "statement",
    [
        "values = [x for x in data]",
        "for x in data:\n    display(x)",
        "if flag:\n    result = workflow.calculate(context)",
        "def calculate():\n    return 1",
        "result = data.mean()",
        "result = data.groupby('symbol')",
        "result = workflow.calculate(context).mean()",
        "result = 1 + 2",
        "result = eval('1 + 2')",
        "from pandas import read_csv",
        "import requests",
        "from tcc_crypto.modeling.pilot import run_default_svc_rolling_pilot",
        "from tcc_crypto.workflows import *",
        "workflow = data\nresult = workflow.mean()",
        "result.columns = ['value']",
        "result = -data",
    ],
)
def test_notebook_guard_rejects_processing_and_bypasses(statement):
    source = "from tcc_crypto.workflows import exploration as workflow\n" + statement
    assert notebook_violations(source)


def test_notebook_guard_accepts_stepwise_configuration_and_display():
    assert not notebook_violations("""
from IPython.display import display
from tcc_crypto.workflows import exploration as workflow
RUN_ID = "example"
SYMBOLS = ["BTCUSDT"]
context = workflow.open_exploration("hourly-prices", run_id=RUN_ID)
inputs = workflow.load_inputs(context)
result = workflow.calculate(context, inputs)
display(workflow.table_preview(result))
""")


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
                    assert module_exists(name), (origin, name)
            if isinstance(node, ast.ImportFrom) and node.module == "tcc_crypto":
                assert {alias.name for alias in node.names} <= ENTRYPOINTS | LAYERS, (
                    origin
                )
