"""
Perf regression test for the native `ctc-clang` trampoline.

`ctc-clang --version` uses the cached-version fast path (clang_launcher.cpp:1960):
no subprocess spawn, no flag parsing, no toolchain touch after the cache is
warm. Wall-clock for this invocation is almost entirely process-creation
overhead on the host OS, and should stay well under the perf target below.

If this test fires, either the launcher grew import-time cost, the console
script preamble (if any wraps it) regressed, or the test is running on
hardware slow enough to warrant raising NATIVE_VERSION_MAX_MS for that env.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
import time
from pathlib import Path

import pytest

# Generous budget: process-spawn + mmap on cold Windows can exceed 100 ms even
# for a no-op binary. The promise in issue #8 is ~50 ms; we gate at 350 ms so
# a noisy CI runner doesn't cause flakes, while still catching any ~1 s
# regression (Python-import regression would show up as ≥500 ms).
# zccache startup adds overhead vs the old ctc-clang path
NATIVE_VERSION_MAX_MS = 350

_REPO_ROOT = Path(__file__).resolve().parents[1]
_LOCAL_BUILD = _REPO_ROOT / "ctc-clang"


def _find_native_binary() -> Path | None:
    name = "ctc-clang.exe" if sys.platform == "win32" else "ctc-clang"
    local = _LOCAL_BUILD / name
    if local.exists():
        return local
    found = shutil.which("ctc-clang")
    return Path(found) if found else None


CTC_CLANG = _find_native_binary()


@pytest.mark.skipif(
    CTC_CLANG is None,
    reason="ctc-clang native binary not built",
)
def test_native_version_startup_under_budget():
    assert CTC_CLANG is not None

    # Warm up: first call may pay for the version-cache write.
    subprocess.run([str(CTC_CLANG), "--version"], capture_output=True, check=True, timeout=30)

    samples_ms: list[float] = []
    for _ in range(5):
        t0 = time.perf_counter()
        result = subprocess.run(
            [str(CTC_CLANG), "--version"],
            capture_output=True,
            check=True,
            timeout=30,
        )
        elapsed_ms = (time.perf_counter() - t0) * 1000
        assert b"clang version" in result.stdout.lower(), result.stdout
        samples_ms.append(elapsed_ms)

    samples_ms.sort()
    median = samples_ms[len(samples_ms) // 2]
    assert median < NATIVE_VERSION_MAX_MS, (
        f"Native `ctc-clang --version` median {median:.1f} ms exceeded "
        f"{NATIVE_VERSION_MAX_MS} ms budget. Samples: "
        f"{[f'{x:.1f}' for x in samples_ms]}"
    )
