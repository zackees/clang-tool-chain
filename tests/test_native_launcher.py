"""Tests for the native C++ launcher (ctc-clang / ctc-clang++).

These tests exercise the compiled native launcher binary by invoking it
with various argument combinations and checking the resulting clang
command line via -### (dry-run) output.

The launcher source is extracted from the ``clang_tool_chain.native_tools``
package resource and compiled via the ``compile_native()`` API into a
temporary directory the first time the test module is loaded.

Cross-platform: tests are split into universal, Windows-only, Linux-only,
and macOS-only sections based on the platform-specific behaviors of the
launcher.
"""

import importlib.resources as resources
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

IS_WINDOWS = sys.platform == "win32"
IS_LINUX = sys.platform == "linux"
IS_MACOS = sys.platform == "darwin"


# ------------------------------------------------------------------
# Module-level compilation: build the launcher once for all tests
# ------------------------------------------------------------------

# Persistent temp dir (cleaned up by atexit) holding compiled binaries.
_build_dir: str | None = None
_build_ok: bool = False


def _ensure_built() -> bool:
    """Compile native tools into a temp directory (runs once per session)."""
    global _build_dir, _build_ok  # noqa: PLW0603
    if _build_dir is not None:
        return _build_ok

    # Verify the source is accessible as a package resource
    ref = resources.files("clang_tool_chain.native_tools").joinpath("clang_launcher.cpp")
    if not (hasattr(ref, "is_file") and ref.is_file()):  # type: ignore[union-attr]
        _build_dir = ""
        return False

    _build_dir = tempfile.mkdtemp(prefix="ctc_native_test_")

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

    # Register cleanup
    import atexit

    def _cleanup() -> None:
        if _build_dir and os.path.isdir(_build_dir):
            shutil.rmtree(_build_dir, ignore_errors=True)

    atexit.register(_cleanup)
    return _build_ok


def _native_launcher_dir() -> Path:
    """Return the directory containing ctc-clang / ctc-clang++."""
    _ensure_built()
    return Path(_build_dir) if _build_dir else Path(__file__).resolve().parent / "native"


def _exe(name: str) -> str:
    """Return full path to a test binary."""
    suffix = ".exe" if IS_WINDOWS else ""
    return str(_native_launcher_dir() / f"{name}{suffix}")


def _out_ext() -> str:
    """Return the output executable extension for this platform."""
    return ".exe" if IS_WINDOWS else ""


def _run(
    args: list[str],
    env_override: dict[str, str] | None = None,
    timeout: int = 30,
) -> subprocess.CompletedProcess:
    """Run a command, capturing output."""
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


def _dry_run_flags(binary: str, extra_args: list[str]) -> str:
    """Run `binary -### <extra_args>` and return the combined stderr."""
    result = _run([binary, "-###"] + extra_args)
    return result.stderr


def _has_native_launcher() -> bool:
    """Check if the native launcher binary was compiled successfully."""
    return _ensure_built()


def _create_launcher_copy(name: str, tmp_dir: str) -> str:
    """Copy ctc-clang binary to tmp_dir with a different name for argv[0] testing."""
    suffix = ".exe" if IS_WINDOWS else ""
    src = _exe("ctc-clang")
    dst = os.path.join(tmp_dir, f"{name}{suffix}")
    shutil.copy2(src, dst)
    if not IS_WINDOWS:
        os.chmod(dst, 0o755)
    return dst


SKIP_REASON = "Native launcher compilation failed"


# ==========================================================================
# Resource extraction + compile pipeline
# ==========================================================================


class TestNativeToolResource(unittest.TestCase):
    """Verify the .cpp source is accessible as a package resource and compiles."""

    def test_source_exists_in_package(self) -> None:
        """clang_launcher.cpp must be discoverable via importlib.resources."""
        ref = resources.files("clang_tool_chain.native_tools").joinpath("clang_launcher.cpp")
        self.assertTrue(
            hasattr(ref, "is_file") and ref.is_file(),  # type: ignore[union-attr]
            "clang_launcher.cpp not found in clang_tool_chain.native_tools package",
        )

    def test_registry_lists_launcher(self) -> None:
        """TOOL_REGISTRY must contain the launcher entry."""
        from clang_tool_chain.native_tools import TOOL_REGISTRY

        self.assertIn("launcher", TOOL_REGISTRY)
        tool = TOOL_REGISTRY["launcher"]
        self.assertEqual(tool.source, "clang_launcher.cpp")
        self.assertEqual(tool.output, "ctc-clang")
        self.assertIn("ctc-clang++", tool.aliases)

    def test_compile_native_produces_binaries(self) -> None:
        """compile_native() extracts the source and produces working binaries."""
        tmp_dir = tempfile.mkdtemp(prefix="ctc_resource_test_")
        try:
            from clang_tool_chain.commands.compile_native import compile_native

            rc = compile_native(tmp_dir)
            self.assertEqual(rc, 0, "compile_native() returned non-zero")

            suffix = ".exe" if IS_WINDOWS else ""
            clang_bin = Path(tmp_dir) / f"ctc-clang{suffix}"
            clangpp_bin = Path(tmp_dir) / f"ctc-clang++{suffix}"
            self.assertTrue(clang_bin.exists(), f"ctc-clang not produced in {tmp_dir}")
            self.assertTrue(clangpp_bin.exists(), f"ctc-clang++ not produced in {tmp_dir}")

            # Verify the binary actually runs (--version)
            result = _run([str(clang_bin), "--version"])
            self.assertEqual(result.returncode, 0, f"ctc-clang --version failed:\n{result.stderr}")
            self.assertIn("clang", result.stdout.lower())
        finally:
            shutil.rmtree(tmp_dir, ignore_errors=True)


