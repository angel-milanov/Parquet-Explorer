from __future__ import annotations

from parquet_explorer import __version__
from parquet_explorer.licenses import LGPL_3_0_WITH_GPL_3_0, components


def test_every_component_is_fully_described() -> None:
    for component in components():
        assert component.name
        assert component.version
        assert component.license_name
        assert component.url.startswith("https://")
        assert len(component.text) > 500, component.name


def test_the_app_reports_its_own_version() -> None:
    app = components()[0]

    assert app.name == "Parquet Explorer"
    assert app.version == __version__
    assert app.title == f"Parquet Explorer {__version__}"


def test_everything_shipped_is_listed() -> None:
    names = {component.name for component in components()}

    assert names == {"Parquet Explorer", "DuckDB", "PySide6", "Qt", "Python"}


def test_the_lgpl_text_carries_the_gpl_it_incorporates() -> None:
    """The LGPL v3 is only half its own terms; the GPL v3 has to come with it."""
    assert "GNU LESSER GENERAL PUBLIC LICENSE" in LGPL_3_0_WITH_GPL_3_0
    assert "GNU GENERAL PUBLIC LICENSE" in LGPL_3_0_WITH_GPL_3_0
    assert LGPL_3_0_WITH_GPL_3_0.index("GNU LESSER GENERAL PUBLIC LICENSE") < (
        LGPL_3_0_WITH_GPL_3_0.index("                    GNU GENERAL PUBLIC LICENSE")
    )


def test_qt_and_pyside_share_the_lgpl_text() -> None:
    by_name = {component.name: component for component in components()}

    assert by_name["Qt"].text == LGPL_3_0_WITH_GPL_3_0
    assert by_name["PySide6"].text == LGPL_3_0_WITH_GPL_3_0


def test_license_texts_are_wrapped_narrow_enough_to_read() -> None:
    """The dialog does not re-wrap, so an over-wide text would scroll sideways."""
    for component in components():
        widest = max(len(line) for line in component.text.splitlines())
        assert widest <= 80, f"{component.name}: {widest} columns"
