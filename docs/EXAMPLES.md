# Examples

Practical code examples and compilation workflows.

## Hello World (C)

```c
// hello.c
#include <stdio.h>

int main() {
    printf("Hello from clang-tool-chain!\n");
    return 0;
}
```

```bash
clang-tool-chain-c hello.c -o hello
./hello
```

## Hello World (C++)

```cpp
// hello.cpp
#include <iostream>

int main() {
    std::cout << "Hello from clang-tool-chain!" << std::endl;
    return 0;
}
```

```bash
clang-tool-chain-cpp hello.cpp -o hello
./hello
```

## Multi-File Compilation

```c
// math_ops.h
#ifndef MATH_OPS_H
#define MATH_OPS_H
int add(int a, int b);
int multiply(int a, int b);
#endif

// math_ops.c
#include "math_ops.h"
int add(int a, int b) { return a + b; }
int multiply(int a, int b) { return a * b; }

// main.c
#include <stdio.h>
#include "math_ops.h"

int main() {
    printf("5 + 3 = %d\n", add(5, 3));
    printf("5 * 3 = %d\n", multiply(5, 3));
    return 0;
}
```

```bash
# Compile and link in one step
clang-tool-chain-c main.c math_ops.c -o program
./program

# Or compile separately then link
clang-tool-chain-c -c math_ops.c -o math_ops.o
clang-tool-chain-c -c main.c -o main.o
clang-tool-chain-c main.o math_ops.o -o program
./program
```

## Creating a Static Library

```bash
# Compile source files to object files
clang-tool-chain-c -c math_ops.c -o math_ops.o
clang-tool-chain-c -c string_ops.c -o string_ops.o

# Create static library
clang-tool-chain-ar rcs libmylib.a math_ops.o string_ops.o

# Generate archive index (optional but recommended)
clang-tool-chain-ranlib libmylib.a

# Link against the library
clang-tool-chain-c main.c -L. -lmylib -o program
./program
```

## Cross-Platform Build Script

```bash
#!/bin/bash
# build.sh - Cross-platform build script

set -e

# Compile
echo "Compiling..."
clang-tool-chain-c -O2 -Wall -Wextra src/*.c -o myprogram

# Strip symbols for release
echo "Stripping symbols..."
clang-tool-chain-strip myprogram -o myprogram.release

echo "Build complete: myprogram.release"
```

## CMake Integration

```cmake
# CMakeLists.txt
cmake_minimum_required(VERSION 3.15)
project(MyProject C CXX)

set(CMAKE_C_COMPILER clang-tool-chain-c)
set(CMAKE_CXX_COMPILER clang-tool-chain-cpp)

add_executable(myprogram
    src/main.cpp
    src/utils.cpp
)

target_compile_options(myprogram PRIVATE -Wall -Wextra -O2)
```

```bash
cmake -B build
cmake --build build
./build/myprogram
```

## WebAssembly Example

```c
// fibonacci.c
#include <stdio.h>
#include <emscripten.h>

EMSCRIPTEN_KEEPALIVE
int fibonacci(int n) {
    if (n <= 1) return n;
    return fibonacci(n - 1) + fibonacci(n - 2);
}

int main() {
    printf("Fibonacci(10) = %d\n", fibonacci(10));
    return 0;
}
```

```bash
# Compile to WebAssembly
clang-tool-chain-emcc fibonacci.c -o fibonacci.js

# Run with bundled Node.js
node fibonacci.js
# Output: Fibonacci(10) = 55
```

## Cosmopolitan (Actually Portable Executable)

```c
// hello_ape.c
#include <stdio.h>

int main() {
    printf("This binary runs on Windows, Linux, macOS, and BSD!\n");
    return 0;
}
```

```bash
# Build Actually Portable Executable
clang-tool-chain-cosmocc hello_ape.c -o hello.com

# Run on any platform
./hello.com  # Linux/macOS/FreeBSD/etc.
# On Windows: hello.com
```

## Executable C++ Script (Shebang)

```cpp
#!/usr/bin/env -S uvx clang-tool-chain-build-run --cached
#include <iostream>
#include <vector>
#include <numeric>

int main(int argc, char* argv[]) {
    if (argc < 2) {
        std::cerr << "Usage: " << argv[0] << " <numbers...>" << std::endl;
        return 1;
    }

    std::vector<int> numbers;
    for (int i = 1; i < argc; i++) {
        numbers.push_back(std::stoi(argv[i]));
    }

    int sum = std::accumulate(numbers.begin(), numbers.end(), 0);
    std::cout << "Sum: " << sum << std::endl;

    return 0;
}
```

```bash
chmod +x sum.cpp
./sum.cpp 1 2 3 4 5
# Output: Sum: 15
```

## Inlined Build Directives

```cpp
// pthread_example.cpp
// @link: pthread
// @std: c++17

#include <iostream>
#include <thread>
#include <vector>

void worker(int id) {
    std::cout << "Thread " << id << " working..." << std::endl;
}

int main() {
    std::vector<std::thread> threads;
    for (int i = 0; i < 4; i++) {
        threads.emplace_back(worker, i);
    }

    for (auto& t : threads) {
        t.join();
    }

    std::cout << "All threads completed!" << std::endl;
    return 0;
}
```

```bash
# Automatically links pthread and uses C++17
clang-tool-chain-cpp pthread_example.cpp -o pthread_example
./pthread_example
```

