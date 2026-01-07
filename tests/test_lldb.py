"""
Integration tests for LLDB (LLVM Debugger) functionality.

These tests verify that LLDB tools are properly installed and can analyze
debug builds with crash information.

Note: These tests will FAIL (not skip) if LLDB infrastructure is broken.
"""

import re
import subprocess
import sys
import tempfile
import time
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

    def _format_diagnostic_output(
        self, title: str, cmd: list[str], result: subprocess.CompletedProcess[str], elapsed_time: float | None = None
    ) -> str:
        """Format diagnostic output for test failures."""
        lines = [
            f"\n{'=' * 80}",
            f"DIAGNOSTIC: {title}",
            f"{'=' * 80}",
            f"Command: {' '.join(cmd)}",
        ]
        if elapsed_time is not None:
            lines.append(f"Elapsed Time: {elapsed_time:.2f}s")
        lines.extend(
            [
                f"Return Code: {result.returncode}",
                f"\nSTDOUT ({len(result.stdout)} chars):",
                "-" * 80,
                result.stdout if result.stdout else "(empty)",
                "-" * 80,
                f"\nSTDERR ({len(result.stderr)} chars):",
                "-" * 80,
                result.stderr if result.stderr else "(empty)",
                "-" * 80,
                f"{'=' * 80}\n",
            ]
        )
        return "\n".join(lines)

    def _extract_stack_frames(self, output: str) -> list[str]:
        """Extract stack frame information from LLDB output."""
        # Match patterns like "frame #0:", "* thread #1", function names, etc.
        frame_patterns = [
            r"frame\s+#\d+:.*",  # frame #0: ...
            r"\*\s+thread\s+#\d+.*",  # * thread #1 ...
            r"#\d+\s+\w+\s+in\s+\w+.*",  # #0  0x... in main ...
        ]
        frames = []
        for line in output.splitlines():
            for pattern in frame_patterns:
                if re.search(pattern, line, re.IGNORECASE):
                    frames.append(line.strip())
                    break
        return frames

    def setUp(self) -> None:
        """Set up test environment with temporary directory and test files."""
        self.temp_dir = tempfile.mkdtemp()
        self.temp_path = Path(self.temp_dir)
        self.timing_info: dict[str, float] = {}

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
        # Check if python310.dll is present on Windows (required for LLDB to run)
        if sys.platform == "win32":

            bin_dir = wrapper.get_lldb_binary_dir()
            python_dll = bin_dir / "python310.dll"
            if not python_dll.exists():
                self.skipTest(
                    f"python310.dll is missing from LLDB installation at {python_dll}. "
                    "This is a critical dependency for liblldb.dll. The LLDB archive may be incomplete. "
                    "LLDB cannot run without this file."
                )

        # Step 1: Compile with debug symbols
        compile_cmd = [
            "clang-tool-chain-c",
            str(self.test_c),
            "-g3",  # Full debug information
            "-O0",  # No optimization for accurate debugging
            "-o",
            str(self.exe_name),
        ]

        start_time = time.time()
        result = subprocess.run(compile_cmd, capture_output=True, text=True, timeout=60)
        compile_time = time.time() - start_time
        self.timing_info["compile"] = compile_time

        self.assertEqual(
            result.returncode,
            0,
            f"Compilation failed{self._format_diagnostic_output('Compilation Failure', compile_cmd, result, compile_time)}",
        )
        self.assertTrue(self.exe_name.exists(), f"Executable should exist at {self.exe_name}")

        # Step 2: Run LLDB with --print flag
        lldb_cmd = ["clang-tool-chain-lldb", "--print", str(self.exe_name)]

        start_time = time.time()
        result = subprocess.run(lldb_cmd, capture_output=True, text=True, timeout=60)
        lldb_time = time.time() - start_time
        self.timing_info["lldb_execution"] = lldb_time

        # LLDB should exit with non-zero (program crashed)
        # But LLDB itself should run successfully

        output = result.stdout + result.stderr
        diagnostic = self._format_diagnostic_output("LLDB Crash Analysis", lldb_cmd, result, lldb_time)

        # Extract stack frames for better diagnostics
        frames = self._extract_stack_frames(output)
        frames_info = (
            f"\nExtracted {len(frames)} stack frames:\n" + "\n".join(f"  {frame}" for frame in frames)
            if frames
            else "\nNo stack frames detected!"
        )

        # Step 3: Verify stack trace contents
        # Check for function names in stack trace
        expected_functions = ["main", "intermediate_function", "trigger_crash"]
        missing_functions = [func for func in expected_functions if func not in output]

        if missing_functions:
            self.fail(
                f"Missing functions in stack trace: {missing_functions}\n"
                f"Expected all of: {expected_functions}{frames_info}{diagnostic}"
            )

        # Check for source file reference
        self.assertIn(
            "crash_test.c", output, f"Stack trace should reference source file 'crash_test.c'{frames_info}{diagnostic}"
        )

        # Check for crash reason (platform-specific)
        crash_indicators = [
            "SIGSEGV",  # Linux/macOS signal
            "access violation",  # Windows
            "segmentation fault",
            "null pointer",
        ]

        has_crash_indicator = any(indicator.lower() in output.lower() for indicator in crash_indicators)
        if not has_crash_indicator:
            self.fail(
                f"Stack trace should indicate crash reason (expected one of: {crash_indicators})\n"
                f"No crash indicator found in output{frames_info}{diagnostic}"
            )

        # Check for line numbers (indicates debug symbols loaded)
        # Looking for patterns like ":12" or "line 12"
        line_number_patterns = [
            r":\d+",  # file.c:12
            r"line \d+",  # line 12
            r"#\d+.*:\d+",  # frame #0: file.c:12
        ]

        has_line_numbers = any(re.search(pattern, output) for pattern in line_number_patterns)
        if not has_line_numbers:
            self.fail(
                f"Stack trace should contain line numbers (patterns: {line_number_patterns})\n"
                f"No line numbers found{frames_info}{diagnostic}"
            )

        # Print timing summary on success
        print(
            f"\n✓ test_lldb_print_crash_stack: compile={compile_time:.2f}s, lldb={lldb_time:.2f}s, total={compile_time+lldb_time:.2f}s"
        )

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

        start_time = time.time()
        result = subprocess.run(compile_cmd, capture_output=True, text=True, timeout=60)
        compile_time = time.time() - start_time
        self.timing_info["deep_stack_compile"] = compile_time

        self.assertEqual(
            result.returncode,
            0,
            f"Compilation failed{self._format_diagnostic_output('Deep Stack Compilation Failure', compile_cmd, result, compile_time)}",
        )
        self.assertTrue(exe_name.exists(), f"Executable should exist at {exe_name}")

        # Step 2: Run LLDB with --print flag
        lldb_cmd = ["clang-tool-chain-lldb", "--print", str(exe_name)]

        start_time = time.time()
        result = subprocess.run(lldb_cmd, capture_output=True, text=True, timeout=60)
        lldb_time = time.time() - start_time
        self.timing_info["deep_stack_lldb"] = lldb_time

        output = result.stdout + result.stderr
        diagnostic = self._format_diagnostic_output("LLDB Deep Stack Analysis", lldb_cmd, result, lldb_time)

        # Extract stack frames for better diagnostics
        frames = self._extract_stack_frames(output)
        frames_info = (
            f"\nExtracted {len(frames)} stack frames:\n" + "\n".join(f"  {frame}" for frame in frames)
            if frames
            else "\nNo stack frames detected!"
        )

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

        missing_functions = [func for func in expected_functions if func not in output]
        found_functions = [func for func in expected_functions if func in output]

        if missing_functions:
            self.fail(
                f"Missing {len(missing_functions)} of {len(expected_functions)} expected functions: {missing_functions}\n"
                f"Found functions: {found_functions}\n"
                f"This may indicate incomplete backtrace support.{frames_info}{diagnostic}"
            )

        # Step 4: Verify line numbers present (indicates debug symbols and full backtrace)
        line_number_patterns = [
            r":\d+",  # file.c:12
            r"line \d+",  # line 12
            r"#\d+.*:\d+",  # frame #0: file.c:12
        ]

        has_line_numbers = any(re.search(pattern, output) for pattern in line_number_patterns)
        if not has_line_numbers:
            self.fail(
                f"Stack trace should contain line numbers (patterns: {line_number_patterns})\n"
                f"No line numbers found - debug symbols may not be loaded{frames_info}{diagnostic}"
            )

        # Step 5: Verify source file references
        self.assertIn(
            "deep_stack.c", output, f"Stack trace should reference source file 'deep_stack.c'{frames_info}{diagnostic}"
        )

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

        found_python_errors = [err for err in python_error_indicators if err in output]
        if found_python_errors:
            self.fail(
                f"Python errors detected: {found_python_errors}\n"
                f"Python is bundled (status: {python_env['status']}) but errors occurred.\n"
                f"This indicates a configuration problem with the bundled Python.{frames_info}{diagnostic}"
            )

        # Step 7: Verify crash reason present
        crash_indicators = [
            "SIGSEGV",  # Linux/macOS signal
            "access violation",  # Windows
            "segmentation fault",
            "null pointer",
        ]

        has_crash_indicator = any(indicator.lower() in output.lower() for indicator in crash_indicators)
        if not has_crash_indicator:
            self.fail(
                f"Stack trace should indicate crash reason (expected one of: {crash_indicators})\n"
                f"No crash indicator found{frames_info}{diagnostic}"
            )

        # Print timing summary and function coverage on success
        total_time = compile_time + lldb_time
        print(
            f"\n✓ test_lldb_full_backtraces_with_python: compile={compile_time:.2f}s, lldb={lldb_time:.2f}s, total={total_time:.2f}s"
        )
        print(f"  Functions found: {len(found_functions)}/{len(expected_functions)}, Frames extracted: {len(frames)}")


if __name__ == "__main__":
    unittest.main()
