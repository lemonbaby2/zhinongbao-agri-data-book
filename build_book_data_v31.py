# -*- coding: utf-8 -*-
"""v3.1 增量：把广东21市数据构建为两卷新书，追加进 book_data.json。"""
import json
from pathlib import Path

ROOT = Path(__file__).parent
BOOK = ROOT / "app/data/book_data.json"
GD = ROOT / "app/data/guangdong.json"

d = json.load(open(BOOK, encoding="utf-8"))
g = json.load(open(GD, encoding="utf-8"))

cities = g["cities"]
rank = g["rank_2018"]
p24 = g["province_2024"]

def text_block(title, paras):
    return {"type": "text", "title": title, "paras": paras}

def kpi_block(items):
    return {"type": "kpi", "items": items}

def chart_block(title, kind, data, note=""):
    return {"type": "chart", "title": title, "kind": kind, "data": data, "note": note}

def table_block(title, headers, rows):
    return {"type": "table", "title": title, "headers": headers, "rows": rows}

def image_block(path, caption):
    return {"type": "image", "path": path, "caption": caption}

def city_series(city, key, last=20):
    s = cities[city]["series"]
    return [[r["year"], r[key]] for r in s if r.get(key) is not None][-last:]

# 区域GDP汇总（2018）
region_gdp = {}
for c, v in cities.items():
    s = v["series"]
    if s and s[-1].get("gdp_wan"):
        region_gdp.setdefault(v["region"], 0)
        region_gdp[v["region"]] += s[-1]["gdp_wan"] / 10000  # 万元->亿元
region_gdp_list = [[k, round(v, 1)] for k, v in sorted(region_gdp.items(), key=lambda x: -x[1])]

# 区域一产占比均值（2018）
region_agri = {}
for c, v in cities.items():
    s = v["series"]
    if s and s[-1].get("agri_share") is not None:
        region_agri.setdefault(v["region"], []).append(s[-1]["agri_share"])
region_agri_list = [[k, round(sum(vs)/len(vs), 2)] for k, vs in region_agri.items()]

srcnote = "数据来源：GitCode open-source-toolkit/db3cf《中国城市统计年鉴（2010-2019）面板数据》，1999–2018。"

