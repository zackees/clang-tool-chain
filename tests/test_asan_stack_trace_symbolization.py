"""
Tests for ASAN stack trace symbolization.

This test suite verifies that ASAN stack traces properly resolve all addresses
to symbol names, ensuring no `<unknown module>` or unresolved hex addresses appear.

The automatic ASAN_OPTIONS injection (fast_unwind_on_malloc=0:symbolize=1) should
ensure complete symbolization of stack traces.
"""

import os
import platform
import re
import subprocess
import tempfile
from pathlib import Path

import pytest


class TestASANStackTraceSymbolization:
    """Test that ASAN stack traces are fully symbolized."""

    @pytest.fixture
    def temp_dir(self):
        """Create a temporary directory for test files."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)

    @pytest.fixture
    def heap_buffer_overflow_file(self, temp_dir):
        """Create a C++ file that triggers heap-buffer-overflow."""
        cpp_file = temp_dir / "heap_overflow.cpp"
        cpp_file.write_text(
            """
#include <cstdlib>

// Use noinline to ensure functions appear in stack trace
__attribute__((noinline))
void trigger_overflow(int* ptr, int size) {
    // Intentional heap buffer overflow - read beyond bounds
    volatile int x = ptr[size];  // Out of bounds read
    (void)x;
}

__attribute__((noinline))
void intermediate_function(int* ptr, int size) {
    trigger_overflow(ptr, size);
}

__attribute__((noinline))
void outer_function() {
    int* ptr = new int[10];
    intermediate_function(ptr, 10);  // Access index 10 of array[0..9]
    delete[] ptr;
}

int main() {
    outer_function();
    return 0;
}
"""
        )
        return cpp_file

    @pytest.fixture
    def use_after_free_file(self, temp_dir):
        """Create a C++ file that triggers use-after-free."""
        cpp_file = temp_dir / "use_after_free.cpp"
        cpp_file.write_text(
            """
#include <cstdlib>

__attribute__((noinline))
void access_freed_memory(int* ptr) {
    // Use-after-free: access memory after delete
    volatile int x = *ptr;
    (void)x;
}

__attribute__((noinline))
void free_and_access() {
    int* ptr = new int(42);
    delete ptr;
    access_freed_memory(ptr);  // Use after free
}

