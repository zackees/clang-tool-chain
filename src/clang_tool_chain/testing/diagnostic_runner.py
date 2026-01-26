"""
Reusable diagnostic test infrastructure for clang-tool-chain.

Provides a framework for running diagnostic tests with consistent
output formatting, error handling, and keyboard interrupt support.
"""

import sys
from collections.abc import Callable
from typing import Any


class DiagnosticTest:
    """
    Represents a single diagnostic test with metadata.

    Attributes:
        name: Human-readable test name
        test_fn: Callable that executes the test (returns 0 on success, non-zero on failure)
        step_num: Current step number (for progress display)
        total: Total number of tests (for progress display)
    """

    def __init__(self, name: str, test_fn: Callable[[], int], step_num: int, total: int):
        self.name = name
        self.test_fn = test_fn
        self.step_num = step_num
        self.total = total

    def run(self, safe_print_fn: Callable[..., None]) -> int:
        """
        Run the test and display results.

        Args:
            safe_print_fn: Function to use for safe Unicode printing

        Returns:
            0 on success, non-zero on failure
        """
        print(f"[{self.step_num}/{self.total}] {self.name}...")
        try:
            result = self.test_fn()
            if result == 0:
                safe_print_fn("      ✓ PASSED")
            return result
        except KeyboardInterrupt:
            # Re-raise KeyboardInterrupt to allow proper handling at suite level
            raise
        except Exception as e:
            safe_print_fn(f"      ✗ FAILED: {e}")
            return 1


class DiagnosticTestSuite:
    """
    Manages and executes a collection of diagnostic tests.

    Provides consistent formatting, progress tracking, and error handling
    for multiple diagnostic tests.
    """

    def __init__(self, title: str = "Diagnostic Tests", safe_print_fn: Callable[..., None] | None = None):
        """
        Initialize the test suite.

        Args:
            title: Title to display at the start of the test run
            safe_print_fn: Function to use for safe Unicode printing (defaults to print)
        """
        self.title = title
        self.tests: list[DiagnosticTest] = []
        self.safe_print_fn = safe_print_fn if safe_print_fn is not None else print

    def add_test(self, name: str, test_fn: Callable[[], int]) -> None:
        """
        Add a test to the suite.

        Args:
            name: Human-readable test name
            test_fn: Callable that executes the test (returns 0 on success, non-zero on failure)
        """
        step_num = len(self.tests) + 1
        total = 0  # Will be set in run_all()
        self.tests.append(DiagnosticTest(name, test_fn, step_num, total))

    def run_all(self) -> int:
        """
        Run all tests in the suite.

        Displays a header, runs each test in sequence, and displays a summary.
        Stops on first failure or keyboard interrupt.

        Returns:
            0 if all tests passed, non-zero if any test failed
        """
        if not self.tests:
            print("No tests to run.")
            return 0

        # Update total count for all tests
        total = len(self.tests)
        for test in self.tests:
            test.total = total

        # Print header
        print(self.title)
        print("=" * 70)
        print()

        # Run each test
        for test in self.tests:
            result = test.run(self.safe_print_fn)
            print()  # Blank line after each test

            if result != 0:
                # Test failed, stop execution
                print("=" * 70)
                self.safe_print_fn("Tests failed. ✗")
                print()
                return result

        # All tests passed
        print("=" * 70)
        self.safe_print_fn("All tests passed! ✓")
        print()
        return 0


def safe_print(*args: Any, **kwargs: Any) -> None:
    """
    Print function that handles encoding errors gracefully.

    Falls back to ASCII characters if the console doesn't support Unicode.
    This ensures compatibility with Windows CP1252 and other limited encodings.

    This is a helper function that can be used as the safe_print_fn for
    DiagnosticTestSuite, but the suite can also accept a custom implementation.
    """
    try:
        # Try to print normally first
        print(*args, **kwargs)
    except (UnicodeEncodeError, UnicodeDecodeError):
        # If encoding fails, replace Unicode characters with ASCII equivalents
        file = kwargs.get("file", sys.stdout)
        encoding = getattr(file, "encoding", "utf-8") or "utf-8"

        safe_args = []
        for arg in args:
            text = str(arg)

            # First, replace known Unicode characters with ASCII equivalents
            text = text.replace("✓", "[OK]")
            text = text.replace("✗", "[FAIL]")

            # Then, replace any remaining unencodable characters
            safe_text = []
            for char in text:
                try:
                    char.encode(encoding)
                    safe_text.append(char)
                except (UnicodeEncodeError, UnicodeDecodeError):
                    safe_text.append("?")

            safe_args.append("".join(safe_text))

        print(*safe_args, **kwargs)
