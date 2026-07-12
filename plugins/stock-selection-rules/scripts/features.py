"""纯量价特征计算：给定一只票的归一化日K + 锚点位置，算出评分卡要用的启动前/判定窗特征。
归一化 K线 DataFrame（按日期升序）列：date, open, high, low, close, volume, turnover
  turnover 为分数（0.1376 = 13.76%），pct 内部按 close/prev_close-1 算。
窗口口径见 启动前规律_评分卡_v1.md §0：
  anchor 为打分锚点(只用 ≤anchor 的行)；J=判定窗(launch_len 根，止于 anchor)；pre20=J 之前 pre20_len 根。
无外部依赖，可 python features.py 自检。
"""
from __future__ import annotations
import math


def _pct_series(closes):
    out = [float("nan")]
    for i in range(1, len(closes)):
        p = closes[i - 1]
        out.append(closes[i] / p - 1 if p else float("nan"))
    return out


def compute_features(frame, anchor_idx, cfg):
    """frame: dict of lists {date,open,high,low,close,volume,turnover}；anchor_idx: 锚点行下标。
    返回特征 dict；数据不足返回 None。"""
    w = cfg["windows"]
    L, P, LB = w["launch_len"], w["pre20_len"], w["breakout_lookback"]
    need_before = P + LB  # pre20 之前还要 LB 根算突破前高/量比
    if anchor_idx - L + 1 - need_before < 0:
        return None
    close = frame["close"]
    vol = frame["volume"]
    to = frame["turnover"]
    pct = _pct_series(close)

    # --- 窗口下标 ---
    j_start = anchor_idx - L + 1
    j_idx = list(range(j_start, anchor_idx + 1))              # 判定窗 J
    pre_end = j_start - 1
    pre_start = pre_end - P + 1
    pre_idx = list(range(pre_start, pre_end + 1))             # 启动前窗 pre20

    # --- pre20 位置/换手 ---
    pre20_return = close[pre_end] / close[pre_start] - 1
    pre_to = [to[i] for i in pre_idx]
    pre20_avg_turnover = sum(pre_to) / len(pre_to)
    pre20_max_turnover = max(pre_to)

    # --- pre20 形态：试盘 + 回踩缩量 ---
    has_probe = any(
        (pct[i] is not None and not math.isnan(pct[i]) and pct[i] >= cfg["R7"]["probe_pct"] and to[i] > cfg["R7"]["probe_turnover"])
        or (pct[i] is not None and not math.isnan(pct[i]) and pct[i] >= cfg["R7"]["limit_pct"])
        for i in pre_idx
    )
    last5 = pre_idx[-5:]
    early = pre_idx[:-5] or pre_idx
    v_last5 = sum(vol[i] for i in last5) / len(last5)
    v_early = sum(vol[i] for i in early) / len(early)
    pullback_ratio = v_last5 / v_early if v_early else float("inf")

    # --- 判定窗 J：逐根找最强启动确认K线 ---
    def hi_before(i, n):
        seg = close[i - n:i]
        return max(seg) if seg else float("-inf")

    def volratio5(i):
        seg = vol[i - 5:i]
        m = sum(seg) / len(seg) if seg else 0
        return vol[i] / m if m else 0.0

    bars = []
    for i in j_idx:
        p = pct[i]
        if p is None or math.isnan(p):
            continue
        bars.append({
            "date": frame["date"][i], "pct": p, "turnover": to[i],
            "volratio5": volratio5(i),
            "break5": close[i] > hi_before(i, 5),
            "break10": close[i] > hi_before(i, 10),
            "break20": close[i] > hi_before(i, 20),
        })

    return {
        "anchor_date": frame["date"][anchor_idx],
        "anchor_close": close[anchor_idx],
        "pre20_return": pre20_return,
        "pre20_avg_turnover": pre20_avg_turnover,
        "pre20_max_turnover": pre20_max_turnover,
        "pre20_has_probe": has_probe,
        "pre20_pullback_ratio": pullback_ratio,
        "j_bars": bars,
    }


def outcome_return(frame, anchor_idx, outcome_len):
    """兼容旧接口；结果口径统一由 bt_common.outcome_return 维护。"""
    from bt_common import outcome_return as _outcome_return

    return _outcome_return(frame, anchor_idx, outcome_len)


# ---------------- 自检 ----------------
if __name__ == "__main__":
    import yaml, os
    cfg = yaml.safe_load(open(os.path.join(os.path.dirname(__file__), "rules_config.yaml"), encoding="utf-8"))
    # 造一条已知答案的合成K线：pre20 横盘低换手(位置干净) → J 里一根放量强阳破前高 → 之后大涨
    n = 60
    date = [f"d{i:02d}" for i in range(n)]
    close = [10.0] * 40                      # 前40根横在10块（pre20 里位置干净、涨幅~0）
    close += [10.0, 10.1, 11.2, 11.3, 11.4]  # 40..44：其中 42 放量强阳
    close += [12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 24, 25, 26]  # O：一路大涨
    openp = [c for c in close]
    high = [c * 1.01 for c in close]
    low = [c * 0.99 for c in close]
    vol = [1000.0] * 42 + [3000.0] + [1000.0] * (n - 43)   # 第42根放量3倍
    to = [0.02] * n                                        # 换手 2%（干净低位）
    to[42] = 0.09
    frame = {"date": date, "open": openp, "high": high, "low": low, "close": close, "volume": vol, "turnover": to}

    # anchor 取第 44 根（J=[40..44]，pre20=[15..39]，之后 15 根做 O）
    anchor = 44
    f = compute_features(frame, anchor, cfg)
    assert f is not None, "特征应算得出"
    assert abs(f["pre20_return"]) < 0.01, f"pre20 应~0，实际{f['pre20_return']}"
    assert f["pre20_avg_turnover"] < 0.035, "pre20 换手应<3.5%"
    strong = [b for b in f["j_bars"] if b["pct"] >= 0.07 and b["volratio5"] > 1.4 and b["break5"]]
    assert strong, f"J 内应有放量强阳破前高，实际 {f['j_bars']}"
    o = outcome_return(frame, anchor, cfg["windows"]["outcome_len"])
    assert o is not None and o > 0.5, f"O 应大涨>50%，实际{o}"
    # 边界：数据不足返回 None
    assert compute_features(frame, 5, cfg) is None, "锚点太早应返回 None"
    print("features 自检通过 ✓  pre20_return=%.3f avg_to=%.3f 强阳=%d O=%.2f" % (
        f["pre20_return"], f["pre20_avg_turnover"], len(strong), o))
