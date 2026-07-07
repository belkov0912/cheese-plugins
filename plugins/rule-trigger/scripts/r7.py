"""R7 试盘后回踩 · 单票/多票即时查 + 全市场高分名单（新版相对放量口径）。

R7 语义 = "最近20个交易日里，是否出现过相对自身明显放量的试盘K线，
随后最近5日缩量回踩且结构没有明显走坏"。

它是观察信号，不是买点。没有回踩、直接继续主升的票交给 R0 扳机；
冲高后放量砸回平台的票，不算好的 R7。
"""
from __future__ import annotations
import argparse
import datetime as dt
import math
import os
import statistics
import sys

import fetch
import store

DEFAULT_TODAY_EXCLUDES = ("bj", "sh688")

SETUP_LEN = 20
PULLBACK_LEN = 5
REL_LOOKBACK = 60
MIN_BARS = 50

PROBE_PCT = 0.07
PROBE_VOLRATIO5 = 1.8
PROBE_REL_TURNOVER = 2.0
PROBE_REL_AMOUNT = 2.0
PROBE_LIMIT_PCT = 0.095
PULLBACK_RATIO_STRONG = 0.8
PULLBACK_RATIO_LOOSE = 1.0
STRUCTURE_BREAK_BUFFER = 0.03
LIGHT_ACTIVE_RATIO = 1.3


def _pct_series(closes):
    out = [float("nan")]
    for i in range(1, len(closes)):
        p = closes[i - 1]
        out.append(closes[i] / p - 1 if p else float("nan"))
    return out


def _avg(xs):
    xs = [float(x) for x in xs if x is not None]
    return sum(xs) / len(xs) if xs else 0.0


def _median(xs):
    xs = [float(x) for x in xs if x is not None]
    return statistics.median(xs) if xs else 0.0


def _ratio(v, base):
    return float(v) / float(base) if base else 0.0


def _volratio5(vol, i):
    seg = vol[max(0, i - 5):i]
    m = _avg(seg)
    return _ratio(vol[i], m)


def _break_before(close, i, n=5):
    seg = close[max(0, i - n):i]
    return close[i] > max(seg) if seg else False


def _relative_metrics(frame, i):
    close = frame["close"]
    vol = frame["volume"]
    turnover = frame["turnover"]
    amounts = [close[j] * vol[j] for j in range(len(close))]
    hist_start = max(0, i - REL_LOOKBACK)
    hist_idx = list(range(hist_start, i))
    med_turn = _median(turnover[j] for j in hist_idx)
    med_amt = _median(amounts[j] for j in hist_idx)
    return {
        "volratio5": _volratio5(vol, i),
        "turnover_ratio60": _ratio(turnover[i], med_turn),
        "amount_ratio60": _ratio(amounts[i], med_amt),
        "median_turnover60": med_turn,
        "median_amount60": med_amt,
        "amount": amounts[i],
    }


def _probe_evidence(frame, pct, i):
    close = frame["close"]
    turnover = frame["turnover"]
    rel = _relative_metrics(frame, i)
    break5 = _break_before(close, i, 5)
    checks = []
    if rel["volratio5"] >= PROBE_VOLRATIO5:
        checks.append(f"量比5={rel['volratio5']:.1f}")
    if rel["turnover_ratio60"] >= PROBE_REL_TURNOVER:
        checks.append(f"换手/60日中位={rel['turnover_ratio60']:.1f}x")
    if rel["amount_ratio60"] >= PROBE_REL_AMOUNT:
        checks.append(f"额/60日中位={rel['amount_ratio60']:.1f}x")
    if pct[i] >= PROBE_LIMIT_PCT and break5:
        checks.append("近涨停且破5日高")
    return checks, rel, break5


def _find_probe(frame, idxs, pct, require_price=True):
    probes = []
    for i in idxs:
        p = pct[i]
        if p is None or math.isnan(p):
            continue
        checks, rel, break5 = _probe_evidence(frame, pct, i)
        if require_price:
            ok = p >= PROBE_PCT and bool(checks)
        else:
            ok = bool(checks)
        if ok:
            probes.append({
                "idx": i,
                "date": frame["date"][i],
                "pct": p,
                "turnover": frame["turnover"][i],
                "checks": checks,
                "volratio5": rel["volratio5"],
                "turnover_ratio60": rel["turnover_ratio60"],
                "amount_ratio60": rel["amount_ratio60"],
                "break5": break5,
            })
    if not probes:
        return None
    return max(probes, key=lambda x: (len(x["checks"]), x["pct"], x["volratio5"], x["turnover_ratio60"]))


