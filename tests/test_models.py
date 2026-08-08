from __future__ import annotations

from decimal import Decimal

import pytest
from PySide6.QtCore import QModelIndex, Qt

from parquet_explorer.data import Column, QueryResult
from parquet_explorer.models import NULL_TEXT, QueryResultModel, format_value, is_numeric

pytestmark = pytest.mark.gui


@pytest.fixture
def result() -> QueryResult:
    return QueryResult(
        columns=(Column("id", "BIGINT"), Column("name", "VARCHAR")),
        rows=((1, "a"), (2, None)),
        elapsed=0.01,
    )


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (None, NULL_TEXT),
        (True, "true"),
        (False, "false"),
        (12, "12"),
        (1.5, "1.5"),
        (Decimal("1.50"), "1.50"),
        ("text", "text"),
        (b"\x00\xff", "0x00ff"),
    ],
)
def test_format_value(value: object, expected: str) -> None:
    assert format_value(value) == expected


def test_format_value_truncates_long_blobs() -> None:
    assert format_value(bytes(32)).endswith("…")


@pytest.mark.parametrize("type_name", ["BIGINT", "DOUBLE", "DECIMAL(10,2)", "utinyint"])
def test_is_numeric_true(type_name: str) -> None:
    assert is_numeric(type_name) is True


@pytest.mark.parametrize("type_name", ["VARCHAR", "DATE", "BOOLEAN", "BIGINT[]"])
def test_is_numeric_false(type_name: str) -> None:
    assert is_numeric(type_name) is False


def test_empty_model_has_no_rows_or_columns() -> None:
    model = QueryResultModel()

    assert model.rowCount() == 0
    assert model.columnCount() == 0


def test_model_dimensions(result: QueryResult) -> None:
    model = QueryResultModel(result)

    assert model.rowCount() == 2
    assert model.columnCount() == 2


def test_model_ignores_child_parents(result: QueryResult) -> None:
    model = QueryResultModel(result)
    parent = model.index(0, 0)

    assert model.rowCount(parent) == 0
    assert model.columnCount(parent) == 0


def test_display_role(result: QueryResult) -> None:
    model = QueryResultModel(result)

    assert model.data(model.index(0, 1), Qt.ItemDataRole.DisplayRole) == "a"
    assert model.data(model.index(1, 1), Qt.ItemDataRole.DisplayRole) == NULL_TEXT


def test_null_cells_get_a_muted_foreground(result: QueryResult) -> None:
    model = QueryResultModel(result)

    assert model.data(model.index(1, 1), Qt.ItemDataRole.ForegroundRole) is not None
    assert model.data(model.index(0, 1), Qt.ItemDataRole.ForegroundRole) is None


def test_numeric_columns_are_right_aligned(result: QueryResult) -> None:
    model = QueryResultModel(result)
    numeric = model.data(model.index(0, 0), Qt.ItemDataRole.TextAlignmentRole)
    text = model.data(model.index(0, 1), Qt.ItemDataRole.TextAlignmentRole)

    assert numeric & int(Qt.AlignmentFlag.AlignRight)
    assert text & int(Qt.AlignmentFlag.AlignLeft)


def test_invalid_index_returns_none(result: QueryResult) -> None:
    model = QueryResultModel(result)

    assert model.data(QModelIndex()) is None


def test_header_data(result: QueryResult) -> None:
    model = QueryResultModel(result)

    assert model.headerData(0, Qt.Orientation.Horizontal, Qt.ItemDataRole.DisplayRole) == "id"
    tooltip = model.headerData(0, Qt.Orientation.Horizontal, Qt.ItemDataRole.ToolTipRole)
    assert "BIGINT" in tooltip
    assert model.headerData(0, Qt.Orientation.Vertical, Qt.ItemDataRole.DisplayRole) == 1


def test_set_result_resets_the_model(result: QueryResult) -> None:
    model = QueryResultModel()
    seen: list[str] = []
    model.modelAboutToBeReset.connect(lambda: seen.append("about"))
    model.modelReset.connect(lambda: seen.append("reset"))

    model.set_result(result)

    assert seen == ["about", "reset"]
    assert model.result is result
    assert model.rowCount() == 2
