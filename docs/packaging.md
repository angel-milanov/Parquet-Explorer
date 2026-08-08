# Packaging

How the downloadable builds are produced. Day-to-day development does not need any
of this — see [Contributing](contributing.md) for that.

The multi-step commands are named in `[tool.poe.tasks]` in `pyproject.toml`, so
they do not have to be copied out of the docs. `uv run poe` lists them.

## Standalone bundle

```bash
uv run poe bundle
./dist/parquet-explorer/parquet-explorer
```

`packaging/parquet-explorer.spec` drives PyInstaller. Two decisions are baked into
it:

- **One directory, not `--onefile`.** Qt ships enough shared libraries that a
  single-file build would spend seconds unpacking to a temporary directory on
  every launch.
- **Unused Qt modules are excluded.** PySide6 bundles 3D, WebEngine, Charts,
  Multimedia and more; the app touches none of them, and dropping them roughly
  halves the archive.

On Windows the executable also gets an icon, a version resource (the product name,
version and copyright that File Explorer shows under *Details*), and
`hide_console="hide-early"` — so a double-click opens the GUI with no console
window behind it, while `parquet-explorer --version` still prints when run from a
terminal.

## Windows installer

```powershell
uv run poe installer
```

That builds the bundle and compiles `packaging/installer.iss`, leaving
`dist/parquet-explorer-<version>-windows-x86_64-setup.exe`.

It needs [Inno Setup 6.3 or newer](https://jrsoftware.org/isdl.php):

```powershell
winget install --id JRSoftware.InnoSetup
```

`packaging/build_installer.py` finds `ISCC.exe` on `PATH` or in the usual Program
Files locations — pass `--iscc <path>` if yours lives somewhere else, and
`--skip-bundle` to reuse a bundle you already built.

The app version is passed to Inno Setup as `/DAppVersion`, so `installer.iss`
never needs editing for a release.

!!! danger "Never change `AppId`"

    The GUID in `installer.iss` is how Windows recognises an existing installation
    and upgrades it in place. Changing it turns every future release into a
    side-by-side second install rather than an upgrade.

## macOS disk image

```bash
uv run poe dmg
```

That builds the bundle and leaves
`dist/parquet-explorer-<version>-macos-arm64.dmg`. Only `hdiutil` and `codesign`
are needed, both of which ship with macOS.

On macOS the spec wraps the collected bundle in `Parquet Explorer.app` as well —
`dist/parquet-explorer/` is left alone, so the tarball and the smoke test are
unaffected. `packaging/build_dmg.py` then stages the app next to a symlink to
`/Applications` and compresses the pair into a read-only image, which is the
drag-to-install layout users expect. Pass `--skip-bundle` to reuse a bundle you
already built.

The app is signed **ad-hoc** (`codesign --sign -`) before packaging. That is not a
nicety: Apple silicon refuses to run unsigned code at all. It is not a Developer ID
signature, though, so the download is still unnotarised and Gatekeeper still asks
the user to confirm the first launch — see [Installation](installation.md#standalone-builds).
Signing properly needs a paid Apple Developer account, a certificate in the CI
keychain and a notarisation step.

!!! danger "Never change `BUNDLE_IDENTIFIER`"

    `io.github.angel-milanov.parquet-explorer` in the spec is how macOS recognises
    an installation — it keys Launch Services, the preferences domain and the
    Gatekeeper record. It plays the same role as `AppId` on Windows.

The app deliberately declares no `CFBundleDocumentTypes`, so it does not claim
`.parquet` files the way the Windows installer offers to. Opening a file from
Finder sends the app a `QFileOpenEvent` rather than a command-line argument, and
nothing handles that event yet — advertising the association would only produce an
app that opens empty.

## The icon

`src/parquet_explorer/icon.py` draws the icon at runtime with `QPainter`, and that
is what the window and taskbar use. Drawing it rather than shipping a PNG keeps the
wheel free of package data and means a source checkout, a wheel install and a
bundle all look the same.

PyInstaller needs a real file at build time, so `packaging/icon.ico` (Windows) and
`packaging/icon.icns` (macOS) are generated from those same shapes and committed:

```bash
uv run poe icon
```

Both are written on any platform — an `.icns` is just a container of PNG frames, so
building one needs no macOS tooling.

`tests/test_icon.py` parses both committed files and checks their frames still
match what the sources declare, so a stale icon fails CI rather than shipping.

## Releasing

Tag a commit and push the tag:

```bash
git tag -a v0.1.0 -m "v0.1.0"
git push origin v0.1.0
```

[`release.yml`](https://github.com/angel-milanov/parquet-explorer/blob/main/.github/workflows/release.yml)
then builds, in parallel:

1. the sdist and wheel, with `uv build`;
2. a standalone bundle on Linux, macOS and Windows, plus the Windows installer and
   the macOS disk image.

Each bundle is smoke-tested by running `--version` and grepping the output for
DuckDB and Qt. Because `--version` has to import both libraries to report their
versions, that check fails loudly if either did not make it into the bundle.

Everything is then attached to a GitHub release with generated notes, which is what
gives users a [releases page](https://github.com/angel-milanov/parquet-explorer/releases)
listing every version and its downloads. Nothing is published by hand, so the
assets on a release are exactly what that tag builds.

The same workflow can be re-run from the Actions tab with **Run workflow**, which
takes an existing tag — useful if a release job failed after the tag was pushed.

### PyPI

Publishing is wired up but disabled. To turn it on, configure [trusted
publishing](https://docs.pypi.org/trusted-publishers/) for the project on PyPI,
then set the repository variable `PUBLISH_TO_PYPI` to `true`.
