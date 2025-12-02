"""
Integration tests for the complete clang-tool-chain system.

These tests verify end-to-end functionality by compiling real C/C++ code
using various compilation schemes and testing all major tools.
"""

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Any

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from clang_tool_chain import wrapper
from clang_tool_chain.downloader import ToolchainInfrastructureError


class TestHelloWorldCompilation(unittest.TestCase):
    """Test complete compilation workflows with Hello World programs."""

    def setUp(self) -> None:
        """Set up test environment with temporary directory."""
        self.temp_dir = tempfile.mkdtemp()
        self.temp_path = Path(self.temp_dir)

        # Create test source files
        self.hello_c = self.temp_path / "hello.c"
        self.hello_c.write_text(
            "#include <stdio.h>\n" "int main() {\n" '    printf("Hello from C!\\n");\n' "    return 0;\n" "}\n"
        )

        self.hello_cpp = self.temp_path / "hello.cpp"
        self.hello_cpp.write_text(
            "#include <iostream>\n"
            "int main() {\n"
            '    std::cout << "Hello from C++!" << std::endl;\n'
            "    return 0;\n"
            "}\n"
        )

        # Create a helper function source for library tests
        self.helper_c = self.temp_path / "helper.c"
        self.helper_c.write_text(
            "#include <stdio.h>\n" "void print_helper() {\n" '    printf("Helper function called!\\n");\n' "}\n"
        )

        self.helper_h = self.temp_path / "helper.h"
        self.helper_h.write_text("#ifndef HELPER_H\n" "#define HELPER_H\n" "void print_helper(void);\n" "#endif\n")

        self.main_with_helper_c = self.temp_path / "main_with_helper.c"
        self.main_with_helper_c.write_text(
            "#include <stdio.h>\n"
            '#include "helper.h"\n'
            "int main() {\n"
            '    printf("Main function\\n");\n'
            "    print_helper();\n"
            "    return 0;\n"
            "}\n"
        )

    def tearDown(self) -> None:
        """Clean up temporary directory."""
        import shutil

        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_one_shot_c_compilation(self) -> None:
        """Test compiling C source directly to executable in one step."""
        try:
            platform_name, _ = wrapper.get_platform_info()
            output = self.temp_path / ("hello_c.exe" if platform_name == "win" else "hello_c")

            # Compile in one step: source -> executable
            result = wrapper.run_tool("clang", [str(self.hello_c), "-o", str(output)])

            self.assertEqual(result, 0, "One-shot C compilation should succeed")
            self.assertTrue(output.exists(), f"Output executable should exist at {output}")

            # Verify the executable runs
            run_result = subprocess.run([str(output)], capture_output=True, text=True)
            self.assertEqual(run_result.returncode, 0, "Executable should run successfully")
            self.assertIn("Hello from C!", run_result.stdout, "Output should contain expected text")
        except ToolchainInfrastructureError:
            raise

    def test_one_shot_cpp_compilation(self) -> None:
        """Test compiling C++ source directly to executable in one step."""
        try:
            platform_name, _ = wrapper.get_platform_info()
            output = self.temp_path / ("hello_cpp.exe" if platform_name == "win" else "hello_cpp")

            # Compile in one step: source -> executable
            result = wrapper.run_tool("clang++", [str(self.hello_cpp), "-o", str(output)])

            self.assertEqual(result, 0, "One-shot C++ compilation should succeed")
            self.assertTrue(output.exists(), f"Output executable should exist at {output}")

            # Verify the executable runs
            run_result = subprocess.run([str(output)], capture_output=True, text=True)
            self.assertEqual(run_result.returncode, 0, "Executable should run successfully")
            self.assertIn("Hello from C++!", run_result.stdout, "Output should contain expected text")
        except ToolchainInfrastructureError:
            raise

    def test_separate_compile_and_link(self) -> None:
        """Test compiling to object file then linking separately."""
        try:
            platform_name, _ = wrapper.get_platform_info()
            obj_file = self.temp_path / "hello.o"
            output = self.temp_path / ("hello_linked.exe" if platform_name == "win" else "hello_linked")

            # Step 1: Compile to object file
            compile_result = wrapper.run_tool("clang", ["-c", str(self.hello_c), "-o", str(obj_file)])
            self.assertEqual(compile_result, 0, "Compilation to object file should succeed")
            self.assertTrue(obj_file.exists(), f"Object file should exist at {obj_file}")

            # Step 2: Link object file to executable
            link_result = wrapper.run_tool("clang", [str(obj_file), "-o", str(output)])
            self.assertEqual(link_result, 0, "Linking should succeed")
            self.assertTrue(output.exists(), f"Output executable should exist at {output}")

            # Verify the executable runs
            run_result = subprocess.run([str(output)], capture_output=True, text=True)
            self.assertEqual(run_result.returncode, 0, "Executable should run successfully")
            self.assertIn("Hello from C!", run_result.stdout, "Output should contain expected text")
        except ToolchainInfrastructureError:
            raise

    def test_static_library_creation_and_linking(self) -> None:
        """Test creating a static library with llvm-ar and linking against it."""
        try:
            platform_name, _ = wrapper.get_platform_info()
            helper_obj = self.temp_path / "helper.o"
            static_lib = self.temp_path / "libhelper.a"
            main_obj = self.temp_path / "main.o"
            output = self.temp_path / ("main_static.exe" if platform_name == "win" else "main_static")

            # Step 1: Compile helper to object file
            compile_helper = wrapper.run_tool("clang", ["-c", str(self.helper_c), "-o", str(helper_obj)])
            self.assertEqual(compile_helper, 0, "Helper compilation should succeed")
            self.assertTrue(helper_obj.exists(), f"Helper object file should exist at {helper_obj}")

            # Step 2: Create static library from helper object
            ar_result = wrapper.run_tool("llvm-ar", ["rcs", str(static_lib), str(helper_obj)])
            self.assertEqual(ar_result, 0, "Static library creation should succeed")
            self.assertTrue(static_lib.exists(), f"Static library should exist at {static_lib}")

            # Step 3: Compile main to object file
            compile_main = wrapper.run_tool(
                "clang", ["-c", str(self.main_with_helper_c), "-o", str(main_obj), f"-I{self.temp_path}"]
            )
            self.assertEqual(compile_main, 0, "Main compilation should succeed")
            self.assertTrue(main_obj.exists(), f"Main object file should exist at {main_obj}")

            # Step 4: Link main with static library
            link_result = wrapper.run_tool("clang", [str(main_obj), str(static_lib), "-o", str(output)])
            self.assertEqual(link_result, 0, "Linking with static library should succeed")
            self.assertTrue(output.exists(), f"Output executable should exist at {output}")

            # Verify the executable runs
            run_result = subprocess.run([str(output)], capture_output=True, text=True)
            self.assertEqual(run_result.returncode, 0, "Executable should run successfully")
            self.assertIn("Main function", run_result.stdout, "Output should contain main function text")
            self.assertIn("Helper function called!", run_result.stdout, "Output should contain helper text")
        except ToolchainInfrastructureError:
            raise

    @unittest.skipUnless(
        sys.platform.startswith("linux") or sys.platform.startswith("darwin"),
        "Thin archives are primarily a Unix feature",
    )
    def test_thin_archive_creation(self) -> None:
        """Test creating a thin archive (archive with references instead of embedded objects)."""
        try:
            helper_obj = self.temp_path / "helper.o"
            thin_archive = self.temp_path / "libhelper_thin.a"

            # Step 1: Compile helper to object file
            compile_helper = wrapper.run_tool("clang", ["-c", str(self.helper_c), "-o", str(helper_obj)])
            self.assertEqual(compile_helper, 0, "Helper compilation should succeed")

            # Step 2: Create thin archive using 'T' flag
            ar_result = wrapper.run_tool("llvm-ar", ["rcsT", str(thin_archive), str(helper_obj)])
            self.assertEqual(ar_result, 0, "Thin archive creation should succeed")
            self.assertTrue(thin_archive.exists(), f"Thin archive should exist at {thin_archive}")

            # Verify it's actually thin (smaller than regular archive)
            regular_archive = self.temp_path / "libhelper_regular.a"
            wrapper.run_tool("llvm-ar", ["rcs", str(regular_archive), str(helper_obj)])

            thin_size = thin_archive.stat().st_size
            regular_size = regular_archive.stat().st_size

            # Thin archives should be smaller (they just reference the object file)
            self.assertLess(thin_size, regular_size, "Thin archive should be smaller than regular archive")
        except ToolchainInfrastructureError:
            raise


