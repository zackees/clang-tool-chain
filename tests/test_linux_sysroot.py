"""Tests for Linux sysroot header bundling (LinuxSysrootTransformer).

Unit tests that run on all platforms to verify the transformer logic.
"""

import os
from unittest.mock import patch


class TestLinuxSysrootTransformerUnit:
    """Unit tests for LinuxSysrootTransformer class (all platforms).

    These tests verify the transformer's filtering logic without requiring
    actual bundled sysroot headers to be present.
    """

    def test_priority(self):
        """Test transformer priority is 140."""
        from clang_tool_chain.execution.arg_transformers import LinuxSysrootTransformer

        transformer = LinuxSysrootTransformer()
        assert transformer.priority() == 140

    def test_skips_non_linux(self):
        """Test transformer skips non-Linux platforms."""
        from clang_tool_chain.execution.arg_transformers import (
            LinuxSysrootTransformer,
            ToolContext,
        )

        transformer = LinuxSysrootTransformer()

        # Test Windows
        context_win = ToolContext("win", "x86_64", "clang", False)
        result = transformer.transform(["test.c"], context_win)
        assert result == ["test.c"], "Should skip Windows"

        # Test macOS
        context_mac = ToolContext("darwin", "x86_64", "clang", False)
        result = transformer.transform(["test.c"], context_mac)
        assert result == ["test.c"], "Should skip macOS"

    def test_skips_non_clang_tools(self):
        """Test transformer skips non-clang tools."""
        from clang_tool_chain.execution.arg_transformers import (
            LinuxSysrootTransformer,
            ToolContext,
        )

        transformer = LinuxSysrootTransformer()

        # Test llvm-ar
        context = ToolContext("linux", "x86_64", "llvm-ar", False)
        result = transformer.transform(["test.a"], context)
        assert result == ["test.a"], "Should skip llvm-ar"

        # Test llvm-nm
        context = ToolContext("linux", "x86_64", "llvm-nm", False)
        result = transformer.transform(["test.o"], context)
        assert result == ["test.o"], "Should skip llvm-nm"

    def test_skips_with_sysroot_flag(self):
        """Test transformer skips when --sysroot is present."""
        from clang_tool_chain.execution.arg_transformers import (
            LinuxSysrootTransformer,
            ToolContext,
        )

        transformer = LinuxSysrootTransformer()
        context = ToolContext("linux", "x86_64", "clang", False)

        result = transformer.transform(["--sysroot=/custom/path", "test.c"], context)
        assert result == ["--sysroot=/custom/path", "test.c"], "Should skip with --sysroot"

        # Also test --sysroot=value form
        result = transformer.transform(["--sysroot=/another/path", "test.c"], context)
        assert result == ["--sysroot=/another/path", "test.c"], "Should skip with --sysroot=value"

    def test_skips_with_nostdinc(self):
        """Test transformer skips when -nostdinc is present."""
        from clang_tool_chain.execution.arg_transformers import (
            LinuxSysrootTransformer,
            ToolContext,
        )

        transformer = LinuxSysrootTransformer()
        context = ToolContext("linux", "x86_64", "clang", False)

        result = transformer.transform(["-nostdinc", "test.c"], context)
        assert result == ["-nostdinc", "test.c"], "Should skip with -nostdinc"

    def test_skips_with_nostdincpp(self):
        """Test transformer skips when -nostdinc++ is present."""
        from clang_tool_chain.execution.arg_transformers import (
            LinuxSysrootTransformer,
            ToolContext,
        )

        transformer = LinuxSysrootTransformer()
        context = ToolContext("linux", "x86_64", "clang++", False)

        result = transformer.transform(["-nostdinc++", "test.cpp"], context)
        assert result == ["-nostdinc++", "test.cpp"], "Should skip with -nostdinc++"

    def test_skips_with_nostdlib(self):
        """Test transformer skips when -nostdlib is present."""
        from clang_tool_chain.execution.arg_transformers import (
            LinuxSysrootTransformer,
            ToolContext,
        )

        transformer = LinuxSysrootTransformer()
        context = ToolContext("linux", "x86_64", "clang", False)

        result = transformer.transform(["-nostdlib", "test.c"], context)
        assert result == ["-nostdlib", "test.c"], "Should skip with -nostdlib"

    def test_skips_with_ffreestanding(self):
        """Test transformer skips when -ffreestanding is present."""
        from clang_tool_chain.execution.arg_transformers import (
            LinuxSysrootTransformer,
            ToolContext,
        )

        transformer = LinuxSysrootTransformer()
        context = ToolContext("linux", "x86_64", "clang", False)

        result = transformer.transform(["-ffreestanding", "test.c"], context)
        assert result == ["-ffreestanding", "test.c"], "Should skip with -ffreestanding"

    def test_opt_out_via_env_var(self):
        """Test transformer is disabled by CLANG_TOOL_CHAIN_NO_BUNDLED_SYSROOT=1."""
        from clang_tool_chain.execution.arg_transformers import (
            LinuxSysrootTransformer,
            ToolContext,
        )

        transformer = LinuxSysrootTransformer()
        context = ToolContext("linux", "x86_64", "clang", False)

        with patch.dict(os.environ, {"CLANG_TOOL_CHAIN_NO_BUNDLED_SYSROOT": "1"}):
            result = transformer.transform(["test.c"], context)
            assert result == ["test.c"], "Should skip when BUNDLED_SYSROOT disabled"

    def test_opt_out_via_no_auto(self):
        """Test transformer is disabled by CLANG_TOOL_CHAIN_NO_AUTO=1."""
        from clang_tool_chain.execution.arg_transformers import (
            LinuxSysrootTransformer,
            ToolContext,
        )

        transformer = LinuxSysrootTransformer()
        context = ToolContext("linux", "x86_64", "clang", False)

        with patch.dict(os.environ, {"CLANG_TOOL_CHAIN_NO_AUTO": "1"}):
            result = transformer.transform(["test.c"], context)
            assert result == ["test.c"], "Should skip when NO_AUTO set"

    def test_applies_to_clang(self):
        """Test transformer applies to clang on Linux (doesn't crash)."""
        from clang_tool_chain.execution.arg_transformers import (
            LinuxSysrootTransformer,
            ToolContext,
        )

        transformer = LinuxSysrootTransformer()
        context = ToolContext("linux", "x86_64", "clang", False)

        # Result may or may not change depending on whether
        # bundled sysroot exists. We just verify it doesn't crash.
        result = transformer.transform(["test.c"], context)
        assert isinstance(result, list)

    def test_applies_to_clang_plus_plus(self):
        """Test transformer applies to clang++ on Linux (doesn't crash)."""
        from clang_tool_chain.execution.arg_transformers import (
            LinuxSysrootTransformer,
            ToolContext,
        )

        transformer = LinuxSysrootTransformer()
        context = ToolContext("linux", "x86_64", "clang++", False)

        result = transformer.transform(["test.cpp"], context)
        assert isinstance(result, list)

    def test_in_default_pipeline(self):
        """Test LinuxSysrootTransformer is included in the default pipeline."""
        from clang_tool_chain.execution.arg_transformers import (
            LinuxSysrootTransformer,
            create_default_pipeline,
        )

        pipeline = create_default_pipeline()
        transformer_types = [type(t) for t in pipeline._transformers]
        assert LinuxSysrootTransformer in transformer_types, "Should be in default pipeline"

    def test_pipeline_order(self):
        """Test LinuxSysrootTransformer runs before LinuxUnwindTransformer in pipeline."""
        from clang_tool_chain.execution.arg_transformers import (
            LinuxSysrootTransformer,
            LinuxUnwindTransformer,
            create_default_pipeline,
        )

        pipeline = create_default_pipeline()
        transformer_types = [type(t) for t in pipeline._transformers]
        sysroot_idx = transformer_types.index(LinuxSysrootTransformer)
        unwind_idx = transformer_types.index(LinuxUnwindTransformer)
        assert sysroot_idx < unwind_idx, "Sysroot should run before unwind"


