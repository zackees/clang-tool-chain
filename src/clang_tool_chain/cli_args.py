"""
Argument dataclasses for clang-tool-chain CLI commands.

This module contains dataclass representations of parsed command-line arguments
for various entry points in the clang-tool-chain package. These dataclasses
provide type-safe, structured access to command arguments.
"""

from dataclasses import dataclass, field


@dataclass
class BuildArgs:
    """Arguments for clang-tool-chain-build command."""

    source_file: str
    output_file: str
    compiler_flags: list[str] = field(default_factory=list)


@dataclass
class BuildRunArgs:
    """Arguments for clang-tool-chain-build-run command."""

    cached: bool
    source_file: str
    compiler_flags: list[str] = field(default_factory=list)
    program_args: list[str] = field(default_factory=list)


@dataclass
class LldbArgs:
    """Arguments for clang-tool-chain-lldb command."""

    print_mode: bool
    executable: str | None
    lldb_args: list[str] = field(default_factory=list)
