"""
Unit tests for wrapper module functionality.

These tests verify platform detection, binary path resolution,
and tool execution infrastructure.
"""

import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from clang_tool_chain import wrapper


class TestPlatformDetection(unittest.TestCase):
    """Test platform and architecture detection."""

    @patch("platform.system")
    @patch("platform.machine")
    def test_windows_x86_64(self, mock_machine, mock_system):
        """Test Windows x86_64 detection."""
        mock_system.return_value = "Windows"
        mock_machine.return_value = "AMD64"

        platform_name, arch = wrapper.get_platform_info()

        self.assertEqual(platform_name, "win")
        self.assertEqual(arch, "x86_64")

    @patch("platform.system")
    @patch("platform.machine")
    def test_linux_x86_64(self, mock_machine, mock_system):
        """Test Linux x86_64 detection."""
        mock_system.return_value = "Linux"
        mock_machine.return_value = "x86_64"

        platform_name, arch = wrapper.get_platform_info()

        self.assertEqual(platform_name, "linux")
        self.assertEqual(arch, "x86_64")

    @patch("platform.system")
    @patch("platform.machine")
    def test_linux_aarch64(self, mock_machine, mock_system):
        """Test Linux ARM64 detection."""
        mock_system.return_value = "Linux"
        mock_machine.return_value = "aarch64"

        platform_name, arch = wrapper.get_platform_info()

        self.assertEqual(platform_name, "linux")
        self.assertEqual(arch, "aarch64")

    @patch("platform.system")
    @patch("platform.machine")
    def test_darwin_x86_64(self, mock_machine, mock_system):
        """Test macOS x86_64 detection."""
        mock_system.return_value = "Darwin"
        mock_machine.return_value = "x86_64"

        platform_name, arch = wrapper.get_platform_info()

        self.assertEqual(platform_name, "darwin")
        self.assertEqual(arch, "x86_64")

    @patch("platform.system")
    @patch("platform.machine")
    def test_darwin_arm64(self, mock_machine, mock_system):
        """Test macOS ARM64 detection."""
        mock_system.return_value = "Darwin"
        mock_machine.return_value = "arm64"

        platform_name, arch = wrapper.get_platform_info()

        self.assertEqual(platform_name, "darwin")
        self.assertEqual(arch, "aarch64")

    @patch("platform.system")
    def test_unsupported_platform(self, mock_system):
        """Test that unsupported platforms raise an error."""
        mock_system.return_value = "FreeBSD"

        with self.assertRaises(RuntimeError) as context:
            wrapper.get_platform_info()

        self.assertIn("Unsupported platform", str(context.exception))

    @patch("platform.system")
    @patch("platform.machine")
    def test_unsupported_architecture(self, mock_machine, mock_system):
        """Test that unsupported architectures raise an error."""
        mock_system.return_value = "Linux"
        mock_machine.return_value = "i686"

        with self.assertRaises(RuntimeError) as context:
            wrapper.get_platform_info()

        self.assertIn("Unsupported architecture", str(context.exception))


class TestAssetsDirectory(unittest.TestCase):
    """Test assets directory location."""

    def test_get_assets_dir(self):
        """Test that get_assets_dir returns a valid path."""
        assets_dir = wrapper.get_assets_dir()

        self.assertIsInstance(assets_dir, Path)
        self.assertTrue(str(assets_dir).endswith("assets"))
        # Check that it's in the project root (not inside clang_tool_chain package)
        self.assertNotIn(str(Path("src") / "clang_tool_chain" / "assets"), str(assets_dir))


