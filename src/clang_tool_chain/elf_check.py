"""ELF runtime-resolvability diagnostics.

Pure-stdlib parser for the narrow slice of the ELF format needed to answer one
question: "will the dynamic loader find every ``DT_NEEDED`` soname this binary
declares, at process start?"

This deliberately does *not* shell out to ``readelf``/``objdump``/``ldd`` to do
the parsing -- the whole point (see GitHub issue #55) is to diagnose broken
systems where the toolchain installs cleanly, compiles cleanly, links cleanly,
and produces a binary that cannot start. ``ldconfig -p`` is still consulted
(best-effort, if present) to check the system library cache, but the ELF
itself is always parsed by hand with :mod:`struct`.

Only 64-bit little-endian ELF (x86_64, aarch64) is supported. Anything else --
32-bit ELF, big-endian ELF, or a file that isn't ELF at all -- makes
:func:`read_elf_info` return ``None`` rather than raising.
"""

from __future__ import annotations

import os
import shutil
import struct
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

# --- ELF constants (only what we need) ---------------------------------

_ELFCLASS64 = 2
_ELFDATA2LSB = 1

_PT_LOAD = 1
_PT_DYNAMIC = 2
_PT_INTERP = 3

_DT_NULL = 0
_DT_NEEDED = 1
_DT_STRTAB = 5
_DT_STRSZ = 10
_DT_RPATH = 15
_DT_RUNPATH = 29

_EM_X86_64 = 62
_EM_AARCH64 = 183

_EHDR_SIZE = 64
_PHDR_SIZE = 56
_DYN_ENTRY_SIZE = 16

_MACHINE_NAMES = {
    _EM_X86_64: "x86_64",
    _EM_AARCH64: "aarch64",
}

#: Platform-default dynamic linker path, keyed by the machine name we assign
#: in :data:`_MACHINE_NAMES`. A binary whose ``PT_INTERP`` points somewhere
#: else (e.g. ``/nix/store/.../ld-linux-x86-64.so.2``) will not have the
#: nix-ld shim (or the equivalent system integration) invoked for it.
DEFAULT_INTERP_BY_MACHINE: dict[str, str] = {
    "x86_64": "/lib64/ld-linux-x86-64.so.2",
    "aarch64": "/lib/ld-linux-aarch64.so.1",
}

#: Directories the dynamic loader searches by default (i.e. without any
#: rpath/runpath/LD_LIBRARY_PATH/ldconfig help). Not exhaustive, but covers
#: every mainstream glibc-based distro layout.
_DEFAULT_TRUSTED_DIRS: tuple[str, ...] = (
    "/lib",
    "/lib64",
    "/usr/lib",
    "/usr/lib64",
    "/usr/local/lib",
    "/lib/x86_64-linux-gnu",
    "/usr/lib/x86_64-linux-gnu",
    "/lib/aarch64-linux-gnu",
    "/usr/lib/aarch64-linux-gnu",
)

#: Fallback nix-ld shared library directory used by NixOS's `programs.nix-ld`
#: module when NIX_LD_LIBRARY_PATH is not set. Mirrors
#: clang_tool_chain.platform.nixos._NIX_LD_FALLBACK_DIR (kept private there,
#: so duplicated here rather than imported).
_NIX_LD_FALLBACK_DIR = "/run/current-system/sw/share/nix-ld/lib"


@dataclass
class ElfInfo:
    """The handful of ELF facts needed to diagnose runtime-resolvability."""

    interp: str  # "" for static binaries / no PT_INTERP
    needed: list[str] = field(default_factory=list)
    rpath: list[str] = field(default_factory=list)  # already ':'-split
    runpath: list[str] = field(default_factory=list)
    machine: str = ""  # "x86_64", "aarch64", or "" if unknown/unsupported


def _split_colon_path(raw: str) -> list[str]:
    return [entry for entry in raw.split(":") if entry]


