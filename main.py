import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QFont
from ui import MainWindow

def main():
    app = QApplication(sys.argv)
    app.setApplicationName('培训排课与出勤管理系统')
    app.setOrganizationName('TrainingSystem')

    font = QFont('Microsoft YaHei', 10)
    app.setFont(font)

    app.setStyleSheet('''
        QMainWindow {
            background: #ecf0f1;
        }
        QPushButton {
            background: #3498db;
            color: white;
            border: none;
            padding: 8px 16px;
            border-radius: 4px;
            font-size: 13px;
        }
        QPushButton:hover {
            background: #2980b9;
        }
        QPushButton:pressed {
            background: #1a5276;
        }
        QPushButton:disabled {
            background: #bdc3c7;
            color: #7f8c8d;
        }
        QLineEdit, QTextEdit, QComboBox, QSpinBox, QDateTimeEdit, QDateEdit {
            padding: 6px;
            border: 1px solid #bdc3c7;
            border-radius: 4px;
            background: white;
            selection-background-color: #3498db;
        }
        QLineEdit:focus, QTextEdit:focus, QComboBox:focus, QSpinBox:focus {
            border: 1px solid #3498db;
        }
        QTableWidget {
            background: white;
            gridline-color: #ecf0f1;
            selection-background-color: #3498db;
        }
        QTableWidget::item:selected {
            background: #3498db;
            color: white;
        }
        QHeaderView::section {
            background: #34495e;
            color: white;
            padding: 8px;
            border: none;
            font-weight: bold;
        }
        QTabWidget::pane {
            border: 1px solid #bdc3c7;
            border-radius: 4px;
            background: white;
        }
        QTabBar::tab {
            background: #ecf0f1;
            padding: 8px 16px;
            margin-right: 2px;
            border-top-left-radius: 4px;
            border-top-right-radius: 4px;
        }
        QTabBar::tab:selected {
            background: #3498db;
            color: white;
        }
        QLabel {
            color: #2c3e50;
        }
        QCalendarWidget {
            background: white;
        }
        QCalendarWidget QWidget#qt_calendar_navigationbar {
            background: #34495e;
        }
        QCalendarWidget QToolButton {
            color: white;
            background: transparent;
            padding: 4px;
        }
        QCalendarWidget QMenu {
            background: white;
            color: black;
        }
        QCalendarWidget QToolButton:hover {
            background: #3498db;
        }
        QCalendarWidget QSpinBox {
            background: white;
            color: black;
        }
        QCalendarWidget QAbstractItemView:enabled {
            selection-background-color: #3498db;
            selection-color: white;
        }
    ''')

    window = MainWindow()
    window.show()

    sys.exit(app.exec())

if __name__ == '__main__':
    main()
