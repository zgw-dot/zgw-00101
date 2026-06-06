from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QTableWidget,
    QTableWidgetItem, QHeaderView, QMessageBox, QLabel, QSplitter,
    QListWidget, QListWidgetItem, QComboBox, QLineEdit, QCalendarWidget,
    QTextEdit, QFrame, QGroupBox, QAbstractItemView, QMenu, QToolBar,
    QStatusBar, QTabWidget
)
from PySide6.QtCore import Qt, QDate, QTimer
from PySide6.QtGui import QAction, QColor, QBrush, QFont
from datetime import datetime, timedelta
from services import (
    CourseService, RegistrationService, AttendanceService,
    ExportService, ExceptionService, ValidationError
)
from .dialogs import (
    CourseDialog, RegistrationDialog, TransferDialog,
    TransferReviewDialog, CheckInDialog, MakeupRequestDialog,
    MakeupReviewDialog, DateRangeDialog
)

class CourseCalendarWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.init_ui()
        self.refresh_calendar()

    def init_ui(self):
        layout = QVBoxLayout(self)

        toolbar = QHBoxLayout()
        refresh_btn = QPushButton('刷新')
        refresh_btn.clicked.connect(self.refresh_calendar)
        toolbar.addWidget(refresh_btn)
        toolbar.addStretch()
        layout.addLayout(toolbar)

        self.calendar = QCalendarWidget()
        self.calendar.setGridVisible(True)
        self.calendar.selectionChanged.connect(self.on_date_selected)
        layout.addWidget(self.calendar)

        layout.addWidget(QLabel('当日课程：'))
        self.day_course_list = QListWidget()
        self.day_course_list.itemDoubleClicked.connect(self.on_course_double_clicked)
        self.day_course_list.setContextMenuPolicy(Qt.CustomContextMenu)
        self.day_course_list.customContextMenuRequested.connect(self.show_context_menu)
        layout.addWidget(self.day_course_list, 2)

    def refresh_calendar(self):
        self.course_dates = {}
        courses = CourseService.get_all_courses('published')
        for course in courses:
            date_str = course['start_time'][:10]
            if date_str not in self.course_dates:
                self.course_dates[date_str] = []
            self.course_dates[date_str].append(course)

        self.calendar.setDateTextFormat(QDate(), self.calendar.dateTextFormat(QDate()))
        for date_str, courses in self.course_dates.items():
            date = QDate.fromString(date_str, 'yyyy-MM-dd')
            format = self.calendar.dateTextFormat(date)
            format.setBackground(QBrush(QColor(200, 230, 255)))
            self.calendar.setDateTextFormat(date, format)

        self.on_date_selected()

    def on_date_selected(self):
        selected = self.calendar.selectedDate().toString('yyyy-MM-dd')
        self.day_course_list.clear()

        if selected in self.course_dates:
            for course in self.course_dates[selected]:
                count = RegistrationService.get_course_registrations(course['id'])
                time_range = f"{course['start_time'][11:16]} - {course['end_time'][11:16]}"
                text = f"[{time_range}] {course['title']} | {course['instructor']} | {course['venue']} | {len(count)}/{course['capacity']}人"
                item = QListWidgetItem(text)
                item.setData(Qt.UserRole, course)
                if len(count) >= course['capacity']:
                    item.setForeground(QBrush(QColor(244, 67, 54)))
                self.day_course_list.addItem(item)

    def on_course_double_clicked(self, item):
        course = item.data(Qt.UserRole)
        if self.parent() and hasattr(self.parent(), 'parent'):
            main_window = self.window()
            if hasattr(main_window, 'open_course_detail'):
                main_window.open_course_detail(course['id'])

    def show_context_menu(self, pos):
        item = self.day_course_list.itemAt(pos)
        if not item:
            return

        course = item.data(Qt.UserRole)
        menu = QMenu(self)

        detail_action = QAction('查看详情', self)
        detail_action.triggered.connect(lambda: self.window().open_course_detail(course['id']))
        menu.addAction(detail_action)

        register_action = QAction('学员报名', self)
        register_action.triggered.connect(lambda: self.show_registration_dialog(course['id']))
        menu.addAction(register_action)

        checkin_action = QAction('签到', self)
        checkin_action.triggered.connect(lambda: self.show_checkin_dialog(course['id']))
        menu.addAction(checkin_action)

        menu.exec(self.day_course_list.mapToGlobal(pos))

    def show_registration_dialog(self, course_id):
        dialog = RegistrationDialog(course_id, self)
        if dialog.exec():
            self.refresh_calendar()
            self.window().refresh_all()

    def show_checkin_dialog(self, course_id):
        dialog = CheckInDialog(course_id, self)
        dialog.exec()
        self.window().refresh_all()

class CourseListWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.init_ui()
        self.refresh()

    def init_ui(self):
        layout = QVBoxLayout(self)

        toolbar = QHBoxLayout()
        add_btn = QPushButton('新建课程')
        add_btn.clicked.connect(self.add_course)
        toolbar.addWidget(add_btn)

        edit_btn = QPushButton('编辑')
        edit_btn.clicked.connect(self.edit_course)
        toolbar.addWidget(edit_btn)

        publish_btn = QPushButton('发布')
        publish_btn.clicked.connect(self.publish_course)
        toolbar.addWidget(publish_btn)

        delete_btn = QPushButton('删除')
        delete_btn.clicked.connect(self.delete_course)
        toolbar.addWidget(delete_btn)

        self.filter_combo = QComboBox()
        self.filter_combo.addItems(['全部', '草稿', '已发布'])
        self.filter_combo.currentIndexChanged.connect(self.refresh)
        toolbar.addStretch()
        toolbar.addWidget(QLabel('筛选：'))
        toolbar.addWidget(self.filter_combo)

        layout.addLayout(toolbar)

        self.table = QTableWidget()
        self.table.setColumnCount(9)
        self.table.setHorizontalHeaderLabels([
            'ID', '标题', '主题', '讲师', '场地', '开始时间',
            '容量', '已报名', '状态'
        ])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.doubleClicked.connect(self.on_row_double_clicked)
        layout.addWidget(self.table)

    def refresh(self):
        filter_text = self.filter_combo.currentText()
        status = None
        if filter_text == '草稿':
            status = 'draft'
        elif filter_text == '已发布':
            status = 'published'

        courses = CourseService.get_all_courses(status)
        self.table.setRowCount(len(courses))

        for row, course in enumerate(courses):
            reg_count = len(RegistrationService.get_course_registrations(course['id']))

            self.table.setItem(row, 0, QTableWidgetItem(str(course['id'])))
            self.table.setItem(row, 1, QTableWidgetItem(course['title']))
            self.table.setItem(row, 2, QTableWidgetItem(course['theme']))
            self.table.setItem(row, 3, QTableWidgetItem(course['instructor']))
            self.table.setItem(row, 4, QTableWidgetItem(course['venue']))
            self.table.setItem(row, 5, QTableWidgetItem(course['start_time'][:16]))
            self.table.setItem(row, 6, QTableWidgetItem(str(course['capacity'])))
            count_item = QTableWidgetItem(f'{reg_count}')
            if reg_count >= course['capacity']:
                count_item.setForeground(QBrush(QColor(244, 67, 54)))
            self.table.setItem(row, 7, count_item)

            status_text = '已发布' if course['status'] == 'published' else '草稿'
            status_item = QTableWidgetItem(status_text)
            if course['status'] == 'published':
                status_item.setForeground(QBrush(QColor(76, 175, 80)))
            self.table.setItem(row, 8, status_item)

            self.table.item(row, 0).setData(Qt.UserRole, course['id'])

    def get_selected_course_id(self):
        current_row = self.table.currentRow()
        if current_row < 0:
            return None
        return self.table.item(current_row, 0).data(Qt.UserRole)

    def add_course(self):
        dialog = CourseDialog(self)
        if dialog.exec():
            data = dialog.get_data()
            try:
                CourseService.create_course(data)
                self.refresh()
                self.window().refresh_all()
            except ValidationError as e:
                QMessageBox.warning(self, '创建失败', str(e))

    def edit_course(self):
        course_id = self.get_selected_course_id()
        if not course_id:
            QMessageBox.warning(self, '提示', '请选择课程')
            return

        course = CourseService.get_course(course_id)
        dialog = CourseDialog(self, course)
        if dialog.exec():
            data = dialog.get_data()
            try:
                CourseService.update_course(course_id, data)
                self.refresh()
                self.window().refresh_all()
            except ValidationError as e:
                QMessageBox.warning(self, '更新失败', str(e))

    def publish_course(self):
        course_id = self.get_selected_course_id()
        if not course_id:
            QMessageBox.warning(self, '提示', '请选择课程')
            return

        try:
            CourseService.publish_course(course_id)
            QMessageBox.information(self, '成功', '课程已发布')
            self.refresh()
            self.window().refresh_all()
        except ValidationError as e:
            QMessageBox.warning(self, '发布失败', str(e))

    def delete_course(self):
        course_id = self.get_selected_course_id()
        if not course_id:
            QMessageBox.warning(self, '提示', '请选择课程')
            return

        if QMessageBox.question(self, '确认', '确定要删除此课程吗？') != QMessageBox.Yes:
            return

        try:
            CourseService.delete_course(course_id)
            self.refresh()
            self.window().refresh_all()
        except ValidationError as e:
            QMessageBox.warning(self, '删除失败', str(e))

    def on_row_double_clicked(self, index):
        course_id = self.get_selected_course_id()
        if course_id:
            self.window().open_course_detail(course_id)