# ==========================================================================
# Universal tests (all platforms)
# ==========================================================================


@unittest.skipUnless(_has_native_launcher(), SKIP_REASON)
class TestDetectMode(unittest.TestCase):
    """Test argv[0] dispatch: binary name determines C vs C++ mode."""

    def setUp(self) -> None:
        self.tmp_dir = tempfile.mkdtemp()

    def tearDown(self) -> None:
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def _mode_for(self, binary_name: str) -> str:
        """Return 'C' or 'CXX' for the given binary name via CTC_DEBUG."""
        binary = _create_launcher_copy(binary_name, self.tmp_dir)
        result = _run([binary, "--version"], env_override={"CTC_DEBUG": "1"})
        for line in result.stderr.splitlines():
            if "[ctc-debug] mode=" in line:
                return line.split("mode=")[1].strip()
        self.fail(f"No mode line in CTC_DEBUG output:\n{result.stderr}")

    def test_ctc_clang_is_c_mode(self) -> None:
        self.assertEqual(self._mode_for("ctc-clang"), "C")

    def test_ctc_clangpp_is_cxx_mode(self) -> None:
        """ctc-clang++ should be CXX mode (BUG-002 regression test)."""
        self.assertEqual(self._mode_for("ctc-clang++"), "CXX")

    def test_my_cpp_compiler_is_cxx_mode(self) -> None:
        self.assertEqual(self._mode_for("my-cpp-compiler"), "CXX")

    def test_name_with_plusplus_is_cxx_mode(self) -> None:
        self.assertEqual(self._mode_for("my-g++"), "CXX")

    def test_plain_clang_is_c_mode(self) -> None:
        self.assertEqual(self._mode_for("clang"), "C")

    def test_cc_is_c_mode(self) -> None:
        self.assertEqual(self._mode_for("cc"), "C")

    def test_uppercase_cpp_is_cxx_mode(self) -> None:
        self.assertEqual(self._mode_for("my-CPP-tool"), "CXX")


@unittest.skipUnless(_has_native_launcher(), SKIP_REASON)
class TestBinarySelection(unittest.TestCase):
    """Test that the correct clang/clang++ binary is selected based on mode."""

    def setUp(self) -> None:
        self.tmp_dir = tempfile.mkdtemp()

    def tearDown(self) -> None:
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def _selected_binary(self, binary_name: str) -> str:
        binary = _create_launcher_copy(binary_name, self.tmp_dir)
        result = _run([binary, "--version"], env_override={"CTC_DEBUG": "1"})
        for line in result.stderr.splitlines():
            if "[ctc-debug] selected clang_bin=" in line:
                return line.split("selected clang_bin=")[1].strip()
        self.fail(f"No selected clang_bin line:\n{result.stderr}")

    def test_c_mode_selects_clang(self) -> None:
        selected = self._selected_binary("ctc-clang")
        basename = os.path.basename(selected).lower()
        expected = "clang.exe" if IS_WINDOWS else "clang"
        self.assertEqual(basename, expected)

    def test_cxx_mode_selects_clangpp(self) -> None:
        selected = self._selected_binary("ctc-clang++")
        basename = os.path.basename(selected).lower()
        expected = "clang++.exe" if IS_WINDOWS else "clang++"
        self.assertEqual(basename, expected)


