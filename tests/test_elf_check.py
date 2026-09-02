"""Tests for :mod:`clang_tool_chain.elf_check`.

All ELF inputs are hand-built synthetic byte blobs (no real compiler
invocation needed) so this suite runs identically on Linux, macOS, and
Windows CI runners.
"""

from __future__ import annotations

import struct
from typing import TYPE_CHECKING

from clang_tool_chain import elf_check

if TYPE_CHECKING:
    from pathlib import Path

    import pytest

EM_X86_64 = 0x3E
EM_AARCH64 = 0xB7

PT_LOAD = 1
PT_DYNAMIC = 2
PT_INTERP = 3

DT_NEEDED = 1
DT_STRTAB = 5
DT_STRSZ = 10
DT_RPATH = 15
DT_RUNPATH = 29
DT_NULL = 0

_EHDR_SIZE = 64
_PHDR_SIZE = 56


def build_elf(
    *,
    interp: str | None = None,
    needed: list[str] | None = None,
    rpath: str | None = None,
    runpath: str | None = None,
    machine: int = EM_X86_64,
    ei_class: int = 2,
    ei_data: int = 1,
) -> bytes:
    """Build a minimal, identity-mapped (vaddr == file offset) 64-bit ELF.

    A single PT_LOAD segment covers the whole file, so DT_STRTAB's "virtual
    address" can just be its file offset -- no real loading/relocation logic
    needed to make read_elf_info's vaddr_to_offset resolve it.
    """
    needed = needed or []

    n_phdrs = 1  # PT_LOAD always present
    if interp is not None:
        n_phdrs += 1
    has_dynamic = bool(needed) or rpath is not None or runpath is not None
    if has_dynamic:
        n_phdrs += 1

    offset = _EHDR_SIZE + n_phdrs * _PHDR_SIZE

    interp_offset = 0
    interp_bytes = b""
    if interp is not None:
        interp_bytes = interp.encode() + b"\x00"
        interp_offset = offset
        offset += len(interp_bytes)

    dyn_offset = 0
    dyn_bytes = b""
    strtab = bytearray(b"\x00")
    if has_dynamic:

        def add_str(s: str) -> int:
            off = len(strtab)
            strtab.extend(s.encode() + b"\x00")
            return off

        needed_offs = [add_str(s) for s in needed]
        rpath_off = add_str(rpath) if rpath is not None else None
        runpath_off = add_str(runpath) if runpath is not None else None

        entries: list[tuple[int, int]] = [(DT_NEEDED, o) for o in needed_offs]
        if rpath_off is not None:
            entries.append((DT_RPATH, rpath_off))
        if runpath_off is not None:
            entries.append((DT_RUNPATH, runpath_off))
        entries.append((DT_STRTAB, 0))  # patched below once strtab_offset is known
        entries.append((DT_STRSZ, len(strtab)))
        entries.append((DT_NULL, 0))

        dyn_offset = offset
        dyn_array_len = len(entries) * 16
        strtab_offset = dyn_offset + dyn_array_len

        final_entries = []
        for tag, val in entries:
            final_entries.append((tag, strtab_offset if tag == DT_STRTAB else val))
        dyn_bytes = b"".join(struct.pack("<QQ", t, v) for t, v in final_entries)

        offset = strtab_offset + len(strtab)
    else:
        strtab_offset = offset

    total_size = offset

    phdrs = bytearray()
    phdrs += struct.pack("<IIQQQQQQ", PT_LOAD, 5, 0, 0, 0, total_size, total_size, 0x1000)
    if interp is not None:
        phdrs += struct.pack(
            "<IIQQQQQQ",
            PT_INTERP,
            4,
            interp_offset,
            interp_offset,
            interp_offset,
            len(interp_bytes),
            len(interp_bytes),
            1,
        )
    if has_dynamic:
        dyn_total_len = (strtab_offset - dyn_offset) + len(strtab)
        phdrs += struct.pack(
            "<IIQQQQQQ", PT_DYNAMIC, 6, dyn_offset, dyn_offset, dyn_offset, dyn_total_len, dyn_total_len, 8
        )

    ehdr = bytearray(_EHDR_SIZE)
    ehdr[0:4] = b"\x7fELF"
    ehdr[4] = ei_class
    ehdr[5] = ei_data
    ehdr[6] = 1  # EI_VERSION
    struct.pack_into("<HHI", ehdr, 16, 2, machine, 1)  # e_type=ET_EXEC, e_machine, e_version
    struct.pack_into("<QQQ", ehdr, 24, 0, _EHDR_SIZE, 0)  # e_entry, e_phoff, e_shoff
    struct.pack_into("<IHHHHHH", ehdr, 48, 0, _EHDR_SIZE, _PHDR_SIZE, n_phdrs, 0, 0, 0)

    content = bytearray(total_size)
    content[0:_EHDR_SIZE] = ehdr
    content[_EHDR_SIZE : _EHDR_SIZE + len(phdrs)] = phdrs
    if interp is not None:
        content[interp_offset : interp_offset + len(interp_bytes)] = interp_bytes
    if has_dynamic:
        content[dyn_offset : dyn_offset + len(dyn_bytes)] = dyn_bytes
        content[strtab_offset : strtab_offset + len(strtab)] = strtab

    return bytes(content)


