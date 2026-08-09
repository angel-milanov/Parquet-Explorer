"""What Parquet Explorer is built from, and the license each part is under.

Kept apart from the dialog that displays it so the list can be checked without a
display. The texts themselves live in :mod:`parquet_explorer.license_texts`.
"""

from __future__ import annotations

from dataclasses import dataclass

from parquet_explorer import __version__
from parquet_explorer.license_texts import (
    GPL_3_0,
    LGPL_3_0,
    MIT_DUCKDB,
    MIT_PARQUET_EXPLORER,
    PSF_2_0,
)

HOMEPAGE = "https://github.com/angel-milanov/parquet-explorer"

_INCORPORATION_NOTE = """

----------------------------------------------------------------------

The GNU Lesser General Public License v3 above incorporates the terms and
conditions of version 3 of the GNU General Public License, which is therefore
reproduced in full below.

----------------------------------------------------------------------

"""

#: The LGPL v3 opens by stating that it "incorporates the terms and conditions
#: of version 3 of the GNU General Public License", so half of what binds a
#: reader of the LGPL is in the GPL. Showing one without the other would be an
#: incomplete answer to "what license is Qt under?".
LGPL_3_0_WITH_GPL_3_0 = LGPL_3_0 + _INCORPORATION_NOTE + GPL_3_0


@dataclass(frozen=True, slots=True)
class Component:
    """One piece of software the app ships, and the license covering it."""

    name: str
    version: str
    license_name: str
    url: str
    text: str

    @property
    def title(self) -> str:
        """``name version``, or just the name for anything unversioned."""
        return f"{self.name} {self.version}" if self.version else self.name


def components() -> tuple[Component, ...]:
    """Everything shipped, in the order the About dialog lists it.

    Versions are read at runtime rather than pinned here, so a standalone bundle
    reports the libraries it actually contains instead of what the source tree
    was pinned against.
    """
    import platform

    import duckdb
    from PySide6 import __version__ as pyside_version
    from PySide6.QtCore import qVersion

    return (
        Component(
            name="Parquet Explorer",
            version=__version__,
            license_name="MIT License",
            url=HOMEPAGE,
            text=MIT_PARQUET_EXPLORER,
        ),
        Component(
            name="DuckDB",
            version=duckdb.__version__,
            license_name="MIT License",
            url="https://duckdb.org",
            text=MIT_DUCKDB,
        ),
        Component(
            name="PySide6",
            version=pyside_version,
            license_name="GNU LGPL v3",
            url="https://doc.qt.io/qtforpython/",
            text=LGPL_3_0_WITH_GPL_3_0,
        ),
        Component(
            name="Qt",
            version=qVersion(),
            license_name="GNU LGPL v3",
            url="https://www.qt.io",
            text=LGPL_3_0_WITH_GPL_3_0,
        ),
        Component(
            name="Python",
            version=platform.python_version(),
            license_name="PSF License Agreement v2",
            url="https://www.python.org",
            text=PSF_2_0,
        ),
    )
