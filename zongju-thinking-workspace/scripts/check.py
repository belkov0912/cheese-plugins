#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""zongju-thinking 量化评分：把"假大空"变成可测指标。"""
import json, re, sys, os, glob

# 1. 空话短语（换个公司名照样成立的句子）
FLUFF = ["空间广阔","前景广阔","格局有望优化","格局优化","先发优势","值得重点关注","值得关注",
         "长期看好","战略意义","受益于","具备优势","持续受益","景气度高","赛道优质",
         "护城河深厚","龙头地位稳固","成长性良好","potential","大有可为","想象空间"]

# 2. 旧版框架黑话（列名词代替事实）
JARGON = ["反身性","护栏指标","代理指标","资本周期","期权价值","厚尾","第一性原理","单位经济性",
          "采用扩散","控制点","商品化","基准率","参照类","路径依赖","飞轮","博弈激励","治理/代理",
          "二阶影响","约束层级","目标函数","可知性","信噪比","前视偏差","损益不对称","负和"]

# 3. 归档六档
BUCKETS = ["可建仓","等回撤","等数据","题材期权","事件博弈","排除","证据不足"]

NUM = re.compile(r'\d+(?:\.\d+)?\s*(?:%|％|亿元|亿|万元|万|倍|x|X|元|个百分点|GWh|MW|pct)')
DATE = re.compile(r'(?:20\d{2}[-/年]\d{1,2}|20\d{2}\s*年|20\d{2}H[12]|20\d{2}Q[1-4]|[12]?\d月\d{1,2}日|\bQ[1-4]\b|\bH[12]\b)')
URL = re.compile(r'https?://')

def count_any(text, words):
    return sum(text.count(w) for w in words)

def check(path):
    t = open(path, encoding='utf-8').read()
    body = re.sub(r'\s', '', t)
    chars = len(body)
    nums = NUM.findall(t)
    dates = DATE.findall(t)
    fluff = count_any(t, FLUFF)
    jargon = count_any(t, JARGON)
    buckets = [b for b in BUCKETS if b in t]
    has_falsify = bool(re.search(r'证伪|推翻|说明我错|判断错了|证明.{0,4}错', t))
    has_next = bool(re.search(r'下一个数据|下一个可验证|最该核对|等哪|待验证时点|验证时点|核对', t))
    urls = len(URL.findall(t))

    m = {
        "chars": chars,
        "num_count": len(nums),
        "num_per_100char": round(len(nums) / max(chars, 1) * 100, 2),
        "date_count": len(dates),
        "fluff_count": fluff,
        "fluff_per_1000char": round(fluff / max(chars, 1) * 1000, 2),
        "jargon_count": jargon,
        "jargon_per_1000char": round(jargon / max(chars, 1) * 1000, 2),
        "buckets_found": buckets,
        "has_falsification": has_falsify,
        "has_next_datapoint": has_next,
        "source_url_count": urls,
    }
    a = [
        ("数字密度达标：每100字≥1.5个带单位的具体数字", m["num_per_100char"] >= 1.5,
         f'{m["num_per_100char"]} 个/100字（共 {m["num_count"]} 个数字 / {chars} 字）'),
        ("空话极少：空话短语总数 ≤2", fluff <= 2, f'命中 {fluff} 次'),
        ("不靠框架黑话充数：框架名词总数 ≤3", jargon <= 3, f'命中 {jargon} 次'),
        ("有明确归档结论（可建仓/等回撤/等数据/题材期权/事件博弈/排除/证据不足）",
         len(buckets) > 0, f'命中 {buckets or "无"}'),
        ("有可核对的证伪点", has_falsify, "找到" if has_falsify else "未找到"),
        ("有下一个可验证数据/时点", has_next, "找到" if has_next else "未找到"),
        ("数据带时点：日期/季度标记 ≥5 处", len(dates) >= 5, f'{len(dates)} 处'),
        ("附了来源链接 ≥3 条", urls >= 3, f'{urls} 条'),
    ]
    return m, a

if __name__ == "__main__":
    root = sys.argv[1]
    out = {}
    for ed in sorted(glob.glob(os.path.join(root, "eval-*"))):
        for cfg in ["with_skill", "old_skill", "without_skill"]:
            files = glob.glob(os.path.join(ed, cfg, "outputs", "*.md"))
            if not files: continue
            m, a = check(files[0])
            run_id = f"{os.path.basename(ed)}-{cfg}"
            passed = sum(1 for _, p, _ in a if p)
            out[run_id] = {"metrics": m, "passed": passed, "total": len(a),
                           "expectations": [{"text": t, "passed": bool(p), "evidence": e} for t, p, e in a]}
            gp = os.path.join(ed, cfg, "grading.json")
            json.dump({"run_id": run_id, "expectations": out[run_id]["expectations"],
                       "metrics": m, "score": f"{passed}/{len(a)}"},
                      open(gp, "w"), ensure_ascii=False, indent=2)
    print(json.dumps(out, ensure_ascii=False, indent=2))
