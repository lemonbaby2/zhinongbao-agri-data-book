# -*- coding: utf-8 -*-
"""v8：注入卷八《决策与算法精准干预》到 book_data.json。

真实数值来自 guangdong_reform.json / guangdong.json；
作物保本参考来自 app/agent.py 的 CROP_REF，与运行时 Agent 工具保持一致。
"""
import importlib
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
BOOK = ROOT / "app" / "data" / "book_data.json"
GD = ROOT / "app" / "data" / "guangdong_reform.json"
GDC = ROOT / "app" / "data" / "guangdong.json"
sys.path.insert(0, str(ROOT / "content"))

PAGES_PER_CHAPTER = 20
CHAPTERS = 5

CROP_REF = {
    "水稻": {"yield": 480, "price": 2.7, "cost": 1150},
    "小麦": {"yield": 420, "price": 2.5, "cost": 950},
    "玉米": {"yield": 520, "price": 2.3, "cost": 900},
    "大豆": {"yield": 165, "price": 5.2, "cost": 620},
    "甘蔗": {"yield": 5200, "price": 0.52, "cost": 2400},
    "蔬菜": {"yield": 3200, "price": 2.6, "cost": 5200},
    "柑橘": {"yield": 2200, "price": 4.2, "cost": 4800},
    "茶叶": {"yield": 110, "price": 68.0, "cost": 4600},
}


def load(p):
    return json.load(open(p, encoding="utf-8"))


def fmt(v, digits=2):
    if v is None:
        return "—"
    if isinstance(v, int):
        return f"{v:,}"
    return f"{v:,.{digits}f}"


def build_tables(gd, gdc):
    series = gd["series"]
    inc = {int(y): v for y, v in series["rural_income"]}
    gross = {int(y): v for y, v in series["gross_output"]}
    grain = {int(y): v for y, v in series["grain_output"]}
    engel = {int(y): v for y, v in series["engel"]}
    years = [1978, 1985, 1990, 1995, 2000, 2005, 2010, 2015, 2018, 2020, 2025]
    decade = {
        "type": "table",
        "title": "广东农村经济的阶段结算（官方序列抽样年份）",
        "headers": ["年份", "人均收入(元)", "农林牧渔总产值(亿元)", "粮食(万吨)", "恩格尔系数(%)"],
        "rows": [[str(y), fmt(inc.get(y)), fmt(gross.get(y)), fmt(grain.get(y), 1),
                  fmt(engel.get(y), 1)] for y in years],
    }
    sec = {k: {int(y): v for y, v in vv} for k, vv in series["sector_output"].items()}
    sv = {k: sec[k].get(2018) for k in sec}
    tot = sum(v for v in sv.values() if v)
    label = {"agri": "农业（种植业）", "forestry": "林业", "livestock": "畜牧业",
             "fishery": "渔业", "service": "农林牧渔服务业"}
    sector = {
        "type": "table", "title": "2018 年广东农林牧渔五业产值与占比",
        "headers": ["行业", "产值(亿元)", "占比(%)"],
        "rows": [[label[k], fmt(sv[k]), f"{sv[k]/tot*100:.1f}"] for k in sv] +
                [["合计", fmt(tot), "100.0"]],
    }
    rows = []
    for city, info in (gdc.get("cities") or {}).items():
        last = next((r for r in info.get("series") or [] if r.get("year") == 2018), None)
        if not last:
            continue
        rows.append([city, (last.get("gdp_wan") or 0) / 10000.0,
                     last.get("agri_share"), info.get("region", "")])
    rows.sort(key=lambda r: -r[1])
    pick = rows[:8] + [["…", None, None, ""]] + rows[-4:]
    cities = {
        "type": "table", "title": "广东 21 市 GDP 与农业份额（2018 年面板，前八与后四）",
        "headers": ["城市", "GDP(亿元)", "第一产业占比(%)", "区域"],
        "rows": [[c, fmt(g) if g is not None else "…",
                  f"{a:.1f}" if isinstance(a, (int, float)) else "…", r] for c, g, a, r in pick],
    }

    # 作物保本参考：与 agent.CROP_REF 完全同源
    crop_rows = []
    for name, ref in CROP_REF.items():
        y, p, c = ref["yield"], ref["price"], ref["cost"]
        be_price = c / y if y else 0
        be_yield = c / p if p else 0
        profit = p * y - c
        margin = profit / (p * y) * 100 if p * y else 0
        level = ("低风险" if margin >= 25 else "中风险" if margin >= 8
                 else "偏高风险" if margin >= 0 else "高风险")
        crop_rows.append([name, fmt(y, 0), fmt(p), fmt(c, 0), fmt(be_price),
                          fmt(be_yield, 0), fmt(profit, 0), f"{margin:.1f}", level])
    crop_be = {
        "type": "table",
        "title": "主要作物保本参考（演示值，需按当地台账替换）",
        "headers": ["作物", "单产(公斤/亩)", "售价(元/公斤)", "成本(元/亩)",
                    "保本价(元)", "保本单产(公斤)", "亩利润(元)", "利润率(%)", "风险"],
        "rows": crop_rows,
    }
    review = {
        "type": "table",
        "title": "处方复核记录表（模板，需用户填写实测值）",
        "headers": ["处方编号", "干预动作", "预测值", "实测售价", "实测单产", "实测成本", "偏差", "结论"],
        "rows": [["RX-001", "示例：锁 30% 订单", "见处方", "待填", "待填", "待填", "待算", "待判"],
                 ["RX-002", "示例：统一采购降本", "见处方", "待填", "待填", "待填", "待算", "待判"],
                 ["RX-003", "示例：小面积试种", "见处方", "待填", "待填", "待填", "待算", "待判"]],
    }
    return {"decade": decade, "sector": sector, "cities": cities,
            "crop_break_even": crop_be, "decision_review": review}


