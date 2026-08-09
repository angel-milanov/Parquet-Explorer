from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from parquet_explorer.avro import avro_schema, avro_schema_json, sanitize_name, to_avro_schema
from parquet_explorer.parquet_schema import LogicalType, SchemaNode

# Hand-built schema trees cover shapes DuckDB's writer never produces -- required
# fields, legacy two-level lists, INT96 -- which is most of what the mapping has
# to get right.  The tests at the bottom go through a real file end to end.


def leaf(name: str, physical: str, repetition: str = "optional", **kwargs: Any) -> SchemaNode:
    return SchemaNode(name=name, repetition=repetition, physical_type=physical, **kwargs)


def group(
    name: str, *children: SchemaNode, repetition: str = "optional", **kwargs: Any
) -> SchemaNode:
    return SchemaNode(name=name, repetition=repetition, children=children, **kwargs)


def root(*children: SchemaNode) -> SchemaNode:
    return group("schema", *children, repetition="required")


def convert(*children: SchemaNode, name: str = "record") -> dict[str, Any]:
    return to_avro_schema(root(*children), name)


def field_type(node: SchemaNode) -> Any:
    return convert(node)["fields"][0]["type"]


# -- names -------------------------------------------------------------------


@pytest.mark.parametrize(
    ("name", "expected"),
    [
        ("plain", "plain"),
        ("with space", "with_space"),
        ("dots.and-dashes", "dots_and_dashes"),
        ("2024", "_2024"),
        ("", "_"),
        ("héllo", "h_llo"),
    ],
)
def test_sanitize_name(name: str, expected: str) -> None:
    assert sanitize_name(name) == expected


def test_a_renamed_field_says_what_it_was_called() -> None:
    entry = convert(leaf("total (eur)", "INT32"))["fields"][0]

    assert entry["name"] == "total__eur_"
    assert entry["doc"] == "Parquet field name: total (eur)"


def test_record_names_are_unique_across_branches() -> None:
    schema = convert(
        group("outer", group("detail", leaf("a", "INT32"))),
        group("other", group("detail", leaf("b", "INT32"))),
    )

    first = schema["fields"][0]["type"][1]["fields"][0]["type"][1]["name"]
    second = schema["fields"][1]["type"][1]["fields"][0]["type"][1]["name"]
    assert first == "detail"
    assert second == "other_detail"
    assert first != second


def test_the_record_is_named_after_whatever_it_is_given() -> None:
    assert convert(leaf("a", "INT32"), name="sales")["name"] == "sales"
    assert convert(leaf("a", "INT32"), name="2024 sales")["name"] == "_2024_sales"


# -- nullability -------------------------------------------------------------


def test_an_optional_field_is_a_nullable_union_defaulting_to_null() -> None:
    entry = convert(leaf("a", "INT32"))["fields"][0]

    assert entry["type"] == ["null", "int"]
    assert entry["default"] is None


def test_a_required_field_is_not_a_union() -> None:
    entry = convert(leaf("a", "INT32", repetition="required"))["fields"][0]

    assert entry["type"] == "int"
    assert "default" not in entry


def test_a_bare_repeated_field_is_an_array() -> None:
    assert field_type(leaf("a", "INT32", repetition="repeated")) == {
        "type": "array",
        "items": "int",
    }


# -- structure ---------------------------------------------------------------


def test_a_group_becomes_a_record() -> None:
    assert field_type(group("point", leaf("x", "DOUBLE"), leaf("y", "DOUBLE"))) == [
        "null",
        {
            "type": "record",
            "name": "point",
            "fields": [
                {"name": "x", "type": ["null", "double"], "default": None},
                {"name": "y", "type": ["null", "double"], "default": None},
            ],
        },
    ]


def test_a_three_level_list_collapses_to_an_array() -> None:
    node = group(
        "tags",
        group("list", leaf("element", "BYTE_ARRAY", converted_type="UTF8"), repetition="repeated"),
        converted_type="LIST",
    )

    assert field_type(node) == ["null", {"type": "array", "items": ["null", "string"]}]


