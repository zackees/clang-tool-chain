# Quick Start Guide

Get started with `clang-tool-chain` in under 5 minutes!

## Installation

Install the package using pip:

```bash
pip install clang-tool-chain
```

Or install from source:

```bash
git clone https://github.com/zackees/clang-tool-chain.git
cd clang-tool-chain
pip install -e ".[dev]"
```

## First Steps

### 1. Verify Installation

Check that the package is installed correctly:

```bash
clang-tool-chain --version
```

This should display version information for the package.

### 2. View Available Tools

List all available Clang tools:

```bash
clang-tool-chain list-tools
```

You should see a list of available compiler and utility tools.

### 3. Check Tool Information

Get information about your platform and binary paths:

```bash
clang-tool-chain info
```

This shows:
- Your platform (Windows, macOS, or Linux)
- Architecture (x86_64 or ARM64)
- Binary directory path
- Available tools

## Your First Compilation

### Simple C Program

Create a simple C program:

```bash
# Create hello.c
cat > hello.c << 'EOF'
#include <stdio.h>

int main() {
    printf("Hello from Clang!\n");
    return 0;
}
EOF
```

Compile and run it:

```bash
# Compile
clang-tool-chain-c hello.c -o hello

# Run
./hello                    # On Linux/macOS
hello.exe                  # On Windows
```

Output: `Hello from Clang!`

### Simple C++ Program

Create a C++ program:

```bash
# Create hello.cpp
cat > hello.cpp << 'EOF'
#include <iostream>
#include <vector>

int main() {
    std::vector<std::string> greetings = {"Hello", "from", "Clang++!"};
    for (const auto& word : greetings) {
        std::cout << word << " ";
    }
    std::cout << std::endl;
    return 0;
}
EOF
```

Compile with C++17:

```bash
# Compile
clang-tool-chain-cpp -std=c++17 hello.cpp -o hello_cpp

# Run
./hello_cpp                # On Linux/macOS
hello_cpp.exe              # On Windows
```

Output: `Hello from Clang++!`

## Common Tasks

### Compile with Optimization

```bash
# Debug build
clang-tool-chain-c -g -O0 hello.c -o hello_debug

# Release build with optimization
clang-tool-chain-c -O3 hello.c -o hello_release
```

### Multi-File Compilation

Create a project with multiple files:

```bash
# math_lib.h
cat > math_lib.h << 'EOF'
#ifndef MATH_LIB_H
#define MATH_LIB_H

int add(int a, int b);
int multiply(int a, int b);

#endif
EOF

# math_lib.c
cat > math_lib.c << 'EOF'
#include "math_lib.h"

int add(int a, int b) {
    return a + b;
}

int multiply(int a, int b) {
    return a * b;
}
EOF

# main.c
cat > main.c << 'EOF'
#include <stdio.h>
#include "math_lib.h"

int main() {
    printf("2 + 3 = %d\n", add(2, 3));
    printf("2 * 3 = %d\n", multiply(2, 3));
    return 0;
}
EOF
```

Compile separately and link:

```bash
# Compile to object files
clang-tool-chain-c -c math_lib.c -o math_lib.o
clang-tool-chain-c -c main.c -o main.o

# Link
clang-tool-chain-c math_lib.o main.o -o calculator

# Run
./calculator               # On Linux/macOS
calculator.exe             # On Windows
```

Output:
```
2 + 3 = 5
2 * 3 = 6
```

### Create a Static Library

```bash
# Create object file
clang-tool-chain-c -c math_lib.c -o math_lib.o

# Create archive
clang-tool-chain-ar rcs libmath.a math_lib.o

# Link against the library
clang-tool-chain-c main.c -L. -lmath -o calculator

# Run
./calculator               # On Linux/macOS
calculator.exe             # On Windows
```

### Inspect Binaries

View symbols in an executable:

```bash
clang-tool-chain-nm calculator
```

Disassemble an executable:

```bash
clang-tool-chain-objdump -d calculator
```

Strip debug symbols:

```bash
clang-tool-chain-strip calculator
```

## Binary Management

### Download Pre-built Binaries

If you need to manually download the Clang binaries (usually done automatically):

```bash
python -m clang_tool_chain.downloads.download_binaries
```

This will download LLVM 21.1.5 binaries for your platform.

### Strip Binaries for Size

Reduce binary size by removing unnecessary files:

```bash
python -m clang_tool_chain.downloads.strip_binaries
```

This reduces the ~3.5 GB full installation to ~300-400 MB.

## Platform-Specific Notes

### Windows

