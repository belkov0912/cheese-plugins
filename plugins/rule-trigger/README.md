# rule-trigger

规则触发器工具箱：提供 R0「启动扳机」、R7「试盘后回踩」、R9「下跌反转」、R1「动态主线强度」、A股最近观察评级和本地行情仓，后续可扩展其余规则评分、扫描和复盘。R0 查最近 5 个交易日里有没有「放量强阳突破」；R7 查最近 20 个交易日里有没有「相对放量试盘 → 缩量回踩」；R9 查「刚跌完企稳的票，最近 5 个交易日有没有放量大阳收复失地」；R1 先按申万一级行业 5/20 日涨幅选出市场当下主线，再找行业内 20 日强势前排；`a-share-latest-rating` 用回测定版的 R7+R1 组合给最近完整交易日做 S/A/B/C/D/N/A 观察评级。**自带全部脚本，行情数据下载到用户本地**——装上插件、建一次仓，任何机器都能用。

## 快速开始

```text
1. 安装插件（/plugins → cheese-plugins → rule-trigger），机器上有 python3 即可
2. 建仓：/r0-data → skill 会先自检依赖（缺了征得同意后自动 pip install），
   然后全量下载（约45-90分钟，断点续跑）；隔天保鲜用 update，
   全市场约1-1.5小时——sina 每次传全量历史，增量省不了网络，建议后台/定时跑
3. 查询：/r0-trigger 景旺电子   或   /r7-trigger 景旺电子
```

## 六个 skill

| skill | 干什么 |
|---|---|
| `r0-trigger` | 查 R0 分：单票/多票（名称或代码），或 `--today` 全市场扣扳机名单 |
| `r7-trigger` | 查 R7 分：单票/多票试盘后回踩形态，或 `--today` 全市场 R7 高分名单 |
| `r9-trigger` | 查 R9 分：单票/多票下跌反转形态，或 `--today` 全市场反转确认名单 |
| `r1-mainline` | 查 R1 分：单票/多票动态主线强度，或 `--today` 当前主线行业与行业内前排 |
| `a-share-latest-rating` | 用回测定版的 R7+R1 组合查最近完整交易日观察评级 |
| `r0-data` | 本地行情仓：全量下载 / 增量更新 / 仓况检查 |

## 结构

```text
plugins/rule-trigger/
  docs/
    r0.md             # R0 方法、公式、回测方法和历史结果
    r7.md             # R7 方法、公式、回测方法和历史结果
    r9.md             # R9 方法、公式、回测结论(回测闭环在扫描器仓)
    r1.md             # R1 动态行业主线方法、公式和同仓回测结论
    a-share-rating.md # A股观察评级(R7+R1组合)方法、口径、回测结论
  scripts/            # skill 共用的后端
    r0.py             # 查询入口（自检：无参运行）
    r7.py             # R7 试盘后回踩查询入口（自检：无参运行）
    r9.py             # R9 下跌反转查询入口（自检：无参运行）
    r1.py             # R1 动态主线强度查询入口（自检：无参运行）
    a_share_latest_rating.py # R7+R1 组合观察评级与回测复现
    ai_tickers.txt    # 旧 AI R1 的历史快照；动态 R1 不再读取
    backtest_r0.py    # R0 历史回测（IC/lift/召回）
    backtest_r7.py    # 新版 R7 历史回测：和旧 R7 对照 IC/lift/召回
    bt_common.py      # 两个回测共用的协议口径（结果标签/IC/分桶/精度召回）
    store.py          # 数据仓：backfill / update / stat
    fetch.py          # sina 票池 + 日K（hfq）
    score.py          # 当前 R0/旧 R7；兼容旧版 R0-R8 综合评分接口
    features.py       # R0/旧版 R7 共用特征；兼容旧 outcome_return
    rules_config.yaml # 当前阈值 + 旧版综合评分兼容配置
  skills/r0-trigger/  # R0 查分 skill
  skills/r7-trigger/  # R7 查分 skill
  skills/r9-trigger/  # R9 查分 skill
  skills/r1-mainline/ # R1 查分 skill
  skills/a-share-latest-rating/ # A股最近观察评级 skill
  skills/r0-data/     # 数据 skill
```

