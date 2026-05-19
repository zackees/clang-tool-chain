// clang-tool-chain unified native launcher.
//
// One C++ source, one compiled binary, N hardlinks pointing at it. The
// ``argv[0]`` basename selects which underlying native binary to exec, AND
// which dispatch path to take:
//
//   FAST PATH — simple "look up <install_root>/bin/<name>{ext} and exec".
//   No Python interpreter, no env-var setup, no discovery cache. Used for:
//
//     linker variants (all alias the same lld.exe internally; argv[0]
//     selects ELF / Mach-O / PE/COFF flavour):
//       ctc-lld         ctc-ld.lld      ctc-ld64.lld     ctc-lld-link
//
//     archive / inspection / object manipulation (in <clang_root>/bin):
//       ctc-llvm-ar         ctc-llvm-objcopy   ctc-llvm-readobj
//       ctc-llvm-nm         ctc-llvm-objdump   ctc-llvm-strip
//       ctc-llvm-ranlib     ctc-llvm-dlltool   ctc-llvm-symbolizer
//       ctc-llvm-lib
//
//     AST query (in <clang_root>/bin):
//       ctc-clang-query
//
//     LLDB (in <lldb_root>/bin — separate install dir):
//       ctc-lldb            ctc-lldb-server
//
//   SPECIAL PATH — clang / clang++ go through the full clang_launcher
//   dispatch with ABI profile injection, sysroot detection, target
//   selection, library deployment, and the 3-tier cache. That code lives
//   in clang_launcher.cpp which is #included below with CTC_LAUNCHER_NO_MAIN
//   set so its entry point becomes ``clang_launcher_main`` instead of
//   ``main``. Names:
//       ctc-clang           ctc-clang++         ctc-clang-cpp
//
// Tools NOT handled here:
//   - emcc / em++ / emar / etc. — emscripten Python scripts handled by
//     launcher_emcc.cpp and launcher_emtool.cpp (different dispatch logic).
//   - wasm-ld — special version-matching needs against the emscripten LLVM
//     install (launcher_wasmld.cpp resolves it lazily via Python discovery).
//
// Build: clang++ -O3 -std=c++17 -o ctc-llvm-ar launcher_clang_tool.cpp
//   Linux:   add -static-libstdc++ -static-libgcc -lpthread
//   Windows: add -static-libstdc++ -static-libgcc

// Pull in clang_launcher.cpp's dispatch logic as a regular function rather
// than its own main(). The macro lets clang_launcher.cpp still build
// standalone if someone wants just that part — but TOOL_REGISTRY no longer
// invokes it standalone; this file is the entry point for everything.
#define CTC_LAUNCHER_NO_MAIN
#include "clang_launcher.cpp"  // provides clang_launcher_main + ctc_common helpers

// ``using namespace ctc;`` is already established by clang_launcher.cpp.
// CTC_TAG and get_ctc_home_dir likewise come from there — don't redefine.

// ============================================================================
// Section 1: Tool table — which install dir each name lives in
// ============================================================================

// "Install kind" — which directory under ~/.clang-tool-chain/ holds the
// binary. Each "fast path" tool below maps to one of these.
enum class InstallKind { Clang, Lldb };

struct ToolEntry {
    const char* name;       // basename of the binary (sans .exe)
    InstallKind kind;       // which install root
};

