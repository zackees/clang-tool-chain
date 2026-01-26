"""
Manifest handling module.

Handles parsing and fetching manifest files for all toolchain components:
- Clang/LLVM toolchain
- IWYU (Include What You Use)
- Emscripten (WebAssembly)
- Node.js runtime
"""

import json
from dataclasses import dataclass
from typing import Any, TypeVar
from urllib.request import Request, urlopen

from clang_tool_chain.interrupt_utils import handle_keyboard_interrupt_properly
from clang_tool_chain.logging_config import configure_logging

# Configure logging using centralized configuration
logger = configure_logging(__name__)

# Base URLs for manifests
MANIFEST_BASE_URL = "https://raw.githubusercontent.com/zackees/clang-tool-chain-bins/main/assets/clang"
IWYU_MANIFEST_BASE_URL = "https://raw.githubusercontent.com/zackees/clang-tool-chain-bins/main/assets/iwyu"
LLDB_MANIFEST_BASE_URL = "https://raw.githubusercontent.com/zackees/clang-tool-chain-bins/main/assets/lldb"
EMSCRIPTEN_MANIFEST_BASE_URL = "https://raw.githubusercontent.com/zackees/clang-tool-chain-bins/main/assets/emscripten"
NODEJS_MANIFEST_BASE_URL = "https://raw.githubusercontent.com/zackees/clang-tool-chain-bins/main/assets/nodejs"
COSMOCC_MANIFEST_BASE_URL = "https://raw.githubusercontent.com/zackees/clang-tool-chain-bins/main/assets/cosmocc"

# Generic type variable for JSON deserialization
T = TypeVar("T")


# ============================================================================
# Custom Exceptions
# ============================================================================


class ToolchainInfrastructureError(Exception):
    """
    Raised when toolchain infrastructure is broken (404, network errors, etc).

    This exception indicates a problem with the package's distribution infrastructure
    that should cause tests to FAIL rather than skip. Examples:
    - Manifest files return 404
    - Download URLs are broken
    - Network errors accessing expected resources
    """

    pass


# ============================================================================
# Data Structures
# ============================================================================


@dataclass
class ArchitectureEntry:
    """Represents an architecture entry in the root manifest."""

    arch: str
    manifest_path: str


@dataclass
class PlatformEntry:
    """Represents a platform entry in the root manifest."""

    platform: str
    architectures: list[ArchitectureEntry]


@dataclass
class RootManifest:
    """Represents the root manifest structure."""

    platforms: list[PlatformEntry]


@dataclass
class ArchivePart:
    """
    Represents a single part of a multi-part archive.

    Attributes:
        part_number: Sequential part number (1, 2, 3, ...)
        href: Download URL for this part
        sha256: SHA256 checksum for verification
        size_bytes: Size of this part in bytes (optional)
    """

    part_number: int
    href: str
    sha256: str
    size_bytes: int | None = None


@dataclass
class VersionInfo:
    """Represents version information in a platform manifest."""

    version: str
    href: str
    sha256: str
    parts: list[ArchivePart] | None = None  # Optional multi-part archive information


@dataclass
class Manifest:
    """Represents a platform-specific manifest structure."""

    latest: str
    versions: dict[str, VersionInfo]


# ============================================================================
# Parsing Functions
# ============================================================================


def _parse_root_manifest(data: dict[str, Any]) -> RootManifest:
    """
    Parse raw JSON data into a RootManifest dataclass.

    Args:
        data: Raw JSON dictionary

    Returns:
        Parsed RootManifest object
    """
    platforms = []
    for platform_data in data.get("platforms", []):
        architectures = []
        for arch_data in platform_data.get("architectures", []):
            # Support both "manifest_path" and "manifest_url" keys for backward compatibility
            manifest_path = arch_data.get("manifest_path") or arch_data.get("manifest_url")
            architectures.append(ArchitectureEntry(arch=arch_data["arch"], manifest_path=manifest_path))
        platforms.append(PlatformEntry(platform=platform_data["platform"], architectures=architectures))
    return RootManifest(platforms=platforms)


