"""
Entry point for running the downloads module as a script.

Usage:
    python -m clang_tool_chain.downloads.fetch_and_archive --platform win --arch x86_64
"""

from .fetch_and_archive import main

if __name__ == "__main__":
    main()
