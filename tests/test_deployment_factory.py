"""
Comprehensive tests for the deployment factory pattern.

Tests platform-specific deployer creation, platform detection,
and factory method functionality.
"""

import unittest
from unittest.mock import patch

from clang_tool_chain.deployment.base_deployer import BaseLibraryDeployer
from clang_tool_chain.deployment.factory import DeploymentFactory, create_deployer


class TestDeploymentFactory(unittest.TestCase):
    """Test suite for DeploymentFactory class."""

    # ========== Platform-Specific Deployer Creation ==========

    def test_create_windows_deployer(self):
        """Test creating Windows DLL deployer."""
        deployer = DeploymentFactory.create_deployer("windows", "x86_64")

        self.assertIsNotNone(deployer)
        assert deployer is not None  # Type narrowing for Pyright
        self.assertIsInstance(deployer, BaseLibraryDeployer)
        self.assertEqual(type(deployer).__name__, "DllDeployer")
        self.assertEqual(deployer.platform_name, "windows")
        self.assertEqual(deployer.arch, "x86_64")

    def test_create_windows_deployer_win32_alias(self):
        """Test creating Windows deployer using 'win32' platform name."""
        deployer = DeploymentFactory.create_deployer("win32", "x86_64")

        self.assertIsNotNone(deployer)
        self.assertEqual(type(deployer).__name__, "DllDeployer")

    def test_create_linux_deployer(self):
        """Test creating Linux .so deployer."""
        deployer = DeploymentFactory.create_deployer("linux", "x86_64")

        self.assertIsNotNone(deployer)
        assert deployer is not None  # Type narrowing for Pyright
        self.assertIsInstance(deployer, BaseLibraryDeployer)
        self.assertEqual(type(deployer).__name__, "SoDeployer")
        self.assertEqual(deployer.platform_name, "linux")
        self.assertEqual(deployer.arch, "x86_64")

    def test_create_linux_deployer_arm64(self):
        """Test creating Linux deployer for ARM64 architecture."""
        deployer = DeploymentFactory.create_deployer("linux", "arm64")

        self.assertIsNotNone(deployer)
        assert deployer is not None  # Type narrowing for Pyright
        self.assertEqual(type(deployer).__name__, "SoDeployer")
        self.assertEqual(deployer.arch, "arm64")

    def test_create_darwin_deployer(self):
        """Test creating macOS .dylib deployer."""
        deployer = DeploymentFactory.create_deployer("darwin", "x86_64")

        self.assertIsNotNone(deployer)
        assert deployer is not None  # Type narrowing for Pyright
        self.assertIsInstance(deployer, BaseLibraryDeployer)
        self.assertEqual(type(deployer).__name__, "DylibDeployer")
        self.assertEqual(deployer.platform_name, "darwin")
        self.assertEqual(deployer.arch, "x86_64")

    def test_create_darwin_deployer_macos_alias(self):
        """Test creating macOS deployer using 'macos' platform name."""
        deployer = DeploymentFactory.create_deployer("macos", "arm64")

        self.assertIsNotNone(deployer)
        assert deployer is not None  # Type narrowing for Pyright
        self.assertEqual(type(deployer).__name__, "DylibDeployer")
        self.assertEqual(deployer.arch, "arm64")

    def test_create_darwin_deployer_arm64(self):
        """Test creating macOS deployer for Apple Silicon."""
        deployer = DeploymentFactory.create_deployer("darwin", "arm64")

        self.assertIsNotNone(deployer)
        assert deployer is not None  # Type narrowing for Pyright
        self.assertEqual(type(deployer).__name__, "DylibDeployer")
        self.assertEqual(deployer.arch, "arm64")

    # ========== Unsupported Platforms ==========

    def test_create_unsupported_platform(self):
        """Test that unsupported platforms return None."""
        deployer = DeploymentFactory.create_deployer("freebsd", "x86_64")
        self.assertIsNone(deployer)

    def test_create_unsupported_platform_openbsd(self):
        """Test that OpenBSD returns None."""
        deployer = DeploymentFactory.create_deployer("openbsd", "x86_64")
        self.assertIsNone(deployer)

    def test_create_unsupported_platform_solaris(self):
        """Test that Solaris returns None."""
        deployer = DeploymentFactory.create_deployer("solaris", "sparc")
        self.assertIsNone(deployer)

    # ========== Platform Name Normalization ==========

    def test_platform_name_case_insensitive(self):
        """Test that platform names are case-insensitive."""
        deployers = [
            DeploymentFactory.create_deployer("WINDOWS", "x86_64"),
            DeploymentFactory.create_deployer("Windows", "x86_64"),
            DeploymentFactory.create_deployer("windows", "x86_64"),
        ]

        for deployer in deployers:
            self.assertIsNotNone(deployer)
            self.assertEqual(type(deployer).__name__, "DllDeployer")

    def test_platform_name_with_whitespace(self):
        """Test that platform names with whitespace are handled."""
        deployers = [
            DeploymentFactory.create_deployer(" linux ", "x86_64"),
            DeploymentFactory.create_deployer("  darwin  ", "x86_64"),
            DeploymentFactory.create_deployer(" windows ", "x86_64"),
        ]

        for deployer in deployers:
            self.assertIsNotNone(deployer)

    # ========== Current Platform Detection ==========

    @patch("sys.platform", "linux")
    def test_create_deployer_for_current_platform_linux(self):
        """Test automatic Linux detection."""
        deployer = DeploymentFactory.create_deployer_for_current_platform("x86_64")

        self.assertIsNotNone(deployer)
        self.assertEqual(type(deployer).__name__, "SoDeployer")

    @patch("sys.platform", "win32")
    def test_create_deployer_for_current_platform_windows(self):
        """Test automatic Windows detection."""
        deployer = DeploymentFactory.create_deployer_for_current_platform("x86_64")

        self.assertIsNotNone(deployer)
        self.assertEqual(type(deployer).__name__, "DllDeployer")

    @patch("sys.platform", "darwin")
    def test_create_deployer_for_current_platform_darwin(self):
        """Test automatic macOS detection."""
        deployer = DeploymentFactory.create_deployer_for_current_platform("x86_64")

        self.assertIsNotNone(deployer)
        self.assertEqual(type(deployer).__name__, "DylibDeployer")

    @patch("sys.platform", "freebsd")
    def test_create_deployer_for_current_platform_unsupported(self):
        """Test that unsupported current platforms return None."""
        deployer = DeploymentFactory.create_deployer_for_current_platform("x86_64")
        self.assertIsNone(deployer)

    # ========== Supported Platforms Query ==========

    def test_get_supported_platforms(self):
        """Test getting list of supported platforms."""
        platforms = DeploymentFactory.get_supported_platforms()

        self.assertIsInstance(platforms, list)
        self.assertEqual(len(platforms), 3)
        self.assertIn("windows", platforms)
        self.assertIn("linux", platforms)
        self.assertIn("darwin", platforms)

    def test_is_platform_supported_windows(self):
        """Test checking Windows support."""
        self.assertTrue(DeploymentFactory.is_platform_supported("windows"))
        self.assertTrue(DeploymentFactory.is_platform_supported("win32"))
        self.assertTrue(DeploymentFactory.is_platform_supported("WINDOWS"))

    def test_is_platform_supported_linux(self):
        """Test checking Linux support."""
        self.assertTrue(DeploymentFactory.is_platform_supported("linux"))
        self.assertTrue(DeploymentFactory.is_platform_supported("Linux"))
        self.assertTrue(DeploymentFactory.is_platform_supported(" linux "))

    def test_is_platform_supported_darwin(self):
        """Test checking macOS support."""
        self.assertTrue(DeploymentFactory.is_platform_supported("darwin"))
        self.assertTrue(DeploymentFactory.is_platform_supported("macos"))
        self.assertTrue(DeploymentFactory.is_platform_supported("DARWIN"))

    def test_is_platform_supported_unsupported(self):
        """Test checking unsupported platforms."""
        self.assertFalse(DeploymentFactory.is_platform_supported("freebsd"))
        self.assertFalse(DeploymentFactory.is_platform_supported("openbsd"))
        self.assertFalse(DeploymentFactory.is_platform_supported("solaris"))
        self.assertFalse(DeploymentFactory.is_platform_supported("aix"))

    # ========== Architecture Support ==========

    def test_create_deployer_x86_64(self):
        """Test creating deployers for x86_64 architecture."""
        deployers = [
            DeploymentFactory.create_deployer("windows", "x86_64"),
            DeploymentFactory.create_deployer("linux", "x86_64"),
            DeploymentFactory.create_deployer("darwin", "x86_64"),
        ]

        for deployer in deployers:
            self.assertIsNotNone(deployer)
            assert deployer is not None  # Type narrowing for Pyright
            self.assertEqual(deployer.arch, "x86_64")

    def test_create_deployer_arm64(self):
        """Test creating deployers for ARM64 architecture."""
        deployers = [
            DeploymentFactory.create_deployer("linux", "arm64"),
            DeploymentFactory.create_deployer("darwin", "arm64"),
        ]

        for deployer in deployers:
            self.assertIsNotNone(deployer)
            assert deployer is not None  # Type narrowing for Pyright
            self.assertEqual(deployer.arch, "arm64")

    def test_create_deployer_aarch64(self):
        """Test creating deployers for aarch64 architecture (Linux alias)."""
        deployer = DeploymentFactory.create_deployer("linux", "aarch64")

        self.assertIsNotNone(deployer)
        assert deployer is not None  # Type narrowing for Pyright
        self.assertEqual(deployer.arch, "aarch64")

    def test_create_deployer_i686(self):
        """Test creating deployers for i686 architecture."""
        deployer = DeploymentFactory.create_deployer("windows", "i686")

        self.assertIsNotNone(deployer)
        assert deployer is not None  # Type narrowing for Pyright
        self.assertEqual(deployer.arch, "i686")

    # ========== Module-Level Convenience Function ==========

    def test_create_deployer_function_windows(self):
        """Test module-level create_deployer() function for Windows."""
        deployer = create_deployer("windows", "x86_64")

        self.assertIsNotNone(deployer)
        self.assertEqual(type(deployer).__name__, "DllDeployer")

    def test_create_deployer_function_linux(self):
        """Test module-level create_deployer() function for Linux."""
        deployer = create_deployer("linux", "x86_64")

        self.assertIsNotNone(deployer)
        self.assertEqual(type(deployer).__name__, "SoDeployer")

    def test_create_deployer_function_darwin(self):
        """Test module-level create_deployer() function for macOS."""
        deployer = create_deployer("darwin", "arm64")

        self.assertIsNotNone(deployer)
        self.assertEqual(type(deployer).__name__, "DylibDeployer")

    def test_create_deployer_function_unsupported(self):
        """Test module-level create_deployer() returns None for unsupported platforms."""
        deployer = create_deployer("freebsd", "x86_64")
        self.assertIsNone(deployer)

    # ========== Default Architecture ==========

    def test_create_deployer_default_arch(self):
        """Test that default architecture is x86_64."""
        deployers = [
            DeploymentFactory.create_deployer("windows"),
            DeploymentFactory.create_deployer("linux"),
            DeploymentFactory.create_deployer("darwin"),
        ]

        for deployer in deployers:
            self.assertIsNotNone(deployer)
            assert deployer is not None  # Type narrowing for Pyright
            self.assertEqual(deployer.arch, "x86_64")

    # ========== Deployer Interface Verification ==========

    def test_deployer_has_required_methods(self):
        """Test that created deployers have required methods."""
        deployer = DeploymentFactory.create_deployer("linux", "x86_64")

        self.assertTrue(hasattr(deployer, "detect_dependencies"))
        self.assertTrue(hasattr(deployer, "is_deployable_library"))
        self.assertTrue(hasattr(deployer, "find_library_in_toolchain"))
        self.assertTrue(hasattr(deployer, "get_library_extension"))
        self.assertTrue(hasattr(deployer, "detect_all_dependencies"))
        self.assertTrue(hasattr(deployer, "deploy_library"))
        self.assertTrue(hasattr(deployer, "deploy_all"))

    def test_deployer_platform_name_correct(self):
        """Test that deployers have correct platform_name attribute."""
        windows_deployer = DeploymentFactory.create_deployer("windows", "x86_64")
        linux_deployer = DeploymentFactory.create_deployer("linux", "x86_64")
        darwin_deployer = DeploymentFactory.create_deployer("darwin", "x86_64")

        assert windows_deployer is not None  # Type narrowing for Pyright
        assert linux_deployer is not None  # Type narrowing for Pyright
        assert darwin_deployer is not None  # Type narrowing for Pyright
        self.assertEqual(windows_deployer.platform_name, "windows")
        self.assertEqual(linux_deployer.platform_name, "linux")
        self.assertEqual(darwin_deployer.platform_name, "darwin")


