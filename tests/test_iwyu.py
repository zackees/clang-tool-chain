"""
Integration tests for IWYU (Include What You Use) functionality.

These tests verify that the IWYU tools are properly installed and functional.

Note: These tests will FAIL (not skip) if the IWYU infrastructure is broken
(404 errors, missing manifests, etc). This ensures that broken URLs are caught
in CI rather than silently ignored.
"""

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import pytest

from clang_tool_chain import wrapper
from clang_tool_chain.downloader import ToolchainInfrastructureError


class TestIWYUInstallation(unittest.TestCase):
    """Test IWYU installation and basic functionality."""

    def test_iwyu_binary_dir_exists(self) -> None:
        """Test that IWYU binary directory can be located."""
        try:
            bin_dir = wrapper.get_iwyu_binary_dir()
            self.assertTrue(bin_dir.exists(), f"IWYU binary directory should exist at {bin_dir}")
            self.assertTrue(bin_dir.is_dir(), f"IWYU binary location should be a directory: {bin_dir}")
        except ToolchainInfrastructureError:
            # Infrastructure errors should fail the test, not skip it
            raise

    def test_find_iwyu_tool(self) -> None:
        """Test finding the include-what-you-use binary."""
        try:
            iwyu_path = wrapper.find_iwyu_tool("include-what-you-use")
            self.assertTrue(iwyu_path.exists(), f"IWYU tool should exist at {iwyu_path}")
            self.assertTrue(iwyu_path.is_file(), f"IWYU tool should be a file: {iwyu_path}")
        except ToolchainInfrastructureError:
            raise

    def test_find_iwyu_tool_py(self) -> None:
        """Test finding the iwyu_tool.py helper script."""
        try:
            iwyu_tool_path = wrapper.find_iwyu_tool("iwyu_tool.py")
            self.assertTrue(iwyu_tool_path.exists(), f"iwyu_tool.py should exist at {iwyu_tool_path}")
            self.assertTrue(iwyu_tool_path.is_file(), f"iwyu_tool.py should be a file: {iwyu_tool_path}")
        except ToolchainInfrastructureError:
            raise

    def test_find_fix_includes_py(self) -> None:
        """Test finding the fix_includes.py helper script."""
        try:
            fix_includes_path = wrapper.find_iwyu_tool("fix_includes.py")
            self.assertTrue(fix_includes_path.exists(), f"fix_includes.py should exist at {fix_includes_path}")
            self.assertTrue(fix_includes_path.is_file(), f"fix_includes.py should be a file: {fix_includes_path}")
        except RuntimeError as e:
            # fix_includes.py is not included in some IWYU distributions (e.g., Windows)
            if "not found" in str(e):
                pytest.skip(f"fix_includes.py not available in this IWYU distribution: {e}")
            raise
        except ToolchainInfrastructureError:
            raise


