# Linux Shared Library Deployment Research

**Author**: Agent 1.2 (Linux Shared Library Research)
**Date**: 2026-01-25
**Purpose**: Research Linux shared library deployment patterns and best practices for implementing automatic .so deployment in clang-tool-chain

---

## Table of Contents

1. [Dependency Detection Tools](#dependency-detection-tools)
2. [Deployment Strategies](#deployment-strategies)
3. [Best Practices](#best-practices)
4. [libunwind Specifics](#libunwind-specifics)
5. [Common Pitfalls and Security Considerations](#common-pitfalls-and-security-considerations)
6. [Recommendations for Implementation](#recommendations-for-implementation)

---

## 1. Dependency Detection Tools

### 1.1 Overview

Three primary tools exist for detecting shared library dependencies in Linux:

| Tool | Purpose | Security | Recursion | Execution Risk |
|------|---------|----------|-----------|----------------|
| `ldd` | List dynamic dependencies | ⚠️ Risk on untrusted binaries | ✅ Full (direct + transitive) | **High** - May execute binary |
| `readelf -d` | Read ELF dynamic section | ✅ Safe | ❌ Direct only | **None** - Static analysis |
| `patchelf --print-rpath` | Print RPATH/RUNPATH | ✅ Safe | ❌ Metadata only | **None** - Static analysis |

### 1.2 ldd (List Dynamic Dependencies)

**How it works**: `ldd` prints the shared libraries required by each program or shared library by invoking the standard dynamic linker with the `LD_TRACE_LOADED_OBJECTS` environment variable set to 1.

**Advantages**:
- Performs recursive lookup of dependencies, showing both direct and transitive dependencies
- Shows not only library names but also their resolved paths on the system
- Mimics the actual runtime behavior of the dynamic linker

**Critical Security Warning**:
> ⚠️ **Some versions of ldd may attempt to obtain dependency information by directly executing the program, so you should never employ ldd on untrusted executables since this may result in execution of arbitrary code.**

**Example Output**:
```bash
$ ldd /usr/bin/gcc
    linux-vdso.so.1 (0x00007ffed3bfe000)
    libc.so.6 => /lib/x86_64-linux-gnu/libc.so.6 (0x00007f8b3e200000)
    /lib64/ld-linux-x86-64.so.2 (0x00007f8b3e400000)
```

### 1.3 readelf -d (Read ELF Dynamic Section)

**How it works**: `readelf` inspects dynamic section entries and lists required shared libraries **without executing the program**.

**Advantages**:
- Analyzes the file without executing it, offering a **secure way to inspect dependencies**
- Shows only directly linked libraries (not recursive), providing precise control
- Better choice for ELF format analysis on Linux

**Example Usage**:
```bash
$ readelf -d /usr/bin/gcc | grep NEEDED
 0x0000000000000001 (NEEDED)             Shared library: [libc.so.6]
```

**Filtering NEEDED entries**:
```bash
$ readelf -d myprogram | grep '(NEEDED)' | awk '{print $5}' | tr -d '[]'
libc.so.6
libpthread.so.0
libstdc++.so.6
```

### 1.4 patchelf

**How it works**: `patchelf` is primarily a tool for **modifying** ELF binaries (changing RPATH, interpreter, etc.) rather than just inspecting dependencies, though it can display dynamic linking information.

**Capabilities**:
- Read RPATH/RUNPATH: `patchelf --print-rpath myprogram`
- Read interpreter: `patchelf --print-interpreter myprogram`
- Modify RPATH: `patchelf --set-rpath /new/path myprogram`
- Add to RUNPATH: `patchelf --add-rpath /additional/path myprogram`
- Remove RPATH: `patchelf --remove-rpath myprogram`
- Shrink RPATH: `patchelf --shrink-rpath myprogram` (removes unused directories)

**Example**:
```bash
$ patchelf --print-rpath myprogram
/opt/lib:/usr/local/lib
```

### 1.5 Comparison and Recommendations

**For Safe Dependency Inspection** (recommended for clang-tool-chain):
```bash
# Extract direct dependencies safely
readelf -d myprogram | grep '(NEEDED)' | awk '{print $5}' | tr -d '[]'

# Alternative using objdump
objdump -p myprogram | grep NEEDED | awk '{print $2}'
```

**For Complete Dependency Resolution** (when binary is trusted):
```bash
ldd myprogram
```

**For Modifying Dependencies**:
```bash
patchelf --set-rpath '$ORIGIN:$ORIGIN/lib' myprogram
```

**Security Best Practice**: For automated tooling (like clang-tool-chain), **always use `readelf -d` or `objdump -p`** to avoid the execution risk of `ldd` on user-compiled binaries.

---

## 2. Deployment Strategies

### 2.1 RPATH vs RUNPATH: Technical Differences

#### Search Order Priority

The major difference between RPATH and RUNPATH is their position in the dynamic linker's search order:

| Priority Order | LD_LIBRARY_PATH Present | LD_LIBRARY_PATH Absent |
|----------------|-------------------------|------------------------|
| 1st | **RPATH** | **RPATH** |
| 2nd | (skipped) | **LD_LIBRARY_PATH** |
| 3rd | **LD_LIBRARY_PATH** | RUNPATH |
| 4th | RUNPATH | System paths |
| 5th | System paths | - |

**Key Insight**: RPATH is searched **before** LD_LIBRARY_PATH, while RUNPATH is searched **after**.

#### Historical Context

Earlier, RPATH was the only flag that existed. The problem arose that once RPATH is set (which is done at build time), it cannot be overridden during execution since LD_LIBRARY_PATH has lower precedence. This limitation led to the introduction of RUNPATH, which allows LD_LIBRARY_PATH to take precedence, enabling runtime library path overrides without rebuilding.

#### Critical Behavior Difference: Indirect Dependencies

> ⚠️ **CRITICAL**: The executable's RUNPATH is **not used** for finding indirect library dependencies.

**Example Scenario**:
```
myprogram (RUNPATH=/opt/lib)
  └─ libfoo.so (found in /opt/lib)
       └─ libbar.so (NEEDED by libfoo.so)
```

- With **RPATH**: `/opt/lib` is used to find `libbar.so`
- With **RUNPATH**: `/opt/lib` is **NOT** used to find `libbar.so` (only for direct dependencies)

**Implication**: When shipping binaries, either:
1. Use **RPATH** (not RUNPATH) for reliable transitive dependency resolution
2. Set **LD_LIBRARY_PATH** before running the binary
3. Set **RPATH on all libraries** (not just the executable)

#### When Both Are Present

If both RPATH and RUNPATH are set in the same binary, the dynamic loader **ignores RPATH** and only uses RUNPATH.

#### Linker Flags

```bash
# Set RPATH (legacy, higher precedence)
gcc -Wl,-rpath,/opt/lib -o myprogram myprogram.c

# Set RUNPATH (modern, allows LD_LIBRARY_PATH override)
gcc -Wl,--enable-new-dtags -Wl,-rpath,/opt/lib -o myprogram myprogram.c

# Force RPATH even with --enable-new-dtags
gcc -Wl,--disable-new-dtags -Wl,-rpath,/opt/lib -o myprogram myprogram.c
```

### 2.2 Deployment Strategy: Copying Libraries vs Modifying RPATH

#### Option A: Copy Libraries to Executable Directory

**Approach**: Copy required `.so` files to the same directory as the executable and set `RPATH=$ORIGIN`.

**Advantages**:
- Self-contained deployment (all dependencies bundled)
- No system-wide changes required
- Works immediately without LD_LIBRARY_PATH
- Portable across different systems

**Disadvantages**:
- Duplicates libraries if multiple executables share dependencies
- Increases disk usage
- Requires careful version management (symlinks)
- May conflict with system libraries if LD_LIBRARY_PATH is set

**Example Implementation**:
```bash
# Compile with $ORIGIN RPATH
clang++ -o myprogram myprogram.cpp -Wl,-rpath,'$ORIGIN'

# Copy dependencies
cp /usr/lib/x86_64-linux-gnu/libstdc++.so.6 .
cp /usr/lib/x86_64-linux-gnu/libgcc_s.so.1 .

# Run (no LD_LIBRARY_PATH needed)
./myprogram
```

#### Option B: Modify RPATH to Absolute Paths

**Approach**: Set RPATH to absolute paths where libraries are installed.

**Advantages**:
- No need to copy libraries
- Shares libraries across executables (saves disk space)
- Works for system-wide installations

**Disadvantages**:
- Not portable (hardcoded paths)
- Requires libraries to be installed at specific locations
- Cannot be overridden by LD_LIBRARY_PATH (if using RPATH, not RUNPATH)

**Example Implementation**:
```bash
# Compile with absolute RPATH
clang++ -o myprogram myprogram.cpp -Wl,-rpath,/opt/myapp/lib

# Or modify existing binary
patchelf --set-rpath /opt/myapp/lib myprogram
```

#### Option C: Hybrid Approach with $ORIGIN

**Approach**: Use `$ORIGIN` to set RPATH relative to executable location, allowing flexible deployment.

**Advantages**:
- Portable (no absolute paths)
- Can bundle libraries in subdirectory (e.g., `./lib/`)
- Works with relocatable installations

**Disadvantages**:
- $ORIGIN is ignored in setuid/setgid programs (security feature)
- Requires understanding of relative path structure

**Example Implementation**:
```bash
# Directory structure:
# myapp/
#   bin/myprogram
#   lib/libfoo.so

# Compile with $ORIGIN-relative RPATH
clang++ -o bin/myprogram myprogram.cpp -Wl,-rpath,'$ORIGIN/../lib'

# Or modify existing binary
patchelf --set-rpath '$ORIGIN/../lib' bin/myprogram
```

### 2.3 Recommended Strategy for clang-tool-chain

**For Windows-style automatic DLL deployment on Linux**:

1. **Detect dependencies** using `readelf -d` (safe, no execution risk)
2. **Copy libraries** to executable directory
3. **Set RPATH** to `$ORIGIN` (or modify existing RPATH to include `$ORIGIN`)
4. **Handle symlinks** properly (preserve version numbering)
5. **Check timestamps** to avoid redundant copies

**Pros**:
- Consistent with Windows DLL deployment behavior
- Self-contained executables
- No system-wide changes required
- Works immediately without environment setup

**Cons**:
- Duplicates libraries (acceptable for development workflow)
- Requires careful transitive dependency resolution

---

## 3. Best Practices

### 3.1 RPATH Best Practices

#### DO:
- ✅ Use `$ORIGIN` for relative paths (portable, relocatable)
- ✅ Use **RPATH** (not RUNPATH) for bundled libraries to ensure transitive dependencies work
- ✅ Limit RPATH to application-specific directories (avoid system paths like `/usr/lib`)
- ✅ Shrink RPATH after build to remove unused directories (`patchelf --shrink-rpath`)
- ✅ Verify RPATH with `patchelf --print-rpath` or `readelf -d | grep RPATH`

#### DON'T:
- ❌ Don't use RPATH for system libraries (rely on standard system paths)
- ❌ Don't mix RPATH and RUNPATH (RPATH is ignored if RUNPATH present)
- ❌ Don't use absolute paths unless necessary (breaks portability)
- ❌ Don't set world-writable directories in RPATH (security risk)

### 3.2 Library Versioning and Symlinks

Shared libraries follow a versioning scheme:

```
libfoo.so          -> libfoo.so.1.2.3  (development symlink, for linking)
libfoo.so.1        -> libfoo.so.1.2.3  (SONAME symlink, for runtime)
libfoo.so.1.2.3    (actual library file, with full version)
```

**When copying libraries**:
1. Copy the **actual library file** (`libfoo.so.1.2.3`)
2. Create the **SONAME symlink** (`libfoo.so.1 -> libfoo.so.1.2.3`)
3. Optionally create the **development symlink** (`libfoo.so -> libfoo.so.1.2.3`) if needed for linking

**Why**: Binaries typically reference the SONAME (`libfoo.so.1`), not the full version. The dynamic linker expects the SONAME to resolve to a compatible library.

### 3.3 Transitive Dependency Resolution

When copying libraries, you must resolve **transitive dependencies**:

```bash
# Example: myprogram depends on libfoo.so.1, which depends on libbar.so.2

# Step 1: Find direct dependencies
readelf -d myprogram | grep '(NEEDED)'

# Step 2: For each dependency, find its dependencies
readelf -d libfoo.so.1 | grep '(NEEDED)'

# Step 3: Recursively copy all dependencies
# (Implementation requires graph traversal to avoid duplicates)
```

**Challenge**: `readelf -d` only shows direct dependencies, requiring recursive resolution.

**Solution**: Use `ldd` on **trusted** binaries after initial compilation, or implement recursive `readelf` parsing.

### 3.4 Avoiding System Library Conflicts

When bundling libraries, be cautious about copying **system libraries** like:
- `libc.so.6` (GNU C Library)
- `libpthread.so.0` (POSIX threads)
- `libm.so.6` (Math library)
- `libdl.so.2` (Dynamic linking)

**Why**: These are tightly coupled to the system and kernel version. Copying them can cause:
- ABI incompatibilities
- Crashes due to kernel interface mismatches
- Subtle bugs in threading or signal handling

**Best Practice**: Only copy **application-specific** and **toolchain-provided** libraries (e.g., libstdc++, libgcc_s, libunwind). Let system libraries be resolved via standard paths.

### 3.5 Deployment Checklist

Before deploying an executable with bundled libraries:

- [ ] Verify RPATH with `patchelf --print-rpath` or `readelf -d`
- [ ] Check dependencies with `ldd` (on trusted binaries only)
- [ ] Ensure SONAME symlinks are present
- [ ] Test on a clean system (without LD_LIBRARY_PATH set)
- [ ] Verify no absolute paths in RPATH (unless intentional)
- [ ] Check file permissions (libraries should be readable, not writable)
- [ ] Document bundled library versions

---

## 4. libunwind Specifics

### 4.1 Version Numbering

libunwind uses SONAME-based versioning:

- **libunwind 1.5+**: SONAME is `libunwind.so.8`
- **LLVM libunwind**: SONAME is `libunwind.so.1`

> ⚠️ **Critical**: These are **different libraries** with the same base name!

If you have a binary that `DT_NEEDS` a shared object with a SONAME of `libunwind.so.1`, then libunwind 1.5 (nongnu) will **not** satisfy it. Binaries requiring `libunwind.so.1` were likely built against the LLVM libunwind.

**On Ubuntu 22.04**:
- `libunwind-15` package provides LLVM libunwind (`libunwind.so.1`)
- `libunwind8` package provides nongnu libunwind (`libunwind.so.8`)

### 4.2 Standard Installation Paths

Typical installation paths:

- **System-wide** (Debian/Ubuntu): `/usr/lib/x86_64-linux-gnu/libunwind.so.8`
- **User-local**: `/usr/local/lib/libunwind.so.8`
- **LLVM toolchain**: `<llvm-install>/lib/libunwind.so.1`

### 4.3 Symlink Structure

For **nongnu libunwind** (SONAME libunwind.so.8):

```
libunwind.so          -> libunwind.so.8.0.1  (development symlink)
libunwind.so.8        -> libunwind.so.8.0.1  (SONAME symlink)
libunwind.so.8.0.1    (actual library)
```

For **LLVM libunwind** (SONAME libunwind.so.1):

```
libunwind.so          -> libunwind.so.1      (development symlink)
libunwind.so.1        (actual library, typically no further versioning)
```

### 4.4 Missing Symlinks Issue

**Bug Report**: Debian bug #996823 documented a missing symlink issue where `libunwind-13` package only included `/usr/lib/x86_64-linux-gnu/libunwind.so.1` but **not** `/usr/lib/x86_64-linux-gnu/libunwind.so` (development symlink).

**Impact**: Linking with `-lunwind` failed because the linker expects `libunwind.so` (unversioned) to exist.

**Workaround**: Manually create the symlink:
```bash
sudo ln -s libunwind.so.1 /usr/lib/x86_64-linux-gnu/libunwind.so
```

### 4.5 Deployment Recommendations for libunwind

When deploying executables that depend on libunwind:

1. **Identify which libunwind**: Check SONAME with `readelf -d myprogram | grep libunwind`
2. **Copy the correct library**: Match the SONAME (`.so.1` for LLVM, `.so.8` for nongnu)
3. **Create SONAME symlink**: Ensure `libunwind.so.X -> libunwind.so.X.Y.Z` exists
4. **Test on target system**: Verify with `ldd myprogram` (no "not found" errors)

**Example**:
```bash
# For LLVM libunwind
cp /path/to/llvm/lib/libunwind.so.1 ./
./myprogram  # Works if RPATH=$ORIGIN is set

# For nongnu libunwind
cp /usr/lib/x86_64-linux-gnu/libunwind.so.8.0.1 ./
ln -s libunwind.so.8.0.1 libunwind.so.8
./myprogram  # Works if RPATH=$ORIGIN is set
```

### 4.6 Additional libunwind Libraries

The nongnu libunwind package includes multiple libraries:

- `libunwind.so` - Main library
- `libunwind-coredump.so` - Core dump unwinding
- `libunwind-generic.so` - Generic unwinding (symlink to architecture-specific library)
- `libunwind-ptrace.so` - Ptrace-based unwinding
- `libunwind-setjmp.so` - setjmp/longjmp emulation
- `libunwind-x86_64.so` - x86_64-specific unwinding

**For clang-tool-chain**: Only `libunwind.so` (LLVM variant) is typically needed, as it's used by the LLVM toolchain's exception handling.

---

## 5. Common Pitfalls and Security Considerations

### 5.1 Security Pitfalls Overview

Shared library hijacking is a powerful attack technique where an attacker forces a target application to load a malicious shared library instead of the legitimate one. This can be achieved by:

1. Exploiting insecure RPATH/RUNPATH configurations
2. Abusing environment variables like LD_LIBRARY_PATH
3. Placing malicious libraries in directories with higher search priority

### 5.2 RPATH/RUNPATH Vulnerabilities

#### Writable Directories in RPATH

**Risk**: If RPATH includes directories writable by attackers, malicious libraries can be injected.

**Example**:
```bash
# BAD: /tmp is world-writable
patchelf --set-rpath '/tmp:/opt/lib' myprogram

# An attacker can create /tmp/libfoo.so (malicious)
# myprogram will load it instead of the legitimate library
```

**Mitigation**:
- ✅ Only use RPATH for directories with restricted write permissions
- ✅ Avoid world-writable directories (`/tmp`, `/var/tmp`)
- ✅ Use `$ORIGIN` for application-controlled directories

#### Relative Paths with $ORIGIN

**Risk**: The `$ORIGIN` token is **ignored in setuid/setgid programs** as a security measure.

**Why**: setuid programs have elevated privileges. If `$ORIGIN` were honored, an attacker could:
1. Place the setuid binary in a controlled directory
2. Add malicious libraries in `$ORIGIN/lib`
3. Execute the setuid binary to gain elevated privileges with malicious code

**Mitigation**: For setuid/setgid programs, use **absolute paths** in RPATH or rely on system library paths.

#### RPATH Injection Attacks

**Attack Scenario**: If RPATH includes user-controlled directories, privilege escalation is possible.

**Example**:
```bash
# Vulnerable program with RPATH=/home/user/lib
patchelf --print-rpath /usr/local/bin/vulnerable
/home/user/lib

# Attacker creates malicious library
echo 'void malicious() __attribute__((constructor)); void malicious() { system("/bin/bash"); }' > /home/user/lib/libfoo.c
gcc -shared -fPIC -o /home/user/lib/libfoo.so /home/user/lib/libfoo.c

# When vulnerable program runs, malicious code executes
/usr/local/bin/vulnerable
```

**Mitigation**: Avoid user-controlled directories in RPATH for privileged programs.

### 5.3 LD_LIBRARY_PATH Issues

#### Scope and Inheritance

**Problem**: LD_LIBRARY_PATH overrides the search paths for **all binaries**, not just the intended one.

**Example**:
```bash
# Intent: Override library path for myprogram
export LD_LIBRARY_PATH=/opt/myapp/lib
./myprogram  # Works as intended

# Unintended consequence: ALL subsequent commands use /opt/myapp/lib
ls  # May load malicious libraries from /opt/myapp/lib if present
gcc # May break if incompatible libraries are found
```

**Mitigation**:
- ✅ Use RPATH instead of LD_LIBRARY_PATH for production deployments
- ✅ Limit LD_LIBRARY_PATH scope with wrapper scripts:
  ```bash
  LD_LIBRARY_PATH=/opt/myapp/lib ./myprogram
  # (LD_LIBRARY_PATH only affects this one command)
  ```

#### Security in Setuid Programs

**Protection**: LD_LIBRARY_PATH is **ignored** when the executable is being run in secure-execution mode (setuid/setgid programs).

**Why**: Prevents unprivileged users from injecting malicious libraries into privileged programs.

#### Distribution Deployment

**Guideline**: LD_LIBRARY_PATH cannot be used for distribution-wide deployments because:
- It's inherited by all child processes
- It can cause unexpected side effects (library version conflicts)
- It's discouraged by Linux distribution guidelines (e.g., Debian)

**Alternative**: Use RPATH or install libraries in standard system paths (`/usr/lib`, `/usr/local/lib`) with `ldconfig`.

### 5.4 Library Search Order Exploits

#### Search Order Reference

The dynamic linker searches for libraries in this order (when not setuid/setgid):

1. **RPATH** (if present, DT_RUNPATH not present)
2. **LD_LIBRARY_PATH** (if RPATH not present or RUNPATH present)
3. **RUNPATH** (if present)
4. **System cache** (`/etc/ld.so.cache`, managed by `ldconfig`)
5. **Default paths** (`/lib`, `/usr/lib`, etc.)

**Exploit Scenario**: Attacker with control over LD_LIBRARY_PATH (if RUNPATH is used) can inject libraries before system paths.

**Defense**: Use **RPATH** (not RUNPATH) for critical applications to prevent LD_LIBRARY_PATH override.

### 5.5 Best Practices for Secure Deployment

#### Debian RPATH Policy

**Allowed Use**: The only generally accepted use of RPATH in Debian is to add **non-standard library paths** (like `/usr/lib/<package>`) to libraries that are only intended to be used by executables or other libraries **within the same source package**.

**Rationale**: Prevents contamination of system-wide library search paths.

#### System-Wide Library Installation

For production deployments, a safer system-wide approach:

1. Copy the library to `/usr/local/lib` or `/usr/lib/<package>`
2. Update the loader cache using `ldconfig`:
   ```bash
   sudo cp libfoo.so.1.2.3 /usr/local/lib/
   sudo ln -s libfoo.so.1.2.3 /usr/local/lib/libfoo.so.1
   sudo ldconfig
   ```
3. Verify: `ldconfig -p | grep libfoo`

**Advantage**: Libraries are managed centrally, reducing security risks.

#### File Permissions

Ensure bundled libraries have correct permissions:

```bash
# Libraries should be readable by all, writable only by owner
chmod 644 *.so*

# Or more restrictive (owner only)
chmod 600 *.so*

# NEVER make libraries world-writable
# chmod 666 *.so*  # DANGEROUS!
```

#### Verification Checklist

Before deploying an executable with bundled libraries:

- [ ] RPATH does not include world-writable directories
- [ ] RPATH does not include user-controlled directories (for privileged programs)
- [ ] Libraries have correct permissions (not world-writable)
- [ ] No absolute paths in RPATH (unless intentional and safe)
- [ ] Tested on a clean system without LD_LIBRARY_PATH set
- [ ] Verified with `ldd` (no unexpected library paths)
- [ ] Documented bundled library versions and sources

---

## 6. Recommendations for Implementation

### 6.1 Implementation Strategy for clang-tool-chain

Based on the research, here's the recommended approach for automatic `.so` deployment on Linux (analogous to Windows DLL deployment):

#### Phase 1: Dependency Detection (Safe)

1. **Use `readelf -d`** to extract `NEEDED` entries:
   ```bash
   readelf -d myprogram | grep '(NEEDED)' | awk '{print $5}' | tr -d '[]'
   ```

2. **Recursive resolution**: For each library, recursively find its dependencies:
   ```python
   def get_dependencies(binary_path):
       result = subprocess.run(['readelf', '-d', binary_path], capture_output=True, text=True)
       needed_libs = []
       for line in result.stdout.splitlines():
           if '(NEEDED)' in line:
               lib = line.split('[')[1].split(']')[0]
               needed_libs.append(lib)
       return needed_libs
   ```

3. **Resolve library paths**: Use `ld.so --list` (safer alternative to `ldd`) or search standard paths:
   ```bash
   ld.so --list /path/to/myprogram
   ```

#### Phase 2: Filtering (Critical)

**Only copy toolchain-provided libraries**, not system libraries:

```python
SYSTEM_LIBS = {'libc.so.6', 'libpthread.so.0', 'libm.so.6', 'libdl.so.2', 'librt.so.1', 'linux-vdso.so.1', 'ld-linux-x86-64.so.2'}
CLANG_LIBS = {'libunwind.so.1', 'libc++.so.1', 'libc++abi.so.1', 'libgcc_s.so.1'}

def should_copy_library(lib_name):
    # Only copy CLANG_LIBS, skip SYSTEM_LIBS
    return lib_name in CLANG_LIBS
```

**Rationale**: System libraries are tightly coupled to the kernel and should be resolved via standard paths.

#### Phase 3: Copying with Symlink Handling

1. **Copy actual library file**:
   ```python
   shutil.copy2('/path/to/libfoo.so.1.2.3', './libfoo.so.1.2.3')
   ```

2. **Create SONAME symlink**:
   ```python
   os.symlink('libfoo.so.1.2.3', './libfoo.so.1')
   ```

3. **Check timestamps** (avoid redundant copies):
   ```python
   if os.path.exists(dest_path):
       src_mtime = os.path.getmtime(src_path)
       dest_mtime = os.path.getmtime(dest_path)
       if src_mtime <= dest_mtime:
           return  # Skip copy, dest is up-to-date
   ```

#### Phase 4: RPATH Modification

**Option A**: Modify existing RPATH to include `$ORIGIN`:
```python
result = subprocess.run(['patchelf', '--print-rpath', binary_path], capture_output=True, text=True)
current_rpath = result.stdout.strip()

if '$ORIGIN' not in current_rpath:
    new_rpath = f'$ORIGIN:{current_rpath}' if current_rpath else '$ORIGIN'
    subprocess.run(['patchelf', '--set-rpath', new_rpath, binary_path])
```

**Option B**: Set RPATH during linking (cleaner):
```bash
clang++ -o myprogram myprogram.cpp -Wl,-rpath,'$ORIGIN'
```

#### Phase 5: Verification

After deployment, verify:
```python
result = subprocess.run(['ldd', binary_path], capture_output=True, text=True)
if 'not found' in result.stdout:
    print(f"Warning: Missing dependencies for {binary_path}")
```

### 6.2 Environment Variables for User Control

Similar to Windows DLL deployment, provide opt-out mechanisms:

- `CLANG_TOOL_CHAIN_NO_DEPLOY_SO=1` - Disable automatic .so deployment
- `CLANG_TOOL_CHAIN_SO_DEPLOY_VERBOSE=1` - Enable verbose logging
- `CLANG_TOOL_CHAIN_USE_SYSTEM_LD=1` - Use system libraries (already exists for linker)

### 6.3 Performance Considerations

**Overhead**:
- Library detection: ~50ms per executable (`readelf` overhead)
- Library copying: ~50ms total (2-3 small libraries typically)
- RPATH modification: ~20ms (`patchelf` overhead)
- **Total**: ~120ms per executable build

**Optimization**:
- Cache resolved library paths (avoid repeated searches)
- Skip copy if timestamp unchanged
- Parallelize library copying (if multiple libraries)

### 6.4 Logging Levels

Similar to Windows DLL deployment:

- **INFO**: Summary of deployed libraries (e.g., "Deployed 3 shared libraries for myprogram")
- **DEBUG**: Individual library operations (detection, copy, skip reasons)
- **WARNING**: Missing libraries, permission errors, detection failures

### 6.5 Testing Strategy

**Test Coverage**:
1. Basic executable with clang-provided dependencies
2. Executable with transitive dependencies
3. Shared library (.so) output
4. Multiple executables sharing libraries (timestamp check)
5. Opt-out via environment variables
6. Missing dependencies (warning, non-fatal)
7. Permission errors (warning, non-fatal)

**Test Platforms**:
- Linux x86_64
- Linux ARM64

### 6.6 Implementation Files

Suggested file structure (mirroring Windows DLL deployment):

```
src/clang_tool_chain/deployment/
├── __init__.py
├── dll_deployer.py       (existing, Windows)
└── so_deployer.py        (new, Linux)

tests/
├── test_dll_deployment.py  (existing, Windows)
└── test_so_deployment.py   (new, Linux)
```

### 6.7 Open Questions

1. **RPATH vs RUNPATH**: Should we use RPATH (higher precedence, transitive dependencies work) or RUNPATH (allows LD_LIBRARY_PATH override)?
   - **Recommendation**: Use **RPATH** for reliability with transitive dependencies.

2. **System library bundling**: Should we allow users to bundle system libraries via opt-in flag?
   - **Recommendation**: No. Too risky. Only bundle toolchain-provided libraries.

3. **patchelf dependency**: Should we bundle patchelf or require users to install it?
   - **Recommendation**: Add `patchelf` as an optional dependency (like `sccache`). If not available, skip RPATH modification and warn user.

4. **Shared library (.so) outputs**: Should we deploy dependencies for .so files (like we do for .dll on Windows)?
   - **Recommendation**: Yes, but with opt-out (`CLANG_TOOL_CHAIN_NO_DEPLOY_DLLS_FOR_DLLS=1` analogue).

### 6.8 Comparison with Windows DLL Deployment

| Feature | Windows DLL Deployment | Linux .so Deployment |
|---------|----------------------|---------------------|
| Detection Tool | `llvm-objdump -p` (PE imports) | `readelf -d` (ELF NEEDED) |
| Deployment Strategy | Copy DLLs to executable directory | Copy .so files + set RPATH |
| Symlink Handling | N/A (Windows shortcuts not needed) | Must create SONAME symlinks |
| RPATH Equivalent | N/A (DLL search uses directory) | RPATH/RUNPATH in ELF binary |
| System Libraries | Exclude MSVC runtime | Exclude glibc, libpthread, etc. |
| Opt-out | `CLANG_TOOL_CHAIN_NO_DEPLOY_DLLS=1` | `CLANG_TOOL_CHAIN_NO_DEPLOY_SO=1` |
| Verbose Logging | `CLANG_TOOL_CHAIN_DLL_DEPLOY_VERBOSE=1` | `CLANG_TOOL_CHAIN_SO_DEPLOY_VERBOSE=1` |

---

## References

### Dependency Detection Tools
- [How to check library dependencies in Linux](https://www.simplified.guide/linux/show-shared-library-dependency)
- [Understanding ldd: The Linux Dynamic Dependency Explorer](https://dzone.com/articles/linux-ldd-command-dynamic-dependencies)
- [Better understanding Linux secondary dependencies solving with examples](http://www.kaizou.org/2015/01/linux-libraries.html)
- [Find library dependencies of a binary file (Linux) - DEV Community](https://dev.to/tallesl/find-library-dependencies-of-a-binary-file-linux-3njf)
- [ldd: Your Linux Shared Library Troubleshooting Guide Better 2026](https://www.linuxoperatingsystem.net/ldd-command-line-in-linux/)
- [How to Show All Shared Libraries Used by Executables in Linux? | Baeldung on Linux](https://www.baeldung.com/linux/show-shared-libraries-executables)

### RPATH vs RUNPATH
- [rpath vs runpath. Before we understand the difference… | by Heart Bleed | Obscure System | Medium](https://medium.com/obscure-system/rpath-vs-runpath-883029b17c45)
- [Shared Library RPATH vs Binary RPATH: Priority, Linker Search Order, and $ORIGIN Behavior Explained](https://linuxvox.com/blog/the-shared-library-rpath-and-the-binary-rpath-priority/)
- [Yet another post about dynamic lookup of shared libraries - twdev.blog](https://twdev.blog/2024/08/rpath/)
- [RPATH, RUNPATH, and dynamic linking](https://blog.tremily.us/posts/rpath/)

### libunwind Specifics
- [why don't have libunwind.so.1 after install? · libunwind/libunwind · Discussion #665](https://github.com/libunwind/libunwind/discussions/665)
- [libunwind-1.8.3](https://www.linuxfromscratch.org/blfs/view/svn/general/libunwind.html)
- [#996823 - libunwind-13: Missing symlink libunwind.so to libunwind.so.1](https://bugs.debian.org/cgi-bin/bugreport.cgi?bug=996823)

### Security Considerations
- [Shared Libs: Linking, LD_LIBRARY_PATH, rpath, & ldconfig](https://circuitlabs.net/shared-libs-linking-ld_library_path-rpath-ldconfig/)
- [Understanding Shared Libraries in Linux | by Can Özkan | Jan, 2026 | Medium](https://can-ozkan.medium.com/understanding-shared-libraries-in-linux-77d302ba45ec)
- [The why and how of RPATH – Flameeyes's Weblog](https://flameeyes.blog/2010/06/20/the-why-and-how-of-rpath/)
- [Linux Privilege Escalation: Abusing shared libraries | BoiteAKlou's Infosec Blog](https://www.boiteaklou.fr/Abusing-Shared-Libraries.html)
- [RpathIssue - Debian Wiki](https://wiki.debian.org/RpathIssue)

### patchelf
- [Changing rpath in an Already Compiled Binary | Baeldung on Linux](https://www.baeldung.com/linux/rpath-change-in-binary)
- [GitHub - NixOS/patchelf: A small utility to modify the dynamic linker and RPATH of ELF executables](https://github.com/NixOS/patchelf)
- [patchelf: Modify ELF files | Man Page](https://www.mankier.com/1/patchelf)
- [patchelf(1) — patchelf — Debian unstable](https://manpages.debian.org/unstable/patchelf/patchelf.1.en.html)

---

**End of Research Document**
