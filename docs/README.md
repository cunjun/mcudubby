# McuBuddy Docs

This directory contains the working documentation for `McuBuddy`. The top-level README files are
short product entry points; detailed setup, workflows, examples, validation, and tool indexes live
here.

## Start Here

Use these first when setting up a new board:

1. [Quickstart](quickstart.md)
2. [Generic Board Workflow](generic-board-workflow.md)
3. [Windows MCP Config Example](windows-mcp-config-example.md), if the MCP client runs on Windows
4. [Board Validation Guide](board-validation-guide.md)

## AI Assistant Operation

Use these when an AI assistant is driving or planning a debug session:

1. [AI Playbook](ai-playbook.md)
2. [AI Examples](ai-examples.md)
3. [Peripheral Actuator Debug Playbook](peripheral-actuator-debug-playbook.md)

`AI Playbook` is the default operating guide. `AI Examples` holds short scenario sequences.
The actuator playbook is a specialized guide for cases where the firmware path works but the
physical output still does not move.

## Reference

- [Tool Reference](tool-reference.md) - grouped MCP tool index
- [Support Matrix](support-matrix.md) - backend support, target metadata, validation coverage, and limits
- [MCP Usage Example](mcp-usage-example.md) - compact example session shape
- [Codex Runbook](codex-runbook.md) - Codex development, validation, and commit conventions
- [mcubug Codex/CC Skill](mcubug-skill.md) - install and maintain the bundled assistant skill
- [v0.6 Roadmap](v0.6-roadmap.md) - current post-core roadmap

## Reading Orders

### Bring Up A New Board

1. [Quickstart](quickstart.md)
2. [Generic Board Workflow](generic-board-workflow.md)
3. [Board Validation Guide](board-validation-guide.md)
4. [Support Matrix](support-matrix.md)

### Configure A Windows MCP Client

1. [Windows MCP Config Example](windows-mcp-config-example.md)
2. [Quickstart](quickstart.md)
3. [Generic Board Workflow](generic-board-workflow.md)

### Improve Diagnosis Tools

1. [AI Playbook](ai-playbook.md)
2. [AI Examples](ai-examples.md)
3. [Peripheral Actuator Debug Playbook](peripheral-actuator-debug-playbook.md)
4. [Board Validation Guide](board-validation-guide.md)

## Documentation Ownership

To keep the docs from drifting:

- Put public positioning and the shortest first-session shape in the root README files.
- Put install and first-board setup details in [Quickstart](quickstart.md).
- Put arbitrary target, CMSIS-Pack, Keil project, and smoke-test details in
  [Generic Board Workflow](generic-board-workflow.md).
- Put scenario decision trees in [AI Playbook](ai-playbook.md), with compact worked examples in
  [AI Examples](ai-examples.md).
- Put backend status, validated boards, partial paths, and known limits in
  [Support Matrix](support-matrix.md).
- Put the complete grouped tool list in [Tool Reference](tool-reference.md).
- Put Codex development, verification, and commit conventions in [Codex Runbook](codex-runbook.md).
- Put bundled Codex/CC skill installation and sync notes in [mcubug Codex/CC Skill](mcubug-skill.md).

When adding board support, prefer:

- configuration over hard-coded target branches
- CMSIS-Pack/SVD/project files over copied constants
- read-only smoke tests before flashing or reset-heavy workflows
- unit tests for new parsing or fallback behavior
