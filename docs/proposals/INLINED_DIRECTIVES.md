# Inlined Build Directives for Single-File C++ Programs

## Overview

This proposal defines a standard syntax for embedding build metadata directly in C++ source files, enabling single-file programs to be self-contained and self-describing. This is analogous to hashbangs in scripting languages but extends to include library dependencies, linker flags, and build configuration.

## Motivation

Consider a simple pthread example:
```cpp
// Currently requires external build configuration
#include <pthread.h>
int main() { /* uses pthreads */ }
// Must compile with: clang++ -lpthread main.cpp
```

With inlined directives:
```cpp
// @link: pthread
#include <pthread.h>
int main() { /* uses pthreads */ }
// Tool reads directive and adds -lpthread automatically
```

## Directive Syntax

### General Format
```
// @directive: value
// @directive: key=value
// @directive: [list, of, values]
```

### Location Rules
1. Directives MUST appear at the top of the file
2. Directives MUST use single-line comment syntax (`//`)
3. Directives end when a non-directive non-empty line is encountered
4. Empty lines and regular comments between directives are allowed

### Core Directives

#### `@link` - Library Linking
```cpp
// @link: pthread                    // Links -lpthread
// @link: [pthread, m, dl]           // Links multiple libraries
// @link: /usr/local/lib/libfoo.a    // Absolute path to library
```

#### `@cflags` - Compiler Flags
```cpp
// @cflags: -Wall -Wextra            // Warning flags
// @cflags: -O2                      // Optimization level
// @cflags: -DDEBUG                  // Preprocessor definitions
```

#### `@ldflags` - Linker Flags
```cpp
// @ldflags: -rpath /opt/lib         // Runtime library path
// @ldflags: -L/usr/local/lib        // Library search path
```

#### `@include` - Include Paths
```cpp
// @include: /usr/local/include      // Add include path
// @include: [../common, ./vendor]   // Multiple paths
```

#### `@pkg-config` - pkg-config Integration
```cpp
// @pkg-config: openssl              // Use pkg-config for flags
// @pkg-config: [openssl, libcurl]   // Multiple packages
```

#### `@require` - Package Requirements (Future)
```cpp
// @require: fmt>=9.0                // Version constraints
// @require: nlohmann_json           // Latest version
// @require: boost/system            // Specific subpackage
```

#### `@platform` - Platform-Specific Configuration
```cpp
// @platform: linux
//   @link: pthread
// @platform: windows
//   @link: ws2_32
// @platform: darwin
//   @ldflags: -framework CoreFoundation
```

#### `@std` - C++ Standard Version
```cpp
// @std: c++20                       // Use C++20
// @std: c++17                       // Use C++17
```

### Advanced Features

#### Conditional Expressions
Following FastLED's @filter pattern:
```cpp
// @link: pthread | (platform is linux) or (platform is darwin)
// @link: ws2_32 | platform is windows
```

#### Comments Within Directives
```cpp
// @link: pthread  // Required for threading support
// @cflags: -O3    // Production optimization
```

## Complete Examples

### Example 1: pthread Hello World
```cpp
// @link: pthread
// @std: c++17
//
// Simple pthread example with embedded build directives

#include <pthread.h>
#include <stdio.h>

void* thread_func(void* arg) {
    printf("Hello from thread!\n");
    return nullptr;
}

int main() {
    pthread_t thread;
    pthread_create(&thread, nullptr, thread_func, nullptr);
    pthread_join(thread, nullptr);
    return 0;
}
```

### Example 2: Cross-Platform Networking
```cpp
// @std: c++17
// @platform: linux
//   @link: pthread
// @platform: windows
//   @link: ws2_32
//   @cflags: -D_WIN32_WINNT=0x0601
// @platform: darwin
//   @link: pthread
//
// Cross-platform networking example

#include <iostream>
#ifdef _WIN32
#include <winsock2.h>
#else
#include <sys/socket.h>
#include <netinet/in.h>
#endif

int main() {
    // Network code here
    return 0;
}
```

