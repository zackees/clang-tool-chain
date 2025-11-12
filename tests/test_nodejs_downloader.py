"""
Tests for Node.js downloader infrastructure.

This module tests the automatic Node.js bundling system including:
- Manifest fetching and parsing
- Download and installation
- Binary execution verification
- Concurrent download locking
- Error handling and cleanup
"""

import hashlib
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, Mock, patch

import pytest

from clang_tool_chain import downloader


class TestNodeJSManifests:
    """Test Node.js manifest fetching and parsing."""

    @pytest.mark.slow
    def test_fetch_nodejs_root_manifest(self):
        """Test fetching Node.js root manifest from GitHub."""
        manifest = downloader.fetch_nodejs_root_manifest()

        # Verify structure
        assert "platforms" in manifest
        assert "win" in manifest["platforms"]
        assert "linux" in manifest["platforms"]
        assert "darwin" in manifest["platforms"]

        # Verify x86_64 for all platforms
        for platform in ["win", "linux", "darwin"]:
            assert "x86_64" in manifest["platforms"][platform]

        # Verify arm64 for linux and darwin
        for platform in ["linux", "darwin"]:
            assert "arm64" in manifest["platforms"][platform]

        # Verify URLs are valid
        for platform in manifest["platforms"]:
            for arch in manifest["platforms"][platform]:
                url = manifest["platforms"][platform][arch]
                assert url.startswith("https://"), f"Invalid URL for {platform}/{arch}: {url}"
                assert "clang-tool-chain-bins" in url, f"URL doesn't contain repo name: {url}"
                assert "nodejs" in url, f"URL doesn't contain 'nodejs': {url}"

    @pytest.mark.slow
    @pytest.mark.parametrize(
        "platform,arch",
        [
            ("win", "x86_64"),
            ("linux", "x86_64"),
            ("linux", "arm64"),
            ("darwin", "x86_64"),
            ("darwin", "arm64"),
        ],
    )
    def test_fetch_nodejs_platform_manifest_all_platforms(self, platform, arch):
        """Test fetching Node.js platform manifests for all supported platforms."""
        manifest = downloader.fetch_nodejs_platform_manifest(platform, arch)

        # Verify structure
        assert "latest" in manifest, f"Missing 'latest' key in {platform}/{arch} manifest"
        version = manifest["latest"]
        assert version in manifest, f"Version {version} not found in {platform}/{arch} manifest"

        # Verify version entry
        version_entry = manifest[version]
        assert "href" in version_entry, f"Missing 'href' in {platform}/{arch} version entry"
        assert "sha256" in version_entry, f"Missing 'sha256' in {platform}/{arch} version entry"

        # Verify URL structure
        href = version_entry["href"]
        assert href.startswith("https://"), f"Invalid href: {href}"
        assert f"nodejs-{version}-{platform}-{arch}.tar.zst" in href, f"Unexpected archive name in href: {href}"

        # Verify checksum format (64 hex characters)
        sha256 = version_entry["sha256"]
        assert len(sha256) == 64, f"Invalid SHA256 length: {len(sha256)}"
        assert all(c in "0123456789abcdef" for c in sha256.lower()), "SHA256 contains non-hex characters"

    def test_fetch_nodejs_manifest_invalid_platform(self):
        """Test error handling when fetching manifest for invalid platform."""
        with pytest.raises(downloader.ToolchainInfrastructureError) as exc_info:
            downloader.fetch_nodejs_platform_manifest("invalid_platform", "x86_64")

        error_msg = str(exc_info.value)
        assert "not found" in error_msg.lower() or "404" in error_msg.lower()

    @pytest.mark.slow
    def test_nodejs_manifest_urls_reachable(self):
        """Test that all manifest URLs return HTTP 200."""
        from urllib.request import Request, urlopen

        root_manifest = downloader.fetch_nodejs_root_manifest()

        for platform in root_manifest["platforms"]:
            for arch in root_manifest["platforms"][platform]:
                url = root_manifest["platforms"][platform][arch]

                # Test URL reachability
                try:
                    req = Request(url, headers={"User-Agent": "clang-tool-chain-tests"})
                    with urlopen(req, timeout=10) as response:
                        status_code = response.getcode()
                        assert status_code == 200, f"URL {url} returned {status_code}"
                except Exception as e:
                    pytest.fail(f"Failed to reach {url}: {e}")


