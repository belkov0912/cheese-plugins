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

from trade_context import normalize_code, read_universe, sector_daily_context, stock_context


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
    parser.add_argument("--no-sector-daily", action="store_true", help="跳过申万行业日线强度（r1 口径，截至前一交易日）的计算")
    parser.add_argument("--teaching", action="store_true", help="附加事后教学统计（允许后视，只用于提炼下次的规则，不参与评分）")
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

    # 量能：同标的、交易日之前的分钟K只作基准，全部早于交易日，不违反无后视。
    prior = bars[(bars["symbol"] == normalize_symbol(symbol)) & (bars["datetime"].dt.date < trade_time.date())]
    volume_ratio = None
    baseline_days = 0
    if len(prior):
        same_window = prior[prior["datetime"].dt.time < cutoff.time()]
        if len(same_window):
            per_day = same_window.groupby(same_window["datetime"].dt.date)["volume"].sum()
            baseline_days = int(len(per_day))
            if float(per_day.mean()) > 0:
                volume_ratio = round(float(visible["volume"].sum()) / float(per_day.mean()), 2)
    recent5m_volume_ratio = None
    if len(visible) >= 10:
        last5_sum = float(visible["volume"].iloc[-5:].sum())
        earlier_mean = float(visible["volume"].iloc[:-5].mean())
        if earlier_mean > 0:
            recent5m_volume_ratio = round(last5_sum / (earlier_mean * 5), 2)

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
        "intraday_volume_ratio": volume_ratio,
        "volume_baseline_days": baseline_days,
        "recent5m_volume_ratio": recent5m_volume_ratio,
        "visible_high": round(high, 4),
        "visible_low": round(low, 4),
    }


def fill_time_windows(bars, symbol, trade_time, price):
    """用全天分钟K反查成交价可能出现的时间窗。

    成交价必然落在成交那一分钟的高低区间内，因此这里允许扫描全天——
    只用于校正估算的成交时间，绝不参与任何结构或质量评价。
    """
    day = bars[
        (bars["symbol"] == normalize_symbol(symbol))
        & (bars["datetime"].dt.date == trade_time.date())
    ].sort_values("datetime")
    if day.empty:
        return {"status": "no_bars", "estimated": trade_time.strftime("%H:%M")}
    price = float(price)
    result = {"estimated": trade_time.strftime("%H:%M")}
    for tolerance_pct in (0.0, 0.5):
        tolerance = price * tolerance_pct / 100
        hit = day[(day["low"] - tolerance <= price) & (price <= day["high"] + tolerance)]
        if not len(hit):
            continue
        windows = []
        start = prev = None
        for ts in hit["datetime"]:
            if start is None:
                start = prev = ts
            elif (ts - prev) <= pd.Timedelta(minutes=1):
                prev = ts
            else:
                windows.append((start, prev))
                start = prev = ts
        windows.append((start, prev))
        estimated_bar = trade_time.ceil("min") if trade_time != trade_time.floor("min") else trade_time
        consistent = any(
            begin - pd.Timedelta(minutes=1) <= estimated_bar <= end + pd.Timedelta(minutes=1)
            for begin, end in windows
        )
        result.update({
            "status": "consistent" if consistent else "inconsistent",
            "tolerance_pct": tolerance_pct,
            "windows": [
                begin.strftime("%H:%M") if begin == end
                else "%s-%s" % (begin.strftime("%H:%M"), end.strftime("%H:%M"))
                for begin, end in windows
            ],
        })
        return result
    result["status"] = "price_out_of_day_range"
    return result


def teaching_snapshot(bars, symbol, trade_time, price):
    """事后教学（允许后视）：全天与成交后的走势统计。

    只用于提炼下次可执行的买卖规则，绝不回流进四项评分或对这笔交易的当时评价。
    """
    day = bars[
        (bars["symbol"] == normalize_symbol(symbol))
        & (bars["datetime"].dt.date == trade_time.date())
    ].sort_values("datetime")
    if day.empty:
        return {"status": "no_bars"}
    price = float(price)
    day_high = float(day["high"].max())
    day_low = float(day["low"].min())
    day_close = float(day["close"].iloc[-1])
    vwap = None
    if day["volume"].sum() > 0:
        typical = (day["high"] + day["low"] + day["close"]) / 3
        vwap = float((typical * day["volume"]).sum() / day["volume"].sum())
        if "amount" in day.columns and day["amount"].notna().all():
            raw = float(day["amount"].sum() / day["volume"].sum())
            median_price = float(day["close"].median())
            if median_price > 0 and 0.5 <= raw / median_price <= 2:
                vwap = raw
    result = {
        "status": "ready",
        "hindsight_note": "本节允许后视，只用于提炼下次的规则，不评价这笔交易的当时决策",
        "day_high": round(day_high, 4),
        "day_high_time": day.loc[day["high"].idxmax(), "datetime"].strftime("%H:%M"),
        "day_low": round(day_low, 4),
        "day_low_time": day.loc[day["low"].idxmin(), "datetime"].strftime("%H:%M"),
        "day_close": round(day_close, 4),
        "close_vs_fill_pct": pct(day_close, price),
        "day_vwap": round(vwap, 4) if vwap is not None else None,
        "fill_vs_day_vwap_pct": pct(price, vwap) if vwap is not None else None,
    }
    post = day[day["datetime"] >= trade_time.floor("min")]
    if len(post):
        result["post_fill_high_pct"] = pct(float(post["high"].max()), price)
        result["post_fill_low_pct"] = pct(float(post["low"].min()), price)
    return result