def read_elf_info(path: Path) -> ElfInfo | None:
    """Parse ``PT_INTERP`` and the ``PT_DYNAMIC`` entries of an ELF file.

    Returns ``None`` if ``path`` cannot be read, is not ELF at all, or is not
    a 64-bit little-endian ELF file (32-bit and big-endian ELF included).
    Never raises for malformed/truncated input -- worst case is a partially
    populated :class:`ElfInfo` or ``None``.
    """
    try:
        with open(path, "rb") as f:
            data = f.read()
    except OSError:
        return None

    if len(data) < _EHDR_SIZE or data[:4] != b"\x7fELF":
        return None

    ei_class = data[4]
    ei_data = data[5]
    if ei_class != _ELFCLASS64 or ei_data != _ELFDATA2LSB:
        return None

    try:
        (e_machine,) = struct.unpack_from("<H", data, 18)
        e_phoff, _e_shoff = struct.unpack_from("<QQ", data, 32)
        e_phentsize, e_phnum = struct.unpack_from("<HH", data, 54)
    except struct.error:
        return None

    machine = _MACHINE_NAMES.get(e_machine, "")

    interp = ""
    loads: list[tuple[int, int, int]] = []  # (vaddr, filesz, offset)
    dynamic_offset: int | None = None
    dynamic_filesz = 0

    try:
        for i in range(e_phnum):
            off = e_phoff + i * e_phentsize
            if off + _PHDR_SIZE > len(data):
                break
            p_type, _p_flags = struct.unpack_from("<II", data, off)
            p_offset, p_vaddr, _p_paddr, p_filesz, _p_memsz, _p_align = struct.unpack_from("<QQQQQQ", data, off + 8)
            if p_type == _PT_LOAD:
                loads.append((p_vaddr, p_filesz, p_offset))
            elif p_type == _PT_INTERP:
                if p_offset + p_filesz <= len(data):
                    raw = data[p_offset : p_offset + p_filesz]
                    interp = raw.split(b"\x00", 1)[0].decode("utf-8", "replace")
            elif p_type == _PT_DYNAMIC:
                dynamic_offset = p_offset
                dynamic_filesz = p_filesz
    except (struct.error, IndexError):
        return None

    def vaddr_to_offset(vaddr: int) -> int | None:
        for seg_vaddr, seg_filesz, seg_offset in loads:
            if seg_vaddr <= vaddr < seg_vaddr + seg_filesz:
                return seg_offset + (vaddr - seg_vaddr)
        return None

    needed: list[str] = []
    rpath: list[str] = []
    runpath: list[str] = []

    if dynamic_offset is not None:
        strtab_vaddr: int | None = None
        strsz = 0
        rpath_stroff: int | None = None
        runpath_stroff: int | None = None
        needed_stroffs: list[int] = []

        try:
            n_entries = dynamic_filesz // _DYN_ENTRY_SIZE
            for i in range(n_entries):
                off = dynamic_offset + i * _DYN_ENTRY_SIZE
                if off + _DYN_ENTRY_SIZE > len(data):
                    break
                tag, val = struct.unpack_from("<QQ", data, off)
                if tag == _DT_NULL:
                    break
                if tag == _DT_NEEDED:
                    needed_stroffs.append(val)
                elif tag == _DT_STRTAB:
                    strtab_vaddr = val
                elif tag == _DT_STRSZ:
                    strsz = val
                elif tag == _DT_RPATH:
                    rpath_stroff = val
                elif tag == _DT_RUNPATH:
                    runpath_stroff = val
        except struct.error:
            pass

        if strtab_vaddr is not None:
            strtab_offset = vaddr_to_offset(strtab_vaddr)
            if strtab_offset is not None and strtab_offset < len(data):
                strtab = data[strtab_offset : strtab_offset + strsz] if strsz else data[strtab_offset:]

                def get_string(str_off: int, _strtab: bytes = strtab) -> str:
                    if str_off < 0 or str_off >= len(_strtab):
                        return ""
                    end = _strtab.find(b"\x00", str_off)
                    if end == -1:
                        end = len(_strtab)
                    return _strtab[str_off:end].decode("utf-8", "replace")

                needed = [get_string(o) for o in needed_stroffs]
                if rpath_stroff is not None:
                    rpath = _split_colon_path(get_string(rpath_stroff))
                if runpath_stroff is not None:
                    runpath = _split_colon_path(get_string(runpath_stroff))

    return ElfInfo(interp=interp, needed=needed, rpath=rpath, runpath=runpath, machine=machine)


