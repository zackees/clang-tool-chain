# Security Policy

## Overview

The security of `clang-tool-chain` and its users is a top priority. This document outlines our security policy, including supported versions, how to report vulnerabilities, and our security practices.

## Supported Versions

We currently support the following versions with security updates:

| Version | Supported          | Status |
| ------- | ------------------ | ------ |
| 0.0.x   | :white_check_mark: | Alpha - Active development |
| < 0.0.1 | :x:                | Not released |

**Note**: As this project is in alpha (v0.0.1), we may make breaking changes to address security issues. We will clearly document all security-related changes in the [CHANGELOG.md](CHANGELOG.md).

## Security Considerations

### Binary Distribution

`clang-tool-chain` distributes pre-built LLVM/Clang binaries. Users should be aware of the following:

1. **Binary Sources**: All binaries are downloaded from official LLVM sources:
   - Primary: https://github.com/llvm/llvm-project/releases
   - Mirror: https://releases.llvm.org/

2. **Checksum Verification**:
   - **Automatic Verification**: The download scripts automatically verify SHA256 checksums to ensure binary integrity
   - **Checksum Database**: Known checksums are maintained in `src/clang_tool_chain/checksums.py`
   - **Protection Against**:
     - Corrupted downloads due to network issues
     - Man-in-the-middle attacks
     - Compromised mirror servers
     - File tampering
   - **Verification Process**:
     - When downloading, the script checks for known checksums in the database
     - If a checksum is available, it's automatically verified after download
     - Downloads fail if checksum verification fails (unless disabled with `--no-verify`)
     - Existing files are re-verified before reuse
   - **Adding Checksums**: See `src/clang_tool_chain/checksums.py` for instructions on adding checksums for new releases
   - **Opt-out**: Verification can be disabled with `--no-verify` flag (not recommended)

3. **No Modifications**: We do not modify the LLVM binaries beyond:
   - Removing documentation and examples (size optimization)
   - Removing unnecessary tools
   - Stripping debug symbols
   - We do NOT patch, recompile, or alter the actual tool binaries

4. **LLVM Security**: For security issues in the LLVM/Clang tools themselves, refer to:
   - LLVM Security Group: https://llvm.org/docs/Security.html
   - LLVM Bug Tracker: https://github.com/llvm/llvm-project/issues

### Code Execution

The Python wrapper executes the downloaded Clang binaries as subprocesses:

1. **Argument Passing**: Arguments are passed directly to the binary without shell interpretation (using `subprocess.run` with `shell=False`)
2. **Path Validation**: Binary paths are validated before execution
3. **No Arbitrary Execution**: The wrapper only executes known Clang tools, not arbitrary commands

### Supply Chain Security

We take supply chain security seriously:

1. **Minimal Dependencies**: The package has minimal Python dependencies to reduce attack surface
2. **Locked Dependencies**: We use specific version pins in development
3. **Automated Scanning**: CI/CD includes security scanning (planned)
4. **Reproducible Builds**: Build process is documented and reproducible

## Reporting a Vulnerability

### Where to Report

**DO NOT** open a public GitHub issue for security vulnerabilities.

Instead, report security issues to:

- **Email**: security@example.com (replace with actual security contact)
- **GitHub Security Advisories**: Use GitHub's private vulnerability reporting at:
  https://github.com/zackees/clang-tool-chain/security/advisories/new

### What to Include

When reporting a vulnerability, please include:

1. **Description**: Clear description of the vulnerability
2. **Impact**: What could an attacker accomplish?
3. **Reproduction Steps**: Step-by-step instructions to reproduce
4. **Affected Versions**: Which versions are affected?
5. **Proposed Solution**: If you have suggestions for fixing it
6. **Proof of Concept**: Code or commands demonstrating the issue (if safe to share)

Example report structure:

```
Subject: [SECURITY] Brief description of vulnerability

Description:
[Detailed description of the vulnerability]

Impact:
[What an attacker could do with this vulnerability]

Reproduction Steps:
1. Install clang-tool-chain version X.X.X
2. Run command: clang-tool-chain-c [specific arguments]
3. Observe: [unexpected behavior]

Affected Versions:
- Version 0.0.1
- [Other versions if known]

Proposed Solution:
[Your suggestions for fixing the issue]

Additional Context:
[Any other relevant information]
```

### Response Timeline

We aim to respond to security reports according to the following timeline:

| Stage | Timeline |
|-------|----------|
| Initial Response | Within 48 hours |
| Vulnerability Assessment | Within 7 days |
| Fix Development | Depends on severity |
| Security Advisory | Before or with fix release |
| Public Disclosure | After fix is available |

**Severity Classifications**:

- **Critical**: Arbitrary code execution, privilege escalation - Fix within 7 days
- **High**: Information disclosure, DoS - Fix within 30 days
- **Medium**: Lesser impact issues - Fix within 90 days
- **Low**: Minimal impact - Fix in next regular release

### Disclosure Policy

We follow responsible disclosure:

1. **Private Reporting**: Vulnerabilities are reported privately
2. **Investigation**: We investigate and develop a fix
3. **Coordination**: We coordinate disclosure with the reporter
4. **Advisory**: We publish a security advisory with CVE (if applicable)
5. **Public Disclosure**: Details are made public after fix is available

We request that security researchers:

- Give us reasonable time to fix the issue before public disclosure (typically 90 days)
- Do not exploit the vulnerability beyond proof-of-concept
- Do not access, modify, or delete user data
- Keep the vulnerability confidential until we publish an advisory

## Security Best Practices for Users

### Installation

1. **Verify Package Source**: Install from trusted sources (PyPI, official GitHub)
   ```bash
   pip install clang-tool-chain
   ```

2. **Check Package Hash**: Verify the package hash matches official releases
   ```bash
   pip install clang-tool-chain==0.0.1 --require-hashes
   ```

3. **Use Virtual Environments**: Always install in a virtual environment
   ```bash
   python -m venv .venv
   source .venv/bin/activate  # On Windows: .venv\Scripts\activate
   pip install clang-tool-chain
   ```

### Binary Downloads

1. **Automatic Downloads**: The package downloads binaries from official LLVM sources

2. **Checksum Verification** (Recommended):
   - SHA256 checksums are **automatically verified** during download
   - Checksums are stored in `src/clang_tool_chain/checksums.py`
   - Verification is **enabled by default** for security
   - Failed verification prevents use of potentially corrupted files

   ```bash
   # Download with automatic verification (default)
   python scripts/download_binaries.py --current-only

   # Disable verification (NOT recommended)
   python scripts/download_binaries.py --current-only --no-verify
   ```

3. **Manual Checksum Verification**: You can manually compute and verify checksums:
   ```bash
   # Linux/macOS
   sha256sum LLVM-21.1.5-Linux-X64.tar.xz

   # Windows PowerShell
   Get-FileHash LLVM-21.1.5-win64.exe -Algorithm SHA256

   # Windows CMD
   certutil -hashfile LLVM-21.1.5-win64.exe SHA256
   ```

4. **Adding Checksums**: To add checksums for new LLVM releases:
   - See instructions in `src/clang_tool_chain/checksums.py`
   - Verify official LLVM signatures first (GPG or GitHub attestation)
   - Compute SHA256 checksum of verified binary
   - Add to `KNOWN_CHECKSUMS` dictionary

5. **Source Inspection**: Review `scripts/download_binaries.py` to see exactly what is downloaded

### Compilation Security

When using clang-tool-chain to compile code:

1. **Trusted Sources**: Only compile code from trusted sources
2. **Code Review**: Review code before compilation, especially from external sources
3. **Sandboxing**: Consider compiling untrusted code in isolated environments (containers, VMs)
4. **Output Validation**: Validate compiled binaries before execution

### System Security

1. **Keep Updated**: Update to the latest version regularly
   ```bash
   pip install --upgrade clang-tool-chain
   ```

