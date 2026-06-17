---
name: pptx-author
description: 在本地生成 .pptx 文件，适合无实时 PowerPoint 环境的报告/演示稿输出。
---

# pptx-author


Use this skill when running **headless** (managed-agent / CMA mode) and you need to deliver a PowerPoint deck as a **file artifact** rather than editing a live document via `mcp__office__powerpoint_*`.

## Output contract

- First follow the trading output policy in `03-Trading/AGENTS.md`. For financial research inside this Obsidian vault, write the deck into the relevant company, theme, or task folder under `03-Trading/`, not the workspace root.
- Use `./out/<name>.pptx` only as a fallback when no project output location can be inferred and the user has not provided one. Create `./out/` if it does not exist.
- Return the path in your final message so the orchestration layer can collect it.

## How to build the deck

Write a short Python script and run it with Bash. Use `python-pptx`:

```python
from pptx import Presentation
from pptx.util import Inches, Pt

prs = Presentation("./templates/firm-template.pptx")  # if a template is provided
# or: prs = Presentation()

slide = prs.slides.add_slide(prs.slide_layouts[5])    # title-only
slide.shapes.title.text = "Valuation Summary"
# ... add tables / charts / text boxes ...

output_path = "./out/pitch-<target>.pptx"      # fallback only; prefer the AGENTS.md target path
prs.save(output_path)
```

## Conventions (mirror the live-Office `pitch-deck` skill)

- **One idea per slide.** Title states the takeaway; body supports it.
- **Every number traces to the model.** If a figure comes from `./out/model.xlsx`, footnote the sheet and cell.
- **Use the firm template** when one is mounted at `./templates/`; otherwise default layouts.
- **Charts**: prefer embedding a PNG rendered from the model over native pptx charts when fidelity matters.
- **No external sends.** This skill writes a file; it never emails or uploads.

## When NOT to use

If `mcp__office__powerpoint_*` tools are available (Cowork plugin mode), use those instead — they drive the user's live document with review checkpoints. This skill is the file-producing fallback for headless runs.
