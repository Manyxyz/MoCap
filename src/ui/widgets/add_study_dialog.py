from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout, QLineEdit,
    QPushButton, QLabel, QListWidget, QListWidgetItem, QFileDialog,
    QComboBox, QDateEdit, QMessageBox, QCheckBox, QMenu, QCompleter
)
from PySide6.QtCore import Qt, QDate, Signal, QThread, QStringListModel
from PySide6.QtGui import QAction
from pathlib import Path
from datetime import date

from ...database.db_manager import DatabaseManager
from ...database.models import Study, Participant
from .add_participant_dialog import AddParticipantDialog 
from .add_type_dialog import AddTypeDialog
from ..message_box import styled_message_box

class FileScanWorker(QThread):
    finished = Signal(int)
    progress = Signal(str)
    error = Signal(str)
    
    def __init__(self, db, study_id):
        super().__init__()
        self.db = db
        self.study_id = study_id
    
    def run(self):
        try:
            from pathlib import Path
            
            study = self.db.get_study(self.study_id)
            if not study or not study.path:
                self.finished.emit(0)
                return
            
            study_path = Path(study.path)
            if not study_path.exists():
                self.finished.emit(0)
                return
            
            self.progress.emit("Finding C3D files...")
            c3d_files = list(study_path.rglob("*.c3d"))
            
            if not c3d_files:
                self.finished.emit(0)
                return
            
            self.progress.emit(f"Found {len(c3d_files)} C3D files, checking database...")
            
            conn = self.db._get_connection()
            try:
                from ...config import MYSQL_CONFIG
                
                conn.database = MYSQL_CONFIG['database']
                cursor = conn.cursor(dictionary=True)
                
                cursor.execute(
                    "SELECT file_path FROM File WHERE Study_id_study = %s",
                    (self.study_id,)
                )
                existing_paths = {row['file_path'] for row in cursor.fetchall()}
                
                new_files = []
                for c3d_file in c3d_files:
                    file_path_str = str(c3d_file)
                    if file_path_str not in existing_paths:
                        new_files.append((c3d_file.name, file_path_str, self.study_id))
                
                if not new_files:
                    cursor.close()
                    conn.close()
                    self.finished.emit(0)
                    return
                
                self.progress.emit(f"Indexing {len(new_files)} new files...")
                cursor.executemany(
                    "INSERT INTO File (name, file_path, Study_id_study) VALUES (%s, %s, %s)",
                    new_files
                )
                
                conn.commit()
                files_added = len(new_files)
                
                cursor.close()
                conn.close()
                
                self.finished.emit(files_added)
                
            except Exception as e:
                if conn:
                    try:
                        conn.rollback()
                    except Exception:
                        pass
                raise
                
        except Exception as e:
            self.error.emit(str(e))

