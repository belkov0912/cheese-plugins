"""R0 本地行情仓（插件自带版，扫描器 store.py 同源裁剪）。
数据目录 = $R0_DATA_DIR，缺省 ~/.r0-data —— **数据永远在用户本地**，不进插件、不进 git。
  backfill  全量拉全A股日K(后复权hfq) → parquet。断点续跑：已覆盖目标窗口的票自动跳过，中断重跑即可。
            新上市的票由 backfill 纳入（update 只保鲜已有票）。
  update    重抓所有"不新鲜"的票。注意：数据源(sina)每次调用都传该票全量历史，增量省不了网络——
            全市场隔天更新约 1-1.5 小时（和 backfill 同量级），请后台跑；只有少数票过期时才快。
  stat      看仓况
用法：
  python3 store.py backfill --days 400              # 首次全量，约 45-90 分钟
  python3 store.py backfill --days 400 --limit 300  # 先小跑试试
  python3 store.py update                           # 保鲜（全市场约 1-1.5 小时，后台跑）
  python3 store.py stat
"""
from __future__ import annotations
import os, sys, time, argparse, datetime as dt
import pandas as pd
import fetch

HERE = os.path.dirname(os.path.abspath(__file__))
COLS = ["date", "open", "high", "low", "close", "volume", "turnover"]
STORE = os.path.expanduser(os.environ.get("R0_DATA_DIR") or "~/.r0-data")
FAIL_ABORT = 10   # 连续抓取失败这么多只就中止：多半是断网/限流/缺依赖，硬扛只是空耗
MIN_R0_BARS = 50  # 少于这个数量会入仓但不参与 R0 打分，视为次新/短历史


def _ensure_store():
    try:
        os.makedirs(STORE, exist_ok=True)
    except FileExistsError:
        raise SystemExit(f"数据目录不可用：{STORE} 是个坏软链（指向不存在的位置）。删掉它或改 $R0_DATA_DIR。")
    except PermissionError:
        raise SystemExit(f"数据目录不可写：{STORE}。把 $R0_DATA_DIR 指向可写位置。")


def _need_parquet():
    try:
        import pandas as _pd
    except ImportError as e:
        pkg = getattr(e, "name", None) or str(e)
        raise SystemExit(f"缺依赖 {pkg}：python3 -m pip install -r {os.path.join(HERE, 'requirements.txt')}")
    try:
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            p = os.path.join(tmp, "check.parquet")
            _pd.DataFrame({"date": ["2000-01-01"], "close": [1.0]}).to_parquet(p)
            _pd.read_parquet(p)
    except Exception as e:
        raise SystemExit(f"parquet 读写不可用（通常缺 pyarrow）：python3 -m pip install pyarrow。原始错误：{type(e).__name__}: {e}")


def _need_akshare():
    try:
        import akshare  # noqa: F401
        import yaml  # noqa: F401
    except ImportError as e:
        pkg = getattr(e, "name", None) or str(e)
        raise SystemExit(f"缺依赖 {pkg}（这不是限流）：python3 -m pip install -r {os.path.join(HERE, 'requirements.txt')}")
    _need_parquet()


def _path(sym):
    return os.path.join(STORE, f"{sym}.parquet")


def _raw(sym, start, end):
    """akshare(sina) 拉 [start,end] 归一化 DataFrame；失败 None。
    价格用后复权(hfq)：除权缺口不再假装成暴跌（不复权时 送转日收盘-30% 会污染涨幅/突破）。
    选 hfq 不选 qfq：后复权的历史值不随未来除权改写，每日增量追加口径永远一致。"""
    import akshare as ak
    for a in range(3):
        try:
            df = ak.stock_zh_a_daily(symbol=sym, start_date=start.replace("-", ""),
                                     end_date=end.replace("-", ""), adjust="hfq")
            if df is None or len(df) < 1:
                return None
            df["date"] = df["date"].astype(str).str[:10]
            return df[COLS].copy()
        except Exception:
            time.sleep(0.4 * (a + 1))
    return None


