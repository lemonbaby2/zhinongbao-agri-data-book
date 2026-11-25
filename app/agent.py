# -*- coding: utf-8 -*-
"""智农宝决策 Agent 内核。

设计要点
- 双引擎：配置了 LLM（OpenAI 兼容）就走 function-calling；没配置就走本地规则引擎（离线可答）。
- 工具即能力：省份面板 / 广东市域 / 排名 / 趋势外推 / 种植保本 / 全书检索 / 城市画像。
- 全部数据离线，不联网也能回答；联网只在调用大模型时发生。
"""
import json
import os
import re
import urllib.request
import urllib.error
from pathlib import Path

# ---------------------------------------------------------------- 配置

def state_dir():
    base = os.environ.get("APPDATA") or os.path.expanduser("~")
    d = Path(base) / "ZhinongbaoBook"
    d.mkdir(parents=True, exist_ok=True)
    return d


LLM_CONF = state_dir() / "llm.json"
LLM_DEFAULT = {"base_url": "", "api_key": "", "model": "qwen-plus"}


def load_llm_conf():
    conf = dict(LLM_DEFAULT)
    if LLM_CONF.exists():
        try:
            conf.update(json.loads(LLM_CONF.read_text(encoding="utf-8")))
        except Exception:
            pass
    return conf


def save_llm_conf(conf):
    LLM_CONF.write_text(json.dumps(conf, ensure_ascii=False, indent=2), encoding="utf-8")


# ---------------------------------------------------------------- 数据仓

METRIC_ALIASES = [
    (["一产占比", "第一产业占", "农业比重", "农业占比"], "第一产业占GDP比重(%)"),
    (["一产gdp", "第一产业gdp", "农业gdp", "一产产值"], "第一产业GDP(亿元)"),
    (["人均gdp"], "人均GDP(元)"),
    (["gdp", "生产总值", "经济总量", "经济规模"], "总GDP(亿元)"),
    (["收入", "可支配", "农民收入", "农村居民收入"], "农村居民人均可支配收入(元)"),
    (["人口", "常住人口"], "常住人口(万人)"),
    (["一产收入", "农业收入"], "农村居民人均第一产业收入估算(元)"),
]

MACRO_ALIASES = [
    (["城乡收入倍差", "倍差", "城乡差距"], "城乡收入倍差"),
    (["农民工月", "月均收入"], "农民工月均收入(元/人)"),
    (["一产就业", "农业就业", "就业比重"], "第一产业就业人口比重(%)"),
    (["科技进步", "科技贡献"], "农业科技进步贡献率(%)"),
    (["数字农业农村", "数字化水平"], "县域数字农业农村发展总体水平(%)"),
    (["农药", "农药利用率"], "农药有效利用率(%)"),
    (["农民工", "外出农民工"], "农民工人数(万人)"),
]

CITY_METRICS = {
    "gdp_wan": ("GDP(亿元)", 1 / 10000),
    "agri_share": ("第一产业占比(%)", 1),
    "agri_emp_share": ("一产就业比重(%)", 1),
    "pop": ("年末总人口(万人)", 1),
    "gdp_pc": ("人均GDP(元)", 1),
    "ind2_share": ("第二产业占比(%)", 1),
    "ind3_share": ("第三产业占比(%)", 1),
    "gdp_growth": ("GDP增速(%)", 1),
}

CITY_ALIASES = [
    (["一产", "农业占比", "农业比重", "种地", "依赖农业"], "agri_share"),
    (["就业"], "agri_emp_share"),
    (["人口"], "pop"),
    (["人均"], "gdp_pc"),
    (["二产", "工业"], "ind2_share"),
    (["三产", "服务业"], "ind3_share"),
    (["增速", "增长"], "gdp_growth"),
    (["gdp", "生产总值", "经济体量"], "gdp_wan"),
]

# 主要大田作物：单产(公斤/亩) / 出售价(元/公斤) / 亩成本(元)
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


