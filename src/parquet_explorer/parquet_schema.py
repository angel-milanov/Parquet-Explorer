"""Read a Parquet file's schema out of its own footer.

No DuckDB and no Qt in here.  A Parquet footer is a Thrift *compact protocol*
encoding of ``FileMetaData``, and what follows decodes the one field of it that
describes columns.  Going to the file rather than asking a query engine to
describe the view is what keeps the details an Avro schema needs: repetition
(``required`` / ``optional`` / ``repeated``, i.e. nullability), the logical-type
annotations, and the wrapper groups that spell out ``LIST`` and ``MAP``.  A
flattened ``DESCRIBE`` has already thrown all of that away.

The Thrift encoding is self-describing enough to skip fields we do not care
about, so only ``FileMetaData.schema`` is interpreted; everything else in the
footer -- row groups, statistics, key/value metadata -- is stepped over.
"""

from __future__ import annotations

import contextlib
import os
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

#: The four bytes a Parquet file both starts and ends with.
MAGIC = b"PAR1"
#: What the last four bytes are instead when the footer itself is encrypted.
ENCRYPTED_MAGIC = b"PARE"


class SchemaError(Exception):
    """The file could not be read as Parquet."""


# -- Thrift compact protocol -------------------------------------------------

_STOP = 0x00
_TRUE = 0x01
_FALSE = 0x02
_BYTE = 0x03
_I16 = 0x04
_I32 = 0x05
_I64 = 0x06
_DOUBLE = 0x07
_BINARY = 0x08
_LIST = 0x09
_SET = 0x0A
_MAP = 0x0B
_STRUCT = 0x0C
_UUID = 0x0D

_INTEGERS = (_I16, _I32, _I64)

#: Called with ``(field_id, type_id)``; returns True if it consumed the value.
Visitor = Callable[[int, int], bool]


class _Reader:
    """Enough of Thrift's compact protocol to walk a Parquet footer."""

    def __init__(self, data: bytes) -> None:
        self._data = data
        self._pos = 0

    def byte(self) -> int:
        try:
            value = self._data[self._pos]
        except IndexError:
            raise SchemaError("truncated Parquet footer") from None
        self._pos += 1
        return value

    def advance(self, count: int) -> None:
        if self._pos + count > len(self._data):
            raise SchemaError("truncated Parquet footer")
        self._pos += count

    def varint(self) -> int:
        result = shift = 0
        while True:
            byte = self.byte()
            result |= (byte & 0x7F) << shift
            if not byte & 0x80:
                return result
            shift += 7
            if shift > 70:
                raise SchemaError("malformed varint in Parquet footer")

    def integer(self) -> int:
        """A zigzag-encoded varint, which is how i16/i32/i64 are written."""
        value = self.varint()
        return (value >> 1) ^ -(value & 1)

    def binary(self) -> bytes:
        length = self.varint()
        end = self._pos + length
        if length < 0 or end > len(self._data):
            raise SchemaError("truncated Parquet footer")
        chunk = self._data[self._pos : end]
        self._pos = end
        return chunk

    def text(self) -> str:
        return self.binary().decode("utf-8", "replace")

    def list_header(self) -> tuple[int, int]:
        """Return ``(size, element_type)``.  Sizes over 14 spill into a varint."""
        header = self.byte()
        size = header >> 4
        if size == 0x0F:
            size = self.varint()
        return size, header & 0x0F

    def read_struct(self, visit: Visitor) -> None:
        """Walk one struct, handing each field to ``visit`` and skipping the rest."""
        field_id = 0
        while True:
            header = self.byte()
            type_id = header & 0x0F
            if type_id == _STOP:
                return
            delta = header >> 4
            field_id = field_id + delta if delta else self.integer()
            if not visit(field_id, type_id):
                self.skip(type_id)

    def skip(self, type_id: int) -> None:
        if type_id in (_TRUE, _FALSE):
            return  # booleans are encoded in the field header itself
        if type_id == _BYTE:
            self.byte()
        elif type_id in _INTEGERS:
            self.integer()
        elif type_id == _DOUBLE:
            self.advance(8)
        elif type_id == _UUID:
            self.advance(16)
        elif type_id == _BINARY:
            self.binary()
        elif type_id in (_LIST, _SET):
            size, element_type = self.list_header()
            for _ in range(size):
                self.skip(element_type)
        elif type_id == _MAP:
            size = self.varint()
            if size:
                kinds = self.byte()
                for _ in range(size):
                    self.skip(kinds >> 4)
                    self.skip(kinds & 0x0F)
        elif type_id == _STRUCT:
            self.read_struct(_skip_everything)
        else:
            raise SchemaError(f"unsupported Thrift type {type_id} in Parquet footer")


def _skip_everything(field_id: int, type_id: int) -> bool:
    return False


