# -*- coding: utf-8 -*-
"""排版与标注规范：书卷分类、字体令牌、关键词词典、富文本高亮。

楷体（KaiTi/STKaiti）用于中文正文与引文；Times New Roman 用于数字、
拉丁字母与统计符号。关键词按三类着色：制度/政策（红）、指标/数据（蓝）、
决断/警示（金）。QT 与网页共用同一份词典，保证标注一致。
"""
import html
import re

# --------------------------------------------------------------------------
# 一、书卷分类：7 卷归入 4 部（对应参考框架的 part0 → part1..part4）
# --------------------------------------------------------------------------
PARTS = [
    {
        "id": "part1", "no": "Ⅰ", "title": "国土与数据",
        "lead": "从 31 省面板到岭南 21 市，先看清脚下的土地。",
        "desc": "一部关于尺度的书：45 年、31 省、21 市。数据是它的经纬，地图是它的骨架。",
        "volumes": ["vol1", "vol5"], "theme": "#1f9d55",
        "tags": ["31省面板", "1980—2024", "岭南21市", "市域版图"],
    },
    {
        "id": "part2", "no": "Ⅱ", "title": "作物与田畴",
        "lead": "一粒种子里，藏着播种面积、产量与市场的全部秘密。",
        "desc": "茶叶、粮食、果蔬——每一种作物都是一段自然与人的博弈史，用数据读懂它的脾气。",
        "volumes": ["vol2", "vol3"], "theme": "#b07d2b",
        "tags": ["播种面积", "茶香数据志", "产量", "市场"],
    },
    {
        "id": "part3", "no": "Ⅲ", "title": "预测与决策",
        "lead": "让数据替农民先算一遍账，少亏一次就是多赚一季。",
        "desc": "预测不是算命，是把不确定性压缩成可执行的三个动作：做什么、不做什么、何时收手。卷八用 5 章 100 页写清算法链路与精准干预措施。",
        "volumes": ["vol4", "vol8"], "theme": "#3d7ab5",
        "tags": ["防亏损", "保本测算", "价格预测", "决策 Agent", "算法精准干预", "保本价", "止损线"],
    },
    {
        "id": "part4", "no": "Ⅳ", "title": "四十八年长卷",
        "lead": "1978—2026，一条田埂上的中国：从生存到未来。",
        "desc": "全书压卷之作。10 章 × 20 页，用官方长面板讲述一场仍未结束的农村实验。",
        "volumes": ["vol6", "vol7"], "theme": "#a3412f",
        "tags": ["1978—2026", "10章200页", "改革开放", "决策系统"],
    },
]

VOLUME_PART = {vid: p["id"] for p in PARTS for vid in p["volumes"]}

# --------------------------------------------------------------------------
# 二、字体令牌（中文楷体 / 西文/数字 Times New Roman）
# --------------------------------------------------------------------------
FONT = {
    "cn": '"KaiTi","STKaiti","楷体","Kaiti SC","DFKai-SB"',
    "en": '"Times New Roman","Times","Georgia"',
    "cn_ui": '"KaiTi","STKaiti","楷体","Microsoft YaHei"',
    "pair": '"Times New Roman","KaiTi","STKaiti","楷体","Microsoft YaHei"',
}