- 数据在 `$R0_DATA_DIR`（缺省 `~/.r0-data`），不进插件、不进 git。K线为**后复权(hfq)**：除权缺口不污染涨幅/突破，且历史值不随未来除权改写、增量口径永远一致。
- R0 方法、公式、命令、回测方法和当前结论单独放在 `docs/r0.md`。
- R7 方法、公式、命令、回测方法和当前结论单独放在 `docs/r7.md`。
- **定位：R0 是"候选池里的票该不该扣扳机"，不是选股信号。** 满分票八成也不涨；先有基本面候选池，R0 只回答介入时机。
- **定位：R7 是"资金试过盘、最近在缩量回踩没有"，也不是选股信号。** R7 高只说明值得观察，真正动手仍要等 R0 或再次转强。
- **定位：R9 是"刚跌完企稳的票有没有放量大阳收复失地"，只有 5 分值得行动。** 3/4 分回测表现平平；单周期回测（约13个月），待 forward 检验。
- **定位：R1 是"市场主线正落在哪些行业、行业里谁在前排"的状态排序，不是扳机。** 5 分=动态主线行业内前 7%，2 分=主线行业掉队者；AI 不再是固定硬门，只有相关行业真实走强时才进入主线。
- **定位：a-share-latest-rating 是"观察池评级器"，不是交易建议。** 它把 R7 形态确认和 R1 动态主线强度组合成 S/A/B/C/D/N/A；规则先经历史回测定版。

## 规则文档

| 文档 | 内容 |
|---|---|
| `docs/r0.md` | R0 启动扳机：使用方法、公式、分数含义、阈值出处、回测方法、2026-07-06 回测结论 |
| `docs/r7.md` | R7 试盘后回踩：使用方法、公式、分数含义、回测方法、2026-07-05 回测结论 |
| `docs/r9.md` | R9 下跌反转：使用方法、公式、分数含义、2026-07-07 十轮迭代回测结论 |
| `docs/r1.md` | R1 动态主线强度：申万一级行业 5/20 日规则、分数含义、2026-07-12 同仓对照回测 |
| `docs/a-share-rating.md` | A股观察评级：R7+R1 组合分档、回测口径与结论、与扳机 skill 的分工 |

## 与扫描器的同步（维护者备忘）

权威版打分代码在私有扫描器仓库（vault `03-Trading/code/`），研究闭环（全市场验证/回测/权重迭代）都在那边跑。本插件的运行入口只依赖 R0 和对照用旧版 R7；`score.py`、`features.py`、`rules_config.yaml` 另保留旧版 R0-R8 综合评分兼容接口。扫描器迭代后按函数同步，不要删掉兼容接口。动态 R1 独立维护，不再同步 AI 白名单：

```bash
# 按函数同步 features.py、score_R0、score_R7 及其阈值
# r1.py 使用申万行业数据，不读取 ai_tickers.txt
```

维护者本机可把数据目录软链到扫描器的仓复用每日 cron：`ln -s <scanner-data> ~/.r0-data`。

## 扩展边界

`rule-trigger` 是插件级容器，可以放多个相关 skill；`r0-data` 和 `r0-trigger` 放在同一个插件里没有问题，因为它们共享同一个本地行情仓和同一套量价特征。

后续加规则时，不要把所有逻辑都塞进 `r0.py`。推荐边界：

- `store.py` / `fetch.py`：只负责本地行情仓和票池。
- `features.py` / `score.py` / `rules_config.yaml`：放插件入口、回测共用逻辑，以及已发布旧接口所需的最小兼容层。
- `r0.py`：只做 R0 单项扳机查询。
- `r7.py`：只做 R7 单项试盘回踩查询。当前是新版相对放量口径；要转正进扫描器前，先回测。
- `r9.py`：只做 R9 单项下跌反转查询。定版参数与扫描器仓 `r9_reversal.py` 同源（2026-07-07 iter7），改参数先在扫描器侧回测。
- `r1.py`：只做 R1 动态主线查询；申万行业指数与历史归属缓存在 `$R0_DATA_DIR`，首次使用或缓存超过 7 天时自动刷新。
- `a_share_latest_rating.py`：只做 R7+R1 组合观察评级和回测复现；最近日查询与历史回测必须共用同一个 `rate_combo()`。
- 新增 `scorecard.py` 或 `scan.py`：承接新版 R1-R8 综合评分、候选池扫描和排序；不要继续扩展 `score.py` 的旧版兼容实现。
- skill 层按用户意图拆：`r0-trigger` 查 R0，`r7-trigger` 查 R7，`r0-data` 管数据，后续再加 `rule-scorecard` / `rule-scan`。
