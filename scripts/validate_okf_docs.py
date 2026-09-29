"""Validate the repository's local Open Knowledge Format documentation profile."""

from __future__ import annotations

import argparse
from datetime import datetime
from pathlib import Path
import re
import sys
from typing import Any
from urllib.parse import unquote

import yaml


ALLOWED_AUTHORITIES = {
    "approved-methodology",
    "external-reference",
    "generated-evidence",
    "navigation",
    "research-context",
}
ALLOWED_STATUSES = {"draft", "stable", "deprecated"}
ALLOWED_TYPES = {
    "Data Quality Report",
    "External Methodology Reference",
    "Methodology Decision",
    "Redirect",
    "Research Context",
}
REQUIRED_FIELDS = {
    "type",
    "title",
    "description",
    "tags",
    "status",
    "authority",
    "generated",
}
ACTOR_PATTERN = re.compile(
    r"^(?:(?:human|process):[a-z0-9][a-z0-9.-]*|[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+)$"
)
MARKDOWN_LINK_PATTERN = re.compile(r"\[([^\]]+)\]\(([^)]+)\)")
INDEX_ENTRY_PATTERN = re.compile(
    r"^\s*(?:[-*]|\d+\.)\s+\[([^\]]+)\]\(([^)]+)\)\s+-\s+(.+?)\s*$"
)


class ValidationError(Exception):
    """Raised when an OKF bundle violates the repository profile."""


def _parse_frontmatter(path: Path) -> tuple[dict[str, Any], str]:
    text = path.read_text(encoding="utf-8")
    lines = text.splitlines(keepends=True)
    if not lines or lines[0].strip() != "---":
        raise ValidationError(f"{path}: missing YAML frontmatter")

    closing_index = next(
        (index for index, line in enumerate(lines[1:], start=1) if line.strip() == "---"),
        None,
    )
    if closing_index is None:
        raise ValidationError(f"{path}: unclosed YAML frontmatter")

    yaml_text = "".join(lines[1:closing_index])
    try:
        metadata = yaml.safe_load(yaml_text)
    except yaml.YAMLError as error:
        raise ValidationError(f"{path}: invalid YAML frontmatter: {error}") from error
    if not isinstance(metadata, dict):
        raise ValidationError(f"{path}: frontmatter must be a mapping")
    return metadata, "".join(lines[closing_index + 1 :])


def _validate_timestamp(value: Any, location: str, errors: list[str]) -> None:
    if not isinstance(value, str):
        errors.append(f"{location}: timestamp must be a quoted ISO 8601 string")
        return
    normalized = value[:-1] + "+00:00" if value.endswith("Z") else value
    try:
        timestamp = datetime.fromisoformat(normalized)
    except ValueError:
        errors.append(f"{location}: invalid ISO 8601 timestamp {value!r}")
        return
    if timestamp.tzinfo is None or timestamp.utcoffset() is None:
        errors.append(f"{location}: timestamp must include an explicit UTC offset")


def _validate_actor(value: Any, location: str, errors: list[str]) -> None:
    if not isinstance(value, str) or not ACTOR_PATTERN.fullmatch(value):
        errors.append(f"{location}: invalid OKF actor {value!r}")


def _validate_event(value: Any, location: str, errors: list[str]) -> None:
    if not isinstance(value, dict):
        errors.append(f"{location}: event must be a mapping")
        return
    if "by" not in value or "at" not in value:
        errors.append(f"{location}: event requires by and at")
        return
    _validate_actor(value["by"], f"{location}.by", errors)
    _validate_timestamp(value["at"], f"{location}.at", errors)


def _local_link_target(path: Path, target: str, bundle_root: Path) -> Path | None:
    target = target.strip()
    if not target or target.startswith(("#", "http://", "https://", "mailto:")):
        return None
    target = unquote(target.split("#", 1)[0].split("?", 1)[0])
    if not target:
        return None
    if target.startswith("/"):
        return bundle_root / target.lstrip("/")
    return path.parent / target


def _validate_markdown_links(
    path: Path,
    body: str,
    bundle_root: Path,
    errors: list[str],
) -> None:
    for _, target in MARKDOWN_LINK_PATTERN.findall(body):
        destination = _local_link_target(path, target, bundle_root)
        if destination is not None and not destination.resolve().exists():
            errors.append(f"{path}: broken internal link {target!r}")


