#!/usr/bin/env python3
"""Backtest and apply the A-share latest observation rating.

The script intentionally reuses the rule-trigger plugin implementation:
- R7 comes from r7.score_r7 on a frame truncated at anchor date.
- R1R3 is rebuilt cross-sectionally for each historical anchor date with the
  current AI whitelist. That makes the historical result an upper-bound version
  because the whitelist itself is a current snapshot.

Default universe excludes bj* and sh688*, matching r7/r1r3 plugin defaults.
"""
from __future__ import annotations

import argparse
import bisect
import csv
import datetime as dt
import math
import os
import random
import re
import sys
from collections import defaultdict
from pathlib import Path

import pandas as pd


DEFAULT_RULE_SCRIPTS = Path(__file__).resolve().parent
RULE_SCRIPTS = Path(os.environ.get("RULE_TRIGGER_SCRIPTS", DEFAULT_RULE_SCRIPTS)).expanduser()
if not RULE_SCRIPTS.exists():
    raise SystemExit(f"rule-trigger scripts not found: {RULE_SCRIPTS}")
sys.path.insert(0, str(RULE_SCRIPTS))

import r1r3  # noqa: E402
import r7  # noqa: E402
import store  # noqa: E402


OUTCOME_WINDOWS = (5, 10, 20)
DEFAULT_STEP = 10
DEFAULT_RANDOM_N = 10000
DEFAULT_OUT = DEFAULT_RULE_SCRIPTS.parent / "out" / "a-share-latest-rating"
UNIVERSE_EXCLUDES = ("bj", "sh688")
AI_WHITELIST_FORWARD_LOOKING = True


# Iteration rule block. Change only one small rule unit per optimization round.
RULE_VERSION = "v2_a_requires_r1r3_4"
S_MIN_R7 = 4
S_MIN_R1R3 = 5
S_MIN_TOTAL = 9
A_MIN_R1R3 = 4
A_MIN_TOTAL = 8
B_CORE_MIN = 4
FILTER_R1R3_2_TO_D = False


def is_excluded(sym: str) -> bool:
    return sym.startswith(UNIVERSE_EXCLUDES)


def pct(x: float | None) -> str:
    if x is None or (isinstance(x, float) and math.isnan(x)):
        return "-"
    return f"{x * 100:.1f}%"


def num(x: float | None, nd: int = 2) -> str:
    if x is None or (isinstance(x, float) and math.isnan(x)):
        return "-"
    return f"{x:.{nd}f}"


def frame_slice(frame: dict[str, list], end_idx: int) -> dict[str, list]:
    return {k: v[: end_idx + 1] for k, v in frame.items()}


def date_index(frame: dict[str, list]) -> dict[str, int]:
    return {str(d): i for i, d in enumerate(frame["date"])}


def load_name_map() -> dict[str, str]:
    path = Path(store.STORE) / "universe.csv"
    out: dict[str, str] = {}
    if path.exists():
        with path.open(encoding="utf-8") as f:
            for row in csv.DictReader(f):
                out[row["code"]] = row["name"]
    return out


def load_frames(limit: int = 0, include_bj688: bool = False) -> dict[str, dict[str, list]]:
    syms = sorted(store.list_symbols())
    if not include_bj688:
        syms = [s for s in syms if not is_excluded(s)]
    if limit:
        syms = syms[:limit]
    frames: dict[str, dict[str, list]] = {}
    for i, sym in enumerate(syms):
        if i % 500 == 0:
            print(f"  load {i}/{len(syms)}", file=sys.stderr)
        frame = store.load_frame(sym)
        if frame and len(frame["date"]) >= 80:
            frames[sym] = frame
    return frames


def store_data_max(frames: dict[str, dict[str, list]]) -> str | None:
    lasts = [f["date"][-1] for f in frames.values() if f.get("date")]
    return max(lasts) if lasts else None


def latest_complete_trade_date() -> str:
    return store._data_end_date()  # intentionally uses rule-trigger's Beijing-time logic


def r7_probe_age(desc: str, hist: dict[str, list]) -> int | None:
    match = re.search(r"试盘(\d{4}-\d{2}-\d{2})", desc)
    if not match:
        return None
    d = match.group(1)
    try:
        idx = len(hist["date"]) - 1 - list(reversed(hist["date"])).index(d)
    except ValueError:
        return None
    return len(hist["date"]) - 1 - idx


