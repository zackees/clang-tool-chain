// clang-tool-chain native launcher for Emscripten archive/inspection tools.
//
// One binary, four roles — dispatched by argv[0] basename:
//   ctc-emar      -> emar.py       (Emscripten archiver, wraps llvm-ar)
//   ctc-emranlib  -> emranlib.py   (Emscripten ranlib, wraps llvm-ranlib)
//   ctc-emnm      -> emnm.py       (Emscripten symbol lister, wraps llvm-nm)
//   ctc-emstrip   -> emstrip.py    (Emscripten stripper, wraps llvm-strip)
//
// Unlike emcc, these tools are thin Python wrappers around LLVM binaries and
// don't need Node.js. We still need a Python interpreter (the tool itself is
// a .py file), but we skip the clang-tool-chain *wrapper* Python entirely —
// ~1.2s saved per invocation. With ~30 archive ops in a clean FastLED WASM
// build that's ~35s of pure interpreter startup gone.
//
// Strategy: cache (python_path, emscripten_dir, config_path, bin_dir, tool_script)
// on first run via a one-shot discovery script; on subsequent runs read the
// cache, set EMSCRIPTEN/EMSCRIPTEN_ROOT/EM_CONFIG, and exec python tool.py.
//
// Single-file C++17, no external deps beyond OS APIs and the standard library.
//
// Build: clang++ -O3 -std=c++17 -o ctc-emar launcher_emtool.cpp
//   Linux:   add -static-libstdc++ -static-libgcc -lpthread
//   Windows: add -static-libstdc++ -static-libgcc

#include <cctype>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <fstream>
#include <sstream>
#include <string>
#include <vector>

#ifdef _WIN32
#define WIN32_LEAN_AND_MEAN
#define NOMINMAX
#include <direct.h>
#include <io.h>
#include <process.h>
#include <windows.h>
#else
#include <sys/stat.h>
#include <sys/types.h>
#include <sys/wait.h>
#include <unistd.h>
#endif

// ============================================================================
// Section 0: Constants
// ============================================================================

#ifdef _WIN32
static constexpr char PATH_LIST_SEP = ';';
#else
static constexpr char PATH_LIST_SEP = ':';
#endif

// ============================================================================
// Section 1: Platform Abstraction
// ============================================================================

enum class Platform { Windows, Linux, Darwin };
enum class Arch { X86_64, ARM64 };

static Platform get_platform() {
#ifdef _WIN32
    return Platform::Windows;
#elif defined(__APPLE__)
    return Platform::Darwin;
#elif defined(__linux__)
    return Platform::Linux;
#else
#error "Unsupported platform"
#endif
}

static Arch get_arch() {
#if defined(__x86_64__) || defined(_M_X64)
    return Arch::X86_64;
#elif defined(__aarch64__) || defined(_M_ARM64)
    return Arch::ARM64;
#else
#error "Unsupported architecture"
#endif
}

static const char* platform_str(Platform p) {
    switch (p) {
    case Platform::Windows: return "win";
    case Platform::Linux: return "linux";
    case Platform::Darwin: return "darwin";
    }
    return "unknown";
}

static const char* arch_str(Arch a) {
    switch (a) {
    case Arch::X86_64: return "x86_64";
    case Arch::ARM64: return "arm64";
    }
    return "unknown";
}

static char path_sep() {
#ifdef _WIN32
    return '\\';
#else
    return '/';
#endif
}

static std::string path_join(const std::string& a, const std::string& b) {
    if (a.empty()) return b;
    if (b.empty()) return a;
    char last = a.back();
    if (last == '/' || last == '\\') return a + b;
    return a + path_sep() + b;
}

static bool path_exists(const std::string& path) {
#ifdef _WIN32
    DWORD attr = GetFileAttributesA(path.c_str());
    return attr != INVALID_FILE_ATTRIBUTES;
#else
    struct stat st;
    return stat(path.c_str(), &st) == 0;
#endif
}

static std::string get_home_dir() {
#ifdef _WIN32
    const char* profile = getenv("USERPROFILE");
    if (profile && profile[0]) return profile;
    const char* homedrive = getenv("HOMEDRIVE");
    const char* homepath = getenv("HOMEPATH");
    if (homedrive && homepath) return std::string(homedrive) + homepath;
    return "C:\\Users\\Default";
#else
    const char* home = getenv("HOME");
    if (home && home[0]) return home;
    return "/tmp";
#endif
}

