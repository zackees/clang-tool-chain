# Security

Security practices and verification for clang-tool-chain.

## Overview

Security is a top priority for this project. All downloaded binaries are verified using SHA256 checksums, and the download process includes multiple safety layers.

## Checksum Verification

### Automatic Verification

SHA256 checksums are automatically verified during every download:

- **Enabled by default** - No configuration needed
- **Manifest-based** - Checksums stored in version-controlled manifests
- **Protection against**:
  - Corrupted downloads
  - Man-in-the-middle (MITM) attacks
  - File tampering
  - Supply chain attacks

### Manual Verification

You can manually verify checksums before installation:

```bash
# See what will be downloaded
clang-tool-chain-fetch --dry-run

# Example output shows SHA256:
# URL: https://raw.githubusercontent.com/zackees/clang-tool-chain-bins/main/assets/clang/linux/x86_64/llvm-21.1.5.tar.zst
# SHA256: abc123def456...

# Verify checksum in manifest
cat ~/.clang-tool-chain/downloads-bins/assets/clang/linux/x86_64/manifest.json
```

### Checksum Sources

Checksums are stored in version-controlled manifest files:

**Location:** `downloads-bins/assets/clang/{platform}/{arch}/manifest.json`

**Example manifest:**
```json
{
  "version": "21.1.5",
  "archive": "llvm-21.1.5.tar.zst",
  "sha256": "abc123def456...",
  "url": "https://raw.githubusercontent.com/zackees/clang-tool-chain-bins/main/assets/clang/linux/x86_64/llvm-21.1.5.tar.zst",
  "size": 91234567
}
```

## Safe Extraction

### Python 3.12+ Tarfile Safety

- **Filter mode:** Uses `filter="data"` to prevent path traversal attacks
- **Temporary directory:** Extraction happens in temp directory, then moved atomically
- **Validation:** Verifies archive integrity before extraction
- **No symlink attacks:** Filters prevent malicious symlinks

### Extraction Process

1. Download to temporary file
2. Verify SHA256 checksum
3. Extract to temporary directory with safety filters
4. Validate extracted contents
5. Atomic move to final location
6. Create completion marker (`done.txt`)

## Download Security

### HTTPS Only

All downloads use encrypted HTTPS connections:

```
https://raw.githubusercontent.com/zackees/clang-tool-chain-bins/main/assets/...
```

- ✅ **Encrypted transport** - Prevents eavesdropping
- ✅ **GitHub infrastructure** - Benefits from GitHub's security
- ✅ **TLS/SSL** - Modern cipher suites

### Trust Model

When using clang-tool-chain, you're trusting:

1. **This package maintainer** - Author of clang-tool-chain
2. **GitHub infrastructure** - Hosts the binary archives
3. **LLVM project** - Source of the original binaries
4. **Package checksums** - Version-controlled in repository

**Note:** This is similar to trusting PyPI, npm, or any package registry.

### Checksum Verification Process

```python
# Simplified verification flow
def verify_download(file_path, expected_sha256):
    actual_sha256 = compute_sha256(file_path)
    if actual_sha256 != expected_sha256:
        raise SecurityError("Checksum mismatch!")
    return True
```

Every download is verified before use. Failed verification stops the installation.

## Maximum Security Options

### Option 1: Manual Verification

```bash
# 1. Check what will be downloaded
clang-tool-chain-fetch --dry-run

# 2. Verify checksums in manifest
cat downloads-bins/assets/clang/<platform>/<arch>/manifest.json

# 3. Download archive manually
wget <url-from-step-1>

# 4. Verify checksum independently
sha256sum llvm-*.tar.zst

# 5. Compare with manifest

# 6. Extract and install manually if verified
```

### Option 2: Offline Installation

For airgapped or high-security environments:

```bash
# On internet-connected machine:
# 1. Download archive
wget https://raw.githubusercontent.com/zackees/clang-tool-chain-bins/main/assets/clang/{platform}/{arch}/llvm-*.tar.zst

# 2. Verify checksum independently
sha256sum llvm-*.tar.zst
# Compare with: downloads-bins/assets/clang/{platform}/{arch}/manifest.json

# 3. Transfer verified archive to target machine

# On offline machine:
# 4. Extract manually
mkdir -p ~/.clang-tool-chain/clang/{platform}/{arch}
python -m clang_tool_chain.downloads.expand_archive llvm-*.tar.zst ~/.clang-tool-chain/clang/{platform}/{arch}
touch ~/.clang-tool-chain/clang/{platform}/{arch}/done.txt

# 5. Verify installation
clang-tool-chain test
```

