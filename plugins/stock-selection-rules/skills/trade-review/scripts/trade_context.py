#!/usr/bin/env python3
"""Generate no-lookahead daily context for an A-share trade review.

The script deliberately excludes every daily bar on or after --trade-date.
It describes the daily backdrop available before the trade date; it does not
reconstruct intraday prices or judge the result of a trade.
"""

import argparse
import json
import os
import re
import sys
from datetime import datetime
from pathlib import Path

import pandas as pd


def parse_args():
    parser = argparse.ArgumentParser(
        description="Read r0-data strictly before a trade date and report daily trend context."
    )
    parser.add_argument("--trade-date", required=True, help="YYYY-MM-DD; this date is excluded")
    parser.add_argument(
        "--previous-session",
        help="Expected previous A-share trading day. Without it, freshness cannot be fully verified.",
    )
    parser.add_argument("--codes", required=True, help="Comma-separated codes, e.g. 603538,sz002156")
    parser.add_argument(
        "--data-dir",
        default=os.environ.get("R0_DATA_DIR", "~/.r0-data"),
        help="r0-data directory (default: $R0_DATA_DIR or ~/.r0-data)",
    )
    parser.add_argument("--format", choices=("md", "json"), default="md")
    parser.add_argument(
        "--allow-stale",
        action="store_true",
        help="Return success even if one or more stocks are stale or missing",
    )
    return parser.parse_args()


def normalize_code(raw):
    code = raw.strip().lower()
    if re.fullmatch(r"(?:sh|sz|bj)\d{6}", code):
        return code
    if not re.fullmatch(r"\d{6}", code):
        raise ValueError("股票代码必须是 6 位数字或 sh/sz/bj 加 6 位数字：%s" % raw)
    if code.startswith(("4", "8", "9")):
        return "bj" + code
    if code.startswith(("5", "6")):
        return "sh" + code
    return "sz" + code


def safe_number(value, digits=4):
    if value is None or pd.isna(value):
        return None
    return round(float(value), digits)


def percent_change(current, earlier):
    if current is None or earlier is None or earlier == 0:
        return None
    return safe_number((current / earlier - 1) * 100, 2)


def rolling_mean(series, window):
    if len(series) < window:
        return None
    return float(series.iloc[-window:].mean())


def return_n_days(close, n):
    if len(close) < n + 1:
        return None
    return percent_change(float(close.iloc[-1]), float(close.iloc[-(n + 1)]))


def trend_state(close, ma5, ma20, ma60):
    if None in (ma5, ma20, ma60):
        return "数据不足"
    if close >= ma5 >= ma20 and close >= ma60:
        return "偏强"
    if close <= ma5 <= ma20 and close <= ma60:
        return "偏弱"
    return "震荡/修复"


def range_position(frame, days, close):
    if len(frame) < days:
        return None
    window = frame.iloc[-days:]
    high = float(window["high"].max())
    low = float(window["low"].min())
    if high <= low:
        return None
    return safe_number((close - low) / (high - low) * 100, 1)


def read_universe(data_dir):
    path = data_dir / "universe.csv"
    if not path.exists():
        return {}
    universe = pd.read_csv(path, dtype=str)
    if not {"code", "name"}.issubset(universe.columns):
        return {}
    return dict(zip(universe["code"].str.lower(), universe["name"]))


