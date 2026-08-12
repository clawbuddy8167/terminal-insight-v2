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
# Ship Windows unblock helper next to the exe (onedir COLLECT root).
if sys.platform.startswith("win"):
    datas.append((str(ROOT / "scripts" / "unblock-windows.bat"), "."))
    datas.append((str(ROOT / "scripts" / "unblock-windows.ps1"), "."))

binaries = []
hiddenimports = [
    "pywebview",
    "pywebview.platforms.cocoa",  # macOS
    "pywebview.platforms.edgechromium",  # Windows WebView2
    "pywebview.platforms.winforms",
    "clr_loader",
    "pythonnet",
    "charset_normalizer",
    "openpyxl",
    "httpx",
    "bs4",
    "pydantic",
    "pydantic_settings",
    "dotenv",
    "rich",
]

# Collect pythonnet / clr_loader / webview native bits (Windows GUI).
try:
    from PyInstaller.utils.hooks import collect_all, collect_data_files

    for pkg in ("pythonnet", "clr_loader", "webview"):
        d, b, h = collect_all(pkg)
        datas += d
        binaries += b
        hiddenimports += h
except Exception:
    pass

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
