"""
Tests for lld linker selection and flag injection.

This module tests the platform-specific lld linker flag injection
behavior to ensure correct linker flags are used on each platform.
"""

import io
import os
import unittest
from unittest.mock import patch

from clang_tool_chain.linker.lld import _add_lld_linker_if_needed


class TestLLDLinkerSelection(unittest.TestCase):
    """Test cases for platform-specific lld linker flag injection."""

    def test_macos_uses_lld(self):
        """Test that macOS uses -fuse-ld=lld (clang driver dispatches to ld64.lld).

        Note: This test verifies that we use -fuse-ld=lld (not -fuse-ld=ld64.lld) because
        the clang driver does NOT recognize -fuse-ld=ld64.lld as a valid option.
        The driver only recognizes generic names like "lld", "gold", "bfd" and automatically
        dispatches to the appropriate linker binary (ld64.lld on Darwin, ld.lld on Linux).
        """
        args = ["main.cpp", "-o", "main"]
        result = _add_lld_linker_if_needed("darwin", args)
        # Should inject -fuse-ld=lld (NOT -fuse-ld=ld64.lld which is invalid)
        # The clang driver auto-dispatches to ld64.lld on Darwin targets
        self.assertEqual(result[0], "-fuse-ld=lld")
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
        """Test that macOS translates GNU ld flags to ld64.lld equivalents when LLD is forced.

        Note: This test verifies that GNU ld flags are translated to ld64.lld equivalents
        AND that we use -fuse-ld=lld (not -fuse-ld=ld64.lld). The clang driver does not
        recognize -fuse-ld=ld64.lld as a valid option, so we must use -fuse-ld=lld and
        let the driver dispatch to ld64.lld automatically on Darwin.
        """
        args = ["-Wl,--no-undefined", "main.cpp", "-o", "main"]
        result = _add_lld_linker_if_needed("darwin", args)
        # Should inject -fuse-ld=lld (NOT -fuse-ld=ld64.lld) and translate flags
        self.assertEqual(result[0], "-fuse-ld=lld")
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

    def test_macos_user_specified_ld64_lld_auto_converts_to_lld(self):
        """Test that macOS auto-converts -fuse-ld=ld64.lld to -fuse-ld=lld.

        Note: This test verifies that when the user specifies -fuse-ld=ld64.lld,
        it is automatically converted to -fuse-ld=lld because the clang driver
        does NOT recognize -fuse-ld=ld64.lld as a valid option. A warning is
        emitted to stderr to inform the user of this auto-conversion.
        """
        args = ["-fuse-ld=ld64.lld", "-Wl,--fatal-warnings", "main.cpp", "-o", "main"]
        result = _add_lld_linker_if_needed("darwin", args)
        # Should auto-convert -fuse-ld=ld64.lld to -fuse-ld=lld
        self.assertEqual(result[0], "-fuse-ld=lld")
        # Flags should still be translated
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

    def test_macos_ld64_lld_emits_warning(self):
        """Test that using -fuse-ld=ld64.lld on macOS emits a warning to stderr.

        Note: This test verifies that when the user specifies -fuse-ld=ld64.lld,
        a warning is emitted to stderr informing them that it has been
        auto-converted to -fuse-ld=lld. This is important because -fuse-ld=ld64.lld
        is NOT a valid clang driver option.
        """
        args = ["-fuse-ld=ld64.lld", "main.cpp", "-o", "main"]

        # Capture stderr
        captured_stderr = io.StringIO()
        with patch("sys.stderr", captured_stderr):
            result = _add_lld_linker_if_needed("darwin", args)

        # Verify the warning was emitted
        warning_output = captured_stderr.getvalue()
        self.assertIn("Warning", warning_output)
        self.assertIn("-fuse-ld=ld64.lld", warning_output)
        self.assertIn("Auto-converting", warning_output)
        self.assertIn("-fuse-ld=lld", warning_output)

        # Verify the conversion happened
        self.assertEqual(result[0], "-fuse-ld=lld")


if __name__ == "__main__":
    unittest.main()
