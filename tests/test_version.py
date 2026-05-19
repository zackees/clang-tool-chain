"""
Unit tests for version consistency.

These tests verify that version information is consistent across different files.
"""

import re
import unittest
from pathlib import Path

from clang_tool_chain.__version__ import __version__


class TestVersionConsistency(unittest.TestCase):
    """Test version consistency across files."""

    def test_version_matches_pyproject_toml(self) -> None:
        """Test that __version__.py version matches pyproject.toml version."""
        # Read pyproject.toml
        pyproject_path = Path(__file__).parent.parent / "pyproject.toml"
        pyproject_content = pyproject_path.read_text(encoding="utf-8")

        # Extract version from pyproject.toml using regex
        # Looking for: version = "x.y.z"
        version_pattern = r'^version\s*=\s*"([^"]+)"'
        match = re.search(version_pattern, pyproject_content, re.MULTILINE)

        self.assertIsNotNone(match, "Could not find version in pyproject.toml")
        pyproject_version = match.group(1) if match else None

        # Compare versions
        self.assertEqual(
            __version__,
            pyproject_version,
            f"Version mismatch: __version__.py has '{__version__}' but pyproject.toml has '{pyproject_version}'",
        )

    def test_version_format(self) -> None:
        """Test that version follows semantic versioning format."""
        # Semantic versioning pattern: MAJOR.MINOR.PATCH with optional pre-release/build metadata
        semver_pattern = (
            r"^\d+\.\d+\.\d+(?:-[0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*)?(?:\+[0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*)?$"
        )

        self.assertIsNotNone(
            re.match(semver_pattern, __version__), f"Version '{__version__}' does not follow semantic versioning format"
        )

    def test_init_py_imports_from_version_py(self) -> None:
        """Test that __init__.py's __version__ matches __version__.py's value.

        Regression guard for issue #34: __init__.py previously hardcoded
        ``__version__ = "1.1.10"`` and was missed on every version bump
        since then, so ``clang_tool_chain.__version__`` lied to callers.
        Fixed by making __init__.py import from __version__.py.

        This test catches the drift two ways:
          1. Runtime check: ``clang_tool_chain.__version__`` (read via the
             package import) must equal ``__version__.__version__``.
          2. Source-level check: __init__.py must NOT contain a hardcoded
             string assignment to __version__ — only an import.
        """
        import clang_tool_chain

        self.assertEqual(
            clang_tool_chain.__version__,
            __version__,
            f"Runtime drift: clang_tool_chain.__version__='{clang_tool_chain.__version__}' "
            f"but __version__.py says '{__version__}'. "
            f"__init__.py probably hardcodes the value instead of importing it.",
        )

        # Source-level guard: forbid the hardcoded-string pattern that caused
        # the drift in the first place. An ``import`` line containing the
        # word ``__version__`` is fine; a bare assignment is not.
        init_path = Path(__file__).parent.parent / "src" / "clang_tool_chain" / "__init__.py"
        init_src = init_path.read_text(encoding="utf-8")
        hardcoded = re.search(r'^__version__\s*=\s*"[^"]+"', init_src, re.MULTILINE)
        self.assertIsNone(
            hardcoded,
            "Found a hardcoded __version__ assignment in src/clang_tool_chain/__init__.py. "
            "Drop it and import from __version__.py instead to prevent version drift "
            "(see issue #34 and CLAUDE.md's version-bump checklist).",
        )


if __name__ == "__main__":
    unittest.main()
