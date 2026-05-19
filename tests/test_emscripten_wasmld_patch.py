"""
Unit tests for the EMCC_WASM_LD patch applied to emscripten/tools/shared.py.

Background: GitHub issue #22 — emcc has no built-in env-var override for
WASM_LD, so the installer rewrites shared.py to honor EMCC_WASM_LD. These
tests exercise the patch helper in isolation without needing a real
emscripten install.
"""

from pathlib import Path

import pytest

from clang_tool_chain.installers.emscripten import EmscriptenInstaller, _installer

SHARED_PY_TEMPLATE = """# minimal shared.py stub for testing
import os

def llvm_tool_path(tool):
    return '/fake/llvm/bin/' + tool

CLANG_CC = llvm_tool_path('clang')
WASM_LD = llvm_tool_path('wasm-ld')
LLVM_AR = llvm_tool_path('llvm-ar')
"""


def _make_fake_install(root: Path) -> Path:
    """Create a minimal install tree containing emscripten/tools/shared.py."""
    tools_dir = root / "emscripten" / "tools"
    tools_dir.mkdir(parents=True)
    (tools_dir / "shared.py").write_text(SHARED_PY_TEMPLATE, encoding="utf-8")
    return root


def test_patch_applies_to_unpatched_shared_py(tmp_path: Path) -> None:
    install_dir = _make_fake_install(tmp_path / "emsdk")
    shared_py = install_dir / "emscripten" / "tools" / "shared.py"

    _installer._apply_wasm_ld_patch(install_dir)

    patched = shared_py.read_text(encoding="utf-8")
    assert EmscriptenInstaller._WASM_LD_PATCH_MARKER in patched
    assert "WASM_LD = os.environ.get('EMCC_WASM_LD') or llvm_tool_path('wasm-ld')" in patched
    # Original assignment must be gone — otherwise both lines run and the second wins
    assert "WASM_LD = llvm_tool_path('wasm-ld')\n" not in patched.replace("or llvm_tool_path('wasm-ld')\n", "")


def test_patch_is_idempotent(tmp_path: Path) -> None:
    install_dir = _make_fake_install(tmp_path / "emsdk")
    shared_py = install_dir / "emscripten" / "tools" / "shared.py"

    _installer._apply_wasm_ld_patch(install_dir)
    after_first = shared_py.read_text(encoding="utf-8")
    _installer._apply_wasm_ld_patch(install_dir)
    after_second = shared_py.read_text(encoding="utf-8")

    assert after_first == after_second
    assert after_second.count(EmscriptenInstaller._WASM_LD_PATCH_MARKER) == 1


def test_patch_no_op_when_shared_py_missing(tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
    install_dir = tmp_path / "emsdk"
    install_dir.mkdir()
    # Should not raise — just log a warning.
    _installer._apply_wasm_ld_patch(install_dir)


def test_patch_no_op_when_expected_line_absent(tmp_path: Path) -> None:
    install_dir = _make_fake_install(tmp_path / "emsdk")
    shared_py = install_dir / "emscripten" / "tools" / "shared.py"
    shared_py.write_text("# nothing here matches the expected line\n", encoding="utf-8")

    _installer._apply_wasm_ld_patch(install_dir)

    # Marker absent, file untouched (no crash, no rewrite).
    content = shared_py.read_text(encoding="utf-8")
    assert EmscriptenInstaller._WASM_LD_PATCH_MARKER not in content


def test_patched_module_honors_env_var(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """End-to-end check: import the patched stub and confirm EMCC_WASM_LD wins."""
    install_dir = _make_fake_install(tmp_path / "emsdk")
    _installer._apply_wasm_ld_patch(install_dir)

    shared_py = install_dir / "emscripten" / "tools" / "shared.py"

    # Load the patched module fresh under two env-var states.
    import importlib.util
    import sys

    def load() -> object:
        spec = importlib.util.spec_from_file_location("ctc_test_shared", shared_py)
        assert spec is not None and spec.loader is not None
        mod = importlib.util.module_from_spec(spec)
        sys.modules["ctc_test_shared"] = mod
        try:
            spec.loader.exec_module(mod)
        finally:
            sys.modules.pop("ctc_test_shared", None)
        return mod

    monkeypatch.delenv("EMCC_WASM_LD", raising=False)
    default_mod = load()
    assert getattr(default_mod, "WASM_LD") == "/fake/llvm/bin/wasm-ld"  # noqa: B009

    monkeypatch.setenv("EMCC_WASM_LD", "/custom/ctc-wasm-ld")
    override_mod = load()
    assert getattr(override_mod, "WASM_LD") == "/custom/ctc-wasm-ld"  # noqa: B009
