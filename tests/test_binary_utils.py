"""
Test LLVM binary utilities (llvm-ar, llvm-nm, llvm-objdump, etc.).

These tests verify that the LLVM binary utilities are properly installed
and functional across all platforms.
"""

import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import pytest

from clang_tool_chain.downloader import ToolchainInfrastructureError


class TestLLVMBinaryUtilsVersion(unittest.TestCase):
    """Test that LLVM binary utilities are installed and report versions."""

    def test_llvm_ar_installed(self) -> None:
        """Test that llvm-ar is installed and accessible."""
        try:
            result = subprocess.run(
                ["clang-tool-chain-ar", "--version"],
                capture_output=True,
                text=True,
                timeout=10,
            )

            # Should succeed
            self.assertEqual(result.returncode, 0, f"llvm-ar --version failed: {result.stderr}")

            # Check for version info
            combined_output = (result.stdout + result.stderr).lower()
            self.assertTrue(
                "llvm" in combined_output or "version" in combined_output,
                "llvm-ar should report version",
            )
        except FileNotFoundError:
            self.fail("clang-tool-chain-ar command not found")
        except ToolchainInfrastructureError:
            raise

    def test_llvm_nm_installed(self) -> None:
        """Test that llvm-nm is installed and accessible."""
        try:
            result = subprocess.run(
                ["clang-tool-chain-nm", "--version"],
                capture_output=True,
                text=True,
                timeout=10,
            )

            # Should succeed
            self.assertEqual(result.returncode, 0, f"llvm-nm --version failed: {result.stderr}")

            # Check for version info
            combined_output = (result.stdout + result.stderr).lower()
            self.assertTrue(
                "llvm" in combined_output or "version" in combined_output,
                "llvm-nm should report version",
            )
        except FileNotFoundError:
            self.fail("clang-tool-chain-nm command not found")
        except ToolchainInfrastructureError:
            raise

    def test_llvm_objdump_installed(self) -> None:
        """Test that llvm-objdump is installed and accessible."""
        try:
            result = subprocess.run(
                ["clang-tool-chain-objdump", "--version"],
                capture_output=True,
                text=True,
                timeout=10,
            )

            # Should succeed
            self.assertEqual(result.returncode, 0, f"llvm-objdump --version failed: {result.stderr}")

            # Check for version info
            combined_output = (result.stdout + result.stderr).lower()
            self.assertTrue(
                "llvm" in combined_output or "version" in combined_output,
                "llvm-objdump should report version",
            )
        except FileNotFoundError:
            self.fail("clang-tool-chain-objdump command not found")
        except ToolchainInfrastructureError:
            raise

    def test_llvm_strip_installed(self) -> None:
        """Test that llvm-strip is installed and accessible."""
        try:
            result = subprocess.run(
                ["clang-tool-chain-strip", "--version"],
                capture_output=True,
                text=True,
                timeout=10,
            )

            # Should succeed
            self.assertEqual(result.returncode, 0, f"llvm-strip --version failed: {result.stderr}")

            # Check for version info
            combined_output = (result.stdout + result.stderr).lower()
            self.assertTrue(
                "llvm" in combined_output or "version" in combined_output,
                "llvm-strip should report version",
            )
        except FileNotFoundError:
            self.fail("clang-tool-chain-strip command not found")
        except ToolchainInfrastructureError:
            raise

    def test_llvm_readelf_installed(self) -> None:
        """Test that llvm-readelf is installed and accessible."""
        try:
            result = subprocess.run(
                ["clang-tool-chain-readelf", "--version"],
                capture_output=True,
                text=True,
                timeout=10,
            )

            # Should succeed or return 1
            self.assertIn(
                result.returncode,
                [0, 1],
                f"llvm-readelf --version should complete. Return code: {result.returncode}",
            )
        except FileNotFoundError:
            self.fail("clang-tool-chain-readelf command not found")
        except ToolchainInfrastructureError:
            raise

    def test_llvm_objcopy_installed(self) -> None:
        """Test that llvm-objcopy is installed and accessible."""
        try:
            result = subprocess.run(
                ["clang-tool-chain-objcopy", "--version"],
                capture_output=True,
                text=True,
                timeout=10,
            )

            # Should succeed
            self.assertEqual(result.returncode, 0, f"llvm-objcopy --version failed: {result.stderr}")

            # Check for version info
            combined_output = (result.stdout + result.stderr).lower()
            self.assertTrue(
                "llvm" in combined_output or "version" in combined_output,
                "llvm-objcopy should report version",
            )
        except FileNotFoundError:
            self.fail("clang-tool-chain-objcopy command not found")
        except ToolchainInfrastructureError:
            raise

    def test_llvm_ranlib_installed(self) -> None:
        """Test that llvm-ranlib is installed and accessible."""
        try:
            result = subprocess.run(
                ["clang-tool-chain-ranlib", "--version"],
                capture_output=True,
                text=True,
                timeout=10,
            )

            # Should succeed
            self.assertEqual(result.returncode, 0, f"llvm-ranlib --version failed: {result.stderr}")

            # Check for version info
            combined_output = (result.stdout + result.stderr).lower()
            self.assertTrue(
                "llvm" in combined_output or "version" in combined_output,
                "llvm-ranlib should report version",
            )
        except FileNotFoundError:
            self.fail("clang-tool-chain-ranlib command not found")
        except ToolchainInfrastructureError:
            raise