// Keep in sync with TOOL_REGISTRY entry in native_tools/__init__.py and the
// alias list compile-native materialises.
static const ToolEntry FAST_PATH_TOOLS[] = {
    // linker variants — all alias the same lld.exe internally, argv[0]
    // selects ELF (ld.lld), Mach-O (ld64.lld), or PE/COFF (lld-link) mode.
    {"lld", InstallKind::Clang},
    {"ld.lld", InstallKind::Clang},
    {"ld64.lld", InstallKind::Clang},
    {"lld-link", InstallKind::Clang},
    // archive / inspection / manipulation
    {"llvm-ar", InstallKind::Clang},
    {"llvm-nm", InstallKind::Clang},
    {"llvm-objdump", InstallKind::Clang},
    {"llvm-objcopy", InstallKind::Clang},
    {"llvm-ranlib", InstallKind::Clang},
    {"llvm-strip", InstallKind::Clang},
    {"llvm-readobj", InstallKind::Clang},
    {"llvm-dlltool", InstallKind::Clang},
    {"llvm-lib", InstallKind::Clang},
    {"llvm-symbolizer", InstallKind::Clang},
    // AST query (analysis only — no compilation)
    {"clang-query", InstallKind::Clang},
    // LLDB — separate install root under ~/.clang-tool-chain/lldb/
    {"lldb", InstallKind::Lldb},
    {"lldb-server", InstallKind::Lldb},
};

// ============================================================================
// Section 2: argv[0] -> tool name + dispatch table
// ============================================================================

// Strip optional ``ctc-`` or ``clang-tool-chain-`` prefix from a basename,
// lower-case the result, and report whether a prefix was actually stripped.
// The had_prefix bit distinguishes:
//   - ``ctc-foo`` (had_prefix=true, name=foo) — user invoked a CTC binary,
//     so an unrecognised ``foo`` is a typo that should error loudly.
//   - ``my-g++`` (had_prefix=false, name=my-g++) — user renamed the binary
//     to integrate it into a build system that detects compilers by name
//     pattern. Unknown names fall through to clang dispatch (which has its
//     own ``detect_mode`` heuristic for C vs C++).
static std::string strip_ctc_prefix(const std::string& basename, bool& had_prefix) {
    std::string base = to_lower(basename);
    had_prefix = false;
    static const char* prefixes[] = {"clang-tool-chain-", "ctc-"};
    for (const char* prefix : prefixes) {
        size_t plen = std::strlen(prefix);
        if (base.size() > plen && base.compare(0, plen, prefix) == 0) {
            base.erase(0, plen);
            had_prefix = true;
            break;
        }
    }
    return base;
}

// Returns the matching ToolEntry if argv[0] names a fast-path tool, else
// nullptr. clang/clang++/clang-cpp are NOT in this table — they're handled
// by the special path before this is consulted.
static const ToolEntry* lookup_fast_path(const std::string& tool_name) {
    for (const auto& entry : FAST_PATH_TOOLS) {
        if (tool_name == entry.name) return &entry;
    }
    return nullptr;
}

// True if argv[0] names a clang-dispatch tool (the complex ABI-profile path).
// Exact matches: ``clang`` / ``clang++`` / ``clang-cpp``.
static bool is_clang_dispatch(const std::string& tool_name) {
    return tool_name == "clang" || tool_name == "clang++" || tool_name == "clang-cpp";
}

// ============================================================================
// Section 3: Fast-path resolution — <install_root>/bin/<name>{exe_ext}
// ============================================================================

static std::string resolve_fast_path_tool(const ToolEntry& entry, Platform platform, Arch arch) {
    std::string install_dir = get_ctc_home_dir();
    const char* root_subdir = (entry.kind == InstallKind::Lldb) ? "lldb" : "clang";
    install_dir = path_join(install_dir, root_subdir);
    install_dir = path_join(install_dir, platform_str(platform));
    install_dir = path_join(install_dir, arch_str(arch));
    std::string bin_dir = path_join(install_dir, "bin");

#ifdef _WIN32
    return path_join(bin_dir, std::string(entry.name) + ".exe");
#else
    return path_join(bin_dir, entry.name);
#endif
}

// ============================================================================
// Section 4: main()
// ============================================================================