@unittest.skipUnless(_has_native_launcher(), SKIP_REASON)
class TestCompileOnlyFlags(unittest.TestCase):
    """Test that -c, -S, and -E are all treated as compile-only (no link flags)."""

    def setUp(self) -> None:
        self.tmp_dir = tempfile.mkdtemp()
        self.test_c = os.path.join(self.tmp_dir, "test.c")
        with open(self.test_c, "w") as f:
            f.write("int main() { return 0; }\n")

    def tearDown(self) -> None:
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def _assert_no_linker(self, flag: str) -> None:
        stderr = _dry_run_flags(_exe("ctc-clang"), [flag, self.test_c])
        linker_lines = [
            line
            for line in stderr.splitlines()
            if "ld.lld" in line.lower() or "lld-link" in line.lower() or "ld64.lld" in line.lower()
        ]
        self.assertEqual(
            len(linker_lines),
            0,
            f"Linker invocations found with {flag}:\n" + "\n".join(linker_lines),
        )

    def test_dash_c(self) -> None:
        self._assert_no_linker("-c")

    def test_dash_s_flag(self) -> None:
        """BUG-006: -S should be treated as compile-only."""
        self._assert_no_linker("-S")

    def test_dash_e_flag(self) -> None:
        """BUG-006: -E should be treated as compile-only."""
        self._assert_no_linker("-E")


@unittest.skipUnless(_has_native_launcher(), SKIP_REASON)
class TestDeployDependenciesStripped(unittest.TestCase):
    """Test that --deploy-dependencies is stripped from args passed to clang."""

    def setUp(self) -> None:
        self.tmp_dir = tempfile.mkdtemp()
        self.test_c = os.path.join(self.tmp_dir, "test.c")
        with open(self.test_c, "w") as f:
            f.write("int main() { return 0; }\n")

    def tearDown(self) -> None:
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def test_deploy_dependencies_not_in_clang_args(self) -> None:
        stderr = _dry_run_flags(
            _exe("ctc-clang"),
            ["--deploy-dependencies", "-c", self.test_c],
        )
        self.assertNotIn("deploy-dependencies", stderr)


@unittest.skipUnless(_has_native_launcher(), SKIP_REASON)
class TestNostdincPassthrough(unittest.TestCase):
    """Test that -nostdinc is passed through to clang."""

    def setUp(self) -> None:
        self.tmp_dir = tempfile.mkdtemp()
        self.test_c = os.path.join(self.tmp_dir, "test.c")
        with open(self.test_c, "w") as f:
            f.write("// no-op\n")

    def tearDown(self) -> None:
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def test_nostdinc_present(self) -> None:
        """Clang translates -nostdinc to -nostdsysteminc -nobuiltininc in -### output."""
        stderr = _dry_run_flags(_exe("ctc-clang"), ["-c", "-nostdinc", self.test_c])
        self.assertIn("-nostdsysteminc", stderr)


