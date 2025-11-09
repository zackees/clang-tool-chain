#!/usr/bin/env python3
"""
Strip and optimize LLVM binaries for minimal package size.

This script removes unnecessary files from downloaded LLVM distributions
and strips debug symbols from binaries to minimize package size.
"""

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path

# Essential binaries to keep
ESSENTIAL_BINARIES = {
    # Core compilation
    "clang",
    "clang++",
    "clang-cl",  # Windows only
    "clang-cpp",
    # Linkers
    "lld",
    "lld-link",
    "ld.lld",
    "ld64.lld",
    "wasm-ld",
    # Binary utilities
    "llvm-ar",
    "llvm-nm",
    "llvm-objdump",
    "llvm-objcopy",
    "llvm-ranlib",
    "llvm-strip",
    "llvm-readelf",
    "llvm-readobj",
    # Additional utilities
    "llvm-as",
    "llvm-dis",
    "clang-format",
    "clang-tidy",
    "llvm-symbolizer",
    "llvm-config",
}

# Directories to remove completely
REMOVE_DIRS = {
    "share/doc",
    "share/man",
    "docs",
    "share/clang",
    "share/opt-viewer",
    "share/scan-build",
    "share/scan-view",
    "python_packages",
    "libexec",  # Helper scripts usually not needed
}

# File patterns to remove
REMOVE_PATTERNS = {
    "*.a",  # Static libraries
    "*.lib",  # Windows static libraries
    "CMakeLists.txt",
    "*.cmake",
}

# Directories containing files to remove by pattern
PATTERN_REMOVE_DIRS = {
    "lib",
    "lib64",
}


