#!/usr/bin/env python3
"""Symlink Claude Code and Codex rules, skills, and reviewed memory."""

import argparse
import os
import sys
from dataclasses import dataclass
from pathlib import Path


SYSTEM_SKILL_NAMES = {".system"}


@dataclass(frozen=True)
class Pair:
    label: str
    claude: Path
    codex: Path


def expand(path: str | Path) -> Path:
    return Path(path).expanduser().resolve()


def exists(path: Path) -> bool:
    # A broken symlink is still an existing agent artifact; never overwrite it.
    return path.exists() or path.is_symlink()


def link_source(source: Path, target: Path) -> str:
    try:
        return os.path.relpath(source, target.parent)
    except ValueError:
        return str(source)


def same_target(left: Path, right: Path) -> bool:
    if not exists(left) or not exists(right):
        return False
    try:
        return left.resolve() == right.resolve()
    except FileNotFoundError:
        return False


def make_link(source: Path, target: Path, apply: bool, actions: list[str]) -> None:
    actions.append(f"link {target} -> {source}")
    if apply:
        target.parent.mkdir(parents=True, exist_ok=True)
        target.symlink_to(link_source(source, target))


def sync_pair(pair: Pair, apply: bool, actions: list[str]) -> None:
    """Sync one file, one directory, or one named skill without merging."""
    claude_exists = exists(pair.claude)
    codex_exists = exists(pair.codex)

    if not claude_exists and not codex_exists:
        actions.append(f"skip {pair.label}: neither side exists")
        return

    if claude_exists and codex_exists:
        if same_target(pair.claude, pair.codex):
            actions.append(f"ok {pair.label}: already shared")
            return
        actions.append(f"conflict {pair.label}: both sides exist and differ")
        actions.append(f"  claude: {pair.claude}")
        actions.append(f"  codex:  {pair.codex}")
        return

    if claude_exists:
        actions.append(f"{pair.label}: Claude exists, Codex missing")
        make_link(pair.claude, pair.codex, apply, actions)
        return

    actions.append(f"{pair.label}: Codex exists, Claude missing")
    make_link(pair.codex, pair.claude, apply, actions)


def find_repo_root(start: Path) -> tuple[Path, bool]:
    cur = start.resolve()
    if cur.is_file():
        cur = cur.parent
    for path in [cur, *cur.parents]:
        if (path / ".git").exists():
            return path, True
    return cur, False


def child_names(left: Path, right: Path, skip: set[str] | None = None) -> list[str]:
    names: set[str] = set()
    for directory in (left, right):
        if directory.is_dir():
            names.update(path.name for path in directory.iterdir())
    return sorted(names - (skip or set()))


def skill_pairs(claude_dir: Path, codex_dir: Path) -> list[Pair]:
    # Skills are linked one entry at a time so Codex-owned entries like .system stay intact.
    return [
        Pair(f"skill:{name}", claude_dir / name, codex_dir / name)
        for name in child_names(claude_dir, codex_dir, SYSTEM_SKILL_NAMES)
    ]


def dir_child_pairs(label: str, claude_dir: Path, codex_dir: Path) -> list[Pair]:
    return [
        Pair(f"{label}:{name}", claude_dir / name, codex_dir / name)
        for name in child_names(claude_dir, codex_dir)
    ]


def default_pairs(args: argparse.Namespace, warnings: list[str]) -> list[Pair]:
    if args.scope == "pair":
        return [Pair("pair", expand(args.claude_path), expand(args.codex_path))]

    if args.scope == "dir-pairs":
        return dir_child_pairs("dir-pair", expand(args.claude_path), expand(args.codex_path))

    if args.scope == "global":
        claude_rules = Path.home() / ".claude" / "CLAUDE.md"
        codex_rules = Path.home() / ".codex" / "AGENTS.md"
        claude_skills = Path.home() / ".claude" / "skills"
        codex_skills = Path.home() / ".codex" / "skills"
    else:
        root, found = find_repo_root(expand(args.repo))
        if not found:
            warnings.append(f"warning repo: no .git found; using {root}")
        claude_rules = root / "CLAUDE.md"
        codex_rules = root / "AGENTS.md"
        claude_skills = root / ".claude" / "skills"
        codex_skills = root / ".agents" / "skills"

    pairs: list[Pair] = []
    if args.kind in ("rules", "all"):
        pairs.append(Pair("rules", claude_rules, codex_rules))
    if args.kind in ("skills", "all"):
        pairs.extend(skill_pairs(claude_skills, codex_skills))
    return pairs


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("scope", choices=["global", "repo", "pair", "dir-pairs"])
    parser.add_argument("items", nargs="*")
    parser.add_argument("--repo", default=".", help="repo path for repo scope")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--apply", action="store_true", help="make changes")
    mode.add_argument("--dry-run", action="store_true", help="show actions only")
    args = parser.parse_args()

    args.kind = "all"
    args.claude_path = None
    args.codex_path = None
    if args.scope in ("pair", "dir-pairs") and len(args.items) == 2:
        args.claude_path, args.codex_path = args.items
    elif args.scope in ("global", "repo") and len(args.items) <= 1:
        args.kind = args.items[0] if args.items else "all"
    return args


def validate_args(args: argparse.Namespace) -> int | None:
    if args.scope == "pair":
        if args.kind != "all" or len(args.items) != 2:
            print("ERROR: pair usage is: agentlink.py pair CLAUDE_PATH CODEX_PATH [--apply]", file=sys.stderr)
            return 2
    elif args.scope == "dir-pairs":
        if args.kind != "all" or len(args.items) != 2:
            print("ERROR: dir-pairs usage is: agentlink.py dir-pairs CLAUDE_DIR CODEX_DIR [--apply]", file=sys.stderr)
            return 2
    elif args.kind not in ("rules", "skills", "all") or len(args.items) > 1:
        print("ERROR: global/repo usage is: agentlink.py SCOPE [rules|skills|all] [--apply]", file=sys.stderr)
        return 2
    return None


def has_conflict(actions: list[str]) -> bool:
    return any(action.startswith("conflict ") or action.startswith("ERROR:") for action in actions)


def main() -> int:
    args = parse_args()
    error_code = validate_args(args)
    if error_code is not None:
        return error_code

    actions: list[str] = []
    warnings: list[str] = []

    try:
        pairs = default_pairs(args, warnings)
        if not pairs:
            actions.append(f"skip {args.scope} {getattr(args, 'kind', '')}: no matching entries")
        for pair in pairs:
            sync_pair(pair, args.apply, actions)
    except OSError as exc:
        actions.append(f"ERROR: {exc.filename or 'operation failed'}: {exc.strerror or exc}")

    print("APPLY" if args.apply else "DRY RUN")
    for warning in warnings:
        print(f"- {warning}")
    for action in actions:
        print(f"- {action}")

    return 1 if has_conflict(actions) else 0


if __name__ == "__main__":
    sys.exit(main())
