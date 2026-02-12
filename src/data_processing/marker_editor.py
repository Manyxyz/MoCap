import numpy as np
from typing import List, Optional, Dict, Tuple
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QListWidget, QListWidgetItem,
    QLabel, QPushButton, QLineEdit, QCheckBox, QMessageBox, QInputDialog, 
    QComboBox, QApplication, QAbstractItemView, QStyledItemDelegate, QDialog
)
from PySide6.QtCore import Qt, Signal, QItemSelection, QItemSelectionModel
from PySide6.QtGui import QFont
from ..config import ASSETS_DIR  
from PySide6.QtGui import QIcon  
from PySide6.QtCore import QSize 
from ..ui.widgets.rename_marker_dialog import RenameMarkerDialog
from ..config import MODEL_OUTPUT_KEYWORDS
from ..ui.message_box import styled_message_box

class ElideRightDelegate(QStyledItemDelegate):
    def paint(self, painter, option, index):
        option.textElideMode = Qt.ElideRight
        super().paint(painter, option, index)

class MarkerEditor(QWidget):
    
    markersChanged = Signal(list)
    markerRenamed = Signal(int, str)
    markerDeleted = Signal(int)
    markerRestored = Signal(int, object)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.marker_labels = []
        self.marker_visible = []
        self.undo_stack = []
        self.redo_stack = []
        self.main_window_ui = None
        self._setup_ui()
    
    def _get_dialog_parent(self):
        if self.main_window_ui and hasattr(self.main_window_ui, '_main_window'):
            return self.main_window_ui._main_window
        return self    

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        

        header = QLabel("Marker Editor")
        header.setStyleSheet("font-weight: bold; font-size: 14px; color: #222;")
        layout.addWidget(header)
        

        controls_layout_1 = QHBoxLayout()
        
        self.toggle_all_btn = QPushButton("Hide All")
        self.toggle_all_btn.setStyleSheet("""
            QPushButton {
                background: #3aa0ff;
                color: #fff;
                border-radius: 6px;
                padding: 4px 12px;
                font-size: 12px;
            }
            QPushButton:hover { background: #2a8fdf; }
        """)
        controls_layout_1.addWidget(self.toggle_all_btn)

        self.default_btn = QPushButton("Default")
        self.default_btn.setStyleSheet("""
            QPushButton {
                background: #28a745;
                color: #fff;
                border-radius: 6px;
                padding: 4px 12px;
                font-size: 12px;
            }
            QPushButton:hover { background: #218838; }
        """)
        self.default_btn.setToolTip("Show only default markers (from config.py)")
        controls_layout_1.addWidget(self.default_btn)

 
        self.delete_btn = QPushButton("Delete")
        self.delete_btn.setStyleSheet("""
            QPushButton {
                background: #dc3545;
                color: #fff;
                border-radius: 6px;
                padding: 4px 12px;
                font-size: 12px;
            }
            QPushButton:hover { background: #c82333; }
        """)
        self.delete_btn.setEnabled(False)
        controls_layout_1.addWidget(self.delete_btn)

        layout.addLayout(controls_layout_1)

        controls_layout_2 = QHBoxLayout()
        
        self.participant_combo = QComboBox()
        self.participant_combo.setToolTip("Select participant")
        self.participant_combo.setMinimumWidth(115)
        self.participant_combo.setMaximumWidth(115) 

        self.participant_combo.setItemDelegate(ElideRightDelegate(self.participant_combo))

        self.participant_combo.view().window().setWindowFlags(
            Qt.Popup | Qt.FramelessWindowHint | Qt.NoDropShadowWindowHint
        )
        self.participant_combo.setStyleSheet("""
            QComboBox {
                border: 2px solid #ccc;
                border-radius: 3px;
                padding: 1px 6px;
                background: white;
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

        controls_layout_2.addWidget(self.participant_combo)

        self.assign_btn = QPushButton("Assign ID")
        self.assign_btn.setToolTip("Prefix selected marker names with participant code")
        self.assign_btn.setStyleSheet("""
            QPushButton {
                background: #0066cc;
                color: #fff;
                border-radius: 6px;
                padding: 4px 10px;
                font-size: 12px;
            }
            QPushButton:hover { background: #005bb5; }
        """)
        controls_layout_2.addWidget(self.assign_btn) 
        layout.addLayout(controls_layout_2)
        

        self.marker_list = QListWidget()
        self.marker_list.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.marker_list.setStyleSheet("""
            QListWidget {
                background-color: #ffffff;
                color: #333;
                border: 2px solid #ccc;
                border-radius: 4px;
            }
            QListWidget::item {
                color: #333;
                padding: 2px;
            }
            QListWidget::item:selected {
                background: #777171;
                color: white;
            }
            QListWidget::item:hover {
                background: #e6e9ec;
            }
            QScrollBar:vertical {
                background: #f8f8f8;        
                width: 13px;
                margin: 2px;
                border: 2px solid #b8b8b8;      
            }
            QScrollBar::handle:vertical {
                background: #d0d0d0;        
                min-height: 30px;
            }
            QScrollBar::handle:vertical:hover {
                background: #b0b0b0;        
            }
            QScrollBar::add-line:vertical,
            QScrollBar::sub-line:vertical {
                height: 0px;
            }
            QScrollBar::add-page:vertical,
            QScrollBar::sub-page:vertical {
                background: transparent;
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
        layout.addWidget(self.marker_list, 1)
        

        self._add_collapsible_sections(layout)
        

        self.toggle_all_btn.clicked.connect(self._toggle_all_markers)
        self.default_btn.clicked.connect(self._show_default_markers)
        self.marker_list.itemDoubleClicked.connect(self._on_marker_double_clicked)
        self.marker_list.itemSelectionChanged.connect(self._on_selection_changed)
        self.assign_btn.clicked.connect(self._assign_selected_to_participant)
        self.delete_btn.clicked.connect(self._delete_selected_marker)

    def _populate_participant_combo(self):
        try:
            self.participant_combo.clear()
            self.participant_combo.setPlaceholderText("Select participant")

            if not hasattr(self, 'main_window_ui') or self.main_window_ui is None:
                return
            combo = getattr(self.main_window_ui, 'study_combo', None)
            if combo is None:
                return
            current_index = combo.currentIndex()
            study_id = combo.itemData(current_index)
            if not study_id:
                return

            from ..database.db_manager import DatabaseManager
            db = DatabaseManager()
            participants = db.get_study_participants(study_id)
            if not participants:
                return

            for p in participants:
                display = f"{p.code}-{p.name} {p.surname}"  
                tooltip = f"{p.code}\n{p.name} {p.surname}"  
                self.participant_combo.addItem(display, p.code)
                last_index = self.participant_combo.count() - 1 
                self.participant_combo.setItemData(last_index, tooltip, Qt.ToolTipRole)
        except Exception as e:
            pass

    def _assign_selected_to_participant(self):
        try:
            index = self.participant_combo.currentIndex()
            code = None
            if index >= 0:
                code = self.participant_combo.currentData()
                if not code:
                    txt = (self.participant_combo.currentText() or "").strip()
                    import re
                    m = re.match(r'^\s*([A-Za-z0-9_+-]+)', txt)
                    if m:
                        code = m.group(1)

            if not code:
                dialog = QInputDialog(self)
                dialog.setWindowTitle("Participant code")
                dialog.setLabelText("Enter participant code (e.g. JT01):")
                dialog.setTextValue("")
                
                dialog.setStyleSheet("""
                    QDialog {
                        background: #545c64;
                    }
                    QLabel {
                        color: #ffffff;
                        background: #545c64;
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
                ok = dialog.exec()
                code_input = dialog.textValue()
                if not ok or not code_input or not code_input.strip():
                    styled_message_box(
                        QMessageBox.Warning,
                        "No Participant",
                        "Select or enter a participant ID first.",
                        parent=self._get_dialog_parent()
                    )
                    return
                code = code_input.strip()

            selected_items = self.marker_list.selectedItems()
            if not selected_items:
                styled_message_box(
                    QMessageBox.Warning,
                    "No Selection",
                    "Select one or more markers to assign.",
                    parent=self._get_dialog_parent()
                )
                return

            sel_indices = sorted({self.marker_list.row(it) for it in selected_items if self.marker_list.row(it) >= 0})
            if not sel_indices:
                return


            conflicts = []
            ops = []
            for idx in sel_indices:
                if idx < 0 or idx >= len(self.marker_labels):
                    continue
                old_name = self.marker_labels[idx]
                base = old_name.split(':', 1)[1].strip() if ':' in old_name else old_name
                new_name = f"{code}:{base}"
                ops.append((idx, base, new_name))
                for j, lab in enumerate(self.marker_labels):
                    if j != idx and lab == new_name:
                        conflicts.append(j)

            conflicts = sorted(set([c for c in conflicts if c not in sel_indices]))

            overwrite = False
            if conflicts:
                dlg = styled_message_box(
                    QMessageBox.Question,
                    "Overwrite existing IDs",
                    f"{len(conflicts)} existing marker(s) already have the target ID prefix.\n"
                    "Do you want to overwrite those occurrences?",
                    QMessageBox.Yes | QMessageBox.No | QMessageBox.Cancel,
                    QMessageBox.Cancel,
                    parent=self._get_dialog_parent()
                )
                if dlg:
                    reply = dlg.standardButton(dlg.clickedButton())
                    if reply == QMessageBox.Cancel:
                        return
                    overwrite = (reply == QMessageBox.Yes)

            changes = []
        
            changed = 0
            if overwrite and conflicts:
                for other_idx in conflicts:
                    try:
                        old_other = self.marker_labels[other_idx]
                        base_other = old_other.split(':', 1)[1].strip() if ':' in old_other else old_other
                        
                        changes.append({
                            'index': other_idx,
                            'old_name': old_other,
                            'new_name': base_other
                        })
                        
                        self.marker_labels[other_idx] = base_other
                        self._update_marker_display(other_idx, base_other)
                        self.markerRenamed.emit(other_idx, base_other)
                        changed += 1
                    except Exception:
                        pass

            for idx, base, new_name in ops:
                old_name = self.marker_labels[idx]
                if old_name == new_name:
                    continue
                if (not overwrite) and (new_name in self.marker_labels):
                    continue
                
                changes.append({
                    'index': idx,
                    'old_name': old_name,
                    'new_name': new_name
                })
                
                self.marker_labels[idx] = new_name
                self._update_marker_display(idx, new_name)
                self.markerRenamed.emit(idx, new_name)
                changed += 1

            if changes and self.main_window_ui and hasattr(self.main_window_ui, '_undo_stack'):
                undo_action = {
                    'type': 'assign_markers',
                    'changes': changes,
                    'participant_code': code
                }
                self.main_window_ui._undo_stack.append(undo_action)
                self.main_window_ui._redo_stack.clear()

            if changed > 0:
                self.markersChanged.emit(self.marker_visible)
                styled_message_box(
                    QMessageBox.Information,
                    "Assigned",
                    f"Assigned {changed} marker(s) to {code}.",
                    parent=self._get_dialog_parent()
                )
            else:
                styled_message_box(
                    QMessageBox.Information,
                    "No Changes",
                    "No marker names were changed.",
                    parent=self._get_dialog_parent()
                )
        except Exception as e:
            
            styled_message_box(
                QMessageBox.Critical,
                "Assign Error",
                f"Failed to assign markers:\n{e}",
                parent=self._get_dialog_parent()
            )
    
    def _add_collapsible_sections(self, parent_layout):
        self.model_outputs_section = self._create_collapsible_section("Model Outputs")
        parent_layout.addWidget(self.model_outputs_section)
        
        self.analog_channels_section = self._create_collapsible_section("Analog Channels")
        parent_layout.addWidget(self.analog_channels_section)

    def _create_collapsible_section(self, title):  
        container = QWidget()
        container_layout = QVBoxLayout(container)
        container_layout.setContentsMargins(0, 4, 0, 4)
        container_layout.setSpacing(0)
        
        header_btn = QPushButton(f"  {title}") 
        
        icon_collapsed_path = ASSETS_DIR / "drop_right.svg"
        icon_expanded_path = ASSETS_DIR  / "drop_down.svg"
        
        if icon_collapsed_path.exists():
            header_btn.setIcon(QIcon(str(icon_collapsed_path)))
            header_btn.setIconSize(QSize(10, 10)) 
        
        header_btn.setStyleSheet("""
            QPushButton {
                text-align: left;
                padding: 6px 8px;
                padding-left: 6px;  
                background: #f0f0f0;
                border: 1px solid #ddd;
                border-radius: 4px;
                font-weight: bold;
                color: #333;
            }
            QPushButton:hover {
                background: #e0e0e0;
            }
        """)
        
        content_list = QListWidget()
        content_list.setStyleSheet("""
            QListWidget {
                background: transparent;
                border: none;
                color: #666;
                font-size: 11px;
            }
            QListWidget::item {
                padding: 2px 12px;
                border: none;
            }
            QListWidget::item:hover {
                background: #f5f5f5;
            }
        """)
        content_list.setMaximumHeight(200)
        content_list.hide()
        
        def toggle():
            is_visible = content_list.isVisible()
            content_list.setVisible(not is_visible)
            
            if is_visible:
                if icon_collapsed_path.exists():
                    header_btn.setIcon(QIcon(str(icon_collapsed_path)))
            else:
                if icon_expanded_path.exists():
                    header_btn.setIcon(QIcon(str(icon_expanded_path)))
        
        header_btn.clicked.connect(toggle)
        
        container_layout.addWidget(header_btn)
        container_layout.addWidget(content_list)
        
        container._header = header_btn
        container._content = content_list
        container._title = title
        container._icon_collapsed_path = icon_collapsed_path  
        container._icon_expanded_path = icon_expanded_path
        
        return container
    
    def set_markers(self, labels: List[str], visible: Optional[List[bool]] = None):
        self.marker_labels = list(labels) if labels else []
        self.marker_visible = list(visible) if visible else [True] * len(self.marker_labels)
        
        while len(self.marker_visible) < len(self.marker_labels):
            self.marker_visible.append(True)
        
        self._populate_marker_list()
        self._update_toggle_button_text()
    
    def _populate_marker_list(self):
        self.marker_list.clear()
        
        if not self.marker_labels:
            return
        
        checkbox_style = ("""
            QCheckBox {
                spacing: 10px;
                margin: 2px;
            }
            QCheckBox::indicator {
                width: 14px;
                height: 14px;
                border: 2px solid #3aa0ff;
                background: #ffffff;
            }
            QCheckBox::indicator:checked {
                background: #3aa0ff;
            }
        """)
        
        for i, label in enumerate(self.marker_labels):
            item = QListWidgetItem()
            widget = QWidget()
            row_layout = QHBoxLayout(widget)
            row_layout.setContentsMargins(6, 2, 6, 2)
            
            checkbox = QCheckBox()
            checkbox.setChecked(self.marker_visible[i] if i < len(self.marker_visible) else True)
            checkbox.setStyleSheet(checkbox_style)
            
            label_widget = QLabel(label)
            label_widget.setStyleSheet("color: #222;")
            
            if self._is_model_output_label(label):
                label_widget.setStyleSheet("color: #888; font-style: italic;")
                label_widget.setToolTip("Model output - not a physical marker")
            
            row_layout.addWidget(checkbox)
            row_layout.addWidget(label_widget)
            row_layout.addStretch()
            
            item.setSizeHint(widget.sizeHint())
            item.setFlags(item.flags() | Qt.ItemIsSelectable | Qt.ItemIsEnabled)
            self.marker_list.addItem(item)
            self.marker_list.setItemWidget(item, widget)
            
            checkbox.stateChanged.connect(self._make_checkbox_handler(i))
    
    def _make_checkbox_handler(self, index: int):
        def on_checkbox_changed(state):
            if index < len(self.marker_visible):
                self.marker_visible[index] = (state == 2)
                self._update_toggle_button_text()
                self.markersChanged.emit(self.marker_visible)
        return on_checkbox_changed
    
    def _toggle_all_markers(self):
        if not self.marker_visible:
            return
        
        all_visible = all(self.marker_visible)
        new_state = not all_visible
        
        for i in range(len(self.marker_visible)):
            self.marker_visible[i] = new_state
        
        for i in range(self.marker_list.count()):
            item = self.marker_list.item(i)
            widget = self.marker_list.itemWidget(item)
            if widget:
                checkbox = widget.findChild(QCheckBox)
                if checkbox:
                    checkbox.blockSignals(True)
                    checkbox.setChecked(new_state)
                    checkbox.blockSignals(False)
        
        self._update_toggle_button_text()
        self.markersChanged.emit(self.marker_visible)
    
    def _update_toggle_button_text(self):
        if not self.marker_visible:
            return
        
        all_visible = all(self.marker_visible)
        self.toggle_all_btn.setText("Hide All" if all_visible else "Show All")

    def _show_default_markers(self):
        if not self.marker_visible or not self.marker_labels:
            return
        
        from ..config import DEFAULT_VISIBLE_MARKERS
        
        changed_count = 0
        
        for i, label in enumerate(self.marker_labels):
            clean_label = label.split(':')[-1].strip().upper()
            
            should_be_visible = clean_label in DEFAULT_VISIBLE_MARKERS
            
            if self.marker_visible[i] != should_be_visible:
                self.marker_visible[i] = should_be_visible
                changed_count += 1
        
        for i in range(self.marker_list.count()):
            item = self.marker_list.item(i)
            widget = self.marker_list.itemWidget(item)
            if widget and i < len(self.marker_visible):
                checkbox = widget.findChild(QCheckBox)
                if checkbox:
                    checkbox.blockSignals(True)
                    checkbox.setChecked(self.marker_visible[i])
                    checkbox.blockSignals(False)
        
        self._update_toggle_button_text()
        
        self.markersChanged.emit(self.marker_visible)
    
    def _on_marker_double_clicked(self, item: QListWidgetItem):
        index = self.marker_list.row(item)
        if 0 <= index < len(self.marker_labels):
            self._rename_marker(index)
    
    def _rename_marker(self, index: int):
        if not (0 <= index < len(self.marker_labels)):
            return
        
        from ..ui.widgets.rename_marker_dialog import RenameMarkerDialog
        
        current_name = self.marker_labels[index]
        
        main_win = None
        if self.main_window_ui and hasattr(self.main_window_ui, '_main_window'):
            main_win = self.main_window_ui._main_window
        
        dialog = RenameMarkerDialog(
            current_name=current_name,
            existing_names=self.marker_labels,
            parent=self,
            main_window=main_win 
        )
        
        if dialog.exec() == QDialog.Accepted:
            new_name = dialog.get_new_name()
            
            if new_name:
                old_name = self.marker_labels[index]
                

                if self.main_window_ui and hasattr(self.main_window_ui, '_undo_stack'):
                    undo_action = {
                        'type': 'rename_marker',
                        'index': index,
                        'old_name': old_name,
                        'new_name': new_name
                    }
                    self.main_window_ui._undo_stack.append(undo_action)
                    self.main_window_ui._redo_stack.clear()
                

                self.marker_labels[index] = new_name
                self._update_marker_display(index, new_name)
                self.markerRenamed.emit(index, new_name)
                
                styled_message_box(
                    QMessageBox.Information,
                    "Success",
                    f"Marker '{old_name}' renamed to '{new_name}'",
                    parent=self._get_dialog_parent()
                )
    
    def _update_marker_display(self, index: int, new_name: str):
        if not (0 <= index < self.marker_list.count()):
            return
        
        item = self.marker_list.item(index)
        widget = self.marker_list.itemWidget(item)
        if widget:
            label_widget = widget.findChild(QLabel)
            if label_widget:
                label_widget.setText(new_name)
                
                if self._is_model_output_label(new_name):
                    label_widget.setStyleSheet("color: #888; font-style: italic;")
                    label_widget.setToolTip("Model output - not a physical marker")
                else:
                    label_widget.setStyleSheet("color: #222;")
                    label_widget.setToolTip("")
    
    def _is_model_output_label(self, label: str) -> bool:
        if not label:
            return False
        
        lab = str(label).strip().lower()
        
        if ':' in lab:
            left, right = lab.split(':', 1)
            if left.strip().startswith(('actor', 'model', 'output')):
                return any(k in right for k in MODEL_OUTPUT_KEYWORDS)
            return False
        
        return any(k in lab for k in MODEL_OUTPUT_KEYWORDS)
    
    def get_marker_labels(self) -> List[str]:
        return list(self.marker_labels)
    
    def get_marker_visibility(self) -> List[bool]:
        return list(self.marker_visible)
    
    def export_marker_mapping(self) -> Dict[str, str]:
        return {label: label for label in self.marker_labels}

    def _delete_selected_marker(self):
        selected = self.marker_list.selectedItems()
        if not selected:
            return

        sel_indices = sorted({self.marker_list.row(it) for it in selected if self.marker_list.row(it) >= 0})
        if not sel_indices:
            return

        preview = ", ".join([self.marker_labels[i] for i in sel_indices[:6]])
        more = "" if len(sel_indices) <= 6 else f", ... (+{len(sel_indices)-6})"

        dlg = styled_message_box(
            QMessageBox.Question,
            "Delete Marker(s)",
            f"Delete {len(sel_indices)} marker(s): {preview}{more}?\n\nYou can undo with Ctrl+Z.",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
            parent=self._get_dialog_parent()
        )

        if dlg:
            reply = dlg.standardButton(dlg.clickedButton())
            if reply != QMessageBox.Yes:
                return


        items = []
        for idx in sel_indices:
            if not (0 <= idx < len(self.marker_labels)):
                continue
            marker_data = None
            try:
                if self.main_window_ui and hasattr(self.main_window_ui, 'frames_data'):
                    frames_data = self.main_window_ui.frames_data
                    if frames_data is not None and 0 <= idx < frames_data.shape[1]:
                        marker_data = frames_data[:, idx, :].copy()
            except Exception:
                marker_data = None
            items.append({
                'index': idx,
                'label': self.marker_labels[idx],
                'visible': self.marker_visible[idx] if idx < len(self.marker_visible) else True,
                'data': marker_data
            })

        n_deleted = len(sel_indices)

        if self.main_window_ui and hasattr(self.main_window_ui, '_undo_stack'):
            undo_action = {
                'type': 'delete_marker',
                'items': items
            }
            self.main_window_ui._undo_stack.append(undo_action)
            self.main_window_ui._redo_stack.clear()
        else:
            self.undo_stack.append({'type': 'delete_multi', 'items': items})
            self.redo_stack.clear()


        for idx in sorted(sel_indices, reverse=True):
            if 0 <= idx < len(self.marker_labels):
                del self.marker_labels[idx]
                if idx < len(self.marker_visible):
                    del self.marker_visible[idx]
                try:
                    self.markerDeleted.emit(idx)
                except Exception:
                    pass

        self._populate_marker_list()
        self.markersChanged.emit(self.marker_visible)

        try:
            styled_message_box(
                QMessageBox.Information,
                "Deleted",
                f"Deleted {n_deleted} marker(s).",
                parent=self._get_dialog_parent()
            )
        except Exception:
            pass

    def undo(self) -> bool:
        if not self.undo_stack:
            return False

        action = self.undo_stack.pop()

        if action['type'] == 'delete':

            index = action['index']
            label = action['label']
            visible = action['visible']
            marker_data = action.get('data')
            self.marker_labels.insert(index, label)
            self.marker_visible.insert(index, visible)
            if marker_data is not None:
                self.markerRestored.emit(index, marker_data)
        elif action['type'] == 'delete_multi':

            items = action.get('items', [])
            for it in sorted(items, key=lambda x: x['index']):
                idx = it['index']
                label = it['label']
                visible = it.get('visible', True)
                data = it.get('data')
                idx = max(0, min(idx, len(self.marker_labels)))
                self.marker_labels.insert(idx, label)
                self.marker_visible.insert(idx, visible)
                if data is not None:
                    try:
                        self.markerRestored.emit(idx, data)
                    except Exception:
                        pass
        else:
            self.undo_stack.append(action)
            return False

        self._populate_marker_list()
        self.markersChanged.emit(self.marker_visible)
        self.redo_stack.append(action)
        return True

    def redo(self) -> bool:
        if not self.redo_stack:
            return False

        action = self.redo_stack.pop()

        if action['type'] == 'delete':
            index = action['index']
            if 0 <= index < len(self.marker_labels):
                del self.marker_labels[index]
                if index < len(self.marker_visible):
                    del self.marker_visible[index]
                try:
                    self.markerDeleted.emit(index)
                except Exception:
                    pass
        elif action['type'] == 'delete_multi':
            items = action.get('items', [])
            indices = sorted({it['index'] for it in items if isinstance(it.get('index'), int)}, reverse=True)
            for idx in indices:
                if 0 <= idx < len(self.marker_labels):
                    del self.marker_labels[idx]
                    if idx < len(self.marker_visible):
                        del self.marker_visible[idx]
                    try:
                        self.markerDeleted.emit(idx)
                    except Exception:
                        pass
        else:
            self.redo_stack.append(action)
            return False

        self._populate_marker_list()
        self.markersChanged.emit(self.marker_visible)
        self.undo_stack.append(action)
        return True
    
    def _on_selection_changed(self):
        selected = self.marker_list.selectedItems()
        self.delete_btn.setEnabled(len(selected) > 0)

    def set_model_outputs(self, labels: List[str]):
        if not hasattr(self, 'model_outputs_section'):
            return
        
        content = self.model_outputs_section._content
        content.clear()
        
        if not labels:
            content.addItem("(no model outputs)")
            return
        
        categories = {
            'Angles': [],
            'Forces': [],
            'Moments': [],
            'Powers': [],
            'Other': []
        }
        
        for label in labels:
            lab_lower = label.lower()
            if 'angle' in lab_lower:
                categories['Angles'].append(label)
            elif 'force' in lab_lower or 'grf' in lab_lower or 'reaction' in lab_lower:
                categories['Forces'].append(label)
            elif 'moment' in lab_lower or 'momen' in lab_lower:
                categories['Moments'].append(label)
            elif 'power' in lab_lower:
                categories['Powers'].append(label)
            else:
                categories['Other'].append(label)
        
        for category, items in categories.items():
            if items:
                header_item = QListWidgetItem(f"  {category}")
                header_item.setFlags(Qt.NoItemFlags)
                font = header_item.font()
                font.setBold(True)
                header_item.setFont(font)
                content.addItem(header_item)
                
                for item in sorted(items):
                    list_item = QListWidgetItem(f"    • {item}")
                    list_item.setFlags(Qt.NoItemFlags)
                    content.addItem(list_item)

    def set_analog_channels(self, labels: List[str]):
        if not hasattr(self, 'analog_channels_section'):
            return
        
        content = self.analog_channels_section._content
        content.clear()
        
        if not labels:
            content.addItem("(no analog channels)")
            return
        
        force_channels = []
        voltage_channels = []
        other_channels = []
        
        for label in labels:
            lab_lower = label.lower()
            if any(x in lab_lower for x in ['fx', 'fy', 'fz', 'mx', 'my', 'mz']):
                force_channels.append(label)
            elif 'voltage' in lab_lower:
                voltage_channels.append(label)
            else:
                other_channels.append(label)
        
        if force_channels:
            header = QListWidgetItem("  Force Plates")
            header.setFlags(Qt.NoItemFlags)
            font = header.font()
            font.setBold(True)
            header.setFont(font)
            content.addItem(header)
            
            for ch in sorted(force_channels):
                item = QListWidgetItem(f"    • {ch}")
                item.setFlags(Qt.NoItemFlags)
                content.addItem(item)
        
        if voltage_channels:
            header = QListWidgetItem("  Voltages")
            header.setFlags(Qt.NoItemFlags)
            font = header.font()
            font.setBold(True)
            header.setFont(font)
            content.addItem(header)
            
            for ch in sorted(voltage_channels):
                item = QListWidgetItem(f"    • {ch}")
                item.setFlags(Qt.NoItemFlags)
                content.addItem(item)
        
        if other_channels:
            header = QListWidgetItem("  Other")
            header.setFlags(Qt.NoItemFlags)
            font = header.font()
            font.setBold(True)
            header.setFont(font)
            content.addItem(header)
            
            for ch in sorted(other_channels):
                item = QListWidgetItem(f"    • {ch}")
                item.setFlags(Qt.NoItemFlags)
                content.addItem(item)