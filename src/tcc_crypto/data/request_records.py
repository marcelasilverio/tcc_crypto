"""Read saved per-symbol responses lazily instead of retaining all daily histories."""

from __future__ import annotations

import json
from collections.abc import Sequence
from pathlib import Path

from tcc_crypto.reporting.provenance import file_sha256


class SavedRecords(Sequence):
    def __init__(self, records: list[dict]):
        self.records = records

    def __len__(self) -> int:
        return len(self.records)

    def __getitem__(self, position):
        record = self.records[position]
        if "record_path" not in record:
            return record
        path = Path(record["record_path"])
        if file_sha256(path) != record["sha256"]:
            raise ValueError(f"Modified symbol response: {path}")
        return json.loads(path.read_text())
