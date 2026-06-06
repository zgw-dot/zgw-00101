from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout, QLabel, QLineEdit,
    QTextEdit, QComboBox, QDateTimeEdit, QSpinBox, QPushButton,
    QMessageBox, QDialogButtonBox, QListWidget, QListWidgetItem,
    QTableWidget, QTableWidgetItem, QHeaderView, QAbstractItemView,
    QInputDialog, QDateEdit, QFileDialog, QFrame
)
from PySide6.QtCore import Qt, QDateTime, QDate
from PySide6.QtGui import QColor, QBrush
from services import (
    CourseService, RegistrationService, AttendanceService,
    ExportService, BatchOperationService, UndoManager, ValidationError
)
from datetime import datetime, timedelta

class CourseDialog(QDialog):
    def __init__(self, parent=None, course=None):
        super().__init__(parent)
        self.course = course
        self.setWindowTitle('编辑课程' if course else '新建课程')
        self.resize(500, 600)
        self.init_ui()
        if course:
            self.load_data()

    def init_ui(self):
        layout = QVBoxLayout(self)
        form = QFormLayout()

        self.title_edit = QLineEdit()
        form.addRow('课程标题*：', self.title_edit)

        self.theme_edit = QLineEdit()
        form.addRow('课程主题*：', self.theme_edit)

        self.desc_edit = QTextEdit()
        self.desc_edit.setFixedHeight(80)
        form.addRow('课程描述：', self.desc_edit)

        self.instructor_edit = QLineEdit()
        form.addRow('讲师*：', self.instructor_edit)

        self.venue_edit = QLineEdit()
        form.addRow('场地*：', self.venue_edit)

        default_start = QDateTime.currentDateTime().addDays(7).addSecs(-3600 * QDateTime.currentDateTime().time().hour() + 9 * 3600)
        default_start.setTime(default_start.time().addSecs(-default_start.time().minute() * 60 - default_start.time().second()))

        self.start_edit = QDateTimeEdit(default_start)
        self.start_edit.setDisplayFormat('yyyy-MM-dd HH:mm')
        self.start_edit.setCalendarPopup(True)
        form.addRow('开始时间*：', self.start_edit)

        self.end_edit = QDateTimeEdit(default_start.addSecs(3 * 3600))
        self.end_edit.setDisplayFormat('yyyy-MM-dd HH:mm')
        self.end_edit.setCalendarPopup(True)
        form.addRow('结束时间*：', self.end_edit)

        self.capacity_spin = QSpinBox()
        self.capacity_spin.setRange(1, 1000)
        self.capacity_spin.setValue(30)
        form.addRow('课程容量*：', self.capacity_spin)

        self.deadline_edit = QDateTimeEdit(default_start.addDays(-1))
        self.deadline_edit.setDisplayFormat('yyyy-MM-dd HH:mm')
        self.deadline_edit.setCalendarPopup(True)
        form.addRow('报名截止*：', self.deadline_edit)

        self.status_combo = QComboBox()
        self.status_combo.addItems(['草稿', '已发布'])
        form.addRow('状态：', self.status_combo)

        layout.addLayout(form)

        buttons = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def load_data(self):
        self.title_edit.setText(self.course['title'])
        self.theme_edit.setText(self.course['theme'])
        self.desc_edit.setPlainText(self.course.get('description', ''))
        self.instructor_edit.setText(self.course['instructor'])
        self.venue_edit.setText(self.course['venue'])
        self.start_edit.setDateTime(QDateTime.fromString(self.course['start_time'], Qt.ISODate))
        self.end_edit.setDateTime(QDateTime.fromString(self.course['end_time'], Qt.ISODate))
        self.capacity_spin.setValue(self.course['capacity'])
        self.deadline_edit.setDateTime(QDateTime.fromString(self.course['registration_deadline'], Qt.ISODate))
        self.status_combo.setCurrentIndex(1 if self.course['status'] == 'published' else 0)

    def get_data(self):
        return {
            'title': self.title_edit.text().strip(),
            'theme': self.theme_edit.text().strip(),
            'description': self.desc_edit.toPlainText().strip(),
            'instructor': self.instructor_edit.text().strip(),
            'venue': self.venue_edit.text().strip(),
            'start_time': self.start_edit.dateTime().toString(Qt.ISODate),
            'end_time': self.end_edit.dateTime().toString(Qt.ISODate),
            'capacity': self.capacity_spin.value(),
            'registration_deadline': self.deadline_edit.dateTime().toString(Qt.ISODate),
            'status': 'published' if self.status_combo.currentIndex() == 1 else 'draft'
        }

    def accept(self):
        data = self.get_data()
        try:
            CourseService.validate_course_data(data)
            super().accept()
        except ValidationError as e:
            QMessageBox.warning(self, '输入错误', str(e))

