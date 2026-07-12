"""R1 动态主线强度：申万一级行业 5/20 日强度门 + 行业内个股 20 日排名。

行业先按 0.4×5日排名 + 0.6×20日排名选出动态主线；再在主线行业内给个股分档。
R1 是状态排序，不是买点。真正的时机仍看 R0/R9。
"""
from __future__ import annotations

import argparse
import bisect
import datetime as dt
import os
import sys
from pathlib import Path

import pandas as pd

import store
from r0 import _name_map, resolve


RET5_N = 5
RET20_N = 20
RET_N = RET20_N  # 兼容既有消费者
SECTOR_HEAT_CUT = 0.85
SECTOR_P20_MIN = 0.60
SECTOR_P5_MIN = 0.50
SECTOR_RET20_MIN = 0.0
MIN_SECTOR_MEMBERS = 20
MIN_VALID_SECTORS = 25
TIER_CUTS = ((0.93, 5), (0.66, 4), (0.33, 3), (-1.0, 2))
COHORT_EXCLUDES = ("bj", "sh688")
CACHE_MAX_AGE_DAYS = 7

INDUSTRY_HISTORY_CACHE = Path(store.STORE) / "sw_industry_history.csv"
SECTOR_CLOSE_CACHE = Path(store.STORE) / "sw1_sector_close.parquet"

# 申万 2021 一级行业：分类代码前两位 → (行业名, 指数代码)。
SW1 = {
    "11": ("农林牧渔", "801010"), "22": ("基础化工", "801030"),
    "23": ("钢铁", "801040"), "24": ("有色金属", "801050"),
    "27": ("电子", "801080"), "28": ("汽车", "801880"),
    "33": ("家用电器", "801110"), "34": ("食品饮料", "801120"),
    "35": ("纺织服饰", "801130"), "36": ("轻工制造", "801140"),
    "37": ("医药生物", "801150"), "41": ("公用事业", "801160"),
    "42": ("交通运输", "801170"), "43": ("房地产", "801180"),
    "45": ("商贸零售", "801200"), "46": ("社会服务", "801210"),
    "48": ("银行", "801780"), "49": ("非银金融", "801790"),
    "51": ("综合", "801230"), "61": ("建筑材料", "801710"),
    "62": ("建筑装饰", "801720"), "63": ("电力设备", "801730"),
    "64": ("机械设备", "801890"), "65": ("国防军工", "801740"),
    "71": ("计算机", "801750"), "72": ("传媒", "801760"),
    "73": ("通信", "801770"), "74": ("煤炭", "801950"),
    "75": ("石油石化", "801960"), "76": ("环保", "801970"),
    "77": ("美容护理", "801980"),
}


def tier_from_rank(rank: float) -> int:
    for cut, tier in TIER_CUTS:
        if rank >= cut:
            return tier
    return 2


def rank_of(value: float, values: list[float]) -> float:
    """平均名次百分位；并列值共享同一档。"""
    if not values:
        return 0.0
    ordered = sorted(values)
    left = bisect.bisect_left(ordered, value)
    right = bisect.bisect_right(ordered, value)
    return ((left + 1) + right) / 2 / len(ordered)


def _cache_old(path: Path) -> bool:
    if not path.exists():
        return True
    age = dt.datetime.now().timestamp() - path.stat().st_mtime
    return age > CACHE_MAX_AGE_DAYS * 86400


