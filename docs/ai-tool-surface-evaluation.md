# GPT-5.6 Tool-Surface Evaluation

This document defines the repeatable evaluation used to compare the legacy `full` tool catalog with
the v0.5.2 `core` profile. The machine-readable scenario source is
`tests/evaluation/gpt5p6_scenarios.yaml`.

## Fields

Each scenario records the same fields:

- `id`
- `title`
- `input`
- `completion_criteria`
- `required_evidence`
- `forbidden_operations`
- `baseline.executed`
- `baseline.reason`

## Baseline Status

The initial baseline is intentionally marked as not executed because this workspace did not have
real MCU boards, probes, Keil MDK, or public firmware artifacts attached during implementation.
Mock outputs must not be counted as hardware success. A real run should update the scenario results
with the model version, active profile, task completion, required evidence, invalid tool calls,
high-risk tool calls, total calls, and failure reason when a scenario cannot complete.

## Comparison Rule

The `core` profile passes the tool-surface comparison only when it completes or clearly blocks on
the same representative flows as `full`, avoids calls to hidden tools, and reduces invalid or
high-risk tool selection. Hardware success can only be claimed when a real board path has been run
and recorded in the validation guide or validation records.