class TestReadElfInfo:
    def test_non_elf_file_returns_none(self, tmp_path: Path) -> None:
        p = tmp_path / "not_elf.bin"
        p.write_bytes(b"this is definitely not an ELF file, just plain text padding" * 4)
        assert elf_check.read_elf_info(p) is None

    def test_missing_file_returns_none(self, tmp_path: Path) -> None:
        assert elf_check.read_elf_info(tmp_path / "does_not_exist") is None

    def test_32bit_header_returns_none(self, tmp_path: Path) -> None:
        p = tmp_path / "elf32"
        p.write_bytes(build_elf(needed=["libc.so.6"], ei_class=1, ei_data=1))
        assert elf_check.read_elf_info(p) is None

    def test_big_endian_header_returns_none(self, tmp_path: Path) -> None:
        p = tmp_path / "elf_be"
        p.write_bytes(build_elf(needed=["libc.so.6"], ei_class=2, ei_data=2))
        assert elf_check.read_elf_info(p) is None

    def test_parses_interp_needed_and_runpath(self, tmp_path: Path) -> None:
        p = tmp_path / "prog"
        p.write_bytes(
            build_elf(
                interp="/lib64/ld-linux-x86-64.so.2",
                needed=["libc.so.6", "libm.so.6"],
                runpath="/opt/lib:/opt/lib2",
            )
        )
        info = elf_check.read_elf_info(p)
        assert info is not None
        assert info.interp == "/lib64/ld-linux-x86-64.so.2"
        assert info.needed == ["libc.so.6", "libm.so.6"]
        assert info.runpath == ["/opt/lib", "/opt/lib2"]
        assert info.rpath == []
        assert info.machine == "x86_64"

    def test_parses_aarch64_machine(self, tmp_path: Path) -> None:
        p = tmp_path / "prog_arm"
        p.write_bytes(build_elf(interp="/lib/ld-linux-aarch64.so.1", needed=["libc.so.6"], machine=EM_AARCH64))
        info = elf_check.read_elf_info(p)
        assert info is not None
        assert info.machine == "aarch64"

    def test_no_dynamic_section_is_static(self, tmp_path: Path) -> None:
        p = tmp_path / "static_prog"
        p.write_bytes(build_elf())
        info = elf_check.read_elf_info(p)
        assert info is not None
        assert info.interp == ""
        assert info.needed == []


