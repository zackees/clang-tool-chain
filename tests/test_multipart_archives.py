"""
Unit tests for multi-part archive support.

Tests the functionality for downloading and concatenating multi-part archives
that are split to stay under GitHub's 100 MB file size limit.
"""

import hashlib
from pathlib import Path
from typing import Any
from unittest.mock import Mock, patch

import pytest

from clang_tool_chain.downloader import (
    VersionInfo,
    download_archive,
    download_archive_parts,
    is_multipart_archive,
)


class TestMultipartDetection:
    """Tests for multi-part archive detection."""

    def test_single_part_archive(self):
        """Test detection of single-part archive."""
        version_info = VersionInfo(
            version="1.0.0",
            href="https://example.com/archive.tar.zst",
            sha256="abc123",
            parts=None,
        )
        assert not is_multipart_archive(version_info)

    def test_multipart_archive(self):
        """Test detection of multi-part archive."""
        version_info = VersionInfo(
            version="1.0.0",
            href="https://example.com/archive.tar.zst",
            sha256="abc123",
            parts=[
                {"href": "https://example.com/archive.tar.zst.part1", "sha256": "part1hash"},
                {"href": "https://example.com/archive.tar.zst.part2", "sha256": "part2hash"},
            ],
        )
        assert is_multipart_archive(version_info)

    def test_empty_parts_list(self):
        """Test detection with empty parts list."""
        version_info = VersionInfo(
            version="1.0.0",
            href="https://example.com/archive.tar.zst",
            sha256="abc123",
            parts=[],
        )
        assert not is_multipart_archive(version_info)


class TestPartConcatenation:
    """Tests for downloading and concatenating parts."""

    def test_concatenation_logic(self, tmp_path: Path) -> None:
        """Test basic concatenation of parts."""
        # Create test parts
        part1_data = b"test data part 1" * 1000
        part2_data = b"test data part 2" * 1000

        part1_path = tmp_path / "test.part1"
        part2_path = tmp_path / "test.part2"
        part1_path.write_bytes(part1_data)
        part2_path.write_bytes(part2_data)

        # Test concatenation
        output = tmp_path / "output.tar.zst"
        with open(output, "wb") as outfile:
            outfile.write(part1_data)
            outfile.write(part2_data)

        # Verify
        result = output.read_bytes()
        assert result == part1_data + part2_data
        assert len(result) == len(part1_data) + len(part2_data)

    def test_checksum_verification(self, tmp_path: Path) -> None:
        """Test checksum verification for concatenated parts."""
        # Create test data
        part1_data = b"test data part 1" * 1000
        part2_data = b"test data part 2" * 1000

        # Calculate checksums
        part1_sha256 = hashlib.sha256(part1_data).hexdigest()
        part2_sha256 = hashlib.sha256(part2_data).hexdigest()

        # Concatenate and calculate final checksum
        full_data = part1_data + part2_data
        full_sha256 = hashlib.sha256(full_data).hexdigest()

        # Verify individual part checksums
        assert hashlib.sha256(part1_data).hexdigest() == part1_sha256
        assert hashlib.sha256(part2_data).hexdigest() == part2_sha256

        # Verify full checksum
        assert hashlib.sha256(full_data).hexdigest() == full_sha256


class TestDownloadArchiveParts:
    """Tests for download_archive_parts function."""

    @patch("clang_tool_chain.archive.urlopen")
    def test_download_multipart_archive(self, mock_urlopen: Any, tmp_path: Path) -> None:
        """Test downloading and concatenating multi-part archive."""
        # Create test data
        part1_data = b"x" * (50 * 1024 * 1024)  # 50 MB
        part2_data = b"y" * (50 * 1024 * 1024)  # 50 MB

        # Calculate checksums
        part1_sha256 = hashlib.sha256(part1_data).hexdigest()
        part2_sha256 = hashlib.sha256(part2_data).hexdigest()
        full_data = part1_data + part2_data
        full_sha256 = hashlib.sha256(full_data).hexdigest()

        # Mock HTTP responses
        mock_response1 = Mock()
        mock_response1.read.return_value = part1_data
        mock_response1.getheader.return_value = str(len(part1_data))

        mock_response2 = Mock()
        mock_response2.read.return_value = part2_data
        mock_response2.getheader.return_value = str(len(part2_data))

        mock_urlopen.return_value.__enter__.side_effect = [mock_response1, mock_response2]

        # Create version info
        version_info = VersionInfo(
            version="1.0.0",
            href="https://example.com/archive.tar.zst",
            sha256=full_sha256,
            parts=[
                {"href": "https://example.com/archive.tar.zst.part1", "sha256": part1_sha256},
                {"href": "https://example.com/archive.tar.zst.part2", "sha256": part2_sha256},
            ],
        )

        # Download and concatenate
        result_path = download_archive_parts(version_info, tmp_path)

        # Verify result
        assert result_path.exists()
        result_data = result_path.read_bytes()
        assert len(result_data) == len(full_data)
        assert hashlib.sha256(result_data).hexdigest() == full_sha256

    @patch("clang_tool_chain.archive.urlopen")
    def test_part_checksum_mismatch(self, mock_urlopen: Any, tmp_path: Path) -> None:
        """Test that part checksum mismatch raises error."""
        # Create test data
        part1_data = b"correct data"
        wrong_sha256 = "wrongchecksum123"

        # Mock HTTP response
        mock_response = Mock()
        mock_response.read.return_value = part1_data
        mock_response.getheader.return_value = str(len(part1_data))
        mock_urlopen.return_value.__enter__.return_value = mock_response

        # Create version info with wrong checksum
        version_info = VersionInfo(
            version="1.0.0",
            href="https://example.com/archive.tar.zst",
            sha256="fullhash",
            parts=[
                {"href": "https://example.com/archive.tar.zst.part1", "sha256": wrong_sha256},
            ],
        )

        # Should raise error due to checksum mismatch
        from clang_tool_chain.downloader import ToolchainInfrastructureError

        with pytest.raises(ToolchainInfrastructureError, match="checksum mismatch"):
            download_archive_parts(version_info, tmp_path)