## Windows-Specific Example (MSVC ABI)

```cpp
// windows_specific.cpp
#include <windows.h>
#include <iostream>

int main() {
    DWORD version = GetVersion();
    std::cout << "Windows version: " << LOBYTE(LOWORD(version)) << "."
              << HIBYTE(LOWORD(version)) << std::endl;
    return 0;
}
```

```bash
# Windows only - use MSVC ABI for Windows APIs
clang-tool-chain-cpp-msvc windows_specific.cpp -o windows_specific.exe
.\windows_specific.exe
```

## Include What You Use (IWYU)

```cpp
// before_iwyu.cpp
#include <iostream>
#include <vector>
#include <string>
#include <algorithm>

int main() {
    std::cout << "Hello!" << std::endl;  // Only uses iostream
    return 0;
}
```

```bash
# Analyze includes
clang-tool-chain-iwyu before_iwyu.cpp

# Output suggests:
# - Remove <vector>, <string>, <algorithm>
# - Keep <iostream>
```

## Code Formatting and Linting

```cpp
// unformatted.cpp
#include <iostream>
int main(){std::cout<<"Hello!"<<std::endl;return 0;}
```

```bash
# Format code
clang-tool-chain-format -i unformatted.cpp

# Result:
# #include <iostream>
# int main() {
#   std::cout << "Hello!" << std::endl;
#   return 0;
# }

# Lint code
clang-tool-chain-tidy unformatted.cpp
```

## LLDB Debugging

```cpp
// crash.cpp
#include <iostream>

void buggy_function() {
    int* ptr = nullptr;
    *ptr = 42;  // Crash!
}

int main() {
    std::cout << "About to crash..." << std::endl;
    buggy_function();
    return 0;
}
```

```bash
# Compile with debug symbols
clang-tool-chain-cpp -g crash.cpp -o crash

# Debug crash
clang-tool-chain-lldb crash
# (lldb) run
# (lldb) bt  # Backtrace shows crash location
```

## sccache Integration

```bash
# Install sccache
pip install clang-tool-chain[sccache]

# First build (cache miss)
clang-tool-chain-sccache-cpp large_project.cpp -o program
# Time: 10 seconds

# Rebuild (cache hit)
clang-tool-chain-sccache-cpp large_project.cpp -o program
# Time: <1 second

# Check statistics
clang-tool-chain-sccache --show-stats
```

## Binary Utilities

```bash
# Create object file
clang-tool-chain-c -c main.c -o main.o

# List symbols
clang-tool-chain-nm main.o

# Disassemble
clang-tool-chain-objdump -d main.o

# Show file info
clang-tool-chain-readelf -h main.o

# Strip symbols
clang-tool-chain-strip program -o program.stripped
```

## Platform-Specific Directives

```cpp
// cross_platform.cpp
// @std: c++17

// @platform: linux
//   @link: pthread
//   @link: rt

// @platform: windows
//   @link: ws2_32

// @platform: darwin
//   @link: pthread

#include <iostream>

int main() {
    std::cout << "Cross-platform build!" << std::endl;
    return 0;
}
```

```bash
# Automatically adapts to current platform
clang-tool-chain-cpp cross_platform.cpp -o cross_platform
```

## Advanced CMake with clang-tool-chain

```cmake
# CMakeLists.txt
cmake_minimum_required(VERSION 3.20)
project(AdvancedProject C CXX)

# Use clang-tool-chain compilers
set(CMAKE_C_COMPILER clang-tool-chain-c)
set(CMAKE_CXX_COMPILER clang-tool-chain-cpp)

# Use clang-tool-chain binary utilities
set(CMAKE_AR clang-tool-chain-ar)
set(CMAKE_RANLIB clang-tool-chain-ranlib)
set(CMAKE_STRIP clang-tool-chain-strip)

# Optional: Use sccache for faster rebuilds
set(CMAKE_C_COMPILER_LAUNCHER clang-tool-chain-sccache)
set(CMAKE_CXX_COMPILER_LAUNCHER clang-tool-chain-sccache)

add_executable(myapp src/main.cpp src/utils.cpp)
target_compile_features(myapp PRIVATE cxx_std_17)
target_compile_options(myapp PRIVATE -Wall -Wextra -O2)
```

## TDD Workflow with Executable Scripts

```cpp
#!/usr/bin/env -S uvx clang-tool-chain-build-run --cached
// tests.cpp
#include <cassert>
#include <iostream>
#include <string>

// Code under test
std::string reverse(const std::string& s) {
    return std::string(s.rbegin(), s.rend());
}

int main() {
    // Tests
    assert(reverse("hello") == "olleh");
    assert(reverse("") == "");
    assert(reverse("a") == "a");
    assert(reverse("racecar") == "racecar");

    std::cout << "✓ All tests passed!" << std::endl;
    return 0;
}
```

```bash
chmod +x tests.cpp

# Edit code, run tests - instant feedback!
./tests.cpp
```

## Related Documentation

- [Clang/LLVM Toolchain](CLANG_LLVM.md) - Compiler commands
- [Build Utilities](BUILD_UTILITIES.md) - Build and run tools
- [Executable Scripts](EXECUTABLE_SCRIPTS.md) - Shebang support
- [Inlined Build Directives](DIRECTIVES.md) - Embed build config
- [CI/CD Integration](CICD_INTEGRATION.md) - Automation examples
