"""DuckDB-backed data access.  No Qt in here, so it is testable headless."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import duckdb

#: The view name the opened file is registered under, and what queries refer to.
TABLE_NAME = "data"

DEFAULT_QUERY = f"SELECT *\nFROM {TABLE_NAME}\nLIMIT 1000;"


class QueryError(Exception):
    """A SQL statement failed.  Carries DuckDB's message verbatim."""


@dataclass(frozen=True)
class Column:
    name: str
    type: str


@dataclass(frozen=True)
class QueryResult:
    """Everything the grid needs to display one query's output."""

    columns: tuple[Column, ...]
    rows: tuple[tuple[Any, ...], ...] = field(default=())
    elapsed: float = 0.0

    @property
    def row_count(self) -> int:
        return len(self.rows)

    @property
    def column_count(self) -> int:
        return len(self.columns)


def quote_literal(value: str) -> str:
    """Quote ``value`` as a DuckDB string literal."""
    return "'" + value.replace("'", "''") + "'"


def normalize_path(path: str | Path) -> str:
    """Return a path DuckDB accepts.

    Windows separators are flipped to ``/``: DuckDB treats a backslash as a
    literal character when globbing, and forward slashes work on every platform.
    """
    text = str(path)
    return text if "://" in text else text.replace("\\", "/")


class ParquetSession:
    """A DuckDB connection with (at most) one Parquet file registered as a view."""

    def __init__(self) -> None:
        self._connection = duckdb.connect()
        self._path: str | None = None

    @property
    def path(self) -> str | None:
        """The currently open file, or ``None`` when nothing is open."""
        return self._path

    @property
    def is_open(self) -> bool:
        return self._path is not None

    def open(self, path: str | Path) -> tuple[Column, ...]:
        """Register ``path`` as the :data:`TABLE_NAME` view and return its columns."""
        target = normalize_path(path)
        try:
            self._connection.execute(
                f"CREATE OR REPLACE VIEW {TABLE_NAME} AS "
                f"SELECT * FROM read_parquet({quote_literal(target)})"
            )
            columns = self.columns()
        except duckdb.Error as exc:
            raise QueryError(str(exc)) from exc
        self._path = target
        return columns

    def columns(self) -> tuple[Column, ...]:
        """Column names and types of the open file."""
        rows = self._connection.execute(f"DESCRIBE {TABLE_NAME}").fetchall()
        return tuple(Column(name=row[0], type=row[1]) for row in rows)

    def row_count(self) -> int:
        """Total rows in the open file (read from Parquet metadata, so cheap)."""
        row = self._connection.execute(f"SELECT count(*) FROM {TABLE_NAME}").fetchone()
        return int(row[0]) if row else 0

    def run(self, sql: str) -> QueryResult:
        """Execute ``sql`` and fetch the full result.

        Multiple ``;``-separated statements are allowed; the output of the last
        one that produces rows is what comes back.
        """
        started = time.perf_counter()
        try:
            cursor = self._connection.execute(sql)
            description = cursor.description
            rows = cursor.fetchall() if description else []
        except duckdb.Error as exc:
            raise QueryError(str(exc)) from exc
        elapsed = time.perf_counter() - started

        columns = tuple(Column(name=item[0], type=str(item[1])) for item in description or ())
        return QueryResult(columns=columns, rows=tuple(rows), elapsed=elapsed)

    def export_csv(self, sql: str, destination: str | Path) -> None:
        """Write the result of ``sql`` to ``destination`` as CSV with a header."""
        target = quote_literal(normalize_path(destination))
        statement = sql.strip().rstrip(";")
        try:
            self._connection.execute(f"COPY ({statement}) TO {target} (FORMAT CSV, HEADER)")
        except duckdb.Error as exc:
            raise QueryError(str(exc)) from exc

    def close(self) -> None:
        self._connection.close()
        self._path = None
