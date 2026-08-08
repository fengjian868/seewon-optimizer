# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller 打包配置。

打包命令：
    pyinstaller build.spec

产物：dist/希沃一体机优化工具.exe（单文件，双击即用，零依赖）
"""
from PyInstaller.utils.hooks import collect_submodules

block_cipher = None

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    datas=[
        # 内置资源随 exe 一起打包
        ('assets/app.manifest', 'assets'),
        ('assets/icons', 'assets/icons'),
    ],
    hiddenimports=[
        'psutil',
        'PIL',
        'PIL._tkinter_finder',
    ],
    hookspath=[],
    runtime_hooks=[],
    excludes=['matplotlib', 'numpy', 'PyQt5', 'PySide6'],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='希沃一体机优化工具',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    # 嵌入 UAC manifest：启动即弹提权
    uac_admin=True,
    runtime_tmpdir=None,
    console=False,           # --windowed：不弹黑框
    disable_windowed_traceback=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='assets/icons/app.ico',
)
