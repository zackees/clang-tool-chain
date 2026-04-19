# Zccache Integration — Interface Contracts

<!-- AGENT: Read this file before implementing any of the zccache-integration
     phases (P2 install profile, P3 shim, P4 console scripts, P5 tests).
     These interfaces are load-bearing — the phases run in parallel, so
     everyone shares this contract. -->

Target state: replace the custom `ctc-clang` native launcher and the legacy
`execute_tool` Python pipeline with a thin Python shim that execs into
`zccache` (PyPI package, Rust binary, `>=1.2.12`). Zero custom native code
in this repo.

Read this doc alongside:
- `docs/ENVIRONMENT_VARIABLES.md` (env-var surface, being pruned)

## 1. `profile.json` schema

**Location:** `~/.clang-tool-chain/{platform}/{arch}/profile.json` (honoring
`CLANG_TOOL_CHAIN_DOWNLOAD_PATH`).

**Produced by:** `clang-tool-chain install clang` (and re-generated on
each reinstall).

**Consumed by:** `zccache_shim.exec_via_zccache`.

**Schema version:** `"version": 1` — bump breaks backward compat; readers
must reject unknown versions.

```json
{
  "version": 1,
  "generated_at": "2026-04-18T18:14:00Z",
  "platform": "win",
  "arch": "x86_64",
  "clang_root": "C:/Users/me/.clang-tool-chain/clang/win/x86_64",
  "binaries": {
    "clang":      "{clang_root}/bin/clang.exe",
    "clang++":    "{clang_root}/bin/clang++.exe",
    "clang-tidy": "{clang_root}/bin/clang-tidy.exe",
    "lld":        "{clang_root}/bin/lld.exe",
    "llvm-ar":    "{clang_root}/bin/llvm-ar.exe",
    "emcc":       "{emsdk_root}/emcc.bat",
    "em++":       "{emsdk_root}/em++.bat",
    "wasm-ld":    "{clang_root}/bin/wasm-ld.exe",
    "iwyu":       "{iwyu_root}/bin/include-what-you-use.exe"
  },
  "abi_profiles": {
    "gnu": {
      "flags_all": [
        "--target=x86_64-w64-windows-gnu",
        "--sysroot={clang_root}/x86_64-w64-mingw32",
        "-stdlib=libc++",
        "-I{clang_root}/include/c++/v1",
        "-isystem{clang_root}/include"
      ],
      "flags_link_only": [
        "-rtlib=compiler-rt",
        "-fuse-ld=lld",
        "--unwindlib=libunwind",
        "-static-libgcc",
        "-static-libstdc++",
        "-lpthread"
      ]
    },
    "msvc": {
      "flags_all": ["--target=x86_64-pc-windows-msvc"],
      "flags_link_only": []
    }
  },
  "sanitizer_env": {
    "ASAN_SYMBOLIZER_PATH": "{clang_root}/bin/llvm-symbolizer.exe",
    "ASAN_OPTIONS_DEFAULTS": "abort_on_error=1:halt_on_error=1"
  },
  "libdeploy": {
    "mingw_dll_dir":         "{clang_root}/x86_64-w64-mingw32/bin",
    "llvm_objdump":          "{clang_root}/bin/llvm-objdump.exe",
    "compiler_rt_libs_dir":  "{clang_root}/lib/clang/21/lib/windows"
  }
}
```

### Schema rules

- **`{placeholder}` substitution** is performed at profile-load time, NOT
  at bake time. `{clang_root}` is always defined. Others (`{emsdk_root}`,
  `{iwyu_root}`) are optional — absence means the tool isn't installed.
- **Null values** mean "intentionally absent on this platform" (e.g., MSVC
  ABI is null on Linux/macOS). Reader skips the whole block.
- **Paths use forward slashes** on all platforms. Consumers normalize to
  OS-native separators.
- **`flags_all`** always apply when this ABI is selected. **`flags_link_only`**
  are dropped when `-c`, `-S`, or `-E` appears in user argv.
