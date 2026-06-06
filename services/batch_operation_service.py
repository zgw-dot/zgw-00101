from datetime import datetime
from db.dao import (
    RegistrationDAO, CourseDAO, StudentDAO, ExceptionLogDAO,
    BatchOperationLogDAO, BatchOperationItemDAO, RegistrationDAOExt
)
from .course_service import ValidationError
from .undo_manager import UndoManager

VALID_STATUSES = ['registered', 'cancelled', 'transferred_out', 'attended', 'absent']
STATUS_CN_MAP = {
    'registered': '已报名',
    'cancelled': '已取消',
    'transferred_out': '已转出',
    'attended': '已出勤',
    'absent': '缺勤'
}

class BatchOperationService:
    @staticmethod
    def _validate_and_prepare(course_id, registration_ids, operation_type,
                              target_course_id=None, target_status=None):
        course = CourseDAO.get_by_id(course_id)
        if not course:
            raise ValidationError('课程不存在')

        if course['status'] != 'published':
            raise ValidationError('课程未发布，不能进行批量操作')

        if not registration_ids:
            raise ValidationError('未选择任何报名记录')

        registrations = RegistrationDAOExt.get_registrations_by_ids(registration_ids)
        if len(registrations) != len(registration_ids):
            found_ids = {r['id'] for r in registrations}
            missing = [rid for rid in registration_ids if rid not in found_ids]
            raise ValidationError(f'部分报名记录不存在: {missing}')

        for reg in registrations:
            if reg['course_id'] != course_id:
                raise ValidationError(
                    f'学员 {reg["student_name"]}({reg["employee_id"]}) 不属于当前课程'
                )

        target_course = None
        if target_course_id:
            target_course = CourseDAO.get_by_id(target_course_id)
            if not target_course:
                raise ValidationError('目标课程不存在')
            if target_course['status'] != 'published':
                raise ValidationError('目标课程未发布')
            if course['theme'] != target_course['theme']:
                raise ValidationError('只能调到同主题的其他场次')
            if target_course_id == course_id:
                raise ValidationError('不能调到当前课程')

        return course, registrations, target_course

    @staticmethod
    def _build_summary(operation_type, registrations, course,
                       target_course=None, target_status=None):
        summary = {
            'operation_type': operation_type,
            'operation_cn': {
                'cancel': '批量取消',
                'change_status': '批量改状态',
                'transfer': '批量调课'
            }.get(operation_type, operation_type),
            'course_id': course['id'],
            'course_title': course['title'],
            'count': len(registrations),
            'students': []
        }

        if target_course:
            summary['target_course_id'] = target_course['id']
            summary['target_course_title'] = target_course['title']
            target_count = RegistrationDAO.count_by_course(target_course['id'])
            summary['target_capacity'] = target_course['capacity']
            summary['target_current'] = target_count
            summary['target_available'] = target_course['capacity'] - target_count

        if target_status:
            summary['target_status'] = target_status
            summary['target_status_cn'] = STATUS_CN_MAP.get(target_status, target_status)

        for reg in registrations:
            summary['students'].append({
                'registration_id': reg['id'],
                'student_id': reg['student_id'],
                'name': reg['student_name'],
                'employee_id': reg['employee_id'],
                'department': reg.get('department', ''),
                'current_status': reg['status'],
                'current_status_cn': STATUS_CN_MAP.get(reg['status'], reg['status'])
            })

        return summary

    @staticmethod
    def get_preview(course_id, registration_ids, operation_type,
                    target_course_id=None, target_status=None):
        course, registrations, target_course = BatchOperationService._validate_and_prepare(
            course_id, registration_ids, operation_type,
            target_course_id, target_status
        )

        if operation_type == 'change_status' and target_status not in VALID_STATUSES:
            raise ValidationError(f'无效的目标状态: {target_status}')

        summary = BatchOperationService._build_summary(
            operation_type, registrations, course,
            target_course, target_status
        )

        warnings = []
        if operation_type == 'transfer' and target_course:
            available = target_course['capacity'] - RegistrationDAO.count_by_course(target_course['id'])
            if available < len(registrations):
                warnings.append(
                    f'目标课程容量不足（剩余 {available} 个名额），'
                    f'超出部分将被拦截，最多成功 {available} 人'
                )

        for reg in registrations:
            if operation_type == 'cancel':
                if reg['status'] == 'cancelled':
                    warnings.append(f'学员 {reg["student_name"]} 已取消报名，将被跳过')
                elif reg['status'] == 'transferred_out':
                    warnings.append(f'学员 {reg["student_name"]} 已转出，将被跳过')
            elif operation_type == 'transfer':
                if reg['status'] != 'registered':
                    warnings.append(
                        f'学员 {reg["student_name"]} 当前状态为'
                        f'{STATUS_CN_MAP.get(reg["status"], reg["status"])}，不能调课'
                    )
                elif RegistrationDAO.exists(target_course['id'], reg['student_id']):
                    warnings.append(
                        f'学员 {reg["student_name"]} 已报名目标课程'
                        f'【{target_course["title"]}】，将被拦截'
                    )
            elif operation_type == 'change_status':
                if reg['status'] == target_status:
                    warnings.append(
                        f'学员 {reg["student_name"]} 已是'
                        f'{STATUS_CN_MAP.get(target_status, target_status)}状态，将被跳过'
                    )

        summary['warnings'] = warnings
        return summary

    @staticmethod
    def batch_cancel(course_id, registration_ids, operator='管理员'):
        summary = BatchOperationService.get_preview(
            course_id, registration_ids, 'cancel'
        )
        return BatchOperationService._execute_cancel(summary, operator)

    @staticmethod
    def _execute_cancel(summary, operator):
        course_id = summary['course_id']
        log_id = BatchOperationLogDAO.create(
            operation_type='cancel',
            from_course_id=course_id,
            total_count=summary['count'],
            success_count=0,
            failure_count=0,
            operated_by=operator
        )

        success_count = 0
        failure_count = 0
        result_rows = []

        for student in summary['students']:
            reg_id = student['registration_id']
            student_id = student['student_id']
            result_row = {
                'registration_id': reg_id,
                'student_id': student_id,
                'name': student['name'],
                'employee_id': student['employee_id'],
                'department': student['department'],
                'old_status': student['current_status'],
                'new_status': 'cancelled',
                'success': False,
                'failure_reason': ''
            }

            try:
                reg = RegistrationDAO.get_by_id(reg_id)
                if not reg:
                    result_row['failure_reason'] = '报名记录不存在'
                elif reg['status'] == 'cancelled':
                    result_row['failure_reason'] = '该学员已取消报名'
                elif reg['status'] == 'transferred_out':
                    result_row['failure_reason'] = '该学员已转出'
                else:
                    RegistrationDAO.update_status(reg_id, 'cancelled')
                    result_row['success'] = True
                    result_row['undo_data'] = {
                        'type': 'cancel',
                        'registration_id': reg_id,
                        'old_status': reg['status'],
                        'course_id': course_id
                    }
                    success_count += 1
            except Exception as e:
                result_row['failure_reason'] = f'系统异常: {e}'
                ExceptionLogDAO.create(
                    'batch_cancel_error',
                    f'批量取消失败：学员 {student["name"]}({student["employee_id"]})，'
                    f'原因: {e}',
                    course_id=course_id,
                    student_id=student_id
                )

            if not result_row['success']:
                failure_count += 1
                if result_row['failure_reason'] and '系统异常' not in result_row['failure_reason']:
                    ExceptionLogDAO.create(
                        'batch_cancel_intercepted',
                        f'批量取消被拦截：学员 {student["name"]}({student["employee_id"]})，'
                        f'原因: {result_row["failure_reason"]}',
                        course_id=course_id,
                        student_id=student_id
                    )

            BatchOperationItemDAO.create(
                batch_log_id=log_id,
                registration_id=reg_id,
                student_id=student_id,
                from_course_id=course_id,
                to_course_id=None,
                old_status=result_row['old_status'],
                new_status=result_row['new_status'],
                success=result_row['success'],
                failure_reason=result_row['failure_reason'] if result_row['failure_reason'] else None,
                undo_data=result_row.get('undo_data')
            )
            result_rows.append(result_row)

        BatchOperationLogDAO.update_counts(log_id, success_count, failure_count)

        if success_count > 0:
            UndoManager.set_last_batch_log(log_id)

        return {
            'batch_log_id': log_id,
            'operation_type': 'cancel',
            'operation_cn': '批量取消',
            'course_id': course_id,
            'course_title': summary['course_title'],
            'total': summary['count'],
            'success_count': success_count,
            'failure_count': failure_count,
            'rows': result_rows
        }

    @staticmethod
    def batch_change_status(course_id, registration_ids, target_status, operator='管理员'):
        if target_status not in VALID_STATUSES:
            raise ValidationError(f'无效的目标状态: {target_status}')

        summary = BatchOperationService.get_preview(
            course_id, registration_ids, 'change_status',
            target_status=target_status
        )
        return BatchOperationService._execute_change_status(summary, target_status, operator)

    @staticmethod
    def _execute_change_status(summary, target_status, operator):
        course_id = summary['course_id']
        log_id = BatchOperationLogDAO.create(
            operation_type='change_status',
            from_course_id=course_id,
            target_status=target_status,
            total_count=summary['count'],
            success_count=0,
            failure_count=0,
            operated_by=operator
        )

        success_count = 0
        failure_count = 0
        result_rows = []

        for student in summary['students']:
            reg_id = student['registration_id']
            student_id = student['student_id']
            result_row = {
                'registration_id': reg_id,
                'student_id': student_id,
                'name': student['name'],
                'employee_id': student['employee_id'],
                'department': student['department'],
                'old_status': student['current_status'],
                'new_status': target_status,
                'old_status_cn': student['current_status_cn'],
                'new_status_cn': STATUS_CN_MAP.get(target_status, target_status),
                'success': False,
                'failure_reason': ''
            }

            try:
                reg = RegistrationDAO.get_by_id(reg_id)
                if not reg:
                    result_row['failure_reason'] = '报名记录不存在'
                elif reg['status'] == target_status:
                    result_row['failure_reason'] = (
                        f'该学员已是{STATUS_CN_MAP.get(target_status, target_status)}状态'
                    )
                else:
                    old_status = reg['status']
                    RegistrationDAO.update_status(reg_id, target_status)
                    result_row['success'] = True
                    result_row['undo_data'] = {
                        'type': 'change_status',
                        'registration_id': reg_id,
                        'old_status': old_status,
                        'new_status': target_status,
                        'course_id': course_id
                    }
                    success_count += 1
            except Exception as e:
                result_row['failure_reason'] = f'系统异常: {e}'
                ExceptionLogDAO.create(
                    'batch_status_error',
                    f'批量改状态失败：学员 {student["name"]}({student["employee_id"]})，'
                    f'目标状态: {STATUS_CN_MAP.get(target_status, target_status)}，原因: {e}',
                    course_id=course_id,
                    student_id=student_id
                )

            if not result_row['success']:
                failure_count += 1
                if result_row['failure_reason'] and '系统异常' not in result_row['failure_reason']:
                    ExceptionLogDAO.create(
                        'batch_status_intercepted',
                        f'批量改状态被拦截：学员 {student["name"]}({student["employee_id"]})，'
                        f'原因: {result_row["failure_reason"]}',
                        course_id=course_id,
                        student_id=student_id
                    )

            BatchOperationItemDAO.create(
                batch_log_id=log_id,
                registration_id=reg_id,
                student_id=student_id,
                from_course_id=course_id,
                to_course_id=None,
                old_status=result_row['old_status'],
                new_status=target_status,
                success=result_row['success'],
                failure_reason=result_row['failure_reason'] if result_row['failure_reason'] else None,
                undo_data=result_row.get('undo_data')
            )
            result_rows.append(result_row)

        BatchOperationLogDAO.update_counts(log_id, success_count, failure_count)

        if success_count > 0:
            UndoManager.set_last_batch_log(log_id)

        return {
            'batch_log_id': log_id,
            'operation_type': 'change_status',
            'operation_cn': '批量改状态',
            'course_id': course_id,
            'course_title': summary['course_title'],
            'target_status': target_status,
            'target_status_cn': STATUS_CN_MAP.get(target_status, target_status),
            'total': summary['count'],
            'success_count': success_count,
            'failure_count': failure_count,
            'rows': result_rows
        }

    @staticmethod
    def batch_transfer(course_id, registration_ids, target_course_id, operator='管理员'):
        summary = BatchOperationService.get_preview(
            course_id, registration_ids, 'transfer',
            target_course_id=target_course_id
        )
        return BatchOperationService._execute_transfer(summary, target_course_id, operator)

    @staticmethod
    def _execute_transfer(summary, target_course_id, operator):
        course_id = summary['course_id']
        target_course = CourseDAO.get_by_id(target_course_id)

        log_id = BatchOperationLogDAO.create(
            operation_type='transfer',
            from_course_id=course_id,
            to_course_id=target_course_id,
            total_count=summary['count'],
            success_count=0,
            failure_count=0,
            operated_by=operator
        )

        success_count = 0
        failure_count = 0
        result_rows = []

        for student in summary['students']:
            reg_id = student['registration_id']
            student_id = student['student_id']
            result_row = {
                'registration_id': reg_id,
                'student_id': student_id,
                'name': student['name'],
                'employee_id': student['employee_id'],
                'department': student['department'],
                'from_course_id': course_id,
                'from_course_title': summary['course_title'],
                'to_course_id': target_course_id,
                'to_course_title': target_course['title'],
                'old_status': student['current_status'],
                'new_status': 'transferred_out',
                'success': False,
                'failure_reason': ''
            }

            try:
                reg = RegistrationDAO.get_by_id(reg_id)
                if not reg:
                    result_row['failure_reason'] = '报名记录不存在'
                elif reg['status'] != 'registered':
                    result_row['failure_reason'] = (
                        f'当前状态为{STATUS_CN_MAP.get(reg["status"], reg["status"])}，不能调课'
                    )
                elif RegistrationDAO.exists(target_course_id, student_id):
                    result_row['failure_reason'] = '该学员已报名目标课程'
                else:
                    target_count = RegistrationDAO.count_by_course(target_course_id)
                    if target_count >= target_course['capacity']:
                        result_row['failure_reason'] = '目标课程容量已满'
                    else:
                        new_reg_id = None
                        try:
                            transfer_results = RegistrationDAOExt.batch_transfer([{
                                'registration_id': reg_id,
                                'student_id': student_id,
                                'from_course_id': course_id,
                                'to_course_id': target_course_id
                            }])
                            if transfer_results and transfer_results[0]['success']:
                                new_reg_id = transfer_results[0]['new_registration_id']
                                result_row['success'] = True
                                result_row['new_registration_id'] = new_reg_id
                                result_row['undo_data'] = {
                                    'type': 'transfer',
                                    'old_registration_id': reg_id,
                                    'new_registration_id': new_reg_id,
                                    'student_id': student_id,
                                    'from_course_id': course_id,
                                    'to_course_id': target_course_id
                                }
                                success_count += 1
                            else:
                                result_row['failure_reason'] = '调课操作失败'
                        except Exception as e:
                            result_row['failure_reason'] = f'调课操作异常: {e}'
            except Exception as e:
                result_row['failure_reason'] = f'系统异常: {e}'
                ExceptionLogDAO.create(
                    'batch_transfer_error',
                    f'批量调课失败：学员 {student["name"]}({student["employee_id"]})，'
                    f'从【{summary["course_title"]}】到【{target_course["title"]}】，原因: {e}',
                    course_id=course_id,
                    student_id=student_id
                )

            if not result_row['success']:
                failure_count += 1
                if result_row['failure_reason'] and '系统异常' not in result_row['failure_reason']:
                    ExceptionLogDAO.create(
                        'batch_transfer_intercepted',
                        f'批量调课被拦截：学员 {student["name"]}({student["employee_id"]})，'
                        f'原因: {result_row["failure_reason"]}',
                        course_id=course_id,
                        student_id=student_id
                    )

            BatchOperationItemDAO.create(
                batch_log_id=log_id,
                registration_id=reg_id,
                student_id=student_id,
                from_course_id=course_id,
                to_course_id=target_course_id,
                old_status=result_row['old_status'],
                new_status='transferred_out',
                success=result_row['success'],
                failure_reason=result_row['failure_reason'] if result_row['failure_reason'] else None,
                undo_data=result_row.get('undo_data')
            )
            result_rows.append(result_row)

        BatchOperationLogDAO.update_counts(log_id, success_count, failure_count)

        if success_count > 0:
            UndoManager.set_last_batch_log(log_id)

        return {
            'batch_log_id': log_id,
            'operation_type': 'transfer',
            'operation_cn': '批量调课',
            'course_id': course_id,
            'course_title': summary['course_title'],
            'target_course_id': target_course_id,
            'target_course_title': target_course['title'],
            'total': summary['count'],
            'success_count': success_count,
            'failure_count': failure_count,
            'rows': result_rows
        }

    @staticmethod
    def get_available_target_courses(course_id):
        course = CourseDAO.get_by_id(course_id)
        if not course:
            raise ValidationError('课程不存在')
        return CourseDAO.get_by_theme(course['theme'], course_id)
