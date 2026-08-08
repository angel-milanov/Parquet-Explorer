from __future__ import annotations

import importlib.util
import struct
from pathlib import Path
from types import ModuleType

import pytest

from parquet_explorer.icon import ICON_SIZES, app_icon, render_pixmap

pytestmark = pytest.mark.gui

PACKAGING = Path(__file__).resolve().parent.parent / "packaging"
ICO_PATH = PACKAGING / "icon.ico"
ICNS_PATH = PACKAGING / "icon.icns"


def make_icon_module() -> ModuleType:
    """Import ``packaging/make_icon.py``, which is a script rather than a package."""
    spec = importlib.util.spec_from_file_location("make_icon", PACKAGING / "make_icon.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


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


def test_committed_icns_matches_the_frames_the_generator_declares() -> None:
    """The .icns is generated and committed, so it can drift from make_icon.py."""
    data = ICNS_PATH.read_bytes()

    assert data[:4] == b"icns", "not an icon file"
    assert struct.unpack(">I", data[4:8])[0] == len(data), "header length is not the file length"

    frames = []
    offset = 8
    while offset < len(data):
        kind = data[offset : offset + 4]
        # Every ICNS length counts its own 8-byte element header.
        length = struct.unpack(">I", data[offset + 4 : offset + 8])[0]
        payload = data[offset + 8 : offset + length]

        assert payload[:4] == b"\x89PNG", f"the {kind!r} frame is not PNG-encoded"
        # Width and height sit at a fixed offset in the PNG's leading IHDR chunk.
        width, height = struct.unpack(">II", payload[16:24])
        assert width == height, f"the {kind!r} frame is not square"

        frames.append((kind, width))
        offset += length

    assert tuple(frames) == make_icon_module().ICNS_TYPES, "regenerate with: uv run poe icon"


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