class CourseDetailWidget(QWidget):
    def __init__(self, course_id, parent=None):
        super().__init__(parent)
        self.course_id = course_id
        self.init_ui()
        self.refresh()

    def init_ui(self):
        layout = QVBoxLayout(self)

        self.info_label = QLabel()
        self.info_label.setStyleSheet('padding: 15px; background: #f5f5f5; border-radius: 8px; font-size: 14px;')
        self.info_label.setWordWrap(True)
        layout.addWidget(self.info_label)

        toolbar = QHBoxLayout()

        register_btn = QPushButton('学员报名')
        register_btn.clicked.connect(self.show_registration)
        toolbar.addWidget(register_btn)

        checkin_btn = QPushButton('签到')
        checkin_btn.clicked.connect(self.show_checkin)
        toolbar.addWidget(checkin_btn)

        mark_absent_btn = QPushButton('一键标记缺勤')
        mark_absent_btn.clicked.connect(self.mark_all_absent)
        toolbar.addWidget(mark_absent_btn)

        export_btn = QPushButton('导出生勤表')
        export_btn.clicked.connect(self.export_attendance)
        toolbar.addWidget(export_btn)

        toolbar.addStretch()

        back_btn = QPushButton('返回')
        back_btn.clicked.connect(lambda: self.window().show_course_list())
        toolbar.addWidget(back_btn)

        layout.addLayout(toolbar)

        self.tabs = QTabWidget()

        self.reg_tab = QWidget()
        reg_layout = QVBoxLayout(self.reg_tab)
        self.reg_table = QTableWidget()
        self.reg_table.setColumnCount(6)
        self.reg_table.setHorizontalHeaderLabels(['工号', '姓名', '部门', '电话', '邮箱', '操作'])
        self.reg_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.reg_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        reg_layout.addWidget(self.reg_table)

        self.att_tab = QWidget()
        att_layout = QVBoxLayout(self.att_tab)
        self.att_table = QTableWidget()
        self.att_table.setColumnCount(7)
        self.att_table.setHorizontalHeaderLabels(['工号', '姓名', '部门', '状态', '签到时间', '补签状态', '操作'])
        self.att_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.att_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        att_layout.addWidget(self.att_table)

        self.tabs.addTab(self.reg_tab, '报名名单')
        self.tabs.addTab(self.att_tab, '出勤状态')
        layout.addWidget(self.tabs)

    def refresh(self):
        course = CourseService.get_course(self.course_id)
        if not course:
            return

        summary = CourseService.get_course_attendance_summary(self.course_id)
        status_text = '已发布' if course['status'] == 'published' else '草稿'
        self.info_label.setText(
            f'<b>{course["title"]}</b><br>'
            f'主题：{course["theme"]} | 状态：{status_text}<br>'
            f'讲师：{course["instructor"]} | 场地：{course["venue"]}<br>'
            f'时间：{course["start_time"][:16]} ~ {course["end_time"][:16]}<br>'
            f'报名截止：{course["registration_deadline"][:16]}<br>'
            f'报名：{summary["total_registered"]}/{course["capacity"]} 人 | '
            f'出勤：{summary["present"]} | 缺勤：{summary["absent"]} | '
            f'未签：{summary["pending"]} | 补签：{summary["makeup"]}'
        )

        if course.get('description'):
            self.info_label.setText(self.info_label.text() + f'<br>描述：{course["description"]}')

        self.refresh_registrations()
        self.refresh_attendance()

    def refresh_registrations(self):
        regs = RegistrationService.get_course_registrations(self.course_id)
        self.reg_table.setRowCount(len(regs))

        for row, reg in enumerate(regs):
            self.reg_table.setItem(row, 0, QTableWidgetItem(reg['employee_id']))
            self.reg_table.setItem(row, 1, QTableWidgetItem(reg['name']))
            self.reg_table.setItem(row, 2, QTableWidgetItem(reg.get('department', '')))
            self.reg_table.setItem(row, 3, QTableWidgetItem(reg.get('phone', '')))
            self.reg_table.setItem(row, 4, QTableWidgetItem(reg.get('email', '')))

            btn_widget = QWidget()
            btn_layout = QHBoxLayout(btn_widget)
            btn_layout.setContentsMargins(2, 2, 2, 2)
            transfer_btn = QPushButton('调课')
            transfer_btn.setFixedHeight(24)
            transfer_btn.clicked.connect(lambda _, r=reg: self.request_transfer(r))
            btn_layout.addWidget(transfer_btn)
            self.reg_table.setCellWidget(row, 5, btn_widget)

            self.reg_table.item(row, 0).setData(Qt.UserRole, reg['id'])

    def refresh_attendance(self):
        attendances = AttendanceService.get_course_attendance(self.course_id)
        self.att_table.setRowCount(len(attendances))

        status_map = {'present': '已出勤', 'absent': '缺勤', 'pending': '未签到'}
        makeup_map = {'none': '无', 'pending': '待审核', 'approved': '已通过', 'rejected': '已驳回'}
        color_map = {'present': QColor(76, 175, 80), 'absent': QColor(244, 67, 54), 'pending': QColor(255, 152, 0)}

        for row, att in enumerate(attendances):
            self.att_table.setItem(row, 0, QTableWidgetItem(att['employee_id']))
            self.att_table.setItem(row, 1, QTableWidgetItem(att['name']))
            self.att_table.setItem(row, 2, QTableWidgetItem(att.get('department', '')))

            status_item = QTableWidgetItem(status_map.get(att['status'], att['status']))
            status_item.setForeground(QBrush(color_map.get(att['status'], QColor(0, 0, 0))))
            self.att_table.setItem(row, 3, status_item)

            checkin_text = att.get('check_in_time', '')
            if checkin_text:
                checkin_text = checkin_text[11:19]
            self.att_table.setItem(row, 4, QTableWidgetItem(checkin_text))

            makeup_item = QTableWidgetItem(makeup_map.get(att.get('makeup_status', 'none'), '无'))
            if att.get('makeup_status') == 'pending':
                makeup_item.setForeground(QBrush(QColor(255, 152, 0)))
            elif att.get('makeup_status') == 'approved':
                makeup_item.setForeground(QBrush(QColor(76, 175, 80)))
            self.att_table.setItem(row, 5, makeup_item)

            btn_widget = QWidget()
            btn_layout = QHBoxLayout(btn_widget)
            btn_layout.setContentsMargins(2, 2, 2, 2)

            if att['status'] != 'present' and att.get('makeup_status') not in ['pending', 'approved']:
                makeup_btn = QPushButton('申请补签')
                makeup_btn.setFixedHeight(24)
                makeup_btn.clicked.connect(lambda _, a=att: self.request_makeup(a))
                btn_layout.addWidget(makeup_btn)

            self.att_table.setCellWidget(row, 6, btn_widget)

            self.att_table.item(row, 0).setData(Qt.UserRole, att)

    def show_registration(self):
        dialog = RegistrationDialog(self.course_id, self)
        if dialog.exec():
            self.refresh()
            self.window().refresh_all()

    def show_checkin(self):
        dialog = CheckInDialog(self.course_id, self)
        dialog.exec()
        self.refresh()
        self.window().refresh_all()

    def mark_all_absent(self):
        if QMessageBox.question(self, '确认', '确定要将所有未签到学员标记为缺勤吗？') != QMessageBox.Yes:
            return
        try:
            count = AttendanceService.mark_all_absent(self.course_id)
            QMessageBox.information(self, '成功', f'已标记 {count} 名学员为缺勤')
            self.refresh()
            self.window().refresh_all()
        except ValidationError as e:
            QMessageBox.warning(self, '操作失败', str(e))

    def export_attendance(self):
        try:
            path = ExportService.export_course_attendance(self.course_id)
            QMessageBox.information(self, '成功', f'已导出到：\n{path}')
        except Exception as e:
            QMessageBox.warning(self, '导出失败', str(e))

    def request_transfer(self, reg):
        dialog = TransferDialog(reg, self)
        if dialog.exec():
            self.refresh()
            self.window().refresh_all()

    def request_makeup(self, att):
        dialog = MakeupRequestDialog(self.course_id, att['student_id'], att['name'], self)
        if dialog.exec():
            self.refresh()
            self.window().refresh_all()

class TransferReviewWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.init_ui()
        self.refresh()

    def init_ui(self):
        layout = QVBoxLayout(self)

        toolbar = QHBoxLayout()
        refresh_btn = QPushButton('刷新')
        refresh_btn.clicked.connect(self.refresh)
        toolbar.addWidget(refresh_btn)

        self.filter_combo = QComboBox()
        self.filter_combo.addItems(['全部', '待审核', '已通过', '已驳回'])
        self.filter_combo.currentIndexChanged.connect(self.refresh)
        toolbar.addStretch()
        toolbar.addWidget(QLabel('筛选：'))
        toolbar.addWidget(self.filter_combo)
        layout.addLayout(toolbar)

        self.table = QTableWidget()
        self.table.setColumnCount(7)
        self.table.setHorizontalHeaderLabels([
            'ID', '学员', '原课程', '目标课程', '申请时间', '状态', '操作'
        ])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        layout.addWidget(self.table)

    def refresh(self):
        filter_text = self.filter_combo.currentText()
        status = None
        if filter_text == '待审核':
            status = 'pending'
        elif filter_text == '已通过':
            status = 'approved'
        elif filter_text == '已驳回':
            status = 'rejected'

        requests = RegistrationService.get_transfer_requests(status)
        self.table.setRowCount(len(requests))

        status_map = {'pending': '待审核', 'approved': '已通过', 'rejected': '已驳回'}
        color_map = {'pending': QColor(255, 152, 0), 'approved': QColor(76, 175, 80), 'rejected': QColor(244, 67, 54)}

        for row, req in enumerate(requests):
            self.table.setItem(row, 0, QTableWidgetItem(str(req['id'])))
            self.table.setItem(row, 1, QTableWidgetItem(f'{req["student_name"]}({req["employee_id"]})'))
            self.table.setItem(row, 2, QTableWidgetItem(req['from_course_title']))
            self.table.setItem(row, 3, QTableWidgetItem(req['to_course_title']))
            self.table.setItem(row, 4, QTableWidgetItem(req['requested_at'][:19]))

            status_item = QTableWidgetItem(status_map.get(req['status'], req['status']))
            status_item.setForeground(QBrush(color_map.get(req['status'], QColor(0, 0, 0))))
            self.table.setItem(row, 5, status_item)

            btn_widget = QWidget()
            btn_layout = QHBoxLayout(btn_widget)
            btn_layout.setContentsMargins(2, 2, 2, 2)

            if req['status'] == 'pending':
                review_btn = QPushButton('审核')
                review_btn.setFixedHeight(24)
                review_btn.clicked.connect(lambda _, r=req: self.review_request(r))
                btn_layout.addWidget(review_btn)

            self.table.setCellWidget(row, 6, btn_widget)
            self.table.item(row, 0).setData(Qt.UserRole, req)

    def review_request(self, req):
        dialog = TransferReviewDialog(req, self)
        if dialog.exec():
            self.refresh()
            self.window().refresh_all()

class MakeupReviewWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.init_ui()
        self.refresh()

    def init_ui(self):
        layout = QVBoxLayout(self)

        toolbar = QHBoxLayout()
        refresh_btn = QPushButton('刷新')
        refresh_btn.clicked.connect(self.refresh)
        toolbar.addWidget(refresh_btn)
        layout.addLayout(toolbar)

        info_label = QLabel('待审核的补签申请：')
        layout.addWidget(info_label)

        self.table = QTableWidget()
        self.table.setColumnCount(7)
        self.table.setHorizontalHeaderLabels([
            'ID', '学员', '课程', '课程时间', '申请时间', '补签原因', '操作'
        ])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setWordWrap(True)
        self.table.verticalHeader().setDefaultSectionSize(60)
        layout.addWidget(self.table)

    def refresh(self):
        makeups = AttendanceService.get_pending_makeups()
        self.table.setRowCount(len(makeups))

        for row, makeup in enumerate(makeups):
            self.table.setItem(row, 0, QTableWidgetItem(str(makeup['id'])))
            self.table.setItem(row, 1, QTableWidgetItem(f'{makeup["student_name"]}({makeup["employee_id"]})'))
            self.table.setItem(row, 2, QTableWidgetItem(makeup['course_title']))
            self.table.setItem(row, 3, QTableWidgetItem(makeup['course_time'][:16]))
            self.table.setItem(row, 4, QTableWidgetItem(makeup['makeup_requested_at'][:19]))
            self.table.setItem(row, 5, QTableWidgetItem(makeup.get('makeup_reason', '')))

            btn_widget = QWidget()
            btn_layout = QHBoxLayout(btn_widget)
            btn_layout.setContentsMargins(2, 2, 2, 2)
            review_btn = QPushButton('审核')
            review_btn.setFixedHeight(24)
            review_btn.clicked.connect(lambda _, m=makeup: self.review_makeup(m))
            btn_layout.addWidget(review_btn)
            self.table.setCellWidget(row, 6, btn_widget)

            self.table.item(row, 0).setData(Qt.UserRole, makeup)

    def review_makeup(self, makeup):
        dialog = MakeupReviewDialog(makeup, self)
        if dialog.exec():
            self.refresh()
            self.window().refresh_all()

class ExceptionLogWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.init_ui()
        self.refresh()

    def init_ui(self):
        layout = QVBoxLayout(self)

        toolbar = QHBoxLayout()
        refresh_btn = QPushButton('刷新')
        refresh_btn.clicked.connect(self.refresh)
        toolbar.addWidget(refresh_btn)

        export_btn = QPushButton('导出异常日志')
        export_btn.clicked.connect(self.export_logs)
        toolbar.addWidget(export_btn)

        self.filter_combo = QComboBox()
        self.filter_combo.addItems(['全部', '未处理', '已处理'])
        self.filter_combo.currentIndexChanged.connect(self.refresh)
        toolbar.addStretch()
        toolbar.addWidget(QLabel('筛选：'))
        toolbar.addWidget(self.filter_combo)
        layout.addLayout(toolbar)

        self.table = QTableWidget()
        self.table.setColumnCount(8)
        self.table.setHorizontalHeaderLabels([
            'ID', '异常类型', '描述', '关联课程', '关联学员',
            '发生时间', '状态', '操作'
        ])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setWordWrap(True)
        self.table.verticalHeader().setDefaultSectionSize(50)
        layout.addWidget(self.table)

    def refresh(self):
        filter_text = self.filter_combo.currentText()
        handled = None
        if filter_text == '未处理':
            handled = False
        elif filter_text == '已处理':
            handled = True

        logs = ExceptionService.get_all_logs(handled=handled)
        self.table.setRowCount(len(logs))

        type_map = {
            'over_capacity': '超容量报名',
            'transfer_after_deadline': '截止后调课',
            'duplicate_checkin': '重复签到',
            'unapproved_makeup': '未审核补签生效',
            'makeup_approved': '补签审核通过',
            'makeup_rejected': '补签审核驳回'
        }

        for row, log in enumerate(logs):
            self.table.setItem(row, 0, QTableWidgetItem(str(log['id'])))

            type_item = QTableWidgetItem(type_map.get(log['type'], log['type']))
            type_item.setForeground(QBrush(QColor(244, 67, 54)))
            self.table.setItem(row, 1, type_item)

            desc_item = QTableWidgetItem(log['description'])
            self.table.setItem(row, 2, desc_item)

            self.table.setItem(row, 3, QTableWidgetItem(log.get('course_title') or ''))

            student_text = ''
            if log.get('student_name'):
                student_text = f'{log["student_name"]}({log.get("employee_id", "")})'
            self.table.setItem(row, 4, QTableWidgetItem(student_text))

            self.table.setItem(row, 5, QTableWidgetItem(log['created_at'][:19]))

            status_text = '已处理' if log['handled'] else '未处理'
            status_item = QTableWidgetItem(status_text)
            if log['handled']:
                status_item.setForeground(QBrush(QColor(76, 175, 80)))
            else:
                status_item.setForeground(QBrush(QColor(255, 152, 0)))
            self.table.setItem(row, 6, status_item)

            btn_widget = QWidget()
            btn_layout = QHBoxLayout(btn_widget)
            btn_layout.setContentsMargins(2, 2, 2, 2)

            if not log['handled']:
                handle_btn = QPushButton('标记已处理')
                handle_btn.setFixedHeight(24)
                handle_btn.clicked.connect(lambda _, lid=log['id']: self.mark_handled(lid))
                btn_layout.addWidget(handle_btn)

            self.table.setCellWidget(row, 7, btn_widget)
            self.table.item(row, 0).setData(Qt.UserRole, log['id'])

    def mark_handled(self, log_id):
        try:
            ExceptionService.mark_handled(log_id)
            self.refresh()
            self.window().refresh_all()
        except Exception as e:
            QMessageBox.warning(self, '操作失败', str(e))

    def export_logs(self):
        try:
            path = ExportService.export_exception_logs()
            QMessageBox.information(self, '成功', f'已导出到：\n{path}')
        except Exception as e:
            QMessageBox.warning(self, '导出失败', str(e))

class HistoryWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.init_ui()
        self.refresh()

    def init_ui(self):
        layout = QVBoxLayout(self)

        toolbar = QHBoxLayout()
        refresh_btn = QPushButton('刷新')
        refresh_btn.clicked.connect(self.refresh)
        toolbar.addWidget(refresh_btn)

        date_range_btn = QPushButton('按日期查询')
        date_range_btn.clicked.connect(self.query_by_date)
        toolbar.addWidget(date_range_btn)

        export_all_btn = QPushButton('导出全部历史')
        export_all_btn.clicked.connect(self.export_all)
        toolbar.addWidget(export_all_btn)

        toolbar.addStretch()
        layout.addLayout(toolbar)

        self.table = QTableWidget()
        self.table.setColumnCount(8)
        self.table.setHorizontalHeaderLabels([
            '课程', '主题', '讲师', '场地', '时间', '报名人数', '出勤率', '状态'
        ])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.doubleClicked.connect(self.on_row_double_clicked)
        layout.addWidget(self.table)

    def refresh(self, start_date=None, end_date=None):
        if start_date and end_date:
            courses = CourseService.get_courses_by_date(start_date, end_date)
        else:
            courses = CourseService.get_all_courses()

        self.table.setRowCount(len(courses))

        status_map = {'draft': '草稿', 'published': '已发布'}

        for row, course in enumerate(courses):
            summary = CourseService.get_course_attendance_summary(course['id'])

            self.table.setItem(row, 0, QTableWidgetItem(course['title']))
            self.table.setItem(row, 1, QTableWidgetItem(course['theme']))
            self.table.setItem(row, 2, QTableWidgetItem(course['instructor']))
            self.table.setItem(row, 3, QTableWidgetItem(course['venue']))
            self.table.setItem(row, 4, QTableWidgetItem(
                f'{course["start_time"][:16]} ~ {course["end_time"][:11]}'
            ))
            self.table.setItem(row, 5, QTableWidgetItem(
                f'{summary["total_registered"]}/{course["capacity"]}'
            ))

            rate_text = f'{summary["attendance_rate"]:.1f}%'
            rate_item = QTableWidgetItem(rate_text)
            if summary['attendance_rate'] >= 90:
                rate_item.setForeground(QBrush(QColor(76, 175, 80)))
            elif summary['attendance_rate'] >= 70:
                rate_item.setForeground(QBrush(QColor(255, 152, 0)))
            else:
                rate_item.setForeground(QBrush(QColor(244, 67, 54)))
            self.table.setItem(row, 6, rate_item)

            status_item = QTableWidgetItem(status_map.get(course['status'], course['status']))
            if course['status'] == 'published':
                status_item.setForeground(QBrush(QColor(76, 175, 80)))
            self.table.setItem(row, 7, status_item)

            self.table.item(row, 0).setData(Qt.UserRole, course['id'])

    def query_by_date(self):
        dialog = DateRangeDialog(self)
        if dialog.exec():
            start, end = dialog.get_range()
            self.refresh(start, end)

    def export_all(self):
        try:
            path = ExportService.export_all_history()
            QMessageBox.information(self, '成功', f'已导出到：\n{path}')
        except Exception as e:
            QMessageBox.warning(self, '导出失败', str(e))

    def on_row_double_clicked(self, index):
        course_id = self.table.item(index.row(), 0).data(Qt.UserRole)
        if course_id:
            self.window().open_course_detail(course_id)
