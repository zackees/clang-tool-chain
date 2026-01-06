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

        Note: Python site-packages are bundled with LLDB on Windows x64, enabling
        full backtrace functionality including "bt all" command.
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

    def test_lldb_full_backtraces_with_python(self) -> None:
        """
        Test LLDB full "bt all" backtraces work with bundled Python site-packages.

        This test verifies that Python 3.10 site-packages are properly bundled and
        that LLDB can produce complete backtraces with all stack frames.

        Steps:
        1. Check if Python is bundled with LLDB installation
        2. Compile deep_stack.c with -g3 (7-level deep call stack)
        3. Run: clang-tool-chain-lldb --print deep_stack.exe
        4. Verify output contains all 7 user functions in stack trace
        5. Verify line numbers and source file references for all frames
        6. If Python is bundled, verify no Python import errors

        Success Criteria:
        - All 7 user functions visible in backtrace
        - Line numbers present for all user frames
        - Source file references accurate
        - If Python bundled: No Python-related errors in output
        """
        # Check if Python is bundled with LLDB
        from clang_tool_chain.execution.lldb import check_lldb_python_environment

        python_env = check_lldb_python_environment()
        python_bundled = python_env["status"] == "ready"

        if not python_bundled:
            self.skipTest(
                f"Python is not bundled with LLDB installation (status: {python_env['status']}). "
                f"Message: {python_env['message']}. "
                "This test requires LLDB with Python 3.10 site-packages. "
                "The LLDB distribution may not include Python modules yet."
            )
        # Create a test C file with deep call stack (7 levels)
        deep_stack_c = self.temp_path / "deep_stack.c"
        deep_stack_c.write_text(
            """
#include <stdio.h>

void level7_crash(int *ptr) {
    printf("Level 7 - About to crash\\n");
    *ptr = 42;  // Null pointer dereference
}

void level6(int *ptr) {
    printf("Level 6\\n");
    level7_crash(ptr);
}

void level5(int *ptr) {
    printf("Level 5\\n");
    level6(ptr);
}

void level4(int *ptr) {
    printf("Level 4\\n");
    level5(ptr);
}

void level3(int *ptr) {
    printf("Level 3\\n");
    level4(ptr);
}

void level2(int *ptr) {
    printf("Level 2\\n");
    level3(ptr);
}

void level1() {
    printf("Level 1\\n");
    level2(NULL);
}

int main() {
    printf("Starting deep stack test\\n");
    level1();
    return 0;
}
"""
        )

        # Output executable name
        if sys.platform == "win32":
            exe_name = self.temp_path / "deep_stack.exe"
        else:
            exe_name = self.temp_path / "deep_stack"

        # Step 1: Compile with debug symbols
        compile_cmd = [
            "clang-tool-chain-c",
            str(deep_stack_c),
            "-g3",  # Full debug information
            "-O0",  # No optimization for accurate debugging
            "-o",
            str(exe_name),
        ]

        result = subprocess.run(compile_cmd, capture_output=True, text=True, timeout=60)

        self.assertEqual(
            result.returncode,
            0,
            f"Compilation failed:\nSTDOUT: {result.stdout}\nSTDERR: {result.stderr}",
        )
        self.assertTrue(exe_name.exists(), f"Executable should exist at {exe_name}")

        # Step 2: Run LLDB with --print flag
        lldb_cmd = ["clang-tool-chain-lldb", "--print", str(exe_name)]

        result = subprocess.run(lldb_cmd, capture_output=True, text=True, timeout=60)

        output = result.stdout + result.stderr

        # Step 3: Verify all 7 user functions in stack trace
        expected_functions = [
            "main",
            "level1",
            "level2",
            "level3",
            "level4",
            "level5",
            "level6",
            "level7_crash",
        ]

        for func in expected_functions:
            self.assertIn(func, output, f"Stack trace should contain '{func}' function. Output:\n{output}")

        # Step 4: Verify line numbers present (indicates debug symbols and full backtrace)
        import re

        line_number_patterns = [
            r":\d+",  # file.c:12
            r"line \d+",  # line 12
            r"#\d+.*:\d+",  # frame #0: file.c:12
        ]

        has_line_numbers = any(re.search(pattern, output) for pattern in line_number_patterns)
        self.assertTrue(has_line_numbers, f"Stack trace should contain line numbers. Output:\n{output}")

        # Step 5: Verify source file references
        self.assertIn("deep_stack.c", output, "Stack trace should reference source file 'deep_stack.c'")

        # Step 6: Verify no Python-related errors (only checked if Python is bundled)
        # Since we already skipped the test if Python isn't bundled, any Python errors here
        # indicate a configuration problem with the bundled Python
        python_error_indicators = [
            "ModuleNotFoundError",
            "ImportError",
            "Python module not found",
            "Failed to load Python",
            "LLDB_DISABLE_PYTHON",
        ]

        for error_indicator in python_error_indicators:
            self.assertNotIn(
                error_indicator,
                output,
                f"Output should not contain Python error '{error_indicator}'. "
                f"Python is bundled (status: {python_env['status']}) but errors occurred. "
                f"This indicates a configuration problem. Output:\n{output}",
            )

        # Step 7: Verify crash reason present
        crash_indicators = [
            "SIGSEGV",  # Linux/macOS signal
            "access violation",  # Windows
            "segmentation fault",
            "null pointer",
        ]

        has_crash_indicator = any(indicator.lower() in output.lower() for indicator in crash_indicators)
        self.assertTrue(has_crash_indicator, f"Stack trace should indicate crash reason. Output:\n{output}")


if __name__ == "__main__":
    unittest.main()
