"""Tests for the native emcc/em++ and wasm-ld launchers.

Exercises the compiled native launcher binaries (ctc-emcc, ctc-em++,
ctc-wasm-ld) by invoking them with various argument combinations.

Tests are split into:
  - Resource & compilation: verify sources exist and compile
  - Help: verify --help output
  - Mode detection: argv[0] dispatch (emcc vs em++)
  - Dry-run with templates: --compile-commands / --link-args + --dry-run
  - Template parsing: JSON array and one-arg-per-line formats
  - Clang launcher: --ctc-help and --dry-run (new flags)

Tests that need Emscripten installed are skipped if it is not available.
"""

import json
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

    ref = resources.files("clang_tool_chain.native_tools").joinpath("launcher_emcc.cpp")
    if not (hasattr(ref, "is_file") and ref.is_file()):  # type: ignore[union-attr]
        _build_dir = ""
        return False

    _build_dir = tempfile.mkdtemp(prefix="ctc_emcc_test_")

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


def _create_copy(src_name: str, dst_name: str, tmp_dir: str) -> str:
    """Copy a binary with a different name for argv[0] testing."""
    suffix = ".exe" if IS_WINDOWS else ""
    src = _exe(src_name)
    dst = os.path.join(tmp_dir, f"{dst_name}{suffix}")
    shutil.copy2(src, dst)
    if not IS_WINDOWS:
        os.chmod(dst, 0o755)
    return dst


SKIP_REASON = "Native tool compilation failed"


# ==========================================================================
# Resource & Registry
# ==========================================================================


class TestEmccToolResource(unittest.TestCase):
    """Verify emcc/wasm-ld sources are accessible and registered."""

    def test_emcc_source_exists(self) -> None:
        import importlib.resources as resources

        ref = resources.files("clang_tool_chain.native_tools").joinpath("launcher_emcc.cpp")
        self.assertTrue(
            hasattr(ref, "is_file") and ref.is_file(),  # type: ignore[union-attr]
            "launcher_emcc.cpp not found in package",
        )

    def test_wasmld_source_exists(self) -> None:
        import importlib.resources as resources

        ref = resources.files("clang_tool_chain.native_tools").joinpath("launcher_wasmld.cpp")
        self.assertTrue(
            hasattr(ref, "is_file") and ref.is_file(),  # type: ignore[union-attr]
            "launcher_wasmld.cpp not found in package",
        )

    def test_registry_has_emcc(self) -> None:
        from clang_tool_chain.native_tools import TOOL_REGISTRY

        self.assertIn("emcc", TOOL_REGISTRY)
        tool = TOOL_REGISTRY["emcc"]
        self.assertEqual(tool.source, "launcher_emcc.cpp")
        self.assertEqual(tool.output, "ctc-emcc")
        self.assertIn("ctc-em++", tool.aliases)

    def test_registry_has_wasmld(self) -> None:
        from clang_tool_chain.native_tools import TOOL_REGISTRY

        self.assertIn("wasmld", TOOL_REGISTRY)
        tool = TOOL_REGISTRY["wasmld"]
        self.assertEqual(tool.source, "launcher_wasmld.cpp")
        self.assertEqual(tool.output, "ctc-wasm-ld")


@unittest.skipUnless(_has_native(), SKIP_REASON)
class TestCompileProducesBinaries(unittest.TestCase):
    """Verify compile_native() produces all expected binaries."""

    def test_emcc_binary_exists(self) -> None:
        self.assertTrue(os.path.exists(_exe("ctc-emcc")), "ctc-emcc not produced")

    def test_empp_binary_exists(self) -> None:
        self.assertTrue(os.path.exists(_exe("ctc-em++")), "ctc-em++ not produced")

    def test_wasmld_binary_exists(self) -> None:
        self.assertTrue(os.path.exists(_exe("ctc-wasm-ld")), "ctc-wasm-ld not produced")

    def test_clang_binary_exists(self) -> None:
        self.assertTrue(os.path.exists(_exe("ctc-clang")), "ctc-clang not produced")


# ==========================================================================
# Help flag tests
# ==========================================================================


