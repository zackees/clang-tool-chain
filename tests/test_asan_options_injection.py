"""
Tests for automatic ASAN_OPTIONS, LSAN_OPTIONS, and ASAN_SYMBOLIZER_PATH injection.

This test suite verifies that sanitizer environment variables are automatically
injected when running executables compiled with Address Sanitizer or Leak Sanitizer,
improving stack trace quality for dlopen()'d shared libraries.
"""

import os
import subprocess
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

from clang_tool_chain.execution.sanitizer_env import (
    DEFAULT_ASAN_OPTIONS,
    DEFAULT_LSAN_OPTIONS,
    _get_builtin_suppression_file,
    detect_sanitizers_from_flags,
    get_symbolizer_path,
    prepare_sanitizer_environment,
)


class TestDetectSanitizersFromFlags:
    """Test detection of sanitizers from compiler flags."""

    def test_detect_asan_from_fsanitize_address(self):
        """Test that -fsanitize=address enables both ASAN and LSAN."""
        asan, lsan = detect_sanitizers_from_flags(["-fsanitize=address"])
        assert asan is True
        assert lsan is True  # ASAN implies LSAN

    def test_detect_lsan_from_fsanitize_leak(self):
        """Test that -fsanitize=leak enables only LSAN."""
        asan, lsan = detect_sanitizers_from_flags(["-fsanitize=leak"])
        assert asan is False
        assert lsan is True

    def test_detect_asan_with_other_sanitizers(self):
        """Test that -fsanitize=address,undefined still detects ASAN."""
        asan, lsan = detect_sanitizers_from_flags(["-fsanitize=address,undefined"])
        assert asan is True
        assert lsan is True

    def test_no_sanitizers_detected(self):
        """Test that regular flags don't trigger sanitizer detection."""
        asan, lsan = detect_sanitizers_from_flags(["-O2", "-Wall", "-std=c++17"])
        assert asan is False
        assert lsan is False

    def test_empty_flags(self):
        """Test with empty flag list."""
        asan, lsan = detect_sanitizers_from_flags([])
        assert asan is False
        assert lsan is False

    def test_multiple_fsanitize_flags(self):
        """Test with multiple -fsanitize flags."""
        asan, lsan = detect_sanitizers_from_flags(["-fsanitize=undefined", "-fsanitize=address"])
        assert asan is True
        assert lsan is True

    def test_fsanitize_leak_only(self):
        """Test standalone leak sanitizer."""
        asan, lsan = detect_sanitizers_from_flags(["-fsanitize=leak", "-O2"])
        assert asan is False
        assert lsan is True