def row_value(row, column, default=None):
    value = row[column] if column in row.index else default
    return default if pd.isna(value) else value


def review_one(row, bars, data_dir, names, previous_session, sector_daily):
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
            "fill_time_check": "成交价时间窗核对扫描全天分钟K，只用于校正估算成交时间，不参与结构评价",
        },
        "fill_time_check": fill_time_windows(bars, symbol, trade_time, row["price"]),
        "daily_context": daily,
        "sector_daily": sector_daily.get(symbol, {"status": "unavailable", "reason": "未计算"}),
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
            if snapshot.get("intraday_volume_ratio") is not None:
                detail += "；量比 %s（同时段 %s 日基准）" % (
                    snapshot["intraday_volume_ratio"], snapshot["volume_baseline_days"]
                )
            if snapshot.get("recent5m_volume_ratio") is not None:
                detail += "，近5分量能比 %s" % snapshot["recent5m_volume_ratio"]
            lines.append("- %s：截至 %s，%s 根完整一分钟K；相对开盘 %s%%，相对当时VWAP %s%%，可见区间位置 %s%%%s。" % (
                label, snapshot["cutoff_exclusive"], snapshot["bars_used"], snapshot["change_from_open_pct"],
                snapshot["distance_vwap_pct"], snapshot["position_in_visible_range_pct"], detail
            ))
        else:
            lines.append("- %s：`%s`，%s。" % (label, snapshot["status"], snapshot.get("reason", "未提供")))

    def append_sector_daily(snapshot):
        if snapshot.get("status") == "ready":
            rank = snapshot.get("stock_rank_in_sector")
            lines.append(
                "- 行业日线（截至 %s）：%s 5日%s%%、20日%s%%，热度rank %s%s；个股20日%s%%%s，R1=%s。" % (
                    snapshot["as_of"], snapshot["sector_name"],
                    snapshot["sector_ret5_pct"], snapshot["sector_ret20_pct"],
                    snapshot["sector_rank"], "（动态主线）" if snapshot.get("sector_mainline") else "",
                    snapshot["stock_ret20_pct"],
                    "、行业内rank %s" % rank if rank is not None else "",
                    snapshot["r1_score"],
                )
            )
        else:
            lines.append("- 行业日线：`%s`，%s。" % (snapshot.get("status"), snapshot.get("reason", "未提供")))

    def append_fill_time(check):
        status = check.get("status")
        if status in ("consistent", "inconsistent"):
            note = "" if not check.get("tolerance_pct") else "（含 %s%% 容差）" % check["tolerance_pct"]
            lines.append("- 成交价时间窗核对：`%s`，估算 %s，价格出现于 %s%s。" % (
                status, check.get("estimated"), "、".join(check.get("windows", [])), note
            ))
        else:
            lines.append("- 成交价时间窗核对：`%s`，估算 %s。" % (status, check.get("estimated")))

    for item in reviews:
        trade = item["trade"]
        lines.extend(["## %s %s" % (trade["name"], trade["side"]), ""])
        lines.append("- 成交：%s，%s，%s × %s。" % (trade["datetime"], trade["symbol"], trade["price"], trade["quantity"]))
        lines.append("- 复盘状态：`%s`。" % item["status"])
        daily = item["daily_context"]
        lines.append("- 日线：`%s`，数据截止 %s，趋势 %s。" % (
            daily["status"], daily.get("data_cutoff", "无"), daily.get("trend_state", "无")
        ))
        append_fill_time(item["fill_time_check"])
        append_sector_daily(item["sector_daily"])
        append_intraday("个股分时", item["stock_intraday"])
        append_intraday("大盘分时", item["market_intraday"])
        append_intraday("行业分时", item["sector_intraday"])
        teaching = item.get("teaching")
        if teaching:
            if teaching.get("status") == "ready":
                post = ""
                if teaching.get("post_fill_high_pct") is not None:
                    post = "；成交后最高 %s%%、最低 %s%%（相对成交价）" % (
                        teaching["post_fill_high_pct"], teaching["post_fill_low_pct"]
                    )
                lines.append(
                    "- 事后教学（允许后视，不参与评分）：全天最高 %s（%s）、最低 %s（%s）、收盘 %s（相对成交价 %s%%）；全天VWAP %s，成交价相对全天VWAP %s%%%s。" % (
                        teaching["day_high"], teaching["day_high_time"],
                        teaching["day_low"], teaching["day_low_time"],
                        teaching["day_close"], teaching["close_vs_fill_pct"],
                        teaching["day_vwap"], teaching["fill_vs_day_vwap_pct"], post,
                    )
                )
            else:
                lines.append("- 事后教学：`%s`。" % teaching.get("status"))
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
    if args.no_sector_daily:
        sector_daily = {}
    else:
        sector_daily = sector_daily_context(
            sorted(set(trades["symbol"])), previous_session.strftime("%Y-%m-%d")
        )
    reviews = [review_one(row, bars, data_dir, names, previous_session, sector_daily) for _, row in trades.iterrows()]
    if args.teaching:
        for item, (_, row) in zip(reviews, trades.iterrows()):
            item["teaching"] = teaching_snapshot(bars, row["symbol"], row["datetime"], row["price"])

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
