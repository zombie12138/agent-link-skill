---
name: agentlink
description: Share Claude Code and Codex rules, skills, and reviewed memory by symlinking existing files or skill entries. Use when the user asks to sync CLAUDE.md with AGENTS.md, global or repo skills, reviewed memory files/folders, /agentlink global, /agentlink repo, or explicit Claude/Codex path pairs.
---

# Agentlink

Use this skill to let Claude Code and Codex share basic working context through
symlinks. Do exactly the sync the user asked for; do not run unrelated sync
steps.

Agentlink has three sync strategies:

- **Rules**: link one rules file to one rules file.
- **Skills**: link each skill entry separately, never the whole skills folder.
- **Memory**: prefer linking one reviewed memory file or folder; only link
  children one by one when the user asks or a whole-folder link is not suitable.

The helper only creates symlinks:

- If only one side exists, link the missing side to the existing side.
- If both sides already resolve to the same target, do nothing.
- If both sides exist and differ, report a conflict and stop.

Never delete, merge, append, overwrite, or back up agent artifacts. When both
sides exist and differ, explain both paths and ask the user what to do. The user
may choose to manually merge files, delete one side, move one side aside, or
leave the conflict unresolved. Run Agentlink again only after the conflict is
resolved.

## Capability Routing

Map user requests narrowly:

| User Wants | Command |
| --- | --- |
| Sync global Claude/Codex rules | `global rules` |
| Sync global Claude/Codex skills entry by entry | `global skills` |
| Sync global rules and skills | `global all` or `global` |
| Sync repo Claude/Codex rules | `repo rules --repo PATH` |
| Sync repo Claude/Codex skills entry by entry | `repo skills --repo PATH` |
| Sync repo rules and skills | `repo all --repo PATH` or `repo --repo PATH` |
| Sync one reviewed memory file or one whole reviewed memory folder | `pair CLAUDE_PATH CODEX_PATH` |
| Sync children of two reviewed memory folders | `dir-pairs CLAUDE_DIR CODEX_DIR` |

Do not infer a larger sequence. If the user asks only for rules, only sync
rules. If the user asks only for skills, only sync skills.

When a user says "repo skills/memory/rules", run repo rules and skills with the
repo command, but do not assume memory is inside the repo. Memory is always an
explicit path decision.

## Rules

Rules are one file on each side.

Global rules:

```text
~/.claude/CLAUDE.md  <->  ~/.codex/AGENTS.md
```

Repo rules:

```text
<repo>/CLAUDE.md  <->  <repo>/AGENTS.md
```

Commands:

```bash
python3 scripts/agentlink.py global rules --dry-run
python3 scripts/agentlink.py repo rules --repo . --dry-run
```

## Skills

Skills are linked entry by entry. Do not symlink the whole skills directory.
This keeps Codex-owned entries such as `.system` intact and avoids hiding
agent-specific files.

Global skill entries:

```text
~/.claude/skills/<name>  <->  ~/.codex/skills/<name>
```

Repo skill entries:

```text
<repo>/.claude/skills/<name>  <->  <repo>/.agents/skills/<name>
```

Commands:

```bash
python3 scripts/agentlink.py global skills --dry-run
python3 scripts/agentlink.py repo skills --repo . --dry-run
```

Notes:

- `.system` is skipped.
- New skills are not discovered by an old symlink plan. Run Agentlink again
  after adding a skill.
- Claude plugin skills are not converted automatically. If the user wants a
  plugin skill shared, first make a normal Claude skill entry that points to it
  with a distinct name such as `<skill-name>-sync`, then run the skills sync.

## Memory

Memory sync is only for reviewed Markdown-like files or directories the user
intentionally wants to share. Do not sync generated databases, JSONL logs,
session state, credentials, caches, plugin state, or temporary files.

Memory may live outside the repository. For example, Claude Code may keep
project memory under a path like:

```text
~/.claude/projects/<encoded-project-path>/memory/
```

Do not guess the Codex destination for such memory. If the user asks to sync
repo memory and no obvious repo-local memory path exists, report the discovered
Claude memory path and ask for the Codex target path, or ask whether to skip
memory.

Prefer `pair` for memory after both paths are known. It links one file or one
whole folder:

```bash
python3 scripts/agentlink.py pair .claude/memory/MEMORY.md .codex/memory/MEMORY.md --dry-run
python3 scripts/agentlink.py pair .claude/memory .codex/memory --dry-run
python3 scripts/agentlink.py pair ~/.claude/projects/ENCODED_REPO/memory ~/.codex/memories/REPO --dry-run
```

Use `dir-pairs` only when a whole-folder memory link is not suitable and the
user wants reviewed children linked separately:

```bash
python3 scripts/agentlink.py dir-pairs .claude/memory .codex/memory --dry-run
```

## Helper

Use `--dry-run` first, then `--apply` after reviewing the plan:

```bash
python3 scripts/agentlink.py global --dry-run
python3 scripts/agentlink.py repo --repo . --dry-run
python3 scripts/agentlink.py pair CLAUDE_PATH CODEX_PATH --dry-run
python3 scripts/agentlink.py dir-pairs CLAUDE_DIR CODEX_DIR --dry-run
```

Apply is intentionally simple and does not roll back earlier links if a later
pair hits a filesystem error. For risky changes, dry-run first and apply one
capability at a time.

Exit codes:

- `0`: success or no-op.
- `1`: conflict or filesystem/runtime error.
- `2`: invalid CLI arguments.

Warn users before uninstalling or deleting `~/.claude`, `~/.codex`, repo
`.claude`, or repo `.agents`: after Agentlink creates symlinks, one side may be
the real source. Removing the real source can remove the shared rules, skills,
or memory for both agents.
