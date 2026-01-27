"""
Unit tests for Linux .so deployment (so_deployer.py).

This test suite mirrors the Windows DLL deployment tests and verifies:
- Pattern matching for deployable vs system libraries
- Dependency detection using readelf
- Library location in toolchain directories
- Symlink handling for versioned .so files
- Environment variable controls
- Integration with execution core
"""

import os
import subprocess
from pathlib import Path
from unittest.mock import MagicMock, Mock, patch

import pytest

from clang_tool_chain.deployment.so_deployer import (
    SoDeployer,
    detect_required_so_files,
    post_link_so_deployment,
)


class TestSoDeployerPatternMatching:
    """Test library pattern matching (deployable vs system)."""

    def test_is_deployable_libcpp(self):
        """libc++.so.1 should be deployable."""
        deployer = SoDeployer()
        assert deployer.is_deployable_library("libc++.so.1")

    def test_is_deployable_libcpp_versioned(self):
        """libc++.so.1.0 should be deployable."""
        deployer = SoDeployer()
        assert deployer.is_deployable_library("libc++.so.1.0")

    def test_is_deployable_libcppabi(self):
        """libc++abi.so.1 should be deployable."""
        deployer = SoDeployer()
        assert deployer.is_deployable_library("libc++abi.so.1")

    def test_is_deployable_libunwind(self):
        """libunwind.so.1 should be deployable."""
        deployer = SoDeployer()
        assert deployer.is_deployable_library("libunwind.so.1")

    def test_is_deployable_sanitizer_asan(self):
        """libclang_rt.asan.so should be deployable."""
        deployer = SoDeployer()
        assert deployer.is_deployable_library("libclang_rt.asan.so")

    def test_is_deployable_sanitizer_tsan(self):
        """libclang_rt.tsan.so should be deployable."""
        deployer = SoDeployer()
        assert deployer.is_deployable_library("libclang_rt.tsan.so")

    def test_is_not_deployable_glibc(self):
        """libc.so.6 should NOT be deployable (system library)."""
        deployer = SoDeployer()
        assert not deployer.is_deployable_library("libc.so.6")

    def test_is_not_deployable_libm(self):
        """libm.so.6 should NOT be deployable (system library)."""
        deployer = SoDeployer()
        assert not deployer.is_deployable_library("libm.so.6")

    def test_is_not_deployable_libpthread(self):
        """libpthread.so.0 should NOT be deployable (system library)."""
        deployer = SoDeployer()
        assert not deployer.is_deployable_library("libpthread.so.0")

    def test_is_not_deployable_libdl(self):
        """libdl.so.2 should NOT be deployable (system library)."""
        deployer = SoDeployer()
        assert not deployer.is_deployable_library("libdl.so.2")

    def test_is_not_deployable_libgcc(self):
        """libgcc_s.so.1 should NOT be deployable (system library)."""
        deployer = SoDeployer()
        assert not deployer.is_deployable_library("libgcc_s.so.1")

    def test_is_not_deployable_linux_vdso(self):
        """linux-vdso.so.1 should NOT be deployable (kernel)."""
        deployer = SoDeployer()
        assert not deployer.is_deployable_library("linux-vdso.so.1")

    def test_is_not_deployable_ld_linux(self):
        """ld-linux-x86-64.so.2 should NOT be deployable (dynamic linker)."""
        deployer = SoDeployer()
        assert not deployer.is_deployable_library("ld-linux-x86-64.so.2")

    def test_is_not_deployable_unknown_library(self):
        """Random library should NOT be deployable."""
        deployer = SoDeployer()
        assert not deployer.is_deployable_library("libfoo.so.1")


