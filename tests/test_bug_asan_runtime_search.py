"""
Tests for Bug 1 and Bug 2 from BUGS.md:

Bug 1: SoDeployer.find_library_in_toolchain should search compiler-rt subdirectories
  (lib/clang/<version>/lib/<target>/) for sanitizer runtimes like libclang_rt.asan.so.

Bug 2: prepare_sanitizer_environment should set LD_LIBRARY_PATH on Linux when ASAN
  is enabled, mirroring the Windows PATH injection logic.
"""

from unittest.mock import patch

from clang_tool_chain.deployment.so_deployer import SoDeployer
from clang_tool_chain.execution.sanitizer_env import prepare_sanitizer_environment

# ============================================================================
# Bug 1: find_library_in_toolchain should search compiler-rt subdirectories
# ============================================================================


class TestBug1CompilerRtSearch:
    """SoDeployer.find_library_in_toolchain must search lib/clang/<ver>/lib/<target>/."""

    def test_find_asan_in_compiler_rt_x86_64(self, tmp_path):
        """libclang_rt.asan.so should be found in lib/clang/21.1.5/lib/x86_64-unknown-linux-gnu/."""
        deployer = SoDeployer(arch="x86_64")

        # Create mock toolchain directory structure matching LLVM 21.1.5
        clang_lib = tmp_path / "clang" / "lib"
        rt_dir = clang_lib / "clang" / "21.1.5" / "lib" / "x86_64-unknown-linux-gnu"
        rt_dir.mkdir(parents=True)
        asan_lib = rt_dir / "libclang_rt.asan.so"
        asan_lib.write_text("mock asan library")

        # The top-level lib/ should NOT contain the asan lib (this is the bug scenario)
        assert not (clang_lib / "libclang_rt.asan.so").exists()

        with patch("clang_tool_chain.platform.detection.get_platform_binary_dir") as mock_get_bin:
            mock_get_bin.return_value = tmp_path / "clang" / "bin"
            found = deployer.find_library_in_toolchain("libclang_rt.asan.so")

        assert found is not None, (
            "Bug 1: find_library_in_toolchain failed to find libclang_rt.asan.so "
            "in compiler-rt subdirectory lib/clang/21.1.5/lib/x86_64-unknown-linux-gnu/"
        )

    def test_find_asan_in_compiler_rt_linux_subdir(self, tmp_path):
        """libclang_rt.asan.so should also be found in lib/clang/<ver>/lib/linux/."""
        deployer = SoDeployer(arch="x86_64")

        clang_lib = tmp_path / "clang" / "lib"
        rt_dir = clang_lib / "clang" / "21.1.5" / "lib" / "linux"
        rt_dir.mkdir(parents=True)
        asan_lib = rt_dir / "libclang_rt.asan.so"
        asan_lib.write_text("mock asan library")

        with patch("clang_tool_chain.platform.detection.get_platform_binary_dir") as mock_get_bin:
            mock_get_bin.return_value = tmp_path / "clang" / "bin"
            found = deployer.find_library_in_toolchain("libclang_rt.asan.so")

        assert found is not None, (
            "Bug 1: find_library_in_toolchain failed to find libclang_rt.asan.so "
            "in compiler-rt subdirectory lib/clang/21.1.5/lib/linux/"
        )

    def test_find_asan_in_compiler_rt_aarch64(self, tmp_path):
        """libclang_rt.asan.so should be found for aarch64 in the correct target dir."""
        deployer = SoDeployer(arch="aarch64")

        clang_lib = tmp_path / "clang" / "lib"
        rt_dir = clang_lib / "clang" / "21.1.5" / "lib" / "aarch64-unknown-linux-gnu"
        rt_dir.mkdir(parents=True)
        asan_lib = rt_dir / "libclang_rt.asan.so"
        asan_lib.write_text("mock asan library")

        with patch("clang_tool_chain.platform.detection.get_platform_binary_dir") as mock_get_bin:
            mock_get_bin.return_value = tmp_path / "clang" / "bin"
            found = deployer.find_library_in_toolchain("libclang_rt.asan.so")

        assert found is not None, (
            "Bug 1: find_library_in_toolchain failed to find libclang_rt.asan.so "
            "in compiler-rt subdirectory for aarch64"
        )

    def test_find_asan_arch_suffixed_variant(self, tmp_path):
        """libclang_rt.asan.so should match libclang_rt.asan-x86_64.so."""
        deployer = SoDeployer(arch="x86_64")

        clang_lib = tmp_path / "clang" / "lib"
        rt_dir = clang_lib / "clang" / "21.1.5" / "lib" / "x86_64-unknown-linux-gnu"
        rt_dir.mkdir(parents=True)
        # Only the architecture-suffixed variant exists
        asan_lib = rt_dir / "libclang_rt.asan-x86_64.so"
        asan_lib.write_text("mock asan library arch-suffixed")

        with patch("clang_tool_chain.platform.detection.get_platform_binary_dir") as mock_get_bin:
            mock_get_bin.return_value = tmp_path / "clang" / "bin"
            found = deployer.find_library_in_toolchain("libclang_rt.asan.so")

        assert found is not None, (
            "Bug 1: find_library_in_toolchain failed to find architecture-suffixed "
            "variant libclang_rt.asan-x86_64.so when looking for libclang_rt.asan.so"
        )

    def test_find_tsan_in_compiler_rt(self, tmp_path):
        """Other sanitizer runtimes (tsan) should also be found in compiler-rt."""
        deployer = SoDeployer(arch="x86_64")

        clang_lib = tmp_path / "clang" / "lib"
        rt_dir = clang_lib / "clang" / "21.1.5" / "lib" / "x86_64-unknown-linux-gnu"
        rt_dir.mkdir(parents=True)
        tsan_lib = rt_dir / "libclang_rt.tsan.so"
        tsan_lib.write_text("mock tsan library")

        with patch("clang_tool_chain.platform.detection.get_platform_binary_dir") as mock_get_bin:
            mock_get_bin.return_value = tmp_path / "clang" / "bin"
            found = deployer.find_library_in_toolchain("libclang_rt.tsan.so")

        assert found is not None, (
            "Bug 1: find_library_in_toolchain failed to find libclang_rt.tsan.so in compiler-rt subdirectory"
        )

    def test_still_finds_libcpp_in_top_level_lib(self, tmp_path):
        """Non-sanitizer libraries (libc++) should still be found in top-level lib/."""
        deployer = SoDeployer(arch="x86_64")

        clang_lib = tmp_path / "clang" / "lib"
        clang_lib.mkdir(parents=True)
        libcpp = clang_lib / "libc++.so.1"
        libcpp.write_text("mock libc++")

        with patch("clang_tool_chain.platform.detection.get_platform_binary_dir") as mock_get_bin:
            mock_get_bin.return_value = tmp_path / "clang" / "bin"
            found = deployer.find_library_in_toolchain("libc++.so.1")

        assert found is not None, "Regular libraries should still be found in top-level lib/"


