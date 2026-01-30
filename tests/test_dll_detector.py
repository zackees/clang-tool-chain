"""
Unit tests for DLL detection strategies.

Tests the Strategy pattern implementation for DLL detection including
ObjdumpDLLDetector, HeuristicDLLDetector, and TransitiveDependencyScanner.
"""

import sys
import tempfile
from pathlib import Path

# Handle imports based on platform
# Import for type checking on all platforms, but only use at runtime on Windows
from typing import TYPE_CHECKING
from unittest.mock import MagicMock, patch

import pytest

if TYPE_CHECKING or sys.platform == "win32":
    from clang_tool_chain.deployment.dll_detector import (
        DLLDetector,
        HeuristicDLLDetector,
        ObjdumpDLLDetector,
        TransitiveDependencyScanner,
    )


@pytest.mark.skipif(sys.platform != "win32", reason="Windows-only test")
class TestDLLDetector:
    """Test suite for DLL detection strategies."""

    def test_dll_detector_is_abstract(self):
        """Test that DLLDetector cannot be instantiated directly."""
        with pytest.raises(TypeError):
            DLLDetector()  # type: ignore

    def test_heuristic_detector_default_list(self):
        """Test HeuristicDLLDetector with default DLL list."""
        with tempfile.NamedTemporaryFile(suffix=".exe", delete=False) as tmp:
            tmp.write(b"fake exe")
            tmp_path = Path(tmp.name)

        try:
            detector = HeuristicDLLDetector()
            result = detector.detect(tmp_path)

            # Should return default MinGW DLLs
            assert "libwinpthread-1.dll" in result
            assert "libgcc_s_seh-1.dll" in result
            assert "libstdc++-6.dll" in result
            assert len(result) == 3
        finally:
            tmp_path.unlink()

    def test_heuristic_detector_custom_list(self):
        """Test HeuristicDLLDetector with custom DLL list."""
        with tempfile.NamedTemporaryFile(suffix=".exe", delete=False) as tmp:
            tmp.write(b"fake exe")
            tmp_path = Path(tmp.name)

        try:
            custom_dlls = ["custom1.dll", "custom2.dll"]
            detector = HeuristicDLLDetector(dll_list=custom_dlls)
            result = detector.detect(tmp_path)

            assert result == custom_dlls
            assert len(result) == 2
        finally:
            tmp_path.unlink()

    def test_heuristic_detector_nonexistent_file(self):
        """Test HeuristicDLLDetector raises FileNotFoundError for nonexistent file."""
        detector = HeuristicDLLDetector()
        with pytest.raises(FileNotFoundError):
            detector.detect(Path("nonexistent.exe"))

    def test_objdump_detector_missing_objdump(self):
        """Test ObjdumpDLLDetector raises RuntimeError if objdump not found."""
        with tempfile.NamedTemporaryFile(suffix=".exe", delete=False) as tmp:
            tmp.write(b"fake exe")
            tmp_path = Path(tmp.name)

        try:
            detector = ObjdumpDLLDetector(objdump_path=Path("nonexistent-objdump.exe"))
            with pytest.raises(RuntimeError, match="llvm-objdump not found"):
                detector.detect(tmp_path)
        finally:
            tmp_path.unlink()

    def test_objdump_detector_nonexistent_binary(self):
        """Test ObjdumpDLLDetector raises FileNotFoundError for nonexistent binary."""
        objdump_path = Path("llvm-objdump.exe")  # Path doesn't matter, won't be called
        detector = ObjdumpDLLDetector(objdump_path=objdump_path)

        with pytest.raises(FileNotFoundError):
            detector.detect(Path("nonexistent.exe"))

    @patch("subprocess.run")
    def test_objdump_detector_success(self, mock_run):
        """Test ObjdumpDLLDetector successfully extracts DLLs."""
        with tempfile.NamedTemporaryFile(suffix=".exe", delete=False) as tmp:
            tmp.write(b"fake exe")
            tmp_path = Path(tmp.name)

        with tempfile.NamedTemporaryFile(suffix=".exe", delete=False) as objdump_tmp:
            objdump_tmp.write(b"fake objdump")
            objdump_path = Path(objdump_tmp.name)

        try:
            # Mock llvm-objdump output
            mock_result = MagicMock()
            mock_result.returncode = 0
            mock_result.stdout = """
            DLL Name: kernel32.dll
            DLL Name: libwinpthread-1.dll
            DLL Name: libgcc_s_seh-1.dll
            DLL Name: msvcrt.dll
            """
            mock_run.return_value = mock_result

            # Create detector with filter function
            def is_mingw_dll(dll_name):
                return dll_name.startswith("lib")

            detector = ObjdumpDLLDetector(objdump_path=objdump_path, dll_filter_func=is_mingw_dll)
            result = detector.detect(tmp_path)

            # Should only return filtered DLLs
            assert "libwinpthread-1.dll" in result
            assert "libgcc_s_seh-1.dll" in result
            assert "kernel32.dll" not in result
            assert "msvcrt.dll" not in result
            assert len(result) == 2
        finally:
            tmp_path.unlink()
            objdump_path.unlink()

    @patch("subprocess.run")
    def test_objdump_detector_timeout(self, mock_run):
        """Test ObjdumpDLLDetector handles timeout."""
        import subprocess

        with tempfile.NamedTemporaryFile(suffix=".exe", delete=False) as tmp:
            tmp.write(b"fake exe")
            tmp_path = Path(tmp.name)

        with tempfile.NamedTemporaryFile(suffix=".exe", delete=False) as objdump_tmp:
            objdump_tmp.write(b"fake objdump")
            objdump_path = Path(objdump_tmp.name)

        try:
            mock_run.side_effect = subprocess.TimeoutExpired(cmd="llvm-objdump", timeout=10)
            detector = ObjdumpDLLDetector(objdump_path=objdump_path)

            with pytest.raises(RuntimeError, match="timed out"):
                detector.detect(tmp_path)
        finally:
            tmp_path.unlink()
            objdump_path.unlink()

    @patch("subprocess.run")
    def test_transitive_dependency_scanner(self, mock_run):
        """Test TransitiveDependencyScanner finds transitive dependencies."""
        with tempfile.NamedTemporaryFile(suffix=".exe", delete=False) as objdump_tmp:
            objdump_tmp.write(b"fake objdump")
            objdump_path = Path(objdump_tmp.name)

        try:
            # Mock DLL locator function
            dll_locations = {
                "liba.dll": Path("C:/toolchain/liba.dll"),
                "libb.dll": Path("C:/toolchain/libb.dll"),
                "libc.dll": Path("C:/toolchain/libc.dll"),
            }

            def dll_locator(dll_name):
                return dll_locations.get(dll_name)

            # Mock objdump outputs for each DLL
            def mock_run_side_effect(*args, **kwargs):
                binary_path = args[0][2]  # Get path from command line

                mock_result = MagicMock()
                mock_result.returncode = 0

                if "liba.dll" in str(binary_path):
                    # liba.dll depends on libb.dll
                    mock_result.stdout = "DLL Name: libb.dll\nDLL Name: kernel32.dll"
                elif "libb.dll" in str(binary_path):
                    # libb.dll depends on libc.dll
                    mock_result.stdout = "DLL Name: libc.dll\nDLL Name: msvcrt.dll"
                elif "libc.dll" in str(binary_path):
                    # libc.dll has no MinGW dependencies
                    mock_result.stdout = "DLL Name: kernel32.dll"
                else:
                    mock_result.stdout = ""

                return mock_result

            mock_run.side_effect = mock_run_side_effect

            # Create scanner with filter
            def is_lib_dll(dll_name):
                return dll_name.startswith("lib")

            scanner = TransitiveDependencyScanner(dll_locator, objdump_path, dll_filter_func=is_lib_dll)

            # Scan starting from liba.dll
            result = scanner.scan_transitive_dependencies(["liba.dll"])

            # Should find liba.dll -> libb.dll -> libc.dll
            assert "liba.dll" in result
            assert "libb.dll" in result
            assert "libc.dll" in result
            assert "kernel32.dll" not in result
            assert "msvcrt.dll" not in result
            assert len(result) == 3
        finally:
            objdump_path.unlink()

    def test_transitive_scanner_missing_dll(self):
        """Test TransitiveDependencyScanner handles missing DLLs gracefully."""
        with tempfile.NamedTemporaryFile(suffix=".exe", delete=False) as objdump_tmp:
            objdump_tmp.write(b"fake objdump")
            objdump_path = Path(objdump_tmp.name)

        try:
            # DLL locator that always returns None
            def dll_locator(dll_name):
                return None

            scanner = TransitiveDependencyScanner(dll_locator, objdump_path)
            result = scanner.scan_transitive_dependencies(["missing.dll"])

            # Should return the input DLL even if not found
            assert "missing.dll" in result
            assert len(result) == 1
        finally:
            objdump_path.unlink()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
