# -*- coding: utf-8 -*-
"""v8 专测：卷八 100 页排版、新块型（algo/action/image）渲染、无溢出。
沿用 test_reader.py 的真实 MainWindow + _fit_check 缩排机制。
"""
import sys, traceback
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from PySide6.QtWidgets import QApplication
from app.main import MainWindow

errors = []
overflow = []
counts = {}


def settle(app, ms=90):
    import time
    t0 = time.time()
    while (time.time() - t0) * 1000 < ms:
        app.processEvents()
        time.sleep(0.006)


def main():
    app = QApplication([])
    w = MainWindow()
    w.resize(1400, 900)
    w.show()
    app.processEvents()
    w.stack.setCurrentWidget(w.reader)
    r = w.reader
    book = next(b for b in w.data["books"] if b["id"] == "vol8")
    print("卷八：", book["title"], len(book["chapters"]), "章")

    for ci, ch in enumerate(book["chapters"]):
        for pi in range(len(ch["pages"])):
            try:
                r.load(book, ci, pi)
                settle(app)
                pg = ch["pages"][pi]
                for b in pg["blocks"]:
                    counts[b["type"]] = counts.get(b["type"], 0) + 1
                hint = r.playout.sizeHint().height()
                avail = r.scroll.viewport().height()
                if hint > avail + 8:
                    overflow.append((ci + 1, pi + 1, hint, avail))
            except Exception:
                errors.append((ci + 1, pi + 1, traceback.format_exc()[-400:]))

    print("块型统计：", counts)
    print("渲染异常：", len(errors))
    for e in errors[:5]:
        print("  ", e)
    print("溢出页：", len(overflow))
    for o in overflow[:8]:
        print("  ", o)
    ok = not errors and not overflow
    print("结论：", "全部通过 ✅" if ok else "存在问题 ❌")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
