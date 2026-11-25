# -*- coding: utf-8 -*-
"""构建卷七《改革开放四十八年》v6：10 章 × 20 页 = 200 页真书分页。

页面内容在 content/chNN.py 里写，真实数值由本脚本从
guangdong_reform.json / guangdong.json 注入，保证不手抄错数。
"""
import importlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
BOOK = ROOT / "app" / "data" / "book_data.json"
GD = ROOT / "app" / "data" / "guangdong_reform.json"
GDC = ROOT / "app" / "data" / "guangdong.json"
sys.path.insert(0, str(ROOT / "content"))

PAGES_PER_CHAPTER = 20
CHAPTERS = 10


def load(p):
    return json.load(open(p, encoding="utf-8"))


def fmt(v, digits=2):
    if v is None:
        return "—"
    if isinstance(v, int):
        return f"{v:,}"
    return f"{v:,.{digits}f}"


def build_tables(gd, gdc):
    s = gd["series"]
    inc = {int(y): v for y, v in s["rural_income"]}
    gross = {int(y): v for y, v in s["gross_output"]}
    grain = {int(y): v for y, v in s["grain_output"]}
    engel = {int(y): v for y, v in s["engel"]}
    fva = {int(y): v for y, v in s["first_value_added"]}

    years = [1978, 1985, 1990, 1995, 2000, 2005, 2010, 2015, 2018, 2020, 2025]
    decade = {
        "type": "table",
        "title": "广东农村经济的阶段结算（官方序列抽样年份）",
        "headers": ["年份", "人均收入(元)", "农林牧渔总产值(亿元)", "粮食(万吨)", "恩格尔系数(%)"],
        "rows": [[str(y), fmt(inc.get(y), 2), fmt(gross.get(y)), fmt(grain.get(y), 1),
                  fmt(engel.get(y), 1)] for y in years],
    }

    nodes = [
        (1985, "取消粮食统购，改合同定购"),
        (1988, "价格闯关，全国零售物价 +18.8%"),
        (1992, "广东率先放开粮食购销价格"),
        (1993, "全国取消粮票"),
        (1995, "收入五年增长 1.59 倍"),
    ]
    reform_nodes = {
        "type": "table",
        "title": "农产品价格改革的四个节点与当年广东数据",
        "headers": ["年份", "政策节点", "人均收入(元)", "总产值(亿元)"],
        "rows": [[str(y), k, fmt(inc.get(y), 2), fmt(gross.get(y))] for y, k in nodes],
    }

    sec = {k: {int(y): v for y, v in vv} for k, vv in s["sector_output"].items()}
    sv = {k: sec[k].get(2018) for k in sec}
    tot = sum(v for v in sv.values() if v)
    label = {"agri": "农业（种植业）", "forestry": "林业", "livestock": "畜牧业",
             "fishery": "渔业", "service": "农林牧渔服务业"}
    sector = {
        "type": "table",
        "title": "2018 年广东农林牧渔五业产值与占比",
        "headers": ["行业", "产值(亿元)", "占比(%)"],
        "rows": [[label[k], fmt(sv[k]), f"{sv[k] / tot * 100:.1f}"] for k in sv] + \
                [["合计", fmt(tot), "100.0"]],
    }

    # 21 市：2018 年 GDP（万元→亿元）与第一产业占比
    rows = []
    for city, info in (gdc.get("cities") or {}).items():
        last = None
        for rec in info.get("series") or []:
            if rec.get("year") == 2018:
                last = rec
        if not last:
            continue
        rows.append([city, (last.get("gdp_wan") or 0) / 10000.0,
                     last.get("agri_share"), info.get("region", "")])
    rows.sort(key=lambda r: -r[1])
    pick = rows[:8] + [["…", None, None, ""]] + rows[-4:]
    cities = {
        "type": "table",
        "title": "广东 21 市 GDP 与农业份额（2018 年面板，前八与后四）",
        "headers": ["城市", "GDP(亿元)", "第一产业占比(%)", "区域"],
        "rows": [[c, fmt(g) if g is not None else "…",
                  f"{a:.1f}" if isinstance(a, (int, float)) else "…", r] for c, g, a, r in pick],
    }
    return {"decade": decade, "reform_nodes": reform_nodes,
            "sector": sector, "cities": cities}


