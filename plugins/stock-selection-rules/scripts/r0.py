"""R0 启动扳机 · 单票/多票即时查 + 今日全市场名单（skill r0-breakout 的后端，插件自带）。
复用扫描器同源的 features/score 管线，取最后一根K线给 R0 打 1-5 分 + 证据化描述。
R0 语义 = "判定窗 J（最近5个交易日）里最强的启动确认K线有多强"，一次打分即回答"过去5天扣没扣扳机"。

数据目录 = $R0_DATA_DIR，缺省 ~/.r0-data（先用 store.py backfill 建仓；没建仓时单票会自动联网现抓）。

用法：
  python3 r0.py 景旺电子 603228 sz300476     # 逐票报 R0（名称或代码都行）
  python3 r0.py --today                        # 扫本地仓，列出今日 R0≥4 的票（默认排除 bj* / sh688*）
  python3 r0.py --today --min 5                # 只看 R0=5
  python3 r0.py --today --include-bj688        # 包含北交所和科创板 688
诚实边界见 skill：R0 是"候选池里的票扣扳机"，不是选股信号；IC 仅 +0.07、满分票八成也不涨。
"""
from __future__ import annotations
import os, sys, argparse
import yaml
import store, features, score, fetch

HERE = os.path.dirname(os.path.abspath(__file__))
DEFAULT_TODAY_EXCLUDES = ("bj", "sh688")


def _cfg():
    return yaml.safe_load(open(os.path.join(HERE, "rules_config.yaml"), encoding="utf-8"))


def _name_map():
    """universe.csv（backfill 时保存）的 code→name / name→code；只为解析用户输入。"""
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
    """名称或代码 → sina 符号(sh/sz/bj+6位)。解析不出返回 None。"""
    t = token.strip()
    if t[:2].lower() in ("sh", "sz", "bj") and t[2:].isdigit():
        return t.lower()
    if t.isdigit() and len(t) == 6:
        pref = "sh" if t[0] == "6" else ("bj" if t[0] in "489" else "sz")
        return pref + t
    if t in n2c:                       # 精确名
        return n2c[t]
    hit = [c for n, c in n2c.items() if t in n]   # 模糊名
    return hit[0] if len(hit) == 1 else None


def _r0_of(frame, cfg):
    """一个归一化K线 dict → (tier, desc)；数据不足返回 (None, 原因)。"""
    if not frame or len(frame["date"]) < 50:
        return None, "数据不足(<50根K线，次新或停牌)"
    feat = features.compute_features(frame, len(frame["date"]) - 1, cfg)
    if feat is None:
        return None, "历史不足以算特征"
    return score.score_R0(feat, cfg)


def _is_default_today_excluded(sym):
    """--today 默认剔除北交所和科创板688；单票查询不受影响。"""
    return sym.startswith(DEFAULT_TODAY_EXCLUDES)


def score_one(sym, cfg):
    """(tier, desc)。仓里没有就 live 抓一次（约需网络几秒）。
    live 现抓同样只取到上一个收盘（走 store._data_end_date 的 15:05 北京时间保护）——
    否则盘中的半根K线会进打分、还会被缓存进数据仓当天不自愈。"""
    import datetime as dt
    frame = store.load_frame(sym)
    if not frame:
        end = store._data_end_date()
        start = (dt.date.fromisoformat(end) - dt.timedelta(days=150)).isoformat()
        frame = fetch.get_kline(sym, start, end)
        if not frame:
            return None, "联网现抓失败：网络不通/被 sina 限流/代码不存在（三种都长这样）。稍后再试，或先用 r0-data 建仓走本地"
    tier, desc = _r0_of(frame, cfg)
    if tier is not None:
        last = frame["date"][-1]
        if last < (dt.date.fromisoformat(store._data_end_date()) - dt.timedelta(days=15)).isoformat():
            desc += f" ⚠数据止于{last}（疑似停牌，或本地仓太久没更新——跑 r0-data 增量）"
    return tier, desc


def _scan_today(score_frame, min_score, include_bj688, heading):
    """R0/R7/R9 共用的本地全仓扫描与过旧数据过滤。"""
    import datetime as dt
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
        tier, desc = score_frame(frame)[:2]
        if tier is not None and tier >= min_score:
            rows.append((tier, sym, c2n.get(sym, ""), desc, frame["date"][-1]))
    if not lasts:
        print("本地仓文件全部读不出来（多半缺 pyarrow 或文件损坏）", file=sys.stderr)
        sys.exit(1)
    data_max = max(lasts)   # 全仓真实数据水位，不拿任意一只票充数
    stale_cut = (dt.date.fromisoformat(data_max) - dt.timedelta(days=15)).isoformat()
    stale_n = sum(1 for r in rows if r[4] < stale_cut)
    rows = [r for r in rows if r[4] >= stale_cut]   # 停牌/久未更新的票：J窗是旧的，不该挂在名单里
    rows.sort(key=lambda r: (-r[0], r[1]))
    notes = []
    if not include_bj688:
        notes.append(f"默认排除 bj*/sh688* {excluded} 只")
    if stale_n:
        notes.append(f"另剔除 {stale_n} 只停牌/数据过旧票")
    note = "；" + "；".join(notes) if notes else ""
    print(f"# {heading}（数据截至 {data_max}，共 {len(rows)} 只{note}）\n")
    for tier, sym, name, desc, _ in rows:
        print(f"{tier}  {sym} {name:<6}  {desc}")


