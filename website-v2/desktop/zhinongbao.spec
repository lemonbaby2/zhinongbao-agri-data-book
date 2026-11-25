# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller 打包配置：单文件、无控制台窗口，站点整目录内嵌。

运行方式（在 desktop 目录下）：
    python -m PyInstaller --noconfirm --clean zhinongbao.spec
也可以用项目根目录的 tools/build_exe.py 一键完成重命名。
"""

import os
from pathlib import Path

ROOT = Path(SPECPATH).resolve()
SITE = ROOT.parent / "site"
ICON = ROOT / "assets" / "zhinongbao.ico"
VERSION_FILE = ROOT / "version_info.txt"

if not (SITE / "index.html").is_file():
    raise SystemExit(f"站点目录不完整：{SITE}")

a = Analysis(
    ["zhinongbao.py"],
    pathex=[str(ROOT)],
    binaries=[],
    datas=[(str(SITE), "site")],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["tkinter", "unittest", "pydoc", "test", "numpy", "PIL", "pytest"],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="ZhiNongBao",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    runtime_tmpdir=None,
    console=os.environ.get("ZN_CONSOLE") == "1",
    disable_windowed_traceback=False,
    icon=str(ICON) if ICON.is_file() else None,
    version=str(VERSION_FILE) if VERSION_FILE.is_file() else None,
)
