"""
Tests for automatic ASAN_OPTIONS and LSAN_OPTIONS injection.

This test suite verifies that sanitizer environment variables are automatically
injected when running executables compiled with Address Sanitizer or Leak Sanitizer,
improving stack trace quality for dlopen()'d shared libraries.
"""

import os

from clang_tool_chain.execution.sanitizer_env import (
    DEFAULT_ASAN_OPTIONS,
    DEFAULT_LSAN_OPTIONS,
    detect_sanitizers_from_flags,
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
