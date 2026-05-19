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
    "launcher": NativeTool(
        source="clang_launcher.cpp",
        output="ctc-clang",
        aliases=["ctc-clang++"],
    ),
    "emcc": NativeTool(
        source="launcher_emcc.cpp",
        output="ctc-emcc",
        aliases=["ctc-em++"],
    ),
    "wasmld": NativeTool(
        source="launcher_wasmld.cpp",
        output="ctc-wasm-ld",
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