class RegistrationDialog(QDialog):
    def __init__(self, course_id, parent=None):
        super().__init__(parent)
        self.course_id = course_id
        self.setWindowTitle('学员报名')
        self.resize(400, 300)
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        form = QFormLayout()

        self.name_edit = QLineEdit()
        form.addRow('姓名*：', self.name_edit)

        self.emp_id_edit = QLineEdit()
        form.addRow('工号*：', self.emp_id_edit)

        self.dept_edit = QLineEdit()
        form.addRow('部门：', self.dept_edit)

        self.phone_edit = QLineEdit()
        form.addRow('电话：', self.phone_edit)

        self.email_edit = QLineEdit()
        form.addRow('邮箱：', self.email_edit)

        layout.addLayout(form)

        buttons = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def get_data(self):
        return {
            'name': self.name_edit.text().strip(),
            'employee_id': self.emp_id_edit.text().strip(),
            'department': self.dept_edit.text().strip(),
            'phone': self.phone_edit.text().strip(),
            'email': self.email_edit.text().strip()
        }

    def accept(self):
        data = self.get_data()
        if not data['name'] or not data['employee_id']:
            QMessageBox.warning(self, '提示', '请填写姓名和工号')
            return

        try:
            RegistrationService.register_student(self.course_id, data)
            QMessageBox.information(self, '成功', '报名成功！')
            super().accept()
        except ValidationError as e:
            QMessageBox.warning(self, '报名失败', str(e))

class TransferDialog(QDialog):
    def __init__(self, registration, parent=None):
        super().__init__(parent)
        self.registration = registration
        self.setWindowTitle('申请调课')
        self.resize(500, 400)
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)

        info = QLabel(
            f'当前课程：{self.registration["course_title"]}\n'
            f'课程主题：{self.registration["course_theme"]}\n'
            f'学员：{self.registration["student_name"]} ({self.registration["employee_id"]})'
        )
        info.setStyleSheet('padding: 10px; background: #f0f0f0; border-radius: 5px;')
        layout.addWidget(info)

        form = QFormLayout()

        self.target_combo = QComboBox()
        self.load_target_courses()
        form.addRow('目标课程*：', self.target_combo)

        self.reason_edit = QTextEdit()
        self.reason_edit.setFixedHeight(100)
        form.addRow('调课原因：', self.reason_edit)

        layout.addLayout(form)

        buttons = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def load_target_courses(self):
        try:
            courses = RegistrationService.get_available_transfer_courses(
                self.registration['id']
            )
            if not courses:
                self.target_combo.addItem('暂无可用的同主题课程', None)
                return

            for course in courses:
                display = f'{course["title"]} ({course["start_time"][:16]}) - {course["venue"]}'
                self.target_combo.addItem(display, course['id'])
        except ValidationError as e:
            QMessageBox.warning(self, '错误', str(e))

    def accept(self):
        target_id = self.target_combo.currentData()
        if not target_id:
            QMessageBox.warning(self, '提示', '请选择目标课程')
            return

        reason = self.reason_edit.toPlainText().strip()
        try:
            RegistrationService.request_transfer(
                self.registration['id'], target_id, reason
            )
            QMessageBox.information(self, '成功', '调课申请已提交，等待管理员审核')
            super().accept()
        except ValidationError as e:
            QMessageBox.warning(self, '申请失败', str(e))

class TransferReviewDialog(QDialog):
    def __init__(self, request, parent=None):
        super().__init__(parent)
        self.request = request
        self.setWindowTitle('审核调课申请')
        self.resize(500, 500)
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)

        info = QLabel(
            f'学员：{self.request["student_name"]} ({self.request["employee_id"]})\n'
            f'原课程：{self.request["from_course_title"]}\n'
            f'目标课程：{self.request["to_course_title"]}\n'
            f'课程主题：{self.request["course_theme"]}\n'
            f'申请时间：{self.request["requested_at"][:19]}'
        )
        info.setStyleSheet('padding: 10px; background: #f0f0f0; border-radius: 5px;')
        info.setWordWrap(True)
        layout.addWidget(info)

        if self.request.get('reason'):
            reason_label = QLabel(f'申请原因：{self.request["reason"]}')
            reason_label.setWordWrap(True)
            reason_label.setStyleSheet('padding: 10px; background: #fff8e1; border-radius: 5px;')
            layout.addWidget(reason_label)

        form = QFormLayout()
        self.note_edit = QTextEdit()
        self.note_edit.setFixedHeight(100)
        self.note_edit.setPlaceholderText('填写审核意见（驳回时必填）')
        form.addRow('审核意见：', self.note_edit)
        layout.addLayout(form)

        btn_layout = QHBoxLayout()
        approve_btn = QPushButton('通过')
        approve_btn.setStyleSheet('background: #4caf50; color: white; padding: 8px 20px;')
        approve_btn.clicked.connect(lambda: self.review(True))
        btn_layout.addWidget(approve_btn)

        reject_btn = QPushButton('驳回')
        reject_btn.setStyleSheet('background: #f44336; color: white; padding: 8px 20px;')
        reject_btn.clicked.connect(lambda: self.review(False))
        btn_layout.addWidget(reject_btn)

        cancel_btn = QPushButton('取消')
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(cancel_btn)

        layout.addLayout(btn_layout)

    def review(self, approved):
        note = self.note_edit.toPlainText().strip()
        try:
            RegistrationService.review_transfer(
                self.request['id'], approved, note
            )
            QMessageBox.information(self, '成功', '审核完成')
            super().accept()
        except ValidationError as e:
            QMessageBox.warning(self, '审核失败', str(e))

