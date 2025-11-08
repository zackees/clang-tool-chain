"""
Unit tests for manifest.json files in downloads directory.

These tests verify that manifest files are well-formed and contain valid data.
"""

import json
import sys
import unittest
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))


class TestManifestFiles(unittest.TestCase):
    """Test manifest.json files in downloads subdirectories."""

    @classmethod
    def setUpClass(cls):
        """Set up test class with downloads directory path."""
        cls.downloads_dir = Path(__file__).parent.parent / "downloads"
        cls.required_version_fields = ["href", "sha256"]
        cls.valid_platforms = ["win", "linux", "darwin"]
        cls.valid_architectures = ["x86_64", "arm64"]

    def test_downloads_directory_exists(self):
        """Test that downloads directory exists."""
        self.assertTrue(self.downloads_dir.exists(), f"Downloads directory not found at {self.downloads_dir}")
        self.assertTrue(self.downloads_dir.is_dir(), f"Downloads path is not a directory: {self.downloads_dir}")

    def test_root_manifest_exists(self):
        """Test that root manifest.json exists in downloads directory."""
        root_manifest = self.downloads_dir / "manifest.json"
        self.assertTrue(root_manifest.exists(), "Root manifest.json not found in downloads/")
        self.assertTrue(root_manifest.is_file(), "Root manifest.json is not a file")

    def test_root_manifest_valid_json(self):
        """Test that root manifest.json contains valid JSON."""
        root_manifest = self.downloads_dir / "manifest.json"
        if root_manifest.exists():
            try:
                with open(root_manifest, encoding="utf-8") as f:
                    json.load(f)
            except json.JSONDecodeError as e:
                self.fail(f"Invalid JSON in downloads/manifest.json: {e}")

    def test_root_manifest_structure(self):
        """Test that root manifest has the expected structure."""
        root_manifest = self.downloads_dir / "manifest.json"
        if root_manifest.exists():
            with open(root_manifest, encoding="utf-8") as f:
                data = json.load(f)

            # Check for platforms field
            self.assertIn("platforms", data, "Missing 'platforms' field in root manifest.json")
            self.assertIsInstance(data["platforms"], list, "'platforms' must be a list in root manifest.json")

            # Verify each platform entry
            for i, platform_entry in enumerate(data["platforms"]):
                with self.subTest(platform_index=i):
                    self.assertIn("platform", platform_entry, f"Missing 'platform' field in platforms[{i}]")
                    self.assertIn("architectures", platform_entry, f"Missing 'architectures' field in platforms[{i}]")
                    self.assertIsInstance(
                        platform_entry["architectures"],
                        list,
                        f"'architectures' must be a list in platforms[{i}]",
                    )

                    # Verify platform name is valid
                    self.assertIn(
                        platform_entry["platform"],
                        self.valid_platforms,
                        f"Invalid platform '{platform_entry['platform']}' in platforms[{i}]",
                    )

                    # Verify each architecture entry
                    for j, arch_entry in enumerate(platform_entry["architectures"]):
                        with self.subTest(platform_index=i, arch_index=j):
                            self.assertIn(
                                "arch", arch_entry, f"Missing 'arch' field in platforms[{i}].architectures[{j}]"
                            )
                            self.assertIn(
                                "manifest_path",
                                arch_entry,
                                f"Missing 'manifest_path' field in platforms[{i}].architectures[{j}]",
                            )

                            # Verify arch is valid
                            self.assertIn(
                                arch_entry["arch"],
                                self.valid_architectures,
                                f"Invalid architecture '{arch_entry['arch']}' in platforms[{i}].architectures[{j}]",
                            )

                            # Verify no version info in root manifest (should be in platform/arch manifests only)
                            self.assertNotIn(
                                "clang_version",
                                arch_entry,
                                f"Root manifest should not contain 'clang_version' - found in platforms[{i}].architectures[{j}]",
                            )

    def test_root_manifest_references_existing_manifests(self):
        """Test that all manifest_path references in root manifest point to existing files."""
        root_manifest = self.downloads_dir / "manifest.json"
        if root_manifest.exists():
            with open(root_manifest, encoding="utf-8") as f:
                data = json.load(f)

            for platform_entry in data.get("platforms", []):
                platform_name = platform_entry.get("platform", "unknown")
                for arch_entry in platform_entry.get("architectures", []):
                    arch_name = arch_entry.get("arch", "unknown")
                    manifest_path = arch_entry.get("manifest_path", "")

                    with self.subTest(platform=platform_name, arch=arch_name):
                        full_path = self.downloads_dir / manifest_path
                        self.assertTrue(
                            full_path.exists(),
                            f"Manifest file not found: {manifest_path} (referenced in root manifest for {platform_name}/{arch_name})",
                        )

    def test_root_manifest_completeness(self):
        """Test that root manifest lists all existing platform/arch combinations."""
        root_manifest = self.downloads_dir / "manifest.json"
        if root_manifest.exists():
            with open(root_manifest, encoding="utf-8") as f:
                data = json.load(f)

            # Build a set of platform/arch combinations from root manifest
            root_combinations = set()
            for platform_entry in data.get("platforms", []):
                platform = platform_entry.get("platform")
                for arch_entry in platform_entry.get("architectures", []):
                    arch = arch_entry.get("arch")
                    root_combinations.add((platform, arch))

            # Build a set of platform/arch combinations from filesystem
            fs_combinations = set()
            for platform_dir in self.downloads_dir.iterdir():
                if platform_dir.is_dir() and platform_dir.name in self.valid_platforms:
                    for arch_dir in platform_dir.iterdir():
                        if arch_dir.is_dir() and arch_dir.name in self.valid_architectures:
                            manifest_path = arch_dir / "manifest.json"
                            if manifest_path.exists():
                                fs_combinations.add((platform_dir.name, arch_dir.name))

            # Verify they match
            missing_in_root = fs_combinations - root_combinations
            extra_in_root = root_combinations - fs_combinations

            self.assertEqual(
                len(missing_in_root),
                0,
                f"Root manifest is missing these platform/arch combinations: {missing_in_root}",
            )
            self.assertEqual(
                len(extra_in_root),
                0,
                f"Root manifest references non-existent platform/arch combinations: {extra_in_root}",
            )

    def test_platform_subdirectories_exist(self):
        """Test that expected platform subdirectories exist."""
        subdirs = [d for d in self.downloads_dir.iterdir() if d.is_dir()]
        platform_dirs = [d.name for d in subdirs]

        for platform in self.valid_platforms:
            self.assertIn(platform, platform_dirs, f"Platform directory '{platform}' not found in downloads/")

    def test_architecture_subdirectories_exist(self):
        """Test that each platform has architecture subdirectories."""
        for platform in self.valid_platforms:
            platform_dir = self.downloads_dir / platform
            if platform_dir.exists():
                arch_subdirs = [d for d in platform_dir.iterdir() if d.is_dir()]
                # At least one architecture should exist for each platform
                self.assertTrue(len(arch_subdirs) > 0, f"No architecture subdirectories found in downloads/{platform}/")

    def test_all_manifests_exist(self):
        """Test that each platform/arch subdirectory contains a manifest.json file."""
        for platform_dir in self.downloads_dir.iterdir():
            if platform_dir.is_dir() and platform_dir.name in self.valid_platforms:
                for arch_dir in platform_dir.iterdir():
                    if arch_dir.is_dir() and arch_dir.name in self.valid_architectures:
                        manifest_path = arch_dir / "manifest.json"
                        self.assertTrue(
                            manifest_path.exists(), f"manifest.json not found in {platform_dir.name}/{arch_dir.name}/"
                        )

    def test_manifest_json_valid(self):
        """Test that all manifest.json files contain valid JSON."""
        for platform_dir in self.downloads_dir.iterdir():
            if platform_dir.is_dir() and platform_dir.name in self.valid_platforms:
                for arch_dir in platform_dir.iterdir():
                    if arch_dir.is_dir() and arch_dir.name in self.valid_architectures:
                        manifest_path = arch_dir / "manifest.json"
                        if manifest_path.exists():
                            with self.subTest(platform=platform_dir.name, arch=arch_dir.name):
                                try:
                                    with open(manifest_path, encoding="utf-8") as f:
                                        json.load(f)
                                except json.JSONDecodeError as e:
                                    self.fail(f"Invalid JSON in {platform_dir.name}/{arch_dir.name}/manifest.json: {e}")

    def test_manifest_structure(self):
        """Test that manifest files have the expected structure."""
        for platform_dir in self.downloads_dir.iterdir():
            if platform_dir.is_dir() and platform_dir.name in self.valid_platforms:
                for arch_dir in platform_dir.iterdir():
                    if arch_dir.is_dir() and arch_dir.name in self.valid_architectures:
                        manifest_path = arch_dir / "manifest.json"
                        if manifest_path.exists():
                            with self.subTest(platform=platform_dir.name, arch=arch_dir.name):
                                with open(manifest_path, encoding="utf-8") as f:
                                    data = json.load(f)

                                path_str = f"{platform_dir.name}/{arch_dir.name}"

                                # Verify manifest is a dictionary
                                self.assertIsInstance(
                                    data, dict, f"Manifest must be a dictionary in {path_str}/manifest.json"
                                )

                                # Check for 'latest' field
                                self.assertIn("latest", data, f"Missing 'latest' field in {path_str}/manifest.json")
                                self.assertIsInstance(
                                    data["latest"], str, f"'latest' must be a string in {path_str}/manifest.json"
                                )

                                # Verify 'latest' points to an existing version
                                latest_version = data["latest"]
                                self.assertIn(
                                    latest_version,
                                    data,
                                    f"'latest' version '{latest_version}' not found in manifest in {path_str}/manifest.json",
                                )

                                # Verify at least one version exists (besides 'latest')
                                version_keys = [k for k in data if k != "latest"]
                                self.assertGreater(
                                    len(version_keys),
                                    0,
                                    f"No version entries found in {path_str}/manifest.json",
                                )

    def test_version_fields(self):
        """Test that each version entry has all required fields."""
        for platform_dir in self.downloads_dir.iterdir():
            if platform_dir.is_dir() and platform_dir.name in self.valid_platforms:
                for arch_dir in platform_dir.iterdir():
                    if arch_dir.is_dir() and arch_dir.name in self.valid_architectures:
                        manifest_path = arch_dir / "manifest.json"
                        if manifest_path.exists():
                            with open(manifest_path, encoding="utf-8") as f:
                                data = json.load(f)

                            path_str = f"{platform_dir.name}/{arch_dir.name}"

                            # Get all version keys (excluding 'latest')
                            version_keys = [k for k in data if k != "latest"]

                            for version in version_keys:
                                with self.subTest(platform=platform_dir.name, arch=arch_dir.name, version=version):
                                    version_data = data[version]

                                    # Verify version data is a dictionary
                                    self.assertIsInstance(
                                        version_data,
                                        dict,
                                        f"Version '{version}' must be a dictionary in {path_str}/manifest.json",
                                    )

                                    # Check all required fields
                                    for field in self.required_version_fields:
                                        self.assertIn(
                                            field,
                                            version_data,
                                            f"Missing field '{field}' in version '{version}' of {path_str}/manifest.json",
                                        )
                                        # Ensure field is not empty
                                        self.assertTrue(
                                            version_data[field],
                                            f"Field '{field}' is empty in version '{version}' of {path_str}/manifest.json",
                                        )

    def test_sha256_format(self):
        """Test that SHA256 checksums are properly formatted."""
        sha256_pattern = r"^[a-f0-9]{64}$"
        import re

        for platform_dir in self.downloads_dir.iterdir():
            if platform_dir.is_dir() and platform_dir.name in self.valid_platforms:
                for arch_dir in platform_dir.iterdir():
                    if arch_dir.is_dir() and arch_dir.name in self.valid_architectures:
                        manifest_path = arch_dir / "manifest.json"
                        if manifest_path.exists():
                            with open(manifest_path, encoding="utf-8") as f:
                                data = json.load(f)

                            path_str = f"{platform_dir.name}/{arch_dir.name}"

                            # Get all version keys (excluding 'latest')
                            version_keys = [k for k in data if k != "latest"]

                            for version in version_keys:
                                with self.subTest(platform=platform_dir.name, arch=arch_dir.name, version=version):
                                    version_data = data[version]
                                    sha256 = version_data.get("sha256", "")
                                    self.assertTrue(
                                        re.match(sha256_pattern, sha256),
                                        f"Invalid SHA256 format '{sha256}' in version '{version}' of {path_str}/manifest.json",
                                    )

    def test_href_format(self):
        """Test that href URLs are properly formatted."""
        for platform_dir in self.downloads_dir.iterdir():
            if platform_dir.is_dir() and platform_dir.name in self.valid_platforms:
                for arch_dir in platform_dir.iterdir():
                    if arch_dir.is_dir() and arch_dir.name in self.valid_architectures:
                        manifest_path = arch_dir / "manifest.json"
                        if manifest_path.exists():
                            with open(manifest_path, encoding="utf-8") as f:
                                data = json.load(f)

                            path_str = f"{platform_dir.name}/{arch_dir.name}"

                            # Get all version keys (excluding 'latest')
                            version_keys = [k for k in data if k != "latest"]

                            for version in version_keys:
                                with self.subTest(platform=platform_dir.name, arch=arch_dir.name, version=version):
                                    version_data = data[version]
                                    href = version_data.get("href", "")

                                    # Verify it's a GitHub raw URL
                                    self.assertTrue(
                                        href.startswith("https://raw.githubusercontent.com/"),
                                        f"Invalid href URL in version '{version}' of {path_str}/manifest.json - must be GitHub raw URL",
                                    )

                                    # Verify it contains the expected filename pattern
                                    expected_filename = f"llvm-{version}-{platform_dir.name}-{arch_dir.name}.tar.zst"
                                    self.assertTrue(
                                        href.endswith(expected_filename),
                                        f"href URL doesn't end with expected filename '{expected_filename}' in version '{version}' of {path_str}/manifest.json",
                                    )

    def test_latest_points_to_highest_version(self):
        """Test that 'latest' field points to the highest semantic version."""
        from packaging import version

        for platform_dir in self.downloads_dir.iterdir():
            if platform_dir.is_dir() and platform_dir.name in self.valid_platforms:
                for arch_dir in platform_dir.iterdir():
                    if arch_dir.is_dir() and arch_dir.name in self.valid_architectures:
                        manifest_path = arch_dir / "manifest.json"
                        if manifest_path.exists():
                            with self.subTest(platform=platform_dir.name, arch=arch_dir.name):
                                with open(manifest_path, encoding="utf-8") as f:
                                    data = json.load(f)

                                path_str = f"{platform_dir.name}/{arch_dir.name}"

                                # Get all version keys (excluding 'latest')
                                version_keys = [k for k in data if k != "latest"]

                                # Skip if no versions exist
                                if not version_keys:
                                    continue

                                # Parse and sort versions
                                parsed_versions = []
                                for v in version_keys:
                                    try:
                                        parsed_versions.append((version.parse(v), v))
                                    except Exception as e:
                                        self.fail(f"Failed to parse version '{v}' in {path_str}/manifest.json: {e}")

                                # Get the highest version
                                parsed_versions.sort(reverse=True)
                                highest_version = parsed_versions[0][1]

                                # Verify 'latest' points to the highest version
                                latest_value = data.get("latest")
                                self.assertEqual(
                                    latest_value,
                                    highest_version,
                                    f"'latest' field is '{latest_value}' but should be '{highest_version}' (highest version) in {path_str}/manifest.json",
                                )


if __name__ == "__main__":
    unittest.main()
