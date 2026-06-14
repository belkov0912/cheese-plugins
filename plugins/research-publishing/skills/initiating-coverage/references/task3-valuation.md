# Task 3: Valuation Analysis - Detailed Workflow

This document provides step-by-step instructions for executing Task 3 (Valuation Analysis) of the initiating-coverage skill.

## 中文估值输出规则（最高优先级）

当用户使用中文、标的是 A 股/港股/中资公司、或输出进入中文 Obsidian Vault 时，Task 3 必须生成中文估值分析：

- 标题、章节名、表格列名、图表标题、结论和风险均使用中文；不要输出 `INVESTMENT RECOMMENDATION`、`Price Target`、`Upside`、`Comparable Companies Analysis` 这类英文模板标题。
- 目标价按交易市场货币输出，例如 A 股写 `目标价：XX 元/股`，港股写 `XX 港元/股`，美股写 `XX 美元/股`。
- 评级默认使用中文：`买入`、`增持`、`中性`、`减持`、`卖出`；如需兼容海外口径，可写 `买入（BUY）`。
- 三种情景默认写为 `乐观 / 中性 / 悲观`，可在括号中保留 `Bull/Base/Bear`。
- 表格单位使用中文金融写法：`总市值（亿元）`、`企业价值（亿元）`、`收入（亿元）`、`EBITDA（亿元）`、`净利润（亿元）`、`目标价（元/股）`。
- DCF 估值要明确区分 `事实数据`、`核心假设`、`估值结果`、`敏感性` 和 `证伪点`；不要只给公式和点位。
- 对 A 股公司，WACC 的无风险利率优先使用中国 10 年期国债收益率；股权风险溢价、Beta、税率、目标资本结构必须说明来源或估算逻辑。
- 交付前检查英文残留：`Price Target`、`Upside`、`BUY/HOLD/SELL`、`Mkt Cap`、`$M`、`Source:` 等模板词要改成中文，专有名词和必要英文缩写除外。

## Task Overview

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

**Output**: Valuation Analysis (4-6 pages + Excel tabs)
- DCF 估值和敏感性分析
- 可比公司估值
- 可比交易估值（如适用）
- 估值区间图/Football Field
- 目标价、评级和上涨空间

---

## Input Verification

**BEFORE STARTING - CHECK:**
- [ ] Task 2 complete? (Financial model exists)
- [ ] Model file path/location known?
- [ ] Can access projected financials from model?

**Required from model:**
- [ ] Projected FCF (5 years)
- [ ] Revenue projections
- [ ] EBITDA projections
- [ ] Terminal year metrics
- [ ] Balance sheet data (debt, cash, shares)

**IF VERIFICATION FAILS**: Stop and complete Task 2 (Financial Modeling) before proceeding.

---

## Detailed Methodology Reference

For deep dive on valuation methodologies, formulas, and theory, see:
**[valuation-methodologies.md](<./valuation-methodologies.md>)**

This workflow document focuses on execution steps. Reference the methodology file for:
- DCF theory and formulas
- WACC calculation details
- Terminal value methods
- Comparable companies theory
- Precedent transactions theory

---

## Step-by-Step Valuation Workflow

### Step 1: Extract Data from Financial Model

**From Task 2's financial model, extract:**

1. **Projected Financials (5 years)**
   - Revenue by year (2025E-2029E)
   - EBITDA by year
   - EBIT by year
   - Tax rate
   - D&A by year
   - CapEx by year
   - Change in NWC by year

2. **Unlevered Free Cash Flow**
   ```
   Extract from DCF Inputs tab in financial model:

                   2025E   2026E   2027E   2028E   2029E
   EBIT            XXX     XXX     XXX     XXX     XXX
   × (1 - 税率)
   = NOPAT         XXX     XXX     XXX     XXX     XXX
   + 折旧摊销       XXX     XXX     XXX     XXX     XXX
   - 资本开支       (XX)    (XX)    (XX)    (XX)    (XX)
   - 营运资本增加   (XX)    (XX)    (XX)    (XX)    (XX)
   = 无杠杆自由现金流 XXX   XXX     XXX     XXX     XXX

   注：表格顶部写清楚单位，例如 `单位：百万元`。
   ```

