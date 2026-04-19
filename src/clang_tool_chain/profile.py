"""
Install-time profile generation and load-time consumption for zccache integration.

The profile.json file captures everything the zccache shim needs to dispatch a
tool invocation without importing the heavy ``execution.*`` / ``abi.*`` modules.
It is written once per install alongside ``done.txt`` and consumed on every
shim invocation.

See ``docs/ZCCACHE_INTEGRATION_CONTRACTS.md`` section "1. profile.json schema"
for the authoritative schema.

Two halves:
  * Generation side (``generate_profile`` / ``write_profile``): runs at install
    time. May import from anywhere.
  * Consumption side (``load_profile``): runs on the shim hot path. Must stay
    import-light -- only ``json``, ``pathlib``, ``os``, ``sys``, ``datetime``,
    ``dataclasses``.
"""

from __future__ import annotations

import json
import os
import subprocess
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SCHEMA_VERSION = 1


class ProfileMissingError(Exception):
    """Raised when profile.json does not exist at the expected location."""


class ProfileVersionError(Exception):
    """Raised when profile.json has an unknown schema version."""


# ---------------------------------------------------------------------------
# Dataclasses mirroring the on-disk JSON schema.
# ---------------------------------------------------------------------------


@dataclass
class AbiProfile:
    flags_all: list[str] = field(default_factory=list)
    flags_link_only: list[str] = field(default_factory=list)
    # Optional per-ABI fields (populated only where meaningful).
    isysroot: str = ""


@dataclass
class LibDeploy:
    mingw_dll_dir: str = ""
    llvm_objdump: str = ""
    compiler_rt_libs_dir: str = ""
    libunwind_lib_dir: str = ""


@dataclass
class Profile:
    version: int = SCHEMA_VERSION
    generated_at: str = ""
    platform: str = ""
    arch: str = ""
    clang_root: str = ""
    binaries: dict[str, str] = field(default_factory=dict)
    abi_profiles: dict[str, AbiProfile] = field(default_factory=dict)
    sanitizer_env: dict[str, str] = field(default_factory=dict)
    libdeploy: LibDeploy = field(default_factory=LibDeploy)


# ---------------------------------------------------------------------------
# Path helpers.
# ---------------------------------------------------------------------------


def _fwd(p: Path | str) -> str:
    """Normalize a filesystem path to forward slashes for JSON storage."""
    return str(p).replace("\\", "/")


def _exe(name: str, platform: str) -> str:
    return f"{name}.exe" if platform == "win" else name


def _bin(install_dir: Path, name: str, platform: str) -> Path:
    return install_dir / "bin" / _exe(name, platform)


# ---------------------------------------------------------------------------
# Generation side.
# ---------------------------------------------------------------------------


def _discover_binaries(install_dir: Path, platform: str, arch: str) -> dict[str, str]:
    """Build the ``binaries`` block. Only populate keys whose binary exists."""
    bins: dict[str, str] = {}
    clang_root = "{clang_root}"

    for tool in ("clang", "clang++", "clang-tidy", "lld", "llvm-ar", "wasm-ld", "llvm-symbolizer", "llvm-objdump"):
        if _bin(install_dir, tool, platform).exists():
            bins[tool] = f"{clang_root}/bin/{_exe(tool, platform)}"

    # Emscripten: uses ``get_emscripten_install_dir`` which lives outside clang_root.
    try:
        from .path_utils import get_emscripten_install_dir

        emsdk_root = get_emscripten_install_dir(platform, arch)
        if emsdk_root.exists():
            # The launcher script lives at ``<emsdk>/emscripten/emcc.py``; the shim
            # needs the logical entry point, which on all platforms is the python
            # script invoked through the bundled node runtime. We export the path
            # as-is; zccache treats ``.py`` as a normal executable argv[0].
            emcc_py = emsdk_root / "emscripten" / "emcc.py"
            empp_py = emsdk_root / "emscripten" / "em++.py"
            if emcc_py.exists():
                bins["emcc"] = "{emsdk_root}/emscripten/emcc.py"
            if empp_py.exists():
                bins["em++"] = "{emsdk_root}/emscripten/em++.py"
    except Exception:
        pass

    # IWYU: only present if ``get_iwyu_install_dir`` exists.
    try:
        from .path_utils import get_iwyu_install_dir

        iwyu_root = get_iwyu_install_dir(platform, arch)
        iwyu_bin = iwyu_root / "bin" / _exe("include-what-you-use", platform)
        if iwyu_bin.exists():
            bins["iwyu"] = "{iwyu_root}/bin/" + _exe("include-what-you-use", platform)
    except Exception:
        pass

    return bins


