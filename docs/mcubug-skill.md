# mcubug Skill For Codex And CC

This repository includes an assistant skill at `skills/mcubug`. The skill teaches Codex and
Claude Code (CC) how to use `mcudubby` as an evidence-first embedded board debugging workflow
instead of treating the MCP tools as an unstructured command catalog.

Local source path from this checkout:

```text
E:\work_code\mcudubby\skills\mcubug
```

Local file link:

```text
file:///E:/work_code/mcudubby/skills/mcubug/SKILL.md
```

## What The Skill Contains

- `SKILL.md` - concise routing, safety rules, backend guidance, and reporting template
- `references/` - synchronized copies of the project docs needed during debug sessions
- `scripts/sync_references.py` - refreshes skill references from `docs/`
- `scripts/validate_skill.py` - checks required references and local Markdown links
- `scripts/install_skill.py` - installs the skill into a Codex or CC skills directory

## Install For Codex From This Checkout

From the repository root:

```powershell
.\.venv\Scripts\python.exe .\skills\mcubug\scripts\install_skill.py --target codex --overwrite
```

If you have a normal `python` command available:

```powershell
python .\skills\mcubug\scripts\install_skill.py --target codex --overwrite
```

The default Codex destination is:

```text
%USERPROFILE%\.codex\skills\mcubug
```

If `CODEX_HOME` is set, the Codex destination becomes:

```text
%CODEX_HOME%\skills\mcubug
```

On this machine that usually resolves to:

```text
C:\Users\zhouluo\.codex\skills\mcubug
```

Local file link after install:

```text
file:///C:/Users/zhouluo/.codex/skills/mcubug/SKILL.md
```

Restart Codex or open a new Codex thread after installing so the skill list refreshes.

## Install For Claude Code / CC From This Checkout

From the repository root:

```powershell
.\.venv\Scripts\python.exe .\skills\mcubug\scripts\install_skill.py --target cc --overwrite
```

If you have a normal `python` command available:

```powershell
python .\skills\mcubug\scripts\install_skill.py --target cc --overwrite
```

The default CC destination is:

```text
%USERPROFILE%\.claude\skills\mcubug
```

If `CLAUDE_HOME` is set, the CC destination becomes:

```text
%CLAUDE_HOME%\skills\mcubug
```

On this machine that usually resolves to:

```text
C:\Users\zhouluo\.claude\skills\mcubug
```

Local file link after install:

```text
file:///C:/Users/zhouluo/.claude/skills/mcubug/SKILL.md
```

Restart Claude Code / CC or open a new session after installing so the skill list refreshes.

## Custom Destination

Use `--dest-root` to install somewhere else. The skill is copied into a `mcubug` subdirectory
under the destination root:

```powershell
python .\skills\mcubug\scripts\install_skill.py --dest-root C:\path\to\skills --overwrite
```

## Refresh References After Editing Docs

When the project docs change, refresh the skill references:

```powershell
.\.venv\Scripts\python.exe .\skills\mcubug\scripts\sync_references.py
```

Then reinstall the skill if you want the local Codex copy updated:

```powershell
.\.venv\Scripts\python.exe .\skills\mcubug\scripts\install_skill.py --target codex --overwrite
```

Or reinstall the CC copy:

```powershell
.\.venv\Scripts\python.exe .\skills\mcubug\scripts\install_skill.py --target cc --overwrite
```

## Validate

Run the repository-local skill check:

```powershell
.\.venv\Scripts\python.exe .\skills\mcubug\scripts\validate_skill.py .\skills\mcubug
```

If the system skill-creator tools are available, also run:

```powershell
.\.venv\Scripts\python.exe C:\Users\zhouluo\.codex\skills\.system\skill-creator\scripts\quick_validate.py .\skills\mcubug
```

## Maintenance Rule

Keep project documentation canonical in `docs/`. The skill references are copied from those docs
so Codex can load only the pieces it needs during a debug session. Do not add broad duplicate
README-style material to `skills/mcubug/references/`; add or update the relevant project doc, then
run `sync_references.py`.
