"""
Tests for the emar / emstrip / emranlib / emnm console-script wrappers
added in 1.5.0 (closes issue #23).

Verifies:
  - All eight entry-point names install and import.
  - Each runs `--version` end-to-end (proves dispatch into the bundled
    emscripten Python tools works, including the `tools/` fallback for emnm).
  - The lightweight ``execute_emscripten_py_tool`` helper rejects
    non-archive tool names.
"""

from __future__ import annotations

import shutil
import subprocess

import pytest

# Tools that respond to --version with rc=0 — used in a broader smoke test
# to cover the Binaryen + wasm-heavy entry points added in 1.5.0.
_VERSION_FRIENDLY_TOOLS = (
    "emar",
    "emstrip",
    "emranlib",
    "emnm",
    "emcc",
    "wasm-ld",
    "wasm-opt",
    "wasm-as",
    "wasm-dis",
    "wasm-emscripten-finalize",
    "wasm-merge",
    "wasm-metadce",
    "wasm-ctor-eval",
)
_VERSION_ENTRY_POINTS = tuple(
    f"{prefix}{name}" for prefix in ("clang-tool-chain-", "ctc-") for name in _VERSION_FRIENDLY_TOOLS
)

# Tools whose dispatch we verify just by checking the entry point is installed.
# These tools either don't accept --version (emcmake / emsize / em-config print
# usage and exit non-zero) or are interactive (wasm-shell), so we don't run them.
_INSTALL_ONLY_TOOLS = (
    "emcmake",
    "emmake",
    "emconfigure",
    "emscons",
    "embuilder",
    "em-config",
    "emsize",
    "emrun",
    "emscan-deps",
    "emsymbolizer",
    "emdwp",
    "emcoverage",
    "emprofile",
    "wasm-shell",
)
_INSTALL_ONLY_ENTRY_POINTS = tuple(
    f"{prefix}{name}" for prefix in ("clang-tool-chain-", "ctc-") for name in _INSTALL_ONLY_TOOLS
)


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
    from clang_tool_chain.execution.emscripten import execute_emscripten_py_tool

    with pytest.raises(ValueError, match="emar"):
        execute_emscripten_py_tool("emcc")


@pytest.mark.serial
@pytest.mark.skipif(not _is_emscripten_available(), reason="Emscripten binaries not available for this platform")
@pytest.mark.parametrize("entry_point", _VERSION_ENTRY_POINTS)
def test_version_friendly_entry_point_dispatches(entry_point: str) -> None:
    """Every console script that supports ``--version`` must dispatch and exit 0.

    Covers the four archive tools (emar/emstrip/emranlib/emnm), the heavy WASM
    compilers/linker (emcc/wasm-ld), and the Binaryen native binaries
    (wasm-opt, wasm-as, wasm-dis, etc.). Both ``clang-tool-chain-*`` and
    ``ctc-*`` short-form aliases are exercised.
    """
    binary = shutil.which(entry_point)
    assert binary is not None, f"{entry_point} not installed (re-run uv pip install -e .)"

    result = subprocess.run([binary, "--version"], capture_output=True, text=True, timeout=60)
    assert result.returncode == 0, (
        f"{entry_point} --version failed (rc={result.returncode})\nstdout: {result.stdout!r}\nstderr: {result.stderr!r}"
    )


@pytest.mark.parametrize("entry_point", _INSTALL_ONLY_ENTRY_POINTS)
def test_install_only_entry_point_installed(entry_point: str) -> None:
    """Tools that don't honour ``--version`` still need to be registered as scripts.

    pyproject.toml ``[project.scripts]`` declares them; ``uv pip install -e .``
    materialises them in the venv. This guards against typos in the script
    map (e.g. a stale entry-point pointing at a renamed function).
    """
    assert shutil.which(entry_point), (
        f"{entry_point} not installed — likely a stale [project.scripts] entry or a missing _main function."
    )