def _validate_concept(
    path: Path,
    bundle_root: Path,
    errors: list[str],
) -> tuple[dict[str, Any], str] | None:
    try:
        metadata, body = _parse_frontmatter(path)
    except ValidationError as error:
        errors.append(str(error))
        return None

    missing = sorted(field for field in REQUIRED_FIELDS if not metadata.get(field))
    if missing:
        errors.append(f"{path}: missing required fields: {', '.join(missing)}")

    if metadata.get("type") not in ALLOWED_TYPES:
        errors.append(f"{path}: unknown type {metadata.get('type')!r}")
    if metadata.get("status") not in ALLOWED_STATUSES:
        errors.append(f"{path}: invalid status {metadata.get('status')!r}")
    if metadata.get("authority") not in ALLOWED_AUTHORITIES:
        errors.append(f"{path}: invalid authority {metadata.get('authority')!r}")
    if not isinstance(metadata.get("tags"), list) or not metadata.get("tags"):
        errors.append(f"{path}: tags must be a non-empty list")

    if "generated" in metadata:
        _validate_event(metadata["generated"], f"{path}: generated", errors)

    verified = metadata.get("verified")
    if metadata.get("status") == "stable" and metadata.get("authority") != "navigation":
        if not verified:
            errors.append(f"{path}: stable non-navigation concepts require verified")
    if verified:
        events = verified if isinstance(verified, list) else [verified]
        for index, event in enumerate(events):
            _validate_event(event, f"{path}: verified[{index}]", errors)

    sources = metadata.get("sources", [])
    if sources and not isinstance(sources, list):
        errors.append(f"{path}: sources must be a list")
    elif isinstance(sources, list):
        source_ids: set[str] = set()
        for index, source in enumerate(sources):
            if not isinstance(source, dict):
                errors.append(f"{path}: sources[{index}] requires resource")
                continue
            resource = source.get("resource")
            if not isinstance(resource, str) or not resource.strip():
                errors.append(f"{path}: sources[{index}] requires resource as a non-empty string")
            source_id = source.get("id")
            if source_id is not None and not isinstance(source_id, str):
                errors.append(f"{path}: sources[{index}].id must be a string")
            elif source_id:
                if source_id in source_ids:
                    errors.append(f"{path}: duplicate source id {source_id!r}")
                source_ids.add(source_id)
            if source.get("author") is not None:
                _validate_actor(source["author"], f"{path}: sources[{index}].author", errors)
            if source.get("last_modified") is not None:
                _validate_timestamp(
                    source["last_modified"],
                    f"{path}: sources[{index}].last_modified",
                    errors,
                )

    if metadata.get("as_of") is not None:
        _validate_timestamp(metadata["as_of"], f"{path}: as_of", errors)
    if metadata.get("stale_after") is not None:
        _validate_timestamp(metadata["stale_after"], f"{path}: stale_after", errors)

    if metadata.get("type") == "Methodology Decision":
        if metadata.get("authority") != "approved-methodology":
            errors.append(f"{path}: methodology decisions require approved-methodology authority")
        if metadata.get("decision_status") != "approved":
            errors.append(f"{path}: methodology decisions require decision_status: approved")

    if metadata.get("type") == "Redirect":
        redirect_to = metadata.get("redirect_to")
        if not isinstance(redirect_to, str) or not redirect_to:
            errors.append(f"{path}: redirects require redirect_to")
        else:
            destination = (path.parent / redirect_to).resolve()
            if not destination.exists():
                errors.append(f"{path}: redirect target does not exist: {redirect_to}")
        if metadata.get("status") != "deprecated":
            errors.append(f"{path}: redirects must use status: deprecated")
        if metadata.get("authority") != "navigation":
            errors.append(f"{path}: redirects require navigation authority")
    elif metadata.get("status") == "deprecated":
        errors.append(f"{path}: only redirects may use status: deprecated")

    _validate_markdown_links(path, body, bundle_root, errors)

    return metadata, body