def _light_active(frame, idxs, pct):
    best = None
    for i in idxs:
        rel = _relative_metrics(frame, i)
        p = pct[i]
        strength = max(rel["volratio5"], rel["turnover_ratio60"], rel["amount_ratio60"])
        if strength >= LIGHT_ACTIVE_RATIO:
            row = {
                "idx": i,
                "date": frame["date"][i],
                "pct": 0.0 if p is None or math.isnan(p) else p,
                "strength": strength,
                "volratio5": rel["volratio5"],
                "turnover_ratio60": rel["turnover_ratio60"],
                "amount_ratio60": rel["amount_ratio60"],
            }
            if best is None or (row["strength"], row["pct"]) > (best["strength"], best["pct"]):
                best = row
    return best


def _pullback_state(frame, setup_start, last5_start, probe_idx):
    close = frame["close"]
    vol = frame["volume"]
    last5 = list(range(last5_start, last5_start + PULLBACK_LEN))
    active = list(range(max(setup_start, probe_idx - 2), min(last5_start, probe_idx + 3)))
    if not active:
        active = list(range(setup_start, last5_start))
    active_avg = _avg(vol[i] for i in active)
    last5_avg = _avg(vol[i] for i in last5)
    pull_ratio = _ratio(last5_avg, active_avg)

    prior5 = list(range(max(0, probe_idx - 5), probe_idx))
    platform_low = min(close[i] for i in prior5) if prior5 else close[probe_idx]
    pullback_low = min(close[i] for i in last5)
    structure_ok = pullback_low >= platform_low * (1 - STRUCTURE_BREAK_BUFFER)
    return {
        "pullback_ratio": pull_ratio,
        "structure_ok": structure_ok,
        "platform_low": platform_low,
        "pullback_low": pullback_low,
    }


def score_r7(frame):
    """一个归一化K线 dict → (tier, desc, info)。
    info 只在找到试盘时给：{platform_low, tolerance_low, pullback_low, last_close}（后复权价），
    供单票模式换算成屏幕价打印结构线；没有试盘时为 None。"""
    if not frame or len(frame["date"]) < MIN_BARS:
        return None, "数据不足(<50根K线，次新或停牌)", None
    n = len(frame["date"])
    setup_start = max(0, n - SETUP_LEN)
    last5_start = n - PULLBACK_LEN
    if setup_start >= last5_start:
        return None, "历史不足以算R7窗口", None

    pct = _pct_series(frame["close"])
    setup_idx = list(range(setup_start, n))
    early_idx = list(range(setup_start, last5_start))
    last5_idx = list(range(last5_start, n))

    completed_probe = _find_probe(frame, early_idx, pct, require_price=True)
    recent_probe = _find_probe(frame, last5_idx, pct, require_price=True)
    light = _light_active(frame, setup_idx, pct)

    if completed_probe:
        pull = _pullback_state(frame, setup_start, last5_start, completed_probe["idx"])
        strong_pull = pull["pullback_ratio"] <= PULLBACK_RATIO_STRONG
        loose_pull = pull["pullback_ratio"] <= PULLBACK_RATIO_LOOSE
        if strong_pull and pull["structure_ok"]:
            s = 5
        elif loose_pull:
            s = 4
        else:
            s = 3
        desc = (
            f"R7={s} 试盘{completed_probe['date']} 涨{completed_probe['pct']*100:.1f}% "
            f"换手{completed_probe['turnover']*100:.1f}% 量比5={completed_probe['volratio5']:.1f} "
            f"相对换手{completed_probe['turnover_ratio60']:.1f}x 相对额{completed_probe['amount_ratio60']:.1f}x "
            f"回踩量比{pull['pullback_ratio']:.2f} 结构{'未破' if pull['structure_ok'] else '跌破'}"
        )
        info = {"platform_low": pull["platform_low"],
                "tolerance_low": pull["platform_low"] * (1 - STRUCTURE_BREAK_BUFFER),
                "pullback_low": pull["pullback_low"], "last_close": frame["close"][-1]}
        return s, desc, info

    if recent_probe:
        i = recent_probe["idx"]
        prior5 = list(range(max(0, i - 5), i))
        plat = min(frame["close"][j] for j in prior5) if prior5 else frame["close"][i]
        info = {"platform_low": plat, "tolerance_low": plat * (1 - STRUCTURE_BREAK_BUFFER),
                "pullback_low": min(frame["close"][j] for j in range(i, n)),
                "last_close": frame["close"][-1]}
        return 3, (
            f"R7=3 近5日刚试盘{recent_probe['date']} 涨{recent_probe['pct']*100:.1f}% "
            f"换手{recent_probe['turnover']*100:.1f}% 量比5={recent_probe['volratio5']:.1f}，"
            "尚未完成缩量回踩"
        ), info

    if light:
        return 2, (
            f"R7=2 仅轻微活跃 {light['date']} 涨{light['pct']*100:.1f}% "
            f"量比5={light['volratio5']:.1f} 相对换手{light['turnover_ratio60']:.1f}x "
            f"相对额{light['amount_ratio60']:.1f}x，未形成试盘回踩"
        ), None

    return 1, "R7=1 最近20日无明显相对放量试盘，也没有缩量回踩结构", None


