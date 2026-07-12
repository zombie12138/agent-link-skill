---
name: agentlink
description: Share matching Claude Code and Codex rules, skills, and reviewed memory by symlinking like artifacts. Use when the user asks to sync CLAUDE.md with AGENTS.md, global or repo skills, reviewed memory files/folders, /agentlink global, /agentlink repo, explicit Claude/Codex path pairs, or to sync/share plugins between Claude and Codex.
---

# Agentlink

Share Claude Code and Codex working context through symlinks. Do exactly the
sync the user asked for; do not run unrelated steps.

Keep artifact types aligned: rules↔rules, skills↔skills, reviewed memory↔
reviewed memory. Plugins and agent definitions stay native to each host. If the
user insists on plugin↔plugin or plugin↔skill anyway, follow **Not Recommended**.

Strategies:

- **Rules**: one rules file to one rules file.
- **Skills**: each skill entry separately, never the whole skills folder.
- **Memory**: one reviewed file or folder first; `dir-pairs` only when asked or
  a whole-folder link is unsuitable.

Helper behavior:

- Only one side exists → link the missing side to the existing side.
- Both already resolve alike → no-op.
- Both exist and differ → report conflict; never delete, merge, append,
  overwrite, or back up. Show both paths and ask what to do.

## Capability Routing

| User Wants | Command |
| --- | --- |
| Sync global Claude/Codex rules | `global rules` |
| Sync global Claude/Codex skills entry by entry | `global skills` |
| Sync global rules and skills | `global all` or `global` |
| Sync repo Claude/Codex rules | `repo rules --repo PATH` |
| Sync repo Claude/Codex skills entry by entry | `repo skills --repo PATH` |
| Sync repo rules and skills | `repo all --repo PATH` or `repo --repo PATH` |
| Sync one reviewed memory file or folder | `pair CLAUDE_PATH CODEX_PATH` |
| Sync children of two reviewed memory folders | `dir-pairs CLAUDE_DIR CODEX_DIR` |

Do not widen the request. "Repo skills/memory/rules" still means repo rules and
skills only; memory always needs explicit paths.

## Paths

Rules:

```text
~/.claude/CLAUDE.md  <->  ~/.codex/AGENTS.md
<repo>/CLAUDE.md    <->  <repo>/AGENTS.md
```

Skills (entry by entry; skip `.system`; skip Codex-side symlinks; re-run after
adding a skill):

```text
~/.claude/skills/<name>        <->  ~/.codex/skills/<name>
<repo>/.claude/skills/<name>  <->  <repo>/.agents/skills/<name>
```

Memory is reviewed Markdown only — never SQLite, JSONL, sessions, credentials,
caches, or plugin runtime state.

Claude keeps project memory under `~/.claude/projects/<encoded-path>/memory/`.
Encode the repo absolute path by replacing every `/` with `-` (so
`/home/zombie/apps/ganja` → `-home-zombie-apps-ganja`). Recommended
Codex/repo facade (ganja-style): symlink under the repo

```text
<repo>/.agents/memory  ->  ~/.claude/projects/<encoded-path>/memory/
```

Use `pair` with Claude path first:

```bash
pair ~/.claude/projects/<encoded-path>/memory <repo>/.agents/memory
```

Do not invent a global `~/.claude/memory/` or treat `~/.codex/memory/` as the
default. Do not default-sync generated `~/.codex/memories/`. If the user names
other memory paths, follow their preference.

### Setup (install / first use)

Require these bullets in global rules (`~/.codex/AGENTS.md` /
`~/.claude/CLAUDE.md`). If missing, show them and ask before editing:

```text
- Store persistent memory as Markdown files under `<repo>/.agents/memory/`; do not use SQLite memory. Read memory before each session.
- Before writing, inspect the exact path, resolve symlinks, and read existing content. Never infer absence from search results or use Add File unless the resolved path is confirmed absent.
```

Then for the current repo (dry-run first):

```bash
pair ~/.claude/projects/<encoded-path>/memory <repo>/.agents/memory
```

## Not Recommended

Do not automate plugin↔plugin or plugin↔skill. This section only unifies
behavior when the user insists: warn, get confirmation, do not extend
`agentlink.py` or revive `plugin-skills`. Prefer native plugins per host.

### Plugin ↔ plugin

Contracts differ (manifests, discovery, cache, namespaces; Claude may ship
hooks/MCP/agents, Codex mainly skills). Symlinking whole plugin roots usually
breaks the other host and fakes equivalence.

If insisted: keep each manifest native; share only the portable skill tree
(`SKILL.md` + optional `scripts/`) via ordinary `skills` sync or an explicit
same-type `pair`; or ship two native plugins that vendor the same skill files.

### Plugin ↔ skill

This is a type conversion, not a sync: the receiver gets a skill and loses
plugin identity, hooks/MCP/agents, and marketplace lifecycle.

If insisted: warn; only single-skill trees with top-level `SKILL.md` and no
required host-only pieces; `pair` that skill dir into the peer skills path
(never cache/runtime/credentials); on name conflict, stop and ask.

### Afterwards: how to check

1. `ls -la` / `readlink -f`: which side is real, both resolve alike.
2. Invoke on **each** host; host-only features only where expected.
3. Remind: ordinary `skills` sync skips Codex symlinks, so Agentlink will not
   manage these links; deleting the real source can break both sides.

## Helper

Resolve the helper from **this skill directory**, not the user's project cwd:

```bash
# Claude Code
python3 "$CLAUDE_SKILL_DIR/scripts/agentlink.py" SCOPE [args] --dry-run
# Codex
python3 "$SKILL_DIR/scripts/agentlink.py" SCOPE [args] --dry-run
```

If neither variable is set, use the directory that contains this `SKILL.md`.

Dry-run first, then `--apply` after review:

```bash
python3 "$CLAUDE_SKILL_DIR/scripts/agentlink.py" global --dry-run
python3 "$CLAUDE_SKILL_DIR/scripts/agentlink.py" repo --repo . --dry-run
python3 "$CLAUDE_SKILL_DIR/scripts/agentlink.py" pair CLAUDE_PATH CODEX_PATH --dry-run
python3 "$CLAUDE_SKILL_DIR/scripts/agentlink.py" dir-pairs CLAUDE_DIR CODEX_DIR --dry-run
```

Apply does not roll back earlier links if a later pair fails. For risky
changes, dry-run first and apply one capability at a time.

Exit codes: `0` success/no-op, `1` conflict/runtime error, `2` invalid args.

Warn before uninstalling `~/.claude`, `~/.codex`, repo `.claude`, or repo
`.agents`: after linking, one side may be the real source; removing it can
drop shared rules, skills, or memory for both agents.