# ========== 卷五：岭南21市 ==========
vol5 = {
    "id": "vol5", "title": "卷五 · 岭南21市", "subtitle": "广东市域农业经济版图",
    "cover": "img/crop-rice.jpg", "color": "#c47f1a", "icon": "🏙️",
    "intro": "把镜头从省域推进到市域。广东21个地级市，从珠三角的科创重镇到粤西粤北的农业腹地，一产占比从不足0.1%到超过18%——同一省份内部，藏着中国最完整的经济梯度。本卷用20年市域面板，逐城拆解这片土地的差异。",
    "chapters": [
        {"title": "第一章 · 二十一座城：市域数据总览", "lead": "1999–2018，21市 × 20年 = 420条真实市域记录，覆盖人口、GDP、三次产业结构、耕地与就业。",
         "blocks": [
             text_block("一省之内，四个世界", [
                 "广东是中国经济第一大省，但省内差异极大。2018年，深圳一产占比仅0.09%，广州0.98%——它们已是高度的工业化与后工业化经济体；而同期云浮18.23%、湛江17.74%、梅州17.67%，农业仍是当地经济的重要支柱。",
                 "这种梯度不是落后与先进的简单对立，而是功能分工：珠三角承担科技创新与高端制造，粤东粤西粤北承担农业、生态与产业转移。理解广东，必须理解这种内部差异。",
             ]),
             kpi_block([["21", "地级市"], ["20", "年份跨度(1999–2018)"], ["420", "市域面板记录"], ["251", "原始指标列数"]]),
             chart_block("2018年广东21市GDP排名（亿元）", "bar",
                         [[c.replace("市",""), round(v/10000, 1)] for c, v in rank["gdp"]], srcnote),
             chart_block("2018年广东21市第一产业占比（%，Top 12）", "bar",
                         [[c.replace("市",""), v] for c, v in rank["agri_share"][:12]], srcnote),
             chart_block("交互探索：任选一座城市，查看它20年的经济轨迹", "city_explorer", [],
                         "在上方的「城市」与「指标」下拉框中选择，曲线实时重绘。数据为1999–2018年真实面板。"),
         ]},
        {"title": "第二章 · 四大板块：珠三角与粤东西北", "lead": "珠三角、粤东、粤西、粤北——四个板块的GDP与农业占比，呈现清晰的空间分工。",
         "blocks": [
             text_block("板块之间的分工", [
                 "2018年，珠三角9市GDP合计超过8万亿元，占全省八成以上；粤东、粤西、粤北各板块合计均在万亿元量级。经济总量高度集中，但农业比重恰好相反——粤北与粤西的一产占比显著高于珠三角。",
                 f"到2024年，这一格局延续：全省GDP {p24['GDP_亿元']:,.2f}亿元，其中珠三角{p24['珠三角GDP_亿元']:,.2f}亿元、粤东{p24['粤东GDP_亿元']:,.2f}亿元、粤西{p24['粤西GDP_亿元']:,.2f}亿元、粤北{p24['粤北GDP_亿元']:,.2f}亿元。增速上，珠三角{p24['珠三角增速']}%领先，粤北{p24['粤北增速']}%紧随。",
             ]),
             chart_block("2018年四大板块GDP合计（亿元）", "bar", region_gdp_list, srcnote),
             chart_block("2018年四大板块平均一产占比（%）", "bar", region_agri_list, srcnote),
             table_block("2024年广东分区域主要指标", ["区域", "GDP(亿元)", "增速(%)"],
                         [["珠三角", p24["珠三角GDP_亿元"], p24["珠三角增速"]],
                          ["粤东", p24["粤东GDP_亿元"], p24["粤东增速"]],
                          ["粤西", p24["粤西GDP_亿元"], p24["粤西增速"]],
                          ["粤北", p24["粤北GDP_亿元"], p24["粤北增速"]]]),
             image_block("img/farm-digital.jpg", "数字农田：粤东西北农业现代化的方向（AI 生成插画）"),
         ]},
        {"title": "第三章 · 二十年的经济跃迁", "lead": "从1999到2018，广东各市经历了不同节奏的增长。这条曲线，是中国区域发展最鲜活的样本。",
         "blocks": [
             text_block("增长的节奏", [
                 "深圳从1999年的约1400亿元跃升至2018年的2.42万亿元，增长超过17倍；广州同期从约1900亿元增至2.29万亿元。两座一线城市构成了广东经济的双核心。",
                 "与之对照，粤北的梅州、河源等市基数较小、增速平缓。差距的扩大与收敛，是区域经济学最核心的命题，也是「百县千镇万村高质量发展工程」要解决的实际问题。",
             ]),
             chart_block("深圳市GDP增长（1999–2018，亿元）", "line",
                         [[r[0], round(r[1]/10000, 1)] for r in city_series("深圳市", "gdp_wan")], srcnote),
             chart_block("广州市GDP增长（1999–2018，亿元）", "line",
                         [[r[0], round(r[1]/10000, 1)] for r in city_series("广州市", "gdp_wan")], srcnote),
             chart_block("湛江市GDP增长（1999–2018，亿元）", "line",
                         [[r[0], round(r[1]/10000, 1)] for r in city_series("湛江市", "gdp_wan")], srcnote),
         ]},
        {"title": "第四章 · 农业的份额：谁在真正种地", "lead": "一产占比与一产就业比重，共同揭示哪些城市仍是农业腹地。",
         "blocks": [
             text_block("农业密度的地理", [
                 "2018年一产占比最高的云浮（18.23%）、湛江（17.74%）、梅州（17.67%），集中在粤西与粤北。这些地区承担着广东的粮食、果蔬、畜牧供给功能。",
                 "湛江一产就业比重2.62%，虽然绝对值不高，但在全省已属前列。农业现代化对这些地区意味着：用更少的劳动力，产出更多的价值。",
             ]),
             chart_block("2018年一产就业比重（%，Top 12）", "bar",
                         [[c.replace("市",""), v] for c, v in rank["agri_emp_share"][:12]], srcnote),
             table_block("2018年一产占比最高的8个市", ["城市", "一产占比(%)"],
                         [[c.replace("市",""), v] for c, v in rank["agri_share"][:8]]),
             image_block("img/crop-orchard.jpg", "果园经济：粤北山区的特色农业（AI 生成插画）"),
         ]},
        {"title": "第五章 · 尾声：从市域回到省域", "lead": "市域的差异，最终汇聚成省域的总量。下一章，我们把21市的线索收束到广东全省的农业全景。",
         "blocks": [
             text_block("下一站，全省农业", [
                 "21市的面板让我们看见了差异，但农业的全貌还需要省域视角——播种面积、粮食产量、茶叶、蔬菜、水产品。下一卷，我们用2024年广东省统计公报，补齐这幅全景。",
             ]),
         ]},
    ],
}

