# Callgrind (Call Graph Profiler)

<!-- AGENT: Read this file when working on callgrind profiling, performance analysis,
     or clang-tool-chain-callgrind command.
     Key topics: profiling, instruction counts, call graphs, KCachegrind.
     Related: docs/VALGRIND.md, docs/CLANG_LLVM.md. -->

Callgrind is a call-graph generating cache and branch-prediction profiler that ships with Valgrind. Unlike sampling profilers, callgrind uses **instrumentation** to count every instruction executed, producing deterministic results with no sampling noise.

`clang-tool-chain-callgrind` provides a dedicated CLI that runs callgrind inside a Docker container and auto-annotates the output for human-readable profiling reports.

## Quick Start

```bash
# Compile with debug symbols (on any platform)
clang-tool-chain-cpp program.cpp -g -O0 -o program

# Profile with callgrind (requires Docker)
clang-tool-chain-callgrind ./program

# Keep raw output for GUI tools (KCachegrind)
clang-tool-chain-callgrind --raw ./program
```

## Requirements

- **Docker** must be installed and running
  - Windows/macOS: [Docker Desktop](https://www.docker.com/products/docker-desktop)
  - Linux: `sudo apt install docker.io` (or equivalent)
- Program must be compiled for Linux (clang-tool-chain handles this)
- Compile with `-g` (debug symbols) for source-level annotation
- Compile with `-O0` for accurate line-level attribution (optimization moves code around)

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

1. **Compile**: Build your program with `clang-tool-chain-c` or `clang-tool-chain-cpp` using `-g -O0`
2. **Download**: On first use, clang-tool-chain downloads pre-built Valgrind binaries (~5 MB)
3. **Docker**: The compiled binary and Valgrind are mounted into an Ubuntu 22.04 Docker container
4. **Profile**: Callgrind instruments every instruction and records call graphs
5. **Annotate**: `callgrind_annotate` converts the raw output to a human-readable report
6. **Report**: The annotated output is printed to stdout (or written to a file with `-o`)

## Reading the Output

The annotated output shows instruction counts per function and per source line:

```
--------------------------------------------------------------------------------
Profile data file 'callgrind.out.1' (creator: callgrind-3.24.0)
--------------------------------------------------------------------------------
Ir
--------------------------------------------------------------------------------
10,030,015  PROGRAM TOTALS

--------------------------------------------------------------------------------
Ir            file:function
--------------------------------------------------------------------------------
10,000,000    program.cpp:hot_function(int) [/workdir/program]
    20,010    program.cpp:main [/workdir/program]
    10,005    ???:_start [/workdir/program]
```

**Key metrics:**

| Metric | Description |
|--------|-------------|
| **Ir** | Instruction references (number of instructions executed) |
| **Dr** | Data read references (with `--cache-sim=yes`) |
| **Dw** | Data write references (with `--cache-sim=yes`) |
| **Bc** | Conditional branches executed (with `--branch-sim=yes`) |
| **Bi** | Indirect branches executed (with `--branch-sim=yes`) |

The percentages show how much of total execution each function accounts for. Functions are sorted by cost (most expensive first).

## Common Options

### Callgrind-specific options

| Option | Description |
|--------|-------------|
| `--raw` | Keep raw `callgrind.out.*` file, skip auto-annotation |
| `--output FILE`, `-o FILE` | Write annotated output to file instead of stdout |
| `--threshold N` | Annotation threshold percentage (default: 95) |

### Valgrind passthrough options

All other `--` flags before the executable are passed through to Valgrind/callgrind:

| Option | Description |
|--------|-------------|
| `--callgrind-out-file=FILE` | Set output file name pattern |
| `--cache-sim=yes` | Enable cache simulation (adds Dr/Dw/D1mr/D1mw/DLmr/DLmw) |
| `--branch-sim=yes` | Enable branch prediction simulation (adds Bc/Bcm/Bi/Bim) |
| `--collect-jumps=yes` | Collect jump counts |
| `--separate-callers=N` | Separate context by N callers |
| `--separate-threads=yes` | Produce separate output per thread |

## Example: Finding Performance Bottlenecks

```cpp
// bottleneck.cpp
#include <cstdio>
#include <cmath>

// This function is intentionally slow
double slow_sum(const double* data, int n) {
    double total = 0;
    for (int i = 0; i < n; i++) {
        total += sqrt(data[i]) * log(data[i] + 1.0);
    }
    return total;
}

// This function is fast
double fast_sum(const double* data, int n) {
    double total = 0;
    for (int i = 0; i < n; i++) {
        total += data[i];
    }
    return total;
}

int main() {
    const int N = 100000;
    double data[N];
    for (int i = 0; i < N; i++) data[i] = i * 0.001;

    double a = slow_sum(data, N);  // ~99% of time
    double b = fast_sum(data, N);  // ~1% of time
    printf("Results: %f %f\n", a, b);
    return 0;
}
```

```bash
clang-tool-chain-cpp bottleneck.cpp -g -O0 -o bottleneck -lm
clang-tool-chain-callgrind ./bottleneck
```

The output will clearly show that `slow_sum` dominates execution time, making it the optimization target.

## Using with KCachegrind/QCachegrind

For interactive visualization of call graphs, use the `--raw` flag to preserve the `callgrind.out.*` file, then open it in a GUI tool:

```bash
# Generate raw callgrind output
clang-tool-chain-callgrind --raw ./program

# Open in KCachegrind (Linux) or QCachegrind (macOS/Windows)
kcachegrind callgrind.out.*
```

### Installing KCachegrind/QCachegrind

| Platform | Install Command |
|----------|----------------|
| Ubuntu/Debian | `sudo apt install kcachegrind` |
| Fedora | `sudo dnf install kcachegrind` |
| macOS (Homebrew) | `brew install qcachegrind` |
| Windows | Use [QCachegrind](https://sourceforge.net/projects/qcachegrindwin/) |

KCachegrind provides:
- Interactive call graph visualization
- Treemap view of function costs
- Source code annotation with instruction counts
- Caller/callee relationship browsing

## Using with Cosmopolitan (cosmocc)

Cosmocc produces APE (Actually Portable Executable) `.com` files that use an MZ header, not ELF. Valgrind cannot run APE binaries directly, but cosmocc also produces a `.dbg` sidecar file that works with callgrind.

**`clang-tool-chain-callgrind` handles this automatically.** When you pass a `.com` file, it detects the APE format and redirects to the `.dbg` sidecar.

```bash
# Compile with cosmocc (debug build produces .dbg sidecar)
clang-tool-chain-cosmocc -g -O0 program.c -o program.com

# Profile — auto-redirects to program.com.dbg
clang-tool-chain-callgrind ./program.com
```

**Note:** Cosmocc uses a custom malloc allocator, so heap-related metrics may not be accurate. Instruction counts and call graphs work normally.

## Comparison: Callgrind vs Cachegrind vs Massif

| Tool | Purpose | Metric | Best For |
|------|---------|--------|----------|
| **callgrind** | Call graph profiling | Instruction counts per function | Finding CPU hotspots, call chain analysis |
| **cachegrind** | Cache profiling | Cache hits/misses (L1, LL) | Optimizing memory access patterns |
| **massif** | Heap profiling | Heap memory over time | Finding memory bloat, peak usage |

All three can be used via `clang-tool-chain-valgrind --tool=<name>`, but `clang-tool-chain-callgrind` adds auto-annotation for callgrind specifically.

## Troubleshooting

### "Docker is required to run callgrind"

Callgrind is a Valgrind tool (Linux-only). clang-tool-chain uses Docker to run it on any platform.

**Solution:** Install Docker:
- Windows/macOS: Download [Docker Desktop](https://www.docker.com/products/docker-desktop)
- Linux: `sudo apt install docker.io && sudo usermod -aG docker $USER`

### No callgrind.out.* file produced

The program may have crashed before callgrind could write its output.

**Solution:** Ensure the program runs correctly without callgrind first:
```bash
./program  # Test it runs without crashing
clang-tool-chain-callgrind ./program
```

### Annotation shows no source lines

**Solution:** Compile with debug symbols:
```bash
clang-tool-chain-cpp program.cpp -g -O0 -o program
```

### Profiling is very slow

Callgrind instruments every instruction, so programs run 20-50x slower than normal. This is expected. For faster (but less accurate) profiling, consider sampling-based profilers like `perf`.

**Tips to reduce profiling time:**
- Use smaller input data sets
- Profile a representative subset of the workload
- Use `--collect-atstart=no` and `--toggle-collect=function_name` to profile only specific functions

### callgrind_annotate failed

If auto-annotation fails, the raw output file is preserved. You can:
1. View it with a GUI tool: `kcachegrind callgrind.out.*`
2. Manually annotate: `callgrind_annotate callgrind.out.*`
3. Use `--raw` to skip annotation entirely

## See Also

- [Valgrind (Memory Error Detector)](VALGRIND.md) - Memory leak detection and analysis
- [Clang/LLVM Toolchain](CLANG_LLVM.md) - Main compiler documentation
- [Cosmopolitan (cosmocc)](COSMOCC.md) - Actually Portable Executables
