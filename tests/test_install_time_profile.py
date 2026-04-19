"""
Unit tests for ``clang_tool_chain.profile`` (P2 install-time profile).

These tests exercise the profile.json generation and load-time substitution
contract documented in ``docs/ZCCACHE_INTEGRATION_CONTRACTS.md`` section 1.

The module is being written concurrently with these tests. We use
``pytest.importorskip`` so the file can be collected and committed before
the implementation lands.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path  # noqa: TC003 — imported at runtime by fixtures

import pytest

profile_mod = pytest.importorskip("clang_tool_chain.profile")


IS_WINDOWS = sys.platform == "win32"
IS_LINUX = sys.platform == "linux"
IS_MACOS = sys.platform == "darwin"


# ---------------------------------------------------------------------------
# Helpers — fabricate a minimal install-dir layout so ``generate_profile``
# has something to discover.
# ---------------------------------------------------------------------------


def _make_fake_install(install_dir: Path, platform: str, arch: str) -> Path:
    """Populate ``install_dir`` with the empty binaries ``generate_profile`` looks for."""
    ext = ".exe" if platform == "win" else ""
    bin_dir = install_dir / "bin"
    bin_dir.mkdir(parents=True, exist_ok=True)
    for tool in (
        "clang",
        "clang++",
        "clang-tidy",
        "lld",
        "llvm-ar",
        "wasm-ld",
        "llvm-symbolizer",
        "llvm-objdump",
    ):
        (bin_dir / f"{tool}{ext}").write_bytes(b"")

    # Platform-specific scaffolding.
    if platform == "win":
        sysroot_name = "x86_64-w64-mingw32" if arch == "x86_64" else "aarch64-w64-mingw32"
        (install_dir / sysroot_name / "bin").mkdir(parents=True, exist_ok=True)
        # A stub DLL so libdeploy detection has something to pin to.
        (install_dir / sysroot_name / "bin" / "libgcc_s_seh-1.dll").write_bytes(b"")
    elif platform == "linux":
        (install_dir / "lib").mkdir(parents=True, exist_ok=True)
        (install_dir / "include").mkdir(parents=True, exist_ok=True)
        (install_dir / "include" / "libunwind.h").write_bytes(b"")

    # Compiler-rt layout — ``lib/clang/<ver>/lib/<target>``.
    if platform == "win":
        target_dirs = ["windows"]
    elif platform == "linux":
        target_dirs = ["x86_64-unknown-linux-gnu" if arch == "x86_64" else "aarch64-unknown-linux-gnu"]
    elif platform == "darwin":
        target_dirs = ["darwin"]
    else:
        target_dirs = []
    for tgt in target_dirs:
        (install_dir / "lib" / "clang" / "21" / "lib" / tgt).mkdir(parents=True, exist_ok=True)
        # Drop a stub runtime so directory is non-empty.
        (install_dir / "lib" / "clang" / "21" / "lib" / tgt / "clang_rt.builtins.a").write_bytes(b"")

    return install_dir


def _default_platform_arch() -> tuple[str, str]:
    if IS_WINDOWS:
        return "win", "x86_64"
    if IS_LINUX:
        return "linux", "x86_64"
    if IS_MACOS:
        return "darwin", "arm64"
    pytest.skip(f"Unsupported platform for profile tests: {sys.platform}")


@pytest.fixture(autouse=True)
def _reset_profile_cache():
    """Ensure each test starts with a cold profile cache."""
    reset = getattr(profile_mod, "_reset_cache_for_tests", None)
    if callable(reset):
        reset()
    yield
    if callable(reset):
        reset()


# ---------------------------------------------------------------------------
# Schema / shape tests
# ---------------------------------------------------------------------------


def test_schema_version_is_1(tmp_path: Path) -> None:
    plat, arch = _default_platform_arch()
    install = _make_fake_install(tmp_path / "install", plat, arch)

    profile = profile_mod.generate_profile(install, plat, arch)

    assert profile.version == 1
    assert profile_mod.SCHEMA_VERSION == 1


def _iter_path_strings(profile) -> list[str]:  # type: ignore[no-untyped-def]
    """Yield every string in the profile that is expected to be a filesystem path."""
    out: list[str] = []
    out.extend(profile.binaries.values())
    for abi in profile.abi_profiles.values():
        out.extend(abi.flags_all)
        # flags_link_only are flags — they never contain backslashes, but include anyway.
        out.extend(abi.flags_link_only)
        if abi.isysroot:
            out.append(abi.isysroot)
    libdeploy = profile.libdeploy
    for field_name in ("mingw_dll_dir", "llvm_objdump", "compiler_rt_libs_dir", "libunwind_lib_dir"):
        value = getattr(libdeploy, field_name, "")
        if value:
            out.append(value)
    return out


def test_binaries_use_forward_slashes(tmp_path: Path) -> None:
    plat, arch = _default_platform_arch()
    install = _make_fake_install(tmp_path / "install", plat, arch)
    profile = profile_mod.generate_profile(install, plat, arch)

    for value in _iter_path_strings(profile):
        assert "\\" not in value, f"Backslash found in profile value: {value!r}"


def test_generate_populates_libdeploy_for_platform(tmp_path: Path) -> None:
    plat, arch = _default_platform_arch()
    install = _make_fake_install(tmp_path / "install", plat, arch)
    profile = profile_mod.generate_profile(install, plat, arch)

    # compiler_rt_libs_dir should be detected on every platform — we created
    # the directory tree for it in the fixture.
    assert profile.libdeploy.compiler_rt_libs_dir, "compiler_rt_libs_dir unexpectedly empty"
    assert profile.libdeploy.compiler_rt_libs_dir.startswith("{clang_root}/")

    if plat == "win":
        assert profile.libdeploy.mingw_dll_dir, "mingw_dll_dir unexpectedly empty for win"
        assert "mingw32" in profile.libdeploy.mingw_dll_dir
        assert profile.libdeploy.llvm_objdump, "llvm_objdump unexpectedly empty for win"
    elif plat == "linux":
        assert profile.libdeploy.libunwind_lib_dir, "libunwind_lib_dir unexpectedly empty for linux"
        assert profile.libdeploy.libunwind_lib_dir.endswith("/lib")


# ---------------------------------------------------------------------------
# Load-time behaviour
# ---------------------------------------------------------------------------


def test_placeholder_substitution_on_load(tmp_path: Path) -> None:
    """A literal ``{clang_root}`` in the on-disk profile becomes an absolute path."""
    plat, arch = _default_platform_arch()
    install = _make_fake_install(tmp_path / "install", plat, arch)

    # Hand-craft a minimal profile.json containing a placeholder binary.
    payload = {
        "version": 1,
        "generated_at": "2026-01-01T00:00:00Z",
        "platform": plat,
        "arch": arch,
        "clang_root": str(install).replace("\\", "/"),
        "binaries": {
            "clang": "{clang_root}/bin/clang" + (".exe" if plat == "win" else ""),
        },
        "abi_profiles": {},
        "sanitizer_env": {},
        "libdeploy": {},
    }
    (install / "profile.json").write_text(json.dumps(payload), encoding="utf-8")

    loaded = profile_mod.load_profile(install)

    assert "clang" in loaded.binaries
    resolved = loaded.binaries["clang"]
    assert "{clang_root}" not in resolved
    assert "{" not in resolved  # no leftover placeholders at all
    assert resolved.startswith(str(install).replace("\\", "/"))


def test_load_profile_raises_if_missing(tmp_path: Path) -> None:
    empty = tmp_path / "empty"
    empty.mkdir()

    with pytest.raises(profile_mod.ProfileMissingError):
        profile_mod.load_profile(empty)


def test_load_profile_raises_on_unknown_version(tmp_path: Path) -> None:
    install = tmp_path / "install"
    install.mkdir()
    payload = {
        "version": 99,
        "generated_at": "2026-01-01T00:00:00Z",
        "platform": "win",
        "arch": "x86_64",
        "clang_root": str(install).replace("\\", "/"),
        "binaries": {},
        "abi_profiles": {},
        "sanitizer_env": {},
        "libdeploy": {},
    }
    (install / "profile.json").write_text(json.dumps(payload), encoding="utf-8")

    version_err = getattr(profile_mod, "ProfileVersionError", None)
    if version_err is None:
        pytest.skip("ProfileVersionError not exported yet")

    with pytest.raises(version_err):
        profile_mod.load_profile(install)


def test_round_trip_write_and_load(tmp_path: Path) -> None:
    plat, arch = _default_platform_arch()
    install = _make_fake_install(tmp_path / "install", plat, arch)

    original = profile_mod.generate_profile(install, plat, arch)
    path = profile_mod.write_profile(original, install)
    assert path.exists()
    assert path.name == "profile.json"

    loaded = profile_mod.load_profile(install)

    # Version / platform / arch survive exactly.
    assert loaded.version == original.version
    assert loaded.platform == original.platform
    assert loaded.arch == original.arch

    # Binary keys match (though values are now resolved, not placeholder'd).
    assert set(loaded.binaries.keys()) == set(original.binaries.keys())

    # Every loaded path is absolute (or at least placeholder-free).
    for resolved in loaded.binaries.values():
        assert "{clang_root}" not in resolved

    # abi_profiles names round-trip.
    assert set(loaded.abi_profiles.keys()) == set(original.abi_profiles.keys())


# ---------------------------------------------------------------------------
# Platform-gated structural tests
# ---------------------------------------------------------------------------


@pytest.mark.skipif(not IS_WINDOWS, reason="Windows-specific ABI profiles")
def test_windows_has_gnu_and_msvc_profiles(tmp_path: Path) -> None:
    install = _make_fake_install(tmp_path / "install", "win", "x86_64")
    profile = profile_mod.generate_profile(install, "win", "x86_64")

    assert "gnu" in profile.abi_profiles
    assert "msvc" in profile.abi_profiles

    gnu = profile.abi_profiles["gnu"]
    assert any(f == "--target=x86_64-w64-windows-gnu" for f in gnu.flags_all)
    assert any(f == "-fuse-ld=lld" for f in gnu.flags_link_only)

    msvc = profile.abi_profiles["msvc"]
    assert msvc.flags_all == ["--target=x86_64-pc-windows-msvc"]
    assert msvc.flags_link_only == []


@pytest.mark.skipif(not IS_LINUX, reason="Linux-specific ABI profile")
def test_linux_has_single_linux_profile(tmp_path: Path) -> None:
    install = _make_fake_install(tmp_path / "install", "linux", "x86_64")
    profile = profile_mod.generate_profile(install, "linux", "x86_64")

    assert set(profile.abi_profiles.keys()) == {"linux"}
    assert "-fuse-ld=lld" in profile.abi_profiles["linux"].flags_link_only


@pytest.mark.skipif(not IS_MACOS, reason="macOS-specific ABI profile")
def test_darwin_has_single_darwin_profile(tmp_path: Path) -> None:
    install = _make_fake_install(tmp_path / "install", "darwin", "arm64")
    profile = profile_mod.generate_profile(install, "darwin", "arm64")

    assert set(profile.abi_profiles.keys()) == {"darwin"}
    assert "-fuse-ld=lld" in profile.abi_profiles["darwin"].flags_link_only
