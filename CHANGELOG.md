# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Changed
- **Windows GNU ABI**: MinGW headers and sysroot are now integrated into the main Clang archive
  - Eliminates separate 91 MB MinGW download on first use
  - Simplifies installation process - single archive download
  - Reduces total download size from 145 MB to ~53 MB (integrated archive)
  - MinGW headers in `<clang_root>/include/`
  - Sysroot in `<clang_root>/x86_64-w64-mingw32/`
  - Compiler-rt in `<clang_root>/lib/clang/<version>/`
  - No API changes - existing code continues to work
  - Automatic migration on next toolchain download
  - Wrapper automatically adds explicit include paths for integrated headers
  - Resource directory auto-detection for compiler intrinsics and runtime libraries

### Removed
- Separate MinGW sysroot download and installation logic
- `ensure_mingw_sysroot_installed()` function (internal API, not user-facing)
- `download_and_install_mingw()` function (internal API, not user-facing)
- MinGW-specific manifest fetching functions (internal API, not user-facing)
- `MINGW_MANIFEST_BASE_URL` constant (internal, not user-facing)
- Approximately 320 lines of MinGW-specific download code

### Fixed
- Windows GNU ABI compilation now works correctly with integrated MinGW headers
- Explicit include paths added for C++ standard library and MinGW headers
- Resource directory auto-detection for compiler intrinsics (mm_malloc.h, etc.)
- Resource directory correctly set for linking with libclang_rt.builtins.a
- Manifest test now correctly handles deprecated versions when determining "latest"

### Migration Notes
- Existing installations will automatically download the new integrated archive on next use
- Old cached MinGW archives in `~/.clang-tool-chain/mingw/` are no longer used (safe to delete)
- Use `clang-tool-chain purge --yes` to remove old cache and download fresh integrated archive
- No code changes required for users - wrappers automatically detect integrated headers

### Added
- **Node.js Bundling for Emscripten**: Automatic download and installation of minimal Node.js runtime
  - No manual Node.js installation required for Emscripten users
  - Three-tier priority system: bundled > system > auto-download
  - Minimal Node.js runtime: ~23-24 MB per platform (38% smaller than official distributions)
  - Automatic download on first Emscripten use (one-time, ~10-30 seconds)
  - Falls back to system Node.js if available
  - Supported platforms: Windows x64, Linux x64/ARM64, macOS x64/ARM64
  - File locking prevents concurrent downloads
  - SHA256 checksum verification for all downloads
  - Comprehensive test suite with 22 test cases
  - Installation path: `~/.clang-tool-chain/nodejs/{platform}/{arch}/`
- Maintainer script: `downloads-bins/tools/fetch_and_archive_nodejs.py` for generating Node.js archives
- Comprehensive Node.js bundling documentation in CLAUDE.md

## [0.0.1] - 2025-11-07

### Added
- Initial alpha release of clang-tool-chain package
- Python wrapper executables for LLVM/Clang tools:
  - `clang-tool-chain-c` - C compiler wrapper (clang)
  - `clang-tool-chain-cpp` - C++ compiler wrapper (clang++)
  - `clang-tool-chain-ld` - Linker wrapper (lld/lld-link)
  - `clang-tool-chain-ar` - Archive tool wrapper (llvm-ar)
  - `clang-tool-chain-nm` - Symbol viewer wrapper (llvm-nm)
  - `clang-tool-chain-objdump` - Object dumper wrapper (llvm-objdump)
  - `clang-tool-chain-objcopy` - Object copy/modify wrapper (llvm-objcopy)
  - `clang-tool-chain-ranlib` - Archive indexer wrapper (llvm-ranlib)
  - `clang-tool-chain-strip` - Symbol stripper wrapper (llvm-strip)
  - `clang-tool-chain-readelf` - ELF reader wrapper (llvm-readelf)
  - `clang-tool-chain-as` - Assembler wrapper (llvm-as)
  - `clang-tool-chain-dis` - Disassembler wrapper (llvm-dis)
  - `clang-tool-chain-format` - Code formatter wrapper (clang-format)
  - `clang-tool-chain-tidy` - Static analyzer wrapper (clang-tidy)
- CLI commands:
  - `clang-tool-chain info` - Display package information
  - `clang-tool-chain version` - Display version information
  - `clang-tool-chain list-tools` - List all available tools
  - `clang-tool-chain path` - Show installation paths
- Download script (`scripts/download_binaries.py`):
  - Download LLVM 21.1.5 binaries for Windows, Linux, and macOS
  - Support for x86_64 and ARM64 architectures
  - Checksum verification
  - Automatic extraction and organization
- Strip script (`scripts/strip_binaries.py`):
  - Remove unnecessary files (docs, headers, examples)
  - Remove unused tools
  - Strip debug symbols with llvm-strip
  - Reduce size from ~3.5GB to ~300-400MB per platform
- Platform detection and binary location logic
- Cross-platform support: Windows (x64), Linux (x64/ARM64), macOS (x64/ARM64)
- Comprehensive test suite:
  - 30 unit tests for wrapper and CLI modules
  - Integration test framework for real binary testing
  - Example programs (hello.c, hello.cpp, math library demo)
- Documentation:
  - Comprehensive README with installation and usage instructions
  - Examples directory with compilation tutorials
  - CONTRIBUTING.md with development guidelines
  - CHANGELOG.md for version tracking
  - CLAUDE.md for AI assistant guidance
- GitHub Actions CI/CD workflows:
  - test.yml - Multi-platform testing (Windows, Linux, macOS)
  - lint.yml - Code quality checks
  - release.yml - PyPI publishing automation
- Development tooling:
  - Pre-commit hooks for code quality
  - Convenience scripts (./install, ./test, ./lint, ./clean)
  - uv-based dependency management
  - Coverage reporting with pytest-cov

### Infrastructure
- Modern Python packaging with pyproject.toml
- Python 3.10+ support
- Apache 2.0 License with LLVM Exceptions
- Multi-platform GitHub Actions testing matrix
- Code quality tools: ruff, black, isort, mypy, pyright

### Notes
- This is an alpha release for testing and development
- LLVM binaries must be downloaded separately using provided scripts
- Binary size optimization reduces ~15GB (all platforms) to ~1.5-2GB
- Integration tests skip gracefully when binaries are not available

## Version History

- **0.0.1** (2025-11-07) - Initial alpha release with core functionality

---

## Types of Changes

- **Added** - New features
- **Changed** - Changes in existing functionality
- **Deprecated** - Soon-to-be removed features
- **Removed** - Removed features
- **Fixed** - Bug fixes
- **Security** - Vulnerability fixes

## Links

- [Repository](https://github.com/OWNER/clang-tool-chain)
- [Issue Tracker](https://github.com/OWNER/clang-tool-chain/issues)
- [PyPI Package](https://pypi.org/project/clang-tool-chain/)
