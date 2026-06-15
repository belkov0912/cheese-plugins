---
name: screen-workflow
description: 运行选股筛选或生成投资想法。
---

# /screen Workflow

> Codex note: This skill was migrated for Codex. When upstream text says to load or invoke a skill, use the matching Codex skill by name. Prefer Codex file/artifact tooling for spreadsheets, presentations, and documents; treat live Office JS add-in paths as legacy upstream guidance unless the user explicitly provides that environment.

This is the Codex-native equivalent of the upstream `/screen` slash command. If arguments are missing, ask only for the information needed to continue.

Load the `idea-generation` skill and run quantitative screens or thematic sweeps to surface new investment ideas.

If criteria are provided, use them. Otherwise ask the user what they're looking for (long/short, sector, style, theme).