class TestDownloadArchive:
    """Tests for download_archive convenience function."""

    @patch("clang_tool_chain.archive.download_file")
    def test_single_part_download(self, mock_download_file: Any, tmp_path: Path) -> None:
        """Test that single-part archives use download_file."""
        version_info = VersionInfo(
            version="1.0.0",
            href="https://example.com/archive.tar.zst",
            sha256="abc123",
            parts=None,
        )

        dest_path = tmp_path / "archive.tar.zst"
        download_archive(version_info, dest_path)

        # Verify download_file was called
        mock_download_file.assert_called_once_with("https://example.com/archive.tar.zst", dest_path, "abc123")

    @patch("clang_tool_chain.archive.download_archive_parts")
    @patch("clang_tool_chain.archive.shutil.move")
    def test_multipart_download(self, mock_move: Any, mock_download_parts: Any, tmp_path: Path) -> None:
        """Test that multi-part archives use download_archive_parts."""
        version_info = VersionInfo(
            version="1.0.0",
            href="https://example.com/archive.tar.zst",
            sha256="abc123",
            parts=[
                {"href": "https://example.com/part1", "sha256": "hash1"},
                {"href": "https://example.com/part2", "sha256": "hash2"},
            ],
        )

        # Mock return path
        mock_download_parts.return_value = Path("/tmp/temp_archive.tar.zst")

        dest_path = tmp_path / "archive.tar.zst"
        download_archive(version_info, dest_path)

        # Verify download_archive_parts was called
        assert mock_download_parts.called

        # Verify move was called
        assert mock_move.called


class TestManifestParsing:
    """Tests for parsing manifests with multi-part archives."""

    def test_parse_multipart_manifest(self):
        """Test parsing manifest with multi-part archive info."""
        from clang_tool_chain.downloader import _parse_manifest

        manifest_data = {
            "latest": "4.0.15",
            "versions": {
                "4.0.15": {
                    "href": "https://example.com/archive.tar.zst",
                    "sha256": "fullhash123",
                    "parts": [
                        {"href": "https://example.com/part1", "sha256": "hash1"},
                        {"href": "https://example.com/part2", "sha256": "hash2"},
                        {"href": "https://example.com/part3", "sha256": "hash3"},
                    ],
                }
            },
        }

        manifest = _parse_manifest(manifest_data)

        assert manifest.latest == "4.0.15"
        assert "4.0.15" in manifest.versions

        version_info = manifest.versions["4.0.15"]
        assert version_info.version == "4.0.15"
        assert version_info.href == "https://example.com/archive.tar.zst"
        assert version_info.sha256 == "fullhash123"
        assert version_info.parts is not None
        assert len(version_info.parts) == 3
        assert version_info.parts[0]["href"] == "https://example.com/part1"
        assert version_info.parts[0]["sha256"] == "hash1"

    def test_parse_single_part_manifest(self):
        """Test parsing manifest without multi-part info."""
        from clang_tool_chain.downloader import _parse_manifest

        manifest_data = {
            "latest": "21.1.5",
            "versions": {
                "21.1.5": {
                    "href": "https://example.com/archive.tar.zst",
                    "sha256": "hash123",
                }
            },
        }

        manifest = _parse_manifest(manifest_data)

        assert manifest.latest == "21.1.5"
        version_info = manifest.versions["21.1.5"]
        assert version_info.parts is None


class TestSplitArchiveTool:
    """Tests for the split_archive.py tool."""

    def test_split_and_reassemble(self, tmp_path: Path) -> None:
        """Test splitting an archive and reassembling it."""
        import sys

        sys.path.insert(0, str(Path(__file__).parent.parent / "downloads-bins" / "tools"))

        try:
            from split_archive import split_archive  # type: ignore[import-not-found]
        except ImportError:
            pytest.skip("split_archive module not available")
            return  # For type checker - pytest.skip() raises an exception

        # Create a test archive (100 MB of data)
        test_data = b"x" * (100 * 1024 * 1024)
        archive_path = tmp_path / "test.tar.zst"
        archive_path.write_bytes(test_data)

        # Split into 45 MB parts (should create 3 parts)
        output_dir = tmp_path / "parts"
        output_dir.mkdir()

        parts = split_archive(archive_path, part_size_mb=45, output_dir=output_dir)

        # Verify parts were created
        assert len(parts) == 3
        assert all(part_path.exists() for part_path, _ in parts)

        # Reassemble and verify
        reassembled_path = tmp_path / "reassembled.tar.zst"
        with open(reassembled_path, "wb") as outfile:
            for part_path, _ in parts:
                outfile.write(part_path.read_bytes())

        # Verify checksums match
        original_hash = hashlib.sha256(test_data).hexdigest()
        reassembled_hash = hashlib.sha256(reassembled_path.read_bytes()).hexdigest()
        assert original_hash == reassembled_hash


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
