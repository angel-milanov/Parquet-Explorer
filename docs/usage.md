# Using the app

## Opening a file

Three ways, all equivalent:

- **File → Open** (++ctrl+o++)
- **Drag** a `.parquet` file onto the window
- **Pass it on the command line**: `parquet-explorer sales.parquet`

```
parquet-explorer [file]

  file          Parquet file to open on startup
  --version     Print the version and exit
  -h, --help    Show the help and exit
```

Opening a file does three things: the column list on the left fills in with names
and types, the editor is reset to the default query, and that query runs. So the
first rows are on screen without touching the keyboard.

Opening a second file replaces the first — the app holds one file at a time.

## The `data` view

The open file is registered with DuckDB as a view named **`data`**. That is the
name to use in queries:

```sql
SELECT * FROM data LIMIT 1000;
```

Double-clicking a column in the left-hand panel inserts its name at the cursor,
which saves retyping `signup_date` for the third time.

## Running queries

| Shortcut | Action |
| --- | --- |
| ++ctrl+enter++ or ++f5++ | Run the query |
| ++ctrl+o++ | Open a Parquet file |
| ++ctrl+e++ | Export the result to CSV |
| ++ctrl+shift+a++ | Show the schema as Avro |
| ++ctrl+shift+c++ | Copy the Avro schema to the clipboard |

The status bar reports the shape and cost of what came back:

```
1,000 rows × 6 columns · 6 ms
```

Multiple statements separated by `;` all run, and the last one that produces rows
is what lands in the grid.

### When a query fails

The DuckDB error appears above the grid, and **the previous result stays on
screen**. A typo costs you nothing — fix it and run again.

## Reading the grid

- **Numbers are right-aligned**, text is left-aligned, so columns of figures line
  up and are easy to scan.
- **`NULL` is drawn as grey `NULL` text** rather than an empty cell, so a missing
  value is distinguishable from an empty string.
- **Booleans** show as `true` / `false`, **blobs** as truncated hex.
- **Hover a column header** to see its type.

## SQL worth knowing

Because the engine is DuckDB, far more is available than `SELECT *`.

### Understand a file you have never seen

```sql
-- Every column: type, min, max, distinct count, null percentage, quartiles
SUMMARIZE data;

-- Just the schema
DESCRIBE data;

-- How big is it, really?
SELECT count(*) FROM data;
```

### Aggregate

```sql
SELECT region,
       count(*)                     AS customers,
       round(avg(revenue), 2)       AS avg_revenue,
       max(signup_date)             AS newest
FROM data
GROUP BY region
ORDER BY customers DESC;
```

### Find the odd rows

```sql
-- Rows with any NULL in a column you care about
SELECT * FROM data WHERE region IS NULL;

-- Duplicate keys
SELECT id, count(*) AS n
FROM data
GROUP BY id
HAVING count(*) > 1;
```

### Reach other files

`data` is just one view in a normal DuckDB session, so you can read other files in
the same query:

```sql
SELECT d.*, r.label
FROM data d
JOIN read_csv('regions.csv') r ON r.code = d.region;

-- A whole directory of Parquet, including Hive-style partitions
SELECT count(*) FROM read_parquet('archive/**/*.parquet', hive_partitioning = true);
```

### Inspect the Parquet file itself

```sql
SELECT * FROM parquet_file_metadata('sales.parquet');   -- writer, row groups, size
SELECT * FROM parquet_schema('sales.parquet');          -- physical types, encodings
SELECT * FROM parquet_metadata('sales.parquet');        -- per-row-group statistics
```

## The schema as Avro

**File → Avro Schema…** (++ctrl+shift+a++) shows the open file's structure as an
Avro record schema — the contents of a `.avsc` file — with a **Copy to Clipboard**
button. ++ctrl+shift+c++ skips the window and copies it directly.

```json
{
  "type": "record",
  "name": "sales",
  "fields": [
    { "name": "id", "type": ["null", "long"], "default": null },
    { "name": "region", "type": ["null", "string"], "default": null },
    { "name": "day", "type": ["null", { "type": "int", "logicalType": "date" }],
      "default": null },
    { "name": "tags", "type": ["null", { "type": "array", "items": ["null", "string"] }],
      "default": null }
  ]
}
```

The record is named after the file, and the schema is read from the Parquet footer
rather than from the `data` view — so it reflects the file itself, not the current
query, and it does not change when you edit the SQL.

Because the footer is the source, the details Avro cares about survive:

- **Nullability** comes from each field's repetition. An `optional` field becomes a
  `["null", T]` union defaulting to `null`; a `required` one stays bare.
- **Nested types** keep their shape: structs become records, `LIST` groups become
  arrays, and string-keyed `MAP` groups become Avro maps. The older two-level list
  layouts are understood too.
- **Logical types** carry over: dates, times and timestamps (including the
  UTC-adjusted / local distinction), decimals with their precision and scale, and
  UUIDs.

Three things have no exact Avro equivalent and are widened on purpose:

| Parquet | Avro | Why |
| --- | --- | --- |
| `INT96` | `timestamp-micros` | The legacy timestamp; the nanosecond digits are dropped. |
| unsigned 64-bit | `long` | Avro has no unsigned types, so the top half of the range does not fit. |
| `ENUM` | `string` | An Avro enum must list its symbols, and a Parquet footer does not record them. |

!!! note "Maps with non-string keys"

    Avro maps are string-keyed. A Parquet map keyed by anything else becomes an
    array of `{key, value}` records instead, which is the usual way to spell it.

!!! note "Nanosecond precision needs Avro 1.12"

    `timestamp-nanos` and its siblings were added in Avro 1.12. Files written with
    nanosecond times produce a schema that older Avro libraries will reject.

## Exporting

++ctrl+e++ writes the result of the **current editor contents** to a CSV file with
a header row. Note that it re-runs the query rather than dumping what is on screen,
so edit the query first if you want something different from what the grid shows.

For any other format, DuckDB's `COPY` works directly from the editor:

```sql
COPY (SELECT * FROM data WHERE revenue > 1000)
TO 'big-spenders.parquet' (FORMAT PARQUET);
```

## Versions and licenses

**Help → About Parquet Explorer** has two tabs. The first repeats the `--version`
line — the app's version together with the DuckDB, PySide6 and Qt versions it is
running against — with a **Copy version info** button, which is the easiest way to
get that line for a bug report. On the standalone Windows build it is the *only*
way, since that executable is a GUI program and prints nothing at a prompt.

The second lists everything the app ships and shows the full text of each license:
Parquet Explorer and DuckDB under the MIT license, PySide6 and Qt under the GNU
LGPL v3, and Python under the PSF License Agreement. The LGPL text is followed by
the GNU GPL v3, whose terms it incorporates by reference.

## Limits worth knowing

!!! warning "Results are fully materialised"

    Rows are fetched in full into memory rather than paged, and the query runs on
    the UI thread — so a query returning tens of millions of rows will allocate
    them all and the window will not repaint until it finishes. This is a
    deliberate trade for a simple, predictable implementation.

    In practice: keep a `LIMIT` on exploratory queries, and let SQL do the
    aggregating. DuckDB reads only the columns and row groups it needs, so
    `SELECT region, count(*) FROM data GROUP BY region` over a large file is fast
    and returns almost nothing.
