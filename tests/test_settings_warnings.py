"""
Tests for settings warnings functionality.
"""

import logging
from pathlib import Path

import pytest
from _pytest.logging import LogCaptureFixture
from _pytest.monkeypatch import MonkeyPatch

from clang_tool_chain.settings_warnings import (
    reset_warnings,
    warn_download_path_override,
    warn_if_env_var_set,
    warn_no_sysroot,
    warn_use_system_ld,
)


@pytest.fixture(autouse=True)
def reset_warning_state():
    """Reset warning state before each test."""
    reset_warnings()
    yield
    reset_warnings()


@pytest.fixture
def clean_env(monkeypatch: MonkeyPatch) -> None:
    """Clean environment variables before tests."""
    monkeypatch.delenv("CLANG_TOOL_CHAIN_DOWNLOAD_PATH", raising=False)
    monkeypatch.delenv("CLANG_TOOL_CHAIN_NO_SYSROOT", raising=False)
    monkeypatch.delenv("CLANG_TOOL_CHAIN_USE_SYSTEM_LD", raising=False)


class TestWarnIfEnvVarSet:
    """Tests for the generic warn_if_env_var_set function."""

    def test_no_warning_when_var_not_set(self, clean_env: None, caplog: LogCaptureFixture) -> None:
        """Test that no warning is issued when env var is not set."""
        with caplog.at_level(logging.WARNING):
            result = warn_if_env_var_set("TEST_VAR")
            assert result is False
            assert len(caplog.records) == 0

    def test_warning_when_var_is_set(self, monkeypatch: MonkeyPatch, caplog: LogCaptureFixture) -> None:
        """Test that warning is issued when env var is set."""
        monkeypatch.setenv("TEST_VAR", "test_value")
        with caplog.at_level(logging.WARNING):
            result = warn_if_env_var_set("TEST_VAR")
            assert result is True
            assert len(caplog.records) == 1
            assert "TEST_VAR=test_value" in caplog.text

    def test_warning_with_expected_value_match(self, monkeypatch: MonkeyPatch, caplog: LogCaptureFixture) -> None:
        """Test warning with expected value that matches."""
        monkeypatch.setenv("TEST_VAR", "expected")
        with caplog.at_level(logging.WARNING):
            result = warn_if_env_var_set("TEST_VAR", expected_value="expected")
            assert result is True
            assert len(caplog.records) == 1

    def test_no_warning_with_expected_value_mismatch(self, monkeypatch: MonkeyPatch, caplog: LogCaptureFixture) -> None:
        """Test no warning when expected value doesn't match."""
        monkeypatch.setenv("TEST_VAR", "wrong")
        with caplog.at_level(logging.WARNING):
            result = warn_if_env_var_set("TEST_VAR", expected_value="expected")
            assert result is False
            assert len(caplog.records) == 0

    def test_custom_message(self, monkeypatch: MonkeyPatch, caplog: LogCaptureFixture) -> None:
        """Test custom warning message."""
        monkeypatch.setenv("TEST_VAR", "value")
        custom_msg = "Custom warning message"
        with caplog.at_level(logging.WARNING):
            warn_if_env_var_set("TEST_VAR", message=custom_msg)
            assert custom_msg in caplog.text

    def test_warning_shown_once_by_default(self, monkeypatch: MonkeyPatch, caplog: LogCaptureFixture) -> None:
        """Test that warning is only shown once by default."""
        monkeypatch.setenv("TEST_VAR", "value")
        with caplog.at_level(logging.WARNING):
            # First call should warn
            result1 = warn_if_env_var_set("TEST_VAR")
            assert result1 is True
            assert len(caplog.records) == 1

            # Second call should not warn
            caplog.clear()
            result2 = warn_if_env_var_set("TEST_VAR")
            assert result2 is True  # Still returns True
            assert len(caplog.records) == 0  # But no new warning

    def test_warning_shown_multiple_times_when_once_false(
        self, monkeypatch: MonkeyPatch, caplog: LogCaptureFixture
    ) -> None:
        """Test that warning is shown multiple times when once=False."""
        monkeypatch.setenv("TEST_VAR", "value")
        with caplog.at_level(logging.WARNING):
            # First call should warn
            warn_if_env_var_set("TEST_VAR", once=False)
            assert len(caplog.records) == 1

            # Second call should also warn
            caplog.clear()
            warn_if_env_var_set("TEST_VAR", once=False)
            assert len(caplog.records) == 1


