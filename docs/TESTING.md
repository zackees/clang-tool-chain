# Testing Guide

This document describes the testing infrastructure and how to run tests for the clang-tool-chain package.

## Quick Diagnostic Test

```bash
# Quick diagnostic test of the toolchain installation
clang-tool-chain-test           # Runs 7 diagnostic tests
# Or via main CLI:
clang-tool-chain test          # Same as above
```

**Diagnostic Test Suite (`clang-tool-chain-test`):**
The test command runs 7 diagnostic tests to verify your toolchain installation:
1. Platform detection
2. Toolchain installation verification
3. clang binary resolution
4. clang++ binary resolution
5. clang version check
6. C compilation test
7. C++ compilation test

This command is especially useful for debugging installation issues in GitHub Actions or other CI/CD environments.

## Running Full Test Suite

```bash
# Run all tests with coverage (parallel execution)
./test

# Or manually with pytest:
uv run pytest                    # Run with coverage reporting
uv run pytest -n auto            # Run in parallel
uv run pytest tests/test_cli.py  # Run specific test file
uv run pytest -m "not slow"      # Skip slow tests

# Run single test
uv run pytest tests/test_cli.py::MainTester::test_imports -v
```

## Test Organization

### Core Tests

- `test_cli.py` - CLI command tests
- `test_downloader.py` - Download/install tests
- `test_build_tools.py` - Build tool tests
- `test_integration.py` - End-to-end tests
- `test_manifest.py` - Manifest parsing tests

### Platform-Specific Tests

- `test_gnu_abi.py` - Windows GNU ABI tests (TASK.md scenarios)
- `test_msvc_compile.py` - Windows MSVC comprehensive tests
- `test_emscripten.py` - Emscripten/WebAssembly tests
- `test_nodejs_downloader.py` - Node.js bundling infrastructure tests

## Windows-Specific Testing

### Windows GNU ABI Tests

```bash
# Test Windows GNU ABI support (Windows only)
uv run pytest tests/test_gnu_abi.py -v

# Run all Windows-specific tests
uv run pytest -k "windows or gnu or msvc" -v
```

**Windows GNU ABI Test Coverage:**
- `test_gnu_abi.py` - Complete TASK.md scenarios (10 test cases)
  - Basic C++11 standard library headers with GNU target
  - C++11 code with MSVC headers (should fail)
  - Complete compilation and linking
  - Target triple verification
  - Default GNU ABI behavior on Windows
  - Explicit target override
  - MSVC variant commands
- `test_cli.py` - Windows GNU default detection
- `test_downloader.py` - MinGW sysroot download infrastructure (8 test cases)

### Windows MSVC ABI Tests

```bash
# Run MSVC ABI tests (requires Windows SDK)
uv run pytest tests/test_msvc_compile.py -v
```

**Windows MSVC ABI Testing:**

The `test_msvc_compile.py` test suite provides comprehensive testing of the Windows MSVC ABI support:

**Test Coverage (15 tests):**
1. MSVC variant command availability
2. MSVC target triple injection verification
3. Basic C compilation
4. Basic C++ compilation
5. Complete C build (compile + link + execute)
6. Complete C++ build (compile + link + execute)
7. C++ STL features (vector, map, algorithms, smart pointers)
8. Multi-file compilation
9. Windows-specific headers (<windows.h>)
10. Optimization levels (-O0, -O1, -O2, -O3)
11. C++ standard versions (-std=c++11, -std=c++14, etc.)
12. User target override behavior
13. Error message reporting
14. Debug symbols (-g)
15. Warning flags (-W*)

**Requirements:**
- Windows platform (tests are skipped on other platforms)
- Visual Studio or Windows SDK installed (most tests require this)
- Tests gracefully skip if SDK not detected

**Running MSVC tests locally:**
```bash
# Requires Visual Studio Developer Command Prompt or vcvarsall.bat
# Option 1: Use Developer Command Prompt
uv run pytest tests/test_msvc_compile.py -v

# Option 2: Set up MSVC environment first
call "C:\Program Files\Microsoft Visual Studio\2022\Community\VC\Auxiliary\Build\vcvarsall.bat" x64
uv run pytest tests/test_msvc_compile.py -v
```

**GitHub Actions:**
The `.github/workflows/test-win-msvc.yml` workflow runs comprehensive MSVC tests on every push/PR:
- Uses `ilammy/msvc-dev-cmd@v1` to set up MSVC environment
- Tests all MSVC variant commands
- Verifies target triple injection
- Tests Windows API compilation
- Runs full test suite with Visual Studio SDK
- Tests multi-file projects and optimization levels

## Emscripten and WebAssembly Testing

```bash
# Run Emscripten tests (requires Node.js)
uv run pytest tests/test_emscripten.py -v

# Test classes:
# - TestEmscripten: Compilation and execution tests
# - TestEmscriptenDownloader: Infrastructure tests

# Test Node.js bundling infrastructure
uv run pytest tests/test_nodejs_downloader.py -v

# Test Emscripten with bundled Node.js
uv run pytest tests/test_emscripten.py -v
```

## Test Coverage Requirements

- Coverage reports are generated automatically with pytest
- Reports in: terminal, HTML (htmlcov/), and XML formats
- Source coverage tracked for `src/` directory only

### Coverage Configuration

The test suite uses pytest-cov for coverage reporting:

```bash
# View coverage report in terminal
uv run pytest

# Generate HTML coverage report
uv run pytest --cov-report=html
# Open htmlcov/index.html in browser

# Generate XML coverage report (for CI)
uv run pytest --cov-report=xml
```

## Test Isolation

Tests are designed to be independent and can run in any order:

- Each test creates temporary directories for compilation
- Cleanup happens automatically via pytest fixtures
- Downloads are mocked in unit tests to avoid network dependencies
- Integration tests use real downloads but cache them

## Continuous Integration

### GitHub Actions Workflows

- `.github/workflows/test.yml` - Cross-platform test suite (Linux, macOS, Windows)
- `.github/workflows/test-win-msvc.yml` - Windows MSVC-specific tests
- `.github/workflows/lint.yml` - Code quality checks

All workflows run on:
- Every push to main branch
- Every pull request
- Manual workflow dispatch

## Writing New Tests

When adding new functionality, ensure you:

1. Add unit tests in the appropriate test file
2. Add integration tests if the feature interacts with external systems
3. Update this document with new test categories
4. Mark slow tests with `@pytest.mark.slow`
5. Mark platform-specific tests with `@pytest.mark.skipif`

Example:
```python
import pytest
import platform

@pytest.mark.slow
def test_full_compilation():
    # Long-running test
    pass

@pytest.mark.skipif(platform.system() != "Windows", reason="Windows only")
def test_windows_specific():
    # Windows-only test
    pass
```
