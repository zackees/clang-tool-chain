"""
Integration tests for library deployment with sccache.

These tests verify that the --deploy-dependencies flag works correctly
with both regular clang wrappers and sccache-wrapped clang wrappers.

Tests cover:
- Windows DLL deployment (automatic for .exe, opt-in for .dll)
- Linux .so deployment (opt-in via --deploy-dependencies)
- macOS .dylib deployment (opt-in via --deploy-dependencies)
- Both clang-tool-chain-cpp and clang-tool-chain-sccache-cpp wrappers
"""

import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import pytest


def skip_if_sccache_unavailable():
    """Check if sccache is available (either in PATH or via iso-env)."""
    # First check if sccache is in PATH
    if shutil.which("sccache") is not None:
        return False

    # Try to invoke clang-tool-chain-sccache-cpp --help to trigger iso-env setup
    try:
        result = subprocess.run(
            ["clang-tool-chain-sccache-cpp", "--help"],
            capture_output=True,
            text=True,
            timeout=30,
        )
        return result.returncode != 0
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return True


# Common test source files
LIB_CPP_SOURCE = """
#include <iostream>
#include <string>

extern "C" {
    void print_message(const char* msg) {
        std::string message(msg);
        std::cout << "Library says: " << message << std::endl;
    }
}
"""

MAIN_CPP_SOURCE = """
#include <stdio.h>

extern "C" void print_message(const char* msg);

int main() {
    print_message("Hello from shared library!");
    return 0;
}
"""

SIMPLE_CPP_SOURCE = """
#include <iostream>
#include <string>

int main() {
    std::string msg = "Hello from executable!";
    std::cout << msg << std::endl;
    return 0;
}
"""


@pytest.mark.skipif(sys.platform == "win32", reason="Linux/macOS deployment tests")
class TestSharedLibraryDeploymentNonSccache(unittest.TestCase):
    """Test shared library deployment with regular clang wrappers (non-sccache)."""

    def setUp(self) -> None:
        """Set up test environment with temporary directory."""
        self.temp_dir = tempfile.mkdtemp()
        self.temp_path = Path(self.temp_dir)

        # Create source files
        self.lib_cpp = self.temp_path / "mylib.cpp"
        self.lib_cpp.write_text(LIB_CPP_SOURCE)

        self.main_cpp = self.temp_path / "main.cpp"
        self.main_cpp.write_text(MAIN_CPP_SOURCE)

        self.simple_cpp = self.temp_path / "simple.cpp"
        self.simple_cpp.write_text(SIMPLE_CPP_SOURCE)

    def tearDown(self) -> None:
        """Clean up temporary directory."""
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_so_deployment_with_flag(self) -> None:
        """Test Linux .so dependency deployment with --deploy-dependencies flag."""
        if sys.platform != "linux":
            pytest.skip("Linux-only test")

        # Build shared library with --deploy-dependencies flag
        ext = ".so"
        lib_output = self.temp_path / f"libmylib{ext}"
        result = subprocess.run(
            [
                "clang-tool-chain-cpp",
                "-shared",
                "-fPIC",
                str(self.lib_cpp),
                "-o",
                str(lib_output),
                "--deploy-dependencies",
            ],
            capture_output=True,
            text=True,
            timeout=60,
        )

        self.assertEqual(result.returncode, 0, f"Build should succeed\nStderr: {result.stderr}")
        self.assertTrue(lib_output.exists(), f"Output {ext} should exist at {lib_output}")

    def test_dylib_deployment_with_flag(self) -> None:
        """Test macOS .dylib dependency deployment with --deploy-dependencies flag."""
        if sys.platform != "darwin":
            pytest.skip("macOS-only test")

        # Build shared library with --deploy-dependencies flag
        ext = ".dylib"
        lib_output = self.temp_path / f"libmylib{ext}"
        result = subprocess.run(
            [
                "clang-tool-chain-cpp",
                "-shared",
                "-fPIC",
                str(self.lib_cpp),
                "-o",
                str(lib_output),
                "--deploy-dependencies",
            ],
            capture_output=True,
            text=True,
            timeout=60,
        )

        self.assertEqual(result.returncode, 0, f"Build should succeed\nStderr: {result.stderr}")
        self.assertTrue(lib_output.exists(), f"Output {ext} should exist at {lib_output}")

    def test_executable_deployment_with_flag(self) -> None:
        """Test executable dependency deployment with --deploy-dependencies flag."""
        # Build executable with --deploy-dependencies flag
        exe_output = self.temp_path / "simple"
        result = subprocess.run(
            [
                "clang-tool-chain-cpp",
                str(self.simple_cpp),
                "-o",
                str(exe_output),
                "--deploy-dependencies",
            ],
            capture_output=True,
            text=True,
            timeout=60,
        )

        self.assertEqual(result.returncode, 0, f"Build should succeed\nStderr: {result.stderr}")
        self.assertTrue(exe_output.exists(), f"Output executable should exist at {exe_output}")