def _parse_manifest(data: dict[str, Any]) -> Manifest:
    """
    Parse raw JSON data into a Manifest dataclass.

    Args:
        data: Raw JSON dictionary

    Returns:
        Parsed Manifest object
    """
    latest = data.get("latest", "")
    versions = {}

    # Check if versions are nested under a "versions" key
    if "versions" in data and isinstance(data["versions"], dict):
        # Parse nested versions structure
        for key, value in data["versions"].items():
            if isinstance(value, dict) and "href" in value and "sha256" in value:
                parts_raw = value.get("parts", None)
                parts = None
                if parts_raw and isinstance(parts_raw, list):
                    parts = [
                        ArchivePart(
                            part_number=p.get("part", idx + 1),
                            href=p["href"],
                            sha256=p["sha256"],
                            size_bytes=p.get("size"),
                        )
                        for idx, p in enumerate(parts_raw)
                    ]
                versions[key] = VersionInfo(version=key, href=value["href"], sha256=value["sha256"], parts=parts)
    else:
        # Parse flat structure (all non-"latest" keys are version entries)
        for key, value in data.items():
            if key != "latest" and isinstance(value, dict) and "href" in value and "sha256" in value:
                parts_raw = value.get("parts", None)
                parts = None
                if parts_raw and isinstance(parts_raw, list):
                    parts = [
                        ArchivePart(
                            part_number=p.get("part", idx + 1),
                            href=p["href"],
                            sha256=p["sha256"],
                            size_bytes=p.get("size"),
                        )
                        for idx, p in enumerate(parts_raw)
                    ]
                versions[key] = VersionInfo(version=key, href=value["href"], sha256=value["sha256"], parts=parts)

    return Manifest(latest=latest, versions=versions)


# ============================================================================
# Fetching Functions
# ============================================================================


def _fetch_json_raw(url: str) -> dict[str, Any]:
    """
    Fetch and parse JSON from a URL.

    Args:
        url: URL to fetch

    Returns:
        Parsed JSON as a dictionary

    Raises:
        ToolchainInfrastructureError: If fetching or parsing fails
    """
    logger.info(f"Fetching JSON from: {url}")
    try:
        req = Request(url, headers={"User-Agent": "clang-tool-chain"})
        with urlopen(req, timeout=30) as response:
            data = response.read()
            logger.debug(f"Received {len(data)} bytes from {url}")
            result: dict[str, Any] = json.loads(data.decode("utf-8"))
            logger.info(f"Successfully fetched and parsed JSON from {url}")
            return result
    except KeyboardInterrupt as ke:
        handle_keyboard_interrupt_properly(ke)
    except Exception as e:
        logger.error(f"Failed to fetch JSON from {url}: {e}")
        raise ToolchainInfrastructureError(f"Failed to fetch JSON from {url}: {e}") from e


# ============================================================================
# Clang/LLVM Manifest Functions
# ============================================================================


def fetch_root_manifest() -> RootManifest:
    """
    Fetch the root manifest file for Clang/LLVM.

    Returns:
        Root manifest as a RootManifest object
    """
    logger.info("Fetching root manifest")
    url = f"{MANIFEST_BASE_URL}/manifest.json"
    data = _fetch_json_raw(url)
    manifest = _parse_root_manifest(data)
    logger.info(f"Root manifest loaded with {len(manifest.platforms)} platforms")
    return manifest


def fetch_platform_manifest(platform: str, arch: str) -> Manifest:
    """
    Fetch the platform-specific manifest file for Clang/LLVM.

    Args:
        platform: Platform name (e.g., "win", "linux", "darwin")
        arch: Architecture name (e.g., "x86_64", "arm64")

    Returns:
        Platform manifest as a Manifest object

    Raises:
        RuntimeError: If platform/arch combination is not found
    """
    logger.info(f"Fetching platform manifest for {platform}/{arch}")
    root_manifest = fetch_root_manifest()

    # Find the platform in the manifest
    for plat_entry in root_manifest.platforms:
        if plat_entry.platform == platform:
            # Find the architecture
            for arch_entry in plat_entry.architectures:
                if arch_entry.arch == arch:
                    manifest_path = arch_entry.manifest_path
                    logger.info(f"Found manifest path: {manifest_path}")
                    url = f"{MANIFEST_BASE_URL}/{manifest_path}"
                    data = _fetch_json_raw(url)
                    manifest = _parse_manifest(data)
                    logger.info(f"Platform manifest loaded successfully for {platform}/{arch}")
                    return manifest

    logger.error(f"Platform {platform}/{arch} not found in manifest")
    raise RuntimeError(f"Platform {platform}/{arch} not found in manifest")


