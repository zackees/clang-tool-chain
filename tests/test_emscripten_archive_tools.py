"""
Tests for the emar / emstrip / emranlib / emnm console-script wrappers
added in 1.5.0 (closes issue #23).

Verifies:
  - All eight entry-point names install and import.
  - Each runs `--version` end-to-end (proves dispatch into the bundled
    emscripten Python tools works, including the `tools/` fallback for emnm).
  - The lightweight ``execute_emscripten_archive_tool`` helper rejects
    non-archive tool names.
"""

from __future__ import annotations

import shutil
import subprocess

import pytest

_ARCHIVE_TOOL_NAMES = ("emar", "emstrip", "emranlib", "emnm")
_ALL_ENTRY_POINTS = tuple(f"{prefix}{name}" for prefix in ("clang-tool-chain-", "ctc-") for name in _ARCHIVE_TOOL_NAMES)


def _is_emscripten_available() -> bool:
    """Mirrors test_emscripten.is_emscripten_available — skip when no archive exists."""
    try:
        from clang_tool_chain.downloader import fetch_emscripten_platform_manifest
        from clang_tool_chain.wrapper import get_platform_info

        platform, arch = get_platform_info()
        manifest = fetch_emscripten_platform_manifest(platform, arch)
        if not manifest.latest or manifest.latest == "PENDING":
            return False
        return manifest.latest in manifest.versions
    except Exception:
        return False


def test_all_main_functions_importable() -> None:
    """All eight new ``*_main`` entry-point functions must import cleanly."""
    from clang_tool_chain.wrapper import (
        ctc_emar_main,
        ctc_emnm_main,
        ctc_emranlib_main,
        ctc_emstrip_main,
        emar_main,
        emnm_main,
        emranlib_main,
        emstrip_main,
    )

    for fn in (
        emar_main,
        emstrip_main,
        emranlib_main,
        emnm_main,
        ctc_emar_main,
        ctc_emstrip_main,
        ctc_emranlib_main,
        ctc_emnm_main,
    ):
        assert callable(fn), fn


def test_archive_tool_helper_rejects_non_archive_tools() -> None:
    """Sanity-check the narrow input contract on the lightweight helper."""
    from clang_tool_chain.execution.emscripten import execute_emscripten_archive_tool

    with pytest.raises(ValueError, match="emar"):
        execute_emscripten_archive_tool("emcc")


@pytest.mark.serial
@pytest.mark.skipif(not _is_emscripten_available(), reason="Emscripten binaries not available for this platform")
@pytest.mark.parametrize("entry_point", _ALL_ENTRY_POINTS)
def test_entry_point_dispatches_to_emscripten(entry_point: str) -> None:
    """Each installed console script must dispatch into the bundled tool.

    We invoke ``--version`` which is supported by every underlying llvm-*
    tool and exits 0. This proves both that the entry point is registered
    AND that find_emscripten_tool can resolve the .py script (including the
    tools/ subdir fallback added for emnm).
    """
    binary = shutil.which(entry_point)
    assert binary is not None, f"{entry_point} not installed (re-run uv pip install -e .)"

    result = subprocess.run([binary, "--version"], capture_output=True, text=True, timeout=60)
    assert result.returncode == 0, (
        f"{entry_point} --version failed (rc={result.returncode})\nstdout: {result.stdout!r}\nstderr: {result.stderr!r}"
    )
    # All llvm-* tools print their own name in the version banner; loose check
    # rather than asserting a specific banner string (varies across LLVM versions).
    assert "LLVM" in result.stdout or "llvm" in result.stdout.lower(), result.stdout