3. **Balance Sheet Data (current)**
   - Total debt
   - Cash & equivalents
   - Net debt (Debt - Cash)
   - Diluted shares outstanding

4. **Scenario Data**
   - Bull case revenue CAGR and terminal margin
   - Base case revenue CAGR and terminal margin
   - Bear case revenue CAGR and terminal margin

### Step 2: Build DCF Analysis

#### A. Calculate WACC

**1. Determine Risk-Free Rate**
   - US-listed companies: use current 10-year US Treasury yield
   - A-share/China companies: use current China 10-year government bond yield
   - Always state the observation date and source

**2. Determine Cost of Equity (CAPM)**
   ```
   Cost of Equity = Risk-Free Rate + Beta × Equity Risk Premium

   Inputs:
   - Risk-Free Rate: [Current 10-year Treasury, e.g., 4.2%]
   - Beta: [Company beta from Bloomberg/FactSet or peer average]
   - Equity Risk Premium: 5-6% (historical average)

   Example:
   Cost of Equity = 4.2% + 1.3 × 5.5% = 11.35%
   ```

**3. Determine Cost of Debt**
   ```
   Cost of Debt = Current borrowing rate or implied yield on bonds

   For private companies:
   Cost of Debt = Risk-Free Rate + Credit Spread (based on rating)

   Example:
   Cost of Debt (pre-tax) = 6.5%
   Cost of Debt (after-tax) = 6.5% × (1 - 25% tax rate) = 4.875%
   ```

**4. Determine Capital Structure**
   ```
   Use market values (not book values):

   Market Value of Equity (E) = Share Price × Shares Outstanding
   Market Value of Debt (D) = Total Debt (use book value if bonds not traded)
   Total Value (V) = E + D

   Weight of Equity = E / V
   Weight of Debt = D / V

   Example:
   E = $5,000M (90.9%)
   D = $500M (9.1%)
   V = $5,500M (100%)
   ```

**5. Calculate WACC**
   ```
   WACC = (E/V × Cost of Equity) + (D/V × Cost of Debt × (1 - Tax Rate))

   Example:
   WACC = (90.9% × 11.35%) + (9.1% × 6.5% × (1 - 25%))
   WACC = 10.32% + 0.44% = 10.76%

   Round to: 10.8% for base case
   ```

#### B. Calculate Terminal Value

**Method 1: Perpetuity Growth (Preferred)**
```
Terminal Value = FCF(2029) × (1 + g) / (WACC - g)

Where:
- FCF(2029) = Final year unlevered FCF from model
- g = Perpetual growth rate (typically 2.0-3.0%)
  - Should not exceed long-term GDP growth
  - Use 2.5% as base case

Example:
FCF(2029) = $500M
g = 2.5%
WACC = 10.8%

Terminal Value = $500M × (1.025) / (0.108 - 0.025)
Terminal Value = $512.5M / 0.083 = $6,175M
```

**Method 2: Exit Multiple (Alternative)**
```
Terminal Value = EBITDA(2029) × Exit Multiple

Where:
- Exit Multiple = Current peer trading median (e.g., 12-15x EBITDA)

Example:
EBITDA(2029) = $800M
Exit Multiple = 13x

Terminal Value = $800M × 13x = $10,400M
```

**Choose one method or average both.**

#### C. Discount Cash Flows to Present Value

```
PV of Projected FCF = Σ [FCFt / (1 + WACC)^t] for t = 1 to 5

Example:
Year    FCF      Discount    PV of FCF
        ($M)     Factor      ($M)
2025    $250     1/(1.108)^1 = 0.9026    $226
2026    $320     1/(1.108)^2 = 0.8147    $261
2027    $390     1/(1.108)^3 = 0.7353    $287
2028    $450     1/(1.108)^4 = 0.6636    $299
2029    $500     1/(1.108)^5 = 0.5988    $299
                              Total PV:  $1,372M

PV of Terminal Value = Terminal Value / (1 + WACC)^5
PV of Terminal Value = $6,175M / (1.108)^5 = $6,175M × 0.5988 = $3,697M

Enterprise Value = $1,372M + $3,697M = $5,069M
```