@unittest.skipUnless(_has_native(), SKIP_REASON)
class TestEmccHelp(unittest.TestCase):
    """Test --help / -h flag for emcc launcher."""

    def test_help_flag(self) -> None:
        result = _run([_exe("ctc-emcc"), "--help"])
        self.assertEqual(result.returncode, 0, f"--help failed:\n{result.stderr}")
        self.assertIn("--compile-commands", result.stdout)
        self.assertIn("--link-args", result.stdout)
        self.assertIn("--capture-compile-commands", result.stdout)
        self.assertIn("--capture-link-args", result.stdout)
        self.assertIn("--dry-run", result.stdout)

    def test_h_flag(self) -> None:
        result = _run([_exe("ctc-emcc"), "-h"])
        self.assertEqual(result.returncode, 0, f"-h failed:\n{result.stderr}")
        self.assertIn("--compile-commands", result.stdout)

    def test_help_shows_ctc_emcc_name(self) -> None:
        result = _run([_exe("ctc-emcc"), "--help"])
        self.assertIn("ctc-emcc", result.stdout)

    def test_help_empp_shows_empp_name(self) -> None:
        """When invoked as ctc-em++, help should show ctc-em++ in usage."""
        result = _run([_exe("ctc-em++"), "--help"])
        self.assertEqual(result.returncode, 0)
        self.assertIn("ctc-em++", result.stdout)


@unittest.skipUnless(_has_native(), SKIP_REASON)
class TestWasmLdHelp(unittest.TestCase):
    """Test --help / -h flag for wasm-ld launcher."""

    def test_help_flag(self) -> None:
        result = _run([_exe("ctc-wasm-ld"), "--help"])
        self.assertEqual(result.returncode, 0, f"--help failed:\n{result.stderr}")
        self.assertIn("ctc-wasm-ld", result.stdout)
        self.assertIn("--dry-run", result.stdout)

    def test_h_flag(self) -> None:
        result = _run([_exe("ctc-wasm-ld"), "-h"])
        self.assertEqual(result.returncode, 0)
        self.assertIn("--dry-run", result.stdout)


@unittest.skipUnless(_has_native(), SKIP_REASON)
class TestClangHelp(unittest.TestCase):
    """Test --ctc-help flag for clang launcher."""

    def test_ctc_help_flag(self) -> None:
        result = _run([_exe("ctc-clang"), "--ctc-help"])
        self.assertEqual(result.returncode, 0, f"--ctc-help failed:\n{result.stderr}")
        self.assertIn("--deploy-dependencies", result.stdout)
        self.assertIn("--dry-run", result.stdout)
        self.assertIn("--ctc-help", result.stdout)


# ==========================================================================
# Mode detection (emcc vs em++)
# ==========================================================================


@unittest.skipUnless(_has_native(), SKIP_REASON)
class TestEmccModeDetection(unittest.TestCase):
    """Test argv[0] dispatch: binary name determines C vs C++ (emcc vs em++) mode."""

    def setUp(self) -> None:
        self.tmp_dir = tempfile.mkdtemp()

    def tearDown(self) -> None:
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def _mode_for(self, binary_name: str) -> str:
        """Return 'emcc' or 'em++' based on CTC_DEBUG output."""
        binary = _create_copy("ctc-emcc", binary_name, self.tmp_dir)
        result = _run([binary, "--help"], env_override={"CTC_DEBUG": "1"})
        for line in result.stderr.splitlines():
            if "mode=" in line:
                mode_str = line.split("mode=")[1].split()[0]
                return mode_str
        # Fall back to checking stdout for the name
        if "ctc-em++" in result.stdout:
            return "em++"
        return "emcc"

    def test_ctc_emcc_is_c_mode(self) -> None:
        mode = self._mode_for("ctc-emcc")
        self.assertEqual(mode, "emcc")

    def test_ctc_empp_is_cxx_mode(self) -> None:
        mode = self._mode_for("ctc-em++")
        self.assertEqual(mode, "em++")

    def test_name_with_plusplus_is_cxx(self) -> None:
        mode = self._mode_for("my-em++")
        self.assertEqual(mode, "em++")

    def test_name_with_empp_is_cxx(self) -> None:
        mode = self._mode_for("my-empp-tool")
        self.assertEqual(mode, "em++")


# ==========================================================================
# Template-based dry-run (no Emscripten needed)
# ==========================================================================