def test_a_list_of_required_elements_has_no_null_in_its_items() -> None:
    node = group(
        "tags",
        group("list", leaf("element", "INT32", repetition="required"), repetition="repeated"),
        converted_type="LIST",
    )

    assert field_type(node) == ["null", {"type": "array", "items": "int"}]


def test_a_two_level_list_of_primitives_collapses_too() -> None:
    node = group("tags", leaf("element", "INT32", repetition="repeated"), converted_type="LIST")

    assert field_type(node) == ["null", {"type": "array", "items": "int"}]


def test_a_legacy_list_named_array_is_the_element_itself() -> None:
    node = group(
        "tags",
        group("array", leaf("x", "INT32"), repetition="repeated"),
        converted_type="LIST",
    )
    items = field_type(node)[1]["items"]

    assert items["type"] == "record"
    assert [entry["name"] for entry in items["fields"]] == ["x"]


def test_a_legacy_list_of_multi_field_groups_is_the_element_itself() -> None:
    node = group(
        "pairs",
        group("wrapper", leaf("x", "INT32"), leaf("y", "INT32"), repetition="repeated"),
        converted_type="LIST",
    )
    items = field_type(node)[1]["items"]

    assert [entry["name"] for entry in items["fields"]] == ["x", "y"]


def test_a_list_annotation_on_something_else_falls_back_to_a_record() -> None:
    node = group("odd", leaf("x", "INT32"), converted_type="LIST")

    assert field_type(node)[1]["type"] == "record"


def test_a_string_keyed_map_becomes_an_avro_map() -> None:
    node = group(
        "counts",
        group(
            "key_value",
            leaf("key", "BYTE_ARRAY", repetition="required", converted_type="UTF8"),
            leaf("value", "INT32"),
            repetition="repeated",
        ),
        converted_type="MAP",
    )

    assert field_type(node) == ["null", {"type": "map", "values": ["null", "int"]}]


def test_a_map_with_other_keys_becomes_an_array_of_pairs() -> None:
    node = group(
        "counts",
        group(
            "key_value",
            leaf("key", "INT32", repetition="required"),
            leaf("value", "INT32"),
            repetition="repeated",
        ),
        converted_type="MAP",
    )

    assert field_type(node) == [
        "null",
        {
            "type": "array",
            "items": {
                "type": "record",
                "name": "counts",
                "fields": [
                    {"name": "key", "type": "int"},
                    {"name": "value", "type": ["null", "int"], "default": None},
                ],
            },
        },
    ]


def test_a_map_annotation_on_something_else_falls_back_to_a_record() -> None:
    node = group("odd", leaf("x", "INT32"), converted_type="MAP")

    assert field_type(node)[1]["type"] == "record"


def test_wrapper_group_names_do_not_become_record_names() -> None:
    node = group(
        "orders",
        group("list", group("element", leaf("id", "INT32")), repetition="repeated"),
        converted_type="LIST",
    )

    assert field_type(node)[1]["items"][1]["name"] == "orders"


# -- leaves ------------------------------------------------------------------


@pytest.mark.parametrize(
    ("physical", "expected"),
    [
        ("BOOLEAN", "boolean"),
        ("INT32", "int"),
        ("INT64", "long"),
        ("FLOAT", "float"),
        ("DOUBLE", "double"),
        ("BYTE_ARRAY", "bytes"),
    ],
)
def test_physical_types_without_annotations(physical: str, expected: str) -> None:
    assert field_type(leaf("a", physical, repetition="required")) == expected


@pytest.mark.parametrize(
    ("converted", "expected"),
    [
        ("UTF8", "string"),
        ("ENUM", "string"),
        ("JSON", "string"),
        ("BSON", "bytes"),
        ("INT_8", "int"),
        ("INT_16", "int"),
        ("INT_32", "int"),
        ("INT_64", "long"),
        ("UINT_8", "int"),
        ("UINT_16", "int"),
        ("UINT_32", "long"),
        ("UINT_64", "long"),
    ],
)
def test_converted_types_that_map_to_a_plain_avro_type(converted: str, expected: str) -> None:
    node = leaf("a", "BYTE_ARRAY", repetition="required", converted_type=converted)

    assert field_type(node) == expected


