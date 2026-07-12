# agentlink

Agentlink helps Claude Code and Codex share the same basic working context with
symlinks. It does not create a new canonical store. It links the agent artifacts
you already have.

Artifact types stay intact: rules map to rules, skills map to skills, and
reviewed memory maps to reviewed memory. Plugins and agent definitions remain
native artifacts for their host; Agentlink never converts them into skills.

Agentlink itself ships native Claude Code and Codex plugin manifests.

Agentlink has three sync strategies:

| Strategy | What It Does |
| --- | --- |
| Rules | Links one rules file to one rules file, such as `CLAUDE.md` and `AGENTS.md`. |
| Skills | Links each skill entry separately, preserving Codex-owned entries such as `.system`. |
| Memory | Links one reviewed memory file or folder first; links children one by one only when needed. |

All operations are conservative:

- Default mode is dry-run.
- If only one side exists, the missing side becomes a symlink to the existing side.
- If both sides already resolve to the same target, nothing changes.
- If both sides exist and differ, Agentlink reports a conflict and makes no change.
- Agentlink does not merge, append, delete, replace, or back up files.

## Install

### Claude Code Plugin

No git clone required. From inside Claude Code:

```text
/plugin marketplace add zombie12138/agentlink
/plugin install agentlink@agentlink
/reload-plugins
```

Use the namespaced plugin skill:

```text
/agentlink:agentlink dry-run global skills sync between Claude Code and Codex
```

### Codex Plugin

From a shell:

```bash
codex plugin marketplace add zombie12138/agentlink
codex plugin add agentlink@agentlink
```

Start a new Codex thread after installation, then invoke the bundled skill as
`$agentlink`.

## Usage

Use the skill from your agent. Ask for a dry run first, review the plan, then
ask it to apply.

Claude Code plugin:

```text
/agentlink:agentlink dry-run global rules sync between Claude Code and Codex
/agentlink:agentlink dry-run global skills sync between Claude Code and Codex
/agentlink:agentlink dry-run repo rules and skills sync for this repository
/agentlink:agentlink dry-run this memory pair: .claude/memory/MEMORY.md and .codex/memory/MEMORY.md
```

Codex:

```text
Use $agentlink to dry-run global rules sync between Claude Code and Codex.
Use $agentlink to dry-run global skills sync between Claude Code and Codex.
Use $agentlink to dry-run repo rules and skills sync for this repository.
Use $agentlink to dry-run this memory pair: .claude/memory/MEMORY.md and .codex/memory/MEMORY.md.
```

The helper script is intentionally small. If you need to debug or run it
directly, read [skills/agentlink/SKILL.md](./skills/agentlink/SKILL.md) and
invoke `scripts/agentlink.py` from that skill directory (Claude:
`$CLAUDE_SKILL_DIR`, Codex: `$SKILL_DIR`).

## Behavior

Rules are file pairs:

```text
~/.claude/CLAUDE.md  <->  ~/.codex/AGENTS.md
<repo>/CLAUDE.md    <->  <repo>/AGENTS.md
```

Skills are entry pairs:

```text
~/.claude/skills/<name>        <->  ~/.codex/skills/<name>
<repo>/.claude/skills/<name>  <->  <repo>/.agents/skills/<name>
```

Ordinary `skills` sync skips Codex-side symlink entries so generated or
externally managed entries are not synced back into Claude skills.

`global all` and `repo all` include rules and skills only. Plugin packages,
agent definitions, runtime state, caches, sessions, credentials, and JSONL logs
are outside the symlink helper's scope.

Memory is explicit. Claude source:
`~/.claude/projects/<encoded-path>/memory/` (encode the repo absolute path by
replacing `/` with `-`, e.g. `/home/zombie/apps/ganja` →
`-home-zombie-apps-ganja`). Recommended facade:

```text
<repo>/.agents/memory  ->  ~/.claude/projects/<encoded-path>/memory/
```

Prefer Markdown; avoid SQLite. Do not default-sync `~/.codex/memories/`. If the
user names other memory paths, follow their preference.

## Safety

- Skills are not synced by linking the whole skills directory.
- Codex `.system` skill entries are skipped and preserved.
- Ordinary skills sync skips Codex-side symlink entries.
- New skills require running Agentlink again so the new entry can be linked.
- For conflicts, the agent should show both paths and ask the user whether to
  manually merge, delete one side, move one side aside, or leave it unchanged.
- Do not sync generated databases, JSONL logs, session state, credentials,
  caches, plugin state, or temporary files.
- Exit codes: `0` success/no-op, `1` conflict/runtime error, `2` invalid arguments.
- Do not delete or uninstall `.claude`, `.codex`, `~/.claude`, or `~/.codex`
  casually after syncing. One side may now be the real shared source; removing it
  can make both agents lose the linked rules, skills, or memory.
