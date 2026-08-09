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
IS_MACOS = sys.platform == "darwin"

# macOS identifies an installed app by this string: it is the key for Launch
# Services, the preferences domain and the Gatekeeper record.  Like AppId in
# installer.iss, changing it makes an existing install look like a new app.
BUNDLE_IDENTIFIER = "io.github.angel-milanov.parquet-explorer"

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
    # On Windows this is a GUI-subsystem executable, so Windows never creates a
    # console for it and launching the app shows no terminal at all.  `--noconsole`
    # and `--windowed` are the command-line spellings of this; a spec file ignores
    # command-line flags, so it has to be set here.
    #
    # The rejected alternative was console=True plus hide_console="hide-early",
    # which lets Windows create the console and hides it afterwards: measured at
    # ~30 ms visible on a cold launch, and no help whatever when the console is
    # delegated to Windows Terminal, because that window belongs to another process.
    #
    # The cost is that cmd and PowerShell do not *wait* for a GUI program, so typing
    # `parquet-explorer --version` at a prompt returns before the output arrives.
    # Nothing depends on that: a GUI process still inherits the handles its launcher
    # passes it, so redirects and pipes capture --version normally, which is how the
    # release smoke test reads it (under `shell: bash`, which does wait).  The app
    # has no CLI beyond an optional file argument, --version and --help, so this is
    # not worth a second console executable.
    console=not IS_WINDOWS,
)

collection = COLLECT(
    executable,
    analysis.binaries,
    analysis.datas,
    strip=False,
    upx=False,
    name="parquet-explorer",
)

# On macOS the same collected bundle is also wrapped in a .app, which is what the
# disk image ships and what Finder can launch.  dist/parquet-explorer/ stays as it
# is, so the smoke test and the tar.gz are unaffected.
if IS_MACOS:
    BUNDLE(
        collection,
        name="Parquet Explorer.app",
        icon=os.path.join(SPEC_DIR, "icon.icns"),
        bundle_identifier=BUNDLE_IDENTIFIER,
        version=__version__,
        info_plist={
            "CFBundleName": "Parquet Explorer",
            "CFBundleDisplayName": "Parquet Explorer",
            "CFBundleShortVersionString": __version__,
            "CFBundleVersion": __version__,
            "LSApplicationCategoryType": "public.app-category.developer-tools",
            "LSMinimumSystemVersion": "12.0",
            # The macOS executable is built console=True (the split above is Windows
            # only), and PyInstaller reads that as "this is a command-line tool",
            # defaulting the bundle to LSBackgroundOnly — which would leave the app
            # with no Dock icon and no menu bar.  The keys here are merged over its
            # defaults, so saying so plainly is the fix.
            "LSBackgroundOnly": False,
            "NSHighResolutionCapable": True,
            "NSHumanReadableCopyright": "Copyright (c) 2026 Angel Milanov. MIT licensed.",
        },
    )