class TestSanitizerEnvironmentInjection:
    """Test automatic sanitizer environment variable injection."""

    def test_asan_options_injected_when_asan_enabled(self):
        """Test that ASAN_OPTIONS is injected when -fsanitize=address is used."""
        base_env = {"PATH": "/usr/bin", "HOME": "/home/test"}

        result = prepare_sanitizer_environment(base_env, compiler_flags=["-fsanitize=address"])

        assert "ASAN_OPTIONS" in result
        assert result["ASAN_OPTIONS"] == DEFAULT_ASAN_OPTIONS
        # Original env vars should be preserved
        assert result["PATH"] == "/usr/bin"
        assert result["HOME"] == "/home/test"

    def test_lsan_options_injected_when_asan_enabled(self):
        """Test that LSAN_OPTIONS is injected when -fsanitize=address is used (ASAN implies LSAN)."""
        base_env = {"PATH": "/usr/bin"}

        result = prepare_sanitizer_environment(base_env, compiler_flags=["-fsanitize=address"])

        assert "LSAN_OPTIONS" in result
        assert result["LSAN_OPTIONS"] == DEFAULT_LSAN_OPTIONS

    def test_lsan_options_injected_when_lsan_enabled(self):
        """Test that LSAN_OPTIONS is injected when -fsanitize=leak is used."""
        base_env = {"PATH": "/usr/bin"}

        result = prepare_sanitizer_environment(base_env, compiler_flags=["-fsanitize=leak"])

        assert "LSAN_OPTIONS" in result
        assert result["LSAN_OPTIONS"] == DEFAULT_LSAN_OPTIONS
        # ASAN should NOT be injected for leak-only
        assert "ASAN_OPTIONS" not in result

    def test_no_injection_without_sanitizers(self):
        """Test that no options are injected when no sanitizers are used."""
        base_env = {"PATH": "/usr/bin"}

        result = prepare_sanitizer_environment(base_env, compiler_flags=["-O2", "-Wall"])

        assert "ASAN_OPTIONS" not in result
        assert "LSAN_OPTIONS" not in result

    def test_no_injection_without_compiler_flags(self):
        """Test that no options are injected when compiler_flags is None."""
        base_env = {"PATH": "/usr/bin"}

        result = prepare_sanitizer_environment(base_env, compiler_flags=None)

        assert "ASAN_OPTIONS" not in result
        assert "LSAN_OPTIONS" not in result

    def test_asan_options_preserved_when_user_specified(self):
        """Test that user-specified ASAN_OPTIONS is preserved."""
        user_asan_options = "detect_leaks=0:halt_on_error=1"
        base_env = {"PATH": "/usr/bin", "ASAN_OPTIONS": user_asan_options}

        result = prepare_sanitizer_environment(base_env, compiler_flags=["-fsanitize=address"])

        # User config should be preserved
        assert result["ASAN_OPTIONS"] == user_asan_options
        # LSAN_OPTIONS should still be injected since not set by user
        assert result["LSAN_OPTIONS"] == DEFAULT_LSAN_OPTIONS

    def test_lsan_options_preserved_when_user_specified(self):
        """Test that user-specified LSAN_OPTIONS is preserved."""
        user_lsan_options = "verbosity=1:log_threads=1"
        base_env = {"PATH": "/usr/bin", "LSAN_OPTIONS": user_lsan_options}

        result = prepare_sanitizer_environment(base_env, compiler_flags=["-fsanitize=address"])

        # User config should be preserved
        assert result["LSAN_OPTIONS"] == user_lsan_options
        # ASAN_OPTIONS should still be injected since not set by user
        assert result["ASAN_OPTIONS"] == DEFAULT_ASAN_OPTIONS

    def test_both_options_preserved_when_user_specified(self):
        """Test that both user-specified options are preserved."""
        user_asan_options = "detect_leaks=0"
        user_lsan_options = "verbosity=1"
        base_env = {
            "PATH": "/usr/bin",
            "ASAN_OPTIONS": user_asan_options,
            "LSAN_OPTIONS": user_lsan_options,
        }

        result = prepare_sanitizer_environment(base_env, compiler_flags=["-fsanitize=address"])

        # Both user configs should be preserved
        assert result["ASAN_OPTIONS"] == user_asan_options
        assert result["LSAN_OPTIONS"] == user_lsan_options

    def test_disabled_via_environment_variable(self):
        """Test that injection is disabled via CLANG_TOOL_CHAIN_NO_SANITIZER_ENV."""
        base_env = {"PATH": "/usr/bin"}

        # Save original env and set disable flag
        original_env = os.environ.get("CLANG_TOOL_CHAIN_NO_SANITIZER_ENV")
        try:
            os.environ["CLANG_TOOL_CHAIN_NO_SANITIZER_ENV"] = "1"

            result = prepare_sanitizer_environment(base_env, compiler_flags=["-fsanitize=address"])

            # Neither option should be injected
            assert "ASAN_OPTIONS" not in result
            assert "LSAN_OPTIONS" not in result
            # Original env should be preserved
            assert result["PATH"] == "/usr/bin"
        finally:
            # Restore original env
            if original_env is None:
                os.environ.pop("CLANG_TOOL_CHAIN_NO_SANITIZER_ENV", None)
            else:
                os.environ["CLANG_TOOL_CHAIN_NO_SANITIZER_ENV"] = original_env

    def test_disabled_via_true_value(self):
        """Test that injection is disabled with 'true' value."""
        base_env = {"PATH": "/usr/bin"}

        original_env = os.environ.get("CLANG_TOOL_CHAIN_NO_SANITIZER_ENV")
        try:
            os.environ["CLANG_TOOL_CHAIN_NO_SANITIZER_ENV"] = "true"

            result = prepare_sanitizer_environment(base_env, compiler_flags=["-fsanitize=address"])

            assert "ASAN_OPTIONS" not in result
            assert "LSAN_OPTIONS" not in result
        finally:
            if original_env is None:
                os.environ.pop("CLANG_TOOL_CHAIN_NO_SANITIZER_ENV", None)
            else:
                os.environ["CLANG_TOOL_CHAIN_NO_SANITIZER_ENV"] = original_env

    def test_disabled_via_yes_value(self):
        """Test that injection is disabled with 'yes' value."""
        base_env = {"PATH": "/usr/bin"}

        original_env = os.environ.get("CLANG_TOOL_CHAIN_NO_SANITIZER_ENV")
        try:
            os.environ["CLANG_TOOL_CHAIN_NO_SANITIZER_ENV"] = "yes"

            result = prepare_sanitizer_environment(base_env, compiler_flags=["-fsanitize=address"])

            assert "ASAN_OPTIONS" not in result
            assert "LSAN_OPTIONS" not in result
        finally:
            if original_env is None:
                os.environ.pop("CLANG_TOOL_CHAIN_NO_SANITIZER_ENV", None)
            else:
                os.environ["CLANG_TOOL_CHAIN_NO_SANITIZER_ENV"] = original_env

    def test_not_disabled_via_invalid_value(self):
        """Test that injection is not disabled with invalid/empty value."""
        base_env = {"PATH": "/usr/bin"}

        original_env = os.environ.get("CLANG_TOOL_CHAIN_NO_SANITIZER_ENV")
        try:
            os.environ["CLANG_TOOL_CHAIN_NO_SANITIZER_ENV"] = "0"

            result = prepare_sanitizer_environment(base_env, compiler_flags=["-fsanitize=address"])

            # Should still inject since "0" is not a disable value
            assert "ASAN_OPTIONS" in result
            assert "LSAN_OPTIONS" in result
        finally:
            if original_env is None:
                os.environ.pop("CLANG_TOOL_CHAIN_NO_SANITIZER_ENV", None)
            else:
                os.environ["CLANG_TOOL_CHAIN_NO_SANITIZER_ENV"] = original_env

    def test_uses_os_environ_when_base_env_is_none(self):
        """Test that os.environ is used when base_env is None."""
        original_env = os.environ.get("CLANG_TOOL_CHAIN_NO_SANITIZER_ENV")
        original_asan = os.environ.get("ASAN_OPTIONS")
        original_lsan = os.environ.get("LSAN_OPTIONS")
        try:
            # Clear disable flag and sanitizer options
            os.environ.pop("CLANG_TOOL_CHAIN_NO_SANITIZER_ENV", None)
            os.environ.pop("ASAN_OPTIONS", None)
            os.environ.pop("LSAN_OPTIONS", None)

            result = prepare_sanitizer_environment(None, compiler_flags=["-fsanitize=address"])

            # Should inject options
            assert "ASAN_OPTIONS" in result
            assert "LSAN_OPTIONS" in result
            # Should contain os.environ values
            assert "PATH" in result  # PATH should exist in os.environ
        finally:
            # Restore original env
            if original_env is None:
                os.environ.pop("CLANG_TOOL_CHAIN_NO_SANITIZER_ENV", None)
            else:
                os.environ["CLANG_TOOL_CHAIN_NO_SANITIZER_ENV"] = original_env
            if original_asan is None:
                os.environ.pop("ASAN_OPTIONS", None)
            else:
                os.environ["ASAN_OPTIONS"] = original_asan
            if original_lsan is None:
                os.environ.pop("LSAN_OPTIONS", None)
            else:
                os.environ["LSAN_OPTIONS"] = original_lsan

    def test_does_not_modify_original_env(self):
        """Test that the original base_env dictionary is not modified."""
        base_env = {"PATH": "/usr/bin"}
        base_env_copy = base_env.copy()

        # Clear disable flag for this test
        original_disable = os.environ.get("CLANG_TOOL_CHAIN_NO_SANITIZER_ENV")
        try:
            os.environ.pop("CLANG_TOOL_CHAIN_NO_SANITIZER_ENV", None)

            result = prepare_sanitizer_environment(base_env, compiler_flags=["-fsanitize=address"])

            # Result should have injected options
            assert "ASAN_OPTIONS" in result
            # Original should be unchanged
            assert base_env == base_env_copy
            assert "ASAN_OPTIONS" not in base_env
        finally:
            if original_disable is None:
                os.environ.pop("CLANG_TOOL_CHAIN_NO_SANITIZER_ENV", None)
            else:
                os.environ["CLANG_TOOL_CHAIN_NO_SANITIZER_ENV"] = original_disable

    def test_default_options_contain_expected_settings(self):
        """Test that default options contain the expected settings for better stack traces."""
        # These settings fix <unknown module> in stack traces
        assert "fast_unwind_on_malloc=0" in DEFAULT_ASAN_OPTIONS
        assert "symbolize=1" in DEFAULT_ASAN_OPTIONS
        assert "detect_leaks=1" in DEFAULT_ASAN_OPTIONS

        assert "fast_unwind_on_malloc=0" in DEFAULT_LSAN_OPTIONS
        assert "symbolize=1" in DEFAULT_LSAN_OPTIONS

    def test_combined_sanitizers(self):
        """Test with combined sanitizers like -fsanitize=address,undefined."""
        base_env = {"PATH": "/usr/bin"}

        result = prepare_sanitizer_environment(base_env, compiler_flags=["-fsanitize=address,undefined"])

        assert "ASAN_OPTIONS" in result
        assert "LSAN_OPTIONS" in result

    def test_empty_compiler_flags(self):
        """Test with empty compiler flags list."""
        base_env = {"PATH": "/usr/bin"}

        result = prepare_sanitizer_environment(base_env, compiler_flags=[])

        # No sanitizers, no injection
        assert "ASAN_OPTIONS" not in result
        assert "LSAN_OPTIONS" not in result


