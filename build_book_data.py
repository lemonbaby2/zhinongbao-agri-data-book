# -*- coding: utf-8 -*-
"""
把智农宝面板数据 + 茶文化数据 + GitHub 真实农业数据集
构建为书式阅读器所需的 book_data.json（多卷多章，章章衔接）。
"""
import json, csv, shutil
from pathlib import Path
from collections import defaultdict

ROOT = Path(__file__).parent
ZN = ROOT / "zn/智农宝_v2.2.0/site/data"
DISP = ROOT / "display/数据展示系统"
GH = ROOT / "extra_data/price_yield_dataset"
OUT = ROOT / "app/data"
OUT.mkdir(parents=True, exist_ok=True)
ASSET = ROOT / "app/assets"
ASSET.mkdir(parents=True, exist_ok=True)

# ---------- 1. 面板数据 ----------
dash = json.load(open(ZN / "dashboard.json", encoding="utf-8"))
PANEL = dash["panel"]["rows"]
MACRO = dash["macro"]["rows"]
YEARS = dash["years"]
PROVINCES = dash["provinces"]

def col_mean(year, key):
    vals = [r[key] for r in PANEL if r["年份"] == year and r.get(key) is not None]
    return round(sum(vals) / len(vals), 3) if vals else None

def col_sum(year, key):
    vals = [r[key] for r in PANEL if r["年份"] == year and r.get(key) is not None]
    return round(sum(vals), 2) if vals else None

# 全国一产占比趋势
share_trend = [[y, col_mean(y, "第一产业占GDP比重(%)")] for y in YEARS]
gdp_trend = [[y, col_sum(y, "总GDP(亿元)")] for y in YEARS]
income_trend = [[y, col_mean(y, "农村居民人均可支配收入(元)")] for y in YEARS]

# 最新一年省份排名
latest = max(YEARS)
def province_rank(key, n=10, reverse=True):
    rows = [(r["省份"], r[key]) for r in PANEL if r["年份"] == latest and r.get(key) is not None]
    rows.sort(key=lambda x: x[1], reverse=reverse)
    return [[k, round(v, 2)] for k, v in rows[:n]]

top_gdp = province_rank("总GDP(亿元)", 12)
top_share = province_rank("第一产业占GDP比重(%)", 12)
top_income = province_rank("农村居民人均可支配收入(元)", 12)

# 宏观趋势
macro_year = sorted([r["年份"] for r in MACRO if r.get("年份")])
def macro_series(key):
    return [[r["年份"], r[key]] for r in sorted(MACRO, key=lambda r: r["年份"]) if r.get(key) is not None]

urban_rural = [[r["年份"], r.get("城镇居民人均可支配收入(元)"), r.get("农村居民人均可支配收入(元)"), r.get("城乡收入倍差")]
               for r in sorted(MACRO, key=lambda r: r["年份"]) if r.get("城乡收入倍差")]

# ---------- 2. 作物数据 ----------
crops = json.load(open(ZN / "crops.json", encoding="utf-8"))["provinces"]

def province_crop(prov, indicator, n=26):
    d = crops.get(prov, {})
    inds = d.get("indicators", {})
    key = next((k for k in inds if indicator in k), None)
    if not key:
        return [], ""
    years = d.get("years", [])
    vals = inds[key]
    pairs = [[years[i], vals[i]] for i in range(min(len(years), len(vals))) if vals[i] is not None]
    pairs.sort()
    return pairs[-n:], key

area_sh, area_key = province_crop("上海", "农作物总播种面积")
area_he, _ = province_crop("河南", "农作物总播种面积")
area_hl, _ = province_crop("黑龙江", "农作物总播种面积")