# ============================================================================
# IWYU Manifest Functions
# ============================================================================


def fetch_iwyu_root_manifest() -> RootManifest:
    """
    Fetch the IWYU root manifest file.

    Returns:
        Root manifest as a RootManifest object
    """
    logger.info("Fetching IWYU root manifest")
    url = f"{IWYU_MANIFEST_BASE_URL}/manifest.json"
    data = _fetch_json_raw(url)
    manifest = _parse_root_manifest(data)
    logger.info(f"IWYU root manifest loaded with {len(manifest.platforms)} platforms")
    return manifest


def fetch_iwyu_platform_manifest(platform: str, arch: str) -> Manifest:
    """
    Fetch the IWYU platform-specific manifest file.

    Args:
        platform: Platform name (e.g., "win", "linux", "darwin")
        arch: Architecture name (e.g., "x86_64", "arm64")

    Returns:
        Platform manifest as a Manifest object

    Raises:
        RuntimeError: If platform/arch combination is not found
    """
    logger.info(f"Fetching IWYU platform manifest for {platform}/{arch}")
    root_manifest = fetch_iwyu_root_manifest()

    # Find the platform in the manifest
    for plat_entry in root_manifest.platforms:
        if plat_entry.platform == platform:
            # Find the architecture
            for arch_entry in plat_entry.architectures:
                if arch_entry.arch == arch:
                    manifest_path = arch_entry.manifest_path
                    logger.info(f"Found IWYU manifest path: {manifest_path}")
                    url = f"{IWYU_MANIFEST_BASE_URL}/{manifest_path}"
                    data = _fetch_json_raw(url)
                    manifest = _parse_manifest(data)
                    logger.info(f"IWYU platform manifest loaded successfully for {platform}/{arch}")
                    return manifest

    logger.error(f"IWYU platform {platform}/{arch} not found in manifest")
    raise RuntimeError(f"IWYU platform {platform}/{arch} not found in manifest")


# ============================================================================
# LLDB Manifest Functions
# ============================================================================


def fetch_lldb_root_manifest() -> RootManifest:
    """
    Fetch the LLDB root manifest file.

    Returns:
        Root manifest as a RootManifest object
    """
    logger.info("Fetching LLDB root manifest")
    url = f"{LLDB_MANIFEST_BASE_URL}/manifest.json"
    data = _fetch_json_raw(url)
    manifest = _parse_root_manifest(data)
    logger.info(f"LLDB root manifest loaded with {len(manifest.platforms)} platforms")
    return manifest


def fetch_lldb_platform_manifest(platform: str, arch: str) -> Manifest:
    """
    Fetch the LLDB platform-specific manifest file.

    Args:
        platform: Platform name (e.g., "win", "linux", "darwin")
        arch: Architecture name (e.g., "x86_64", "arm64")

    Returns:
        Platform manifest as a Manifest object

    Raises:
        RuntimeError: If platform/arch combination is not found
    """
    logger.info(f"Fetching LLDB platform manifest for {platform}/{arch}")
    root_manifest = fetch_lldb_root_manifest()

    # Find the platform in the manifest
    for plat_entry in root_manifest.platforms:
        if plat_entry.platform == platform:
            # Find the architecture
            for arch_entry in plat_entry.architectures:
                if arch_entry.arch == arch:
                    manifest_path = arch_entry.manifest_path
                    logger.info(f"Found LLDB manifest path: {manifest_path}")
                    url = f"{LLDB_MANIFEST_BASE_URL}/{manifest_path}"
                    data = _fetch_json_raw(url)
                    manifest = _parse_manifest(data)
                    logger.info(f"LLDB platform manifest loaded successfully for {platform}/{arch}")
                    return manifest

    logger.error(f"LLDB platform {platform}/{arch} not found in manifest")
    raise RuntimeError(f"LLDB platform {platform}/{arch} not found in manifest")


