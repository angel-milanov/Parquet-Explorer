"""Turn a Parquet schema into an Avro record schema (a ``.avsc`` document).

Pure translation, no Qt and no DuckDB: the input is the tree
:mod:`parquet_explorer.parquet_schema` decodes from the file's footer.

The mapping follows Parquet's own logical-type annotations, and reads the
repetition of each field as its nullability -- ``optional`` becomes a
``["null", T]`` union defaulting to ``null``, ``required`` stays bare.  Wrapper
groups annotated ``LIST`` and ``MAP`` collapse into Avro's ``array`` and ``map``,
including the two-level layouts older writers produced.

Three Parquet types have no exact Avro counterpart and are widened deliberately:

* ``INT96`` -- the legacy timestamp -- becomes ``timestamp-micros``, matching what
  every reader materialises it as, at the cost of the nanosecond digits.
* Unsigned 64-bit integers become ``long``, which cannot hold the top half of
  their range.  Avro has no unsigned types.
* ``ENUM`` becomes ``string``: an Avro enum has to list its symbols, and a
  Parquet footer does not record them.

Nanosecond times need Avro 1.12 or later, which is where ``timestamp-nanos`` and
its siblings were added.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from parquet_explorer.parquet_schema import LogicalType, SchemaError, SchemaNode, read_schema

#: A schema is a name, an inline definition, or a union of them.
AvroType = str | dict[str, Any] | list[Any]

_NOT_A_NAME = re.compile(r"[^A-Za-z0-9_]")

#: Names Parquet gives its own wrapper groups.  They say nothing about the data,
#: so a record that lands on one is named after its path instead.
_WRAPPER_NAMES = frozenset(
    {"array", "bag", "element", "entries", "item", "key", "key_value", "list", "map", "value"}
)


def sanitize_name(name: str) -> str:
    """Return ``name`` as a legal Avro name: ``[A-Za-z_][A-Za-z0-9_]*``."""
    cleaned = _NOT_A_NAME.sub("_", name)
    if not cleaned or cleaned[0].isdigit():
        cleaned = f"_{cleaned}"
    return cleaned


class _Names:
    """Hands out unique names.

    Avro's named types -- records and fixeds -- all share one namespace, so two
    structs called ``address`` in different branches would collide.  The first
    claim on a name wins; later ones fall back to their path, then to a suffix.
    """

    def __init__(self) -> None:
        self._taken: set[str] = set()

    def take(self, *preferences: str) -> str:
        for preference in preferences:
            candidate = sanitize_name(preference)
            if candidate not in self._taken:
                self._taken.add(candidate)
                return candidate
        base = sanitize_name(preferences[-1] if preferences else "record")
        suffix = 2
        while f"{base}{suffix}" in self._taken:
            suffix += 1
        self._taken.add(f"{base}{suffix}")
        return f"{base}{suffix}"


def _preferences(node: SchemaNode, path: tuple[str, ...], suffix: str = "") -> tuple[str, str]:
    """Names to try for ``node``'s Avro type, best first."""
    own = f"{node.name}{suffix}"
    from_path = f"{'_'.join(path)}{suffix}"
    return (from_path, own) if node.name in _WRAPPER_NAMES else (own, from_path)


# -- Structure ---------------------------------------------------------------


def to_avro_schema(root: SchemaNode, name: str = "record") -> dict[str, Any]:
    """Convert a Parquet schema tree into an Avro record schema."""
    names = _Names()
    return {
        "type": "record",
        "name": names.take(name),
        "fields": [_field(child, names, (child.name,)) for child in root.children],
    }


def _field(node: SchemaNode, names: _Names, path: tuple[str, ...]) -> dict[str, Any]:
    return _entry(node, _field_type(node, names, path))


def _entry(node: SchemaNode, avro_type: AvroType) -> dict[str, Any]:
    """One entry of a record's ``fields``, given the type already worked out."""
    name = sanitize_name(node.name)
    entry: dict[str, Any] = {"name": name, "type": avro_type}
    if name != node.name:
        entry["doc"] = f"Parquet field name: {node.name}"
    if node.repetition == "optional":
        entry["default"] = None
    return entry


def _field_type(node: SchemaNode, names: _Names, path: tuple[str, ...]) -> AvroType:
    """The type of ``node`` including its repetition."""
    if node.repetition == "repeated":
        # A bare repeated field (no LIST wrapper) is a list of zero or more
        # values, so it is an array that is never itself null.
        return {"type": "array", "items": _base_type(node, names, path)}
    base = _base_type(node, names, path)
    return ["null", base] if node.repetition == "optional" else base