class CheckInDialog(QDialog):
    def __init__(self, course_id, parent=None):
        super().__init__(parent)
        self.course_id = course_id
        self.setWindowTitle('签到')
        self.resize(400, 200)
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)

        hint = QLabel('请输入学员工号进行签到：')
        layout.addWidget(hint)

        self.emp_id_edit = QLineEdit()
        self.emp_id_edit.setPlaceholderText('输入工号后按回车')
        self.emp_id_edit.returnPressed.connect(self.do_checkin)
        layout.addWidget(self.emp_id_edit)

        self.result_label = QLabel('')
        self.result_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.result_label)

        btn_layout = QHBoxLayout()
        ok_btn = QPushButton('签到')
        ok_btn.clicked.connect(self.do_checkin)
        btn_layout.addWidget(ok_btn)

        close_btn = QPushButton('关闭')
        close_btn.clicked.connect(self.accept)
        btn_layout.addWidget(close_btn)

        layout.addLayout(btn_layout)

    def do_checkin(self):
        emp_id = self.emp_id_edit.text().strip()
        if not emp_id:
            self.result_label.setText('请输入工号')
            self.result_label.setStyleSheet('color: #f44336;')
            return

        try:
            AttendanceService.check_in(self.course_id, emp_id)
            self.result_label.setText(f'✓ 签到成功！{emp_id}')
            self.result_label.setStyleSheet('color: #4caf50; font-weight: bold;')
            self.emp_id_edit.clear()
            self.emp_id_edit.setFocus()
        except ValidationError as e:
            self.result_label.setText(f'✗ {str(e)}')
            self.result_label.setStyleSheet('color: #f44336;')

class MakeupRequestDialog(QDialog):
    def __init__(self, course_id, student_id, student_name, parent=None):
        super().__init__(parent)
        self.course_id = course_id
        self.student_id = student_id
        self.student_name = student_name
        self.setWindowTitle('申请补签')
        self.resize(400, 300)
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)

        info = QLabel(f'学员：{self.student_name}')
        info.setStyleSheet('padding: 10px; background: #f0f0f0; border-radius: 5px;')
        layout.addWidget(info)

        form = QFormLayout()
        self.reason_edit = QTextEdit()
        self.reason_edit.setPlaceholderText('请详细说明补签原因（至少5个字符）')
        self.reason_edit.setFixedHeight(120)
        form.addRow('补签原因*：', self.reason_edit)
        layout.addLayout(form)

        buttons = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def accept(self):
        reason = self.reason_edit.toPlainText().strip()
        try:
            AttendanceService.request_makeup(
                self.course_id, self.student_id, reason
            )
            QMessageBox.information(self, '成功', '补签申请已提交，等待审核')
            super().accept()
        except ValidationError as e:
            QMessageBox.warning(self, '提交失败', str(e))

class MakeupReviewDialog(QDialog):
    def __init__(self, makeup, parent=None):
        super().__init__(parent)
        self.makeup = makeup
        self.setWindowTitle('审核补签申请')
        self.resize(500, 500)
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)

        info = QLabel(
            f'学员：{self.makeup["student_name"]} ({self.makeup["employee_id"]})\n'
            f'课程：{self.makeup["course_title"]}\n'
            f'课程时间：{self.makeup["course_time"][:16]}\n'
            f'申请时间：{self.makeup["makeup_requested_at"][:19]}'
        )
        info.setStyleSheet('padding: 10px; background: #f0f0f0; border-radius: 5px;')
        info.setWordWrap(True)
        layout.addWidget(info)

        if self.makeup.get('makeup_reason'):
            reason_label = QLabel(f'补签原因：{self.makeup["makeup_reason"]}')
            reason_label.setWordWrap(True)
            reason_label.setStyleSheet('padding: 10px; background: #fff8e1; border-radius: 5px;')
            layout.addWidget(reason_label)

        form = QFormLayout()
        self.note_edit = QTextEdit()
        self.note_edit.setFixedHeight(100)
        self.note_edit.setPlaceholderText('填写审核意见（驳回时必填）')
        form.addRow('审核意见：', self.note_edit)
        layout.addLayout(form)

        btn_layout = QHBoxLayout()
        approve_btn = QPushButton('通过补签')
        approve_btn.setStyleSheet('background: #4caf50; color: white; padding: 8px 20px;')
        approve_btn.clicked.connect(lambda: self.review(True))
        btn_layout.addWidget(approve_btn)

        reject_btn = QPushButton('驳回')
        reject_btn.setStyleSheet('background: #f44336; color: white; padding: 8px 20px;')
        reject_btn.clicked.connect(lambda: self.review(False))
        btn_layout.addWidget(reject_btn)

        cancel_btn = QPushButton('取消')
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(cancel_btn)

        layout.addLayout(btn_layout)

    def review(self, approved):
        note = self.note_edit.toPlainText().strip()
        try:
            AttendanceService.review_makeup(
                self.makeup['id'], approved, '管理员', note
            )
            QMessageBox.information(self, '成功', '审核完成')
            super().accept()
        except ValidationError as e:
            QMessageBox.warning(self, '审核失败', str(e))

class DateRangeDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle('选择日期范围')
        self.resize(300, 150)
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        form = QFormLayout()

        today = QDate.currentDate()
        self.start_edit = QDateEdit(today.addMonths(-1))
        self.start_edit.setDisplayFormat('yyyy-MM-dd')
        self.start_edit.setCalendarPopup(True)
        form.addRow('开始日期：', self.start_edit)

        self.end_edit = QDateEdit(today)
        self.end_edit.setDisplayFormat('yyyy-MM-dd')
        self.end_edit.setCalendarPopup(True)
        form.addRow('结束日期：', self.end_edit)

        layout.addLayout(form)

        buttons = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def get_range(self):
        return (
            self.start_edit.date().toString('yyyy-MM-dd'),
            self.end_edit.date().toString('yyyy-MM-dd')
        )

class BatchImportResultDialog(QDialog):
    def __init__(self, import_result, parent=None):
        super().__init__(parent)
        self.import_result = import_result
        self.setWindowTitle('批量导入结果')
        self.resize(900, 600)
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)

        summary_frame = QFrame()
        summary_frame.setStyleSheet('background: #f5f5f5; border-radius: 8px; padding: 15px;')
        summary_layout = QVBoxLayout(summary_frame)

        title = QLabel(f'课程：{self.import_result.get("course_title", "")}')
        title.setStyleSheet('font-size: 16px; font-weight: bold;')
        summary_layout.addWidget(title)

        stats_layout = QHBoxLayout()
        total_label = QLabel(f'总行数：<b>{self.import_result.get("total", 0)}</b>')
        total_label.setStyleSheet('font-size: 14px;')
        stats_layout.addWidget(total_label)

        success_count = self.import_result.get("success_count", 0)
        success_label = QLabel(f'成功：<b><span style="color: #4caf50;">{success_count}</span></b>')
        success_label.setStyleSheet('font-size: 14px;')
        stats_layout.addWidget(success_label)

        failure_count = self.import_result.get("failure_count", 0)
        failure_label = QLabel(f'失败：<b><span style="color: #f44336;">{failure_count}</span></b>')
        failure_label.setStyleSheet('font-size: 14px;')
        stats_layout.addWidget(failure_label)

        stats_layout.addStretch()
        summary_layout.addLayout(stats_layout)
        layout.addWidget(summary_frame)

        detail_label = QLabel('处理明细：')
        detail_label.setStyleSheet('font-size: 14px; font-weight: bold; margin-top: 10px;')
        layout.addWidget(detail_label)

        self.table = QTableWidget()
        self.table.setColumnCount(7)
        self.table.setHorizontalHeaderLabels([
            '行号', '姓名', '工号', '部门', '联系方式', '处理结果', '失败原因'
        ])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)

        rows = self.import_result.get('rows', [])
        self.table.setRowCount(len(rows))

        for row_idx, row_data in enumerate(rows):
            self.table.setItem(row_idx, 0, QTableWidgetItem(str(row_data.get('row_number', ''))))
            self.table.setItem(row_idx, 1, QTableWidgetItem(row_data.get('name', '')))
            self.table.setItem(row_idx, 2, QTableWidgetItem(row_data.get('employee_id', '')))
            self.table.setItem(row_idx, 3, QTableWidgetItem(row_data.get('department', '')))
            self.table.setItem(row_idx, 4, QTableWidgetItem(row_data.get('phone', '')))

            if row_data.get('success'):
                result_item = QTableWidgetItem('成功')
                result_item.setForeground(QBrush(QColor(76, 175, 80)))
                result_item.setBackground(QBrush(QColor(232, 245, 233)))
            else:
                result_item = QTableWidgetItem('失败')
                result_item.setForeground(QBrush(QColor(244, 67, 54)))
                result_item.setBackground(QBrush(QColor(255, 235, 238)))
            self.table.setItem(row_idx, 5, result_item)

            failure_reason = row_data.get('failure_reason', '')
            reason_item = QTableWidgetItem(failure_reason)
            if failure_reason:
                reason_item.setForeground(QBrush(QColor(244, 67, 54)))
            self.table.setItem(row_idx, 6, reason_item)

        layout.addWidget(self.table, 1)

        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        export_btn = QPushButton('导出结果')
        export_btn.setStyleSheet('background: #2196f3; color: white; padding: 8px 20px;')
        export_btn.clicked.connect(self.export_result)
        btn_layout.addWidget(export_btn)

        close_btn = QPushButton('关闭')
        close_btn.setStyleSheet('padding: 8px 20px;')
        close_btn.clicked.connect(self.accept)
        btn_layout.addWidget(close_btn)

        layout.addLayout(btn_layout)

    def export_result(self):
        try:
            path = ExportService.export_import_result(self.import_result)
            QMessageBox.information(self, '导出成功', f'导入结果已导出到：\n{path}')
        except Exception as e:
            QMessageBox.warning(self, '导出失败', str(e))

