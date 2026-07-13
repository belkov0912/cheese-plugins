#!/usr/bin/env python3
"""Freeze point-in-time A-share evidence from trades and one-minute bars.

The minute-bar CSV must label a bar by its end time. For a fill at T, the
script only retains bars whose timestamp is strictly earlier than floor(T, 1m),
therefore it never uses the fill minute or anything after it.
"""

import argparse
import json
import os
import sys
from pathlib import Path

import pandas as pd

from trade_context import normalize_code, read_universe, stock_context


TRADE_COLUMNS = {"datetime", "code", "side", "price", "quantity", "market_symbol"}
BAR_COLUMNS = {"symbol", "datetime", "open", "high", "low", "close", "volume"}


def parse_args():
    parser = argparse.ArgumentParser(description="Freeze trade-time minute data without lookahead.")
    parser.add_argument("--trades", required=True, help="CSV: datetime,code,side,price,quantity,market_symbol; optional sector_symbol")
    parser.add_argument("--minute-bars", required=True, help="CSV: symbol,datetime,open,high,low,close,volume; optional amount,prev_close")
    parser.add_argument("--previous-session", required=True, help="Expected prior A-share session, YYYY-MM-DD")
    parser.add_argument("--data-dir", default=os.environ.get("R0_DATA_DIR", "~/.r0-data"))
    parser.add_argument("--format", choices=("md", "json"), default="md")
    parser.add_argument("--allow-incomplete", action="store_true")
    return parser.parse_args()


def parse_datetime(value):
    series = pd.to_datetime(pd.Series([value]), errors="coerce")
    if series.isna().iloc[0]:
        return pd.NaT
    timestamp = series.iloc[0]
    if getattr(timestamp, "tzinfo", None) is not None:
        timestamp = timestamp.tz_convert("Asia/Shanghai").tz_localize(None)
    return timestamp


def normalize_symbol(value):
    raw = str(value).strip().lower()
    try:
        return normalize_code(raw)
    except ValueError:
        return raw


def pct(current, prior, digits=2):
    if current is None or prior is None or pd.isna(current) or pd.isna(prior) or prior == 0:
        return None
    return round((float(current) / float(prior) - 1) * 100, digits)


def parse_trades(path):
    trades = pd.read_csv(path, dtype={"code": str})
    missing = TRADE_COLUMNS - set(trades.columns)
    if missing:
        raise ValueError("交割单缺列: " + ", ".join(sorted(missing)))
    trades = trades.copy()
    trades["datetime"] = trades["datetime"].map(parse_datetime)
    if trades["datetime"].isna().any():
        raise ValueError("交割单存在无法解析的 datetime")
    for column in ("price", "quantity"):
        trades[column] = pd.to_numeric(trades[column], errors="coerce")
    if trades[["price", "quantity"]].isna().any().any():
        raise ValueError("交割单的 price 或 quantity 不是数字")
    try:
        trades["symbol"] = trades["code"].map(normalize_code)
    except ValueError as exc:
        raise ValueError(str(exc))
    return trades.sort_values("datetime").reset_index(drop=True)


def parse_bars(path):
    bars = pd.read_csv(path, dtype={"symbol": str})
    missing = BAR_COLUMNS - set(bars.columns)
    if missing:
        raise ValueError("一分钟数据缺列: " + ", ".join(sorted(missing)))
    bars = bars.copy()
    bars["symbol"] = bars["symbol"].map(normalize_symbol)
    bars["datetime"] = bars["datetime"].map(parse_datetime)
    if bars["datetime"].isna().any():
        raise ValueError("一分钟数据存在无法解析的 datetime")
    for column in BAR_COLUMNS - {"symbol", "datetime"}:
        bars[column] = pd.to_numeric(bars[column], errors="coerce")
    for column in ("amount", "prev_close"):
        if column in bars.columns:
            bars[column] = pd.to_numeric(bars[column], errors="coerce")
    return bars.dropna(subset=["open", "high", "low", "close", "volume"]).sort_values("datetime")


