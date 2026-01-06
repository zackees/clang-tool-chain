"""
Integration tests for LLDB (LLVM Debugger) functionality.

These tests verify that LLDB tools are properly installed and can analyze
debug builds with crash information.

Note: These tests will FAIL (not skip) if LLDB infrastructure is broken.
"""

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import pytest

from clang_tool_chain import wrapper
from clang_tool_chain.downloader import ToolchainInfrastructureError


class TestLLDBInstallation(unittest.TestCase):
    """Test LLDB installation and binary availability."""

    def test_lldb_binary_dir_exists(self) -> None:
        """Test that LLDB binary directory can be located."""
        try:
            bin_dir = wrapper.get_lldb_binary_dir()
            self.assertTrue(bin_dir.exists(), f"LLDB binary directory should exist at {bin_dir}")
            self.assertTrue(bin_dir.is_dir(), f"LLDB binary location should be a directory: {bin_dir}")
        except ToolchainInfrastructureError:
            raise

    def test_find_lldb_tool(self) -> None:
        """Test finding the lldb binary."""
        try:
            lldb_path = wrapper.find_lldb_tool("lldb")
            self.assertTrue(lldb_path.exists(), f"LLDB tool should exist at {lldb_path}")
            self.assertTrue(lldb_path.is_file(), f"LLDB tool should be a file: {lldb_path}")
        except ToolchainInfrastructureError:
            raise


@pytest.mark.serial
class TestLLDBExecution(unittest.TestCase):
    """Test LLDB execution with crash analysis."""

    def setUp(self) -> None:
        """Set up test environment with temporary directory and test files."""
        self.temp_dir = tempfile.mkdtemp()
        self.temp_path = Path(self.temp_dir)

        # Create a test C file that will crash with null pointer dereference
        self.test_c = self.temp_path / "crash_test.c"
        self.test_c.write_text(
            """
#include <stdio.h>

void trigger_crash(int *ptr) {
    printf("About to crash...\\n");
    *ptr = 42;  // Null pointer dereference
}

void intermediate_function() {
    trigger_crash(NULL);
}

int main() {
    printf("Starting program...\\n");
    intermediate_function();
    return 0;
}
"""
        )

        # Output executable name
        if sys.platform == "win32":
            self.exe_name = self.temp_path / "crash_test.exe"
        else:
            self.exe_name = self.temp_path / "crash_test"

    def tearDown(self) -> None:
        """Clean up temporary files."""
        import shutil

        shutil.rmtree(self.temp_dir, ignore_errors=True)

    @pytest.mark.xfail(
        sys.platform == "win32",
        reason="Full 'bt all' backtraces require Python site-packages (lldb module) which is not bundled. "
        "Basic crash detection works but full stack traces may be incomplete. "
        "See docs/LLDB.md Python Dependencies section for details.",
        strict=False,
    )
    def test_lldb_print_crash_stack(self) -> None:
        """
        Test LLDB can analyze a debug build with null pointer exception.

        Steps:
        1. Compile crash_test.c with -g3 (full debug symbols)
        2. Run: clang-tool-chain-lldb --print crash_test.exe
        3. Verify output contains:
           - Function names: main, intermediate_function, trigger_crash
           - Source file reference: crash_test.c
           - Line number information
           - Crash reason (SIGSEGV, access violation, etc.)

        Note: This test may fail on Windows x64 due to missing Python site-packages.
        LLDB includes python310.dll but not the full Python environment needed for
        advanced backtrace features. Basic debugging still works.
        """
        # Step 1: Compile with debug symbols
        compile_cmd = [
            "clang-tool-chain-c",
            str(self.test_c),
            "-g3",  # Full debug information
            "-O0",  # No optimization for accurate debugging
            "-o",
            str(self.exe_name),
        ]

        result = subprocess.run(compile_cmd, capture_output=True, text=True, timeout=60)

        self.assertEqual(
            result.returncode,
            0,
            f"Compilation failed:\nSTDOUT: {result.stdout}\nSTDERR: {result.stderr}",
        )
        self.assertTrue(self.exe_name.exists(), f"Executable should exist at {self.exe_name}")

        # Step 2: Run LLDB with --print flag
        lldb_cmd = ["clang-tool-chain-lldb", "--print", str(self.exe_name)]

        result = subprocess.run(lldb_cmd, capture_output=True, text=True, timeout=60)

        # LLDB should exit with non-zero (program crashed)
        # But LLDB itself should run successfully

        output = result.stdout + result.stderr

        # Step 3: Verify stack trace contents
        # Check for function names in stack trace
        self.assertIn("main", output, "Stack trace should contain 'main' function")
        self.assertIn("intermediate_function", output, "Stack trace should contain 'intermediate_function'")
        self.assertIn("trigger_crash", output, "Stack trace should contain 'trigger_crash' function")

        # Check for source file reference
        self.assertIn("crash_test.c", output, "Stack trace should reference source file 'crash_test.c'")

        # Check for crash reason (platform-specific)
        crash_indicators = [
            "SIGSEGV",  # Linux/macOS signal
            "access violation",  # Windows
            "segmentation fault",
            "null pointer",
        ]

        has_crash_indicator = any(indicator.lower() in output.lower() for indicator in crash_indicators)
        self.assertTrue(has_crash_indicator, f"Stack trace should indicate crash reason. Output:\n{output}")

        # Check for line numbers (indicates debug symbols loaded)
        # Looking for patterns like ":12" or "line 12"
        import re

        line_number_patterns = [
            r":\d+",  # file.c:12
            r"line \d+",  # line 12
            r"#\d+.*:\d+",  # frame #0: file.c:12
        ]

        has_line_numbers = any(re.search(pattern, output) for pattern in line_number_patterns)
        self.assertTrue(has_line_numbers, f"Stack trace should contain line numbers. Output:\n{output}")


if __name__ == "__main__":
    unittest.main()
