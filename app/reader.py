# -*- coding: utf-8 -*-
"""智农宝 · 真书翻页阅读器（v6）

设计目标：把每一章做成一本可以翻的纸书——
  * 单页版式：页眉（栏目/书名）、正文、页脚页码，纸纹背景与书脊装订线；
  * 透视翻页动画：旧页沿折痕卷起/新页展开，带折痕阴影与纸边高光；
  * 翻页音效：程序合成的纸张沙沙声，可在界面上开关；
  * 点击热区：点页面左右两侧即可翻页，翻到底自动进下一章；
  * 交互控件：页码跳转、书签、目录（含页数）、字号、夜间模式、AI 决策、网页版。

数据层同时兼容两种结构：
  * 新结构 chapter["pages"]（卷七：10 章 × 20 页）；
  * 旧结构 chapter["blocks"]（其余各卷：自动按块分页）。
"""
import json
import sys
from pathlib import Path

from PySide6.QtCore import (Qt, QRectF, QPointF, QTimer, QVariantAnimation,
                            QEasingCurve, Signal, QSize)
from PySide6.QtGui import (QBrush, QColor, QFont, QLinearGradient, QPainter,
                           QPen, QPixmap, QPolygonF, QTransform)
from PySide6.QtWidgets import (QAbstractItemView, QComboBox, QDialog, QFrame,
                               QGridLayout, QHBoxLayout, QLabel, QPushButton,
                               QScrollArea, QSizePolicy, QSpinBox, QTableWidget,
                               QTableWidgetItem, QHeaderView, QToolButton,
                               QVBoxLayout, QWidget, QGraphicsDropShadowEffect)

try:
    from app.chart_widget import ChartWidget, CityExplorerWidget
except ImportError:
    from chart_widget import ChartWidget, CityExplorerWidget

try:
    from app.typography_bridge import mark, hits, part_of, parts
except ImportError:
    from typography_bridge import mark, hits, part_of, parts

APP_TITLE = "智农宝 · 农业数据全书"


def res_path(rel):
    """兼容 PyInstaller 与源码运行：优先 _MEIPASS，其次 app/ 目录。"""
    base = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
    p = base / rel
    return p if p.exists() else Path(__file__).resolve().parent / rel


# --------------------------------------------------------------------------
# 音效
# --------------------------------------------------------------------------
class SoundKit:
    """优先用 winsound（Windows 原生、打包后无需多媒体插件），否则退回 QSoundEffect。"""

    NAMES = ("turn", "turn_back", "open", "close", "tick")

    def __init__(self):
        self.dir = res_path("assets/sfx")
        self.enabled = True
        self._mode = None
        self._effects = {}
        try:
            import winsound  # noqa: F401
            self._ws = winsound
            self._mode = "win"
        except Exception:
            self._ws = None
        if self._mode is None:
            try:
                from PySide6.QtMultimedia import QSoundEffect
                from PySide6.QtCore import QUrl
                for n in self.NAMES:
                    p = self.dir / f"{n}.wav"
                    if p.exists():
                        e = QSoundEffect()
                        e.setSource(QUrl.fromLocalFile(str(p)))
                        e.setVolume(0.7)
                        self._effects[n] = e
                self._mode = "qt" if self._effects else None
            except Exception:
                self._mode = None

    @property
    def available(self):
        return self._mode is not None

    def play(self, name, vol=0.75):
        if not self.enabled or not self._mode:
            return
        p = self.dir / f"{name}.wav"
        if not p.exists():
            return
        try:
            if self._mode == "win":
                self._ws.PlaySound(str(p), self._ws.SND_FILENAME |
                                   self._ws.SND_ASYNC | self._ws.SND_NODEFAULT)
            else:
                e = self._effects.get(name)
                if e:
                    e.setVolume(vol)
                    e.play()
        except Exception:
            pass


# --------------------------------------------------------------------------
# 纸张
# --------------------------------------------------------------------------
class PaperSheet(QFrame):
    """一张纸：纸纹、内框线、装订侧阴影。"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.night = False
        self._tex = QPixmap(str(res_path("assets/paper.png")))
        self.setObjectName("paper")

    def set_night(self, v):
        self.night = v
        self.update()

    def paintEvent(self, e):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        r = self.rect().adjusted(0, 0, -1, -1)
        base = QColor("#16202b") if self.night else QColor("#fbf8f0")
        p.fillRect(r, base)
        if not self._tex.isNull():
            p.setOpacity(0.35 if self.night else 0.85)
            p.drawTiledPixmap(r, self._tex)
            p.setOpacity(1.0)
        # 装订侧（左侧）阴影
        g = QLinearGradient(r.left(), 0, r.left() + 38, 0)
        g.setColorAt(0, QColor(0, 0, 0, 60 if self.night else 42))
        g.setColorAt(1, QColor(0, 0, 0, 0))
        p.fillRect(QRectF(r.left(), r.top(), 38, r.height()), QBrush(g))
        # 右侧页边
        g2 = QLinearGradient(r.right() - 26, 0, r.right(), 0)
        g2.setColorAt(0, QColor(0, 0, 0, 0))
        g2.setColorAt(1, QColor(0, 0, 0, 26 if self.night else 16))
        p.fillRect(QRectF(r.right() - 26, r.top(), 26, r.height()), QBrush(g2))
        # 内框细线
        pen = QPen(QColor(120, 110, 90, 40 if self.night else 55), 1)
        p.setPen(pen)
        p.drawRect(r.adjusted(26, 22, -20, -22))
        # 农田等高线暗纹（右下留白处）
        p.save()
        p.setOpacity(0.10 if self.night else 0.16)
        p.setPen(QPen(QColor(120, 150, 120), 1.1))
        cx, cy = r.right() - 90, r.bottom() - 60
        for k in range(7):
            p.drawArc(QRectF(cx - 40 - k * 26, cy - 26 - k * 12, 80 + k * 52, 52 + k * 24),
                      200 * 16, 140 * 16)
        p.restore()
        # 右下卷角
        p.save()
        p.setOpacity(0.7)
        size = 22
        poly = QPolygonF([QPointF(r.right() - size, r.bottom()),
                          QPointF(r.right(), r.bottom() - size),
                          QPointF(r.right(), r.bottom())])
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(0, 0, 0, 26))
        p.drawPolygon(poly)
        p.restore()
        super().paintEvent(e)


# --------------------------------------------------------------------------
# 透视翻页
# --------------------------------------------------------------------------
class FlipOverlay(QWidget):
    """front = 旧页快照，back = 新页快照。

    direction > 0：旧页从左折起，露出新页；
    direction < 0：新页自左展开，覆盖旧页。
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        self.hide()
        self.t = 0.0
        self.dir = 1
        self.front = None
        self.back = None
        self._done = None
        self.anim = QVariantAnimation(self)
        self.anim.valueChanged.connect(self._tick)
        self.anim.finished.connect(self._finish)

    def start(self, front, back, direction, on_done=None, duration=320):
        self.front, self.back = front, back
        self.dir = direction
        self.t = 0.0
        self._done = on_done
        if self.parent():
            self.setGeometry(self.parent().rect())
        self.show()
        self.raise_()
        self.anim.stop()
        self.anim.setDuration(duration)
        self.anim.setStartValue(0.0)
        self.anim.setEndValue(1.0)
        self.anim.setEasingCurve(QEasingCurve.OutCubic)
        self.anim.start()

    def _tick(self, v):
        self.t = float(v)
        self.update()

    def _finish(self):
        self.hide()
        cb = self._done
        self._done = None
        if cb:
            cb()

    @staticmethod
    def _quad(w, h, fold, curve):
        return QPolygonF([QPointF(0, 0),
                          QPointF(fold, h * curve),
                          QPointF(fold, h * (1 - curve)),
                          QPointF(0, h)])

    def _draw_mapped(self, p, pix, fold, curve, w, h):
        if pix is None or pix.isNull():
            return
        src = QPolygonF([QPointF(0, 0), QPointF(pix.width(), 0),
                         QPointF(pix.width(), pix.height()), QPointF(0, pix.height())])
        tr = QTransform()
        if QTransform.quadToQuad(src, self._quad(w, h, max(fold, 1.0), curve), tr):
            p.save()
            p.setTransform(tr)
            p.drawPixmap(0, 0, pix)
            p.restore()

    def paintEvent(self, e):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.setRenderHint(QPainter.SmoothPixmapTransform)
        w, h = self.width(), self.height()
        t = self.t
        curve = 0.030 * (abs(0.5 - t) * 2) + 0.004
        if self.dir > 0:
            if self.back is not None:
                p.drawPixmap(0, 0, self.back)
            fold = w * (1 - 0.955 * t)
            self._draw_mapped(p, self.front, fold, curve, w, h)
            # 折痕阴影
            g = QLinearGradient(fold - 110, 0, fold + 8, 0)
            g.setColorAt(0.0, QColor(0, 0, 0, 0))
            g.setColorAt(0.75, QColor(0, 0, 0, 70))
            g.setColorAt(1.0, QColor(0, 0, 0, 110))
            p.fillRect(QRectF(max(fold - 110, 0), 0, min(118, fold + 8), h), QBrush(g))
            # 翻起一页的纸背：折痕右侧一条亮边
            back_w = min(12, max(3, w * 0.03 * (1 - t)))
            gb = QLinearGradient(fold, 0, fold + back_w, 0)
            gb.setColorAt(0, QColor(255, 255, 252, 200))
            gb.setColorAt(0.6, QColor(246, 242, 232, 90))
            gb.setColorAt(1, QColor(230, 225, 212, 0))
            p.fillRect(QRectF(fold, h * curve, back_w, h * (1 - 2 * curve)), QBrush(gb))
            p.setPen(QPen(QColor(255, 255, 255, 200), 1.2))
            p.drawLine(QPointF(fold, h * curve), QPointF(fold, h * (1 - curve)))
        else:
            if self.front is not None:
                p.drawPixmap(0, 0, self.front)
            fold = w * 0.955 * t
            self._draw_mapped(p, self.back, fold, curve * (1 - t), w, h)
            g = QLinearGradient(fold - 8, 0, fold + 110, 0)
            g.setColorAt(0.0, QColor(0, 0, 0, 100))
            g.setColorAt(0.3, QColor(0, 0, 0, 55))
            g.setColorAt(1.0, QColor(0, 0, 0, 0))
            p.fillRect(QRectF(fold, 0, min(118, w - fold), h), QBrush(g))
            p.setPen(QPen(QColor(255, 255, 255, 110), 1.2))
            p.drawLine(QPointF(fold, h * curve * (1 - t)),
                       QPointF(fold, h * (1 - curve * (1 - t))))


