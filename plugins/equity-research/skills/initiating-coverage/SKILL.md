---
name: initiating-coverage
description: 生成机构风格首次覆盖报告；中文场景默认使用中文研报表达、中文标题、中文单位和中文可读性标准；默认自动执行 Task 1 公司研究、Task 2 财务建模、Task 3 估值分析，并在 Task 4 图表生成和 Task 5 报告组装前询问确认。
---

# 首次覆盖 / Initiating Coverage


通过 5 个任务生成机构风格首次覆盖研究。默认情况下，Task 1-3 作为核心流程自动执行；Task 4 图表生成和 Task 5 报告组装属于更重的生产任务，必须在完成前置任务后再询问用户是否继续。

## Overview

This skill produces comprehensive first-time coverage reports following institutional standards. For Chinese users, A-share/H-share/HK/China coverage, or work inside a Chinese Obsidian vault, the deliverables must read like Chinese institutional research rather than a translated English template.

**Default Font**: Chinese deliverables should use readable Chinese fonts such as PingFang SC, Microsoft YaHei, Source Han Sans, SimSun, or a platform-equivalent CJK font. Use Times New Roman only for English deliverables or when explicitly requested.

## 语言与可读性默认规则

这些规则优先于各 Task 文件中的英文示例模板：

- 默认跟随用户语言。用户用中文提问、标的是 A 股/港股/中资公司、或输出在中文 Obsidian Vault 内时，Markdown、DOCX 正文、章节标题、表格列名、图表标题、图例、注释和结论均优先使用中文。
- 不要保留英文模板腔标题，除非用户明确要求英文。将 `COMPANY RESEARCH REPORT` 改为 `首次覆盖研究文档`，`Investment View` 改为 `投资观点`，`Price Target` 改为 `目标价`，`Upside` 改为 `上涨空间`，`DCF Analysis` 改为 `DCF 估值`，`Comparable Companies` 改为 `可比公司估值`，`Risk Factors` 改为 `风险提示`。
- 评级默认使用中文研报口径：`买入`、`增持`、`中性`、`减持`、`卖出`。需要兼容海外口径时，可写成 `买入（BUY）`，但中文在前。
- 单位使用中文金融写法：`亿元`、`百万元`、`万股`、`元/股`、`美元/股`、`%`。A 股公司默认使用人民币和 `元/股`，不要输出 `$M`、`$XX.XX`、`Mkt Cap` 这类英文单位列名。
- 写作要结论先行：每个核心章节先给 2-4 条判断，再展开证据、假设和风险。避免把资料罗列成流水账。
- 可读性优先：段落控制在 3-6 行；长表必须有中文列名和单位；关键分歧用 `事实 / 判断 / 假设 / 证伪点` 拆开；英文缩写第一次出现时解释中文含义。
- 资料源按市场选择。A 股优先使用交易所公告、巨潮资讯、公司年报/季报、投资者关系材料、行业协会和监管公开数据；美股再优先使用 SEC 文件。
- 交付前必须检查英文残留：搜索 `COMPANY RESEARCH`、`Investment View`、`Price Target`、`Upside`、`BUY/HOLD/SELL`、`$M`、`Mkt Cap`、`Source:`。除专有名词、股票代码、英文公司名和必要引用外，发现模板残留要改成中文。

## Obsidian Output Location

When running inside this Obsidian vault, do not write initiating-coverage deliverables to the workspace root `./out/` unless the user explicitly asks for a temporary output directory.

Use this project folder:

`03-Trading/个股分析/<Company>/首次覆盖_<YYYYMMDD>/`

If `<Company>` already has an existing company folder under a deeper category, such as `03-Trading/个股分析/半导体/江化微/`, reuse that existing company folder and create `首次覆盖_<YYYYMMDD>/` inside it.

Within the project folder, write each task to its task subfolder:

- `Task1_Research/[Company]_Research_Document_[Date].md`
- `Task2_Model/[Company]_Financial_Model_[Date].xlsx`
- `Task3_Valuation/[Company]_Valuation_Analysis_[Date].md`
- `Task4_Charts/[Company]_Charts_[Date].zip`
- `Task5_Report/[Company]_Initiation_Report_[Date].docx`

If the vault root cannot be identified by the presence of `03-Trading`, ask the user where to save the deliverable before writing files.

---

## ⚠️ CRITICAL: Automated Core Pipeline, Confirm Before Production Tasks

**THIS SKILL RUNS TASKS 1-3 AUTOMATICALLY BY DEFAULT, THEN ASKS BEFORE TASK 4 AND TASK 5.**

