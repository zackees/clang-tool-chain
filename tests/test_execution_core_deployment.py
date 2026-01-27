"""
Integration tests for execution core shared library deployment.

These tests verify that the factory-based deployer integration works correctly
in execution/core.py for Linux and macOS shared library deployment.
"""

import os
import sys
import tempfile
import unittest
from pathlib import Path

import pytest

from clang_tool_chain import wrapper
from clang_tool_chain.downloader import ToolchainInfrastructureError


@pytest.mark.skipif(sys.platform == "win32", reason="Linux/macOS deployment tests only")
class TestSharedLibraryDeployment(unittest.TestCase):
    """Test shared library dependency deployment via execution core."""

    def setUp(self) -> None:
        """Set up test environment with temporary directory."""
        self.temp_dir = tempfile.mkdtemp()
        self.temp_path = Path(self.temp_dir)

        # Create a simple C++ shared library source
        self.lib_cpp = self.temp_path / "mylib.cpp"
        self.lib_cpp.write_text(
            """
#include <iostream>
#include <string>

extern "C" {
    void print_message(const char* msg) {
        std::string message(msg);
        std::cout << "Library says: " << message << std::endl;
    }
}
"""
        )

        # Create a C++ executable that uses the library
        self.main_cpp = self.temp_path / "main.cpp"
        self.main_cpp.write_text(
            """
#include <stdio.h>

extern "C" void print_message(const char* msg);

int main() {
    print_message("Hello from shared library!");
    return 0;
}
"""
        )

    def tearDown(self) -> None:
        """Clean up temporary directory."""
        import shutil

        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_linux_so_deployment_with_flag(self) -> None:
        """Test Linux .so dependency deployment with --deploy-dependencies flag."""
        if sys.platform != "linux":
            pytest.skip("Linux-only test")

        try:
            # Build shared library with --deploy-dependencies flag
            lib_output = self.temp_path / "libmylib.so"
            result = wrapper.run_tool(
                "clang++",
                [
                    "-shared",
                    "-fPIC",
                    str(self.lib_cpp),
                    "-o",
                    str(lib_output),
                    "--deploy-dependencies",
                ],
            )

            self.assertEqual(result, 0, "Shared library build should succeed")
            self.assertTrue(lib_output.exists(), f"Output .so should exist at {lib_output}")

            # Check if any .so files were deployed to the output directory
            # Note: May or may not deploy depending on dependencies detected
            so_files = list(self.temp_path.glob("*.so*"))
            # We should at least have the output library
            self.assertGreaterEqual(len(so_files), 1, "At least output .so should exist")

        except ToolchainInfrastructureError:
            raise

    def test_macos_dylib_deployment_with_flag(self) -> None:
        """Test macOS .dylib dependency deployment with --deploy-dependencies flag."""
        if sys.platform != "darwin":
            pytest.skip("macOS-only test")

        try:
            # Build shared library with --deploy-dependencies flag
            lib_output = self.temp_path / "libmylib.dylib"
            result = wrapper.run_tool(
                "clang++",
                [
                    "-shared",
                    "-fPIC",
                    str(self.lib_cpp),
                    "-o",
                    str(lib_output),
                    "--deploy-dependencies",
                ],
            )

            self.assertEqual(result, 0, "Shared library build should succeed")
            self.assertTrue(lib_output.exists(), f"Output .dylib should exist at {lib_output}")

            # Check if any .dylib files were deployed to the output directory
            # Note: May or may not deploy depending on dependencies detected
            dylib_files = list(self.temp_path.glob("*.dylib"))
            # We should at least have the output library
            self.assertGreaterEqual(len(dylib_files), 1, "At least output .dylib should exist")

        except ToolchainInfrastructureError:
            raise

    def test_deployment_disabled_via_env_var(self) -> None:
        """Test that CLANG_TOOL_CHAIN_NO_DEPLOY_LIBS disables deployment."""
        platform_name, _ = wrapper.get_platform_info()

        if platform_name == "win":
            pytest.skip("Linux/macOS test only")

        # Determine output extension
        ext = ".so" if platform_name == "linux" else ".dylib"
        lib_output = self.temp_path / f"libmylib{ext}"

        try:
            # Set environment variable to disable deployment
            old_env = os.environ.get("CLANG_TOOL_CHAIN_NO_DEPLOY_LIBS")
            os.environ["CLANG_TOOL_CHAIN_NO_DEPLOY_LIBS"] = "1"

            try:
                result = wrapper.run_tool(
                    "clang++",
                    [
                        "-shared",
                        "-fPIC",
                        str(self.lib_cpp),
                        "-o",
                        str(lib_output),
                        "--deploy-dependencies",
                    ],
                )

                self.assertEqual(result, 0, "Build should succeed even with deployment disabled")
                self.assertTrue(lib_output.exists(), f"Output library should exist at {lib_output}")

                # With deployment disabled, we should only have the output library
                lib_files = list(self.temp_path.glob(f"*{ext}*"))
                self.assertEqual(len(lib_files), 1, "Should only have output library (no deps deployed)")

            finally:
                # Restore environment
                if old_env is None:
                    os.environ.pop("CLANG_TOOL_CHAIN_NO_DEPLOY_LIBS", None)
                else:
                    os.environ["CLANG_TOOL_CHAIN_NO_DEPLOY_LIBS"] = old_env

        except ToolchainInfrastructureError:
            raise

    def test_verbose_logging_via_env_var(self) -> None:
        """Test that CLANG_TOOL_CHAIN_LIB_DEPLOY_VERBOSE enables verbose logging."""
        platform_name, _ = wrapper.get_platform_info()

        if platform_name == "win":
            pytest.skip("Linux/macOS test only")

        # Determine output extension
        ext = ".so" if platform_name == "linux" else ".dylib"
        lib_output = self.temp_path / f"libmylib{ext}"

        try:
            # Set environment variable for verbose logging
            old_env = os.environ.get("CLANG_TOOL_CHAIN_LIB_DEPLOY_VERBOSE")
            os.environ["CLANG_TOOL_CHAIN_LIB_DEPLOY_VERBOSE"] = "1"

            try:
                result = wrapper.run_tool(
                    "clang++",
                    [
                        "-shared",
                        "-fPIC",
                        str(self.lib_cpp),
                        "-o",
                        str(lib_output),
                        "--deploy-dependencies",
                    ],
                )

                self.assertEqual(result, 0, "Build should succeed with verbose logging")
                self.assertTrue(lib_output.exists(), f"Output library should exist at {lib_output}")

                # Note: We can't easily verify verbose output in unit test,
                # but we verify it doesn't break the build

            finally:
                # Restore environment
                if old_env is None:
                    os.environ.pop("CLANG_TOOL_CHAIN_LIB_DEPLOY_VERBOSE", None)
                else:
                    os.environ["CLANG_TOOL_CHAIN_LIB_DEPLOY_VERBOSE"] = old_env

        except ToolchainInfrastructureError:
            raise


