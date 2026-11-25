# -*- mode: python ; coding: utf-8 -*-
import os

block_cipher = None

datas = [
    ('app/data/book_data.json', 'data'),
    ('app/data/guangdong.json', 'data'),
    ('app/data/guangdong_reform.json', 'data'),
    ('app/data/progress.json', 'data'),
    ('app/data/typography.json', 'data'),
    ('content/typography.py', 'content'),
    ('app/assets/charts', 'assets/charts'),
    ('app/assets/img', 'assets/img'),
    ('app/assets/tea', 'assets/tea'),
    ('app/assets/sfx', 'assets/sfx'),
    ('app/assets/paper.png', 'assets'),
    ('app/assets/img3d', 'assets/img3d'),
    ('app/assets/diagrams', 'assets/diagrams'),
    ('app/site/assets/diagrams', 'site/assets/diagrams'),
    ('app/site', 'site'),
]
# 可选文件不存在时跳过
datas = [d for d in datas if os.path.exists(d[0])]

a = Analysis(
    ['installer.py'],
    pathex=['.'],
    binaries=[],
    datas=datas,
    hiddenimports=['app.main', 'app.chart_widget', 'app.agent', 'app.agent_ui',
                   'app.webserve', 'app.reader', 'app.typography_bridge', 'urllib.request', 'http.server'],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['PySide6.QtWebEngineCore', 'PySide6.QtWebEngineWidgets',
              'PySide6.Qt3DCore', 'tkinter'],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)
pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz, a.scripts, a.binaries, a.zipfiles, a.datas, [],
    name='智农宝农业数据全书_v8.0.0',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,
)
