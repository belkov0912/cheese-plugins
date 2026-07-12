---
name: initiating-coverage
description: 生成机构风格首次覆盖报告；中文场景默认使用中文研报表达、中文标题、中文单位和中文可读性标准；默认自动执行 Task 1 公司研究、Task 2 财务建模、Task 3 估值分析，并在 Task 4 图表生成和 Task 5 报告组装前询问确认。
---

# 首次覆盖

通过 5 个任务生成机构风格首次覆盖研究。默认自动完成 Task 1-3；Task 4 和 Task 5 是较重的生产任务，分别在开始前征得用户确认。

## 默认语言与口径

用户使用中文、标的是 A 股/港股/中资公司，或输出进入中文 Obsidian Vault 时：

- 正文、标题、表格、图表、脚注和结论使用中文机构研报表达；专有名词和必要缩写除外。
- 评级使用买入/增持/中性/减持/卖出；A 股默认人民币、亿元和元/股。
- 使用可显示中文的字体，如 PingFang SC、Microsoft YaHei、Source Han Sans 或 SimSun。
- 结论先行，核心判断拆成事实、判断、假设和证伪点；重要数字必须可追溯。
- A 股优先交易所公告、巨潮资讯、公司定期报告、投资者关系材料、监管和行业协会数据；其他市场使用对应一手来源。
- 交付前搜索并清理不必要的英文模板词，如 `COMPANY RESEARCH`、`Investment View`、`Price Target`、`BUY/HOLD/SELL`、`Mkt Cap`、`$M` 和 `Source:`。

用户明确要求英文或提供模板时，以用户要求或模板为准。

## 输出位置

在包含 `03-Trading` 的 Obsidian Vault 中，写入：

```text
03-Trading/个股分析/<Company>/首次覆盖_<YYYYMMDD>/
├── Task1_Research/[Company]_Research_Document_[Date].md
├── Task2_Model/[Company]_Financial_Model_[Date].xlsx
├── Task3_Valuation/[Company]_Valuation_Analysis_[Date].md
├── Task4_Charts/[Company]_Charts_[Date].zip
└── Task5_Report/[Company]_Initiation_Report_[Date].docx
```

若已有更深层的公司目录，沿用该目录。无法识别 Vault 根目录且用户未指定路径时，先询问保存位置；不要默认写到仓库根目录。

## 执行规则

| Task | 工作 | 前置条件 | 唯一交付物 | 详细说明 |
|---|---|---|---|---|
| 1 | 公司研究 | 公司名或代码 | 6,000-8,000 字研究文档 | [task1-company-research.md](<./references/task1-company-research.md>) |
| 2 | 财务建模 | 可核验的历史财务数据 | 含 6 个核心表的 `.xlsx` | [task2-financial-modeling.md](<./references/task2-financial-modeling.md>) |
| 3 | 估值分析 | Task 2 模型 | 估值 `.md`，并向原模型增加 4 个估值表 | [task3-valuation.md](<./references/task3-valuation.md>) |
| 4 | 图表生成 | Task 1-3 和所需市场数据 | 含 25-35 张图及索引的 `.zip` | [task4-chart-generation.md](<./references/task4-chart-generation.md>) |
| 5 | 报告组装 | Task 1-4 全部完成 | 30-50 页 `.docx` | [task5-report-assembly.md](<./references/task5-report-assembly.md>) |

每次只读取当前任务对应的 reference；需要 Task 3 深入估值方法时再读 [valuation-methodologies.md](<./references/valuation-methodologies.md>)。Task 5 还需读取 [report-template.md](<./assets/report-template.md>) 和 [quality-checklist.md](<./assets/quality-checklist.md>)。

### 自动核心流程

用户要求“首次覆盖报告”“完整流程”或未指定 Task 时：

1. 立即依次执行 Task 1、2、3。
2. Task 2 若缺少可靠财务数据，完成仍可独立完成的工作并说明缺口，向用户索取数据或数据源；不要编造模型输入。
3. Task 3 只有在 Task 2 模型存在且可读时才开始。
4. Task 3 完成后停止，询问是否继续 Task 4。
5. Task 4 完成后停止，询问是否继续 Task 5。

用户明确只要某个 Task 时，只执行该 Task；如果前置条件不满足，指出缺少的具体文件或数据，不生成占位交付物。

### 确认门

- Task 4 必须在 Task 1-3 完成后获得用户明确确认。
- Task 5 必须在 Task 4 完成后再次获得用户明确确认。
- 用户一开始说“完成全部 5 个任务”也不取消这两个确认门。

## 各任务验收

### Task 1

- 覆盖公司、管理层、产品、行业、5-10 家竞品、市场空间和 8-12 条风险。
- 管理层覆盖 3-4 名关键高管，每人 300-400 字。
- 只交付 `[Company]_Research_Document_[Date].md`。

### Task 2

- 历史期 3-5 年，预测期 5 年；公式联动且可重算。
- 六个核心表：收入模型、利润表、现金流量表、资产负债表、情景假设、DCF 输入。
- 收入模型含产品和地区拆分；乐观/中性/悲观情景参数不同。
- 只交付 `[Company]_Financial_Model_[Date].xlsx`。

### Task 3

- 至少完成 DCF 和可比公司估值；适用时加入可比交易。
- DCF 有敏感性分析；可比公司含 5-10 家同行及最大值、75 分位、中位数、25 分位和最小值。
- 明确目标价、评级、上涨/下跌空间、催化剂和风险。
- 交付估值 `.md`，并在 Task 2 模型中增加 DCF、Sensitivity Analysis、Comparable Companies、Valuation Summary 四个表。

### Task 4

- 生成 25-35 张高分辨率图；基础清单除图 34 外的 24 张固定图必须生成。
- 图 34 的历史估值数据可得时必须生成；确实不可得时说明原因，并用一张有效可选图替代，图表总数仍不得少于 25 张。
- 必须含收入按产品、收入按地区、DCF 敏感性、估值足球场四张图。
- 图表可打开、文字可读、数据与模型一致，并有资料来源。
- 只交付图表 zip 和包内 `chart_index.txt`。

### Task 5

- 30-50 页、10,000-15,000 字、25-35 张内嵌图、12-20 张表。
- 首页含评级、目标价、上涨空间、核心观点、财务摘要和相对合适基准指数的股价表现图。
- 所有数字与模型一致，所有重要来源为可点击链接。
- Task 2/3 已更新的 XLSX 是 Task 5 的前置输入和核对依据；Task 5 不重新创建或重复交付该模型。
- 只交付 `[Company]_Initiation_Report_[Date].docx`。

## 通用质量标准

- 所有数据和关键判断有来源；当前数据必须实时核验。
- 不用占位符，不创建任务外的总结、速查表或“完成报告”。
- 模型、估值、图表和报告之间的数字、年份、币种及单位一致。
- 交付文件必须实际打开或渲染检查；表格公式、图表文字和 DOCX 排版分别验证。
- 不发布或对外分发；交付物仍需用户审阅。