class TestSoDeployerDependencyDetection:
    """Test dependency detection using readelf."""

    def test_detect_dependencies_success(self):
        """Test successful readelf dependency detection."""
        deployer = SoDeployer()

        # Mock readelf output
        readelf_output = """
Dynamic section at offset 0x2000 contains 24 entries:
  Tag        Type                         Name/Value
 0x0000000000000001 (NEEDED)             Shared library: [libc++.so.1]
 0x0000000000000001 (NEEDED)             Shared library: [libunwind.so.1]
 0x0000000000000001 (NEEDED)             Shared library: [libm.so.6]
 0x0000000000000001 (NEEDED)             Shared library: [libc.so.6]
"""

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = Mock(stdout=readelf_output, returncode=0)
            deps = deployer.detect_dependencies(Path("/fake/program"))

        assert "libc++.so.1" in deps
        assert "libunwind.so.1" in deps
        assert "libm.so.6" in deps
        assert "libc.so.6" in deps
        assert len(deps) == 4

    def test_detect_dependencies_no_needed(self):
        """Test readelf output with no NEEDED entries."""
        deployer = SoDeployer()

        # Mock readelf output with no dependencies
        readelf_output = """
Dynamic section at offset 0x2000 contains 10 entries:
  Tag        Type                         Name/Value
 0x000000000000000e (SONAME)             Library soname: [libtest.so]
"""

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = Mock(stdout=readelf_output, returncode=0)
            deps = deployer.detect_dependencies(Path("/fake/program"))

        assert len(deps) == 0

    def test_detect_dependencies_readelf_not_found(self):
        """Test handling of missing readelf command."""
        deployer = SoDeployer()

        with patch("subprocess.run", side_effect=FileNotFoundError):
            deps = deployer.detect_dependencies(Path("/fake/program"))

        assert len(deps) == 0

    def test_detect_dependencies_readelf_timeout(self):
        """Test handling of readelf timeout."""
        deployer = SoDeployer()

        with patch("subprocess.run", side_effect=subprocess.TimeoutExpired("readelf", 10)):
            deps = deployer.detect_dependencies(Path("/fake/program"))

        assert len(deps) == 0

    def test_detect_dependencies_readelf_error(self):
        """Test handling of readelf error."""
        deployer = SoDeployer()

        with patch("subprocess.run", side_effect=subprocess.CalledProcessError(1, "readelf")):
            deps = deployer.detect_dependencies(Path("/fake/program"))

        assert len(deps) == 0

    def test_detect_dependencies_nonexistent_file(self):
        """Test detection on nonexistent file."""
        deployer = SoDeployer()

        with patch("subprocess.run", side_effect=subprocess.CalledProcessError(1, "readelf")):
            deps = deployer.detect_dependencies(Path("/nonexistent/program"))

        assert len(deps) == 0


class TestSoDeployerLibraryLocation:
    """Test finding libraries in toolchain directories."""

    def test_find_library_in_clang_lib(self, tmp_path):
        """Test finding library in Clang toolchain lib directory."""
        deployer = SoDeployer()

        # Create mock Clang lib directory
        clang_lib = tmp_path / "clang" / "lib"
        clang_lib.mkdir(parents=True)
        lib_file = clang_lib / "libc++.so.1"
        lib_file.write_text("mock library")

        with patch("clang_tool_chain.platform.detection.get_platform_binary_dir") as mock_get_bin:
            mock_get_bin.return_value = tmp_path / "clang" / "bin"

            found = deployer.find_library_in_toolchain("libc++.so.1")

        assert found is not None
        assert found.name == "libc++.so.1"

    def test_find_library_resolves_symlink(self, tmp_path):
        """Test that find_library resolves symlinks."""
        deployer = SoDeployer()

        # Create mock library with symlink
        clang_lib = tmp_path / "clang" / "lib"
        clang_lib.mkdir(parents=True)
        real_file = clang_lib / "libc++.so.1.0"
        real_file.write_text("real library")
        symlink = clang_lib / "libc++.so.1"
        symlink.symlink_to("libc++.so.1.0")

        with patch("clang_tool_chain.platform.detection.get_platform_binary_dir") as mock_get_bin:
            mock_get_bin.return_value = tmp_path / "clang" / "bin"

            found = deployer.find_library_in_toolchain("libc++.so.1")

        assert found is not None
        assert found.name == "libc++.so.1.0"  # Resolved to real file

    def test_find_library_not_found(self):
        """Test handling of library not found."""
        deployer = SoDeployer()

        with patch("clang_tool_chain.platform.detection.get_platform_binary_dir") as mock_get_bin:
            mock_get_bin.return_value = Path("/nonexistent/bin")

            found = deployer.find_library_in_toolchain("libnonexistent.so.1")

        assert found is None

    def test_find_library_search_order(self, tmp_path):
        """Test that libraries are found in correct search order."""
        deployer = SoDeployer()

        # Create mock libraries in multiple locations
        clang_lib = tmp_path / "clang" / "lib"
        clang_lib.mkdir(parents=True)
        clang_file = clang_lib / "libc++.so.1"
        clang_file.write_text("clang version")

        with patch("clang_tool_chain.platform.detection.get_platform_binary_dir") as mock_get_bin:
            mock_get_bin.return_value = tmp_path / "clang" / "bin"

            found = deployer.find_library_in_toolchain("libc++.so.1")

        # Should find Clang version first
        assert found is not None
        assert found.parent == clang_lib


