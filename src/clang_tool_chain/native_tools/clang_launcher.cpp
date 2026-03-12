// clang-tool-chain native launcher
// Replaces the Python clang/clang++ wrapper with near-zero startup overhead.
// Single-file C++17, no external dependencies beyond OS APIs and standard library.
//
// Build: clang++ -O3 -std=c++17 -o ctc-clang launcher.cpp
//   Linux:   add -static-libstdc++ -static-libgcc -lpthread
//   Windows: add -static-libstdc++ -static-libgcc

#include <algorithm>
#include <atomic>
#include <cctype>
#include <chrono>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <fstream>
#include <functional>
#include <mutex>
#include <sstream>
#include <string>
#include <thread>
#include <unordered_map>
#include <vector>

#ifdef _WIN32
#define WIN32_LEAN_AND_MEAN
#define NOMINMAX
#include <direct.h>
#include <io.h>
#include <process.h>
#include <shlobj.h>
#include <windows.h>
#else
#include <dirent.h>
#include <sys/stat.h>
#include <sys/types.h>
#include <sys/wait.h>
#include <unistd.h>
#endif

// ============================================================================
// Section 0: Constants and Platform Detection
// ============================================================================

enum class Platform { Windows, Linux, Darwin };
enum class Arch { X86_64, ARM64 };
enum class CompilerMode { C, CXX };

static constexpr const char* CTC_CACHE_FILENAME = ".ctc-cache";
static constexpr const char* DONE_FILENAME = "done.txt";
static constexpr const char* CTC_TAG = "[ctc] ";

// Lightweight profiler: records named time spans, prints on request.
// Zero overhead when not used (no allocations until mark() is called).
struct Profiler {
    using Clock = std::chrono::high_resolution_clock;
    Clock::time_point start;
    struct Entry { const char* name; double us; };
    std::vector<Entry> entries;
    Clock::time_point last;
    bool active = false;

    void begin() { start = last = Clock::now(); active = true; }
    void mark(const char* name) {
        if (!active) return;
        auto now = Clock::now();
        double us = std::chrono::duration<double, std::micro>(now - last).count();
        entries.push_back({name, us});
        last = now;
    }
    void report() const {
        if (!active) return;
        double total = std::chrono::duration<double, std::micro>(
            Clock::now() - start).count();
        fprintf(stderr, "[ctc-profile] Phase breakdown:\n");
        for (const auto& e : entries) {
            fprintf(stderr, "[ctc-profile]   %-30s %7.0f us  (%4.1f%%)\n",
                    e.name, e.us, e.us / total * 100.0);
        }
        fprintf(stderr, "[ctc-profile]   %-30s %7.0f us\n", "TOTAL", total);
    }
};
static Profiler g_prof;

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

// For path construction: ~/.clang-tool-chain/clang/{platform}/{arch}/
static const char* platform_str(Platform p) {
    switch (p) {
    case Platform::Windows: return "win";
    case Platform::Linux: return "linux";
    case Platform::Darwin: return "darwin";
    }
    return "unknown";
}

// For path construction (matches Python get_platform_info)
static const char* arch_str(Arch a) {
    switch (a) {
    case Arch::X86_64: return "x86_64";
    case Arch::ARM64: return "arm64";
    }
    return "unknown";
}

// For --target= triple construction
static const char* arch_target_str(Arch a) {
    switch (a) {
    case Arch::X86_64: return "x86_64";
    case Arch::ARM64: return "aarch64";
    }
    return "unknown";
}

// Platform name for directive matching (directives use "windows" not "win")
static const char* platform_directive_str(Platform p) {
    switch (p) {
    case Platform::Windows: return "windows";
    case Platform::Linux: return "linux";
    case Platform::Darwin: return "darwin";
    }
    return "unknown";
}

// ============================================================================
// Section 1: Platform Abstraction Layer
// ============================================================================

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

static bool is_directory(const std::string& path) {
#ifdef _WIN32
    DWORD attr = GetFileAttributesA(path.c_str());
    return attr != INVALID_FILE_ATTRIBUTES && (attr & FILE_ATTRIBUTE_DIRECTORY);
#else
    struct stat st;
    return stat(path.c_str(), &st) == 0 && S_ISDIR(st.st_mode);
#endif
}

