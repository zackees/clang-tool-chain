"""
Inlined Build Directives Parser

This module parses build directives embedded in C++ source files.
Directives are single-line comments at the top of the file that specify
build configuration like library dependencies, compiler flags, etc.

Example directives:
    // @link: pthread
    // @link: [pthread, m, dl]
    // @cflags: -O2 -Wall
    // @std: c++17
    // @platform: linux
    //   @link: pthread
"""

from __future__ import annotations

import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class ParsedDirectives:
    """Container for parsed directives from a source file."""

    # Core build configuration
    links: list[str] = field(default_factory=list)
    cflags: list[str] = field(default_factory=list)
    ldflags: list[str] = field(default_factory=list)
    includes: list[str] = field(default_factory=list)
    std: str | None = None

    # Package management
    pkg_config: list[str] = field(default_factory=list)
    requires: list[str] = field(default_factory=list)

    # Platform-specific overrides
    platform_overrides: dict[str, ParsedDirectives] = field(default_factory=dict)

    # Source file info
    source_path: Path | None = None

    def get_linker_args(self) -> list[str]:
        """Generate linker arguments from parsed directives."""
        args = []

        # Add -l flags for libraries
        for lib in self.links:
            if lib.startswith("/") or lib.endswith(".a") or lib.endswith(".lib"):
                # Absolute path to library
                args.append(lib)
            else:
                # Library name
                args.append(f"-l{lib}")

        # Add ldflags
        args.extend(self.ldflags)

        return args

    def get_compiler_args(self) -> list[str]:
        """Generate compiler arguments from parsed directives."""
        args = []

        # C++ standard
        if self.std:
            args.append(f"-std={self.std}")

        # Include paths
        for inc in self.includes:
            args.append(f"-I{inc}")

        # Compiler flags
        args.extend(self.cflags)

        return args

    def get_all_args(self) -> list[str]:
        """Get all compiler and linker arguments."""
        return self.get_compiler_args() + self.get_linker_args()

    def merge_platform(self, platform: str) -> ParsedDirectives:
        """Create a new ParsedDirectives with platform overrides applied."""
        if platform not in self.platform_overrides:
            return self

        result = ParsedDirectives(
            links=self.links.copy(),
            cflags=self.cflags.copy(),
            ldflags=self.ldflags.copy(),
            includes=self.includes.copy(),
            std=self.std,
            pkg_config=self.pkg_config.copy(),
            requires=self.requires.copy(),
            source_path=self.source_path,
        )

        override = self.platform_overrides[platform]
        result.links.extend(override.links)
        result.cflags.extend(override.cflags)
        result.ldflags.extend(override.ldflags)
        result.includes.extend(override.includes)
        result.pkg_config.extend(override.pkg_config)
        result.requires.extend(override.requires)

        if override.std:
            result.std = override.std

        return result


