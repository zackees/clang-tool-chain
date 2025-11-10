"""
Tests for the downloader module.
"""

import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, Mock, patch

from clang_tool_chain import downloader


class TestDownloader(unittest.TestCase):
    """Test cases for downloader module."""

    def test_get_home_toolchain_dir(self) -> None:
        """Test that get_home_toolchain_dir returns correct path."""
        result = downloader.get_home_toolchain_dir()
        self.assertIsInstance(result, Path)
        self.assertTrue(str(result).endswith(".clang-tool-chain"))

    def test_get_lock_path(self) -> None:
        """Test that get_lock_path returns correct lock file path."""
        result = downloader.get_lock_path("linux", "x86_64")
        self.assertIsInstance(result, Path)
        self.assertTrue(str(result).endswith("linux-x86_64.lock"))

    def test_get_install_dir(self) -> None:
        """Test that get_install_dir returns correct installation path."""
        result = downloader.get_install_dir("darwin", "arm64")
        self.assertIsInstance(result, Path)
        self.assertTrue(str(result).endswith("darwin/arm64") or str(result).endswith("darwin\\arm64"))

    def test_verify_checksum_success(self) -> None:
        """Test checksum verification with correct hash."""
        with tempfile.NamedTemporaryFile(delete=False) as tmp:
            tmp.write(b"test content")
            tmp_path = Path(tmp.name)

        try:
            # Calculate expected hash
            expected_hash = hashlib.sha256(b"test content").hexdigest()
            result = downloader.verify_checksum(tmp_path, expected_hash)
            self.assertTrue(result)
        finally:
            tmp_path.unlink()

    def test_verify_checksum_failure(self) -> None:
        """Test checksum verification with incorrect hash."""
        with tempfile.NamedTemporaryFile(delete=False) as tmp:
            tmp.write(b"test content")
            tmp_path = Path(tmp.name)

        try:
            wrong_hash = "0" * 64
            result = downloader.verify_checksum(tmp_path, wrong_hash)
            self.assertFalse(result)
        finally:
            tmp_path.unlink()

    @patch("clang_tool_chain.downloader.urlopen")
    def test_fetch_json_raw(self, mock_urlopen: Mock) -> None:
        """Test fetching JSON from URL."""
        test_data = {"key": "value", "number": 42}
        mock_response = MagicMock()
        mock_response.read.return_value = json.dumps(test_data).encode("utf-8")
        mock_response.__enter__.return_value = mock_response
        mock_urlopen.return_value = mock_response

        result = downloader._fetch_json_raw("http://test.com/data.json")
        self.assertEqual(result, test_data)

    def test_parse_root_manifest(self) -> None:
        """Test parsing root manifest with comprehensive data."""
        test_data = {
            "platforms": [
                {
                    "platform": "win",
                    "architectures": [{"arch": "x86_64", "manifest_path": "win/x86_64/manifest.json"}],
                },
                {
                    "platform": "linux",
                    "architectures": [
                        {"arch": "x86_64", "manifest_path": "linux/x86_64/manifest.json"},
                        {"arch": "arm64", "manifest_path": "linux/arm64/manifest.json"},
                    ],
                },
                {
                    "platform": "darwin",
                    "architectures": [
                        {"arch": "x86_64", "manifest_path": "darwin/x86_64/manifest.json"},
                        {"arch": "arm64", "manifest_path": "darwin/arm64/manifest.json"},
                    ],
                },
            ]
        }

        result = downloader._parse_root_manifest(test_data)

        # Verify structure
        self.assertIsInstance(result, downloader.RootManifest)
        self.assertEqual(len(result.platforms), 3)

        # Verify Windows platform
        win_platform = result.platforms[0]
        self.assertEqual(win_platform.platform, "win")
        self.assertEqual(len(win_platform.architectures), 1)
        self.assertEqual(win_platform.architectures[0].arch, "x86_64")
        self.assertEqual(win_platform.architectures[0].manifest_path, "win/x86_64/manifest.json")

        # Verify Linux platform
        linux_platform = result.platforms[1]
        self.assertEqual(linux_platform.platform, "linux")
        self.assertEqual(len(linux_platform.architectures), 2)
        self.assertEqual(linux_platform.architectures[0].arch, "x86_64")
        self.assertEqual(linux_platform.architectures[1].arch, "arm64")

        # Verify Darwin platform
        darwin_platform = result.platforms[2]
        self.assertEqual(darwin_platform.platform, "darwin")
        self.assertEqual(len(darwin_platform.architectures), 2)

    @patch("clang_tool_chain.downloader._fetch_json_raw")
    def test_fetch_root_manifest(self, mock_fetch_json_raw: Mock) -> None:
        """Test fetching root manifest via network."""
        test_data = {
            "platforms": [
                {
                    "platform": "linux",
                    "architectures": [{"arch": "x86_64", "manifest_path": "linux/x86_64/manifest.json"}],
                }
            ]
        }
        mock_fetch_json_raw.return_value = test_data

        result = downloader.fetch_root_manifest()
        self.assertIsInstance(result, downloader.RootManifest)
        self.assertEqual(len(result.platforms), 1)
        self.assertEqual(result.platforms[0].platform, "linux")
        self.assertEqual(len(result.platforms[0].architectures), 1)
        self.assertEqual(result.platforms[0].architectures[0].arch, "x86_64")
        self.assertEqual(result.platforms[0].architectures[0].manifest_path, "linux/x86_64/manifest.json")

    def test_parse_manifest(self) -> None:
        """Test parsing platform manifest with multiple versions."""
        test_data = {
            "latest": "21.1.5",
            "21.1.5": {
                "href": "https://example.com/llvm-21.1.5-win-x86_64.tar.zst",
                "sha256": "abc123def456",
            },
            "21.1.4": {
                "href": "https://example.com/llvm-21.1.4-win-x86_64.tar.zst",
                "sha256": "xyz789uvw012",
            },
            "20.0.0": {
                "href": "https://example.com/llvm-20.0.0-win-x86_64.tar.zst",
                "sha256": "old111old222",
            },
        }

        result = downloader._parse_manifest(test_data)

        # Verify structure
        self.assertIsInstance(result, downloader.Manifest)
        self.assertEqual(result.latest, "21.1.5")
        self.assertEqual(len(result.versions), 3)

        # Verify latest version
        self.assertIn("21.1.5", result.versions)
        latest_info = result.versions["21.1.5"]
        self.assertIsInstance(latest_info, downloader.VersionInfo)
        self.assertEqual(latest_info.version, "21.1.5")
        self.assertEqual(latest_info.href, "https://example.com/llvm-21.1.5-win-x86_64.tar.zst")
        self.assertEqual(latest_info.sha256, "abc123def456")

        # Verify older version
        self.assertIn("21.1.4", result.versions)
        old_info = result.versions["21.1.4"]
        self.assertEqual(old_info.version, "21.1.4")
        self.assertEqual(old_info.href, "https://example.com/llvm-21.1.4-win-x86_64.tar.zst")
        self.assertEqual(old_info.sha256, "xyz789uvw012")

        # Verify oldest version
        self.assertIn("20.0.0", result.versions)
        oldest_info = result.versions["20.0.0"]
        self.assertEqual(oldest_info.version, "20.0.0")

    @patch("clang_tool_chain.downloader._fetch_json_raw")
    def test_fetch_platform_manifest(self, mock_fetch_json_raw: Mock) -> None:
        """Test fetching platform-specific manifest."""
        root_manifest_data = {
            "platforms": [
                {
                    "platform": "win",
                    "architectures": [{"arch": "x86_64", "manifest_path": "win/x86_64/manifest.json"}],
                }
            ]
        }
        platform_manifest_data = {
            "latest": "21.1.5",
            "21.1.5": {"href": "http://example.com/file.tar.zst", "sha256": "abc123"},
        }

        mock_fetch_json_raw.side_effect = [root_manifest_data, platform_manifest_data]

        result = downloader.fetch_platform_manifest("win", "x86_64")
        self.assertIsInstance(result, downloader.Manifest)
        self.assertEqual(result.latest, "21.1.5")
        self.assertIn("21.1.5", result.versions)
        self.assertEqual(result.versions["21.1.5"].version, "21.1.5")
        self.assertEqual(result.versions["21.1.5"].href, "http://example.com/file.tar.zst")
        self.assertEqual(result.versions["21.1.5"].sha256, "abc123")

    @patch("clang_tool_chain.downloader._fetch_json_raw")
    def test_fetch_platform_manifest_not_found(self, mock_fetch_json_raw: Mock) -> None:
        """Test fetching platform manifest for unsupported platform."""
        root_manifest_data = {
            "platforms": [
                {
                    "platform": "linux",
                    "architectures": [{"arch": "x86_64", "manifest_path": "linux/x86_64/manifest.json"}],
                }
            ]
        }
        mock_fetch_json_raw.return_value = root_manifest_data

        with self.assertRaises(RuntimeError) as context:
            downloader.fetch_platform_manifest("unsupported", "unknown")

        self.assertIn("not found in manifest", str(context.exception))

    @patch("clang_tool_chain.downloader._fetch_json_raw")
    def test_manifest_integration_flow(self, mock_fetch_json_raw: Mock) -> None:
        """Test full integration flow: root manifest -> platform manifest -> version info."""
        # Simulate complete root manifest
        root_manifest_data = {
            "platforms": [
                {
                    "platform": "win",
                    "architectures": [{"arch": "x86_64", "manifest_path": "win/x86_64/manifest.json"}],
                },
                {
                    "platform": "linux",
                    "architectures": [
                        {"arch": "x86_64", "manifest_path": "linux/x86_64/manifest.json"},
                        {"arch": "arm64", "manifest_path": "linux/arm64/manifest.json"},
                    ],
                },
                {
                    "platform": "darwin",
                    "architectures": [
                        {"arch": "x86_64", "manifest_path": "darwin/x86_64/manifest.json"},
                        {"arch": "arm64", "manifest_path": "darwin/arm64/manifest.json"},
                    ],
                },
            ]
        }

        # Simulate Windows x86_64 platform manifest
        win_manifest_data = {
            "latest": "21.1.5",
            "21.1.5": {
                "href": "https://raw.githubusercontent.com/zackees/clang-tool-chain-bins/main/clang/win/x86_64/llvm-21.1.5-win-x86_64.tar.zst",
                "sha256": "3c21e45edeee591fe8ead5427d25b62ddb26c409575b41db03d6777c77bba44f",
            },
        }

        # Simulate Linux arm64 platform manifest
        linux_arm64_manifest_data = {
            "latest": "21.1.5",
            "21.1.5": {
                "href": "https://raw.githubusercontent.com/zackees/clang-tool-chain-bins/main/clang/linux/arm64/llvm-21.1.5-linux-arm64.tar.zst",
                "sha256": "deadbeefcafebabe0123456789abcdef0123456789abcdef0123456789abcdef",
            },
        }

        # Test Windows x86_64
        mock_fetch_json_raw.side_effect = [root_manifest_data, win_manifest_data]
        win_manifest = downloader.fetch_platform_manifest("win", "x86_64")

        # Verify root manifest was parsed correctly
        self.assertIsInstance(win_manifest, downloader.Manifest)
        self.assertEqual(win_manifest.latest, "21.1.5")

        # Verify version info
        version, url, sha256 = downloader.get_latest_version_info(win_manifest)
        self.assertEqual(version, "21.1.5")
        self.assertIn("llvm-21.1.5-win-x86_64.tar.zst", url)
        self.assertEqual(sha256, "3c21e45edeee591fe8ead5427d25b62ddb26c409575b41db03d6777c77bba44f")

        # Test Linux arm64
        mock_fetch_json_raw.side_effect = [root_manifest_data, linux_arm64_manifest_data]
        linux_manifest = downloader.fetch_platform_manifest("linux", "arm64")

        self.assertIsInstance(linux_manifest, downloader.Manifest)
        self.assertEqual(linux_manifest.latest, "21.1.5")

        # Verify version info for Linux
        version, url, sha256 = downloader.get_latest_version_info(linux_manifest)
        self.assertEqual(version, "21.1.5")
        self.assertIn("llvm-21.1.5-linux-arm64.tar.zst", url)
        self.assertEqual(sha256, "deadbeefcafebabe0123456789abcdef0123456789abcdef0123456789abcdef")

    def test_get_latest_version_info(self) -> None:
        """Test extracting latest version information from manifest."""
        platform_manifest = downloader.Manifest(
            latest="21.1.5",
            versions={
                "21.1.5": downloader.VersionInfo(
                    version="21.1.5", href="http://example.com/llvm-21.1.5.tar.zst", sha256="abc123"
                )
            },
        )

        version, url, sha256 = downloader.get_latest_version_info(platform_manifest)
        self.assertEqual(version, "21.1.5")
        self.assertEqual(url, "http://example.com/llvm-21.1.5.tar.zst")
        self.assertEqual(sha256, "abc123")

    def test_get_latest_version_info_missing_latest(self) -> None:
        """Test get_latest_version_info with missing 'latest' field."""
        platform_manifest = downloader.Manifest(
            latest="",
            versions={
                "21.1.5": downloader.VersionInfo(
                    version="21.1.5", href="http://example.com/file.tar.zst", sha256="abc123"
                )
            },
        )

        with self.assertRaises(RuntimeError) as context:
            downloader.get_latest_version_info(platform_manifest)

        self.assertIn("does not specify a 'latest' version", str(context.exception))

    def test_get_latest_version_info_missing_version(self) -> None:
        """Test get_latest_version_info with missing version data."""
        platform_manifest = downloader.Manifest(latest="21.1.5", versions={})

        with self.assertRaises(RuntimeError) as context:
            downloader.get_latest_version_info(platform_manifest)

        self.assertIn("not found in manifest", str(context.exception))

    def test_parse_root_manifest_empty_platforms(self) -> None:
        """Test parsing root manifest with no platforms."""
        test_data = {"platforms": []}
        result = downloader._parse_root_manifest(test_data)

        self.assertIsInstance(result, downloader.RootManifest)
        self.assertEqual(len(result.platforms), 0)

    def test_parse_root_manifest_empty_architectures(self) -> None:
        """Test parsing root manifest with platform but no architectures."""
        test_data = {"platforms": [{"platform": "win", "architectures": []}]}
        result = downloader._parse_root_manifest(test_data)

        self.assertIsInstance(result, downloader.RootManifest)
        self.assertEqual(len(result.platforms), 1)
        self.assertEqual(result.platforms[0].platform, "win")
        self.assertEqual(len(result.platforms[0].architectures), 0)

    def test_parse_manifest_only_latest_field(self) -> None:
        """Test parsing manifest with only 'latest' field and no versions."""
        test_data = {"latest": "21.1.5"}
        result = downloader._parse_manifest(test_data)  # type: ignore[arg-type]

        self.assertIsInstance(result, downloader.Manifest)
        self.assertEqual(result.latest, "21.1.5")
        self.assertEqual(len(result.versions), 0)

    def test_parse_manifest_ignores_non_dict_values(self) -> None:
        """Test that manifest parser ignores non-dict values."""
        test_data = {
            "latest": "21.1.5",
            "21.1.5": {"href": "http://example.com/file.tar.zst", "sha256": "abc123"},
            "some_string": "should be ignored",
            "some_number": 42,
            "some_array": ["should", "be", "ignored"],
        }
        result = downloader._parse_manifest(test_data)  # type: ignore[arg-type]

        self.assertIsInstance(result, downloader.Manifest)
        self.assertEqual(len(result.versions), 1)
        self.assertIn("21.1.5", result.versions)
        self.assertNotIn("some_string", result.versions)
        self.assertNotIn("some_number", result.versions)
        self.assertNotIn("some_array", result.versions)

    @patch("clang_tool_chain.downloader._fetch_json_raw")
    def test_fetch_platform_manifest_architecture_not_found(self, mock_fetch_json_raw: Mock) -> None:
        """Test fetching platform manifest when platform exists but architecture doesn't."""
        root_manifest_data = {
            "platforms": [
                {
                    "platform": "linux",
                    "architectures": [{"arch": "x86_64", "manifest_path": "linux/x86_64/manifest.json"}],
                }
            ]
        }
        mock_fetch_json_raw.return_value = root_manifest_data

        with self.assertRaises(RuntimeError) as context:
            downloader.fetch_platform_manifest("linux", "riscv64")

        self.assertIn("not found in manifest", str(context.exception))

    def test_is_toolchain_installed_false(self) -> None:
        """Test is_toolchain_installed returns False when not installed."""
        with (
            tempfile.TemporaryDirectory() as tmpdir,
            patch("clang_tool_chain.downloader.get_install_dir", return_value=Path(tmpdir) / "nonexistent"),
        ):
            result = downloader.is_toolchain_installed("linux", "x86_64")
            self.assertFalse(result)

    def test_is_toolchain_installed_true(self) -> None:
        """Test is_toolchain_installed returns True when done.txt exists."""
        with tempfile.TemporaryDirectory() as tmpdir:
            install_dir = Path(tmpdir)
            install_dir.mkdir(parents=True, exist_ok=True)

            # Create done.txt file
            done_file = install_dir / "done.txt"
            done_file.write_text("Installation completed successfully\n")

            with patch("clang_tool_chain.downloader.get_install_dir", return_value=install_dir):
                result = downloader.is_toolchain_installed("linux", "x86_64")
                self.assertTrue(result)

    def test_is_toolchain_installed_false_no_done_file(self) -> None:
        """Test is_toolchain_installed returns False when done.txt is missing."""
        with tempfile.TemporaryDirectory() as tmpdir:
            install_dir = Path(tmpdir)
            install_dir.mkdir(parents=True, exist_ok=True)

            # Create bin directory and clang binary but no done.txt
            bin_dir = install_dir / "bin"
            bin_dir.mkdir(parents=True)
            clang_path = bin_dir / "clang"
            clang_path.touch()

            with patch("clang_tool_chain.downloader.get_install_dir", return_value=install_dir):
                result = downloader.is_toolchain_installed("linux", "x86_64")
                self.assertFalse(result)

    @patch("clang_tool_chain.downloader.is_toolchain_installed")
    def test_ensure_toolchain_already_installed(self, mock_is_installed: Mock) -> None:
        """Test ensure_toolchain when already installed (no lock needed)."""
        mock_is_installed.return_value = True

        # Should return immediately without acquiring lock
        downloader.ensure_toolchain("linux", "x86_64")

        # Verify it only checked once (before lock)
        self.assertEqual(mock_is_installed.call_count, 1)

    @patch("clang_tool_chain.downloader.download_and_install_toolchain")
    @patch("clang_tool_chain.downloader.is_toolchain_installed")
    def test_ensure_toolchain_needs_install(self, mock_is_installed: Mock, mock_download: Mock) -> None:
        """Test ensure_toolchain when installation is needed."""
        # First check returns False, second (inside lock) also returns False
        mock_is_installed.side_effect = [False, False]

        downloader.ensure_toolchain("linux", "x86_64")

        # Should have called download_and_install
        mock_download.assert_called_once_with("linux", "x86_64")

    @patch("clang_tool_chain.downloader.download_and_install_toolchain")
    @patch("clang_tool_chain.downloader.is_toolchain_installed")
    def test_ensure_toolchain_race_condition(self, mock_is_installed: Mock, mock_download: Mock) -> None:
        """Test ensure_toolchain handles race condition (another process installed)."""
        # First check returns False, second (inside lock) returns True
        mock_is_installed.side_effect = [False, True]

        downloader.ensure_toolchain("linux", "x86_64")

        # Should NOT have called download_and_install
        mock_download.assert_not_called()

    def test_fix_file_permissions(self) -> None:
        """Test that fix_file_permissions sets correct permissions on Unix systems."""
        import platform
        import stat

        # Skip on Windows since permissions work differently
        if platform.system() == "Windows":
            self.skipTest("Permission fixing is Unix-specific")

        with tempfile.TemporaryDirectory() as tmpdir:
            install_dir = Path(tmpdir)

            # Create test directory structure
            bin_dir = install_dir / "bin"
            lib_dir = install_dir / "lib" / "clang" / "21" / "lib" / "x86_64-unknown-linux-gnu"
            include_dir = install_dir / "lib" / "clang" / "21" / "include"

            bin_dir.mkdir(parents=True)
            lib_dir.mkdir(parents=True)
            include_dir.mkdir(parents=True)

            # Create test files
            binary = bin_dir / "clang"
            binary.write_text("binary")
            binary.chmod(0o644)  # Start with non-executable

            shared_lib = lib_dir / "libclang_rt.asan.so"
            shared_lib.write_text("shared lib")
            shared_lib.chmod(0o644)  # Start with non-executable

            header = include_dir / "stddef.h"
            header.write_text("header")
            header.chmod(0o755)  # Start with executable (wrong)

            static_lib = lib_dir / "libclang.a"
            static_lib.write_text("static lib")
            static_lib.chmod(0o755)  # Start with executable (wrong)

            # Fix permissions
            downloader.fix_file_permissions(install_dir)

            # Verify permissions were fixed
            binary_mode = binary.stat().st_mode
            self.assertTrue(binary_mode & stat.S_IXUSR, "Binary should be executable")
            self.assertEqual(binary_mode & 0o777, 0o755, f"Binary should be 0o755, got {oct(binary_mode & 0o777)}")

            lib_mode = shared_lib.stat().st_mode
            self.assertTrue(lib_mode & stat.S_IXUSR, "Shared library should be executable")
            self.assertEqual(lib_mode & 0o777, 0o755, f"Shared lib should be 0o755, got {oct(lib_mode & 0o777)}")

            header_mode = header.stat().st_mode
            self.assertFalse(header_mode & stat.S_IXUSR, "Header should not be executable")
            self.assertEqual(header_mode & 0o777, 0o644, f"Header should be 0o644, got {oct(header_mode & 0o777)}")

            static_mode = static_lib.stat().st_mode
            self.assertFalse(static_mode & stat.S_IXUSR, "Static lib should not be executable")
            self.assertEqual(static_mode & 0o777, 0o644, f"Static lib should be 0o644, got {oct(static_mode & 0o777)}")


if __name__ == "__main__":
    unittest.main()
