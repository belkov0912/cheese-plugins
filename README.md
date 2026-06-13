# cheese-plugins

Personal Agent plugin workspace for finding my cheese.

`cheese-plugins` is a small, practical workspace for collecting reusable
Agent building blocks: plugins, skills, slash commands, agents, templates, and
maintenance scripts. The name comes from *Who Moved My Cheese?*: this repo is
the tool bench for finding, testing, and packaging my own cheese.

## Structure

```text
cheese-plugins/
  marketplace.json          # Local plugin marketplace index
  plugins/                  # Installable plugin bundles
    cheese-core/
      .codex-plugin/
        plugin.json
      skills/
      commands/
      agents/
  skills/                   # Canonical standalone skill sources
  commands/                 # Canonical standalone command sources
  agents/                   # Canonical standalone agent sources
  templates/                # Reusable skeletons and snippets
  docs/                     # Notes that are too large for README
  examples/                 # Small usage examples
  scripts/
    validate.sh
    new-skill.sh
    new-plugin.sh
```

## Current Package

- `plugins/cheese-core`: first local plugin bundle.
- `skills/zongju-thinking`: canonical source for the 总局思维 skill.
- `plugins/cheese-core/skills/zongju-thinking`: packaged copy for the plugin.

## Add A Skill

```bash
scripts/new-skill.sh my-skill "Short description of when to use it"
```

Then edit:

```text
skills/my-skill/SKILL.md
skills/my-skill/agents/openai.yaml
```

When the skill should ship inside the default plugin, copy it into:

```text
plugins/cheese-core/skills/my-skill/
```

Keep `SKILL.md` concise. Put only the instructions the agent needs at runtime.

## Add A Plugin

```bash
scripts/new-plugin.sh my-plugin "Short plugin description"
```

This creates:

```text
plugins/my-plugin/.codex-plugin/plugin.json
plugins/my-plugin/skills/
plugins/my-plugin/commands/
plugins/my-plugin/agents/
```

It also appends the plugin to `marketplace.json`.

## Validate

Run:

```bash
scripts/validate.sh
```

The validator checks:

- required files exist
- `marketplace.json` and plugin manifests parse as JSON
- marketplace entries point to existing plugin paths
- plugin names match their folders
- skill frontmatter contains `name` and `description`
- `agents/openai.yaml` includes basic UI metadata when present
- obvious manifest placeholders are absent

## Sync Targets

Codex skill source:

```text
/Users/jiananliu/.codex/skills/zongju-thinking
```

Obsidian skill copy:

```text
/Users/jiananliu/Library/Mobile Documents/iCloud~md~obsidian/Documents/Obsidian Vault/.agents/skills/zongju-thinking
```

This repo keeps its own canonical copy under `skills/`. If the Codex or
Obsidian copy changes first, sync the newer version back here before packaging
or editing the plugin bundle.

## Naming

- Use lower-case kebab-case: `zongju-thinking`, `cheese-core`.
- Plugin folder name must match `.codex-plugin/plugin.json` `name`.
- Skill folder name should match `SKILL.md` frontmatter `name`.
- Avoid generic names like `helper`, `tool`, or `workflow` unless the scope is
  genuinely broad.