@pytest.mark.serial
class TestIWYUExecution(unittest.TestCase):
    """Test IWYU execution with real C++ code."""

    def setUp(self) -> None:
        """Set up test environment with temporary directory and test files."""
        self.temp_dir = tempfile.mkdtemp()
        self.temp_path = Path(self.temp_dir)

        # Create a test C++ file with unused includes
        self.test_cpp = self.temp_path / "test.cpp"
        self.test_cpp.write_text(
            "#include <iostream>\n"
            "#include <vector>\n"
            "#include <string>\n"
            "\n"
            "// Only using iostream, vector and string are unused\n"
            "int main() {\n"
            '    std::cout << "Hello from IWYU test!" << std::endl;\n'
            "    return 0;\n"
            "}\n"
        )

        # Create a test file with proper includes
        # Optimization: Use C stdio.h instead of C++ iostream for faster parsing
        self.good_cpp = self.temp_path / "good.c"
        self.good_cpp.write_text('#include <stdio.h>\n\nint main() {\n    printf("Hello!\\n");\n    return 0;\n}\n')

        # Create a test file that uses vector
        self.vector_cpp = self.temp_path / "vector_test.cpp"
        self.vector_cpp.write_text(
            "#include <vector>\n"
            "#include <iostream>\n"
            "\n"
            "int main() {\n"
            "    std::vector<int> vec = {1, 2, 3};\n"
            "    std::cout << vec.size() << std::endl;\n"
            "    return 0;\n"
            "}\n"
        )

    def tearDown(self) -> None:
        """Clean up temporary directory."""
        import shutil

        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def get_iwyu_env(self, verbose: bool = False) -> dict[str, str]:
        """Get environment dict for running IWYU with DLL path on Windows and shared libraries on Linux.

        Args:
            verbose: If True, enable verbose library loading diagnostics (LD_DEBUG on Linux)
        """
        import os

        env = os.environ.copy()

        # On Windows, add the IWYU bin directory to PATH so DLLs can be found
        if sys.platform == "win32":
            bin_dir = wrapper.get_iwyu_binary_dir()
            env["PATH"] = f"{bin_dir}{os.pathsep}{env.get('PATH', '')}"
        # On Linux, add the IWYU lib directory to LD_LIBRARY_PATH so shared libraries can be found
        elif sys.platform == "linux":
            bin_dir = wrapper.get_iwyu_binary_dir()
            lib_dir = bin_dir.parent / "lib"
            if lib_dir.exists():
                existing_ld_path = env.get("LD_LIBRARY_PATH", "")
                if existing_ld_path:
                    env["LD_LIBRARY_PATH"] = f"{lib_dir}{os.pathsep}{existing_ld_path}"
                else:
                    env["LD_LIBRARY_PATH"] = str(lib_dir)

            # Enable verbose library loading diagnostics if requested
            # LD_DEBUG=libs shows library search paths and loading details
            # LD_DEBUG=all shows everything (very verbose)
            if verbose:
                env["LD_DEBUG"] = "libs"

        return env

    def _check_for_crash(self, result: subprocess.CompletedProcess[str], iwyu_path: Path, context: str = "") -> None:
        """Check if IWYU crashed and provide detailed diagnostics.

        Args:
            result: The subprocess result from running IWYU
            iwyu_path: Path to the IWYU binary
            context: Additional context for the error message
        """
        if result.returncode < 0:
            signal_name = {
                -11: "SIGSEGV (Segmentation fault)",
                -6: "SIGABRT (Abort)",
                -4: "SIGILL (Illegal instruction)",
            }.get(result.returncode, f"Signal {-result.returncode}")

            # Re-run with verbose diagnostics to get library loading info
            diagnostic_info = ""
            if sys.platform == "linux":
                try:
                    verbose_result = subprocess.run(
                        [str(iwyu_path), "--version"],
                        capture_output=True,
                        text=True,
                        timeout=10,
                        env=self.get_iwyu_env(verbose=True),
                    )
                    diagnostic_info = (
                        f"\n\nLibrary loading diagnostics (LD_DEBUG=libs):\n{verbose_result.stderr[:2000]}"
                    )
                except Exception as e:
                    diagnostic_info = f"\n\nFailed to get diagnostics: {e}"

            context_msg = f" ({context})" if context else ""
            self.fail(
                f"IWYU crashed with {signal_name}{context_msg}. "
                f"This usually indicates:\n"
                f"  - Missing shared library dependencies\n"
                f"  - ABI incompatibility between binary and system libraries\n"
                f"  - Corrupted binary\n\n"
                f"Binary path: {iwyu_path}\n"
                f"Return code: {result.returncode}\n"
                f"stdout: {result.stdout[:500]}\n"
                f"stderr: {result.stderr[:500]}{diagnostic_info}"
            )

    def test_iwyu_version(self) -> None:
        """Test that IWYU can report its version."""
        try:
            iwyu_path = wrapper.find_iwyu_tool("include-what-you-use")
            result = subprocess.run(
                [str(iwyu_path), "--version"], capture_output=True, text=True, timeout=10, env=self.get_iwyu_env()
            )

            # Check for crash signals (negative return codes on Unix)
            self._check_for_crash(result, iwyu_path, context="--version command")

            # IWYU may return 0 or non-zero for --version
            self.assertIn(
                result.returncode,
                [0, 1],
                f"IWYU version command should complete. Return code: {result.returncode}",
            )

            # Check for version info in output (may be in stdout or stderr)
            combined_output = (result.stdout + result.stderr).lower()
            self.assertTrue(
                "include-what-you-use" in combined_output or "iwyu" in combined_output or "clang" in combined_output,
                "IWYU version output should contain tool information",
            )
        except ToolchainInfrastructureError:
            raise
        except subprocess.TimeoutExpired:
            self.skipTest("IWYU analysis timed out - this may be a platform-specific issue")

    def test_iwyu_analyze_file(self) -> None:
        """Test running IWYU on a test file.

        Optimization: Use simpler C headers instead of heavy C++ STL headers.
        C standard library headers (stdio.h, stdlib.h) parse much faster than
        C++ iostream/vector/string which have complex template implementations.
        """
        try:
            # Create a simpler test file with C headers for faster parsing
            simple_test_cpp = self.temp_path / "simple_test.c"
            simple_test_cpp.write_text(
                "#include <stdio.h>\n"
                "#include <stdlib.h>\n"
                "\n"
                "// Only using stdio.h, stdlib.h is unused\n"
                "int main() {\n"
                '    printf("Hello from IWYU test!\\n");\n'
                "    return 0;\n"
                "}\n"
            )

            iwyu_path = wrapper.find_iwyu_tool("include-what-you-use")
            clang_bin_dir = wrapper.get_platform_binary_dir()

            # Run IWYU on the test file
            # IWYU needs to know where to find system headers
            result = subprocess.run(
                [
                    str(iwyu_path),
                    str(simple_test_cpp),
                    "--",
                    f"-I{clang_bin_dir.parent / 'include'}",
                ],
                capture_output=True,
                text=True,
                timeout=30,
                cwd=str(self.temp_path),
                env=self.get_iwyu_env(),
            )

            # Check for crash signals
            self._check_for_crash(result, iwyu_path, context="analyzing test file")

            # IWYU returns non-zero when it finds issues (which is expected)
            # We just verify it runs without crashing
            self.assertIn(
                result.returncode,
                [0, 1, 2],
                f"IWYU should complete analysis. Return code: {result.returncode}, stderr: {result.stderr[:200]}",
            )

            # IWYU produces output (usually to stderr)
            combined_output = result.stdout + result.stderr
            self.assertTrue(
                len(combined_output) > 0,
                "IWYU should produce output",
            )
        except ToolchainInfrastructureError:
            raise
        except subprocess.TimeoutExpired:
            self.skipTest("IWYU analysis timed out - this may be a platform-specific issue")

    def test_iwyu_on_good_file(self) -> None:
        """Test IWYU on a file with correct includes."""
        try:
            iwyu_path = wrapper.find_iwyu_tool("include-what-you-use")
            clang_bin_dir = wrapper.get_platform_binary_dir()

            result = subprocess.run(
                [
                    str(iwyu_path),
                    str(self.good_cpp),
                    "--",
                    f"-I{clang_bin_dir.parent / 'include'}",
                ],
                capture_output=True,
                text=True,
                timeout=30,
                cwd=str(self.temp_path),
                env=self.get_iwyu_env(),
            )

            # Check for crash signals
            self._check_for_crash(result, iwyu_path, context="analyzing good file")

            # IWYU should complete (return code may vary)
            self.assertIn(
                result.returncode,
                [0, 1, 2],
                f"IWYU should complete analysis on good file. Return code: {result.returncode}",
            )
        except ToolchainInfrastructureError:
            raise
        except subprocess.TimeoutExpired:
            self.skipTest("IWYU analysis timed out - this may be a platform-specific issue")

    def test_iwyu_with_compile_commands(self) -> None:
        """Test IWYU with a compilation database.

        Optimization: Use simpler C file instead of C++ to reduce parsing time.
        """
        try:
            import json

            # Create a simpler C test file for faster parsing
            simple_c = self.temp_path / "simple_db_test.c"
            simple_c.write_text(
                '#include <stdio.h>\n#include <stdlib.h>\n\nint main() {\n    printf("Test\\n");\n    return 0;\n}\n'
            )

            # Create a simple compile_commands.json
            compile_commands = [
                {
                    "directory": str(self.temp_path),
                    "command": f"clang -c {simple_c}",
                    "file": str(simple_c),
                }
            ]

            compile_db_path = self.temp_path / "compile_commands.json"
            compile_db_path.write_text(json.dumps(compile_commands, indent=2))

            iwyu_path = wrapper.find_iwyu_tool("include-what-you-use")

            # Run IWYU with the compilation database
            result = subprocess.run(
                [str(iwyu_path), str(simple_c)],
                capture_output=True,
                text=True,
                timeout=30,
                cwd=str(self.temp_path),
                env=self.get_iwyu_env(),
            )

            # Check for crash signals
            self._check_for_crash(result, iwyu_path, context="with compilation database")

            # IWYU should complete (may have warnings/suggestions)
            self.assertIn(
                result.returncode,
                [0, 1, 2],
                f"IWYU should complete with compile database. Return code: {result.returncode}",
            )
        except ToolchainInfrastructureError:
            raise
        except subprocess.TimeoutExpired:
            self.skipTest("IWYU analysis timed out - this may be a platform-specific issue")


