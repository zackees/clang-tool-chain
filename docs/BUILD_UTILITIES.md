# Build Utilities

Simple build tools for quick compilation and TDD workflows.

**3 commands • Caching support • Shebang support • Auto-run**

## Quick Examples

```bash
# Build and run in one step
clang-tool-chain-build-run hello.cpp

# Build and run with caching (faster iterations)
clang-tool-chain-build-run --cached hello.cpp

# Executable C++ scripts (Unix/Linux/macOS)
#!/usr/bin/env -S uvx clang-tool-chain-build-run --cached
#include <iostream>
int main() { std::cout << "Hello!\n"; }

chmod +x script.cpp && ./script.cpp
```

## Available Commands

| Command | Description | Key Feature |
|---------|-------------|-------------|
| `clang-tool-chain-build` | Build C/C++ files | Simple compilation wrapper |
| `clang-tool-chain-build-run` | Build and run executable | SHA256-based caching with `--cached` |
| `clang-tool-chain-run` | Run executable | Internal use by build-run |

## Key Features

- **SHA256-based Caching** - `--cached` flag skips recompilation if source unchanged
- **Shebang Support** - Make C++ files directly executable with `#!/usr/bin/env`
- **Zero-Install with uvx** - Scripts auto-install via `uvx` (only needs `pip install uv`)
- **Instant Iteration** - Perfect for TDD and quick prototyping

## Common Workflows

### TDD Workflow

```bash
# Write tests in test.cpp
clang-tool-chain-build-run --cached test.cpp
# Output: All tests passed! (compiles on first run)

# Edit test.cpp
clang-tool-chain-build-run --cached test.cpp
# Output: Compiling... All tests passed! (recompiles after changes)

# Run again without editing
clang-tool-chain-build-run --cached test.cpp
# Output: All tests passed! (instant - cached)
```

### Executable Scripts (Recommended - Zero Install)

```cpp
#!/usr/bin/env -S uvx clang-tool-chain-build-run --cached
#include <iostream>

int main() {
    std::cout << "Executable C++!" << std::endl;
    return 0;
}
```

```bash
chmod +x script.cpp
./script.cpp  # Auto-installs clang-tool-chain via uvx!
```

### Pass Arguments to Program

```bash
# Arguments after -- go to the program
clang-tool-chain-build-run hello.cpp -- arg1 arg2

# Combined with caching
clang-tool-chain-build-run --cached process.cpp -- input.txt
```

## Platform Support

| Platform | Shebang Support | Command |
|----------|----------------|---------|
| Linux    | ✅ Yes | `chmod +x script.cpp && ./script.cpp` |
| macOS    | ✅ Yes | `chmod +x script.cpp && ./script.cpp` |
| Windows (Git Bash) | ✅ Yes | `./script.cpp` |
| Windows (cmd/PowerShell) | ❌ No | `clang-tool-chain-build-run --cached script.cpp` |

## Caching Details

### How Caching Works

- **SHA256 hash** computed from source file content
- **Cache location**: `~/.clang-tool-chain/build_cache/`
- **Smart invalidation**: Automatically recompiles when source changes
- **No configuration** needed - just use `--cached` flag

### Cache Management

```bash
# Clear all cached executables
rm -rf ~/.clang-tool-chain/build_cache/

# Check cache size
du -sh ~/.clang-tool-chain/build_cache/
```

## Related Documentation

- [Executable C++ Scripts](EXECUTABLE_SCRIPTS.md) - Detailed shebang setup
- [Inlined Build Directives](DIRECTIVES.md) - Embed build config in source files
- [Clang/LLVM Toolchain](CLANG_LLVM.md) - Core compiler documentation
