# Valgrind (Memory Error Detector)

<!-- AGENT: Read this file when working on Valgrind memory analysis, leak detection,
     or clang-tool-chain-valgrind command.
     Key topics: memory leaks, uninitialized values, Docker execution, valgrind flags.
     Related: docs/CLANG_LLVM.md, docs/TESTING.md. -->

Valgrind is a dynamic analysis tool for detecting memory errors, leaks, and other issues in C/C++ programs. Since Valgrind is Linux-only, clang-tool-chain runs it inside a Docker container so it works from any host platform (Windows, macOS, Linux).

## Quick Start

```bash
# Compile with debug symbols (on any platform)
clang-tool-chain-cpp program.cpp -g -O0 -o program

# Run with Valgrind (requires Docker)
clang-tool-chain-valgrind --leak-check=full ./program
```

## Requirements

- **Docker** must be installed and running
  - Windows/macOS: [Docker Desktop](https://www.docker.com/products/docker-desktop)
  - Linux: `sudo apt install docker.io` (or equivalent)
- Program must be compiled for Linux (clang-tool-chain handles cross-compilation)

## Platform Support

| Host Platform | Architecture | Status |
|---------------|-------------|--------|
| Windows       | x86_64      | Supported (via Docker) |
| Linux         | x86_64      | Supported (via Docker) |
| Linux         | arm64       | Supported (via Docker) |
| macOS         | x86_64      | Supported (via Docker) |
| macOS         | arm64       | Supported (via Docker) |

**Note:** The executable being analyzed must be a Linux ELF binary. Compile with `clang-tool-chain-cpp` targeting Linux.

## How It Works

1. **Compile**: You compile your program using `clang-tool-chain-c` or `clang-tool-chain-cpp` with `-g` (debug symbols) and `-O0` (no optimization)
2. **Download**: On first use, clang-tool-chain downloads pre-built Valgrind binaries (~5 MB compressed)
3. **Docker**: The compiled binary and Valgrind installation are mounted into an Ubuntu 22.04 Docker container
4. **Analysis**: Valgrind runs your program inside the container and reports any memory errors

## Common Options

| Option | Description |
|--------|-------------|
| `--leak-check=full` | Show detailed leak information |
| `--track-origins=yes` | Track origins of uninitialized values |
| `--show-reachable=yes` | Show reachable blocks in leak check |
| `--error-exitcode=1` | Exit with code 1 if errors found (useful for CI) |
| `--tool=memcheck` | Memory error detector (default) |
| `--tool=cachegrind` | Cache profiler |
| `--tool=callgrind` | Call graph profiler |
| `--tool=helgrind` | Thread error detector |
| `--tool=drd` | Thread error detector (alternative) |
| `--tool=massif` | Heap profiler |

## Usage Examples

### Detecting Memory Leaks

```cpp
// leak_test.cpp
#include <cstdlib>
#include <cstdio>

int main() {
    int* p = (int*)malloc(100 * sizeof(int));
    p[0] = 42;
    printf("Allocated %d\n", p[0]);
    // BUG: forgot to free(p)
    return 0;
}
```

```bash
clang-tool-chain-cpp leak_test.cpp -g -O0 -o leak_test
clang-tool-chain-valgrind --leak-check=full ./leak_test
```

**Expected output:**
```
==1== HEAP SUMMARY:
==1==     in use at exit: 400 bytes in 1 blocks
==1==   total heap usage: 2 allocs, 1 frees, 1,424 bytes allocated
==1==
==1== 400 bytes in 1 blocks are definitely lost in loss record 1 of 1
==1==    at 0x...: malloc (...)
==1==    by 0x...: main (leak_test.cpp:5)
```

### Detecting Use of Uninitialized Values

```cpp
// uninit_test.cpp
#include <cstdlib>
#include <cstdio>

int main() {
    int* p = (int*)malloc(sizeof(int));
    // BUG: reading *p without initializing it
    if (*p > 0) {
        printf("positive\n");
    }
    free(p);
    return 0;
}
```

```bash
clang-tool-chain-cpp uninit_test.cpp -g -O0 -o uninit_test
clang-tool-chain-valgrind --track-origins=yes ./uninit_test
```

### Using in CI/CD

```bash
# Compile and test with Valgrind, fail if any errors
clang-tool-chain-cpp program.cpp -g -O0 -o program
clang-tool-chain-valgrind --leak-check=full --error-exitcode=1 ./program
```

The `--error-exitcode=1` flag causes Valgrind to return exit code 1 if any memory errors are found, making it suitable for CI pipelines.

## Troubleshooting

### "Docker is required to run Valgrind"

Valgrind is a Linux-only tool. clang-tool-chain uses Docker to run it on any platform.

**Solution:** Install Docker:
- Windows/macOS: Download [Docker Desktop](https://www.docker.com/products/docker-desktop)
- Linux: `sudo apt install docker.io && sudo usermod -aG docker $USER`

### "Executable not found"

**Solution:** Ensure the executable path is correct and the file exists:
```bash
ls -la ./program  # Verify the file exists
clang-tool-chain-valgrind ./program
```

### Valgrind reports no errors but program crashes

**Solution:** Compile with debug symbols and no optimization:
```bash
# Wrong: no debug info, optimization enabled
clang-tool-chain-cpp program.cpp -O2 -o program

# Right: debug symbols, no optimization
clang-tool-chain-cpp program.cpp -g -O0 -o program
```

### Docker permission denied

**Solution:** Add your user to the docker group:
```bash
sudo usermod -aG docker $USER
# Log out and log back in
```

## Architecture

### Installation Directory

```
~/.clang-tool-chain/valgrind/linux/{arch}/
├── bin/
│   ├── valgrind            # Main Valgrind executable
│   ├── vgdb                # Valgrind GDB server
│   └── valgrind-listener   # Valgrind listener
├── lib/
│   └── valgrind/           # Valgrind tool plugins
│       ├── memcheck-amd64-linux
│       ├── cachegrind-amd64-linux
│       ├── callgrind-amd64-linux
│       ├── helgrind-amd64-linux
│       ├── drd-amd64-linux
│       ├── massif-amd64-linux
│       └── ...
└── libexec/
    └── valgrind/           # Valgrind helper executables
```

### Docker Execution Flow

```
Host (any platform)          Docker Container (Ubuntu 22.04)
┌─────────────────┐         ┌─────────────────────────────┐
│ clang-tool-chain │         │                             │
│ -valgrind        │ ──────> │ /opt/valgrind/bin/valgrind  │
│                  │         │   └── /workdir/program      │
│ Mounts:          │         │                             │
│  - valgrind/     │ ──ro──> │ /opt/valgrind/              │
│  - program dir/  │ ──rw──> │ /workdir/                   │
└─────────────────┘         └─────────────────────────────┘
```

## See Also

- [Clang/LLVM Toolchain](CLANG_LLVM.md) - Main compiler documentation
- [LLDB Debugger](LLDB.md) - Interactive debugger
- [Testing Guide](TESTING.md) - Testing infrastructure