class TestBinaryPathResolution(unittest.TestCase):
    """Test binary path resolution."""

    @patch("clang_tool_chain.wrapper.get_platform_info")
    @patch("clang_tool_chain.wrapper.get_assets_dir")
    def test_windows_binary_dir(self, mock_assets_dir, mock_platform):
        """Test Windows binary directory path."""
        mock_platform.return_value = ("win", "x86_64")
        mock_assets_dir.return_value = Path("/fake/assets")

        # This will raise RuntimeError since the path doesn't exist
        with self.assertRaises(RuntimeError):
            wrapper.get_platform_binary_dir()

    @patch("clang_tool_chain.wrapper.get_platform_info")
    @patch("clang_tool_chain.wrapper.get_assets_dir")
    def test_linux_x86_binary_dir(self, mock_assets_dir, mock_platform):
        """Test Linux x86_64 binary directory path."""
        mock_platform.return_value = ("linux", "x86_64")
        mock_assets_dir.return_value = Path("/fake/assets")

        with self.assertRaises(RuntimeError):
            wrapper.get_platform_binary_dir()

    @patch("clang_tool_chain.wrapper.get_platform_info")
    @patch("clang_tool_chain.wrapper.get_assets_dir")
    def test_linux_arm_binary_dir(self, mock_assets_dir, mock_platform):
        """Test Linux ARM64 binary directory path."""
        mock_platform.return_value = ("linux", "aarch64")
        mock_assets_dir.return_value = Path("/fake/assets")

        with self.assertRaises(RuntimeError):
            wrapper.get_platform_binary_dir()

    @patch("clang_tool_chain.wrapper.get_platform_info")
    @patch("clang_tool_chain.wrapper.get_assets_dir")
    def test_darwin_x86_binary_dir(self, mock_assets_dir, mock_platform):
        """Test macOS x86_64 binary directory path."""
        mock_platform.return_value = ("darwin", "x86_64")
        mock_assets_dir.return_value = Path("/fake/assets")

        with self.assertRaises(RuntimeError):
            wrapper.get_platform_binary_dir()

    @patch("clang_tool_chain.wrapper.get_platform_info")
    @patch("clang_tool_chain.wrapper.get_assets_dir")
    def test_darwin_arm_binary_dir(self, mock_assets_dir, mock_platform):
        """Test macOS ARM64 binary directory path."""
        mock_platform.return_value = ("darwin", "aarch64")
        mock_assets_dir.return_value = Path("/fake/assets")

        with self.assertRaises(RuntimeError):
            wrapper.get_platform_binary_dir()

    def test_missing_binaries_error_message(self):
        """Test that missing binaries produce a helpful error message."""
        with self.assertRaises(RuntimeError) as context:
            wrapper.get_platform_binary_dir()

        error_msg = str(context.exception)
        self.assertIn("Binaries not found", error_msg)
        self.assertIn("download", error_msg.lower())


class TestToolBinaryResolution(unittest.TestCase):
    """Test finding specific tool binaries."""

    def test_find_tool_without_binaries(self):
        """Test that finding a tool fails when binaries are not installed."""
        with self.assertRaises(RuntimeError):
            wrapper.find_tool_binary("clang")


class TestRunTool(unittest.TestCase):
    """Test tool execution functions."""

    @patch("clang_tool_chain.wrapper.find_tool_binary")
    @patch("subprocess.run")
    def test_run_tool_success(self, mock_run, mock_find):
        """Test successful tool execution."""
        mock_find.return_value = Path("/fake/bin/clang")
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_run.return_value = mock_result

        result = wrapper.run_tool("clang", ["--version"])

        self.assertEqual(result, 0)
        mock_run.assert_called_once()

    @patch("clang_tool_chain.wrapper.find_tool_binary")
    @patch("subprocess.run")
    def test_run_tool_failure(self, mock_run, mock_find):
        """Test tool execution with non-zero exit code."""
        mock_find.return_value = Path("/fake/bin/clang")
        mock_result = MagicMock()
        mock_result.returncode = 1
        mock_run.return_value = mock_result

        result = wrapper.run_tool("clang", ["-invalid-flag"])

        self.assertEqual(result, 1)

    @patch("clang_tool_chain.wrapper.find_tool_binary")
    @patch("subprocess.run")
    def test_run_tool_not_found(self, mock_run, mock_find):
        """Test tool execution when binary doesn't exist."""
        mock_find.return_value = Path("/fake/bin/nonexistent")
        mock_run.side_effect = FileNotFoundError()

        with self.assertRaises(RuntimeError) as context:
            wrapper.run_tool("nonexistent", [])

        self.assertIn("Tool not found", str(context.exception))


class TestWrapperEntryPoints(unittest.TestCase):
    """Test wrapper entry point functions."""

    def test_wrapper_functions_exist(self):
        """Test that all wrapper entry points are defined."""
        entry_points = [
            "clang_main",
            "clang_cpp_main",
            "lld_main",
            "llvm_ar_main",
            "llvm_nm_main",
            "llvm_objdump_main",
            "llvm_objcopy_main",
            "llvm_ranlib_main",
            "llvm_strip_main",
            "llvm_readelf_main",
            "llvm_as_main",
            "llvm_dis_main",
            "clang_format_main",
            "clang_tidy_main",
        ]

        for entry_point in entry_points:
            self.assertTrue(
                hasattr(wrapper, entry_point),
                f"Missing entry point: {entry_point}",
            )
            self.assertTrue(
                callable(getattr(wrapper, entry_point)),
                f"Entry point not callable: {entry_point}",
            )


if __name__ == "__main__":
    unittest.main()
