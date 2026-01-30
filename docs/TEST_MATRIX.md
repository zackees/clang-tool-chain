# Test Matrix

Comprehensive test coverage across all platforms and tool categories ensures reliability and quality.

## Platform Coverage

clang-tool-chain is tested on:
- **5 platforms:** Windows x64, Linux x86_64, Linux ARM64, macOS x86_64, macOS ARM64
- **9 tool categories:** clang, clang-sccache, emscripten, emscripten-sccache, iwyu, lldb, format-lint, binary-utils, cosmocc, lib-deploy
- **45 GitHub Actions workflows** covering all platform+tool combinations

## Test Matrix by Platform

| Tool Category | Windows x64 | Linux x86_64 | Linux ARM64 | macOS x86_64 | macOS ARM64 |
|---------------|-------------|--------------|-------------|--------------|-------------|
| **clang** | [![clang-win](https://github.com/zackees/clang-tool-chain/actions/workflows/test-clang-win.yml/badge.svg)](https://github.com/zackees/clang-tool-chain/actions/workflows/test-clang-win.yml) | [![clang-linux-x86](https://github.com/zackees/clang-tool-chain/actions/workflows/test-clang-linux-x86.yml/badge.svg)](https://github.com/zackees/clang-tool-chain/actions/workflows/test-clang-linux-x86.yml) | [![clang-linux-arm](https://github.com/zackees/clang-tool-chain/actions/workflows/test-clang-linux-arm.yml/badge.svg)](https://github.com/zackees/clang-tool-chain/actions/workflows/test-clang-linux-arm.yml) | [![clang-macos-x86](https://github.com/zackees/clang-tool-chain/actions/workflows/test-clang-macos-x86.yml/badge.svg)](https://github.com/zackees/clang-tool-chain/actions/workflows/test-clang-macos-x86.yml) | [![clang-macos-arm](https://github.com/zackees/clang-tool-chain/actions/workflows/test-clang-macos-arm.yml/badge.svg)](https://github.com/zackees/clang-tool-chain/actions/workflows/test-clang-macos-arm.yml) |
| **clang+sccache** | [![clang-sccache-win](https://github.com/zackees/clang-tool-chain/actions/workflows/test-clang-sccache-win.yml/badge.svg)](https://github.com/zackees/clang-tool-chain/actions/workflows/test-clang-sccache-win.yml) | [![clang-sccache-linux-x86](https://github.com/zackees/clang-tool-chain/actions/workflows/test-clang-sccache-linux-x86.yml/badge.svg)](https://github.com/zackees/clang-tool-chain/actions/workflows/test-clang-sccache-linux-x86.yml) | [![clang-sccache-linux-arm](https://github.com/zackees/clang-tool-chain/actions/workflows/test-clang-sccache-linux-arm.yml/badge.svg)](https://github.com/zackees/clang-tool-chain/actions/workflows/test-clang-sccache-linux-arm.yml) | [![clang-sccache-macos-x86](https://github.com/zackees/clang-tool-chain/actions/workflows/test-clang-sccache-macos-x86.yml/badge.svg)](https://github.com/zackees/clang-tool-chain/actions/workflows/test-clang-sccache-macos-x86.yml) | [![clang-sccache-macos-arm](https://github.com/zackees/clang-tool-chain/actions/workflows/test-clang-sccache-macos-arm.yml/badge.svg)](https://github.com/zackees/clang-tool-chain/actions/workflows/test-clang-sccache-macos-arm.yml) |
| **emscripten** | [![emscripten-windows-x86](https://github.com/zackees/clang-tool-chain/actions/workflows/test-emscripten-windows-x86.yml/badge.svg)](https://github.com/zackees/clang-tool-chain/actions/workflows/test-emscripten-windows-x86.yml) | [![emscripten-linux-x86](https://github.com/zackees/clang-tool-chain/actions/workflows/test-emscripten-linux-x86.yml/badge.svg)](https://github.com/zackees/clang-tool-chain/actions/workflows/test-emscripten-linux-x86.yml) | [![emscripten-linux-arm](https://github.com/zackees/clang-tool-chain/actions/workflows/test-emscripten-linux-arm.yml/badge.svg)](https://github.com/zackees/clang-tool-chain/actions/workflows/test-emscripten-linux-arm.yml) | [![emscripten-macos-x86](https://github.com/zackees/clang-tool-chain/actions/workflows/test-emscripten-macos-x86.yml/badge.svg)](https://github.com/zackees/clang-tool-chain/actions/workflows/test-emscripten-macos-x86.yml) | [![emscripten-macos-arm](https://github.com/zackees/clang-tool-chain/actions/workflows/test-emscripten-macos-arm.yml/badge.svg)](https://github.com/zackees/clang-tool-chain/actions/workflows/test-emscripten-macos-arm.yml) |
| **emscripten+sccache** | [![emscripten-sccache-win](https://github.com/zackees/clang-tool-chain/actions/workflows/test-emscripten-sccache-win.yml/badge.svg)](https://github.com/zackees/clang-tool-chain/actions/workflows/test-emscripten-sccache-win.yml) | [![emscripten-sccache-linux-x86](https://github.com/zackees/clang-tool-chain/actions/workflows/test-emscripten-sccache-linux-x86.yml/badge.svg)](https://github.com/zackees/clang-tool-chain/actions/workflows/test-emscripten-sccache-linux-x86.yml) | [![emscripten-sccache-linux-arm](https://github.com/zackees/clang-tool-chain/actions/workflows/test-emscripten-sccache-linux-arm.yml/badge.svg)](https://github.com/zackees/clang-tool-chain/actions/workflows/test-emscripten-sccache-linux-arm.yml) | [![emscripten-sccache-macos-x86](https://github.com/zackees/clang-tool-chain/actions/workflows/test-emscripten-sccache-macos-x86.yml/badge.svg)](https://github.com/zackees/clang-tool-chain/actions/workflows/test-emscripten-sccache-macos-x86.yml) | [![emscripten-sccache-macos-arm](https://github.com/zackees/clang-tool-chain/actions/workflows/test-emscripten-sccache-macos-arm.yml/badge.svg)](https://github.com/zackees/clang-tool-chain/actions/workflows/test-emscripten-sccache-macos-arm.yml) |
| **iwyu** | [![iwyu-win](https://github.com/zackees/clang-tool-chain/actions/workflows/test-iwyu-win.yml/badge.svg)](https://github.com/zackees/clang-tool-chain/actions/workflows/test-iwyu-win.yml) | [![iwyu-linux-x86](https://github.com/zackees/clang-tool-chain/actions/workflows/test-iwyu-linux-x86.yml/badge.svg)](https://github.com/zackees/clang-tool-chain/actions/workflows/test-iwyu-linux-x86.yml) | [![iwyu-linux-arm](https://github.com/zackees/clang-tool-chain/actions/workflows/test-iwyu-linux-arm.yml/badge.svg)](https://github.com/zackees/clang-tool-chain/actions/workflows/test-iwyu-linux-arm.yml) | [![iwyu-macos-x86](https://github.com/zackees/clang-tool-chain/actions/workflows/test-iwyu-macos-x86.yml/badge.svg)](https://github.com/zackees/clang-tool-chain/actions/workflows/test-iwyu-macos-x86.yml) | [![iwyu-macos-arm](https://github.com/zackees/clang-tool-chain/actions/workflows/test-iwyu-macos-arm.yml/badge.svg)](https://github.com/zackees/clang-tool-chain/actions/workflows/test-iwyu-macos-arm.yml) |
| **format-lint** | [![format-lint-win](https://github.com/zackees/clang-tool-chain/actions/workflows/test-format-lint-win.yml/badge.svg)](https://github.com/zackees/clang-tool-chain/actions/workflows/test-format-lint-win.yml) | [![format-lint-linux-x86](https://github.com/zackees/clang-tool-chain/actions/workflows/test-format-lint-linux-x86.yml/badge.svg)](https://github.com/zackees/clang-tool-chain/actions/workflows/test-format-lint-linux-x86.yml) | [![format-lint-linux-arm](https://github.com/zackees/clang-tool-chain/actions/workflows/test-format-lint-linux-arm.yml/badge.svg)](https://github.com/zackees/clang-tool-chain/actions/workflows/test-format-lint-linux-arm.yml) | [![format-lint-macos-x86](https://github.com/zackees/clang-tool-chain/actions/workflows/test-format-lint-macos-x86.yml/badge.svg)](https://github.com/zackees/clang-tool-chain/actions/workflows/test-format-lint-macos-x86.yml) | [![format-lint-macos-arm](https://github.com/zackees/clang-tool-chain/actions/workflows/test-format-lint-macos-arm.yml/badge.svg)](https://github.com/zackees/clang-tool-chain/actions/workflows/test-format-lint-macos-arm.yml) |
| **binary-utils** | [![binary-utils-win](https://github.com/zackees/clang-tool-chain/actions/workflows/test-binary-utils-win.yml/badge.svg)](https://github.com/zackees/clang-tool-chain/actions/workflows/test-binary-utils-win.yml) | [![binary-utils-linux-x86](https://github.com/zackees/clang-tool-chain/actions/workflows/test-binary-utils-linux-x86.yml/badge.svg)](https://github.com/zackees/clang-tool-chain/actions/workflows/test-binary-utils-linux-x86.yml) | [![binary-utils-linux-arm](https://github.com/zackees/clang-tool-chain/actions/workflows/test-binary-utils-linux-arm.yml/badge.svg)](https://github.com/zackees/clang-tool-chain/actions/workflows/test-binary-utils-linux-arm.yml) | [![binary-utils-macos-x86](https://github.com/zackees/clang-tool-chain/actions/workflows/test-binary-utils-macos-x86.yml/badge.svg)](https://github.com/zackees/clang-tool-chain/actions/workflows/test-binary-utils-macos-x86.yml) | [![binary-utils-macos-arm](https://github.com/zackees/clang-tool-chain/actions/workflows/test-binary-utils-macos-arm.yml/badge.svg)](https://github.com/zackees/clang-tool-chain/actions/workflows/test-binary-utils-macos-arm.yml) |
| **lldb** | [![lldb-win](https://github.com/zackees/clang-tool-chain/actions/workflows/test-lldb-win.yml/badge.svg)](https://github.com/zackees/clang-tool-chain/actions/workflows/test-lldb-win.yml) | [![lldb-linux-x86](https://github.com/zackees/clang-tool-chain/actions/workflows/test-lldb-linux-x86.yml/badge.svg)](https://github.com/zackees/clang-tool-chain/actions/workflows/test-lldb-linux-x86.yml) | [![lldb-linux-arm](https://github.com/zackees/clang-tool-chain/actions/workflows/test-lldb-linux-arm.yml/badge.svg)](https://github.com/zackees/clang-tool-chain/actions/workflows/test-lldb-linux-arm.yml) | [![lldb-macos-x86](https://github.com/zackees/clang-tool-chain/actions/workflows/test-lldb-macos-x86.yml/badge.svg)](https://github.com/zackees/clang-tool-chain/actions/workflows/test-lldb-macos-x86.yml) | [![lldb-macos-arm](https://github.com/zackees/clang-tool-chain/actions/workflows/test-lldb-macos-arm.yml/badge.svg)](https://github.com/zackees/clang-tool-chain/actions/workflows/test-lldb-macos-arm.yml) |
| **cosmocc** | [![cosmocc-win](https://github.com/zackees/clang-tool-chain/actions/workflows/test-cosmocc-win.yml/badge.svg)](https://github.com/zackees/clang-tool-chain/actions/workflows/test-cosmocc-win.yml) | [![cosmocc-linux-x86](https://github.com/zackees/clang-tool-chain/actions/workflows/test-cosmocc-linux-x86.yml/badge.svg)](https://github.com/zackees/clang-tool-chain/actions/workflows/test-cosmocc-linux-x86.yml) | [![cosmocc-linux-arm](https://github.com/zackees/clang-tool-chain/actions/workflows/test-cosmocc-linux-arm.yml/badge.svg)](https://github.com/zackees/clang-tool-chain/actions/workflows/test-cosmocc-linux-arm.yml) | [![cosmocc-macos-x86](https://github.com/zackees/clang-tool-chain/actions/workflows/test-cosmocc-macos-x86.yml/badge.svg)](https://github.com/zackees/clang-tool-chain/actions/workflows/test-cosmocc-macos-x86.yml) | [![cosmocc-macos-arm](https://github.com/zackees/clang-tool-chain/actions/workflows/test-cosmocc-macos-arm.yml/badge.svg)](https://github.com/zackees/clang-tool-chain/actions/workflows/test-cosmocc-macos-arm.yml) |
| **lib-deploy** | [![lib-deploy-win](https://github.com/zackees/clang-tool-chain/actions/workflows/test-lib-deploy-win.yml/badge.svg)](https://github.com/zackees/clang-tool-chain/actions/workflows/test-lib-deploy-win.yml) | [![lib-deploy-linux-x86](https://github.com/zackees/clang-tool-chain/actions/workflows/test-lib-deploy-linux-x86.yml/badge.svg)](https://github.com/zackees/clang-tool-chain/actions/workflows/test-lib-deploy-linux-x86.yml) | [![lib-deploy-linux-arm](https://github.com/zackees/clang-tool-chain/actions/workflows/test-lib-deploy-linux-arm.yml/badge.svg)](https://github.com/zackees/clang-tool-chain/actions/workflows/test-lib-deploy-linux-arm.yml) | [![lib-deploy-macos-x86](https://github.com/zackees/clang-tool-chain/actions/workflows/test-lib-deploy-macos-x86.yml/badge.svg)](https://github.com/zackees/clang-tool-chain/actions/workflows/test-lib-deploy-macos-x86.yml) | [![lib-deploy-macos-arm](https://github.com/zackees/clang-tool-chain/actions/workflows/test-lib-deploy-macos-arm.yml/badge.svg)](https://github.com/zackees/clang-tool-chain/actions/workflows/test-lib-deploy-macos-arm.yml) |

## Tool Category Descriptions

### clang
Basic Clang/LLVM compilation for C and C++ source files. Tests verify:
- Basic compilation of C and C++ programs
- Linking executables and libraries
- Platform-specific SDK detection (macOS)
- MinGW integration (Windows GNU ABI)
- MSVC ABI support (Windows)

### clang+sccache
Clang compilation with sccache compilation caching. Tests verify:
- Cache hit/miss detection
- Compilation speedup on cache hits
- Cache persistence across builds
- Multi-file project caching

### emscripten
WebAssembly compilation with Emscripten SDK. Tests verify:
- C to WASM compilation
- C++ to WASM compilation
- Generated JavaScript glue code
- Bundled Node.js runtime execution

### emscripten+sccache
Emscripten with sccache caching. Tests verify:
- Emscripten cache hit/miss
- WASM compilation caching
- Cache speedup metrics

### iwyu
Include What You Use analyzer. Tests verify:
- Header dependency analysis
- Unnecessary include detection
- Missing include suggestions
- Forward declaration recommendations

### format-lint
clang-format and clang-tidy tools. Tests verify:
- Code formatting consistency
- Style preset application
- Static analysis checks
- Auto-fix functionality

### binary-utils
LLVM binary utilities (ar, nm, objdump, strip, readelf, etc.). Tests verify:
- Static library creation
- Symbol table inspection
- Binary disassembly
- Debug symbol stripping

### lldb
LLDB debugger for crash analysis and debugging. Tests verify:
- Interactive debugging session startup
- Breakpoint setting
- Stack trace generation
- Core dump analysis (where supported)

### cosmocc
Cosmopolitan Libc for Actually Portable Executables. Tests verify:
- APE compilation for C
- APE compilation for C++
- Cross-platform binary execution
- No runtime dependencies

### lib-deploy
Automatic shared library deployment for executables. Tests verify:
- Windows DLL detection and deployment (MinGW runtime)
- Linux .so detection and deployment (libc++, libunwind, sanitizers)
- macOS .dylib detection and deployment (@rpath resolution)
- Symlink handling for versioned libraries
- Environment variable controls
- Cross-platform factory pattern

## Test Organization

### Test Files by Category

Tests are organized in the `tests/` directory by tool category:

- **tests/test_integration.py** - Basic clang compilation tests
- **tests/test_emscripten.py** - Emscripten WebAssembly compilation
- **tests/test_emscripten_full_pipeline.py** - Full Emscripten pipeline tests
- **tests/test_iwyu.py** - Include What You Use analyzer tests
- **tests/test_lldb.py** - LLDB debugger tests
- **tests/test_format_lint.py** - clang-format and clang-tidy tests
- **tests/test_binary_utils.py** - LLVM binary utilities tests
- **tests/test_build_run_cached_integration.py** - sccache integration tests
- **tests/test_cosmocc.py** - Cosmopolitan Libc tests
- **tests/test_dll_deployment.py** - Windows DLL deployment tests
- **tests/test_so_deployment.py** - Linux .so deployment tests
- **tests/test_dylib_deployment.py** - macOS .dylib deployment tests
- **tests/test_deployment_factory.py** - Cross-platform deployment factory tests

### Running Tests Locally

```bash
# Run all tests
./test

# Run tests for specific category
uv run pytest tests/test_integration.py -v
uv run pytest tests/test_emscripten.py -v
uv run pytest tests/test_iwyu.py -v

# Run tests in parallel
uv run pytest -n auto
```

### CI/CD Integration

Each platform+tool combination has a dedicated GitHub Actions workflow:
- Workflow files: `.github/workflows/test-{category}-{platform}.yml`
- Triggered on: push, pull request
- Runs: Platform-specific tests for the category

## Test Coverage Goals

- **Platform Coverage:** All supported platforms (Windows, Linux x86_64/ARM64, macOS x86_64/ARM64)
- **Tool Coverage:** All 41 wrapper commands tested
- **Integration Testing:** Real compilation, linking, and execution
- **Edge Cases:** Platform-specific features, ABI differences, SDK detection

## Continuous Integration

All workflows are triggered on:
- Push to main branch
- Pull requests to main
- Manual workflow dispatch

Results are displayed as status badges in this document and the main README.

## See Also

- [Testing Guide](TESTING.md) - Comprehensive testing documentation
- [CI/CD Integration](CICD_INTEGRATION.md) - CI/CD setup and best practices
- [Contributing](CONTRIBUTING.md) - How to add new tests