def _data_end_date():
    """数据可信截止日：按**北京时间**（机器在别的时区也不会把盘中半根K线当收盘入仓），
    A股收盘(15:05)前只到昨天；周末回拨到周五（周末抓不到新K线，避免全仓空转）。
    节假日本地判断不了，会空转一轮拿不到新数据，无害。"""
    try:
        from zoneinfo import ZoneInfo
        now = dt.datetime.now(ZoneInfo("Asia/Shanghai"))
    except Exception:   # 个别系统缺 IANA 时区库：退回本机时间，东八区机器行为不变
        now = dt.datetime.now()
    target = now.date()
    if (now.hour, now.minute) < (15, 5):
        target -= dt.timedelta(days=1)
    while target.weekday() >= 5:
        target -= dt.timedelta(days=1)
    return target.isoformat()


def _save_universe(uni):
    """存一份 code→name 快照，给 r0.py 做名称解析。best-effort。"""
    try:
        pd.DataFrame(uni, columns=["code", "name"]).to_csv(
            os.path.join(STORE, "universe.csv"), index=False)
    except Exception:
        pass


def _merge_write(p, df):
    """与已有数据合并后写：--days 改小也不会把长历史截短。"""
    if os.path.exists(p):
        try:
            old = pd.read_parquet(p)
            df = (pd.concat([old, df], ignore_index=True)
                  .drop_duplicates("date", keep="last").sort_values("date").reset_index(drop=True))
        except Exception:
            pass
    df.to_parquet(p)


def _is_fresh_dates(d, end_ok_cut):
    """已有文件只要尾部够新就跳过；新股没有 400 天历史，强求起点会导致反复重抓。"""
    if d.empty:
        return False
    return str(d.max())[:10] >= end_ok_cut


def backfill(days, limit):
    _ensure_store()
    _need_akshare()
    start = (dt.date.today() - dt.timedelta(days=days)).isoformat()
    end = _data_end_date()
    try:
        uni = fetch.get_universe(limit=limit or None)
        _save_universe(uni)
    except ImportError as e:
        raise SystemExit(f"缺依赖：{e}。pip install akshare pandas pyarrow pyyaml")
    except Exception as e:
        print(f"[backfill] 票池接口失败({type(e).__name__})，回退用本地仓已有票列表", file=sys.stderr)
        uni = fetch.get_universe_offline(limit=limit or None)
        if not uni:
            print("[backfill] 本地也没有票列表。若是首次建仓：票池接口偶尔限流，过几分钟重跑。", file=sys.stderr)
            sys.exit(1)
    # 跳过判断用自然日容差：end 可能落在周末/长假，而K线只有交易日。
    # 只看尾部是否够新，不强求起点覆盖 start：新股天然没有更早历史，重抓也补不出来。
    end_ok_cut = (dt.date.fromisoformat(end) - dt.timedelta(days=9)).isoformat()
    print(f"[backfill] 全市场 {len(uni)} 只，窗口 {start}~{end}（断点续跑：已覆盖的自动跳过）", file=sys.stderr)
    ok = short = skip = fail = consec = 0
    t0 = time.time()
    for i, (sym, name) in enumerate(uni):
        p = _path(sym)
        if os.path.exists(p):
            try:
                d = pd.read_parquet(p, columns=["date"])["date"].astype(str)
                if _is_fresh_dates(d, end_ok_cut):
                    skip += 1
                    continue
            except ImportError:
                raise SystemExit("读 parquet 需要 pyarrow：pip install pyarrow")
            except Exception:
                pass
        df = _raw(sym, start, end)
        if df is not None and len(df) > 0:
            _merge_write(p, df)
            if len(df) < MIN_R0_BARS:
                short += 1
            else:
                ok += 1
            consec = 0
        else:
            fail += 1
            consec += 1
            if consec >= FAIL_ABORT:
                print(f"[backfill] 连续 {consec} 只抓取失败，中止（多半是断网/被限流）。"
                      f"已完成 {ok+short+skip} 只不会丢，恢复后重跑即可续上。", file=sys.stderr)
                sys.exit(2)
        if (i + 1) % 200 == 0:
            print(f"  {i+1}/{len(uni)}  新增{ok} 短史{short} 跳过{skip} 失败{fail}  {time.time()-t0:.0f}s", file=sys.stderr)
    print(f"[backfill] 完成 新增{ok} 短史{short} 跳过{skip} 失败{fail}  用时{(time.time()-t0)/60:.1f}分钟", file=sys.stderr)


