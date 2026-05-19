"""
Regression tests for issue #29: ``clang-tool-chain-em-cpp`` / ``-emcc`` /
``-zccache-em-cpp`` / ``-zccache-emcc`` failing on Windows with "%1 is not a
valid Win32 application" because the baked profile pointed at ``.py`` paths
that ``CreateProcess`` can't exec directly.

Three regressions are covered:

1. ``profile.py`` bakes ``.bat`` paths for emcc/em++ on Windows.
2. ``zccache_shim._resolve_tool_path`` rewrites stale ``.py`` paths from
   pre-1.5.2 profiles to the sibling ``.bat`` at exec time.
3. ``exec_via_zccache`` sets ``EM_CONFIG`` / ``EMSCRIPTEN`` env and skips
   host-ABI flag injection for emcc/em++/wasm-ld (those are wasm-targeted).
"""

from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

IS_WINDOWS = sys.platform == "win32"


def _is_emscripten_available() -> bool:
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


# ---- Unit-level: shim path rewrite ----------------------------------------


@pytest.mark.skipif(not IS_WINDOWS, reason="The .py → .bat rewrite only fires on Windows")
def test_resolve_rewrites_py_to_bat(tmp_path: Path) -> None:
    """A profile baked at 1.5.0 / 1.5.1 had .py paths. The shim must rewrite
    to the sibling .bat at exec time so existing installs keep working."""
    from clang_tool_chain.profile import Profile
    from clang_tool_chain.zccache_shim import _resolve_tool_path

    # Materialise a fake emscripten layout
    em_dir = tmp_path / "emscripten"
    em_dir.mkdir()
    py = em_dir / "em++.py"
    bat = em_dir / "em++.bat"
    py.write_text("# fake .py\n")
    bat.write_text("@echo off\necho fake bat\n")

    profile = Profile(binaries={"em++": str(py)})

    resolved = _resolve_tool_path(profile, "em++")
    assert resolved.lower().endswith(".bat"), f"expected .bat rewrite, got {resolved}"
    assert Path(resolved).name == "em++.bat"


@pytest.mark.skipif(not IS_WINDOWS, reason="Windows-only path")
def test_resolve_py_without_bat_fallback_errors_cleanly(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """If a .py is baked but no sibling .bat exists, fail loudly rather than
    letting zccache die with the cryptic 'not a valid Win32 application'."""
    from clang_tool_chain.profile import Profile
    from clang_tool_chain.zccache_shim import _resolve_tool_path

    em_dir = tmp_path / "emscripten"
    em_dir.mkdir()
    py = em_dir / "em++.py"
    py.write_text("# fake .py\n")

    profile = Profile(binaries={"em++": str(py)})

    with pytest.raises(SystemExit) as exc_info:
        _resolve_tool_path(profile, "em++")
    assert exc_info.value.code == 1
    err = capsys.readouterr().err
    assert "Windows cannot exec a .py file directly" in err
    assert "em++.bat" in err


# ---- Integration-level: full end-to-end dispatch --------------------------


@pytest.mark.serial
@pytest.mark.skipif(not _is_emscripten_available(), reason="Emscripten not available on this platform")
@pytest.mark.parametrize(
    "entry_point",
    [
        "clang-tool-chain-emcc",
        "clang-tool-chain-em-cpp",
        "clang-tool-chain-zccache-emcc",
        "clang-tool-chain-zccache-em-cpp",
        "ctc-emcc",
        "ctc-em-cpp",
    ],
)
def test_emscripten_zccache_entry_point_compiles(entry_point: str) -> None:
    """The exact repro from issue #29: each affected entry point must compile
    a hello-world translation unit cleanly (rc=0, non-empty output)."""
    binary = shutil.which(entry_point)
    if not binary:
        pytest.skip(f"{entry_point} not installed (re-run uv pip install -e .)")

    with tempfile.TemporaryDirectory() as td:
        src = Path(td) / "t.cpp"
        src.write_text("int main(){return 0;}\n")
        out = Path(td) / "t.o"
        result = subprocess.run(
            [binary, "-c", str(src), "-o", str(out), "-O0"],
            capture_output=True,
            text=True,
            timeout=120,
        )
        assert result.returncode == 0, (
            f"{entry_point} failed (rc={result.returncode})\nstderr: {result.stderr!r}\nstdout: {result.stdout!r}"
        )
        assert out.exists() and out.stat().st_size > 0, f"{entry_point} returned 0 but produced no output file"
