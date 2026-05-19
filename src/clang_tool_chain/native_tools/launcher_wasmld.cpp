// clang-tool-chain native wasm-ld launcher
// Replaces the Python wasm-ld wrapper with near-zero startup overhead.
// wasm-ld is a native binary — this launcher bypasses Python entirely.
//
// Strategy: On first run (cache miss), invoke Python ONCE to discover the
// wasm-ld binary path via the clang_tool_chain package (which handles
// downloading and installation). Cache the result. All subsequent runs
// read the cache and exec wasm-ld directly — zero Python/Node overhead.
//
// Single-file C++17. Common utilities live in ctc_common.h.
//
// Build: clang++ -O3 -std=c++17 -o ctc-wasm-ld launcher_wasmld.cpp
//   Linux:   add -static-libstdc++ -static-libgcc -lpthread
//   Windows: add -static-libstdc++ -static-libgcc

#include "ctc_common.h"

using namespace ctc;

// ============================================================================
// Section 0: Tool-specific constants
// ============================================================================

static constexpr const char* CTC_TAG = "[ctc-wasm-ld] ";
static constexpr const char* CACHE_FILENAME = ".ctc-wasmld-cache";

// ============================================================================
// Section 1: Cache (single key: wasm_ld_path)
// ============================================================================

struct WasmLdCache {
    std::string wasm_ld_path;

    bool is_valid() const {
        return !wasm_ld_path.empty() && path_exists(wasm_ld_path);
    }
};

static WasmLdCache read_cache(const std::string& cache_path) {
    WasmLdCache cache;
    std::string content = read_file(cache_path);
    if (content.empty()) return cache;
    auto kv = parse_kv_cache(content);
    auto it = kv.find("wasm_ld_path");
    if (it != kv.end()) cache.wasm_ld_path = it->second;
    return cache;
}

// ============================================================================
// Section 2: One-Shot Python Discovery
// ============================================================================

// Python one-liner: discovers wasm-ld path via clang_tool_chain.
// This triggers emscripten download/install if needed.
// Avoid f-strings — cmd.exe mangles \" inside -c "..." on Windows.
static const char* DISCOVERY_SCRIPT =
    "from clang_tool_chain.execution.emscripten import find_emscripten_wasm_ld_binary; "
    "print('wasm_ld_path=' + str(find_emscripten_wasm_ld_binary()))";

static WasmLdCache discover_via_python(const std::string& cache_path) {
    std::string python = find_python();
    if (python.empty()) {
        fprintf(stderr, "%sPython not found in PATH. Needed for one-time path discovery.\n", CTC_TAG);
        exit(1);
    }

    fprintf(stderr, "%sFirst run — discovering wasm-ld path via Python (one-time)...\n", CTC_TAG);

    std::string cmd = "\"" + python + "\" -c \"" + DISCOVERY_SCRIPT + "\"";
    std::string output = run_capture(cmd);

    if (output.empty()) {
        fprintf(stderr, "%sDiscovery failed. Is clang-tool-chain installed?\n", CTC_TAG);
        fprintf(stderr, "%sTry: pip install clang-tool-chain && clang-tool-chain install emscripten\n", CTC_TAG);
        exit(1);
    }

    WasmLdCache cache;
    auto kv = parse_kv_cache(output);
    auto it = kv.find("wasm_ld_path");
    if (it != kv.end()) cache.wasm_ld_path = it->second;

    if (cache.is_valid()) {
        write_file_atomic(cache_path, output);
        fprintf(stderr, "%sPath cached. Subsequent runs will be instant.\n", CTC_TAG);
    } else {
        fprintf(stderr, "%sDiscovery returned invalid wasm-ld path. Output:\n%s\n", CTC_TAG, output.c_str());
        exit(1);
    }

    return cache;
}

// ============================================================================
// Section 3: main()
// ============================================================================

int main(int argc, char* argv[]) {
    bool debug = env_is_truthy("CTC_DEBUG");

    Platform platform = get_platform();
    Arch arch = get_arch();

    if (debug) {
        fprintf(stderr, "[ctc-wasm-ld-debug] platform=%s arch=%s\n",
                platform_str(platform), arch_str(arch));
    }

    // --help
    bool dry_run = false;
    for (int i = 1; i < argc; i++) {
        if (strcmp(argv[i], "--help") == 0 || strcmp(argv[i], "-h") == 0) {
            printf("Usage: ctc-wasm-ld [options] [wasm-ld-args...]\n\n");
            printf("Native wasm-ld launcher — bypasses Python/Node startup overhead.\n\n");
            printf("Launcher flags:\n");
            printf("  --dry-run    Print the command that would be exec'd\n");
            printf("  --help, -h   Show this help\n\n");
            printf("All other arguments are passed directly to wasm-ld.\n");
            printf("Environment: CTC_DEBUG=1 for debug output.\n");
            return 0;
        }
        if (strcmp(argv[i], "--dry-run") == 0) {
            dry_run = true;
        }
    }

    // 1. Resolve cache path
    std::string home = get_home_dir();
    std::string install_dir = path_join(home, ".clang-tool-chain");
    install_dir = path_join(install_dir, "emscripten");
    install_dir = path_join(install_dir, platform_str(platform));
    install_dir = path_join(install_dir, arch_str(arch));
    std::string cache_path = path_join(install_dir, CACHE_FILENAME);

    // 2. Read cache or discover via Python (one-time)
    WasmLdCache cache = read_cache(cache_path);
    if (!cache.is_valid()) {
        cache = discover_via_python(cache_path);
    }

    if (debug) {
        fprintf(stderr, "[ctc-wasm-ld-debug] wasm_ld_path=%s\n", cache.wasm_ld_path.c_str());
    }

    // 3. Build command: wasm-ld [user args...]
    std::vector<std::string> cmd;
    cmd.push_back(cache.wasm_ld_path);
    for (int i = 1; i < argc; i++) {
        if (strcmp(argv[i], "--dry-run") == 0) continue;  // strip launcher flag
        cmd.push_back(argv[i]);
    }

    // 4. Exec (replaces this process — no Python, no Node, pure native)
    if (dry_run) { print_command(cmd); return 0; }
    exec_process(cmd, CTC_TAG);
}
