from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QLabel, QLineEdit, 
    QPushButton, QHBoxLayout, QMessageBox
)
from PySide6.QtCore import Qt
from ..message_box import styled_message_box

class RenameMarkerDialog(QDialog):
    
    def __init__(self, current_name: str, existing_names: list, parent=None, main_window=None):
       
        super().__init__(parent)
        self.current_name = current_name
        self.existing_names = existing_names
        self.new_name = None
        self.main_window = main_window 
        
        self.setWindowTitle("Rename Marker")
        self.setMinimumWidth(300)
        
        self.setStyleSheet("""
            QDialog {
                background: #545c64;
            }
            QLabel {
                color: #ffffff;
                font-size: 13px;
            }
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
            QLineEdit:focus {
                border: 2px solid #3aa0ff;
            }
            QPushButton {
                border-radius: 6px;
                padding: 8px 20px;
                font-size: 13px;
                font-weight: bold;
            }
        """)
        
        self._setup_ui()
        

    def _get_dialog_parent(self):
        if self.main_window:
            return self.main_window
        
        current = self.parent()
        while current:
            if hasattr(current, '_main_window'):
                return current._main_window
            current = current.parent() if hasattr(current, 'parent') else None
        
        return None
    
    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        layout.setContentsMargins(20, 20, 20, 20)
        
        title = QLabel(f"Enter new name for marker:")
        title.setStyleSheet("font-weight: bold; font-size: 14px; background: #545c64;")
        layout.addWidget(title)
        
        current_label = QLabel(f"Current: {self.current_name}")
        current_label.setStyleSheet("color: #aaa; font-size: 12px; background: #545c64;")
        layout.addWidget(current_label)
        
        self.input_field = QLineEdit(self.current_name)
        self.input_field.selectAll()
        layout.addWidget(self.input_field)
        
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
        
        ok_btn = QPushButton("Rename")
        ok_btn.setStyleSheet("""
            QPushButton {
                background: #3aa0ff;
                color: white;
            }
            QPushButton:hover { background: #2a8fdf; }
        """)
        ok_btn.clicked.connect(self._on_rename)
        ok_btn.setDefault(True)
        button_layout.addWidget(ok_btn)
        
        layout.addLayout(button_layout)
        
        self.input_field.returnPressed.connect(self._on_rename)
    
    def _styled_message_box(self, icon, title: str, text: str, buttons=None, default=None):
        from PySide6.QtWidgets import QMessageBox, QPushButton
        dlg = QMessageBox(self)
        dlg.setWindowTitle(title)
        dlg.setIcon(icon)
        dlg.setText(text)
        if buttons is not None:
            dlg.setStandardButtons(buttons)
        if default is not None:
            dlg.setDefaultButton(default)
        dlg.setStyleSheet("""
            QMessageBox {
                background: #545c64;
                color: #000000;
            }
            QMessageBox QLabel { color: #ffffff; }
            QLabel#qt_msgboxex_icon_label { background: #545c64; }
            QPushButton { color: #ffffff; background: #545c64 }
        """)
        dlg.exec()
        return dlg
        
    
    def _on_rename(self):
        new_name = self.input_field.text().strip()
        
        if not new_name:
            styled_message_box(
                QMessageBox.Warning,
                "Validation Error",
                "Marker name cannot be empty.",
                parent=self._get_dialog_parent()
            )
            self.input_field.setFocus()
            return
        
        if new_name == self.current_name:
            styled_message_box(
                QMessageBox.Information,
                "No Change",
                "Marker name was not changed.",
                parent=self._get_dialog_parent()
            )
            self.reject()
            return
        
        if new_name in self.existing_names:
            styled_message_box(
                QMessageBox.Warning,
                "Duplicate Name",
                f"A marker with the name '{new_name}' already exists.",
                parent=self._get_dialog_parent()
            )
            self.input_field.setFocus()
            self.input_field.selectAll()
            return
        
        self.new_name = new_name
        self.accept()
    
    def get_new_name(self) -> str:
        return self.new_name