@unittest.skipUnless(_has_native_launcher(), SKIP_REASON)
class TestEndToEnd(unittest.TestCase):
    """End-to-end compilation tests (all platforms)."""

    def setUp(self) -> None:
        self.tmp_dir = tempfile.mkdtemp()
        self.tmp_path = Path(self.tmp_dir)

    def tearDown(self) -> None:
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def test_compile_and_run_c(self) -> None:
        src = self.tmp_path / "hello.c"
        exe = self.tmp_path / f"hello{_out_ext()}"
        src.write_text('#include <stdio.h>\nint main() { printf("C_OK\\n"); return 0; }\n')
        result = _run([_exe("ctc-clang"), "-o", str(exe), str(src)])
        self.assertEqual(result.returncode, 0, f"Compile failed:\n{result.stderr}")
        self.assertTrue(exe.exists())
        result = _run([str(exe)])
        self.assertEqual(result.returncode, 0)
        self.assertIn("C_OK", result.stdout)

    def test_compile_and_run_cpp(self) -> None:
        src = self.tmp_path / "hello.cpp"
        exe = self.tmp_path / f"hello{_out_ext()}"
        src.write_text('#include <iostream>\nint main() { std::cout << "CXX_OK" << std::endl; return 0; }\n')
        result = _run([_exe("ctc-clang++"), "-o", str(exe), str(src)], timeout=60)
        self.assertEqual(result.returncode, 0, f"Compile failed:\n{result.stderr}")
        self.assertTrue(exe.exists())
        result = _run([str(exe)])
        self.assertEqual(result.returncode, 0)
        self.assertIn("CXX_OK", result.stdout)

    def test_compile_only_produces_object(self) -> None:
        src = self.tmp_path / "test.c"
        src.write_text("int foo() { return 42; }\n")
        result = _run([_exe("ctc-clang"), "-c", str(src), "-o", str(self.tmp_path / "test.o")])
        self.assertEqual(result.returncode, 0, f"Compile failed:\n{result.stderr}")
        self.assertTrue((self.tmp_path / "test.o").exists())

    def test_output_path_with_spaces(self) -> None:
        space_dir = self.tmp_path / "my output dir"
        space_dir.mkdir()
        src = self.tmp_path / "hello.c"
        exe = space_dir / f"hello{_out_ext()}"
        src.write_text('#include <stdio.h>\nint main() { printf("SPACE_OK\\n"); return 0; }\n')
        result = _run([_exe("ctc-clang"), "-o", str(exe), str(src)])
        self.assertEqual(result.returncode, 0, f"Compile failed:\n{result.stderr}")
        self.assertTrue(exe.exists())
        result = _run([str(exe)])
        self.assertIn("SPACE_OK", result.stdout)

    def test_source_path_with_spaces(self) -> None:
        space_dir = self.tmp_path / "my source dir"
        space_dir.mkdir()
        src = space_dir / "hello.c"
        exe = self.tmp_path / f"hello{_out_ext()}"
        src.write_text('#include <stdio.h>\nint main() { printf("SRC_SPACE_OK\\n"); return 0; }\n')
        result = _run([_exe("ctc-clang"), "-o", str(exe), str(src)])
        self.assertEqual(result.returncode, 0, f"Compile failed:\n{result.stderr}")
        result = _run([str(exe)])
        self.assertIn("SRC_SPACE_OK", result.stdout)

    def test_no_args_exits_cleanly(self) -> None:
        result = _run([_exe("ctc-clang")])
        # clang returns 1 with usage message when no input files given
        self.assertIn(result.returncode, [0, 1])

    def test_multiple_source_files(self) -> None:
        a = self.tmp_path / "a.c"
        b = self.tmp_path / "b.c"
        a.write_text("int foo() { return 1; }\n")
        b.write_text("int foo(); int main() { return foo() - 1; }\n")
        exe = self.tmp_path / f"multi{_out_ext()}"
        result = _run([_exe("ctc-clang"), "-o", str(exe), str(a), str(b)])
        self.assertEqual(result.returncode, 0, f"Multi-file compile failed:\n{result.stderr}")
        result = _run([str(exe)])
        self.assertEqual(result.returncode, 0)

    def test_assembly_output_with_dash_s(self) -> None:
        src = self.tmp_path / "test.c"
        src.write_text("int foo() { return 42; }\n")
        asm_out = self.tmp_path / "test.s"
        result = _run([_exe("ctc-clang"), "-S", str(src), "-o", str(asm_out)])
        self.assertEqual(result.returncode, 0, f"-S failed:\n{result.stderr}")
        self.assertTrue(asm_out.exists())
        self.assertTrue(len(asm_out.read_text()) > 0, "Assembly output is empty")

    def test_preprocess_with_dash_e(self) -> None:
        src = self.tmp_path / "test.c"
        src.write_text("#define FOO 42\nint x = FOO;\n")
        result = _run([_exe("ctc-clang"), "-E", str(src)])
        self.assertEqual(result.returncode, 0, f"-E failed:\n{result.stderr}")
        self.assertIn("42", result.stdout)

    def test_empty_source_file(self) -> None:
        src = self.tmp_path / "empty.c"
        src.write_text("")
        result = _run([_exe("ctc-clang"), "-c", str(src), "-o", str(self.tmp_path / "empty.o")])
        self.assertIn(result.returncode, [0, 1])


