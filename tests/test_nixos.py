"""
Tests for NixOS support (GitHub issue #55).

All tests mock the environment / subprocess calls -- none require an actual
NixOS host to run.
"""

import subprocess
from pathlib import Path

import pytest

from clang_tool_chain.platform import nixos

# Real-world example outputs captured on a NixOS box, quoted in the issue.
_LIBGCC_FILE_NAME = "/nix/store/aaaa-gcc-15.2.0/lib/gcc/x86_64-unknown-linux-gnu/15.2.0/libgcc.a"
_CRT1_FILE_NAME = "/nix/store/bbbb-glibc-2.42-67/lib/crt1.o"
_LIBSTDCXX_FILE_NAME = "/nix/store/cccc-gcc-15.2.0-lib/lib/libstdc++.so.6"
_LIBGCC_S_FILE_NAME = "/nix/store/cccc-gcc-15.2.0-lib/lib/libgcc_s.so.1"

_WP_V_STDERR = """\
ignoring nonexistent directory "/nix/store/xxxx/include"
#include "..." search starts here:
 /nix/store/aaaa-gcc-15.2.0/lib/gcc/x86_64-unknown-linux-gnu/15.2.0/include
#include <...> search starts here:
 /nix/store/aaaa-gcc-15.2.0/lib/gcc/x86_64-unknown-linux-gnu/15.2.0/include
 /nix/store/dddd-glibc-2.42-dev/include
 /nix/store/aaaa-gcc-15.2.0/lib/gcc/x86_64-unknown-linux-gnu/15.2.0/include-fixed
End of search list.
"""


def _completed(stdout: str = "", stderr: str = "", returncode: int = 0) -> subprocess.CompletedProcess:
    return subprocess.CompletedProcess(args=[], returncode=returncode, stdout=stdout, stderr=stderr)


