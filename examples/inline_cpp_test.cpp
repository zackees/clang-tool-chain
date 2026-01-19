#!/usr/bin/env -S clang-tool-chain-build-run --cached
/*
 * Inline C++ Test Example
 *
 * This file demonstrates that C++ can be executed directly like a script
 * on Unix systems when clang-tool-chain is installed.
 *
 * Requirements:
 *   - Unix-like OS (Linux, macOS, WSL)
 *   - clang-tool-chain installed: pip install clang-tool-chain
 *   - OR: uv available and run from project with clang-tool-chain dependency
 *
 * Usage:
 *   chmod +x inline_cpp_test.cpp
 *   ./inline_cpp_test.cpp
 *
 * The --cached flag ensures:
 *   - First run: compiles and executes
 *   - Subsequent runs: skips compilation if source unchanged
 */
#include <iostream>
#include <cassert>
#include <vector>
#include <string>

// Example function to test
template<typename T>
T sum(const std::vector<T>& values) {
    T result = T{};
    for (const auto& v : values) {
        result += v;
    }
    return result;
}

int main() {
    std::cout << "Running inline C++ tests..." << std::endl;

    // Test 1: Integer sum
    std::vector<int> ints = {1, 2, 3, 4, 5};
    assert(sum(ints) == 15);
    std::cout << "  [PASS] Integer sum test" << std::endl;

    // Test 2: Double sum
    std::vector<double> doubles = {1.5, 2.5, 3.0};
    assert(sum(doubles) == 7.0);
    std::cout << "  [PASS] Double sum test" << std::endl;

    // Test 3: Empty vector
    std::vector<int> empty;
    assert(sum(empty) == 0);
    std::cout << "  [PASS] Empty vector test" << std::endl;

    std::cout << "\nAll tests passed!" << std::endl;
    return 0;
}
