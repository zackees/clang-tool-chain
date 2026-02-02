"""
Test that ASAN options are correctly configured for Windows.

This module tests the fix for the Windows detect_leaks bug where
ASAN-instrumented executables fail with:
    "AddressSanitizer: detect_leaks is not supported on this platform."

LeakSanitizer is NOT supported on Windows (only Linux, macOS, Android,
Fuchsia, NetBSD). This test ensures we don't set detect_leaks=1 on Windows.

References:
    - https://clang.llvm.org/docs/LeakSanitizer.html (supported platforms)
    - https://reviews.llvm.org/D115103 (incomplete Windows port)
"""

import os
import platform

import pytest

from clang_tool_chain.execution.sanitizer_env import (
    get_default_asan_options,
    prepare_sanitizer_environment,
)


class TestAsanWindowsDetectLeaks:
    """Tests for Windows-specific ASAN behavior."""

    def test_detect_leaks_not_in_windows_defaults(self) -> None:
        """Verify detect_leaks=1 is NOT in defaults when on Windows."""
        options = get_default_asan_options()
        if platform.system() == "Windows":
            assert "detect_leaks=1" not in options, (
                "detect_leaks=1 should not be in Windows ASAN options (LSAN not supported on Windows)"
            )
        else:
            # On Linux/macOS, detect_leaks should be present
            assert "detect_leaks=1" in options

    def test_detect_leaks_in_linux_macos_defaults(self) -> None:
        """Verify detect_leaks=1 IS in defaults for Linux/macOS."""
        # This test documents the expected behavior on supported platforms
        options = get_default_asan_options()
        if platform.system() in ("Linux", "Darwin"):
            assert "detect_leaks=1" in options, "detect_leaks=1 should be in ASAN options on Linux/macOS"

    def test_base_options_always_present(self) -> None:
        """Verify base options are always present regardless of platform."""
        options = get_default_asan_options()
        assert "fast_unwind_on_malloc=0" in options
        assert "symbolize=1" in options

    def test_prepare_env_respects_platform(self) -> None:
        """Verify prepare_sanitizer_environment respects platform."""
        env = prepare_sanitizer_environment(
            base_env={},
            compiler_flags=["-fsanitize=address"],
        )

        asan_options = env.get("ASAN_OPTIONS", "")

        if platform.system() == "Windows":
            assert "detect_leaks=1" not in asan_options
        else:
            assert "detect_leaks=1" in asan_options


class TestAsanWindowsIntegration:
    """Integration tests for ASAN on Windows."""

    @pytest.mark.skipif(platform.system() != "Windows", reason="Windows-only test")
    def test_asan_executable_runs_successfully(self) -> None:
        """
        Test that an ASAN-instrumented executable runs successfully on Windows.

        This test verifies the fix works: after removing detect_leaks=1 from
        Windows defaults, ASAN executables should run without errors.
        """
        import subprocess
        import tempfile
        from pathlib import Path

        test_code = """
#include <cstdio>
int main() {
    printf("Hello ASAN\\n");
    return 0;
}
"""
        with tempfile.TemporaryDirectory() as tmpdir:
            src_file = Path(tmpdir) / "test_asan.cpp"
            exe_file = Path(tmpdir) / "test_asan.exe"

            src_file.write_text(test_code)

            # Compile with ASAN using clang-tool-chain
            try:
                from clang_tool_chain.platform.paths import find_tool_binary

                clang = find_tool_binary("clang++")
            except (ImportError, RuntimeError) as e:
                pytest.skip(f"clang++ not available: {e}")

            compile_result = subprocess.run(
                [
                    str(clang),
                    "-fsanitize=address",
                    "-shared-libasan",
                    str(src_file),
                    "-o",
                    str(exe_file),
                ],
                capture_output=True,
                text=True,
            )

            if compile_result.returncode != 0:
                pytest.skip(f"Compilation failed: {compile_result.stderr}")

            # Run with our prepared environment (should not include detect_leaks=1)
            env = prepare_sanitizer_environment(
                base_env=os.environ.copy(),
                compiler_flags=["-fsanitize=address"],
            )

            run_result = subprocess.run(
                [str(exe_file)],
                env=env,
                capture_output=True,
                text=True,
            )

            # This should now succeed since detect_leaks is not set on Windows
            assert run_result.returncode == 0, (
                f"ASAN executable should run successfully on Windows.\n"
                f"stdout: {run_result.stdout}\n"
                f"stderr: {run_result.stderr}"
            )
            assert "Hello ASAN" in run_result.stdout

    @pytest.mark.skipif(platform.system() != "Windows", reason="Windows-only test")
    def test_user_can_still_set_detect_leaks_manually(self) -> None:
        """
        Test that users can still manually set detect_leaks if they want.

        Even though we don't set it by default on Windows, users should be
        able to experiment with it if LSAN support improves in the future.
        """
        env = {
            "ASAN_OPTIONS": "detect_leaks=1:symbolize=1",
        }

        result = prepare_sanitizer_environment(
            base_env=env,
            compiler_flags=["-fsanitize=address"],
        )

        # User's existing ASAN_OPTIONS should be preserved
        assert result["ASAN_OPTIONS"] == "detect_leaks=1:symbolize=1"