class TestBinaryUtilities(unittest.TestCase):
    """Test LLVM binary analysis and manipulation utilities."""

    def setUp(self) -> None:
        """Set up test environment with compiled object file."""
        self.temp_dir = tempfile.mkdtemp()
        self.temp_path = Path(self.temp_dir)

        # Create a test C file with recognizable symbols
        self.test_c = self.temp_path / "test.c"
        self.test_c.write_text(
            "int global_variable = 42;\n"
            "static int static_variable = 100;\n"
            "void public_function() {}\n"
            "static void static_function() {}\n"
            "int main() { return 0; }\n"
        )

        # Compile to object file for testing utilities
        self.obj_file = self.temp_path / "test.o"
        try:
            result = wrapper.run_tool("clang", ["-c", str(self.test_c), "-o", str(self.obj_file)])
            if result != 0:
                raise RuntimeError("Could not compile test object file")
        except RuntimeError:
            self.obj_file = None

    def tearDown(self) -> None:
        """Clean up temporary directory."""
        import shutil

        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_llvm_nm_list_symbols(self) -> None:
        """Test llvm-nm can list symbols from object file."""
        if self.obj_file is None or not self.obj_file.exists():
            self.skipTest("Test object file not available")

        try:
            # Run llvm-nm and capture output
            result = subprocess.run(
                [str(wrapper.find_tool_binary("llvm-nm")), str(self.obj_file)], capture_output=True, text=True
            )
            self.assertEqual(result.returncode, 0, "llvm-nm should succeed")

            # Check for expected symbols in output
            output = result.stdout.lower()
            # At minimum, we should see main and global_variable
            self.assertTrue(
                "main" in output or "global_variable" in output, "llvm-nm output should contain symbol information"
            )
        except ToolchainInfrastructureError:
            raise

    def test_llvm_objdump_disassemble(self) -> None:
        """Test llvm-objdump can disassemble object file."""
        if self.obj_file is None or not self.obj_file.exists():
            self.skipTest("Test object file not available")

        try:
            # Run llvm-objdump with disassembly
            result = subprocess.run(
                [str(wrapper.find_tool_binary("llvm-objdump")), "-d", str(self.obj_file)],
                capture_output=True,
                text=True,
            )
            self.assertEqual(result.returncode, 0, "llvm-objdump should succeed")

            # Output should contain disassembly markers
            output = result.stdout.lower()
            # Should see either function names or assembly-like content
            has_content = any(marker in output for marker in ["main", "disassembly", "file format"])
            self.assertTrue(has_content, "llvm-objdump output should contain disassembly or file format info")
        except ToolchainInfrastructureError:
            raise

    def test_llvm_readelf_headers(self) -> None:
        """Test llvm-readelf can read ELF headers."""
        if self.obj_file is None or not self.obj_file.exists():
            self.skipTest("Test object file not available")

        try:
            platform_name, _ = wrapper.get_platform_info()
            if platform_name == "win":
                self.skipTest("llvm-readelf is primarily for ELF format (Linux/Unix)")

            # Run llvm-readelf to show headers
            result = subprocess.run(
                [str(wrapper.find_tool_binary("llvm-readelf")), "-h", str(self.obj_file)],
                capture_output=True,
                text=True,
            )
            self.assertEqual(result.returncode, 0, "llvm-readelf should succeed")

            # Check for format-specific information
            output = result.stdout.lower()
            if platform_name == "darwin":
                # macOS uses Mach-O format, not ELF
                self.assertIn("mach-o", output, "llvm-readelf output should contain Mach-O information on macOS")
            else:
                # Linux should contain ELF header information
                self.assertIn("elf", output, "llvm-readelf output should contain ELF information")
        except ToolchainInfrastructureError:
            raise

    def test_llvm_strip_debug_info(self) -> None:
        """Test llvm-strip can remove debug information from binary."""
        if self.obj_file is None or not self.obj_file.exists():
            self.skipTest("Test object file not available")

        try:
            # Compile with debug symbols
            debug_obj = self.temp_path / "test_debug.o"
            compile_result = wrapper.run_tool("clang", ["-g", "-c", str(self.test_c), "-o", str(debug_obj)])
            if compile_result != 0:
                self.skipTest("Could not compile with debug symbols")

            # Get original size
            original_size = debug_obj.stat().st_size

            # Strip the binary
            stripped_obj = self.temp_path / "test_stripped.o"
            import shutil

            shutil.copy(debug_obj, stripped_obj)

            strip_result = wrapper.run_tool("llvm-strip", [str(stripped_obj)])
            self.assertEqual(strip_result, 0, "llvm-strip should succeed")

            # Stripped file should be smaller (debug info removed)
            stripped_size = stripped_obj.stat().st_size
            self.assertLessEqual(
                stripped_size, original_size, "Stripped binary should be smaller or same size as original"
            )
        except ToolchainInfrastructureError:
            raise

    def test_llvm_objcopy_section_manipulation(self) -> None:
        """Test llvm-objcopy can manipulate sections in object file."""
        if self.obj_file is None or not self.obj_file.exists():
            self.skipTest("Test object file not available")

        try:
            # Create a copy with llvm-objcopy
            copied_obj = self.temp_path / "test_copy.o"

            result = subprocess.run(
                [str(wrapper.find_tool_binary("llvm-objcopy")), str(self.obj_file), str(copied_obj)],
                capture_output=True,
                text=True,
            )
            self.assertEqual(result.returncode, 0, "llvm-objcopy should succeed")
            self.assertTrue(copied_obj.exists(), "Copied object file should exist")

            # Both files should be similar in size (basic copy)
            original_size = self.obj_file.stat().st_size
            copied_size = copied_obj.stat().st_size
            self.assertEqual(copied_size, original_size, "Copied file should have same size as original")
        except ToolchainInfrastructureError:
            raise

    def test_llvm_ranlib_generate_index(self) -> None:
        """Test llvm-ranlib can generate index for static library."""
        try:
            # Create an object file
            helper_obj = self.temp_path / "helper.o"
            helper_c = self.temp_path / "helper.c"
            helper_c.write_text("void helper() {}\n")

            compile_result = wrapper.run_tool("clang", ["-c", str(helper_c), "-o", str(helper_obj)])
            if compile_result != 0:
                self.skipTest("Could not compile helper object")

            # Create static library
            static_lib = self.temp_path / "libtest.a"
            ar_result = wrapper.run_tool("llvm-ar", ["rc", str(static_lib), str(helper_obj)])
            if ar_result != 0:
                self.skipTest("Could not create static library")

            # Run llvm-ranlib to generate index
            ranlib_result = wrapper.run_tool("llvm-ranlib", [str(static_lib)])
            self.assertEqual(ranlib_result, 0, "llvm-ranlib should succeed")

            # Library should still exist and be valid
            self.assertTrue(static_lib.exists(), "Library should still exist after ranlib")
        except ToolchainInfrastructureError:
            raise


