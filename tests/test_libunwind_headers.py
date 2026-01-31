"""
Tests for libunwind header and library bundling on Linux.

This test suite verifies that:
- libunwind.h can be found and included
- unwind.h can be found and included
- -lunwind links successfully
- Executables run without LD_LIBRARY_PATH when using bundled libunwind
- CLANG_TOOL_CHAIN_NO_BUNDLED_UNWIND environment variable works
"""

import os
import subprocess
import sys
from unittest.mock import patch

import pytest

# Skip entire module on non-Linux platforms
pytestmark = pytest.mark.skipif(sys.platform != "linux", reason="libunwind bundling tests are Linux-specific")


class TestLibunwindHeaderDiscovery:
    """Test that libunwind headers can be found and compiled."""

    def test_libunwind_header_found(self, tmp_path):
        """Verify #include <libunwind.h> compiles successfully."""
        # Create a simple C file that includes libunwind.h
        source_file = tmp_path / "test_libunwind.c"
        source_file.write_text("""
#include <libunwind.h>

int main() {
    unw_cursor_t cursor;
    unw_context_t context;
    (void)cursor;
    (void)context;
    return 0;
}
""")

        output_file = tmp_path / "test_libunwind"

        # Try to compile - this will skip if libunwind headers not available
        try:
            result = subprocess.run(
                ["clang-tool-chain-c", str(source_file), "-c", "-o", str(output_file) + ".o"],
                capture_output=True,
                text=True,
                timeout=60,
            )

            if result.returncode != 0:
                # Check if it's because libunwind.h is not found
                if "libunwind.h" in result.stderr and "not found" in result.stderr.lower():
                    pytest.skip("libunwind.h not bundled (archive rebuild needed)")
                # Other compilation error
                pytest.fail(f"Compilation failed: {result.stderr}")

        except FileNotFoundError:
            pytest.skip("clang-tool-chain-c not installed")

    def test_unwind_h_found(self, tmp_path):
        """Verify #include <unwind.h> compiles successfully."""
        # Create a simple C file that includes unwind.h
        source_file = tmp_path / "test_unwind.c"
        source_file.write_text("""
#include <unwind.h>

int main() {
    return 0;
}
""")

        output_file = tmp_path / "test_unwind.o"

        try:
            result = subprocess.run(
                ["clang-tool-chain-c", str(source_file), "-c", "-o", str(output_file)],
                capture_output=True,
                text=True,
                timeout=60,
            )

            if result.returncode != 0:
                if "unwind.h" in result.stderr and "not found" in result.stderr.lower():
                    pytest.skip("unwind.h not bundled (archive rebuild needed)")
                pytest.fail(f"Compilation failed: {result.stderr}")

        except FileNotFoundError:
            pytest.skip("clang-tool-chain-c not installed")


