# r0-trigger

R0「启动扳机」即时查：给一只/多只 A 股算最近 5 个交易日里「放量强阳突破」启动确认K线的成色（1-5 分），带证据化描述（哪天、涨幅、量比、破几日高、换手）。**自带全部脚本，行情数据下载到用户本地**——装上插件、建一次仓，任何机器都能用。

## 快速开始

```text
1. 安装插件（/plugins → cheese-plugins → r0-trigger），机器上有 python3 即可
2. 建仓：/r0-data → skill 会先自检依赖（缺了征得同意后自动 pip install），
   然后全量下载（约45-90分钟，断点续跑）；隔天保鲜用 update，
   全市场约1-1.5小时——sina 每次传全量历史，增量省不了网络，建议后台/定时跑
3. 查询：/r0-trigger 景旺电子   或   /r0-trigger 最近谁扣扳机了
```

## 两个 skill

| skill | 干什么 |
|---|---|
| `r0-trigger` | 查 R0 分：单票/多票（名称或代码），或 `--today` 全市场扣扳机名单 |
| `r0-data` | 本地行情仓：全量下载 / 增量更新 / 仓况检查 |

## 结构

```text
plugins/r0-trigger/
  scripts/            # 两个 skill 共用的后端
    r0.py             # 查询入口（自检：无参运行）
    store.py          # 数据仓：backfill / update / stat
    fetch.py          # sina 票池 + 日K（hfq）
    score.py          # R0-R8 打分（与扫描器逐字同源）
    features.py       # 量价特征（与扫描器逐字同源）
    rules_config.yaml # 阈值快照
  skills/r0-trigger/  # 查分 skill
  skills/r0-data/     # 数据 skill
```

- 数据在 `$R0_DATA_DIR`（缺省 `~/.r0-data`），不进插件、不进 git。K线为**后复权(hfq)**：除权缺口不污染涨幅/突破，且历史值不随未来除权改写、增量口径永远一致。
- 打分逻辑来自翻倍股扫描器的 `score_R0`（38 只翻倍股研究定阈值，14 个历史窗口全市场验证：IC 均值 +0.07、5 分组命中率约为基础 2 倍）。
- **定位：R0 是"候选池里的票该不该扣扳机"，不是选股信号。** 满分票八成也不涨；先有基本面候选池，R0 只回答介入时机。

## 与扫描器的同步（维护者备忘）

权威版打分代码在私有扫描器仓库（vault `03-Trading/code/`），研究闭环（全市场验证/回测/权重迭代）都在那边跑。本插件的 `score.py`/`features.py` 是逐字副本、`rules_config.yaml` 是去掉本机 paths 段的快照。扫描器迭代后要同步：

```bash
cp <scanner>/features.py <scanner>/score.py plugins/r0-trigger/scripts/
# 再对照 rules_config.yaml 的阈值/权重，更新快照日期注释
```

维护者本机可把数据目录软链到扫描器的仓复用每日 cron：`ln -s <scanner-data> ~/.r0-data`。