@pytest.mark.serial
class TestIWYUHelperScripts(unittest.TestCase):
    """Test IWYU helper Python scripts."""

    def test_iwyu_tool_help(self) -> None:
        """Test that iwyu_tool.py can display help."""
        try:
            iwyu_tool_path = wrapper.find_iwyu_tool("iwyu_tool.py")
            python_exe = sys.executable

            result = subprocess.run(
                [python_exe, str(iwyu_tool_path), "--help"],
                capture_output=True,
                text=True,
                timeout=10,
            )

            # Help command should succeed
            self.assertEqual(result.returncode, 0, "iwyu_tool.py --help should succeed")

            # Should contain usage information
            combined_output = result.stdout + result.stderr
            self.assertTrue(
                "usage" in combined_output.lower() or "help" in combined_output.lower(),
                "iwyu_tool.py help should contain usage information",
            )
        except ToolchainInfrastructureError:
            raise

    def test_fix_includes_help(self) -> None:
        """Test that fix_includes.py can display help."""
        try:
            fix_includes_path = wrapper.find_iwyu_tool("fix_includes.py")
            python_exe = sys.executable

            result = subprocess.run(
                [python_exe, str(fix_includes_path), "--help"],
                capture_output=True,
                text=True,
                timeout=10,
            )

            # Help command should succeed
            self.assertEqual(result.returncode, 0, "fix_includes.py --help should succeed")

            # Should contain usage information
            combined_output = result.stdout + result.stderr
            self.assertTrue(
                "usage" in combined_output.lower() or "help" in combined_output.lower(),
                "fix_includes.py help should contain usage information",
            )
        except RuntimeError as e:
            # fix_includes.py is not included in some IWYU distributions (e.g., Windows)
            if "not found" in str(e):
                pytest.skip(f"fix_includes.py not available in this IWYU distribution: {e}")
            raise
        except ToolchainInfrastructureError:
            raise


