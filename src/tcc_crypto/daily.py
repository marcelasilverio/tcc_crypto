"""Run explicit stages of the daily pipeline: python -m tcc_crypto.daily --help."""

from __future__ import annotations

import argparse
import json
import logging
from pathlib import Path
from typing import Sequence

from tcc_crypto.paths import COLLECTION_CONFIG_PATH, repository_root, resolve_path

LOGGER = logging.getLogger(__name__)


def parser() -> argparse.ArgumentParser:
    command = argparse.ArgumentParser(description=__doc__)
    command.add_argument(
        "stage",
        choices=(
            "paths",
            "collect",
            "align",
            "features",
            "targets",
            "dataset",
            "prepare",
            "pilot",
            "grid-search",
            "final-test",
            "export",
        ),
    )
    command.add_argument(
        "--profile",
        choices=("pilot", "development", "experiment"),
        default=None,
        help="Data context; experiment prepares the full approved period without modeling. Defaults to development (pilot for the pilot command).",
    )
    command.add_argument(
        "--config", type=Path, help="Experiment JSON; collect uses a collection JSON."
    )
    command.add_argument("--repository-root", type=Path)
    symbols = command.add_mutually_exclusive_group()
    symbols.add_argument(
        "--symbols",
        nargs="+",
        help="Defaults to BTCUSDT for development or the configured pilot symbol.",
    )
    symbols.add_argument(
        "--all-symbols",
        action="store_true",
        help="Explicitly execute the configured universe.",
    )
    command.add_argument(
        "--overwrite",
        action="store_true",
        help="Replace derived outputs; never overwrite raw data.",
    )
    command.add_argument(
        "--kind",
        choices=("dataset", "results", "final-results"),
        default="dataset",
        help="Workbook to regenerate with export.",
    )
    command.add_argument(
        "--eligibility-only",
        action="store_true",
        help="With grid-search: inspect prepared-dataset eligibility without fitting.",
    )
    return command


def _collect(args: argparse.Namespace, root: Path) -> None:
    from tcc_crypto.collection.config import load_collection_config
    from tcc_crypto.collection.pipeline import run_collection

    config = load_collection_config(
        resolve_path(root, args.config or COLLECTION_CONFIG_PATH)
    )
    symbols = (
        config.symbols if args.all_symbols else tuple(args.symbols or ("BTCUSDT",))
    )
    _, manifest = run_collection(
        config, root, symbols=symbols, progress_callback=LOGGER.info
    )
    print(manifest)


def main(argv: Sequence[str] | None = None) -> None:
    arguments = parser()
    args = arguments.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    root = repository_root(args.repository_root)
    if args.eligibility_only and args.stage != "grid-search":
        arguments.error("--eligibility-only applies only to grid-search.")
    if args.profile == "experiment" and (
        args.stage in ("collect", "pilot", "grid-search", "final-test")
        or (args.stage == "export" and args.kind in ("results", "final-results"))
    ):
        arguments.error(
            "The experiment profile supports data preparation and dataset export only."
        )
    if args.stage == "collect":
        _collect(args, root)
        return
    from tcc_crypto.workflows import daily_data, svm
    from tcc_crypto.workflows.context import load_context

    profile = args.profile or ("pilot" if args.stage == "pilot" else "development")
    if (args.stage == "pilot" and profile != "pilot") or (
        args.stage in ("grid-search", "final-test") and profile != "development"
    ):
        arguments.error("The model command and profile must match.")
    initial = load_context(profile, config_path=args.config, root=root)
    symbols = (
        getattr(initial.model, "candidate_symbols", (initial.data.symbol,))
        if args.all_symbols
        else tuple(args.symbols or (initial.data.symbol,))
    )
    if len(set(symbols)) != len(symbols):
        arguments.error("Symbols must be unique.")
    contexts = [
        load_context(profile, config_path=args.config, symbol=symbol, root=root)
        for symbol in symbols
    ]
    for context in contexts:
        if args.stage == "paths":
            print(json.dumps(context.paths.inventory(context.kind), indent=2))
        elif args.stage in ("align", "features", "targets", "dataset", "prepare"):
            print(getattr(daily_data, args.stage)(context, overwrite=args.overwrite))
        elif args.stage == "final-test":
            from tcc_crypto.workflows.final_evaluation import run

            print(
                json.dumps(
                    {
                        key: str(path)
                        for key, path in run(context, overwrite=args.overwrite).items()
                    },
                    indent=2,
                )
            )
        elif args.stage in ("pilot", "grid-search"):
            if args.eligibility_only:
                print(svm.assess(context, overwrite=args.overwrite))
            else:
                print(
                    json.dumps(
                        {
                            key: str(path)
                            for key, path in svm.run(
                                context, overwrite=args.overwrite
                            ).items()
                        },
                        indent=2,
                    )
                )
        else:
            if args.kind == "final-results":
                from tcc_crypto.workflows.final_evaluation import export
            else:
                export = (
                    daily_data.export_dataset
                    if args.kind == "dataset"
                    else svm.export_results
                )
            print(export(context, overwrite=args.overwrite))
    if args.all_symbols and (
        args.stage == "final-test"
        or (args.stage == "export" and args.kind == "final-results")
    ):
        from tcc_crypto.workflows.final_evaluation import summarize_universe

        print(
            json.dumps(
                {
                    key: str(path)
                    for key, path in summarize_universe(
                        contexts, overwrite=args.overwrite
                    ).items()
                },
                indent=2,
            )
        )


if __name__ == "__main__":
    main()
