"""
Unit tests for SoDeployer's "already resolvable, skip deployment" behavior.

Covers the GitHub issue #55 (request #2) feature: before copying a runtime
dependency on Linux, check whether the dynamic loader would already find it
via RPATH/RUNPATH, LD_LIBRARY_PATH, the ldconfig cache, or the default
trusted directories -- and skip the copy if so.

All tests mock `subprocess.run` and use `tmp_path` for fake library files;
no real `readelf`/`ldconfig` binaries are required, so this suite passes on
any platform (Windows/macOS CI included).
"""

import subprocess
from pathlib import Path
from unittest.mock import Mock, patch

from clang_tool_chain.deployment.so_deployer import SoDeployer


class TestParseRpathRunpath:
    """Test parsing DT_RPATH / DT_RUNPATH out of `readelf -d` output."""

    def test_parse_runpath_simple(self, tmp_path):
        deployer = SoDeployer()
        readelf_output = " 0x000000000000001d (RUNPATH)            Library runpath: [/opt/foo/lib]\n"

        dirs = deployer._parse_rpath_runpath(readelf_output, tmp_path)

        assert dirs == [Path("/opt/foo/lib")]

    def test_parse_runpath_multiple_entries(self, tmp_path):
        deployer = SoDeployer()
        readelf_output = " 0x000000000000001d (RUNPATH)            Library runpath: [/opt/foo/lib:/opt/bar/lib]\n"

        dirs = deployer._parse_rpath_runpath(readelf_output, tmp_path)

        assert dirs == [Path("/opt/foo/lib"), Path("/opt/bar/lib")]

    def test_parse_rpath_simple(self, tmp_path):
        deployer = SoDeployer()
        readelf_output = " 0x000000000000000f (RPATH)              Library rpath: [/opt/baz/lib]\n"

        dirs = deployer._parse_rpath_runpath(readelf_output, tmp_path)

        assert dirs == [Path("/opt/baz/lib")]

    def test_parse_rpath_and_runpath_union(self, tmp_path):
        """Both RPATH and RUNPATH entries should be unioned (order between them doesn't matter)."""
        deployer = SoDeployer()
        readelf_output = (
            " 0x000000000000000f (RPATH)              Library rpath: [/opt/baz/lib]\n"
            " 0x000000000000001d (RUNPATH)            Library runpath: [/opt/foo/lib]\n"
        )

        dirs = deployer._parse_rpath_runpath(readelf_output, tmp_path)

        assert set(dirs) == {Path("/opt/baz/lib"), Path("/opt/foo/lib")}

    def test_parse_origin_expansion(self, tmp_path):
        """$ORIGIN should expand to the binary's own directory."""
        deployer = SoDeployer()
        readelf_output = " 0x000000000000001d (RUNPATH)            Library runpath: [$ORIGIN/../lib]\n"

        dirs = deployer._parse_rpath_runpath(readelf_output, tmp_path)

        assert dirs == [Path(f"{tmp_path}/../lib")]

    def test_parse_curly_origin_expansion(self, tmp_path):
        """${ORIGIN} (braced form) should also expand."""
        deployer = SoDeployer()
        readelf_output = " 0x000000000000001d (RUNPATH)            Library runpath: [${ORIGIN}/lib]\n"

        dirs = deployer._parse_rpath_runpath(readelf_output, tmp_path)

        assert dirs == [Path(f"{tmp_path}/lib")]

    def test_parse_skips_lib_and_platform_tokens(self, tmp_path):
        """Entries containing $LIB or $PLATFORM (dynamic-linker substitutions) are skipped."""
        deployer = SoDeployer()
        readelf_output = (
            " 0x000000000000001d (RUNPATH)            Library runpath: [/opt/good/lib:$LIB/bad:${PLATFORM}/also-bad]\n"
        )

        dirs = deployer._parse_rpath_runpath(readelf_output, tmp_path)

        assert dirs == [Path("/opt/good/lib")]

    def test_parse_no_rpath_runpath(self, tmp_path):
        deployer = SoDeployer()
        readelf_output = " 0x0000000000000001 (NEEDED)             Shared library: [libc.so.6]\n"

        dirs = deployer._parse_rpath_runpath(readelf_output, tmp_path)

        assert dirs == []

    def test_parse_deduplicates(self, tmp_path):
        deployer = SoDeployer()
        readelf_output = (
            " 0x000000000000000f (RPATH)              Library rpath: [/opt/foo/lib]\n"
            " 0x000000000000001d (RUNPATH)            Library runpath: [/opt/foo/lib]\n"
        )

        dirs = deployer._parse_rpath_runpath(readelf_output, tmp_path)

        assert dirs == [Path("/opt/foo/lib")]


