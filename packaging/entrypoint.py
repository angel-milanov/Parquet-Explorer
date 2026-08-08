"""PyInstaller entry script for the standalone builds."""

from __future__ import annotations

import sys

from parquet_explorer.app import main

if __name__ == "__main__":
    sys.exit(main())
