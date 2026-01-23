# Code Formatting and Linting

This document covers code formatting with clang-format and static analysis with clang-tidy.

## Overview

clang-tool-chain includes two essential code quality tools:

- **clang-format** - Automatic code formatter for C/C++/Objective-C
- **clang-tidy** - Static analyzer and linter with automatic fixes

Both tools integrate seamlessly with IDEs, editors, and CI/CD pipelines for consistent code style and quality across your codebase.

---

## clang-format

Automatic code formatting tool that enforces consistent style across your codebase.

**Command:** `clang-tool-chain-format`

### Basic Usage

```bash
# Format file (print to stdout)
clang-tool-chain-format file.cpp

# Format in-place (overwrite file)
clang-tool-chain-format -i file.cpp

# Format multiple files
clang-tool-chain-format -i src/*.cpp include/*.h

# Format with specific style
clang-tool-chain-format -i -style=Google file.cpp

# Check formatting (exit code 0 if already formatted)
clang-tool-chain-format --dry-run --Werror file.cpp
```

### Configuration Files

clang-format looks for configuration in `.clang-format` files (YAML format) in the current directory and parent directories.

**Create configuration:**

```bash
# Generate default .clang-format based on style
clang-tool-chain-format -style=LLVM -dump-config > .clang-format

# Or use one of the built-in styles
clang-tool-chain-format -style=Google -dump-config > .clang-format
```

**Example `.clang-format` file:**

```yaml
---
BasedOnStyle: LLVM
IndentWidth: 4
ColumnLimit: 120
UseTab: Never
BreakBeforeBraces: Allman
AllowShortFunctionsOnASingleLine: Empty
PointerAlignment: Left
```

### Built-in Style Presets

| Style | Description | Use Case |
|-------|-------------|----------|
| **LLVM** | LLVM coding standards | Default, balanced style |
| **Google** | Google C++ Style Guide | Widely used in industry |
| **Chromium** | Chromium project style | Based on Google with tweaks |
| **Mozilla** | Mozilla coding style | Firefox codebase |
| **WebKit** | WebKit coding style | Safari/WebKit |
| **Microsoft** | Microsoft Visual Studio style | Windows development |
| **GNU** | GNU coding standards | GCC and GNU projects |

**Preview styles:**

```bash
# Compare different styles
clang-tool-chain-format -style=LLVM file.cpp > file_llvm.cpp
clang-tool-chain-format -style=Google file.cpp > file_google.cpp
clang-tool-chain-format -style=Mozilla file.cpp > file_mozilla.cpp

# Pick the one you like!
```

### Common Configuration Options

**Indentation:**
```yaml
IndentWidth: 4                    # Number of spaces per indent level
UseTab: Never                     # Never/ForIndentation/ForContinuationAndIndentation/Always
TabWidth: 4                       # Width of tab character
```

**Line Length:**
```yaml
ColumnLimit: 120                  # Maximum line length (0 = no limit)
```

**Braces:**
```yaml
BreakBeforeBraces: Attach         # Attach/Linux/Mozilla/Stroustrup/Allman/GNU/WebKit/Custom
```

**Spacing:**
```yaml
SpaceBeforeParens: ControlStatements  # Never/Always/ControlStatements/etc.
SpaceAfterCStyleCast: false
SpaceBeforeAssignmentOperators: true
```

**Pointers and References:**
```yaml
PointerAlignment: Left            # Left/Right/Middle
# int* ptr; (Left)
# int *ptr; (Right)
# int * ptr; (Middle)
```

**Functions:**
```yaml
AllowShortFunctionsOnASingleLine: Empty  # None/Empty/Inline/All
AllowShortIfStatementsOnASingleLine: Never
AllowShortLoopsOnASingleLine: false
```

### IDE Integration

#### Visual Studio Code

**Method 1: C/C++ Extension (Microsoft)**

1. Install "C/C++" extension
2. Configure in `.vscode/settings.json`:

```json
{
  "C_Cpp.clang_format_path": "clang-tool-chain-format",
  "C_Cpp.clang_format_style": "file",
  "editor.formatOnSave": true
}
```

**Method 2: Clang-Format Extension**

