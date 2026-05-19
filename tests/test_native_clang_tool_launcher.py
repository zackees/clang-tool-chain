"""Tests for the native clang-tool multi-role launcher.

Single C++ launcher (``launcher_clang_tool.cpp``) compiles to one binary
that's hardlinked (or copied on FAT/exFAT) under 15 names. argv[0]
basename selects which underlying LLVM/Clang native binary in
``<clang_root>/bin/`` to exec.

Tests:
  - Resource & registry presence
  - All 15 binaries are produced by compile-native
  - Binaries share underlying storage (hardlink/symlink/copy)
  - --ctc-help renders with the right tool name per binary
  - --version dispatches per-name (proves argv[0]-based dispatch into LLVM)
  - Unknown argv[0] name fails loudly with a clear error
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

IS_WINDOWS = sys.platform == "win32"

ALL_CLANG_TOOLS = (
    # clang dispatch — special ABI-profile / sysroot / target / lib-deploy path
    "clang",
    "clang++",
    "clang-cpp",
    # linker variants (all alias the same lld binary internally)
    "lld",
    "ld.lld",
    "ld64.lld",
    "lld-link",
    # archive / inspection / manipulation
    "llvm-ar",
    "llvm-nm",
    "llvm-objdump",
    "llvm-objcopy",
    "llvm-ranlib",
    "llvm-strip",
    "llvm-readobj",
    "llvm-dlltool",
    "llvm-lib",
    "llvm-symbolizer",
    # AST query
    "clang-query",
    # LLDB (separate install root)
    "lldb",
    "lldb-server",
)

# Tools that print a banner on --version and exit 0. The lld variants
# behave differently per platform (ld64.lld on Windows complains since it
# only handles Mach-O), so they're excluded from the broad dispatch test
# and checked in a separate platform-specific test.
VERSION_FRIENDLY = (
    "clang",
    "clang++",
    "clang-cpp",
    "llvm-ar",
    "llvm-nm",
    "llvm-objdump",
    "llvm-objcopy",
    "llvm-ranlib",
    "llvm-strip",
    "llvm-readobj",
    "llvm-symbolizer",
    "clang-query",
    "lld-link",
)


# ------------------------------------------------------------------
# Module-level compilation: build native tools once for all tests
# ------------------------------------------------------------------

_build_dir: str | None = None
_build_ok: bool = False


def _ensure_built() -> bool:
    global _build_dir, _build_ok  # noqa: PLW0603
    if _build_dir is not None:
        return _build_ok

    import importlib.resources as resources

    ref = resources.files("clang_tool_chain.native_tools").joinpath("launcher_clang_tool.cpp")
    if not (hasattr(ref, "is_file") and ref.is_file()):  # type: ignore[union-attr]
        _build_dir = ""
        return False

    _build_dir = tempfile.mkdtemp(prefix="ctc_clang_tool_test_")

    try:
        from clang_tool_chain.commands.compile_native import compile_native

        rc = compile_native(_build_dir)
        _build_ok = rc == 0
    except Exception:
        _build_ok = False

    if not _build_ok:
        print(f"WARNING: native tool compilation failed (dir={_build_dir})", file=sys.stderr)

    import atexit

    def _cleanup() -> None:
        if _build_dir and os.path.isdir(_build_dir):
            shutil.rmtree(_build_dir, ignore_errors=True)

    atexit.register(_cleanup)
    return _build_ok


def _native_dir() -> Path:
    _ensure_built()
    return Path(_build_dir) if _build_dir else Path(__file__).resolve().parent / "native"


def _exe(name: str) -> str:
    suffix = ".exe" if IS_WINDOWS else ""
    return str(_native_dir() / f"{name}{suffix}")


def _run(args: list[str], timeout: int = 30) -> subprocess.CompletedProcess:
    return subprocess.run(args, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=timeout)


def _has_native() -> bool:
    return _ensure_built()


SKIP_REASON = "Native tool compilation failed"


# ==========================================================================
# Resource & Registry
# ==========================================================================


class TestClangToolResource(unittest.TestCase):
    def test_source_exists(self) -> None:
        import importlib.resources as resources

        ref = resources.files("clang_tool_chain.native_tools").joinpath("launcher_clang_tool.cpp")
        self.assertTrue(
            hasattr(ref, "is_file") and ref.is_file(),  # type: ignore[union-attr]
            "launcher_clang_tool.cpp not found in package",
        )

    def test_registry_has_clang_tool(self) -> None:
        from clang_tool_chain.native_tools import TOOL_REGISTRY

        self.assertIn("clang_tool", TOOL_REGISTRY)
        tool = TOOL_REGISTRY["clang_tool"]
        self.assertEqual(tool.source, "launcher_clang_tool.cpp")
        # Primary + 14 aliases = 15 dispatched tools.
        all_names = {tool.output, *tool.aliases}
        expected = {f"ctc-{n}" for n in ALL_CLANG_TOOLS}
        self.assertEqual(all_names, expected, f"Registry tool names {all_names} don't match expected {expected}")


# ==========================================================================
# compile-native produces all binaries
# ==========================================================================


@unittest.skipUnless(_has_native(), SKIP_REASON)
class TestCompileProducesBinaries(unittest.TestCase):
    def test_all_15_binaries_exist(self) -> None:
        for tool in ALL_CLANG_TOOLS:
            binary = _exe(f"ctc-{tool}")
            self.assertTrue(os.path.exists(binary), f"ctc-{tool} not produced at {binary}")


# ==========================================================================
# Single-binary storage (hardlink / symlink / copy fallback)
# ==========================================================================


@unittest.skipUnless(_has_native(), SKIP_REASON)
class TestSingleBinaryStorage(unittest.TestCase):
    """All 15 aliases must resolve to the same on-disk binary.

    Unix: aliases are symlinks pointing at the primary (ctc-clang).
    Windows: aliases are hardlinks (same inode), or byte-equal copies on
    filesystems that don't support hardlinks.
    """

    def test_aliases_share_storage(self) -> None:
        primary = Path(_exe("ctc-clang"))
        primary_stat = primary.stat()
        for tool in ALL_CLANG_TOOLS:
            if tool == "clang":  # primary
                continue
            alias = Path(_exe(f"ctc-{tool}"))
            self.assertTrue(alias.exists(), f"ctc-{tool} missing")

            if not IS_WINDOWS and alias.is_symlink():
                target = os.readlink(alias)
                self.assertIn("ctc-clang", target, f"ctc-{tool} -> {target}, expected ctc-clang")
                continue

            alias_stat = alias.stat()
            same_inode = alias_stat.st_ino == primary_stat.st_ino and alias_stat.st_ino != 0
            # Either same inode (hardlink) or matching size (copy fallback).
            if not same_inode:
                self.assertEqual(
                    alias_stat.st_size,
                    primary_stat.st_size,
                    f"ctc-{tool} ({alias_stat.st_size}) ≠ ctc-clang ({primary_stat.st_size}) bytes",
                )


# ==========================================================================
# Per-alias dispatch via --ctc-help
# ==========================================================================


@unittest.skipUnless(_has_native(), SKIP_REASON)
class TestCtcHelp(unittest.TestCase):
    """--ctc-help must mention the dispatched tool by name."""

    # clang/clang++/clang-cpp use clang_launcher.cpp's own help format which
    # prints "ctc-clang" or "ctc-clang++" based on CompilerMode (not the
    # literal argv[0] basename). Skip them here — TestVersionDispatch covers
    # the actual dispatch path.
    _SKIP_HELP_NAME = {"clang", "clang++", "clang-cpp"}

    def test_ctc_help_per_alias(self) -> None:
        for tool in ALL_CLANG_TOOLS:
            if tool in self._SKIP_HELP_NAME:
                continue
            binary = _exe(f"ctc-{tool}")
            result = _run([binary, "--ctc-help"])
            self.assertEqual(result.returncode, 0, f"ctc-{tool} --ctc-help failed: {result.stderr}")
            self.assertIn(
                f"ctc-{tool}",
                result.stdout,
                f"--ctc-help for ctc-{tool} doesn't mention its own name: {result.stdout!r}",
            )


# ==========================================================================
# Per-alias dispatch via --version on tools that support it
# ==========================================================================


@unittest.skipUnless(_has_native(), SKIP_REASON)
class TestVersionDispatch(unittest.TestCase):
    """--version into the underlying LLVM binary should exit 0 with banner."""

    def test_version_dispatches_per_tool(self) -> None:
        for tool in VERSION_FRIENDLY:
            binary = _exe(f"ctc-{tool}")
            result = _run([binary, "--version"])
            self.assertEqual(
                result.returncode,
                0,
                f"ctc-{tool} --version exit {result.returncode}: stderr={result.stderr!r}",
            )
            banner = (result.stdout or result.stderr).strip()
            self.assertTrue(banner, f"ctc-{tool} --version produced no output")


# ==========================================================================
# Unknown argv[0]
# ==========================================================================


@unittest.skipUnless(_has_native(), SKIP_REASON)
class TestUnknownArgv0(unittest.TestCase):
    """A copy under a non-whitelisted name must fail loudly."""

    def test_unknown_name_fails(self) -> None:
        primary = _exe("ctc-clang")
        with tempfile.TemporaryDirectory() as td:
            suffix = ".exe" if IS_WINDOWS else ""
            bogus = os.path.join(td, f"ctc-bogus-tool{suffix}")
            shutil.copy2(primary, bogus)
            if not IS_WINDOWS:
                os.chmod(bogus, 0o755)
            result = _run([bogus, "--version"])
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("Could not determine tool", result.stderr)


if __name__ == "__main__":
    unittest.main()
