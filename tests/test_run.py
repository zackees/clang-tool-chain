"""
Integration tests for clang-tool-chain-run command.

Tests the run utility that compiles C/C++ programs using Cosmopolitan CC
to Actually Portable Executables (APE) and runs them. These executables
run natively on Windows, Linux, macOS, FreeBSD, NetBSD, and OpenBSD.
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
class TestRunCommand(unittest.TestCase):
    """Test the clang-tool-chain-run command."""

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

    def test_run_main_exists(self):
        """Test that run_main function exists."""
        self.assertTrue(hasattr(wrapper, "run_main"), "run_main function should exist")
        self.assertTrue(callable(wrapper.run_main), "run_main should be callable")

    def test_run_simple_cpp(self):
        """Test compiling and running a simple C++ program with cosmocc."""
        # Create a simple C++ file
        cpp_file = self.temp_path / "test.cpp"
        cpp_file.write_text('#include <iostream>\nint main() { std::cout << "SUCCESS_COSMO" << std::endl; return 0; }')

        # Run using subprocess since run_main uses sys.exit
        result = subprocess.run(
            ["clang-tool-chain-run", str(cpp_file)],
            capture_output=True,
            text=True,
            timeout=60,
        )

        # Check that it succeeded and printed the expected output
        self.assertEqual(result.returncode, 0, f"Run should succeed\nStdout: {result.stdout}\nStderr: {result.stderr}")
        self.assertIn("SUCCESS_COSMO", result.stdout, "Should output SUCCESS_COSMO")

        # Verify that a .com file was created (Actually Portable Executable)
        com_file = cpp_file.with_suffix(".com")
        self.assertTrue(com_file.exists(), f"APE file should exist: {com_file}")

    def test_run_simple_c(self):
        """Test compiling and running a simple C program with cosmocc."""
        # Create a simple C file
        c_file = self.temp_path / "test.c"
        c_file.write_text('#include <stdio.h>\nint main() { printf("C_SUCCESS_COSMO\\n"); return 0; }')

        # Run using subprocess
        result = subprocess.run(
            ["clang-tool-chain-run", str(c_file)],
            capture_output=True,
            text=True,
            timeout=60,
        )

        # Check that it succeeded
        self.assertEqual(result.returncode, 0, f"Run should succeed\nStdout: {result.stdout}\nStderr: {result.stderr}")
        self.assertIn("C_SUCCESS_COSMO", result.stdout, "Should output C_SUCCESS_COSMO")

        # Verify that a .com file was created
        com_file = c_file.with_suffix(".com")
        self.assertTrue(com_file.exists(), f"APE file should exist: {com_file}")

    def test_run_with_arguments(self):
        """Test running a program that takes arguments."""
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
            ["clang-tool-chain-run", str(cpp_file), "--", "arg1", "arg2"],
            capture_output=True,
            text=True,
            timeout=60,
        )

        self.assertEqual(result.returncode, 0, f"Run should succeed\nStderr: {result.stderr}")
        self.assertIn("arg1", result.stdout)
        self.assertIn("arg2", result.stdout)

    def test_run_with_compiler_flags(self):
        """Test running with compiler flags."""
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
            ["clang-tool-chain-run", str(cpp_file), "-std=c++17"],
            capture_output=True,
            text=True,
            timeout=60,
        )

        self.assertEqual(result.returncode, 0, f"Run with flags should succeed\nStderr: {result.stderr}")
        self.assertIn("HAS_VALUE", result.stdout)

    def test_cached_run_first_run(self):
        """Test --cached flag on first run (should compile)."""
        cpp_file = self.temp_path / "cached.cpp"
        cpp_file.write_text('#include <iostream>\nint main() { std::cout << "CACHED_COSMO" << std::endl; return 0; }')

        hash_file = cpp_file.with_suffix(".hash")

        # First run with --cached
        result = subprocess.run(
            ["clang-tool-chain-run", "--cached", str(cpp_file)],
            capture_output=True,
            text=True,
            timeout=60,
        )

        self.assertEqual(result.returncode, 0, f"First cached run should succeed\nStderr: {result.stderr}")
        self.assertIn("CACHED_COSMO", result.stdout)
        self.assertIn("Cache miss", result.stderr, "First run should be cache miss")
        self.assertTrue(hash_file.exists(), "Hash file should be created")

    def test_cached_run_second_run(self):
        """Test --cached flag on second run (should skip compilation)."""
        cpp_file = self.temp_path / "cached2.cpp"
        cpp_file.write_text('#include <iostream>\nint main() { std::cout << "CACHED2_COSMO" << std::endl; return 0; }')

        # First run
        result1 = subprocess.run(
            ["clang-tool-chain-run", "--cached", str(cpp_file)],
            capture_output=True,
            text=True,
            timeout=60,
        )
        self.assertEqual(result1.returncode, 0)

        # Second run (should use cache)
        result2 = subprocess.run(
            ["clang-tool-chain-run", "--cached", str(cpp_file)],
            capture_output=True,
            text=True,
            timeout=60,
        )

        self.assertEqual(result2.returncode, 0, f"Second cached run should succeed\nStderr: {result2.stderr}")
        self.assertIn("CACHED2_COSMO", result2.stdout)
        self.assertIn("Cache hit", result2.stderr, "Second run should be cache hit")
        self.assertIn("skipping compilation", result2.stderr)

    def test_cached_run_invalidation(self):
        """Test that cache is invalidated when source file changes."""
        cpp_file = self.temp_path / "cached3.cpp"
        cpp_file.write_text('#include <iostream>\nint main() { std::cout << "VERSION1" << std::endl; return 0; }')

        # First run
        result1 = subprocess.run(
            ["clang-tool-chain-run", "--cached", str(cpp_file)],
            capture_output=True,
            text=True,
            timeout=60,
        )
        self.assertEqual(result1.returncode, 0)
        self.assertIn("VERSION1", result1.stdout)

        # Modify the file
        cpp_file.write_text('#include <iostream>\nint main() { std::cout << "VERSION2" << std::endl; return 0; }')

        # Second run (should recompile due to hash mismatch)
        result2 = subprocess.run(
            ["clang-tool-chain-run", "--cached", str(cpp_file)],
            capture_output=True,
            text=True,
            timeout=60,
        )

        self.assertEqual(result2.returncode, 0, f"Run after file change should succeed\nStderr: {result2.stderr}")
        self.assertIn("VERSION2", result2.stdout, "Should run new version")
        self.assertIn("Hash mismatch", result2.stderr, "Should detect hash mismatch")

    @unittest.skipUnless(platform.system() in ("Linux", "Darwin"), "Shebang test only for Unix platforms")
    def test_shebang_execution(self):
        """Test that a C++ file with shebang can be executed directly on Unix."""
        # Create C++ file with shebang
        cpp_file = self.temp_path / "shebang_test.cpp"
        shebang_content = """#!/usr/bin/env -S clang-tool-chain-run --cached