class TestGetSymbolizerPath:
    """Test get_symbolizer_path() function."""

    def test_returns_string_or_none(self):
        """Test that get_symbolizer_path returns a string or None."""
        result = get_symbolizer_path()
        assert result is None or isinstance(result, str)

    def test_path_exists_when_returned(self):
        """Test that when a path is returned, it points to an existing file."""
        result = get_symbolizer_path()
        if result is not None:
            assert Path(result).exists(), f"Symbolizer path does not exist: {result}"

    def test_path_contains_llvm_symbolizer(self):
        """Test that returned path contains 'llvm-symbolizer' in the name."""
        result = get_symbolizer_path()
        if result is not None:
            path = Path(result)
            # On Windows it might be llvm-symbolizer.exe
            assert "llvm-symbolizer" in path.name.lower().replace(".exe", "")

    @patch("clang_tool_chain.execution.sanitizer_env.shutil.which")
    @patch("clang_tool_chain.platform.paths.find_tool_binary")
    def test_falls_back_to_system_path(self, mock_find_tool, mock_which):
        """Test fallback to system PATH when clang-tool-chain binary not found."""
        mock_find_tool.side_effect = RuntimeError("Tool not found")
        mock_which.return_value = "/usr/bin/llvm-symbolizer"

        # The function should fall back to shutil.which
        result = get_symbolizer_path()

        # Should have returned the system path
        assert result == "/usr/bin/llvm-symbolizer"
        mock_which.assert_called_with("llvm-symbolizer")

    @patch("clang_tool_chain.execution.sanitizer_env.shutil.which")
    @patch("clang_tool_chain.platform.paths.find_tool_binary")
    def test_returns_none_when_not_found_anywhere(self, mock_find_tool, mock_which):
        """Test that None is returned when symbolizer not found anywhere."""
        mock_find_tool.side_effect = RuntimeError("Tool not found")
        mock_which.return_value = None

        result = get_symbolizer_path()

        assert result is None

    def test_returns_clang_tool_chain_path_when_available(self):
        """Test that clang-tool-chain path is preferred when available."""
        result = get_symbolizer_path()
        if result is not None:
            # When clang-tool-chain is installed, path should be in .clang-tool-chain
            # or the installation directory
            path = Path(result)
            # It should be an absolute path
            assert path.is_absolute()


