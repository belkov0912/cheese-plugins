---
name: dcf-model
description: DCF 估值建模：现金流预测、WACC、终值、敏感性分析和估值摘要。
---

# DCF Model Builder

生成可审计、可重算的 DCF Excel 模型，包含 Bear/Base/Bull 情景、WACC、企业价值到股权价值桥接和敏感性分析。

## 输入与数据源

最低输入：公司名/代码、3-5 年历史财务、当前股价、稀释后股数、债务、现金和预测假设。未给预测时，可使用有来源的管理层指引或一致预期，并清楚标注。

数据优先级：

1. 用户提供的模型或模板；有模板时在原结构上工作。
2. 可用的结构化金融数据源。
3. 公司监管文件、业绩材料和可靠市场数据。
4. 其他来源仅作交叉验证。

当前股价、无风险利率、Beta、债务、现金和股数必须核验日期。每个硬编码输入都写单元格批注：`Source: [Document/System], [Date], [Reference], [URL]`。

## 工作环境

- 实时 Excel 环境使用原生 Excel 能力，公式写入 formula 字段。
- 独立 `.xlsx` 使用现有电子表格技能/openpyxl，派生值写公式而不是 Python 计算结果。
- 合并标题时先给左上角单元格赋值，再合并和格式化范围。
- 用户模板、样式指南和明确偏好优先于默认格式。

## 不可省略的约束

- 只有历史数据、市场数据和假设可以硬编码；预测、利润率、折现、终值、桥接和敏感性全部使用 Excel 公式。
- 先锁定所有行和区块，再写公式；每完成一个区块立即测试引用。
- OpEx 以收入而非毛利为驱动基础，除非业务模型有明确不同依据。
- 终值增长率须有长期名义 GDP、通胀等依据，通常为 2%-5%，且必须低于 WACC；无依据时不得高于同币种长期无风险利率或长期经济增速，异常假设须解释并做敏感性测试。终值占企业价值通常应在 50%-70%，超出时解释并复核。
- 使用稀释后股数；净债务为总债务减现金，净现金在股权价值桥接中增加价值。
- 模型必须能通过情景选择器切换 Bear/Base/Bull，不在每个预测公式中散落多层 IF。
- 交付前重算并消除 `#REF!`、`#DIV/0!`、`#VALUE!`、`#NAME?`、`#NUM!` 和 `#N/A`。

## 分段确认

按以下顺序构建并向用户展示关键输出：

1. 原始输入和历史期。
2. 收入与利润率预测。
3. Unlevered FCF。
4. WACC。
5. 终值、企业价值、股权价值和每股价值。
6. 敏感性表。

发现错误就在当前阶段修正，不把错误带到后续区块。

## 模型结构

独立 DCF 任务输出 `[Ticker]_DCF_Model_[Date].xlsx`，只建两个工作表。若本技能被首次覆盖等上游流程调用，则把同样的模型区块写入上游指定的现有工作簿，并遵循上游的工作表和交付契约；不要另建重复文件。

### DCF

按顺序包含：

1. 公司、日期、币种、单位和情景选择器。
2. 市场数据：股价、稀释股数、市值、债务、现金和净债务。
3. Bear/Base/Bull 假设区块。
4. 历史和预测利润表摘要。
5. Unlevered FCF。
6. 折现、终值和企业价值到股权价值桥接。
7. 三张敏感性表，放在 DCF 表底部。

### WACC

包含：

- 无风险利率、Beta、股权风险溢价和股权成本。
- 税前/税后债务成本。
- 市值口径的股权与债务权重。
- WACC 计算和来源。

## DCF 计算

### 收入与利润

预测期通常 5 年；高增长公司可用 7-10 年，成熟公司可用 3-5 年，但要说明原因。

```text
Revenue_t = Revenue_(t-1) × (1 + Growth_t)
Gross Profit_t = Revenue_t × Gross Margin_t
EBIT_t = Gross Profit_t - S&M_t - R&D_t - G&A_t
```

预测必须显示收入增长率和关键利润率。增长向长期稳态收敛，利润率变化要有规模、组合或成本依据。

### Unlevered FCF

```text
NOPAT = EBIT × (1 - Tax Rate)
UFCF = NOPAT + D&A - CapEx - ΔNWC
```

- D&A、CapEx 和营运资本假设与历史和业务模式一致。
- `ΔNWC` 的符号及驱动口径写清楚，避免把资金占用写成现金来源。
- 税率异常时使用公司有效税率或法定税率并解释。

### WACC

