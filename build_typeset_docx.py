# -*- coding: utf-8 -*-
"""排印级书稿：把 book_data.json 排成楷体 + Times New Roman + 关键词三色标注的 .docx。

遵循排版 skill 规范：
  * 中文正文=楷体（KaiTi/STKaiti），数字与拉丁字母=Times New Roman；
  * 关键词分三类着色：制度政策=红、指标数据=蓝、决断警示=金；
  * 按四部分类编排目录；卷七 10 章 × 20 页全量收录。
"""
import json
import re
import sys
from pathlib import Path

from docx import Document
from docx.shared import Pt, RGBColor, Cm
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_LINE_SPACING
from docx.enum.section import WD_SECTION
from docx.oxml.ns import qn

BASE = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE / 'content'))
import typography as T

CN = '楷体'
CN_ALT = 'KaiTi'
EN = 'Times New Roman'
C_POLICY = RGBColor(0xA3, 0x41, 0x2F)
C_METRIC = RGBColor(0x2F, 0x60, 0x94)
C_DECISION = RGBColor(0x9A, 0x6B, 0x12)
C_INK = RGBColor(0x1D, 0x2A, 0x22)
C_MUTE = RGBColor(0x6D, 0x80, 0x72)


def set_run_font(run, size=11, bold=False, color=C_INK, en=False):
    run.font.name = EN if en else CN
    run.font.size = Pt(size)
    run.font.bold = bold
    run.font.color.rgb = color
    rPr = run._element.get_or_add_rPr()
    rFonts = rPr.find(qn('w:rFonts'))
    if rFonts is None:
        from docx.oxml import OxmlElement
        rFonts = OxmlElement('w:rFonts')
        rPr.append(rFonts)
    rFonts.set(qn('w:eastAsia'), CN_ALT if not en else CN)
    rFonts.set(qn('w:ascii'), EN)
    rFonts.set(qn('w:hAnsi'), EN)


# 关键词切分（长词优先）
_ALL = sorted([(w, k) for k, words in T.KW.items() for w in words], key=lambda x: -len(x[0]))
_KEYS = [w for w, _ in _ALL]
_KMAP = dict(_ALL)
# 非捕获组：避免 re.split 因嵌套捕获组重复返回同一片段
_NUM_PAT = r'(?:\d[\d,，]*\.?\d*)\s*(?:亿元|万吨|万亩|万头|万人|元/亩|元|%|倍|公斤|斤|户|亩|公顷|个点|个百分点)'
_YEAR_PAT = r'(?:19[7-9]\d|20[0-2]\d)\s*年?'
_PAT = re.compile('(' + '|'.join(re.escape(w) for w in _KEYS) + '|' +
                  _NUM_PAT + '|' + _YEAR_PAT + ')')
_NUM_COMPILED = re.compile(_NUM_PAT)
_YEAR_COMPILED = re.compile(_YEAR_PAT)


def add_marked(paragraph, text, size=11, base_color=C_INK):
    """按关键词切分文本，逐段设置字体与颜色。"""
    if not text:
        return
    parts = _PAT.split(str(text))
    for seg in parts:
        if not seg:
            continue
        kind = _KMAP.get(seg)
        if kind == 'policy':
            set_run_font(paragraph.add_run(seg), size, True, C_POLICY, en=False)
        elif kind == 'metric':
            set_run_font(paragraph.add_run(seg), size, True, C_METRIC, en=False)
        elif kind == 'decision':
            set_run_font(paragraph.add_run(seg), size, True, C_DECISION, en=False)
        elif _NUM_COMPILED.fullmatch(seg) or _YEAR_COMPILED.fullmatch(seg):
            set_run_font(paragraph.add_run(seg), size, True, C_METRIC, en=True)
        else:
            set_run_font(paragraph.add_run(seg), size, False, base_color, en=False)


def para(doc, text='', size=11, align=None, space_after=6, first_indent=True, color=C_INK):
    p = doc.add_paragraph()
    if align is not None:
        p.alignment = align
    pf = p.paragraph_format
    pf.space_after = Pt(space_after)
    pf.line_spacing_rule = WD_LINE_SPACING.MULTIPLE
    pf.line_spacing = 1.5
    if first_indent:
        pf.first_line_indent = Cm(0.74)
    if text:
        add_marked(p, text, size, color)
    return p


def heading(doc, text, level=1):
    p = doc.add_paragraph()
    p.paragraph_format.space_before = Pt(16 if level == 1 else 10)
    p.paragraph_format.space_after = Pt(8)
    p.paragraph_format.keep_with_next = True
    size = {1: 20, 2: 15, 3: 12.5}.get(level, 11)
    color = C_POLICY if level == 1 else (C_METRIC if level == 2 else C_INK)
    r = p.add_run(text)
    set_run_font(r, size, True, color, en=False)
    return p


