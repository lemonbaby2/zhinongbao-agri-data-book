# -*- coding: utf-8 -*-
"""决策 Agent 对话界面：气泡对话、工具步骤、快捷提问、大模型配置。"""
import html
import re
import threading

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import QFont, QPixmap, QColor, QPainter, QPainterPath
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton,
    QScrollArea, QFrame, QDialog, QFormLayout, QComboBox, QTextBrowser,
    QSizePolicy, QFileDialog,
)

from agent import Agent, DataHub, load_llm_conf, save_llm_conf, state_dir

CSS = """
#agentRoot { background: #f4f8f5; }
#agentHead { background: qlineargradient(x1:0,y1:0,x2:1,y2:1,
             stop:0 #0f7a44, stop:0.55 #12a150, stop:1 #0b5b34); }
#agentHead QLabel { color: #ffffff; background: transparent; }
#agentTitle { font-size: 21px; font-weight: 700; }
#agentSub { font-size: 12px; color: #d6f0e0; }
#bubbleUser {
    background: #1f9d55; color: #ffffff; border-radius: 14px;
    padding: 11px 15px; font-size: 14px;
}
#bubbleBot {
    background: #ffffff; color: #1f2a24; border: 1px solid #e2ebe5;
    border-radius: 14px; padding: 13px 16px; font-size: 14px;
}
#bubbleBotErr { background: #fff7ed; color: #8a4b0f; border: 1px solid #f4d7b0;
    border-radius: 14px; padding: 12px 15px; font-size: 13px; }
#stepBox { background: #f0f6f2; border: 1px dashed #c9dfd1; border-radius: 10px;
           color: #4a5f53; font-size: 11px; padding: 8px 10px; }
#engineTag { color: #6d8478; font-size: 11px; }
#chips QPushButton {
    background: #ffffff; color: #16673f; border: 1px solid #cfe6da;
    border-radius: 15px; padding: 6px 13px; font-size: 12px;
}
#chips QPushButton:hover { background: #e8f6ee; border-color: #1f9d55; }
#askInput {
    background: #ffffff; border: 1px solid #d5e6dc; border-radius: 20px;
    padding: 10px 16px; font-size: 14px;
}
#askInput:focus { border: 1px solid #1f9d55; }
#sendBtn {
    background: qlineargradient(x1:0,y1:0,x2:1,y2:0, stop:0 #12a150, stop:1 #0f7a44);
    color: #ffffff; border: none; border-radius: 20px; padding: 10px 24px;
    font-size: 14px; font-weight: 600;
}
#sendBtn:hover { background: #16b35a; }
#sendBtn:disabled { background: #b9cdc1; }
#cfgBtn { background: transparent; color: #ffffff; border: 1px solid rgba(255,255,255,.55);
    border-radius: 14px; padding: 5px 13px; font-size: 12px; }
#cfgBtn:hover { background: rgba(255,255,255,.18); }
"""

QUICK = [
    "广东一产占比多少",
    "2024年一产占比最高的5个省",
    "深圳2018年GDP是多少",
    "农村居民收入未来3年趋势",
    "水稻20亩、售价2.5元，保本吗",
    "广东21市哪个最依赖农业",
    "广东改革开放农民收入增长多少倍",
    "广东2024年粮食产量是多少",
    "广东恩格尔系数历年怎么变",
]


