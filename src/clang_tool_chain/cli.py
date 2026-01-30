"""
Main entry point for clang-tool-chain CLI.

Provides commands for managing and using the LLVM toolchain.
"""

import argparse
import subprocess
import sys
from typing import Any, NoReturn

from clang_tool_chain import sccache_runner, wrapper
from clang_tool_chain.interrupt_utils import handle_keyboard_interrupt_properly

try:
    from .__version__ import __version__
except ImportError:
    __version__ = "unknown"


def safe_print(*args: Any, **kwargs: Any) -> None:
    """
    Print function that handles encoding errors gracefully.

    Falls back to ASCII characters if the console doesn't support Unicode.
    This ensures compatibility with Windows CP1252 and other limited encodings.
    """
    try:
        # Try to print normally first
        print(*args, **kwargs)
    except (UnicodeEncodeError, UnicodeDecodeError):
        # If encoding fails, replace Unicode characters with ASCII equivalents
        file = kwargs.get("file", sys.stdout)
        encoding = getattr(file, "encoding", "utf-8") or "utf-8"

        safe_args = []
        for arg in args:
            text = str(arg)

            # First, replace known Unicode characters with ASCII equivalents
            text = text.replace("✓", "[OK]")
            text = text.replace("✗", "[FAIL]")

            # Then, replace any remaining unencodable characters
            safe_text = []
            for char in text:
                try:
                    char.encode(encoding)
                    safe_text.append(char)
                except (UnicodeEncodeError, UnicodeDecodeError):
                    # Replace unencodable character with its Unicode codepoint
                    codepoint = f"U+{ord(char):04X}"
                    safe_text.append(f"[{codepoint}]")

            safe_args.append("".join(safe_text))

        # Try printing again with replaced characters
        try:
            print(*safe_args, **kwargs)
        except (UnicodeEncodeError, UnicodeDecodeError):
            # Last resort: write to buffer with error handling
            if hasattr(file, "buffer"):
                output = " ".join(safe_args)
                end_value = kwargs.get("end")
                if end_value is not None:
                    output += str(end_value)
                else:
                    output += "\n"
                file.buffer.write(output.encode("ascii", errors="backslashreplace"))
                file.flush()
            else:
                # Ultimate fallback: convert to ASCII with backslashreplace
                for arg in safe_args:
                    file.write(arg.encode("ascii", errors="backslashreplace").decode("ascii"))
                file.write("\n")


def cmd_info(args: argparse.Namespace) -> int:
    """Display information about the toolchain installation."""
    print("Clang Tool Chain - LLVM/Clang Distribution")
    print("=" * 60)
    print()

    # Platform information
    try:
        platform_name, arch = wrapper.get_platform_info()
        print(f"Platform:     {platform_name}")
        print(f"Architecture: {arch}")
        print()
    except RuntimeError as e:
        print(f"Error detecting platform: {e}")
        return 1

    # Windows GNU ABI information
    if platform_name == "win":
        print("Windows Target Configuration:")
        print("  Default ABI:  GNU (x86_64-w64-windows-gnu)")
        print("  MSVC ABI:     Available via clang-tool-chain-c-msvc")
        print("                and clang-tool-chain-cpp-msvc")
        print()
        print("Why GNU ABI is default:")
        print("  - Cross-platform consistency (same ABI on Linux/macOS/Windows)")
        print("  - C++11 strict mode support (MSVC headers require C++14+)")
        print("  - Arduino/embedded compatibility (matches GCC toolchain)")
        print()

    # Assets directory
    assets_dir = wrapper.get_assets_dir()
    print(f"Assets directory: {assets_dir}")
    print(f"Assets exist:     {assets_dir.exists()}")
    print()

    # Binary directory
    try:
        bin_dir = wrapper.get_platform_binary_dir()
        print(f"Binary directory: {bin_dir}")
        print("Binaries installed: Yes")
        print()

        # List available tools
        if bin_dir.exists():
            binaries = sorted(
                [f.stem for f in bin_dir.iterdir() if f.is_file()],
                key=str.lower,
            )
            print(f"Available tools ({len(binaries)}):")
            for binary in binaries:
                print(f"  - {binary}")
    except RuntimeError:
        print("Binaries installed: No")
        print()
        print("To install binaries, run:")
        print("  python scripts/download_binaries.py --current-only")
        print("  python scripts/strip_binaries.py <extracted_dir> <output_dir> --platform <platform>")

    return 0


def cmd_version(args: argparse.Namespace) -> int:
    """Display version of a specific tool."""
    tool_name: str = args.tool

    # Map common names to actual tool names
    tool_map = {
        "c": "clang",
        "cpp": "clang++",
        "c++": "clang++",
        "ld": "lld",
    }

    actual_tool: str = tool_map.get(tool_name, tool_name)

    try:
        wrapper.find_tool_binary(actual_tool)
        result = wrapper.run_tool(actual_tool, ["--version"])
        return result
    except RuntimeError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1


