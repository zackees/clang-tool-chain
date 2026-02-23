"""
Generate .def files from DLL export tables using llvm-readobj.

This module provides a cross-platform alternative to MinGW's gendef tool.
It uses llvm-readobj --coff-exports to extract the export table from a PE/COFF
DLL and generates a standard .def file that can be used with llvm-dlltool to
create import libraries.

Usage:
    clang-tool-chain-gendef mylib.dll              # writes mylib.def
    clang-tool-chain-gendef -o custom.def mylib.dll # writes custom.def
    clang-tool-chain-gendef - mylib.dll             # writes to stdout
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

from ..platform.paths import find_tool_binary


def _parse_coff_exports(readobj_output: str) -> list[dict[str, str]]:
    """Parse llvm-readobj --coff-exports output into a list of export entries."""
    exports: list[dict[str, str]] = []
    current: dict[str, str] = {}

    for line in readobj_output.splitlines():
        line = line.strip()
        if line == "Export {":
            current = {}
        elif line == "}":
            if current:
                exports.append(current)
                current = {}
        else:
            match = re.match(r"(\w+):\s+(.*)", line)
            if match:
                current[match.group(1)] = match.group(2).strip()

    return exports


def _generate_def_content(dll_name: str, exports: list[dict[str, str]]) -> str:
    """Generate .def file content from parsed exports."""
    lines = [f"LIBRARY {dll_name}", "EXPORTS"]

    for export in exports:
        name = export.get("Name", "")
        if not name:
            continue

        # Skip forwarded exports (they point to another DLL)
        if "ForwardedTo" in export:
            continue

        ordinal = export.get("Ordinal", "")
        entry = f"    {name}"
        if ordinal:
            entry += f" @{ordinal}"

        lines.append(entry)

    return "\n".join(lines) + "\n"


def generate_def_from_dll(dll_path: str | Path, output_path: str | Path | None = None) -> str:
    """
    Generate a .def file from a DLL's export table.

    Args:
        dll_path: Path to the DLL file.
        output_path: Path to write the .def file. If None, derives from dll_path.
                     If "-", returns content without writing.

    Returns:
        The generated .def file content.
    """
    dll_path = Path(dll_path)
    if not dll_path.exists():
        print(f"Error: DLL not found: {dll_path}", file=sys.stderr)
        sys.exit(1)

    readobj_path = find_tool_binary("llvm-readobj")

    result = subprocess.run(
        [str(readobj_path), "--coff-exports", str(dll_path)],
        capture_output=True,
        text=True,
        timeout=30,
    )

    if result.returncode != 0:
        print(f"Error: llvm-readobj failed: {result.stderr}", file=sys.stderr)
        sys.exit(1)

    exports = _parse_coff_exports(result.stdout)
    dll_name = dll_path.name
    content = _generate_def_content(dll_name, exports)

    if output_path != "-":
        output_path = dll_path.with_suffix(".def") if output_path is None else Path(output_path)
        output_path.write_text(content, encoding="utf-8")
        print(f"Generated {output_path} ({len(exports)} exports)")

    return content


def gendef_main() -> int:
    """Entry point for clang-tool-chain-gendef command."""
    import argparse

    parser = argparse.ArgumentParser(
        prog="clang-tool-chain-gendef",
        description="Generate .def files from DLL export tables (uses llvm-readobj).",
    )
    parser.add_argument("dll", help="Path to the DLL file")
    parser.add_argument(
        "-o",
        "--output",
        default=None,
        help="Output .def file path (default: <dllname>.def, use '-' for stdout)",
    )

    args = parser.parse_args()

    content = generate_def_from_dll(args.dll, args.output)

    if args.output == "-":
        sys.stdout.write(content)

    return 0
