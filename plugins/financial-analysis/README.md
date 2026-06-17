# financial-analysis

财务建模与分析工具:DCF、可比公司、LBO、三表模型、竞争格局分析与 Deck 质检。

改编自 Anthropic FSI 的 [`financial-analysis`](https://github.com/anthropics) 插件,MIT。
技能分两类:**基础技能**(承载具体方法)和配套的 **`-workflow` 编排器**(把对应
基础技能包成一步到位的工作流)。

## 估值建模

| 技能 | 作用 | 配套工作流 |
| --- | --- | --- |
| `dcf-model` | DCF 估值:现金流预测、WACC、终值、敏感性 | `dcf-workflow` |
| `comps-analysis` | 可比公司分析:同行选择、倍数、统计区间 | `comps-workflow` |
| `lbo-model` | LBO:融资结构、债务偿还、IRR/MOIC、敏感性 | `lbo-workflow` |
| `3-statement-model` | 联动三表:利润表 / 资产负债表 / 现金流量表 | `3-statement-model-workflow` |
| `model-builder` | 从零搭建 DCF/LBO/三表/可比公司模型的 Agent | — |
| — | 调试与审计模型错误 | `debug-model-workflow` |

## 表格处理

- **`xlsx-author`** — 无实时 Excel 环境时,本地生成 `.xlsx`。
- **`audit-xls`** — 审计模型:公式、硬编码、勾稽关系、平衡检查。
- **`clean-data-xls`** — 清洗数据:格式统一、文本转数字、去重、异常标记。

## 竞争与发布

- **`competitive-analysis`**(+ `competitive-analysis-workflow`)— 竞争格局、竞品对比、战略含义。
- **`ib-check-deck`** — 投行/路演材料质检:数字一致性、脚注、叙事匹配、格式。
- **`deck-refresh`** — 用最新数据刷新 PPT/报告:季度滚动、财报刷新、数字替换。
- **`pptx-author`** — 无实时 PowerPoint 环境时,本地生成 `.pptx`。
- **`ppt-template-creator`**(+ `ppt-template-workflow`)— 把用户的 PPT 模板封装成可复用的模板 skill。