# -- Parquet's enums ---------------------------------------------------------

_PHYSICAL_TYPES = (
    "BOOLEAN",
    "INT32",
    "INT64",
    "INT96",
    "FLOAT",
    "DOUBLE",
    "BYTE_ARRAY",
    "FIXED_LEN_BYTE_ARRAY",
)

_REPETITIONS = ("required", "optional", "repeated")

_CONVERTED_TYPES = (
    "UTF8",
    "MAP",
    "MAP_KEY_VALUE",
    "LIST",
    "ENUM",
    "DECIMAL",
    "DATE",
    "TIME_MILLIS",
    "TIME_MICROS",
    "TIMESTAMP_MILLIS",
    "TIMESTAMP_MICROS",
    "UINT_8",
    "UINT_16",
    "UINT_32",
    "UINT_64",
    "INT_8",
    "INT_16",
    "INT_32",
    "INT_64",
    "JSON",
    "BSON",
    "INTERVAL",
)

#: ``LogicalType`` is a Thrift union, so the field id *is* the kind.
_LOGICAL_TYPES = {
    1: "STRING",
    2: "MAP",
    3: "LIST",
    4: "ENUM",
    5: "DECIMAL",
    6: "DATE",
    7: "TIME",
    8: "TIMESTAMP",
    10: "INTEGER",
    11: "UNKNOWN",
    12: "JSON",
    13: "BSON",
    14: "UUID",
    15: "FLOAT16",
    16: "VARIANT",
    17: "GEOMETRY",
    18: "GEOGRAPHY",
}

_TIME_UNITS = {1: "MILLIS", 2: "MICROS", 3: "NANOS"}


def _enum_name(names: tuple[str, ...], value: int) -> str | None:
    """Names are indexed by the enum value; unknown values read as ``None``."""
    return names[value] if 0 <= value < len(names) else None


@dataclass(frozen=True)
class LogicalType:
    """A Parquet ``LogicalType`` annotation and whichever parameters it carries."""

    kind: str
    unit: str | None = None
    utc: bool | None = None
    precision: int | None = None
    scale: int | None = None
    bit_width: int | None = None
    signed: bool | None = None


@dataclass(frozen=True)
class SchemaNode:
    """One node of the Parquet schema tree.

    Groups (records, and the wrappers around lists and maps) have no
    ``physical_type``; leaves have one and no children.
    """

    name: str
    repetition: str = "required"
    physical_type: str | None = None
    type_length: int | None = None
    converted_type: str | None = None
    logical_type: LogicalType | None = None
    precision: int | None = None
    scale: int | None = None
    children: tuple[SchemaNode, ...] = ()

    @property
    def is_group(self) -> bool:
        return self.physical_type is None


# -- Decoding ----------------------------------------------------------------


@dataclass
class _Element:
    """A flat ``SchemaElement``, before the tree is rebuilt from ``num_children``."""

    name: str = ""
    repetition: str = "required"
    physical_type: str | None = None
    type_length: int | None = None
    num_children: int = 0
    converted_type: str | None = None
    logical_type: LogicalType | None = None
    precision: int | None = None
    scale: int | None = None


class _SchemaFound(Exception):
    """Internal: the schema is decoded, so the rest of the footer can be ignored."""


def _read_time_unit(reader: _Reader) -> str | None:
    """``TimeUnit`` is a union of empty structs -- only the field id matters."""
    unit: list[str] = []

    def visit(field_id: int, type_id: int) -> bool:
        name = _TIME_UNITS.get(field_id)
        if name is not None:
            unit.append(name)
        return False

    reader.read_struct(visit)
    return unit[0] if unit else None


def _read_logical_type(reader: _Reader) -> LogicalType | None:
    found: list[LogicalType] = []

    def visit(field_id: int, type_id: int) -> bool:
        kind = _LOGICAL_TYPES.get(field_id)
        if kind is None or type_id != _STRUCT:
            return False
        found.append(_read_logical_parameters(reader, kind))
        return True

    reader.read_struct(visit)
    return found[0] if found else None


def _read_logical_parameters(reader: _Reader, kind: str) -> LogicalType:
    values: dict[int, object] = {}

    def visit(field_id: int, type_id: int) -> bool:
        if type_id in _INTEGERS:
            values[field_id] = reader.integer()
        elif type_id == _BYTE:  # i8, e.g. IntType.bitWidth
            values[field_id] = reader.byte()
        elif type_id in (_TRUE, _FALSE):
            values[field_id] = type_id == _TRUE
        elif type_id == _STRUCT and field_id == 2 and kind in ("TIME", "TIMESTAMP"):
            values[field_id] = _read_time_unit(reader)
        else:
            return False
        return True

    reader.read_struct(visit)

    def integer(key: int) -> int | None:
        value = values.get(key)
        return value if isinstance(value, int) and not isinstance(value, bool) else None

    def flag(key: int) -> bool | None:
        value = values.get(key)
        return value if isinstance(value, bool) else None

    if kind == "DECIMAL":
        return LogicalType(kind, scale=integer(1), precision=integer(2))
    if kind in ("TIME", "TIMESTAMP"):
        unit = values.get(2)
        return LogicalType(kind, unit=unit if isinstance(unit, str) else None, utc=flag(1))
    if kind == "INTEGER":
        return LogicalType(kind, bit_width=integer(1), signed=flag(2))
    return LogicalType(kind)


