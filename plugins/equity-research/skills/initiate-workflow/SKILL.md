---
name: initiate-workflow
description: 创建一篇首次覆盖/深度覆盖报告。
---

# /initiate Workflow

> Codex note: This skill was migrated for Codex. When upstream text says to load or invoke a skill, use the matching Codex skill by name. Prefer Codex file/artifact tooling for spreadsheets, presentations, and documents; treat live Office JS add-in paths as legacy upstream guidance unless the user explicitly provides that environment.

This is the Codex-native equivalent of the upstream `/initiate` slash command. If arguments are missing, ask only for the information needed to continue.

Load the `initiating-coverage` skill and begin the 5-task workflow to create an institutional-quality initiation report.

If a ticker is provided, use it. Otherwise ask the user which company to initiate on.