### If User Requests Full Pipeline or an Initiation Report

When user requests:
- "Create a coverage initiation report for [Company]"
- "Write an initiation report for [Company]"
- "Do the entire equity research process for [Company]"
- "Complete all 5 tasks for [Company]"
- Any request that implies running multiple tasks or the entire workflow

**REQUIRED RESPONSE:**

1. **Start the automated core pipeline immediately:**
   ```
   开始为 [Company] 执行首次覆盖核心流程。

   我会自动完成：
   1. 公司研究
   2. 财务建模
   3. 估值分析

   Task 3 完成后，我会再询问是否继续：
   4. 图表生成
   5. 报告组装
   ```

2. **If Task 2 financial data cannot be accessed automatically:**
   ```
   我可以先完成 Task 1 公司研究，但 Task 2 财务建模需要历史财务数据。
   目前无法自动取得 [Company] 的年报、财务报表或用户提供的历史财务数据。
   请提供财务报表，或确认可使用的数据源后再继续 Task 2。
   ```

3. **After Task 3 completes, ask before Task 4:**
   ```
   Task 1-3 已完成。是否继续 Task 4（图表生成）？
   ```

4. **After Task 4 completes, ask before Task 5:**
   ```
   Task 4 已完成。是否继续 Task 5（报告组装）？
   ```

### Task Execution Rules

- ✅ If the user asks for an initiation report, full pipeline, or does not specify a task, automatically execute Tasks 1, 2, and 3 in sequence
- ✅ If the user explicitly requests only one task, execute only that task
- ✅ Always verify prerequisites before starting each task
- ✅ Task 2 may proceed automatically for public companies when SEC filings or other reliable financial statements are accessible
- ✅ Task 3 may proceed automatically only after Task 2 output exists and is accessible
- ✅ After completing Task 3, stop and ask whether to execute Task 4
- ✅ After completing Task 4, stop and ask whether to execute Task 5
- ❌ Never execute Task 4 without explicit user confirmation after Tasks 1-3 are complete
- ❌ Never execute Task 5 without explicit user confirmation after Task 4 is complete
- ❌ Never execute Tasks 3-5 without verifying required inputs exist

### ⚠️ Deliverables Policy: NO SHORTCUTS

**DELIVER ONLY THE SPECIFIED OUTPUTS. DO NOT CREATE EXTRA DOCUMENTS.**

Each task specifies exact deliverables. Do NOT create:
- ❌ "Completion summaries"
- ❌ "Executive summaries"
- ❌ "Quick reference guides"
- ❌ "Next steps documents"
- ❌ "Task completion reports"
- ❌ Any other "helpful" documentation not explicitly specified

**Why**: These extras waste context and are not part of the professional workflow.

**What TO deliver**:
- ✅ Task 1: Research document (.md) — **NOTHING ELSE**
- ✅ Task 2: Financial model (.xlsx) — **NOTHING ELSE**
- ✅ Task 3: Valuation analysis (.md) + Excel tabs added to Task 2 file — **NOTHING ELSE**
- ✅ Task 4: Charts zip file (.zip) — **NOTHING ELSE**
- ✅ Task 5: Final report (.docx) — **NOTHING ELSE**

**If a deliverable is not listed above, DO NOT CREATE IT.**

---

## Task Selection

Select which task to execute:

| Task | 名称 | 前置条件 | 输出 |
|------|------|--------------|--------|
| **1** | 公司研究 | 公司名称/股票代码 | 6,000-8,000 字研究文档 |
| **2** | 财务建模 | 年报/财报/历史财务数据 | Excel 财务模型（6 个核心表） |
| **3** | 估值分析 | Task 2 财务模型 | 估值分析 + 目标价 |
| **4** | 图表生成 | Task 1、2、3 + 外部市场数据 | 25-35 张 PNG/JPG 图表 |
| **5** | 报告组装 | 全部前置任务（Task 1-4） | 30-50 页 DOCX 报告 |

---

## How to Use This Skill

### User Request Patterns and Responses

**Pattern 1: User specifies a specific task**
```
User: "Use initiating-coverage, Task 1 for Tesla"
Response: ✅ Execute Task 1 immediately
```

**Pattern 2: User asks for "initiation report" or "full pipeline"**
```
User: "Create a coverage initiation report for Tesla"
Response: ✅ Automatically execute Tasks 1, 2, and 3 in sequence
         ✅ Stop after Task 3 and ask whether to proceed with Task 4
```

