from datetime import datetime
from db.dao import (
    RegistrationDAO, CourseDAO, StudentDAO,
    TransferRequestDAO, ExceptionLogDAO
)
from .course_service import ValidationError

class RegistrationService:
    @staticmethod
    def register_student(course_id, student_data):
        course = CourseDAO.get_by_id(course_id)
        if not course:
            raise ValidationError('课程不存在')

        if course['status'] != 'published':
            raise ValidationError('课程未发布，不能报名')

        now = datetime.now()
        deadline = datetime.fromisoformat(course['registration_deadline'])
        if now > deadline:
            raise ValidationError('报名已截止')

        if not student_data.get('name') or not student_data.get('employee_id'):
            raise ValidationError('姓名和工号不能为空')

        student_id = StudentDAO.get_or_create(student_data)

        if RegistrationDAO.exists(course_id, student_id):
            raise ValidationError('该学员已报名此课程')

        current_count = RegistrationDAO.count_by_course(course_id)
        if current_count >= course['capacity']:
            ExceptionLogDAO.create(
                'over_capacity',
                f'课程【{course["title"]}】报名人数已达上限 {course["capacity"]} 人，'
                f'学员 {student_data["name"]}({student_data["employee_id"]}) 报名被拒绝',
                course_id=course_id,
                student_id=student_id
            )
            raise ValidationError(
                f'报名失败：课程容量已满（{current_count}/{course["capacity"]}）'
            )

        reg_id = RegistrationDAO.create(course_id, student_id)
        return reg_id

    @staticmethod
    def get_by_id(registration_id):
        return RegistrationDAO.get_by_id(registration_id)

    @staticmethod
    def get_course_registrations(course_id):
        return RegistrationDAO.get_by_course(course_id)

    @staticmethod
    def get_student_registrations(student_id):
        return RegistrationDAO.get_by_student(student_id)

    @staticmethod
    def request_transfer(registration_id, to_course_id, reason=''):
        reg = RegistrationDAO.get_by_id(registration_id)
        if not reg:
            raise ValidationError('报名记录不存在')

        if reg['status'] != 'registered':
            raise ValidationError('当前报名状态不允许调课')

        from_course = CourseDAO.get_by_id(reg['course_id'])
        to_course = CourseDAO.get_by_id(to_course_id)

        if not to_course:
            raise ValidationError('目标课程不存在')

        if to_course['status'] != 'published':
            raise ValidationError('目标课程未发布')

        if from_course['theme'] != to_course['theme']:
            raise ValidationError('只能调到同主题的其他场次')

        now = datetime.now()
        from_deadline = datetime.fromisoformat(from_course['registration_deadline'])
        if now > from_deadline:
            ExceptionLogDAO.create(
                'transfer_after_deadline',
                f'学员 {reg["student_name"]} 申请从课程【{from_course["title"]}】'
                f'调到【{to_course["title"]}】被拒绝：已过报名截止时间',
                course_id=reg['course_id'],
                student_id=reg['student_id']
            )
            raise ValidationError('报名截止后不能申请调课')

        if reg['course_id'] == to_course_id:
            raise ValidationError('不能调到当前课程')

        if RegistrationDAO.exists(to_course_id, reg['student_id']):
            raise ValidationError('该学员已报名目标课程')

        to_count = RegistrationDAO.count_by_course(to_course_id)
        if to_count >= to_course['capacity']:
            raise ValidationError('目标课程容量已满')

        request_id = TransferRequestDAO.create(
            registration_id, reg['course_id'], to_course_id, reason
        )
        return request_id

    @staticmethod
    def get_transfer_requests(status=None):
        return TransferRequestDAO.get_all(status)

    @staticmethod
    def review_transfer(request_id, approved, review_note='', reviewer='管理员'):
        request = TransferRequestDAO.get_by_id(request_id)
        if not request:
            raise ValidationError('调课申请不存在')

        if request['status'] != 'pending':
            raise ValidationError('该申请已处理')

        if approved:
            to_course = CourseDAO.get_by_id(request['to_course_id'])
            to_count = RegistrationDAO.count_by_course(request['to_course_id'])
            if to_count >= to_course['capacity']:
                raise ValidationError('目标课程容量已满，无法通过调课')

            RegistrationDAO.transfer(
                request['registration_id'],
                request['from_course_id'],
                request['to_course_id']
            )
            TransferRequestDAO.review(request_id, 'approved', review_note, reviewer)
        else:
            TransferRequestDAO.review(request_id, 'rejected', review_note, reviewer)

        return True

    @staticmethod
    def get_available_transfer_courses(registration_id):
        reg = RegistrationDAO.get_by_id(registration_id)
        if not reg:
            raise ValidationError('报名记录不存在')

        return CourseDAO.get_by_theme(reg['course_theme'], reg['course_id'])
