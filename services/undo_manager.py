from datetime import datetime
from db.dao import (
    BatchOperationLogDAO, BatchOperationItemDAO,
    RegistrationDAO, ExceptionLogDAO
)
from db.database import get_connection
from .course_service import ValidationError

class UndoManager:
    _instance = None
    _last_batch_log_id = None
    _session_start = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._session_start = datetime.now().isoformat()
        return cls._instance

    @classmethod
    def reset_session(cls):
        cls._last_batch_log_id = None
        cls._session_start = datetime.now().isoformat()

    @classmethod
    def set_last_batch_log(cls, batch_log_id):
        cls._last_batch_log_id = batch_log_id

    @classmethod
    def has_undo_available(cls):
        if cls._last_batch_log_id is None:
            return False
        log = BatchOperationLogDAO.get_by_id(cls._last_batch_log_id)
        if not log:
            cls._last_batch_log_id = None
            return False
        if log['undone']:
            cls._last_batch_log_id = None
            return False
        if log['created_at'] < cls._session_start:
            cls._last_batch_log_id = None
            return False
        if log['success_count'] <= 0:
            cls._last_batch_log_id = None
            return False
        return True

    @classmethod
    def get_last_undo_info(cls):
        if not cls.has_undo_available():
            return None
        log = BatchOperationLogDAO.get_by_id(cls._last_batch_log_id)
        if not log:
            return None

        operation_cn = {
            'cancel': '批量取消',
            'change_status': '批量改状态',
            'transfer': '批量调课'
        }.get(log['operation_type'], log['operation_type'])

        items = BatchOperationItemDAO.get_successful_by_batch_log(cls._last_batch_log_id)

        return {
            'batch_log_id': log['id'],
            'operation_type': log['operation_type'],
            'operation_cn': operation_cn,
            'success_count': log['success_count'],
            'total_count': log['total_count'],
            'created_at': log['created_at'],
            'items': items
        }

    @classmethod
    def undo_last_operation(cls, operator='管理员'):
        if not cls.has_undo_available():
            raise ValidationError('没有可撤销的批量操作')

        log_id = cls._last_batch_log_id
        undo_info = cls.get_last_undo_info()

        items = BatchOperationItemDAO.get_successful_by_batch_log(log_id)

        success_count = 0
        failure_count = 0
        results = []
        pending_logs = []
        pending_error_logs = []

        conn = get_connection()
        cursor = conn.cursor()

        try:
            for item in items:
                undo_data = item.get('undo_data')
                if not undo_data:
                    failure_count += 1
                    results.append({
                        'item_id': item['id'],
                        'student_name': item.get('student_name', ''),
                        'employee_id': item.get('employee_id', ''),
                        'success': False,
                        'reason': '缺少撤销数据'
                    })
                    continue

                undo_type = undo_data.get('type')
                try:
                    if undo_type == 'cancel':
                        cls._undo_cancel(cursor, undo_data, item)
                    elif undo_type == 'change_status':
                        cls._undo_change_status(cursor, undo_data, item)
                    elif undo_type == 'transfer':
                        cls._undo_transfer(cursor, undo_data, item)
                    else:
                        failure_count += 1
                        results.append({
                            'item_id': item['id'],
                            'student_name': item.get('student_name', ''),
                            'employee_id': item.get('employee_id', ''),
                            'success': False,
                            'reason': f'未知的撤销类型: {undo_type}'
                        })
                        continue

                    success_count += 1
                    results.append({
                        'item_id': item['id'],
                        'student_name': item.get('student_name', ''),
                        'employee_id': item.get('employee_id', ''),
                        'success': True
                    })

                    pending_logs.append({
                        'type': 'batch_operation_undone',
                        'description': f'撤销批量操作：{undo_info["operation_cn"]}，'
                                       f'学员 {item.get("student_name", "")}({item.get("employee_id", "")})，'
                                       f'操作人：{operator}',
                        'course_id': undo_data.get('from_course_id') or undo_data.get('course_id'),
                        'student_id': item['student_id']
                    })

                except Exception as e:
                    failure_count += 1
                    results.append({
                        'item_id': item['id'],
                        'student_name': item.get('student_name', ''),
                        'employee_id': item.get('employee_id', ''),
                        'success': False,
                        'reason': f'撤销失败: {e}'
                    })
                    pending_error_logs.append({
                        'type': 'batch_undo_error',
                        'description': f'撤销批量操作失败：学员 {item.get("student_name", "")}'
                                       f'({item.get("employee_id", "")})，原因: {e}',
                        'course_id': undo_data.get('from_course_id') or undo_data.get('course_id'),
                        'student_id': item['student_id']
                    })

            cursor.execute('UPDATE batch_operation_logs SET undone=1, undone_at=? WHERE id=?',
                           (datetime.now().isoformat(), log_id))
            conn.commit()
            conn.close()
            cls._last_batch_log_id = None

            for log in pending_logs:
                ExceptionLogDAO.create(
                    log['type'], log['description'], log['course_id'], log['student_id']
                )
            for log in pending_error_logs:
                ExceptionLogDAO.create(
                    log['type'], log['description'], log['course_id'], log['student_id']
                )

        except Exception as e:
            try:
                conn.rollback()
                conn.close()
            except:
                pass
            raise ValidationError(f'撤销操作失败: {e}')

        return {
            'batch_log_id': log_id,
            'operation_type': undo_info['operation_type'],
            'operation_cn': undo_info['operation_cn'],
            'total_attempted': len(items),
            'success_count': success_count,
            'failure_count': failure_count,
            'results': results
        }

    @staticmethod
    def _undo_cancel(cursor, undo_data, item):
        reg_id = undo_data['registration_id']
        old_status = undo_data['old_status']
        cursor.execute(
            'UPDATE registrations SET status=? WHERE id=?',
            (old_status, reg_id)
        )
        if cursor.rowcount <= 0:
            raise Exception(f'报名记录 {reg_id} 不存在或未更新')

    @staticmethod
    def _undo_change_status(cursor, undo_data, item):
        reg_id = undo_data['registration_id']
        old_status = undo_data['old_status']
        cursor.execute(
            'UPDATE registrations SET status=? WHERE id=?',
            (old_status, reg_id)
        )
        if cursor.rowcount <= 0:
            raise Exception(f'报名记录 {reg_id} 不存在或未更新')

    @staticmethod
    def _undo_transfer(cursor, undo_data, item):
        old_reg_id = undo_data['old_registration_id']
        new_reg_id = undo_data['new_registration_id']
        from_course_id = undo_data['from_course_id']
        to_course_id = undo_data['to_course_id']
        student_id = undo_data['student_id']

        cursor.execute(
            'DELETE FROM registrations WHERE id=?',
            (new_reg_id,)
        )
        if cursor.rowcount <= 0:
            raise Exception(f'新报名记录 {new_reg_id} 不存在或无法删除')

        cursor.execute(
            'UPDATE registrations SET status=? WHERE id=? AND course_id=? AND student_id=?',
            ('registered', old_reg_id, from_course_id, student_id)
        )
        if cursor.rowcount <= 0:
            raise Exception(f'原报名记录 {old_reg_id} 不存在或无法恢复')
