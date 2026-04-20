"""
Thin Python shim that execs into the ``zccache`` Rust binary.

This module is intentionally import-light: it pulls only stdlib plus
``clang_tool_chain.profile`` (which is also kept light). It must NOT import
``execution.*``, ``arg_transformers``, ``platform.detection``, ``installer``,
``downloader``, or any heavy module — those cost hundreds of milliseconds at
startup and defeat the point of moving to a native cache.

Public API (see ``docs/ZCCACHE_INTEGRATION_CONTRACTS.md`` §2):

* :func:`find_zccache_binary`
* :func:`load_profile`
* :func:`exec_via_zccache`
* :func:`parse_directives_fast`
* :class:`ProfileMissingError`
"""

from __future__ import annotations

import logging
import os
import platform as _platform_mod
import re
import shutil
import sys
from pathlib import Path
from typing import Literal, NoReturn

from clang_tool_chain.profile import Profile, ProfileMissingError
from clang_tool_chain.profile import load_profile as _load_profile

__all__ = [
    "ABI",
    "ProfileMissingError",
    "ToolName",
    "exec_via_zccache",
    "find_zccache_binary",
    "load_profile",
    "parse_directives_fast",
]

ToolName = Literal["clang", "clang++", "emcc", "em++", "wasm-ld", "clang-tidy", "iwyu"]
ABI = Literal["auto", "gnu", "msvc", "linux", "darwin"]

_logger = logging.getLogger(__name__)
if os.environ.get("CTC_SHIM_DEBUG") == "1" and not _logger.handlers:
    _handler = logging.StreamHandler(sys.stderr)
    _handler.setFormatter(logging.Formatter("[ctc-shim] %(message)s"))
    _logger.addHandler(_handler)
    _logger.setLevel(logging.DEBUG)

_SOURCE_SUFFIXES = frozenset({".c", ".cpp", ".cc", ".cxx", ".c++", ".m", ".mm"})
_DIRECTIVE_RE = re.compile(r"^\s*//\s*@(link|cflags|ldflags|std|include|platform)\s*:\s*(.+?)\s*$")
_DIRECTIVE_SCAN_LINES = 200


def find_zccache_binary() -> Path | None:
    """Locate the ``zccache`` executable.

    Lookup order:
      1. ``Path(sys.executable).parent`` — the venv/Scripts dir where pip
         installs console scripts alongside this package.
      2. ``PATH`` via :func:`shutil.which`.

    Returns ``None`` if not found. Callers are expected to emit an actionable
    error and exit.
    """
    exe_name = "zccache.exe" if os.name == "nt" else "zccache"
    local = Path(sys.executable).parent / exe_name
    if local.is_file():
        return local

    found = shutil.which("zccache")
    if found:
        return Path(found)
    return None


def load_profile() -> Profile:
    """Load the active ``profile.json``. Delegates to :mod:`clang_tool_chain.profile`."""
    return _load_profile()


