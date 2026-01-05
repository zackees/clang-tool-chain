"""
Unit tests to verify that clang download sizes are within acceptable limits per platform.

These tests perform HTTP HEAD requests to check the Content-Length of the clang archives
and ensure they don't exceed platform-specific size limits.
"""

import unittest
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from clang_tool_chain.manifest import fetch_platform_manifest, fetch_root_manifest

# Maximum acceptable download sizes per platform (in bytes)
# These limits ensure downloads remain practical for users
MAX_DOWNLOAD_SIZES = {
    "win": {
        "x86_64": 100 * 1024 * 1024,  # 100 MB for Windows x64
    },
    "linux": {
        "x86_64": 100 * 1024 * 1024,  # 100 MB for Linux x64
        "arm64": 100 * 1024 * 1024,  # 100 MB for Linux ARM64
    },
    "darwin": {
        "x86_64": 100 * 1024 * 1024,  # 100 MB for macOS x64
        "arm64": 100 * 1024 * 1024,  # 100 MB for macOS ARM64
    },
}


def _get_content_length(url: str) -> int:
    """
    Get the Content-Length of a URL via HTTP HEAD request.

    Args:
        url: The URL to check

    Returns:
        The content length in bytes

    Raises:
        HTTPError: If the HTTP request fails
        ValueError: If Content-Length header is missing
    """
    req = Request(url, method="HEAD")
    try:
        with urlopen(req, timeout=30) as response:
            content_length = response.getheader("Content-Length")
            if content_length is None:
                raise ValueError(f"No Content-Length header found for {url}")
            return int(content_length)
    except (HTTPError, URLError) as e:
        raise HTTPError(url, getattr(e, "code", 0), f"Failed to fetch HEAD for {url}: {e}", None, None) from e  # type: ignore[arg-type]


class TestDownloadSizeLimits(unittest.TestCase):
    """Test that clang download sizes are within acceptable limits."""

    @classmethod
    def setUpClass(cls):
        """Fetch the root manifest once for all tests."""
        try:
            cls.root_manifest = fetch_root_manifest()
        except Exception as e:
            cls.root_manifest = None
            cls.skip_reason = f"Failed to fetch root manifest: {e}"

    def test_root_manifest_available(self):
        """Verify that the root manifest was fetched successfully."""
        self.assertIsNotNone(self.root_manifest, getattr(self.__class__, "skip_reason", "Unknown error"))

    def test_all_platform_download_sizes(self):
        """Test that all platform download sizes are within limits."""
        if self.root_manifest is None:
            self.skipTest(getattr(self.__class__, "skip_reason", "Root manifest not available"))

        # Iterate through all platforms and architectures in the root manifest
        for platform_entry in self.root_manifest.platforms:
            platform = platform_entry.platform
            for arch_entry in platform_entry.architectures:
                arch = arch_entry.arch

                # Skip special cases like mingw-x86_64 (sysroot, not full toolchain)
                if arch.startswith("mingw-"):
                    continue

                # Skip platforms without defined size limits
                if platform not in MAX_DOWNLOAD_SIZES:
                    continue
                if arch not in MAX_DOWNLOAD_SIZES[platform]:
                    continue

                with self.subTest(platform=platform, arch=arch):
                    self._test_platform_download_size(platform, arch)

    def _test_platform_download_size(self, platform: str, arch: str):
        """
        Test that a specific platform/arch download is within size limits.

        Args:
            platform: Platform name (win, linux, darwin)
            arch: Architecture name (x86_64, arm64)
        """
        # Fetch the platform manifest
        try:
            manifest = fetch_platform_manifest(platform, arch)
        except Exception as e:
            self.fail(f"Failed to fetch manifest for {platform}/{arch}: {e}")

        # Get the latest version
        latest_version = manifest.latest
        self.assertIn(latest_version, manifest.versions, f"Latest version {latest_version} not found in manifest")

        # Get the download URL
        version_info = manifest.versions[latest_version]
        download_url = version_info.href

        # Perform HTTP HEAD request to get file size
        try:
            content_length = _get_content_length(download_url)
        except Exception as e:
            self.fail(f"Failed to get content length for {platform}/{arch} ({download_url}): {e}")

        # Get the size limit for this platform/arch
        max_size = MAX_DOWNLOAD_SIZES[platform][arch]

        # Convert to MB for readable output
        content_length_mb = content_length / (1024 * 1024)
        max_size_mb = max_size / (1024 * 1024)

        # Assert that the download size is within limits
        self.assertLessEqual(
            content_length,
            max_size,
            f"{platform}/{arch} download size is {content_length_mb:.2f} MB, "
            f"which exceeds the limit of {max_size_mb:.0f} MB. "
            f"URL: {download_url}",
        )

        # Print success info (visible with pytest -v)
        print(
            f"✓ {platform}/{arch}: {content_length_mb:.2f} MB / {max_size_mb:.0f} MB "
            f"({content_length_mb / max_size_mb * 100:.1f}% of limit)"
        )

    def test_windows_x64_download_size(self):
        """Test that Windows x64 download is under 250 MB."""
        if self.root_manifest is None:
            self.skipTest(getattr(self.__class__, "skip_reason", "Root manifest not available"))
        self._test_platform_download_size("win", "x86_64")

    def test_linux_x64_download_size(self):
        """Test that Linux x64 download is under 250 MB."""
        if self.root_manifest is None:
            self.skipTest(getattr(self.__class__, "skip_reason", "Root manifest not available"))
        self._test_platform_download_size("linux", "x86_64")

    def test_linux_arm64_download_size(self):
        """Test that Linux ARM64 download is under 250 MB."""
        if self.root_manifest is None:
            self.skipTest(getattr(self.__class__, "skip_reason", "Root manifest not available"))
        self._test_platform_download_size("linux", "arm64")

    def test_darwin_x64_download_size(self):
        """Test that macOS x64 download is under 250 MB."""
        if self.root_manifest is None:
            self.skipTest(getattr(self.__class__, "skip_reason", "Root manifest not available"))
        self._test_platform_download_size("darwin", "x86_64")

    def test_darwin_arm64_download_size(self):
        """Test that macOS ARM64 download is under 250 MB."""
        if self.root_manifest is None:
            self.skipTest(getattr(self.__class__, "skip_reason", "Root manifest not available"))
        self._test_platform_download_size("darwin", "arm64")


if __name__ == "__main__":
    unittest.main()
