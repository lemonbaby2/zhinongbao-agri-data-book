# -*- coding: utf-8 -*-
"""打包书式阅读器源码 zip（含 app 源码、数据、素材、构建脚本、README）。"""
import hashlib, zipfile
from pathlib import Path

ROOT = Path(__file__).parent
VERSION = "8.0.0"
DIST = ROOT / "dist"
DIST.mkdir(exist_ok=True)

# 只收这些路径
INCLUDE = [
    "app/main.py", "app/chart_widget.py", "app/agent.py", "app/agent_ui.py",
    "app/reader.py", "app/webserve.py", "app/__init__.py",
    "app/data/book_data.json", "app/data/guangdong.json", "app/data/guangdong_reform.json",
    "app/data/progress.json", "app/data/book_data.v5.bak.json",
    "app/assets/charts", "app/assets/img", "app/assets/img3d", "app/assets/diagrams",
    "app/assets/tea", "app/assets/sfx", "app/assets/paper.png", "app/data/typography.json",
    "app/site",
    "content", "build_typeset_docx.py", "gen_media.py", "build_reform_v6.py", "sync_site_v6.py",
    "build_decision_v8.py", "gen_decision_diagrams.py", "sync_site_v8.py",
    "test_reader.py", "test_v8.py",
    "installer.py", "build_book_data.py", "build_guangdong.py", "build_book_data_v31.py",
    "enrich_book_v4.py", "build_gd_reform.py", "build_reform_book.py",
    "extra_data/gd_official", "zhinongbao_book.spec", "verify_exe.py", "README.md",
    "dist/zhinongbao-decision-agent.zip",
]
ROOTDIR = f"智农宝农业数据全书_v{VERSION}"
tmp = DIST / f"_book_src_{VERSION}.zip"
final = DIST / f"智农宝农业数据全书_源码_v{VERSION}.zip"

count = 0
with zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as z:
    for rel in INCLUDE:
        p = ROOT / rel
        if not p.exists():
            continue
        if p.is_dir():
            for f in sorted(p.rglob("*")):
                if f.is_file():
                    z.write(f, f"{ROOTDIR}/{f.relative_to(ROOT).as_posix()}")
                    count += 1
        else:
            z.write(p, f"{ROOTDIR}/{rel}")
            count += 1
tmp.replace(final)
h = hashlib.sha256(final.read_bytes()).hexdigest()
(final.parent / "book_src.sha256").write_text(f"{h}  {final.name}\n", encoding="utf-8")
print(f"packaged: {final.name}, {count} entries, {final.stat().st_size//1024} KB")
print("sha256:", h)
