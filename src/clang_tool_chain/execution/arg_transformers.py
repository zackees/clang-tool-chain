"""
Composable Argument Transformers using Chain of Responsibility Pattern

This module implements a flexible and composable system for transforming compiler
arguments based on platform, tool, and ABI requirements. Each transformer is
responsible for a specific aspect of argument transformation (SDK paths, linker
flags, ABI configuration, etc.) and transformers can be combined in a pipeline.

The Chain of Responsibility pattern allows:
- Independent, testable transformers
- Flexible ordering based on priority
- Easy addition of new transformers
- Clear separation of concerns

Architecture:
    ArgumentTransformer (ABC)
        ├── DirectivesTransformer (priority=50)
        ├── MacOSSDKTransformer (priority=100)
        ├── LinuxUnwindTransformer (priority=150)
        ├── LLDLinkerTransformer (priority=200)
        ├── ASANRuntimeTransformer (priority=250)
        ├── RPathTransformer (priority=275)
        ├── GNUABITransformer (priority=300)
        └── MSVCABITransformer (priority=300)

    ArgumentPipeline
        - Manages transformer execution order
        - Applies transformers in priority order (low to high)
        - Returns final transformed arguments
"""

from __future__ import annotations

import logging
import os
from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from clang_tool_chain.env_utils import is_feature_disabled

if TYPE_CHECKING:
    from clang_tool_chain.directives.parser import ParsedDirectives

logger = logging.getLogger(__name__)


@dataclass
class ToolContext:
    """
    Context information for argument transformation.

    This provides all the information transformers need to make decisions
    about which arguments to add or modify.

    Attributes:
        platform_name: Platform identifier (win, darwin, linux)
        arch: Architecture (x86_64, arm64)
        tool_name: Name of the tool being executed (clang, clang++, etc.)
        use_msvc: True if using MSVC ABI (Windows only)
    """

    platform_name: str
    arch: str
    tool_name: str
    use_msvc: bool


class ArgumentTransformer(ABC):
    """
    Abstract base class for argument transformers.

    Each transformer implements a specific aspect of argument transformation
    and has a priority that determines its execution order in the pipeline.
    Lower priority values execute first.
    """

    @abstractmethod
    def transform(self, args: list[str], context: ToolContext) -> list[str]:
        """
        Transform compiler arguments based on context.

        Args:
            args: Current compiler/linker arguments
            context: Execution context with platform and tool information

        Returns:
            Transformed arguments (may be modified or returned as-is)
        """
        pass

    @abstractmethod
    def priority(self) -> int:
        """
        Return the priority of this transformer.

        Lower values execute first. This allows control over the order
        in which transformers are applied.

        Returns:
            Priority value (typically 0-1000)
        """
        pass


class DirectivesTransformer(ArgumentTransformer):
    """
    Transformer for inlined build directives in source files.

    Priority: 50 (runs early to allow source files to specify requirements)

    This transformer parses C/C++ source files for embedded build directives
    (e.g., // @link: pthread, // @std: c++17) and adds the corresponding
    compiler and linker arguments.

    Environment Variables:
        CLANG_TOOL_CHAIN_NO_DIRECTIVES: Set to '1' to disable directive parsing
        CLANG_TOOL_CHAIN_NO_AUTO: Set to '1' to disable all automatic features
        CLANG_TOOL_CHAIN_DIRECTIVE_VERBOSE: Set to '1' to enable debug logging
    """

    def priority(self) -> int:
        return 50

    def transform(self, args: list[str], context: ToolContext) -> list[str]:
        """Add arguments from inlined build directives in source files."""
        # Check if directives are disabled (via NO_DIRECTIVES or NO_AUTO)
        if is_feature_disabled("DIRECTIVES"):
            return args

        # Only apply to clang/clang++ compilation commands
        if context.tool_name not in ("clang", "clang++"):
            return args

        # Find source files in arguments
        source_files = [Path(arg) for arg in args if arg.endswith((".c", ".cpp", ".cc", ".cxx"))]

        if not source_files:
            return args

        # Parse directives from all source files
        from clang_tool_chain.directives.parser import DirectiveParser

        parser = DirectiveParser()
        all_directives: list[ParsedDirectives] = []

        for source_file in source_files:
            if not source_file.exists():
                continue

            try:
                directives = parser.parse_file_for_current_platform(source_file)
                all_directives.append(directives)

                if os.environ.get("CLANG_TOOL_CHAIN_DIRECTIVE_VERBOSE") == "1":
                    logger.info(f"Parsed directives from {source_file}: {directives.get_all_args()}")

            except Exception as e:
                logger.warning(f"Failed to parse directives from {source_file}: {e}")
                continue

        if not all_directives:
            return args

        # Merge all directives into final argument list
        directive_args = []
        for directives in all_directives:
            directive_args.extend(directives.get_all_args())

        if directive_args:
            logger.info(f"Adding {len(directive_args)} arguments from inlined build directives")
            # Prepend directive arguments so they can be overridden by explicit args
            return directive_args + args

        return args