class DataHub:
    """懒加载全部离线数据，供 Agent 工具调用。"""

    def __init__(self, base=None):
        self.base = Path(base) if base else Path(__file__).resolve().parent
        self._panel = None
        self._macro = None
        self._gd = None
        self._reform = None
        self._crops = None
        self._book = None

    def _read(self, rel):
        p = self.base / rel
        if not p.exists():
            return None
        try:
            return json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            return None

    @property
    def panel(self):
        if self._panel is None:
            d = self._read("site/data/dashboard.json") or {}
            self._panel = (d.get("panel") or {}).get("rows", [])
            self._years = d.get("years", [])
            self._provinces = d.get("provinces", [])
        return self._panel

    @property
    def years(self):
        self.panel
        return getattr(self, "_years", [])

    @property
    def provinces(self):
        self.panel
        return getattr(self, "_provinces", [])

    @property
    def macro(self):
        if self._macro is None:
            d = self._read("site/data/dashboard.json") or {}
            rows = (d.get("macro") or {}).get("rows", [])
            # 原始工作簿的宏观表年份列被倒置：年份升序时收入却递减。
            # 只翻转年份标签，不碰任何数值，保持与统计公报一致。
            col = "农村居民人均可支配收入(元)"
            pairs = [(r.get("年份"), r.get(col)) for r in rows if r.get(col) is not None]
            if len(pairs) >= 6:
                xs = [p[0] for p in pairs]
                ys = [p[1] for p in pairs]
                mx = sum(xs) / len(xs)
                my = sum(ys) / len(ys)
                cov = sum((a - mx) * (b - my) for a, b in zip(xs, ys))
                if cov < 0:
                    years = sorted(xs)
                    for i, r in enumerate(rows):
                        if r.get("年份") is not None:
                            r["年份"] = years[len(years) - 1 - i]
                    rows.sort(key=lambda r: r.get("年份") or 0)
            self._macro = rows
        return self._macro

    @property
    def gd(self):
        if self._gd is None:
            self._gd = self._read("data/guangdong.json") or {}
        return self._gd

    @property
    def reform(self):
        if self._reform is None:
            self._reform = self._read("data/guangdong_reform.json") or {}
        return self._reform

    @property
    def crops(self):
        if self._crops is None:
            self._crops = self._read("site/data/crops.json") or {}
        return self._crops

    @property
    def book(self):
        if self._book is None:
            self._book = self._read("data/book_data.json") or {}
        return self._book

    # -------- 基础查询

    def norm_province(self, text):
        for p in self.provinces:
            for suffix in ["", "省", "市", "自治区", "壮族自治区", "回族自治区", "维吾尔自治区"]:
                pass
            if p in text:
                return p
        # 常见简称
        alias = {"广东": "广东", "广西": "广西", "上海": "上海", "北京": "北京", "重庆": "重庆",
                 "内蒙": "内蒙古", "黑龙": "黑龙江", "新疆": "新疆", "西藏": "西藏", "宁夏": "宁夏"}
        for k, v in alias.items():
            if k in text and v in self.provinces:
                return v
        return None

    def norm_city(self, text):
        cities = list((self.gd.get("cities") or {}).keys())
        for c in cities:
            if c in text or c.replace("市", "") in text:
                return c
        return None

    def detect_metric(self, text):
        t = text.lower()
        for keys, col in METRIC_ALIASES:
            if any(k in t for k in keys):
                return col
        for keys, col in MACRO_ALIASES:
            if any(k in t for k in keys):
                return col
        return None

    def detect_city_metric(self, text):
        t = text.lower()
        for keys, col in CITY_ALIASES:
            if any(k in t for k in keys):
                return col
        return "gdp"

    def series(self, province, col):
        rows = [r for r in self.panel if r.get("省份") == province and r.get(col) is not None]
        return [(r["年份"], r[col]) for r in rows]

    def macro_series(self, col):
        rows = [r for r in self.macro if r.get(col) is not None]
        return [(r["年份"], r[col]) for r in rows]

    def latest(self, province, col):
        s = self.series(province, col)
        return s[-1] if s else (None, None)

    def rank(self, col, year, top=5, asc=False):
        vals = [(r["省份"], r[col]) for r in self.panel if r.get("年份") == year and r.get(col) is not None]
        vals.sort(key=lambda x: x[1], reverse=not asc)
        return vals[:top]

    def city_series(self, city, key):
        c = (self.gd.get("cities") or {}).get(city) or {}
        return [(r["year"], r[key]) for r in c.get("series", []) if r.get(key) is not None]


# ---------------------------------------------------------------- 工具

