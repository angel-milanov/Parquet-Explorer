from __future__ import annotations

from pathlib import Path

import duckdb
import pytest

from parquet_explorer.parquet_schema import MAGIC, SchemaError, SchemaNode, read_schema


def find(node: SchemaNode, name: str) -> SchemaNode:
    for child in node.children:
        if child.name == name:
            return child
    raise AssertionError(f"{name} is not a child of {node.name}: {[c.name for c in node.children]}")


def test_root_is_a_group_holding_the_columns(sample_parquet: Path) -> None:
    root = read_schema(sample_parquet)

    assert root.is_group is True
    assert [child.name for child in root.children] == [
        "id",
        "name",
        "score",
        "flag",
        "day",
        "maybe",
    ]


def test_leaves_carry_physical_and_annotated_types(sample_parquet: Path) -> None:
    root = read_schema(sample_parquet)

    assert find(root, "id").physical_type == "INT64"
    assert find(root, "name").physical_type == "BYTE_ARRAY"
    assert find(root, "name").converted_type == "UTF8"
    assert find(root, "flag").physical_type == "BOOLEAN"
    assert find(root, "day").converted_type == "DATE"
    # i * 1.5 makes score a DECIMAL rather than a DOUBLE, stored as a fixed leaf.
    assert find(root, "score").physical_type == "FIXED_LEN_BYTE_ARRAY"
    assert find(root, "score").converted_type == "DECIMAL"


def test_columns_written_by_duckdb_are_optional(sample_parquet: Path) -> None:
    root = read_schema(sample_parquet)

    assert {child.repetition for child in root.children} == {"optional"}


def test_a_list_keeps_its_three_level_wrapper(nested_parquet: Path) -> None:
    node = find(read_schema(nested_parquet), "a_list")

    assert node.converted_type == "LIST"
    wrapper = node.children[0]
    assert wrapper.repetition == "repeated"
    assert wrapper.children[0].physical_type == "INT32"


def test_a_struct_becomes_a_group_of_leaves(nested_parquet: Path) -> None:
    node = find(read_schema(nested_parquet), "a_struct")

    assert node.is_group is True
    assert [child.name for child in node.children] == ["x", "y"]


def test_a_map_keeps_its_key_value_group(nested_parquet: Path) -> None:
    node = find(read_schema(nested_parquet), "a_map")

    assert node.converted_type == "MAP"
    key, value = node.children[0].children
    assert (key.name, key.repetition, key.converted_type) == ("key", "required", "UTF8")
    assert value.name == "value"


def test_decimal_parameters_come_back(nested_parquet: Path) -> None:
    node = find(read_schema(nested_parquet), "a_decimal")

    assert node.converted_type == "DECIMAL"
    assert node.logical_type is not None
    assert (node.logical_type.precision, node.logical_type.scale) == (9, 3)


def test_a_fixed_length_leaf_reports_its_width(nested_parquet: Path) -> None:
    node = find(read_schema(nested_parquet), "a_big_decimal")

    assert node.physical_type == "FIXED_LEN_BYTE_ARRAY"
    assert node.type_length == 16


def test_timestamps_record_whether_they_are_utc(nested_parquet: Path) -> None:
    root = read_schema(nested_parquet)
    naive = find(root, "a_timestamp").logical_type
    zoned = find(root, "a_timestamptz").logical_type

    assert naive is not None and (naive.kind, naive.unit, naive.utc) == (
        "TIMESTAMP",
        "MICROS",
        False,
    )
    assert zoned is not None and (zoned.kind, zoned.unit, zoned.utc) == (
        "TIMESTAMP",
        "MICROS",
        True,
    )


def test_uuid_is_read_as_a_logical_type(nested_parquet: Path) -> None:
    node = find(read_schema(nested_parquet), "a_uuid")

    assert node.logical_type is not None
    assert node.logical_type.kind == "UUID"


def test_unsigned_integers_keep_their_annotation(nested_parquet: Path) -> None:
    node = find(read_schema(nested_parquet), "an_unsigned")

    assert node.converted_type == "UINT_64"


def test_a_footer_full_of_other_metadata_still_parses(tmp_path: Path) -> None:
    """Row-group statistics and field ids are fields the reader has to step over.

    Many small row groups make the footer far larger than the schema in it, which
    is the case the early exit after ``FileMetaData.schema`` exists for.
    """
    path = tmp_path / "chunked.parquet"
    connection = duckdb.connect()
    connection.execute(
        f"""
        COPY (SELECT i AS id, 'n' || i AS name FROM range(5000) t(i))
        TO '{path.as_posix()}'
        (FORMAT PARQUET, ROW_GROUP_SIZE 512, FIELD_IDS {{'id': 1, 'name': 2}})
        """
    )
    connection.close()

    root = read_schema(path)

    assert [child.name for child in root.children] == ["id", "name"]
    assert find(root, "name").converted_type == "UTF8"


def test_a_v2_footer_parses(tmp_path: Path) -> None:
    path = tmp_path / "v2.parquet"
    connection = duckdb.connect()
    connection.execute(
        f"""
        COPY (SELECT i AS id, [i] AS tags FROM range(100) t(i))
        TO '{path.as_posix()}' (FORMAT PARQUET, PARQUET_VERSION V2)
        """
    )
    connection.close()

    root = read_schema(path)

    assert [child.name for child in root.children] == ["id", "tags"]
    assert find(root, "tags").converted_type == "LIST"


def test_a_missing_file_raises(tmp_path: Path) -> None:
    with pytest.raises(SchemaError):
        read_schema(tmp_path / "nope.parquet")


def test_a_file_that_is_not_parquet_raises(tmp_path: Path) -> None:
    path = tmp_path / "not.parquet"
    path.write_bytes(b"just some bytes that are long enough to seek in")

    with pytest.raises(SchemaError, match="not a Parquet file"):
        read_schema(path)


def test_a_tiny_file_raises(tmp_path: Path) -> None:
    path = tmp_path / "tiny.parquet"
    path.write_bytes(MAGIC)

    with pytest.raises(SchemaError, match="too small"):
        read_schema(path)


def test_an_encrypted_footer_is_reported_as_such(tmp_path: Path) -> None:
    path = tmp_path / "encrypted.parquet"
    path.write_bytes(MAGIC + bytes(8) + (4).to_bytes(4, "little") + b"PARE")

    with pytest.raises(SchemaError, match="encrypted"):
        read_schema(path)


def test_a_footer_longer_than_the_file_raises(tmp_path: Path) -> None:
    path = tmp_path / "corrupt.parquet"
    path.write_bytes(MAGIC + bytes(8) + (1 << 20).to_bytes(4, "little") + MAGIC)

    with pytest.raises(SchemaError, match="corrupt"):
        read_schema(path)


def test_a_truncated_footer_raises(tmp_path: Path, sample_parquet: Path) -> None:
    """The declared footer length is right, but the Thrift bytes are garbage."""
    path = tmp_path / "truncated.parquet"
    path.write_bytes(MAGIC + bytes([0x19] * 8) + (8).to_bytes(4, "little") + MAGIC)

    with pytest.raises(SchemaError):
        read_schema(path)


def test_a_remote_path_is_refused() -> None:
    with pytest.raises(SchemaError, match="not a local file"):
        read_schema("s3://bucket/file.parquet")