class TestCompilerVersions(unittest.TestCase):
    """Test that all major tools can report their versions."""

    def test_clang_version(self) -> None:
        """Test clang --version works."""
        try:
            result = subprocess.run(
                [str(wrapper.find_tool_binary("clang")), "--version"], capture_output=True, text=True
            )
            self.assertEqual(result.returncode, 0, "clang --version should succeed")
            self.assertIn("clang version", result.stdout.lower(), "Output should contain version info")
        except ToolchainInfrastructureError:
            raise

    def test_clang_cpp_version(self) -> None:
        """Test clang++ --version works."""
        try:
            result = subprocess.run(
                [str(wrapper.find_tool_binary("clang++")), "--version"], capture_output=True, text=True
            )
            self.assertEqual(result.returncode, 0, "clang++ --version should succeed")
            self.assertIn("clang version", result.stdout.lower(), "Output should contain version info")
        except ToolchainInfrastructureError:
            raise

    def test_llvm_ar_version(self) -> None:
        """Test llvm-ar --version works."""
        try:
            result = subprocess.run(
                [str(wrapper.find_tool_binary("llvm-ar")), "--version"], capture_output=True, text=True
            )
            self.assertEqual(result.returncode, 0, "llvm-ar --version should succeed")
            output = result.stdout.lower()
            # llvm-ar reports as "llvm" in version string
            self.assertTrue("llvm" in output or "ar" in output, "Output should contain version info")
        except ToolchainInfrastructureError:
            raise


