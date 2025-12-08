"""
Test clang-format and clang-tidy tools.

These tests verify that the formatting and linting tools are properly installed
and functional across all platforms.
"""

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import pytest

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from clang_tool_chain.downloader import ToolchainInfrastructureError


class TestClangFormat(unittest.TestCase):
    """Test clang-format functionality."""

    def test_clang_format_installed(self) -> None:
        """Test that clang-format is installed and accessible."""
        try:
            result = subprocess.run(
                ["clang-tool-chain-format", "--version"],
                capture_output=True,
                text=True,
                timeout=30,
            )

            # If tool not found in binaries, skip the test
            if result.returncode != 0 and "Tool 'clang-format' not found" in result.stderr:
                pytest.skip("clang-format not included in LLVM binaries for this platform")

            # clang-format --version should succeed
            self.assertEqual(result.returncode, 0, f"clang-format --version failed: {result.stderr}")

            # Check for version info in output
            combined_output = (result.stdout + result.stderr).lower()
            self.assertTrue(
                "clang-format" in combined_output or "version" in combined_output,
                "clang-format version output should contain version information",
            )
        except FileNotFoundError:
            self.fail("clang-tool-chain-format command not found")
        except ToolchainInfrastructureError:
            raise

    def test_clang_format_basic(self) -> None:
        """Test basic clang-format functionality."""
        temp_dir = tempfile.mkdtemp()
        temp_path = Path(temp_dir)

        try:
            # Create unformatted C++ file
            test_cpp = temp_path / "test_format.cpp"
            test_cpp.write_text(
                "int main(){int x=1;int y=2;return x+y;}\n"
            )

            # Run clang-format
            result = subprocess.run(
                ["clang-tool-chain-format", "-style=LLVM", str(test_cpp)],
                capture_output=True,
                text=True,
                timeout=30,
            )

            # If tool not found in binaries, skip the test
            if result.returncode != 0 and "Tool 'clang-format' not found" in result.stderr:
                pytest.skip("clang-format not included in LLVM binaries for this platform")

            # Should succeed
            self.assertEqual(result.returncode, 0, f"clang-format failed: {result.stderr}")

            # Should produce formatted output
            self.assertGreater(len(result.stdout), 0, "clang-format should produce output")

            # Formatted code should have proper spacing
            self.assertIn("int x = 1", result.stdout, "clang-format should add spacing around operators")

        except ToolchainInfrastructureError:
            raise
        finally:
            import shutil
            shutil.rmtree(temp_dir, ignore_errors=True)

    def test_clang_format_inplace(self) -> None:
        """Test clang-format in-place modification."""
        temp_dir = tempfile.mkdtemp()
        temp_path = Path(temp_dir)

        try:
            # Create unformatted C++ file
            test_cpp = temp_path / "test_inplace.cpp"
            original_content = "int main(){int x=1;return x;}\n"
            test_cpp.write_text(original_content)

            # Run clang-format in-place
            result = subprocess.run(
                ["clang-tool-chain-format", "-i", "-style=LLVM", str(test_cpp)],
                capture_output=True,
                text=True,
                timeout=30,
            )

            # If tool not found in binaries, skip the test
            if result.returncode != 0 and "Tool 'clang-format' not found" in result.stderr:
                pytest.skip("clang-format not included in LLVM binaries for this platform")

            # Should succeed
            self.assertEqual(result.returncode, 0, f"clang-format -i failed: {result.stderr}")

            # File should be modified
            modified_content = test_cpp.read_text()
            self.assertNotEqual(
                original_content,
                modified_content,
                "clang-format -i should modify the file",
            )

            # Modified content should have proper formatting
            self.assertIn("int x = 1", modified_content, "Formatted code should have proper spacing")

        except ToolchainInfrastructureError:
            raise
        finally:
            import shutil
            shutil.rmtree(temp_dir, ignore_errors=True)


@pytest.mark.serial
class TestClangTidy(unittest.TestCase):
    """Test clang-tidy functionality."""

    def test_clang_tidy_installed(self) -> None:
        """Test that clang-tidy is installed and accessible."""
        try:
            result = subprocess.run(
                ["clang-tool-chain-tidy", "--version"],
                capture_output=True,
                text=True,
                timeout=30,
            )

            # If tool not found in binaries, skip the test
            if result.returncode != 0 and "Tool 'clang-tidy' not found" in result.stderr:
                pytest.skip("clang-tidy not included in LLVM binaries for this platform")

            # clang-tidy --version should succeed
            self.assertEqual(result.returncode, 0, f"clang-tidy --version failed: {result.stderr}")

            # Check for version info in output
            combined_output = (result.stdout + result.stderr).lower()
            self.assertTrue(
                "clang-tidy" in combined_output or "llvm" in combined_output or "version" in combined_output,
                "clang-tidy version output should contain version information",
            )
        except FileNotFoundError:
            self.fail("clang-tool-chain-tidy command not found")
        except ToolchainInfrastructureError:
            raise

    def test_clang_tidy_basic(self) -> None:
        """Test basic clang-tidy functionality."""
        temp_dir = tempfile.mkdtemp()
        temp_path = Path(temp_dir)

        try:
            # Create C++ file with potential issues
            test_cpp = temp_path / "test_tidy.cpp"
            test_cpp.write_text(
                """
#include <iostream>

int main() {
    int x = 0;
    int y = x;
    std::cout << y << std::endl;
    return 0;
}
"""
            )

            # Run clang-tidy (may not find issues, just verify it runs)
            result = subprocess.run(
                ["clang-tool-chain-tidy", str(test_cpp), "--"],
                capture_output=True,
                text=True,
                timeout=60,
            )

            # If tool not found in binaries, skip the test
            if result.returncode != 0 and "Tool 'clang-tidy' not found" in result.stderr:
                pytest.skip("clang-tidy not included in LLVM binaries for this platform")

            # clang-tidy may return non-zero for warnings, so check it completed
            self.assertIn(
                result.returncode,
                [0, 1],
                f"clang-tidy should complete. Return code: {result.returncode}, stderr: {result.stderr[:200]}",
            )

        except ToolchainInfrastructureError:
            raise
        except subprocess.TimeoutExpired:
            self.skipTest("clang-tidy analysis timed out - this may be a platform-specific issue")
        finally:
            import shutil
            shutil.rmtree(temp_dir, ignore_errors=True)

    def test_clang_tidy_with_checks(self) -> None:
        """Test clang-tidy with specific checks."""
        temp_dir = tempfile.mkdtemp()
        temp_path = Path(temp_dir)

        try:
            # Create C++ file
            test_cpp = temp_path / "test_checks.cpp"
            test_cpp.write_text(
                """
int main() {
    int unused_variable = 42;
    return 0;
}
"""
            )

            # Run clang-tidy with specific checks
            result = subprocess.run(
                [
                    "clang-tool-chain-tidy",
                    str(test_cpp),
                    "-checks=-*,readability-*",
                    "--",
                ],
                capture_output=True,
                text=True,
                timeout=60,
            )

            # If tool not found in binaries, skip the test
            if result.returncode != 0 and "Tool 'clang-tidy' not found" in result.stderr:
                pytest.skip("clang-tidy not included in LLVM binaries for this platform")

            # Should complete (may find warnings)
            self.assertIn(
                result.returncode,
                [0, 1],
                f"clang-tidy should complete with checks. Return code: {result.returncode}",
            )

        except ToolchainInfrastructureError:
            raise
        except subprocess.TimeoutExpired:
            self.skipTest("clang-tidy analysis timed out - this may be a platform-specific issue")
        finally:
            import shutil
            shutil.rmtree(temp_dir, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