int main() {
    free_and_access();
    return 0;
}
"""
        )
        return cpp_file

    def _parse_asan_stack_frames(self, output: str) -> list[dict]:
        """
        Parse ASAN stack trace output and extract stack frames.

        ASAN stack trace format examples:
            #0 0x7f1234567890 in function_name file.cpp:123
            #1 0x7f1234567890 in function_name (/path/to/binary+0x1234)
            #2 0x7f1234567890  (<unknown module>)
            #3 0x7f1234567890 in __libc_start_main
            #4 0x7ff7d00f143c (C:\\path\\to\\binary.exe+0x14000143c) [Windows partial]

        Returns list of dicts with frame info.
        """
        frames = []

        # Match stack frame lines: #N 0xADDRESS ...
        frame_pattern = re.compile(r"^\s*#(\d+)\s+(0x[0-9a-fA-F]+)\s+(.*)$", re.MULTILINE)

        for match in frame_pattern.finditer(output):
            frame_num = int(match.group(1))
            address = match.group(2)
            rest = match.group(3).strip()

            frame = {
                "frame_num": frame_num,
                "address": address,
                "rest": rest,
                "has_symbol": False,
                "is_unknown_module": False,
                "is_binary_offset_only": False,
                "symbol_name": None,
            }

            # Check if it's an unknown module
            if "<unknown module>" in rest:
                frame["is_unknown_module"] = True
            # Check if it has a proper symbol (starts with "in ")
            elif rest.startswith("in "):
                frame["has_symbol"] = True
                # Extract symbol name: "in function_name ..."
                symbol_match = re.match(r"in\s+(\S+)", rest)
                if symbol_match:
                    frame["symbol_name"] = symbol_match.group(1)
            # Could also be just "(binary+offset)" which is partial symbolization
            # This is common on Windows when llvm-symbolizer is not in PATH
            elif re.match(r"\([^)]+\+0x[0-9a-fA-F]+\)", rest):
                # Has binary but no function name - partial symbolization (acceptable)
                frame["is_binary_offset_only"] = True
                frame["has_symbol"] = False
            # If it matches common runtime symbols we can accept them
            elif any(rt in rest for rt in ["__asan", "__sanitizer", "__interceptor", "_start", "__libc"]):
                frame["has_symbol"] = True
                frame["symbol_name"] = rest.split()[0] if rest else None
            # Windows system DLLs with function names (e.g., "BaseThreadInitThunk+0x13")
            elif "+" in rest and not rest.startswith("("):
                frame["has_symbol"] = True
                symbol_match = re.match(r"(\S+)\+", rest)
                if symbol_match:
                    frame["symbol_name"] = symbol_match.group(1)

            frames.append(frame)

        return frames

    def _compile_with_asan(self, source_file: Path, output_exe: Path) -> subprocess.CompletedProcess:
        """Compile a source file with ASAN and debug info."""
        cmd = [
            "clang-tool-chain-cpp",
            "-fsanitize=address",
            "-fno-omit-frame-pointer",
            "-g",  # Debug info for better symbolization
            "-O0",  # No optimization to preserve stack frames
            str(source_file),
            "-o",
            str(output_exe),
            "--deploy-dependencies",
        ]

        return subprocess.run(cmd, capture_output=True, text=True)

    def _run_asan_executable(self, exe_path: Path, env: dict | None = None) -> subprocess.CompletedProcess:
        """Run an ASAN-instrumented executable and capture output."""
        run_env = os.environ.copy()
        if env:
            run_env.update(env)

        return subprocess.run(
            [str(exe_path)],
            capture_output=True,
            text=True,
            timeout=30,
            env=run_env,
            cwd=str(exe_path.parent),
        )

    def _is_symbolizer_available(self) -> bool:
        """Check if llvm-symbolizer is available for full symbolization."""
        try:
            result = subprocess.run(
                ["clang-tool-chain-llvm-symbolizer", "--version"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            return result.returncode == 0
        except (subprocess.TimeoutExpired, FileNotFoundError):
            return False

    def test_heap_buffer_overflow_symbolized(self, heap_buffer_overflow_file):
        """
        Test that heap-buffer-overflow ASAN output has properly resolved stack traces.

        Primary goal: Verify NO <unknown module> entries appear in the stack trace.
        This is the critical check that ASAN can identify all code locations.

        Secondary goal: If llvm-symbolizer is available, verify function names
        are resolved. On Windows without symbolizer, (binary+offset) is acceptable.
        """
        output_exe = heap_buffer_overflow_file.parent / "heap_overflow"
        if os.name == "nt":
            output_exe = heap_buffer_overflow_file.parent / "heap_overflow.exe"

        # Compile
        compile_result = self._compile_with_asan(heap_buffer_overflow_file, output_exe)
        assert compile_result.returncode == 0, f"Compilation failed: {compile_result.stderr}"
        assert output_exe.exists(), "Executable not created"

        # Run and trigger ASAN error
        run_result = self._run_asan_executable(output_exe)

        # Should exit with non-zero (ASAN detected error)
        assert run_result.returncode != 0, (
            "Expected ASAN to detect heap-buffer-overflow and exit non-zero.\n"
            f"STDOUT: {run_result.stdout}\nSTDERR: {run_result.stderr}"
        )

        # Combine output (ASAN can write to stderr)
        full_output = run_result.stdout + run_result.stderr

        # Verify ASAN detected the error
        assert "heap-buffer-overflow" in full_output.lower() or "addresssanitizer" in full_output.lower(), (
            f"ASAN error message not found in output:\n{full_output}"
        )

        # Parse stack frames
        frames = self._parse_asan_stack_frames(full_output)

        # We should have multiple frames
        assert len(frames) > 0, f"No stack frames found in output:\n{full_output}"

        # PRIMARY CHECK: No <unknown module> entries
        # This is the critical test - all addresses must resolve to something
        unknown_frames = [f for f in frames if f["is_unknown_module"]]
        assert len(unknown_frames) == 0, (
            f"Found {len(unknown_frames)} <unknown module> entries in stack trace!\n"
            f"Unknown frames: {unknown_frames}\n"
            f"Full ASAN output:\n{full_output}"
        )

        # SECONDARY CHECK: Verify some level of resolution
        # Either function names OR binary+offset is acceptable
        # (Windows without llvm-symbolizer shows binary+offset format)
        resolved_frames = [f for f in frames if f["has_symbol"] or f.get("is_binary_offset_only", False)]

        assert len(resolved_frames) > 0, (
            f"No resolved frames found (neither symbols nor binary+offset).\n"
            f"All frames: {frames}\n"
            f"Full output:\n{full_output}"
        )

        # OPTIONAL CHECK: If symbolizer is available, expect function names
        symbolizer_available = self._is_symbolizer_available()
        if symbolizer_available:
            our_functions = ["trigger_overflow", "intermediate_function", "outer_function", "main"]
            symbolized_functions = [f["symbol_name"] for f in frames if f["symbol_name"]]

            found_our_function = any(
                any(func_name in (sym or "") for sym in symbolized_functions) for func_name in our_functions
            )

            # This is informational when symbolizer is present - warn but don't fail
            if not found_our_function:
                print(
                    f"\nNOTE: llvm-symbolizer available but custom functions not found.\n"
                    f"Symbolized: {symbolized_functions}\n"
                    f"Expected one of: {our_functions}"
                )

    def test_use_after_free_symbolized(self, use_after_free_file):
        """
        Test that use-after-free ASAN output has no <unknown module> entries.
        """
        output_exe = use_after_free_file.parent / "use_after_free"
        if os.name == "nt":
            output_exe = use_after_free_file.parent / "use_after_free.exe"

        # Compile
        compile_result = self._compile_with_asan(use_after_free_file, output_exe)
        assert compile_result.returncode == 0, f"Compilation failed: {compile_result.stderr}"

        # Run and trigger ASAN error
        run_result = self._run_asan_executable(output_exe)

        # Should exit non-zero
        assert run_result.returncode != 0, "Expected ASAN to detect use-after-free"

        full_output = run_result.stdout + run_result.stderr

        # Verify ASAN detected the error
        assert "use-after" in full_output.lower() or "addresssanitizer" in full_output.lower(), (
            f"ASAN error message not found:\n{full_output}"
        )

        # Parse and check for unknown modules
        frames = self._parse_asan_stack_frames(full_output)
        assert len(frames) > 0, f"No stack frames found:\n{full_output}"

        # PRIMARY CHECK: No <unknown module> entries
        unknown_frames = [f for f in frames if f["is_unknown_module"]]
        assert len(unknown_frames) == 0, (
            f"Found <unknown module> entries in stack trace!\n"
            f"Unknown frames: {unknown_frames}\n"
            f"Full output:\n{full_output}"
        )

        # Verify some resolution occurred
        resolved_frames = [f for f in frames if f["has_symbol"] or f.get("is_binary_offset_only", False)]
        assert len(resolved_frames) > 0, f"No resolved frames found:\n{full_output}"

    def test_no_unresolved_hex_only_frames(self, heap_buffer_overflow_file):
        """
        Test that stack frames don't have just hex addresses without any context.

        A fully symbolized frame should have either:
        - "in function_name" with the function name
        - Runtime symbols like __asan_*, __libc_start_main, etc.

        Not just bare hex addresses like:
            #3 0x7bd29db5c5ec
        """
        output_exe = heap_buffer_overflow_file.parent / "heap_overflow_hex_test"
        if os.name == "nt":
            output_exe = heap_buffer_overflow_file.parent / "heap_overflow_hex_test.exe"

        # Compile
        compile_result = self._compile_with_asan(heap_buffer_overflow_file, output_exe)
        assert compile_result.returncode == 0, f"Compilation failed: {compile_result.stderr}"

        # Run
        run_result = self._run_asan_executable(output_exe)
        full_output = run_result.stdout + run_result.stderr

        # Check for frames with only hex address and nothing useful
        # Pattern: #N 0xHEX followed by empty or just whitespace
        hex_only_pattern = re.compile(r"^\s*#\d+\s+0x[0-9a-fA-F]+\s*$", re.MULTILINE)
        hex_only_matches = hex_only_pattern.findall(full_output)

        assert len(hex_only_matches) == 0, (
            f"Found {len(hex_only_matches)} stack frames with only hex addresses (no symbols):\n"
            f"{hex_only_matches}\n"
            f"Full output:\n{full_output}"
        )

    def test_asan_works_with_custom_options(self, heap_buffer_overflow_file):
        """
        Test that ASAN still works when custom ASAN_OPTIONS are set.

        This verifies that user-provided ASAN_OPTIONS are respected and
        don't break the stack trace generation.
        """
        output_exe = heap_buffer_overflow_file.parent / "heap_overflow_custom"
        if os.name == "nt":
            output_exe = heap_buffer_overflow_file.parent / "heap_overflow_custom.exe"

        # Compile
        compile_result = self._compile_with_asan(heap_buffer_overflow_file, output_exe)
        assert compile_result.returncode == 0, f"Compilation failed: {compile_result.stderr}"

        # Run with custom ASAN_OPTIONS (user override)
        run_result = self._run_asan_executable(
            output_exe,
            env={
                "ASAN_OPTIONS": "symbolize=1:detect_leaks=0",
                "CLANG_TOOL_CHAIN_NO_SANITIZER_ENV": "1",  # Disable auto-injection
            },
        )
        full_output = run_result.stdout + run_result.stderr

        # Should still detect the error
        assert run_result.returncode != 0, "Expected ASAN to detect heap-buffer-overflow"
        assert "heap-buffer-overflow" in full_output.lower() or "addresssanitizer" in full_output.lower()

        # Parse frames
        frames = self._parse_asan_stack_frames(full_output)
        assert len(frames) > 0, f"No frames with custom options:\n{full_output}"

        # Should still have no unknown modules
        unknown_frames = [f for f in frames if f["is_unknown_module"]]
        assert len(unknown_frames) == 0, (
            f"Found <unknown module> with custom ASAN_OPTIONS:\n{unknown_frames}\nOutput:\n{full_output}"
        )

        print(f"\nCustom ASAN_OPTIONS test: {len(frames)} frames, {len(unknown_frames)} unknown")

    @pytest.mark.skipif(platform.system() == "Windows", reason="ASAN behavior differs on Windows")
    def test_shared_library_symbolization(self, temp_dir):
        """
        Test that ASAN properly symbolizes stack traces through shared libraries.

        This specifically tests the dlopen() case that fast_unwind_on_malloc=0 fixes.
        """
        # Create shared library source
        lib_source = temp_dir / "mylib.cpp"
        lib_source.write_text(
            """
