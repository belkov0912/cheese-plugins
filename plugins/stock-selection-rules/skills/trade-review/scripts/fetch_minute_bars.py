#!/usr/bin/env python3
"""下载指定交易日的一分钟K（新浪源，经 akshare），写成 trade_snapshot.py 的 minute-bars.csv。

新浪一分钟接口只保留最近约 8 个交易日、未复权价，时间戳为分钟结束时刻
（当日首根 09:31:00），与 trade_snapshot.py 的口径一致。超出保留窗口的
交易日会被报告为缺口，此时按 SKILL.md 回落到截图推断模式。
"""

import argparse
import sys
import time

import pandas as pd

from trade_context import normalize_code


DEFAULT_INDICES = "sh000001,sz399001,sz399006"


def parse_args():
    parser = argparse.ArgumentParser(description="Fetch one-minute bars for a trade date via sina (akshare).")
    parser.add_argument("--codes", required=True, help="逗号分隔：6 位代码或 sh/sz/bj 前缀代码；指数和 ETF 必须带前缀")
    parser.add_argument("--date", required=True, help="交易日 YYYY-MM-DD")
    parser.add_argument("--out", required=True, help="输出 CSV 路径")
    parser.add_argument("--indices", default=DEFAULT_INDICES, help="附带下载的指数，默认上证/深证/创业板；传空串跳过")
    parser.add_argument("--retries", type=int, default=3)
    return parser.parse_args()


def to_symbols(raw, label):
    symbols = []
    for item in raw.split(","):
        item = item.strip().lower()
        if not item:
            continue
        try:
            symbols.append(normalize_code(item))
        except ValueError as exc:
            print("%s：%s" % (label, exc), file=sys.stderr)
            sys.exit(2)
    return symbols


def fetch_one(symbol, retries):
    import akshare as ak

    for attempt in range(retries):
        try:
            df = ak.stock_zh_a_minute(symbol=symbol, period="1")
            if df is not None and len(df):
                return df
        except Exception:
            pass
        time.sleep(1.2 * (attempt + 1))
    return None


def main():
    args = parse_args()
    try:
        import akshare  # noqa: F401
    except ImportError:
        print("需要 akshare（新浪分钟数据源）：pip install akshare，或设置 R0_REVIEW_PYTHON 指向已安装它的环境。", file=sys.stderr)
        return 2
    trade_date = str(pd.Timestamp(args.date).date())
    symbols = to_symbols(args.codes, "--codes") + to_symbols(args.indices, "--indices")
    symbols = list(dict.fromkeys(symbols))

    frames, report, gaps = [], [], []
    for symbol in symbols:
        raw = fetch_one(symbol, args.retries)
        if raw is None or raw.empty:
            report.append("%s: 接口无返回" % symbol)
            gaps.append(symbol)
            continue
        bars = raw.copy()
        bars["day"] = pd.to_datetime(bars["day"])
        for column in ("open", "high", "low", "close", "volume"):
            bars[column] = pd.to_numeric(bars[column], errors="coerce")
        if "amount" in bars.columns:
            bars["amount"] = pd.to_numeric(bars["amount"], errors="coerce")
        window_lo, window_hi = str(bars["day"].min()), str(bars["day"].max())
        day_mask = bars["day"].dt.strftime("%Y-%m-%d") == trade_date
        day_bars = bars[day_mask]
        if day_bars.empty:
            report.append("%s: %s 无数据（接口保留窗口 %s → %s；超窗或停牌）" % (symbol, trade_date, window_lo, window_hi))
            gaps.append(symbol)
            continue
        prior = bars[bars["day"].dt.strftime("%Y-%m-%d") < trade_date]
        prev_close = float(prior["close"].iloc[-1]) if len(prior) else None
        out = pd.DataFrame({
            "symbol": symbol,
            "datetime": day_bars["day"].dt.strftime("%Y-%m-%d %H:%M:%S"),
            "open": day_bars["open"],
            "high": day_bars["high"],
            "low": day_bars["low"],
            "close": day_bars["close"],
            "volume": day_bars["volume"],
            "amount": day_bars.get("amount"),
            "prev_close": prev_close,
        })
        frames.append(out)
        report.append("%s: %d 根，%s → %s，prev_close=%s" % (
            symbol, len(out), day_bars["day"].min().strftime("%H:%M"),
            day_bars["day"].max().strftime("%H:%M"), prev_close if prev_close is not None else "无",
        ))

    if frames:
        pd.concat(frames, ignore_index=True).to_csv(args.out, index=False)
        print("已写入 %s（%d 个代码）" % (args.out, len(frames)))
    for line in report:
        print("  " + line)
    if gaps:
        print("缺口：%s 拿不到 %s 的一分钟K，这些代码按 SKILL.md 回落到截图推断模式。" % ("、".join(gaps), trade_date), file=sys.stderr)
        return 3
    return 0


if __name__ == "__main__":
    sys.exit(main())
