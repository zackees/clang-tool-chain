// valgrind_test.cpp - Test program with intentional memory errors for Valgrind
//
// This program contains several memory issues that Valgrind should detect:
// 1. Memory leak (allocated but never freed)
// 2. Use of uninitialized value
// 3. Invalid read (read after free)
//
// Compile: clang-tool-chain-cpp valgrind_test.cpp -g -O0 -o valgrind_test
// Run:     clang-tool-chain-valgrind --leak-check=full --error-exitcode=1 ./valgrind_test

#include <cstdio>
#include <cstdlib>

int main() {
    printf("Valgrind test program starting...\n");

    // Bug 1: Memory leak - allocate but never free
    int* leaked = (int*)malloc(100 * sizeof(int));
    leaked[0] = 42;
    printf("Allocated memory at %p (will be leaked)\n", (void*)leaked);

    // Bug 2: Use of uninitialized value
    int* uninit = (int*)malloc(sizeof(int));
    if (*uninit > 0) {  // Reading uninitialized memory
        printf("Uninitialized value was positive\n");
    } else {
        printf("Uninitialized value was non-positive\n");
    }
    free(uninit);

    printf("Valgrind test program finished.\n");
    // leaked is never freed - Valgrind should report this

    return 0;
}