def _base_type(node: SchemaNode, names: _Names, path: tuple[str, ...]) -> AvroType:
    """The type of ``node`` ignoring its repetition."""
    if not node.is_group:
        return _primitive_type(node, names, path)
    annotation = _annotation(node)
    if annotation == "LIST":
        return _list_type(node, names, path)
    if annotation in ("MAP", "MAP_KEY_VALUE"):
        return _map_type(node, names, path)
    return _record_type(node, names, path)


def _annotation(node: SchemaNode) -> str | None:
    if node.logical_type is not None and node.logical_type.kind in ("LIST", "MAP"):
        return node.logical_type.kind
    if node.converted_type in ("LIST", "MAP", "MAP_KEY_VALUE"):
        return node.converted_type
    return None


def _record_type(node: SchemaNode, names: _Names, path: tuple[str, ...]) -> dict[str, Any]:
    name = names.take(*_preferences(node, path))
    return {
        "type": "record",
        "name": name,
        "fields": [_field(child, names, (*path, child.name)) for child in node.children],
    }


def _list_type(node: SchemaNode, names: _Names, path: tuple[str, ...]) -> AvroType:
    element = _list_element(node)
    if element is None:  # annotated LIST but not shaped like one
        return _record_type(node, names, path)
    child, two_level = element
    # The element keeps the list's own path: the wrapper groups between them are
    # Parquet plumbing and would only make generated names longer.
    items = (
        _base_type(child, names, path)
        if two_level  # the repeated field is itself the element, so never null
        else _field_type(child, names, path)
    )
    return {"type": "array", "items": items}


def _list_element(node: SchemaNode) -> tuple[SchemaNode, bool] | None:
    """Find a LIST's element node, and whether this is a legacy two-level list.

    The rules are Parquet's backward-compatibility rules: the repeated field is
    the element unless it is a single-field group that looks like the standard
    three-level wrapper.
    """
    if len(node.children) != 1:
        return None
    child = node.children[0]
    if child.repetition != "repeated":
        return None
    if not child.is_group or len(child.children) != 1:
        return child, True
    if child.name in ("array", f"{node.name}_tuple"):
        return child, True
    return child.children[0], False


def _map_type(node: SchemaNode, names: _Names, path: tuple[str, ...]) -> AvroType:
    pair = _map_pair(node)
    if pair is None:  # annotated MAP but not shaped like one
        return _record_type(node, names, path)
    group, key, value = pair
    key_type = _field_type(key, names, (*path, key.name))
    value_type = _field_type(value, names, (*path, value.name))
    if key_type == "string":
        return {"type": "map", "values": value_type}
    # Avro maps are string-keyed only, so anything else becomes a list of pairs.
    return {
        "type": "array",
        "items": {
            "type": "record",
            "name": names.take(*_preferences(group, path)),
            "fields": [_entry(key, key_type), _entry(value, value_type)],
        },
    }


def _map_pair(node: SchemaNode) -> tuple[SchemaNode, SchemaNode, SchemaNode] | None:
    """Return the ``(key_value group, key, value)`` of a MAP, if it has one."""
    if len(node.children) != 1:
        return None
    group = node.children[0]
    if not group.is_group or len(group.children) < 2:
        return None
    return group, group.children[0], group.children[1]


# -- Leaves ------------------------------------------------------------------


def _primitive_type(node: SchemaNode, names: _Names, path: tuple[str, ...]) -> AvroType:
    if node.logical_type is not None:
        mapped = _from_logical_type(node, node.logical_type, names, path)
        if mapped is not None:
            return mapped
    if node.converted_type is not None:
        mapped = _from_converted_type(node, names, path)
        if mapped is not None:
            return mapped
    return _from_physical_type(node, names, path)


def _from_logical_type(
    node: SchemaNode, logical: LogicalType, names: _Names, path: tuple[str, ...]
) -> AvroType | None:
    kind = logical.kind
    if kind in ("STRING", "ENUM", "JSON"):
        return "string"
    if kind == "BSON":
        return "bytes"
    if kind == "UUID":
        return {"type": "string", "logicalType": "uuid"}
    if kind == "UNKNOWN":
        return "null"
    if kind == "FLOAT16":
        return "float"
    if kind == "DECIMAL":
        return _decimal(node, logical.precision, logical.scale, names, path)
    if kind == "DATE":
        return {"type": "int", "logicalType": "date"}
    if kind == "TIME":
        if logical.unit == "MILLIS":
            return {"type": "int", "logicalType": "time-millis"}
        return {"type": "long", "logicalType": f"time-{_unit(logical.unit)}"}
    if kind == "TIMESTAMP":
        prefix = "timestamp" if logical.utc else "local-timestamp"
        return {"type": "long", "logicalType": f"{prefix}-{_unit(logical.unit)}"}
    if kind == "INTEGER":
        return _integer(logical)
    return None  # VARIANT, GEOMETRY and friends: fall back to the physical type