class TestFactoryEdgeCases(unittest.TestCase):
    """Test edge cases and error handling."""

    def test_empty_platform_name(self):
        """Test handling of empty platform name."""
        deployer = DeploymentFactory.create_deployer("", "x86_64")
        self.assertIsNone(deployer)

    def test_whitespace_only_platform_name(self):
        """Test handling of whitespace-only platform name."""
        deployer = DeploymentFactory.create_deployer("   ", "x86_64")
        self.assertIsNone(deployer)

    def test_empty_arch(self):
        """Test handling of empty architecture string."""
        # Empty arch should still create deployer (deployer may handle it)
        deployer = DeploymentFactory.create_deployer("linux", "")
        self.assertIsNotNone(deployer)
        assert deployer is not None  # Type narrowing for Pyright
        self.assertEqual(deployer.arch, "")

    def test_multiple_deployer_creation(self):
        """Test creating multiple deployers doesn't cause issues."""
        deployers = []
        for _ in range(10):
            deployers.append(DeploymentFactory.create_deployer("linux", "x86_64"))

        self.assertEqual(len(deployers), 10)
        for deployer in deployers:
            self.assertIsNotNone(deployer)
            self.assertEqual(type(deployer).__name__, "SoDeployer")

    def test_mixed_platform_creation(self):
        """Test creating deployers for different platforms in sequence."""
        platforms = ["windows", "linux", "darwin", "windows", "darwin", "linux"]
        expected_types = ["DllDeployer", "SoDeployer", "DylibDeployer", "DllDeployer", "DylibDeployer", "SoDeployer"]

        for platform, expected_type in zip(platforms, expected_types):
            deployer = DeploymentFactory.create_deployer(platform, "x86_64")
            self.assertIsNotNone(deployer)
            self.assertEqual(type(deployer).__name__, expected_type)


