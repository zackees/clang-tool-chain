#!/usr/bin/env python3
"""
Unit tests for scripts.download_binaries module.

Tests the BinaryDownloader class and related functions for downloading
and extracting LLVM binaries.
"""

import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, Mock, mock_open, patch

# Add scripts directory to path
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

import download_binaries  # noqa: E402


class TestGetCurrentPlatform(unittest.TestCase):
    """Test the get_current_platform function."""

    @patch("platform.system")
    @patch("platform.machine")
    def test_windows_x86_64(self, mock_machine, mock_system):
        """Test detection of Windows x86_64."""
        mock_system.return_value = "Windows"
        mock_machine.return_value = "AMD64"
        result = download_binaries.get_current_platform()
        self.assertEqual(result, "win-x86_64")

    @patch("platform.system")
    @patch("platform.machine")
    def test_linux_x86_64(self, mock_machine, mock_system):
        """Test detection of Linux x86_64."""
        mock_system.return_value = "Linux"
        mock_machine.return_value = "x86_64"
        result = download_binaries.get_current_platform()
        self.assertEqual(result, "linux-x86_64")

    @patch("platform.system")
    @patch("platform.machine")
    def test_linux_aarch64(self, mock_machine, mock_system):
        """Test detection of Linux ARM64."""
        mock_system.return_value = "Linux"
        mock_machine.return_value = "aarch64"
        result = download_binaries.get_current_platform()
        self.assertEqual(result, "linux-aarch64")

    @patch("platform.system")
    @patch("platform.machine")
    def test_macos_x86_64(self, mock_machine, mock_system):
        """Test detection of macOS x86_64."""
        mock_system.return_value = "Darwin"
        mock_machine.return_value = "x86_64"
        result = download_binaries.get_current_platform()
        self.assertEqual(result, "darwin-x86_64")

    @patch("platform.system")
    @patch("platform.machine")
    def test_macos_arm64(self, mock_machine, mock_system):
        """Test detection of macOS ARM64."""
        mock_system.return_value = "Darwin"
        mock_machine.return_value = "arm64"
        result = download_binaries.get_current_platform()
        self.assertEqual(result, "darwin-arm64")

    @patch("platform.system")
    @patch("platform.machine")
    def test_unsupported_platform(self, mock_machine, mock_system):
        """Test detection of unsupported platform."""
        mock_system.return_value = "FreeBSD"
        mock_machine.return_value = "x86_64"
        result = download_binaries.get_current_platform()
        self.assertIsNone(result)