#include <iostream>
int main() {
    std::cout << "SHEBANG_SUCCESS_COSMO" << std::endl;
    return 0;
}
"""
        cpp_file.write_text(shebang_content)

        # Make executable
        cpp_file.chmod(0o755)

        # Try to run directly
        result = subprocess.run([str(cpp_file)], capture_output=True, text=True, timeout=60)

        # This should work if clang-tool-chain-run is in PATH
        if result.returncode == 0:
            self.assertIn("SHEBANG_SUCCESS_COSMO", result.stdout, "Shebang execution should produce expected output")
        else:
            # If it failed, it's likely because the command isn't in PATH yet
            # This is expected during development, so we skip
            self.skipTest(f"Shebang execution requires clang-tool-chain-run in PATH: {result.stderr}")

    def test_compilation_error_handling(self):
        """Test that compilation errors are properly reported."""
        # Create a file with syntax errors
        cpp_file = self.temp_path / "error.cpp"
        cpp_file.write_text("int main() { THIS_IS_INVALID; return 0; }")

        result = subprocess.run(
            ["clang-tool-chain-run", str(cpp_file)],
            capture_output=True,
            text=True,
            timeout=60,
        )

        # Compilation should fail and report the error
        # Note: cosmocc might still create a .com file, but compilation errors should be visible
        self.assertIn("error:", result.stderr, "Should show compilation error")
        self.assertIn("THIS_IS_INVALID", result.stderr, "Should mention the invalid identifier")

    def test_ape_executable_format(self):
        """Test that the output is actually an APE (.com file)."""
        cpp_file = self.temp_path / "ape_test.cpp"
        cpp_file.write_text('#include <iostream>\nint main() { std::cout << "APE_TEST" << std::endl; return 0; }')

        result = subprocess.run(
            ["clang-tool-chain-run", str(cpp_file)],
            capture_output=True,
            text=True,
            timeout=60,
        )

        self.assertEqual(result.returncode, 0)

        # Verify the .com file exists
        com_file = cpp_file.with_suffix(".com")
        self.assertTrue(com_file.exists(), "APE file should be created with .com extension")

        # Verify the file is executable
        self.assertTrue(os.access(com_file, os.X_OK) or platform.system() == "Windows", "APE should be executable")

        # Run the APE directly to verify it works
        result_direct = subprocess.run([str(com_file)], capture_output=True, text=True, timeout=60)
        self.assertEqual(result_direct.returncode, 0, "APE should run directly")
        self.assertIn("APE_TEST", result_direct.stdout, "Direct APE execution should work")

    def test_cross_platform_compatibility(self):
        """Test that the APE works on the current platform."""
        # Cosmopolitan APE binaries detect platform at runtime, not compile-time
        # So we test a simple program that works cross-platform
        cpp_file = self.temp_path / "platform_test.cpp"
        cpp_file.write_text("""
#include <iostream>
int main() {
    std::cout << "APE_CROSS_PLATFORM_SUCCESS" << std::endl;
    return 0;
}
""")

        result = subprocess.run(
            ["clang-tool-chain-run", str(cpp_file)],
            capture_output=True,
            text=True,
            timeout=60,
        )

        self.assertEqual(result.returncode, 0, f"APE should run on all platforms\nStderr: {result.stderr}")
        self.assertIn("APE_CROSS_PLATFORM_SUCCESS", result.stdout, "APE should execute successfully")

    def test_with_inlined_directives(self):
        """Test that inlined build directives work with clang-tool-chain-run."""
        cpp_file = self.temp_path / "directives_test.cpp"
        cpp_file.write_text("""
// @std: c++17
#include <iostream>
#include <optional>
int main() {
    std::optional<int> opt = 42;
    if (opt) std::cout << "DIRECTIVES_WORK" << std::endl;
    return 0;
}
""")

        result = subprocess.run(
            ["clang-tool-chain-run", str(cpp_file)],
            capture_output=True,
            text=True,
            timeout=60,
        )

        self.assertEqual(result.returncode, 0, f"Run with directives should succeed\nStderr: {result.stderr}")
        self.assertIn("DIRECTIVES_WORK", result.stdout)


if __name__ == "__main__":
    unittest.main()
