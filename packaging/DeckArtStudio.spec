# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for DeckArt Studio. Build with packaging\\build_exe.ps1, not by hand."""
import sys
from pathlib import Path

PROJECT_ROOT = Path(SPECPATH).resolve().parent
sys.path.insert(0, str(PROJECT_ROOT))
from deckart_studio.version import APP_VERSION  # noqa: E402

ICON = str(PROJECT_ROOT / "packaging" / "deckart.ico")
UNUSED_QT_MODULES = [
    "PySide6.QtQml", "PySide6.QtQuick", "PySide6.QtQuickWidgets", "PySide6.QtNetwork", "PySide6.QtOpenGL",
    "PySide6.QtOpenGLWidgets", "PySide6.QtSql", "PySide6.QtTest", "PySide6.QtXml", "PySide6.QtConcurrent",
    "PySide6.QtDBus", "PySide6.QtPrintSupport", "PySide6.QtSvg", "PySide6.QtSvgWidgets",
]

analysis = Analysis(
    [str(PROJECT_ROOT / "deckart_studio" / "__main__.py")],
    pathex=[str(PROJECT_ROOT)],
    binaries=[],
    datas=[(str(PROJECT_ROOT / "deckart_studio" / "assets"), "deckart_studio/assets")],
    hiddenimports=[],
    hookspath=[],
    runtime_hooks=[],
    excludes=["tkinter", "unittest", "pydoc", "doctest"] + UNUSED_QT_MODULES,
    noarchive=False,
)
archive = PYZ(analysis.pure)

windowed_exe = EXE(
    archive, analysis.scripts, [],
    exclude_binaries=True,
    name="DeckArtStudio",
    icon=ICON,
    console=False,
    disable_windowed_traceback=False,
    upx=False,
    version=None,
)
console_exe = EXE(
    archive, analysis.scripts, [],
    exclude_binaries=True,
    name="DeckArtStudio-debug",
    icon=ICON,
    console=True,
    upx=False,
)
COLLECT(
    windowed_exe, console_exe,
    analysis.binaries, analysis.datas,
    strip=False, upx=False,
    name="DeckArtStudio",
)
