"""The About dialog: which versions this is built from, and their licenses.

The licenses are not a formality here. Qt and PySide6 are LGPL, which asks that a
copy of the license travel with the binary, and the standalone builds ship both —
along with DuckDB and CPython. A dialog is the one place a user of a `.dmg` or an
installer will actually find them.
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QFontDatabase, QGuiApplication
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QPlainTextEdit,
    QSplitter,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

# app.py imports the window lazily, inside main(), so this does not come back
# around: the banner lives there because --version prints it.
from parquet_explorer.app import version_string
from parquet_explorer.icon import render_pixmap
from parquet_explorer.licenses import HOMEPAGE, components

SUMMARY = "Open a Parquet file, run DuckDB SQL against it, read the results in a grid."
COPYRIGHT = "Copyright © 2026 Angel Milanov. Parquet Explorer is MIT licensed."


class AboutDialog(QDialog):
    """Version details on one tab, the licenses of everything shipped on another."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("About Parquet Explorer")
        # Wide enough that the 78-column license texts fit without scrolling
        # sideways, which is the whole reason this dialog is not a QMessageBox.
        self.resize(900, 600)

        self.components = components()
        self.fixed_font = QFontDatabase.systemFont(QFontDatabase.SystemFont.FixedFont)

        self.tabs = QTabWidget()
        self.tabs.addTab(self._build_about_tab(), "&About")
        self.tabs.addTab(self._build_licenses_tab(), "&Licenses")

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(self.reject)
        self.copy_button = buttons.addButton(
            "&Copy version info", QDialogButtonBox.ButtonRole.ActionRole
        )
        self.copy_button.setToolTip("Copy the version line to paste into a bug report")
        self.copy_button.clicked.connect(self.copy_version_info)

        layout = QVBoxLayout(self)
        layout.addWidget(self.tabs)
        layout.addWidget(buttons)

    # -- construction -------------------------------------------------------

    def _build_about_tab(self) -> QWidget:
        logo = QLabel()
        logo.setPixmap(render_pixmap(96))
        logo.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignHCenter)

        name = QLabel("Parquet Explorer")
        title_font = name.font()
        title_font.setPointSize(title_font.pointSize() + 6)
        title_font.setBold(True)
        name.setFont(title_font)

        summary = QLabel(SUMMARY)
        summary.setWordWrap(True)

        # Selectable because this is the line bug reports want, and on the
        # standalone Windows build `--version` at a prompt prints nothing.
        self.version_label = QLabel(version_string())
        self.version_label.setFont(self.fixed_font)
        self.version_label.setWordWrap(True)
        self.version_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)

        homepage = QLabel(f'<a href="{HOMEPAGE}">{HOMEPAGE}</a>')
        homepage.setOpenExternalLinks(True)

        copyright_label = QLabel(COPYRIGHT)
        copyright_label.setWordWrap(True)

        details = QVBoxLayout()
        details.setSpacing(10)
        details.addWidget(name)
        details.addWidget(summary)
        details.addWidget(self.version_label)
        details.addWidget(homepage)
        details.addWidget(copyright_label)
        details.addStretch(1)

        tab = QWidget()
        layout = QHBoxLayout(tab)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(20)
        layout.addWidget(logo)
        layout.addLayout(details, 1)
        return tab

    def _build_licenses_tab(self) -> QWidget:
        self.component_list = QListWidget()
        self.component_list.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        for component in self.components:
            # Two lines rather than "name — license": one line long enough to
            # hold both would be wider than any sensible width for this list.
            self.component_list.addItem(f"{component.title}\n{component.license_name}")
        self.component_list.currentRowChanged.connect(self.show_license)

        self.license_heading = QLabel()
        self.license_heading.setWordWrap(True)
        self.license_heading.setOpenExternalLinks(True)

        self.license_view = QPlainTextEdit()
        self.license_view.setReadOnly(True)
        self.license_view.setFont(self.fixed_font)
        # The texts are already wrapped at 78 columns upstream; wrapping them
        # again would re-break lines the license authors set deliberately.
        self.license_view.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)

        text_side = QWidget()
        text_layout = QVBoxLayout(text_side)
        text_layout.setContentsMargins(0, 0, 0, 0)
        text_layout.setSpacing(6)
        text_layout.addWidget(self.license_heading)
        text_layout.addWidget(self.license_view)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.addWidget(self.component_list)
        splitter.addWidget(text_side)
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([240, 640])

        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.addWidget(splitter)

        self.component_list.setCurrentRow(0)
        return tab

    # -- actions ------------------------------------------------------------

    def show_license(self, row: int) -> None:
        """Show the license of the component at ``row`` in the list."""
        if not 0 <= row < len(self.components):
            return
        component = self.components[row]
        self.license_heading.setText(
            f"<b>{component.title}</b> — {component.license_name} — "
            f'<a href="{component.url}">{component.url}</a>'
        )
        self.license_view.setPlainText(component.text)
        self.license_view.verticalScrollBar().setValue(0)

    def copy_version_info(self) -> None:
        """Put the ``--version`` line on the clipboard."""
        QGuiApplication.clipboard().setText(version_string())
