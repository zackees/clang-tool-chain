#!/usr/bin/env python3
"""Custom lint rule: flag ' '.join() on argument/flag lists.

Joining CLI args with ' '.join() is unsafe — arguments containing spaces
are silently corrupted and substring matches across argument boundaries
cause false positives.  Use ``any(pat in a for a in args)`` for flag
detection or ``shlex.join(args)`` / ``subprocess.list2cmdline(args)``
for display purposes.

Exit code 0: no violations, 1: violations found.
"""

import re
import sys
from pathlib import Path

# Pattern:  ' '.join( or " ".join(
PATTERN = re.compile(r"""["']\s["']\.join\(""")

# Variable names that strongly suggest CLI argument lists
ARG_NAMES = re.compile(
    r"\b(args|argv|cmd|command|flags|compiler_args|linker_args|safe_args"
    r"|extra_args|user_args|filtered_args)\b",
    re.IGNORECASE,
)

DIRECTIVE = (
    "CTC-LINT: Do not join CLI args with ' '.join() — "
    "use shlex.join() for display, or iterate the list for flag detection. "
    "See: https://docs.python.org/3/library/shlex.html#shlex.join"
)


def check_file(path: Path) -> list[str]:
    violations: list[str] = []
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeDecodeError):
        return violations

    for lineno, line in enumerate(lines, 1):
        if PATTERN.search(line) and ARG_NAMES.search(line):
            # skip lines with a # noqa marker
            if "# noqa" in line or "# lint-ok" in line:
                continue
            violations.append(f"{path}:{lineno}: {DIRECTIVE}\n    {line.strip()}")

    return violations


def main() -> int:
    roots = sys.argv[1:] or ["src", "tests"]
    violations: list[str] = []
    for root in roots:
        root_path = Path(root)
        if root_path.is_file():
            violations.extend(check_file(root_path))
        else:
            for py in sorted(root_path.rglob("*.py")):
                violations.extend(check_file(py))

    if violations:
        print(f"Found {len(violations)} violation(s):\n")
        for v in violations:
            print(v)
            print()
        return 1

    print("No ' '.join(args) violations found.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