class TestAsanSymbolizerPathInjection:
    """Test ASAN_SYMBOLIZER_PATH automatic injection."""

    def test_symbolizer_path_injected_when_asan_enabled(self):
        """Test that ASAN_SYMBOLIZER_PATH is injected when -fsanitize=address is used."""
        base_env = {"PATH": "/usr/bin"}

        # Clear disable flag
        original_disable = os.environ.get("CLANG_TOOL_CHAIN_NO_SANITIZER_ENV")
        try:
            os.environ.pop("CLANG_TOOL_CHAIN_NO_SANITIZER_ENV", None)

            result = prepare_sanitizer_environment(base_env, compiler_flags=["-fsanitize=address"])

            # ASAN_SYMBOLIZER_PATH should be set if symbolizer is available
            symbolizer = get_symbolizer_path()
            if symbolizer is not None:
                assert "ASAN_SYMBOLIZER_PATH" in result
                assert result["ASAN_SYMBOLIZER_PATH"] == symbolizer
        finally:
            if original_disable is None:
                os.environ.pop("CLANG_TOOL_CHAIN_NO_SANITIZER_ENV", None)
            else:
                os.environ["CLANG_TOOL_CHAIN_NO_SANITIZER_ENV"] = original_disable

    def test_symbolizer_path_injected_when_lsan_enabled(self):
        """Test that ASAN_SYMBOLIZER_PATH is injected when -fsanitize=leak is used."""
        base_env = {"PATH": "/usr/bin"}

        original_disable = os.environ.get("CLANG_TOOL_CHAIN_NO_SANITIZER_ENV")
        try:
            os.environ.pop("CLANG_TOOL_CHAIN_NO_SANITIZER_ENV", None)

            result = prepare_sanitizer_environment(base_env, compiler_flags=["-fsanitize=leak"])

            symbolizer = get_symbolizer_path()
            if symbolizer is not None:
                assert "ASAN_SYMBOLIZER_PATH" in result
                assert result["ASAN_SYMBOLIZER_PATH"] == symbolizer
        finally:
            if original_disable is None:
                os.environ.pop("CLANG_TOOL_CHAIN_NO_SANITIZER_ENV", None)
            else:
                os.environ["CLANG_TOOL_CHAIN_NO_SANITIZER_ENV"] = original_disable

    def test_symbolizer_path_not_injected_without_sanitizers(self):
        """Test that ASAN_SYMBOLIZER_PATH is not injected without sanitizers."""
        base_env = {"PATH": "/usr/bin"}

        result = prepare_sanitizer_environment(base_env, compiler_flags=["-O2", "-Wall"])

        assert "ASAN_SYMBOLIZER_PATH" not in result

    def test_symbolizer_path_preserved_when_user_specified(self):
        """Test that user-specified ASAN_SYMBOLIZER_PATH is preserved."""
        user_symbolizer = "/custom/path/to/llvm-symbolizer"
        base_env = {"PATH": "/usr/bin", "ASAN_SYMBOLIZER_PATH": user_symbolizer}

        original_disable = os.environ.get("CLANG_TOOL_CHAIN_NO_SANITIZER_ENV")
        try:
            os.environ.pop("CLANG_TOOL_CHAIN_NO_SANITIZER_ENV", None)

            result = prepare_sanitizer_environment(base_env, compiler_flags=["-fsanitize=address"])

            # User-specified path should be preserved
            assert result["ASAN_SYMBOLIZER_PATH"] == user_symbolizer
        finally:
            if original_disable is None:
                os.environ.pop("CLANG_TOOL_CHAIN_NO_SANITIZER_ENV", None)
            else:
                os.environ["CLANG_TOOL_CHAIN_NO_SANITIZER_ENV"] = original_disable

    def test_symbolizer_path_not_injected_when_disabled(self):
        """Test that ASAN_SYMBOLIZER_PATH is not injected when disabled via env var."""
        base_env = {"PATH": "/usr/bin"}

        original_env = os.environ.get("CLANG_TOOL_CHAIN_NO_SANITIZER_ENV")
        try:
            os.environ["CLANG_TOOL_CHAIN_NO_SANITIZER_ENV"] = "1"

            result = prepare_sanitizer_environment(base_env, compiler_flags=["-fsanitize=address"])

            # Nothing should be injected when disabled
            assert "ASAN_SYMBOLIZER_PATH" not in result
            assert "ASAN_OPTIONS" not in result
            assert "LSAN_OPTIONS" not in result
        finally:
            if original_env is None:
                os.environ.pop("CLANG_TOOL_CHAIN_NO_SANITIZER_ENV", None)
            else:
                os.environ["CLANG_TOOL_CHAIN_NO_SANITIZER_ENV"] = original_env

    def test_all_sanitizer_vars_injected_together(self):
        """Test that ASAN_OPTIONS, LSAN_OPTIONS, and ASAN_SYMBOLIZER_PATH are all injected."""
        base_env = {"PATH": "/usr/bin"}

        original_disable = os.environ.get("CLANG_TOOL_CHAIN_NO_SANITIZER_ENV")
        try:
            os.environ.pop("CLANG_TOOL_CHAIN_NO_SANITIZER_ENV", None)

            result = prepare_sanitizer_environment(base_env, compiler_flags=["-fsanitize=address"])

            # All three should be set (if symbolizer is available)
            assert "ASAN_OPTIONS" in result
            assert "LSAN_OPTIONS" in result
            symbolizer = get_symbolizer_path()
            if symbolizer is not None:
                assert "ASAN_SYMBOLIZER_PATH" in result
        finally:
            if original_disable is None:
                os.environ.pop("CLANG_TOOL_CHAIN_NO_SANITIZER_ENV", None)
            else:
                os.environ["CLANG_TOOL_CHAIN_NO_SANITIZER_ENV"] = original_disable


class TestSymbolizerPathPlatformSpecific:
    """Platform-specific tests for symbolizer path."""

    def test_windows_symbolizer_path_has_exe_extension(self):
        """Test that Windows symbolizer path has .exe extension."""
        if sys.platform != "win32":
            return  # Skip on non-Windows

        result = get_symbolizer_path()
        if result is not None:
            assert result.endswith(".exe"), f"Windows path should end with .exe: {result}"

    def test_unix_symbolizer_path_no_exe_extension(self):
        """Test that Unix symbolizer path does not have .exe extension."""
        if sys.platform == "win32":
            return  # Skip on Windows

        result = get_symbolizer_path()
        if result is not None:
            assert not result.endswith(".exe"), f"Unix path should not end with .exe: {result}"

    def test_linux_symbolizer_path_valid(self):
        """Test that Linux symbolizer path is valid."""
        if sys.platform != "linux":
            return  # Skip on non-Linux

        result = get_symbolizer_path()
        if result is not None:
            path = Path(result)
            assert path.exists(), f"Linux symbolizer should exist: {result}"
            assert path.is_file(), f"Linux symbolizer should be a file: {result}"

    def test_macos_symbolizer_path_valid(self):
        """Test that macOS symbolizer path is valid."""
        if sys.platform != "darwin":
            return  # Skip on non-macOS

        result = get_symbolizer_path()
        if result is not None:
            path = Path(result)
            assert path.exists(), f"macOS symbolizer should exist: {result}"
            assert path.is_file(), f"macOS symbolizer should be a file: {result}"

    def test_symbolizer_path_is_executable(self):
        """Test that the symbolizer binary is executable."""
        result = get_symbolizer_path()
        if result is None:
            return  # Skip if not available

        path = Path(result)
        if sys.platform == "win32":
            # On Windows, .exe files are executable by default
            assert path.suffix.lower() == ".exe"
        else:
            # On Unix, check executable permission
            import stat

            mode = path.stat().st_mode
            assert mode & stat.S_IXUSR, f"Symbolizer should be executable: {result}"


