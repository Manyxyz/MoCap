from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout, QLineEdit,
    QPushButton, QLabel, QListWidget, QListWidgetItem, QComboBox, 
    QDateEdit, QMessageBox, QProgressDialog, QCompleter
)
from PySide6.QtCore import Qt, QDate, Signal, QThread, QStringListModel
from pathlib import Path
from datetime import date
from PySide6.QtGui import QAction
from PySide6.QtWidgets import QMenu
from ...database.db_manager import DatabaseManager
from ...database.models import Study, Participant
from ..message_box import styled_message_box

class UpdateFilePathsWorker(QThread):
    finished = Signal(int) 
    progress = Signal(str)
    error = Signal(str)

    def __init__(self, db: 'DatabaseManager', study_id: int, old_root: Path, new_root: Path, require_exists: bool = False):
        super().__init__()
        self.db = db
        self.study_id = study_id
        self.old_root = old_root.resolve() if old_root else None
        self.new_root = new_root.resolve()
        self.require_exists = require_exists

    def run(self):
        try:
            self.progress.emit("Loading file list from database...")
            files = self.db.get_study_files(self.study_id) or []
            total = len(files)
            updated = 0
            import os

            for i, f in enumerate(files, start=1):
                try:
                    if not getattr(f, 'file_path', None):
                        continue
                    old_fp = Path(f.file_path)
                    rel = None
                    if self.old_root:
                        try:
                            rel_candidate = os.path.relpath(str(old_fp.resolve()), str(self.old_root))
                            if not rel_candidate.startswith(".."):
                                rel = Path(rel_candidate)
                        except Exception:
                            try:
                                rel = old_fp.relative_to(self.old_root)
                            except Exception:
                                rel = None

                    if rel is not None:
                        new_fp = Path(self.new_root) / rel
                    else:
                        new_fp = Path(self.new_root) / old_fp.name

                    if self.require_exists and not new_fp.exists():
                        continue

                    f.file_path = str(new_fp.resolve())
                    self.db.update_file(f)
                    updated += 1

                    if i % 10 == 0 or i == total:
                        self.progress.emit(f"Updated {updated}/{total} files...")
                except Exception:
                    continue

            self.finished.emit(updated)
        except Exception as e:
            self.error.emit(str(e))


