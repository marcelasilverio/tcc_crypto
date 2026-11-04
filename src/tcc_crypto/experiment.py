"""One entrypoint: collect -> prepare -> dataset -> train -> results."""

import argparse
import json
import logging
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pandas as pd

from tcc_crypto import collection, dataset, preparation, results, training
from tcc_crypto.config import Config, load_config, select_symbols
from tcc_crypto.paths import MAIN_TABLES, ROOT, Paths, metadata_path, raw_paths

LOGGER = logging.getLogger(__name__)
AUDIT_NAMES = (
    "predictions",
    "metrics",
    "selection",
    "correlations",
    "scaling",
    "blocks",
    "folds",
    "candidates",
    "fold_scores",
    "winners",
    "failures",
)


def context(config: Config, run_id: str) -> dict:
    return {"run_id": run_id, "configuration": config.signature}


def open_execution(config: Config, paths: Paths) -> dict:
    """Bind an execution ID to one immutable effective configuration."""
    signature = context(config, paths.run_id)
    snapshot = paths.configuration
    if snapshot.exists():
        if json.loads(snapshot.read_text()) != signature:
            raise ValueError(
                "Run ID belongs to another configuration; choose a new run ID."
            )
    else:
        results.write_json(snapshot, signature)
    if not paths.execution.exists():
        results.write_json(paths.execution, results.execution_metadata(paths.root))
    return signature


def collect(config: Config, symbols: list[str], *, root: Path = ROOT) -> list[Path]:
    def one(symbol):
        LOGGER.info("Collect: %s", symbol)
        return collection.collect_symbol(symbol, config.values["collection"], root)

    with ThreadPoolExecutor(
        max_workers=config.values["collection"]["max_workers"]
    ) as pool:
        return list(pool.map(one, symbols))


def _save_tables(tables: dict, destinations: dict, signature: dict, sources, overwrite):
    results.ensure_writable(
        [p for dest in destinations.values() for p in (dest, metadata_path(dest))],
        overwrite=overwrite,
    )
    for name, frame in tables.items():
        results.write_table(
            frame,
            destinations[name],
            context=signature,
            sources=sources,
            overwrite=overwrite,
        )


def prepare(
    config: Config, symbols: list[str], paths: Paths, *, overwrite=False
) -> None:
    signature = open_execution(config, paths)
    for symbol in symbols:
        LOGGER.info("Validate and treat: %s", symbol)
        collected = raw_paths(paths.root, symbol, config.values["collection"])
        source = collected["raw"]
        if not source.exists():
            raise FileNotFoundError(
                f"Missing raw data for {symbol}; run 'collect' first."
            )
        collection.validate_raw(collected, symbol, config.values["collection"])
        raw = pd.read_csv(source, dtype=str, keep_default_na=False)
        try:
            prepared = preparation.prepare_symbol(raw, symbol, config.values["study"])
        except ValueError as error:
            results.write_table(
                pd.DataFrame(
                    [
                        {
                            "symbol": symbol,
                            "status": "structural_error",
                            "error": str(error),
                        }
                    ]
                ),
                paths.audit(symbol, "preparation_error"),
                context=signature,
                sources=[source],
                overwrite=overwrite,
            )
            raise
        tables = {
            "treated": prepared.treated,
            "availability": prepared.availability,
            "treatment": prepared.treatment,
            "quality": prepared.diagnostics,
        }
        destinations = {
            name: paths.table(symbol, name)
            if name == "treated"
            else paths.audit(symbol, name)
            for name in tables
        }
        _save_tables(
            tables, destinations, signature, [source, collected["metadata"]], overwrite
        )
    consolidate(config, paths, quality=True, model=False, overwrite=overwrite)


