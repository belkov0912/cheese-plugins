"""R0–R8 打分：每条规律输出 (1-5 分, 一句描述)，再合成综合分。
阈值全读 rules_config.yaml。见 启动前规律_评分卡_v1.md §2/§3。
输入：
  feat  = features.compute_features 的返回
  meta  = {"mktcap_yi":float|None, "pe_ttm":float|None, "ai":{"tier":0/1/2,"industry_ai":bool,"hits":[..]},
           "growth":float|None(最近一期归母/扣非同比,取大者,分数), "st":bool, "event":{...}}
无外部依赖，可 python score.py 自检。
"""
from __future__ import annotations
import math

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
            t -= 1  # 一字/买不到，降一档
        if t > btier or best is None:
            btier, best = t, b
    if best is None:
        return 1, "R0=1 判定窗无有效K线"
    tag = "/".join(k for k, v in [("5", best["break5"]), ("10", best["break10"]), ("20", best["break20"]) ] if v) or "无"
    return btier, f"R0={btier} {best['date']} 涨{best['pct']*100:.1f}% 量比{best['volratio5']:.1f} 破{tag}日高 换手{best['turnover']*100:.0f}%"


def score_R1(meta, cfg):
    m = meta["ai"]["tier"]
    g = meta.get("growth")
    if g is None:
        s = {2: 3, 1: 2, 0: 1}[m]
        return s, f"R1={s} 主线tier{m}({','.join(meta['ai']['hits'][:2]) or '非AI'})+财报缺失"
    F = 2 if g > cfg["R1"]["growth_strong"] else (1 if g >= 0 else 0)
    tbl = {(2, 2): 5, (2, 1): 4, (1, 2): 4, (2, 0): 3, (1, 1): 3, (1, 0): 2, (0, 2): 2, (0, 1): 2, (0, 0): 1}
    s = tbl[(m, F)]
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
    v = meta.get("mktcap_yi")
    if v is None:
        return 3, "R4=3 市值缺失"
    for lo, hi, s in cfg["R4"]["bands"]:
        if lo <= v < hi:
            return s, f"R4={s} 市值{v:.0f}亿"
    return 1, f"R4=1 市值{v:.0f}亿"


def score_R5(meta, cfg):
    pe = meta.get("pe_ttm")
    c = cfg["R5"]
    if pe is None:
        return 3, "R5=3 PE_TTM缺失"
    if pe < 0:
        s = 3 if pe >= c["small_loss_pe"] else 1
        return s, f"R5={s} 亏损PE_TTM{pe:.0f}"
    for lo, hi, s in c["bands_pos"]:
        if lo <= pe < hi:
            return s, f"R5={s} PE_TTM{pe:.0f}"
    return 1, f"R5=1 PE_TTM{pe:.0f}"


def score_R6(meta, cfg):
    if meta.get("st"):
        return 1, "R6=1 ST/*ST"
    flags = meta.get("risk_flags") or []
    if flags:
        return 3, f"R6=3 {'/'.join(flags[:2])}"
    return 5, "R6=5 信披暂无雷(代理)"


def score_R7(feat, cfg):
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
    ev = meta.get("event") or {}
    if ev.get("restructure_active"):
        return 5, "R8=5 重组停复牌推进"
    if ev.get("restructure_concept"):
        return 4, "R8=4 重组/注入概念"
    if ev.get("event_concept"):
        return 3, "R8=3 有事件概念无实质推进"
    return 1, "R8=1 无事件数据(占位)"