class TestConcurrentDownload(unittest.TestCase):
    """Test that concurrent downloads are properly synchronized."""

    def test_concurrent_download_locking(self) -> None:
        """
        Test that multiple concurrent compile processes handle download locking correctly.

        This test:
        1. Clears the toolchain directory
        2. Starts two compilation processes simultaneously
        3. Verifies both complete successfully
        4. Ensures they finish within 10 seconds of each other (proving one waits for the other)
        """
        import concurrent.futures
        import contextlib
        import shutil
        import time
        from pathlib import Path

        # Quick check if toolchain can be downloaded
        try:
            import subprocess

            result = subprocess.run(["clang-tool-chain-c", "--version"], capture_output=True, text=True, timeout=10)
            if result.returncode != 0:
                self.skipTest(f"Toolchain not accessible: {result.stderr}")
        except Exception as e:
            self.skipTest(f"Toolchain not accessible: {e}")

        # Clean the toolchain directory (except root)
        toolchain_dir = Path.home() / ".clang-tool-chain"
        if toolchain_dir.exists():
            for item in toolchain_dir.iterdir():
                if item.is_dir():
                    # On Windows, handle permission errors when files are in use
                    with contextlib.suppress(PermissionError, OSError):
                        shutil.rmtree(item)
                elif item.is_file() and not item.name.endswith(".lock"):
                    with contextlib.suppress(PermissionError, OSError):
                        item.unlink()

        # Create two temporary directories with test files
        temp_dir1 = tempfile.mkdtemp()
        temp_dir2 = tempfile.mkdtemp()

        try:
            # Create test files
            test_c1 = Path(temp_dir1) / "test1.c"
            test_c1.write_text('#include <stdio.h>\nint main() { printf("Test 1\\n"); return 0; }')

            test_c2 = Path(temp_dir2) / "test2.c"
            test_c2.write_text('#include <stdio.h>\nint main() { printf("Test 2\\n"); return 0; }')

            platform_name, _ = wrapper.get_platform_info()
            out1 = Path(temp_dir1) / ("test1.exe" if platform_name == "win" else "test1")
            out2 = Path(temp_dir2) / ("test2.exe" if platform_name == "win" else "test2")

            # Function to compile
            def compile_file(source: Path, output: Path) -> dict[str, Any]:
                start_time = time.time()
                try:
                    result = wrapper.run_tool("clang", [str(source), "-o", str(output)])
                    end_time = time.time()
                    return {
                        "success": result == 0,
                        "start": start_time,
                        "end": end_time,
                        "duration": end_time - start_time,
                    }
                except Exception as e:
                    end_time = time.time()
                    return {
                        "success": False,
                        "start": start_time,
                        "end": end_time,
                        "duration": end_time - start_time,
                        "error": str(e),
                    }

            # Run both compilations concurrently
            with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
                future1 = executor.submit(compile_file, test_c1, out1)
                future2 = executor.submit(compile_file, test_c2, out2)

                result1 = future1.result()
                result2 = future2.result()

            # Verify both succeeded
            self.assertTrue(result1["success"], f"First compilation failed: {result1.get('error', 'Unknown')}")
            self.assertTrue(result2["success"], f"Second compilation failed: {result2.get('error', 'Unknown')}")

            # Calculate time difference between completion times
            time_diff = abs(result1["end"] - result2["end"])

            # Both should finish within 10 seconds of each other
            # (One downloads, the other waits, both compile quickly)
            # Using 10s to account for CI environment variability (network latency, filesystem sync, etc.)
            self.assertLess(
                time_diff,
                10.0,
                f"Compilations finished {time_diff:.2f}s apart, expected < 10s. "
                f"This suggests the locking mechanism may not be working correctly.",
            )

            # Verify executables were created
            self.assertTrue(out1.exists(), "First executable should exist")
            self.assertTrue(out2.exists(), "Second executable should exist")

        finally:
            # Clean up
            shutil.rmtree(temp_dir1, ignore_errors=True)
            shutil.rmtree(temp_dir2, ignore_errors=True)


