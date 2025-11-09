# IWYU Binary Downloads Summary

## Downloaded Binaries

### Windows x86_64
- Source: MSYS2 mingw64
- Package: mingw-w64-x86_64-include-what-you-use-0.25-1
- Version: 0.25
- URL: https://mirror.msys2.org/mingw/mingw64/mingw-w64-x86_64-include-what-you-use-0.25-1-any.pkg.tar.zst
- SHA256: (from Homebrew API) N/A - MSYS2 package
- Architecture: x86_64 (PE32+ executable)

### macOS x86_64  
- Source: Homebrew bottle
- Version: 0.25_1
- URL: https://ghcr.io/v2/homebrew/core/include-what-you-use/blobs/sha256:5525b7f43377fd15a36821b00c8fcda1cffa466315fc189881cd843e6a14ec54
- SHA256: 5525b7f43377fd15a36821b00c8fcda1cffa466315fc189881cd843e6a14ec54
- Architecture: Mach-O 64-bit x86_64 executable

### macOS ARM64
- Source: Homebrew bottle  
- Version: 0.25_1
- URL: https://ghcr.io/v2/homebrew/core/include-what-you-use/blobs/sha256:ce1afe4cf2eda64076bcecc7ac53578564fded555d6786ab46b5b26fd8022679
- SHA256: ce1afe4cf2eda64076bcecc7ac53578564fded555d6786ab46b5b26fd8022679
- Architecture: Mach-O 64-bit arm64 executable

### Linux x86_64
- Source: Homebrew bottle
- Version: 0.25_1
- URL: https://ghcr.io/v2/homebrew/core/include-what-you-use/blobs/sha256:33758f6714ab8c29596918913cd70a1f162406e4ea2c161ba5a55f932bf4d90c
- SHA256: 33758f6714ab8c29596918913cd70a1f162406e4ea2c161ba5a55f932bf4d90c
- Architecture: ELF 64-bit LSB pie executable, x86-64

### Linux ARM64
- Source: Homebrew bottle
- Version: 0.25_1  
- URL: https://ghcr.io/v2/homebrew/core/include-what-you-use/blobs/sha256:8c63e00abc6b27ee41877b9dab66a79f961be696bd0899649dc48c4e7ba02a9b
- SHA256: 8c63e00abc6b27ee41877b9dab66a79f961be696bd0899649dc48c4e7ba02a9b
- Architecture: ELF 64-bit LSB pie executable, ARM aarch64

## Files Included

Each platform includes:
- `bin/include-what-you-use` (or .exe on Windows) - Main IWYU executable
- `bin/fix_includes.py` - Python script to automatically fix includes
- `bin/iwyu_tool.py` - Python tool for running IWYU
- `share/include-what-you-use/*.imp` - Mapping files for various libraries (Boost, Qt, Python, etc.)
- `LICENSE.TXT` - License file (Homebrew bottles only)
- `README.md` - Documentation (Homebrew bottles only)

## Directory Structure

```
downloads/iwyu/
├── win/
│   └── x86_64/
│       ├── bin/
│       └── share/
├── darwin/
│   ├── x86_64/
│   │   ├── bin/
│   │   └── share/
│   └── arm64/
│       ├── bin/
│       └── share/
└── linux/
    ├── x86_64/
    │   ├── bin/
    │   └── share/
    └── arm64/
        ├── bin/
        └── share/
```
