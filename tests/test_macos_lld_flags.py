"""
Tests for macOS ld64.lld linker flag translation.

This module tests the translation of GNU ld flags to ld64.lld equivalents
when using lld on macOS.
"""

import os
import unittest
from unittest.mock import patch

from clang_tool_chain.linker.lld import (  # noqa: E402
    _add_lld_linker_if_needed,
    _translate_linker_flags_for_macos_lld,
)


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


class TestMacOSLLDIntegration(unittest.TestCase):
    """Integration tests for macOS LLD linker behavior."""

    def test_macos_auto_injects_ld64_lld(self):
        """Test that macOS automatically injects -fuse-ld=lld (generic variant)."""
        args = ["main.cpp", "-o", "main"]
        result = _add_lld_linker_if_needed("darwin", args)
        self.assertEqual(result[0], "-fuse-ld=lld")

    def test_macos_flag_translation_with_auto_inject(self):
        """Test that flag translation happens when LLD is auto-injected on macOS."""
        args = ["-Wl,--no-undefined", "-Wl,--fatal-warnings", "main.cpp", "-o", "main"]
        result = _add_lld_linker_if_needed("darwin", args)
        # Should have lld flag first (generic variant)
        self.assertEqual(result[0], "-fuse-ld=lld")
        # Flags should be translated
        self.assertIn("-Wl,-undefined,error", result)
        self.assertIn("-Wl,-fatal_warnings", result)
        # Original GNU flags should not be present
        self.assertNotIn("-Wl,--no-undefined", result)
        self.assertNotIn("-Wl,--fatal-warnings", result)

    def test_macos_user_lld_triggers_flag_translation(self):
        """Test that user-specified -fuse-ld=lld triggers flag translation on macOS."""
        args = ["-fuse-ld=lld", "-Wl,--no-undefined", "main.cpp", "-o", "main"]
        result = _add_lld_linker_if_needed("darwin", args)
        # User's -fuse-ld=lld should be preserved
        self.assertEqual(result[0], "-fuse-ld=lld")
        # Flags should be translated
        self.assertEqual(result[1], "-Wl,-undefined,error")
        # No additional -fuse-ld flag should be added
        self.assertEqual(result.count("-fuse-ld=lld"), 1)
        self.assertNotIn("-fuse-ld=ld64.lld", result)

    def test_macos_user_ld64_lld_triggers_flag_translation(self):
        """Test that user-specified -fuse-ld=ld64.lld triggers flag translation on macOS."""
        args = ["-fuse-ld=ld64.lld", "-Wl,--fatal-warnings", "main.cpp", "-o", "main"]
        result = _add_lld_linker_if_needed("darwin", args)
        # User's -fuse-ld=ld64.lld should be preserved
        self.assertEqual(result[0], "-fuse-ld=ld64.lld")
        # Flags should be translated
        self.assertEqual(result[1], "-Wl,-fatal_warnings")
        # No additional -fuse-ld flag should be added
        self.assertEqual(result.count("-fuse-ld=ld64.lld"), 1)

    def test_macos_system_linker_env_skips_injection_and_translation(self):
        """Test that CLANG_TOOL_CHAIN_USE_SYSTEM_LD=1 skips LLD and flag translation."""
        with patch.dict(os.environ, {"CLANG_TOOL_CHAIN_USE_SYSTEM_LD": "1"}):
            args = ["-Wl,--no-undefined", "main.cpp", "-o", "main"]
            result = _add_lld_linker_if_needed("darwin", args)
            # Should not inject lld or translate flags
            self.assertEqual(result, args)
            self.assertNotIn("-fuse-ld=lld", result)
            self.assertNotIn("-fuse-ld=ld64.lld", result)
            # Original flag should remain untranslated
            self.assertIn("-Wl,--no-undefined", result)

    def test_linux_no_flag_translation(self):
        """Test that Linux does not translate GNU flags (ld.lld understands them natively)."""
        args = ["-Wl,--no-undefined", "-Wl,--fatal-warnings", "main.cpp", "-o", "main"]
        result = _add_lld_linker_if_needed("linux", args)
        # Should inject lld but not translate flags
        self.assertEqual(result[0], "-fuse-ld=lld")
        # Original GNU flags should remain unchanged
        self.assertIn("-Wl,--no-undefined", result)
        self.assertIn("-Wl,--fatal-warnings", result)

    def test_windows_not_affected(self):
        """Test that Windows behavior is not affected."""
        args = ["main.cpp", "-o", "main.exe"]
        result = _add_lld_linker_if_needed("win", args)
        # Should not inject any lld flag (handled separately in GNU ABI setup)
        self.assertEqual(result, args)


if __name__ == "__main__":
    unittest.main()
