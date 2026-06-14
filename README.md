# cheese-plugins

Personal Agent plugin workspace for finding my cheese.

`cheese-plugins` is a small, practical workspace for collecting reusable
Agent building blocks: plugins, skills, slash commands, agents, templates, and
maintenance scripts. The name comes from *Who Moved My Cheese?*: this repo is
the tool bench for finding, testing, and packaging my own cheese.

## Install

Register this Git repo as a Codex plugin marketplace once:

```bash
codex plugin marketplace add git@github.com:belkov0912/cheese-plugins.git
```

Then install the plugin you want:

```bash
codex plugin add cheese-core@cheese-plugins
codex plugin add financial-modeling@cheese-plugins
codex plugin add investment-research@cheese-plugins
codex plugin add earnings-research@cheese-plugins
codex plugin add research-publishing@cheese-plugins
codex plugin add serenity-skill@cheese-plugins
```

After repo changes, pull the latest marketplace snapshot and reinstall the
plugin you changed:

```bash
codex plugin marketplace upgrade cheese-plugins
codex plugin add <plugin-name>@cheese-plugins
```

For local development before pushing, register the working tree directly:

```bash
codex plugin marketplace add /Users/jiananliu/work/project/cheese-plugins
```

Start a new Codex thread after reinstalling so new skills and plugin metadata
are picked up.

## Structure

```text
cheese-plugins/
  .agents/
    plugins/
      marketplace.json      # Codex plugin marketplace index
  plugins/                  # Installable plugin bundles
    cheese-core/
      .codex-plugin/
        plugin.json
      skills/
      commands/
      agents/
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

- `plugins/`: installable plugin bundles grouped by workflow. Each plugin owns
  its skills under `plugins/<plugin-name>/skills/`.
- There is no top-level `skills/` source copy. The plugin bundle is the source
  of truth.

| Plugin | Scope | Included skills |
| --- | --- | --- |
| `cheese-core` | Core reasoning | `zongju-thinking` |
| `financial-modeling` | Models, valuation, spreadsheet checks | `3-statement-model`, `dcf-model`, `lbo-model`, `comps-analysis`, model update/build workflows, `audit-xls`, `clean-data-xls`, `xlsx-author` |
| `investment-research` | Idea generation, sector work, catalysts, thesis tracking | `idea-generation`, `screen-workflow`, `sector-overview`, `competitive-analysis`, `catalyst-calendar`, `thesis-tracker` and related workflows |
| `earnings-research` | Earnings previews, post-earnings notes, morning notes | `earnings-preview`, `earnings-analysis`, `earnings-reviewer`, `morning-note` and related workflows |
| `research-publishing` | Coverage reports, deck checks, PowerPoint output | `initiating-coverage`, `initiate-workflow`, `ib-check-deck`, `deck-refresh`, PPT template and PPTX skills |
| `serenity-skill` | Serenity-inspired supply-chain bottleneck research | `serenity-skill` from [muxuuu/serenity-skill](https://github.com/muxuuu/serenity-skill), MIT |

## Add A Skill

```bash
scripts/new-skill.sh financial-modeling my-skill "Short description of when to use it"
```

Then edit:

```text
plugins/financial-modeling/skills/my-skill/SKILL.md
plugins/financial-modeling/skills/my-skill/agents/openai.yaml
```

Use the package table above to choose the plugin. If the skill starts a new
workflow, create a new plugin instead of adding it to `cheese-core`.

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

It also appends the plugin to `.agents/plugins/marketplace.json`.

## Validate

Run:

```bash
scripts/validate.sh
```

The validator checks:

- required files exist
- `.agents/plugins/marketplace.json` and plugin manifests parse as JSON
- marketplace entries point to existing plugin paths
- every plugin under `plugins/` is registered in the marketplace
- plugin names match their folders
- skill frontmatter contains `name` and `description`
- `agents/openai.yaml` includes basic UI metadata when present
- obvious manifest placeholders are absent

## Sync Sources

Older standalone skill copies may exist outside this repo, for example under
`/Users/jiananliu/.codex/skills/` or the Obsidian vault's `.agents/skills/`.
When importing from those locations, copy the skill into the matching
`plugins/<plugin-name>/skills/` directory. Do not add a top-level `skills/`
copy.

## Naming

- Use lower-case kebab-case: `zongju-thinking`, `cheese-core`.
- Plugin folder name must match `.codex-plugin/plugin.json` `name`.
- Skill folder name should match `SKILL.md` frontmatter `name`.
- Avoid generic names like `helper`, `tool`, or `workflow` unless the scope is
  genuinely broad.
