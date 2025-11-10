"""
Unit tests for version consistency.

These tests verify that version information is consistent across different files.
"""

import re
import sys
import unittest
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

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


if __name__ == "__main__":
    unittest.main()