def _expand_origin(entry: str, binary_dir: Path) -> str:
    """Expand ``$ORIGIN``/``${ORIGIN}`` tokens relative to the binary's directory."""
    origin = str(binary_dir)
    return entry.replace("${ORIGIN}", origin).replace("$ORIGIN", origin)


_ldconfig_paths_cache: dict[str, str] | None = None


def _ldconfig_soname_paths() -> dict[str, str]:
    """Return ``{soname: resolved_path}`` parsed from ``ldconfig -p`` (best-effort, cached).

    Empty when ``ldconfig`` is unavailable, has no cache (e.g. NixOS, which
    does not ship one), or exits non-zero. Kept separate from
    :func:`_ldconfig_sonames` so tests can monkeypatch either the "is this
    soname known" check or the "what real path does it resolve to" lookup
    (needed to recurse into it) independently.
    """
    global _ldconfig_paths_cache
    if _ldconfig_paths_cache is not None:
        return _ldconfig_paths_cache

    paths: dict[str, str] = {}
    ldconfig = shutil.which("ldconfig") or "/sbin/ldconfig"
    try:
        result = subprocess.run([ldconfig, "-p"], capture_output=True, text=True, timeout=5)
        if result.returncode == 0:
            for line in result.stdout.splitlines():
                line = line.strip()
                if " => " not in line:
                    continue
                name_part, _, resolved = line.partition(" => ")
                soname = name_part.split(" ", 1)[0].strip()
                resolved = resolved.strip()
                if soname and resolved:
                    paths.setdefault(soname, resolved)
    except (OSError, subprocess.SubprocessError):
        pass

    _ldconfig_paths_cache = paths
    return _ldconfig_paths_cache


def _ldconfig_sonames() -> frozenset[str]:
    """Return the sonames known to ``ldconfig -p`` (empty set if unavailable).

    Best-effort and cached for the process lifetime (via
    :func:`_ldconfig_soname_paths`). Exists as its own function so tests (and
    callers on systems with an unusual ldconfig) can monkeypatch it directly.
    """
    return frozenset(_ldconfig_soname_paths())


_MAX_TRANSITIVE_DEPTH = 32


