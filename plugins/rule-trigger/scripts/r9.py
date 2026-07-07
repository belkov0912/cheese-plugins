"""R9 下跌反转 · 单票/多票即时查 + 全市场高分名单。

R9 语义 = "刚走完一段明确下跌、横住企稳之后，最近 5 个交易日里有没有出现
放量大阳收复失地的反转确认K线"。

只有 5 分是值得行动的档（回测 hit10=38.3%、hit20=18.9%，基础的 2.1/3.2 倍）；
3/4 分与基础差距小，只当观察。2 分 = 下跌企稳背景在、还没确认，进观察池。
定版参数与回测同源：扫描器仓 r9_reversal.py（2026-07-07 十轮迭代 iter7 冠军）。
"""
from __future__ import annotations
import argparse
import datetime as dt
import math
import sys

import fetch
import store
from r7 import _name_map, resolve, _is_default_today_excluded, _screen_factor, _pct_series

DEFAULT_TODAY_EXCLUDES = ("bj", "sh688")

DOWN_LEN = 20        # 下跌段长度
STAB_LEN = 7         # 企稳段长度
JUDGE_LEN = 5        # 判定窗:最近5个交易日找信号日
MIN_BARS = 45

DOWN_RET = -0.12     # 下跌段跌幅门槛
LOW_TOL = 0.99       # 企稳不破低容忍(乘数)
STAB_VOL = 1.0       # 企稳段均量/下跌段均量 上限
WEAK_PCT, WEAK_VR = 0.03, 1.3    # 3分:温和放量上涨
MID_PCT, MID_VR = 0.04, 1.5      # 4分:放量上涨
STRONG_PCT = 0.07                # 5分:强阳(量能路径已回测证明无效,不设)
BREAK_N4 = 10        # 4分:破10日高(冒出企稳平台)
BREAK_N5 = 20        # 5分:收复20日高(吃掉整段下跌套牢区)
ONECHAR_TURNOVER = 0.02


def _avg(xs):
    xs = list(xs)
    return sum(xs) / len(xs) if xs else 0.0


def _background(close, vol, i):
    """信号日 i 的下跌企稳背景。返回 (成立?, 证据dict)。
    下跌段 D=[i-27, i-8](20根),企稳段 S=[i-7, i-1](7根),与回测 shift 口径逐字一致。"""
    if i < STAB_LEN + DOWN_LEN:
        return False, None
    d_lo, d_hi = i - STAB_LEN - DOWN_LEN, i - STAB_LEN - 1
    s_lo, s_hi = i - STAB_LEN, i - 1
    down_ret = close[d_hi] / close[d_lo] - 1
    down_min = min(close[d_lo:d_hi + 1])
    stab_min = min(close[s_lo:s_hi + 1])
    vol_down = _avg(vol[d_lo:d_hi + 1])
    vol_stab = _avg(vol[s_lo:s_hi + 1])
    ok = (down_ret <= DOWN_RET
          and stab_min >= down_min * LOW_TOL
          and vol_stab <= vol_down * STAB_VOL)
    ev = {"down_ret": down_ret, "down_min": down_min, "stab_min": stab_min,
          "stab_vol_ratio": vol_stab / vol_down if vol_down else float("inf"),
          "down_from": d_lo, "down_to": d_hi}
    return ok, ev


def _tier_at(frame, pct, i):
    """判定窗内单根K线的 R9 档位。返回 (tier, ev) ;背景不成立返回 (None, None)。"""
    close, vol, to = frame["close"], frame["volume"], frame["turnover"]
    ok, ev = _background(close, vol, i)
    if not ok:
        return None, None
    p = pct[i]
    if p is None or math.isnan(p):
        return 2, ev
    vr5 = vol[i] / _avg(vol[i - 5:i]) if _avg(vol[i - 5:i]) else 0.0
    break10 = close[i] > max(close[i - BREAK_N4:i])
    break20 = close[i] > max(close[i - BREAK_N5:i])
    tier = 2
    if p >= WEAK_PCT and vr5 >= WEAK_VR:
        tier = 3
    if p >= MID_PCT and vr5 >= MID_VR and break10:
        tier = 4
    if p >= STRONG_PCT and vr5 >= MID_VR and break20:
        tier = 5
    if tier >= 3 and to[i] < ONECHAR_TURNOVER:
        tier -= 1  # 一字板降档:买不到的信号不可执行,同 R0
    ev = dict(ev, pct=p, vr5=vr5, turnover=to[i], break10=break10, break20=break20,
              reclaim_hi=max(close[i - BREAK_N5:i]))
    return tier, ev


