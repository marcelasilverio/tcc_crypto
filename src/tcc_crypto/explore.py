"""Independent exploratory stages: python -m tcc_crypto.explore ANALYSIS OPERATION."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from tcc_crypto.workflows import exploration as workflow
from tcc_crypto.workflows.exploration_context import API_ANALYSES, DEFAULT_CONFIGS
from tcc_crypto.workflows.exploration_figures import PLOTTABLE


def parser() -> argparse.ArgumentParser:
    command = argparse.ArgumentParser(description=__doc__)
    analyses = command.add_subparsers(dest="analysis", required=True)
    for analysis in DEFAULT_CONFIGS:
        operations = analyses.add_parser(analysis).add_subparsers(
            dest="operation", required=True
        )
        choices = ["paths", "calculate", "export", "run"]
        if analysis in API_ANALYSES:
            choices.append("collect")
        if analysis in PLOTTABLE:
            choices.append("plot")
        for operation in choices:
            sub = operations.add_parser(operation)
            sub.add_argument("--config", type=Path)
            sub.add_argument("--repository-root", type=Path)
            sub.add_argument("--run-id", required=operation not in ("paths", "run"))
            sub.add_argument("--symbols", nargs="+")
            sub.add_argument("--overwrite", action="store_true")
    return command


def main(argv: list[str] | None = None) -> None:
    args = parser().parse_args(argv)
    try:
        context = workflow.open_exploration(
            args.analysis,
            config_path=args.config,
            root=args.repository_root,
            run_id=args.run_id,
            symbols=tuple(args.symbols) if args.symbols else None,
        )
        if args.operation == "paths":
            print(
                json.dumps(
                    {"run_id": context.paths.run_id, **context.paths.inventory()},
                    indent=2,
                )
            )
            return
        if args.operation == "run":
            workflow.run(context, overwrite=args.overwrite)
        elif args.operation == "collect":
            workflow.save_inputs(
                context, workflow.collect_inputs(context), overwrite=args.overwrite
            )
        elif args.operation == "calculate":
            inputs = (
                workflow.load_saved_inputs(context)
                if args.analysis in API_ANALYSES
                else workflow.load_inputs(context)
            )
            if args.analysis not in API_ANALYSES:
                workflow.save_inputs(context, inputs, overwrite=args.overwrite)
            workflow.save_results(
                context, workflow.calculate(context, inputs), overwrite=args.overwrite
            )
        else:
            inputs = workflow.load_saved_inputs(context)
            result = workflow.load_results(context)
            if args.operation == "plot":
                workflow.plot_saved(context, inputs, result, overwrite=args.overwrite)
            else:
                workflow.export_workbooks(
                    context, inputs, result, overwrite=args.overwrite
                )
        print(
            json.dumps(
                {"run_id": context.paths.run_id, **context.paths.inventory()}, indent=2
            )
        )
    except (ValueError, FileNotFoundError, FileExistsError) as error:
        raise SystemExit(str(error)) from error


if __name__ == "__main__":
    main()