def resolve(block, series, tables):
    t = block["type"]
    if t == "figure":
        key = block["series"]
        raw = series.get(key)
        if isinstance(raw, dict):
            pts = {}
            for k, vv in raw.items():
                for y, v in vv:
                    pts[int(y)] = pts.get(int(y), 0) + v
            raw = sorted(pts.items())
        raw = [[int(y), v] for y, v in raw if v is not None]
        lo = block.get("lo") or raw[0][0]
        hi = block.get("hi") or raw[-1][0]
        data = [[y, v] for y, v in raw if lo <= y <= hi]
        return {"type": "chart", "title": block["title"],
                "kind": block.get("kind", "line"), "data": data,
                "note": block.get("note", "")}
    if t == "datatable":
        tb = dict(tables[block["key"]])
        if block.get("title"):
            tb["title"] = block["title"]
        return tb
    if t == "table" and block.get("takeaway"):
        tb = dict(block)
        tb.pop("takeaway", None)
        tb["note"] = block["takeaway"]
        return tb
    return block


def cagr(gd, key, y0, y1):
    s = {int(y): v for y, v in gd["series"][key]}
    if y0 not in s or y1 not in s or not s[y0]:
        return None
    return ((s[y1] / s[y0]) ** (1 / (y1 - y0)) - 1) * 100


