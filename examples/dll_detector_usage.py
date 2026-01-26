"""
Example usage of the DLL detection Strategy pattern.

This example demonstrates how to use the various DLL detection strategies
independently or composed together.
"""

from pathlib import Path


# Example 1: Using HeuristicDLLDetector (fallback strategy)
def example_heuristic_detector():
    """Demonstrate heuristic DLL detection with default MinGW DLLs."""
    from clang_tool_chain.deployment.dll_detector import HeuristicDLLDetector

    binary_path = Path("C:/path/to/program.exe")

    # Create detector with default DLL list
    detector = HeuristicDLLDetector()

    # This would detect DLLs (if binary existed)
    # result = detector.detect(binary_path)
    # print(f"Heuristic DLLs: {result}")

    # For this example, just show what it would return
    print("Example 1: HeuristicDLLDetector")
    print("  Would return: ['libwinpthread-1.dll', 'libgcc_s_seh-1.dll', 'libstdc++-6.dll']")
    print()


# Example 2: Using HeuristicDLLDetector with custom list
def example_custom_heuristic():
    """Demonstrate heuristic DLL detection with custom DLL list."""
    from clang_tool_chain.deployment.dll_detector import HeuristicDLLDetector

    # Custom DLLs for a specific application
    custom_dlls = [
        "libwinpthread-1.dll",
        "libgcc_s_seh-1.dll",
        "libstdc++-6.dll",
        "libgomp-1.dll",  # OpenMP runtime
        "libclang_rt.asan_dynamic-x86_64.dll",  # AddressSanitizer
    ]

    detector = HeuristicDLLDetector(dll_list=custom_dlls)

    print("Example 2: HeuristicDLLDetector with custom DLLs")
    print(f"  Custom DLL list: {custom_dlls}")
    print()


# Example 3: Using ObjdumpDLLDetector (precise detection)
def example_objdump_detector():
    """Demonstrate objdump-based DLL detection with filtering."""
    from clang_tool_chain.deployment.dll_detector import ObjdumpDLLDetector

    objdump_path = Path("C:/path/to/llvm-objdump.exe")
    binary_path = Path("C:/path/to/program.exe")

    # Filter function to only detect MinGW DLLs
    def is_mingw_dll(dll_name: str) -> bool:
        return dll_name.lower().startswith("lib")

    # Create detector with filter
    detector = ObjdumpDLLDetector(objdump_path=objdump_path, dll_filter_func=is_mingw_dll)

    print("Example 3: ObjdumpDLLDetector with filtering")
    print("  Runs: llvm-objdump -p program.exe")
    print("  Filters: Only DLLs starting with 'lib'")
    print("  Would exclude: kernel32.dll, msvcrt.dll, etc.")
    print()


# Example 4: Using TransitiveDependencyScanner
def example_transitive_scanner():
    """Demonstrate transitive dependency scanning."""
    from clang_tool_chain.deployment.dll_detector import TransitiveDependencyScanner

    objdump_path = Path("C:/path/to/llvm-objdump.exe")

    # Mock DLL locator function
    def locate_dll(dll_name: str) -> Path | None:
        """Locate a DLL in the MinGW sysroot."""
        sysroot = Path("C:/path/to/mingw/bin")
        dll_path = sysroot / dll_name
        return dll_path if dll_path.exists() else None

    # Filter for deployable DLLs
    def is_deployable(dll_name: str) -> bool:
        return dll_name.lower().startswith("lib")

    # Create scanner
    scanner = TransitiveDependencyScanner(
        dll_locator_func=locate_dll, objdump_path=objdump_path, dll_filter_func=is_deployable
    )

    # Scan starting from direct dependencies
    direct_deps = ["libstdc++-6.dll", "libgcc_s_seh-1.dll"]

    print("Example 4: TransitiveDependencyScanner")
    print(f"  Direct dependencies: {direct_deps}")
    print("  Scanner will recursively find:")
    print("    libstdc++-6.dll -> libwinpthread-1.dll")
    print("    libgcc_s_seh-1.dll -> libwinpthread-1.dll")
    print("  Result: ['libstdc++-6.dll', 'libgcc_s_seh-1.dll', 'libwinpthread-1.dll']")
    print()