def point_snapshot(bars, symbol, trade_time):
    if not symbol:
        return {"status": "not_supplied"}
    cutoff = trade_time.floor("min")
    visible = bars[(bars["symbol"] == normalize_symbol(symbol)) & (bars["datetime"] < cutoff)].copy()
    visible = visible[visible["datetime"].dt.date == trade_time.date()]
    if len(visible) < 2:
        return {
            "status": "insufficient",
            "reason": "成交前少于两根完整一分钟K",
            "cutoff_exclusive": cutoff.strftime("%Y-%m-%d %H:%M"),
            "bars_used": len(visible),
        }

    latest = float(visible["close"].iloc[-1])
    first_open = float(visible["open"].iloc[0])
    high = float(visible["high"].max())
    low = float(visible["low"].min())
    vwap = None
    vwap_method = None
    if visible["volume"].sum() > 0:
        typical = (visible["high"] + visible["low"] + visible["close"]) / 3
        estimated_vwap = float((typical * visible["volume"]).sum() / visible["volume"].sum())
        vwap = estimated_vwap
        vwap_method = "分钟典型价按成交量加权"
        if "amount" in visible.columns and visible["amount"].notna().all():
            raw_vwap = float(visible["amount"].sum() / visible["volume"].sum())
            median_price = float(visible["close"].median())
            if median_price > 0 and 0.5 <= raw_vwap / median_price <= 2:
                vwap = raw_vwap
                vwap_method = "成交额/成交量"
            elif median_price > 0 and 0.5 <= (raw_vwap / 100) / median_price <= 2:
                vwap = raw_vwap / 100
                vwap_method = "成交额/(成交量×100)"
    position = None if high <= low else round((latest - low) / (high - low) * 100, 1)
    ret_5m = pct(latest, float(visible["close"].iloc[-6])) if len(visible) >= 6 else None
    return {
        "status": "ready",
        "cutoff_exclusive": cutoff.strftime("%Y-%m-%d %H:%M"),
        "bars_used": int(len(visible)),
        "last_complete_bar": visible["datetime"].iloc[-1].strftime("%Y-%m-%d %H:%M"),
        "change_from_open_pct": pct(latest, first_open),
        "vwap": round(vwap, 4) if vwap is not None else None,
        "vwap_method": vwap_method,
        "distance_vwap_pct": pct(latest, vwap),
        "change_from_prev_close_pct": (
            pct(latest, float(visible["prev_close"].dropna().iloc[0]))
            if "prev_close" in visible.columns and visible["prev_close"].notna().any() else None
        ),
        "opening_gap_pct": (
            pct(first_open, float(visible["prev_close"].dropna().iloc[0]))
            if "prev_close" in visible.columns and visible["prev_close"].notna().any() else None
        ),
        "position_in_visible_range_pct": position,
        "drawdown_from_visible_high_pct": pct(latest, high),
        "return_5m_pct": ret_5m,
        "visible_high": round(high, 4),
        "visible_low": round(low, 4),
    }


def row_value(row, column, default=None):
    value = row[column] if column in row.index else default
    return default if pd.isna(value) else value