def parse_directives_fast(args: list[str]) -> list[str]:
    """Scan source files in ``args`` for ``// @directive:`` lines.

    Only recognises the six directives covered by the contract (``link``,
    ``cflags``, ``ldflags``, ``std``, ``include``, ``platform``). Full parsing
    (platform gating, package-config, etc.) lives in
    :mod:`clang_tool_chain.directives.parser`; this routine is the hot-path
    subset.

    Environment:
        CLANG_TOOL_CHAIN_NO_DIRECTIVES=1 — short-circuits to ``[]``.
        CLANG_TOOL_CHAIN_DIRECTIVE_VERBOSE=1 — dumps parsed flags to stderr.
    """
    if os.environ.get("CLANG_TOOL_CHAIN_NO_DIRECTIVES") == "1":
        return []

    verbose = os.environ.get("CLANG_TOOL_CHAIN_DIRECTIVE_VERBOSE") == "1"
    flags: list[str] = []
    host = _host_platform_key()

    for arg in args:
        if not arg or arg.startswith("-"):
            continue
        suffix = _suffix_lower(arg)
        if suffix not in _SOURCE_SUFFIXES:
            continue
        path = Path(arg)
        if not path.is_file():
            continue
        try:
            with path.open("r", encoding="utf-8", errors="replace") as fh:
                lines = [next(fh, "") for _ in range(_DIRECTIVE_SCAN_LINES)]
        except OSError:
            continue

        in_platform_block: str | None = None
        for line in lines:
            if not line:
                continue
            match = _DIRECTIVE_RE.match(line)
            if not match:
                continue
            name, value = match.group(1), match.group(2).strip()

            if name == "platform":
                in_platform_block = value.strip().lower() or None
                continue
            if in_platform_block is not None and in_platform_block != host:
                continue

            flags.extend(_directive_to_flags(name, value))

    if verbose and flags:
        sys.stderr.write(f"[ctc-directives] {' '.join(flags)}\n")
    return flags


def exec_via_zccache(
    tool: ToolName,
    *,
    use_cache: bool,
    abi: ABI = "auto",
) -> NoReturn:
    """Build the zccache argv and exec. Never returns.

    See ``docs/ZCCACHE_INTEGRATION_CONTRACTS.md`` §2 for the exact argv order
    and environment contract.
    """
    zccache = find_zccache_binary()
    if zccache is None:
        sys.stderr.write(
            "error: `zccache` binary not found.\n"
            "       Install it with: pip install 'zccache>=1.3.0'\n"
            "       (installed alongside this package's venv, or anywhere on PATH).\n"
        )
        sys.exit(1)

    try:
        profile = load_profile()
    except ProfileMissingError:
        # Auto-install (matches legacy `clang-tool-chain-c` first-use behavior).
        # Also regenerates profile.json on pre-v1.4 installs that pre-date the
        # profile-bake installer hook.
        if _auto_install_or_regenerate_profile():
            try:
                profile = load_profile()
            except ProfileMissingError:
                sys.stderr.write(
                    "error: profile.json still missing after install; run `clang-tool-chain install clang` manually.\n"
                )
                sys.exit(1)
        else:
            sys.stderr.write("error: toolchain install failed. Run `clang-tool-chain install clang` manually.\n")
            sys.exit(1)

    user_args = list(sys.argv[1:])
    user_args, abi_override = _consume_ctc_abi_flag(user_args)
    user_args, deploy_requested = _consume_deploy_dependencies_flag(user_args)
    user_args = _strip_unsupported_windows_linker_flags(user_args)
    user_args = _inject_shared_libasan_if_needed(user_args)
    resolved_abi = _resolve_abi(abi, user_args, abi_override)

    abi_profile = profile.abi_profiles.get(resolved_abi)
    if abi_profile is None:
        available = ", ".join(sorted(profile.abi_profiles.keys())) or "<none>"
        sys.stderr.write(
            f"error: ABI profile '{resolved_abi}' not available on this platform. Available profiles: {available}.\n"
        )
        sys.exit(1)

    directive_flags = parse_directives_fast(user_args)
    is_no_link = _is_no_link_invocation(user_args)
    user_has_target = any(a.startswith("--target=") or a == "--target" for a in user_args)

    def _drop_target(flags: list[str]) -> list[str]:
        # When the user supplied --target= explicitly, let them win — strip
        # any --target= we were going to inject from the profile.
        if not user_has_target:
            return flags
        return [f for f in flags if not f.startswith("--target=") and f != "--target"]

    merged: list[str] = []
    merged.extend(user_args)
    merged.extend(directive_flags)
    merged.extend(_drop_target(abi_profile.flags_all))
    if not is_no_link:
        merged.extend(_drop_target(abi_profile.flags_link_only))

    compiler_path = _resolve_tool_path(profile, tool)
    argv = [str(zccache), compiler_path, *merged]

    env = os.environ.copy()
    if use_cache:
        env["ZCCACHE_LINK_DEPLOY_CMD"] = "clang-tool-chain-libdeploy"
        env.pop("ZCCACHE_DISABLE", None)
    else:
        env["ZCCACHE_DISABLE"] = "1"

    _logger.debug("exec argv: %r", argv)
    _logger.debug(
        "use_cache=%s abi=%s compiler=%s deploy=%s",
        use_cache,
        resolved_abi,
        compiler_path,
        deploy_requested,
    )

    # Use subprocess + sys.exit uniformly. os.execvpe on Windows is an
    # emulation that intermittently crashes with 0xC0000005 when the spawned
    # process itself forks children (as zccache does when it runs clang).
    # Using subprocess is a few ms slower but always correct.
    import subprocess

    rc = subprocess.run(argv, env=env).returncode

    # Post-link deployment decision:
    #   1. Explicit --deploy-dependencies → always deploy
    #   2. Windows GNU ABI + linking an .exe/.dll → auto-deploy MinGW DLLs
    #      (mirrors legacy `post_link_dll_deployment` — the runtime DLLs
    #      libwinpthread-1.dll, libstdc++-6.dll, etc. must sit next to the
    #      exe or it fails at launch with STATUS_DLL_NOT_FOUND).
    #   3. ZCCACHE_LINK_DEPLOY_CMD hook handles everything in cache mode.
    if rc == 0 and not is_no_link and not use_cache:
        output_path = _extract_output_path(user_args)
        should_deploy = deploy_requested or (
            _host_platform_key() == "windows"
            and resolved_abi == "gnu"
            and output_path is not None
            and _suffix_lower(str(output_path)) in {".exe", ".dll"}
        )
        if should_deploy and output_path is not None:
            _run_libdeploy(output_path, env)
    sys.exit(rc)


