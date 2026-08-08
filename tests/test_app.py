from __future__ import annotations

import pytest

from parquet_explorer import __version__
from parquet_explorer.app import _set_windows_app_id, build_parser, main, version_string


def test_version_string_reports_the_app_and_its_dependencies() -> None:
    text = version_string()

    assert text.startswith(f"parquet-explorer {__version__}")
    assert "DuckDB" in text
    assert "PySide6" in text
    assert "Qt" in text


def test_version_flag_exits_cleanly(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as exit_info:
        main(["--version"])

    assert exit_info.value.code == 0
    assert __version__ in capsys.readouterr().out


def test_unknown_flag_exits_with_usage_error() -> None:
    with pytest.raises(SystemExit) as exit_info:
        main(["--nope"])

    assert exit_info.value.code == 2


def test_file_argument_is_optional() -> None:
    assert build_parser().parse_args([]).file is None
    assert build_parser().parse_args(["a.parquet"]).file == "a.parquet"


def test_setting_the_windows_app_id_never_raises() -> None:
    """It is a no-op off Windows and must not break startup on it."""
    _set_windows_app_id()
