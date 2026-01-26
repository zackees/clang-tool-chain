"""
Linker configuration and management for clang-tool-chain.

This package provides linker-related functionality including:
- LLD (LLVM Linker) configuration and forcing
- Linker flag translation for cross-platform compatibility
- Platform-specific linker selection logic
"""

from clang_tool_chain.linker.lld import (
    _add_lld_linker_if_needed,
    _should_force_lld,
    _translate_linker_flags_for_macos_lld,
)

__all__ = [
    "_add_lld_linker_if_needed",
    "_should_force_lld",
    "_translate_linker_flags_for_macos_lld",
]
