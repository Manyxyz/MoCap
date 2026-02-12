from PySide6.QtWidgets import QDialog, QVBoxLayout, QLabel, QLineEdit, QPushButton, QHBoxLayout, QMessageBox
from ..message_box import styled_message_box

class AddTypeDialog(QDialog):

    def __init__(self, parent=None, existing_name: str = None):
        super().__init__(parent)
        self.setWindowTitle("Add Study Type")
        self.setMinimumWidth(300)
        self.type_name = None
        self.existing_name = existing_name

        self.setStyleSheet("""
            QDialog { background: #5a6268; }
            QLabel { color: #222; font-size: 13px; }
            QLineEdit {
                border: 2px solid #ccc;
                border-radius: 6px;
                padding: 8px 12px;
                font-size: 13px;
                background: white;
                color: #222;
                selection-background-color: #3aa0ff;
                selection-color: white;
            }
            QLineEdit:focus { border: 2px solid #3aa0ff; }
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

        title_label_text = "Enter new name for study type:" if existing_name else "Enter new study type name:"
        title = QLabel(title_label_text)
        title.setStyleSheet("font-weight: bold; font-size: 14px; background: #5a6268; color: #fff;")
        layout.addWidget(title)

        self.input_field = QLineEdit()
        if existing_name:
            self.input_field.setText(existing_name)
            self.input_field.selectAll()
        else:
            self.input_field.setPlaceholderText("e.g., Dance, Sport")
        layout.addWidget(self.input_field)

        btn_row = QHBoxLayout()
        btn_row.addStretch()

        cancel_btn = QPushButton("Cancel")
        cancel_btn.setStyleSheet("QPushButton { background: #6c757d; color: white; } QPushButton:hover { background: #5a6268; }")
        cancel_btn.clicked.connect(self.reject)
        btn_row.addWidget(cancel_btn)

        ok_btn_text = "Update" if existing_name else "Add"
        ok_btn = QPushButton(ok_btn_text)
        ok_btn.setStyleSheet("QPushButton { background: #3aa0ff; color: white; } QPushButton:hover { background: #2a8fdf; }")
        ok_btn.clicked.connect(self._on_ok)
        ok_btn.setDefault(True)
        btn_row.addWidget(ok_btn)

        layout.addLayout(btn_row)
        self.input_field.returnPressed.connect(self._on_ok)

    def _on_ok(self):
        text = self.input_field.text().strip()
        if not text:
            styled_message_box(QMessageBox.Warning, "Validation Error", "Type name cannot be empty.", parent=None)
            return
        if self.existing_name and text == self.existing_name:
            styled_message_box(QMessageBox.Information, "No Change", "Type name was not changed.", parent=None)
            self.reject()
            return
        self.type_name = text
        self.accept()

    def get_type_name(self) -> str:
        return self.type_name