# --------------------------------------------------------------------------
# 点击热区
# --------------------------------------------------------------------------
class StageArea(QFrame):
    prev_clicked = Signal()
    next_clicked = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("stage")
        self.setMouseTracking(True)
        self.setCursor(Qt.ArrowCursor)
        self._hover = 0

    def mouseMoveEvent(self, e):
        x = e.position().x()
        side = -1 if x < self.width() * 0.18 else (1 if x > self.width() * 0.82 else 0)
        if side != self._hover:
            self._hover = side
            self.setCursor(Qt.PointingHandCursor if side else Qt.ArrowCursor)
            self.update()
        super().mouseMoveEvent(e)

    def leaveEvent(self, e):
        self._hover = 0
        self.update()
        super().leaveEvent(e)

    def mousePressEvent(self, e):
        if e.button() == Qt.LeftButton:
            x = e.position().x()
            if x < self.width() * 0.18:
                self.prev_clicked.emit()
                return
            if x > self.width() * 0.82:
                self.next_clicked.emit()
                return
        super().mousePressEvent(e)

    def paintEvent(self, e):
        super().paintEvent(e)
        if not self._hover:
            return
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        h = self.height()
        cy = h / 2
        alpha = 46 if self._hover < 0 else 46
        c = QColor(255, 255, 255, alpha)
        p.setPen(Qt.NoPen)
        p.setBrush(QBrush(c))
        if self._hover < 0:
            p.setOpacity(0.55)
            p.drawEllipse(QPointF(24, cy), 15, 15)
            p.setPen(QPen(QColor(60, 60, 60, 150), 1.6))
            p.drawLine(QPointF(29, cy), QPointF(19, cy))
            p.drawLine(QPointF(19, cy), QPointF(24, cy - 5))
            p.drawLine(QPointF(19, cy), QPointF(24, cy + 5))
        else:
            p.setOpacity(0.55)
            p.drawEllipse(QPointF(self.width() - 24, cy), 15, 15)
            p.setPen(QPen(QColor(60, 60, 60, 150), 1.6))
            p.drawLine(QPointF(self.width() - 29, cy), QPointF(self.width() - 19, cy))
            p.drawLine(QPointF(self.width() - 19, cy), QPointF(self.width() - 24, cy - 5))
            p.drawLine(QPointF(self.width() - 19, cy), QPointF(self.width() - 24, cy + 5))


class PageRail(QWidget):
    """纸页右侧的翻页导航轨：每章 20 个点，当前页高亮，可点击跳转。"""

    jump = Signal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.total = 0
        self.cur = 0
        self.night = False
        self.setFixedWidth(16)
        self.setCursor(Qt.PointingHandCursor)
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setToolTip("点击圆点可跳到对应页")

    def set_pages(self, total, cur, night=False):
        self.total, self.cur, self.night = total, cur, night
        self.setFixedHeight(max(60, total * 13))
        self.update()

    def paintEvent(self, e):
        if not self.total:
            return
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        step = (self.height() - 10) / max(1, self.total - 1)
        for i in range(self.total):
            y = 5 + i * step
            if i == self.cur:
                p.setBrush(QColor("#b23b2e") if not self.night else QColor("#7fe0b0"))
                p.setPen(Qt.NoPen)
                p.drawEllipse(QPointF(8, y), 3.6, 3.6)
                p.setPen(QPen(QColor(178, 59, 46, 90) if not self.night else QColor(127, 224, 176, 90), 1))
                p.drawEllipse(QPointF(8, y), 6.6, 6.6)
            else:
                p.setPen(Qt.NoPen)
                p.setBrush(QColor(150, 140, 118, 120) if not self.night else QColor(120, 140, 160, 120))
                p.drawEllipse(QPointF(8, y), 2.2, 2.2)

    def mousePressEvent(self, e):
        if not self.total:
            return
        step = (self.height() - 10) / max(1, self.total - 1)
        idx = int(round((e.position().y() - 5) / step)) if step else 0
        self.jump.emit(max(0, min(self.total - 1, idx)))


# --------------------------------------------------------------------------
# 分页工具
# --------------------------------------------------------------------------
def chapter_pages(ch):
    """把章节统一成页列表。旧书（只有 blocks）按块自动分页。"""
    if ch.get("pages"):
        return ch["pages"]
    pages = [{"no": 1, "kicker": "本章", "title": ch.get("title", ""),
              "kind": "cover", "blocks": [], "lead": ch.get("lead", "")}]
    blocks = ch.get("blocks") or []
    chunk, cur, idx = [], [], 2
    for b in blocks:
        cur.append(b)
        if len(cur) >= 3 or b.get("type") in ("table", "chart"):
            chunk.append(cur)
            cur = []
    if cur:
        chunk.append(cur)
    for i, c in enumerate(chunk):
        pages.append({"no": idx, "kicker": "本章" if i == 0 else "续前页",
                      "title": ch.get("title", ""), "kind": "body", "blocks": c})
        idx += 1
    return pages


def load_guangdong():
    for p in (res_path("data/guangdong.json"), res_path("app/data/guangdong.json")):
        if Path(p).exists():
            try:
                return json.load(open(p, encoding="utf-8"))
            except Exception:
                return None
    return None