def cmd_list_tools(args: argparse.Namespace) -> int:
    """List all available wrapper tools."""
    print("Available clang-tool-chain commands:")
    print("=" * 60)
    print()

    tools = [
        ("clang-tool-chain-c", "C compiler (clang) - GNU ABI on Windows"),
        ("clang-tool-chain-cpp", "C++ compiler (clang++) - GNU ABI on Windows"),
        ("clang-tool-chain-c-msvc", "C compiler (clang) - MSVC ABI (Windows only)"),
        ("clang-tool-chain-cpp-msvc", "C++ compiler (clang++) - MSVC ABI (Windows only)"),
        ("clang-tool-chain-ld", "LLVM linker (lld/lld-link)"),
        ("clang-tool-chain-ar", "Archive tool (llvm-ar)"),
        ("clang-tool-chain-nm", "Symbol table viewer (llvm-nm)"),
        ("clang-tool-chain-objdump", "Object file dumper (llvm-objdump)"),
        ("clang-tool-chain-objcopy", "Object copying tool (llvm-objcopy)"),
        ("clang-tool-chain-ranlib", "Archive index generator (llvm-ranlib)"),
        ("clang-tool-chain-strip", "Symbol stripper (llvm-strip)"),
        ("clang-tool-chain-readelf", "ELF file reader (llvm-readelf)"),
        ("clang-tool-chain-as", "LLVM assembler (llvm-as)"),
        ("clang-tool-chain-dis", "LLVM disassembler (llvm-dis)"),
        ("clang-tool-chain-format", "Code formatter (clang-format)"),
        ("clang-tool-chain-tidy", "Static analyzer (clang-tidy)"),
    ]

    for cmd, desc in tools:
        print(f"  {cmd:30s} - {desc}")

    print()
    print("sccache integration (requires sccache in PATH):")
    print("=" * 60)
    print()

    sccache_tools = [
        ("clang-tool-chain-sccache", "Direct sccache access (stats, management)"),
        ("clang-tool-chain-sccache-c", "sccache + C compiler (clang)"),
        ("clang-tool-chain-sccache-cpp", "sccache + C++ compiler (clang++)"),
    ]

    for cmd, desc in sccache_tools:
        print(f"  {cmd:30s} - {desc}")

    print()
    print("For more information, run:")
    print("  clang-tool-chain info")

    return 0


def cmd_path(args: argparse.Namespace) -> int:
    """Display the path to the binary directory or a specific tool."""
    try:
        if args.tool:
            tool_name: str = args.tool
            # Map common names to actual tool names
            tool_map = {
                "c": "clang",
                "cpp": "clang++",
                "c++": "clang++",
                "ld": "lld",
            }

            actual_tool: str = tool_map.get(tool_name, tool_name)
            tool_path = wrapper.find_tool_binary(actual_tool)
            print(tool_path)
        else:
            bin_dir = wrapper.get_platform_binary_dir()
            print(bin_dir)
        return 0
    except RuntimeError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1


def cmd_package_version(args: argparse.Namespace) -> int:
    """Display the package version."""
    print(f"clang-tool-chain version: {__version__}")
    print()

    if args.verbose:
        # Show more detailed version information
        print("Package Information:")
        print("=" * 60)
        print("  Package:       clang-tool-chain")
        print(f"  Version:       {__version__}")
        print()

        # Try to get actual clang version from installed binaries
        try:
            platform_name, arch = wrapper.get_platform_info()
            print("Platform Information:")
            print(f"  Platform:      {platform_name}")
            print(f"  Architecture:  {arch}")
            print()

            # Try to get installed clang version
            try:
                wrapper.find_tool_binary("clang")
                print("Installed LLVM/Clang:")
                result = wrapper.run_tool("clang", ["--version"])
                if result != 0:
                    print("  (Unable to determine version)")
            except RuntimeError:
                print("Installed LLVM/Clang:")
                print("  Not installed yet")
                print()
                print("To install binaries, run:")
                print("  python scripts/download_binaries.py --current-only")
                print("  python scripts/strip_binaries.py <extracted_dir> <output_dir> --platform <platform>")
        except RuntimeError as e:
            print(f"Error: {e}", file=sys.stderr)

    return 0