def cmd_today(min_score, cfg, include_bj688=False):
    _scan_today(lambda frame: _r0_of(frame, cfg), min_score, include_bj688,
                f"最近5个交易日内扣过扳机（R0≥{min_score}）的名单")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("tickers", nargs="*", help="名称或代码，可多只")
    ap.add_argument("--today", action="store_true", help="扫本地仓列出今日 R0≥min 的票")
    ap.add_argument("--min", type=int, default=4, help="--today 的分数门槛，默认4")
    ap.add_argument("--include-bj688", action="store_true", help="--today 时包含 bj* 和 sh688*（默认排除）")
    args = ap.parse_args()
    cfg = _cfg()

    if args.today:
        cmd_today(args.min, cfg, include_bj688=args.include_bj688)
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
        tier, desc = score_one(sym, cfg)
        name = c2n.get(sym, "")
        if tier is None:
            print(f"✗ {sym} {name}：{desc}")
        else:
            print(f"R0={tier}  {sym} {name}  {desc}")


# ---------------- 自检（无参运行时触发，不碰网络） ----------------
if __name__ == "__main__" and len(sys.argv) == 1:
    from contextlib import redirect_stdout, redirect_stderr
    from io import StringIO
    from unittest.mock import patch

    cfg = _cfg()
    # 代码解析
    assert resolve("sh603228", {}) == "sh603228"
    assert resolve("603228", {}) == "sh603228"
    assert resolve("300476", {}) == "sz300476"
    assert resolve("920819", {}) == "bj920819"
    assert resolve("不存在的鬼票xyz", {}) is None
    assert _is_default_today_excluded("bj920510")
    assert _is_default_today_excluded("sh688017")
    assert not _is_default_today_excluded("sh603228")
    assert not _is_default_today_excluded("sz300476")
    # 共用全仓扫描：排除 688，并剔除相对全仓水位过旧的命中票。
    fake = {"sz000001": {"date": ["2026-07-09"]}, "sh688001": {"date": ["2026-07-09"]},
            "sz000002": {"date": ["2026-06-01"]}}
    output = StringIO()
    with patch.object(store, "list_symbols", return_value=list(fake)), \
         patch.object(store, "load_frame", side_effect=fake.get), \
         patch(__name__ + "._name_map", return_value=({"sz000001": "平安银行"}, {})), \
         redirect_stdout(output), redirect_stderr(StringIO()):
        _scan_today(lambda frame: (5, "命中", {}), 4, False, "测试名单")
    assert "共 1 只" in output.getvalue() and "sz000001 平安银行" in output.getvalue()
    assert "sh688001" not in output.getvalue() and "sz000002" not in output.getvalue()
    # 合成K线：横盘40根 → 最后一根放量强阳破前高 → 应扣扳机 R0≥4
    n = 56
    close = [10.0] * 55 + [10.9]
    vol = [1000.0] * 55 + [3000.0]
    to = [0.03] * 55 + [0.09]
    frame = {"date": [f"d{i:02d}" for i in range(n)], "open": close, "high": [c * 1.01 for c in close],
             "low": [c * 0.99 for c in close], "close": close, "volume": vol, "turnover": to}
    tier, desc = _r0_of(frame, cfg)
    assert tier is not None and tier >= 4, f"放量强阳破前高应 R0≥4，实际 {tier} {desc}"
    # 数据不足
    tier2, _ = _r0_of({"date": ["d0"] * 10, "open": [1] * 10, "high": [1] * 10, "low": [1] * 10,
                       "close": [1] * 10, "volume": [1] * 10, "turnover": [0.01] * 10}, cfg)
    assert tier2 is None
    # 本地仓有票的话，顺手跑一只真的
    syms = store.list_symbols()
    if syms:
        t3, d3 = score_one(syms[0], cfg)
        print(f"r0 自检通过 ✓  合成票 R0={tier}；真票 {syms[0]} → R0={t3} | {d3}")
    else:
        print(f"r0 自检通过 ✓  合成票 R0={tier}（本地仓为空，跳过真票；建仓见 store.py）")
    sys.exit(0)

if __name__ == "__main__":
    main()