### Option 3: Build from Source

For ultimate control, build LLVM from source:

```bash
# Clone LLVM
git clone https://github.com/llvm/llvm-project.git
cd llvm-project

# Checkout specific version
git checkout llvmorg-21.1.5

# Build (requires significant time and resources)
cmake -S llvm -B build -DCMAKE_BUILD_TYPE=Release
cmake --build build

# Point clang-tool-chain to your build
export CLANG_TOOL_CHAIN_DOWNLOAD_PATH=/path/to/llvm/build
```

## Reporting Security Issues

### Responsible Disclosure

For security vulnerabilities, please:

1. **DO NOT** report in public GitHub issues
2. **DO** email security@[project-domain] (or see SECURITY.md in repo)
3. Include:
   - Description of vulnerability
   - Steps to reproduce
   - Potential impact
   - Suggested fix (if applicable)

### Response Timeline

- **Acknowledgment:** Within 48 hours
- **Initial assessment:** Within 7 days
- **Fix timeline:** Depends on severity
  - Critical: 1-7 days
  - High: 7-14 days
  - Medium: 14-30 days
  - Low: 30+ days

## Security Best Practices

### For Users

1. **Verify checksums** - Especially for first install
2. **Use HTTPS** - Never download over HTTP
3. **Keep updated** - Install security updates promptly
4. **Pin versions** - Use `clang-tool-chain==X.Y.Z` in production
5. **Review manifests** - Check checksums in version control
6. **Audit dependencies** - Review what tools you're using

### For CI/CD

1. **Cache toolchains** - Reduces repeated downloads
2. **Pin package version** - Ensures reproducible builds
3. **Verify installation** - Run `clang-tool-chain test` in CI
4. **Use secrets management** - For sccache backends (S3, Redis, etc.)
5. **Scan containers** - If using Docker with clang-tool-chain

### For Developers

1. **Review changes** - Check manifest updates in PRs
2. **Verify binaries** - Test new LLVM versions thoroughly
3. **Document security** - Update this guide with new features
4. **Report issues** - See responsible disclosure above

## Threat Model

### In Scope

✅ **Download verification** - SHA256 checksums prevent tampering
✅ **Archive extraction** - Safe extraction prevents path traversal
✅ **HTTPS transport** - Encrypted downloads prevent eavesdropping
✅ **Manifest integrity** - Version-controlled checksums prevent manipulation

### Out of Scope

❌ **Compiler bugs** - clang-tool-chain uses official LLVM binaries
❌ **User code vulnerabilities** - Your code is your responsibility
❌ **System security** - OS-level security is outside our scope
❌ **Network security** - Firewall/proxy configuration is user-managed

### Assumptions

- User trusts the clang-tool-chain maintainer
- User trusts GitHub infrastructure
- User trusts LLVM project binaries
- System Python installation is not compromised
- Network transport (HTTPS/TLS) is secure

## Compliance and Auditing

### For Enterprises

Enterprises can audit clang-tool-chain by:

1. **Review source code** - All code on GitHub
2. **Review manifests** - All checksums in version control
3. **Independent verification** - Download and verify checksums
4. **Build from source** - Ultimate control (LLVM source build)
5. **Offline deployment** - Air-gapped installation supported

### Audit Trail

Every download creates an audit trail:

- Downloaded archive URL
- SHA256 checksum verification
- Installation timestamp
- Installation path
- Package version

## FAQ

**Q: Are binaries signed?**
A: Not currently. We use SHA256 checksums stored in version-controlled manifests. Code signing is planned for future releases.

**Q: Can I use my own binary mirrors?**
A: Not directly, but you can use offline installation with your own pre-downloaded archives.

**Q: What if GitHub is compromised?**
A: Checksums in the repository would detect tampering. An attacker would need to compromise both GitHub infrastructure AND the repository.

**Q: Are there reproducible builds?**
A: The LLVM binaries come from official LLVM releases or Homebrew. We don't currently rebuild from source, but you can verify checksums against official LLVM releases.

## Related Documentation

- [Installation Guide](INSTALLATION.md) - Installation options
- [Troubleshooting](TROUBLESHOOTING.md) - Common issues
- [Architecture](ARCHITECTURE.md) - Technical architecture
- [SECURITY.md](../SECURITY.md) - Reporting security issues