def future_metrics(frame: dict[str, list], anchor_idx: int) -> dict[str, float] | None:
    close0 = float(frame["close"][anchor_idx])
    if not close0 or anchor_idx + max(OUTCOME_WINDOWS) >= len(frame["close"]):
        return None
    out: dict[str, float] = {}
    for n in OUTCOME_WINDOWS:
        highs = frame["high"][anchor_idx + 1 : anchor_idx + 1 + n]
        out[f"max_ret_{n}"] = max(float(x) for x in highs) / close0 - 1
    lows20 = frame["low"][anchor_idx + 1 : anchor_idx + 21]
    out["max_drawdown_20"] = min(float(x) for x in lows20) / close0 - 1

    pre_hit_low = float("inf")
    hit10_seen = False
    for high, low in zip(
        frame["high"][anchor_idx + 1 : anchor_idx + 21],
        frame["low"][anchor_idx + 1 : anchor_idx + 21],
    ):
        pre_hit_low = min(pre_hit_low, float(low))
        if float(high) / close0 - 1 >= 0.10:
            hit10_seen = True
            break
    if not hit10_seen:
        pre_hit_low = min(float(x) for x in lows20)
    out["drawdown_before_hit10"] = pre_hit_low / close0 - 1
    return out


def build_anchor_rows(
    frames: dict[str, dict[str, list]],
    step: int,
    sample_start: str | None,
    sample_end: str | None,
) -> tuple[list[dict], set[str]]:
    rows: list[dict] = []
    needed_dates: set[str] = set()
    min_anchor = max(r7.MIN_BARS - 1, r1r3.RET_N)
    outcome_len = max(OUTCOME_WINDOWS)
    for sym, frame in frames.items():
        n = len(frame["date"])
        anchor = n - 1 - outcome_len
        while anchor >= min_anchor:
            anchor_date = str(frame["date"][anchor])
            if sample_start and anchor_date < sample_start:
                break
            if sample_end and anchor_date > sample_end:
                anchor -= step
                continue
            metrics = future_metrics(frame, anchor)
            if metrics is not None:
                rows.append({"code": sym, "anchor_idx": anchor, "anchor_date": anchor_date})
                needed_dates.add(anchor_date)
            anchor -= step
    return rows, needed_dates


def build_r1r3_context(
    frames: dict[str, dict[str, list]],
    needed_dates: set[str],
) -> dict[str, dict[str, tuple[float, float, int]]]:
    whitelist = r1r3.load_whitelist()
    index_by_sym = {sym: date_index(frame) for sym, frame in frames.items()}
    by_date: dict[str, list[tuple[str, float]]] = defaultdict(list)
    for sym, frame in frames.items():
        if is_excluded(sym) or sym[2:] not in whitelist:
            continue
        idx_map = index_by_sym[sym]
        close = frame["close"]
        for d in needed_dates:
            idx = idx_map.get(d)
            if idx is None or idx < r1r3.RET_N:
                continue
            base = float(close[idx - r1r3.RET_N])
            if base:
                by_date[d].append((sym, float(close[idx]) / base - 1))

    context: dict[str, dict[str, tuple[float, float, int]]] = {}
    for d, vals in by_date.items():
        sorted_vals = sorted(ret for _, ret in vals)
        n = len(sorted_vals)
        daily: dict[str, tuple[float, float, int]] = {}
        for sym, ret in vals:
            rank = bisect.bisect_right(sorted_vals, ret) / n if n else 0.0
            daily[sym] = (rank, ret, n)
        context[d] = daily
    return context


def r1r3_score_for(
    sym: str,
    anchor_date: str,
    r1_context: dict[str, dict[str, tuple[float, float, int]]],
    whitelist: set[str],
) -> tuple[int | None, float | None, float | None, int]:
    if is_excluded(sym):
        return None, None, None, 0
    if sym[2:] not in whitelist:
        return 1, None, None, 0
    row = r1_context.get(anchor_date, {}).get(sym)
    if row is None:
        return None, None, None, len(r1_context.get(anchor_date, {}))
    rank, ret20, cohort_n = row
    return r1r3.tier_from_rank(rank), rank, ret20, cohort_n


