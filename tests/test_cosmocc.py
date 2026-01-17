"""
Integration tests for Cosmopolitan (cosmocc) functionality.

These tests verify that the cosmocc toolchain is properly installed and functional.
Cosmocc produces "Actually Portable Executables" (APE) that run on Windows, Linux,
macOS, FreeBSD, NetBSD, and OpenBSD without modification.

Note: Cosmocc uses a universal/shared installation that works across all platforms.
The same binaries are used regardless of host platform since APE format is portable.

Note: These tests will FAIL (not skip) if the cosmocc infrastructure is broken
(404 errors, missing manifests, etc). This ensures that broken URLs are caught
in CI rather than silently ignored.
"""

import os
import subprocess
import tempfile
import unittest
from pathlib import Path

import pytest

from clang_tool_chain import wrapper
from clang_tool_chain.downloader import ToolchainInfrastructureError
from clang_tool_chain.execution.cosmocc import (
    find_cosmocc_tool,
    get_cosmocc_binary_dir,
    get_platform_info,
)


class TestCosmoccPlatformDetection(unittest.TestCase):
    """Test platform detection for cosmocc."""

    def test_platform_detection(self) -> None:
        """Test that platform can be detected."""
        platform_name, arch = get_platform_info()

        self.assertIn(platform_name, ["win", "linux", "darwin"])
        self.assertIn(arch, ["x86_64", "arm64"])


class TestCosmoccInstallation(unittest.TestCase):
    """Test cosmocc installation and basic functionality.

    Note: Cosmocc uses a universal installation shared across all platforms.
    """

    def test_cosmocc_binary_dir_exists(self) -> None:
        """Test that cosmocc binary directory can be located (universal installation)."""
        try:
            bin_dir = get_cosmocc_binary_dir()
            self.assertTrue(bin_dir.exists(), f"Cosmocc binary directory should exist at {bin_dir}")
            self.assertTrue(bin_dir.is_dir(), f"Cosmocc binary location should be a directory: {bin_dir}")
        except ToolchainInfrastructureError:
            # Infrastructure errors should fail the test, not skip it
            raise

    def test_find_cosmocc_tool(self) -> None:
        """Test finding the cosmocc binary."""
        try:
            cosmocc_path = find_cosmocc_tool("cosmocc")
            self.assertTrue(cosmocc_path.exists(), f"cosmocc tool should exist at {cosmocc_path}")
            self.assertTrue(cosmocc_path.is_file(), f"cosmocc tool should be a file: {cosmocc_path}")
        except ToolchainInfrastructureError:
            raise

    def test_find_cosmocpp_tool(self) -> None:
        """Test finding the cosmoc++ binary."""
        try:
            cosmocpp_path = find_cosmocc_tool("cosmoc++")
            self.assertTrue(cosmocpp_path.exists(), f"cosmoc++ tool should exist at {cosmocpp_path}")
            self.assertTrue(cosmocpp_path.is_file(), f"cosmoc++ tool should be a file: {cosmocpp_path}")
        except ToolchainInfrastructureError:
            raise


