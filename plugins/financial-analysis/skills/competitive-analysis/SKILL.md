---
name: competitive-analysis
description: 竞争格局分析：市场定位、竞品对比、玩家拆解、战略含义，并默认调用 obsidian-markdown 保存为 Obsidian Markdown 研报。
---

# Competitive Landscape Markdown Note

Build a complete competitive landscape research note. Output an Obsidian Markdown file, not a PowerPoint deck. Do not create `.pptx`, slides, or deck outlines in this skill.

## Required Companion Skill

Before writing the final file, load and follow the `obsidian-markdown` skill. Use its rules for frontmatter, Markdown tables, callouts, wikilinks, embeds, and external links.

## Output Contract

Save the final analysis as a `.md` file in the user's Obsidian vault.

Default paths:

- Single company: `03-Trading/个股分析/{company}/{company}_竞争格局分析_{YYYY-MM-DD}.md`
- Industry or theme: `03-Trading/行业分析/{target}/{target}_竞争格局分析_{YYYY-MM-DD}.md`

If the user gives a path, use that exact path. Create missing folders when needed.

Required frontmatter for a company note:

```yaml
---
title: {company}竞争格局分析
date: {YYYY-MM-DD}
company: {company}
ticker: {ticker}
tags:
  - 个股分析
  - 竞争格局
status: draft
generated_by:
  plugin: financial-analysis
  skill: competitive-analysis
---
```

For industry or theme notes, replace `company` and `ticker` with `industry` or `theme` fields.

## Workflow

### Step 1 - Confirm Scope

If the user provided a clear company, industry, or theme, proceed directly. Ask only for missing information that is truly required.

Clarify only when needed:

- **Scope** - Single target company with competitors around it, or multi-company side-by-side.
- **Competitor set** - Use exactly named competitors. If not named, choose reasonable direct, adjacent, and global benchmarks.
- **Audience and depth** - Quick read, full primer, or investment memo.
- **Investment context** - Include bull/base/bear scenarios only when useful for investment research.

If the user uploaded Excel/CSV data, preserve source values exactly. Do not silently recalculate or re-round source-file numbers.

### Step 2 - Research and Analyze

Use source quality in this order:

1. Annual reports, filings, audited statements.
2. Earnings calls, investor presentations, company announcements.
3. Regulator, exchange, or government/industry data.
4. Sell-side or third-party research for estimates and private-company context.
5. News for recent events, verified against primary sources when possible.

Make data comparable:

- Use the same fiscal period across competitors when possible.
- Flag FY/CY mismatches clearly.
- Use consistent metric definitions.
- Convert currency only when needed, and state exchange rate/date.
- Mark missing data as `N/A` or explain why unavailable.

### Step 3 - Write the Markdown Note

Use this default structure unless the user asks otherwise:

```markdown
# {target}竞争格局分析

> [!note] 口径说明
> 说明覆盖范围、数据口径、时间点和非投资建议。

## 一句话结论

## 关键判断

## 行业如何赚钱

## {target}画像

## 竞品地图

## 2x2 定位

## 国内竞品拆解

## 海外竞品拆解

## 横向财务对比

## 护城河评估

## 战略含义

## 投资情景

## 风险

## 结论

## 资料来源
```

For non-investment strategy work, replace `投资情景` with `战略情景` or remove it.

### Step 4 - Save and Verify

After writing the `.md` file:

1. Read back the first lines to confirm frontmatter and title.
2. Check that Markdown tables are valid.
3. Check that `## 资料来源` exists and all important numbers are source-backed.
4. Report the saved file path to the user.

## Analysis Modules

### Industry-defining Metrics

Before comparing players, identify the 3-5 metrics the industry actually runs on. Examples:

| Industry | Key metrics |
|---|---|
| SaaS | ARR, NRR, CAC payback, LTV/CAC, Rule of 40 |
| Payments | GPV, take rate, attach rate, transaction margin |
| Marketplaces | GMV, take rate, buyer/seller ratio, repeat rate |
| Retail | Same-store sales, inventory turns, sales per sq ft |
| Logistics | Volume, cost per unit, on-time delivery %, capacity utilization |

For unlisted industries, choose metrics investors and operators benchmark on.

### Competitor Mapping

Group competitors by the lens that fits the market:

- Business model - platform / vertical / horizontal.
- Segment - enterprise / SMB / consumer.
- Posture - direct / adjacent / emerging.
- Origin - incumbent / disruptor / new entrant.
- Geography - domestic / overseas / global.

### Positioning Visualization

Represent positioning in Markdown-friendly form:

- Use a 2x2 table when two factors dominate.
- Use a tier table when companies cluster naturally.
- Use a value-chain table for vertical industries.
- Use Mermaid only when it adds clarity and remains readable in Obsidian.

### Competitor Deep-dives

Use two compact tables per important competitor when data supports it.

Metrics:

```markdown
| Metric | Value |
|---|---:|
| Revenue | {value} |
| Growth | {value} |
| Gross margin | {value} |
| Profitability | {value} |
| Cash flow | {value} |
```

Qualitative:

```markdown
| Category | Assessment |
|---|---|
| Business | What they do in one sentence |
| Strengths | 2-3 concise points |
| Weaknesses | 2-3 concise points |
| Strategy | Current priorities |
```

### Comparative Analysis

Compare across the same dimensions and show the actual values, not just ratings.

```markdown
| Dimension | Company A | Company B | Company C |
|---|---|---|---|
| Scale | 强：$160B | 中：$45B | 弱：$8B |
| Growth | 中：+26% | 强：+35% | 中：+22% |
| Margins | 中：7.5% | 弱：3.2% | 强：15% |
```

### Moat and Synthesis

Assess durable advantages and structural vulnerabilities:

| Moat | What to assess |
|---|---|
| Network effects | User/supplier flywheel strength |
| Switching costs | Integration depth, contract lock-in, workflow dependency |
| Scale economies | Unit cost or procurement advantages at volume |
| Intangible assets | Brand, proprietary data, licenses, patents |
| Channel/ecosystem | Partner network, developer ecosystem, installed base |

For investment contexts, include bull/base/bear scenarios:

```markdown
| Scenario | Probability | Key driver | Result |
|---|---:|---|---|
| Bull | 30% | Market share gains, margin expansion | ... |
| Base | 50% | Current trajectory continues | ... |
| Bear | 20% | Competitive pressure, margin compression | ... |
```

## Quality Checklist

Before finishing:

- The final artifact is a saved `.md` file, not a PPT/deck.
- Frontmatter is valid YAML.
- `generated_by.plugin` and `generated_by.skill` are present.
- The note path matches the user request or default path.
- Every named competitor and requested data point is covered.
- Tables render as valid Markdown.
- Internal vault notes use wikilinks; external sources use Markdown links.
- Every important number is source-backed.
- `## 资料来源` is present.
