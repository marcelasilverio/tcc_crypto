"""Explicit classification stages and independent portfolio execution."""

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
        "stage",
        choices=[
            "collect",
            "prepare",
            "dataset",
            "train",
            "results",
            "run",
            "portfolio",
        ],
    )
    parser.add_argument("--config", type=Path)
    parser.add_argument("--portfolio-config", type=Path)
    parser.add_argument(
        "--source-run-id",
        help="Saved classification run used by portfolio; defaults to the latest run.",
    )
    parser.add_argument("--run-id")
    parser.add_argument("--overwrite", action="store_true")
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--symbols", nargs="+")
    group.add_argument("--all-symbols", action="store_true")
    args = parser.parse_args(argv)
    if args.stage != "collect" and not args.run_id:
        parser.error("--run-id is required for derived stages.")
    if args.stage == "portfolio":
        if args.config or args.symbols or args.all_symbols:
            parser.error(
                "portfolio uses --portfolio-config and the saved training universe."
            )
        logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
        execute_portfolio(
            args.run_id,
            config_path=args.portfolio_config,
            overwrite=args.overwrite,
            source_run_id=args.source_run_id,
        )
        return
    if args.portfolio_config:
        parser.error("--portfolio-config applies only to portfolio.")
    if args.source_run_id is not None:
        parser.error("--source-run-id applies only to portfolio.")
    if not args.symbols and not args.all_symbols:
        parser.error("Choose --symbols or --all-symbols.")
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


def latest_training_execution(root: Path = ROOT) -> Paths:
    """Resolve the most recently recorded classification execution exactly once."""
    from tcc_crypto.paths import OUTPUTS

    candidates = []
    for directory in sorted((root / OUTPUTS).glob("daily_*")):
        if not directory.is_dir():
            continue
        paths = Paths(root, directory.name.removeprefix("daily_"))
        if not paths.execution.exists():
            raise ValueError(f"Missing execution timestamp: {directory}")
        timestamp = pd.Timestamp(
            json.loads(paths.execution.read_text())["execution_time_utc"]
        )
        if pd.isna(timestamp) or timestamp.tzinfo is None:
            raise ValueError(f"Invalid execution timestamp: {directory}")
        candidates.append((timestamp.tz_convert("UTC"), paths))
    if not candidates:
        raise FileNotFoundError(
            "No saved training execution; run the classification stages explicitly."
        )
    latest = max(t for t, _ in candidates)
    selected = [p for t, p in candidates if t == latest]
    if len(selected) != 1:
        raise ValueError("Latest training execution timestamp is ambiguous.")
    return selected[0]