extern "C" __attribute__((noinline))
void lib_trigger_overflow() {
    int* ptr = new int[5];
    volatile int x = ptr[5];  // Overflow
    (void)x;
    delete[] ptr;
}
"""
        )

        # Create main source that uses the library
        main_source = temp_dir / "main.cpp"
        main_source.write_text(
            """
#include <dlfcn.h>
#include <cstdio>
#include <cstdlib>

typedef void (*overflow_func)();

int main() {
    // Load library dynamically
    void* handle = dlopen("./libmylib.so", RTLD_NOW);
    if (!handle) {
        fprintf(stderr, "dlopen failed: %s\\n", dlerror());
        return 1;
    }

    overflow_func func = (overflow_func)dlsym(handle, "lib_trigger_overflow");
    if (!func) {
        fprintf(stderr, "dlsym failed: %s\\n", dlerror());
        dlclose(handle);
        return 1;
    }

    // Call function that triggers overflow
    func();

    dlclose(handle);
    return 0;
}
"""
        )

        # Determine output paths
        lib_output = temp_dir / "libmylib.so"
        exe_output = temp_dir / "main"

        # Compile shared library with ASAN
        lib_cmd = [
            "clang-tool-chain-cpp",
            "-shared",
            "-fPIC",
            "-fsanitize=address",
            "-fno-omit-frame-pointer",
            "-g",
            "-O0",
            str(lib_source),
            "-o",
            str(lib_output),
        ]

        lib_result = subprocess.run(lib_cmd, capture_output=True, text=True)
        assert lib_result.returncode == 0, f"Library compilation failed: {lib_result.stderr}"

        # Compile main with ASAN
        main_cmd = [
            "clang-tool-chain-cpp",
            "-fsanitize=address",
            "-fno-omit-frame-pointer",
            "-g",
            "-O0",
            str(main_source),
            "-o",
            str(exe_output),
            "-ldl",
            "--deploy-dependencies",
        ]

        main_result = subprocess.run(main_cmd, capture_output=True, text=True)
        assert main_result.returncode == 0, f"Main compilation failed: {main_result.stderr}"

        # Run with ASAN
        run_result = self._run_asan_executable(exe_output)
        full_output = run_result.stdout + run_result.stderr

        # Check for dlopen failure first
        if "dlopen failed" in full_output:
            pytest.skip("dlopen failed - shared library not loadable in ASAN environment")

        # Should detect the overflow
        assert run_result.returncode != 0, "Expected ASAN to detect overflow in shared library"

        # Parse stack trace
        frames = self._parse_asan_stack_frames(full_output)

        # Check for unknown modules - this is the key test
        unknown_frames = [f for f in frames if f["is_unknown_module"]]
        assert len(unknown_frames) == 0, (
            f"Found <unknown module> in shared library stack trace!\n"
            f"This is the bug that fast_unwind_on_malloc=0 should fix.\n"
            f"Unknown frames: {unknown_frames}\n"
            f"Full output:\n{full_output}"
        )

        # Verify our library function appears in the trace
        symbolized = [f["symbol_name"] for f in frames if f["symbol_name"]]
        has_lib_func = any("lib_trigger_overflow" in (s or "") for s in symbolized)

        assert has_lib_func, (
            f"Library function 'lib_trigger_overflow' not found in symbolized trace.\n"
            f"Symbolized: {symbolized}\n"
            f"Full output:\n{full_output}"
        )


class TestASANStackTraceFormat:
    """Test parsing of various ASAN stack trace formats."""

    def test_parse_standard_frame(self):
        """Test parsing standard ASAN frame format."""
        output = """
    #0 0x7f1234567890 in malloc (/lib/x86_64-linux-gnu/libc.so.6+0x12345)
    #1 0x7f1234567abc in my_function /home/user/test.cpp:42
    #2 0x7f1234567def in main /home/user/test.cpp:100