**Pattern 3: User wants to do "all tasks" or "entire workflow"**
```
User: "I want to complete all 5 tasks for Tesla"
Response: ✅ Automatically execute Tasks 1, 2, and 3 in sequence
         ✅ Ask for confirmation before Task 4
         ✅ Ask for confirmation before Task 5
```

### Correct Usage Examples

**Executing a single task:**
```
"Use initiating-coverage skill, Task 1 for Tesla"
"Do Task 2 of initiating-coverage for Tesla"
"Run Task 3 for Tesla using the initiating-coverage skill"
```

**Completing full report with automated core pipeline:**
```
Request 1: "Create an initiation report for Tesla"
           → Automatically run Task 1
           → Automatically run Task 2 if financial data is accessible
           → Automatically run Task 3 after the model is complete
           → Deliver Task 1-3 outputs
           → Ask whether to proceed with Task 4
Request 2: User confirms Task 4
           → Generate charts
           → Ask whether to proceed with Task 5
Request 3: User confirms Task 5
           → Assemble final report
```

### Task Execution Order

For a complete initiation report, Tasks 1-3 are the automated core pipeline and Tasks 4-5 are confirmation-gated production tasks:

```
Task 1 - Company Research (independent)
   ↓ [automatic]
Task 2 - Financial Modeling (requires public filings, statements, or user-provided financials)
   ↓ [automatic only after Task 2 verification passes]
Task 3 - Valuation Analysis (requires Task 2 output)
   ↓ [STOP: ask user whether to continue]
Task 4 - Chart Generation (requires Tasks 1, 2, 3 + external data)
   ↓ [STOP: ask user whether to continue]
Task 5 - Report Assembly (requires ALL previous task outputs)
```

**Note**: Tasks 1 and 2 can still be run individually when explicitly requested. In the automated core pipeline, run Task 1 first for business context, then Task 2, then Task 3. Tasks 3-5 have strict dependencies and must verify inputs before proceeding.

---

## Task 1: Company Research

**Purpose**: Research company's business, management, competitive position, industry, and risks.

**Prerequisites**: ✅ None (fully independent)
- Company name or ticker symbol

**Process**:
1. Verify company name/ticker provided
2. Load detailed instructions from references/task1-company-research.md
3. Execute qualitative research workflow
4. Deliver research document

**Output**: Company Research Document (6,000-8,000 words)
- 公司概览与发展历史
- 管理层履历与治理评估（每人 300-400 中文字 × 3-4 名高管）
- 产品与服务分析
- 行业概览
- 竞争格局分析（5-10 家竞品）
- 市场空间测算
- 风险提示（8-12 条）

**File name**: `[Company]_Research_Document_[Date].md`

**⚠️ DELIVER ONLY THIS 1 FILE. NO completion summaries, no extra documents.**

**⚠️ DO NOT TAKE SHORTCUTS:**
- ✅ Write full 6,000-8,000 words (not summaries)
- ✅ Complete 300-400 word bios for ALL 3-4 executives
- ✅ Analyze ALL 5-10 competitors thoroughly
- ✅ Cover all 8-12 risks across 4 categories
- ❌ Do not abbreviate sections to save time
- ❌ Do not skip any required sections

**Verification before proceeding**: None required for this task.

---

## Task 2: Financial Modeling

**Purpose**: Extract historical financials and build comprehensive Excel financial model with projections and scenarios.

**Prerequisites**: ⚠️ Verify before starting
- **Required**: Access to company financial data
  - For US public companies: Latest 10-K from SEC EDGAR
  - For A-share/H-share/HK companies: latest annual report, quarterly reports, exchange filings, CNINFO/SSE/SZSE/HKEX announcements, or company IR materials
  - For private companies: Financial statements or available estimates
  - OR: Pre-extracted historical financials provided by user
- **Optional**: Company research (Task 1) for business context

**Input Verification**:
```
BEFORE STARTING - Select approach:

Option A: Extract financials (most common)
- [ ] Have access to 10-K or financial statements?
- [ ] Ready to extract 3-5 years of data?

Option B: User provided pre-extracted financials
- [ ] Historical financials file received?
- [ ] Contains income statement, cash flow, balance sheet (3-5 years)?

Optional:
- [ ] Company research (Task 1) complete for context?
```

**Process**:
1. Verify access to financial data
2. Load detailed instructions from references/task2-financial-modeling.md
3. **Step 1**: Extract historical financials (if needed)
4. **Step 2+**: Build projection model with 6 essential tabs
5. Deliver Excel model

