import csv
from datetime import datetime
from db.dao import (
    WaitingListDAO, WaitingListResultDAO,
    CourseDAO, StudentDAO, RegistrationDAO, ExceptionLogDAO
)
from .course_service import ValidationError


class WaitingListService:
    @staticmethod
    def _validate_waiting_list(course_id, student_data):
        course = CourseDAO.get_by_id(course_id)
        if not course:
            raise ValidationError('课程不存在')

        if course['status'] != 'published':
            raise ValidationError('课程未发布，不能添加候补')

        if not student_data.get('name') or not student_data.get('employee_id'):
            raise ValidationError('姓名和工号不能为空')

        student_id = StudentDAO.get_or_create(student_data)

        if WaitingListDAO.exists(course_id, student_id, 'waiting'):
            raise ValidationError('该学员已在候补队列中')

        if RegistrationDAO.exists(course_id, student_id):
            raise ValidationError('该学员已报名此课程')

        return course, student_id

    @staticmethod
    def add_to_waiting_list(course_id, student_data, priority=0, source='manual', note=''):
        course, student_id = WaitingListService._validate_waiting_list(course_id, student_data)

        waiting_id = WaitingListDAO.create(
            course_id, student_id, priority, source, note
        )

        if waiting_id is None:
            raise ValidationError('该学员已在候补队列中')

        ExceptionLogDAO.create(
            'waiting_list_added',
            f'学员 {student_data["name"]}({student_data["employee_id"]}) '
            f'已加入课程【{course["title"]}】候补队列，'
            f'优先级：{priority}，来源：{source}',
            course_id=course_id,
            student_id=student_id
        )

        return waiting_id

    @staticmethod
    def batch_import_waiting_list(course_id, csv_file_path):
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
                priority_col = None
                note_col = None

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
                    elif col_lower in ['优先级', 'priority'] and priority_col is None:
                        priority_col = col
                    elif col_lower in ['备注', 'note', 'remark'] and note_col is None:
                        note_col = col

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

                    priority_str = (row.get(priority_col) or '').strip() if priority_col else '0'
                    try:
                        priority = int(priority_str)
                    except (ValueError, TypeError):
                        priority = 0

                    note = (row.get(note_col) or '').strip() if note_col else ''

                    row_result = {
                        'row_number': line_num,
                        'name': name,
                        'employee_id': employee_id,
                        'department': department,
                        'phone': phone,
                        'priority': priority,
                        'success': False,
                        'failure_reason': ''
                    }

                    if not name or not employee_id:
                        row_result['failure_reason'] = '缺少必填字段：姓名或工号不能为空'
                        ExceptionLogDAO.create(
                            'waiting_list_import_error',
                            f'候补导入第 {line_num} 行失败：缺少必填字段，'
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
                        waiting_id = WaitingListService.add_to_waiting_list(
                            course_id, student_data, priority, 'csv_import', note
                        )
                        row_result['success'] = True
                        row_result['waiting_list_id'] = waiting_id
                        results['success_count'] += 1
                    except ValidationError as e:
                        row_result['failure_reason'] = str(e)
                        try:
                            student = StudentDAO.get_by_employee_id(employee_id)
                            student_id = student['id'] if student else None
                        except:
                            student_id = None
                        ExceptionLogDAO.create(
                            'waiting_list_import_error',
                            f'候补导入第 {line_num} 行失败：{e}，'
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
                            'waiting_list_import_system_error',
                            f'候补导入第 {line_num} 行系统异常：{e}，'
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
    def get_waiting_list(course_id, status='waiting'):
        waiting_list = WaitingListDAO.get_by_course(course_id, status)
        for idx, item in enumerate(waiting_list, 1):
            item['position'] = idx
        return waiting_list

    @staticmethod
    def get_all_waiting_list(status='waiting'):
        return WaitingListDAO.get_all(status)

    @staticmethod
    def get_waiting_count(course_id, status='waiting'):
        return WaitingListDAO.count_by_course(course_id, status)

    @staticmethod
    def remove_from_waiting_list(waiting_id):
        waiting = WaitingListDAO.get_by_id(waiting_id)
        if not waiting:
            raise ValidationError('候补记录不存在')

        success = WaitingListDAO.delete(waiting_id)
        if success:
            ExceptionLogDAO.create(
                'waiting_list_removed',
                f'学员 {waiting["name"]}({waiting["employee_id"]}) '
                f'已从课程【{waiting["course_title"]}】候补队列中移除',
                course_id=waiting['course_id'],
                student_id=waiting['student_id']
            )
        return success

    @staticmethod
    def get_available_slots(course_id):
        course = CourseDAO.get_by_id(course_id)
        if not course:
            raise ValidationError('课程不存在')

        registered_count = RegistrationDAO.count_by_course(course_id)
        return max(0, course['capacity'] - registered_count)

    @staticmethod
    def preview_auto_fill(course_id, slot_count=None):
        course = CourseDAO.get_by_id(course_id)
        if not course:
            raise ValidationError('课程不存在')

        if course['status'] != 'published':
            raise ValidationError('课程未发布，不能执行补位')

        now = datetime.now()
        deadline = datetime.fromisoformat(course['registration_deadline'])
        if now > deadline:
            raise ValidationError('报名已截止，不能执行补位')

        if slot_count is None:
            slot_count = WaitingListService.get_available_slots(course_id)

        if slot_count <= 0:
            raise ValidationError('当前没有可用名额')

        waiting_list = WaitingListService.get_waiting_list(course_id, 'waiting')
        if not waiting_list:
            raise ValidationError('当前没有候补学员')

        preview_items = []
        warnings = []
        can_process_collected = 0

        for waiting in waiting_list:
            if can_process_collected >= slot_count and len(preview_items) >= slot_count:
                break

            student_id = waiting['student_id']
            position = waiting['position']

            item = {
                'waiting_list_id': waiting['id'],
                'position': position,
                'student_id': student_id,
                'name': waiting['name'],
                'employee_id': waiting['employee_id'],
                'department': waiting.get('department', ''),
                'phone': waiting.get('phone', ''),
                'priority': waiting['priority'],
                'source': waiting['source'],
                'added_at': waiting['added_at'],
                'can_process': True,
                'failure_reason': ''
            }

            if RegistrationDAO.exists(course_id, student_id):
                item['can_process'] = False
                item['failure_reason'] = '该学员已报名此课程'
                warnings.append(f'第{position}位 {waiting["name"]}：已报名此课程，将跳过')
            else:
                can_process_collected += 1

            preview_items.append(item)

        can_process_count = sum(1 for item in preview_items if item['can_process'])

        return {
            'course_id': course_id,
            'course_title': course['title'],
            'total_waiting': len(waiting_list),
            'available_slots': slot_count,
            'can_process_count': can_process_count,
            'warnings': warnings,
            'items': preview_items
        }

    @staticmethod
    def execute_auto_fill(course_id, slot_count=None):
        preview = WaitingListService.preview_auto_fill(course_id, slot_count)
        course = CourseDAO.get_by_id(course_id)

        result_items = []
        success_count = 0
        failure_count = 0

        for item in preview['items']:
            result_item = {
                'waiting_list_id': item['waiting_list_id'],
                'original_position': item['position'],
                'student_id': item['student_id'],
                'name': item['name'],
                'employee_id': item['employee_id'],
                'department': item['department'],
                'phone': item['phone'],
                'priority': item['priority'],
                'source': item['source'],
                'result': 'failed',
                'failure_reason': item['failure_reason'],
                'registration_id': None
            }

            if not item['can_process']:
                failure_count += 1
                WaitingListResultDAO.create(
                    course_id,
                    item['waiting_list_id'],
                    item['student_id'],
                    item['position'],
                    item['priority'],
                    item['source'],
                    'failed',
                    item['failure_reason']
                )
                ExceptionLogDAO.create(
                    'waiting_list_fill_failed',
                    f'补位失败：学员 {item["name"]}({item["employee_id"]}) '
                    f'原因：{item["failure_reason"]}',
                    course_id=course_id,
                    student_id=item['student_id']
                )
                result_items.append(result_item)
                continue

            try:
                student_data = {
                    'name': item['name'],
                    'employee_id': item['employee_id'],
                    'department': item['department'],
                    'phone': item['phone']
                }

                from .registration_service import RegistrationService
                reg_id = RegistrationService.register_student(course_id, student_data)

                WaitingListDAO.update_status(
                    item['waiting_list_id'], 'filled',
                    f'补位成功，报名ID：{reg_id}'
                )

                WaitingListResultDAO.create(
                    course_id,
                    item['waiting_list_id'],
                    item['student_id'],
                    item['position'],
                    item['priority'],
                    item['source'],
                    'success',
                    None,
                    reg_id
                )

                result_item['result'] = 'success'
                result_item['registration_id'] = reg_id
                result_item['failure_reason'] = ''
                success_count += 1

                ExceptionLogDAO.create(
                    'waiting_list_filled',
                    f'补位成功：学员 {item["name"]}({item["employee_id"]}) '
                    f'已从候补队列第{item["position"]}位转为正式报名，报名ID：{reg_id}',
                    course_id=course_id,
                    student_id=item['student_id']
                )

            except ValidationError as e:
                result_item['failure_reason'] = str(e)
                failure_count += 1

                WaitingListResultDAO.create(
                    course_id,
                    item['waiting_list_id'],
                    item['student_id'],
                    item['position'],
                    item['priority'],
                    item['source'],
                    'failed',
                    str(e)
                )

                ExceptionLogDAO.create(
                    'waiting_list_fill_failed',
                    f'补位失败：学员 {item["name"]}({item["employee_id"]}) '
                    f'原因：{e}',
                    course_id=course_id,
                    student_id=item['student_id']
                )

            except Exception as e:
                result_item['failure_reason'] = f'系统异常：{e}'
                failure_count += 1

                WaitingListResultDAO.create(
                    course_id,
                    item['waiting_list_id'],
                    item['student_id'],
                    item['position'],
                    item['priority'],
                    item['source'],
                    'failed',
                    f'系统异常：{e}'
                )

                ExceptionLogDAO.create(
                    'waiting_list_fill_system_error',
                    f'补位系统异常：学员 {item["name"]}({item["employee_id"]}) '
                    f'原因：{e}',
                    course_id=course_id,
                    student_id=item['student_id']
                )

            result_items.append(result_item)

        return {
            'course_id': course_id,
            'course_title': course['title'],
            'total': len(result_items),
            'success_count': success_count,
            'failure_count': failure_count,
            'available_slots': preview['available_slots'],
            'items': result_items
        }

    @staticmethod
    def get_fill_results(course_id, limit=100):
        return WaitingListResultDAO.get_latest_by_course(course_id, limit)

    @staticmethod
    def get_all_fill_results(limit=1000):
        return WaitingListResultDAO.get_all(limit)
