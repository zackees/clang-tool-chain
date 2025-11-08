#!/usr/bin/env python3
"""
Unit tests for scripts.strip_binaries module.

Tests the BinaryStripper class and related functions for stripping
and optimizing LLVM binaries.
"""

import sys
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

# Add scripts directory to path
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

import strip_binaries  # noqa: E402


class TestBinaryStripper(unittest.TestCase):
    """Test the BinaryStripper class."""

    def setUp(self):
        """Set up test fixtures."""
        self.source_dir = Path("source")
        self.output_dir = Path("output")
        self.platform = "linux-x86_64"
        self.stripper = strip_binaries.BinaryStripper(
            source_dir=self.source_dir,
            output_dir=self.output_dir,
            platform=self.platform,
            keep_headers=False,
            strip_binaries=True,
            verbose=False,
        )

    def test_init(self):
        """Test BinaryStripper initialization."""
        self.assertEqual(self.stripper.source_dir, self.source_dir)
        self.assertEqual(self.stripper.output_dir, self.output_dir)
        self.assertEqual(self.stripper.platform, self.platform)
        self.assertFalse(self.stripper.keep_headers)
        self.assertTrue(self.stripper.strip_binaries)
        self.assertFalse(self.stripper.verbose)
        self.assertEqual(self.stripper.original_size, 0)
        self.assertEqual(self.stripper.final_size, 0)
        self.assertEqual(self.stripper.files_removed, 0)
        self.assertEqual(self.stripper.files_kept, 0)

    def test_init_with_options(self):
        """Test BinaryStripper initialization with custom options."""
        stripper = strip_binaries.BinaryStripper(
            source_dir=Path("src"),
            output_dir=Path("dst"),
            platform="win-x86_64",
            keep_headers=True,
            strip_binaries=False,
            verbose=True,
        )
        self.assertEqual(stripper.source_dir, Path("src"))
        self.assertEqual(stripper.output_dir, Path("dst"))
        self.assertEqual(stripper.platform, "win-x86_64")
        self.assertTrue(stripper.keep_headers)
        self.assertFalse(stripper.strip_binaries)
        self.assertTrue(stripper.verbose)

    def test_log_verbose_off(self):
        """Test log method when verbose is off."""
        with patch("builtins.print") as mock_print:
            self.stripper.log("test message")
            mock_print.assert_not_called()

    def test_log_verbose_on(self):
        """Test log method when verbose is on."""
        self.stripper.verbose = True
        with patch("builtins.print") as mock_print:
            self.stripper.log("test message")
            mock_print.assert_called_once_with("test message")

    @patch("pathlib.Path.rglob")
    def test_get_dir_size(self, mock_rglob):
        """Test directory size calculation."""
        # Mock file structure
        mock_file1 = Mock()
        mock_file1.is_file.return_value = True
        mock_file1.stat.return_value.st_size = 1000

        mock_file2 = Mock()
        mock_file2.is_file.return_value = True
        mock_file2.stat.return_value.st_size = 2000

        mock_dir = Mock()
        mock_dir.is_file.return_value = False

        mock_rglob.return_value = [mock_file1, mock_file2, mock_dir]

        size = self.stripper.get_dir_size(Path("test"))
        self.assertEqual(size, 3000)

    @patch("pathlib.Path.rglob")
    def test_get_dir_size_error(self, mock_rglob):
        """Test directory size calculation with error."""
        mock_rglob.side_effect = Exception("Permission denied")
        size = self.stripper.get_dir_size(Path("test"))
        self.assertEqual(size, 0)

    @patch("pathlib.Path.exists")
    def test_find_llvm_root_direct(self, mock_exists):
        """Test finding LLVM root when source_dir is root."""
        mock_exists.return_value = True
        root = self.stripper.find_llvm_root()
        self.assertEqual(root, self.source_dir)

    @patch("pathlib.Path.iterdir")
    @patch("pathlib.Path.exists")
    def test_find_llvm_root_subdirectory(self, mock_exists, mock_iterdir):
        """Test finding LLVM root in subdirectory."""
        # source_dir/bin doesn't exist
        mock_exists.return_value = False

        # Create mock subdirectory with bin
        mock_subdir = Mock()
        mock_subdir.is_dir.return_value = True
        mock_subdir.__truediv__ = lambda self, other: Mock(exists=lambda: other == "bin")
        mock_subdir.name = "llvm-21.1.5"

        mock_iterdir.return_value = [mock_subdir]

        root = self.stripper.find_llvm_root()
        self.assertIsNotNone(root)

    @patch("pathlib.Path.iterdir")
    @patch("pathlib.Path.exists")
    def test_find_llvm_root_not_found(self, mock_exists, mock_iterdir):
        """Test finding LLVM root when not found."""
        mock_exists.return_value = False
        mock_iterdir.return_value = []

        root = self.stripper.find_llvm_root()
        self.assertIsNone(root)

    def test_should_keep_binary_essential(self):
        """Test should_keep_binary for essential binaries."""
        # Test exact match
        self.assertTrue(self.stripper.should_keep_binary("clang"))
        self.assertTrue(self.stripper.should_keep_binary("clang++"))
        self.assertTrue(self.stripper.should_keep_binary("llvm-ar"))
        self.assertTrue(self.stripper.should_keep_binary("lld"))

    def test_should_keep_binary_with_extension(self):
        """Test should_keep_binary with file extensions."""
        self.assertTrue(self.stripper.should_keep_binary("clang.exe"))
        self.assertTrue(self.stripper.should_keep_binary("llvm-ar.exe"))
        self.assertTrue(self.stripper.should_keep_binary("lld.dll"))

    def test_should_keep_binary_non_essential(self):
        """Test should_keep_binary for non-essential binaries."""
        self.assertFalse(self.stripper.should_keep_binary("llvm-xray"))
        self.assertFalse(self.stripper.should_keep_binary("opt"))
        self.assertFalse(self.stripper.should_keep_binary("llc"))
        self.assertFalse(self.stripper.should_keep_binary("random-tool"))

    @patch("shutil.copy2")
    @patch("shutil.copytree")
    @patch("pathlib.Path.mkdir")
    @patch("pathlib.Path.exists")
    @patch("pathlib.Path.glob")
    @patch("pathlib.Path.iterdir")
    def test_copy_essential_files_bins(
        self,
        mock_iterdir,
        mock_glob,
        mock_exists,
        mock_mkdir,
        mock_copytree,
        mock_copy2,
    ):
        """Test copying essential binary files."""
        mock_exists.return_value = True

        # Mock bin directory contents
        mock_clang = Mock()
        mock_clang.is_file.return_value = True
        mock_clang.name = "clang"

        mock_opt = Mock()
        mock_opt.is_file.return_value = True
        mock_opt.name = "opt"

        mock_iterdir.return_value = [mock_clang, mock_opt]
        mock_glob.return_value = []  # No license files

        src_root = Path("src")
        dst_root = Path("dst")

        self.stripper.copy_essential_files(src_root, dst_root)

        # Should keep clang (files_kept > 0), remove opt (files_removed > 0)
        self.assertGreater(self.stripper.files_kept, 0)
        self.assertGreater(self.stripper.files_removed, 0)

    @patch("shutil.copy2")
    @patch("shutil.copytree")
    @patch("pathlib.Path.mkdir")
    @patch("pathlib.Path.exists")
    @patch("pathlib.Path.glob")
    @patch("pathlib.Path.iterdir")
    def test_copy_essential_files_libs(
        self,
        mock_iterdir,
        mock_glob,
        mock_exists,
        mock_mkdir,
        mock_copytree,
        mock_copy2,
    ):
        """Test copying essential library files."""
        # Always return True for exists checks (simpler approach)
        mock_exists.return_value = True

        # Mock lib directory contents
        mock_clang_dir = Mock()
        mock_clang_dir.is_dir.return_value = True
        mock_clang_dir.is_file.return_value = False
        mock_clang_dir.name = "clang"

        mock_static_lib = Mock()
        mock_static_lib.is_dir.return_value = False
        mock_static_lib.is_file.return_value = True
        mock_static_lib.name = "libLLVM.a"
        mock_static_lib.suffix = ".a"

        mock_dynamic_lib = Mock()
        mock_dynamic_lib.is_dir.return_value = False
        mock_dynamic_lib.is_file.return_value = True
        mock_dynamic_lib.name = "libLLVM.so"
        mock_dynamic_lib.suffix = ".so"

        mock_iterdir.return_value = [mock_clang_dir, mock_static_lib, mock_dynamic_lib]
        mock_glob.return_value = []  # No license files

        src_root = Path("src")
        dst_root = Path("dst")

        self.stripper.copy_essential_files(src_root, dst_root)

        # Should copytree clang dir at least once
        self.assertGreater(mock_copytree.call_count, 0)

    @patch("shutil.copy2")
    @patch("shutil.copytree")
    @patch("pathlib.Path.mkdir")
    @patch("pathlib.Path.exists")
    @patch("pathlib.Path.glob")
    @patch("pathlib.Path.iterdir")
    def test_copy_essential_files_with_headers(
        self,
        mock_iterdir,
        mock_glob,
        mock_exists,
        mock_mkdir,
        mock_copytree,
        mock_copy2,
    ):
        """Test copying files with headers enabled."""
        self.stripper.keep_headers = True
        mock_exists.return_value = True
        mock_iterdir.return_value = []
        mock_glob.return_value = []

        src_root = Path("src")
        dst_root = Path("dst")

        self.stripper.copy_essential_files(src_root, dst_root)

        # Should call copytree for include directory
        # Check that copytree was called at least once
        self.assertTrue(mock_copytree.called)

    @patch("subprocess.run")
    @patch("pathlib.Path.stat")
    @patch("pathlib.Path.exists")
    def test_strip_binary_linux(self, mock_exists, mock_stat, mock_run):
        """Test stripping binary on Linux."""
        mock_exists.return_value = True
        mock_stat.return_value.st_size = 10000000
        mock_run.return_value = Mock(returncode=0, stderr="")

        binary_path = Path("test_binary")
        result = self.stripper.strip_binary(binary_path)

        self.assertTrue(result)
        mock_run.assert_called_once()
        # Check that strip command was called
        args = mock_run.call_args[0][0]
        self.assertIn("llvm-strip", str(args[0]) if isinstance(args, list) else "")

    @patch("subprocess.run")
    @patch("pathlib.Path.stat")
    @patch("pathlib.Path.exists")
    def test_strip_binary_windows(self, mock_exists, mock_stat, mock_run):
        """Test stripping binary on Windows."""
        self.stripper.platform = "win-x86_64"
        mock_exists.return_value = True
        mock_stat.return_value.st_size = 10000000
        mock_run.return_value = Mock(returncode=0, stderr="")

        binary_path = Path("test_binary.exe")
        result = self.stripper.strip_binary(binary_path)

        self.assertTrue(result)
        mock_run.assert_called_once()

    @patch("pathlib.Path.exists")
    def test_strip_binary_no_llvm_strip(self, mock_exists):
        """Test stripping when llvm-strip doesn't exist."""
        mock_exists.return_value = False
        self.stripper.verbose = True

        binary_path = Path("test_binary")
        result = self.stripper.strip_binary(binary_path)

        # Should return False on Windows, attempt with system strip on Unix
        if "win" in self.platform:
            self.assertFalse(result)

    def test_strip_binary_disabled(self):
        """Test stripping when disabled."""
        self.stripper.strip_binaries = False
        binary_path = Path("test_binary")
        result = self.stripper.strip_binary(binary_path)
        self.assertTrue(result)

    @patch("subprocess.run")
    @patch("pathlib.Path.stat")
    @patch("pathlib.Path.exists")
    def test_strip_binary_failure(self, mock_exists, mock_stat, mock_run):
        """Test stripping binary failure."""
        mock_exists.return_value = True
        mock_stat.return_value.st_size = 10000000
        mock_run.return_value = Mock(returncode=1, stderr="Error stripping")

        binary_path = Path("test_binary")
        result = self.stripper.strip_binary(binary_path)

        self.assertFalse(result)

    @patch.object(strip_binaries.BinaryStripper, "strip_binary")
    @patch("os.access")
    @patch("pathlib.Path.exists")
    @patch("pathlib.Path.iterdir")
    @patch("builtins.print")
    def test_strip_all_binaries(self, mock_print, mock_iterdir, mock_exists, mock_access, mock_strip_binary):
        """Test stripping all binaries."""
        mock_exists.return_value = True

        # Mock binary files
        mock_binary1 = Mock()
        mock_binary1.is_file.return_value = True
        mock_binary1.suffix = ".exe"

        mock_binary2 = Mock()
        mock_binary2.is_file.return_value = True
        mock_binary2.suffix = ".dll"

        mock_iterdir.return_value = [mock_binary1, mock_binary2]
        mock_access.return_value = True
        mock_strip_binary.return_value = True

        self.stripper.platform = "win-x86_64"
        self.stripper.strip_all_binaries()

        # Should have attempted to strip 2 binaries
        self.assertEqual(mock_strip_binary.call_count, 2)

    @patch.object(strip_binaries.BinaryStripper, "strip_binary")
    @patch("pathlib.Path.exists")
    @patch("builtins.print")
    def test_strip_all_binaries_no_bin_dir(self, mock_print, mock_exists, mock_strip_binary):
        """Test stripping when bin directory doesn't exist."""
        mock_exists.return_value = False

        self.stripper.strip_all_binaries()

        mock_strip_binary.assert_not_called()

    @patch.object(strip_binaries.BinaryStripper, "strip_all_binaries")
    @patch.object(strip_binaries.BinaryStripper, "copy_essential_files")
    @patch.object(strip_binaries.BinaryStripper, "get_dir_size")
    @patch.object(strip_binaries.BinaryStripper, "find_llvm_root")
    @patch("builtins.print")
    def test_process_success(
        self,
        mock_print,
        mock_find_root,
        mock_get_size,
        mock_copy_files,
        mock_strip_binaries,
    ):
        """Test successful processing."""
        mock_find_root.return_value = Path("llvm_root")
        mock_get_size.side_effect = [3500000000, 300000000]  # 3.5GB -> 300MB

        result = self.stripper.process()

        self.assertTrue(result)
        mock_find_root.assert_called_once()
        mock_copy_files.assert_called_once()
        mock_strip_binaries.assert_called_once()
        self.assertEqual(self.stripper.original_size, 3500000000)
        self.assertEqual(self.stripper.final_size, 300000000)

    @patch.object(strip_binaries.BinaryStripper, "find_llvm_root")
    @patch("builtins.print")
    def test_process_no_llvm_root(self, mock_print, mock_find_root):
        """Test processing when LLVM root not found."""
        mock_find_root.return_value = None

        result = self.stripper.process()

        self.assertFalse(result)