class TestFactoryIntegration(unittest.TestCase):
    """Integration tests using actual deployer functionality."""

    def test_windows_deployer_get_library_extension(self):
        """Test that Windows deployer returns correct extension."""
        deployer = DeploymentFactory.create_deployer("windows", "x86_64")
        assert deployer is not None  # Type narrowing for Pyright
        self.assertEqual(deployer.get_library_extension(), ".dll")

    def test_linux_deployer_get_library_extension(self):
        """Test that Linux deployer returns correct extension."""
        deployer = DeploymentFactory.create_deployer("linux", "x86_64")
        assert deployer is not None  # Type narrowing for Pyright
        self.assertEqual(deployer.get_library_extension(), ".so")

    def test_darwin_deployer_get_library_extension(self):
        """Test that macOS deployer returns correct extension."""
        deployer = DeploymentFactory.create_deployer("darwin", "x86_64")
        assert deployer is not None  # Type narrowing for Pyright
        self.assertEqual(deployer.get_library_extension(), ".dylib")

    def test_deployer_logger_initialized(self):
        """Test that deployers have logger initialized."""
        deployer = DeploymentFactory.create_deployer("linux", "x86_64")
        assert deployer is not None  # Type narrowing for Pyright
        self.assertTrue(hasattr(deployer, "logger"))
        self.assertIsNotNone(deployer.logger)