def cmd_install_clang(args: argparse.Namespace) -> int:
    """Pre-download and install the core Clang/LLVM toolchain."""
    from . import env_breadcrumbs, installer
    from .path_utils import get_install_dir

    print("Clang Tool Chain - Install Clang/LLVM")
    print("=" * 60)
    print()

    # Get current platform info
    try:
        platform_name, arch = wrapper.get_platform_info()
        print(f"Platform:     {platform_name}")
        print(f"Architecture: {arch}")
        print()
    except RuntimeError as e:
        print(f"Error detecting platform: {e}")
        return 1

    # Check if already installed (without triggering auto-download)
    if installer.is_toolchain_installed(platform_name, arch):
        install_dir = get_install_dir(platform_name, arch)
        safe_print("✓ Clang/LLVM toolchain already installed at:")
        print(f"  {install_dir}")
        print()

        # Mark as installed in database
        env_breadcrumbs.mark_component_installed("clang", str(install_dir))

        print("To verify installation, run:")
        print("  clang-tool-chain-test")
        return 0

    # Download and install
    print("Downloading and installing Clang/LLVM toolchain...")
    print()
    print("This will download approximately:")
    if platform_name == "win":
        print("  - Windows GNU ABI: ~90 MB (includes MinGW sysroot)")
        print("  - Windows MSVC ABI: ~71 MB")
    else:
        print("  - ~71-91 MB (compressed)")
    print()

    try:
        # Use the installer to ensure toolchain is installed
        installer.ensure_toolchain(platform_name, arch)

        # Verify installation
        bin_dir = wrapper.get_platform_binary_dir()
        if bin_dir.exists():
            print()
            print("=" * 60)
            safe_print("✓ Installation Complete!")
            print()
            print(f"Toolchain installed at: {bin_dir.parent}")
            print()

            # Mark as installed in database
            env_breadcrumbs.mark_component_installed("clang", str(bin_dir.parent))

            # Count tools
            tool_count = len(list(bin_dir.glob("*")))
            print(f"Available tools: {tool_count}")
            print()

            # Show some key tools
            key_tools = ["clang", "clang++", "lld", "llvm-ar", "clang-format"]
            print("Key tools installed:")
            for tool in key_tools:
                tool_name = f"{tool}.exe" if platform_name == "win" else tool
                tool_path = bin_dir / tool_name
                if tool_path.exists():
                    safe_print(f"  ✓ {tool}")
            print()

            print("To use these tools:")
            print("  clang-tool-chain-c hello.c -o hello")
            print("  clang-tool-chain-cpp hello.cpp -o hello")
            print()
            print("To verify installation:")
            print("  clang-tool-chain-test")
            print()
            print("To install additional components:")
            print("  - IWYU: Run 'clang-tool-chain-iwyu' (auto-downloads on first use)")
            print("  - Emscripten: Run 'clang-tool-chain-emcc' (auto-downloads on first use)")
            print()
            return 0
        else:
            safe_print("✗ Installation verification failed - bin directory not found")
            return 1

    except KeyboardInterrupt as ke:
        handle_keyboard_interrupt_properly(ke)
    except Exception as e:
        print()
        safe_print(f"✗ Installation failed: {e}")
        return 1


def cmd_purge(args: argparse.Namespace) -> int:
    """Remove all downloaded toolchains and cached data."""
    from . import component_db, downloader

    toolchain_dir = downloader.get_home_toolchain_dir()

    if not toolchain_dir.exists():
        print(f"No toolchain directory found at: {toolchain_dir}")
        print("Nothing to purge.")
        return 0

    # Get all installed components and PATH components
    all_components = component_db.get_all_installed_components()
    path_components = component_db.get_all_path_components()

    # Show what will be removed
    print("Clang Tool Chain - Purge")
    print("=" * 60)
    print()
    print("This will remove all downloaded toolchains from:")
    print(f"  {toolchain_dir}")
    print()

    # Show installed components
    if all_components:
        print("Installed components:")
        for comp in all_components:
            status = " (in PATH)" if comp.in_path else ""
            install_path = comp.install_path if comp.install_path else "unknown"
            print(f"  - {comp.name}: {install_path}{status}")
        print()

    # Show PATH components that will be cleaned up
    if path_components:
        print("Components in system PATH (will be removed from PATH):")
        for component, bin_path in path_components:
            print(f"  - {component}: {bin_path}")
        print()

    # Calculate total size
    try:
        total_size = sum(f.stat().st_size for f in toolchain_dir.rglob("*") if f.is_file())
        total_size_mb = total_size / (1024 * 1024)
        print(f"Total size: {total_size_mb:.2f} MB")
    except KeyboardInterrupt as ke:
        handle_keyboard_interrupt_properly(ke)
    except Exception:
        print("Total size: (unable to calculate)")

    print()

    # Ask for confirmation unless --yes flag is provided
    if not args.yes:
        response = input("Are you sure you want to remove all toolchains? [y/N]: ")
        if response.lower() not in ("y", "yes"):
            print("Purge cancelled.")
            return 0

    # Remove environment PATH entries first (if setenvironment is available)
    if path_components:
        print()
        print("Removing components from system PATH...")
        try:
            import setenvironment

            for component, bin_path in path_components:
                try:
                    setenvironment.remove_env_path(bin_path)
                    safe_print(f"  ✓ Removed {component} from PATH")
                except KeyboardInterrupt as ke:
                    handle_keyboard_interrupt_properly(ke)
                except Exception as e:
                    safe_print(f"  ✗ Failed to remove {component} from PATH: {e}")
        except ImportError:
            safe_print("  ⚠ setenvironment not installed, cannot auto-remove from PATH")
            print("  Please run the following commands manually:")
            for component, _bin_path in path_components:
                print(f"    clang-tool-chain uninstall {component}-env")

    # Remove the directory
    print()
    print("Removing toolchain directory...")
    try:
        downloader._robust_rmtree(toolchain_dir)
        safe_print("✓ Successfully removed all toolchains.")
        print()
        if path_components:
            print("Note: PATH changes take effect in new terminal sessions.")
            print()
        print("Toolchains will be re-downloaded on next use of clang-tool-chain commands.")

        # Clear the component database
        component_db.remove_all_components()

        return 0
    except KeyboardInterrupt as ke:
        handle_keyboard_interrupt_properly(ke)
    except Exception as e:
        safe_print(f"✗ Failed to remove toolchain directory: {e}")
        return 1


