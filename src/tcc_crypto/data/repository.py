"""Data: repository."""

from __future__ import annotations

from pathlib import Path


def find_repository_root(start: Path | None = None) -> Path:
    """Find the repository root by looking for AGENTS.md and pyproject.toml."""
    current = (start or Path.cwd()).resolve()
    for candidate in (current, *current.parents):
        if (candidate / "AGENTS.md").exists() and (
            candidate / "pyproject.toml"
        ).exists():
            return candidate
    raise FileNotFoundError("Could not locate the repository root.")
