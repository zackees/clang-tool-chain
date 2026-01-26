"""
Node.js resolution using Chain of Responsibility pattern.

This module provides a clean, extensible system for locating Node.js installations
using the Chain of Responsibility design pattern. It implements a three-tier priority
system for Node.js availability:

1. Bundled Node.js: Preferred (known version, minimal size, no user setup)
2. System Node.js: Fallback (backward compatibility)
3. Auto-download: Last resort (automatic installation)

The resolver automatically tries each detection method in order until one succeeds.
"""

import logging
import shutil
import sys
from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from clang_tool_chain.interrupt_utils import handle_keyboard_interrupt_properly

logger = logging.getLogger(__name__)


@dataclass
class NodeJSLocation:
    """
    Represents a located Node.js installation.

    Attributes:
        path: Path to the node executable
        source: Where the Node.js was found ("bundled", "system", "downloaded")
    """

    path: Path
    source: Literal["bundled", "system", "downloaded"]


class NodeJSDetector(ABC):
    """
    Abstract base class for Node.js detection strategies.

    Each detector implements one way of finding Node.js and can delegate
    to the next detector in the chain if it fails.
    """

    def __init__(self, next_detector: "NodeJSDetector | None" = None):
        """
        Initialize detector with optional next detector in chain.

        Args:
            next_detector: Next detector to try if this one fails
        """
        self._next_detector = next_detector

    @abstractmethod
    def detect(self, platform_name: str, arch: str) -> NodeJSLocation | None:
        """
        Attempt to detect Node.js installation.

        Args:
            platform_name: Platform name ("win", "linux", "darwin")
            arch: Architecture ("x86_64", "arm64")

        Returns:
            NodeJSLocation if found, None otherwise
        """
        pass

    def _try_next(self, platform_name: str, arch: str) -> NodeJSLocation | None:
        """
        Delegate to next detector in chain.

        Args:
            platform_name: Platform name ("win", "linux", "darwin")
            arch: Architecture ("x86_64", "arm64")

        Returns:
            NodeJSLocation if found by next detector, None otherwise
        """
        if self._next_detector:
            return self._next_detector.detect(platform_name, arch)
        return None


class BundledNodeDetector(NodeJSDetector):
    """
    Detects bundled Node.js installation in ~/.clang-tool-chain/nodejs.

    This is the preferred detection method because:
    - Known version and behavior
    - Minimal size (~10-15 MB compressed)
    - No user installation required
    - Consistent across all platforms
    """

    def detect(self, platform_name: str, arch: str) -> NodeJSLocation | None:
        """
        Check for bundled Node.js installation.

        Args:
            platform_name: Platform name ("win", "linux", "darwin")
            arch: Architecture ("x86_64", "arm64")

        Returns:
            NodeJSLocation if bundled Node.js exists, otherwise tries next detector
        """
        logger.debug("BundledNodeDetector: Checking for bundled Node.js")

        # Construct bundled Node.js path
        nodejs_install_dir = Path.home() / ".clang-tool-chain" / "nodejs" / platform_name / arch
        node_binary_name = "node.exe" if platform_name == "win" else "node"
        bundled_node = nodejs_install_dir / "bin" / node_binary_name

        if bundled_node.exists():
            logger.info(f"Using bundled Node.js: {bundled_node}")
            logger.debug(f"Bundled Node.js location: {bundled_node}")
            return NodeJSLocation(path=bundled_node, source="bundled")

        logger.debug("BundledNodeDetector: Bundled Node.js not found, trying next detector")
        return self._try_next(platform_name, arch)


class SystemNodeDetector(NodeJSDetector):
    """
    Detects system Node.js installation via PATH.

    This is a fallback for users with existing Node.js installations,
    preserving backward compatibility.
    """

    def detect(self, platform_name: str, arch: str) -> NodeJSLocation | None:
        """
        Check for system Node.js in PATH.

        Args:
            platform_name: Platform name ("win", "linux", "darwin")
            arch: Architecture ("x86_64", "arm64")

        Returns:
            NodeJSLocation if system Node.js exists, otherwise tries next detector
        """
        logger.debug("SystemNodeDetector: Checking for system Node.js in PATH")

        system_node = shutil.which("node")
        if system_node:
            logger.info(f"Using system Node.js: {system_node}")
            logger.debug(
                "Bundled Node.js not found. Using system Node.js from PATH as fallback. "
                "To use bundled Node.js, it will be downloaded automatically on next run if system Node.js is removed."
            )
            return NodeJSLocation(path=Path(system_node), source="system")

        logger.debug("SystemNodeDetector: System Node.js not found, trying next detector")
        return self._try_next(platform_name, arch)