def build_datasets(
    config: Config, symbols: list[str], paths: Paths, *, overwrite=False
) -> None:
    signature = open_execution(config, paths)
    for symbol in symbols:
        LOGGER.info("Build dataset: %s", symbol)
        source = paths.table(symbol, "treated")
        treated = results.read_table(source, context=signature, stage="prepare")
        tables = dataset.build_dataset(treated, config.values)
        _save_tables(
            vars(tables),
            {name: paths.table(symbol, name) for name in vars(tables)},
            signature,
            [source, metadata_path(source)],
            overwrite,
        )


def train(config: Config, symbols: list[str], paths: Paths, *, overwrite=False) -> None:
    signature = open_execution(config, paths)
    for symbol in symbols:
        LOGGER.info("Train and evaluate: %s", symbol)
        source = paths.table(symbol, "dataset")
        values = results.read_table(source, context=signature, stage="dataset")
        destinations = {name: paths.audit(symbol, name) for name in AUDIT_NAMES}
        results.ensure_writable(
            [p for d in destinations.values() for p in (d, metadata_path(d))],
            overwrite=overwrite,
        )
        calculated = training.train_symbol(values, symbol, config.values, config.grid)
        _save_tables(
            calculated,
            destinations,
            signature,
            [source, metadata_path(source)],
            overwrite,
        )
    consolidate(config, paths, quality=False, model=True, overwrite=overwrite)


def consolidate(
    config: Config, paths: Paths, *, quality=True, model=True, overwrite=False
) -> None:
    """Read saved evidence only; never prepare data or fit an estimator."""
    signature = open_execution(config, paths)

    names = ([] if not quality else ["availability", "treatment"]) + (
        []
        if not model
        else [
            "metrics",
            "feature_selection",
            "predictions_in_sample",
            "actuals_in_sample",
            "predictions_out_of_sample",
            "actuals_out_of_sample",
        ]
    )
    results.ensure_writable(
        [
            p
            for name in names
            for p in (paths.main(name), metadata_path(paths.main(name)))
        ],
        overwrite=overwrite,
    )

    def combine(name):
        frames = []
        sources = []
        for symbol in config.values["symbols"]:
            path = paths.audit(symbol, name)
            if not path.exists():
                continue
            frame = results.read_table(
                path,
                context=signature,
                stage="prepare" if name in ("availability", "treatment") else "train",
            )
            sources.extend([path, metadata_path(path)])
            if not frame.empty:
                frames.append(frame)
        return (
            pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()
        ), sources

    if quality:
        available, sources = combine("availability")
        if available.empty:
            raise FileNotFoundError("No availability evidence; run 'prepare' first.")
        # Unprocessed assets remain nullable; absence is only inferred after raw inspection.
        matrix = (
            available.pivot(index="date_utc", columns="symbol", values="available")
            .reindex(columns=config.values["symbols"])
            .astype("Int64")
        )
        matrix.columns.name = None
        results.write_table(
            matrix.reset_index(),
            paths.main("availability"),
            context=signature,
            sources=sources,
            overwrite=overwrite,
        )
        treated, sources = combine("treatment")
        results.write_table(
            treated,
            paths.main("treatment"),
            context=signature,
            sources=sources,
            overwrite=overwrite,
        )
    if model:
        # Read one asset's long audit at a time; retain only compact matrix columns.
        sources = []
        matrices = {
            ("actuals_" if actual else "predictions_") + role: []
            for role in ("in_sample", "out_of_sample")
            for actual in (False, True)
        }
        keys = ["feature_time_utc", "target", "window_size"]
        for symbol in config.values["symbols"]:
            path = paths.audit(symbol, "predictions")
            if not path.exists():
                continue
            predictions = results.read_table(path, context=signature, stage="train")
            sources.extend([path, metadata_path(path)])
            for role in ("in_sample", "out_of_sample"):
                for actual in (False, True):
                    name = ("actuals_" if actual else "predictions_") + role
                    matrix = results.binary_matrix(
                        predictions, [symbol], role, actual=actual
                    )
                    matrices[name].append(matrix.set_index(keys))
        if not sources:
            raise FileNotFoundError("No saved predictions; run 'train' first.")
        for name, columns in matrices.items():
            matrix = (
                pd.concat(columns, axis=1)
                .reindex(columns=config.values["symbols"])
                .astype("Int64")
                .sort_index()
                .reset_index()
            )
            results.write_table(
                matrix,
                paths.main(name),
                context=signature,
                sources=sources,
                overwrite=overwrite,
            )
        for name, source_name in [
            ("metrics", "metrics"),
            ("feature_selection", "selection"),
        ]:
            frame, sources = combine(source_name)
            if name == "feature_selection" and not frame.empty:
                frame = frame.loc[frame.fit_scope == "full_in_sample"].reset_index(
                    drop=True
                )
            results.write_table(
                frame,
                paths.main(name),
                context=signature,
                sources=sources,
                overwrite=overwrite,
            )