def build_tools(hub: DataHub):
    """返回 [{name, desc, params, fn}]，供 LLM function-calling 与离线规则共用。"""

    def t_province(province, metric=None):
        col = hub.detect_metric(metric or "") if metric else None
        col = col or "第一产业占GDP比重(%)"
        p = hub.norm_province(province or "")
        if not p:
            return {"error": f"未识别到省份：{province}"}
        y, v = hub.latest(p, col)
        s = hub.series(p, col)
        first = s[0] if s else (None, None)
        chg = round(v - first[1], 2) if first[1] not in (None, 0) and v is not None else None
        return {"province": p, "metric": col, "year": y, "value": v,
                "first_year": first[0], "first_value": first[1], "change": chg,
                "series_tail": s[-8:]}

    def t_rank(metric, year=None, top=8, asc=False):
        col = hub.detect_metric(metric or "") or "第一产业占GDP比重(%)"
        y = int(year) if year else (hub.years[-1] if hub.years else 2024)
        return {"metric": col, "year": y, "ranking": hub.rank(col, y, top, asc)}

    def t_trend(scope, metric, forecast=3):
        col = hub.detect_metric(metric or "")
        if not col:
            return {"error": f"未识别指标：{metric}"}
        p = hub.norm_province(scope or "")
        s = hub.series(p, col) if p else hub.macro_series(col)
        if len(s) < 3:
            return {"error": "数据点不足"}
        # 用最近 10 年拟合，避免长周期凸增长被老数据拉低
        fc = forecast_linear(s[-10:], int(forecast))
        return {"scope": p or "全国宏观", "metric": col, "points": len(s),
                "latest": s[-1], "forecast": fc}

    def t_cities(city=None, metric=None):
        key = hub.detect_city_metric(metric or "")
        label, factor = CITY_METRICS.get(key, ("GDP(亿元)", 1))
        if city:
            c = hub.norm_city(city)
            if not c:
                return {"error": f"未识别广东城市：{city}", "available": list(hub.gd.get("cities", {}).keys())}
            raw = hub.city_series(c, key)
            s = [(y, round(v * factor, 2)) for y, v in raw]
            try:
                reg = hub.gd["cities"][c].get("region")
            except Exception:
                reg = ""
            if not s:
                return {"error": f"{c} 的 {label} 无有效观测", "city": c, "metric": label}
            return {"city": c, "region": reg, "metric": label, "latest": s[-1],
                    "first": s[0], "points": len(s), "series_tail": s[-6:]}
        # 无城市 → 给排名
        rows = []
        for c, v in (hub.gd.get("cities") or {}).items():
            s = hub.city_series(c, key)
            if s:
                rows.append((c, round(s[-1][1] * factor, 2), v.get("region")))
        rows.sort(key=lambda x: x[1], reverse=True)
        return {"metric": label, "year": 2018, "ranking": rows[:10], "count": len(rows)}

    def t_cost(crop=None, area=10, price=None, yield_=None, cost=None):
        name = crop or "水稻"
        hit = None
        for k in CROP_REF:
            if k in name:
                hit = k
                break
        ref = CROP_REF.get(hit or "水稻")
        yld = float(yield_) if yield_ else ref["yield"]
        prc = float(price) if price else ref["price"]
        cst = float(cost) if cost else ref["cost"]
        a = float(area or 10)
        revenue = yld * prc
        profit_mu = revenue - cst
        breakeven_price = cst / yld if yld else None
        breakeven_yield = cst / prc if prc else None
        margin = profit_mu / revenue * 100 if revenue else 0
        if margin >= 25:
            level, advice = "低风险", "利润空间充足，可按计划扩种；建议锁定 30% 订单对冲价格回落。"
        elif margin >= 8:
            level, advice = "中风险", "利润偏薄，优先降本（统一采购/机械化）或改种高附加值品种。"
        elif margin >= 0:
            level, advice = "偏高风险", "接近盈亏平衡，任何价格下跌都会亏损；建议缩面积并投保。"
        else:
            level, advice = "高风险", "当前参数下必然亏损，不建议种植；或改种/改期/改销售渠道。"
        return {"crop": hit or name, "area_mu": a, "yield_per_mu": yld, "price": prc,
                "cost_per_mu": cst, "revenue_per_mu": round(revenue, 1),
                "profit_per_mu": round(profit_mu, 1), "total_profit": round(profit_mu * a, 1),
                "margin_pct": round(margin, 1), "breakeven_price": round(breakeven_price, 2),
                "breakeven_yield": round(breakeven_yield, 0), "risk": level, "advice": advice}

    def t_search(keyword):
        kw = (keyword or "").strip()
        if not kw:
            return {"error": "关键词为空"}
        hits = []
        for b in hub.book.get("books", []):
            for i, ch in enumerate(b.get("chapters", [])):
                blob = ch.get("title", "") + ch.get("lead", "")
                for bl in ch.get("blocks", []):
                    blob += bl.get("title", "") or ""
                    blob += " ".join(bl.get("paras", []) or [])
                    if bl.get("type") == "table":
                        blob += " ".join(str(c) for r in bl.get("rows", []) for c in r)
                if kw in blob:
                    hits.append({"book": b["title"], "book_id": b["id"], "chapter": ch["title"],
                                 "index": i, "snippet": blob[max(0, blob.find(kw) - 30):blob.find(kw) + 70]})
        return {"keyword": kw, "count": len(hits), "hits": hits[:6]}

    def t_gd_reform(metric=None, year=None):
        """广东省统计局官方 1978—2025 长面板查询（含 2026 预测）。"""
        SERIES = {
            "农林牧渔业总产值": "gross_output", "总产值": "gross_output", "农业产值": "gross_output",
            "农民收入": "rural_income", "可支配收入": "rural_income", "农村居民收入": "rural_income",
            "收入": "rural_income", "恩格尔": "engel", "住房": "housing", "居住": "housing",
            "粮食": "grain_output", "粮食产量": "grain_output",
            "一产增加值": "first_value_added", "第一产业增加值": "first_value_added",
            "GDP": "gdp", "地区生产总值": "gdp",
            "蔬菜": "vegetable_output", "水果": "fruit_output", "茶叶": "tea_output",
            "水产品": "aquatic_output", "猪肉": "pork_output",
        }
        name = metric or ""
        key = next((v for k, v in SERIES.items() if k in name), None)
        key = key or "rural_income"
        LABELS = {
            "gross_output": "农林牧渔业总产值", "rural_income": "农村居民人均可支配收入",
            "engel": "恩格尔系数", "housing": "人均住房建筑面积",
            "grain_output": "粮食产量", "first_value_added": "第一产业增加值",
            "gdp": "地区生产总值", "vegetable_output": "蔬菜产量",
            "fruit_output": "园林水果产量", "tea_output": "茶叶产量",
            "aquatic_output": "水产品产量", "pork_output": "猪肉产量",
        }
        s = (hub.reform.get("series") or {}).get(key) or []
        s = [[int(y), float(v)] for y, v in s if y is not None and v is not None]
        d = dict(s)
        picked = None
        if year:
            m = re.search(r"(?:19|20)\d{2}", str(year))
            if m:
                yy = int(m.group(0))
                picked = [yy, d.get(yy)]
        return {
            "metric": key, "label": LABELS.get(key, key), "points": len(s),
            "first": s[0] if s else None, "latest": s[-1] if s else None,
            "picked": picked, "series": s,
            "projection": (hub.reform.get("projection_2026") or {}).get(key),
            "source": "广东省统计局官方年鉴与公报（1978—2025），2026 为模型预测",
        }

    def t_gd_overview():
        p = hub.gd.get("province_2024") or {}
        cities = hub.gd.get("cities") or {}
        top = []
        for c, v in cities.items():
            s = hub.city_series(c, "gdp")
            if s:
                top.append((c, round(s[-1][1] / 10000, 1), v.get("region")))
        top.sort(key=lambda x: x[1], reverse=True)
        return {"province_2024": p, "city_count": len(cities), "top_cities": top[:8],
                "note": "市域数据来自《中国城市统计年鉴》开源面板 1999–2018；省级为 2024 公报"}

    def t_action_plan(crop=None, area=10, price=None, yield_=None, cost=None, problem=None):
        """行动型 Agent：诊断 → 决策 → 措施 → 预期 → 复核，一次输出可执行处方。

        与 cost_plan 的区别：cost_plan 只给测算；action_plan 给出带触发条件、
        具体动作与事后复核指标的完整行动链，可直接抄到台账执行。
        """
        diag = t_cost(crop=crop, area=area, price=price, yield_=yield_, cost=cost)
        name = diag["crop"]
        margin = diag["margin_pct"]
        risk = diag["risk"]
        # 诊断：按利润率与用户描述定位问题类型
        pdesc = (problem or "")
        if any(k in pdesc for k in ["卖", "价", "销", "渠道", "收购"]):
            ptype = "价格/渠道型"
        elif any(k in pdesc for k in ["成本", "化肥", "人工", "贵"]):
            ptype = "成本型"
        elif any(k in pdesc for k in ["产量", "单产", "种不出", "病害"]):
            ptype = "产量型"
        elif margin < 8:
            ptype = "价格/成本型（按利润率推断）"
        else:
            ptype = "综合型（未指定问题，按利润率推断）"

        be_price = diag["breakeven_price"]
        # 触发条件：价格跌破保本价 105%
        trigger_price = round(be_price * 1.05, 2) if be_price else None
        if risk in ("低风险",):
            decision = "利润率充足，允许小步扩种；保留对照田，锁定 30% 订单对冲价格回落。"
            measures = [
                "维持或小幅扩大面积，单次增幅不超过 20%",
                "保留 20% 面积作对照，记录分块单产",
                "联系 1—2 个订单渠道，锁定约 30% 产量",
                "完整记录种子/化肥/人工/机械逐项成本",
            ]
        elif risk in ("中风险",):
            decision = "利润偏薄，优先降本；暂不扩种，做好锁价与台账。"
            measures = [
                "停止扩种，维持现有面积",
                "统一采购种子化肥，压低单价",
                "以共用机械替代部分人工",
                "锁定 30% 订单，规避价格回落",
            ]
        elif risk == "偏高风险":
            decision = "接近盈亏平衡，任何价格下跌都会亏损；缩面积并投保。"
            measures = [
                "缩减面积 20%—30%，先止住现金流风险",
                "查询当地农业保险 coverage 并投保",
                "联系订单农业，约定最低收购价",
                "核算成本结构，找出占比最大的一项",
            ]
        else:
            decision = "当前参数下必然亏损，不建议种植；先止损再考虑改种。"
            measures = [
                "本季不种或改种高附加值品种",
                "若已种植，锁定任何能覆盖变动成本的售价",
                "暂停新增投入，避免亏损扩大",
                "复盘：单产/价格/成本哪一项失真",
            ]
        expected = ("在" + ptype + "场景下，把亏损概率压到可承受范围；" +
                    ("目标利润率回到 10% 以上。" if margin < 10 else "保持当前利润水平。"))
        verify = ("下季实际售价、实际单产、亩成本、是否签单/投保；"
                  "连续三次同方向偏差需重选模型或改阈值。")
        return {
            "tool": "action_plan", "problem_type": ptype, "crop": name,
            "diagnosis": {"profit_per_mu": diag["profit_per_mu"],
                          "margin_pct": diag["margin_pct"], "risk": risk,
                          "breakeven_price": be_price,
                          "breakeven_yield": diag["breakeven_yield"]},
            "trigger": f"售价跌破 {trigger_price} 元/公斤（保本价 × 105%）时触发处置",
            "decision": decision, "measures": measures,
            "expected": expected, "verify": verify,
            "authority": "本处方为建议，须由农户/农技员确认后执行；系统不下发指令。",
        }

    tools = [
        {"name": "action_plan", "fn": t_action_plan,
         "desc": "行动型决策：诊断问题类型并输出触发条件/决策/措施/预期/复核的完整干预处方（五段式）",
         "params": {"crop": "作物", "area": "亩数", "price": "售价", "yield_": "单产",
                    "cost": "亩成本", "problem": "问题描述，如 卖不上价/成本太高/产量低"}},
        {"name": "query_province", "fn": t_province,
         "desc": "查询某个省级地区的最新指标值与历史序列",
         "params": {"province": "省名，如 广东", "metric": "指标，如 一产占比/GDP/收入/人口"}},
        {"name": "rank_provinces", "fn": t_rank,
         "desc": "按指标对 31 省排名",
         "params": {"metric": "指标", "year": "年份，可省略", "top": "取前几名", "asc": "是否升序"}},
        {"name": "trend_forecast", "fn": t_trend,
         "desc": "取某省或全国宏观指标的历史序列并做线性外推",
         "params": {"scope": "省份名，或全国", "metric": "指标", "forecast": "外推年数"}},
        {"name": "query_cities", "fn": t_cities,
         "desc": "查询广东 21 个地级市指标；不传城市则返回排名",
         "params": {"city": "城市名，如 深圳", "metric": "指标，如 GDP/一产占比/人口"}},
        {"name": "cost_plan", "fn": t_cost,
         "desc": "种植保本与风险测算：保本价、亩利润、风险等级与建议",
         "params": {"crop": "作物", "area": "亩数", "price": "售价元/公斤", "yield_": "单产公斤/亩", "cost": "亩成本元"}},
        {"name": "search_book", "fn": t_search,
         "desc": "在全书 35 章中检索关键词，返回章节定位",
         "params": {"keyword": "关键词"}},
        {"name": "gd_overview", "fn": t_gd_overview,
         "desc": "广东农业与市域经济全景概览",
         "params": {}},
        {"name": "gd_reform_query", "fn": t_gd_reform,
         "desc": "查询广东改革开放 1978—2025 官方长面板：总产值/农民收入/恩格尔/粮食/住房/GDP，含 2026 预测",
         "params": {"metric": "指标名，如 农民收入/总产值/粮食产量/恩格尔/住房", "year": "年份，可省略"}},
    ]
    return tools