class TestSoDeployerArchitectures:
    """Test architecture-specific behavior."""

    def test_x86_64_architecture(self):
        """Test x86_64 architecture configuration."""
        deployer = SoDeployer(arch="x86_64")
        assert deployer.arch == "x86_64"
        assert deployer.platform_name == "linux"

    def test_arm64_architecture(self):
        """Test arm64 architecture configuration."""
        deployer = SoDeployer(arch="arm64")
        assert deployer.arch == "arm64"
        assert deployer.platform_name == "linux"

    def test_aarch64_architecture(self):
        """Test aarch64 architecture configuration."""
        deployer = SoDeployer(arch="aarch64")
        assert deployer.arch == "aarch64"
        assert deployer.platform_name == "linux"

    def test_get_library_extension(self):
        """Test library extension is .so."""
        deployer = SoDeployer()
        assert deployer.get_library_extension() == ".so"


class TestSoDeployerSymlinkHandling:
    """Test versioned symlink handling."""

    def test_deploy_library_creates_symlink(self, tmp_path):
        """Test that deploy_library creates necessary symlinks."""
        deployer = SoDeployer()

        # Create mock source library
        src_dir = tmp_path / "src"
        src_dir.mkdir()
        src_file = src_dir / "libc++.so.1.0"
        src_file.write_text("library content")

        # Mock find_library_in_toolchain
        deployer.find_library_in_toolchain = Mock(return_value=src_file)

        # Deploy to output directory
        output_dir = tmp_path / "output"
        output_dir.mkdir()

        result = deployer.deploy_library("libc++.so.1", output_dir)

        assert result is True
        assert (output_dir / "libc++.so.1.0").exists()  # Real file
        assert (output_dir / "libc++.so.1").exists()  # Symlink

        # Verify symlink points to real file
        if (output_dir / "libc++.so.1").is_symlink():
            assert (output_dir / "libc++.so.1").readlink() == Path("libc++.so.1.0")

    def test_deploy_library_no_symlink_if_same_name(self, tmp_path):
        """Test that no symlink is created if names match."""
        deployer = SoDeployer()

        # Create mock source library
        src_dir = tmp_path / "src"
        src_dir.mkdir()
        src_file = src_dir / "libc++.so.1"
        src_file.write_text("library content")

        # Mock find_library_in_toolchain
        deployer.find_library_in_toolchain = Mock(return_value=src_file)

        # Deploy to output directory
        output_dir = tmp_path / "output"
        output_dir.mkdir()

        result = deployer.deploy_library("libc++.so.1", output_dir)

        assert result is True
        assert (output_dir / "libc++.so.1").exists()  # Real file

        # Count files (should be 1, not 2)
        files = list(output_dir.iterdir())
        assert len(files) == 1


