"""Tests for the inlined build directives parser."""

import pytest

from clang_tool_chain.directives.parser import DirectiveParser, ParsedDirectives


class TestDirectiveParser:
    """Tests for DirectiveParser."""

    def test_parse_simple_link(self):
        """Test parsing a simple @link directive."""
        content = """// @link: pthread
#include <pthread.h>
int main() { return 0; }
"""
        parser = DirectiveParser()
        result = parser.parse_string(content)

        assert result.links == ["pthread"]
        assert result.get_linker_args() == ["-lpthread"]

    def test_parse_list_link(self):
        """Test parsing @link with list syntax."""
        content = """// @link: [pthread, m, dl]
int main() { return 0; }
"""
        parser = DirectiveParser()
        result = parser.parse_string(content)

        assert result.links == ["pthread", "m", "dl"]
        assert result.get_linker_args() == ["-lpthread", "-lm", "-ldl"]

    def test_parse_std(self):
        """Test parsing @std directive."""
        content = """// @std: c++17
int main() { return 0; }
"""
        parser = DirectiveParser()
        result = parser.parse_string(content)

        assert result.std == "c++17"
        assert "-std=c++17" in result.get_compiler_args()

    def test_parse_cflags(self):
        """Test parsing @cflags directive."""
        content = """// @cflags: -O2 -Wall -Wextra
int main() { return 0; }
"""
        parser = DirectiveParser()
        result = parser.parse_string(content)

        assert result.cflags == ["-O2", "-Wall", "-Wextra"]

    def test_parse_multiple_directives(self):
        """Test parsing multiple directives."""
        content = """// @link: pthread
// @std: c++17
// @cflags: -O2
int main() { return 0; }
"""
        parser = DirectiveParser()
        result = parser.parse_string(content)

        assert result.links == ["pthread"]
        assert result.std == "c++17"
        assert result.cflags == ["-O2"]

    def test_parse_include(self):
        """Test parsing @include directive."""
        content = """// @include: /usr/local/include
// @include: [./vendor, ../common]
int main() { return 0; }
"""
        parser = DirectiveParser()
        result = parser.parse_string(content)

        assert result.includes == ["/usr/local/include", "./vendor", "../common"]

    def test_parse_pkg_config(self):
        """Test parsing @pkg-config directive."""
        content = """// @pkg-config: openssl
// @pkg-config: [libcurl, zlib]
int main() { return 0; }
"""
        parser = DirectiveParser()
        result = parser.parse_string(content)

        assert result.pkg_config == ["openssl", "libcurl", "zlib"]

    def test_stop_at_code(self):
        """Test that parsing stops at non-comment code."""
        content = """// @link: pthread
// @std: c++17
#include <pthread.h>
// @link: shouldnotparse
int main() { return 0; }
"""
        parser = DirectiveParser()
        result = parser.parse_string(content)

        assert result.links == ["pthread"]
        assert "shouldnotparse" not in result.links

    def test_empty_lines_between_directives(self):
        """Test that empty lines between directives are OK."""
        content = """// @link: pthread

// @std: c++17

int main() { return 0; }
"""
        parser = DirectiveParser()
        result = parser.parse_string(content)

        assert result.links == ["pthread"]
        assert result.std == "c++17"

    def test_comments_between_directives(self):
        """Test that regular comments between directives are OK."""
        content = """// @link: pthread
// This is a comment
// Another comment
// @std: c++17
int main() { return 0; }
"""
        parser = DirectiveParser()
        result = parser.parse_string(content)

        assert result.links == ["pthread"]
        assert result.std == "c++17"

    def test_trailing_comment_ignored(self):
        """Test that trailing comments on directive lines are ignored."""
        content = """// @link: pthread  // Required for threading
// @std: c++17 // Modern C++
int main() { return 0; }
"""
        parser = DirectiveParser()
        result = parser.parse_string(content)

        assert result.links == ["pthread"]
        assert result.std == "c++17"

    def test_absolute_library_path(self):
        """Test absolute library path in @link."""
        content = """// @link: /usr/local/lib/libfoo.a
int main() { return 0; }
"""
        parser = DirectiveParser()
        result = parser.parse_string(content)

        assert result.links == ["/usr/local/lib/libfoo.a"]
        assert result.get_linker_args() == ["/usr/local/lib/libfoo.a"]

    def test_get_all_args(self):
        """Test getting all arguments combined."""
        content = """// @link: pthread
// @std: c++17
// @cflags: -O2
// @include: /opt/include
int main() { return 0; }
"""
        parser = DirectiveParser()
        result = parser.parse_string(content)

        all_args = result.get_all_args()
        assert "-std=c++17" in all_args
        assert "-I/opt/include" in all_args
        assert "-O2" in all_args
        assert "-lpthread" in all_args