**Output**: Excel Financial Model (.xlsx)
- 6 essential tabs:
  1. **收入模型** - 产品拆分（20-30 行）+ 地区拆分（15-20 行）
  2. **利润表** - 完整 P&L，40-50 个科目，历史 3-5 年 + 预测 5 年
  3. **现金流量表** - 经营/投资/筹资活动，历史 + 预测
  4. **资产负债表** - 资产/负债/权益，历史 + 预测
  5. **情景假设** - 乐观/中性/悲观情景对比
  6. **DCF输入** - 为 Task 3 估值准备的自由现金流和估值参数

**File name**: `[Company]_Financial_Model_[Date].xlsx`

**⚠️ DELIVER ONLY THIS 1 FILE. NO completion summaries, no extra documents.**

**⚠️ DO NOT TAKE SHORTCUTS:**
- ✅ If extracting financials: Extract ALL line items from 3 financial statements (3-5 years)
- ✅ Build ALL 6 projection tabs completely with full detail
- ✅ Create detailed revenue model with 20-30 product rows AND 15-20 geography rows
- ✅ Build complete income statement with 40-50 line items (not abbreviated)
- ✅ Include full cash flow statement and balance sheet with all line items
- ✅ Complete ALL three scenarios (Bull/Base/Bear) with different parameters
- ❌ Do not create simplified/abbreviated versions
- ❌ Do not skip any of the 6 essential tabs
- ❌ Do not skip historical financials extraction if needed

**Verification before proceeding to Task 3**:
- [ ] Historical financials extracted (if needed) or provided
- [ ] Excel file created and can be opened
- [ ] Model has all 6 essential tabs (Revenue Model, Income Statement, Cash Flow, Balance Sheet, Scenarios, DCF Inputs)
- [ ] Historical data (3-5 years) incorporated
- [ ] Projections complete (5 years forward)
- [ ] Scenarios complete (Bull/Base/Bear)

---

## Task 3: Valuation Analysis

**Purpose**: Perform comprehensive valuation using DCF, comparables, and precedent transactions.

**Prerequisites**: ⚠️ Verify before starting
- **Required**: Financial model from Task 2
  - Projected income statements
  - Projected cash flows
  - Revenue and EBITDA forecasts
  - DCF inputs (unlevered FCF)

**⚠️ CRITICAL: DO NOT START THIS TASK UNLESS TASK 2 IS COMPLETE**

This task requires the financial model from Task 2. Starting without it will result in incomplete work.

**IF TASK 2 IS NOT COMPLETE**: Stop immediately and inform the user that Task 2 (Financial Modeling) must be completed first. Do not attempt to proceed or create placeholder valuations.

**Input Verification**:
```
BEFORE STARTING:
- [ ] Task 2 complete? (Financial model exists)
- [ ] Model file path/location known?
- [ ] Can access projected financials from model?

Required from model:
- [ ] Projected FCF (5 years)
- [ ] Revenue projections
- [ ] EBITDA projections
- [ ] Terminal year metrics
```

**Process**:
1. Verify financial model is accessible
2. Load detailed instructions from references/task3-valuation.md
3. Execute valuation workflow
4. Deliver valuation analysis

**Output**: Valuation Analysis (4-6 pages + Excel tabs)
- DCF analysis with sensitivity tables
- Comparable companies (5-10 peers with statistical summary)
- Precedent transactions (if applicable)
- Valuation football field
- **目标价**：XX 元/股（A 股/人民币口径）或对应交易币种
- **评级**：买入/增持/中性/减持/卖出
- **上涨空间**：XX%
- Key catalysts (3-5)

**Files**:
- `[Company]_Valuation_Analysis_[Date].md` (written analysis document)
- Excel tabs added to `[Company]_Financial_Model_[Date].xlsx` (from Task 2)
  - DCF tab with calculations
  - Sensitivity analysis tab
  - Comparable companies tab
  - Valuation summary tab

**⚠️ DELIVER ONLY: 1 markdown file + 4 tabs added to existing Excel. NO completion summaries, no extra documents.**

**⚠️ DO NOT TAKE SHORTCUTS:**
- ✅ Complete full DCF analysis with sensitivity matrix (not simplified)
- ✅ Analyze ALL 5-10 comparable companies with full data
- ✅ Include statistical summary in comps table (max/75th/median/25th/min)
- ✅ Create complete sensitivity analysis tab with multiple WACC and terminal growth scenarios
- ✅ Write full 4-6 pages of valuation analysis (not abbreviated)
- ✅ Research and justify price target with specific methodology
- ❌ Do not skip comparable company analysis
- ❌ Do not create simplified DCF without sensitivity