@pytest.mark.parametrize(
    ("converted", "expected"),
    [
        ("DATE", {"type": "int", "logicalType": "date"}),
        ("TIME_MILLIS", {"type": "int", "logicalType": "time-millis"}),
        ("TIME_MICROS", {"type": "long", "logicalType": "time-micros"}),
        ("TIMESTAMP_MILLIS", {"type": "long", "logicalType": "timestamp-millis"}),
        ("TIMESTAMP_MICROS", {"type": "long", "logicalType": "timestamp-micros"}),
    ],
)
def test_converted_date_and_time_types(converted: str, expected: dict[str, Any]) -> None:
    node = leaf("a", "INT64", repetition="required", converted_type=converted)

    assert field_type(node) == expected


@pytest.mark.parametrize(
    ("unit", "utc", "expected"),
    [
        ("MILLIS", True, "timestamp-millis"),
        ("MICROS", True, "timestamp-micros"),
        ("NANOS", True, "timestamp-nanos"),
        ("MICROS", False, "local-timestamp-micros"),
        ("NANOS", False, "local-timestamp-nanos"),
    ],
)
def test_a_timestamp_maps_by_unit_and_time_zone(unit: str, utc: bool, expected: str) -> None:
    node = leaf(
        "a",
        "INT64",
        repetition="required",
        logical_type=LogicalType("TIMESTAMP", unit=unit, utc=utc),
    )

    assert field_type(node) == {"type": "long", "logicalType": expected}


def test_a_millisecond_time_stays_a_32_bit_int() -> None:
    node = leaf(
        "a", "INT32", repetition="required", logical_type=LogicalType("TIME", unit="MILLIS")
    )

    assert field_type(node) == {"type": "int", "logicalType": "time-millis"}


def test_uuid_annotates_a_string() -> None:
    node = leaf(
        "a",
        "FIXED_LEN_BYTE_ARRAY",
        repetition="required",
        type_length=16,
        logical_type=LogicalType("UUID"),
    )

    assert field_type(node) == {"type": "string", "logicalType": "uuid"}


def test_an_unsigned_64_bit_integer_widens_to_long() -> None:
    node = leaf(
        "a",
        "INT64",
        repetition="required",
        logical_type=LogicalType("INTEGER", bit_width=64, signed=False),
    )

    assert field_type(node) == "long"


def test_a_small_unsigned_integer_stays_an_int() -> None:
    node = leaf(
        "a",
        "INT32",
        repetition="required",
        logical_type=LogicalType("INTEGER", bit_width=16, signed=False),
    )

    assert field_type(node) == "int"


def test_int96_becomes_a_microsecond_timestamp() -> None:
    node = leaf("a", "INT96", repetition="required")

    assert field_type(node) == {"type": "long", "logicalType": "timestamp-micros"}


def test_an_integer_backed_decimal_widens_to_bytes() -> None:
    node = leaf(
        "amount",
        "INT32",
        repetition="required",
        converted_type="DECIMAL",
        logical_type=LogicalType("DECIMAL", precision=9, scale=3),
    )

    assert field_type(node) == {
        "type": "bytes",
        "logicalType": "decimal",
        "precision": 9,
        "scale": 3,
    }


def test_a_fixed_length_decimal_stays_fixed() -> None:
    node = leaf(
        "amount",
        "FIXED_LEN_BYTE_ARRAY",
        repetition="required",
        type_length=16,
        converted_type="DECIMAL",
        logical_type=LogicalType("DECIMAL", precision=38, scale=9),
    )

    assert field_type(node) == {
        "type": "fixed",
        "name": "amount_decimal",
        "size": 16,
        "logicalType": "decimal",
        "precision": 38,
        "scale": 9,
    }


