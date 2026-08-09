from __future__ import annotations

import csv
import json
from pathlib import Path

import pytest
from PySide6.QtGui import QGuiApplication

from parquet_explorer.data import TABLE_NAME, ParquetSession
from parquet_explorer.parquet_schema import SchemaError
from parquet_explorer.window import AvroSchemaDialog, MainWindow

pytestmark = pytest.mark.gui


@pytest.fixture
def window(qtbot) -> MainWindow:
    window = MainWindow(ParquetSession())
    qtbot.addWidget(window)
    return window


def test_starts_with_run_and_export_disabled(window: MainWindow) -> None:
    assert window.run_action.isEnabled() is False
    assert window.export_action.isEnabled() is False
    assert window.avro_action.isEnabled() is False
    assert window.copy_avro_action.isEnabled() is False
    assert window.model.rowCount() == 0


def test_opening_a_file_lists_columns_and_runs_the_default_query(
    window: MainWindow, sample_parquet: Path
) -> None:
    window.open_file(sample_parquet)

    assert window.columns_tree.topLevelItemCount() == 6
    assert window.columns_tree.topLevelItem(0).text(0) == "id"
    assert window.columns_tree.topLevelItem(0).text(1) == "BIGINT"
    assert TABLE_NAME in window.editor.toPlainText()
    assert window.model.rowCount() == 100
    assert window.model.columnCount() == 6
    assert window.run_action.isEnabled() is True
    assert window.error_label.isHidden() is True


def test_window_title_shows_the_file_name(window: MainWindow, sample_parquet: Path) -> None:
    window.open_file(sample_parquet)

    assert sample_parquet.name in window.windowTitle()


def test_status_bar_reports_shape_and_timing(window: MainWindow, sample_parquet: Path) -> None:
    window.open_file(sample_parquet)

    text = window.status_label.text()
    assert "100 rows" in text
    assert "6 columns" in text
    assert "ms" in text


def test_opening_an_unreadable_file_shows_an_error(window: MainWindow, tmp_path: Path) -> None:
    window.open_file(tmp_path / "missing.parquet")

    assert window.error_label.isHidden() is False
    assert window.run_action.isEnabled() is False


def test_running_an_edited_query_updates_the_grid(window: MainWindow, sample_parquet: Path) -> None:
    window.open_file(sample_parquet)
    window.editor.setPlainText(f"SELECT id FROM {TABLE_NAME} WHERE id < 4")

    window.run_query()

    assert window.model.rowCount() == 4
    assert window.model.columnCount() == 1


def test_a_failing_query_shows_the_error_and_keeps_the_previous_rows(
    window: MainWindow, sample_parquet: Path
) -> None:
    window.open_file(sample_parquet)
    window.editor.setPlainText("SELECT * FROM does_not_exist")

    window.run_query()

    assert window.error_label.isHidden() is False
    assert "does_not_exist" in window.error_label.text()
    assert window.model.rowCount() == 100


def test_a_successful_query_clears_a_previous_error(
    window: MainWindow, sample_parquet: Path
) -> None:
    window.open_file(sample_parquet)
    window.editor.setPlainText("SELECT * FROM does_not_exist")
    window.run_query()

    window.editor.setPlainText(f"SELECT 1 FROM {TABLE_NAME} LIMIT 1")
    window.run_query()

    assert window.error_label.isHidden() is True


def test_run_query_is_a_no_op_without_an_open_file(window: MainWindow) -> None:
    window.editor.setPlainText("SELECT 1")

    window.run_query()

    assert window.model.rowCount() == 0


def test_run_query_ignores_an_empty_editor(window: MainWindow, sample_parquet: Path) -> None:
    window.open_file(sample_parquet)
    window.editor.setPlainText("   \n  ")

    window.run_query()

    assert window.model.rowCount() == 100


def test_double_clicking_a_column_inserts_its_name(
    window: MainWindow, sample_parquet: Path
) -> None:
    window.open_file(sample_parquet)
    window.editor.setPlainText("")

    window._insert_column_name(window.columns_tree.topLevelItem(1))

    assert window.editor.toPlainText() == "name"


