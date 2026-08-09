# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project adheres
to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- Avro schema view: **File → Avro Schema…** (<kbd>Ctrl</kbd> + <kbd>Shift</kbd> +
  <kbd>A</kbd>) shows the open file's structure as an Avro record (`.avsc`) with a
  button to copy it, and **File → Copy Avro Schema** (<kbd>Ctrl</kbd> +
  <kbd>Shift</kbd> + <kbd>C</kbd>) puts it straight on the clipboard. The schema is
  decoded from the Parquet footer itself, so nullability, logical types and nested
  lists, maps and structs all survive the translation.
- **Help → About Parquet Explorer**, an information dialog in two tabs. The first
  repeats the `--version` line, with a button that copies it for a bug report; the
  second lists everything the app ships and shows the full text of its license —
  Parquet Explorer and DuckDB (MIT), PySide6 and Qt (GNU LGPL v3, followed by the
  GNU GPL v3 it incorporates), and Python (PSF License Agreement).
- Documentation site built with Material for MkDocs and published to GitHub Pages
  on every push to `main`.

- Windows installer, built with Inno Setup (`uv run poe installer`) and attached to
  releases. Installs per user, adds a Start menu entry, and optionally registers
  Parquet Explorer as a handler for `.parquet` files.
- macOS disk image (`uv run poe dmg`), attached to releases. Ships
  `Parquet Explorer.app` next to an Applications shortcut to drag it onto. The app
  is ad-hoc signed but not notarised, so the first launch needs right-click → Open.
- Project commands are declared in `[tool.poe.tasks]`; `uv run poe` lists them.
- Application icon, drawn in code and used for the window, the taskbar and the
  Windows executable.
- Windows executables carry a version resource, so File Explorer shows the product
  name, version and copyright.

### Changed

- `--version` now also reports the DuckDB, PySide6 and Qt versions.
- Windows builds no longer show a console window when the app is launched: the
  executable is now a GUI program rather than a console one whose window was
  hidden after the fact. `--version` and `--help` still work when redirected or
  piped, but `cmd` and PowerShell do not wait for a GUI program, so they print
  nothing when typed at a prompt.

## [0.1.0] - 2026-08-07

First release.

### Added

- Open a Parquet file from the file dialog, a drag-and-drop, or the command line.
- The open file is registered as a DuckDB view named `data`, and the editor starts
  on `SELECT * FROM data LIMIT 1000`.
- Run SQL with <kbd>Ctrl</kbd> + <kbd>Enter</kbd> or <kbd>F5</kbd>; results land in
  a grid with numeric columns right-aligned and `NULL`s rendered distinctly.
- Schema panel listing column names and types; double-click inserts a name into the
  editor.
- Inline error reporting that keeps the previous result on screen.
- CSV export of the current query's result.
- Row count, column count and elapsed time in the status bar.

[Unreleased]: https://github.com/angel-milanov/parquet-explorer/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/angel-milanov/parquet-explorer/releases/tag/v0.1.0
