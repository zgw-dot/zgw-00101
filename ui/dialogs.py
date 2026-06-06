from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout, QLabel, QLineEdit,
    QTextEdit, QComboBox, QDateTimeEdit, QSpinBox, QPushButton,
    QMessageBox, QDialogButtonBox, QListWidget, QListWidgetItem,
    QTableWidget, QTableWidgetItem, QHeaderView, QAbstractItemView,
    QInputDialog, QDateEdit
)
from PySide6.QtCore import Qt, QDateTime, QDate
from services import (
    CourseService, RegistrationService, AttendanceService,
    ExportService, ValidationError
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