def _discover_compiler_rt_libs_dir(install_dir: Path, platform: str, arch: str) -> str:
    """Locate the compiler-rt runtime directory (e.g. lib/clang/<version>/lib/<target>)."""
    clang_lib = install_dir / "lib" / "clang"
    if not clang_lib.exists():
        return ""

    if platform == "win":
        targets = ["windows"]
    elif platform == "linux":
        targets = ["x86_64-unknown-linux-gnu", "linux"] if arch == "x86_64" else ["aarch64-unknown-linux-gnu", "linux"]
    elif platform == "darwin":
        targets = ["darwin"]
    else:
        targets = []

    for version_dir in sorted(clang_lib.iterdir(), reverse=True):
        if not version_dir.is_dir():
            continue
        for tgt in targets:
            candidate = version_dir / "lib" / tgt
            if candidate.exists():
                # Store with ``{clang_root}`` placeholder so the profile is relocatable.
                rel = candidate.relative_to(install_dir)
                return "{clang_root}/" + _fwd(rel)
    return ""


def _build_windows_gnu_flags(arch: str) -> AbiProfile:
    if arch == "x86_64":
        target = "x86_64-w64-windows-gnu"
        sysroot_name = "x86_64-w64-mingw32"
    elif arch == "arm64":
        target = "aarch64-w64-windows-gnu"
        sysroot_name = "aarch64-w64-mingw32"
    else:
        raise ValueError(f"Unsupported Windows GNU arch: {arch}")

    flags_all = [
        f"--target={target}",
        "--sysroot={clang_root}/" + sysroot_name,
        "-stdlib=libc++",
        "-I{clang_root}/include/c++/v1",
        "-isystem{clang_root}/include",
    ]
    flags_link_only = [
        "-rtlib=compiler-rt",
        "-fuse-ld=lld",
        "--unwindlib=libunwind",
        "-static-libgcc",
        "-static-libstdc++",
        "-lpthread",
    ]
    return AbiProfile(flags_all=flags_all, flags_link_only=flags_link_only)


def _build_windows_msvc_flags(arch: str) -> AbiProfile:
    if arch == "x86_64":
        target = "x86_64-pc-windows-msvc"
    elif arch == "arm64":
        target = "aarch64-pc-windows-msvc"
    else:
        raise ValueError(f"Unsupported Windows MSVC arch: {arch}")
    return AbiProfile(flags_all=[f"--target={target}"], flags_link_only=[])


def _build_linux_flags() -> AbiProfile:
    # ``flags_all`` is empty on Linux: the bundled clang driver's default target
    # triple is already correct. Linker flags match the LLDLinkerTransformer.
    return AbiProfile(flags_all=[], flags_link_only=["-fuse-ld=lld"])


def _detect_macos_sdk_path() -> str:
    """Call ``xcrun --show-sdk-path`` once; return empty string on failure."""
    try:
        result = subprocess.run(
            ["xcrun", "--show-sdk-path"],
            capture_output=True,
            text=True,
            check=True,
            timeout=5,
        )
        sdk_path = result.stdout.strip()
        if sdk_path and Path(sdk_path).exists():
            return _fwd(sdk_path)
    except (FileNotFoundError, subprocess.CalledProcessError, subprocess.TimeoutExpired):
        pass
    except Exception:
        pass
    return ""


def _build_darwin_flags() -> AbiProfile:
    profile = AbiProfile(flags_all=[], flags_link_only=["-fuse-ld=lld"])
    sdk_path = _detect_macos_sdk_path()
    if sdk_path:
        profile.isysroot = sdk_path
        profile.flags_all = ["-isysroot", sdk_path]
    return profile


def _build_abi_profiles(platform: str, arch: str) -> dict[str, AbiProfile]:
    if platform == "win":
        return {
            "gnu": _build_windows_gnu_flags(arch),
            "msvc": _build_windows_msvc_flags(arch),
        }
    if platform == "linux":
        return {"linux": _build_linux_flags()}
    if platform == "darwin":
        return {"darwin": _build_darwin_flags()}
    return {}