class TestSoDeployerEnvironmentVariables:
    """Test environment variable controls."""

    def test_post_link_respects_no_deploy_libs(self, tmp_path, monkeypatch):
        """Test CLANG_TOOL_CHAIN_NO_DEPLOY_LIBS disables deployment."""
        monkeypatch.setenv("CLANG_TOOL_CHAIN_NO_DEPLOY_LIBS", "1")

        exe = tmp_path / "program"
        exe.write_text("mock executable")
        exe.chmod(0o755)

        count = post_link_so_deployment(exe)
        assert count == 0

    def test_post_link_respects_no_deploy_so(self, tmp_path, monkeypatch):
        """Test CLANG_TOOL_CHAIN_NO_DEPLOY_SO disables deployment."""
        monkeypatch.setenv("CLANG_TOOL_CHAIN_NO_DEPLOY_SO", "1")

        exe = tmp_path / "program"
        exe.write_text("mock executable")
        exe.chmod(0o755)

        count = post_link_so_deployment(exe)
        assert count == 0

    def test_post_link_allows_deployment_by_default(self, tmp_path, monkeypatch):
        """Test deployment is allowed when env vars not set."""
        # Ensure env vars are not set
        monkeypatch.delenv("CLANG_TOOL_CHAIN_NO_DEPLOY_LIBS", raising=False)
        monkeypatch.delenv("CLANG_TOOL_CHAIN_NO_DEPLOY_SO", raising=False)

        exe = tmp_path / "program"
        exe.write_text("mock executable")
        exe.chmod(0o755)

        # Mock deployer
        with patch("clang_tool_chain.deployment.so_deployer.SoDeployer") as mock_deployer_class:
            mock_deployer = MagicMock()
            mock_deployer.deploy_all.return_value = 3
            mock_deployer_class.return_value = mock_deployer

            count = post_link_so_deployment(exe)

        assert count == 3
        mock_deployer.deploy_all.assert_called_once_with(exe)


class TestSoDeployerFileTypes:
    """Test handling of different file types."""

    def test_post_link_handles_executable(self, tmp_path, monkeypatch):
        """Test deployment for executable files."""
        exe = tmp_path / "program"
        exe.write_text("mock executable")
        exe.chmod(0o755)

        with patch("clang_tool_chain.deployment.so_deployer.SoDeployer") as mock_deployer_class:
            mock_deployer = MagicMock()
            mock_deployer.deploy_all.return_value = 2
            mock_deployer_class.return_value = mock_deployer

            count = post_link_so_deployment(exe)

        assert count == 2

    def test_post_link_handles_shared_library(self, tmp_path):
        """Test deployment for .so files."""
        lib = tmp_path / "libtest.so"
        lib.write_text("mock shared library")

        with patch("clang_tool_chain.deployment.so_deployer.SoDeployer") as mock_deployer_class:
            mock_deployer = MagicMock()
            mock_deployer.deploy_all.return_value = 1
            mock_deployer_class.return_value = mock_deployer

            count = post_link_so_deployment(lib)

        assert count == 1

    def test_post_link_handles_versioned_so(self, tmp_path):
        """Test deployment for versioned .so files (libtest.so.1.2.3)."""
        lib = tmp_path / "libtest.so.1.2.3"
        lib.write_text("mock versioned library")

        with patch("clang_tool_chain.deployment.so_deployer.SoDeployer") as mock_deployer_class:
            mock_deployer = MagicMock()
            mock_deployer.deploy_all.return_value = 1
            mock_deployer_class.return_value = mock_deployer

            count = post_link_so_deployment(lib)

        assert count == 1

    def test_post_link_skips_nonexistent_file(self, tmp_path):
        """Test handling of nonexistent files."""
        exe = tmp_path / "nonexistent"
        count = post_link_so_deployment(exe)
        assert count == 0

    def test_post_link_skips_object_files(self, tmp_path):
        """Test that .o files are skipped."""
        obj = tmp_path / "test.o"
        obj.write_text("mock object file")

        count = post_link_so_deployment(obj)
        assert count == 0


