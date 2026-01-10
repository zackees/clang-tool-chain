"""
Integration test for sccache wrapper with thin archives on Windows.

This test verifies that clang-tool-chain-sccache-cpp correctly uses ld.lld
instead of MSVC's link.exe, which is critical for thin archive support.

Background:
- LLVM thin archives store file paths instead of embedded object files
- MSVC's link.exe cannot read thin archives (error LNK1136)
- LLVM's ld.lld CAN read thin archives
- The sccache wrapper must inject GNU ABI arguments to force ld.lld usage
"""

import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import pytest


@pytest.mark.serial
@pytest.mark.skipif(sys.platform != "win32", reason="Windows-specific test for MSVC vs lld")
class TestSccacheThinArchiveWindows(unittest.TestCase):
    """Test that sccache wrapper uses ld.lld and supports thin archives on Windows.

    Note: Marked as serial because sccache tests can experience resource contention
    when run in parallel with other compilation tests, leading to timeouts.
    """

    @classmethod
    def setUpClass(cls):
        """Pre-install sccache once for all tests to avoid timeout during individual tests."""
        # Check if sccache is already installed in PATH
        import shutil

        if shutil.which("sccache") is None:
            # Try to pre-install sccache via iso-env by calling sccache --version
            # This will trigger the iso-env installation on first use
            # Use a longer timeout for this one-time setup
            try:
                result = subprocess.run(
                    ["clang-tool-chain-sccache-cpp", "--help"],
                    capture_output=True,
                    text=True,
                    timeout=180,  # 3 minutes for initial download/setup
                )
                if result.returncode != 0:
                    print(f"Warning: sccache pre-installation failed: {result.stderr}", file=sys.stderr)
            except subprocess.TimeoutExpired:
                print("Warning: sccache pre-installation timed out", file=sys.stderr)
            except Exception as e:
                print(f"Warning: sccache pre-installation error: {e}", file=sys.stderr)

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

    def test_sccache_uses_lld_not_msvc_linker(self):
        """
        Verify that clang-tool-chain-sccache-cpp uses ld.lld instead of MSVC's link.exe.

        This is critical because:
        1. Without GNU ABI args, clang auto-detects MSVC and uses link.exe
        2. link.exe cannot read LLVM thin archives
        3. The fix adds GNU ABI injection to force ld.lld usage
        """
        # Create a simple test program
        test_cpp = self.temp_path / "test_linker.cpp"
        test_cpp.write_text(
            """
#include <iostream>
int main() {
    std::cout << "Testing linker selection" << std::endl;
    return 0;
}
"""
        )

        # Compile with verbose output to see which linker is used
        result = subprocess.run(
            ["clang-tool-chain-sccache-cpp", str(test_cpp), "-o", "test_linker.exe", "-v"],
            capture_output=True,
            text=True,
            timeout=10,
        )

        # Verify compilation succeeded
        self.assertEqual(result.returncode, 0, f"Compilation failed\nStderr: {result.stderr}")

        # Verify ld.lld was used (not link.exe)
        stderr_lower = result.stderr.lower()
        self.assertIn("ld.lld", stderr_lower, "Should use LLVM's ld.lld linker")
        self.assertNotIn("link.exe", stderr_lower, "Should NOT use MSVC's link.exe")
        self.assertNotIn("microsoft visual studio", stderr_lower, "Should NOT use MSVC toolchain paths")

        # Verify GNU ABI target was used (shown in verbose output as "Target:" or triple)
        # The --target flag is passed internally but may not appear in -v output from sccache
        self.assertIn("x86_64-w64-windows-gnu", result.stderr, "Should use GNU ABI target (x86_64-w64-windows-gnu)")
        # Note: "default target x86_64-pc-windows-msvc" just shows what clang was built with
        # The actual target used is shown in "Target:" line and "-triple" argument

        # Verify executable runs
        exe_result = subprocess.run(["./test_linker.exe"], capture_output=True, text=True, timeout=5)
        self.assertEqual(exe_result.returncode, 0, "Executable should run successfully")
        self.assertIn("Testing linker selection", exe_result.stdout)

    def test_sccache_thin_archive_linking(self):
        """
        Test complete thin archive workflow with sccache wrapper.

        This verifies:
        1. Compilation with sccache works
        2. Thin archive creation works
        3. Linking against thin archive works (requires ld.lld, not link.exe)
        4. Final executable runs correctly
        """
        # Create library source
        lib_cpp = self.temp_path / "mathlib.cpp"
        lib_cpp.write_text(
            """
int add(int a, int b) { return a + b; }
int multiply(int a, int b) { return a * b; }
int subtract(int a, int b) { return a - b; }
"""
        )

        # Create main program
        main_cpp = self.temp_path / "main.cpp"
        main_cpp.write_text(
            """
#include <iostream>
extern int add(int, int);
extern int multiply(int, int);
extern int subtract(int, int);

int main() {
    int sum = add(10, 5);           // 15
    int product = multiply(4, 3);   // 12
    int diff = subtract(20, 8);     // 12
    int result = sum + product - diff;  // 15 + 12 - 12 = 15
    std::cout << "Result: " << result << std::endl;
    return result;
}
"""
        )

        # Step 1: Compile library with sccache
        compile_result = subprocess.run(
            ["clang-tool-chain-sccache-cpp", "-c", str(lib_cpp), "-o", "mathlib.o"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        self.assertEqual(compile_result.returncode, 0, f"Library compilation failed\n{compile_result.stderr}")
        self.assertTrue((self.temp_path / "mathlib.o").exists(), "Object file should be created")

        # Step 2: Create thin archive using LLVM ar
        # The 'T' flag creates a thin archive (stores paths instead of embedding objects)
        archive_result = subprocess.run(
            ["clang-tool-chain-ar", "rcsT", "libmath_thin.a", "mathlib.o"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        self.assertEqual(archive_result.returncode, 0, f"Archive creation failed\n{archive_result.stderr}")

        # Verify it's actually a thin archive
        archive_file = self.temp_path / "libmath_thin.a"
        self.assertTrue(archive_file.exists(), "Archive file should be created")

        # Use 'file' command if available to verify thin archive format
        try:
            file_result = subprocess.run(
                ["file", str(archive_file)], capture_output=True, text=True, timeout=5, check=False
            )
            if file_result.returncode == 0:
                self.assertIn("thin archive", file_result.stdout.lower(), "Should be a thin archive")
        except FileNotFoundError:
            # 'file' command not available on Windows, skip verification
            pass

        # Step 3: Link main program with thin archive using sccache
        # This is the critical test - link.exe would fail here with LNK1136
        link_result = subprocess.run(
            ["clang-tool-chain-sccache-cpp", str(main_cpp), "libmath_thin.a", "-o", "test_thin.exe"],
            capture_output=True,
            text=True,
            timeout=10,
        )

        # Verify linking succeeded (would fail with link.exe)
        self.assertEqual(
            link_result.returncode,
            0,
            f"Linking with thin archive failed (MSVC link.exe?)\nStderr: {link_result.stderr}",
        )
        self.assertTrue((self.temp_path / "test_thin.exe").exists(), "Executable should be created")

        # Verify no MSVC linker errors
        self.assertNotIn("LNK1136", link_result.stderr, "Should not get MSVC thin archive error")
        self.assertNotIn("fatal error LNK", link_result.stderr, "Should not get any MSVC linker errors")

        # Step 4: Run the executable
        exe_result = subprocess.run(["./test_thin.exe"], capture_output=True, text=True, timeout=5)

        # Verify execution
        self.assertEqual(
            exe_result.returncode, 15, "Exit code should be 15 (add(10,5) + multiply(4,3) - subtract(20,8))"
        )
        self.assertIn("Result: 15", exe_result.stdout, "Output should show correct calculation")

    def test_sccache_regular_archive_comparison(self):
        """
        Compare thin archive vs regular (fat) archive to ensure both work.

        This validates that:
        - Regular archives work (baseline)
        - Thin archives also work (regression test for the bug fix)
        """
        # Create library source
        lib_cpp = self.temp_path / "lib.cpp"
        lib_cpp.write_text("int get_value() { return 42; }")

        # Create main program
        main_cpp = self.temp_path / "main.cpp"
        main_cpp.write_text(
            """
extern int get_value();
int main() { return get_value(); }
"""
        )

        # Compile library
        subprocess.run(
            ["clang-tool-chain-sccache-cpp", "-c", str(lib_cpp), "-o", "lib.o"],
            check=True,
            timeout=10,
        )

        # Test 1: Regular (fat) archive
        subprocess.run(["clang-tool-chain-ar", "rcs", "libfat.a", "lib.o"], check=True, timeout=10)
        subprocess.run(
            ["clang-tool-chain-sccache-cpp", str(main_cpp), "libfat.a", "-o", "test_fat.exe"],
            check=True,
            timeout=10,
        )
        fat_result = subprocess.run(["./test_fat.exe"], capture_output=True, timeout=5)
        self.assertEqual(fat_result.returncode, 42, "Fat archive should work")

        # Test 2: Thin archive
        subprocess.run(["clang-tool-chain-ar", "rcsT", "libthin.a", "lib.o"], check=True, timeout=10)
        subprocess.run(
            ["clang-tool-chain-sccache-cpp", str(main_cpp), "libthin.a", "-o", "test_thin.exe"],
            check=True,
            timeout=10,
        )
        thin_result = subprocess.run(["./test_thin.exe"], capture_output=True, timeout=5)
        self.assertEqual(thin_result.returncode, 42, "Thin archive should work (was broken before fix)")

        # Both should produce the same result
        self.assertEqual(
            fat_result.returncode,
            thin_result.returncode,
            "Fat and thin archives should produce identical results",
        )


if __name__ == "__main__":
    unittest.main()