class EditStudyDialog(QDialog):
    
    studyUpdated = Signal(int)
    
    def __init__(self, study_id: int, parent=None):
        super().__init__(parent)
        self.study_id = study_id
        self.db = DatabaseManager()
        self.setWindowTitle("Edit Study")
        self.setMinimumWidth(500)
        self._new_folder_path = None 
        self._setup_ui()
        self._load_study_data()


    
    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(16)
        self.setStyleSheet("background: #545c64;")
        
        title = QLabel("Edit Study")
        title.setStyleSheet("font-size: 18px; font-weight: bold; color: #ffffff;")
        layout.addWidget(title)
        
        form = QFormLayout()
        form.setSpacing(12)
        
        folder_label = QLabel("Study Folder:")
        folder_label.setStyleSheet("font-weight: bold; color: #ffffff;")
        
        folder_row = QHBoxLayout()
        self.folder_display = QLabel()
        self.folder_display.setStyleSheet("""
            QLabel {
                border: 1px solid #ccc;
                border-radius: 4px;
                padding: 6px;
                background: #f5f5f5;
                color: #000000;
            }
        """)
        folder_row.addWidget(self.folder_display, 1)
        
        self.change_folder_btn = QPushButton("Change...")
        self.change_folder_btn.clicked.connect(self._browse_folder)
        self.change_folder_btn.setStyleSheet("""
            QPushButton {
                background: #000000;
                color: white;
                border-radius: 4px;
                padding: 6px 12px;
            }
            QPushButton:hover { background: #5a6268; }
        """)
        folder_row.addWidget(self.change_folder_btn)
        
        form.addRow(folder_label, folder_row)
        
        name_label = QLabel("Study Name:")
        name_label.setStyleSheet("font-weight: bold; color: #ffffff;")

        name_layout = QHBoxLayout()

        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText("Enter study name")
        self.name_edit.setStyleSheet("""
            QLineEdit {
                border: 2px solid #ccc;
                border-radius: 4px;
                padding: 2px;
                background: white;
                color: #000000;
            }
            QLineEdit:focus {
                border: 2px solid #3aa0ff;
            }
        """)

        name_layout.addWidget(self.name_edit, 3)
        self.name_edit.setFixedHeight(28)
        
        self.identifiers_inline = QLabel("")
        self.identifiers_inline.setStyleSheet("""
            QLabel {
                border: 1px dashed #ccc;
                border-radius: 4px;
                padding: 6px;
                background: #f9f9f9;
                color: #000000;
                font-style: italic;
            }
        """)
        self.identifiers_inline.setAlignment(Qt.AlignCenter)
        self.identifiers_inline.setMinimumWidth(120)
        self.identifiers_inline.setFixedHeight(28)

        name_layout.addWidget(self.identifiers_inline, 1)

        form.addRow(name_label, name_layout)
        
        participant_layout = QVBoxLayout()
        participant_header = QHBoxLayout()
        
        participant_label = QLabel("Participants:")
        participant_label.setStyleSheet("font-weight: bold; color: #ffffff;")
        participant_header.addWidget(participant_label)
        
        self.add_participant_btn = QPushButton("+")
        self.add_participant_btn.setFixedSize(24, 24)
        self.add_participant_btn.setStyleSheet("""
            QPushButton {
                background: #3aa0ff;
                color: white;
                border-radius: 12px;
                font-weight: bold;
            }
            QPushButton:hover { background: #2a8fdf; }
        """)
        self.add_participant_btn.clicked.connect(self._add_new_participant)
        participant_header.addWidget(self.add_participant_btn)
        participant_header.addStretch()
        
        participant_layout.addLayout(participant_header)

        self.participant_search = QLineEdit()
        self.participant_search.setPlaceholderText("Search participants (name / code)")
        self.participant_search.setClearButtonEnabled(True)
        self.participant_search.setMaximumHeight(26)

        self.participant_search.setStyleSheet("""
            QLineEdit {
                background: #545c64;
                color: white;
                border: 1px solid #777;
                border-radius: 4px;
                padding: 4px 6px;
            }
            QLineEdit::placeholder {
                color: #ffffff;
                opacity: 0.85;
            }
        """)

        participant_layout.addWidget(self.participant_search)

        self._participant_search_model = QStringListModel()
        self._participant_search_map: dict[str, int] = {}
        self._participant_completer = QCompleter(self._participant_search_model, self)
        self._participant_completer.setCaseSensitivity(Qt.CaseInsensitive)

        self._participant_completer.setFilterMode(Qt.MatchContains)

        try:
            popup = self._participant_completer.popup()
            popup.setStyleSheet("""
                QListView {
                    background: #545c64;
                    color: #fff;
                    border: 1px solid #3aa0ff;
                    padding: 2px;
                    outline: none;
                }
                QListView:focus { outline: none; }
                QListView::item {
                    padding: 6px 8px;
                    outline: none;
                }
                QListView::item:selected {
                    background: #3aa0ff;
                    color: #fff;
                    outline: none;
                }
                QListView::item:focus { outline: none; }
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
        except Exception:
            pass

        self.participant_search.setCompleter(self._participant_completer)
        self._participant_completer.activated.connect(self._on_participant_completer_activated)
        

        self.participant_list = QListWidget()
        self.participant_list.setMaximumHeight(120)
        self.participant_list.setSelectionMode(QListWidget.MultiSelection)
        self.participant_list.setStyleSheet("""
            QListWidget {
                background: #545c64;
                border: 1px solid #ccc;
                border-radius: 4px;
                padding: 4px;
                outline: none;
            }
            QListWidget::item {
                padding: 4px;
                color: #ffffff;
            }
            QListWidget::item:selected {
                background: #3aa0ff;
                color: white;
            }
            QListWidget::item:hover {
                border-radius: 0px;
                background: #71baff;
            }
        """)
        
        self.participant_list.setContextMenuPolicy(Qt.CustomContextMenu)
        self.participant_list.customContextMenuRequested.connect(self._show_participant_context_menu)
        
        self.participant_list.itemSelectionChanged.connect(self._update_study_name)
        
        participant_layout.addWidget(self.participant_list)
        
        form.addRow(participant_layout)
        
        type_layout = QVBoxLayout()
        type_header = QHBoxLayout()
        
        type_label = QLabel("Type:")
        type_label.setStyleSheet("font-weight: bold; color: #ffffff;")
        type_header.addWidget(type_label)
        
        self.add_type_btn = QPushButton("+")
        self.add_type_btn.setFixedSize(24, 24)
        self.add_type_btn.setStyleSheet("""
            QPushButton {
                background: #3aa0ff;
                color: white;
                border-radius: 12px;
                font-weight: bold;
            }
            QPushButton:hover { background: #2a8fdf; }
        """)
        self.add_type_btn.clicked.connect(self._add_custom_type)
        type_header.addWidget(self.add_type_btn)
        type_header.addStretch()
        
        type_layout.addLayout(type_header)
        
        self.type_combo = QComboBox()
        self.type_combo.setEditable(False)
        self.type_combo.setStyleSheet("""
            QComboBox {
                border: 1px solid #ccc;
                border-radius: 4px;
                padding: 6px;
                color: #ffffff;
            }
            QComboBox QAbstractItemView {
                color: #ffffff;
            }
        """)
        self.type_combo.setContextMenuPolicy(Qt.CustomContextMenu)
        self.type_combo.customContextMenuRequested.connect(self._show_type_context_menu)
        
        type_layout.addWidget(self.type_combo)
        
        form.addRow(type_layout)
        
        date_label = QLabel("Date:")
        date_label.setStyleSheet("font-weight: bold; color: #ffffff;")
        
        self.date_edit = QDateEdit()
        self.date_edit.setCalendarPopup(True)
        self.date_edit.setDate(QDate.currentDate())
        self.date_edit.setStyleSheet("""
            QDateEdit {
                border: 1px solid #ccc;
                border-radius: 4px;
                padding: 6px;
                color: #ffffff;
            }
        """)
        
        form.addRow(date_label, self.date_edit)
        
        layout.addLayout(form)
        
        button_layout = QHBoxLayout()
        
        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.setStyleSheet("""
            QPushButton {
                background: #6c757d;
                color: white;
                border-radius: 4px;
                padding: 8px 16px;
            }
            QPushButton:hover { background: #5a6268; }
        """)
        self.cancel_btn.clicked.connect(self.reject)
        
        self.save_btn = QPushButton("Save Changes")
        self.save_btn.setStyleSheet("""
            QPushButton {
                background: #28a745;
                color: white;
                border-radius: 4px;
                padding: 8px 16px;
                font-weight: bold;
            }
            QPushButton:hover { background: #218838; }
        """)
        self.save_btn.clicked.connect(self._save_study)
        
        button_layout.addStretch()
        button_layout.addWidget(self.cancel_btn)
        button_layout.addWidget(self.save_btn)
        
        layout.addLayout(button_layout)

    def _browse_folder(self):
        from PySide6.QtWidgets import QFileDialog
        from pathlib import Path
        
        folder = QFileDialog.getExistingDirectory(
            self,
            "Select Study Folder",
            str(Path(self.folder_display.text()).parent if self.folder_display.text() else Path.home())
        )
        if folder:
            new_path = Path(folder).resolve()
            self.folder_display.setText(str(new_path))
            self._new_folder_path = new_path

    def _update_study_name(self):
        selected_items = self.participant_list.selectedItems()
        
        if not selected_items:
            self.identifiers_inline.setText("")
            self.identifiers_inline.setStyleSheet("""
                QLabel {
                    border: 1px dashed #ccc;
                    border-radius: 4px;
                    padding: 6px;
                    background: #f9f9f9;
                    color: #666;
                    font-style: italic;
                }
            """)
            return
        
        identifiers = []
        for item in selected_items:
            participant_id = item.data(Qt.UserRole)
            participant = self.db.get_participant(participant_id)
            
            if participant:
                identifiers.append(participant.code)
        
        if identifiers:
            identifier_text = f"[{', '.join(identifiers)}]"
            self.identifiers_inline.setText(identifier_text)
            self.identifiers_inline.setStyleSheet("""
                QLabel {
                    border: 2px solid #3aa0ff;
                    border-radius: 4px;
                    padding: 6px;
                    background: #e8f4ff;
                    color: #222;
                    font-weight: bold;
                }
            """)
        else:
            self.identifiers_inline.setText("[no codes]")
            self.identifiers_inline.setStyleSheet("""
                QLabel {
                    border: 2px solid #dc3545;
                    border-radius: 4px;
                    padding: 6px;
                    background: #f8d7da;
                    color: #dc3545;
                    font-weight: bold;
                }
            """)

    def _load_study_data(self):
        try:
            study = self.db.get_study(self.study_id)
            if not study:
                styled_message_box(QMessageBox.Critical, "Error", "Study not found!", parent=self)
                self.reject()
                return
            
            if study.path:
                self.original_folder_name = Path(study.path).name
                self.folder_display.setText(study.path)
            else:
                self.original_folder_name = "Unknown"
                self.folder_display.setText("(no folder path)")
            
            self._new_folder_path = None

            study_name = study.name
            
            import re
            match = re.match(r'^(.*?)\s*\[(.*?)\]\s*$', study_name)
            if match:
                base_name = match.group(1).strip()
            else:
                base_name = study_name
            
            self.name_edit.setText(base_name)
            
            self._load_study_types()
            
            if study.type_name:
                index = self.type_combo.findText(study.type_name)
                if index >= 0:
                    self.type_combo.setCurrentIndex(index)
            
            if study.date:
                self.date_edit.setDate(QDate(study.date.year, study.date.month, study.date.day))
            
            self._load_participants()
            
            current_participants = self.db.get_study_participants(self.study_id)
            current_ids = {p.id_participant for p in current_participants}
            
            for i in range(self.participant_list.count()):
                item = self.participant_list.item(i)
                participant_id = item.data(Qt.UserRole)
                if participant_id in current_ids:
                    item.setSelected(True)
            
            self._update_study_name()
            
        except Exception as e:
            styled_message_box(QMessageBox.Critical, "Error", f"Failed to load study data:\n{e}", parent=self)
            self.reject()
        
    def _load_participants(self):
        try:
            participants = self.db.get_all_participants()
            self.participant_list.clear()
            
            for p in participants:
                item = QListWidgetItem(f"{p.name} {p.surname} ({p.code})")
                item.setData(Qt.UserRole, p.id_participant)
                self.participant_list.addItem(item)
            self._refresh_participant_search_model(participants)
        except Exception as e:
            pass
        
    def _refresh_participant_search_model(self, participants=None):
        """Rebuild completer model from participants (display -> id mapping).
        Keep suggestions as full displays "Name Surname (CODE)". Typing code will match via MatchContains.
        """
        try:
            if participants is None:
                participants = self.db.get_all_participants()
        except Exception:
            participants = []

        suggestions = []
        self._participant_search_map.clear()
        seen = set()

        for p in participants:
            name = (p.name or "").strip()
            surname = (p.surname or "").strip()
            code = (p.code or "").strip()

            if name or surname:
                display = f"{name} {surname}".strip()
                if code:
                    display = f"{display} ({code})"
            else:
                display = code or ""

            if not display:
                continue

            if display not in seen:
                suggestions.append(display)
                self._participant_search_map[display] = p.id_participant
                seen.add(display)

            if code:
                self._participant_search_map[code] = p.id_participant

        self._participant_search_model.setStringList(suggestions)

    def _on_participant_completer_activated(self, text: str):
        if not text:
            return
        pid = self._participant_search_map.get(text) or self._participant_search_map.get(text.strip())
        if not pid:
            for i in range(self.participant_list.count()):
                it = self.participant_list.item(i)
                if text.lower() in it.text().lower():
                    pid = it.data(Qt.UserRole)
                    break
        if pid:
            self.select_participant_by_id(pid)

    def select_participant_by_id(self, participant_id: int) -> bool:
        """Select and scroll to participant by id without clearing other selections.
        Returns True if found.
        """
        for i in range(self.participant_list.count()):
            it = self.participant_list.item(i)
            try:
                if it.data(Qt.UserRole) == participant_id:
                    it.setSelected(True)
                    try:
                        self.participant_list.scrollToItem(it)
                    except Exception:
                        pass
                    try:
                        self.participant_list.setFocus()
                    except Exception:
                        pass
                    return True
            except Exception:
                continue
        return False
    
    def _load_study_types(self):
        try:
            types = self.db.get_study_types()
            self.type_combo.clear()
            
            if types:
                for type_id, type_name in types:
                    self.type_combo.addItem(type_name, type_id)
            else:
                self.type_combo.addItem("(no types - add one with +)", None)
                
        except Exception as e:
            self.type_combo.clear()
            self.type_combo.addItem("(error loading types)", None)
    
    def _show_participant_context_menu(self, position):
        menu = QMenu(self.participant_list)
    
        item = self.participant_list.itemAt(position)
        
        if item:
            participant_id = item.data(Qt.UserRole)
            
            edit_action = QAction("Edit Participant", menu)
            edit_action.triggered.connect(lambda: self._edit_participant(participant_id))
            menu.addAction(edit_action)
            
            menu.addSeparator()
            
            delete_action = QAction("Delete Participant", menu)
            delete_action.triggered.connect(lambda: self._delete_participant(participant_id))
            menu.addAction(delete_action)
        
        menu.exec(self.participant_list.mapToGlobal(position))

    def _start_update_paths_worker(self, old_root: Path, new_root: Path, require_exists: bool, label: str):
        try:
            self._update_worker = UpdateFilePathsWorker(self.db, self.study_id, old_root, new_root, require_exists=require_exists)

            progress = QProgressDialog(label, None, 0, 0, self)
            progress.setWindowModality(Qt.NonModal)
            progress.setWindowTitle("Updating file paths")
            progress.setMinimumDuration(0)
            progress.setCancelButton(None)
            progress.show()

            def on_progress(msg: str):
                try:
                    progress.setLabelText(msg)
                except Exception:
                    pass

            def on_finished(count: int):
                try:
                    progress.close()
                except Exception:
                    pass
                try:
                    self._update_worker = None
                except Exception:
                    pass

            def on_error(err: str):
                try:
                    progress.close()
                except Exception:
                    pass
                try:
                    self._update_worker = None
                except Exception:
                    pass

            self._update_worker.progress.connect(on_progress)
            self._update_worker.finished.connect(on_finished)
            self._update_worker.error.connect(on_error)

            self._update_worker.start()
        except Exception as e:
            pass
    
    def _edit_participant(self, participant_id: int):
        from .add_participant_dialog import AddParticipantDialog
        
        try:
            participant = self.db.get_participant(participant_id)
            if not participant:
                return
            
            dialog = AddParticipantDialog(self, participant)
            if dialog.exec():
                updated_participant = dialog.get_participant()
                updated_participant.id_participant = participant_id
                
                if self.db.update_participant(updated_participant):
                    selected_ids = {item.data(Qt.UserRole) for item in self.participant_list.selectedItems()}
                    
                    self._load_participants()
                    
                    for i in range(self.participant_list.count()):
                        item = self.participant_list.item(i)
                        if item.data(Qt.UserRole) in selected_ids:
                            item.setSelected(True)
                    
                    styled_message_box(
                        QMessageBox.Information,
                        "Success",
                        f"Participant '{updated_participant.full_name}' updated!",
                        parent=self
                    )
                else:
                    styled_message_box(
                        QMessageBox.Warning,
                        "Error",
                        "Failed to update participant.",
                        parent=self
                    )
        except Exception as e:
            styled_message_box(
                QMessageBox.Critical,
                "Error",
                f"Failed to edit participant:\n{e}",
                parent=self
            )

    def _delete_participant(self, participant_id: int):
        try:
            participant = self.db.get_participant(participant_id)
            if not participant:
                return
            studies_using = self.db.get_participant_studies(participant_id)
            if studies_using:
                styled_message_box(
                    QMessageBox.Warning,
                    "Cannot Delete",
                    f"Participant '{participant.full_name}' ({participant.code}) is used by {len(studies_using)} study/studies.\n\n"
                    "Please reassign or remove the participant from those studies before deleting.",
                    parent=self
                )
                return

            dlg = styled_message_box(
                QMessageBox.Question,
                "Delete Participant",
                f"Delete participant '{participant.full_name}' ({participant.code})?\n\n"
                "This action cannot be undone.",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No,
                parent=self
            )
            reply = dlg.standardButton(dlg.clickedButton()) if dlg else QMessageBox.No
            if reply == QMessageBox.Yes:
                if self.db.delete_participant(participant_id):
                    selected_ids = {item.data(Qt.UserRole) for item in self.participant_list.selectedItems()}
                    selected_ids.discard(participant_id)

                    self._load_participants()

                    for i in range(self.participant_list.count()):
                        item = self.participant_list.item(i)
                        if item.data(Qt.UserRole) in selected_ids:
                            item.setSelected(True)
                    self._update_study_name()

                    styled_message_box(
                        QMessageBox.Information,
                        "Success",
                        f"Participant '{participant.full_name}' deleted.",
                        parent=self
                    )
                else:
                    styled_message_box(
                        QMessageBox.Warning,
                        "Error",
                        "Failed to delete participant.",
                        parent=self
                    )
        except Exception as e:
            styled_message_box(
                QMessageBox.Critical,
                "Error",
                f"An error occurred:\n{e}",
                parent=self
            )
    
    def _add_new_participant(self):
        from .add_participant_dialog import AddParticipantDialog
        
        dialog = AddParticipantDialog(self)
        if dialog.exec():
            participant = dialog.get_participant()
            try:
                participant_id = self.db.add_participant(participant)
                
                selected_ids = set()
                for item in self.participant_list.selectedItems():
                    selected_ids.add(item.data(Qt.UserRole))
                
                self._load_participants()
                
                for i in range(self.participant_list.count()):
                    item = self.participant_list.item(i)
                    pid = item.data(Qt.UserRole)
                    if pid in selected_ids or pid == participant_id:
                        item.setSelected(True)
                
                styled_message_box(QMessageBox.Information, "Success", f"Participant '{participant.full_name}' added!", parent=self)
            except Exception as e:
                styled_message_box(QMessageBox.Critical, "Error", f"Failed to add participant:\n{e}", parent=self)
    
    def _add_custom_type(self):
        from .add_type_dialog import AddTypeDialog
        from PySide6.QtWidgets import QMessageBox
        dialog = AddTypeDialog(self)
        if dialog.exec() == QDialog.Accepted:
            text = dialog.get_type_name()
            if not text:
                return
            try:
                if self.db.add_study_type(text):
                    self._load_study_types()
                    idx = self.type_combo.findText(text)
                    if idx >= 0:
                        self.type_combo.setCurrentIndex(idx)
                    styled_message_box(QMessageBox.Information, "Success", f"Study type '{text}' added successfully!", parent=self)
                else:
                    styled_message_box(QMessageBox.Warning, "Warning", "Failed to add study type. It may already exist.", parent=self)
            except Exception as e:
                styled_message_box(QMessageBox.Critical, "Error", f"Failed to add study type:\n{e}", parent=self)

    def _show_type_context_menu(self, position):
        from PySide6.QtWidgets import QMenu
        from PySide6.QtGui import QAction
        
        menu = QMenu(self.type_combo)
        
        current_index = self.type_combo.currentIndex()
        type_id = self.type_combo.itemData(current_index)
        type_name = self.type_combo.itemText(current_index)
        
        if type_id:
            edit_action = QAction("Edit Type", menu)
            edit_action.triggered.connect(lambda: self._edit_type(type_id, type_name))
            menu.addAction(edit_action)
            
            menu.addSeparator()
            
            delete_action = QAction("Delete Type", menu)
            delete_action.triggered.connect(lambda: self._delete_type(type_id, type_name))
            menu.addAction(delete_action)
            
            menu.exec(self.type_combo.mapToGlobal(position))
            
    def _edit_type(self, type_id: int, old_name: str):
        from .add_type_dialog import AddTypeDialog
        
        dialog = AddTypeDialog(self, existing_name=old_name)
        
        if dialog.exec() == QDialog.Accepted:
            new_name = dialog.get_type_name()
            
            if not new_name:
                return
            
            try:
                if self.db.update_study_type(type_id, new_name):
                    selected_type_id = type_id
                    
                    self._load_study_types()
                    
                    index = self.type_combo.findData(selected_type_id)
                    if index >= 0:
                        self.type_combo.setCurrentIndex(index)
                    
                    styled_message_box(
                        QMessageBox.Information,
                        "Success",
                        f"Study type renamed to '{new_name}'!",
                        parent=self
                    )
                else:
                    styled_message_box(
                        QMessageBox.Warning,
                        "Error",
                        "Failed to update study type. It may already exist.",
                        parent=self
                    )
            except Exception as e:
                styled_message_box(
                    QMessageBox.Critical,
                    "Error",
                    f"Failed to edit study type:\n{e}",
                    parent=self
                )  

    def _delete_type(self, type_id: int, type_name: str):
        try:
            studies_using_type = self.db.get_studies_by_type(type_id)
            
            if studies_using_type:
                styled_message_box(
                    QMessageBox.Warning,
                    "Cannot Delete",
                    f"Study type '{type_name}' is used by {len(studies_using_type)} study/studies.\n\n"
                    "Please reassign those studies to a different type before deleting.",
                    parent=self
                )
                return
            
            dlg = styled_message_box(
                QMessageBox.Question,
                "Delete Study Type",
                f"Delete study type '{type_name}'?\n\n"
                "⚠️ This action cannot be undone.",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No,
                parent=self
            )
            reply = dlg.standardButton(dlg.clickedButton()) if dlg else QMessageBox.No
            
            if reply == QMessageBox.Yes:
                if self.db.delete_study_type(type_id):
                    self._load_study_types()
                    
                    if self.type_combo.count() > 0:
                        self.type_combo.setCurrentIndex(0)
                    
                    styled_message_box(
                        QMessageBox.Information,
                        "Success",
                        f"Study type '{type_name}' deleted.",
                        parent=self
                    )
                else:
                    styled_message_box(
                        QMessageBox.Warning,
                        "Error",
                        "Failed to delete study type.",
                        parent=self
                    )
        except Exception as e:
            styled_message_box(
                QMessageBox.Critical,
                "Error",
                f"An error occurred:\n{e}",
                parent=self
            )

    def _save_study(self):
        base_name = self.name_edit.text().strip()
        if not base_name:
            styled_message_box(QMessageBox.Warning, "Validation Error", "Study name cannot be empty!", parent=self)
            return

        type_id = self.type_combo.currentData()
        if not type_id:
            styled_message_box(QMessageBox.Warning, "Validation Error", "Please select a valid study type!", parent=self)
            return

        selected_participants = []
        for item in self.participant_list.selectedItems():
            participant_id = item.data(Qt.UserRole)
            selected_participants.append(participant_id)

        identifiers = []
        for participant_id in selected_participants:
            participant = self.db.get_participant(participant_id)
            if participant:
                identifiers.append(participant.code)

        if identifiers:
            full_study_name = f"{base_name} [{', '.join(identifiers)}]"
        else:
            full_study_name = base_name

        try:
            study = self.db.get_study(self.study_id)
            if not study:
                styled_message_box(QMessageBox.Critical, "Error", "Study not found!", parent=self)
                return

            if getattr(self, "_new_folder_path", None):
                new_folder_path = Path(self._new_folder_path)
                old_path = Path(study.path) if study.path else None

                study.path = str(new_folder_path.resolve())

                current_folder_name = new_folder_path.name
                final_new_root = new_folder_path

                if current_folder_name != full_study_name:
                    styled_message_box(
                        QMessageBox.Information,
                        "Folder Rename",
                        f"The folder will be renamed to match the study name:\n\n"
                        f"From: {current_folder_name}\n"
                        f"To: {full_study_name}",
                        parent=self
                    )
                    
                    try:
                        renamed_folder_path = new_folder_path.parent / full_study_name
                        if renamed_folder_path.exists():
                            styled_message_box(QMessageBox.Critical, "Error", f"Target folder already exists:\n{renamed_folder_path}", parent=self)
                            return
                        new_folder_path.rename(renamed_folder_path)
                        study.path = str(renamed_folder_path.resolve())
                        final_new_root = renamed_folder_path
                    except Exception as e:
                        styled_message_box(QMessageBox.Critical, "Folder Rename Error", f"Failed to rename new folder:\n{e}\n\nStudy will be saved with original folder name.", parent=self)
                        final_new_root = new_folder_path

                try:
                    self.db.update_study(study)
                except Exception:
                    pass

                try:
                    self._start_update_paths_worker(old_path, final_new_root, require_exists=True, label="Updating file paths after folder change...")
                except Exception as e:
                    pass

            if not getattr(self, "_new_folder_path", None):
                old_path = Path(study.path) if study.path else None
                if old_path and old_path.exists():
                    current_folder_name = old_path.name
                    new_folder_name = full_study_name
                    
                    if current_folder_name != new_folder_name:
                        styled_message_box(
                            QMessageBox.Information,
                            "Folder Rename",
                            f"The folder will be renamed to match the updated study name:\n\n"
                            f"From: {current_folder_name}\n"
                            f"To: {new_folder_name}",
                            parent=self
                        )
                        
                        try:
                            new_folder_path = old_path.parent / new_folder_name
                            if new_folder_path.exists():
                                styled_message_box(QMessageBox.Critical, "Error", f"Target folder already exists:\n{new_folder_path}", parent=self)
                                return
                            old_path.rename(new_folder_path)

                            study.path = str(new_folder_path)
                            try:
                                self.db.update_study(study)
                            except Exception:
                                pass

                            try:
                                self._start_update_paths_worker(old_path, new_folder_path, require_exists=False, label="Updating file paths after rename...")
                            except Exception as e:
                                pass
                        except Exception as e:
                            styled_message_box(QMessageBox.Critical, "Folder Rename Error", f"Failed to rename folder:\n{e}\n\nStudy name will be updated in database only.", parent=self)

            study.name = full_study_name
            study.type_id = type_id
            study.date = self.date_edit.date().toPython()

            self.db.update_study(study)

            current_participants = self.db.get_study_participants(self.study_id)
            current_ids = {p.id_participant for p in current_participants}
            new_ids = set(selected_participants)

            for pid in current_ids - new_ids:
                self.db.remove_participant_from_study(self.study_id, pid)
            for pid in new_ids - current_ids:
                self.db.add_participant_to_study(self.study_id, pid)

            success_msg = f"Study '{full_study_name}' updated successfully!\nParticipants: {len(selected_participants)}"
            if getattr(self, "_new_folder_path", None):
                success_msg += f"\n\nFolder path updated to:\n{Path(study.path).name}"
            styled_message_box(QMessageBox.Information, "Success", success_msg, parent=self)

            self.studyUpdated.emit(self.study_id)
            self.accept()

        except Exception as e:
            styled_message_box(QMessageBox.Critical, "Error", f"Failed to update study:\n{e}", parent=self)