static std::vector<std::string> list_directory(const std::string& path) {
    std::vector<std::string> entries;
#ifdef _WIN32
    std::string pattern = path + "\\*";
    WIN32_FIND_DATAA fd;
    HANDLE h = FindFirstFileA(pattern.c_str(), &fd);
    if (h == INVALID_HANDLE_VALUE) return entries;
    do {
        std::string name = fd.cFileName;
        if (name != "." && name != "..") entries.push_back(name);
    } while (FindNextFileA(h, &fd));
    FindClose(h);
#else
    DIR* dir = opendir(path.c_str());
    if (!dir) return entries;
    struct dirent* ent;
    while ((ent = readdir(dir)) != nullptr) {
        std::string name = ent->d_name;
        if (name != "." && name != "..") entries.push_back(name);
    }
    closedir(dir);
#endif
    return entries;
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

static std::string get_exe_basename(const std::string& path) {
    size_t pos = path.find_last_of("/\\");
    std::string name = (pos == std::string::npos) ? path : path.substr(pos + 1);
    // Strip .exe extension
    if (name.size() > 4) {
        std::string ext = name.substr(name.size() - 4);
        for (auto& c : ext) c = (char)tolower((unsigned char)c);
        if (ext == ".exe") name = name.substr(0, name.size() - 4);
    }
    return name;
}

static std::string get_dir_name(const std::string& path) {
    size_t pos = path.find_last_of("/\\");
    if (pos == std::string::npos) return ".";
    return path.substr(0, pos);
}

static std::string get_extension(const std::string& path) {
    size_t dot = path.rfind('.');
    size_t sep = path.find_last_of("/\\");
    if (dot == std::string::npos || (sep != std::string::npos && dot < sep)) return "";
    std::string ext = path.substr(dot);
    for (auto& c : ext) c = (char)tolower((unsigned char)c);
    return ext;
}

static std::string get_env(const char* name) {
    const char* val = getenv(name);
    return val ? val : "";
}

static bool env_is_truthy(const char* name) {
    std::string val = get_env(name);
    return val == "1" || val == "true" || val == "yes";
}

// Check CLANG_TOOL_CHAIN_NO_{feature}=1 or CLANG_TOOL_CHAIN_NO_AUTO=1
static bool is_feature_disabled(const char* feature) {
    if (env_is_truthy("CLANG_TOOL_CHAIN_NO_AUTO")) return true;
    std::string env_name = std::string("CLANG_TOOL_CHAIN_NO_") + feature;
    return env_is_truthy(env_name.c_str());
}

static void set_env(const char* name, const std::string& value) {
#ifdef _WIN32
    SetEnvironmentVariableA(name, value.c_str());
    _putenv_s(name, value.c_str());
#else
    setenv(name, value.c_str(), 1);
#endif
}

// Hierarchical note suppression:
//   CLANG_TOOL_CHAIN_NO_NOTE=1           -> suppress ALL notes
//   CLANG_TOOL_CHAIN_NO_{category}_NOTE=1 -> suppress category (e.g. SANITIZER, LINKER)
//   CLANG_TOOL_CHAIN_NO_{name}_NOTE=1     -> suppress specific note
static bool is_note_suppressed(const char* name, const char* category = nullptr) {
    if (env_is_truthy("CLANG_TOOL_CHAIN_NO_NOTE")) return true;
    if (category) {
        std::string cat_env = std::string("CLANG_TOOL_CHAIN_NO_") + category + "_NOTE";
        if (env_is_truthy(cat_env.c_str())) return true;
    }
    std::string env = std::string("CLANG_TOOL_CHAIN_NO_") + name + "_NOTE";
    return env_is_truthy(env.c_str());
}

static void print_note(const char* name, const char* category, const char* message) {
    if (is_note_suppressed(name, category)) return;
    fprintf(stderr, "[clang-tool-chain] %s\n", message);
}

static std::string read_file(const std::string& path) {
    std::ifstream f(path, std::ios::binary);
    if (!f) return "";
    std::ostringstream ss;
    ss << f.rdbuf();
    return ss.str();
}

static bool write_file_atomic(const std::string& path, const std::string& content) {
    // Write to temp file, then atomic rename
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
    // Windows: MoveFileEx with REPLACE_EXISTING for atomic replace
    if (!MoveFileExA(tmp.c_str(), path.c_str(), MOVEFILE_REPLACE_EXISTING)) {
        // Fallback: delete target, then rename
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

static bool copy_file_atomic(const std::string& src, const std::string& dst) {
    std::string tmp = dst + ".tmp." + std::to_string(
#ifdef _WIN32
        (int)GetCurrentProcessId()
#else
        (int)getpid()
#endif
    );
#ifdef _WIN32
    if (!CopyFileA(src.c_str(), tmp.c_str(), FALSE)) return false;
    if (!MoveFileExA(tmp.c_str(), dst.c_str(), MOVEFILE_REPLACE_EXISTING)) {
        DeleteFileA(dst.c_str());
        if (!MoveFileA(tmp.c_str(), dst.c_str())) {
            DeleteFileA(tmp.c_str());
            return false;
        }
    }
    return true;
#else
    // Read src, write to tmp, rename
    std::ifstream in(src, std::ios::binary);
    if (!in) return false;
    std::ofstream out(tmp, std::ios::binary);
    if (!out) return false;
    out << in.rdbuf();
    if (!out) { std::remove(tmp.c_str()); return false; }
    out.close();
    in.close();
    if (rename(tmp.c_str(), dst.c_str()) != 0) {
        std::remove(tmp.c_str());
        return false;
    }
    return true;
#endif
}

// Escape newlines for single-line cache storage
static std::string escape_newlines(const std::string& s) {
    std::string out;
    out.reserve(s.size());
    for (char c : s) {
        if (c == '\n') { out += "\\n"; }
        else if (c == '\\') { out += "\\\\"; }
        else if (c != '\r') { out += c; }
    }
    return out;
}

static std::string unescape_newlines(const std::string& s) {
    std::string out;
    out.reserve(s.size());
    for (size_t i = 0; i < s.size(); i++) {
        if (s[i] == '\\' && i + 1 < s.size()) {
            if (s[i + 1] == 'n') { out += '\n'; i++; }
            else if (s[i + 1] == '\\') { out += '\\'; i++; }
            else out += s[i];
        } else {
            out += s[i];
        }
    }
    return out;
}

// Capture stdout from a command. Returns empty string on failure.
// On Windows, uses CreateProcess with pipe redirection (avoids cmd.exe quoting issues).
// On Unix, uses popen.
static std::string capture_process_stdout(const std::vector<std::string>& cmd) {
    std::string result;
#ifdef _WIN32
    // Build command line using proper Windows quoting
    std::string cmdline;
    for (size_t i = 0; i < cmd.size(); i++) {
        if (i > 0) cmdline += ' ';
        // Quote args that contain spaces or special chars
        bool needs_quote = cmd[i].find(' ') != std::string::npos ||
                           cmd[i].find('\t') != std::string::npos;
        if (needs_quote) { cmdline += '"'; cmdline += cmd[i]; cmdline += '"'; }
        else cmdline += cmd[i];
    }

    // Create pipe for stdout capture
    HANDLE read_pipe = nullptr, write_pipe = nullptr;
    SECURITY_ATTRIBUTES sa = {};
    sa.nLength = sizeof(sa);
    sa.bInheritHandle = TRUE;
    if (!CreatePipe(&read_pipe, &write_pipe, &sa, 0)) return result;
    SetHandleInformation(read_pipe, HANDLE_FLAG_INHERIT, 0);

    STARTUPINFOA si = {};
    si.cb = sizeof(si);
    si.hStdInput = GetStdHandle(STD_INPUT_HANDLE);
    si.hStdOutput = write_pipe;
    si.hStdError = GetStdHandle(STD_ERROR_HANDLE);
    si.dwFlags = STARTF_USESTDHANDLES;

    PROCESS_INFORMATION pi = {};
    std::vector<char> cmdline_buf(cmdline.begin(), cmdline.end());
    cmdline_buf.push_back('\0');

    if (!CreateProcessA(nullptr, cmdline_buf.data(), nullptr, nullptr, TRUE,
                        0, nullptr, nullptr, &si, &pi)) {
        CloseHandle(read_pipe);
        CloseHandle(write_pipe);
        return result;
    }
    CloseHandle(write_pipe);  // Close write end so reads will terminate

    // Read all stdout
    char buf[4096];
    DWORD bytes_read;
    while (ReadFile(read_pipe, buf, sizeof(buf), &bytes_read, nullptr) && bytes_read > 0) {
        result.append(buf, bytes_read);
    }
    CloseHandle(read_pipe);

    WaitForSingleObject(pi.hProcess, INFINITE);
    CloseHandle(pi.hProcess);
    CloseHandle(pi.hThread);
#else
    // Build command line for popen
    std::string cmdline;
    for (size_t i = 0; i < cmd.size(); i++) {
        if (i > 0) cmdline += ' ';
        cmdline += '\'';
        for (char c : cmd[i]) {
            if (c == '\'') cmdline += "'\\''";
            else cmdline += c;
        }
        cmdline += '\'';
    }
    FILE* pipe = popen(cmdline.c_str(), "r");
    if (!pipe) return result;
    char buf[4096];
    while (fgets(buf, sizeof(buf), pipe)) result += buf;
    pclose(pipe);
#endif
    while (!result.empty() && (result.back() == '\n' || result.back() == '\r'))
        result.pop_back();
    return result;
}

// ============================================================================
// Section 2: Cache File
// ============================================================================

struct CtcCache {
    std::string clang_root;
    std::string clang_bin;          // path to clang binary
    std::string clangpp_bin;        // path to clang++ binary
    std::string resource_dir;       // lib/clang/<version>/
    std::string resource_include;   // lib/clang/<version>/include
    std::string cxx_include;        // include/c++/v1

    // Windows-only
    std::string sysroot;            // <arch>-w64-mingw32
    std::string mingw_include;      // include/
    std::string sysroot_bin;        // <arch>-w64-mingw32/bin/ (DLL source)

    // Linux-only
    std::string sysroot_include;    // sysroot/usr/include
    std::string sysroot_multiarch;  // sysroot/usr/include/<multiarch>
    std::string libunwind_include;  // include (if libunwind.h exists)
    std::string libunwind_lib;      // lib (if libunwind exists)

    // macOS-only
    std::string macos_sdk_path;

    // Cached --version output (avoids spawning clang for version queries)
    std::string version_output;

    bool is_valid() const {
        return !clang_bin.empty() && path_exists(clang_bin);
    }
};

static CtcCache read_cache(const std::string& cache_path) {
    CtcCache cache;
    std::string content = read_file(cache_path);
    if (content.empty()) return cache;

    std::istringstream stream(content);
    std::string line;
    while (std::getline(stream, line)) {
        // Trim \r
        if (!line.empty() && line.back() == '\r') line.pop_back();
        size_t eq = line.find('=');
        if (eq == std::string::npos) continue;
        std::string key = line.substr(0, eq);
        std::string val = line.substr(eq + 1);

        if (key == "clang_root") cache.clang_root = val;
        else if (key == "clang_bin") cache.clang_bin = val;
        else if (key == "clangpp_bin") cache.clangpp_bin = val;
        else if (key == "resource_dir") cache.resource_dir = val;
        else if (key == "resource_include") cache.resource_include = val;
        else if (key == "cxx_include") cache.cxx_include = val;
        else if (key == "sysroot") cache.sysroot = val;
        else if (key == "mingw_include") cache.mingw_include = val;
        else if (key == "sysroot_bin") cache.sysroot_bin = val;
        else if (key == "sysroot_include") cache.sysroot_include = val;
        else if (key == "sysroot_multiarch") cache.sysroot_multiarch = val;
        else if (key == "libunwind_include") cache.libunwind_include = val;
        else if (key == "libunwind_lib") cache.libunwind_lib = val;
        else if (key == "macos_sdk_path") cache.macos_sdk_path = val;
        else if (key == "version_output") cache.version_output = unescape_newlines(val);
    }
    return cache;
}

static std::string discover_resource_dir(const std::string& clang_root) {
    std::string lib_clang = path_join(clang_root, "lib");
    lib_clang = path_join(lib_clang, "clang");
    if (!is_directory(lib_clang)) return "";
    auto dirs = list_directory(lib_clang);
    for (const auto& d : dirs) {
        std::string full = path_join(lib_clang, d);
        if (is_directory(full)) return full;
    }
    return "";
}

#ifdef __APPLE__
static std::string discover_macos_sdk_path() {
    // Check SDKROOT env var first
    std::string sdkroot = get_env("SDKROOT");
    if (!sdkroot.empty() && is_directory(sdkroot)) return sdkroot;

    // Run xcrun --show-sdk-path
    FILE* pipe = popen("xcrun --show-sdk-path 2>/dev/null", "r");
    if (!pipe) return "";
    char buf[1024];
    std::string result;
    while (fgets(buf, sizeof(buf), pipe)) result += buf;
    pclose(pipe);
    // Trim trailing newline
    while (!result.empty() && (result.back() == '\n' || result.back() == '\r'))
        result.pop_back();
    if (is_directory(result)) return result;
    return "";
}
#endif

static void write_cache(const CtcCache& cache, const std::string& cache_path) {
    std::ostringstream ss;
    ss << "clang_root=" << cache.clang_root << "\n";
    ss << "clang_bin=" << cache.clang_bin << "\n";
    ss << "clangpp_bin=" << cache.clangpp_bin << "\n";
    if (!cache.resource_dir.empty()) ss << "resource_dir=" << cache.resource_dir << "\n";
    if (!cache.resource_include.empty()) ss << "resource_include=" << cache.resource_include << "\n";
    if (!cache.cxx_include.empty()) ss << "cxx_include=" << cache.cxx_include << "\n";
    if (!cache.sysroot.empty()) ss << "sysroot=" << cache.sysroot << "\n";
    if (!cache.mingw_include.empty()) ss << "mingw_include=" << cache.mingw_include << "\n";
    if (!cache.sysroot_bin.empty()) ss << "sysroot_bin=" << cache.sysroot_bin << "\n";
    if (!cache.sysroot_include.empty()) ss << "sysroot_include=" << cache.sysroot_include << "\n";
    if (!cache.sysroot_multiarch.empty()) ss << "sysroot_multiarch=" << cache.sysroot_multiarch << "\n";
    if (!cache.libunwind_include.empty()) ss << "libunwind_include=" << cache.libunwind_include << "\n";
    if (!cache.libunwind_lib.empty()) ss << "libunwind_lib=" << cache.libunwind_lib << "\n";
    if (!cache.macos_sdk_path.empty()) ss << "macos_sdk_path=" << cache.macos_sdk_path << "\n";
    if (!cache.version_output.empty()) ss << "version_output=" << escape_newlines(cache.version_output) << "\n";
    write_file_atomic(cache_path, ss.str());
}

static CtcCache discover_and_write_cache(const std::string& install_dir,
                                          const std::string& cache_path,
                                          Platform platform, Arch arch) {
    CtcCache cache;
    cache.clang_root = install_dir;

    std::string bin_dir = path_join(install_dir, "bin");
#ifdef _WIN32
    cache.clang_bin = path_join(bin_dir, "clang.exe");
    cache.clangpp_bin = path_join(bin_dir, "clang++.exe");
#else
    cache.clang_bin = path_join(bin_dir, "clang");
    cache.clangpp_bin = path_join(bin_dir, "clang++");
#endif

    // Discover resource dir (lib/clang/<version>/)
    std::string res = discover_resource_dir(install_dir);
    if (!res.empty()) {
        cache.resource_dir = res;
        std::string inc = path_join(res, "include");
        if (is_directory(inc)) cache.resource_include = inc;
    }

    // C++ headers
    std::string cxx = path_join(install_dir, "include");
    cxx = path_join(cxx, "c++");
    cxx = path_join(cxx, "v1");
    if (is_directory(cxx)) cache.cxx_include = cxx;

    // Platform-specific paths
    if (platform == Platform::Windows) {
        const char* sysroot_name = (arch == Arch::X86_64) ? "x86_64-w64-mingw32" : "aarch64-w64-mingw32";
        std::string sr = path_join(install_dir, sysroot_name);
        if (is_directory(sr)) {
            cache.sysroot = sr;
            std::string sr_bin = path_join(sr, "bin");
            if (is_directory(sr_bin)) cache.sysroot_bin = sr_bin;
        }
        std::string mingw_inc = path_join(install_dir, "include");
        if (is_directory(mingw_inc)) cache.mingw_include = mingw_inc;
    } else if (platform == Platform::Linux) {
        std::string sysroot_inc = path_join(install_dir, "sysroot");
        sysroot_inc = path_join(sysroot_inc, "usr");
        sysroot_inc = path_join(sysroot_inc, "include");
        std::string marker = path_join(sysroot_inc, "stdio.h");
        if (path_exists(marker)) {
            cache.sysroot_include = sysroot_inc;
            const char* multiarch = (arch == Arch::X86_64) ? "x86_64-linux-gnu" : "aarch64-linux-gnu";
            std::string ma = path_join(sysroot_inc, multiarch);
            if (is_directory(ma)) cache.sysroot_multiarch = ma;
        }
        // Bundled libunwind
        std::string uw_header = path_join(install_dir, "include");
        uw_header = path_join(uw_header, "libunwind.h");
        if (path_exists(uw_header)) {
            cache.libunwind_include = path_join(install_dir, "include");
            cache.libunwind_lib = path_join(install_dir, "lib");
        }
    } else if (platform == Platform::Darwin) {
#ifdef __APPLE__
        cache.macos_sdk_path = discover_macos_sdk_path();
#endif
        // Bundled sysroot fallback
        std::string sysroot_inc = path_join(install_dir, "sysroot");
        sysroot_inc = path_join(sysroot_inc, "usr");
        sysroot_inc = path_join(sysroot_inc, "include");
        std::string marker = path_join(sysroot_inc, "stdio.h");
        if (path_exists(marker)) {
            cache.sysroot_include = sysroot_inc;
        }
    }

    write_cache(cache, cache_path);
    return cache;
}

// ============================================================================
// Section 3: argv[0] Dispatch
// ============================================================================

static CompilerMode detect_mode(const char* argv0) {
    std::string name = get_exe_basename(argv0);
    // Convert to lowercase for matching
    for (auto& c : name) c = (char)tolower((unsigned char)c);
    // Check for C++ indicators: "++", "c++", "cpp", "pp"
    if (name.find("++") != std::string::npos) return CompilerMode::CXX;
    if (name.find("cpp") != std::string::npos) return CompilerMode::CXX;
    return CompilerMode::C;
}

// ============================================================================
// Section 4: User Argument Parsing
// ============================================================================

struct ParsedArgs {
    bool compile_only = false;
    bool dry_run = false;
    bool no_print = false;
    bool deploy_dependencies = false;
    bool has_fsanitize_address = false;
    bool has_shared_flag = false;
    bool user_specified_target = false;
    bool user_specified_fuse_ld = false;
    bool user_specified_isysroot = false;
    bool has_nostdinc = false;
    bool has_nostdlib = false;
    bool has_ffreestanding = false;
    bool has_sysroot_flag = false;
    bool has_msvc_linker_flags = false;
    std::string output_path;
    std::string target_value;  // the --target= value (for GNU ABI detection)
    std::vector<std::string> source_files;
    std::vector<std::string> filtered_args;  // args with --deploy-dependencies removed
};

static bool str_contains(const std::string& haystack, const char* needle) {
    return haystack.find(needle) != std::string::npos;
}

static bool starts_with(const std::string& s, const char* prefix) {
    return s.compare(0, strlen(prefix), prefix) == 0;
}

static bool starts_with(const std::string& s, const std::string& prefix) {
    return s.compare(0, prefix.size(), prefix) == 0;
}

static ParsedArgs parse_user_args(int argc, char* argv[]) {
    ParsedArgs p;

    static const char* msvc_patterns[] = {
        "-Wl,/MACHINE:", "-Wl,/OUT:", "-Wl,/SUBSYSTEM:",
        "-Wl,/DEBUG", "-Wl,/PDB:", "-Wl,/NOLOGO",
        "/MACHINE:", "/OUT:", "/SUBSYSTEM:",
        "/DEBUG", "/PDB:", "/NOLOGO",
    };

    for (int i = 1; i < argc; i++) {
        std::string arg = argv[i];

        if (arg == "--deploy-dependencies") {
            p.deploy_dependencies = true;
            continue;  // Strip from filtered_args
        }
        if (arg == "--dry-run") {
            p.dry_run = true;
            continue;  // Strip from filtered_args
        }
        if (arg == "--no-print") {
            p.no_print = true;
            continue;  // Strip from filtered_args
        }

        // Detect flags
        if (arg == "-c" || arg == "-S" || arg == "-E") p.compile_only = true;
        if (arg == "-shared") p.has_shared_flag = true;
        if (str_contains(arg, "-fsanitize=address")) p.has_fsanitize_address = true;
        if (starts_with(arg, "--target=")) {
            p.user_specified_target = true;
            p.target_value = arg.substr(9);  // after "--target="
        } else if (arg == "--target" && i + 1 < argc) {
            p.user_specified_target = true;
            p.target_value = argv[i + 1];
        }
        if (starts_with(arg, "-fuse-ld=")) p.user_specified_fuse_ld = true;
        if (arg == "-isysroot") p.user_specified_isysroot = true;
        if (arg == "-nostdinc" || arg == "-nostdinc++") p.has_nostdinc = true;
        if (arg == "-nostdlib") p.has_nostdlib = true;
        if (arg == "-ffreestanding") p.has_ffreestanding = true;
        if (starts_with(arg, "--sysroot=") || arg == "--sysroot") p.has_sysroot_flag = true;

        // MSVC linker flag detection
        for (const char* pat : msvc_patterns) {
            if (str_contains(arg, pat)) {
                p.has_msvc_linker_flags = true;
                break;
            }
        }

        // Output path
        if (arg == "-o" && i + 1 < argc) {
            p.output_path = argv[i + 1];
        }

        // Source files
        std::string ext = get_extension(arg);
        if (ext == ".c" || ext == ".cpp" || ext == ".cc" || ext == ".cxx" ||
            ext == ".c++" || ext == ".m" || ext == ".mm") {
            p.source_files.push_back(arg);
        }

        p.filtered_args.push_back(arg);
    }
    return p;
}

// ============================================================================
// Section 5: Directive Parsing (threaded)
// ============================================================================

struct DirectiveResult {
    std::vector<std::string> compiler_args;
    std::vector<std::string> linker_args;
};

static std::string trim(const std::string& s) {
    size_t start = s.find_first_not_of(" \t\r\n");
    if (start == std::string::npos) return "";
    size_t end = s.find_last_not_of(" \t\r\n");
    return s.substr(start, end - start + 1);
}

static std::string to_lower(const std::string& s) {
    std::string r = s;
    for (auto& c : r) c = (char)tolower((unsigned char)c);
    return r;
}

// Parse a value that might be a list: [a, b, c] or a plain string
static std::vector<std::string> parse_directive_value(const std::string& value) {
    std::string v = trim(value);
    if (v.size() >= 2 && v.front() == '[' && v.back() == ']') {
        // List syntax
        std::string inner = v.substr(1, v.size() - 2);
        std::vector<std::string> items;
        std::istringstream ss(inner);
        std::string item;
        while (std::getline(ss, item, ',')) {
            std::string trimmed = trim(item);
            if (!trimmed.empty()) items.push_back(trimmed);
        }
        return items;
    }
    return {v};
}

static DirectiveResult parse_directives_from_file(const std::string& filepath, Platform platform) {
    DirectiveResult result;
    std::ifstream f(filepath);
    if (!f) return result;

    std::string current_platform_str = platform_directive_str(platform);

    // Track platform context: empty = global, else platform-specific
    std::string active_platform;
    bool in_platform_block = false;

    std::string line;
    while (std::getline(f, line)) {
        std::string stripped = trim(line);

        // Stop at first non-comment, non-empty line
        if (!stripped.empty() && !starts_with(stripped, "//")) break;
        if (stripped.empty()) continue;

        // Must be a comment line; check for directive
        // Find @directive: pattern
        size_t at_pos = stripped.find('@');
        if (at_pos == std::string::npos) continue;

        // Check indentation to determine platform context
        bool is_indented = (line.find("//") != std::string::npos &&
                           line.find('@') > line.find("//") + 4);

        // Extract directive name and value
        size_t colon = stripped.find(':', at_pos);
        if (colon == std::string::npos) continue;
        std::string name = to_lower(trim(stripped.substr(at_pos + 1, colon - at_pos - 1)));
        std::string value = trim(stripped.substr(colon + 1));
        // Remove trailing // comment
        size_t trail_comment = value.find("//");
        if (trail_comment != std::string::npos) {
            value = trim(value.substr(0, trail_comment));
        }

        if (name == "platform") {
            active_platform = to_lower(value);
            in_platform_block = true;
            continue;
        }

        // If not indented, reset platform context
        if (!is_indented) {
            in_platform_block = false;
            active_platform.clear();
        }

        // Check if this directive applies to current platform
        if (in_platform_block && !active_platform.empty()) {
            if (active_platform != current_platform_str) continue;
        }

        auto values = parse_directive_value(value);

        if (name == "link") {
            for (const auto& v : values) {
                if (starts_with(v, "/") || v.find(".a") != std::string::npos ||
                    v.find(".lib") != std::string::npos) {
                    result.linker_args.push_back(v);
                } else {
                    result.linker_args.push_back("-l" + v);
                }
            }
        } else if (name == "std") {
            if (!values.empty()) {
                result.compiler_args.push_back("-std=" + values[0]);
            }
        } else if (name == "cflags") {
            for (const auto& v : values) {
                // Split by spaces
                std::istringstream ss(v);
                std::string flag;
                while (ss >> flag) result.compiler_args.push_back(flag);
            }
        } else if (name == "ldflags") {
            for (const auto& v : values) {
                std::istringstream ss(v);
                std::string flag;
                while (ss >> flag) result.linker_args.push_back(flag);
            }
        } else if (name == "include") {
            for (const auto& v : values) {
                result.compiler_args.push_back("-I" + v);
            }
        }
    }
    return result;
}

static DirectiveResult parse_all_directives(const std::vector<std::string>& source_files,
                                             Platform platform) {
    DirectiveResult merged;
    for (const auto& f : source_files) {
        if (!path_exists(f)) continue;
        auto r = parse_directives_from_file(f, platform);
        merged.compiler_args.insert(merged.compiler_args.end(),
                                     r.compiler_args.begin(), r.compiler_args.end());
        merged.linker_args.insert(merged.linker_args.end(),
                                   r.linker_args.begin(), r.linker_args.end());
    }
    return merged;
}

// ============================================================================
// Section 6: Platform-Specific Flag Injection
// ============================================================================

static std::vector<std::string> build_platform_flags(
    const CtcCache& cache,
    ParsedArgs& parsed,  // non-const: may modify filtered_args (e.g. -lunwind removal)
    CompilerMode mode,
    Platform platform,
    Arch arch) {

    std::vector<std::string> flags;
    bool compile_only = parsed.compile_only;

    // --- 6.1: macOS SDK injection (priority 100) ---
    if (platform == Platform::Darwin && !is_feature_disabled("SYSROOT")) {
        if (!parsed.user_specified_isysroot && !parsed.has_nostdinc && !parsed.has_ffreestanding) {
            if (!cache.macos_sdk_path.empty()) {
                flags.push_back("-isysroot");
                flags.push_back(cache.macos_sdk_path);
            }
        }
    }

    // --- 6.2: macOS bundled sysroot fallback (priority 105) ---
    if (platform == Platform::Darwin && !is_feature_disabled("BUNDLED_SYSROOT")) {
        // Only if no -isysroot already present (either from user or from 6.1)
        bool has_isysroot = parsed.user_specified_isysroot || !cache.macos_sdk_path.empty();
        if (!has_isysroot && !parsed.has_sysroot_flag && !parsed.has_nostdinc &&
            !parsed.has_ffreestanding && !cache.sysroot_include.empty()) {
            flags.push_back("-isystem" + cache.sysroot_include);
        }
    }

    // --- 6.3: macOS -lunwind removal (priority 125) ---
    if (platform == Platform::Darwin && !is_feature_disabled("MACOS_UNWIND_FIX")) {
        auto& args = parsed.filtered_args;
        args.erase(std::remove(args.begin(), args.end(), std::string("-lunwind")), args.end());
    }

    // --- 6.4: Linux bundled sysroot (priority 140) ---
    if (platform == Platform::Linux && !is_feature_disabled("BUNDLED_SYSROOT")) {
        if (!parsed.has_sysroot_flag && !parsed.has_nostdinc && !parsed.has_ffreestanding) {
            // Add multiarch first (higher priority), then common
            if (!cache.sysroot_multiarch.empty()) {
                flags.push_back("-isystem" + cache.sysroot_multiarch);
            }
            if (!cache.sysroot_include.empty()) {
                flags.push_back("-isystem" + cache.sysroot_include);
            }
        }
    }

    // --- 6.5: Linux bundled libunwind (priority 150) ---
    if (platform == Platform::Linux && !is_feature_disabled("BUNDLED_UNWIND")) {
        if (!cache.libunwind_include.empty()) {
            flags.push_back("-I" + cache.libunwind_include);
            if (!compile_only && !cache.libunwind_lib.empty()) {
                flags.push_back("-L" + cache.libunwind_lib);
                flags.push_back("-Wl,-rpath," + cache.libunwind_lib);
            }
        }
    }

    // --- 6.6: LLD Linker (priority 200) ---
    bool should_force_lld = !compile_only &&
                            !env_is_truthy("CLANG_TOOL_CHAIN_USE_SYSTEM_LD") &&
                            !parsed.user_specified_fuse_ld &&
                            !parsed.has_msvc_linker_flags &&
                            (platform == Platform::Linux || platform == Platform::Darwin);

    if (should_force_lld) {
        flags.push_back("-fuse-ld=lld");
        print_note("LINKER_COMPAT", "LINKER",
                   "Using bundled LLD linker (suppress: CLANG_TOOL_CHAIN_USE_SYSTEM_LD=1)");

        // macOS: ensure ld64.lld symlink exists
        if (platform == Platform::Darwin) {
            std::string bin_dir = path_join(cache.clang_root, "bin");
            std::string ld64_path = path_join(bin_dir, "ld64.lld");
            if (!path_exists(ld64_path)) {
#ifndef _WIN32
                std::string lld_path = path_join(bin_dir, "lld");
                if (path_exists(lld_path)) {
                    symlink("lld", ld64_path.c_str()); // best effort
                }
#endif
            }
        }
    }

    // macOS: flag translation (also when user specified -fuse-ld=lld)
    if (platform == Platform::Darwin && !compile_only) {
        bool using_lld = should_force_lld || parsed.user_specified_fuse_ld;
        if (using_lld) {
            // Translate GNU ld flags to ld64.lld equivalents in filtered_args
            auto& args = parsed.filtered_args;
            std::vector<std::string> new_args;
            for (size_t i = 0; i < args.size(); i++) {
                const auto& arg = args[i];
                if (starts_with(arg, "-Wl,")) {
                    // Split, translate, rejoin
                    std::string payload = arg.substr(4);
                    std::vector<std::string> parts;
                    std::istringstream ss(payload);
                    std::string part;
                    while (std::getline(ss, part, ',')) parts.push_back(part);

                    std::vector<std::string> translated;
                    for (auto& f : parts) {
                        if (f == "--no-undefined") {
                            // not supported by ld64.lld, strip entirely
                        } else if (f == "--fatal-warnings") {
                            translated.push_back("-fatal_warnings");
                        } else if (f == "--allow-shlib-undefined") {
                            // removed
                        } else {
                            translated.push_back(f);
                        }
                    }
                    if (!translated.empty()) {
                        std::string joined = "-Wl,";
                        for (size_t j = 0; j < translated.size(); j++) {
                            if (j > 0) joined += ",";
                            joined += translated[j];
                        }
                        new_args.push_back(joined);
                    }
                } else if (arg == "--no-undefined") {
                    // not supported by ld64.lld, strip entirely
                } else if (arg == "--fatal-warnings") {
                    new_args.push_back("-Wl,-fatal_warnings");
                } else if (arg == "--allow-shlib-undefined") {
                    // removed
                } else {
                    new_args.push_back(arg);
                }
            }
            args = std::move(new_args);
        }
    }

    // Windows: GNU flag cleanup (when linking)
    if (platform == Platform::Windows && !compile_only && !parsed.has_msvc_linker_flags) {
        auto& args = parsed.filtered_args;
        std::vector<std::string> new_args;
        for (const auto& arg : args) {
            if (starts_with(arg, "-Wl,")) {
                std::string payload = arg.substr(4);
                std::vector<std::string> parts;
                std::istringstream ss(payload);
                std::string part;
                while (std::getline(ss, part, ',')) parts.push_back(part);

                std::vector<std::string> filtered;
                for (auto& f : parts) {
                    if (f == "--allow-shlib-undefined" ||
                        f == "--allow-multiple-definition" ||
                        f == "--no-undefined") {
                        // removed
                    } else {
                        filtered.push_back(f);
                    }
                }
                if (!filtered.empty()) {
                    std::string joined = "-Wl,";
                    for (size_t j = 0; j < filtered.size(); j++) {
                        if (j > 0) joined += ",";
                        joined += filtered[j];
                    }
                    new_args.push_back(joined);
                }
            } else if (arg == "--allow-shlib-undefined" ||
                       arg == "--allow-multiple-definition" ||
                       arg == "--no-undefined") {
                // removed
            } else {
                new_args.push_back(arg);
            }
        }
        args = std::move(new_args);
    }

    // --- 6.7: ASAN runtime injection (priority 250) ---
    if (parsed.has_fsanitize_address && !is_feature_disabled("SHARED_ASAN") &&
        (platform == Platform::Linux || platform == Platform::Windows)) {
        flags.push_back("-shared-libasan");
        print_note("SHARED_ASAN", "SANITIZER",
                   "Added -shared-libasan for AddressSanitizer (suppress: CLANG_TOOL_CHAIN_NO_SHARED_ASAN=1)");
        if (parsed.has_shared_flag && platform == Platform::Linux) {
            flags.push_back("-Wl,--allow-shlib-undefined");
            print_note("ALLOW_SHLIB_UNDEFINED", "SANITIZER",
                       "Added -Wl,--allow-shlib-undefined for shared ASAN library");
        }
    }

    // --- 6.8: RPath for --deploy-dependencies (priority 275) ---
    if (platform == Platform::Linux && parsed.deploy_dependencies &&
        !compile_only && !is_feature_disabled("RPATH")) {
        flags.push_back("-Wl,-rpath,$ORIGIN");
    }

    // --- 6.9: Windows GNU ABI (priority 300) ---
    if (platform == Platform::Windows && !parsed.has_msvc_linker_flags) {
        // Check if we should inject GNU ABI
        bool inject_gnu = true;
        if (parsed.user_specified_target) {
            // Only inject GNU flags if the user's target is a GNU/MinGW target
            std::string lower_target = to_lower(parsed.target_value);
            if (lower_target.find("-gnu") == std::string::npos &&
                lower_target.find("mingw") == std::string::npos) {
                inject_gnu = false;
            }
        }

        if (inject_gnu) {
            const char* at = arch_target_str(arch);
            if (!parsed.user_specified_target) {
                flags.push_back(std::string("--target=") + at + "-w64-windows-gnu");
            }
            if (!cache.sysroot.empty()) {
                flags.push_back("--sysroot=" + cache.sysroot);
            }
            flags.push_back("-stdlib=libc++");
            // Include paths: skip when -nostdinc or -ffreestanding (user wants no system headers)
            if (!parsed.has_nostdinc && !parsed.has_ffreestanding) {
                if (!cache.cxx_include.empty()) {
                    flags.push_back("-I" + cache.cxx_include);
                }
                // NOTE: Do NOT add -I<resource_include> or -resource-dir here.
                // Clang auto-detects resource dir from its binary location and adds
                // -internal-isystem for resource headers. Adding -I would redundantly
                // elevate them above -isystem priority. See BUG-001 in BUG.md.
                if (!cache.mingw_include.empty()) {
                    flags.push_back("-isystem" + cache.mingw_include);
                }
            }

            // Link-time only flags
            if (!compile_only) {
                flags.push_back("-rtlib=compiler-rt");
                flags.push_back("-fuse-ld=lld");
                flags.push_back("--unwindlib=libunwind");
                flags.push_back("-static-libgcc");
                flags.push_back("-static-libstdc++");
                flags.push_back("-lpthread");
            }
        }
    }

    return flags;
}

// ============================================================================
// Section 7: Final Command Assembly
// ============================================================================

static std::vector<std::string> build_final_command(
    const std::string& clang_bin,
    const std::vector<std::string>& platform_flags,
    const DirectiveResult& directives,
    const std::vector<std::string>& user_args) {

    std::vector<std::string> cmd;
    cmd.push_back(clang_bin);

    // Platform flags first (can be overridden by user)
    cmd.insert(cmd.end(), platform_flags.begin(), platform_flags.end());

    // Directive compiler args
    cmd.insert(cmd.end(), directives.compiler_args.begin(), directives.compiler_args.end());

    // User args
    cmd.insert(cmd.end(), user_args.begin(), user_args.end());

    // Directive linker args last (libraries go at end)
    cmd.insert(cmd.end(), directives.linker_args.begin(), directives.linker_args.end());

    return cmd;
}

// ============================================================================
// Section 8: Shared Library Deployment
// ============================================================================

// Run a command and capture stdout line by line
static std::vector<std::string> run_capture_lines(const std::string& cmd) {
    std::vector<std::string> lines;
#ifdef _WIN32
    FILE* pipe = _popen(cmd.c_str(), "r");
#else
    FILE* pipe = popen(cmd.c_str(), "r");
#endif
    if (!pipe) return lines;
    char buf[4096];
    while (fgets(buf, sizeof(buf), pipe)) {
        std::string line = buf;
        while (!line.empty() && (line.back() == '\n' || line.back() == '\r'))
            line.pop_back();
        if (!line.empty()) lines.push_back(line);
    }
#ifdef _WIN32
    _pclose(pipe);
#else
    pclose(pipe);
#endif
    return lines;
}

// Known system libraries that should NOT be deployed
static bool is_system_library(const std::string& name) {
    std::string lower = to_lower(name);
#ifdef _WIN32
    // Windows system DLLs
    static const char* sys_dlls[] = {
        "kernel32.dll", "ntdll.dll", "msvcrt.dll", "user32.dll",
        "advapi32.dll", "ws2_32.dll", "shell32.dll", "ole32.dll",
        "oleaut32.dll", "gdi32.dll", "comdlg32.dll", "comctl32.dll",
        "bcrypt.dll", "crypt32.dll", "ucrtbase.dll", "vcruntime",
        "api-ms-win-", "ext-ms-win-", nullptr
    };
    for (const char** p = sys_dlls; *p; p++) {
        if (str_contains(lower, *p)) return true;
    }
#else
    // Linux/macOS system libraries
    static const char* sys_libs[] = {
        "libpthread", "libdl.", "librt.", "libm.", "libc.",
        "libgcc_s.", "ld-linux", "linux-vdso", "libSystem.",
        "libobjc.", "libsystem_", "/usr/lib/", "/lib/", nullptr
    };
    for (const char** p = sys_libs; *p; p++) {
        if (str_contains(lower, *p)) return true;
    }
#endif
    return false;
}

#ifdef _WIN32
// Smart DLL deployment: use llvm-objdump to read PE imports, fall back to pattern matching
static std::vector<std::string> get_pe_imports(const std::string& objdump_path,
                                                 const std::string& exe_path) {
    std::vector<std::string> imports;
    std::string cmd = "\"" + objdump_path + "\" -p \"" + exe_path + "\" 2>nul";
    auto lines = run_capture_lines(cmd);
    for (const auto& line : lines) {
        // Look for "DLL Name: xxx.dll"
        size_t pos = line.find("DLL Name:");
        if (pos != std::string::npos) {
            std::string dll = trim(line.substr(pos + 9));
            if (!dll.empty() && !is_system_library(dll)) {
                imports.push_back(dll);
            }
        }
    }
    return imports;
}

static bool matches_dll_pattern(const std::string& name) {
    std::string lower = to_lower(name);
    // MinGW runtime patterns
    if (starts_with(lower, "libwinpthread") && get_extension(lower) == ".dll") return true;
    if (starts_with(lower, "libgcc_s_") && get_extension(lower) == ".dll") return true;
    if (starts_with(lower, "libstdc++") && get_extension(lower) == ".dll") return true;
    if (starts_with(lower, "libc++") && get_extension(lower) == ".dll") return true;
    if (starts_with(lower, "libunwind") && get_extension(lower) == ".dll") return true;
    if (starts_with(lower, "libgomp") && get_extension(lower) == ".dll") return true;
    if (starts_with(lower, "libssp") && get_extension(lower) == ".dll") return true;
    if (starts_with(lower, "libquadmath") && get_extension(lower) == ".dll") return true;
    // Sanitizer DLLs
    if (str_contains(lower, "asan_dynamic") && get_extension(lower) == ".dll") return true;
    if (str_contains(lower, "ubsan_dynamic") && get_extension(lower) == ".dll") return true;
    return false;
}

static void deploy_dlls(const CtcCache& cache, const std::string& output_path,
                         bool has_asan) {
    if (is_feature_disabled("DLL_DEPLOY") || is_feature_disabled("DEPLOY_LIBS")) return;

    std::string ext = get_extension(output_path);
    if (ext != ".exe" && ext != ".dll") return;
    if (!path_exists(output_path)) return;

    std::string output_dir = get_dir_name(output_path);
    if (output_dir.empty()) output_dir = ".";

    // Build search dirs
    std::vector<std::string> search_dirs;
    if (!cache.sysroot_bin.empty()) search_dirs.push_back(cache.sysroot_bin);
    std::string clang_bin_dir = path_join(cache.clang_root, "bin");
    if (has_asan) search_dirs.push_back(clang_bin_dir);

    // Try smart detection via llvm-objdump
    std::string objdump = path_join(clang_bin_dir, "llvm-objdump.exe");
    if (path_exists(objdump)) {
        auto imports = get_pe_imports(objdump, output_path);
        for (const auto& dll_name : imports) {
            // Find the DLL in search dirs
            for (const auto& dir : search_dirs) {
                std::string src = path_join(dir, dll_name);
                if (path_exists(src)) {
                    std::string dst = path_join(output_dir, dll_name);
                    if (!path_exists(dst)) copy_file_atomic(src, dst);
                    break;
                }
            }
        }
        return;  // objdump succeeded, skip pattern fallback
    }

    // Fallback: pattern matching
    for (const auto& dir : search_dirs) {
        auto entries = list_directory(dir);
        for (const auto& entry : entries) {
            if (!matches_dll_pattern(entry)) continue;
            std::string src = path_join(dir, entry);
            std::string dst = path_join(output_dir, entry);
            if (path_exists(dst)) continue;
            copy_file_atomic(src, dst);
        }
    }
}
#endif

// --- Linux/macOS shared library deployment ---
#ifndef _WIN32
static void deploy_shared_libs(const CtcCache& cache, const std::string& output_path,
                                bool has_asan, Platform platform) {
    if (is_feature_disabled("DEPLOY_LIBS")) return;
    if (!path_exists(output_path)) return;

    std::string output_dir = get_dir_name(output_path);
    if (output_dir.empty()) output_dir = ".";
    std::string lib_dir = path_join(cache.clang_root, "lib");

    // Determine which libraries to deploy
    // Use ldd/readelf on Linux, otool on macOS to find actual dependencies
    std::vector<std::string> needed;

    if (platform == Platform::Linux) {
        // readelf -d <exe> | grep NEEDED
        std::string cmd = "readelf -d \"" + output_path + "\" 2>/dev/null";
        auto lines = run_capture_lines(cmd);
        for (const auto& line : lines) {
            // Format: 0x0001 (NEEDED) Shared library: [libc++.so.1]
            size_t bracket = line.find('[');
            size_t bracket_end = line.find(']', bracket);
            if (bracket != std::string::npos && bracket_end != std::string::npos &&
                str_contains(line, "NEEDED")) {
                std::string lib = line.substr(bracket + 1, bracket_end - bracket - 1);
                if (!is_system_library(lib)) needed.push_back(lib);
            }
        }
    } else if (platform == Platform::Darwin) {
        // otool -L <exe>
        std::string cmd = "otool -L \"" + output_path + "\" 2>/dev/null";
        auto lines = run_capture_lines(cmd);
        for (size_t i = 1; i < lines.size(); i++) {  // skip first line (exe name)
            std::string trimmed = trim(lines[i]);
            // Format: /usr/lib/libc++.1.dylib (compatibility version ...)
            size_t space = trimmed.find(' ');
            if (space != std::string::npos) {
                std::string lib_path = trimmed.substr(0, space);
                std::string lib_name = lib_path;
                size_t slash = lib_name.find_last_of('/');
                if (slash != std::string::npos) lib_name = lib_name.substr(slash + 1);
                if (!is_system_library(lib_path)) needed.push_back(lib_name);
            }
        }
    }

    // If readelf/otool failed or returned nothing, use known patterns
    if (needed.empty()) {
        auto entries = list_directory(lib_dir);
        const char* so_ext = (platform == Platform::Darwin) ? ".dylib" : ".so";
        for (const auto& entry : entries) {
            std::string lower = to_lower(entry);
            if (starts_with(lower, "libc++") && str_contains(lower, so_ext)) {
                needed.push_back(entry);
            } else if (starts_with(lower, "libunwind") && str_contains(lower, so_ext)) {
                needed.push_back(entry);
            } else if (has_asan && str_contains(lower, "asan") && str_contains(lower, so_ext)) {
                needed.push_back(entry);
            }
        }
    }

    // Deploy each needed library
    for (const auto& lib_name : needed) {
        // Search in clang lib dir
        std::string src = path_join(lib_dir, lib_name);
        if (!path_exists(src)) {
            // Try with glob-like search for versioned .so (e.g., libc++.so.1 -> libc++.so.1.0)
            auto entries = list_directory(lib_dir);
            for (const auto& e : entries) {
                if (starts_with(e, lib_name) || starts_with(lib_name, e)) {
                    src = path_join(lib_dir, e);
                    if (path_exists(src)) break;
                }
            }
        }
        if (path_exists(src)) {
            std::string dst = path_join(output_dir, lib_name);
            if (!path_exists(dst)) {
                copy_file_atomic(src, dst);
            }
        }
    }
}
#endif

// ============================================================================
// Section 8b: Sanitizer Environment Setup
// ============================================================================

// Set up ASAN_OPTIONS, LSAN_OPTIONS, ASAN_SYMBOLIZER_PATH, and PATH (Windows)
// to ensure ASAN-instrumented executables run correctly with good stack traces.
// Only modifies env vars that are not already set (user config takes priority).
static void setup_sanitizer_environment(const CtcCache& cache, bool has_asan,
                                         [[maybe_unused]] Platform platform) {
    if (is_feature_disabled("SANITIZER_ENV")) return;
    if (!has_asan) return;

    // ASAN_OPTIONS: improve stack traces from dlopen'd shared libraries
    if (get_env("ASAN_OPTIONS").empty()) {
#ifdef _WIN32
        // LeakSanitizer is NOT supported on Windows
        set_env("ASAN_OPTIONS", "fast_unwind_on_malloc=0:symbolize=1");
#else
        set_env("ASAN_OPTIONS", "fast_unwind_on_malloc=0:symbolize=1:detect_leaks=1");
#endif
        print_note("ASAN_OPTIONS", "SANITIZER",
                   "Injected ASAN_OPTIONS for better stack traces "
                   "(suppress: CLANG_TOOL_CHAIN_NO_SANITIZER_ENV=1)");
    }

    // LSAN_OPTIONS: improve leak sanitizer stack traces
    if (get_env("LSAN_OPTIONS").empty()) {
#ifndef _WIN32
        // LSAN only supported on Linux/macOS
        set_env("LSAN_OPTIONS", "fast_unwind_on_malloc=0:symbolize=1");
#endif
    }

    // ASAN_SYMBOLIZER_PATH: point to bundled llvm-symbolizer
    if (get_env("ASAN_SYMBOLIZER_PATH").empty()) {
        std::string bin_dir = path_join(cache.clang_root, "bin");
#ifdef _WIN32
        std::string symbolizer = path_join(bin_dir, "llvm-symbolizer.exe");
#else
        std::string symbolizer = path_join(bin_dir, "llvm-symbolizer");
#endif
        if (path_exists(symbolizer)) {
            set_env("ASAN_SYMBOLIZER_PATH", symbolizer);
        }
    }

#ifdef _WIN32
    // Windows: add runtime DLL directories to PATH so ASAN DLLs are found at runtime
    std::string current_path = get_env("PATH");
    std::string prepend;
    std::string clang_bin_dir = path_join(cache.clang_root, "bin");
    if (is_directory(clang_bin_dir)) {
        prepend = clang_bin_dir;
    }
    if (!cache.sysroot_bin.empty() && is_directory(cache.sysroot_bin)) {
        if (!prepend.empty()) prepend += ";";
        prepend += cache.sysroot_bin;
    }
    if (!prepend.empty()) {
        if (!current_path.empty()) {
            set_env("PATH", prepend + ";" + current_path);
        } else {
            set_env("PATH", prepend);
        }
    }
#endif
}

// ============================================================================
// Section 9: Toolchain Not Found (Slow Path)
// ============================================================================

[[noreturn]] static void install_toolchain_and_reexec(int argc, char* argv[],
                                                       const std::string& install_dir) {
    fprintf(stderr, "%sClang toolchain not found. Installing...\n", CTC_TAG);

    // Try uv first
    int rc;
#ifdef _WIN32
    rc = _spawnlp(_P_WAIT, "uv", "uv", "run", "--with", "clang-tool-chain",
                   "clang-tool-chain", "install", "clang", nullptr);
#else
    pid_t pid = fork();
    if (pid == 0) {
        execlp("uv", "uv", "run", "--with", "clang-tool-chain",
               "clang-tool-chain", "install", "clang", nullptr);
        // If exec fails, try pip fallback
        execlp("pip", "pip", "install", "clang-tool-chain", nullptr);
        _exit(127);
    }
    int status = 0;
    waitpid(pid, &status, 0);
    rc = WIFEXITED(status) ? WEXITSTATUS(status) : 1;

    if (rc == 0) {
        // pip install succeeded but we still need to run install
        pid = fork();
        if (pid == 0) {
            execlp("clang-tool-chain", "clang-tool-chain", "install", "clang", nullptr);
            _exit(127);
        }
        waitpid(pid, &status, 0);
        rc = WIFEXITED(status) ? WEXITSTATUS(status) : 1;
    }
#endif

    // Check if installation succeeded
    std::string done = path_join(install_dir, DONE_FILENAME);
    if (path_exists(done)) {
        // Re-exec self
        fprintf(stderr, "%sToolchain installed. Resuming...\n", CTC_TAG);
#ifdef _WIN32
        _execv(argv[0], argv);
#else
        execv(argv[0], argv);
#endif
    }

    fprintf(stderr, "%sFailed to install toolchain. Run: clang-tool-chain install clang\n", CTC_TAG);
    exit(1);
}

// ============================================================================
// Section 10: Error Path Integrity Check
// ============================================================================

static void check_toolchain_integrity(const CtcCache& cache, const std::string& cache_path) {
    if (!cache.clang_bin.empty() && !path_exists(cache.clang_bin)) {
        // Delete stale cache
        std::remove(cache_path.c_str());
        fprintf(stderr, "%sToolchain binary missing. Run: clang-tool-chain install clang\n", CTC_TAG);
    }
}

// ============================================================================
// Section 11: Process Execution
// ============================================================================

#ifdef _WIN32
// Quote a single argument for Windows CreateProcess command line.
// Follows the MSVC CRT argv parsing convention:
//   - Arguments with spaces/tabs/quotes or empty args get wrapped in quotes
//   - Inside quotes: backslashes before a quote must be doubled
//   - Trailing backslashes before the closing quote must be doubled
static std::string win_quote_arg(const std::string& arg) {
    bool needs_quote = arg.empty() || arg.find(' ') != std::string::npos ||
                       arg.find('\t') != std::string::npos ||
                       arg.find('"') != std::string::npos;
    if (!needs_quote) return arg;

    std::string result = "\"";
    size_t num_backslashes = 0;
    for (size_t j = 0; j < arg.size(); j++) {
        if (arg[j] == '\\') {
            num_backslashes++;
        } else if (arg[j] == '"') {
            // Double the backslashes before a quote, then escape the quote
            result.append(num_backslashes * 2 + 1, '\\');
            result += '"';
            num_backslashes = 0;
        } else {
            // Backslashes not followed by quote are literal
            result.append(num_backslashes, '\\');
            result += arg[j];
            num_backslashes = 0;
        }
    }
    // Double trailing backslashes (they precede the closing quote)
    result.append(num_backslashes * 2, '\\');
    result += '"';
    return result;
}

static int create_process_and_wait(const std::vector<std::string>& cmd) {
    // Build command line string (Windows requires a single command line)
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

    // CreateProcess needs mutable string
    std::vector<char> cmdline_buf(cmdline.begin(), cmdline.end());
    cmdline_buf.push_back('\0');

    if (!CreateProcessA(nullptr, cmdline_buf.data(), nullptr, nullptr, TRUE,
                        0, nullptr, nullptr, &si, &pi)) {
        fprintf(stderr, "%sFailed to create process: %lu\n", CTC_TAG, GetLastError());
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

[[noreturn]] static void exec_process(const std::vector<std::string>& cmd) {
#ifdef _WIN32
    // Use CreateProcessA with explicit handle inheritance instead of _execv,
    // which can lose stdout in some Windows environments (MSYS2, etc.)
    int rc = create_process_and_wait(cmd);
    exit(rc);
#else
    std::vector<const char*> argv_ptrs;
    for (const auto& s : cmd) argv_ptrs.push_back(s.c_str());
    argv_ptrs.push_back(nullptr);
    execv(cmd[0].c_str(), const_cast<char**>(argv_ptrs.data()));
    // If exec fails
    fprintf(stderr, "%sFailed to exec: %s\n", CTC_TAG, cmd[0].c_str());
    exit(127);
#endif
}

// ============================================================================
// Section 12: main()
// ============================================================================

int main(int argc, char* argv[]) {
    bool profile = env_is_truthy("CTC_PROFILE");
    if (profile) g_prof.begin();

    bool debug = env_is_truthy("CTC_DEBUG");

    // 1. Detect mode from argv[0]
    CompilerMode mode = detect_mode(argv[0]);
    Platform platform = get_platform();
    Arch arch = get_arch();
    g_prof.mark("detect mode/platform/arch");

    if (debug) {
        fprintf(stderr, "[ctc-debug] argv[0]=%s\n", argv[0]);
        fprintf(stderr, "[ctc-debug] basename=%s\n", get_exe_basename(argv[0]).c_str());
        fprintf(stderr, "[ctc-debug] mode=%s\n", mode == CompilerMode::CXX ? "CXX" : "C");
    }

    // --ctc-help: print launcher usage (--help is passed to clang)
    for (int i = 1; i < argc; i++) {
        if (strcmp(argv[i], "--ctc-help") == 0) {
            const char* name = (mode == CompilerMode::CXX) ? "ctc-clang++" : "ctc-clang";
            printf("Usage: %s [launcher-flags] [clang-args...]\n\n", name);
            printf("Native Clang launcher — bypasses Python wrapper overhead.\n\n");
            printf("Launcher flags (consumed by the launcher, not passed to clang):\n");
            printf("  --deploy-dependencies   Deploy runtime DLLs alongside output binary\n");
            printf("  --dry-run               Print the command that would be exec'd\n");
            printf("  --ctc-help              Show this help (--help is forwarded to clang)\n\n");
            printf("Environment:\n");
            printf("  CTC_DEBUG=1             Debug output\n");
            printf("  CLANG_TOOL_CHAIN_NO_AUTO=1  Skip directive parsing, exec clang directly\n");
            return 0;
        }
    }

    // 2. Resolve install directory
    std::string home = get_home_dir();
    std::string install_dir = path_join(home, ".clang-tool-chain");
    install_dir = path_join(install_dir, "clang");
    install_dir = path_join(install_dir, platform_str(platform));
    install_dir = path_join(install_dir, arch_str(arch));
    std::string cache_path = path_join(install_dir, CTC_CACHE_FILENAME);

    // 3. Check done.txt (toolchain installed?)
    std::string done_path = path_join(install_dir, DONE_FILENAME);
    if (!path_exists(done_path)) {
        install_toolchain_and_reexec(argc, argv, install_dir);
        // Does not return
    }
    g_prof.mark("resolve dirs + done.txt check");

    // 4. Read or discover cache
    CtcCache cache = read_cache(cache_path);
    if (!cache.is_valid()) {
        cache = discover_and_write_cache(install_dir, cache_path, platform, arch);
    }
    g_prof.mark("read cache");

    // 4b. Fast path: cached --version (avoids all flag building and process spawning)
    //     Skip when CTC_DEBUG is set so full debug output is visible.
    if (argc == 2 && std::string(argv[1]) == "--version" && !cache.version_output.empty() && !debug) {
        printf("%s\n", cache.version_output.c_str());
        return 0;
    }

    // 5. Background thread: validate cache still valid
    // Capture by value to avoid use-after-free if main() returns (Windows CreateProcess path)
    std::string validator_clang_bin = cache.clang_bin;
    std::string validator_install_dir = install_dir;
    std::string validator_cache_path = cache_path;
    Platform validator_platform = platform;
    Arch validator_arch = arch;
    std::thread validator([=]() {
        if (!path_exists(validator_clang_bin)) {
            discover_and_write_cache(validator_install_dir, validator_cache_path,
                                     validator_platform, validator_arch);
        }
    });
    validator.detach();
    g_prof.mark("spawn validator thread");

    // 6. Check NO_AUTO early exit
    if (env_is_truthy("CLANG_TOOL_CHAIN_NO_AUTO")) {
        const std::string& bin = (mode == CompilerMode::CXX) ? cache.clangpp_bin : cache.clang_bin;
        std::vector<std::string> cmd;
        cmd.push_back(bin);
        bool early_dry_run = false;
        for (int i = 1; i < argc; i++) {
            if (strcmp(argv[i], "--dry-run") == 0) { early_dry_run = true; continue; }
            cmd.push_back(argv[i]);
        }
        if (early_dry_run) { print_command(cmd); return 0; }
        exec_process(cmd);
    }

    // 7. Parse user args
    ParsedArgs parsed = parse_user_args(argc, argv);
    g_prof.mark("parse user args");

    // 8. Parse directives (synchronous — thread overhead on Windows exceeds the work)
    DirectiveResult directives;
    if (!is_feature_disabled("DIRECTIVES") && !parsed.source_files.empty()) {
        directives = parse_all_directives(parsed.source_files, platform);
    }
    g_prof.mark("parse directives");

    // 9. Build platform flags
    auto platform_flags = build_platform_flags(cache, parsed, mode, platform, arch);
    g_prof.mark("build platform flags");

    // 10b. Directive verbose output
    if (env_is_truthy("CLANG_TOOL_CHAIN_DIRECTIVE_VERBOSE")) {
        if (!directives.compiler_args.empty() || !directives.linker_args.empty()) {
            fprintf(stderr, "[clang-tool-chain] Parsed directives:\n");
            for (const auto& arg : directives.compiler_args) {
                fprintf(stderr, "[clang-tool-chain]   compiler: %s\n", arg.c_str());
            }
            for (const auto& arg : directives.linker_args) {
                fprintf(stderr, "[clang-tool-chain]   linker: %s\n", arg.c_str());
            }
        }
    }

    // 11. Build final command
    const std::string& clang_bin = (mode == CompilerMode::CXX) ? cache.clangpp_bin : cache.clang_bin;

    if (debug) {
        fprintf(stderr, "[ctc-debug] cache.clang_bin=%s\n", cache.clang_bin.c_str());
        fprintf(stderr, "[ctc-debug] cache.clangpp_bin=%s\n", cache.clangpp_bin.c_str());
        fprintf(stderr, "[ctc-debug] selected clang_bin=%s\n", clang_bin.c_str());
    }

    auto cmd = build_final_command(clang_bin, platform_flags, directives, parsed.filtered_args);
    g_prof.mark("build final command");

    // 11b. Handle --dry-run / --no-print: build command but don't execute
    if (parsed.dry_run || parsed.no_print) {
        g_prof.report();
        if (parsed.dry_run) {
            for (size_t i = 0; i < cmd.size(); i++) {
                if (i > 0) printf(" ");
                bool needs_quote = false;
                for (char c : cmd[i]) {
                    if (c == ' ' || c == '\t' || c == '"' || c == '\'') { needs_quote = true; break; }
                }
                if (needs_quote) printf("\"%s\"", cmd[i].c_str());
                else printf("%s", cmd[i].c_str());
            }
            printf("\n");
        }
        return 0;
    }

    // 11c. Cache --version output on first invocation (cache miss at step 4b)
    if (argc == 2 && std::string(argv[1]) == "--version" && cache.version_output.empty()) {
        std::string ver = capture_process_stdout(cmd);
        if (!ver.empty()) {
            cache.version_output = ver;
            write_cache(cache, cache_path);
            printf("%s\n", ver.c_str());
            return 0;
        }
        // If capture failed, fall through to normal exec
    }

    // 11d. Set up sanitizer environment variables before exec
    setup_sanitizer_environment(cache, parsed.has_fsanitize_address, platform);
    g_prof.mark("sanitizer env setup");
    g_prof.report();

    // 12. Execute
#ifdef _WIN32
    bool needs_post_link = !parsed.compile_only &&
                           !parsed.output_path.empty() &&
                           (get_extension(parsed.output_path) == ".exe" ||
                            get_extension(parsed.output_path) == ".dll");

    if (needs_post_link) {
        int rc = create_process_and_wait(cmd);
        if (rc == 0 && parsed.deploy_dependencies) {
            deploy_dlls(cache, parsed.output_path, parsed.has_fsanitize_address);
        }
        if (rc != 0) {
            check_toolchain_integrity(cache, cache_path);
        }
        return rc;
    }
#else
    // Unix: if --deploy-dependencies was passed and we're linking, use fork+wait
    // so we can run deploy_shared_libs() after clang finishes
    if (parsed.deploy_dependencies && !parsed.compile_only && !parsed.output_path.empty()) {
        std::vector<const char*> argv_ptrs;
        for (const auto& s : cmd) argv_ptrs.push_back(s.c_str());
        argv_ptrs.push_back(nullptr);

        pid_t pid = fork();
        if (pid == 0) {
            // Child: exec clang
            execv(cmd[0].c_str(), const_cast<char**>(argv_ptrs.data()));
            fprintf(stderr, "%sFailed to exec: %s\n", CTC_TAG, cmd[0].c_str());
            _exit(127);
        }
        if (pid < 0) {
            fprintf(stderr, "%sFailed to fork\n", CTC_TAG);
            return 1;
        }
        int status = 0;
        waitpid(pid, &status, 0);
        int rc = WIFEXITED(status) ? WEXITSTATUS(status) : 1;
        if (rc == 0) {
            deploy_shared_libs(cache, parsed.output_path, parsed.has_fsanitize_address, platform);
        } else {
            check_toolchain_integrity(cache, cache_path);
        }
        return rc;
    }
#endif

    // Default: exec (replaces process) — compile-only, or no deploy-dependencies
    exec_process(cmd);
    // Does not return
}