def rate_combo(r7_score: int | None, r1_score: int | None) -> tuple[str, str]:
    if r7_score is None or r1_score is None:
        return "N/A", "数据不足"
    total = r7_score + r1_score
    if FILTER_R1R3_2_TO_D and r1_score == 2:
        return "D", "R1R3=2 主线掉队过滤"
    if r7_score >= S_MIN_R7 and r1_score >= S_MIN_R1R3 and total >= S_MIN_TOTAL:
        return "S", f"R7>={S_MIN_R7} 且 R1R3>={S_MIN_R1R3} 且总分>={S_MIN_TOTAL}"
    if (
        r1_score >= A_MIN_R1R3
        and total >= A_MIN_TOTAL
        and (r7_score >= B_CORE_MIN or r1_score >= B_CORE_MIN)
    ):
        return "A", f"总分>={A_MIN_TOTAL} 且至少一个核心因子>={B_CORE_MIN}"
    if r7_score >= B_CORE_MIN or r1_score >= B_CORE_MIN:
        return "B", f"至少一个核心因子>={B_CORE_MIN}"
    if r1_score <= 2 and r7_score <= 2:
        return "D", "主线或形态都弱"
    return "C", "证据不足"


def build_pool(args: argparse.Namespace) -> tuple[pd.DataFrame, dict[str, str]]:
    frames = load_frames(args.limit, args.include_bj688)
    if not frames:
        raise SystemExit(f"本地仓为空或可用数据不足: {store.STORE}")
    rows, needed_dates = build_anchor_rows(frames, args.step, args.start, args.end)
    if not rows:
        raise SystemExit("无可用回测样本：检查日期区间、step 或数据长度。")
    print(f"  anchors {len(rows)}; r1r3 dates {len(needed_dates)}", file=sys.stderr)
    r1_context = build_r1r3_context(frames, needed_dates)
    whitelist = r1r3.load_whitelist()
    names = load_name_map()

    out = []
    for i, row in enumerate(rows):
        if i % 10000 == 0:
            print(f"  score {i}/{len(rows)}", file=sys.stderr)
        sym = row["code"]
        anchor = row["anchor_idx"]
        frame = frames[sym]
        hist = frame_slice(frame, anchor)
        r7_score, r7_desc, _ = r7.score_r7(hist)
        r1_score, rank, ret20, cohort_n = r1r3_score_for(
            sym, row["anchor_date"], r1_context, whitelist
        )
        rating, reason = rate_combo(r7_score, r1_score)
        metrics = future_metrics(frame, anchor)
        if metrics is None or rating == "N/A":
            continue
        out.append(
            {
                "code": sym,
                "name": names.get(sym, ""),
                "anchor_date": row["anchor_date"],
                "quarter": pd.Period(row["anchor_date"], freq="Q").strftime("%YQ%q"),
                "r7": int(r7_score),
                "r7_probe_age": r7_probe_age(r7_desc, hist),
                "r1r3": int(r1_score),
                "r1r3_rank": rank,
                "r1r3_ret20": ret20,
                "r1r3_cohort_n": cohort_n,
                "rating": rating,
                "rating_reason": reason,
                "hit10": metrics["max_ret_20"] >= 0.10,
                "hit20": metrics["max_ret_20"] >= 0.20,
                **metrics,
            }
        )
    pool = pd.DataFrame(out)
    meta = {
        "data_max": store_data_max(frames) or "-",
        "target_latest": latest_complete_trade_date(),
        "sample_start": pool["anchor_date"].min() if len(pool) else "-",
        "sample_end": pool["anchor_date"].max() if len(pool) else "-",
    }
    return pool, meta


def subset_metrics(df: pd.DataFrame) -> dict[str, float | int]:
    if len(df) == 0:
        return {
            "n": 0,
            "hit10_5": math.nan,
            "hit10_10": math.nan,
            "hit10": math.nan,
            "hit20": math.nan,
            "avg_max20": math.nan,
            "avg_dd20": math.nan,
            "avg_pre_hit10_dd": math.nan,
        }
    return {
        "n": int(len(df)),
        "hit10_5": float((df["max_ret_5"] >= 0.10).mean()),
        "hit10_10": float((df["max_ret_10"] >= 0.10).mean()),
        "hit10": float(df["hit10"].mean()),
        "hit20": float(df["hit20"].mean()),
        "avg_max20": float(df["max_ret_20"].mean()),
        "avg_dd20": float(df["max_drawdown_20"].mean()),
        "avg_pre_hit10_dd": float(df["drawdown_before_hit10"].mean()),
    }