# --------------------------------------------------------------------------
# 三、关键词词典（三类）
# --------------------------------------------------------------------------
KW = {
    "policy": [  # 制度 / 政策 —— 红
        "家庭联产承包责任制", "改革开放", "乡村振兴", "农业现代化", "供给侧结构性改革",
        "脱贫攻坚", "全面小康", "农村承包地", "三权分置", "土地流转", "惠农政策",
        "农业税", "取消农业税", "最低收购价", "一号文件", "入世", "WTO", "城镇化",
        "新农村建设", "城乡融合", "共同富裕", "双重经营", "统分结合", "集体经济",
        "生产责任制", "包产到户", "大包干", "人民公社", "合作社", "社会化服务",
        "农田水利", "高标准农田", "耕地红线", "粮食安全", "藏粮于地", "藏粮于技",
        "数字化改革", "数字乡村", "双循环", "新发展格局", "绿色低碳", "生态文明",
        "精准干预", "决策闭环", "人在环里", "订单农业", "风险转移", "农业保险",
    ],
    "metric": [  # 指标 / 数据 —— 蓝
        "第一产业增加值", "农林牧渔业总产值", "农村居民人均可支配收入", "农民人均纯收入",
        "恩格尔系数", "粮食产量", "播种面积", "有效灌溉面积", "农业机械化",
        "GDP", "复合增长率", "同比", "环比", "占比", "人均", "产值", "产量", "收入",
        "mAP50", "召回率", "精确率", "置信区间", "外推", "预测值", "面板数据",
        "中位数", "分位数", "回归", "相关系数", "样本", "观测值", "口径",
        "保本价", "保本单产", "利润率", "亩利润", "期望收益", "CAGR", "复合增长率",
        "状态向量", "触发条件", "复核指标", "最小二乘", "R²", "置信区间",
    ],
    "decision": [  # 决断 / 警示 —— 金
        "防亏损", "保本", "止损", "风险", "预警", "底线", "红线", "临界", "阈值",
        "不要", "切忌", "警示", "非官方统计", "模型外推", "幻觉", "不可外推",
        "结论", "建议", "决断", "关键", "铁律", "边界", "代价", "警惕",
    ],
}

# 数字 + 单位（Times New Roman 高亮）
NUM_RE = re.compile(
    r"(?<![\u4e00-\u9fff])(\d[\d,，]*\.?\d*)\s*(亿元|万吨|万亩|万头|万人|元/亩|元|%|倍|公斤|斤|年|户|亩|公顷|个点|个百分点)"
)

# 年份（1978—2026）
YEAR_RE = re.compile(r"(19[7-9]\d|20[0-2]\d)\s*年?")

_COLOR = {"policy": "#a3412f", "metric": "#2f6094", "decision": "#9a6b12"}
_COLOR_NIGHT = {"policy": "#f0a08c", "metric": "#8fc4ef", "decision": "#f0cf80"}

# 长词优先，避免「农业现代化」被「农业」先切
_ALL_KW = sorted(
    [(w, k) for k, words in KW.items() for w in words],
    key=lambda x: -len(x[0]),
)


def _mark_text(text, night=False):
    """把纯文本转成带关键词标注的 HTML（不包外层标签）。"""
    colors = _COLOR_NIGHT if night else _COLOR
    s = html.escape(text)
    # 占位符方式，避免高亮嵌套互相破坏
    slots = []

    def _hold(inner_html):
        slots.append(inner_html)
        return "\x00%d\x00" % (len(slots) - 1)

    # 1) 关键词
    for word, kind in _ALL_KW:
        if not word:
            continue
        # 用负向断言避免重复标注已占位区域
        s = re.sub(
            re.escape(word),
            lambda m, k=kind, w=word: _hold(
                '<span style="color:%s;font-weight:700;">%s</span>' % (colors[k], w)
            ),
            s,
        )
    # 2) 数字+单位
    s = NUM_RE.sub(
        lambda m: _hold(
            '<span style="font-family:\'Times New Roman\',serif;font-weight:700;'
            'color:%s;">%s</span>' % (colors["metric"], m.group(0))
        ),
        s,
    )
    # 3) 年份
    s = YEAR_RE.sub(
        lambda m: _hold(
            '<span style="font-family:\'Times New Roman\',serif;font-weight:700;">%s</span>'
            % m.group(0)
        ),
        s,
    )
    # 回填
    for i, frag in enumerate(slots):
        s = s.replace("\x00%d\x00" % i, frag)
    return s


def mark_paragraph(text, night=False, cls="para"):
    """返回可直接 setText(RichText) 的整段 HTML，字体为楷体+TNR。"""
    body = _mark_text(text, night)
    return (
        '<div style="font-family:\'Times New Roman\',\'KaiTi\',\'楷体\',serif;">'
        + body + "</div>"
    )


def keyword_stats(text):
    """统计一段文字命中的关键词，供 UI 显示「本页关键词」。"""
    hits = []
    for word, kind in _ALL_KW:
        if word and word in text:
            hits.append((word, kind))
    return hits


JSON_EXPORT = {
    "parts": PARTS,
    "font": FONT,
    "keywords": KW,
    "numPattern": NUM_RE.pattern,
    "yearPattern": YEAR_RE.pattern,
    "colors": _COLOR,
    "colorsNight": _COLOR_NIGHT,
}
