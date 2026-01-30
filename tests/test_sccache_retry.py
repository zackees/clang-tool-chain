"""
Tests for sccache retry logic on Windows server timeout.

These tests verify that the _run_with_retry function correctly detects
sccache server errors and retries on Windows.
"""

from unittest.mock import MagicMock, patch

import pytest


class TestSccacheServerErrorDetection:
    """Test sccache server error pattern detection."""

    def test_detects_failed_to_send_data_error(self):
        """Test detection of 'Failed to send data to or receive data from server' error."""
        from clang_tool_chain.sccache_runner import _is_sccache_server_error

        output = "sccache: caused by: Failed to send data to or receive data from server"
        assert _is_sccache_server_error(output) is True

    def test_detects_failed_to_execute_compile_error(self):
        """Test detection of 'failed to execute compile' error."""
        from clang_tool_chain.sccache_runner import _is_sccache_server_error

        output = "sccache: error: failed to execute compile"
        assert _is_sccache_server_error(output) is True

    def test_detects_connection_refused_error(self):
        """Test detection of 'Connection refused' error."""
        from clang_tool_chain.sccache_runner import _is_sccache_server_error

        output = "sccache: Connection refused"
        assert _is_sccache_server_error(output) is True

    def test_detects_server_returned_error(self):
        """Test detection of 'server returned an error' message."""
        from clang_tool_chain.sccache_runner import _is_sccache_server_error

        output = "sccache: server returned an error: timeout"
        assert _is_sccache_server_error(output) is True

    def test_case_insensitive_detection(self):
        """Test that error detection is case-insensitive."""
        from clang_tool_chain.sccache_runner import _is_sccache_server_error

        output = "SCCACHE: FAILED TO SEND DATA TO OR RECEIVE DATA FROM SERVER"
        assert _is_sccache_server_error(output) is True

    def test_does_not_match_normal_output(self):
        """Test that normal compilation output is not detected as an error."""
        from clang_tool_chain.sccache_runner import _is_sccache_server_error

        output = "Compiling main.cpp\nLinking program.exe\nBuild complete."
        assert _is_sccache_server_error(output) is False

    def test_does_not_match_regular_compile_error(self):
        """Test that regular compile errors are not detected as server errors."""
        from clang_tool_chain.sccache_runner import _is_sccache_server_error

        output = "main.cpp:10:5: error: use of undeclared identifier 'foo'"
        assert _is_sccache_server_error(output) is False


class TestRunWithRetry:
    """Test _run_with_retry function behavior."""

    def test_no_retry_on_success(self):
        """Test that successful commands don't trigger retries."""
        from clang_tool_chain.sccache_runner import _run_with_retry

        with (
            patch("platform.system", return_value="Windows"),
            patch("clang_tool_chain.sccache_runner.subprocess.run") as mock_run,
        ):
            mock_result = MagicMock()
            mock_result.returncode = 0
            mock_result.stdout = b"Success"
            mock_result.stderr = b""
            mock_run.return_value = mock_result

            result = _run_with_retry(["sccache", "clang++", "test.cpp"])

            assert result.returncode == 0
            assert mock_run.call_count == 1

    def test_retry_on_server_error_windows(self):
        """Test that server errors trigger retries on Windows."""
        from clang_tool_chain.sccache_runner import _run_with_retry

        with (
            patch("platform.system", return_value="Windows"),
            patch("clang_tool_chain.sccache_runner.subprocess.run") as mock_run,
            patch("clang_tool_chain.sccache_runner.time.sleep") as mock_sleep,
        ):
            # First call fails with server error
            error_result = MagicMock()
            error_result.returncode = 2
            error_result.stdout = b""
            error_result.stderr = b"sccache: caused by: Failed to send data to or receive data from server"

            # Second call succeeds
            success_result = MagicMock()
            success_result.returncode = 0
            success_result.stdout = b"Success"
            success_result.stderr = b""

            mock_run.side_effect = [error_result, success_result]

            result = _run_with_retry(["sccache", "clang++", "test.cpp"], max_retries=3, retry_delay=0.1)

            assert result.returncode == 0
            assert mock_run.call_count == 2
            mock_sleep.assert_called_once_with(0.1)

    def test_no_retry_on_linux(self):
        """Test that retries are not attempted on Linux."""
        from clang_tool_chain.sccache_runner import _run_with_retry

        with (
            patch("platform.system", return_value="Linux"),
            patch("clang_tool_chain.sccache_runner.subprocess.run") as mock_run,
        ):
            # Fail with server error
            error_result = MagicMock()
            error_result.returncode = 2
            error_result.stdout = b""
            error_result.stderr = b"sccache: caused by: Failed to send data to or receive data from server"
            mock_run.return_value = error_result

            result = _run_with_retry(["sccache", "clang++", "test.cpp"])

            # Should return the error without retrying
            assert result.returncode == 2
            assert mock_run.call_count == 1

    def test_no_retry_on_non_server_error(self):
        """Test that regular compile errors don't trigger retries."""
        from clang_tool_chain.sccache_runner import _run_with_retry

        with (
            patch("platform.system", return_value="Windows"),
            patch("clang_tool_chain.sccache_runner.subprocess.run") as mock_run,
        ):
            # Fail with regular compile error
            error_result = MagicMock()
            error_result.returncode = 1
            error_result.stdout = b""
            error_result.stderr = b"main.cpp:10:5: error: use of undeclared identifier 'foo'"
            mock_run.return_value = error_result

            result = _run_with_retry(["sccache", "clang++", "test.cpp"])

            # Should return the error without retrying
            assert result.returncode == 1
            assert mock_run.call_count == 1

    def test_max_retries_exhausted(self):
        """Test that retries stop after max_retries attempts."""
        from clang_tool_chain.sccache_runner import _run_with_retry

        with (
            patch("platform.system", return_value="Windows"),
            patch("clang_tool_chain.sccache_runner.subprocess.run") as mock_run,
            patch("clang_tool_chain.sccache_runner.time.sleep") as mock_sleep,
        ):
            # Always fail with server error
            error_result = MagicMock()
            error_result.returncode = 2
            error_result.stdout = b""
            error_result.stderr = b"sccache: caused by: Failed to send data to or receive data from server"
            mock_run.return_value = error_result

            result = _run_with_retry(["sccache", "clang++", "test.cpp"], max_retries=2, retry_delay=0.1)

            # Should fail after 3 attempts (1 initial + 2 retries)
            assert result.returncode == 2
            assert mock_run.call_count == 3
            assert mock_sleep.call_count == 2


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
