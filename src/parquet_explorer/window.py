"""The main application window."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QSettings, Qt
from PySide6.QtGui import QAction, QDragEnterEvent, QDropEvent, QFont, QKeySequence
from PySide6.QtWidgets import (
    QAbstractItemView,
    QFileDialog,
    QHeaderView,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPlainTextEdit,
    QSplitter,
    QTableView,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from parquet_explorer import __version__
from parquet_explorer.about import AboutDialog
from parquet_explorer.data import DEFAULT_QUERY, ParquetSession, QueryError
from parquet_explorer.models import QueryResultModel

PARQUET_FILTER = "Parquet files (*.parquet *.pq);;All files (*)"


def _monospace_font() -> QFont:
    font = QFont("Consolas" if hasattr(QFont, "Monospace") else "")
    font.setStyleHint(QFont.StyleHint.Monospace)
    font.setFamilies(["Cascadia Mono", "Consolas", "Menlo", "DejaVu Sans Mono", "monospace"])
    return font


class MainWindow(QMainWindow):
    """Open a Parquet file, edit the query, run it, look at the rows."""

    def __init__(self, session: ParquetSession | None = None) -> None:
        super().__init__()
        self.session = session or ParquetSession()
        self.model = QueryResultModel(parent=self)
        self._settings = QSettings("parquet-explorer", "parquet-explorer")

        self.setWindowTitle(f"Parquet Explorer {__version__}")
        self.resize(1100, 720)
        self.setAcceptDrops(True)

        self._build_ui()
        self._build_actions()
        self._update_enabled_state()

    # -- construction -------------------------------------------------------

    def _build_ui(self) -> None:
        self.columns_tree = QTreeWidget()
        self.columns_tree.setHeaderLabels(["Column", "Type"])
        self.columns_tree.setRootIsDecorated(False)
        self.columns_tree.setAlternatingRowColors(True)
        self.columns_tree.itemDoubleClicked.connect(self._insert_column_name)

        self.editor = QPlainTextEdit()
        self.editor.setFont(_monospace_font())
        self.editor.setPlaceholderText("Open a Parquet file to start querying…")
        self.editor.setTabChangesFocus(False)

        self.error_label = QLabel()
        self.error_label.setWordWrap(True)
        self.error_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.error_label.setStyleSheet(
            "QLabel { background: #4a1f22; color: #ffd5d5; padding: 8px; border-radius: 4px; }"
        )
        self.error_label.hide()

        self.table = QTableView()
        self.table.setModel(self.model)
        self.table.setAlternatingRowColors(True)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectItems)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setHorizontalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        self.table.verticalHeader().setDefaultSectionSize(22)

        results = QWidget()
        results_layout = QVBoxLayout(results)
        results_layout.setContentsMargins(0, 0, 0, 0)
        results_layout.setSpacing(6)
        results_layout.addWidget(self.error_label)
        results_layout.addWidget(self.table)

        right = QSplitter(Qt.Orientation.Vertical)
        right.addWidget(self.editor)
        right.addWidget(results)
        right.setStretchFactor(0, 1)
        right.setStretchFactor(1, 3)
        right.setSizes([180, 500])

        main_splitter = QSplitter(Qt.Orientation.Horizontal)
        main_splitter.addWidget(self.columns_tree)
        main_splitter.addWidget(right)
        main_splitter.setStretchFactor(0, 0)
        main_splitter.setStretchFactor(1, 1)
        main_splitter.setSizes([240, 860])

        self.setCentralWidget(main_splitter)

        self.status_label = QLabel("No file open")
        self.statusBar().addPermanentWidget(self.status_label)

    def _build_actions(self) -> None:
        self.open_action = QAction("&Open…", self)
        self.open_action.setShortcut(QKeySequence.StandardKey.Open)
        self.open_action.setStatusTip("Open a Parquet file")
        self.open_action.triggered.connect(self.choose_file)

        self.run_action = QAction("&Run", self)
        self.run_action.setShortcuts([QKeySequence("Ctrl+Return"), QKeySequence("F5")])
        self.run_action.setStatusTip("Run the query (Ctrl+Enter)")
        self.run_action.triggered.connect(self.run_query)

        self.export_action = QAction("&Export CSV…", self)
        self.export_action.setShortcut(QKeySequence("Ctrl+E"))
        self.export_action.setStatusTip("Write the current query's result to a CSV file")
        self.export_action.triggered.connect(self.export_csv)

        self.quit_action = QAction("&Quit", self)
        self.quit_action.setShortcut(QKeySequence.StandardKey.Quit)
        self.quit_action.triggered.connect(self.close)

        self.about_action = QAction("&About Parquet Explorer", self)
        # AboutRole moves it into the application menu on macOS, where a Help
        # menu entry named "About …" is not where anyone looks for it.
        self.about_action.setMenuRole(QAction.MenuRole.AboutRole)
        self.about_action.setStatusTip("Version details and open source licenses")
        self.about_action.triggered.connect(self.show_about)

        file_menu = self.menuBar().addMenu("&File")
        file_menu.addAction(self.open_action)
        file_menu.addAction(self.export_action)
        file_menu.addSeparator()
        file_menu.addAction(self.quit_action)

        query_menu = self.menuBar().addMenu("&Query")
        query_menu.addAction(self.run_action)

        help_menu = self.menuBar().addMenu("&Help")
        help_menu.addAction(self.about_action)

        toolbar = self.addToolBar("Main")
        toolbar.setMovable(False)
        toolbar.addAction(self.open_action)
        toolbar.addAction(self.run_action)
        toolbar.addAction(self.export_action)

    # -- actions ------------------------------------------------------------

    def choose_file(self) -> None:
        start_dir = str(self._settings.value("last_dir", "", type=str))
        path, _ = QFileDialog.getOpenFileName(self, "Open Parquet file", start_dir, PARQUET_FILTER)
        if path:
            self.open_file(path)

    def open_file(self, path: str | Path) -> None:
        """Register ``path`` as the ``data`` view and run the default query."""
        try:
            columns = self.session.open(path)
        except QueryError as exc:
            self._show_error(f"Could not open {path}\n\n{exc}")
            return

        self._settings.setValue("last_dir", str(Path(path).parent))
        self.columns_tree.clear()
        for column in columns:
            QTreeWidgetItem(self.columns_tree, [column.name, column.type])
        self.columns_tree.resizeColumnToContents(0)

        self.editor.setPlainText(DEFAULT_QUERY)
        self.setWindowTitle(f"{Path(path).name} — Parquet Explorer {__version__}")
        self._update_enabled_state()
        self.run_query()

    def run_query(self) -> None:
        if not self.session.is_open:
            return
        sql = self.editor.toPlainText().strip()
        if not sql:
            return

        self.setCursor(Qt.CursorShape.WaitCursor)
        try:
            result = self.session.run(sql)
        except QueryError as exc:
            self._show_error(str(exc))
            return
        finally:
            self.unsetCursor()

        self._clear_error()
        self.model.set_result(result)
        self.table.resizeColumnsToContents()
        self._cap_column_widths()
        self.status_label.setText(
            f"{result.row_count:,} rows × {result.column_count} columns"
            f" · {result.elapsed * 1000:.0f} ms"
        )

    def export_csv(self) -> None:
        if not self.session.is_open:
            return
        sql = self.editor.toPlainText().strip()
        if not sql:
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "Export result as CSV", "result.csv", "CSV files (*.csv);;All files (*)"
        )
        if not path:
            return
        try:
            self.session.export_csv(sql, path)
        except QueryError as exc:
            QMessageBox.warning(self, "Export failed", str(exc))
            return
        self.statusBar().showMessage(f"Exported to {path}", 5000)

    def show_about(self) -> None:
        """Open the About dialog — version details and the licenses shipped."""
        AboutDialog(self).exec()

    # -- helpers ------------------------------------------------------------

    def _insert_column_name(self, item: QTreeWidgetItem) -> None:
        self.editor.insertPlainText(item.text(0))
        self.editor.setFocus()

    def _cap_column_widths(self, maximum: int = 320) -> None:
        header = self.table.horizontalHeader()
        for section in range(self.model.columnCount()):
            if header.sectionSize(section) > maximum:
                header.resizeSection(section, maximum)

    def _show_error(self, message: str) -> None:
        self.error_label.setText(message)
        self.error_label.show()
        self.status_label.setText("Query failed")

    def _clear_error(self) -> None:
        self.error_label.clear()
        self.error_label.hide()

    def _update_enabled_state(self) -> None:
        is_open = self.session.is_open
        self.run_action.setEnabled(is_open)
        self.export_action.setEnabled(is_open)

    # -- drag and drop ------------------------------------------------------

    def dragEnterEvent(self, event: QDragEnterEvent) -> None:
        urls = event.mimeData().urls()
        if len(urls) == 1 and urls[0].isLocalFile():
            event.acceptProposedAction()

    def dropEvent(self, event: QDropEvent) -> None:
        urls = event.mimeData().urls()
        if urls:
            self.open_file(urls[0].toLocalFile())
            event.acceptProposedAction()

    def closeEvent(self, event) -> None:
        self.session.close()
        super().closeEvent(event)