class TestBinaryDownloader(unittest.TestCase):
    """Test the BinaryDownloader class."""

    def setUp(self):
        """Set up test fixtures."""
        self.version = "21.1.5"
        self.output_dir = "test_downloads"
        self.downloader = download_binaries.BinaryDownloader(version=self.version, output_dir=self.output_dir)

    def test_init(self):
        """Test BinaryDownloader initialization."""
        self.assertEqual(self.downloader.version, self.version)
        self.assertEqual(self.downloader.output_dir, Path(self.output_dir))

    def test_init_creates_output_dir(self):
        """Test that output directory is created on init."""
        with patch("pathlib.Path.mkdir") as mock_mkdir:
            download_binaries.BinaryDownloader(version="21.1.5", output_dir="new_dir")
            mock_mkdir.assert_called_once_with(parents=True, exist_ok=True)

    @patch("urllib.request.urlretrieve")
    @patch("pathlib.Path.exists")
    @patch("builtins.print")
    def test_download_file_success(self, mock_print, mock_exists, mock_urlretrieve):
        """Test successful file download."""
        mock_exists.return_value = False
        url = "https://example.com/test.tar.xz"
        destination = Path("test.tar.xz")

        result = self.downloader.download_file(url, destination, show_progress=False)

        self.assertTrue(result)
        mock_urlretrieve.assert_called_once()
        # Check that it was called with the URL and destination
        args = mock_urlretrieve.call_args[0]
        self.assertEqual(args[0], url)
        self.assertEqual(args[1], destination)

    @patch("urllib.request.urlretrieve")
    @patch("pathlib.Path.exists")
    @patch("builtins.input")
    @patch("builtins.print")
    def test_download_file_existing_skip(self, mock_print, mock_input, mock_exists, mock_urlretrieve):
        """Test skipping download of existing file."""
        mock_exists.return_value = True
        mock_input.return_value = "n"
        url = "https://example.com/test.tar.xz"
        destination = Path("test.tar.xz")

        result = self.downloader.download_file(url, destination, show_progress=False)

        self.assertTrue(result)
        mock_urlretrieve.assert_not_called()

    @patch("urllib.request.urlretrieve")
    @patch("pathlib.Path.exists")
    @patch("builtins.input")
    @patch("builtins.print")
    def test_download_file_existing_overwrite(self, mock_print, mock_input, mock_exists, mock_urlretrieve):
        """Test overwriting existing file."""
        mock_exists.return_value = True
        mock_input.return_value = "y"
        url = "https://example.com/test.tar.xz"
        destination = Path("test.tar.xz")

        result = self.downloader.download_file(url, destination, show_progress=False)

        self.assertTrue(result)
        mock_urlretrieve.assert_called_once()

    @patch("urllib.request.urlretrieve")
    @patch("pathlib.Path.exists")
    @patch("builtins.print")
    def test_download_file_error(self, mock_print, mock_exists, mock_urlretrieve):
        """Test handling of download error."""
        mock_exists.return_value = False
        mock_urlretrieve.side_effect = Exception("Network error")
        url = "https://example.com/test.tar.xz"
        destination = Path("test.tar.xz")

        result = self.downloader.download_file(url, destination, show_progress=False)

        self.assertFalse(result)

    @patch("tarfile.open")
    @patch("pathlib.Path.mkdir")
    @patch("builtins.print")
    def test_extract_archive_success(self, mock_print, mock_mkdir, mock_tarfile):
        """Test successful archive extraction."""
        mock_tar = MagicMock()
        mock_tarfile.return_value.__enter__.return_value = mock_tar
        archive_path = Path("test.tar.xz")
        extract_dir = Path("extracted")

        result = self.downloader.extract_archive(archive_path, extract_dir)

        self.assertTrue(result)
        mock_tar.extractall.assert_called_once_with(extract_dir)

    @patch("tarfile.open")
    @patch("pathlib.Path.mkdir")
    @patch("builtins.print")
    def test_extract_archive_error(self, mock_print, mock_mkdir, mock_tarfile):
        """Test handling of extraction error."""
        mock_tarfile.side_effect = Exception("Extraction error")
        archive_path = Path("test.tar.xz")
        extract_dir = Path("extracted")

        result = self.downloader.extract_archive(archive_path, extract_dir)

        self.assertFalse(result)

    @patch("subprocess.run")
    @patch("shutil.which")
    @patch("pathlib.Path.mkdir")
    @patch("builtins.print")
    def test_extract_windows_installer_with_7zip(self, mock_print, mock_mkdir, mock_which, mock_run):
        """Test Windows installer extraction with 7zip."""
        mock_which.return_value = "C:\\Program Files\\7-Zip\\7z.exe"
        mock_run.return_value = Mock(returncode=0)
        installer_path = Path("LLVM-21.1.5-win64.exe")
        extract_dir = Path("extracted")

        result = self.downloader.extract_windows_installer(installer_path, extract_dir)

        self.assertTrue(result)
        mock_run.assert_called_once()
        # Check that 7z was called
        args = mock_run.call_args[0][0]
        self.assertEqual(args[0], "7z")

    @patch("subprocess.run")
    @patch("shutil.which")
    @patch("pathlib.Path.mkdir")
    @patch("builtins.print")
    def test_extract_windows_installer_no_7zip(self, mock_print, mock_mkdir, mock_which, mock_run):
        """Test Windows installer extraction without 7zip."""
        mock_which.return_value = None
        installer_path = Path("LLVM-21.1.5-win64.exe")
        extract_dir = Path("extracted")

        result = self.downloader.extract_windows_installer(installer_path, extract_dir)

        self.assertFalse(result)

    def test_download_platform_unknown(self):
        """Test download with unknown platform."""
        with patch("builtins.print"):
            result = self.downloader.download_platform("unknown-platform")
            self.assertIsNone(result)

    @patch.object(download_binaries.BinaryDownloader, "download_file")
    @patch.object(download_binaries.BinaryDownloader, "extract_archive")
    @patch("builtins.print")
    def test_download_platform_success(self, mock_print, mock_extract, mock_download):
        """Test successful platform download."""
        mock_download.return_value = True
        mock_extract.return_value = True

        result = self.downloader.download_platform("linux-x86_64")

        self.assertIsNotNone(result)
        mock_download.assert_called_once()
        mock_extract.assert_called_once()

    @patch.object(download_binaries.BinaryDownloader, "download_file")
    @patch("builtins.print")
    def test_download_platform_download_fail(self, mock_print, mock_download):
        """Test platform download failure."""
        mock_download.return_value = False

        result = self.downloader.download_platform("linux-x86_64")

        self.assertIsNone(result)

    @patch.object(download_binaries.BinaryDownloader, "download_file")
    @patch.object(download_binaries.BinaryDownloader, "extract_archive")
    @patch("builtins.print")
    def test_download_platform_extract_fail(self, mock_print, mock_extract, mock_download):
        """Test platform extraction failure."""
        mock_download.return_value = True
        mock_extract.return_value = False

        result = self.downloader.download_platform("linux-x86_64")

        self.assertIsNone(result)

    @patch.object(download_binaries.BinaryDownloader, "download_file")
    @patch("builtins.print")
    def test_download_platform_with_alternative(self, mock_print, mock_download):
        """Test platform download with alternative URL."""
        # First download fails, second succeeds
        mock_download.side_effect = [False, True]

        with patch.object(download_binaries.BinaryDownloader, "extract_windows_installer") as mock_extract:
            mock_extract.return_value = True
            self.downloader.download_platform("win-x86_64")

        # Should have tried twice
        self.assertEqual(mock_download.call_count, 2)

    @patch.object(download_binaries.BinaryDownloader, "download_platform")
    @patch("builtins.print")
    def test_download_all_default(self, mock_print, mock_download_platform):
        """Test downloading all platforms."""
        mock_download_platform.return_value = Path("extracted")

        results = self.downloader.download_all()

        # Should download all platforms in BINARY_CONFIGS
        self.assertEqual(mock_download_platform.call_count, len(download_binaries.BINARY_CONFIGS))
        self.assertEqual(len(results), len(download_binaries.BINARY_CONFIGS))

    @patch.object(download_binaries.BinaryDownloader, "download_platform")
    @patch("builtins.print")
    def test_download_all_specific_platforms(self, mock_print, mock_download_platform):
        """Test downloading specific platforms."""
        mock_download_platform.return_value = Path("extracted")
        platforms = ["linux-x86_64", "darwin-arm64"]

        results = self.downloader.download_all(platforms=platforms)

        # Should download only specified platforms
        self.assertEqual(mock_download_platform.call_count, 2)
        self.assertEqual(len(results), 2)
        self.assertIn("linux-x86_64", results)
        self.assertIn("darwin-arm64", results)