def cmd_install_clang_env(args: argparse.Namespace) -> int:
    """Install Clang/LLVM toolchain binaries to system environment (PATH)."""
    import setenvironment

    from . import env_breadcrumbs, installer

    print("Clang Tool Chain - Install to Environment")
    print("=" * 60)
    print()

    # First, ensure clang is installed
    try:
        platform_name, arch = wrapper.get_platform_info()
    except RuntimeError as e:
        print(f"Error: Failed to detect platform: {e}")
        return 1

    if not installer.is_toolchain_installed(platform_name, arch):
        print("Clang/LLVM toolchain not found. Installing first...")
        print()
        installer.ensure_toolchain(platform_name, arch)
        print()
        safe_print("✓ Clang/LLVM toolchain installed")
        print()

    # Get the binary directory
    try:
        bin_dir = wrapper.get_platform_binary_dir()
    except RuntimeError as e:
        print(f"Error: Failed to locate toolchain binaries: {e}")
        return 1

    if not bin_dir.exists():
        print(f"Error: Binary directory does not exist: {bin_dir}")
        print()
        print("Installation failed. Please try running:")
        print("  clang-tool-chain install clang")
        return 1

    print(f"Binary directory: {bin_dir}")
    print()

    # Add bin directory to PATH
    print("Adding toolchain bin directory to PATH...")
    try:
        setenvironment.add_env_path(str(bin_dir))
        safe_print(f"✓ Added to PATH: {bin_dir}")

        # Mark as installed to environment (for automatic cleanup during purge)
        env_breadcrumbs.mark_component_installed_to_env("clang", str(bin_dir))
    except KeyboardInterrupt as ke:
        handle_keyboard_interrupt_properly(ke)
    except Exception as e:
        safe_print(f"✗ Failed to add to PATH: {e}")
        return 1

    print()
    print("=" * 60)
    print("Installation Complete!")
    print()
    print("The following tools are now available globally:")
    print("  clang, clang++, lld, llvm-ar, llvm-nm, llvm-objdump,")
    print("  llvm-strip, clang-format, clang-tidy, and more...")
    print()
    print("IMPORTANT: You may need to:")
    print("  - Restart your terminal/shell for changes to take effect")
    print("  - On some systems, log out and log back in")
    print()
    print("To verify installation, open a new terminal and run:")
    print("  clang --version")
    print()

    return 0


def cmd_uninstall_clang_env(args: argparse.Namespace) -> int:
    """Remove Clang/LLVM toolchain binaries from system environment (PATH)."""
    import setenvironment

    from . import env_breadcrumbs

    print("Clang Tool Chain - Uninstall from Environment")
    print("=" * 60)
    print()

    # Get the binary directory
    try:
        bin_dir = wrapper.get_platform_binary_dir()
    except RuntimeError as e:
        print(f"Error: Failed to locate toolchain binaries: {e}")
        return 1

    print(f"Binary directory: {bin_dir}")
    print()

    # Remove bin directory from PATH
    print("Removing toolchain bin directory from PATH...")
    try:
        setenvironment.remove_env_path(str(bin_dir))
        safe_print(f"✓ Removed from PATH: {bin_dir}")

        # Remove breadcrumb
        env_breadcrumbs.unmark_component_installed_to_env("clang")
    except KeyboardInterrupt as ke:
        handle_keyboard_interrupt_properly(ke)
    except Exception as e:
        safe_print(f"✗ Failed to remove from PATH: {e}")
        return 1

    print()
    print("=" * 60)
    print("Uninstallation Complete!")
    print()
    print("The toolchain binaries are no longer in your system PATH.")
    print()
    print("IMPORTANT: You may need to:")
    print("  - Restart your terminal/shell for changes to take effect")
    print("  - On some systems, log out and log back in")
    print()
    print("You can still use the tools via clang-tool-chain wrapper commands:")
    print("  clang-tool-chain-c, clang-tool-chain-cpp, etc.")
    print()

    return 0


