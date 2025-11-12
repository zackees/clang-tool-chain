"""
Tests for macOS ld64.lld linker flag translation.

This module tests the translation of GNU ld flags to ld64.lld equivalents
when using lld on macOS.
"""

import sys
import unittest
from pathlib import Path

# Add src to path for imports
src_dir = Path(__file__).parent.parent / "src"
sys.path.insert(0, str(src_dir))

from clang_tool_chain.wrapper import _translate_linker_flags_for_macos_lld  # noqa: E402


class TestMacOSLLDFlagTranslation(unittest.TestCase):
    """Test cases for macOS ld64.lld flag translation."""

    def test_no_undefined_flag_in_wl(self):
        """Test translation of --no-undefined in -Wl, flags."""
        args = ["-Wl,--no-undefined"]
        result = _translate_linker_flags_for_macos_lld(args)
        self.assertEqual(result, ["-Wl,-undefined,error"])

    def test_no_undefined_flag_standalone(self):
        """Test translation of standalone --no-undefined flag."""
        args = ["--no-undefined"]
        result = _translate_linker_flags_for_macos_lld(args)
        self.assertEqual(result, ["-Wl,-undefined,error"])

    def test_multiple_flags_in_wl(self):
        """Test translation with multiple flags in -Wl,."""
        args = ["-Wl,--no-undefined,--fatal-warnings,-rpath,/usr/lib"]
        result = _translate_linker_flags_for_macos_lld(args)
        self.assertEqual(result, ["-Wl,-undefined,error,-fatal_warnings,-rpath,/usr/lib"])

    def test_fatal_warnings_flag(self):
        """Test translation of --fatal-warnings flag."""
        args = ["-Wl,--fatal-warnings"]
        result = _translate_linker_flags_for_macos_lld(args)
        self.assertEqual(result, ["-Wl,-fatal_warnings"])

    def test_mixed_translated_and_non_translated_flags(self):
        """Test mix of flags that need and don't need translation."""
        args = ["-O2", "-Wl,--no-undefined", "-std=c++17", "-Wl,-rpath,/lib"]
        result = _translate_linker_flags_for_macos_lld(args)
        self.assertEqual(result, ["-O2", "-Wl,-undefined,error", "-std=c++17", "-Wl,-rpath,/lib"])

    def test_no_translation_needed(self):
        """Test that args without GNU ld flags are unchanged."""
        args = ["-O2", "-std=c++17", "-Wall", "-o", "output"]
        result = _translate_linker_flags_for_macos_lld(args)
        self.assertEqual(result, args)

    def test_empty_args(self):
        """Test with empty argument list."""
        args = []
        result = _translate_linker_flags_for_macos_lld(args)
        self.assertEqual(result, [])

    def test_multiple_wl_flags(self):
        """Test with multiple -Wl, arguments."""
        args = ["-Wl,--no-undefined", "-Wl,--fatal-warnings", "-Wl,-L/usr/lib"]
        result = _translate_linker_flags_for_macos_lld(args)
        self.assertEqual(result, ["-Wl,-undefined,error", "-Wl,-fatal_warnings", "-Wl,-L/usr/lib"])

    def test_complex_compilation_command(self):
        """Test with a realistic compilation command."""
        args = [
            "-Iinclude",
            "-std=c++11",
            "-O0",
            "-g",
            "-Wall",
            "-Wextra",
            "-Wl,--no-undefined",
            "-o",
            "output.exe",
            "main.cpp",
        ]
        expected = [
            "-Iinclude",
            "-std=c++11",
            "-O0",
            "-g",
            "-Wall",
            "-Wextra",
            "-Wl,-undefined,error",
            "-o",
            "output.exe",
            "main.cpp",
        ]
        result = _translate_linker_flags_for_macos_lld(args)
        self.assertEqual(result, expected)


if __name__ == "__main__":
    unittest.main()
