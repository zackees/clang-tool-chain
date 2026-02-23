"""
Test llvm-dlltool and gendef workflow for import library filtering.

This tests the real-world use case from FastLED: building a DLL with
--export-all-symbols causes std:: template instantiations to leak into
the export table. The workflow is:

1. Build a DLL with --export-all-symbols (simulating FastLED)
2. Extract exports with clang-tool-chain-gendef
3. Filter out unwanted std:: symbols from the .def file
4. Regenerate a clean import library with clang-tool-chain-dlltool

This verifies that the filtered import library is smaller and only
contains the intended public API symbols.
"""

import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import pytest

from clang_tool_chain.downloader import ToolchainInfrastructureError

# This entire test is Windows-only (DLLs are a Windows concept)
pytestmark = pytest.mark.skipif(not sys.platform.startswith("win"), reason="DLL tests are Windows-only")


LIB_SOURCE = """\
// Simulates a library like FastLED that exports everything,
// including unwanted std:: template instantiations.
#include <string>
#include <vector>

// Public API - these should be kept
extern "C" {
    __declspec(dllexport) int fastled_init(void) { return 1; }
    __declspec(dllexport) void fastled_show(void) {}
    __declspec(dllexport) int fastled_set_brightness(int b) { return b; }
}

// Internal functions that use std:: types - their symbols leak
// into exports when --export-all-symbols is used
std::string get_version() { return "1.0.0"; }
std::vector<int> get_led_data() { return {1, 2, 3}; }
"""

CONSUMER_SOURCE = """\
// A consumer that links against the filtered import library.
// This verifies the filtered .dll.a still works for linking.
extern "C" {
    int fastled_init(void);
    void fastled_show(void);
    int fastled_set_brightness(int b);
}

int main() {
    fastled_init();
    fastled_show();
    fastled_set_brightness(128);
    return 0;
}
"""


def _run(args: list[str], cwd: str, timeout: int = 30) -> subprocess.CompletedProcess:
    """Run a command, raising on failure."""
    result = subprocess.run(args, capture_output=True, text=True, timeout=timeout, cwd=cwd)
    if result.returncode != 0:
        raise RuntimeError(f"Command failed: {' '.join(args)}\nstdout: {result.stdout}\nstderr: {result.stderr}")
    return result


