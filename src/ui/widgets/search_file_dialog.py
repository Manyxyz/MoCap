from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QLineEdit, QListWidget, QListWidgetItem,
    QTextEdit, QHBoxLayout, QPushButton, QMenu, QAbstractItemView
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QKeySequence, QGuiApplication, QAction
try:
    from PySide6.QtGui import QShortcut
except Exception:
    from PySide6.QtWidgets import QShortcut

from pathlib import Path

from ...database.db_manager import DatabaseManager
from ...database.models import File, Study


class SearchFileDialog(QDialog):
    fileChosen = Signal(str, int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Search Files")
        self.setMinimumWidth(650)

        self.setStyleSheet("""
            QDialog { background: #545c64; }
            QLabel { color: #ffffff; font-size: 13px; }
            QLineEdit {
                border: 2px solid #4BA5D6;
                border-radius: 6px;
                padding: 8px 12px;
                font-size: 13px;
                background: white;
                color: #222;
                selection-background-color: #3aa0ff;
                selection-color: white;
            }
            QPushButton {
                border-radius: 6px;
                padding: 8px 20px;
                font-size: 13px;
                font-weight: bold;
            }
            QListWidget {
                background: #ffffff;
                color: #222;
                border: 2px solid #ccc;
                border-radius: 4px;
                outline: none;
            }
            QListWidget:focus { outline: none; }
            QListWidget::item:selected { background: #3aa0ff; color: #fff; outline: none }
            QTextEdit {
                background: #ffffff;
                color: #222;
                border: 2px solid #ccc;
                border-radius: 4px;
            }
            QScrollBar:vertical {
                background: #f8f8f8;
                width: 13px;
                margin: 2px;
                border: 2px solid #b8b8b8;
                border-radius: 6px;
            }
            QScrollBar::handle:vertical {
                background: #72BFE9;
                min-height: 30px;
                border-radius: 6px;
            }
            QScrollBar::handle:vertical:hover {
                background: #176691;
            }
            QScrollBar::add-line:vertical,
            QScrollBar::sub-line:vertical {
                height: 0px;
            }
            QScrollBar:horizontal {
                background: #f8f8f8;
                height: 13px;
                margin: 2px;
                border: 2px solid #b8b8b8;
                border-radius: 6px;
            }
            QScrollBar::handle:horizontal {
                background: #d0d0d0;
                min-width: 30px;
                border-radius: 6px;
            }
            QScrollBar::add-line:horizontal,
            QScrollBar::sub-line:horizontal {
                width: 0px;
            }
        """)

        self.db = DatabaseManager()
        self._all_files = []

        layout = QVBoxLayout(self)

        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("Type filename or substring...")
        layout.addWidget(self.search_edit)

        self.results = QListWidget()
        self.results.setSelectionMode(QAbstractItemView.SingleSelection)
        self.results.setContextMenuPolicy(Qt.CustomContextMenu)
        layout.addWidget(self.results, 1)

        self.details = QTextEdit("Select a file to see details")
        self.details.setReadOnly(True)
        self.details.setAcceptRichText(True)
        self.details.setTextInteractionFlags(Qt.TextSelectableByMouse | Qt.TextSelectableByKeyboard)
        self.details.setMinimumHeight(30)
        self.details.setMaximumHeight(100)
        layout.addWidget(self.details)

        btn_row = QHBoxLayout()
        btn_row.addStretch()
        self.open_btn = QPushButton("Open")
        self.open_btn.setEnabled(False)
        self.close_btn = QPushButton("Close")

        self.open_btn.setStyleSheet("""
            QPushButton {
                background: white;
                color: #0a0a0a;
                border: 2px solid #3aa0ff;
                border-radius: 6px;
                padding: 8px 18px;
                font-weight: bold;
            }
            QPushButton:hover {
                background: #e8f6ff;
            }
            QPushButton:pressed {
                background: #d0eaff;
            }
            QPushButton:disabled {
                background: #f5f7fa;
                color: #9aa6b2;
                border-color: #cfeafe;
            }
        """)
        self.close_btn.setStyleSheet("""
            QPushButton {
                background: white;
                color: #0a0a0a;
                border: 2px solid #3aa0ff;
                border-radius: 6px;
                padding: 8px 18px;
                font-weight: bold;
            }
            QPushButton:hover {
                background: #e8f6ff;
            }
            QPushButton:pressed {
                background: #d0eaff;
            }
        """)
        btn_row.addWidget(self.open_btn)
        btn_row.addWidget(self.close_btn)
        layout.addLayout(btn_row)

        
        self.search_edit.textChanged.connect(self._on_search_text_changed)
        self.results.currentItemChanged.connect(self._on_selection_changed)
        self.results.itemDoubleClicked.connect(self._on_item_activated)
        self.open_btn.clicked.connect(self._on_open_clicked)
        self.close_btn.clicked.connect(self.reject)
        self.results.customContextMenuRequested.connect(self._on_results_context_menu)

        self._copy_shortcut = QShortcut(QKeySequence.Copy, self)
        self._copy_shortcut.activated.connect(self._copy_selection_to_clipboard)

        self._reload_cache()

    def _reload_cache(self):
        try:
            self._all_files = self.db.get_all_files()
        except Exception:
            self._all_files = []

    def _on_search_text_changed(self, text: str):
        q = (text or "").strip().lower()
        self.results.clear()
        if not q:
            return
        for f in self._all_files:
            name = (getattr(f, "name", None) or "") if hasattr(f, "name") else Path(f.file_path).name
            if q in (name or "").lower() or q in (f.file_path or "").lower():
                if f.file_path:
                    p = Path(f.file_path)
                    parent = p.parent.name or str(p.parent)
                    display = f"{name}  —  {parent}/{p.name}"
                else:
                    display = name
                itm = QListWidgetItem(display)
                itm.setData(Qt.UserRole, f)
                self.results.addItem(itm)
        if self.results.count() > 0:
            self.results.setCurrentRow(0)

    def _on_selection_changed(self, current: QListWidgetItem, previous: QListWidgetItem):
        self.open_btn.setEnabled(bool(current))
        if not current:
            self.details.setHtml("Select a file to see details")
            return
        f: File = current.data(Qt.UserRole)
        path = f.file_path or "(no path)"
        study_name = "(no study)"
        try:
            if getattr(f, "study_id", None):
                s: Study = self.db.get_study(f.study_id)
                if s:
                    study_name = s.name or study_name
        except Exception:
            pass
        html = (
            f"<b>Name:</b> {getattr(f, 'name', None) or (Path(f.file_path).name if f.file_path else '')}<br>"
            f"<b>Path:</b> {path}<br>"
            f"<b>Study:</b> {study_name}"
        )
        self.details.setHtml(html)

    def _on_item_activated(self, item: QListWidgetItem):
        f: File = item.data(Qt.UserRole)
        if f and f.file_path:
            self.fileChosen.emit(str(f.file_path), int(getattr(f, "study_id", 0) or 0))
            self.accept()

    def _on_open_clicked(self):
        self.open_selected()

    def _on_results_context_menu(self, pos):
        item = self.results.itemAt(pos)
        if not item:
            return
        f: File = item.data(Qt.UserRole)
        menu = QMenu(self)
        open_action = QAction("Open", menu)
        open_action.triggered.connect(lambda: self._open_item(f))
        menu.addAction(open_action)

        copy_path = QAction("Copy Path", menu)
        copy_path.triggered.connect(lambda: self._copy_text(str(f.file_path)))
        menu.addAction(copy_path)

        copy_info = QAction("Copy Study Info", menu)
        copy_info.triggered.connect(lambda: self._copy_study_info(f))
        menu.addAction(copy_info)

        menu.exec(self.results.mapToGlobal(pos))

    def _open_item(self, f: File):
        if f and f.file_path:
            self.fileChosen.emit(str(f.file_path), int(getattr(f, "study_id", 0) or 0))
            self.accept()

    def _copy_text(self, text: str):
        if not text:
            return
        QGuiApplication.clipboard().setText(text)

    def _copy_study_info(self, f: File):
        try:
            study_name = "(no study)"
            date_str = ""
            type_str = ""
            if getattr(f, "study_id", None):
                s = self.db.get_study(f.study_id)
                if s:
                    study_name = s.name or study_name
                    date_str = s.date.strftime("%Y-%m-%d") if getattr(s, "date", None) else ""
                    type_str = getattr(s, "type_name", "") or ""
            parts = [f"Name: {getattr(f, 'name', None) or Path(f.file_path).name}", f"Path: {f.file_path}", f"Study: {study_name}"]
            if type_str:
                parts.append(f"Type: {type_str}")
            if date_str:
                parts.append(f"Date: {date_str}")
            text = "\n".join(parts)
            self._copy_text(text)
        except Exception:
            pass

    def _copy_selection_to_clipboard(self):
        try:
            cursor = self.details.textCursor()
            if cursor is not None and cursor.hasSelection():
                selected = cursor.selectedText()
                if selected:
                    self._copy_text(selected)
                    return
        except Exception:
            pass

        item = self.results.currentItem()
        if item:
            self._copy_text(item.text())
            return

        return

    def open_selected(self) -> bool:
        item = self.results.currentItem()
        if not item:
            return False
        f: File = item.data(Qt.UserRole)
        if f and f.file_path:
            self.fileChosen.emit(str(f.file_path), int(getattr(f, "study_id", 0) or 0))
            self.accept()
            return True
        return False