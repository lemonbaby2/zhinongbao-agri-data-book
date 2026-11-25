# -*- coding: utf-8 -*-
"""从《中国城市统计年鉴》开源面板提取广东21市数据，生成 guangdong.json。
数据来源：GitCode open-source-toolkit/db3cf（CC 授权开源），原表 1999-2018。
省级 2024 农业锚点来自广东省统计局《2024年国民经济和社会发展统计公报》。
"""
import json, openpyxl
from pathlib import Path

ROOT = Path(__file__).parent
SRC = ROOT / "extra_data/citystats/中国城市统计年鉴（2010-2019）面板数据.xlsx"
OUT = ROOT / "app/data/guangdong.json"

# 广东21地级市 + 区域划分
CITY_REGION = {
    "广州市": "珠三角", "深圳市": "珠三角", "珠海市": "珠三角", "佛山市": "珠三角",
    "东莞市": "珠三角", "中山市": "珠三角", "惠州市": "珠三角", "江门市": "珠三角",
    "肇庆市": "珠三角",
    "汕头市": "粤东", "潮州市": "粤东", "揭阳市": "粤东", "汕尾市": "粤东",
    "湛江市": "粤西", "茂名市": "粤西", "阳江市": "粤西",
    "韶关市": "粤北", "河源市": "粤北", "梅州市": "粤北", "清远市": "粤北", "云浮市": "粤北",
}

# 2024 年 21 市 GDP 增速（南方+ 2025-02-08 报道，文字稿可确认的）
GDP_GROWTH_2024 = {
    "深圳市": 5.8, "东莞市": None, "惠州市": None,  # 报道明确深莞惠领跑，深圳5.8%
}

# 2024 省级农业锚点（广东省统计局 2024 统计公报）
PROV_2024 = {
    "粮食播种面积_万亩": 3355.13, "糖蔗种植面积_万亩": 176.24,
    "油料种植面积_万亩": 549.76, "蔬菜种植面积_万亩": 2234.00,
    "中草药材种植面积_万亩": 112.81,
    "粮食产量_万吨": 1313.43, "糖蔗产量_万吨": 1052.64,
    "油料产量_万吨": 123.15, "蔬菜产量_万吨": 4245.01,
    "园林水果产量_万吨": 2056.19, "茶叶产量_万吨": 19.17,
    "猪牛羊禽肉产量_万吨": 500.64, "猪肉产量_万吨": 305.18,
    "水产品产量_万吨": 966.35,
    "第一产业增加值_亿元": 5837.03, "GDP_亿元": 141633.81,
    "一产占比_percent": 4.1, "常住人口_万人": 12780,
    "城镇化率_percent": 75.91,
    "珠三角GDP_亿元": 115365.14, "粤东GDP_亿元": 8601.39,
    "粤西GDP_亿元": 9541.55, "粤北GDP_亿元": 8125.73,
    "珠三角增速": 3.7, "粤东增速": 2.4, "粤西增速": 2.1, "粤北增速": 3.2,
}

# 从面板提取
wb = openpyxl.load_workbook(SRC, read_only=True, data_only=True)
ws = wb["Sheet1"]
rows_iter = ws.iter_rows(values_only=True)
hdr = list(next(rows_iter))
IDX = {h: i for i, h in enumerate(hdr)}

COL = {
    "year": 2, "pop": 3, "agri_emp_share": 15,
    "cultivated": 57, "land": 59, "gdp": 66, "gdp_pc": 68,
    "gdp_growth": 70, "agri_share": 72, "ind2_share": 74, "ind3_share": 76,
}

cities = {c: {"region": r, "series": []} for c, r in CITY_REGION.items()}
for row in rows_iter:
    city = str(row[1])
    if city not in cities:
        continue
    try:
        year = int(row[COL["year"]])
    except (ValueError, TypeError):
        continue
    def gv(key):
        v = row[COL[key]]
        return v if isinstance(v, (int, float)) else None
    rec = {
        "year": year,
        "pop": gv("pop"),
        "agri_emp_share": gv("agri_emp_share"),
        "cultivated": gv("cultivated"),
        "land": gv("land"),
        "gdp_wan": gv("gdp"),          # 万元
        "gdp_pc": gv("gdp_pc"),        # 元
        "gdp_growth": gv("gdp_growth"),
        "agri_share": gv("agri_share"),
        "ind2_share": gv("ind2_share"),
        "ind3_share": gv("ind3_share"),
    }
    cities[city]["series"].append(rec)

for c in cities:
    cities[c]["series"].sort(key=lambda r: r["year"])

# 最新年(2018)排名
def rank_latest(key, n=21):
    items = []
    for c, d in cities.items():
        s = d["series"]
        if s and s[-1].get(key) is not None:
            items.append([c, round(s[-1][key], 3)])
    items.sort(key=lambda x: x[1], reverse=True)
    return items[:n]

result = {
    "meta": {
        "title": "广东21市·市域农业与经济面板",
        "source": "GitCode open-source-toolkit/db3cf《中国城市统计年鉴（2010-2019）面板数据》",
        "years": "1999-2018",
        "cities": len(cities),
        "records": sum(len(d["series"]) for d in cities.values()),
        "note": "市域数据来自开源统计年鉴面板；2024省级农业锚点来自广东省统计局统计公报。耕地面积字段在原始面板中大量缺测。",
    },
    "province_2024": PROV_2024,
    "cities": cities,
    "rank_2018": {
        "gdp": rank_latest("gdp_wan"),
        "agri_share": rank_latest("agri_share"),
        "gdp_pc": rank_latest("gdp_pc"),
        "pop": rank_latest("pop"),
        "agri_emp_share": rank_latest("agri_emp_share"),
    },
}

OUT.parent.mkdir(parents=True, exist_ok=True)
json.dump(result, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, separators=(",", ":"))
print("guangdong.json written:", OUT.stat().st_size // 1024, "KB")
print("cities:", len(cities), "records:", result["meta"]["records"])
print("2018 一产占比 Top5:", result["rank_2018"]["agri_share"][:5])