def cmd_install_cosmocc(args: argparse.Namespace) -> int:
    """Pre-download and install the Cosmopolitan (cosmocc) toolchain."""
    from . import env_breadcrumbs, installer
    from .path_utils import get_cosmocc_install_dir

    print("Clang Tool Chain - Install Cosmopolitan (cosmocc)")
    print("=" * 60)
    print()

    # Get current platform info (for display and file extension handling only)
    try:
        platform_name, arch = wrapper.get_platform_info()
        print(f"Current platform: {platform_name}/{arch}")
        print("Note: Cosmocc is universal and runs on all platforms")
        print()
    except RuntimeError as e:
        print(f"Error detecting platform: {e}")
        return 1

    # Check if already installed (universal - no platform/arch args needed)
    if installer.is_cosmocc_installed():
        install_dir = get_cosmocc_install_dir()
        safe_print("✓ Cosmopolitan (cosmocc) toolchain already installed at:")
        print(f"  {install_dir}")
        print()

        # Mark as installed in database
        env_breadcrumbs.mark_component_installed("cosmocc", str(install_dir))

        print("To verify installation, run:")
        print("  clang-tool-chain-cosmocc --version")
        return 0

    # Download and install
    print("Downloading and installing universal Cosmopolitan (cosmocc) toolchain...")
    print()
    print("This will download approximately:")
    print("  - ~441 MB (Cosmopolitan produces universal 'Actually Portable Executables')")
    print()
    print("Cosmopolitan features:")
    print("  - Single binary that runs on Windows, Linux, macOS, FreeBSD, NetBSD, OpenBSD")
    print("  - No runtime dependencies required")
    print("  - Executables are completely self-contained")
    print()

    try:
        # Use the installer to ensure cosmocc is installed (universal - no platform/arch args needed)
        installer.ensure_cosmocc()

        # Verify installation (universal - no platform/arch args needed)
        install_dir = get_cosmocc_install_dir()
        bin_dir = install_dir / "bin"
        if bin_dir.exists():
            print()
            print("=" * 60)
            safe_print("✓ Universal Installation Complete!")
            print()
            print(f"Toolchain installed at: {install_dir}")
            print()

            # Mark as installed in database
            env_breadcrumbs.mark_component_installed("cosmocc", str(install_dir))

            # Count tools
            tool_count = len(list(bin_dir.glob("*")))
            print(f"Available tools: {tool_count}")
            print()

            # Show some key tools
            key_tools = ["cosmocc", "cosmoc++"]
            print("Key tools installed:")
            for tool in key_tools:
                # On Windows, cosmocc tools might have .exe or no extension
                if platform_name == "win":
                    for ext in [".exe", ".bat", ""]:
                        tool_path = bin_dir / f"{tool}{ext}"
                        if tool_path.exists():
                            safe_print(f"  ✓ {tool}")
                            break
                else:
                    tool_path = bin_dir / tool
                    if tool_path.exists():
                        safe_print(f"  ✓ {tool}")
            print()

            print("To use these tools:")
            print("  clang-tool-chain-cosmocc hello.c -o hello.com")
            print("  clang-tool-chain-cosmocpp hello.cpp -o hello.com")
            print()
            print("The resulting .com files run on all platforms without modification!")
            print()
            return 0
        else:
            safe_print("✗ Installation verification failed - bin directory not found")
            return 1

    except KeyboardInterrupt as ke:
        handle_keyboard_interrupt_properly(ke)
    except Exception as e:
        print()
        safe_print(f"✗ Installation failed: {e}")
        return 1


def cmd_install_cosmocc_env(args: argparse.Namespace) -> int:
    """Install Cosmopolitan (cosmocc) toolchain binaries to system environment (PATH)."""
    import setenvironment

    from . import env_breadcrumbs, installer
    from .path_utils import get_cosmocc_install_dir

    print("Clang Tool Chain - Install Cosmopolitan to Environment")
    print("=" * 60)
    print()

    # Get current platform info (for display only)
    try:
        platform_name, arch = wrapper.get_platform_info()
        print(f"Current platform: {platform_name}/{arch}")
        print("Note: Cosmocc is universal and runs on all platforms")
        print()
    except RuntimeError as e:
        print(f"Error: Failed to detect platform: {e}")
        return 1

    # First, ensure cosmocc is installed (universal - no platform/arch args needed)
    if not installer.is_cosmocc_installed():
        print("Universal Cosmopolitan (cosmocc) toolchain not found. Installing first...")
        print()
        installer.ensure_cosmocc()
        print()
        safe_print("✓ Universal Cosmopolitan (cosmocc) toolchain installed")
        print()

    # Get the binary directory (universal - no platform/arch args needed)
    install_dir = get_cosmocc_install_dir()
    bin_dir = install_dir / "bin"

    if not bin_dir.exists():
        print(f"Error: Binary directory does not exist: {bin_dir}")
        print()
        print("Installation failed. Please try running:")
        print("  clang-tool-chain install cosmocc")
        return 1

    print(f"Binary directory: {bin_dir}")
    print()

    # Add bin directory to PATH
    print("Adding cosmocc bin directory to PATH...")
    try:
        setenvironment.add_env_path(str(bin_dir))
        safe_print(f"✓ Added to PATH: {bin_dir}")

        # Mark as installed to environment (for automatic cleanup during purge)
        env_breadcrumbs.mark_component_installed_to_env("cosmocc", str(bin_dir))
    except KeyboardInterrupt as ke:
        handle_keyboard_interrupt_properly(ke)
    except Exception as e:
        safe_print(f"✗ Failed to add to PATH: {e}")
        return 1

    print()
    print("=" * 60)
    print("Installation Complete!")
    print()
    print("The following tools are now available globally:")
    print("  cosmocc, cosmoc++, and other Cosmopolitan tools...")
    print()
    print("IMPORTANT: You may need to:")
    print("  - Restart your terminal/shell for changes to take effect")
    print("  - On some systems, log out and log back in")
    print()
    print("To verify installation, open a new terminal and run:")
    print("  cosmocc --version")
    print()

    return 0