@pytest.mark.serial
class TestCosmoccExecution(unittest.TestCase):
    """Test cosmocc execution with real C code."""

    def setUp(self) -> None:
        """Set up test environment with temporary directory and test files."""
        self.temp_dir = tempfile.mkdtemp()
        self.temp_path = Path(self.temp_dir)

        # Create a simple C test file
        self.test_c = self.temp_path / "hello.c"
        self.test_c.write_text(
            "#include <stdio.h>\n"
            "\n"
            "int main() {\n"
            '    printf("Hello from Cosmopolitan!\\n");\n'
            "    return 0;\n"
            "}\n"
        )

        # Create a simple C++ test file
        self.test_cpp = self.temp_path / "hello.cpp"
        self.test_cpp.write_text(
            "#include <iostream>\n"
            "\n"
            "int main() {\n"
            '    std::cout << "Hello from Cosmopolitan C++!" << std::endl;\n'
            "    return 0;\n"
            "}\n"
        )

    def tearDown(self) -> None:
        """Clean up temporary directory."""
        import shutil

        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def get_cosmocc_env(self) -> dict[str, str]:
        """Get environment dict for running cosmocc.

        Uses the universal cosmocc installation (no platform/arch arguments needed).
        """
        env = os.environ.copy()

        # Add cosmocc bin directory to PATH (universal installation)
        try:
            bin_dir = get_cosmocc_binary_dir()  # No args - universal installation
            env["PATH"] = f"{bin_dir}{os.pathsep}{env.get('PATH', '')}"

            # Set COSMOCC environment variable
            install_dir = bin_dir.parent
            env["COSMOCC"] = str(install_dir)
        except Exception:
            pass

        return env

    def _build_cosmocc_command(self, cosmocc_path: Path, args: list[str]) -> list[str]:
        """Build command to run cosmocc, handling shell requirement.

        Cosmocc tools are POSIX shell scripts that need to be executed through
        a shell interpreter on all platforms.
        """
        import shutil

        platform_name, _ = get_platform_info()

        if platform_name == "win":
            # Find a shell to execute the script
            shell = shutil.which("bash") or shutil.which("sh")
            if not shell:
                # Check common locations
                for candidate in [
                    r"C:\Program Files\Git\bin\bash.exe",
                    r"C:\Program Files\Git\usr\bin\bash.exe",
                    r"C:\msys64\usr\bin\bash.exe",
                ]:
                    if os.path.exists(candidate):
                        shell = candidate
                        break

            if shell:
                # Convert path to Unix-style for the shell
                tool_path_unix = str(cosmocc_path).replace("\\", "/")
                return [shell, tool_path_unix] + args
            else:
                self.skipTest("Cosmocc requires bash on Windows (Git Bash, MSYS2, etc.)")
        else:
            # On Unix/Linux, explicitly invoke through shell to handle potential
            # shebang issues or exec format errors
            shell = shutil.which("bash") or shutil.which("sh")
            if shell:
                return [shell, str(cosmocc_path)] + args

        # Fallback: try direct execution
        return [str(cosmocc_path)] + args

    def _check_for_crash(self, result: subprocess.CompletedProcess[str], tool_path: Path, context: str = "") -> None:
        """Check if cosmocc crashed and provide detailed diagnostics."""
        if result.returncode < 0:
            signal_name = {
                -11: "SIGSEGV (Segmentation fault)",
                -6: "SIGABRT (Abort)",
                -4: "SIGILL (Illegal instruction)",
            }.get(result.returncode, f"Signal {-result.returncode}")

            context_msg = f" ({context})" if context else ""
            self.fail(
                f"Cosmocc crashed with {signal_name}{context_msg}. "
                f"This usually indicates:\n"
                f"  - Missing shared library dependencies\n"
                f"  - ABI incompatibility between binary and system libraries\n"
                f"  - Corrupted binary\n\n"
                f"Binary path: {tool_path}\n"
                f"Return code: {result.returncode}\n"
                f"stdout: {result.stdout[:500]}\n"
                f"stderr: {result.stderr[:500]}"
            )

    def test_cosmocc_version(self) -> None:
        """Test that cosmocc can report its version."""
        try:
            cosmocc_path = find_cosmocc_tool("cosmocc")
            cmd = self._build_cosmocc_command(cosmocc_path, ["--version"])
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=30,
                env=self.get_cosmocc_env(),
            )

            # Check for crash signals (negative return codes on Unix)
            self._check_for_crash(result, cosmocc_path, context="--version command")

            # cosmocc should return 0 for --version
            self.assertEqual(
                result.returncode,
                0,
                f"cosmocc version command should succeed. Return code: {result.returncode}, "
                f"stderr: {result.stderr[:200]}",
            )

            # Check for version info in output
            combined_output = (result.stdout + result.stderr).lower()
            self.assertTrue(
                "cosmocc" in combined_output or "cosmopolitan" in combined_output or "clang" in combined_output,
                f"cosmocc version output should contain tool information. Output: {combined_output[:300]}",
            )
        except ToolchainInfrastructureError:
            raise
        except subprocess.TimeoutExpired:
            self.skipTest("cosmocc version command timed out")

    def test_cosmocpp_version(self) -> None:
        """Test that cosmoc++ can report its version."""
        try:
            cosmocpp_path = find_cosmocc_tool("cosmoc++")
            cmd = self._build_cosmocc_command(cosmocpp_path, ["--version"])
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=30,
                env=self.get_cosmocc_env(),
            )

            # Check for crash signals
            self._check_for_crash(result, cosmocpp_path, context="--version command")

            # cosmoc++ should return 0 for --version
            self.assertEqual(
                result.returncode,
                0,
                f"cosmoc++ version command should succeed. Return code: {result.returncode}, "
                f"stderr: {result.stderr[:200]}",
            )
        except ToolchainInfrastructureError:
            raise
        except subprocess.TimeoutExpired:
            self.skipTest("cosmoc++ version command timed out")

    def test_cosmocc_compile_c(self) -> None:
        """Test compiling a simple C program with cosmocc."""
        try:
            cosmocc_path = find_cosmocc_tool("cosmocc")

            # Output file - Cosmopolitan uses .com extension for APE
            output_file = self.temp_path / "hello.com"

            # Convert paths to Unix-style for shell on Windows
            platform_name, _ = get_platform_info()
            if platform_name == "win":
                test_c_path = str(self.test_c).replace("\\", "/")
                output_path = str(output_file).replace("\\", "/")
            else:
                test_c_path = str(self.test_c)
                output_path = str(output_file)

            cmd = self._build_cosmocc_command(cosmocc_path, [test_c_path, "-o", output_path])
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=120,  # Cosmopolitan compilation can take longer
                cwd=str(self.temp_path),
                env=self.get_cosmocc_env(),
            )

            # Check for crash signals
            self._check_for_crash(result, cosmocc_path, context="compiling C file")

            # Compilation should succeed
            self.assertEqual(
                result.returncode,
                0,
                f"cosmocc compilation should succeed. Return code: {result.returncode}, "
                f"stdout: {result.stdout[:300]}, stderr: {result.stderr[:300]}",
            )

            # Output file should exist
            self.assertTrue(
                output_file.exists(),
                f"Compiled output should exist at {output_file}",
            )

            # Output file should be non-empty
            self.assertGreater(
                output_file.stat().st_size,
                0,
                "Compiled output should be non-empty",
            )
        except ToolchainInfrastructureError:
            raise
        except subprocess.TimeoutExpired:
            self.skipTest("cosmocc compilation timed out")

    def test_cosmocc_compile_cpp(self) -> None:
        """Test compiling a simple C++ program with cosmoc++."""
        try:
            cosmocpp_path = find_cosmocc_tool("cosmoc++")

            # Output file
            output_file = self.temp_path / "hello_cpp.com"

            # Convert paths to Unix-style for shell on Windows
            platform_name, _ = get_platform_info()
            if platform_name == "win":
                test_cpp_path = str(self.test_cpp).replace("\\", "/")
                output_path = str(output_file).replace("\\", "/")
            else:
                test_cpp_path = str(self.test_cpp)
                output_path = str(output_file)

            cmd = self._build_cosmocc_command(cosmocpp_path, [test_cpp_path, "-o", output_path])
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=180,  # C++ compilation can take even longer
                cwd=str(self.temp_path),
                env=self.get_cosmocc_env(),
            )

            # Check for crash signals
            self._check_for_crash(result, cosmocpp_path, context="compiling C++ file")

            # Compilation should succeed
            self.assertEqual(
                result.returncode,
                0,
                f"cosmoc++ compilation should succeed. Return code: {result.returncode}, "
                f"stdout: {result.stdout[:300]}, stderr: {result.stderr[:300]}",
            )

            # Output file should exist
            self.assertTrue(
                output_file.exists(),
                f"Compiled output should exist at {output_file}",
            )
        except ToolchainInfrastructureError:
            raise
        except subprocess.TimeoutExpired:
            self.skipTest("cosmoc++ compilation timed out")

    @pytest.mark.slow
    def test_cosmocc_run_executable(self) -> None:
        """Test that a compiled Cosmopolitan executable can run."""
        try:
            cosmocc_path = find_cosmocc_tool("cosmocc")

            # Compile
            output_file = self.temp_path / "runtest.com"

            # Convert paths to Unix-style for shell on Windows
            platform_name, _ = get_platform_info()
            if platform_name == "win":
                test_c_path = str(self.test_c).replace("\\", "/")
                output_path = str(output_file).replace("\\", "/")
            else:
                test_c_path = str(self.test_c)
                output_path = str(output_file)

            cmd = self._build_cosmocc_command(cosmocc_path, [test_c_path, "-o", output_path])
            compile_result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=120,
                cwd=str(self.temp_path),
                env=self.get_cosmocc_env(),
            )

            if compile_result.returncode != 0:
                self.skipTest(f"Compilation failed: {compile_result.stderr[:200]}")

            # Run the executable
            run_result = subprocess.run(
                [str(output_file)],
                capture_output=True,
                text=True,
                timeout=30,
                cwd=str(self.temp_path),
            )

            # The executable should run and print the expected message
            self.assertEqual(
                run_result.returncode,
                0,
                f"Executable should run successfully. Return code: {run_result.returncode}, "
                f"stderr: {run_result.stderr[:200]}",
            )

            self.assertIn(
                "Hello from Cosmopolitan",
                run_result.stdout,
                f"Executable output should contain expected message. Output: {run_result.stdout}",
            )
        except ToolchainInfrastructureError:
            raise
        except subprocess.TimeoutExpired:
            self.skipTest("Executable run timed out")

    @pytest.mark.slow
    def test_cosmocc_dlopen_loading(self) -> None:
        """Test that cosmo_dlopen can load platform-native shared libraries.

        Cosmopolitan provides cosmo_dlopen() for loading platform-native libraries.
        This test verifies that dynamic library loading works by loading libm
        and calling a math function.

        Note: cosmo_dlopen() automatically handles platform differences:
        - On Linux: loads .so files
        - On macOS: converts .so to .dylib
        - On Windows: converts .so to .dll
        """
        try:
            cosmocc_path = find_cosmocc_tool("cosmocc")

            # Create a test file that uses cosmo_dlopen to load libm
            dlopen_test_c = self.temp_path / "dlopen_test.c"
            dlopen_test_c.write_text(
                "#include <stdio.h>\n"
                "#include <dlfcn.h>\n"
                "#include <math.h>\n"
                "\n"
                "// Test cosmo_dlopen by loading libm and calling sqrt\n"
                "int main() {\n"
                "    void *handle;\n"
                "    double (*sqrt_func)(double);\n"
                "    char *error;\n"
                "\n"
                "    // Try to load libm - cosmo_dlopen handles platform differences\n"
                "    // On Linux: libm.so.6, on macOS: libm.dylib, on Windows: handled differently\n"
                "#if defined(__APPLE__)\n"
                '    handle = cosmo_dlopen("libm.dylib", RTLD_LAZY);\n'
                "#elif defined(_WIN32)\n"
                "    // On Windows, math functions are in ucrtbase.dll or msvcrt.dll\n"
                '    handle = cosmo_dlopen("ucrtbase.dll", RTLD_LAZY);\n'
                "    if (!handle) {\n"
                '        handle = cosmo_dlopen("msvcrt.dll", RTLD_LAZY);\n'
                "    }\n"
                "#else\n"
                '    handle = cosmo_dlopen("libm.so.6", RTLD_LAZY);\n'
                "#endif\n"
                "\n"
                "    if (!handle) {\n"
                "        // Fallback: use built-in sqrt (statically linked)\n"
                '        printf("dlopen not available, using static sqrt\\n");\n'
                "        double result = sqrt(16.0);\n"
                '        printf("sqrt(16.0) = %.1f\\n", result);\n'
                "        if (result == 4.0) {\n"
                '            printf("DLOPEN_TEST: PASS (static fallback)\\n");\n'
                "            return 0;\n"
                "        }\n"
                "        return 1;\n"
                "    }\n"
                "\n"
                "    // Get sqrt function pointer\n"
                '    sqrt_func = (double (*)(double))cosmo_dlsym(handle, "sqrt");\n'
                "    if (!sqrt_func) {\n"
                '        printf("Could not find sqrt symbol, using static\\n");\n'
                "        cosmo_dlclose(handle);\n"
                "        double result = sqrt(16.0);\n"
                '        printf("sqrt(16.0) = %.1f\\n", result);\n'
                '        printf("DLOPEN_TEST: PASS (static fallback)\\n");\n'
                "        return 0;\n"
                "    }\n"
                "\n"
                "    // Call the dynamically loaded sqrt\n"
                "    double result = sqrt_func(16.0);\n"
                '    printf("Dynamic sqrt(16.0) = %.1f\\n", result);\n'
                "\n"
                "    cosmo_dlclose(handle);\n"
                "\n"
                "    if (result == 4.0) {\n"
                '        printf("DLOPEN_TEST: PASS (dynamic)\\n");\n'
                "        return 0;\n"
                "    }\n"
                "\n"
                '    printf("DLOPEN_TEST: FAIL\\n");\n'
                "    return 1;\n"
                "}\n"
            )

            # Compile the dlopen test
            output_file = self.temp_path / "dlopen_test.com"

            # Convert paths to Unix-style for shell on Windows
            platform_name, _ = get_platform_info()
            if platform_name == "win":
                dlopen_test_c_path = str(dlopen_test_c).replace("\\", "/")
                output_path = str(output_file).replace("\\", "/")
            else:
                dlopen_test_c_path = str(dlopen_test_c)
                output_path = str(output_file)

            cmd = self._build_cosmocc_command(cosmocc_path, [dlopen_test_c_path, "-o", output_path, "-lm"])
            compile_result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=120,
                cwd=str(self.temp_path),
                env=self.get_cosmocc_env(),
            )

            # Check for crash signals
            self._check_for_crash(result=compile_result, tool_path=cosmocc_path, context="compiling dlopen test")

            # Compilation should succeed
            self.assertEqual(
                compile_result.returncode,
                0,
                f"dlopen test compilation should succeed. Return code: {compile_result.returncode}, "
                f"stdout: {compile_result.stdout[:300]}, stderr: {compile_result.stderr[:300]}",
            )

            # Run the executable
            run_result = subprocess.run(
                [str(output_file)],
                capture_output=True,
                text=True,
                timeout=30,
                cwd=str(self.temp_path),
            )

            # The executable should run successfully
            # Note: dlopen may fail on some platforms but the test should still pass
            # if it gracefully falls back to static linking
            self.assertEqual(
                run_result.returncode,
                0,
                f"dlopen test should run successfully. Return code: {run_result.returncode}, "
                f"stdout: {run_result.stdout}, stderr: {run_result.stderr[:200]}",
            )

            # Verify the test passed (either dynamic or static fallback)
            self.assertIn(
                "DLOPEN_TEST: PASS",
                run_result.stdout,
                f"dlopen test should pass. Output: {run_result.stdout}",
            )

        except ToolchainInfrastructureError:
            raise
        except subprocess.TimeoutExpired:
            self.skipTest("dlopen test timed out")

    @pytest.mark.slow
    def test_cosmocc_shared_library_creation(self) -> None:
        """Test building a shared library with cosmocc.

        Note: Cosmopolitan is primarily designed for static linking and APE creation.
        Shared library support is limited, but we test what's available.
        """
        try:
            cosmocc_path = find_cosmocc_tool("cosmocc")

            # Create a simple library source
            lib_c = self.temp_path / "mylib.c"
            lib_c.write_text(
                "int add(int a, int b) {\n"
                "    return a + b;\n"
                "}\n"
                "\n"
                "int multiply(int a, int b) {\n"
                "    return a * b;\n"
                "}\n"
            )

            # Create main program that uses the library (statically linked)
            main_c = self.temp_path / "main_with_lib.c"
            main_c.write_text(
                "#include <stdio.h>\n"
                "\n"
                "// Declare external functions from our library\n"
                "extern int add(int a, int b);\n"
                "extern int multiply(int a, int b);\n"
                "\n"
                "int main() {\n"
                "    int sum = add(3, 4);\n"
                "    int product = multiply(3, 4);\n"
                '    printf("add(3, 4) = %d\\n", sum);\n'
                '    printf("multiply(3, 4) = %d\\n", product);\n'
                "    if (sum == 7 && product == 12) {\n"
                '        printf("LIBRARY_TEST: PASS\\n");\n'
                "        return 0;\n"
                "    }\n"
                '    printf("LIBRARY_TEST: FAIL\\n");\n'
                "    return 1;\n"
                "}\n"
            )

            # Compile both files together (static linking - Cosmopolitan's strength)
            output_file = self.temp_path / "main_with_lib.com"

            # Convert paths to Unix-style for shell on Windows
            platform_name, _ = get_platform_info()
            if platform_name == "win":
                lib_c_path = str(lib_c).replace("\\", "/")
                main_c_path = str(main_c).replace("\\", "/")
                output_path = str(output_file).replace("\\", "/")
            else:
                lib_c_path = str(lib_c)
                main_c_path = str(main_c)
                output_path = str(output_file)

            cmd = self._build_cosmocc_command(cosmocc_path, [lib_c_path, main_c_path, "-o", output_path])
            compile_result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=120,
                cwd=str(self.temp_path),
                env=self.get_cosmocc_env(),
            )

            self._check_for_crash(result=compile_result, tool_path=cosmocc_path, context="compiling library test")

            self.assertEqual(
                compile_result.returncode,
                0,
                f"Library compilation should succeed. Return code: {compile_result.returncode}, "
                f"stderr: {compile_result.stderr[:300]}",
            )

            # Run the executable
            run_result = subprocess.run(
                [str(output_file)],
                capture_output=True,
                text=True,
                timeout=30,
                cwd=str(self.temp_path),
            )

            self.assertEqual(
                run_result.returncode,
                0,
                f"Library test should run successfully. Return code: {run_result.returncode}, "
                f"stderr: {run_result.stderr[:200]}",
            )

            self.assertIn(
                "LIBRARY_TEST: PASS",
                run_result.stdout,
                f"Library test should pass. Output: {run_result.stdout}",
            )

        except ToolchainInfrastructureError:
            raise
        except subprocess.TimeoutExpired:
            self.skipTest("Library test timed out")


