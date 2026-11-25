# -*- coding: utf-8 -*-
"""生成卷八专用的"干净数据图"：决策闭环 / 保本分析 / 风险分级 / 增速对比 / 算法管线 / 对标。

设计原则：浅底、楷体中文 + Times New Roman 数字、少装饰、信息优先。
替代原来带「AI生成」水印且构图杂乱的 AI 拼贴图。
"""
from pathlib import Path
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch, Rectangle
import matplotlib.font_manager as fm

ROOT = Path(__file__).resolve().parent
OUT = [ROOT / "app" / "assets" / "diagrams", ROOT / "app" / "site" / "assets" / "diagrams"]
for d in OUT:
    d.mkdir(parents=True, exist_ok=True)

CN = fm.FontProperties(fname="C:/Windows/Fonts/STKAITI.TTF")
CNB = fm.FontProperties(fname="C:/Windows/Fonts/simhei.ttf")
EN = "Times New Roman"
INK = "#1d2a22"
GREEN = "#1b6b46"
RED = "#a3412f"
BLUE = "#2f6094"
GOLD = "#9a6b12"
PAPER = "#fbf8ef"
GRID = "#ddd4bd"


def save(fig, name):
    for d in OUT:
        fig.savefig(d / name, dpi=150, bbox_inches="tight", facecolor=PAPER,
                    pad_inches=0.22)
    plt.close(fig)
    print("generated", name)


def base(w, h):
    fig = plt.figure(figsize=(w, h), facecolor=PAPER)
    ax = fig.add_axes([0, 0, 1, 1])
    ax.set_xlim(0, 100)
    ax.set_ylim(0, 100)
    ax.axis("off")
    return fig, ax


def box(ax, x, y, w, h, face, edge, text, sub="", fs=13, tc=INK, lw=1.6):
    p = FancyBboxPatch((x, y), w, h,
                       boxstyle="round,pad=0.6,rounding_size=2.0",
                       linewidth=lw, edgecolor=edge, facecolor=face, zorder=2)
    ax.add_patch(p)
    ax.text(x + w / 2, y + h * (0.62 if sub else 0.5), text, ha="center", va="center",
            fontproperties=CNB, fontsize=fs, color=tc, zorder=3)
    if sub:
        ax.text(x + w / 2, y + h * 0.27, sub, ha="center", va="center",
                fontproperties=CN, fontsize=fs - 4, color="#6d6350", zorder=3)


# ---------------------------------------------------------------- 决策闭环
def decision_loop():
    fig, ax = base(12.8, 3.6)
    ax.text(50, 92, "决策闭环 · 从数据到措施的五个环节", ha="center", va="center",
            fontproperties=CNB, fontsize=18, color=GREEN)
    ax.text(50, 82, "每一环都可追问、可复算、可拒绝", ha="center", va="center",
            fontproperties=CN, fontsize=11, color="#8a7a5e")
    stages = [
        ("① 感知", "官方序列 · 台账\n尺度对齐 · 留空", "#eef6f1", GREEN),
        ("② 预测", "线性/指数/CAGR\n带区间与标签", "#eaf1f8", BLUE),
        ("③ 决策", "保本价 · 风险分级\n期望收益 · 止损", "#fbf3e2", GOLD),
        ("④ 干预", "品种/面积/时机\n成本/渠道/保险", "#fbeeea", RED),
        ("⑤ 复核", "实测四指标\n偏差归因修订", "#f0eef7", "#6b5590"),
    ]
    xs = [3, 22.5, 42, 61.5, 81]
    w = 16
    for (t, s, face, edge), x in zip(stages, xs):
        box(ax, x, 30, w, 34, face, edge, t, s, fs=14, tc=edge)
    for x in [19.2, 38.7, 58.2, 77.7]:
        ax.add_patch(FancyArrowPatch((x, 47), (x + 2.6, 47),
                     arrowstyle="-|>", mutation_scale=16, linewidth=1.8,
                     color="#8a7a5e", zorder=4))
    # feedback arrow
    ax.add_patch(FancyArrowPatch((89, 30), (11, 30), connectionstyle="arc3,rad=-0.32",
                 arrowstyle="-|>", mutation_scale=15, linewidth=1.5,
                 linestyle="--", color=GREEN, zorder=1))
    ax.text(50, 12, "实测值回流 · 半闭环（人工录入）", ha="center", va="center",
            fontproperties=CN, fontsize=10.5, color=GREEN)
    save(fig, "decision_loop.png")


