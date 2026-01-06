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

## Parallel Testing Infrastructure

The test suite supports parallel execution using `pytest-xdist` for faster test runs.

### Automatic Toolchain Pre-installation

The `tests/conftest.py` file contains a `pytest_configure()` hook that **automatically pre-installs the toolchain before running parallel tests**. This prevents race conditions and timeout issues when multiple worker processes try to download the toolchain simultaneously.

**How it works:**
1. The hook runs once in the main process before pytest-xdist spawns workers
2. It checks if the toolchain is already installed
3. If not, it downloads and installs the toolchain (~30-60 seconds for initial download)
4. Worker processes find the toolchain already installed and start immediately
5. No test timeouts waiting for concurrent downloads

**Why this is needed:**
- Without pre-installation, all worker processes would call `ensure_toolchain()` simultaneously
- Process 1 acquires the lock and downloads ~90MB (~30-60 seconds)
- Processes 2-N wait for the lock
- Tests timeout (10-30 seconds) before download completes → test failures

This pattern is especially important for:
- CI environments (GitHub Actions) with fresh installations
- Local development after `clang-tool-chain purge`
- Windows where file locking can add delays

**Implementation details:**
```python
# tests/conftest.py
def pytest_configure(config):
    """Pre-install toolchain before spawning worker processes."""
    if not hasattr(config, "workerinput"):  # Only in main process
        platform_name, arch = get_platform_info()
        installer.ensure_toolchain(platform_name, arch)
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

### Tool-Specific Tests

- `test_format_lint.py` - clang-format and clang-tidy tools (6 tests)
- `test_binary_utils.py` - LLVM binary utilities (14 tests: ar, nm, objdump, strip, readelf, objcopy, ranlib)
- `test_iwyu.py` - Include What You Use analyzer tests
- `test_lldb.py` - LLDB debugger tests (4 tests: installation, crash analysis, full backtraces)
- `test_build_run_cached_integration.py` - sccache integration tests

## LLDB Debugger Testing

The LLDB test suite verifies that the LLVM debugger can analyze crash dumps, produce stack traces, and work with bundled Python modules.

### Running LLDB Tests

```bash
# Run all LLDB tests
uv run pytest tests/test_lldb.py -v

# Run specific test
uv run pytest tests/test_lldb.py::TestLLDBExecution::test_lldb_full_backtraces_with_python -v
```

### Test Coverage (4 tests)

**Installation Tests (`TestLLDBInstallation`):**
1. **test_lldb_binary_dir_exists** - Verify LLDB binary directory can be located
2. **test_find_lldb_tool** - Verify lldb binary can be found

**Execution Tests (`TestLLDBExecution`):**
3. **test_lldb_print_crash_stack** - Basic crash analysis with stack traces
4. **test_lldb_full_backtraces_with_python** - Full backtraces with Python modules (requires bundled Python)

### Test Features

**Enhanced Diagnostics (Iteration 16):**
- **Formatted diagnostic output** - Full command execution details with timing
- **Stack frame extraction** - Parse and display extracted stack frames
- **Missing function detection** - Lists which expected functions are missing from backtrace
- **Performance timing** - Compile and LLDB execution times tracked and reported
- **Comprehensive error messages** - Context-rich failures with full output dumps

**Diagnostic Output Format:**
```
================================================================================
DIAGNOSTIC: LLDB Crash Analysis
================================================================================
Command: clang-tool-chain-lldb --print crash_test.exe
Elapsed Time: 1.23s
Return Code: 0

STDOUT (1234 chars):
--------------------------------------------------------------------------------
(lldb output here)
--------------------------------------------------------------------------------

STDERR (0 chars):
--------------------------------------------------------------------------------
(empty)
--------------------------------------------------------------------------------
================================================================================

Extracted 5 stack frames:
  frame #0: 0x00007ff1234 crash_test.exe`trigger_crash at crash_test.c:12
  frame #1: 0x00007ff1235 crash_test.exe`intermediate_function at crash_test.c:18
  frame #2: 0x00007ff1236 crash_test.exe`main at crash_test.c:24
