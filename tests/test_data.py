from __future__ import annotations

import csv
from pathlib import Path

import pytest

from parquet_explorer.data import (
    DEFAULT_QUERY,
    TABLE_NAME,
    ParquetSession,
    QueryError,
    normalize_path,
    quote_literal,
)


def test_quote_literal_escapes_single_quotes() -> None:
    assert quote_literal("O'Brien") == "'O''Brien'"


def test_normalize_path_flips_windows_separators() -> None:
    assert normalize_path(r"C:\data\file.parquet") == "C:/data/file.parquet"


def test_normalize_path_leaves_urls_alone() -> None:
    assert normalize_path("s3://bucket/file.parquet") == "s3://bucket/file.parquet"


def test_session_starts_closed(session: ParquetSession) -> None:
    assert session.is_open is False
    assert session.path is None


def test_open_returns_columns(session: ParquetSession, sample_parquet: Path) -> None:
    columns = session.open(sample_parquet)

    assert session.is_open is True
    assert [column.name for column in columns] == ["id", "name", "score", "flag", "day", "maybe"]
    assert columns[0].type == "BIGINT"
    assert columns[1].type == "VARCHAR"


def test_open_missing_file_raises(session: ParquetSession, tmp_path: Path) -> None:
    with pytest.raises(QueryError):
        session.open(tmp_path / "nope.parquet")
    assert session.is_open is False


def test_row_count(open_session: ParquetSession) -> None:
    assert open_session.row_count() == 100


def test_default_query_runs_against_the_open_file(open_session: ParquetSession) -> None:
    result = open_session.run(DEFAULT_QUERY)

    assert result.row_count == 100
    assert result.column_count == 6
    assert result.elapsed >= 0.0


def test_default_query_targets_the_registered_view() -> None:
    assert TABLE_NAME in DEFAULT_QUERY


def test_run_projects_and_filters(open_session: ParquetSession) -> None:
    result = open_session.run(f"SELECT id, name FROM {TABLE_NAME} WHERE id < 3 ORDER BY id")

    assert [column.name for column in result.columns] == ["id", "name"]
    assert result.rows == ((0, "name_0"), (1, "name_1"), (2, "name_2"))


def test_run_preserves_nulls(open_session: ParquetSession) -> None:
    result = open_session.run(f"SELECT maybe FROM {TABLE_NAME} WHERE id = 0")

    assert result.rows == ((None,),)


def test_run_invalid_sql_raises_query_error(open_session: ParquetSession) -> None:
    with pytest.raises(QueryError, match="nonexistent_column"):
        open_session.run(f"SELECT nonexistent_column FROM {TABLE_NAME}")


def test_run_multiple_statements_returns_the_last_result(open_session: ParquetSession) -> None:
    result = open_session.run("SELECT 1 AS a; SELECT 2 AS b;")

    assert [column.name for column in result.columns] == ["b"]
    assert result.rows == ((2,),)


def test_run_statement_without_rows_yields_empty_result(open_session: ParquetSession) -> None:
    result = open_session.run("CREATE OR REPLACE VIEW scratch AS SELECT 1")

    assert result.row_count == 0


def test_reopening_replaces_the_view(session: ParquetSession, sample_parquet: Path) -> None:
    session.open(sample_parquet)
    session.open(sample_parquet)

    assert session.run(f"SELECT count(*) FROM {TABLE_NAME}").rows == ((100,),)


def test_export_csv(open_session: ParquetSession, tmp_path: Path) -> None:
    destination = tmp_path / "out.csv"

    open_session.export_csv(
        f"SELECT id, name FROM {TABLE_NAME} WHERE id < 2 ORDER BY id;", destination
    )

    with destination.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.reader(handle))
    assert rows == [["id", "name"], ["0", "name_0"], ["1", "name_1"]]


def test_export_csv_reports_failures(open_session: ParquetSession, tmp_path: Path) -> None:
    with pytest.raises(QueryError):
        open_session.export_csv("SELECT * FROM missing_table", tmp_path / "out.csv")
