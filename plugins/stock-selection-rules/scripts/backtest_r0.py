"""Backtest R0 launch-trigger on the local A-share kline store.

协议与 backtest_r7.py 完全一致（同一锚点网格、结果标签、θ 网格、逐窗口 IC，见 bt_common.py）：
- 每只股票沿历史每 outcome_len 个交易日取一个锚点（结果窗互不重叠）。
- R0 只用 <=锚点 的K线打分（features.compute_features 的下标约束，无未来函数）。
- 结果 = 锚点后 outcome_len 根内最大收盘涨幅，θ 扫 rules_config 的三档。
- 默认 universe 与 r7.py --today 一致：排除 bj* 和 sh688*，加 --include-bj688 可含。

历史备注：R0 首次 14 窗全市场回测（含 bj/688）在私有扫描器仓库跑（2026-07-02，均值 IC +0.07、11/14 窗为正）。
本脚本是其 R0 专用的插件版；扫描器的多规则回测（R0-R8+综合分）仍留在扫描器。
"""
from __future__ import annotations

import argparse
import datetime as dt
import os
import sys

import pandas as pd
import yaml

import bt_common as bt
import features
import score
import store

HERE = os.path.dirname(os.path.abspath(__file__))
DEFAULT_OUT = os.path.join(os.path.dirname(HERE), "out")


def _write_report(windows, pool, args, out_dir, cfg):
    os.makedirs(out_dir, exist_ok=True)
    run_date = dt.date.today().isoformat().replace("-", "")
    rp = os.path.join(out_dir, f"回测_R0_{run_date}.md")
    csvp = os.path.join(out_dir, f"回测_R0_明细_{run_date}.csv")
    pool.to_csv(csvp, index=False)

    labels = [w["anchor_date"] for w in windows]
    rules = [("R0", "R0")]
    summaries = bt.summary_rows(windows, rules)

    report = []
    report.append(f"# R0 启动扳机历史回测 {run_date}\n")
    report.append("## 口径\n")
    report.append(f"- 数据仓：`{store.STORE}`（后复权 hfq）")
    report.append(f"- 数据截至：{pool['data_last'].max() if len(pool) else '—'}")
    report.append(f"- 样本：{len(pool)} 条 stock-window；{len(windows)} 个不重叠窗口；锚点间隔 {args.step or cfg['windows']['outcome_len']} 个交易日")
    report.append(f"- 结果标签：锚点后 {cfg['windows']['outcome_len']} 个交易日内最大收盘涨幅 >= θ")
    universe = "包含 bj*/sh688*（--include-bj688）" if args.include_bj688 else "排除 bj* 和 sh688*（默认，与 backtest_r7 同口径）"
    report.append(f"- universe：{universe}；不额外做基本面/主线过滤。")
    report.append("- R0 打分只用 <=锚点 的K线（无未来函数）；R0 是纯量价规则，无市值/财报前视问题。\n")

    report.append("## 逐窗口 Spearman IC\n")
    report.append("| 规则 | " + " | ".join(labels) + " | 均值 | IC>0窗口 |")
    report.append("|---|" + "--:|" * (len(labels) + 2))
    for row in summaries:
        cells = " | ".join(bt.fmt_num(x, 2) for x in row["ics"])
        report.append(f"| {row['rule']} | {cells} | {bt.fmt_num(row['mean_ic'], 2)} | {row['ic_positive']}/{row['ic_windows']} |")

    for theta in cfg["outcome"]["thetas"]:
        base = (pool["outcome_ret"] >= theta).mean()
        report.append(f"\n## 合并分桶 θ={int(theta * 100)}%，基础命中率 {bt.fmt_pct(base)}（N={len(pool)}）\n")
        report.append("| 分数 | n | 命中率 | lift |")
        report.append("|--:|--:|--:|--:|")
        for s, n, rate in bt.bucket_table(pool, "R0", theta):
            lift = rate / base if base and rate == rate else float("nan")
            report.append(f"| {s} | {n} | {bt.fmt_pct(rate)} | {bt.fmt_num(lift, 2)} |")
        report.append("\n### R0>=4 扳机名单表现\n")
        report.append("| 选中数 | 选中命中 | 精度 | 赢家召回 | 覆盖率 |")
        report.append("|--:|--:|--:|--:|--:|")
        selected, hits, precision, recall, coverage = bt.coverage_precision(pool, "R0", theta, min_score=4)
        report.append(f"| {selected} | {hits} | {bt.fmt_pct(precision)} | {bt.fmt_pct(recall)} | {bt.fmt_pct(coverage)} |")

    hi = max(cfg["outcome"]["thetas"])
    report.append(f"\n## 赢家召回（O内 >= {int(hi * 100)}%）\n")
    winners = pool[pool["outcome_ret"] >= hi]
    if len(winners):
        cnt = int((winners["R0"] >= 4).sum())
        report.append(f"- R0>=4 覆盖赢家：{cnt}/{len(winners)}（{cnt / len(winners) * 100:.1f}%）")
    else:
        report.append("- 合并样本里没有 >=50% 赢家。")

    report.append("\n## 快速结论\n")
    r0 = summaries[0]
    report.append(f"- R0 均值 IC：{bt.fmt_num(r0['mean_ic'], 2)}，IC>0 窗口：{r0['ic_positive']}/{r0['ic_windows']}。")
    report.append("- 这只是量价历史回放，不含主线、财报、公告过滤；R0 是扳机不是选股器，满分票多数也不涨。")

    with open(rp, "w", encoding="utf-8") as f:
        f.write("\n".join(report) + "\n")
    return rp, csvp