- Platform-specific keys:
  - Windows: `gnu` + `msvc` profiles; `libdeploy.mingw_dll_dir` populated.
  - Linux: single `"linux"` ABI profile; `libdeploy` contains
    `libunwind_lib_dir` instead of `mingw_dll_dir`.
  - macOS: single `"darwin"` ABI profile with `isysroot` field (detected
    once via `xcrun` at install time, may be empty if CLT not present).

## 2. `zccache_shim.py` public API

```python
# src/clang_tool_chain/zccache_shim.py

from typing import Literal, NoReturn

ToolName = Literal[
    "clang", "clang++", "emcc", "em++", "wasm-ld", "clang-tidy", "iwyu"
]
ABI = Literal["auto", "gnu", "msvc", "linux", "darwin"]

def find_zccache_binary() -> Path | None:
    """sys.executable-adjacent → PATH. None if missing."""

def load_profile() -> Profile:
    """Reads profile.json, applies {placeholder} substitution, caches in
    module global. Raises ProfileMissingError if install hasn't run."""

def exec_via_zccache(
    tool: ToolName,
    *,
    use_cache: bool,
    abi: ABI = "auto",
) -> NoReturn:
    """
    Builds the argv and execvps into zccache. Never returns.

    Order of argv construction:
      1. sys.argv[1:]                               — user args
      2. directive_flags_from_sources(sys.argv[1:]) — parsed from source files
      3. abi_profile.flags_all                      — from profile.json
      4. abi_profile.flags_link_only                — unless -c/-S/-E in argv
      5. resolve tool → absolute compiler path from profile.binaries
      6. final: [zccache, <compiler_path>, ...merged_args]

    If use_cache is False: ZCCACHE_DISABLE=1 set before execvp.
    If use_cache is True:  ZCCACHE_LINK_DEPLOY_CMD set to
                           "clang-tool-chain-libdeploy" before execvp.

    abi selection:
      "auto"  → Windows default = gnu, linux/macos use the only profile
      "gnu"/"msvc"/"linux"/"darwin" → force specific profile
    """

def parse_directives_fast(args: list[str]) -> list[str]:
    """Scan source files in argv for // @link:, // @cflags:, etc.
    Import-light: no execution.* or arg_transformers imports."""

class ProfileMissingError(Exception): ...
```

### Constraints

- **Import footprint:** the module must NOT import `execution.*`,
  `arg_transformers`, `platform.detection`, or anything that transitively
  loads them. Enforced by a subprocess-based test.
- **No logging at INFO.** Keep silent on hot path. `CTC_SHIM_DEBUG=1`
  opens a DEBUG channel via `logging`.
- **Thread-unsafe profile cache is fine** — each invocation is a fresh
  process.

## 3. Console script entry-point pattern

Every new entry point is ≤ 3 lines:

```python
# src/clang_tool_chain/commands/entry_points.py

def clang_main() -> NoReturn:
    from ..zccache_shim import exec_via_zccache
    exec_via_zccache("clang", use_cache=False)

def zccache_clang_main() -> NoReturn:
    from ..zccache_shim import exec_via_zccache
    exec_via_zccache("clang", use_cache=True)
```

### Full entry-point matrix

| Console script                          | `tool`       | `use_cache` |
|-----------------------------------------|--------------|-------------|
| `clang-tool-chain-clang`                | `clang`      | False       |
| `clang-tool-chain-clang++`              | `clang++`    | False       |
| `clang-tool-chain-zccache-clang`        | `clang`      | True        |
| `clang-tool-chain-zccache-clang++`      | `clang++`    | True        |
| `clang-tool-chain-emcc`                 | `emcc`       | False       |
| `clang-tool-chain-em++`                 | `em++`       | False       |
| `clang-tool-chain-zccache-emcc`         | `emcc`       | True        |
| `clang-tool-chain-zccache-em++`         | `em++`       | True        |
| `clang-tool-chain-wasm-ld`              | `wasm-ld`    | False       |
| `clang-tool-chain-zccache-wasm-ld`      | `wasm-ld`    | True        |
| `clang-tool-chain-clang-tidy`           | `clang-tidy` | False       |
| `clang-tool-chain-zccache-clang-tidy`   | `clang-tidy` | True        |
| `clang-tool-chain-iwyu`                 | `iwyu`       | False       |
| `clang-tool-chain-zccache-iwyu`         | `iwyu`       | True        |
| `clang-tool-chain-libdeploy`            | *(not a shim)* | n/a       |

