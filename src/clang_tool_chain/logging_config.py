"""
Centralized logging configuration for clang-tool-chain.

This module provides a single location for configuring logging across all
clang-tool-chain modules. Logging verbosity can be controlled via the
CLANG_TOOL_CHAIN_VERBOSE environment variable.

Environment Variables:
    CLANG_TOOL_CHAIN_VERBOSE: Set to '1' or 'true' to enable verbose logging (INFO level).
                              By default, only WARNING and ERROR messages are shown.

Usage:
    from clang_tool_chain.logging_config import configure_logging

    logger = configure_logging(__name__)
"""

import logging
import os
import sys


def is_verbose_enabled() -> bool:
    """
    Check if verbose logging is enabled via environment variable.

    Returns:
        True if CLANG_TOOL_CHAIN_VERBOSE is set to '1' or 'true' (case-insensitive)
    """
    verbose = os.environ.get("CLANG_TOOL_CHAIN_VERBOSE", "").lower()
    return verbose in ("1", "true", "yes")


def configure_logging(name: str) -> logging.Logger:
    """
    Configure logging for the given module name.

    This function should be called once per module to configure logging.
    It sets up a consistent format and log level across all modules.

    Args:
        name: Module name (usually __name__)

    Returns:
        Configured logger instance

    Example:
        logger = configure_logging(__name__)
        logger.info("This will only show if CLANG_TOOL_CHAIN_VERBOSE=1")
        logger.warning("This will always show")
    """
    # Determine log level based on environment variable
    log_level = logging.INFO if is_verbose_enabled() else logging.WARNING

    # Configure basic logging (only first call takes effect)
    logging.basicConfig(
        level=log_level,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=[logging.StreamHandler(sys.stderr)],
        force=True,  # Force reconfiguration if already configured
    )

    # Get and configure logger for this module
    logger = logging.getLogger(name)
    logger.setLevel(log_level)

    return logger
