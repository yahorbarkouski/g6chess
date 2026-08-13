#!/usr/bin/env python3
"""Reject recurring contrastive-negation templates in public README prose."""

from __future__ import annotations

import re
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
README_PATHS = (REPOSITORY_ROOT / "README.md", REPOSITORY_ROOT / "frontend/README.md")
DISALLOWED_PATTERNS = (
    re.compile(r"\bthe point is not\b", re.IGNORECASE),
    re.compile(r"\bnot\s+(?:just|only|simply|merely)\b", re.IGNORECASE),
    re.compile(
        r"\b(?:not|isn't|aren't|doesn't|don't)\b(?:(?![.!?]).){0,180}\bbut\b",
        re.IGNORECASE | re.DOTALL,
    ),
)


def main() -> int:
    failures: list[str] = []
    for path in README_PATHS:
        prose = path.read_text(encoding="utf-8")
        for pattern in DISALLOWED_PATTERNS:
            for match in pattern.finditer(prose):
                line = prose.count("\n", 0, match.start()) + 1
                failures.append(f"{path.relative_to(REPOSITORY_ROOT)}:{line}")

    if failures:
        print("README prose check failed. Rewrite contrastive negation directly:")
        for failure in failures:
            print(f"  {failure}")
        return 1

    print("README prose check passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
