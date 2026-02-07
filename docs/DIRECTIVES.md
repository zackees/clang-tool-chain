# Inlined Build Directives

<!-- AGENT: Read this file when working on inlined build directives (@link, @std, @cflags,
     @ldflags, @include, @platform) or self-contained source file compilation.
     Key topics: directive parsing, CLANG_TOOL_CHAIN_NO_DIRECTIVES, platform-specific directives.
     Related: docs/CLANG_LLVM.md, docs/ENVIRONMENT_VARIABLES.md. -->

**Self-contained C/C++ source files with embedded build configuration.**

Inlined directives allow you to embed library dependencies, compiler flags, and other build settings directly in your source files. No more remembering complex command-line flags - the source file knows how to build itself.

## Quick Example

```cpp
// @link: pthread
// @std: c++17

#include <pthread.h>
#include <iostream>

void* thread_func(void* arg) {
    std::cout << "Hello from thread!" << std::endl;
    return nullptr;
}

int main() {
    pthread_t t;
    pthread_create(&t, nullptr, thread_func, nullptr);
    pthread_join(t, nullptr);
    return 0;
}
```

Compile without any extra flags:
```bash
clang-tool-chain-cpp pthread_hello.cpp -o pthread_hello
# Automatically adds -std=c++17 -lpthread
```

## Supported Commands

Directive parsing is integrated into these commands:

| Command | Description | Status |
|---------|-------------|--------|
| `clang-tool-chain-cpp` | C++ compiler | ✅ Supported |
| `clang-tool-chain-c` | C compiler | ✅ Supported |
| `clang-tool-chain-cpp-msvc` | C++ compiler (MSVC ABI) | ✅ Supported |
| `clang-tool-chain-c-msvc` | C compiler (MSVC ABI) | ✅ Supported |
| `clang-tool-chain-build` | Simple build utility | ✅ Supported |
| `clang-tool-chain-build-run` | Build and run | ✅ Supported |

## Directive Syntax

Directives use single-line comments with a special `@directive: value` format:

```cpp
// @directive: value
// @directive: [list, of, values]
```

### Location Rules

1. Directives **must appear at the top** of the file
2. Directives **must use single-line comment syntax** (`//`)
3. Parsing stops at the first non-directive, non-empty, non-comment line
4. Empty lines and regular comments between directives are allowed

### Example with Multiple Directives

```cpp
// @std: c++20
// @link: [pthread, m, dl]
// @cflags: -O2 -Wall -Wextra
// @include: /opt/mylib/include
//
// Multi-threaded math computation example

#include <pthread.h>
#include <cmath>
// ...
```

## Available Directives

### `@link` - Library Linking

Links libraries using `-l` flags.

```cpp
// @link: pthread                    // Single library -> -lpthread
// @link: [pthread, m, dl]           // Multiple libraries -> -lpthread -lm -ldl
// @link: /usr/local/lib/libfoo.a    // Absolute path (passed directly)
```

### `@cflags` - Compiler Flags

Adds flags to the compiler command.

```cpp
// @cflags: -Wall -Wextra            // Warning flags
// @cflags: -O2                      // Optimization level
// @cflags: -DDEBUG                  // Preprocessor definitions
// @cflags: -fno-exceptions          // Disable exceptions
```

### `@ldflags` - Linker Flags

Adds flags to the linker command.

```cpp
// @ldflags: -rpath /opt/lib         // Runtime library path
// @ldflags: -L/usr/local/lib        // Library search path
// @ldflags: -static                 // Static linking
```

### `@include` - Include Paths

Adds header search paths using `-I` flags.

```cpp
// @include: /usr/local/include      // Single path
// @include: [../common, ./vendor]   // Multiple paths
```

### `@std` - C/C++ Standard Version

Sets the language standard.

```cpp
// @std: c++20                       // C++20 standard
// @std: c++17                       // C++17 standard
// @std: c11                         // C11 standard
// @std: gnu++20                     // GNU C++20 extensions
```

### `@pkg-config` - pkg-config Integration (Planned)

Use pkg-config to get compiler/linker flags.

```cpp
// @pkg-config: openssl              // Single package
// @pkg-config: [openssl, libcurl]   // Multiple packages
```