@unittest.skipUnless(_has_native(), SKIP_REASON)
class TestEmccTemplateCompile(unittest.TestCase):
    """Test --compile-commands + --dry-run: read template, substitute, print."""

    def setUp(self) -> None:
        self.tmp_dir = tempfile.mkdtemp()
        self.tmp_path = Path(self.tmp_dir)

    def tearDown(self) -> None:
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def _write_json_template(self, args: list[str]) -> str:
        path = str(self.tmp_path / "compile_template.json")
        with open(path, "w") as f:
            json.dump(args, f)
        return path

    def _write_line_template(self, args: list[str]) -> str:
        path = str(self.tmp_path / "compile_template.txt")
        with open(path, "w") as f:
            for a in args:
                f.write(a + "\n")
        return path

    def test_json_template_dry_run(self) -> None:
        """--compile-commands=template.json --dry-run substitutes and prints."""
        clang_bin = "/usr/bin/fake-clang"
        if IS_WINDOWS:
            clang_bin = "C:/fake/clang.exe"
        tmpl = self._write_json_template(
            [
                clang_bin,
                "-target",
                "wasm32",
                "-c",
                "{input}",
                "-o",
                "{output}",
            ]
        )
        result = _run(
            [
                _exe("ctc-emcc"),
                f"--compile-commands={tmpl}",
                "--dry-run",
                "-c",
                "foo.cpp",
                "-o",
                "foo.o",
            ]
        )
        self.assertEqual(result.returncode, 0, f"dry-run failed:\n{result.stderr}")
        self.assertIn(clang_bin, result.stdout)
        self.assertIn("foo.cpp", result.stdout)
        self.assertIn("foo.o", result.stdout)
        # Placeholders should be replaced
        self.assertNotIn("{input}", result.stdout)
        self.assertNotIn("{output}", result.stdout)

    def test_line_per_arg_template_dry_run(self) -> None:
        """Line-per-arg template format works with --compile-commands."""
        clang_bin = "/usr/bin/fake-clang"
        if IS_WINDOWS:
            clang_bin = "C:/fake/clang.exe"
        tmpl = self._write_line_template(
            [
                clang_bin,
                "-target",
                "wasm32",
                "-c",
                "{input}",
                "-o",
                "{output}",
            ]
        )
        result = _run(
            [
                _exe("ctc-emcc"),
                f"--compile-commands={tmpl}",
                "--dry-run",
                "-c",
                "foo.cpp",
                "-o",
                "foo.o",
            ]
        )
        self.assertEqual(result.returncode, 0, f"dry-run failed:\n{result.stderr}")
        self.assertIn("foo.cpp", result.stdout)
        self.assertIn("foo.o", result.stdout)

    def test_missing_template_file_errors(self) -> None:
        """--compile-commands with nonexistent file should fail."""
        result = _run(
            [
                _exe("ctc-emcc"),
                "--compile-commands=/nonexistent/template.json",
                "--dry-run",
                "-c",
                "foo.cpp",
                "-o",
                "foo.o",
            ]
        )
        self.assertNotEqual(result.returncode, 0)

    def test_empty_template_file_errors(self) -> None:
        """--compile-commands with empty file should fail."""
        tmpl = str(self.tmp_path / "empty.json")
        with open(tmpl, "w") as f:
            f.write("")
        result = _run(
            [
                _exe("ctc-emcc"),
                f"--compile-commands={tmpl}",
                "--dry-run",
                "-c",
                "foo.cpp",
                "-o",
                "foo.o",
            ]
        )
        self.assertNotEqual(result.returncode, 0)

    def test_template_with_spaces_in_args(self) -> None:
        """Template args with spaces should be quoted in dry-run output."""
        clang_bin = "/usr/bin/fake-clang"
        if IS_WINDOWS:
            clang_bin = "C:/fake/clang.exe"
        tmpl = self._write_json_template(
            [
                clang_bin,
                "-I/path with spaces/include",
                "-c",
                "{input}",
                "-o",
                "{output}",
            ]
        )
        result = _run(
            [
                _exe("ctc-emcc"),
                f"--compile-commands={tmpl}",
                "--dry-run",
                "-c",
                "foo.cpp",
                "-o",
                "foo.o",
            ]
        )
        self.assertEqual(result.returncode, 0)
        # Args with spaces should appear in output (quoted)
        self.assertIn("path with spaces", result.stdout)


@unittest.skipUnless(_has_native(), SKIP_REASON)
class TestEmccTemplateLink(unittest.TestCase):
    """Test --link-args + --dry-run: read template, substitute, print."""

    def setUp(self) -> None:
        self.tmp_dir = tempfile.mkdtemp()
        self.tmp_path = Path(self.tmp_dir)

    def tearDown(self) -> None:
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def test_link_args_dry_run(self) -> None:
        """--link-args=template.json --dry-run substitutes and prints."""
        ld_bin = "/usr/bin/fake-wasm-ld"
        if IS_WINDOWS:
            ld_bin = "C:/fake/wasm-ld.exe"
        tmpl_path = str(self.tmp_path / "link_template.json")
        with open(tmpl_path, "w") as f:
            json.dump(
                [
                    ld_bin,
                    "-o",
                    "{output}",
                    "{input}",
                    "--strip-debug",
                    "-lc",
                ],
                f,
            )
        result = _run(
            [
                _exe("ctc-emcc"),
                f"--link-args={tmpl_path}",
                "--dry-run",
                "foo.o",
                "-o",
                "foo.wasm",
            ]
        )
        self.assertEqual(result.returncode, 0, f"dry-run failed:\n{result.stderr}")
        self.assertIn(ld_bin, result.stdout)
        self.assertIn("foo.o", result.stdout)
        self.assertIn("foo.wasm", result.stdout)
        self.assertNotIn("{input}", result.stdout)
        self.assertNotIn("{output}", result.stdout)

    def test_missing_link_template_errors(self) -> None:
        result = _run(
            [
                _exe("ctc-emcc"),
                "--link-args=/nonexistent/link.json",
                "--dry-run",
                "foo.o",
                "-o",
                "foo.wasm",
            ]
        )
        self.assertNotEqual(result.returncode, 0)


