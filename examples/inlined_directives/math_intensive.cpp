// @link: [pthread, m]
// @cflags: -O2 -march=native
// @std: c++17
//
// Multi-threaded math-intensive computation example.
// Demonstrates linking against multiple libraries and compiler flags.
//
// Usage:
//   clang-tool-chain-cpp math_intensive.cpp -o math_intensive
//   ./math_intensive

#include <pthread.h>
#include <cmath>
#include <cstdio>
#include <cstdlib>
#include <vector>

#define NUM_THREADS 4
#define ELEMENTS_PER_THREAD 250000

struct WorkerData {
    int thread_id;
    double* data;
    size_t start;
    size_t end;
    double partial_sum;
};

void* compute_partial_sum(void* arg) {
    WorkerData* work = static_cast<WorkerData*>(arg);
    double sum = 0.0;

    for (size_t i = work->start; i < work->end; i++) {
        // Compute trigonometric series
        double x = work->data[i];
        sum += std::sin(x) * std::cos(x * 0.5) + std::exp(-x * 0.001);
    }

    work->partial_sum = sum;
    printf("Thread %d: computed sum = %.6f (indices %zu-%zu)\n",
           work->thread_id, sum, work->start, work->end);
    return nullptr;
}

int main() {
    const size_t total_elements = NUM_THREADS * ELEMENTS_PER_THREAD;
    std::vector<double> data(total_elements);

    // Initialize data
    printf("Initializing %zu elements...\n", total_elements);
    for (size_t i = 0; i < total_elements; i++) {
        data[i] = static_cast<double>(i) * 0.001;
    }

    pthread_t threads[NUM_THREADS];
    WorkerData workers[NUM_THREADS];

    printf("Starting %d threads for parallel computation...\n", NUM_THREADS);

    // Create worker threads
    for (int i = 0; i < NUM_THREADS; i++) {
        workers[i].thread_id = i;
        workers[i].data = data.data();
        workers[i].start = i * ELEMENTS_PER_THREAD;
        workers[i].end = (i + 1) * ELEMENTS_PER_THREAD;
        workers[i].partial_sum = 0.0;

        int result = pthread_create(&threads[i], nullptr, compute_partial_sum, &workers[i]);
        if (result != 0) {
            fprintf(stderr, "Error creating thread %d\n", i);
            return 1;
        }
    }

    // Wait for threads and sum results
    double total_sum = 0.0;
    for (int i = 0; i < NUM_THREADS; i++) {
        pthread_join(threads[i], nullptr);
        total_sum += workers[i].partial_sum;
    }

    printf("\nFinal result: %.6f\n", total_sum);
    printf("Computation completed successfully!\n");
    return 0;
}
