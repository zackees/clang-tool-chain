"""
Tests for macOS SDK detection and sysroot handling.

These tests verify that the automatic SDK detection works correctly on macOS
and that the wrapper properly injects -isysroot when needed.
"""

import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from clang_tool_chain import wrapper


class TestMacOSSDKDetection(unittest.TestCase):
    """Test macOS SDK detection and sysroot handling."""

    @unittest.skipUnless(sys.platform == "darwin", "macOS-specific test")
    def test_xcrun_sdk_detection(self) -> None:
        """Test that xcrun can detect the SDK path on macOS."""
        result = subprocess.run(["xcrun", "--show-sdk-path"], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, "xcrun should successfully detect SDK path")
        sdk_path = result.stdout.strip()
        self.assertTrue(sdk_path, "SDK path should not be empty")
        self.assertTrue(Path(sdk_path).exists(), f"SDK path should exist: {sdk_path}")
        self.assertIn(".sdk", sdk_path, "SDK path should contain .sdk")

    @unittest.skipUnless(sys.platform == "darwin", "macOS-specific test")
    def test_sysroot_injection(self) -> None:
        """Test that -isysroot is automatically injected on macOS."""
        # Test with empty args
        args = ["-c", "test.c"]
        modified_args = wrapper._add_macos_sysroot_if_needed(args)

        # Should have added -isysroot at the beginning
        self.assertGreaterEqual(len(modified_args), len(args) + 2, "Should add -isysroot and path")
        self.assertEqual(modified_args[0], "-isysroot", "First arg should be -isysroot")
        self.assertTrue(Path(modified_args[1]).exists(), f"SDK path should exist: {modified_args[1]}")

    @unittest.skipUnless(sys.platform == "darwin", "macOS-specific test")
    def test_sysroot_not_added_when_present(self) -> None:
        """Test that -isysroot is not added if already present."""
        args = ["-isysroot", "/some/path", "-c", "test.c"]
        modified_args = wrapper._add_macos_sysroot_if_needed(args)

        # Should be unchanged
        self.assertEqual(args, modified_args, "-isysroot should not be added when already present")

    @unittest.skipUnless(sys.platform == "darwin", "macOS-specific test")
    def test_sysroot_disabled_by_env_var(self) -> None:
        """Test that CLANG_TOOL_CHAIN_NO_SYSROOT disables automatic sysroot."""
        # Set environment variable
        old_value = os.environ.get("CLANG_TOOL_CHAIN_NO_SYSROOT")
        os.environ["CLANG_TOOL_CHAIN_NO_SYSROOT"] = "1"

        try:
            args = ["-c", "test.c"]
            modified_args = wrapper._add_macos_sysroot_if_needed(args)

            # Should be unchanged
            self.assertEqual(args, modified_args, "Sysroot should not be added when disabled")
        finally:
            # Restore environment
            if old_value is None:
                os.environ.pop("CLANG_TOOL_CHAIN_NO_SYSROOT", None)
            else:
                os.environ["CLANG_TOOL_CHAIN_NO_SYSROOT"] = old_value

    @unittest.skipUnless(sys.platform == "darwin", "macOS-specific test")
    def test_sysroot_respects_sdkroot_env(self) -> None:
        """Test that SDKROOT environment variable is respected."""
        # Set SDKROOT
        old_value = os.environ.get("SDKROOT")
        os.environ["SDKROOT"] = "/custom/sdk/path"

        try:
            args = ["-c", "test.c"]
            modified_args = wrapper._add_macos_sysroot_if_needed(args)

            # Should be unchanged (clang will use SDKROOT)
            self.assertEqual(args, modified_args, "Sysroot should not be added when SDKROOT is set")
        finally:
            # Restore environment
            if old_value is None:
                os.environ.pop("SDKROOT", None)
            else:
                os.environ["SDKROOT"] = old_value

    @unittest.skipUnless(sys.platform == "darwin", "macOS-specific test")
    def test_sysroot_not_added_for_nostdinc(self) -> None:
        """Test that -isysroot is not added when -nostdinc is present."""
        for flag in ["-nostdinc", "-nostdinc++", "-nostdlib", "-ffreestanding"]:
            with self.subTest(flag=flag):
                args = [flag, "-c", "test.c"]
                modified_args = wrapper._add_macos_sysroot_if_needed(args)

                # Should be unchanged
                self.assertEqual(args, modified_args, f"Sysroot should not be added when {flag} is present")

    @unittest.skipUnless(sys.platform == "darwin", "macOS-specific test")
    def test_compilation_with_system_headers(self) -> None:
        """Test that compilation works with system headers on macOS."""
        # Create temporary test file
        temp_dir = tempfile.mkdtemp()
        try:
            test_c = Path(temp_dir) / "test_sdk.c"
            test_c.write_text('#include <stdio.h>\nint main() { printf("test\\n"); return 0; }')

            output = Path(temp_dir) / "test_sdk"

            # Compile using run_tool (which should auto-add -isysroot)
            result = wrapper.run_tool("clang", [str(test_c), "-o", str(output)])

            self.assertEqual(result, 0, "Compilation should succeed with automatic SDK detection")
            self.assertTrue(output.exists(), f"Output executable should exist at {output}")

            # Verify it runs
            run_result = subprocess.run([str(output)], capture_output=True, text=True)
            self.assertEqual(run_result.returncode, 0, "Executable should run successfully")
            self.assertIn("test", run_result.stdout, "Output should contain expected text")
        except RuntimeError as e:
            self.skipTest(f"Binaries not installed: {e}")
        finally:
            import shutil

            shutil.rmtree(temp_dir, ignore_errors=True)

    @unittest.skipUnless(sys.platform == "darwin", "macOS-specific test")
    def test_cpp_compilation_with_iostream(self) -> None:
        """Test that C++ compilation works with iostream on macOS."""
        # Create temporary test file
        temp_dir = tempfile.mkdtemp()
        try:
            test_cpp = Path(temp_dir) / "test_sdk.cpp"
            test_cpp.write_text('#include <iostream>\nint main() { std::cout << "test" << std::endl; return 0; }')

            output = Path(temp_dir) / "test_sdk"

            # Compile using run_tool (which should auto-add -isysroot)
            result = wrapper.run_tool("clang++", [str(test_cpp), "-o", str(output)])

            self.assertEqual(result, 0, "C++ compilation should succeed with automatic SDK detection")
            self.assertTrue(output.exists(), f"Output executable should exist at {output}")

            # Verify it runs
            run_result = subprocess.run([str(output)], capture_output=True, text=True)
            self.assertEqual(run_result.returncode, 0, "C++ executable should run successfully")
            self.assertIn("test", run_result.stdout, "Output should contain expected text")
        except RuntimeError as e:
            self.skipTest(f"Binaries not installed: {e}")
        finally:
            import shutil

            shutil.rmtree(temp_dir, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