# ---------------------------------------------------------------- 保本分析
def breakeven():
    fig = plt.figure(figsize=(8.6, 5.4), facecolor=PAPER)
    ax = fig.add_subplot(111, facecolor="#fffdf7")
    y = 480.0
    c = 1150.0
    p_be = c / y
    prices = [1.6, 1.8, 2.0, 2.2, 2.4, 2.6, 2.8, 3.0, 3.2]
    revenue = [p * y for p in prices]
    ax.plot(prices, revenue, color=BLUE, lw=2.4, label="销售收入 = 售价 × 单产", zorder=3)
    ax.axhline(c, color=RED, lw=2.0, linestyle="--", label="总成本 = 1150 元/亩", zorder=2)
    ax.axvline(p_be, color=GOLD, lw=1.8, linestyle=":", zorder=2)
    ax.scatter([p_be], [c], s=70, color=GOLD, zorder=5)
    ax.annotate(f"保本价 {p_be:.2f} 元/公斤", xy=(p_be, c), xytext=(2.42, 900),
                fontproperties=CN, fontsize=12, color=GOLD,
                arrowprops=dict(arrowstyle="->", color=GOLD, lw=1.3))
    ax.fill_between([p_be, 3.2], [c, c], [3.2 * y, 3.2 * y], color="#dff0e2", alpha=.55, zorder=1)
    ax.fill_between([1.6, p_be], [1.6 * y, c], [c, c], color="#f7ded9", alpha=.55, zorder=1)
    ax.text(2.85, c + 90, "盈利区", fontproperties=CN, fontsize=12, color=GREEN, ha="center")
    ax.text(1.95, c - 130, "亏损区", fontproperties=CN, fontsize=12, color=RED, ha="center")
    ax.set_xlabel("售价（元/公斤）", fontproperties=CN, fontsize=12, color=INK)
    ax.set_ylabel("金额（元/亩）", fontproperties=CN, fontsize=12, color=INK)
    ax.set_title("保本价：收入线与成本线的交点（水稻演示值）", fontproperties=CNB,
                 fontsize=15, color=GREEN, pad=12)
    for lab in ax.get_xticklabels() + ax.get_yticklabels():
        lab.set_fontfamily(EN); lab.set_fontsize(10); lab.set_color("#5b5a4c")
    ax.grid(color=GRID, lw=.7, alpha=.7)
    for sp in ["top", "right"]:
        ax.spines[sp].set_visible(False)
    leg = ax.legend(prop=CN, fontsize=10, loc="upper left", frameon=False)
    save(fig, "breakeven.png")


# ---------------------------------------------------------------- 风险四级
def risk_levels():
    fig, ax = base(10.6, 5.0)
    ax.text(50, 92, "四级风险分级 → 对应动作", ha="center", va="center",
            fontproperties=CNB, fontsize=18, color=GREEN)
    ax.text(50, 83, "利润率 = 亩利润 ÷ 亩收入 × 100%", ha="center", va="center",
            fontproperties=CN, fontsize=11, color="#8a7a5e")
    rows = [
        ("≥ 25%", "低风险", "小步扩种 · 锁部分订单", "#eef6f1", GREEN),
        ("8 — 25%", "中风险", "优先降本 · 统一采购/机械化", "#f0f5fa", BLUE),
        ("0 — 8%", "偏高风险", "缩面积 · 投保 · 找订单", "#fbf3e2", GOLD),
        ("< 0", "高风险", "不建议种植 · 改种/改期/改渠道", "#fbeeea", RED),
    ]
    y = 70
    for rng, lvl, act, face, edge in rows:
        box(ax, 4, y - 6, 17, 12, face, edge, rng, "", fs=13, tc=edge)
        box(ax, 23, y - 6, 18, 12, face, edge, lvl, "", fs=14, tc=edge)
        box(ax, 43, y - 6, 53, 12, face, edge, act, "", fs=12, tc=INK, lw=1.0)
        y -= 19
    ax.text(50, 6, "风险等级不是标签，是明天就能执行的动作。", ha="center", va="center",
            fontproperties=CN, fontsize=10.5, color="#6d6350")
    save(fig, "risk_levels.png")


# ---------------------------------------------------------------- 增速对比
def cagr_compare():
    fig = plt.figure(figsize=(8.8, 4.6), facecolor=PAPER)
    ax = fig.add_subplot(111, facecolor="#fffdf7")
    labels = ["农村居民收入", "农林牧渔总产值", "粮食产量"]
    vals = [7.745, 6.331, 0.851]
    colors = [GREEN, BLUE, RED]
    bars = ax.barh(labels, vals, color=colors, height=0.55, zorder=3)
    for b, v in zip(bars, vals):
        ax.text(v + 0.12, b.get_y() + b.get_height() / 2, f"{v:.3f}%",
                va="center", fontfamily=EN, fontweight="bold", fontsize=12, color=INK)
    ax.set_title("广东三项指标复合增长率（2015—2025）", fontproperties=CNB,
                 fontsize=15, color=GREEN, pad=12)
    ax.set_xlabel("CAGR（%）", fontproperties=CN, fontsize=11, color=INK)
    for lab in ax.get_yticklabels():
        lab.set_fontproperties(CN); lab.set_fontsize(12); lab.set_color(INK)
    for lab in ax.get_xticklabels():
        lab.set_fontfamily(EN); lab.set_fontsize(10); lab.set_color("#5b5a4c")
    ax.set_xlim(0, 9)
    ax.grid(axis="x", color=GRID, lw=.7, alpha=.7, zorder=0)
    for sp in ["top", "right"]:
        ax.spines[sp].set_visible(False)
    fig.text(0.5, 0.045, "粮食几乎零增长 → 增产不能靠扩面，只能靠单产与结构",
             ha="center", fontproperties=CN, fontsize=10.5, color="#6d6350")
    save(fig, "cagr_compare.png")


