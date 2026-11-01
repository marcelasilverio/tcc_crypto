"""Network-free collection tests."""

import pandas as pd
import pytest

from tcc_crypto.collection import collect_symbol
from tcc_crypto.config import load_config
from tcc_crypto.paths import raw_paths
from tcc_crypto.results import file_sha256


def test_collection_resume_and_exhausted_history(tmp_path):
    settings = load_config().values["collection"].copy()
    settings.update(
        start_time_utc="2020-01-01T00:00:00Z",
        end_time_utc="2020-01-05T23:59:59.999Z",
        limit=2,
    )
    start = int(pd.Timestamp(settings["start_time_utc"]).timestamp() * 1000)
    row = [start, "1", "2", "1", "2", "1", start + 86400000 - 1, "2", 1, "0", "0", "0"]
    calls = []

    def broken(p):
        calls.append(p)
        if len(calls) == 1:
            return [row]
        raise RuntimeError("network interruption")

    with pytest.raises(RuntimeError):
        collect_symbol("BTCUSDT", settings, tmp_path, requester=broken)
    seen = []

    def resumed(p):
        seen.append(p)
        return []

    path = collect_symbol("BTCUSDT", settings, tmp_path, requester=resumed)
    assert seen[0]["startTime"] == start + 1
    assert len(pd.read_csv(path)) == 1
    digest = file_sha256(path)
    collect_symbol(
        "BTCUSDT", settings, tmp_path, requester=lambda p: pytest.fail("Raw exists")
    )
    assert file_sha256(path) == digest
    assert not list(tmp_path.rglob("*.xlsx"))


def test_malformed_response_is_not_completion(tmp_path):
    settings = load_config().values["collection"]
    with pytest.raises(ValueError, match="Malformed"):
        collect_symbol(
            "BTCUSDT", settings, tmp_path, requester=lambda p: {"error": "bad"}
        )
    assert not raw_paths(tmp_path, "BTCUSDT", settings)["raw"].exists()


def test_incomplete_numeric_fields_are_preserved_for_preparation(tmp_path):
    settings = load_config().values["collection"]
    start = int(pd.Timestamp(settings["start_time_utc"]).timestamp() * 1000)
    pages = iter([[[start, "bad-price"]], []])
    path = collect_symbol(
        "BTCUSDT", settings, tmp_path, requester=lambda p: next(pages)
    )
    frame = pd.read_csv(path)
    assert frame.open.iloc[0] == "bad-price"
    assert pd.isna(frame.high.iloc[0])


def test_http_retry_preserves_failure_diagnostic(monkeypatch):
    from urllib.error import URLError

    from tcc_crypto import collection

    calls = []

    def fail(*args, **kwargs):
        calls.append(1)
        raise URLError("simulated failure")

    monkeypatch.setattr(collection, "urlopen", fail)
    monkeypatch.setattr(collection.time, "sleep", lambda seconds: None)
    with pytest.raises(RuntimeError, match="simulated failure"):
        collection.request_json(
            "https://example.invalid", {}, timeout_seconds=1, max_retries=2
        )
    assert len(calls) == 3
