# macOS Dylib Deployment Research

**Research conducted:** January 25, 2026

This document provides comprehensive research on macOS shared library (dylib) deployment patterns, best practices, and implementation recommendations for the clang-tool-chain project.

## Table of Contents

1. [Dependency Detection](#dependency-detection)
2. [Path Resolution](#path-resolution)
3. [install_name_tool Usage](#install_name_tool-usage)
4. [Deployment Strategies](#deployment-strategies)
5. [Best Practices](#best-practices)
6. [libunwind on macOS](#libunwind-on-macos)
7. [Code Signing Considerations](#code-signing-considerations)
8. [Security Considerations](#security-considerations)
9. [Recommendations for Implementation](#recommendations-for-implementation)
10. [Sources](#sources)

---

## Dependency Detection

### Using `otool -L`

The primary tool for detecting dylib dependencies on macOS is `otool -L`:

```bash
otool -L /path/to/binary
```

**Output format:**
- **First line:** The library's own install name (LC_ID_DYLIB)
- **Subsequent lines:** Install names of all imported libraries

**Example:**
```bash
$ otool -L my_program
my_program:
    @rpath/libfoo.dylib (compatibility version 1.0.0, current version 1.2.3)
    /usr/lib/libSystem.B.dylib (compatibility version 1.0.0, current version 1311.0.0)
```

### Important Caveats

1. **Dynamic Library Cache**: Modern macOS versions use a dynamic library cache (`dyld_shared_cache`), which complicates dependency inspection for system libraries. For cached libraries, you may need the [dyld-shared-cache-extractor](https://github.com/keith/dyld-shared-cache-extractor).

2. **First Line is NOT a Dependency**: The first line output by `otool -L` shows the library's own install name (LC_ID_DYLIB), not a dependency. This is crucial when parsing output.

3. **Viewing Library ID Only**: To see just the library's identification:
   ```bash
   otool -l libWaffle.dylib | grep -A 2 LC_ID_DYLIB
   ```

### Alternative Tools

**For recursive dependency analysis:**

- [dylibtree](https://github.com/keith/dylibtree) - Recursively inspect dynamic dependencies of Mach-O binaries
- [ldd-apple](https://github.com/tetractius/ldd-apple) - A more ldd-like tool for macOS
- [macdylibbundler](https://github.com/auriamg/macdylibbundler) - Automatically bundles dependencies and fixes paths

---

## Path Resolution

macOS's dynamic linker (dyld) uses three special path variables for runtime library resolution:

### `@executable_path`

**Definition:** Replaced with the full path to the directory containing the process's main executable.

**Use case:** Ideal for frameworks embedded inside applications, allowing libraries to reference locations relative to the application's executable.

**Example:**
```
@executable_path/../Frameworks/libfoo.dylib
```
For an app at `/Applications/MyApp.app/Contents/MacOS/MyApp`, this resolves to `/Applications/MyApp.app/Contents/Frameworks/libfoo.dylib`.

**Limitation:** All references are relative to the main executable, not the loading library.

### `@loader_path`

**Definition:** Replaced with the full path to the directory containing the Mach-O binary that contains the load command.

**Use case:** More flexible than `@executable_path` for frameworks or plugins that embed other frameworks. References are relative to the *loading* library, not the main executable.

**Example:**
```
@loader_path/libbar.dylib
```

**Key difference:** For executables, `@loader_path` and `@executable_path` are identical. For frameworks loading other frameworks, `@loader_path` is relative to the framework, making it relocatable.

### `@rpath`

**Definition:** Stands for "Runpath search path". The dynamic linker searches a list of rpath directories specified in LC_RPATH load commands.

**Use case:** Provides maximum flexibility - multiple search paths can be specified, allowing the same library to be found in different locations depending on context.

**How it works:**
1. When dyld loads a Mach-O image, it scans for LC_RPATH load commands
2. Each LC_RPATH adds a directory to the rpath list
3. When loading a library with `@rpath/libfoo.dylib`, dyld searches each rpath directory in order

**Example:**
```
# Library install name:
@rpath/libfoo.dylib

# Executable rpaths (can have multiple):
@executable_path/Frameworks
@executable_path/../lib
/usr/local/lib
```

**Advantages:**
- One library can be used in multiple contexts without modification
- Prioritized search (first match wins)
- Each application can specify its own search paths via LC_RPATH

**View rpaths:**
```bash
otool -l my_program | grep -A 2 LC_RPATH
```

---

## install_name_tool Usage

`install_name_tool` is the primary utility for modifying dylib paths after building. However, it should be used judiciously.

### Common Commands

**1. Change a library dependency path:**
```bash
install_name_tool -change /old/path/to/lib.dylib @rpath/lib.dylib /path/to/binary
```

**2. Change a library's install name (LC_ID_DYLIB):**
```bash
install_name_tool -id @rpath/lib.dylib /path/to/lib.dylib
```

**3. Add an rpath:**
```bash
install_name_tool -add_rpath @executable_path/../Frameworks /path/to/binary
```

**4. Delete an rpath:**
```bash
install_name_tool -delete_rpath /old/rpath /path/to/binary
```

**5. Change an rpath:**
```bash
install_name_tool -rpath /old/rpath /new/rpath /path/to/binary
```

### Best Practices for install_name_tool

1. **Set at Build Time, Not Runtime**: It's best to set correct install names during compilation using linker flags:
   ```bash
   # Set library install name at build time
   clang -dynamiclib -o libfoo.dylib foo.o -install_name @rpath/libfoo.dylib

   # Add rpath to executable at build time
   clang -o program main.o -Wl,-rpath,@executable_path/../Frameworks
   ```

2. **Verify Changes with otool**: Always verify modifications:
   ```bash
   install_name_tool -change /old/lib.dylib @rpath/lib.dylib binary
   otool -L binary  # Verify the change was applied
   ```

3. **Avoid Absolute Paths**: Never use absolute paths like `/usr/local/lib/libfoo.dylib` for distributed applications. Use `@rpath`, `@loader_path`, or `@executable_path` for portability.

4. **Use @loader_path for Relative Paths**: When libraries need to find dependencies relative to their own location:
   ```bash
   install_name_tool -change libbar.dylib @loader_path/libbar.dylib libfoo.dylib
   ```

5. **Code Signing Warning**: Modifying binaries with `install_name_tool` invalidates code signatures. You must re-sign after modifications:
   ```bash
   install_name_tool -change old new binary
   codesign -s - binary  # Ad-hoc signing
   ```

---

## Deployment Strategies

### 1. Manual Bundling

**Steps:**
1. Create a `Frameworks` directory in the app bundle:
   ```
   MyApp.app/
     Contents/
       MacOS/
         MyApp
       Frameworks/
         libfoo.dylib
         libbar.dylib
   ```

2. Copy dylibs to the Frameworks directory:
   ```bash
   cp /path/to/libfoo.dylib MyApp.app/Contents/Frameworks/
   ```

3. Fix library paths:
   ```bash
   # Fix executable references
   install_name_tool -change /usr/local/lib/libfoo.dylib @executable_path/../Frameworks/libfoo.dylib MyApp.app/Contents/MacOS/MyApp

   # Fix library's own install name
   install_name_tool -id @rpath/libfoo.dylib MyApp.app/Contents/Frameworks/libfoo.dylib

   # Fix inter-library dependencies
   install_name_tool -change /usr/local/lib/libbar.dylib @loader_path/libbar.dylib MyApp.app/Contents/Frameworks/libfoo.dylib
   ```

4. Add rpath to executable (optional if using @executable_path):
   ```bash
   install_name_tool -add_rpath @executable_path/../Frameworks MyApp.app/Contents/MacOS/MyApp
   ```

### 2. Using dylibbundler

[dylibbundler](https://github.com/auriamg/macdylibbundler) automates the entire process:

```bash
dylibbundler -od -b -x MyApp.app/Contents/MacOS/MyApp -d MyApp.app/Contents/Frameworks/
```

**What it does:**
- Determines which dylibs are needed
- Copies libraries into the app bundle
- Fixes all paths using `install_name_tool`
- Handles transitive dependencies recursively

**Default locations:**
- Libraries: `@executable_path/../libs/` (default) or `@executable_path/../Frameworks/` (with `-b` flag)

### 3. Using @rpath at Build Time

**Most modern and flexible approach:**

1. **Build libraries with @rpath install names:**
   ```bash
   clang -dynamiclib -o libfoo.dylib foo.o -install_name @rpath/libfoo.dylib
   ```

2. **Link executables with appropriate rpaths:**
   ```bash
   clang -o program main.o -lfoo -L./libs -Wl,-rpath,@executable_path/libs -Wl,-rpath,/usr/local/lib
   ```

3. **Benefits:**
   - No post-processing needed
   - Multiple search locations (prioritized)
   - Same library can be used in different contexts
   - Application-specific configuration

4. **Multiple rpaths for flexibility:**
   ```bash
   # Add multiple search paths (first match wins)
   -Wl,-rpath,@executable_path/../Frameworks  # Check app bundle first
   -Wl,-rpath,@loader_path                    # Check alongside loading binary
   -Wl,-rpath,/usr/local/lib                  # Fall back to system location
   ```

### 4. Standard Bundle Structure

**Qt-style deployment (widely adopted):**
```
MyApp.app/
  Contents/
    Info.plist
    MacOS/
      MyApp
    Frameworks/
      QtCore.framework/
      QtGui.framework/
      libcustom.dylib
    Resources/
      icon.icns
```

**Key points:**
- Frameworks go in `Contents/Frameworks/`
- Dylibs can also go in `Contents/Frameworks/`
- Use `@executable_path/../Frameworks` for references
- Ensures application uses bundled versions even if system versions exist

---

## Best Practices

### 1. Prefer @rpath for Modern Applications

**Rationale:**
- Maximum flexibility
- Multiple search paths
- Application-specific configuration
- No post-processing needed

**Implementation:**
```bash
# Library build
clang -dynamiclib -o libfoo.dylib foo.o -install_name @rpath/libfoo.dylib

# Executable build
clang -o app main.o -lfoo -L./libs -Wl,-rpath,@executable_path/libs
```

### 2. Use @loader_path for Inter-Library Dependencies

**When:** A library depends on another library in the same directory.

**Why:** Makes libraries relocatable - they can find each other regardless of where they're installed.

**Example:**
```bash
# libfoo.dylib depends on libbar.dylib (both in same directory)
install_name_tool -change libbar.dylib @loader_path/libbar.dylib libfoo.dylib
```

### 3. Use @executable_path for App Bundles

**When:** Distributing an application with bundled frameworks.

**Why:** Simple, reliable, widely used pattern.

**Structure:**
```
@executable_path/../Frameworks/libfoo.dylib
```

### 4. Set Install Names at Build Time

**Best practice:** Configure linker flags during compilation rather than post-processing:

```bash
# CMake example
set_target_properties(foo PROPERTIES
    INSTALL_NAME_DIR "@rpath"
    BUILD_WITH_INSTALL_RPATH TRUE
)

# Xcode: Set "Dynamic Library Install Name" to @rpath/$(EXECUTABLE_PATH)
```

### 5. Avoid Absolute Paths

**Never:**
```bash
/usr/local/lib/libfoo.dylib          # Breaks if library moves
/Users/me/project/lib/libfoo.dylib   # User-specific path
```

**Always:**
```bash
@rpath/libfoo.dylib                  # Flexible, relocatable
@loader_path/libfoo.dylib            # Relative to loading binary
@executable_path/../lib/libfoo.dylib # Relative to app
```

### 6. Combine Multiple Strategies

**Hybrid approach for maximum compatibility:**
```bash
# Library with @rpath install name
-install_name @rpath/libfoo.dylib

# Executable with multiple rpaths (prioritized)
-Wl,-rpath,@executable_path/../Frameworks  # Check app bundle first
-Wl,-rpath,@loader_path                    # Check alongside binary
-Wl,-rpath,/usr/local/lib                  # Fall back to system
```

### 7. Minimize Dependencies on Non-System Libraries

**Guideline:** Depend on system libraries when possible:
- `/usr/lib/libSystem.B.dylib` - Always available
- `/System/Library/Frameworks/` - Apple frameworks

**Avoid depending on:**
- `/usr/local/lib/` libraries (Homebrew, MacPorts) - not present on all systems
- Third-party libraries without bundling them

### 8. Test on Clean Systems

**Critical:** Test deployments on systems without development tools installed:
- No Xcode
- No Homebrew/MacPorts
- No `/usr/local/lib/` dependencies

**Tool:** Use a clean VM or container for testing.

---

## libunwind on macOS

### System libunwind

**Location:** Integrated into `libSystem.B.dylib` (Apple's standard C library)

**Path:** `/usr/lib/libSystem.B.dylib`

**Key points:**
- **Built-in:** Part of every macOS installation
- **No explicit linking needed:** Automatically linked with every program
- **Headers:** Available in Xcode SDK at `/usr/include/libunwind.h`
- **No separate .dylib:** Functionality is part of libSystem

**Usage:**
```c
#include <libunwind.h>
// No explicit -lunwind needed - part of libSystem
```

### Third-Party libunwind (LLVM/Custom Builds)

**Installation paths (Homebrew/MacPorts/source builds):**
- Libraries: `/usr/local/lib/libunwind.dylib` (default prefix)
- Headers: `/usr/local/include/libunwind.h`

**Building from source (LLVM libunwind):**
```bash
cmake -DCMAKE_INSTALL_PREFIX=/usr/local ..
make install
# Installs to /usr/local/lib/libunwind.a (static)
# Installs to /usr/local/lib/libunwind.dylib (if shared)
```

### Deployment Considerations

1. **System libunwind (recommended):**
   - Always available
   - No deployment needed
   - Automatically linked
   - Well-tested and optimized

2. **Custom libunwind:**
   - May be needed for newer features
   - Must be bundled or installed separately
   - Requires explicit linking: `-lunwind`
   - Path management required (rpath/install_name)

3. **Code Signing:**
   - System libSystem.dylib is signed by Apple
   - Custom libunwind builds need signing for distribution
   - Use `codesign -s - libunwind.dylib` for ad-hoc signing

**Recommendation for clang-tool-chain:**
- Prefer system libunwind for macOS (built into libSystem)
- Only bundle custom libunwind if specific LLVM features are required
- If bundling, use `@rpath/libunwind.dylib` with Frameworks directory

---

## Code Signing Considerations

### Overview

Code signing is **mandatory** for macOS applications distributed outside the Mac App Store (notarization requirement) and **strongly recommended** for all distributed software.

### Basic Code Signing Requirements

**Sign all binaries:**
```bash
# Ad-hoc signing (for testing)
codesign -s - MyApp.app

# Developer ID signing (for distribution)
codesign -s "Developer ID Application: Your Name" MyApp.app
```

**Sign nested code:**
Code signatures record nested code including frameworks, dylibs, helper tools, apps, and plug-ins by recording their code signatures for verification.

**Signing order (important):**
1. Sign dylibs first (innermost code)
2. Sign frameworks next
3. Sign main executable last (outermost code)

```bash
# Correct order
codesign -s - MyApp.app/Contents/Frameworks/libfoo.dylib
codesign -s - MyApp.app/Contents/Frameworks/QtCore.framework
codesign -s - MyApp.app
```

### Hardened Runtime

**What it is:** Security feature (introduced macOS 10.14 Mojave) that protects runtime integrity by preventing:
- Code injection
- Dynamic library hijacking
- Process memory tampering

**Enable hardened runtime:**
```bash
codesign -s - -o runtime MyApp.app
```

**Required for notarization:** Apps submitted to Apple's notary service must use hardened runtime.

### Library Validation

**What it is:** A hardened runtime feature that restricts which libraries can be loaded.

**Restriction:** Only allows loading:
- Libraries signed by Apple
- Libraries signed with the same Team ID as the main executable

**Enable (automatic with hardened runtime):**
```bash
codesign -s "Developer ID" -o runtime MyApp.app
```

**Disable (if needed for third-party plugins):**
Add entitlement: `com.apple.security.cs.disable-library-validation`

**Security trade-off:** Disabling library validation weakens security but may be necessary for plugin architectures.

### Hardened Runtime Restrictions

**1. Library Loading:**
- Unsigned dylibs cannot load into hardened processes
- Dylibs must be at least ad-hoc signed (`codesign -s -`)
- With library validation, dylibs must have matching Team IDs

**2. File System Paths:**
- File system relative paths are restricted
- `@executable_path` works but is restricted on Apple Silicon
- Prefer `@rpath` for modern applications

**3. SDK Requirements:**
- Code must be built with macOS 10.9 SDK or later
- Old SDKs or unknown SDK versions are rejected

### Code Signing After Modifications

**Problem:** `install_name_tool` invalidates code signatures.

**Solution:** Re-sign after modifications:
```bash
# Modify paths
install_name_tool -change old new MyApp

# Re-sign (invalidated signature)
codesign -s - MyApp  # Ad-hoc signing for testing
```

**For distribution:**
```bash
codesign -s "Developer ID Application: Your Name" -o runtime MyApp
```

### Entitlements

**Common entitlements for dylib loading:**

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "...">
<plist version="1.0">
<dict>
    <!-- Disable library validation (if needed for plugins) -->
    <key>com.apple.security.cs.disable-library-validation</key>
    <true/>

    <!-- Allow unsigned executable memory (if using JIT) -->
    <key>com.apple.security.cs.allow-unsigned-executable-memory</key>
    <true/>
</dict>
</plist>
```

**Apply entitlements:**
```bash
codesign -s "Developer ID" -o runtime --entitlements app.entitlements MyApp.app
```

### Verification

**Check signature:**
```bash
codesign -dv --verbose=4 MyApp.app
```

**Check hardened runtime:**
```bash
codesign -d --entitlements - MyApp.app
```

**Verify signature:**
```bash
codesign --verify --verbose=4 MyApp.app
```

### References

- [Technical Note TN2206: macOS Code Signing In Depth](https://developer.apple.com/library/archive/technotes/tn2206/_index.html)
- [Configuring the Hardened Runtime](https://developer.apple.com/documentation/xcode/configuring-the-hardened-runtime)

---

## Security Considerations

### Dylib Hijacking

**What it is:** An attack where malicious dylibs replace legitimate ones, allowing arbitrary code execution with the application's privileges.

**Attack vector:** When an application cannot find a dylib in the specified path, an attacker with write access can place a malicious dylib at that location.

**Consequences:**
- Privilege escalation
- Arbitrary code execution
- Data exfiltration
- System compromise

### Apple's Defense Mechanisms

**1. System Integrity Protection (SIP)**
- Protects system directories (`/System`, `/usr`, `/bin`, `/sbin`)
- Prevents modification even by root
- Introduced in macOS 10.11 (El Capitan)

**2. Hardened Runtime**
- Prevents code injection
- Restricts dylib loading
- Prevents memory tampering
- Required for notarization

**3. Library Validation**
- Only allows loading dylibs signed by Apple or same Team ID
- Prevents unsigned/differently-signed dylib injection
- Part of hardened runtime

**4. Code Signing (AMFI)**
- Apple Mobile File Integrity (AMFI) verifies signatures
- Checks that code hasn't been tampered with
- Validates signing identity

### macOS Security Model

**Key protections:**
- macOS never searches `$PATH` for libraries (unlike Linux `LD_LIBRARY_PATH`)
- Most system locations are only writable as root
- SIP prevents tampering with system libraries
- Gatekeeper blocks unsigned applications

**However:** Dylib hijacking is still possible in certain scenarios:
- Applications loading dylibs from writable locations
- Weak file permissions on bundled dylibs
- `@rpath` vulnerabilities (if rpath includes writable directories)

### Best Practices for Security

**1. Use Absolute Paths for Critical Libraries**

For security-critical libraries, consider absolute system paths:
```bash
/usr/lib/libSystem.B.dylib  # Protected by SIP
```

**2. Avoid Writable Directories in @rpath**

**Bad:**
```bash
-Wl,-rpath,/tmp                 # Attacker can write here
-Wl,-rpath,$HOME/.local/lib     # User-writable
```

**Good:**
```bash
-Wl,-rpath,@executable_path/../Frameworks  # App bundle (code signed)
-Wl,-rpath,/usr/lib                        # Protected by SIP
```

**3. Enable Hardened Runtime and Library Validation**

```bash
codesign -s "Developer ID" -o runtime MyApp.app
```

This enables library validation automatically.

**4. Sign All Bundled Dylibs**

```bash
# Sign all dylibs with same Team ID
find MyApp.app -name "*.dylib" -exec codesign -s "Developer ID" {} \;
```

**5. Set Restrictive File Permissions**

```bash
# App bundle should not be world-writable
chmod -R go-w MyApp.app
```

**6. Validate Library Paths**

Before shipping, verify no writable paths:
```bash
otool -L MyApp | grep -v "/usr/lib" | grep -v "/System"
# Inspect any non-system paths
```

**7. Avoid `dlopen()` with Relative Paths**

**Bad:**
```c
dlopen("libfoo.dylib", RTLD_NOW);  // Searches multiple paths
```

**Good:**
```c
dlopen("@rpath/libfoo.dylib", RTLD_NOW);  // Explicit path
// Or absolute:
dlopen("/Applications/MyApp.app/Contents/Frameworks/libfoo.dylib", RTLD_NOW);
```

**8. Monitor for Hijacking Attempts**

Apple's tools can detect hijacking vulnerabilities:
- Xcode's "Validate App" feature
- `dyld` warnings in Console.app
- Third-party tools: [dylib-hijacking-toolkit](https://github.com/UnsaltedHash42/dylib-hijacking-toolkit)

### Code Signing and Gatekeeper

**Gatekeeper restrictions:**
- Apps with `@rpath` or absolute paths to non-bundled dylibs are **rejected**
- Exception: System libraries are allowed
- `dlopen()` loads are not checked by Gatekeeper (less secure)

**For distribution:**
1. Bundle all non-system dylibs
2. Use `@rpath` with app bundle Frameworks directory
3. Sign everything with same Team ID
4. Enable hardened runtime
5. Notarize with Apple

### Detection Tools

**Check for hijackable dylibs:**
```bash
# Install dylib hijacking toolkit
git clone https://github.com/UnsaltedHash42/dylib-hijacking-toolkit
./dylib_hijack_scanner.py /path/to/MyApp.app
```

**Console warnings:**
```bash
# Check Console.app for dyld warnings:
log show --predicate 'process == "MyApp"' --info --debug | grep dyld
```

---

## Recommendations for Implementation

Based on this research, here are specific recommendations for implementing dylib deployment in clang-tool-chain (similar to Windows DLL deployment):

### 1. Use `otool -L` for Dependency Detection

**Implementation:**
```python
def detect_dylib_dependencies(binary_path: str) -> list[str]:
    """Detect dylib dependencies using otool -L."""
    result = subprocess.run(
        ["otool", "-L", binary_path],
        capture_output=True,
        text=True,
        check=True
    )

    lines = result.stdout.strip().split('\n')
    # Skip first line (binary's own install name)
    deps = []
    for line in lines[1:]:
        # Parse: "\t/path/to/lib.dylib (compatibility version X, current version Y)"
        lib_path = line.strip().split(' ')[0]
        deps.append(lib_path)

    return deps
```

**Key considerations:**
- Skip first line (LC_ID_DYLIB, not a dependency)
- Parse format: `\tpath (compatibility ..., current ...)`
- Handle both absolute and @rpath/@loader_path/@executable_path paths

### 2. Filter for Bundleable Libraries

**Logic:**
```python
def should_bundle_dylib(lib_path: str) -> bool:
    """Determine if a dylib should be bundled."""
    # Never bundle system libraries
    if lib_path.startswith("/usr/lib/"):
        return False
    if lib_path.startswith("/System/Library/"):
        return False
    if "libSystem" in lib_path:
        return False

    # Bundle these:
    # - @rpath/... (need to resolve)
    # - @loader_path/... (relative to loading binary)
    # - @executable_path/... (if outside system paths)
    # - /usr/local/lib/... (Homebrew/custom installs)

    if lib_path.startswith("@rpath"):
        return True  # Needs rpath resolution
    if lib_path.startswith("@loader_path"):
        return True
    if lib_path.startswith("/usr/local/"):
        return True
    if lib_path.startswith("/opt/"):
        return True

    return False
```

### 3. Deployment Strategy: Use install_name_tool

**Approach:**
1. Detect dependencies with `otool -L`
2. Copy non-system dylibs to output directory (same as executable)
3. Use `install_name_tool` to fix paths to `@loader_path/libfoo.dylib`

**Why @loader_path:**
- Simple: Dylibs in same directory as executable
- No app bundle required
- Works for command-line tools
- Makes binaries relocatable

**Implementation:**
```python
def deploy_dylib(binary_path: str, dylib_path: str, output_dir: str):
    """Copy dylib and fix paths."""
    dylib_name = os.path.basename(dylib_path)
    dest_path = os.path.join(output_dir, dylib_name)

    # Copy dylib
    shutil.copy2(dylib_path, dest_path)

    # Fix binary's reference to use @loader_path
    subprocess.run([
        "install_name_tool",
        "-change", dylib_path,
        f"@loader_path/{dylib_name}",
        binary_path
    ], check=True)

    # Fix dylib's install name
    subprocess.run([
        "install_name_tool",
        "-id", f"@loader_path/{dylib_name}",
        dest_path
    ], check=True)

    # Fix inter-dylib dependencies recursively
    fix_dylib_dependencies(dest_path, output_dir)
```

### 4. Handle Transitive Dependencies

**Recursive approach:**
```python
def fix_dylib_dependencies(dylib_path: str, output_dir: str):
    """Fix dependencies of a bundled dylib."""
    deps = detect_dylib_dependencies(dylib_path)

    for dep in deps:
        if should_bundle_dylib(dep):
            dep_name = os.path.basename(dep)

            # Fix reference to use @loader_path
            subprocess.run([
                "install_name_tool",
                "-change", dep,
                f"@loader_path/{dep_name}",
                dylib_path
            ], check=True)
```

### 5. Code Signing After Modifications

**Critical step:**
```python
def resign_binary(binary_path: str):
    """Re-sign binary after install_name_tool modifications."""
    try:
        subprocess.run([
            "codesign",
            "-s", "-",  # Ad-hoc signature
            "--force",  # Replace existing signature
            binary_path
        ], check=True)
    except subprocess.CalledProcessError:
        # Non-fatal: binary still works, just signature is invalid
        logger.warning(f"Failed to re-sign {binary_path}")
```

### 6. Environment Variables (Cross-Platform)

**Implemented:**
- `CLANG_TOOL_CHAIN_NO_DEPLOY_LIBS=1` - Disable automatic library deployment
- `CLANG_TOOL_CHAIN_NO_DEPLOY_SHARED_LIB=1` - Disable deployment for .dylib outputs only
- `CLANG_TOOL_CHAIN_LIB_DEPLOY_VERBOSE=1` - Enable verbose logging

### 7. Opt-Out Conditions

**Skip deployment when:**
- Platform is not macOS
- Compile-only (`-c` flag)
- Output is not an executable or .dylib (.o, .a files)
- Environment variable `CLANG_TOOL_CHAIN_NO_DEPLOY_LIBS=1`
- Output is .dylib and `CLANG_TOOL_CHAIN_NO_DEPLOY_SHARED_LIB=1`

### 8. Logging

**Levels:**
- **INFO**: Summary (e.g., "Deployed 3 dylib(s) for program")
- **DEBUG**: Individual dylib operations (detection, copy, path fixes)
- **WARNING**: Missing dylibs, permission errors, signing failures

### 9. Performance Expectations

**Estimated overhead per executable:**
- `otool -L`: ~10-20ms
- Copy dylibs: ~20-50ms (typically 1-3 dylibs)
- `install_name_tool` per fix: ~10-20ms
- `codesign`: ~50-100ms

**Total:** ~100-200ms per executable (acceptable overhead)

### 10. Testing Strategy

**Test cases:**
1. Executable with no non-system dependencies (no-op)
2. Executable with 1 custom dylib (copy + fix)
3. Executable with transitive dependencies (recursive)
4. Executable with @rpath dependencies (resolve + bundle)
5. .dylib output (test DEPLOY_DYLIBS_FOR_DYLIBS flag)
6. Environment variable opt-out
7. Compile-only (-c flag, skip deployment)
8. Code signing re-sign after modifications

### 11. Special Considerations for libunwind

**On macOS:**
- System libunwind is part of libSystem.B.dylib
- No deployment needed for system libunwind
- Custom LLVM libunwind: deploy if detected in `/usr/local/lib/`

**Detection:**
```python
if "libunwind.dylib" in deps and not lib_path.startswith("/usr/lib/"):
    # Custom libunwind - needs deployment
    deploy_dylib(binary_path, lib_path, output_dir)
```

---

## Sources

### Dependency Detection
- [Using otool to list dependencies - Apple Developer Forums](https://developer.apple.com/forums/thread/705281)
- [dylibtree - Inspect dynamic dependencies recursively](https://github.com/keith/dylibtree)
- [macdylibbundler - Utility to ease bundling libraries](https://github.com/auriamg/macdylibbundler)
- [Dynamic Library Usage Guidelines - Apple Developer](https://developer.apple.com/library/archive/documentation/DeveloperTools/Conceptual/DynamicLibraries/100-Articles/DynamicLibraryUsageGuidelines.html)

### Path Resolution
- [Understanding dyld @executable_path, @loader_path and @rpath - iTwenty's Space](https://itwenty.me/posts/01-understanding-rpath/)
- [@rpath what? - Krzyzanowski Blog](https://blog.krzyzanowskim.com/2018/12/05/rpath-what/)
- [Run-Path Dependent Libraries - Apple Developer](https://developer.apple.com/library/archive/documentation/DeveloperTools/Conceptual/DynamicLibraries/100-Articles/RunpathDependentLibraries.html)
- [Fun with rpath, otool, and install_name_tool - Chris Hamons](https://medium.com/@donblas/fun-with-rpath-otool-and-install-name-tool-e3e41ae86172)
- [Friday Q&A: Linking and Install Names - mikeash.com](https://www.mikeash.com/pyblog/friday-qa-2009-11-06-linking-and-install-names.html)

### install_name_tool Usage
- [Runtime linking on Mac - docosx documentation](https://matthew-brett.github.io/docosx/mac_runtime_link.html)
- [Fun with rpath, otool, and install_name_tool - Medium](https://medium.com/@donblas/fun-with-rpath-otool-and-install-name-tool-e3e41ae86172)
- [On OSX, library install name should contain @rpath - conda-build Issue #279](https://github.com/conda/conda-build/issues/279)
- [Changing Shared Library Paths on MacOS - Christian Scott](https://christianfscott.com/change-shared-library-path/)

### Deployment Strategies
- [macdylibbundler GitHub Repository](https://github.com/auriamg/macdylibbundler)
- [Deploying Applications on Mac OS X - Qt Documentation](https://doc.qt.io/archives/qq/qq09-mac-deployment.html)
- [Embedding .dylib libraries in your application bundle - geek jutsu](https://geekjutsu.wordpress.com/2015/10/13/embedding-dylib-libraries-in-your-application-bundle/)

### libunwind on macOS
- [libunwind - Homebrew Formulae](https://formulae.brew.sh/formula/libunwind)
- [Building libunwind - LLVM Documentation](https://bcain-llvm.readthedocs.io/projects/libunwind/en/latest/BuildingLibunwind/)
- [libunwind GitHub Repository (Apple fork)](https://github.com/tony/libunwind)

### Code Signing
- [Technical Note TN2206: macOS Code Signing In Depth](https://developer.apple.com/library/archive/technotes/tn2206/_index.html)
- [Configuring the Hardened Runtime - Apple Developer](https://developer.apple.com/documentation/xcode/configuring-the-hardened-runtime)
- [Code signing of dylib for use under hardened runtime - Apple Forums](https://developer.apple.com/forums/thread/670761)
- [A dylib fails to load under Hardened Runtime - Apple Forums](https://developer.apple.com/forums/thread/656303)

### Security Considerations
- [A Deep Dive into Penetration Testing of macOS Applications (Part 3) - CyberArk](https://www.cyberark.com/resources/threat-research-blog/a-deep-dive-into-penetration-testing-of-macos-applications-part-3)
- [Snake&Apple IV—Dylib Hijacking - Medium](https://karol-mazurek.medium.com/snake-apple-iv-dylibs-2c955439b94e)
- [Detecting and Exploiting App Vulnerabilities with DYLIB Injection - Der Benji](https://benjitrapp.github.io/attacks/2024-07-07-dylib-injection/)
- [Hijack Execution Flow: Dylib Hijacking - MITRE ATT&CK](https://attack.mitre.org/techniques/T1574/004/)
- [dylib-hijacking-toolkit GitHub Repository](https://github.com/UnsaltedHash42/dylib-hijacking-toolkit)
- [Dylib hijacking on OS X - Virus Bulletin](https://www.virusbulletin.com/virusbulletin/2015/03/dylib-hijacking-os-x)

---

**Document Status:** Research Complete
**Next Steps:** Implementation planning and code development
**Related Documents:**
- `docs/DLL_DEPLOYMENT.md` (Windows implementation reference)
- `docs/DLL_DETECTOR_ARCHITECTURE.md` (Architecture reference)