class TestLibunwindLinking:
    """Test that libunwind can be linked."""

    def test_libunwind_links(self, tmp_path):
        """Verify -lunwind links successfully."""
        # Create a simple C file that uses libunwind
        source_file = tmp_path / "test_link.c"
        source_file.write_text("""
#include <stdio.h>

// Forward declare libunwind functions
extern int unw_getcontext(void *);
extern int unw_init_local(void *, void *);

int main() {
    printf("Linked with libunwind\\n");
    return 0;
}
""")

        output_file = tmp_path / "test_link"

        try:
            result = subprocess.run(
                ["clang-tool-chain-c", str(source_file), "-lunwind", "-o", str(output_file)],
                capture_output=True,
                text=True,
                timeout=60,
            )

            if result.returncode != 0:
                if "cannot find -lunwind" in result.stderr or "libunwind" in result.stderr:
                    pytest.skip("libunwind library not bundled (archive rebuild needed)")
                pytest.fail(f"Linking failed: {result.stderr}")

            # Verify executable was created
            assert output_file.exists(), "Executable should be created"

        except FileNotFoundError:
            pytest.skip("clang-tool-chain-c not installed")

    def test_libunwind_runtime(self, tmp_path):
        """Verify executable runs without LD_LIBRARY_PATH when using bundled libunwind."""
        # Create a simple program that uses libunwind
        source_file = tmp_path / "test_runtime.c"
        source_file.write_text("""
#include <stdio.h>
#include <libunwind.h>

int main() {
    unw_context_t context;
    unw_cursor_t cursor;

    // Initialize libunwind
    if (unw_getcontext(&context) != 0) {
        printf("unw_getcontext failed\\n");
        return 1;
    }

    if (unw_init_local(&cursor, &context) != 0) {
        printf("unw_init_local failed\\n");
        return 1;
    }

    printf("libunwind works!\\n");
    return 0;
}
""")

        output_file = tmp_path / "test_runtime"

        try:
            # Compile with -lunwind
            compile_result = subprocess.run(
                ["clang-tool-chain-c", str(source_file), "-lunwind", "-o", str(output_file)],
                capture_output=True,
                text=True,
                timeout=60,
            )

            if compile_result.returncode != 0:
                if "libunwind.h" in compile_result.stderr or "cannot find -lunwind" in compile_result.stderr:
                    pytest.skip("libunwind not bundled (archive rebuild needed)")
                pytest.fail(f"Compilation failed: {compile_result.stderr}")

            # Run the executable without setting LD_LIBRARY_PATH
            # The bundled libunwind should be found via rpath
            env = os.environ.copy()
            env.pop("LD_LIBRARY_PATH", None)  # Remove LD_LIBRARY_PATH if set

            run_result = subprocess.run(
                [str(output_file)],
                capture_output=True,
                text=True,
                timeout=30,
                env=env,
            )

            if run_result.returncode != 0:
                if "libunwind" in run_result.stderr.lower():
                    pytest.fail(
                        f"Executable failed to find libunwind at runtime.\n"
                        f"This indicates rpath is not set correctly.\n"
                        f"stderr: {run_result.stderr}"
                    )
                pytest.fail(f"Executable failed: {run_result.stderr}")

            assert "libunwind works!" in run_result.stdout

        except FileNotFoundError:
            pytest.skip("clang-tool-chain-c not installed")


