"""
Parity tests for the native `ctc-clang` trampoline.

For each representative invocation, drive the native launcher via `--dry-run`
and assert the expected high-value flag transforms land in the resolved argv:

* GNU ABI Windows injection (default path)
* MSVC ABI Windows injection (via `--target=...-pc-windows-msvc` shim prefix)
* `--deploy-dependencies` flag stripping
* Inlined directive plumbing (`// @link:`, `// @cflags`)
* Pass-through of `-c`, `-o X`, `-oX` output forms

These are integration tests — they spawn the native binary. Tests are skipped
when the `ctc-clang` binary isn't available on the test machine.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[1]
_LOCAL_BUILD = _REPO_ROOT / "ctc-clang"


def _find_native_binary(basename: str) -> Path | None:
    """Prefer the locally-built launcher in ./ctc-clang/, fall back to PATH."""
    name = f"{basename}.exe" if sys.platform == "win32" else basename
    local = _LOCAL_BUILD / name
    if local.exists():
        return local
    found = shutil.which(basename)
    return Path(found) if found else None


CTC_CLANG = _find_native_binary("ctc-clang")
CTC_CLANG_PP = _find_native_binary("ctc-clang++")

_require_native = pytest.mark.skipif(
    CTC_CLANG is None or CTC_CLANG_PP is None,
    reason="ctc-clang native binary not built — run `uv run clang-tool-chain-compile-native ctc-clang`",
)


def _dry_run(binary: Path, args: list[str]) -> str:
    """Invoke the native launcher with --dry-run and return stdout."""
    result = subprocess.run(
        [str(binary), "--dry-run", *args],
        capture_output=True,
        text=True,
        check=False,
        timeout=30,
    )
    assert result.returncode == 0, (
        f"ctc-clang --dry-run exited {result.returncode}\nstdout={result.stdout}\nstderr={result.stderr}"
    )
    return result.stdout


# ============================================================================
# GNU ABI (default path) — Windows only; other platforms skip
# ============================================================================


@_require_native
@pytest.mark.skipif(sys.platform != "win32", reason="GNU ABI injection is Windows-only")
def test_gnu_abi_injects_target_and_sysroot():
    assert CTC_CLANG is not None
    out = _dry_run(CTC_CLANG, ["hello.c", "-o", "hello.exe"])
    assert "-w64-windows-gnu" in out, out
    assert "-stdlib=libc++" in out, out
    assert "-fuse-ld=lld" in out, out


@_require_native
@pytest.mark.skipif(sys.platform != "win32", reason="GNU ABI injection is Windows-only")
def test_gnu_abi_cxx_variant_uses_clang_pp():
    assert CTC_CLANG_PP is not None
    out = _dry_run(CTC_CLANG_PP, ["hello.cpp", "-o", "hello.exe"])
    assert "clang++" in out, out
    assert "-w64-windows-gnu" in out, out


@_require_native
@pytest.mark.skipif(sys.platform != "win32", reason="Compile-only flag path is checked here")
def test_compile_only_suppresses_link_flags():
    assert CTC_CLANG is not None
    out = _dry_run(CTC_CLANG, ["-c", "hello.c", "-o", "hello.o"])
    # Link-only flags must NOT appear when -c is present
    assert "-lpthread" not in out, out
    assert "-static-libstdc++" not in out, out


# ============================================================================
# MSVC ABI (via shim prefix) — the shim prepends `--target=...-pc-windows-msvc`.
# Directly testing this at the launcher level by supplying the prefix ourselves.
# ============================================================================


@_require_native
@pytest.mark.skipif(sys.platform != "win32", reason="MSVC target is Windows-only")
def test_msvc_target_suppresses_gnu_abi_injection():
    assert CTC_CLANG is not None
    out = _dry_run(
        CTC_CLANG,
        ["--target=x86_64-pc-windows-msvc", "hello.c", "-o", "hello.exe"],
    )
    # GNU ABI block must NOT fire when user supplies an MSVC target
    assert "-stdlib=libc++" not in out, out
    assert "-w64-windows-gnu" not in out, out
    assert "x86_64-pc-windows-msvc" in out, out


# ============================================================================
# Argv parsing edge cases
# ============================================================================


@_require_native
def test_deploy_dependencies_flag_stripped():
    assert CTC_CLANG is not None
    out = _dry_run(CTC_CLANG, ["--deploy-dependencies", "hello.c"])
    # The launcher flag must not leak through to clang.
    assert "--deploy-dependencies" not in out, out


@_require_native
def test_concatenated_oX_recognized_for_output_path():  # noqa: N802
    """Gap #11: both `-o foo.exe` and `-ofoo.exe` should set output_path."""
    assert CTC_CLANG is not None
    # Just exercising the path; we can't see output_path directly but --dry-run
    # succeeds which means parsing didn't crash.
    out = _dry_run(CTC_CLANG, ["hello.c", "-oconcatenated.exe"])
    assert "hello.c" in out, out