**Verification before proceeding to Task 4**:
- [ ] Price target determined
- [ ] Valuation uses multiple methods (DCF + Comps minimum)
- [ ] DCF sensitivity table complete
- [ ] Comparable companies table includes statistical summary

---

## Task 4: Chart Generation

**Purpose**: Generate 25-35 professional financial charts for the report.

**Prerequisites**: ⚠️ Verify before starting
- **Required**: Company research from Task 1
  - Company history and milestones (for timeline charts)
  - Management team and org structure (for org charts)
  - Product portfolio (for product charts)
  - Customer segmentation (for customer charts)
  - Competitive landscape (for competitive charts)
  - TAM analysis (for market size charts)
- **Required**: Financial model from Task 2 (with Task 3 valuation tabs added)
  - Revenue by product/geography data (Task 2 tabs)
  - Margin trends (Task 2 tabs)
  - Scenario comparison data (Task 2 tabs)
  - DCF sensitivity table (Task 3 tab in same Excel file)
  - Comparable companies data (Task 3 tab in same Excel file)
  - Valuation ranges (Task 3 tab in same Excel file)
- **Required**: External market data
  - Historical stock price data (Yahoo Finance, Bloomberg, etc.)
  - Historical valuation multiples (for historical trend charts)

**⚠️ CRITICAL: DO NOT START THIS TASK UNLESS TASKS 1, 2, AND 3 ARE COMPLETE**

This task requires outputs from all three previous tasks. Starting without them will result in incomplete charts.

**IF ANY OF TASKS 1, 2, OR 3 ARE NOT COMPLETE**: Stop immediately and inform the user which tasks need to be completed first. The specific requirements are:
- Task 1: Company research document (for 9 charts)
- Task 2: Financial model with all 6 tabs (for 8 charts)
- Task 3: Valuation tabs added to the model (for 6 charts)
- External data access (for 2 charts)

Do not attempt to create placeholder charts or skip charts due to missing data.

**Input Verification**:
```
BEFORE STARTING:
- [ ] Task 1 complete? (Company research exists)
- [ ] Task 2 complete? (Financial model exists)
- [ ] Task 3 complete? (Valuation analysis exists)
- [ ] Can access external market data sources?

Required from Task 1:
- [ ] Company history and milestones (for charts 05, 06)
- [ ] Management team structure (for chart 07)
- [ ] Product portfolio details (for chart 08)
- [ ] Customer segmentation data (for chart 09)
- [ ] Competitive landscape analysis (for charts 16, 17, 18)
- [ ] TAM sizing and market data (for chart 15)

Required from Task 2:
- [ ] Revenue by product (historical + projected) - for chart 03 ⭐
- [ ] Revenue by geography (historical + projected) - for chart 04 ⭐
- [ ] Income statement with margins (for charts 02, 10, 11)
- [ ] Cash flow statement (for chart 12)
- [ ] Scenario comparison data (for chart 14)

Required from Task 3:
- [ ] DCF sensitivity matrix - for chart 28 ⭐
- [ ] DCF components (for chart 29)
- [ ] Comparable companies data (for charts 30, 31)
- [ ] Valuation ranges - for chart 32 ⭐

Required from External Sources:
- [ ] Historical stock price data (for chart 01)
- [ ] Historical valuation multiples (for chart 34)
```

**Process**:
1. Verify model and valuation outputs are accessible
2. Load detailed instructions from references/task4-chart-generation.md
3. Execute chart generation workflow
4. Package all charts into a zip file
5. Deliver zip file

**Output**: 25-35 Professional Chart Files (PNG/JPG, 300 DPI) packaged in zip

**4 MANDATORY Charts** (must be present) ⭐:
- chart_03: Revenue by product (stacked area)
- chart_04: Revenue by geography (stacked bar)
- chart_28: DCF sensitivity (2-way heatmap)
- chart_32: Valuation football field (horizontal bars)

**25 REQUIRED Charts** (specific list):
- Investment Summary: chart_01
- Financial Performance: charts 02, 03⭐, 04⭐, 10, 11, 12, 14
- Company 101: charts 05, 06, 07, 08, 09, 15, 16
- Competitive/Market: charts 17, 18
- Scenario Analysis: chart 13
- Valuation: charts 28⭐, 29, 30, 31, 32⭐, 33, 34

