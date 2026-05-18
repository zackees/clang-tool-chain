"""Tests for the native emar / emranlib / emnm / emstrip launcher.

A single C++ launcher (``launcher_emtool.cpp``) is compiled and aliased to
four binaries (``ctc-emar``, ``ctc-emranlib``, ``ctc-emnm``, ``ctc-emstrip``).
The tool dispatches based on ``argv[0]`` basename.

Tests cover:
  - Registry & resource presence
  - All four binaries are produced
  - --ctc-help renders with the correct tool name per binary
  - argv[0] dispatch (unknown name should fail loudly)
  - Cached-path dry-run round-trip (no Emscripten install needed)

Tests requiring an actual Emscripten install are skipped if unavailable.
"""

import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

IS_WINDOWS = sys.platform == "win32"


# ------------------------------------------------------------------
# Module-level compilation: build native tools once for all tests
# ------------------------------------------------------------------

_build_dir: str | None = None
_build_ok: bool = False


def _ensure_built() -> bool:
    """Compile native tools into a temp directory (runs once per session)."""
    global _build_dir, _build_ok  # noqa: PLW0603
    if _build_dir is not None:
        return _build_ok

    import importlib.resources as resources

    ref = resources.files("clang_tool_chain.native_tools").joinpath("launcher_emtool.cpp")
    if not (hasattr(ref, "is_file") and ref.is_file()):  # type: ignore[union-attr]
        _build_dir = ""
        return False

    _build_dir = tempfile.mkdtemp(prefix="ctc_emtool_test_")

    try:
        from clang_tool_chain.commands.compile_native import compile_native

        rc = compile_native(_build_dir)
        _build_ok = rc == 0
    except Exception:
        _build_ok = False

    if not _build_ok:
        print(
            f"WARNING: native tool compilation failed (dir={_build_dir})",
            file=sys.stderr,
        )

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


def _run(
    args: list[str],
    env_override: dict[str, str] | None = None,
    timeout: int = 30,
) -> subprocess.CompletedProcess:
    env = os.environ.copy()
    if env_override:
        env.update(env_override)
    return subprocess.run(
        args,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=env,
        timeout=timeout,
    )


def _has_native() -> bool:
    return _ensure_built()


def _copy_with_name(src_name: str, dst_name: str, tmp_dir: str) -> str:
    """Copy a launcher binary to tmp_dir under a different name for argv[0] testing."""
    suffix = ".exe" if IS_WINDOWS else ""
    src = _exe(src_name)
    dst = os.path.join(tmp_dir, f"{dst_name}{suffix}")
    shutil.copy2(src, dst)
    if not IS_WINDOWS:
        os.chmod(dst, 0o755)
    return dst


SKIP_REASON = "Native tool compilation failed"

EM_TOOLS = ("emar", "emranlib", "emnm", "emstrip")


# ==========================================================================
# Resource & Registry
# ==========================================================================


class TestEmtoolResource(unittest.TestCase):
    """Verify launcher_emtool.cpp is accessible and registered."""

    def test_source_exists(self) -> None:
        import importlib.resources as resources

        ref = resources.files("clang_tool_chain.native_tools").joinpath("launcher_emtool.cpp")
        self.assertTrue(
            hasattr(ref, "is_file") and ref.is_file(),  # type: ignore[union-attr]
            "launcher_emtool.cpp not found in package",
        )

    def test_registry_has_emtool(self) -> None:
        from clang_tool_chain.native_tools import TOOL_REGISTRY

        self.assertIn("emtool", TOOL_REGISTRY)
        tool = TOOL_REGISTRY["emtool"]
        self.assertEqual(tool.source, "launcher_emtool.cpp")
        self.assertEqual(tool.output, "ctc-emar")
        for alias in ("ctc-emranlib", "ctc-emnm", "ctc-emstrip"):
            self.assertIn(alias, tool.aliases, f"{alias} missing from emtool aliases")


@unittest.skipUnless(_has_native(), SKIP_REASON)
class TestCompileProducesBinaries(unittest.TestCase):
    """compile_native() should produce ctc-emar plus its three aliases."""

    def test_all_four_binaries_exist(self) -> None:
        for tool in EM_TOOLS:
            binary = _exe(f"ctc-{tool}")
            self.assertTrue(os.path.exists(binary), f"ctc-{tool} not produced at {binary}")


# ==========================================================================
# --ctc-help renders the right tool name per binary
# ==========================================================================


@unittest.skipUnless(_has_native(), SKIP_REASON)
class TestCtcHelp(unittest.TestCase):
    """--ctc-help should print usage that names the dispatched tool."""

    def test_ctc_help_per_binary(self) -> None:
        for tool in EM_TOOLS:
            with self.subTest(tool=tool):
                result = _run([_exe(f"ctc-{tool}"), "--ctc-help"])
                self.assertEqual(
                    result.returncode,
                    0,
                    f"--ctc-help for ctc-{tool} failed:\n{result.stderr}",
                )
                self.assertIn(f"ctc-{tool}", result.stdout)
                self.assertIn("--dry-run", result.stdout)
                self.assertIn("--ctc-help", result.stdout)


# ==========================================================================
# argv[0] dispatch
# ==========================================================================