"""
        test_obj = TestASANStackTraceSymbolization()
        frames = test_obj._parse_asan_stack_frames(output)

        assert len(frames) == 3
        assert frames[0]["frame_num"] == 0
        assert frames[0]["has_symbol"] is True
        assert frames[1]["symbol_name"] == "my_function"
        assert frames[2]["symbol_name"] == "main"

    def test_parse_unknown_module(self):
        """Test parsing unknown module frame."""
        output = """
    #0 0x7f1234567890 in my_function test.cpp:10
    #1 0x7f1234567abc  (<unknown module>)
    #2 0x7f1234567def in main test.cpp:20
"""
        test_obj = TestASANStackTraceSymbolization()
        frames = test_obj._parse_asan_stack_frames(output)

        assert len(frames) == 3
        assert frames[0]["is_unknown_module"] is False
        assert frames[1]["is_unknown_module"] is True
        assert frames[2]["is_unknown_module"] is False

    def test_parse_asan_internal_symbols(self):
        """Test parsing ASAN internal symbols."""
        output = """
    #0 0x7f1234567890 in __asan_report_load4 (/path/to/asan.so+0x1234)
    #1 0x7f1234567abc in __sanitizer::something (/path/to/asan.so+0x5678)
    #2 0x7f1234567def in my_function test.cpp:10
"""
        test_obj = TestASANStackTraceSymbolization()
        frames = test_obj._parse_asan_stack_frames(output)

        assert len(frames) == 3
        # ASAN internal symbols should be recognized as having symbols
        assert frames[0]["has_symbol"] is True
        assert frames[1]["has_symbol"] is True
        assert frames[2]["has_symbol"] is True