def page_break(doc):
    doc.add_page_break()


def build():
    book = json.load(open(BASE / 'app/data/book_data.json', encoding='utf-8'))
    books = {b['id']: b for b in book['books']}
    doc = Document()

    # 页面：A4 + 页边距
    for s in doc.sections:
        s.top_margin = Cm(2.4); s.bottom_margin = Cm(2.2)
        s.left_margin = Cm(2.6); s.right_margin = Cm(2.4)

    # 默认样式
    normal = doc.styles['Normal']
    normal.font.name = CN
    normal.font.size = Pt(11)
    normal.element.rPr.rFonts.set(qn('w:eastAsia'), CN_ALT)

    # ===== 封面 =====
    for _ in range(4):
        doc.add_paragraph()
    p = doc.add_paragraph(); p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    set_run_font(p.add_run('智农宝'), 40, True, C_POLICY)
    p = doc.add_paragraph(); p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    set_run_font(p.add_run('农 业 数 据 全 书'), 26, True, C_INK)
    p = doc.add_paragraph(); p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    set_run_font(p.add_run('改革开放 · 农村经济 · 智慧农业决策系统'), 14, False, C_MUTE)
    doc.add_paragraph()
    p = doc.add_paragraph(); p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    set_run_font(p.add_run('七卷 · 四部 · 三十五章 · 一千三百九十五页'), 12, False, C_METRIC, en=True)
    for _ in range(3):
        doc.add_paragraph()
    p = doc.add_paragraph(); p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    set_run_font(p.add_run('楷体正文 · Times New Roman 数字 · 关键词三色标注'), 11, False, C_MUTE)
    p = doc.add_paragraph(); p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    set_run_font(p.add_run('数据来自《广东农村统计年鉴 2019》与广东省统计局公报'), 10.5, False, C_MUTE)
    ip = doc.add_paragraph(); ip.alignment = WD_ALIGN_PARAGRAPH.CENTER
    cover_img = BASE / 'app/assets/img3d/smart_farm.jpg'
    if cover_img.exists():
        ip.add_run().add_picture(str(cover_img), width=Cm(11))
    page_break(doc)

    # ===== 四部分类目录 =====
    heading(doc, '目 录 · 四部分类', 1)
    para(doc, '全书按主题归为四部。每一部是一个独立的数据世界，卷与卷之间层层衔接。', first_indent=False, color=C_MUTE)
    for part in T.PARTS:
        heading(doc, '第 %s 部　%s' % (part['no'], part['title']), 2)
        para(doc, part['lead'], first_indent=False)
        for vid in part['volumes']:
            b = books.get(vid)
            if not b:
                continue
            p = doc.add_paragraph()
            p.paragraph_format.left_indent = Cm(0.8)
            p.paragraph_format.space_after = Pt(3)
            add_marked(p, '%s　%s（%d 章）' % (b.get('icon', '📖'), b['title'], len(b['chapters'])), 11)
    page_break(doc)

    # ===== 各卷正文 =====
    part_imgs = {'part1': 'guangdong_map', 'part2': 'tea_garden',
                 'part3': 'dashboard', 'part4': 'smart_farm'}
    for part in T.PARTS:
        heading(doc, '第 %s 部　%s' % (part['no'], part['title']), 1)
        # 3D 等距插画（按部配图）
        img = BASE / 'app/assets/img3d' / (part_imgs.get(part['id'], 'smart_farm') + '.jpg')
        if img.exists():
            ip = doc.add_paragraph()
            ip.alignment = WD_ALIGN_PARAGRAPH.CENTER
            ip.paragraph_format.space_after = Pt(6)
            ip.add_run().add_picture(str(img), width=Cm(12.5))
        para(doc, part['desc'], first_indent=False, color=C_MUTE)
        for vid in part['volumes']:
            b = books.get(vid)
            if not b:
                continue
            heading(doc, b['title'], 2)
            if b.get('subtitle'):
                para(doc, b['subtitle'], first_indent=False, color=C_MUTE)
            for ch in b['chapters']:
                heading(doc, ch['title'], 3)
                if ch.get('lead'):
                    para(doc, ch['lead'], first_indent=False)
                blocks = ch.get('blocks', [])
                pages = ch.get('pages', [])
                if pages:  # 卷七：10 章 × 20 页
                    for pg in pages:
                        if pg.get('kind') == 'cover':
                            continue
                        if pg.get('title'):
                            heading(doc, '第 %d 页 · %s' % (pg.get('no', 0), pg['title']), 3)
                        render_blocks(doc, pg.get('blocks', []))
                else:
                    render_blocks(doc, blocks)
        page_break(doc)

    out = BASE / 'dist' / '智农宝农业数据全书_排印书稿_v8.0.0.docx'
    out.parent.mkdir(exist_ok=True)
    doc.save(str(out))
    print('SAVED', out.name, round(out.stat().st_size / 1024, 1), 'KB')


