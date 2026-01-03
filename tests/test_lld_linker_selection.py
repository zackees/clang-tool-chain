"""
Tests for lld linker selection and flag injection.

This module tests the platform-specific lld linker flag injection
behavior to ensure correct linker flags are used on each platform.
"""

import unittest
from pathlib import Path

src_dir = Path(__file__).parent.parent / "src"
from clang_tool_chain.linker.lld import _add_lld_linker_if_needed  # noqa: E402


class TestLLDLinkerSelection(unittest.TestCase):
    """Test cases for platform-specific lld linker flag injection."""

    def test_macos_uses_ld64_lld(self):
        """Test that macOS (darwin) uses -fuse-ld=ld64.lld."""
        args = ["main.cpp", "-o", "main"]
        result = _add_lld_linker_if_needed("darwin", args)
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
        """Test that user-specified linker flags are respected."""
        args = ["-fuse-ld=gold", "main.cpp", "-o", "main"]
        result = _add_lld_linker_if_needed("linux", args)
        self.assertEqual(result, args)

        args = ["-fuse-ld=/usr/bin/ld", "main.cpp", "-o", "main"]
        result = _add_lld_linker_if_needed("darwin", args)
        self.assertEqual(result, args)

    def test_macos_flag_translation_applied(self):
        """Test that macOS also translates GNU ld flags."""
        args = ["-Wl,--no-undefined", "main.cpp", "-o", "main"]
        result = _add_lld_linker_if_needed("darwin", args)
        # Should have ld64.lld flag first, then translated flags
        self.assertEqual(result[0], "-fuse-ld=ld64.lld")
        self.assertEqual(result[1], "-Wl,-undefined,error")
        self.assertEqual(result[2:], ["main.cpp", "-o", "main"])

    def test_linux_no_flag_translation(self):
        """Test that Linux doesn't translate flags (not needed for ELF lld)."""
        args = ["-Wl,--no-undefined", "main.cpp", "-o", "main"]
        result = _add_lld_linker_if_needed("linux", args)
        # Should have lld flag first, but no translation
        self.assertEqual(result[0], "-fuse-ld=lld")
        self.assertEqual(result[1:], args)


if __name__ == "__main__":
    unittest.main()
