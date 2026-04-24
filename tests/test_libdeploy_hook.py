"""
Unit tests for ``clang_tool_chain.commands.libdeploy.main`` (P3).

Tests the post-link deployment hook contract documented in
``docs/ZCCACHE_INTEGRATION_CONTRACTS.md`` section 4.

Key guarantees:
  * Non-fatal — exits 0 on every error path, warnings go to stderr.
  * Idempotent — suffixes like ``.o`` / ``.a`` are skipped.
  * Silent on success unless ``CLANG_TOOL_CHAIN_LIB_DEPLOY_VERBOSE=1``.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

libdeploy = pytest.importorskip("clang_tool_chain.commands.libdeploy")
profile_mod = pytest.importorskip("clang_tool_chain.profile")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_file(p: Path, magic: bytes = b"") -> Path:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes(magic)
    return p


@pytest.fixture(autouse=True)
def _stub_profile(monkeypatch, tmp_path):
    """Install a minimal Profile so main() doesn't short-circuit on missing profile.

    Individual tests may override this by re-patching ``load_profile``.
    """
    clang_root = tmp_path / "_profile_root"
    clang_root.mkdir()
    profile = profile_mod.Profile(
        version=profile_mod.SCHEMA_VERSION,
        generated_at="2026-01-01T00:00:00Z",
        platform="win" if sys.platform == "win32" else ("linux" if sys.platform == "linux" else "darwin"),
        arch="x86_64",
        clang_root=str(clang_root).replace("\\", "/"),
        binaries={},
        abi_profiles={},
        sanitizer_env={},
        libdeploy=profile_mod.LibDeploy(),
    )

    def _loader(install_dir: Path | None = None):  # noqa: ANN001
        return profile

    monkeypatch.setattr(profile_mod, "load_profile", _loader, raising=False)


def _run_main_with_argv(monkeypatch, argv: list[str]) -> int:
    monkeypatch.setattr(sys, "argv", argv)
    try:
        libdeploy.main()
    except SystemExit as exc:
        return int(exc.code) if exc.code is not None else 0
    return 0


# ---------------------------------------------------------------------------
# No-op cases (unknown/intermediate suffixes)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("suffix", [".o", ".obj", ".a", ".lib"])
def test_libdeploy_noop_for_unknown_suffix(tmp_path, monkeypatch, suffix):
    artifact = _make_file(tmp_path / f"build/foo{suffix}", b"\x00\x00\x00\x00")

    rc = _run_main_with_argv(monkeypatch, ["clang-tool-chain-libdeploy", str(artifact)])

    assert rc == 0


def test_libdeploy_missing_path_is_non_fatal(tmp_path, monkeypatch, capsys):
    nonexistent = tmp_path / "does-not-exist.exe"

    rc = _run_main_with_argv(monkeypatch, ["clang-tool-chain-libdeploy", str(nonexistent)])

    assert rc == 0
    captured = capsys.readouterr()
    # Either silent or a warning; must not crash.
    assert captured.err == "" or "warning" in captured.err.lower()


# ---------------------------------------------------------------------------
# Dispatch tests
# ---------------------------------------------------------------------------


def test_libdeploy_dll_dispatches_to_dll_deployer(tmp_path, monkeypatch):
    dll = _make_file(tmp_path / "out/hello.dll", b"MZ\x00\x00")
    called: list[tuple[Path, str]] = []

    def fake(output_path, platform, *, use_gnu_abi=True):  # noqa: ANN001
        called.append((output_path, platform))

    import clang_tool_chain.deployment.dll_deployer as dll_mod

    monkeypatch.setattr(dll_mod, "post_link_dll_deployment", fake, raising=False)

    rc = _run_main_with_argv(monkeypatch, ["clang-tool-chain-libdeploy", str(dll)])

    assert rc == 0
    assert called, "dll deployer was not invoked for .dll output"
    assert Path(called[0][0]).name == "hello.dll"
    assert called[0][1] == "win"


def test_libdeploy_exe_dispatches_to_dll_deployer(tmp_path, monkeypatch):
    exe = _make_file(tmp_path / "out/app.exe", b"MZ\x00\x00")
    called: list[Path] = []

    def fake(output_path, platform, *, use_gnu_abi=True):  # noqa: ANN001
        called.append(output_path)

    import clang_tool_chain.deployment.dll_deployer as dll_mod

    monkeypatch.setattr(dll_mod, "post_link_dll_deployment", fake, raising=False)

    rc = _run_main_with_argv(monkeypatch, ["clang-tool-chain-libdeploy", str(exe)])

    assert rc == 0
    assert called, "dll deployer not invoked for .exe"


@pytest.mark.skipif(sys.platform == "win32", reason=".so deployment is Linux/macOS only")
def test_libdeploy_so_dispatches_on_linux(tmp_path, monkeypatch):
    so = _make_file(tmp_path / "out/libfoo.so", b"\x7fELF")
    called: list[Path] = []

    def fake(output_path, *, arch="x86_64"):  # noqa: ANN001
        called.append(output_path)

    import clang_tool_chain.deployment.so_deployer as so_mod

    monkeypatch.setattr(so_mod, "post_link_so_deployment", fake, raising=False)

    rc = _run_main_with_argv(monkeypatch, ["clang-tool-chain-libdeploy", str(so)])

    assert rc == 0
    assert called, "so deployer not invoked for .so output"


@pytest.mark.skipif(sys.platform == "win32", reason=".dylib deployment is macOS only")
def test_libdeploy_dylib_dispatches_on_macos(tmp_path, monkeypatch):
    dylib = _make_file(tmp_path / "out/libfoo.dylib", b"\xcf\xfa\xed\xfe")
    called: list[Path] = []

    def fake(output_path, *, arch="x86_64"):  # noqa: ANN001
        called.append(output_path)

    import clang_tool_chain.deployment.dylib_deployer as dylib_mod

    monkeypatch.setattr(dylib_mod, "post_link_dylib_deployment", fake, raising=False)

    rc = _run_main_with_argv(monkeypatch, ["clang-tool-chain-libdeploy", str(dylib)])

    assert rc == 0
    assert called, "dylib deployer not invoked for .dylib output"


# ---------------------------------------------------------------------------
# Error tolerance
# ---------------------------------------------------------------------------


def test_libdeploy_errors_are_non_fatal(tmp_path, monkeypatch, capsys):
    dll = _make_file(tmp_path / "out/hello.dll", b"MZ\x00\x00")

    def boom(*args, **kwargs):  # noqa: ANN001, ANN002, ANN003
        raise RuntimeError("simulated deploy failure")

    import clang_tool_chain.deployment.dll_deployer as dll_mod

    monkeypatch.setattr(dll_mod, "post_link_dll_deployment", boom, raising=False)

    rc = _run_main_with_argv(monkeypatch, ["clang-tool-chain-libdeploy", str(dll)])

    assert rc == 0  # must not break the build
    captured = capsys.readouterr()
    assert "warning" in captured.err.lower() or "fail" in captured.err.lower()


# ---------------------------------------------------------------------------
# Verbose mode
# ---------------------------------------------------------------------------


def test_libdeploy_verbose_env_logs_deployed_files(tmp_path, monkeypatch, capsys):
    dll = _make_file(tmp_path / "out/verbose_case.dll", b"MZ\x00\x00")
    monkeypatch.setenv("CLANG_TOOL_CHAIN_LIB_DEPLOY_VERBOSE", "1")

    def fake(output_path, platform, *, use_gnu_abi=True):  # noqa: ANN001
        # Real deployer would print file names; we simulate that via stderr.
        sys.stderr.write(f"[libdeploy] deployed: {Path(output_path).name}\n")

    import clang_tool_chain.deployment.dll_deployer as dll_mod

    monkeypatch.setattr(dll_mod, "post_link_dll_deployment", fake, raising=False)

    rc = _run_main_with_argv(monkeypatch, ["clang-tool-chain-libdeploy", str(dll)])

    assert rc == 0
    captured = capsys.readouterr()
    # Either the shim itself or the fake deployer should have written the file name.
    assert "verbose_case.dll" in captured.err


def test_libdeploy_silent_by_default(tmp_path, monkeypatch, capsys):
    dll = _make_file(tmp_path / "out/silent.dll", b"MZ\x00\x00")
    monkeypatch.delenv("CLANG_TOOL_CHAIN_LIB_DEPLOY_VERBOSE", raising=False)

    def fake(output_path, platform, *, use_gnu_abi=True):  # noqa: ANN001
        return None

    import clang_tool_chain.deployment.dll_deployer as dll_mod

    monkeypatch.setattr(dll_mod, "post_link_dll_deployment", fake, raising=False)

    rc = _run_main_with_argv(monkeypatch, ["clang-tool-chain-libdeploy", str(dll)])

    assert rc == 0
    captured = capsys.readouterr()
    # Silent on success.
    assert captured.out == ""
    assert "deployed" not in captured.err.lower()
