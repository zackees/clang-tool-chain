"""
Pytest configuration for clang-tool-chain tests.

This module ensures the toolchain is installed before running parallel tests
to avoid timeout issues when multiple processes try to download simultaneously.
"""

import pytest

from clang_tool_chain.cli import safe_print


def pytest_configure(config: pytest.Config) -> None:
    """
    Pre-install the toolchain before running any tests.

    This hook runs once at the start of the test session, BEFORE pytest-xdist
    spawns worker processes. By installing the toolchain here, we ensure:

    1. Only one download happens (in the main process)
    2. Worker processes find the toolchain already installed
    3. No parallel download race conditions
    4. No test timeouts waiting for download to complete

    This is especially important for:
    - Parallel test execution (pytest -n auto)
    - Fresh installations (CI, local development after purge)
    - Windows where file locking can cause delays
    """
    # Only install if we're the controller (not a worker)
    # pytest-xdist sets workerinput for worker processes
    if not hasattr(config, "workerinput"):
        from clang_tool_chain import installer
        from clang_tool_chain.platform.detection import get_platform_info

        print("\n" + "=" * 70)
        print("Pre-installing clang-tool-chain before running tests...")
        print("=" * 70)

        try:
            platform_name, arch = get_platform_info()

            # Check if already installed (quick check without lock)
            if installer.is_toolchain_installed(platform_name, arch):
                safe_print(f"✓ Toolchain already installed for {platform_name}/{arch}")
            else:
                print(f"Downloading toolchain for {platform_name}/{arch}...")
                print("This may take 30-60 seconds for the initial download...")

                # Ensure toolchain is installed (with locking for safety)
                installer.ensure_toolchain(platform_name, arch)

                safe_print(f"✓ Toolchain successfully installed for {platform_name}/{arch}")

            print("=" * 70 + "\n")

        except Exception as e:
            safe_print(f"✗ Failed to pre-install toolchain: {e}")
            print("Tests will attempt individual installation (may cause timeouts)")
            print("=" * 70 + "\n")