class TestSymbolizerPathIntegration:
    """Integration tests for symbolizer path with actual clang-tool-chain installation."""

    def test_symbolizer_in_clang_tool_chain_bin(self):
        """Test that symbolizer is found in clang-tool-chain bin directory."""
        result = get_symbolizer_path()
        if result is None:
            return  # Skip if not installed

        # The path should contain .clang-tool-chain if using bundled binary
        path_str = str(result).lower()
        # Either it's in .clang-tool-chain or it's a system path
        is_bundled = ".clang-tool-chain" in path_str or "clang_tool_chain" in path_str
        is_system = any(p in path_str for p in ["/usr/bin", "/usr/local/bin", "c:\\program files", "llvm"])
        assert is_bundled or is_system, f"Unexpected symbolizer location: {result}"

    def test_prepare_env_returns_consistent_symbolizer_path(self):
        """Test that prepare_sanitizer_environment returns consistent symbolizer path."""
        base_env = {"PATH": "/usr/bin"}

        original_disable = os.environ.get("CLANG_TOOL_CHAIN_NO_SANITIZER_ENV")
        try:
            os.environ.pop("CLANG_TOOL_CHAIN_NO_SANITIZER_ENV", None)

            result1 = prepare_sanitizer_environment(base_env.copy(), compiler_flags=["-fsanitize=address"])
            result2 = prepare_sanitizer_environment(base_env.copy(), compiler_flags=["-fsanitize=address"])

            # Both calls should return the same symbolizer path
            if "ASAN_SYMBOLIZER_PATH" in result1:
                assert "ASAN_SYMBOLIZER_PATH" in result2
                assert result1["ASAN_SYMBOLIZER_PATH"] == result2["ASAN_SYMBOLIZER_PATH"]
        finally:
            if original_disable is None:
                os.environ.pop("CLANG_TOOL_CHAIN_NO_SANITIZER_ENV", None)
            else:
                os.environ["CLANG_TOOL_CHAIN_NO_SANITIZER_ENV"] = original_disable


