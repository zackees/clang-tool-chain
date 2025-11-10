"""
Comprehensive Windows MSVC ABI compilation tests.

This test suite provides thorough testing of the MSVC variant commands,
including C/C++ compilation, linking, execution, and MSVC-specific features.
"""

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


@unittest.skipUnless(sys.platform == "win32", "MSVC tests are Windows-only")
class TestMSVCCompilation(unittest.TestCase):
    """Comprehensive test suite for MSVC ABI compilation on Windows."""

    @classmethod
    def setUpClass(cls) -> None:
        """Check if toolchain is accessible before running any tests."""
        try:
            result = subprocess.run(
                ["clang-tool-chain-cpp-msvc", "--version"],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=120,  # 2 minute timeout for download
            )
            if result.returncode != 0:
                raise unittest.SkipTest(f"Toolchain not accessible: {result.stderr}")

            # Check if we have MSVC SDK (needed for most tests)
            cls.has_msvc_sdk = cls._check_msvc_sdk()
            if not cls.has_msvc_sdk:
                print("\n" + "=" * 70)
                print("WARNING: Visual Studio SDK not detected!")
                print("Most MSVC tests will be skipped.")
                print("To run full MSVC tests, install Visual Studio or run in")
                print("a Developer Command Prompt.")
                print("=" * 70 + "\n")

        except (subprocess.TimeoutExpired, FileNotFoundError, Exception) as e:
            raise unittest.SkipTest(f"Toolchain not accessible: {e}")

    @staticmethod
    def _check_msvc_sdk() -> bool:
        """Check if MSVC SDK environment variables are present."""
        import os

        sdk_vars = [
            "WindowsSdkDir",
            "WindowsSDKDir",
            "UniversalCRTSdkDir",
            "VCToolsInstallDir",
            "VSINSTALLDIR",
            "WindowsSDKVersion",
        ]
        return any(os.getenv(var) for var in sdk_vars)

    def setUp(self) -> None:
        """Set up test environment with temporary directory."""
        self.temp_dir = tempfile.mkdtemp()
        self.temp_path = Path(self.temp_dir)

    def tearDown(self) -> None:
        """Clean up temporary directory."""
        import shutil

        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_01_msvc_variant_commands_exist(self) -> None:
        """Test that MSVC variant commands are available."""
        # Test C compiler
        result_c = subprocess.run(
            ["clang-tool-chain-c-msvc", "--version"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        self.assertEqual(
            result_c.returncode,
            0,
            f"clang-tool-chain-c-msvc should be available.\nstderr: {result_c.stderr}",
        )
        self.assertIn("clang", result_c.stdout.lower())

        # Test C++ compiler
        result_cpp = subprocess.run(
            ["clang-tool-chain-cpp-msvc", "--version"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        self.assertEqual(
            result_cpp.returncode,
            0,
            f"clang-tool-chain-cpp-msvc should be available.\nstderr: {result_cpp.stderr}",
        )
        self.assertIn("clang", result_cpp.stdout.lower())

    def test_02_msvc_target_injection(self) -> None:
        """Test that MSVC variants inject the correct target triple."""
        test_file = self.temp_path / "test.c"
        test_file.write_text("int main() { return 0; }\n")

        result = subprocess.run(
            ["clang-tool-chain-c-msvc", "-v", "-c", str(test_file)],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            cwd=str(self.temp_path),
        )

        output = (result.stdout or "") + (result.stderr or "")

        # Should contain MSVC target triple
        self.assertIn(
            "x86_64-pc-windows-msvc",
            output,
            f"MSVC target triple should appear in verbose output.\nFull output:\n{output}",
        )

        # Should NOT contain GNU target
        self.assertNotIn(
            "x86_64-w64-mingw32",
            output,
            f"GNU target should NOT appear when using MSVC variant.\nFull output:\n{output}",
        )

    def test_03_msvc_c_compilation_basic(self) -> None:
        """Test basic C compilation with MSVC variant."""
        if not self.has_msvc_sdk:
            self.skipTest("Visual Studio SDK not available")

        test_file = self.temp_path / "hello.c"
        test_code = """
#include <stdio.h>

int main() {
    printf("Hello from MSVC C compiler!\\n");
    return 0;
}
"""
        test_file.write_text(test_code)

        # Compile only (no linking)
        result = subprocess.run(
            ["clang-tool-chain-c-msvc", "-c", str(test_file), "-o", "hello.o"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            cwd=str(self.temp_path),
        )

        self.assertEqual(
            result.returncode,
            0,
            f"C compilation should succeed.\nstdout: {result.stdout}\nstderr: {result.stderr}",
        )

        obj_file = self.temp_path / "hello.o"
        self.assertTrue(obj_file.exists(), "Object file should be created")

    def test_04_msvc_cpp_compilation_basic(self) -> None:
        """Test basic C++ compilation with MSVC variant."""
        if not self.has_msvc_sdk:
            self.skipTest("Visual Studio SDK not available")

        test_file = self.temp_path / "hello.cpp"
        test_code = """
#include <iostream>

int main() {
    std::cout << "Hello from MSVC C++ compiler!" << std::endl;
    return 0;
}
"""
        test_file.write_text(test_code)

        # Compile only (no linking)
        result = subprocess.run(
            ["clang-tool-chain-cpp-msvc", "-c", str(test_file), "-o", "hello.o"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            cwd=str(self.temp_path),
        )

        self.assertEqual(
            result.returncode,
            0,
            f"C++ compilation should succeed.\nstdout: {result.stdout}\nstderr: {result.stderr}",
        )

        obj_file = self.temp_path / "hello.o"
        self.assertTrue(obj_file.exists(), "Object file should be created")

    def test_05_msvc_c_complete_build(self) -> None:
        """Test complete C compilation and linking with MSVC variant."""
        if not self.has_msvc_sdk:
            self.skipTest("Visual Studio SDK not available")

        test_file = self.temp_path / "program.c"
        test_code = """
#include <stdio.h>
#include <stdlib.h>

int add(int a, int b) {
    return a + b;
}

int main() {
    int result = add(42, 13);
    printf("Result: %d\\n", result);
    return 0;
}
"""
        test_file.write_text(test_code)
        exe_file = self.temp_path / "program.exe"

        # Compile and link in one step
        result = subprocess.run(
            ["clang-tool-chain-c-msvc", str(test_file), "-o", str(exe_file)],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            cwd=str(self.temp_path),
        )

        self.assertEqual(
            result.returncode,
            0,
            f"Compilation and linking should succeed.\nstdout: {result.stdout}\nstderr: {result.stderr}",
        )

        self.assertTrue(exe_file.exists(), "Executable should be created")

        # Run the executable
        run_result = subprocess.run(
            [str(exe_file)],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=5,
        )

        self.assertEqual(
            run_result.returncode,
            0,
            f"Program should run successfully.\nstderr: {run_result.stderr}",
        )
        self.assertIn(
            "Result: 55",
            run_result.stdout,
            f"Output should contain 'Result: 55'. Got: {run_result.stdout}",
        )

    def test_06_msvc_cpp_complete_build(self) -> None:
        """Test complete C++ compilation and linking with MSVC variant."""
        if not self.has_msvc_sdk:
            self.skipTest("Visual Studio SDK not available")

        test_file = self.temp_path / "program.cpp"
        test_code = """
#include <iostream>
#include <vector>
#include <string>

class Calculator {
public:
    int add(int a, int b) {
        return a + b;
    }
};

int main() {
    Calculator calc;
    std::vector<std::string> messages = {"Hello", "from", "MSVC", "C++"};

    for (const auto& msg : messages) {
        std::cout << msg << " ";
    }
    std::cout << std::endl;

    int result = calc.add(42, 13);
    std::cout << "Calculation: " << result << std::endl;

    return 0;
}
"""
        test_file.write_text(test_code)
        exe_file = self.temp_path / "program.exe"

        # Compile and link in one step
        result = subprocess.run(
            ["clang-tool-chain-cpp-msvc", str(test_file), "-o", str(exe_file)],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            cwd=str(self.temp_path),
        )

        self.assertEqual(
            result.returncode,
            0,
            f"Compilation and linking should succeed.\nstdout: {result.stdout}\nstderr: {result.stderr}",
        )

        self.assertTrue(exe_file.exists(), "Executable should be created")

        # Run the executable
        run_result = subprocess.run(
            [str(exe_file)],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=5,
        )

        self.assertEqual(
            run_result.returncode,
            0,
            f"Program should run successfully.\nstderr: {run_result.stderr}",
        )
        self.assertIn("Hello from MSVC C++", run_result.stdout)
        self.assertIn("Calculation: 55", run_result.stdout)

    def test_07_msvc_cpp_stl_features(self) -> None:
        """Test C++ standard library features with MSVC variant."""
        if not self.has_msvc_sdk:
            self.skipTest("Visual Studio SDK not available")

        test_file = self.temp_path / "stl_test.cpp"
        test_code = """
#include <iostream>
#include <vector>
#include <map>
#include <string>
#include <algorithm>
#include <memory>

int main() {
    // Test vector
    std::vector<int> numbers = {1, 2, 3, 4, 5};

    // Test map
    std::map<std::string, int> scores;
    scores["Alice"] = 100;
    scores["Bob"] = 95;

    // Test algorithm
    auto it = std::find(numbers.begin(), numbers.end(), 3);

    // Test smart pointers
    auto ptr = std::make_unique<int>(42);

    std::cout << "STL test passed!" << std::endl;
    std::cout << "Found: " << (it != numbers.end() ? "yes" : "no") << std::endl;
    std::cout << "Alice's score: " << scores["Alice"] << std::endl;
    std::cout << "Smart pointer value: " << *ptr << std::endl;

    return 0;
}
"""
        test_file.write_text(test_code)
        exe_file = self.temp_path / "stl_test.exe"

        # Compile with C++11 standard
        result = subprocess.run(
            ["clang-tool-chain-cpp-msvc", "-std=c++11", str(test_file), "-o", str(exe_file)],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            cwd=str(self.temp_path),
        )

        self.assertEqual(
            result.returncode,
            0,
            f"STL compilation should succeed.\nstdout: {result.stdout}\nstderr: {result.stderr}",
        )

        self.assertTrue(exe_file.exists(), "Executable should be created")

        # Run the executable
        run_result = subprocess.run(
            [str(exe_file)],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=5,
        )

        self.assertEqual(run_result.returncode, 0, f"STL test program should run.\nstderr: {run_result.stderr}")
        self.assertIn("STL test passed!", run_result.stdout)
        self.assertIn("Found: yes", run_result.stdout)
        self.assertIn("Alice's score: 100", run_result.stdout)
        self.assertIn("Smart pointer value: 42", run_result.stdout)

    def test_08_msvc_multi_file_compilation(self) -> None:
        """Test multi-file C++ compilation with MSVC variant."""
        if not self.has_msvc_sdk:
            self.skipTest("Visual Studio SDK not available")

        # Create header file
        header_file = self.temp_path / "math_ops.h"
        header_code = """
#ifndef MATH_OPS_H
#define MATH_OPS_H

int add(int a, int b);
int multiply(int a, int b);

#endif
"""
        header_file.write_text(header_code)

        # Create implementation file
        impl_file = self.temp_path / "math_ops.cpp"
        impl_code = """
#include "math_ops.h"

int add(int a, int b) {
    return a + b;
}

int multiply(int a, int b) {
    return a * b;
}
"""
        impl_file.write_text(impl_code)

        # Create main file
        main_file = self.temp_path / "main.cpp"
        main_code = """
#include <iostream>
#include "math_ops.h"

int main() {
    int sum = add(10, 20);
    int product = multiply(5, 6);

    std::cout << "Sum: " << sum << std::endl;
    std::cout << "Product: " << product << std::endl;

    return 0;
}
"""
        main_file.write_text(main_code)

        exe_file = self.temp_path / "multi_file.exe"

        # Compile all files together
        result = subprocess.run(
            [
                "clang-tool-chain-cpp-msvc",
                str(main_file),
                str(impl_file),
                "-o",
                str(exe_file),
            ],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            cwd=str(self.temp_path),
        )

        self.assertEqual(
            result.returncode,
            0,
            f"Multi-file compilation should succeed.\nstdout: {result.stdout}\nstderr: {result.stderr}",
        )

        self.assertTrue(exe_file.exists(), "Executable should be created")

        # Run the executable
        run_result = subprocess.run(
            [str(exe_file)],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=5,
        )

        self.assertEqual(run_result.returncode, 0, f"Program should run.\nstderr: {run_result.stderr}")
        self.assertIn("Sum: 30", run_result.stdout)
        self.assertIn("Product: 30", run_result.stdout)

    def test_09_msvc_windows_headers(self) -> None:
        """Test compilation with Windows-specific headers."""
        if not self.has_msvc_sdk:
            self.skipTest("Visual Studio SDK not available")

        test_file = self.temp_path / "windows_test.cpp"
        test_code = """
#include <windows.h>
#include <iostream>

int main() {
    // Get Windows version
    DWORD version = GetVersion();
    DWORD major = (DWORD)(LOBYTE(LOWORD(version)));
    DWORD minor = (DWORD)(HIBYTE(LOWORD(version)));

    std::cout << "Windows version: " << major << "." << minor << std::endl;
    std::cout << "Windows API accessible!" << std::endl;

    return 0;
}
"""
        test_file.write_text(test_code)
        exe_file = self.temp_path / "windows_test.exe"

        # Compile with Windows headers
        result = subprocess.run(
            ["clang-tool-chain-cpp-msvc", str(test_file), "-o", str(exe_file)],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            cwd=str(self.temp_path),
        )

        self.assertEqual(
            result.returncode,
            0,
            f"Windows API compilation should succeed.\nstdout: {result.stdout}\nstderr: {result.stderr}",
        )

        self.assertTrue(exe_file.exists(), "Executable should be created")

        # Run the executable
        run_result = subprocess.run(
            [str(exe_file)],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=5,
        )

        self.assertEqual(run_result.returncode, 0, f"Windows API program should run.\nstderr: {run_result.stderr}")
        self.assertIn("Windows API accessible!", run_result.stdout)

    def test_10_msvc_optimization_levels(self) -> None:
        """Test different optimization levels with MSVC variant."""
        if not self.has_msvc_sdk:
            self.skipTest("Visual Studio SDK not available")

        test_file = self.temp_path / "optimize.cpp"
        test_code = """
#include <iostream>

int fibonacci(int n) {
    if (n <= 1) return n;
    return fibonacci(n-1) + fibonacci(n-2);
}

int main() {
    int result = fibonacci(10);
    std::cout << "Fibonacci(10) = " << result << std::endl;
    return 0;
}
"""
        test_file.write_text(test_code)

        # Test different optimization levels
        opt_levels = ["-O0", "-O1", "-O2", "-O3"]

        for opt in opt_levels:
            exe_file = self.temp_path / f"optimize{opt}.exe"

            result = subprocess.run(
                ["clang-tool-chain-cpp-msvc", opt, str(test_file), "-o", str(exe_file)],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                cwd=str(self.temp_path),
            )

            self.assertEqual(
                result.returncode,
                0,
                f"Compilation with {opt} should succeed.\nstdout: {result.stdout}\nstderr: {result.stderr}",
            )

            self.assertTrue(exe_file.exists(), f"Executable with {opt} should be created")

            # Run to verify correctness
            run_result = subprocess.run(
                [str(exe_file)],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=5,
            )

            self.assertEqual(run_result.returncode, 0, f"Program with {opt} should run.\nstderr: {run_result.stderr}")
            self.assertIn("Fibonacci(10) = 55", run_result.stdout)

    def test_11_msvc_cpp_standards(self) -> None:
        """Test different C++ standards with MSVC variant."""
        if not self.has_msvc_sdk:
            self.skipTest("Visual Studio SDK not available")

        # C++11 features
        test_file = self.temp_path / "cpp11.cpp"
        test_code = """
#include <iostream>
#include <vector>

int main() {
    auto x = 42;
    std::vector<int> v = {1, 2, 3};
    for (auto val : v) {
        std::cout << val << " ";
    }
    std::cout << std::endl;
    return 0;
}
"""
        test_file.write_text(test_code)
        exe_file = self.temp_path / "cpp11.exe"

        result = subprocess.run(
            ["clang-tool-chain-cpp-msvc", "-std=c++11", str(test_file), "-o", str(exe_file)],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            cwd=str(self.temp_path),
        )

        self.assertEqual(
            result.returncode,
            0,
            f"C++11 compilation should succeed.\nstdout: {result.stdout}\nstderr: {result.stderr}",
        )

        run_result = subprocess.run([str(exe_file)], capture_output=True, text=True, timeout=5)
        self.assertEqual(run_result.returncode, 0)
        self.assertIn("1 2 3", run_result.stdout)

    def test_12_msvc_respects_user_target(self) -> None:
        """Test that MSVC variants respect user-provided --target flag."""
        test_file = self.temp_path / "test.c"
        test_file.write_text("int main() { return 0; }\n")

        # Use MSVC variant but provide GNU target explicitly
        result = subprocess.run(
            ["clang-tool-chain-c-msvc", "-v", "--target=x86_64-w64-mingw32", "-c", str(test_file)],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            cwd=str(self.temp_path),
        )

        output = (result.stdout or "") + (result.stderr or "")

        # Should see user's GNU target, not MSVC target
        self.assertIn(
            "x86_64-w64-mingw32",
            output,
            f"User's explicit target should be used.\nFull output:\n{output}",
        )

    def test_13_msvc_error_messages(self) -> None:
        """Test that compilation errors are properly reported."""
        if not self.has_msvc_sdk:
            self.skipTest("Visual Studio SDK not available")

        test_file = self.temp_path / "error.cpp"
        test_code = """
#include <iostream>

int main() {
    // Intentional error: missing semicolon
    std::cout << "Hello"
    return 0;
}
"""
        test_file.write_text(test_code)

        result = subprocess.run(
            ["clang-tool-chain-cpp-msvc", "-c", str(test_file)],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            cwd=str(self.temp_path),
        )

        # Should fail with non-zero exit code
        self.assertNotEqual(result.returncode, 0, "Compilation should fail for invalid code")

        # Error message should be informative
        error_output = result.stderr or result.stdout
        self.assertTrue(len(error_output) > 0, "Should provide error message")
        self.assertIn("error", error_output.lower(), "Should mention 'error'")

    def test_14_msvc_debug_symbols(self) -> None:
        """Test compilation with debug symbols."""
        if not self.has_msvc_sdk:
            self.skipTest("Visual Studio SDK not available")

        test_file = self.temp_path / "debug.cpp"
        test_code = """
#include <iostream>

void debug_function() {
    std::cout << "Debug test" << std::endl;
}

int main() {
    debug_function();
    return 0;
}
"""
        test_file.write_text(test_code)
        exe_file = self.temp_path / "debug.exe"

        # Compile with debug symbols
        result = subprocess.run(
            ["clang-tool-chain-cpp-msvc", "-g", str(test_file), "-o", str(exe_file)],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            cwd=str(self.temp_path),
        )

        self.assertEqual(
            result.returncode,
            0,
            f"Debug compilation should succeed.\nstdout: {result.stdout}\nstderr: {result.stderr}",
        )

        self.assertTrue(exe_file.exists(), "Debug executable should be created")

        # Run the executable
        run_result = subprocess.run([str(exe_file)], capture_output=True, text=True, timeout=5)
        self.assertEqual(run_result.returncode, 0)
        self.assertIn("Debug test", run_result.stdout)

    def test_15_msvc_warning_flags(self) -> None:
        """Test that warning flags work with MSVC variant."""
        if not self.has_msvc_sdk:
            self.skipTest("Visual Studio SDK not available")

        test_file = self.temp_path / "warnings.cpp"
        test_code = """
#include <iostream>

int main() {
    int unused_variable = 42;  // Should trigger warning with -Wunused-variable
    std::cout << "Hello" << std::endl;
    return 0;
}
"""
        test_file.write_text(test_code)

        # Compile with warnings enabled
        result = subprocess.run(
            ["clang-tool-chain-cpp-msvc", "-Wunused-variable", "-c", str(test_file)],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            cwd=str(self.temp_path),
        )

        # Should succeed but produce warning
        self.assertEqual(result.returncode, 0, "Compilation should succeed despite warnings")

        # Should mention the unused variable
        output = result.stderr or result.stdout
        self.assertIn("unused", output.lower(), "Should warn about unused variable")


if __name__ == "__main__":
    unittest.main()
