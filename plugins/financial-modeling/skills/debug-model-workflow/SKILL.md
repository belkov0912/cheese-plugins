---
name: debug-model-workflow
description: 调试和审计财务模型错误。
---

# /debug-model Workflow

> Codex note: This skill was migrated for Codex. When upstream text says to load or invoke a skill, use the matching Codex skill by name. Prefer Codex file/artifact tooling for spreadsheets, presentations, and documents; treat live Office JS add-in paths as legacy upstream guidance unless the user explicitly provides that environment.

This is the Codex-native equivalent of the upstream `/debug-model` slash command. If arguments are missing, ask only for the information needed to continue.

Load the `audit-xls` skill with scope **model** and audit the specified financial model for broken formulas, balance sheet imbalances, hardcoded overrides, circular references, and logic errors — including the full model-integrity checks (BS balance, cash tie-out, roll-forwards, model-type-specific bugs).

If a file path is provided, use it. Otherwise ask the user for the model to review.
