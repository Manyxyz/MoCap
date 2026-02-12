from typing import List, Optional, Dict  
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QListWidget, QListWidgetItem, QLabel, QLineEdit, QFrame, QSizePolicy, QSplitter, QApplication, QSlider, QCheckBox, QComboBox, QCompleter, QMessageBox
)
from PySide6.QtCore import Qt, QTimer, Signal, QSize, QStringListModel, QFileSystemWatcher, QObject, QTimer, QThread
from PySide6.QtGui import QIcon, QPainter, QColor, QPen, QBrush, QFont
from pathlib import Path
from ..visualization.viewer3d import Markers3DWidget
from ..config import ASSETS_DIR
from ..data_processing.marker_editor import MarkerEditor
from ..data_processing.recording_trimmer import RecordingTrimmer 
from datetime import datetime 
from ..config import DEFAULT_FRAME_RATE
from .widgets.settings_dialog import *
from ..data_processing.config_manager import ConfigManager
from .message_box import styled_message_box
import os
import re
import traceback
import numpy as np
try:
    import pyqtgraph as pg
    import pyqtgraph.opengl as gl
except Exception:
    pg = None
    gl = None

try:
    from c3d import Reader
except Exception:
    Reader = None


try:
    import ezc3d
except Exception:
    ezc3d = None

class FileSyncWorker(QThread):
    
    progress = Signal(str, int) 
    finished = Signal(int, int)
    
    def __init__(self, study_ids: list, parent=None):
        super().__init__(parent)
        self.study_ids = study_ids
        self._stop_requested = False
    
    def stop(self):
        self._stop_requested = True
    
    def run(self):
        try:
            from ..database.db_manager import DatabaseManager
            from ..database.models import File
            
            db = DatabaseManager()
            total_added = 0
            total_removed = 0
            
            for study_id in self.study_ids:
                if self._stop_requested:
                    break
                
                try:
                    study = db.get_study(study_id)
                    if not study or not study.path:
                        continue
                                        
                    study_path = Path(study.path)
                    if not study_path.exists():
                        continue
                    

                    db_files = db.get_study_files(study_id) or []
                    db_paths = {
                        getattr(f, "file_path", ""): getattr(f, "id_file", None)
                        for f in db_files
                        if getattr(f, "file_path", "")
                    }
                    

                    disk_files = set()
                    for c3d in study_path.rglob("*.c3d"):
                        disk_files.add(str(c3d))
                    for c3d in study_path.rglob("*.C3D"):
                        disk_files.add(str(c3d))
                    

                    for db_path, file_id in db_paths.items():
                        if db_path and db_path not in disk_files and file_id:
                            try:
                                db.delete_file(int(file_id))
                                total_removed += 1
                            except Exception:
                                pass
                    

                    for disk_path in disk_files:
                        if disk_path not in db_paths:
                            try:
                                new_file = File(
                                    name=Path(disk_path).name,
                                    file_path=disk_path,
                                    study_id=study_id
                                )
                                db.add_file(new_file)
                                total_added += 1
                            except Exception:
                                pass
                
                except Exception:
                    continue
                    
        except Exception as e:
            pass

class TimelineWidget(QWidget):
    frameSelected = Signal(int)
    trimChanged = Signal(int, int)
    def __init__(self, parent=None):
        super().__init__(parent)
        self.frames = 0
        self.frame_rate = 100.0
        self.current = 0
        self.setMinimumHeight(80)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.valid_mask = None
        
        self.trim_start = 0
        self.trim_end = 0
        self.dragging_handle = None
        self.setMouseTracking(True)

    def set_frames_count(self, n):
        self.frames = int(n or 0)
        self.valid_mask = None
        self.trim_start = 0
        self.trim_end = max(0, self.frames - 1)
        self.update()

    def set_frame_rate(self, fr):
        self.frame_rate = float(fr or 1.0)
        self.update()

    def set_current(self, idx):
        if self.frames <= 0:
            self.current = 0
        else:
            self.current = int(max(self.trim_start, min(self.trim_end, idx)))
        self.update()

    def set_valid_mask(self, mask):
        try:
            self.valid_mask = np.asarray(mask, dtype=bool)
        except Exception:
            self.valid_mask = None
        self.update()
        
    def get_trim_range(self):
        return (self.trim_start, self.trim_end)

    def set_trim_range(self, start, end):
        self.trim_start = max(0, min(start, self.frames - 1))
        self.trim_end = max(0, min(end, self.frames - 1))
        if self.trim_start > self.trim_end:
            self.trim_start, self.trim_end = self.trim_end, self.trim_start
        self.update()
        self.trimChanged.emit(self.trim_start, self.trim_end)

    def paintEvent(self, ev):
        p = QPainter(self)
        w = self.width()
        h = self.height()

        p.fillRect(0, 0, w, h, QColor("#121416"))

        if self.frames <= 0:
            p.setPen(QPen(QColor("#555"), 1))
            p.drawText(self.rect(), Qt.AlignCenter, "No timeline")
            p.end()
            return

        track_h = 18
        track_y = (h - track_h) // 2
        margin = 20
        track_width = w - 2 * margin

        start_x = margin + int((self.trim_start / max(1, self.frames - 1)) * track_width)
        end_x   = margin + int((self.trim_end   / max(1, self.frames - 1)) * track_width)


        p.setPen(Qt.NoPen)
        base_grad = QBrush(QColor("#1e1f22"))
        p.setBrush(base_grad)
        p.drawRect(margin, track_y, track_width, track_h)


        p.setBrush(QColor(0,122,255,60))
        p.drawRect(start_x, track_y, end_x - start_x, track_h)


        if self.valid_mask is not None and len(self.valid_mask) == self.frames:
            p.setBrush(QColor(0,122,255,120))
            block_w = max(1.0, track_width / max(1, self.frames))
            i = 0
            while i < self.frames:
                if not self.valid_mask[i]:
                    i += 1
                    continue
                j = i + 1
                while j < self.frames and self.valid_mask[j]:
                    j += 1
                x_seg = start_x + int((i - self.trim_start) / max(1, (self.trim_end - self.trim_start)) * (end_x - start_x))
                right_seg = start_x + int((j - self.trim_start) / max(1, (self.trim_end - self.trim_start)) * (end_x - start_x))
                clip_x = max(start_x, x_seg)
                clip_r = min(end_x, right_seg)
                if clip_r > clip_x:
                    p.drawRect(clip_x, track_y, clip_r - clip_x, track_h)
                i = j


        p.setPen(QPen(QColor("#3d3f44"), 1))
        tick_count = 50 
        for i in range(tick_count + 1):
            fx = i / float(tick_count)
            x = margin + int(fx * track_width)
            major = (i % 5 == 0)
            p.drawLine(x, track_y - (10 if major else 6), x, track_y + track_h + (10 if major else 6))
            if major:
                frame_idx = int(fx * (self.frames - 1))
                p.setPen(QPen(QColor("#8c929b")))
                p.setFont(QFont("Arial", 7))
                p.drawText(x - 20, track_y - 16, 40, 12, Qt.AlignCenter, str(frame_idx))
                p.setPen(QPen(QColor("#3d3f44"), 1))


        handle_line_pen = QPen(QColor("#007aff"))
        handle_line_pen.setWidth(2)
        p.setPen(handle_line_pen)
        p.drawLine(start_x, track_y - 14, start_x, track_y + track_h + 14)
        p.drawLine(end_x, track_y - 14, end_x, track_y + track_h + 14)

        p.setBrush(QColor("#007aff"))
        p.setPen(QPen(QColor("#0d0f11"), 2))
        p.drawEllipse(start_x - 5, track_y - 20, 10, 10)
        p.drawEllipse(end_x - 5, track_y - 20, 10, 10)


        pos_x = margin + int((self.current / float(max(1, self.frames - 1))) * track_width)
        pos_x = max(start_x, min(end_x, pos_x))

        p.setBrush(QColor("#00e0e0"))
        p.setPen(QPen(QColor("#081818"), 2))
        p.drawEllipse(pos_x - 7, track_y + track_h + 2, 14, 14)
        p.setPen(QPen(QColor("#00e0e0"), 2))
        p.drawLine(pos_x, track_y - 18, pos_x, track_y + track_h + 2)

        p.end()
    def mousePressEvent(self, ev):
        if self.frames <= 0:
            return
        
        x = ev.position().x() if hasattr(ev, "position") else ev.x()
        w = self.width()
        margin = 20
        track_width = w - 2 * margin
        
        start_x = margin + int((self.trim_start / max(1, self.frames - 1)) * track_width)
        end_x = margin + int((self.trim_end / max(1, self.frames - 1)) * track_width)
        
        handle_width = 8
        
        if abs(x - start_x) < handle_width * 2:
            self.dragging_handle = 'start'
        elif abs(x - end_x) < handle_width * 2:
            self.dragging_handle = 'end'
        else:
            self.dragging_handle = 'playhead'
            rel = (x - margin) / float(max(1.0, track_width))
            idx = int(rel * (self.frames - 1))
            
            idx = max(self.trim_start, min(self.trim_end, idx))
            self.current = idx
            self.frameSelected.emit(idx)
            self.update()
    
    def mouseMoveEvent(self, ev):
        if self.frames <= 0:
            return
        
        x = ev.position().x() if hasattr(ev, "position") else ev.x()
        w = self.width()
        margin = 20
        track_width = w - 2 * margin
        
        if self.dragging_handle == 'start':
            rel = (x - margin) / float(max(1.0, track_width))
            idx = int(rel * (self.frames - 1))
            idx = max(0, min(self.trim_end - 1, idx))
            
            if idx != self.trim_start:
                self.trim_start = idx
                
                if self.current < self.trim_start:
                    self.current = self.trim_start
                    self.frameSelected.emit(self.current)
                
                self.update()
                self.trimChanged.emit(self.trim_start, self.trim_end)
        
        elif self.dragging_handle == 'end':
            rel = (x - margin) / float(max(1.0, track_width))
            idx = int(rel * (self.frames - 1))
            idx = max(self.trim_start + 1, min(self.frames - 1, idx))
            
            if idx != self.trim_end:
                self.trim_end = idx
                
                if self.current > self.trim_end:
                    self.current = self.trim_end
                    self.frameSelected.emit(self.current)
                
                self.update()
                self.trimChanged.emit(self.trim_start, self.trim_end)
        
        elif self.dragging_handle == 'playhead':
            rel = (x - margin) / float(max(1.0, track_width))
            idx = int(rel * (self.frames - 1))
            idx = max(self.trim_start, min(self.frames - 1, idx))
            
            if idx != self.current:
                self.current = idx
                self.frameSelected.emit(idx)
                self.update()
        
        else:
            start_x = margin + int((self.trim_start / max(1, self.frames - 1)) * track_width)
            end_x = margin + int((self.trim_end / max(1, self.frames - 1)) * track_width)
            handle_width = 8
            
            if abs(x - start_x) < handle_width * 2 or abs(x - end_x) < handle_width * 2:
                self.setCursor(Qt.SizeHorCursor)
            else:
                self.setCursor(Qt.ArrowCursor)

    def mouseReleaseEvent(self, ev):
        self.dragging_handle = None

    def wheelEvent(self, ev):
        delta = ev.angleDelta().y()
        if delta > 0:
            new_current = max(self.trim_start, self.current - 1)
        else:
            new_current = min(self.trim_end, self.current + 1)
        
        if new_current != self.current:
            self.current = new_current
            self.frameSelected.emit(self.current)
            self.update()

    
