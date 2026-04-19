"""
Unit tests for ``clang_tool_chain.zccache_shim`` (P3).

Covers the public API documented in ``docs/ZCCACHE_INTEGRATION_CONTRACTS.md``
section 2. Imports are guarded with ``pytest.importorskip`` so the file can
be committed before the shim lands.

Patterns mirror ``tests/test_native_shim.py`` — same ``_ExecvpCalled``
sentinel trick, same ``monkeypatch.setattr(sys, "argv", ...)`` approach.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

shim = pytest.importorskip("clang_tool_chain.zccache_shim")
profile_mod = pytest.importorskip("clang_tool_chain.profile")


# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------


class _ExecvpCalled(Exception):  # noqa: N818 — sentinel, not an error type
    """Sentinel raised in place of a real exec so the test can inspect argv/env."""

    def __init__(self, file: str, argv: list[str], env: dict[str, str] | None = None):
        self.file = file
        self.argv = list(argv)
        self.env = dict(env) if env is not None else dict(os.environ)


def _install_execvp_capture(monkeypatch: pytest.MonkeyPatch) -> None:
    """Replace ``os.execvp``/``os.execvpe`` AND ``subprocess.run`` with a
    sentinel-raising fake.

    The shim switched from ``os.execvpe`` to ``subprocess.run`` + ``sys.exit``
    because Windows exec-emulation crashes when the spawned child forks
    (as ``zccache`` does when it runs ``clang``). Tests that want to inspect
    argv/env should intercept at the ``subprocess.run`` boundary instead.
    """

    def fake_execvp(file, argv):  # noqa: ANN001
        raise _ExecvpCalled(file, argv)

    def fake_execvpe(file, argv, env):  # noqa: ANN001
        raise _ExecvpCalled(file, argv, env)

    def fake_subprocess_run(argv, *args, **kwargs):  # noqa: ANN001, ANN002
        env = kwargs.get("env")
        raise _ExecvpCalled(argv[0], argv, env)

    monkeypatch.setattr(os, "execvp", fake_execvp, raising=False)
    monkeypatch.setattr(os, "execvpe", fake_execvpe, raising=False)
    # The shim does ``import subprocess`` lazily inside the function body,
    # so patch the attribute on the subprocess module itself.
    import subprocess as _subprocess

    monkeypatch.setattr(_subprocess, "run", fake_subprocess_run)


def _fake_zccache(dir_path: Path) -> Path:
    name = "zccache.exe" if os.name == "nt" else "zccache"
    binary = dir_path / name
    binary.write_bytes(b"")
    if os.name != "nt":
        binary.chmod(0o755)
    return binary


def _make_fake_compiler(dir_path: Path, basename: str = "clang") -> Path:
    name = f"{basename}.exe" if os.name == "nt" else basename
    path = dir_path / name
    path.write_bytes(b"")
    if os.name != "nt":
        path.chmod(0o755)
    return path


@pytest.fixture(autouse=True)
def _reset_profile_cache():
    reset = getattr(profile_mod, "_reset_cache_for_tests", None)
    if callable(reset):
        reset()
    yield
    if callable(reset):
        reset()


@pytest.fixture
def fake_profile(tmp_path, monkeypatch):
    """Install a minimal resolved ``Profile`` so ``exec_via_zccache`` runs."""
    clang_root = tmp_path / "clang_root"
    bin_dir = clang_root / "bin"
    bin_dir.mkdir(parents=True)
    compiler_path = _make_fake_compiler(bin_dir, "clang")
    _make_fake_compiler(bin_dir, "clang++")

    abi_name = "gnu" if sys.platform == "win32" else ("linux" if sys.platform == "linux" else "darwin")
    abi_profile = profile_mod.AbiProfile(
        flags_all=["--target=fake-target", "-stdlib=libc++"],
        flags_link_only=["-fuse-ld=lld", "-lpthread"],
    )
    profile = profile_mod.Profile(
        version=profile_mod.SCHEMA_VERSION,
        generated_at="2026-01-01T00:00:00Z",
        platform="win" if sys.platform == "win32" else ("linux" if sys.platform == "linux" else "darwin"),
        arch="x86_64",
        clang_root=str(clang_root).replace("\\", "/"),
        binaries={
            "clang": str(compiler_path),
            "clang++": str(bin_dir / ("clang++.exe" if os.name == "nt" else "clang++")),
        },
        abi_profiles={abi_name: abi_profile},
        sanitizer_env={},
        libdeploy=profile_mod.LibDeploy(),
    )

    def _fake_load(install_dir: Path | None = None):  # noqa: ANN001
        return profile

    monkeypatch.setattr(shim, "load_profile", _fake_load, raising=False)
    # Also patch the underlying module function in case the shim calls it directly.
    monkeypatch.setattr(profile_mod, "load_profile", _fake_load, raising=False)

    return profile, compiler_path


# ---------------------------------------------------------------------------
# find_zccache_binary
# ---------------------------------------------------------------------------


def test_find_zccache_binary_prefers_sys_executable_dir(tmp_path, monkeypatch):
    fake_python_dir = tmp_path / "py"
    fake_python_dir.mkdir()
    monkeypatch.setattr(sys, "executable", str(fake_python_dir / "python.exe"))
    binary = _fake_zccache(fake_python_dir)

    found = shim.find_zccache_binary()

    assert found == binary


def test_find_zccache_binary_falls_back_to_PATH(tmp_path, monkeypatch):  # noqa: N802
    empty = tmp_path / "empty"
    empty.mkdir()
    monkeypatch.setattr(sys, "executable", str(empty / "python.exe"))

    path_dir = tmp_path / "on-path"
    path_dir.mkdir()
    binary = _fake_zccache(path_dir)
    monkeypatch.setenv("PATH", str(path_dir))

    found = shim.find_zccache_binary()

    assert found == binary


def test_find_zccache_binary_returns_none_when_missing(tmp_path, monkeypatch):
    empty = tmp_path / "empty"
    empty.mkdir()
    monkeypatch.setattr(sys, "executable", str(empty / "python.exe"))
    monkeypatch.setenv("PATH", "")

    assert shim.find_zccache_binary() is None


# ---------------------------------------------------------------------------
# Env-var handling
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("value", ["1", "true", "yes", "on"])
def test_fallback_requested_truthy_values_accepted(monkeypatch, value):
    """The shim honors a ctc-abi override expressed via env var."""
    monkeypatch.setenv("CTC_ABI", "msvc")
    # Just verify the env var is read into the internal resolver without error.
    resolver = getattr(shim, "_resolve_abi", None)
    if resolver is None:
        pytest.skip("internal resolver not exposed")
    assert resolver("auto", [], None) == "msvc"
    monkeypatch.delenv("CTC_ABI", raising=False)
    monkeypatch.setenv("CTC_ABI", value if value != "on" else "msvc")
    # Any truthy-looking non-empty string gets treated as a literal ABI
    # (the contract doesn't boolean-coerce here; it's a string override).
    assert resolver("auto", [], None) in {"msvc", value}


# ---------------------------------------------------------------------------
# exec_via_zccache — argv construction
# ---------------------------------------------------------------------------


def test_exec_via_zccache_builds_correct_argv(tmp_path, monkeypatch, fake_profile):
    profile, compiler_path = fake_profile

    # Put zccache alongside sys.executable.
    py_dir = tmp_path / "py"
    py_dir.mkdir()
    monkeypatch.setattr(sys, "executable", str(py_dir / "python.exe"))
    zccache = _fake_zccache(py_dir)

    monkeypatch.setattr(sys, "argv", ["clang-tool-chain-clang", "hello.c", "-o", "hello"])
    monkeypatch.delenv("CTC_ABI", raising=False)
    monkeypatch.delenv("CLANG_TOOL_CHAIN_NO_DIRECTIVES", raising=False)
    monkeypatch.setenv("CLANG_TOOL_CHAIN_NO_DIRECTIVES", "1")  # keep argv deterministic
    _install_execvp_capture(monkeypatch)

    with pytest.raises(_ExecvpCalled) as exc:
        shim.exec_via_zccache("clang", use_cache=False)

    call = exc.value
    assert call.file == str(zccache)
    # argv[0] == zccache path
    assert call.argv[0] == str(zccache)
    # argv[1] must be the resolved compiler path (absolute).
    assert Path(call.argv[1]).name.startswith("clang")
    # User args + profile flags must all be present somewhere after argv[1].
    tail = call.argv[2:]
    assert "hello.c" in tail
    assert "-o" in tail
    assert "hello" in tail
    for flag in profile.abi_profiles[next(iter(profile.abi_profiles))].flags_all:
        assert flag in tail
    for flag in profile.abi_profiles[next(iter(profile.abi_profiles))].flags_link_only:
        assert flag in tail


def test_use_cache_false_sets_ZCCACHE_DISABLE(tmp_path, monkeypatch, fake_profile):  # noqa: N802
    py_dir = tmp_path / "py"
    py_dir.mkdir()
    monkeypatch.setattr(sys, "executable", str(py_dir / "python.exe"))
    _fake_zccache(py_dir)
    monkeypatch.setattr(sys, "argv", ["clang-tool-chain-clang", "hello.c"])
    monkeypatch.setenv("CLANG_TOOL_CHAIN_NO_DIRECTIVES", "1")
    monkeypatch.delenv("ZCCACHE_DISABLE", raising=False)
    _install_execvp_capture(monkeypatch)

    with pytest.raises(_ExecvpCalled) as exc:
        shim.exec_via_zccache("clang", use_cache=False)

    env = exc.value.env
    assert env.get("ZCCACHE_DISABLE") == "1"


def test_use_cache_true_sets_LINK_DEPLOY_CMD(tmp_path, monkeypatch, fake_profile):  # noqa: N802
    py_dir = tmp_path / "py"
    py_dir.mkdir()
    monkeypatch.setattr(sys, "executable", str(py_dir / "python.exe"))
    _fake_zccache(py_dir)
    monkeypatch.setattr(sys, "argv", ["clang-tool-chain-zccache-clang", "hello.c"])
    monkeypatch.setenv("CLANG_TOOL_CHAIN_NO_DIRECTIVES", "1")
    monkeypatch.delenv("ZCCACHE_DISABLE", raising=False)
    monkeypatch.delenv("ZCCACHE_LINK_DEPLOY_CMD", raising=False)
    _install_execvp_capture(monkeypatch)

    with pytest.raises(_ExecvpCalled) as exc:
        shim.exec_via_zccache("clang", use_cache=True)

    env = exc.value.env
    assert env.get("ZCCACHE_LINK_DEPLOY_CMD") == "clang-tool-chain-libdeploy"
    assert env.get("ZCCACHE_DISABLE") != "1"


def test_compile_only_suppresses_link_flags(tmp_path, monkeypatch, fake_profile):
    profile, _ = fake_profile
    py_dir = tmp_path / "py"
    py_dir.mkdir()
    monkeypatch.setattr(sys, "executable", str(py_dir / "python.exe"))
    _fake_zccache(py_dir)
    monkeypatch.setattr(sys, "argv", ["clang-tool-chain-clang", "-c", "hello.c", "-o", "hello.o"])
    monkeypatch.setenv("CLANG_TOOL_CHAIN_NO_DIRECTIVES", "1")
    _install_execvp_capture(monkeypatch)

    with pytest.raises(_ExecvpCalled) as exc:
        shim.exec_via_zccache("clang", use_cache=False)

    argv = exc.value.argv
    abi_name = next(iter(profile.abi_profiles))
    for link_flag in profile.abi_profiles[abi_name].flags_link_only:
        assert link_flag not in argv, f"link-only flag {link_flag!r} leaked into compile-only invocation"


# ---------------------------------------------------------------------------
# ABI resolution
# ---------------------------------------------------------------------------


@pytest.mark.skipif(sys.platform != "win32", reason="Windows ABI resolution")
def test_abi_auto_windows_default_is_gnu(monkeypatch):
    resolver = getattr(shim, "_resolve_abi", None)
    if resolver is None:
        pytest.skip("internal _resolve_abi not exposed")
    monkeypatch.delenv("CTC_ABI", raising=False)
    assert resolver("auto", [], None) == "gnu"


@pytest.mark.skipif(sys.platform != "win32", reason="Windows ABI resolution")
def test_abi_auto_windows_msvc_target_in_argv_detected(monkeypatch):
    resolver = getattr(shim, "_resolve_abi", None)
    if resolver is None:
        pytest.skip("internal _resolve_abi not exposed")
    monkeypatch.delenv("CTC_ABI", raising=False)
    args = ["hello.c", "--target=x86_64-pc-windows-msvc"]
    assert resolver("auto", args, None) == "msvc"


def test_abi_msvc_env_var_override(monkeypatch):
    resolver = getattr(shim, "_resolve_abi", None)
    if resolver is None:
        pytest.skip("internal _resolve_abi not exposed")
    monkeypatch.setenv("CTC_ABI", "msvc")
    assert resolver("auto", [], None) == "msvc"


def test_abi_msvc_flag_stripped_from_argv():
    consume = getattr(shim, "_consume_ctc_abi_flag", None)
    if consume is None:
        pytest.skip("internal _consume_ctc_abi_flag not exposed")
    out, override = consume(["--ctc-abi=msvc", "hello.c", "-o", "hello"])
    assert override == "msvc"
    assert "--ctc-abi=msvc" not in out
    assert out == ["hello.c", "-o", "hello"]

    out, override = consume(["--ctc-abi", "gnu", "hello.c"])
    assert override == "gnu"
    assert "--ctc-abi" not in out
    assert out == ["hello.c"]


# ---------------------------------------------------------------------------
# parse_directives_fast
# ---------------------------------------------------------------------------


def test_parse_directives_fast_link_directive(tmp_path, monkeypatch):
    source = tmp_path / "hello.c"
    source.write_text(
        "// @link: m\n#include <math.h>\nint main(void){return 0;}\n",
        encoding="utf-8",
    )
    monkeypatch.delenv("CLANG_TOOL_CHAIN_NO_DIRECTIVES", raising=False)

    flags = shim.parse_directives_fast([str(source)])

    assert "-lm" in flags


def test_parse_directives_fast_cflags_directive(tmp_path, monkeypatch):
    source = tmp_path / "hello.c"
    source.write_text(
        "// @cflags: -DFOO=1 -Wall\nint main(void){return 0;}\n",
        encoding="utf-8",
    )
    monkeypatch.delenv("CLANG_TOOL_CHAIN_NO_DIRECTIVES", raising=False)

    flags = shim.parse_directives_fast([str(source)])

    assert "-DFOO=1" in flags
    assert "-Wall" in flags


def test_parse_directives_fast_no_directives_env_disables(tmp_path, monkeypatch):
    source = tmp_path / "hello.c"
    source.write_text(
        "// @link: m\nint main(void){return 0;}\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("CLANG_TOOL_CHAIN_NO_DIRECTIVES", "1")

    assert shim.parse_directives_fast([str(source)]) == []


# ---------------------------------------------------------------------------
# Actionable error messages
# ---------------------------------------------------------------------------


def test_binary_not_found_exits_with_actionable_error(tmp_path, monkeypatch, capsys, fake_profile):
    empty = tmp_path / "empty"
    empty.mkdir()
    monkeypatch.setattr(sys, "executable", str(empty / "python.exe"))
    monkeypatch.setenv("PATH", "")
    monkeypatch.setattr(sys, "argv", ["clang-tool-chain-clang", "--version"])

    with pytest.raises(SystemExit) as exc:
        shim.exec_via_zccache("clang", use_cache=False)

    assert exc.value.code != 0
    captured = capsys.readouterr()
    assert "zccache" in captured.err.lower()
    assert "pip install" in captured.err.lower()


def test_missing_profile_exits_with_actionable_error(tmp_path, monkeypatch, capsys):
    # zccache present, but load_profile raises.
    py_dir = tmp_path / "py"
    py_dir.mkdir()
    monkeypatch.setattr(sys, "executable", str(py_dir / "python.exe"))
    _fake_zccache(py_dir)
    monkeypatch.setattr(sys, "argv", ["clang-tool-chain-clang", "--version"])

    def _missing(*args, **kwargs):  # noqa: ANN001, ANN002, ANN003
        raise profile_mod.ProfileMissingError("stub: not installed")

    monkeypatch.setattr(shim, "load_profile", _missing, raising=False)
    monkeypatch.setattr(profile_mod, "load_profile", _missing, raising=False)

    with pytest.raises(SystemExit) as exc:
        shim.exec_via_zccache("clang", use_cache=False)

    assert exc.value.code != 0
    captured = capsys.readouterr()
    assert "clang-tool-chain install clang" in captured.err


# ---------------------------------------------------------------------------
# Import-footprint regression
# ---------------------------------------------------------------------------


def test_zccache_shim_import_is_lightweight():
    """
    Importing ``clang_tool_chain.zccache_shim`` must NOT transitively pull the
    heavy Python pipeline (``execution.*``, ``arg_transformers``, ...).

    Mirrors the test at the bottom of ``tests/test_native_shim.py``.
    """
    code = (
        "import sys; "
        "import clang_tool_chain.zccache_shim as _shim; "
        "heavy = ["
        "'clang_tool_chain.execution.core', "
        "'clang_tool_chain.execution.arg_transformers', "
        "'clang_tool_chain.execution.build', "
        "'clang_tool_chain.platform.detection', "
        "'clang_tool_chain.installer', "
        "'clang_tool_chain.downloader', "
        "]; "
        "loaded = [m for m in heavy if m in sys.modules]; "
        "assert not loaded, f'hot path pulled: {loaded}'"
    )
    result = subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, f"Hot-path import regression:\nstdout={result.stdout}\nstderr={result.stderr}"
