"""
CLI entry point for ``clang-tool-chain-libdeploy``.

Called by zccache via the ``ZCCACHE_LINK_DEPLOY_CMD`` post-link hook after a
cache-miss link. Receives the linker output path as ``argv[1]`` and deploys
runtime dependencies (MinGW DLLs on Windows, libc++/libunwind on Linux/macOS,
etc.) next to the output.

Contract (see ``docs/ZCCACHE_INTEGRATION_CONTRACTS.md`` §4):

* Errors are non-fatal — warnings go to stderr and the process exits 0 so a
  deployment failure does not poison the zccache entry for an otherwise
  successful build.
* Idempotent — calling twice with the same output path is a no-op second time.
* Silent on success, unless ``CLANG_TOOL_CHAIN_LIB_DEPLOY_VERBOSE=1`` is set.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

_VERBOSE_ENV = "CLANG_TOOL_CHAIN_LIB_DEPLOY_VERBOSE"


def _verbose() -> bool:
    return os.environ.get(_VERBOSE_ENV) == "1"


def _log(msg: str) -> None:
    if _verbose():
        sys.stderr.write(f"[libdeploy] {msg}\n")


def _warn(msg: str) -> None:
    sys.stderr.write(f"[libdeploy] warning: {msg}\n")


def _classify(output_path: Path) -> str | None:
    """Return ``'windows'``, ``'linux'``, ``'darwin'``, or ``None`` for unsupported."""
    suffix = output_path.suffix.lower()
    name = output_path.name

    if suffix in (".exe", ".dll"):
        return "windows"
    if suffix == ".dylib":
        return "darwin"
    if suffix == ".so" or ".so." in name:
        return "linux"

    # No recognized suffix — sniff magic bytes for suffix-less Unix executables.
    if output_path.is_file():
        try:
            with output_path.open("rb") as fh:
                magic = fh.read(4)
        except OSError as exc:
            _log(f"cannot read magic bytes from {output_path}: {exc}")
            return None

        if magic[:4] == b"\x7fELF":
            return "linux"
        if magic[:4] in (
            b"\xfe\xed\xfa\xce",
            b"\xfe\xed\xfa\xcf",
            b"\xcf\xfa\xed\xfe",
            b"\xce\xfa\xed\xfe",
            b"\xca\xfe\xba\xbe",
        ):
            return "darwin"
        if magic[:2] == b"MZ":
            return "windows"

    return None


def _deploy_windows(output_path: Path) -> None:
    from clang_tool_chain.deployment.dll_deployer import post_link_dll_deployment

    # Windows deployment currently requires the GNU ABI flag; profile-driven
    # detection is done inside the deployer, so we pass ``use_gnu_abi=True``
    # (the only abi that needs MinGW runtime DLLs).
    post_link_dll_deployment(output_path, "win", use_gnu_abi=True)


def _deploy_linux(output_path: Path) -> None:
    from clang_tool_chain.deployment.so_deployer import post_link_so_deployment

    arch = _detect_arch_linux()
    post_link_so_deployment(output_path, arch=arch)


def _deploy_darwin(output_path: Path) -> None:
    from clang_tool_chain.deployment.dylib_deployer import post_link_dylib_deployment

    arch = _detect_arch_darwin()
    post_link_dylib_deployment(output_path, arch=arch)


def _detect_arch_linux() -> str:
    import platform

    machine = platform.machine().lower()
    if machine in ("aarch64", "arm64"):
        return "aarch64"
    return "x86_64"


def _detect_arch_darwin() -> str:
    import platform

    machine = platform.machine().lower()
    if machine in ("arm64", "aarch64"):
        return "arm64"
    return "x86_64"


def main() -> None:
    """Post-link deployment entry point. Always exits 0."""
    if len(sys.argv) < 2:
        _warn("no output path provided; expected `clang-tool-chain-libdeploy <output>`")
        sys.exit(0)

    raw = sys.argv[1]
    output_path = Path(raw)
    if not output_path.is_absolute():
        output_path = output_path.resolve()

    if not output_path.exists():
        _warn(f"output path does not exist: {output_path}")
        sys.exit(0)

    # Ensure the profile is present before dispatching. This is cheap (single
    # JSON read) and gives a clean warning rather than a deep ImportError later.
    try:
        from clang_tool_chain.profile import load_profile

        load_profile()
    except Exception as exc:  # noqa: BLE001 - non-fatal; warn and bail
        _warn(f"profile unavailable ({exc}); skipping deployment for {output_path.name}")
        sys.exit(0)

    kind = _classify(output_path)
    if kind is None:
        _log(f"skipping {output_path.name}: unrecognized output type")
        sys.exit(0)

    _log(f"deploying dependencies for {output_path} (kind={kind})")

    try:
        if kind == "windows":
            _deploy_windows(output_path)
        elif kind == "linux":
            _deploy_linux(output_path)
        elif kind == "darwin":
            _deploy_darwin(output_path)
    except Exception as exc:  # noqa: BLE001 - contract: non-fatal on any error
        _warn(f"deployment failed for {output_path.name}: {exc}")
        sys.exit(0)

    _log(f"done: {output_path.name}")
    sys.exit(0)


if __name__ == "__main__":
    main()
