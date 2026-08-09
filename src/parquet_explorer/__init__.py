"""Parquet Explorer — open a Parquet file, run SQL against it, view the results."""

from __future__ import annotations

__version__ = "0.2.0"
__all__ = ["__version__", "main"]


def main() -> int:
    """Entry point shim so ``from parquet_explorer import main`` keeps working."""
    from parquet_explorer.app import main as _main

    return _main()
