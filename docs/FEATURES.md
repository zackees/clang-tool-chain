# Features

Complete feature reference for clang-tool-chain.

## Core Features

### Automatic Download on First Use
Zero-configuration installation to `~/.clang-tool-chain/`. No manual setup required - the toolchain downloads automatically when you first use any command.

### Manifest-Based Distribution
Version-controlled releases with SHA256 checksum verification. Every download is verified against cryptographic checksums stored in the version-controlled manifest.

### Multi-Part Archive Support
Transparent handling of large archives (>100 MB) split into parts. The downloader automatically reassembles multi-part archives without user intervention.

### Ultra-Optimized Archives
94.3% size reduction achieved through:
- Binary stripping (removes unnecessary symbols)
- File deduplication (hardlinks for identical files)
- zstd level 22 compression (maximum compression ratio)

**Result:** LLVM archives reduced from ~1.3 GB to ~71-91 MB

### Cross-Platform Support
Uniform interface across all platforms:
- Windows x86_64
- macOS x86_64 (Intel)
- macOS ARM64 (Apple Silicon)
- Linux x86_64
- Linux ARM64

### Concurrent-Safe Installation
File locking prevents race conditions in parallel builds. Multiple processes can safely trigger toolchain installation simultaneously.

### Python Wrapper Commands
35 entry points for all essential LLVM tools. Every tool accessible via `clang-tool-chain-*` command prefix.

### Pre-Built Binaries
Official LLVM binaries with minimal modifications:
- Clang 21.1.5 (Windows x64, Linux x86_64/ARM64)
- Clang 21.1.6 (macOS ARM64)
- Clang 19.1.7 (macOS x86_64)

### Essential Toolchain Utilities
Complete C/C++ development environment:
- Compilers (clang, clang++)
- Linkers (lld, lld-link)
- Binary utilities (ar, nm, objdump, strip, readelf, ranlib, objcopy, as, dis)
- Code formatters (clang-format, clang-tidy)
- Include analyzer (IWYU)
- Debugger (LLDB)
- WebAssembly compiler (Emscripten)
- APE compiler (Cosmopolitan)

### Automatic macOS SDK Detection
Seamlessly finds system headers on macOS without configuration. Uses `xcrun --show-sdk-path` to locate SDK automatically.

## All Available Commands

### Management & Utilities (6 commands)

| Command | Description |
|---------|-------------|
| `clang-tool-chain` | Main management interface (subcommands: info, version, list-tools, path, package-version, test, purge) |
| `clang-tool-chain-test` | Run 7 diagnostic tests to verify installation |
| `clang-tool-chain-fetch` | Manual download utility for pre-fetching binaries |
| `clang-tool-chain-paths` | Get installation paths in JSON format |

### Clang/LLVM Compilers (4 commands)

| Command | Description | Platform |
|---------|-------------|----------|
| `clang-tool-chain-c` | C compiler (GNU ABI) | All platforms |
| `clang-tool-chain-cpp` | C++ compiler (GNU ABI) | All platforms |
| `clang-tool-chain-c-msvc` | C compiler (MSVC ABI) | Windows only |
| `clang-tool-chain-cpp-msvc` | C++ compiler (MSVC ABI) | Windows only |

### Build Utilities (3 commands)

| Command | Description |
|---------|-------------|
| `clang-tool-chain-build` | Simple build tool for C/C++ |
| `clang-tool-chain-build-run` | Compile and run in one step (with optional caching) |
| `clang-tool-chain-run` | Run cached build (from --cached builds) |

### sccache Compilation Caching (5 commands)

| Command | Description | Platform |
|---------|-------------|----------|
| `clang-tool-chain-sccache` | Direct sccache access (stats, management) | All platforms |
| `clang-tool-chain-sccache-c` | C compiler with sccache caching (GNU ABI) | All platforms |
| `clang-tool-chain-sccache-cpp` | C++ compiler with sccache caching (GNU ABI) | All platforms |
| `clang-tool-chain-sccache-c-msvc` | C compiler with sccache caching (MSVC ABI) | Windows only |
| `clang-tool-chain-sccache-cpp-msvc` | C++ compiler with sccache caching (MSVC ABI) | Windows only |

### LLVM Binary Utilities (11 commands)