def forecast_linear(pairs, years_ahead=3):
    """最小二乘线性外推，返回 [(year, value, r2)] 与斜率说明。"""
    n = len(pairs)
    xs = list(range(n))
    ys = [v for _, v in pairs]
    mx = sum(xs) / n
    my = sum(ys) / n
    sxx = sum((x - mx) ** 2 for x in xs)
    sxy = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    if sxx == 0:
        return []
    b = sxy / sxx
    a = my - b * mx
    ss_tot = sum((y - my) ** 2 for y in ys)
    ss_res = sum((y - (a + b * x)) ** 2 for x, y in zip(xs, ys))
    r2 = 1 - ss_res / ss_tot if ss_tot else 0
    last_year = pairs[-1][0]
    out = []
    for k in range(1, years_ahead + 1):
        out.append([last_year + k, round(a + b * (n - 1 + k), 2), round(r2, 3)])
    return out


# ---------------------------------------------------------------- LLM 客户端

class LLMError(Exception):
    pass


def llm_chat(conf, messages, tools=None, timeout=60):
    base = (conf.get("base_url") or "").rstrip("/")
    key = conf.get("api_key") or ""
    if not base or not key:
        raise LLMError("未配置大模型")
    url = base if base.endswith("/chat/completions") else base + "/chat/completions"
    payload = {"model": conf.get("model") or "gpt-4o-mini", "messages": messages, "temperature": 0.3}
    if tools:
        payload["tools"] = [{"type": "function",
                             "function": {"name": t["name"], "description": t["desc"],
                                          "parameters": {"type": "object",
                                                         "properties": {k: {"type": "string", "description": v}
                                                                        for k, v in t["params"].items()},
                                                         "required": []}}}
                            for t in tools]
        payload["tool_choice"] = "auto"
    req = urllib.request.Request(
        url, data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {key}"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", "ignore")[:300]
        raise LLMError(f"HTTP {e.code}: {body}")
    except Exception as e:
        raise LLMError(f"连接失败：{type(e).__name__}: {e}")


