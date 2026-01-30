"""Tests for parallel download functionality with range requests."""

import hashlib
import os
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, Mock, patch

import httpx
import pytest

from clang_tool_chain.parallel_download import (
    DownloadConfig,
    ServerCapabilities,
    _calculate_chunks,
    _verify_checksum,
    check_server_capabilities,
    download_file_parallel,
)


def create_mock_httpx_response(headers: dict, status_code: int = 200, content: bytes = b"") -> MagicMock:
    """Create a mock httpx response for testing."""
    mock_response = MagicMock()
    mock_response.headers = httpx.Headers(headers)
    mock_response.status_code = status_code
    mock_response.content = content

    # Make it work as a context manager
    mock_response.__enter__ = Mock(return_value=mock_response)
    mock_response.__exit__ = Mock(return_value=False)

    return mock_response


def create_mock_httpx_client(response: MagicMock) -> MagicMock:
    """Create a mock httpx.Client for testing."""
    mock_client = MagicMock()
    mock_client.head.return_value = response
    mock_client.stream.return_value = response
    mock_client.__enter__ = Mock(return_value=mock_client)
    mock_client.__exit__ = Mock(return_value=False)
    return mock_client


class TestServerCapabilities:
    """Test server capability detection."""

    def test_check_server_capabilities_with_range_support(self):
        """Test detection of server that supports range requests."""
        mock_response = create_mock_httpx_response(
            headers={"Content-Length": "104857600", "Accept-Ranges": "bytes"},
            status_code=200,
        )
        mock_client = create_mock_httpx_client(mock_response)

        with patch("clang_tool_chain.parallel_download.httpx.Client", return_value=mock_client):
            caps = check_server_capabilities("https://example.com/file.tar.zst")

            assert caps.supports_ranges is True
            assert caps.content_length == 104857600
            assert caps.accepts_partial is True

    def test_check_server_capabilities_without_range_support(self):
        """Test detection of server that doesn't support range requests."""
        mock_response = create_mock_httpx_response(
            headers={"Content-Length": "104857600", "Accept-Ranges": "none"},
            status_code=200,
        )
        mock_client = create_mock_httpx_client(mock_response)

        with patch("clang_tool_chain.parallel_download.httpx.Client", return_value=mock_client):
            caps = check_server_capabilities("https://example.com/file.tar.zst")

            assert caps.supports_ranges is False
            assert caps.content_length == 104857600

    def test_check_server_capabilities_no_content_length(self):
        """Test detection when server doesn't provide Content-Length."""
        mock_response = create_mock_httpx_response(
            headers={"Accept-Ranges": "bytes"},
            status_code=200,
        )
        mock_client = create_mock_httpx_client(mock_response)

        with patch("clang_tool_chain.parallel_download.httpx.Client", return_value=mock_client):
            caps = check_server_capabilities("https://example.com/file.tar.zst")

            assert caps.supports_ranges is True
            assert caps.content_length is None

    def test_check_server_capabilities_network_error(self):
        """Test handling of network errors during capability check."""
        mock_client = MagicMock()
        mock_client.head.side_effect = httpx.ConnectError("Connection failed")
        mock_client.__enter__ = Mock(return_value=mock_client)
        mock_client.__exit__ = Mock(return_value=False)

        with patch("clang_tool_chain.parallel_download.httpx.Client", return_value=mock_client):
            caps = check_server_capabilities("https://example.com/file.tar.zst")

            # Should return conservative defaults
            assert caps.supports_ranges is False
            assert caps.content_length is None


