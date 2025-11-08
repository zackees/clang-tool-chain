"""
Unit tests for the checksums module.

Tests the checksum database functionality for LLVM binary verification.
"""

import unittest

from clang_tool_chain.checksums import (
    KNOWN_CHECKSUMS,
    add_checksum,
    format_platform_key,
    get_checksum,
    get_supported_platforms,
    get_supported_versions,
    has_checksum,
)


class TestGetChecksum(unittest.TestCase):
    """Test the get_checksum function."""

    def test_get_checksum_exists(self):
        """Test getting a checksum that exists."""
        # Add a test checksum
        test_version = "99.0.0"
        test_platform = "test-platform"
        test_checksum = "abc123def456"
        KNOWN_CHECKSUMS[test_version] = {test_platform: test_checksum}

        # Get the checksum
        result = get_checksum(test_version, test_platform)
        self.assertEqual(result, test_checksum)

        # Clean up
        del KNOWN_CHECKSUMS[test_version]

    def test_get_checksum_version_not_found(self):
        """Test getting a checksum for a non-existent version."""
        result = get_checksum("99.99.99", "any-platform")
        self.assertIsNone(result)

    def test_get_checksum_platform_not_found(self):
        """Test getting a checksum for a non-existent platform."""
        # Version exists but platform doesn't
        test_version = "21.1.5"
        result = get_checksum(test_version, "nonexistent-platform")
        self.assertIsNone(result)

    def test_get_checksum_empty_checksum(self):
        """Test getting an empty checksum value."""
        # Add a test version with empty checksum
        test_version = "99.0.1"
        test_platform = "test-platform"
        KNOWN_CHECKSUMS[test_version] = {test_platform: ""}

        # Get the empty checksum
        result = get_checksum(test_version, test_platform)
        self.assertEqual(result, "")

        # Clean up
        del KNOWN_CHECKSUMS[test_version]


class TestHasChecksum(unittest.TestCase):
    """Test the has_checksum function."""

    def test_has_checksum_exists(self):
        """Test checking for a checksum that exists."""
        # Add a test checksum
        test_version = "99.0.2"
        test_platform = "test-platform"
        test_checksum = "abc123"
        KNOWN_CHECKSUMS[test_version] = {test_platform: test_checksum}

        # Check if checksum exists
        result = has_checksum(test_version, test_platform)
        self.assertTrue(result)

        # Clean up
        del KNOWN_CHECKSUMS[test_version]

    def test_has_checksum_not_exists(self):
        """Test checking for a checksum that doesn't exist."""
        result = has_checksum("99.99.99", "any-platform")
        self.assertFalse(result)

    def test_has_checksum_empty_string(self):
        """Test that empty string checksums are considered non-existent."""
        # Add a test version with empty checksum
        test_version = "99.0.3"
        test_platform = "test-platform"
        KNOWN_CHECKSUMS[test_version] = {test_platform: ""}

        # Check if checksum exists (should be False for empty strings)
        result = has_checksum(test_version, test_platform)
        self.assertFalse(result)

        # Clean up
        del KNOWN_CHECKSUMS[test_version]

    def test_has_checksum_version_exists_platform_not(self):
        """Test when version exists but platform doesn't."""
        # Add a test version with one platform
        test_version = "99.0.4"
        KNOWN_CHECKSUMS[test_version] = {"platform-a": "checksum-a"}

        # Check for non-existent platform
        result = has_checksum(test_version, "platform-b")
        self.assertFalse(result)

        # Clean up
        del KNOWN_CHECKSUMS[test_version]


class TestGetSupportedVersions(unittest.TestCase):
    """Test the get_supported_versions function."""

    def test_get_supported_versions(self):
        """Test getting list of supported versions."""
        # Add some test versions
        test_versions = ["99.0.5", "99.0.6"]
        for version in test_versions:
            KNOWN_CHECKSUMS[version] = {}

        # Get supported versions
        result = get_supported_versions()

        # Check that our test versions are included
        for version in test_versions:
            self.assertIn(version, result)

        # Clean up
        for version in test_versions:
            del KNOWN_CHECKSUMS[version]

    def test_get_supported_versions_returns_list(self):
        """Test that the function returns a list."""
        result = get_supported_versions()
        self.assertIsInstance(result, list)

    def test_get_supported_versions_includes_21_1_5(self):
        """Test that version 21.1.5 is in supported versions."""
        result = get_supported_versions()
        self.assertIn("21.1.5", result)


