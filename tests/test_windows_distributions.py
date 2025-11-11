"""
Test Windows GNU and MSVC distributions as separate test suites.

These tests verify that both Windows ABI variants (GNU and MSVC) work correctly
and are treated as separate distribution targets, similar to how Linux x86_64
and arm64 are tested separately.
"""

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import pytest


@pytest.mark.serial
@unittest.skipUnless(sys.platform == "win32", "Windows-only tests")
class TestWindowsGNUDistribution(unittest.TestCase):
    """Test suite for Windows GNU ABI distribution (default)."""

    def setUp(self) -> None:
        """Set up test environment with temporary directory."""
        self.temp_dir = tempfile.mkdtemp()
        self.temp_path = Path(self.temp_dir)

        # Check if toolchain is accessible
        try:
            result = subprocess.run(
                ["clang-tool-chain-cpp", "--version"],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=120,
            )
            if result.returncode != 0:
                self.skipTest(f"Toolchain not accessible: {result.stderr}")
        except (subprocess.TimeoutExpired, FileNotFoundError, Exception) as e:
            self.skipTest(f"Toolchain not accessible: {e}")

    def tearDown(self) -> None:
        """Clean up temporary directory."""
        import shutil

        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_gnu_c_compiler_available(self) -> None:
        """Test that GNU C compiler is available."""
        result = subprocess.run(
            ["clang-tool-chain-c", "--version"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )

        self.assertEqual(result.returncode, 0, "clang-tool-chain-c should be available")
        self.assertIn("clang", result.stdout.lower(), "Should report clang version")

    def test_gnu_cpp_compiler_available(self) -> None:
        """Test that GNU C++ compiler is available."""
        result = subprocess.run(
            ["clang-tool-chain-cpp", "--version"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )

        self.assertEqual(result.returncode, 0, "clang-tool-chain-cpp should be available")
        self.assertIn("clang", result.stdout.lower(), "Should report clang version")

    def test_gnu_uses_mingw_target(self) -> None:
        """Test that GNU distribution uses MinGW target by default."""
        test_file = self.temp_path / "test.c"
        test_file.write_text("int main() { return 0; }\n")

        try:
            result = subprocess.run(
                ["clang-tool-chain-c", "-v", "-c", str(test_file)],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                cwd=str(self.temp_path),
            )

            output = (result.stderr + result.stdout).lower()
            has_gnu_target = "w64-mingw32" in output or "windows-gnu" in output

            self.assertTrue(
                has_gnu_target,
                f"GNU distribution should use MinGW target by default.\nOutput:\n{result.stderr}\n{result.stdout}",
            )
        finally:
            for f in [test_file, self.temp_path / "test.o"]:
                if f.exists():
                    f.unlink()

    def test_gnu_c_compilation(self) -> None:
        """Test C compilation with GNU distribution."""
        test_file = self.temp_path / "test.c"
        test_code = """#include <stdio.h>
int main() {
    printf("Hello GNU C\\n");
    return 0;
}
"""
        test_file.write_text(test_code)
        exe_file = self.temp_path / "test.exe"

        try:
            result = subprocess.run(
                ["clang-tool-chain-c", str(test_file), "-o", str(exe_file)],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                cwd=str(self.temp_path),
            )

            self.assertEqual(
                result.returncode, 0, f"Compilation should succeed.\nstderr: {result.stderr}\nstdout: {result.stdout}"
            )
            self.assertTrue(exe_file.exists(), "Executable should be created")

            # Run the executable
            run_result = subprocess.run([str(exe_file)], capture_output=True, text=True, timeout=5)
            self.assertEqual(run_result.returncode, 0, "Executable should run successfully")
            self.assertIn("Hello GNU C", run_result.stdout, "Output should contain expected text")
        finally:
            for f in [test_file, exe_file]:
                if f.exists():
                    f.unlink()

    def test_gnu_cpp_compilation(self) -> None:
        """Test C++ compilation with GNU distribution."""
        test_file = self.temp_path / "test.cpp"
        test_code = """#include <iostream>
#include <vector>

int main() {
    std::vector<int> v = {1, 2, 3};
    std::cout << "Hello GNU C++" << std::endl;
    return 0;
}
"""
        test_file.write_text(test_code)
        exe_file = self.temp_path / "test.exe"

        try:
            result = subprocess.run(
                ["clang-tool-chain-cpp", "-std=c++11", str(test_file), "-o", str(exe_file)],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                cwd=str(self.temp_path),
            )

            self.assertEqual(
                result.returncode, 0, f"Compilation should succeed.\nstderr: {result.stderr}\nstdout: {result.stdout}"
            )
            self.assertTrue(exe_file.exists(), "Executable should be created")

            # Run the executable
            run_result = subprocess.run([str(exe_file)], capture_output=True, text=True, timeout=5)
            self.assertEqual(run_result.returncode, 0, "Executable should run successfully")
            self.assertIn("Hello GNU C++", run_result.stdout, "Output should contain expected text")
        finally:
            for f in [test_file, exe_file]:
                if f.exists():
                    f.unlink()

    def test_gnu_strict_cpp11_mode(self) -> None:
        """Test that GNU distribution supports strict C++11 mode."""
        test_file = self.temp_path / "test.cpp"
        test_code = """#include <type_traits>
#include <vector>

int main() {
    std::vector<int> v = {1, 2, 3};
    return 0;
}
"""
        test_file.write_text(test_code)

        try:
            result = subprocess.run(
                ["clang-tool-chain-cpp", "-std=c++11", "-Werror=c++14-extensions", "-c", str(test_file)],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                cwd=str(self.temp_path),
            )

            self.assertEqual(
                result.returncode,
                0,
                f"Strict C++11 mode should work with GNU headers.\nstderr: {result.stderr}\nstdout: {result.stdout}",
            )
        finally:
            for f in [test_file, self.temp_path / "test.o"]:
                if f.exists():
                    f.unlink()

    def test_gnu_sccache_variant(self) -> None:
        """Test that sccache variants work with GNU distribution."""
        test_file = self.temp_path / "test.c"
        test_file.write_text("int main() { return 0; }\n")

        try:
            # Test compilation with sccache-c (which uses GNU by default on Windows)
            result = subprocess.run(
                ["clang-tool-chain-sccache-c", "-c", str(test_file)],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                cwd=str(self.temp_path),
            )

            # sccache might not be installed, so we accept either success or sccache-not-found error
            if result.returncode != 0:
                output = result.stderr.lower() + result.stdout.lower()
                if "sccache" in output:
                    self.skipTest("sccache not installed")
                else:
                    self.fail(f"Unexpected error: {result.stderr}")
        finally:
            for f in [test_file, self.temp_path / "test.o"]:
                if f.exists():
                    f.unlink()


@pytest.mark.serial
@unittest.skipUnless(sys.platform == "win32", "Windows-only tests")
class TestWindowsMSVCDistribution(unittest.TestCase):
    """Test suite for Windows MSVC ABI distribution (opt-in)."""

    def setUp(self) -> None:
        """Set up test environment with temporary directory."""
        self.temp_dir = tempfile.mkdtemp()
        self.temp_path = Path(self.temp_dir)

        # Check if toolchain is accessible
        try:
            result = subprocess.run(
                ["clang-tool-chain-cpp-msvc", "--version"],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=120,
            )
            if result.returncode != 0:
                self.skipTest(f"Toolchain not accessible: {result.stderr}")
        except (subprocess.TimeoutExpired, FileNotFoundError, Exception) as e:
            self.skipTest(f"Toolchain not accessible: {e}")

    def tearDown(self) -> None:
        """Clean up temporary directory."""
        import shutil

        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_msvc_c_compiler_available(self) -> None:
        """Test that MSVC C compiler is available."""
        result = subprocess.run(
            ["clang-tool-chain-c-msvc", "--version"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )

        self.assertEqual(result.returncode, 0, "clang-tool-chain-c-msvc should be available")
        self.assertIn("clang", result.stdout.lower(), "Should report clang version")

    def test_msvc_cpp_compiler_available(self) -> None:
        """Test that MSVC C++ compiler is available."""
        result = subprocess.run(
            ["clang-tool-chain-cpp-msvc", "--version"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )

        self.assertEqual(result.returncode, 0, "clang-tool-chain-cpp-msvc should be available")
        self.assertIn("clang", result.stdout.lower(), "Should report clang version")

    def test_msvc_uses_msvc_target(self) -> None:
        """Test that MSVC distribution uses MSVC target."""
        test_file = self.temp_path / "test.c"
        test_file.write_text("int main() { return 0; }\n")

        try:
            result = subprocess.run(
                ["clang-tool-chain-c-msvc", "-v", "-c", str(test_file)],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                cwd=str(self.temp_path),
            )

            output = (result.stderr + result.stdout).lower()
            has_msvc_target = "msvc" in output

            self.assertTrue(
                has_msvc_target, f"MSVC distribution should use MSVC target.\nOutput:\n{result.stderr}\n{result.stdout}"
            )

            # Should not have GNU target
            self.assertNotIn(
                "w64-mingw32",
                output,
                f"MSVC distribution should not use MinGW target.\nOutput:\n{result.stderr}\n{result.stdout}",
            )
        finally:
            for f in [test_file, self.temp_path / "test.o"]:
                if f.exists():
                    f.unlink()

    def test_msvc_c_compilation(self) -> None:
        """Test C compilation with MSVC distribution."""
        test_file = self.temp_path / "test.c"
        test_code = """#include <stdio.h>
int main() {
    printf("Hello MSVC C\\n");
    return 0;
}
"""
        test_file.write_text(test_code)
        exe_file = self.temp_path / "test.exe"

        try:
            result = subprocess.run(
                ["clang-tool-chain-c-msvc", str(test_file), "-o", str(exe_file)],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                cwd=str(self.temp_path),
            )

            output = (result.stdout or "") + (result.stderr or "")
            # Skip if Windows SDK not available
            if result.returncode != 0 and any(
                keyword in output.lower() for keyword in ["windows sdk", "visual studio", "vcruntime.h", "corecrt.h"]
            ):
                self.skipTest("Visual Studio SDK not available for MSVC testing")

            self.assertEqual(
                result.returncode, 0, f"Compilation should succeed.\nstderr: {result.stderr}\nstdout: {result.stdout}"
            )
            self.assertTrue(exe_file.exists(), "Executable should be created")

            # Run the executable
            run_result = subprocess.run([str(exe_file)], capture_output=True, text=True, timeout=5)
            self.assertEqual(run_result.returncode, 0, "Executable should run successfully")
            self.assertIn("Hello MSVC C", run_result.stdout, "Output should contain expected text")
        finally:
            for f in [test_file, exe_file]:
                if f.exists():
                    f.unlink()

    def test_msvc_cpp_compilation(self) -> None:
        """Test C++ compilation with MSVC distribution."""
        test_file = self.temp_path / "test.cpp"
        test_code = """#include <iostream>
#include <vector>

int main() {
    std::vector<int> v = {1, 2, 3};
    std::cout << "Hello MSVC C++" << std::endl;
    return 0;
}
"""
        test_file.write_text(test_code)
        exe_file = self.temp_path / "test.exe"

        try:
            result = subprocess.run(
                ["clang-tool-chain-cpp-msvc", str(test_file), "-o", str(exe_file)],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                cwd=str(self.temp_path),
            )

            output = (result.stdout or "") + (result.stderr or "")
            # Skip if Windows SDK not available
            if result.returncode != 0 and any(
                keyword in output.lower()
                for keyword in ["windows sdk", "visual studio", "vcruntime.h", "corecrt.h", "libcmt", "msvcrt"]
            ):
                self.skipTest("Visual Studio SDK not available for MSVC testing")

            self.assertEqual(
                result.returncode, 0, f"Compilation should succeed.\nstderr: {result.stderr}\nstdout: {result.stdout}"
            )
            self.assertTrue(exe_file.exists(), "Executable should be created")

            # Run the executable
            run_result = subprocess.run([str(exe_file)], capture_output=True, text=True, timeout=5)
            self.assertEqual(run_result.returncode, 0, "Executable should run successfully")
            self.assertIn("Hello MSVC C++", run_result.stdout, "Output should contain expected text")
        finally:
            for f in [test_file, exe_file]:
                if f.exists():
                    f.unlink()

    def test_msvc_abi_name_mangling(self) -> None:
        """Test that MSVC distribution uses MSVC name mangling."""
        test_file = self.temp_path / "test.cpp"
        test_code = """
class MyClass {
public:
    void myMethod(int x, double y);
};

void MyClass::myMethod(int x, double y) {
    // Implementation
}

extern "C" int exported_function() {
    return 42;
}
"""
        test_file.write_text(test_code)

        try:
            result = subprocess.run(
                ["clang-tool-chain-cpp-msvc", "-c", str(test_file), "-o", str(self.temp_path / "test.o")],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                cwd=str(self.temp_path),
            )

            output = (result.stdout or "") + (result.stderr or "")
            # Skip if Windows SDK not available
            if result.returncode != 0 and any(
                keyword in output.lower() for keyword in ["windows sdk", "visual studio", "vcruntime.h", "corecrt.h"]
            ):
                self.skipTest("Visual Studio SDK not available for MSVC testing")

            self.assertEqual(result.returncode, 0, "Compilation should succeed")

            # Check symbols
            nm_result = subprocess.run(
                ["clang-tool-chain-nm", str(self.temp_path / "test.o")],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
            )

            self.assertEqual(nm_result.returncode, 0, "llvm-nm should work on MSVC object")

            # MSVC uses ?name@ format for name mangling
            # The exact format is complex, but it should NOT be GNU-style _ZN format
            symbols = nm_result.stdout

            # Check that it doesn't use GNU mangling
            self.assertNotIn("_ZN", symbols, "MSVC object should not use GNU-style name mangling (_ZN prefix)")

            # extern "C" function should be present without mangling
            self.assertIn("exported_function", symbols, "extern C function should be present")
        finally:
            for f in [test_file, self.temp_path / "test.o"]:
                if f.exists():
                    f.unlink()

    def test_msvc_sccache_variant(self) -> None:
        """Test that sccache MSVC variants work."""
        test_file = self.temp_path / "test.c"
        test_file.write_text("int main() { return 0; }\n")

        try:
            # Test compilation with sccache-c-msvc
            result = subprocess.run(
                ["clang-tool-chain-sccache-c-msvc", "-c", str(test_file)],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                cwd=str(self.temp_path),
            )

            # sccache might not be installed, or SDK might not be available
            if result.returncode != 0:
                output = result.stderr.lower() + result.stdout.lower()
                if "sccache" in output:
                    self.skipTest("sccache not installed")
                elif any(keyword in output for keyword in ["windows sdk", "visual studio", "vcruntime", "corecrt"]):
                    self.skipTest("Visual Studio SDK not available")
                else:
                    self.fail(f"Unexpected error: {result.stderr}")
        finally:
            for f in [test_file, self.temp_path / "test.o"]:
                if f.exists():
                    f.unlink()


@pytest.mark.serial
@unittest.skipUnless(sys.platform == "win32", "Windows-only tests")
class TestWindowsDistributionSeparation(unittest.TestCase):
    """Test that GNU and MSVC distributions are properly separated."""

    def test_gnu_and_msvc_produce_different_binaries(self) -> None:
        """Test that GNU and MSVC distributions produce different object files."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)

            # Create a test C++ file
            test_file = temp_path / "test.cpp"
            test_code = """
class MyClass {
public:
    void myMethod(int x);
};

void MyClass::myMethod(int x) {
    // Implementation
}
"""
            test_file.write_text(test_code)

            # Compile with GNU
            gnu_obj = temp_path / "test_gnu.o"
            result_gnu = subprocess.run(
                ["clang-tool-chain-cpp", "-c", str(test_file), "-o", str(gnu_obj)],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
            )
            self.assertEqual(result_gnu.returncode, 0, "GNU compilation should succeed")

            # Compile with MSVC
            msvc_obj = temp_path / "test_msvc.o"
            result_msvc = subprocess.run(
                ["clang-tool-chain-cpp-msvc", "-c", str(test_file), "-o", str(msvc_obj)],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
            )

            # Skip if MSVC SDK not available
            if result_msvc.returncode != 0:
                output = result_msvc.stdout + result_msvc.stderr
                if any(
                    keyword in output.lower() for keyword in ["windows sdk", "visual studio", "vcruntime", "corecrt"]
                ):
                    self.skipTest("Visual Studio SDK not available")

            self.assertEqual(result_msvc.returncode, 0, "MSVC compilation should succeed")

            # The object files should be different
            gnu_content = gnu_obj.read_bytes()
            msvc_content = msvc_obj.read_bytes()

            self.assertNotEqual(
                gnu_content,
                msvc_content,
                "GNU and MSVC should produce different object files (different ABIs, name mangling, etc.)",
            )

    def test_default_uses_gnu_not_msvc(self) -> None:
        """Test that default commands use GNU, not MSVC."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            test_file = temp_path / "test.c"
            test_file.write_text("int main() { return 0; }\n")

            # Use default clang-tool-chain-c (should be GNU)
            result = subprocess.run(
                ["clang-tool-chain-c", "-v", "-c", str(test_file)],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
            )

            output = (result.stderr + result.stdout).lower()

            # Should see GNU target being used (--target flag or triple in cc1 invocation)
            self.assertIn("w64-mingw32", output, "Default should use GNU target")

            # Should see the actual target triple x86_64-w64-windows-gnu in the cc1 invocation
            # (not just the "default target" which is what clang was compiled for)
            self.assertIn("x86_64-w64-windows-gnu", output, "Should use GNU ABI (windows-gnu triple)")


if __name__ == "__main__":
    unittest.main()