def stock_context(code, name, data_dir, trade_date, previous_session=None):
    path = data_dir / (code + ".parquet")
    result = {
        "code": code,
        "name": name or code,
        "trade_date": trade_date.strftime("%Y-%m-%d"),
        "rule": "已排除 date >= 交易日 的所有日K",
    }
    if not path.exists():
        result.update(status="missing", reason="找不到 %s" % path.name)
        return result

    try:
        frame = pd.read_parquet(path)
    except Exception as exc:  # Report one stock without hiding other results.
        result.update(status="unreadable", reason=str(exc))
        return result

    required = {"date", "open", "high", "low", "close", "volume", "turnover"}
    missing = sorted(required - set(frame.columns))
    if missing:
        result.update(status="unreadable", reason="缺字段: " + ", ".join(missing))
        return result

    frame = frame.copy()
    frame["date"] = pd.to_datetime(frame["date"], errors="coerce").dt.normalize()
    for column in required - {"date"}:
        frame[column] = pd.to_numeric(frame[column], errors="coerce")
    frame = frame.dropna(subset=["date", "close"]).sort_values("date")

    future_rows = int((frame["date"] >= trade_date).sum())
    history = frame[frame["date"] < trade_date].copy()
    result["quarantined_rows"] = future_rows
    if history.empty:
        result.update(status="insufficient_history", reason="交易日前没有可用日K")
        return result

    last = history.iloc[-1]
    cutoff = last["date"]
    gap_days = int((trade_date - cutoff).days)
    result.update(
        data_cutoff=cutoff.strftime("%Y-%m-%d"),
        gap_calendar_days=gap_days,
        bars=len(history),
    )

    close = history["close"].reset_index(drop=True)
    ma5 = rolling_mean(close, 5)
    ma20 = rolling_mean(close, 20)
    ma60 = rolling_mean(close, 60)
    volume = history["volume"].reset_index(drop=True)
    turnover = history["turnover"].reset_index(drop=True)
    volume_base_5 = rolling_mean(volume.iloc[:-1], 5)
    turnover_base_5 = rolling_mean(turnover.iloc[:-1], 5)
    current_close = float(close.iloc[-1])

    result.update(
        trend_state=trend_state(current_close, ma5, ma20, ma60),
        return_5d_pct=return_n_days(close, 5),
        return_20d_pct=return_n_days(close, 20),
        return_60d_pct=return_n_days(close, 60),
        distance_ma5_pct=percent_change(current_close, ma5),
        distance_ma20_pct=percent_change(current_close, ma20),
        distance_ma60_pct=percent_change(current_close, ma60),
        range_position_20d_pct=range_position(history, 20, current_close),
        range_position_60d_pct=range_position(history, 60, current_close),
        last_day_volume_ratio_5d=percent_change(float(volume.iloc[-1]), volume_base_5),
        last_day_turnover_ratio_5d=percent_change(float(turnover.iloc[-1]), turnover_base_5),
    )

    if len(history) < 60:
        result.update(status="insufficient_history", reason="交易日前不足 60 根日K")
    elif previous_session is None:
        result.update(
            status="freshness_unverified",
            reason="未提供上一交易日，无法确认个股日K是否完整",
        )
    elif cutoff != previous_session:
        result.update(
            status="stale",
            reason="数据截至 %s，预期上一交易日为 %s" % (
                result["data_cutoff"], previous_session.strftime("%Y-%m-%d")
            ),
        )
    else:
        result["status"] = "ready"
    return result


def render_markdown(results):
    lines = ["# 交易前日线背景（严格无后视）", ""]
    for item in results:
        lines.extend(["## %s %s" % (item["name"], item["code"]), ""])
        lines.append("- 状态：`%s`" % item["status"])
        if item.get("reason"):
            lines.append("- 原因：%s" % item["reason"])
        lines.append("- 规则：%s；隔离了 %s 根当日及之后日K。" % (item["rule"], item.get("quarantined_rows", 0)))
        if item.get("data_cutoff"):
            lines.append("- 数据截止：%s；距交易日 %s 个日历日；可用日K %s 根。" % (
                item["data_cutoff"], item["gap_calendar_days"], item["bars"]
            ))
            lines.append("- 趋势：%s；5/20/60日收益：%s%% / %s%% / %s%%。" % (
                item["trend_state"], item["return_5d_pct"], item["return_20d_pct"], item["return_60d_pct"]
            ))
            lines.append("- 均线：收盘距 MA5 / MA20 / MA60：%s%% / %s%% / %s%%。" % (
                item["distance_ma5_pct"], item["distance_ma20_pct"], item["distance_ma60_pct"]
            ))
            lines.append("- 区间位置：20日 / 60日：%s%% / %s%%；前一日量能/换手相对前5日：%s%% / %s%%。" % (
                item["range_position_20d_pct"], item["range_position_60d_pct"],
                item["last_day_volume_ratio_5d"], item["last_day_turnover_ratio_5d"]
            ))
        lines.append("")
    return "\n".join(lines)


def main():
    args = parse_args()
    try:
        trade_date = pd.Timestamp(datetime.strptime(args.trade_date, "%Y-%m-%d")).normalize()
    except ValueError:
        print("--trade-date 必须是 YYYY-MM-DD", file=sys.stderr)
        return 2

    try:
        codes = [normalize_code(value) for value in re.split(r"[\s,]+", args.codes.strip()) if value]
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    if not codes:
        print("--codes 至少提供一只股票", file=sys.stderr)
        return 2

    previous_session = None
    if args.previous_session:
        try:
            previous_session = pd.Timestamp(datetime.strptime(args.previous_session, "%Y-%m-%d")).normalize()
        except ValueError:
            print("--previous-session 必须是 YYYY-MM-DD", file=sys.stderr)
            return 2
        if previous_session >= trade_date:
            print("--previous-session 必须早于 --trade-date", file=sys.stderr)
            return 2

    data_dir = Path(args.data_dir).expanduser()
    if not data_dir.exists():
        print("数据目录不存在：%s" % data_dir, file=sys.stderr)
        return 2
    names = read_universe(data_dir)
    results = [stock_context(code, names.get(code), data_dir, trade_date, previous_session) for code in codes]

    if args.format == "json":
        print(json.dumps(results, ensure_ascii=False, indent=2))
    else:
        print(render_markdown(results))

    bad = [item for item in results if item["status"] != "ready"]
    if bad and not args.allow_stale:
        print("拒绝将不完整或过期日线当作交易前背景；可修复数据后重试，或显式传 --allow-stale。", file=sys.stderr)
        return 3
    return 0


if __name__ == "__main__":
    sys.exit(main())
