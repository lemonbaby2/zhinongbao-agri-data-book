# -*- coding: utf-8 -*-
"""QT 与排版规范之间的薄桥接层：兼容 PyInstaller 打包路径。"""
import sys
from pathlib import Path

def _load():
    base = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent.parent))
    p = base / "content"
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))
    import typography as T
    return T

_T = None
def _t():
    global _T
    if _T is None:
        _T = _load()
    return _T

def mark(text, night=False):
    return _t().mark_paragraph(text, night=night)

def hits(text):
    return _t().keyword_stats(text)

def part_of(book_id):
    return _t().VOLUME_PART.get(book_id)

def parts():
    return _t().PARTS