class TestPlatformDirectives:
    """Tests for platform-specific directives."""

    def test_platform_linux(self):
        """Test platform-specific directives for Linux."""
        content = """// @std: c++17
// @platform: linux
//   @link: pthread
// @platform: windows
//   @link: ws2_32
int main() { return 0; }
"""
        parser = DirectiveParser()
        parser._current_platform = "linux"
        result = parser.parse_for_current_platform(content)

        assert result.std == "c++17"
        assert "pthread" in result.links
        assert "ws2_32" not in result.links

    def test_platform_windows(self):
        """Test platform-specific directives for Windows."""
        content = """// @std: c++17
// @platform: linux
//   @link: pthread
// @platform: windows
//   @link: ws2_32
int main() { return 0; }
"""
        parser = DirectiveParser()
        parser._current_platform = "windows"
        result = parser.parse_for_current_platform(content)

        assert result.std == "c++17"
        assert "ws2_32" in result.links
        assert "pthread" not in result.links


class TestParsedDirectives:
    """Tests for ParsedDirectives dataclass."""

    def test_empty_directives(self):
        """Test empty ParsedDirectives."""
        result = ParsedDirectives()

        assert result.links == []
        assert result.cflags == []
        assert result.std is None
        assert result.get_linker_args() == []
        assert result.get_compiler_args() == []

    def test_merge_platform_no_override(self):
        """Test merge_platform when no override exists."""
        result = ParsedDirectives(links=["base"])
        merged = result.merge_platform("nonexistent")

        assert merged is result  # Same object when no override

    def test_merge_platform_with_override(self):
        """Test merge_platform with existing override."""
        result = ParsedDirectives(
            links=["base"],
            std="c++17",
            platform_overrides={"linux": ParsedDirectives(links=["pthread"], cflags=["-Wall"])},
        )
        merged = result.merge_platform("linux")

        assert "base" in merged.links
        assert "pthread" in merged.links
        assert merged.std == "c++17"
        assert "-Wall" in merged.cflags


class TestFileParser:
    """Tests for file parsing."""

    def test_parse_pthread_example(self, tmp_path):
        """Test parsing the pthread example file."""
        example_content = """// @link: pthread
// @std: c++17
//
// Simple pthread example

#include <pthread.h>
#include <stdio.h>

int main() {
    printf("Hello!\\n");
    return 0;
}
"""
        example_file = tmp_path / "pthread_example.cpp"
        example_file.write_text(example_content)

        parser = DirectiveParser()
        result = parser.parse_file(example_file)

        assert result.source_path == example_file
        assert result.links == ["pthread"]
        assert result.std == "c++17"

    def test_parse_math_example(self, tmp_path):
        """Test parsing the math intensive example."""
        example_content = """// @link: [pthread, m]
// @cflags: -O2 -march=native
// @std: c++17

#include <cmath>
int main() { return 0; }
"""
        example_file = tmp_path / "math_example.cpp"
        example_file.write_text(example_content)

        parser = DirectiveParser()
        result = parser.parse_file(example_file)

        assert result.links == ["pthread", "m"]
        assert "-O2" in result.cflags
        assert "-march=native" in result.cflags
        assert result.std == "c++17"