class TestDiagnoseBinary:
    def test_pinned_nondefault_interp_with_unresolvable_sonames_warns(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        p = tmp_path / "nix_prog"
        p.write_bytes(
            build_elf(
                interp="/nix/store/abcdef1234567890/glibc-2.38/lib/ld-linux-x86-64.so.2",
                needed=["libstdc++.so.6", "libclang_rt.asan.so"],
            )
        )
        monkeypatch.setattr(elf_check, "_ldconfig_sonames", lambda: frozenset())
        monkeypatch.setattr(elf_check, "_DEFAULT_TRUSTED_DIRS", ())
        monkeypatch.delenv("LD_LIBRARY_PATH", raising=False)
        monkeypatch.delenv("NIX_LD_LIBRARY_PATH", raising=False)
        monkeypatch.setattr(elf_check, "_NIX_LD_FALLBACK_DIR", str(tmp_path / "no-such-nix-ld-dir"))

        lines = elf_check.diagnose_binary(p)
        assert lines, "expected warning lines for unresolvable sonames on a pinned interp"

        joined = "\n".join(lines)
        assert "clang-tool-chain: warning:" in lines[0]
        assert "pins interpreter /nix/store/abcdef1234567890/glibc-2.38/lib/ld-linux-x86-64.so.2" in lines[0]
        assert "not the system default /lib64/ld-linux-x86-64.so.2" in joined
        assert "nix-ld shim will not run" in joined
        assert "NIX_LD_LIBRARY_PATH will be ignored" in joined
        assert "libstdc++.so.6" in joined
        assert "libclang_rt.asan.so" in joined
        assert "-Wl,-dynamic-linker" in joined

    def test_default_interp_with_resolvable_sonames_is_clean(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        libdir = tmp_path / "libs"
        libdir.mkdir()
        (libdir / "libfoo.so.1").write_bytes(b"\x00")

        p = tmp_path / "prog"
        p.write_bytes(
            build_elf(
                interp="/lib64/ld-linux-x86-64.so.2",
                needed=["libfoo.so.1"],
                runpath=str(libdir),
            )
        )
        monkeypatch.setattr(elf_check, "_ldconfig_sonames", lambda: frozenset())
        monkeypatch.setattr(elf_check, "_DEFAULT_TRUSTED_DIRS", ())
        monkeypatch.delenv("LD_LIBRARY_PATH", raising=False)
        monkeypatch.delenv("NIX_LD_LIBRARY_PATH", raising=False)
        monkeypatch.setattr(elf_check, "_NIX_LD_FALLBACK_DIR", str(tmp_path / "no-such-nix-ld-dir"))

        assert elf_check.diagnose_binary(p) == []

    def test_static_binary_is_clean(self, tmp_path: Path) -> None:
        p = tmp_path / "static_prog"
        p.write_bytes(build_elf())
        assert elf_check.diagnose_binary(p) == []

    def test_non_elf_is_clean(self, tmp_path: Path) -> None:
        p = tmp_path / "script.sh"
        p.write_text("#!/bin/sh\necho hi\n")
        assert elf_check.diagnose_binary(p) == []

    def test_default_interp_with_unresolvable_sonames_uses_generic_message(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        p = tmp_path / "prog"
        p.write_bytes(
            build_elf(
                interp="/lib64/ld-linux-x86-64.so.2",
                needed=["libtotally_missing_thing.so.1"],
            )
        )
        monkeypatch.setattr(elf_check, "_ldconfig_sonames", lambda: frozenset())
        monkeypatch.setattr(elf_check, "_DEFAULT_TRUSTED_DIRS", ())
        monkeypatch.delenv("LD_LIBRARY_PATH", raising=False)
        monkeypatch.delenv("NIX_LD_LIBRARY_PATH", raising=False)
        monkeypatch.setattr(elf_check, "_NIX_LD_FALLBACK_DIR", str(tmp_path / "no-such-nix-ld-dir"))

        lines = elf_check.diagnose_binary(p)
        assert lines
        joined = "\n".join(lines)
        assert "pins interpreter" not in joined
        assert "libtotally_missing_thing.so.1" in joined


class TestUnresolvableSonames:
    def test_ld_library_path_resolves(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        libdir = tmp_path / "libs"
        libdir.mkdir()
        (libdir / "libbar.so.2").write_bytes(b"\x00")

        p = tmp_path / "prog"
        p.write_bytes(build_elf(needed=["libbar.so.2"]))

        monkeypatch.setattr(elf_check, "_ldconfig_sonames", lambda: frozenset())
        monkeypatch.setattr(elf_check, "_DEFAULT_TRUSTED_DIRS", ())
        monkeypatch.setattr(elf_check, "_NIX_LD_FALLBACK_DIR", str(tmp_path / "no-such-nix-ld-dir"))
        monkeypatch.setenv("LD_LIBRARY_PATH", str(libdir))
        monkeypatch.delenv("NIX_LD_LIBRARY_PATH", raising=False)

        assert elf_check.unresolvable_sonames(p) == []

    def test_nix_ld_library_path_resolves_for_default_interp(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A default/absent interpreter means nix-ld would actually run, so its
        NIX_LD_LIBRARY_PATH should be consulted too."""
        nix_ld_dir = tmp_path / "nix-ld-libs"
        nix_ld_dir.mkdir()
        (nix_ld_dir / "libquux.so.4").write_bytes(b"\x00")

        p = tmp_path / "prog"
        p.write_bytes(build_elf(interp="/lib64/ld-linux-x86-64.so.2", needed=["libquux.so.4"]))

        monkeypatch.setattr(elf_check, "_ldconfig_sonames", lambda: frozenset())
        monkeypatch.setattr(elf_check, "_DEFAULT_TRUSTED_DIRS", ())
        monkeypatch.setattr(elf_check, "_NIX_LD_FALLBACK_DIR", str(tmp_path / "no-such-nix-ld-dir"))
        monkeypatch.delenv("LD_LIBRARY_PATH", raising=False)
        monkeypatch.setenv("NIX_LD_LIBRARY_PATH", str(nix_ld_dir))

        assert elf_check.unresolvable_sonames(p) == []

    def test_nix_ld_library_path_ignored_for_pinned_nondefault_interp(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A pinned non-default interpreter means nix-ld never runs, so
        NIX_LD_LIBRARY_PATH must NOT rescue the soname."""
        nix_ld_dir = tmp_path / "nix-ld-libs"
        nix_ld_dir.mkdir()
        (nix_ld_dir / "libquux.so.4").write_bytes(b"\x00")

        p = tmp_path / "prog"
        p.write_bytes(build_elf(interp="/nix/store/xyz/glibc/lib/ld-linux-x86-64.so.2", needed=["libquux.so.4"]))

        monkeypatch.setattr(elf_check, "_ldconfig_sonames", lambda: frozenset())
        monkeypatch.setattr(elf_check, "_DEFAULT_TRUSTED_DIRS", ())
        monkeypatch.setattr(elf_check, "_NIX_LD_FALLBACK_DIR", str(tmp_path / "no-such-nix-ld-dir"))
        monkeypatch.delenv("LD_LIBRARY_PATH", raising=False)
        monkeypatch.setenv("NIX_LD_LIBRARY_PATH", str(nix_ld_dir))

        assert elf_check.unresolvable_sonames(p) == ["libquux.so.4"]

    def test_ldconfig_cache_resolves(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        p = tmp_path / "prog"
        p.write_bytes(build_elf(needed=["libbaz.so.3"]))

        monkeypatch.setattr(elf_check, "_ldconfig_sonames", lambda: frozenset({"libbaz.so.3"}))
        monkeypatch.setattr(elf_check, "_DEFAULT_TRUSTED_DIRS", ())
        monkeypatch.delenv("LD_LIBRARY_PATH", raising=False)
        monkeypatch.delenv("NIX_LD_LIBRARY_PATH", raising=False)
        monkeypatch.setattr(elf_check, "_NIX_LD_FALLBACK_DIR", str(tmp_path / "no-such-nix-ld-dir"))

        assert elf_check.unresolvable_sonames(p) == []

    def test_origin_expansion(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        (tmp_path / "libqux.so.1").write_bytes(b"\x00")

        p = tmp_path / "prog"
        p.write_bytes(build_elf(needed=["libqux.so.1"], runpath="$ORIGIN"))

        monkeypatch.setattr(elf_check, "_ldconfig_sonames", lambda: frozenset())
        monkeypatch.setattr(elf_check, "_DEFAULT_TRUSTED_DIRS", ())
        monkeypatch.delenv("LD_LIBRARY_PATH", raising=False)
        monkeypatch.delenv("NIX_LD_LIBRARY_PATH", raising=False)
        monkeypatch.setattr(elf_check, "_NIX_LD_FALLBACK_DIR", str(tmp_path / "no-such-nix-ld-dir"))

        assert elf_check.unresolvable_sonames(p) == []


class TestTransitiveDependencies:
    """The direct-NEEDED-only check misses failures like GitHub issue #55's
    NixOS trap: a soname that resolves as a *direct* dependency of the root
    can still fail at runtime if one of *its* dependencies does not resolve.
    These two tests are the same shape (root -> libdep.so -> libmissing.so.1,
    with libmissing.so.1 physically sitting in the root's own search
    directory the whole time) and differ only in whether the root points at
    that directory via DT_RUNPATH or DT_RPATH -- isolating the exact
    semantic distinction: DT_RUNPATH is never inherited by a dependency's own
    lookups, DT_RPATH is.
    """

    def test_runpath_is_not_inherited_by_dependency_own_lookup(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        libdir = tmp_path / "libs"
        libdir.mkdir()
        (libdir / "libdep.so").write_bytes(build_elf(needed=["libmissing.so.1"]))
        # Physically present in the root's RUNPATH dir -- but must still be
        # reported missing, because libdep.so's own NEEDED lookup does not
        # inherit the root's DT_RUNPATH.
        (libdir / "libmissing.so.1").write_bytes(b"\x00")

        root = tmp_path / "root"
        root.write_bytes(build_elf(needed=["libdep.so"], runpath=str(libdir)))

        monkeypatch.setattr(elf_check, "_ldconfig_sonames", lambda: frozenset())
        monkeypatch.setattr(elf_check, "_DEFAULT_TRUSTED_DIRS", ())
        monkeypatch.setattr(elf_check, "_NIX_LD_FALLBACK_DIR", str(tmp_path / "no-such-nix-ld-dir"))
        monkeypatch.delenv("LD_LIBRARY_PATH", raising=False)
        monkeypatch.delenv("NIX_LD_LIBRARY_PATH", raising=False)

        assert elf_check.unresolvable_sonames(root) == ["libmissing.so.1"]

    def test_rpath_is_inherited_by_dependency_own_lookup(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        libdir = tmp_path / "libs"
        libdir.mkdir()
        (libdir / "libdep.so").write_bytes(build_elf(needed=["libmissing.so.1"]))
        (libdir / "libmissing.so.1").write_bytes(b"\x00")

        root = tmp_path / "root"
        # Only difference from the test above: DT_RPATH instead of DT_RUNPATH.
        root.write_bytes(build_elf(needed=["libdep.so"], rpath=str(libdir)))

        monkeypatch.setattr(elf_check, "_ldconfig_sonames", lambda: frozenset())
        monkeypatch.setattr(elf_check, "_DEFAULT_TRUSTED_DIRS", ())
        monkeypatch.setattr(elf_check, "_NIX_LD_FALLBACK_DIR", str(tmp_path / "no-such-nix-ld-dir"))
        monkeypatch.delenv("LD_LIBRARY_PATH", raising=False)
        monkeypatch.delenv("NIX_LD_LIBRARY_PATH", raising=False)

        assert elf_check.unresolvable_sonames(root) == []

    def test_diagnose_binary_reports_transitive_soname(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """diagnose_binary()'s pinned-interpreter message must name a
        transitively-unresolvable soname, not just direct NEEDED entries."""
        libdir = tmp_path / "libs"
        libdir.mkdir()
        (libdir / "libdep.so").write_bytes(build_elf(needed=["libmissing.so.1"]))
        (libdir / "libmissing.so.1").write_bytes(b"\x00")

        root = tmp_path / "root"
        root.write_bytes(
            build_elf(
                interp="/nix/store/abcdef1234567890/glibc-2.38/lib/ld-linux-x86-64.so.2",
                needed=["libdep.so"],
                runpath=str(libdir),
            )
        )

        monkeypatch.setattr(elf_check, "_ldconfig_sonames", lambda: frozenset())
        monkeypatch.setattr(elf_check, "_DEFAULT_TRUSTED_DIRS", ())
        monkeypatch.setattr(elf_check, "_NIX_LD_FALLBACK_DIR", str(tmp_path / "no-such-nix-ld-dir"))
        monkeypatch.delenv("LD_LIBRARY_PATH", raising=False)
        monkeypatch.delenv("NIX_LD_LIBRARY_PATH", raising=False)

        lines = elf_check.diagnose_binary(root)
        joined = "\n".join(lines)
        assert "pins interpreter" in joined
        assert "libmissing.so.1" in joined
        # libdep.so itself resolved fine (via the root's RUNPATH) -- only its
        # own unresolvable NEEDED should be named as missing.
        assert "libdep.so" not in joined

    def test_soname_resolved_as_direct_dependency_is_not_re_flagged_missing(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Regression test: a soname the root resolves directly (via its own
        RUNPATH) must not be wrongly re-flagged missing just because a
        transitively-loaded dependency with no RPATH/RUNPATH of its own also
        lists it as NEEDED -- the real dynamic loader reuses whatever is
        already loaded in the process rather than re-searching per object."""
        libdir = tmp_path / "libs"
        libdir.mkdir()
        (libdir / "libshared.so.1").write_bytes(b"\x00")
        # libdep.so has no RPATH/RUNPATH of its own, and also needs
        # libshared.so.1 -- which is NOT reachable from libdep.so's own
        # (empty) search path, only via the root's RUNPATH.
        (libdir / "libdep.so").write_bytes(build_elf(needed=["libshared.so.1"]))

        root = tmp_path / "root"
        root.write_bytes(build_elf(needed=["libshared.so.1", "libdep.so"], runpath=str(libdir)))

        monkeypatch.setattr(elf_check, "_ldconfig_sonames", lambda: frozenset())
        monkeypatch.setattr(elf_check, "_DEFAULT_TRUSTED_DIRS", ())
        monkeypatch.setattr(elf_check, "_NIX_LD_FALLBACK_DIR", str(tmp_path / "no-such-nix-ld-dir"))
        monkeypatch.delenv("LD_LIBRARY_PATH", raising=False)
        monkeypatch.delenv("NIX_LD_LIBRARY_PATH", raising=False)

        assert elf_check.unresolvable_sonames(root) == []