```text
Cost of Equity = Risk-Free Rate + Beta × Equity Risk Premium
After-Tax Cost of Debt = Pre-Tax Cost of Debt × (1 - Tax Rate)
Market Cap = Share Price × Diluted Shares
Net Debt = Debt - Cash
Enterprise Value = Market Cap + Net Debt
WACC = Ke × Equity Weight + Kd_after_tax × Debt Weight
```

- 无风险利率使用估值日同币种约 10 年期主权债收益率；Beta 默认使用 5 年月度数据并匹配合适的市场指数，替代口径须解释。
- 股权风险溢价注明来源和日期；税前债务成本使用公司债收益率/信用利差，或利息费用/平均债务，并说明口径和期间。

权重使用市场价值。无债务公司 WACC 等于股权成本；净现金公司的处理必须避免不合理负债务权重，必要时以目标资本结构或纯股权口径说明。

### 折现与终值

默认使用年中折现：第 1-5 年折现期为 0.5、1.5、2.5、3.5、4.5。

```text
Discount Factor_t = 1 / (1 + WACC)^Period_t
PV UFCF_t = UFCF_t × Discount Factor_t
Terminal Value = UFCF_final × (1 + g) / (WACC - g)
PV Terminal Value = Terminal Value × final Discount Factor
```

可用退出倍数作为交叉检查；倍数必须来自可比公司或交易。不能混用不同口径的 EBITDA、收入或年份。

### 企业价值到每股价值

```text
Enterprise Value = Σ PV UFCF + PV Terminal Value
Equity Value = Enterprise Value - Net Debt - Other Claims + Non-operating Assets
Implied Price = Equity Value / Diluted Shares
Implied Return = Implied Price / Current Price - 1
```

少数股东权益、养老金、租赁负债和非经营资产只在金额重大且口径一致时调整。

## 情景选择

每个情景独立成块，结构统一：区块标题、预测年份表头、假设行。至少包括收入增长、EBIT 率、税率、D&A、CapEx、营运资本、WACC 和终值增长率。

情景选择器使用 1=Bear、2=Base、3=Bull。建立“Selected Case”汇总行或列，以 `INDEX`/`OFFSET` 从三个区块取值，预测公式只引用汇总值：

```excel
=INDEX(B10:D10,1,$B$6)
```

这样切换情景只改变选择器，不需要在每个公式内重复嵌套 IF。

## 敏感性分析

在 DCF 表底部建立三张 5×5 表：

1. WACC × 终值增长率。
2. 收入增长 × EBIT 率。
3. Beta × 无风险利率。

要求：

- 行列数为奇数，轴值围绕实际 Base 假设对称展开。
- 中心格就是 Base 情景，结果必须等于主估值中的每股价值，并用中蓝色加粗标出。
- 75 个数据格全部写入完整重算公式；不能用线性近似、空白、占位说明或需要用户手工操作的 Excel Data Table。
- 公式引用行/列表头的假设值，返回该组合下的每股价值。
- 表间留空行并使用清楚的色阶，但保证文字可读。

## 格式与审计

- 字体颜色：蓝色=硬编码输入，黑色=公式，绿色=跨表引用。
- 填充色保持克制：深蓝标题、浅蓝表头、中蓝关键输出、浅灰输入、白色计算区。
- 年份为文本；百分比 `0.0%`；金额标明单位；负数用括号；零显示为 `-`。
- 大区块用边框区分，单元格内部不铺满边框。
- 每个硬编码输入在写入时立即添加来源批注。
- 内置检查至少覆盖 `g < WACC`、情景切换、敏感性中心格、每股价值桥接和终值占比。

## 交付前验证

1. 切换三种情景，确认 Selected Case、预测、WACC、终值和每股价值同步更新。
2. 抽查收入、EBIT、UFCF、折现和桥接公式，确认引用正确。
3. 核对无风险利率、Beta、股权风险溢价、债务成本和终值增长率的来源、日期与口径；异常假设须有解释和敏感性测试。
4. 确认三张敏感性表共 75 个工作公式，中心格等于 Base 每股价值。
5. 独立 `.xlsx` 运行电子表格技能提供的重算检查，例如：

   ```bash
   python recalc.py model.xlsx 30
   ```

6. 修复全部公式错误后重新运行，直到状态成功。
7. 打开或渲染工作簿，检查表头、批注、数字格式、列宽和关键输出可读性。

出现不合理估值或公式错误时，读取 [TROUBLESHOOTING.md](<./TROUBLESHOOTING.md>)。只交付最终 `.xlsx`，不附加手工步骤或占位说明。