class MacOSSDKTransformer(ArgumentTransformer):
    """
    Transformer for macOS SDK path detection and injection.

    Priority: 100 (runs after directives but before linker/ABI)

    This transformer implements LLVM's official three-tier SDK detection:
    1. Explicit -isysroot flag (user override)
    2. SDKROOT environment variable (Xcode standard)
    3. Automatic xcrun --show-sdk-path (fallback detection)

    Environment Variables:
        CLANG_TOOL_CHAIN_NO_SYSROOT: Set to '1' to disable automatic -isysroot
        SDKROOT: Custom SDK path (standard macOS variable)
    """

    def priority(self) -> int:
        return 100

    def transform(self, args: list[str], context: ToolContext) -> list[str]:
        """Add macOS SDK path if needed."""
        # Only applies to macOS clang/clang++
        if context.platform_name != "darwin" or context.tool_name not in ("clang", "clang++"):
            return args

        # Import here to avoid circular dependency
        from clang_tool_chain.sdk import _add_macos_sysroot_if_needed

        logger.debug("Checking if macOS sysroot needs to be added")
        return _add_macos_sysroot_if_needed(args)


class LinuxUnwindTransformer(ArgumentTransformer):
    """
    Transformer for adding bundled libunwind include/library paths on Linux.

    Priority: 150 (runs after SDK but before linker)

    This transformer adds include and library paths for the bundled libunwind
    headers and libraries on Linux. This allows compilation of code that uses
    libunwind without requiring system libunwind-dev to be installed.

    When libunwind.h exists in the clang toolchain's include directory:
    - Adds -I<clang_root>/include for header discovery
    - Adds -L<clang_root>/lib for library discovery
    - Adds -Wl,-rpath,<clang_root>/lib for runtime library discovery

    Environment Variables:
        CLANG_TOOL_CHAIN_NO_BUNDLED_UNWIND: Set to '1' to disable bundled libunwind
        CLANG_TOOL_CHAIN_NO_AUTO: Set to '1' to disable all automatic features
    """

    def priority(self) -> int:
        return 150

    def transform(self, args: list[str], context: ToolContext) -> list[str]:
        """Add bundled libunwind paths if available on Linux."""
        # Only applies to Linux clang/clang++
        if context.platform_name != "linux" or context.tool_name not in ("clang", "clang++"):
            return args

        # Check if disabled (via NO_BUNDLED_UNWIND or NO_AUTO)
        if is_feature_disabled("BUNDLED_UNWIND"):
            return args

        # Check if compile-only (no linking)
        is_compile_only = "-c" in args

        try:
            from clang_tool_chain.platform.detection import get_platform_binary_dir

            clang_bin = get_platform_binary_dir()
            clang_root = clang_bin.parent

            # Check if bundled libunwind.h exists
            libunwind_header = clang_root / "include" / "libunwind.h"
            if not libunwind_header.exists():
                logger.debug("Bundled libunwind.h not found, skipping LinuxUnwindTransformer")
                return args

            result = list(args)
            include_dir = clang_root / "include"
            lib_dir = clang_root / "lib"

            # Add include path (always needed for compilation)
            include_flag = f"-I{include_dir}"
            if include_flag not in args:
                result = [include_flag] + result
                logger.debug(f"Adding bundled libunwind include path: {include_flag}")

            # Add library path and rpath (only for linking)
            if not is_compile_only:
                lib_flag = f"-L{lib_dir}"
                if lib_flag not in args:
                    result = [lib_flag] + result
                    logger.debug(f"Adding bundled libunwind library path: {lib_flag}")

                # Add rpath so runtime can find libunwind.so
                rpath_flag = f"-Wl,-rpath,{lib_dir}"
                # Check if any rpath to our lib dir already exists
                has_our_rpath = any(str(lib_dir) in arg and "-rpath" in arg for arg in args)
                if not has_our_rpath:
                    result = [rpath_flag] + result
                    logger.debug(f"Adding bundled libunwind rpath: {rpath_flag}")

            return result

        except Exception as e:
            logger.debug(f"LinuxUnwindTransformer error: {e}")
            return args