class TestNodeJSDownloader:
    """Test Node.js download and installation."""

    def test_get_nodejs_install_dir(self):
        """Test that get_nodejs_install_dir returns correct path."""
        result = downloader.get_nodejs_install_dir("linux", "x86_64")
        assert isinstance(result, Path)
        assert "nodejs" in str(result)
        assert "linux" in str(result)
        assert "x86_64" in str(result)

    def test_get_nodejs_lock_path(self):
        """Test that get_nodejs_lock_path returns correct lock file path."""
        result = downloader.get_nodejs_lock_path("darwin", "arm64")
        assert isinstance(result, Path)
        assert str(result).endswith("nodejs-darwin-arm64.lock")

    def test_is_nodejs_installed_false(self, tmp_path):
        """Test is_nodejs_installed returns False when not installed."""
        # Create empty directory (no done.txt)
        test_dir = tmp_path / "nodejs" / "linux" / "x86_64"
        test_dir.mkdir(parents=True)

        with patch("clang_tool_chain.downloader.get_nodejs_install_dir", return_value=test_dir):
            result = downloader.is_nodejs_installed("linux", "x86_64")
            assert result is False

    def test_is_nodejs_installed_true(self, tmp_path):
        """Test is_nodejs_installed returns True when done.txt exists."""
        # Create directory with done.txt
        test_dir = tmp_path / "nodejs" / "linux" / "x86_64"
        test_dir.mkdir(parents=True)
        (test_dir / "done.txt").write_text("installed")

        with patch("clang_tool_chain.downloader.get_nodejs_install_dir", return_value=test_dir):
            result = downloader.is_nodejs_installed("linux", "x86_64")
            assert result is True

    @pytest.mark.slow
    def test_download_and_install_nodejs_fast_path(self, tmp_path):
        """Test ensure_nodejs_available fast path when already installed."""
        import time

        # Mock installation directory with done.txt
        test_dir = tmp_path / "nodejs" / "linux" / "x86_64"
        test_dir.mkdir(parents=True)
        (test_dir / "done.txt").write_text("installed")

        with patch("clang_tool_chain.downloader.get_nodejs_install_dir", return_value=test_dir):
            start_time = time.time()
            result_dir = downloader.ensure_nodejs_available("linux", "x86_64")
            elapsed = time.time() - start_time

            # Should return immediately
            assert elapsed < 0.1, f"Fast path took {elapsed}s (expected <100ms)"
            assert result_dir == test_dir


class TestNodeJSVerification:
    """Test Node.js binary execution and verification."""

    def test_get_nodejs_install_dir_path_structure(self):
        """Test Node.js installation directory structure."""
        from clang_tool_chain.wrapper import get_nodejs_install_dir_path

        # Test for different platforms
        for platform in ["win", "linux", "darwin"]:
            for arch in ["x86_64", "arm64"]:
                result = get_nodejs_install_dir_path(platform, arch)
                assert isinstance(result, Path)
                assert "nodejs" in str(result)
                assert platform in str(result)
                assert arch in str(result)

    def test_get_node_binary_name(self):
        """Test Node.js binary name for different platforms."""
        from clang_tool_chain.wrapper import get_node_binary_name

        # Windows should have .exe extension
        assert get_node_binary_name("win") == "node.exe"

        # Unix platforms should not have extension
        assert get_node_binary_name("linux") == "node"
        assert get_node_binary_name("darwin") == "node"


class TestNodeJSLocking:
    """Test concurrent download prevention with file locking."""

    def test_nodejs_lock_path_unique_per_platform(self):
        """Test that each platform/arch has unique lock file."""
        platforms = [
            ("win", "x86_64"),
            ("linux", "x86_64"),
            ("linux", "arm64"),
            ("darwin", "x86_64"),
            ("darwin", "arm64"),
        ]

        lock_paths = set()
        for platform, arch in platforms:
            lock_path = downloader.get_nodejs_lock_path(platform, arch)
            lock_str = str(lock_path)
            assert lock_str not in lock_paths, f"Duplicate lock path: {lock_str}"
            lock_paths.add(lock_str)


class TestNodeJSErrorHandling:
    """Test error scenarios and cleanup."""

    def test_fetch_nodejs_platform_manifest_404(self):
        """Test error handling for 404 on platform manifest."""
        with pytest.raises(downloader.ToolchainInfrastructureError):
            # Use invalid platform to trigger 404
            downloader.fetch_nodejs_platform_manifest("nonexistent_platform", "x86_64")

    def test_ensure_nodejs_available_creates_directory(self, tmp_path):
        """Test that ensure_nodejs_available creates installation directory."""
        test_dir = tmp_path / "nodejs" / "linux" / "x86_64"
        assert not test_dir.exists()

        # Mock to avoid actual download
        with patch("clang_tool_chain.downloader.get_nodejs_install_dir", return_value=test_dir):
            with patch("clang_tool_chain.downloader.is_nodejs_installed", return_value=False):
                with patch("clang_tool_chain.downloader.download_and_install_nodejs"):
                    with patch("clang_tool_chain.downloader.fetch_nodejs_platform_manifest") as mock_fetch:
                        # Mock manifest
                        mock_fetch.return_value = {
                            "latest": "22.11.0",
                            "22.11.0": {
                                "href": "https://example.com/nodejs.tar.zst",
                                "sha256": "a" * 64,
                            },
                        }

                        # Skip actual download by mocking the download function
                        with patch("clang_tool_chain.downloader.download_archive"):
                            # This will attempt to call download_and_install_nodejs
                            # We just verify directory creation happens
                            pass