class TestWarnDownloadPathOverride:
    """Tests for warn_download_path_override function."""

    def test_no_warning_without_override(self, clean_env: None, caplog: LogCaptureFixture) -> None:
        """Test no warning when CLANG_TOOL_CHAIN_DOWNLOAD_PATH is not set."""
        with caplog.at_level(logging.WARNING):
            result = warn_download_path_override()
            assert result is None
            assert len(caplog.records) == 0

    def test_warning_with_override(self, monkeypatch: MonkeyPatch, caplog: LogCaptureFixture) -> None:
        """Test warning when CLANG_TOOL_CHAIN_DOWNLOAD_PATH is set."""
        test_path = "/custom/path"
        monkeypatch.setenv("CLANG_TOOL_CHAIN_DOWNLOAD_PATH", test_path)
        with caplog.at_level(logging.WARNING):
            result = warn_download_path_override()
            assert result == test_path
            assert len(caplog.records) == 1
            assert "CLANG_TOOL_CHAIN_DOWNLOAD_PATH" in caplog.text
            assert test_path in caplog.text
            assert "custom download path" in caplog.text.lower()

    def test_warning_shown_once(self, monkeypatch: MonkeyPatch, caplog: LogCaptureFixture) -> None:
        """Test that warning is only shown once per session."""
        monkeypatch.setenv("CLANG_TOOL_CHAIN_DOWNLOAD_PATH", "/custom/path")
        with caplog.at_level(logging.WARNING):
            # First call
            warn_download_path_override()
            assert len(caplog.records) == 1

            # Second call
            caplog.clear()
            warn_download_path_override()
            assert len(caplog.records) == 0


class TestWarnNoSysroot:
    """Tests for warn_no_sysroot function."""

    def test_no_warning_when_not_set(self, clean_env: None, caplog: LogCaptureFixture) -> None:
        """Test no warning when CLANG_TOOL_CHAIN_NO_SYSROOT is not set."""
        with caplog.at_level(logging.WARNING):
            result = warn_no_sysroot()
            assert result is False
            assert len(caplog.records) == 0

    def test_no_warning_when_set_to_zero(self, monkeypatch: MonkeyPatch, caplog: LogCaptureFixture) -> None:
        """Test no warning when CLANG_TOOL_CHAIN_NO_SYSROOT=0."""
        monkeypatch.setenv("CLANG_TOOL_CHAIN_NO_SYSROOT", "0")
        with caplog.at_level(logging.WARNING):
            result = warn_no_sysroot()
            assert result is False
            assert len(caplog.records) == 0

    def test_warning_when_set_to_one(self, monkeypatch: MonkeyPatch, caplog: LogCaptureFixture) -> None:
        """Test warning when CLANG_TOOL_CHAIN_NO_SYSROOT=1."""
        monkeypatch.setenv("CLANG_TOOL_CHAIN_NO_SYSROOT", "1")
        with caplog.at_level(logging.WARNING):
            result = warn_no_sysroot()
            assert result is True
            assert len(caplog.records) == 1
            assert "CLANG_TOOL_CHAIN_NO_SYSROOT=1" in caplog.text
            assert "macOS SDK detection disabled" in caplog.text

    def test_warning_mentions_manual_sysroot(self, monkeypatch: MonkeyPatch, caplog: LogCaptureFixture) -> None:
        """Test that warning mentions manual sysroot specification."""
        monkeypatch.setenv("CLANG_TOOL_CHAIN_NO_SYSROOT", "1")
        with caplog.at_level(logging.WARNING):
            warn_no_sysroot()
            assert "-isysroot" in caplog.text or "SDKROOT" in caplog.text


class TestWarnUseSystemLd:
    """Tests for warn_use_system_ld function."""

    def test_no_warning_when_not_set(self, clean_env: None, caplog: LogCaptureFixture) -> None:
        """Test no warning when CLANG_TOOL_CHAIN_USE_SYSTEM_LD is not set."""
        with caplog.at_level(logging.WARNING):
            result = warn_use_system_ld()
            assert result is False
            assert len(caplog.records) == 0

    def test_no_warning_when_set_to_zero(self, monkeypatch: MonkeyPatch, caplog: LogCaptureFixture) -> None:
        """Test no warning when CLANG_TOOL_CHAIN_USE_SYSTEM_LD=0."""
        monkeypatch.setenv("CLANG_TOOL_CHAIN_USE_SYSTEM_LD", "0")
        with caplog.at_level(logging.WARNING):
            result = warn_use_system_ld()
            assert result is False
            assert len(caplog.records) == 0

    def test_warning_when_set_to_one(self, monkeypatch: MonkeyPatch, caplog: LogCaptureFixture) -> None:
        """Test warning when CLANG_TOOL_CHAIN_USE_SYSTEM_LD=1."""
        monkeypatch.setenv("CLANG_TOOL_CHAIN_USE_SYSTEM_LD", "1")
        with caplog.at_level(logging.WARNING):
            result = warn_use_system_ld()
            assert result is True
            assert len(caplog.records) == 1
            assert "CLANG_TOOL_CHAIN_USE_SYSTEM_LD=1" in caplog.text
            assert "system linker" in caplog.text.lower()

    def test_warning_mentions_lld(self, monkeypatch: MonkeyPatch, caplog: LogCaptureFixture) -> None:
        """Test that warning mentions lld."""
        monkeypatch.setenv("CLANG_TOOL_CHAIN_USE_SYSTEM_LD", "1")
        with caplog.at_level(logging.WARNING):
            warn_use_system_ld()
            assert "lld" in caplog.text.lower()