def metric_row(label: str, df: pd.DataFrame) -> str:
    m = subset_metrics(df)
    return (
        f"| {label} | {m['n']} | {pct(m['hit10_5'])} | {pct(m['hit10_10'])} | "
        f"{pct(m['hit10'])} | {pct(m['hit20'])} | {pct(m['avg_max20'])} | "
        f"{pct(m['avg_dd20'])} | {pct(m['avg_pre_hit10_dd'])} |"
    )


def selected_baselines(pool: pd.DataFrame, random_n: int, seed: int) -> list[tuple[str, pd.DataFrame, str]]:
    n = min(random_n, len(pool))
    random_df = pool.sample(n=n, random_state=seed) if n < len(pool) else pool.copy()
    return [
        (f"全市场随机样本(seed={seed}, n={n})", random_df, "从全样本确定性抽样"),
        ("R7 单因子: R7>=4", pool[pool["r7"] >= 4], "只看试盘回踩形态"),
        ("R1R3 单因子: R1R3>=4", pool[pool["r1r3"] >= 4], "只看主线内相对强度"),
        (
            "简单交集: R7>=4 且 R1R3>=4",
            pool[(pool["r7"] >= 4) & (pool["r1r3"] >= 4)],
            "两个因子硬交集",
        ),
        ("R1R3=5 单独前排", pool[pool["r1r3"] == 5], "主线前7%"),
    ]


def rating_table(pool: pd.DataFrame) -> list[str]:
    rows = [
        "| 评级 | n | 5日hit10 | 10日hit10 | 20日hit10 | 20日hit20 | 平均20日最大涨幅 | 平均20日最大回撤 | 平均hit10前回撤 |",
        "|---|--:|--:|--:|--:|--:|--:|--:|--:|",
    ]
    order = ["S", "A", "B", "C", "D"]
    for rating in order:
        rows.append(metric_row(rating, pool[pool["rating"] == rating]))
    return rows


def baseline_table(pool: pd.DataFrame, random_n: int, seed: int) -> list[str]:
    rows = [
        "| baseline | n | 5日hit10 | 10日hit10 | 20日hit10 | 20日hit20 | 平均20日最大涨幅 | 平均20日最大回撤 | 平均hit10前回撤 |",
        "|---|--:|--:|--:|--:|--:|--:|--:|--:|",
    ]
    for label, df, _ in selected_baselines(pool, random_n, seed):
        rows.append(metric_row(label, df))
    return rows


def stability_table(pool: pd.DataFrame, ratings: tuple[str, ...] = ("S", "A")) -> list[str]:
    rows = [
        "| 季度 | 评级 | n | 20日hit10 | 20日hit20 | 平均20日最大涨幅 | 平均20日最大回撤 |",
        "|---|---|--:|--:|--:|--:|--:|",
    ]
    for quarter in sorted(pool["quarter"].dropna().unique()):
        q = pool[pool["quarter"] == quarter]
        for rating in ratings:
            m = subset_metrics(q[q["rating"] == rating])
            rows.append(
                f"| {quarter} | {rating} | {m['n']} | {pct(m['hit10'])} | "
                f"{pct(m['hit20'])} | {pct(m['avg_max20'])} | {pct(m['avg_dd20'])} |"
            )
    return rows


def factor_bucket_table(pool: pd.DataFrame, col: str) -> list[str]:
    rows = [
        f"| {col}分档 | n | 5日hit10 | 10日hit10 | 20日hit10 | 20日hit20 | 平均20日最大涨幅 | 平均20日最大回撤 |",
        "|---|--:|--:|--:|--:|--:|--:|--:|",
    ]
    for score in range(1, 6):
        m = subset_metrics(pool[pool[col] == score])
        rows.append(
            f"| {score} | {m['n']} | {pct(m['hit10_5'])} | {pct(m['hit10_10'])} | "
            f"{pct(m['hit10'])} | {pct(m['hit20'])} | {pct(m['avg_max20'])} | "
            f"{pct(m['avg_dd20'])} |"
        )
    return rows


