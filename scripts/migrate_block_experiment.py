"""Archive the previous protocol; default to a read-only inventory."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from pathlib import Path

ARCHIVE = Path("archive/pre_block_20261031")
MANIFEST = ARCHIVE / "migration.json"


def checksum(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def inventory(root: Path) -> list[dict]:
    """Freeze exact destinations before moving anything; ignore local caches."""
    entries = []
    for folder in (
        "src/tcc_crypto",
        "configs",
        "notebooks",
        "tests",
        "data/processed",
        "data/exploration",
        "outputs/binance",
        "outputs/migrations",
    ):
        for source in sorted((root / folder).rglob("*")):
            if not source.is_file() or any(
                part.startswith(".") or part == "__pycache__"
                for part in source.relative_to(root).parts
            ):
                continue
            relative = source.relative_to(root)
            if relative.as_posix() == "tests/test_okf_docs.py":
                continue
            if folder.startswith(("data/", "outputs/")):
                parts = relative.parts[:-1]
                context = next(
                    (
                        p
                        for p in parts
                        if p.startswith(("binance_", "hourly_", "btc_daily"))
                    ),
                    "exploration",
                )
                unique = hashlib.sha256(str(relative).encode()).hexdigest()[:16]
                destination = (
                    Path("outputs/archive") / context / f"{unique}_{source.name}"
                )
            else:
                destination = ARCHIVE / relative
            entries.append(
                {
                    "source": str(relative),
                    "destination": str(destination),
                    "size": source.stat().st_size,
                    "sha256": checksum(source),
                }
            )
    return entries


def migrate(
    root: Path, *, apply: bool = False, sources_only: bool = False
) -> list[dict]:
    manifest = root / MANIFEST
    entries = json.loads(manifest.read_text()) if manifest.exists() else inventory(root)
    destinations = [item["destination"] for item in entries]
    if len(set(destinations)) != len(destinations):
        raise ValueError("Migration destinations collide.")
    for item in entries:
        source, target = root / item["source"], root / item["destination"]
        if target.exists() and checksum(target) != item["sha256"]:
            raise ValueError(f"Conflicting destination: {target}")
        if not target.exists() and (
            not source.exists() or checksum(source) != item["sha256"]
        ):
            raise ValueError(f"Source changed or disappeared: {source}")
    if not apply:
        return entries
    manifest.parent.mkdir(parents=True, exist_ok=True)
    if not manifest.exists():
        manifest.write_text(json.dumps(entries, indent=2) + "\n")
    for item in entries:
        if sources_only and item["source"].startswith(("data/", "outputs/")):
            continue
        source, target = root / item["source"], root / item["destination"]
        if target.exists():
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(source, target)
        if checksum(target) != item["sha256"]:
            raise ValueError(f"Migration checksum failure: {target}")
        parent = source.parent
        while parent != root and not any(parent.iterdir()):
            parent.rmdir()
            parent = parent.parent
    return entries


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--sources-only", action="store_true")
    args = parser.parse_args()
    records = migrate(
        Path(__file__).resolve().parents[1],
        apply=args.apply,
        sources_only=args.sources_only,
    )
    print(f"Verified migration inventory: {len(records)} files; apply={args.apply}")
