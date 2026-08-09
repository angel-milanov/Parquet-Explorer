from __future__ import annotations

from pathlib import Path

import duckdb
import pytest

from parquet_explorer.data import ParquetSession


@pytest.fixture(scope="session")
def sample_parquet(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """A small Parquet file covering the value shapes the grid has to render."""
    path = tmp_path_factory.mktemp("data") / "sample.parquet"
    connection = duckdb.connect()
    connection.execute(
        f"""
        COPY (
            SELECT
                i                                   AS id,
                'name_' || i                        AS name,
                i * 1.5                             AS score,
                (i % 3 = 0)                         AS flag,
                DATE '2024-01-01' + i::INTEGER      AS day,
                CASE WHEN i % 5 = 0 THEN NULL ELSE i END AS maybe
            FROM range(100) t(i)
        ) TO '{path.as_posix()}' (FORMAT PARQUET)
        """
    )
    connection.close()
    return path


@pytest.fixture(scope="session")
def nested_parquet(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """A Parquet file covering the annotated and nested types Avro has to map.

    Separate from :func:`sample_parquet` rather than folded into it because the
    grid tests assert on that file's exact six-column shape.
    """
    path = tmp_path_factory.mktemp("data") / "nested.parquet"
    connection = duckdb.connect()
    connection.execute(
        f"""
        COPY (
            SELECT
                1::INTEGER                          AS an_int,
                'x'                                 AS a_string,
                [1, 2, 3]                           AS a_list,
                {{'x': 1, 'y': 'z'}}                AS a_struct,
                MAP(['k'], [1])                     AS a_map,
                MAP([1], ['v'])                     AS an_int_map,
                3.14::DECIMAL(9, 3)                 AS a_decimal,
                123456789.1::DECIMAL(38, 9)         AS a_big_decimal,
                DATE '2024-01-01'                   AS a_date,
                TIMESTAMP '2024-01-01 12:00:00'     AS a_timestamp,
                TIMESTAMPTZ '2024-01-01 12:00:00'   AS a_timestamptz,
                TIME '12:00:00'                     AS a_time,
                gen_random_uuid()                   AS a_uuid,
                'blob'::BLOB                        AS a_blob,
                1.5::FLOAT                          AS a_float,
                true                                AS a_bool,
                1::UBIGINT                          AS an_unsigned,
                [{{'a': 1}}]                        AS a_list_of_structs
        ) TO '{path.as_posix()}' (FORMAT PARQUET)
        """
    )
    connection.close()
    return path


@pytest.fixture
def session() -> ParquetSession:
    session = ParquetSession()
    yield session
    session.close()


@pytest.fixture
def open_session(session: ParquetSession, sample_parquet: Path) -> ParquetSession:
    session.open(sample_parquet)
    return session
