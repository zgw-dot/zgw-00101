from datetime import datetime
from db.dao import (
    AttendanceDAO, CourseDAO, StudentDAO,
    RegistrationDAO, ExceptionLogDAO
)
from .course_service import ValidationError

class AttendanceService:
    @staticmethod
    def check_in(course_id, student_identifier):
        course = CourseDAO.get_by_id(course_id)
        if not course:
            raise ValidationError('课程不存在')

        if course['status'] != 'published':
            raise ValidationError('课程未发布')

        course_start = datetime.fromisoformat(course['start_time'])
        course_end = datetime.fromisoformat(course['end_time'])
        now = datetime.now()

        if now < course_start:
            raise ValidationError('课程尚未开始，不能签到')

        if now > course_end:
            raise ValidationError('课程已结束，不能签到')

        if isinstance(student_identifier, int):
            student = StudentDAO.get_by_id(student_identifier)
        else:
            student = StudentDAO.get_by_employee_id(student_identifier)

        if not student:
            raise ValidationError('学员不存在')

        if not RegistrationDAO.exists(course_id, student['id']):
            raise ValidationError('该学员未报名此课程')

        attendance = AttendanceDAO.get_or_create(course_id, student['id'])

        if attendance['status'] == 'present' and not attendance['is_makeup']:
            ExceptionLogDAO.create(
                'duplicate_checkin',
                f'学员 {student["name"]}({student["employee_id"]}) 在课程【{course["title"]}】'
                f'重复签到被拦截',
                course_id=course_id,
                student_id=student['id']
            )
            raise ValidationError('该学员已签到，请勿重复签到')

        success = AttendanceDAO.check_in(course_id, student['id'])
        if not success:
            raise ValidationError('签到失败')

        return True

    @staticmethod
    def get_course_attendance(course_id):
        course = CourseDAO.get_by_id(course_id)
        if not course:
            raise ValidationError('课程不存在')

        registrations = RegistrationDAO.get_by_course(course_id)
        attendances = AttendanceDAO.get_by_course(course_id)

        att_map = {a['student_id']: a for a in attendances}
        result = []

        for reg in registrations:
            student_id = reg['student_id']
            att = att_map.get(student_id)
            if not att:
                att = AttendanceDAO.get_or_create(course_id, student_id)

            result.append({
                'student_id': student_id,
                'name': reg['name'],
                'employee_id': reg['employee_id'],
                'department': reg.get('department', ''),
                'status': att['status'],
                'check_in_time': att.get('check_in_time'),
                'is_makeup': att['is_makeup'],
                'makeup_status': att.get('makeup_status', 'none'),
                'makeup_reason': att.get('makeup_reason', ''),
                'attendance_id': att['id']
            })

        return result

    @staticmethod
    def mark_all_absent(course_id):
        course = CourseDAO.get_by_id(course_id)
        if not course:
            raise ValidationError('课程不存在')

        registrations = RegistrationDAO.get_by_course(course_id)
        marked = 0

        for reg in registrations:
            if AttendanceDAO.mark_absent(course_id, reg['student_id']):
                marked += 1

        return marked

    @staticmethod
    def request_makeup(course_id, student_id, reason):
        if not reason or len(reason.strip()) < 5:
            raise ValidationError('请填写补签原因（至少5个字符）')

        course = CourseDAO.get_by_id(course_id)
        if not course:
            raise ValidationError('课程不存在')

        student = StudentDAO.get_by_id(student_id)
        if not student:
            raise ValidationError('学员不存在')

        if not RegistrationDAO.exists(course_id, student_id):
            raise ValidationError('该学员未报名此课程')

        attendance = AttendanceDAO.get_or_create(course_id, student_id)

        if attendance['makeup_status'] == 'pending':
            raise ValidationError('已有补签申请待审核，请勿重复提交')

        if attendance['makeup_status'] == 'approved':
            raise ValidationError('该学员已通过补签')

        success = AttendanceDAO.request_makeup(course_id, student_id, reason)
        if not success:
            raise ValidationError('补签申请提交失败')

        return True

    @staticmethod
    def get_pending_makeups():
        return AttendanceDAO.get_pending_makeups()

    @staticmethod
    def review_makeup(attendance_id, approved, reviewer='管理员', note=''):
        attendance = None
        conn = None
        try:
            from db.database import get_connection
            conn = get_connection()
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM attendances WHERE id=?', (attendance_id,))
            row = cursor.fetchone()
            if row:
                attendance = dict(row)
        finally:
            if conn:
                conn.close()

        if not attendance:
            raise ValidationError('出勤记录不存在')

        if attendance['makeup_status'] != 'pending':
            raise ValidationError('该补签申请状态不是待审核')

        if not approved and not note:
            raise ValidationError('驳回补签必须填写原因')

        success = AttendanceDAO.review_makeup(attendance_id, approved, reviewer, note)
        if not success:
            raise ValidationError('审核失败')

        return True

    @staticmethod
    def get_student_attendance(student_id):
        return AttendanceDAO.get_by_student(student_id)
