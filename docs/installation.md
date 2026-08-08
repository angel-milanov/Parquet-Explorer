# Installation

## Standalone builds

Every [release](https://github.com/angel-milanov/parquet-explorer/releases) ships
builds that need no Python installed.

=== "Windows"

    Download `parquet-explorer-<version>-windows-x86_64-setup.exe` and run it.

    It installs per user, so no administrator rights are needed, and adds a Start
    menu entry. Two checkboxes during setup are worth a glance:

    - **Desktop shortcut** — off by default.
    - **Open .parquet files with Parquet Explorer** — registers the app as an
      *additional* handler, so it appears under "Open with" without displacing
      whatever you already use for `.parquet`.

    If you would rather not install anything, `parquet-explorer-windows-x86_64.zip`
    is the same bundle as a plain archive — unpack it and run
    `parquet-explorer.exe`.

=== "macOS"

    Download `parquet-explorer-macos-arm64.tar.gz`, unpack it, and run the
    `parquet-explorer` binary inside.

    The build is not signed or notarised, so Gatekeeper will object on first
    launch. Right-click the binary and choose **Open** to get the "open anyway"
    prompt, or clear the quarantine attribute:

    ```bash
    xattr -dr com.apple.quarantine parquet-explorer
    ```

=== "Linux"

    Download `parquet-explorer-linux-x86_64.tar.gz`, unpack it, and run the
    `parquet-explorer` binary inside.

    Qt needs a handful of system libraries that a minimal container may not have.
    On Debian and Ubuntu:

    ```bash
    sudo apt-get install -y libegl1 libgl1 libxkbcommon-x11-0 libxcb-cursor0 \
      libxcb-icccm4 libxcb-image0 libxcb-keysyms1 libxcb-randr0 \
      libxcb-render-util0 libxcb-shape0 libxcb-xinerama0
    ```

## From PyPI

Installing as a tool keeps its dependencies isolated but puts the command on your
`PATH`:

```bash
uv tool install parquet-explorer
# or
pipx install parquet-explorer
```

Plain `pip install parquet-explorer` works too, in a virtual environment.

Python 3.10 or newer is required. PySide6 and DuckDB ship wheels for every
supported platform, so there is nothing to compile.

## From source

```bash
git clone https://github.com/angel-milanov/parquet-explorer
cd parquet-explorer
uv run parquet-explorer
```

[uv](https://docs.astral.sh/uv/) creates the environment and installs dependencies
on first run. See [Contributing](contributing.md) for the rest of the development
setup.

## Verifying the install

```console
$ parquet-explorer --version
parquet-explorer 0.1.0 (DuckDB 1.5.5, PySide6 6.11.1, Qt 6.11.1)
```

The DuckDB and Qt versions are reported alongside the app's own — that is the line
to paste into a bug report.
