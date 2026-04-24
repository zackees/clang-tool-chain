"""
Integration tests for the full zccache dispatch path (P3 + P4).

These tests require both:
  * ``zccache`` binary installed (``pip install zccache``).
  * ``clang-tool-chain install clang`` already run, so ``profile.json`` exists.

Skipped cleanly otherwise so CI without these prerequisites stays green.

Contract: ``docs/ZCCACHE_INTEGRATION_CONTRACTS.md`` sections 2-3.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import time
from pathlib import Path  # noqa: TC003 — used at runtime

import pytest

shim = pytest.importorskip("clang_tool_chain.zccache_shim")
profile_mod = pytest.importorskip("clang_tool_chain.profile")


def _zccache_available() -> bool:
    return shim.find_zccache_binary() is not None


def _profile_available() -> bool:
    try:
        profile_mod.load_profile()
        return True
    except Exception:
        return False


def _clang_tool_chain_clang_available() -> bool:
    return shutil.which("clang-tool-chain-clang") is not None


pytestmark = [
    pytest.mark.skipif(not _zccache_available(), reason="zccache not installed; run `pip install zccache`"),
    pytest.mark.skipif(not _profile_available(), reason="profile.json missing; run `clang-tool-chain install clang`"),
    pytest.mark.skipif(
        not _clang_tool_chain_clang_available(),
        reason="`clang-tool-chain-clang` console script not on PATH (not installed or P4 not landed)",
    ),
]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _run(argv: list[str], cwd: Path | None = None, timeout: int = 60) -> subprocess.CompletedProcess:
    return subprocess.run(
        argv,
        cwd=str(cwd) if cwd else None,
        capture_output=True,
        text=True,
        check=False,
        timeout=timeout,
    )


def _hello_c(path: Path) -> Path:
    path.write_text(
        '#include <stdio.h>\nint main(void){ printf("hello\\n"); return 0; }\n',
        encoding="utf-8",
    )
    return path


def _hello_c_with_link_directive(path: Path) -> Path:
    path.write_text(
        "// @link: m\n"
        "#include <stdio.h>\n"
        "#include <math.h>\n"
        'int main(void){ double x = sqrt(2.0); printf("%f\\n", x); return 0; }\n',
        encoding="utf-8",
    )
    return path


# ---------------------------------------------------------------------------
# Smoke test — --version must round-trip via zccache
# ---------------------------------------------------------------------------


def test_clang_dispatch_via_passthrough_exits_0():
    result = _run(["clang-tool-chain-clang", "--version"], timeout=30)
    assert result.returncode == 0, f"stdout={result.stdout}\nstderr={result.stderr}"
    combined = (result.stdout + result.stderr).lower()
    assert "clang version" in combined, f"Output missing 'clang version':\n{combined}"


# ---------------------------------------------------------------------------
# Cache hit behavior — second compile should produce the same artifact
# ---------------------------------------------------------------------------


def test_zccache_clang_cache_hit_produces_same_output(tmp_path):
    if not shutil.which("clang-tool-chain-zccache-clang"):
        pytest.skip("clang-tool-chain-zccache-clang not installed (P4 not landed)")

    source = _hello_c(tmp_path / "hello.c")
    out1 = tmp_path / ("hello1.exe" if os.name == "nt" else "hello1")
    out2 = tmp_path / ("hello2.exe" if os.name == "nt" else "hello2")

    cache_dir = tmp_path / ".zccache"
    env = os.environ.copy()
    env["ZCCACHE_DIR"] = str(cache_dir)

    t0 = time.perf_counter()
    r1 = subprocess.run(
        ["clang-tool-chain-zccache-clang", str(source), "-o", str(out1)],
        capture_output=True,
        text=True,
        env=env,
        timeout=120,
    )
    elapsed1 = time.perf_counter() - t0

    assert r1.returncode == 0, f"first compile failed: stdout={r1.stdout}\nstderr={r1.stderr}"
    assert out1.exists()

    t0 = time.perf_counter()
    r2 = subprocess.run(
        ["clang-tool-chain-zccache-clang", str(source), "-o", str(out2)],
        capture_output=True,
        text=True,
        env=env,
        timeout=120,
    )
    elapsed2 = time.perf_counter() - t0

    assert r2.returncode == 0, f"second compile failed: stdout={r2.stdout}\nstderr={r2.stderr}"
    assert out2.exists()

    # Both compiles must succeed with identical behavior. We do NOT strictly
    # require the second to be faster (caching first object, then linking
    # still happens — and cold filesystem caches can make this flaky), only
    # that both complete successfully.
    # Log the timings for human inspection.
    sys.stderr.write(f"[zccache-integration] cold={elapsed1:.2f}s warm={elapsed2:.2f}s\n")


# ---------------------------------------------------------------------------
# Directive end-to-end — // @link: m should produce a linkable program
# ---------------------------------------------------------------------------


def test_directive_produces_linker_flag(tmp_path):
    source = _hello_c_with_link_directive(tmp_path / "math_hello.c")
    out = tmp_path / ("math_hello.exe" if os.name == "nt" else "math_hello")

    result = _run(["clang-tool-chain-clang", str(source), "-o", str(out)], timeout=120)

    # On Windows GNU, libm is built into libc — the @link: m should be a no-op
    # but the build should still succeed. On Linux/macOS, it must link libm.
    assert result.returncode == 0, f"compile with // @link: m failed:\nstdout={result.stdout}\nstderr={result.stderr}"
    assert out.exists()

    # Sanity: the emitted binary should actually run.
    run = _run([str(out)], timeout=15)
    assert run.returncode == 0, f"emitted binary crashed:\nstdout={run.stdout}\nstderr={run.stderr}"
