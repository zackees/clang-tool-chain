"""
Tests to verify that Clang (not GCC) is being invoked by the wrappers.

This test suite ensures that clang-tool-chain always uses LLVM/Clang binaries
rather than falling back to GCC or MinGW gcc. It also verifies that Clang
headers take precedence over MinGW headers.
"""

import subprocess
import sys
from pathlib import Path

import pytest


class TestCompilerVerification:
    """Verify that Clang binary is used, not GCC."""

    def test_clang_binary_is_used_cpp(self) -> None:
        """Verify clang++ is invoked by clang-tool-chain-cpp (not g++)."""
        result = subprocess.run(
            ["clang-tool-chain-cpp", "--version"],
            capture_output=True,
            text=True,
            timeout=30,
        )
        assert result.returncode == 0, f"Command failed: {result.stderr}"
        output = result.stdout.lower()

        # Verify "clang" is present in version output
        assert "clang" in output, f"Expected 'clang' in version output, got: {result.stdout}"

        # Verify "gcc" is NOT present (to ensure we're not using GCC)
        assert "gcc" not in output, f"Unexpected 'gcc' in version output, got: {result.stdout}"

    def test_clang_version_output_cpp(self) -> None:
        """Verify clang-tool-chain-cpp reports Clang version (not GCC version)."""
        result = subprocess.run(
            ["clang-tool-chain-cpp", "--version"],
            capture_output=True,
            text=True,
            timeout=30,
        )
        assert result.returncode == 0, f"Command failed: {result.stderr}"

        # Check for Clang version format (e.g., "clang version 21.1.5")
        assert "clang version" in result.stdout.lower(), f"Expected 'clang version' in output, got: {result.stdout}"

    def test_clang_binary_is_used_c(self) -> None:
        """Verify clang is invoked by clang-tool-chain-c (not gcc)."""
        result = subprocess.run(
            ["clang-tool-chain-c", "--version"],
            capture_output=True,
            text=True,
            timeout=30,
        )
        assert result.returncode == 0, f"Command failed: {result.stderr}"
        output = result.stdout.lower()

        # Verify "clang" is present
        assert "clang" in output, f"Expected 'clang' in version output, got: {result.stdout}"

        # Verify "gcc" is NOT present
        assert "gcc" not in output, f"Unexpected 'gcc' in version output, got: {result.stdout}"

    @pytest.mark.skipif(sys.platform != "win32", reason="Windows-specific test (GNU ABI)")
    def test_clang_headers_not_gcc_headers_windows(self, tmp_path: Path) -> None:
        """
        Verify that Clang's standard headers are used (not GCC/MinGW headers).

        This test compiles code that would fail if GCC headers override Clang headers.
        It specifically tests that Clang's intrinsic headers take precedence.
        """
        # Write a simple test file that includes standard headers
        test_file = tmp_path / "test_headers.cpp"
        test_file.write_text("""
            #include <iostream>
            #include <cstddef>
            #include <cstdarg>

            // Use features that may differ between Clang and GCC headers
            int main() {
                std::cout << "Testing Clang headers" << std::endl;
                std::size_t size = 42;
                return size == 42 ? 0 : 1;
            }
            """)

        # Compile with verbose output to see include paths
        result = subprocess.run(
            [
                "clang-tool-chain-cpp",
                "-v",  # Verbose to see include search paths
                "-c",
                str(test_file),
                "-o",
                str(tmp_path / "test_headers.o"),
            ],
            capture_output=True,
            text=True,
            timeout=60,
        )

        # Compilation should succeed
        assert result.returncode == 0, f"Compilation failed: {result.stderr}\n{result.stdout}"

        # Check that the output includes Clang's include directories
        combined_output = result.stdout + result.stderr
        assert "clang" in combined_output.lower(), "Expected Clang include paths in verbose output"

    @pytest.mark.skipif(sys.platform != "win32", reason="Windows-specific test (GNU ABI)")
    def test_mingw_headers_still_accessible_windows(self, tmp_path: Path) -> None:
        """
        Verify that MinGW headers (windows.h, pthread.h) are still accessible.

        Even though MinGW headers have lower priority, they should still be
        available for Windows-specific functionality.
        """
        # Write a test file that uses Windows headers
        test_file = tmp_path / "test_windows.cpp"
        test_file.write_text("""
            #include <windows.h>
            #include <iostream>

            int main() {
                // Use a Windows-specific type to verify windows.h is accessible
                DWORD value = 42;
                std::cout << "Windows headers accessible: " << value << std::endl;
                return 0;
            }
            """)

        # Compile
        result = subprocess.run(
            [
                "clang-tool-chain-cpp",
                str(test_file),
                "-o",
                str(tmp_path / "test_windows.exe"),
            ],
            capture_output=True,
            text=True,
            timeout=60,
        )

        # Compilation should succeed
        assert result.returncode == 0, f"Windows headers not accessible: {result.stderr}\n{result.stdout}"
