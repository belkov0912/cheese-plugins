"""R0/R7 当前回测打分，并保留旧版 R0-R8 综合评分兼容接口。

旧接口的阈值和权重继续从 rules_config.yaml 读取。
"""
from __future__ import annotations

RULES = ["R0", "R1", "R2", "R3", "R4", "R5", "R6", "R7", "R8"]


def _pctstr(x):
    return "缺" if x is None else f"{x*100:.0f}%"


def score_R0(feat, cfg):
    c = cfg["R0"]
    best, btier = None, 1
    for b in feat["j_bars"]:
        p, vr = b["pct"], b["volratio5"]
        if p >= c["strong_pct"] and vr > c["volratio"] and b["break5"] and b["break10"] and b["break20"]:
            t = 5
        elif p >= c["strong_pct"] and vr > c["volratio"] and b["break5"]:
            t = 4
        elif (p >= c["strong_pct"] and b["break5"]) or (vr > c["volratio"] and c["mid_pct"] <= p < c["strong_pct"] and b["break5"]):
            t = 3
        elif (c["weak_pct"] <= p < c["strong_pct"] and vr > c["volratio"]) or (b["break5"] and p < c["mid_pct"]):
            t = 2
        else:
            t = 1
        if b["turnover"] < c["onechar_turnover"] and t > 1:
            t -= 1
        if t > btier or best is None:
            btier, best = t, b
    if best is None:
        return 1, "R0=1 判定窗无有效K线"
    tag = "/".join(k for k, v in [("5", best["break5"]), ("10", best["break10"]), ("20", best["break20"])] if v) or "无"
    return btier, f"R0={btier} {best['date']} 涨{best['pct']*100:.1f}% 量比{best['volratio5']:.1f} 破{tag}日高 换手{best['turnover']*100:.0f}%"


def score_R1(meta, cfg):
    m = meta["ai"]["tier"]
    g = meta.get("growth")
    if g is None:
        s = {2: 3, 1: 2, 0: 1}[m]
        return s, f"R1={s} 主线tier{m}({','.join(meta['ai']['hits'][:2]) or '非AI'})+财报缺失"
    factor = 2 if g > cfg["R1"]["growth_strong"] else (1 if g >= 0 else 0)
    table = {
        (2, 2): 5, (2, 1): 4, (1, 2): 4,
        (2, 0): 3, (1, 1): 3, (1, 0): 2,
        (0, 2): 2, (0, 1): 2, (0, 0): 1,
    }
    s = table[(m, factor)]
    if m == 0:
        s = min(s, 2)
    return s, f"R1={s} 主线tier{m}({','.join(meta['ai']['hits'][:2]) or '非AI'}) 财报同比{_pctstr(g)}"


def score_R2(feat, cfg):
    c = cfg["R2"]
    r, t = feat["pre20_return"], feat["pre20_avg_turnover"]
    if r > c["overheat_return"] or t > c["overheat_turnover"]:
        return 1, f"R2=1 启动前20日涨{r*100:.0f}%/均换手{t*100:.0f}% 二波过热"
    if c["s5_return"][0] <= r <= c["s5_return"][1]:
        base = 5
    elif c["s4_return"][0] < r <= c["s4_return"][1]:
        base = 4
    elif c["s3_return"][0] < r <= c["s3_return"][1]:
        base = 3
    elif c["s2_return"][0] < r <= c["s2_return"][1]:
        base = 2
    elif r < c["s5_return"][0]:
        base = 3
    else:
        base = 2
    if t >= c["s4_turnover"]:
        base = min(base, 2)
    elif t >= c["s5_turnover"]:
        base = min(base, 4)
    return base, f"R2={base} 启动前20日涨{r*100:.0f}% 均换手{t*100:.1f}%"


def score_R3(meta, cfg):
    ai = meta["ai"]
    if ai.get("industry_ai") and ai["tier"] >= 1:
        s = 5
    elif ai.get("industry_ai"):
        s = 4
    elif ai["tier"] >= 2:
        s = 3
    elif ai["tier"] == 1:
        s = 2
    else:
        s = 1
    return s, f"R3={s} {'AI主业' if ai.get('industry_ai') else '概念挂靠tier'+str(ai['tier'])}(粗代理)"


def score_R4(meta, cfg):
    value = meta.get("mktcap_yi")
    if value is None:
        return 3, "R4=3 市值缺失"
    for lo, hi, score in cfg["R4"]["bands"]:
        if lo <= value < hi:
            return score, f"R4={score} 市值{value:.0f}亿"
    return 1, f"R4=1 市值{value:.0f}亿"


