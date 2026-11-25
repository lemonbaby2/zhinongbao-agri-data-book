# -*- coding: utf-8 -*-
"""
构建《广东改革开放农村经济·智慧农业决策数据 1978—2026》

数据源（全部为广东省统计局 / 国家统计局广东调查总队官方发布）：
  1. 《广东农村统计年鉴 2019》——1978—2018 年农林牧渔业总产值、分行业产值、
     农村居民收入消费、恩格尔系数、住房面积、农作物播种面积与产量（权威面板）
  2. 《广东经济社会发展成就回顾总结》——2012—2021 年结构性数据
  3. 2019—2025 年广东省国民经济和社会发展统计公报 / 经济运行简况 / 农业生产运行简况
  4. 本机比赛工作簿 31 省面板（广东行）——仅作参照，标注"未独立核验"

输出：app/data/guangdong_reform.json
"""
import json
import os
import re
from pathlib import Path

import fitz  # PyMuPDF

ROOT = Path(__file__).resolve().parent
PDF_DIR = ROOT / "extra_data" / "gd_official"
YEARBOOK = PDF_DIR / "广东农村统计年鉴2019.pdf"
OUT = ROOT / "app" / "data" / "guangdong_reform.json"

YEAR_RE = re.compile(r"^(19[4-9]\d|20[0-2]\d)$")
NUM_RE = re.compile(r"^-?\d[\d,]*\.?\d*$")


def year_blocks(text, stop=None, lo=1949, hi=2026):
    """把 PDF 文本里 '年份 + 一串数字' 的表解析成 {year: [floats]}"""
    blocks, cur = {}, None
    for raw in text.splitlines():
        line = raw.strip()
        if stop and line == stop:
            break
        if YEAR_RE.match(line):
            y = int(line)
            cur = y if lo <= y <= hi else None
            if cur is not None:
                blocks[cur] = []
            continue
        if cur is not None and NUM_RE.match(line):
            blocks[cur].append(float(line.replace(",", "")))
    return blocks


def pairs(d, idx=0, years=None, skip_missing=True):
    out = []
    for y in sorted(d):
        if years is not None and y not in years:
            continue
        vals = d[y]
        if len(vals) <= idx:
            continue
        v = vals[idx]
        if skip_missing and v is None:
            continue
        out.append([y, round(v, 4)])
    return out


def page_text(doc, page_no):
    return doc[page_no - 1].get_text()