# ---------------------------------------------------------------- Agent

SYSTEM_PROMPT = """你是「智农宝」农业决策助手，服务于中国农业经营与政策研究场景。
规则：
1. 先用工具查真实数据，再下结论；不要编造数字。
2. 回答结构：先给结论一句话，再给关键数据（可用短表格），最后给一条可执行建议。
3. 数据边界要说清：31省面板1980-2024来自比赛工作簿；广东21市为《中国城市统计年鉴》1999-2018；作物单产/价格为参考值。
4. 涉及种植决策时必须给风险等级与保本价。
5. 中文回答，简洁，不超过 400 字。"""


class Reply:
    def __init__(self, text, steps=None, engine="离线规则", chart=None):
        self.text = text
        self.steps = steps or []
        self.engine = engine
        self.chart = chart


class Agent:
    def __init__(self, hub: DataHub):
        self.hub = hub
        self.tools = build_tools(hub)
        self.by_name = {t["name"]: t for t in self.tools}

    # ---------------- 对外入口

    def ask(self, question):
        conf = load_llm_conf()
        if conf.get("api_key") and conf.get("base_url"):
            try:
                return self._llm_ask(question, conf)
            except LLMError as e:
                r = self._offline_ask(question)
                r.text = f"⚠️ 大模型调用失败（{e}），以下由离线规则引擎回答：\n\n" + r.text
                return r
        return self._offline_ask(question)

    # ---------------- LLM 路径

    def _llm_ask(self, question, conf):
        messages = [{"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": question}]
        steps = []
        for _ in range(4):
            resp = llm_chat(conf, messages, self.tools)
            msg = (resp.get("choices") or [{}])[0].get("message") or {}
            calls = msg.get("tool_calls") or []
            if not calls:
                return Reply(msg.get("content") or "（模型未返回内容）", steps,
                             f"大模型 · {conf.get('model')}")
            messages.append(msg)
            for c in calls:
                fn = c.get("function", {})
                name = fn.get("name")
                try:
                    args = json.loads(fn.get("arguments") or "{}")
                except Exception:
                    args = {}
                tool = self.by_name.get(name)
                result = tool["fn"](**args) if tool else {"error": "unknown tool"}
                steps.append({"tool": name, "args": args, "result": result})
                messages.append({"role": "tool", "tool_call_id": c.get("id"),
                                 "content": json.dumps(result, ensure_ascii=False)[:4000]})
        return Reply("（工具调用轮数超限，请把问题拆细一些）", steps, f"大模型 · {conf.get('model')}")

    # ---------------- 离线规则路径

    def _offline_ask(self, question):
        q = question or ""
        steps = []
        # 0) 行动型：完整决策处方（diagnosis→action→verify）
        if any(k in q for k in ["决策方案", "行动方案", "干预处方", "怎么办", "该怎么做",
                                "帮我决定", "给个方案", "精准干预"]):
            crop = None
            for k in CROP_REF:
                if k in q:
                    crop = k
                    break
            area = _num_after(q, ["亩", "亩地"]) or 10
            price = _num_after(q, ["元/公斤", "元一斤", "元/斤"])
            res = self.by_name["action_plan"]["fn"](
                crop=crop, area=area, price=price, problem=q)
            d = res["diagnosis"]
            text = (
                f"【行动型决策处方 · {res['crop']}】\n\n"
                f"**① 诊断**：{res['problem_type']}；风险 {d['risk']}，利润率 {d['margin_pct']:.1f}%，"
                f"保本价 {d['breakeven_price']:.2f} 元/公斤。\n\n"
                f"**② 触发条件**：{res['trigger']}\n\n"
                f"**③ 算法决策**：{res['decision']}\n\n"
                f"**④ 落地措施**：\n" +
                "\n".join(f"- {m}" for m in res["measures"]) +
                f"\n\n**⑤ 预期效果**：{res['expected']}\n\n"
                f"**⑥ 复核指标**：{res['verify']}\n\n"
                f"> {res['authority']}\n\n"
                f"> 数值为内置参考值，请用当地收购价与自家成本台账替换后复算。")
            steps.append({"tool": "action_plan",
                          "args": {"crop": crop or "水稻", "area": area,
                                   "problem": q[:40]}, "result": res})
            return Reply(text, steps)

        # 1) 种植成本 / 保本 / 防亏损
        if any(k in q for k in ["保本", "成本", "亏", "种什么", "赚", "利润", "亩"]):
            crop = None
            for k in CROP_REF:
                if k in q:
                    crop = k
                    break
            area = _num_after(q, ["亩", "亩地"]) or 10
            price = _num_after(q, ["元/公斤", "元一斤", "元/斤"])
            res = self.by_name["cost_plan"]["fn"](crop=crop, area=area, price=price)
            steps.append({"tool": "cost_plan", "args": {"crop": crop or "水稻", "area": area}, "result": res})
            text = (f"【结论】{res['crop']} 按 {res['area_mu']:.0f} 亩测算，风险等级为 **{res['risk']}**，"
                    f"亩利润 {res['profit_per_mu']:.0f} 元，总利润约 {res['total_profit']:,.0f} 元。\n\n"
                    f"| 指标 | 数值 |\n| --- | --- |\n"
                    f"| 单产 | {res['yield_per_mu']:.0f} 公斤/亩 |\n"
                    f"| 售价 | {res['price']:.2f} 元/公斤 |\n"
                    f"| 亩收入 | {res['revenue_per_mu']:,.0f} 元 |\n"
                    f"| 亩成本 | {res['cost_per_mu']:,.0f} 元 |\n"
                    f"| 保本价 | {res['breakeven_price']:.2f} 元/公斤 |\n"
                    f"| 保本单产 | {res['breakeven_yield']:.0f} 公斤/亩 |\n"
                    f"| 利润率 | {res['margin_pct']:.1f}% |\n\n"
                    f"**建议**：{res['advice']}\n\n"
                    f"> 单产/价格/成本为内置参考值，实际请以当地收购价与自家成本替换。")
            return Reply(text, steps)

        # 1.5) 广东改革开放官方长面板（1978—2026）
        reform_hint = ("广东" in q or "岭南" in q) and any(
            k in q for k in ["改革开放", "四十八年", "48年", "历年", "官方", "统计局", "年鉴",
                             "1978", "1980", "1990", "2026", "农民收入", "恩格尔",
                             "住房", "总产值", "粮食产量", "可支配收入"])
        if reform_hint:
            res = self.by_name["gd_reform_query"]["fn"](metric=q, year=q)
            steps.append({"tool": "gd_reform_query",
                          "args": {"metric": res["metric"]}, "result": {k: v for k, v in res.items() if k != "series"}})
            first, last = res.get("first"), res.get("latest")
            if not first or not last:
                return Reply("未取到该指标的官方序列，可试：农民收入、总产值、粮食产量、恩格尔、住房、GDP。", steps)
            label = res.get("label") or res["metric"]
            if res.get("picked") and res["picked"][1] is not None:
                head = f"【结论】{res['picked'][0]} 年广东 **{label}** 为 **{res['picked'][1]:,.2f}**（官方数据）。\n\n"
            else:
                head = (f"【结论】广东 **{label}** 最新为 **{last[1]:,.2f}**（{last[0]} 年，官方数据）；"
                        f"起点 {first[0]} 年为 {first[1]:,.2f}。\n\n")
            if first[1]:
                ratio = (f"，从 {first[0]} 年增长 **{last[1] / first[1]:,.1f} 倍**"
                         if last[1] >= first[1]
                         else f"，较 {first[0]} 年下降 **{(1 - last[1] / first[1]) * 100:,.1f}%**")
            else:
                ratio = ""
            proj = res.get("projection")
            proj_txt = (f"\n2026 年模型预测：{proj['forecast_2026']:,.2f} {proj['unit']}"
                        f"（2015—2025 复合增速 {proj['rate_2015_2025']:.2f}%，非官方统计）。"
                        if proj else "")
            body = (f"{head}跨度 {first[0]}—{last[0]} 年{ratio}，共 {res['points']} 个年度观测。{proj_txt}\n\n"
                    f"**建议**：官方序列适合看长周期结构变化；短周期决策请叠加市域面板与当年公报。\n\n"
                    f"> 来源：{res['source']}。")
            chart = {"title": f"广东 · {label}（{first[0]}—{last[0]}，官方）",
                     "kind": "line", "data": [[y, round(v, 2)] for y, v in res["series"]]}
            return Reply(body, steps, chart=chart)

        # 2) 广东城市
        city = self.hub.norm_city(q)
        if city or ("广东" in q and any(k in q for k in ["市", "城市", "珠三角", "粤东", "粤西", "粤北"])):
            res = self.by_name["query_cities"]["fn"](city=city, metric=q)
            steps.append({"tool": "query_cities", "args": {"city": city}, "result": res})
            if city and "error" in res:
                return Reply(f"{res['error']}。可查城市：{'、'.join(res.get('available', [])[:8])} 等。", steps)
            if city:
                first = res["first"]
                last = res["latest"]
                gr = ""
                if first and last and first[1]:
                    gr = f"，{last[0] - first[0]} 年间从 {first[1]:,.2f} 变为 {last[1]:,.2f}"
                key = self.hub.detect_city_metric(q)
                factor = CITY_METRICS.get(key, ("", 1))[1]
                chart = {"title": f"{city} · {res['metric']}（1999–2018）", "kind": "line",
                         "data": [[y, round(v * factor, 2)] for y, v in self.hub.city_series(city, key)]}
                text = (f"【结论】{city}（{res['region']}）最新 {res['metric']} 为 **{last[1]:,.2f}**"
                        f"（{last[0]} 年）{gr}。\n\n"
                        f"**建议**：市域数据只到 2018 年，做当前决策时请结合省级 2024 公报一起看。\n\n"
                        f"> 数据来源：《中国城市统计年鉴》开源面板（1999–2018），共 {res['points']} 个年度观测。")
                return Reply(text, steps, chart=chart)
            rows = res.get("ranking", [])
            body = "\n".join(f"| {i+1} | {c} | {v:,.2f} | {r} |" for i, (c, v, r) in enumerate(rows[:8]))
            text = (f"【结论】广东 21 市中 {res['metric']} 最高的是 **{rows[0][0]}**（{rows[0][1]:,.2f}），"
                    f"最低的是 **{rows[-1][0]}**（{rows[-1][1]:,.2f}）。\n\n"
                    f"| # | 城市 | {res['metric']} | 板块 |\n| --- | --- | --- | --- |\n{body}\n\n"
                    f"**建议**：一产占比高的城市（粤西粤北）适合布局规模化种植与初加工；"
                    f"珠三角城市应走都市农业、预制菜与冷链枢纽路线。\n\n"
                    f"> 数据来源：《中国城市统计年鉴》开源面板，{res['year']} 年。")
            return Reply(text, steps)

        # 3) 排名
        if any(k in q for k in ["排名", "最高", "最低", "前几", "top", "排行", "哪省"]):
            col = self.hub.detect_metric(q)
            res = self.by_name["rank_provinces"]["fn"](metric=q, top=8)
            steps.append({"tool": "rank_provinces", "args": {"metric": col}, "result": res})
            body = "\n".join(f"| {i+1} | {p} | {v:,.2f} |" for i, (p, v) in enumerate(res["ranking"]))
            return Reply(f"【结论】{res['year']} 年 **{res['metric']}** 排名如下：\n\n"
                         f"| # | 省份 | 数值 |\n| --- | --- | --- |\n{body}\n\n"
                         f"**建议**：比较省份时注意口径差异——高收入省份往往一产占比低，"
                         f"结构差异比绝对数值更值得关注。", steps)

        # 4) 趋势 / 预测
        if any(k in q for k in ["趋势", "预测", "未来", "变化", "走势", "会怎样", "十年"]):
            prov = self.hub.norm_province(q)
            col = self.hub.detect_metric(q)
            res = self.by_name["trend_forecast"]["fn"](scope=prov or "全国", metric=q, forecast=3)
            steps.append({"tool": "trend_forecast", "args": {"scope": prov, "metric": col}, "result": res})
            if "error" in res:
                return Reply("没匹配到指标，可以试试：一产占比、GDP、农村居民收入、人口、城乡收入倍差。", steps)
            fc = "\n".join(f"| {y} | {v:,.2f} | {r:.3f} |" for y, v, r in res["forecast"])
            s = self.hub.series(prov, col) if prov else self.hub.macro_series(col)
            chart = {"title": f"{res['scope']} · {res['metric']}", "kind": "line",
                     "data": [[y, round(v, 2)] for y, v in s[-20:]]}
            return Reply(f"【结论】{res['scope']} 的 **{res['metric']}** 最新为 {res['latest'][1]:,.2f}"
                         f"（{res['latest'][0]} 年），线性外推 3 年：\n\n"
                         f"| 年份 | 预测值 | R² |\n| --- | --- | --- |\n{fc}\n\n"
                         f"**建议**：外推只反映历史惯性，不含政策与气候冲击；跨周期决策请叠加情景假设。",
                         steps, chart=chart)

        # 5) 具体省份（广东全景/方案类问题不走单省分支）
        prov = self.hub.norm_province(q)
        panorama = ("广东" in q and any(k in q for k in
                    ["全景", "整体", "21市", "二十一市", "方案", "全省", "布局", "依赖农业"]))
        if prov and not panorama:
            col = self.hub.detect_metric(q) or "第一产业占GDP比重(%)"
            res = self.by_name["query_province"]["fn"](province=prov, metric=col)
            steps.append({"tool": "query_province", "args": {"province": prov, "metric": col}, "result": res})
            s = self.hub.series(prov, col)
            chart = {"title": f"{prov} · {col}", "kind": "line", "data": [[y, round(v, 2)] for y, v in s[-25:]]}
            chg = res.get("change")
            chg_txt = f"，较 {res['first_year']} 年变化 {chg:+,.2f}" if chg is not None else ""
            return Reply(f"【结论】{prov} 的 **{col}** 最新为 **{res['value']:,.2f}**（{res['year']} 年）{chg_txt}。\n\n"
                         f"**建议**：与全国均值、同大区省份对照看更有意义——单独一个数字看不出结构性位置。",
                         steps, chart=chart)

        # 6) 广东全景
        if "广东" in q:
            res = self.by_name["gd_overview"]["fn"]()
            steps.append({"tool": "gd_overview", "args": {}, "result": res})
            p = res["province_2024"]
            body = "\n".join(f"| {c} | {g:,.1f} | {r} |" for c, g, r in res["top_cities"][:6])
            return Reply(f"【结论】广东 2024 年粮食总产 {p.get('grain_万吨','1313.43')} 万吨，"
                         f"茶叶 {p.get('tea_万吨','19.17')} 万吨，一产增加值 {p.get('agri_gdp_亿元','—')} 亿元；"
                         f"21 市中 GDP 前六：\n\n| 城市 | GDP(亿元) | 板块 |\n| --- | --- | --- |\n{body}\n\n"
                         f"**建议**：广东农业走「珠三角都市农业 + 粤西粤北规模化」双轨，"
                         f"决策时要按板块而非全省平均看。\n\n> {res['note']}", steps)

        # 7) 检索兜底
        kw = re.sub(r"[？?。，,\s]|帮我|请|查|一下|看看|关于|多少|数据|情况|的", "", q)[:6]
        if len(kw) < 2:
            kw = "农业"
        res = self.by_name["search_book"]["fn"](keyword=kw)
        steps.append({"tool": "search_book", "args": {"keyword": kw}, "result": res})
        if res.get("count"):
            hits = "\n".join(f"- 《{h['book']}》 {h['chapter']}" for h in res["hits"][:4])
            return Reply(f"【结论】全书里有 {res['count']} 处提到「{kw}」，最相关章节：\n\n{hits}\n\n"
                         f"**建议**：点左侧目录直接跳过去；也可以问得更具体，例如「广东一产占比多少」「水稻10亩保本价」。", steps)
        return Reply("我可以回答这几类问题：\n\n"
                     "1. **查省市数据** —— 「广东一产占比多少」「深圳2018年GDP」\n"
                     "2. **排名对比** —— 「2024年一产占比最高的5个省」\n"
                     "3. **趋势预测** —— 「农村居民收入未来3年趋势」\n"
                     "4. **种植决策** —— 「水稻20亩，售价2.5元保本吗」\n"
                     "5. **广东全景** —— 「广东21市哪个最依赖农业」\n\n"
                     "配好大模型 API 后可以自由追问，回答会更灵活。", steps)


def _num_after(text, units):
    for u in units:
        m = re.search(r"(\d+(?:\.\d+)?)\s*" + re.escape(u), text)
        if m:
            v = float(m.group(1))
            return v / 2 if "斤" in u and "公斤" not in u else v
    # 口语表达："售价2.5"、"价格2块8"、"亩成本1200"
    for lead in ["售价", "价格", "单价", "成本", "亩成本"]:
        m = re.search(lead + r"[^\d]{0,4}(\d+(?:\.\d+)?)", text)
        if m:
            return float(m.group(1))
    return None