# ---------------------------------------------------------------------------
# Internals
# ---------------------------------------------------------------------------


def _suffix_lower(arg: str) -> str:
    idx = arg.rfind(".")
    if idx < 0:
        return ""
    # Guard against paths like ``./foo`` or ``../foo``.
    slash = max(arg.rfind("/"), arg.rfind(os.sep))
    if idx < slash:
        return ""
    return arg[idx:].lower()


def _directive_to_flags(name: str, value: str) -> list[str]:
    value = value.strip()
    if not value:
        return []

    if name == "link":
        return [f"-l{lib}" for lib in _split_list(value)]
    if name == "cflags":
        return _split_shell(value)
    if name == "ldflags":
        return _split_shell(value)
    if name == "std":
        return [f"-std={value}"]
    if name == "include":
        return [f"-I{inc}" for inc in _split_list(value)]
    return []


def _split_list(value: str) -> list[str]:
    """Split a directive value that may be ``[a, b, c]`` or ``a`` or ``a b c``."""
    v = value.strip()
    if v.startswith("[") and v.endswith("]"):
        v = v[1:-1]
    parts = [p.strip() for p in re.split(r"[,\s]+", v) if p.strip()]
    return parts


def _split_shell(value: str) -> list[str]:
    # Lightweight shell split — good enough for the hot path. Users with
    # quoted whitespace values can rely on the full directives.parser path
    # invoked by the install-time profile bake.
    return [tok for tok in value.split() if tok]


def _host_platform_key() -> str:
    system = _platform_mod.system().lower()
    if system == "windows":
        return "windows"
    if system == "darwin":
        return "darwin"
    return "linux"


def _consume_ctc_abi_flag(args: list[str]) -> tuple[list[str], str | None]:
    """Remove ``--ctc-abi=<value>`` / ``--ctc-abi <value>`` from args."""
    out: list[str] = []
    override: str | None = None
    i = 0
    while i < len(args):
        a = args[i]
        if a == "--ctc-abi" and i + 1 < len(args):
            override = args[i + 1]
            i += 2
            continue
        if a.startswith("--ctc-abi="):
            override = a.split("=", 1)[1]
            i += 1
            continue
        out.append(a)
        i += 1
    return out, override


