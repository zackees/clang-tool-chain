#!/bin/bash
# .claude/hooks/lint-on-save.sh
# Runs ruff and pyright on saved Python files

INPUT=$(cat)
FILE_PATH=$(echo "$INPUT" | jq -r '.tool_input.file_path // empty')

# Only lint Python files
if [[ ! "$FILE_PATH" =~ \.py$ ]]; then
  exit 0
fi

echo "🔍 Linting: $FILE_PATH" >&2

# Run ruff check with auto-fix
if uv run ruff check --fix "$FILE_PATH" 2>&1; then
  echo "✓ Ruff check passed" >&2
else
  echo "✗ Ruff check failed" >&2
fi

# Run ruff format
if uv run ruff format "$FILE_PATH" 2>&1; then
  echo "✓ Ruff format passed" >&2
else
  echo "✗ Ruff format failed" >&2
fi

# Run pyright
if uv run pyright "$FILE_PATH" 2>&1; then
  echo "✓ Pyright check passed" >&2
else
  echo "✗ Pyright found issues" >&2
fi

exit 0