def _unit(unit: str | None) -> str:
    return {"MILLIS": "millis", "MICROS": "micros", "NANOS": "nanos"}.get(unit or "", "micros")


def _integer(logical: LogicalType) -> str:
    bits = logical.bit_width or 32
    if logical.signed is False:
        return "int" if bits <= 16 else "long"
    return "int" if bits <= 32 else "long"


_FROM_CONVERTED_TYPE: dict[str, AvroType] = {
    "UTF8": "string",
    "ENUM": "string",
    "JSON": "string",
    "BSON": "bytes",
    "DATE": {"type": "int", "logicalType": "date"},
    "TIME_MILLIS": {"type": "int", "logicalType": "time-millis"},
    "TIME_MICROS": {"type": "long", "logicalType": "time-micros"},
    "TIMESTAMP_MILLIS": {"type": "long", "logicalType": "timestamp-millis"},
    "TIMESTAMP_MICROS": {"type": "long", "logicalType": "timestamp-micros"},
    "UINT_8": "int",
    "UINT_16": "int",
    "UINT_32": "long",
    "UINT_64": "long",
    "INT_8": "int",
    "INT_16": "int",
    "INT_32": "int",
    "INT_64": "long",
}


def _from_converted_type(node: SchemaNode, names: _Names, path: tuple[str, ...]) -> AvroType | None:
    converted = node.converted_type
    if converted == "DECIMAL":
        return _decimal(node, node.precision, node.scale, names, path)
    if converted == "INTERVAL":
        # Parquet's interval is a 12-byte fixed, which is exactly what Avro's
        # duration logical type annotates.
        return {
            "type": "fixed",
            "name": names.take(*_preferences(node, path, "_interval")),
            "size": 12,
            "logicalType": "duration",
        }
    mapped = _FROM_CONVERTED_TYPE.get(converted or "")
    return dict(mapped) if isinstance(mapped, dict) else mapped


def _from_physical_type(node: SchemaNode, names: _Names, path: tuple[str, ...]) -> AvroType:
    physical = node.physical_type
    if physical == "BOOLEAN":
        return "boolean"
    if physical == "INT32":
        return "int"
    if physical == "INT64":
        return "long"
    if physical == "INT96":
        return {"type": "long", "logicalType": "timestamp-micros"}
    if physical == "FLOAT":
        return "float"
    if physical == "DOUBLE":
        return "double"
    if physical == "FIXED_LEN_BYTE_ARRAY":
        return {
            "type": "fixed",
            "name": names.take(*_preferences(node, path)),
            "size": node.type_length or 0,
        }
    return "bytes"  # BYTE_ARRAY, and anything a future Parquet version adds


def _decimal(
    node: SchemaNode,
    precision: int | None,
    scale: int | None,
    names: _Names,
    path: tuple[str, ...],
) -> dict[str, Any]:
    if node.physical_type == "FIXED_LEN_BYTE_ARRAY":
        schema: dict[str, Any] = {
            "type": "fixed",
            "name": names.take(*_preferences(node, path, "_decimal")),
            "size": node.type_length or 16,
        }
    else:
        # Avro has no int-backed decimal, so INT32/INT64 decimals widen to bytes.
        schema = {"type": "bytes"}
    schema["logicalType"] = "decimal"
    schema["precision"] = precision if precision is not None else 38
    schema["scale"] = scale or 0
    return schema


# -- Entry points ------------------------------------------------------------


def avro_schema(path: str | Path, name: str | None = None) -> dict[str, Any]:
    """Read ``path``'s footer and return its schema as an Avro record.

    The record is named after the file unless ``name`` says otherwise.  Raises
    :class:`~parquet_explorer.parquet_schema.SchemaError` if the file cannot be
    read as Parquet.
    """
    root = read_schema(path)
    return to_avro_schema(root, name or Path(str(path)).stem or "record")


def avro_schema_json(path: str | Path, name: str | None = None) -> str:
    """The same schema as a formatted ``.avsc`` document."""
    return json.dumps(avro_schema(path, name), indent=2)


__all__ = [
    "AvroType",
    "SchemaError",
    "avro_schema",
    "avro_schema_json",
    "sanitize_name",
    "to_avro_schema",
]
