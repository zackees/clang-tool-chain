"""Tests for macOS sysroot header bundling (MacOSSysrootTransformer).

Unit tests that run on all platforms to verify the transformer logic.
The macOS transformer acts as a fallback when MacOSSDKTransformer cannot
find the system SDK (no Xcode/CLT installed).
"""

import os
from unittest.mock import patch


class TestMacOSSysrootTransformerUnit:
    """Unit tests for MacOSSysrootTransformer class (all platforms).

    These tests verify the transformer's filtering logic without requiring
    actual bundled sysroot headers to be present.
    """

    def test_priority(self):
        """Test transformer priority is 105 (after MacOSSDKTransformer at 100)."""
        from clang_tool_chain.execution.arg_transformers import MacOSSysrootTransformer

        transformer = MacOSSysrootTransformer()
        assert transformer.priority() == 105

    def test_skips_non_darwin(self):
        """Test transformer skips non-macOS platforms."""
        from clang_tool_chain.execution.arg_transformers import (
            MacOSSysrootTransformer,
            ToolContext,
        )

        transformer = MacOSSysrootTransformer()

        # Test Windows
        context_win = ToolContext("win", "x86_64", "clang", False)
        result = transformer.transform(["test.c"], context_win)
        assert result == ["test.c"], "Should skip Windows"

        # Test Linux
        context_linux = ToolContext("linux", "x86_64", "clang", False)
        result = transformer.transform(["test.c"], context_linux)
        assert result == ["test.c"], "Should skip Linux"

    def test_skips_non_clang_tools(self):
        """Test transformer skips non-clang tools."""
        from clang_tool_chain.execution.arg_transformers import (
            MacOSSysrootTransformer,
            ToolContext,
        )

        transformer = MacOSSysrootTransformer()

        # Test llvm-ar
        context = ToolContext("darwin", "x86_64", "llvm-ar", False)
        result = transformer.transform(["test.a"], context)
        assert result == ["test.a"], "Should skip llvm-ar"

        # Test llvm-nm
        context = ToolContext("darwin", "arm64", "llvm-nm", False)
        result = transformer.transform(["test.o"], context)
        assert result == ["test.o"], "Should skip llvm-nm"

    def test_skips_when_isysroot_present(self):
        """Test transformer skips when -isysroot is already in args (system SDK found)."""
        from clang_tool_chain.execution.arg_transformers import (
            MacOSSysrootTransformer,
            ToolContext,
        )

        transformer = MacOSSysrootTransformer()
        context = ToolContext("darwin", "x86_64", "clang", False)

        result = transformer.transform(["-isysroot", "/Library/Developer/SDKs/MacOSX.sdk", "test.c"], context)
        assert result == ["-isysroot", "/Library/Developer/SDKs/MacOSX.sdk", "test.c"], "Should skip with -isysroot"

    def test_skips_with_sysroot_flag(self):
        """Test transformer skips when --sysroot is present."""
        from clang_tool_chain.execution.arg_transformers import (
            MacOSSysrootTransformer,
            ToolContext,
        )

        transformer = MacOSSysrootTransformer()
        context = ToolContext("darwin", "arm64", "clang", False)

        result = transformer.transform(["--sysroot=/custom/path", "test.c"], context)
        assert result == ["--sysroot=/custom/path", "test.c"], "Should skip with --sysroot"

    def test_skips_with_nostdinc(self):
        """Test transformer skips when -nostdinc is present."""
        from clang_tool_chain.execution.arg_transformers import (
            MacOSSysrootTransformer,
            ToolContext,
        )

        transformer = MacOSSysrootTransformer()
        context = ToolContext("darwin", "x86_64", "clang", False)

        result = transformer.transform(["-nostdinc", "test.c"], context)
        assert result == ["-nostdinc", "test.c"], "Should skip with -nostdinc"

    def test_skips_with_nostdincpp(self):
        """Test transformer skips when -nostdinc++ is present."""
        from clang_tool_chain.execution.arg_transformers import (
            MacOSSysrootTransformer,
            ToolContext,
        )

        transformer = MacOSSysrootTransformer()
        context = ToolContext("darwin", "arm64", "clang++", False)

        result = transformer.transform(["-nostdinc++", "test.cpp"], context)
        assert result == ["-nostdinc++", "test.cpp"], "Should skip with -nostdinc++"

    def test_skips_with_nostdlib(self):
        """Test transformer skips when -nostdlib is present."""
        from clang_tool_chain.execution.arg_transformers import (
            MacOSSysrootTransformer,
            ToolContext,
        )

        transformer = MacOSSysrootTransformer()
        context = ToolContext("darwin", "x86_64", "clang", False)

        result = transformer.transform(["-nostdlib", "test.c"], context)
        assert result == ["-nostdlib", "test.c"], "Should skip with -nostdlib"

    def test_skips_with_ffreestanding(self):
        """Test transformer skips when -ffreestanding is present."""
        from clang_tool_chain.execution.arg_transformers import (
            MacOSSysrootTransformer,
            ToolContext,
        )

        transformer = MacOSSysrootTransformer()
        context = ToolContext("darwin", "arm64", "clang", False)

        result = transformer.transform(["-ffreestanding", "test.c"], context)
        assert result == ["-ffreestanding", "test.c"], "Should skip with -ffreestanding"

    def test_opt_out_via_env_var(self):
        """Test transformer is disabled by CLANG_TOOL_CHAIN_NO_BUNDLED_SYSROOT=1."""
        from clang_tool_chain.execution.arg_transformers import (
            MacOSSysrootTransformer,
            ToolContext,
        )

        transformer = MacOSSysrootTransformer()
        context = ToolContext("darwin", "x86_64", "clang", False)

        with patch.dict(os.environ, {"CLANG_TOOL_CHAIN_NO_BUNDLED_SYSROOT": "1"}):
            result = transformer.transform(["test.c"], context)
            assert result == ["test.c"], "Should skip when BUNDLED_SYSROOT disabled"

    def test_opt_out_via_no_auto(self):
        """Test transformer is disabled by CLANG_TOOL_CHAIN_NO_AUTO=1."""
        from clang_tool_chain.execution.arg_transformers import (
            MacOSSysrootTransformer,
            ToolContext,
        )

        transformer = MacOSSysrootTransformer()
        context = ToolContext("darwin", "arm64", "clang", False)

        with patch.dict(os.environ, {"CLANG_TOOL_CHAIN_NO_AUTO": "1"}):
            result = transformer.transform(["test.c"], context)
            assert result == ["test.c"], "Should skip when NO_AUTO set"

    def test_applies_to_clang(self):
        """Test transformer applies to clang on macOS (doesn't crash)."""
        from clang_tool_chain.execution.arg_transformers import (
            MacOSSysrootTransformer,
            ToolContext,
        )

        transformer = MacOSSysrootTransformer()
        context = ToolContext("darwin", "x86_64", "clang", False)

        # Result may or may not change depending on whether
        # bundled sysroot exists. We just verify it doesn't crash.
        result = transformer.transform(["test.c"], context)
        assert isinstance(result, list)

    def test_applies_to_clang_plus_plus(self):
        """Test transformer applies to clang++ on macOS (doesn't crash)."""
        from clang_tool_chain.execution.arg_transformers import (
            MacOSSysrootTransformer,
            ToolContext,
        )

        transformer = MacOSSysrootTransformer()
        context = ToolContext("darwin", "arm64", "clang++", False)

        result = transformer.transform(["test.cpp"], context)
        assert isinstance(result, list)

    def test_in_default_pipeline(self):
        """Test MacOSSysrootTransformer is included in the default pipeline."""
        from clang_tool_chain.execution.arg_transformers import (
            MacOSSysrootTransformer,
            create_default_pipeline,
        )

        pipeline = create_default_pipeline()
        transformer_types = [type(t) for t in pipeline._transformers]
        assert MacOSSysrootTransformer in transformer_types, "Should be in default pipeline"

    def test_pipeline_order_after_sdk(self):
        """Test MacOSSysrootTransformer runs after MacOSSDKTransformer."""
        from clang_tool_chain.execution.arg_transformers import (
            MacOSSDKTransformer,
            MacOSSysrootTransformer,
            create_default_pipeline,
        )

        pipeline = create_default_pipeline()
        transformer_types = [type(t) for t in pipeline._transformers]
        sdk_idx = transformer_types.index(MacOSSDKTransformer)
        sysroot_idx = transformer_types.index(MacOSSysrootTransformer)
        assert sdk_idx < sysroot_idx, "SDK transformer should run before sysroot fallback"

    def test_pipeline_order_before_unwind(self):
        """Test MacOSSysrootTransformer runs before MacOSUnwindTransformer."""
        from clang_tool_chain.execution.arg_transformers import (
            MacOSSysrootTransformer,
            MacOSUnwindTransformer,
            create_default_pipeline,
        )

        pipeline = create_default_pipeline()
        transformer_types = [type(t) for t in pipeline._transformers]
        sysroot_idx = transformer_types.index(MacOSSysrootTransformer)
        unwind_idx = transformer_types.index(MacOSUnwindTransformer)
        assert sysroot_idx < unwind_idx, "Sysroot should run before unwind"