class TestChunkCalculation:
    """Test chunk boundary calculation."""

    def test_calculate_chunks_even_division(self):
        """Test chunk calculation when file size divides evenly."""
        file_size = 80 * 1024 * 1024  # 80 MB
        chunk_size = 8 * 1024 * 1024  # 8 MB
        chunks = _calculate_chunks(file_size, chunk_size)

        assert len(chunks) == 10
        assert chunks[0].start == 0
        assert chunks[0].end == chunk_size - 1
        assert chunks[-1].end == file_size - 1

        # Verify all chunks are accounted for
        total_bytes = sum(chunk.end - chunk.start + 1 for chunk in chunks)
        assert total_bytes == file_size

    def test_calculate_chunks_uneven_division(self):
        """Test chunk calculation when file size doesn't divide evenly."""
        file_size = 85 * 1024 * 1024  # 85 MB
        chunk_size = 8 * 1024 * 1024  # 8 MB
        chunks = _calculate_chunks(file_size, chunk_size)

        assert len(chunks) == 11  # 10 full chunks + 1 partial
        assert chunks[-1].end == file_size - 1

        # Last chunk should be smaller
        last_chunk_size = chunks[-1].end - chunks[-1].start + 1
        assert last_chunk_size < chunk_size

        # Verify all chunks are accounted for
        total_bytes = sum(chunk.end - chunk.start + 1 for chunk in chunks)
        assert total_bytes == file_size

    def test_calculate_chunks_small_file(self):
        """Test chunk calculation for file smaller than chunk size."""
        file_size = 5 * 1024 * 1024  # 5 MB
        chunk_size = 8 * 1024 * 1024  # 8 MB
        chunks = _calculate_chunks(file_size, chunk_size)

        assert len(chunks) == 1
        assert chunks[0].start == 0
        assert chunks[0].end == file_size - 1

    def test_calculate_chunks_metadata(self):
        """Test that chunk metadata is correct."""
        chunks = _calculate_chunks(24 * 1024 * 1024, 8 * 1024 * 1024)

        assert len(chunks) == 3
        for i, chunk in enumerate(chunks):
            assert chunk.index == i
            assert chunk.total_chunks == 3


class TestChecksumVerification:
    """Test checksum verification."""

    def test_verify_checksum_success(self):
        """Test successful checksum verification."""
        # Create a temporary file with known content
        with tempfile.NamedTemporaryFile(delete=False) as f:
            test_data = b"Hello, World! This is test data."
            f.write(test_data)
            f.flush()
            temp_path = Path(f.name)

        try:
            # Calculate expected hash
            expected_hash = hashlib.sha256(test_data).hexdigest()

            # Verify
            assert _verify_checksum(temp_path, expected_hash) is True

        finally:
            temp_path.unlink()

    def test_verify_checksum_failure(self):
        """Test checksum verification failure."""
        # Create a temporary file with known content
        with tempfile.NamedTemporaryFile(delete=False) as f:
            test_data = b"Hello, World! This is test data."
            f.write(test_data)
            f.flush()
            temp_path = Path(f.name)

        try:
            # Use wrong hash
            wrong_hash = "0" * 64

            # Verify
            assert _verify_checksum(temp_path, wrong_hash) is False

        finally:
            temp_path.unlink()

    def test_verify_checksum_case_insensitive(self):
        """Test that checksum verification is case-insensitive."""
        with tempfile.NamedTemporaryFile(delete=False) as f:
            test_data = b"Test data"
            f.write(test_data)
            f.flush()
            temp_path = Path(f.name)

        try:
            expected_hash = hashlib.sha256(test_data).hexdigest()

            # Test with uppercase
            assert _verify_checksum(temp_path, expected_hash.upper()) is True
            # Test with lowercase
            assert _verify_checksum(temp_path, expected_hash.lower()) is True

        finally:
            temp_path.unlink()


