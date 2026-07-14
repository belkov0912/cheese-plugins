# equity-research

权益研究工具:晨会短评、行业研究、竞争格局、选题、催化剂、论点跟踪与个股消息面快讯。

改编自 Anthropic FSI 的 [`equity-research`](https://github.com/anthropics) 插件,MIT。
技能分两类:**基础技能** 和配套的 **`-workflow` 编排器**(把对应基础技能包成一步
到位的工作流)。

## 晨会

- **`morning-note`**(+ `morning-note-workflow`)— 晨会短评:隔夜变化、交易线索、行动建议。

## 行业研究

- **`sector-overview`**(+ `sector-workflow`)— 行业/主题概览:市场空间、产业链、驱动因素。
- **`competitive-analysis`** — 竞争格局分析:市场定位、竞品对比、玩家拆解、战略含义,输出 Obsidian Markdown 研报。
- **`market-researcher`** — 自动串联行业概览、竞争格局、可比公司与机会短名单的 Agent。

## 选题 / 催化 / 论点

- **`idea-generation`**(+ `screen-workflow`)— 系统化选股与想法挖掘:主题筛选、量化条件、初步 thesis。
- **`catalyst-calendar`**(+ `catalysts-workflow`)— 覆盖股票的催化剂日历:财报、会议、监管、宏观事件。
- **`thesis-tracker`**(+ `thesis-workflow`)— 维护个股投资 thesis:核心逻辑、数据点、催化、风险、验证节点。

## 消息面

- **`stock-pulse`** — 个股消息面快讯:联网查最新公告与 24 小时内利好/利空(每条带日期+来源链接),
  查机构评级与网络大 V 催票信号,综合给 1-10 利好/利空评级,并把带时间戳的快讯段追加到
  `03-Trading/个股分析/<公司>/<公司>.md` 结尾(只追加、不改已有内容)。
