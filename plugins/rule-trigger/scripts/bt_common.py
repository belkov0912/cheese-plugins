"""backtest_r0.py / backtest_r7.py 共用的纯工具函数：结果标签、IC、分桶、精度召回。
协议口径（两边必须一致，改这里等于同时改两个回测）：
- 结果标签 = 锚点后 outcome_len 根内最大收盘涨幅（收盘口径，不用盘中高点）。
- IC = 每窗口内 分数 vs outcome_ret 的 Spearman 秩相关。
- 默认 universe 排除 bj* 和 sh688*（与 r7.py --today 一致）。
"""
from __future__ import annotations


def is_bj688(sym):
    return sym.startswith(("bj", "sh688"))


def outcome_return(frame, anchor_idx, outcome_len):
    close = frame["close"]
    if anchor_idx + outcome_len >= len(close):
        return None
    base = close[anchor_idx]
    fwd = close[anchor_idx + 1: anchor_idx + 1 + outcome_len]
    return max(fwd) / base - 1 if base and fwd else None


def safe_ic(df, col):
    if col not in df.columns or df[col].nunique(dropna=True) < 2:
        return float("nan")
    return df[[col, "outcome_ret"]].corr(method="spearman").iloc[0, 1]


def fmt_pct(x):
    return "—" if x != x else f"{x * 100:.1f}%"


def fmt_num(x, nd=2):
    return "—" if x != x else f"{x:.{nd}f}"


def bucket_table(df, rule, theta):
    hit = (df["outcome_ret"] >= theta).astype(int)
    g = hit.groupby(df[rule]).agg(["size", "mean"])
    rows = []
    for s in range(1, 6):
        if s in g.index:
            rows.append((s, int(g.loc[s, "size"]), float(g.loc[s, "mean"])))
        else:
            rows.append((s, 0, float("nan")))
    return rows


def coverage_precision(df, rule, theta, min_score=4):
    sel = df[rule] >= min_score
    hit = df["outcome_ret"] >= theta
    winners = int(hit.sum())
    selected = int(sel.sum())
    selected_hits = int((sel & hit).sum())
    precision = selected_hits / selected if selected else float("nan")
    recall = selected_hits / winners if winners else float("nan")
    coverage = selected / len(df) if len(df) else float("nan")
    return selected, selected_hits, precision, recall, coverage


def summary_rows(windows, rules):
    out = []
    for rname, col in rules:
        ics = [safe_ic(w["df"], col) for w in windows]
        good = [x for x in ics if x == x]
        mean_ic = sum(good) / len(good) if good else float("nan")
        out.append({
            "rule": rname,
            "mean_ic": mean_ic,
            "ic_positive": sum(1 for x in good if x > 0),
            "ic_windows": len(good),
            "ics": ics,
        })
    return out