def cmd_uninstall_cosmocc_env(args: argparse.Namespace) -> int:
    """Remove Cosmopolitan (cosmocc) toolchain binaries from system environment (PATH)."""
    import setenvironment

    from . import env_breadcrumbs
    from .path_utils import get_cosmocc_install_dir

    print("Clang Tool Chain - Uninstall Cosmopolitan from Environment")
    print("=" * 60)
    print()

    # Get current platform info (for display only)
    try:
        platform_name, arch = wrapper.get_platform_info()
        print(f"Current platform: {platform_name}/{arch}")
        print("Note: Cosmocc is universal and runs on all platforms")
        print()
    except RuntimeError as e:
        print(f"Error: Failed to detect platform: {e}")
        return 1

    # Get the binary directory (universal - no platform/arch args needed)
    install_dir = get_cosmocc_install_dir()
    bin_dir = install_dir / "bin"

    print(f"Binary directory: {bin_dir}")
    print()

    # Remove bin directory from PATH
    print("Removing cosmocc bin directory from PATH...")
    try:
        setenvironment.remove_env_path(str(bin_dir))
        safe_print(f"✓ Removed from PATH: {bin_dir}")

        # Remove breadcrumb
        env_breadcrumbs.unmark_component_installed_to_env("cosmocc")
    except KeyboardInterrupt as ke:
        handle_keyboard_interrupt_properly(ke)
    except Exception as e:
        safe_print(f"✗ Failed to remove from PATH: {e}")
        return 1

    print()
    print("=" * 60)
    print("Uninstallation Complete!")
    print()
    print("The cosmocc binaries are no longer in your system PATH.")
    print()
    print("IMPORTANT: You may need to:")
    print("  - Restart your terminal/shell for changes to take effect")
    print("  - On some systems, log out and log back in")
    print()
    print("You can still use the tools via clang-tool-chain wrapper commands:")
    print("  clang-tool-chain-cosmocc, clang-tool-chain-cosmocpp")
    print()

    return 0


def cmd_test(args: argparse.Namespace) -> int:
    """Run diagnostic tests to verify the toolchain installation."""
    import tempfile
    from pathlib import Path

    print("Clang Tool Chain - Diagnostic Tests")
    print("=" * 70)
    print()

    # Test 1: Platform Detection
    print("[1/7] Testing platform detection...")
    platform_name: str
    arch: str
    try:
        platform_name, arch = wrapper.get_platform_info()
        print(f"      Platform: {platform_name}/{arch}")
        safe_print("      ✓ PASSED")
    except KeyboardInterrupt as ke:
        handle_keyboard_interrupt_properly(ke)
    except Exception as e:
        safe_print(f"      ✗ FAILED: {e}")
        return 1
    print()

    # Test 2: Toolchain Download/Installation
    print("[2/7] Testing toolchain installation...")
    try:
        bin_dir = wrapper.get_platform_binary_dir()
        if bin_dir.exists():
            print(f"      Binary directory: {bin_dir}")
            safe_print("      ✓ PASSED")
        else:
            safe_print(f"      ✗ FAILED: Binary directory does not exist: {bin_dir}")
            return 1
    except KeyboardInterrupt as ke:
        handle_keyboard_interrupt_properly(ke)
    except Exception as e:
        safe_print(f"      ✗ FAILED: {e}")
        return 1
    print()

    # Test 3: Finding clang binary
    print("[3/7] Testing binary resolution (clang)...")
    clang_path: Path
    try:
        clang_path = wrapper.find_tool_binary("clang")
        print(f"      Found: {clang_path}")
        if not clang_path.exists():
            safe_print(f"      ✗ FAILED: Binary does not exist: {clang_path}")
            return 1
        safe_print("      ✓ PASSED")
    except KeyboardInterrupt as ke:
        handle_keyboard_interrupt_properly(ke)
    except Exception as e:
        safe_print(f"      ✗ FAILED: {e}")
        return 1
    print()

    # Test 4: Finding clang++ binary
    print("[4/7] Testing binary resolution (clang++)...")
    clang_cpp_path: Path
    try:
        clang_cpp_path = wrapper.find_tool_binary("clang++")
        print(f"      Found: {clang_cpp_path}")
        if not clang_cpp_path.exists():
            safe_print(f"      ✗ FAILED: Binary does not exist: {clang_cpp_path}")
            return 1
        safe_print("      ✓ PASSED")
    except KeyboardInterrupt as ke:
        handle_keyboard_interrupt_properly(ke)
    except Exception as e:
        safe_print(f"      ✗ FAILED: {e}")
        return 1
    print()

    # Test 5: Version check for clang
    print("[5/7] Testing clang version...")
    try:
        result = subprocess.run([str(clang_path), "--version"], capture_output=True, text=True, timeout=10)
        if result.returncode == 0:
            version_line = result.stdout.split("\n")[0]
            print(f"      {version_line}")
            safe_print("      ✓ PASSED")
        else:
            safe_print(f"      ✗ FAILED: clang --version returned {result.returncode}")
            print(f"      stderr: {result.stderr}")
            return 1
    except KeyboardInterrupt as ke:
        handle_keyboard_interrupt_properly(ke)
    except Exception as e:
        safe_print(f"      ✗ FAILED: {e}")
        return 1
    print()

    # Test 6: Simple compilation test
    print("[6/7] Testing C compilation...")
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir_path = Path(tmpdir)
        test_c = tmpdir_path / "test.c"
        test_out = tmpdir_path / "test"
        if platform_name == "win":
            test_out = test_out.with_suffix(".exe")

        # Write simple C program
        test_c.write_text(
            """
#include <stdio.h>
int main() {
    printf("Hello from clang-tool-chain!\\n");
    return 0;
}
"""
        )

        try:
            # Compile
            result = subprocess.run(
                [str(clang_path), str(test_c), "-o", str(test_out)], capture_output=True, text=True, timeout=30
            )
            if result.returncode != 0:
                safe_print("      ✗ FAILED: Compilation failed")
                print(f"      stdout: {result.stdout}")
                print(f"      stderr: {result.stderr}")
                return 1

            # Verify output file was created
            if not test_out.exists():
                safe_print(f"      ✗ FAILED: Output binary not created: {test_out}")
                return 1

            print(f"      Compiled: {test_out}")
            safe_print("      ✓ PASSED")
        except KeyboardInterrupt as ke:
            handle_keyboard_interrupt_properly(ke)
        except Exception as e:
            safe_print(f"      ✗ FAILED: {e}")
            return 1
    print()

    # Test 7: Simple C++ compilation test
    print("[7/7] Testing C++ compilation...")
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir_path = Path(tmpdir)
        test_cpp = tmpdir_path / "test.cpp"
        test_out = tmpdir_path / "test"
        if platform_name == "win":
            test_out = test_out.with_suffix(".exe")

        # Write simple C++ program
        test_cpp.write_text(
            """
#include <iostream>
int main() {
    std::cout << "Hello from clang-tool-chain C++!" << std::endl;
    return 0;
}
"""
        )

        try:
            # Compile
            result = subprocess.run(
                [str(clang_cpp_path), str(test_cpp), "-o", str(test_out)], capture_output=True, text=True, timeout=30
            )
            if result.returncode != 0:
                safe_print("      ✗ FAILED: Compilation failed")
                print(f"      stdout: {result.stdout}")
                print(f"      stderr: {result.stderr}")
                return 1

            # Verify output file was created
            if not test_out.exists():
                safe_print(f"      ✗ FAILED: Output binary not created: {test_out}")
                return 1

            print(f"      Compiled: {test_out}")
            safe_print("      ✓ PASSED")
        except KeyboardInterrupt as ke:
            handle_keyboard_interrupt_properly(ke)
        except Exception as e:
            safe_print(f"      ✗ FAILED: {e}")
            return 1
    print()

    print("=" * 70)
    safe_print("All tests passed! ✓")
    print()
    return 0


