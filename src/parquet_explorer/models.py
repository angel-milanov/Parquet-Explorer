"""Qt model that presents a :class:`~parquet_explorer.data.QueryResult` in a grid."""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from PySide6.QtCore import QAbstractTableModel, QModelIndex, QObject, QPersistentModelIndex, Qt
from PySide6.QtGui import QColor

from parquet_explorer.data import QueryResult

#: Qt passes either flavour of index into the model's virtual methods.
Index = QModelIndex | QPersistentModelIndex

NULL_TEXT = "NULL"
NULL_COLOR = QColor(140, 140, 150)

_NUMERIC_PREFIXES = (
    "TINYINT",
    "SMALLINT",
    "INTEGER",
    "BIGINT",
    "HUGEINT",
    "UTINYINT",
    "USMALLINT",
    "UINTEGER",
    "UBIGINT",
    "UHUGEINT",
    "FLOAT",
    "DOUBLE",
    "DECIMAL",
    "REAL",
)


def is_numeric(type_name: str) -> bool:
    normalized = type_name.upper()
    if "[" in normalized:  # list types such as BIGINT[] are not scalars
        return False
    return normalized.startswith(_NUMERIC_PREFIXES)


def format_value(value: Any) -> str:
    """Render a DuckDB value for display in a cell."""
    if value is None:
        return NULL_TEXT
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, float):
        return repr(value)
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, (bytes, bytearray, memoryview)):
        raw = bytes(value)
        head = raw[:16].hex()
        return f"0x{head}…" if len(raw) > 16 else f"0x{head}"
    return str(value)


class QueryResultModel(QAbstractTableModel):
    """Read-only table model backed by an in-memory query result."""

    def __init__(self, result: QueryResult | None = None, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._result = result or QueryResult(columns=())

    @property
    def result(self) -> QueryResult:
        return self._result

    def set_result(self, result: QueryResult) -> None:
        self.beginResetModel()
        self._result = result
        self.endResetModel()

    # -- QAbstractTableModel ------------------------------------------------

    def rowCount(self, parent: Index = QModelIndex()) -> int:
        return 0 if parent.isValid() else self._result.row_count

    def columnCount(self, parent: Index = QModelIndex()) -> int:
        return 0 if parent.isValid() else self._result.column_count

    def data(self, index: Index, role: int = Qt.ItemDataRole.DisplayRole) -> Any:
        if not index.isValid():
            return None
        value = self._result.rows[index.row()][index.column()]

        if role in (Qt.ItemDataRole.DisplayRole, Qt.ItemDataRole.ToolTipRole):
            return format_value(value)
        if role == Qt.ItemDataRole.ForegroundRole and value is None:
            return NULL_COLOR
        if role == Qt.ItemDataRole.TextAlignmentRole:
            column = self._result.columns[index.column()]
            if is_numeric(column.type):
                return int(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            return int(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        return None

    def headerData(
        self,
        section: int,
        orientation: Qt.Orientation,
        role: int = Qt.ItemDataRole.DisplayRole,
    ) -> Any:
        if orientation == Qt.Orientation.Vertical:
            return section + 1 if role == Qt.ItemDataRole.DisplayRole else None

        if section >= self._result.column_count:
            return None
        column = self._result.columns[section]
        if role == Qt.ItemDataRole.DisplayRole:
            return column.name
        if role == Qt.ItemDataRole.ToolTipRole:
            return f"{column.name} — {column.type}"
        return None