*Note: pkg-config support is planned for a future release.*

### `@platform` - Platform-Specific Configuration

Apply directives only on specific platforms.

```cpp
// @std: c++17

// @platform: linux
//   @link: pthread
//   @link: dl

// @platform: windows
//   @link: ws2_32
//   @cflags: -D_WIN32_WINNT=0x0601

// @platform: darwin
//   @link: pthread
//   @ldflags: -framework CoreFoundation
```

**Supported platforms:**
- `linux` - Linux (all architectures)
- `windows` - Windows
- `darwin` - macOS
- `freebsd` - FreeBSD
- `openbsd` - OpenBSD
- `netbsd` - NetBSD

## Environment Variables

### `CLANG_TOOL_CHAIN_NO_DIRECTIVES`

Set to `1` to disable directive parsing entirely:

```bash
CLANG_TOOL_CHAIN_NO_DIRECTIVES=1 clang-tool-chain-cpp pthread_hello.cpp -o hello
# Directives will be ignored - must specify flags manually
```

### `CLANG_TOOL_CHAIN_DIRECTIVE_VERBOSE`

Set to `1` to see what directives are being applied:

```bash
CLANG_TOOL_CHAIN_DIRECTIVE_VERBOSE=1 clang-tool-chain-cpp pthread_hello.cpp -o hello
# Output: Directive args from source files: ['-std=c++17', '-lpthread']
```

## Complete Examples

### Example 1: Basic Threading

```cpp
// pthread_hello.cpp
// @link: pthread
// @std: c++17

#include <pthread.h>
#include <iostream>

void* say_hello(void* arg) {
    std::cout << "Hello from thread " << *(int*)arg << std::endl;
    return nullptr;
}

int main() {
    pthread_t threads[4];
    int ids[4] = {0, 1, 2, 3};

    for (int i = 0; i < 4; i++) {
        pthread_create(&threads[i], nullptr, say_hello, &ids[i]);
    }

    for (int i = 0; i < 4; i++) {
        pthread_join(threads[i], nullptr);
    }

    return 0;
}
```

```bash
clang-tool-chain-cpp pthread_hello.cpp -o pthread_hello
./pthread_hello
```

### Example 2: Cross-Platform Networking

```cpp
// network_example.cpp
// @std: c++17

// @platform: linux
//   @link: pthread

// @platform: windows
//   @link: ws2_32
//   @cflags: -D_WIN32_WINNT=0x0601

// @platform: darwin
//   @link: pthread

#include <iostream>

#ifdef _WIN32
#include <winsock2.h>
#pragma comment(lib, "ws2_32.lib")  // For MSVC (ignored by clang-tool-chain)
#else
#include <sys/socket.h>
#include <netinet/in.h>
#include <arpa/inet.h>
#include <unistd.h>
#endif

int main() {
#ifdef _WIN32
    WSADATA wsa;
    WSAStartup(MAKEWORD(2, 2), &wsa);
#endif

    std::cout << "Network example - platform-specific directives work!" << std::endl;

#ifdef _WIN32
    WSACleanup();
#endif
    return 0;
}
```

### Example 3: Optimized Math Computation

```cpp
// math_intensive.cpp
// @link: [pthread, m]
// @cflags: -O2 -march=native
// @std: c++17

#include <pthread.h>
#include <cmath>
#include <vector>
#include <iostream>
#include <numeric>

constexpr int NUM_THREADS = 4;
constexpr int DATA_SIZE = 1000000;

struct ThreadData {
    double* data;
    int start;
    int end;
    double result;
};

void* compute_sum(void* arg) {
    ThreadData* td = static_cast<ThreadData*>(arg);
    td->result = 0;
    for (int i = td->start; i < td->end; i++) {
        td->result += std::sin(td->data[i]) * std::cos(td->data[i]);
    }
    return nullptr;
}

int main() {
    std::vector<double> data(DATA_SIZE);
    std::iota(data.begin(), data.end(), 1.0);

    pthread_t threads[NUM_THREADS];
    ThreadData thread_data[NUM_THREADS];
    int chunk_size = DATA_SIZE / NUM_THREADS;

    for (int i = 0; i < NUM_THREADS; i++) {
        thread_data[i] = {data.data(), i * chunk_size, (i + 1) * chunk_size, 0};
        pthread_create(&threads[i], nullptr, compute_sum, &thread_data[i]);
    }

    double total = 0;
    for (int i = 0; i < NUM_THREADS; i++) {
        pthread_join(threads[i], nullptr);
        total += thread_data[i].result;
    }

    std::cout << "Computed sum: " << total << std::endl;
    return 0;
}
```

