# Include What You Use (IWYU)

**A static analysis tool that detects unnecessary `#include` directives and suggests missing ones in C/C++ code.**

---

## Quick Start

```bash
# Install the package
pip install clang-tool-chain

# Analyze a source file
clang-tool-chain-iwyu myfile.cpp -- -std=c++17

# Automatically fix includes based on IWYU output
clang-tool-chain-iwyu myfile.cpp -- -std=c++17 | clang-tool-chain-fix-includes
```

IWYU downloads automatically (~53-57 MB) on first use.

---

## Available Commands

| Command | Tool | Description |
|---------|------|-------------|
| `clang-tool-chain-iwyu` | `include-what-you-use` | Analyze source files for include issues |
| `clang-tool-chain-iwyu-tool` | `iwyu_tool.py` | Batch analysis using compile_commands.json |
| `clang-tool-chain-fix-includes` | `fix_includes.py` | Automatically apply IWYU recommendations |

---

## Platform Support

| Platform | Architecture | Version | Status |
|----------|-------------|---------|--------|
| Windows  | x86_64      | 0.25    | Stable |
| Linux    | x86_64      | 0.25    | Stable |
| Linux    | ARM64       | 0.25    | Stable |
| macOS    | x86_64      | 0.25    | Stable |
| macOS    | ARM64       | 0.25    | Stable |

**Note:** IWYU is built against LLVM 21.x and requires approximately 53-57 MB download per platform.

---

## What IWYU Does

IWYU helps you maintain clean header dependencies by:

1. **Detecting unnecessary includes** - Headers that are included but never used
2. **Suggesting missing includes** - Headers that should be directly included
3. **Recommending forward declarations** - When a full include is overkill
4. **Enforcing IWYU policy** - "Include what you use, use what you include"

### Why This Matters

| Problem | Solution |
|---------|----------|
| Slow compilation | Removing unnecessary includes speeds up builds |
| Hidden dependencies | Makes header dependencies explicit |
| Fragile builds | Protects against "include-order" bugs |
| Large binaries | Reduces unnecessary symbol exposure |

---

## Basic Usage

### Analyzing a Single File

```bash
# Basic analysis
clang-tool-chain-iwyu main.cpp

# With C++ standard specified
clang-tool-chain-iwyu main.cpp -- -std=c++17

# With include paths
clang-tool-chain-iwyu main.cpp -- -I./include -I./vendor

# With defines
clang-tool-chain-iwyu main.cpp -- -DDEBUG -DPLATFORM_LINUX
```

**Note:** Arguments after `--` are passed to the Clang frontend.

### Understanding IWYU Output

IWYU outputs recommendations in a structured format:

```
myfile.cpp should add these lines:
#include <vector>                 // for vector
#include "myheader.h"             // for MyClass

myfile.cpp should remove these lines:
- #include <iostream>             // lines 3-3

The full include-list for myfile.cpp:
#include <vector>                 // for vector
#include "myheader.h"             // for MyClass
---
```

### Automatically Fixing Includes

```bash
# Pipe IWYU output to fix-includes
clang-tool-chain-iwyu myfile.cpp -- -std=c++17 | clang-tool-chain-fix-includes

# Or save output first for review
clang-tool-chain-iwyu myfile.cpp -- -std=c++17 > iwyu.out
cat iwyu.out                                    # Review recommendations
clang-tool-chain-fix-includes < iwyu.out       # Apply changes
```

---

## Project-Wide Analysis

### Using compile_commands.json

For CMake projects with a compilation database:

```bash
# Generate compile_commands.json (CMake)
cmake -B build -DCMAKE_EXPORT_COMPILE_COMMANDS=ON
cmake --build build

# Run IWYU on entire project
clang-tool-chain-iwyu-tool -p build/

# Run IWYU and automatically fix
clang-tool-chain-iwyu-tool -p build/ | clang-tool-chain-fix-includes
```

### Analyzing Specific Files

```bash
# Analyze specific file in project
clang-tool-chain-iwyu-tool -p build/ src/main.cpp

# Analyze files matching pattern
clang-tool-chain-iwyu-tool -p build/ -- src/*.cpp
```

---

## Common Options

### IWYU Options

| Option | Description |
|--------|-------------|
| `--no_comments` | Don't add "// for symbol" comments |
| `--no_fwd_decls` | Don't suggest forward declarations |
| `--transitive_includes_only` | Only report transitive includes |
| `--verbose=N` | Set verbosity level (0-7) |
| `--check_also=GLOB` | Also check files matching GLOB |

```bash
# Example with options
clang-tool-chain-iwyu --no_comments --verbose=1 main.cpp -- -std=c++17
```

### fix_includes Options

| Option | Description |
|--------|-------------|
| `--dry_run` | Show changes without applying |
| `--safe_headers` | Don't remove "safe" includes |
| `--reorder` | Reorder includes after fixing |
| `--nosafe_headers` | Remove all suggested includes |

```bash
# Preview changes without applying
clang-tool-chain-iwyu main.cpp -- | clang-tool-chain-fix-includes --dry_run

# Conservative mode - only add includes
clang-tool-chain-iwyu main.cpp -- | clang-tool-chain-fix-includes --safe_headers
```