def refresh_reference_data() -> None:
    """原子刷新申万行业分类历史和 31 个一级行业指数日线。"""
    try:
        import akshare as ak
    except ImportError as exc:
        raise RuntimeError("缺 akshare，先按 r0-data 的依赖安装流程补齐") from exc

    Path(store.STORE).mkdir(parents=True, exist_ok=True)
    print("  刷新申万行业分类历史…", file=sys.stderr)
    history = ak.stock_industry_clf_hist_sw().copy()
    required = {"symbol", "start_date", "industry_code", "update_time"}
    if len(history) < 10000 or not required.issubset(history.columns):
        raise RuntimeError("申万行业分类历史返回不完整，保留旧缓存")
    history["symbol"] = history["symbol"].astype(str).str.zfill(6)
    history["start_date"] = history["start_date"].astype(str).str[:10]
    history["industry_code"] = history["industry_code"].astype(str).str.zfill(6)
    history["source_snapshot_date"] = dt.date.today().isoformat()

    closes = {}
    for i, (sector, (name, index_code)) in enumerate(SW1.items(), 1):
        print(f"  行业指数 {i:02d}/{len(SW1)} {name}", file=sys.stderr)
        frame = ak.index_hist_sw(index_code, period="day")
        if frame is None or len(frame) < RET20_N + 1 or not {"日期", "收盘"}.issubset(frame.columns):
            raise RuntimeError(f"申万行业指数 {name}({index_code}) 返回不完整，保留旧缓存")
        dates = frame["日期"].astype(str).str[:10]
        closes[sector] = pd.Series(frame["收盘"].astype(float).to_numpy(), index=dates)
    sector_close = pd.DataFrame(closes).sort_index()
    if sector_close.shape[1] != len(SW1):
        raise RuntimeError("申万一级行业指数缺列，保留旧缓存")

    history_tmp = INDUSTRY_HISTORY_CACHE.with_suffix(".csv.tmp")
    sector_tmp = SECTOR_CLOSE_CACHE.with_suffix(".parquet.tmp")
    history.to_csv(history_tmp, index=False)
    sector_close.to_parquet(sector_tmp)
    os.replace(history_tmp, INDUSTRY_HISTORY_CACHE)
    os.replace(sector_tmp, SECTOR_CLOSE_CACHE)


def load_reference_data(
    target_date: str | None = None,
    force_refresh: bool = False,
) -> tuple[pd.DataFrame, dict[str, tuple[list[str], list[str]]]]:
    need_refresh = force_refresh or _cache_old(INDUSTRY_HISTORY_CACHE) or _cache_old(SECTOR_CLOSE_CACHE)
    if not need_refresh and target_date:
        try:
            cached = pd.read_parquet(SECTOR_CLOSE_CACHE)
            latest = str(cached.index.max())[:10]
            # 数据源偶尔慢一天；6 小时内不重复轰接口，仍缺目标日时由调用方返回 N/A。
            age_hours = (dt.datetime.now().timestamp() - SECTOR_CLOSE_CACHE.stat().st_mtime) / 3600
            need_refresh = latest < target_date and age_hours >= 6
        except Exception:
            need_refresh = True
    if need_refresh:
        try:
            refresh_reference_data()
        except Exception as exc:
            if not (INDUSTRY_HISTORY_CACHE.exists() and SECTOR_CLOSE_CACHE.exists()):
                raise RuntimeError(f"申万行业数据初始化失败：{exc}") from exc
            print(f"⚠ 申万行业数据刷新失败，继续使用旧缓存：{exc}", file=sys.stderr)

    sector_close = pd.read_parquet(SECTOR_CLOSE_CACHE)
    sector_close.index = sector_close.index.astype(str).str[:10]
    raw = pd.read_csv(INDUSTRY_HISTORY_CACHE, dtype={"symbol": str, "industry_code": str})
    raw["symbol"] = raw["symbol"].str.zfill(6)
    raw["industry_code"] = raw["industry_code"].str.zfill(6)
    raw["start_date"] = raw["start_date"].astype(str).str[:10]
    history = {}
    for code, rows in raw.sort_values(["symbol", "start_date"]).groupby("symbol"):
        rows = rows.drop_duplicates("start_date", keep="last")
        history[code] = (rows["start_date"].tolist(), rows["industry_code"].str[:2].tolist())
    return sector_close, history


def industry_at(
    code: str,
    date: str,
    history: dict[str, tuple[list[str], list[str]]],
) -> str | None:
    rows = history.get(code)
    if not rows:
        return None
    starts, sectors = rows
    idx = bisect.bisect_right(starts, date) - 1
    return sectors[idx] if idx >= 0 and sectors[idx] in SW1 else None


