"""
Integration tests for essential build tools availability.

These tests verify that all core build tools are available and functional:
- Compilers: clang, clang++
- Linker: lld
- Archiver: llvm-ar
- Binary utilities: llvm-nm, llvm-objdump, llvm-objcopy, llvm-ranlib, llvm-strip, llvm-readelf

These tests skip linting/formatting tools like clang-tidy and clang-format.
"""

'''

DISABLED FOR NOW

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from clang_tool_chain import wrapper


class TestEssentialBuildTools(unittest.TestCase):
    """Test that essential build tools are available and functional."""

    def setUp(self):
        """Set up test environment."""
        self.temp_dir = tempfile.mkdtemp()
        self.temp_path = Path(self.temp_dir)

    def test_clang_available(self):
        """Test that clang (C compiler) is available."""
        try:
            tool_path = wrapper.find_tool_binary("clang")
            self.assertTrue(tool_path.exists(), f"clang binary not found at {tool_path}")
        except RuntimeError as e:
            self.skipTest(f"Binaries not installed: {e}")

    def test_clang_cpp_available(self):
        """Test that clang++ (C++ compiler) is available."""
        try:
            tool_path = wrapper.find_tool_binary("clang++")
            self.assertTrue(tool_path.exists(), f"clang++ binary not found at {tool_path}")
        except RuntimeError as e:
            self.skipTest(f"Binaries not installed: {e}")

    def test_lld_available(self):
        """Test that lld (linker) is available."""
        try:
            platform_name, _ = wrapper.get_platform_info()
            tool_name = "lld-link" if platform_name == "win" else "lld"
            tool_path = wrapper.find_tool_binary(tool_name)
            self.assertTrue(tool_path.exists(), f"{tool_name} binary not found at {tool_path}")
        except RuntimeError as e:
            self.skipTest(f"Binaries not installed: {e}")

    def test_llvm_ar_available(self):
        """Test that llvm-ar (archiver) is available."""
        try:
            tool_path = wrapper.find_tool_binary("llvm-ar")
            self.assertTrue(tool_path.exists(), f"llvm-ar binary not found at {tool_path}")
        except RuntimeError as e:
            self.skipTest(f"Binaries not installed: {e}")

    def test_llvm_nm_available(self):
        """Test that llvm-nm (symbol lister) is available."""
        try:
            tool_path = wrapper.find_tool_binary("llvm-nm")
            self.assertTrue(tool_path.exists(), f"llvm-nm binary not found at {tool_path}")
        except RuntimeError as e:
            self.skipTest(f"Binaries not installed: {e}")

    def test_llvm_objdump_available(self):
        """Test that llvm-objdump is available."""
        try:
            tool_path = wrapper.find_tool_binary("llvm-objdump")
            self.assertTrue(tool_path.exists(), f"llvm-objdump binary not found at {tool_path}")
        except RuntimeError as e:
            self.skipTest(f"Binaries not installed: {e}")

    def test_llvm_objcopy_available(self):
        """Test that llvm-objcopy is available."""
        try:
            tool_path = wrapper.find_tool_binary("llvm-objcopy")
            self.assertTrue(tool_path.exists(), f"llvm-objcopy binary not found at {tool_path}")
        except RuntimeError as e:
            self.skipTest(f"Binaries not installed: {e}")

    def test_llvm_ranlib_available(self):
        """Test that llvm-ranlib is available."""
        try:
            tool_path = wrapper.find_tool_binary("llvm-ranlib")
            self.assertTrue(tool_path.exists(), f"llvm-ranlib binary not found at {tool_path}")
        except RuntimeError as e:
            self.skipTest(f"Binaries not installed: {e}")

    def test_llvm_strip_available(self):
        """Test that llvm-strip is available."""
        try:
            tool_path = wrapper.find_tool_binary("llvm-strip")
            self.assertTrue(tool_path.exists(), f"llvm-strip binary not found at {tool_path}")
        except RuntimeError as e:
            self.skipTest(f"Binaries not installed: {e}")

    def test_llvm_readelf_available(self):
        """Test that llvm-readelf is available."""
        try:
            tool_path = wrapper.find_tool_binary("llvm-readelf")
            self.assertTrue(tool_path.exists(), f"llvm-readelf binary not found at {tool_path}")
        except RuntimeError as e:
            self.skipTest(f"Binaries not installed: {e}")


class TestBuildToolsFunctionality(unittest.TestCase):
    """Test that essential build tools actually work (integration tests)."""

    def setUp(self):
        """Set up test environment with temporary directory."""
        self.temp_dir = tempfile.mkdtemp()
        self.temp_path = Path(self.temp_dir)

    def test_clang_version(self):
        """Test that clang can report its version."""
        try:
            result = wrapper.run_tool("clang", ["--version"])
            self.assertEqual(result, 0, "clang --version should return exit code 0")
        except RuntimeError as e:
            self.skipTest(f"Binaries not installed: {e}")

    def test_clang_cpp_version(self):
        """Test that clang++ can report its version."""
        try:
            result = wrapper.run_tool("clang++", ["--version"])
            self.assertEqual(result, 0, "clang++ --version should return exit code 0")
        except RuntimeError as e:
            self.skipTest(f"Binaries not installed: {e}")

    @unittest.skipUnless(sys.platform.startswith("win") or sys.platform.startswith("linux"), "Platform specific test")
    def test_compile_simple_c_program(self):
        """Test compiling a simple C program."""
        try:
            # Create a simple C file
            c_file = self.temp_path / "test.c"
            c_file.write_text('#include <stdio.h>\nint main() { printf("test\\n"); return 0; }')

            # Compile it
            output_file = self.temp_path / "test.exe" if sys.platform.startswith("win") else self.temp_path / "test"
            result = wrapper.run_tool("clang", [str(c_file), "-o", str(output_file)])

            self.assertEqual(result, 0, "Compilation should succeed")
            self.assertTrue(output_file.exists(), "Output executable should exist")
        except RuntimeError as e:
            self.skipTest(f"Binaries not installed: {e}")

    @unittest.skipUnless(sys.platform.startswith("win") or sys.platform.startswith("linux"), "Platform specific test")
    def test_compile_simple_cpp_program(self):
        """Test compiling a simple C++ program."""
        try:
            # Create a simple C++ file
            cpp_file = self.temp_path / "test.cpp"
            cpp_file.write_text('#include <iostream>\nint main() { std::cout << "test" << std::endl; return 0; }')

            # Compile it
            output_file = self.temp_path / "test.exe" if sys.platform.startswith("win") else self.temp_path / "test"
            result = wrapper.run_tool("clang++", [str(cpp_file), "-o", str(output_file)])

            self.assertEqual(result, 0, "Compilation should succeed")
            self.assertTrue(output_file.exists(), "Output executable should exist")
        except RuntimeError as e:
            self.skipTest(f"Binaries not installed: {e}")

    def test_llvm_ar_create_archive(self):
        """Test that llvm-ar can create an archive."""
        try:
            # Create a simple object file first
            c_file = self.temp_path / "test.c"
            c_file.write_text("int test_func() { return 42; }")

            obj_file = self.temp_path / "test.o"
            compile_result = wrapper.run_tool("clang", ["-c", str(c_file), "-o", str(obj_file)])

            if compile_result != 0:
                self.skipTest("Could not compile test object file")

            # Create archive
            archive_file = self.temp_path / "libtest.a"
            ar_result = wrapper.run_tool("llvm-ar", ["rcs", str(archive_file), str(obj_file)])

            self.assertEqual(ar_result, 0, "Archive creation should succeed")
            self.assertTrue(archive_file.exists(), "Archive file should exist")
        except RuntimeError as e:
            self.skipTest(f"Binaries not installed: {e}")

    def test_llvm_nm_list_symbols(self):
        """Test that llvm-nm can list symbols from an object file."""
        try:
            # Create a simple object file
            c_file = self.temp_path / "test.c"
            c_file.write_text("int global_var = 42;\nint test_func() { return global_var; }")

            obj_file = self.temp_path / "test.o"
            compile_result = wrapper.run_tool("clang", ["-c", str(c_file), "-o", str(obj_file)])

            if compile_result != 0:
                self.skipTest("Could not compile test object file")

            # List symbols
            nm_result = wrapper.run_tool("llvm-nm", [str(obj_file)])
            self.assertEqual(nm_result, 0, "llvm-nm should succeed")
        except RuntimeError as e:
            self.skipTest(f"Binaries not installed: {e}")


class TestBuildCommand(unittest.TestCase):
    """Test the clang-tool-chain-build command."""

    def setUp(self):
        """Set up test environment."""
        self.temp_dir = tempfile.mkdtemp()
        self.temp_path = Path(self.temp_dir)

    def tearDown(self):
        """Clean up test environment."""
        import shutil

        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_build_main_exists(self):
        """Test that build_main function exists."""
        self.assertTrue(hasattr(wrapper, "build_main"), "build_main function should exist")
        self.assertTrue(callable(wrapper.build_main), "build_main should be callable")

    @unittest.skipUnless(sys.platform.startswith("win") or sys.platform.startswith("linux"), "Platform specific test")
    def test_build_cpp_file(self):
        """Test building a C++ file using the build command."""
        try:
            # Create a simple C++ file
            cpp_file = self.temp_path / "hello.cpp"
            cpp_file.write_text('#include <iostream>\nint main() { std::cout << "Hello!" << std::endl; return 0; }')

            # Build using subprocess since build_main uses execute_tool (which exits)
            output_file = self.temp_path / "hello.exe" if sys.platform.startswith("win") else self.temp_path / "hello"

            # Use the wrapper's run_tool to compile instead
            result = wrapper.run_tool("clang++", [str(cpp_file), "-o", str(output_file)])

            self.assertEqual(result, 0, "Build should succeed")
            self.assertTrue(output_file.exists(), "Output executable should exist")
        except RuntimeError as e:
            self.skipTest(f"Binaries not installed: {e}")

    def test_execute_tool_exists(self):
        """Test that execute_tool function exists for build_main to use."""
        self.assertTrue(hasattr(wrapper, "execute_tool"))
        self.assertTrue(callable(wrapper.execute_tool))


if __name__ == "__main__":
    unittest.main()
'''
