#!/usr/bin/env python3
"""
Unit tests for LLVM version consistency.

Ensures that the centralized LLVM version configuration in llvm_versions.py
matches the versions declared in the manifest.json files.
"""

import json
from pathlib import Path

import pytest

from clang_tool_chain.llvm_versions import (
    LLVM_VERSIONS,
    LLVMVersion,
    get_llvm_version,
    get_llvm_version_string,
    get_llvm_version_tuple,
    supports_ld64_lld_flag,
)

# Path to the manifest files relative to the repo root
REPO_ROOT = Path(__file__).parent.parent
MANIFEST_BASE = REPO_ROOT / "downloads-bins" / "assets" / "clang"


class TestLLVMVersionConfiguration:
    """Tests for the centralized LLVM version configuration."""

    def test_all_platforms_have_versions(self):
        """Verify all expected platforms have version entries."""
        expected_platforms = {"darwin", "linux", "win"}
        assert set(LLVM_VERSIONS.keys()) == expected_platforms

    def test_all_versions_are_21x_or_higher(self):
        """Verify all platforms use LLVM 21.x or higher."""
        for platform, version in LLVM_VERSIONS.items():
            assert version.major >= 21, f"Platform {platform} uses LLVM {version}, expected >= 21.x"

    def test_version_tuple_format(self):
        """Verify version tuples have correct format."""
        for _platform, version in LLVM_VERSIONS.items():
            assert isinstance(version, LLVMVersion)
            assert isinstance(version.major, int)
            assert isinstance(version.minor, int)
            assert isinstance(version.patch, int)
            assert version.major > 0
            assert version.minor >= 0
            assert version.patch >= 0

    def test_get_llvm_version_returns_correct_type(self):
        """Verify get_llvm_version returns LLVMVersion."""
        for platform in ["darwin", "linux", "win"]:
            version = get_llvm_version(platform)
            assert isinstance(version, LLVMVersion)

    def test_get_llvm_version_string_format(self):
        """Verify version strings have correct format."""
        for platform in ["darwin", "linux", "win"]:
            version_str = get_llvm_version_string(platform)
            parts = version_str.split(".")
            assert len(parts) == 3, f"Version string {version_str} should have 3 parts"
            for part in parts:
                assert part.isdigit(), f"Version part {part} should be numeric"

    def test_get_llvm_version_tuple_format(self):
        """Verify version tuples have correct format."""
        for platform in ["darwin", "linux", "win"]:
            version_tuple = get_llvm_version_tuple(platform)
            assert isinstance(version_tuple, tuple)
            assert len(version_tuple) == 3
            assert all(isinstance(v, int) for v in version_tuple)

    def test_unknown_platform_returns_default(self):
        """Verify unknown platforms return the default version."""
        version = get_llvm_version("unknown_platform")
        assert version is not None
        assert isinstance(version, LLVMVersion)

    def test_supports_ld64_lld_flag_for_21x(self):
        """Verify LLVM 21.x supports ld64.lld flag."""
        # All current platforms use LLVM 21.x which supports ld64.lld
        for platform in ["darwin", "linux", "win"]:
            assert supports_ld64_lld_flag(platform), f"Platform {platform} should support ld64.lld"

    def test_llvm_version_str(self):
        """Verify LLVMVersion __str__ works correctly."""
        version = LLVMVersion(21, 1, 6)
        assert str(version) == "21.1.6"

    def test_llvm_version_from_string(self):
        """Verify LLVMVersion.from_string works correctly."""
        version = LLVMVersion.from_string("21.1.6")
        assert version == LLVMVersion(21, 1, 6)

    def test_llvm_version_from_string_invalid(self):
        """Verify LLVMVersion.from_string raises on invalid input."""
        with pytest.raises(ValueError):
            LLVMVersion.from_string("21.1")
        with pytest.raises(ValueError):
            LLVMVersion.from_string("invalid")