class TestIsNixos:
    def test_true_via_marker_file(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        marker = tmp_path / "NIXOS"
        marker.write_text("")
        monkeypatch.setattr(nixos, "_NIXOS_MARKER_PATH", marker)
        monkeypatch.delenv("NIX_LD", raising=False)
        monkeypatch.delenv("NIX_LD_LIBRARY_PATH", raising=False)
        assert nixos.is_nixos() is True

    def test_true_via_nix_ld_env(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        monkeypatch.setattr(nixos, "_NIXOS_MARKER_PATH", tmp_path / "does-not-exist")
        monkeypatch.setenv("NIX_LD", "/nix/store/x/ld.so")
        monkeypatch.delenv("NIX_LD_LIBRARY_PATH", raising=False)
        assert nixos.is_nixos() is True

    def test_true_via_nix_ld_library_path_env(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        monkeypatch.setattr(nixos, "_NIXOS_MARKER_PATH", tmp_path / "does-not-exist")
        monkeypatch.delenv("NIX_LD", raising=False)
        monkeypatch.setenv("NIX_LD_LIBRARY_PATH", "/nix/store/y/lib")
        assert nixos.is_nixos() is True

    def test_false_when_no_markers(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        monkeypatch.setattr(nixos, "_NIXOS_MARKER_PATH", tmp_path / "does-not-exist")
        monkeypatch.delenv("NIX_LD", raising=False)
        monkeypatch.delenv("NIX_LD_LIBRARY_PATH", raising=False)
        assert nixos.is_nixos() is False


class TestDiscoverNixToolchain:
    def test_discovers_all_fields(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("NIX_LD_LIBRARY_PATH", raising=False)
        monkeypatch.setattr(nixos, "_NIX_LD_FALLBACK_DIR", "/nonexistent-nix-ld-fallback-dir-for-tests")

        def fake_run(cmd: list[str], **kwargs: object) -> subprocess.CompletedProcess:
            assert cmd[0] == "gcc"
            arg = cmd[1]
            if arg == "-print-libgcc-file-name":
                return _completed(stdout=_LIBGCC_FILE_NAME + "\n")
            if arg == "-print-file-name=crt1.o":
                return _completed(stdout=_CRT1_FILE_NAME + "\n")
            if arg == "-print-file-name=libstdc++.so.6":
                return _completed(stdout=_LIBSTDCXX_FILE_NAME + "\n")
            if arg == "-print-file-name=libgcc_s.so.1":
                return _completed(stdout=_LIBGCC_S_FILE_NAME + "\n")
            if arg == "-E":
                return _completed(stderr=_WP_V_STDERR)
            raise AssertionError(f"unexpected gcc invocation: {cmd}")

        monkeypatch.setattr(nixos.subprocess, "run", fake_run)

        toolchain = nixos.discover_nix_toolchain(gcc="gcc")
        assert toolchain is not None

        assert toolchain.gcc_install_dir == "/nix/store/aaaa-gcc-15.2.0/lib/gcc/x86_64-unknown-linux-gnu/15.2.0"
        # gcc_root is the gcc_install_dir's 4th parent.
        assert toolchain.gcc_root == "/nix/store/aaaa-gcc-15.2.0"
        assert toolchain.glibc_lib_dir == "/nix/store/bbbb-glibc-2.42-67/lib"
        assert toolchain.gcc_lib_dir == "/nix/store/cccc-gcc-15.2.0-lib/lib"
        assert toolchain.libgcc_dir == "/nix/store/cccc-gcc-15.2.0-lib/lib"
        assert toolchain.glibc_include_dir == "/nix/store/dddd-glibc-2.42-dev/include"
        assert toolchain.nix_ld_lib_dirs == ()

    def test_nix_ld_lib_dirs_from_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("NIX_LD_LIBRARY_PATH", "/a/lib:/b/lib")

        def fake_run(cmd: list[str], **kwargs: object) -> subprocess.CompletedProcess:
            arg = cmd[1]
            if arg == "-print-libgcc-file-name":
                return _completed(stdout=_LIBGCC_FILE_NAME)
            if arg == "-print-file-name=crt1.o":
                return _completed(stdout=_CRT1_FILE_NAME)
            if arg == "-print-file-name=libstdc++.so.6":
                return _completed(stdout=_LIBSTDCXX_FILE_NAME)
            if arg == "-print-file-name=libgcc_s.so.1":
                return _completed(stdout=_LIBGCC_S_FILE_NAME)
            if arg == "-E":
                return _completed(stderr=_WP_V_STDERR)
            raise AssertionError(f"unexpected gcc invocation: {cmd}")

        monkeypatch.setattr(nixos.subprocess, "run", fake_run)

        toolchain = nixos.discover_nix_toolchain(gcc="gcc")
        assert toolchain is not None
        assert toolchain.nix_ld_lib_dirs == ("/a/lib", "/b/lib")

    def test_none_when_gcc_absent(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(nixos.shutil, "which", lambda name: None)
        assert nixos.discover_nix_toolchain() is None

    def test_none_when_libgcc_probe_fails(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(nixos.subprocess, "run", lambda *a, **k: _completed(returncode=1))
        assert nixos.discover_nix_toolchain(gcc="gcc") is None

    def test_none_when_probe_echoes_bare_name(self, monkeypatch: pytest.MonkeyPatch) -> None:
        # gcc echoes back the bare filename it could not resolve (not an absolute path).
        def fake_run(cmd: list[str], **kwargs: object) -> subprocess.CompletedProcess:
            arg = cmd[1]
            if arg == "-print-libgcc-file-name":
                return _completed(stdout="libgcc.a")
            raise AssertionError(f"unexpected gcc invocation: {cmd}")

        monkeypatch.setattr(nixos.subprocess, "run", fake_run)
        assert nixos.discover_nix_toolchain(gcc="gcc") is None


class TestBuildConfigLines:
    def _toolchain(self, tmp_path: Path) -> nixos.NixToolchain:
        gcc_install_dir = tmp_path / "gcc-install"
        gcc_lib_dir = tmp_path / "gcc-lib"
        glibc_lib_dir = tmp_path / "glibc-lib"
        glibc_include_dir = tmp_path / "glibc-include"
        for d in (gcc_install_dir, gcc_lib_dir, glibc_lib_dir, glibc_include_dir):
            d.mkdir()
        return nixos.NixToolchain(
            gcc_root=str(tmp_path / "gcc-root"),
            gcc_install_dir=str(gcc_install_dir),
            gcc_lib_dir=str(gcc_lib_dir),
            libgcc_dir=str(gcc_lib_dir),
            glibc_lib_dir=str(glibc_lib_dir),
            glibc_include_dir=str(glibc_include_dir),
            nix_ld_lib_dirs=(),
        )

    def test_contains_gcc_toolchain_flag(self, tmp_path: Path) -> None:
        toolchain = self._toolchain(tmp_path)
        lines = nixos.build_config_lines(toolchain)
        assert f"--gcc-toolchain={toolchain.gcc_root}" in lines

    def test_contains_compiler_rt_rpath_when_supplied(self, tmp_path: Path) -> None:
        toolchain = self._toolchain(tmp_path)
        rt_dir = tmp_path / "compiler-rt-lib"
        rt_dir.mkdir()
        lines = nixos.build_config_lines(toolchain, compiler_rt_lib_dir=str(rt_dir))
        assert f"-Wl,-rpath,{rt_dir}" in lines

    def test_omits_compiler_rt_rpath_when_not_supplied(self, tmp_path: Path) -> None:
        toolchain = self._toolchain(tmp_path)
        lines = nixos.build_config_lines(toolchain, compiler_rt_lib_dir=None)
        assert not any("compiler-rt" in line for line in lines)

    def test_never_pins_dynamic_linker(self, tmp_path: Path) -> None:
        # Regression guard for issue #55: pinning -Wl,-dynamic-linker would bypass
        # the nix-ld shim, which is the issue's stated first preference. Only
        # actual flag lines matter here -- the header comments discuss the flag
        # by name to explain why it is intentionally absent.
        toolchain = self._toolchain(tmp_path)
        rt_dir = tmp_path / "compiler-rt-lib"
        rt_dir.mkdir()
        lines = nixos.build_config_lines(toolchain, compiler_rt_lib_dir=str(rt_dir))
        flag_lines = [line for line in lines if line and not line.startswith("#")]
        assert not any("-dynamic-linker" in line for line in flag_lines)

    def test_dedupes_directories(self, tmp_path: Path) -> None:
        shared_dir = tmp_path / "shared"
        shared_dir.mkdir()
        toolchain = nixos.NixToolchain(
            gcc_root=str(tmp_path / "gcc-root"),
            gcc_install_dir=str(shared_dir),
            gcc_lib_dir=str(shared_dir),
            libgcc_dir=str(shared_dir),
            glibc_lib_dir=str(shared_dir),
            glibc_include_dir="",
            nix_ld_lib_dirs=(),
        )
        lines = nixos.build_config_lines(toolchain)
        assert lines.count(f"-L{shared_dir}") == 1
        assert lines.count(f"-Wl,-rpath,{shared_dir}") == 1


class TestWriteNixosClangConfigs:
    def _fake_toolchain(self, tmp_path: Path) -> nixos.NixToolchain:
        gcc_dir = tmp_path / "gcc"
        gcc_dir.mkdir(exist_ok=True)
        return nixos.NixToolchain(
            gcc_root=str(gcc_dir),
            gcc_install_dir=str(gcc_dir),
            gcc_lib_dir=str(gcc_dir),
            libgcc_dir=str(gcc_dir),
            glibc_lib_dir=str(gcc_dir),
            glibc_include_dir="",
            nix_ld_lib_dirs=(),
        )

    def _make_nixos(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        monkeypatch.setattr(nixos, "is_nixos", lambda: True)
        monkeypatch.setattr(nixos, "discover_nix_toolchain", lambda gcc=None: self._fake_toolchain(tmp_path))
        monkeypatch.delenv(nixos.NO_CFG_ENV_VAR, raising=False)

    def test_writes_both_files(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        self._make_nixos(monkeypatch, tmp_path)
        clang_root = tmp_path / "clang-root"
        clang_root.mkdir()

        written = nixos.write_nixos_clang_configs(clang_root)

        assert {p.name for p in written} == {"clang.cfg", "clang++.cfg"}
        for name in ("clang.cfg", "clang++.cfg"):
            content = (clang_root / "bin" / name).read_text()
            assert content.startswith(nixos.NIXOS_CFG_MARKER)

    def test_noop_when_env_disabled(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        self._make_nixos(monkeypatch, tmp_path)
        monkeypatch.setenv(nixos.NO_CFG_ENV_VAR, "1")
        clang_root = tmp_path / "clang-root"
        clang_root.mkdir()

        written = nixos.write_nixos_clang_configs(clang_root)

        assert written == []
        assert not (clang_root / "bin" / "clang.cfg").exists()

    def test_noop_when_not_nixos(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        monkeypatch.setattr(nixos, "is_nixos", lambda: False)
        clang_root = tmp_path / "clang-root"
        clang_root.mkdir()

        written = nixos.write_nixos_clang_configs(clang_root)

        assert written == []

    def test_noop_when_toolchain_not_discovered(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        monkeypatch.setattr(nixos, "is_nixos", lambda: True)
        monkeypatch.setattr(nixos, "discover_nix_toolchain", lambda gcc=None: None)
        monkeypatch.delenv(nixos.NO_CFG_ENV_VAR, raising=False)
        clang_root = tmp_path / "clang-root"
        clang_root.mkdir()

        written = nixos.write_nixos_clang_configs(clang_root)

        assert written == []

    def test_backs_up_foreign_existing_cfg(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        self._make_nixos(monkeypatch, tmp_path)
        clang_root = tmp_path / "clang-root"
        bin_dir = clang_root / "bin"
        bin_dir.mkdir(parents=True)
        foreign_content = "# hand-written by the issue reporter\n--gcc-toolchain=/nix/store/whatever\n"
        (bin_dir / "clang.cfg").write_text(foreign_content)

        written = nixos.write_nixos_clang_configs(clang_root)

        assert (bin_dir / "clang.cfg") in written
        backup = bin_dir / "clang.cfg.bak"
        assert backup.exists()
        assert backup.read_text() == foreign_content
        assert (bin_dir / "clang.cfg").read_text().startswith(nixos.NIXOS_CFG_MARKER)

    def test_overwrites_own_marker_without_backup(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        self._make_nixos(monkeypatch, tmp_path)
        clang_root = tmp_path / "clang-root"

        first_written = nixos.write_nixos_clang_configs(clang_root)
        assert first_written  # first write happens

        # Change the discovered toolchain so the regenerated content differs.
        other_gcc_dir = tmp_path / "other-gcc"
        other_gcc_dir.mkdir()
        monkeypatch.setattr(
            nixos,
            "discover_nix_toolchain",
            lambda gcc=None: nixos.NixToolchain(
                gcc_root=str(other_gcc_dir),
                gcc_install_dir=str(other_gcc_dir),
                gcc_lib_dir=str(other_gcc_dir),
                libgcc_dir=str(other_gcc_dir),
                glibc_lib_dir=str(other_gcc_dir),
                glibc_include_dir="",
                nix_ld_lib_dirs=(),
            ),
        )

        second_written = nixos.write_nixos_clang_configs(clang_root)

        assert second_written
        bin_dir = clang_root / "bin"
        assert not (bin_dir / "clang.cfg.bak").exists()
        assert not (bin_dir / "clang++.cfg.bak").exists()
        assert str(other_gcc_dir) in (bin_dir / "clang.cfg").read_text()

    def test_skips_rewrite_when_content_unchanged(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        self._make_nixos(monkeypatch, tmp_path)
        clang_root = tmp_path / "clang-root"

        first_written = nixos.write_nixos_clang_configs(clang_root)
        assert first_written

        second_written = nixos.write_nixos_clang_configs(clang_root)
        assert second_written == []

    def test_force_rewrites_even_when_unchanged(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        self._make_nixos(monkeypatch, tmp_path)
        clang_root = tmp_path / "clang-root"

        first_written = nixos.write_nixos_clang_configs(clang_root)
        assert first_written

        second_written = nixos.write_nixos_clang_configs(clang_root, force=True)
        assert second_written  # forced rewrite happens even though content is identical


class TestNixosStatusReport:
    def test_empty_when_not_nixos(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(nixos, "is_nixos", lambda: False)
        assert nixos.nixos_status_report() == []

    def test_reports_missing_gcc(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(nixos, "is_nixos", lambda: True)
        monkeypatch.setattr(nixos, "discover_nix_toolchain", lambda gcc=None: None)
        lines = nixos.nixos_status_report()
        assert any("No system gcc" in line for line in lines)

    def test_reports_discovered_toolchain(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        monkeypatch.setattr(nixos, "is_nixos", lambda: True)
        toolchain = nixos.NixToolchain(
            gcc_root="/nix/store/gcc",
            gcc_install_dir="/nix/store/gcc/lib/gcc/x/1",
            gcc_lib_dir="/nix/store/gcc-lib/lib",
            libgcc_dir="/nix/store/gcc-lib/lib",
            glibc_lib_dir="/nix/store/glibc/lib",
            glibc_include_dir="/nix/store/glibc-dev/include",
            nix_ld_lib_dirs=("/run/current-system/sw/share/nix-ld/lib",),
        )
        monkeypatch.setattr(nixos, "discover_nix_toolchain", lambda gcc=None: toolchain)
        lines = nixos.nixos_status_report()
        assert any("/nix/store/gcc" in line for line in lines)
