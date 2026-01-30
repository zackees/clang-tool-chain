// Simple ASAN test program
#include <iostream>
#include <vector>

int main() {
    std::vector<int> v = {1, 2, 3, 4, 5};

    // Safe access
    for (size_t i = 0; i < v.size(); i++) {
        std::cout << v[i] << " ";
    }
    std::cout << std::endl;

    std::cout << "ASAN test passed!" << std::endl;
    return 0;
}
