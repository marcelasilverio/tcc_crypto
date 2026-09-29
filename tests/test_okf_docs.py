from __future__ import annotations

import importlib.util
from pathlib import Path
import tempfile
import unittest


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
VALIDATOR_PATH = REPOSITORY_ROOT / "scripts" / "validate_okf_docs.py"
SPEC = importlib.util.spec_from_file_location("validate_okf_docs", VALIDATOR_PATH)
assert SPEC and SPEC.loader
VALIDATOR = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(VALIDATOR)


VALID_FRONTMATTER = """---
type: Research Context
title: Example
description: Example description.
tags: [example]
status: stable
authority: research-context
generated: { by: "process:test", at: "2026-09-29T10:16:31Z" }
verified: { by: "human:reviewer", at: "2026-09-29T10:16:31Z" }
---

# Example
"""


class OkfDocumentationTest(unittest.TestCase):
    def _bundle(self) -> tuple[tempfile.TemporaryDirectory[str], Path]:
        temporary_directory = tempfile.TemporaryDirectory()
        root = Path(temporary_directory.name)
        (root / "index.md").write_text(
            "---\nokf_version: \"0.2\"\n---\n\n# Index\n\n"
            "- [Example](example.md) - Example description.\n",
            encoding="utf-8",
        )
        (root / "example.md").write_text(VALID_FRONTMATTER, encoding="utf-8")
        return temporary_directory, root

    def test_repository_documentation_bundle_is_valid(self) -> None:
        self.assertEqual(VALIDATOR.validate_bundle(REPOSITORY_ROOT / "docs"), [])

    def test_valid_minimal_bundle(self) -> None:
        temporary_directory, root = self._bundle()
        self.addCleanup(temporary_directory.cleanup)
        self.assertEqual(VALIDATOR.validate_bundle(root), [])

    def test_invalid_yaml_is_rejected(self) -> None:
        temporary_directory, root = self._bundle()
        self.addCleanup(temporary_directory.cleanup)
        (root / "example.md").write_text("---\ntype: [broken\n---\n", encoding="utf-8")
        self.assertTrue(any("invalid YAML" in error for error in VALIDATOR.validate_bundle(root)))

    def test_missing_type_is_rejected(self) -> None:
        temporary_directory, root = self._bundle()
        self.addCleanup(temporary_directory.cleanup)
        content = VALID_FRONTMATTER.replace("type: Research Context\n", "")
        (root / "example.md").write_text(content, encoding="utf-8")
        self.assertTrue(any("missing required fields: type" in error for error in VALIDATOR.validate_bundle(root)))

    def test_timestamp_without_timezone_is_rejected(self) -> None:
        temporary_directory, root = self._bundle()
        self.addCleanup(temporary_directory.cleanup)
        content = VALID_FRONTMATTER.replace("2026-09-29T10:16:31Z", "2026-09-29T10:16:31", 1)
        (root / "example.md").write_text(content, encoding="utf-8")
        self.assertTrue(any("explicit UTC offset" in error for error in VALIDATOR.validate_bundle(root)))

    def test_invalid_actor_is_rejected(self) -> None:
        temporary_directory, root = self._bundle()
        self.addCleanup(temporary_directory.cleanup)
        content = VALID_FRONTMATTER.replace("process:test", "unknown actor")
        (root / "example.md").write_text(content, encoding="utf-8")
        self.assertTrue(any("invalid OKF actor" in error for error in VALIDATOR.validate_bundle(root)))

    def test_incomplete_index_is_rejected(self) -> None:
        temporary_directory, root = self._bundle()
        self.addCleanup(temporary_directory.cleanup)
        (root / "index.md").write_text(
            "---\nokf_version: \"0.2\"\n---\n\n# Index\n",
            encoding="utf-8",
        )
        self.assertTrue(any("expected exactly one index entry" in error for error in VALIDATOR.validate_bundle(root)))

    def test_broken_internal_link_is_rejected(self) -> None:
        temporary_directory, root = self._bundle()
        self.addCleanup(temporary_directory.cleanup)
        with (root / "example.md").open("a", encoding="utf-8") as handle:
            handle.write("\n[Missing](missing.md)\n")
        self.assertTrue(any("broken internal link" in error for error in VALIDATOR.validate_bundle(root)))

    def test_source_without_resource_is_rejected(self) -> None:
        temporary_directory, root = self._bundle()
        self.addCleanup(temporary_directory.cleanup)
        content = VALID_FRONTMATTER.replace(
            "verified: { by: \"human:reviewer\", at: \"2026-09-29T10:16:31Z\" }\n",
            "verified: { by: \"human:reviewer\", at: \"2026-09-29T10:16:31Z\" }\n"
            "sources:\n  - id: missing-resource\n",
        )
        (root / "example.md").write_text(content, encoding="utf-8")
        self.assertTrue(any("requires resource" in error for error in VALIDATOR.validate_bundle(root)))

    def test_duplicate_source_id_is_rejected(self) -> None:
        temporary_directory, root = self._bundle()
        self.addCleanup(temporary_directory.cleanup)
        content = VALID_FRONTMATTER.replace(
            "verified: { by: \"human:reviewer\", at: \"2026-09-29T10:16:31Z\" }\n",
            "verified: { by: \"human:reviewer\", at: \"2026-09-29T10:16:31Z\" }\n"
            "sources:\n"
            "  - { id: repeated, resource: first-source }\n"
            "  - { id: repeated, resource: second-source }\n",
        )
        (root / "example.md").write_text(content, encoding="utf-8")
        self.assertTrue(any("duplicate source id" in error for error in VALIDATOR.validate_bundle(root)))

    def test_invalid_log_date_heading_is_rejected(self) -> None:
        temporary_directory, root = self._bundle()
        self.addCleanup(temporary_directory.cleanup)
        (root / "log.md").write_text(
            "# Documentation update log\n\n## September 29, 2026\n\n- Updated.\n",
            encoding="utf-8",
        )
        self.assertTrue(any("invalid log date heading" in error for error in VALIDATOR.validate_bundle(root)))

    def test_redirect_with_missing_target_is_rejected(self) -> None:
        temporary_directory, root = self._bundle()
        self.addCleanup(temporary_directory.cleanup)
        redirect = VALID_FRONTMATTER.replace("Research Context", "Redirect")
        redirect = redirect.replace("status: stable", "status: deprecated")
        redirect = redirect.replace("authority: research-context", "authority: navigation")
        redirect = redirect.replace("---\n\n# Example", "redirect_to: missing.md\n---\n\n# Example", 1)
        (root / "example.md").write_text(redirect, encoding="utf-8")
        self.assertTrue(any("redirect target does not exist" in error for error in VALIDATOR.validate_bundle(root)))


if __name__ == "__main__":
    unittest.main()