---

## Mapping Files

IWYU uses mapping files to understand which headers provide which symbols.

### Built-in Mappings

IWYU includes mappings for:
- C standard library
- C++ standard library
- Common POSIX headers
- Platform-specific headers

### Custom Mapping Files

Create `.imp` files for project-specific mappings:

```
# myproject.imp
[
  # Map internal header to public API
  { "include": ["\"internal/impl.h\"", "private", "\"myproject/api.h\"", "public"] },

  # Map symbol to header
  { "symbol": ["MyClass", "private", "\"myproject/myclass.h\"", "public"] }
]
```

Use with:
```bash
clang-tool-chain-iwyu -Xiwyu --mapping_file=myproject.imp main.cpp --
```

---

## CI/CD Integration

### GitHub Actions

```yaml
name: IWYU Check

on: [push, pull_request]

jobs:
  iwyu:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3

      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.11'

      - name: Install clang-tool-chain
        run: pip install clang-tool-chain

      - name: Configure project
        run: cmake -B build -DCMAKE_EXPORT_COMPILE_COMMANDS=ON

      - name: Run IWYU
        run: |
          clang-tool-chain-iwyu-tool -p build/ > iwyu.out
          if grep -q "should add\|should remove" iwyu.out; then
            cat iwyu.out
            echo "::warning::IWYU found include issues"
          fi
```

### Pre-commit Hook

```yaml
# .pre-commit-config.yaml
repos:
  - repo: local
    hooks:
      - id: iwyu
        name: Include What You Use
        entry: bash -c 'clang-tool-chain-iwyu "$@" -- -std=c++17 2>&1 | grep -q "has correct" && exit 0 || exit 1' --
        language: system
        files: \.(cpp|cc|cxx|c)$
```

---

## Troubleshooting

### "fatal error: 'xxx.h' file not found"

**Problem:** IWYU can't find system or project headers.

**Solution:** Specify include paths:
```bash
clang-tool-chain-iwyu main.cpp -- -I./include -I/usr/local/include
```

### "unknown argument: '-xxx'"

**Problem:** IWYU doesn't recognize a compiler flag.

**Solution:** Use `-Xiwyu` to pass IWYU-specific flags:
```bash
clang-tool-chain-iwyu -Xiwyu --verbose=1 main.cpp --
```

### Different Results Than Expected

**Problem:** IWYU suggests changes that seem wrong.

**Solutions:**
1. Check if a custom mapping file is needed
2. Use `--verbose=3` to see IWYU's reasoning
3. Consider if a forward declaration is appropriate

### macOS: SDK Headers Not Found

**Problem:** Can't find system headers on macOS.

**Solution:** Ensure Xcode Command Line Tools are installed:
```bash
xcode-select --install
```

---

## Best Practices

### 1. Include What You Use

```cpp
// BAD: Relying on transitive includes
#include "database.h"  // Happens to include <vector>
std::vector<int> data; // Works by accident

// GOOD: Include what you use
#include <vector>       // Explicit dependency
#include "database.h"
std::vector<int> data;
```

### 2. Forward Declare When Possible

```cpp
// BAD: Full include for pointer/reference
#include "huge_class.h"
void process(HugeClass* obj);

// GOOD: Forward declaration
class HugeClass;
void process(HugeClass* obj);
```

### 3. Run IWYU Regularly

- Add to CI/CD pipeline
- Run before major refactors
- Use as code review checkpoint

---

## Environment Variables

| Variable | Description |
|----------|-------------|
| `IWYU_ROOT` | Override IWYU installation directory |
| `CLANG_TOOL_CHAIN_DOWNLOAD_PATH` | Override all toolchain installations |

---

## How IWYU Works

1. **Parses source code** using Clang's frontend
2. **Analyzes symbol usage** to determine what's actually needed
3. **Compares against includes** to find mismatches
4. **Generates recommendations** for additions and removals

IWYU follows the principle: *"If you use a symbol, include the header that defines it."*

---

## Comparison: Manual vs IWYU

| Approach | Pros | Cons |
|----------|------|------|
| **Manual review** | Full control, no tools needed | Tedious, error-prone |
| **IWYU** | Automated, consistent | May need mapping files |
| **Compiler warnings** | Built-in (`-Wunused-includes` in GCC) | Less comprehensive |

---

## Additional Resources

- [IWYU Official Documentation](https://include-what-you-use.org/)
- [IWYU GitHub Repository](https://github.com/include-what-you-use/include-what-you-use)
- [IWYU Mapping Files Guide](https://github.com/include-what-you-use/include-what-you-use/blob/master/docs/IWYUMappings.md)

---

## See Also

- [Clang/LLVM Toolchain](CLANG_LLVM.md) - Main compiler documentation
- [Contributing](CONTRIBUTING.md) - How to add new tools
- [Architecture](ARCHITECTURE.md) - Technical details

---

**Installation:** `pip install clang-tool-chain`
**First use download:** ~53-57 MB
**IWYU version:** 0.25 (based on LLVM 21.x)
