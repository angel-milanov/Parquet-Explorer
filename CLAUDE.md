# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

The project uses [uv](https://docs.astral.sh/uv/). `uv sync` installs everything —
`[tool.uv] default-groups` pulls in both the dev and packaging groups.

```bash
uv run parquet-explorer [file.parquet]   # launch the app
uv run pytest                            # test
uv run ruff check .                      # lint
uv run ruff format .                      # format
uv run mypy                              # type-check (src/parquet_explorer only)
```

Running a subset of tests:

```bash
uv run pytest tests/test_data.py                        # one file
uv run pytest tests/test_data.py::test_row_count        # one test
uv run pytest -k "export"                               # by name
uv run pytest -m "not gui"                              # skip everything that builds widgets
```

Multi-step packaging commands are named in `[tool.poe.tasks]`; `uv run poe` lists them.
`installer` is Windows-only and needs Inno Setup 6.3+ on PATH; `dmg` is macOS-only
and needs only the `hdiutil` and `codesign` that ship with the OS.

```bash
uv run poe bundle      # PyInstaller one-dir bundle into dist/
uv run poe installer   # bundle, then compile packaging/installer.iss
uv run poe dmg         # bundle, then stage Parquet Explorer.app into a .dmg
uv run poe icon        # regenerate packaging/icon.{ico,icns} from icon.py
```

The shell here is PowerShell. Setting an env var for one command is
`$env:QT_QPA_PLATFORM="offscreen"; uv run pytest`, not the `VAR=x cmd` form.

## Architecture

Modules under `src/parquet_explorer/`, layered so the logic is testable without a
display:

- **`data.py`** — the DuckDB session. Deliberately imports no Qt. Everything that
  touches the database lives here and is covered by plain (non-GUI) tests.
- **`parquet_schema.py`** — decodes a Parquet footer into a schema tree. No Qt and
  no DuckDB.
- **`avro.py`** — translates that tree into an Avro record schema (`.avsc`).
- **`models.py`** — adapts a `QueryResult` to `QAbstractTableModel` for the grid.
- **`window.py`** — `MainWindow`: schema panel, SQL editor, results grid, status bar,
  and `AvroSchemaDialog`.
- **`about.py`** — the About dialog: version details and the license texts.
- **`licenses.py`** — what ships and under which license, with no widgets involved,
  so the list has plain tests. **`license_texts.py`** holds the texts themselves.

`app.py` is the entry point (argument parsing, `QApplication` setup) and `icon.py`
draws the application icon. Keep `data.py` free of Qt imports — that boundary is
what lets most behaviour be tested headless.

### Things that span files

**The `data` view.** `ParquetSession.open()` registers the file as a DuckDB view
named `TABLE_NAME` (`"data"`), and `DEFAULT_QUERY` selects from it. Both live in
`data.py`. That name is user-visible: it is what people type in the editor, so
renaming it is a breaking change, and several tests assert on it.

**Results are fully materialised.** `ParquetSession.run()` calls `fetchall()` and
`QueryResult` holds the rows as a tuple of tuples. There is no lazy paging or
background thread — a query that returns 50M rows will allocate them. This is a
deliberate trade for simplicity; if you add paging, the model's `rowCount`/`data`
and the status-bar wiring in `MainWindow.run_query()` all have to change together.

**Error flow.** `data.py` catches `duckdb.Error` and re-raises `QueryError`.
`MainWindow` shows that message in `error_label` above the grid and deliberately
leaves the previous result in the model, so a typo does not wipe the screen. Tests
assert both halves of that behaviour.

**The Avro schema does not come from DuckDB.** `parquet_schema.read_schema()` reads
the file's own footer — a Thrift compact-protocol `FileMetaData` — and rebuilds the
schema tree from it. That is a deliberate choice, not an oversight: `DESCRIBE data`
(and DuckDB's `parquet_schema()` table function) flattens away the three things the
Avro mapping is built on — per-level repetition, which *is* the nullability; the
logical-type annotations with their parameters; and the wrapper groups that spell
out `LIST` and `MAP`, including the legacy two-level layouts. Adding pyarrow or
fastparquet to read them instead was rejected too: a ~40 MB dependency in every
PyInstaller bundle, and its nested types come back as *Arrow* types, so the
Parquet-level detail would have to be dug back out anyway. Only
`FileMetaData.schema` is decoded; the walk stops there rather than stepping over
every row group's statistics, which is why the reader is O(schema) not O(footer).

**Three Avro mappings are lossy on purpose.** `INT96` → `timestamp-micros`,
unsigned 64-bit → `long`, `ENUM` → `string`. Each is documented in `avro.py`'s
module docstring and in `docs/usage.md`, and each has a test — if you "fix" one,
you are changing a decision, not a bug. Nanosecond logical types (`timestamp-nanos`
and friends) need Avro 1.12 or later; that is also deliberate, the alternative
being to silently round to microseconds. Avro's named types share one flat
namespace, so `avro.py`'s `_Names` hands out unique record and fixed names — two
structs called `address` in different branches would otherwise collide, and
Parquet's own wrapper names (`element`, `key_value`, …) would leak into the output.

**The icon has three representations.** `icon.py` draws it at runtime with QPainter
(used for the window and taskbar); `packaging/make_icon.py` renders the same shapes
into `packaging/icon.ico` and `packaging/icon.icns`, both committed because
PyInstaller needs a file at build time. Both are written on any platform — an
`.icns` is a container of PNG frames, so it needs no macOS tooling. Change
`icon.py` and you must run `uv run poe icon` and commit the result —
`tests/test_icon.py` compares the committed `.ico` against `ICON_SIZES` and the
`.icns` against `make_icon.ICNS_TYPES`, and fails otherwise.

**Version is single-sourced.** `__init__.__version__` feeds the CLI banner, the
Windows version resource in the PyInstaller spec, and the installer version that
`build_installer.py` passes to Inno Setup as `/DAppVersion`. The About dialog shows
`app.version_string()` — the same banner `--version` prints — rather than composing
its own, which is why `about.py` imports from `app.py` and not the other way round.

**License texts are Python, not package data.** `license_texts.py` holds each
license verbatim as a module constant, for the same reason `icon.py` draws rather
than ships a PNG: a plain import cannot go missing from a wheel or a PyInstaller
bundle. They are copies of upstream files — re-copy rather than edit, and keep them
wrapped at 78 columns, which `tests/test_licenses.py` enforces because `about.py`
shows them without re-wrapping. `licenses.py` deliberately appends the GPL v3 to
the LGPL v3, since the LGPL states in its own opening that it incorporates it.

## Testing

GUI tests are marked `@pytest.mark.gui` and use pytest-qt's `qtbot`/`qapp`. They run
headless under `QT_QPA_PLATFORM=offscreen`, which CI sets globally; locally on a
desktop they open real windows unless you set it yourself.

`tests/conftest.py` builds the sample Parquet file once per session with a DuckDB
`COPY`, covering ints, strings, floats, booleans, dates and a nullable column.
Prefer extending that fixture over writing new Parquet files ad hoc. `nested_parquet`
is the second fixture, for lists, structs, maps and the annotated types the Avro
mapping has to handle; it is separate because the grid tests assert on
`sample_parquet`'s exact six-column shape. Note that DuckDB's writer marks every
column `optional` and turns `i * 1.5` into a `DECIMAL`, so schema shapes it cannot
produce — `required` fields, two-level lists, `INT96` — are tested against
hand-built `SchemaNode` trees in `tests/test_avro.py`.

New behaviour needs a test. Logic that does not need a widget belongs in `data.py`
with a plain test; widget behaviour gets a `gui`-marked test.

## Packaging notes

`packaging/parquet-explorer.spec` builds a one-dir bundle (not `--onefile`: Qt's
shared libraries make unpacking slow on every launch) and excludes the Qt modules
the app never uses. On Windows it also embeds the icon and a version resource, and
sets `console=False` on Windows, so the exe is a GUI-subsystem program and Windows
never creates a console for it. `--noconsole` and `--windowed` are the CLI
spellings of that flag; spec files ignore CLI flags, so it belongs here.

The rejected alternative was `console=True` with `hide_console="hide-early"`, which
lets Windows create the console and hides it a moment later — measured at ~30 ms
visible on a cold launch, and no help at all when the console is delegated to
Windows Terminal, since that window belongs to a different process.

What `console=False` costs is narrow and worth knowing: cmd and PowerShell do not
*wait* for a GUI program, so `parquet-explorer --version` typed at a prompt returns
before the output arrives. Redirects and pipes still capture it, because a GUI
process inherits the handles its launcher passes. There is deliberately no second
console executable — the CLI is an optional file argument, `--version` and `--help`,
which does not justify shipping two programs.

`--version` intentionally reports the DuckDB and Qt versions as well as the app's.
The release workflow greps that output as its smoke test, so it fails loudly if
either library did not make it into the bundle. That step must stay on `shell: bash`
with its pipe — bash waits for the process and the pipe gives the output somewhere
to land, where PowerShell would capture nothing. A following step asserts the PE
subsystem byte is 2, since the smoke test passes either way and nothing else would
notice a console reappearing on every launch.

On macOS the spec additionally wraps that bundle in `Parquet Explorer.app`, which
`packaging/build_dmg.py` ad-hoc-signs (Apple silicon will not run unsigned code) and
stages beside an `/Applications` symlink inside a `.dmg`. `dist/parquet-explorer/`
is left in place, so the tarball and the `--version` smoke test are unaffected. The
app is unnotarised, so first launch still needs right-click → Open. It declares no
`CFBundleDocumentTypes`: Finder opens documents via `QFileOpenEvent`, not argv, and
nothing handles that event yet.

`AppId` in `packaging/installer.iss` is how Windows recognises an existing install
to upgrade in place — never change it. `BUNDLE_IDENTIFIER` in the spec is the macOS
equivalent, and is equally permanent.
