---
name: thesis-workflow
description: 创建或更新个股投资 thesis。
---

# /thesis Workflow

> Codex note: This skill was migrated for Codex. When upstream text says to load or invoke a skill, use the matching Codex skill by name. Prefer Codex file/artifact tooling for spreadsheets, presentations, and documents; treat live Office JS add-in paths as legacy upstream guidance unless the user explicitly provides that environment.

This is the Codex-native equivalent of the upstream `/thesis` slash command. If arguments are missing, ask only for the information needed to continue.

Load the `thesis-tracker` skill to create a new thesis or update an existing one with new data points.

If a ticker is provided, use it. Otherwise ask the user which position to review.
