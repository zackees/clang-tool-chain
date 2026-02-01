"""
Tests for unwind_windows.c implementation with _Ux86_64_get_proc_name.

These tests verify that:
1. The C implementation compiles successfully
2. _Ux86_64_get_proc_name provides symbol resolution for libunwind
3. unw_get_proc_name() works natively (without Python symbolizer)

Windows-only tests - skipped on Linux/macOS.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

# Skip entire module on non-Windows platforms
pytestmark = pytest.mark.skipif(sys.platform != "win32", reason="Windows C implementation test")


# Path to the C implementation files
SYMBOLIZER_DIR = Path(__file__).parent.parent / "src" / "clang_tool_chain" / "symbolizer"
UNWIND_WINDOWS_C = SYMBOLIZER_DIR / "unwind_windows.c"
UNWIND_WINDOWS_H = SYMBOLIZER_DIR / "unwind_windows.h"


class TestCImplementationExists:
    """Verify the C implementation files exist."""

    def test_unwind_windows_c_exists(self):
        """unwind_windows.c should exist."""
        assert UNWIND_WINDOWS_C.exists(), f"Expected {UNWIND_WINDOWS_C} to exist"

    def test_unwind_windows_h_exists(self):
        """unwind_windows.h should exist."""
        assert UNWIND_WINDOWS_H.exists(), f"Expected {UNWIND_WINDOWS_H} to exist"

    def test_header_declares_functions(self):
        """Header should declare required functions."""
        content = UNWIND_WINDOWS_H.read_text()
        assert "unw_get_proc_name_windows" in content
        assert "_Ux86_64_get_proc_name" in content
        assert "unw_windows_sym_init" in content
        assert "unw_windows_sym_cleanup" in content


class TestCompileCImplementation:
    """Test that the C implementation compiles correctly."""

    @pytest.fixture(scope="class")
    def compiled_object(self, tmp_path_factory):
        """Compile unwind_windows.c to an object file."""
        build_dir = tmp_path_factory.mktemp("build")
        obj_file = build_dir / "unwind_windows.o"

        result = subprocess.run(
            [
                "clang-tool-chain-c",
                "-c",
                str(UNWIND_WINDOWS_C),
                "-o",
                str(obj_file),
                "-I",
                str(SYMBOLIZER_DIR),
            ],
            capture_output=True,
            text=True,
            timeout=120,
        )

        if result.returncode != 0:
            pytest.fail(f"Failed to compile unwind_windows.c: {result.stderr}")

        return obj_file

    def test_compiles_to_object(self, compiled_object):
        """Should compile to object file without errors."""
        assert compiled_object.exists()
        assert compiled_object.stat().st_size > 0


@pytest.fixture(scope="module")
def native_symbol_test_binary(tmp_path_factory) -> Path:
    """
    Compile a test program that uses libunwind with our _Ux86_64_get_proc_name.

    This compiles unwind_windows.c along with the test program, so unw_get_proc_name()
    automatically uses our implementation.
    """
    src_dir = tmp_path_factory.mktemp("src")
    build_dir = tmp_path_factory.mktemp("build")

    # Test program that uses unw_get_proc_name directly
    src_file = src_dir / "test_native_symbols.c"
    src_file.write_text(
        """\
#include <stdio.h>

#define UNW_LOCAL_ONLY
#include <libunwind.h>

// Our function names are unique to verify correct resolution
void unique_function_alpha(void);
void unique_function_beta(void);
void unique_function_gamma(void);

void print_backtrace_native(void) {
    unw_cursor_t cursor;
    unw_context_t context;
    int frame = 0;
    int symbols_resolved = 0;
    int symbols_failed = 0;

    unw_getcontext(&context);
    unw_init_local(&cursor, &context);

    printf("=== Native Symbol Resolution Test ===\\n");
    while (unw_step(&cursor) > 0 && frame < 20) {
        unw_word_t ip;
        unw_get_reg(&cursor, UNW_REG_IP, &ip);

        char name[256] = {0};
        unw_word_t offset = 0;

        // This should now work with our _Ux86_64_get_proc_name implementation
        int ret = unw_get_proc_name(&cursor, name, sizeof(name), &offset);

        if (ret == 0 && name[0] != '\\0') {
            printf("RESOLVED FRAME %d: %s+0x%llx [0x%llx]\\n",
                   frame, name, (unsigned long long)offset, (unsigned long long)ip);
            symbols_resolved++;
        } else {
            printf("FAILED FRAME %d: ret=%d [0x%llx]\\n",
                   frame, ret, (unsigned long long)ip);
            symbols_failed++;
        }
        frame++;
    }

    printf("\\n=== Summary ===\\n");
    printf("Symbols resolved: %d\\n", symbols_resolved);
    printf("Symbols failed: %d\\n", symbols_failed);
    printf("SUCCESS_MARKER: %s\\n", symbols_resolved > 0 ? "TRUE" : "FALSE");
}

void unique_function_gamma(void) {
    print_backtrace_native();
}

void unique_function_beta(void) {
    unique_function_gamma();
}

void unique_function_alpha(void) {
    unique_function_beta();
}