@pytest.mark.serial
class TestDlltoolFilterWorkflow(unittest.TestCase):
    """End-to-end test of the DLL export filtering workflow."""

    def setUp(self) -> None:
        self.temp_dir = tempfile.mkdtemp()
        self.cwd = self.temp_dir

        # Write source files
        (Path(self.temp_dir) / "mylib.cpp").write_text(LIB_SOURCE)
        (Path(self.temp_dir) / "consumer.cpp").write_text(CONSUMER_SOURCE)

        # Build DLL with --export-all-symbols
        _run(
            ["clang-tool-chain-cpp", "-shared", "-Wl,--export-all-symbols", "-o", "mylib.dll", "mylib.cpp"],
            cwd=self.cwd,
        )
        self.assertTrue((Path(self.temp_dir) / "mylib.dll").exists(), "DLL should be created")

    def tearDown(self) -> None:
        import shutil

        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_gendef_extracts_exports(self) -> None:
        """gendef should extract all exports from the DLL including std:: symbols."""
        try:
            result = _run(["clang-tool-chain-gendef", "-o", "-", "mylib.dll"], cwd=self.cwd)
            def_content = result.stdout

            # Should have LIBRARY header
            self.assertIn("LIBRARY mylib.dll", def_content)
            self.assertIn("EXPORTS", def_content)

            # Should contain our public API
            self.assertIn("fastled_init", def_content)
            self.assertIn("fastled_show", def_content)
            self.assertIn("fastled_set_brightness", def_content)

            # Should also contain leaked std:: symbols (mangled as _ZNSt3__)
            self.assertRegex(def_content, r"_ZNSt3__1", "Should contain leaked std:: symbols")

        except ToolchainInfrastructureError:
            raise

    def test_filter_and_regenerate_import_library(self) -> None:
        """
        Full workflow: extract .def, filter std:: symbols, regenerate import lib.

        This is the FastLED use case - reduce a bloated import library by
        removing std:: template instantiations from the export table.
        """
        try:
            # Step 1: Extract .def from DLL
            _run(["clang-tool-chain-gendef", "-o", "mylib_full.def", "mylib.dll"], cwd=self.cwd)
            full_def = (Path(self.temp_dir) / "mylib_full.def").read_text(encoding="utf-8")

            # Count total exports
            full_export_lines = [ln for ln in full_def.splitlines() if ln.strip().startswith("_") or "fastled" in ln]
            total_exports = len(full_export_lines)
            self.assertGreater(total_exports, 10, "DLL should have many exports (std:: leaks)")

            # Step 2: Filter out std:: symbols (mangled as _ZNSt or _ZNKSt)
            filtered_lines = []
            for line in full_def.splitlines():
                stripped = line.strip()
                # Keep LIBRARY/EXPORTS headers, blank lines, and non-std symbols
                if not stripped or stripped.startswith(("LIBRARY", "EXPORTS")) or not re.match(r"_ZN?K?St", stripped):
                    filtered_lines.append(line)

            filtered_def = "\n".join(filtered_lines) + "\n"
            (Path(self.temp_dir) / "mylib_filtered.def").write_text(filtered_def, encoding="utf-8")

            # Verify filtering removed std:: symbols
            filtered_export_lines = [
                ln for ln in filtered_def.splitlines() if ln.strip().startswith("_") or "fastled" in ln
            ]
            self.assertLess(
                len(filtered_export_lines),
                total_exports,
                f"Filtered exports ({len(filtered_export_lines)}) should be less than total ({total_exports})",
            )

            # Our public API should survive filtering
            self.assertIn("fastled_init", filtered_def)
            self.assertIn("fastled_show", filtered_def)
            self.assertIn("fastled_set_brightness", filtered_def)

            # std:: symbols should be gone
            self.assertNotRegex(filtered_def, r"_ZNSt3__1", "std:: symbols should be filtered out")

            # Step 3: Generate filtered import library with llvm-dlltool
            _run(
                [
                    "clang-tool-chain-dlltool",
                    "-d",
                    "mylib_filtered.def",
                    "-D",
                    "mylib.dll",
                    "-l",
                    "mylib_filtered.dll.a",
                    "-m",
                    "i386:x86-64",
                ],
                cwd=self.cwd,
            )

            filtered_lib = Path(self.temp_dir) / "mylib_filtered.dll.a"
            self.assertTrue(filtered_lib.exists(), "Filtered import library should be created")
            self.assertGreater(filtered_lib.stat().st_size, 0, "Import library should not be empty")

            # Step 4: Also generate the full (unfiltered) import library for size comparison
            _run(
                [
                    "clang-tool-chain-dlltool",
                    "-d",
                    "mylib_full.def",
                    "-D",
                    "mylib.dll",
                    "-l",
                    "mylib_full.dll.a",
                    "-m",
                    "i386:x86-64",
                ],
                cwd=self.cwd,
            )

            full_lib = Path(self.temp_dir) / "mylib_full.dll.a"
            self.assertTrue(full_lib.exists())

            # Filtered lib should be smaller
            self.assertLess(
                filtered_lib.stat().st_size,
                full_lib.stat().st_size,
                "Filtered import library should be smaller than unfiltered",
            )

            # Step 5: Verify the filtered import library actually works for linking
            _run(
                ["clang-tool-chain-cpp", "consumer.cpp", "-o", "consumer.exe", "-L.", "-l:mylib_filtered.dll.a"],
                cwd=self.cwd,
            )

            consumer_exe = Path(self.temp_dir) / "consumer.exe"
            self.assertTrue(consumer_exe.exists(), "Consumer should link against filtered import library")

            # Step 6: Run the consumer to verify it works at runtime
            result = subprocess.run(
                [str(consumer_exe)],
                capture_output=True,
                text=True,
                timeout=10,
                cwd=self.cwd,
            )
            self.assertEqual(result.returncode, 0, f"Consumer should run successfully: {result.stderr}")

        except ToolchainInfrastructureError:
            raise

    def test_dlltool_version(self) -> None:
        """llvm-dlltool should be accessible and report a version."""
        try:
            result = subprocess.run(
                ["clang-tool-chain-dlltool", "--version"],
                capture_output=True,
                text=True,
                timeout=10,
                cwd=self.cwd,
            )
            combined = (result.stdout + result.stderr).lower()
            self.assertTrue(
                "llvm" in combined or "version" in combined,
                f"llvm-dlltool should report version info, got: {combined[:200]}",
            )
        except FileNotFoundError:
            self.fail("clang-tool-chain-dlltool command not found")
        except ToolchainInfrastructureError:
            raise

    def test_lib_version(self) -> None:
        """llvm-lib should be accessible and report a version."""
        try:
            result = subprocess.run(
                ["clang-tool-chain-lib", "--version"],
                capture_output=True,
                text=True,
                timeout=10,
                cwd=self.cwd,
            )
            combined = (result.stdout + result.stderr).lower()
            self.assertTrue(
                "llvm" in combined or "version" in combined,
                f"llvm-lib should report version info, got: {combined[:200]}",
            )
        except FileNotFoundError:
            self.fail("clang-tool-chain-lib command not found")
        except ToolchainInfrastructureError:
            raise


if __name__ == "__main__":
    unittest.main()