def run(args):
    cfg = yaml.safe_load(open(os.path.join(HERE, "rules_config.yaml"), encoding="utf-8"))
    w = cfg["windows"]
    outcome_len = int(w["outcome_len"])
    step = args.step or outcome_len
    min_anchor = w["pre20_len"] + w["breakout_lookback"] + w["launch_len"] - 1  # compute_features 最小可行锚点

    syms = store.list_symbols()
    if not args.include_bj688:
        syms = [s for s in syms if not bt.is_bj688(s)]
    syms = sorted(syms)
    if args.limit:
        syms = syms[: args.limit]
    if not syms:
        raise SystemExit(f"本地仓为空或被过滤空（{store.STORE}）。先跑 r0-data 建仓。")

    rows_by_window = {}
    total = len(syms)
    for i, sym in enumerate(syms):
        if i % 500 == 0:
            print(f"  {i}/{total}", file=sys.stderr)
        frame = store.load_frame(sym)
        if not frame:
            continue
        n = len(frame["date"])
        k = 0
        while True:
            anchor = n - 1 - outcome_len - k * step
            if anchor < min_anchor:
                break
            outcome = bt.outcome_return(frame, anchor, outcome_len)
            if outcome is None:
                break
            feat = features.compute_features(frame, anchor, cfg)
            if feat is None:
                k += 1
                continue
            tier, desc = score.score_R0(feat, cfg)
            rows_by_window.setdefault(k, []).append({
                "code": sym,
                "anchor_date": frame["date"][anchor],
                "data_last": frame["date"][-1],
                "R0": int(tier),
                "outcome_ret": outcome,
                "R0_desc": desc,
            })
            k += 1

    windows = []
    for k in sorted(rows_by_window, reverse=True):
        df = pd.DataFrame(rows_by_window[k])
        if len(df):
            windows.append({"anchor_date": df["anchor_date"].mode().iloc[0], "df": df})
    if not windows:
        raise SystemExit("回测无可用窗口：数据不足或全部被过滤。")
    pool = pd.concat([w["df"] for w in windows], ignore_index=True)
    rp, csvp = _write_report(windows, pool, args, args.out, cfg)
    print(f"回测窗口 {len(windows)} 个，样本 {len(pool)} 条")
    print(f"报告: {rp}")
    print(f"明细: {csvp}")
    print(open(rp, encoding="utf-8").read())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=0, help="只回测前 N 只，0=全量")
    ap.add_argument("--step", type=int, default=0, help="锚点间隔，默认=outcome_len")
    ap.add_argument("--include-bj688", action="store_true", help="包含 bj* 和 sh688*（默认排除）")
    ap.add_argument("--out", default=DEFAULT_OUT, help="输出目录，默认 plugins/stock-selection-rules/out")
    args = ap.parse_args()
    run(args)


if __name__ == "__main__":
    main()
