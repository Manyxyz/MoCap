from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QFormLayout, QLineEdit,
    QPushButton, QHBoxLayout, QLabel, QMessageBox, QMenu
)

from ...database.models import Participant
from ...database.db_manager import DatabaseManager
from ..message_box import styled_message_box
from PySide6.QtGui import QAction

class AddParticipantDialog(QDialog):
    
    def __init__(self, parent=None, participant = None):
        super().__init__(parent)
        self.setWindowTitle("Edit Participant" if participant else "Add Participant")
        self.setMinimumWidth(350)
        self.db = DatabaseManager()
        
        if participant:
            self.original_code = participant.code 
        else:
            self.original_code = None
        
        self._setup_ui()
        
        if participant:
            self.name_edit.setText(participant.name)
            self.surname_edit.setText(participant.surname)
            self.code_edit.setText(participant.code)

        self.name_edit.textChanged.connect(self._update_code)
        self.surname_edit.textChanged.connect(self._update_code)

    def _generate_code(self, name: str, surname: str) -> str:
        if not name or not surname:
            return ""
            
        code_base = f"{name[0]}{surname[0]}".upper()
        
        try:
            existing_codes = []
            participants = self.db.get_all_participants()
            for p in participants:
                if p.code.startswith(code_base):
                    existing_codes.append(p.code)
            
            counter = 1
            while f"{code_base}{counter:02d}" in existing_codes:
                counter += 1
                
            return f"{code_base}{counter:02d}"
            
        except Exception:
            return f"{code_base}01"

    def _update_code(self):
        name = self.name_edit.text().strip()
        surname = self.surname_edit.text().strip()

        if not self._is_valid_name_field(name) or not self._is_valid_name_field(surname):
            return

        current_code = self.code_edit.text().strip()
        if not current_code or (len(current_code) == 4 and current_code[:2].isalpha() and current_code[2:].isdigit()):
            generated_code = self._generate_code(name, surname)
            self.code_edit.setText(generated_code)
    
    def _is_valid_name_field(self, s: str) -> bool:
        import unicodedata
        if not s:
            return False
        for c in s:
            if c in (" ", "-", "'"):
                continue
            cat = unicodedata.category(c)
            if cat.startswith("L"):
                continue
            return False
        return True

    def accept(self) -> None:
        import re
        name = self.name_edit.text().strip()
        surname = self.surname_edit.text().strip()
        code = self.code_edit.text().strip()

        if not name:
            styled_message_box(QMessageBox.Warning, "Validation Error", "Name field is required!", parent=None)
            self.name_edit.setFocus()
            return

        if not surname:
            styled_message_box(QMessageBox.Warning, "Validation Error", "Surname field is required!", parent=None)
            self.surname_edit.setFocus()
            return

        if not code:
            styled_message_box(QMessageBox.Warning, "Validation Error", "Code field is required!", parent=None)
            self.code_edit.setFocus()
            return

        if not self._is_valid_name_field(name):
            styled_message_box(QMessageBox.Warning, "Validation Error",
                "Name contains invalid characters.", parent=None)
            self.name_edit.setFocus()
            return

        if not self._is_valid_name_field(surname):
            styled_message_box(QMessageBox.Warning, "Validation Error",
                "Surname contains invalid characters.", parent=None)
            self.surname_edit.setFocus()
            return

        if not re.match(r'^[A-Za-z]{2}\d{2}$', code):
            styled_message_box(QMessageBox.Warning, "Validation Error",
                "Code must be in format: AA01\n(2 letters followed by 2 digits)", parent=None)
            self.code_edit.setFocus()
            return

        try:
            participants = self.db.get_all_participants()
            if any(p.code == code for p in participants if code != self.original_code):
                styled_message_box(QMessageBox.Warning, "Validation Error",
                    f"Code '{code}' is already in use!\nPlease enter a different code.", parent=None)
                self.code_edit.setFocus()
                return
        except Exception as e:
            styled_message_box(QMessageBox.Critical, "Error", f"Database error:\n{e}", parent=None)
            return

        super().accept()
    
    def _setup_ui(self):
        self.setStyleSheet("""
            QDialog { background: #545c64; }
            QLabel { color: #ffffff; font-size: 13px; }
            QLineEdit {
                border: 2px solid #ccc;
                border-radius: 6px;
                padding: 8px 12px;
                font-size: 13px;
                background: #545c64;
                color: #ffffff;
                selection-background-color: #3aa0ff;
                selection-color: white;
            }
            QLineEdit:focus { border: 2px solid #3aa0ff; }
            QLineEdit::placeholder {
                color: #aaa;
                font-style: italic;
            }
            QPushButton {
                border-radius: 6px;
                padding: 8px 20px;
                font-size: 13px;
                font-weight: bold;
            }
        """)

        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        layout.setContentsMargins(20, 20, 20, 20)

        title_text = "Edit Participant" if self.original_code else "Add New Participant"
        title = QLabel(title_text)
        title.setStyleSheet("font-weight: bold; font-size: 14px; background: #545c64;")
        layout.addWidget(title)

        form = QFormLayout()
        form.setSpacing(10)

        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText("First name")
        form.addRow("Name*:", self.name_edit)

        self.surname_edit = QLineEdit()
        self.surname_edit.setPlaceholderText("Last name")
        form.addRow("Surname*:", self.surname_edit)

        self.code_edit = QLineEdit()
        self.code_edit.setPlaceholderText("e.g., AB01")
        self.code_edit.setMaxLength(4)
        form.addRow("Code*:", self.code_edit)
        
        QLabel.setStyleSheet(self.name_edit, "background: #5a6268;")
        QLabel.setStyleSheet(self.surname_edit, "background: #5a6268;")
        QLabel.setStyleSheet(self.code_edit, "background: #5a6268;")
        
        layout.addLayout(form)

        button_layout = QHBoxLayout()
        button_layout.addStretch()

        cancel_btn = QPushButton("Cancel")
        cancel_btn.setStyleSheet("""
            QPushButton {
                background: #6c757d;
                color: white;
            }
            QPushButton:hover { background: #5a6268; }
        """)
        cancel_btn.clicked.connect(self.reject)
        button_layout.addWidget(cancel_btn)

        save_btn = QPushButton("Save")
        save_btn.setStyleSheet("""
            QPushButton {
                background: #3aa0ff;
                color: white;
            }
            QPushButton:hover { background: #2a8fdf; }
        """)
        save_btn.clicked.connect(self.accept)
        save_btn.setDefault(True)
        button_layout.addWidget(save_btn)

        layout.addLayout(button_layout)
    
    def get_participant(self) -> Participant:
        return Participant(
            name=self.name_edit.text().strip(),
            surname=self.surname_edit.text().strip(),
            code=self.code_edit.text().strip()
        )