def md2html(text):
    """极简 Markdown → HTML：标题/粗体/表格/引用/列表/换行。"""
    lines = text.split("\n")
    out, i = [], 0
    while i < len(lines):
        ln = lines[i]
        s = ln.strip()
        if not s:
            out.append("<div style='height:7px'></div>")
            i += 1
            continue
        # 表格
        if s.startswith("|") and i + 1 < len(lines) and set(lines[i + 1].replace("|", "").strip()) <= set("-: "):
            header = [c.strip() for c in s.strip("|").split("|")]
            i += 2
            body = []
            while i < len(lines) and lines[i].strip().startswith("|"):
                body.append([c.strip() for c in lines[i].strip().strip("|").split("|")])
                i += 1
            t = ["<table cellspacing='0' cellpadding='6' style='border-collapse:collapse;font-size:13px;margin:4px 0'>"]
            t.append("<tr>" + "".join(
                f"<th style='background:#eaf6ef;color:#16673f;border:1px solid #d8e8de;text-align:left'>{html.escape(h)}</th>"
                for h in header) + "</tr>")
            for row in body:
                t.append("<tr>" + "".join(
                    f"<td style='border:1px solid #e6efe9;color:#26332c'>{html.escape(c)}</td>" for c in row) + "</tr>")
            t.append("</table>")
            out.append("".join(t))
            continue
        # 引用
        if s.startswith("&gt;") or s.startswith(">"):
            out.append(f"<div style='color:#6d8478;font-size:12px;border-left:3px solid #cfe6da;"
                       f"padding:2px 0 2px 9px;margin:5px 0'>{html.escape(s.lstrip('> '))}</div>")
            i += 1
            continue
        # 列表
        if re.match(r"^(\d+\.|-|\*)\s", s):
            item = re.sub(r"^(\d+\.|-|\*)\s", "", s)
            out.append(f"<div style='margin:3px 0 3px 6px'>• {inline_md(item)}</div>")
            i += 1
            continue
        out.append(f"<div style='margin:3px 0;line-height:1.65'>{inline_md(s)}</div>")
        i += 1
    return "".join(out)


def inline_md(s):
    s = html.escape(s)
    s = re.sub(r"\*\*(.+?)\*\*", r"<b style='color:#0f7a44'>\1</b>", s)
    s = re.sub(r"`(.+?)`", r"<code style='background:#eef5f0;padding:1px 4px;border-radius:3px'>\1</code>", s)
    return s


class Bubble(QFrame):
    def __init__(self, text, user=False, err=False, parent=None):
        super().__init__(parent)
        name = "bubbleUser" if user else ("bubbleBotErr" if err else "bubbleBot")
        self.setObjectName(name)
        # 内联样式：PyInstaller 打包后 QSS 继承偶发失效，直接写死保证可见
        if user:
            self.setStyleSheet("QFrame{background:#1f9d55;color:#ffffff;border-radius:14px;}"
                               "QLabel{color:#ffffff;background:transparent;}")
        elif err:
            self.setStyleSheet("QFrame{background:#fff7ed;border:1px solid #f4d7b0;border-radius:14px;}")
        else:
            self.setStyleSheet("QFrame{background:#ffffff;border:1px solid #e2ebe5;border-radius:14px;}")
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lab = QLabel()
        lab.setTextFormat(Qt.RichText)
        lab.setWordWrap(True)
        if user:
            lab.setText(f"<div style='color:#fff;font-size:14px;line-height:1.6'>{html.escape(text)}</div>")
        else:
            lab.setText(md2html(text))
        lab.setTextInteractionFlags(Qt.TextSelectableByMouse)
        lay.addWidget(lab)
        self.setMaximumWidth(880)
        self.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Minimum)