def main() -> int:
    """Main entry point for the clang-tool-chain CLI."""
    parser = argparse.ArgumentParser(
        prog="clang-tool-chain",
        description="LLVM/Clang toolchain management and wrapper utilities",
        epilog="For more information, visit: https://github.com/your-repo/clang-tool-chain",
    )

    # Add --version flag at the top level
    parser.add_argument(
        "-V",
        "--version",
        action="version",
        version=f"clang-tool-chain {__version__}",
        help="Show program's version number and exit",
    )

    subparsers = parser.add_subparsers(
        dest="command",
        help="Available commands",
    )

    # info command
    parser_info = subparsers.add_parser(
        "info",
        help="Display information about the toolchain installation",
    )
    parser_info.set_defaults(func=cmd_info)

    # version command
    parser_version = subparsers.add_parser(
        "version",
        help="Display version of a specific tool",
    )
    parser_version.add_argument(
        "tool",
        help="Tool name (e.g., clang, clang++, lld)",
    )
    parser_version.set_defaults(func=cmd_version)

    # list-tools command
    parser_list = subparsers.add_parser(
        "list-tools",
        help="List all available wrapper tools",
    )
    parser_list.set_defaults(func=cmd_list_tools)

    # path command
    parser_path = subparsers.add_parser(
        "path",
        help="Display the path to the binary directory or a specific tool",
    )
    parser_path.add_argument(
        "tool",
        nargs="?",
        help="Tool name (optional, prints binary directory if not specified)",
    )
    parser_path.set_defaults(func=cmd_path)

    # package-version command
    parser_pkg_version = subparsers.add_parser(
        "package-version",
        help="Display the package version and target LLVM version",
    )
    parser_pkg_version.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Show detailed version information including installed LLVM version",
    )
    parser_pkg_version.set_defaults(func=cmd_package_version)

    # test command
    parser_test = subparsers.add_parser(
        "test",
        help="Run diagnostic tests to verify the toolchain installation",
    )
    parser_test.set_defaults(func=cmd_test)

    # install command (with subcommands)
    parser_install = subparsers.add_parser(
        "install",
        help="Install toolchain components",
    )
    install_subparsers = parser_install.add_subparsers(
        dest="install_component",
        help="Component to install",
    )

    # install clang
    parser_install_clang = install_subparsers.add_parser(
        "clang",
        help="Pre-download and install the core Clang/LLVM toolchain",
    )
    parser_install_clang.set_defaults(func=cmd_install_clang)

    # install clang-env
    parser_install_clang_env = install_subparsers.add_parser(
        "clang-env",
        help="Install Clang/LLVM toolchain binaries to system environment (PATH)",
    )
    parser_install_clang_env.set_defaults(func=cmd_install_clang_env)

    # install cosmocc
    parser_install_cosmocc = install_subparsers.add_parser(
        "cosmocc",
        help="Pre-download and install the Cosmopolitan (cosmocc) toolchain",
    )
    parser_install_cosmocc.set_defaults(func=cmd_install_cosmocc)

    # install cosmocc-env
    parser_install_cosmocc_env = install_subparsers.add_parser(
        "cosmocc-env",
        help="Install Cosmopolitan (cosmocc) toolchain binaries to system environment (PATH)",
    )
    parser_install_cosmocc_env.set_defaults(func=cmd_install_cosmocc_env)

    # uninstall command (with subcommands)
    parser_uninstall = subparsers.add_parser(
        "uninstall",
        help="Uninstall toolchain components from environment",
    )
    uninstall_subparsers = parser_uninstall.add_subparsers(
        dest="uninstall_component",
        help="Component to uninstall",
    )

    # uninstall clang-env
    parser_uninstall_clang_env = uninstall_subparsers.add_parser(
        "clang-env",
        help="Remove Clang/LLVM toolchain binaries from system environment (PATH)",
    )
    parser_uninstall_clang_env.set_defaults(func=cmd_uninstall_clang_env)

    # uninstall cosmocc-env
    parser_uninstall_cosmocc_env = uninstall_subparsers.add_parser(
        "cosmocc-env",
        help="Remove Cosmopolitan (cosmocc) toolchain binaries from system environment (PATH)",
    )
    parser_uninstall_cosmocc_env.set_defaults(func=cmd_uninstall_cosmocc_env)

    # purge command
    parser_purge = subparsers.add_parser(
        "purge",
        help="Remove all downloaded toolchains and cached data",
    )
    parser_purge.add_argument(
        "-y",
        "--yes",
        action="store_true",
        help="Skip confirmation prompt and remove immediately",
    )
    parser_purge.set_defaults(func=cmd_purge)

    # Parse arguments
    args = parser.parse_args()

    # If no command specified, show help
    if not args.command:
        parser.print_help()
        return 0

    # Handle install/uninstall subcommands without component specified
    if args.command == "install" and not hasattr(args, "func"):
        print("Error: Please specify what to install")
        print()
        print("Available options:")
        print("  clang-tool-chain install clang        - Install core Clang/LLVM toolchain")
        print("  clang-tool-chain install clang-env    - Add Clang to system PATH")
        print("  clang-tool-chain install cosmocc      - Install Cosmopolitan toolchain")
        print("  clang-tool-chain install cosmocc-env  - Add Cosmopolitan to system PATH")
        print()
        print("For more information: clang-tool-chain install --help")
        return 1

    if args.command == "uninstall" and not hasattr(args, "func"):
        print("Error: Please specify what to uninstall")
        print()
        print("Available options:")
        print("  clang-tool-chain uninstall clang-env   - Remove Clang from system PATH")
        print("  clang-tool-chain uninstall cosmocc-env - Remove Cosmopolitan from system PATH")
        print()
        print("For more information: clang-tool-chain uninstall --help")
        return 1

    # Execute command
    return args.func(args)