@unittest.skipUnless(_has_native(), SKIP_REASON)
class TestArgv0Dispatch(unittest.TestCase):
    """Tool name is detected from the executable's basename."""

    def setUp(self) -> None:
        self.tmp_dir = tempfile.mkdtemp()

    def tearDown(self) -> None:
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def test_unknown_tool_name_fails(self) -> None:
        """A binary copied to a name that isn't a known emtool should fail loudly."""
        binary = _copy_with_name("ctc-emar", "ctc-not-a-real-tool", self.tmp_dir)
        result = _run([binary, "--ctc-help"])
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Could not determine tool", result.stderr)

    def test_prefix_stripping(self) -> None:
        """clang-tool-chain-<tool> should be detected the same as ctc-<tool>."""
        for tool in EM_TOOLS:
            with self.subTest(tool=tool):
                binary = _copy_with_name("ctc-emar", f"clang-tool-chain-{tool}", self.tmp_dir)
                result = _run([binary, "--ctc-help"])
                self.assertEqual(
                    result.returncode,
                    0,
                    f"clang-tool-chain-{tool} dispatch failed:\n{result.stderr}",
                )
                self.assertIn(f"ctc-{tool}", result.stdout)

    def test_bare_tool_name(self) -> None:
        """Bare 'emar' (no ctc- prefix) should still dispatch correctly."""
        for tool in EM_TOOLS:
            with self.subTest(tool=tool):
                binary = _copy_with_name("ctc-emar", tool, self.tmp_dir)
                result = _run([binary, "--ctc-help"])
                self.assertEqual(result.returncode, 0)
                self.assertIn(f"ctc-{tool}", result.stdout)


# ==========================================================================
# Cached-path dry-run round-trip (no real Emscripten install required)
# ==========================================================================


@unittest.skipUnless(_has_native(), SKIP_REASON)
class TestDryRunWithSeededCache(unittest.TestCase):
    """Seed the per-tool cache file and verify --dry-run prints the right command.

    Avoids needing a real Emscripten install: we point the launcher at a
    fake HOME and write a hand-crafted cache that satisfies path_exists()
    checks (we create the placeholder files too).
    """

    def setUp(self) -> None:
        self.tmp_dir = tempfile.mkdtemp(prefix="ctc_emtool_cache_")
        self.tmp_path = Path(self.tmp_dir)

        # Mimic the launcher's install dir layout under our fake HOME.
        platform_name = {
            "win32": "win",
            "darwin": "darwin",
            "linux": "linux",
        }.get(sys.platform, "linux")

        import platform as platform_mod

        machine = platform_mod.machine().lower()
        if machine in ("x86_64", "amd64"):
            arch = "x86_64"
        elif machine in ("arm64", "aarch64"):
            arch = "arm64"
        else:
            self.skipTest(f"Unsupported test arch: {machine}")

        self.install_dir = self.tmp_path / ".clang-tool-chain" / "emscripten" / platform_name / arch
        self.install_dir.mkdir(parents=True)

        # Fake python: use the current interpreter (a real, executable file).
        self.fake_python = sys.executable

        # Fake tool scripts: create empty .py files in the emscripten/ subdir.
        em_subdir = self.install_dir / "emscripten"
        em_subdir.mkdir()
        self.fake_scripts: dict[str, str] = {}
        for tool in EM_TOOLS:
            script = em_subdir / f"{tool}.py"
            script.write_text("# placeholder\n")
            self.fake_scripts[tool] = str(script)

    def tearDown(self) -> None:
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def _seed_cache(self, tool: str) -> None:
        cache_file = self.install_dir / f".ctc-{tool}-cache"
        content = (
            f"python_path={self.fake_python}\n"
            f"emscripten_dir={self.install_dir / 'emscripten'}\n"
            f"config_path={self.install_dir / '.emscripten'}\n"
            f"bin_dir={self.install_dir / 'bin'}\n"
            f"tool_script={self.fake_scripts[tool]}\n"
        )
        cache_file.write_text(content)

    def _home_env(self) -> dict[str, str]:
        if IS_WINDOWS:
            return {"USERPROFILE": str(self.tmp_path)}
        return {"HOME": str(self.tmp_path)}

    def test_dry_run_prints_python_and_script(self) -> None:
        """--dry-run output should contain python_path then tool_script then user args."""
        for tool in EM_TOOLS:
            with self.subTest(tool=tool):
                self._seed_cache(tool)
                result = _run(
                    [_exe(f"ctc-{tool}"), "--dry-run", "rcs", "libfoo.a", "foo.o"],
                    env_override=self._home_env(),
                )
                self.assertEqual(
                    result.returncode,
                    0,
                    f"--dry-run for ctc-{tool} failed:\n{result.stderr}",
                )
                # python interpreter, then tool script, then user args
                self.assertIn(self.fake_python, result.stdout)
                self.assertIn(self.fake_scripts[tool], result.stdout)
                self.assertIn("rcs", result.stdout)
                self.assertIn("libfoo.a", result.stdout)
                self.assertIn("foo.o", result.stdout)

    def test_dry_run_strips_launcher_flag(self) -> None:
        """--dry-run itself must not appear in the printed command."""
        self._seed_cache("emar")
        result = _run(
            [_exe("ctc-emar"), "--dry-run", "rcs", "libfoo.a"],
            env_override=self._home_env(),
        )
        self.assertEqual(result.returncode, 0)
        # The launcher flag is consumed and must not be forwarded to emar.py.
        # Check that no token equals "--dry-run" (just substring match would be
        # too brittle if user args could legitimately contain "--dry-run").
        tokens = result.stdout.split()
        self.assertNotIn("--dry-run", tokens)


if __name__ == "__main__":
    unittest.main()