def _name_map():
    import csv
    c2n, n2c = {}, {}
    up = os.path.join(store.STORE, "universe.csv")
    if os.path.exists(up):
        with open(up, encoding="utf-8") as f:
            for row in csv.DictReader(f):
                c2n[row["code"]] = row["name"]
                n2c[row["name"]] = row["code"]
    return c2n, n2c


def resolve(token, n2c):
    t = token.strip()
    if t[:2].lower() in ("sh", "sz", "bj") and t[2:].isdigit():
        return t.lower()
    if t.isdigit() and len(t) == 6:
        pref = "sh" if t[0] == "6" else ("bj" if t[0] in "489" else "sz")
        return pref + t
    if t in n2c:
        return n2c[t]
    hit = [c for n, c in n2c.items() if t in n]
    return hit[0] if len(hit) == 1 else None


def _is_default_today_excluded(sym):
    return sym.startswith(DEFAULT_TODAY_EXCLUDES)


def _screen_factor(sym, frame):
    """后复权→屏幕价换算因子（= 仓内 hfq 收盘 / 同日原始收盘）。
    拉最近两周原始价按日期配对；拿不到（断网/限流/停牌无重叠日）返回 None，调用方退回打后复权价。"""
    try:
        import akshare as ak
        end = frame["date"][-1]
        start = (dt.date.fromisoformat(end) - dt.timedelta(days=14)).isoformat()
        raw = ak.stock_zh_a_daily(symbol=sym, start_date=start.replace("-", ""),
                                  end_date=end.replace("-", ""), adjust="")
        m = {str(d)[:10]: float(c) for d, c in zip(raw["date"], raw["close"])}
        for i in range(len(frame["date"]) - 1, max(-1, len(frame["date"]) - 15), -1):
            d, hc = frame["date"][i], frame["close"][i]
            if d in m and m[d] and hc:
                return hc / m[d]
    except Exception:
        pass
    return None


def score_one(sym):
    frame = store.load_frame(sym)
    if not frame:
        end = store._data_end_date()
        start = (dt.date.fromisoformat(end) - dt.timedelta(days=180)).isoformat()
        frame = fetch.get_kline(sym, start, end)
        if not frame:
            return None, "联网现抓失败：网络不通/被 sina 限流/代码不存在。稍后再试，或先用 r0-data 建仓走本地"
    tier, desc, info = score_r7(frame)
    if tier is not None:
        last = frame["date"][-1]
        if last < (dt.date.fromisoformat(store._data_end_date()) - dt.timedelta(days=15)).isoformat():
            desc += f" ⚠数据止于{last}（疑似停牌，或本地仓太久没更新——跑 r0-data 增量）"
        if info:
            # 结构线换算成屏幕价（行情软件的除权价），对不上屏幕是后复权口径——这里替用户除掉因子
            f2 = _screen_factor(sym, frame)
            cv = (lambda v: f"{v / f2:.2f}") if f2 else (lambda v: f"{v:.2f}")
            unit = f"屏幕价,复权因子{f2:.2f}" if f2 else "后复权价,原始价没拿到"
            desc += (f"｜结构线({unit}): 平台{cv(info['platform_low'])} / "
                     f"容忍{cv(info['tolerance_low'])} / 最近收{cv(info['last_close'])}")
    return tier, desc