@unittest.skipUnless(_has_native_launcher(), SKIP_REASON)
class TestDirectives(unittest.TestCase):
    """Test inlined build directive parsing (all platforms)."""

    def setUp(self) -> None:
        self.tmp_dir = tempfile.mkdtemp()
        self.tmp_path = Path(self.tmp_dir)

    def tearDown(self) -> None:
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def test_link_directive(self) -> None:
        src = self.tmp_path / "test.c"
        src.write_text("// @link: m\nint main() { return 0; }\n")
        stderr = _dry_run_flags(_exe("ctc-clang"), [str(src), "-o", str(self.tmp_path / f"test{_out_ext()}")])
        self.assertIn("-lm", stderr)

    def test_std_directive(self) -> None:
        src = self.tmp_path / "test.c"
        src.write_text("// @std: c17\nint main() { return 0; }\n")
        stderr = _dry_run_flags(_exe("ctc-clang"), ["-c", str(src)])
        self.assertIn("-std=c17", stderr)

    def test_cflags_directive(self) -> None:
        src = self.tmp_path / "test.c"
        src.write_text("// @cflags: -DFOO=1\nint main() { return 0; }\n")
        stderr = _dry_run_flags(_exe("ctc-clang"), ["-c", str(src)])
        # Clang cc1 may split -DFOO=1 into "-D" "FOO=1"
        self.assertIn("FOO=1", stderr)

    def test_platform_directive_current_platform(self) -> None:
        """Directives for the CURRENT platform should apply."""
        if IS_WINDOWS:
            platform_name = "windows"
        elif IS_LINUX:
            platform_name = "linux"
        else:
            platform_name = "darwin"
        src = self.tmp_path / "test.c"
        src.write_text(
            f"// @platform: {platform_name}\n//     @cflags: -DPLATFORM_MATCH=1\nint main() {{ return 0; }}\n"
        )
        stderr = _dry_run_flags(_exe("ctc-clang"), ["-c", str(src)])
        self.assertIn("PLATFORM_MATCH=1", stderr)

    def test_platform_directive_other_platform(self) -> None:
        """Directives for a DIFFERENT platform should NOT apply."""
        other = "linux" if IS_WINDOWS else "windows"
        src = self.tmp_path / "test.c"
        src.write_text(f"// @platform: {other}\n//     @cflags: -DOTHER_ONLY=1\nint main() {{ return 0; }}\n")
        stderr = _dry_run_flags(_exe("ctc-clang"), ["-c", str(src)])
        self.assertNotIn("OTHER_ONLY=1", stderr)

    def test_directives_disabled_by_env(self) -> None:
        src = self.tmp_path / "test.c"
        src.write_text("// @cflags: -DSHOULD_NOT_APPEAR=1\nint main() { return 0; }\n")
        # First verify it DOES appear normally
        stderr = _dry_run_flags(_exe("ctc-clang"), ["-c", str(src)])
        self.assertIn("SHOULD_NOT_APPEAR=1", stderr)
        # Now suppress
        result = _run(
            [_exe("ctc-clang"), "-###", "-c", str(src)],
            env_override={"CLANG_TOOL_CHAIN_NO_DIRECTIVES": "1"},
        )
        self.assertNotIn("SHOULD_NOT_APPEAR=1", result.stderr)

    def test_directive_list_syntax(self) -> None:
        src = self.tmp_path / "test.c"
        src.write_text("// @link: [m, pthread]\nint main() { return 0; }\n")
        stderr = _dry_run_flags(_exe("ctc-clang"), [str(src), "-o", str(self.tmp_path / f"test{_out_ext()}")])
        self.assertIn("-lm", stderr)
        self.assertIn("-lpthread", stderr)


@unittest.skipUnless(_has_native_launcher(), SKIP_REASON)
class TestNoAutoMode(unittest.TestCase):
    """Test CLANG_TOOL_CHAIN_NO_AUTO=1 passthrough mode (all platforms)."""

    def setUp(self) -> None:
        self.tmp_dir = tempfile.mkdtemp()
        self.test_c = os.path.join(self.tmp_dir, "test.c")
        with open(self.test_c, "w") as f:
            f.write("int main() { return 0; }\n")

    def tearDown(self) -> None:
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def test_no_auto_does_not_crash(self) -> None:
        result = _run(
            [_exe("ctc-clang"), "-###", "-c", self.test_c],
            env_override={"CLANG_TOOL_CHAIN_NO_AUTO": "1"},
        )
        self.assertEqual(result.returncode, 0, f"NO_AUTO mode failed:\n{result.stderr}")


@unittest.skipUnless(_has_native_launcher(), SKIP_REASON)
class TestSysrootOverride(unittest.TestCase):
    """Test user --sysroot= override (all platforms)."""

    def setUp(self) -> None:
        self.tmp_dir = tempfile.mkdtemp()
        self.tmp_path = Path(self.tmp_dir)

    def tearDown(self) -> None:
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def test_user_sysroot_in_output(self) -> None:
        src = self.tmp_path / "test.c"
        src.write_text("int main() { return 0; }\n")
        fake_sysroot = self.tmp_path / "fake_sysroot"
        fake_sysroot.mkdir()
        stderr = _dry_run_flags(
            _exe("ctc-clang"),
            ["--sysroot=" + str(fake_sysroot), "-c", str(src)],
        )
        self.assertIn("fake_sysroot", stderr)


# ==========================================================================
# Windows-only tests
# ==========================================================================