# ---------- 3. GitHub 真实黄瓜价格数据 ----------
cucumber = []
try:
    with open(GH / "data.csv", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            try:
                cucumber.append([row["trade_time"], round(float(row["price"]), 3), round(float(row["temp"]), 1)])
            except (ValueError, KeyError):
                pass
except FileNotFoundError:
    pass

# ---------- 4. 茶文化真实数据（来自数据展示系统 ECharts）----------
tea_sales = [
    ["绿茶", 131.10, 2110.45], ["红茶", 38.13, 564.21], ["黑茶", 36.44, 321.35],
    ["乌龙茶", 24.84, 284.56], ["白茶", 8.13, 100.53], ["黄茶", 1.12, 14.17],
]
tea_export_years = ["2016", "2017", "2018", "2019", "2020", "2021", "2022"]
tea_export = [1.35, 1.49, 1.95, 2.07, 2.37, 2.43, 2.42]
tea_books = [
    ("《茶经》", "唐·陆羽", "世界上第一部茶学专著，奠定中国茶文化理论基础。"),
    ("《大观茶论》", "宋·赵佶", "宋徽宗所著，详述宋代点茶工艺与茶器。"),
    ("《茶录》", "宋·蔡襄", "论述茶汤品质与烹试方法。"),
    ("《煮泉小品》", "明·田艺蘅", "品水与煮茶的经典论述。"),
    ("《茶书全集》", "明·喻政", "明代茶书集大成之作。"),
    ("《续茶经》", "清·陆廷灿", "对《茶经》的续补，集历代茶事之大成。"),
]

# ---------- 5. 图表素材复制 ----------
chart_src = ROOT / "zn/智农宝_v2.2.0/site/assets/charts"
chart_dst = ASSET / "charts"
chart_dst.mkdir(parents=True, exist_ok=True)
chart_files = []
for p in sorted(chart_src.glob("*.png")):
    shutil.copy2(p, chart_dst / p.name)
    chart_files.append(p.name)

# 农田插画
img_src = ROOT / "zn/智农宝_v2.2.0/site/assets/img"
img_dst = ASSET / "img"
img_dst.mkdir(parents=True, exist_ok=True)
img_files = []
for p in sorted(img_src.glob("*.jpg")):
    shutil.copy2(p, img_dst / p.name)
    img_files.append(p.name)

# 茶文化图片：从百度图片目录挑几张代表性茶书封面
tea_src = DISP / "素材/百度图片"
tea_dst = ASSET / "tea"
tea_dst.mkdir(parents=True, exist_ok=True)
tea_imgs = []
if tea_src.exists():
    for p in sorted(tea_src.glob("*.jpg"))[:12]:
        shutil.copy2(p, tea_dst / p.name)
        tea_imgs.append(p.name)

# ---------- 6. 组装书 ----------
def chart_block(title, kind, data, note=""):
    return {"type": "chart", "title": title, "kind": kind, "data": data, "note": note}

def text_block(title, paras):
    return {"type": "text", "title": title, "paras": paras}

def kpi_block(items):
    return {"type": "kpi", "items": items}

def image_block(path, caption):
    return {"type": "image", "path": path, "caption": caption}

def table_block(title, headers, rows):
    return {"type": "table", "title": title, "headers": headers, "rows": rows}

books = []

# ==== 卷一：数据中国 ====
books.append({
    "id": "vol1", "title": "卷一 · 数据中国", "subtitle": "31省45年农业经济面板",
    "cover": "img/hero-farm.jpg", "color": "#1f9d55", "icon": "🌾",
    "intro": "从1980到2024，45年间中国农村经历了人类历史上规模最大的结构转型。本卷以31个省级地区的面板数据为经，以第一产业占比、农村居民收入、区域分化为纬，铺开一幅农业中国的长卷。",
    "chapters": [
        {"title": "第一章 · 引子：土地上的四十五年", "lead": "当第一产业占GDP的比重从近三成降到不足一成，消失的并非农业本身，而是它在国民经济中的相对位置。",
         "blocks": [
             text_block("一个国家的转身", [
                 "1980年，中国第一产业增加值占国内生产总值的比重接近30%，八亿人生活在农村。到2024年，这一比重降至8.4%。四十五年间，农业在国民经济中的相对份额缩小了超过三分之二。",
                 "这不是农业的衰退，而是中国经济结构升级的缩影。第二、第三产业以更快的速度增长，农业劳动力和资本持续向效率更高的部门转移。理解这一进程，是理解今日中国农村一切问题的起点。",
             ]),
             kpi_block([["31", "省级地区"], ["45", "年份跨度 1980–2024"], ["1,395", "面板记录"], ["8.4%", "2024年一产占比"]]),
             chart_block("全国第一产业占GDP比重（1980–2024）", "line", share_trend,
                         "口径：31省面板逐年均值。数据来自本机比赛工作簿，未独立核验国家统计局原表。"),
             image_block("img/hero-farm.jpg", "麦田：农业文明的恒久底色（AI 生成插画）"),
         ]},
        {"title": "第二章 · 经济版图：31省的总量与结构", "lead": "经济总量与农业占比呈现显著的空间分异——东部沿海以更小的农业份额支撑更高的总量，中西部则相反。",
         "blocks": [
             text_block("总量的梯度", [
                 f"在{latest}年，广东、江苏、山东位居地区生产总值前三。经济总量的空间格局与改革开放以来的区域发展战略高度吻合：沿海率先开放，制造业与服务业集聚，农业占比相应下降。",
                 "但总量不等于效率。第一产业占比高的地区，往往不是农业更发达，而是整体工业化程度较低。这一区别，是阅读后续所有图表时必须牢记的前提。",
             ]),
             chart_block(f"{latest}年各省GDP排名（Top 12，亿元）", "bar", top_gdp),
             chart_block(f"{latest}年各省第一产业占比（Top 12，%）", "bar", top_share),
             image_block("img/farm-digital.jpg", "数字农田鸟瞰：区域农业的空间组织（AI 生成插画）"),
         ]},
        {"title": "第三章 · 收入的爬坡：农村居民可支配收入", "lead": "农民收入的增长曲线，与城镇化、劳动力转移和农业技术进步三条线索交织在一起。",
         "blocks": [
             text_block("从温饱到小康", [
                 "1980年，农村居民人均可支配收入不足200元；2024年，这一数字已超过2万元，名义增长超过百倍。但收入的结构发生了根本变化：工资性收入占比持续上升，家庭经营纯收入的比重下降。",
                 "这意味着，今天农民的收入越来越取决于其在城市劳动力市场中的位置，而非单纯的作物产量。农业政策的着力点，也因此从增产转向增收。",
             ]),
             chart_block("农村居民人均可支配收入（1980–2024，元）", "line", income_trend),
             chart_block("全国GDP总量（1980–2024，亿元）", "area", gdp_trend),
         ]},
        {"title": "第四章 · 劳动力大迁移：结构转型的另一面", "lead": "第一产业就业人口比重的下降，是这一轮结构转型最深刻的社会事实。",
         "blocks": [
             text_block("离开土地的人", [
                 "2000年以来，第一产业就业人口比重持续下降，农民工规模突破2.9亿。外出务工成为农村家庭收入的主要来源之一，也重塑了乡村的年龄结构与家庭形态。",
                 "城乡收入倍差在2007年前后达到峰值后逐步收窄，但绝对差距仍然存在。乡村振兴战略的核心命题，正是如何在人口流动的大背景下重建乡村的产业与公共服务。",
             ]),
             chart_block("城乡收入与倍差（2000年起）", "multi", {
                 "labels": [r[0] for r in urban_rural],
                 "series": [
                     {"name": "城镇居民收入", "data": [r[1] for r in urban_rural]},
                     {"name": "农村居民收入", "data": [r[2] for r in urban_rural]},
                 ]
             }),
             chart_block("第一产业就业人口比重（%）", "line", macro_series("第一产业就业人口比重(%)")),
             chart_block("农业科技进步贡献率（%）", "line", macro_series("农业科技进步贡献率(%)")),
         ]},
        {"title": "第五章 · 尾声：数据里的中国乡村", "lead": "面板数据的每一个数字背后，都是一个具体的人、一块具体的田、一个具体的选择。",
         "blocks": [
             text_block("从数字回到人", [
                 "本卷呈现的是统计意义上的农业中国。它简化了无数个体的复杂处境，却也揭示了单一个案无法看见的长期趋势。",
                 "下一卷，我们将把镜头推近，从宏观面板走向具体的作物、田块与产量，看看在总量曲线的背后，田野里究竟生长着什么。",
             ]),
             kpi_block([["24", "宏观指标年份数"], ["232", "源数据文件"], ["24", "分析图表"]]),
         ]},
    ],
})

# ==== 卷二：作物与田畴 ====
books.append({
    "id": "vol2", "title": "卷二 · 作物与田畴", "subtitle": "播种面积、产量与市场",
    "cover": "img/crop-rice.jpg", "color": "#2f9e6e", "icon": "🌱",
    "intro": "宏观数据之下，是每一季作物的具体生长。本卷从播种面积入手，串联作物产量、市场价格与数字农田，让数据落回田畴之间。",
    "chapters": [
        {"title": "第一章 · 播种面积的变迁", "lead": "播种面积是农业最基础的变量，它的每一次伸缩，都记录着农户对市场与政策的回应。",
         "blocks": [
             text_block("土地的用途", [
                 "以上海为例，农作物总播种面积从2000年的约521千公顷下降到2025年的约220千公顷。这背后是快速城镇化对农业用地的挤压，也是都市农业向高附加值方向的转型。",
                 "相比之下，河南、黑龙江等农业主产区的播种面积保持稳定甚至增长。土地的流向，勾勒出中国农业生产重心的北移与集中。",
             ]),
             chart_block("上海农作物总播种面积（2000–2025，千公顷）", "line", area_sh),
             chart_block("河南农作物总播种面积（2000–2025，千公顷）", "line", area_he),
             chart_block("黑龙江农作物总播种面积（2000–2025，千公顷）", "line", area_hl),
             image_block("img/crop-rice.jpg", "水稻田：播种面积变化的主角之一（AI 生成插画）"),
         ]},
        {"title": "第二章 · 市场脉动：来自真实交易数据的价格", "lead": "价格的每一次跳动，都是供需、天气与预期的合力。这里我们用一组公开的real-world交易数据，还原市场价格的温度。",
         "blocks": [
             text_block("一组真实的交易记录", [
                 "以下数据来自 GitHub 开源项目 Asong205/price_yield_dataset（Apache-2.0 许可），记录了山东临沂黄瓜市场逐日的交易价格与气温。数据集规模为原始55万条中的公开样本部分。",
                 "价格与气温的关系并不简单：低温可能推高运输与保温成本，高温则影响供应节奏。观察价格的波动，比观察单一价格点更有价值。",
             ]),
             chart_block("黄瓜市场逐日价格（真实交易数据，元/公斤）", "line",
                         [[r[0], r[1]] for r in cucumber],
                         "数据来源：GitHub Asong205/price_yield_dataset，Apache-2.0。仅取公开样本部分。"),
             kpi_block([[str(len(cucumber)), "交易日样本"], ["临沂", "山东 · 黄瓜市场"],
                        [f"{min(r[1] for r in cucumber):.2f}" if cucumber else "—", "最低价(元/kg)"],
                        [f"{max(r[1] for r in cucumber):.2f}" if cucumber else "—", "最高价(元/kg)"]]),
             image_block("img/crop-greenhouse.jpg", "温室大棚：价格波动背后的生产方式（AI 生成插画）"),
         ]},
        {"title": "第三章 · 数字农田生态", "lead": "当传感器、无人机与数据平台进入农田，农业生产开始拥有自己的\"数字神经系统\"。",
         "blocks": [
             text_block("四情监测：苗情、墒情、虫情、灾情", [
                 "数字农田的核心，是把田间状态转化为可计算的数据。苗情反映作物长势，墒情描述土壤水分，虫情预警病虫害，灾情评估极端天气影响。四类数据合并，构成农田的\"体检报告\"。",
                 "地块级管理让差异化投入成为可能：哪里该多浇水，哪里该少施肥，不再依赖经验 Estimation，而是基于空间数据和作物模型。",
             ]),
             kpi_block([["4", "情监测维度"], ["NDVI", "长势遥感指数"], ["3s", "数据刷新周期"], ["7×24", "连续监测"]]),
             image_block("img/farm-digital.jpg", "数字孪生农田：分区、网格与数据图层（AI 生成插画）"),
             image_block("img/crop-corn.jpg", "玉米田：精准农业的典型应用场景（AI 生成插画）"),
         ]},
        {"title": "第四章 · 尾声：从田畴到餐桌", "lead": "作物离开农田之后，还有一段关于流通、加工与消费的旅程。",
         "blocks": [
             text_block("下一站，茶香", [
                 "作物与田畴的故事，讲的是农业生产的一端。而农产品真正的价值，最终要在消费端实现。",
                 "接下来的一卷，我们把目光转向一种特殊的作物——茶。它既是农产品，也是文化符号，其数据背后承载着中国市场与贸易的独特逻辑。",
             ]),
         ]},
    ],
})

# ==== 卷三：茶香数据志 ====
books.append({
    "id": "vol3", "title": "卷三 · 茶香数据志", "subtitle": "中国茶叶的生产、贸易与消费",
    "cover": "img/crop-orchard.jpg", "color": "#8a6d3b", "icon": "🍵",
    "intro": "茶，是中国农业中最具文化厚度的一章。本卷整理自\"数据展示系统\"中的茶文化数据，从典籍、产量、贸易到消费，勾勒一片茶叶背后的产业图谱。",
    "chapters": [
        {"title": "第一章 · 茶的前世今生", "lead": "从神农尝百草到宋代点茶，茶的历史几乎与中国文明史同步。",
         "blocks": [
             text_block("一部茶书，半部文化史", [
                 "中国是世界上最早发现和利用茶树的国家。唐代陆羽著《茶经》，是世界上第一部茶学专著；宋代赵佶《大观茶论》详述点茶工艺；明清以降，茶书层出不穷，形成庞大的茶学文献体系。",
                 "以下列出部分代表性茶书，均来自\"数据展示系统\"中的茶书典籍素材。",
             ]),
             table_block("中国代表性茶书典籍", ["书名", "作者", "要义"],
                         [[b[0], b[1], b[2]] for b in tea_books]),
             image_block("tea/" + (tea_imgs[0] if tea_imgs else "《大观茶论》.jpg"), "茶书典籍封面（数据展示系统素材）"),
         ]},
        {"title": "第二章 · 六大茶类的产量与产值", "lead": "2022年，中国六大茶类中绿茶以内销131万吨、2110亿元稳居首位。",
         "blocks": [
             text_block("绿红黑白乌黄", [
                 "中国茶分为绿茶、红茶、黑茶、乌龙茶、白茶、黄茶六大类。2022年，绿茶内销量131.10万吨，内销额2110.45亿元，占据绝对主导；红茶次之，内销量38.13万吨。",
                 "白茶与黄茶体量较小，但单位价值不低：白茶8.13万吨对应100.53亿元，黄茶1.12万吨对应14.17亿元。小众茶类的价值逻辑，与大众茶完全不同。",
             ]),
             chart_block("2022年六大茶类内销量（万吨）", "bar", [[r[0], r[1]] for r in tea_sales]),
             chart_block("2022年六大茶类内销额（亿元）", "bar", [[r[0], r[2]] for r in tea_sales]),
             table_block("2022年六大茶类内销明细", ["茶类", "内销量(万吨)", "内销额(亿元)"],
                         [[r[0], r[1], r[2]] for r in tea_sales]),
         ]},
        {"title": "第三章 · 茶贸经纬：出口与世界", "lead": "2022年，中国茶叶出口额20.8亿美元，近七年出口量稳定在1.3–2.4万吨区间。",
         "blocks": [
             text_block("一片叶子的海外之旅", [
                 "中国是世界最大的茶叶生产国，也是重要的茶叶出口国。2022年出口额20.8亿美元，绿茶是出口的主力品类。出口量的年度波动，反映国际市场需求与国内供给的双重影响。",
             ]),
             chart_block("近7年茶叶出口数量（万吨）", "line",
                         [[tea_export_years[i], tea_export[i]] for i in range(len(tea_export_years))]),
             kpi_block([["20.8", "2022出口额(亿美元)"], ["6", "茶类品类"],
                        ["1.35–2.43", "近7年出口量(万吨)"], ["世界第一", "茶叶产量地位"]]),
         ]},
        {"title": "第四章 · 尾声：数据的边界", "lead": "茶文化数据来自历史比赛项目，涉及的数值请按\"参考数据\"理解。",
         "blocks": [
             text_block("诚实的注脚", [
                 "本卷数据整理自本机的\"数据展示系统\"历史项目（ECharts 大屏源码），属于比赛作品中的资料汇编。其中部分数值可能来自公开报道与行业报告，未逐一核验原始统计口径。",
                 "我们保留这些数据的原貌，并明确标注其来源性质——这是对所有使用者最基本的尊重。",
             ]),
         ]},
    ],
})

# ==== 卷四：预测与决策 ====
books.append({
    "id": "vol4", "title": "卷四 · 预测与决策", "subtitle": "让数据帮农民少亏钱",
    "cover": "img/crop-corn.jpg", "color": "#c47f1a", "icon": "📈",
    "intro": "数据的价值，最终要落到决策上。本卷把预测模型与风险判断结合，回答一个朴素的问题：今年种什么、种多少、怎么才能不亏。",
    "chapters": [
        {"title": "第一章 · 预测的原理", "lead": "预测不是预言，而是在历史数据中找到可被外推的规律。",
         "blocks": [
             text_block("趋势从哪里来", [
                 "本系统提供两类本地预测：线性趋势外推与指数趋势外推。前者假设变量随时间匀速变化，后者假设按比例增长。两种方法都计算拟合优度R²，用于判断趋势的可靠性。",
                 "预测的精度上限由数据质量决定。历史数据中的结构性断点——如政策变化、气候异常——会让简单外推失效。因此所有预测结果都应结合专家判断使用。",
             ]),
             chart_block("全国第一产业占GDP比重趋势外推", "line", share_trend,
                         "实线为历史值。预测请在系统的\"趋势预测\"页面交互查看。"),
         ]},
        {"title": "第二章 · 保本价与风险评级", "lead": "种一亩地要花多少钱？卖多少钱才不亏？这是每个农户最关心的问题。",
         "blocks": [
             text_block("从成本到保本", [
                 "保本价 = 总成本 ÷ 预期产量。当市场价低于保本价，种植就会亏损。系统根据作物、面积、种子、化肥、人工等参数，自动测算保本价、保本单产与预期利润，并用红黄绿三色给出风险评级。",
                 "更进一步地，系统提供售价×单产的敏感性矩阵：在±20%的价格与产量波动下，利润会如何变化。这种\"最坏情况\"思维，是防止亏损的关键。",
             ]),
             kpi_block([["3", "风险等级(红黄绿)"], ["±20%", "敏感性波动区间"],
                        ["8", "作物参考品类"], ["0", "数据上传云端"]]),
             image_block("img/crop-greenhouse.jpg", "设施农业：可控环境下的成本与收益（AI 生成插画）"),
         ]},
        {"title": "第三章 · 尾声：让数据成为新农具", "lead": "最好的预测，是让人在做决定时多一分把握。",
         "blocks": [
             text_block("工具的价值", [
                 "本系统所有计算均在本机完成，数据不联网、不上传。预测使用的是历史面板与内置参考值，属于演示级分析工具，不作为实际生产决策的唯一依据。",
                 "我们的目标不是替代农户的经验，而是为经验提供一个可对照的数据视角。",
             ]),
         ]},
    ],
})

# 组装最终 JSON
result = {
    "meta": {
        "title": "智农宝 · 农业数据全书",
        "subtitle": "一部可以翻阅的数据之书",
        "version": "3.0.0",
        "source_note": "数据来源：本机比赛工作簿 + 数据展示系统历史项目 + GitHub 开源数据集（Apache-2.0）",
        "built": "2026-11-23",
        "counts": {
            "books": len(books),
            "chapters": sum(len(b["chapters"]) for b in books),
            "panel_records": len(PANEL),
            "source_files": 232,
        }
    },
    "books": books,
    "assets": {"charts": chart_files, "img": img_files, "tea": tea_imgs},
}

out = OUT / "book_data.json"
json.dump(result, open(out, "w", encoding="utf-8"), ensure_ascii=False, separators=(",", ":"))
print("book_data.json written:", out.stat().st_size // 1024, "KB")
print("books:", len(books), "chapters:", result["meta"]["counts"]["chapters"])
print("charts:", len(chart_files), "img:", len(img_files), "tea:", len(tea_imgs))
