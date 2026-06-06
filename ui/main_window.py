from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
    QLabel, QStackedWidget, QListWidget, QListWidgetItem, QStatusBar,
    QMessageBox, QToolBar, QSizePolicy
)
from PySide6.QtCore import Qt, QTimer, QSize
from PySide6.QtGui import QIcon, QColor, QBrush, QAction
from db import init_database
from services import ExceptionService, UndoManager
from .widgets import (
    CourseCalendarWidget, CourseListWidget, CourseDetailWidget,
    TransferReviewWidget, MakeupReviewWidget, ExceptionLogWidget,
    HistoryWidget, CertificateManagementWidget
)
from .dialogs import UndoDialog

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle('培训排课与出勤管理系统')
        self.resize(1200, 800)

        init_database()

        self.init_ui()
        self.init_menu()

        self.status_timer = QTimer()
        self.status_timer.timeout.connect(self.update_status_bar)
        self.status_timer.start(5000)
        self.update_status_bar()

    def init_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QVBoxLayout(central)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        self.toolbar = QToolBar('工具栏')
        self.toolbar.setMovable(False)
        self.toolbar.setIconSize(QSize(20, 20))
        self.toolbar.setStyleSheet('''
            QToolBar {
                background: #f8f9fa;
                border-bottom: 1px solid #dee2e6;
                padding: 4px;
            }
            QToolBar button {
                padding: 6px 14px;
                border-radius: 4px;
                margin: 0 4px;
            }
        ''')
        self.addToolBar(self.toolbar)

        self.undo_action = QAction('↩ 撤销上次批量操作', self)
        self.undo_action.setShortcut('Ctrl+Z')
        self.undo_action.triggered.connect(self.show_undo_dialog)
        self.toolbar.addAction(self.undo_action)

        self.toolbar.addSeparator()

        self.undo_status_label = QLabel('')
        self.undo_status_label.setStyleSheet('color: #6c757d; font-size: 12px; padding: 0 10px;')
        self.toolbar.addWidget(self.undo_status_label)

        spacer = QWidget()
        spacer.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        self.toolbar.addWidget(spacer)

        content_container = QWidget()
        content_layout = QHBoxLayout(content_container)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(0)
        main_layout.addWidget(content_container, 1)

        self.sidebar = QListWidget()
        self.sidebar.setFixedWidth(200)
        self.sidebar.setStyleSheet('''
            QListWidget {
                background: #2c3e50;
                color: white;
                border: none;
                font-size: 14px;
            }
            QListWidget::item {
                padding: 15px;
                border-bottom: 1px solid #34495e;
            }
            QListWidget::item:selected {
                background: #3498db;
                color: white;
            }
            QListWidget::item:hover {
                background: #34495e;
            }
        ''')

        menu_items = [
            ('📅 课程日历', 'calendar'),
            ('📚 课程管理', 'courses'),
            ('🔄 调课审核', 'transfer'),
            ('✍️ 补签审核', 'makeup'),
            ('🎓 结业证书', 'certificate'),
            ('⚠️ 异常日志', 'exception'),
            ('📊 历史记录', 'history')
        ]

        for text, key in menu_items:
            item = QListWidgetItem(text)
            item.setData(Qt.UserRole, key)
            self.sidebar.addItem(item)

        self.sidebar.setCurrentRow(0)
        self.sidebar.currentRowChanged.connect(self.on_menu_changed)
        content_layout.addWidget(self.sidebar)

        self.content_stack = QStackedWidget()

        self.calendar_widget = CourseCalendarWidget()
        self.course_list_widget = CourseListWidget()
        self.transfer_widget = TransferReviewWidget()
        self.makeup_widget = MakeupReviewWidget()
        self.certificate_widget = CertificateManagementWidget()
        self.exception_widget = ExceptionLogWidget()
        self.history_widget = HistoryWidget()

        self.content_stack.addWidget(self.calendar_widget)
        self.content_stack.addWidget(self.course_list_widget)
        self.content_stack.addWidget(self.transfer_widget)
        self.content_stack.addWidget(self.makeup_widget)
        self.content_stack.addWidget(self.certificate_widget)
        self.content_stack.addWidget(self.exception_widget)
        self.content_stack.addWidget(self.history_widget)

        content_layout.addWidget(self.content_stack, 1)

        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_label = QLabel()
        self.status_bar.addWidget(self.status_label)

        self.update_undo_button_state()

    def init_menu(self):
        menubar = self.menuBar()

        file_menu = menubar.addMenu('文件(&F)')
        exit_action = file_menu.addAction('退出(&X)')
        exit_action.triggered.connect(self.close)

        help_menu = menubar.addMenu('帮助(&H)')
        about_action = help_menu.addAction('关于(&A)')
        about_action.triggered.connect(self.show_about)

    def on_menu_changed(self, row):
        item = self.sidebar.item(row)
        key = item.data(Qt.UserRole)

        mapping = {
            'calendar': 0,
            'courses': 1,
            'transfer': 2,
            'makeup': 3,
            'certificate': 4,
            'exception': 5,
            'history': 6
        }

        if key in mapping:
            self.content_stack.setCurrentIndex(mapping[key])
            self.refresh_current()

    def refresh_current(self):
        current = self.content_stack.currentWidget()
        if hasattr(current, 'refresh'):
            current.refresh()
        elif hasattr(current, 'refresh_calendar'):
            current.refresh_calendar()

    def update_status_bar(self):
        try:
            unhandled = ExceptionService.get_unhandled_count()
            pending_transfer = len([
                r for r in __import__('services').RegistrationService.get_transfer_requests('pending')
            ])
            pending_makeup = len(__import__('services').AttendanceService.get_pending_makeups())

            status_parts = []
            if unhandled > 0:
                status_parts.append(f'⚠️ 异常: {unhandled}')
            if pending_transfer > 0:
                status_parts.append(f'🔄 调课待审: {pending_transfer}')
            if pending_makeup > 0:
                status_parts.append(f'✍️ 补签待审: {pending_makeup}')

            if status_parts:
                self.status_label.setText(' | '.join(status_parts))
                self.status_label.setStyleSheet('color: #e74c3c; font-weight: bold;')
            else:
                self.status_label.setText('✓ 系统运行正常')
                self.status_label.setStyleSheet('color: #27ae60;')
        except:
            self.status_label.setText('')

    def open_course_detail(self, course_id):
        detail = CourseDetailWidget(course_id)
        index = self.content_stack.addWidget(detail)
        self.content_stack.setCurrentIndex(index)

    def show_course_list(self):
        self.sidebar.setCurrentRow(1)
        self.on_menu_changed(1)

    def show_about(self):
        QMessageBox.about(
            self,
            '关于',
            '<h3>培训排课与出勤管理系统</h3>'
            '<p>版本 1.0</p>'
            '<p>功能：</p>'
            '<ul>'
            '<li>课程日历与管理</li>'
            '<li>讲师与场地安排</li>'
            '<li>学员报名与容量控制</li>'
            '<li>调课申请与审核</li>'
            '<li>签到与异常处理</li>'
            '<li>补签申请与审核</li>'
            '<li>历史记录查询</li>'
            '<li>CSV 数据导出</li>'
            '</ul>'
        )

    def show_undo_dialog(self):
        dialog = UndoDialog(self)
        if dialog.exec():
            try:
                result = UndoManager.undo_last_operation()
                if result:
                    QMessageBox.information(self, '撤销成功',
                        f'已撤销 {result["restored_count"]} 条记录')
                    self.refresh_all()
                    self.update_undo_button_state()
                else:
                    QMessageBox.warning(self, '撤销失败', '没有可撤销的操作')
            except Exception as e:
                QMessageBox.warning(self, '撤销失败', f'撤销操作失败：{e}')

    def update_undo_button_state(self):
        try:
            has_undo = UndoManager.has_undo_available()
            self.undo_action.setEnabled(has_undo)

            if has_undo:
                undo_info = UndoManager.get_last_undo_info()
                if undo_info:
                    op_type_map = {
                        'cancel': '批量取消',
                        'change_status': '批量改状态',
                        'transfer': '批量调课'
                    }
                    op_type = op_type_map.get(undo_info.get('operation_type'), '批量操作')
                    self.undo_status_label.setText(
                        f"可撤销: {op_type} ({undo_info.get('success_count', 0)} 条成功记录)"
                    )
                    self.undo_status_label.setStyleSheet('color: #ff9800; font-size: 12px; padding: 0 10px;')
                else:
                    self.undo_status_label.setText('')
            else:
                self.undo_status_label.setText('')
                self.undo_status_label.setStyleSheet('color: #6c757d; font-size: 12px; padding: 0 10px;')
        except Exception as e:
            self.undo_status_label.setText('')

    def refresh_all(self):
        try:
            self.calendar_widget.refresh_calendar()
        except:
            pass
        try:
            self.course_list_widget.refresh()
        except:
            pass
        try:
            self.transfer_widget.refresh()
        except:
            pass
        try:
            self.makeup_widget.refresh()
        except:
            pass
        try:
            self.certificate_widget.refresh_certificates()
        except:
            pass
        try:
            self.exception_widget.refresh()
        except:
            pass
        try:
            self.history_widget.refresh()
        except:
            pass
        self.update_status_bar()
        self.update_undo_button_state()

    def closeEvent(self, event):
        reply = QMessageBox.question(
            self, '确认退出',
            '确定要退出系统吗？\n所有数据已自动保存。',
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            event.accept()
        else:
            event.ignore()