class BatchOperationConfirmDialog(QDialog):
    def __init__(self, summary, parent=None):
        super().__init__(parent)
        self.summary = summary
        self.setWindowTitle(f'确认{summary["operation_cn"]}')
        self.resize(600, 500)
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)

        summary_frame = QFrame()
        summary_frame.setStyleSheet('background: #fff3e0; border-radius: 8px; padding: 15px;')
        summary_layout = QVBoxLayout(summary_frame)

        op_type = self.summary.get('operation_cn', '')
        title = QLabel(f'<h3>{op_type}确认</h3>')
        summary_layout.addWidget(title)

        info_parts = [
            f'原课程：<b>{self.summary.get("course_title", "")}</b>',
            f'操作数量：<b>{self.summary.get("count", 0)}</b> 人'
        ]

        if self.summary.get('target_course_title'):
            target_course_info = (
                f'目标课程：<b>{self.summary.get("target_course_title", "")}</b><br>'
                f'目标课程容量：{self.summary.get("target_current", 0)}/'
                f'{self.summary.get("target_capacity", 0)}，'
                f'剩余名额：<b>{self.summary.get("target_available", 0)}</b>'
            )
            info_parts.append(target_course_info)

        if self.summary.get('target_status_cn'):
            info_parts.append(f'目标状态：<b>{self.summary.get("target_status_cn", "")}</b>')

        info_label = QLabel('<br>'.join(info_parts))
        info_label.setWordWrap(True)
        summary_layout.addWidget(info_label)

        warnings = self.summary.get('warnings', [])
        if warnings:
            warning_label = QLabel(
                '<b><span style="color: #f44336;">⚠️ 注意事项：</span></b>'
            )
            summary_layout.addWidget(warning_label)

            warning_text = '<br>'.join([f'• {w}' for w in warnings])
            warning_content = QLabel(warning_text)
            warning_content.setStyleSheet('color: #e65100;')
            warning_content.setWordWrap(True)
            summary_layout.addWidget(warning_content)

        layout.addWidget(summary_frame)

        detail_label = QLabel(f'涉及学员名单（共 {self.summary.get("count", 0)} 人）：')
        detail_label.setStyleSheet('font-size: 14px; font-weight: bold; margin-top: 10px;')
        layout.addWidget(detail_label)

        self.table = QTableWidget()
        self.table.setColumnCount(5)
        self.table.setHorizontalHeaderLabels(['工号', '姓名', '部门', '当前状态', '操作'])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)

        students = self.summary.get('students', [])
        self.table.setRowCount(len(students))

        for row, student in enumerate(students):
            self.table.setItem(row, 0, QTableWidgetItem(student.get('employee_id', '')))
            self.table.setItem(row, 1, QTableWidgetItem(student.get('name', '')))
            self.table.setItem(row, 2, QTableWidgetItem(student.get('department', '')))

            status_item = QTableWidgetItem(student.get('current_status_cn', ''))
            if student.get('current_status') == 'cancelled':
                status_item.setForeground(QBrush(QColor(158, 158, 158)))
            elif student.get('current_status') == 'transferred_out':
                status_item.setForeground(QBrush(QColor(255, 152, 0)))
            self.table.setItem(row, 3, status_item)

            op_type = self.summary.get('operation_type', '')
            if op_type == 'cancel':
                op_text = '取消报名'
                op_color = QColor(244, 67, 54)
            elif op_type == 'transfer':
                op_text = f'调至{self.summary.get("target_course_title", "")}'
                op_color = QColor(33, 150, 243)
            else:
                op_text = f'改为{self.summary.get("target_status_cn", "")}'
                op_color = QColor(156, 39, 176)

            op_item = QTableWidgetItem(op_text)
            op_item.setForeground(QBrush(op_color))
            self.table.setItem(row, 4, op_item)

        layout.addWidget(self.table, 1)

        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        confirm_btn = QPushButton('确认执行')
        confirm_btn.setStyleSheet(
            'background: #f44336; color: white; padding: 10px 30px; font-weight: bold;'
        )
        confirm_btn.clicked.connect(self.accept)
        btn_layout.addWidget(confirm_btn)

        cancel_btn = QPushButton('取消')
        cancel_btn.setStyleSheet('padding: 10px 30px;')
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(cancel_btn)

        layout.addLayout(btn_layout)