def score_r9(frame):
    """一个归一化K线 dict → (tier, desc, info)。
    info 在 tier>=2 时给:{reclaim_hi, down_low, last_close}(后复权价),
    reclaim_hi=当前要收复的20日高(收上它才够5分确认),供单票模式换算屏幕价。"""
    if not frame or len(frame["date"]) < MIN_BARS:
        return None, f"数据不足(<{MIN_BARS}根K线,次新或停牌)", None
    n = len(frame["date"])
    close, vol = frame["close"], frame["volume"]
    pct = _pct_series(close)

    best, best_ev, best_i = None, None, None
    for i in range(n - JUDGE_LEN, n):
        tier, ev = _tier_at(frame, pct, i)
        if tier is not None and tier >= 3:
            key = (tier, ev.get("pct", 0))
            if best is None or key > (best, best_ev.get("pct", 0)):
                best, best_ev, best_i = tier, ev, i

    if best is not None:
        ev = best_ev
        d = frame["date"][best_i]
        recl = "收复20日高" if ev["break20"] else ("破10日高" if ev["break10"] else "未破平台")
        desc = (f"R9={best} 反转确认{d} 涨{ev['pct']*100:.1f}% 量比5={ev['vr5']:.1f} "
                f"换手{ev['turnover']*100:.1f}% {recl}"
                f"｜背景:前置20日跌{ev['down_ret']*100:.1f}% 企稳缩量比{ev['stab_vol_ratio']:.2f}")
        info = {"reclaim_hi": ev["reclaim_hi"], "down_low": ev["down_min"],
                "last_close": close[-1]}
        return best, desc, info

    # 判定窗内没有>=3的信号:看当前是否处于"下跌企稳"观察状态(以最后一根为准)
    ok, ev = _background(close, vol, n - 1)
    if ok:
        reclaim_hi = max(close[n - 1 - BREAK_N5:n - 1])
        desc = (f"R9=2 下跌企稳观察中:前置20日跌{ev['down_ret']*100:.1f}% "
                f"企稳未破低(低点{ev['down_min']:.2f}) 缩量比{ev['stab_vol_ratio']:.2f}，"
                f"等放量大阳收复20日高({reclaim_hi:.2f})才算确认")
        return 2, desc, {"reclaim_hi": reclaim_hi, "down_low": ev["down_min"],
                         "last_close": close[-1]}
    return 1, "R9=1 无下跌企稳背景(不是刚跌完企稳的形态)", None


def score_one(sym):
    frame = store.load_frame(sym)
    if not frame:
        end = store._data_end_date()
        start = (dt.date.fromisoformat(end) - dt.timedelta(days=180)).isoformat()
        frame = fetch.get_kline(sym, start, end)
        if not frame:
            return None, "联网现抓失败：网络不通/被 sina 限流/代码不存在。稍后再试，或先用 r0-data 建仓走本地"
    tier, desc, info = score_r9(frame)
    if tier is not None:
        last = frame["date"][-1]
        if last < (dt.date.fromisoformat(store._data_end_date()) - dt.timedelta(days=15)).isoformat():
            desc += f" ⚠数据止于{last}（疑似停牌，或本地仓太久没更新——跑 r0-data 增量）"
        if info:
            f2 = _screen_factor(sym, frame)
            cv = (lambda v: f"{v / f2:.2f}") if f2 else (lambda v: f"{v:.2f}")
            unit = f"屏幕价,复权因子{f2:.2f}" if f2 else "后复权价,原始价没拿到"
            desc += (f"｜关键价({unit}): 收复线{cv(info['reclaim_hi'])} / "
                     f"下跌低点{cv(info['down_low'])} / 最近收{cv(info['last_close'])}")
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
        tier, desc, _ = score_r9(frame)   # 名单不换算屏幕价(每只都要一次网络请求,不值得)
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
    print(f"# 下跌反转确认（R9≥{min_score}）名单（数据截至 {data_max}，共 {len(rows)} 只{note}）\n")
    for tier, sym, name, desc, _ in rows:
        print(f"{tier}  {sym} {name:<6}  {desc}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("tickers", nargs="*", help="名称或代码，可多只")
    ap.add_argument("--today", action="store_true", help="扫本地仓列出 R9≥min 的下跌反转票")
    ap.add_argument("--min", type=int, default=5, help="--today 的分数门槛，默认5(唯一的钱桶)")
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
            print(f"R9={tier}  {sym} {name}  {desc}")


if __name__ == "__main__" and len(sys.argv) == 1:
    # 合成K线自检:横盘15 → 下跌20根10→8 → 企稳12根缩量8.15 → 信号日+9%放量4倍收复20日高
    n = 75
    close = [10.0] * 15
    close += [10 - 2 * k / 19 for k in range(20)]
    close += [8.15, 8.13, 8.16, 8.14, 8.17, 8.15, 8.13, 8.16, 8.15, 8.14, 8.17, 8.15]
    close += [8.15 * 1.09]
    close += [9.0 + k * 0.05 for k in range(n - 48)]
    vol = [1000.0] * 35 + [600.0] * 12 + [2500.0] + [1200.0] * (n - 48)
    frame = {"date": [f"D{i:03d}" for i in range(n)], "open": close,
             "high": [c * 1.01 for c in close], "low": [c * 0.99 for c in close],
             "close": close, "volume": vol, "turnover": [0.05] * n}
    # 截到信号日为判定窗末根
    f_sig = {k: (v[:48] if isinstance(v, list) else v) for k, v in frame.items()}
    tier, desc, info = score_r9(f_sig)
    assert tier == 5, f"信号日应 R9=5，实际 {tier} {desc}"
    assert info and info["down_low"] == 8.0, f"下跌低点应8.0,实际 {info}"
    # 只到企稳段末=观察状态
    f_stab = {k: (v[:47] if isinstance(v, list) else v) for k, v in frame.items()}
    tier2, desc2, _ = score_r9(f_stab)
    assert tier2 == 2, f"企稳期应 R9=2，实际 {tier2} {desc2}"
    # 一路上涨无下跌背景 → 1
    up = [8 + 4 * k / (n - 1) for k in range(n)]
    f_up = dict(frame, close=up, open=up, high=[c * 1.01 for c in up], low=[c * 0.99 for c in up])
    tier3, desc3, _ = score_r9(f_up)
    assert tier3 == 1, f"上涨背景应 R9=1，实际 {tier3} {desc3}"
    short, _, _ = score_r9({"date": ["d"] * 10, "open": [1] * 10, "high": [1] * 10,
                            "low": [1] * 10, "close": [1] * 10, "volume": [1] * 10,
                            "turnover": [0.01] * 10})
    assert short is None
    print(f"r9 自检通过 ✓  合成票 R9={tier} | {desc}")
    sys.exit(0)

if __name__ == "__main__":
    main()