def unresolvable_sonames(path: Path, info: ElfInfo | None = None) -> list[str]:
    """Return the sonames that will not resolve anywhere in the transitive
    dependency graph rooted at ``path``.

    This walks NEEDED -> resolved library -> its own NEEDED, and so on
    (cycle- and depth-guarded), because a soname that resolves as a *direct*
    dependency of the root binary can still fail at runtime if one of ITS
    dependencies does not resolve -- e.g. the root links
    ``libclang_rt.asan.so`` successfully via its own RUNPATH, but
    ``libclang_rt.asan.so`` itself needs ``libstdc++.so.6`` and has no RPATH/
    RUNPATH of its own, so that lookup falls through to LD_LIBRARY_PATH/
    ldconfig/trusted dirs -- none of which have it on NixOS. A direct-NEEDED-
    only check misses this entirely (GitHub issue #55).

    Per node in the graph, in order:
      1. that node's own DT_RPATH + DT_RUNPATH (``$ORIGIN`` expanded relative
         to *that node's* directory, not the root binary's),
      2. DT_RPATH (never DT_RUNPATH) accumulated from ancestors -- DT_RPATH is
         inherited transitively by the whole dependency graph, DT_RUNPATH
         applies only to the object that defines it and is never inherited,
      3. ``LD_LIBRARY_PATH``,
      4. ``ldconfig -p``,
      5. the default trusted directories,
      6. ``NIX_LD_LIBRARY_PATH`` (and its fallback directory) -- but only when
         the *root* binary's interpreter is the platform default (i.e. the
         nix-ld shim would actually run for it); that condition is keyed off
         the root because the interpreter is what selects the loader.

    Nodes that cannot be parsed as ELF are treated as resolved leaves (we
    still know the soname resolved to *a* file, we just can't see further).
    A visited-set of resolved real paths guards against cycles/repeats, and
    recursion stops past `_MAX_TRANSITIVE_DEPTH` (32) so a pathological graph
    cannot hang the CLI -- a soname that DID resolve to a real file is never
    reported missing merely because its own subtree wasn't explored.
    """
    if info is None:
        info = read_elf_info(path)
    if info is None or not info.needed:
        return []

    root_default_interp = DEFAULT_INTERP_BY_MACHINE.get(info.machine)
    interp_lets_nix_ld_run = not info.interp or info.interp == root_default_interp

    ld_library_path_dirs = _split_colon_path(os.environ.get("LD_LIBRARY_PATH", ""))

    nix_ld_dirs: list[str] = []
    if interp_lets_nix_ld_run:
        nix_ld_dirs = _split_colon_path(os.environ.get("NIX_LD_LIBRARY_PATH", ""))
        if not nix_ld_dirs and os.path.isdir(_NIX_LD_FALLBACK_DIR):
            nix_ld_dirs = [_NIX_LD_FALLBACK_DIR]

    known_sonames = _ldconfig_sonames()
    ldconfig_paths = _ldconfig_soname_paths()

    missing: list[str] = []
    missing_seen: set[str] = set()

    # Sonames already known to resolve *somewhere* in the graph, regardless of
    # which node needed them. This mirrors the real dynamic loader: it keeps
    # one flat per-process table of already-loaded objects (matched by
    # soname) and reuses that before ever consulting a requesting object's
    # own RPATH/RUNPATH. Without this, a soname resolved as a DIRECT
    # dependency of the root (e.g. libc.so.6, found via the root's own
    # RUNPATH) would be re-searched -- and wrongly flagged missing -- when a
    # transitively-loaded dependency with no RPATH/RUNPATH of its own (e.g.
    # libm.so.6) also lists it as NEEDED.
    resolved_by_name: dict[str, str] = {}

    root_path = Path(path)
    try:
        visited: set[str] = {str(root_path.resolve())}
    except OSError:
        visited = set()

    # Worklist entries: (elf_path, parsed_info, inherited_rpath_dirs, depth)
    worklist: list[tuple[Path, ElfInfo, list[str], int]] = [(root_path, info, [], 0)]

    while worklist:
        node_path, node_info, inherited_rpath, depth = worklist.pop(0)

        try:
            node_dir = node_path.resolve().parent
        except OSError:
            node_dir = node_path.parent

        own_dirs: list[str] = []
        if node_info.runpath:
            own_dirs.extend(_expand_origin(d, node_dir) for d in node_info.runpath)
        elif node_info.rpath:
            own_dirs.extend(_expand_origin(d, node_dir) for d in node_info.rpath)

        search_dirs = [*own_dirs, *inherited_rpath, *ld_library_path_dirs, *_DEFAULT_TRUSTED_DIRS, *nix_ld_dirs]

        # DT_RPATH (never DT_RUNPATH) of this node is inherited by whatever
        # it resolves, on top of whatever this node itself inherited.
        own_rpath_expanded = [_expand_origin(d, node_dir) for d in node_info.rpath]
        child_inherited_rpath = [*inherited_rpath, *own_rpath_expanded]

        for soname in node_info.needed:
            if soname in resolved_by_name:
                # Already loaded elsewhere in the process -- the real loader
                # would reuse it without consulting this node's search paths.
                continue

            if soname in known_sonames:
                # Resolved (known to the system's ldconfig cache). Recurse
                # into it only if we also know a concrete path -- otherwise
                # it's a resolved leaf as far as this check is concerned.
                resolved_path = ldconfig_paths.get(soname)
                resolved_by_name[soname] = resolved_path or ""
                if resolved_path and resolved_path not in visited and depth < _MAX_TRANSITIVE_DEPTH:
                    visited.add(resolved_path)
                    child_info = read_elf_info(Path(resolved_path))
                    if child_info is not None and child_info.needed:
                        worklist.append((Path(resolved_path), child_info, child_inherited_rpath, depth + 1))
                continue

            resolved_path = None
            for directory in search_dirs:
                try:
                    candidate = Path(directory) / soname
                    if candidate.is_file():
                        resolved_path = str(candidate.resolve())
                        break
                except OSError:
                    continue

            if resolved_path is None:
                if soname not in missing_seen:
                    missing_seen.add(soname)
                    missing.append(soname)
                continue

            # Resolved (possibly correcting an earlier, more restrictive
            # node's failure to find this exact soname -- see resolved_by_name
            # above).
            resolved_by_name[soname] = resolved_path
            if soname in missing_seen:
                missing_seen.discard(soname)
                missing.remove(soname)

            if resolved_path in visited:
                continue
            visited.add(resolved_path)

            if depth >= _MAX_TRANSITIVE_DEPTH:
                continue

            child_info = read_elf_info(Path(resolved_path))
            if child_info is None or not child_info.needed:
                continue

            worklist.append((Path(resolved_path), child_info, child_inherited_rpath, depth + 1))

    return missing