class TestChecksumVerification(unittest.TestCase):
    """Test checksum verification functionality."""

    def setUp(self):
        """Set up test fixtures."""
        self.downloader = download_binaries.BinaryDownloader(
            version="21.1.5", output_dir="test_downloads", verify_checksums=True
        )

    @patch("builtins.open", new_callable=mock_open, read_data=b"test content")
    def test_compute_sha256(self, mock_file):
        """Test SHA256 computation."""
        test_path = Path("test_file.txt")
        checksum = self.downloader.compute_sha256(test_path)

        # SHA256 of "test content"
        expected = "6ae8a75555209fd6c44157c0aed8016e763ff435a19cf186f76863140143ff72"
        self.assertEqual(checksum, expected)
        mock_file.assert_called_once_with(test_path, "rb")

    @patch.object(download_binaries.BinaryDownloader, "compute_sha256")
    @patch("builtins.print")
    def test_verify_checksum_match(self, mock_print, mock_compute):
        """Test checksum verification with matching checksum."""
        test_path = Path("test.tar.xz")
        expected = "abc123"
        mock_compute.return_value = "abc123"

        result = self.downloader.verify_checksum(test_path, expected)

        self.assertTrue(result)
        mock_compute.assert_called_once_with(test_path)

    @patch.object(download_binaries.BinaryDownloader, "compute_sha256")
    @patch("builtins.print")
    def test_verify_checksum_mismatch(self, mock_print, mock_compute):
        """Test checksum verification with mismatched checksum."""
        test_path = Path("test.tar.xz")
        expected = "abc123"
        mock_compute.return_value = "def456"

        result = self.downloader.verify_checksum(test_path, expected)

        self.assertFalse(result)

    @patch("builtins.print")
    def test_verify_checksum_disabled(self, mock_print):
        """Test checksum verification when disabled."""
        downloader = download_binaries.BinaryDownloader(version="21.1.5", verify_checksums=False)
        test_path = Path("test.tar.xz")

        result = downloader.verify_checksum(test_path, "any_checksum")

        self.assertTrue(result)

    @patch("builtins.print")
    def test_verify_checksum_no_expected(self, mock_print):
        """Test checksum verification with no expected checksum."""
        test_path = Path("test.tar.xz")

        result = self.downloader.verify_checksum(test_path, None)

        self.assertTrue(result)

    @patch.object(download_binaries.BinaryDownloader, "compute_sha256")
    @patch("builtins.print")
    def test_verify_checksum_case_insensitive(self, mock_print, mock_compute):
        """Test checksum verification is case insensitive."""
        test_path = Path("test.tar.xz")
        expected = "ABC123"
        mock_compute.return_value = "abc123"

        result = self.downloader.verify_checksum(test_path, expected)

        self.assertTrue(result)

    @patch.object(download_binaries.BinaryDownloader, "compute_sha256")
    @patch("builtins.print")
    def test_verify_checksum_error(self, mock_print, mock_compute):
        """Test checksum verification error handling."""
        test_path = Path("test.tar.xz")
        mock_compute.side_effect = Exception("File read error")

        result = self.downloader.verify_checksum(test_path, "abc123")

        self.assertFalse(result)

    @patch("urllib.request.urlretrieve")
    @patch("pathlib.Path.exists")
    @patch("builtins.print")
    @patch.object(download_binaries.BinaryDownloader, "verify_checksum")
    def test_download_file_with_checksum_verification(self, mock_verify, mock_print, mock_exists, mock_urlretrieve):
        """Test file download with checksum verification."""
        mock_exists.return_value = False
        mock_verify.return_value = True

        url = "https://example.com/file.tar.xz"
        dest = Path("downloads/file.tar.xz")
        checksum = "abc123"

        result = self.downloader.download_file(url, dest, expected_checksum=checksum)

        self.assertTrue(result)
        mock_verify.assert_called_once_with(dest, checksum)

    @patch("urllib.request.urlretrieve")
    @patch("pathlib.Path.exists")
    @patch("builtins.print")
    @patch.object(download_binaries.BinaryDownloader, "verify_checksum")
    def test_download_file_checksum_fail(self, mock_verify, mock_print, mock_exists, mock_urlretrieve):
        """Test file download with failed checksum verification."""
        mock_exists.return_value = False
        mock_verify.return_value = False

        url = "https://example.com/file.tar.xz"
        dest = Path("downloads/file.tar.xz")
        checksum = "abc123"

        result = self.downloader.download_file(url, dest, expected_checksum=checksum)

        self.assertFalse(result)

    @patch("pathlib.Path.exists")
    @patch("builtins.print")
    @patch.object(download_binaries.BinaryDownloader, "verify_checksum")
    def test_download_file_existing_verified(self, mock_verify, mock_print, mock_exists):
        """Test skipping download when existing file is verified."""
        mock_exists.return_value = True
        mock_verify.return_value = True

        url = "https://example.com/file.tar.xz"
        dest = Path("downloads/file.tar.xz")
        checksum = "abc123"

        result = self.downloader.download_file(url, dest, expected_checksum=checksum)

        self.assertTrue(result)
        mock_verify.assert_called_once_with(dest, checksum)

    @patch("urllib.request.urlretrieve")
    @patch("pathlib.Path.exists")
    @patch("builtins.print")
    @patch.object(download_binaries.BinaryDownloader, "verify_checksum")
    def test_download_file_existing_reverify(self, mock_verify, mock_print, mock_exists, mock_urlretrieve):
        """Test re-downloading when existing file fails verification."""
        mock_exists.return_value = True
        # First verification fails (existing file), second succeeds (new download)
        mock_verify.side_effect = [False, True]

        url = "https://example.com/file.tar.xz"
        dest = Path("downloads/file.tar.xz")
        checksum = "abc123"

        result = self.downloader.download_file(url, dest, expected_checksum=checksum)

        self.assertTrue(result)
        # Should verify twice: once for existing, once for new
        self.assertEqual(mock_verify.call_count, 2)
        mock_urlretrieve.assert_called_once()