class BatchOperationResultDialog(QDialog):
    def __init__(self, result, parent=None):
        super().__init__(parent)
        self.result = result
        self.setWindowTitle(f'{result["operation_cn"]}结果')
        self.resize(900, 600)
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)

        summary_frame = QFrame()
        summary_frame.setStyleSheet('background: #f5f5f5; border-radius: 8px; padding: 15px;')
        summary_layout = QVBoxLayout(summary_frame)

        op_type = self.result.get('operation_cn', '')
        title = QLabel(f'<h3>{op_type}完成</h3>')
        summary_layout.addWidget(title)

        info_parts = [f'原课程：<b>{self.result.get("course_title", "")}</b>']

        if self.result.get('target_course_title'):
            info_parts.append(f'目标课程：<b>{self.result.get("target_course_title", "")}</b>')

        if self.result.get('target_status_cn'):
            info_parts.append(f'目标状态：<b>{self.result.get("target_status_cn", "")}</b>')

        info_label = QLabel('<br>'.join(info_parts))
        info_label.setWordWrap(True)
        summary_layout.addWidget(info_label)

        stats_layout = QHBoxLayout()
        total_label = QLabel(f'处理总数：<b>{self.result.get("total", 0)}</b>')
        total_label.setStyleSheet('font-size: 14px;')
        stats_layout.addWidget(total_label)

        success_count = self.result.get('success_count', 0)
        success_label = QLabel(
            f'成功：<b><span style="color: #4caf50;">{success_count}</span></b>'
        )
        success_label.setStyleSheet('font-size: 14px;')
        stats_layout.addWidget(success_label)

        failure_count = self.result.get('failure_count', 0)
        failure_label = QLabel(
            f'失败：<b><span style="color: #f44336;">{failure_count}</span></b>'
        )
        failure_label.setStyleSheet('font-size: 14px;')
        stats_layout.addWidget(failure_label)

        stats_layout.addStretch()
        summary_layout.addLayout(stats_layout)
        layout.addWidget(summary_frame)

        detail_label = QLabel('处理明细：')
        detail_label.setStyleSheet('font-size: 14px; font-weight: bold; margin-top: 10px;')
        layout.addWidget(detail_label)

        self.table = QTableWidget()

        op_type = self.result.get('operation_type', '')
        if op_type == 'transfer':
            self.table.setColumnCount(9)
            self.table.setHorizontalHeaderLabels([
                '序号', '姓名', '工号', '部门',
                '原课程', '目标课程',
                '原状态', '处理结果', '失败原因'
            ])
        elif op_type == 'cancel':
            self.table.setColumnCount(8)
            self.table.setHorizontalHeaderLabels([
                '序号', '姓名', '工号', '部门',
                '原课程', '原状态', '处理结果', '失败原因'
            ])
        else:
            self.table.setColumnCount(8)
            self.table.setHorizontalHeaderLabels([
                '序号', '姓名', '工号', '部门',
                '课程', '原状态', '处理结果', '失败原因'
            ])

        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)

        rows = self.result.get('rows', [])
        self.table.setRowCount(len(rows))

        for row_idx, row_data in enumerate(rows):
            self.table.setItem(row_idx, 0, QTableWidgetItem(str(row_idx + 1)))
            self.table.setItem(row_idx, 1, QTableWidgetItem(row_data.get('name', '')))
            self.table.setItem(row_idx, 2, QTableWidgetItem(row_data.get('employee_id', '')))
            self.table.setItem(row_idx, 3, QTableWidgetItem(row_data.get('department', '')))

            if op_type == 'transfer':
                self.table.setItem(row_idx, 4, QTableWidgetItem(row_data.get('from_course_title', '')))
                self.table.setItem(row_idx, 5, QTableWidgetItem(row_data.get('to_course_title', '')))
                self.table.setItem(row_idx, 6, QTableWidgetItem(row_data.get('old_status_cn', row_data.get('old_status', ''))))
                result_col = 7
                reason_col = 8
            elif op_type == 'cancel':
                self.table.setItem(row_idx, 4, QTableWidgetItem(self.result.get('course_title', '')))
                self.table.setItem(row_idx, 5, QTableWidgetItem(row_data.get('old_status_cn', row_data.get('old_status', ''))))
                result_col = 6
                reason_col = 7
            else:
                self.table.setItem(row_idx, 4, QTableWidgetItem(self.result.get('course_title', '')))
                status_text = f'{row_data.get("old_status_cn", "")} → {row_data.get("new_status_cn", "")}'
                self.table.setItem(row_idx, 5, QTableWidgetItem(status_text))
                result_col = 6
                reason_col = 7

            if row_data.get('success'):
                result_item = QTableWidgetItem('成功')
                result_item.setForeground(QBrush(QColor(76, 175, 80)))
                result_item.setBackground(QBrush(QColor(232, 245, 233)))
            else:
                result_item = QTableWidgetItem('失败')
                result_item.setForeground(QBrush(QColor(244, 67, 54)))
                result_item.setBackground(QBrush(QColor(255, 235, 238)))
            self.table.setItem(row_idx, result_col, result_item)

            failure_reason = row_data.get('failure_reason', '')
            reason_item = QTableWidgetItem(failure_reason)
            if failure_reason:
                reason_item.setForeground(QBrush(QColor(244, 67, 54)))
            self.table.setItem(row_idx, reason_col, reason_item)

        layout.addWidget(self.table, 1)

        btn_layout = QHBoxLayout()

        undo_btn = None
        if UndoManager.has_undo_available() and success_count > 0:
            undo_btn = QPushButton('撤销此操作')
            undo_btn.setStyleSheet(
                'background: #ff9800; color: white; padding: 8px 20px; font-weight: bold;'
            )
            undo_btn.clicked.connect(self.undo_operation)
            btn_layout.addWidget(undo_btn)

        btn_layout.addStretch()

        export_btn = QPushButton('导出结果')
        export_btn.setStyleSheet('background: #2196f3; color: white; padding: 8px 20px;')
        export_btn.clicked.connect(self.export_result)
        btn_layout.addWidget(export_btn)

        close_btn = QPushButton('关闭')
        close_btn.setStyleSheet('padding: 8px 20px;')
        close_btn.clicked.connect(self.accept)
        btn_layout.addWidget(close_btn)

        layout.addLayout(btn_layout)

    def export_result(self):
        try:
            path = ExportService.export_batch_operation_result(self.result)
            QMessageBox.information(self, '导出成功', f'操作结果已导出到：\n{path}')
        except Exception as e:
            QMessageBox.warning(self, '导出失败', str(e))

    def undo_operation(self):
        undo_info = UndoManager.get_last_undo_info()
        if not undo_info:
            QMessageBox.warning(self, '提示', '没有可撤销的操作')
            return

        reply = QMessageBox.question(
            self, '确认撤销',
            f'确定要撤销「{undo_info["operation_cn"]}」吗？\n'
            f'将恢复 {undo_info["success_count"]} 条成功的记录。',
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )

        if reply != QMessageBox.Yes:
            return

        try:
            undo_result = UndoManager.undo_last_operation()
            QMessageBox.information(
                self, '撤销完成',
                f'撤销操作完成：\n'
                f'成功恢复：{undo_result["success_count"]} 条\n'
                f'失败：{undo_result["failure_count"]} 条'
            )
            self.accept()
        except ValidationError as e:
            QMessageBox.warning(self, '撤销失败', str(e))