```

**Performance Metrics:**
```
✓ test_lldb_print_crash_stack: compile=0.45s, lldb=1.23s, total=1.68s
✓ test_lldb_full_backtraces_with_python: compile=0.52s, lldb=1.45s, total=1.97s
  Functions found: 8/8, Frames extracted: 12
```

### Test Behavior

**test_lldb_print_crash_stack:**
- Compiles crash_test.c with null pointer dereference
- Runs LLDB with `--print` flag to analyze crash
- Verifies output contains:
  - Function names: main, intermediate_function, trigger_crash
  - Source file reference: crash_test.c
  - Line number information (e.g., `:12`, `line 12`)
  - Crash reason (SIGSEGV, access violation, etc.)
- Reports timing: compile time, LLDB execution time, total time
- Extracts and displays stack frames on failure

**test_lldb_full_backtraces_with_python:**
- Checks if Python is bundled with LLDB installation
- **Skips if Python not bundled** (status != "ready")
- Compiles deep_stack.c with 7-level deep call stack
- Runs LLDB crash analysis
- Verifies all 7 user functions visible in backtrace:
  - main, level1, level2, level3, level4, level5, level6, level7_crash
- Verifies line numbers and source file references
- Verifies no Python-related errors if Python is bundled
- Reports function coverage: "Functions found: 8/8, Frames extracted: 12"

### Platform Support

**Current Status:**
- ✅ **Windows x64** - Complete with Python 3.10 bundled
- ⏳ **Linux x86_64** - Wrapper ready, archives pending workflow execution
- ⏳ **Linux ARM64** - Wrapper ready, archives pending workflow execution
- ⏳ **macOS x86_64** - Planned
- ⏳ **macOS ARM64** - Planned

**Python Bundling:**
- **Windows x64**: Python 3.10 bundled (full "bt all" support)
- **Linux**: Python 3.10 ready for bundling (archives pending)
- **macOS**: Planned for future releases

### Test Skip Behavior

**Python-Dependent Tests:**
The `test_lldb_full_backtraces_with_python` test will skip if:
- LLDB Python environment status is not "ready"
- Python site-packages are not bundled
- Python diagnostic check fails

Skip message example:
```
SKIPPED: Python is not bundled with LLDB installation (status: not_found).
Message: Python directory not found at ~/.clang-tool-chain/lldb-*/python.
This test requires LLDB with Python 3.10 site-packages.
The LLDB distribution may not include Python modules yet.
```

### Troubleshooting Test Failures

**Missing Functions in Stack Trace:**
```
Missing functions in stack trace: ['level5', 'level6']
Found functions: ['main', 'level1', 'level2', 'level3', 'level4', 'level7_crash']
This may indicate incomplete backtrace support.

Extracted 10 stack frames:
  frame #0: ...
  (diagnostic output follows)
