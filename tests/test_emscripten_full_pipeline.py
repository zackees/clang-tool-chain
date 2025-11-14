"""
Comprehensive Emscripten compilation pipeline tests.

This module tests the complete Emscripten toolchain workflow including:
- Header file compilation
- Multi-file compilation
- Object file generation
- Thin archive creation (static libraries)
- Static library linking
- Precompiled header (PCH) generation
- Full pipeline integration

Tests follow patterns from test_gnu_abi.py and test_msvc_compile.py.
"""

import subprocess
import sys
from pathlib import Path

import pytest


def is_emscripten_available() -> bool:
    """Check if Emscripten binaries are available for this platform."""
    try:
        result = subprocess.run(
            ["clang-tool-chain-emcc", "--version"],
            capture_output=True,
            text=True,
            timeout=30,
        )
        return result.returncode == 0
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False


@pytest.mark.skipif(not is_emscripten_available(), reason="Emscripten binaries not available for this platform")
class TestEmscriptenCompilationPipeline:
    """Comprehensive Emscripten compilation pipeline tests."""

    def test_01_header_files_compilation(self, tmp_path: Path) -> None:
        """Test that header files are correctly included in compilation."""
        # Create world.h header
        world_h = tmp_path / "world.h"
        world_h.write_text(
            """
#ifndef WORLD_H
#define WORLD_H

#include <string>

std::string get_world_message();

#endif // WORLD_H
"""
        )

        # Create hello.h header
        hello_h = tmp_path / "hello.h"
        hello_h.write_text(
            """
#ifndef HELLO_H
#define HELLO_H

#include <string>

std::string get_hello_message();

#endif // HELLO_H
"""
        )

        # Create main.cpp that uses both headers
        main_cpp = tmp_path / "main.cpp"
        main_cpp.write_text(
            """
#include <iostream>
#include "hello.h"
#include "world.h"

std::string get_hello_message() {
    return "Hello";
}

std::string get_world_message() {
    return "World";
}

int main() {
    std::cout << get_hello_message() << " " << get_world_message() << "!" << std::endl;
    return 0;
}
"""
        )

        # Compile with header includes
        output_js = tmp_path / "main.js"
        result = subprocess.run(
            [
                "clang-tool-chain-empp",
                str(main_cpp),
                "-I",
                str(tmp_path),
                "-o",
                str(output_js),
            ],
            capture_output=True,
            text=True,
            timeout=300,
        )

        assert result.returncode == 0, f"Compilation failed:\nstdout: {result.stdout}\nstderr: {result.stderr}"
        assert output_js.exists(), "Output JavaScript file was not created"
        assert (tmp_path / "main.wasm").exists(), "Output WebAssembly file was not created"

        # Execute the compiled WASM
        exec_result = subprocess.run(
            ["node", str(output_js)],
            capture_output=True,
            text=True,
            timeout=30,
            cwd=tmp_path,
        )

        assert (
            exec_result.returncode == 0
        ), f"Execution failed:\nstdout: {exec_result.stdout}\nstderr: {exec_result.stderr}"
        assert "Hello World!" in exec_result.stdout, f"Expected output not found. Got: {exec_result.stdout}"

    def test_02_multi_file_compilation(self, tmp_path: Path) -> None:
        """Test compilation of multiple separate source files."""
        # Create hello.cpp
        hello_cpp = tmp_path / "hello.cpp"
        hello_cpp.write_text(
            """
#include <string>

std::string get_hello() {
    return "Hello";
}
"""
        )

        # Create world.cpp
        world_cpp = tmp_path / "world.cpp"
        world_cpp.write_text(
            """
#include <string>

std::string get_world() {
    return "World";
}
"""
        )

        # Create main.cpp
        main_cpp = tmp_path / "main.cpp"
        main_cpp.write_text(
            """
#include <iostream>
#include <string>

std::string get_hello();
std::string get_world();

int main() {
    std::cout << get_hello() << " " << get_world() << "!" << std::endl;
    return 0;
}
"""
        )

        # Compile all files together
        output_js = tmp_path / "program.js"
        result = subprocess.run(
            [
                "clang-tool-chain-empp",
                str(hello_cpp),
                str(world_cpp),
                str(main_cpp),
                "-o",
                str(output_js),
            ],
            capture_output=True,
            text=True,
            timeout=300,
        )

        assert (
            result.returncode == 0
        ), f"Multi-file compilation failed:\nstdout: {result.stdout}\nstderr: {result.stderr}"
        assert output_js.exists(), "Output file was not created"

        # Execute
        exec_result = subprocess.run(
            ["node", str(output_js)],
            capture_output=True,
            text=True,
            timeout=30,
            cwd=tmp_path,
        )

        assert exec_result.returncode == 0, f"Execution failed: {exec_result.stderr}"
        assert "Hello World!" in exec_result.stdout

    def test_03_object_file_generation(self, tmp_path: Path) -> None:
        """Test generation of object files (.o) using -c flag."""
        # Create source file
        hello_cpp = tmp_path / "hello.cpp"
        hello_cpp.write_text(
            """
#include <string>

std::string get_message() {
    return "Hello from object file!";
}
"""
        )

        # Compile to object file
        hello_o = tmp_path / "hello.o"
        result = subprocess.run(
            [
                "clang-tool-chain-empp",
                "-c",
                str(hello_cpp),
                "-o",
                str(hello_o),
            ],
            capture_output=True,
            text=True,
            timeout=300,
        )

        assert (
            result.returncode == 0
        ), f"Object file compilation failed:\nstdout: {result.stdout}\nstderr: {result.stderr}"
        assert hello_o.exists(), "Object file was not created"
        assert hello_o.stat().st_size > 0, "Object file is empty"

    def test_04_thin_archive_creation(self, tmp_path: Path) -> None:
        """Test creation of thin archives (.a) using emar."""
        # Create multiple source files
        file1_cpp = tmp_path / "file1.cpp"
        file1_cpp.write_text(
            """
int add(int a, int b) {
    return a + b;
}
"""
        )

        file2_cpp = tmp_path / "file2.cpp"
        file2_cpp.write_text(
            """
int multiply(int a, int b) {
    return a * b;
}
"""
        )

        # Compile to object files
        file1_o = tmp_path / "file1.o"
        file2_o = tmp_path / "file2.o"

        result1 = subprocess.run(
            ["clang-tool-chain-empp", "-c", str(file1_cpp), "-o", str(file1_o)],
            capture_output=True,
            text=True,
            timeout=300,
        )
        assert result1.returncode == 0, f"file1.o compilation failed: {result1.stderr}"
        assert file1_o.exists()

        result2 = subprocess.run(
            ["clang-tool-chain-empp", "-c", str(file2_cpp), "-o", str(file2_o)],
            capture_output=True,
            text=True,
            timeout=300,
        )
        assert result2.returncode == 0, f"file2.o compilation failed: {result2.stderr}"
        assert file2_o.exists()

        # Create thin archive using emar
        libmath_a = tmp_path / "libmath.a"
        result = subprocess.run(
            [
                "clang-tool-chain-emar",
                "rcs",
                str(libmath_a),
                str(file1_o),
                str(file2_o),
            ],
            capture_output=True,
            text=True,
            timeout=300,
        )

        assert result.returncode == 0, f"Archive creation failed:\nstdout: {result.stdout}\nstderr: {result.stderr}"
        assert libmath_a.exists(), "Archive file was not created"
        assert libmath_a.stat().st_size > 0, "Archive file is empty"

    def test_05_static_library_linking(self, tmp_path: Path) -> None:
        """Test linking against static library (.a file)."""
        # Create library source files
        math_ops_cpp = tmp_path / "math_ops.cpp"
        math_ops_cpp.write_text(
            """
int add(int a, int b) {
    return a + b;
}

int subtract(int a, int b) {
    return a - b;
}
"""
        )

        string_ops_cpp = tmp_path / "string_ops.cpp"
        string_ops_cpp.write_text(
            """
#include <string>

std::string concat(const std::string& a, const std::string& b) {
    return a + b;
}
"""
        )

        # Compile to object files
        math_ops_o = tmp_path / "math_ops.o"
        string_ops_o = tmp_path / "string_ops.o"

        subprocess.run(
            ["clang-tool-chain-empp", "-c", str(math_ops_cpp), "-o", str(math_ops_o)],
            capture_output=True,
            text=True,
            timeout=300,
            check=True,
        )

        subprocess.run(
            ["clang-tool-chain-empp", "-c", str(string_ops_cpp), "-o", str(string_ops_o)],
            capture_output=True,
            text=True,
            timeout=300,
            check=True,
        )

        # Create static library
        libops_a = tmp_path / "libops.a"
        subprocess.run(
            ["clang-tool-chain-emar", "rcs", str(libops_a), str(math_ops_o), str(string_ops_o)],
            capture_output=True,
            text=True,
            timeout=300,
            check=True,
        )

        # Create main program that uses the library
        main_cpp = tmp_path / "main.cpp"
        main_cpp.write_text(
            """
#include <iostream>
#include <string>

int add(int a, int b);
int subtract(int a, int b);
std::string concat(const std::string& a, const std::string& b);

int main() {
    int sum = add(5, 3);
    int diff = subtract(10, 4);
    std::string result = concat("Static", "Library");

    std::cout << "Sum: " << sum << std::endl;
    std::cout << "Diff: " << diff << std::endl;
    std::cout << "Concat: " << result << std::endl;

    return 0;
}
"""
        )

        # Link against static library
        output_js = tmp_path / "program.js"
        result = subprocess.run(
            [
                "clang-tool-chain-empp",
                str(main_cpp),
                str(libops_a),
                "-o",
                str(output_js),
            ],
            capture_output=True,
            text=True,
            timeout=300,
        )

        assert result.returncode == 0, f"Linking failed:\nstdout: {result.stdout}\nstderr: {result.stderr}"
        assert output_js.exists()

        # Execute
        exec_result = subprocess.run(
            ["node", str(output_js)],
            capture_output=True,
            text=True,
            timeout=30,
            cwd=tmp_path,
        )

        assert exec_result.returncode == 0, f"Execution failed: {exec_result.stderr}"
        assert "Sum: 8" in exec_result.stdout
        assert "Diff: 6" in exec_result.stdout
        assert "Concat: StaticLibrary" in exec_result.stdout

    def test_06_precompiled_headers(self, tmp_path: Path) -> None:
        """Test PCH generation and usage."""
        # Create a header file with common includes
        common_h = tmp_path / "common.h"
        common_h.write_text(
            """
#ifndef COMMON_H
#define COMMON_H

#include <iostream>
#include <string>
#include <vector>
#include <map>

// Common type definitions
using StringVector = std::vector<std::string>;
using StringMap = std::map<std::string, std::string>;

// Common inline function
inline std::string get_greeting() {
    return "Hello from PCH!";
}

#endif // COMMON_H
"""
        )

        # Generate precompiled header
        common_pch = tmp_path / "common.h.pch"
        pch_result = subprocess.run(
            [
                "clang-tool-chain-empp",
                "-x",
                "c++-header",
                str(common_h),
                "-o",
                str(common_pch),
            ],
            capture_output=True,
            text=True,
            timeout=300,
        )

        assert (
            pch_result.returncode == 0
        ), f"PCH generation failed:\nstdout: {pch_result.stdout}\nstderr: {pch_result.stderr}"
        assert common_pch.exists(), "Precompiled header was not created"
        assert common_pch.stat().st_size > 0, "Precompiled header is empty"

        # Create source file that uses the PCH
        main_cpp = tmp_path / "main.cpp"
        main_cpp.write_text(
            """
#include "common.h"

int main() {
    StringVector messages;
    messages.push_back(get_greeting());
    messages.push_back("PCH works!");

    for (const auto& msg : messages) {
        std::cout << msg << std::endl;
    }

    return 0;
}
"""
        )

        # Compile using the PCH
        output_js = tmp_path / "program.js"
        compile_result = subprocess.run(
            [
                "clang-tool-chain-empp",
                "-include-pch",
                str(common_pch),
                str(main_cpp),
                "-o",
                str(output_js),
            ],
            capture_output=True,
            text=True,
            timeout=300,
        )

        assert (
            compile_result.returncode == 0
        ), f"Compilation with PCH failed:\nstdout: {compile_result.stdout}\nstderr: {compile_result.stderr}"
        assert output_js.exists()

        # Execute
        exec_result = subprocess.run(
            ["node", str(output_js)],
            capture_output=True,
            text=True,
            timeout=30,
            cwd=tmp_path,
        )

        assert exec_result.returncode == 0, f"Execution failed: {exec_result.stderr}"
        assert "Hello from PCH!" in exec_result.stdout
        assert "PCH works!" in exec_result.stdout

    def test_07_complete_pipeline_integration(self, tmp_path: Path) -> None:
        """Test complete pipeline: headers -> objects -> archives -> linking -> execution."""
        # Step 1: Create header files
        world_h = tmp_path / "world.h"
        world_h.write_text(
            """
#ifndef WORLD_H
#define WORLD_H

#include <string>

namespace world {
    std::string get_message();
    int get_value();
}

#endif // WORLD_H
"""
        )

        hello_h = tmp_path / "hello.h"
        hello_h.write_text(
            """
#ifndef HELLO_H
#define HELLO_H

#include <string>
#include "world.h"  // Include world.h in hello.h

namespace hello {
    std::string get_message();
    void print_world_info();
}

#endif // HELLO_H
"""
        )

        # Step 2: Generate PCH from world.h
        world_pch = tmp_path / "world.h.pch"
        pch_result = subprocess.run(
            [
                "clang-tool-chain-empp",
                "-x",
                "c++-header",
                str(world_h),
                "-o",
                str(world_pch),
            ],
            capture_output=True,
            text=True,
            timeout=300,
        )
        assert pch_result.returncode == 0, f"PCH generation failed: {pch_result.stderr}"
        assert world_pch.exists()

        # Step 3: Create implementation files
        world_cpp = tmp_path / "world.cpp"
        world_cpp.write_text(
            """
#include "world.h"

namespace world {
    std::string get_message() {
        return "World Library";
    }

    int get_value() {
        return 42;
    }
}
"""
        )

        hello_cpp = tmp_path / "hello.cpp"
        hello_cpp.write_text(
            """
#include "hello.h"
#include <iostream>

namespace hello {
    std::string get_message() {
        return "Hello Library";
    }

    void print_world_info() {
        std::cout << "World says: " << world::get_message() << std::endl;
        std::cout << "World value: " << world::get_value() << std::endl;
    }
}
"""
        )

        # Step 4: Compile to object files
        world_o = tmp_path / "world.o"
        hello_o = tmp_path / "hello.o"

        world_compile = subprocess.run(
            [
                "clang-tool-chain-empp",
                "-c",
                str(world_cpp),
                "-I",
                str(tmp_path),
                "-o",
                str(world_o),
            ],
            capture_output=True,
            text=True,
            timeout=300,
        )
        assert world_compile.returncode == 0, f"world.o compilation failed: {world_compile.stderr}"
        assert world_o.exists()

        hello_compile = subprocess.run(
            [
                "clang-tool-chain-empp",
                "-c",
                str(hello_cpp),
                "-I",
                str(tmp_path),
                "-include-pch",
                str(world_pch),
                "-o",
                str(hello_o),
            ],
            capture_output=True,
            text=True,
            timeout=300,
        )
        assert hello_compile.returncode == 0, f"hello.o compilation failed: {hello_compile.stderr}"
        assert hello_o.exists()

        # Step 5: Create thin archives (.a) for each
        libworld_a = tmp_path / "libworld.a"
        libhello_a = tmp_path / "libhello.a"

        world_ar = subprocess.run(
            ["clang-tool-chain-emar", "rcs", str(libworld_a), str(world_o)],
            capture_output=True,
            text=True,
            timeout=300,
        )
        assert world_ar.returncode == 0, f"libworld.a creation failed: {world_ar.stderr}"
        assert libworld_a.exists()

        hello_ar = subprocess.run(
            ["clang-tool-chain-emar", "rcs", str(libhello_a), str(hello_o)],
            capture_output=True,
            text=True,
            timeout=300,
        )
        assert hello_ar.returncode == 0, f"libhello.a creation failed: {hello_ar.stderr}"
        assert libhello_a.exists()

        # Step 6: Create main program
        main_cpp = tmp_path / "main.cpp"
        main_cpp.write_text(
            """
#include <iostream>
#include "hello.h"
#include "world.h"

int main() {
    std::cout << "=== Complete Pipeline Test ===" << std::endl;
    std::cout << hello::get_message() << std::endl;
    std::cout << world::get_message() << std::endl;
    hello::print_world_info();
    std::cout << "Pipeline test completed successfully!" << std::endl;
    return 0;
}
"""
        )

        # Step 7: Link everything together
        output_js = tmp_path / "program.js"
        link_result = subprocess.run(
            [
                "clang-tool-chain-empp",
                str(main_cpp),
                str(libhello_a),
                str(libworld_a),
                "-I",
                str(tmp_path),
                "-o",
                str(output_js),
            ],
            capture_output=True,
            text=True,
            timeout=300,
        )

        assert (
            link_result.returncode == 0
        ), f"Linking failed:\nstdout: {link_result.stdout}\nstderr: {link_result.stderr}"
        assert output_js.exists()
        assert (tmp_path / "program.wasm").exists()

        # Step 8: Execute and verify
        exec_result = subprocess.run(
            ["node", str(output_js)],
            capture_output=True,
            text=True,
            timeout=30,
            cwd=tmp_path,
        )

        assert (
            exec_result.returncode == 0
        ), f"Execution failed:\nstdout: {exec_result.stdout}\nstderr: {exec_result.stderr}"
        output = exec_result.stdout
        assert "Complete Pipeline Test" in output
        assert "Hello Library" in output
        assert "World Library" in output
        assert "World says: World Library" in output
        assert "World value: 42" in output
        assert "Pipeline test completed successfully!" in output


if __name__ == "__main__":
    # Allow running this test file directly
    sys.exit(pytest.main([__file__, "-v"]))