### Example 4: C Language

```c
// simple_c.c
// @cflags: -O2 -Wall

#include <stdio.h>

int main(void) {
    printf("Hello from C with directives!\n");
    return 0;
}
```

```bash
clang-tool-chain-c simple_c.c -o simple_c
./simple_c
```

## How It Works

When you run a command like `clang-tool-chain-cpp myfile.cpp -o myfile`:

1. **Source Detection**: The tool scans command-line arguments to find source files (`.cpp`, `.c`, `.cc`, `.cxx`, `.c++`, `.m`, `.mm`)

2. **Directive Parsing**: For each source file, the parser reads lines from the top of the file until it hits a non-directive, non-comment, non-empty line

3. **Platform Filtering**: Platform-specific directives (`@platform: linux`, etc.) are filtered to match the current platform

4. **Argument Generation**: Directives are converted to compiler arguments:
   - `@std: c++17` → `-std=c++17`
   - `@link: pthread` → `-lpthread`
   - `@cflags: -O2` → `-O2`
   - etc.

5. **Command Assembly**: The directive arguments are prepended to the user-supplied arguments and passed to the compiler

6. **Deduplication**: If the same directive appears in multiple source files, duplicate arguments are removed

## Best Practices

### 1. Put Directives at the Very Top

```cpp
// Good - directives at the top
// @link: pthread
// @std: c++17

#include <pthread.h>
```

```cpp
// Bad - directives after includes (won't be parsed)
#include <pthread.h>

// @link: pthread  // This will be ignored!
```

### 2. Use Platform Sections for Cross-Platform Code

```cpp
// @std: c++17

// @platform: linux
//   @link: pthread
// @platform: windows
//   @link: ws2_32
// @platform: darwin
//   @link: pthread

// Code works on all platforms!
```

### 3. Use List Syntax for Multiple Libraries

```cpp
// Good - compact
// @link: [pthread, m, dl]

// Also valid - one per line
// @link: pthread
// @link: m
// @link: dl
```

### 4. Use Verbose Mode for Debugging

```bash
CLANG_TOOL_CHAIN_DIRECTIVE_VERBOSE=1 clang-tool-chain-cpp myfile.cpp -o myfile
```

## Limitations

1. **Top-of-file only**: Directives must be at the very top of the file
2. **No conditional expressions yet**: `// @link: pthread | platform is linux` syntax is planned but not yet implemented
3. **pkg-config not yet implemented**: The `@pkg-config` directive is planned for a future release
4. **Single-file focus**: Directives are per-source-file; for multi-file projects, consider using a build system

## Troubleshooting

### Directives Not Being Applied

1. **Check placement**: Directives must be at the top of the file, before any code
2. **Check syntax**: Use `// @directive: value` format (note the space after `//`)
3. **Enable verbose mode**: `CLANG_TOOL_CHAIN_DIRECTIVE_VERBOSE=1`
4. **Check if disabled**: Ensure `CLANG_TOOL_CHAIN_NO_DIRECTIVES` is not set

### Platform Directives Not Working

1. **Check platform name**: Use `linux`, `windows`, `darwin` (not `macos`)
2. **Check indentation**: Platform-specific directives should be indented under `@platform:`

### Library Not Found

1. **Check library name**: Use the library name without `lib` prefix and file extension
2. **Check platform availability**: Some libraries are platform-specific (e.g., `ws2_32` is Windows-only)

## See Also

- [Examples](../examples/inlined_directives/) - Working example files
- [Original Proposal](./proposals/INLINED_DIRECTIVES.md) - Design document and rationale
- [Parser Implementation](../src/clang_tool_chain/directives/parser.py) - Source code
