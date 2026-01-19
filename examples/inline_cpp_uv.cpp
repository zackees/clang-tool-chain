#!/usr/bin/env -S uv run clang-tool-chain-build-run --cached
/*
 * Inline C++ Test via UV
 *
 * This variant uses 'uv run' to execute clang-tool-chain-build-run.
 * Useful when:
 *   - clang-tool-chain is not globally installed
 *   - Running from a project directory with pyproject.toml
 *   - uv handles the virtual environment automatically
 *
 * Requirements:
 *   - uv installed: https://docs.astral.sh/uv/
 *   - Run from a directory with pyproject.toml that includes clang-tool-chain
 *
 * Usage:
 *   chmod +x inline_cpp_uv.cpp
 *   ./inline_cpp_uv.cpp  # Must run from project root
 */
#include <iostream>

int main() {
    std::cout << "Hello from C++ executed via uv run!" << std::endl;
    std::cout << "This demonstrates the uv + clang-tool-chain integration." << std::endl;
    return 0;
}