- Executables have `.exe` extension
- Use `clang-tool-chain-c` (not just `clang`)
- MSVC runtime is bundled (no external dependencies)
- Both forward slashes (`/`) and backslashes (`\`) work in paths

### macOS

- Separate binaries for Intel (x86_64) and Apple Silicon (ARM64)
- The package automatically detects your architecture
- Code signing warnings are normal for downloaded binaries
- Use `./executable` to run compiled programs

### Linux

- Requires glibc (usually already installed)
- Use `./executable` to run compiled programs
- Works on x86_64 and ARM64 architectures
- Minimal dependencies required

## Troubleshooting

### "Command not found" Error

If you get a "command not found" error:

1. Make sure the package is installed: `pip list | grep clang-tool-chain`
2. Check your PATH includes pip's bin directory
3. Try using the full path: `python -m clang_tool_chain.wrapper <tool> <args>`

### "Binary not found" Error

If the tools can't find the Clang binaries:

1. Run `clang-tool-chain info` to check the binary directory
2. Download binaries: `python -m clang_tool_chain.downloads.download_binaries`
3. Strip binaries: `python -m clang_tool_chain.downloads.strip_binaries`
4. Check that `assets/<platform>/<arch>/bin/` exists

### Compilation Errors

If compilation fails:

1. Check that your C/C++ code is valid
2. Try adding `-v` flag for verbose output: `clang-tool-chain-c -v hello.c`
3. Check that all required headers and libraries are available
4. On Windows, ensure you have the Windows SDK installed for system headers

## Next Steps

Now that you've completed the quick start:

1. **Explore Examples**: Check out the `examples/` directory for more complex projects
2. **Read the Full Documentation**: See `README.md` for complete reference
3. **Customize Compilation**: Learn about optimization flags and compiler options
4. **Build Real Projects**: Use clang-tool-chain for your C/C++ projects

## Common Commands Reference

| Command | Purpose |
|---------|---------|
| `clang-tool-chain-c` | Compile C code |
| `clang-tool-chain-cpp` | Compile C++ code |
| `clang-tool-chain-ld` | Link object files |
| `clang-tool-chain-ar` | Create static libraries |
| `clang-tool-chain-nm` | View symbols |
| `clang-tool-chain-objdump` | Disassemble binaries |
| `clang-tool-chain-strip` | Remove debug symbols |
| `clang-tool-chain --version` | Show version |
| `clang-tool-chain list-tools` | List available tools |
| `clang-tool-chain info` | Show platform info |

## Getting Help

- **Documentation**: See `README.md` for complete documentation
- **Examples**: Check `examples/README.md` for tutorials
- **Issues**: Report bugs at https://github.com/zackees/clang-tool-chain/issues
- **Contributing**: See `CONTRIBUTING.md` for guidelines
- **Clang Documentation**: https://clang.llvm.org/docs/

## Compilation Flags Reference

### Common C Flags

```bash
-std=c11              # Use C11 standard
-std=c17              # Use C17 standard
-O0                   # No optimization (debug)
-O1                   # Basic optimization
-O2                   # Moderate optimization
-O3                   # Aggressive optimization
-g                    # Include debug info
-Wall                 # Enable all warnings
-Werror               # Treat warnings as errors
-I<path>              # Add include directory
-L<path>              # Add library directory
-l<name>              # Link library
-o <file>             # Output file name
-c                    # Compile only (no linking)
-v                    # Verbose output
```

### Common C++ Flags

```bash
-std=c++11            # Use C++11 standard
-std=c++14            # Use C++14 standard
-std=c++17            # Use C++17 standard
-std=c++20            # Use C++20 standard
-stdlib=libc++        # Use LLVM's libc++
-pthread              # Enable pthread support
```

## Example Workflow

Here's a complete workflow for a small project:

```bash
# 1. Create project directory
mkdir my_project
cd my_project

# 2. Create source files
echo '#include <stdio.h>' > main.c
echo 'int main() { printf("My Project\n"); return 0; }' >> main.c

# 3. Compile with debug info
clang-tool-chain-c -g -O0 -Wall main.c -o main_debug

# 4. Test the debug build
./main_debug

# 5. Compile optimized release build
clang-tool-chain-c -O3 main.c -o main_release

# 6. Strip debug symbols
clang-tool-chain-strip main_release

# 7. Verify the final binary
clang-tool-chain-nm main_release
```

## Tips and Best Practices

1. **Always use `-Wall`**: Enable all warnings to catch potential issues early
2. **Debug vs Release**: Use `-g -O0` for debugging, `-O3` for production
3. **Static Analysis**: Consider using `clang-tool-chain-format` for code formatting
4. **Version Control**: Don't commit compiled binaries (`.o`, `.a`, executables)
5. **Dependencies**: Document any external libraries your project needs
6. **Cross-Platform**: Test on all target platforms before release

## Success!

You're now ready to use `clang-tool-chain` for your C/C++ development. Happy coding!

For more advanced usage, refer to:
- `README.md` - Complete package documentation
- `examples/README.md` - Detailed examples and tutorials
- `CONTRIBUTING.md` - How to contribute to the project
- [Clang Documentation](https://clang.llvm.org/docs/) - Official Clang resources
