# CI/CD Integration

Comprehensive CI/CD integration examples for GitHub Actions, GitLab CI, Docker, and Azure Pipelines.

## GitHub Actions

### Basic Build

```yaml
# .github/workflows/build.yml
name: Build

on: [push, pull_request]

jobs:
  build:
    runs-on: ${{ matrix.os }}
    strategy:
      matrix:
        os: [ubuntu-latest, windows-latest, macos-latest]

    steps:
      - uses: actions/checkout@v3

      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.11'

      - name: Install clang-tool-chain
        run: pip install clang-tool-chain

      - name: Compile project
        run: |
          clang-tool-chain-c src/main.c -o program
          ./program

      - name: Upload artifact
        uses: actions/upload-artifact@v3
        with:
          name: program-${{ matrix.os }}
          path: program*
```

### With Toolchain Caching

```yaml
# .github/workflows/build-cached.yml
name: Build with Cache

on: [push, pull_request]

jobs:
  build:
    runs-on: ubuntu-latest

    steps:
      - uses: actions/checkout@v3

      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.11'

      - name: Cache clang-tool-chain
        uses: actions/cache@v3
        with:
          path: ~/.clang-tool-chain
          key: clang-${{ runner.os }}-${{ runner.arch }}

      - name: Install clang-tool-chain
        run: pip install clang-tool-chain

      - name: Build
        run: clang-tool-chain-cpp main.cpp -o program
```

### With sccache

```yaml
# .github/workflows/build-sccache.yml
name: Build with sccache

on: [push, pull_request]

jobs:
  build:
    runs-on: ubuntu-latest

    steps:
      - uses: actions/checkout@v3

      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.11'

      - name: Install clang-tool-chain with sccache
        run: pip install clang-tool-chain[sccache]

      - name: Cache sccache
        uses: actions/cache@v3
        with:
          path: ${{ runner.temp }}/sccache
          key: sccache-${{ runner.os }}-${{ hashFiles('**/src/**') }}

      - name: Configure sccache
        run: |
          echo "SCCACHE_DIR=${{ runner.temp }}/sccache" >> $GITHUB_ENV

      - name: Build with sccache
        run: clang-tool-chain-sccache-cpp main.cpp -o program

      - name: Show cache stats
        run: clang-tool-chain-sccache --show-stats
```

### Multi-Platform Matrix

```yaml
# .github/workflows/matrix.yml
name: Multi-Platform Build

on: [push, pull_request]

jobs:
  build:
    strategy:
      matrix:
        os: [ubuntu-latest, windows-latest, macos-latest]
        arch: [x86_64]
        include:
          - os: ubuntu-latest
            arch: arm64
            runs-on: ubuntu-22.04-arm64

    runs-on: ${{ matrix.runs-on || matrix.os }}

    steps:
      - uses: actions/checkout@v3

      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.11'

      - name: Install clang-tool-chain
        run: pip install clang-tool-chain

      - name: Build
        run: clang-tool-chain-cpp main.cpp -o program-${{ matrix.os }}-${{ matrix.arch }}

      - name: Test
        run: ./program-${{ matrix.os }}-${{ matrix.arch }}

      - name: Upload artifacts
        uses: actions/upload-artifact@v3
        with:
          name: binaries
          path: program-*
```

## GitLab CI

### Basic Pipeline

```yaml
# .gitlab-ci.yml
image: python:3.11

stages:
  - build
  - test

build:
  stage: build
  script:
    - pip install clang-tool-chain
    - clang-tool-chain-c src/main.c -o program
    - clang-tool-chain-strip program
  artifacts:
    paths:
      - program

test:
  stage: test
  script:
    - ./program
```

### With Caching

```yaml
# .gitlab-ci.yml
image: python:3.11

variables:
  PIP_CACHE_DIR: "$CI_PROJECT_DIR/.cache/pip"
  CLANG_TOOL_CHAIN_DOWNLOAD_PATH: "$CI_PROJECT_DIR/.cache/clang"

cache:
  paths:
    - .cache/pip
    - .cache/clang

stages:
  - build
  - test

build:
  stage: build
  script:
    - pip install clang-tool-chain
    - clang-tool-chain-cpp main.cpp -o program
  artifacts:
    paths:
      - program

test:
  stage: test
  script:
    - ./program
    - echo "Tests passed!"
```

### Multi-Platform

```yaml
# .gitlab-ci.yml
stages:
  - build

.build_template: &build_job
  stage: build
  script:
    - pip install clang-tool-chain
    - clang-tool-chain-cpp main.cpp -o program
  artifacts:
    paths:
      - program

build:linux:
  <<: *build_job
  image: python:3.11
  tags:
    - linux

build:macos:
  <<: *build_job
  tags:
    - macos

build:windows:
  <<: *build_job
  tags:
    - windows
  script:
    - pip install clang-tool-chain
    - clang-tool-chain-cpp main.cpp -o program.exe
```

## Docker

### Dockerfile

```dockerfile
# Dockerfile
FROM python:3.11-slim

# Install clang-tool-chain
RUN pip install clang-tool-chain

# Pre-download binaries (optional, speeds up builds)
RUN clang-tool-chain install clang || true

# Copy source code
COPY src/ /app/src/
WORKDIR /app

# Build
RUN clang-tool-chain-c src/main.c -o program

CMD ["./program"]
```

**Build and run:**
```bash
docker build -t myapp .
docker run myapp
```

### Multi-Stage Build (Smaller Image)