def load_portfolio_inputs(paths: Paths, settings: dict) -> dict:
    """Read historical inputs under their saved classification configuration."""
    from tcc_crypto.config import validate_config

    if not paths.configuration.exists() or not paths.execution.exists():
        raise FileNotFoundError(
            "Missing saved classification configuration; run the prerequisite stages explicitly."
        )
    configuration_digest = results.file_sha256(paths.configuration)
    signature = json.loads(paths.configuration.read_text())
    if signature.get("run_id") != paths.run_id:
        raise ValueError("Saved training run ID mismatch.")
    saved = signature["configuration"]
    config = validate_config(Config(saved["experiment"], saved["grid"]))
    if (
        settings["targets"] != config.values["targets"]
        or settings["source"]["training_window_days"] not in config.values["windows"]
    ):
        raise ValueError(
            "Newest training execution is incompatible with the portfolio configuration."
        )
    symbols = [
        s
        for s in config.values["symbols"]
        if s not in config.values["excluded_symbols"]
    ]
    required_columns = {
        "features": {"feature_time_utc", "r1"},
        "targets": {
            "feature_time_utc",
            "target_time_utc",
            *[f"target_{q * 100:g}pct" for q in settings["targets"]],
        },
        "treated": {
            "date_utc",
            "open",
            "high",
            "low",
            "close",
            "is_imputed",
            "source_date_utc",
        },
        "predictions": {
            "symbol",
            "model",
            "role",
            "window_size",
            "target",
            "block_id",
            "feature_time_utc",
            "target_time_utc",
            "fit_time_utc",
            "prediction_time_utc",
            "predicted",
        },
    }
    tables, source_tables = {}, []
    checksums = {
        str(paths.configuration.resolve()): configuration_digest,
        str(paths.execution.resolve()): results.file_sha256(paths.execution),
    }
    for name in ("features", "targets", "treated", "predictions"):
        tables[name] = {}
        for symbol in symbols:
            path = (
                paths.audit(symbol, name)
                if name == "predictions"
                else paths.table(symbol, name)
            )
            for dependency in (path, metadata_path(path)):
                if not dependency.exists():
                    raise FileNotFoundError(
                        f"Missing saved {name} input {dependency}; run its prerequisite stage explicitly."
                    )
                checksums[str(dependency.resolve())] = results.file_sha256(dependency)
            tables[name][symbol] = results.read_table(
                path,
                context=signature,
                stage="train" if name == "predictions" else "dataset/prepare",
            )
            if not required_columns[name] <= set(tables[name][symbol]):
                raise ValueError(
                    f"Missing required {name} columns for {symbol}; inspect the saved prerequisite stage."
                )
            source_tables.append(path.resolve())
    # Validate saved table semantics separately from their persisted dtype schema.
    from tcc_crypto.portfolio import _dated

    for symbol in symbols:
        features = tables["features"][symbol]
        treated = tables["treated"][symbol]
        targets = tables["targets"][symbol]
        _dated(features, "feature_time_utc", symbol)
        _dated(treated, "date_utc", symbol)
        _dated(targets, "feature_time_utc", symbol)
        if not pd.api.types.is_numeric_dtype(features.r1):
            raise ValueError(f"R1 must be numeric: {symbol}")
        if (
            not pd.api.types.is_bool_dtype(treated.is_imputed)
            or treated.is_imputed.isna().any()
        ):
            raise ValueError(f"Invalid imputation markers: {symbol}")
        if (
            treated.source_date_utc.isna().any()
            or not treated.source_date_utc.le(treated.date_utc).all()
        ):
            raise ValueError(f"Invalid candle source dates: {symbol}")
        for column in ("open", "high", "low", "close"):
            if not pd.api.types.is_numeric_dtype(treated[column]):
                raise ValueError(f"{column} must be numeric: {symbol}")
        if not targets.target_time_utc.eq(
            targets.feature_time_utc + pd.Timedelta(days=1)
        ).all():
            raise ValueError(f"Invalid saved target alignment: {symbol}")
        predicted = tables["predictions"][symbol]
        if not predicted.empty and not predicted.symbol.eq(symbol).all():
            raise ValueError(f"Prediction symbol mismatch: {symbol}")
    source = {
        "run_id": paths.run_id,
        "context": signature,
        "execution_time_utc": json.loads(paths.execution.read_text())[
            "execution_time_utc"
        ],
        "symbols": symbols,
        "tables": [str(p) for p in source_tables],
        "checksums": checksums,
    }
    results.validate_portfolio_source(source)
    return {"source": source, "tables": tables, "symbols": symbols}