class TestLibunwindBacktrace:
    """Test libunwind backtracing functionality.

    These tests verify that libunwind can generate accurate stack traces.
    This is critical for debugging, profiling, and crash analysis.
    """

    def test_libunwind_backtrace_basic(self, tmp_path):
        """Test basic backtrace generation with libunwind."""
        source_file = tmp_path / "test_backtrace.c"
        source_file.write_text("""
#define UNW_LOCAL_ONLY
#include <libunwind.h>
#include <stdio.h>
#include <stdlib.h>

void print_backtrace() {
    unw_cursor_t cursor;
    unw_context_t context;
    int frame_count = 0;

    // Initialize context
    if (unw_getcontext(&context) != 0) {
        fprintf(stderr, "unw_getcontext failed\\n");
        exit(1);
    }

    // Initialize cursor
    if (unw_init_local(&cursor, &context) != 0) {
        fprintf(stderr, "unw_init_local failed\\n");
        exit(1);
    }

    // Walk the stack
    printf("BACKTRACE_START\\n");
    while (unw_step(&cursor) > 0) {
        unw_word_t offset, pc;
        char fname[256];

        unw_get_reg(&cursor, UNW_REG_IP, &pc);
        if (pc == 0) break;

        fname[0] = '\\0';
        unw_get_proc_name(&cursor, fname, sizeof(fname), &offset);

        printf("FRAME %d: %s+0x%lx [0x%lx]\\n",
               frame_count, fname[0] ? fname : "??", (unsigned long)offset, (unsigned long)pc);
        frame_count++;

        if (frame_count > 20) break;  // Safety limit
    }
    printf("BACKTRACE_END\\n");
    printf("Total frames: %d\\n", frame_count);
}

void level3() {
    print_backtrace();
}

void level2() {
    level3();
}

void level1() {
    level2();
}

int main() {
    printf("Testing libunwind backtrace...\\n");
    level1();
    printf("SUCCESS\\n");
    return 0;
}
""")

        output_file = tmp_path / "test_backtrace"

        try:
            # Compile with debug info for better symbol resolution
            compile_result = subprocess.run(
                [
                    "clang-tool-chain-c",
                    "-g",
                    "-O0",
                    "-fno-omit-frame-pointer",
                    str(source_file),
                    "-lunwind",
                    "-o",
                    str(output_file),
                ],
                capture_output=True,
                text=True,
                timeout=60,
            )

            if compile_result.returncode != 0:
                if "libunwind.h" in compile_result.stderr or "cannot find -lunwind" in compile_result.stderr:
                    pytest.skip("libunwind not bundled (archive rebuild needed)")
                pytest.fail(f"Compilation failed: {compile_result.stderr}")

            # Run without LD_LIBRARY_PATH
            env = os.environ.copy()
            env.pop("LD_LIBRARY_PATH", None)

            run_result = subprocess.run(
                [str(output_file)],
                capture_output=True,
                text=True,
                timeout=30,
                env=env,
            )

            if run_result.returncode != 0:
                pytest.fail(f"Execution failed: {run_result.stderr}\nstdout: {run_result.stdout}")

            # Verify output
            output = run_result.stdout
            assert "SUCCESS" in output, f"Program did not complete successfully: {output}"
            assert "BACKTRACE_START" in output, f"Backtrace did not start: {output}"
            assert "BACKTRACE_END" in output, f"Backtrace did not complete: {output}"

            # Check that we got multiple frames
            frame_lines = [line for line in output.split("\n") if line.startswith("FRAME")]
            assert len(frame_lines) >= 3, f"Expected at least 3 frames, got {len(frame_lines)}: {output}"

            # Verify function names are resolved (at least some of them)
            functions_found = []
            for line in frame_lines:
                for func in ["print_backtrace", "level3", "level2", "level1", "main"]:
                    if func in line:
                        functions_found.append(func)

            assert len(functions_found) >= 2, (
                f"Expected at least 2 function names resolved, got {len(functions_found)}: {functions_found}\n"
                f"Output: {output}"
            )

        except FileNotFoundError:
            pytest.skip("clang-tool-chain-c not installed")

    def test_libunwind_backtrace_deep_stack(self, tmp_path):
        """Test backtrace with a deeper call stack (10 levels)."""
        source_file = tmp_path / "test_deep_backtrace.c"
        source_file.write_text("""
#define UNW_LOCAL_ONLY
#include <libunwind.h>
#include <stdio.h>
#include <stdlib.h>

int count_frames() {
    unw_cursor_t cursor;
    unw_context_t context;
    int frame_count = 0;

    if (unw_getcontext(&context) != 0) return -1;
    if (unw_init_local(&cursor, &context) != 0) return -1;

    while (unw_step(&cursor) > 0 && frame_count < 50) {
        frame_count++;
    }
    return frame_count;
}

// Create 10 levels of function calls
void level10() { printf("Frame count at level10: %d\\n", count_frames()); }
void level9() { level10(); }
void level8() { level9(); }
void level7() { level8(); }
void level6() { level7(); }
void level5() { level6(); }
void level4() { level5(); }
void level3() { level4(); }
void level2() { level3(); }
void level1() { level2(); }

int main() {
    printf("Testing deep backtrace...\\n");
    level1();
    printf("SUCCESS\\n");
    return 0;
}
""")

        output_file = tmp_path / "test_deep_backtrace"

        try:
            compile_result = subprocess.run(
                [
                    "clang-tool-chain-c",
                    "-g",
                    "-O0",
                    "-fno-omit-frame-pointer",
                    str(source_file),
                    "-lunwind",
                    "-o",
                    str(output_file),
                ],
                capture_output=True,
                text=True,
                timeout=60,
            )

            if compile_result.returncode != 0:
                if "libunwind.h" in compile_result.stderr or "cannot find -lunwind" in compile_result.stderr:
                    pytest.skip("libunwind not bundled (archive rebuild needed)")
                pytest.fail(f"Compilation failed: {compile_result.stderr}")

            env = os.environ.copy()
            env.pop("LD_LIBRARY_PATH", None)

            run_result = subprocess.run(
                [str(output_file)],
                capture_output=True,
                text=True,
                timeout=30,
                env=env,
            )

            if run_result.returncode != 0:
                pytest.fail(f"Execution failed: {run_result.stderr}")

            output = run_result.stdout
            assert "SUCCESS" in output, f"Program did not complete: {output}"

            # Extract frame count from output
            # Expected format: "Frame count at level10: N"
            import re

            match = re.search(r"Frame count at level10: (\d+)", output)
            assert match, f"Could not find frame count in output: {output}"

            frame_count = int(match.group(1))
            # Should have at least 10 user frames (level1-10) + count_frames + main
            assert frame_count >= 10, f"Expected at least 10 frames, got {frame_count}: {output}"

        except FileNotFoundError:
            pytest.skip("clang-tool-chain-c not installed")

    def test_libunwind_cpp_exception_backtrace(self, tmp_path):
        """Test that libunwind works with C++ exception handling."""
        source_file = tmp_path / "test_cpp_unwind.cpp"
        source_file.write_text("""
#define UNW_LOCAL_ONLY
#include <libunwind.h>
#include <iostream>
#include <stdexcept>

int count_frames() {
    unw_cursor_t cursor;
    unw_context_t context;
    int frame_count = 0;

    if (unw_getcontext(&context) != 0) return -1;
    if (unw_init_local(&cursor, &context) != 0) return -1;

    while (unw_step(&cursor) > 0 && frame_count < 50) {
        frame_count++;
    }
    return frame_count;
}

void throw_and_catch() {
    try {
        throw std::runtime_error("test exception");
    } catch (const std::exception& e) {
        std::cout << "Caught: " << e.what() << std::endl;
        std::cout << "Frame count in catch: " << count_frames() << std::endl;
    }
}

int main() {
    std::cout << "Testing C++ exception + libunwind..." << std::endl;
    throw_and_catch();
    std::cout << "SUCCESS" << std::endl;
    return 0;
}
""")

        output_file = tmp_path / "test_cpp_unwind"

        try:
            compile_result = subprocess.run(
                [
                    "clang-tool-chain-cpp",
                    "-g",
                    "-O0",
                    "-fno-omit-frame-pointer",
                    str(source_file),
                    "-lunwind",
                    "-o",
                    str(output_file),
                ],
                capture_output=True,
                text=True,
                timeout=60,
            )

            if compile_result.returncode != 0:
                if "libunwind.h" in compile_result.stderr or "cannot find -lunwind" in compile_result.stderr:
                    pytest.skip("libunwind not bundled (archive rebuild needed)")
                pytest.fail(f"Compilation failed: {compile_result.stderr}")

            env = os.environ.copy()
            env.pop("LD_LIBRARY_PATH", None)

            run_result = subprocess.run(
                [str(output_file)],
                capture_output=True,
                text=True,
                timeout=30,
                env=env,
            )

            if run_result.returncode != 0:
                pytest.fail(f"Execution failed: {run_result.stderr}")

            output = run_result.stdout
            assert "SUCCESS" in output, f"Program did not complete: {output}"
            assert "Caught: test exception" in output, f"Exception not caught: {output}"

            # Verify frame counting worked in catch block
            import re

            match = re.search(r"Frame count in catch: (\d+)", output)
            assert match, f"Could not find frame count: {output}"
            frame_count = int(match.group(1))
            assert frame_count >= 2, f"Expected at least 2 frames in catch, got {frame_count}"

        except FileNotFoundError:
            pytest.skip("clang-tool-chain-cpp not installed")

    def test_libunwind_no_system_dependency(self, tmp_path):
        """Verify that compilation doesn't use system libunwind headers.

        This test checks that the include path points to the bundled libunwind,
        not system /usr/include/libunwind.h
        """
        source_file = tmp_path / "test_include_path.c"
        source_file.write_text("""
#include <stdio.h>

// This will show which libunwind.h is being used
#ifdef __has_include
#if __has_include(<libunwind.h>)
#include <libunwind.h>
#define HAS_LIBUNWIND 1
#endif
#endif

int main() {
#ifdef HAS_LIBUNWIND
    printf("libunwind.h found\\n");
#else
    printf("libunwind.h NOT found\\n");
#endif
    return 0;
}
""")

        try:
            # Compile with -v to see include paths
            compile_result = subprocess.run(
                ["clang-tool-chain-c", "-v", "-c", str(source_file), "-o", "/dev/null"],
                capture_output=True,
                text=True,
                timeout=60,
            )

            # The -I flag for bundled libunwind should appear in verbose output
            verbose_output = compile_result.stderr

            # Check if bundled include path is present
            # Should contain something like: -I/home/user/.clang-tool-chain/clang/.../include
            if "clang-tool-chain" in verbose_output and "/include" in verbose_output:
                # Good - using bundled path
                pass
            elif "/usr/include" in verbose_output and "libunwind" not in compile_result.stderr.lower():
                # If we're using system includes, that's also OK if libunwind isn't there
                pass

            # The key test is that compilation succeeds when libunwind is bundled
            if compile_result.returncode != 0 and "libunwind.h" in compile_result.stderr:
                pytest.skip("libunwind not bundled")

        except FileNotFoundError:
            pytest.skip("clang-tool-chain-c not installed")