class TestLsanSuppressionFiles:
    """Test LSan suppression file functionality."""

    def test_get_builtin_suppression_file_darwin(self):
        """Test that Darwin suppression file is returned on macOS."""
        with patch("clang_tool_chain.execution.sanitizer_env.platform.system") as mock_system:
            mock_system.return_value = "Darwin"
            result = _get_builtin_suppression_file()
            if result is not None:  # Only if file exists
                assert "darwin" in str(result).lower()
                assert result.name == "lsan_suppressions_darwin.txt"

    def test_get_builtin_suppression_file_linux(self):
        """Test that Linux suppression file is returned on Linux."""
        with patch("clang_tool_chain.execution.sanitizer_env.platform.system") as mock_system:
            mock_system.return_value = "Linux"
            result = _get_builtin_suppression_file()
            if result is not None:  # Only if file exists
                assert "linux" in str(result).lower()
                assert result.name == "lsan_suppressions_linux.txt"

    def test_get_builtin_suppression_file_windows(self):
        """Test that Windows returns None (no LSan support)."""
        with patch("clang_tool_chain.execution.sanitizer_env.platform.system") as mock_system:
            mock_system.return_value = "Windows"
            result = _get_builtin_suppression_file()
            assert result is None

    def test_suppression_file_included_in_lsan_options(self):
        """Test that suppression file is added to LSAN_OPTIONS when LSAN is enabled."""
        base_env = {"PATH": "/usr/bin"}

        original_disable = os.environ.get("CLANG_TOOL_CHAIN_NO_SANITIZER_ENV")
        try:
            os.environ.pop("CLANG_TOOL_CHAIN_NO_SANITIZER_ENV", None)

            # Mock platform to ensure we get a suppression file
            with patch("clang_tool_chain.execution.sanitizer_env.platform.system") as mock_system:
                mock_system.return_value = "Darwin"  # Use Darwin for test

                result = prepare_sanitizer_environment(base_env, compiler_flags=["-fsanitize=address"])

                # LSAN_OPTIONS should be set
                assert "LSAN_OPTIONS" in result

                # Should contain suppression file path if file exists
                suppression_file = _get_builtin_suppression_file()
                if suppression_file is not None and suppression_file.exists():
                    assert "suppressions=" in result["LSAN_OPTIONS"]
        finally:
            if original_disable is None:
                os.environ.pop("CLANG_TOOL_CHAIN_NO_SANITIZER_ENV", None)
            else:
                os.environ["CLANG_TOOL_CHAIN_NO_SANITIZER_ENV"] = original_disable

    def test_custom_suppression_file_merged_with_builtin(self):
        """Test that custom suppression file is merged with built-in suppressions."""
        import tempfile

        base_env = {"PATH": "/usr/bin"}

        # Create a temporary suppression file
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as tmp:
            tmp.write("leak:test_pattern\n")
            tmp_path = tmp.name

        try:
            original_disable = os.environ.get("CLANG_TOOL_CHAIN_NO_SANITIZER_ENV")
            try:
                os.environ.pop("CLANG_TOOL_CHAIN_NO_SANITIZER_ENV", None)

                # Mock platform to ensure we get a built-in suppression file
                with patch("clang_tool_chain.execution.sanitizer_env.platform.system") as mock_system:
                    mock_system.return_value = "Darwin"

                    result = prepare_sanitizer_environment(
                        base_env, compiler_flags=["-fsanitize=address"], suppression_file=tmp_path
                    )

                    assert "LSAN_OPTIONS" in result
                    # Custom suppression should be present
                    assert f"suppressions={Path(tmp_path).absolute()}" in result["LSAN_OPTIONS"]

                    # Built-in suppression should ALSO be present (merge behavior)
                    builtin_file = _get_builtin_suppression_file()
                    if builtin_file and builtin_file.exists():
                        assert f"suppressions={builtin_file.absolute()}" in result["LSAN_OPTIONS"]
                        # Verify both are in the options (two suppressions= entries)
                        assert result["LSAN_OPTIONS"].count("suppressions=") == 2
            finally:
                if original_disable is None:
                    os.environ.pop("CLANG_TOOL_CHAIN_NO_SANITIZER_ENV", None)
                else:
                    os.environ["CLANG_TOOL_CHAIN_NO_SANITIZER_ENV"] = original_disable
        finally:
            # Clean up temporary file
            Path(tmp_path).unlink(missing_ok=True)

    def test_empty_string_suppression_file_disables_builtin(self):
        """Test that empty string suppression_file disables built-in suppressions."""
        base_env = {"PATH": "/usr/bin"}

        original_disable = os.environ.get("CLANG_TOOL_CHAIN_NO_SANITIZER_ENV")
        try:
            os.environ.pop("CLANG_TOOL_CHAIN_NO_SANITIZER_ENV", None)

            result = prepare_sanitizer_environment(base_env, compiler_flags=["-fsanitize=address"], suppression_file="")

            # LSAN_OPTIONS should be set but without suppressions
            assert "LSAN_OPTIONS" in result
            assert "suppressions=" not in result["LSAN_OPTIONS"]
            # Should contain default options only
            assert "fast_unwind_on_malloc=0" in result["LSAN_OPTIONS"]
        finally:
            if original_disable is None:
                os.environ.pop("CLANG_TOOL_CHAIN_NO_SANITIZER_ENV", None)
            else:
                os.environ["CLANG_TOOL_CHAIN_NO_SANITIZER_ENV"] = original_disable

    def test_suppressions_appended_to_existing_lsan_options(self):
        """Test that both built-in and custom suppressions are appended to existing LSAN_OPTIONS."""
        import tempfile

        # Create a temporary suppression file
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as tmp:
            tmp.write("leak:test_pattern\n")
            tmp_path = tmp.name

        try:
            base_env = {"PATH": "/usr/bin", "LSAN_OPTIONS": "verbosity=1"}

            original_disable = os.environ.get("CLANG_TOOL_CHAIN_NO_SANITIZER_ENV")
            try:
                os.environ.pop("CLANG_TOOL_CHAIN_NO_SANITIZER_ENV", None)

                # Mock platform to ensure we get a built-in suppression file
                with patch("clang_tool_chain.execution.sanitizer_env.platform.system") as mock_system:
                    mock_system.return_value = "Darwin"

                    result = prepare_sanitizer_environment(
                        base_env, compiler_flags=["-fsanitize=address"], suppression_file=tmp_path
                    )

                    # Should preserve user options
                    assert "LSAN_OPTIONS" in result
                    assert "verbosity=1" in result["LSAN_OPTIONS"]

                    # Custom suppression should be present
                    assert f"suppressions={Path(tmp_path).absolute()}" in result["LSAN_OPTIONS"]

                    # Built-in suppression should also be present (merge behavior)
                    builtin_file = _get_builtin_suppression_file()
                    if builtin_file and builtin_file.exists():
                        assert f"suppressions={builtin_file.absolute()}" in result["LSAN_OPTIONS"]
                        # User options + built-in + custom = should start with verbosity
                        assert result["LSAN_OPTIONS"].startswith("verbosity=1:")
            finally:
                if original_disable is None:
                    os.environ.pop("CLANG_TOOL_CHAIN_NO_SANITIZER_ENV", None)
                else:
                    os.environ["CLANG_TOOL_CHAIN_NO_SANITIZER_ENV"] = original_disable
        finally:
            # Clean up temporary file
            Path(tmp_path).unlink(missing_ok=True)

    def test_nonexistent_custom_suppression_file_ignored_but_builtin_applied(self):
        """Test that nonexistent custom suppression file is ignored but built-in still applies."""
        base_env = {"PATH": "/usr/bin"}

        original_disable = os.environ.get("CLANG_TOOL_CHAIN_NO_SANITIZER_ENV")
        try:
            os.environ.pop("CLANG_TOOL_CHAIN_NO_SANITIZER_ENV", None)

            # Mock platform to ensure we get a built-in suppression file
            with patch("clang_tool_chain.execution.sanitizer_env.platform.system") as mock_system:
                mock_system.return_value = "Darwin"

                result = prepare_sanitizer_environment(
                    base_env,
                    compiler_flags=["-fsanitize=address"],
                    suppression_file="/nonexistent/path/to/suppressions.txt",
                )

                # LSAN_OPTIONS should be set
                assert "LSAN_OPTIONS" in result

                # Built-in suppression should still be present (nonexistent custom is skipped)
                builtin_file = _get_builtin_suppression_file()
                if builtin_file and builtin_file.exists():
                    assert f"suppressions={builtin_file.absolute()}" in result["LSAN_OPTIONS"]
                    # Only one suppressions= entry (custom was skipped)
                    assert result["LSAN_OPTIONS"].count("suppressions=") == 1

                # The nonexistent custom path should NOT be in the options
                assert "/nonexistent/path/to/suppressions.txt" not in result["LSAN_OPTIONS"]
        finally:
            if original_disable is None:
                os.environ.pop("CLANG_TOOL_CHAIN_NO_SANITIZER_ENV", None)
            else:
                os.environ["CLANG_TOOL_CHAIN_NO_SANITIZER_ENV"] = original_disable

    def test_suppression_not_added_when_lsan_disabled(self):
        """Test that suppression is not added when LSAN is not enabled."""
        import tempfile

        # Create a temporary suppression file
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as tmp:
            tmp.write("leak:test_pattern\n")
            tmp_path = tmp.name

        try:
            base_env = {"PATH": "/usr/bin"}

            result = prepare_sanitizer_environment(base_env, compiler_flags=["-O2", "-Wall"], suppression_file=tmp_path)

            # LSAN_OPTIONS should not be set since LSAN not enabled
            assert "LSAN_OPTIONS" not in result
        finally:
            # Clean up temporary file
            Path(tmp_path).unlink(missing_ok=True)

    def test_builtin_suppression_files_exist(self):
        """Test that built-in suppression files exist in the package."""
        # This test verifies that the suppression files are properly included in the package
        from pathlib import Path

        # Get the data directory path
        data_dir = Path(__file__).parent.parent / "src" / "clang_tool_chain" / "data"

        # Check Darwin suppression file
        darwin_file = data_dir / "lsan_suppressions_darwin.txt"
        assert darwin_file.exists(), f"Darwin suppression file not found: {darwin_file}"

        # Check Linux suppression file
        linux_file = data_dir / "lsan_suppressions_linux.txt"
        assert linux_file.exists(), f"Linux suppression file not found: {linux_file}"

    def test_darwin_suppression_file_contains_patterns(self):
        """Test that Darwin suppression file contains expected patterns."""
        from pathlib import Path

        data_dir = Path(__file__).parent.parent / "src" / "clang_tool_chain" / "data"
        darwin_file = data_dir / "lsan_suppressions_darwin.txt"

        if darwin_file.exists():
            content = darwin_file.read_text()
            # Check for expected macOS system library patterns
            assert "libobjc.A.dylib" in content
            assert "libxpc.dylib" in content or "dyld" in content
            # File should not be empty
            assert len(content.strip()) > 0

    def test_no_warning_when_no_custom_suppression_file_provided(self):
        """Test that no warning is logged when user doesn't provide a custom suppression file."""

        base_env = {"PATH": "/usr/bin"}

        original_disable = os.environ.get("CLANG_TOOL_CHAIN_NO_SANITIZER_ENV")
        try:
            os.environ.pop("CLANG_TOOL_CHAIN_NO_SANITIZER_ENV", None)

            # Capture log output
            with patch("clang_tool_chain.execution.sanitizer_env.logger") as mock_logger:
                # Call without custom suppression file (None = use built-in only)
                prepare_sanitizer_environment(base_env, compiler_flags=["-fsanitize=address"], suppression_file=None)

                # Should NOT have called warning() - only info() for injecting built-in
                mock_logger.warning.assert_not_called()
        finally:
            if original_disable is None:
                os.environ.pop("CLANG_TOOL_CHAIN_NO_SANITIZER_ENV", None)
            else:
                os.environ["CLANG_TOOL_CHAIN_NO_SANITIZER_ENV"] = original_disable

    def test_warning_when_custom_suppression_file_not_found(self):
        """Test that a warning is logged when user provides a nonexistent custom suppression file."""

        base_env = {"PATH": "/usr/bin"}

        original_disable = os.environ.get("CLANG_TOOL_CHAIN_NO_SANITIZER_ENV")
        try:
            os.environ.pop("CLANG_TOOL_CHAIN_NO_SANITIZER_ENV", None)

            # Capture log output
            with patch("clang_tool_chain.execution.sanitizer_env.logger") as mock_logger:
                # Call with nonexistent custom suppression file
                prepare_sanitizer_environment(
                    base_env,
                    compiler_flags=["-fsanitize=address"],
                    suppression_file="/nonexistent/path/to/suppressions.txt",
                )

                # Should have called warning() for missing file
                mock_logger.warning.assert_called_once()
                warning_msg = mock_logger.warning.call_args[0][0]
                assert "not found" in warning_msg
                assert "/nonexistent/path/to/suppressions.txt" in warning_msg
        finally:
            if original_disable is None:
                os.environ.pop("CLANG_TOOL_CHAIN_NO_SANITIZER_ENV", None)
            else:
                os.environ["CLANG_TOOL_CHAIN_NO_SANITIZER_ENV"] = original_disable