class TestLdLibraryPathResolution:
    """Test LD_LIBRARY_PATH directory resolution via the current environment."""

    def test_ld_library_path_single_dir(self, monkeypatch):
        deployer = SoDeployer()
        monkeypatch.setenv("LD_LIBRARY_PATH", "/opt/mylibs")

        dirs = deployer._get_ld_library_path_dirs()

        assert dirs == [Path("/opt/mylibs")]

    def test_ld_library_path_multiple_dirs(self, monkeypatch):
        deployer = SoDeployer()
        monkeypatch.setenv("LD_LIBRARY_PATH", "/opt/a:/opt/b")

        dirs = deployer._get_ld_library_path_dirs()

        assert dirs == [Path("/opt/a"), Path("/opt/b")]

    def test_ld_library_path_unset(self, monkeypatch):
        deployer = SoDeployer()
        monkeypatch.delenv("LD_LIBRARY_PATH", raising=False)

        dirs = deployer._get_ld_library_path_dirs()

        assert dirs == []

    def test_is_resolvable_via_ld_library_path(self, tmp_path, monkeypatch):
        """A soname sitting in an LD_LIBRARY_PATH directory should resolve."""
        deployer = SoDeployer()
        lib_dir = tmp_path / "mylibs"
        lib_dir.mkdir()
        lib_file = lib_dir / "libfoo.so.1"
        lib_file.write_text("fake lib")

        monkeypatch.setenv("LD_LIBRARY_PATH", str(lib_dir))
        # No ldconfig cache needed for this to resolve via step 2.
        deployer._ldconfig_cache = {}

        resolved = deployer.is_resolvable("libfoo.so.1", tmp_path / "program")

        assert resolved == lib_file


class TestLdconfigCacheParsing:
    """Test parsing of `ldconfig -p` output."""

    def test_ldconfig_parses_lines(self):
        deployer = SoDeployer()
        ldconfig_output = (
            "1234 libs found in cache `/etc/ld.so.cache'\n"
            "\tlibfoo.so.1 (libc6,x86-64) => /usr/lib/x86_64-linux-gnu/libfoo.so.1\n"
            "\tlibbar.so.2 (libc6,x86-64) => /usr/lib/libbar.so.2\n"
        )

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = Mock(stdout=ldconfig_output, returncode=0)
            cache = deployer._get_ldconfig_cache()

        assert cache["libfoo.so.1"] == Path("/usr/lib/x86_64-linux-gnu/libfoo.so.1")
        assert cache["libbar.so.2"] == Path("/usr/lib/libbar.so.2")

    def test_ldconfig_cache_built_at_most_once(self):
        """Subsequent calls should not re-invoke subprocess.run."""
        deployer = SoDeployer()
        ldconfig_output = "\tlibfoo.so.1 (libc6,x86-64) => /usr/lib/libfoo.so.1\n"

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = Mock(stdout=ldconfig_output, returncode=0)
            deployer._get_ldconfig_cache()
            deployer._get_ldconfig_cache()

        assert mock_run.call_count == 1

    def test_ldconfig_not_found_treated_as_empty(self):
        """FileNotFoundError (e.g. NixOS, which has no ldconfig) must not raise."""
        deployer = SoDeployer()

        with patch("subprocess.run", side_effect=FileNotFoundError):
            cache = deployer._get_ldconfig_cache()

        assert cache == {}

    def test_ldconfig_nonzero_exit_treated_as_empty(self):
        deployer = SoDeployer()

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = Mock(stdout="", returncode=1)
            cache = deployer._get_ldconfig_cache()

        assert cache == {}

    def test_ldconfig_timeout_treated_as_empty(self):
        deployer = SoDeployer()

        with patch("subprocess.run", side_effect=subprocess.TimeoutExpired("ldconfig", 10)):
            cache = deployer._get_ldconfig_cache()

        assert cache == {}


