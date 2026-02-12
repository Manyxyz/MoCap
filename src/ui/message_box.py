from PySide6.QtWidgets import QMessageBox


def styled_message_box(icon, title: str, text: str, buttons=None, default=None, parent=None):
    dlg = QMessageBox(parent)
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
        QMessageBox QLabel { color: #ffffff; background: #545c64;}
        QLabel#qt_msgboxex_icon_label {
            background: #545c64;
        }
        QPushButton {
            color: #ffffff;
            background: #545c64;
        }          
    """)

    dlg.exec()
    return dlg