@pytest.mark.skipif(sys.platform != "win32", reason="Windows DLL deployment tests only")
class TestWindowsDllDeployment(unittest.TestCase):
    """Test Windows DLL dependency deployment via execution core."""

    def setUp(self) -> None:
        """Set up test environment with temporary directory."""
        self.temp_dir = tempfile.mkdtemp()
        self.temp_path = Path(self.temp_dir)

        # Create a simple C++ DLL source
        self.dll_cpp = self.temp_path / "mydll.cpp"
        self.dll_cpp.write_text(
            """
#include <iostream>
#include <string>

extern "C" __declspec(dllexport) void print_message(const char* msg) {
    std::string message(msg);
    std::cout << "DLL says: " << message << std::endl;
}
"""
        )

    def tearDown(self) -> None:
        """Clean up temporary directory."""
        import shutil

        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_windows_dll_deployment_with_flag(self) -> None:
        """Test Windows .dll dependency deployment with --deploy-dependencies flag."""
        if sys.platform != "win32":
            pytest.skip("Windows-only test")

        try:
            # Build DLL with --deploy-dependencies flag
            # Use C++ stdlib to ensure we get MinGW DLLs
            dll_output = self.temp_path / "mydll.dll"
            result = wrapper.run_tool(
                "clang++",
                [
                    "-shared",
                    str(self.dll_cpp),
                    "-o",
                    str(dll_output),
                    "--deploy-dependencies",
                ],
            )

            self.assertEqual(result, 0, "DLL build should succeed")
            self.assertTrue(dll_output.exists(), f"Output .dll should exist at {dll_output}")

            # Check if MinGW runtime DLLs were deployed
            dll_files = list(self.temp_path.glob("*.dll"))

            # With C++ stdlib usage and GNU ABI, we should get runtime DLLs
            # Note: Deployment happens but may not always copy DLLs if they're already up-to-date
            # or if the binary doesn't have dependencies we consider deployable
            self.assertGreaterEqual(len(dll_files), 1, "Should have at least output DLL")

            # If we have more than 1 DLL, check for MinGW DLLs
            if len(dll_files) > 1:
                dll_names = [dll.name.lower() for dll in dll_files]
                has_mingw_dll = any(
                    "libwinpthread" in name or "libgcc" in name or "libstdc++" in name or "libc++" in name
                    for name in dll_names
                )
                # If DLLs were deployed, they should be MinGW DLLs
                if len(dll_files) > 1:
                    self.assertTrue(
                        has_mingw_dll or len(dll_files) == 1, "If DLLs deployed, should include MinGW runtime DLLs"
                    )

        except ToolchainInfrastructureError:
            raise


if __name__ == "__main__":
    unittest.main()
