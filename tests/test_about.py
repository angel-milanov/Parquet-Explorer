from __future__ import annotations

import pytest

from parquet_explorer import __version__
from parquet_explorer.about import AboutDialog
from parquet_explorer.data import ParquetSession
from parquet_explorer.licenses import components
from parquet_explorer.window import MainWindow

pytestmark = pytest.mark.gui


@pytest.fixture
def dialog(qtbot) -> AboutDialog:
    dialog = AboutDialog()
    qtbot.addWidget(dialog)
    return dialog


def test_shows_the_version_banner(dialog: AboutDialog) -> None:
    text = dialog.version_label.text()

    assert __version__ in text
    assert "DuckDB" in text
    assert "Qt" in text


def test_lists_every_component(dialog: AboutDialog) -> None:
    listed = [
        dialog.component_list.item(row).text() for row in range(dialog.component_list.count())
    ]

    assert len(listed) == len(components())
    assert any(line.startswith("DuckDB ") and "MIT" in line for line in listed)
    assert any(line.startswith("Qt ") and "LGPL" in line for line in listed)


def test_opens_on_the_first_license(dialog: AboutDialog) -> None:
    assert dialog.component_list.currentRow() == 0
    assert "MIT License" in dialog.license_view.toPlainText()
    assert "Parquet Explorer" in dialog.license_heading.text()


def test_selecting_a_component_shows_its_license(dialog: AboutDialog) -> None:
    row = next(i for i, component in enumerate(components()) if component.name == "Qt")

    dialog.component_list.setCurrentRow(row)

    text = dialog.license_view.toPlainText()
    assert "GNU LESSER GENERAL PUBLIC LICENSE" in text
    assert "GNU GENERAL PUBLIC LICENSE" in text
    assert "qt.io" in dialog.license_heading.text()


def test_an_out_of_range_row_is_ignored(dialog: AboutDialog) -> None:
    """Clearing the list emits currentRowChanged(-1) before the widget is gone."""
    before = dialog.license_view.toPlainText()

    dialog.show_license(-1)

    assert dialog.license_view.toPlainText() == before


def test_copy_version_info_puts_the_banner_on_the_clipboard(dialog: AboutDialog, qapp) -> None:
    dialog.copy_version_info()

    assert __version__ in qapp.clipboard().text()


def test_the_help_menu_opens_the_dialog(qtbot, monkeypatch: pytest.MonkeyPatch) -> None:
    window = MainWindow(ParquetSession())
    qtbot.addWidget(window)
    opened: list[AboutDialog] = []
    monkeypatch.setattr(
        "parquet_explorer.window.AboutDialog.exec",
        lambda self: opened.append(self),
    )

    window.about_action.trigger()

    assert len(opened) == 1
    assert opened[0].windowTitle() == "About Parquet Explorer"
