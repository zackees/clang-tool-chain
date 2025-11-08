# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- Placeholder for future changes

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