def update():
    _ensure_store()
    _need_akshare()
    today = _data_end_date()
    files = [f for f in os.listdir(STORE) if f.endswith(".parquet")]
    if not files:
        print("[update] 本地仓为空，先跑： python3 store.py backfill --days 400", file=sys.stderr)
        sys.exit(1)
    print(f"[update] 本地仓 {len(files)} 只，目标补至 {today}。"
          f"提醒：数据源每次传全量历史，全市场隔天更新约 1-1.5 小时。", file=sys.stderr)
    fetched = fresh = fail = consec = 0
    t0 = time.time()
    for i, f in enumerate(files):
        sym = f[:-8]
        p = _path(sym)
        try:
            old = pd.read_parquet(p)
            last = str(old["date"].max())[:10]
            if last >= today:
                fresh += 1
                continue
            frm = (dt.date.fromisoformat(last) - dt.timedelta(days=3)).isoformat()
            new = _raw(sym, frm, today)
            if new is None or new.empty:
                fail += 1
                consec += 1
                if consec >= FAIL_ABORT:
                    print(f"[update] 连续 {consec} 只抓取失败，中止（多半是断网/被限流；也可能停牌票扎堆，重跑试试）。"
                          f"已更新 {fetched} 只不会丢。", file=sys.stderr)
                    sys.exit(2)
                continue
            consec = 0
            merged = (pd.concat([old, new], ignore_index=True)
                      .drop_duplicates("date", keep="last").sort_values("date").reset_index(drop=True))
            merged.to_parquet(p)
            fetched += 1
        except ImportError:
            raise SystemExit("读 parquet 需要 pyarrow：pip install pyarrow")
        except Exception:
            fail += 1
        if (i + 1) % 500 == 0:
            print(f"  {i+1}/{len(files)}  更新{fetched} 已新鲜{fresh} 失败{fail}  {time.time()-t0:.0f}s", file=sys.stderr)
    msg = f"[update] 完成 更新{fetched} 已新鲜{fresh} 失败{fail}  用时{(time.time()-t0)/60:.1f}分钟"
    if fail:
        msg += "（失败的多为停牌票或被限流，重跑可补）"
    print(msg, file=sys.stderr)


def load_frame(sym):
    """离线读本地仓 → 归一化 dict(list)；无则 None。打分走这个，不碰网络。"""
    p = _path(sym)
    if not os.path.exists(p):
        return None
    try:
        df = pd.read_parquet(p).sort_values("date").reset_index(drop=True)
        return {c: df[c].tolist() for c in COLS}
    except ImportError:
        raise SystemExit("读 parquet 需要 pyarrow：pip install pyarrow")
    except Exception:
        return None   # 单个文件损坏：当缺数据处理


def list_symbols():
    if not os.path.isdir(STORE):
        return []
    return [f[:-8] for f in os.listdir(STORE) if f.endswith(".parquet")]


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["backfill", "update", "stat"])
    ap.add_argument("--days", type=int, default=400)
    ap.add_argument("--limit", type=int, default=0)
    a = ap.parse_args()
    if a.cmd == "backfill":
        backfill(a.days, a.limit)
    elif a.cmd == "update":
        update()
    else:
        _need_parquet()
        syms = list_symbols()
        print(f"数据目录 {STORE}")
        print(f"本地仓 {len(syms)} 只")
        if syms:
            short = 0
            latest = []
            for sym in syms:
                try:
                    d = pd.read_parquet(_path(sym), columns=["date"])["date"].astype(str)
                    if len(d) < MIN_R0_BARS:
                        short += 1
                    if not d.empty:
                        latest.append(str(d.max())[:10])
                except Exception:
                    pass
            if latest:
                print("全仓最新日", max(latest))
            if short:
                print(f"短历史(<{MIN_R0_BARS}根，次新/暂不可打分) {short} 只")
            fr = load_frame(syms[0])
            print("样例(任一只，仅供参考)", syms[0], "根数", len(fr["date"]) if fr else None,
                  "末日", fr["date"][-1] if fr else None)