def cmd_today(min_score, include_bj688=False):
    syms = store.list_symbols()
    if not syms:
        print(f"本地仓为空（{store.STORE}）。先建仓： python3 store.py backfill --days 400", file=sys.stderr)
        sys.exit(1)
    c2n, _ = _name_map()
    rows, lasts = [], []
    excluded = 0
    for i, sym in enumerate(syms):
        if i % 1000 == 0:
            print(f"  扫描 {i}/{len(syms)}", file=sys.stderr)
        if not include_bj688 and _is_default_today_excluded(sym):
            excluded += 1
            continue
        frame = store.load_frame(sym)
        if not frame:
            continue
        lasts.append(frame["date"][-1])
        tier, desc, _ = score_r7(frame)   # 名单不换算屏幕价（每只都要一次网络请求，不值得）
        if tier is not None and tier >= min_score:
            rows.append((tier, sym, c2n.get(sym, ""), desc, frame["date"][-1]))
    if not lasts:
        print("本地仓文件全部读不出来（多半缺 pyarrow 或文件损坏）", file=sys.stderr)
        sys.exit(1)
    data_max = max(lasts)
    stale_cut = (dt.date.fromisoformat(data_max) - dt.timedelta(days=15)).isoformat()
    stale_n = sum(1 for r in rows if r[4] < stale_cut)
    rows = [r for r in rows if r[4] >= stale_cut]
    rows.sort(key=lambda r: (-r[0], r[1]))
    notes = []
    if not include_bj688:
        notes.append(f"默认排除 bj*/sh688* {excluded} 只")
    if stale_n:
        notes.append(f"另剔除 {stale_n} 只停牌/数据过旧票")
    note = "；" + "；".join(notes) if notes else ""
    print(f"# 最近20日试盘后回踩（R7≥{min_score}）名单（数据截至 {data_max}，共 {len(rows)} 只{note}）\n")
    for tier, sym, name, desc, _ in rows:
        print(f"{tier}  {sym} {name:<6}  {desc}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("tickers", nargs="*", help="名称或代码，可多只")
    ap.add_argument("--today", action="store_true", help="扫本地仓列出 R7≥min 的试盘回踩票")
    ap.add_argument("--min", type=int, default=4, help="--today 的分数门槛，默认4")
    ap.add_argument("--include-bj688", action="store_true", help="--today 时包含 bj* 和 sh688*（默认排除）")
    args = ap.parse_args()

    if args.today:
        cmd_today(args.min, include_bj688=args.include_bj688)
        return
    if not args.tickers:
        ap.print_help()
        return

    c2n, n2c = _name_map()
    for tok in args.tickers:
        sym = resolve(tok, n2c)
        if not sym:
            print(f"✗ {tok}：解析不出代码（名称歧义或本地无票名快照，请给6位代码）")
            continue
        tier, desc = score_one(sym)
        name = c2n.get(sym, "")
        if tier is None:
            print(f"✗ {sym} {name}：{desc}")
        else:
            print(f"R7={tier}  {sym} {name}  {desc}")


if __name__ == "__main__" and len(sys.argv) == 1:
    assert resolve("sh603228", {}) == "sh603228"
    assert resolve("603228", {}) == "sh603228"
    assert resolve("300476", {}) == "sz300476"
    assert resolve("920819", {}) == "bj920819"
    assert _is_default_today_excluded("bj920510")
    assert _is_default_today_excluded("sh688017")
    assert not _is_default_today_excluded("sh603228")

    n = 80
    close = [10.0] * n
    vol = [1000.0] * n
    turnover = [0.01] * n
    probe = n - 12
    close[probe] = 10.9
    vol[probe] = 3000.0
    turnover[probe] = 0.035
    for i in range(probe + 1, n - 5):
        close[i] = 10.6
        vol[i] = 1800.0
        turnover[i] = 0.02
    for i in range(n - 5, n):
        close[i] = 10.4
        vol[i] = 700.0
        turnover[i] = 0.01
    frame = {"date": [f"d{i:02d}" for i in range(n)], "open": close, "high": [c * 1.01 for c in close],
             "low": [c * 0.99 for c in close], "close": close, "volume": vol, "turnover": turnover}
    tier, desc, info = score_r7(frame)
    assert tier == 5, f"试盘后缩量回踩应 R7=5，实际 {tier} {desc}"
    assert info and abs(info["platform_low"] - 10.0) < 1e-9, f"平台线应=试盘前5日最低收盘10.0，实际 {info}"
    assert abs(info["tolerance_low"] - 9.7) < 1e-9, "容忍线应=平台×0.97"

    short, _, _ = score_r7({"date": ["d0"] * 10, "open": [1] * 10, "high": [1] * 10, "low": [1] * 10,
                            "close": [1] * 10, "volume": [1] * 10, "turnover": [0.01] * 10})
    assert short is None
    print(f"r7 自检通过 ✓  合成票 R7={tier} | {desc}")
    sys.exit(0)

if __name__ == "__main__":
    main()