def write_report(pool: pd.DataFrame, meta: dict[str, str], args: argparse.Namespace) -> Path:
    args.out.mkdir(parents=True, exist_ok=True)
    run_id = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    csv_path = args.out / f"combo_backtest_{RULE_VERSION}_{run_id}.csv"
    report_path = args.out / f"combo_backtest_{RULE_VERSION}_{run_id}.md"
    pool.to_csv(csv_path, index=False)

    lines: list[str] = []
    lines.append(f"# A-share latest rating combo backtest {RULE_VERSION}\n")
    lines.append("## 样本与口径\n")
    lines.append(f"- 数据仓: `{store.STORE}`")
    lines.append(f"- 全仓最新日: {meta['data_max']}；按北京时间应有最新完整交易日: {meta['target_latest']}")
    lines.append(f"- 样本区间: {meta['sample_start']} ~ {meta['sample_end']}")
    lines.append(f"- 样本数量: {len(pool)} 条 stock-anchor；锚点间隔 step={args.step} 个交易日")
    lines.append("- 默认 universe: 排除 bj* 与 sh688*；标签使用锚点后最高价，不用未来数据算特征。")
    lines.append("- R7: 每个锚点先截断到当日再调用 `r7.score_r7()`。")
    lines.append("- R1R3: 每个历史日只用当日及以前 20 日涨幅做 AI 白名单横截面 rank；但 AI 白名单是当前快照，历史结果是上界版本。")
    lines.append("- hit10 = 未来20个交易日内最高价较锚点收盘 >=10%；hit20 = >=20%。\n")

    lines.append("## 当前组合分档规则\n")
    lines.append(f"- 版本: `{RULE_VERSION}`")
    lines.append(f"- S: R7>={S_MIN_R7} 且 R1R3>={S_MIN_R1R3} 且 R7+R1R3>={S_MIN_TOTAL}")
    lines.append(
        f"- A: R1R3>={A_MIN_R1R3} 且 R7+R1R3>={A_MIN_TOTAL} "
        f"且至少一个核心因子>={B_CORE_MIN}"
    )
    lines.append(f"- B: R7>={B_CORE_MIN} 或 R1R3>={B_CORE_MIN}")
    lines.append("- D: R1R3<=2 且 R7<=2" + ("；并强制过滤 R1R3=2" if FILTER_R1R3_2_TO_D else ""))
    lines.append("- C: 其他证据不足样本\n")

    lines.append("## 组合评级表现\n")
    lines.extend(rating_table(pool))
    lines.append("")
    lines.append("## 必比 baseline\n")
    lines.extend(baseline_table(pool, args.random_n, args.seed))
    lines.append("")
    lines.append("## 单因子分档: R7\n")
    lines.extend(factor_bucket_table(pool, "r7"))
    lines.append("")
    lines.append("## 单因子分档: R1R3\n")
    lines.extend(factor_bucket_table(pool, "r1r3"))
    lines.append("")
    lines.append("## 分季度稳定性: S/A\n")
    lines.extend(stability_table(pool))
    lines.append("")
    counts = pool["rating"].value_counts().reindex(["S", "A", "B", "C", "D"], fill_value=0)
    lines.append("## 样本数防幻觉\n")
    lines.append(", ".join(f"{k}={int(v)}" for k, v in counts.items()))
    lines.append("")
    lines.append("## 输出文件\n")
    lines.append(f"- 明细: `{csv_path}`")
    lines.append(f"- 报告: `{report_path}`")
    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return report_path


def run_backtest(args: argparse.Namespace) -> None:
    pool, meta = build_pool(args)
    if len(pool) == 0:
        raise SystemExit("回测后无有效样本。")
    report = write_report(pool, meta, args)
    print(report.read_text(encoding="utf-8"))