class TestBinaryConfigs(unittest.TestCase):
    """Test binary configuration constants."""

    def test_binary_configs_exist(self):
        """Test that BINARY_CONFIGS is defined."""
        self.assertIsNotNone(download_binaries.BINARY_CONFIGS)
        self.assertIsInstance(download_binaries.BINARY_CONFIGS, dict)

    def test_binary_configs_platforms(self):
        """Test that all expected platforms are configured."""
        expected_platforms = [
            "win-x86_64",
            "linux-x86_64",
            "linux-aarch64",
            "darwin-x86_64",
            "darwin-arm64",
        ]
        for platform in expected_platforms:
            self.assertIn(platform, download_binaries.BINARY_CONFIGS)

    def test_binary_configs_structure(self):
        """Test that each config has required fields."""
        for platform, config in download_binaries.BINARY_CONFIGS.items():
            self.assertIn("filename", config, f"{platform} missing filename")
            self.assertIn("url", config, f"{platform} missing url")
            self.assertIn("type", config, f"{platform} missing type")

    def test_default_version(self):
        """Test that DEFAULT_VERSION is defined."""
        self.assertIsNotNone(download_binaries.DEFAULT_VERSION)
        self.assertIsInstance(download_binaries.DEFAULT_VERSION, str)

    def test_github_release_url(self):
        """Test that GITHUB_RELEASE_URL is defined."""
        self.assertIsNotNone(download_binaries.GITHUB_RELEASE_URL)
        self.assertTrue(download_binaries.GITHUB_RELEASE_URL.startswith("https://"))


if __name__ == "__main__":
    unittest.main()