def render_blocks(doc, blocks):
    for b in blocks:
        t = b.get('type')
        if t == 'text':
            if b.get('title'):
                heading(doc, b['title'], 3)
            for para_txt in b.get('paras', []):
                para(doc, para_txt)
        elif t == 'theme':
            p = doc.add_paragraph()
            p.paragraph_format.left_indent = Cm(0.6)
            add_marked(p, '◆ ' + b.get('quote', ''), 11.5, C_POLICY)
            if b.get('question'):
                p2 = doc.add_paragraph()
                p2.paragraph_format.left_indent = Cm(0.6)
                add_marked(p2, '　　?' + b['question'], 10.5, C_MUTE)
        elif t == 'doc':
            if b.get('head'):
                heading(doc, b['head'], 3)
            for para_txt in b.get('paras', []):
                para(doc, para_txt)
        elif t == 'voice':
            p = doc.add_paragraph()
            p.paragraph_format.left_indent = Cm(0.8)
            add_marked(p, '「' + b.get('quote', '') + '」', 11, C_INK)
        elif t == 'note':
            for para_txt in b.get('paras', []):
                para(doc, '注：' + para_txt, size=10, color=C_MUTE)
        elif t == 'decision':
            for item in b.get('items', []):
                if isinstance(item, (list, tuple)) and len(item) >= 2:
                    para(doc, '▸ ' + str(item[1]), size=10.5)
                else:
                    para(doc, '▸ ' + str(item), size=10.5)
        elif t == 'table':
            rows = b.get('rows', [])
            if rows:
                cols = len(rows[0]) if isinstance(rows[0], (list, tuple)) else 1
                table = doc.add_table(rows=0, cols=cols)
                table.style = 'Light Grid Accent 1'
                for row in rows:
                    cells = table.add_row().cells
                    for i, cell in enumerate(row if isinstance(row, (list, tuple)) else [row]):
                        if i < cols:
                            cells[i].text = ''
                            add_marked(cells[i].paragraphs[0], str(cell), 9)
        elif t == 'kpi':
            items = b.get('items', [])
            if items:
                para(doc, '　|　'.join('%s %s' % (v, l) for v, l in items), size=10,
                     first_indent=False, color=C_METRIC)
        elif t == 'algo':
            # 算法管线：标题 + 输入 + 编号步骤 + 输出
            if b.get('title'):
                heading(doc, '⚙ ' + b['title'], 4)
            if b.get('inputs'):
                para(doc, '输入：' + '　→　'.join(str(x) for x in b['inputs']),
                     size=10, first_indent=False, color=C_METRIC)
            for i, st in enumerate(b.get('steps', []), 1):
                if isinstance(st, (list, tuple)) and len(st) >= 2:
                    para(doc, '%d) %s：%s' % (i, st[0], st[1]),
                         size=10.5, first_indent=False)
            if b.get('output'):
                para(doc, '输出：' + str(b['output']), size=10.5,
                     first_indent=False, color=C_POLICY)
            if b.get('note'):
                para(doc, '※ ' + b['note'], size=9.5, first_indent=False, color=C_MUTE)
        elif t == 'action':
            # 精准干预处方：五段式
            heading(doc, '✚ 精准干预处方', 4)
            for label, key in [('触发条件', 'trigger'), ('算法决策', 'decision'),
                               ('预期效果', 'expected'), ('复核指标', 'verify')]:
                if b.get(key):
                    para(doc, '【%s】%s' % (label, b[key]), size=10.5,
                         first_indent=False, color=C_POLICY if label == '算法决策' else C_INK)
            if b.get('measures'):
                para(doc, '【落地措施】', size=10.5, first_indent=False, color=C_METRIC)
                for m in b['measures']:
                    para(doc, '　• ' + str(m), size=10.5, first_indent=False)
        elif t == 'image':
            # 诊断图以题注方式保留（图形见桌面版/网页版）
            if b.get('caption'):
                para(doc, '〔图〕' + b['caption'], size=9.5,
                     first_indent=False, color=C_MUTE)
        elif t == 'closing':
            if b.get('question'):
                para(doc, b['question'], size=11.5, color=C_POLICY)
        # chart 区块在 Word 中以文字说明保留（图形见网页版/桌面版）


if __name__ == '__main__':
    build()
