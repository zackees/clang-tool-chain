"""
Individual diagnostic test implementations for clang-tool-chain.

Each test function returns 0 on success, non-zero on failure.
"""

import subprocess
import tempfile
from pathlib import Path

from clang_tool_chain import wrapper


def _test_platform_detection() -> int:
    """Test 1: Platform Detection."""
    try:
        platform_name, arch = wrapper.get_platform_info()
        print(f"      Platform: {platform_name}/{arch}")
        return 0
    except Exception as e:
        print(f"      Error: {e}")
        return 1


def _test_toolchain_installation() -> int:
    """Test 2: Toolchain Download/Installation."""
    try:
        bin_dir = wrapper.get_platform_binary_dir()
        if bin_dir.exists():
            print(f"      Binary directory: {bin_dir}")
            return 0
        else:
            print(f"      Binary directory does not exist: {bin_dir}")
            return 1
    except Exception as e:
        print(f"      Error: {e}")
        return 1


def _test_clang_binary() -> int:
    """Test 3: Finding clang binary."""
    try:
        clang_path = wrapper.find_tool_binary("clang")
        print(f"      Found: {clang_path}")
        if not clang_path.exists():
            print(f"      Binary does not exist: {clang_path}")
            return 1
        # Store for use in later tests
        _test_clang_binary.clang_path = clang_path  # type: ignore
        return 0
    except Exception as e:
        print(f"      Error: {e}")
        return 1


def _test_clang_cpp_binary() -> int:
    """Test 4: Finding clang++ binary."""
    try:
        clang_cpp_path = wrapper.find_tool_binary("clang++")
        print(f"      Found: {clang_cpp_path}")
        if not clang_cpp_path.exists():
            print(f"      Binary does not exist: {clang_cpp_path}")
            return 1
        # Store for use in later tests
        _test_clang_cpp_binary.clang_cpp_path = clang_cpp_path  # type: ignore
        return 0
    except Exception as e:
        print(f"      Error: {e}")
        return 1


def _test_clang_version() -> int:
    """Test 5: Version check for clang."""
    try:
        # Get clang path from previous test
        clang_path = getattr(_test_clang_binary, "clang_path", None)
        if clang_path is None:
            clang_path = wrapper.find_tool_binary("clang")

        result = subprocess.run([str(clang_path), "--version"], capture_output=True, text=True, timeout=10)
        if result.returncode == 0:
            version_line = result.stdout.split("\n")[0]
            print(f"      {version_line}")
            return 0
        else:
            print(f"      clang --version returned {result.returncode}")
            print(f"      stderr: {result.stderr}")
            return 1
    except Exception as e:
        print(f"      Error: {e}")
        return 1


def _test_c_compilation() -> int:
    """Test 6: Simple C compilation test."""
    try:
        # Get platform info and clang path
        platform_name, _ = wrapper.get_platform_info()
        clang_path = getattr(_test_clang_binary, "clang_path", None)
        if clang_path is None:
            clang_path = wrapper.find_tool_binary("clang")

        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)
            test_c = tmpdir_path / "test.c"
            test_out = tmpdir_path / "test"
            if platform_name == "win":
                test_out = test_out.with_suffix(".exe")

            # Write simple C program
            test_c.write_text(
                """
#include <stdio.h>
int main() {
    printf("Hello from clang-tool-chain!\\n");
    return 0;
}
"""
            )

            # Compile
            result = subprocess.run(
                [str(clang_path), str(test_c), "-o", str(test_out)], capture_output=True, text=True, timeout=30
            )
            if result.returncode != 0:
                print("      Compilation failed")
                print(f"      stdout: {result.stdout}")
                print(f"      stderr: {result.stderr}")
                return 1

            # Verify output file was created
            if not test_out.exists():
                print(f"      Output binary not created: {test_out}")
                return 1

            print(f"      Compiled: {test_out}")
            return 0
    except Exception as e:
        print(f"      Error: {e}")
        return 1


def _test_cpp_compilation() -> int:
    """Test 7: Simple C++ compilation test."""
    try:
        # Get platform info and clang++ path
        platform_name, _ = wrapper.get_platform_info()
        clang_cpp_path = getattr(_test_clang_cpp_binary, "clang_cpp_path", None)
        if clang_cpp_path is None:
            clang_cpp_path = wrapper.find_tool_binary("clang++")

        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)
            test_cpp = tmpdir_path / "test.cpp"
            test_out = tmpdir_path / "test"
            if platform_name == "win":
                test_out = test_out.with_suffix(".exe")

            # Write simple C++ program
            test_cpp.write_text(
                """
#include <iostream>
int main() {
    std::cout << "Hello from clang-tool-chain C++!" << std::endl;
    return 0;
}
"""
            )

            # Compile
            result = subprocess.run(
                [str(clang_cpp_path), str(test_cpp), "-o", str(test_out)], capture_output=True, text=True, timeout=30
            )
            if result.returncode != 0:
                print("      Compilation failed")
                print(f"      stdout: {result.stdout}")
                print(f"      stderr: {result.stderr}")
                return 1

            # Verify output file was created
            if not test_out.exists():
                print(f"      Output binary not created: {test_out}")
                return 1

            print(f"      Compiled: {test_out}")
            return 0
    except Exception as e:
        print(f"      Error: {e}")
        return 1