# ==========================================================================
# Clang launcher: --dry-run and --ctc-help
# ==========================================================================


@unittest.skipUnless(_has_native(), SKIP_REASON)
class TestClangDryRun(unittest.TestCase):
    """Test --dry-run for the clang launcher."""

    def setUp(self) -> None:
        self.tmp_dir = tempfile.mkdtemp()
        self.tmp_path = Path(self.tmp_dir)
        self.test_c = str(self.tmp_path / "test.c")
        with open(self.test_c, "w") as f:
            f.write("int main() { return 0; }\n")

    def tearDown(self) -> None:
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def test_dry_run_prints_command(self) -> None:
        """--dry-run should print the clang command without executing."""
        result = _run([_exe("ctc-clang"), "--dry-run", "-c", self.test_c])
        self.assertEqual(result.returncode, 0, f"dry-run failed:\n{result.stderr}")
        # Should contain clang binary path in output
        out = result.stdout.lower()
        self.assertTrue(
            "clang" in out,
            f"Expected 'clang' in dry-run output:\n{result.stdout}",
        )
        # Should contain the source file
        self.assertIn("test.c", result.stdout)

    def test_dry_run_does_not_produce_output(self) -> None:
        """--dry-run should NOT actually compile anything."""
        out_o = str(self.tmp_path / "test.o")
        result = _run([_exe("ctc-clang"), "--dry-run", "-c", self.test_c, "-o", out_o])
        self.assertEqual(result.returncode, 0)
        self.assertFalse(os.path.exists(out_o), "Object file should not be produced in dry-run")

    def test_dry_run_not_in_clang_args(self) -> None:
        """--dry-run should be stripped from args passed to clang."""
        result = _run([_exe("ctc-clang"), "--dry-run", "-c", self.test_c])
        self.assertEqual(result.returncode, 0)
        self.assertNotIn("--dry-run", result.stdout)

    def test_dry_run_with_no_auto(self) -> None:
        """--dry-run should work with CLANG_TOOL_CHAIN_NO_AUTO=1."""
        result = _run(
            [_exe("ctc-clang"), "--dry-run", "-c", self.test_c],
            env_override={"CLANG_TOOL_CHAIN_NO_AUTO": "1"},
        )
        self.assertEqual(result.returncode, 0, f"dry-run+no_auto failed:\n{result.stderr}")
        self.assertIn("test.c", result.stdout)


# ==========================================================================
# Emcc flag parsing edge cases
# ==========================================================================


@unittest.skipUnless(_has_native(), SKIP_REASON)
class TestEmccFlagParsing(unittest.TestCase):
    """Test that launcher flags are correctly parsed and stripped."""

    def setUp(self) -> None:
        self.tmp_dir = tempfile.mkdtemp()
        self.tmp_path = Path(self.tmp_dir)

    def tearDown(self) -> None:
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def _write_template(self, name: str = "tmpl.json") -> str:
        path = str(self.tmp_path / name)
        clang_bin = "/usr/bin/fake-clang"
        if IS_WINDOWS:
            clang_bin = "C:/fake/clang.exe"
        with open(path, "w") as f:
            json.dump([clang_bin, "-c", "{input}", "-o", "{output}"], f)
        return path

    def test_compile_commands_flag_stripped(self) -> None:
        """--compile-commands= should not appear in the executed command."""
        tmpl = self._write_template()
        result = _run(
            [
                _exe("ctc-emcc"),
                f"--compile-commands={tmpl}",
                "--dry-run",
                "-c",
                "foo.cpp",
                "-o",
                "foo.o",
            ]
        )
        self.assertEqual(result.returncode, 0)
        self.assertNotIn("--compile-commands", result.stdout)

    def test_dry_run_flag_stripped(self) -> None:
        """--dry-run should not appear in the executed command."""
        tmpl = self._write_template()
        result = _run(
            [
                _exe("ctc-emcc"),
                f"--compile-commands={tmpl}",
                "--dry-run",
                "-c",
                "foo.cpp",
                "-o",
                "foo.o",
            ]
        )
        self.assertEqual(result.returncode, 0)
        self.assertNotIn("--dry-run", result.stdout)

    def test_compile_commands_value_not_truncated(self) -> None:
        """Regression: substr offset bug could truncate the file path."""
        # Use a template path that would reveal truncation
        tmpl = self._write_template("Xcompile_args.json")
        result = _run(
            [
                _exe("ctc-emcc"),
                f"--compile-commands={tmpl}",
                "--dry-run",
                "-c",
                "foo.cpp",
                "-o",
                "foo.o",
            ]
        )
        # If the path was truncated (e.g., substr(20) instead of 19),
        # the first char would be missing and the file wouldn't be found
        self.assertEqual(result.returncode, 0, f"Template path may be truncated:\n{result.stderr}")

    def test_multiple_flags_together(self) -> None:
        """Multiple launcher flags in same invocation."""
        tmpl = self._write_template()
        result = _run(
            [
                _exe("ctc-emcc"),
                f"--compile-commands={tmpl}",
                "--dry-run",
                "-c",
                "source.cpp",
                "-o",
                "output.o",
            ]
        )
        self.assertEqual(result.returncode, 0)
        self.assertIn("source.cpp", result.stdout)
        self.assertIn("output.o", result.stdout)