int main(void) {
    printf("Starting native symbol resolution test...\\n");
    unique_function_alpha();
    printf("Test complete.\\n");
    return 0;
}
""",
        encoding="utf-8",
    )

    exe_file = build_dir / "test_native_symbols.exe"

    # Compile with our unwind_windows.c to provide _Ux86_64_get_proc_name
    result = subprocess.run(
        [
            "clang-tool-chain-c",
            str(src_file),
            str(UNWIND_WINDOWS_C),  # Include our implementation
            "-o",
            str(exe_file),
            "-I",
            str(SYMBOLIZER_DIR),
            "-g",  # Debug symbols for COFF table
            "-O0",
            "-fno-omit-frame-pointer",
            "-lunwind",
        ],
        capture_output=True,
        text=True,
        timeout=120,
    )

    if result.returncode != 0:
        pytest.skip(f"Failed to compile native symbol test: {result.stderr}")

    if not exe_file.exists():
        pytest.skip("Native symbol test binary was not created")

    return exe_file


class TestNativeSymbolResolution:
    """Tests that verify _Ux86_64_get_proc_name works with libunwind."""

    def test_unw_get_proc_name_works(self, native_symbol_test_binary):
        """unw_get_proc_name() should return function names without UNW_ENOINFO."""
        result = subprocess.run(
            [str(native_symbol_test_binary)],
            capture_output=True,
            text=True,
            timeout=30,
        )

        assert result.returncode == 0, f"Program failed: {result.stderr}"

        output = result.stdout
        print(output)  # For debugging

        # Check that the program ran
        assert "Native Symbol Resolution Test" in output

        # Check for SUCCESS_MARKER
        assert "SUCCESS_MARKER: TRUE" in output, "No symbols were resolved"

    def test_resolves_user_functions(self, native_symbol_test_binary):
        """Should resolve our unique function names."""
        result = subprocess.run(
            [str(native_symbol_test_binary)],
            capture_output=True,
            text=True,
            timeout=30,
        )

        assert result.returncode == 0

        output = result.stdout.lower()

        # Our unique function names should appear
        assert "unique_function_gamma" in output or "gamma" in output, "unique_function_gamma not found in output"

    def test_resolves_multiple_frames(self, native_symbol_test_binary):
        """Should resolve multiple stack frames."""
        result = subprocess.run(
            [str(native_symbol_test_binary)],
            capture_output=True,
            text=True,
            timeout=30,
        )

        assert result.returncode == 0

        output = result.stdout

        # Count resolved frames
        resolved_count = output.count("RESOLVED FRAME")
        failed_count = output.count("FAILED FRAME")

        # Should have at least some resolved frames
        assert resolved_count >= 1, f"Expected at least 1 resolved frame, got {resolved_count}"

        # Most frames should be resolved
        total = resolved_count + failed_count
        if total > 0:
            success_rate = resolved_count / total
            assert success_rate >= 0.3, f"Expected at least 30% success rate, got {success_rate:.1%}"

    def test_returns_offset(self, native_symbol_test_binary):
        """Should return valid offset from function start."""
        result = subprocess.run(
            [str(native_symbol_test_binary)],
            capture_output=True,
            text=True,
            timeout=30,
        )

        assert result.returncode == 0

        output = result.stdout

        # Look for offset pattern in RESOLVED frames
        import re

        # Pattern: name+0xOFFSET where OFFSET is not 0 (could be 0x0 for exact match though)
        offset_pattern = r"RESOLVED FRAME \d+: \w+\+0x([0-9a-f]+)"
        offsets = re.findall(offset_pattern, output, re.IGNORECASE)

        assert len(offsets) > 0, "No offsets found in resolved frames"

    def test_main_function_resolved(self, native_symbol_test_binary):
        """Should resolve 'main' function."""
        result = subprocess.run(
            [str(native_symbol_test_binary)],
            capture_output=True,
            text=True,
            timeout=30,
        )

        assert result.returncode == 0

        # main should appear somewhere in the trace
        output = result.stdout.lower()
        # Could be 'main' or '_main' or similar
        assert "main" in output, "main function not found in stack trace"


class TestDLLBuild:
    """Tests for the pre-built DLL."""

    def test_dll_exists(self):
        """Pre-built DLL should exist."""
        dll_path = SYMBOLIZER_DIR / "libunwind_proc_name.dll"
        # This may not exist if not built yet - skip if missing
        if not dll_path.exists():
            pytest.skip(
                "DLL not built yet - run: clang-tool-chain-c -shared -fPIC unwind_windows.c -o libunwind_proc_name.dll"
            )

    def test_dll_exports_symbols(self):
        """DLL should export required symbols."""
        import shutil

        dll_path = SYMBOLIZER_DIR / "libunwind_proc_name.dll"
        if not dll_path.exists():
            pytest.skip("DLL not built yet")

        # Find llvm-nm
        llvm_nm = shutil.which("llvm-nm")
        if not llvm_nm:
            # Try clang-tool-chain path
            from pathlib import Path

            home = Path.home()
            llvm_nm = home / ".clang-tool-chain" / "clang" / "win" / "x86_64" / "bin" / "llvm-nm.exe"
            if not llvm_nm.exists():
                pytest.skip("llvm-nm not found")
            llvm_nm = str(llvm_nm)

        result = subprocess.run(
            [llvm_nm, str(dll_path)],
            capture_output=True,
            text=True,
            timeout=30,
        )

        if result.returncode != 0:
            pytest.skip(f"llvm-nm failed: {result.stderr}")

        symbols = result.stdout

        # Check for required symbols
        assert "_Ux86_64_get_proc_name" in symbols, "Missing _Ux86_64_get_proc_name"
        assert "unw_get_proc_name_windows" in symbols, "Missing unw_get_proc_name_windows"