def _build_sanitizer_env(install_dir: Path, platform: str) -> dict[str, str]:
    env: dict[str, str] = {}
    symbolizer = _bin(install_dir, "llvm-symbolizer", platform)
    if symbolizer.exists():
        env["ASAN_SYMBOLIZER_PATH"] = "{clang_root}/bin/" + _exe("llvm-symbolizer", platform)
    if platform == "win":
        # LSAN is unsupported on Windows; omit detect_leaks.
        env["ASAN_OPTIONS_DEFAULTS"] = "fast_unwind_on_malloc=0:symbolize=1"
    else:
        env["ASAN_OPTIONS_DEFAULTS"] = "fast_unwind_on_malloc=0:symbolize=1:detect_leaks=1"
    return env


def _build_libdeploy(install_dir: Path, platform: str, arch: str) -> LibDeploy:
    lib = LibDeploy()
    lib.compiler_rt_libs_dir = _discover_compiler_rt_libs_dir(install_dir, platform, arch)

    if platform == "win":
        sysroot_name = "x86_64-w64-mingw32" if arch == "x86_64" else "aarch64-w64-mingw32"
        sysroot_bin = install_dir / sysroot_name / "bin"
        if sysroot_bin.exists():
            lib.mingw_dll_dir = "{clang_root}/" + sysroot_name + "/bin"
        objdump = _bin(install_dir, "llvm-objdump", platform)
        if objdump.exists():
            lib.llvm_objdump = "{clang_root}/bin/" + _exe("llvm-objdump", platform)
    elif platform == "linux":
        lib_dir = install_dir / "lib"
        if lib_dir.exists() and (install_dir / "include" / "libunwind.h").exists():
            lib.libunwind_lib_dir = "{clang_root}/lib"
    # macOS: compiler_rt_libs_dir only.
    return lib


def generate_profile(install_dir: Path, platform: str, arch: str) -> Profile:
    """Discover everything needed for profile.json and return a Profile."""
    profile = Profile(
        version=SCHEMA_VERSION,
        generated_at=datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        platform=platform,
        arch=arch,
        clang_root=_fwd(install_dir),
        binaries=_discover_binaries(install_dir, platform, arch),
        abi_profiles=_build_abi_profiles(platform, arch),
        sanitizer_env=_build_sanitizer_env(install_dir, platform),
        libdeploy=_build_libdeploy(install_dir, platform, arch),
    )
    return profile


def _profile_to_dict(profile: Profile) -> dict[str, Any]:
    d = asdict(profile)
    # Strip empty optional strings from libdeploy / abi isysroot for a clean JSON.
    d["libdeploy"] = {k: v for k, v in d["libdeploy"].items() if v}
    for abi_data in d["abi_profiles"].values():
        if not abi_data.get("isysroot"):
            abi_data.pop("isysroot", None)
    return d


def write_profile(profile: Profile, install_dir: Path) -> Path:
    """Serialize to ``{install_dir}/profile.json`` with atomic write."""
    install_dir.mkdir(parents=True, exist_ok=True)
    final_path = install_dir / "profile.json"
    tmp_path = install_dir / "profile.json.tmp"
    payload = json.dumps(_profile_to_dict(profile), indent=2, sort_keys=False)
    tmp_path.write_text(payload, encoding="utf-8")
    # Atomic rename (cross-platform; os.replace handles existing target).
    os.replace(tmp_path, final_path)
    return final_path


# ---------------------------------------------------------------------------
# Consumption side. Keep imports minimal.
# ---------------------------------------------------------------------------


_profile_cache: Profile | None = None


def _get_install_dir_light(platform: str, arch: str) -> Path:
    """Import-light mirror of ``path_utils.get_install_dir``."""
    env_override = os.environ.get("CLANG_TOOL_CHAIN_DOWNLOAD_PATH")
    base = Path(env_override) if env_override else Path.home() / ".clang-tool-chain"
    return base / "clang" / platform / arch


def _detect_platform_arch_light() -> tuple[str, str]:
    """Import-light platform/arch detection mirroring ``platform.detection``."""
    import platform as _platform

    system = _platform.system().lower()
    machine = _platform.machine().lower()
    if system == "windows":
        plat = "win"
    elif system == "linux":
        plat = "linux"
    elif system == "darwin":
        plat = "darwin"
    else:
        raise RuntimeError(f"Unsupported platform: {system}")
    if machine in ("x86_64", "amd64"):
        arch = "x86_64"
    elif machine in ("aarch64", "arm64"):
        arch = "arm64"
    else:
        raise RuntimeError(f"Unsupported architecture: {machine}")
    return plat, arch


def _substitute_placeholders(value: str, clang_root: str, emsdk_root: str, iwyu_root: str) -> str:
    out = value.replace("{clang_root}", clang_root)
    if emsdk_root:
        out = out.replace("{emsdk_root}", emsdk_root)
    if iwyu_root:
        out = out.replace("{iwyu_root}", iwyu_root)
    return out


