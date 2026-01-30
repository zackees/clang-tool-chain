"""
Tests for ASAN (Address Sanitizer) runtime library linking on all platforms.

This test suite exposes and verifies the fix for undefined ASAN symbols
during linking when using -fsanitize=address.

Tests run on Windows, Linux, and macOS to ensure consistent ASAN support.
"""

import os
import platform
import subprocess
import tempfile
from pathlib import Path

import pytest


class TestASANLinking:
    """Test ASAN runtime library linking behavior."""

    @pytest.fixture
    def temp_dir(self):
        """Create a temporary directory for test files."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)

    @pytest.fixture
    def simple_cpp_file(self, temp_dir):
        """Create a simple C++ file for testing."""
        cpp_file = temp_dir / "test_asan.cpp"
        cpp_file.write_text(
            """
            #include <iostream>
            #include <vector>

            int main() {
                std::vector<int> v = {1, 2, 3, 4, 5};

                // Intentional out-of-bounds access to test ASAN
                // This should be caught by ASAN at runtime
                int* ptr = v.data();

                // Safe access
                for (size_t i = 0; i < v.size(); i++) {
                    std::cout << ptr[i] << " ";
                }
                std::cout << std::endl;

                return 0;
            }
            """
        )
        return cpp_file

    def test_asan_compile_only_succeeds(self, simple_cpp_file):
        """Test that compilation with ASAN succeeds (compile-only) on all platforms."""
        output_obj = simple_cpp_file.parent / "test_asan.o"

        cmd = [
            "clang-tool-chain-cpp",
            "-c",
            "-fsanitize=address",
            "-fsanitize=undefined",
            str(simple_cpp_file),
            "-o",
            str(output_obj),
        ]

        result = subprocess.run(cmd, capture_output=True, text=True)

        assert result.returncode == 0, f"Compile failed: {result.stderr}"
        assert output_obj.exists(), "Object file not created"

    def test_asan_link_executable_succeeds(self, simple_cpp_file):
        """
        Test that linking an executable with ASAN succeeds on all platforms.

        This test replicates the bug that was occurring in FastLED builds:
        - Code compiled with -fsanitize=address
        - But linking failed with undefined ASAN symbols

        After the fix, this should work on Linux, macOS, and Windows.
        """
        output_exe = simple_cpp_file.parent / "test_asan"
        if os.name == "nt":
            output_exe = simple_cpp_file.parent / "test_asan.exe"

        cmd = [
            "clang-tool-chain-cpp",
            "-fsanitize=address",
            "-fsanitize=undefined",
            str(simple_cpp_file),
            "-o",
            str(output_exe),
        ]

        result = subprocess.run(cmd, capture_output=True, text=True)

        # This should succeed after the fix
        assert result.returncode == 0, (
            f"Link failed with ASAN:\n"
            f"STDOUT: {result.stdout}\n"
            f"STDERR: {result.stderr}\n"
            f"This is the bug we're fixing - ASAN runtime not linked properly"
        )
        assert output_exe.exists(), "Executable not created"

    def test_asan_link_shared_library_succeeds(self, temp_dir):
        """Test that linking a shared library with ASAN succeeds on all platforms."""
        cpp_file = temp_dir / "test_lib.cpp"
        cpp_file.write_text(
            """
            #include <vector>

            extern "C" int test_function(int x) {
                std::vector<int> v = {1, 2, 3};
                return v[x % 3];  // Safe modulo access
            }
            """
        )

        # Platform-specific shared library extension
        if os.name == "nt":
            output_lib = temp_dir / "test.dll"
        elif platform.system() == "Darwin":
            output_lib = temp_dir / "libtest.dylib"
        else:
            output_lib = temp_dir / "libtest.so"

        cmd = [
            "clang-tool-chain-cpp",
            "-shared",
            "-fPIC",
            "-fsanitize=address",
            "-fsanitize=undefined",
            str(cpp_file),
            "-o",
            str(output_lib),
        ]

        result = subprocess.run(cmd, capture_output=True, text=True)

        # This should succeed after the fix
        assert result.returncode == 0, (
            f"Shared library link failed with ASAN:\nSTDOUT: {result.stdout}\nSTDERR: {result.stderr}"
        )
        assert output_lib.exists(), "Shared library not created"

    def test_asan_uses_shared_runtime(self, simple_cpp_file):
        """
        Test that ASAN uses shared/dynamic runtime library on all platforms.

        This test verifies the fix is working correctly by checking that:
        - Linux: Uses libclang_rt.asan.so (shared runtime)
        - Windows: Uses clang_rt.asan_dynamic-*.dll (dynamic runtime)
        - macOS: Uses libclang_rt.asan_osx_dynamic.dylib (dynamic runtime)
        """
        output_exe = simple_cpp_file.parent / "test_asan"
        if os.name == "nt":
            output_exe = simple_cpp_file.parent / "test_asan.exe"

        # Compile with ASAN
        compile_cmd = [
            "clang-tool-chain-cpp",
            "-fsanitize=address",
            str(simple_cpp_file),
            "-o",
            str(output_exe),
        ]

        result = subprocess.run(compile_cmd, capture_output=True, text=True)
        assert result.returncode == 0, f"Compilation failed: {result.stderr}"

        # Check that shared/dynamic runtime is being used
        system = platform.system()

        if system == "Linux":
            # Use ldd to check for shared ASAN library
            ldd_result = subprocess.run(
                ["ldd", str(output_exe)],
                capture_output=True,
                text=True,
            )
            assert "libclang_rt.asan" in ldd_result.stdout, (
                f"Expected shared ASAN runtime (libclang_rt.asan.so) but not found.\n"
                f"ldd output:\n{ldd_result.stdout}\n"
                f"This indicates static linking was used instead of shared."
            )

        elif system == "Darwin":
            # Use otool to check for dynamic ASAN library
            otool_result = subprocess.run(
                ["otool", "-L", str(output_exe)],
                capture_output=True,
                text=True,
            )
            # macOS may use either @rpath or absolute path
            has_asan_dylib = "libclang_rt.asan" in otool_result.stdout or "asan_osx_dynamic" in otool_result.stdout
            assert has_asan_dylib, (
                f"Expected dynamic ASAN runtime but not found.\n"
                f"otool output:\n{otool_result.stdout}\n"
                f"This indicates static linking was used instead of dynamic."
            )

        elif os.name == "nt":
            # Windows: Check that executable doesn't have static ASAN symbols embedded
            # Instead, it should depend on clang_rt.asan_dynamic-*.dll
            # We can verify this by checking the executable runs without errors
            # (static ASAN would fail if runtime not properly initialized)
            run_result = subprocess.run(
                [str(output_exe)],
                capture_output=True,
                text=True,
                timeout=5,
            )
            assert run_result.returncode == 0, (
                f"ASAN executable failed to run (may indicate static linking issue):\n"
                f"STDOUT: {run_result.stdout}\n"
                f"STDERR: {run_result.stderr}"
            )

    def test_asan_executable_runs(self, simple_cpp_file):
        """Test that ASAN-instrumented executable runs successfully on all platforms."""
        output_exe = simple_cpp_file.parent / "test_asan"
        if os.name == "nt":
            output_exe = simple_cpp_file.parent / "test_asan.exe"

        # Compile with ASAN
        compile_cmd = [
            "clang-tool-chain-cpp",
            "-fsanitize=address",
            "-fsanitize=undefined",
            str(simple_cpp_file),
            "-o",
            str(output_exe),
        ]

        result = subprocess.run(compile_cmd, capture_output=True, text=True)
        assert result.returncode == 0, f"Compilation failed: {result.stderr}"

        # Run the executable
        run_result = subprocess.run(
            [str(output_exe)],
            capture_output=True,
            text=True,
            timeout=5,
        )

        # Should run successfully (exit code 0)
        assert run_result.returncode == 0, (
            f"ASAN executable failed to run:\nSTDOUT: {run_result.stdout}\nSTDERR: {run_result.stderr}"
        )

        # Check output
        assert "1 2 3 4 5" in run_result.stdout, "Expected output not found"

    def test_asan_shared_library_deployed(self, simple_cpp_file):
        """
        Test that ASAN shared library is deployed with --deploy-dependencies on all platforms.

        This verifies the fix for deployment code not running on Linux/macOS (os.execv issue).
        """
        output_exe = simple_cpp_file.parent / "test_asan"
        if os.name == "nt":
            output_exe = simple_cpp_file.parent / "test_asan.exe"

        # Compile with ASAN and deploy-dependencies
        compile_cmd = [
            "clang-tool-chain-cpp",
            "-fsanitize=address",
            str(simple_cpp_file),
            "-o",
            str(output_exe),
            "--deploy-dependencies",
        ]

        result = subprocess.run(compile_cmd, capture_output=True, text=True)
        assert result.returncode == 0, f"Compilation failed: {result.stderr}"

        # Check if ASAN shared library was deployed
        output_dir = output_exe.parent
        system = platform.system()

        if system == "Linux":
            # Look for libclang_rt.asan.so in the output directory
            asan_libs = list(output_dir.glob("libclang_rt.asan*.so*"))

            # Use ldd to check what libraries are needed
            ldd_result = subprocess.run(
                ["ldd", str(output_exe)],
                capture_output=True,
                text=True,
            )

            # Check that either:
            # 1. libclang_rt.asan.so is deployed locally, OR
            # 2. libclang_rt.asan.so is found via system paths
            has_asan_lib = len(asan_libs) > 0 or "libclang_rt.asan" in ldd_result.stdout

            assert has_asan_lib, (
                f"ASAN runtime library not found on Linux.\n"
                f"Deployed libs in {output_dir}: {[f.name for f in output_dir.glob('*.so*')]}\n"
                f"ldd output:\n{ldd_result.stdout}"
            )

        elif system == "Darwin":
            # Look for libclang_rt.asan*.dylib in the output directory
            asan_libs = list(output_dir.glob("libclang_rt.asan*.dylib"))

            # Use otool to check what libraries are needed
            otool_result = subprocess.run(
                ["otool", "-L", str(output_exe)],
                capture_output=True,
                text=True,
            )

            has_asan_lib = len(asan_libs) > 0 or "libclang_rt.asan" in otool_result.stdout

            assert has_asan_lib, (
                f"ASAN runtime library not found on macOS.\n"
                f"Deployed libs in {output_dir}: {[f.name for f in output_dir.glob('*.dylib')]}\n"
                f"otool output:\n{otool_result.stdout}"
            )

        elif os.name == "nt":
            # Windows: Look for clang_rt.asan_dynamic-*.dll
            # Note: Windows GNU ABI automatically deploys DLLs even without --deploy-dependencies
            # This test verifies that it still works with the flag
            asan_dlls = list(output_dir.glob("*asan*.dll"))

            # For Windows, we just verify the executable runs
            # (DLL deployment is automatic for GNU ABI)
            run_result = subprocess.run(
                [str(output_exe)],
                capture_output=True,
                text=True,
                timeout=5,
            )

            assert run_result.returncode == 0, (
                f"ASAN executable failed to run on Windows:\n"
                f"STDOUT: {run_result.stdout}\n"
                f"STDERR: {run_result.stderr}\n"
                f"Deployed DLLs in {output_dir}: {[f.name for f in asan_dlls]}"
            )

    def test_asan_detects_memory_error(self, temp_dir):
        """
        Test that ASAN actually detects memory errors at runtime on all platforms.

        This verifies that ASAN is not only linking correctly, but also
        functioning properly to catch real memory errors.
        """
        cpp_file = temp_dir / "test_asan_error.cpp"
        cpp_file.write_text(
            """
            #include <cstdlib>

            int main() {
                int* ptr = new int[10];
                // Intentional heap buffer overflow
                int x = ptr[10];  // Out of bounds read
                delete[] ptr;
                return x;
            }
            """
        )

        output_exe = temp_dir / "test_asan_error"
        if os.name == "nt":
            output_exe = temp_dir / "test_asan_error.exe"

        # Compile with ASAN
        compile_cmd = [
            "clang-tool-chain-cpp",
            "-fsanitize=address",
            str(cpp_file),
            "-o",
            str(output_exe),
        ]

        compile_result = subprocess.run(compile_cmd, capture_output=True, text=True)
        assert compile_result.returncode == 0, f"Compilation failed: {compile_result.stderr}"

        # Run the executable - should detect heap buffer overflow
        run_result = subprocess.run(
            [str(output_exe)],
            capture_output=True,
            text=True,
            timeout=5,
        )

        # ASAN should detect the error and exit with non-zero code
        assert run_result.returncode != 0, "ASAN should have detected heap buffer overflow"

        # Check that ASAN error message is present
        error_output = run_result.stderr + run_result.stdout
        assert "heap-buffer-overflow" in error_output or "ASAN" in error_output or "ERROR" in error_output, (
            f"ASAN error message not found in output:\n{error_output}"
        )