#### D. Calculate Equity Value and Price Per Share

```
企业价值                         506.9 亿元
- 净债务（债务 - 现金）           (45.0 亿元)
+ 非经营性资产                    0 亿元
- 少数股东权益                    0 亿元
- 优先股                          0 亿元
= 股权价值                        461.9 亿元

稀释后总股本                     10.0 亿股

每股价值 = 461.9 亿元 / 10.0 亿股 = 46.19 元/股

当前股价：42.00 元/股
隐含上涨空间：10.0%
```

#### E. DCF Sensitivity Analysis **CRITICAL**

**Table 1: WACC vs. Terminal Growth Rate**

Create 2-way sensitivity table:
```
Price Per Share ($)     Terminal Growth Rate
WACC        1.5%    2.0%    2.5%    3.0%    3.5%
9.0%        $52     $55     $59     $63     $68
9.5%        $48     $51     $54     $58     $62
10.0%       $45     $48     $51     $54     $57
10.5%       $42     $45     $47     $50     $53
11.0%       $40     $42     $44     $47     $50
11.5%       $38     $40     $42     $44     $47
12.0%       $36     $38     $40     $42     $44

Base Case: WACC = 10.8%, g = 2.5% → $46
Format as heatmap: Green (high values) → Yellow → Red (low values)
```

**Table 2: Revenue CAGR vs. Terminal EBITDA Margin**
```
Price Per Share ($)     Terminal EBITDA Margin (2029E)
Revenue CAGR    28%     30%     32%     34%     36%
15%             $38     $42     $46     $50     $54
20%             $42     $46     $51     $56     $61
25%             $46     $51     $56     $62     $68
30%             $51     $56     $62     $68     $75
35%             $56     $62     $68     $75     $83

Base Case: Rev CAGR = 25%, EBITDA Margin = 32% → $56
```

### Step 3: 可比公司估值分析

#### A. Select Comparable Companies

**Selection Criteria:**
- Same industry/sector (primary requirement)
- Similar business model
- Comparable size (market cap, revenue)
- Similar growth profile
- Similar geographies

**Identify 5-10 peer companies:**
1. [Peer 1] - Direct competitor
2. [Peer 2] - Direct competitor
3. [Peer 3] - Adjacent player
4. [Peer 4] - Similar business model
5. [Peer 5] - Regional competitor
6. [Add 3-5 more]

**Document rationale for each peer selected.**

#### B. Gather Peer Financial Data

**For each comparable, gather:**
- Current stock price
- Shares outstanding (diluted)
- Market capitalization
- Total debt and cash (for EV calculation)
- Enterprise value
- LTM (Last Twelve Months) financials:
  - Revenue
  - EBITDA
  - EBIT
  - Net Income
- NTM (Next Twelve Months) consensus estimates
- Revenue growth rate
- EBITDA margin

**Data sources:**
- FactSet, CapitalIQ, Bloomberg (preferred)
- Company 10-Ks/10-Qs for actuals
- Consensus estimates from Yahoo Finance, Seeking Alpha (if pro tools unavailable)

#### C. Calculate Valuation Multiples

**For each peer, calculate:**
```
EV/Revenue (LTM) = Enterprise Value / LTM Revenue
EV/Revenue (NTM) = Enterprise Value / NTM Revenue (est.)
EV/EBITDA (LTM) = Enterprise Value / LTM EBITDA
EV/EBITDA (NTM) = Enterprise Value / NTM EBITDA (est.)
P/E (NTM) = Market Cap / NTM Net Income (est.)
```

#### D. Create Comparable Companies Table (MANDATORY FORMAT)