def score_R5(meta, cfg):
    pe = meta.get("pe_ttm")
    c = cfg["R5"]
    if pe is None:
        return 3, "R5=3 PE_TTM缺失"
    if pe < 0:
        score = 3 if pe >= c["small_loss_pe"] else 1
        return score, f"R5={score} 亏损PE_TTM{pe:.0f}"
    for lo, hi, score in c["bands_pos"]:
        if lo <= pe < hi:
            return score, f"R5={score} PE_TTM{pe:.0f}"
    return 1, f"R5=1 PE_TTM{pe:.0f}"


def score_R6(meta, cfg):
    if meta.get("st"):
        return 1, "R6=1 ST/*ST"
    flags = meta.get("risk_flags") or []
    if flags:
        return 3, f"R6=3 {'/'.join(flags[:2])}"
    return 5, "R6=5 信披暂无雷(代理)"


def score_R7(feat, cfg):
    """旧版绝对换手口径，仅供 backtest_r7.py 对照。"""
    c = cfg["R7"]
    lo, hi = c["active_turnover"]
    t = feat["pre20_avg_turnover"]
    act = lo <= t <= hi
    probe = feat["pre20_has_probe"]
    pull = feat["pre20_pullback_ratio"] <= c["pullback_ratio"]
    if act and probe and pull:
        s = 5
    elif probe and pull:
        s = 4
    elif probe or act:
        s = 3
    elif t >= lo:
        s = 2
    else:
        s = 1
    return s, f"R7={s} 均换手{t*100:.1f}% 试盘{'有' if probe else '无'} 回踩{feat['pre20_pullback_ratio']:.2f}"


def score_R8(meta, cfg):
    event = meta.get("event") or {}
    if event.get("restructure_active"):
        return 5, "R8=5 重组停复牌推进"
    if event.get("restructure_concept"):
        return 4, "R8=4 重组/注入概念"
    if event.get("event_concept"):
        return 3, "R8=3 有事件概念无实质推进"
    return 1, "R8=1 无事件数据(占位)"


def score_all(feat, meta, cfg):
    """返回旧版 R0-R8 分项及 v1/v2 综合分。"""
    out = {
        "R0": score_R0(feat, cfg),
        "R1": score_R1(meta, cfg),
        "R2": score_R2(feat, cfg),
        "R3": score_R3(meta, cfg),
        "R4": score_R4(meta, cfg),
        "R5": score_R5(meta, cfg),
        "R6": score_R6(meta, cfg),
        "R7": score_R7(feat, cfg),
        "R8": score_R8(meta, cfg),
    }
    weights = cfg["weights"]
    for key, current_weights in (
        ("composite", weights),
        ("composite_v2", cfg.get("weights_v2") or weights),
    ):
        raw = sum(current_weights[rule] * out[rule][0] for rule in RULES)
        if meta.get("st"):
            raw = min(raw, float(cfg["R6"]["st_cap"]))
        out[key] = max(1, min(5, int(round(raw))))
        out[key + "_raw"] = round(raw, 4)
    out["评分说明"] = " | ".join(out[rule][1] for rule in RULES)
    return out


if __name__ == "__main__":
    import os
    import yaml

    from features import compute_features

    cfg = yaml.safe_load(open(os.path.join(os.path.dirname(__file__), "rules_config.yaml"), encoding="utf-8"))
    n = 60
    close = [10.0] * 40 + [10.0, 10.1, 11.2, 11.3, 11.4] + list(range(12, 27))
    volume = [1000.0] * 42 + [3000.0] + [1000.0] * (n - 43)
    turnover = [0.02] * n
    turnover[42] = 0.09
    frame = {
        "date": [f"d{i:02d}" for i in range(n)],
        "open": close,
        "high": [c * 1.01 for c in close],
        "low": [c * 0.99 for c in close],
        "close": close,
        "volume": volume,
        "turnover": turnover,
    }
    feat = compute_features(frame, 44, cfg)
    meta = {
        "mktcap_yi": 88.0,
        "pe_ttm": 55.0,
        "ai": {"tier": 2, "industry_ai": True, "hits": ["半导体", "算力"]},
        "growth": 0.8,
        "st": False,
        "event": {},
    }
    result = score_all(feat, meta, cfg)
    assert result["R0"][0] >= 4
    assert result["R1"][0] == 5
    assert result["R2"][0] == 5
    assert result["R4"][0] == 5
    assert 1 <= result["composite"] <= 5
    assert 1 <= result["composite_v2"] <= 5
    assert score_all(feat, dict(meta, st=True), cfg)["composite"] <= 2
    print("score 自检通过 ✓ ", {rule: result[rule][0] for rule in RULES}, "综合", result["composite"])
