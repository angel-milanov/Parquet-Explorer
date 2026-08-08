"""Render ``packaging/icon.ico`` and ``packaging/icon.icns`` from :mod:`parquet_explorer.icon`.

PyInstaller needs an icon file on disk at build time, so the platform icons are
committed rather than generated during the build.  Re-run this after changing the
icon:

    uv run python packaging/make_icon.py

Both formats are written on every platform — the ``.icns`` is a container of PNG
frames, so building it needs no macOS tooling.
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

PACKAGING = Path(__file__).parent
ICO_PATH = PACKAGING / "icon.ico"
ICNS_PATH = PACKAGING / "icon.icns"

_ICONDIR = "<HHH"  # reserved, type (1 = icon), image count
_ICONDIRENTRY = "<BBBBHHII"  # w, h, colours, reserved, planes, bpp, size, offset

#: ICNS element types and the pixel size each one holds.  macOS names them after
#: the point size and scale factor — ``ic11`` is 16pt@2x, hence 32 pixels — and
#: only accepts PNG payloads for these newer types.  Ordered small to large, which
#: is the order Finder expects to read them in.
ICNS_TYPES = (
    (b"ic11", 32),  # 16pt @2x
    (b"ic12", 64),  # 32pt @2x
    (b"ic07", 128),  # 128pt @1x
    (b"ic08", 256),  # 256pt @1x
    (b"ic09", 512),  # 512pt @1x
    (b"ic10", 1024),  # 512pt @2x
)


def _png_frame(size: int) -> bytes:
    """Render one icon size as PNG bytes.

    Windows Vista and later read PNG-compressed frames straight out of an ICO,
    which keeps the file small and avoids hand-rolling a BMP + AND mask.  The
    ICNS types used here are PNG-only to begin with.
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


def build_icns(types: tuple[tuple[bytes, int], ...] = ICNS_TYPES) -> bytes:
    """Build an ICNS: a magic header, a total length, then type-tagged elements.

    Every length — the file's and each element's — counts its own 8-byte header.
    """
    elements = b"".join(
        kind + struct.pack(">I", 8 + len(payload)) + payload
        for kind, payload in ((kind, _png_frame(size)) for kind, size in types)
    )
    return b"icns" + struct.pack(">I", 8 + len(elements)) + elements


def main() -> int:
    QGuiApplication([])

    for path, data, count in (
        (ICO_PATH, build_ico(), len(ICON_SIZES)),
        (ICNS_PATH, build_icns(), len(ICNS_TYPES)),
    ):
        path.write_bytes(data)
        print(f"wrote {path} ({len(data)} bytes, {count} sizes)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