# ============================================================================
# Emscripten Manifest Functions
# ============================================================================


def fetch_emscripten_root_manifest() -> RootManifest:
    """
    Fetch the Emscripten root manifest file.

    Returns:
        Root manifest as a RootManifest object
    """
    logger.info("Fetching Emscripten root manifest")
    url = f"{EMSCRIPTEN_MANIFEST_BASE_URL}/manifest.json"
    data = _fetch_json_raw(url)
    manifest = _parse_root_manifest(data)
    logger.info(f"Emscripten root manifest loaded with {len(manifest.platforms)} platforms")
    return manifest


def fetch_emscripten_platform_manifest(platform: str, arch: str) -> Manifest:
    """
    Fetch the Emscripten platform-specific manifest file.

    Args:
        platform: Platform name (e.g., "win", "linux", "darwin")
        arch: Architecture name (e.g., "x86_64", "arm64")

    Returns:
        Platform manifest as a Manifest object

    Raises:
        RuntimeError: If platform/arch combination is not found
    """
    logger.info(f"Fetching Emscripten platform manifest for {platform}/{arch}")
    root_manifest = fetch_emscripten_root_manifest()

    # Find the platform in the manifest
    for plat_entry in root_manifest.platforms:
        if plat_entry.platform == platform:
            # Find the architecture
            for arch_entry in plat_entry.architectures:
                if arch_entry.arch == arch:
                    manifest_path = arch_entry.manifest_path
                    logger.debug(f"Platform manifest path: {manifest_path}")
                    # Check if manifest_path is already an absolute URL
                    if manifest_path.startswith(("http://", "https://")):
                        manifest_url = manifest_path
                    else:
                        manifest_url = f"{EMSCRIPTEN_MANIFEST_BASE_URL}/{manifest_path}"
                    data = _fetch_json_raw(manifest_url)
                    manifest = _parse_manifest(data)
                    logger.info(f"Platform manifest loaded: latest version = {manifest.latest}")
                    return manifest

            # Architecture not found
            available_arches = [a.arch for a in plat_entry.architectures]
            raise RuntimeError(
                f"Architecture '{arch}' not found for platform '{platform}'\n"
                f"Available architectures: {', '.join(available_arches)}\n"
                f"If you believe this should be supported, please report at:\n"
                f"https://github.com/zackees/clang-tool-chain/issues"
            )

    # Platform not found
    available_platforms = [p.platform for p in root_manifest.platforms]
    raise RuntimeError(
        f"Platform '{platform}' not found in Emscripten manifest\n"
        f"Available platforms: {', '.join(available_platforms)}\n"
        f"If you believe this should be supported, please report at:\n"
        f"https://github.com/zackees/clang-tool-chain/issues"
    )


# ============================================================================
# Node.js Manifest Functions
# ============================================================================


def fetch_nodejs_root_manifest() -> RootManifest:
    """
    Fetch the Node.js root manifest file.

    Returns:
        Root manifest as a RootManifest object

    Raises:
        ToolchainInfrastructureError: If fetching fails
    """
    logger.info("Fetching Node.js root manifest")
    url = f"{NODEJS_MANIFEST_BASE_URL}/manifest.json"
    data = _fetch_json_raw(url)
    manifest = _parse_root_manifest(data)
    logger.info(f"Node.js root manifest loaded with {len(manifest.platforms)} platforms")
    return manifest


