"""R1 主线内强度 · 单票/多票即时查 + 全市场板块内强度前排名单。

R1 语义 = "这只票在不在 AI 主线白名单里,在的话它的 20 日涨幅在板块内排第几"。
把旧 R1=R3 的二值门(在白名单=5/不在=1)拆成 5 档,rank 当"主线兑现度"的市场代理:
主线的钱如果真在兑现,会先落在板块内被资金选中的强势票上。

分档: 1=非白名单 | 2=板块内rank<0.33(主线掉队者,反面信号) | 3=0.33~0.66 |
      4=0.66~0.93 | 5=rank>=0.93(板块内前7%,主线兑现正落在这只票上)

它是状态排序不是扳机——动手仍看 R0/R9;定版与回测同源:扫描器仓 r1_mainline.py
(2026-07-07 十轮迭代,5分 hit10=41.7%/hit20=21.0%,白名单前视上界)。
注意:rank 要在全板块内算,单票查询也需要本地行情仓(r0-data 建仓),没有联网兜底。
"""
from __future__ import annotations
import argparse
import datetime as dt
import os
import sys

import store
from r7 import _name_map, resolve

HERE = os.path.dirname(os.path.abspath(__file__))

RET_N = 20
STRONG_RANK = 0.93
TIER_CUTS = ((0.93, 5), (0.66, 4), (0.33, 3), (-1.0, 2))
COHORT_EXCLUDES = ("bj", "sh688")  # 回测口径:板块与排名都不含北交所/688


def load_whitelist():
    codes = set()
    for line in open(os.path.join(HERE, "ai_tickers.txt"), encoding="utf-8"):
        t = line.strip()
        if t and not t.startswith("#"):
            codes.add(t[:6])
    return codes


def tier_from_rank(r):
    for cut, tier in TIER_CUTS:
        if r >= cut:
            return tier
    return 2


def rank_of(value, values):
    """value 在 values 里的百分位(<=占比,同 pandas pct rank 的近似)。"""
    return sum(1 for v in values if v <= value) / len(values) if values else 0.0


def build_cohort():
    """本地仓里所有白名单成员的 20 日涨幅(只取数据最新日与全仓最新日一致的票,保证同日排名)。
    返回 ({sym: ret20}, data_max);仓为空返回 (None, None)。"""
    syms = store.list_symbols()
    if not syms:
        return None, None
    wl = load_whitelist()
    raw = {}
    for sym in syms:
        if sym.startswith(COHORT_EXCLUDES) or sym[2:] not in wl:
            continue
        frame = store.load_frame(sym)
        if not frame or len(frame["close"]) < RET_N + 1:
            continue
        c = frame["close"]
        raw[sym] = (frame["date"][-1], c[-1] / c[-RET_N - 1] - 1)
    if not raw:
        return None, None
    data_max = max(d for d, _ in raw.values())
    cohort = {s: r for s, (d, r) in raw.items() if d == data_max}
    return cohort, data_max


def describe(sym, cohort, data_max, c2n):
    name = c2n.get(sym, "")
    if sym.startswith(COHORT_EXCLUDES):
        return None, f"✗ {sym} {name}：北交所/科创板688 不在 R1 回测口径内，不打分"
    if sym[2:] not in load_whitelist():
        return 1, f"R1=1  {sym} {name}  非 AI 白名单成员(主线门槛没过,与板块内强弱无关)"
    if sym not in cohort:
        return None, (f"✗ {sym} {name}：白名单成员但当日板块排名缺数据"
                      f"(停牌/数据不新鲜,仓最新日 {data_max})——跑 r0-data 增量后重试")
    vals = list(cohort.values())
    r = rank_of(cohort[sym], vals)
    tier = tier_from_rank(r)
    label = {5: "板块内前7%,主线兑现正落在这只票上", 4: "板块内偏强",
             3: "板块内中游", 2: "板块内弱,主线掉队者(反面信号)"}[tier]
    return tier, (f"R1={tier}  {sym} {name}  20日涨幅{cohort[sym]*100:+.1f}% "
                  f"板块内rank {r:.2f}(第{(1-r)*100:.0f}名百分位) {label}"
                  f"｜板块{len(vals)}只,数据截至{data_max}")


def cmd_today(min_score):
    cohort, data_max = build_cohort()
    if cohort is None:
        print(f"本地仓为空（{store.STORE}）。先建仓： python3 store.py backfill --days 400", file=sys.stderr)
        sys.exit(1)
    c2n, _ = _name_map()
    vals = list(cohort.values())
    rows = []
    for sym, ret in cohort.items():
        r = rank_of(ret, vals)
        tier = tier_from_rank(r)
        if tier >= min_score:
            rows.append((r, tier, sym, c2n.get(sym, ""), ret))
    rows.sort(key=lambda x: -x[0])
    print(f"# 主线内强度前排（R1≥{min_score}）名单（板块{len(vals)}只，数据截至 {data_max}，共 {len(rows)} 只）")
    print("# 状态排序不是买点;白名单是当前名单(有前视),数字当上界读\n")
    for r, tier, sym, name, ret in rows:
        print(f"{tier}  {sym} {name:<6}  rank {r:.2f}  20日{ret*100:+.1f}%")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("tickers", nargs="*", help="名称或代码，可多只")
    ap.add_argument("--today", action="store_true", help="列出板块内强度前排(R1≥min)")
    ap.add_argument("--min", type=int, default=5, help="--today 的分数门槛，默认5")
    args = ap.parse_args()

    if args.today:
        cmd_today(args.min)
        return
    if not args.tickers:
        ap.print_help()
        return

    cohort, data_max = build_cohort()
    if cohort is None:
        print(f"本地仓为空（{store.STORE}）。R1 的排名要全板块数据,没有联网兜底——先用 r0-data 建仓", file=sys.stderr)
        sys.exit(1)
    c2n, n2c = _name_map()
    for tok in args.tickers:
        sym = resolve(tok, n2c)
        if not sym:
            print(f"✗ {tok}：解析不出代码（名称歧义或本地无票名快照，请给6位代码）")
            continue
        _, desc = describe(sym, cohort, data_max, c2n)
        print(desc)


if __name__ == "__main__" and len(sys.argv) == 1:
    # 纯函数自检(不碰本地仓)
    assert tier_from_rank(0.95) == 5 and tier_from_rank(0.93) == 5
    assert tier_from_rank(0.80) == 4 and tier_from_rank(0.50) == 3 and tier_from_rank(0.10) == 2
    vals = [0.30, 0.10, 0.00, -0.05]
    assert rank_of(0.30, vals) == 1.0 and tier_from_rank(rank_of(0.30, vals)) == 5
    assert rank_of(-0.05, vals) == 0.25 and tier_from_rank(rank_of(-0.05, vals)) == 2
    assert rank_of(0.10, vals) == 0.75
    wl = load_whitelist()
    assert len(wl) > 1000 and all(len(c) == 6 for c in wl), "白名单快照应为6位代码"
    print(f"r1 自检通过 ✓  白名单快照 {len(wl)} 只")
    sys.exit(0)

if __name__ == "__main__":
    main()