class TestIsResolvable:
    """Integration-style tests for SoDeployer.is_resolvable()."""

    def test_resolves_via_rpath_runpath(self, tmp_path):
        deployer = SoDeployer()
        binary_dir = tmp_path / "bin"
        binary_dir.mkdir()
        binary_path = binary_dir / "myprogram"

        rpath_dir = tmp_path / "rpathlibs"
        rpath_dir.mkdir()
        lib_file = rpath_dir / "libfoo.so.1"
        lib_file.write_text("fake lib")

        deployer._rpath_runpath_cache[binary_path] = [rpath_dir]
        deployer._ldconfig_cache = {}

        resolved = deployer.is_resolvable("libfoo.so.1", binary_path)

        assert resolved == lib_file

    def test_resolves_via_ldconfig_cache(self, tmp_path):
        deployer = SoDeployer()
        binary_path = tmp_path / "myprogram"

        lib_dir = tmp_path / "usrlib"
        lib_dir.mkdir()
        lib_file = lib_dir / "libfoo.so.1"
        lib_file.write_text("fake lib")

        deployer._ldconfig_cache = {"libfoo.so.1": lib_file}

        resolved = deployer.is_resolvable("libfoo.so.1", binary_path)

        assert resolved == lib_file

    def test_resolves_via_trusted_dir(self, tmp_path, monkeypatch):
        deployer = SoDeployer()
        binary_path = tmp_path / "myprogram"

        trusted_dir = tmp_path / "trusted"
        trusted_dir.mkdir()
        lib_file = trusted_dir / "libfoo.so.1"
        lib_file.write_text("fake lib")

        deployer._ldconfig_cache = {}
        monkeypatch.setattr(deployer, "_get_trusted_dirs", lambda: [trusted_dir])

        resolved = deployer.is_resolvable("libfoo.so.1", binary_path)

        assert resolved == lib_file

    def test_unresolvable_soname_returns_none(self, tmp_path, monkeypatch):
        """A soname that resolves nowhere must report as unresolvable (still deployed)."""
        deployer = SoDeployer()
        binary_path = tmp_path / "myprogram"

        deployer._ldconfig_cache = {}
        monkeypatch.delenv("LD_LIBRARY_PATH", raising=False)
        monkeypatch.setattr(deployer, "_get_trusted_dirs", lambda: [])

        resolved = deployer.is_resolvable("libtotally_missing.so.1", binary_path)

        assert resolved is None


class TestDeployAllSkipsResolvable:
    """Integration tests for the deploy_all() skip-if-resolvable wiring."""

    def test_deploy_all_skips_resolvable_library(self, tmp_path, monkeypatch, caplog):
        deployer = SoDeployer()
        monkeypatch.delenv("CLANG_TOOL_CHAIN_ALWAYS_DEPLOY", raising=False)

        binary_dir = tmp_path / "out"
        binary_dir.mkdir()
        binary_path = binary_dir / "myprogram"
        binary_path.write_text("fake elf")

        # Pretend libc++.so.1 is already resolvable somewhere.
        already_there = tmp_path / "already_there.so.1"
        already_there.write_text("fake lib")

        with (
            patch.object(deployer, "detect_all_dependencies", return_value={"libc++.so.1"}),
            patch.object(deployer, "is_resolvable", return_value=already_there) as mock_is_resolvable,
            patch.object(deployer, "deploy_library") as mock_deploy_library,
            caplog.at_level("INFO"),
        ):
            count = deployer.deploy_all(binary_path)

        assert count == 0
        mock_deploy_library.assert_not_called()
        mock_is_resolvable.assert_called_once_with("libc++.so.1", binary_path)
        assert "Skipping libc++.so.1" in caplog.text
        assert "already resolvable" in caplog.text
        assert "CLANG_TOOL_CHAIN_ALWAYS_DEPLOY" in caplog.text

    def test_deploy_all_deploys_unresolvable_library(self, tmp_path, monkeypatch):
        deployer = SoDeployer()
        monkeypatch.delenv("CLANG_TOOL_CHAIN_ALWAYS_DEPLOY", raising=False)

        binary_path = tmp_path / "myprogram"
        binary_path.write_text("fake elf")

        with (
            patch.object(deployer, "detect_all_dependencies", return_value={"libc++.so.1"}),
            patch.object(deployer, "is_resolvable", return_value=None),
            patch.object(deployer, "deploy_library", return_value=True) as mock_deploy_library,
        ):
            count = deployer.deploy_all(binary_path)

        assert count == 1
        mock_deploy_library.assert_called_once_with("libc++.so.1", binary_path.parent)

    def test_always_deploy_env_var_bypasses_resolvable_check(self, tmp_path, monkeypatch):
        """CLANG_TOOL_CHAIN_ALWAYS_DEPLOY=1 restores unconditional-copy behavior."""
        deployer = SoDeployer()
        monkeypatch.setenv("CLANG_TOOL_CHAIN_ALWAYS_DEPLOY", "1")

        binary_path = tmp_path / "myprogram"
        binary_path.write_text("fake elf")

        already_there = tmp_path / "already_there.so.1"
        already_there.write_text("fake lib")

        with (
            patch.object(deployer, "detect_all_dependencies", return_value={"libc++.so.1"}),
            patch.object(deployer, "is_resolvable", return_value=already_there) as mock_is_resolvable,
            patch.object(deployer, "deploy_library", return_value=True) as mock_deploy_library,
        ):
            count = deployer.deploy_all(binary_path)

        assert count == 1
        mock_deploy_library.assert_called_once_with("libc++.so.1", binary_path.parent)
        # The resolvability check itself should not even run when the escape hatch is set.
        mock_is_resolvable.assert_not_called()

    def test_deploy_all_no_dependencies(self, tmp_path):
        deployer = SoDeployer()
        binary_path = tmp_path / "myprogram"
        binary_path.write_text("fake elf")

        with patch.object(deployer, "detect_all_dependencies", return_value=set()):
            count = deployer.deploy_all(binary_path)

        assert count == 0
