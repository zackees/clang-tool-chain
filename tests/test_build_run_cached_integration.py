"""
Integration test specifically for clang-tool-chain-build-run with --cached flag.

This test verifies the complete caching workflow in a single comprehensive test.
"""

import os
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))


class TestBuildRunCachedIntegration(unittest.TestCase):
    """Comprehensive integration test for --cached flag functionality."""

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

    def test_complete_cached_workflow(self):
        """
        Test the complete --cached workflow:
        1. First run: Cache miss, compile and run
        2. Second run: Cache hit, skip compilation and run
        3. Modify source: Cache invalidation, recompile and run
        4. Third run: Cache hit again with new version
        """
        cpp_file = self.temp_path / "cached_test.cpp"
        hash_file = cpp_file.with_suffix(".hash")
        exe_file = cpp_file.with_suffix(".exe" if sys.platform.startswith("win") else "")

        # Step 1: Create initial source file
        cpp_file.write_text(
            """
#include <iostream>
int main() {
    std::cout << "VERSION_1" << std::endl;
    return 0;
}
"""
        )

        # Step 2: First run with --cached (should compile)
        print("\n=== Step 1: First run (cache miss) ===")
        result1 = subprocess.run(
            ["clang-tool-chain-build-run", "--cached", str(cpp_file)],
            capture_output=True,
            text=True,
            timeout=60,
        )

        # Verify first run
        self.assertEqual(result1.returncode, 0, f"First run should succeed\nStderr: {result1.stderr}")
        self.assertIn("VERSION_1", result1.stdout, "Should output VERSION_1")
        self.assertIn("Cache miss", result1.stderr, "Should report cache miss on first run")
        self.assertIn("Compiling:", result1.stderr, "Should compile on first run")
        self.assertTrue(hash_file.exists(), "Hash file should be created")
        self.assertTrue(exe_file.exists(), "Executable should be created")

        # Store the hash for later verification
        initial_hash = hash_file.read_text().strip()
        initial_exe_mtime = exe_file.stat().st_mtime

        # Small delay to ensure timestamps differ if recompilation occurs
        time.sleep(0.1)

        # Step 3: Second run with --cached (should use cache)
        print("\n=== Step 2: Second run (cache hit) ===")
        result2 = subprocess.run(
            ["clang-tool-chain-build-run", "--cached", str(cpp_file)],
            capture_output=True,
            text=True,
            timeout=60,
        )

        # Verify second run used cache
        self.assertEqual(result2.returncode, 0, f"Second run should succeed\nStderr: {result2.stderr}")
        self.assertIn("VERSION_1", result2.stdout, "Should still output VERSION_1")
        self.assertIn("Cache hit", result2.stderr, "Should report cache hit")
        self.assertIn("skipping compilation", result2.stderr, "Should skip compilation")
        self.assertNotIn("Compiling:", result2.stderr, "Should NOT compile on cache hit")

        # Verify executable wasn't recompiled (same mtime)
        second_exe_mtime = exe_file.stat().st_mtime
        self.assertEqual(
            initial_exe_mtime,
            second_exe_mtime,
            "Executable should not be recompiled on cache hit (same mtime)",
        )

        # Verify hash file unchanged
        second_hash = hash_file.read_text().strip()
        self.assertEqual(initial_hash, second_hash, "Hash should remain unchanged on cache hit")

        # Small delay before modification
        time.sleep(0.1)

        # Step 4: Modify source file
        print("\n=== Step 3: Modify source (cache invalidation) ===")
        cpp_file.write_text(
            """
#include <iostream>
int main() {
    std::cout << "VERSION_2_MODIFIED" << std::endl;
    return 42;
}
"""
        )

        # Step 5: Third run after modification (should recompile)
        result3 = subprocess.run(
            ["clang-tool-chain-build-run", "--cached", str(cpp_file)],
            capture_output=True,
            text=True,
            timeout=60,
        )

        # Verify recompilation occurred
        self.assertEqual(result3.returncode, 42, f"Third run should succeed with new exit code\nStderr: {result3.stderr}")
        self.assertIn("VERSION_2_MODIFIED", result3.stdout, "Should output new version text")
        self.assertIn("Cache miss", result3.stderr, "Should report cache miss after file change")
        self.assertIn("Hash mismatch", result3.stderr, "Should detect hash mismatch")
        self.assertIn("Compiling:", result3.stderr, "Should recompile after modification")

        # Verify executable was recompiled (different mtime)
        third_exe_mtime = exe_file.stat().st_mtime
        self.assertGreater(
            third_exe_mtime,
            second_exe_mtime,
            "Executable should be recompiled after source change (newer mtime)",
        )

        # Verify hash was updated
        third_hash = hash_file.read_text().strip()
        self.assertNotEqual(initial_hash, third_hash, "Hash should be updated after source change")

        # Small delay before final run
        time.sleep(0.1)

        # Step 6: Fourth run (should use new cache)
        print("\n=== Step 4: Fourth run (cache hit with new version) ===")
        result4 = subprocess.run(
            ["clang-tool-chain-build-run", "--cached", str(cpp_file)],
            capture_output=True,
            text=True,
            timeout=60,
        )

        # Verify cache works with modified version
        self.assertEqual(result4.returncode, 42, f"Fourth run should succeed\nStderr: {result4.stderr}")
        self.assertIn("VERSION_2_MODIFIED", result4.stdout, "Should still output modified version")
        self.assertIn("Cache hit", result4.stderr, "Should report cache hit for modified version")
        self.assertIn("skipping compilation", result4.stderr, "Should skip compilation on cache hit")

        # Verify executable wasn't recompiled again
        fourth_exe_mtime = exe_file.stat().st_mtime
        self.assertEqual(
            third_exe_mtime,
            fourth_exe_mtime,
            "Executable should not be recompiled on cache hit (same mtime)",
        )

        print("\n=== All cache workflow steps passed! ===")

    def test_cached_with_cpp11_flag(self):
        """Test that --cached works correctly with C++11 flag."""
        cpp_file = self.temp_path / "cached_cpp11.cpp"
        hash_file = cpp_file.with_suffix(".hash")

        cpp_file.write_text(
            """
#include <iostream>
#include <vector>
int main() {
    std::vector<int> v = {1, 2, 3};  // C++11 initializer list
    for (auto x : v) {  // C++11 range-based for loop
        std::cout << x << " ";
    }
    std::cout << "CPP11_CACHED" << std::endl;
    return 0;
}
"""
        )

        # First run with --cached and C++11 flag
        result1 = subprocess.run(
            ["clang-tool-chain-build-run", "--cached", str(cpp_file), "-std=c++11"],
            capture_output=True,
            text=True,
            timeout=60,
        )

        self.assertEqual(result1.returncode, 0, f"First run with C++11 should succeed\nStderr: {result1.stderr}")
        self.assertIn("CPP11_CACHED", result1.stdout)
        self.assertTrue(hash_file.exists(), "Hash file should be created")

        # Second run (should use cache)
        result2 = subprocess.run(
            ["clang-tool-chain-build-run", "--cached", str(cpp_file), "-std=c++11"],
            capture_output=True,
            text=True,
            timeout=60,
        )

        self.assertEqual(result2.returncode, 0, f"Second run should succeed\nStderr: {result2.stderr}")
        self.assertIn("CPP11_CACHED", result2.stdout)
        self.assertIn("Cache hit", result2.stderr, "Should use cache on second run with C++11")

    def test_cached_with_compiler_flags(self):
        """Test that --cached works correctly with compiler flags."""
        cpp_file = self.temp_path / "cached_flags.cpp"
        hash_file = cpp_file.with_suffix(".hash")

        cpp_file.write_text(
            """
#include <iostream>
#include <optional>
int main() {
    std::optional<int> value = 123;
    std::cout << "CPP17_WORKS: " << value.value() << std::endl;
    return 0;
}
"""
        )

        # First run with --cached and compiler flags
        result1 = subprocess.run(
            ["clang-tool-chain-build-run", "--cached", str(cpp_file), "-std=c++17"],
            capture_output=True,
            text=True,
            timeout=60,
        )

        self.assertEqual(result1.returncode, 0, f"First run with flags should succeed\nStderr: {result1.stderr}")
        self.assertIn("CPP17_WORKS: 123", result1.stdout)
        self.assertTrue(hash_file.exists(), "Hash file should be created")

        # Second run (should use cache)
        result2 = subprocess.run(
            ["clang-tool-chain-build-run", "--cached", str(cpp_file), "-std=c++17"],
            capture_output=True,
            text=True,
            timeout=60,
        )

        self.assertEqual(result2.returncode, 0, f"Second run should succeed\nStderr: {result2.stderr}")
        self.assertIn("CPP17_WORKS: 123", result2.stdout)
        self.assertIn("Cache hit", result2.stderr, "Should use cache on second run")

    def test_cached_with_program_arguments(self):
        """Test that --cached works correctly when passing arguments to the program."""
        cpp_file = self.temp_path / "cached_args.cpp"

        cpp_file.write_text(
            """
#include <iostream>
int main(int argc, char* argv[]) {
    std::cout << "ARGC: " << argc << std::endl;
    for (int i = 1; i < argc; ++i) {
        std::cout << "ARG" << i << ": " << argv[i] << std::endl;
    }
    return 0;
}
"""
        )

        # First run with arguments
        result1 = subprocess.run(
            ["clang-tool-chain-build-run", "--cached", str(cpp_file), "--", "hello", "world"],
            capture_output=True,
            text=True,
            timeout=60,
        )

        self.assertEqual(result1.returncode, 0, f"First run should succeed\nStderr: {result1.stderr}")
        self.assertIn("ARG1: hello", result1.stdout)
        self.assertIn("ARG2: world", result1.stdout)

        # Second run with different arguments (should use cache for compilation)
        result2 = subprocess.run(
            ["clang-tool-chain-build-run", "--cached", str(cpp_file), "--", "foo", "bar", "baz"],
            capture_output=True,
            text=True,
            timeout=60,
        )

        self.assertEqual(result2.returncode, 0, f"Second run should succeed\nStderr: {result2.stderr}")
        self.assertIn("ARG1: foo", result2.stdout)
        self.assertIn("ARG2: bar", result2.stdout)
        self.assertIn("ARG3: baz", result2.stdout)
        self.assertIn("Cache hit", result2.stderr, "Should use cache even with different program arguments")


if __name__ == "__main__":
    unittest.main()
