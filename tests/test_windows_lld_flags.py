"""
Tests for Windows lld-link linker flag translation.

This module tests the translation of GNU ld flags to lld-link (MSVC) equivalents
when using lld on Windows.
"""

import os
import shutil
import sys
import tempfile
import unittest
from unittest.mock import patch

from clang_tool_chain.linker.lld import (  # noqa: E402
    _translate_linker_flags_for_windows_lld,
)


class TestWindowsLLDFlagTranslation(unittest.TestCase):
    """Test cases for Windows lld-link flag translation (runs on all platforms)."""

    def test_allow_shlib_undefined_in_wl(self):
        """Test translation of --allow-shlib-undefined in -Wl, flags."""
        args = ["-Wl,--allow-shlib-undefined"]
        result = _translate_linker_flags_for_windows_lld(args)
        self.assertEqual(result, ["-Wl,/FORCE:UNRESOLVED"])

    def test_allow_shlib_undefined_standalone(self):
        """Test translation of standalone --allow-shlib-undefined flag."""
        args = ["--allow-shlib-undefined"]
        result = _translate_linker_flags_for_windows_lld(args)
        self.assertEqual(result, ["-Wl,/FORCE:UNRESOLVED"])

    def test_gc_sections_flag(self):
        """Test translation of --gc-sections flag."""
        args = ["-Wl,--gc-sections"]
        result = _translate_linker_flags_for_windows_lld(args)
        self.assertEqual(result, ["-Wl,/OPT:REF"])

    def test_no_gc_sections_flag(self):
        """Test translation of --no-gc-sections flag."""
        args = ["-Wl,--no-gc-sections"]
        result = _translate_linker_flags_for_windows_lld(args)
        self.assertEqual(result, ["-Wl,/OPT:NOREF"])

    def test_shared_flag(self):
        """Test translation of -shared flag."""
        args = ["-shared"]
        result = _translate_linker_flags_for_windows_lld(args)
        self.assertEqual(result, ["-Wl,/DLL"])

    def test_allow_multiple_definition_flag(self):
        """Test translation of --allow-multiple-definition flag."""
        args = ["-Wl,--allow-multiple-definition"]
        result = _translate_linker_flags_for_windows_lld(args)
        self.assertEqual(result, ["-Wl,/FORCE:MULTIPLE"])

    def test_no_undefined_removed(self):
        """Test that --no-undefined is removed (MSVC default behavior)."""
        args = ["-Wl,--no-undefined"]
        result = _translate_linker_flags_for_windows_lld(args)
        # The flag should be completely removed (MSVC disallows undefined by default)
        self.assertEqual(result, [])

    def test_no_undefined_removed_standalone(self):
        """Test that standalone --no-undefined is removed."""
        args = ["--no-undefined"]
        result = _translate_linker_flags_for_windows_lld(args)
        self.assertEqual(result, [])

    def test_multiple_flags_in_wl(self):
        """Test translation with multiple flags in -Wl,."""
        args = ["-Wl,--allow-shlib-undefined,--gc-sections"]
        result = _translate_linker_flags_for_windows_lld(args)
        self.assertEqual(result, ["-Wl,/FORCE:UNRESOLVED,/OPT:REF"])

    def test_multiple_flags_with_passthrough(self):
        """Test translation with mix of translated and passthrough flags."""
        args = ["-Wl,--allow-shlib-undefined,-rpath,/lib,--gc-sections"]
        result = _translate_linker_flags_for_windows_lld(args)
        # -rpath should pass through unchanged, others translated
        self.assertEqual(result, ["-Wl,/FORCE:UNRESOLVED,-rpath,/lib,/OPT:REF"])

    def test_msvc_flags_passthrough(self):
        """Test that MSVC flags pass through unchanged (backward compatibility)."""
        args = ["-Wl,/FORCE:UNRESOLVED"]
        result = _translate_linker_flags_for_windows_lld(args)
        # MSVC flags should remain unchanged
        self.assertEqual(result, ["-Wl,/FORCE:UNRESOLVED"])

    def test_mixed_msvc_and_gnu_flags(self):
        """Test mix of MSVC and GNU flags in same -Wl,."""
        args = ["-Wl,/FORCE:UNRESOLVED,--gc-sections"]
        result = _translate_linker_flags_for_windows_lld(args)
        # MSVC flag passes through, GNU flag translated
        self.assertEqual(result, ["-Wl,/FORCE:UNRESOLVED,/OPT:REF"])

    def test_mixed_translated_and_non_translated_flags(self):
        """Test mix of compiler flags and linker flags."""
        args = ["-O2", "-Wl,--allow-shlib-undefined", "-std=c++17", "-Wl,--gc-sections"]
        result = _translate_linker_flags_for_windows_lld(args)
        self.assertEqual(result, ["-O2", "-Wl,/FORCE:UNRESOLVED", "-std=c++17", "-Wl,/OPT:REF"])

    def test_no_translation_needed(self):
        """Test that args without GNU ld flags are unchanged."""
        args = ["-O2", "-std=c++17", "-Wall", "-o", "output.exe"]
        result = _translate_linker_flags_for_windows_lld(args)
        self.assertEqual(result, args)

    def test_empty_args(self):
        """Test with empty argument list."""
        args = []
        result = _translate_linker_flags_for_windows_lld(args)
        self.assertEqual(result, [])

    def test_multiple_wl_flags(self):
        """Test with multiple -Wl, arguments."""
        args = ["-Wl,--allow-shlib-undefined", "-Wl,--gc-sections", "-Wl,-rpath,/lib"]
        result = _translate_linker_flags_for_windows_lld(args)
        self.assertEqual(result, ["-Wl,/FORCE:UNRESOLVED", "-Wl,/OPT:REF", "-Wl,-rpath,/lib"])

    def test_warning_suppression(self):
        """Test that warning for translated flags can be suppressed via env var."""
        with patch.dict(os.environ, {"CLANG_TOOL_CHAIN_NO_LINKER_COMPAT_NOTE": "1"}):
            args = ["-Wl,--allow-shlib-undefined"]
            # This should not print a warning (we can't easily test stderr output here,
            # but the env var should prevent the warning from being printed)
            result = _translate_linker_flags_for_windows_lld(args)
            self.assertEqual(result, ["-Wl,/FORCE:UNRESOLVED"])

    def test_warning_suppression_via_category(self):
        """Test that warning can be suppressed via LINKER_NOTE category."""
        with patch.dict(os.environ, {"CLANG_TOOL_CHAIN_NO_LINKER_NOTE": "1"}):
            args = ["-Wl,--gc-sections"]
            result = _translate_linker_flags_for_windows_lld(args)
            self.assertEqual(result, ["-Wl,/OPT:REF"])

    def test_warning_suppression_via_auto(self):
        """Test that warning can be suppressed via NO_AUTO."""
        with patch.dict(os.environ, {"CLANG_TOOL_CHAIN_NO_AUTO": "1"}):
            args = ["-shared"]
            result = _translate_linker_flags_for_windows_lld(args)
            self.assertEqual(result, ["-Wl,/DLL"])

    def test_removed_flag_with_other_flags(self):
        """Test that removed flags don't affect other flags."""
        args = ["-Wl,--no-undefined,--allow-shlib-undefined,--gc-sections"]
        result = _translate_linker_flags_for_windows_lld(args)
        # --no-undefined should be removed, others translated
        self.assertEqual(result, ["-Wl,/FORCE:UNRESOLVED,/OPT:REF"])

    def test_complex_compilation_command(self):
        """Test with a realistic compilation command."""
        args = [
            "-Iinclude",
            "-std=c++11",
            "-O2",
            "-g",
            "-Wall",
            "-Wextra",
            "-shared",
            "-Wl,--allow-shlib-undefined",
            "-o",
            "output.dll",
            "main.cpp",
        ]
        expected = [
            "-Iinclude",
            "-std=c++11",
            "-O2",
            "-g",
            "-Wall",
            "-Wextra",
            "-Wl,/DLL",
            "-Wl,/FORCE:UNRESOLVED",
            "-o",
            "output.dll",
            "main.cpp",
        ]
        result = _translate_linker_flags_for_windows_lld(args)
        self.assertEqual(result, expected)


