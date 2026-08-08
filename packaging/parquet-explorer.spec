# PyInstaller spec for the standalone Parquet Explorer builds.
#
# Built from the repository root:  pyinstaller packaging/parquet-explorer.spec
#
# A one-directory bundle is used rather than --onefile: Qt ships a lot of shared
# libraries, and unpacking them to a temp directory on every launch is slow.

import os
import sys

SPEC_DIR = SPECPATH  # noqa: F821 - injected by PyInstaller
IS_WINDOWS = sys.platform == "win32"

sys.path.insert(0, os.path.join(SPEC_DIR, os.pardir, "src"))
from parquet_explorer import __version__  # noqa: E402

# PySide6 pulls in Qt modules we never touch (3D, WebEngine, Charts, …).  Dropping
# them keeps the archive to a sane size.
EXCLUDED_QT = [
    "PySide6.Qt3DAnimation",
    "PySide6.Qt3DCore",
    "PySide6.Qt3DExtras",
    "PySide6.Qt3DInput",
    "PySide6.Qt3DLogic",
    "PySide6.Qt3DRender",
    "PySide6.QtBluetooth",
    "PySide6.QtCharts",
    "PySide6.QtDataVisualization",
    "PySide6.QtMultimedia",
    "PySide6.QtMultimediaWidgets",
    "PySide6.QtNetworkAuth",
    "PySide6.QtNfc",
    "PySide6.QtOpenGL",
    "PySide6.QtPositioning",
    "PySide6.QtQml",
    "PySide6.QtQuick",
    "PySide6.QtQuick3D",
    "PySide6.QtQuickWidgets",
    "PySide6.QtRemoteObjects",
    "PySide6.QtSensors",
    "PySide6.QtSerialPort",
    "PySide6.QtSpatialAudio",
    "PySide6.QtTextToSpeech",
    "PySide6.QtWebChannel",
    "PySide6.QtWebEngineCore",
    "PySide6.QtWebEngineQuick",
    "PySide6.QtWebEngineWidgets",
    "PySide6.QtWebSockets",
]


def windows_version_resource():
    """Populate the Windows "Details" tab of the executable's properties."""
    from PyInstaller.utils.win32.versioninfo import (
        FixedFileInfo,
        StringFileInfo,
        StringStruct,
        StringTable,
        VarFileInfo,
        VarStruct,
        VSVersionInfo,
    )

    parts = tuple(int(piece) for piece in __version__.split(".")[:3])
    numeric = (*parts, 0)

    return VSVersionInfo(
        ffi=FixedFileInfo(filevers=numeric, prodvers=numeric, mask=0x3F, flags=0x0, OS=0x4),
        kids=[
            StringFileInfo(
                [
                    StringTable(
                        "040904B0",  # US English, Unicode
                        [
                            StringStruct("CompanyName", "Parquet Explorer contributors"),
                            StringStruct("FileDescription", "Parquet Explorer"),
                            StringStruct("FileVersion", __version__),
                            StringStruct("InternalName", "parquet-explorer"),
                            StringStruct("LegalCopyright", "Copyright (c) 2026 Angel Milanov"),
                            StringStruct("OriginalFilename", "parquet-explorer.exe"),
                            StringStruct("ProductName", "Parquet Explorer"),
                            StringStruct("ProductVersion", __version__),
                        ],
                    )
                ]
            ),
            VarFileInfo([VarStruct("Translation", [0x0409, 1200])]),
        ],
    )


analysis = Analysis(
    [os.path.join(SPEC_DIR, "entrypoint.py")],
    pathex=[],
    binaries=[],
    datas=[],
    hiddenimports=["duckdb"],
    hookspath=[],
    runtime_hooks=[],
    excludes=[*EXCLUDED_QT, "matplotlib", "numpy", "pandas", "tkinter", "IPython"],
    noarchive=False,
)

pyz = PYZ(analysis.pure)

executable = EXE(
    pyz,
    analysis.scripts,
    [],
    exclude_binaries=True,
    name="parquet-explorer",
    debug=False,
    strip=False,
    upx=False,
    icon=os.path.join(SPEC_DIR, "icon.ico") if IS_WINDOWS else None,
    version=windows_version_resource() if IS_WINDOWS else None,
    # Console-enabled so `--version` and `--help` print when the exe is run from
    # a terminal, but the console the bootloader opens on a double-click is hidden
    # straight away — a GUI app should not sit behind a black window.
    console=True,
    hide_console="hide-early" if IS_WINDOWS else None,
)

COLLECT(
    executable,
    analysis.binaries,
    analysis.datas,
    strip=False,
    upx=False,
    name="parquet-explorer",
)