def test_an_interval_becomes_avros_duration() -> None:
    node = leaf(
        "span",
        "FIXED_LEN_BYTE_ARRAY",
        repetition="required",
        type_length=12,
        converted_type="INTERVAL",
    )

    assert field_type(node) == {
        "type": "fixed",
        "name": "span_interval",
        "size": 12,
        "logicalType": "duration",
    }


def test_a_plain_fixed_length_leaf_becomes_a_fixed() -> None:
    node = leaf("hash", "FIXED_LEN_BYTE_ARRAY", repetition="required", type_length=32)

    assert field_type(node) == {"type": "fixed", "name": "hash", "size": 32}


def test_a_null_typed_column_becomes_null() -> None:
    node = leaf("a", "INT32", repetition="required", logical_type=LogicalType("UNKNOWN"))

    assert field_type(node) == "null"


def test_an_unmapped_logical_type_falls_back_to_the_physical_one() -> None:
    node = leaf("a", "BYTE_ARRAY", repetition="required", logical_type=LogicalType("GEOMETRY"))

    assert field_type(node) == "bytes"


# -- end to end --------------------------------------------------------------


def test_a_real_file_converts_to_a_record_named_after_it(sample_parquet: Path) -> None:
    schema = avro_schema(sample_parquet)

    assert schema["type"] == "record"
    assert schema["name"] == "sample"
    assert [entry["name"] for entry in schema["fields"]] == [
        "id",
        "name",
        "score",
        "flag",
        "day",
        "maybe",
    ]
    assert schema["fields"][0]["type"] == ["null", "long"]
    assert schema["fields"][1]["type"] == ["null", "string"]
    assert schema["fields"][2]["type"] == [
        "null",
        {
            "type": "fixed",
            "name": "score_decimal",
            "size": 16,
            "logicalType": "decimal",
            "precision": 21,
            "scale": 1,
        },
    ]
    assert schema["fields"][3]["type"] == ["null", "boolean"]
    assert schema["fields"][4]["type"] == ["null", {"type": "int", "logicalType": "date"}]


def test_the_record_name_can_be_overridden(sample_parquet: Path) -> None:
    assert avro_schema(sample_parquet, "orders")["name"] == "orders"


def test_the_json_form_is_indented_and_parses_back(sample_parquet: Path) -> None:
    text = avro_schema_json(sample_parquet)

    assert text.startswith("{\n")
    assert json.loads(text) == avro_schema(sample_parquet)


def test_nested_types_survive_the_round_trip(nested_parquet: Path) -> None:
    fields = {entry["name"]: entry["type"] for entry in avro_schema(nested_parquet)["fields"]}

    assert fields["a_list"] == ["null", {"type": "array", "items": ["null", "int"]}]
    assert fields["a_map"] == ["null", {"type": "map", "values": ["null", "int"]}]
    assert fields["an_int_map"][1]["type"] == "array"
    assert fields["a_struct"][1]["type"] == "record"
    assert fields["a_uuid"] == ["null", {"type": "string", "logicalType": "uuid"}]
    assert fields["a_timestamp"] == [
        "null",
        {"type": "long", "logicalType": "local-timestamp-micros"},
    ]
    assert fields["a_timestamptz"] == ["null", {"type": "long", "logicalType": "timestamp-micros"}]
    assert fields["a_blob"] == ["null", "bytes"]
    assert fields["an_unsigned"] == ["null", "long"]
    assert fields["a_list_of_structs"][1]["items"][1]["type"] == "record"


def test_every_named_type_in_a_real_file_is_unique(nested_parquet: Path) -> None:
    names: list[str] = []

    def walk(schema: Any) -> None:
        if isinstance(schema, list):
            for member in schema:
                walk(member)
        elif isinstance(schema, dict):
            if schema.get("type") in ("record", "fixed", "enum"):
                names.append(schema["name"])
            for value in schema.values():
                walk(value)

    walk(avro_schema(nested_parquet))

    assert names
    assert len(names) == len(set(names))