For Chinese deliverables, use this Chinese table format:

```
可比公司估值分析

公司        代码    总市值   EV/收入  EV/收入  EV/EBITDA EV/EBITDA P/E   收入增速 EBITDA率
                  （亿元）  LTM     NTM     LTM       NTM       NTM
可比公司A   PRA    452     3.5x    3.2x    15.2x     13.8x     25x   18%     23%
可比公司B   PRB    328     3.2x    2.9x    14.1x     12.5x     22x   15%     23%
可比公司C   PRC    285     2.8x    2.6x    12.8x     11.2x     20x   12%     22%

[目标公司]  TRGT   380     3.4x    3.1x    14.8x     13.0x     24x   17%     23%

统计摘要
最大值              452     4.1x    3.7x    17.5x     15.2x     29x   22%     23%
75分位              452     3.7x    3.4x    16.1x     14.1x     26x   19%     23%
中位数              389     3.5x    3.2x    15.2x     13.8x     25x   17%     23%
25分位              328     3.2x    2.9x    14.1x     12.5x     22x   15%     22%
最小值              285     2.8x    2.6x    12.8x     11.2x     20x   12%     22%

注：市场数据截至 [日期]。LTM 为最近 12 个月，NTM 为未来 12 个月预测。
资料来源：公司公告、交易所披露、FactSet/Wind/Choice/同花顺等数据源、分析师估算。
```

**CRITICAL**: The statistical summary (max/75th/median/25th/min) is MANDATORY.

#### E. Apply Multiples to Target Company

**Choose primary multiple (typically EV/EBITDA for mature companies):**

```
Target Company NTM EBITDA = $550M (from financial model)

Apply Median Peer Multiple:
Peer Median EV/EBITDA (NTM) = 13.8x
Implied EV = $550M × 13.8x = $7,590M

Apply 25th Percentile (Conservative):
25th Percentile EV/EBITDA (NTM) = 12.5x
Implied EV = $550M × 12.5x = $6,875M

Apply 75th Percentile (Optimistic):
75th Percentile EV/EBITDA (NTM) = 14.1x
Implied EV = $550M × 14.1x = $7,755M

Valuation Range (Comps): $6,875M - $7,755M
Midpoint: $7,315M

Convert to Equity Value:
Implied EV (Median)        $7,590M
- Net Debt                 ($450M)
= Implied Equity Value     $7,140M

Shares Outstanding         100M
Implied Price/Share        $71.40
```

**Justify Premium/Discount:**
- Target is growing 17% vs. peer median 17% → In-line
- Target EBITDA margin 23% vs. peer median 23% → In-line
- Target market position → [Justify premium/discount]
- **Conclusion**: Apply median multiple (no adjustment)

### Step 4: Precedent Transactions (Optional)

**Note**: Only if M&A is relevant for this sector/company.

#### A. Identify Relevant Transactions

