"""Inventory historical research artifacts; move only with --apply."""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict
from pathlib import Path

from tcc_crypto.paths import MIGRATION_MANIFEST_DIR, repository_root
from tcc_crypto.reporting.migration import MIGRATION_NAME, apply_migration, inventory


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repository-root", type=Path)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args(argv)
    root = repository_root(args.repository_root)
    if args.apply:
        payload = apply_migration(root)
    else:
        journal = root / MIGRATION_MANIFEST_DIR / MIGRATION_NAME
        payload = (
            json.loads(journal.read_text())
            if journal.exists()
            else {
                "mode": "dry-run",
                "items": [asdict(item) for item in inventory(root)],
            }
        )
    print(json.dumps(payload, indent=2))


if __name__ == "__main__":
    main()