def score_all(feat, meta, cfg):
    """返回 {'R0':(s,desc),...,'composite':int,'composite_raw':float,
    'composite_v2':int,'composite_v2_raw':float,'评分说明':str}
    composite=v1 现行权重；composite_v2=挑战者权重(weights_v2，缺省时等于 v1)，两者并排进验证。
    raw 为未取整的加权分，验证算 IC 用（3档取整分算相关太粗）。"""
    out = {
        "R0": score_R0(feat, cfg), "R1": score_R1(meta, cfg), "R2": score_R2(feat, cfg),
        "R3": score_R3(meta, cfg), "R4": score_R4(meta, cfg), "R5": score_R5(meta, cfg),
        "R6": score_R6(meta, cfg), "R7": score_R7(feat, cfg), "R8": score_R8(meta, cfg),
    }
    for key, w in (("composite", cfg["weights"]), ("composite_v2", cfg.get("weights_v2") or cfg["weights"])):
        raw = sum(w[r] * out[r][0] for r in RULES)
        if meta.get("st"):
            raw = min(raw, float(cfg["R6"]["st_cap"]))  # raw 也封顶，IC 用 raw 算
        comp = max(1, min(5, int(round(raw))))
        out[key] = comp
        out[key + "_raw"] = round(raw, 4)
    out["评分说明"] = " | ".join(out[r][1] for r in RULES)
    return out


# ---------------- 自检 ----------------
if __name__ == "__main__":
    import yaml, os
    from features import compute_features
    cfg = yaml.safe_load(open(os.path.join(os.path.dirname(__file__), "rules_config.yaml"), encoding="utf-8"))
    # 复用 features 自检里的"干净低位+放量强阳"合成票
    n = 60
    close = [10.0] * 40 + [10.0, 10.1, 11.2, 11.3, 11.4] + [12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 24, 25, 26]
    vol = [1000.0] * 42 + [3000.0] + [1000.0] * (n - 43)
    to = [0.02] * n; to[42] = 0.09
    frame = {"date": [f"d{i:02d}" for i in range(n)], "open": close, "high": [c*1.01 for c in close],
             "low": [c*0.99 for c in close], "close": close, "volume": vol, "turnover": to}
    feat = compute_features(frame, 44, cfg)
    meta = {"mktcap_yi": 88.0, "pe_ttm": 55.0, "ai": {"tier": 2, "industry_ai": True, "hits": ["半导体", "算力"]},
            "growth": 0.8, "st": False, "event": {}}
    r = score_all(feat, meta, cfg)
    assert r["R0"][0] >= 4, f"放量强阳破前高应 R0≥4，实际 {r['R0']}"
    assert r["R2"][0] == 5, f"干净低位应 R2=5，实际 {r['R2']}"
    assert r["R4"][0] == 5, f"88亿应 R4=5，实际 {r['R4']}"
    assert r["R1"][0] == 5, f"AI+同比80%应 R1=5，实际 {r['R1']}"
    assert 1 <= r["composite"] <= 5
    assert 1 <= r["composite_v2"] <= 5
    w2 = cfg.get("weights_v2")
    if w2:
        assert abs(sum(w2.values()) - 1.0) < 1e-6, "weights_v2 权重和应=1"
        assert w2["R6"] == 0 and w2["R8"] == 0, "v2 应剔除哑规则"
    # ST 一票否决
    meta2 = dict(meta, st=True)
    assert score_all(feat, meta2, cfg)["composite"] <= 2, "ST 应封顶2"
    # 过热票 R2=1
    close_hot = [10.0]*15 + [10+0.5*i for i in range(20)] + [19.5]*10 + [20,21,22,23,24,25,26,27,28,30,32,34,36,38,40]
    frame_hot = {"date":[f"d{i}" for i in range(len(close_hot))],"open":close_hot,"high":[c*1.01 for c in close_hot],
                 "low":[c*0.99 for c in close_hot],"close":close_hot,"volume":[2000.0]*len(close_hot),"turnover":[0.05]*len(close_hot)}
    fh = compute_features(frame_hot, len(close_hot)-16, cfg)
    if fh:
        assert score_R2(fh, cfg)[0] <= 2, f"启动前大涨应 R2≤2，实际 {score_R2(fh,cfg)}"
    print("score 自检通过 ✓ ", {k: v[0] for k, v in r.items() if k in RULES}, "综合", r["composite"])
    print("  说明:", r["评分说明"])