class TestMacOSSysrootTransformerWithHeaders:
    """Tests that verify -isystem injection when sysroot headers are present.

    These tests mock the filesystem to simulate bundled sysroot headers.
    """

    def test_injects_isystem_flag(self, tmp_path):
        """Test that -isystem flag is injected when sysroot exists and no -isysroot."""
        from clang_tool_chain.execution.arg_transformers import (
            MacOSSysrootTransformer,
            ToolContext,
        )

        transformer = MacOSSysrootTransformer()
        context = ToolContext("darwin", "x86_64", "clang", False)

        # Create mock sysroot structure
        sysroot_include = tmp_path / "sysroot" / "usr" / "include"
        sysroot_include.mkdir(parents=True)
        (sysroot_include / "stdio.h").write_text("/* stdio */")

        # Mock get_platform_binary_dir to return our temp dir
        mock_bin_dir = tmp_path / "bin"
        mock_bin_dir.mkdir()

        with (
            patch("clang_tool_chain.execution.arg_transformers.is_feature_disabled", return_value=False),
            patch(
                "clang_tool_chain.platform.detection.get_platform_binary_dir",
                return_value=mock_bin_dir,
            ),
        ):
            result = transformer.transform(["test.c"], context)

        # Should have added one -isystem flag (no multiarch on macOS)
        isystem_flags = [arg for arg in result if arg.startswith("-isystem")]
        assert len(isystem_flags) == 1, f"Expected 1 -isystem flag, got {isystem_flags}"
        assert str(sysroot_include) in isystem_flags[0]

    def test_does_not_inject_when_isysroot_present(self, tmp_path):
        """Test that no -isystem is injected when -isysroot is already present."""
        from clang_tool_chain.execution.arg_transformers import (
            MacOSSysrootTransformer,
            ToolContext,
        )

        transformer = MacOSSysrootTransformer()
        context = ToolContext("darwin", "arm64", "clang", False)

        # Create mock sysroot structure (would normally trigger injection)
        sysroot_include = tmp_path / "sysroot" / "usr" / "include"
        sysroot_include.mkdir(parents=True)
        (sysroot_include / "stdio.h").write_text("/* stdio */")

        # Args already have -isysroot from MacOSSDKTransformer
        args = ["-isysroot", "/Library/Developer/SDKs/MacOSX.sdk", "test.c"]
        result = transformer.transform(args, context)

        # Should NOT have added any -isystem flags
        isystem_flags = [arg for arg in result if arg.startswith("-isystem")]
        assert len(isystem_flags) == 0, "Should not inject when -isysroot present"

    def test_works_for_arm64(self, tmp_path):
        """Test that transformer works for arm64 architecture."""
        from clang_tool_chain.execution.arg_transformers import (
            MacOSSysrootTransformer,
            ToolContext,
        )

        transformer = MacOSSysrootTransformer()
        context = ToolContext("darwin", "arm64", "clang", False)

        # Create mock sysroot structure
        sysroot_include = tmp_path / "sysroot" / "usr" / "include"
        sysroot_include.mkdir(parents=True)
        (sysroot_include / "stdio.h").write_text("/* stdio */")

        mock_bin_dir = tmp_path / "bin"
        mock_bin_dir.mkdir()

        with (
            patch("clang_tool_chain.execution.arg_transformers.is_feature_disabled", return_value=False),
            patch(
                "clang_tool_chain.platform.detection.get_platform_binary_dir",
                return_value=mock_bin_dir,
            ),
        ):
            result = transformer.transform(["test.c"], context)

        isystem_flags = [arg for arg in result if arg.startswith("-isystem")]
        assert len(isystem_flags) == 1, "Should inject for arm64 too"
