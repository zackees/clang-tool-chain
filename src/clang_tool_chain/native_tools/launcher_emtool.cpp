// clang-tool-chain native launcher for Emscripten Python-script tools.
//
// One binary, 17 roles — dispatched by argv[0] basename. The same compiled
// .exe is hardlinked (or copied on systems without hardlinks) under each of
// these names; argv[0] selects which underlying emscripten Python script to
// drive:
//
//   archive / inspection
//     ctc-emar       -> emar.py        (Emscripten archiver, wraps llvm-ar)
//     ctc-emranlib   -> emranlib.py    (Emscripten ranlib, wraps llvm-ranlib)
//     ctc-emnm       -> tools/emnm.py  (Emscripten symbol lister, wraps llvm-nm)
//     ctc-emstrip    -> emstrip.py     (Emscripten stripper, wraps llvm-strip)
//     ctc-emsize     -> emsize.py      (Emscripten size analyser, wraps llvm-size)
//     ctc-emsymbolizer -> tools/emsymbolizer.py (WASM stack-trace symbolizer)
//     ctc-emdwp      -> tools/emdwp.py (DWARF packaging tool)
//     ctc-emcoverage -> tools/emcoverage.py
//     ctc-emprofile  -> tools/emprofile.py
//
//   build orchestration (driver wrappers)
//     ctc-emcmake    -> emcmake.py     (cmake driver)
//     ctc-emmake     -> emmake.py      (make driver)
//     ctc-emconfigure-> emconfigure.py (./configure driver)
//     ctc-emscons    -> emscons.py     (SCons driver)
//     ctc-embuilder  -> embuilder.py   (system library builder)
//
//   misc
//     ctc-em-config  -> em-config.py   (config query tool)
//     ctc-emrun      -> emrun.py       (HTML/WASM browser launcher)
//     ctc-emscan-deps-> emscan-deps.py (dependency scanner)
//
// Unlike emcc, none of these tools run JS, so we skip the Node.js setup that
// `execute_emscripten_tool` would otherwise do. We still need a Python
// interpreter (the tool itself is a .py file), but we skip the clang-tool-chain
// *wrapper* Python entirely — ~1.2s saved per invocation.
//
// Strategy: cache (python_path, emscripten_dir, config_path, bin_dir, tool_script)
// on first run via a one-shot discovery script; on subsequent runs read the
// cache, set EMSCRIPTEN/EMSCRIPTEN_ROOT/EM_CONFIG, and exec python tool.py.
//
// Single-file C++17. Common utilities live in ctc_common.h.
//
// Build: clang++ -O3 -std=c++17 -o ctc-emar launcher_emtool.cpp
//   Linux:   add -static-libstdc++ -static-libgcc -lpthread
//   Windows: add -static-libstdc++ -static-libgcc

#include "ctc_common.h"

using namespace ctc;

// ============================================================================
// Section 1: argv[0] -> tool name dispatch
// ============================================================================

// Map argv[0] basename -> Emscripten tool name (without .py).
// Recognised forms: "ctc-emar", "emar", "clang-tool-chain-emar", etc.
// Returns empty string if no tool name can be extracted.
static std::string detect_tool_name(const char* argv0) {
    std::string base = to_lower(get_exe_basename(argv0));

    // Strip optional "ctc-" or "clang-tool-chain-" prefix.
    static const char* prefixes[] = {"clang-tool-chain-", "ctc-"};
    for (const char* prefix : prefixes) {
        size_t plen = strlen(prefix);
        if (base.size() > plen && base.compare(0, plen, prefix) == 0) {
            base.erase(0, plen);
            break;
        }
    }

    // Whitelist known tool names so a typo / unknown rename fails loudly
    // instead of silently invoking some random "<name>.py". Keep in sync
    // with TOOL_REGISTRY entry in native_tools/__init__.py and the
    // [project.scripts] block in pyproject.toml.
    static const char* known[] = {
        // archive / inspection
        "emar", "emranlib", "emnm", "emstrip",
        "emsize", "emsymbolizer", "emdwp", "emcoverage", "emprofile",
        // build orchestration
        "emcmake", "emmake", "emconfigure", "emscons", "embuilder",
        // misc
        "em-config", "emrun", "emscan-deps",
    };
    for (const char* t : known) {
        if (base == t) return t;
    }
    return "";
}