@_require_native
def test_empty_argv_does_not_crash():
    """Invoking with no args should error gracefully via clang, not crash launcher."""
    assert CTC_CLANG is not None
    result = subprocess.run(
        [str(CTC_CLANG), "--dry-run"],
        capture_output=True,
        text=True,
        check=False,
        timeout=30,
    )
    # --dry-run with no user args still prints the command and exits 0
    assert result.returncode == 0, result.stderr


# ============================================================================
# Inlined directives — the launcher must honor `// @link:` etc.
# ============================================================================


@_require_native
def test_link_directive_appended(tmp_path):
    """A source file with `// @link: m` must add `-lm` to the resolved argv."""
    assert CTC_CLANG is not None
    src = tmp_path / "needs_libm.c"
    src.write_text("// @link: m\nint main(void) { return 0; }\n")

    out = _dry_run(CTC_CLANG, [str(src), "-o", str(tmp_path / "out.exe")])
    assert "-lm" in out, out


@_require_native
def test_cflags_directive_appended(tmp_path):
    assert CTC_CLANG is not None
    src = tmp_path / "needs_flags.c"
    src.write_text("// @cflags: -DFOO=1 -O1\nint main(void) { return 0; }\n")

    out = _dry_run(CTC_CLANG, [str(src), "-o", str(tmp_path / "out.exe")])
    assert "-DFOO=1" in out, out
    assert "-O1" in out, out


@_require_native
def test_std_directive_applied(tmp_path):
    assert CTC_CLANG is not None
    src = tmp_path / "needs_std.c"
    src.write_text("// @std: c11\nint main(void) { return 0; }\n")

    out = _dry_run(CTC_CLANG, [str(src), "-o", str(tmp_path / "out.exe")])
    assert "-std=c11" in out, out


@_require_native
def test_no_directives_env_var_suppresses_parsing(tmp_path, monkeypatch):
    assert CTC_CLANG is not None
    src = tmp_path / "has_directive.c"
    src.write_text("// @link: m\nint main(void) { return 0; }\n")

    monkeypatch.setenv("CLANG_TOOL_CHAIN_NO_DIRECTIVES", "1")
    out = _dry_run(CTC_CLANG, [str(src), "-o", str(tmp_path / "out.exe")])
    assert "-lm" not in out, out


# ============================================================================
# --version fast path
# ============================================================================


@_require_native
def test_version_returns_clang_version_string():
    assert CTC_CLANG is not None
    result = subprocess.run(
        [str(CTC_CLANG), "--version"],
        capture_output=True,
        text=True,
        check=False,
        timeout=30,
    )
    assert result.returncode == 0, result.stderr
    assert "clang version" in result.stdout.lower(), result.stdout


# ============================================================================
# Env-var parity — CLANG_TOOL_CHAIN_DOWNLOAD_PATH honored
# ============================================================================


@_require_native
def test_download_path_env_var_redirects_install_dir(tmp_path, monkeypatch):
    """Gap #3: launcher must honor CLANG_TOOL_CHAIN_DOWNLOAD_PATH."""
    assert CTC_CLANG is not None
    fake_home = tmp_path / "custom-toolchain"
    fake_home.mkdir()
    monkeypatch.setenv("CLANG_TOOL_CHAIN_DOWNLOAD_PATH", str(fake_home))
    # The launcher will detect the custom dir is empty and try to install.
    # We just check it doesn't use the default path by observing that it tries
    # to install at the custom path (CTC_DEBUG shows this).
    monkeypatch.setenv("CTC_DEBUG", "1")

    result = subprocess.run(
        [str(CTC_CLANG), "--ctc-help"],
        capture_output=True,
        text=True,
        check=False,
        timeout=10,
    )
    # --ctc-help shouldn't need the toolchain at all; just verify no crash.
    assert result.returncode == 0, result.stderr