@pytest.mark.serial
@pytest.mark.skipif(sys.platform == "win32", reason="Linux/macOS deployment tests")
@pytest.mark.skipif(skip_if_sccache_unavailable(), reason="sccache not available")
class TestSharedLibraryDeploymentSccache(unittest.TestCase):
    """Test shared library deployment with sccache wrappers."""

    @classmethod
    def setUpClass(cls):
        """Pre-install sccache once for all tests to avoid timeout during individual tests."""
        if shutil.which("sccache") is None:
            try:
                result = subprocess.run(
                    ["clang-tool-chain-sccache-cpp", "--help"],
                    capture_output=True,
                    text=True,
                    timeout=180,  # 3 minutes for initial download/setup
                )
                if result.returncode != 0:
                    print(f"Warning: sccache pre-installation failed: {result.stderr}", file=sys.stderr)
            except subprocess.TimeoutExpired:
                print("Warning: sccache pre-installation timed out", file=sys.stderr)
            except Exception as e:
                print(f"Warning: sccache pre-installation error: {e}", file=sys.stderr)

    def setUp(self) -> None:
        """Set up test environment with temporary directory."""
        self.temp_dir = tempfile.mkdtemp()
        self.temp_path = Path(self.temp_dir)
        self.original_dir = os.getcwd()
        os.chdir(self.temp_dir)

        # Create source files
        self.lib_cpp = self.temp_path / "mylib.cpp"
        self.lib_cpp.write_text(LIB_CPP_SOURCE)

        self.main_cpp = self.temp_path / "main.cpp"
        self.main_cpp.write_text(MAIN_CPP_SOURCE)

        self.simple_cpp = self.temp_path / "simple.cpp"
        self.simple_cpp.write_text(SIMPLE_CPP_SOURCE)

    def tearDown(self) -> None:
        """Clean up test environment."""
        os.chdir(self.original_dir)
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_sccache_so_deployment_with_flag(self) -> None:
        """Test Linux .so dependency deployment with sccache + --deploy-dependencies flag."""
        if sys.platform != "linux":
            pytest.skip("Linux-only test")

        # Build shared library with sccache and --deploy-dependencies flag
        ext = ".so"
        lib_output = self.temp_path / f"libmylib{ext}"
        result = subprocess.run(
            [
                "clang-tool-chain-sccache-cpp",
                "-shared",
                "-fPIC",
                str(self.lib_cpp),
                "-o",
                str(lib_output),
                "--deploy-dependencies",
            ],
            capture_output=True,
            text=True,
            timeout=60,
        )

        self.assertEqual(result.returncode, 0, f"Build should succeed\nStderr: {result.stderr}")
        self.assertTrue(lib_output.exists(), f"Output {ext} should exist at {lib_output}")

    def test_sccache_dylib_deployment_with_flag(self) -> None:
        """Test macOS .dylib dependency deployment with sccache + --deploy-dependencies flag."""
        if sys.platform != "darwin":
            pytest.skip("macOS-only test")

        # Build shared library with sccache and --deploy-dependencies flag
        ext = ".dylib"
        lib_output = self.temp_path / f"libmylib{ext}"
        result = subprocess.run(
            [
                "clang-tool-chain-sccache-cpp",
                "-shared",
                "-fPIC",
                str(self.lib_cpp),
                "-o",
                str(lib_output),
                "--deploy-dependencies",
            ],
            capture_output=True,
            text=True,
            timeout=60,
        )

        self.assertEqual(result.returncode, 0, f"Build should succeed\nStderr: {result.stderr}")
        self.assertTrue(lib_output.exists(), f"Output {ext} should exist at {lib_output}")

    def test_sccache_executable_deployment_with_flag(self) -> None:
        """Test executable dependency deployment with sccache + --deploy-dependencies flag."""
        # Build executable with sccache and --deploy-dependencies flag
        exe_output = self.temp_path / "simple"
        result = subprocess.run(
            [
                "clang-tool-chain-sccache-cpp",
                str(self.simple_cpp),
                "-o",
                str(exe_output),
                "--deploy-dependencies",
            ],
            capture_output=True,
            text=True,
            timeout=60,
        )

        self.assertEqual(result.returncode, 0, f"Build should succeed\nStderr: {result.stderr}")
        self.assertTrue(exe_output.exists(), f"Output executable should exist at {exe_output}")

        # Verify executable runs
        if sys.platform != "win32":
            exe_result = subprocess.run([str(exe_output)], capture_output=True, text=True, timeout=10)
            self.assertEqual(exe_result.returncode, 0, f"Executable should run\nStderr: {exe_result.stderr}")
            self.assertIn("Hello from executable!", exe_result.stdout)


