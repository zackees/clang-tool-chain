# Acknowledgments

This project stands on the shoulders of giants. We're grateful to the following projects and their maintainers:

## Core Technologies

### LLVM Project
- **[LLVM Project](https://llvm.org/)**
- For the excellent Clang/LLVM toolchain that powers this package
- License: Apache License 2.0 with LLVM Exception
- LLVM provides the world-class compiler infrastructure that makes modern C/C++ development possible

### GitHub LLVM Releases
- **[GitHub LLVM Releases](https://github.com/llvm/llvm-project/releases)**
- For providing pre-built binaries across all platforms
- These official releases enable the entire auto-download distribution model
- Saves users from having to build LLVM from source (2-4 hours compile time)

## Compression & Performance

### Zstandard (zstd)
- **[Zstandard (zstd)](https://facebook.github.io/zstd/)**
- For incredible compression performance enabling ultra-compact archives
- Achieves ~94% size reduction at level 22 (1.5 GB → 71-91 MB)
- Fast decompression ensures minimal overhead on first use
- License: BSD 3-Clause

### pyzstd
- **[pyzstd](https://github.com/animalize/pyzstd)**
- For Python bindings to Zstandard
- Enables seamless zstd integration in Python tooling
- License: BSD 3-Clause

## Infrastructure & Utilities

### fasteners
- **[fasteners](https://github.com/harlowja/fasteners)**
- For cross-platform file locking
- Ensures thread-safe and process-safe downloads and installations
- Critical for concurrent builds and parallel CI/CD pipelines
- License: Apache License 2.0

### Emscripten
- **[Emscripten](https://emscripten.org/)**
- For the complete C/C++ to WebAssembly toolchain
- Makes browser-based and Node.js C/C++ applications possible
- Includes bundled LLVM (separate from main clang-tool-chain LLVM)
- License: MIT/Apache 2.0 dual license

### Node.js
- **[Node.js](https://nodejs.org/)**
- For the JavaScript runtime bundled with Emscripten
- Enables running WebAssembly applications without separate installation
- License: MIT

### Cosmopolitan Libc
- **[Cosmopolitan Libc](https://github.com/jart/cosmopolitan)**
- For the Actually Portable Executable (APE) format
- Makes "build once, run anywhere" a reality for C/C++ programs
- Single binary runs natively on Windows, Linux, macOS, FreeBSD, etc.
- License: ISC

### Include What You Use (IWYU)
- **[IWYU](https://include-what-you-use.org/)**
- For the include-optimization analyzer
- Helps maintain clean, minimal header dependencies
- Reduces compile times and build complexity
- License: LLVM Exception

## Build Tools & Ecosystem

### sccache
- **[sccache](https://github.com/mozilla/sccache)**
- For distributed compilation caching
- Provides 2-10x speedup on rebuilds
- Supports cloud storage backends (S3, Redis, GCS, Azure)
- License: Apache License 2.0

### uv
- **[uv](https://github.com/astral-sh/uv)**
- For ultra-fast Python package management
- Powers the executable C++ script workflow (`uvx`)
- 10-100x faster than pip for package installation
- License: Apache License 2.0 / MIT

## Packaging & Distribution

### PyPI
- **[Python Package Index (PyPI)](https://pypi.org/)**
- For hosting and distributing the package
- Makes `pip install clang-tool-chain` possible
- Serves millions of downloads to developers worldwide

### GitHub
- **[GitHub](https://github.com/)**
- For hosting the repository and CI/CD infrastructure
- GitHub Actions provides free CI/CD for all platforms
- Enables comprehensive test matrix (40 workflows)

### GitHub Actions
- **[GitHub Actions](https://github.com/features/actions)**
- For free, powerful CI/CD across Windows, Linux, and macOS
- Runs 40 test workflows on every commit
- Ensures quality across all platform+tool combinations

## Development Tools

### pytest
- **[pytest](https://pytest.org/)**
- For the testing framework
- Powers comprehensive test suite with 200+ tests
- License: MIT

### Ruff
- **[Ruff](https://github.com/astral-sh/ruff)**
- For ultra-fast Python linting and formatting
- 10-100x faster than traditional tools (Flake8, Black)
- Handles linting, formatting, and import sorting in one tool
- License: MIT

### MyPy & Pyright
- **[MyPy](https://github.com/python/mypy)**
- **[Pyright](https://github.com/microsoft/pyright)**
- For static type checking
- Catches type errors before runtime
- Ensures code quality and maintainability
- Licenses: MIT

## Community & Inspiration

### Python Community
- For the incredible ecosystem of libraries and tools
- Python's simplicity makes this distribution model possible
- Cross-platform support is unmatched

### C++ Community
- For decades of language evolution and tooling improvements
- Modern C++ (C++11/14/17/20/23) makes complex projects manageable
- Standards committee ensures language continues to evolve

### Open Source Community
- For the collaborative spirit that makes projects like this possible
- Contributors who report bugs, suggest features, and submit fixes
- Users who trust and adopt the tool in their workflows

## Special Thanks

### Users & Contributors
- Every user who reports issues, suggests improvements, or spreads the word
- Contributors who submit pull requests, documentation fixes, and test cases
- Early adopters who provided feedback during development

### Maintainers of Dependencies
- All the maintainers of the libraries clang-tool-chain depends on
- Their tireless work ensures the foundation remains stable
- Security updates and bug fixes flow through the ecosystem

---

## How to Contribute

Want to contribute to clang-tool-chain? See the **[Contributing Guide](CONTRIBUTING.md)** for:
- How to add new tools
- Codebase architecture
- Testing requirements
- Submission guidelines

Found a bug or have a feature request? Open an issue on [GitHub](https://github.com/zackees/clang-tool-chain/issues).

---

## License

clang-tool-chain is distributed under the **Apache License 2.0**. See [LICENSE_INFO.md](LICENSE_INFO.md) for complete licensing details for all bundled components.

---

**Thank you to everyone who makes this project possible!**