def resolve(block, series, tables):
    t = block["type"]
    if t == "figure":
        key = block["series"]
        raw = series.get(key)
        if isinstance(raw, dict):  # 五业：取合计
            pts = {}
            for k, vv in raw.items():
                for y, v in vv:
                    pts[int(y)] = pts.get(int(y), 0) + v
            raw = sorted(pts.items())
        raw = [[int(y), v] for y, v in raw if v is not None]
        lo = block.get("lo") or raw[0][0]
        hi = block.get("hi") or raw[-1][0]
        data = [[y, v] for y, v in raw if lo <= y <= hi]
        unit = {"rural_income": "元", "gross_output": "亿元", "grain_output": "万吨",
                "engel": "%", "housing": "平方米", "rural_consumption": "元",
                "grain_area_ka": "千公顷", "sector_output": "亿元"}.get(key, "")
        return {"type": "chart", "title": block["title"],
                "kind": block.get("kind", "line"), "data": data,
                "note": block.get("note", "") or f"单位：{unit}" if unit else block.get("note", "")}
    if t == "datatable":
        tb = dict(tables[block["key"]])
        if block.get("title"):
            tb["title"] = block["title"]
        return tb
    return block


def main():
    gd = load(GD)
    gdc = load(GDC)
    series = gd["series"]
    tables = build_tables(gd, gdc)
    from more import EXTRA
    book = load(BOOK)

    chapters = []
    total_pages = 0
    report = []
    for i in range(1, CHAPTERS + 1):
        mod = importlib.import_module(f"ch{i:02d}")
        importlib.reload(mod)
        ch = mod.CHAPTER
        pages = []
        for pg in ch["pages"]:
            blocks = [resolve(b, series, tables) for b in pg["blocks"]]
            extra = EXTRA.get((i, pg["no"]))
            if extra:
                for b in blocks:
                    if b.get("type") == "text":
                        b["paras"] = list(b["paras"]) + list(extra)
                        break
            pages.append({"no": pg["no"], "kicker": pg["kicker"], "title": pg["title"],
                          "kind": pg.get("kind", "body"), "blocks": blocks})
        assert len(pages) == PAGES_PER_CHAPTER, f"第 {i} 章页数 {len(pages)}"
        assert [p["no"] for p in pages] == list(range(1, PAGES_PER_CHAPTER + 1)), \
            f"第 {i} 章页码不连续"
        flat = []
        for p in pages:
            flat.extend(p["blocks"])
        chapters.append({
            "title": ch["title"], "lead": ch["lead"], "epigraph": ch["epigraph"],
            "span": ch["span"], "pages": pages, "blocks": flat,
            "theme": next((b.get("tag", "") for b in flat if b["type"] == "theme"), ""),
        })
        total_pages += len(pages)
        report.append((i, ch["title"], len(pages), len(flat)))

    old = next((b for b in book["books"] if b["id"] == "vol7"), {})
    vol7 = {
        "id": "vol7",
        "title": old.get("title") or "卷七 · 改革开放四十八年",
        "subtitle": "农村经济智慧农业决策系统 · 1978—2026 · 200 页真书",
        "cover": old.get("cover") or "img/crop-orchard.jpg",
        "color": old.get("color") or "#b23b2e",
        "icon": old.get("icon") or "📖",
        "intro": "十章，每章二十页：扉页、主题卡、档案、口述、数据表、图表、决策卡。"
                 "数据全部来自广东省统计局官方年鉴与公报，预测值单独标注。",
        "chapters": chapters,
    }
    book["books"] = [b for b in book["books"] if b["id"] != "vol7"] + [vol7]
    counts = dict(book["meta"].get("counts") or {})
    counts.update({"books": len(book["books"]),
                   "chapters": sum(len(b["chapters"]) for b in book["books"]),
                   "vol7_pages": total_pages,
                   "vol7_chapters": CHAPTERS})
    book["meta"]["counts"] = counts
    book["meta"]["version"] = "6.0.0"
    book["meta"]["built"] = "2026-11-26"
    book["meta"]["source_note"] = ("卷七 1978—2018 年数据逐格提取自《广东农村统计年鉴 2019》；"
                                   "2019—2025 为广东省统计局公报锚点；2026 为模型外推，非官方统计。")
    json.dump(book, open(BOOK, "w", encoding="utf-8"), ensure_ascii=False, indent=1)

    print(f"卷七重建完成：{CHAPTERS} 章 / {total_pages} 页 / "
          f"{sum(r[3] for r in report)} 个区块")
    for i, title, npages, nblocks in report:
        print(f"  第{i:2d}章 {title[:30]:32s} {npages:2d} 页  {nblocks:3d} 块")
    print("全书：", counts)


if __name__ == "__main__":
    main()
