from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, 
    QLineEdit, QPushButton, QFormLayout, QGroupBox
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QDoubleValidator, QIntValidator


class SettingsDialog(QDialog):
    
    settingsChanged = Signal(dict)
    
    def __init__(self, current_settings: dict, parent=None):
        """
        Args:
            current_settings: Dict with keys:
                - frame_rate: float
                - camera_distance: float
                - grid_size: float
                - grid_spacing: float
        """
        super().__init__(parent)
        self.setWindowTitle("Visualization Settings")
        self.setModal(True)
        self.setMinimumWidth(400)
        
        self.current_settings = current_settings.copy()
        
        self._setup_ui()
        self._load_current_values()
    
    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(16)
        
        title = QLabel("Visualization Settings")
        title.setStyleSheet("""
            font-size: 18px;
            font-weight: bold;
            color: #222;
            margin-bottom: 8px;
        """)
        layout.addWidget(title)
        
        settings_group = QGroupBox("Display Parameters")
        settings_group.setStyleSheet("""
            QGroupBox {
                font-weight: bold;
                border: 2px solid #ddd;
                border-radius: 8px;
                margin-top: 12px;
                padding-top: 16px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px;
            }
        """)
        
        form_layout = QFormLayout(settings_group)
        form_layout.setSpacing(12)
        form_layout.setContentsMargins(16, 20, 16, 16)
        
        self.frame_rate_edit = QLineEdit()
        self.frame_rate_edit.setValidator(QDoubleValidator(0.1, 10000.0, 2))
        self.frame_rate_edit.setPlaceholderText("e.g. 100.0")
        self.frame_rate_edit.setStyleSheet(self._input_style())
        form_layout.addRow("Frame Rate (Hz):", self.frame_rate_edit)
        
        self.camera_distance_edit = QLineEdit()
        self.camera_distance_edit.setValidator(QDoubleValidator(100.0, 50000.0, 1))
        self.camera_distance_edit.setPlaceholderText("e.g. 5000")
        self.camera_distance_edit.setStyleSheet(self._input_style())
        form_layout.addRow("Camera Distance:", self.camera_distance_edit)
        
        self.grid_size_edit = QLineEdit()
        self.grid_size_edit.setValidator(QDoubleValidator(100.0, 50000.0, 1))
        self.grid_size_edit.setPlaceholderText("e.g. 5000")
        self.grid_size_edit.setStyleSheet(self._input_style())
        form_layout.addRow("Grid Size:", self.grid_size_edit)
        
        self.grid_spacing_edit = QLineEdit()
        self.grid_spacing_edit.setValidator(QDoubleValidator(10.0, 5000.0, 1))
        self.grid_spacing_edit.setPlaceholderText("e.g. 400")
        self.grid_spacing_edit.setStyleSheet(self._input_style())
        form_layout.addRow("Grid Spacing:", self.grid_spacing_edit)
        
        
        
        layout.addWidget(settings_group)
        
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(10)
        
        reset_btn = QPushButton("Reset to Defaults")
        reset_btn.setStyleSheet("""
            QPushButton {
                background: #6c757d;
                color: white;
                border-radius: 6px;
                padding: 8px 16px;
                font-size: 13px;
            }
            QPushButton:hover { background: #5a6268; }
        """)
        reset_btn.clicked.connect(self._reset_to_defaults)
        
        cancel_btn = QPushButton("Cancel")
        cancel_btn.setStyleSheet("""
            QPushButton {
                background: #dc3545;
                color: white;
                border-radius: 6px;
                padding: 8px 16px;
                font-size: 13px;
            }
            QPushButton:hover { background: #c82333; }
        """)
        cancel_btn.clicked.connect(self.reject)
        
        apply_btn = QPushButton("Apply")
        apply_btn.setStyleSheet("""
            QPushButton {
                background: #28a745;
                color: white;
                border-radius: 6px;
                padding: 8px 16px;
                font-size: 13px;
                font-weight: bold;
            }
            QPushButton:hover { background: #218838; }
        """)
        apply_btn.clicked.connect(self._apply_settings)
        
        btn_layout.addWidget(reset_btn)
        btn_layout.addStretch()
        btn_layout.addWidget(cancel_btn)
        btn_layout.addWidget(apply_btn)
        
        layout.addLayout(btn_layout)
    
    def _input_style(self):
        return """
            QLineEdit {
                border: 2px solid #ddd;
                border-radius: 6px;
                padding: 6px 10px;
                font-size: 13px;
                background: white;
                color: #000000;
            }
            QLineEdit:focus {
                border: 2px solid #3aa0ff;
            }
        """
    
    def _load_current_values(self):
        self.frame_rate_edit.setText(str(self.current_settings.get('frame_rate', 100.0)))
        self.camera_distance_edit.setText(str(self.current_settings.get('camera_distance', 5000)))
        self.grid_size_edit.setText(str(self.current_settings.get('grid_size', 5000)))
        self.grid_spacing_edit.setText(str(self.current_settings.get('grid_spacing', 400)))
    
    def _reset_to_defaults(self):
        from ...config import (
            DEFAULT_FRAME_RATE, DEFAULT_CAMERA_DISTANCE, 
            GRID_SIZE, GRID_SPACING
        )
        self.frame_rate_edit.setText(str(DEFAULT_FRAME_RATE))
        self.camera_distance_edit.setText(str(DEFAULT_CAMERA_DISTANCE))
        self.grid_size_edit.setText(str(GRID_SIZE))
        self.grid_spacing_edit.setText(str(GRID_SPACING))
        
        self._apply_settings()
    
    def _apply_settings(self):
        try:
            new_settings = {
                'frame_rate': float(self.frame_rate_edit.text() or 100.0),
                'camera_distance': float(self.camera_distance_edit.text() or 5000),
                'grid_size': float(self.grid_size_edit.text() or 5000),
                'grid_spacing': float(self.grid_spacing_edit.text() or 400),
            }
            
            self.settingsChanged.emit(new_settings)
            self.accept()
            
        except ValueError as e:
            from PySide6.QtWidgets import QMessageBox
            QMessageBox.warning(
                self, 
                "Invalid Input", 
                f"Please enter valid numeric values.\n\nError: {e}"
            )