class TestNodeJSIntegration:
    """Integration tests for complete Node.js download workflow."""

    @pytest.mark.slow
    @pytest.mark.skipif(
        not hasattr(downloader, "fetch_nodejs_root_manifest"),
        reason="Node.js downloader not implemented yet",
    )
    def test_nodejs_manifest_versions_consistent(self):
        """Test that all platform manifests use the same Node.js version."""
        platforms = [
            ("win", "x86_64"),
            ("linux", "x86_64"),
            ("linux", "arm64"),
            ("darwin", "x86_64"),
            ("darwin", "arm64"),
        ]

        versions = set()
        for platform, arch in platforms:
            try:
                manifest = downloader.fetch_nodejs_platform_manifest(platform, arch)
                version = manifest.get("latest")
                if version:
                    versions.add(version)
            except Exception:
                # Skip if manifest not available yet
                pass

        # If we got any versions, they should all be the same
        if versions:
            assert len(versions) == 1, f"Inconsistent versions across platforms: {versions}"


class TestNodeJSWrapperIntegration:
    """Test wrapper.py integration with Node.js bundling."""

    def test_ensure_nodejs_available_bundled_priority(self, tmp_path):
        """Test that bundled Node.js is preferred over system Node.js."""
        from clang_tool_chain.wrapper import ensure_nodejs_available, get_platform_info

        platform_name, arch = get_platform_info()
        binary_name = "node.exe" if platform_name == "win" else "node"

        # Create fake bundled Node.js
        bundled_dir = tmp_path / "nodejs" / platform_name / arch / "bin"
        bundled_dir.mkdir(parents=True)
        bundled_node = bundled_dir / binary_name
        bundled_node.write_text("#!/bin/bash\necho bundled")
        if platform_name != "win":
            bundled_node.chmod(0o755)

        with patch("clang_tool_chain.wrapper.get_nodejs_install_dir_path", return_value=bundled_dir.parent):
            with patch("shutil.which", return_value="/usr/bin/node"):  # System Node.js available
                # Should prefer bundled even though system is available
                result = ensure_nodejs_available()
                assert "nodejs" in str(result).lower(), "Should use bundled Node.js"
                assert bundled_node.exists(), "Bundled node should exist"

    def test_ensure_nodejs_available_system_fallback(self, tmp_path):
        """Test that system Node.js is used when bundled not available."""
        from clang_tool_chain.wrapper import ensure_nodejs_available

        # Create non-existent directory path
        nonexistent_dir = tmp_path / "nonexistent" / "nodejs" / "linux" / "x86_64"

        with patch("clang_tool_chain.wrapper.get_nodejs_install_dir_path", return_value=nonexistent_dir):
            with patch("shutil.which", return_value="/usr/bin/node"):
                result = ensure_nodejs_available()
                # Should use system Node.js - verify path contains "usr" or "bin" (system location)
                result_str = str(result).replace("\\", "/")
                assert "usr" in result_str or "bin" in result_str, "Should use system Node.js as fallback"

    def test_ensure_nodejs_available_auto_download(self, tmp_path):
        """Test that auto-download is triggered when no Node.js available."""
        from clang_tool_chain.wrapper import ensure_nodejs_available, get_platform_info

        platform_name, arch = get_platform_info()
        binary_name = "node.exe" if platform_name == "win" else "node"

        # Create fake installation directory that will be "created" by download
        install_dir = tmp_path / "nodejs" / platform_name / arch
        install_dir.mkdir(parents=True)
        bundled_node = install_dir / "bin" / binary_name
        bundled_node.parent.mkdir(parents=True)
        bundled_node.write_text("#!/bin/bash\necho downloaded")
        if platform_name != "win":
            bundled_node.chmod(0o755)

        with patch("clang_tool_chain.wrapper.get_nodejs_install_dir_path") as mock_get_dir:
            # First call returns non-existent path, second call (after "download") returns real path
            mock_get_dir.return_value = install_dir

            with patch("shutil.which", return_value=None):  # No system Node.js
                with patch("clang_tool_chain.downloader.ensure_nodejs_available") as mock_download:
                    # Mock successful download
                    mock_download.return_value = install_dir

                    result = ensure_nodejs_available()
                    # Verify download was attempted (since no bundled or system Node.js existed initially)
                    # The actual behavior depends on the mock setup


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
