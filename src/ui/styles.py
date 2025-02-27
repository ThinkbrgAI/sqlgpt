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
    min-width: 100px;
    min-height: 25px;
    margin: 2px;
}

QPushButton:hover {
    background-color: #4d4d4d;
    border-color: #777777;
}

QPushButton:pressed {
    background-color: #555555;
}

QPushButton:disabled {
    background-color: #2d2d2d;
    color: #777777;
    border-color: #444444;
}

QPushButton#import_btn, QPushButton#import_folder_btn {
    background-color: #1565c0;  /* Blue */
    border-color: #0d47a1;
}

QPushButton#import_btn:hover, QPushButton#import_folder_btn:hover {
    background-color: #1976d2;  /* Lighter blue */
}

QPushButton#import_btn:pressed, QPushButton#import_folder_btn:pressed {
    background-color: #0d47a1;  /* Darker blue */
}

QPushButton#export_btn, QPushButton#import_excel_btn {
    background-color: #00695c;  /* Teal */
    border-color: #004d40;
}

QPushButton#export_btn:hover, QPushButton#import_excel_btn:hover {
    background-color: #00796b;  /* Lighter teal */
}

QPushButton#export_btn:pressed, QPushButton#import_excel_btn:pressed {
    background-color: #004d40;  /* Darker teal */
}

QPushButton#process_btn {
    background-color: #2e7d32;  /* Dark green */
    border-color: #1b5e20;
}

QPushButton#process_btn:hover {
    background-color: #388e3c;  /* Slightly lighter green */
}

QPushButton#process_btn:pressed {
    background-color: #1b5e20;  /* Darker green */
}

QPushButton#stop_btn {
    background-color: #c62828;  /* Dark red */
    border-color: #b71c1c;
}

QPushButton#stop_btn:hover {
    background-color: #d32f2f;  /* Slightly lighter red */
}

QPushButton#stop_btn:pressed {
    background-color: #b71c1c;  /* Darker red */
}

QPushButton#clear_btn, QPushButton#clear_all_btn {
    background-color: #7b1fa2;  /* Purple */
    border-color: #6a1b9a;
}

QPushButton#clear_btn:hover, QPushButton#clear_all_btn:hover {
    background-color: #8e24aa;  /* Lighter purple */
}

QPushButton#clear_btn:pressed, QPushButton#clear_all_btn:pressed {
    background-color: #6a1b9a;  /* Darker purple */
}

QPushButton#config_btn {
    background-color: #f57c00;  /* Orange */
    border-color: #e65100;
}

QPushButton#config_btn:hover {
    background-color: #fb8c00;  /* Lighter orange */
}

QPushButton#config_btn:pressed {
    background-color: #e65100;  /* Darker orange */
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