**Search for 5-10 M&A deals:**
- Same industry, last 3-5 years
- Similar size (0.5x to 2x target's size)
- Announced and closed deals

**Example:**
```
PRECEDENT TRANSACTIONS ANALYSIS

Date     Target        Acquirer      Deal     EV/Rev  EV/EBITDA  Premium  Rationale
                                    Value($B)  LTM     LTM
Q1 2024  Comp A       Strategic      $5.2B    4.2x    16.5x      35%      Consolidation
Q3 2023  Comp B       PE Firm        $3.8B    3.8x    14.2x      28%      Platform
Q4 2023  Comp C       Strategic      $4.5B    4.0x    15.8x      32%      Geographic
Q2 2023  Comp D       Strategic      $6.1B    4.5x    17.2x      38%      Strategic fit
Q1 2023  Comp E       PE Firm        $3.2B    3.5x    13.5x      25%      Carve-out

Median                                        4.0x    15.8x      32%

资料来源：CapitalIQ、公司公告、新闻稿。
```

#### B. Apply to Target Company

```
Target Company LTM EBITDA = $500M
Precedent Median EV/EBITDA (LTM) = 15.8x

Implied EV (Precedent) = $500M × 15.8x = $7,900M

Note: Precedent multiples typically 10-20% higher than trading comps
due to control premium and synergies.
```

### Step 5: Valuation Reconciliation

#### A. Create Valuation Summary Table

```
VALUATION SUMMARY

估值方法                低值    中值    高值    权重    加权价值
DCF 估值                42      46      51      50%     23.00
可比公司估值（NTM）     64      71      78      40%     28.40
可比交易估值            70      79      88      10%     7.90
                                                        -------
加权平均目标价                          100%    59.30 元/股

取整目标价：59.00 元/股

当前价格（截至 [日期]）：        42.00 元/股
上涨空间：                       40%（59.00 / 42.00 - 1）
```

#### B. Determine Weighting Rationale

**Typical Weighting:**
- DCF: 40-60% (higher when forecasts reliable)
- Trading Comps: 25-40% (reflects market sentiment)
- Precedent Trans: 10-25% (lower unless M&A likely)

**For this example:**
- DCF 50%: High confidence in projections
- Comps 40%: Robust peer set
- Precedent 10%: M&A unlikely near-term

#### C. Create Valuation Football Field Chart

```
估值区间图

估值方法                低值 ◄────────── 区间 ──────────► 高值

DCF 估值                42  ▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓ 51

可比公司估值（NTM）     64  ▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓ 78

可比交易估值            70  ▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓ 88
                                          ↑
                                    当前价格：42 元/股
─────────────────────────────────────────────────────────
估值区间                42                           88
目标价：59 元/股（加权平均）

Color code:
- DCF: Blue
- Trading Comps: Green
- Precedent Trans: Orange
- Vertical line at current price: Red dashed
- Vertical line at target: Black solid
```

#### D. Scenario-Based Valuations

```
VALUATION BY SCENARIO

Scenario    Probability  Revenue  EBITDA    DCF      Comps    Weighted
                        CAGR     Margin    Value    Multiple  Avg
Bear Case   20%         18%      28%       $38      11.5x     $42
Base Case   60%         25%      32%       $46      13.8x     $59
Bull Case   20%         32%      36%       $58      16.0x     $82

Expected Value (probability-weighted): $59
```

### Step 6: 目标价与投资建议

```
投资建议

当前价格：          42.00 元/股（截至 [日期]）
目标价：            59.00 元/股（12 个月）
上涨/下跌空间：     +40.5%
评级：              买入

估值方法：          基于 DCF（50%）、可比公司估值（40%）和可比交易估值（10%）
                   的加权结果。若可比交易不适用，应说明剔除原因并重分配权重。

投资期限：          12 个月

核心催化剂

1. 新产品/新产能释放（[时间]）
   - 预计带动收入增速提升 [X] 个百分点
   - 订单、认证、产能爬坡或客户导入已有可验证迹象

2. 利润率改善（[年份]）
   - 规模效应、产品结构或成本下降推动盈利弹性
   - EBITDA 率/净利率有望从 [X]% 提升至 [Y]%

3. 市占率提升（持续验证）
   - 相对竞争对手的成本、渠道、技术或客户粘性优势正在兑现

目标价风险

下行风险：
1. 竞争加剧（高/中/低概率，估值影响约 -X%）
   - 新进入者、价格战或客户流失可能压制收入和利润率

2. 执行风险（高/中/低概率，估值影响约 -X%）
   - 新产品、新产能或海外拓展不及预期

3. 宏观/周期风险（高/中/低概率，估值影响约 -X%）
   - 下游需求放缓、价格下行或库存周期反转

上行风险：
1. 业绩持续超预期（估值影响约 +X%）
   - 收入增速、利润率或现金流好于模型假设

2. 估值重估/并购可能（估值影响约 +X%）
   - 行业景气改善、政策催化或战略收购带来估值弹性
```

---

## Quality Standards

### DCF Quality Checks
- [ ] WACC properly calculated with documented components
- [ ] Terminal value reasonable (< 70% of total enterprise value)
- [ ] Sensitivity analysis covers realistic ranges (±200-300bps for WACC, ±100bps for terminal growth)
- [ ] Unlevered FCF properly calculated from EBIT
- [ ] Enterprise to equity value bridge correct
- [ ] Share count is diluted shares, not basic

### Comparables Quality Checks
- [ ] 5-10 comparable companies selected
- [ ] Peer selection defensible (document why each peer was chosen)
- [ ] Statistical summary included (max/75th/median/25th/min) - MANDATORY
- [ ] Multiple selection appropriate (EV/EBITDA for mature, EV/Revenue for high-growth)
- [ ] Premium/discount justified with specific factors
- [ ] Data sourced properly with dates noted

### Overall Valuation Quality Checks
- [ ] At least 2 valuation methods used (DCF + Comps minimum)
- [ ] Weighting explained and appropriate
- [ ] Valuation range provided (low/base/high), not just point estimate
- [ ] Scenarios analyzed (Bull/Base/Bear)
- [ ] Sanity checks performed (see below)
- [ ] All assumptions documented with rationale

---

## Sanity Checks

**Always perform these validation checks:**

1. **Historical Multiple Check**
   - Is implied multiple in line with company's historical trading range?
   - If not, explain why

2. **Peer Comparison**
   - Is premium/discount vs. peers justified by fundamentals?
   - Check: growth, margins, market position

3. **Implied Growth Check**
   - What growth is market pricing in at current price?
   - Is that reasonable given company trajectory?

4. **Market Cap Reasonableness**
   - Does total market cap make sense given company size and peers?
   - Would company be too large/small relative to industry?

5. **Terminal Value Check**
   - Is terminal value < 60-70% of total enterprise value?
   - If > 70%, projections may not be long enough

6. **WACC Reasonableness**
   - Is WACC 8-14% range for typical companies?
   - Tech/high-growth: 10-14%
   - Mature/stable: 7-10%

7. **Implied Returns Check**
   - What IRR from current price to target over 12 months?
   - Is that consistent with recommendation rating?

---

## Output Files

Create the following deliverables:

### 1. Valuation Analysis Document
**File**: `[Company]_Valuation_Analysis_[Date].md` (written analysis)

**Contents** (4-6 pages):
- Executive summary with price target
- DCF analysis (1 page) with sensitivity table
- Comparable companies analysis (1 page) with statistical summary
- Precedent transactions (0.5 page) if applicable
- Valuation summary and football field (0.5 page)
- Investment recommendation (1 page)
- Key catalysts and risks (1 page)

### 2. Excel Valuation Tabs
**Add to Task 2's financial model file:** `[Company]_Financial_Model_[Date].xlsx`

**IMPORTANT**: Do NOT create a separate Excel file. Add these tabs to the existing financial model from Task 2. This keeps all quantitative data in one place.

**Tabs to add:**
- DCF tab with full calculations
- Sensitivity analysis tab
- Comps tab with peer data
- Precedent transactions tab (if applicable)
- Valuation summary tab

---

## Success Criteria

A successful valuation analysis should:
1. Use at least 2 methods (DCF + Comps minimum)
2. Include comprehensive DCF sensitivity analysis (2-way tables)
3. Include statistical summary in comps (max/75th/median/25th/min)
4. Provide valuation range (low/base/high), not point estimate
5. Document all key assumptions with clear rationale
6. Perform sanity checks
7. Arrive at defensible price target
8. Provide clear buy/hold/sell recommendation
9. Identify 3-5 key catalysts
10. Identify 3-5 key risks
11. Be auditable and transparent

---

## Next Steps

After completing Task 3, the valuation analysis will be used for:
- **Task 4 (Charts)**: Create DCF sensitivity heatmaps, valuation football field, scenario comparison charts
- **Task 5 (Report Assembly)**: Integrate valuation analysis into final report

The price target and recommendation are the foundation of the final investment recommendation in the equity research report.