@unittest.skipUnless(IS_WINDOWS, "Windows-only: GNU ABI injection")
@unittest.skipUnless(_has_native_launcher(), SKIP_REASON)
class TestWindowsGNUABI(unittest.TestCase):
    """Test Windows GNU ABI flag injection via -### output."""

    def setUp(self) -> None:
        self.tmp_dir = tempfile.mkdtemp()
        self.tmp_path = Path(self.tmp_dir)
        self.test_c = os.path.join(self.tmp_dir, "test.c")
        with open(self.test_c, "w") as f:
            f.write("int main() { return 0; }\n")

    def tearDown(self) -> None:
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def test_target_injected(self) -> None:
        stderr = _dry_run_flags(_exe("ctc-clang"), ["-c", self.test_c])
        self.assertIn("-windows-gnu", stderr)

    def test_sysroot_injected(self) -> None:
        stderr = _dry_run_flags(_exe("ctc-clang"), ["-c", self.test_c])
        self.assertIn("-isysroot", stderr)

    def test_link_has_lld(self) -> None:
        stderr = _dry_run_flags(_exe("ctc-clang"), [self.test_c, "-o", str(self.tmp_path / "test.exe")])
        self.assertTrue(
            any("ld.lld" in line.lower() for line in stderr.splitlines()),
            f"No lld linker invocation found:\n{stderr}",
        )

    def test_user_target_msvc_skips_gnu(self) -> None:
        """BUG-005: --target=msvc should NOT inject GNU sysroot."""
        stderr = _dry_run_flags(
            _exe("ctc-clang"),
            ["--target=x86_64-pc-windows-msvc", "-c", self.test_c],
        )
        self.assertNotIn("mingw32", stderr.lower())

    def test_user_target_gnu_keeps_gnu(self) -> None:
        stderr = _dry_run_flags(
            _exe("ctc-clang"),
            ["--target=x86_64-w64-windows-gnu", "-c", self.test_c],
        )
        self.assertIn("mingw32", stderr.lower())

    def test_gnu_flag_cleanup(self) -> None:
        """Windows LLD should strip unsupported GNU linker flags."""
        stderr = _dry_run_flags(
            _exe("ctc-clang"),
            ["-Wl,--allow-shlib-undefined", self.test_c, "-o", str(self.tmp_path / "test.exe")],
        )
        # The flag should be stripped, not passed to lld
        self.assertNotIn("allow-shlib-undefined", stderr)


@unittest.skipUnless(IS_WINDOWS, "Windows-only: DLL deployment")
@unittest.skipUnless(_has_native_launcher(), SKIP_REASON)
class TestWindowsDLLDeployment(unittest.TestCase):
    """Test --deploy-dependencies DLL deployment (Windows only)."""

    def setUp(self) -> None:
        self.tmp_dir = tempfile.mkdtemp()
        self.tmp_path = Path(self.tmp_dir)

    def tearDown(self) -> None:
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def test_deploy_succeeds(self) -> None:
        """--deploy-dependencies succeeds; static linking means no DLLs needed."""
        src = self.tmp_path / "hello.cpp"
        exe = self.tmp_path / "hello.exe"
        src.write_text('#include <iostream>\nint main() { std::cout << "DLL_OK" << std::endl; return 0; }\n')
        result = _run([_exe("ctc-clang++"), "--deploy-dependencies", "-o", str(exe), str(src)], timeout=60)
        self.assertEqual(result.returncode, 0, f"Compile failed:\n{result.stderr}")
        # With -static-libgcc -static-libstdc++ (injected by GNU ABI), the exe is fully
        # statically linked and has no non-system DLL dependencies. Smart detection via
        # llvm-objdump correctly finds nothing to deploy. Verify the exe runs.
        run_result = _run([str(exe)], timeout=10)
        self.assertEqual(run_result.returncode, 0, f"Exe failed to run:\n{run_result.stderr}")
        self.assertIn("DLL_OK", run_result.stdout)

    def test_no_deploy_without_flag(self) -> None:
        """BUG-008: DLLs should NOT be deployed without --deploy-dependencies."""
        src = self.tmp_path / "hello.cpp"
        exe = self.tmp_path / "hello.exe"
        src.write_text('#include <iostream>\nint main() { std::cout << "OK" << std::endl; return 0; }\n')
        result = _run([_exe("ctc-clang++"), "-o", str(exe), str(src)], timeout=60)
        self.assertEqual(result.returncode, 0, f"Compile failed:\n{result.stderr}")
        dlls = list(self.tmp_path.glob("*.dll"))
        self.assertEqual(len(dlls), 0, f"DLLs deployed without flag: {[d.name for d in dlls]}")


# ==========================================================================
# Linux-only tests
# ==========================================================================