@unittest.skipUnless(sys.platform == "win32", "Windows-only integration tests")
class TestWindowsLLDFlagIntegration(unittest.TestCase):
    """Integration tests for Windows LLD linker behavior (Windows only)."""

    def setUp(self):
        """Set up test environment."""
        # Create temporary directory for test files
        self.temp_dir = tempfile.mkdtemp()

        # Check if toolchain is accessible
        try:
            import subprocess

            result = subprocess.run(
                ["clang-tool-chain-cpp", "--version"],
                capture_output=True,
                text=True,
                timeout=10,
            )
            if result.returncode != 0:
                self.skipTest("clang-tool-chain-cpp not accessible")
        except (FileNotFoundError, subprocess.TimeoutExpired):
            self.skipTest("clang-tool-chain-cpp not available")

    def tearDown(self):
        """Clean up test environment."""
        # Remove temporary directory
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)

    def test_allow_shlib_undefined_compilation(self):
        """Test building DLL with undefined symbols using GNU flag."""
        import subprocess

        # Create test source file
        test_file = os.path.join(self.temp_dir, "test.cpp")
        with open(test_file, "w") as f:
            f.write('extern "C" __declspec(dllexport) int test() { return 42; }\n')

        # Build DLL with GNU flag
        output_file = os.path.join(self.temp_dir, "test.dll")
        result = subprocess.run(
            [
                "clang-tool-chain-cpp",
                "-shared",
                "-Wl,--allow-shlib-undefined",
                test_file,
                "-o",
                output_file,
            ],
            capture_output=True,
            text=True,
        )

        # Should succeed
        self.assertEqual(result.returncode, 0, f"Build failed: {result.stderr}")
        # Output should exist
        self.assertTrue(os.path.exists(output_file))

    def test_gc_sections_flag_compilation(self):
        """Test that --gc-sections flag works in actual build."""
        import subprocess

        # Create test source file
        test_file = os.path.join(self.temp_dir, "test.cpp")
        with open(test_file, "w") as f:
            f.write(
                """
int used_function() { return 42; }
int unused_function() { return 0; }
int main() { return used_function(); }
"""
            )

        # Build with GNU flag
        output_file = os.path.join(self.temp_dir, "test.exe")
        result = subprocess.run(
            [
                "clang-tool-chain-cpp",
                "-Wl,--gc-sections",
                test_file,
                "-o",
                output_file,
            ],
            capture_output=True,
            text=True,
        )

        # Should succeed
        self.assertEqual(result.returncode, 0, f"Build failed: {result.stderr}")
        # Output should exist
        self.assertTrue(os.path.exists(output_file))

    def test_comprehensive_gnu_flags_with_verbose(self):
        """PRIMARY VERIFICATION TEST: Verify GNU flags work correctly with GNU ABI (default).

        This test:
        1. Uses -shared (supported) and --allow-shlib-undefined (not supported)
        2. Enables -v verbose mode to see linker invocation
        3. Verifies -shared passes through, --allow-shlib-undefined is removed
        4. Verifies removal warnings emitted to stderr
        5. Verifies build succeeds with ld.lld MinGW mode
        """
        import subprocess

        # Create test source file
        test_file = os.path.join(self.temp_dir, "test.cpp")
        with open(test_file, "w") as f:
            f.write('extern "C" __declspec(dllexport) int test() { return 42; }\n')

        # Build DLL with verbose output and GNU flags
        # Using GNU ABI (default), so flags should be processed for ld.lld MinGW mode
        output_file = os.path.join(self.temp_dir, "test.dll")
        result = subprocess.run(
            [
                "clang-tool-chain-cpp",
                "-v",  # Verbose to see linker invocation
                "-shared",  # Supported by ld.lld MinGW
                "-Wl,--allow-shlib-undefined,--gc-sections",  # --allow-shlib-undefined removed, --gc-sections kept
                test_file,
                "-o",
                output_file,
            ],
            capture_output=True,
            text=True,
        )

        # Should succeed
        self.assertEqual(result.returncode, 0, f"Build failed: {result.stderr}")

        # Verify output exists
        self.assertTrue(os.path.exists(output_file))

        # Verify GNU flags appear in verbose output (combined stdout/stderr)
        verbose_output = result.stdout + result.stderr

        # Check for GNU-style linker invocation (ld.lld in MinGW mode)
        self.assertIn("ld.lld", verbose_output, "Expected ld.lld linker")

        # Extract just the linker command line from verbose output
        # It starts with "ld.lld" and ends before the next line
        import re

        # Extract linker command from verbose output
        linker_cmd_match = re.search(r'"[^"]*ld\.lld"[^\n]*', verbose_output)
        self.assertIsNotNone(linker_cmd_match, "Could not find ld.lld command line in output")
        assert linker_cmd_match is not None  # Type guard for pyright
        linker_cmd = linker_cmd_match.group(0)

        # Check that supported flags appear in linker command
        self.assertIn("--shared", linker_cmd, "Expected --shared flag (supported)")
        self.assertIn("--gc-sections", linker_cmd, "Expected --gc-sections flag (supported)")

        # --allow-shlib-undefined should NOT appear in linker command (removed)
        self.assertNotIn("--allow-shlib-undefined", linker_cmd, "--allow-shlib-undefined should be removed")

        # Verify removal warning was emitted (unless suppressed)
        if "CLANG_TOOL_CHAIN_NO_LINKER_COMPAT_NOTE" not in os.environ:
            self.assertIn(
                "removed GNU linker flags not supported by ld.lld MinGW mode",
                result.stderr,
                "Expected removal warning in stderr",
            )

    def test_no_undefined_flag_removed(self):
        """Test that --no-undefined is removed for GNU ABI (ld.lld MinGW mode)."""
        import subprocess

        # Create test source file
        test_file = os.path.join(self.temp_dir, "test.cpp")
        with open(test_file, "w") as f:
            f.write("int main() { return 0; }\n")

        # Build with --no-undefined (should be removed)
        output_file = os.path.join(self.temp_dir, "test.exe")
        result = subprocess.run(
            [
                "clang-tool-chain-cpp",
                "-Wl,--no-undefined",
                test_file,
                "-o",
                output_file,
            ],
            capture_output=True,
            text=True,
        )

        # Should succeed
        self.assertEqual(result.returncode, 0, f"Build failed: {result.stderr}")
        # Output should exist
        self.assertTrue(os.path.exists(output_file))

        # Verify warning mentions flag was removed (GNU mode message)
        if "CLANG_TOOL_CHAIN_NO_LINKER_COMPAT_NOTE" not in os.environ:
            self.assertIn("removed, not supported", result.stderr)


if __name__ == "__main__":
    unittest.main()