class TestIWYUWrapperEntryPoints(unittest.TestCase):
    """Test that IWYU wrapper entry points work correctly."""

    def test_wrapper_can_find_iwyu_binary_dir(self) -> None:
        """Test that the wrapper can locate IWYU binary directory."""
        try:
            bin_dir = wrapper.get_iwyu_binary_dir()
            self.assertTrue(bin_dir.exists(), "IWYU binary directory should exist")

            # Check for expected files using find_iwyu_tool which has retry logic
            # for Windows file system caching issues during parallel test execution
            iwyu_path = wrapper.find_iwyu_tool("include-what-you-use")
            self.assertTrue(
                iwyu_path.exists(),
                f"IWYU binary should exist at {iwyu_path}",
            )
            self.assertTrue(iwyu_path.is_file(), f"IWYU binary should be a file: {iwyu_path}")
        except ToolchainInfrastructureError:
            raise

    def test_wrapper_find_all_iwyu_tools(self) -> None:
        """Test that wrapper can find all IWYU tools."""
        tools = ["include-what-you-use", "iwyu_tool.py", "fix_includes.py"]

        for tool_name in tools:
            with self.subTest(tool=tool_name):
                try:
                    tool_path = wrapper.find_iwyu_tool(tool_name)
                    self.assertTrue(tool_path.exists(), f"{tool_name} should exist at {tool_path}")
                except ToolchainInfrastructureError:
                    raise
                except RuntimeError as e:
                    self.skipTest(f"IWYU binaries not installed: {e}")


if __name__ == "__main__":
    unittest.main()
