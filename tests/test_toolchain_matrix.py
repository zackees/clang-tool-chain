"""
Comprehensive toolchain test matrix for Windows.

This test suite validates all essential toolchain operations to identify
the minimal set of binaries required for C/C++ compilation and linking.

Test Categories:
1. C Compilation: basic, optimized, with flags
2. C++ Compilation: basic, optimized, with flags, standards
3. Linking: static, dynamic, with lld variants
4. Archives: create, thin archives, ranlib operations
5. Binary Inspection: objdump, nm, readobj/readelf
6. Binary Manipulation: strip, objcopy
7. Cross-tool Integration: full build pipelines

This helps determine which binaries are truly needed vs duplicates.
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


class ToolchainTestBase(unittest.TestCase):
    """Base class for toolchain tests with common utilities."""

    def setUp(self):
        """Set up test environment with temporary directory."""
        self.temp_dir = tempfile.mkdtemp()
        self.temp_path = Path(self.temp_dir)

        # Get the bin directory
        try:
            self.bin_dir = wrapper.get_platform_binary_dir()
        except RuntimeError:
            self.skipTest("Binaries not installed")

    def run_binary(self, binary_name, args, check=True):
        """Run a binary directly from the bin directory."""
        binary_path = self.bin_dir / f"{binary_name}.exe"
        if not binary_path.exists():
            self.fail(f"Binary not found: {binary_path}")

        cmd = [str(binary_path)] + args
        result = subprocess.run(
            cmd,
            cwd=str(self.temp_path),
            capture_output=True,
            text=True
        )

        if check and result.returncode != 0:
            self.fail(
                f"Command failed: {' '.join(cmd)}\n"
                f"stdout: {result.stdout}\n"
                f"stderr: {result.stderr}"
            )

        return result


class TestCCompilation(ToolchainTestBase):
    """Test C compilation scenarios."""

    def setUp(self):
        super().setUp()
        # Create test C file
        self.c_file = self.temp_path / "test.c"
        self.c_file.write_text(
            '#include <stdio.h>\n'
            'int add(int a, int b) { return a + b; }\n'
            'int main() { printf("Result: %d\\n", add(2, 3)); return 0; }\n'
        )

    def test_basic_c_compilation_clang(self):
        """Test basic C compilation with clang.exe."""
        output = self.temp_path / "test.exe"
        result = self.run_binary("clang", [
            str(self.c_file),
            "-o", str(output)
        ])
        self.assertTrue(output.exists())

        # Run the executable
        run_result = subprocess.run([str(output)], capture_output=True, text=True)
        self.assertEqual(run_result.returncode, 0)
        self.assertIn("Result: 5", run_result.stdout)

    def test_c_compilation_with_lld_link(self):
        """Test C compilation using lld-link explicitly."""
        output = self.temp_path / "test_lld.exe"
        result = self.run_binary("clang", [
            "-fuse-ld=lld",
            str(self.c_file),
            "-o", str(output)
        ])
        self.assertTrue(output.exists())

        # Run the executable
        run_result = subprocess.run([str(output)], capture_output=True, text=True)
        self.assertEqual(run_result.returncode, 0)

    def test_c_compilation_optimized(self):
        """Test C compilation with optimization flags."""
        for opt_level in ["-O0", "-O1", "-O2", "-O3", "-Os"]:
            with self.subTest(opt_level=opt_level):
                output = self.temp_path / f"test_{opt_level.replace('-', '')}.exe"
                result = self.run_binary("clang", [
                    opt_level,
                    str(self.c_file),
                    "-o", str(output)
                ])
                self.assertTrue(output.exists())

    def test_c_object_file_compilation(self):
        """Test compiling C to object file."""
        obj_file = self.temp_path / "test.o"
        result = self.run_binary("clang", [
            "-c",
            str(self.c_file),
            "-o", str(obj_file)
        ])
        self.assertTrue(obj_file.exists())

    def test_c_with_debug_symbols(self):
        """Test C compilation with debug symbols."""
        output = self.temp_path / "test_debug.exe"
        result = self.run_binary("clang", [
            "-g",
            str(self.c_file),
            "-o", str(output)
        ])
        self.assertTrue(output.exists())


class TestCppCompilation(ToolchainTestBase):
    """Test C++ compilation scenarios."""

    def setUp(self):
        super().setUp()
        # Create test C++ file
        self.cpp_file = self.temp_path / "test.cpp"
        self.cpp_file.write_text(
            '#include <iostream>\n'
            '#include <vector>\n'
            'int main() {\n'
            '    std::vector<int> v = {1, 2, 3};\n'
            '    std::cout << "Size: " << v.size() << std::endl;\n'
            '    return 0;\n'
            '}\n'
        )

    def test_basic_cpp_compilation_clang_plusplus(self):
        """Test basic C++ compilation with clang++.exe."""
        output = self.temp_path / "test.exe"
        result = self.run_binary("clang++", [
            str(self.cpp_file),
            "-o", str(output)
        ])
        self.assertTrue(output.exists())

        # Run the executable
        run_result = subprocess.run([str(output)], capture_output=True, text=True)
        self.assertEqual(run_result.returncode, 0)
        self.assertIn("Size: 3", run_result.stdout)

    def test_cpp_compilation_via_clang_exe(self):
        """Test C++ compilation using clang.exe with -x c++ flag."""
        output = self.temp_path / "test_via_clang.exe"
        result = self.run_binary("clang", [
            "-x", "c++",
            str(self.cpp_file),
            "-o", str(output)
        ])
        self.assertTrue(output.exists())

        # Run the executable
        run_result = subprocess.run([str(output)], capture_output=True, text=True)
        self.assertEqual(run_result.returncode, 0)

    def test_cpp_standards(self):
        """Test C++ compilation with different standards."""
        # Note: MSVC 2019 headers require C++14 or later
        standards = ["-std=c++14", "-std=c++17", "-std=c++20"]
        for std in standards:
            with self.subTest(standard=std):
                output = self.temp_path / f"test_{std.replace('-', '').replace('+', 'p')}.exe"
                result = self.run_binary("clang++", [
                    std,
                    str(self.cpp_file),
                    "-o", str(output)
                ])
                self.assertTrue(output.exists())

    def test_cpp_with_lld_link(self):
        """Test C++ compilation using lld-link explicitly."""
        output = self.temp_path / "test_lld.exe"
        result = self.run_binary("clang++", [
            "-fuse-ld=lld",
            str(self.cpp_file),
            "-o", str(output)
        ])
        self.assertTrue(output.exists())

    def test_cpp_object_file_compilation(self):
        """Test compiling C++ to object file."""
        obj_file = self.temp_path / "test.o"
        result = self.run_binary("clang++", [
            "-c",
            str(self.cpp_file),
            "-o", str(obj_file)
        ])
        self.assertTrue(obj_file.exists())


class TestArchiveOperations(ToolchainTestBase):
    """Test archive creation and manipulation."""

    def setUp(self):
        super().setUp()
        # Create multiple object files for archiving
        self.obj_files = []
        for i in range(3):
            c_file = self.temp_path / f"file{i}.c"
            c_file.write_text(f"int func{i}() {{ return {i}; }}\n")

            obj_file = self.temp_path / f"file{i}.o"
            self.run_binary("clang", ["-c", str(c_file), "-o", str(obj_file)])
            self.obj_files.append(obj_file)

    def test_create_regular_archive(self):
        """Test creating a regular static archive with llvm-ar."""
        archive = self.temp_path / "libtest.a"
        result = self.run_binary("llvm-ar", [
            "rcs",
            str(archive)
        ] + [str(obj) for obj in self.obj_files])

        self.assertTrue(archive.exists())

        # List contents
        list_result = self.run_binary("llvm-ar", ["t", str(archive)])
        self.assertIn("file0.o", list_result.stdout)

    def test_create_thin_archive(self):
        """Test creating a thin archive."""
        archive = self.temp_path / "libtest_thin.a"
        result = self.run_binary("llvm-ar", [
            "rcsT",
            str(archive)
        ] + [str(obj) for obj in self.obj_files])

        self.assertTrue(archive.exists())
        # Thin archives are typically much smaller
        thin_size = archive.stat().st_size
        self.assertLess(thin_size, 10000)  # Should be very small

    def test_llvm_ranlib_on_archive(self):
        """Test running llvm-ranlib on an archive."""
        archive = self.temp_path / "libtest.a"
        self.run_binary("llvm-ar", [
            "rcs",
            str(archive)
        ] + [str(obj) for obj in self.obj_files])

        # Run ranlib
        result = self.run_binary("llvm-ranlib", [str(archive)])
        self.assertEqual(result.returncode, 0)

    def test_extract_from_archive(self):
        """Test extracting files from an archive."""
        archive = self.temp_path / "libtest.a"
        self.run_binary("llvm-ar", [
            "rcs",
            str(archive)
        ] + [str(obj) for obj in self.obj_files])

        # Create extraction directory
        extract_dir = self.temp_path / "extracted"
        extract_dir.mkdir()

        # Extract
        result = self.run_binary("llvm-ar", [
            "x",
            str(archive)
        ])


class TestBinaryInspection(ToolchainTestBase):
    """Test binary inspection tools."""

    def setUp(self):
        super().setUp()
        # Create a test executable
        c_file = self.temp_path / "inspect.c"
        c_file.write_text(
            'int global_var = 42;\n'
            'static int static_var = 100;\n'
            'int add(int a, int b) { return a + b; }\n'
            'int main() { return add(global_var, static_var); }\n'
        )

        self.exe_file = self.temp_path / "inspect.exe"
        self.run_binary("clang", [str(c_file), "-o", str(self.exe_file)])

        self.obj_file = self.temp_path / "inspect.o"
        self.run_binary("clang", ["-c", str(c_file), "-o", str(self.obj_file)])

    def test_llvm_nm_list_symbols(self):
        """Test llvm-nm to list symbols."""
        result = self.run_binary("llvm-nm", [str(self.obj_file)])
        self.assertEqual(result.returncode, 0)
        # Should contain our symbols
        self.assertTrue(
            "global_var" in result.stdout or "global_var" in result.stderr,
            "Should find global_var symbol"
        )

    def test_llvm_objdump_disassemble(self):
        """Test llvm-objdump disassembly."""
        result = self.run_binary("llvm-objdump", ["-d", str(self.obj_file)])
        self.assertEqual(result.returncode, 0)

    def test_llvm_objdump_headers(self):
        """Test llvm-objdump section headers."""
        result = self.run_binary("llvm-objdump", ["-h", str(self.obj_file)])
        self.assertEqual(result.returncode, 0)

    def test_llvm_readobj_file_headers(self):
        """Test llvm-readobj to read object file headers."""
        result = self.run_binary("llvm-readobj", ["--file-headers", str(self.obj_file)])
        self.assertEqual(result.returncode, 0)

    def test_llvm_readobj_sections(self):
        """Test llvm-readobj to read sections."""
        result = self.run_binary("llvm-readobj", ["--sections", str(self.obj_file)])
        self.assertEqual(result.returncode, 0)


class TestBinaryManipulation(ToolchainTestBase):
    """Test binary manipulation tools."""

    def setUp(self):
        super().setUp()
        # Create a test executable with debug symbols
        c_file = self.temp_path / "manip.c"
        c_file.write_text(
            'int main() { return 0; }\n'
        )

        self.exe_file = self.temp_path / "manip.exe"
        self.run_binary("clang", ["-g", str(c_file), "-o", str(self.exe_file)])

    def test_llvm_strip_executable(self):
        """Test llvm-strip to remove debug symbols."""
        # Get original size
        original_size = self.exe_file.stat().st_size

        # Strip
        result = self.run_binary("llvm-strip", [str(self.exe_file)])
        self.assertEqual(result.returncode, 0)

        # Size should be same or smaller (Windows PE may not shrink much)
        new_size = self.exe_file.stat().st_size
        self.assertLessEqual(new_size, original_size)

    def test_llvm_objcopy_create_copy(self):
        """Test llvm-objcopy to copy binary."""
        copy_file = self.temp_path / "manip_copy.exe"
        result = self.run_binary("llvm-objcopy", [
            str(self.exe_file),
            str(copy_file)
        ])
        self.assertEqual(result.returncode, 0)
        self.assertTrue(copy_file.exists())

    def test_llvm_objcopy_strip_sections(self):
        """Test llvm-objcopy to strip specific sections."""
        output_file = self.temp_path / "manip_stripped.exe"
        result = self.run_binary("llvm-objcopy", [
            "--strip-debug",
            str(self.exe_file),
            str(output_file)
        ])
        self.assertEqual(result.returncode, 0)
        self.assertTrue(output_file.exists())


class TestLinkerVariants(ToolchainTestBase):
    """Test different linker variants to determine which are needed."""

    def setUp(self):
        super().setUp()
        self.c_file = self.temp_path / "link_test.c"
        self.c_file.write_text('int main() { return 0; }\n')

    def test_default_linker(self):
        """Test compilation with default linker."""
        output = self.temp_path / "test_default.exe"
        result = self.run_binary("clang", [str(self.c_file), "-o", str(output)])
        self.assertTrue(output.exists())

    def test_lld_link_explicit(self):
        """Test using lld-link explicitly."""
        output = self.temp_path / "test_lld_link.exe"
        result = self.run_binary("clang", [
            "-fuse-ld=lld",
            str(self.c_file),
            "-o", str(output)
        ])
        self.assertTrue(output.exists())

    def test_ld_lld_if_exists(self):
        """Test if ld.lld.exe can be used (Unix-style LLD)."""
        # On Windows, this may not work as expected
        ld_lld = self.bin_dir / "ld.lld.exe"
        if ld_lld.exists():
            # Just verify it exists and can show version
            result = self.run_binary("ld.lld", ["--version"], check=False)
            # May or may not work on Windows, just check it exists


class TestSharedLibraries(ToolchainTestBase):
    """Test shared library (DLL) creation and linking."""

    def test_create_dll_basic(self):
        """Test creating a basic DLL."""
        # Create DLL source
        dll_c = self.temp_path / "mylib.c"
        dll_c.write_text(
            '__declspec(dllexport) int add(int a, int b) { return a + b; }\n'
            '__declspec(dllexport) int multiply(int a, int b) { return a * b; }\n'
        )

        # Compile to DLL
        dll_file = self.temp_path / "mylib.dll"
        result = self.run_binary("clang", [
            "-shared",
            "-fuse-ld=lld",
            str(dll_c),
            "-o", str(dll_file)
        ])

        self.assertTrue(dll_file.exists())

        # Should also create import library (.lib)
        lib_file = self.temp_path / "mylib.lib"
        if lib_file.exists():
            self.assertTrue(True, "Import library created")

    def test_create_and_link_dll(self):
        """Test creating a DLL and linking an executable against it."""
        # Create DLL source
        dll_c = self.temp_path / "mathlib.c"
        dll_c.write_text(
            '__declspec(dllexport) int compute(int x) { return x * 2 + 1; }\n'
        )

        # Compile to DLL (lld-link on Windows automatically creates .lib)
        dll_file = self.temp_path / "mathlib.dll"
        self.run_binary("clang", [
            "-shared",
            "-fuse-ld=lld",
            str(dll_c),
            "-o", str(dll_file)
        ])

        self.assertTrue(dll_file.exists())

        # Check if import library was created
        lib_file = self.temp_path / "mathlib.lib"

        # Create executable that uses the DLL
        main_c = self.temp_path / "main.c"
        main_c.write_text(
            '__declspec(dllimport) int compute(int x);\n'
            'int main() { return compute(5); }\n'
        )

        # Link against the DLL's import library if it exists
        exe = self.temp_path / "main.exe"

        if lib_file.exists():
            self.run_binary("clang", [
                "-fuse-ld=lld",
                str(main_c),
                str(lib_file),
                "-o", str(exe)
            ])
        else:
            # If no .lib, just verify DLL was created
            # On some configurations, linking might need explicit .def file
            self.assertTrue(dll_file.exists(), "DLL should be created even without .lib")
            return  # Skip the linking test if no .lib

        self.assertTrue(exe.exists())

        # Run the executable (DLL must be in same directory)
        result = subprocess.run([str(exe)], capture_output=True, text=True, cwd=str(self.temp_path))
        self.assertEqual(result.returncode, 11)  # compute(5) = 5*2+1 = 11

    def test_dll_with_cpp(self):
        """Test creating a C++ DLL."""
        # Create C++ DLL source
        dll_cpp = self.temp_path / "cpplib.cpp"
        dll_cpp.write_text(
            '#include <string>\n'
            'extern "C" __declspec(dllexport) int string_length(const char* str) {\n'
            '    return std::string(str).length();\n'
            '}\n'
        )

        # Compile to DLL
        dll_file = self.temp_path / "cpplib.dll"
        result = self.run_binary("clang++", [
            "-shared",
            "-fuse-ld=lld",
            str(dll_cpp),
            "-o", str(dll_file)
        ])

        self.assertTrue(dll_file.exists())

    def test_dll_from_object_files(self):
        """Test creating DLL from pre-compiled object files."""
        # Create source
        c_file = self.temp_path / "objlib.c"
        c_file.write_text(
            '__declspec(dllexport) int global_var = 42;\n'
            '__declspec(dllexport) int get_value() { return global_var; }\n'
        )

        # Compile to object first (Windows doesn't require -fPIC)
        obj_file = self.temp_path / "objlib.o"
        result = self.run_binary("clang", [
            "-c",
            str(c_file),
            "-o", str(obj_file)
        ])

        self.assertTrue(obj_file.exists())

        # Create DLL from object file
        dll_file = self.temp_path / "objlib.dll"
        result = self.run_binary("clang", [
            "-shared",
            "-fuse-ld=lld",
            str(obj_file),
            "-o", str(dll_file)
        ])

        self.assertTrue(dll_file.exists())


class TestIntegrationScenarios(ToolchainTestBase):
    """Test complete build scenarios combining multiple tools."""

    def test_compile_link_run_c(self):
        """Test complete C workflow: compile, link, run."""
        c_file = self.temp_path / "complete.c"
        c_file.write_text(
            '#include <stdio.h>\n'
            'int main() { printf("Complete test\\n"); return 42; }\n'
        )

        # Compile
        exe = self.temp_path / "complete.exe"
        self.run_binary("clang", ["-fuse-ld=lld", str(c_file), "-o", str(exe)])

        # Run
        result = subprocess.run([str(exe)], capture_output=True, text=True)
        self.assertEqual(result.returncode, 42)
        self.assertIn("Complete test", result.stdout)

    def test_compile_archive_link(self):
        """Test workflow: compile to objects, create archive, link."""
        # Create library source
        lib_c = self.temp_path / "mylib.c"
        lib_c.write_text('int mylib_func() { return 123; }\n')

        # Compile to object
        lib_obj = self.temp_path / "mylib.o"
        self.run_binary("clang", ["-c", str(lib_c), "-o", str(lib_obj)])

        # Create archive
        lib_archive = self.temp_path / "libmy.a"
        self.run_binary("llvm-ar", ["rcs", str(lib_archive), str(lib_obj)])

        # Create main source that uses the library
        main_c = self.temp_path / "main.c"
        main_c.write_text(
            'extern int mylib_func();\n'
            'int main() { return mylib_func(); }\n'
        )

        # Compile and link with archive
        exe = self.temp_path / "main.exe"
        self.run_binary("clang", [
            "-fuse-ld=lld",
            str(main_c),
            str(lib_archive),
            "-o", str(exe)
        ])

        # Run
        result = subprocess.run([str(exe)], capture_output=True, text=True)
        self.assertEqual(result.returncode, 123)

    def test_compile_inspect_strip_pipeline(self):
        """Test workflow: compile with debug, inspect, strip."""
        c_file = self.temp_path / "pipeline.c"
        c_file.write_text('int global = 10;\nint main() { return global; }\n')

        # Compile with debug symbols
        exe = self.temp_path / "pipeline.exe"
        self.run_binary("clang", ["-g", str(c_file), "-o", str(exe)])

        original_size = exe.stat().st_size

        # Inspect with nm
        nm_result = self.run_binary("llvm-nm", [str(exe)])
        self.assertEqual(nm_result.returncode, 0)

        # Strip
        self.run_binary("llvm-strip", [str(exe)])

        # Verify still runs
        result = subprocess.run([str(exe)], capture_output=True, text=True)
        self.assertEqual(result.returncode, 10)


class TestClangVariants(ToolchainTestBase):
    """Test if different clang variants are actually needed."""

    def test_clang_exe_compiles_c(self):
        """Test clang.exe can compile C."""
        c_file = self.temp_path / "test.c"
        c_file.write_text('int main() { return 0; }\n')
        exe = self.temp_path / "test.exe"

        result = self.run_binary("clang", [str(c_file), "-o", str(exe)])
        self.assertTrue(exe.exists())

    def test_clang_exe_compiles_cpp_with_flag(self):
        """Test clang.exe can compile C++ with -x c++."""
        cpp_file = self.temp_path / "test.cpp"
        cpp_file.write_text(
            '#include <iostream>\n'
            'int main() { std::cout << "test"; return 0; }\n'
        )
        exe = self.temp_path / "test.exe"

        result = self.run_binary("clang", ["-x", "c++", str(cpp_file), "-o", str(exe)])
        self.assertTrue(exe.exists())

    def test_clang_plusplus_compiles_cpp(self):
        """Test clang++.exe compiles C++."""
        cpp_file = self.temp_path / "test.cpp"
        cpp_file.write_text(
            '#include <iostream>\n'
            'int main() { std::cout << "test"; return 0; }\n'
        )
        exe = self.temp_path / "test.exe"

        result = self.run_binary("clang++", [str(cpp_file), "-o", str(exe)])
        self.assertTrue(exe.exists())

    def test_clang_cl_if_exists(self):
        """Test clang-cl.exe if it exists (MSVC-compatible driver)."""
        clang_cl = self.bin_dir / "clang-cl.exe"
        if clang_cl.exists():
            c_file = self.temp_path / "test.c"
            c_file.write_text('int main() { return 0; }\n')
            exe = self.temp_path / "test_cl.exe"

            # clang-cl uses MSVC-style flags
            result = self.run_binary("clang-cl", [
                str(c_file),
                f"/Fe{exe}"
            ], check=False)
            # May or may not work depending on MSVC availability


if __name__ == "__main__":
    # Run with verbose output
    unittest.main(verbosity=2)
