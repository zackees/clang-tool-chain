"""Tests for the callgrind execution module."""

from unittest.mock import patch

import pytest


class TestCallgrindArgParsing:
    """Test argument parsing for the callgrind command."""

    def test_parse_basic_executable(self):
        """Test parsing with just an executable."""
        from clang_tool_chain.execution.callgrind import _parse_callgrind_args

        _, valgrind_flags, executable, exe_args, raw, output_file, threshold = _parse_callgrind_args(["./program"])
        assert executable == "./program"
        assert exe_args == []
        assert valgrind_flags == []
        assert raw is False
        assert output_file is None
        assert threshold == 95

    def test_parse_executable_with_args(self):
        """Test parsing with executable and its arguments."""
        from clang_tool_chain.execution.callgrind import _parse_callgrind_args

        _, valgrind_flags, executable, exe_args, raw, output_file, threshold = _parse_callgrind_args(
            ["./program", "arg1", "arg2"]
        )
        assert executable == "./program"
        assert exe_args == ["arg1", "arg2"]

    def test_parse_raw_flag(self):
        """Test parsing the --raw flag."""
        from clang_tool_chain.execution.callgrind import _parse_callgrind_args

        _, _, executable, _, raw, _, _ = _parse_callgrind_args(["--raw", "./program"])
        assert executable == "./program"
        assert raw is True

    def test_parse_output_flag_long(self):
        """Test parsing --output flag."""
        from clang_tool_chain.execution.callgrind import _parse_callgrind_args

        _, _, executable, _, _, output_file, _ = _parse_callgrind_args(["--output", "report.txt", "./program"])
        assert executable == "./program"
        assert output_file == "report.txt"

    def test_parse_output_flag_short(self):
        """Test parsing -o flag."""
        from clang_tool_chain.execution.callgrind import _parse_callgrind_args

        _, _, executable, _, _, output_file, _ = _parse_callgrind_args(["-o", "report.txt", "./program"])
        assert executable == "./program"
        assert output_file == "report.txt"

    def test_parse_output_flag_equals(self):
        """Test parsing --output=FILE form."""
        from clang_tool_chain.execution.callgrind import _parse_callgrind_args

        _, _, executable, _, _, output_file, _ = _parse_callgrind_args(["--output=report.txt", "./program"])
        assert executable == "./program"
        assert output_file == "report.txt"

    def test_parse_threshold_equals(self):
        """Test parsing --threshold=N form."""
        from clang_tool_chain.execution.callgrind import _parse_callgrind_args

        _, _, executable, _, _, _, threshold = _parse_callgrind_args(["--threshold=80", "./program"])
        assert executable == "./program"
        assert threshold == 80

    def test_parse_threshold_separate(self):
        """Test parsing --threshold N form."""
        from clang_tool_chain.execution.callgrind import _parse_callgrind_args

        _, _, executable, _, _, _, threshold = _parse_callgrind_args(["--threshold", "80", "./program"])
        assert executable == "./program"
        assert threshold == 80

    def test_parse_valgrind_passthrough_flags(self):
        """Test that unknown flags are passed through to valgrind."""
        from clang_tool_chain.execution.callgrind import _parse_callgrind_args

        _, valgrind_flags, executable, _, _, _, _ = _parse_callgrind_args(
            ["--cache-sim=yes", "--branch-sim=yes", "./program"]
        )
        assert executable == "./program"
        assert "--cache-sim=yes" in valgrind_flags
        assert "--branch-sim=yes" in valgrind_flags

    def test_parse_all_options_combined(self):
        """Test parsing with all option types combined."""
        from clang_tool_chain.execution.callgrind import _parse_callgrind_args

        _, valgrind_flags, executable, exe_args, raw, output_file, threshold = _parse_callgrind_args(
            ["--raw", "--threshold=80", "--cache-sim=yes", "-o", "out.txt", "./program", "arg1"]
        )
        assert executable == "./program"
        assert exe_args == ["arg1"]
        assert raw is True
        assert output_file == "out.txt"
        assert threshold == 80
        assert "--cache-sim=yes" in valgrind_flags

    def test_parse_no_executable(self):
        """Test parsing with no executable specified."""
        from clang_tool_chain.execution.callgrind import _parse_callgrind_args

        _, _, executable, _, _, _, _ = _parse_callgrind_args(["--raw"])
        assert executable is None


class TestCallgrindHelp:
    """Test help/usage output."""

    def test_no_args_shows_usage(self):
        """Test that no arguments shows usage and exits."""
        from clang_tool_chain.execution.callgrind import execute_callgrind_tool

        with pytest.raises(SystemExit) as exc_info:
            execute_callgrind_tool(args=[])
        assert exc_info.value.code == 1

    def test_help_flag_shows_usage(self):
        """Test that --help shows usage and exits with 0."""
        from clang_tool_chain.execution.callgrind import execute_callgrind_tool

        with pytest.raises(SystemExit) as exc_info:
            execute_callgrind_tool(args=["--help"])
        assert exc_info.value.code == 0

    def test_h_flag_shows_usage(self):
        """Test that -h shows usage and exits with 0."""
        from clang_tool_chain.execution.callgrind import execute_callgrind_tool

        with pytest.raises(SystemExit) as exc_info:
            execute_callgrind_tool(args=["-h"])
        assert exc_info.value.code == 0


class TestCallgrindEntryPoint:
    """Test the entry point function exists and is importable."""

    def test_callgrind_main_importable(self):
        """Test that callgrind_main is importable from entry_points."""
        from clang_tool_chain.commands.entry_points import callgrind_main

        assert callable(callgrind_main)

    def test_callgrind_main_in_commands_init(self):
        """Test that callgrind_main is exported from commands package."""
        from clang_tool_chain.commands import callgrind_main

        assert callable(callgrind_main)

    def test_callgrind_main_in_wrapper(self):
        """Test that callgrind_main is exported from wrapper module."""
        from clang_tool_chain.wrapper import callgrind_main

        assert callable(callgrind_main)

    def test_execute_callgrind_tool_importable(self):
        """Test that execute_callgrind_tool is importable."""
        from clang_tool_chain.execution.callgrind import execute_callgrind_tool

        assert callable(execute_callgrind_tool)


class TestCallgrindDockerCheck:
    """Test Docker availability checking."""

    @patch("clang_tool_chain.execution.callgrind._check_docker_available", return_value=False)
    def test_no_docker_exits_with_error(self, mock_docker):
        """Test that missing Docker produces a helpful error."""
        from clang_tool_chain.execution.callgrind import execute_callgrind_tool

        with pytest.raises(SystemExit) as exc_info:
            execute_callgrind_tool(args=["./program"])
        assert exc_info.value.code == 1


class TestCallgrindInvalidThreshold:
    """Test invalid threshold handling."""

    def test_invalid_threshold_value(self):
        """Test that an invalid threshold value exits with error."""
        from clang_tool_chain.execution.callgrind import _parse_callgrind_args

        with pytest.raises(SystemExit):
            _parse_callgrind_args(["--threshold=abc", "./program"])
