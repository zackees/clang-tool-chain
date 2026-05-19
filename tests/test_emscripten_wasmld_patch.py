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


# ============================================================================
# 1.5.5 performance optimizations
# ============================================================================


def test_marker_file_dropped_after_first_patch(tmp_path: Path) -> None:
    """The first successful patch must drop a sidecar marker file so
    subsequent calls can take the single-stat fast path."""
    install_dir = _make_fake_install(tmp_path / "emsdk")
    marker_path = install_dir / EmscriptenInstaller._WASM_LD_PATCH_MARKER_FILE
    assert not marker_path.exists()

    _installer._apply_wasm_ld_patch(install_dir)

    assert marker_path.exists(), "marker file should be created after first patch"


def test_marker_file_makes_second_call_skip_shared_py_read(tmp_path: Path) -> None:
    """When the sidecar marker exists, _apply_wasm_ld_patch must not even
    open shared.py — that's the whole point of the fast path."""
    install_dir = _make_fake_install(tmp_path / "emsdk")
    shared_py = install_dir / "emscripten" / "tools" / "shared.py"

    # First call: applies patch, drops marker
    _installer._apply_wasm_ld_patch(install_dir)
    assert (install_dir / EmscriptenInstaller._WASM_LD_PATCH_MARKER_FILE).exists()

    # Replace shared.py with garbage and re-run. If the fast path works, the
    # patch helper must NOT read shared.py and the garbage stays intact.
    shared_py.write_text("totally invalid content", encoding="utf-8")
    _installer._apply_wasm_ld_patch(install_dir)
    assert shared_py.read_text(encoding="utf-8") == "totally invalid content"


def test_marker_dropped_on_already_patched_install_without_marker(tmp_path: Path) -> None:
    """Pre-1.5.5 installs have shared.py already patched but no sidecar marker.
    The first 1.5.5+ call should detect the existing patch and drop the marker
    so subsequent calls take the fast path."""
    install_dir = _make_fake_install(tmp_path / "emsdk")
    shared_py = install_dir / "emscripten" / "tools" / "shared.py"
    # Manually apply patch to simulate pre-1.5.5 install (no marker yet)
    _installer._apply_wasm_ld_patch(install_dir)
    marker_path = install_dir / EmscriptenInstaller._WASM_LD_PATCH_MARKER_FILE
    marker_path.unlink()
    assert EmscriptenInstaller._WASM_LD_PATCH_MARKER in shared_py.read_text(encoding="utf-8")

    # First call after upgrade: should see in-content marker, drop sidecar
    _installer._apply_wasm_ld_patch(install_dir)
    assert marker_path.exists()


def test_post_race_window_true_when_done_txt_is_old(tmp_path: Path) -> None:
    import os
    import time as _time

    from clang_tool_chain.installers.emscripten import _DONE_TXT_RACE_WINDOW_SECONDS, _is_post_race_window

    done = tmp_path / "done.txt"
    done.write_text("installed")
    old_mtime = _time.time() - (_DONE_TXT_RACE_WINDOW_SECONDS + 10)
    os.utime(done, (old_mtime, old_mtime))

    assert _is_post_race_window(done) is True


def test_post_race_window_false_when_done_txt_is_fresh(tmp_path: Path) -> None:
    from clang_tool_chain.installers.emscripten import _is_post_race_window

    done = tmp_path / "done.txt"
    done.write_text("just installed")  # mtime = now

    assert _is_post_race_window(done) is False


def test_can_skip_manifest_recheck_when_done_txt_recent(tmp_path: Path) -> None:
    from clang_tool_chain.installers.emscripten import _can_skip_manifest_recheck

    done = tmp_path / "done.txt"
    done.write_text("recent install")

    assert _can_skip_manifest_recheck(done) is True


def test_can_skip_manifest_recheck_false_when_done_txt_stale(tmp_path: Path) -> None:
    import os
    import time as _time

    from clang_tool_chain.installers.emscripten import _MANIFEST_RECHECK_INTERVAL_SECONDS, _can_skip_manifest_recheck

    done = tmp_path / "done.txt"
    done.write_text("very old install")
    stale = _time.time() - (_MANIFEST_RECHECK_INTERVAL_SECONDS + 100)
    os.utime(done, (stale, stale))

    assert _can_skip_manifest_recheck(done) is False


def test_can_skip_manifest_recheck_false_when_done_txt_missing(tmp_path: Path) -> None:
    from clang_tool_chain.installers.emscripten import _can_skip_manifest_recheck

    assert _can_skip_manifest_recheck(tmp_path / "nope.txt") is False


def test_force_manifest_check_env_var_overrides(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Setting CLANG_TOOL_CHAIN_FORCE_MANIFEST_CHECK=1 must force the network
    re-check even when done.txt is fresh."""
    from clang_tool_chain.installers.emscripten import _can_skip_manifest_recheck

    done = tmp_path / "done.txt"
    done.write_text("recent")

    monkeypatch.setenv("CLANG_TOOL_CHAIN_FORCE_MANIFEST_CHECK", "1")
    assert _can_skip_manifest_recheck(done) is False

    monkeypatch.delenv("CLANG_TOOL_CHAIN_FORCE_MANIFEST_CHECK")
    assert _can_skip_manifest_recheck(done) is True


def test_ensure_available_memoizes_within_process() -> None:
    """A second call in the same process must short-circuit to ~0 cost."""
    import time as _time

    from clang_tool_chain.installers.emscripten import (
        _emscripten_ensure_memo_reset_for_tests,
        ensure_emscripten_available,
    )

    # Best-effort: only meaningful if emscripten is actually installed here.
    try:
        from clang_tool_chain.wrapper import get_platform_info

        platform, arch = get_platform_info()
    except Exception:
        pytest.skip("platform info unavailable")

    if not (Path.home() / ".clang-tool-chain" / "emscripten" / platform / arch / "done.txt").exists():
        pytest.skip("emscripten not installed; can't exercise memoization end-to-end")

    _emscripten_ensure_memo_reset_for_tests()
    ensure_emscripten_available(platform, arch)  # warms the memo

    t0 = _time.perf_counter()
    ensure_emscripten_available(platform, arch)  # second call should be ~no-op
    second_call_ms = (_time.perf_counter() - t0) * 1000
    assert second_call_ms < 5.0, f"memoized call took {second_call_ms:.2f} ms, expected <5"
