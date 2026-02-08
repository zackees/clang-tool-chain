/*
 * cosmocc_valgrind_test.c - Test program for cosmocc + Valgrind integration.
 *
 * Compile with cosmocc:
 *   clang-tool-chain-cosmocc -g -O0 cosmocc_valgrind_test.c -o cosmocc_valgrind_test.com
 *
 * Run with Valgrind:
 *   clang-tool-chain-valgrind --track-origins=yes --error-exitcode=1 ./cosmocc_valgrind_test.com
 *
 * Expected: Valgrind detects the use of an uninitialized variable and exits with code 1.
 *
 * NOTE: Cosmocc produces statically-linked binaries with a custom malloc allocator.
 * Valgrind cannot intercept Cosmopolitan's malloc/free, so heap leak detection
 * does not work. However, Valgrind CAN detect control-flow errors like use of
 * uninitialized values, which is what this test exercises.
 */

#include <stdio.h>

int main(void) {
    /* BUG: conditional jump depends on uninitialized variable */
    int uninit;
    if (uninit > 0) {
        printf("positive\n");
    } else {
        printf("non-positive\n");
    }

    printf("cosmocc valgrind test completed\n");
    return 0;
}
