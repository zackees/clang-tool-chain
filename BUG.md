# Known Bugs and Issues

## Build System Issues

### 1. sccache Windows Persistence Error (Active)

**Symptoms:**
```
sccache: encountered fatal error
sccache: error: failed to persist temporary file: The system cannot find the path specified. (os error 3)
sccache: caused by: failed to persist temporary file: The system cannot find the path specified. (os error 3)
sccache: caused by: The system cannot find the path specified. (os error 3)
```

**When it occurs:**
- Intermittent compilation failures on Windows
- Appears to be related to sccache trying to write to cache directory
- May be triggered by cache directory deletion or path changes

**Workarounds:**
```bash
# Stop sccache server
sccache --stop-server

# Clear sccache cache
rm -rf "$HOME/.cache/sccache"  # Linux/Mac
rm -rf "$HOME/AppData/Local/Mozilla/sccache/cache"  # Windows

# Disable sccache temporarily
SCCACHE_DISABLE=1 uv run test.py --cpp
```

**Root cause:**
- Likely Windows-specific file system race condition or permission issue
- sccache may be trying to create temporary files in a directory that doesn't exist
- Could be related to long path names or special characters in Windows paths

**Status:** Under investigation

---

### 2. Fingerprint Caching May Not Track Test File Changes (Suspected)

**Symptoms:**
- Build system may not recompile when test files in `tests/` are modified
- Using `--no-fingerprint` flag forces rebuild and picks up changes
- Changes to `src/` files are detected correctly

**Hypothesis:**
The fingerprinting system in `ci/util/meson_helper.py` (or related) may only be tracking changes in `src/` directory recursively, not `tests/` directory.

**Test case to verify:**
```bash
# 1. Make a change to a test file
echo "// test change" >> tests/fl/timeout.cpp

# 2. Run tests without --no-fingerprint
uv run test.py --cpp timeout

# 3. Check if it recompiles or uses cached version
# Expected: Should recompile
# Actual (suspected): May use cached version
```

**Workaround:**
Use `--no-fingerprint` flag when working on test files:
```bash
uv run test.py --cpp --no-fingerprint <testname>
```

**Suggested fix:**
Review fingerprinting logic in:
- `ci/util/meson_helper.py`
- `ci/util/fingerprint.py` (if exists)
- Ensure both `src/` and `tests/` directories are scanned recursively for changes
- Consider including `tests/test_config.py` and `tests/organize_tests.py` in fingerprint

**Status:** Needs investigation and verification

---

## Code Organization Improvements Completed

### CriticalSection Moved to fl/isr.h (2026-01-05)

**Change:**
Moved `CriticalSection` RAII helper class from `fl/detail/async_log_queue.h` to `fl/isr.h` for broader reusability.

**Migration notes:**
- Old location: `fl::CriticalSection` in `fl/detail/async_log_queue.h`
- New location: `fl::isr::CriticalSection` in `fl/isr.h`
- Implementation: `fl/isr.cpp`

**Updated files:**
- `src/fl/isr.h` - Added CriticalSection class declaration
- `src/fl/isr.cpp` - Added CriticalSection implementation
- `src/fl/detail/async_log_queue.h` - Now includes `fl/isr.h` and uses `fl::isr::CriticalSection`
- `src/fl/detail/async_log_queue.cpp` - Updated all references to use `fl::isr::CriticalSection`
- `tests/fl/async_log_queue.cpp` - Updated test to use `fl::isr::CriticalSection`

**Breaking change:** Yes, for any code that directly referenced `fl::CriticalSection`
- Old: `fl::CriticalSection cs;`
- New: `fl::isr::CriticalSection cs;`

---

## AsyncLogger Refactoring (2026-01-05)

**Completed:**
Refactored AsyncLogger to use template-based lazy instantiation with auto-registration.

**Key changes:**
1. Created `src/fl/detail/async_logger.{h,cpp}` - Moved AsyncLogger implementation to detail folder
2. Created `ActiveLoggerRegistry` - Only tracks loggers that are actually instantiated
3. Implemented `get_async_logger_by_index<N>()` - Template function with auto-registration
4. Removed old switch-based registry that forced all 16 loggers to compile

**Benefits:**
- Linker can now remove unused async logger singletons
- Only loggers accessed via convenience wrappers or template function are compiled
- Zero overhead registration via static initialization
- Reduced binary size when not all logger categories are used

**Test coverage:**
- `tests/fl/detail/async_logger.cpp` - Verifies lazy instantiation and auto-registration

---

## Future Improvements

### Build System
- [ ] Investigate and fix sccache Windows persistence error
- [ ] Verify and fix fingerprint tracking for test files
- [ ] Consider adding build system self-test for fingerprinting accuracy

### Code Quality
- [ ] Add more tests for CriticalSection behavior (if mockable)
- [ ] Document best practices for using CriticalSection in ISR contexts
- [ ] Consider adding debug mode that tracks CriticalSection nesting depth
