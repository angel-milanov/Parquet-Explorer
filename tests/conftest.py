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


@pytest.fixture
def session() -> ParquetSession:
    session = ParquetSession()
    yield session
    session.close()


@pytest.fixture
def open_session(session: ParquetSession, sample_parquet: Path) -> ParquetSession:
    session.open(sample_parquet)
    return session