def _resolve_abi(requested: ABI, user_args: list[str], flag_override: str | None) -> str:
    env_override = os.environ.get("CTC_ABI")
    if env_override:
        return env_override
    if flag_override:
        return flag_override
    if requested != "auto":
        return requested

    host = _host_platform_key()
    if host == "windows":
        for a in user_args:
            if a.startswith("--target=") and "windows-msvc" in a:
                return "msvc"
        return "gnu"
    if host == "darwin":
        return "darwin"
    return "linux"


def _is_no_link_invocation(args: list[str]) -> bool:
    return any(a in ("-c", "-S", "-E") for a in args)


def _strip_unsupported_windows_linker_flags(args: list[str]) -> list[str]:
    """Remove `-Wl,` linker pass-throughs that ld.lld on Windows rejects.

    The legacy clang pipeline stripped these with a one-line warning. ld.lld
    accepts most GNU ld flags but rejects the handful below — passing them
    through causes a hard link failure.
    """
    if _host_platform_key() != "windows":
        return args
    unsupported = {
        "--allow-shlib-undefined",
        "--allow-multiple-definition",
        "--no-undefined",
    }
    stripped: list[str] = []
    out: list[str] = []
    for a in args:
        # `-Wl,flag[,flag...]` — filter individual sub-flags
        if a.startswith("-Wl,"):
            parts = a[4:].split(",")
            kept = [p for p in parts if p not in unsupported]
            dropped = [p for p in parts if p in unsupported]
            if dropped:
                stripped.extend(dropped)
            if not kept:
                continue
            if len(kept) == len(parts):
                out.append(a)
            else:
                out.append("-Wl," + ",".join(kept))
            continue
        # Bare `--no-undefined` etc. directly to clang — strip too
        if a in unsupported:
            stripped.append(a)
            continue
        out.append(a)
    if stripped and os.environ.get("CLANG_TOOL_CHAIN_NO_LINKER_COMPAT_NOTE") != "1":
        sys.stderr.write(
            "clang-tool-chain: removed GNU linker flags not supported by ld.lld "
            f"MinGW mode: {' '.join(stripped)}. Set "
            "CLANG_TOOL_CHAIN_NO_LINKER_COMPAT_NOTE=1 to silence. "
            "These flags were removed, not supported.\n"
        )
    return out


def _inject_shared_libasan_if_needed(args: list[str]) -> list[str]:
    """On Linux/Windows, add `-shared-libasan` when `-fsanitize=address` present.

    Matches the legacy ``ASANRuntimeTransformer``. macOS uses a different ASAN
    runtime model, so skip there. Emits an informational note on injection
    (suppressable via ``CLANG_TOOL_CHAIN_NO_SHARED_ASAN_NOTE``).
    """
    host = _host_platform_key()
    if host == "darwin":
        return args
    has_fsan_addr = any(
        a == "-fsanitize=address"
        or a.startswith("-fsanitize=address,")
        or a.startswith("-fsanitize=")
        and "address" in a
        for a in args
    )
    if not has_fsan_addr:
        return args
    if "-shared-libasan" in args:
        return args
    if os.environ.get("CLANG_TOOL_CHAIN_NO_SHARED_ASAN") == "1":
        return args

    out = list(args) + ["-shared-libasan"]
    if (
        os.environ.get("CLANG_TOOL_CHAIN_NO_SHARED_ASAN_NOTE") != "1"
        and os.environ.get("CLANG_TOOL_CHAIN_NO_SANITIZER_NOTE") != "1"
    ):
        sys.stderr.write(
            "clang-tool-chain: automatically injected -shared-libasan for "
            "shared ASAN runtime. Set CLANG_TOOL_CHAIN_NO_SHARED_ASAN_NOTE=1 "
            "to silence.\n"
        )
    return out