class TestLinuxSysrootTransformerWithHeaders:
    """Tests that verify -isystem injection when sysroot headers are present.

    These tests mock the filesystem to simulate bundled sysroot headers.
    """

    def test_injects_isystem_flags(self, tmp_path):
        """Test that -isystem flags are injected when sysroot exists."""

        from clang_tool_chain.execution.arg_transformers import (
            LinuxSysrootTransformer,
            ToolContext,
        )

        transformer = LinuxSysrootTransformer()
        context = ToolContext("linux", "x86_64", "clang", False)

        # Create mock sysroot structure
        sysroot_include = tmp_path / "sysroot" / "usr" / "include"
        sysroot_include.mkdir(parents=True)
        (sysroot_include / "stdio.h").write_text("/* stdio */")

        multiarch_dir = sysroot_include / "x86_64-linux-gnu"
        multiarch_dir.mkdir()
        (multiarch_dir / "bits").mkdir()
        (multiarch_dir / "bits" / "types.h").write_text("/* types */")

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

        # Should have added -isystem flags
        isystem_flags = [arg for arg in result if arg.startswith("-isystem")]
        assert len(isystem_flags) == 2, f"Expected 2 -isystem flags, got {isystem_flags}"

        # Common include should be first (prepended last)
        assert str(sysroot_include) in isystem_flags[0]
        # Multiarch should be second (prepended first, so ends up after common when both prepended)
        assert "x86_64-linux-gnu" in isystem_flags[1]

    def test_arm64_multiarch_dir(self, tmp_path):
        """Test that arm64 multiarch directory is used for aarch64 context."""
        from clang_tool_chain.execution.arg_transformers import (
            LinuxSysrootTransformer,
            ToolContext,
        )

        transformer = LinuxSysrootTransformer()
        context = ToolContext("linux", "aarch64", "clang", False)

        # Create mock sysroot structure
        sysroot_include = tmp_path / "sysroot" / "usr" / "include"
        sysroot_include.mkdir(parents=True)
        (sysroot_include / "stdio.h").write_text("/* stdio */")

        multiarch_dir = sysroot_include / "aarch64-linux-gnu"
        multiarch_dir.mkdir()

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
        multiarch_flags = [f for f in isystem_flags if "aarch64-linux-gnu" in f]
        assert len(multiarch_flags) == 1, "Should have aarch64-linux-gnu -isystem flag"


