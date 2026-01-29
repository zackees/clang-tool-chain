#!/usr/bin/env python3
"""
Unit tests for LLVM version consistency across Emscripten toolchain.

Ensures that emcc and wasm-ld use the same LLVM version to prevent
IR incompatibility errors during compilation.

Usage:
    pytest test_version_consistency.py -v
    python test_version_consistency.py  # Run with unittest
"""

import re
import subprocess
import sys
import tempfile
from pathlib import Path

try:
    import pytest  # type: ignore[import]

    has_pytest = True
except ImportError:
    has_pytest = False

import unittest


def get_llvm_version_from_emcc() -> str:
    """
    Extract LLVM version from emcc.

    Returns:
        LLVM version string (e.g., "22.0.0git" or "21.1.5")
    """
    # Run emcc with -v to get verbose output including LLVM version
    result = subprocess.run(["clang-tool-chain-emcc", "-v"], capture_output=True, text=True, check=True)

    # Example verbose output: "clang version 22.0.0git (https://github.com/llvm/llvm-project ...)"
    # Look in both stdout and stderr (emcc outputs to stderr)
    combined_output = result.stdout + result.stderr
    match = re.search(r"clang version (\S+)", combined_output)

    if not match:
        raise ValueError(
            f"Could not extract LLVM version from emcc -v output.\nSTDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
        )

    return match.group(1)


def get_llvm_version_from_wasm_ld() -> str:
    """
    Extract LLVM version from wasm-ld.

    Returns:
        LLVM version string (e.g., "21.1.5")
    """
    result = subprocess.run(["clang-tool-chain-wasm-ld", "--version"], capture_output=True, text=True, check=True)

    # Example output: "LLD 21.1.5" or "LLD 22.0.0git"
    combined_output = result.stdout + result.stderr
    match = re.search(r"LLD (\S+)", combined_output)

    if not match:
        raise ValueError(
            f"Could not extract LLD version from wasm-ld output.\nSTDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
        )

    return match.group(1)


def normalize_version(version: str) -> str:
    """
    Normalize LLVM version strings for comparison.

    Examples:
        "22.0.0git" -> "22.0.0"
        "21.1.5" -> "21.1.5"
        "22.0.0 (https://...)" -> "22.0.0"

    Returns:
        Normalized version string (major.minor.patch)
    """
    # Strip "git" suffix and URL artifacts
    version = version.split()[0]  # Remove URL if present
    version = version.rstrip("git")  # Remove "git" suffix
    return version


# ============================================================================
# PYTEST-STYLE TESTS
# ============================================================================

