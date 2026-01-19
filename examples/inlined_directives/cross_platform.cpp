// @std: c++17
// @platform: linux
//   @link: pthread
// @platform: windows
//   @link: ws2_32
// @platform: darwin
//   @link: pthread
//   @ldflags: -framework CoreFoundation
//
// Cross-platform example demonstrating platform-specific directives.
// The build tool selects appropriate flags based on the current platform.
//
// Usage:
//   clang-tool-chain-cpp cross_platform.cpp -o cross_platform
//   ./cross_platform

#include <cstdio>
#include <cstdlib>
#include <cstring>

#ifdef _WIN32
    #define WIN32_LEAN_AND_MEAN
    #include <windows.h>
    #include <winsock2.h>
    #pragma comment(lib, "ws2_32.lib")

    const char* get_platform_name() { return "Windows"; }

    void platform_init() {
        WSADATA wsaData;
        WSAStartup(MAKEWORD(2, 2), &wsaData);
        printf("Winsock initialized\n");
    }

    void platform_cleanup() {
        WSACleanup();
    }

    unsigned long get_thread_id() {
        return GetCurrentThreadId();
    }

#elif defined(__APPLE__)
    #include <pthread.h>
    #include <CoreFoundation/CoreFoundation.h>

    const char* get_platform_name() { return "macOS"; }

    void platform_init() {
        // CoreFoundation is automatically initialized
        printf("CoreFoundation available\n");
    }

    void platform_cleanup() {
        // Nothing to clean up
    }

    unsigned long get_thread_id() {
        return (unsigned long)pthread_self();
    }

#else  // Linux and other Unix-like
    #include <pthread.h>
    #include <unistd.h>
    #include <sys/syscall.h>

    const char* get_platform_name() { return "Linux"; }

    void platform_init() {
        printf("POSIX threads available\n");
    }

    void platform_cleanup() {
        // Nothing to clean up
    }

    unsigned long get_thread_id() {
        return (unsigned long)syscall(SYS_gettid);
    }
#endif

void print_system_info() {
    printf("=== System Information ===\n");
    printf("Platform: %s\n", get_platform_name());
    printf("Main thread ID: %lu\n", get_thread_id());
    printf("Pointer size: %zu bytes\n", sizeof(void*));
    printf("Int size: %zu bytes\n", sizeof(int));
    printf("Long size: %zu bytes\n", sizeof(long));
    printf("==========================\n");
}

int main() {
    printf("Cross-platform example with inlined build directives\n\n");

    platform_init();
    print_system_info();
    platform_cleanup();

    printf("\nProgram completed successfully!\n");
    return 0;
}
