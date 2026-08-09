# Contributing

Thanks for taking the time. Bug reports, feature ideas and pull requests are all
welcome.

## Getting set up

You need [uv](https://docs.astral.sh/uv/) and Python 3.14 or newer. `uv sync` will
download a suitable interpreter if you don't have one.

```bash
git clone https://github.com/angel-milanov/parquet-explorer
cd parquet-explorer
uv sync --all-groups
uv run parquet-explorer
```

## Before you open a pull request

Run what CI runs:

```bash
uv run ruff check .
uv run ruff format --check .
uv run mypy
uv run pytest
```

`ruff format .` fixes formatting; `ruff check --fix .` fixes most lint findings.

## What we look for

- **Tests.** New behaviour needs a test. Logic that doesn't need a widget belongs
  in `data.py` and gets a plain test; widget behaviour gets a `pytest-qt` test
  marked `@pytest.mark.gui`. The whole suite runs headless.
- **Keep the layers apart.** `data.py` stays Qt-free so it stays easy to test.
- **Match the surrounding style.** Type hints on public functions, docstrings that
  say why rather than restating the signature.
- **Regenerate the icon if you change it.** `src/parquet_explorer/icon.py` is the
  source of truth; run `uv run python packaging/make_icon.py` and commit the
  updated `packaging/icon.ico`, or the icon test will fail.

## Reporting bugs

Open an issue with the Parquet file's schema (or a small file that reproduces it),
the query you ran, what you expected, and what happened. Include your OS and the
output of `parquet-explorer --version` — or, on the standalone Windows build, the
version from the app's window title, since that executable is a GUI program and
prints nothing at a prompt.

## Code of conduct

Be decent to each other. Harassment or personal attacks aren't welcome here, and
maintainers will remove comments, commits and issues that cross that line.
