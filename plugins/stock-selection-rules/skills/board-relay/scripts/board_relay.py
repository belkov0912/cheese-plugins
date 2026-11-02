#!/usr/bin/env python3
"""二三板接力 · 收盘后离线筛选（两个小馒头打法）。

收盘后（建议 17:00 前后）用当日涨停数据筛出次日二板/三板打板观察名单：
  1. 定题材：只留板块批量涨停（共振）的票，独苗不做；
  2. 看盘口：当日封板早、没反复开板、不是尾盘偷袭、不是一字（要换手板）；
  3. 卡量能：首板放量、充分换手；二板缩量加速优先；
  4. 排雷：高标（次日 4 板+）、大盘股、ST、近期利空公告、临近解禁。
通过的票打分排序，top N 是次日重点盯盘对象。真正的买点仍在次日盘中：
同题材里谁最快封板、10 点前封死、封后不开，谁就是龙头，打它。

数据源（全部免费公开接口，缓存到 $R0_DATA_DIR/board_relay，缺省 ~/.r0-data/board_relay）：
  同花顺 涨停池 + 涨停热点板块（含涨停原因；历史约 1 年）
  东方财富 涨停池 / 昨日涨停池（炸板次数、连板数；只保留最近几周）
  东方财富 日K（前复权价、原始成交量）、个股公告、限售解禁

用法：
  board_relay.py screen                        # 最近一个完整交易日（北京时间 15:30 后算当天）
  board_relay.py screen --date 2026-11-02 --top 5
  board_relay.py screen --json                 # 机器可读
  board_relay.py screen --md-out <路径.md>      # 另存一份 Markdown 报告
  board_relay.py backtest --days 7 --top 3     # 回测最近 7 个交易日 top3 的次日表现
  board_relay.py                               # 无参 = 离线自检（不碰网络）
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import io
import json
import os
import re
import sys
import time
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor
from contextlib import redirect_stderr
from decimal import ROUND_HALF_UP, Decimal

BJ = dt.timezone(dt.timedelta(hours=8))  # 中国无夏令时，固定东八区
DATA_DIR = os.path.join(os.path.expanduser(os.environ.get("R0_DATA_DIR") or "~/.r0-data"), "board_relay")
HTTP_TIMEOUT = 15
READY_HM = (15, 30)  # 北京时间该点之后，当天算完整交易日
WORKERS = 6

THS_BASE = "https://data.10jqka.com.cn/dataapi/limit_up/"
THS_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120 Safari/537.36",
    "Referer": "https://data.10jqka.com.cn/datacenterph/limitup/limtupInfo.html",
}
THS_FIELDS = "199112,10,9001,330323,330324,330325,9002,330329,133971,133970,1968584,3475914,9003,9004"
EM_NOTICE_URL = "https://np-anotice-stock.eastmoney.com/api/security/ann"
UA = {"User-Agent": THS_HEADERS["User-Agent"]}

DEFAULTS = {
    "top": 3,
    "min_theme": 3,             # 板块共振：同一题材当日涨停家数下限
    "min_block_chg": 2.0,       # 同花顺热点板块当日涨幅下限(%)：板块整体在涨才算共振，挡住"大而泛"概念凑数
    "max_float_cap": 200.0,     # 流通市值上限(亿)
    "min_first_turnover": 3.0,  # 首板换手下限(%)：首板要充分换手
    "min_first_vr": 1.0,        # 首板量比下限（当日量 / 前5日均量）：首板要放量
    "tail_cutoff": "14:30:00",  # 首次封板晚于此 = 尾盘偷袭
    "lanban_gap": 60,           # 开过板且首封到末封间隔 ≥ 此(交易分钟) = 烂板
    "lanban_opens": 3,          # 东财炸板次数 ≥ 此 = 反复炸板（大涨日开 1-2 次板很常见，不算反复）
    "notice_days": 30,          # 公告排雷回看自然日
    "unlock_days": 30,          # 解禁前瞻自然日
    "unlock_ratio": 0.01,       # 解禁市值占流通市值比例下限(小数)
    "include_688": False,
}

# 涨停原因里描述个股事件而非板块题材的标签：业绩、资本运作、国资、超跌等，不拿来算共振
NON_THEME_TAG = re.compile(
    r"季报|中报|年报|半年报|业绩|预增|扭亏|减亏|净利|营收|增长|大增|高增|落地|超跌|反弹|并购|重组|收购|"
    r"购买资产|资产注入|借壳|控制权|实控|入主|国资|央企|国企|回购|增持|分红|股权|摘帽|举牌|定增|重整|"
    r"破产|次新|复牌|转让|拟入主")

STRONG_NOTICE = [
    # (类别, 命中, 豁免)
    ("减持", re.compile(r"减持"), re.compile(r"完毕|结果|届满|终止|未减持|不减持|不存在减持|承诺不减持|未实施")),
    ("监管", re.compile(r"立案|行政处罚|处罚决定|警示函|监管函|问询函|关注函|纪律处分|通报批评|监管措施"), None),
    ("业绩预亏", re.compile(r"预亏|首亏|续亏|增亏|预减|业绩.{0,6}(下降|下滑|亏损)|亏损.{0,4}预告"), None),
    ("退市/ST", re.compile(r"退市|终止上市|其他风险警示|\*ST"), re.compile(r"撤销")),
    ("解禁", re.compile(r"限售.{0,12}上市流通|解除限售"), None),
]
WEAK_NOTICE = [
    ("风险提示", re.compile(r"风险提示|严重异常波动")),
    ("减值", re.compile(r"减值")),
    ("诉讼/冻结/质押", re.compile(r"诉讼|仲裁|冻结|质押")),
]


class DataError(RuntimeError):
    pass


# ---------------------------------------------------------------- 通用工具

def bj_now() -> dt.datetime:
    return dt.datetime.now(BJ).replace(tzinfo=None)


def _patch_requests_timeout() -> None:
    """akshare 多数接口不传 timeout，服务端挂起会卡死整个进程；统一补默认超时。"""
    import requests

    if getattr(requests.sessions.Session.request, "_board_relay_patched", False):
        return
    original = requests.sessions.Session.request

    def request(self, method, url, **kwargs):
        if kwargs.get("timeout") is None:
            kwargs["timeout"] = HTTP_TIMEOUT
        return original(self, method, url, **kwargs)

    request._board_relay_patched = True
    requests.sessions.Session.request = request


def _retry(fn, tries=3, wait=1.0):
    last = None
    for i in range(tries):
        try:
            return fn()
        except Exception as exc:  # 网络抖动、限流、接口偶发空响应
            last = exc
            time.sleep(wait * (i + 1))
    raise last


def _quiet(fn):
    """吞掉 akshare 的 tqdm 进度条（只在主线程用）。"""
    with redirect_stderr(io.StringIO()):
        return fn()


def _f(x, default=None):
    try:
        if x is None or x == "" or x == "-":
            return default
        v = float(x)
        return default if v != v else v  # NaN
    except (TypeError, ValueError):
        return default


def _path(*parts) -> str:
    p = os.path.join(DATA_DIR, *parts)
    os.makedirs(os.path.dirname(p), exist_ok=True)
    return p


def _load_json(p):
    try:
        with open(p, encoding="utf-8") as fh:
            return json.load(fh)
    except Exception:
        return None


def _dump_json(p, obj) -> None:
    tmp = p + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(obj, fh, ensure_ascii=False)
    os.replace(tmp, p)


def is_complete(date: str, now: dt.datetime | None = None) -> bool:
    """这个交易日的盘后数据是否已定稿（只缓存定稿的数据）。"""
    now = now or bj_now()
    d = dt.date.fromisoformat(date)
    return d < now.date() or (d == now.date() and (now.hour, now.minute) >= READY_HM)


def hms_of(ts) -> str | None:
    """同花顺 unix 秒 → 北京时间 HH:MM:SS。"""
    v = _f(ts)
    if not v:
        return None
    return dt.datetime.fromtimestamp(int(v), BJ).strftime("%H:%M:%S")


def em_hms(s) -> str | None:
    """东财 '092500' / 92500 → '09:25:00'。"""
    if s is None or s == "":
        return None
    s = str(int(float(s))).zfill(6)
    return f"{s[:2]}:{s[2:4]}:{s[4:]}"


def trade_minute(hms: str) -> float:
    """HH:MM:SS → 从 09:30 起算的交易分钟（午休不计；竞价段记 0）。"""
    h, m, s = (int(x) for x in hms.split(":"))
    t = h * 60 + m + s / 60.0
    if t <= 570:          # 09:30 前
        return 0.0
    if t <= 690:          # 11:30 前
        return t - 570
    if t < 780:           # 午休
        return 120.0
    return 120.0 + min(t, 900) - 780


def limit_pct(code: str, name: str) -> float:
    if "ST" in name.upper():
        return 0.05
    if code.startswith(("300", "301", "688", "689")):
        return 0.20
    if code.startswith(("4", "8", "92")):
        return 0.30
    return 0.10


def limit_price(prev_close: float, pct: float) -> float:
    q = Decimal(str(prev_close)) * (Decimal(1) + Decimal(str(pct)))
    return float(q.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


def parse_high_days(s) -> tuple:
    """同花顺 '首板' / 'N天M板' → (N, M)。"""
    if not s:
        return None, None
    if s == "首板":
        return 1, 1
    m = re.match(r"(\d+)天(\d+)板", str(s))
    if m:
        return int(m.group(1)), int(m.group(2))
    return None, None


def is_bj(code: str) -> bool:
    return code.startswith(("4", "8", "92"))


# ---------------------------------------------------------------- 交易日历

def trade_dates() -> list:
    p = _path("trade_dates.json")
    cached = _load_json(p)
    fresh = cached and time.time() - os.path.getmtime(p) < 7 * 86400
    if fresh and cached:
        return cached
    try:
        import akshare as ak

        df = _retry(lambda: ak.tool_trade_date_hist_sina())
        dates = sorted(str(x)[:10] for x in df["trade_date"])
        if len(dates) > 1000:
            _dump_json(p, dates)
            return dates
    except Exception as exc:
        print(f"[交易日历] 新浪日历拉取失败（{type(exc).__name__}），用缓存或工作日近似", file=sys.stderr)
    if cached:
        return cached
    today = bj_now().date()
    return [(today - dt.timedelta(days=i)).isoformat() for i in range(800, -30, -1)
            if (today - dt.timedelta(days=i)).weekday() < 5]


def latest_complete(dates: list, now: dt.datetime | None = None) -> str:
    now = now or bj_now()
    done = [d for d in dates if is_complete(d, now) and d <= now.date().isoformat()]
    if not done:
        raise DataError("交易日历里找不到已收盘的交易日")
    return done[-1]


def prev_trade(dates: list, date: str) -> str | None:
    earlier = [d for d in dates if d < date]
    return earlier[-1] if earlier else None


def next_trade(dates: list, date: str) -> str | None:
    later = [d for d in dates if d > date]
    return later[0] if later else None


# ---------------------------------------------------------------- 数据源：同花顺

def _ths_get(path: str, params: dict) -> dict:
    import requests

    r = requests.get(THS_BASE + path, params=params, headers=THS_HEADERS, timeout=HTTP_TIMEOUT)
    r.raise_for_status()
    return r.json()


def ths_pool(date: str) -> dict:
    """同花顺涨停池：{'info': [...], 'limit_up_count': {...}, 'limit_down_count': {...}}。"""
    key = date.replace("-", "")
    p = _path("ths", f"pool_{key}.json")
    cached = _load_json(p)
    if cached:
        return cached
    params = {"page": 1, "limit": 200, "field": THS_FIELDS, "filter": "HS,GEM2STAR",
              "order_field": "330324", "order_type": "0", "date": key}
    j = _retry(lambda: _ths_get("limit_up_pool", params))
    if j.get("status_code") not in (0, None):
        raise DataError(f"同花顺涨停池 {date}：{j.get('status_msg')}")
    data = j.get("data") or {}
    info = list(data.get("info") or [])
    total = int((data.get("page") or {}).get("total") or len(info))
    page = 2
    while len(info) < total and page <= 10:
        params["page"] = page
        jj = _retry(lambda: _ths_get("limit_up_pool", params))
        more = ((jj.get("data") or {}).get("info")) or []
        if not more:
            break
        info.extend(more)
        page += 1
    for row in info:
        row.pop("time_preview", None)  # 分时缩略，用不上
    out = {"info": info, "limit_up_count": data.get("limit_up_count"),
           "limit_down_count": data.get("limit_down_count")}
    if info and is_complete(date):
        _dump_json(p, out)
    return out


def ths_blocks(date: str) -> list:
    """同花顺涨停热点板块（当日涨停家数前 20 的概念板块，含成员与板块涨幅）。"""
    key = date.replace("-", "")
    p = _path("ths", f"blocks_{key}.json")
    cached = _load_json(p)
    if cached is not None:
        return cached
    j = _retry(lambda: _ths_get("block_top", {"filter": "HS,GEM2STAR", "date": key}))
    if j.get("status_code") not in (0, None):
        raise DataError(f"同花顺热点板块 {date}：{j.get('status_msg')}")
    blocks = []
    for b in j.get("data") or []:
        blocks.append({
            "code": b.get("code"), "name": b.get("name"), "change": _f(b.get("change"), 0.0),
            "limit_up_num": int(_f(b.get("limit_up_num"), 0)),
            "members": [s.get("code") for s in (b.get("stock_list") or []) if s.get("code")],
        })
    if blocks and is_complete(date):
        _dump_json(p, blocks)
    return blocks


# ---------------------------------------------------------------- 数据源：东方财富

def _em_pool(kind: str, date: str):
    """东财涨停池(zt) / 昨日涨停池(prev)。接口只保留最近几周，取不到返回 None。"""
    key = date.replace("-", "")
    p = _path("em", f"{kind}_{key}.json")
    cached = _load_json(p)
    if cached is not None:
        return cached or None
    import akshare as ak

    fn = {"zt": ak.stock_zt_pool_em, "prev": ak.stock_zt_pool_previous_em}[kind]
    try:
        df = _retry(lambda: fn(date=key), tries=3)
    except Exception:
        return None
    if df is None or df.empty:
        if is_complete(date) and dt.date.fromisoformat(date) < bj_now().date() - dt.timedelta(days=45):
            _dump_json(p, [])  # 早已过保留期，记一笔免得反复请求
        return None
    rows = json.loads(df.to_json(orient="records", force_ascii=False))
    if is_complete(date):
        _dump_json(p, rows)
    return rows


def em_zt_pool(date: str):
    return _em_pool("zt", date)


def em_prev_pool(date: str):
    return _em_pool("prev", date)


def bars(code: str, start: str, end: str) -> list:
    """东财日K（前复权价、原始量）。按日期升序：[{date, open, close, high, low, volume, turnover, pct}]。
    缓存只覆盖定稿日期；需要更大区间时整段重抓（前复权价在除权后会整体改写，不拼接不同批次）。"""
    p = _path("kline", f"{code}.json")
    cached = _load_json(p)
    if cached and cached["start"] <= start and cached["end"] >= end:
        return [r for r in cached["rows"] if start <= r["date"] <= end]
    s = min(start, cached["start"]) if cached else start
    # 一次抓到最近已收盘的自然日，回测逐日推进时不必反复重抓
    now = bj_now()
    closed = now.date() if (now.hour, now.minute) >= READY_HM else now.date() - dt.timedelta(days=1)
    e = max(end, closed.isoformat())
    import akshare as ak

    def em():
        df = ak.stock_zh_a_hist(symbol=code, period="daily", start_date=s.replace("-", ""),
                                end_date=e.replace("-", ""), adjust="qfq")
        return [{"date": str(r["日期"])[:10], "open": _f(r["开盘"]), "close": _f(r["收盘"]),
                 "high": _f(r["最高"]), "low": _f(r["最低"]), "volume": _f(r["成交量"]),
                 "turnover": _f(r["换手率"]), "pct": _f(r["涨跌幅"])} for _, r in df.iterrows()]

    def sina():
        sym = ("sh" if code.startswith("6") else "bj" if is_bj(code) else "sz") + code
        df = ak.stock_zh_a_daily(symbol=sym, start_date=s.replace("-", ""), end_date=e.replace("-", ""), adjust="qfq")
        rows, prev = [], None
        for _, r in df.iterrows():
            c = _f(r["close"])
            rows.append({"date": str(r["date"])[:10], "open": _f(r["open"]), "close": c, "high": _f(r["high"]),
                         "low": _f(r["low"]), "volume": _f(r["volume"]),
                         "turnover": (_f(r.get("turnover"), 0.0) or 0.0) * 100,
                         "pct": (c / prev - 1) * 100 if prev else None})
            prev = c
        return rows

    rows = None
    for source in (em, sina):
        try:
            rows = _retry(source, tries=2)
            if rows:
                break
        except Exception:
            rows = None
    if not rows:
        return []
    done = [r for r in rows if is_complete(r["date"])]
    if done:
        _dump_json(p, {"start": s, "end": min(e, closed.isoformat()), "rows": done})
    return [r for r in rows if start <= r["date"] <= end]


def notices(code: str) -> list:
    """东财个股公告标题（最近 50 条）：[(YYYY-MM-DD, 标题)]。"""
    import requests

    params = {"sr": "-1", "page_size": "50", "page_index": "1", "ann_type": "A", "client_source": "web",
              "stock_list": code, "f_node": "0", "s_node": "0"}

    def get():
        r = requests.get(EM_NOTICE_URL, params=params, headers=UA, timeout=HTTP_TIMEOUT)
        r.raise_for_status()
        return r.json()

    j = _retry(get)
    lst = ((j or {}).get("data") or {}).get("list") or []
    return [(str(a.get("notice_date", ""))[:10], str(a.get("title", ""))) for a in lst]


def unlocks(start: str, end: str) -> dict:
    """限售解禁日程：{代码: [(解禁日, 占流通市值比例, 实际解禁市值亿)]}；拉取失败返回 None。"""
    import akshare as ak

    try:
        df = _retry(lambda: _quiet(lambda: ak.stock_restricted_release_detail_em(
            start_date=start.replace("-", ""), end_date=end.replace("-", ""))), tries=2)
    except Exception:
        return None
    out = defaultdict(list)
    if df is None or df.empty:
        return out
    for _, r in df.iterrows():
        out[str(r["股票代码"]).zfill(6)].append(
            (str(r["解禁时间"])[:10], _f(r["占解禁前流通市值比例"], 0.0), (_f(r["实际解禁市值"], 0.0) or 0.0) / 1e8))
    return out


# ---------------------------------------------------------------- 规则

def classify_notices(items: list, asof: str, days: int) -> tuple:
    """公告标题 → (强利空列表, 弱提示列表)；只看 (asof-days, asof] 之间的公告，杜绝后视。"""
    lo = (dt.date.fromisoformat(asof) - dt.timedelta(days=days)).isoformat()
    strong, weak = [], []
    for date, title in items:
        if not (lo < date <= asof):
            continue
        hit = False
        for kind, pat, exempt in STRONG_NOTICE:
            if pat.search(title) and not (exempt and exempt.search(title)):
                strong.append(f"{kind}:{date} {title}")
                hit = True
                break
        if hit:
            continue
        for kind, pat in WEAK_NOTICE:
            if pat.search(title):
                weak.append(f"{kind}:{date} {title}")
                break
    return strong, weak


def build_records(pool: dict, em_rows) -> list:
    em = {str(r.get("代码", "")).zfill(6): r for r in (em_rows or [])}
    recs = []
    for x in pool.get("info") or []:
        code = str(x.get("code") or "").zfill(6)
        name = str(x.get("name") or "")
        first, last = hms_of(x.get("first_limit_up_time")), hms_of(x.get("last_limit_up_time"))
        e = em.get(code)
        em_opens = int(_f(e.get("炸板次数"), 0)) if e else None
        if e and not first:
            first, last = em_hms(e.get("首次封板时间")), em_hms(e.get("最后封板时间"))
        opened = (em_opens > 0) if em_opens is not None else (
            x.get("change_tag") == "LIMIT_BACK" or str(x.get("is_again_limit")) == "1")
        gap = (trade_minute(last) - trade_minute(first)) if (first and last) else 0.0
        days, boards = parse_high_days(x.get("high_days"))
        recs.append({
            "code": code, "name": name, "close": _f(x.get("latest")), "chg": _f(x.get("change_rate")),
            "turnover": _f(x.get("turnover_rate"), 0.0), "float_cap": (_f(x.get("currency_value"), 0.0) or 0.0) / 1e8,
            "seal_amt": (_f(x.get("order_amount"), 0.0) or 0.0) / 1e8, "first": first, "last": last,
            "type": x.get("limit_up_type") or "", "high_days": x.get("high_days") or "", "hd": (days, boards),
            "reason": x.get("reason_type") or "", "tags": [t for t in (x.get("reason_type") or "").split("+") if t],
            "opened": bool(opened), "em_opens": em_opens, "gap": max(gap, 0.0),
            "em_streak": int(_f(e.get("连板数"), 0)) if e else None,
            "industry": (e or {}).get("所属行业"),
        })
    return recs


def assign_streaks(recs: list, date: str, dates: list, pool_fn=None, depth: int = 12) -> None:
    """连板数：东财连板数优先；否则同花顺 'N天N板' 直接给；'N天M板'(N≠M) 逐日回溯前一日涨停池。"""
    pool_fn = pool_fn or ths_pool
    memo = {}

    def streak_on(code: str, day: str, hd: tuple, left: int) -> int:
        days, boards = hd
        if days is not None and days == boards:
            return boards
        if left <= 0:
            return 1
        prev = prev_trade(dates, day)
        if not prev:
            return 1
        if prev not in memo:
            try:
                memo[prev] = {str(r.get("code")).zfill(6): parse_high_days(r.get("high_days"))
                              for r in (pool_fn(prev).get("info") or [])}
            except Exception:
                memo[prev] = {}
        if code not in memo[prev]:
            return 1
        return 1 + streak_on(code, prev, memo[prev][code], left - 1)

    for r in recs:
        if r["em_streak"]:
            r["streak"] = r["em_streak"]
        else:
            r["streak"] = streak_on(r["code"], date, r["hd"], depth)


def norm_tag(t: str) -> str:
    """涨停原因标签归一：'人工智能漫剧'→'AI漫剧'，去引号（'“羊”字辈'→'羊字辈'）。"""
    return re.sub(r"[“”\"'‘’\s]", "", t.replace("人工智能", "AI"))


def build_themes(recs: list, blocks: list, cfg: dict) -> list:
    """题材 = 涨停原因证据 + 热点板块胶水。

    1. 热点板块（当日涨停≥min_theme 且板块涨幅≥min_block_chg）按成员重叠(≥50%)合并成簇——只用来把相关标签
       并成一条主线、给主线命名；"华为概念/人工智能"这类大而泛的概念不能直接把票拉进主线。
    2. 归一化标签里 ≥min_theme 家共用的叫大标签；大标签的票有一半以上落在某簇里，它就是该簇的核心标签，
       否则自成一个题材（如"羊字辈"、"白酒"）。
    3. 簇的家族标签 = 核心标签 + 与核心标签在同一只票上共现、且票主要在簇内的两家小标签（如 IP运营、图书出版）。
    4. 票的涨停原因里有家族标签、或某个标签包含核心标签（核心标签'短剧' → '短剧出海'也算）才算该题材成员。
       没有核心标签、但板块涨幅很强(≥5%)的簇按板块成员计（标签写法不统一时兜底）。
    每只票归入成员最多的题材；一个题材也挂不上 = 独苗/非主线。"""
    min_n = cfg["min_theme"]
    codes = {r["code"] for r in recs}
    stocks_of = defaultdict(set)
    for r in recs:
        seen = []
        for t in r["tags"]:
            if NON_THEME_TAG.search(t):
                continue
            n = norm_tag(t)
            if n and n not in seen:
                seen.append(n)
        r["ntags"] = seen
        for t in seen:
            stocks_of[t].add(r["code"])

    hot = []
    for b in blocks or []:
        mem = set(b["members"]) & codes
        if len(mem) >= min_n and (b["change"] or 0) >= cfg["min_block_chg"]:
            hot.append({"name": b["name"], "chg": b["change"], "members": mem})
    parent = list(range(len(hot)))

    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    for i in range(len(hot)):
        for j in range(i + 1, len(hot)):
            a, b = hot[i]["members"], hot[j]["members"]
            if len(a & b) / min(len(a), len(b)) >= 0.5:
                parent[find(i)] = find(j)
    groups = defaultdict(list)
    for i, h in enumerate(hot):
        groups[find(i)].append(h)
    clusters = []
    for g in groups.values():
        g.sort(key=lambda h: -h["chg"])
        clusters.append({"name": "/".join(h["name"] for h in g[:3]), "blocks": [h["name"] for h in g],
                         "scope": set().union(*(h["members"] for h in g)), "chg": g[0]["chg"]})

    big = sorted((t for t, s in stocks_of.items() if len(s) >= min_n), key=lambda t: (-len(stocks_of[t]), t))
    core_of = {}
    for t in big:
        s, best, ov = stocks_of[t], None, 0.0
        for i, c in enumerate(clusters):
            o = len(s & c["scope"]) / len(s)
            if o > ov or (best is not None and o == ov and len(c["scope"]) > len(clusters[best]["scope"])):
                best, ov = i, o
        if best is not None and ov >= 0.5:
            core_of[t] = best

    themes = []
    for i, c in enumerate(clusters):
        core = [t for t in big if core_of.get(t) == i]
        if core:
            themes.append(dict(c, core=core, kind="cluster"))
        elif (c["chg"] or 0) >= 5.0:
            themes.append(dict(c, core=[], kind="block", members=set(c["scope"]), family=[]))
    for t in big:
        if t not in core_of:
            themes.append({"name": t, "blocks": [], "scope": None, "chg": None, "core": [t], "kind": "tag"})

    for th in themes:
        if th["kind"] == "block":
            continue
        core = set(th["core"])
        fam = set(core)
        if th["kind"] == "cluster":
            for r in recs:
                if not core & set(r["ntags"]):
                    continue
                for t in r["ntags"]:
                    s = stocks_of[t]
                    if t not in fam and 2 <= len(s) < min_n and len(s & th["scope"]) / len(s) >= 0.5:
                        fam.add(t)
        th["family"] = sorted(fam - core, key=lambda t: (-len(stocks_of[t]), t))
        th["members"] = {r["code"] for r in recs
                         if any(t in fam or any(len(c) >= 2 and c in t for c in core) for t in r["ntags"])}

    themes = [th for th in themes if len(th["members"]) >= min_n]
    themes.sort(key=lambda th: (-len(th["members"]), th["name"]))
    for r in recs:
        mine = [th for th in themes if r["code"] in th["members"]]
        if mine:
            th = max(mine, key=lambda th: len(th["members"]))
            r["theme"], r["theme_n"] = th["name"], len(th["members"])
        else:
            r["theme"], r["theme_n"] = None, max([1] + [len(stocks_of[t]) for t in r["ntags"]])
    return themes


def cheap_reasons(r: dict, cfg: dict) -> list:
    """不用联网就能判的排除项（按方法里"坚决不碰"的顺序）。"""
    out = []
    if "ST" in r["name"].upper() or "退" in r["name"]:
        out.append("ST/退市")
    if is_bj(r["code"]):
        out.append("北交所")
    if r["code"].startswith(("688", "689")) and not cfg["include_688"]:
        out.append("科创板(默认不做)")
    if r["streak"] >= 3:
        out.append(f"高标{r['streak']}连板(次日{r['streak'] + 1}板不碰)")
    if r["type"] == "一字板":
        out.append("一字板(没换手)")
    if (r["first"] or "99") >= cfg["tail_cutoff"]:
        out.append(f"尾盘偷袭(首封{(r['first'] or '--:--')[:5]})")
    if (r["em_opens"] is not None and r["em_opens"] >= cfg["lanban_opens"]) or (r["opened"] and r["gap"] >= cfg["lanban_gap"]):
        opens = f"开板{r['em_opens']}次," if r["em_opens"] is not None else "开过板,"
        out.append(f"烂板({opens}{(r['first'] or '')[:5]}→{(r['last'] or '')[:5]})")
    if r["float_cap"] > cfg["max_float_cap"]:
        out.append(f"大盘股(流通{r['float_cap']:.0f}亿)")
    if r["theme"] is None:
        out.append(f"独苗/非主线(同题材涨停仅{r['theme_n']}家)")
    if r["streak"] == 1 and r["turnover"] < cfg["min_first_turnover"]:
        out.append(f"首板换手不足({r['turnover']:.1f}%)")
    return out


def volume_feats(rows: list, date: str) -> dict | None:
    """rows 为截至 date（含）的日K。首板看量比 vr=当日量/前5日均量；二板看 sr=当日量/首板日量。"""
    rows = [x for x in rows if x["date"] <= date and x.get("volume")]
    if not rows or rows[-1]["date"] != date:
        return None
    v = [x["volume"] for x in rows]
    prev5 = v[-6:-1]
    vr = v[-1] / (sum(prev5) / len(prev5)) if prev5 and sum(prev5) > 0 else None
    sr = v[-1] / v[-2] if len(v) >= 2 and v[-2] > 0 else None
    prev5b = v[-7:-2]
    vr_prev = v[-2] / (sum(prev5b) / len(prev5b)) if len(v) >= 3 and prev5b and sum(prev5b) > 0 else None
    return {"vr": vr, "sr": sr, "vr_prev": vr_prev, "bar_close": rows[-1]["close"]}


def score_parts(r: dict) -> dict:
    """满分 100：题材 30 + 封板时间 20 + 不开板 10 + 量能 20 + 先手 10 + 市值 10。"""
    n = r["theme_n"]
    theme = 30 if n >= 20 else 25 if n >= 10 else 20 if n >= 6 else 15 if n >= 4 else 10
    t = r["first"] or "99"
    seal = 20 if t <= "09:35:00" else 16 if t <= "10:00:00" else 11 if t <= "10:30:00" else 6 if t <= "11:30:00" else 2 if t <= "14:00:00" else 0
    if not r["opened"]:
        hold = 10
    elif r["gap"] <= 15 and (r["em_opens"] is None or r["em_opens"] <= 1):
        hold = 5
    else:
        hold = 0
    if r["streak"] == 1:
        vr = r.get("vr")
        vol = 0 if vr is None else 20 if vr >= 3 else 16 if vr >= 2 else 10 if vr >= 1.5 else 5 if vr >= 1.0 else 0
    else:
        sr = r.get("sr")
        vol = 0 if sr is None else 20 if sr <= 0.8 else 16 if sr <= 1.0 else 10 if sr <= 1.3 else 5 if sr <= 2.0 else 0
    rank = r.get("theme_rank") or 99
    first = 10 if rank == 1 else 5 if rank <= 3 else 0
    fc = r["float_cap"]
    cap = 10 if fc <= 50 else 7 if fc <= 100 else 4 if fc <= 150 else 1
    return {"题材": theme, "封板": seal, "不开板": hold, "量能": vol, "先手": first, "市值": cap}


def rank_in_theme(cands: list) -> None:
    by = defaultdict(list)
    for r in cands:
        by[r["theme"]].append(r)
    for group in by.values():
        times = sorted(r["first"] or "99" for r in group)
        for r in group:
            r["theme_rank"] = times.index(r["first"] or "99") + 1


# ---------------------------------------------------------------- 主流程

def _parallel(fn, items, workers=WORKERS):
    if not items:
        return []
    with ThreadPoolExecutor(max_workers=min(workers, len(items))) as ex:
        return list(ex.map(fn, items))


def screen(date: str, cfg: dict, dates: list | None = None, notices_on: bool = True, log=None) -> dict:
    log = log or (lambda msg: print(msg, file=sys.stderr))
    dates = dates or trade_dates()
    if date not in dates:
        raise DataError(f"{date} 不是交易日")
    nxt = next_trade(dates, date)
    pool = ths_pool(date)
    if not pool.get("info"):
        raise DataError(f"同花顺涨停池 {date} 为空（还没收盘、非交易日或数据源异常）")
    try:
        blocks = ths_blocks(date)
    except Exception as exc:
        log(f"[题材] 同花顺热点板块拉取失败（{type(exc).__name__}），只用涨停原因标签聚类")
        blocks = []
    em_rows = em_zt_pool(date)
    em_prev = em_prev_pool(date)
    recs = build_records(pool, em_rows)
    assign_streaks(recs, date, dates)
    clusters = build_themes(recs, blocks, cfg)

    excluded, survivors = [], []
    for r in recs:
        why = cheap_reasons(r, cfg)
        if why:
            r["excluded"] = why
            excluded.append(r)
        else:
            survivors.append(r)

    # 量能：只给过了初筛的票拉日K
    start = (dt.date.fromisoformat(date) - dt.timedelta(days=45)).isoformat()
    feats = _parallel(lambda r: volume_feats(bars(r["code"], start, date), date), survivors)
    kept = []
    for r, f in zip(survivors, feats):
        r.update(f or {"vr": None, "sr": None, "vr_prev": None})
        r["vol_missing"] = f is None
        if f and r["streak"] == 1 and f["vr"] is not None and f["vr"] < cfg["min_first_vr"]:
            r["excluded"] = [f"首板没放量(量比{f['vr']:.2f})"]
            excluded.append(r)
        else:
            kept.append(r)

    # 排雷：公告 + 解禁（只看 date 当天及以前公布的公告）
    notice_status = "未排雷(--no-notice)" if not notices_on else "初筛后无候选，无需排雷"
    if notices_on and kept:
        lo_unlock = (dt.date.fromisoformat(date) + dt.timedelta(days=1)).isoformat()
        hi_unlock = (dt.date.fromisoformat(date) + dt.timedelta(days=cfg["unlock_days"])).isoformat()
        unlock_map = unlocks(lo_unlock, hi_unlock)

        def fetch_notice(r):
            try:
                return notices(r["code"])
            except Exception:
                return None

        got = _parallel(fetch_notice, kept)
        clean, failed = [], 0
        for r, items in zip(kept, got):
            strong, weak = classify_notices(items or [], date, cfg["notice_days"])
            if items is None:
                failed += 1
                weak = ["公告拉取失败，未排雷"]
            for day, ratio, amt in (unlock_map or {}).get(r["code"], []):
                if ratio >= cfg["unlock_ratio"]:
                    strong.append(f"解禁:{day} 占流通{ratio * 100:.1f}% 约{amt:.1f}亿")
            r["risk"], r["notes"] = strong, weak
            if strong:
                r["excluded"] = ["利空:" + "；".join(strong[:2])]
                excluded.append(r)
            else:
                clean.append(r)
        kept = clean
        notice_status = f"已查公告{len(got) - failed}只" + (f"，{failed}只拉取失败" if failed else "") + \
                        ("；解禁日程拉取失败" if unlock_map is None else "")
    else:
        for r in kept:
            r["risk"], r["notes"] = [], []

    rank_in_theme(kept)
    pct_of = {}
    for r in kept:
        parts = score_parts(r)
        r["parts"], r["score"] = parts, sum(parts.values())
        pct_of[r["code"]] = limit_pct(r["code"], r["name"])
        if r["close"]:
            r["next_limit"] = limit_price(r["close"], pct_of[r["code"]])
            r["premium_line"] = round(r["next_limit"] * 1.03, 2)
    kept.sort(key=lambda r: (-r["score"], r["first"] or "99", r["float_cap"]))

    luc = (pool.get("limit_up_count") or {})
    ldc = (pool.get("limit_down_count") or {})
    ladder = Counter(min(r["streak"], 5) for r in recs)
    highest = max(recs, key=lambda r: (r["streak"], r["first"] and -trade_minute(r["first"]) or 0))
    sent = {
        "zt": (luc.get("today") or {}).get("num"), "touched": (luc.get("today") or {}).get("history_num"),
        "seal_rate": (luc.get("today") or {}).get("rate"), "broken": (luc.get("today") or {}).get("open_num"),
        "dt": (ldc.get("today") or {}).get("num"),
        "zt_prev": (luc.get("yesterday") or {}).get("num"), "dt_prev": (ldc.get("yesterday") or {}).get("num"),
        "ladder": {k: ladder.get(k, 0) for k in range(1, 6)},
        "highest": f"{highest['name']}({highest['streak']}板)",
    }
    if em_prev:
        chgs = [_f(x.get("涨跌幅")) for x in em_prev if _f(x.get("涨跌幅")) is not None]
        if chgs:
            sent["prev_avg"] = sum(chgs) / len(chgs)
            sent["prev_up"] = sum(1 for c in chgs if c > 0) / len(chgs)
            sent["prev_n"] = len(chgs)
    return {
        "date": date, "next": nxt, "cfg": cfg, "sentiment": sent,
        "clusters": [{"name": c["name"], "n": len(c["members"]), "chg": c["chg"], "blocks": c["blocks"],
                      "core": c["core"], "family": c["family"], "kind": c["kind"]} for c in clusters],
        "candidates": kept, "top": kept[:cfg["top"]], "excluded": excluded, "all": recs,
        "sources": {"em_zt": em_rows is not None, "em_prev": em_prev is not None, "blocks": bool(blocks),
                    "notice": notice_status},
    }


# ---------------------------------------------------------------- 输出

def _stage(r):
    return "二板" if r["streak"] == 1 else "三板"


def _vol_text(r):
    if r.get("vol_missing"):
        return "量能缺"
    if r["streak"] == 1:
        return f"量比{r['vr']:.1f}" if r.get("vr") is not None else "量比?"
    return f"较首板{r['sr']:.2f}倍" if r.get("sr") is not None else "量比?"


def _open_text(r):
    if not r["opened"]:
        return "未开板"
    if r["em_opens"] is not None:
        return f"开{r['em_opens']}次"
    return "开过板"


def _excl_bucket(reason: str) -> str:
    return re.split(r"[(:（]", reason, maxsplit=1)[0]


def render(res: dict) -> str:
    s, out = res["sentiment"], []
    out.append(f"# 二三板接力离线筛选 · {res['date']} 收盘 → 次日 {res['next'] or '?'} 打板观察\n")
    src = res["sources"]
    out.append("数据：同花顺涨停池/热点板块" + (" + 东财涨停池(炸板次数/连板)" if src["em_zt"] else "（东财涨停池缺，开板次数按同花顺回封标记估）")
               + " + 东财日K + " + src["notice"] + f"；缓存 {DATA_DIR}\n")
    out.append("## 情绪（背景，不是硬门槛）\n")
    seal = f"{s['seal_rate'] * 100:.0f}%" if s.get("seal_rate") is not None else "?"
    out.append(f"- 涨停 {s.get('zt')} · 曾涨停 {s.get('touched')} · 封板率 {seal} · 炸板 {s.get('broken')} · 跌停 {s.get('dt')}"
               f"（上一交易日：涨停 {s.get('zt_prev')} / 跌停 {s.get('dt_prev')}）")
    if "prev_avg" in s:
        out.append(f"- 上一交易日涨停今日表现：{s['prev_n']} 只，平均 {s['prev_avg']:+.1f}%，上涨占 {s['prev_up'] * 100:.0f}%")
    lad = s["ladder"]
    out.append(f"- 连板梯队：首板 {lad[1]} · 2板 {lad[2]} · 3板 {lad[3]} · 4板 {lad[4]} · 5板+ {lad[5]}；最高 {s['highest']}\n")
    out.append(f"## 主线题材（当日涨停 ≥{res['cfg']['min_theme']} 家，热点板块涨幅 ≥{res['cfg']['min_block_chg']}%）\n")
    if not res["clusters"]:
        out.append("- 没有达标题材：今天没有板块共振，按方法应空仓观望。\n")
    for i, c in enumerate(res["clusters"][:8], 1):
        chg = f"（板块 {c['chg']:+.1f}%）" if c["chg"] is not None else "（涨停原因标签）"
        if c["kind"] == "cluster":
            extra = "；核心标签 " + "、".join(c["core"][:6])
        elif c["kind"] == "block":
            extra = "；按板块成员计（涨停原因写法不统一）"
        else:
            extra = ""
        out.append(f"{i}. {c['name']}{chg} · 涨停 {c['n']} 家{extra}")
    out.append("")
    cands = res["candidates"]
    out.append(f"## Top {len(res['top'])}（次日重点盯：同题材谁最快封板、10 点前封死且封后不开，打它）\n")
    if not cands:
        out.append("- 无候选：按方法空仓。\n")
    else:
        out.append("| # | 股票 | 次日 | 题材(涨停家数) | 首封/末封 | 开板 | 量能 | 换手 | 流通 | 分 | 次日涨停价 | +3%溢价线 |")
        out.append("|---|---|---|---|---|---|---|---|---|---:|---:|---:|")
        for i, r in enumerate(res["top"], 1):
            out.append(f"| {i} | {r['code']} {r['name']} | {_stage(r)} | {r['theme']}({r['theme_n']}) | "
                       f"{(r['first'] or '')[:5]}/{(r['last'] or '')[:5]} | {_open_text(r)} | {_vol_text(r)} | "
                       f"{r['turnover']:.1f}% | {r['float_cap']:.0f}亿 | {r['score']} | {r.get('next_limit', '')} | "
                       f"{r.get('premium_line', '')} |")
        out.append("\n分数构成：题材30 + 封板时间20 + 不开板10 + 量能20 + 题材内先手10 + 市值10。"
                   "+3%溢价线 = 次日涨停价×1.03，买入后第二天开盘溢价不到它就走。\n")
        out.append("## 全部候选（按题材分组）\n")
        by = defaultdict(list)
        for r in cands:
            by[r["theme"]].append(r)
        for theme, group in sorted(by.items(), key=lambda kv: (-kv[1][0]["theme_n"], -kv[1][0]["score"])):
            out.append(f"### {theme}（涨停 {group[0]['theme_n']} 家）")
            for r in group:
                p = r["parts"]
                note = f"；提示 {r['notes'][0]}" if r.get("notes") else ""
                out.append(f"- {r['score']:>3}  {r['code']} {r['name']}  {_stage(r)}候选  首封{(r['first'] or '')[:5]} "
                           f"{_open_text(r)} {_vol_text(r)} 换手{r['turnover']:.1f}% 流通{r['float_cap']:.0f}亿  "
                           f"[题{p['题材']}/封{p['封板']}/稳{p['不开板']}/量{p['量能']}/先{p['先手']}/市{p['市值']}]  "
                           f"原因：{r['reason']}{note}")
            out.append("")
    cnt = Counter(_excl_bucket(r["excluded"][0]) for r in res["excluded"])
    out.append("## 排除统计（每只只记第一条原因）\n")
    out.append("- " + " · ".join(f"{k} {v}" for k, v in cnt.most_common()))
    risky = [r for r in res["excluded"] if r["excluded"][0].startswith("利空")]
    for r in risky:
        out.append(f"  - {r['code']} {r['name']}：{r['excluded'][0]}")
    high = [r for r in res["excluded"] if r["streak"] >= 3]
    if high:
        out.append("- 高标（只看高度，不参与）：" + "、".join(
            f"{r['name']}{r['streak']}板" for r in sorted(high, key=lambda r: -r["streak"])[:8]))
    out.append("\n提醒：这是收盘后的观察名单，不是买入指令。次日只打盘中确认的那只（板块内最快、10 点前封死、封后不开）；"
               "没有共振、看不懂就空仓。")
    return "\n".join(out)


def _jsonable(res: dict) -> dict:
    keys = ("code", "name", "streak", "theme", "theme_n", "first", "last", "type", "opened", "em_opens", "gap",
            "turnover", "float_cap", "close", "vr", "sr", "score", "parts", "next_limit", "premium_line",
            "reason", "risk", "notes", "excluded", "high_days")
    pick = lambda r: {k: r.get(k) for k in keys if k in r}
    return {"date": res["date"], "next": res["next"], "sentiment": res["sentiment"], "clusters": res["clusters"],
            "top": [pick(r) for r in res["top"]], "candidates": [pick(r) for r in res["candidates"]],
            "excluded": [pick(r) for r in res["excluded"]], "sources": res["sources"]}


def archive(res: dict) -> str:
    p = _path("picks", f"{res['date'].replace('-', '')}.csv")
    cols = ["rank", "code", "name", "stage", "theme", "theme_n", "score", "first", "last", "opened", "turnover",
            "float_cap", "vr", "sr", "next_limit", "premium_line", "reason"]
    with open(p, "w", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(cols)
        for i, r in enumerate(res["candidates"], 1):
            w.writerow([i, r["code"], r["name"], _stage(r), r["theme"], r["theme_n"], r["score"], r["first"], r["last"],
                        r["opened"], f"{r['turnover']:.2f}", f"{r['float_cap']:.1f}",
                        "" if r.get("vr") is None else f"{r['vr']:.2f}", "" if r.get("sr") is None else f"{r['sr']:.2f}",
                        r.get("next_limit", ""), r.get("premium_line", ""), r["reason"]])
    return p


# ---------------------------------------------------------------- 回测

def outcome(code: str, date: str, nxt: str) -> dict | None:
    """date 收盘 → nxt 当天：开盘/最高/收盘相对 date 收盘的涨幅(%)。"""
    start = (dt.date.fromisoformat(date) - dt.timedelta(days=10)).isoformat()
    rows = {r["date"]: r for r in bars(code, start, nxt)}
    a, b = rows.get(date), rows.get(nxt)
    if not a or not b or not a["close"]:
        return None
    c0 = a["close"]
    return {"open": (b["open"] / c0 - 1) * 100, "high": (b["high"] / c0 - 1) * 100, "close": (b["close"] / c0 - 1) * 100}


def backtest(days: int, cfg: dict, success: float, end: str | None = None) -> dict:
    dates = trade_dates()
    last = end or latest_complete(dates)
    if last not in dates:
        raise DataError(f"{last} 不是交易日")
    idx = dates.index(last)
    tests = dates[max(0, idx - days):idx]  # 每个 T 的次日都 ≤ last，结果可验证
    out = []
    for T in tests:
        nxt = next_trade(dates, T)
        print(f"[回测] {T} → {nxt}", file=sys.stderr)
        res = screen(T, cfg, dates=dates, log=lambda m: print("  " + m, file=sys.stderr))
        nxt_codes = {str(x.get("code")).zfill(6) for x in (ths_pool(nxt).get("info") or [])}
        rows = []
        for i, r in enumerate(res["top"], 1):
            o = outcome(r["code"], T, nxt)
            rows.append({"rank": i, "code": r["code"], "name": r["name"], "stage": _stage(r), "score": r["score"],
                         "theme": r["theme"], "o": o, "board": r["code"] in nxt_codes,
                         "ok": (o is not None and o["close"] >= success)})
        prev = em_prev_pool(nxt) or []
        chg = {str(x.get("代码")).zfill(6): _f(x.get("涨跌幅")) for x in prev}
        base_all = [chg[r["code"]] for r in res["all"] if chg.get(r["code"]) is not None]
        base_cand = [chg[r["code"]] for r in res["candidates"] if chg.get(r["code"]) is not None]
        out.append({"date": T, "next": nxt, "top": rows, "n_cand": len(res["candidates"]), "n_zt": len(res["all"]),
                    "base_all": base_all, "base_cand": base_cand, "clusters": res["clusters"][:3],
                    "sentiment": res["sentiment"]})
    return {"days": out, "success": success, "top": cfg["top"], "end": last}


def render_backtest(bt: dict) -> str:
    s = bt["success"]
    out = [f"# 二三板接力 top{bt['top']} 回测 · 截至 {bt['end']}（次日收盘涨幅 ≥ +{s:g}% 算成功）\n",
           "| 筛选日 | 次日 | # | 股票 | 次日 | 分 | 次日开盘 | 次日最高 | 次日收盘 | 次日涨停 | 成功 |",
           "|---|---|---|---|---|---:|---:|---:|---:|---|---|"]
    picks = []
    for d in bt["days"]:
        if not d["top"]:
            out.append(f"| {d['date']} | {d['next']} | - | 无候选（空仓） | | | | | | | |")
        for r in d["top"]:
            o = r["o"]
            fmt = (lambda k: f"{o[k]:+.1f}%") if o else (lambda k: "缺")
            out.append(f"| {d['date']} | {d['next']} | {r['rank']} | {r['code']} {r['name']} | {r['stage']} | {r['score']} | "
                       f"{fmt('open')} | {fmt('high')} | {fmt('close')} | {'是' if r['board'] else '否'} | "
                       f"{'✓' if r['ok'] else '✗'} |")
            picks.append(r)
    valid = [r for r in picks if r["o"]]
    out.append("")
    if valid:
        n = len(valid)
        ok = sum(r["ok"] for r in valid)
        hi = sum(r["o"]["high"] >= s for r in valid)
        bd = sum(r["board"] for r in valid)
        avg = sum(r["o"]["close"] for r in valid) / n
        out.append(f"- **成功率（次日收盘 ≥ +{s:g}%）：{ok}/{n} = {ok / n * 100:.0f}%**")
        out.append(f"- 次日盘中最高触及 +{s:g}%：{hi}/{n} = {hi / n * 100:.0f}%；次日涨停（晋级）：{bd}/{n} = {bd / n * 100:.0f}%")
        out.append(f"- 次日收盘平均涨幅：{avg:+.2f}%")
    all_c = [c for d in bt["days"] for c in d["base_cand"]]
    all_z = [c for d in bt["days"] for c in d["base_all"]]
    if all_c:
        out.append(f"- 对照·全部候选（未排序）：次日收盘 ≥ +{s:g}% 占 {sum(c >= s for c in all_c) / len(all_c) * 100:.0f}%"
                   f"（{len(all_c)} 只次，平均 {sum(all_c) / len(all_c):+.2f}%）")
    if all_z:
        out.append(f"- 对照·当日全部涨停股：次日收盘 ≥ +{s:g}% 占 {sum(c >= s for c in all_z) / len(all_z) * 100:.0f}%"
                   f"（{len(all_z)} 只次，平均 {sum(all_z) / len(all_z):+.2f}%）")
    out.append("\n口径：筛选只用筛选日及以前的数据（公告按发布日截断）；次日涨幅相对筛选日收盘（前复权）。"
               "样本只有几个交易日，只能看形状，不能当胜率。")
    return "\n".join(out)


# ---------------------------------------------------------------- CLI

def _cfg_from(args) -> dict:
    cfg = dict(DEFAULTS)
    for k in ("top", "min_theme", "min_block_chg", "max_float_cap", "min_first_turnover"):
        v = getattr(args, k, None)
        if v is not None:
            cfg[k] = v
    cfg["include_688"] = bool(getattr(args, "include_688", False))
    return cfg


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="二三板接力收盘后离线筛选（两个小馒头打法）")
    sub = ap.add_subparsers(dest="cmd")
    for name in ("screen", "backtest"):
        sp = sub.add_parser(name)
        sp.add_argument("--top", type=int)
        sp.add_argument("--min-theme", dest="min_theme", type=int)
        sp.add_argument("--min-block-chg", dest="min_block_chg", type=float)
        sp.add_argument("--max-float-cap", dest="max_float_cap", type=float, help="流通市值上限(亿)")
        sp.add_argument("--min-first-turnover", dest="min_first_turnover", type=float)
        sp.add_argument("--include-688", dest="include_688", action="store_true")
        if name == "screen":
            sp.add_argument("--date", help="YYYY-MM-DD，缺省=最近完整交易日")
            sp.add_argument("--json", action="store_true")
            sp.add_argument("--md-out", dest="md_out")
            sp.add_argument("--no-notice", dest="no_notice", action="store_true", help="跳过公告/解禁排雷")
        else:
            sp.add_argument("--days", type=int, default=7)
            sp.add_argument("--success", type=float, default=3.0, help="次日收盘涨幅达到多少(%)算成功")
            sp.add_argument("--end", help="最后一个次日（含），缺省=最近完整交易日")
            sp.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)
    if not args.cmd:
        ap.print_help()
        return 0
    _patch_requests_timeout()
    cfg = _cfg_from(args)
    try:
        if args.cmd == "screen":
            dates = trade_dates()
            date = args.date or latest_complete(dates)
            if re.fullmatch(r"\d{8}", date):
                date = f"{date[:4]}-{date[4:6]}-{date[6:]}"
            res = screen(date, cfg, dates=dates, notices_on=not args.no_notice)
            path = archive(res)
            text = render(res)
            if args.md_out:
                os.makedirs(os.path.dirname(os.path.abspath(args.md_out)), exist_ok=True)
                with open(args.md_out, "w", encoding="utf-8") as fh:
                    fh.write(text + "\n")
            if args.json:
                print(json.dumps(_jsonable(res), ensure_ascii=False, indent=1, default=list))
            else:
                print(text)
                print(f"\n（候选已存档 {path}）")
        else:
            end = args.end
            if end and re.fullmatch(r"\d{8}", end):
                end = f"{end[:4]}-{end[4:6]}-{end[6:]}"
            bt = backtest(args.days, cfg, args.success, end)
            p = _path("backtest", f"top{cfg['top']}_{bt['end'].replace('-', '')}_{args.days}d.json")
            _dump_json(p, bt)
            if args.json:
                print(json.dumps(bt, ensure_ascii=False, indent=1))
            else:
                print(render_backtest(bt))
                print(f"\n（明细已存档 {p}）")
    except DataError as exc:
        print(f"✗ {exc}", file=sys.stderr)
        return 2
    except ImportError as exc:
        print(f"✗ 缺依赖 {exc}：python3 -m pip install akshare pandas requests", file=sys.stderr)
        return 3
    return 0


# ---------------------------------------------------------------- 离线自检

def selftest() -> None:
    assert trade_minute("09:25:00") == 0 and trade_minute("09:35:00") == 5
    assert trade_minute("13:00:00") == 120 and trade_minute("14:00:00") == 180
    assert trade_minute("11:40:00") == 120
    assert hms_of("1793602515") == "14:55:15"
    assert em_hms("092500") == "09:25:00" and em_hms(93024) == "09:30:24"
    assert limit_price(9.39, 0.10) == 10.33 and limit_price(30.78, 0.20) == 36.94
    assert limit_price(4.45, 0.10) == 4.90 and limit_price(10.05, 0.10) == 11.06
    assert limit_pct("300788", "中信出版") == 0.20 and limit_pct("600259", "中稀有色") == 0.10
    assert limit_pct("000001", "*ST某某") == 0.05
    assert parse_high_days("首板") == (1, 1) and parse_high_days("9天5板") == (9, 5)
    assert NON_THEME_TAG.search("三季报增长") and NON_THEME_TAG.search("控制权变更")
    assert not NON_THEME_TAG.search("AI短剧") and not NON_THEME_TAG.search("“羊”字辈")
    assert is_complete("2026-11-02", dt.datetime(2026, 11, 2, 15, 31))
    assert not is_complete("2026-11-02", dt.datetime(2026, 11, 2, 15, 0))
    assert latest_complete(["2026-10-30", "2026-11-02", "2026-11-03"], dt.datetime(2026, 11, 3, 9, 0)) == "2026-11-02"
    assert latest_complete(["2026-10-30", "2026-11-02"], dt.datetime(2026, 11, 2, 17, 0)) == "2026-11-02"

    # 公告排雷：窗口截断 + 豁免
    items = [("2026-10-20", "关于持股5%以上股东减持股份预披露公告"),
             ("2026-10-21", "关于控股股东减持计划实施完毕的公告"),
             ("2026-10-25", "关于股票交易异常波动的公告"),
             ("2026-11-03", "关于收到问询函的公告"),            # 晚于 asof，不能用
             ("2026-08-01", "2026年半年度业绩预亏公告")]       # 超出回看窗口
    strong, weak = classify_notices(items, "2026-11-02", 30)
    assert len(strong) == 1 and strong[0].startswith("减持"), strong
    assert weak == [], weak

    # 合成一天：AI 簇 4 只 + 独苗 1 只
    ts = lambda hm: str(int(dt.datetime(2026, 11, 2, int(hm[:2]), int(hm[3:5]), tzinfo=BJ).timestamp()))
    info = []
    spec = [("000001", "甲", "09:31", "09:31", "FIRST_LIMIT", "AI短剧+影视", 8.0, 40e8, "首板", "换手板"),
            ("000002", "乙", "09:45", "10:20", "LIMIT_BACK", "AI短剧+IP", 12.0, 60e8, "首板", "换手板"),
            ("000003", "丙", "10:05", "10:05", "FIRST_LIMIT", "AI短剧+游戏", 2.0, 30e8, "首板", "换手板"),
            ("000004", "丁", "14:40", "14:45", "FIRST_LIMIT", "AI短剧+出版", 9.0, 30e8, "首板", "换手板"),
            ("000005", "戊", "09:25", "09:25", "FIRST_LIMIT", "AI短剧+传媒", 1.0, 30e8, "2天2板", "一字板"),
            ("000006", "己", "09:40", "09:40", "FIRST_LIMIT", "海峡两岸+服装", 9.0, 30e8, "首板", "换手板"),
            ("000007", "庚", "09:50", "09:55", "LIMIT_BACK", "AI短剧+算力", 6.0, 500e8, "2天2板", "换手板")]
    for code, name, f, l, tag, reason, to, cap, hd, typ in spec:
        info.append({"code": code, "name": name, "latest": 10.0, "change_rate": 10.0, "turnover_rate": to,
                     "currency_value": cap, "order_amount": 1e7, "first_limit_up_time": ts(f),
                     "last_limit_up_time": ts(l), "limit_up_type": typ, "high_days": hd, "reason_type": reason,
                     "change_tag": tag, "is_again_limit": 1 if tag == "LIMIT_BACK" else 0})
    recs = build_records({"info": info}, None)
    assign_streaks(recs, "2026-11-02", ["2026-10-30", "2026-11-02"], pool_fn=lambda d: {"info": []})
    blocks = [{"name": "AI视频", "change": 8.0, "limit_up_num": 6,
               "members": ["000001", "000002", "000003", "000004", "000005", "000007"]},
              {"name": "数字经济", "change": 0.5, "limit_up_num": 3, "members": ["000001", "000006", "000002"]}]
    cfg = dict(DEFAULTS)
    clusters = build_themes(recs, blocks, cfg)
    assert clusters[0]["name"] == "AI视频" and len(clusters[0]["members"]) == 6, clusters
    by = {r["code"]: r for r in recs}
    assert by["000006"]["theme"] is None                         # 板块涨幅不够 + 标签不成簇 → 独苗
    assert by["000002"]["gap"] == 35 and by["000002"]["opened"]
    reasons = {r["code"]: cheap_reasons(r, cfg) for r in recs}
    assert reasons["000001"] == [], reasons["000001"]
    assert reasons["000002"] == [], reasons["000002"]            # 开过一次板、35 分钟回封：不算烂板
    assert any(x.startswith("首板换手不足") for x in reasons["000003"])
    assert any(x.startswith("尾盘偷袭") for x in reasons["000004"])
    assert any(x.startswith("一字板") for x in reasons["000005"])
    assert any(x.startswith("独苗") for x in reasons["000006"])
    assert any(x.startswith("大盘股") for x in reasons["000007"])
    by["000002"]["gap"] = 75
    assert any(x.startswith("烂板") for x in cheap_reasons(by["000002"], cfg))
    by["000002"]["gap"] = 35

    # 量能与打分
    rows = [{"date": f"2026-10-{d:02d}", "volume": 100.0, "close": 9.0} for d in range(20, 31)]
    rows.append({"date": "2026-11-02", "volume": 320.0, "close": 10.0})
    vf = volume_feats(rows, "2026-11-02")
    assert abs(vf["vr"] - 3.2) < 1e-9 and abs(vf["sr"] - 3.2) < 1e-9
    assert volume_feats(rows, "2026-11-03") is None
    a, b = by["000001"], by["000002"]
    a.update(vr=3.2, sr=None)
    b.update(vr=1.6, sr=None)
    rank_in_theme([a, b])
    assert a["theme_rank"] == 1 and b["theme_rank"] == 2
    pa, pb = score_parts(a), score_parts(b)
    assert pa == {"题材": 20, "封板": 20, "不开板": 10, "量能": 20, "先手": 10, "市值": 10}, pa
    assert sum(pb.values()) < sum(pa.values())
    two = dict(a, streak=2, sr=0.7)
    assert score_parts(two)["量能"] == 20
    two["sr"] = 2.5
    assert score_parts(two)["量能"] == 0

    # 连板回溯：N天M板(N≠M) 需要看前一日
    hist = {"2026-10-30": {"info": [{"code": "000009", "high_days": "2天2板"}]}}
    r9 = {"code": "000009", "hd": (4, 3), "em_streak": None}
    assign_streaks([r9], "2026-11-02", ["2026-10-29", "2026-10-30", "2026-11-02"],
                   pool_fn=lambda d: hist.get(d, {"info": []}))
    assert r9["streak"] == 3, r9
    r10 = {"code": "000010", "hd": (4, 2), "em_streak": None}
    assign_streaks([r10], "2026-11-02", ["2026-10-30", "2026-11-02"], pool_fn=lambda d: hist.get(d, {"info": []}))
    assert r10["streak"] == 1
    print("board_relay 自检通过 ✓")


if __name__ == "__main__":
    if len(sys.argv) == 1:
        selftest()
        sys.exit(0)
    sys.exit(main())
