# Contributing to clang-tool-chain

Thank you for your interest in contributing to clang-tool-chain! This document provides guidelines and instructions for contributing to the project.

## Table of Contents

- [Code of Conduct](#code-of-conduct)
- [Getting Started](#getting-started)
- [Development Setup](#development-setup)
- [Making Changes](#making-changes)
- [Testing](#testing)
- [Code Quality](#code-quality)
- [Submitting Changes](#submitting-changes)
- [Reporting Bugs](#reporting-bugs)
- [Suggesting Enhancements](#suggesting-enhancements)
- [Style Guidelines](#style-guidelines)

## Code of Conduct

This project follows a standard code of conduct. Please be respectful and constructive in all interactions with other contributors.

## Getting Started

1. **Fork the repository** on GitHub
2. **Clone your fork** locally:
   ```bash
   git clone https://github.com/YOUR_USERNAME/clang-tool-chain.git
   cd clang-tool-chain
   ```
3. **Set up the development environment** (see below)
4. **Create a branch** for your changes:
   ```bash
   git checkout -b feature/my-new-feature
   # or
   git checkout -b fix/issue-123
   ```

## Development Setup

### Prerequisites

- Python 3.10 or higher
- `uv` package manager (recommended) or `pip`
- Git

### Installation

Using the convenience script (recommended):

```bash
./install
```

Or manually:

```bash
# Create virtual environment
uv venv --python 3.11

# Activate virtual environment
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install dependencies
uv pip install -e ".[dev]"

# Install pre-commit hooks
pre-commit install
```

### Verify Installation

```bash
# Run tests
./test

# Run linters
./lint

# Check CLI works
uv run clang-tool-chain --help
```

## Making Changes

### Branch Naming

Use descriptive branch names:

- `feature/description` - For new features
- `fix/issue-number` or `fix/description` - For bug fixes
- `docs/description` - For documentation changes
- `refactor/description` - For code refactoring
- `test/description` - For test improvements

### Commit Messages

Write clear, concise commit messages:

```
Short summary (50 chars or less)

Longer explanation if needed. Wrap at 72 characters. Explain what
and why, not how. Reference issues using #123.

- Bullet points are okay
- Use present tense ("Add feature" not "Added feature")
- Use imperative mood ("Move cursor to..." not "Moves cursor to...")
```

Examples:
- `Add support for ARM64 Linux binaries`
- `Fix path handling on Windows (#42)`
- `Refactor wrapper module for better testability`
- `Update README with installation instructions`

## Testing

### Running Tests

```bash
# Run all tests
./test

# Run specific test file
uv run pytest tests/test_cli.py

# Run specific test
uv run pytest tests/test_cli.py::MainTester::test_imports

# Run with verbose output
uv run pytest -v

# Run in parallel
uv run pytest -n auto

# Skip slow tests
uv run pytest -m "not slow"
```

### Writing Tests

- **Unit tests**: Place in `tests/` directory, use `unittest` framework
- **Integration tests**: Place in `tests/test_integration.py`, test with real binaries
- **Test naming**: Use descriptive names like `test_compile_c_hello_world`
- **Test organization**: Group related tests in classes

Example test:

```python
import unittest
from clang_tool_chain import wrapper

class MyFeatureTests(unittest.TestCase):
    def test_feature_works(self):
        """Test that my feature works correctly."""
        result = wrapper.some_function()
        self.assertEqual(result, expected_value)
```

### Test Coverage

- Aim for high test coverage (>80%)
- Run coverage report: `uv run pytest --cov`
- View HTML report: `open htmlcov/index.html`

## Code Quality

### Linting and Formatting

We use several tools to maintain code quality. Run all at once:

```bash
./lint
```

Or individually:

```bash
# Format code and sort imports
uv run ruff format src tests

# Check linting
uv run ruff check --fix src tests

# Type checking
uv run mypy src tests
uv run pyright src tests
```

### Pre-commit Hooks

Pre-commit hooks run automatically on `git commit`:

```bash
# Install hooks
pre-commit install

# Run manually
pre-commit run --all-files

# Skip hooks (not recommended)
git commit --no-verify
```

### Code Style

- **Line length**: Maximum 120 characters
- **Formatting**: Use ruff format (handles code formatting and import sorting)
- **Type hints**: Use type hints where possible
- **Docstrings**: Use for public functions and classes
- **Comments**: Explain why, not what

Example:

```python
from typing import Optional

def compile_source(
    source_file: str,
    output_file: Optional[str] = None,
    optimization_level: int = 0,
) -> int:
    """
    Compile a C/C++ source file using clang.

    Args:
        source_file: Path to the source file to compile
        output_file: Optional output file path (default: a.out)
        optimization_level: Optimization level 0-3 (default: 0)

    Returns:
        Exit code from the compiler (0 = success)

    Raises:
        FileNotFoundError: If source_file does not exist
    """
    # Implementation here
    pass
```

## Submitting Changes

### Pull Request Process

1. **Update tests**: Add/update tests for your changes
2. **Update documentation**: Update README.md, docstrings, etc.
3. **Run checks**: Ensure all tests and linters pass
4. **Commit changes**: Use clear, descriptive commit messages
5. **Push to your fork**:
   ```bash
   git push origin feature/my-new-feature
   ```
6. **Open a Pull Request** on GitHub
7. **Describe your changes**: Use the PR template, explain what and why

### Pull Request Guidelines

- **One feature per PR**: Keep changes focused
- **Update CHANGELOG.md**: Add entry under "Unreleased" section
- **Reference issues**: Use "Fixes #123" or "Closes #456"
- **Respond to feedback**: Be open to suggestions
- **Keep it clean**: Rebase if needed, squash trivial commits

### PR Template

```markdown
## Description
Brief description of changes

## Type of Change
- [ ] Bug fix (non-breaking change)
- [ ] New feature (non-breaking change)
- [ ] Breaking change (fix or feature that would cause existing functionality to not work as expected)
- [ ] Documentation update

## Testing
- [ ] Tests pass locally
- [ ] Added/updated tests for changes
- [ ] Linters pass (./lint)

## Checklist
- [ ] Code follows project style guidelines
- [ ] Self-review completed
- [ ] Comments added for complex code
- [ ] Documentation updated
- [ ] CHANGELOG.md updated
```

## Reporting Bugs

### Before Submitting

1. **Check existing issues**: Search for similar issues
2. **Try latest version**: Ensure bug exists in latest release
3. **Reproduce**: Create minimal reproduction steps

### Bug Report Template

```markdown
## Bug Description
Clear description of the bug

## Steps to Reproduce
1. Run command `clang-tool-chain-c hello.c`
2. Observe error message
3. ...

## Expected Behavior
What you expected to happen

## Actual Behavior
What actually happened

## Environment
- OS: Windows 10, Ubuntu 22.04, macOS 13, etc.
- Python Version: 3.11.5
- clang-tool-chain Version: 0.0.1
- Installation Method: pip, from source, etc.

## Additional Context
Error messages, logs, screenshots, etc.
```

## Suggesting Enhancements

We welcome enhancement suggestions! Please provide:

1. **Clear use case**: Why is this enhancement needed?
2. **Proposed solution**: How should it work?
3. **Alternatives considered**: Other approaches you thought about
4. **Examples**: Show how it would be used

## Style Guidelines

### Python Style

- Follow PEP 8 with line length of 120
- Use type hints for function signatures
- Use descriptive variable names
- Avoid single-letter variables (except loop counters)
- Prefer explicit over implicit

### Documentation Style

- Use Markdown for documentation files
- Keep lines under 80 characters in Markdown
- Use code blocks with language specifiers
- Include examples for complex features

### Git Style

- Commit early, commit often
- Write meaningful commit messages
- Keep commits focused on single change
- Rebase to keep history clean

## Development Workflow

### Typical Workflow

```bash
# 1. Update main branch
git checkout main
git pull upstream main

# 2. Create feature branch
git checkout -b feature/my-feature

# 3. Make changes and test
# ... edit files ...
./test
./lint

# 4. Commit changes
git add .
git commit -m "Add my feature"

# 5. Push to fork
git push origin feature/my-feature

# 6. Open Pull Request on GitHub
```

### Keeping Your Fork Updated

```bash
# Add upstream remote (once)
git remote add upstream https://github.com/ORIGINAL_OWNER/clang-tool-chain.git

# Fetch and merge updates
git fetch upstream
git checkout main
git merge upstream/main
git push origin main
```

## Questions?

If you have questions about contributing:

1. Check existing documentation (README.md, CLAUDE.md)
2. Search closed issues for similar questions
3. Open a new issue with your question
4. Tag it with "question" label

## License

By contributing, you agree that your contributions will be licensed under the Apache License 2.0 with LLVM Exceptions (same as the project).

Thank you for contributing to clang-tool-chain!
