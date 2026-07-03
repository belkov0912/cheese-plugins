---
name: r0-data
description: >-
  r0-trigger 的本地行情仓管理——全量下载（backfill，首次建仓约45-90分钟，断点续跑）、
  增量更新（update，只重抓不新鲜的票；注意全市场隔天更新约1-1.5小时，数据源每次传全量历史）、仓况检查（stat）。
  数据是全A股约5300只的日K（后复权hfq，含换手），存用户本地 $R0_DATA_DIR（缺省 ~/.r0-data），不进插件不进git。
  Use whenever 用户要「建仓 / 下载行情数据 / 全量下载 / 增量更新 / 更新数据 / 数据到哪天了 / r0 数据仓多大」，
  或 r0-trigger 报「本地仓为空/数据过旧」时，或输入 /r0-data。
  Do NOT use for: 查 R0 分数（用 r0-trigger）；非 A 股数据。
---

# R0 数据仓 · 全量下载 / 增量更新

r0-trigger 打分要读本地行情仓（全A股日K parquet，后复权 hfq）。本 skill 负责建仓和保鲜。

## 脚本与数据在哪

- 脚本：本插件根目录 `scripts/store.py`（从本 SKILL.md 上两级即插件根；也可用 `${CLAUDE_PLUGIN_ROOT}/scripts`）。
- 数据目录：`$R0_DATA_DIR`，缺省 `~/.r0-data`。约 5300 个 parquet + `universe.csv`（票名快照），400 天日K合计约几百 MB。

## 第 0 步：环境自检（每次先做，10秒）

```bash
python3 -c "import akshare, pandas, pyarrow, yaml" 2>&1
```

- 通过 → 继续。
- 报 ModuleNotFoundError → 告诉用户缺哪个包，**征得同意后**帮装：`pip install -r <插件根>/scripts/requirements.txt`（或单装缺的那个）。装完重跑自检确认。
- 连 python3 都没有 → 如实报，让用户先装 Python 3.9+。
- 别跳过这步直接跑脚本：脚本虽会报缺依赖，但先装好能少跑一轮长任务。

## 三个命令

```bash
cd <插件根>/scripts

python3 store.py backfill --days 400    # 全量建仓：首次约45-90分钟；断点续跑，中断了重跑即可（已覆盖的自动跳过）
python3 store.py backfill --days 400 --limit 300   # 想先试水就小跑300只
python3 store.py update                 # 保鲜：只重抓"不新鲜"的票。⚠全市场隔天更新约1-1.5小时（见要点3）
python3 store.py stat                   # 仓况：多少只、样例最后日期
```

## 执行要点（照做，别发挥）

1. **先跑 `stat` 看现状**再决定全量还是增量：仓为空 → backfill；有仓但日期旧 → update；日期已是最近交易日 → 啥都不用做，如实回报。
2. **backfill 和 update 都是长任务，都用后台方式跑**（run_in_background），完成后跑 `stat` 验证并回报「N 只、数据截至 X」。别向用户承诺"几分钟"。
3. **update 为什么不快**：sina 日K接口每次调用都传该票**全量历史**、本地才切片——增量省的是"跳过已新鲜的票"，省不了单票网络量。全市场隔天更新 ≈ backfill 同量级（约1-1.5小时）；只有少数票过期时才快。
4. **限流是常态不是故障**：票池接口（sina 全A列表）偶尔返回 HTML 被限流——backfill 会自动回退用本地已有票列表。脚本内建"连续10只抓取失败即中止"保护，中止了如实转告原因（断网/限流），等几分钟重跑续上。**缺依赖会明确报 pip install 什么**，别把缺依赖当限流处理。
5. **盘中保护是内建的**：按北京时间 15:05 收盘前跑只补到昨天（防半根K线入仓），周末自动回拨到周五。这是设计不是 bug，别绕过。
6. **新上市的票由 backfill 纳入**（它拉最新票池）；update 只保鲜已有票。隔一阵重跑一次 backfill 即可补新股（已覆盖的会跳过，不会重下）。
7. **想每天自动保鲜**：告诉用户可以自己加一条定时任务（macOS launchd / Linux cron），每交易日 16:30 后跑 `python3 store.py update`。**只给命令和说明，不要主动替用户装定时任务**，用户明确要求才装。

## 口径（用户问起时讲清）

- **后复权(hfq)**：除权除息缺口不会假装成暴跌污染涨幅/突破计算；且后复权历史值不随未来除权改写，增量追加口径永远一致（这是选 hfq 不选 qfq 的原因）。
- 数据源 sina（经 akshare），免费公开接口，字段含每根K线换手率。
- `universe.csv` 是建仓时顺手存的票名快照，r0-trigger 用它做「名称→代码」解析；新股上市后要重跑一次 backfill 才能按名字查（按代码查不受影响）。