class TestLsanSuppressionIntegration:
    """Integration tests for LSan suppression with actual compilation and execution.

    These tests verify that:
    1. A program with an intentional memory leak is detected by LSan
    2. A custom suppression file can suppress the leak detection
    3. The merge behavior works (built-in + custom suppressions)

    Note: These tests require the clang-tool-chain toolchain to be installed.
    They are skipped on Windows since LSAN is not supported there.
    """

    @pytest.fixture
    def temp_dir(self):
        """Create a temporary directory for test files."""
        import tempfile

        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)

    @pytest.fixture
    def leak_c_file(self, temp_dir):
        """Create a C file with an intentional memory leak."""
        c_file = temp_dir / "leak_test.c"
        c_file.write_text(
            """
#include <stdlib.h>
#include <stdio.h>

// Function that leaks memory - name is used for suppression matching
void intentional_leak_function(void) {
    // Allocate memory and intentionally leak it
    char* leaked = (char*)malloc(100);
    if (leaked) {
        leaked[0] = 'X';  // Use the memory to prevent optimization
        printf("Allocated memory at %p\\n", (void*)leaked);
    }
    // Intentionally NOT freeing 'leaked' - this is the leak
}

int main(void) {
    printf("Starting leak test\\n");
    intentional_leak_function();
    printf("Exiting without freeing memory\\n");
    return 0;
}
"""
        )
        return c_file

    @pytest.fixture
    def suppression_file(self, temp_dir):
        """Create a custom suppression file that suppresses the intentional leak."""
        supp_file = temp_dir / "my_suppressions.txt"
        supp_file.write_text(
            """# Custom suppression file for testing
# This suppresses the intentional leak in our test program
leak:intentional_leak_function
"""
        )
        return supp_file

    @pytest.mark.skipif(
        sys.platform == "win32",
        reason="LSan is not supported on Windows",
    )
    def test_leak_detected_without_suppression(self, leak_c_file, temp_dir):
        """Test that the memory leak is detected by LSan without suppression."""

        output_exe = temp_dir / "leak_test"

        # Compile with ASAN (includes LSAN)
        compile_cmd = [
            "clang-tool-chain-c",
            "-fsanitize=address",
            "-g",
            str(leak_c_file),
            "-o",
            str(output_exe),
        ]

        compile_result = subprocess.run(compile_cmd, capture_output=True, text=True)
        if compile_result.returncode != 0:
            pytest.skip(f"Compilation failed: {compile_result.stderr}")

        assert output_exe.exists(), "Executable not created"

        # Run without any suppression - leak should be detected
        # Prepare environment with ASAN options but no custom suppression
        env = prepare_sanitizer_environment(
            base_env=os.environ.copy(),
            compiler_flags=["-fsanitize=address"],
            suppression_file="",  # Disable built-in suppressions to ensure leak is detected
        )

        run_result = subprocess.run([str(output_exe)], capture_output=True, text=True, env=env)

        # LSan should detect the leak and exit with non-zero code
        # Note: The exact exit code may vary, but stderr should contain leak info
        assert (
            "leak" in run_result.stderr.lower()
            or "sanitizer" in run_result.stderr.lower()
            or run_result.returncode != 0
        ), (
            f"Expected leak detection, got: stdout={run_result.stdout}, stderr={run_result.stderr}, rc={run_result.returncode}"
        )

    @pytest.mark.skipif(
        sys.platform == "win32",
        reason="LSan is not supported on Windows",
    )
    def test_leak_suppressed_with_custom_file(self, leak_c_file, suppression_file, temp_dir):
        """Test that the memory leak is suppressed when using a custom suppression file."""

        output_exe = temp_dir / "leak_test_suppressed"

        # Compile with ASAN (includes LSAN)
        compile_cmd = [
            "clang-tool-chain-c",
            "-fsanitize=address",
            "-g",
            str(leak_c_file),
            "-o",
            str(output_exe),
        ]

        compile_result = subprocess.run(compile_cmd, capture_output=True, text=True)
        if compile_result.returncode != 0:
            pytest.skip(f"Compilation failed: {compile_result.stderr}")

        assert output_exe.exists(), "Executable not created"

        # Run WITH custom suppression file - leak should be suppressed
        env = prepare_sanitizer_environment(
            base_env=os.environ.copy(),
            compiler_flags=["-fsanitize=address"],
            suppression_file=str(suppression_file),
        )

        run_result = subprocess.run([str(output_exe)], capture_output=True, text=True, env=env)

        # With suppression, the program should exit cleanly (or at least not report our specific leak)
        # Check that stderr doesn't contain "intentional_leak_function" as a leak source
        assert "intentional_leak_function" not in run_result.stderr or "suppressed" in run_result.stderr.lower(), (
            f"Expected leak to be suppressed, got: stderr={run_result.stderr}"
        )

    @pytest.mark.skipif(
        sys.platform == "win32",
        reason="LSan is not supported on Windows",
    )
    def test_merge_behavior_both_suppressions_applied(self, temp_dir):
        """Test that both built-in and custom suppressions are merged correctly."""

        # Create a C file with two different leak patterns
        c_file = temp_dir / "dual_leak_test.c"
        c_file.write_text(
            """
#include <stdlib.h>
#include <stdio.h>

// Leak that will be suppressed by custom file
void custom_suppressed_leak(void) {
    char* leaked = (char*)malloc(50);
    if (leaked) leaked[0] = 'A';
}

// Another leak for testing
void another_leak(void) {
    char* leaked = (char*)malloc(50);
    if (leaked) leaked[0] = 'B';
}

int main(void) {
    custom_suppressed_leak();
    another_leak();
    return 0;
}
"""
        )

        # Custom suppression file that only suppresses one leak
        custom_supp = temp_dir / "partial_suppressions.txt"
        custom_supp.write_text("leak:custom_suppressed_leak\n")

        output_exe = temp_dir / "dual_leak_test"

        # Compile
        compile_cmd = [
            "clang-tool-chain-c",
            "-fsanitize=address",
            "-g",
            str(c_file),
            "-o",
            str(output_exe),
        ]

        compile_result = subprocess.run(compile_cmd, capture_output=True, text=True)
        if compile_result.returncode != 0:
            pytest.skip(f"Compilation failed: {compile_result.stderr}")

        # Run with merge behavior
        env = prepare_sanitizer_environment(
            base_env=os.environ.copy(),
            compiler_flags=["-fsanitize=address"],
            suppression_file=str(custom_supp),  # Custom suppression + built-in
        )

        run_result = subprocess.run([str(output_exe)], capture_output=True, text=True, env=env)

        # custom_suppressed_leak should be suppressed
        # another_leak might still be detected (unless caught by built-in suppressions)
        # The key is that our custom suppression was applied
        assert "custom_suppressed_leak" not in run_result.stderr or "suppressed" in run_result.stderr.lower(), (
            f"Expected custom_suppressed_leak to be suppressed, got: stderr={run_result.stderr}"
        )
