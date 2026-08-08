"""Build the Windows installer.

Runs PyInstaller to produce ``dist/parquet-explorer``, then hands that bundle to
Inno Setup's compiler.  The app version is passed through so ``installer.iss``
never has to be edited for a release:

    uv run poe installer
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path

from parquet_explorer import __version__

ROOT = Path(__file__).resolve().parent.parent
PACKAGING = ROOT / "packaging"
BUNDLE = ROOT / "dist" / "parquet-explorer"
SPEC = PACKAGING / "parquet-explorer.spec"
ISS = PACKAGING / "installer.iss"

INSTALL_HINT = """\
Inno Setup 6.3 or newer was not found.  Install it and re-run, for example:

    winget install --id JRSoftware.InnoSetup
    choco install innosetup

or download it from https://jrsoftware.org/isdl.php
If it is installed somewhere unusual, pass --iscc <path to ISCC.exe>."""


def find_iscc() -> Path | None:
    """Locate the Inno Setup command-line compiler."""
    on_path = shutil.which("ISCC")
    if on_path:
        return Path(on_path)

    for variable in ("ProgramFiles(x86)", "ProgramFiles", "ProgramW6432"):
        base = os.environ.get(variable)
        if not base:
            continue
        for release in ("6", "5"):
            candidate = Path(base) / f"Inno Setup {release}" / "ISCC.exe"
            if candidate.is_file():
                return candidate
    return None


def run(command: list[str]) -> None:
    print(f"$ {subprocess.list2cmdline(command)}", flush=True)
    subprocess.run(command, check=True, cwd=ROOT)


def build_bundle() -> None:
    pyinstaller = shutil.which("pyinstaller")
    if pyinstaller is None:
        raise SystemExit(
            "pyinstaller is not installed. Run `uv sync` (the package group is "
            "installed by default) and try again."
        )
    run([pyinstaller, "--noconfirm", "--clean", str(SPEC)])


def build_installer(iscc: Path) -> Path:
    run([str(iscc), f"/DAppVersion={__version__}", str(ISS)])
    installer = ROOT / "dist" / f"parquet-explorer-{__version__}-windows-x86_64-setup.exe"
    if not installer.is_file():
        raise SystemExit(f"Inno Setup reported success but {installer} is missing")
    return installer


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--skip-bundle",
        action="store_true",
        help="reuse the existing dist/parquet-explorer instead of rebuilding it",
    )
    parser.add_argument("--iscc", type=Path, help="path to ISCC.exe")
    args = parser.parse_args(argv)

    if sys.platform != "win32":
        raise SystemExit("The installer can only be built on Windows.")

    iscc = args.iscc or find_iscc()
    if iscc is None or not iscc.is_file():
        raise SystemExit(INSTALL_HINT)
    print(f"Inno Setup compiler: {iscc}")

    if args.skip_bundle:
        if not BUNDLE.is_dir():
            raise SystemExit(f"{BUNDLE} does not exist — drop --skip-bundle to build it.")
        print(f"Reusing {BUNDLE}")
    else:
        build_bundle()

    installer = build_installer(iscc)
    size_mb = installer.stat().st_size / 1024 / 1024
    print(f"\nBuilt {installer} ({size_mb:.1f} MB)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
