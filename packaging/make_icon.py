"""Render ``packaging/icon.ico`` from :mod:`parquet_explorer.icon`.

PyInstaller needs an icon file on disk at build time, so the ``.ico`` is committed
rather than generated during the build.  Re-run this after changing the icon:

    uv run python packaging/make_icon.py
"""

from __future__ import annotations

import os
import struct
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QBuffer, QByteArray
from PySide6.QtGui import QGuiApplication

from parquet_explorer.icon import ICON_SIZES, render_pixmap

DESTINATION = Path(__file__).parent / "icon.ico"

_ICONDIR = "<HHH"  # reserved, type (1 = icon), image count
_ICONDIRENTRY = "<BBBBHHII"  # w, h, colours, reserved, planes, bpp, size, offset


def _png_frame(size: int) -> bytes:
    """Render one icon size as PNG bytes.

    Windows Vista and later read PNG-compressed frames straight out of an ICO,
    which keeps the file small and avoids hand-rolling a BMP + AND mask.
    """
    data = QByteArray()
    buffer = QBuffer(data)
    buffer.open(QBuffer.OpenModeFlag.WriteOnly)
    if not render_pixmap(size).save(buffer, "PNG"):
        raise RuntimeError(f"could not encode the {size}px frame as PNG")
    buffer.close()
    return bytes(data)


def build_ico(sizes: tuple[int, ...] = ICON_SIZES) -> bytes:
    frames = [(size, _png_frame(size)) for size in sizes]

    header = struct.pack(_ICONDIR, 0, 1, len(frames))
    offset = len(header) + struct.calcsize(_ICONDIRENTRY) * len(frames)

    directory = b""
    for size, payload in frames:
        # 256 is stored as 0 — the field is a single byte.
        dimension = 0 if size >= 256 else size
        directory += struct.pack(
            _ICONDIRENTRY, dimension, dimension, 0, 0, 1, 32, len(payload), offset
        )
        offset += len(payload)

    return header + directory + b"".join(payload for _, payload in frames)


def main() -> int:
    QGuiApplication([])
    DESTINATION.write_bytes(build_ico())
    print(f"wrote {DESTINATION} ({DESTINATION.stat().st_size} bytes, {len(ICON_SIZES)} sizes)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
