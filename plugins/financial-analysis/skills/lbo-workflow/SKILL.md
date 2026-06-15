---
name: lbo-workflow
description: 为 PE 收购构建 LBO 模型。
---

# /lbo Workflow

> Codex note: This skill was migrated for Codex. When upstream text says to load or invoke a skill, use the matching Codex skill by name. Prefer Codex file/artifact tooling for spreadsheets, presentations, and documents; treat live Office JS add-in paths as legacy upstream guidance unless the user explicitly provides that environment.

This is the Codex-native equivalent of the upstream `/lbo` slash command. If arguments are missing, ask only for the information needed to continue.

Load the `lbo-model` skill and build a leveraged buyout model for the specified company or deal.

If a company name is provided as an argument, use it. Otherwise ask the user for the target company and deal parameters.
