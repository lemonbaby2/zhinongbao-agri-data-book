# -*- coding: utf-8 -*-
"""
智农宝 · 农业数据全书 — 番茄小说式交互阅读器
多卷多章、点击翻篇、层层衔接、QtCharts 图表、夜间模式、字号调节、进度记忆。
"""
import os, sys, json
from pathlib import Path

from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QFrame, QLabel, QPushButton, QScrollArea,
    QVBoxLayout, QHBoxLayout, QGridLayout, QStackedWidget, QSizePolicy, QSlider,
    QListWidget, QListWidgetItem, QDialog, QTextEdit, QGraphicsDropShadowEffect,
    QProgressBar, QAbstractItemView, QToolButton,
)
from PySide6.QtCore import Qt, QPropertyAnimation, QEasingCurve, QRect, QSize, QTimer, QParallelAnimationGroup
from PySide6.QtGui import QFont, QColor, QPalette, QPixmap, QIcon, QCursor, QPainter, QLinearGradient

try:
    from app.chart_widget import ChartWidget, CityExplorerWidget
    from app.reader import ReaderView
    from app.webserve import WebService
except ImportError:
    from chart_widget import ChartWidget, CityExplorerWidget
    from reader import ReaderView
    from webserve import WebService

APP_TITLE = "智农宝 · 农业数据全书"
VERSION = "8.0.0"


def res_path(rel):
    """兼容 PyInstaller 与源码运行。"""
    if hasattr(sys, "_MEIPASS"):
        base = Path(sys._MEIPASS)
    else:
        base = Path(__file__).parent
    p = base / rel
    return p if p.exists() else Path(__file__).parent / rel


def load_book():
    p = res_path("data/book_data.json")
    with open(p, encoding="utf-8") as f:
        return json.load(f)


def load_guangdong():
    p = res_path("data/guangdong.json")
    if not p.exists():
        return None
    with open(p, encoding="utf-8") as f:
        return json.load(f)


# ============ 通用卡片 ============
class Card(QFrame):
    def __init__(self, parent=None, night=False):
        super().__init__(parent)
        self.night = night
        self.setObjectName("card")
        self.apply()
    def apply(self):
        if self.night:
            self.setStyleSheet("QFrame#card{background:#202a36;border:1px solid #2f3c4b;border-radius:14px;}")
        else:
            self.setStyleSheet("QFrame#card{background:#ffffff;border:1px solid #eceff2;border-radius:14px;}")