### Example 3: OpenSSL with pkg-config
```cpp
// @pkg-config: openssl
// @std: c++17
//
// SSL/TLS example using OpenSSL

#include <openssl/ssl.h>
#include <openssl/err.h>

int main() {
    SSL_library_init();
    SSL_CTX* ctx = SSL_CTX_new(TLS_client_method());
    // ... SSL code
    SSL_CTX_free(ctx);
    return 0;
}
```

### Example 4: Math and Threading
```cpp
// @link: [pthread, m]
// @cflags: -O2 -march=native
// @std: c++20
//
// High-performance parallel computation

#include <pthread.h>
#include <cmath>
#include <vector>
#include <numeric>

int main() {
    std::vector<double> data(1000000);
    std::iota(data.begin(), data.end(), 1.0);

    // Parallel computation using pthreads
    double sum = 0;
    for (auto& x : data) {
        sum += std::sin(x);
    }
    return 0;
}
```

## Parsing Specification

### Regular Expression Pattern
```regex
^//\s*@(\w+):\s*(.+?)\s*(//.*)?$
```

Captures:
1. Directive name (e.g., `link`, `cflags`)
2. Value (e.g., `pthread`, `[pthread, m]`)
3. Optional trailing comment

### Parsing Algorithm
```python
def parse_directives(source_code: str) -> dict:
    directives = {}
    current_platform = None

    for line in source_code.splitlines():
        line = line.strip()

        # Stop at first non-directive non-empty line
        if line and not line.startswith('//'):
            break

        # Skip empty lines and regular comments
        if not line or (line.startswith('//') and '@' not in line):
            continue

        # Parse directive
        match = re.match(r'^//\s*@(\w+):\s*(.+?)(\s*//.*)?$', line)
        if match:
            name, value = match.group(1), match.group(2).strip()

            # Handle platform nesting
            if name == 'platform':
                current_platform = value
            else:
                key = f"{current_platform}:{name}" if current_platform else name
                directives[key] = parse_value(value)

    return directives

def parse_value(value: str):
    # Handle list syntax: [a, b, c]
    if value.startswith('[') and value.endswith(']'):
        return [v.strip() for v in value[1:-1].split(',')]
    # Handle conditional: value | condition
    if ' | ' in value:
        val, cond = value.split(' | ', 1)
        return {'value': val.strip(), 'condition': cond.strip()}
    return value
```

## Tool Integration

### clang-tool-chain Integration
```bash
# Reads directives and compiles automatically
clang-tool-chain-cpp pthread_example.cpp -o pthread_example

# Verbose mode shows parsed directives
clang-tool-chain-cpp -v pthread_example.cpp -o pthread_example
# Output:
# Parsed directives:
#   @link: pthread
#   @std: c++17
# Effective command: clang++ -std=c++17 -lpthread pthread_example.cpp -o pthread_example
```

### Direct Execution (Future)
```bash
# Make the file executable with a hashbang-like runner
#!/usr/bin/env clang-tool-chain-run
// @link: pthread
// ... rest of C++ code ...
```

## Compatibility Notes

1. **Backwards Compatible**: Standard C++ comments, existing tools ignore them
2. **IDE Friendly**: No special syntax highlighting needed
3. **Doxygen Compatible**: Does not conflict with `/// @param` style docs
4. **Build System Agnostic**: Can be implemented by any build tool

## Future Extensions

1. **Conan/vcpkg Integration**: `@conan: fmt/9.1.0`
2. **CMake Export**: Generate CMakeLists.txt from directives
3. **Dependency Resolution**: Automatic transitive dependency handling
4. **Remote Dependencies**: `@url: https://example.com/lib.h`
5. **Checksum Verification**: `@sha256: abc123...`

## Reference

This design is inspired by:
- FastLED's `@filter` directive system
- Python's `__future__` imports
- Rust's `#![feature(...)]` attributes
- JavaScript's pragma directives
- Shell hashbangs (`#!/bin/bash`)
