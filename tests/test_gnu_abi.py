"""
Test Windows GNU ABI support (v1.0.5+).

These tests verify that clang-tool-chain properly supports Windows GNU ABI target
(x86_64-w64-windows-gnu) with automatic MinGW sysroot download and configuration.

Windows defaults to GNU ABI (windows-gnu target) for cross-platform consistency,
matching the approach of zig cc. This uses Clang's native GNU ABI support for Windows,
with MinGW-w64 sysroot providing headers and libraries. The windows-gnu target provides
C++11 strict mode compatibility and avoids MSVC header issues.

Features tested:
- Automatic GNU ABI (windows-gnu target) injection on Windows
- MinGW-w64 sysroot download and configuration
- Target triple handling (auto vs explicit)
- MSVC variant commands for Windows-specific projects
- C++11 strict mode compatibility
"""

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import pytest


@pytest.mark.serial
@unittest.skipUnless(sys.platform == "win32", "Windows-only tests")
class TestGNUABI(unittest.TestCase):
    """
    Test suite for Windows GNU ABI support (v1.0.5+).

    Tests Clang's windows-gnu target with automatic MinGW-w64 sysroot download,
    target triple injection, and C++11 strict mode compatibility on Windows.
    """

    def setUp(self) -> None:
        """Set up test environment with temporary directory."""
        self.temp_dir = tempfile.mkdtemp()
        self.temp_path = Path(self.temp_dir)

        # Check if toolchain is accessible (skip tests if download fails)
        try:
            result = subprocess.run(
                ["clang-tool-chain-cpp", "--version"],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=120,  # 2 minute timeout for download
            )
            if result.returncode != 0:
                self.skipTest(f"Toolchain not accessible: {result.stderr}")
        except (subprocess.TimeoutExpired, FileNotFoundError, Exception) as e:
            self.skipTest(f"Toolchain not accessible: {e}")

    def tearDown(self) -> None:
        """Clean up temporary directory."""
        import shutil

        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_1_basic_cpp11_gnu_target(self) -> None:
        """
        Test basic C++11 standard library headers with automatic GNU ABI.

        Default Windows behavior (v1.0.5+): Automatically uses windows-gnu target
        (x86_64-w64-windows-gnu) with MinGW-w64 sysroot. This ensures C++11 strict
        mode compatibility without requiring C++14 extensions.
        """
        test_file = self.temp_path / "test_gnu_target.cpp"
        test_code = """#include <initializer_list>
#include <vector>
#include <string>

int main() {
    std::vector<int> v = {1, 2, 3};
    std::string s = "hello";
    return 0;
}
"""
        test_file.write_text(test_code)

        try:
            # Default should use GNU ABI on Windows
            result = subprocess.run(
                ["clang-tool-chain-cpp", "-std=c++11", "-c", str(test_file)],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                cwd=str(self.temp_path),
            )

            self.assertEqual(
                result.returncode,
                0,
                f"Compilation should succeed with GNU target.\nstdout: {result.stdout}\nstderr: {result.stderr}",
            )
            obj_file = self.temp_path / "test_gnu_target.o"
            self.assertTrue(obj_file.exists(), "Object file should be created")
        finally:
            # Cleanup
            for f in [test_file, self.temp_path / "test_gnu_target.o"]:
                if f.exists():
                    f.unlink()

    def test_2_cpp11_with_msvc_headers_should_fail(self) -> None:
        """
        Test MSVC variant with C++11 strict mode (expected to fail or skip).

        MSVC headers require C++14 extensions even in C++11 mode. This test
        demonstrates why GNU ABI is the default on Windows - it provides true
        C++11 strict mode compatibility. Uses clang-tool-chain-cpp-msvc variant.
        """
        test_file = self.temp_path / "test_msvc_target.cpp"
        test_code = """#include <type_traits>
#include <vector>

int main() {
    std::vector<int> v = {1, 2, 3};
    return 0;
}
"""
        test_file.write_text(test_code)

        try:
            # Using MSVC variant with strict C++11 mode should fail
            # due to MSVC headers using C++14 features
            result = subprocess.run(
                ["clang-tool-chain-cpp-msvc", "-std=c++11", "-Werror=c++14-extensions", "-c", str(test_file)],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                cwd=str(self.temp_path),
            )

            # We expect this to fail due to C++14 extensions in MSVC headers
            if result.returncode == 0:
                # If it succeeded, it might mean MSVC headers are not being used
                # or the strict mode is not being enforced
                self.skipTest(
                    "MSVC headers compiled successfully in strict C++11 mode. "
                    "This might indicate MSVC SDK is not installed or being used."
                )

            # Check that error mentions C++14 extensions
            error_output = (result.stderr or "").lower()
            has_cpp14_error = "c++14" in error_output or "auto" in error_output or "extension" in error_output
            self.assertTrue(
                has_cpp14_error,
                f"Expected C++14 extension error in stderr.\nstdout: {result.stdout}\nstderr: {result.stderr}",
            )
        finally:
            if test_file.exists():
                test_file.unlink()
            obj_file = self.temp_path / "test_msvc_target.o"
            if obj_file.exists():
                obj_file.unlink()

    def test_3_complete_compilation_and_linking(self) -> None:
        """
        Test complete compilation, linking, and execution with GNU ABI.

        Verifies that the automatic GNU ABI setup produces working executables
        that can run on Windows. Tests iostream, vector, string, and range-based for.
        """
        test_file = self.temp_path / "test_full.cpp"
        test_code = """#include <iostream>
#include <vector>
#include <string>

int main() {
    std::vector<std::string> messages = {"Hello", "World"};
    for (const auto& msg : messages) {
        std::cout << msg << " ";
    }
    std::cout << std::endl;
    return 0;
}
"""
        test_file.write_text(test_code)
        exe_file = self.temp_path / "test_program.exe"

        try:
            # Compile and link with default (GNU target)
            result = subprocess.run(
                ["clang-tool-chain-cpp", "-std=c++11", "-o", str(exe_file), str(test_file)],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                cwd=str(self.temp_path),
            )

            self.assertEqual(
                result.returncode,
                0,
                f"Compilation and linking should succeed.\nstdout: {result.stdout}\nstderr: {result.stderr}",
            )
            self.assertTrue(exe_file.exists(), "Executable should be created")

            # Try to run the program
            run_result = subprocess.run(
                [str(exe_file)], capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=5
            )

            self.assertEqual(run_result.returncode, 0, f"Program should run successfully.\nstderr: {run_result.stderr}")
            self.assertIn(
                "Hello World", run_result.stdout, f"Output should contain 'Hello World'. Got: {run_result.stdout}"
            )
        finally:
            for f in [test_file, exe_file]:
                if f.exists():
                    f.unlink()

    def test_4_verify_target_triple(self) -> None:
        """
        Test that verbose output shows GNU target triple injection.

        Verifies that the wrapper automatically injects --target=x86_64-w64-windows-gnu
        when compiling on Windows without an explicit --target flag.
        """
        test_file = self.temp_path / "test.cpp"
        test_file.write_text("int main() { return 0; }\n")

        try:
            # Run with verbose flag to see target triple
            result = subprocess.run(
                ["clang-tool-chain-cpp", "-v", "-c", str(test_file)],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                cwd=str(self.temp_path),
            )

            # Check for correct target in verbose output
            output = (result.stderr + result.stdout).lower()

            # Should contain GNU-style target triple
            has_gnu_target = "w64-mingw32" in output or "windows-gnu" in output

            self.assertTrue(
                has_gnu_target,
                f"Verbose output should contain GNU target triple (w64-mingw32 or windows-gnu).\n"
                f"stdout: {result.stdout}\nstderr: {result.stderr}",
            )
        finally:
            for f in [test_file, self.temp_path / "test.o"]:
                if f.exists():
                    f.unlink()

    def test_default_is_gnu_on_windows(self) -> None:
        """
        Test that Windows defaults to GNU ABI (v1.0.5+ behavior).

        Without explicit --target flag, clang-tool-chain-cpp should automatically
        use windows-gnu target (x86_64-w64-windows-gnu) for cross-platform consistency.
        """
        test_file = self.temp_path / "test_default.cpp"
        test_code = """#include <iostream>
int main() {
    std::cout << "Hello" << std::endl;
    return 0;
}
"""
        test_file.write_text(test_code)

        try:
            # Compile without explicit --target flag
            result = subprocess.run(
                ["clang-tool-chain-cpp", "-v", "-std=c++11", "-c", str(test_file)],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                cwd=str(self.temp_path),
            )

            # Should use GNU target by default
            output = (result.stderr + result.stdout).lower()
            has_gnu_target = "w64-mingw32" in output or "windows-gnu" in output

            self.assertTrue(
                has_gnu_target,
                f"Default should use GNU target on Windows.\nstdout: {result.stdout}\nstderr: {result.stderr}",
            )
            self.assertEqual(result.returncode, 0, f"Compilation should succeed.\nstderr: {result.stderr}")
        finally:
            for f in [test_file, self.temp_path / "test_default.o"]:
                if f.exists():
                    f.unlink()

    def test_explicit_msvc_target_override(self) -> None:
        """
        Test that explicit --target=x86_64-pc-windows-msvc overrides GNU default.

        Users can explicitly request MSVC ABI by passing --target flag, which
        prevents automatic GNU ABI injection. Requires Visual Studio SDK.
        """
        test_file = self.temp_path / "test_explicit_msvc.cpp"
        test_code = "int main() { return 0; }\n"
        test_file.write_text(test_code)

        try:
            # Explicitly request MSVC target
            result = subprocess.run(
                ["clang-tool-chain-cpp", "--target=x86_64-pc-windows-msvc", "-v", "-c", str(test_file)],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                cwd=str(self.temp_path),
            )

            # Should use MSVC target
            output = (result.stderr + result.stdout).lower()
            has_msvc_target = "msvc" in output and "mingw" not in output

            # Note: This test might fail if Visual Studio SDK is not installed
            if result.returncode != 0 and "visual studio" in output:
                self.skipTest("Visual Studio SDK not available for MSVC target testing")

            self.assertTrue(
                has_msvc_target or result.returncode != 0,
                f"Should attempt MSVC target when explicitly requested.\nstdout: {result.stdout}\nstderr: {result.stderr}",
            )
        finally:
            for f in [test_file, self.temp_path / "test_explicit_msvc.o"]:
                if f.exists():
                    f.unlink()

    def test_c_compilation_gnu_default(self) -> None:
        """
        Test that C compilation also defaults to GNU ABI on Windows.

        Both clang-tool-chain-c and clang-tool-chain-cpp should use windows-gnu target
        by default on Windows (v1.0.5+).
        """
        test_file = self.temp_path / "test_c.c"
        test_code = """#include <stdio.h>
int main() {
    printf("Hello from C\\n");
    return 0;
}
"""
        test_file.write_text(test_code)

        try:
            # Compile C code with default target
            result = subprocess.run(
                ["clang-tool-chain-c", "-v", "-c", str(test_file)],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                cwd=str(self.temp_path),
            )

            # Should use GNU target
            output = (result.stderr + result.stdout).lower()
            has_gnu_target = "w64-mingw32" in output or "windows-gnu" in output

            self.assertTrue(
                has_gnu_target,
                f"C compilation should use GNU target by default.\nstdout: {result.stdout}\nstderr: {result.stderr}",
            )
            self.assertEqual(result.returncode, 0, f"C compilation should succeed.\nstderr: {result.stderr}")
        finally:
            for f in [test_file, self.temp_path / "test_c.o"]:
                if f.exists():
                    f.unlink()

    def test_msvc_variant_command_exists(self) -> None:
        """
        Test that MSVC variant commands are available.

        clang-tool-chain-c-msvc and clang-tool-chain-cpp-msvc provide opt-in
        MSVC ABI support for Windows-specific projects that require MSVC compatibility.
        """
        # Test that clang-tool-chain-c-msvc exists
        result_c = subprocess.run(
            ["clang-tool-chain-c-msvc", "--version"], capture_output=True, text=True, encoding="utf-8", errors="replace"
        )

        self.assertEqual(
            result_c.returncode,
            0,
            f"clang-tool-chain-c-msvc should be available.\nstdout: {result_c.stdout}\nstderr: {result_c.stderr}",
        )

        # Test that clang-tool-chain-cpp-msvc exists
        result_cpp = subprocess.run(
            ["clang-tool-chain-cpp-msvc", "--version"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )

        self.assertEqual(
            result_cpp.returncode,
            0,
            f"clang-tool-chain-cpp-msvc should be available.\nstdout: {result_cpp.stdout}\nstderr: {result_cpp.stderr}",
        )

        # Both should report clang version
        self.assertIn("clang", result_c.stdout.lower(), "Should report clang version")
        self.assertIn("clang", result_cpp.stdout.lower(), "Should report clang version")

    def test_mingw_headers_integrated_in_clang_installation(self) -> None:
        """
        Test that MinGW headers are integrated into Clang installation (v2.0.0+).

        Verifies that MinGW headers, sysroot, and compiler-rt are included in the main
        Clang archive, eliminating the need for a separate MinGW download.

        This is the new architecture where:
        - MinGW headers are in <clang_root>/include/
        - Sysroot is in <clang_root>/x86_64-w64-mingw32/
        - Compiler-rt is in <clang_root>/lib/clang/<version>/
        """
        from clang_tool_chain.wrapper import get_platform_binary_dir

        # Get the clang installation root
        clang_bin_dir = get_platform_binary_dir()
        clang_root = clang_bin_dir.parent

        # Check for MinGW headers in include/
        include_dir = clang_root / "include"
        self.assertTrue(
            include_dir.exists(),
            f"MinGW headers should be integrated in Clang installation at {include_dir}",
        )

        # Check for key MinGW header files
        windows_h = include_dir / "windows.h"
        mingw_h = include_dir / "_mingw.h"

        self.assertTrue(
            windows_h.exists(),
            f"windows.h should exist in integrated headers at {windows_h}",
        )
        self.assertTrue(
            mingw_h.exists(),
            f"_mingw.h should exist in integrated headers at {mingw_h}",
        )

        # Check for sysroot directory
        sysroot = clang_root / "x86_64-w64-mingw32"
        self.assertTrue(
            sysroot.exists(),
            f"MinGW sysroot should be integrated in Clang installation at {sysroot}",
        )

        # Check for sysroot libraries
        sysroot_lib = sysroot / "lib"
        self.assertTrue(
            sysroot_lib.exists(),
            f"Sysroot lib directory should exist at {sysroot_lib}",
        )

        # Check that there are import libraries (.a files)
        import_libs = list(sysroot_lib.glob("*.a"))
        self.assertGreater(
            len(import_libs),
            0,
            f"Should have import libraries in {sysroot_lib}",
        )

        # Check for compiler-rt in lib/clang/
        clang_lib = clang_root / "lib" / "clang"
        self.assertTrue(
            clang_lib.exists(),
            f"Clang lib directory should exist at {clang_lib}",
        )

        # Find version directory (should be exactly one)
        version_dirs = [d for d in clang_lib.iterdir() if d.is_dir()]
        self.assertGreater(
            len(version_dirs),
            0,
            f"Should have at least one version directory in {clang_lib}",
        )

        # Check for resource headers in first version directory
        version_dir = version_dirs[0]
        resource_include = version_dir / "include"
        if resource_include.exists():
            # Check for common compiler intrinsic headers
            intrinsic_headers = list(resource_include.glob("*mmintrin.h"))
            self.assertGreater(
                len(intrinsic_headers),
                0,
                f"Should have intrinsic headers in {resource_include}",
            )

        # Verify no separate mingw directory exists (old architecture)
        from clang_tool_chain.downloader import get_home_toolchain_dir

        toolchain_dir = get_home_toolchain_dir()
        old_mingw_dir = toolchain_dir / "mingw"

        # It's OK if the directory exists but doesn't have the current arch
        # (might be from old installations), but it should not be the primary location
        if old_mingw_dir.exists():
            # If it exists, the headers in clang_root should still be the primary ones
            self.assertTrue(
                include_dir.exists(),
                "Even if old mingw dir exists, integrated headers should be present",
            )

    def test_pthread_usage(self) -> None:
        """
        Test that pthread headers and libraries work correctly with GNU ABI.

        This verifies that MinGW's winpthreads library is accessible and that
        threading support works after the include path ordering fix. MinGW headers
        (including pthread.h) should be available via -isystem, while Clang's
        standard headers take precedence via -I.
        """
        test_file = self.temp_path / "test_pthread.cpp"
        test_code = """#include <pthread.h>
#include <iostream>

void* thread_func(void* arg) {
    std::cout << "Thread running" << std::endl;
    return nullptr;
}

int main() {
    pthread_t thread;
    int result = pthread_create(&thread, nullptr, thread_func, nullptr);
    if (result != 0) {
        std::cerr << "Failed to create thread" << std::endl;
        return 1;
    }
    pthread_join(thread, nullptr);
    std::cout << "Thread completed" << std::endl;
    return 0;
}
"""
        test_file.write_text(test_code)
        exe_file = self.temp_path / "test_pthread.exe"

        try:
            # Compile and link with pthread support
            result = subprocess.run(
                ["clang-tool-chain-cpp", str(test_file), "-o", str(exe_file)],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                cwd=str(self.temp_path),
            )

            self.assertEqual(
                result.returncode,
                0,
                f"pthread compilation should succeed.\nstdout: {result.stdout}\nstderr: {result.stderr}",
            )
            self.assertTrue(exe_file.exists(), "Executable should be created")

            # Run the program to verify pthread works
            run_result = subprocess.run(
                [str(exe_file)], capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=5
            )

            self.assertEqual(
                run_result.returncode, 0, f"pthread program should run successfully.\nstderr: {run_result.stderr}"
            )
            self.assertIn(
                "Thread running",
                run_result.stdout,
                f"Output should contain 'Thread running'. Got: {run_result.stdout}",
            )
            self.assertIn(
                "Thread completed",
                run_result.stdout,
                f"Output should contain 'Thread completed'. Got: {run_result.stdout}",
            )
        finally:
            for f in [test_file, exe_file]:
                if f.exists():
                    f.unlink()


@unittest.skipUnless(sys.platform == "win32", "MSVC ABI tests are Windows-only")
class TestMSVCABI(unittest.TestCase):
    """
    Test MSVC ABI support on Windows (opt-in via -msvc variants).

    These tests verify that the MSVC variant commands (clang-tool-chain-c-msvc,
    clang-tool-chain-cpp-msvc) properly inject MSVC target and detect Windows SDK.

    MSVC ABI is opt-in for Windows-specific projects that require compatibility
    with Visual Studio-compiled libraries. Most tests skip gracefully if Visual
    Studio SDK is not installed.
    """

    def test_msvc_target_injection(self) -> None:
        """
        Test that MSVC variants inject --target=x86_64-pc-windows-msvc.

        Verifies that clang-tool-chain-c-msvc and clang-tool-chain-cpp-msvc
        automatically add the MSVC target triple in verbose output.
        """
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create a simple C file
            test_file = Path(temp_dir) / "test.c"
            test_file.write_text("int main() { return 0; }\n")

            # Compile with -msvc variant and capture verbose output to see target
            result = subprocess.run(
                ["clang-tool-chain-c-msvc", "-v", "-c", str(test_file), "-o", str(Path(temp_dir) / "test.o")],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
            )

            # Check that the target triple appears in verbose output
            output = (result.stdout or "") + (result.stderr or "")
            self.assertIn(
                "x86_64-pc-windows-msvc",
                output,
                f"MSVC target triple should appear in verbose output.\nFull output:\n{output}",
            )

            # Should not contain GNU target
            self.assertNotIn(
                "x86_64-w64-windows-gnu",
                output,
                f"GNU target should NOT appear when using MSVC variant.\nFull output:\n{output}",
            )

    def test_msvc_respects_user_target(self) -> None:
        """
        Test that MSVC variants respect explicit --target override.

        Users can override the MSVC variant's automatic target injection by
        providing their own --target flag (e.g., forcing GNU ABI).
        """
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create a simple C file
            test_file = Path(temp_dir) / "test.c"
            test_file.write_text("int main() { return 0; }\n")

            # Use MSVC variant but provide GNU target explicitly
            result = subprocess.run(
                [
                    "clang-tool-chain-c-msvc",
                    "-v",
                    "--target=x86_64-w64-windows-gnu",
                    "-c",
                    str(test_file),
                    "-o",
                    str(Path(temp_dir) / "test.o"),
                ],
                capture_output=True,
                text=True,
            )

            # Should see user's GNU target, not MSVC target
            output = (result.stdout or "") + (result.stderr or "")
            self.assertIn(
                "x86_64-w64-windows-gnu",
                output,
                f"User's explicit target should be used.\nFull output:\n{output}",
            )

    def test_msvc_basic_compilation(self) -> None:
        """
        Test basic object file compilation with MSVC variant.

        Attempts to compile a simple C++ file with iostream using the MSVC ABI.
        Gracefully skips if Visual Studio SDK is not installed.
        """
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create a simple C++ file
            test_file = Path(temp_dir) / "test.cpp"
            test_file.write_text("""
#include <iostream>
int main() {
    std::cout << "Hello MSVC" << std::endl;
    return 0;
}
""")

            # Try to compile with MSVC variant
            result = subprocess.run(
                ["clang-tool-chain-cpp-msvc", "-c", str(test_file), "-o", str(Path(temp_dir) / "test.o")],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
            )

            output = (result.stdout or "") + (result.stderr or "")

            # If Visual Studio SDK is not available, skip this test gracefully
            if result.returncode != 0 and any(
                keyword in output.lower() for keyword in ["windows sdk", "visual studio", "vcruntime.h", "corecrt.h"]
            ):
                self.skipTest("Visual Studio SDK not available for MSVC target testing")

            # Otherwise, compilation should succeed
            self.assertEqual(
                result.returncode,
                0,
                f"Compilation with MSVC variant should succeed.\nstdout: {result.stdout}\nstderr: {result.stderr}",
            )

            # Verify object file was created
            obj_file = Path(temp_dir) / "test.o"
            self.assertTrue(obj_file.exists(), "Object file should be created")

    def test_msvc_complete_build(self) -> None:
        """
        Test complete compilation, linking, and execution with MSVC ABI.

        Produces a working executable using MSVC ABI and runs it to verify output.
        Requires Visual Studio SDK; gracefully skips if not available.
        """
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create a simple C++ file
            test_file = Path(temp_dir) / "test.cpp"
            test_file.write_text("""
#include <iostream>
int main() {
    std::cout << "Hello MSVC" << std::endl;
    return 0;
}
""")

            exe_file = Path(temp_dir) / "test.exe"

            # Try to compile and link with MSVC variant
            result = subprocess.run(
                ["clang-tool-chain-cpp-msvc", str(test_file), "-o", str(exe_file)],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
            )

            output = (result.stdout or "") + (result.stderr or "")

            # If Visual Studio SDK is not available, skip this test gracefully
            if result.returncode != 0 and any(
                keyword in output.lower()
                for keyword in ["windows sdk", "visual studio", "vcruntime.h", "corecrt.h", "libcmt", "msvcrt"]
            ):
                self.skipTest("Visual Studio SDK not available for MSVC target testing")

            # Otherwise, linking should succeed
            self.assertEqual(
                result.returncode,
                0,
                f"Linking with MSVC variant should succeed.\nstdout: {result.stdout}\nstderr: {result.stderr}",
            )

            # Verify executable was created
            self.assertTrue(exe_file.exists(), "Executable file should be created")

            # Try to run the executable
            run_result = subprocess.run(
                [str(exe_file)], capture_output=True, text=True, encoding="utf-8", errors="replace"
            )
            self.assertEqual(run_result.returncode, 0, "Executable should run successfully")
            self.assertIn("Hello MSVC", run_result.stdout, "Executable should produce expected output")

    def test_gnu_vs_msvc_symbol_differences(self) -> None:
        """
        Test that GNU and MSVC ABIs produce different name mangling.

        Integration test that verifies GNU ABI (default) and MSVC ABI (-msvc variant)
        use different C++ name mangling schemes. Uses llvm-nm to inspect symbols.
        Requires Visual Studio SDK for MSVC compilation.

        Optimization (Iteration 10): Simplified source code (single method, no separate implementation)
        reduces compilation time from 14.90s to target <8s.
        """
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create a C++ file with minimal class (single method for faster compilation)
            test_file = Path(temp_dir) / "test.cpp"
            test_file.write_text("""
class C {
public:
    void m(int x);
};

void C::m(int x) {}

extern "C" int f() { return 0; }
""")

            # Compile with GNU variant
            gnu_obj = Path(temp_dir) / "test_gnu.o"
            result_gnu = subprocess.run(
                ["clang-tool-chain-cpp", "-c", str(test_file), "-o", str(gnu_obj)],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
            )

            # Compile with MSVC variant
            msvc_obj = Path(temp_dir) / "test_msvc.o"
            result_msvc = subprocess.run(
                ["clang-tool-chain-cpp-msvc", "-c", str(test_file), "-o", str(msvc_obj)],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
            )

            # Skip if MSVC compilation failed due to missing SDK
            if result_msvc.returncode != 0:
                output = result_msvc.stdout + result_msvc.stderr
                if any(
                    keyword in output.lower()
                    for keyword in ["windows sdk", "visual studio", "vcruntime.h", "corecrt.h"]
                ):
                    self.skipTest("Visual Studio SDK not available for MSVC target testing")

            # Both should succeed
            self.assertEqual(result_gnu.returncode, 0, f"GNU compilation failed:\n{result_gnu.stderr}")
            self.assertEqual(result_msvc.returncode, 0, f"MSVC compilation failed:\n{result_msvc.stderr}")

            # Use llvm-nm to check symbol names
            nm_gnu = subprocess.run(
                ["clang-tool-chain-nm", str(gnu_obj)],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
            )

            nm_msvc = subprocess.run(
                ["clang-tool-chain-nm", str(msvc_obj)],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
            )

            # Both should succeed
            self.assertEqual(nm_gnu.returncode, 0, "llvm-nm should work on GNU object")
            self.assertEqual(nm_msvc.returncode, 0, "llvm-nm should work on MSVC object")

            # Symbol names should be different (different name mangling)
            # GNU typically uses _ZN format, MSVC uses ?name@ format
            # The extern "C" function should be the same though
            self.assertIn("f", nm_gnu.stdout, "GNU object should have f symbol")
            self.assertIn("f", nm_msvc.stdout, "MSVC object should have f symbol")

            # But the mangled names should be different
            # This is the key difference between ABIs
            gnu_symbols = set(nm_gnu.stdout.split())
            msvc_symbols = set(nm_msvc.stdout.split())

            # Check that there are differences (not identical symbol sets)
            self.assertNotEqual(
                gnu_symbols,
                msvc_symbols,
                "GNU and MSVC should produce different symbols due to different name mangling",
            )

    def test_msvc_sdk_warning_display(self) -> None:
        """
        Test that SDK warning function works correctly.

        Verifies that _print_msvc_sdk_warning() produces helpful guidance about
        Visual Studio SDK installation and setup when SDK is not detected.
        """
        # This test verifies that the warning function works
        # We can't easily test it in actual compilation without mocking env vars,
        # but we can at least verify the function exists and can be called

        # This should not raise an exception
        import io
        import sys as sys_module

        from clang_tool_chain.wrapper import _print_msvc_sdk_warning

        # Capture stderr
        old_stderr = sys_module.stderr
        try:
            sys_module.stderr = io.StringIO()
            _print_msvc_sdk_warning()
            warning_output = sys_module.stderr.getvalue()

            # Verify warning contains expected content
            self.assertIn("Windows SDK", warning_output, "Warning should mention Windows SDK")
            self.assertIn("Visual Studio", warning_output, "Warning should mention Visual Studio")
            self.assertIn("clang-tool-chain-c", warning_output, "Warning should suggest GNU alternative")

        finally:
            sys_module.stderr = old_stderr


if __name__ == "__main__":
    unittest.main()