def _sector_state(
    sector_close: pd.DataFrame,
    date: str,
    counts: dict[str, int],
) -> dict[str, dict] | None:
    if date not in sector_close.index:
        return None
    pos = sector_close.index.get_loc(date)
    if isinstance(pos, (slice, list)):
        return None
    pos = int(pos)
    if pos < RET20_N:
        return None
    r5 = sector_close.iloc[pos] / sector_close.iloc[pos - RET5_N] - 1
    r20 = sector_close.iloc[pos] / sector_close.iloc[pos - RET20_N] - 1
    valid = [s for s in SW1 if counts.get(s, 0) >= MIN_SECTOR_MEMBERS and pd.notna(r5.get(s)) and pd.notna(r20.get(s))]
    if len(valid) < MIN_VALID_SECTORS:
        return None
    p5 = {s: rank_of(float(r5[s]), [float(r5[x]) for x in valid]) for s in valid}
    p20 = {s: rank_of(float(r20[s]), [float(r20[x]) for x in valid]) for s in valid}
    heat = {s: 0.4 * p5[s] + 0.6 * p20[s] for s in valid}
    pheat = {s: rank_of(heat[s], list(heat.values())) for s in valid}
    return {
        s: {
            "sector_code": s,
            "sector_name": SW1[s][0],
            "sector_ret5": float(r5[s]),
            "sector_ret20": float(r20[s]),
            "sector_p5": p5[s],
            "sector_p20": p20[s],
            "sector_rank": pheat[s],
            "sector_n": counts[s],
            "mainline": (
                pheat[s] >= SECTOR_HEAT_CUT
                and p20[s] >= SECTOR_P20_MIN
                and p5[s] >= SECTOR_P5_MIN
                and float(r20[s]) > SECTOR_RET20_MIN
            ),
        }
        for s in valid
    }


def build_context(
    frames: dict[str, dict[str, list]],
    needed_dates: set[str],
    force_refresh: bool = False,
) -> tuple[dict[str, dict[str, dict]], dict[str, dict[str, dict]]]:
    """按历史日构建 R1；行业指数、行业归属和个股收益都只使用当日及以前数据。"""
    target = max(needed_dates) if needed_dates else None
    sector_close, history = load_reference_data(target, force_refresh)
    frame_indexes = {sym: {str(d): i for i, d in enumerate(frame["date"])} for sym, frame in frames.items()}
    sector_dates = list(sector_close.index)
    sector_pos = {d: i for i, d in enumerate(sector_dates)}
    contexts = {}
    states_by_date = {}

    for date in sorted(needed_dates):
        pos = sector_pos.get(date)
        if pos is None or pos < RET20_N:
            continue
        base_date = sector_dates[pos - RET20_N]
        grouped: dict[str, list[tuple[str, float]]] = {}
        for sym, frame in frames.items():
            if sym.startswith(COHORT_EXCLUDES):
                continue
            idx = frame_indexes[sym].get(date)
            base_idx = frame_indexes[sym].get(base_date)
            if idx is None or base_idx is None:
                continue
            base = float(frame["close"][base_idx])
            if not base:
                continue
            sector = industry_at(sym[2:], date, history)
            if sector:
                grouped.setdefault(sector, []).append((sym, float(frame["close"][idx]) / base - 1))
        counts = {sector: len(rows) for sector, rows in grouped.items()}
        states = _sector_state(sector_close, date, counts)
        if states is None:
            continue
        daily = {}
        for sector, rows in grouped.items():
            state = states.get(sector)
            if state is None:
                continue
            values = [ret for _, ret in rows]
            for sym, ret20 in rows:
                stock_rank = rank_of(ret20, values) if state["mainline"] else None
                daily[sym] = {
                    **state,
                    "score": tier_from_rank(stock_rank) if stock_rank is not None else 1,
                    "stock_rank": stock_rank,
                    "stock_ret20": ret20,
                }
        contexts[date] = daily
        states_by_date[date] = states
    return contexts, states_by_date


def _load_frames() -> tuple[dict[str, dict[str, list]], str | None]:
    frames = {}
    for sym in store.list_symbols():
        if sym.startswith(COHORT_EXCLUDES):
            continue
        frame = store.load_frame(sym)
        if frame and len(frame["date"]) >= RET20_N + 1:
            frames[sym] = frame
    latest = max((str(frame["date"][-1]) for frame in frames.values()), default=None)
    return frames, latest