# ============================================================================
# Bug 2: prepare_sanitizer_environment should set LD_LIBRARY_PATH on Linux
# ============================================================================


class TestBug2LinuxLdLibraryPath:
    """prepare_sanitizer_environment must set LD_LIBRARY_PATH on Linux for ASAN."""

    @patch("clang_tool_chain.execution.sanitizer_env.platform")
    def test_linux_asan_sets_ld_library_path(self, mock_platform):
        """On Linux with ASAN, LD_LIBRARY_PATH should include compiler-rt dirs."""
        mock_platform.system.return_value = "Linux"

        base_env = {"PATH": "/usr/bin"}
        env = prepare_sanitizer_environment(
            base_env=base_env,
            compiler_flags=["-fsanitize=address"],
        )

        assert "LD_LIBRARY_PATH" in env, (
            "Bug 2: prepare_sanitizer_environment does not set LD_LIBRARY_PATH on Linux when ASAN is enabled"
        )

    @patch("clang_tool_chain.execution.sanitizer_env.platform")
    def test_linux_asan_ld_library_path_preserves_existing(self, mock_platform):
        """Existing LD_LIBRARY_PATH should be preserved (appended)."""
        mock_platform.system.return_value = "Linux"

        base_env = {"PATH": "/usr/bin", "LD_LIBRARY_PATH": "/custom/lib"}
        env = prepare_sanitizer_environment(
            base_env=base_env,
            compiler_flags=["-fsanitize=address"],
        )

        assert "LD_LIBRARY_PATH" in env
        assert "/custom/lib" in env["LD_LIBRARY_PATH"], (
            "Bug 2: prepare_sanitizer_environment overwrites existing LD_LIBRARY_PATH instead of preserving it"
        )

    @patch("clang_tool_chain.execution.sanitizer_env.platform")
    def test_linux_no_asan_no_ld_library_path(self, mock_platform):
        """Without ASAN, LD_LIBRARY_PATH should not be modified."""
        mock_platform.system.return_value = "Linux"

        base_env = {"PATH": "/usr/bin"}
        env = prepare_sanitizer_environment(
            base_env=base_env,
            compiler_flags=["-O2"],
        )

        assert "LD_LIBRARY_PATH" not in env, "LD_LIBRARY_PATH should not be set when ASAN is not enabled"

    @patch("clang_tool_chain.execution.sanitizer_env.platform")
    def test_linux_asan_ld_library_path_contains_compiler_rt(self, mock_platform):
        """LD_LIBRARY_PATH should include the compiler-rt directory path."""
        mock_platform.system.return_value = "Linux"

        base_env = {"PATH": "/usr/bin"}
        env = prepare_sanitizer_environment(
            base_env=base_env,
            compiler_flags=["-fsanitize=address"],
        )

        if "LD_LIBRARY_PATH" in env:
            ld_path = env["LD_LIBRARY_PATH"]
            # Should contain at least one path with lib in it
            assert "lib" in ld_path, f"Bug 2: LD_LIBRARY_PATH should contain library directories, got: {ld_path}"
