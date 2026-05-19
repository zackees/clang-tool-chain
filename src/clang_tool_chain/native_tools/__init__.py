"""
Native C++ tool sources bundled with clang-tool-chain.

Each .cpp file in this package is a single-file C++ tool that can be compiled
using the bundled Clang toolchain via `clang-tool-chain compile-native <dir>`.

The TOOL_REGISTRY maps tool IDs to their build descriptors. To add a new tool,
drop a single-file .cpp into this directory and add an entry to TOOL_REGISTRY.
"""

from dataclasses import dataclass, field


@dataclass(frozen=True)
class NativeTool:
    """Build descriptor for a single-file native C++ tool."""

    source: str  # Source filename relative to this package (e.g. "launcher.cpp")
    output: str  # Primary output binary name WITHOUT extension (e.g. "ctc-clang")
    aliases: list[str] = field(default_factory=list)  # Extra names (symlinks/copies)
    std: str = "c++17"  # C++ standard


TOOL_REGISTRY: dict[str, NativeTool] = {
    "emcc": NativeTool(
        source="launcher_emcc.cpp",
        output="ctc-emcc",
        aliases=["ctc-em++"],
    ),
    "wasmld": NativeTool(
        source="launcher_wasmld.cpp",
        output="ctc-wasm-ld",
    ),
    # Unified native launcher: one C++ source -> one compiled binary -> N
    # hardlinks/copies. argv[0] dispatch selects between:
    #   - SPECIAL PATH for ctc-clang / ctc-clang++ / ctc-clang-cpp — runs
    #     clang_launcher.cpp's full ABI-profile / sysroot / target / lib-deploy
    #     dispatch (included into launcher_clang_tool.cpp via #include).
    #   - FAST PATH for everything else — simple "find <install>/bin/<name>{ext}
    #     and exec". Covers LLVM utilities (llvm-ar/nm/strip/...), the lld
    #     linker variants, clang-query, and LLDB tools.
    # clang_launcher.cpp is no longer a standalone TOOL_REGISTRY entry — it's
    # consumed by launcher_clang_tool.cpp. Keep the alias list in sync with
    # launcher_clang_tool.cpp's FAST_PATH_TOOLS table.
    "clang_tool": NativeTool(
        source="launcher_clang_tool.cpp",
        output="ctc-clang",
        aliases=[
            # complex clang dispatch path
            "ctc-clang++",
            "ctc-clang-cpp",
            # linker variants (all alias the same lld binary internally)
            "ctc-lld",
            "ctc-ld.lld",
            "ctc-ld64.lld",
            "ctc-lld-link",
            # archive / inspection / manipulation
            "ctc-llvm-ar",
            "ctc-llvm-nm",
            "ctc-llvm-objdump",
            "ctc-llvm-objcopy",
            "ctc-llvm-ranlib",
            "ctc-llvm-strip",
            "ctc-llvm-readobj",
            "ctc-llvm-dlltool",
            "ctc-llvm-lib",
            "ctc-llvm-symbolizer",
            # AST query
            "ctc-clang-query",
            # LLDB (separate install root)
            "ctc-lldb",
            "ctc-lldb-server",
            # IWYU (separate install root); ctc-iwyu dispatches to
            # include-what-you-use{ext} via the alias→binary override
            # in launcher_clang_tool.cpp.
            "ctc-iwyu",
            # clang-format / clang-tidy (clang_extra install root)
            "ctc-clang-format",
            "ctc-clang-tidy",
        ],
    ),
    # One C++ source -> one binary -> 17 hardlinks/copies. argv[0] dispatch
    # selects which emscripten Python tool to invoke. Keep this list in sync
    # with the `known[]` whitelist in launcher_emtool.cpp:detect_tool_name and
    # the [project.scripts] block in pyproject.toml.
    "emtool": NativeTool(
        source="launcher_emtool.cpp",
        output="ctc-emar",
        aliases=[
            # archive / inspection
            "ctc-emstrip",
            "ctc-emranlib",
            "ctc-emnm",
            "ctc-emsize",
            "ctc-emsymbolizer",
            "ctc-emdwp",
            "ctc-emcoverage",
            "ctc-emprofile",
            # build orchestration
            "ctc-emcmake",
            "ctc-emmake",
            "ctc-emconfigure",
            "ctc-emscons",
            "ctc-embuilder",
            # misc
            "ctc-em-config",
            "ctc-emrun",
            "ctc-emscan-deps",
        ],
    ),
}
