"""
Cross-platform test for executable C++ scripts via shebang.

This test verifies that C++ files can be executed as scripts:
- Linux/macOS: Direct execution via shebang
- Windows: Execution via git-bash (MSYS2/Git Bash)

The shebang feature allows running C++ like a scripting language:
    ./script.cpp  # Compiles (if needed) and runs!
"""

import os
import platform
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path


def find_git_bash() -> str | None:
    """Find git-bash executable on Windows."""
    if platform.system() != "Windows":
        return None

    # Common git-bash locations
    candidates = [
        shutil.which("bash"),  # If git is in PATH, bash might be too
        r"C:\Program Files\Git\bin\bash.exe",
        r"C:\Program Files (x86)\Git\bin\bash.exe",
        os.path.expandvars(r"%LOCALAPPDATA%\Programs\Git\bin\bash.exe"),
        os.path.expandvars(r"%ProgramFiles%\Git\bin\bash.exe"),
    ]

    for candidate in candidates:
        if candidate and Path(candidate).exists():
            return candidate

    return None


class TestShebangCrossPlatform(unittest.TestCase):
    """Test shebang-based C++ execution across all platforms."""

    @classmethod
    def setUpClass(cls):
        """Detect platform capabilities."""
        cls.is_windows = platform.system() == "Windows"
        cls.git_bash = find_git_bash() if cls.is_windows else None

        if cls.is_windows and not cls.git_bash:
            print("WARNING: git-bash not found on Windows. Shebang tests will be skipped.")

    def _create_cpp_script(self, tmpdir: Path, name: str, content: str) -> Path:
        """Create an executable C++ script file."""
        cpp_file = tmpdir / name
        cpp_file.write_text(content, encoding="utf-8")
        if not self.is_windows:
            cpp_file.chmod(0o755)
        return cpp_file

    def _run_cpp_script(
        self, cpp_file: Path, cwd: Path | None = None, timeout: int = 120
    ) -> subprocess.CompletedProcess:
        """Run a C++ script, using git-bash on Windows."""
        run_cwd = cwd if cwd is not None else cpp_file.parent

        if self.is_windows and self.git_bash:
            # On Windows, use git-bash to execute the script
            # Convert Windows path to Unix-style for bash and make it executable
            unix_path = str(cpp_file).replace("\\", "/")
            # Use bash -c with chmod to ensure executable, then run it
            # The shebang is interpreted when the script is executed directly
            result = subprocess.run(
                [self.git_bash, "-c", f"chmod +x '{unix_path}' && '{unix_path}'"],
                capture_output=True,
                text=True,
                timeout=timeout,
                cwd=run_cwd,
            )
        else:
            # On Unix, execute directly
            result = subprocess.run(
                [str(cpp_file)],
                capture_output=True,
                text=True,
                timeout=timeout,
                cwd=run_cwd,
            )
        return result

    def _skip_if_no_bash(self):
        """Skip test if bash is not available (Windows without git-bash)."""
        if self.is_windows and not self.git_bash:
            self.skipTest("git-bash not found on Windows")

    def test_shebang_hello_world(self):
        """Test basic shebang C++ execution."""
        self._skip_if_no_bash()

        cpp_content = """#!/usr/bin/env -S clang-tool-chain-build-run --cached
#include <iostream>

int main() {
    std::cout << "SHEBANG_HELLO_WORLD_SUCCESS" << std::endl;
    return 0;
}
"""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmppath = Path(tmpdir)
            cpp_file = self._create_cpp_script(tmppath, "hello.cpp", cpp_content)

            result = self._run_cpp_script(cpp_file)

            self.assertEqual(result.returncode, 0, f"Failed: {result.stderr}")
            self.assertIn("SHEBANG_HELLO_WORLD_SUCCESS", result.stdout)

    def test_shebang_with_assertions(self):
        """Test inline C++ with assertions (TDD-style)."""
        self._skip_if_no_bash()

        cpp_content = """#!/usr/bin/env -S clang-tool-chain-build-run --cached
#include <iostream>
#include <cassert>
#include <vector>

template<typename T>
T sum(const std::vector<T>& v) {
    T result = T{};
    for (const auto& x : v) result += x;
    return result;
}

int main() {
    // Run inline tests
    assert(sum(std::vector<int>{1, 2, 3, 4, 5}) == 15);
    assert(sum(std::vector<double>{1.5, 2.5}) == 4.0);
    assert(sum(std::vector<int>{}) == 0);

    std::cout << "SHEBANG_ASSERTIONS_PASSED" << std::endl;
    return 0;
}
"""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmppath = Path(tmpdir)
            cpp_file = self._create_cpp_script(tmppath, "test_inline.cpp", cpp_content)

            result = self._run_cpp_script(cpp_file)

            self.assertEqual(result.returncode, 0, f"Assertions failed: {result.stderr}")
            self.assertIn("SHEBANG_ASSERTIONS_PASSED", result.stdout)

    def test_shebang_caching_works(self):
        """Test that --cached flag skips recompilation on unchanged source."""
        self._skip_if_no_bash()

        cpp_content = """#!/usr/bin/env -S clang-tool-chain-build-run --cached
#include <iostream>

int main() {
    std::cout << "SHEBANG_CACHED_TEST" << std::endl;
    return 0;
}
"""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmppath = Path(tmpdir)
            cpp_file = self._create_cpp_script(tmppath, "cached.cpp", cpp_content)

            # First run - compiles
            result1 = self._run_cpp_script(cpp_file)
            self.assertEqual(result1.returncode, 0, f"First run failed: {result1.stderr}")
            self.assertIn("SHEBANG_CACHED_TEST", result1.stdout)

            # Check hash file was created
            hash_file = tmppath / "cached.hash"
            self.assertTrue(hash_file.exists(), "Hash file should be created for --cached")

            # Second run - should use cache
            result2 = self._run_cpp_script(cpp_file)
            self.assertEqual(result2.returncode, 0, f"Cached run failed: {result2.stderr}")
            self.assertIn("SHEBANG_CACHED_TEST", result2.stdout)

    def test_shebang_via_uv_run(self):
        """Test C++ execution via 'uv run' shebang (project-based)."""
        self._skip_if_no_bash()

        cpp_content = """#!/usr/bin/env -S uv run clang-tool-chain-build-run --cached
#include <iostream>

int main() {
    std::cout << "SHEBANG_UV_RUN_SUCCESS" << std::endl;
    return 0;
}
"""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmppath = Path(tmpdir)
            cpp_file = self._create_cpp_script(tmppath, "uv_test.cpp", cpp_content)

            # Must run from project root for uv to find pyproject.toml
            project_root = Path(__file__).parent.parent

            result = self._run_cpp_script(cpp_file, cwd=project_root, timeout=180)

            self.assertEqual(result.returncode, 0, f"uv run failed: {result.stderr}")
            self.assertIn("SHEBANG_UV_RUN_SUCCESS", result.stdout)


if __name__ == "__main__":
    unittest.main()