def test_main() -> int:
    """
    Standalone entry point for the test command.

    This allows running: clang-tool-chain-test
    """
    import argparse

    args = argparse.Namespace()  # Empty namespace
    return cmd_test(args)


def sccache_main() -> int:
    """
    Entry point for direct sccache passthrough command.

    This command allows users to run sccache directly for commands like:
    - clang-tool-chain-sccache --show-stats
    - clang-tool-chain-sccache --zero-stats
    - clang-tool-chain-sccache --start-server
    - clang-tool-chain-sccache --stop-server

    If sccache is not found in PATH, automatically uses iso-env to run it in an isolated environment.
    """
    args = sys.argv[1:]
    return sccache_runner.run_sccache(args)


def sccache_c_main() -> NoReturn:
    """
    Entry point for sccache + clang C compiler wrapper.

    This command wraps the clang C compiler with sccache for compilation caching.
    Delegates to core.py for unified argument transformation and DLL deployment.
    """
    wrapper.sccache_clang_main(use_msvc=False)


def sccache_cpp_main() -> NoReturn:
    """
    Entry point for sccache + clang++ C++ compiler wrapper.

    This command wraps the clang++ C++ compiler with sccache for compilation caching.
    Delegates to core.py for unified argument transformation and DLL deployment.
    """
    wrapper.sccache_clang_cpp_main(use_msvc=False)


def sccache_c_msvc_main() -> NoReturn:
    """
    Entry point for sccache + clang C compiler wrapper with MSVC ABI.

    This command wraps the clang C compiler with sccache for compilation caching,
    using MSVC ABI target on Windows.
    """
    wrapper.sccache_clang_main(use_msvc=True)


def sccache_cpp_msvc_main() -> NoReturn:
    """
    Entry point for sccache + clang++ C++ compiler wrapper with MSVC ABI.

    This command wraps the clang++ C++ compiler with sccache for compilation caching,
    using MSVC ABI target on Windows.
    """
    wrapper.sccache_clang_cpp_main(use_msvc=True)


if __name__ == "__main__":
    sys.exit(main())