@pytest.mark.serial
class TestLLVMBinaryUtilsFunctionality(unittest.TestCase):
    """Test LLVM binary utilities functionality with real binaries."""

    def setUp(self) -> None:
        """Set up test environment with temporary directory and test files."""
        self.temp_dir = tempfile.mkdtemp()
        self.temp_path = Path(self.temp_dir)
        self.original_dir = os.getcwd()
        os.chdir(self.temp_dir)

        # Create a test C file
        self.test_c = self.temp_path / "test.c"
        self.test_c.write_text(
            """
#include <stdio.h>

int global_var = 42;

int add(int a, int b) {
    return a + b;
}

int main() {
    printf("Result: %d\\n", add(5, 7));
    return 0;
}
"""
        )

        # Compile to object file
        result = subprocess.run(
            ["clang-tool-chain-c", "-c", str(self.test_c), "-o", "test.o"],
            capture_output=True,
            text=True,
            timeout=30,
        )

        if result.returncode != 0:
            raise RuntimeError(f"Failed to compile test file: {result.stderr}")

        self.test_obj = self.temp_path / "test.o"

    def tearDown(self) -> None:
        """Clean up temporary directory."""
        os.chdir(self.original_dir)
        import shutil

        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_llvm_ar_create_archive(self) -> None:
        """Test creating a static library with llvm-ar."""
        try:
            archive_file = self.temp_path / "libtest.a"

            # Create archive
            result = subprocess.run(
                ["clang-tool-chain-ar", "rcs", str(archive_file), str(self.test_obj)],
                capture_output=True,
                text=True,
                timeout=30,
            )

            # Should succeed
            self.assertEqual(result.returncode, 0, f"llvm-ar rcs failed: {result.stderr}")

            # Archive should be created
            self.assertTrue(archive_file.exists(), "Archive file should be created")
            self.assertGreater(archive_file.stat().st_size, 0, "Archive should not be empty")

        except ToolchainInfrastructureError:
            raise

    def test_llvm_nm_symbols(self) -> None:
        """Test listing symbols with llvm-nm."""
        try:
            # Run llvm-nm on object file
            result = subprocess.run(
                ["clang-tool-chain-nm", str(self.test_obj)],
                capture_output=True,
                text=True,
                timeout=30,
            )

            # Should succeed
            self.assertEqual(result.returncode, 0, f"llvm-nm failed: {result.stderr}")

            # Should produce output with symbols
            self.assertGreater(len(result.stdout), 0, "llvm-nm should produce output")

            # Should list function symbols (add, main)
            # Note: mangling and format may vary by platform
            combined_output = result.stdout.lower()
            self.assertTrue(
                "add" in combined_output or "main" in combined_output,
                "llvm-nm should list function symbols",
            )

        except ToolchainInfrastructureError:
            raise

    def test_llvm_objdump_disassemble(self) -> None:
        """Test disassembly with llvm-objdump."""
        try:
            # Run llvm-objdump with disassembly
            result = subprocess.run(
                ["clang-tool-chain-objdump", "-d", str(self.test_obj)],
                capture_output=True,
                text=True,
                timeout=30,
            )

            # Should succeed
            self.assertEqual(result.returncode, 0, f"llvm-objdump -d failed: {result.stderr}")

            # Should produce output
            self.assertGreater(len(result.stdout), 0, "llvm-objdump should produce output")

            # Should contain disassembly
            combined_output = result.stdout.lower()
            self.assertTrue(
                "disassembly" in combined_output or "main" in combined_output or "add" in combined_output,
                "llvm-objdump should produce disassembly",
            )

        except ToolchainInfrastructureError:
            raise

    def test_llvm_strip_binary(self) -> None:
        """Test stripping symbols with llvm-strip."""
        try:
            # Compile with debug symbols
            debug_exe = self.temp_path / ("test_debug.exe" if sys.platform.startswith("win") else "test_debug")
            result = subprocess.run(
                ["clang-tool-chain-c", str(self.test_c), "-g", "-o", str(debug_exe)],
                capture_output=True,
                text=True,
                timeout=30,
            )

            self.assertEqual(result.returncode, 0, f"Compilation with -g failed: {result.stderr}")

            # Get original size
            original_size = debug_exe.stat().st_size

            # Strip symbols
            stripped_exe = self.temp_path / ("test_stripped.exe" if sys.platform.startswith("win") else "test_stripped")
            result = subprocess.run(
                ["clang-tool-chain-strip", str(debug_exe), "-o", str(stripped_exe)],
                capture_output=True,
                text=True,
                timeout=30,
            )

            # Should succeed
            self.assertEqual(result.returncode, 0, f"llvm-strip failed: {result.stderr}")

            # Stripped binary should exist
            self.assertTrue(stripped_exe.exists(), "Stripped binary should be created")

            # Stripped binary should be smaller or same size
            stripped_size = stripped_exe.stat().st_size
            self.assertLessEqual(
                stripped_size,
                original_size,
                "Stripped binary should be smaller or equal to original",
            )

        except ToolchainInfrastructureError:
            raise

    @pytest.mark.skipif(sys.platform.startswith("win"), reason="readelf primarily for ELF (Linux/macOS)")
    def test_llvm_readelf_headers(self) -> None:
        """Test reading ELF headers (non-Windows platforms)."""
        try:
            # Run llvm-readelf on object file
            result = subprocess.run(
                ["clang-tool-chain-readelf", "-h", str(self.test_obj)],
                capture_output=True,
                text=True,
                timeout=30,
            )

            # Should succeed
            self.assertEqual(result.returncode, 0, f"llvm-readelf -h failed: {result.stderr}")

            # Should produce output
            self.assertGreater(len(result.stdout), 0, "llvm-readelf should produce output")

            # Should contain ELF header information
            combined_output = result.stdout.lower()
            self.assertTrue(
                "elf" in combined_output or "header" in combined_output or "class" in combined_output,
                "llvm-readelf should show ELF header information",
            )

        except ToolchainInfrastructureError:
            raise

    def test_llvm_objcopy_section_manipulation(self) -> None:
        """Test section manipulation with llvm-objcopy."""
        try:
            # Copy object file with llvm-objcopy
            copied_obj = self.temp_path / "test_copied.o"
            result = subprocess.run(
                ["clang-tool-chain-objcopy", str(self.test_obj), str(copied_obj)],
                capture_output=True,
                text=True,
                timeout=30,
            )

            # Should succeed
            self.assertEqual(result.returncode, 0, f"llvm-objcopy failed: {result.stderr}")

            # Copied file should exist
            self.assertTrue(copied_obj.exists(), "Copied object file should be created")

        except ToolchainInfrastructureError:
            raise

    def test_llvm_ranlib_archive_indexing(self) -> None:
        """Test archive indexing with llvm-ranlib."""
        try:
            # Create archive first
            archive_file = self.temp_path / "libtest_ranlib.a"
            result = subprocess.run(
                ["clang-tool-chain-ar", "rcs", str(archive_file), str(self.test_obj)],
                capture_output=True,
                text=True,
                timeout=30,
            )

            self.assertEqual(result.returncode, 0, f"llvm-ar rcs failed: {result.stderr}")

            # Run llvm-ranlib on archive
            result = subprocess.run(
                ["clang-tool-chain-ranlib", str(archive_file)],
                capture_output=True,
                text=True,
                timeout=30,
            )

            # Should succeed
            self.assertEqual(result.returncode, 0, f"llvm-ranlib failed: {result.stderr}")

        except ToolchainInfrastructureError:
            raise


if __name__ == "__main__":
    unittest.main()