class TestGetSupportedPlatforms(unittest.TestCase):
    """Test the get_supported_platforms function."""

    def test_get_supported_platforms_with_checksums(self):
        """Test getting platforms with checksums."""
        # Add test version with platforms
        test_version = "99.0.7"
        KNOWN_CHECKSUMS[test_version] = {
            "platform-a": "checksum-a",
            "platform-b": "checksum-b",
        }

        # Get supported platforms
        result = get_supported_platforms(test_version)
        self.assertEqual(set(result), {"platform-a", "platform-b"})

        # Clean up
        del KNOWN_CHECKSUMS[test_version]

    def test_get_supported_platforms_no_version(self):
        """Test getting platforms for non-existent version."""
        result = get_supported_platforms("99.99.99")
        self.assertEqual(result, [])

    def test_get_supported_platforms_empty_checksums(self):
        """Test getting platforms when checksums are empty strings."""
        # Add test version with empty checksums
        test_version = "99.0.8"
        KNOWN_CHECKSUMS[test_version] = {
            "platform-a": "",  # Empty checksum
            "platform-b": "checksum-b",  # Valid checksum
        }

        # Get supported platforms (should only include platform-b)
        result = get_supported_platforms(test_version)
        self.assertEqual(result, ["platform-b"])

        # Clean up
        del KNOWN_CHECKSUMS[test_version]

    def test_get_supported_platforms_returns_list(self):
        """Test that the function returns a list."""
        result = get_supported_platforms("21.1.5")
        self.assertIsInstance(result, list)


class TestAddChecksum(unittest.TestCase):
    """Test the add_checksum function."""

    def test_add_checksum_new_version(self):
        """Test adding a checksum for a new version."""
        test_version = "99.0.9"
        test_platform = "test-platform"
        test_checksum = "abc123def456"

        # Add checksum
        add_checksum(test_version, test_platform, test_checksum)

        # Verify it was added
        self.assertIn(test_version, KNOWN_CHECKSUMS)
        self.assertEqual(KNOWN_CHECKSUMS[test_version][test_platform], test_checksum)

        # Clean up
        del KNOWN_CHECKSUMS[test_version]

    def test_add_checksum_existing_version(self):
        """Test adding a checksum to an existing version."""
        test_version = "99.0.10"
        platform_a = "platform-a"
        platform_b = "platform-b"
        checksum_a = "checksum-a"
        checksum_b = "checksum-b"

        # Add first platform
        KNOWN_CHECKSUMS[test_version] = {platform_a: checksum_a}

        # Add second platform
        add_checksum(test_version, platform_b, checksum_b)

        # Verify both exist
        self.assertEqual(KNOWN_CHECKSUMS[test_version][platform_a], checksum_a)
        self.assertEqual(KNOWN_CHECKSUMS[test_version][platform_b], checksum_b)

        # Clean up
        del KNOWN_CHECKSUMS[test_version]

    def test_add_checksum_update_existing(self):
        """Test updating an existing checksum."""
        test_version = "99.0.11"
        test_platform = "test-platform"
        old_checksum = "old-checksum"
        new_checksum = "new-checksum"

        # Add initial checksum
        KNOWN_CHECKSUMS[test_version] = {test_platform: old_checksum}

        # Update with new checksum
        add_checksum(test_version, test_platform, new_checksum)

        # Verify it was updated
        self.assertEqual(KNOWN_CHECKSUMS[test_version][test_platform], new_checksum)

        # Clean up
        del KNOWN_CHECKSUMS[test_version]

    def test_add_checksum_lowercase(self):
        """Test that checksums are converted to lowercase."""
        test_version = "99.0.12"
        test_platform = "test-platform"
        test_checksum = "ABC123DEF456"

        # Add checksum with uppercase
        add_checksum(test_version, test_platform, test_checksum)

        # Verify it was converted to lowercase
        self.assertEqual(KNOWN_CHECKSUMS[test_version][test_platform], test_checksum.lower())

        # Clean up
        del KNOWN_CHECKSUMS[test_version]


