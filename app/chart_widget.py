# -*- coding: utf-8 -*-
"""轻量自绘图表组件（折线/柱状/面积/多线），不依赖 WebEngine。"""
from PySide6.QtWidgets import QWidget
from PySide6.QtCore import Qt, QRectF, QPointF
from PySide6.QtGui import QPainter, QColor, QPen, QBrush, QFont, QLinearGradient

C_LINE = ["#1f9d55", "#e07b39", "#2f89cf", "#9b6bb5", "#c0392b"]
C_BG = "#ffffff"
C_GRID = "#e8ecef"
C_AXIS = "#8a949e"
C_TEXT = "#4a5560"


class ChartWidget(QWidget):
    def __init__(self, title, kind, data, note="", parent=None):
        super().__init__(parent)
        self.title = title
        self.kind = kind
        self.data = data
        self.note = note
        self.setMinimumHeight(300)
        self.night = False
        self.scale = 1.0

    def setNight(self, v):
        self.night = v
        self.update()

    def setScale(self, s):
        self.scale = s
        self.update()

    def _colors(self):
        if self.night:
            return "#1e2733", "#2f3a47", "#8b98a6", "#c8d2dc"
        return C_BG, C_GRID, C_AXIS, C_TEXT

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        bg, grid, axis, text = self._colors()
        p.fillRect(self.rect(), QColor(bg))
        w, h = self.width(), self.height()
        pad_l, pad_r, pad_t, pad_b = 62, 22, 46, 46
        f = QFont()
        base = max(10, int(11 * self.scale))
        f.setPointSize(base)
        p.setFont(f)

        # 标题
        p.setPen(QColor("#1f9d55" if not self.night else "#5fd39a"))
        fb = QFont(f); fb.setBold(True); fb.setPointSize(base + 2)
        p.setFont(fb)
        p.drawText(QRectF(10, 6, w - 20, 26), Qt.AlignLeft | Qt.AlignVCenter, self.title)
        p.setFont(f)

        plot = QRectF(pad_l, pad_t, w - pad_l - pad_r, h - pad_t - pad_b)
        if plot.width() < 40 or plot.height() < 40:
            p.end(); return

        try:
            if self.kind == "bar":
                self._draw_bar(p, plot, grid, axis, text)
            elif self.kind == "line":
                self._draw_line(p, plot, grid, axis, text, area=False)
            elif self.kind == "area":
                self._draw_line(p, plot, grid, axis, text, area=True)
            elif self.kind == "multi":
                self._draw_multi(p, plot, grid, axis, text)
            else:
                self._draw_line(p, plot, grid, axis, text)
        except Exception as e:
            p.setPen(QColor("#c0392b"))
            p.drawText(plot, Qt.AlignCenter, f"图表渲染异常: {e}")

        # 注脚
        if self.note:
            p.setPen(QColor(axis))
            fn = QFont(f); fn.setPointSize(max(8, base - 2)); p.setFont(fn)
            p.drawText(QRectF(10, h - 18, w - 20, 16), Qt.AlignLeft | Qt.AlignVCenter, "注：" + self.note)
        p.end()

    def _data_pairs(self):
        if isinstance(self.data, list):
            if not self.data:
                return [], []
            first = self.data[0]
            if isinstance(first, list) and len(first) >= 2:
                labels = [str(x[0]) for x in self.data]
                vals = [float(x[1]) if x[1] is not None else 0.0 for x in self.data]
                return labels, vals
        return [], []

    def _nice_range(self, vals):
        vmin, vmax = min(vals), max(vals)
        if vmin == vmax:
            vmin -= 1; vmax += 1
        rng = vmax - vmin
        step = 10 ** (len(str(int(rng))) - 1) if rng > 0 else 1
        if rng / step > 10: step *= 5
        elif rng / step > 5: step *= 2
        lo = int(vmin // step) * step
        hi = int(vmax // step + 1) * step
        return lo, hi

    def _draw_grid(self, p, plot, lo, hi, grid, axis, text, rows=4):
        p.setPen(QPen(QColor(grid), 1))
        for i in range(rows + 1):
            y = plot.bottom() - plot.height() * i / rows
            p.drawLine(QPointF(plot.left(), y), QPointF(plot.right(), y))
            val = lo + (hi - lo) * i / rows
            p.setPen(QColor(axis))
            lbl = f"{val:,.0f}" if abs(val) >= 100 else f"{val:.1f}"
            p.drawText(QRectF(4, y - 9, plot.left() - 8, 18), Qt.AlignRight | Qt.AlignVCenter, lbl)
            p.setPen(QPen(QColor(grid), 1))

    def _draw_bar(self, p, plot, grid, axis, text):
        labels, vals = self._data_pairs()
        if not vals: return
        lo, hi = self._nice_range(vals)
        self._draw_grid(p, plot, lo, hi, grid, axis, text)
        n = len(vals)
        slot = plot.width() / n
        bw = max(4, slot * 0.62)
        base = plot.bottom()
        for i, v in enumerate(vals):
            x = plot.left() + slot * i + (slot - bw) / 2
            hh = (v - lo) / (hi - lo) * plot.height() if hi > lo else 0
            color = QColor(C_LINE[i % len(C_LINE)])
            grad = QLinearGradient(x, base - hh, x, base)
            grad.setColorAt(0, color.lighter(115))
            grad.setColorAt(1, color)
            p.setPen(Qt.NoPen); p.setBrush(QBrush(grad))
            p.drawRect(QRectF(x, base - hh, bw, hh))
            p.setPen(QColor(axis))
            f = p.font(); small = QFont(f); small.setPointSize(max(7, f.pointSize() - 2)); p.setFont(small)
            lab = labels[i] if len(labels[i]) <= 6 else labels[i][:5] + "…"
            p.drawText(QRectF(plot.left() + slot * i - slot/2, base + 4, slot, 18), Qt.AlignCenter, lab)
            p.setFont(f)

    def _draw_line(self, p, plot, grid, axis, text, area=False):
        labels, vals = self._data_pairs()
        if not vals: return
        lo, hi = self._nice_range(vals)
        self._draw_grid(p, plot, lo, hi, grid, axis, text)
        n = len(vals)
        step = plot.width() / max(1, n - 1)
        pts = [QPointF(plot.left() + step * i,
                       plot.bottom() - (v - lo) / (hi - lo) * plot.height()) for i, v in enumerate(vals)]
        if area and len(pts) >= 2:
            poly = [pts[0]] + pts + [QPointF(pts[-1].x(), plot.bottom()), QPointF(pts[0].x(), plot.bottom())]
            from PySide6.QtGui import QPolygonF
            grad = QLinearGradient(plot.topLeft(), plot.bottomLeft())
            grad.setColorAt(0, QColor(31, 157, 85, 120))
            grad.setColorAt(1, QColor(31, 157, 85, 12))
            p.setPen(Qt.NoPen); p.setBrush(QBrush(grad))
            p.drawPolygon(QPolygonF(poly))
        color = QColor(C_LINE[0])
        p.setPen(QPen(color, 2.4))
        p.setBrush(Qt.NoBrush)
        for i in range(1, len(pts)):
            p.drawLine(pts[i-1], pts[i])
        p.setBrush(QBrush(color))
        for pt in pts:
            p.drawEllipse(pt, 2.4, 2.4)
        # X 标签（最多 8 个）
        stride = max(1, n // 8)
        f = p.font(); small = QFont(f); small.setPointSize(max(7, f.pointSize() - 2)); p.setFont(small)
        for i in range(0, n, stride):
            p.setPen(QColor(axis))
            p.drawText(QRectF(pts[i].x() - 28, plot.bottom() + 4, 56, 18), Qt.AlignCenter, labels[i])
        p.setFont(f)

    def _draw_multi(self, p, plot, grid, axis, text):
        d = self.data
        labels = d.get("labels", [])
        series = d.get("series", [])
        allv = [v for s in series for v in s.get("data", []) if v is not None]
        if not allv: return
        lo, hi = self._nice_range(allv)
        self._draw_grid(p, plot, lo, hi, grid, axis, text)
        n = len(labels)
        step = plot.width() / max(1, n - 1)
        for si, s in enumerate(series):
            vals = s.get("data", [])
            pts = [QPointF(plot.left() + step * i,
                           plot.bottom() - (v - lo) / (hi - lo) * plot.height())
                   for i, v in enumerate(vals) if v is not None]
            color = QColor(C_LINE[si % len(C_LINE)])
            p.setPen(QPen(color, 2.2)); p.setBrush(Qt.NoBrush)
            for i in range(1, len(pts)):
                p.drawLine(pts[i-1], pts[i])
            # 图例
            p.setBrush(QBrush(color)); p.setPen(Qt.NoPen)
            lx = plot.left() + 8 + si * 150
            p.drawRect(QRectF(lx, plot.top() + 4, 10, 10))
            p.setPen(QColor(text))
            p.drawText(QRectF(lx + 14, plot.top() + 2, 130, 16), Qt.AlignLeft | Qt.AlignVCenter, s.get("name", ""))
        stride = max(1, n // 8)
        f = p.font(); small = QFont(f); small.setPointSize(max(7, f.pointSize() - 2)); p.setFont(small)
        for i in range(0, n, stride):
            p.setPen(QColor(axis))
            x = plot.left() + step * i
            p.drawText(QRectF(x - 28, plot.bottom() + 4, 56, 18), Qt.AlignCenter, labels[i])
        p.setFont(f)


class CityExplorerWidget(QWidget):
    """广东21市交互探索器：下拉选择城市 + 指标，实时重绘20年曲线。"""
    from PySide6.QtWidgets import QComboBox

    METRICS = [
        ("gdp_wan", "GDP(亿元)", 1 / 10000),
        ("agri_share", "第一产业占比(%)", 1),
        ("agri_emp_share", "一产就业比重(%)", 1),
        ("pop", "年末总人口(万人)", 1),
        ("gdp_pc", "人均GDP(元)", 1),
        ("ind2_share", "第二产业占比(%)", 1),
        ("ind3_share", "第三产业占比(%)", 1),
    ]

    def __init__(self, gd_data, parent=None):
        super().__init__(parent)
        self.gd = gd_data
        self.night = False
        self.scale = 1.0
        self.setMinimumHeight(420)

        from PySide6.QtWidgets import QComboBox, QHBoxLayout, QVBoxLayout, QLabel
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        top = QHBoxLayout()
        self.city_cb = QComboBox()
        self.metric_cb = QComboBox()
        for c in sorted(self.gd["cities"].keys()):
            self.city_cb.addItem(c)
        for key, label, _ in self.METRICS:
            self.metric_cb.addItem(label)
        self.city_cb.currentTextChanged.connect(self.update)
        self.metric_cb.currentIndexChanged.connect(self.update)
        top.addWidget(QLabel("城市：")); top.addWidget(self.city_cb, 1)
        top.addSpacing(10)
        top.addWidget(QLabel("指标：")); top.addWidget(self.metric_cb, 1)
        lay.addLayout(top)

        self.plot = _MiniPlot(self)
        lay.addWidget(self.plot, 1)
        self.city_cb.setCurrentText("广州市")

    def setNight(self, v):
        self.night = v
        self.plot.night = v
        self.plot.update()

    def setScale(self, s):
        self.scale = s
        self.plot.scale = s
        self.plot.update()

    def update(self, *args):
        city = self.city_cb.currentText()
        key, label, factor = self.METRICS[self.metric_cb.currentIndex()]
        s = self.gd["cities"].get(city, {}).get("series", [])
        pairs = [[r["year"], r[key] * factor] for r in s if r.get(key) is not None]
        self.plot.title = f"{city} · {label}（1999–2018）"
        self.plot.data = pairs
        self.plot.update()


class _MiniPlot(QWidget):
    def __init__(self, parent):
        super().__init__(parent)
        self.title = ""
        self.data = []
        self.night = False
        self.scale = 1.0
        self.setMinimumHeight(360)

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        bg = "#1e2733" if self.night else "#ffffff"
        grid = "#2f3a47" if self.night else "#e8ecef"
        axis = "#8b98a6" if self.night else "#8a949e"
        text = "#c8d2dc" if self.night else "#4a5560"
        p.fillRect(self.rect(), QColor(bg))
        w, h = self.width(), self.height()
        pad = QRectF(58, 40, w - 80, h - 80)
        f = QFont(); f.setPointSize(max(10, int(11 * self.scale))); p.setFont(f)
        p.setPen(QColor("#5fd39a" if self.night else "#1f9d55"))
        fb = QFont(f); fb.setBold(True); fb.setPointSize(f.pointSize() + 2); p.setFont(fb)
        p.drawText(QRectF(8, 4, w - 16, 28), Qt.AlignCenter, self.title)
        p.setFont(f)
        vals = [v for _, v in self.data]
        if not vals or pad.width() < 40 or pad.height() < 40:
            p.end(); return
        lo, hi = min(vals), max(vals)
        if lo == hi: lo -= 1; hi += 1
        rng = hi - lo
        p.setPen(QPen(QColor(grid), 1))
        for i in range(5):
            y = pad.bottom() - pad.height() * i / 4
            p.drawLine(QPointF(pad.left(), y), QPointF(pad.right(), y))
            val = lo + rng * i / 4
            p.setPen(QColor(axis))
            lbl = f"{val:,.0f}" if abs(val) >= 100 else f"{val:.2f}"
            p.drawText(QRectF(2, y - 9, pad.left() - 6, 18), Qt.AlignRight | Qt.AlignVCenter, lbl)
            p.setPen(QPen(QColor(grid), 1))
        n = len(self.data)
        step = pad.width() / max(1, n - 1)
        pts = [QPointF(pad.left() + step * i, pad.bottom() - (v - lo) / rng * pad.height())
               for i, (_, v) in enumerate(self.data)]
        p.setPen(QPen(QColor("#1f9d55"), 2.4)); p.setBrush(Qt.NoBrush)
        for i in range(1, len(pts)):
            p.drawLine(pts[i-1], pts[i])
        p.setBrush(QBrush(QColor("#1f9d55")))
        for pt in pts: p.drawEllipse(pt, 2.2, 2.2)
        sf = QFont(f); sf.setPointSize(max(7, f.pointSize() - 2)); p.setFont(sf)
        for i in range(0, n, 4):
            p.setPen(QColor(axis))
            p.drawText(QRectF(pts[i].x() - 24, pad.bottom() + 4, 48, 18),
                       Qt.AlignCenter, str(self.data[i][0]))
        p.end()
