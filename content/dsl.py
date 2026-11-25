# -*- coding: utf-8 -*-
"""卷七页面 DSL：让每章 20 页的写作保持紧凑、可校验。

内容文件只描述"这一页要说什么"，真实数值由 build_reform_v6.py
从 guangdong_reform.json / guangdong.json 注入，避免手抄错数。
"""


def P(title, *paras):
    return {"type": "text", "title": title, "paras": list(paras)}


def KPI(*items):
    """items: (数值, 说明) 元组，最多 4 个一行"""
    return {"type": "kpi", "items": [list(i) for i in items]}


def FIG(series, title, lo=None, hi=None, kind="line", note=""):
    """引用官方序列，由构建脚本填 data"""
    return {"type": "figure", "series": series, "title": title,
            "lo": lo, "hi": hi, "kind": kind, "note": note}


def TBL(key, title=""):
    """引用构建脚本里预置的真实数据表"""
    return {"type": "datatable", "key": key, "title": title}


def IMG(path, cap):
    return {"type": "image", "path": path, "caption": cap}


def THEME(tag, quote, question):
    return {"type": "theme", "tag": tag, "quote": quote, "question": question}


def DOC(head, *paras):
    """档案摘录：政策文件 / 报表原文的版式"""
    return {"type": "doc", "head": head, "paras": list(paras)}


def VOICE(who, quote, note=""):
    return {"type": "voice", "who": who, "quote": quote, "note": note}


def DECIDE(*items):
    """items: (✅/🟡/❌, 标题, 说明)"""
    return {"type": "decision", "items": [list(i) for i in items]}


def NOTE(*paras, title="数据注记"):
    return {"type": "note", "title": title, "paras": list(paras)}


def ALGO(title, inputs, steps, output, note=""):
    """算法管线：输入 → 处理步骤 → 输出。steps: (标题, 说明) 元组。
    用于把"算法做了什么"写成可核对的链路，而不是口号。"""
    return {"type": "algo", "title": title,
            "inputs": list(inputs), "steps": [list(s) for s in steps],
            "output": output, "note": note}


def ACTION(trigger, decision, measures, expected, verify):
    """精准干预处方：触发条件 → 算法决策 → 落地措施 → 预期效果 → 复核指标。"""
    return {"type": "action", "trigger": trigger, "decision": decision,
            "measures": list(measures), "expected": expected, "verify": verify}


def BENCH(title, headers, rows, takeaway=""):
    """对标表：与已存在的智慧农业系统逐项对照，避免自说自话。"""
    return {"type": "table", "title": title, "headers": headers,
            "rows": [list(r) for r in rows], "takeaway": takeaway}


def CLOSE(next_title, question, hint=""):
    return {"type": "closing", "next": next_title, "question": question, "hint": hint}


def page(no, kicker, title, *blocks, kind="body"):
    return {"no": no, "kicker": kicker, "title": title,
            "kind": kind, "blocks": list(blocks)}


def chapter(num, title, span, lead, epigraph, pages):
    return {"num": num, "title": title, "span": span,
            "lead": lead, "epigraph": epigraph, "pages": pages}