| Command | Tool | Description |
|---------|------|-------------|
| `clang-tool-chain-ld` | `lld` / `lld-link` | LLVM linker |
| `clang-tool-chain-ar` | `llvm-ar` | Archive/library creator |
| `clang-tool-chain-nm` | `llvm-nm` | Symbol table viewer |
| `clang-tool-chain-objdump` | `llvm-objdump` | Object file dumper/disassembler |
| `clang-tool-chain-objcopy` | `llvm-objcopy` | Object file copier/modifier |
| `clang-tool-chain-ranlib` | `llvm-ranlib` | Archive index generator |
| `clang-tool-chain-strip` | `llvm-strip` | Symbol stripper |
| `clang-tool-chain-readelf` | `llvm-readelf` | ELF file reader |
| `clang-tool-chain-as` | `llvm-as` | LLVM assembler |
| `clang-tool-chain-dis` | `llvm-dis` | LLVM disassembler |
| `clang-tool-chain-size` | `llvm-size` | Binary size analyzer |

### Format & Lint (2 commands)

| Command | Tool | Description |
|---------|------|-------------|
| `clang-tool-chain-format` | `clang-format` | Code formatter |
| `clang-tool-chain-tidy` | `clang-tidy` | Static analyzer/linter |

### IWYU Include Analyzer (3 commands)

| Command | Tool | Description |
|---------|------|-------------|
| `clang-tool-chain-iwyu` | `include-what-you-use` | Include analyzer - finds unnecessary includes |
| `clang-tool-chain-iwyu-tool` | `iwyu_tool.py` | IWYU batch runner for projects |
| `clang-tool-chain-fix-includes` | `fix_includes.py` | Automatically fix includes based on IWYU output |

### LLDB Debugger (2 commands)

| Command | Tool | Description |
|---------|------|-------------|
| `clang-tool-chain-lldb` | `lldb` | LLVM debugger for interactive debugging |
| `clang-tool-chain-lldb-check-python` | Diagnostic | Check LLDB Python support status |

### Emscripten WebAssembly (5 commands)

| Command | Tool | Description |
|---------|------|-------------|
| `clang-tool-chain-emcc` | `emcc` | Emscripten C compiler (WebAssembly) |
| `clang-tool-chain-empp` | `em++` | Emscripten C++ compiler (WebAssembly) |
| `clang-tool-chain-emar` | `emar` | Emscripten archiver (WebAssembly) |
| `clang-tool-chain-sccache-emcc` | `sccache` + `emcc` | Emscripten C compiler with sccache caching |
| `clang-tool-chain-sccache-empp` | `sccache` + `em++` | Emscripten C++ compiler with sccache caching |

### Cosmopolitan Libc (2 commands)

| Command | Tool | Description |
|---------|------|-------------|
| `clang-tool-chain-cosmocc` | `cosmocc` | Cosmopolitan C compiler (APE) |
| `clang-tool-chain-cosmocpp` | `cosmoc++` | Cosmopolitan C++ compiler (APE) |

## Command Summary by Category

- **Management & Utilities:** 4 commands
- **Clang/LLVM Compilers:** 4 commands
- **Build Utilities:** 3 commands
- **sccache Caching:** 5 commands
- **LLVM Binary Utilities:** 11 commands
- **Format & Lint:** 2 commands
- **IWYU Include Analyzer:** 3 commands
- **LLDB Debugger:** 2 commands
- **Emscripten WebAssembly:** 5 commands
- **Cosmopolitan Libc:** 2 commands

**Total:** 41 wrapper commands

## Feature Categories

### Developer Experience
- Zero-configuration setup
- Auto-download on first use
- Consistent interface across platforms
- Python integration
- Executable C++ scripts (shebang support)
- Inlined build directives

### Performance
- Ultra-compressed archives (94.3% reduction)
- Parallel downloads with HTTP range requests
- sccache compilation caching (2-10x faster rebuilds)
- Concurrent-safe installation
- SHA256-based build caching

### Security
- SHA256 checksum verification
- HTTPS-only downloads
- Python 3.12+ tarfile safety filters
- No privilege escalation needed

### Portability
- Cross-platform support (Windows, macOS, Linux)
- Multi-architecture support (x86_64, ARM64)
- Works offline after first download
- No admin rights required
- Reproducible builds

### Toolchain Completeness
- Full Clang/LLVM 21 toolchain
- Complete Emscripten/WebAssembly pipeline
- IWYU include analyzer
- clang-format and clang-tidy
- LLDB debugger with Python support
- Cosmopolitan Libc for APE binaries
- All LLVM binary utilities

## See Also

- [Installation Guide](INSTALLATION.md) - Setup and configuration
- [Management CLI](MANAGEMENT_CLI.md) - CLI commands and workflows
- [Architecture](ARCHITECTURE.md) - Technical design and implementation
- [All Tools Documentation](../README.md#-detailed-documentation) - Comprehensive tool-by-tool guides