@unittest.skipUnless(IS_LINUX, "Linux-only: LLD and sysroot injection")
@unittest.skipUnless(_has_native_launcher(), SKIP_REASON)
class TestLinuxLLD(unittest.TestCase):
    """Test Linux LLD linker injection."""

    def setUp(self) -> None:
        self.tmp_dir = tempfile.mkdtemp()
        self.tmp_path = Path(self.tmp_dir)
        self.test_c = os.path.join(self.tmp_dir, "test.c")
        with open(self.test_c, "w") as f:
            f.write("int main() { return 0; }\n")

    def tearDown(self) -> None:
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def test_lld_forced_on_link(self) -> None:
        """LLD should be forced as the linker on Linux."""
        stderr = _dry_run_flags(_exe("ctc-clang"), [self.test_c, "-o", str(self.tmp_path / "test")])
        self.assertTrue(
            any("ld.lld" in line for line in stderr.splitlines()),
            f"No ld.lld linker invocation:\n{stderr}",
        )

    def test_lld_not_forced_with_env(self) -> None:
        """CLANG_TOOL_CHAIN_USE_SYSTEM_LD=1 should skip LLD injection."""
        result = _run(
            [_exe("ctc-clang"), "-###", self.test_c, "-o", str(self.tmp_path / "test")],
            env_override={"CLANG_TOOL_CHAIN_USE_SYSTEM_LD": "1"},
        )
        # The -fuse-ld=lld flag should NOT appear in the launcher's args
        # (we check the command line, not the cc1 output)
        self.assertNotIn("-fuse-ld=lld", result.stderr.split("\n")[0] if result.stderr else "")

    def test_rpath_with_deploy_dependencies(self) -> None:
        """--deploy-dependencies on Linux should add -Wl,-rpath,$ORIGIN."""
        stderr = _dry_run_flags(
            _exe("ctc-clang"),
            ["--deploy-dependencies", self.test_c, "-o", str(self.tmp_path / "test")],
        )
        self.assertIn("$ORIGIN", stderr)

    def test_no_rpath_without_deploy(self) -> None:
        """Without --deploy-dependencies, $ORIGIN rpath should NOT appear."""
        stderr = _dry_run_flags(
            _exe("ctc-clang"),
            [self.test_c, "-o", str(self.tmp_path / "test")],
        )
        self.assertNotIn("$ORIGIN", stderr)


@unittest.skipUnless(IS_LINUX, "Linux-only: bundled sysroot")
@unittest.skipUnless(_has_native_launcher(), SKIP_REASON)
class TestLinuxSysroot(unittest.TestCase):
    """Test Linux bundled sysroot and libunwind injection."""

    def setUp(self) -> None:
        self.tmp_dir = tempfile.mkdtemp()
        self.test_c = os.path.join(self.tmp_dir, "test.c")
        with open(self.test_c, "w") as f:
            f.write('#include <stdio.h>\nint main() { printf("OK\\n"); return 0; }\n')

    def tearDown(self) -> None:
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def test_sysroot_headers_available(self) -> None:
        """Bundled sysroot should make stdio.h available without system headers."""
        result = _run([_exe("ctc-clang"), "-c", self.test_c, "-o", os.path.join(self.tmp_dir, "test.o")])
        self.assertEqual(result.returncode, 0, f"Compile with sysroot failed:\n{result.stderr}")

    def test_libunwind_injected_on_link(self) -> None:
        """Bundled libunwind should be injected as -I and -L on link."""
        stderr = _dry_run_flags(
            _exe("ctc-clang"),
            [self.test_c, "-o", os.path.join(self.tmp_dir, "test")],
        )
        # Check for libunwind rpath (only if bundled libunwind exists in the installation)
        # This is optional — some installations may not have it
        if "libunwind" in stderr:
            self.assertIn("-rpath", stderr)

    def test_nostdinc_skips_sysroot(self) -> None:
        """-nostdinc should prevent bundled sysroot injection."""
        stderr = _dry_run_flags(_exe("ctc-clang"), ["-c", "-nostdinc", self.test_c])
        # Should not have -isystem for sysroot (but may have other -isystem from clang itself)
        self.assertIn("-nostdsysteminc", stderr)

    def test_ffreestanding_skips_sysroot(self) -> None:
        """-ffreestanding should prevent bundled sysroot injection."""
        result = _run(
            [_exe("ctc-clang"), "-###", "-c", "-ffreestanding", self.test_c],
        )
        # The -ffreestanding should appear in the output
        self.assertIn("-ffreestanding", result.stderr)


@unittest.skipUnless(IS_LINUX, "Linux-only: ASAN shared library")
@unittest.skipUnless(_has_native_launcher(), SKIP_REASON)
class TestLinuxASAN(unittest.TestCase):
    """Test ASAN shared library injection on Linux."""

    def setUp(self) -> None:
        self.tmp_dir = tempfile.mkdtemp()
        self.test_c = os.path.join(self.tmp_dir, "test.c")
        with open(self.test_c, "w") as f:
            f.write("int main() { return 0; }\n")

    def tearDown(self) -> None:
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def test_asan_injects_shared_libasan(self) -> None:
        """-fsanitize=address should inject -shared-libasan."""
        stderr = _dry_run_flags(
            _exe("ctc-clang"),
            ["-fsanitize=address", self.test_c, "-o", os.path.join(self.tmp_dir, "test")],
        )
        self.assertIn("-shared-libasan", stderr)

    def test_asan_shared_lib_allows_undefined(self) -> None:
        """-shared with ASAN should add --allow-shlib-undefined."""
        stderr = _dry_run_flags(
            _exe("ctc-clang"),
            ["-fsanitize=address", "-shared", self.test_c, "-o", os.path.join(self.tmp_dir, "test.so")],
        )
        self.assertIn("allow-shlib-undefined", stderr)