class AutoDownloadNodeDetector(NodeJSDetector):
    """
    Downloads bundled Node.js if no existing installation is found.

    This is a last resort that provides automatic installation with user feedback.
    """

    def detect(self, platform_name: str, arch: str) -> NodeJSLocation | None:
        """
        Download bundled Node.js.

        Args:
            platform_name: Platform name ("win", "linux", "darwin")
            arch: Architecture ("x86_64", "arm64")

        Returns:
            NodeJSLocation after download, or None if download fails

        Raises:
            RuntimeError: If download fails and no fallback is available
        """
        logger.debug("AutoDownloadNodeDetector: No Node.js found, starting auto-download")
        logger.info("Node.js not found. Downloading bundled Node.js...")

        # Print user-friendly download message
        print("\n" + "=" * 60, file=sys.stderr)
        print("Node.js Auto-Download", file=sys.stderr)
        print("=" * 60, file=sys.stderr)
        print("Node.js is required for Emscripten (WebAssembly compilation).", file=sys.stderr)
        print("Downloading minimal Node.js runtime (~10-15 MB)...", file=sys.stderr)
        print("This is a one-time download and will be cached for future use.", file=sys.stderr)
        print("=" * 60 + "\n", file=sys.stderr)

        try:
            # Import downloader and trigger download
            from .. import downloader

            downloader.ensure_nodejs_available(platform_name, arch)

            # Verify installation succeeded
            nodejs_install_dir = Path.home() / ".clang-tool-chain" / "nodejs" / platform_name / arch
            node_binary_name = "node.exe" if platform_name == "win" else "node"
            bundled_node = nodejs_install_dir / "bin" / node_binary_name

            if bundled_node.exists():
                logger.info(f"Node.js successfully downloaded: {bundled_node}")
                print(f"\nNode.js successfully installed to: {nodejs_install_dir}", file=sys.stderr)
                print("Future compilations will use the cached Node.js runtime.\n", file=sys.stderr)
                return NodeJSLocation(path=bundled_node, source="downloaded")
            else:
                # This should not happen (downloader should raise exception), but handle gracefully
                raise RuntimeError(
                    f"Node.js download completed but binary not found at expected location:\n"
                    f"  Expected: {bundled_node}\n"
                    f"  Installation directory: {nodejs_install_dir}"
                )

        except KeyboardInterrupt as ke:
            handle_keyboard_interrupt_properly(ke)
        except Exception as e:
            # Download failed - provide helpful error message
            logger.error(f"Failed to download Node.js: {e}")
            print("\n" + "=" * 60, file=sys.stderr)
            print("Node.js Download Failed", file=sys.stderr)
            print("=" * 60, file=sys.stderr)
            print(f"Error: {e}", file=sys.stderr)
            print("\nWorkaround: Install Node.js manually", file=sys.stderr)
            print("  - Download from: https://nodejs.org/", file=sys.stderr)
            print("  - Linux: apt install nodejs / yum install nodejs", file=sys.stderr)
            print("  - macOS: brew install node", file=sys.stderr)
            print("  - Windows: Install from https://nodejs.org/", file=sys.stderr)
            print("\nAfter installation, ensure node is in your PATH.", file=sys.stderr)
            print("Verify with: node --version", file=sys.stderr)
            print("\nIf this problem persists, please report it at:", file=sys.stderr)
            print("  https://github.com/zackees/clang-tool-chain/issues", file=sys.stderr)
            print("=" * 60 + "\n", file=sys.stderr)

            # Re-raise as RuntimeError for consistent error handling
            raise RuntimeError(
                "Failed to install bundled Node.js and no system Node.js found.\n"
                "Please install Node.js manually (see instructions above) or report this issue."
            ) from e


class NodeJSResolver:
    """
    Resolves Node.js installation using Chain of Responsibility pattern.

    This class coordinates the detection chain and provides a simple interface
    for finding Node.js installations.
    """

    def __init__(self):
        """
        Initialize resolver with default detection chain.

        The chain order is:
        1. BundledNodeDetector (preferred)
        2. SystemNodeDetector (fallback)
        3. AutoDownloadNodeDetector (last resort)
        """
        # Build chain in reverse order (last to first)
        self._detector_chain = BundledNodeDetector(
            next_detector=SystemNodeDetector(next_detector=AutoDownloadNodeDetector())
        )

    def resolve(self, platform_name: str, arch: str) -> Path:
        """
        Resolve Node.js installation path.

        Args:
            platform_name: Platform name ("win", "linux", "darwin")
            arch: Architecture ("x86_64", "arm64")

        Returns:
            Path to node executable

        Raises:
            RuntimeError: If Node.js cannot be found or downloaded
        """
        logger.debug(f"NodeJSResolver: Starting resolution for {platform_name}/{arch}")

        location = self._detector_chain.detect(platform_name, arch)

        if location:
            logger.info(f"Node.js resolved: {location.path} (source: {location.source})")
            return location.path

        # Should never reach here (AutoDownloadNodeDetector should either succeed or raise)
        raise RuntimeError(
            "Failed to resolve Node.js installation. All detection methods failed.\n"
            "This is an internal error - please report it at:\n"
            "https://github.com/zackees/clang-tool-chain/issues"
        )