class BatchTargetCourseDialog(QDialog):
    def __init__(self, course_id, parent=None):
        super().__init__(parent)
        self.course_id = course_id
        self.target_course_id = None
        self.setWindowTitle('选择目标课程')
        self.resize(500, 400)
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)

        hint_label = QLabel('请选择要转移到的同主题课程：')
        hint_label.setStyleSheet('font-size: 14px; margin-bottom: 10px;')
        layout.addWidget(hint_label)

        self.course_list = QListWidget()
        self.course_list.itemDoubleClicked.connect(lambda _: self.accept())
        layout.addWidget(self.course_list, 1)

        self.load_courses()

        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        ok_btn = QPushButton('确定')
        ok_btn.setStyleSheet('background: #4caf50; color: white; padding: 8px 20px;')
        ok_btn.clicked.connect(self.accept)
        btn_layout.addWidget(ok_btn)

        cancel_btn = QPushButton('取消')
        cancel_btn.setStyleSheet('padding: 8px 20px;')
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(cancel_btn)

        layout.addLayout(btn_layout)

    def load_courses(self):
        try:
            courses = BatchOperationService.get_available_target_courses(self.course_id)
            if not courses:
                self.course_list.addItem('暂无可用的同主题课程')
                return

            for course in courses:
                count = RegistrationService.get_course_registrations(course['id'])
                display_text = (
                    f'{course["title"]}\n'
                    f'  时间：{course["start_time"][:16]} ~ {course["end_time"][11:16]}\n'
                    f'  场地：{course["venue"]} | 讲师：{course["instructor"]}\n'
                    f'  容量：{len(count)}/{course["capacity"]} 人'
                )
                item = QListWidgetItem(display_text)
                item.setData(Qt.UserRole, course['id'])
                if len(count) >= course['capacity']:
                    item.setForeground(QBrush(QColor(244, 67, 54)))
                    display_text += ' (已满)'
                    item.setText(display_text)
                self.course_list.addItem(item)
        except ValidationError as e:
            QMessageBox.warning(self, '错误', str(e))

    def get_target_course_id(self):
        current_item = self.course_list.currentItem()
        if current_item:
            return current_item.data(Qt.UserRole)
        return None

class BatchTargetStatusDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.target_status = None
        self.setWindowTitle('选择目标状态')
        self.resize(400, 300)
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)

        hint_label = QLabel('请选择要设置的目标状态：')
        hint_label.setStyleSheet('font-size: 14px; margin-bottom: 10px;')
        layout.addWidget(hint_label)

        self.status_combo = QComboBox()
        self.status_combo.addItem('已报名', 'registered')
        self.status_combo.addItem('已出勤', 'attended')
        self.status_combo.addItem('缺勤', 'absent')
        self.status_combo.addItem('已取消', 'cancelled')
        self.status_combo.addItem('已转出', 'transferred_out')
        layout.addWidget(self.status_combo)

        layout.addStretch()

        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        ok_btn = QPushButton('确定')
        ok_btn.setStyleSheet('background: #4caf50; color: white; padding: 8px 20px;')
        ok_btn.clicked.connect(self.accept)
        btn_layout.addWidget(ok_btn)

        cancel_btn = QPushButton('取消')
        cancel_btn.setStyleSheet('padding: 8px 20px;')
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(cancel_btn)

        layout.addLayout(btn_layout)

    def get_target_status(self):
        return self.status_combo.currentData()

class UndoDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle('撤销批量操作')
        self.resize(600, 400)
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)

        undo_info = UndoManager.get_last_undo_info()

        if not undo_info:
            info_label = QLabel('当前没有可撤销的批量操作。')
            info_label.setAlignment(Qt.AlignCenter)
            info_label.setStyleSheet('font-size: 14px; color: #666;')
            layout.addWidget(info_label)

            btn_layout = QHBoxLayout()
            btn_layout.addStretch()
            close_btn = QPushButton('关闭')
            close_btn.setStyleSheet('padding: 8px 20px;')
            close_btn.clicked.connect(self.reject)
            btn_layout.addWidget(close_btn)
            layout.addLayout(btn_layout)
            return

        summary_frame = QFrame()
        summary_frame.setStyleSheet('background: #e3f2fd; border-radius: 8px; padding: 15px;')
        summary_layout = QVBoxLayout(summary_frame)

        title = QLabel(f'<h3>可撤销的操作：{undo_info["operation_cn"]}</h3>')
        summary_layout.addWidget(title)

        info_text = (
            f'操作时间：{undo_info["created_at"][:19]}<br>'
            f'操作成功记录数：<b>{undo_info["success_count"]}</b> / 总记录数：{undo_info["total_count"]}<br>'
            f'<span style="color: #ff9800;">⚠️ 撤销将恢复所有成功变更的记录，包括：</span><br>'
            f'• 批量取消：恢复为原状态<br>'
            f'• 批量改状态：恢复为原状态<br>'
            f'• 批量调课：删除目标课程的报名，恢复原课程报名'
        )
        info_label = QLabel(info_text)
        info_label.setWordWrap(True)
        summary_layout.addWidget(info_label)

        layout.addWidget(summary_frame)

        detail_label = QLabel('将恢复以下学员的记录：')
        detail_label.setStyleSheet('font-size: 14px; font-weight: bold; margin-top: 10px;')
        layout.addWidget(detail_label)

        self.table = QTableWidget()
        self.table.setColumnCount(4)
        self.table.setHorizontalHeaderLabels(['工号', '姓名', '操作类型', '备注'])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)

        items = undo_info.get('items', [])
        self.table.setRowCount(len(items))

        for row, item in enumerate(items):
            self.table.setItem(row, 0, QTableWidgetItem(item.get('employee_id', '')))
            self.table.setItem(row, 1, QTableWidgetItem(item.get('student_name', '')))

            op_type = undo_info['operation_type']
            if op_type == 'cancel':
                op_text = '撤销取消 → 恢复原状态'
            elif op_type == 'transfer':
                op_text = f'撤销调课 → 从【{item.get("to_course_title", "")}】返回【{item.get("from_course_title", "")}】'
            else:
                op_text = f'撤销改状态 → 恢复原状态'

            self.table.setItem(row, 2, QTableWidgetItem(op_text))

            undo_data = item.get('undo_data')
            if undo_data and undo_data.get('old_status'):
                old_status_cn = {
                    'registered': '已报名',
                    'cancelled': '已取消',
                    'transferred_out': '已转出',
                    'attended': '已出勤',
                    'absent': '缺勤'
                }.get(undo_data['old_status'], undo_data['old_status'])
                self.table.setItem(row, 3, QTableWidgetItem(f'原状态：{old_status_cn}'))

        layout.addWidget(self.table, 1)

        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        undo_btn = QPushButton('确认撤销')
        undo_btn.setStyleSheet(
            'background: #ff9800; color: white; padding: 10px 30px; font-weight: bold;'
        )
        undo_btn.clicked.connect(self.do_undo)
        btn_layout.addWidget(undo_btn)

        cancel_btn = QPushButton('取消')
        cancel_btn.setStyleSheet('padding: 10px 30px;')
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(cancel_btn)

        layout.addLayout(btn_layout)

    def do_undo(self):
        try:
            undo_result = UndoManager.undo_last_operation()
            QMessageBox.information(
                self, '撤销完成',
                f'撤销操作完成：\n\n'
                f'成功恢复：{undo_result["success_count"]} 条\n'
                f'失败：{undo_result["failure_count"]} 条\n\n'
                f'容量占用、报名状态已自动恢复。'
            )
            self.accept()
        except ValidationError as e:
            QMessageBox.warning(self, '撤销失败', str(e))