class TestBundledSysrootFeatureRegistration:
    """Test that BUNDLED_SYSROOT is properly registered as a controllable feature."""

    def test_feature_in_controllable_features(self):
        """Test BUNDLED_SYSROOT is in CONTROLLABLE_FEATURES dict."""
        from clang_tool_chain.env_utils import CONTROLLABLE_FEATURES

        assert "BUNDLED_SYSROOT" in CONTROLLABLE_FEATURES

    def test_feature_disabled_check(self):
        """Test is_feature_disabled works for BUNDLED_SYSROOT."""
        from clang_tool_chain.env_utils import is_feature_disabled

        # Default: not disabled
        with patch.dict(os.environ, {}, clear=False):
            # Remove if set
            os.environ.pop("CLANG_TOOL_CHAIN_NO_BUNDLED_SYSROOT", None)
            os.environ.pop("CLANG_TOOL_CHAIN_NO_AUTO", None)
            assert not is_feature_disabled("BUNDLED_SYSROOT")

        # Specific disable
        with patch.dict(os.environ, {"CLANG_TOOL_CHAIN_NO_BUNDLED_SYSROOT": "1"}):
            assert is_feature_disabled("BUNDLED_SYSROOT")

        # Global disable
        with patch.dict(os.environ, {"CLANG_TOOL_CHAIN_NO_AUTO": "1"}):
            assert is_feature_disabled("BUNDLED_SYSROOT")