def _read_element(reader: _Reader) -> _Element:
    element = _Element()

    def visit(field_id: int, type_id: int) -> bool:
        if field_id == 1 and type_id in _INTEGERS:
            element.physical_type = _enum_name(_PHYSICAL_TYPES, reader.integer())
        elif field_id == 2 and type_id in _INTEGERS:
            element.type_length = reader.integer()
        elif field_id == 3 and type_id in _INTEGERS:
            element.repetition = _enum_name(_REPETITIONS, reader.integer()) or "required"
        elif field_id == 4 and type_id == _BINARY:
            element.name = reader.text()
        elif field_id == 5 and type_id in _INTEGERS:
            element.num_children = reader.integer()
        elif field_id == 6 and type_id in _INTEGERS:
            element.converted_type = _enum_name(_CONVERTED_TYPES, reader.integer())
        elif field_id == 7 and type_id in _INTEGERS:
            element.scale = reader.integer()
        elif field_id == 8 and type_id in _INTEGERS:
            element.precision = reader.integer()
        elif field_id == 10 and type_id == _STRUCT:
            element.logical_type = _read_logical_type(reader)
        else:
            return False
        return True

    reader.read_struct(visit)
    return element


def _build_tree(elements: list[_Element], index: int) -> tuple[SchemaNode, int]:
    """Rebuild one subtree from the depth-first list, returning the next index."""
    element = elements[index]
    index += 1
    children: list[SchemaNode] = []
    for _ in range(element.num_children):
        if index >= len(elements):
            raise SchemaError("Parquet schema claims more columns than the footer holds")
        child, index = _build_tree(elements, index)
        children.append(child)
    node = SchemaNode(
        name=element.name,
        repetition=element.repetition,
        physical_type=element.physical_type,
        type_length=element.type_length,
        converted_type=element.converted_type,
        logical_type=element.logical_type,
        precision=element.precision,
        scale=element.scale,
        children=tuple(children),
    )
    return node, index


def read_footer(path: Path) -> bytes:
    """Return the raw Thrift bytes of ``path``'s ``FileMetaData``."""
    try:
        with path.open("rb") as handle:
            handle.seek(0, os.SEEK_END)
            size = handle.tell()
            if size < len(MAGIC) * 2 + 4:
                raise SchemaError(f"{path.name} is too small to be a Parquet file")
            handle.seek(-8, os.SEEK_END)
            tail = handle.read(8)
            if tail[4:] == ENCRYPTED_MAGIC:
                raise SchemaError(f"{path.name} has an encrypted footer, which cannot be read")
            if tail[4:] != MAGIC:
                raise SchemaError(f"{path.name} is not a Parquet file")
            length = int.from_bytes(tail[:4], "little")
            if length == 0 or length + 8 > size:
                raise SchemaError(f"{path.name} has a corrupt footer")
            handle.seek(-(length + 8), os.SEEK_END)
            return handle.read(length)
    except OSError as exc:
        raise SchemaError(str(exc)) from exc


def read_schema(path: str | Path) -> SchemaNode:
    """Return the root of ``path``'s schema tree.

    The root is the (unnamed, in practice ``schema`` or similar) group Parquet
    wraps every file in; its children are the top-level columns.
    """
    text = str(path)
    if "://" in text:
        raise SchemaError(f"{text} is not a local file, so its footer cannot be read")

    reader = _Reader(read_footer(Path(text)))
    elements: list[_Element] = []

    def visit(field_id: int, type_id: int) -> bool:
        if field_id != 2 or type_id != _LIST:  # FileMetaData.schema
            return False
        size, element_type = reader.list_header()
        if element_type != _STRUCT:
            raise SchemaError("Parquet footer holds a schema of an unexpected shape")
        for _ in range(size):
            elements.append(_read_element(reader))
        raise _SchemaFound  # row groups and statistics follow; we are done

    with contextlib.suppress(_SchemaFound):
        reader.read_struct(visit)

    if not elements:
        raise SchemaError(f"{Path(text).name} carries no schema in its footer")
    root, _ = _build_tree(elements, 0)
    return root