def diagnose_binary(path: Path) -> list[str]:
    """Human-readable warning lines about runtime-resolvability problems.

    Returns an empty list when the binary looks fine: not ELF, statically
    linked (no ``DT_NEEDED`` entries), or every soname resolves.

    When the interpreter is pinned to something other than the platform
    default (the NixOS trap from GitHub issue #55: a Nix-store interpreter
    path means the nix-ld shim never runs) *and* sonames are unresolvable,
    emits the issue's one-line diagnosis naming the interpreter and every
    missing soname. Otherwise, on a plain Linux system with simply
    unresolvable sonames, emits a shorter, generic version of the same
    warning.
    """
    info = read_elf_info(path)
    if info is None or not info.needed:
        return []

    missing = unresolvable_sonames(path, info)
    if not missing:
        return []

    default_interp = DEFAULT_INTERP_BY_MACHINE.get(info.machine)
    pinned_nondefault = bool(info.interp) and default_interp is not None and info.interp != default_interp

    lines: list[str] = []
    if pinned_nondefault:
        lines.append(f"clang-tool-chain: warning: {path} pins interpreter {info.interp}")
        lines.append(f"  (not the system default {default_interp}), so the nix-ld shim will not run")
        lines.append("  and NIX_LD_LIBRARY_PATH will be ignored.")
        lines.append("  These libraries are on neither its rpath/runpath nor any system search path and the")
        lines.append("  binary will fail to start:")
        for soname in missing:
            lines.append(f"    {soname}")
        lines.append("  Fix: rebuild without -Wl,-dynamic-linker, or add -Wl,-rpath,<dir> for each.")
    else:
        plural = "library" if len(missing) == 1 else "libraries"
        lines.append(f"clang-tool-chain: warning: {path} depends on {len(missing)} {plural} not resolvable at runtime:")
        for soname in missing:
            lines.append(f"    {soname}")
        lines.append("  Fix: add -Wl,-rpath,<dir> for each, or install the missing library system-wide.")
    return lines