class TestBuildIntegration:
    """Tests for build integration with directives."""

    def test_get_directive_args_simple(self, tmp_path):
        """Test _get_directive_args with a simple source file."""
        from clang_tool_chain.execution.build import _get_directive_args

        source_content = """// @link: pthread
// @std: c++17
int main() { return 0; }
"""
        source_file = tmp_path / "test.cpp"
        source_file.write_text(source_content)

        args = _get_directive_args(source_file)

        assert "-std=c++17" in args
        assert "-lpthread" in args

    def test_get_directive_args_multiple_flags(self, tmp_path):
        """Test _get_directive_args with multiple flags."""
        from clang_tool_chain.execution.build import _get_directive_args

        source_content = """// @link: [pthread, m]
// @cflags: -O2 -Wall
// @std: c++20
int main() { return 0; }
"""
        source_file = tmp_path / "test.cpp"
        source_file.write_text(source_content)

        args = _get_directive_args(source_file)

        assert "-std=c++20" in args
        assert "-O2" in args
        assert "-Wall" in args
        assert "-lpthread" in args
        assert "-lm" in args

    def test_get_directive_args_no_directives(self, tmp_path):
        """Test _get_directive_args with no directives."""
        from clang_tool_chain.execution.build import _get_directive_args

        source_content = """// Regular comment
#include <stdio.h>
int main() { return 0; }
"""
        source_file = tmp_path / "test.c"
        source_file.write_text(source_content)

        args = _get_directive_args(source_file)

        assert args == []

    def test_get_directive_args_disabled_via_env(self, tmp_path, monkeypatch):
        """Test that directives can be disabled via environment variable."""
        from clang_tool_chain.execution.build import _get_directive_args

        source_content = """// @link: pthread
// @std: c++17
int main() { return 0; }
"""
        source_file = tmp_path / "test.cpp"
        source_file.write_text(source_content)

        # Disable directives parsing
        monkeypatch.setenv("CLANG_TOOL_CHAIN_NO_DIRECTIVES", "1")

        args = _get_directive_args(source_file)

        assert args == []

    def test_example_files_exist(self):
        """Test that the example files have correct directives."""
        from pathlib import Path

        from clang_tool_chain.execution.build import _get_directive_args

        examples_dir = Path(__file__).parent.parent / "examples" / "inlined_directives"

        # pthread_hello.cpp
        pthread_file = examples_dir / "pthread_hello.cpp"
        if pthread_file.exists():
            args = _get_directive_args(pthread_file)
            assert "-std=c++17" in args
            assert "-lpthread" in args

        # math_intensive.cpp
        math_file = examples_dir / "math_intensive.cpp"
        if math_file.exists():
            args = _get_directive_args(math_file)
            assert "-std=c++17" in args
            assert "-lpthread" in args
            assert "-lm" in args
            assert "-O2" in args