# Example 5: Complete detection workflow (as used in dll_deployer.py)
def example_complete_workflow():
    """Demonstrate the complete detection workflow with fallback."""
    from clang_tool_chain.deployment.dll_detector import (
        HeuristicDLLDetector,
        ObjdumpDLLDetector,
        TransitiveDependencyScanner,
    )

    binary_path = Path("C:/path/to/program.exe")
    objdump_path = Path("C:/path/to/llvm-objdump.exe")

    # Define filter and locator
    def is_deployable_dll(dll_name: str) -> bool:
        import re

        mingw_patterns = [
            r"libwinpthread.*\.dll",
            r"libgcc_s_.*\.dll",
            r"libstdc\+\+.*\.dll",
        ]
        dll_lower = dll_name.lower()
        return any(re.match(p, dll_lower) for p in mingw_patterns)

    def locate_dll(dll_name: str) -> Path | None:
        sysroot = Path("C:/mingw/bin")
        dll_path = sysroot / dll_name
        return dll_path if dll_path.exists() else None

    print("Example 5: Complete workflow with fallback")
    print()

    # Try precise detection
    try:
        if not objdump_path.exists():
            raise RuntimeError("objdump not found")

        # Create objdump detector
        objdump_detector = ObjdumpDLLDetector(objdump_path=objdump_path, dll_filter_func=is_deployable_dll)

        print("  Step 1: Detect direct dependencies using objdump")
        # detected_dlls = objdump_detector.detect(binary_path)
        detected_dlls = ["libstdc++-6.dll", "libgcc_s_seh-1.dll"]
        print(f"    Found: {detected_dlls}")
        print()

        if detected_dlls:
            # Create transitive scanner
            scanner = TransitiveDependencyScanner(
                dll_locator_func=locate_dll, objdump_path=objdump_path, dll_filter_func=is_deployable_dll
            )

            print("  Step 2: Scan for transitive dependencies")
            # all_dlls = scanner.scan_transitive_dependencies(detected_dlls)
            all_dlls = detected_dlls + ["libwinpthread-1.dll"]
            print(f"    All DLLs: {all_dlls}")
            print()

            return all_dlls

    except RuntimeError:
        # Fallback to heuristic
        print("  objdump failed, using heuristic fallback")
        fallback = HeuristicDLLDetector()
        # result = fallback.detect(binary_path)
        result = ["libwinpthread-1.dll", "libgcc_s_seh-1.dll", "libstdc++-6.dll"]
        print(f"    Heuristic result: {result}")
        print()
        return result


# Example 6: Custom detector strategy
def example_custom_detector():
    """Demonstrate creating a custom detector strategy."""
    from clang_tool_chain.deployment.dll_detector import DLLDetector

    class ConfigFileDLLDetector(DLLDetector):
        """Detector that reads DLL list from a config file."""

        def __init__(self, config_path: Path):
            self.config_path = config_path

        def detect(self, binary_path: Path) -> list[str]:
            """Read DLL list from config file."""
            if not binary_path.exists():
                raise FileNotFoundError(f"Binary not found: {binary_path}")

            # Read config file (simplified example)
            # In real code, this would parse JSON/YAML/INI
            dlls = [
                "libwinpthread-1.dll",
                "libgcc_s_seh-1.dll",
                "app-specific.dll",
            ]
            return dlls

    print("Example 6: Custom detector strategy")
    print("  ConfigFileDLLDetector reads from config.json")
    print("  Allows per-project DLL customization")
    print("  Easily pluggable via DLLDetector interface")
    print()


if __name__ == "__main__":
    print("=" * 70)
    print("DLL Detector Strategy Pattern Examples")
    print("=" * 70)
    print()

    example_heuristic_detector()
    example_custom_heuristic()
    example_objdump_detector()
    example_transitive_scanner()
    example_complete_workflow()
    example_custom_detector()

    print("=" * 70)
    print("All examples completed!")
    print("=" * 70)