1. Install "Clang-Format" extension
2. Configure in `.vscode/settings.json`:

```json
{
  "clang-format.executable": "clang-tool-chain-format",
  "clang-format.style": "file",
  "editor.formatOnSave": true
}
```

#### CLion / IntelliJ IDEA

1. **Settings → Editor → Code Style → C/C++**
2. **Set from... → Predefined Style → LLVM/Google/etc.**
3. Or: **Enable ClangFormat → Use clang-format binary** → Point to `clang-tool-chain-format`
4. **Reformat Code:** Ctrl+Alt+L (Windows/Linux) or Cmd+Option+L (macOS)

#### Vim / Neovim

**Using vim-clang-format plugin:**

```vim
" Install plugin (vim-plug)
Plug 'rhysd/vim-clang-format'

" Configure
let g:clang_format#command = 'clang-tool-chain-format'
let g:clang_format#style_options = {
  \ "BasedOnStyle": "LLVM",
  \ "IndentWidth": 4,
  \ "ColumnLimit": 120
  \ }

" Auto-format on save
autocmd FileType c,cpp,objc ClangFormatAutoEnable

" Manual format: <Leader>cf
```

**Using ALE (Asynchronous Lint Engine):**

```vim
Plug 'dense-analysis/ale'

let g:ale_c_clangformat_executable = 'clang-tool-chain-format'
let g:ale_c_clangformat_options = '-style=file'
let g:ale_fixers = {
\   'c': ['clangformat'],
\   'cpp': ['clangformat'],
\}
```

#### Emacs

**Using clang-format.el:**

```elisp
;; Install clang-format package
(require 'clang-format)

;; Configure executable
(setq clang-format-executable "clang-tool-chain-format")

;; Keybindings
(global-set-key (kbd "C-c f") 'clang-format-region)
(global-set-key (kbd "C-c u") 'clang-format-buffer)

;; Auto-format on save
(add-hook 'c-mode-common-hook
  (lambda ()
    (add-hook 'before-save-hook 'clang-format-buffer nil 'local)))
```

---

## clang-tidy

Static analyzer and linter that detects bugs, style issues, and suggests modern C++ improvements.

**Command:** `clang-tool-chain-tidy`

### Basic Usage

```bash
# Analyze single file
clang-tool-chain-tidy file.cpp

# Analyze with specific checks
clang-tool-chain-tidy -checks='-*,readability-*' file.cpp

# Analyze with compiler flags
clang-tool-chain-tidy file.cpp -- -std=c++17 -I./include

# Analyze and auto-fix issues
clang-tool-chain-tidy -fix file.cpp -- -std=c++17

# Analyze with custom config
clang-tool-chain-tidy --config-file=.clang-tidy file.cpp
```

### Configuration Files

clang-tidy looks for `.clang-tidy` configuration files (YAML format) in the current directory and parent directories.

**Example `.clang-tidy` file:**

```yaml
---
Checks: >
  -*,
  bugprone-*,
  modernize-*,
  performance-*,
  readability-*,
  -readability-identifier-length,
  -modernize-use-trailing-return-type
WarningsAsErrors: ''
HeaderFilterRegex: '.*'
FormatStyle: file
CheckOptions:
  - key: readability-identifier-naming.ClassCase
    value: CamelCase
  - key: readability-identifier-naming.FunctionCase
    value: camelBack
  - key: readability-identifier-naming.VariableCase
    value: lower_case
```

### Check Categories

**Security and Reliability:**
- `bugprone-*` - Detects common programming errors
- `cert-*` - CERT C++ Coding Standard checks
- `cppcoreguidelines-*` - C++ Core Guidelines checks

**Modernization:**
- `modernize-*` - Suggests modern C++ features (auto, nullptr, range-for, etc.)
- `modernize-use-auto` - Replace explicit type with auto
- `modernize-use-nullptr` - Replace NULL/0 with nullptr
- `modernize-use-override` - Add override keyword

**Performance:**
- `performance-*` - Detects performance issues
- `performance-unnecessary-copy-initialization` - Avoid unnecessary copies
- `performance-move-const-arg` - Detect useless std::move