def build():
    doc = fitz.open(str(YEARBOOK))

    # --- 7-1 历年农林牧渔业总产值（1978—2018，当年价，亿元）-------------
    gross = year_blocks(page_text(doc, 163), stop="注：1.", lo=1978, hi=2018)
    # 1978—2002 为 5 列（合计/农业/林业/牧业/渔业），2003 起 6 列（+服务业）
    gross_all = pairs(gross, 0)
    sectors = {
        "agri": pairs(gross, 1),
        "forestry": pairs(gross, 2),
        "livestock": pairs(gross, 3),
        "fishery": pairs(gross, 4),
        "service": pairs(gross, 5),
    }

    # --- 8-1 主要年份农作物播种面积（千公顷）-----------------------------
    area = year_blocks(page_text(doc, 193), stop="二、构成(%)", lo=1949, hi=2018)
    area_all = pairs(area, 0)
    area_grain = pairs(area, 1)

    # --- 8-2 主要年份农作物产量（万吨）----------------------------------
    crops = year_blocks(page_text(doc, 195), stop="二、指数", lo=1949, hi=2018)
    grain = pairs(crops, 0)
    # 8-2 列顺序：粮食 / 稻谷 / 薯类 / 大豆 / 糖蔗 / 花生 / 黄红麻 / 土烟 / 烤烟
    soy = pairs(crops, 3)
    sugar = pairs(crops, 4)
    peanut = pairs(crops, 5)

    # --- 15-1 农村常住居民收入与支出（1978—2018）------------------------
    inc = year_blocks(page_text(doc, 423), stop="注：", lo=1978, hi=2018)
    rural_income, rural_consume, engel = [], [], []
    for y in sorted(inc):
        v = inc[y]
        if not v:
            continue
        rural_income.append([y, round(v[0], 2)])
        # 1978 行少一列"实际增长"，消费支出在第 3 位；其余年份在第 4 位
        ci = 3 if y == 1978 else 4
        if len(v) > ci:
            rural_consume.append([y, round(v[ci], 2)])
        # PDF 页脚页码（如 415.0）会被追加进该年份数值块；恩格尔系数合理区间 20—80
        engel_values = [x for x in v if 20 <= x <= 80]
        if engel_values:
            engel.append([y, round(engel_values[-1], 2)])

    # --- 15-2 历年农村常住居民家庭基本情况（住房面积）-------------------
    house = year_blocks(page_text(doc, 424), lo=1978, hi=2018)
    housing = []
    for y, v in sorted(house.items()):
        plausible = [x for x in v if 5 <= x <= 100]  # 排除页脚页码 416.0
        if len(plausible) >= 2:
            housing.append([y, round(plausible[-1], 2)])

    doc.close()

    # --- 2019—2025 官方公报 / 运行简况锚点 -------------------------------
    OFFICIAL = {
        "gdp": {
            2018: 97277.77, 2019: 107671.07, 2020: 110760.94, 2021: 124369.67,
            2022: 129118.58, 2023: 135673.16, 2024: 141633.81, 2025: 145846.76,
        },
        "first_value_added": {
            2018: 3831.44, 2019: 4351.26, 2020: 4769.99, 2022: 5350.09,
            2023: 5540.70, 2024: 5837.03, 2025: 5891.80,
        },
        "rural_income": {
            2019: 18818, 2020: 20143, 2021: 22306, 2022: 23598,
            2023: 25142, 2024: 26729, 2025: 28170,
        },
        "grain_output": {
            2019: 1240.80, 2020: 1267.56, 2021: 1279.87, 2022: 1291.54,
            2023: 1285.19, 2024: 1313.43, 2025: 1318.8,
        },
        "gross_output": {
            2019: 7175.89, 2020: 7937.60, 2021: 8305.84, 2022: 8890.56,
            2023: 9202.09, 2024: 9701.21, 2025: 9798.65,
        },
        "vegetable_output": {2018: 3330.24, 2020: 3706.85, 2021: 3855.73, 2024: 4245.01},
        "fruit_output": {2018: 1547.81, 2020: 1756.16, 2021: 1826.73, 2024: 2056.19},
        "tea_output": {2018: 9.99, 2020: 12.82, 2021: 13.95, 2024: 19.17},
        "aquatic_output": {2020: 875.80, 2021: 921.67, 2022: 894.14, 2024: 966.35},
        "pork_output": {2022: 279.81, 2024: 305.18},
        "grain_area_wanmu": {
            2021: 3319.55, 2022: 3345.45, 2023: 3344.26,
            2024: 3355.13, 2025: 3353.0,
        },
    }

    def merge(base, extra):
        d = {int(y): float(v) for y, v in base}
        d.update({int(y): float(v) for y, v in extra.items()})
        return [[y, round(d[y], 4)] for y in sorted(d)]

    # 官方分行业产值补充（2019 官方 xlsx；2023 官方农业产值表）
    sector_extra = {
        "agri": {2019: 3530.21, 2023: 4430.96},
        "forestry": {2019: 408.48, 2023: 562.69},
        "livestock": {2019: 1404.13, 2023: 1696.79},
        "fishery": {2019: 1524.78, 2023: 2005.31},
        "service": {2019: 308.30, 2023: 506.35},
    }
    for key, extra in sector_extra.items():
        sectors[key] = merge(sectors[key], extra)

    series = {
        "gross_output": merge(gross_all, OFFICIAL["gross_output"]),
        "sector_output": {k: v for k, v in sectors.items()},
        "rural_income": merge(rural_income, OFFICIAL["rural_income"]),
        "rural_consumption": rural_consume,
        "engel": engel,
        "housing": housing,
        "grain_output": merge(grain, OFFICIAL["grain_output"]),
        "grain_area_ka": area_grain,
        "crop_area_ka": area_all,
        "soy_output": soy,
        "sugar_output": sugar,
        "peanut_output": peanut,
        "gdp": [[y, float(v)] for y, v in sorted(OFFICIAL["gdp"].items())],
        "first_value_added": [[y, float(v)] for y, v in sorted(OFFICIAL["first_value_added"].items())],
        "vegetable_output": [[y, float(v)] for y, v in sorted(OFFICIAL["vegetable_output"].items())],
        "fruit_output": [[y, float(v)] for y, v in sorted(OFFICIAL["fruit_output"].items())],
        "tea_output": [[y, float(v)] for y, v in sorted(OFFICIAL["tea_output"].items())],
        "aquatic_output": [[y, float(v)] for y, v in sorted(OFFICIAL["aquatic_output"].items())],
        "pork_output": [[y, float(v)] for y, v in sorted(OFFICIAL["pork_output"].items())],
        "grain_area_wanmu": [[y, float(v)] for y, v in sorted(OFFICIAL["grain_area_wanmu"].items())],
    }

    # --- 比赛工作簿广东行（1980—2024），仅作参照 -------------------------
    dash_path = ROOT / "app" / "site" / "data" / "dashboard.json"
    dash = json.load(open(dash_path, encoding="utf-8"))
    workbook = []
    for r in dash["panel"]["rows"]:
        if r["省份"] != "广东":
            continue
        workbook.append({
            "year": r["年份"],
            "gdp": r["总GDP(亿元)"],
            "first_gdp": r["第一产业GDP(亿元)"],
            "share": r["第一产业占GDP比重(%)"],
            "pop": r["常住人口(万人)"],
            "income": r["农村居民人均可支配收入(元)"],
        })

    # --- 2026 预测（明确标注为模型外推，不是官方统计）--------------------
    def cagr(series, start=2015, end=2025):
        d = dict(series)
        if start not in d or end not in d or d[start] <= 0:
            return None
        n = end - start
        return (d[end] / d[start]) ** (1.0 / n) - 1

    proj = {}
    for key, label, unit in [
        ("rural_income", "农村居民人均可支配收入", "元"),
        ("gross_output", "农林牧渔业总产值", "亿元"),
        ("grain_output", "粮食产量", "万吨"),
    ]:
        rate = cagr(series[key])
        if rate is None:
            continue
        last_v = dict(series[key])[2025]
        proj[key] = {
            "label": label, "unit": unit,
            "rate_2015_2025": round(rate * 100, 3),
            "forecast_2026": round(last_v * (1 + rate), 2),
            "method": "2015—2025 复合增长率外推（演示级，非官方统计）",
        }

    # --- 改革开放关键节点（用于章节主题）--------------------------------
    milestones = [
        {"year": 1978, "title": "起跑线", "desc": "十一届三中全会召开，农村改革破题。广东农民人均可支配收入仅 193 元。"},
        {"year": 1980, "title": "特区破冰", "desc": "深圳、珠海、汕头经济特区设立；农林牧渔业总产值 126 亿元。"},
        {"year": 1985, "title": "价格闯关", "desc": "取消农产品统购派购，市场机制进入田间地头。"},
        {"year": 1990, "title": "亿元村", "desc": "珠三角乡镇企业勃兴，农民收入突破千元大关。"},
        {"year": 1992, "title": "南巡春潮", "desc": "市场经济体制目标确立，农业劳动力大规模向非农转移。"},
        {"year": 2000, "title": "世纪之交", "desc": "一产占比降至 11.2%，农业从总量转向质量。"},
        {"year": 2006, "title": "全面免税", "desc": "农业税退出历史舞台，种田不再交粮税。"},
        {"year": 2012, "title": "十八大", "desc": "农林牧渔业总产值 4550 亿元，现代农业加速。"},
        {"year": 2017, "title": "乡村振兴", "desc": "党的十九大提出乡村振兴战略，农业数字化起步。"},
        {"year": 2020, "title": "抗疫保供", "desc": "疫情冲击下粮食产量 1267.56 万吨，创八年新高。"},
        {"year": 2023, "title": "百千万工程", "desc": "县域经济成为主战场，21 市农业版图重绘。"},
        {"year": 2024, "title": "新质生产力", "desc": "粮食产量 1313.43 万吨，农业机械总动力 2615.70 万千瓦。"},
        {"year": 2025, "title": "十四五收官", "desc": "农民收入 28170 元，城乡居民收入比缩小至 2.27:1。"},
        {"year": 2026, "title": "十五五开局", "desc": "智慧农业决策系统成为新农具（预测与展望）。"},
    ]

    sources = [
        {
            "name": "广东农村统计年鉴 2019",
            "org": "广东省统计局 / 国家统计局广东调查总队",
            "url": "http://stats.gd.gov.cn/attachment/0/392/392746/2995454.pdf",
            "coverage": "1978—2018 年农林牧渔业总产值、分行业、农村居民收入消费、播种面积与产量",
        },
        {
            "name": "广东经济社会发展成就回顾总结",
            "org": "广东省统计局",
            "url": "http://stats.gd.gov.cn/attachment/0/503/503663/4015706.pdf",
            "coverage": "2012—2021 年产业结构和农业成就",
        },
        {
            "name": "2024 年广东省国民经济和社会发展统计公报",
            "org": "广东省统计局",
            "url": "https://stats.gd.gov.cn/attachment/0/576/576336/4686764.pdf",
            "coverage": "2024 年农业、收入、GDP",
        },
        {
            "name": "2025 年广东经济运行简况 / 农业生产运行简况",
            "org": "广东省统计局",
            "url": "https://stats.gd.gov.cn/jjxsxwfbh/content/post_4888706.html",
            "coverage": "2025 年 GDP、一产、粮食、农村居民收入",
        },
        {
            "name": "2022 年广东省国民经济和社会发展统计公报",
            "org": "广东省统计局",
            "url": "https://stats.gd.gov.cn/attachment/0/517/517175/4146083.pdf",
            "coverage": "2017—2022 年粮食产量与收入序列",
        },
        {
            "name": "本机比赛工作簿 31 省经济面板（广东行）",
            "org": "本机大数据技能大赛工作簿",
            "url": "local://农业大数据_全国综合指标更新版.xlsx",
            "coverage": "1980—2024 年 GDP / 一产 / 占比，未独立核验，仅作参照",
        },
    ]

    data = {
        "meta": {
            "title": "广东改革开放农村经济 · 智慧农业决策数据",
            "subtitle": "1978—2026 四十八年长面板",
            "built": "2026-11-25",
            "span": "1978—2026",
            "official_years": "1978—2025",
            "projection_years": "2026",
            "sources": sources,
            "caveats": [
                "1978—2018 年主体数据逐格提取自《广东农村统计年鉴 2019》原表。",
                "2019—2025 年锚点来自广东省统计局公开公报与运行简况，口径差异已在来源中注明。",
                "2026 年为复合增长率模型外推，属演示级预测，非官方统计数据。",
                "比赛工作簿面板与官方公报存在口径差异，均已分开存放，不混合使用。",
            ],
        },
        "series": series,
        "workbook_panel": workbook,
        "projection_2026": proj,
        "milestones": milestones,
    }

    OUT.parent.mkdir(parents=True, exist_ok=True)
    json.dump(data, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("WROTE", OUT, OUT.stat().st_size, "bytes")
    for k, v in series.items():
        if isinstance(v, list):
            print(f"  {k:22s} {len(v):3d} points  {v[:1]} ... {v[-1:]}")
    print("  projection:", json.dumps(proj, ensure_ascii=False))


if __name__ == "__main__":
    build()
