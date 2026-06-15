# cheese-plugins

Personal Agent plugin workspace for finding my cheese.

`cheese-plugins` is a small, practical workspace for collecting reusable
Agent building blocks: plugins, skills, slash commands, agents, templates, and
maintenance scripts. The name comes from *Who Moved My Cheese?*: this repo is
the tool bench for finding, testing, and packaging my own cheese.

## Install

This repo uses the official `.claude-plugin/` marketplace format, which is read
by **both Claude Code and codex** — one set of manifests, two runtimes.

Register the marketplace once:

```bash
# Claude Code: in-session
/plugin marketplace add git@github.com:belkov0912/cheese-plugins.git

# codex: in the terminal
codex plugin marketplace add git@github.com:belkov0912/cheese-plugins.git
```

For local development before pushing, register the working tree directly with
its absolute path instead of the Git URL.

Then browse, install, update, and remove plugins from the interactive UI: type
`/plugins` (Claude Code) or `/plugins` in codex, pick `cheese-plugins`, and
operate on the plugin you want. Available plugins: `cheese-core`,
`financial-analysis`, `equity-research`, `serenity-skill`,
`goal-meta-skill`.

Start a new thread after reinstalling so new skills and plugin metadata are
picked up.

## Structure

```text
cheese-plugins/
  .claude-plugin/
    marketplace.json        # Plugin marketplace index (Claude Code + codex)
  plugins/                  # Installable plugin bundles
    cheese-core/
      .claude-plugin/
        plugin.json         # Plugin manifest
      skills/               # Each skill is skills/<name>/SKILL.md
  scripts/
    validate.sh
    new-skill.sh
    new-plugin.sh
```

Skills are shared across runtimes: a skill is just `skills/<name>/SKILL.md`
with `name` and `description` frontmatter. Add `commands/` or `agents/` to a
plugin only when that plugin actually ships them.

## Current Package

- `plugins/`: installable plugin bundles grouped by workflow. Each plugin owns
  its skills under `plugins/<plugin-name>/skills/`.
- There is no top-level `skills/` source copy. The plugin bundle is the source
  of truth.

| Plugin | Scope | Included skills |
| --- | --- | --- |
| `cheese-core` | Core reasoning | `zongju-thinking` |
| `financial-analysis` | Models, valuation, spreadsheet checks, deck QC | `dcf-model`, `comps-analysis`, `lbo-model`, `3-statement-model`, `competitive-analysis`, `audit-xls`, `clean-data-xls`, `xlsx-author`, `ib-check-deck`, `deck-refresh`, `ppt-template-creator`, `pptx-author`, `model-builder` and related workflows. Adapted from Anthropic FSI `financial-analysis` |
| `equity-research` | Earnings, coverage, ideas, catalysts, thesis tracking | `earnings-preview`, `earnings-analysis`, `earnings-reviewer`, `morning-note`, `initiating-coverage`, `idea-generation`, `sector-overview`, `catalyst-calendar`, `thesis-tracker`, `model-update`, `market-researcher` and related workflows. Adapted from Anthropic FSI `equity-research` |
| `serenity-skill` | Serenity-inspired supply-chain bottleneck research | `serenity-skill` from [muxuuu/serenity-skill](https://github.com/muxuuu/serenity-skill), MIT |
| `goal-meta-skill` | Turn vague tasks into strong `/goal` commands | adapted from [joeseesun/qiaomu-goal-meta-skill](https://github.com/joeseesun/qiaomu-goal-meta-skill), MIT (© 向阳乔木) |

## Add A Skill

```bash
scripts/new-skill.sh financial-analysis my-skill "Short description of when to use it"
```

Then edit:

```text
plugins/financial-analysis/skills/my-skill/SKILL.md
```

Use the package table above to choose the plugin. If the skill starts a new
workflow, create a new plugin instead of adding it to `cheese-core`.

Keep `SKILL.md` concise. Put only the instructions the agent needs at runtime.

## Add A Plugin

```bash
scripts/new-plugin.sh my-plugin "Short plugin description" general
```

The third argument is the marketplace category (defaults to `general`). This
creates:

```text
plugins/my-plugin/.claude-plugin/plugin.json
plugins/my-plugin/skills/
```

It also appends the plugin to `.claude-plugin/marketplace.json`.

## Validate

Run:

```bash
scripts/validate.sh
```

The validator checks:

- `.claude-plugin/marketplace.json` and plugin manifests parse as JSON
- each marketplace entry has a string `source`, `description`, and `category`,
  and points to an existing plugin with a `.claude-plugin/plugin.json`
- every plugin under `plugins/` is registered in the marketplace
- plugin manifest `name` matches its folder and its marketplace entry
- plugin manifests have `version`, `description`, and `author.name`
- skill frontmatter contains `name` and `description`, and `name` matches its folder
- obvious manifest placeholders are absent

## Sync Sources

Older standalone skill copies may exist outside this repo, for example under
`~/.claude/skills/` or `~/.codex/skills/`. When importing from those locations,
copy the skill into the matching `plugins/<plugin-name>/skills/` directory. Do
not add a top-level `skills/` copy.

## Naming

- Use lower-case kebab-case: `zongju-thinking`, `cheese-core`.
- Plugin folder name must match `.claude-plugin/plugin.json` `name`.
- Skill folder name should match `SKILL.md` frontmatter `name`.
- Avoid generic names like `helper`, `tool`, or `workflow` unless the scope is
  genuinely broad.