**10 OPTIONAL Charts** (for 26-35 range):
- charts 19-27, 35 (customer acquisition, unit economics, product roadmap, etc.)

**IMPORTANT**: Task 5 embeds ALL charts created (25-35) for visual density (1 chart per 200-300 words).

**File naming**: `chart_01_description.png`, `chart_02_description.png`, etc.

**Deliverable**: `[Company]_Charts_[Date].zip` containing all 25-35 chart files + chart_index.txt

**⚠️ DELIVER ONLY THIS 1 ZIP FILE. NO completion summaries, no separate chart lists, no extra documents.**

**⚠️ DO NOT TAKE SHORTCUTS:**
- ✅ Create ALL 25 required charts minimum (specific list provided in task4-chart-generation.md)
- ✅ Include ALL 4 mandatory charts:
  - chart_03: Revenue by product (stacked area) ⭐
  - chart_04: Revenue by geography (stacked bar) ⭐
  - chart_28: DCF sensitivity (heatmap) ⭐
  - chart_32: Valuation football field ⭐
- ✅ Optional: Add 1-10 more charts to reach 26-35 total for greater visual density
- ✅ Generate professional-quality charts at 300 DPI (not low-res placeholders)
- ✅ Create unique, well-formatted charts for each visualization
- ✅ Package all charts in zip file with chart index
- ❌ Do not create only 10-15 charts (minimum is 25)
- ❌ Do not skip any of the 4 mandatory charts
- ❌ Do not use low-quality/placeholder images

**Verification before proceeding to Task 5**:
- [ ] Minimum 25 chart files created (required)
- [ ] All 4 mandatory charts present:
  - [ ] chart_03: Revenue by product ⭐
  - [ ] chart_04: Revenue by geography ⭐
  - [ ] chart_28: DCF sensitivity ⭐
  - [ ] chart_32: Valuation football field ⭐
- [ ] All charts open and display correctly
- [ ] Charts saved at 300 DPI (print quality)
- [ ] Chart index created listing all files with categories
- [ ] All charts packaged in zip file
- [ ] File naming follows convention: chart_##_description.png

---

## Task 5: Report Assembly

**Purpose**: Write and assemble the comprehensive final DOCX report.

**Prerequisites**: ⚠️ Verify before starting
- **Required**: Company research from Task 1
  - All 6-8K words of content
  - Management bios
  - Competitive analysis
  - Risk assessment
- **Required**: Financial model from Task 2
  - Excel workbook
  - All projections and scenarios
- **Required**: Valuation analysis from Task 3
  - Price target and recommendation
  - DCF, comps, precedent transactions
  - All valuation data
- **Required**: Chart files from Task 4
  - Zip file containing all 25-35 PNG/JPG files
  - Chart index included in zip

**⚠️ CRITICAL: DO NOT START THIS TASK UNLESS ALL TASKS 1-4 ARE COMPLETE**

This is the final assembly task. It cannot be completed without all previous work products.

**IF ANY OF TASKS 1, 2, 3, OR 4 ARE NOT COMPLETE**: Stop immediately and inform the user which tasks need to be completed first. The specific requirements are:
- Task 1: Company research document (6-8K words)
- Task 2: Financial model with all 6 tabs
- Task 3: Valuation analysis with price target and recommendation
- Task 4: Charts zip file with 25-35 charts

Do not attempt to create placeholder content, substitute missing sections, or assemble an incomplete report. The report requires ALL inputs to be publication-ready.

**Input Verification**:
```
BEFORE STARTING - ALL TASKS MUST BE COMPLETE:

Task 1 Verification:
- [ ] Company research document exists? (6-8K words)
- [ ] Management bios complete? (300-400 words × 3-4 execs)
- [ ] Competitive analysis complete? (5-10 competitors)
- [ ] Risk assessment complete? (8-12 risks)

Task 2 Verification:
- [ ] Financial model exists and can be opened?
- [ ] Model has projections (5 years)?
- [ ] Scenarios exist (Bull/Base/Bear)?

Task 3 Verification:
- [ ] Valuation analysis complete?
- [ ] 目标价已确定？
- [ ] 评级已确定？（买入/增持/中性/减持/卖出）
- [ ] DCF and comps complete?

Task 4 Verification:
- [ ] Chart zip file exists?
- [ ] Can extract/access all 25-35 chart files from zip?
- [ ] All 4 mandatory charts present?
  - [ ] Revenue by product (stacked area)
  - [ ] Revenue by geography (stacked bar)
  - [ ] DCF sensitivity (heatmap)
  - [ ] Valuation football field
- [ ] Chart files accessible and can be opened?

IF ANY VERIFICATION FAILS: Stop and complete missing task first.
```

