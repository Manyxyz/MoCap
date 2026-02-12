import sys
import logging
from pathlib import Path
from PySide6.QtWidgets import QApplication, QMainWindow

from .config import MIN_WINDOW_WIDTH, MIN_WINDOW_HEIGHT
from .ui.main_window import MainWindowUI, MainWindowLogic

class MainWindow(QMainWindow):
    
    def __init__(self):
        super().__init__()
        self.setWindowTitle("MoCap-App")
        self.setMinimumSize(MIN_WINDOW_WIDTH, MIN_WINDOW_HEIGHT)
    
        self.ui = MainWindowUI()
        self.ui.setup_ui(self)
        
        self.logic = MainWindowLogic(self.ui, self)
        

def main():
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())

if __name__ == '__main__':
    main()