def test_export_writes_the_current_query(
    window: MainWindow, sample_parquet: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    window.open_file(sample_parquet)
    window.editor.setPlainText(f"SELECT id FROM {TABLE_NAME} WHERE id < 2 ORDER BY id")
    destination = tmp_path / "out.csv"
    monkeypatch.setattr(
        "parquet_explorer.window.QFileDialog.getSaveFileName",
        lambda *args, **kwargs: (str(destination), ""),
    )

    window.export_csv()

    with destination.open(newline="", encoding="utf-8") as handle:
        assert list(csv.reader(handle)) == [["id"], ["0"], ["1"]]


def test_export_cancelled_writes_nothing(
    window: MainWindow, sample_parquet: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    window.open_file(sample_parquet)
    monkeypatch.setattr(
        "parquet_explorer.window.QFileDialog.getSaveFileName",
        lambda *args, **kwargs: ("", ""),
    )

    window.export_csv()

    assert list(tmp_path.glob("*.csv")) == []


def test_choose_file_opens_the_selected_path(
    window: MainWindow, sample_parquet: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        "parquet_explorer.window.QFileDialog.getOpenFileName",
        lambda *args, **kwargs: (str(sample_parquet), ""),
    )

    window.choose_file()

    assert window.model.rowCount() == 100


# -- Avro schema ------------------------------------------------------------


def test_opening_a_file_enables_the_avro_actions(window: MainWindow, sample_parquet: Path) -> None:
    window.open_file(sample_parquet)

    assert window.avro_action.isEnabled() is True
    assert window.copy_avro_action.isEnabled() is True


def test_showing_the_schema_opens_a_dialog_with_the_avsc(
    window: MainWindow, qtbot, sample_parquet: Path
) -> None:
    window.open_file(sample_parquet)

    window.show_avro_schema()

    dialog = window.avro_dialog
    assert dialog is not None
    qtbot.addWidget(dialog)
    assert dialog.isVisible() is True
    assert sample_parquet.name in dialog.windowTitle()
    schema = json.loads(dialog.text)
    assert schema["type"] == "record"
    assert [entry["name"] for entry in schema["fields"]][:2] == ["id", "name"]


def test_showing_the_schema_twice_reuses_the_dialog(
    window: MainWindow, qtbot, sample_parquet: Path
) -> None:
    window.open_file(sample_parquet)

    window.show_avro_schema()
    first = window.avro_dialog
    window.show_avro_schema()

    assert window.avro_dialog is first
    qtbot.addWidget(first)


def test_opening_another_file_refreshes_a_visible_dialog(
    window: MainWindow, qtbot, sample_parquet: Path, nested_parquet: Path
) -> None:
    window.open_file(sample_parquet)
    window.show_avro_schema()
    dialog = window.avro_dialog
    assert dialog is not None
    qtbot.addWidget(dialog)

    window.open_file(nested_parquet)

    assert nested_parquet.name in dialog.windowTitle()
    assert "a_struct" in dialog.text


def test_copying_the_schema_puts_it_on_the_clipboard(
    window: MainWindow, sample_parquet: Path
) -> None:
    window.open_file(sample_parquet)

    window.copy_avro_schema()

    assert json.loads(QGuiApplication.clipboard().text())["name"] == sample_parquet.stem


def test_the_dialog_copy_button_copies(window: MainWindow, qtbot, sample_parquet: Path) -> None:
    window.open_file(sample_parquet)
    window.show_avro_schema()
    dialog = window.avro_dialog
    assert dialog is not None
    qtbot.addWidget(dialog)
    QGuiApplication.clipboard().clear()

    dialog.copy_button.click()

    assert QGuiApplication.clipboard().text() == dialog.text
    assert dialog.copy_button.text() == "Copied"


def test_the_copy_confirmation_reverts(
    window: MainWindow, qtbot, sample_parquet: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    window.open_file(sample_parquet)
    window.show_avro_schema()
    dialog = window.avro_dialog
    assert dialog is not None
    qtbot.addWidget(dialog)
    monkeypatch.setattr(AvroSchemaDialog, "CONFIRM_MS", 10)

    dialog.copy_button.click()

    qtbot.waitUntil(lambda: dialog.copy_button.text() == "&Copy to Clipboard")


def test_the_avro_actions_are_no_ops_without_an_open_file(window: MainWindow) -> None:
    window.show_avro_schema()
    window.copy_avro_schema()

    assert window.avro_dialog is None


def test_an_unreadable_schema_is_reported_instead_of_shown(
    window: MainWindow, sample_parquet: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    window.open_file(sample_parquet)
    warnings: list[str] = []
    monkeypatch.setattr(
        "parquet_explorer.window.avro_schema_json",
        lambda *args, **kwargs: (_ for _ in ()).throw(SchemaError("footer is encrypted")),
    )
    monkeypatch.setattr(
        "parquet_explorer.window.QMessageBox.warning",
        lambda parent, title, text, *args, **kwargs: warnings.append(text),
    )

    window.show_avro_schema()

    assert window.avro_dialog is None
    assert "footer is encrypted" in warnings[0]