def describe(sym: str, record: dict | None, name: str) -> tuple[int | None, str]:
    if sym.startswith(COHORT_EXCLUDES):
        return None, f"✗ {sym} {name}：北交所/科创板688 不在 R1 回测口径内，不打分"
    if record is None:
        return None, f"✗ {sym} {name}：行业归属、当日行情或20日前同日行情缺失，不打分"
    score = record["score"]
    sector = record["sector_name"]
    sector_ev = (
        f"{sector}行业5日{record['sector_ret5']*100:+.1f}%、20日{record['sector_ret20']*100:+.1f}%、"
        f"综合rank {record['sector_rank']:.2f}"
    )
    if score == 1:
        return 1, f"R1=1  {sym} {name}  {sector_ev}，未进入动态主线"
    labels = {5: "行业龙头层", 4: "行业内偏强", 3: "行业内中游", 2: "主线行业掉队者"}
    return score, (
        f"R1={score}  {sym} {name}  {sector_ev}；个股20日{record['stock_ret20']*100:+.1f}%、"
        f"行业内rank {record['stock_rank']:.2f} {labels[score]}｜行业{record['sector_n']}只有效成员"
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("tickers", nargs="*", help="名称或代码，可多只")
    parser.add_argument("--today", action="store_true", help="列出动态主线前排")
    parser.add_argument("--min", type=int, default=5, help="--today 的分数门槛，默认5")
    parser.add_argument("--refresh-industries", action="store_true", help="强制刷新申万行业参考数据")
    args = parser.parse_args()
    if not args.tickers and not args.today and not args.refresh_industries:
        selftest()
        return
    if args.refresh_industries:
        refresh_reference_data()
        if not args.tickers and not args.today:
            print(f"申万行业数据已刷新：{SECTOR_CLOSE_CACHE}")
            return

    frames, latest = _load_frames()
    if not frames or latest is None:
        raise SystemExit(f"本地仓为空（{store.STORE}）。先走 r0-data 建仓")
    context, states = build_context(frames, {latest})
    if latest not in context:
        sector_last = "-"
        if SECTOR_CLOSE_CACHE.exists():
            sector_last = str(pd.read_parquet(SECTOR_CLOSE_CACHE).index.max())[:10]
        raise SystemExit(f"N/A：申万行业数据或横截面不足以计算 {latest}（行业数据截至 {sector_last}）")
    daily = context[latest]
    names, n2c = _name_map()

    if args.today:
        mainlines = sorted(
            (row for row in states[latest].values() if row["mainline"]),
            key=lambda row: -row["sector_rank"],
        )
        print(f"# 动态主线行业（{latest}）")
        for row in mainlines:
            print(
                f"# {row['sector_name']} rank={row['sector_rank']:.2f} "
                f"5日{row['sector_ret5']*100:+.1f}% 20日{row['sector_ret20']*100:+.1f}%"
            )
        rows = []
        for sym, record in daily.items():
            if record["score"] >= args.min:
                rows.append((record["score"], record.get("stock_rank") or 0, sym, names.get(sym, ""), record))
        rows.sort(key=lambda row: (-row[0], -row[1], row[2]))
        print(f"# R1≥{args.min} 前排（共 {len(rows)} 只；状态排序不是买点）")
        for _, _, sym, name, record in rows:
            print(describe(sym, record, name)[1])
        return

    for token in args.tickers:
        sym = resolve(token, n2c)
        if not sym:
            print(f"✗ {token}：名称无法唯一解析，请给6位代码")
            continue
        print(describe(sym, daily.get(sym), names.get(sym, ""))[1])


def selftest() -> None:
    assert tier_from_rank(0.93) == 5 and tier_from_rank(0.80) == 4
    assert tier_from_rank(0.50) == 3 and tier_from_rank(0.10) == 2
    assert rank_of(0.0, [0.0, 0.0, 1.0]) == 0.5
    history = {"000001": (["2020-01-01", "2021-07-30"], ["21", "48"])}
    assert industry_at("000001", "2021-01-01", history) is None  # 旧21已退出现行31行业口径
    assert industry_at("000001", "2022-01-01", history) == "48"
    print("r1 自检通过 ✓  动态主线=申万一级行业5/20日强度 + 行业内20日排名")


if __name__ == "__main__":
    main()