class LLDLinkerTransformer(ArgumentTransformer):
    """
    Transformer for forcing LLVM's lld linker on macOS and Linux.

    Priority: 200 (runs after SDK but before ABI)

    This transformer adds -fuse-ld=lld linker flag. The clang driver
    automatically dispatches to the correct linker binary:
    - macOS: ld64.lld (Mach-O linker)
    - Linux: ld.lld (ELF linker)

    It also translates GNU ld flags to ld64.lld equivalents on macOS:
    - --no-undefined -> -undefined error
    - --fatal-warnings -> -fatal_warnings

    Environment Variables:
        CLANG_TOOL_CHAIN_USE_SYSTEM_LD: Set to '1' to use system linker
    """

    def priority(self) -> int:
        return 200

    def transform(self, args: list[str], context: ToolContext) -> list[str]:
        """Add lld linker flags if needed."""
        # Only applies to clang/clang++
        if context.tool_name not in ("clang", "clang++"):
            return args

        # Import here to avoid circular dependency
        from clang_tool_chain.linker import _add_lld_linker_if_needed

        return _add_lld_linker_if_needed(context.platform_name, args)


class GNUABITransformer(ArgumentTransformer):
    """
    Transformer for Windows GNU ABI (MinGW) configuration.

    Priority: 300 (runs after SDK and linker)

    This transformer adds GNU ABI target arguments for Windows:
    - --target=x86_64-w64-windows-gnu (or aarch64-w64-windows-gnu)
    - --sysroot pointing to MinGW sysroot
    - -stdlib=libc++ for C++ standard library
    - -fuse-ld=lld for LLVM linker
    - -rtlib=compiler-rt for LLVM runtime
    - --unwindlib=libunwind for LLVM unwinder

    This is the default ABI on Windows for cross-platform consistency.
    """

    def priority(self) -> int:
        return 300

    def transform(self, args: list[str], context: ToolContext) -> list[str]:
        """Add GNU ABI target arguments for Windows."""
        # Only applies to Windows clang/clang++ when not using MSVC
        if context.use_msvc or context.tool_name not in ("clang", "clang++"):
            return args

        # Import here to avoid circular dependency
        from clang_tool_chain.abi import _get_gnu_target_args, _should_use_gnu_abi

        if not _should_use_gnu_abi(context.platform_name, args):
            return args

        try:
            gnu_args = _get_gnu_target_args(context.platform_name, context.arch, args)
            if gnu_args:
                logger.info(f"Using GNU ABI with {len(gnu_args)} additional arguments")
                # Prepend GNU args to allow user overrides
                return gnu_args + args
        except Exception as e:
            logger.error(f"Failed to set up GNU ABI: {e}")
            import sys

            print(f"\nWarning: Failed to set up Windows GNU ABI: {e}", file=sys.stderr)
            print("Continuing with default target (may fail)...\n", file=sys.stderr)

        return args