```dockerfile
# Dockerfile.multi-stage
FROM python:3.11-slim AS builder

# Install clang-tool-chain
RUN pip install clang-tool-chain

# Copy source and build
COPY src/ /app/src/
WORKDIR /app
RUN clang-tool-chain-c -O2 src/main.c -o program
RUN clang-tool-chain-strip program

# Final lightweight image
FROM debian:bullseye-slim
COPY --from=builder /app/program /usr/local/bin/program
CMD ["program"]
```

### Docker Compose

```yaml
# docker-compose.yml
version: '3.8'

services:
  build:
    build: .
    volumes:
      - ./src:/app/src
    environment:
      - CLANG_TOOL_CHAIN_DOWNLOAD_PATH=/cache/clang
    command: clang-tool-chain-cpp /app/src/main.cpp -o /app/program
```

## Azure Pipelines

### Basic Pipeline

```yaml
# azure-pipelines.yml
trigger:
  - main

pool:
  vmImage: 'ubuntu-latest'

steps:
- task: UsePythonVersion@0
  inputs:
    versionSpec: '3.11'

- script: |
    pip install clang-tool-chain
    clang-tool-chain-c src/main.c -o program
  displayName: 'Build with clang-tool-chain'

- task: PublishBuildArtifacts@1
  inputs:
    pathToPublish: 'program'
    artifactName: 'executable'
```

### Multi-Platform

```yaml
# azure-pipelines.yml
trigger:
  - main

strategy:
  matrix:
    Linux:
      imageName: 'ubuntu-latest'
    macOS:
      imageName: 'macos-latest'
    Windows:
      imageName: 'windows-latest'

pool:
  vmImage: $(imageName)

steps:
- task: UsePythonVersion@0
  inputs:
    versionSpec: '3.11'

- script: |
    pip install clang-tool-chain
    clang-tool-chain-cpp main.cpp -o program
  displayName: 'Build'

- task: PublishBuildArtifacts@1
  inputs:
    pathToPublish: 'program*'
    artifactName: 'program-$(Agent.OS)'
```

## CircleCI

```yaml
# .circleci/config.yml
version: 2.1

jobs:
  build:
    docker:
      - image: python:3.11
    steps:
      - checkout
      - restore_cache:
          keys:
            - clang-v1-{{ arch }}
      - run:
          name: Install clang-tool-chain
          command: pip install clang-tool-chain
      - run:
          name: Build
          command: clang-tool-chain-cpp main.cpp -o program
      - save_cache:
          key: clang-v1-{{ arch }}
          paths:
            - ~/.clang-tool-chain
      - store_artifacts:
          path: program

workflows:
  version: 2
  build-workflow:
    jobs:
      - build
```

## Travis CI

```yaml
# .travis.yml
language: python
python:
  - "3.11"

os:
  - linux
  - osx

cache:
  directories:
    - ~/.clang-tool-chain

install:
  - pip install clang-tool-chain

script:
  - clang-tool-chain-cpp main.cpp -o program
  - ./program
```

## Common Patterns

### Pre-Install for Faster Builds

```yaml
# Pre-install in setup step
- name: Pre-install toolchain
  run: clang-tool-chain install clang

# Subsequent builds are faster (no download)
- name: Build
  run: clang-tool-chain-cpp main.cpp -o program
```

### Cache Toolchain Between Runs

```yaml
# GitHub Actions example
- name: Cache toolchain
  uses: actions/cache@v3
  with:
    path: ~/.clang-tool-chain
    key: clang-${{ runner.os }}-${{ runner.arch }}
    restore-keys: |
      clang-${{ runner.os }}-
      clang-
```

### Verify Installation

```yaml
# Add diagnostic step
- name: Verify installation
  run: |
    clang-tool-chain info
    clang-tool-chain test
```

### Cross-Compilation

```yaml
# Example: Build ARM64 on x86_64
- name: Cross-compile for ARM64
  run: |
    clang-tool-chain-cpp --target=aarch64-linux-gnu main.cpp -o program-arm64
    # Note: Requires appropriate sysroot
```

## Best Practices

1. **Cache toolchain** - Significantly speeds up CI runs
2. **Use matrix builds** - Test across platforms automatically
3. **Pre-install in Dockerfile** - Faster container startups
4. **Pin Python version** - Ensures consistency (3.10+)
5. **Upload artifacts** - Preserve built binaries
6. **Use sccache for large projects** - Massive speedup on rebuilds
7. **Test installation** - Run `clang-tool-chain test` in CI

## Troubleshooting CI/CD

### Downloads timing out

```yaml
# Increase timeout or pre-cache
- name: Pre-install with retry
  run: |
    for i in {1..3}; do
      clang-tool-chain install clang && break || sleep 5
    done
```

### Permission errors (Linux containers)

```dockerfile
# Run as non-root user
RUN useradd -m builder
USER builder
RUN pip install --user clang-tool-chain
ENV PATH="/home/builder/.local/bin:${PATH}"
```

### Windows PATH issues

```yaml
# Windows PowerShell
- name: Add to PATH
  run: |
    $path = (clang-tool-chain path clang).Replace('"', '')
    echo "$path" | Out-File -FilePath $env:GITHUB_PATH -Encoding utf8 -Append
```

## Related Documentation

- [Installation Guide](INSTALLATION.md) - Installation options
- [Configuration](CONFIGURATION.md) - Environment variables for CI
- [sccache Integration](SCCACHE.md) - Distributed caching setup
- [Examples](EXAMPLES.md) - More build examples
