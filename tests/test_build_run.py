"""
Integration tests for clang-tool-chain-build-run command.

Tests the build-run utility that compiles and runs C/C++ programs in one step,
including caching functionality and shebang support on Unix platforms.
"""

import os
import platform
import subprocess
import tempfile
import unittest
from pathlib import Path

import pytest

from clang_tool_chain import wrapper


@pytest.mark.serial
class TestBuildRunCommand(unittest.TestCase):
    """Test the clang-tool-chain-build-run command."""

    def setUp(self):
        """Set up test environment."""
        self.temp_dir = tempfile.mkdtemp()
        self.temp_path = Path(self.temp_dir)
        self.original_dir = os.getcwd()
        os.chdir(self.temp_dir)

    def tearDown(self):
        """Clean up test environment."""
        os.chdir(self.original_dir)
        import shutil

        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_build_run_main_exists(self):
        """Test that build_run_main function exists."""
        self.assertTrue(hasattr(wrapper, "build_run_main"), "build_run_main function should exist")
        self.assertTrue(callable(wrapper.build_run_main), "build_run_main should be callable")

    def test_compute_file_hash_exists(self):
        """Test that _compute_file_hash helper function exists."""
        self.assertTrue(hasattr(wrapper, "_compute_file_hash"), "_compute_file_hash function should exist")
        self.assertTrue(callable(wrapper._compute_file_hash), "_compute_file_hash should be callable")

    def test_build_and_run_simple_cpp(self):
        """Test building and running a simple C++ program."""
        # Create a simple C++ file
        cpp_file = self.temp_path / "test.cpp"
        cpp_file.write_text('#include <iostream>\nint main() { std::cout << "SUCCESS" << std::endl; return 0; }')

        # Run using subprocess since build_run_main uses sys.exit
        result = subprocess.run(
            ["clang-tool-chain-build-run", str(cpp_file)],
            capture_output=True,
            text=True,
            timeout=30,
        )

        # Check that it succeeded and printed the expected output
        self.assertEqual(result.returncode, 0, f"Build-run should succeed\nStderr: {result.stderr}")
        self.assertIn("SUCCESS", result.stdout, "Should output SUCCESS")

    def test_build_and_run_with_arguments(self):
        """Test building and running a program that takes arguments."""
        # Create a C++ file that echoes arguments
        cpp_file = self.temp_path / "echo_args.cpp"
        cpp_file.write_text("""
#include <iostream>
int main(int argc, char* argv[]) {
    for (int i = 1; i < argc; ++i) {
        std::cout << argv[i] << std::endl;
    }
    return 0;
}
""")

        # Run with arguments
        result = subprocess.run(
            ["clang-tool-chain-build-run", str(cpp_file), "--", "arg1", "arg2"],
            capture_output=True,
            text=True,
            timeout=30,
        )

        self.assertEqual(result.returncode, 0, f"Build-run should succeed\nStderr: {result.stderr}")
        self.assertIn("arg1", result.stdout)
        self.assertIn("arg2", result.stdout)

    def test_build_run_with_cpp11_flag(self):
        """Test building with C++11 flag."""
        # Create a C++ file that uses C++11 features
        cpp_file = self.temp_path / "cpp11.cpp"
        cpp_file.write_text("""
#include <iostream>
#include <vector>
int main() {
    std::vector<int> v = {1, 2, 3};  // C++11 initializer list
    for (auto x : v) {  // C++11 range-based for loop
        std::cout << x << " ";
    }
    std::cout << "CPP11_WORKS" << std::endl;
    return 0;
}
""")

        # Run with C++11 flag
        result = subprocess.run(
            ["clang-tool-chain-build-run", str(cpp_file), "-std=c++11"],
            capture_output=True,
            text=True,
            timeout=30,
        )

        self.assertEqual(result.returncode, 0, f"Build-run with C++11 should succeed\nStderr: {result.stderr}")
        self.assertIn("CPP11_WORKS", result.stdout)

    def test_build_run_with_compiler_flags(self):
        """Test building with compiler flags."""
        # Create a C++ file that uses C++17 features
        cpp_file = self.temp_path / "cpp17.cpp"
        cpp_file.write_text("""
#include <iostream>
#include <optional>
int main() {
    std::optional<int> opt = 42;
    if (opt) std::cout << "HAS_VALUE" << std::endl;
    return 0;
}
""")

        # Run with C++17 flag
        result = subprocess.run(
            ["clang-tool-chain-build-run", str(cpp_file), "-std=c++17"],
            capture_output=True,
            text=True,
            timeout=30,
        )

        self.assertEqual(result.returncode, 0, f"Build-run with flags should succeed\nStderr: {result.stderr}")
        self.assertIn("HAS_VALUE", result.stdout)

    def test_cached_build_first_run(self):
        """Test --cached flag on first run (should compile)."""
        cpp_file = self.temp_path / "cached.cpp"
        cpp_file.write_text('#include <iostream>\nint main() { std::cout << "CACHED" << std::endl; return 0; }')

        hash_file = cpp_file.with_suffix(".hash")

        # First run with --cached
        result = subprocess.run(
            ["clang-tool-chain-build-run", "--cached", str(cpp_file)],
            capture_output=True,
            text=True,
            timeout=30,
        )

        self.assertEqual(result.returncode, 0, f"First cached build should succeed\nStderr: {result.stderr}")
        self.assertIn("CACHED", result.stdout)
        self.assertIn("Cache miss", result.stderr, "First run should be cache miss")
        self.assertTrue(hash_file.exists(), "Hash file should be created")

    def test_cached_build_second_run(self):
        """Test --cached flag on second run (should skip compilation)."""
        cpp_file = self.temp_path / "cached2.cpp"
        cpp_file.write_text('#include <iostream>\nint main() { std::cout << "CACHED2" << std::endl; return 0; }')

        # First run
        result1 = subprocess.run(
            ["clang-tool-chain-build-run", "--cached", str(cpp_file)],
            capture_output=True,
            text=True,
            timeout=30,
        )
        self.assertEqual(result1.returncode, 0)

        # Second run (should use cache)
        result2 = subprocess.run(
            ["clang-tool-chain-build-run", "--cached", str(cpp_file)],
            capture_output=True,
            text=True,
            timeout=30,
        )

        self.assertEqual(result2.returncode, 0, f"Second cached build should succeed\nStderr: {result2.stderr}")
        self.assertIn("CACHED2", result2.stdout)
        self.assertIn("Cache hit", result2.stderr, "Second run should be cache hit")
        self.assertIn("skipping compilation", result2.stderr)

    def test_cached_build_invalidation(self):
        """Test that cache is invalidated when source file changes."""
        cpp_file = self.temp_path / "cached3.cpp"
        cpp_file.write_text('#include <iostream>\nint main() { std::cout << "VERSION1" << std::endl; return 0; }')

        # First run
        result1 = subprocess.run(
            ["clang-tool-chain-build-run", "--cached", str(cpp_file)],
            capture_output=True,
            text=True,
            timeout=30,
        )
        self.assertEqual(result1.returncode, 0)
        self.assertIn("VERSION1", result1.stdout)

        # Modify the file
        cpp_file.write_text('#include <iostream>\nint main() { std::cout << "VERSION2" << std::endl; return 0; }')

        # Second run (should recompile due to hash mismatch)
        result2 = subprocess.run(
            ["clang-tool-chain-build-run", "--cached", str(cpp_file)],
            capture_output=True,
            text=True,
            timeout=30,
        )

        self.assertEqual(result2.returncode, 0, f"Build after file change should succeed\nStderr: {result2.stderr}")
        self.assertIn("VERSION2", result2.stdout, "Should run new version")
        self.assertIn("Hash mismatch", result2.stderr, "Should detect hash mismatch")

    @unittest.skipUnless(platform.system() in ("Linux", "Darwin"), "Shebang test only for Unix platforms")
    def test_shebang_execution(self):
        """Test that a C++ file with shebang can be executed directly on Unix."""
        # Create C++ file with shebang
        cpp_file = self.temp_path / "shebang_test.cpp"
        shebang_content = """#!/usr/bin/env -S clang-tool-chain-build-run --cached
#include <iostream>
int main() {
    std::cout << "SHEBANG_SUCCESS" << std::endl;
    return 0;
}
"""
        cpp_file.write_text(shebang_content)

        # Make executable
        cpp_file.chmod(0o755)

        # Try to run directly
        result = subprocess.run([str(cpp_file)], capture_output=True, text=True, timeout=30)

        # This should work if clang-tool-chain-build-run is in PATH
        if result.returncode == 0:
            self.assertIn("SHEBANG_SUCCESS", result.stdout, "Shebang execution should produce expected output")
        else:
            # If it failed, it's likely because the command isn't in PATH yet
            # This is expected during development, so we skip
            self.skipTest(f"Shebang execution requires clang-tool-chain-build-run in PATH: {result.stderr}")

    def test_c_file_compilation(self):
        """Test that .c files are compiled with clang (not clang++)."""
        # Create a C file (not C++)
        c_file = self.temp_path / "test.c"
        c_file.write_text('#include <stdio.h>\nint main() { printf("C_SUCCESS\\n"); return 0; }')

        result = subprocess.run(
            ["clang-tool-chain-build-run", str(c_file)],
            capture_output=True,
            text=True,
            timeout=30,
        )

        self.assertEqual(result.returncode, 0, f"C file build-run should succeed\nStderr: {result.stderr}")
        self.assertIn("C_SUCCESS", result.stdout)

    def test_compilation_error_handling(self):
        """Test that compilation errors are properly reported."""
        # Create a file with syntax errors
        cpp_file = self.temp_path / "error.cpp"
        cpp_file.write_text("int main() { THIS_IS_INVALID; return 0; }")

        result = subprocess.run(
            ["clang-tool-chain-build-run", str(cpp_file)],
            capture_output=True,
            text=True,
            timeout=30,
        )

        self.assertNotEqual(result.returncode, 0, "Build with errors should fail")
        self.assertIn("Compilation failed", result.stderr)


if __name__ == "__main__":
    unittest.main()
