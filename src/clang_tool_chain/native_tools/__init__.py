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
}