class DirectiveParser:
    """Parser for inlined build directives in C++ source files."""

    # Regex to match directive lines: // @directive: value
    # Note: [\w-]+ allows hyphens in directive names (e.g., pkg-config)
    DIRECTIVE_PATTERN = re.compile(r"^\s*//\s*@([\w-]+):\s*(.+?)(?:\s*//.*)?$", re.MULTILINE)

    # Regex to match list values: [a, b, c]
    LIST_PATTERN = re.compile(r"^\[(.+)\]$")

    # Platform names
    PLATFORMS = {"linux", "windows", "darwin", "freebsd", "openbsd", "netbsd"}

    def __init__(self):
        self._current_platform = self._detect_platform()

    @staticmethod
    def _detect_platform() -> str:
        """Detect the current platform."""
        if sys.platform.startswith("linux"):
            return "linux"
        elif sys.platform == "darwin":
            return "darwin"
        elif sys.platform == "win32":
            return "windows"
        elif sys.platform.startswith("freebsd"):
            return "freebsd"
        else:
            return sys.platform

    def parse_file(self, filepath: str | Path) -> ParsedDirectives:
        """Parse directives from a source file."""
        filepath = Path(filepath)
        content = filepath.read_text(encoding="utf-8")
        result = self.parse_string(content)
        result.source_path = filepath
        return result

    def parse_string(self, content: str) -> ParsedDirectives:
        """Parse directives from source content."""
        result = ParsedDirectives()
        current_platform_directives: ParsedDirectives | None = None

        lines = content.splitlines()

        for line in lines:
            stripped = line.strip()

            # Stop parsing at first non-comment, non-empty line
            if stripped and not stripped.startswith("//"):
                break

            # Skip empty lines and regular comments
            if not stripped or (stripped.startswith("//") and "@" not in stripped):
                continue

            # Try to match directive
            match = self.DIRECTIVE_PATTERN.match(line)
            if not match:
                continue

            directive_name = match.group(1).lower()
            directive_value = match.group(2).strip()

            # Handle platform directive (changes context)
            if directive_name == "platform":
                platform_key = directive_value.lower()
                if platform_key not in result.platform_overrides:
                    result.platform_overrides[platform_key] = ParsedDirectives()
                current_platform_directives = result.platform_overrides[platform_key]
                continue

            # Check indentation for platform context
            # Indented directives belong to current platform
            if line.startswith("//") and not line.startswith("// @"):
                # Indented directive (starts with //   @)
                target = current_platform_directives if current_platform_directives else result
            else:
                # Non-indented, reset platform context
                if not stripped.startswith("//   "):
                    current_platform_directives = None
                target = result

            # Determine target based on indentation
            if current_platform_directives and "  " in line.split("@")[0]:
                target = current_platform_directives
            else:
                target = result

            # Parse the directive value
            value = self._parse_value(directive_value)

            # Apply directive to target
            self._apply_directive(target, directive_name, value)

        return result

    def _parse_value(self, value: str) -> Any:
        """Parse a directive value, handling lists and other special syntax."""
        # Check for list syntax: [a, b, c]
        list_match = self.LIST_PATTERN.match(value)
        if list_match:
            items = list_match.group(1)
            return [item.strip() for item in items.split(",")]

        # Check for conditional: value | condition
        if " | " in value:
            val, condition = value.split(" | ", 1)
            return {"value": val.strip(), "condition": condition.strip()}

        return value

    def _apply_directive(self, target: ParsedDirectives, name: str, value: Any) -> None:
        """Apply a parsed directive to the target ParsedDirectives."""
        if name == "link":
            if isinstance(value, list):
                target.links.extend(value)
            elif isinstance(value, dict):
                # Conditional value - TODO: evaluate condition
                target.links.append(value["value"])
            else:
                target.links.append(value)

        elif name == "cflags":
            if isinstance(value, list):
                target.cflags.extend(value)
            else:
                # Split space-separated flags
                target.cflags.extend(value.split())

        elif name == "ldflags":
            if isinstance(value, list):
                target.ldflags.extend(value)
            else:
                target.ldflags.extend(value.split())

        elif name == "include":
            if isinstance(value, list):
                target.includes.extend(value)
            else:
                target.includes.append(value)

        elif name == "std":
            target.std = value

        elif name == "pkg-config":
            if isinstance(value, list):
                target.pkg_config.extend(value)
            else:
                target.pkg_config.append(value)

        elif name == "require":
            if isinstance(value, list):
                target.requires.extend(value)
            else:
                target.requires.append(value)

    def parse_for_current_platform(self, content: str) -> ParsedDirectives:
        """Parse directives and apply platform-specific overrides."""
        base = self.parse_string(content)
        return base.merge_platform(self._current_platform)

    def parse_file_for_current_platform(self, filepath: str | Path) -> ParsedDirectives:
        """Parse file and apply platform-specific overrides."""
        base = self.parse_file(filepath)
        return base.merge_platform(self._current_platform)


def main():
    """CLI entry point for testing the parser."""
    import argparse

    arg_parser = argparse.ArgumentParser(description="Parse inlined build directives from C++ files")
    arg_parser.add_argument("file", help="C++ source file to parse")
    arg_parser.add_argument("--verbose", "-v", action="store_true", help="Verbose output")
    arg_parser.add_argument(
        "--platform",
        "-p",
        help="Override platform detection (linux, darwin, windows)",
    )

    args = arg_parser.parse_args()

    parser = DirectiveParser()
    if args.platform:
        parser._current_platform = args.platform

    directives = parser.parse_file_for_current_platform(args.file)

    print(f"Source: {directives.source_path}")
    print(f"Platform: {parser._current_platform}")
    print()

    if directives.std:
        print(f"C++ Standard: {directives.std}")

    if directives.links:
        print(f"Libraries: {', '.join(directives.links)}")

    if directives.cflags:
        print(f"CFLAGS: {' '.join(directives.cflags)}")

    if directives.ldflags:
        print(f"LDFLAGS: {' '.join(directives.ldflags)}")

    if directives.includes:
        print(f"Includes: {', '.join(directives.includes)}")

    if directives.pkg_config:
        print(f"pkg-config: {', '.join(directives.pkg_config)}")

    print()
    print("Compiler args:", " ".join(directives.get_compiler_args()))
    print("Linker args:", " ".join(directives.get_linker_args()))
    print()
    print("Full command line addition:")
    print(" ".join(directives.get_all_args()))


if __name__ == "__main__":
    main()
