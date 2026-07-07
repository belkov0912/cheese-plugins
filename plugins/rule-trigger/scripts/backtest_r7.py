"""Backtest R7 probe-and-pullback definitions on the local A-share kline store.

This script compares:
- R7_new: the plugin's relative-volume probe -> pullback definition in r7.py
- R7_old: the original scanner score.score_R7 definition in score.py

Backtest protocol:
- For each stock, pick historical anchors every outcome_len trading days.
- At each anchor, truncate the frame to <= anchor before scoring R7_new.
- Outcome is max close return over the next outcome_len bars.
- Default universe matches r7.py --today: exclude bj* and sh688*.
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
import r7
import score
import store

HERE = os.path.dirname(os.path.abspath(__file__))
DEFAULT_OUT = os.path.join(os.path.dirname(HERE), "out")

# 结果标签/IC/分桶/精度召回等协议口径统一在 bt_common.py，与 backtest_r0.py 共用
_outcome_return = bt.outcome_return
_safe_ic = bt.safe_ic
_fmt_pct = bt.fmt_pct
_fmt_num = bt.fmt_num
_bucket_table = bt.bucket_table
_coverage_precision = bt.coverage_precision
_summary_rows = bt.summary_rows


def _frame_slice(frame, end_idx):
    return {k: v[: end_idx + 1] for k, v in frame.items()}


def _write_report(windows, pool, args, out_dir, cfg):
    os.makedirs(out_dir, exist_ok=True)
    run_date = dt.date.today().isoformat().replace("-", "")
    rp = os.path.join(out_dir, f"回测_R7_{run_date}.md")
    csvp = os.path.join(out_dir, f"回测_R7_明细_{run_date}.csv")
    pool.to_csv(csvp, index=False)

    labels = [w["anchor_date"] for w in windows]
    rules = [("R7_new", "R7_new"), ("R7_old", "R7_old")]
    summaries = _summary_rows(windows, rules)

    report = []
    report.append(f"# R7 新口径历史回测 {run_date}\n")
    report.append("## 口径\n")
    report.append(f"- 数据仓：`{store.STORE}`")
    report.append(f"- 数据截至：{pool['data_last'].max() if len(pool) else '—'}")
    report.append(f"- 样本：{len(pool)} 条 stock-window；{len(windows)} 个不重叠窗口；锚点间隔 {args.step or cfg['windows']['outcome_len']} 个交易日")
    report.append(f"- 结果标签：锚点后 {cfg['windows']['outcome_len']} 个交易日内最大收盘涨幅 >= θ")
    report.append("- 默认 universe：排除 bj* 和 sh688*；不额外做基本面/主线过滤。")
    report.append("- `R7_new` 每个锚点都先截断到当日再算，避免未来K线进特征。")
    report.append("- `R7_old` 是原 `score.py` 里的绝对换手试盘回踩口径，用来做参照。\n")

    report.append("## 逐窗口 Spearman IC\n")
    report.append("| 规则 | " + " | ".join(labels) + " | 均值 | IC>0窗口 |")
    report.append("|---|" + "--:|" * (len(labels) + 2))
    for row in summaries:
        cells = " | ".join(_fmt_num(x, 2) for x in row["ics"])
        report.append(f"| {row['rule']} | {cells} | {_fmt_num(row['mean_ic'], 2)} | {row['ic_positive']}/{row['ic_windows']} |")

    for theta in cfg["outcome"]["thetas"]:
        base = (pool["outcome_ret"] >= theta).mean()
        report.append(f"\n## 合并分桶 θ={int(theta * 100)}%，基础命中率 {_fmt_pct(base)}（N={len(pool)}）\n")
        report.append("| 规则 | 分数 | n | 命中率 | lift |")
        report.append("|---|--:|--:|--:|--:|")
        for rname, col in rules:
            for s, n, rate in _bucket_table(pool, col, theta):
                lift = rate / base if base and rate == rate else float("nan")
                report.append(f"| {rname} | {s} | {n} | {_fmt_pct(rate)} | {_fmt_num(lift, 2)} |")
        report.append("\n### R7>=4 观察名单表现\n")
        report.append("| 规则 | 选中数 | 选中命中 | 精度 | 赢家召回 | 覆盖率 |")
        report.append("|---|--:|--:|--:|--:|--:|")
        for rname, col in rules:
            selected, hits, precision, recall, coverage = _coverage_precision(pool, col, theta, min_score=4)
            report.append(f"| {rname} | {selected} | {hits} | {_fmt_pct(precision)} | {_fmt_pct(recall)} | {_fmt_pct(coverage)} |")

    hi = max(cfg["outcome"]["thetas"])
    report.append(f"\n## 赢家召回（O内 >= {int(hi * 100)}%）\n")
    winners = pool[pool["outcome_ret"] >= hi]
    if len(winners):
        for rname, col in rules:
            cnt = int((winners[col] >= 4).sum())
            report.append(f"- {rname}>=4 覆盖赢家：{cnt}/{len(winners)}（{cnt / len(winners) * 100:.1f}%）")
    else:
        report.append("- 合并样本里没有 >=50% 赢家。")

    report.append("\n## 快速结论\n")
    new = next(x for x in summaries if x["rule"] == "R7_new")
    old = next(x for x in summaries if x["rule"] == "R7_old")
    report.append(f"- R7_new 均值 IC：{_fmt_num(new['mean_ic'], 2)}，IC>0 窗口：{new['ic_positive']}/{new['ic_windows']}。")
    report.append(f"- R7_old 均值 IC：{_fmt_num(old['mean_ic'], 2)}，IC>0 窗口：{old['ic_positive']}/{old['ic_windows']}。")
    report.append("- 这只是价格/量能历史回放，不含主线、财报、公告过滤；R7 高分只能当观察名单，不能单独当买点。")

    with open(rp, "w", encoding="utf-8") as f:
        f.write("\n".join(report) + "\n")
    return rp, csvp


def run(args):
    cfg = yaml.safe_load(open(os.path.join(HERE, "rules_config.yaml"), encoding="utf-8"))
    outcome_len = int(cfg["windows"]["outcome_len"])
    step = args.step or outcome_len
    min_anchor = max(
        r7.REL_LOOKBACK + r7.SETUP_LEN - 1,
        cfg["windows"]["pre20_len"] + cfg["windows"]["breakout_lookback"] + cfg["windows"]["launch_len"] - 1,
    )

    syms = store.list_symbols()
    if not args.include_bj688:
        syms = [s for s in syms if not r7._is_default_today_excluded(s)]
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
            outcome = _outcome_return(frame, anchor, outcome_len)
            if outcome is None:
                break
            hist = _frame_slice(frame, anchor)
            new_score, new_desc, _ = r7.score_r7(hist)
            if new_score is None:
                k += 1
                continue
            old_feat = features.compute_features(frame, anchor, cfg)
            if old_feat is None:
                k += 1
                continue
            old_score, old_desc = score.score_R7(old_feat, cfg)
            row = {
                "code": sym,
                "anchor_date": frame["date"][anchor],
                "data_last": frame["date"][-1],
                "R7_new": int(new_score),
                "R7_old": int(old_score),
                "outcome_ret": outcome,
                "R7_new_desc": new_desc,
                "R7_old_desc": old_desc,
            }
            rows_by_window.setdefault(k, []).append(row)
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
    ap.add_argument("--out", default=DEFAULT_OUT, help="输出目录，默认 plugins/rule-trigger/out")
    args = ap.parse_args()
    run(args)


if __name__ == "__main__":
    main()