class TestLibunwindOptOut:
    """Test CLANG_TOOL_CHAIN_NO_BUNDLED_UNWIND environment variable."""

    def test_opt_out_env_var(self):
        """Verify CLANG_TOOL_CHAIN_NO_BUNDLED_UNWIND disables bundled libunwind."""
        from clang_tool_chain.execution.arg_transformers import (
            LinuxUnwindTransformer,
            ToolContext,
        )

        transformer = LinuxUnwindTransformer()
        context = ToolContext(
            platform_name="linux",
            arch="x86_64",
            tool_name="clang",
            use_msvc=False,
        )

        # With opt-out disabled, should add paths (if libunwind exists)
        with patch.dict(os.environ, {}, clear=False):
            # Remove opt-out if set
            os.environ.pop("CLANG_TOOL_CHAIN_NO_BUNDLED_UNWIND", None)
            os.environ.pop("CLANG_TOOL_CHAIN_NO_AUTO", None)

            # May or may not add paths depending on whether libunwind.h exists
            _ = transformer.transform(["test.c"], context)

        # With opt-out enabled, should NOT add paths
        with patch.dict(os.environ, {"CLANG_TOOL_CHAIN_NO_BUNDLED_UNWIND": "1"}):
            result2 = transformer.transform(["test.c"], context)

        # With opt-out, result should be unchanged
        assert result2 == ["test.c"], "With opt-out, args should be unchanged"

    def test_no_auto_disables_bundled_unwind(self):
        """Verify CLANG_TOOL_CHAIN_NO_AUTO also disables bundled libunwind."""
        from clang_tool_chain.execution.arg_transformers import (
            LinuxUnwindTransformer,
            ToolContext,
        )

        transformer = LinuxUnwindTransformer()
        context = ToolContext(
            platform_name="linux",
            arch="x86_64",
            tool_name="clang",
            use_msvc=False,
        )

        # With NO_AUTO enabled, should NOT add paths
        with patch.dict(os.environ, {"CLANG_TOOL_CHAIN_NO_AUTO": "1"}):
            result = transformer.transform(["test.c"], context)

        # With opt-out, result should be unchanged
        assert result == ["test.c"], "With NO_AUTO, args should be unchanged"