# ============ 书架页 ============
class BookShelf(QWidget):
    def __init__(self, data, on_open):
        super().__init__()
        self.data = data
        self.on_open = on_open
        self.night = False
        self.init_ui()

    def init_ui(self):
        self.setStyleSheet("""
            QWidget#shelf{background:#f5f7f4;}
            QLabel.h1{font-size:34px;font-weight:800;color:#1b2f24;}
            QLabel.h2{font-size:15px;color:#7c8a80;}
        """)
        self.setObjectName("shelf")
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)

        # 顶部横幅
        hero = QFrame()
        hero.setFixedHeight(210)
        hero.setStyleSheet("""
            QFrame#hero{border:none;}
        """)
        hero.setObjectName("hero")
        hero_layout = QHBoxLayout(hero)
        hero_layout.setContentsMargins(42, 26, 42, 26)
        left = QVBoxLayout()
        kicker = QLabel("📚 数据之书 · 可翻阅的农业知识库")
        kicker.setStyleSheet("color:#d9f2e2;font-size:14px;letter-spacing:1px;")
        title = QLabel(APP_TITLE)
        title.setStyleSheet("color:#ffffff;font-size:38px;font-weight:800;font-family:'STKaiti','KaiTi','楷体','Times New Roman',serif;")
        sub = QLabel(self.data["meta"]["subtitle"] + "　·　" +
                     f'{self.data["meta"]["counts"]["books"]} 卷 / {self.data["meta"]["counts"]["chapters"]} 章 / '
                     f'{self.data["meta"]["counts"]["panel_records"]:,} 条面板记录')
        sub.setStyleSheet("color:#d9f2e2;font-size:15px;font-family:'KaiTi','楷体','Times New Roman',serif;")
        left.addWidget(kicker); left.addWidget(title); left.addWidget(sub)
        left.addStretch()
        hero_layout.addLayout(left)
        hero_layout.addStretch()
        # 右侧装饰图
        deco = QLabel()
        pm = QPixmap(str(res_path("assets/img3d/data_cubes.jpg")))
        if not pm.isNull():
            pm = pm.scaled(360, 160, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            deco.setPixmap(pm)
        deco.setFixedSize(360, 160)
        deco.setStyleSheet("border-radius:12px;")
        hero_layout.addWidget(deco)
        outer.addWidget(hero)

        # 书架标题 + 决策 Agent / 网页版入口
        title_row = QWidget()
        title_row.setStyleSheet("background:transparent;")
        tl = QHBoxLayout(title_row)
        tl.setContentsMargins(42, 24, 42, 4)
        shelf_label = QLabel("我的书架")
        shelf_label.setObjectName("h1")
        tl.addWidget(shelf_label)
        tl.addStretch(1)
        for text, fn, style in [
            ("🤖 向 AI 决策 Agent 提问", self._go_agent,
             "QPushButton{background:#0f7a44;color:#fff;border:none;border-radius:16px;padding:9px 20px;font-size:14px;font-weight:600}"
             "QPushButton:hover{background:#16b35a}"),
            ("🌐 打开交互式网页版", self._go_web,
             "QPushButton{background:#fff;color:#0f7a44;border:1px solid #bfe0cd;border-radius:16px;padding:9px 20px;font-size:14px}"
             "QPushButton:hover{background:#eaf6ef}"),
        ]:
            b = QPushButton(text)
            b.setStyleSheet(style)
            b.setCursor(Qt.PointingHandCursor)
            b.clicked.connect(fn)
            tl.addWidget(b)
        outer.addWidget(title_row)
        tip = QLabel("点击书封进入 · 每一章层层衔接，像读小说一样翻阅农业数据")
        tip.setObjectName("h2")
        tip.setContentsMargins(42, 0, 42, 12)
        outer.addWidget(tip)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setStyleSheet("QScrollArea{background:transparent;}")
        grid_w = QWidget()
        grid_w.setStyleSheet("background:transparent;")
        self.grid = QGridLayout(grid_w)
        self.grid.setContentsMargins(42, 8, 42, 30)
        self.grid.setHorizontalSpacing(22)
        self.grid.setVerticalSpacing(22)
        self.grid.setAlignment(Qt.AlignTop | Qt.AlignLeft)
        scroll.setWidget(grid_w)
        outer.addWidget(scroll)

        self.build_cards()

    def _go_agent(self):
        mw = self.window()
        if hasattr(mw, "show_agent"):
            mw.show_agent()

    def _go_web(self):
        mw = self.window()
        if hasattr(mw, "open_web"):
            mw.open_web()

    def paintEvent(self, event):
        # 英雄区渐变背景
        p = QPainter(self)
        grad = QLinearGradient(0, 0, self.width(), 210)
        grad.setColorAt(0, QColor("#0f6b3f"))
        grad.setColorAt(0.55, QColor("#178a50"))
        grad.setColorAt(1, QColor("#26a861"))
        p.fillRect(QRect(0, 0, self.width(), 210), grad)
        super().paintEvent(event)

    def build_cards(self):
        while self.grid.count():
            it = self.grid.takeAt(0)
            w = it.widget()
            if w: w.deleteLater()
        try:
            from app.typography_bridge import parts
        except ImportError:
            from typography_bridge import parts
        books = {b["id"]: b for b in self.data["books"]}
        cols = 4 if self.width() > 1200 else (3 if self.width() > 900 else 2)
        row = 0
        for part in parts():
            # 部标题（跨整行）
            band = QFrame()
            band.setObjectName("partband")
            band.setStyleSheet(
                "QFrame#partband{background:rgba(255,255,255,.92);border-radius:14px;"
                "border-left:5px solid %s;padding:10px 16px;}" % part["theme"])
            bl = QHBoxLayout(band)
            bl.setContentsMargins(14, 8, 14, 8)
            bl.setSpacing(12)
            no = QLabel(part["no"])
            no.setStyleSheet("font-family:'Times New Roman',serif;font-size:34px;"
                             "font-weight:700;color:%s;" % part["theme"])
            bl.addWidget(no)
            tt = QVBoxLayout()
            t1 = QLabel(f'第 {part["no"]} 部 · {part["title"]}')
            t1.setStyleSheet("font-family:'KaiTi','楷体','Times New Roman',serif;"
                             "font-size:19px;font-weight:700;color:#173a2a;")
            t2 = QLabel(part["lead"])
            t2.setStyleSheet("font-family:'KaiTi','楷体','Times New Roman',serif;"
                             "font-size:12.5px;color:#5d7366;")
            t2.setWordWrap(True)
            tt.addWidget(t1); tt.addWidget(t2)
            bl.addLayout(tt, 1)
            for tag in part["tags"][:3]:
                tg = QLabel(tag)
                tg.setStyleSheet("background:#eef5ef;color:#2f6b47;border-radius:9px;"
                                 "padding:3px 9px;font-size:11px;")
                bl.addWidget(tg)
            self.grid.addWidget(band, row, 0, 1, cols)
            row += 1
            # 该部的书卡
            vols = [books[v] for v in part["volumes"] if v in books]
            for i, b in enumerate(vols):
                card = self.make_book_card(b)
                self.grid.addWidget(card, row + i // cols, i % cols)
            row += (len(vols) + cols - 1) // cols

    def resizeEvent(self, e):
        super().resizeEvent(e)
        if hasattr(self, "grid"):
            self.build_cards()

    def make_book_card(self, book):
        card = QFrame()
        card.setCursor(QCursor(Qt.PointingHandCursor))
        card.setFixedSize(238, 330)
        card.setObjectName("bk")
        card.setStyleSheet("""
            QFrame#bk{background:#ffffff;border:1px solid #e6ece8;border-radius:16px;}
            QFrame#bk:hover{border:2px solid #1f9d55;}
        """)
        lay = QVBoxLayout(card)
        lay.setContentsMargins(0, 0, 0, 14)
        lay.setSpacing(0)

        cover = QLabel()
        cover.setFixedHeight(210)
        pm = QPixmap(str(res_path("assets/" + book["cover"])))
        if not pm.isNull():
            pm = pm.scaled(236, 208, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            cover.setPixmap(pm)
        cover.setStyleSheet("border-top-left-radius:16px;border-top-right-radius:16px;")
        lay.addWidget(cover)

        t = QLabel(book["title"])
        t.setStyleSheet("font-family:'Times New Roman','KaiTi','楷体',serif;"
                        "font-size:17px;font-weight:700;color:#1b2f24;padding:12px 14px 2px;")
        lay.addWidget(t)
        s = QLabel(book["subtitle"])
        s.setStyleSheet("font-family:'KaiTi','楷体','Times New Roman',serif;"
                        "font-size:12px;color:#7c8a80;padding:0 14px;")
        lay.addWidget(s)
        c = QLabel(f'{book["icon"]} {len(book["chapters"])} 章')
        c.setStyleSheet(f'font-family:"Times New Roman","KaiTi","楷体",serif;'
                        f'font-size:12px;color:{book["color"]};padding:8px 14px 0;font-weight:600;')
        lay.addWidget(c)

        def open_book(_):
            self.on_open(book)
        card.mousePressEvent = open_book
        return card


# ============ 阅读页 ============
# ============ 目录抽屉 ============
class TocDrawer(QFrame):
    def __init__(self, data, on_jump, main_window):
        super().__init__(main_window)
        self.data = data
        self.on_jump = on_jump
        self.main = main_window
        self.setFixedWidth(300)
        self.setObjectName("toc")
        self.hide()
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        head = QLabel("📖 目录")
        head.setObjectName("toc_head")
        lay.addWidget(head)
        self.list = QListWidget()
        self.list.setObjectName("toc_list")
        self.list.itemClicked.connect(self.click)
        lay.addWidget(self.list, 1)
        close = QPushButton("收起目录 ✕")
        close.setObjectName("toc_close")
        close.clicked.connect(self.main.toggle_toc)
        lay.addWidget(close)

    def load(self, book, idx):
        self.book = book
        self.list.clear()
        for i, ch in enumerate(book["chapters"]):
            npages = len(ch.get("pages") or []) or max(1, len(ch.get("blocks") or []) // 3 + 1)
            title = ch["title"]
            item = QListWidgetItem(("📍 " if i == idx else "　") + title)
            item.setData(Qt.UserRole, i)
            item.setToolTip(f"{npages} 页 · {ch.get('lead', '')[:60]}")
            if i == idx:
                item.setForeground(QColor("#1f9d55"))
                f = item.font(); f.setBold(True); item.setFont(f)
            self.list.addItem(item)
            sub = QListWidgetItem(f"　　{npages} 页　·　{ch.get('span', '')}")
            sub.setData(Qt.UserRole, i)
            sub.setForeground(QColor("#9aa39c"))
            f2 = sub.font(); f2.setPointSize(max(7, f2.pointSize() - 2)); sub.setFont(f2)
            self.list.addItem(sub)

    def click(self, item):
        self.on_jump(item.data(Qt.UserRole))


# ============ 进度管理 ============
class ProgressManager:
    """阅读进度持久化到用户目录（打包后 exe 内只读，避免重启丢失）。"""
    def __init__(self):
        self.p = {}
        appdata = os.environ.get("APPDATA", str(Path.home() / "AppData/Roaming"))
        self.path = Path(appdata) / "ZhinongbaoBook" / "progress.json"
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if self.path.exists():
            try:
                self.p = json.load(open(self.path, encoding="utf-8"))
            except Exception:
                self.p = {}
    def get(self, bid):
        return self.p.get(bid, 0)

    def get_pos(self, bid):
        """返回 (章, 页)，兼容 v5 及以前只存章号的整数格式。"""
        v = self.p.get(bid, 0)
        if isinstance(v, dict):
            return int(v.get("ch", 0)), int(v.get("pg", 0))
        return int(v or 0), 0

    def set(self, bid, pos):
        self.p[bid] = pos
        try:
            with open(self.path, "w", encoding="utf-8") as f:
                json.dump(self.p, f, ensure_ascii=False)
        except Exception:
            pass

    # ---- 书签 ----
    def get_bm(self, bid):
        bm = self.p.get("__bm__")
        return bm.get(bid) if isinstance(bm, dict) else None

    def set_bm(self, bid, val):
        bm = self.p.get("__bm__")
        if not isinstance(bm, dict):
            bm = {}
        bm[bid] = val
        self.p["__bm__"] = bm
        try:
            with open(self.path, "w", encoding="utf-8") as f:
                json.dump(self.p, f, ensure_ascii=False)
        except Exception:
            pass

    def clear_bm(self, bid):
        bm = self.p.get("__bm__")
        if isinstance(bm, dict) and bid in bm:
            bm.pop(bid, None)
            try:
                with open(self.path, "w", encoding="utf-8") as f:
                    json.dump(self.p, f, ensure_ascii=False)
            except Exception:
                pass


# ============ 主窗口 ============
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(APP_TITLE + "  v" + VERSION)
        self.resize(1280, 800)
        self.setMinimumSize(1000, 640)
        self.data = load_book()
        self.pmgr = ProgressManager()

        self.stack = QStackedWidget()
        self.setCentralWidget(self.stack)

        self.shelf = BookShelf(self.data, self.open_book)
        self.reader = ReaderView(self.data, self.pmgr, self)
        self.stack.addWidget(self.shelf)
        self.stack.addWidget(self.reader)
        self.toc = TocDrawer(self.data, self.jump, self)
        self.web = WebService(res_path("site"))
        self.agent_page = None

        self.setStyleSheet("""
            QMainWindow{background:#f5f7f4;}
            QLabel#toc_head{font-size:18px;font-weight:700;color:#1b2f24;padding:18px 18px 12px;border-bottom:1px solid #e8ece9;}
            QFrame#toc{background:#fff;border-left:1px solid #e2e8e4;}
            QListWidget#toc_list{border:none;background:#fff;padding:6px;}
            QListWidget#toc_list::item{padding:10px 8px;border-radius:6px;color:#3d4a42;}
            QListWidget#toc_list::item:selected{background:#eaf5ee;color:#1f9d55;}
            QPushButton#toc_close{background:#f0f4f1;color:#4a5a50;border:none;padding:12px;border-top:1px solid #e8ece9;}
        """)

    def show_shelf(self):
        if self.toc.isVisible(): self.toc.hide()
        self.stack.setCurrentWidget(self.shelf)

    def open_book(self, book):
        ch, pg = self.pmgr.get_pos(book["id"])
        self.reader.load(book, ch, pg)
        self.stack.setCurrentWidget(self.reader)

    def toggle_toc(self):
        if self.toc.isVisible():
            self.toc.hide()
        else:
            self.toc.show()
            self.toc.raise_()
            w = self.width()
            self.toc.setGeometry(w - 300, 56, 300, self.height() - 120)

    def jump(self, idx):
        self.reader.goto(idx)
        self.toc.hide()

    # ---------- Agent 与网页版

    def show_agent(self):
        if self.toc.isVisible():
            self.toc.hide()
        if self.agent_page is None:
            try:
                from app.agent_ui import AgentPage
            except ImportError:
                from agent_ui import AgentPage
            self.agent_page = AgentPage(reader_view=self.reader)
            self.stack.addWidget(self.agent_page)
        self.stack.setCurrentWidget(self.agent_page)

    def open_web(self):
        try:
            url = self.web.open()
            from PySide6.QtWidgets import QMessageBox
            QMessageBox.information(
                self, "已打开交互式网页版",
                f"网页版已在默认浏览器中打开：\n{url}\n\n"
                "包含 21 个页面：数据总览、省域分布、区域对比、趋势预测、"
                "种植防亏损、数字农田大屏、项目答辩等。\n"
                "服务仅监听本机 127.0.0.1，关掉本软件后自动失效。")
        except Exception as e:
            from PySide6.QtWidgets import QMessageBox
            QMessageBox.warning(self, "网页版启动失败", f"{type(e).__name__}: {e}")

    def closeEvent(self, e):
        try:
            self.web.stop()
        except Exception:
            pass
        super().closeEvent(e)

    def resizeEvent(self, e):
        super().resizeEvent(e)
        if self.toc.isVisible():
            self.toc.setGeometry(self.width() - 300, 56, 300, self.height() - 120)


def main():
    app = QApplication(sys.argv)
    app.setFont(QFont("Microsoft YaHei", 10))
    w = MainWindow()
    w.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
