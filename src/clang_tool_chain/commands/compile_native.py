"""
Compile all registered native C++ tools using the bundled Clang toolchain.

Tool sources live in ``clang_tool_chain.native_tools`` and are discovered
via TOOL_REGISTRY.  Each tool is a single-file C++17 program that compiles
to a portable binary with static runtime linking.

Usage:
    clang-tool-chain compile-native <output-dir>
"""

import importlib.resources as resources
import platform as platform_mod
import shlex
import shutil
import subprocess
import sys
from pathlib import Path

from ..native_tools import TOOL_REGISTRY, NativeTool

# ------------------------------------------------------------------
# Source resolution
# ------------------------------------------------------------------


def _find_tool_source(tool: NativeTool) -> Path | None:
    """Locate the .cpp source for *tool* in the package or dev tree."""
    # 1. importlib.resources — works for both installed and editable installs
    try:
        ref = resources.files("clang_tool_chain.native_tools").joinpath(tool.source)
        if hasattr(ref, "is_file") and ref.is_file():  # type: ignore[union-attr]
            return Path(str(ref))
    except (TypeError, AttributeError):
        pass

    # 2. Filesystem fallback relative to this file (development layout)
    pkg_dir = Path(__file__).resolve().parent.parent  # clang_tool_chain/
    candidate = pkg_dir / "native_tools" / tool.source
    if candidate.exists():
        return candidate

    return None


# ------------------------------------------------------------------
# Platform compile flags
# ------------------------------------------------------------------


def _platform_compile_flags(clang_bin_dir: Path, platform_name: str) -> list[str]:
    """Return platform-specific flags for a portable static binary."""
    flags: list[str] = []

    if platform_name == "linux":
        flags.extend(["-static-libstdc++", "-static-libgcc", "-lpthread"])

    elif platform_name == "win":
        flags.extend(["-static-libstdc++", "-static-libgcc"])
        arch = platform_mod.machine().lower()
        if arch in ("x86_64", "amd64"):
            target = "x86_64-w64-windows-gnu"
            sysroot_name = "x86_64-w64-mingw32"
        else:
            target = "aarch64-w64-windows-gnu"
            sysroot_name = "aarch64-w64-mingw32"

        clang_root = clang_bin_dir.parent
        sysroot = clang_root / sysroot_name
        cxx_include = clang_root / "include" / "c++" / "v1"
        mingw_include = clang_root / "include"

        if cxx_include.exists():
            flags.append(f"-I{cxx_include}")

        if sysroot.exists():
            flags.extend(
                [
                    f"--target={target}",
                    f"--sysroot={sysroot}",
                    "-stdlib=libc++",
                    "-rtlib=compiler-rt",
                    "-fuse-ld=lld",
                    "--unwindlib=libunwind",
                    f"-isystem{mingw_include}",
                    "-lpthread",
                ]
            )

    elif platform_name == "darwin":
        lld_path = clang_bin_dir.parent / "bin" / "lld"
        if lld_path.exists():
            flags.append("-fuse-ld=lld")

    return flags


# ------------------------------------------------------------------
# Single-tool compilation
# ------------------------------------------------------------------


def _compile_tool(
    tool: NativeTool,
    source_path: Path,
    output_dir: Path,
    clang_exe: Path,
    platform_flags: list[str],
    platform_name: str,
) -> int:
    """Compile one tool and create its aliases.  Returns 0 on success."""
    exe_suffix = ".exe" if platform_name == "win" else ""
    output_binary = output_dir / f"{tool.output}{exe_suffix}"

    cmd = [str(clang_exe), "-O3", f"-std={tool.std}"]
    cmd.extend(platform_flags)
    cmd.extend(["-o", str(output_binary), str(source_path)])

    print(f"Compiling: {shlex.join(cmd)}")
    result = subprocess.run(cmd)
    if result.returncode != 0:
        print(f"Error: compilation of {tool.source} failed (exit {result.returncode})", file=sys.stderr)
        return result.returncode

    # Create aliases (symlinks on Unix, copies on Windows)
    for alias in tool.aliases:
        alias_path = output_dir / f"{alias}{exe_suffix}"
        if platform_name == "win":
            shutil.copy2(str(output_binary), str(alias_path))
            print(f"Copied: {output_binary} -> {alias_path}")
        else:
            if alias_path.exists() or alias_path.is_symlink():
                alias_path.unlink()
            alias_path.symlink_to(f"{tool.output}{exe_suffix}")
            print(f"Symlink: {alias_path} -> {tool.output}{exe_suffix}")

    return 0


# ------------------------------------------------------------------
# Public API
# ------------------------------------------------------------------


def compile_native(output_dir: str) -> int:
    """
    Compile all registered native tools to *output_dir*.

    Returns:
        0 on success, non-zero on first failure.
    """
    output_path = Path(output_dir).resolve()
    output_path.mkdir(parents=True, exist_ok=True)

    # Ensure toolchain is installed
    from ..platform.detection import get_platform_binary_dir, get_platform_info

    try:
        clang_bin_dir = get_platform_binary_dir()
    except Exception as e:
        print(f"Error: Could not find clang toolchain: {e}", file=sys.stderr)
        print("Run: clang-tool-chain install clang", file=sys.stderr)
        return 1

    platform_name, _ = get_platform_info()
    clang_exe_name = "clang++.exe" if platform_name == "win" else "clang++"
    clang_exe = clang_bin_dir / clang_exe_name
    if not clang_exe.exists():
        print(f"Error: {clang_exe} not found", file=sys.stderr)
        return 1

    platform_flags = _platform_compile_flags(clang_bin_dir, platform_name)

    # Compile each registered tool
    compiled: list[str] = []
    for tool_id, tool in TOOL_REGISTRY.items():
        source = _find_tool_source(tool)
        if source is None:
            print(f"Error: source not found for tool '{tool_id}' ({tool.source})", file=sys.stderr)
            return 1

        print(f"Source: {source}")
        rc = _compile_tool(tool, source, output_path, clang_exe, platform_flags, platform_name)
        if rc != 0:
            return rc

        exe_suffix = ".exe" if platform_name == "win" else ""
        compiled.append(f"  {output_path / (tool.output + exe_suffix)}")
        for alias in tool.aliases:
            compiled.append(f"  {output_path / (alias + exe_suffix)}")

    print(f"\nNative tools built successfully ({len(TOOL_REGISTRY)} tool(s)):")
    for line in compiled:
        print(line)
    return 0


def compile_native_main() -> int:
    """Entry point for ``clang-tool-chain-compile-native``."""
    if len(sys.argv) < 2:
        print("Usage: clang-tool-chain compile-native <output-dir>", file=sys.stderr)
        print("", file=sys.stderr)
        print("Compiles all registered native C++ tools to the specified directory.", file=sys.stderr)
        tools = ", ".join(f"{t.output} ({t.source})" for t in TOOL_REGISTRY.values())
        print(f"Tools: {tools}", file=sys.stderr)
        return 1

    return compile_native(sys.argv[1])