class ASANRuntimeTransformer(ArgumentTransformer):
    """
    Transformer for ASAN (Address Sanitizer) runtime library configuration.

    Priority: 250 (runs after linker but before ABI)

    This transformer ensures proper ASAN runtime linking on Linux and Windows:
    - Detects -fsanitize=address flag
    - Adds -shared-libasan to use shared runtime library
    - Adds -Wl,--allow-shlib-undefined when building shared libraries with ASAN (Linux only)
    - Prevents undefined symbol errors during linking

    The shared runtime library (libclang_rt.asan.so on Linux, libclang_rt.asan_dynamic.dll
    on Windows) contains the full ASAN implementation, while the static wrapper library
    only contains stubs.

    When building shared libraries with sanitizers, the library may have undefined
    symbols that will be provided by the sanitizer runtime when loaded. LLD by
    default enforces no undefined symbols, so we need to allow them explicitly.

    Note: macOS uses a different ASAN runtime mechanism and is not affected.

    Environment Variables:
        CLANG_TOOL_CHAIN_NO_SHARED_ASAN: Set to '1' to disable shared ASAN
        CLANG_TOOL_CHAIN_NO_SANITIZER_NOTE: Set to '1' to suppress the injection note
        CLANG_TOOL_CHAIN_NO_AUTO: Set to '1' to disable all automatic features
    """

    def priority(self) -> int:
        return 250

    def transform(self, args: list[str], context: ToolContext) -> list[str]:
        """Add -shared-libasan and --allow-shlib-undefined when using ASAN on Linux/Windows."""
        import sys

        # Only applies to Linux and Windows (GNU ABI) clang/clang++
        # macOS uses a different ASAN runtime mechanism
        if context.platform_name not in ("linux", "win") or context.tool_name not in ("clang", "clang++"):
            return args

        # Check if ASAN is enabled
        has_asan = any("-fsanitize=address" in arg for arg in args)
        if not has_asan:
            return args

        result = list(args)
        injected_flags = []

        # Check if user disabled shared ASAN (via NO_SHARED_ASAN or NO_AUTO)
        # Also check if -shared-libasan already present
        if not is_feature_disabled("SHARED_ASAN") and "-shared-libasan" not in args:
            # Add -shared-libasan to use shared runtime library
            # This prevents undefined symbol errors during linking
            logger.info("Adding -shared-libasan for ASAN runtime linking on Linux")
            result = ["-shared-libasan"] + result
            injected_flags.append("-shared-libasan")

        # Check if building a shared library with ASAN on Linux
        # Shared libraries need to allow undefined symbols that will be provided
        # by the sanitizer runtime when the runner loads them
        # Note: --allow-shlib-undefined is a Linux ELF linker flag, not supported on Windows
        is_shared_lib = "-shared" in args
        if is_shared_lib and context.platform_name == "linux":
            # Check if --allow-shlib-undefined already present
            has_allow_shlib_undefined = any("--allow-shlib-undefined" in arg for arg in args)
            if not has_allow_shlib_undefined:
                logger.info("Adding -Wl,--allow-shlib-undefined for shared library with ASAN")
                result = ["-Wl,--allow-shlib-undefined"] + result
                injected_flags.append("-Wl,--allow-shlib-undefined")

        # Warn on stderr if we injected flags (unless disabled)
        if injected_flags and not is_feature_disabled("SANITIZER_NOTE"):
            print(
                f"clang-tool-chain: note: automatically injected sanitizer flags: {' '.join(injected_flags)} "
                "(disable with CLANG_TOOL_CHAIN_NO_SANITIZER_NOTE=1)",
                file=sys.stderr,
            )

        return result


class RPathTransformer(ArgumentTransformer):
    """
    Transformer for adding rpath when --deploy-dependencies is used on Linux.

    Priority: 275 (runs after ASAN but before ABI)

    This transformer adds -Wl,-rpath,$ORIGIN to ensure executables can find
    deployed shared libraries (like ASAN runtime) in the same directory
    without requiring LD_LIBRARY_PATH to be set.

    The rpath is only added when:
    - Platform is Linux
    - --deploy-dependencies flag is present
    - Not a compile-only operation (-c flag)

    Environment Variables:
        CLANG_TOOL_CHAIN_NO_RPATH: Set to '1' to disable automatic rpath injection
        CLANG_TOOL_CHAIN_NO_AUTO: Set to '1' to disable all automatic features
    """

    def priority(self) -> int:
        return 275

    def transform(self, args: list[str], context: ToolContext) -> list[str]:
        """Add -Wl,-rpath,$ORIGIN when --deploy-dependencies is used on Linux."""
        # Only applies to Linux clang/clang++
        if context.platform_name != "linux" or context.tool_name not in ("clang", "clang++"):
            return args

        # Check if compile-only (no linking)
        if "-c" in args:
            return args

        # Check if --deploy-dependencies is present
        # Note: The flag may have been stripped already by core.py, so we also check env var
        has_deploy_flag = "--deploy-dependencies" in args
        deploy_from_env = os.environ.get("CLANG_TOOL_CHAIN_DEPLOY_DEPENDENCIES") == "1"

        if not has_deploy_flag and not deploy_from_env:
            return args

        # Check if user disabled rpath (via NO_RPATH or NO_AUTO)
        if is_feature_disabled("RPATH"):
            return args

        # Check if rpath already present
        for arg in args:
            if "-rpath" in arg or "$ORIGIN" in arg:
                return args

        # Add rpath to look in executable's directory first
        # $ORIGIN is resolved at runtime to the directory containing the executable
        logger.info("Adding -Wl,-rpath,$ORIGIN for deployed library lookup on Linux")
        return ["-Wl,-rpath,$ORIGIN"] + args


