"""数据抓取（插件自带版，扫描器 fetch.py 的 R0 裁剪：只留票池 + 日K）。
数据源 sina（akshare）：到处能通、字段全（含每根换手）。
数据目录 = $R0_DATA_DIR，缺省 ~/.r0-data —— 数据永远在用户本地，不进插件。
"""
from __future__ import annotations
import os, time
import pandas as pd

# 注意：不在 import 时 makedirs——坏软链/只读路径会让纯读命令(stat/自检)都起不来。写缓存前再建。
DATA = os.path.expanduser(os.environ.get("R0_DATA_DIR") or "~/.r0-data")


def get_universe(cfg=None, limit=None):
    """全A股 [(symbol, name)]，symbol 形如 sh688146/sz000001/bj920000。剔 ST/退市。
    需要网络（sina 全A实时列表，偶尔被限流——限流时用 get_universe_offline 回退）。"""
    import akshare as ak
    drop_st = True if cfg is None else bool(cfg["universe"].get("drop_st", True))
    df = ak.stock_zh_a_spot()
    rows = []
    for _, r in df.iterrows():
        sym, name = str(r["代码"]), str(r["名称"])
        if drop_st and is_st(name):
            continue
        if "退" in name:
            continue
        rows.append((sym, name))
    if limit:
        rows = rows[:limit]
    return rows


def get_universe_offline(limit=None):
    """离线回退：本地仓票列表 + universe.csv 里的名称（backfill 时保存的快照）。"""
    names = {}
    up = os.path.join(DATA, "universe.csv")
    if os.path.exists(up):
        try:
            d = pd.read_csv(up)
            names = dict(zip(d["code"].astype(str), d["name"].astype(str)))
        except Exception:
            pass
    if not os.path.isdir(DATA):
        return []
    uni = [(f[:-8], names.get(f[:-8], "")) for f in sorted(os.listdir(DATA)) if f.endswith(".parquet")]
    if limit:
        uni = uni[:limit]
    return uni


def _norm_kline(df):
    """sina_daily → 归一化 {date,open,high,low,close,volume,turnover}(list)。turnover 为分数。"""
    df = df.sort_values("date").reset_index(drop=True)
    return {
        "date": [str(x)[:10] for x in df["date"]],
        "open": df["open"].astype(float).tolist(),
        "high": df["high"].astype(float).tolist(),
        "low": df["low"].astype(float).tolist(),
        "close": df["close"].astype(float).tolist(),
        "volume": df["volume"].astype(float).tolist(),
        "turnover": df["turnover"].astype(float).tolist(),
    }


def get_kline(symbol, start_date, end_date, use_cache=True):
    """归一化日K（后复权 hfq，与本地仓同口径）；抓不到返回 None。命中本地仓/缓存则不碰网络。"""
    import akshare as ak
    cf = os.path.join(DATA, f"{symbol}.parquet")
    if use_cache and os.path.exists(cf):
        try:
            df = pd.read_parquet(cf)
            if str(df["date"].max())[:10] >= end_date:
                sub = df[(df["date"].astype(str) >= start_date) & (df["date"].astype(str) <= end_date)]
                if len(sub) > 5:
                    return _norm_kline(sub)
        except Exception:
            pass
    for attempt in range(3):
        try:
            df = ak.stock_zh_a_daily(symbol=symbol, start_date=start_date.replace("-", ""),
                                     end_date=end_date.replace("-", ""), adjust="hfq")
            if df is None or len(df) < 6:
                return None
            df["date"] = df["date"].astype(str).str[:10]
            try:
                os.makedirs(DATA, exist_ok=True)
                df.to_parquet(cf)
            except Exception:
                pass
            return _norm_kline(df)
        except Exception:
            time.sleep(0.4 * (attempt + 1))
    return None


def is_st(name):
    return "ST" in name or "st" in name