def review_one(row, bars, data_dir, names, previous_session):
    trade_time = row["datetime"]
    symbol = row["symbol"]
    daily = stock_context(symbol, names.get(symbol), data_dir, trade_time.normalize(), previous_session)
    stock = point_snapshot(bars, symbol, trade_time)
    if stock["status"] == "ready":
        fill_price = float(row["price"])
        visible_high = stock["visible_high"]
        visible_low = stock["visible_low"]
        stock["fill_distance_vwap_pct"] = pct(fill_price, stock["vwap"])
        stock["fill_vs_visible_high_pct"] = pct(fill_price, visible_high)
        stock["fill_position_in_visible_range_pct"] = (
            None if visible_high <= visible_low
            else round((fill_price - visible_low) / (visible_high - visible_low) * 100, 1)
        )
    market = point_snapshot(bars, row_value(row, "market_symbol"), trade_time)
    sector = point_snapshot(bars, row_value(row, "sector_symbol"), trade_time)
    intraday_ready = stock["status"] == "ready"
    market_ready = market["status"] == "ready"
    sector_ready = sector["status"] == "ready"
    daily_ready = daily["status"] == "ready"
    if daily_ready and intraday_ready and market_ready and sector_ready:
        status = "ready"
    elif daily_ready and intraday_ready and market_ready:
        status = "partial"
    else:
        status = "incomplete"
    return {
        "status": status,
        "trade": {
            "datetime": trade_time.strftime("%Y-%m-%d %H:%M:%S"),
            "symbol": symbol,
            "name": names.get(symbol, symbol),
            "side": str(row["side"]),
            "price": float(row["price"]),
            "quantity": float(row["quantity"]),
        },
        "visibility": {
            "minute_timestamp_semantics": "分钟K必须以分钟结束时间标记；成交所在分钟和之后的K已排除",
            "no_lookahead": "日线仅使用交易日前数据；分时仅使用严格早于成交分钟的数据",
        },
        "daily_context": daily,
        "stock_intraday": stock,
        "market_intraday": market,
        "sector_intraday": sector,
    }


def markdown(reviews):
    lines = ["# 成交时点快照（严格无后视）", ""]

    def append_intraday(label, snapshot):
        if snapshot["status"] == "ready":
            detail = ""
            if snapshot.get("fill_distance_vwap_pct") is not None:
                detail = "；成交价相对当时VWAP %s%%，位于成交前可见区间 %s%%" % (
                    snapshot["fill_distance_vwap_pct"], snapshot["fill_position_in_visible_range_pct"]
                )
            lines.append("- %s：截至 %s，%s 根完整一分钟K；相对开盘 %s%%，相对当时VWAP %s%%，可见区间位置 %s%%%s。" % (
                label, snapshot["cutoff_exclusive"], snapshot["bars_used"], snapshot["change_from_open_pct"],
                snapshot["distance_vwap_pct"], snapshot["position_in_visible_range_pct"], detail
            ))
        else:
            lines.append("- %s：`%s`，%s。" % (label, snapshot["status"], snapshot.get("reason", "未提供")))

    for item in reviews:
        trade = item["trade"]
        lines.extend(["## %s %s" % (trade["name"], trade["side"]), ""])
        lines.append("- 成交：%s，%s，%s × %s。" % (trade["datetime"], trade["symbol"], trade["price"], trade["quantity"]))
        lines.append("- 复盘状态：`%s`。" % item["status"])
        daily = item["daily_context"]
        lines.append("- 日线：`%s`，数据截止 %s，趋势 %s。" % (
            daily["status"], daily.get("data_cutoff", "无"), daily.get("trend_state", "无")
        ))
        append_intraday("个股分时", item["stock_intraday"])
        append_intraday("大盘分时", item["market_intraday"])
        append_intraday("行业分时", item["sector_intraday"])
        lines.append("")
    return "\n".join(lines)


def main():
    args = parse_args()
    try:
        previous_session = pd.Timestamp(args.previous_session).normalize()
        trades = parse_trades(args.trades)
        bars = parse_bars(args.minute_bars)
    except Exception as exc:
        print(str(exc), file=sys.stderr)
        return 2

    data_dir = Path(args.data_dir).expanduser()
    if not data_dir.exists():
        print("数据目录不存在：%s" % data_dir, file=sys.stderr)
        return 2
    names = read_universe(data_dir)
    reviews = [review_one(row, bars, data_dir, names, previous_session) for _, row in trades.iterrows()]

    if args.format == "json":
        print(json.dumps(reviews, ensure_ascii=False, indent=2))
    else:
        print(markdown(reviews))

    if any(item["status"] != "ready" for item in reviews) and not args.allow_incomplete:
        print("至少一笔交易缺少合格的交易前日线或成交前分钟数据，拒绝给出完整时点评价。", file=sys.stderr)
        return 3
    return 0


if __name__ == "__main__":
    sys.exit(main())