class MSVCABITransformer(ArgumentTransformer):
    """
    Transformer for Windows MSVC ABI configuration.

    Priority: 300 (runs after SDK and linker, same as GNU ABI)

    This transformer adds MSVC ABI target arguments for Windows:
    - --target=x86_64-pc-windows-msvc (or aarch64-pc-windows-msvc)

    MSVC ABI is opt-in via *-msvc variant commands and requires
    Windows SDK to be installed.
    """

    def priority(self) -> int:
        return 300

    def transform(self, args: list[str], context: ToolContext) -> list[str]:
        """Add MSVC ABI target arguments for Windows."""
        # Only applies to Windows clang/clang++ when using MSVC variant
        if not context.use_msvc or context.tool_name not in ("clang", "clang++"):
            return args

        # Import here to avoid circular dependency
        from clang_tool_chain.abi import _get_msvc_target_args, _should_use_msvc_abi

        if not _should_use_msvc_abi(context.platform_name, args):
            return args

        try:
            msvc_args = _get_msvc_target_args(context.platform_name, context.arch)
            if msvc_args:
                logger.info(f"Using MSVC ABI with {len(msvc_args)} additional arguments")
                # Prepend MSVC args to allow user overrides
                return msvc_args + args
        except Exception as e:
            logger.error(f"Failed to set up MSVC ABI: {e}")
            import sys

            print(f"\nWarning: Failed to set up Windows MSVC ABI: {e}", file=sys.stderr)
            print("Continuing with default target (may fail)...\n", file=sys.stderr)

        return args


class ArgumentPipeline:
    """
    Pipeline for applying multiple argument transformers in priority order.

    This class manages the execution of transformers, ensuring they run in
    the correct order based on their priority values.

    Example:
        >>> pipeline = ArgumentPipeline([
        ...     DirectivesTransformer(),
        ...     MacOSSDKTransformer(),
        ...     LLDLinkerTransformer(),
        ...     GNUABITransformer(),
        ... ])
        >>> context = ToolContext("darwin", "x86_64", "clang++", False)
        >>> transformed = pipeline.transform(["test.cpp", "-o", "test"], context)
    """

    def __init__(self, transformers: list[ArgumentTransformer]):
        """
        Initialize the pipeline with a list of transformers.

        Args:
            transformers: List of transformers to apply
        """
        # Sort transformers by priority (low to high)
        self._transformers = sorted(transformers, key=lambda t: t.priority())

        logger.debug(f"Initialized pipeline with {len(self._transformers)} transformers:")
        for transformer in self._transformers:
            logger.debug(f"  - {transformer.__class__.__name__} (priority={transformer.priority()})")

    def transform(self, args: list[str], context: ToolContext) -> list[str]:
        """
        Apply all transformers to the arguments in priority order.

        Args:
            args: Original compiler/linker arguments
            context: Execution context

        Returns:
            Transformed arguments after all transformers have been applied
        """
        result = args.copy()

        for transformer in self._transformers:
            transformer_name = transformer.__class__.__name__
            logger.debug(f"Applying {transformer_name}...")

            try:
                result = transformer.transform(result, context)
            except Exception as e:
                logger.error(f"Transformer {transformer_name} failed: {e}")
                # Continue with next transformer, don't fail the whole pipeline
                continue

        logger.debug(f"Pipeline complete: {len(args)} -> {len(result)} arguments")
        return result


def create_default_pipeline() -> ArgumentPipeline:
    """
    Create the default argument transformation pipeline.

    This includes all standard transformers in their default priority order:
    1. DirectivesTransformer (priority=50)
    2. MacOSSDKTransformer (priority=100)
    3. LinuxUnwindTransformer (priority=150)
    4. LLDLinkerTransformer (priority=200)
    5. ASANRuntimeTransformer (priority=250)
    6. RPathTransformer (priority=275)
    7. GNUABITransformer (priority=300)
    8. MSVCABITransformer (priority=300)

    Returns:
        Configured ArgumentPipeline ready for use
    """
    return ArgumentPipeline(
        [
            DirectivesTransformer(),
            MacOSSDKTransformer(),
            LinuxUnwindTransformer(),
            LLDLinkerTransformer(),
            ASANRuntimeTransformer(),
            RPathTransformer(),
            GNUABITransformer(),
            MSVCABITransformer(),
        ]
    )