class TestLLVMVersionMatchesManifest:
    """Tests that verify centralized versions match manifest.json files."""

    @pytest.fixture
    def manifest_versions(self) -> dict[str, dict[str, str]]:
        """Load versions from all manifest.json files."""
        versions = {}
        platform_dirs = {
            "darwin": ["x86_64", "arm64"],
            "linux": ["x86_64", "arm64"],
            "win": ["x86_64"],
        }

        for platform, archs in platform_dirs.items():
            versions[platform] = {}
            for arch in archs:
                manifest_path = MANIFEST_BASE / platform / arch / "manifest.json"
                if manifest_path.exists():
                    with open(manifest_path) as f:
                        manifest = json.load(f)
                        versions[platform][arch] = manifest.get("latest", "")

        return versions

    def test_darwin_version_matches_manifest(self, manifest_versions):
        """Verify darwin version in llvm_versions.py matches manifest."""
        if "darwin" not in manifest_versions:
            pytest.skip("Darwin manifests not found")

        expected_version = get_llvm_version_string("darwin")

        # Check both architectures have the same version as our config
        for arch in ["x86_64", "arm64"]:
            if arch in manifest_versions["darwin"]:
                manifest_version = manifest_versions["darwin"][arch]
                assert manifest_version == expected_version, (
                    f"darwin/{arch} manifest has version {manifest_version}, "
                    f"but llvm_versions.py has {expected_version}"
                )

    def test_linux_version_matches_manifest(self, manifest_versions):
        """Verify linux version in llvm_versions.py matches manifest."""
        if "linux" not in manifest_versions:
            pytest.skip("Linux manifests not found")

        expected_version = get_llvm_version_string("linux")

        for arch in ["x86_64", "arm64"]:
            if arch in manifest_versions["linux"]:
                manifest_version = manifest_versions["linux"][arch]
                assert manifest_version == expected_version, (
                    f"linux/{arch} manifest has version {manifest_version}, but llvm_versions.py has {expected_version}"
                )

    def test_win_version_matches_manifest(self, manifest_versions):
        """Verify win version in llvm_versions.py matches manifest."""
        if "win" not in manifest_versions:
            pytest.skip("Windows manifests not found")

        expected_version = get_llvm_version_string("win")

        for arch in ["x86_64"]:
            if arch in manifest_versions["win"]:
                manifest_version = manifest_versions["win"][arch]
                assert manifest_version == expected_version, (
                    f"win/{arch} manifest has version {manifest_version}, but llvm_versions.py has {expected_version}"
                )

    def test_no_old_19x_versions_in_manifests(self, manifest_versions):
        """Verify no manifests contain old 19.x versions as latest."""
        for platform, archs in manifest_versions.items():
            for arch, version in archs.items():
                if version:
                    major = int(version.split(".")[0])
                    assert major >= 21, f"{platform}/{arch} manifest has old version {version}, expected >= 21.x"


class TestManifestFilesConsistency:
    """Tests for manifest.json file consistency."""

    def test_manifest_files_exist(self):
        """Verify expected manifest files exist."""
        expected_manifests = [
            ("darwin", "x86_64"),
            ("darwin", "arm64"),
            ("linux", "x86_64"),
            ("linux", "arm64"),
            ("win", "x86_64"),
        ]

        for platform, arch in expected_manifests:
            manifest_path = MANIFEST_BASE / platform / arch / "manifest.json"
            assert manifest_path.exists(), f"Missing manifest: {manifest_path}"

    def test_manifest_files_valid_json(self):
        """Verify all manifest files are valid JSON."""
        for manifest_path in MANIFEST_BASE.rglob("manifest.json"):
            with open(manifest_path) as f:
                try:
                    data = json.load(f)
                    # Root manifests have 'platforms' key
                    # Platform manifests have 'latest' key
                    # Legacy manifests have 'assets' key
                    has_platforms = "platforms" in data
                    has_latest = "latest" in data
                    has_assets = "assets" in data
                    assert has_platforms or has_latest or has_assets, (
                        f"{manifest_path} missing 'latest', 'platforms', or 'assets' keys"
                    )
                except json.JSONDecodeError as e:
                    pytest.fail(f"Invalid JSON in {manifest_path}: {e}")

    def test_manifest_latest_version_has_entry(self):
        """Verify the 'latest' version has a corresponding entry."""
        for manifest_path in MANIFEST_BASE.rglob("manifest.json"):
            with open(manifest_path) as f:
                data = json.load(f)
                # Skip root manifests (they have 'platforms' instead of 'latest')
                if "platforms" in data:
                    continue
                latest = data.get("latest")
                if latest:
                    assert latest in data, f"{manifest_path}: 'latest' version {latest} has no corresponding entry"

    def test_manifest_entries_have_required_fields(self):
        """Verify manifest version entries have required fields."""
        required_fields = {"href", "sha256"}

        for manifest_path in MANIFEST_BASE.rglob("manifest.json"):
            with open(manifest_path) as f:
                data = json.load(f)
                # Skip root manifests (they have 'platforms' instead of version entries)
                if "platforms" in data:
                    continue
                for version, entry in data.items():
                    if version == "latest":
                        continue
                    if isinstance(entry, dict):
                        missing = required_fields - set(entry.keys())
                        assert not missing, f"{manifest_path} version {version} missing fields: {missing}"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