@pytest.mark.skipif(sys.platform != "win32", reason="Windows-only deployment tests")
class TestWindowsDllDeploymentNonSccache(unittest.TestCase):
    """Test Windows DLL deployment with regular clang wrappers (non-sccache)."""

    def setUp(self) -> None:
        """Set up test environment with temporary directory."""
        self.temp_dir = tempfile.mkdtemp()
        self.temp_path = Path(self.temp_dir)

        # Create DLL source
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

        # Create simple executable source
        self.simple_cpp = self.temp_path / "simple.cpp"
        self.simple_cpp.write_text(SIMPLE_CPP_SOURCE)

    def tearDown(self) -> None:
        """Clean up temporary directory."""
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_exe_automatic_dll_deployment(self) -> None:
        """Test that Windows .exe builds automatically deploy MinGW DLLs."""
        exe_output = self.temp_path / "simple.exe"
        result = subprocess.run(
            [
                "clang-tool-chain-cpp",
                str(self.simple_cpp),
                "-o",
                str(exe_output),
            ],
            capture_output=True,
            text=True,
            timeout=60,
        )

        self.assertEqual(result.returncode, 0, f"Build should succeed\nStderr: {result.stderr}")
        self.assertTrue(exe_output.exists(), f"Output .exe should exist at {exe_output}")

        # Check for MinGW DLLs in output directory
        dll_files = list(self.temp_path.glob("*.dll"))
        if len(dll_files) > 0:
            dll_names = [dll.name.lower() for dll in dll_files]
            has_mingw_dll = any(
                "libwinpthread" in name or "libgcc" in name or "libstdc++" in name or "libc++" in name
                for name in dll_names
            )
            self.assertTrue(has_mingw_dll, f"Should have MinGW DLLs, found: {dll_names}")

    def test_dll_deployment_with_flag(self) -> None:
        """Test Windows .dll dependency deployment with --deploy-dependencies flag."""
        dll_output = self.temp_path / "mydll.dll"
        result = subprocess.run(
            [
                "clang-tool-chain-cpp",
                "-shared",
                str(self.dll_cpp),
                "-o",
                str(dll_output),
                "--deploy-dependencies",
            ],
            capture_output=True,
            text=True,
            timeout=60,
        )

        self.assertEqual(result.returncode, 0, f"Build should succeed\nStderr: {result.stderr}")
        self.assertTrue(dll_output.exists(), f"Output .dll should exist at {dll_output}")


@pytest.mark.serial
@pytest.mark.skipif(sys.platform != "win32", reason="Windows-only deployment tests")
class TestWindowsDllDeploymentSccache(unittest.TestCase):
    """Test Windows DLL deployment with sccache wrappers."""

    @classmethod
    def setUpClass(cls):
        """Pre-install sccache once for all tests."""
        if shutil.which("sccache") is None:
            try:
                result = subprocess.run(
                    ["clang-tool-chain-sccache-cpp", "--help"],
                    capture_output=True,
                    text=True,
                    timeout=180,
                )
                if result.returncode != 0:
                    print(f"Warning: sccache pre-installation failed: {result.stderr}", file=sys.stderr)
            except subprocess.TimeoutExpired:
                print("Warning: sccache pre-installation timed out", file=sys.stderr)
            except Exception as e:
                print(f"Warning: sccache pre-installation error: {e}", file=sys.stderr)

    def setUp(self) -> None:
        """Set up test environment with temporary directory."""
        self.temp_dir = tempfile.mkdtemp()
        self.temp_path = Path(self.temp_dir)
        self.original_dir = os.getcwd()
        os.chdir(self.temp_dir)

        # Create DLL source
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

        # Create simple executable source
        self.simple_cpp = self.temp_path / "simple.cpp"
        self.simple_cpp.write_text(SIMPLE_CPP_SOURCE)

    def tearDown(self) -> None:
        """Clean up test environment."""
        os.chdir(self.original_dir)
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_sccache_exe_automatic_dll_deployment(self) -> None:
        """Test that sccache + Windows .exe builds automatically deploy MinGW DLLs."""
        exe_output = self.temp_path / "simple.exe"
        result = subprocess.run(
            [
                "clang-tool-chain-sccache-cpp",
                str(self.simple_cpp),
                "-o",
                str(exe_output),
            ],
            capture_output=True,
            text=True,
            timeout=60,
        )

        self.assertEqual(result.returncode, 0, f"Build should succeed\nStderr: {result.stderr}")
        self.assertTrue(exe_output.exists(), f"Output .exe should exist at {exe_output}")

        # Verify executable runs
        exe_result = subprocess.run([str(exe_output)], capture_output=True, text=True, timeout=10)
        self.assertEqual(exe_result.returncode, 0, f"Executable should run\nStderr: {exe_result.stderr}")
        self.assertIn("Hello from executable!", exe_result.stdout)

    def test_sccache_dll_deployment_with_flag(self) -> None:
        """Test sccache + Windows .dll dependency deployment with --deploy-dependencies flag."""
        dll_output = self.temp_path / "mydll.dll"
        result = subprocess.run(
            [
                "clang-tool-chain-sccache-cpp",
                "-shared",
                str(self.dll_cpp),
                "-o",
                str(dll_output),
                "--deploy-dependencies",
            ],
            capture_output=True,
            text=True,
            timeout=60,
        )

        self.assertEqual(result.returncode, 0, f"Build should succeed\nStderr: {result.stderr}")
        self.assertTrue(dll_output.exists(), f"Output .dll should exist at {dll_output}")