class TestFormatPlatformKey(unittest.TestCase):
    """Test the format_platform_key function."""

    def test_format_platform_key_basic(self):
        """Test basic platform key formatting."""
        result = format_platform_key("linux", "x86_64")
        self.assertEqual(result, "linux-x86_64")

    def test_format_platform_key_normalize_x86(self):
        """Test normalizing x86 to x86_64."""
        result = format_platform_key("win", "x86")
        self.assertEqual(result, "win-x86_64")

    def test_format_platform_key_normalize_x64(self):
        """Test normalizing x64 to x86_64."""
        result = format_platform_key("win", "x64")
        self.assertEqual(result, "win-x86_64")

    def test_format_platform_key_normalize_amd64(self):
        """Test normalizing amd64 to x86_64."""
        result = format_platform_key("linux", "amd64")
        self.assertEqual(result, "linux-x86_64")

    def test_format_platform_key_normalize_arm(self):
        """Test normalizing arm to arm64."""
        result = format_platform_key("mac", "arm")
        self.assertEqual(result, "mac-arm64")

    def test_format_platform_key_normalize_aarch64(self):
        """Test normalizing aarch64 to arm64."""
        result = format_platform_key("linux", "aarch64")
        self.assertEqual(result, "linux-arm64")

    def test_format_platform_key_lowercase(self):
        """Test that OS and arch are converted to lowercase."""
        result = format_platform_key("LINUX", "X86_64")
        self.assertEqual(result, "linux-x86_64")

    def test_format_platform_key_already_normalized(self):
        """Test with already normalized values."""
        result = format_platform_key("linux", "x86_64")
        self.assertEqual(result, "linux-x86_64")

        result = format_platform_key("mac", "arm64")
        self.assertEqual(result, "mac-arm64")


class TestKnownChecksums(unittest.TestCase):
    """Test the KNOWN_CHECKSUMS database structure."""

    def test_known_checksums_is_dict(self):
        """Test that KNOWN_CHECKSUMS is a dictionary."""
        self.assertIsInstance(KNOWN_CHECKSUMS, dict)

    def test_known_checksums_has_21_1_5(self):
        """Test that version 21.1.5 exists in database."""
        self.assertIn("21.1.5", KNOWN_CHECKSUMS)

    def test_known_checksums_21_1_5_is_dict(self):
        """Test that 21.1.5 entry is a dictionary."""
        self.assertIsInstance(KNOWN_CHECKSUMS["21.1.5"], dict)

    def test_known_checksums_structure(self):
        """Test the overall structure of KNOWN_CHECKSUMS."""
        # Test that all values are dictionaries
        for version, platforms in KNOWN_CHECKSUMS.items():
            self.assertIsInstance(version, str, f"Version key should be string: {version}")
            self.assertIsInstance(platforms, dict, f"Platforms should be dict for {version}")

            # Test that all platform entries are strings
            for platform, checksum in platforms.items():
                self.assertIsInstance(platform, str, f"Platform key should be string: {platform}")
                self.assertIsInstance(checksum, str, f"Checksum should be string for {version}/{platform}")


class TestIntegration(unittest.TestCase):
    """Integration tests for the checksums module."""

    def test_full_workflow_add_and_retrieve(self):
        """Test full workflow of adding and retrieving a checksum."""
        test_version = "99.0.13"
        test_os = "linux"
        test_arch = "x86_64"
        test_checksum = "abc123def456789"

        # Format platform key
        platform_key = format_platform_key(test_os, test_arch)
        self.assertEqual(platform_key, "linux-x86_64")

        # Check that checksum doesn't exist yet
        self.assertFalse(has_checksum(test_version, platform_key))

        # Add checksum
        add_checksum(test_version, platform_key, test_checksum)

        # Check that checksum now exists
        self.assertTrue(has_checksum(test_version, platform_key))

        # Retrieve checksum
        retrieved = get_checksum(test_version, platform_key)
        self.assertEqual(retrieved, test_checksum)

        # Check supported versions includes our version
        versions = get_supported_versions()
        self.assertIn(test_version, versions)

        # Check supported platforms includes our platform
        platforms = get_supported_platforms(test_version)
        self.assertIn(platform_key, platforms)

        # Clean up
        del KNOWN_CHECKSUMS[test_version]

    def test_multiple_platforms_same_version(self):
        """Test adding multiple platforms for the same version."""
        test_version = "99.0.14"
        platforms = {
            "linux-x86_64": "checksum-linux-x64",
            "linux-arm64": "checksum-linux-arm",
            "win-x86_64": "checksum-win-x64",
        }

        # Add all checksums
        for platform, checksum in platforms.items():
            add_checksum(test_version, platform, checksum)

        # Verify all checksums
        for platform, expected_checksum in platforms.items():
            self.assertTrue(has_checksum(test_version, platform))
            retrieved = get_checksum(test_version, platform)
            self.assertEqual(retrieved, expected_checksum)

        # Verify supported platforms list
        supported = get_supported_platforms(test_version)
        self.assertEqual(set(supported), set(platforms.keys()))

        # Clean up
        del KNOWN_CHECKSUMS[test_version]


if __name__ == "__main__":
    unittest.main()
