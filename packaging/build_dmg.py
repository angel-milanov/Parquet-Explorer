"""Build the macOS disk image.

Runs PyInstaller to produce ``dist/Parquet Explorer.app``, then stages it next to
a shortcut to /Applications and hands the pair to ``hdiutil`` — the drag-to-install
layout every macOS user already knows:

    uv run poe dmg

The app version comes from ``parquet_explorer.__version__``, so nothing here needs
editing for a release.
"""

from __future__ import annotations

import argparse
import platform
import shutil
import subprocess
import sys
from pathlib import Path

from parquet_explorer import __version__

ROOT = Path(__file__).resolve().parent.parent
PACKAGING = ROOT / "packaging"
DIST = ROOT / "dist"
APP = DIST / "Parquet Explorer.app"
STAGING = DIST / "dmg"
SPEC = PACKAGING / "parquet-explorer.spec"

VOLUME_NAME = f"Parquet Explorer {__version__}"


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


def sign_ad_hoc() -> None:
    """Sign the bundle with an ad-hoc signature.

    Apple silicon refuses to run unsigned code at all, so this is what makes the
    build launchable rather than a nicety.  It is *not* a Developer ID signature:
    the app is still unnotarised, and Gatekeeper still asks the user to confirm the
    first launch.
    """
    run(["codesign", "--force", "--deep", "--sign", "-", str(APP)])


def stage() -> None:
    """Lay out the disk image's contents: the app, and a drop target beside it."""
    if STAGING.exists():
        shutil.rmtree(STAGING)
    STAGING.mkdir(parents=True)
    # symlinks=True matters — Qt ships its frameworks as symlinked Versions/ trees,
    # and resolving those would both bloat the image and break code signing.
    shutil.copytree(APP, STAGING / APP.name, symlinks=True)
    (STAGING / "Applications").symlink_to("/Applications")


def build_dmg() -> Path:
    architecture = "arm64" if platform.machine() == "arm64" else "x86_64"
    image = DIST / f"parquet-explorer-{__version__}-macos-{architecture}.dmg"
    image.unlink(missing_ok=True)

    run(
        [
            "hdiutil",
            "create",
            "-volname", VOLUME_NAME,
            "-srcfolder", str(STAGING),
            "-fs", "HFS+",
            "-format", "UDZO",  # compressed, read-only
            "-ov",
            str(image),
        ]
    )  # fmt: skip

    if not image.is_file():
        raise SystemExit(f"hdiutil reported success but {image} is missing")
    return image


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--skip-bundle",
        action="store_true",
        help="reuse the existing dist/Parquet Explorer.app instead of rebuilding it",
    )
    args = parser.parse_args(argv)

    if sys.platform != "darwin":
        raise SystemExit("The disk image can only be built on macOS.")

    if args.skip_bundle:
        if not APP.is_dir():
            raise SystemExit(f"{APP} does not exist — drop --skip-bundle to build it.")
        print(f"Reusing {APP}")
    else:
        build_bundle()

    sign_ad_hoc()
    stage()
    image = build_dmg()
    shutil.rmtree(STAGING)

    size_mb = image.stat().st_size / 1024 / 1024
    print(f"\nBuilt {image} ({size_mb:.1f} MB)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
