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

## Exporting

++ctrl+e++ writes the result of the **current editor contents** to a CSV file with
a header row. Note that it re-runs the query rather than dumping what is on screen,
so edit the query first if you want something different from what the grid shows.

For any other format, DuckDB's `COPY` works directly from the editor:

```sql
COPY (SELECT * FROM data WHERE revenue > 1000)
TO 'big-spenders.parquet' (FORMAT PARQUET);
```

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
