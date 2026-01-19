// @link: pthread
// @std: c++17
//
// Simple pthread example demonstrating inlined build directives.
// This file is self-contained - the build tool reads the directives
// and automatically adds -lpthread and -std=c++17 flags.
//
// Usage:
//   clang-tool-chain-cpp pthread_hello.cpp -o pthread_hello
//   ./pthread_hello

#include <pthread.h>
#include <stdio.h>
#include <stdlib.h>

#define NUM_THREADS 4

struct ThreadData {
    int thread_id;
    const char* message;
};

void* thread_function(void* arg) {
    ThreadData* data = static_cast<ThreadData*>(arg);
    printf("Thread %d: %s\n", data->thread_id, data->message);
    return nullptr;
}

int main() {
    pthread_t threads[NUM_THREADS];
    ThreadData thread_data[NUM_THREADS];

    const char* messages[] = {
        "Hello from thread!",
        "Inlined directives work!",
        "No external build config needed!",
        "Self-contained C++ files!"
    };

    printf("Creating %d threads...\n", NUM_THREADS);

    // Create threads
    for (int i = 0; i < NUM_THREADS; i++) {
        thread_data[i].thread_id = i;
        thread_data[i].message = messages[i];
        int result = pthread_create(&threads[i], nullptr, thread_function, &thread_data[i]);
        if (result != 0) {
            fprintf(stderr, "Error creating thread %d\n", i);
            return 1;
        }
    }

    // Wait for all threads to complete
    for (int i = 0; i < NUM_THREADS; i++) {
        pthread_join(threads[i], nullptr);
    }

    printf("All threads completed!\n");
    return 0;
}