class TestDownloadConfig:
    """Test download configuration."""

    def test_default_config(self):
        """Test default configuration values."""
        config = DownloadConfig()

        assert config.chunk_size == 8 * 1024 * 1024  # 8 MB
        assert config.max_workers == 6
        assert config.connect_timeout == 30.0  # 30 seconds to connect
        assert config.read_timeout == 60.0  # 60 seconds per read
        assert config.min_size_for_parallel == 10 * 1024 * 1024  # 10 MB
        assert config.max_retries == 3  # 3 retries per chunk

    def test_custom_config(self):
        """Test custom configuration values."""
        config = DownloadConfig(
            chunk_size=4 * 1024 * 1024,
            max_workers=8,
            connect_timeout=15.0,
            read_timeout=120.0,
            min_size_for_parallel=5 * 1024 * 1024,
        )

        assert config.chunk_size == 4 * 1024 * 1024
        assert config.max_workers == 8
        assert config.connect_timeout == 15.0
        assert config.read_timeout == 120.0
        assert config.min_size_for_parallel == 5 * 1024 * 1024

    def test_timeout_property(self):
        """Test that timeout property returns correct httpx.Timeout object."""
        config = DownloadConfig(connect_timeout=10.0, read_timeout=45.0)
        timeout = config.timeout

        assert isinstance(timeout, httpx.Timeout)
        assert timeout.connect == 10.0
        assert timeout.read == 45.0
        assert timeout.write == 30.0
        assert timeout.pool == 30.0


class TestParallelDownload:
    """Test parallel download functionality."""

    def test_fallback_to_single_threaded_no_range_support(self):
        """Test fallback when server doesn't support ranges."""
        # Mock server capabilities check
        mock_caps = ServerCapabilities(supports_ranges=False, content_length=100 * 1024 * 1024)

        test_data = b"Test file content"
        expected_hash = hashlib.sha256(test_data).hexdigest()

        # Create a mock streaming response
        mock_response = MagicMock()
        mock_response.headers = httpx.Headers({"Content-Length": str(len(test_data))})
        mock_response.status_code = 200
        mock_response.iter_bytes.return_value = iter([test_data])
        mock_response.raise_for_status = Mock()
        mock_response.__enter__ = Mock(return_value=mock_response)
        mock_response.__exit__ = Mock(return_value=False)

        mock_client = MagicMock()
        mock_client.stream.return_value = mock_response
        mock_client.__enter__ = Mock(return_value=mock_client)
        mock_client.__exit__ = Mock(return_value=False)

        with tempfile.TemporaryDirectory() as tmpdir:
            dest_path = Path(tmpdir) / "test.tar.zst"

            with (
                patch("clang_tool_chain.parallel_download.check_server_capabilities", return_value=mock_caps),
                patch("clang_tool_chain.parallel_download.httpx.Client", return_value=mock_client),
            ):
                download_file_parallel("https://example.com/file.tar.zst", dest_path, expected_hash)

                assert dest_path.exists()
                assert dest_path.read_bytes() == test_data

    def test_fallback_to_single_threaded_small_file(self):
        """Test fallback for files below size threshold."""
        # Mock server with range support but small file
        mock_caps = ServerCapabilities(supports_ranges=True, content_length=5 * 1024 * 1024)  # 5 MB

        test_data = b"Small file content"
        expected_hash = hashlib.sha256(test_data).hexdigest()

        # Create a mock streaming response
        mock_response = MagicMock()
        mock_response.headers = httpx.Headers({"Content-Length": str(len(test_data))})
        mock_response.status_code = 200
        mock_response.iter_bytes.return_value = iter([test_data])
        mock_response.raise_for_status = Mock()
        mock_response.__enter__ = Mock(return_value=mock_response)
        mock_response.__exit__ = Mock(return_value=False)

        mock_client = MagicMock()
        mock_client.stream.return_value = mock_response
        mock_client.__enter__ = Mock(return_value=mock_client)
        mock_client.__exit__ = Mock(return_value=False)

        with tempfile.TemporaryDirectory() as tmpdir:
            dest_path = Path(tmpdir) / "test.tar.zst"

            with (
                patch("clang_tool_chain.parallel_download.check_server_capabilities", return_value=mock_caps),
                patch("clang_tool_chain.parallel_download.httpx.Client", return_value=mock_client),
            ):
                download_file_parallel("https://example.com/file.tar.zst", dest_path, expected_hash)

                assert dest_path.exists()

    def test_checksum_verification_failure(self):
        """Test that download fails with wrong checksum."""
        from clang_tool_chain.manifest import ToolchainInfrastructureError

        mock_caps = ServerCapabilities(supports_ranges=False, content_length=100)

        test_data = b"Test data"
        wrong_hash = "0" * 64

        # Create a mock streaming response
        mock_response = MagicMock()
        mock_response.headers = httpx.Headers({"Content-Length": str(len(test_data))})
        mock_response.status_code = 200
        mock_response.iter_bytes.return_value = iter([test_data])
        mock_response.raise_for_status = Mock()
        mock_response.__enter__ = Mock(return_value=mock_response)
        mock_response.__exit__ = Mock(return_value=False)

        mock_client = MagicMock()
        mock_client.stream.return_value = mock_response
        mock_client.__enter__ = Mock(return_value=mock_client)
        mock_client.__exit__ = Mock(return_value=False)

        with tempfile.TemporaryDirectory() as tmpdir:
            dest_path = Path(tmpdir) / "test.tar.zst"

            with (
                patch("clang_tool_chain.parallel_download.check_server_capabilities", return_value=mock_caps),
                patch("clang_tool_chain.parallel_download.httpx.Client", return_value=mock_client),
            ):
                with pytest.raises(ToolchainInfrastructureError, match="Checksum verification failed"):
                    download_file_parallel("https://example.com/file.tar.zst", dest_path, wrong_hash)

                # Verify temp file was cleaned up
                assert not dest_path.exists()


