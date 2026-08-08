"""The application icon, drawn at runtime.

Drawing it rather than shipping a PNG keeps the wheel free of package data and
means a source checkout, a wheel install and a PyInstaller bundle all show the
same icon.  ``packaging/make_icon.py`` renders these same shapes to the ``.ico``
that the Windows executable embeds.
"""

from __future__ import annotations

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QBrush, QColor, QIcon, QPainter, QPixmap

#: Sizes Windows, macOS and Linux ask for in taskbars, title bars and Explorer.
ICON_SIZES = (16, 24, 32, 48, 64, 128, 256)

BACKGROUND = QColor("#15263c")
BARS = (QColor("#4c9aff"), QColor("#7bc8a4"), QColor("#f2c94c"))

#: Bar geometry as fractions of the icon size: (x, top, width, height).
_BARS_GEOMETRY = (
    (0.22, 0.46, 0.16, 0.32),
    (0.42, 0.26, 0.16, 0.52),
    (0.62, 0.36, 0.16, 0.42),
)


def render_pixmap(size: int) -> QPixmap:
    """Draw the icon at ``size`` × ``size`` pixels."""
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.GlobalColor.transparent)

    painter = QPainter(pixmap)
    try:
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(Qt.PenStyle.NoPen)

        painter.setBrush(QBrush(BACKGROUND))
        radius = size * 0.18
        painter.drawRoundedRect(QRectF(0, 0, size, size), radius, radius)

        for color, (x, top, width, height) in zip(BARS, _BARS_GEOMETRY, strict=True):
            painter.setBrush(QBrush(color))
            bar = QRectF(x * size, top * size, width * size, height * size)
            corner = min(bar.width() * 0.3, 3.0)
            painter.drawRoundedRect(bar, corner, corner)
    finally:
        painter.end()

    return pixmap


def app_icon() -> QIcon:
    """The multi-resolution application icon."""
    icon = QIcon()
    for size in ICON_SIZES:
        icon.addPixmap(render_pixmap(size))
    return icon