# ==========================================================================
# JSON template format edge cases
# ==========================================================================


@unittest.skipUnless(_has_native(), SKIP_REASON)
class TestTemplateFormats(unittest.TestCase):
    """Test various template file format edge cases."""

    def setUp(self) -> None:
        self.tmp_dir = tempfile.mkdtemp()
        self.tmp_path = Path(self.tmp_dir)

    def tearDown(self) -> None:
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def _run_with_template(self, content: str) -> subprocess.CompletedProcess:
        tmpl = str(self.tmp_path / "template.json")
        with open(tmpl, "w") as f:
            f.write(content)
        return _run(
            [
                _exe("ctc-emcc"),
                f"--compile-commands={tmpl}",
                "--dry-run",
                "-c",
                "test.cpp",
                "-o",
                "test.o",
            ]
        )

    def test_json_with_escaped_quotes(self) -> None:
        """JSON template with escaped quotes in args."""
        clang_bin = "/usr/bin/fake-clang"
        if IS_WINDOWS:
            clang_bin = "C:/fake/clang.exe"
        content = json.dumps([clang_bin, '-DFOO="bar"', "-c", "{input}", "-o", "{output}"])
        result = self._run_with_template(content)
        self.assertEqual(result.returncode, 0)
        self.assertIn("FOO", result.stdout)

    def test_json_with_backslash_paths(self) -> None:
        """JSON template with Windows-style backslash paths."""
        content = json.dumps(
            [
                "C:\\path\\to\\clang.exe",
                "-c",
                "{input}",
                "-o",
                "{output}",
            ]
        )
        result = self._run_with_template(content)
        self.assertEqual(result.returncode, 0)

    def test_line_per_arg_with_trailing_whitespace(self) -> None:
        """Line-per-arg format should handle trailing whitespace/CR."""
        clang_bin = "/usr/bin/fake-clang"
        if IS_WINDOWS:
            clang_bin = "C:/fake/clang.exe"
        content = f"{clang_bin}\r\n-c\r\n{{input}}\r\n-o\r\n{{output}}\r\n"
        result = self._run_with_template(content)
        self.assertEqual(result.returncode, 0)
        self.assertIn("test.cpp", result.stdout)

    def test_json_pretty_printed(self) -> None:
        """Pretty-printed JSON should parse correctly."""
        clang_bin = "/usr/bin/fake-clang"
        if IS_WINDOWS:
            clang_bin = "C:/fake/clang.exe"
        content = json.dumps(
            [
                clang_bin,
                "-c",
                "{input}",
                "-o",
                "{output}",
            ],
            indent=2,
        )
        result = self._run_with_template(content)
        self.assertEqual(result.returncode, 0)
        self.assertIn("test.cpp", result.stdout)


# ==========================================================================
# Emscripten availability check (used by tests below)
# ==========================================================================


def _has_emscripten() -> bool:
    """Check if Emscripten is installed and accessible."""
    try:
        from clang_tool_chain.execution.emscripten import find_emscripten_tool

        path = find_emscripten_tool("emcc")
        return path is not None and os.path.exists(str(path))
    except Exception:
        return False


SKIP_EMSCRIPTEN = "Emscripten not installed"


# ==========================================================================
# WasmLd dry-run (requires Emscripten for discovery)
# ==========================================================================


@unittest.skipUnless(_has_native(), SKIP_REASON)
@unittest.skipUnless(_has_emscripten(), SKIP_EMSCRIPTEN)
class TestWasmLdDryRun(unittest.TestCase):
    """Test wasm-ld launcher --dry-run with emscripten available."""

    def test_dry_run_shows_wasm_ld_command(self) -> None:
        """--dry-run should print the wasm-ld command and exit."""
        result = _run(
            [_exe("ctc-wasm-ld"), "--dry-run", "foo.o"],
            timeout=30,
        )
        self.assertEqual(result.returncode, 0, f"dry-run failed:\n{result.stderr}")
        out = result.stdout.lower()
        self.assertIn("wasm-ld", out)
        self.assertIn("foo.o", result.stdout)


