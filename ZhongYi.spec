# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller 打包配置文件
用法：pyinstaller ZhongYi.spec
"""
import os
import sys

block_cipher = None

# 项目根目录
project_dir = os.path.abspath('.')

# 需要额外打包的数据文件
datas = [
    # 图片资源
    (os.path.join(project_dir, 'images'), 'images'),
    # 教程和 SQL 文件（放在 exe 同级目录，用户可见）
    (os.path.join(project_dir, 'tutorial'), 'tutorial'),
]

# 隐藏的导入（PyInstaller 可能分析不到的）
hiddenimports = [
    'pymysql',
    'pypinyin',
    'reportlab',
    'reportlab.pdfbase',
    'reportlab.pdfbase.ttfonts',
    'pypdfium2',
    'PIL',
    'Crypto',
    'Crypto.Cipher',
    'Crypto.Util',
    'Crypto.Hash',
    'pywin32',
]

a = Analysis(
    ['ZhongYi.py'],
    pathex=[project_dir],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'tkinter',  # 不用 tkinter
        'unittest',  # 不用测试框架
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='ZhongYi',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,  # 临时显示控制台，方便调试看错误
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=os.path.join(project_dir, 'images', 'app_icon.ico'),
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='ZhongYi',
)