# ========== 卷六：广东农业全景 ==========
vol6 = {
    "id": "vol6", "title": "卷六 · 广东农业全景", "subtitle": "2024 省域农业数据 + 智农宝方案",
    "cover": "img/hero-farm.jpg", "color": "#1f9d55", "icon": "🌾",
    "intro": "2024年，广东粮食产量1313.43万吨，茶叶19.17万吨，蔬菜4245.01万吨。本卷以省统计局公报为锚点，展开智农宝在广东的落地方案——从数据到决策，从田块到餐桌。",
    "chapters": [
        {"title": "第一章 · 2024：广东农业的数字切片", "lead": "从粮食到茶叶，从耕地到海域——一组数字勾勒出广东农业的当下。",
         "blocks": [
             text_block("饭碗与菜篮子", [
                 f"2024年广东粮食作物播种面积{p24['粮食播种面积_万亩']:,.2f}万亩，产量{p24['粮食产量_万吨']:,.2f}万吨；蔬菜产量{p24['蔬菜产量_万吨']:,.2f}万吨，园林水果{p24['园林水果产量_万吨']:,.2f}万吨。",
                 f"值得关注的是茶叶：产量{p24['茶叶产量_万吨']:,.2f}万吨，同比增长7.2%——这与本书卷三的茶文化数据形成了呼应。广东既是茶叶消费大省，也是重要的茶叶产区。",
             ]),
             kpi_block([["1,313", "粮食产量(万吨)"], ["4,245", "蔬菜产量(万吨)"],
                        ["19.17", "茶叶产量(万吨)"], ["966", "水产品产量(万吨)"]]),
             chart_block("2024年广东主要农产品产量（万吨）", "bar",
                         [["粮食", p24["粮食产量_万吨"]], ["蔬菜", p24["蔬菜产量_万吨"]],
                          ["水果", p24["园林水果产量_万吨"]], ["糖蔗", p24["糖蔗产量_万吨"]],
                          ["茶叶", p24["茶叶产量_万吨"]]],
                         "数据来源：广东省统计局《2024年国民经济和社会发展统计公报》"),
             chart_block("2024年广东主要作物种植面积（万亩）", "bar",
                         [["粮食", p24["粮食播种面积_万亩"]], ["蔬菜", p24["蔬菜种植面积_万亩"]],
                          ["油料", p24["油料种植面积_万亩"]], ["糖蔗", p24["糖蔗种植面积_万亩"]],
                          ["中草药", p24["中草药材种植面积_万亩"]]],
                         "数据来源：广东省统计局《2024年国民经济和社会发展统计公报》"),
         ]},
        {"title": "第二章 · 智农宝广东方案：数据底座", "lead": "把省域面板、市域面板、作物数据与真实交易数据打通，构建广东农业的数据底座。",
         "blocks": [
             text_block("四层数据，一座底座", [
                 "智农宝在广东的数据底座由四层构成：① 31省面板中的广东序列（1980–2024）；② 广东21市市域面板（1999–2018）；③ 省级2024农业公报锚点；④ 作物播种面积与真实市场价格样本。",
                 "四层数据的粒度不同、时间不同、口径不同，但通过统一的指标字典与来源标注，可以在同一界面中对照阅读——这正是本书「数据之书」的设计初衷。",
             ]),
             kpi_block([["1,395", "全国面板记录"], ["420", "广东市域记录"],
                        ["232", "源数据文件"], ["4", "数据层级"]]),
             table_block("智农宝广东数据底座", ["层级", "范围", "年份", "来源"],
                         [["省域面板", "广东", "1980–2024", "本机比赛工作簿"],
                          ["市域面板", "21地级市", "1999–2018", "中国城市统计年鉴开源版"],
                          ["省级锚点", "广东全省", "2024", "广东省统计局公报"],
                          ["作物与市场", "多省+临沂", "2000–2025", "工作簿+GitHub Apache-2.0"]]),
         ]},
        {"title": "第三章 · 智农宝广东方案：防亏损与决策", "lead": "广东农业的高价值作物多、市场波动大，防亏损决策尤为关键。",
         "blocks": [
             text_block("从数据到决策", [
                 "以茶叶为例：2024年广东茶叶产量增长7.2%，但价格受市场供需影响显著。农户面临的核心问题是——扩种还是观望？智农宝的保本价测算与风险评级，正是为这类决策提供量化支撑。",
                 "系统根据作物、面积、成本参数，自动计算保本价、保本单产与预期利润，并用红黄绿三色评级风险。所有计算在本机完成，数据不上传。",
             ]),
             kpi_block([["3", "风险等级"], ["±20%", "敏感性波动"], ["0", "数据上传"], ["8", "参考作物"]]),
             image_block("img/crop-greenhouse.jpg", "设施农业：高价值作物的风险可控路径（AI 生成插画）"),
         ]},
        {"title": "第四章 · 尾声：数据的下一站", "lead": "书读到此处，数据已经从全国走到广东，从省域走到市域，从农田走到餐桌。",
         "blocks": [
             text_block("合卷", [
                 "智农宝农业数据全书到此暂告一段落。四卷主线 + 两卷广东专题，构成一部可翻阅、可交互、可追溯来源的数据之书。",
                 "所有数据均封装在离线软件中，每一个数字都标注了来源与性质。愿这部书，能让农业数据不再冰冷。",
             ]),
         ]},
    ],
}

# 追加（若已存在则替换）
d["books"] = [b for b in d["books"] if b["id"] not in ("vol5", "vol6")]
d["books"].extend([vol5, vol6])
d["meta"]["counts"]["books"] = len(d["books"])
d["meta"]["counts"]["chapters"] = sum(len(b["chapters"]) for b in d["books"])
d["meta"]["counts"]["gd_city_records"] = g["meta"]["records"]
d["meta"]["version"] = "3.1.0"
d["meta"]["built"] = "2026-11-23"

json.dump(d, open(BOOK, "w", encoding="utf-8"), ensure_ascii=False, separators=(",", ":"))
print("book_data.json updated -> v3.1.0")
print("books:", len(d["books"]), "chapters:", d["meta"]["counts"]["chapters"])
for b in d["books"]:
    print(" ", b["id"], b["title"], len(b["chapters"]), "章")
