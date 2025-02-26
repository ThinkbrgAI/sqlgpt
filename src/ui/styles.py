DARK_THEME = """
QMainWindow, QDialog {
    background-color: #2b2b2b;
    color: #ffffff;
}

QWidget {
    background-color: #2b2b2b;
    color: #ffffff;
}

QPushButton {
    background-color: #3d3d3d;
    border: 1px solid #555555;
    border-radius: 4px;
    color: #ffffff;
    padding: 5px 15px;
}

QPushButton:hover {
    background-color: #4d4d4d;
}

QPushButton:pressed {
    background-color: #555555;
}

QLineEdit, QTextEdit, QSpinBox, QComboBox {
    background-color: #3d3d3d;
    border: 1px solid #555555;
    border-radius: 4px;
    color: #ffffff;
    padding: 5px;
}

QTableWidget {
    background-color: #2b2b2b;
    alternate-background-color: #323232;
    border: 1px solid #555555;
    color: #ffffff;
    gridline-color: #555555;
}

QTableWidget::item:selected {
    background-color: #4a4a4a;
}

QHeaderView::section {
    background-color: #3d3d3d;
    color: #ffffff;
    padding: 5px;
    border: 1px solid #555555;
}

QProgressBar {
    border: 1px solid #555555;
    border-radius: 4px;
    text-align: center;
    color: #ffffff;
}

QProgressBar::chunk {
    background-color: #3daee9;
}

QLabel {
    color: #ffffff;
}

QMenuBar {
    background-color: #2b2b2b;
    color: #ffffff;
}

QMenuBar::item:selected {
    background-color: #3d3d3d;
}

QMenu {
    background-color: #2b2b2b;
    color: #ffffff;
    border: 1px solid #555555;
}

QMenu::item:selected {
    background-color: #3d3d3d;
}

QScrollBar:vertical {
    border: none;
    background-color: #2b2b2b;
    width: 10px;
    margin: 0;
}

QScrollBar::handle:vertical {
    background-color: #555555;
    min-height: 20px;
    border-radius: 5px;
}

QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0;
}

QScrollBar:horizontal {
    border: none;
    background-color: #2b2b2b;
    height: 10px;
    margin: 0;
}

QScrollBar::handle:horizontal {
    background-color: #555555;
    min-width: 20px;
    border-radius: 5px;
}

QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {
    width: 0;
}
""" 