**Readability:**
- `readability-*` - Code clarity and style
- `readability-identifier-naming` - Enforce naming conventions
- `readability-magic-numbers` - Detect magic numbers (use named constants)
- `readability-braces-around-statements` - Require braces for all control flow

**Concurrency:**
- `concurrency-*` - Thread safety issues
- `concurrency-mt-unsafe` - Thread-unsafe function usage

**Misc:**
- `clang-analyzer-*` - Static analyzer checks (deep analysis)
- `misc-*` - Miscellaneous checks
- `portability-*` - Portability issues

### Common Check Patterns

**Enable all checks from category:**
```yaml
Checks: 'modernize-*'
```

**Enable all checks except specific ones:**
```yaml
Checks: >
  modernize-*,
  -modernize-use-trailing-return-type,
  -modernize-avoid-c-arrays
```

**Multiple categories:**
```yaml
Checks: >
  bugprone-*,
  modernize-*,
  performance-*,
  readability-*
```

**Disable all, enable specific:**
```yaml
Checks: >
  -*,
  bugprone-use-after-move,
  modernize-use-nullptr,
  performance-unnecessary-copy-initialization
```

### Automatic Fixes

clang-tidy can automatically fix many issues:

```bash
# Preview fixes (don't modify files)
clang-tool-chain-tidy file.cpp -- -std=c++17

# Apply fixes automatically
clang-tool-chain-tidy -fix file.cpp -- -std=c++17

# Apply fixes with confirmation
clang-tool-chain-tidy -fix-errors file.cpp -- -std=c++17

# Export fixes to YAML (review before applying)
clang-tool-chain-tidy -export-fixes=fixes.yaml file.cpp -- -std=c++17
clang-apply-replacements . < fixes.yaml
```

### Naming Convention Checks

Enforce consistent naming across your codebase:

```yaml
CheckOptions:
  # Classes: PascalCase
  - key: readability-identifier-naming.ClassCase
    value: CamelCase

  # Functions: camelCase
  - key: readability-identifier-naming.FunctionCase
    value: camelBack

  # Variables: snake_case
  - key: readability-identifier-naming.VariableCase
    value: lower_case

  # Constants: UPPER_CASE
  - key: readability-identifier-naming.ConstantCase
    value: UPPER_CASE

  # Private members: m_ prefix
  - key: readability-identifier-naming.PrivateMemberPrefix
    value: m_

  # Namespaces: lower_case
  - key: readability-identifier-naming.NamespaceCase
    value: lower_case
```

**Available naming styles:**
- `lower_case` - snake_case (foo_bar)
- `UPPER_CASE` - SCREAMING_SNAKE_CASE (FOO_BAR)
- `camelBack` - camelCase (fooBar)
- `CamelCase` - PascalCase (FooBar)
- `Camel_Snake_Case` - Camel_Snake (Foo_Bar)
- `aNy_CasE` - No restrictions

### IDE Integration

#### Visual Studio Code

1. Install "clangd" extension (recommended) or "C/C++" extension
2. Configure in `.vscode/settings.json`:

**Using clangd:**
```json
{
  "clangd.arguments": [
    "--clang-tidy",
    "--completion-style=detailed"
  ],
  "clangd.path": "clangd"
}
```

**Using C/C++ extension:**
```json
{
  "C_Cpp.codeAnalysis.clangTidy.enabled": true,
  "C_Cpp.codeAnalysis.clangTidy.path": "clang-tool-chain-tidy",
  "C_Cpp.codeAnalysis.clangTidy.useBuildPath": false
}
```

#### CLion

1. **Settings → Editor → Inspections → C/C++**
2. **Enable "Clang-Tidy"**
3. **Configure checks** (uses `.clang-tidy` file automatically)
4. **Code → Inspect Code** to run analysis

#### Vim / Neovim

**Using ALE:**

```vim
Plug 'dense-analysis/ale'

let g:ale_linters = {
\   'c': ['clangtidy'],
\   'cpp': ['clangtidy'],
\}
let g:ale_c_clangtidy_executable = 'clang-tool-chain-tidy'
let g:ale_c_clangtidy_checks = ['*']
let g:ale_c_clangtidy_options = '-- -std=c++17'
```

**Using coc.nvim with clangd:**