**Process**:
1. **CRITICAL**: Verify ALL prerequisites before starting
2. Load detailed instructions from references/task5-report-assembly.md
3. Execute report assembly workflow using Codex's built-in skills:
   - **Use DOCX skill** to create and manipulate the Word document
   - **Use XLSX skill** to read Excel data from Task 2/3
   - **Use Read tool** to read Task 1 and Task 3 markdown files
   - Read Task 1 .md file → Convert to Word formatting → Insert charts inline
   - Read Task 2 .xlsx file → Extract tables → Write quantitative analysis
   - Read Task 3 .md file + Excel tabs → Copy/adapt valuation analysis
   - Insert Task 4 .png chart files throughout using DOCX skill
   - Create text-dense report with charts interspersed every 200-300 words
4. Save and deliver final DOCX report

**Key Principles**:
- Use Codex's DOCX and XLSX skills (NOT Python libraries)
- Use actual file operations (read .md/.xlsx/.png files, write .docx file)
- Good equity research reports are text-dense with lots of illustrating images (60-80% page coverage, 1+ chart per page)

**🔥 CRITICAL: GO ALL OUT ON THIS TASK**

**THIS IS THE FINAL DELIVERABLE. DO NOT TAKE SHORTCUTS.**

- ✅ **Use full token budget** - This is the culmination of all previous work
- ✅ **Write every section completely** - Do not summarize or abbreviate
- ✅ **Hit ALL minimum requirements** - 30+ pages, 10,000+ words, 25+ charts, 12+ tables
- ✅ **Be thorough on projection assumptions** - 2,000-3,000 words with product-by-product detail
- ✅ **Be comprehensive on scenarios** - 1,500-2,000 words with specific Bull/Base/Bear parameters
- ✅ **Insert ALL charts from Task 4** - Not just a few, ALL 25-35 charts throughout
- ✅ **Create ALL tables from Task 2/3** - Extract every financial table, don't skip any
- ✅ **Use Task 1 content verbatim** - Copy/paste full Company 101 sections (6-8K words)
- ✅ **Professional quality only** - This must be indistinguishable from JPMorgan/Goldman Sachs research

**NEVER:**
- ❌ "This section would include..." - WRITE THE ACTUAL SECTION
- ❌ "Charts would be inserted here..." - INSERT THE ACTUAL CHARTS
- ❌ "See financial model for details..." - EXTRACT AND INCLUDE THE DETAILS
- ❌ Skip sections due to length - Every section MUST be complete
- ❌ Abbreviate for token conservation - Use whatever tokens are needed

**This is publication-ready institutional research. Spare no effort, tokens, or detail.**

**Output**: Comprehensive Equity Research Report (.docx)

**Specifications**:
- **Length**: 30-50 pages (MINIMUM 30)
- **Word count**: 10,000-15,000 words (MINIMUM 10,000)
- **Charts**: 25-35 embedded images
- **Tables**: 12-20 comprehensive tables
- **Format**: Professional DOCX with clickable hyperlinks

**Structure**:
- Page 1: 首次覆盖首页 / 投资摘要
- Pages 2-5: 投资逻辑与风险提示
- Pages 6-17: Company 101
- Pages 18-30: 财务分析与盈利预测
- Pages 31-40: 估值分析
- Pages 41-50: 附录

**File name**: `[Company]_Initiation_Report_[Date].docx`

**⚠️ DELIVER ONLY THIS 1 DOCX FILE. NO executive summaries, no "highlights" documents, no extra files.**

**Final Verification**:
- [ ] Report is 30-50 pages
- [ ] Word count is 10,000-15,000
- [ ] 25-35 charts embedded
- [ ] 12-20 tables included
- [ ] All citations are clickable hyperlinks
- [ ] Numbers match financial model exactly

---

## Input Verification Protocol

### Why Input Verification Matters

Each task has strict prerequisites. Running a task without required inputs will:
- Waste time with incomplete work
- Produce low-quality outputs
- Require rework

**Always verify inputs before starting a task.**

### Verification Checklist by Task

**Task 1**: ✅ No verification needed (independent)

**Task 2**: Check historical financials available

**Task 3**: Check financial model exists and is accessible

**Task 4**: Check both model (Task 2) AND valuation (Task 3) exist

**Task 5**: Check ALL previous tasks complete (1, 2, 3, 4)

