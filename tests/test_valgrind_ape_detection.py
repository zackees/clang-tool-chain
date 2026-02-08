"""Tests for APE (Actually Portable Executable) detection in Valgrind module.

These tests verify _detect_ape_and_resolve_dbg() using temporary files,
without requiring Docker, cosmocc, or Valgrind to be installed.
"""

from pathlib import Path

import pytest

from clang_tool_chain.execution.valgrind import _detect_ape_and_resolve_dbg


class TestApeDetection:
    """Tests for _detect_ape_and_resolve_dbg()."""

    def test_non_ape_passthrough(self, tmp_path: Path) -> None:
        """Non-APE files (ELF magic) pass through unchanged."""
        exe = tmp_path / "program"
        exe.write_bytes(b"\x7fELF" + b"\x00" * 100)
        result = _detect_ape_and_resolve_dbg(exe)
        assert result == exe

    def test_com_with_com_dbg_sidecar(self, tmp_path: Path) -> None:
        """.com file with .com.dbg sidecar resolves to the sidecar."""
        com = tmp_path / "program.com"
        com.write_bytes(b"MZ" + b"\x00" * 100)
        dbg = tmp_path / "program.com.dbg"
        dbg.write_bytes(b"\x7fELF" + b"\x00" * 100)
        result = _detect_ape_and_resolve_dbg(com)
        assert result == dbg

    def test_com_with_stem_dbg_fallback(self, tmp_path: Path) -> None:
        """.com file with only stem.dbg falls back correctly."""
        com = tmp_path / "program.com"
        com.write_bytes(b"MZ" + b"\x00" * 100)
        dbg = tmp_path / "program.dbg"
        dbg.write_bytes(b"\x7fELF" + b"\x00" * 100)
        result = _detect_ape_and_resolve_dbg(com)
        assert result == dbg

    def test_mz_magic_without_com_extension(self, tmp_path: Path) -> None:
        """MZ-magic file without .com extension is detected as APE."""
        exe = tmp_path / "program"
        exe.write_bytes(b"MZ" + b"\x00" * 100)
        dbg = tmp_path / "program.dbg"
        dbg.write_bytes(b"\x7fELF" + b"\x00" * 100)
        result = _detect_ape_and_resolve_dbg(exe)
        assert result == dbg

    def test_missing_dbg_sidecar_exits(self, tmp_path: Path) -> None:
        """Missing .dbg sidecar causes sys.exit(1)."""
        com = tmp_path / "program.com"
        com.write_bytes(b"MZ" + b"\x00" * 100)
        with pytest.raises(SystemExit) as exc_info:
            _detect_ape_and_resolve_dbg(com)
        assert exc_info.value.code == 1

    def test_prefers_com_dbg_over_stem_dbg(self, tmp_path: Path) -> None:
        """When both .com.dbg and stem.dbg exist, prefers .com.dbg."""
        com = tmp_path / "program.com"
        com.write_bytes(b"MZ" + b"\x00" * 100)
        com_dbg = tmp_path / "program.com.dbg"
        com_dbg.write_bytes(b"\x7fELF" + b"\x00" * 100)
        stem_dbg = tmp_path / "program.dbg"
        stem_dbg.write_bytes(b"\x7fELF" + b"\x00" * 100)
        result = _detect_ape_and_resolve_dbg(com)
        assert result == com_dbg

    def test_empty_file_not_ape(self, tmp_path: Path) -> None:
        """Empty or too-small file is not detected as APE."""
        exe = tmp_path / "tiny"
        exe.write_bytes(b"")
        result = _detect_ape_and_resolve_dbg(exe)
        assert result == exe

    def test_one_byte_file_not_ape(self, tmp_path: Path) -> None:
        """Single-byte file is not detected as APE."""
        exe = tmp_path / "onebyte"
        exe.write_bytes(b"M")
        result = _detect_ape_and_resolve_dbg(exe)
        assert result == exe
