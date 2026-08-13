#!/usr/bin/env python3
"""Reproduce the reviewed G6 frontend/backend history migration.

The commands are intentionally narrow: they refuse dirty worktrees, broad
targets, and pre-existing output directories. They never push or deploy.
"""

from __future__ import annotations

import argparse
import subprocess
from pathlib import Path


FRONTEND_ENTRIES = (
    ".env.example",
    ".gitignore",
    "AGENTS.md",
    "README.md",
    "audit",
    "biome.json",
    "bun.lock",
    "index.html",
    "package.json",
    "public",
    "src",
    "tsconfig.app.json",
    "tsconfig.json",
    "tsconfig.node.json",
    "vercel.json",
    "vite.config.ts",
)
PRIVATE_AUTHOR_EMAIL = b"yahor.barkouski@gmail.com"
PUBLIC_AUTHOR_EMAIL = b"94449298+yahorbarkouski@users.noreply.github.com"
BACKEND_AUDIT_PATH = "docs/audits"


def run(*args: str, cwd: Path) -> None:
    subprocess.run(args, cwd=cwd, check=True)


def output(*args: str, cwd: Path) -> str:
    return subprocess.run(
        args,
        cwd=cwd,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


def require_repository(path: Path) -> Path:
    repository = path.resolve()
    if output("git", "rev-parse", "--show-toplevel", cwd=repository) != str(repository):
        raise SystemExit(f"Refusing non-root repository path: {repository}")
    return repository


def require_clean(repository: Path) -> None:
    if output("git", "status", "--porcelain", cwd=repository):
        raise SystemExit(f"Refusing dirty worktree: {repository}")


def relocate_frontend(repository: Path) -> None:
    repository = require_repository(repository)
    require_clean(repository)
    destination_root = repository / "frontend"

    for relative in FRONTEND_ENTRIES:
        source = repository / relative
        destination = destination_root / relative
        if not source.exists():
            if destination.exists():
                continue
            raise SystemExit(f"Expected tracked frontend entry is missing: {source}")
        if destination.exists():
            raise SystemExit(f"Refusing to overwrite frontend entry: {destination}")
        destination.parent.mkdir(parents=True, exist_ok=True)
        run("git", "mv", relative, str(Path("frontend") / relative), cwd=repository)


def prepare_backend(source: Path, output_directory: Path, branch: str) -> None:
    source = require_repository(source)
    require_clean(source)
    destination = output_directory.resolve()
    if destination.exists():
        raise SystemExit(f"Refusing pre-existing migration output: {destination}")
    if destination.parent == destination or destination.parent == Path.home():
        raise SystemExit(f"Refusing broad migration output: {destination}")

    run("git", "clone", "--no-local", str(source), str(destination), cwd=source.parent)
    run("git", "checkout", branch, cwd=destination)
    callback = (
        "if commit.author_email == b'"
        + PRIVATE_AUTHOR_EMAIL.decode()
        + "': commit.author_email = b'"
        + PUBLIC_AUTHOR_EMAIL.decode()
        + "'\n"
        "if commit.committer_email == b'"
        + PRIVATE_AUTHOR_EMAIL.decode()
        + "': commit.committer_email = b'"
        + PUBLIC_AUTHOR_EMAIL.decode()
        + "'"
    )
    run(
        "git",
        "filter-repo",
        "--force",
        "--refs",
        branch,
        "--path",
        BACKEND_AUDIT_PATH,
        "--invert-paths",
        "--to-subdirectory-filter",
        "backend",
        "--commit-callback",
        callback,
        cwd=destination,
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)

    relocate = commands.add_parser("relocate-frontend")
    relocate.add_argument("repository", type=Path)

    prepare = commands.add_parser("prepare-backend")
    prepare.add_argument("source", type=Path)
    prepare.add_argument("output", type=Path)
    prepare.add_argument("--branch", required=True)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.command == "relocate-frontend":
        relocate_frontend(args.repository)
    else:
        prepare_backend(args.source, args.output, args.branch)


if __name__ == "__main__":
    main()