class AddStudyDialog(QDialog):
    
    studyAdded = Signal(int)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Add Study")
        self.setMinimumWidth(500)
        self.db = DatabaseManager()
        self._setup_ui()
        self._load_participants()
        self._load_study_types()
    
    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(16)
        
        title = QLabel("Add New Study")
        title.setStyleSheet("font-size: 18px; font-weight: bold; color: #ffffff;")
        layout.addWidget(title)
        
        form = QFormLayout()
        form.setSpacing(12)
        self.setStyleSheet("background: #545c64;")
        
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
                color: #fff;
                border-radius: 4px;
                border: 1px solid #ccc;
                padding: 4px 6px;
            }
            QLineEdit::placeholder {
                color: #888;
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
                outline: none;
                border: 1px solid #ccc;
                border-radius: 4px;
                padding: 4px;
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

        self.participant_list.itemSelectionChanged.connect(self._update_identifiers)
        participant_layout.addWidget(self.participant_list)
        
        form.addRow(participant_layout)
        
        identifier_label = QLabel("Study Identifiers:")
        identifier_label.setStyleSheet("font-weight: bold; color: #ffffff;")
        
        self.identifiers_display = QLabel("(select participants to generate)")
        self.identifiers_display.setStyleSheet("""
            color: #929292;
            font-style: italic;
            padding: 8px;
            border: 1px dashed #ccc;
            border-radius: 4px;
            background: #f9f9f9;
        """)
        self.identifiers_display.setWordWrap(True)
        self.identifiers_display.setFixedHeight(35)
        
        form.addRow(identifier_label, self.identifiers_display)
        
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
        
        folder_label = QLabel("Study Folder:")
        folder_label.setStyleSheet("font-weight: bold; color: #ffffff;")
        
        folder_layout = QHBoxLayout()
        
        self.folder_path_edit = QLineEdit()
        self.folder_path_edit.setPlaceholderText("Select study folder...")
        self.folder_path_edit.setReadOnly(True)
        self.folder_path_edit.setStyleSheet("""
            QLineEdit {
                border: 1px solid #ccc;
                border-radius: 4px;
                padding: 6px;
                background: #f5f5f5;
                color: #000000;

            }
        """)
        
        self.browse_btn = QPushButton("Browse...")
        self.browse_btn.clicked.connect(self._browse_folder)
        self.browse_btn.setStyleSheet("""
            QPushButton {
                background: #6c757d;
                color: white;
                border-radius: 4px;
                padding: 6px 12px;
            }
            QPushButton:hover { background: #5a6268; }
        """)
        
        folder_layout.addWidget(self.folder_path_edit, 1)
        folder_layout.addWidget(self.browse_btn)
        
        form.addRow(folder_label, folder_layout)
        
        name_label = QLabel("Study Name:")
        name_label.setStyleSheet("font-weight: bold; color: #ffffff;")
        
        self.name_display = QLabel("(will be auto-generated from folder)")
        self.name_display.setStyleSheet("""
            background: #ffffff;
            color: #666;
            font-style: italic;
            padding: 6px;
            border: 1px dashed #ccc;
            border-radius: 4px;
        """)
        
        form.addRow(name_label, self.name_display)
        self.name_display.setFixedHeight(35)
        
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
        
        self.save_btn = QPushButton("Save Study")
        self.save_btn.setStyleSheet("""
            QPushButton {
                background: #28a745;
                color: white;
                border-radius: 4px;
                padding: 8px 16px;
                font-weight: bold;
            }
            QPushButton:hover { background: #218838; }
            QPushButton:disabled {
                background: #ccc;
                color: #666;
            }
        """)
        self.save_btn.setEnabled(False)
        self.save_btn.clicked.connect(self._save_study)
        
        button_layout.addStretch()
        button_layout.addWidget(self.cancel_btn)
        button_layout.addWidget(self.save_btn)
        
        layout.addLayout(button_layout)
    
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

    def _add_custom_type(self):
        dialog = AddTypeDialog(self)
        if dialog.exec() == QDialog.Accepted:
            type_name = dialog.get_type_name()
            if not type_name:
                return
            try:
                if self.db.add_study_type(type_name):
                    self._load_study_types()
                    idx = self.type_combo.findText(type_name)
                    if idx >= 0:
                        self.type_combo.setCurrentIndex(idx)
                    from PySide6.QtWidgets import QMessageBox
                    styled_message_box(QMessageBox.Information, "Success", f"Study type '{type_name}' added.", parent=self)
                else:
                    from PySide6.QtWidgets import QMessageBox
                    styled_message_box(QMessageBox.Warning, "Warning", f"Type '{type_name}' may already exist.", parent=self)
            except Exception as e:
                from PySide6.QtWidgets import QMessageBox
                styled_message_box(QMessageBox.Critical, "Error", f"Failed to add study type:\n{e}", parent=self)
                
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

    def _edit_participant(self, participant_id: int):
        try:
            participant = self.db.get_participant(participant_id)
            if not participant:
                return
                
            dialog = AddParticipantDialog(self, participant)
            if dialog.exec():
                updated_participant = dialog.get_participant()
                updated_participant.id_participant = participant_id
                
                if self.db.update_participant(updated_participant):
                    self._load_participants() 
                    styled_message_box(QMessageBox.Information, "Success", f"Participant '{updated_participant.full_name}' updated!", parent=self)
                else:
                    styled_message_box(QMessageBox.Warning, "Error", "Failed to update participant.", parent=self)
        except Exception as e:
            styled_message_box(QMessageBox.Critical, "Error", f"Failed to edit participant:\n{e}", parent=self)
    def _delete_participant(self, participant_id: int):
        try:
            participant = self.db.get_participant(participant_id)
            if not participant:
                return
            studies_using = self.db.get_participant_studies(participant_id)
            if studies_using:
                styled_message_box(QMessageBox.Warning, "Cannot Delete", f"Participant '{participant.full_name}' ({participant.code}) is used by {len(studies_using)} study/studies.\n\nPlease reassign or remove the participant from those studies before deleting.", parent=self)
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

                    self._update_identifiers()

                    styled_message_box(QMessageBox.Information, "Success", f"Participant '{participant.full_name}' deleted.", parent=self)
                else:
                    styled_message_box(QMessageBox.Warning, "Error", "Failed to delete participant.", parent=self)
        except Exception as e:
            styled_message_box(QMessageBox.Critical, "Error", f"An error occurred:\n{e}", parent=self)
    
    def _browse_folder(self):
        folder = QFileDialog.getExistingDirectory(
            self,
            "Select Study Folder",
            str(Path.home())
        )
        
        if folder:
            self.folder_path_edit.setText(folder)
            
            folder_name = Path(folder).name
            
            selected_items = self.participant_list.selectedItems()
            identifiers = []
            for item in selected_items:
                participant_id = item.data(Qt.UserRole)
                participant = self.db.get_participant(participant_id)
                if participant:
                    identifiers.append(participant.code)
            
            if identifiers:
                display_name = f"{folder_name} [{', '.join(identifiers)}]"
            else:
                display_name = folder_name
            
            self.name_display.setText(display_name)
            self.name_display.setStyleSheet("""
                color: #222;
                font-weight: bold;
                padding: 6px;
                border: 1px solid #3aa0ff;
                border-radius: 4px;
                background: #e8f4ff;
            """)
            
            self.save_btn.setEnabled(True)
    
    def _save_study(self):
        if not self.folder_path_edit.text():
            styled_message_box(QMessageBox.Warning, "Validation Error", "Please select a study folder!", parent=self)
            return
        
        type_id = self.type_combo.currentData() 
        if not type_id:
            styled_message_box(QMessageBox.Warning, "Validation Error", "Please select a valid study type!", parent=self)
            return
        
        selected_participants = []
        for item in self.participant_list.selectedItems():
            participant_id = item.data(Qt.UserRole)
            selected_participants.append(participant_id)
        
        if not selected_participants:
            dlg = styled_message_box(
                QMessageBox.Question,
                "No Participants",
                "No participants selected. Continue anyway?",
                QMessageBox.Yes | QMessageBox.No,
                parent=self
            )
            reply = dlg.standardButton(dlg.clickedButton()) if dlg else QMessageBox.No
            if reply == QMessageBox.No:  
                return 
        
        folder_path = self.folder_path_edit.text()
        folder_name = Path(folder_path).name
        
        identifiers = []
        for participant_id in selected_participants:
            participant = self.db.get_participant(participant_id)
            if participant:
                identifiers.append(participant.code)
        
        if identifiers:
            study_name = f"{folder_name} [{', '.join(identifiers)}]"
        else:
            study_name = folder_name
        
        if folder_name != study_name:
            new_folder_path = Path(folder_path).parent / study_name
            try:
                Path(folder_path).rename(new_folder_path)
                folder_path = str(new_folder_path)
            except Exception as e:
                styled_message_box(QMessageBox.Warning, "Warning", f"Could not rename folder:\n{e}\n\nStudy will be saved with original folder name.", parent=self)
        
        study = Study(
            name=study_name,
            type_id=type_id,  
            date=self.date_edit.date().toPython(),
            path=folder_path
        )
        
        try:
            study_id = self.db.add_study(study)
            
            if selected_participants:
                success = self.db.add_participants_to_study_batch(study_id, selected_participants)
                
                if not success:
                    raise Exception("Failed to add participants to study!")
                
            
            from PySide6.QtWidgets import QProgressDialog
            
            progress = QProgressDialog("Indexing C3D files...", None, 0, 0, self)
            progress.setWindowModality(Qt.NonModal)  
            progress.setWindowTitle("Background Indexing")
            progress.setMinimumDuration(0)
            progress.setCancelButton(None)
            progress.show()
            
            self._scan_worker = FileScanWorker(self.db, study_id)
            
            def on_scan_progress(message):
                progress.setLabelText(message)
            
            def on_scan_error(error_msg):
                progress.close()
            
            self._scan_worker.progress.connect(on_scan_progress)
            self._scan_worker.error.connect(on_scan_error)
            
            self._scan_worker.start()
            
            styled_message_box(
                QMessageBox.Information,
                "Success",
                f"Study '{study_name}' created successfully!\n"
                f"Participants: {len(selected_participants)}\n\n"
                f"📂 C3D files are being indexed in the background...",
                parent=self
            )
            
            self._last_study_id = study_id
            self.studyAdded.emit(study_id)
            self.accept()
            
        except Exception as e:
            import traceback
            traceback.print_exc()
            styled_message_box(QMessageBox.Critical, "Error", f"Failed to save study:\n{e}", parent=self)


    def _update_identifiers(self):
        selected_items = self.participant_list.selectedItems()
        
        if not selected_items:
            self.identifiers_display.setText("(select participants to generate)")
            self.identifiers_display.setStyleSheet("""
                color: #666;
                font-style: italic;
                padding: 8px;
                border: 1px dashed #ccc;
                border-radius: 4px;
                background: #f9f9f9;
            """)
            if self.folder_path_edit.text():
                folder_name = Path(self.folder_path_edit.text()).name
                self.name_display.setText(folder_name)
            return
        
        identifiers = []
        for item in selected_items:
            participant_id = item.data(Qt.UserRole)
            participant = self.db.get_participant(participant_id)
            
            if participant:
                identifiers.append(participant.code)
        
        if identifiers:
            identifier_text = ", ".join(identifiers)
            self.identifiers_display.setText(identifier_text)
            self.identifiers_display.setStyleSheet("""
                color: #222;
                font-weight: bold;
                padding: 8px;
                border: 1px solid #3aa0ff;
                border-radius: 4px;
                background: #e8f4ff;
            """)
            
            if self.folder_path_edit.text():
                folder_name = Path(self.folder_path_edit.text()).name
                display_name = f"{folder_name} [{', '.join(identifiers)}]"
                self.name_display.setText(display_name)
                self.name_display.setStyleSheet("""
                    color: #222;
                    font-weight: bold;
                    padding: 6px;
                    border: 1px solid #3aa0ff;
                    border-radius: 4px;
                    background: #e8f4ff;
                """)
        else:
            self.identifiers_display.setText("(no valid codes)")
            self.identifiers_display.setStyleSheet("""
                color: #dc3545;
                padding: 8px;
                border: 1px solid #dc3545;
                border-radius: 4px;
                background: #f8d7da;
            """)
            
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
                    
                    styled_message_box(QMessageBox.Information, "Success", f"Study type renamed to '{new_name}'!", parent=self)
                else:
                    styled_message_box(QMessageBox.Warning, "Error", "Failed to update study type. It may already exist.", parent=self)
            except Exception as e:
                styled_message_box(QMessageBox.Critical, "Error", f"Failed to edit study type:\n{e}", parent=self)
    def _delete_type(self, type_id: int, type_name: str):
        try:
            studies_using_type = self.db.get_studies_by_type(type_id)
            
            if studies_using_type:
                styled_message_box(QMessageBox.Warning, "Cannot Delete", f"Study type '{type_name}' is used by {len(studies_using_type)} study/studies.\n\nPlease reassign those studies to a different type before deleting.", parent=self)
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
                    
                    styled_message_box(QMessageBox.Information, "Success", f"Study type '{type_name}' deleted.", parent=self)
                else:
                    styled_message_box(QMessageBox.Warning, "Error", "Failed to delete study type.", parent=self)
        except Exception as e:
            styled_message_box(QMessageBox.Critical, "Error", f"An error occurred:\n{e}", parent=self)
    
    def get_study_id(self):
        return getattr(self, '_last_study_id', None)