static std::string get_env(const char* name) {
    const char* val = getenv(name);
    return val ? val : "";
}

static bool env_is_truthy(const char* name) {
    std::string val = get_env(name);
    return val == "1" || val == "true" || val == "yes";
}

static void set_env(const char* name, const std::string& value) {
#ifdef _WIN32
    SetEnvironmentVariableA(name, value.c_str());
    _putenv_s(name, value.c_str());
#else
    setenv(name, value.c_str(), 1);
#endif
}

static std::string read_file(const std::string& path) {
    std::ifstream f(path, std::ios::binary);
    if (!f) return "";
    std::ostringstream ss;
    ss << f.rdbuf();
    return ss.str();
}

static bool write_file_atomic(const std::string& path, const std::string& content) {
    std::string tmp = path + ".tmp." + std::to_string(
#ifdef _WIN32
        (int)GetCurrentProcessId()
#else
        (int)getpid()
#endif
    );
    {
        std::ofstream f(tmp, std::ios::binary);
        if (!f) return false;
        f.write(content.data(), (std::streamsize)content.size());
        if (!f) { std::remove(tmp.c_str()); return false; }
    }
#ifdef _WIN32
    if (!MoveFileExA(tmp.c_str(), path.c_str(), MOVEFILE_REPLACE_EXISTING)) {
        DeleteFileA(path.c_str());
        if (!MoveFileA(tmp.c_str(), path.c_str())) {
            std::remove(tmp.c_str());
            return false;
        }
    }
#else
    if (rename(tmp.c_str(), path.c_str()) != 0) {
        std::remove(tmp.c_str());
        return false;
    }
#endif
    return true;
}

// ============================================================================
// Section 2: argv[0] -> tool name dispatch
// ============================================================================

static std::string get_exe_basename(const std::string& path) {
    size_t pos = path.find_last_of("/\\");
    std::string name = (pos == std::string::npos) ? path : path.substr(pos + 1);
    if (name.size() > 4) {
        std::string ext = name.substr(name.size() - 4);
        for (auto& c : ext) c = (char)tolower((unsigned char)c);
        if (ext == ".exe") name = name.substr(0, name.size() - 4);
    }
    for (auto& c : name) c = (char)tolower((unsigned char)c);
    return name;
}

// Map argv[0] basename -> Emscripten tool name (without .py).
// Recognised forms: "ctc-emar", "emar", "clang-tool-chain-emar", etc.
// Returns empty string if no tool name can be extracted.
static std::string detect_tool_name(const char* argv0) {
    std::string base = get_exe_basename(argv0);

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
    // instead of silently invoking some random "<name>.py".
    static const char* known[] = {"emar", "emranlib", "emnm", "emstrip"};
    for (const char* t : known) {
        if (base == t) return t;
    }
    return "";
}

// ============================================================================
// Section 3: Find executable in PATH
// ============================================================================

static std::string find_in_path(const char* name) {
    std::string path_env = get_env("PATH");
    if (path_env.empty()) return "";

    std::istringstream ss(path_env);
    std::string dir;
    while (std::getline(ss, dir, PATH_LIST_SEP)) {
        if (dir.empty()) continue;
        std::string candidate = path_join(dir, name);
        if (path_exists(candidate)) return candidate;
    }
    return "";
}

static std::string find_python() {
#ifdef _WIN32
    std::string p = find_in_path("python.exe");
    if (!p.empty()) return p;
    p = find_in_path("python3.exe");
    if (!p.empty()) return p;
    p = find_in_path("py.exe");
    if (!p.empty()) return p;
#else
    std::string p = find_in_path("python3");
    if (!p.empty()) return p;
    p = find_in_path("python");
    if (!p.empty()) return p;
#endif
    return "";
}

// ============================================================================
// Section 4: Path Cache (per-tool)
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
    std::istringstream stream(content);
    std::string line;
    while (std::getline(stream, line)) {
        if (!line.empty() && line.back() == '\r') line.pop_back();
        size_t eq = line.find('=');
        if (eq == std::string::npos) continue;
        std::string key = line.substr(0, eq);
        std::string val = line.substr(eq + 1);
        if (key == "python_path") c.python_path = val;
        else if (key == "emscripten_dir") c.emscripten_dir = val;
        else if (key == "config_path") c.config_path = val;
        else if (key == "bin_dir") c.bin_dir = val;
        else if (key == "tool_script") c.tool_script = val;
    }
    return c;
}