class TestDirectiveArgsFromCompilerArgs:
    """Tests for get_directive_args_from_compiler_args function.

    This tests the function that extracts directives from source files
    found in compiler argument lists (for clang-tool-chain-c/cpp support).
    """

    def test_single_source_file(self, tmp_path):
        """Test extracting directives from a single source file."""
        from clang_tool_chain.execution.build import get_directive_args_from_compiler_args

        source_content = """// @link: pthread
// @std: c++17
int main() { return 0; }
"""
        source_file = tmp_path / "test.cpp"
        source_file.write_text(source_content)

        args = [str(source_file), "-o", "test.exe"]
        directive_args = get_directive_args_from_compiler_args(args)

        assert "-std=c++17" in directive_args
        assert "-lpthread" in directive_args

    def test_multiple_source_files(self, tmp_path):
        """Test extracting directives from multiple source files."""
        from clang_tool_chain.execution.build import get_directive_args_from_compiler_args

        # First source with pthread
        source1 = tmp_path / "main.cpp"
        source1.write_text(
            """// @link: pthread
int main() { return 0; }
"""
        )

        # Second source with math lib
        source2 = tmp_path / "math_utils.cpp"
        source2.write_text(
            """// @link: m
void compute() {}
"""
        )

        args = [str(source1), str(source2), "-o", "test.exe"]
        directive_args = get_directive_args_from_compiler_args(args)

        assert "-lpthread" in directive_args
        assert "-lm" in directive_args

    def test_no_directives(self, tmp_path):
        """Test with source files that have no directives."""
        from clang_tool_chain.execution.build import get_directive_args_from_compiler_args

        source_file = tmp_path / "simple.c"
        source_file.write_text(
            """int main() { return 0; }
"""
        )

        args = [str(source_file), "-o", "simple"]
        directive_args = get_directive_args_from_compiler_args(args)

        assert directive_args == []

    def test_skip_flags(self, tmp_path):
        """Test that flag arguments are skipped (not treated as source files)."""
        from clang_tool_chain.execution.build import get_directive_args_from_compiler_args

        source_file = tmp_path / "test.cpp"
        source_file.write_text(
            """// @std: c++17
int main() { return 0; }
"""
        )

        # Flags like -O2, -Wall should be skipped
        args = ["-O2", "-Wall", str(source_file), "-o", "test"]
        directive_args = get_directive_args_from_compiler_args(args)

        assert "-std=c++17" in directive_args
        # Ensure flags are not duplicated
        assert "-O2" not in directive_args

    def test_nonexistent_file(self, tmp_path):
        """Test that nonexistent files are skipped."""
        from clang_tool_chain.execution.build import get_directive_args_from_compiler_args

        # Reference a file that doesn't exist
        args = ["nonexistent.cpp", "-o", "test"]
        directive_args = get_directive_args_from_compiler_args(args)

        # Should return empty - nonexistent file is skipped
        assert directive_args == []

    def test_disabled_via_env(self, tmp_path, monkeypatch):
        """Test that directive parsing can be disabled via environment variable."""
        from clang_tool_chain.execution.build import get_directive_args_from_compiler_args

        source_file = tmp_path / "test.cpp"
        source_file.write_text(
            """// @link: pthread
int main() { return 0; }
"""
        )

        # Disable directives
        monkeypatch.setenv("CLANG_TOOL_CHAIN_NO_DIRECTIVES", "1")

        args = [str(source_file), "-o", "test"]
        directive_args = get_directive_args_from_compiler_args(args)

        assert directive_args == []

    def test_c_source_file(self, tmp_path):
        """Test extracting directives from C source files."""
        from clang_tool_chain.execution.build import get_directive_args_from_compiler_args

        source_file = tmp_path / "test.c"
        source_file.write_text(
            """// @link: m
// @std: c11
int main() { return 0; }
"""
        )

        args = [str(source_file), "-o", "test"]
        directive_args = get_directive_args_from_compiler_args(args)

        assert "-std=c11" in directive_args
        assert "-lm" in directive_args

    def test_various_extensions(self, tmp_path):
        """Test various C/C++ source file extensions."""
        from clang_tool_chain.execution.build import get_directive_args_from_compiler_args

        extensions = [".c", ".cpp", ".cc", ".cxx", ".c++"]
        for ext in extensions:
            source_file = tmp_path / f"test{ext}"
            source_file.write_text(
                f"""// @link: test_{ext[1:]}
int main() {{ return 0; }}
"""
            )

            args = [str(source_file), "-o", "test"]
            directive_args = get_directive_args_from_compiler_args(args)

            assert f"-ltest_{ext[1:]}" in directive_args, f"Failed for extension {ext}"

    def test_no_duplicate_args(self, tmp_path):
        """Test that duplicate directive args are deduplicated."""
        from clang_tool_chain.execution.build import get_directive_args_from_compiler_args

        # Both files link to pthread
        source1 = tmp_path / "a.cpp"
        source1.write_text(
            """// @link: pthread
void a() {}
"""
        )

        source2 = tmp_path / "b.cpp"
        source2.write_text(
            """// @link: pthread
void b() {}
"""
        )

        args = [str(source1), str(source2), "-o", "test"]
        directive_args = get_directive_args_from_compiler_args(args)

        # Should only have one -lpthread
        assert directive_args.count("-lpthread") == 1


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