# --------------------------------------------------------------------------
# 阅读器
# --------------------------------------------------------------------------
class ReaderView(QWidget):
    def __init__(self, data, progress_mgr, main_window):
        super().__init__()
        self.data = data
        self.gd = load_guangdong()
        self.pmgr = progress_mgr
        self.main = main_window
        self.book = None
        self.chapter_idx = 0
        self.page_idx = 0
        self.night = False
        self.scale = 1.0
        self.fit = 1.0
        self.charts = []
        self.tables = []
        self.sound = SoundKit()
        self._turning = False
        self._turn_ts = 0.0
        self._last_wheel = 0
        self.init_ui()

    # ---------------- UI ----------------
    def init_ui(self):
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)

        # 顶栏
        bar = QFrame()
        bar.setFixedHeight(54)
        bar.setObjectName("topbar")
        bl = QHBoxLayout(bar)
        bl.setContentsMargins(16, 0, 16, 0)
        bl.setSpacing(8)
        self.btn_back = QToolButton()
        self.btn_back.setText("← 书架")
        self.btn_back.setObjectName("tbbtn")
        self.btn_back.clicked.connect(self.main.show_shelf)
        bl.addWidget(self.btn_back)

        self.lbl_book = QLabel("")
        self.lbl_book.setObjectName("booktitle")
        bl.addWidget(self.lbl_book)
        bl.addStretch(1)

        self.lbl_progress = QLabel("")
        self.lbl_progress.setObjectName("prog")
        bl.addWidget(self.lbl_progress)
        bl.addSpacing(8)

        for text, fn, obj in [("A-", self.font_down, "btn_fdown"),
                              ("A+", self.font_up, "btn_fup"),
                              ("☾ 夜间", self.toggle_night, "btn_night"),
                              ("🔊 音效", self.toggle_sound, "btn_sound"),
                              ("📖 目录", self.main.toggle_toc, "btn_toc")]:
            b = QPushButton(text)
            b.setObjectName("tbbtn2")
            b.clicked.connect(fn)
            b.setCursor(Qt.PointingHandCursor)
            bl.addWidget(b)
            setattr(self, obj, b)

        self.btn_agent = QPushButton("🤖 AI 决策")
        self.btn_agent.setObjectName("tbbtn2")
        self.btn_agent.setStyleSheet(
            "QPushButton{background:qlineargradient(x1:0,y1:0,x2:1,y2:0,stop:0 #12a150,stop:1 #0b5b34);"
            "color:#fff;border:none;border-radius:14px;padding:6px 14px;font-size:13px;font-weight:600}"
            "QPushButton:hover{background:#16b35a}")
        self.btn_agent.setCursor(Qt.PointingHandCursor)
        self.btn_agent.clicked.connect(self.main.show_agent)
        bl.addWidget(self.btn_agent)

        self.btn_web = QPushButton("🌐 网页版")
        self.btn_web.setObjectName("tbbtn2")
        self.btn_web.setCursor(Qt.PointingHandCursor)
        self.btn_web.setToolTip("打开内置交互式数据分析网页")
        self.btn_web.clicked.connect(self.main.open_web)
        bl.addWidget(self.btn_web)
        lay.addWidget(bar)

        # 书桌
        self.desk = QFrame()
        self.desk.setObjectName("desk")
        dl = QHBoxLayout(self.desk)
        dl.setContentsMargins(26, 16, 26, 12)
        dl.setSpacing(0)

        self.bookframe = QFrame()
        self.bookframe.setObjectName("bookframe")
        self.bookframe.setMaximumWidth(1060)
        bf = QHBoxLayout(self.bookframe)
        bf.setContentsMargins(0, 0, 0, 0)
        bf.setSpacing(0)

        # 书脊
        self.spine = QFrame()
        self.spine.setObjectName("spine")
        self.spine.setFixedWidth(24)
        sv = QVBoxLayout(self.spine)
        sv.setContentsMargins(0, 18, 0, 18)
        self.spine_lbl = QLabel("智 农 宝")
        self.spine_lbl.setObjectName("spinelbl")
        self.spine_lbl.setAlignment(Qt.AlignHCenter | Qt.AlignTop)
        sv.addWidget(self.spine_lbl)
        bf.addWidget(self.spine)

        self.stage = StageArea()
        self.stage.prev_clicked.connect(self.prev_page)
        self.stage.next_clicked.connect(self.next_page)
        sl = QVBoxLayout(self.stage)
        sl.setContentsMargins(0, 0, 0, 0)
        sl.setSpacing(0)

        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.NoFrame)
        self.scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.sheet = PaperSheet()
        self.playout = QVBoxLayout(self.sheet)
        self.playout.setContentsMargins(94, 38, 88, 30)
        self.playout.setSpacing(0)
        self.scroll.setWidget(self.sheet)
        sl.addWidget(self.scroll)
        bf.addWidget(self.stage, 1)
        dl.addStretch(1)
        dl.addWidget(self.bookframe, 12)
        dl.addStretch(1)
        lay.addWidget(self.desk, 1)

        self.flip = FlipOverlay(self.stage)
        self.rail = PageRail(self.stage)
        self.rail.jump.connect(self._rail_jump)
        self.rail.raise_()

        # 底栏
        bottom = QFrame()
        bottom.setFixedHeight(62)
        bottom.setObjectName("bottombar")
        btl = QHBoxLayout(bottom)
        btl.setContentsMargins(18, 0, 18, 0)
        btl.setSpacing(8)

        self.btn_pch = QPushButton("⏮ 上一章")
        self.btn_pch.setObjectName("pagebtn2")
        self.btn_pch.clicked.connect(self.prev_chapter)
        self.btn_prev = QPushButton("◀ 上一页")
        self.btn_prev.setObjectName("pagebtn")
        self.btn_prev.clicked.connect(self.prev_page)
        self.btn_next = QPushButton("下一页 ▶")
        self.btn_next.setObjectName("pagebtn")
        self.btn_next.clicked.connect(self.next_page)
        self.btn_nch = QPushButton("下一章 ⏭")
        self.btn_nch.setObjectName("pagebtn2")
        self.btn_nch.clicked.connect(self.next_chapter)

        btl.addWidget(self.btn_pch)
        btl.addWidget(self.btn_prev)
        btl.addStretch(1)

        self.spin = QSpinBox()
        self.spin.setObjectName("pagespin")
        self.spin.setFixedWidth(74)
        self.spin.setAlignment(Qt.AlignCenter)
        self.spin.setKeyboardTracking(False)
        self.spin.valueChanged.connect(self._spin_jump)
        btl.addWidget(QLabel("跳到"))
        btl.addWidget(self.spin)
        self.lbl_page = QLabel("")
        self.lbl_page.setObjectName("pagelbl")
        btl.addWidget(self.lbl_page)

        btl.addStretch(1)
        self.btn_bookmark = QPushButton("🔖 书签")
        self.btn_bookmark.setObjectName("pagebtn2")
        self.btn_bookmark.clicked.connect(self.toggle_bookmark)
        btl.addWidget(self.btn_bookmark)
        btl.addWidget(self.btn_next)
        btl.addWidget(self.btn_nch)
        lay.addWidget(bottom)

    # ---------------- 数据 ----------------
    def load(self, book, index, page=0):
        self.book = book
        self.pages_meta = [chapter_pages(ch) for ch in book["chapters"]]
        self.chapter_idx = max(0, min(index, len(book["chapters"]) - 1))
        npages = len(self.pages_meta[self.chapter_idx])
        self.page_idx = max(0, min(page, npages - 1))
        self.render()
        self._save()
        if hasattr(self.main, "toc"):
            self.main.toc.load(book, self.chapter_idx)
        if index == 0 and page == 0:
            self.sound.play("open", 0.6)

    def _save(self):
        self.pmgr.set(self.book["id"], {"ch": self.chapter_idx, "pg": self.page_idx})

    def _rail_jump(self, idx):
        if idx == self.page_idx:
            return
        self.turn_to(idx, 1 if idx > self.page_idx else -1)

    def _place_rail(self):
        try:
            h = self.rail.height()
            w = self.stage.width()
            self.rail.setGeometry(w - 26, max(18, (self.stage.height() - h) // 2), 16, h)
            self.rail.raise_()
        except Exception:
            pass

    def resizeEvent(self, e):
        super().resizeEvent(e)
        self._place_rail()

    def _spin_jump(self, v):
        if not self.book:
            return
        v = int(v)
        if v == self.page_idx + 1:
            return
        idx = v - 1
        if 0 <= idx < len(self.pages_meta[self.chapter_idx]):
            self.turn_to(idx, 1 if idx > self.page_idx else -1)

    # ---------------- 渲染 ----------------
    def render(self):
        ch = self.book["chapters"][self.chapter_idx]
        pages = self.pages_meta[self.chapter_idx]
        total_ch = len(self.book["chapters"])
        self.lbl_book.setText(f'{self.book["title"]}')
        self.lbl_progress.setText(
            f"第 {self.chapter_idx + 1}/{total_ch} 章 · 第 {self.page_idx + 1}/{len(pages)} 页")
        self.btn_prev.setEnabled(self.page_idx > 0 or self.chapter_idx > 0)
        self.btn_next.setEnabled(self.page_idx < len(pages) - 1 or
                                 self.chapter_idx < total_ch - 1)
        self.btn_pch.setEnabled(self.chapter_idx > 0)
        self.btn_nch.setEnabled(self.chapter_idx < total_ch - 1)
        self.spin.blockSignals(True)
        self.spin.setRange(1, len(pages))
        self.spin.setValue(self.page_idx + 1)
        self.spin.blockSignals(False)
        self.lbl_page.setText(f"/ {len(pages)} 页")
        self.rail.set_pages(len(pages), self.page_idx, self.night)
        self._place_rail()
        self._build_page(ch, pages[self.page_idx])

    def _purge(self, item):
        """递归清空布局项：直接删除子控件与子布局，避免遗留"幽灵文字"。"""
        w = item.widget()
        if w is not None:
            w.setParent(None)
            w.deleteLater()
            return
        lay = item.layout()
        if lay is not None:
            while lay.count():
                self._purge(lay.takeAt(0))
            lay.deleteLater()

    def _clear(self):
        self.sheet.setUpdatesEnabled(False)
        while self.playout.count():
            self._purge(self.playout.takeAt(0))
        self.charts = []
        self.tables = []
        self.sheet.setUpdatesEnabled(True)

    def _build_page(self, ch, page):
        self._clear()
        self.sheet.set_night(self.night)
        pages = self.pages_meta[self.chapter_idx]
        cover = page.get("kind") == "cover"

        # 页眉
        if not cover:
            head = QFrame()
            head.setObjectName("pagehead")
            hl = QHBoxLayout(head)
            hl.setContentsMargins(0, 0, 0, 6)
            k = QLabel(page.get("kicker", ""))
            k.setObjectName("pagekick")
            part_label = part_of(self.book.get("id", "")) or ""
            pc = ""
            if part_label:
                pc = next((x["no"] + " " + x["title"] for x in parts() if x["id"] == part_label), "")
            r = QLabel((f'第 {pc} 部　|　' if pc else '') +
                       f'{self.book["title"]}　·　{ch.get("span", "")}')
            r.setObjectName("pagekick")
            hl.addWidget(k)
            hl.addStretch(1)
            hl.addWidget(r)
            self.playout.addWidget(head)
            rule = QFrame()
            rule.setObjectName("pagerule")
            rule.setFixedHeight(1)
            self.playout.addWidget(rule)
        else:
            self.playout.addSpacing(6)

        if cover:
            self.playout.addStretch(1)
            self._build_cover(ch, page)
        else:
            top = QHBoxLayout()
            top.setContentsMargins(0, 2, 0, 0)
            top.setSpacing(12)
            num = QLabel(f"{page.get('no', 1):02d}")
            num.setObjectName("pagenum")
            num.setFixedWidth(86)
            num.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
            txt = QVBoxLayout()
            txt.setSpacing(2)
            ttl = QLabel(page.get("title", ""))
            ttl.setObjectName("pagetitle")
            ttl.setWordWrap(True)
            sub = QLabel(ch.get("theme", "") or ch.get("span", ""))
            sub.setObjectName("pagesub")
            txt.addWidget(ttl)
            txt.addWidget(sub)
            top.addWidget(num, 0, Qt.AlignTop)
            top.addLayout(txt, 1)
            self.playout.addLayout(top)
            self.playout.addSpacing(8)

        blocks = page.get("blocks", [])
        if len(blocks) == 1 and blocks[0].get("type") == "closing":
            self.playout.addStretch(1)      # 尾页垂直居中，留白更像书籍版权页
        for b in blocks:
            w = self.build_block(b)
            if w:
                self.playout.addWidget(w)

        if any(b.get("type") in ("chart", "table") for b in page.get("blocks", [])):
            src = QLabel("资料来源：《广东农村统计年鉴 2019》／广东省统计局年度公报；"
                         "2026 年为模型外推值，非官方统计。")
            src.setObjectName("srcnote")
            src.setWordWrap(True)
            self.playout.addWidget(src)

        self.playout.addStretch(1)

        ornbox = QFrame()
        ornbox.setObjectName("ornbox")
        ol = QHBoxLayout(ornbox)
        ol.setContentsMargins(0, 0, 0, 0)
        line1 = QFrame(); line1.setObjectName("ornline"); line1.setFixedHeight(1)
        ornmark = QLabel("❖")
        ornmark.setObjectName("ornmark")
        line2 = QFrame(); line2.setObjectName("ornline"); line2.setFixedHeight(1)
        ol.addWidget(line1, 1); ol.addWidget(ornmark, 0); ol.addWidget(line2, 1)
        self.playout.addWidget(ornbox)

        # 页脚
        foot = QFrame()
        foot.setObjectName("pagefoot")
        fl = QHBoxLayout(foot)
        fl.setContentsMargins(0, 8, 0, 0)
        gno = sum(len(p) for p in self.pages_meta[:self.chapter_idx]) + self.page_idx + 1
        left = QLabel(ch.get("theme", "") or "")
        left.setObjectName("foottxt")
        mid = QLabel(f"— {gno} —")
        mid.setObjectName("footnum")
        right = QLabel(f"第 {self.page_idx + 1} / {len(pages)} 页")
        right.setObjectName("foottxt")
        fl.addWidget(left)
        fl.addStretch(1)
        fl.addWidget(mid)
        fl.addStretch(1)
        fl.addWidget(right)
        self.playout.addWidget(foot)

        self.apply_theme()
        QTimer.singleShot(0, self._fit_check)

    def _build_cover(self, ch, page):
        box = QFrame()
        box.setObjectName("cover")
        v = QVBoxLayout(box)
        v.setContentsMargins(6, 26, 6, 10)
        v.setSpacing(10)

        # 3D 等距插画：按所属「部」选取，给扉页空间立体感
        part_id = part_of(self.book.get("id", "")) or ""
        img_map = {"part1": "guangdong_map", "part2": "tea_garden",
                   "part3": "dashboard", "part4": "smart_farm"}
        img_name = img_map.get(part_id, "smart_farm")
        hero = QLabel()
        hero.setObjectName("cover3d")
        hero.setAlignment(Qt.AlignCenter)
        pm = QPixmap(str(res_path("assets/img3d/" + img_name + ".jpg")))
        if not pm.isNull():
            # 裁成宽幅横图：居中取景，保留立体构图
            from PySide6.QtCore import Qt as _Qt
            target_ratio = 2.5
            if pm.width() / pm.height() > target_ratio:
                nw = int(pm.height() * target_ratio)
                pm = pm.copy((pm.width() - nw) // 2, 0, nw, pm.height())
            else:
                nh = int(pm.width() / target_ratio)
                pm = pm.copy(0, (pm.height() - nh) // 3, pm.width(), nh)
            pm = pm.scaled(520, 208, _Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation)
            hero.setPixmap(pm)
        v.addWidget(hero)

        kick = QLabel(ch.get("span", ""))
        kick.setObjectName("coverkick")
        kick.setAlignment(Qt.AlignCenter)
        v.addWidget(kick)

        title = QLabel(ch["title"].split("·", 1)[-1].strip())
        title.setObjectName("covertitle")
        title.setWordWrap(True)
        title.setAlignment(Qt.AlignCenter)
        v.addWidget(title)

        orn = QLabel("◆　◆　◆")
        orn.setObjectName("coverorn")
        orn.setAlignment(Qt.AlignCenter)
        v.addWidget(orn)

        epi = QLabel(ch.get("epigraph", ""))
        epi.setObjectName("coverepi")
        epi.setAlignment(Qt.AlignCenter)
        epi.setWordWrap(True)
        v.addWidget(epi)

        lead = QLabel(ch.get("lead", ""))
        lead.setObjectName("coverlead")
        lead.setWordWrap(True)
        v.addWidget(lead)
        v.addSpacing(6)
        self.playout.addWidget(box)

    def _fit_check(self):
        """内容超高时按 4% 逐级缩排，保持"一页读完"的书感（只缩不放，避免抖动）。"""
        try:
            if not self.sheet or self.sheet.height() <= 0:
                return
            avail = self.scroll.viewport().height()
            need = self.playout.sizeHint().height()
            floor = 0.78
            if need > avail + 6 and self.fit > floor:
                self.fit = max(floor, self.fit - 0.04)
                ch = self.book["chapters"][self.chapter_idx]
                self._build_page(ch, self.pages_meta[self.chapter_idx][self.page_idx])
        except Exception:
            pass

    # ---------------- 区块 ----------------
    def build_block(self, b):
        t = b.get("type")
        f = self.fit
        if t == "text":
            w = QFrame()
            w.setObjectName("blk")
            l = QVBoxLayout(w)
            l.setContentsMargins(0, 14, 0, 14)
            l.setSpacing(12)
            if b.get("title"):
                h = QLabel(b["title"])
                h.setObjectName("blk_title")
                h.setWordWrap(True)
                l.addWidget(h)
            for para in b.get("paras", []):
                pl = QLabel(mark(para, self.night))
                pl.setObjectName("para")
                pl.setWordWrap(True)
                pl.setTextFormat(Qt.RichText)
                l.addWidget(pl)
            return w

        if t == "kpi":
            w = QFrame()
            w.setObjectName("blk")
            g = QGridLayout(w)
            g.setContentsMargins(0, 8, 0, 8)
            g.setSpacing(10)
            items = b.get("items", [])
            cols = min(4, max(1, len(items)))
            for i, (val, lab) in enumerate(items):
                box = QFrame()
                box.setObjectName("kpi")
                bl = QVBoxLayout(box)
                bl.setContentsMargins(12, 10, 12, 10)
                bl.setSpacing(2)
                v = QLabel(str(val))
                v.setObjectName("kpi_v")
                lb = QLabel(lab)
                lb.setObjectName("kpi_l")
                lb.setWordWrap(True)
                bl.addWidget(v)
                bl.addWidget(lb)
                g.addWidget(box, i // cols, i % cols)
            return w

        if t == "chart":
            w = QFrame()
            w.setObjectName("blk")
            l = QVBoxLayout(w)
            l.setContentsMargins(0, 6, 0, 6)
            if b.get("kind") == "city_explorer" and self.gd:
                cw = CityExplorerWidget(self.gd)
            else:
                cw = ChartWidget(b.get("title", ""), b.get("kind", "line"),
                                 b.get("data", []), b.get("note", ""))
            cw.setMinimumHeight(int(292 * f))
            cw.setScale(self.scale)
            cw.setNight(self.night)
            l.addWidget(cw)
            self.charts.append(cw)
            return w

        if t == "image":
            w = QFrame()
            w.setObjectName("blk")
            l = QVBoxLayout(w)
            l.setContentsMargins(0, 6, 0, 6)
            img = QLabel()
            img.setAlignment(Qt.AlignCenter)
            pm = QPixmap(str(res_path("assets/" + b.get("path", ""))))
            if not pm.isNull():
                # 按 fit 缩排，保证"图 + 文"也能一页读完；诊断图为宽幅，限高更严
                max_w = int(860 * f)
                max_h = int(250 * f)
                pm = pm.scaled(max_w, max_h, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                img.setPixmap(pm)
            cap = QLabel(b.get("caption", ""))
            cap.setObjectName("cap")
            cap.setAlignment(Qt.AlignCenter)
            cap.setWordWrap(True)
            l.addWidget(img)
            l.addWidget(cap)
            return w

        if t == "theme":
            w = QFrame()
            w.setObjectName("themecard")
            l = QVBoxLayout(w)
            l.setContentsMargins(26, 18, 26, 18)
            l.setSpacing(8)
            tag = QLabel("✦　" + b.get("tag", "本章主题"))
            tag.setObjectName("themetag")
            quote = QLabel(b.get("quote", ""))
            quote.setObjectName("themequote")
            quote.setWordWrap(True)
            q = QLabel("❓　" + b.get("question", ""))
            q.setObjectName("themequestion")
            q.setWordWrap(True)
            l.addWidget(tag)
            l.addWidget(quote)
            l.addWidget(q)
            return w

        if t == "table":
            w = QFrame()
            w.setObjectName("blk")
            l = QVBoxLayout(w)
            l.setContentsMargins(0, 6, 0, 6)
            if b.get("title"):
                tt = QLabel(b["title"])
                tt.setObjectName("blk_title")
                tt.setWordWrap(True)
                l.addWidget(tt)
            rows = b.get("rows", [])
            headers = b.get("headers", [])
            tbl = QTableWidget(len(rows), len(headers))
            tbl.setHorizontalHeaderLabels(headers)
            tbl.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
            tbl.verticalHeader().setVisible(False)
            tbl.setEditTriggers(QAbstractItemView.NoEditTriggers)
            tbl.setAlternatingRowColors(True)
            tbl.setShowGrid(False)
            for r, row in enumerate(rows):
                for c, val in enumerate(row):
                    item = QTableWidgetItem(str(val))
                    item.setTextAlignment(Qt.AlignCenter)
                    tbl.setItem(r, c, item)
            tbl.verticalHeader().setDefaultSectionSize(26)
            tbl.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
            h = min(len(rows) * 27 + 34, int(440 * self.fit))
            tbl.setMaximumHeight(h)
            tbl.setMinimumHeight(h)
            l.addWidget(tbl)
            self.tables.append(tbl)
            return w

        if t == "doc":
            w = QFrame()
            w.setObjectName("docbox")
            l = QVBoxLayout(w)
            l.setContentsMargins(22, 16, 22, 16)
            l.setSpacing(6)
            head = QLabel(b.get("head", ""))
            head.setObjectName("dochead")
            head.setWordWrap(True)
            l.addWidget(head)
            line = QFrame()
            line.setObjectName("docline")
            line.setFixedHeight(1)
            l.addWidget(line)
            for para in b.get("paras", []):
                p = QLabel(mark(para, self.night))
                p.setObjectName("docpara")
                p.setWordWrap(True)
                p.setTextFormat(Qt.RichText)
                l.addWidget(p)
            return w

        if t == "voice":
            w = QFrame()
            w.setObjectName("voicebox")
            l = QVBoxLayout(w)
            l.setContentsMargins(20, 14, 20, 14)
            l.setSpacing(6)
            quote = QLabel(mark("「" + b.get("quote", "") + "」", self.night))
            quote.setObjectName("voicequote")
            quote.setWordWrap(True)
            quote.setTextFormat(Qt.RichText)
            who = QLabel(b.get("who", ""))
            who.setObjectName("voicewho")
            who.setAlignment(Qt.AlignRight)
            who.setWordWrap(True)
            l.addWidget(quote)
            l.addWidget(who)
            if b.get("note"):
                n = QLabel(b["note"])
                n.setObjectName("voicenote")
                n.setWordWrap(True)
                l.addWidget(n)
            return w

        if t == "decision":
            w = QFrame()
            w.setObjectName("blk")
            l = QVBoxLayout(w)
            l.setContentsMargins(0, 6, 0, 6)
            l.setSpacing(8)
            tt = QLabel("决策清单")
            tt.setObjectName("blk_title")
            l.addWidget(tt)
            for badge_txt, title, desc in b.get("items", []):
                row = QFrame()
                row.setObjectName("decrow")
                rl = QHBoxLayout(row)
                rl.setContentsMargins(12, 10, 12, 10)
                rl.setSpacing(10)
                badge = QLabel(badge_txt)
                badge.setObjectName("decbadge")
                badge.setFixedWidth(26)
                badge.setAlignment(Qt.AlignCenter)
                txt = QWidget()
                tl = QVBoxLayout(txt)
                tl.setContentsMargins(0, 0, 0, 0)
                tl.setSpacing(2)
                h = QLabel(title)
                h.setObjectName("dectitle")
                d = QLabel(desc)
                d.setObjectName("decdesc")
                d.setWordWrap(True)
                tl.addWidget(h)
                tl.addWidget(d)
                rl.addWidget(badge, 0, Qt.AlignTop)
                rl.addWidget(txt, 1)
                l.addWidget(row)
            return w

        if t == "algo":
            # 算法管线：输入 → 步骤 → 输出，用编号卡片呈现，可逐步追问
            w = QFrame()
            w.setObjectName("algobox")
            l = QVBoxLayout(w)
            l.setContentsMargins(12, 8, 12, 8)
            l.setSpacing(3)
            tt = QLabel("⚙　" + b.get("title", "算法链路"))
            tt.setObjectName("algohead")
            tt.setWordWrap(True)
            l.addWidget(tt)

            inp = "　→　".join(str(x) for x in b.get("inputs", []))
            il = QLabel("输入：" + inp)
            il.setObjectName("alio")
            il.setWordWrap(True)
            il.setTextFormat(Qt.RichText)
            l.addWidget(il)

            steps = list(b.get("steps", []))
            cols = 2 if len(steps) >= 5 else 1
            step_grid = QGridLayout()
            step_grid.setContentsMargins(0, 0, 0, 0)
            step_grid.setSpacing(5)
            for idx, (st_title, st_desc) in enumerate(steps, 1):
                row = QFrame()
                row.setObjectName("algostep")
                rl = QHBoxLayout(row)
                rl.setContentsMargins(7, 3, 7, 3)
                rl.setSpacing(8)
                num = QLabel(str(idx))
                num.setObjectName("algonum")
                num.setFixedWidth(24)
                num.setAlignment(Qt.AlignCenter)
                body = QWidget()
                bl = QVBoxLayout(body)
                bl.setContentsMargins(0, 0, 0, 0)
                bl.setSpacing(1)
                st = QLabel(st_title)
                st.setObjectName("algost")
                sd = QLabel(mark(st_desc, self.night))
                sd.setObjectName("algosd")
                sd.setWordWrap(True)
                sd.setTextFormat(Qt.RichText)
                bl.addWidget(st)
                bl.addWidget(sd)
                rl.addWidget(num, 0, Qt.AlignTop)
                rl.addWidget(body, 1)
                step_grid.addWidget(row, (idx - 1) // cols, (idx - 1) % cols)
            l.addLayout(step_grid)

            ol = QLabel("输出：" + str(b.get("output", "")))
            ol.setObjectName("alio")
            ol.setWordWrap(True)
            ol.setTextFormat(Qt.RichText)
            l.addWidget(ol)
            if b.get("note"):
                nl = QLabel("※ " + b["note"])
                nl.setObjectName("algonote")
                nl.setWordWrap(True)
                l.addWidget(nl)
            return w

        if t == "action":
            # 精准干预处方：触发 / 决策 / 措施 / 预期 / 复核
            w = QFrame()
            w.setObjectName("actionbox")
            l = QVBoxLayout(w)
            l.setContentsMargins(16, 12, 16, 12)
            l.setSpacing(5)
            head = QLabel("✚　精准干预处方")
            head.setObjectName("actionhead")
            l.addWidget(head)
            pairs = [
                ("触发条件", b.get("trigger", "")),
                ("算法决策", b.get("decision", "")),
                ("预期效果", b.get("expected", "")),
                ("复核指标", b.get("verify", "")),
            ]
            for k, v in pairs:
                if not v:
                    continue
                row = QLabel("【" + k + "】" + str(v))
                row.setObjectName("actionkv")
                row.setWordWrap(True)
                row.setTextFormat(Qt.RichText)
                row.setText(mark("【" + k + "】" + str(v), self.night))
                l.addWidget(row)
            if b.get("measures"):
                ml = QLabel("【落地措施】")
                ml.setObjectName("actionkv")
                l.addWidget(ml)
                for m in b["measures"]:
                    item = QLabel("　• " + str(m))
                    item.setObjectName("actionitem")
                    item.setWordWrap(True)
                    item.setText(mark("　• " + str(m), self.night))
                    item.setTextFormat(Qt.RichText)
                    l.addWidget(item)
            return w

        if t == "note":
            w = QFrame()
            w.setObjectName("notebox")
            l = QVBoxLayout(w)
            l.setContentsMargins(0, 4, 0, 4)
            l.setSpacing(0)
            btn = QToolButton()
            btn.setObjectName("notebtn")
            btn.setText("▸　" + b.get("title", "数据注记") + "（点开查看口径说明）")
            btn.setCheckable(True)
            btn.setCursor(Qt.PointingHandCursor)
            body = QFrame()
            body.setObjectName("notebody")
            bl = QVBoxLayout(body)
            bl.setContentsMargins(16, 8, 16, 12)
            bl.setSpacing(5)
            for para in b.get("paras", []):
                p = QLabel(mark("· " + para, self.night))
                p.setObjectName("notetxt")
                p.setWordWrap(True)
                p.setTextFormat(Qt.RichText)
                bl.addWidget(p)
            body.setVisible(False)

            def _toggle(checked, _btn=btn, _body=body):
                _body.setVisible(checked)
                _btn.setText(("▾　" if checked else "▸　") +
                             b.get("title", "数据注记") +
                             ("（收起）" if checked else "（点开查看口径说明）"))
                self.sound.play("tick", 0.35)

            btn.toggled.connect(_toggle)
            l.addWidget(btn)
            l.addWidget(body)
            return w

        if t == "closing":
            w = QFrame()
            w.setObjectName("closingbox")
            l = QVBoxLayout(w)
            l.setContentsMargins(30, 26, 30, 20)
            l.setSpacing(10)
            orn = QLabel("◆　◆　◆")
            orn.setObjectName("coverorn")
            orn.setAlignment(Qt.AlignCenter)
            nxt = QLabel(b.get("next", ""))
            nxt.setObjectName("closetitle")
            nxt.setAlignment(Qt.AlignCenter)
            nxt.setWordWrap(True)
            q = QLabel("❓ " + b.get("question", ""))
            q.setObjectName("closeq")
            q.setAlignment(Qt.AlignCenter)
            q.setWordWrap(True)
            hint = QLabel(b.get("hint", ""))
            hint.setObjectName("foottxt")
            hint.setAlignment(Qt.AlignCenter)
            l.addWidget(orn)
            l.addWidget(nxt)
            l.addWidget(q)
            l.addWidget(hint)
            return w
        return None

    # ---------------- 翻页 ----------------
    def _busy(self):
        """翻页动画期间忽略连击；用时间戳兜底，动画信号丢帧也不会锁死。"""
        import time
        if not self._turning:
            return False
        if time.time() - self._turn_ts > 0.42:
            self._turning = False
            return False
        return True

    def _play_turn(self, direction):
        if self.sound.enabled:
            self.sound.play("turn" if direction > 0 else "turn_back", 0.55)

    def turn_to(self, page_idx, direction=1):
        if not self.book or self._busy():
            return
        pages = self.pages_meta[self.chapter_idx]
        if not (0 <= page_idx < len(pages)) or page_idx == self.page_idx:
            return
        import time as _t
        self._turning = True
        self._turn_ts = _t.time()
        snap_old = self.stage.grab()
        self.page_idx = page_idx
        self.render()
        self.playout.activate()
        self._start_flip(snap_old, direction)
        QTimer.singleShot(700, self._release_turn)

    def _start_flip(self, snap_old, direction):
        # 让新页完成布局与首帧绘制后再快照，避免翻页动画露出空白页
        try:
            from PySide6.QtWidgets import QApplication
            QApplication.processEvents()
            self.sheet.repaint()
        except Exception:
            pass
        snap_new = self.stage.grab()
        self._play_turn(direction)
        self.flip.start(snap_old, snap_new, direction, self._flip_done)
        self._save()

    def _release_turn(self):
        self._turning = False

    def _flip_done(self):
        self._turning = False

    def next_page(self):
        if self._busy() or not self.book:
            return
        pages = self.pages_meta[self.chapter_idx]
        if self.page_idx < len(pages) - 1:
            self.turn_to(self.page_idx + 1, 1)
        elif self.chapter_idx < len(self.book["chapters"]) - 1:
            self._goto_chapter(self.chapter_idx + 1, 0, 1)

    def prev_page(self):
        if self._busy() or not self.book:
            return
        if self.page_idx > 0:
            self.turn_to(self.page_idx - 1, -1)
        elif self.chapter_idx > 0:
            prev = self.chapter_idx - 1
            self._goto_chapter(prev, len(self.pages_meta[prev]) - 1, -1)

    def _goto_chapter(self, ch_idx, page_idx, direction):
        import time as _t
        self._turning = True
        self._turn_ts = _t.time()
        snap_old = self.stage.grab()
        self.chapter_idx = ch_idx
        self.page_idx = page_idx
        self.render()
        self.playout.activate()
        if hasattr(self.main, "toc"):
            self.main.toc.load(self.book, ch_idx)
        self._start_flip(snap_old, direction)
        QTimer.singleShot(700, self._release_turn)

    def next_chapter(self):
        if self.chapter_idx < len(self.book["chapters"]) - 1:
            self._goto_chapter(self.chapter_idx + 1, 0, 1)
        else:
            self.sound.play("close", 0.5)

    def prev_chapter(self):
        if self.chapter_idx > 0:
            self._goto_chapter(self.chapter_idx - 1, 0, -1)

    def goto(self, idx):
        if 0 <= idx < len(self.book["chapters"]):
            self._goto_chapter(idx, 0, 1)

    # ---------------- 交互 ----------------
    def toggle_sound(self):
        self.sound.enabled = not self.sound.enabled
        self.btn_sound.setText("🔊 音效" if self.sound.enabled else "🔇 静音")
        if self.sound.enabled:
            self.sound.play("tick", 0.4)

    def toggle_bookmark(self):
        try:
            bm = self.pmgr.get_bm(self.book["id"])
        except Exception:
            bm = None
        cur = {"ch": self.chapter_idx, "pg": self.page_idx,
               "title": self.book["chapters"][self.chapter_idx]["title"],
               "page": self.page_idx + 1}
        if bm and bm.get("ch") == cur["ch"] and bm.get("pg") == cur["pg"]:
            try:
                self.pmgr.clear_bm(self.book["id"])
            except Exception:
                pass
            self.btn_bookmark.setText("🔖 书签")
            self.sound.play("tick", 0.3)
            return
        try:
            self.pmgr.set_bm(self.book["id"], cur)
        except Exception:
            pass
        self.btn_bookmark.setText(f"🔖 已存 · 第{cur['page']}页")
        self.sound.play("tick", 0.45)

    def font_up(self):
        self.scale = min(1.4, self.scale + 0.08)
        self.render()

    def font_down(self):
        self.scale = max(0.84, self.scale - 0.08)
        self.render()

    def toggle_night(self):
        self.night = not self.night
        self.btn_night.setText("☀ 日间" if self.night else "☾ 夜间")
        self.sheet.set_night(self.night)
        for c in self.charts:
            c.setNight(self.night)
        self.apply_theme()

    def show_floating_chart(self, spec):
        try:
            dlg = QDialog(self)
            dlg.setWindowTitle(spec.get("title", "图表"))
            dlg.resize(780, 470)
            dlg.setStyleSheet("QDialog{background:%s}" % ("#1e2733" if self.night else "#ffffff"))
            lay = QVBoxLayout(dlg)
            lay.setContentsMargins(16, 16, 16, 12)
            cw = ChartWidget(spec.get("title", ""), spec.get("kind", "line"),
                             spec.get("data", []), "来自 Agent 工具调用结果")
            cw.setNight(self.night)
            lay.addWidget(cw, 1)
            row = QHBoxLayout()
            row.addStretch(1)
            close = QPushButton("关闭")
            close.clicked.connect(dlg.accept)
            row.addWidget(close)
            lay.addLayout(row)
            self._float_dlgs = getattr(self, "_float_dlgs", []) + [dlg]
            dlg.show()
        except Exception:
            pass

    def keyPressEvent(self, e):
        k = e.key()
        if k in (Qt.Key_Right, Qt.Key_Down):
            self.next_page()
        elif k in (Qt.Key_Left, Qt.Key_Up):
            self.prev_page()
        elif k in (Qt.Key_Space, Qt.Key_PageDown):
            self.next_page()
        elif k == Qt.Key_PageUp:
            self.prev_page()
        elif k == Qt.Key_Home:
            self.goto(0)
        elif k == Qt.Key_End:
            self.goto(len(self.book["chapters"]) - 1)
        else:
            super().keyPressEvent(e)

    def wheelEvent(self, e):
        # 滚轮翻页（带 260ms 节流，避免一格滚过多页）
        import time
        now = time.time()
        if now - self._last_wheel < 0.26:
            return
        if abs(e.angleDelta().y()) >= 40:
            self._last_wheel = now
            if e.angleDelta().y() < 0:
                self.next_page()
            else:
                self.prev_page()
        else:
            super().wheelEvent(e)

    # ---------------- 样式 ----------------
    def apply_theme(self):
        psz = int(round(19 * self.scale * self.fit))
        bsz = int(round(19 * self.scale * self.fit))
        tsz = int(round(24 * self.scale * self.fit))
        csz = int(round(35 * self.scale * self.fit))
        if self.night:
            qss = f"""
            QWidget#desk{{background:qlineargradient(x1:0,y1:0,x2:0,y2:1,stop:0 #141c24,stop:1 #0c1218);}}
            QFrame#bookframe{{background:#101820;border:1px solid #24303c;border-radius:3px;}}
            QFrame#spine{{background:qlineargradient(x1:0,y1:0,x2:1,y2:0,stop:0 #1b2a22,stop:0.5 #24402f,stop:1 #16211b);border-right:1px solid #0c1410;}}
            QLabel#spinelbl{{color:#8fbfa3;font-size:12px;letter-spacing:6px;font-family:"Times New Roman","KaiTi","楷体","Microsoft YaHei",serif;}}
            QFrame#stage{{background:transparent;}}
            QScrollArea{{background:transparent;border:none;}}
            QScrollArea > QWidget > QWidget{{background:transparent;}}
            QLabel#pagekick{{color:#7b8c9c;font-size:11px;letter-spacing:1px;font-family:"KaiTi","楷体","Microsoft YaHei";}}
            QFrame#pagerule{{background:#2c3a48;}}
            QLabel#pagetitle{{color:#f2f7fb;font-size:{tsz}px;font-weight:800;font-family:"KaiTi","楷体","Microsoft YaHei";}}
            QLabel#pagenum{{color:#2f4a58;font-size:{int(tsz*1.55)}px;font-weight:800;font-family:"Times New Roman",Georgia,serif;}}
            QLabel#pagesub{{color:#7f8fa0;font-size:11px;letter-spacing:1px;}}
            QLabel#blk_title{{color:#7fe0b0;font-size:{bsz}px;font-weight:700;font-family:"KaiTi","楷体","Microsoft YaHei";}}
            QLabel#para{{color:#d3dde7;font-size:{psz}px;line-height:214%;font-family:"Times New Roman","KaiTi","楷体","STKaiti",serif;}}
            QLabel#cap{{color:#7e8fa0;font-size:11px;}}
            QFrame#kpi{{background:#1e2a36;border:1px solid #2f3f4f;border-radius:10px;}}
            QLabel#kpi_v{{color:#7fe0b0;font-size:{int(psz*1.5)}px;font-weight:800;font-family:"Times New Roman",Georgia,serif;}}
            QLabel#kpi_l{{color:#93a4b5;font-size:11px;}}
            QFrame#themecard{{background:#1d2833;border:1px solid #35506a;border-left:5px solid #5fd39a;border-radius:12px;margin:8px 0;}}
            QLabel#themetag{{color:#5fd39a;font-size:12px;font-weight:800;letter-spacing:3px;}}
            QLabel#themequote{{color:#eef7ff;font-size:{int(psz*1.28)}px;font-weight:600;line-height:172%;font-family:"Times New Roman","KaiTi","楷体","STKaiti",serif;}}
            QLabel#themequestion{{color:#9fc6e6;font-size:{psz}px;line-height:166%;}}
            QFrame#docbox{{background:#1c2530;border:1px solid #33414f;border-left:4px solid #b23b2e;border-radius:4px;}}
            QLabel#dochead{{color:#e0c9a6;font-size:12px;font-weight:700;font-family:"Times New Roman","KaiTi","楷体",serif;}}
            QFrame#docline{{background:#33414f;}}
            QLabel#docpara{{color:#cbd6e1;font-size:{psz}px;line-height:180%;font-family:"Times New Roman","KaiTi","楷体","STKaiti",serif;}}
            QFrame#voicebox{{background:#1b2632;border-left:3px solid #5f7fa8;border-radius:4px;}}
            QLabel#voicequote{{color:#e6eef7;font-size:{int(psz*1.15)}px;font-family:"Times New Roman","KaiTi","楷体","STKaiti",serif;line-height:176%;}}
            QLabel#voicewho{{color:#8fa0b2;font-size:11px;}}
            QLabel#voicenote{{color:#6f7f8f;font-size:10px;}}
            QFrame#algobox{{background:#16222e;border:1px solid #2b4358;border-left:5px solid #5fd39a;border-radius:10px;margin:6px 0;}}
            QLabel#algohead{{color:#7fe0b0;font-size:{bsz}px;font-weight:800;}}
            QLabel#alio{{color:#bcd3e4;font-size:{int(psz*0.92)}px;line-height:168%;font-family:"Times New Roman","KaiTi","楷体",serif;}}
            QFrame#algostep{{background:#1b2a38;border:1px solid #2c4152;border-radius:7px;}}
            QLabel#algonum{{color:#0f1a24;background:#5fd39a;border-radius:11px;font-size:12px;font-weight:800;font-family:"Times New Roman",serif;}}
            QLabel#algost{{color:#e2f3ea;font-size:{int(psz*0.96)}px;font-weight:700;}}
            QLabel#algosd{{color:#a9bfcf;font-size:{int(psz*0.88)}px;line-height:164%;}}
            QLabel#algonote{{color:#8fa6b8;font-size:10px;line-height:160%;}}
            QFrame#actionbox{{background:#2a2418;border:1px solid #4a3f24;border-left:5px solid #e0b040;border-radius:10px;margin:6px 0;}}
            QLabel#actionhead{{color:#f0cf80;font-size:{bsz}px;font-weight:800;}}
            QLabel#actionkv{{color:#e8d9b4;font-size:{int(psz*0.92)}px;line-height:168%;font-family:"Times New Roman","KaiTi","楷体",serif;}}
            QLabel#actionitem{{color:#cbbb92;font-size:{int(psz*0.88)}px;line-height:164%;font-family:"Times New Roman","KaiTi","楷体",serif;}}
            QFrame#decrow{{background:#1d2733;border:1px solid #2e3c4a;border-radius:8px;}}
            QLabel#decbadge{{font-size:15px;}}
            QLabel#dectitle{{color:#e8f1fa;font-size:{int(psz*0.98)}px;font-weight:700;}}
            QLabel#decdesc{{color:#a9b8c8;font-size:{int(psz*0.9)}px;}}
            QToolButton#notebtn{{color:#8fb8dc;background:transparent;border:none;font-size:{int(psz*0.92)}px;text-align:left;padding:6px 0;}}
            QFrame#notebody{{background:#1a2430;border-left:3px solid #4a6b8a;border-radius:3px;}}
            QLabel#notetxt{{color:#9fb0c0;font-size:{int(psz*0.88)}px;line-height:170%;}}
            QFrame#cover{{background:transparent;}}
            QLabel#cover3d{{border:none;margin:0 0 6px 0;}}
            QLabel#coverkick{{color:#8fa0b2;font-size:12px;letter-spacing:5px;font-family:"KaiTi","楷体","Microsoft YaHei";}}
            QLabel#covertitle{{color:#f4f9ff;font-size:{int(csz*1.05)}px;font-weight:800;font-family:"Times New Roman","STKaiti","KaiTi","楷体",serif;}}
            QLabel#coverorn{{color:#5fd39a;font-size:13px;}}
            QLabel#coverepi{{color:#c9d8e6;font-size:{int(psz*1.2)}px;font-family:"Times New Roman","KaiTi","楷体","STKaiti",serif;}}
            QLabel#coverlead{{color:#9dafc0;font-size:{psz}px;line-height:184%;font-family:"Times New Roman","KaiTi","楷体",serif;}}
            QFrame#closingbox{{background:transparent;}}
            QLabel#closetitle{{color:#7fe0b0;font-size:{int(tsz*1.05)}px;font-weight:800;}}
            QLabel#closeq{{color:#cdd9e5;font-size:{int(psz*1.12)}px;font-family:"Times New Roman","KaiTi","楷体","STKaiti",serif;line-height:180%;}}
            QLabel#foottxt{{color:#6d7d8d;font-size:10px;}}
            QFrame#ornline{{background:#2c3a48;}}
            QLabel#ornmark{{color:#4a5f70;font-size:9px;padding:0 8px;}}
            QLabel#srcnote{{color:#6a7a8a;font-size:9px;padding-top:4px;}}
            QLabel#footnum{{color:#8fa0b2;font-size:11px;}}
            QFrame#pagefoot{{background:transparent;}}
            QTableWidget{{background:#1b2634;color:#d3dde7;gridline-color:#2e3d4d;alternate-background-color:#202c3a;border:1px solid #2e3d4d;border-radius:4px;font-size:{int(psz*0.82)}px;}}
            QHeaderView::section{{background:#243141;color:#aebdcc;border:none;padding:4px;font-size:{int(psz*0.8)}px;}}
            QFrame#topbar{{background:#141c24;border-bottom:1px solid #25313d;}}
            QFrame#bottombar{{background:#141c24;border-top:1px solid #25313d;}}
            QLabel#booktitle{{color:#dbe5ef;font-size:13px;font-weight:600;}}
            QLabel#prog{{color:#8fa0b2;font-size:12px;}}
            QLabel#pagelbl{{color:#8fa0b2;font-size:12px;}}
            QPushButton#pagebtn{{background:#1f9d55;color:#fff;border:none;border-radius:7px;padding:6px 16px;font-weight:600;}}
            QPushButton#pagebtn:disabled{{background:#2c3a48;color:#64748b;}}
            QPushButton#pagebtn2{{background:transparent;color:#aebdcc;border:1px solid #334252;border-radius:7px;padding:6px 12px;}}
            QPushButton#pagebtn2:disabled{{color:#4a5a68;border-color:#243040;}}
            QPushButton#tbbtn2{{background:transparent;color:#aebdcc;border:1px solid #334252;border-radius:6px;padding:4px 9px;}}
            QToolButton#tbbtn{{background:transparent;color:#aebdcc;border:none;font-size:12px;}}
            QSpinBox#pagespin{{background:#1d2733;color:#dbe5ef;border:1px solid #334252;border-radius:5px;padding:2px;}}
            """
        else:
            qss = f"""
            QWidget#desk{{background:qlineargradient(x1:0,y1:0,x2:0,y2:1,stop:0 #24382f,stop:1 #16241d);}}
            QFrame#bookframe{{background:#f6f2e8;border:1px solid #0f1a14;border-radius:3px;}}
            QFrame#spine{{background:qlineargradient(x1:0,y1:0,x2:1,y2:0,stop:0 #6d2b22,stop:0.45 #8f3a2c,stop:1 #5c241d);border-right:1px solid #3f1611;}}
            QLabel#spinelbl{{color:#e8c9a8;font-size:11px;letter-spacing:6px;font-family:"Times New Roman","KaiTi","楷体","Microsoft YaHei",serif;}}
            QFrame#stage{{background:transparent;}}
            QScrollArea{{background:transparent;border:none;}}
            QScrollArea > QWidget > QWidget{{background:transparent;}}
            QLabel#pagekick{{color:#8a7a5e;font-size:11px;letter-spacing:1px;font-family:"KaiTi","楷体","Microsoft YaHei";}}
            QFrame#pagerule{{background:#d8cdb4;}}
            QLabel#pagetitle{{color:#1d2a22;font-size:{tsz}px;font-weight:800;font-family:"KaiTi","楷体","Microsoft YaHei";}}
            QLabel#pagenum{{color:#d8cdb4;font-size:{int(tsz*1.55)}px;font-weight:800;font-family:"Times New Roman",Georgia,serif;}}
            QLabel#pagesub{{color:#8a7a5e;font-size:11px;letter-spacing:1px;}}
            QLabel#blk_title{{color:#1b6b46;font-size:{bsz}px;font-weight:700;font-family:"KaiTi","楷体","Microsoft YaHei";}}
            QLabel#para{{color:#2f3a33;font-size:{psz}px;line-height:214%;font-family:"Times New Roman","KaiTi","楷体","STKaiti",serif;}}
            QLabel#cap{{color:#8d8168;font-size:11px;}}
            QFrame#kpi{{background:#f2efe2;border:1px solid #ded4bb;border-radius:9px;}}
            QLabel#kpi_v{{color:#a3412f;font-size:{int(psz*1.5)}px;font-weight:800;font-family:"Times New Roman",Georgia,serif;}}
            QLabel#kpi_l{{color:#6d6350;font-size:11px;}}
            QFrame#themecard{{background:#fffdf3;border:1px solid #e3d8bb;border-left:5px solid #b23b2e;border-radius:10px;margin:8px 0;}}
            QLabel#themetag{{color:#b23b2e;font-size:12px;font-weight:800;letter-spacing:3px;}}
            QLabel#themequote{{color:#2b2518;font-size:{int(psz*1.28)}px;font-weight:600;line-height:172%;font-family:"Times New Roman","KaiTi","楷体","STKaiti",serif;}}
            QLabel#themequestion{{color:#7a6c4a;font-size:{psz}px;line-height:166%;}}
            QFrame#docbox{{background:#fbf7ea;border:1px solid #ded2b4;border-left:4px solid #b23b2e;border-radius:3px;}}
            QLabel#dochead{{color:#7a4a2a;font-size:12px;font-weight:700;font-family:"Times New Roman","KaiTi","楷体",serif;}}
            QFrame#docline{{background:#ded2b4;}}
            QLabel#docpara{{color:#3a3226;font-size:{psz}px;line-height:180%;font-family:"Times New Roman","KaiTi","楷体","STKaiti",serif;}}
            QFrame#voicebox{{background:#f7f4e8;border-left:3px solid #8a9b83;border-radius:3px;}}
            QLabel#voicequote{{color:#2c3a2f;font-size:{int(psz*1.15)}px;font-family:"Times New Roman","KaiTi","楷体","STKaiti",serif;line-height:176%;}}
            QLabel#voicewho{{color:#7d7361;font-size:11px;}}
            QLabel#voicenote{{color:#9a917c;font-size:10px;}}
            QFrame#algobox{{background:#eef6f1;border:1px solid #c4dfcd;border-left:5px solid #1b8a58;border-radius:10px;margin:6px 0;}}
            QLabel#algohead{{color:#146b45;font-size:{bsz}px;font-weight:800;}}
            QLabel#alio{{color:#37514a;font-size:{int(psz*0.92)}px;line-height:168%;font-family:"Times New Roman","KaiTi","楷体",serif;}}
            QFrame#algostep{{background:#f8fcf9;border:1px solid #d7e8dc;border-radius:7px;}}
            QLabel#algonum{{color:#ffffff;background:#1b8a58;border-radius:11px;font-size:12px;font-weight:800;font-family:"Times New Roman",serif;}}
            QLabel#algost{{color:#1c4b36;font-size:{int(psz*0.96)}px;font-weight:700;}}
            QLabel#algosd{{color:#405c50;font-size:{int(psz*0.88)}px;line-height:164%;}}
            QLabel#algonote{{color:#7b8c81;font-size:10px;line-height:160%;}}
            QFrame#actionbox{{background:#fdf7e8;border:1px solid #e8d9b0;border-left:5px solid #b8860b;border-radius:10px;margin:6px 0;}}
            QLabel#actionhead{{color:#8a6408;font-size:{bsz}px;font-weight:800;}}
            QLabel#actionkv{{color:#5a4a25;font-size:{int(psz*0.92)}px;line-height:168%;font-family:"Times New Roman","KaiTi","楷体",serif;}}
            QLabel#actionitem{{color:#6a5834;font-size:{int(psz*0.88)}px;line-height:164%;font-family:"Times New Roman","KaiTi","楷体",serif;}}
            QFrame#decrow{{background:#faf8ee;border:1px solid #e2dac4;border-radius:7px;}}
            QLabel#decbadge{{font-size:15px;}}
            QLabel#dectitle{{color:#2b362d;font-size:{int(psz*0.98)}px;font-weight:700;}}
            QLabel#decdesc{{color:#5d655c;font-size:{int(psz*0.9)}px;}}
            QToolButton#notebtn{{color:#3d6b52;background:transparent;border:none;font-size:{int(psz*0.92)}px;text-align:left;padding:6px 0;}}
            QFrame#notebody{{background:#f4f1e4;border-left:3px solid #a8b49a;border-radius:3px;}}
            QLabel#notetxt{{color:#5b6355;font-size:{int(psz*0.88)}px;line-height:170%;}}
            QLabel#cover3d{{border:none;margin:0 0 6px 0;}}
            QLabel#coverkick{{color:#8a7a5e;font-size:12px;letter-spacing:5px;font-family:"KaiTi","楷体","Microsoft YaHei";}}
            QLabel#covertitle{{color:#22271f;font-size:{int(csz*1.05)}px;font-weight:800;font-family:"Times New Roman","STKaiti","KaiTi","楷体",serif;}}
            QLabel#coverorn{{color:#b23b2e;font-size:13px;}}
            QLabel#coverepi{{color:#4a4234;font-size:{int(psz*1.2)}px;font-family:"Times New Roman","KaiTi","楷体","STKaiti",serif;}}
            QLabel#coverlead{{color:#5b5a4c;font-size:{psz}px;line-height:184%;font-family:"Times New Roman","KaiTi","楷体",serif;}}
            QLabel#closetitle{{color:#1b6b46;font-size:{int(tsz*1.05)}px;font-weight:800;}}
            QLabel#closeq{{color:#3a443b;font-size:{int(psz*1.12)}px;font-family:"Times New Roman","KaiTi","楷体","STKaiti",serif;line-height:180%;}}
            QLabel#foottxt{{color:#8d8168;font-size:10px;}}
            QFrame#ornline{{background:#ded2b4;}}
            QLabel#ornmark{{color:#b09b74;font-size:9px;padding:0 8px;}}
            QLabel#srcnote{{color:#9a8f76;font-size:9px;padding-top:4px;}}
            QLabel#footnum{{color:#7a6c4a;font-size:11px;}}
            QTableWidget{{background:#fdfbf3;color:#2f3a33;gridline-color:#e2dac4;alternate-background-color:#f7f4e8;border:1px solid #e2dac4;font-size:{int(psz*0.82)}px;}}
            QHeaderView::section{{background:#eee8d6;color:#4c4638;border:none;padding:4px;font-size:{int(psz*0.8)}px;}}
            QFrame#topbar{{background:#ffffff;border-bottom:1px solid #e6e2d5;}}
            QFrame#bottombar{{background:#ffffff;border-top:1px solid #e6e2d5;}}
            QLabel#booktitle{{color:#2b3a31;font-size:13px;font-weight:600;}}
            QLabel#prog{{color:#7d8a80;font-size:12px;}}
            QLabel#pagelbl{{color:#7d8a80;font-size:12px;}}
            QPushButton#pagebtn{{background:#1f9d55;color:#fff;border:none;border-radius:7px;padding:6px 16px;font-weight:600;}}
            QPushButton#pagebtn:disabled{{background:#e2e8e3;color:#a4aea6;}}
            QPushButton#pagebtn2{{background:transparent;color:#4a5a50;border:1px solid #d9e2dc;border-radius:7px;padding:6px 12px;}}
            QPushButton#pagebtn2:disabled{{color:#b6bfb8;border-color:#e8ece9;}}
            QPushButton#tbbtn2{{background:transparent;color:#4a5a50;border:1px solid #d9e2dc;border-radius:6px;padding:4px 9px;}}
            QToolButton#tbbtn{{background:transparent;color:#4a5a50;border:none;font-size:12px;}}
            QSpinBox#pagespin{{background:#fbfaf6;color:#2b3a31;border:1px solid #d9e2dc;border-radius:5px;padding:2px;}}
            """
        self.setStyleSheet(qss)