class BinaryStripper:
    """Strip and optimize LLVM binary distributions."""

    def __init__(
        self,
        source_dir: Path,
        output_dir: Path,
        platform: str,
        keep_headers: bool = False,
        strip_binaries: bool = True,
        verbose: bool = False,
    ):
        """
        Initialize the binary stripper.

        Args:
            source_dir: Directory containing extracted LLVM binaries
            output_dir: Directory to output stripped binaries
            platform: Platform identifier (e.g., "linux-x86_64")
            keep_headers: Whether to keep header files
            strip_binaries: Whether to strip debug symbols
            verbose: Whether to print verbose output
        """
        self.source_dir = Path(source_dir)
        self.output_dir = Path(output_dir)
        self.platform = platform
        self.keep_headers = keep_headers
        self.strip_binaries = strip_binaries
        self.verbose = verbose

        # Statistics
        self.original_size = 0
        self.final_size = 0
        self.files_removed = 0
        self.files_kept = 0

    def log(self, message: str) -> None:
        """Print a message if verbose mode is enabled."""
        if self.verbose:
            print(message)

    def get_dir_size(self, path: Path) -> int:
        """Get total size of a directory in bytes."""
        total = 0
        try:
            for entry in path.rglob("*"):
                if entry.is_file():
                    total += entry.stat().st_size
        except Exception as e:
            self.log(f"Warning: Could not calculate size of {path}: {e}")
        return total

    def find_llvm_root(self) -> Path | None:
        """
        Find the root directory of the LLVM installation.

        Returns:
            Path to LLVM root, or None if not found
        """
        # Check if source_dir is already the root
        if (self.source_dir / "bin").exists():
            return self.source_dir

        # Look for subdirectories that might be the root
        for subdir in self.source_dir.iterdir():
            if subdir.is_dir() and (subdir / "bin").exists():
                return subdir

        return None

    def should_keep_binary(self, binary_name: str) -> bool:
        """
        Check if a binary should be kept.

        Args:
            binary_name: Name of the binary (without extension)

        Returns:
            True if binary should be kept, False otherwise
        """
        # Remove common extensions
        name = binary_name
        for ext in [".exe", ".dll", ".so", ".dylib"]:
            if name.endswith(ext):
                name = name[: -len(ext)]
                break

        return name in ESSENTIAL_BINARIES

    def copy_essential_files(self, src_root: Path, dst_root: Path) -> None:
        """
        Copy only essential files from source to destination.

        Args:
            src_root: Source LLVM root directory
            dst_root: Destination directory
        """
        dst_root.mkdir(parents=True, exist_ok=True)

        # Copy bin directory (filtered)
        src_bin = src_root / "bin"
        if src_bin.exists():
            dst_bin = dst_root / "bin"
            dst_bin.mkdir(parents=True, exist_ok=True)

            for binary in src_bin.iterdir():
                if binary.is_file() and self.should_keep_binary(binary.name):
                    shutil.copy2(binary, dst_bin / binary.name)
                    self.files_kept += 1
                    self.log(f"Keeping binary: {binary.name}")
                else:
                    self.files_removed += 1
                    self.log(f"Removing binary: {binary.name}")

        # Copy lib directory (filtered - keep only runtime libraries)
        for lib_dir_name in ["lib", "lib64"]:
            src_lib = src_root / lib_dir_name
            if not src_lib.exists():
                continue

            dst_lib = dst_root / lib_dir_name
            dst_lib.mkdir(parents=True, exist_ok=True)

            for item in src_lib.iterdir():
                # Keep clang runtime directory
                if item.is_dir() and item.name == "clang":
                    dst_clang = dst_lib / "clang"
                    shutil.copytree(item, dst_clang, dirs_exist_ok=True)
                    self.files_kept += 1
                    self.log(f"Keeping runtime: {item.name}")
                # Keep dynamic libraries (.so, .dll, .dylib)
                elif item.is_file():
                    if any(item.name.endswith(ext) for ext in [".so", ".dll", ".dylib"]):
                        # Check if it's a versioned .so file
                        if ".so." in item.name or item.suffix in [".so", ".dll", ".dylib"]:
                            shutil.copy2(item, dst_lib / item.name)
                            self.files_kept += 1
                            self.log(f"Keeping library: {item.name}")
                    # Remove static libraries
                    elif item.suffix in [".a", ".lib"]:
                        self.files_removed += 1
                        self.log(f"Removing static library: {item.name}")
                    # Keep CMake and other config files if small
                    elif item.suffix in [".cmake"] or "LLVMConfig" in item.name:
                        self.files_removed += 1
                        self.log(f"Removing config file: {item.name}")
                    else:
                        # Keep other files (might be needed)
                        shutil.copy2(item, dst_lib / item.name)
                        self.files_kept += 1

        # Copy include directory only if requested
        if self.keep_headers:
            src_include = src_root / "include"
            if src_include.exists():
                dst_include = dst_root / "include"
                shutil.copytree(src_include, dst_include, dirs_exist_ok=True)
                self.log("Keeping include directory")
        else:
            self.log("Removing include directory")

        # Copy license and readme files
        for pattern in ["LICENSE*", "README*", "NOTICE*"]:
            for item in src_root.glob(pattern):
                if item.is_file():
                    shutil.copy2(item, dst_root / item.name)
                    self.log(f"Keeping license file: {item.name}")

    def strip_binary(self, binary_path: Path) -> bool:
        """
        Strip debug symbols from a binary.

        Args:
            binary_path: Path to the binary to strip

        Returns:
            True if stripping was successful, False otherwise
        """
        if not self.strip_binaries:
            return True

        try:
            # Determine strip command based on platform
            if "win" in self.platform:
                # On Windows, try to find llvm-strip in the output
                llvm_strip = self.output_dir / "bin" / "llvm-strip.exe"
                if not llvm_strip.exists():
                    self.log(f"Skipping strip for {binary_path.name}: llvm-strip not found")
                    return False
                strip_cmd = [str(llvm_strip), "--strip-all", str(binary_path)]
            else:
                # On Unix, use llvm-strip from the output
                llvm_strip = self.output_dir / "bin" / "llvm-strip"
                if not llvm_strip.exists():
                    # Fallback to system strip
                    strip_cmd = ["strip", "--strip-all", str(binary_path)]
                else:
                    strip_cmd = [str(llvm_strip), "--strip-all", str(binary_path)]

            # Get original size
            original_size = binary_path.stat().st_size

            # Run strip command
            result = subprocess.run(strip_cmd, capture_output=True, text=True)

            if result.returncode == 0:
                new_size = binary_path.stat().st_size
                saved = original_size - new_size
                saved_pct = (saved / original_size * 100) if original_size > 0 else 0
                self.log(
                    f"Stripped {binary_path.name}: "
                    f"{original_size/1024/1024:.1f}MB -> {new_size/1024/1024:.1f}MB "
                    f"(saved {saved_pct:.1f}%)"
                )
                return True
            else:
                self.log(f"Failed to strip {binary_path.name}: {result.stderr}")
                return False

        except Exception as e:
            self.log(f"Error stripping {binary_path.name}: {e}")
            return False

    def strip_all_binaries(self) -> None:
        """Strip debug symbols from all binaries in output directory."""
        if not self.strip_binaries:
            print("Skipping binary stripping (disabled)")
            return

        print("Stripping debug symbols from binaries...")

        bin_dir = self.output_dir / "bin"
        if not bin_dir.exists():
            print("Warning: No bin directory found")
            return

        # Get list of binaries to strip
        binaries = []
        for binary in bin_dir.iterdir():
            if binary.is_file():
                # Check if file is executable or library
                if "win" in self.platform:
                    if binary.suffix in [".exe", ".dll"]:
                        binaries.append(binary)
                else:
                    # On Unix, check if file has executable bit
                    if os.access(binary, os.X_OK) or binary.suffix in [".so", ".dylib"]:
                        binaries.append(binary)

        print(f"Found {len(binaries)} binaries to strip")

        # Strip each binary
        success_count = 0
        for binary in binaries:
            if self.strip_binary(binary):
                success_count += 1

        print(f"Successfully stripped {success_count}/{len(binaries)} binaries")

    def process(self) -> bool:
        """
        Process the LLVM distribution: copy essential files and strip binaries.

        Returns:
            True if processing was successful, False otherwise
        """
        print(f"Processing {self.platform}...")

        # Find LLVM root
        llvm_root = self.find_llvm_root()
        if not llvm_root:
            print(f"Error: Could not find LLVM root in {self.source_dir}")
            return False

        print(f"Found LLVM root: {llvm_root}")

        # Calculate original size
        print("Calculating original size...")
        self.original_size = self.get_dir_size(llvm_root)
        print(f"Original size: {self.original_size / 1024 / 1024:.1f} MB")

        # Copy essential files
        print("Copying essential files...")
        self.copy_essential_files(llvm_root, self.output_dir)

        # Strip binaries
        if self.strip_binaries:
            self.strip_all_binaries()

        # Calculate final size
        print("Calculating final size...")
        self.final_size = self.get_dir_size(self.output_dir)
        print(f"Final size: {self.final_size / 1024 / 1024:.1f} MB")

        # Print statistics
        saved = self.original_size - self.final_size
        saved_pct = (saved / self.original_size * 100) if self.original_size > 0 else 0

        print(f"\n{'='*60}")
        print("Statistics")
        print(f"{'='*60}")
        print(f"Original size:  {self.original_size / 1024 / 1024:>10.1f} MB")
        print(f"Final size:     {self.final_size / 1024 / 1024:>10.1f} MB")
        print(f"Saved:          {saved / 1024 / 1024:>10.1f} MB ({saved_pct:.1f}%)")
        print(f"Files kept:     {self.files_kept:>10}")
        print(f"Files removed:  {self.files_removed:>10}")
        print(f"{'='*60}\n")

        return True