def run_latest(args: argparse.Namespace) -> None:
    frames = load_frames(args.limit, args.include_bj688)
    if not frames:
        raise SystemExit(f"N/A: 本地仓为空或可用数据不足: {store.STORE}")
    data_max = store_data_max(frames)
    target = latest_complete_trade_date()
    if data_max is None:
        raise SystemExit("N/A: 本地仓无最新日期")
    if data_max < target and not args.allow_stale:
        raise SystemExit(
            f"N/A: 行情仓过旧，全仓最新日 {data_max}，最近完整交易日应为 {target}。先跑 r0-data update。"
        )

    names = load_name_map()
    target_syms: set[str] | None = None
    unresolved: list[str] = []
    if args.tickers:
        _, n2c = r7._name_map()
        target_syms = set()
        for token in args.tickers:
            sym = r7.resolve(token, n2c)
            if sym:
                target_syms.add(sym)
            else:
                unresolved.append(token)
    needed_dates = {data_max}
    r1_context = build_r1r3_context(frames, needed_dates)
    whitelist = r1r3.load_whitelist()
    rows = []
    for sym, frame in frames.items():
        if target_syms is not None and sym not in target_syms:
            continue
        if frame["date"][-1] != data_max:
            continue
        anchor = len(frame["date"]) - 1
        hist = frame_slice(frame, anchor)
        r7_score, r7_desc, _ = r7.score_r7(hist)
        r1_score, rank, ret20, cohort_n = r1r3_score_for(sym, data_max, r1_context, whitelist)
        rating, reason = rate_combo(r7_score, r1_score)
        if rating == "N/A":
            continue
        rows.append(
            {
                "rating": rating,
                "code": sym,
                "name": names.get(sym, ""),
                "r7": r7_score,
                "r1r3": r1_score,
                "rank": rank,
                "ret20": ret20,
                "cohort_n": cohort_n,
                "reason": reason,
                "r7_desc": r7_desc,
            }
        )
    order = {"S": 0, "A": 1, "B": 2, "C": 3, "D": 4}
    rows.sort(key=lambda x: (order[x["rating"]], -x["r1r3"], -x["r7"], x["code"]))
    if args.min_rating and target_syms is None:
        max_order = order[args.min_rating]
        rows = [r for r in rows if order[r["rating"]] <= max_order]
    if target_syms is None:
        rows = rows[: args.top]
    print(f"# A股最近完整交易日观察评级（{data_max}，规则 {RULE_VERSION}）")
    if AI_WHITELIST_FORWARD_LOOKING:
        print("# 注意：R1R3 使用当前 AI 白名单，历史回测为上界版本；不下单、不荐股。")
    print("rating,code,name,r7,r1r3,rank,ret20,cohort_n,reason")
    for token in unresolved:
        print(f"N/A,{token},名称无法唯一解析,,,,,,请给6位代码")
    if target_syms is not None:
        found = {r["code"] for r in rows}
        for sym in sorted(target_syms - found):
            print(f"N/A,{sym},{names.get(sym, '')},,,,,,无最近完整交易日数据或不在覆盖口径")
    for r in rows:
        rank = "" if r["rank"] is None else f"{r['rank']:.3f}"
        ret20 = "" if r["ret20"] is None else f"{r['ret20']:.4f}"
        print(
            f"{r['rating']},{r['code']},{r['name']},{r['r7']},{r['r1r3']},"
            f"{rank},{ret20},{r['cohort_n']},{r['reason']}"
        )


def parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)

    b = sub.add_parser("backtest", help="run historical combo backtest")
    b.add_argument("--limit", type=int, default=0, help="only first N symbols, 0=all")
    b.add_argument("--step", type=int, default=DEFAULT_STEP, help="anchor spacing in trading bars")
    b.add_argument("--start", default=None, help="inclusive anchor start date YYYY-MM-DD")
    b.add_argument("--end", default=None, help="inclusive anchor end date YYYY-MM-DD")
    b.add_argument("--include-bj688", action="store_true", help="include bj* and sh688*")
    b.add_argument("--random-n", type=int, default=DEFAULT_RANDOM_N)
    b.add_argument("--seed", type=int, default=42)
    b.add_argument("--out", type=Path, default=DEFAULT_OUT)
    b.set_defaults(func=run_backtest)

    l = sub.add_parser("latest", help="rate latest complete trading day")
    l.add_argument("--limit", type=int, default=0, help="only first N symbols, 0=all")
    l.add_argument("--include-bj688", action="store_true", help="include bj* and sh688*")
    l.add_argument("--allow-stale", action="store_true", help="allow stale local store")
    l.add_argument("--min-rating", choices=["S", "A", "B", "C", "D"], default="A")
    l.add_argument("--top", type=int, default=200)
    l.add_argument("tickers", nargs="*", help="optional names/codes to rate; no min-rating filter")
    l.set_defaults(func=run_latest)
    return ap.parse_args()


def main() -> None:
    args = parse_args()
    random.seed(getattr(args, "seed", 42))
    args.func(args)


if __name__ == "__main__":
    main()