class TestDeploymentFlagHandling(unittest.TestCase):
    """Test that --deploy-dependencies flag is correctly stripped and handled."""

    def test_flag_stripped_from_clang_args(self) -> None:
        """Test that --deploy-dependencies is stripped and doesn't reach clang."""
        from clang_tool_chain.execution.core import _extract_deploy_dependencies_flag

        # Test flag present
        args_with_flag = ["test.cpp", "--deploy-dependencies", "-o", "test.exe"]
        filtered, should_deploy = _extract_deploy_dependencies_flag(args_with_flag)
        self.assertEqual(filtered, ["test.cpp", "-o", "test.exe"])
        self.assertTrue(should_deploy)

        # Test flag absent
        args_without_flag = ["test.cpp", "-o", "test.exe"]
        filtered, should_deploy = _extract_deploy_dependencies_flag(args_without_flag)
        self.assertEqual(filtered, ["test.cpp", "-o", "test.exe"])
        self.assertFalse(should_deploy)

    def test_shared_library_output_path_extraction(self) -> None:
        """Test extraction of shared library output paths."""
        from clang_tool_chain.execution.core import _extract_shared_library_output_path

        # Test .dll extraction
        args = ["-shared", "lib.cpp", "-o", "lib.dll"]
        path = _extract_shared_library_output_path(args, "clang++")
        assert path is not None
        self.assertEqual(path.name, "lib.dll")

        # Test .so extraction
        args = ["-shared", "lib.cpp", "-o", "lib.so"]
        path = _extract_shared_library_output_path(args, "clang++")
        assert path is not None
        self.assertEqual(path.name, "lib.so")

        # Test .dylib extraction
        args = ["-shared", "lib.cpp", "-o", "lib.dylib"]
        path = _extract_shared_library_output_path(args, "clang++")
        assert path is not None
        self.assertEqual(path.name, "lib.dylib")

        # Test no -shared flag
        args = ["lib.cpp", "-o", "lib.dll"]
        path = _extract_shared_library_output_path(args, "clang++")
        self.assertIsNone(path)

    def test_executable_output_path_extraction(self) -> None:
        """Test extraction of executable output paths."""
        from clang_tool_chain.execution.core import _extract_executable_output_path

        # Test executable (no extension)
        args = ["main.cpp", "-o", "program"]
        path = _extract_executable_output_path(args, "clang++")
        assert path is not None
        self.assertEqual(path.name, "program")

        # Test .exe extraction
        args = ["main.cpp", "-o", "program.exe"]
        path = _extract_executable_output_path(args, "clang++")
        assert path is not None
        self.assertEqual(path.name, "program.exe")

        # Test compile-only mode
        args = ["-c", "main.cpp", "-o", "main.o"]
        path = _extract_executable_output_path(args, "clang++")
        self.assertIsNone(path)

        # Test shared library (should return None)
        args = ["-shared", "lib.cpp", "-o", "lib.so"]
        path = _extract_executable_output_path(args, "clang++")
        self.assertIsNone(path)


if __name__ == "__main__":
    unittest.main()