### What to Do if Verification Fails

```
IF prerequisites are missing:
1. Stop the current task
2. Identify which prerequisite task(s) need to be completed
3. For missing Tasks 1-3 in the core pipeline, execute them automatically when data access permits
4. For missing Task 4 or Task 5, ask the user before executing the missing production task
5. Return to the requested task once prerequisites are met
```

### Example Verification Dialogue

```
User: "Use initiating-coverage, Task 5 for Tesla"

Codex: "Starting Task 5: Report Assembly for Tesla

VERIFICATION - Checking prerequisites:
- Task 1 (Company research)... ❌ NOT FOUND
- Task 2 (Financial model)... ❌ NOT FOUND
- Task 3 (Valuation)... ❌ NOT FOUND
- Task 4 (Charts)... ❌ NOT FOUND

⚠️ VERIFICATION FAILED

Task 5 requires ALL previous tasks to be complete.

To proceed:
1. I will automatically complete Tasks 1-3 if the required financial data is accessible.
2. Then I will ask whether to complete Task 4 (Chart Generation).
3. After Task 4 is complete, I will ask again before assembling Task 5.

Starting with Task 1 now."
```

---

## Task Reference Files

Detailed instructions for each task are in separate reference files to keep this skill lean:

- **references/task1-company-research.md** - Company research workflow
- **references/task2-financial-modeling.md** - Financial modeling workflow
- **references/task3-valuation.md** - Valuation methodology
  - Also see: references/valuation-methodologies.md for DCF/comps deep dive
- **references/task4-chart-generation.md** - Chart generation workflow
- **references/task5-report-assembly.md** - Report writing workflow
  - Also see: assets/report-template.md for report structure
  - Also see: assets/quality-checklist.md for quality checks

**When to load reference files**: Load ONLY the reference file associated with the specific task being performed. These files are very large - do not load multiple reference files at once. Read the appropriate task reference file at the start of the task for detailed step-by-step instructions.

---

## Quality Standards

All outputs meet institutional standards from leading investment banks (JPMorgan, Goldman Sachs, Morgan Stanley):

- **Comprehensive**: Meet all minimum requirements
- **Detailed**: Specific data and examples, not generic statements
- **Quantified**: Lead with numbers and metrics
- **Cited**: Proper sources with clickable hyperlinks
- **Professional**: Institutional-quality formatting
- **Accurate**: All numbers verified and cross-checked

---

## Important Notes

### Task Independence

- **Task 1** can run anytime (no dependencies)
- **Task 2** can run anytime (just needs historical data)
- **Tasks 1 & 2** can run in parallel when explicitly useful, but the default automated core pipeline runs Task 1 → Task 2 → Task 3 for cleaner context flow
- **Task 3** requires Task 2
- **Task 4** requires Tasks 2 & 3
- **Task 5** requires Tasks 1, 2, 3, & 4

### Session Management

**Same session**: Outputs automatically available to subsequent tasks

**Different sessions**: Reference previous task outputs explicitly
```
"Use Task 3 with the model from yesterday at [path]"
"Use Task 5 with the research document at [path]"
```

### File Organization

Use this structure during workflow:
```
03-Trading/个股分析/[Company]/首次覆盖_[YYYYMMDD]/
├── Task1_Research/
│   └── [Company]_Research_Document.md
├── Task2_Model/
│   └── [Company]_Financial_Model.xlsx
├── Task3_Valuation/
│   └── [Company]_Valuation_Analysis.md
├── Task4_Charts/
│   ├── chart_01.png
│   └── ... (25-35 files)
└── Task5_Report/
    └── [Company]_Initiation_Report.docx
```

### Automated Core Pipeline and Confirmation Gates

This skill supports automatic execution of Tasks 1-3 in sequence when the user asks for an initiation report, full pipeline, or does not specify a task.

Tasks 4 and 5 are confirmation-gated:
- After Task 3, ask before executing Task 4
- After Task 4, ask before executing Task 5

**Why**: Tasks 1-3 establish the analytical base, while Tasks 4-5 are heavier production steps that benefit from user review before chart generation and final report assembly.

---

## Success Criteria

A successful initiation report workflow should:
1. Complete all 5 tasks in order
2. Pass all input verifications
3. Meet all quality standards
4. Produce all required deliverables
5. Numbers cross-check between outputs
6. Final report is publication-ready

**Output quality**: Institutional (JPMorgan/Goldman/Morgan Stanley level)
**Use case**: First-time comprehensive coverage of a company