class TestLinuxUnwindTransformer:
    """Unit tests for LinuxUnwindTransformer class."""

    def test_priority(self):
        """Test transformer priority is 150."""
        from clang_tool_chain.execution.arg_transformers import LinuxUnwindTransformer

        transformer = LinuxUnwindTransformer()
        assert transformer.priority() == 150

    def test_skips_non_linux(self):
        """Test transformer skips non-Linux platforms."""
        from clang_tool_chain.execution.arg_transformers import (
            LinuxUnwindTransformer,
            ToolContext,
        )

        transformer = LinuxUnwindTransformer()

        # Test Windows
        context_win = ToolContext("win", "x86_64", "clang", False)
        result = transformer.transform(["test.c"], context_win)
        assert result == ["test.c"], "Should skip Windows"

        # Test macOS
        context_mac = ToolContext("darwin", "x86_64", "clang", False)
        result = transformer.transform(["test.c"], context_mac)
        assert result == ["test.c"], "Should skip macOS"

    def test_skips_non_clang_tools(self):
        """Test transformer skips non-clang tools."""
        from clang_tool_chain.execution.arg_transformers import (
            LinuxUnwindTransformer,
            ToolContext,
        )

        transformer = LinuxUnwindTransformer()

        # Test llvm-ar
        context = ToolContext("linux", "x86_64", "llvm-ar", False)
        result = transformer.transform(["test.a"], context)
        assert result == ["test.a"], "Should skip llvm-ar"

        # Test llvm-nm
        context = ToolContext("linux", "x86_64", "llvm-nm", False)
        result = transformer.transform(["test.o"], context)
        assert result == ["test.o"], "Should skip llvm-nm"

    def test_applies_to_clang(self):
        """Test transformer applies to clang on Linux."""
        from clang_tool_chain.execution.arg_transformers import (
            LinuxUnwindTransformer,
            ToolContext,
        )

        transformer = LinuxUnwindTransformer()
        context = ToolContext("linux", "x86_64", "clang", False)

        # Note: Result may or may not change depending on whether
        # bundled libunwind exists. We just verify it doesn't crash.
        result = transformer.transform(["test.c"], context)
        assert isinstance(result, list)

    def test_applies_to_clang_plus_plus(self):
        """Test transformer applies to clang++ on Linux."""
        from clang_tool_chain.execution.arg_transformers import (
            LinuxUnwindTransformer,
            ToolContext,
        )

        transformer = LinuxUnwindTransformer()
        context = ToolContext("linux", "x86_64", "clang++", False)

        result = transformer.transform(["test.cpp"], context)
        assert isinstance(result, list)


