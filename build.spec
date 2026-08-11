# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for terminal-insight-v2 GUI.

Build (on the target OS):
    python -W ignore -m PyInstaller build.spec --noconfirm

Windows → dist/terminal-insight-v2/terminal-insight-v2.exe (onedir)
macOS   → dist/Terminal Insight v2.app
"""
import sys
from pathlib import Path

block_cipher = None
ROOT = Path(SPECPATH).resolve()

datas = [
    # Whole package (gui/static, store/schema/*.sql, …)
    (str(ROOT / "src" / "terminal_insight_v2"), "terminal_insight_v2"),
    (str(ROOT / "category_templates"), "category_templates"),
    (str(ROOT / ".env.example"), "."),
]
binaries = []
hiddenimports = [
    "pywebview",
    "pywebview.platforms.cocoa",  # macOS
    "pywebview.platforms.edgechromium",  # Windows WebView2
    "charset_normalizer",
    "openpyxl",
    "httpx",
    "bs4",
    "pydantic",
    "pydantic_settings",
    "dotenv",
    "rich",
]

a = Analysis(
    [str(ROOT / "run_gui.py")],
    pathex=[str(ROOT / "src"), str(ROOT)],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        "matplotlib",
        "matplotlib.pyplot",
        "PyQt5",
        "PyQt6",
        "PySide2",
        "PySide6",
        "tkinter",
        "IPython",
        "notebook",
        "jupyter",
        "pytest",
    ],
    cipher=block_cipher,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="terminal-insight-v2",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    icon=None,
)

if sys.platform == "darwin":
    app = BUNDLE(
        exe,
        a.binaries,
        a.zipfiles,
        a.datas,
        name="Terminal Insight v2.app",
        icon=None,
        bundle_identifier="com.terminalinsight.v2",
    )
else:
    coll = COLLECT(
        exe,
        a.binaries,
        a.zipfiles,
        a.datas,
        name="terminal-insight-v2",
    )
