# Executable C++ Scripts (Shebang Support)

Run C++ files directly like shell scripts!

**Zero-install • Instant iteration • Native performance • Cross-platform**

## Quick Start

Create an executable C++ file:

```cpp
#!/usr/bin/env -S uvx clang-tool-chain-build-run --cached
#include <iostream>

int main() {
    std::cout << "Hello from executable C++!" << std::endl;
    return 0;
}
```

Make it executable and run:

```bash
# Linux/macOS
chmod +x script.cpp
./script.cpp

# Windows (Git Bash)
./script.cpp
```

**That's it!** The first run auto-installs clang-tool-chain via `uvx` and compiles the code. Subsequent runs use the cached binary (thanks to `--cached`).

**Requirements:** Just `uvx` in PATH (install once: `pip install uv`)

## Why This Is Incredible

- **Scripting with C++ performance** - Write quick scripts that run at native speed
- **No build system needed** - Single-file programs just work
- **Instant iteration** - `--cached` flag skips recompilation when source hasn't changed
- **TDD in C++** - Write inline tests with assertions, run with `./test.cpp`
- **Zero installation** - `uvx` auto-installs clang-tool-chain (only needs `pip install uv`)
- **Cross-platform** - Same shebang works on Linux, macOS, and Windows (Git Bash)

## How It Works

### The Shebang Line

```cpp
#!/usr/bin/env -S uvx clang-tool-chain-build-run --cached
```

Breaking it down:
- `#!/usr/bin/env -S` - Shell shebang with `-S` flag to pass multiple arguments
- `uvx` - Package runner from `uv` (auto-installs packages in isolated environments)
- `clang-tool-chain-build-run` - Our build-and-run command
- `--cached` - SHA256-based caching (skips recompilation if source unchanged)

### Execution Flow

1. **First run**: `uvx` checks if `clang-tool-chain` is installed
   - Not found → Downloads and installs to isolated cache
   - Found → Uses cached version
2. **Build step**: `clang-tool-chain-build-run` compiles your C++ file
   - Computes SHA256 hash of source
   - Checks cache (`~/.clang-tool-chain/build_cache/`)
   - Cache miss → Compiles executable
   - Cache hit → Skips compilation
3. **Run step**: Executes the binary

**Subsequent runs** (no source changes):
- `uvx` uses cached package (instant)
- Build step skips compilation (cached binary)
- Total overhead: <100ms

## Example: Inline Tests

```cpp
#!/usr/bin/env -S uvx clang-tool-chain-build-run --cached
#include <iostream>
#include <cassert>
#include <vector>

template<typename T>
T sum(const std::vector<T>& v) {
    T result = T{};
    for (const auto& x : v) result += x;
    return result;
}

int main() {
    // Inline tests - will abort if any assertion fails
    assert(sum(std::vector<int>{1, 2, 3, 4, 5}) == 15);
    assert(sum(std::vector<double>{1.5, 2.5}) == 4.0);
    assert(sum(std::vector<int>{}) == 0);

    std::cout << "All tests passed!" << std::endl;
    return 0;
}
```

```bash
chmod +x test.cpp && ./test.cpp
# Output: All tests passed!
```

## Zero-Install with uvx (Recommended)

### Why uvx?

**Old way** (requires manual setup):
```cpp
#!/usr/bin/env -S clang-tool-chain-build-run --cached
# Requires: pip install clang-tool-chain
```

**New way** (zero setup):
```cpp
#!/usr/bin/env -S uvx clang-tool-chain-build-run --cached
# Only requires: pip install uv
```

**Benefits:**
- ✅ **Zero manual installation** - `uvx` automatically installs `clang-tool-chain` if not cached
- ✅ **Works anywhere** - No need to be in a project directory
- ✅ **Only dependency** - Just needs `uvx` in PATH (from `pip install uv`)
- ✅ **Fast subsequent runs** - Package cached after first use
- ✅ **Truly portable** - Share scripts with anyone who has `uvx`

### Install uvx Once

```bash
pip install uv  # Installs both uv and uvx
```

That's all you need!

## Platform Notes

| Platform | How to Run | Shebang Support |
|----------|------------|----------------|
| **Linux** | `chmod +x script.cpp && ./script.cpp` | ✅ Yes |
| **macOS** | `chmod +x script.cpp && ./script.cpp` | ✅ Yes |
| **Windows (Git Bash)** | `./script.cpp` | ✅ Yes |
| **Windows (cmd/PowerShell)** | `clang-tool-chain-build-run --cached script.cpp` | ❌ No |