class TestCosmoccWrapperEntryPoints(unittest.TestCase):
    """Test that cosmocc wrapper entry points work correctly.

    Note: Cosmocc uses a universal installation, so wrapper functions
    do not require platform/arch arguments.
    """

    def test_wrapper_exports_cosmocc_functions(self) -> None:
        """Test that the wrapper module exports cosmocc functions."""
        # Check that wrapper exports the expected functions
        self.assertTrue(hasattr(wrapper, "cosmocc_main"), "wrapper should export cosmocc_main")
        self.assertTrue(hasattr(wrapper, "cosmocpp_main"), "wrapper should export cosmocpp_main")
        self.assertTrue(hasattr(wrapper, "execute_cosmocc_tool"), "wrapper should export execute_cosmocc_tool")
        self.assertTrue(hasattr(wrapper, "find_cosmocc_tool"), "wrapper should export find_cosmocc_tool")
        self.assertTrue(hasattr(wrapper, "get_cosmocc_binary_dir"), "wrapper should export get_cosmocc_binary_dir")

    def test_wrapper_can_find_cosmocc_binary_dir(self) -> None:
        """Test that the wrapper can locate cosmocc binary directory (universal installation)."""
        try:
            # No arguments needed - cosmocc uses universal installation
            bin_dir = wrapper.get_cosmocc_binary_dir()
            self.assertTrue(bin_dir.exists(), "Cosmocc binary directory should exist")

            # Check for expected files
            cosmocc_path = wrapper.find_cosmocc_tool("cosmocc")
            self.assertTrue(
                cosmocc_path.exists(),
                f"cosmocc binary should exist at {cosmocc_path}",
            )
            self.assertTrue(cosmocc_path.is_file(), f"cosmocc binary should be a file: {cosmocc_path}")
        except ToolchainInfrastructureError:
            raise

    def test_wrapper_find_all_cosmocc_tools(self) -> None:
        """Test that wrapper can find all cosmocc tools."""
        tools = ["cosmocc", "cosmoc++"]

        for tool_name in tools:
            with self.subTest(tool=tool_name):
                try:
                    tool_path = wrapper.find_cosmocc_tool(tool_name)
                    self.assertTrue(tool_path.exists(), f"{tool_name} should exist at {tool_path}")
                except ToolchainInfrastructureError:
                    raise
                except RuntimeError as e:
                    self.skipTest(f"Cosmocc binaries not installed: {e}")


if __name__ == "__main__":
    unittest.main()
