"""Shared execution provenance and streaming file checksums."""

from __future__ import annotations

import platform
import subprocess
from datetime import datetime, timezone
from hashlib import sha256
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path


def file_sha256(path: Path) -> str:
    digest = sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _package_version(distribution: str) -> str | None:
    try:
        return version(distribution)
    except PackageNotFoundError:
        return None


def git_value(arguments: tuple[str, ...], root: Path | None = None) -> str | None:
    try:
        completed = subprocess.run(
            ["git", *arguments], cwd=root, check=False, capture_output=True, text=True
        )
    except OSError:
        return None
    return completed.stdout.strip() if completed.returncode == 0 else None


def _git_revision(root: Path | None = None) -> str | None:
    return git_value(("rev-parse", "HEAD"), root) or None


def _git_working_tree_dirty(root: Path | None = None) -> bool | None:
    value = git_value(("status", "--porcelain"), root)
    return None if value is None else bool(value)


def execution_metadata(root: Path) -> dict[str, object]:
    return {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "code_revision": _git_revision(root),
        "working_tree_dirty": _git_working_tree_dirty(root),
        "python_version": platform.python_version(),
        "package_versions": {
            name: _package_version(name)
            for name in (
                "pandas",
                "numpy",
                "scikit-learn",
                "feature-engine",
                "TA-Lib",
                "openpyxl",
            )
        },
        "random_behavior": False,
        "random_seed": None,
    }
