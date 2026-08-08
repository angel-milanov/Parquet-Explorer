from __future__ import annotations

import struct
from pathlib import Path

import pytest

from parquet_explorer.icon import ICON_SIZES, app_icon, render_pixmap

pytestmark = pytest.mark.gui

ICO_PATH = Path(__file__).resolve().parent.parent / "packaging" / "icon.ico"


def test_app_icon_offers_every_size(qapp) -> None:
    icon = app_icon()

    assert not icon.isNull()
    assert {size.width() for size in icon.availableSizes()} == set(ICON_SIZES)


@pytest.mark.parametrize("size", ICON_SIZES)
def test_render_pixmap_is_square(qapp, size: int) -> None:
    pixmap = render_pixmap(size)

    assert (pixmap.width(), pixmap.height()) == (size, size)


def test_render_pixmap_paints_the_body_and_leaves_corners_transparent(qapp) -> None:
    image = render_pixmap(64).toImage()

    assert image.pixelColor(32, 32).alpha() == 255
    assert image.pixelColor(0, 0).alpha() == 0


def test_committed_ico_matches_the_sizes_the_source_declares() -> None:
    """The .ico is generated and committed, so it can drift from icon.py."""
    data = ICO_PATH.read_bytes()
    _, kind, count = struct.unpack("<HHH", data[:6])

    assert kind == 1, "not an icon file"
    assert count == len(ICON_SIZES), "regenerate with: uv run python packaging/make_icon.py"

    sizes = []
    for index in range(count):
        entry = struct.unpack("<BBBBHHII", data[6 + 16 * index : 22 + 16 * index])
        width, _, _, _, _, _, length, offset = entry
        sizes.append(width or 256)
        assert data[offset : offset + 4] == b"\x89PNG", "frame is not PNG-encoded"
        assert offset + length <= len(data), "frame runs past the end of the file"

    assert tuple(sizes) == ICON_SIZES
