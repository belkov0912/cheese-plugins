# rule-trigger

规则触发器工具箱：先提供 R0「启动扳机」即时查、R7「试盘后回踩」即时查和本地行情仓，后续可扩展 R1-R8 评分、扫描和复盘。R0 查最近 5 个交易日里有没有「放量强阳突破」；R7 查最近 20 个交易日里有没有「相对放量试盘 → 缩量回踩」。**自带全部脚本，行情数据下载到用户本地**——装上插件、建一次仓，任何机器都能用。

## 快速开始

```text
1. 安装插件（/plugins → cheese-plugins → rule-trigger），机器上有 python3 即可
2. 建仓：/r0-data → skill 会先自检依赖（缺了征得同意后自动 pip install），
   然后全量下载（约45-90分钟，断点续跑）；隔天保鲜用 update，
   全市场约1-1.5小时——sina 每次传全量历史，增量省不了网络，建议后台/定时跑
3. 查询：/r0-trigger 景旺电子   或   /r7-trigger 景旺电子
```

## 三个 skill

| skill | 干什么 |
|---|---|
| `r0-trigger` | 查 R0 分：单票/多票（名称或代码），或 `--today` 全市场扣扳机名单 |
| `r7-trigger` | 查 R7 分：单票/多票试盘后回踩形态，或 `--today` 全市场 R7 高分名单 |
| `r0-data` | 本地行情仓：全量下载 / 增量更新 / 仓况检查 |

## 结构

```text
plugins/rule-trigger/
  docs/
    r7.md             # R7 方法、公式、回测方法和历史结果
  scripts/            # skill 共用的后端
    r0.py             # 查询入口（自检：无参运行）
    r7.py             # R7 试盘后回踩查询入口（自检：无参运行）
    backtest_r7.py    # 新版 R7 历史回测：和旧 R7 对照 IC/lift/召回
    store.py          # 数据仓：backfill / update / stat
    fetch.py          # sina 票池 + 日K（hfq）
    score.py          # R0-R8 打分（与扫描器逐字同源）
    features.py       # 量价特征（与扫描器逐字同源）
    rules_config.yaml # 阈值快照
  skills/r0-trigger/  # R0 查分 skill
  skills/r7-trigger/  # R7 查分 skill
  skills/r0-data/     # 数据 skill
```

- 数据在 `$R0_DATA_DIR`（缺省 `~/.r0-data`），不进插件、不进 git。K线为**后复权(hfq)**：除权缺口不污染涨幅/突破，且历史值不随未来除权改写、增量口径永远一致。
- R0 打分逻辑来自翻倍股扫描器的 `score_R0`（38 只翻倍股研究定阈值，14 个历史窗口全市场验证：IC 均值 +0.07、5 分组命中率约为基础 2 倍）。
- R7 方法、公式、命令、回测方法和当前结论单独放在 `docs/r7.md`。
- **定位：R0 是"候选池里的票该不该扣扳机"，不是选股信号。** 满分票八成也不涨；先有基本面候选池，R0 只回答介入时机。
- **定位：R7 是"资金试过盘、最近在缩量回踩没有"，也不是选股信号。** R7 高只说明值得观察，真正动手仍要等 R0 或再次转强。

## 规则文档

| 文档 | 内容 |
|---|---|
| `docs/r7.md` | R7 试盘后回踩：使用方法、公式、分数含义、回测方法、2026-07-05 回测结论 |

## 与扫描器的同步（维护者备忘）

权威版打分代码在私有扫描器仓库（vault `03-Trading/code/`），研究闭环（全市场验证/回测/权重迭代）都在那边跑。本插件的 `score.py`/`features.py` 是逐字副本、`rules_config.yaml` 是去掉本机 paths 段的快照。扫描器迭代后要同步：

```bash
cp <scanner>/features.py <scanner>/score.py plugins/rule-trigger/scripts/
# 再对照 rules_config.yaml 的阈值/权重，更新快照日期注释
```

维护者本机可把数据目录软链到扫描器的仓复用每日 cron：`ln -s <scanner-data> ~/.r0-data`。

## 扩展边界

`rule-trigger` 是插件级容器，可以放多个相关 skill；`r0-data` 和 `r0-trigger` 放在同一个插件里没有问题，因为它们共享同一个本地行情仓和同一套量价特征。

后续加 R1-R8 时，不要把所有逻辑都塞进 `r0.py`。推荐边界：

- `store.py` / `fetch.py`：只负责本地行情仓和票池。
- `features.py` / `score.py` / `rules_config.yaml`：只负责规则特征和 R0-R8 打分。
- `r0.py`：只做 R0 单项扳机查询。
- `r7.py`：只做 R7 单项试盘回踩查询。当前是新版相对放量口径；要转正进扫描器前，先回测。
- 新增 `scorecard.py` 或 `scan.py`：承接 R1-R8 综合评分、候选池扫描和排序。
- skill 层按用户意图拆：`r0-trigger` 查 R0，`r7-trigger` 查 R7，`r0-data` 管数据，后续再加 `rule-scorecard` / `rule-scan`。
