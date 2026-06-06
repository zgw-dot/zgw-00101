import csv
from datetime import datetime
from db.dao import (
    RegistrationDAO, CourseDAO, StudentDAO,
    TransferRequestDAO, ExceptionLogDAO
)
from .course_service import ValidationError

class RegistrationService:
    @staticmethod
    def _validate_registration(course_id, student_data):
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

        return course, student_id

    @staticmethod
    def register_student(course_id, student_data):
        course, student_id = RegistrationService._validate_registration(course_id, student_data)
        reg_id = RegistrationDAO.create(course_id, student_id)
        return reg_id

    @staticmethod
    def batch_import_students(course_id, csv_file_path):
        course = CourseDAO.get_by_id(course_id)
        if not course:
            raise ValidationError('课程不存在')

        results = {
            'course_id': course_id,
            'course_title': course['title'],
            'total': 0,
            'success_count': 0,
            'failure_count': 0,
            'rows': []
        }

        try:
            with open(csv_file_path, 'r', encoding='utf-8-sig') as f:
                reader = csv.DictReader(f)
                fieldnames = [name.strip() for name in reader.fieldnames] if reader.fieldnames else []

                name_col = None
                emp_col = None
                dept_col = None
                phone_col = None

                for col in fieldnames:
                    col_lower = col.lower()
                    if col_lower in ['姓名', 'name'] and name_col is None:
                        name_col = col
                    elif col_lower in ['工号', 'employee_id', 'employeeid'] and emp_col is None:
                        emp_col = col
                    elif col_lower in ['部门', 'department'] and dept_col is None:
                        dept_col = col
                    elif col_lower in ['联系方式', '电话', 'phone', 'mobile'] and phone_col is None:
                        phone_col = col

                if name_col is None or emp_col is None:
                    raise ValidationError(
                        'CSV 缺少必填列，必须包含「姓名」和「工号」列（支持英文 name/employee_id）'
                    )

                for line_num, row in enumerate(reader, start=2):
                    results['total'] += 1

                    name = (row.get(name_col) or '').strip()
                    employee_id = (row.get(emp_col) or '').strip()
                    department = (row.get(dept_col) or '').strip() if dept_col else ''
                    phone = (row.get(phone_col) or '').strip() if phone_col else ''

                    row_result = {
                        'row_number': line_num,
                        'name': name,
                        'employee_id': employee_id,
                        'department': department,
                        'phone': phone,
                        'success': False,
                        'failure_reason': ''
                    }

                    if not name or not employee_id:
                        row_result['failure_reason'] = '缺少必填字段：姓名或工号不能为空'
                        ExceptionLogDAO.create(
                            'import_validation_error',
                            f'批量导入第 {line_num} 行失败：缺少必填字段，'
                            f'姓名="{name}", 工号="{employee_id}"',
                            course_id=course_id
                        )
                        results['failure_count'] += 1
                        results['rows'].append(row_result)
                        continue

                    student_data = {
                        'name': name,
                        'employee_id': employee_id,
                        'department': department,
                        'phone': phone
                    }

                    try:
                        reg_id = RegistrationService.register_student(course_id, student_data)
                        row_result['success'] = True
                        row_result['registration_id'] = reg_id
                        results['success_count'] += 1
                    except ValidationError as e:
                        row_result['failure_reason'] = str(e)
                        try:
                            student = StudentDAO.get_by_employee_id(employee_id)
                            student_id = student['id'] if student else None
                        except:
                            student_id = None
                        ExceptionLogDAO.create(
                            'import_validation_error',
                            f'批量导入第 {line_num} 行失败：{e}，'
                            f'学员 {name}({employee_id})',
                            course_id=course_id,
                            student_id=student_id
                        )
                        results['failure_count'] += 1
                    except Exception as e:
                        row_result['failure_reason'] = f'系统异常：{e}'
                        try:
                            student = StudentDAO.get_by_employee_id(employee_id)
                            student_id = student['id'] if student else None
                        except:
                            student_id = None
                        ExceptionLogDAO.create(
                            'import_system_error',
                            f'批量导入第 {line_num} 行系统异常：{e}，'
                            f'学员 {name}({employee_id})',
                            course_id=course_id,
                            student_id=student_id
                        )
                        results['failure_count'] += 1

                    results['rows'].append(row_result)

        except UnicodeDecodeError:
            raise ValidationError('CSV 文件编码错误，请使用 UTF-8 编码')
        except ValidationError:
            raise
        except Exception as e:
            raise ValidationError(f'读取 CSV 文件失败：{e}')

        return results

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
