"""
Tests for lld linker selection and flag injection.

This module tests the platform-specific lld linker flag injection
behavior to ensure correct linker flags are used on each platform.
"""

import os
import unittest
from unittest.mock import patch

from clang_tool_chain.linker.lld import _add_lld_linker_if_needed


class TestLLDLinkerSelection(unittest.TestCase):
    """Test cases for platform-specific lld linker flag injection."""

    def test_macos_uses_ld64_lld(self):
        """Test that macOS uses -fuse-ld=ld64.lld (explicit Mach-O linker)."""
        args = ["main.cpp", "-o", "main"]
        # Mock LLVM version check to return True (supports ld64.lld)
        with patch("clang_tool_chain.linker.lld._llvm_supports_ld64_lld_flag", return_value=True):
            result = _add_lld_linker_if_needed("darwin", args)
            # Should inject ld64.lld linker flag (explicit Mach-O variant)
            self.assertEqual(result[0], "-fuse-ld=ld64.lld")
            self.assertEqual(result[1:], args)

    def test_linux_uses_lld(self):
        """Test that Linux uses -fuse-ld=lld."""
        args = ["main.cpp", "-o", "main"]
        result = _add_lld_linker_if_needed("linux", args)
        self.assertEqual(result[0], "-fuse-ld=lld")
        self.assertEqual(result[1:], args)

    def test_windows_skips_injection(self):
        """Test that Windows doesn't inject lld flag (handled separately in GNU ABI setup)."""
        args = ["main.cpp", "-o", "main.exe"]
        result = _add_lld_linker_if_needed("win", args)
        self.assertEqual(result, args)

    def test_compile_only_skips_injection(self):
        """Test that compile-only operations don't inject linker flags."""
        args = ["-c", "main.cpp", "-o", "main.o"]
        result = _add_lld_linker_if_needed("darwin", args)
        self.assertEqual(result, args)

        result = _add_lld_linker_if_needed("linux", args)
        self.assertEqual(result, args)

    def test_user_specified_linker_skips_injection(self):
        """Test that user-specified linker flags are respected (no additional flag injected)."""
        args = ["-fuse-ld=gold", "main.cpp", "-o", "main"]
        result = _add_lld_linker_if_needed("linux", args)
        self.assertEqual(result, args)

        # macOS with non-LLD linker should not inject or translate
        args = ["-fuse-ld=/usr/bin/ld", "main.cpp", "-o", "main"]
        result = _add_lld_linker_if_needed("darwin", args)
        self.assertEqual(result, args)

    def test_macos_translates_gnu_flags_when_lld_forced(self):
        """Test that macOS translates GNU ld flags to ld64.lld equivalents when LLD is forced."""
        args = ["-Wl,--no-undefined", "main.cpp", "-o", "main"]
        # Mock LLVM version check to return True (supports ld64.lld)
        with patch("clang_tool_chain.linker.lld._llvm_supports_ld64_lld_flag", return_value=True):
            result = _add_lld_linker_if_needed("darwin", args)
            # Should inject ld64.lld (explicit Mach-O variant) and translate flags
            self.assertEqual(result[0], "-fuse-ld=ld64.lld")
            self.assertEqual(result[1], "-Wl,-undefined,error")
            self.assertEqual(result[2:], ["main.cpp", "-o", "main"])

    def test_macos_user_specified_lld_translates_flags(self):
        """Test that macOS translates flags when user explicitly specifies -fuse-ld=lld."""
        args = ["-fuse-ld=lld", "-Wl,--no-undefined", "main.cpp", "-o", "main"]
        result = _add_lld_linker_if_needed("darwin", args)
        # Should translate flags but not add another -fuse-ld flag
        self.assertEqual(result[0], "-fuse-ld=lld")
        self.assertEqual(result[1], "-Wl,-undefined,error")
        self.assertEqual(result[2:], ["main.cpp", "-o", "main"])

    def test_macos_user_specified_ld64_lld_translates_flags(self):
        """Test that macOS translates flags when user explicitly specifies -fuse-ld=ld64.lld."""
        args = ["-fuse-ld=ld64.lld", "-Wl,--fatal-warnings", "main.cpp", "-o", "main"]
        result = _add_lld_linker_if_needed("darwin", args)
        # Should translate flags but not add another -fuse-ld flag
        self.assertEqual(result[0], "-fuse-ld=ld64.lld")
        self.assertEqual(result[1], "-Wl,-fatal_warnings")
        self.assertEqual(result[2:], ["main.cpp", "-o", "main"])

    def test_linux_no_flag_translation(self):
        """Test that Linux doesn't translate flags (not needed for ELF lld)."""
        args = ["-Wl,--no-undefined", "main.cpp", "-o", "main"]
        result = _add_lld_linker_if_needed("linux", args)
        # Should have lld flag first, but no translation
        self.assertEqual(result[0], "-fuse-ld=lld")
        self.assertEqual(result[1:], args)

    def test_system_ld_env_var_skips_lld_on_macos(self):
        """Test that CLANG_TOOL_CHAIN_USE_SYSTEM_LD=1 skips LLD on macOS."""
        with patch.dict(os.environ, {"CLANG_TOOL_CHAIN_USE_SYSTEM_LD": "1"}):
            args = ["main.cpp", "-o", "main"]
            result = _add_lld_linker_if_needed("darwin", args)
            # Should not inject any linker flag - user wants system linker
            self.assertEqual(result, args)

    def test_system_ld_env_var_skips_lld_on_linux(self):
        """Test that CLANG_TOOL_CHAIN_USE_SYSTEM_LD=1 skips LLD on Linux."""
        with patch.dict(os.environ, {"CLANG_TOOL_CHAIN_USE_SYSTEM_LD": "1"}):
            args = ["main.cpp", "-o", "main"]
            result = _add_lld_linker_if_needed("linux", args)
            # Should not inject any linker flag - user wants system linker
            self.assertEqual(result, args)


if __name__ == "__main__":
    unittest.main()