def _resolve_emsdk_root(platform: str, arch: str) -> str:
    env_override = os.environ.get("CLANG_TOOL_CHAIN_DOWNLOAD_PATH")
    base = Path(env_override) if env_override else Path.home() / ".clang-tool-chain"
    candidate = base / "emscripten" / platform / arch
    return _fwd(candidate) if candidate.exists() else ""


def _resolve_iwyu_root(platform: str, arch: str) -> str:
    env_override = os.environ.get("CLANG_TOOL_CHAIN_DOWNLOAD_PATH")
    base = Path(env_override) if env_override else Path.home() / ".clang-tool-chain"
    candidate = base / "iwyu" / platform / arch
    return _fwd(candidate) if candidate.exists() else ""


def load_profile(install_dir: Path | None = None) -> Profile:
    """Read profile.json, apply placeholder substitution, cache it."""
    global _profile_cache
    if _profile_cache is not None and install_dir is None:
        return _profile_cache

    if install_dir is None:
        platform_name, arch = _detect_platform_arch_light()
        install_dir = _get_install_dir_light(platform_name, arch)

    profile_path = install_dir / "profile.json"
    if not profile_path.exists():
        raise ProfileMissingError(
            f"profile.json not found at {profile_path}. Run 'clang-tool-chain install clang' to regenerate."
        )

    try:
        raw = json.loads(profile_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ProfileMissingError(f"Could not read profile.json at {profile_path}: {exc}") from exc

    version = raw.get("version")
    if version != SCHEMA_VERSION:
        raise ProfileVersionError(
            f"profile.json schema version {version!r} is not supported "
            f"(expected {SCHEMA_VERSION}). Reinstall to regenerate."
        )

    platform_name = raw.get("platform", "")
    arch = raw.get("arch", "")
    clang_root = raw.get("clang_root", _fwd(install_dir))
    emsdk_root = _resolve_emsdk_root(platform_name, arch) if platform_name else ""
    iwyu_root = _resolve_iwyu_root(platform_name, arch) if platform_name else ""

    def _sub(v: str) -> str:
        return _substitute_placeholders(v, clang_root, emsdk_root, iwyu_root)

    binaries = {k: _sub(v) for k, v in raw.get("binaries", {}).items()}
    # Drop binaries whose placeholder could not be resolved (e.g. emcc when
    # emsdk isn't installed): if the substitution left a literal {placeholder}
    # the tool is effectively unavailable.
    binaries = {k: v for k, v in binaries.items() if "{" not in v}

    abi_profiles: dict[str, AbiProfile] = {}
    for abi_name, abi_raw in raw.get("abi_profiles", {}).items():
        if abi_raw is None:
            continue
        abi_profiles[abi_name] = AbiProfile(
            flags_all=[_sub(x) for x in abi_raw.get("flags_all", [])],
            flags_link_only=[_sub(x) for x in abi_raw.get("flags_link_only", [])],
            isysroot=_sub(abi_raw.get("isysroot", "")),
        )

    sanitizer_env = {k: _sub(v) for k, v in raw.get("sanitizer_env", {}).items()}

    lib_raw = raw.get("libdeploy", {}) or {}
    libdeploy = LibDeploy(
        mingw_dll_dir=_sub(lib_raw.get("mingw_dll_dir", "")),
        llvm_objdump=_sub(lib_raw.get("llvm_objdump", "")),
        compiler_rt_libs_dir=_sub(lib_raw.get("compiler_rt_libs_dir", "")),
        libunwind_lib_dir=_sub(lib_raw.get("libunwind_lib_dir", "")),
    )

    profile = Profile(
        version=SCHEMA_VERSION,
        generated_at=raw.get("generated_at", ""),
        platform=platform_name,
        arch=arch,
        clang_root=clang_root,
        binaries=binaries,
        abi_profiles=abi_profiles,
        sanitizer_env=sanitizer_env,
        libdeploy=libdeploy,
    )

    _profile_cache = profile
    return profile


def _reset_cache_for_tests() -> None:
    """Clear the module-global profile cache. Test-only helper."""
    global _profile_cache
    _profile_cache = None


__all__ = [
    "SCHEMA_VERSION",
    "AbiProfile",
    "LibDeploy",
    "Profile",
    "ProfileMissingError",
    "ProfileVersionError",
    "generate_profile",
    "load_profile",
    "write_profile",
]
