"""
Test clang-query tool from the clang-extra distribution.

Verifies that clang-query is properly installed and functional.
"""

import subprocess
import unittest

import pytest

from clang_tool_chain.downloader import ToolchainInfrastructureError


@pytest.mark.serial
class TestClangQuery(unittest.TestCase):
    """Test clang-query functionality."""

    def test_clang_query_installed(self) -> None:
        """Test that clang-query is installed and accessible."""
        try:
            result = subprocess.run(
                ["clang-tool-chain-clang-query", "--version"],
                capture_output=True,
                text=True,
                timeout=60,
            )

            if result.returncode != 0 and "Tool 'clang-query' not found" in result.stderr:
                pytest.skip("clang-query not available for this platform")
            if result.returncode != 0 and "HTTP Error 404" in result.stderr:
                pytest.skip("clang-extra manifest not yet published to GitHub")

            self.assertEqual(result.returncode, 0, f"clang-query --version failed: {result.stderr}")

            combined_output = (result.stdout + result.stderr).lower()
            self.assertTrue(
                "clang-query" in combined_output or "version" in combined_output,
                "clang-query version output should contain version information",
            )
        except FileNotFoundError:
            self.fail("clang-tool-chain-clang-query command not found")
        except ToolchainInfrastructureError:
            raise

    def test_clang_query_help(self) -> None:
        """Test that clang-query --help works."""
        try:
            result = subprocess.run(
                ["clang-tool-chain-clang-query", "--help"],
                capture_output=True,
                text=True,
                timeout=60,
            )

            if result.returncode != 0 and "Tool 'clang-query' not found" in result.stderr:
                pytest.skip("clang-query not available for this platform")
            if result.returncode != 0 and "HTTP Error 404" in result.stderr:
                pytest.skip("clang-extra manifest not yet published to GitHub")

            combined_output = result.stdout + result.stderr
            self.assertTrue(
                "matcher" in combined_output.lower()
                or "usage" in combined_output.lower()
                or "query" in combined_output.lower(),
                "clang-query --help should show usage information",
            )
        except FileNotFoundError:
            self.fail("clang-tool-chain-clang-query command not found")
        except ToolchainInfrastructureError:
            raise


if __name__ == "__main__":
    unittest.main()