def main():
    gd = load(GD)
    gdc = load(GDC)
    series = gd["series"]
    tables = build_tables(gd, gdc)
    book = load(BOOK)

    # 用官方数据回填 KPI 与正文中的三个 CAGR（避免手抄漂移）
    inc_cagr = cagr(gd, "rural_income", 2015, 2025)
    gross_cagr = cagr(gd, "gross_output", 2015, 2025)
    grain_cagr = cagr(gd, "grain_output", 2015, 2025)
    print(f"CAGR 2015-2025: 收入 {inc_cagr:.3f}% / 总产值 {gross_cagr:.3f}% / 粮食 {grain_cagr:.3f}%")

    # 在指定页注入干净的数据图（替代杂乱 AI 拼贴），每章 2 张
    DIAG = {
        (1, 15): ("diagrams/algo_pipeline.png", "决策系统的五个环节：从状态向量到可执行动作"),
        (1, 13): ("diagrams/benchmark.png", "四类系统能力边界对照（数值为定性刻度，非精确评测）"),
        (2, 3): ("diagrams/decision_loop.png", "感知—预测—决策—干预—复核：数据决策闭环"),
        (2, 6): ("diagrams/cagr_compare.png", "广东三项指标复合增长率（2015—2025）"),
        (3, 3): ("diagrams/cagr_compare.png", "方法决定结论：三种增速的三个故事"),
        (3, 10): ("diagrams/benchmark.png", "本系统与行业标杆的能力边界"),
        (4, 3): ("diagrams/breakeven.png", "保本价：收入线与成本线的交点"),
        (4, 7): ("diagrams/risk_levels.png", "四级风险分级与对应动作"),
        (4, 8): ("diagrams/algo_pipeline.png", "从四个输入到一张处方的完整链路"),
        (5, 3): ("diagrams/decision_loop.png", "干预处方在决策闭环中的位置"),
        (5, 9): ("diagrams/benchmark.png", "干预与闭环能力的行业对照"),
        (5, 13): ("diagrams/risk_levels.png", "风险分级：从标签到动作"),
    }

    mod = importlib.import_module("decision")
    importlib.reload(mod)
    chapters = []
    total = 0
    report = []
    for i, ch in enumerate(mod.CHAPTERS, 1):
        pages = []
        for pg in ch["pages"]:
            blocks = [resolve(b, series, tables) for b in pg["blocks"]]
            diag = DIAG.get((i, pg["no"]))
            if diag:
                # 插在最前面，图先于文，符合"先看见再读懂"
                blocks = [{"type": "image", "path": diag[0], "caption": diag[1]}] + blocks
            pages.append({"no": pg["no"], "kicker": pg["kicker"], "title": pg["title"],
                          "kind": pg.get("kind", "body"), "blocks": blocks})
        assert len(pages) == PAGES_PER_CHAPTER, f"第 {i} 章页数 {len(pages)}"
        assert [p["no"] for p in pages] == list(range(1, PAGES_PER_CHAPTER + 1))
        flat = [b for p in pages for b in p["blocks"]]
        chapters.append({
            "title": ch["title"], "lead": ch["lead"], "epigraph": ch["epigraph"],
            "span": ch["span"], "pages": pages, "blocks": flat,
            "theme": next((b.get("tag", "") for b in flat if b["type"] == "theme"), ""),
        })
        total += len(pages)
        kinds = {}
        for b in flat:
            kinds[b["type"]] = kinds.get(b["type"], 0) + 1
        report.append((i, ch["title"], len(pages), kinds))

    vol8 = {
        "id": "vol8",
        "title": "卷八 · 决策与算法精准干预",
        "subtitle": "决策系统专卷 · 5 章 × 20 页 · 可追溯 / 可执行 / 可拒绝",
        "cover": "diagrams/decision_loop.png",
        "color": "#2f6094",
        "icon": "🧭",
        "intro": ("本卷不谈概念，只回答三件事：算法在决策链中做了什么、最终采取了哪些措施、"
                  "事后如何复核。全部数值来自官方序列与本地台账，外推值均标注演示级。"),
        "chapters": chapters,
    }
    book["books"] = [b for b in book["books"] if b["id"] != "vol8"] + [vol8]
    counts = dict(book["meta"].get("counts") or {})
    counts.update({"books": len(book["books"]),
                   "chapters": sum(len(b["chapters"]) for b in book["books"]),
                   "vol8_pages": total, "vol8_chapters": CHAPTERS,
                   "total_pages": sum(len(c.get("pages", [])) for b in book["books"] for c in b["chapters"])})
    book["meta"]["counts"] = counts
    book["meta"]["version"] = "8.0.0"
    book["meta"]["built"] = "2026-11-26"
    book["meta"]["decision_note"] = (
        f"卷八 CAGR(2015-2025)：收入 {inc_cagr:.3f}%、总产值 {gross_cagr:.3f}%、粮食 {grain_cagr:.3f}%；"
        "2026 外推为演示级，非官方统计。对标系统成效数字来自公开报道，不属于本系统。")
    json.dump(book, open(BOOK, "w", encoding="utf-8"), ensure_ascii=False, indent=1)

    print(f"卷八重建完成：{CHAPTERS} 章 / {total} 页")
    for i, title, npages, kinds in report:
        print(f"  第{i}章 {title[:34]:36s} {npages} 页  {kinds}")
    print("全书：", counts)


if __name__ == "__main__":
    main()
