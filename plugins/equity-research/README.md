# equity-research

权益研究工具:财报分析、首次覆盖、选题、催化剂与论点跟踪。

改编自 Anthropic FSI 的 [`equity-research`](https://github.com/anthropics) 插件,MIT。
技能分两类:**基础技能** 和配套的 **`-workflow` 编排器**(把对应基础技能包成一步
到位的工作流)。

## 财报

| 技能 | 作用 | 配套工作流 |
| --- | --- | --- |
| `earnings-preview` | 财报前预览:市场预期、关键指标、情景与催化 | `earnings-preview-workflow` |
| `earnings-analysis` | 财报后点评:超/低预期、指引变化、投资结论 | `earnings-workflow` |
| `earnings-reviewer` | 读财报/电话会、更新模型、产出点评的 Agent | — |
| `morning-note` | 晨会短评:隔夜变化、交易线索、行动建议 | `morning-note-workflow` |

## 覆盖与研报

- **`initiating-coverage`**(+ `initiate-workflow`)— 机构风格首次覆盖报告(中文场景默认中文研报表达)。
- **`sector-overview`**(+ `sector-workflow`)— 行业/主题概览:市场空间、产业链、驱动因素。
- **`market-researcher`** — 自动串联行业概览、竞争格局、可比公司与机会短名单的 Agent。

## 选题 / 催化 / 论点

- **`idea-generation`**(+ `screen-workflow`)— 系统化选股与想法挖掘:主题筛选、量化条件、初步 thesis。
- **`catalyst-calendar`**(+ `catalysts-workflow`)— 覆盖股票的催化剂日历:财报、会议、监管、宏观事件。
- **`thesis-tracker`**(+ `thesis-workflow`)— 维护个股投资 thesis:核心逻辑、数据点、催化、风险、验证节点。

## 模型更新

- **`model-update`**(+ `model-update-workflow`)— 按财报/公告/指引变化更新模型并标记关键变动。