class TestFactorySummary(unittest.TestCase):
    """Summary test to verify overall factory functionality."""

    def test_all_platforms_supported(self):
        """Test that all advertised platforms can create deployers."""
        supported_platforms = DeploymentFactory.get_supported_platforms()

        for platform in supported_platforms:
            deployer = DeploymentFactory.create_deployer(platform, "x86_64")
            self.assertIsNotNone(deployer, f"Failed to create deployer for {platform}")
            self.assertIsInstance(deployer, BaseLibraryDeployer)

    def test_factory_consistency(self):
        """Test that factory creates consistent deployers for same inputs."""
        platform_arch_pairs = [
            ("windows", "x86_64"),
            ("linux", "arm64"),
            ("darwin", "x86_64"),
        ]

        for platform, arch in platform_arch_pairs:
            deployer1 = DeploymentFactory.create_deployer(platform, arch)
            deployer2 = DeploymentFactory.create_deployer(platform, arch)

            assert deployer1 is not None  # Type narrowing for Pyright
            assert deployer2 is not None  # Type narrowing for Pyright
            self.assertEqual(type(deployer1).__name__, type(deployer2).__name__)
            self.assertEqual(deployer1.platform_name, deployer2.platform_name)
            self.assertEqual(deployer1.arch, deployer2.arch)


if __name__ == "__main__":
    unittest.main()