def _validate_index(path: Path, bundle_root: Path, errors: list[str]) -> None:
    text = path.read_text(encoding="utf-8")
    body = text
    if path == bundle_root / "index.md":
        try:
            metadata, body = _parse_frontmatter(path)
        except ValidationError as error:
            errors.append(str(error))
            return
        if metadata != {"okf_version": "0.2"}:
            errors.append(f"{path}: root index frontmatter must contain only okf_version: '0.2'")
    elif text.startswith("---\n"):
        errors.append(f"{path}: non-root index files must not contain frontmatter")

    entries: list[tuple[str, str, str]] = []
    for line in body.splitlines():
        match = INDEX_ENTRY_PATTERN.match(line)
        if match:
            entries.append(match.groups())

    entry_targets = [target for _, target, _ in entries]
    expected_files = [
        child
        for child in path.parent.glob("*.md")
        if child.name not in {"index.md", "log.md"}
    ]
    expected_directories = [
        child
        for child in path.parent.iterdir()
        if child.is_dir() and any(child.rglob("*.md"))
    ]

    for expected in sorted(expected_files + expected_directories):
        matching_entries = []
        for title, target, description in entries:
            destination = _local_link_target(path, target, bundle_root)
            if destination is not None and destination.resolve() == expected.resolve():
                matching_entries.append((title, target, description))
        if len(matching_entries) != 1:
            errors.append(
                f"{path}: expected exactly one index entry for {expected.name}, "
                f"found {len(matching_entries)}"
            )
            continue
        if expected.is_file():
            try:
                metadata, _ = _parse_frontmatter(expected)
            except ValidationError:
                continue
            title, _, description = matching_entries[0]
            if title != metadata.get("title"):
                errors.append(f"{path}: index title for {expected.name} does not match frontmatter")
            if description != metadata.get("description"):
                errors.append(
                    f"{path}: index description for {expected.name} does not match frontmatter"
                )

    for target in entry_targets:
        destination = _local_link_target(path, target, bundle_root)
        if destination is not None and not destination.resolve().exists():
            errors.append(f"{path}: broken index link {target!r}")

    _validate_markdown_links(path, body, bundle_root, errors)


def _validate_log(path: Path, bundle_root: Path, errors: list[str]) -> None:
    text = path.read_text(encoding="utf-8")
    if text.startswith("---\n"):
        errors.append(f"{path}: log.md must not contain frontmatter")

    date_headings: list[str] = []
    for line in text.splitlines():
        if not line.startswith("## "):
            continue
        value = line.removeprefix("## ").strip()
        try:
            datetime.strptime(value, "%Y-%m-%d")
        except ValueError:
            errors.append(f"{path}: invalid log date heading {value!r}")
            continue
        date_headings.append(value)
    if not date_headings:
        errors.append(f"{path}: log.md requires at least one ISO 8601 date heading")
    elif date_headings != sorted(date_headings, reverse=True):
        errors.append(f"{path}: log date headings must be newest first")

    _validate_markdown_links(path, text, bundle_root, errors)


def validate_bundle(bundle_root: Path) -> list[str]:
    """Return validation errors for an OKF bundle using the repository profile."""

    bundle_root = bundle_root.resolve()
    errors: list[str] = []
    root_index = bundle_root / "index.md"
    if not root_index.exists():
        return [f"{bundle_root}: missing root index.md"]

    metadata_by_path: dict[Path, dict[str, Any]] = {}
    bodies_by_path: dict[Path, str] = {}

    for path in sorted(bundle_root.rglob("*.md")):
        if path.name == "index.md":
            _validate_index(path, bundle_root, errors)
            continue
        if path.name == "log.md":
            _validate_log(path, bundle_root, errors)
            continue
        result = _validate_concept(path, bundle_root, errors)
        if result:
            metadata_by_path[path.resolve()], bodies_by_path[path.resolve()] = result

    deprecated_paths = {
        path for path, metadata in metadata_by_path.items() if metadata.get("status") == "deprecated"
    }
    for path, body in bodies_by_path.items():
        if path in deprecated_paths:
            continue
        for _, target in MARKDOWN_LINK_PATTERN.findall(body):
            destination = _local_link_target(path, target, bundle_root)
            if destination is not None and destination.resolve() in deprecated_paths:
                errors.append(f"{path}: active document links to deprecated path {target!r}")

    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("bundle", nargs="?", default="docs", type=Path)
    args = parser.parse_args()

    errors = validate_bundle(args.bundle)
    if errors:
        for error in errors:
            print(error, file=sys.stderr)
        return 1
    print(f"OKF validation passed: {args.bundle}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