class TestIntegration:
    """Integration tests with actual module functions."""

    def test_downloader_warns_on_custom_path(self, monkeypatch: MonkeyPatch, caplog: LogCaptureFixture) -> None:
        """Test that downloader functions trigger warnings."""
        from clang_tool_chain.downloader import get_home_toolchain_dir

        test_path = "/test/custom/path"
        monkeypatch.setenv("CLANG_TOOL_CHAIN_DOWNLOAD_PATH", test_path)

        with caplog.at_level(logging.WARNING):
            result = get_home_toolchain_dir()
            assert result == Path(test_path)
            assert len(caplog.records) == 1
            assert "CLANG_TOOL_CHAIN_DOWNLOAD_PATH" in caplog.text

    def test_wrapper_warns_on_no_sysroot(self, monkeypatch: MonkeyPatch, caplog: LogCaptureFixture) -> None:
        """Test that wrapper functions trigger warnings for NO_SYSROOT."""
        from clang_tool_chain.wrapper import _add_macos_sysroot_if_needed

        monkeypatch.setenv("CLANG_TOOL_CHAIN_NO_SYSROOT", "1")
        test_args = ["clang", "test.c"]

        with caplog.at_level(logging.WARNING):
            result = _add_macos_sysroot_if_needed(test_args)
            assert result == test_args  # Should return unchanged
            assert len(caplog.records) == 1
            assert "CLANG_TOOL_CHAIN_NO_SYSROOT=1" in caplog.text

    def test_wrapper_warns_on_use_system_ld(self, monkeypatch: MonkeyPatch, caplog: LogCaptureFixture) -> None:
        """Test that wrapper functions trigger warnings for USE_SYSTEM_LD."""
        from clang_tool_chain.wrapper import _should_force_lld

        monkeypatch.setenv("CLANG_TOOL_CHAIN_USE_SYSTEM_LD", "1")
        test_args = ["clang", "test.c", "-o", "test"]

        with caplog.at_level(logging.WARNING):
            result = _should_force_lld("linux", test_args)
            assert result is False
            assert len(caplog.records) == 1
            assert "CLANG_TOOL_CHAIN_USE_SYSTEM_LD=1" in caplog.text

    def test_multiple_warnings_different_settings(self, monkeypatch: MonkeyPatch, caplog: LogCaptureFixture) -> None:
        """Test that different settings each produce their own warning."""
        from clang_tool_chain.downloader import get_home_toolchain_dir
        from clang_tool_chain.wrapper import _add_macos_sysroot_if_needed, _should_force_lld

        monkeypatch.setenv("CLANG_TOOL_CHAIN_DOWNLOAD_PATH", "/custom")
        monkeypatch.setenv("CLANG_TOOL_CHAIN_NO_SYSROOT", "1")
        monkeypatch.setenv("CLANG_TOOL_CHAIN_USE_SYSTEM_LD", "1")

        with caplog.at_level(logging.WARNING):
            # Trigger all three warnings
            get_home_toolchain_dir()
            _add_macos_sysroot_if_needed(["clang", "test.c"])
            _should_force_lld("linux", ["clang", "test.c"])

            # Should have 3 distinct warnings
            assert len(caplog.records) == 3
            assert "CLANG_TOOL_CHAIN_DOWNLOAD_PATH" in caplog.text
            assert "CLANG_TOOL_CHAIN_NO_SYSROOT" in caplog.text
            assert "CLANG_TOOL_CHAIN_USE_SYSTEM_LD" in caplog.text


class TestResetWarnings:
    """Tests for the reset_warnings function."""

    def test_reset_allows_warnings_to_show_again(self, monkeypatch: MonkeyPatch, caplog: LogCaptureFixture) -> None:
        """Test that reset_warnings allows warnings to be shown again."""
        monkeypatch.setenv("TEST_VAR", "value")

        with caplog.at_level(logging.WARNING):
            # First call
            warn_if_env_var_set("TEST_VAR")
            assert len(caplog.records) == 1

            # Second call - no warning
            caplog.clear()
            warn_if_env_var_set("TEST_VAR")
            assert len(caplog.records) == 0

            # Reset and try again - should warn
            reset_warnings()
            caplog.clear()
            warn_if_env_var_set("TEST_VAR")
            assert len(caplog.records) == 1