**Windows Notes:**
- Shebang only works in Git Bash / MSYS2 / WSL
- cmd.exe and PowerShell don't support shebang
- Solution: Use full command or Git Bash

## Common Workflows

### Quick Script

```cpp
#!/usr/bin/env -S uvx clang-tool-chain-build-run --cached
#include <iostream>
#include <string>

int main(int argc, char* argv[]) {
    if (argc < 2) {
        std::cerr << "Usage: " << argv[0] << " <name>" << std::endl;
        return 1;
    }
    std::cout << "Hello, " << argv[1] << "!" << std::endl;
    return 0;
}
```

```bash
chmod +x greet.cpp
./greet.cpp World
# Output: Hello, World!
```

### File Processing

```cpp
#!/usr/bin/env -S uvx clang-tool-chain-build-run --cached
#include <iostream>
#include <fstream>
#include <string>

int main(int argc, char* argv[]) {
    if (argc < 2) {
        std::cerr << "Usage: " << argv[0] << " <file>" << std::endl;
        return 1;
    }

    std::ifstream file(argv[1]);
    if (!file) {
        std::cerr << "Error opening file: " << argv[1] << std::endl;
        return 1;
    }

    std::string line;
    int count = 0;
    while (std::getline(file, line)) {
        count++;
    }

    std::cout << "Lines: " << count << std::endl;
    return 0;
}
```

```bash
chmod +x linecount.cpp
./linecount.cpp README.md
# Output: Lines: 427
```

### TDD Workflow

```cpp
#!/usr/bin/env -S uvx clang-tool-chain-build-run --cached
#include <iostream>
#include <cassert>

int fibonacci(int n) {
    if (n <= 1) return n;
    return fibonacci(n - 1) + fibonacci(n - 2);
}

int main() {
    // Tests
    assert(fibonacci(0) == 0);
    assert(fibonacci(1) == 1);
    assert(fibonacci(5) == 5);
    assert(fibonacci(10) == 55);

    std::cout << "✓ All tests passed!" << std::endl;
    return 0;
}
```

Edit, save, run - instant feedback loop!

## Advanced: Passing Arguments

### To Your Program

```bash
# Arguments after script are passed to main()
./script.cpp arg1 arg2 arg3

# Or explicitly with --
./script.cpp -- arg1 arg2
```

### To the Compiler

You can't pass compiler flags directly in the shebang, but you can use [Inlined Build Directives](DIRECTIVES.md):

```cpp
#!/usr/bin/env -S uvx clang-tool-chain-build-run --cached
// @link: pthread
// @std: c++17
// @cflags: -O2 -Wall

#include <iostream>
#include <thread>

int main() {
    std::thread t([]{ std::cout << "Hello from thread!\n"; });
    t.join();
    return 0;
}
```

The `@link`, `@std`, and `@cflags` directives are automatically parsed and applied!

## Comparison with Shell Scripts

| Feature | Shell Script | C++ Executable Script |
|---------|-------------|----------------------|
| **Syntax** | Shell | C++ |
| **Performance** | Interpreted | Native (compiled once) |
| **Type safety** | ❌ No | ✅ Yes |
| **IDE support** | Limited | Full (LSP, IntelliSense) |
| **Standard library** | Shell utils | C++ STL |
| **First run** | Instant | ~1-2 seconds (compile) |
| **Subsequent runs** | Instant | Instant (cached) |
| **Portability** | Shell-specific | Cross-platform C++ |

## Troubleshooting

### "Permission denied" on Linux/macOS

```bash
chmod +x script.cpp
```

### Shebang not working on Windows

Use Git Bash, MSYS2, or WSL. cmd.exe and PowerShell don't support shebangs.

Alternative:
```cmd
clang-tool-chain-build-run --cached script.cpp
```

### Cache not updating after edit

The cache is based on SHA256 hash - it should auto-update. If not:
```bash
# Clear cache
rm -rf ~/.clang-tool-chain/build_cache/

# Or rebuild explicitly
clang-tool-chain-build-run script.cpp  # Force rebuild (no --cached)
```

### uvx not found

```bash
pip install uv  # Installs both uv and uvx
```

## Related Documentation

- [Build Utilities](BUILD_UTILITIES.md) - Details on build-run command
- [Inlined Build Directives](DIRECTIVES.md) - Embed compiler flags in source
- [Examples](EXAMPLES.md) - More code examples