# ---------------------------------------------------------------- 算法管线
def algo_pipeline():
    fig, ax = base(12.4, 4.4)
    ax.text(50, 93, "保本与风险算法：四个输入 → 六个步骤 → 一张处方", ha="center", va="center",
            fontproperties=CNB, fontsize=17, color=GREEN)
    box(ax, 2, 55, 15, 24, "#eef6f1", GREEN, "输入", "作物/面积/单产\n售价/亩成本", fs=13, tc=GREEN)
    box(ax, 2, 22, 15, 24, "#fbf3e2", GOLD, "约束", "资金/面积\n合同/风险承受", fs=13, tc=GOLD)
    steps = ["① 收入 p·y·a", "② 保本价 c/y", "③ 利润 p·y−c", "④ 利润率 margin", "⑤ 四级风险分级", "⑥ 映射措施"]
    for i, s in enumerate(steps):
        x = 21 + (i % 3) * 25.5
        y = 52 if i < 3 else 26
        box(ax, x, y, 22.5, 16, "#f8fcf9", "#1b8a58", s, "", fs=11.5, tc="#1c4b36", lw=1.2)
    box(ax, 80, 38, 18, 24, "#fbeeea", RED, "输出", "保本价/利润\n风险/措施", fs=13, tc=RED)
    for (x1, y1, x2, y2) in [(17, 67, 21, 60), (17, 34, 21, 34), (66.5, 60, 80, 52), (66.5, 34, 80, 50)]:
        ax.add_patch(FancyArrowPatch((x1, y1), (x2, y2), arrowstyle="-|>",
                     mutation_scale=14, lw=1.5, color="#8a7a5e", zorder=4))
    ax.text(50, 8, "每一步都能用计算器复核 —— 可追溯是决策系统的生命线", ha="center", va="center",
            fontproperties=CN, fontsize=10.5, color="#6d6350")
    save(fig, "algo_pipeline.png")


# ---------------------------------------------------------------- 对标雷达
def benchmark():
    import numpy as np
    cats = ["数据可核验", "预测可解释", "干预可执行", "闭环自动", "设备控制"]
    ours = [5, 5, 4, 2, 1]
    ind = [4, 3, 5, 5, 5]
    ang = np.linspace(0, 2 * np.pi, len(cats), endpoint=False).tolist()
    ang += ang[:1]
    ours_ = ours + ours[:1]
    ind_ = ind + ind[:1]
    fig = plt.figure(figsize=(6.6, 6.2), facecolor=PAPER)
    ax = fig.add_subplot(111, polar=True, facecolor="#fffdf7")
    ax.plot(ang, ours_, color=GREEN, lw=2.2, label="智农宝 v8")
    ax.fill(ang, ours_, color=GREEN, alpha=.16)
    ax.plot(ang, ind_, color=BLUE, lw=2.0, ls="--", label="行业标杆（阿里/丰登/GEAIR）")
    ax.fill(ang, ind_, color=BLUE, alpha=.08)
    ax.set_xticks(ang[:-1])
    ax.set_xticklabels(cats, fontproperties=CN, fontsize=12, color=INK)
    ax.set_yticks([1, 2, 3, 4, 5])
    ax.set_yticklabels([])
    ax.set_ylim(0, 5.5)
    ax.grid(color=GRID, lw=.8)
    ax.set_title("能力边界对标：承认差距，明确定位", fontproperties=CNB,
                 fontsize=15, color=GREEN, pad=18)
    ax.legend(prop=CN, fontsize=10, loc="upper right", frameon=False)
    fig.text(0.5, 0.035, "本系统强在可核验与可解释，弱在闭环自动化与设备控制",
             ha="center", fontproperties=CN, fontsize=10, color="#6d6350")
    save(fig, "benchmark.png")


if __name__ == "__main__":
    decision_loop()
    breakeven()
    risk_levels()
    cagr_compare()
    algo_pipeline()
    benchmark()
    print("all diagrams generated")