int main(int argc, char* argv[]) {
    bool debug = env_is_truthy("CTC_DEBUG");

    bool had_prefix = false;
    std::string tool_name = strip_ctc_prefix(get_exe_basename(argv[0]), had_prefix);

    if (debug) {
        fprintf(stderr, "[ctc] argv[0]=%s tool=%s had_prefix=%d\n",
                argv[0], tool_name.c_str(), had_prefix ? 1 : 0);
    }

    // ---- SPECIAL PATH: clang / clang++ / clang-cpp ----
    // Plus the legacy "rename the launcher to my-g++.exe" pattern: if argv[0]
    // had no ``ctc-`` prefix, the user renamed the binary for build-system
    // integration — hand off to clang_launcher.cpp which has its own
    // ``detect_mode`` heuristic for C vs C++ based on argv[0].
    if (is_clang_dispatch(tool_name) || !had_prefix) {
        return clang_launcher_main(argc, argv);
    }

    // ---- FAST PATH: ctc-prefixed binaries get the strict whitelist ----
    const ToolEntry* entry = lookup_fast_path(tool_name);
    if (entry == nullptr) {
        fprintf(stderr, "[ctc] Could not determine tool from argv[0]=%s\n", argv[0]);
        fprintf(stderr, "[ctc] Expected name to match one of: ctc-clang, ctc-clang++, ");
        for (size_t i = 0; i < sizeof(FAST_PATH_TOOLS) / sizeof(FAST_PATH_TOOLS[0]); i++) {
            fprintf(stderr, "%sctc-%s", i > 0 ? ", " : "", FAST_PATH_TOOLS[i].name);
        }
        fprintf(stderr, "\n");
        return 1;
    }

    std::string tag = "[ctc-" + tool_name + "] ";
    Platform platform = get_platform();
    Arch arch = get_arch();

    // --ctc-help renders launcher help; --help is forwarded to the underlying
    // tool (every LLVM tool has its own --help with its own option list).
    bool dry_run = false;
    for (int i = 1; i < argc; i++) {
        if (std::strcmp(argv[i], "--ctc-help") == 0) {
            printf("Usage: ctc-%s [launcher-flags] [%s-args...]\n\n", tool_name.c_str(), tool_name.c_str());
            printf("Native clang-tool-chain launcher — direct exec, no Python.\n\n");
            printf("Launcher flags (consumed here, not passed through):\n");
            printf("  --dry-run    Print the command that would be exec'd\n");
            printf("  --ctc-help   Show this help (use --help to forward to %s)\n\n", tool_name.c_str());
            printf("Environment:\n");
            printf("  CTC_DEBUG=1                       Debug output to stderr\n");
            printf("  CLANG_TOOL_CHAIN_DOWNLOAD_PATH    Relocate the toolchain install dir\n\n");
            printf("All other arguments are passed directly to %s.\n", tool_name.c_str());
            return 0;
        }
        if (std::strcmp(argv[i], "--dry-run") == 0) {
            dry_run = true;
        }
    }

    std::string tool_path = resolve_fast_path_tool(*entry, platform, arch);
    if (!path_exists(tool_path)) {
        const char* hint_install = (entry->kind == InstallKind::Lldb)
                                       ? "clang-tool-chain install lldb"
                                       : "clang-tool-chain install clang";
        fprintf(stderr, "%sTool binary not found: %s\n", tag.c_str(), tool_path.c_str());
        fprintf(stderr, "%sRun: %s\n", tag.c_str(), hint_install);
        fprintf(stderr,
                "%sOr set CLANG_TOOL_CHAIN_DOWNLOAD_PATH if your toolchain "
                "lives elsewhere.\n",
                tag.c_str());
        return 1;
    }

    if (debug) {
        fprintf(stderr, "%stool_path=%s\n", tag.c_str(), tool_path.c_str());
    }

    // Build argv: <tool_path> [user args...]. Strip --dry-run; everything
    // else passes through unchanged.
    std::vector<std::string> cmd;
    cmd.push_back(tool_path);
    for (int i = 1; i < argc; i++) {
        if (std::strcmp(argv[i], "--dry-run") == 0) continue;
        cmd.push_back(argv[i]);
    }

    if (dry_run) {
        print_command(cmd);
        return 0;
    }
    exec_process(cmd, tag.c_str());
}