def main() -> None:
    """Main entry point for the strip script."""
    parser = argparse.ArgumentParser(description="Strip and optimize LLVM binaries for minimal package size")
    parser.add_argument("source_dir", help="Directory containing extracted LLVM binaries")
    parser.add_argument("output_dir", help="Directory to output stripped binaries")
    parser.add_argument(
        "--platform",
        required=True,
        choices=["win-x86_64", "linux-x86_64", "linux-aarch64", "darwin-x86_64", "darwin-arm64"],
        help="Platform identifier",
    )
    parser.add_argument(
        "--keep-headers",
        action="store_true",
        help="Keep header files (increases size significantly)",
    )
    parser.add_argument(
        "--no-strip",
        action="store_true",
        help="Don't strip debug symbols from binaries",
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Print verbose output",
    )

    args = parser.parse_args()

    # Create stripper and process
    stripper = BinaryStripper(
        source_dir=args.source_dir,
        output_dir=args.output_dir,
        platform=args.platform,
        keep_headers=args.keep_headers,
        strip_binaries=not args.no_strip,
        verbose=args.verbose,
    )

    success = stripper.process()

    if not success:
        print("\nError: Failed to process binaries")
        sys.exit(1)

    print("\n✓ Successfully processed binaries")


if __name__ == "__main__":
    main()