class TestEnvironmentVariableConfiguration:
    """Test configuration via environment variables."""

    def test_config_from_environment(self):
        """Test that configuration can be loaded from environment variables."""
        from clang_tool_chain.archive import _get_download_config

        with patch.dict(
            os.environ,
            {
                "CLANG_TOOL_CHAIN_CHUNK_SIZE": "4",
                "CLANG_TOOL_CHAIN_MAX_WORKERS": "8",
                "CLANG_TOOL_CHAIN_MIN_SIZE": "20",
            },
        ):
            config = _get_download_config()

            assert config.chunk_size == 4 * 1024 * 1024
            assert config.max_workers == 8
            assert config.min_size_for_parallel == 20 * 1024 * 1024

    def test_config_invalid_values(self):
        """Test that invalid environment values fall back to defaults."""
        from clang_tool_chain.archive import _get_download_config

        with patch.dict(
            os.environ, {"CLANG_TOOL_CHAIN_CHUNK_SIZE": "invalid", "CLANG_TOOL_CHAIN_MAX_WORKERS": "not_a_number"}
        ):
            config = _get_download_config()

            # Should use defaults
            assert config.chunk_size == 8 * 1024 * 1024
            assert config.max_workers == 6

    def test_disable_parallel_env_var(self):
        """Test that parallel downloads can be disabled via environment."""
        # Need to reload the module to pick up the new environment variable
        import importlib

        import clang_tool_chain.archive

        with patch.dict(os.environ, {"CLANG_TOOL_CHAIN_DISABLE_PARALLEL": "1"}):
            # Reload module to pick up environment variable
            importlib.reload(clang_tool_chain.archive)

            with patch("clang_tool_chain.archive._download_file_legacy") as mock_legacy:
                mock_legacy.return_value = None

                with tempfile.TemporaryDirectory() as tmpdir:
                    dest_path = Path(tmpdir) / "test.tar.zst"
                    clang_tool_chain.archive.download_file("https://example.com/file.tar.zst", dest_path)

                    # Should have called legacy download
                    mock_legacy.assert_called_once()

            # Reload again to restore original state
            importlib.reload(clang_tool_chain.archive)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