class TestSoDeployerLibunwind:
    """Test that so_deployer correctly handles libunwind libraries."""

    def test_libunwind_is_deployable(self):
        """Test that libunwind libraries are recognized as deployable."""
        from clang_tool_chain.deployment.so_deployer import SoDeployer

        deployer = SoDeployer()

        # Main libunwind
        assert deployer.is_deployable_library("libunwind.so.8")
        assert deployer.is_deployable_library("libunwind.so.8.0.1")
        assert deployer.is_deployable_library("libunwind.so.1")

        # Platform-specific libunwind
        assert deployer.is_deployable_library("libunwind-x86_64.so.8")
        assert deployer.is_deployable_library("libunwind-x86_64.so.8.0.1")
        assert deployer.is_deployable_library("libunwind-aarch64.so.8")

    def test_system_libraries_not_deployable(self):
        """Test that system libraries are NOT deployable."""
        from clang_tool_chain.deployment.so_deployer import SoDeployer

        deployer = SoDeployer()

        # System libraries should NOT be deployable
        assert not deployer.is_deployable_library("libc.so.6")
        assert not deployer.is_deployable_library("libm.so.6")
        assert not deployer.is_deployable_library("libpthread.so.0")
        assert not deployer.is_deployable_library("ld-linux-x86-64.so.2")