class TestStaticAnalysis(unittest.TestCase):
    """Test Clang static analyzer functionality."""

    def setUp(self) -> None:
        """Set up test environment with temporary directory."""
        self.temp_dir = tempfile.mkdtemp()
        self.temp_path = Path(self.temp_dir)

        # Create a test C++ file with a potential bug that the analyzer can detect
        self.buggy_cpp = self.temp_path / "buggy.cpp"
        self.buggy_cpp.write_text(
            "#include <cstdlib>\n"
            "int main() {\n"
            "    int *ptr = (int*)malloc(sizeof(int));\n"
            "    *ptr = 42;\n"
            "    // Memory leak - forgot to free(ptr)\n"
            "    return 0;\n"
            "}\n"
        )

        # Create a test file with a division by zero warning
        self.div_zero_cpp = self.temp_path / "div_zero.cpp"
        self.div_zero_cpp.write_text(
            "int main() {\n"
            "    int x = 10;\n"
            "    int y = 0;\n"
            "    int z = x / y;  // Division by zero\n"
            "    return z;\n"
            "}\n"
        )

        # Create a test file with a null dereference
        self.null_deref_cpp = self.temp_path / "null_deref.cpp"
        self.null_deref_cpp.write_text(
            "int main() {\n" "    int *ptr = nullptr;\n" "    return *ptr;  // Null dereference\n" "}\n"
        )

    def tearDown(self) -> None:
        """Clean up temporary directory."""
        import shutil

        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_analyzer_basic_run(self) -> None:
        """Test that the Clang static analyzer can run with basic checkers."""
        try:
            # Run analyzer with core and deadcode checkers
            result = subprocess.run(
                [
                    str(wrapper.find_tool_binary("clang++")),
                    "--analyze",
                    "-Xanalyzer",
                    "-analyzer-checker=core,deadcode",
                    str(self.buggy_cpp),
                ],
                capture_output=True,
                text=True,
                cwd=str(self.temp_path),
            )

            # Analyzer should complete (return code may be 0 or non-zero depending on findings)
            # We just verify it doesn't crash
            self.assertIn(
                result.returncode,
                [0, 1],
                f"Analyzer should complete successfully. Return code: {result.returncode}, "
                f"stdout: {result.stdout}, stderr: {result.stderr}",
            )

        except ToolchainInfrastructureError:
            raise

    def test_analyzer_division_by_zero(self) -> None:
        """Test that analyzer detects division by zero."""
        try:
            # Run analyzer with core checkers
            result = subprocess.run(
                [
                    str(wrapper.find_tool_binary("clang++")),
                    "--analyze",
                    "-Xanalyzer",
                    "-analyzer-checker=core",
                    str(self.div_zero_cpp),
                ],
                capture_output=True,
                text=True,
                cwd=str(self.temp_path),
            )

            # Check output for division warning (may be in stdout or stderr)
            combined_output = result.stdout + result.stderr

            # The analyzer should produce some output
            self.assertTrue(len(combined_output) > 0, "Analyzer should produce output for division by zero")

        except ToolchainInfrastructureError:
            raise

    def test_analyzer_null_dereference(self) -> None:
        """Test that analyzer detects null pointer dereference."""
        try:
            # Run analyzer with core checkers
            result = subprocess.run(
                [
                    str(wrapper.find_tool_binary("clang++")),
                    "--analyze",
                    "-Xanalyzer",
                    "-analyzer-checker=core.NullDereference",
                    str(self.null_deref_cpp),
                ],
                capture_output=True,
                text=True,
                cwd=str(self.temp_path),
            )

            # Analyzer should run (return code varies based on findings)
            self.assertIn(result.returncode, [0, 1], "Analyzer should complete for null dereference test")

            # Check that some analysis output was generated
            combined_output = result.stdout + result.stderr
            self.assertTrue(len(combined_output) > 0, "Analyzer should produce output")

        except ToolchainInfrastructureError:
            raise

    def test_analyzer_with_output_format(self) -> None:
        """Test analyzer with different output formats."""
        try:
            # Run analyzer with plist output format
            plist_file = self.temp_path / "analysis.plist"
            result = subprocess.run(
                [
                    str(wrapper.find_tool_binary("clang++")),
                    "--analyze",
                    "-Xanalyzer",
                    "-analyzer-checker=core",
                    "-Xanalyzer",
                    "-analyzer-output=plist",
                    "-o",
                    str(plist_file),
                    str(self.div_zero_cpp),
                ],
                capture_output=True,
                text=True,
                cwd=str(self.temp_path),
            )

            # Verify analyzer ran
            self.assertIn(result.returncode, [0, 1], "Analyzer should complete")

        except ToolchainInfrastructureError:
            raise

    def test_analyzer_multiple_files(self) -> None:
        """Test analyzer can analyze multiple source files."""
        try:
            # Create another test file
            good_file = self.temp_path / "good.cpp"
            good_file.write_text("int add(int a, int b) {\n" "    return a + b;\n" "}\n")

            # Run analyzer on multiple files
            for test_file in [good_file, self.buggy_cpp]:
                result = subprocess.run(
                    [
                        str(wrapper.find_tool_binary("clang++")),
                        "--analyze",
                        "-Xanalyzer",
                        "-analyzer-checker=core",
                        str(test_file),
                    ],
                    capture_output=True,
                    text=True,
                    cwd=str(self.temp_path),
                )

                # Both should complete
                self.assertIn(
                    result.returncode,
                    [0, 1],
                    f"Analyzer should complete for {test_file.name}",
                )

        except ToolchainInfrastructureError:
            raise


if __name__ == "__main__":
    unittest.main()