// ============================================================================
// Section 2: Path Cache (per-tool)
// ============================================================================

struct PathsCache {
    std::string python_path;
    std::string emscripten_dir;   // .../emscripten/{platform}/{arch}/emscripten
    std::string config_path;      // .../emscripten/{platform}/{arch}/.emscripten
    std::string bin_dir;          // .../emscripten/{platform}/{arch}/bin
    std::string tool_script;      // .../emscripten/{tool}.py

    bool is_valid() const {
        return !python_path.empty() && !tool_script.empty() &&
               path_exists(python_path) && path_exists(tool_script);
    }
};

static PathsCache parse_paths_cache(const std::string& content) {
    PathsCache c;
    auto kv = parse_kv_cache(content);
    auto get = [&](const char* k) -> std::string {
        auto it = kv.find(k);
        return it == kv.end() ? "" : it->second;
    };
    c.python_path = get("python_path");
    c.emscripten_dir = get("emscripten_dir");
    c.config_path = get("config_path");
    c.bin_dir = get("bin_dir");
    c.tool_script = get("tool_script");
    return c;
}

// ============================================================================
// Section 3: One-shot Python discovery
// ============================================================================

// Discovery script: avoid \" inside -c "..." — cmd.exe mangles it on Windows.
// Builds the script by string concatenation in C++ so the tool name is baked
// in literally rather than coming from a Python variable.
static std::string build_discovery_script(const std::string& tool_name) {
    std::string s;
    s += "import sys; ";
    s += "from pathlib import Path; ";
    s += "from clang_tool_chain.execution.emscripten import find_emscripten_tool, get_platform_info; ";
    s += "pn, ar = get_platform_info(); ";
    s += "d = Path.home() / '.clang-tool-chain' / 'emscripten' / pn / ar; ";
    s += "tool = find_emscripten_tool('" + tool_name + "'); ";
    s += "print('python_path=' + sys.executable); ";
    s += "print('emscripten_dir=' + str(d / 'emscripten')); ";
    s += "print('config_path=' + str(d / '.emscripten')); ";
    s += "print('bin_dir=' + str(d / 'bin')); ";
    s += "print('tool_script=' + str(tool))";
    return s;
}

static PathsCache discover_via_python(const std::string& cache_path,
                                      const std::string& tool_name,
                                      const std::string& tag) {
    std::string python = find_python();
    if (python.empty()) {
        fprintf(stderr, "%sPython not found in PATH. Needed for one-time path discovery.\n",
                tag.c_str());
        exit(1);
    }

    fprintf(stderr, "%sFirst run — discovering Emscripten paths via Python (one-time)...\n",
            tag.c_str());

    std::string script = build_discovery_script(tool_name);
    std::string cmd = "\"" + python + "\" -c \"" + script + "\"";
    std::string output = run_capture(cmd);

    if (output.empty()) {
        fprintf(stderr, "%sDiscovery failed. Is clang-tool-chain installed?\n", tag.c_str());
        fprintf(stderr, "%sTry: pip install clang-tool-chain && "
                        "clang-tool-chain install emscripten\n", tag.c_str());
        exit(1);
    }

    PathsCache cache = parse_paths_cache(output);
    if (!cache.is_valid()) {
        fprintf(stderr, "%sDiscovery returned incomplete paths. Output:\n%s\n",
                tag.c_str(), output.c_str());
        exit(1);
    }
    write_file_atomic(cache_path, output);
    fprintf(stderr, "%sPaths cached. Subsequent runs will be instant.\n", tag.c_str());
    return cache;
}

// ============================================================================
// Section 4: main()
// ============================================================================

