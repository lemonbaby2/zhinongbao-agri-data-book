# -*- coding: utf-8 -*-
"""v6 阅读器自检：翻页、跳转、热区、书签、夜间、音效、全书 200 页排版不溢出。"""
import sys
import traceback
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from PySide6.QtCore import QPoint, QPointF, Qt, QEvent
from PySide6.QtGui import QMouseEvent, QWheelEvent
from PySide6.QtWidgets import QApplication

from app.main import MainWindow

errors = []


def settle(app, ms=680):
    """推进事件循环，等翻页动画真正结束。"""
    import time
    t0 = time.time()
    while (time.time() - t0) * 1000 < ms:
        app.processEvents()
        time.sleep(0.008)


def check(cond, msg):
    print(("  ✅ " if cond else "  ❌ ") + msg)
    if not cond:
        errors.append(msg)


def main():
    app = QApplication([])
    w = MainWindow()
    w.resize(1400, 900)
    w.show()
    app.processEvents()
    w.stack.setCurrentWidget(w.reader)
    r = w.reader
    book = next(b for b in w.data["books"] if b["id"] == "vol7")
    r.load(book, 0, 0)
    for _ in range(3):
        app.processEvents()

    print("1) 结构与音效")
    check(len(book["chapters"]) == 10, f"10 章（实际 {len(book['chapters'])}）")
    check(all(len(c["pages"]) == 20 for c in book["chapters"]),
          "每章 20 页")
    check(r.sound.available, f"音效可用（{r.sound._mode}）")

    print("2) 翻页链路")
    r.next_page()
    settle(app)
    check(r.page_idx == 1, f"下一页 → 第 {r.page_idx + 1} 页")
    r.prev_page()
    settle(app)
    check(r.page_idx == 0, "上一页回到第 1 页")
    r.prev_page()          # 第 1 页再往前 → 上一章最后一页
    settle(app)
    check(r.chapter_idx == 0 and r.page_idx == 0, "首章首页不越界")
    r.goto(1)
    settle(app)
    check(r.chapter_idx == 1 and r.page_idx == 0, "goto 第 2 章第 1 页")

    print("3) 页码跳转与圆点导航")
    r.spin.setValue(12)
    settle(app)
    check(r.page_idx == 11, f"SpinBox 跳到 12 → 实际第 {r.page_idx + 1} 页")
    r.rail.jump.emit(3)
    settle(app)
    check(r.page_idx == 3, "点击圆点跳到第 4 页")

    print("4) 点击热区")
    st = r.stage
    for fx, label in ((0.9, "右侧热区 +1"), (0.1, "左侧热区 -1")):
        pos = QPointF(st.width() * fx, st.height() * 0.5)
        ev = QMouseEvent(QEvent.MouseButtonPress, pos, st.mapToGlobal(pos.toPoint()),
                         Qt.LeftButton, Qt.LeftButton, Qt.NoModifier)
        before = r.page_idx
        QApplication.sendEvent(st, ev)
        settle(app)
        want = before + (1 if fx > 0.5 else -1)
        check(r.page_idx == want, f"{label}（{before} → {r.page_idx}）")

    print("5) 滚轮翻页")
    before = r.page_idx
    wev = QWheelEvent(QPointF(st.width() / 2, st.height() / 2),
                      st.mapToGlobal(QPoint(int(st.width() / 2), int(st.height() / 2))),
                      QPoint(0, 0), QPoint(0, -120), Qt.NoButton,
                      Qt.NoModifier, Qt.NoScrollPhase, False)
    QApplication.sendEvent(r, wev)
    settle(app)
    check(r.page_idx == before + 1, f"滚轮向下翻一页（{before} → {r.page_idx}）")
    r._last_wheel = 0
    wev_up = QWheelEvent(QPointF(st.width() / 2, st.height() / 2),
                         st.mapToGlobal(QPoint(int(st.width() / 2), int(st.height() / 2))),
                         QPoint(0, 0), QPoint(0, 120), Qt.NoButton,
                         Qt.NoModifier, Qt.NoScrollPhase, False)
    before = r.page_idx
    QApplication.sendEvent(r, wev_up)
    settle(app)
    check(r.page_idx == before - 1, f"滚轮向上回翻（{before} → {r.page_idx}）")

    print("6) 书签与夜间")
    w.pmgr.clear_bm(book["id"])
    r.toggle_bookmark()
    bm = w.pmgr.get_bm(book["id"])
    check(bool(bm) and bm.get("pg") == r.page_idx, f"书签写入 {bm}")
    r.toggle_night()
    app.processEvents()
    check(r.night and r.sheet.night, "夜间模式切换")
    r.toggle_night()

    print("7) 全书 200 页排版扫描")
    worst = []
    pages = 0
    for ci in range(len(book["chapters"])):
        for pi in range(len(book["chapters"][ci]["pages"])):
            pages += 1
            r.load(book, ci, pi)
            for _ in range(2):
                app.processEvents()
            avail = r.scroll.viewport().height()
            need = r.playout.sizeHint().height()
            if need > avail + 4:
                worst.append((ci + 1, pi + 1, need - avail, round(r.fit, 2)))
    check(pages == 200, f"扫描 {pages} 页")
    check(not worst, f"无溢出页（溢出 {len(worst)} 页：{worst[:6]}）")

    print("8) 各章首末页抽查")
    for ci in (0, 4, 9):
        r.load(book, ci, 0)
        app.processEvents()
        t1 = r.lbl_progress.text()
        r.load(book, ci, 19)
        app.processEvents()
        print(f"    第{ci+1}章 首页「{t1}」末页「{r.lbl_progress.text()}」")

    print("\n结论：" + ("全部通过 ✅" if not errors else f"{len(errors)} 项失败 ❌"))
    for e in errors:
        print("  -", e)
    w.close()
    return 0 if not errors else 1


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:
        traceback.print_exc()
        sys.exit(2)
