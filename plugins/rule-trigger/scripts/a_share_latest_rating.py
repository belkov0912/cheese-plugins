#!/usr/bin/env python3
"""Backtest and apply the A-share latest observation rating.

The script intentionally reuses the rule-trigger plugin implementation:
- R7 comes from r7.score_r7 on a frame truncated at anchor date.
- R1 is rebuilt cross-sectionally for each historical anchor date with the
  current AI whitelist. That makes the historical result an upper-bound version
  because the whitelist itself is a current snapshot.

Default universe excludes bj* and sh688*, matching r7/r1 plugin defaults.
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

import r1  # noqa: E402
import r7  # noqa: E402
import store  # noqa: E402


OUTCOME_WINDOWS = (5, 10, 20)
DEFAULT_STEP = 10
DEFAULT_RANDOM_N = 10000
DEFAULT_OUT = DEFAULT_RULE_SCRIPTS.parent / "out" / "a-share-latest-rating"
UNIVERSE_EXCLUDES = ("bj", "sh688")
AI_WHITELIST_FORWARD_LOOKING = True
# latest 模式的仓覆盖率下限:追平当日 K 线的票占比低于此值 → 拒绝评级(半更新会静默坍缩,见 #1)。
MIN_FRESH_COVERAGE = 0.95


# Iteration rule block. Change only one small rule unit per optimization round.
RULE_VERSION = "v2_a_requires_r1_4"
S_MIN_R7 = 4
S_MIN_R1 = 5
S_MIN_TOTAL = 9
A_MIN_R1 = 4
A_MIN_TOTAL = 8
B_CORE_MIN = 4
FILTER_R1_2_TO_D = False


def is_excluded(sym: str) -> bool:
    return sym.startswith(UNIVERSE_EXCLUDES)


def pct(x: float | None) -> str:
    if x is None or (isinstance(x, float) and math.isnan(x)):
        return "-"
    return f"{x * 100:.1f}%"


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


def load_frames(limit: int = 0) -> dict[str, dict[str, list]]:
    # bj*/sh688* 一律不评级也不进 cohort（涨跌幅制度不同、不在回测口径）——不做开关（见 #3）。
    syms = [s for s in sorted(store.list_symbols()) if not is_excluded(s)]
    if limit:
        syms = syms[:limit]
    # 门槛对齐 r1 定版:只要够算 20 日涨幅即入 cohort（RET_N+1 根）。
    # 历史不足 50 根的票 R7 会自然返回“数据不足”→评级 N/A，但仍参与 R1 板块排名（见 #9）。
    min_bars = r1.RET_N + 1
    frames: dict[str, dict[str, list]] = {}
    for i, sym in enumerate(syms):
        if i % 500 == 0:
            print(f"  load {i}/{len(syms)}", file=sys.stderr)
        frame = store.load_frame(sym)
        if frame and len(frame["date"]) >= min_bars:
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
    # hit10/hit20 用“最高收盘价”口径,与 r7/r9/r1 定版一致(features.outcome_return 也用 close);
    # 之前用 frame["high"](盘中最高价)导致同名 hit10 系统性偏高、跨 skill 不可比(见 #2)。
    close0 = float(frame["close"][anchor_idx])
    if not close0 or anchor_idx + max(OUTCOME_WINDOWS) >= len(frame["close"]):
        return None
    out: dict[str, float] = {}
    for n in OUTCOME_WINDOWS:
        closes = frame["close"][anchor_idx + 1 : anchor_idx + 1 + n]
        out[f"max_ret_{n}"] = max(float(x) for x in closes) / close0 - 1
    # downside 仍用盘中最低价(持有者真实见到的最深处),但它是“相对入场价的最低点”,
    # 不是峰谷式最大回撤——报告标签已相应改名(见 #11)。
    lows20 = frame["low"][anchor_idx + 1 : anchor_idx + 21]
    out["min_ret_vs_entry_20"] = min(float(x) for x in lows20) / close0 - 1

    pre_hit_low = float("inf")
    hit10_seen = False
    for close, low in zip(
        frame["close"][anchor_idx + 1 : anchor_idx + 21],
        frame["low"][anchor_idx + 1 : anchor_idx + 21],
    ):
        pre_hit_low = min(pre_hit_low, float(low))
        if float(close) / close0 - 1 >= 0.10:
            hit10_seen = True
            break
    if not hit10_seen:
        pre_hit_low = min(float(x) for x in lows20)
    out["min_ret_before_hit10"] = pre_hit_low / close0 - 1
    return out


def build_anchor_rows(
    frames: dict[str, dict[str, list]],
    step: int,
    sample_start: str | None,
    sample_end: str | None,
) -> tuple[list[dict], set[str]]:
    rows: list[dict] = []
    needed_dates: set[str] = set()
    min_anchor = max(r7.MIN_BARS - 1, r1.RET_N)
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


def build_r1_context(
    frames: dict[str, dict[str, list]],
    needed_dates: set[str],
) -> dict[str, dict[str, tuple[float, float, int]]]:
    whitelist = r1.load_whitelist()
    index_by_sym = {sym: date_index(frame) for sym, frame in frames.items()}
    by_date: dict[str, list[tuple[str, float]]] = defaultdict(list)
    for sym, frame in frames.items():
        if is_excluded(sym) or sym[2:] not in whitelist:
            continue
        idx_map = index_by_sym[sym]
        close = frame["close"]
        for d in needed_dates:
            idx = idx_map.get(d)
            if idx is None or idx < r1.RET_N:
                continue
            base = float(close[idx - r1.RET_N])
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


def r1_score_for(
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
    return r1.tier_from_rank(rank), rank, ret20, cohort_n


def rate_combo(r7_score: int | None, r1_score: int | None) -> tuple[str, str]:
    if r7_score is None or r1_score is None:
        return "N/A", "数据不足"
    total = r7_score + r1_score
    if FILTER_R1_2_TO_D and r1_score == 2:
        return "D", "R1=2 主线掉队过滤"
    if r7_score >= S_MIN_R7 and r1_score >= S_MIN_R1 and total >= S_MIN_TOTAL:
        return "S", f"R7>={S_MIN_R7} 且 R1>={S_MIN_R1} 且总分>={S_MIN_TOTAL}"
    if (
        r1_score >= A_MIN_R1
        and total >= A_MIN_TOTAL
        and (r7_score >= B_CORE_MIN or r1_score >= B_CORE_MIN)
    ):
        return "A", f"R1>={A_MIN_R1} 且总分>={A_MIN_TOTAL} 且至少一个核心因子>={B_CORE_MIN}"
    if r7_score >= B_CORE_MIN or r1_score >= B_CORE_MIN:
        return "B", f"至少一个核心因子>={B_CORE_MIN}"
    if r1_score <= 2 and r7_score <= 2:
        return "D", "主线或形态都弱"
    return "C", "证据不足"


def build_pool(args: argparse.Namespace) -> tuple[pd.DataFrame, dict[str, str]]:
    frames = load_frames(args.limit)
    if not frames:
        raise SystemExit(f"本地仓为空或可用数据不足: {store.STORE}")
    rows, needed_dates = build_anchor_rows(frames, args.step, args.start, args.end)
    if not rows:
        raise SystemExit("无可用回测样本：检查日期区间、step 或数据长度。")
    print(f"  anchors {len(rows)}; r1 dates {len(needed_dates)}", file=sys.stderr)
    r1_context = build_r1_context(frames, needed_dates)
    whitelist = r1.load_whitelist()
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
        r1_score, rank, ret20, cohort_n = r1_score_for(
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
                "r1": int(r1_score),
                "r1_rank": rank,
                "r1_ret20": ret20,
                "r1_cohort_n": cohort_n,
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
            "avg_low20": math.nan,
            "avg_pre_hit10_low": math.nan,
        }
    return {
        "n": int(len(df)),
        "hit10_5": float((df["max_ret_5"] >= 0.10).mean()),
        "hit10_10": float((df["max_ret_10"] >= 0.10).mean()),
        "hit10": float(df["hit10"].mean()),
        "hit20": float(df["hit20"].mean()),
        "avg_max20": float(df["max_ret_20"].mean()),
        "avg_low20": float(df["min_ret_vs_entry_20"].mean()),
        "avg_pre_hit10_low": float(df["min_ret_before_hit10"].mean()),
    }


def metric_row(label: str, df: pd.DataFrame) -> str:
    m = subset_metrics(df)
    return (
        f"| {label} | {m['n']} | {pct(m['hit10_5'])} | {pct(m['hit10_10'])} | "
        f"{pct(m['hit10'])} | {pct(m['hit20'])} | {pct(m['avg_max20'])} | "
        f"{pct(m['avg_low20'])} | {pct(m['avg_pre_hit10_low'])} |"
    )


def selected_baselines(pool: pd.DataFrame, random_n: int, seed: int) -> list[tuple[str, pd.DataFrame, str]]:
    n = min(random_n, len(pool))
    random_df = pool.sample(n=n, random_state=seed) if n < len(pool) else pool.copy()
    return [
        (f"全市场随机样本(seed={seed}, n={n})", random_df, "从全样本确定性抽样"),
        ("R7 单因子: R7>=4", pool[pool["r7"] >= 4], "只看试盘回踩形态"),
        ("R1 单因子: R1>=4", pool[pool["r1"] >= 4], "只看主线内相对强度"),
        (
            "简单交集: R7>=4 且 R1>=4",
            pool[(pool["r7"] >= 4) & (pool["r1"] >= 4)],
            "两个因子硬交集",
        ),
        ("R1=5 单独前排", pool[pool["r1"] == 5], "主线前7%"),
    ]


def rating_table(pool: pd.DataFrame) -> list[str]:
    rows = [
        "| 评级 | n | 5日hit10 | 10日hit10 | 20日hit10 | 20日hit20 | 平均20日最大涨幅 | 平均20日最低(相对入场) | 平均hit10前最低 |",
        "|---|--:|--:|--:|--:|--:|--:|--:|--:|",
    ]
    order = ["S", "A", "B", "C", "D"]
    for rating in order:
        rows.append(metric_row(rating, pool[pool["rating"] == rating]))
    return rows


def baseline_table(pool: pd.DataFrame, random_n: int, seed: int) -> list[str]:
    rows = [
        "| baseline | n | 5日hit10 | 10日hit10 | 20日hit10 | 20日hit20 | 平均20日最大涨幅 | 平均20日最低(相对入场) | 平均hit10前最低 |",
        "|---|--:|--:|--:|--:|--:|--:|--:|--:|",
    ]
    for label, df, _ in selected_baselines(pool, random_n, seed):
        rows.append(metric_row(label, df))
    return rows


def stability_table(pool: pd.DataFrame, ratings: tuple[str, ...] = ("S", "A")) -> list[str]:
    rows = [
        "| 季度 | 评级 | n | 20日hit10 | 20日hit20 | 平均20日最大涨幅 | 平均20日最低(相对入场) |",
        "|---|---|--:|--:|--:|--:|--:|",
    ]
    for quarter in sorted(pool["quarter"].dropna().unique()):
        q = pool[pool["quarter"] == quarter]
        for rating in ratings:
            m = subset_metrics(q[q["rating"] == rating])
            rows.append(
                f"| {quarter} | {rating} | {m['n']} | {pct(m['hit10'])} | "
                f"{pct(m['hit20'])} | {pct(m['avg_max20'])} | {pct(m['avg_low20'])} |"
            )
    return rows


def factor_bucket_table(pool: pd.DataFrame, col: str) -> list[str]:
    rows = [
        f"| {col}分档 | n | 5日hit10 | 10日hit10 | 20日hit10 | 20日hit20 | 平均20日最大涨幅 | 平均20日最低(相对入场) |",
        "|---|--:|--:|--:|--:|--:|--:|--:|",
    ]
    for score in range(1, 6):
        m = subset_metrics(pool[pool[col] == score])
        rows.append(
            f"| {score} | {m['n']} | {pct(m['hit10_5'])} | {pct(m['hit10_10'])} | "
            f"{pct(m['hit10'])} | {pct(m['hit20'])} | {pct(m['avg_max20'])} | "
            f"{pct(m['avg_low20'])} |"
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
    lines.append(f"- 样本数量: {len(pool)} 条 stock-anchor；锚点间隔 step={args.step} 个交易日"
                 f"（step<标签窗20日，同票相邻样本标签窗重叠、且状态跨锚点持续，有效独立样本远小于名义 n）。")
    lines.append("- 默认 universe: 排除 bj* 与 sh688*；用未来收盘价算标签、不用未来数据算特征。")
    lines.append("- R7: 每个锚点先截断到当日再调用 `r7.score_r7()`。")
    lines.append("- R1: 每个历史日只用当日及以前 20 日涨幅做 AI 白名单横截面 rank；但 AI 白名单是当前快照，历史结果是上界版本。")
    lines.append("- hit10 = 未来20个交易日内**最高收盘价**较锚点收盘 >=10%；hit20 = >=20%（收盘口径，与 r7/r9/r1 定版一致、可横比）。")
    lines.append("- 「20日最低(相对入场)」= 未来20日盘中最低价相对锚点收盘的跌幅（是相对入场价的最深处，非峰谷式最大回撤）。")
    lines.append("- universe 取当前在市票的本地仓，样本期内退市/长停票不在池中，基线与各档命中率含幸存者偏差、同向偏高。\n")

    lines.append("## 当前组合分档规则\n")
    lines.append(f"- 版本: `{RULE_VERSION}`")
    lines.append(f"- S: R7>={S_MIN_R7} 且 R1>={S_MIN_R1} 且 R7+R1>={S_MIN_TOTAL}")
    lines.append(
        f"- A: R1>={A_MIN_R1} 且 R7+R1>={A_MIN_TOTAL} "
        f"且至少一个核心因子>={B_CORE_MIN}"
    )
    lines.append(f"- B: R7>={B_CORE_MIN} 或 R1>={B_CORE_MIN}")
    lines.append("- D: R1<=2 且 R7<=2" + ("；并强制过滤 R1=2" if FILTER_R1_2_TO_D else ""))
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
    lines.append("## 单因子分档: R1\n")
    lines.extend(factor_bucket_table(pool, "r1"))
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
    frames = load_frames(args.limit)
    if not frames:
        raise SystemExit(f"N/A: 本地仓为空或可用数据不足: {store.STORE}")
    data_max = store_data_max(frames)
    target = latest_complete_trade_date()
    if data_max is None:
        raise SystemExit("N/A: 本地仓无最新日期")
    if data_max < target and not args.allow_stale:
        # #7: _data_end_date 不识别法定节假日、且 15:05 后就翻到当天(数据源要 16:30 才有),都会误报。
        raise SystemExit(
            f"N/A: 行情仓过旧，全仓最新日 {data_max}，最近完整交易日应为 {target}。先跑 r0-data update。\n"
            f"    （若今天是法定节假日，或刚过 15:05 收盘、当日数据 16:30 后才出，则仓可能并不旧——"
            f"可用 --allow-stale 按 {data_max} 口径出结果。）"
        )

    # #1: 半更新守卫。store update 逐票串行,进行中仓里混着新旧日期,data_max(max 口径)会被
    # 少数已更新票拉到最新日、放行,随后未追平的票在下方被静默丢弃 → cohort 塌缩、rank 全失真
    # (实测坍缩成 S=1/A=1 且零警告)。这里改为按覆盖率把关:追平 data_max 的票占比过低就拒绝。
    fresh = sum(1 for f in frames.values() if f["date"][-1] == data_max)
    coverage = fresh / len(frames)
    if coverage < MIN_FRESH_COVERAGE and not args.allow_stale:
        raise SystemExit(
            f"N/A: 行情仓疑似正在更新(半更新态)——{len(frames)} 只里只有 {fresh} 只"
            f"({coverage*100:.0f}%) 追平最新日 {data_max}，低于 {MIN_FRESH_COVERAGE*100:.0f}% 阈值。\n"
            f"    此时 R1 板块排名会在残缺样本上算、评级失真。等 r0-data update 跑完再查，"
            f"或加 --allow-stale 明确接受残缺样本(结果仅供调试)。"
        )
    if coverage < MIN_FRESH_COVERAGE:
        print(f"# ⚠ 半更新态:仅 {fresh}/{len(frames)} 只({coverage*100:.0f}%)追平 {data_max}，"
              f"评级建立在残缺板块上，仅供调试。", file=sys.stderr)

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
    r1_context = build_r1_context(frames, needed_dates)
    whitelist = r1.load_whitelist()
    rows = []
    for sym, frame in frames.items():
        if target_syms is not None and sym not in target_syms:
            continue
        if frame["date"][-1] != data_max:
            continue
        anchor = len(frame["date"]) - 1
        hist = frame_slice(frame, anchor)
        r7_score, r7_desc, _ = r7.score_r7(hist)
        r1_score, rank, ret20, cohort_n = r1_score_for(sym, data_max, r1_context, whitelist)
        rating, reason = rate_combo(r7_score, r1_score)
        if rating == "N/A":
            continue
        rows.append(
            {
                "rating": rating,
                "code": sym,
                "name": names.get(sym, ""),
                "r7": r7_score,
                "r1": r1_score,
                "rank": rank,
                "ret20": ret20,
                "cohort_n": cohort_n,
                "reason": reason,
                "r7_desc": r7_desc,
            }
        )
    order = {"S": 0, "A": 1, "B": 2, "C": 3, "D": 4}
    rows.sort(key=lambda x: (order[x["rating"]], -x["r1"], -x["r7"], x["code"]))
    if args.min_rating and target_syms is None:
        max_order = order[args.min_rating]
        rows = [r for r in rows if order[r["rating"]] <= max_order]
    if target_syms is None:
        rows = rows[: args.top]
    single = target_syms is not None
    print(f"# A股最近完整交易日观察评级（{data_max}，规则 {RULE_VERSION}）")
    if AI_WHITELIST_FORWARD_LOOKING:
        print("# 注意：R1 使用当前 AI 白名单，历史回测为上界版本；不下单、不荐股。")
    header = "rating,code,name,r7,r1,rank,ret20,cohort_n,reason"
    print(header + (",r7_desc" if single else ""))
    for token in unresolved:
        print(f"N/A,{token},名称无法唯一解析,,,,,,请给6位代码")
    if single:
        found = {r["code"] for r in rows}
        for sym in sorted(target_syms - found):
            # #13: 分因提示,别把三种原因混成一句。
            if is_excluded(sym):
                why = "北交所/科创板688 不在 R1 回测口径,不打分"
            elif sym not in frames:
                why = f"本地仓无数据或历史不足({r1.RET_N + 1}根)——次新/未建仓,跑 r0-data 补"
            else:
                last = frames[sym]["date"][-1]
                why = f"数据止于{last}≠最新日{data_max}(停牌,或本地仓没更新到当日——跑 r0-data 增量)"
            print(f"N/A,{sym},{names.get(sym, '')},,,,,,{why}" + ("," if single else ""))
    for r in rows:
        rank = "" if r["rank"] is None else f"{r['rank']:.3f}"
        ret20 = "" if r["ret20"] is None else f"{r['ret20']:.4f}"
        line = (
            f"{r['rating']},{r['code']},{r['name']},{r['r7']},{r['r1']},"
            f"{rank},{ret20},{r['cohort_n']},{r['reason']}"
        )
        # #12: 单票模式带上 R7 证据化描述(试盘日/量比/回踩缩量比),对齐 r7-trigger 的信息量。
        if single:
            line += "," + (r["r7_desc"] or "").replace(",", "，")
        print(line)


def parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)

    b = sub.add_parser("backtest", help="run historical combo backtest")
    b.add_argument("--limit", type=int, default=0, help="only first N symbols, 0=all")
    b.add_argument("--step", type=int, default=DEFAULT_STEP, help="anchor spacing in trading bars")
    b.add_argument("--start", default=None, help="inclusive anchor start date YYYY-MM-DD")
    b.add_argument("--end", default=None, help="inclusive anchor end date YYYY-MM-DD")
    b.add_argument("--random-n", type=int, default=DEFAULT_RANDOM_N)
    b.add_argument("--seed", type=int, default=42)
    b.add_argument("--out", type=Path, default=DEFAULT_OUT)
    b.set_defaults(func=run_backtest)

    l = sub.add_parser("latest", help="rate latest complete trading day")
    l.add_argument("--limit", type=int, default=0, help="only first N symbols, 0=all")
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


def _selftest() -> None:
    # #4: 纯函数自检,不碰行情仓。rate_combo 的 S/A/B/C/D 边界改档位常量后有护栏。
    cases = {
        (5, 5): "S", (4, 5): "S",          # 试盘确认 + 主线前排 → S
        (3, 5): "A", (5, 3): "B",          # A 需 R1>=4;R7=5/R1=3 总分8但主线未达4 → B
        (4, 4): "A", (4, 3): "B",          # 简单交集 vs 单核心
        (4, 1): "B", (1, 4): "B",          # 单因子达标 → B
        (2, 2): "D", (1, 1): "D",          # 都弱 → D
        (3, 3): "C",                       # 证据不足 → C
    }
    for (r7v, r1v), want in cases.items():
        got, _ = rate_combo(r7v, r1v)
        assert got == want, f"rate_combo(R7={r7v},R1={r1v}) 应={want},实际={got}"
    assert rate_combo(None, 5)[0] == "N/A" and rate_combo(4, None)[0] == "N/A", "缺因子应 N/A"
    # A 档理由必须点出 R1>=4(#10 回归防护)
    assert "R1>=4" in rate_combo(3, 5)[1], "A 档理由应包含 R1>=4"
    # 白名单快照可读、为 6 位代码
    wl = r1.load_whitelist()
    assert len(wl) > 1000 and all(len(c) == 6 for c in wl), "白名单快照应为6位代码"
    print(f"a_share_latest_rating 自检通过 ✓  规则 {RULE_VERSION}，白名单 {len(wl)} 只")


if __name__ == "__main__":
    if len(sys.argv) == 1:
        _selftest()
    else:
        main()
