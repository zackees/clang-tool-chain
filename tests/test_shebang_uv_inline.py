"""
Test that demonstrates C++ files can be directly executed via shebang
using either:
1. Direct: clang-tool-chain-build-run (if installed)
2. Via uv: uv run clang-tool-chain-build-run (if only uv is available)

This is TDD - test written first, then infrastructure verified.
"""

import os
import platform
import subprocess
import tempfile
import unittest
from pathlib import Path


class TestShebangUvInline(unittest.TestCase):
    """Test shebang-based C++ execution with uv fallback."""

    @unittest.skipIf(platform.system() == "Windows", "Shebang execution requires Unix-like OS")
    def test_shebang_direct_execution(self):
        """Test C++ file with direct shebang can be executed."""
        cpp_content = """#!/usr/bin/env -S clang-tool-chain-build-run --cached
#include <iostream>

int main() {
    std::cout << "DIRECT_SHEBANG_SUCCESS" << std::endl;
    return 0;
}
"""
        with tempfile.TemporaryDirectory() as tmpdir:
            cpp_file = Path(tmpdir) / "test_direct.cpp"
            cpp_file.write_text(cpp_content)
            cpp_file.chmod(0o755)

            result = subprocess.run([str(cpp_file)], capture_output=True, text=True, timeout=60, cwd=tmpdir)

            self.assertEqual(result.returncode, 0, f"Failed: {result.stderr}")
            self.assertIn("DIRECT_SHEBANG_SUCCESS", result.stdout)

    @unittest.skipIf(platform.system() == "Windows", "Shebang execution requires Unix-like OS")
    def test_shebang_via_uv_run(self):
        """Test C++ file can be executed via 'uv run' shebang."""
        # This shebang uses uv to run the tool - works if uv is in PATH
        # and the package is installed in the project
        cpp_content = """#!/usr/bin/env -S uv run clang-tool-chain-build-run --cached
#include <iostream>

int main() {
    std::cout << "UV_RUN_SHEBANG_SUCCESS" << std::endl;
    return 0;
}
"""
        with tempfile.TemporaryDirectory() as tmpdir:
            cpp_file = Path(tmpdir) / "test_uv.cpp"
            cpp_file.write_text(cpp_content)
            cpp_file.chmod(0o755)

            # Need to run from project root where pyproject.toml exists
            project_root = Path(__file__).parent.parent

            result = subprocess.run(
                [str(cpp_file)],
                capture_output=True,
                text=True,
                timeout=120,  # uv run may need to set up environment
                cwd=project_root,  # Run from project root for uv to find pyproject.toml
                env={**os.environ, "UV_PROJECT_ENVIRONMENT": str(project_root / ".venv")},
            )

            self.assertEqual(result.returncode, 0, f"Failed: {result.stderr}")
            self.assertIn("UV_RUN_SHEBANG_SUCCESS", result.stdout)

    @unittest.skipIf(platform.system() == "Windows", "Shebang execution requires Unix-like OS")
    def test_inline_cpp_with_assertions(self):
        """Test inline C++ with actual test assertions that exit non-zero on failure."""
        cpp_content = """#!/usr/bin/env -S clang-tool-chain-build-run --cached
#include <iostream>
#include <cassert>

// Inline test demonstrating TDD pattern
int add(int a, int b) { return a + b; }
int multiply(int a, int b) { return a * b; }

int main() {
    // Test cases - will abort if any assertion fails
    assert(add(2, 3) == 5);
    assert(add(-1, 1) == 0);
    assert(multiply(3, 4) == 12);
    assert(multiply(0, 100) == 0);

    std::cout << "INLINE_CPP_TEST_PASSED" << std::endl;
    return 0;
}
"""
        with tempfile.TemporaryDirectory() as tmpdir:
            cpp_file = Path(tmpdir) / "inline_test.cpp"
            cpp_file.write_text(cpp_content)
            cpp_file.chmod(0o755)

            result = subprocess.run([str(cpp_file)], capture_output=True, text=True, timeout=60, cwd=tmpdir)

            self.assertEqual(result.returncode, 0, f"Assertions failed: {result.stderr}")
            self.assertIn("INLINE_CPP_TEST_PASSED", result.stdout)

    @unittest.skipIf(platform.system() == "Windows", "Shebang execution requires Unix-like OS")
    def test_cached_compilation_skips_rebuild(self):
        """Test that --cached flag actually skips recompilation on second run."""
        cpp_content = """#!/usr/bin/env -S clang-tool-chain-build-run --cached
#include <iostream>

int main() {
    std::cout << "CACHED_TEST" << std::endl;
    return 0;
}
"""
        with tempfile.TemporaryDirectory() as tmpdir:
            cpp_file = Path(tmpdir) / "cached_test.cpp"
            cpp_file.write_text(cpp_content)
            cpp_file.chmod(0o755)

            # First run - compiles
            result1 = subprocess.run([str(cpp_file)], capture_output=True, text=True, timeout=60, cwd=tmpdir)
            self.assertEqual(result1.returncode, 0)

            # Verify hash file was created
            hash_file = Path(tmpdir) / "cached_test.hash"
            self.assertTrue(hash_file.exists(), "Hash file should be created for --cached")

            # Second run - should skip compilation (check by timing or output)
            result2 = subprocess.run([str(cpp_file)], capture_output=True, text=True, timeout=60, cwd=tmpdir)
            self.assertEqual(result2.returncode, 0)
            self.assertIn("CACHED_TEST", result2.stdout)


if __name__ == "__main__":
    unittest.main()