if has_pytest:

    def test_emcc_and_wasm_ld_have_matching_llvm_versions():
        """
        CRITICAL TEST: Verify emcc and wasm-ld use the same LLVM version.

        This prevents LLVM IR incompatibility errors like:
          "wasm-ld: error: Unknown attribute kind (105) (Producer: 'LLVM22.0.0git' Reader: 'LLVM 21.1.5')"

        Rationale:
        - Emscripten is a self-contained toolchain that bundles its own LLVM
        - emcc, wasm-ld, and other tools must use the SAME bundled LLVM version
        - Using system-installed wasm-ld breaks this guarantee

        If this test fails:
        - The clang-tool-chain package is mixing Emscripten's LLVM with system LLVM
        - This will cause compilation failures in production
        """
        emcc_llvm_version = get_llvm_version_from_emcc()
        wasm_ld_llvm_version = get_llvm_version_from_wasm_ld()

        # Normalize versions for comparison (strip "git" suffix, etc.)
        emcc_normalized = normalize_version(emcc_llvm_version)
        wasm_ld_normalized = normalize_version(wasm_ld_llvm_version)

        assert emcc_normalized == wasm_ld_normalized, (
            f"LLVM version mismatch detected!\n"
            f"  emcc uses LLVM:    {emcc_llvm_version} (normalized: {emcc_normalized})\n"
            f"  wasm-ld uses LLVM: {wasm_ld_llvm_version} (normalized: {wasm_ld_normalized})\n"
            f"\n"
            f"This will cause compilation errors like:\n"
            f"  'wasm-ld: error: Unknown attribute kind (X) (Producer: 'LLVM{emcc_llvm_version}' Reader: 'LLVM{wasm_ld_llvm_version}')'\n"
            f"\n"
            f"FIX: Update clang-tool-chain to use Emscripten's bundled wasm-ld instead of system LLVM.\n"
            f"See: emsdk/upstream/bin/wasm-ld (should match emsdk/upstream/bin/clang version)"
        )

    def test_partial_linking_with_real_compilation():
        """
        Integration test: Compile and partially link a WASM object file.

        This test verifies the entire toolchain works end-to-end:
        1. Compile C++ → WASM object file (emcc)
        2. Partial link object file (wasm-ld -r)
        3. Verify no LLVM version errors
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir = Path(tmpdir)

            # Step 1: Create minimal C++ source
            source_file = tmpdir / "test.cpp"
            source_file.write_text("""
                #include <emscripten.h>
                extern "C" {
                    EMSCRIPTEN_KEEPALIVE
                    int add(int a, int b) {
                        return a + b;
                    }
                }
            """)

            # Step 2: Compile to object file
            object_file = tmpdir / "test.o"
            result = subprocess.run(
                ["clang-tool-chain-emcc", "-c", str(source_file), "-o", str(object_file), "-O1"],
                capture_output=True,
                text=True,
            )
            assert result.returncode == 0, f"Compilation failed:\n{result.stderr}"
            assert object_file.exists(), "Object file was not created"

            # Step 3: Partial link (this triggers the version mismatch bug)
            partial_object = tmpdir / "test_partial.o"
            result = subprocess.run(
                [
                    "clang-tool-chain-wasm-ld",
                    "-r",  # Relocatable output
                    str(object_file),
                    "-o",
                    str(partial_object),
                ],
                capture_output=True,
                text=True,
            )

            # Verify no LLVM version errors
            assert result.returncode == 0, (
                f"Partial linking failed (LLVM version mismatch?):\nSTDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
            )

            # Check for the specific error message
            assert "Unknown attribute kind" not in result.stderr, (
                f"LLVM version mismatch detected during partial linking:\n{result.stderr}"
            )

            assert partial_object.exists(), "Partial object file was not created"

    def test_emscripten_uses_bundled_llvm():
        """
        Verify that clang-tool-chain uses Emscripten's bundled LLVM, not system LLVM.

        Emscripten ships with its own LLVM toolchain in emsdk/upstream/bin/.
        The clang-tool-chain wrappers should use these bundled tools.
        """
        emcc_version = get_llvm_version_from_emcc()
        wasm_ld_version = get_llvm_version_from_wasm_ld()

        # Check if versions suggest system LLVM usage
        # Common system LLVM versions: 14.x, 15.x, 16.x, 17.x, 18.x, 19.x, 20.x, 21.x
        # Emscripten typically uses cutting-edge LLVM (22.x, 23.x, etc.)

        # Normalize versions
        emcc_major = int(normalize_version(emcc_version).split(".")[0])
        wasm_ld_major = int(normalize_version(wasm_ld_version).split(".")[0])

        # If emcc is using LLVM 22+ but wasm-ld is using LLVM <=21, likely system LLVM
        if emcc_major >= 22 and wasm_ld_major <= 21:
            pytest.fail(  # type: ignore[name-defined]
                f"wasm-ld appears to be using system LLVM (version {wasm_ld_version}), "
                f"not Emscripten's bundled LLVM (version {emcc_version}).\n"
                f"\n"
                f"Expected: Emscripten's bundled wasm-ld from emsdk/upstream/bin/\n"
                f"Actual: Likely using system-installed wasm-ld\n"
                f"\n"
                f"This will cause LLVM version mismatches during compilation."
            )


# ============================================================================
# UNITTEST-STYLE TESTS (for environments without pytest)
# ============================================================================


class TestVersionConsistency(unittest.TestCase):
    """Unittest-compatible test class."""

    def test_emcc_and_wasm_ld_have_matching_llvm_versions(self):
        """CRITICAL TEST: Verify emcc and wasm-ld use the same LLVM version."""
        emcc_llvm_version = get_llvm_version_from_emcc()
        wasm_ld_llvm_version = get_llvm_version_from_wasm_ld()

        emcc_normalized = normalize_version(emcc_llvm_version)
        wasm_ld_normalized = normalize_version(wasm_ld_llvm_version)

        self.assertEqual(
            emcc_normalized,
            wasm_ld_normalized,
            f"LLVM version mismatch!\n"
            f"  emcc: {emcc_llvm_version} ({emcc_normalized})\n"
            f"  wasm-ld: {wasm_ld_llvm_version} ({wasm_ld_normalized})",
        )

    def test_partial_linking_with_real_compilation(self):
        """Integration test: Compile and partially link a WASM object file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir = Path(tmpdir)
            source_file = tmpdir / "test.cpp"
            source_file.write_text("""
                #include <emscripten.h>
                extern "C" {
                    EMSCRIPTEN_KEEPALIVE
                    int add(int a, int b) { return a + b; }
                }
            """)

            object_file = tmpdir / "test.o"
            result = subprocess.run(
                ["clang-tool-chain-emcc", "-c", str(source_file), "-o", str(object_file), "-O1"],
                capture_output=True,
                text=True,
            )
            self.assertEqual(result.returncode, 0, f"Compilation failed: {result.stderr}")
            self.assertTrue(object_file.exists(), "Object file not created")

            partial_object = tmpdir / "test_partial.o"
            result = subprocess.run(
                ["clang-tool-chain-wasm-ld", "-r", str(object_file), "-o", str(partial_object)],
                capture_output=True,
                text=True,
            )
            self.assertEqual(result.returncode, 0, f"Partial linking failed: {result.stderr}")
            self.assertNotIn("Unknown attribute kind", result.stderr, f"LLVM version mismatch: {result.stderr}")
            self.assertTrue(partial_object.exists(), "Partial object not created")


# ============================================================================
# MAIN ENTRY POINT
# ============================================================================


def main():
    """Main entry point for running tests."""
    print("=" * 70)
    print("clang-tool-chain LLVM Version Consistency Test Suite")
    print("=" * 70)
    print()

    # Display current versions
    try:
        emcc_version = get_llvm_version_from_emcc()
        wasm_ld_version = get_llvm_version_from_wasm_ld()

        print("📦 Package: clang-tool-chain")
        print(f"🔧 emcc LLVM version:    {emcc_version}")
        print(f"🔗 wasm-ld LLVM version: {wasm_ld_version}")
        print()

        emcc_norm = normalize_version(emcc_version)
        wasm_ld_norm = normalize_version(wasm_ld_version)

        if emcc_norm == wasm_ld_norm:
            print("✅ Version Check: PASSED (versions match)")
        else:
            print("❌ Version Check: FAILED (version mismatch detected!)")
            print(f"   Expected: {emcc_norm}")
            print(f"   Got:      {wasm_ld_norm}")
        print()
        print("-" * 70)
        print()
    except Exception as e:
        print(f"⚠️  Warning: Could not extract versions: {e}")
        print()

    # Run tests
    if has_pytest:
        print("Running tests with pytest...")
        sys.exit(pytest.main([__file__, "-v"]))  # type: ignore[name-defined]
    else:
        print("Running tests with unittest (pytest not available)...")
        unittest.main(verbosity=2)


if __name__ == "__main__":
    main()