### MSVC ABI

Not separate entry points. Users override ABI with either:
- **Env var:** `CTC_ABI=msvc clang-tool-chain-clang foo.c`
- **Argv prefix:** `clang-tool-chain-clang --ctc-abi=msvc foo.c` — consumed
  by the shim, stripped from argv before exec.

Deprecated entry points (`-c-msvc`, `-cpp-msvc`, `-sccache-c-msvc`, etc.)
forward to their new equivalent with `abi="msvc"`.

## 4. `clang-tool-chain-libdeploy` CLI contract

Invoked by zccache via `ZCCACHE_LINK_DEPLOY_CMD` after a cache-miss link.
Receives the linker output path as argv[1].

```
clang-tool-chain-libdeploy <output_path>
  - reads profile.libdeploy section
  - dispatches to existing DLL/SO/dylib deployer based on output suffix
  - exits 0 on success, 1 on error (don't fail the build — warn)
```

- No env var dependencies. No assumptions about who invoked it.
- Idempotent — must handle being called twice with the same path.
- Silent on success. Prints deployed DLL names at DEBUG (when
  `CLANG_TOOL_CHAIN_LIB_DEPLOY_VERBOSE=1`).

## 5. Env-var surface (post-migration)

**Kept:**
- `CLANG_TOOL_CHAIN_DOWNLOAD_PATH` — toolchain install dir
- `CLANG_TOOL_CHAIN_NO_DIRECTIVES` — disable directive parsing in shim
- `CLANG_TOOL_CHAIN_DIRECTIVE_VERBOSE` — stderr dump of parsed directives
- `CLANG_TOOL_CHAIN_LIB_DEPLOY_VERBOSE` — libdeploy debug output
- `CLANG_TOOL_CHAIN_USE_SYSTEM_LD` — honored via profile.json rewrite at load
- `CTC_ABI` — override ABI (`auto` | `gnu` | `msvc` | `linux` | `darwin`)
- `CTC_SHIM_DEBUG` — shim-internal debug trace

**Proxied to zccache (documented but not ours):**
- `ZCCACHE_DIR`, `ZCCACHE_DISABLE`, `ZCCACHE_ENDPOINT`, `ZCCACHE_SESSION_ID`

**Removed in Phase 7:**
- `CLANG_TOOL_CHAIN_PY_TRAMPOLINE` — obsolete, no legacy path remains
- `CLANG_TOOL_CHAIN_NO_AUTO` — obsolete, transforms move into profile
- `CLANG_TOOL_CHAIN_NO_*` per-feature switches — collapsed into profile
  rewriting at install time
- `SCCACHE_*` — sccache is gone

## 6. Backward-compat during migration

Phase 6 adds forwarders. Old entry points:

```python
def clang_main() -> NoReturn:  # was: legacy execute_tool dispatch
    import sys
    sys.stderr.write(
        "clang-tool-chain-c is deprecated; use clang-tool-chain-clang. "
        "Forwarding now.\n"
    )
    from ..zccache_shim import exec_via_zccache
    exec_via_zccache("clang", use_cache=False, abi="auto")
```

Old MSVC variants forward with `abi="msvc"`. Old sccache variants forward
with `use_cache=True` (zccache replaces sccache; `SCCACHE_*` env vars are
ignored on the new path).

Legacy `CLANG_TOOL_CHAIN_PY_TRAMPOLINE=1` is a no-op and logs a warning.
It's removed entirely in Phase 7.