2. **Monitor Advisories**: Watch the GitHub repository for security advisories
3. **System Updates**: Keep your system and Python installation up to date
4. **Permissions**: Don't run compilation tools with elevated privileges unless necessary

## Known Security Considerations

### Current Limitations

1. **Alpha Software**: This is alpha-stage software (v0.0.1) and may have undiscovered vulnerabilities
2. **Binary Trust**: Users must trust the LLVM project's binary releases
3. **Download Security**: Depends on HTTPS security for binary downloads
4. **Platform Dependencies**: Relies on underlying OS security (file system permissions, etc.)

### Non-Goals

The following are explicitly out of scope:

1. **LLVM Vulnerabilities**: We don't fix vulnerabilities in LLVM/Clang itself (report to LLVM project)
2. **Compiled Code Security**: We don't guarantee security of code compiled with the tools
3. **System Security**: We don't provide sandboxing or isolation for compilation
4. **Malware Scanning**: We don't scan source code for malicious content

## Security Testing

### Development Practices

1. **Code Review**: All code changes undergo review before merging
2. **Automated Testing**: CI/CD runs automated tests on all platforms
3. **Dependency Scanning**: Regular scanning of Python dependencies (planned)
4. **Static Analysis**: Code is analyzed with ruff, mypy, and pyright
5. **Pre-commit Hooks**: Security checks run automatically on commit

### Testing Tools

We use the following tools for security and quality:

- **ruff**: Fast Python linter with security checks
- **mypy**: Static type checking
- **pyright**: Additional type checking
- **bandit**: Python security linter (planned)
- **safety**: Dependency vulnerability scanning (planned)

### Continuous Monitoring

- GitHub Dependabot: Monitors dependencies for known vulnerabilities
- Security Advisories: Subscribed to LLVM security announcements
- Community Reports: Actively monitor issue reports

## Security Update Process

When a security issue is identified:

1. **Triage**: Assess severity and impact
2. **Fix**: Develop and test a fix
3. **Advisory**: Create a GitHub Security Advisory
4. **Release**: Release patched version
5. **Notification**: Notify users through:
   - GitHub Security Advisory
   - Release notes
   - CHANGELOG.md update
   - PyPI release notes

### Version Numbering

Security releases follow semantic versioning:

- **Patch Release** (0.0.x): Security fixes for current version
- **Minor Release** (0.x.0): Security fixes with new features
- **Major Release** (x.0.0): Breaking changes required for security

## Acknowledgments

We appreciate security researchers who help keep `clang-tool-chain` secure:

- **Hall of Fame**: Security researchers who report valid vulnerabilities will be acknowledged (with permission) in our [SECURITY_HALL_OF_FAME.md](SECURITY_HALL_OF_FAME.md) (planned)
- **CVE Credits**: Researchers will be credited in any published CVEs
- **Thanks**: We're grateful for responsible disclosure

## Resources

### Security Documentation

- **LLVM Security**: https://llvm.org/docs/Security.html
- **Python Security**: https://python.org/news/security/
- **OWASP**: https://owasp.org/
- **CVE Database**: https://cve.mitre.org/

### Related Policies

- [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md) - Community standards
- [CONTRIBUTING.md](CONTRIBUTING.md) - Contribution guidelines
- [LICENSE](LICENSE) - Software license
- [CHANGELOG.md](CHANGELOG.md) - Version history

## Contact

- **Security Issues**: security@example.com (private)
- **General Issues**: https://github.com/zackees/clang-tool-chain/issues (public)
- **Discussions**: https://github.com/zackees/clang-tool-chain/discussions
- **Project Maintainers**: See [CONTRIBUTING.md](CONTRIBUTING.md)

## Legal

This security policy applies to the `clang-tool-chain` Python package and wrapper code. The distributed LLVM/Clang binaries are subject to the LLVM Project's security policy and license.

### Disclaimer

This software is provided "as is" without warranty of any kind. See the [LICENSE](LICENSE) file for full terms.

---

**Last Updated**: 2025-11-07
**Version**: 1.0
**Scope**: clang-tool-chain v0.0.1+