class AgentPage(QWidget):
    """主对话页。"""
    reply_ready = Signal(object, object)  # (Reply|None, error|None) — 跨线程回传

    def __init__(self, reader_view=None, parent=None):
        super().__init__(parent)
        self.setObjectName("agentRoot")
        self.setStyleSheet(CSS)
        self.hub = DataHub(base=str(self._data_base()))
        self.agent = Agent(self.hub)
        self.reader = reader_view
        self._busy = False
        self.reply_ready.connect(self._done)
        self._build()

    def _data_base(self):
        from main import res_path
        return res_path(".")

    # ---------------- UI

    def _build(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        head = QFrame()
        head.setObjectName("agentHead")
        head.setFixedHeight(104)
        hl = QHBoxLayout(head)
        hl.setContentsMargins(28, 16, 22, 16)
        txt = QVBoxLayout()
        txt.setSpacing(3)
        t = QLabel("🤖 智农宝决策 Agent")
        t.setObjectName("agentTitle")
        s = QLabel("查数据 · 算保本 · 判风险 · 给建议 —— 工具调用全程可溯源，离线也能答")
        s.setObjectName("agentSub")
        txt.addWidget(t)
        txt.addWidget(s)
        hl.addLayout(txt, 1)
        self.cfg_btn = QPushButton("⚙ 大模型")
        self.cfg_btn.setObjectName("cfgBtn")
        self.cfg_btn.clicked.connect(self.open_config)
        self.clear_btn = QPushButton("清空")
        self.clear_btn.setObjectName("cfgBtn")
        self.clear_btn.clicked.connect(self.reset)
        hl.addWidget(self.cfg_btn)
        hl.addWidget(self.clear_btn)
        root.addWidget(head)

        # 对话区
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.NoFrame)
        self.scroll.setStyleSheet("QScrollArea{background:#f4f8f5;border:none}"
                                 "QScrollBar:vertical{width:9px;background:transparent}"
                                 "QScrollBar::handle:vertical{background:#c9dfd1;border-radius:4px}")
        self.host = QWidget()
        self.host.setStyleSheet("background:#f4f8f5")
        self.vbox = QVBoxLayout(self.host)
        self.vbox.setContentsMargins(26, 18, 26, 12)
        self.vbox.setSpacing(12)
        # 不用 stretch 顶到底：消息按顺序追加，靠 scroll 自动滚到底部
        self.scroll.setWidget(self.host)
        root.addWidget(self.scroll, 1)

        # 快捷提问
        chips = QWidget()
        chips.setObjectName("chips")
        chips.setStyleSheet("background:#f4f8f5")
        chl = QHBoxLayout(chips)
        chl.setContentsMargins(26, 2, 26, 6)
        chl.setSpacing(8)
        for q in QUICK:
            b = QPushButton(q)
            b.setCursor(Qt.PointingHandCursor)
            b.clicked.connect(lambda _=False, q=q: self.send(q))
            chl.addWidget(b)
        chl.addStretch(1)
        root.addWidget(chips)

        # 输入
        bar = QWidget()
        bar.setStyleSheet("background:#f4f8f5")
        bl = QHBoxLayout(bar)
        bl.setContentsMargins(26, 0, 26, 18)
        bl.setSpacing(10)
        self.input = QLineEdit()
        self.input.setObjectName("askInput")
        self.input.setPlaceholderText("问点什么……  例：广东20亩水稻，亩成本1200元、售价2.6元，会不会亏？")
        self.input.returnPressed.connect(self.on_send)
        self.btn = QPushButton("发送")
        self.btn.setObjectName("sendBtn")
        self.btn.setCursor(Qt.PointingHandCursor)
        self.btn.clicked.connect(self.on_send)
        bl.addWidget(self.input, 1)
        bl.addWidget(self.btn)
        root.addWidget(bar)

        QTimer.singleShot(120, self.welcome)

    # ---------------- 对话

    def welcome(self):
        conf = load_llm_conf()
        if conf.get("api_key"):
            eng = f"大模型已接入 · {conf.get('model')}"
        else:
            eng = "当前为离线规则引擎（点右上「⚙ 大模型」可接入任意 OpenAI 兼容接口）"
        self.add_bot(
            "我是智农宝决策 Agent。可以直接问我数据、要排名、算保本、判风险。\n\n"
            "**我能查的真实数据**\n"
            "- 31 省面板 1980–2024（GDP / 一产占比 / 农村居民收入 / 人口）\n"
            "- 广东 21 市 1999–2018（GDP / 产业结构 / 人口 / 就业）\n"
            "- 作物保本测算（8 种作物参考单产与价格）\n\n"
            "**试一句**：「水稻20亩、售价2.5元，保本吗」或「深圳2018年GDP」。",
            engine=eng, steps=[])

    def add_user(self, text):
        row = QHBoxLayout()
        row.addStretch(1)
        row.addWidget(Bubble(text, user=True))
        self.vbox.addLayout(row)
        QTimer.singleShot(30, self._to_bottom)

    def add_bot(self, text, engine=None, steps=None, err=False):
        wrap = QWidget()
        wrap.setStyleSheet("background:transparent")
        wl = QVBoxLayout(wrap)
        wl.setContentsMargins(0, 0, 0, 0)
        wl.setSpacing(6)
        wl.addWidget(Bubble(text, err=err), 0, Qt.AlignLeft)
        if steps:
            box = QLabel(self._steps_text(steps))
            box.setObjectName("stepBox")
            box.setWordWrap(True)
            box.setTextFormat(Qt.RichText)
            box.setMaximumWidth(880)
            wl.addWidget(box, 0, Qt.AlignLeft)
        if engine:
            tag = QLabel(f"— {engine}")
            tag.setObjectName("engineTag")
            wl.addWidget(tag, 0, Qt.AlignLeft)
        row = QHBoxLayout()
        row.addWidget(wrap)
        row.addStretch(1)
        self.vbox.addLayout(row)
        QTimer.singleShot(30, self._to_bottom)

    def _steps_text(self, steps):
        names = {"query_province": "省级查询", "rank_provinces": "省份排名", "trend_forecast": "趋势外推",
                 "query_cities": "广东市域查询", "cost_plan": "保本测算", "search_book": "全书检索",
                 "gd_overview": "广东全景"}
        parts = []
        for s in steps:
            nm = names.get(s["tool"], s["tool"])
            args = ", ".join(f"{k}={v}" for k, v in (s.get("args") or {}).items() if v not in (None, ""))
            parts.append(f"🔧 <b>{nm}</b>" + (f"（{html.escape(args)}）" if args else ""))
        return "工具调用 → " + " · ".join(parts)

    def _to_bottom(self):
        sb = self.scroll.verticalScrollBar()
        sb.setValue(sb.maximum())

    def on_send(self):
        q = self.input.text().strip()
        if not q:
            return
        self.input.clear()
        self.send(q)

    def send(self, q):
        if self._busy:
            return
        self._busy = True
        self.btn.setEnabled(False)
        self.btn.setText("思考中…")
        self.add_user(q)
        QTimer.singleShot(30, self._to_bottom)

        def work():
            try:
                r = self.agent.ask(q)
                err = None
            except Exception as e:  # noqa
                r = None
                err = f"{type(e).__name__}: {e}"
            # 必须用信号跨线程回传：子线程无事件循环，QTimer.singleShot 不触发
            self.reply_ready.emit(r, err)

        threading.Thread(target=work, daemon=True).start()

    def _done(self, r, err):
        if err:
            self.add_bot(f"出错了：`{err}`\n\n可以换个问法，或点右上「⚙ 大模型」检查接口配置。", err=True)
        else:
            self.add_bot(r.text, engine=r.engine, steps=r.steps)
            if r.chart and self.reader is not None:
                try:
                    self.reader.show_floating_chart(r.chart)
                except Exception:
                    pass
        self._busy = False
        self.btn.setEnabled(True)
        self.btn.setText("发送")
        self._to_bottom()

    def reset(self):
        while self.vbox.count() > 0:
            it = self.vbox.takeAt(0)
            w = it.widget()
            if w:
                w.deleteLater()
            elif it.layout():
                while it.layout().count():
                    c = it.layout().takeAt(0)
                    if c.widget():
                        c.widget().deleteLater()
        self.welcome()

    # ---------------- 配置

    def open_config(self):
        dlg = ConfigDialog(self)
        if dlg.exec():
            conf = load_llm_conf()
            state = f"大模型已接入 · {conf.get('model')}" if conf.get("api_key") else "已切回离线规则引擎"
            self.add_bot(f"配置已保存：{state}。", engine="系统")