```vim
Plug 'neoclide/coc.nvim', {'branch': 'release'}

" coc-settings.json
{
  "clangd.arguments": [
    "--clang-tidy",
    "--header-insertion=never"
  ]
}
```

---

## CI/CD Integration

### Pre-Commit Hooks

**Using pre-commit framework:**

`.pre-commit-config.yaml`:

```yaml
repos:
  - repo: local
    hooks:
      - id: clang-format
        name: clang-format
        entry: clang-tool-chain-format
        args: [-i]
        language: system
        files: \.(c|cpp|h|hpp)$

      - id: clang-tidy
        name: clang-tidy
        entry: clang-tool-chain-tidy
        args: [--quiet]
        language: system
        files: \.(cpp)$
        pass_filenames: true
```

Install hooks:
```bash
pip install pre-commit
pre-commit install
```

**Manual git hook:**

`.git/hooks/pre-commit`:

```bash
#!/bin/bash
set -e

echo "Running clang-format..."
clang-tool-chain-format -i $(git diff --cached --name-only --diff-filter=ACM | grep -E '\.(c|cpp|h|hpp)$')

echo "Running clang-tidy..."
for file in $(git diff --cached --name-only --diff-filter=ACM | grep -E '\.cpp$'); do
  clang-tool-chain-tidy "$file" -- -std=c++17
done

echo "Pre-commit checks passed!"
```

```bash
chmod +x .git/hooks/pre-commit
```

### GitHub Actions

**Format check workflow:**

`.github/workflows/format-check.yml`:

```yaml
name: Format Check

on: [push, pull_request]

jobs:
  format:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3

      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.11'

      - name: Install clang-tool-chain
        run: pip install clang-tool-chain

      - name: Check formatting
        run: |
          # Check if files are formatted
          clang-tool-chain-format --dry-run --Werror src/*.cpp include/*.h

      - name: Run clang-tidy
        run: |
          # Run static analysis
          for file in src/*.cpp; do
            clang-tool-chain-tidy "$file" -- -std=c++17 -Iinclude
          done
```

**Auto-format workflow (creates PR):**

`.github/workflows/auto-format.yml`:

```yaml
name: Auto Format

on:
  push:
    branches: [main]

jobs:
  format:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3

      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.11'

      - name: Install clang-tool-chain
        run: pip install clang-tool-chain

      - name: Format code
        run: |
          clang-tool-chain-format -i src/*.cpp include/*.h

      - name: Create Pull Request
        uses: peter-evans/create-pull-request@v5
        with:
          commit-message: 'style: auto-format code with clang-format'
          title: 'Auto-format code'
          body: 'Automated code formatting via clang-format'
          branch: auto-format
```

### GitLab CI

`.gitlab-ci.yml`:

```yaml
format_check:
  stage: test
  image: python:3.11
  script:
    - pip install clang-tool-chain
    - clang-tool-chain-format --dry-run --Werror src/**/*.cpp include/**/*.h

lint:
  stage: test
  image: python:3.11
  script:
    - pip install clang-tool-chain
    - find src -name '*.cpp' -exec clang-tool-chain-tidy {} -- -std=c++17 -Iinclude \;
```

---

## Common Workflows

### Format Entire Project

```bash
# Find and format all C/C++ files
find . -name '*.cpp' -o -name '*.h' | xargs clang-tool-chain-format -i

# Or with specific directories
clang-tool-chain-format -i src/**/*.cpp include/**/*.h

# Format only git-tracked files
git ls-files '*.cpp' '*.h' | xargs clang-tool-chain-format -i
```

### Format Only Changed Files (Git)

```bash
# Format files modified in last commit
git diff HEAD~1 --name-only --diff-filter=ACM | grep -E '\.(cpp|h)$' | xargs clang-tool-chain-format -i

# Format staged files
git diff --cached --name-only --diff-filter=ACM | grep -E '\.(cpp|h)$' | xargs clang-tool-chain-format -i

# Format files changed since main branch
git diff main --name-only --diff-filter=ACM | grep -E '\.(cpp|h)$' | xargs clang-tool-chain-format -i
```

### Run Specific clang-tidy Checks