```
- **Cause**: Incomplete backtrace, Python modules not loaded, or debug symbols missing
- **Solution**: Check Python environment, verify debug symbols with `-g3`, review diagnostic output

**No Line Numbers Found:**
```
Stack trace should contain line numbers (patterns: [':\d+', 'line \d+', '#\d+.*:\d+'])
No line numbers found - debug symbols may not be loaded
```
- **Cause**: Compilation without debug symbols, stripped binary, or LLDB configuration issue
- **Solution**: Ensure `-g3` flag used, check executable not stripped, verify LLDB can load symbols

**Python Errors Detected:**
```
Python errors detected: ['ModuleNotFoundError', 'ImportError']
Python is bundled (status: ready) but errors occurred.
This indicates a configuration problem with the bundled Python.
```
- **Cause**: PYTHONPATH misconfigured, missing Python modules, or incompatible Python version
- **Solution**: Check Python environment with `clang-tool-chain-lldb --check-python`, review LLDB.md troubleshooting

### CI/CD Integration

**GitHub Actions Workflows:**
- `.github/workflows/test-lldb-linux-x86.yml` - Linux x86_64 LLDB tests
- `.github/workflows/test-lldb-linux-arm.yml` - Linux ARM64 LLDB tests (native runner)
- `.github/workflows/test-lldb-win.yml` - Windows x64 LLDB tests
- `.github/workflows/test-lldb-macos-*.yml` - macOS LLDB tests (planned)

**Workflow Behavior:**
- Skip steps removed in Iteration 13 (workflows now execute full test suite)
- ARM64 workflow uses native `ubuntu-24.04-arm` runner for accurate testing
- Tests run on every push/PR to verify LLDB functionality
- Archives downloaded and extracted before tests execute

### Test Development Guidelines

**Adding New LLDB Tests:**
1. Add test methods to appropriate test class (Installation or Execution)
2. Use `@pytest.mark.serial` to prevent parallel execution conflicts
3. Create temporary directories for test programs (`self.temp_path`)
4. Use helper methods for diagnostics:
   - `_format_diagnostic_output()` - Format command execution details
   - `_extract_stack_frames()` - Parse LLDB output for stack frames
5. Track timing information in `self.timing_info` dict
6. Print success metrics for performance monitoring
7. Provide comprehensive error messages with context

**Example Test Structure:**
```python
def test_new_lldb_feature(self) -> None:
    """Test description with steps and success criteria."""
    # Step 1: Setup
    compile_cmd = [...]
    start_time = time.time()
    result = subprocess.run(compile_cmd, ...)
    compile_time = time.time() - start_time

    # Assertion with diagnostic output
    self.assertEqual(
        result.returncode, 0,
        f"Compilation failed{self._format_diagnostic_output('Title', compile_cmd, result, compile_time)}"
    )

    # Step 2: LLDB execution with timing
    lldb_cmd = [...]
    start_time = time.time()
    result = subprocess.run(lldb_cmd, ...)
    lldb_time = time.time() - start_time

    # Extract frames and create diagnostic
    output = result.stdout + result.stderr
    frames = self._extract_stack_frames(output)
    diagnostic = self._format_diagnostic_output("LLDB Analysis", lldb_cmd, result, lldb_time)

    # Assertions with context
    if expected_item not in output:
        self.fail(f"Expected item missing\nFrames: {len(frames)}{diagnostic}")

    # Success metrics
    print(f"✓ test_name: compile={compile_time:.2f}s, lldb={lldb_time:.2f}s")
```

### Related Documentation

- **LLDB User Guide**: `docs/LLDB.md` - Comprehensive LLDB usage documentation
- **Linux Troubleshooting**: `docs/LLDB.md` (Linux-Specific Troubleshooting section)
- **Python Integration**: `docs/LLDB.md` (Python Integration section)
- **Archive Integration**: `.agent_task/ARCHIVE_INTEGRATION_CHECKLIST.md`
- **Workflow Triggering**: `.agent_task/WORKFLOW_TRIGGER_GUIDE.md`

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

The project uses a comprehensive test matrix with **35 GitHub Actions workflows** covering all platform+tool combinations:

**Test Matrix Structure:**
- **5 platforms:** Windows x64, Linux x86_64, Linux ARM64, macOS x86_64, macOS ARM64
- **7 tool categories:** clang, clang-sccache, emscripten, emscripten-sccache, iwyu, format-lint, binary-utils

**Core Workflows:**
- `.github/workflows/test.yml` - Cross-platform test suite (Linux, macOS, Windows)
- `.github/workflows/test-win-msvc.yml` - Windows MSVC-specific tests
- `.github/workflows/lint.yml` - Code quality checks

**Tool-Specific Workflows (per platform):**
- `test-clang-{platform}.yml` - Basic clang compilation tests
- `test-clang-sccache-{platform}.yml` - Clang with sccache caching
- `test-emscripten-{platform}.yml` - Emscripten WebAssembly compilation
- `test-emscripten-sccache-{platform}.yml` - Emscripten with sccache
- `test-iwyu-{platform}.yml` - Include What You Use analyzer
- `test-format-lint-{platform}.yml` - clang-format and clang-tidy
- `test-binary-utils-{platform}.yml` - LLVM binary utilities

All workflows run on:
- Every push to main branch
- Every pull request
- Manual workflow dispatch

See the README.md "Test Matrix" section for live status badges showing all 35 workflows.

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
