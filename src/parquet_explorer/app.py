"""Application entry point."""

from __future__ import annotations

import argparse
import contextlib
import sys

from parquet_explorer import __version__

#: Identifies the app to the Windows shell so the taskbar groups its windows
#: under our icon instead of the launching interpreter's.
APP_USER_MODEL_ID = "parquet-explorer.ParquetExplorer"


def version_string() -> str:
    """The ``--version`` banner, including the versions users hit bugs with."""
    import duckdb
    from PySide6 import __version__ as pyside_version
    from PySide6.QtCore import qVersion

    return (
        f"parquet-explorer {__version__} "
        f"(DuckDB {duckdb.__version__}, PySide6 {pyside_version}, Qt {qVersion()})"
    )


def _set_windows_app_id(app_id: str = APP_USER_MODEL_ID) -> None:
    """Register an explicit AppUserModelID on Windows; a no-op elsewhere."""
    if sys.platform != "win32":
        return
    import ctypes

    # shell32 is always present, but a locked-down host can still refuse the call.
    with contextlib.suppress(AttributeError, OSError):
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(app_id)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="parquet-explorer", description="Explore Parquet files with SQL."
    )
    parser.add_argument("file", nargs="?", help="Parquet file to open on startup")
    parser.add_argument("--version", action="version", version=version_string())
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv if argv is not None else sys.argv[1:])

    from PySide6.QtWidgets import QApplication

    from parquet_explorer.icon import app_icon
    from parquet_explorer.window import MainWindow

    _set_windows_app_id()

    app = QApplication(sys.argv[:1])
    app.setApplicationName("Parquet Explorer")
    app.setApplicationVersion(__version__)
    app.setOrganizationName("parquet-explorer")
    app.setWindowIcon(app_icon())

    window = MainWindow()
    window.show()
    if args.file:
        window.open_file(args.file)

    return app.exec()


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