```bash
# Check only modernize issues
clang-tool-chain-tidy -checks='-*,modernize-*' file.cpp -- -std=c++17

# Check performance issues
clang-tool-chain-tidy -checks='-*,performance-*' file.cpp -- -std=c++17

# Check multiple categories
clang-tool-chain-tidy -checks='-*,bugprone-*,modernize-*' file.cpp -- -std=c++17
```

### Generate HTML Reports

**clang-tidy with scan-build visualization:**

```bash
# Generate report directory
mkdir -p reports

# Run clang-tidy and save output
clang-tool-chain-tidy -checks='*' src/*.cpp -- -std=c++17 > reports/tidy.txt

# Or use scan-build wrapper (if available)
scan-build --use-analyzer=clang-tool-chain-tidy make
```

---

## Troubleshooting

### clang-format Not Respecting .clang-format File

**Problem:** Format doesn't match configuration file.

**Solutions:**

```bash
# Verify config file is found
clang-tool-chain-format -dump-config file.cpp | head -20

# Explicitly specify config file
clang-tool-chain-format -style=file:.clang-format -i file.cpp

# Check for syntax errors in .clang-format
clang-tool-chain-format -style=file:.clang-format -dump-config > /dev/null
```

### clang-tidy "No Checks Enabled"

**Problem:** No warnings shown, even with obvious issues.

**Solutions:**

```bash
# List enabled checks
clang-tool-chain-tidy -list-checks file.cpp -- -std=c++17

# Explicitly enable checks
clang-tool-chain-tidy -checks='*' file.cpp -- -std=c++17

# Check .clang-tidy file syntax
cat .clang-tidy | grep Checks:
```

### clang-tidy Compilation Errors

**Problem:** clang-tidy shows compilation errors before running checks.

**Solutions:**

```bash
# Ensure correct compiler flags
clang-tool-chain-tidy file.cpp -- -std=c++17 -Iinclude -DDEBUG

# Test compilation first
clang-tool-chain-cpp -fsyntax-only file.cpp -std=c++17 -Iinclude

# Use compile_commands.json (from CMake)
cmake -B build -DCMAKE_EXPORT_COMPILE_COMMANDS=ON
clang-tool-chain-tidy -p build file.cpp
```

### "Fix Conflicts" Errors with -fix

**Problem:** Multiple fixes conflict with each other.

**Solutions:**

```bash
# Run specific check category at a time
clang-tool-chain-tidy -checks='-*,modernize-*' -fix file.cpp -- -std=c++17

# Export fixes and review
clang-tool-chain-tidy -export-fixes=fixes.yaml file.cpp -- -std=c++17
cat fixes.yaml  # Review before applying
```

---

## Best Practices

### Formatting

1. **Use a `.clang-format` file** - Commit it to your repo for consistency
2. **Format on save** - Configure your IDE to auto-format
3. **CI enforcement** - Fail builds on formatting violations
4. **Choose a popular style** - LLVM or Google styles are well-tested
5. **Don't mix tabs and spaces** - Use `UseTab: Never` and `IndentWidth: 4`

### Linting

1. **Start with strict checks** - Enable all categories, disable noisy ones later
2. **Use `.clang-tidy` file** - Version control your check configuration
3. **Run before commit** - Use pre-commit hooks
4. **Fix incrementally** - Don't try to fix entire codebase at once
5. **Review auto-fixes** - `-fix` can introduce bugs, review changes carefully

### CI/CD

1. **Fast feedback** - Run format checks first (fastest)
2. **Cache toolchain** - Pre-install clang-tool-chain in Docker images
3. **Fail on warnings** - Use `WarningsAsErrors` in clang-tidy
4. **Report generation** - Archive clang-tidy output as artifacts

---

## See Also

- [Clang/LLVM Toolchain](CLANG_LLVM.md) - Compiler wrappers
- [Binary Utilities](BINARY_UTILS.md) - llvm-ar, llvm-nm, etc.
- [clang-format Documentation](https://clang.llvm.org/docs/ClangFormat.html) - Official docs
- [clang-tidy Documentation](https://clang.llvm.org/extra/clang-tidy/) - Official docs
- [ClangFormat Style Options](https://clang.llvm.org/docs/ClangFormatStyleOptions.html) - All config options
