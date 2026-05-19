// clang-tool-chain shared launcher utilities.
//
// Header-only library used by every ctc-* native launcher. Each .cpp file is
// compiled as its own translation unit and produces its own executable, so
// `static inline` is enough — there is no shared link step to worry about
// duplicate symbols.
//
// What belongs here: code that is verbatim-duplicated across multiple
// launchers (platform detection, path joining, env helpers, process exec,
// cache parsing, shell tokenisation).
//
// What does NOT belong here: tool-specific state (cache structs, mode enums,
// CTC_TAG strings, profilers). Those stay local to their launcher.
//
// Build: launchers include this header directly. No separate translation
// unit, no linkage flags.

#ifndef CTC_COMMON_H
#define CTC_COMMON_H

#include <cctype>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <fstream>
#include <sstream>
#include <string>
#include <unordered_map>
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

#ifdef __APPLE__
#include <mach-o/dyld.h>
#endif

namespace ctc {

// ============================================================================
// Section 1: Constants
// ============================================================================

#ifdef _WIN32
static constexpr char PATH_LIST_SEP = ';';
#else
static constexpr char PATH_LIST_SEP = ':';
#endif

// ============================================================================
// Section 2: Platform / Architecture Detection
// ============================================================================

enum class Platform { Windows, Linux, Darwin };
enum class Arch { X86_64, ARM64 };

static inline Platform get_platform() {
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

static inline Arch get_arch() {
#if defined(__x86_64__) || defined(_M_X64)
    return Arch::X86_64;
#elif defined(__aarch64__) || defined(_M_ARM64)
    return Arch::ARM64;
#else
#error "Unsupported architecture"
#endif
}

static inline const char* platform_str(Platform p) {
    switch (p) {
    case Platform::Windows: return "win";
    case Platform::Linux:   return "linux";
    case Platform::Darwin:  return "darwin";
    }
    return "unknown";
}

static inline const char* arch_str(Arch a) {
    switch (a) {
    case Arch::X86_64: return "x86_64";
    case Arch::ARM64:  return "arm64";
    }
    return "unknown";
}

// ============================================================================
// Section 3: Path Utilities
// ============================================================================

static inline char path_sep() {
#ifdef _WIN32
    return '\\';
#else
    return '/';
#endif
}

static inline std::string path_join(const std::string& a, const std::string& b) {
    if (a.empty()) return b;
    if (b.empty()) return a;
    char last = a.back();
    if (last == '/' || last == '\\') return a + b;
    return a + path_sep() + b;
}

static inline bool path_exists(const std::string& path) {
#ifdef _WIN32
    DWORD attr = GetFileAttributesA(path.c_str());
    return attr != INVALID_FILE_ATTRIBUTES;
#else
    struct stat st;
    return stat(path.c_str(), &st) == 0;
#endif
}

static inline bool is_directory(const std::string& path) {
#ifdef _WIN32
    DWORD attr = GetFileAttributesA(path.c_str());
    return attr != INVALID_FILE_ATTRIBUTES && (attr & FILE_ATTRIBUTE_DIRECTORY);
#else
    struct stat st;
    return stat(path.c_str(), &st) == 0 && S_ISDIR(st.st_mode);
#endif
}

static inline void make_directory(const std::string& path) {
#ifdef _WIN32
    CreateDirectoryA(path.c_str(), nullptr);
#else
    mkdir(path.c_str(), 0755);
#endif
}

static inline std::string get_home_dir() {
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

// Strip directory + optional .exe suffix and lower-case the result.
static inline std::string get_exe_basename(const std::string& path) {
    size_t pos = path.find_last_of("/\\");
    std::string name = (pos == std::string::npos) ? path : path.substr(pos + 1);
    if (name.size() > 4) {
        std::string ext = name.substr(name.size() - 4);
        for (auto& c : ext) c = (char)tolower((unsigned char)c);
        if (ext == ".exe") name = name.substr(0, name.size() - 4);
    }
    return name;
}

static inline std::string get_extension(const std::string& path) {
    size_t dot = path.rfind('.');
    size_t sep = path.find_last_of("/\\");
    if (dot == std::string::npos || (sep != std::string::npos && dot < sep)) return "";
    std::string ext = path.substr(dot);
    for (auto& c : ext) c = (char)tolower((unsigned char)c);
    return ext;
}

// Directory containing the running executable, or empty on failure.
// Used to find sibling binaries without scanning PATH.
static inline std::string get_exe_dir() {
#ifdef _WIN32
    char buf[MAX_PATH * 2];
    DWORD n = GetModuleFileNameA(NULL, buf, (DWORD)sizeof(buf));
    if (n == 0 || n >= sizeof(buf)) return "";
    std::string p(buf, n);
#elif defined(__APPLE__)
    char buf[4096];
    uint32_t size = sizeof(buf);
    if (_NSGetExecutablePath(buf, &size) != 0) return "";
    std::string p(buf);
#elif defined(__linux__)
    char buf[4096];
    ssize_t n = readlink("/proc/self/exe", buf, sizeof(buf) - 1);
    if (n <= 0) return "";
    buf[n] = 0;
    std::string p(buf);
#else
    return "";
#endif
    size_t sep = p.find_last_of("/\\");
    return (sep == std::string::npos) ? "" : p.substr(0, sep);
}

// ============================================================================
// Section 4: String Helpers
// ============================================================================

static inline std::string to_lower(const std::string& s) {
    std::string r = s;
    for (auto& c : r) c = (char)tolower((unsigned char)c);
    return r;
}

static inline bool starts_with(const std::string& s, const char* prefix) {
    return s.compare(0, std::strlen(prefix), prefix) == 0;
}

// ============================================================================
// Section 5: Environment Helpers
// ============================================================================

static inline std::string get_env(const char* name) {
    const char* val = getenv(name);
    return val ? val : "";
}

static inline bool env_is_truthy(const char* name) {
    std::string val = get_env(name);
    return val == "1" || val == "true" || val == "yes";
}

static inline void set_env(const char* name, const std::string& value) {
#ifdef _WIN32
    SetEnvironmentVariableA(name, value.c_str());
    _putenv_s(name, value.c_str());
#else
    setenv(name, value.c_str(), 1);
#endif
}

static inline void unset_env(const char* name) {
#ifdef _WIN32
    SetEnvironmentVariableA(name, nullptr);
    std::string s = std::string(name) + "=";
    _putenv(s.c_str());
#else
    unsetenv(name);
#endif
}

// ============================================================================
// Section 6: File I/O
// ============================================================================

static inline std::string read_file(const std::string& path) {
    std::ifstream f(path, std::ios::binary);
    if (!f) return "";
    std::ostringstream ss;
    ss << f.rdbuf();
    return ss.str();
}

// Write content to path via a uniquely-named tmp file + atomic rename.
// Returns false on any I/O error.
static inline bool write_file_atomic(const std::string& path, const std::string& content) {
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
// Section 7: PATH lookup
// ============================================================================

static inline std::string find_in_path(const char* name) {
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

static inline std::string find_python() {
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
// Section 8: Cache (key=value\n) Parser
// ============================================================================

// Parse a key=value file format used by every launcher's discovery cache.
// Lines without '=' are skipped. Trailing \r is stripped. Caller can read
// fields they care about with std::unordered_map::find / count.
static inline std::unordered_map<std::string, std::string>
parse_kv_cache(const std::string& content) {
    std::unordered_map<std::string, std::string> out;
    std::istringstream stream(content);
    std::string line;
    while (std::getline(stream, line)) {
        if (!line.empty() && line.back() == '\r') line.pop_back();
        size_t eq = line.find('=');
        if (eq == std::string::npos) continue;
        out.emplace(line.substr(0, eq), line.substr(eq + 1));
    }
    return out;
}

// ============================================================================
// Section 9: Shell-style Tokenizer + JSON Array Parser
// ============================================================================

// Tokenize a single shell-style command line. Handles single/double quotes,
// backslash escapes (Unix; Windows preserves backslashes in paths as POSIX
// shells don't but cmd does — see explicit guard below).
static inline std::vector<std::string> split_shell(const std::string& line) {
    std::vector<std::string> tokens;
    std::string current;
    bool in_single = false, in_double = false, escape = false;
    for (size_t i = 0; i < line.size(); i++) {
        char c = line[i];
        if (escape) { current += c; escape = false; continue; }
#ifdef _WIN32
        // On Windows, backslash is a path separator, not an escape character.
        // Only treat \ as escape when followed by a quote or another backslash
        // inside a double-quoted string.
        if (c == '\\' && !in_single && in_double && i + 1 < line.size()) {
            char next = line[i + 1];
            if (next == '"' || next == '\\') { escape = true; continue; }
        }
#else
        if (c == '\\' && !in_single) { escape = true; continue; }
#endif
        if (c == '\'' && !in_double) { in_single = !in_single; continue; }
        if (c == '"' && !in_single) { in_double = !in_double; continue; }
        if ((c == ' ' || c == '\t') && !in_single && !in_double) {
            if (!current.empty()) { tokens.push_back(current); current.clear(); }
            continue;
        }
        current += c;
    }
    if (!current.empty()) tokens.push_back(current);
    return tokens;
}

// Minimal JSON string-array parser: ["arg1", "arg2", ...]. Handles \" \\ \/ \n \t escapes.
// Anything fancier (numbers, nested objects) is out of scope.
static inline std::vector<std::string> parse_json_array(const std::string& content) {
    std::vector<std::string> result;
    size_t pos = content.find('[');
    if (pos == std::string::npos) return result;
    pos++;

    while (pos < content.size()) {
        while (pos < content.size() && (content[pos] == ' ' || content[pos] == '\t' ||
               content[pos] == '\n' || content[pos] == '\r' || content[pos] == ',')) {
            pos++;
        }
        if (pos >= content.size() || content[pos] == ']') break;

        if (content[pos] != '"') { pos++; continue; }
        pos++;

        std::string s;
        while (pos < content.size() && content[pos] != '"') {
            if (content[pos] == '\\' && pos + 1 < content.size()) {
                char next = content[pos + 1];
                if (next == '"' || next == '\\' || next == '/') { s += next; pos += 2; }
                else if (next == 'n') { s += '\n'; pos += 2; }
                else if (next == 't') { s += '\t'; pos += 2; }
                else { s += content[pos]; pos++; }
            } else {
                s += content[pos]; pos++;
            }
        }
        if (pos < content.size()) pos++;
        result.push_back(s);
    }
    return result;
}

// ============================================================================
// Section 10: Process Execution
// ============================================================================

static inline void print_command(const std::vector<std::string>& cmd) {
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
// Quote a single argument according to Windows command-line parsing rules.
// Doubles trailing backslashes when followed by a quote so the unquoter sees
// the intended single backslash + quote pair.
static inline std::string win_quote_arg(const std::string& arg) {
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

// CreateProcess + wait. Inherits stdout/stderr so Meson/CMake pipes keep
// working — _execv on Windows breaks parent-process pipe attribution.
static inline int create_process_and_wait(const std::vector<std::string>& cmd,
                                          const char* tag = "[ctc] ") {
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
        fprintf(stderr, "%sFailed to create process: %lu\n", tag, GetLastError());
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

// Replace this process with `cmd`. On Windows we go through
// create_process_and_wait so stdout/stderr inheritance survives.
[[noreturn]] static inline void exec_process(const std::vector<std::string>& cmd,
                                             const char* tag = "[ctc] ") {
#ifdef _WIN32
    int rc = create_process_and_wait(cmd, tag);
    std::exit(rc);
#else
    std::vector<const char*> argv_ptrs;
    for (const auto& s : cmd) argv_ptrs.push_back(s.c_str());
    argv_ptrs.push_back(nullptr);
    execv(cmd[0].c_str(), const_cast<char**>(argv_ptrs.data()));
    fprintf(stderr, "%sFailed to exec: %s\n", tag, cmd[0].c_str());
    std::exit(127);
#endif
}

// Run a shell command, capturing stdout. Returns empty string on non-zero
// exit. Used by one-shot Python discovery scripts.
static inline std::string run_capture(const std::string& cmd) {
    std::string result;
#ifdef _WIN32
    // _popen invokes cmd.exe /c which strips the first+last quotes when the
    // command begins with a quote. Wrap once more so the inner quotes survive.
    std::string wrapped = "\"" + cmd + "\"";
    FILE* pipe = _popen(wrapped.c_str(), "r");
#else
    FILE* pipe = popen(cmd.c_str(), "r");
#endif
    if (!pipe) return "";
    char buf[4096];
    while (fgets(buf, sizeof(buf), pipe)) result += buf;
#ifdef _WIN32
    int rc = _pclose(pipe);
#else
    int rc = pclose(pipe);
#endif
    if (rc != 0) return "";
    return result;
}

} // namespace ctc

#endif // CTC_COMMON_H