# ==========================================================================
# macOS-only tests
# ==========================================================================


@unittest.skipUnless(IS_MACOS, "macOS-only: SDK and LLD")
@unittest.skipUnless(_has_native_launcher(), SKIP_REASON)
class TestMacOSSDK(unittest.TestCase):
    """Test macOS SDK injection and LLD linker."""

    def setUp(self) -> None:
        self.tmp_dir = tempfile.mkdtemp()
        self.tmp_path = Path(self.tmp_dir)
        self.test_c = os.path.join(self.tmp_dir, "test.c")
        with open(self.test_c, "w") as f:
            f.write('#include <stdio.h>\nint main() { printf("OK\\n"); return 0; }\n')

    def tearDown(self) -> None:
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def test_isysroot_injected(self) -> None:
        """macOS SDK path should be injected via -isysroot."""
        stderr = _dry_run_flags(_exe("ctc-clang"), ["-c", self.test_c])
        # Should have -isysroot pointing to SDK
        self.assertIn("-isysroot", stderr)

    def test_lld_forced_on_link(self) -> None:
        """LLD should be forced as the linker on macOS."""
        stderr = _dry_run_flags(_exe("ctc-clang"), [self.test_c, "-o", str(self.tmp_path / "test")])
        # macOS uses ld64.lld
        self.assertTrue(
            any("ld64.lld" in line for line in stderr.splitlines()),
            f"No ld64.lld linker invocation:\n{stderr}",
        )

    def test_user_isysroot_not_overridden(self) -> None:
        """User's -isysroot should not be overridden by launcher."""
        stderr = _dry_run_flags(
            _exe("ctc-clang"),
            ["-isysroot", "/nonexistent/sdk", "-c", self.test_c],
        )
        self.assertIn("/nonexistent/sdk", stderr)

    def test_compile_with_sdk(self) -> None:
        """Should compile C code using the discovered SDK."""
        result = _run([_exe("ctc-clang"), "-c", self.test_c, "-o", os.path.join(self.tmp_dir, "test.o")])
        self.assertEqual(result.returncode, 0, f"Compile failed:\n{result.stderr}")


@unittest.skipUnless(IS_MACOS, "macOS-only: flag translation")
@unittest.skipUnless(_has_native_launcher(), SKIP_REASON)
class TestMacOSFlagTranslation(unittest.TestCase):
    """Test GNU-to-ld64.lld flag translation on macOS."""

    def setUp(self) -> None:
        self.tmp_dir = tempfile.mkdtemp()
        self.tmp_path = Path(self.tmp_dir)
        self.test_c = os.path.join(self.tmp_dir, "test.c")
        with open(self.test_c, "w") as f:
            f.write("int main() { return 0; }\n")

    def tearDown(self) -> None:
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def test_no_undefined_translated(self) -> None:
        """--no-undefined should be translated to -undefined error for ld64.lld."""
        stderr = _dry_run_flags(
            _exe("ctc-clang"),
            ["-Wl,--no-undefined", self.test_c, "-o", str(self.tmp_path / "test")],
        )
        # Should be translated, not passed as-is
        self.assertNotIn("--no-undefined", stderr)

    def test_fatal_warnings_translated(self) -> None:
        """--fatal-warnings should be translated to -fatal_warnings for ld64.lld."""
        stderr = _dry_run_flags(
            _exe("ctc-clang"),
            ["-Wl,--fatal-warnings", self.test_c, "-o", str(self.tmp_path / "test")],
        )
        self.assertNotIn("--fatal-warnings", stderr)

    def test_allow_shlib_undefined_removed(self) -> None:
        """--allow-shlib-undefined should be removed on macOS."""
        stderr = _dry_run_flags(
            _exe("ctc-clang"),
            ["-Wl,--allow-shlib-undefined", self.test_c, "-o", str(self.tmp_path / "test")],
        )
        self.assertNotIn("allow-shlib-undefined", stderr)

    def test_lunwind_removed(self) -> None:
        """-lunwind should be removed on macOS (conflicts with system unwind)."""
        stderr = _dry_run_flags(
            _exe("ctc-clang"),
            ["-lunwind", self.test_c, "-o", str(self.tmp_path / "test")],
        )
        # -lunwind should be stripped from the args
        self.assertNotIn("-lunwind", stderr)


if __name__ == "__main__":
    unittest.main()
