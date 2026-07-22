# mcubug Skill

`skills/mcubug/` packages McuBuddy's evidence-first operating guidance for Codex-compatible clients.

## Contents

```text
skills/mcubug/
├── SKILL.md
├── agents/openai.yaml
├── references/
└── scripts/
    ├── sync_references.py
    └── validate_skill.py
```

`SKILL.md` contains routing, safety, and reporting rules. References are generated snapshots of canonical documents under `docs/`.

## Canonical references

The sync script maintains nine references:

- `quickstart.md`
- `windows-mcp-config-example.md`
- `tool-reference.md`
- `support-matrix.md`
- `ai-playbook.md`
- `ai-examples.md`
- `generic-board-workflow.md`
- `board-validation-guide.md`
- `peripheral-actuator-debug-playbook.md`

Do not edit generated copies directly.

## Synchronize and validate

```bash
python skills/mcubug/scripts/sync_references.py
python skills/mcubug/scripts/sync_references.py --check
python skills/mcubug/scripts/validate_skill.py
python scripts/validate_docs.py
```

## Install elsewhere

Copy the complete `skills/mcubug` directory into the receiving Codex skills directory, then restart the client. Keep the directory structure intact.

## Maintenance rule

1. Edit the canonical document in `docs/`.
2. Run the sync script.
3. Run both validators and relevant tests.
4. Review the generated diff with the source change.

The skill explains when to use a capability; the tool reference owns exhaustive signatures and the support matrix owns verified compatibility claims.