def run(config: Config, symbols: list[str], paths: Paths, *, overwrite=False) -> None:
    collect(config, symbols, root=paths.root)
    prepare(config, symbols, paths, overwrite=overwrite)
    build_datasets(config, symbols, paths, overwrite=overwrite)
    train(config, symbols, paths, overwrite=overwrite)


def inspect(
    config: Config, paths: Paths, symbol: str, table: str, *, rows=10
) -> pd.DataFrame:
    """Inspect saved notebook inputs/results without recomputation."""
    if table in ("treated", "features", "targets", "dataset"):
        path = paths.table(symbol, table)
    else:
        path = paths.audit(symbol, table)
    return results.preview(
        results.read_table(path, context=context(config, paths.run_id), stage=table),
        rows,
    )


def inspect_windows(config: Config, paths: Paths, symbol: str) -> pd.DataFrame:
    """Show saved-dataset temporal boundaries without running training."""
    values = results.read_table(
        paths.table(symbol, "dataset"),
        context=context(config, paths.run_id),
        stage="dataset",
    )
    return training.describe_windows(values, config.values)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "stage", choices=["collect", "prepare", "dataset", "train", "results", "run"]
    )
    parser.add_argument("--config", type=Path)
    parser.add_argument("--run-id")
    parser.add_argument("--overwrite", action="store_true")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--symbols", nargs="+")
    group.add_argument("--all-symbols", action="store_true")
    args = parser.parse_args(argv)
    if args.stage != "collect" and not args.run_id:
        parser.error("--run-id is required for derived stages.")
    config = load_config(args.config)
    symbols = select_symbols(config, args.symbols, all_symbols=args.all_symbols)
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    if args.stage == "collect":
        collect(config, symbols)
    else:
        paths = Paths(ROOT, args.run_id)
        if args.stage == "results":
            # Explicitly requested symbols must have saved upstream model evidence.
            for symbol in symbols:
                results.read_table(
                    paths.audit(symbol, "predictions"),
                    context=context(config, args.run_id),
                    stage="train",
                )
            consolidate(config, paths, overwrite=args.overwrite)
        else:
            {"prepare": prepare, "dataset": build_datasets, "train": train, "run": run}[
                args.stage
            ](config, symbols, paths, overwrite=args.overwrite)


def load_report(paths: Paths) -> dict:
    """Load an explicit saved run and validate provenance, without creating files.

    Use its historical configuration, not the possibly changed current JSONs.
    Missing/incompatible artifacts fail with the prerequisite stage named.
    """
    if not paths.configuration.exists() or not paths.execution.exists():
        raise FileNotFoundError(
            "Missing saved execution; run the explicit preparation/training stages first."
        )
    signature = json.loads(paths.configuration.read_text())
    if signature.get("run_id") != paths.run_id:
        raise ValueError("Saved run ID does not match the requested run.")
    return {
        "run_id": paths.run_id,
        "configuration": signature["configuration"],
        "execution": json.loads(paths.execution.read_text()),
        "tables": {
            name: results.read_table(
                paths.main(name), context=signature, stage="results"
            )
            for name in MAIN_TABLES
        },
    }


if __name__ == "__main__":
    main()