class TestEssentialBinaries(unittest.TestCase):
    """Test essential binaries configuration."""

    def test_essential_binaries_exist(self):
        """Test that ESSENTIAL_BINARIES is defined."""
        self.assertIsNotNone(strip_binaries.ESSENTIAL_BINARIES)
        self.assertIsInstance(strip_binaries.ESSENTIAL_BINARIES, set)

    def test_essential_binaries_include_compilers(self):
        """Test that compilers are in essential binaries."""
        compilers = ["clang", "clang++", "clang-cl"]
        for compiler in compilers:
            self.assertIn(compiler, strip_binaries.ESSENTIAL_BINARIES)

    def test_essential_binaries_include_linkers(self):
        """Test that linkers are in essential binaries."""
        linkers = ["lld", "lld-link"]
        for linker in linkers:
            self.assertIn(linker, strip_binaries.ESSENTIAL_BINARIES)

    def test_essential_binaries_include_ar(self):
        """Test that archiver is in essential binaries."""
        self.assertIn("llvm-ar", strip_binaries.ESSENTIAL_BINARIES)

    def test_essential_binaries_include_utils(self):
        """Test that binary utilities are in essential binaries."""
        utils = [
            "llvm-nm",
            "llvm-objdump",
            "llvm-objcopy",
            "llvm-ranlib",
            "llvm-strip",
            "llvm-readelf",
            "llvm-readobj",
        ]
        for util in utils:
            self.assertIn(util, strip_binaries.ESSENTIAL_BINARIES)


class TestRemovalConfigs(unittest.TestCase):
    """Test removal configuration constants."""

    def test_remove_dirs_exist(self):
        """Test that REMOVE_DIRS is defined."""
        self.assertIsNotNone(strip_binaries.REMOVE_DIRS)
        self.assertIsInstance(strip_binaries.REMOVE_DIRS, set)

    def test_remove_dirs_include_docs(self):
        """Test that documentation directories are in REMOVE_DIRS."""
        doc_dirs = ["share/doc", "share/man", "docs"]
        for doc_dir in doc_dirs:
            self.assertIn(doc_dir, strip_binaries.REMOVE_DIRS)

    def test_remove_patterns_exist(self):
        """Test that REMOVE_PATTERNS is defined."""
        self.assertIsNotNone(strip_binaries.REMOVE_PATTERNS)
        self.assertIsInstance(strip_binaries.REMOVE_PATTERNS, set)

    def test_remove_patterns_include_static_libs(self):
        """Test that static libraries are in REMOVE_PATTERNS."""
        self.assertIn("*.a", strip_binaries.REMOVE_PATTERNS)
        self.assertIn("*.lib", strip_binaries.REMOVE_PATTERNS)


if __name__ == "__main__":
    unittest.main()
