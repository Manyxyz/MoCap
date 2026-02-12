from pathlib import Path
from typing import Optional

from PySide6.QtWidgets import (
    QTreeWidget, QTreeWidgetItem, QWidget, QVBoxLayout, 
    QHBoxLayout, QLabel, QPushButton, QMenu, QMessageBox
)
from PySide6.QtCore import Qt, Signal, QSize
from PySide6.QtGui import QIcon, QAction
from ...config import ASSETS_DIR
from ..message_box import styled_message_box

class FileTreeWidget(QWidget):
    
    fileSelected = Signal(str)
    
    def __init__(self, parent=None, main_window_ui=None):
        super().__init__(parent)
        self._current_root = None
        self._undo_stack = [] 
        self._redo_stack = []  
        self.main_window_ui = main_window_ui
        self._setup_ui()

    def _get_message_parent(self):
        if self.main_window_ui and hasattr(self.main_window_ui, '_main_window'):
            return self.main_window_ui._main_window
        return self
    
    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
        
        header_layout = QHBoxLayout()
        
        self.study_label = QLabel("No study selected")
        self.study_label.setStyleSheet("""
            font-weight: bold;
            font-size: 14px;
            border: 2px solid #ccc;
            border-radius: 3px;  
            color: #000000;
        """)
        header_layout.addWidget(self.study_label)
        
        self.refresh_btn = QPushButton()
        self.refresh_btn.setIcon(QIcon(str(ASSETS_DIR / "refresh.svg")))
        self.refresh_btn.setFixedSize(28, 28)
        self.refresh_btn.setIconSize(QSize(20, 20)) 
        self.refresh_btn.setToolTip("Refresh folder tree")  
        self.refresh_btn.setStyleSheet("""
            QPushButton {
                background: #f0f0f0;
                border: 2px solid #ccc;
                border-radius: 3px;
                color: #000000;
            }
            QPushButton:hover { 
                background: #e0e0e0;
            }
        """)
        self.refresh_btn.clicked.connect(self._refresh_tree)
        header_layout.addWidget(self.refresh_btn)
        
        layout.addLayout(header_layout)
        
        self.tree = QTreeWidget()
        self.tree.setHeaderHidden(True)
        self.tree.setIndentation(10)
        self.tree.setStyleSheet("""
            QTreeWidget {
                padding: 2px;
                background: white;  
                border: 2px solid #ddd;
                border-radius: 4px;
                font-size: 13px;
                color: #222; 
            }
            QTreeWidget::item {
                padding: 2px;
                border: none;
                color: #222; 
            }
            QTreeWidget:focus { 
                outline: none; 
            }
            QTreeWidget::item:focus { 
                outline: none; 
            }
            QTreeWidget::item:selected {
                background: #3aa0ff;
                color: #fff;
                outline: none;
            }
            QTreeWidget::item:hover {
                background: #e8f4ff;
                color: #222;  
            }
            QTreeWidget::branch {
                background: white;  
            }
            QScrollBar:vertical {
                background: #f8f8f8;        
                width: 9px;
                margin: 0px;
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
        """)
        
        self.tree.itemClicked.connect(self._on_item_clicked)
        self.tree.setContextMenuPolicy(Qt.CustomContextMenu)
        self.tree.customContextMenuRequested.connect(self._show_context_menu)
        
        layout.addWidget(self.tree)
    
    def load_folder(self, folder_path: str, study_name: str = ""):
        self.tree.clear()
        self._current_root = Path(folder_path)
        
        if not self._current_root.exists():
            self.study_label.setText(f"{study_name} (folder not found)")
            return
        
        self.study_label.setText(study_name or self._current_root.name)
        
        root_item = QTreeWidgetItem([f"📁 {self._current_root.name}"])
        root_item.setData(0, Qt.UserRole, str(self._current_root))
        root_item.setData(0, Qt.UserRole + 1, "folder")
        self.tree.addTopLevelItem(root_item)
        
        self._populate_tree_item(root_item, self._current_root)
        
        root_item.setExpanded(True)
    
    def _populate_tree_item(self, parent_item: QTreeWidgetItem, folder_path: Path):
        try:
            all_items = list(folder_path.iterdir())
            
            all_items = [item for item in all_items if not item.name.startswith('.')]
            
            def sort_key(item):
                """
                Sort key:
                - Folders first (key = (0, '', name))
                - C3D files second (key = (1, '.c3d', name))
                - Other files grouped by extension (key = (2, extension, name))
                Within each group, sort alphabetically by name (case-insensitive)
                """
                if item.is_dir():
                    return (0, '', item.name.lower())
                elif item.suffix.lower() == '.c3d':
                    return (1, '.c3d', item.name.lower())
                else:
                    return (2, item.suffix.lower(), item.name.lower())
            
            items = sorted(all_items, key=sort_key)
            
            for item in items:
                if item.is_dir():
                    child = QTreeWidgetItem([f"📁 {item.name}"])
                    child.setData(0, Qt.UserRole, str(item))
                    child.setData(0, Qt.UserRole + 1, "folder")
                    parent_item.addChild(child)
                    
                    if self._get_depth(child) < 5:
                        self._populate_tree_item(child, item)
                else:
                    icon = self._get_file_icon(item.suffix.lower())
                    child = QTreeWidgetItem([f"{icon} {item.name}"])
                    child.setData(0, Qt.UserRole, str(item))
                    child.setData(0, Qt.UserRole + 1, "file")
                    child.setData(0, Qt.UserRole + 2, item.suffix.lower())
                    parent_item.addChild(child)
        
        except PermissionError:
            pass
    
    def _get_depth(self, item: QTreeWidgetItem) -> int:
        depth = 0
        while item.parent():
            depth += 1
            item = item.parent()
        return depth
    
    def _get_file_icon(self, extension: str) -> str:
        icons = {
            '.c3d': '📊',
            '.txt': '📝',
            '.csv': '📋',
            '.xlsx': '📗',
            '.xls': '📗',
            '.pdf': '📕',
            '.jpg': '🖼️',
            '.jpeg': '🖼️',
            '.png': '🖼️',
            '.gif': '🖼️',
            '.mp4': '🎥',
            '.avi': '🎥',
            '.mov': '🎥',
            '.zip': '📦',
            '.rar': '📦',
            '.7z': '📦',
            '.py': '🐍',
            '.mat': '🔬',
        }
        return icons.get(extension, '📄')
    
    def _on_item_clicked(self, item: QTreeWidgetItem, column: int):
        item_type = item.data(0, Qt.UserRole + 1)
        file_path = item.data(0, Qt.UserRole)
        
        if item_type == "file":

            self.fileSelected.emit(file_path)
    
    def _refresh_tree(self):
        if self._current_root and self._current_root.exists():
            expanded_paths = self._get_expanded_paths()
            
            study_name = self.study_label.text()
            self.load_folder(str(self._current_root), study_name)
            
            self._restore_expanded_paths(expanded_paths)

    def select_file(self, file_path: str) -> bool:
        """Programmatically select and focus the tree item matching file_path.
        Expands parents and scrolls to the item. Returns True if found/selected.
        """
        if not file_path:
            return False

        target = str(file_path)

        def traverse(item: QTreeWidgetItem) -> QTreeWidgetItem | None:
            try:
                data = item.data(0, Qt.UserRole)
                if data == target:
                    return item
            except Exception:
                pass
            for i in range(item.childCount()):
                found = traverse(item.child(i))
                if found:
                    return found
            return None

        for i in range(self.tree.topLevelItemCount()):
            top = self.tree.topLevelItem(i)
            found = traverse(top)
            if found:
                parent = found.parent()
                while parent:
                    parent.setExpanded(True)
                    parent = parent.parent()
                self.tree.setCurrentItem(found)
                self.tree.scrollToItem(found)
                self.tree.setFocus()
                return True
        return False
    
    def _get_expanded_paths(self) -> set:
        expanded = set()
        
        def traverse(item):
            if item.isExpanded():
                expanded.add(item.data(0, Qt.UserRole))
            for i in range(item.childCount()):
                traverse(item.child(i))
        
        for i in range(self.tree.topLevelItemCount()):
            traverse(self.tree.topLevelItem(i))
        
        return expanded
    
    def _restore_expanded_paths(self, expanded_paths: set):
        def traverse(item):
            if item.data(0, Qt.UserRole) in expanded_paths:
                item.setExpanded(True)
            for i in range(item.childCount()):
                traverse(item.child(i))
        
        for i in range(self.tree.topLevelItemCount()):
            traverse(self.tree.topLevelItem(i))
    
    def _show_context_menu(self, position):
        item = self.tree.itemAt(position)
        if not item:
            return
        
        item_type = item.data(0, Qt.UserRole + 1)
        file_path = item.data(0, Qt.UserRole)
        
        menu = QMenu(self)
        
        if item_type == "file":
            open_action = QAction("Open", self)
            open_action.triggered.connect(lambda: self.fileSelected.emit(file_path))
            menu.addAction(open_action)
            
            menu.addSeparator()

            delete_action = QAction("Delete File", self)
            delete_action.triggered.connect(lambda: self._delete_file(file_path))
            menu.addAction(delete_action)
            
            menu.addSeparator()
            
            show_action = QAction("Show in Explorer", self)
            show_action.triggered.connect(lambda: self._show_in_explorer(file_path))
            menu.addAction(show_action)
        
        elif item_type == "folder":
            expand_action = QAction("Expand All", self)
            expand_action.triggered.connect(lambda: item.setExpanded(True))
            menu.addAction(expand_action)
            
            collapse_action = QAction("Collapse All", self)
            collapse_action.triggered.connect(lambda: item.setExpanded(False))
            menu.addAction(collapse_action)

            menu.addSeparator()
        
            import_action = QAction("Import C3D file...", self)
            import_action.triggered.connect(lambda: self._import_c3d_to_folder(file_path))
            menu.addAction(import_action)
            
            menu.addSeparator()
            
            show_action = QAction("Show in Explorer", self)
            show_action.triggered.connect(lambda: self._show_in_explorer(file_path))
            menu.addAction(show_action)
        
        menu.exec(self.tree.mapToGlobal(position))

    def _delete_file(self, file_path: str):
        from PySide6.QtWidgets import QMessageBox
        from pathlib import Path
        
        path = Path(file_path)
        
        if not path.exists():
            styled_message_box(
                QMessageBox.Warning,
                "File Not Found",
                f"File does not exist:\n{path.name}",
                parent=self._get_message_parent()
            )
            return
        
        msg_box = styled_message_box(
            QMessageBox.Question,
            "Delete File",
            f"Delete file '{path.name}'?\n\nThis action can be undone with Ctrl+Z.",
            buttons=QMessageBox.Yes | QMessageBox.No,
            default=QMessageBox.No,
            parent=self._get_message_parent()
        )
        
        if msg_box.standardButton(msg_box.clickedButton()) != QMessageBox.Yes:
            return
        
        try:
            file_backup = None
            db_record = None
            
            if path.suffix.lower() == '.c3d':
                try:
                    from ...database.db_manager import DatabaseManager
                    db = DatabaseManager()
                    
                    all_files = db.get_all_files()
                    for f in all_files:
                        if f.file_path == str(path):
                            db_record = {
                                'id': f.id_file,
                                'name': f.name,
                                'path': f.file_path,
                                'study_id': f.study_id
                            }
                            break
                    
                    if db_record:
                        db.delete_file(db_record['id'])
                except Exception as e:
                    pass
            
            try:
                if path.stat().st_size < 50 * 1024 * 1024:
                    with open(path, 'rb') as f:
                        file_backup = f.read()
            except Exception:
                file_backup = None
            
            path.unlink()
            
            if self.main_window_ui and hasattr(self.main_window_ui, '_undo_stack'):
                undo_action = {
                    'type': 'delete_file',
                    'path': str(path),
                    'backup': file_backup,
                    'db_record': db_record,
                    'is_c3d': path.suffix.lower() == '.c3d'
                }
                self.main_window_ui._undo_stack.append(undo_action)
                self.main_window_ui._redo_stack.clear()
            else:
                pass
            
            self._refresh_tree()
            
            styled_message_box(
                QMessageBox.Information,
                "File Deleted",
                f"File '{path.name}' deleted successfully.\n\nPress Ctrl+Z to undo.",
                parent=self._get_message_parent()
            )
            
        except Exception as e:
            import traceback
            traceback.print_exc()
            styled_message_box(
                QMessageBox.Critical,
                "Delete Error",
                f"Failed to delete file:\n{e}",
                parent=self._get_message_parent()
            )

    def _import_c3d_to_folder(self, folder_path: str):
        from PySide6.QtWidgets import QFileDialog, QMessageBox
        from pathlib import Path
        import shutil
        
        target_folder = Path(folder_path)
        
        if not target_folder.exists():
            styled_message_box(
                QMessageBox.Warning,
                "Folder Not Found",
                f"Target folder does not exist:\n{folder_path}",
                parent=self._get_message_parent()
            )
            return
        
        dlg = QFileDialog(self)
        dlg.setFileMode(QFileDialog.ExistingFile)
        dlg.setNameFilter("C3D Files (*.c3d *.C3D);;All Files (*)")
        dlg.setWindowTitle("Select C3D file to import")
        
        if not dlg.exec():
            return
        
        source_file = Path(dlg.selectedFiles()[0])
        
        if not source_file.exists():
            styled_message_box(
                QMessageBox.Warning,
                "File Not Found",
                f"Selected file does not exist:\n{source_file}",
                parent=self._get_message_parent()
            )
            return
        
        target_file = target_folder / source_file.name
        
        if target_file.exists():
            msg_box = styled_message_box(
                QMessageBox.Question,
                "File Exists",
                f"File '{source_file.name}' already exists in target folder.\n\nOverwrite?",
                buttons=QMessageBox.Yes | QMessageBox.No,
                default=QMessageBox.No,
                parent=self._get_message_parent()
            )
            if msg_box.standardButton(msg_box.clickedButton()) != QMessageBox.Yes:
                return
        
        try:
            shutil.copy2(source_file, target_file)
            
            db_record = None
            study_id = None
            
            try:
                from ...database.db_manager import DatabaseManager
                from ...database.models import File
                
                db = DatabaseManager()

                studies = db.get_all_studies()
                
                for study in studies:
                    if study.path and Path(study.path) == target_folder:
                        study_id = study.id_study
                        break
                
                if not study_id:
                    for study in studies:
                        if study.path:
                            try:
                                if target_folder.is_relative_to(Path(study.path)):
                                    study_id = study.id_study
                                    break
                            except ValueError:
                                continue
                
                if study_id:
                    new_file = File(
                        name=target_file.name,
                        file_path=str(target_file),
                        study_id=study_id
                    )
                    file_id = db.add_file(new_file)
                    
                    db_record = {
                        'id': file_id,
                        'name': target_file.name,
                        'path': str(target_file),
                        'study_id': study_id
                    }
                else:
                    styled_message_box(
                        QMessageBox.Warning,
                        "Study Not Found",
                        f"Could not find associated study for folder:\n{target_folder}\n\n"
                        f"File imported but not added to database.",
                        parent=self._get_message_parent()
                    )
            
            except Exception as e:
                pass
            
            if self.main_window_ui and hasattr(self.main_window_ui, '_undo_stack'):
                undo_action = {
                    'type': 'import_file',
                    'source_path': str(source_file),
                    'target_path': str(target_file),
                    'db_record': db_record,
                    'was_copied': True
                }
                self.main_window_ui._undo_stack.append(undo_action)
                self.main_window_ui._redo_stack.clear()
            
            self._refresh_tree()
            
            styled_message_box(
                QMessageBox.Information,
                "Import Successful",
                f"File '{source_file.name}' imported successfully!\n\n"
                f"Location: {target_folder.name}/{target_file.name}\n\n"
                f"Press Ctrl+Z to undo.",
                parent=self._get_message_parent()
            )
            
        except Exception as e:
            import traceback
            traceback.print_exc()
            styled_message_box(
                QMessageBox.Critical,
                "Import Error",
                f"Failed to import file:\n{e}",
                parent=self._get_message_parent()
            )

    
    def _show_in_explorer(self, path: str):
        import sys
        import subprocess
        
        path_obj = Path(path)
        
        if sys.platform == 'win32':
            if path_obj.is_file():
                subprocess.run(['explorer', '/select,', str(path_obj)])
            else:
                subprocess.run(['explorer', str(path_obj)])
        elif sys.platform == 'darwin':
            subprocess.run(['open', '-R' if path_obj.is_file() else '', str(path_obj)])
        else:
            subprocess.run(['xdg-open', str(path_obj.parent if path_obj.is_file() else path_obj)])
    
    def clear(self):
        self.tree.clear()
        self._current_root = None
        self.study_label.setText("No study selected")
    