class ConfigDialog(QDialog):
    PRESETS = [
        ("自定义 / 留空手填", "", ""),
        ("DeepSeek", "https://api.deepseek.com/v1", "deepseek-chat"),
        ("阿里云百炼（通义）", "https://dashscope.aliyuncs.com/compatible-mode/v1", "qwen-plus"),
        ("智谱 GLM", "https://open.bigmodel.cn/api/paas/v4", "glm-4-flash"),
        ("月之暗面 Kimi", "https://api.moonshot.cn/v1", "moonshot-v1-8k"),
        ("OpenAI", "https://api.openai.com/v1", "gpt-4o-mini"),
        ("本地 Ollama", "http://127.0.0.1:11434/v1", "qwen2.5:7b"),
    ]

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("接入大模型（OpenAI 兼容接口）")
        self.setMinimumWidth(560)
        self.setStyleSheet("""
            QDialog{background:#f7fbf8}
            QLabel{color:#26332c;font-size:13px}
            QLineEdit,QComboBox{border:1px solid #d5e6dc;border-radius:8px;padding:8px 10px;
                background:#fff;font-size:13px}
            QPushButton{background:#1f9d55;color:#fff;border:none;border-radius:8px;
                padding:9px 20px;font-size:13px}
            QPushButton:hover{background:#16b35a}
            QPushButton#ghost{background:#eef5f0;color:#16673f}
        """)
        conf = load_llm_conf()
        lay = QVBoxLayout(self)
        lay.setContentsMargins(22, 20, 22, 18)
        lay.setSpacing(12)

        tip = QLabel("填 Base URL + API Key 即可让 Agent 用大模型思考（工具调用仍走本地真实数据）。\n"
                     "配置存在本机 %APPDATA%\\ZhinongbaoBook\\llm.json，不上传任何地方。")
        tip.setWordWrap(True)
        tip.setStyleSheet("color:#5b7266;font-size:12px")
        lay.addWidget(tip)

        form = QFormLayout()
        form.setSpacing(10)
        self.preset = QComboBox()
        for name, _, _ in self.PRESETS:
            self.preset.addItem(name)
        self.preset.currentIndexChanged.connect(self._apply_preset)
        self.base = QLineEdit(conf.get("base_url", ""))
        self.base.setPlaceholderText("https://api.deepseek.com/v1")
        self.key = QLineEdit(conf.get("api_key", ""))
        self.key.setEchoMode(QLineEdit.Password)
        self.key.setPlaceholderText("sk-...")
        self.model = QLineEdit(conf.get("model", ""))
        self.model.setPlaceholderText("deepseek-chat")
        show = QPushButton("显示")
        show.setObjectName("ghost")
        show.setFixedWidth(56)
        show.clicked.connect(lambda: self.key.setEchoMode(
            QLineEdit.Normal if self.key.echoMode() == QLineEdit.Password else QLineEdit.Password))
        keyrow = QHBoxLayout()
        keyrow.addWidget(self.key, 1)
        keyrow.addWidget(show)
        kw = QWidget()
        kw.setLayout(keyrow)
        form.addRow("预设", self.preset)
        form.addRow("Base URL", self.base)
        form.addRow("API Key", kw)
        form.addRow("模型名", self.model)
        lay.addLayout(form)

        btns = QHBoxLayout()
        test = QPushButton("测试连接")
        test.setObjectName("ghost")
        test.clicked.connect(self._test)
        self.status = QLabel("")
        self.status.setWordWrap(True)
        self.status.setStyleSheet("font-size:12px;color:#5b7266")
        save = QPushButton("保存")
        save.clicked.connect(self._save)
        cancel = QPushButton("取消")
        cancel.setObjectName("ghost")
        cancel.clicked.connect(self.reject)
        btns.addWidget(test)
        btns.addWidget(self.status, 1)
        btns.addWidget(cancel)
        btns.addWidget(save)
        lay.addLayout(btns)

    def _apply_preset(self, i):
        _, url, model = self.PRESETS[i]
        if url:
            self.base.setText(url)
            self.model.setText(model)

    def _current(self):
        return {"base_url": self.base.text().strip(),
                "api_key": self.key.text().strip(),
                "model": self.model.text().strip() or "gpt-4o-mini"}

    def _test(self):
        conf = self._current()
        if not conf["api_key"]:
            self.status.setText("⚠️ 先填 API Key")
            return
        self.status.setText("测试中…")
        self.status.repaint()

        def work():
            from agent import llm_chat, LLMError
            try:
                r = llm_chat(conf, [{"role": "user", "content": "回复两个字：可用"}], timeout=25)
                txt = (r.get("choices") or [{}])[0].get("message", {}).get("content", "")
                self.status.setText(f"✅ 连通，模型回复：{txt[:40]}")
            except LLMError as e:
                self.status.setText(f"❌ {e}")
            except Exception as e:
                self.status.setText(f"❌ {type(e).__name__}: {e}")

        threading.Thread(target=work, daemon=True).start()

    def _save(self):
        conf = self._current()
        if conf["api_key"] and not conf["base_url"]:
            self.status.setText("⚠️ 有 Key 就必须填 Base URL")
            return
        save_llm_conf(conf)
        self.accept()