class TestSoDeployerConvenienceFunctions:
    """Test convenience wrapper functions."""

    def test_detect_required_so_files(self, tmp_path):
        """Test detect_required_so_files wrapper."""
        exe = tmp_path / "program"
        exe.write_text("mock executable")

        with patch("clang_tool_chain.deployment.so_deployer.SoDeployer") as mock_deployer_class:
            mock_deployer = MagicMock()
            mock_deployer.detect_all_dependencies.return_value = {"libc++.so.1", "libunwind.so.1"}
            mock_deployer_class.return_value = mock_deployer

            result = detect_required_so_files(exe, arch="x86_64", recursive=True)

        assert len(result) == 2
        assert "libc++.so.1" in result or "libunwind.so.1" in result

    def test_detect_required_so_files_nonrecursive(self, tmp_path):
        """Test detect_required_so_files with recursive=False."""
        exe = tmp_path / "program"
        exe.write_text("mock executable")

        with patch("clang_tool_chain.deployment.so_deployer.SoDeployer") as mock_deployer_class:
            mock_deployer = MagicMock()
            mock_deployer.detect_all_dependencies.return_value = {"libc++.so.1"}
            mock_deployer_class.return_value = mock_deployer

            detect_required_so_files(exe, recursive=False)

        mock_deployer.detect_all_dependencies.assert_called_once_with(exe, recursive=False)


class TestSoDeployerErrorHandling:
    """Test error handling and logging."""

    def test_deploy_all_handles_exception(self, tmp_path):
        """Test that deploy_all handles exceptions gracefully."""
        deployer = SoDeployer()

        exe = tmp_path / "program"
        exe.write_text("mock executable")

        # Mock detect_dependencies (not detect_all_dependencies) to raise exception
        # This will be caught inside detect_all_dependencies
        with patch.object(deployer, "detect_dependencies", side_effect=RuntimeError("Test error")):
            # Should not raise, returns 0
            count = deployer.deploy_all(exe)
            assert count == 0

    def test_post_link_handles_exception(self, tmp_path):
        """Test that post_link_so_deployment handles exceptions gracefully."""
        exe = tmp_path / "program"
        exe.write_text("mock executable")
        exe.chmod(0o755)

        with patch("clang_tool_chain.deployment.so_deployer.SoDeployer") as mock_deployer_class:
            mock_deployer = MagicMock()
            mock_deployer.deploy_all.side_effect = RuntimeError("Test error")
            mock_deployer_class.return_value = mock_deployer

            # Should not raise, returns 0
            count = post_link_so_deployment(exe)
            assert count == 0

    def test_deploy_library_handles_missing_library(self, tmp_path):
        """Test deploy_library handles missing library gracefully."""
        deployer = SoDeployer()

        output_dir = tmp_path / "output"
        output_dir.mkdir()

        # Mock find_library_in_toolchain to return None
        deployer.find_library_in_toolchain = Mock(return_value=None)

        result = deployer.deploy_library("libnonexistent.so.1", output_dir)
        assert result is False


class TestSoDeployerIntegration:
    """Integration tests (require Linux platform and readelf)."""

    @pytest.mark.skipif(os.name != "posix", reason="Linux-specific test")
    def test_detect_dependencies_real_binary(self, tmp_path):
        """Test detection on a real binary (if readelf available)."""
        # Create a simple C++ program
        source = tmp_path / "test.cpp"
        source.write_text("""
        #include <iostream>
        int main() {
            std::cout << "Hello" << std::endl;
            return 0;
        }
        """)

        exe = tmp_path / "test_program"

        try:
            # Compile with system clang/g++ (if available)
            subprocess.run(
                ["c++", str(source), "-o", str(exe)],
                check=True,
                capture_output=True,
            )

            if exe.exists():
                deployer = SoDeployer()
                deps = deployer.detect_dependencies(exe)

                # Should detect at least libc and libm
                assert len(deps) > 0
                # System libraries should be present
                lib_names = " ".join(deps)
                assert "libc.so" in lib_names or "libstdc++" in lib_names

        except (subprocess.CalledProcessError, FileNotFoundError):
            pytest.skip("C++ compiler not available")

    @pytest.mark.skipif(os.name != "posix", reason="Linux-specific test")
    def test_readelf_available(self):
        """Test that readelf is available (prerequisite check)."""
        try:
            result = subprocess.run(
                ["readelf", "--version"],
                capture_output=True,
                check=True,
            )
            assert result.returncode == 0
        except (subprocess.CalledProcessError, FileNotFoundError):
            pytest.skip("readelf not available")