# ==========================================================================
# Capture and round-trip tests (requires Emscripten installed)
# ==========================================================================


@unittest.skipUnless(_has_native(), SKIP_REASON)
@unittest.skipUnless(_has_emscripten(), SKIP_EMSCRIPTEN)
class TestCaptureCompileCommands(unittest.TestCase):
    """Test --capture-compile-commands: run emcc verbose, save clang template."""

    def setUp(self) -> None:
        self.tmp_dir = tempfile.mkdtemp()
        self.tmp_path = Path(self.tmp_dir)

    def tearDown(self) -> None:
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def test_capture_creates_json_file(self) -> None:
        """--capture-compile-commands should create a JSON template file."""
        src = self.tmp_path / "test.cpp"
        obj = self.tmp_path / "test.o"
        tmpl = self.tmp_path / "compile_args.json"
        src.write_text("int main() { return 0; }\n")
        result = _run(
            [
                _exe("ctc-emcc"),
                f"--capture-compile-commands={tmpl}",
                "-c",
                str(src),
                "-o",
                str(obj),
            ],
            timeout=60,
        )
        self.assertEqual(result.returncode, 0, f"Capture failed:\n{result.stderr}")
        self.assertTrue(tmpl.exists(), f"Template file not created: {tmpl}")
        content = tmpl.read_text()
        self.assertTrue(content.startswith("["), f"Not a JSON array:\n{content[:200]}")

    def test_capture_has_placeholders(self) -> None:
        """Captured template should have {input} and {output} placeholders."""
        src = self.tmp_path / "test.cpp"
        obj = self.tmp_path / "test.o"
        tmpl = self.tmp_path / "compile_args.json"
        src.write_text("int foo() { return 42; }\n")
        result = _run(
            [
                _exe("ctc-emcc"),
                f"--capture-compile-commands={tmpl}",
                "-c",
                str(src),
                "-o",
                str(obj),
            ],
            timeout=60,
        )
        self.assertEqual(result.returncode, 0, f"Capture failed:\n{result.stderr}")
        content = tmpl.read_text()
        self.assertIn("{input}", content)
        # Output placeholder may be {output} or part of -o{output}
        self.assertIn("{output}", content)
        # Source file path should NOT appear (replaced by placeholder)
        self.assertNotIn(str(src), content)

    def test_capture_produces_object_file(self) -> None:
        """--capture-compile-commands should still produce the .o output."""
        src = self.tmp_path / "test.cpp"
        obj = self.tmp_path / "test.o"
        tmpl = self.tmp_path / "compile_args.json"
        src.write_text("int bar() { return 99; }\n")
        _run(
            [
                _exe("ctc-emcc"),
                f"--capture-compile-commands={tmpl}",
                "-c",
                str(src),
                "-o",
                str(obj),
            ],
            timeout=60,
        )
        self.assertTrue(obj.exists(), "Object file not produced during capture")
        self.assertTrue(obj.stat().st_size > 0, "Object file is empty")

    def test_capture_stderr_reports_success(self) -> None:
        """stderr should report the template was saved."""
        src = self.tmp_path / "test.cpp"
        obj = self.tmp_path / "test.o"
        tmpl = self.tmp_path / "compile_args.json"
        src.write_text("int baz() { return 1; }\n")
        result = _run(
            [
                _exe("ctc-emcc"),
                f"--capture-compile-commands={tmpl}",
                "-c",
                str(src),
                "-o",
                str(obj),
            ],
            timeout=60,
        )
        self.assertIn("Saved compile template", result.stderr)

    def test_captured_template_contains_clang(self) -> None:
        """Captured compile template should reference the clang binary."""
        src = self.tmp_path / "test.cpp"
        obj = self.tmp_path / "test.o"
        tmpl = self.tmp_path / "compile_args.json"
        src.write_text("int qux() { return 7; }\n")
        result = _run(
            [
                _exe("ctc-emcc"),
                f"--capture-compile-commands={tmpl}",
                "-c",
                str(src),
                "-o",
                str(obj),
            ],
            timeout=60,
        )
        self.assertEqual(result.returncode, 0, f"Capture failed:\n{result.stderr}")
        content = tmpl.read_text().lower()
        self.assertIn("clang", content)
        self.assertIn("wasm32", content)