def _auto_install_or_regenerate_profile() -> bool:
    """Install the clang toolchain if missing, or regenerate profile.json
    for a pre-v1.4 install that pre-dates the profile-bake installer hook.

    Preserves the legacy first-use-auto-installs behavior of
    ``clang-tool-chain-c``. Heavyweight imports live here (not in the hot
    path) so they only fire on the rare fallback.

    Returns ``True`` on success, ``False`` on failure.
    """
    try:
        from clang_tool_chain.path_utils import get_install_dir
        from clang_tool_chain.platform.detection import get_platform_info
    except Exception as exc:  # noqa: BLE001
        sys.stderr.write(f"error: unable to resolve install paths: {exc}\n")
        return False

    try:
        platform_name, arch = get_platform_info()
    except Exception as exc:  # noqa: BLE001
        sys.stderr.write(f"error: unable to detect platform: {exc}\n")
        return False

    install_dir = get_install_dir(platform_name, arch)
    done_path = install_dir / "done.txt"

    if done_path.exists():
        # Toolchain present; just bake profile.json (matches the installer hook
        # that runs at the end of a fresh install).
        try:
            from clang_tool_chain.profile import generate_profile, write_profile

            profile = generate_profile(install_dir, platform_name, arch)
            write_profile(profile, install_dir)
            return True
        except Exception as exc:  # noqa: BLE001
            sys.stderr.write(f"error: failed to generate profile.json: {exc}\n")
            return False

    # Toolchain absent — full install. The installer hook will write profile.json.
    try:
        from clang_tool_chain import installer  # heavy import

        installer.ensure_toolchain(platform_name, arch)
    except Exception as exc:  # noqa: BLE001
        sys.stderr.write(f"error: toolchain install failed: {exc}\n")
        return False
    return True


def _consume_deploy_dependencies_flag(args: list[str]) -> tuple[list[str], bool]:
    """Strip ``--deploy-dependencies`` from argv and return (clean_args, present)."""
    present = False
    out: list[str] = []
    for a in args:
        if a == "--deploy-dependencies":
            present = True
            continue
        out.append(a)
    return out, present


def _extract_output_path(args: list[str]) -> Path | None:
    """Return the ``-o <path>`` value (or ``-o<path>``) if present and non-object."""
    output: str | None = None
    i = 0
    while i < len(args):
        a = args[i]
        if a == "-o" and i + 1 < len(args):
            output = args[i + 1]
            i += 2
            continue
        if a.startswith("-o") and len(a) > 2:
            output = a[2:]
        i += 1
    if output is None:
        return None
    suffix = _suffix_lower(output)
    if suffix in {".o", ".obj", ".a", ".lib"}:
        return None
    return Path(output).resolve()


def _run_libdeploy(output_path: Path, env: dict[str, str]) -> None:
    """Invoke ``clang-tool-chain-libdeploy <output_path>`` as a subprocess.

    Errors are non-fatal — the compile already succeeded; deploy failures
    should only warn.
    """
    import subprocess

    cmd = ["clang-tool-chain-libdeploy", str(output_path)]
    try:
        subprocess.run(cmd, env=env, check=False)
    except (FileNotFoundError, OSError) as e:
        sys.stderr.write(f"warning: libdeploy post-link hook failed: {e}\n")


def _resolve_tool_path(profile: Profile, tool: str) -> str:
    path = profile.binaries.get(tool)
    if not path:
        sys.stderr.write(
            f"error: tool '{tool}' is not listed in profile.binaries. "
            "The current toolchain install may not provide it — try "
            "`clang-tool-chain install clang` (or the tool-specific installer).\n"
        )
        sys.exit(1)
    # zccache requires an absolute path (it normalizes MSYS paths but will
    # not search PATH). Profile emits absolute paths already; resolve defensively.
    return str(Path(path).resolve())
