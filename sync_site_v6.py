# -*- coding: utf-8 -*-
"""把卷七"10 章 × 20 页"的目录同步到内置网页（#/reform 页）。幂等。"""
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SITE = ROOT / "app" / "site"
BOOK = ROOT / "app" / "data" / "book_data.json"

CSS_ANCHOR = "/* v6 toc */"


def build_toc():
    book = json.load(open(BOOK, encoding="utf-8"))
    vol = next(b for b in book["books"] if b["id"] == "vol7")
    chapters = []
    for i, ch in enumerate(vol["chapters"], 1):
        chapters.append({
            "num": i,
            "title": ch["title"],
            "span": ch.get("span", ""),
            "pages": len(ch.get("pages") or []),
            "theme": ch.get("theme", ""),
            "lead": ch.get("lead", ""),
        })
    toc = {"title": vol["title"], "subtitle": vol["subtitle"],
           "total_pages": sum(c["pages"] for c in chapters), "chapters": chapters}
    out = SITE / "data" / "vol7_toc.json"
    out.write_text(json.dumps(toc, ensure_ascii=False, indent=1), encoding="utf-8")
    return toc


def patch_js():
    p = SITE / "assets" / "js" / "app.js"
    s = p.read_text(encoding="utf-8")
    if "reform: 'guangdong_reform.json'" in s and "vol7: 'vol7_toc.json'" not in s:
        s = s.replace("reform: 'guangdong_reform.json'",
                      "reform: 'guangdong_reform.json', vol7: 'vol7_toc.json'")
    block = """    const toc = app.vol7;
    if (toc && toc.chapters && toc.chapters.length) {
      view.insertAdjacentHTML('beforeend',
        `<div class="section-bar"><h2>十章 · ${toc.total_pages} 页</h2><span class="subtle">配套桌面阅读器可逐页翻阅，含翻页音效与决策 Agent</span></div>
         <div class="toc-grid">${toc.chapters.map(c => `
           <div class="toc-card">
             <div class="toc-no">CH ${String(c.num).padStart(2, '0')}</div>
             <div class="toc-title">${esc((c.title || '').split('·').pop().trim())}</div>
             <div class="toc-meta">${esc(c.span || '')} · ${c.pages} 页 · 主题「${esc(c.theme || '')}」</div>
             <div class="toc-lead">${esc((c.lead || '').slice(0, 68))}…</div>
           </div>`).join('')}</div>`);
    }
"""
    if "十章 · ${toc.total_pages} 页" not in s:
        s = s.replace("""    chart('#rf-engel', engel, '%', 1);
  }""", """    chart('#rf-engel', engel, '%', 1);
""" + block + "  }")
    p.write_text(s, encoding="utf-8")


def patch_css():
    p = SITE / "assets" / "css" / "style.css"
    s = p.read_text(encoding="utf-8")
    if CSS_ANCHOR in s:
        return
    s += """

/* v6 toc */
.toc-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(280px,1fr));gap:14px;margin:16px 0 28px}
.toc-card{background:#fffdf7;border:1px solid #e6dfcd;border-left:4px solid #b23b2e;border-radius:10px;padding:14px 16px;transition:.18s}
.toc-card:hover{transform:translateY(-2px);box-shadow:0 10px 24px rgba(60,45,30,.10)}
.toc-no{font:700 12px/1 "DIN Alternate",system-ui;letter-spacing:2px;color:#b23b2e;opacity:.85}
.toc-title{margin:6px 0 4px;font-size:16px;font-weight:700;color:#22301f}
.toc-meta{font-size:12px;color:#8a7f6a}
.toc-lead{margin-top:8px;font-size:12.5px;line-height:1.75;color:#5d655c}
"""
    p.write_text(s, encoding="utf-8")


def patch_core():
    p = SITE / "data" / "core-data.js"
    s = p.read_text(encoding="utf-8")
    m = re.search(r"window\.__ZN_CORE__=(\{.*\})\s*;?\s*$", s, re.S)
    if not m:
        raise SystemExit("core-data.js 结构未识别")
    core = json.loads(m.group(1))
    core["reform"] = json.load(open(SITE / "data" / "guangdong_reform.json", encoding="utf-8"))
    core["vol7"] = json.load(open(SITE / "data" / "vol7_toc.json", encoding="utf-8"))
    prefix = s[:m.start()]
    p.write_text(prefix + "window.__ZN_CORE__=" +
                 json.dumps(core, ensure_ascii=False, separators=(",", ":")) + ";\n",
                 encoding="utf-8")
    return len(p.read_text(encoding="utf-8"))


if __name__ == "__main__":
    toc = build_toc()
    patch_js()
    patch_css()
    n = patch_core()
    print(f"卷七目录同步完成：{len(toc['chapters'])} 章 / {toc['total_pages']} 页，"
          f"core-data.js {n/1024:.0f} KB")