def execute_portfolio(
    run_id: str,
    *,
    config_path: Path | None = None,
    root: Path = ROOT,
    overwrite=False,
    source_run_id: str | None = None,
) -> Path:
    """Execute only saved-input portfolio allocation and backtesting."""
    from tcc_crypto import backtesting, portfolio
    from tcc_crypto.config import load_portfolio_config
    from tcc_crypto.paths import PORTFOLIO_CONFIG, PortfolioPaths

    settings = load_portfolio_config(config_path)
    portfolio.check_solver(settings["allocation"]["solver"])
    origin = (
        latest_training_execution(root)
        if source_run_id is None
        else Paths(root, source_run_id)
    )
    LOGGER.info(
        "Portfolio source: %s; model=%s; window=%s",
        origin.run_id,
        settings["source"]["model"],
        settings["source"]["training_window_days"],
    )
    inputs = load_portfolio_inputs(origin, settings)
    paths = PortfolioPaths(root, run_id)
    signature = {
        "run_id": run_id,
        "configuration": settings,
        "source_run_id": origin.run_id,
    }
    with results.portfolio_transaction(
        paths, signature, inputs["source"], overwrite=overwrite
    ) as directory:
        tables = inputs["tables"]
        # Only historical R1 and imputation flags cross the allocation boundary.
        allocations = portfolio.allocate_portfolios(
            pd.concat(tables["predictions"].values(), ignore_index=True)[
                [
                    "symbol",
                    "model",
                    "role",
                    "window_size",
                    "target",
                    "block_id",
                    "feature_time_utc",
                    "target_time_utc",
                    "fit_time_utc",
                    "prediction_time_utc",
                    "predicted",
                ]
            ],
            {s: f[["feature_time_utc", "r1"]] for s, f in tables["features"].items()},
            {s: f[["date_utc", "is_imputed"]] for s, f in tables["treated"].items()},
            inputs["symbols"],
            settings,
        )
        evaluated = backtesting.simulate_capital(
            allocations.weights, tables["treated"], tables["targets"], settings
        )
        execution = results.execution_metadata(root)
        from importlib.metadata import version

        execution["package_versions"].update(
            {name: version(name) for name in ("PyPortfolioOpt", "cvxpy", "clarabel")}
        )
        execution.update(
            {
                "solver": settings["allocation"]["solver"],
                "random_generator": "PCG64",
                "source_selection": "latest" if source_run_id is None else "explicit",
                "source_run_id": origin.run_id,
                "symbols": inputs["symbols"],
                "operation_start": str(evaluated.capital.operation_date.min()),
                "operation_end": str(evaluated.capital.operation_date.max()),
                "output_path": str(paths.output.resolve()),
                "config_path": str(Path(config_path).resolve())
                if config_path
                else str((ROOT / PORTFOLIO_CONFIG).resolve()),
            }
        )
        results.publish_portfolio(
            paths,
            directory,
            signature,
            inputs["source"],
            {
                "capital": evaluated.capital,
                "signals": allocations.signals,
                "operations": evaluated.operations,
            },
            execution,
        )
    LOGGER.info("Portfolio saved: %s", paths.output)
    return paths.output


def load_portfolio_report(run_id: str, *, root: Path = ROOT) -> dict:
    """Load a committed portfolio and verify both portfolio and source provenance."""
    from tcc_crypto.config import validate_portfolio_config
    from tcc_crypto.paths import PORTFOLIO_TABLES, PortfolioPaths

    paths = PortfolioPaths(root, run_id)
    if paths.lock.exists():
        raise ValueError(
            "Portfolio result is locked by an active or interrupted execution."
        )
    generation_digest = (
        results.file_sha256(paths.artifact("complete"))
        if paths.artifact("complete").exists()
        else None
    )
    signature = results.validate_portfolio_bundle(paths)
    validate_portfolio_config(signature["configuration"])
    if signature["run_id"] != run_id:
        raise ValueError("Portfolio run ID mismatch.")
    source = json.loads(paths.artifact("source").read_text())
    if source["run_id"] != signature["source_run_id"]:
        raise ValueError("Portfolio source run ID mismatch.")
    results.validate_portfolio_source(source)
    tables = {
        name: results.read_table(
            paths.artifact(name), context=signature, stage="portfolio"
        )
        for name in PORTFOLIO_TABLES
    }
    if (
        paths.lock.exists()
        or results.file_sha256(paths.artifact("complete")) != generation_digest
    ):
        raise ValueError(
            "Portfolio changed while loading; retry after execution completes."
        )
    return {
        "run_id": run_id,
        "source": source,
        "configuration": signature["configuration"],
        "execution": json.loads(paths.artifact("execution").read_text()),
        "tables": tables,
    }


if __name__ == "__main__":
    main()