// ============================================================================
// Section 5: One-shot Python discovery
// ============================================================================

static std::string run_capture(const std::string& cmd) {
    std::string result;
#ifdef _WIN32
    // _popen goes through cmd.exe /c which strips the first and last quotes
    // if the command starts with a quote. Wrap in extra quotes so cmd.exe
    // strips the outer pair and leaves the inner quotes intact.
    std::string wrapped = "\"" + cmd + "\"";
    FILE* pipe = _popen(wrapped.c_str(), "r");
#else
    FILE* pipe = popen(cmd.c_str(), "r");
#endif
    if (!pipe) return "";
    char buf[4096];
    while (fgets(buf, sizeof(buf), pipe)) {
        result += buf;
    }
#ifdef _WIN32
    int rc = _pclose(pipe);
#else
    int rc = pclose(pipe);
#endif
    if (rc != 0) return "";
    return result;
}

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
// Section 6: Process Execution
// ============================================================================

static void print_command(const std::vector<std::string>& cmd) {
    for (size_t i = 0; i < cmd.size(); i++) {
        if (i > 0) printf(" ");
        bool needs_quote = cmd[i].find(' ') != std::string::npos ||
                           cmd[i].find('\t') != std::string::npos;
        if (needs_quote) printf("\"");
        printf("%s", cmd[i].c_str());
        if (needs_quote) printf("\"");
    }
    printf("\n");
}

#ifdef _WIN32
static std::string win_quote_arg(const std::string& arg) {
    bool needs_quote = arg.empty() || arg.find(' ') != std::string::npos ||
                       arg.find('\t') != std::string::npos ||
                       arg.find('"') != std::string::npos;
    if (!needs_quote) return arg;
    std::string result = "\"";
    size_t num_bs = 0;
    for (size_t j = 0; j < arg.size(); j++) {
        if (arg[j] == '\\') {
            num_bs++;
        } else if (arg[j] == '"') {
            result.append(num_bs * 2 + 1, '\\');
            result += '"';
            num_bs = 0;
        } else {
            result.append(num_bs, '\\');
            result += arg[j];
            num_bs = 0;
        }
    }
    result.append(num_bs * 2, '\\');
    result += '"';
    return result;
}

static int create_process_and_wait(const std::vector<std::string>& cmd,
                                    const std::string& tag) {
    std::string cmdline;
    for (size_t i = 0; i < cmd.size(); i++) {
        if (i > 0) cmdline += ' ';
        cmdline += win_quote_arg(cmd[i]);
    }
    STARTUPINFOA si = {};
    si.cb = sizeof(si);
    si.hStdInput = GetStdHandle(STD_INPUT_HANDLE);
    si.hStdOutput = GetStdHandle(STD_OUTPUT_HANDLE);
    si.hStdError = GetStdHandle(STD_ERROR_HANDLE);
    si.dwFlags = STARTF_USESTDHANDLES;
    PROCESS_INFORMATION pi = {};
    std::vector<char> buf(cmdline.begin(), cmdline.end());
    buf.push_back('\0');
    if (!CreateProcessA(nullptr, buf.data(), nullptr, nullptr, TRUE,
                        0, nullptr, nullptr, &si, &pi)) {
        fprintf(stderr, "%sFailed to create process: %lu\n", tag.c_str(), GetLastError());
        return 1;
    }
    WaitForSingleObject(pi.hProcess, INFINITE);
    DWORD exit_code = 1;
    GetExitCodeProcess(pi.hProcess, &exit_code);
    CloseHandle(pi.hProcess);
    CloseHandle(pi.hThread);
    return (int)exit_code;
}
#endif

[[noreturn]] static void exec_process(const std::vector<std::string>& cmd,
                                       const std::string& tag) {
#ifdef _WIN32
    // Use CreateProcess instead of _execv to properly inherit stdout/stderr
    // pipes (e.g. when invoked by Meson or other build systems).
    int rc = create_process_and_wait(cmd, tag);
    exit(rc);
#else
    std::vector<const char*> argv_ptrs;
    for (const auto& s : cmd) argv_ptrs.push_back(s.c_str());
    argv_ptrs.push_back(nullptr);
    execv(cmd[0].c_str(), const_cast<char**>(argv_ptrs.data()));
    fprintf(stderr, "%sFailed to exec: %s\n", tag.c_str(), cmd[0].c_str());
    exit(127);
#endif
}

// ============================================================================
// Section 7: main()
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
    exec_process(cmd, tag);
}