@unittest.skipUnless(_has_native(), SKIP_REASON)
@unittest.skipUnless(_has_emscripten(), SKIP_EMSCRIPTEN)
class TestCaptureRoundTrip(unittest.TestCase):
    """Test that captured templates can be used to compile via --compile-commands."""

    def setUp(self) -> None:
        self.tmp_dir = tempfile.mkdtemp()
        self.tmp_path = Path(self.tmp_dir)

    def tearDown(self) -> None:
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def test_roundtrip_compile(self) -> None:
        """Capture a template, then use it to compile a different file."""
        # Step 1: capture template
        src1 = self.tmp_path / "capture_src.cpp"
        obj1 = self.tmp_path / "capture_src.o"
        tmpl = self.tmp_path / "compile_template.json"
        src1.write_text("int capture_fn() { return 1; }\n")
        result = _run(
            [
                _exe("ctc-emcc"),
                f"--capture-compile-commands={tmpl}",
                "-c",
                str(src1),
                "-o",
                str(obj1),
            ],
            timeout=60,
        )
        self.assertEqual(result.returncode, 0, f"Capture failed:\n{result.stderr}")
        self.assertTrue(tmpl.exists(), "Template not created")

        # Step 2: use template to compile a different file
        src2 = self.tmp_path / "use_src.cpp"
        obj2 = self.tmp_path / "use_src.o"
        src2.write_text("int use_fn() { return 2; }\n")
        result = _run(
            [
                _exe("ctc-emcc"),
                f"--compile-commands={tmpl}",
                "-c",
                str(src2),
                "-o",
                str(obj2),
            ],
            timeout=30,
        )
        self.assertEqual(result.returncode, 0, f"Template compile failed:\n{result.stderr}")
        self.assertTrue(obj2.exists(), "Object file not produced via template")
        self.assertTrue(obj2.stat().st_size > 0, "Object file is empty")

    def test_roundtrip_dry_run(self) -> None:
        """Capture a template, then --dry-run with it to verify substitution."""
        src = self.tmp_path / "cap.cpp"
        obj = self.tmp_path / "cap.o"
        tmpl = self.tmp_path / "tmpl.json"
        src.write_text("int f() { return 0; }\n")
        _run(
            [
                _exe("ctc-emcc"),
                f"--capture-compile-commands={tmpl}",
                "-c",
                str(src),
                "-o",
                str(obj),
            ],
            timeout=60,
        )

        # Dry-run with a different source
        result = _run(
            [
                _exe("ctc-emcc"),
                f"--compile-commands={tmpl}",
                "--dry-run",
                "-c",
                "other.cpp",
                "-o",
                "other.o",
            ],
        )
        self.assertEqual(result.returncode, 0, f"Dry-run failed:\n{result.stderr}")
        self.assertIn("other.cpp", result.stdout)
        self.assertIn("other.o", result.stdout)
        self.assertNotIn("{input}", result.stdout)
        self.assertNotIn("{output}", result.stdout)


@unittest.skipUnless(_has_native(), SKIP_REASON)
@unittest.skipUnless(_has_emscripten(), SKIP_EMSCRIPTEN)
class TestCaptureLinkArgs(unittest.TestCase):
    """Test --capture-link-args: run emcc verbose link, save wasm-ld template."""

    def setUp(self) -> None:
        self.tmp_dir = tempfile.mkdtemp()
        self.tmp_path = Path(self.tmp_dir)

    def tearDown(self) -> None:
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def test_capture_link_creates_json(self) -> None:
        """--capture-link-args should create a JSON template file."""
        # First compile an object
        src = self.tmp_path / "main.cpp"
        obj = self.tmp_path / "main.o"
        src.write_text("int main() { return 0; }\n")
        result = _run(
            [_exe("ctc-emcc"), "-c", str(src), "-o", str(obj)],
            timeout=60,
        )
        self.assertEqual(result.returncode, 0, f"Compile failed:\n{result.stderr}")

        # Now capture link args
        out_js = self.tmp_path / "out.js"
        link_tmpl = self.tmp_path / "link_args.json"
        result = _run(
            [
                _exe("ctc-emcc"),
                f"--capture-link-args={link_tmpl}",
                str(obj),
                "-o",
                str(out_js),
            ],
            timeout=60,
        )
        self.assertEqual(result.returncode, 0, f"Link capture failed:\n{result.stderr}")
        self.assertTrue(link_tmpl.exists(), f"Link template not created: {link_tmpl}")
        content = link_tmpl.read_text()
        self.assertTrue(content.startswith("["), f"Not a JSON array:\n{content[:200]}")

    def test_capture_link_has_wasm_ld(self) -> None:
        """Captured link template should reference wasm-ld."""
        src = self.tmp_path / "main.cpp"
        obj = self.tmp_path / "main.o"
        src.write_text("int main() { return 0; }\n")
        _run([_exe("ctc-emcc"), "-c", str(src), "-o", str(obj)], timeout=60)

        out_js = self.tmp_path / "out.js"
        link_tmpl = self.tmp_path / "link_args.json"
        result = _run(
            [
                _exe("ctc-emcc"),
                f"--capture-link-args={link_tmpl}",
                str(obj),
                "-o",
                str(out_js),
            ],
            timeout=60,
        )
        self.assertEqual(result.returncode, 0, f"Link capture failed:\n{result.stderr}")
        content = link_tmpl.read_text().lower()
        self.assertIn("wasm-ld", content)

    def test_capture_link_has_input_placeholder(self) -> None:
        """Captured link template should have {input} for the object file."""
        src = self.tmp_path / "main.cpp"
        obj = self.tmp_path / "main.o"
        src.write_text("int main() { return 0; }\n")
        _run([_exe("ctc-emcc"), "-c", str(src), "-o", str(obj)], timeout=60)

        out_js = self.tmp_path / "out.js"
        link_tmpl = self.tmp_path / "link_args.json"
        result = _run(
            [
                _exe("ctc-emcc"),
                f"--capture-link-args={link_tmpl}",
                str(obj),
                "-o",
                str(out_js),
            ],
            timeout=60,
        )
        self.assertEqual(result.returncode, 0, f"Link capture failed:\n{result.stderr}")
        content = link_tmpl.read_text()
        self.assertIn("{input}", content)

    def test_capture_link_stderr_reports_success(self) -> None:
        """stderr should report the link template was saved."""
        src = self.tmp_path / "main.cpp"
        obj = self.tmp_path / "main.o"
        src.write_text("int main() { return 0; }\n")
        _run([_exe("ctc-emcc"), "-c", str(src), "-o", str(obj)], timeout=60)

        out_js = self.tmp_path / "out.js"
        link_tmpl = self.tmp_path / "link_args.json"
        result = _run(
            [
                _exe("ctc-emcc"),
                f"--capture-link-args={link_tmpl}",
                str(obj),
                "-o",
                str(out_js),
            ],
            timeout=60,
        )
        self.assertIn("Saved link template", result.stderr)