class MainWindowUI:
    def __init__(self):
        self.current_file_path = None
        self.original_file_path = None
        self.is_modified = False
        self.recording_trimmer = None
        
        self.config_manager = ConfigManager()
        self.frame_rate = DEFAULT_FRAME_RATE

        self._undo_stack = [] 
        self._redo_stack = []
        
    def setup_ui(self, main_window):
        menu = main_window.menuBar()
        menu.setStyleSheet("font-size: 13px;")
        file_menu = menu.addMenu("File")
        
        open_action = file_menu.addAction("Open...")
        open_action.setShortcut("Ctrl+O")
        open_action.triggered.connect(self._open_file)

        search_file_action = file_menu.addAction("Search File...")
        search_file_action.setShortcut("Ctrl+F")
        search_file_action.triggered.connect(self._open_search_file)
        
        file_menu.addSeparator()
        
        self.save_action = file_menu.addAction("Save")
        self.save_action.setShortcut("Ctrl+S")
        self.save_action.setEnabled(False)
        self.save_action.triggered.connect(self._save_file)
        
        self.save_as_action = file_menu.addAction("Save As...")
        self.save_as_action.setShortcut("Ctrl+Shift+S")
        self.save_as_action.setEnabled(False)
        self.save_as_action.triggered.connect(self._save_as_file)
        
        file_menu.addSeparator()
        self.save_to_modified_action = file_menu.addAction("Save to Modified Folder")
        self.save_to_modified_action.setShortcut("Ctrl+M")
        self.save_to_modified_action.setEnabled(False)
        self.save_to_modified_action.triggered.connect(self._save_to_modified)  
        
        file_menu.addSeparator()

        
        exit_action = file_menu.addAction("Exit")
        exit_action.setShortcut("Ctrl+Q")
        exit_action.triggered.connect(main_window.close)
        
        edit_menu = menu.addMenu("Edit")
        
        undo_action = edit_menu.addAction("Undo")
        undo_action.setShortcut("Ctrl+Z")
        undo_action.triggered.connect(self._undo_action)
        
        redo_action = edit_menu.addAction("Redo")
        redo_action.setShortcut("Ctrl+Y")
        redo_action.triggered.connect(self._redo_action)
        
        view_menu = menu.addMenu("View")
        self.toggle_studies_action = view_menu.addAction("Show Studies Panel")
        self.toggle_studies_action.setCheckable(True)
        self.toggle_studies_action.setChecked(True)
        self.toggle_studies_action.setShortcut("Ctrl+1")
        self.toggle_studies_action.triggered.connect(self._toggle_studies_panel)
        
        self.toggle_markers_action = view_menu.addAction("Show Marker Editor")
        self.toggle_markers_action.setCheckable(True)
        self.toggle_markers_action.setChecked(False)
        self.toggle_markers_action.setShortcut("Ctrl+2")
        self.toggle_markers_action.triggered.connect(self._toggle_markers_panel)
        
        menu.setStyleSheet("""
            QMenuBar {
                background: #545c64;
                color: #fff;
            }
            QMenuBar::item {
                background: transparent;
                padding: 4px 8px;
            }
            QMenuBar::item:selected {
                background: #696e7e;
            }
            QMenu {
                background: #fff;
                color: #222;
                border: 1px solid #ccc;
            }
            QMenu::item {
                padding: 6px 20px;
            }
            QMenu::item:selected {
                background: #35383c;
                color: white;
            }
            QMenu::separator {
                height: 1px;
                background: #ddd;
                margin: 2px 0px;
            }
        """)

        self._main_window = main_window

        

        self.recording_trimmer = RecordingTrimmer(parent_widget=self._main_window, main_window_ui=self)

        main_widget = QWidget()
        main_widget.setStyleSheet("background-color: #9098a0")
        main_window.setCentralWidget(main_widget)

        layout = QHBoxLayout(main_widget)
        layout.setContentsMargins(0, 0, 0, 0)

        left_outer_layout = QVBoxLayout()
        left_outer_layout.setContentsMargins(16, 16, 16, 16)
        left_outer_layout.setSpacing(0)

        left_frame = QFrame()
        left_frame.setStyleSheet("""
            QFrame {
                background: #fff;
                border: 1px solid #ccc;
                border-top-left-radius: 0px;
                border-bottom-left-radius: 0px;
                border-top-right-radius: 12px;
                border-bottom-right-radius: 12px;
            }
        """)
        left_frame.setMinimumWidth(300)
        left_frame.setMaximumWidth(840)
        left_frame.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Expanding)
        self._left_frame = left_frame

        left_panel = QVBoxLayout()
        left_panel.setContentsMargins(20, 20, 20, 20)
        left_panel.setSpacing(16)

        title_frame = QFrame()
        title_frame.setStyleSheet("""
            QFrame {
                background: #ffffff;
                border: none;
                border-radius: 22px;
                margin-bottom: 1px;
            }
        """)
        title_layout = QHBoxLayout(title_frame)
        title_layout.setContentsMargins(12, 8, 12, 8)
        title = QLabel("MotionCaptionary")
        title.setStyleSheet("""
            font-weight: bold;
            color: #222;
            font-size: 20px;
            background: transparent;
        """)
        title.setAlignment(Qt.AlignHCenter)
        title_layout.addWidget(title)
        left_panel.addWidget(title_frame)

        self.search = QLineEdit()
        self.search.setPlaceholderText("Search (by name / type / date YYYY-MM-DD)")
        self.search.setClearButtonEnabled(True)
        self.search.setStyleSheet("""
            QLineEdit {
                border: 2px solid #ccc;
                padding: 4px 10px;
                font-size: 14px;
                background: #fafbfc;
                color: #222;
            }
            QLineEdit:focus {
                border: 1.5px solid #888;
                background: #fff;
            }
        """)
        left_panel.addWidget(self.search)

        self._study_search_model = QStringListModel()
        self._study_search_map: Dict[str, int] = {}
        parent_obj = getattr(self, '_main_window', None)
        self._study_completer = QCompleter(self._study_search_model, parent_obj)
        self._study_completer.setCaseSensitivity(Qt.CaseInsensitive)
        self._study_completer.setFilterMode(Qt.MatchContains)
        self._study_completer.activated.connect(self._on_study_completer_activated)
        self.search.setCompleter(self._study_completer)
        self.search.returnPressed.connect(lambda: self._on_study_completer_activated(self.search.text()))

        try:
            popup = self._study_completer.popup()
            popup.setStyleSheet("""
                QListView {
                    background: #fff;
                    color: black;
                    border: 2px solid #5a6268;
                    padding: 1px;
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
                    background: #d0d0d0;
                    min-height: 30px;
                    border-radius: 6px;
                }
                QScrollBar::handle:vertical:hover {
                    background: #b0b0b0;
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

        try:
            self._refresh_search_items()
        except Exception:
            pass
        
        add_study_btn = QPushButton("Add Study")
        add_study_btn.setStyleSheet("""
            QPushButton {
                background: #28a745;
                color: white;
                border-radius: 8px;
                padding: 8px 16px;
                font-weight: bold;
            }
            QPushButton:hover { background: #218838; }
        """)
        add_study_btn.clicked.connect(self._add_study)
        left_panel.addWidget(add_study_btn)

        left_panel.addStretch()
        import_btn = QPushButton("Open file")
        import_btn.setStyleSheet("""
            QPushButton {
                background: #444;
                color: #fff;
                border-radius: 8px;
                padding: 6px 18px;
                font-size: 13px;
            }
            QPushButton:hover {
                background: #222;
            }
        """)
        left_panel.addWidget(import_btn, alignment=Qt.AlignBottom)

        left_frame.setLayout(left_panel)
        left_outer_layout.addWidget(left_frame, 1)

        preview_splitter = QSplitter(Qt.Vertical)

        preview_top = QWidget()
        preview_top.setMinimumHeight(450)
        preview_top_layout = QVBoxLayout(preview_top)
        preview_top_layout.setContentsMargins(0, 0, 0, 0)

        self.preview_label = QLabel()
        self.preview_label.setAlignment(Qt.AlignCenter)
        self.preview_label.setText("<img src='' width='200' height='200'><br><br>")
        self.preview_label.setStyleSheet("background: #ddd; border: 1px solid #bbb; min-height: 350px;")
        preview_top_layout.addWidget(self.preview_label)
        preview_top.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        preview_bottom = QWidget()
        preview_bottom_layout = QVBoxLayout(preview_bottom)
        preview_bottom_layout.setContentsMargins(0, 0, 0, 8)
        preview_bottom_layout.setAlignment(Qt.AlignTop)
        

        controls_wrapper = QVBoxLayout()
        controls_wrapper.setSpacing(6)

        top_controls = QHBoxLayout()
        top_controls.setSpacing(4)
        top_controls.setContentsMargins(0, 0, 0, 0)

        def _set_btn_icon(btn: QPushButton, icon_name: str, fallback_text: str = ""):
            try:
                p = ASSETS_DIR / "icons" / icon_name
                if p.exists():
                    btn.setIcon(QIcon(str(p)))
                    btn.setIconSize(QSize(20, 20))
                    if fallback_text:
                        btn.setText("")
                else:
                    if fallback_text:
                        btn.setText(fallback_text)
            except Exception:
                if fallback_text:
                    btn.setText(fallback_text)

        self.btn_skip_start = QPushButton()
        self.btn_play_pause = QPushButton()
        self.btn_skip_end = QPushButton()

        _set_btn_icon(self.btn_skip_start, "step-backward.svg")
        _set_btn_icon(self.btn_play_pause, "play.svg")
        _set_btn_icon(self.btn_skip_end, "step-forward.svg")
        
        

        for b in (self.btn_skip_start, self.btn_play_pause, self.btn_skip_end):
            b.setFixedSize(38, 38)
            b.setStyleSheet("""
                QPushButton {
                    background:#2a2d30; color:#cdd3da; border-radius:8px;
                    font-weight:bold; font-size:15px;
                }
                QPushButton:hover { background:#35383c; color:white; }
                QPushButton:pressed { background:#007aff; color:white; }
            """)

        top_controls.addWidget(self.btn_skip_start)
        top_controls.addWidget(self.btn_play_pause)
        top_controls.addWidget(self.btn_skip_end)

        sep1 = QFrame()
        sep1.setFrameShape(QFrame.VLine)
        sep1.setStyleSheet("color:#3a3d40;")
        top_controls.addWidget(sep1)

        self.btn_set_in  = QPushButton("Set In")
        self.btn_set_out = QPushButton("Set Out")
        self.btn_apply_trim = QPushButton("Apply Trim")

        for b, hov in [(self.btn_set_in, "#007aff"), (self.btn_set_out, "#007aff")]:
            b.setFixedHeight(38)
            b.setStyleSheet(f"""
                QPushButton {{
                    background:#2a2d30; color:#cdd3da; border-radius:8px;
                    padding:0 18px; font-size:13px;
                }}
                QPushButton:hover {{ background:#35383c; color:{hov}; }}
            """)

        self.btn_apply_trim.setFixedHeight(38)
        self.btn_apply_trim.setStyleSheet("""
            QPushButton {
                background:#2a2d30; color:#cdd3da; border-radius:8px;
                padding:0 20px; font-size:13px;
            }
            QPushButton:hover { background:#007aff; color:white; }
            QPushButton:disabled { background:#2a2d30; color:#666; }
        """)

        top_controls.addWidget(self.btn_set_in)
        top_controls.addWidget(self.btn_set_out)
        top_controls.addWidget(self.btn_apply_trim)

        sep2 = QFrame()
        sep2.setFrameShape(QFrame.VLine)
        sep2.setStyleSheet("color:#3a3d40;")
        top_controls.addWidget(sep2)

        

        self.lbl_frame_counter = QLabel("0000/0000")
        self.lbl_frame_counter.setStyleSheet("color:#ffffff; font-family:Consolas; font-size:14px;")
        self.lbl_frame_counter.setAlignment(Qt.AlignCenter) 

        sep_trim_1 = QFrame()
        sep_trim_1.setFrameShape(QFrame.VLine)
        sep_trim_1.setStyleSheet("color:#3a3d40;")
        

        self.lbl_trim_info = QLabel("Trim: no data")
        self.lbl_trim_info.setStyleSheet("color:#000000; font-family:Consolas; font-size:13px;")
        self.lbl_trim_info.setAlignment(Qt.AlignCenter) 

        sep_trim_2 = QFrame()
        sep_trim_2.setFrameShape(QFrame.VLine)
        sep_trim_2.setStyleSheet("color:#3a3d40;")

        self.timeline = TimelineWidget()
        self.time_slider = QSlider(Qt.Horizontal)
        self.time_slider.setRange(0, 0)
        self.time_slider.setEnabled(False)
        self.time_slider.hide()
        self.time_label = QLabel("00:00.000")
        self.time_label.setStyleSheet("color:#000000; font-family:Consolas; font-size:13px;")
        self.time_label.setAlignment(Qt.AlignCenter)

        self.settings_btn = QPushButton()
        self.settings_btn.setIcon(QIcon(str(ASSETS_DIR / "sliders.svg")))
        self.settings_btn.setFixedSize(28, 28)
        self.settings_btn.clicked.connect(self._open_settings_dialog)
        
        sep_trim_3 = QFrame()
        sep_trim_3.setFrameShape(QFrame.VLine)
        sep_trim_3.setStyleSheet("color:#3a3d40;")

        top_controls.addWidget(self.lbl_frame_counter)
        top_controls.addWidget(sep_trim_1)
        top_controls.addWidget(self.lbl_trim_info)
        top_controls.addWidget(sep_trim_2)
        top_controls.addWidget(self.time_label)
        top_controls.addWidget(sep_trim_3)
        top_controls.addWidget(self.settings_btn)
        

        controls_wrapper.addLayout(top_controls)

        
        
        timeline_row = QHBoxLayout()
        timeline_row.setSpacing(10)
        timeline_row.addWidget(self.timeline, 1)

        controls_wrapper.addLayout(timeline_row)
        
        status_row = QHBoxLayout()
        def _status_box(title, value):
            box = QFrame()
            box.setStyleSheet("""
                QFrame {
                    background:#1e2023; border:1px solid #2a2d30;
                    border-radius:10px;
                }
            """)
            lay = QVBoxLayout(box)
            lay.setContentsMargins(10,6,10,6)
            t = QLabel(title)
            t.setStyleSheet("color:#6c7177; font-size:11px;")
            v = QLabel(value)
            v.setStyleSheet("color:#cdd3da; font-size:13px; font-weight:bold;")
            lay.addWidget(t)
            lay.addWidget(v)
            return box, v
        controls_wrapper.addLayout(status_row)

        preview_bottom_layout.addLayout(controls_wrapper)

        self.btn_set_in.clicked.connect(self._set_timeline_in)
        self.btn_set_out.clicked.connect(self._set_timeline_out)
        self.btn_apply_trim.clicked.connect(self._apply_trim)
        self.btn_skip_start.clicked.connect(lambda: self.time_slider.setValue(self.timeline.trim_start))
        self.btn_skip_end.clicked.connect(lambda: self.time_slider.setValue(self.timeline.trim_end))
        self.btn_play_pause.clicked.connect(self._toggle_play_pause_button)

        def _plot_current_frame_with_mask(frame_idx):
            if self.frames_data is None or frame_idx < 0 or frame_idx >= len(self.frames_data):
                return
            try:
                pts = self.frames_data[int(frame_idx)]
                vis = None
                try:
                    if hasattr(self, 'marker_editor') and self.marker_editor:
                        vis = np.array(self.marker_editor.get_marker_visibility(), dtype=bool)
                        if vis.size > pts.shape[0]:
                            vis = vis[:pts.shape[0]]
                        elif vis.size < pts.shape[0]:
                            pad = np.ones((pts.shape[0] - vis.size,), dtype=bool)
                            vis = np.concatenate([vis, pad])
                except Exception:
                    vis = None
                
                try:
                    if vis is not None:
                        self.markers_3d_widget.plot_markers_masked(pts, vis)
                    else:
                        self.markers_3d_widget.plot_markers(pts)
                except Exception:
                    pass
            except Exception:
                pass

        self._plot_current = _plot_current_frame_with_mask
        

        def _on_timeline_selected(idx):
            try:
                self.time_slider.setValue(int(idx))
            except Exception:
                _plot_current_frame_with_mask(int(idx))
        self.timeline.frameSelected.connect(_on_timeline_selected)
        self.timeline.trimChanged.connect(self._on_trim_changed)

        self.play_timer = QTimer()
        self.play_timer.setInterval(100)  

        self.frames_data = None  
        self.frame_rate = DEFAULT_FRAME_RATE

        def _on_slider_changed(val):
            if self.frames_data is None:
                return
            val = int(val)
            if val < 0 or val >= len(self.frames_data):
                return
            try:
                _plot_current_frame_with_mask(val)
                t = val / float(self.frame_rate) if self.frame_rate and self.frame_rate > 0 else 0.0
                ms = int((t - int(t)) * 1000)
                self.time_label.setText(f"{int(t//60):02d}:{int(t%60):02d}.{ms:03d}")
                try:
                    if hasattr(self, 'timeline'):
                        self.timeline.set_current(val)
                        self._refresh_timeline_metadata()
                except Exception:
                    pass
            except Exception:
                pass

        self.time_slider.valueChanged.connect(_on_slider_changed)

        def _advance():
            if self.frames_data is None:
                return
            
            trim_start, trim_end = self.timeline.get_trim_range()
            
            current = self.time_slider.value()
            
            if current >= trim_end:
                next_frame = trim_start
            else:
                next_frame = current + 1
            
            self.time_slider.setValue(next_frame)
        
        self.play_timer.timeout.connect(_advance)

        preview_splitter.setChildrenCollapsible(False)
        preview_splitter.addWidget(preview_top)
        preview_splitter.addWidget(preview_bottom)
        preview_splitter.setStretchFactor(0, 1)
        preview_splitter.setStretchFactor(1, 0)
        preview_splitter.setSizes([1000, 130])

        preview_frame = QFrame()
        preview_frame.setMinimumWidth(400)
        preview_layout = QVBoxLayout(preview_frame)
        preview_layout.setContentsMargins(8, 4, 8, 0)
        preview_layout.addWidget(preview_splitter)

        left_frame.setLayout(left_panel)
        
        splitter = QSplitter(Qt.Horizontal)
        splitter.addWidget(left_frame)
        splitter.addWidget(preview_frame)
        
        marker_frame = QFrame()
        marker_frame.setStyleSheet("background:#fff; color:#222;border-top-left-radius: 12px; border-bottom-left-radius: 12px; border-top-right-radius: 0px; border-bottom-right-radius: 0px;")
        marker_frame.setMinimumWidth(240)
        marker_frame.setMaximumWidth(270)
        marker_layout = QVBoxLayout(marker_frame)
        marker_layout.setContentsMargins(8, 8, 8, 8)
        
        self.marker_editor = MarkerEditor()
        self.marker_editor.main_window_ui = self 
        
        marker_layout.addWidget(self.marker_editor, 1)

        self.marker_frame = marker_frame
        marker_frame.hide()
        
        self.marker_editor.markersChanged.connect(self._on_markers_visibility_changed)
        self.marker_editor.markerRenamed.connect(self._on_marker_renamed)
        self.marker_editor.markerDeleted.connect(self._on_marker_deleted)
        self.marker_editor.markerRestored.connect(self._on_marker_restored)

        splitter.addWidget(marker_frame)
        splitter.setChildrenCollapsible(False)
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        splitter.setStretchFactor(2, 0)
        splitter.setSizes([300, 700, 160])
        layout.addWidget(splitter)

        self.file_list = QListWidget()
        
        self.import_btn = import_btn
        self.settings_btn = self.settings_btn
        self.preview_label = self.preview_label


        self.markers_3d_widget = Markers3DWidget()
        try:
            self.markers_3d_widget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
            self.markers_3d_widget.hide()
        except Exception:
            pass
        preview_top_layout.addWidget(self.markers_3d_widget, 1)


        preview_top.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        preview_bottom.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        preview_bottom.setMaximumHeight(260)
        preview_frame.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        splitter.setSizes([300, 800])
        preview_splitter.setSizes([1000, 130])

        self.file_list.currentTextChanged.connect(self.update_preview)

        from .widgets.file_tree_widget import FileTreeWidget

        self.study_combo = QComboBox()
        self.study_combo.view().window().setWindowFlags(
            Qt.Popup | Qt.FramelessWindowHint | Qt.NoDropShadowWindowHint)

        self.study_combo.setStyleSheet("""
            QComboBox{
                border: 2px solid #ccc;
                border-radius: 3px;
                padding: 6px;
                background: white;
                color: #000000;
            }
            QComboBox:hover {
                border: 2px solid #3aa0ff;
                border-radius: 3px;
            }
            QComboBox::drop-down {
                border: none;
                background: white;
                width: 0px;
            }
            QComboBox::down-arrow {
                image: none;  
                width: 0px;
                height: 0px;
            }
            QComboBox QAbstractItemView {
                background: white;
                color: #222;
                selection-background-color: #3aa0ff;
                selection-color: white;
                border: 2px solid #ccc;
                border-radius: 6px;
                outline: none;
            }
            QComboBox QAbstractItemView::item {
                padding: 6px;
                color: #222;
                border-radius: 4px; 
            }
            QComboBox QAbstractItemView::item:hover {
                background: #e8f4ff;
                border-radius: 4px;
                color: #222;
                outline: none;
            }
            QComboBox QAbstractItemView::item:selected {
                background: #3aa0ff;
                border-radius: 4px;
                color: white;
                outline: none;
            }
        """)
        self.study_combo.setContextMenuPolicy(Qt.CustomContextMenu)
        self.study_combo.customContextMenuRequested.connect(self._show_study_context_menu)

        self.study_combo.currentIndexChanged.connect(self._on_study_combo_changed)
        left_panel.addWidget(self.study_combo)

       

        self.file_tree = FileTreeWidget(main_window_ui=self)
        self.file_tree.fileSelected.connect(self._on_file_tree_selected)
        left_panel.addWidget(self.file_tree, 1)
        self._load_studies()

        try:
            self.marker_editor.main_window_ui = self
            
            self.study_combo.currentIndexChanged.connect(
                lambda idx: self.marker_editor._populate_participant_combo()
            )
            
        except Exception as e:
            pass
        QTimer.singleShot(3000, self._startup_scan_files)

    def _startup_scan_files(self):
        try:
            from ..database.db_manager import DatabaseManager
                        
            db = DatabaseManager()
            studies = db.get_all_studies() or []
            study_ids = [getattr(s, "id_study", None) for s in studies if getattr(s, "id_study", None)]
            
            if not study_ids:
                return
            
            self._startup_worker = FileSyncWorker(study_ids, parent=self._main_window)
            
            def on_finished(added, removed):
                try:
                    self._startup_worker.deleteLater()
                except Exception:
                    pass
                self._startup_worker = None
            
            self._startup_worker.finished.connect(on_finished)
            self._startup_worker.start()
            
        except Exception as e:
            pass
    def _undo_action(self):
        if not self._undo_stack:
            styled_message_box(QMessageBox.Information, "Undo", "Nothing to undo.", parent=self._main_window)
            return
        
        action = self._undo_stack.pop()
        action_type = action['type']
                
        if action_type == 'delete_file':
            self._undo_delete_file(action)
        elif action_type == 'trim':
            self._undo_trim(action)
        elif action_type == 'delete_marker':
            self._undo_delete_marker(action)
        elif action_type == 'rename_marker':  
            self._undo_rename_marker(action)
        elif action_type == 'assign_markers':
            self._undo_assign_markers(action)
        elif action_type == 'import_file':  
            self._undo_import_file(action)    
        
        self._redo_stack.append(action)

    def _redo_action(self):
        if not self._redo_stack:
            styled_message_box(QMessageBox.Information, "Redo", "Nothing to redo.", parent=self._main_window)
            return
        
        action = self._redo_stack.pop()
        action_type = action['type']
                
        if action_type == 'delete_file':
            self._redo_delete_file(action)
        elif action_type == 'trim':
            self._redo_trim(action)
        elif action_type == 'delete_marker':
            self._redo_delete_marker(action)
        elif action_type == 'rename_marker':  
            self._redo_rename_marker(action)
        elif action_type == 'assign_markers': 
            self._redo_assign_markers(action)
        elif action_type == 'import_file':  
            self._redo_import_file(action)
        
        self._undo_stack.append(action)   

    def _undo_delete_file(self, action):
        try:
            path = Path(action['path'])
            
            if action['backup']:
                with open(path, 'wb') as f:
                    f.write(action['backup'])
            else:
                styled_message_box(QMessageBox.Warning, "Cannot Restore", f"File '{path.name}' has no backup.", parent=self._main_window)
                return
            
            if action['is_c3d'] and action['db_record']:
                from ..database.db_manager import DatabaseManager
                from ..database.models import File
                
                db = DatabaseManager()
                rec = action['db_record']
                new_file = File(name=rec['name'], file_path=rec['path'], study_id=rec['study_id'])
                db.add_file(new_file)
            
            if hasattr(self, 'file_tree'):
                self.file_tree._refresh_tree()
            
            styled_message_box(QMessageBox.Information, "File Restored", f"Restored: {path.name}", parent=self._main_window)
            
        except Exception as e:
            pass
    def _redo_delete_file(self, action):
        try:
            path = Path(action['path'])
            
            if path.exists():
                path.unlink()
            
            if action['is_c3d'] and action['db_record']:
                from ..database.db_manager import DatabaseManager
                db = DatabaseManager()
                all_files = db.get_all_files()
                for f in all_files:
                    if f.file_path == str(path):
                        db.delete_file(f.id_file)
                        break
            
            if hasattr(self, 'file_tree'):
                self.file_tree._refresh_tree()
            
            styled_message_box(QMessageBox.Information, "Delete Redone", f"Deleted again: {path.name}", parent=self._main_window)
            
        except Exception as e:
            pass
        
    def _undo_trim(self, action):
        try:
            self.frames_data = action['original_data']
            
            self.timeline.set_frames_count(self.frames_data.shape[0])
            self.timeline.set_trim_range(0, self.frames_data.shape[0] - 1)
            
            if hasattr(self, 'lbl_trim_info'):
                self.lbl_trim_info.setText(f"Trim: 0–{self.frames_data.shape[0] - 1}")
            
            self.time_slider.setRange(0, max(0, self.frames_data.shape[0] - 1))
            self.time_slider.setValue(0)
            
            self._plot_current(0)
            
            
        except Exception as e:
            pass
        
    def _redo_trim(self, action):
        try:
            start = action['trim_start']
            end = action['trim_end']
            
            self.frames_data = action['original_data'][start:end + 1, :, :]
            
            self.timeline.set_frames_count(self.frames_data.shape[0])
            self.timeline.set_trim_range(0, self.frames_data.shape[0] - 1)
            
            if hasattr(self, 'lbl_trim_info'):
                self.lbl_trim_info.setText(f"Trim: 0–{self.frames_data.shape[0] - 1}")
            
            self.time_slider.setRange(0, max(0, self.frames_data.shape[0] - 1))
            self.time_slider.setValue(0)
            
            self._plot_current(0)
                      
        except Exception as e:
            pass
        
    def _undo_delete_marker(self, action):
        try:
            items = sorted(action['items'], key=lambda x: x['index'])
            
            for item in items:
                idx = item['index']
                
                self.marker_editor.marker_labels.insert(idx, item['label'])
                self.marker_editor.marker_visible.insert(idx, item['visible'])
                
                if item['data'] is not None and self.frames_data is not None:
                    self.frames_data = np.insert(
                        self.frames_data,
                        idx,
                        item['data'],
                        axis=1
                    )
            
            self.marker_editor._populate_marker_list()
            if self.time_slider.isEnabled():
                self._plot_current(int(self.time_slider.value()))
            
            
        except Exception as e:
            pass
        
    def _redo_delete_marker(self, action):
        try:
            items = sorted(action['items'], key=lambda x: x['index'], reverse=True)
            
            for item in items:
                idx = item['index']
                
                if 0 <= idx < len(self.marker_editor.marker_labels):
                    del self.marker_editor.marker_labels[idx]
                    if idx < len(self.marker_editor.marker_visible):
                        del self.marker_editor.marker_visible[idx]
                
                if self.frames_data is not None and 0 <= idx < self.frames_data.shape[1]:
                    self.frames_data = np.delete(self.frames_data, idx, axis=1)
            
            self.marker_editor._populate_marker_list()
            if self.time_slider.isEnabled():
                self._plot_current(int(self.time_slider.value()))
            
            
        except Exception as e:
            pass
            
    def _undo_rename_marker(self, action):
        try:
            index = action['index']
            old_name = action['old_name']
            
            if 0 <= index < len(self.marker_editor.marker_labels):
                self.marker_editor.marker_labels[index] = old_name
                self.marker_editor._update_marker_display(index, old_name)
                self.marker_editor.markerRenamed.emit(index, old_name)
                
                if hasattr(self, 'marker_labels'):
                    if 0 <= index < len(self.marker_labels):
                        self.marker_labels[index] = old_name
                
                
        except Exception as e:
            pass
        
    def _redo_rename_marker(self, action):
        try:
            index = action['index']
            new_name = action['new_name']
            
            if 0 <= index < len(self.marker_editor.marker_labels):
                self.marker_editor.marker_labels[index] = new_name
                self.marker_editor._update_marker_display(index, new_name)
                self.marker_editor.markerRenamed.emit(index, new_name)
                
                if hasattr(self, 'marker_labels'):
                    if 0 <= index < len(self.marker_labels):
                        self.marker_labels[index] = new_name
                            
        except Exception as e:
            pass
        
    def _undo_assign_markers(self, action):
        try:
            changes = action['changes']
            
            for change in reversed(changes):
                index = change['index']
                old_name = change['old_name']
                
                if 0 <= index < len(self.marker_editor.marker_labels):
                    self.marker_editor.marker_labels[index] = old_name
                    self.marker_editor._update_marker_display(index, old_name)
                    self.marker_editor.markerRenamed.emit(index, old_name)
            
            if hasattr(self, 'marker_labels'):
                self.marker_labels = list(self.marker_editor.marker_labels)
            
            self.marker_editor.markersChanged.emit(self.marker_editor.marker_visible)
            
            
        except Exception as e:
            pass
        
    def _redo_assign_markers(self, action):
        try:
            changes = action['changes']
            
            for change in changes:
                index = change['index']
                new_name = change['new_name']
                
                if 0 <= index < len(self.marker_editor.marker_labels):
                    self.marker_editor.marker_labels[index] = new_name
                    self.marker_editor._update_marker_display(index, new_name)
                    self.marker_editor.markerRenamed.emit(index, new_name)
            
            if hasattr(self, 'marker_labels'):
                self.marker_labels = list(self.marker_editor.marker_labels)
            
            self.marker_editor.markersChanged.emit(self.marker_editor.marker_visible)
            
            
        except Exception as e:
            pass
        
    def _undo_import_file(self, action):
        try:
            from pathlib import Path
            
            target_path = Path(action['target_path'])
            
            if target_path.exists():
                target_path.unlink()
            
            if action.get('db_record'):
                try:
                    from ..database.db_manager import DatabaseManager
                    db = DatabaseManager()
                    
                    all_files = db.get_all_files()
                    for f in all_files:
                        if f.file_path == str(target_path):
                            db.delete_file(f.id_file)
                            break
                    else:
                        pass                           
                except Exception as e:
                    pass
            
            if hasattr(self, 'file_tree'):
                self.file_tree._refresh_tree()
            
            styled_message_box(
                QMessageBox.Information,
                "Import Undone",
                f"Removed imported file: {target_path.name}",
                parent=self._main_window
            )
            
        except Exception as e:
            pass
        
    def _redo_import_file(self, action):
        try:
            from pathlib import Path
            import shutil
            
            source_path = Path(action['source_path'])
            target_path = Path(action['target_path'])
            
            if not source_path.exists():
                styled_message_box(
                    QMessageBox.Warning,
                    "Source Not Found",
                    f"Cannot redo import: source file no longer exists:\n{source_path}",
                    parent=self._main_window
                )
                return
            
            shutil.copy2(source_path, target_path)
            
            if action.get('db_record'):
                try:
                    from ..database.db_manager import DatabaseManager
                    from ..database.models import File
                    
                    db = DatabaseManager()
                    rec = action['db_record']
                    
                    new_file = File(
                        name=rec['name'],
                        file_path=rec['path'],
                        study_id=rec['study_id']
                    )
                    file_id = db.add_file(new_file)
                    
                    action['db_record']['id'] = file_id
                    
                except Exception as e:
                    pass
            
            if hasattr(self, 'file_tree'):
                self.file_tree._refresh_tree()
            
            styled_message_box(
                QMessageBox.Information,
                "Import Redone",
                f"Re-imported file: {target_path.name}",
                parent=self._main_window
            )
            
        except Exception as e:
            pass    
    
    def _toggle_play_pause_button(self):
        if not hasattr(self, 'play_timer'):
            return

        def _set_play_icon():
            try:
                p = ASSETS_DIR / "play.svg"
                if p.exists():
                    self.btn_play_pause.setIcon(QIcon(str(p)))
                    self.btn_play_pause.setIconSize(QSize(20, 20))
                    self.btn_play_pause.setText("")
                else:
                    self.btn_play_pause.setIcon(QIcon())
                    self.btn_play_pause.setText("▶")
            except Exception:
                self.btn_play_pause.setText("▶")

        def _set_pause_icon():
            try:
                p = ASSETS_DIR / "pause.svg"
                if p.exists():
                    self.btn_play_pause.setIcon(QIcon(str(p)))
                    self.btn_play_pause.setIconSize(QSize(20, 20))
                    self.btn_play_pause.setText("")
                else:
                    self.btn_play_pause.setIcon(QIcon())
                    self.btn_play_pause.setText("⏸")
            except Exception:
                self.btn_play_pause.setText("⏸")

        if self.play_timer.isActive():
            self.play_timer.stop()
            _set_play_icon()
            if hasattr(self, 'lbl_playback_state'):
                self.lbl_playback_state.setText("Stopped")
        else:
            try:
                interval = int(1000 / max(1.0, float(getattr(self, 'frame_rate', DEFAULT_FRAME_RATE))))
                self.play_timer.setInterval(interval)
            except Exception:
                pass
            self.play_timer.start()
            _set_pause_icon()
            if hasattr(self, 'lbl_playback_state'):
                self.lbl_playback_state.setText("Playing")

    def _set_timeline_in(self):
        if not hasattr(self, 'timeline'):
            return
        cur = None
        try:
            cur = int(self.timeline.current)
        except Exception:
            pass
        if cur is None and hasattr(self, 'time_slider') and self.time_slider.isEnabled():
            cur = int(self.time_slider.value())
        if cur is None:
            cur = 0
        self.timeline.set_trim_range(max(0, min(cur, self.timeline.trim_end)), self.timeline.trim_end)

    def _set_timeline_out(self):
        if not hasattr(self, 'timeline'):
            return
        cur = None
        try:
            cur = int(self.timeline.current)
        except Exception:
            pass
        if cur is None and hasattr(self, 'time_slider') and self.time_slider.isEnabled():
            cur = int(self.time_slider.value())
        if cur is None:
            cur = 0
        self.timeline.set_trim_range(self.timeline.trim_start, max(self.timeline.trim_start, min(cur, self.timeline.frames - 1)))
    
    def _open_settings_dialog(self):
        try:
            current_settings = self.config_manager.get_all()
                        
            dlg = SettingsDialog(current_settings, self._main_window)
            dlg.settingsChanged.connect(self._apply_visualization_settings)
            dlg.exec()
            
        except Exception as e:
            pass
        
            
    def _apply_visualization_settings(self, settings: dict):
        try:
            
            from ..config import GRID_SIZE, GRID_SPACING
            
            self.config_manager.update(settings)
            
            if 'frame_rate' in settings:
                self.frame_rate = float(settings['frame_rate'])
                if hasattr(self, 'play_timer'):
                    interval = int(1000 / max(1.0, self.frame_rate))
                    self.play_timer.setInterval(interval)
            
            if hasattr(self, 'markers_3d_widget') and self.markers_3d_widget:
                viewer = self.markers_3d_widget
                
                if 'camera_distance' in settings:
                    try:
                        viewer.view.setCameraPosition(distance=float(settings['camera_distance']))
                    except Exception as e:
                        pass
                
                if 'grid_size' in settings or 'grid_spacing' in settings:
                    try:
                        import pyqtgraph.opengl as gl
                        for item in viewer.view.items[:]:
                            if isinstance(item, gl.GLGridItem):
                                viewer.view.removeItem(item)
                        
                        g = gl.GLGridItem()
                        g.setSize(
                            x=float(settings.get('grid_size', GRID_SIZE)),
                            y=float(settings.get('grid_size', GRID_SIZE))
                        )
                        g.setSpacing(
                            float(settings.get('grid_spacing', GRID_SPACING)),
                            float(settings.get('grid_spacing', GRID_SPACING))
                        )
                        viewer.view.addItem(g)
                    except Exception as e:
                        pass
                
            
            
            
        except Exception as e:
            pass

    def _on_markers_visibility_changed(self, visibility):
        try:
            if self.frames_data is not None and self.time_slider.isEnabled():
                frame = int(self.time_slider.value())
                self._plot_current(frame)
        except Exception:
            pass

    def _on_marker_renamed(self, index, new_name):
        try:
            if hasattr(self, 'marker_labels') and self.marker_labels:
                if 0 <= index < len(self.marker_labels):
                    self.marker_labels[index] = new_name
                    self._mark_modified()
        except Exception:
            pass

    def _on_marker_deleted(self, index):
        try:
            if hasattr(self, 'frames_data') and self.frames_data is not None:
                if 0 <= index < self.frames_data.shape[1]:
                    self.frames_data = np.delete(self.frames_data, index, axis=1)
                    
                    if hasattr(self, 'marker_editor') and self.marker_editor:
                        self.marker_labels = self.marker_editor.get_marker_labels()
                    
                    self._mark_modified()
                    
                    if self.time_slider.isEnabled():
                        frame = int(self.time_slider.value())
                        self._plot_current(frame)
        except Exception as e:
            pass
        
    def _on_marker_restored(self, index, marker_data):

        try:
            if hasattr(self, 'frames_data') and self.frames_data is not None:
                if marker_data is not None:
                    pass
                    
                    if 0 <= index <= self.frames_data.shape[1]:
                        self.frames_data = np.insert(
                            self.frames_data, 
                            index, 
                            marker_data, 
                            axis=1
                        )
                        
                        
                        if hasattr(self, 'marker_editor') and self.marker_editor:
                            self.marker_labels = self.marker_editor.get_marker_labels()
                        
                        if hasattr(self, 'marker_labels'):
                            expected_count = self.frames_data.shape[1]
                            actual_count = len(self.marker_labels)
                            
                                
                        
                        self._mark_modified()
                        
                        if self.time_slider.isEnabled():
                            frame = int(self.time_slider.value())
                            self._plot_current(frame)
                    else:
                        pass
                else:
                    pass
        except Exception as e:
            pass

    def _normalize_label(self, lab):
        try:
            if isinstance(lab, bytes):
                return lab.decode('utf-8', errors='ignore').strip()
            if isinstance(lab, (list, tuple)) or (hasattr(lab, 'dtype') and getattr(lab, 'dtype') == 'uint8'):
                try:
                    return ''.join([c.decode('utf-8', errors='ignore') if isinstance(c, (bytes, bytearray)) else str(c) for c in lab]).strip()
                except Exception:
                    return str(lab)
            return str(lab).strip()
        except Exception:
            return str(lab)

    def _is_model_output_label(self, label: str) -> bool:
        try:
            if not label:
                return False
            lab = str(label).strip().lower()
            
            model_keywords = [
                'angles', 'angle', 'power', 'force', 'moment', 'groundreaction', 
                'groundreactio', 'normalised', 'normalized', 'grf',
                'reaction', 'reactio', 'momen', 'progress'
            ]
            
            if ':' in lab:
                left, right = lab.split(':', 1)
                left = left.strip()
                right = right.strip()
                
                if left.startswith(('actor', 'model', 'output', 'tp_')):
                    for k in model_keywords:
                        if k in right:
                            return True
                    return False
                else:
                    for k in model_keywords:
                        if k in lab:
                            return True
            else:
                for k in model_keywords:
                    if k in lab:
                        return True
                    
        except Exception:
            pass
        return False

    def _extract_labels_from_ezc3d(self, c):
        labels = None
        try:
            params = c.get('parameters', {}) if hasattr(c, 'get') else {}
            if isinstance(params, dict):
                try:
                    pl = params.get('POINT') or params.get('POINTS') or {}
                    if isinstance(pl, dict):
                        lbls = pl.get('LABELS') or pl.get('LABEL') or pl.get('Labels') or None
                        if isinstance(lbls, dict):
                            labels = lbls.get('value') or lbls.get('labels') or None
                        elif lbls:
                            labels = lbls
                except Exception:
                    pass
            if not labels:
                try:
                    labels = c['parameters']['POINT']['LABELS']['value']
                except Exception:
                    pass
        except Exception:
            labels = None
        if not labels:
            return None
        return [self._normalize_label(x) for x in list(labels)]

    def _extract_labels_from_reader(self, r):
        labels = None
        try:
            if hasattr(r, 'point_labels'):
                labels = getattr(r, 'point_labels')
            else:
                hdr = getattr(r, 'header', None)
                if isinstance(hdr, dict):
                    labels = hdr.get('point_labels') or hdr.get('labels')
        except Exception:
            labels = None
        if not labels:
            return None
        return [self._normalize_label(x) for x in list(labels)]

    def load_frames(self, path):
        if not os.path.exists(path):
            return 0

        if ezc3d is not None:
            try:
                c = ezc3d.c3d(path)
                self._refresh_timeline_metadata()
                try:
                    hdr = c.get('header', {})
                    fr = None
                    if isinstance(hdr, dict):
                        fr = hdr.get('points', {}).get('frame_rate') or hdr.get('point_rate') or hdr.get('frame_rate')
                    if fr is not None:
                        self.frame_rate = float(fr)
                except Exception:
                    pass

                pts = np.array(c['data']['points'])
                if pts.ndim >= 3 and pts.shape[2] > 0:
                    frames = pts[:3, :, :].transpose((2, 1, 0)).astype(float)

                    try:
                        norm_labels = self._extract_labels_from_ezc3d(c)
                        if norm_labels:
                            if len(norm_labels) < frames.shape[1]:
                                norm_labels = norm_labels + [""] * (frames.shape[1] - len(norm_labels))
                            labels_for_pts = norm_labels[:frames.shape[1]]
                            
                            keep_mask = [not self._is_model_output_label(l) for l in labels_for_pts]
                            kept_idx = np.array(keep_mask, dtype=bool)
                            if kept_idx.sum() > 0:
                                frames = frames[:, kept_idx, :]
                                self.marker_labels = [l for l, k in zip(labels_for_pts, keep_mask) if k]
                                self._original_marker_labels = list(self.marker_labels)
                            else:
                                self.marker_labels = labels_for_pts
                                self._original_marker_labels = list(labels_for_pts)
                        else:
                            self.marker_labels = []
                            self._original_marker_labels = []
                    except Exception:
                        self.marker_labels = []
                        self._original_marker_labels = []

                    try:
                        all_nan = np.all(np.isnan(frames), axis=(0, 2))
                        if np.any(all_nan):
                            keep = ~all_nan
                            if keep.sum() > 0:
                                frames = frames[:, keep, :]
                                if self.marker_labels:
                                    self.marker_labels = [l for l, k in zip(self.marker_labels, keep) if k]
                    except Exception:
                        pass

                    self.frames_data = frames
                    self.time_slider.setEnabled(True)
                    self.time_slider.setRange(0, max(0, frames.shape[0] - 1))

                    try:
                        self.time_slider.setValue(0)
                    except Exception:
                        pass
                    try:
                        if hasattr(self, 'timeline') and self.timeline:
                            self.timeline.set_current(0)
                    except Exception:
                        pass
                    try:
                        self._refresh_timeline_metadata()
                    except Exception:
                        pass
                    
                    try:
                        if hasattr(self, 'timeline'):
                            self.timeline.set_frames_count(frames.shape[0])
                            self.timeline.set_frame_rate(self.frame_rate)
                            mask = ~(np.all(np.isclose(frames.reshape(frames.shape[0], -1), 0.0), axis=1))
                            self.timeline.set_valid_mask(mask)
                            
                            if hasattr(self, 'lbl_trim_info'):
                                trim_start = 0
                                trim_end = frames.shape[0] - 1
                                self.lbl_trim_info.setText(f"Trim: {trim_start}–{trim_end}")
                    except Exception:
                        pass

                    self.play_timer.setInterval(int(1000 / max(1.0, float(self.frame_rate))))

                    if self.marker_labels:
                        from ..config import DEFAULT_VISIBLE_MARKERS
                        
                        visibility = []
                        for label in self.marker_labels:
                            clean_label = label.split(':')[-1].strip().upper()
                            is_visible = clean_label in DEFAULT_VISIBLE_MARKERS
                            visibility.append(is_visible)
                        
                        self.marker_editor.set_markers(self.marker_labels, visibility)
                        
                        model_outputs = []
                        analog_channels = []
                        
                        try:
                            if ezc3d is not None:
                                c = ezc3d.c3d(path)
                                all_labels = self._extract_labels_from_ezc3d(c)
                                
                                if all_labels:
                                    for label in all_labels:
                                        if self._is_model_output_label(label):
                                            model_outputs.append(label)
                                
                                try:
                                    analog = c.get('data', {}).get('analogs', None)
                                    if analog is not None:
                                        analog_params = c.get('parameters', {}).get('ANALOG', {})
                                        analog_labels = analog_params.get('LABELS', {}).get('value', [])
                                        analog_channels = [self._normalize_label(x) for x in analog_labels]
                                except Exception:
                                    pass
                        except Exception:
                            pass
                        
                        self.marker_editor.set_model_outputs(model_outputs)
                        self.marker_editor.set_analog_channels(analog_channels)
                        
                        if hasattr(self, '_original_marker_labels') and self._original_marker_labels:
                            self.marker_editor._original_labels = list(self._original_marker_labels)

                        if hasattr(self, 'marker_frame'):
                            self.marker_frame.show()
                            if hasattr(self, 'toggle_markers_action'):
                                self.toggle_markers_action.setChecked(True)
                                self.toggle_markers_action.setText("Hide Marker Editor")
                        else:
                            self.marker_editor.show()
                    else:
                        if hasattr(self, 'marker_frame'):
                            self.marker_frame.hide()
                            if hasattr(self, 'toggle_markers_action'):
                                self.toggle_markers_action.setChecked(False)
                                self.toggle_markers_action.setText("Show Marker Editor")
                        else:
                            self.marker_editor.hide()
                    
                    self.original_file_path = path
                    self.current_file_path = path
                    self.is_modified = False
                    self._update_save_actions()
                    self._update_window_title()
                    
                    return int(frames.shape[1])
            except Exception:
                pass

        if Reader is None:
            return 0
        try:
            collected = []
            with open(path, 'rb') as handle:
                r = Reader(handle)
                for i, fr in enumerate(r.read_frames()):
                    pts = np.array(fr[0])[:, :3]
                    collected.append(pts)
            if len(collected) == 0:
                return 0
            frames = np.stack(collected, axis=0).astype(float)

            try:
                norm_labels = self._extract_labels_from_reader(r)
                if norm_labels:
                    if len(norm_labels) < frames.shape[1]:
                        norm_labels = norm_labels + [""] * (frames.shape[1] - len(norm_labels))
                    labels_for_pts = norm_labels[:frames.shape[1]]
                    
                    keep_mask = [not self._is_model_output_label(l) for l in labels_for_pts]
                    kept_idx = np.array(keep_mask, dtype=bool)
                    if kept_idx.sum() > 0:
                        frames = frames[:, kept_idx, :]
                        self.marker_labels = [l for l, k in zip(labels_for_pts, keep_mask) if k]
                        self._original_marker_labels = list(self.marker_labels)
                    else:
                        self.marker_labels = labels_for_pts
                        self._original_marker_labels = list(labels_for_pts)
                else:
                    self.marker_labels = []
                    self._original_marker_labels = []
            except Exception:
                self.marker_labels = []
                self._original_marker_labels = []

            try:
                all_nan = np.all(np.isnan(frames), axis=(0, 2))
                if np.any(all_nan):
                    keep = ~all_nan
                    if keep.sum() > 0:
                        frames = frames[:, keep, :]
                        if self.marker_labels:
                            self.marker_labels = [l for l, k in zip(self.marker_labels, keep) if k]
            except Exception:
                pass

            self.frames_data = frames
            self.time_slider.setEnabled(True)
            self.time_slider.setRange(0, max(0, frames.shape[0] - 1))

            try:
                if hasattr(self, 'timeline'):
                    self.timeline.set_frames_count(frames.shape[0])
                    self.timeline.set_frame_rate(self.frame_rate)
                    
                    if hasattr(self, 'lbl_trim_info'):
                        trim_start = 0
                        trim_end = frames.shape[0] - 1
                        self.lbl_trim_info.setText(f"Trim: {trim_start}–{trim_end}")
            except Exception:
                pass
            
            try:
                hdr = getattr(r, 'header', None)
                if isinstance(hdr, dict):
                    fr = hdr.get('point_rate') or hdr.get('frame_rate')
                    if fr is not None:
                        self.frame_rate = float(fr)
            except Exception:
                pass
            
            self.play_timer.setInterval(int(1000 / max(1.0, float(self.frame_rate))))
            
            if self.marker_labels:
                from ..config import DEFAULT_VISIBLE_MARKERS
                
                visibility = []
                for label in self.marker_labels:
                    clean_label = label.split(':')[-1].strip().upper()
                    is_visible = clean_label in DEFAULT_VISIBLE_MARKERS
                    visibility.append(is_visible)
                
                self.marker_editor.set_markers(self.marker_labels, visibility)
                
                model_outputs = []
                analog_channels = []
                
                try:
                    if ezc3d is not None:
                        c = ezc3d.c3d(path)
                        all_labels = self._extract_labels_from_ezc3d(c)
                        
                        if all_labels:
                            for label in all_labels:
                                if self._is_model_output_label(label):
                                    model_outputs.append(label)
                        
                        try:
                            analog = c.get('data', {}).get('analogs', None)
                            if analog is not None:
                                analog_params = c.get('parameters', {}).get('ANALOG', {})
                                analog_labels = analog_params.get('LABELS', {}).get('value', [])
                                analog_channels = [self._normalize_label(x) for x in analog_labels]
                        except Exception:
                            pass
                except Exception:
                    pass
                
                self.marker_editor.set_model_outputs(model_outputs)
                self.marker_editor.set_analog_channels(analog_channels)
                
              
                if hasattr(self, '_original_marker_labels') and self._original_marker_labels:
                    self.marker_editor._original_labels = list(self._original_marker_labels)

                if hasattr(self, 'marker_frame'):
                    self.marker_frame.show()
                    if hasattr(self, 'toggle_markers_action'):
                        self.toggle_markers_action.setChecked(True)
                        self.toggle_markers_action.setText("Hide Marker Editor")
                else:
                    self.marker_editor.show()
            else:
                if hasattr(self, 'marker_frame'):
                    self.marker_frame.hide()
                    if hasattr(self, 'toggle_markers_action'):
                        self.toggle_markers_action.setChecked(False)
                        self.toggle_markers_action.setText("Show Marker Editor")
                else:
                    self.marker_editor.hide()
            
            self.original_file_path = path
            self.current_file_path = path
            self.is_modified = False
            self._update_save_actions()
            self._update_window_title()
            
            if self.frames_data is not None and len(self.frames_data) > 0:
                try:
                    self._plot_current(0)
                except Exception:
                    pass
            try:
                if hasattr(self, 'marker_editor') and self.marker_editor:
                    self.marker_editor._populate_participant_combo()
            except Exception:
                pass
            return int(frames.shape[1])

        except Exception:
            return 0

    def _refresh_timeline_metadata(self):
        if not hasattr(self, 'frames_data') or self.frames_data is None:
            return
        total = self.frames_data.shape[0]
        
        cur = int(self.time_slider.value()) if hasattr(self, 'time_slider') and self.time_slider.isEnabled() else 0
        if hasattr(self, 'lbl_frame_counter'):
            self.lbl_frame_counter.setText(f"{cur:04d}/{total-1:04d}")

        if hasattr(self, 'lbl_time_counter'):
           cur_sec = (cur / float(self.frame_rate)) if self.frame_rate else 0.0
           tot_sec = (total / float(self.frame_rate)) if self.frame_rate else 0.0
           try:
               self.lbl_time_counter.setText(f"{self._format_time(cur_sec)} / {self._format_time(tot_sec)}")
           except Exception:
               pass
        if hasattr(self, 'lbl_duration'):
            dur_sec = total / max(1.0, float(self.frame_rate))
            self.lbl_duration.setText(f"{dur_sec:.2f} s")
        if hasattr(self, 'lbl_fps'):
            self.lbl_fps.setText(f"{int(self.frame_rate)} FPS")

    def update_preview(self, text):
        if not text:
            return
        file_path = text.split("\n")[0]
        info_lines = []
        if os.path.exists(file_path):
            info_lines.append(f"<div style='font-size:18px;font-weight:bold;'>{os.path.basename(file_path)}</div>")
            info_lines.append(f"<div style='font-size:12px;color:#e92c2c;'>{file_path}</div>")
            try:
                count = self.load_frames(file_path)
                if count is None or count == 0:
                    info_lines.append("<div style='margin-top:8px;color:#333;'>Loaded (no markers)</div>")
                    try:
                        self.markers_3d_widget.hide()
                    except Exception:
                        pass
                    try:
                        self.preview_label.show()
                    except Exception:
                        pass
                else:
                    info_lines.append(f"<div style='margin-top:8px;color:#333;'>Markers: {count}</div>")
                    
                    try:
                        self.preview_label.hide()
                    except Exception:
                        pass
                    
                    try:
                        self.markers_3d_widget.show()
                        if self.frames_data is not None and len(self.frames_data) > 0:
                            try:
                                self._plot_current(0)
                            except Exception as e:
                                pass
                    except Exception as e:
                        pass
                    
                    try:
                        n_frames = 0 if self.frames_data is None else len(self.frames_data)
                        lbls = getattr(self, 'marker_labels', None)
                        if lbls:
                            sample = ', '.join(lbls[:20])
                            info_lines.append(f"<div style='font-size:12px;color:#444;'>Frames: {n_frames}, Labels: {len(lbls)} (sample: {sample})</div>")
                        else:
                            info_lines.append(f"<div style='font-size:12px;color:#444;'>Frames: {n_frames}, Labels: unknown</div>")
                    except Exception:
                        pass
            except Exception as e:
                info_lines.append(f"<div style='margin-top:8px;color:#a00;'>Load error: {e}</div>")
                try:
                    self.preview_label.show()
                    self.markers_3d_widget.hide()
                except Exception:
                    pass
        else:
            info_lines.append(f"<div style='font-size:16px;'>Selected: {text}</div>")
        
        self.preview_label.setText(''.join(info_lines))

    def _open_file(self):
        from PySide6.QtWidgets import QFileDialog
        dlg = QFileDialog()
        dlg.setFileMode(QFileDialog.ExistingFile)
        dlg.setNameFilter("C3D Files (*.c3d);;All Files (*)")
        if dlg.exec():
            path = dlg.selectedFiles()[0]
            self._load_file(path)

    def _open_file_from_search(self, path: str, study_id: int = 0):
        try:
            if not path:
                return

            if study_id:
                try:
                    for i in range(self.study_combo.count()):
                        if self.study_combo.itemData(i) == study_id:
                            self.study_combo.setCurrentIndex(i)
                            try:
                                self.file_tree.select_file(str(path))
                            except Exception:
                                from PySide6.QtCore import QTimer
                                QTimer.singleShot(150, lambda p=path: self.file_tree.select_file(str(p)))
                            break
                except Exception:
                    pass

            self._load_file(str(path))
        except Exception as e:
            try:
                styled_message_box(QMessageBox.Warning, "Load Error", f"Failed to load file:\n{e}", parent=self._main_window)
            except Exception:
                pass
            

    def _import_file_menu(self):
        if hasattr(self, '_main_window_logic'):
            self._main_window_logic.import_file()

    def _load_file(self, path):
        try:
            count = self.load_frames(path)
            if count:
                self.original_file_path = path
                self.current_file_path = path
                self.is_modified = False
                self._update_save_actions()
                self._update_window_title()
                
                file_already_listed = False
                for i in range(self.file_list.count()):
                    if self.file_list.item(i).text().split("\n")[0] == path:
                        self.file_list.setCurrentRow(i)
                        file_already_listed = True
                        break
                
                if not file_already_listed:
                    self.file_list.addItem(path)
                    self.file_list.setCurrentRow(self.file_list.count() - 1)
                    
        except Exception as e:
            QMessageBox.warning(None, "Load Error", f"Failed to load file:\n{e}")

    def _save_file(self):
        if not self.current_file_path:
            self._save_as_file()
            return
        
        try:
            self._perform_save(self.current_file_path)
            self.is_modified = False
            self._update_save_actions()
            self._update_window_title()

            styled_message_box(QMessageBox.Information, "File Saved", f"File saved successfully:\n{str(self.current_file_path)}", parent=self._main_window)

        except Exception as e:          
            styled_message_box(QMessageBox.Warning, "Save Error", f"Failed to save file:\n{e}", parent=self._main_window)

    def _save_as_file(self):
        from PySide6.QtWidgets import QFileDialog
        dlg = QFileDialog()
        dlg.setFileMode(QFileDialog.AnyFile)
        dlg.setAcceptMode(QFileDialog.AcceptSave)
        dlg.setNameFilter("C3D Files (*.c3d);;All Files (*)")
        dlg.setDefaultSuffix("c3d")
        
        if self.current_file_path:
            dlg.selectFile(self.current_file_path)
        
        if dlg.exec():
            path = dlg.selectedFiles()[0]
            try:
                self._perform_save(path)
                self.current_file_path = path
                self.is_modified = False
                self._update_save_actions()
                self._update_window_title()

                styled_message_box(
                    QMessageBox.Information,
                    "File Saved",
                    f"File saved successfully:\n{path}",
                    parent=self._main_window
                )
            
            except Exception as e:
                styled_message_box(
                    QMessageBox.Warning,
                    "Save Error",
                    f"Failed to save file:\n{e}",
                    parent=self._main_window
                )

    def _save_to_modified(self):
        from pathlib import Path
        from datetime import datetime
        
        if not self.current_file_path:
            styled_message_box(
                QMessageBox.Warning,
                "No File",
                "No file is currently loaded to save.",
                parent=self._main_window
            )
            return
        
        try:
            current_path = Path(self.current_file_path)
            study_folder = current_path.parent
            study_root = study_folder.parent
            
            date_tag = None
            m = re.search(r'\d{4}-\d{2}-\d{2}', study_folder.name)
            if m:
                date_tag = m.group(0)
            else:
                try:
                    mtime = study_folder.stat().st_mtime
                    date_tag = datetime.fromtimestamp(mtime).strftime("%Y-%m-%d")
                except Exception:
                    date_tag = datetime.now().strftime("%Y-%m-%d")

            modified_folder = study_root / f"{date_tag}_modified"
            modified_folder.mkdir(parents=True, exist_ok=True)

            
            filename = current_path.name
            save_path = modified_folder / filename
            
            if save_path.exists():
                dlg = styled_message_box(
                    QMessageBox.Question,
                    "File Exists",
                    f"File '{filename}' already exists in modified folder.\n\nOverwrite?",
                    buttons=QMessageBox.Yes | QMessageBox.No,
                    default=QMessageBox.No,
                    parent=self._main_window
                )
                sb = dlg.standardButton(dlg.clickedButton())
                if sb == QMessageBox.No:
                    return
            
            self._perform_save(str(save_path))
            
            styled_message_box(
                QMessageBox.Information,
                "Saved to Modified",
                f"File saved successfully!\n\nLocation: {str(save_path)}",  
                parent=self._main_window
            )
            self.is_modified = False
            self._update_save_actions()
        
        except Exception as e:
            styled_message_box(
                QMessageBox.Critical,
                "Save Error",
                f"Failed to save to modified folder:\n{e}",
                parent=self._main_window
            )

    def _perform_save(self, path):
        import shutil
        from pathlib import Path
        
        if self.frames_data is None:
            raise ValueError("No data to save")
        self._refresh_timeline_metadata()
        
        if hasattr(self, 'original_file_path') and self.original_file_path:
            if Path(path).suffix.lower() == '.c3d':
                self._save_c3d_with_modifications(path)
            else:
                import numpy as np
                save_data = {
                    'frames': self.frames_data,
                    'labels': getattr(self, 'marker_labels', []),
                    'frame_rate': self.frame_rate
                }
                np.savez(path, **save_data)
        else:
            raise ValueError("No original file to save from")

    def _save_c3d_with_modifications(self, path):
        import shutil
        import json
        from pathlib import Path
        from datetime import datetime

        if not hasattr(self, 'original_file_path') or not self.original_file_path:
            raise ValueError("No original file to modify")

        current_labels = []
        if hasattr(self, 'marker_editor') and self.marker_editor:
            try:
                current_labels = self.marker_editor.get_marker_labels()
                
                self.marker_labels = current_labels
            except Exception as e:
                current_labels = []
        
        if not current_labels and hasattr(self, 'marker_labels'):
            current_labels = self.marker_labels


        original_frame_count = None
        try:
            if ezc3d is not None:
                c_orig = ezc3d.c3d(str(self.original_file_path))
                original_frame_count = int(c_orig['data']['points'].shape[2])
        except Exception:
            original_frame_count = None

        modified_frames = False
        try:
            if hasattr(self, 'frames_data') and self.frames_data is not None and original_frame_count is not None:
                modified_frames = (int(self.frames_data.shape[0]) != original_frame_count)
        except Exception:
            modified_frames = False

        if ezc3d is not None:
            try:
                labels_to_use = current_labels if current_labels else getattr(self, '_original_marker_labels', [])
                if not labels_to_use:
                    labels_to_use = [f"Marker_{i+1}" for i in range(self.frames_data.shape[1])]
                
                self._save_c3d_ezc3d(path, labels_to_use)
                return
            except Exception as e:
                pass
        if modified_frames:
            raise RuntimeError(
                "Cannot save trimmed C3D because ezc3d save failed or ezc3d is not installed. "
                "Install ezc3d (pip install ezc3d) to enable saving trimmed C3D files."
            )

        shutil.copy2(self.original_file_path, path)
        mapping_path = Path(path).with_suffix('.mapping.json')

        original_labels = getattr(self, '_original_marker_labels', current_labels)
        mapping = {}
        for i, (orig, curr) in enumerate(zip(original_labels, current_labels)):
            if orig != curr:
                mapping[orig] = curr

        if mapping:
            with open(mapping_path, 'w', encoding='utf-8') as f:
                json.dump({
                    'marker_name_changes': mapping,
                    'modified_at': datetime.now().isoformat(),
                    'original_file': str(self.original_file_path),
                    'note': 'Mapping created because ezc3d not available or labels-only change.'
                }, f, indent=2)
            
    def _save_c3d_ezc3d(self, path, new_labels):
        import tempfile
        import shutil
        import os
        
        if not hasattr(self, 'frames_data') or self.frames_data is None:
            raise ValueError("No frame data to save")

        current_n_markers = self.frames_data.shape[1]
        current_n_frames = self.frames_data.shape[0]
        
        if not new_labels or len(new_labels) == 0:
            new_labels = [f"Marker_{i+1}" for i in range(current_n_markers)]
        
        if len(new_labels) < current_n_markers:
            new_labels = new_labels + [f"Marker_{i+1}" for i in range(len(new_labels), current_n_markers)]
        elif len(new_labels) > current_n_markers:
            new_labels = new_labels[:current_n_markers]

        temp_fd, temp_path = tempfile.mkstemp(suffix='.c3d')
        os.close(temp_fd)
        
        try:
            c = ezc3d.c3d(str(self.original_file_path))

            try:
                orig_pts = np.array(c.get('data', {}).get('points'))
                orig_point_frames = int(orig_pts.shape[2]) if orig_pts is not None and orig_pts.ndim >= 3 else None
            except Exception:
                orig_point_frames = None

            if 'meta_points' in c.get('data', {}):
                try:
                    del c['data']['meta_points']
                except Exception:
                    pass

            points_data = self.frames_data.transpose(2, 1, 0)
            residuals = np.zeros((1, current_n_markers, current_n_frames), dtype=float)
            points_with_residual = np.vstack([points_data, residuals])
            
            expected_shape = (4, current_n_markers, current_n_frames)
            if points_with_residual.shape != expected_shape:
                raise ValueError(f"Point data shape mismatch: {points_with_residual.shape} != {expected_shape}")

            try:
                analogs = c.get('data', {}).get('analogs', None)
                if analogs is not None and orig_point_frames and orig_point_frames > 0:
                    analogs_arr = np.array(analogs)
                    n_samples = analogs_arr.shape[-1]
                    if orig_point_frames and n_samples % orig_point_frames == 0:
                        subsamples = n_samples // orig_point_frames
                        new_n_samples = current_n_frames * subsamples
                        if new_n_samples <= n_samples:
                            analogs_trimmed = analogs_arr[..., :new_n_samples]
                        else:
                            pad_width = new_n_samples - n_samples
                            pad_shape = list(analogs_arr.shape)
                            pad_shape[-1] = pad_width
                            pad = np.zeros(tuple(pad_shape), dtype=analogs_arr.dtype)
                            analogs_trimmed = np.concatenate([analogs_arr, pad], axis=-1)
                        c['data']['analogs'] = analogs_trimmed
                        try:
                            if 'parameters' in c and 'ANALOG' in c['parameters']:
                                c['parameters']['ANALOG']['FRAMES']['value'] = [int(analogs_trimmed.shape[-1])]
                        except Exception:
                            pass
                    else:
                        if 'analogs' in c.get('data', {}):
                            try:
                                del c['data']['analogs']
                            except Exception:
                                pass
                else:
                    if analogs is not None:
                        try:
                            del c['data']['analogs']
                        except Exception:
                            pass
            except Exception:
                if 'analogs' in c.get('data', {}):
                    try:
                        del c['data']['analogs']
                    except Exception:
                        pass

            c['data']['points'] = points_with_residual

            try:
                c['parameters']['POINT']['LABELS']['value'] = new_labels
            except Exception:
                c['parameters'].setdefault('POINT', {})['LABELS'] = {'value': new_labels}

            try:
                if 'POINT' in c['parameters'] and 'LABELS2' in c['parameters']['POINT']:
                    del c['parameters']['POINT']['LABELS2']
            except Exception:
                pass

            try:
                if 'POINT' in c['parameters'] and 'LABELSX' in c['parameters']['POINT']:
                    empty_labelsx = [""] * current_n_markers
                    c['parameters']['POINT']['LABELSX']['value'] = empty_labelsx
            except Exception:
                try:
                    if 'POINT' in c['parameters'] and 'LABELSX' in c['parameters']['POINT']:
                        del c['parameters']['POINT']['LABELSX']
                except Exception:
                    pass

            try:
                if 'POINT' in c['parameters'] and 'DESCRIPTIONS' in c['parameters']['POINT']:
                    empty_descriptions = [""] * current_n_markers
                    c['parameters']['POINT']['DESCRIPTIONS']['value'] = empty_descriptions
            except Exception:
                pass

            try:
                if 'POINT' in c['parameters'] and 'USED' in c['parameters']['POINT']:
                    c['parameters']['POINT']['USED']['value'] = [current_n_markers]
                else:
                    c['parameters'].setdefault('POINT', {})['USED'] = {'value': [current_n_markers]}
            except Exception:
                pass
            
            try:
                if 'POINT' in c['parameters'] and 'FRAMES' in c['parameters']['POINT']:
                    c['parameters']['POINT']['FRAMES']['value'] = [current_n_frames]
                else:
                    c['parameters'].setdefault('POINT', {})['FRAMES'] = {'value': [current_n_frames]}
            except Exception:
                pass

            try:
                if 'header' in c and isinstance(c['header'], dict):
                    if 'points' in c['header'] and isinstance(c['header']['points'], dict):
                        c['header']['points']['last_frame'] = current_n_frames
                        c['header']['points']['size'] = current_n_markers
            except Exception:
                pass

            c.write(temp_path)
            del c
            shutil.copy2(temp_path, str(path))
            
        finally:
            try:
                os.unlink(temp_path)
            except Exception:
                pass

    def _update_save_actions(self):
        has_data = self.frames_data is not None
        
        self.save_action.setEnabled(has_data and self.is_modified)
        
        self.save_as_action.setEnabled(has_data)
        
        if hasattr(self, 'save_to_modified_action'):
            self.save_to_modified_action.setEnabled(has_data)
        

    def _update_window_title(self):
        if hasattr(self, '_main_window'):
            title = "MotionCaptionary"
            if self.current_file_path:
                from pathlib import Path
                filename = Path(self.current_file_path).name
                title += f" - {filename}"
                if self.is_modified:
                    title += " *"
            self._main_window.setWindowTitle(title)

    def _mark_modified(self):
        self.is_modified = True
        self._update_save_actions()
        self._update_window_title()

    def _undo_marker_action(self):
        try:
            if self.recording_trimmer and self.recording_trimmer.can_undo():
                restored_data = self.recording_trimmer.undo_last_trim()
                
                if restored_data is not None:
                    self.frames_data = restored_data
                    
                    self.timeline.set_frames_count(self.frames_data.shape[0])
                    self.timeline.set_trim_range(0, self.frames_data.shape[0] - 1)
                    
                    if hasattr(self, 'lbl_trim_info'):
                        trim_start = 0
                        trim_end = self.frames_data.shape[0] - 1
                        self.lbl_trim_info.setText(f"Trim: {trim_start}–{trim_end}")
                    
                    self.time_slider.setRange(0, max(0, self.frames_data.shape[0] - 1))
                    self.time_slider.setValue(0)
                    
                    self._plot_current(0)
                    
                    return
            
            if self.marker_editor and self.marker_editor.undo():
                self._mark_modified()
                if self.frames_data is not None and self.time_slider.isEnabled():
                    frame = int(self.time_slider.value())
                    self._plot_current(frame)
        except Exception as e:
            pass

    def _redo_marker_action(self):
        try:
            if self.marker_editor and self.marker_editor.redo():
                self._mark_modified()
                if self.frames_data is not None and self.time_slider.isEnabled():
                    frame = int(self.time_slider.value())
                    self._plot_current(frame)
        except Exception as e:
            pass

    def _on_trim_changed(self, start, end):
        if hasattr(self, 'lbl_trim_info'):
            self.lbl_trim_info.setText(f"Trim: {start}–{end}")
        if hasattr(self, 'btn_apply_trim'):
            self.btn_apply_trim.setEnabled(start > 0 or end < (self.frames_data.shape[0] - 1) if self.frames_data is not None else False)

        if hasattr(self, 'trim_btn') and self.frames_data is not None:
            is_trimmed = start > 0 or end < (self.frames_data.shape[0] - 1)
            self.trim_btn.setEnabled(is_trimmed)
            
            if self.recording_trimmer and is_trimmed:
                is_valid, error = RecordingTrimmer.validate_trim_range(
                    self.frames_data, start, end
                )
                if not is_valid:
                    self.trim_btn.setEnabled(False)

    def _apply_trim(self):
        if self.frames_data is None or not self.recording_trimmer:
            return
        
        try:
            start, end = self.timeline.get_trim_range()
            
            trimmed_data, success = self.recording_trimmer.apply_trim(
                self.frames_data,
                start,
                end,
                self.frame_rate,
                save_to_undo=True
            )
            
            if not success:
                return  
            
            self.frames_data = trimmed_data
            
            self.timeline.set_frames_count(self.frames_data.shape[0])
            self.timeline.set_trim_range(0, self.frames_data.shape[0] - 1)
            
            if hasattr(self, 'lbl_trim_info'):
                new_trim_start = 0
                new_trim_end = self.frames_data.shape[0] - 1
                self.lbl_trim_info.setText(f"Trim: {new_trim_start}–{new_trim_end}")
            
            self.time_slider.setValue(0)
            
            self.is_modified = True
            self._update_save_actions()
            self._update_window_title()
            
            self._plot_current(0)
            
            if hasattr(self, 'trim_btn'):
                self.trim_btn.setEnabled(False)
            
        
        except Exception as e:
            traceback.print_exc()
            styled_message_box(
                QMessageBox.Critical,
                "Trim Error",
                f"Failed to trim recording:\n{e}",
                parent=self._main_window
            )

    def _on_study_combo_changed(self, index: int):
        if index < 0:
            self.file_tree.clear()
            return
        
        study_id = self.study_combo.itemData(index)
        if study_id:
            self._load_study_files(study_id)
            try:
                if hasattr(self, 'marker_editor') and self.marker_editor:
                    self.marker_editor._populate_participant_combo()
            except Exception as e:
                pass

    def _toggle_studies_panel(self):
        
        is_visible = self._left_frame.isVisible()
        self._left_frame.setVisible(not is_visible)
        
        if hasattr(self, 'toggle_studies_action'):
            if is_visible:
                self.toggle_studies_action.setText("Show Studies Panel")
                self.toggle_studies_action.setChecked(False)
            else:
                self.toggle_studies_action.setText("Hide Studies Panel")
                self.toggle_studies_action.setChecked(True)
        
    def _toggle_markers_panel(self):
        
        is_visible = self.marker_frame.isVisible()
        self.marker_frame.setVisible(not is_visible)
        
        if hasattr(self, 'toggle_markers_action'):
            if is_visible:
                self.toggle_markers_action.setText("Show Marker Editor")
                self.toggle_markers_action.setChecked(False)
            else:
                self.toggle_markers_action.setText("Hide Marker Editor")
                self.toggle_markers_action.setChecked(True)
        
    def _load_study_files(self, study_id: int):
        from ..database.db_manager import DatabaseManager
        
        try:
            db = DatabaseManager()
            study = db.get_study(study_id)
            
            if study and study.path:
                self.file_tree.load_folder(study.path, study.name)
            else:
                self.file_tree.clear()
                styled_message_box(
                    QMessageBox.Warning,
                    "Study Path Missing",
                    f"Study '{study.name if study else 'Unknown'}' has no folder path set.",
                    parent=self._main_window
                )
        except Exception as e:
            self.file_tree.clear()

    def _on_file_tree_selected(self, file_path: str):
        from pathlib import Path
        
        path = Path(file_path)
        
        if path.suffix.lower() == '.c3d':
            try:
                count = self.load_frames(str(path))
                
                if count:
                    self.original_file_path = str(path)
                    self.current_file_path = str(path)
                    self.is_modified = False
                    self._update_save_actions()
                    self._update_window_title()
                    
                    self.markers_3d_widget.show()
                    self.preview_label.hide()
                    
                    if self.frames_data is not None and len(self.frames_data) > 0:
                        self._plot_current(0)
            except Exception as e:
                styled_message_box(
                    QMessageBox.Warning,
                    "Load Error",
                    f"Failed to load C3D file:\n{e}",
                    parent=self._main_window
                )
        else:
            self._show_file_info(path)

    def _show_file_info(self, path: Path):
        self.markers_3d_widget.hide()
        self.preview_label.show()
        
        html = f"""
        <div style='font-size:18px; font-weight:bold;'>{path.name}</div>
        <div style='font-size:12px; color:#555; margin-top:4px;'>Type: {path.suffix.upper()} file</div>
        <div style='font-size:12px; color:#666; margin-top:8px;'>Path: {path}</div>
        <div style='font-size:12px; color:#666;'>Size: {path.stat().st_size / 1024:.2f} KB</div>
        """
        
        if path.suffix.lower() in ['.txt', '.csv', '.log']:
            try:
                with open(path, 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read(500) 
                html += f"""
                <div style='font-size:11px; color:#333; margin-top:12px; background:#f5f5f5; 
                            padding:8px; border-radius:4px; font-family:monospace; white-space:pre-wrap;'>
                {content[:500]}{'...' if len(content) >= 500 else ''}
                </div>
                """
            except Exception:
                pass
        
        self.preview_label.setText(html)
    
    def _open_search_file(self):
        try:
            from .widgets.search_file_dialog import SearchFileDialog  
            dlg = SearchFileDialog(self._main_window)
            dlg.fileChosen.connect(self._open_file_from_search)
            dlg.exec()
        except Exception as e:
            pass

    def _load_studies(self):
        from ..database.db_manager import DatabaseManager
        
        try:
            db = DatabaseManager()
            studies = db.get_all_studies()
            
            self.study_combo.clear()
            self.study_combo.setPlaceholderText("Select study")
            
            for study in studies:
                date_str = study.date.strftime("%Y-%m-%d") if study.date else "No date"
                type_str = study.type_name if study.type_name else "Unknown type"
                display = f"{study.name} ({type_str} - {date_str})"
                self.study_combo.addItem(display, study.id_study)
            if hasattr(self, '_all_search_items'):
                self._refresh_search_items()
            
        except Exception as e:
            pass
    
    def _add_study(self):
        from .widgets.add_study_dialog import AddStudyDialog
        
        dialog = AddStudyDialog(self._main_window)
        dialog.studyAdded.connect(self._on_study_added)
        dialog.exec()

    def _on_study_added(self, study_id: int):
        self._load_studies()
        
        for i in range(self.study_combo.count()):
            if self.study_combo.itemData(i) == study_id:
                self.study_combo.setCurrentIndex(i)
                break
               
        try:
            if hasattr(self, 'marker_editor') and self.marker_editor:
                self.marker_editor._populate_participant_combo()
        except Exception as e:
            pass
    
    def _show_study_context_menu(self, position):
        from PySide6.QtWidgets import QMenu
        from PySide6.QtGui import QAction
        
        current_index = self.study_combo.currentIndex()
        if current_index <= 0:
            current_index = self.study_combo.currentIndex()
        if current_index < 0:
            return
        
        study_id = self.study_combo.itemData(current_index)
        if not study_id:
            return
        
        menu = QMenu(self.study_combo)
        
        edit_action = QAction("Edit Study", self.study_combo)
        edit_action.triggered.connect(lambda: self._edit_study(study_id))
        menu.addAction(edit_action)
        
        menu.addSeparator()
        
        delete_action = QAction("Delete Study", self.study_combo)
        delete_action.triggered.connect(lambda: self._delete_study(study_id))
        menu.addAction(delete_action)
        
        menu.exec(self.study_combo.mapToGlobal(position))

    def _edit_study(self, study_id: int):
        from .widgets.edit_study_dialog import EditStudyDialog
        
        dialog = EditStudyDialog(study_id, self._main_window)
        dialog.studyUpdated.connect(self._on_study_updated)
        dialog.exec()

    def _on_study_updated(self, study_id: int):
        self._load_studies()
        
        for i in range(self.study_combo.count()):
            if self.study_combo.itemData(i) == study_id:
                self.study_combo.setCurrentIndex(i)
                break
    
    def _delete_study(self, study_id: int):
        from ..database.db_manager import DatabaseManager
        
        if not study_id:
            return
        
        try:
            db = DatabaseManager()
            study = db.get_study(study_id)
            
            if not study:
                styled_message_box(
                    QMessageBox.Warning,
                    "Study Not Found",
                    "Selected study does not exist in database.",
                    parent=self._main_window
                )
                return
            
            dlg = styled_message_box(
                QMessageBox.Question,
                "Delete Study",
                f"Are you sure you want to delete study '{study.name}'?\n\nThis will remove the study record from database.",
                buttons=QMessageBox.Yes | QMessageBox.No,
                default=QMessageBox.No,
                parent=self._main_window
            )
            if dlg is not None:
                sb = dlg.standardButton(dlg.clickedButton())
                if sb == QMessageBox.Yes:
                    db.delete_study(study_id)
                    self._load_studies()
                    styled_message_box(
                        QMessageBox.Information,
                        "Study Deleted",
                        f"Study '{study.name}' has been deleted.",
                        parent=self._main_window
                    )
        
        except Exception as e:
            traceback.print_exc()
            styled_message_box(
                QMessageBox.Critical,
                "Delete Error",
                f"Failed to delete study:\n{e}",
                parent=self._main_window
            )
    def _refresh_search_items(self):
        try:
            from ..database.db_manager import DatabaseManager
            db = DatabaseManager()
            studies = db.get_all_studies()
        except Exception:
            studies = []

        items = []
        self._study_search_map.clear()

        for s in studies:
            date_str = s.date.strftime("%Y-%m-%d") if getattr(s, "date", None) else "No date"
            type_str = s.type_name if getattr(s, "type_name", None) else "Unknown type"
            display = f"{s.name} ({type_str} - {date_str})"
            items.append(display)
            self._study_search_map[display] = getattr(s, "id_study", None)

        self._study_search_model.setStringList(items)
        self._all_search_items = items

    def _on_study_completer_activated(self, text: str):
        """Handle completer selection (or Enter pressed in search).
        Selects corresponding item in study_combo if found.
        """
        if not text:
            return

        study_id = self._study_search_map.get(text)
        if study_id:
            for i in range(self.study_combo.count()):
                if self.study_combo.itemData(i) == study_id:
                    self.study_combo.setCurrentIndex(i)
                    return

        low = text.lower()
        for i in range(self.study_combo.count()):
            if low in self.study_combo.itemText(i).lower():
                self.study_combo.setCurrentIndex(i)
                return
    
   
class MainWindowLogic:
    
    def __init__(self, ui: MainWindowUI, window):
        self.ui = ui
        self.window = window
        self._setup_connections()
    
    def _setup_connections(self):
        if hasattr(self.ui, 'import_btn'):
            self.ui.import_btn.clicked.connect(self.import_file)
        
        if hasattr(self.ui, 'prev_btn'):
            self.ui.prev_btn.clicked.connect(self._prev_frame)
        if hasattr(self.ui, 'next_btn'):
            self.ui.next_btn.clicked.connect(self._next_frame)
    
    def import_file(self):
        from PySide6.QtWidgets import QFileDialog
        
        dlg = QFileDialog()
        dlg.setFileMode(QFileDialog.ExistingFile)
        dlg.setNameFilter("C3D Files (*.c3d);;All Files (*)")
        
        if dlg.exec():
            path = dlg.selectedFiles()[0]
            try:
                count = self.ui.load_frames(path)
                if count:
                    self.ui.original_file_path = path
                    self.ui.current_file_path = path
                    self.ui.is_modified = False
                    self.ui._update_save_actions()
                    self.ui._update_window_title()

                    try:
                        if hasattr(self.ui, 'study_combo'):
                            self.ui.study_combo.setCurrentIndex(-1)
                    except Exception:
                        pass

                    try:
                        me = getattr(self.ui, 'marker_editor', None)
                        if me and hasattr(me, 'participant_combo'):
                            me.participant_combo.setCurrentIndex(-1)
                    except Exception:
                        pass                    
                    
                    file_already_listed = False
                    for i in range(self.ui.file_list.count()):
                        if self.ui.file_list.item(i).text().split("\n")[0] == path:
                            self.ui.file_list.setCurrentRow(i)
                            file_already_listed = True
                            break
                    
                    if not file_already_listed:
                        self.ui.file_list.addItem(path)
                        self.ui.file_list.setCurrentRow(self.ui.file_list.count() - 1)
            except Exception as e:
                styled_message_box(QMessageBox.Warning, "Import Error", f"Failed to import file:\n{e}", parent=self.window)
    
    def _prev_frame(self):
        if hasattr(self.ui, 'time_slider') and self.ui.time_slider.isEnabled():
            current = self.ui.time_slider.value()
            if current > 0:
                self.ui.time_slider.setValue(current - 1)
    
    def _next_frame(self):
        if hasattr(self.ui, 'time_slider') and self.ui.time_slider.isEnabled():
            current = self.ui.time_slider.value()
            maximum = self.ui.time_slider.maximum()
            if current < maximum:
                self.ui.time_slider.setValue(current + 1)

    def _on_file_link_clicked(self, link: str):
        if link.endswith('.c3d'):
            try:
                count = self.load_frames(link)
                if count:
                    self.original_file_path = link
                    self.current_file_path = link
                    self.is_modified = False
                    self._update_save_actions()
                    self._update_window_title()
                    
                    styled_message_box(
                        QMessageBox.Information,
                        "File Loaded",
                        f"Loaded: {os.path.basename(link)}",
                        parent=self.window
                    )
            except Exception as e:
                styled_message_box(QMessageBox.Warning, "Load Error", f"Failed to load file:\n{e}", parent=self.window)
        else:
            self._show_file_info(Path(link))

