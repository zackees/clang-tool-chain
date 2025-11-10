#!/usr/bin/env python3
"""
Test archive creation to ensure binaries have correct executable permissions.

This test verifies that the tar archives created by fetch_and_archive.py
properly set executable permissions on all binaries in the bin/ directory.
"""

import tarfile
from pathlib import Path

import pytest  # type: ignore[import-not-found]

from clang_tool_chain.downloads.fetch_and_archive import (
    create_tar_archive,
    verify_tar_permissions,
)


class TestArchivePermissions:
    """Test that tar archives have correct executable permissions."""

    def test_create_tar_with_executable_permissions(self, tmp_path: Path) -> None:
        """Test that create_tar_archive sets executable permissions on binaries."""
        # Create a test directory structure
        test_dir = tmp_path / "test_binaries"
        bin_dir = test_dir / "bin"
        bin_dir.mkdir(parents=True)

        # Create some test files (with various extensions to simulate real binaries)
        test_files = ["clang", "clang++", "lld", "llvm-ar.exe", "test-binary"]

        for filename in test_files:
            file_path = bin_dir / filename
            file_path.write_text("#!/bin/sh\necho 'test binary'\n")
            # On Windows, files might not have execute permissions, but tar should set them

        # Also create a non-binary file to ensure it doesn't get executable perms
        lib_dir = test_dir / "lib"
        lib_dir.mkdir(parents=True)
        (lib_dir / "readme.txt").write_text("This is a readme")

        # Create tar archive
        tar_path = tmp_path / "test.tar"
        create_tar_archive(test_dir, tar_path)

        # Verify the archive was created
        assert tar_path.exists()

        # Check permissions in the tar archive
        with tarfile.open(tar_path, "r") as tar:
            for member in tar.getmembers():
                if "/bin/" in member.name and member.isfile():
                    # All files in bin/ should be executable (0o755)
                    assert member.mode & 0o100, f"Binary {member.name} is not executable (mode: {oct(member.mode)})"
                    assert (
                        member.mode == 0o755
                    ), f"Binary {member.name} has wrong mode: {oct(member.mode)} (expected 0o755)"
                elif "/lib/" in member.name and member.isfile():
                    # Files in lib/ should not be forcibly made executable
                    # (they keep their original permissions)
                    pass  # We don't check lib files

    def test_verify_tar_permissions_passes_for_good_archive(self, tmp_path: Path) -> None:
        """Test that verify_tar_permissions passes for an archive with correct permissions."""
        # Create a test directory structure
        test_dir = tmp_path / "test_binaries"
        bin_dir = test_dir / "bin"
        bin_dir.mkdir(parents=True)

        # Create test binaries
        (bin_dir / "clang").write_text("test")
        (bin_dir / "lld").write_text("test")

        # Create tar archive (should set permissions correctly)
        tar_path = tmp_path / "test.tar"
        create_tar_archive(test_dir, tar_path)

        # Verify should pass without raising an exception
        binaries_checked = verify_tar_permissions(tar_path)
        assert binaries_checked == 2

    def test_verify_tar_permissions_fails_for_bad_archive(self, tmp_path: Path) -> None:
        """Test that verify_tar_permissions fails for an archive with incorrect permissions."""
        # Create a test directory structure
        test_dir = tmp_path / "test_binaries"
        bin_dir = test_dir / "bin"
        bin_dir.mkdir(parents=True)

        # Create test binaries
        (bin_dir / "clang").write_text("test")
        (bin_dir / "lld").write_text("test")

        # Create tar archive WITHOUT our filter (to simulate bad permissions)
        tar_path = tmp_path / "test.tar"
        with tarfile.open(tar_path, "w") as tar:
            # Add without filter - permissions will be taken from source files
            # On Windows, these won't have execute permissions
            tar.add(test_dir, arcname=test_dir.name)

        # Modify the archive to explicitly set wrong permissions
        # Re-create with non-executable permissions
        tar_path_bad = tmp_path / "test_bad.tar"
        with tarfile.open(tar_path, "r") as tar_in, tarfile.open(tar_path_bad, "w") as tar_out:
            for member in tar_in.getmembers():
                if "/bin/" in member.name and member.isfile():
                    # Set to non-executable (0o644)
                    member.mode = 0o644
                tar_out.addfile(member, tar_in.extractfile(member) if member.isfile() else None)

        # Verify should fail with RuntimeError
        with pytest.raises(RuntimeError, match="with incorrect permissions"):
            verify_tar_permissions(tar_path_bad)

    def test_tar_filter_sets_correct_permissions(self, tmp_path: Path) -> None:
        """Test that the tar_filter function correctly sets permissions."""
        # Create a test directory
        test_dir = tmp_path / "test_binaries"
        bin_dir = test_dir / "bin"
        bin_dir.mkdir(parents=True)

        # Create test file
        test_binary = bin_dir / "test-bin"
        test_binary.write_text("test")

        # Create tar with our implementation
        tar_path = tmp_path / "test.tar"
        create_tar_archive(test_dir, tar_path)

        # Verify permissions were set correctly
        with tarfile.open(tar_path, "r") as tar:
            members = [m for m in tar.getmembers() if m.name.endswith("test-bin")]
            assert len(members) == 1
            member = members[0]
            assert member.mode == 0o755, f"Expected 0o755, got {oct(member.mode)}"
            assert member.mode & 0o100, "Execute bit not set"

    def test_empty_bin_directory(self, tmp_path: Path) -> None:
        """Test verification with an empty bin directory."""
        # Create empty structure
        test_dir = tmp_path / "test_binaries"
        bin_dir = test_dir / "bin"
        bin_dir.mkdir(parents=True)

        # Create tar archive
        tar_path = tmp_path / "test.tar"
        create_tar_archive(test_dir, tar_path)

        # Verify should pass with 0 binaries checked
        binaries_checked = verify_tar_permissions(tar_path)
        assert binaries_checked == 0

    def test_multiple_binaries_with_mixed_extensions(self, tmp_path: Path) -> None:
        """Test with multiple binaries, some with .exe extension."""
        # Create test directory
        test_dir = tmp_path / "test_binaries"
        bin_dir = test_dir / "bin"
        bin_dir.mkdir(parents=True)

        # Create binaries with different naming patterns
        binaries = [
            "clang",  # No extension (Unix)
            "clang++",  # Special chars
            "lld.exe",  # Windows extension
            "llvm-ar",  # Hyphenated
            "tool_name",  # Underscore
        ]

        for binary in binaries:
            (bin_dir / binary).write_text("test")

        # Create tar archive
        tar_path = tmp_path / "test.tar"
        create_tar_archive(test_dir, tar_path)

        # Verify all binaries have correct permissions
        binaries_checked = verify_tar_permissions(tar_path)
        assert binaries_checked == len(binaries)

        # Double-check each binary
        with tarfile.open(tar_path, "r") as tar:
            for member in tar.getmembers():
                if "/bin/" in member.name and member.isfile():
                    assert member.mode == 0o755, f"{member.name} has mode {oct(member.mode)}, expected 0o755"

    def test_shared_libraries_get_executable_permissions(self, tmp_path: Path) -> None:
        """Test that shared libraries in lib/ get executable permissions."""
        # Create test directory
        test_dir = tmp_path / "test_binaries"
        lib_dir = test_dir / "lib" / "clang" / "21.1.5"
        lib_dir.mkdir(parents=True)

        # Create shared libraries with various naming patterns
        shared_libs = [
            "libclang_rt.asan.so",  # .so extension
            "libclang_rt.asan-x86_64.so.21.1",  # .so.version pattern
            "libfoo.dylib",  # macOS dylib
        ]

        for lib in shared_libs:
            (lib_dir / lib).write_text("shared library")

        # Create tar archive
        tar_path = tmp_path / "test.tar"
        create_tar_archive(test_dir, tar_path)

        # Verify shared libraries have executable permissions
        with tarfile.open(tar_path, "r") as tar:
            for member in tar.getmembers():
                if member.name.endswith((".so", ".dylib")) or ".so." in member.name:
                    assert member.mode == 0o755, f"Shared lib {member.name} has mode {oct(member.mode)}, expected 0o755"

    def test_headers_do_not_get_executable_permissions(self, tmp_path: Path) -> None:
        """Test that headers and static libraries in lib/ do NOT get executable permissions."""
        # Create test directory
        test_dir = tmp_path / "test_binaries"
        lib_dir = test_dir / "lib" / "clang" / "21.1.5" / "include"
        lib_dir.mkdir(parents=True)

        # Create various non-executable files
        non_executable_files = [
            "stddef.h",  # Header
            "module.modulemap",  # Module map
            "limits.inc",  # Include file
            "foo.tcc",  # Template implementation
            "README.txt",  # Text file
            "libfoo.a",  # Static library
        ]

        for file in non_executable_files:
            (lib_dir / file).write_text("header content")

        # Create tar archive
        tar_path = tmp_path / "test.tar"
        create_tar_archive(test_dir, tar_path)

        # Verify these files have 0o644 permissions (readable but not executable)
        with tarfile.open(tar_path, "r") as tar:
            for member in tar.getmembers():
                if member.name.endswith((".h", ".inc", ".modulemap", ".tcc", ".txt", ".a")):
                    assert (
                        member.mode == 0o644
                    ), f"Header/text file {member.name} has mode {oct(member.mode)}, expected 0o644"

    def test_lib_binaries_get_executable_permissions(self, tmp_path: Path) -> None:
        """Test that executable binaries in lib/ (like symbolizers) get executable permissions."""
        # Create test directory
        test_dir = tmp_path / "test_binaries"
        lib_dir = test_dir / "lib" / "clang" / "21.1.5" / "bin"
        lib_dir.mkdir(parents=True)

        # Create executable binaries in lib/
        lib_binaries = [
            "hwasan_symbolize",
            "asan_symbolize",
        ]

        for binary in lib_binaries:
            (lib_dir / binary).write_text("#!/bin/sh\necho test")

        # Create tar archive
        tar_path = tmp_path / "test.tar"
        create_tar_archive(test_dir, tar_path)

        # Verify these binaries have executable permissions
        with tarfile.open(tar_path, "r") as tar:
            for member in tar.getmembers():
                if "symbolize" in member.name and member.isfile():
                    assert member.mode == 0o755, f"Lib binary {member.name} has mode {oct(member.mode)}, expected 0o755"

    def test_mixed_bin_and_lib_structure(self, tmp_path: Path) -> None:
        """Test a realistic structure with both bin/ and lib/ directories."""
        # Create test directory structure
        test_dir = tmp_path / "test_binaries"
        bin_dir = test_dir / "bin"
        lib_dir = test_dir / "lib" / "clang" / "21.1.5"
        include_dir = lib_dir / "include"
        bin_dir.mkdir(parents=True)
        include_dir.mkdir(parents=True)

        # Create binaries
        (bin_dir / "clang").write_text("binary")
        (bin_dir / "lld").write_text("binary")

        # Create shared libraries
        (lib_dir / "libclang_rt.asan.so").write_text("shared lib")
        (lib_dir / "libfoo.dylib").write_text("shared lib")

        # Create headers
        (include_dir / "stddef.h").write_text("header")
        (include_dir / "limits.inc").write_text("include")

        # Create static library
        (lib_dir / "libclang.a").write_text("static lib")

        # Create tar archive
        tar_path = tmp_path / "test.tar"
        create_tar_archive(test_dir, tar_path)

        # Verify permissions
        files_checked = verify_tar_permissions(tar_path)
        assert files_checked >= 4  # At least 2 binaries + 2 shared libs

        # Double-check specific files
        with tarfile.open(tar_path, "r") as tar:
            for member in tar.getmembers():
                if not member.isfile():
                    continue

                if "/bin/" in member.name:
                    assert member.mode == 0o755, f"Binary {member.name} should be 0o755"
                elif member.name.endswith((".so", ".dylib")):
                    assert member.mode == 0o755, f"Shared lib {member.name} should be 0o755"
                elif member.name.endswith((".h", ".inc", ".a")):
                    assert member.mode == 0o644, f"Header/static lib {member.name} should be 0o644"