def fetch_nodejs_platform_manifest(platform: str, arch: str) -> Manifest:
    """
    Fetch the Node.js platform-specific manifest file.

    Args:
        platform: Platform name (e.g., "win", "linux", "darwin")
        arch: Architecture name (e.g., "x86_64", "arm64")

    Returns:
        Platform manifest as a Manifest object

    Raises:
        RuntimeError: If platform/arch combination is not found
        ToolchainInfrastructureError: If fetching fails
    """
    logger.info(f"Fetching Node.js platform manifest for {platform}/{arch}")
    root_manifest = fetch_nodejs_root_manifest()

    # Find the platform in the manifest
    for plat_entry in root_manifest.platforms:
        if plat_entry.platform == platform:
            # Find the architecture
            for arch_entry in plat_entry.architectures:
                if arch_entry.arch == arch:
                    manifest_path = arch_entry.manifest_path
                    logger.debug(f"Platform manifest path: {manifest_path}")
                    # Check if manifest_path is already an absolute URL
                    if manifest_path.startswith(("http://", "https://")):
                        manifest_url = manifest_path
                    else:
                        manifest_url = f"{NODEJS_MANIFEST_BASE_URL}/{manifest_path}"
                    data = _fetch_json_raw(manifest_url)
                    manifest = _parse_manifest(data)
                    logger.info(f"Platform manifest loaded: latest version = {manifest.latest}")
                    return manifest

            # Architecture not found
            available_arches = [a.arch for a in plat_entry.architectures]
            raise RuntimeError(
                f"Architecture '{arch}' not found for platform '{platform}'\n"
                f"Available architectures: {', '.join(available_arches)}\n"
                f"If you believe this should be supported, please report at:\n"
                f"https://github.com/zackees/clang-tool-chain/issues"
            )

    # Platform not found
    available_platforms = [p.platform for p in root_manifest.platforms]
    raise RuntimeError(
        f"Platform '{platform}' not found in Node.js manifest\n"
        f"Available platforms: {', '.join(available_platforms)}\n"
        f"If you believe this should be supported, please report at:\n"
        f"https://github.com/zackees/clang-tool-chain/issues"
    )


# ============================================================================
# Cosmocc (Cosmopolitan) Manifest Functions
# ============================================================================


def fetch_cosmocc_root_manifest() -> RootManifest:
    """
    Fetch the Cosmocc root manifest file.

    Returns:
        Root manifest as a RootManifest object

    Raises:
        ToolchainInfrastructureError: If fetching fails
    """
    logger.info("Fetching Cosmocc root manifest")
    url = f"{COSMOCC_MANIFEST_BASE_URL}/manifest.json"
    data = _fetch_json_raw(url)
    manifest = _parse_root_manifest(data)
    logger.info(f"Cosmocc root manifest loaded with {len(manifest.platforms)} platforms")
    return manifest


def fetch_cosmocc_platform_manifest(platform: str | None = None, arch: str | None = None) -> Manifest:
    """
    Fetch the Cosmocc manifest.

    Cosmocc is universal (APE - Actually Portable Executables), so we use
    a single manifest for all platforms. The platform/arch parameters are
    ignored but kept for backward compatibility.

    Args:
        platform: Ignored - kept for backward compatibility
        arch: Ignored - kept for backward compatibility

    Returns:
        Platform manifest as a Manifest object

    Raises:
        ToolchainInfrastructureError: If fetching fails
    """
    # Log what was passed for debugging, but note we ignore it
    if platform is not None or arch is not None:
        logger.debug(f"Cosmocc manifest requested for {platform}/{arch} - using universal manifest")

    manifest_url = f"{COSMOCC_MANIFEST_BASE_URL}/manifest-universal.json"
    logger.info(f"Fetching Cosmocc universal manifest from {manifest_url}")

    try:
        data = _fetch_json_raw(manifest_url)
        manifest = _parse_manifest(data)
        logger.info(f"Cosmocc universal manifest loaded: latest version = {manifest.latest}")
        return manifest
    except KeyboardInterrupt as ke:
        handle_keyboard_interrupt_properly(ke)
    except Exception as e:
        raise ToolchainInfrastructureError(
            f"Failed to fetch Cosmocc manifest from {manifest_url}: {e}\n"
            f"This may indicate a network issue or that the manifest URL has changed."
        ) from e