# ==========================================================================
# Pipe inheritance (regression test for _execv stdout/stderr loss)
# ==========================================================================


@unittest.skipUnless(_has_native(), SKIP_REASON)
class TestPipeInheritance(unittest.TestCase):
    """Verify that stdout/stderr are properly inherited through exec.

    This is a regression test for the _execv() bug on Windows where
    pipe handles from parent processes (e.g. Meson) were not inherited
    by child processes spawned via _execv(). The fix uses CreateProcess
    with STARTF_USESTDHANDLES instead.
    """

    def setUp(self) -> None:
        self.tmp_dir = tempfile.mkdtemp()
        self.tmp_path = Path(self.tmp_dir)

    def tearDown(self) -> None:
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def test_clang_stdout_captured_via_pipe(self) -> None:
        """ctc-clang --version output must be capturable via subprocess pipe."""
        result = _run([_exe("ctc-clang"), "--version"])
        self.assertEqual(result.returncode, 0, f"--version failed:\n{result.stderr}")
        self.assertTrue(
            len(result.stdout) > 0,
            "stdout is empty — pipe inheritance broken",
        )
        self.assertIn("clang", result.stdout.lower())

    def test_clang_stderr_captured_via_pipe(self) -> None:
        """ctc-clang error output must be capturable via subprocess pipe."""
        # Pass a nonexistent file — clang should emit error to stderr
        result = _run([_exe("ctc-clang"), "-c", "/nonexistent_file_12345.c"])
        self.assertNotEqual(result.returncode, 0)
        self.assertTrue(
            len(result.stderr) > 0,
            "stderr is empty — pipe inheritance broken",
        )

    def test_clang_compile_stdout_stderr_inherited(self) -> None:
        """Real compile: both stdout and stderr should flow through pipes."""
        src = self.tmp_path / "pipe_test.c"
        obj = self.tmp_path / "pipe_test.o"
        src.write_text('#pragma message("PIPE_TEST_DIAG")\nint main() { return 0; }\n')
        result = _run([_exe("ctc-clang"), "-c", str(src), "-o", str(obj)])
        self.assertEqual(result.returncode, 0, f"Compile failed:\n{result.stderr}")
        self.assertTrue(obj.exists(), "Object file not produced")
        # #pragma message goes to stderr
        self.assertIn("PIPE_TEST_DIAG", result.stderr)

    def test_clang_preprocess_stdout_inherited(self) -> None:
        """Preprocessor output (-E) must flow through stdout pipe."""
        src = self.tmp_path / "pipe_pp.c"
        src.write_text("#define PIPE_MARKER 42\nint x = PIPE_MARKER;\n")
        result = _run([_exe("ctc-clang"), "-E", str(src)])
        self.assertEqual(result.returncode, 0, f"-E failed:\n{result.stderr}")
        self.assertIn("42", result.stdout)


if __name__ == "__main__":
    unittest.main()
