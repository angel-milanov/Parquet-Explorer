"""The main application window."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QSettings, Qt, QTimer
from PySide6.QtGui import (
    QAction,
    QDragEnterEvent,
    QDropEvent,
    QFont,
    QGuiApplication,
    QKeySequence,
)
from PySide6.QtWidgets import (
    QAbstractItemView,
    QDialog,
    QFileDialog,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QSplitter,
    QTableView,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from parquet_explorer import __version__
from parquet_explorer.about import AboutDialog
from parquet_explorer.avro import avro_schema_json
from parquet_explorer.data import DEFAULT_QUERY, ParquetSession, QueryError
from parquet_explorer.models import QueryResultModel
from parquet_explorer.parquet_schema import SchemaError

PARQUET_FILTER = "Parquet files (*.parquet *.pq);;All files (*)"


def _monospace_font() -> QFont:
    font = QFont("Consolas" if hasattr(QFont, "Monospace") else "")
    font.setStyleHint(QFont.StyleHint.Monospace)
    font.setFamilies(["Cascadia Mono", "Consolas", "Menlo", "DejaVu Sans Mono", "monospace"])
    return font


class AvroSchemaDialog(QDialog):
    """The open file's schema as an Avro record, with a button to copy it."""

    #: How long the copy button confirms itself before going back to normal.
    CONFIRM_MS = 1500

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.resize(640, 560)

        self.view = QPlainTextEdit()
        self.view.setReadOnly(True)
        self.view.setFont(_monospace_font())
        self.view.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)

        self.copy_button = QPushButton("&Copy to Clipboard")
        self.copy_button.setDefault(True)
        self.copy_button.clicked.connect(self.copy)

        close_button = QPushButton("Close")
        close_button.clicked.connect(self.reject)

        buttons = QHBoxLayout()
        buttons.addStretch(1)
        buttons.addWidget(self.copy_button)
        buttons.addWidget(close_button)

        layout = QVBoxLayout(self)
        layout.addWidget(self.view)
        layout.addLayout(buttons)

    @property
    def text(self) -> str:
        return self.view.toPlainText()

    def set_schema(self, text: str, file_name: str) -> None:
        self.setWindowTitle(f"Avro schema — {file_name}")
        self.view.setPlainText(text)

    def copy(self) -> None:
        QGuiApplication.clipboard().setText(self.text)
        self.copy_button.setText("Copied")
        # Passing self as the timer's context means a dialog destroyed inside the
        # confirmation window takes the pending callback with it.
        QTimer.singleShot(self.CONFIRM_MS, self, self._restore_copy_button)

    def _restore_copy_button(self) -> None:
        self.copy_button.setText("&Copy to Clipboard")


class MainWindow(QMainWindow):
    """Open a Parquet file, edit the query, run it, look at the rows."""

    def __init__(self, session: ParquetSession | None = None) -> None:
        super().__init__()
        self.session = session or ParquetSession()
        self.model = QueryResultModel(parent=self)
        self.avro_dialog: AvroSchemaDialog | None = None
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

        self.avro_action = QAction("&Avro Schema…", self)
        self.avro_action.setShortcut(QKeySequence("Ctrl+Shift+A"))
        self.avro_action.setStatusTip("Show the file's schema as an Avro record (.avsc)")
        self.avro_action.triggered.connect(self.show_avro_schema)

        self.copy_avro_action = QAction("Copy Avro &Schema", self)
        self.copy_avro_action.setShortcut(QKeySequence("Ctrl+Shift+C"))
        self.copy_avro_action.setStatusTip("Copy the file's Avro schema (.avsc) to the clipboard")
        self.copy_avro_action.triggered.connect(self.copy_avro_schema)

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
        file_menu.addAction(self.avro_action)
        file_menu.addAction(self.copy_avro_action)
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
        toolbar.addAction(self.avro_action)

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
        self._sync_avro_dialog()
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

    def show_avro_schema(self) -> None:
        """Open (or refocus) the window showing the file's Avro schema."""
        text = self._avro_schema()
        if text is None:
            return
        if self.avro_dialog is None:
            self.avro_dialog = AvroSchemaDialog(self)
        self.avro_dialog.set_schema(text, self._file_name())
        self.avro_dialog.show()
        self.avro_dialog.raise_()
        self.avro_dialog.activateWindow()

    def copy_avro_schema(self) -> None:
        """Put the file's Avro schema on the clipboard without opening anything."""
        text = self._avro_schema()
        if text is None:
            return
        QGuiApplication.clipboard().setText(text)
        self.statusBar().showMessage("Avro schema copied to the clipboard", 5000)

    def show_about(self) -> None:
        """Open the About dialog — version details and the licenses shipped."""
        AboutDialog(self).exec()

    # -- helpers ------------------------------------------------------------

    def _avro_schema(self) -> str | None:
        """The open file's Avro schema, or ``None`` after reporting why not.

        The schema is read from the Parquet footer rather than from the ``data``
        view, so it is derived afresh each time and never goes stale.
        """
        path = self.session.path
        if not path:
            return None
        try:
            return avro_schema_json(path)
        except SchemaError as exc:
            QMessageBox.warning(self, "Avro schema", f"Could not read the schema.\n\n{exc}")
            return None

    def _file_name(self) -> str:
        return Path(self.session.path).name if self.session.path else ""

    def _sync_avro_dialog(self) -> None:
        """Keep an open schema window in step with a newly opened file."""
        if self.avro_dialog is None or not self.avro_dialog.isVisible():
            return
        text = self._avro_schema()
        if text is not None:
            self.avro_dialog.set_schema(text, self._file_name())

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
        self.avro_action.setEnabled(is_open)
        self.copy_avro_action.setEnabled(is_open)

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