int main(int argc, char* argv[]) {
    bool debug = env_is_truthy("CTC_DEBUG");

    // Dispatch tool by argv[0] basename.
    std::string tool_name = detect_tool_name(argv[0]);
    if (tool_name.empty()) {
        fprintf(stderr, "[ctc-emtool] Could not determine tool from argv[0]=%s\n", argv[0]);
        fprintf(stderr, "[ctc-emtool] Expected name to match one of: "
                        "ctc-emar, ctc-emranlib, ctc-emnm, ctc-emstrip\n");
        return 1;
    }

    std::string tag = "[ctc-" + tool_name + "] ";
    std::string cache_filename = ".ctc-" + tool_name + "-cache";

    Platform platform = get_platform();
    Arch arch = get_arch();

    if (debug) {
        fprintf(stderr, "%sargv[0]=%s tool=%s platform=%s/%s\n",
                tag.c_str(), argv[0], tool_name.c_str(),
                platform_str(platform), arch_str(arch));
    }

    // Parse launcher flags (--help / --dry-run). All other args go through.
    bool dry_run = false;
    for (int i = 1; i < argc; i++) {
        if (strcmp(argv[i], "--help") == 0 || strcmp(argv[i], "-h") == 0) {
            // emar/emranlib/emnm/emstrip all accept -h themselves with their own
            // meanings (e.g. emar -h is a posix archive flag). Use --ctc-help to
            // request the launcher's help instead.
            // Plain --help / -h is forwarded to the underlying tool.
            continue;
        }
        if (strcmp(argv[i], "--ctc-help") == 0) {
            printf("Usage: ctc-%s [launcher-flags] [%s-args...]\n\n",
                   tool_name.c_str(), tool_name.c_str());
            printf("Native Emscripten %s launcher — bypasses clang-tool-chain wrapper.\n\n",
                   tool_name.c_str());
            printf("Launcher flags (consumed by the launcher, not passed through):\n");
            printf("  --dry-run    Print the command that would be exec'd\n");
            printf("  --ctc-help   Show this help (use --help to forward to %s)\n\n",
                   tool_name.c_str());
            printf("All other arguments are passed directly to %s.\n", tool_name.c_str());
            printf("Environment: CTC_DEBUG=1 for debug output.\n");
            return 0;
        }
        if (strcmp(argv[i], "--dry-run") == 0) {
            dry_run = true;
        }
    }

    // Resolve cache path
    std::string home = get_home_dir();
    std::string install_dir = path_join(home, ".clang-tool-chain");
    install_dir = path_join(install_dir, "emscripten");
    install_dir = path_join(install_dir, platform_str(platform));
    install_dir = path_join(install_dir, arch_str(arch));
    std::string cache_path = path_join(install_dir, cache_filename);

    // Read cache or run one-shot Python discovery
    PathsCache cache = parse_paths_cache(read_file(cache_path));
    if (!cache.is_valid()) {
        cache = discover_via_python(cache_path, tool_name, tag);
    }

    if (debug) {
        fprintf(stderr, "%spython=%s\n", tag.c_str(), cache.python_path.c_str());
        fprintf(stderr, "%stool_script=%s\n", tag.c_str(), cache.tool_script.c_str());
        fprintf(stderr, "%semscripten_dir=%s\n", tag.c_str(), cache.emscripten_dir.c_str());
    }

    // Set up Emscripten environment for the child process. emar/emranlib/emnm/
    // emstrip all read EM_CONFIG to locate LLVM_ROOT — without it they fall
    // back to scanning PATH, which is brittle.
    set_env("EMSCRIPTEN", cache.emscripten_dir);
    set_env("EMSCRIPTEN_ROOT", cache.emscripten_dir);
    set_env("EM_CONFIG", cache.config_path);

    // Prepend emscripten bin/ to PATH so the underlying llvm-ar/llvm-ranlib/etc
    // are found by the python wrapper without needing user PATH setup.
    if (!cache.bin_dir.empty()) {
        std::string old_path = get_env("PATH");
        std::string new_path = cache.bin_dir;
        if (!old_path.empty()) {
            new_path += PATH_LIST_SEP;
            new_path += old_path;
        }
        set_env("PATH", new_path);
    }

    // Build command: python tool.py [user args...]
    std::vector<std::string> cmd;
    cmd.push_back(cache.python_path);
    cmd.push_back(cache.tool_script);
    for (int i = 1; i < argc; i++) {
        if (strcmp(argv[i], "--dry-run") == 0) continue;  // strip launcher flag
        cmd.push_back(argv[i]);
    }

    if (dry_run) { print_command(cmd); return 0; }
    exec_process(cmd, tag.c_str());
}
