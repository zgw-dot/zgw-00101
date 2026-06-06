import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from datetime import datetime, timedelta
from db import init_database as init_db
from services import (
    CourseService, RegistrationService, BatchOperationService,
    UndoManager, ExportService, ExceptionService
)
from db.dao import BatchOperationLogDAO, BatchOperationItemDAO, RegistrationDAO, RegistrationDAOExt

def print_test(name, passed, detail=''):
    status = '[PASS]' if passed else '[FAIL]'
    print(f'{status} - {name}')
    if detail:
        print(f'  详情: {detail}')

def main():
    print('批量操作核心功能测试')
    print('='*50)

    if os.path.exists('test_batch.db'):
        os.remove('test_batch.db')

    import db.database as db_module
    original_path = db_module.DB_PATH
    db_module.DB_PATH = os.path.join(os.path.dirname(__file__), 'test_batch.db')
    init_db()

    UndoManager()  # 初始化会话，必须在所有批量操作之前

    try:
        print('\n=== 测试批量取消 ===')
        course_data = {
            'title': '批量取消测试',
            'theme': '测试主题',
            'instructor': '测试讲师',
            'venue': '测试场地',
            'start_time': (datetime.now() + timedelta(days=7)).isoformat(),
            'end_time': (datetime.now() + timedelta(days=7, hours=3)).isoformat(),
            'capacity': 5,
            'registration_deadline': (datetime.now() + timedelta(days=6)).isoformat(),
            'status': 'published'
        }
        course_id = CourseService.create_course(course_data)

        students = [
            {'name': '学生1', 'employee_id': 'TEST001', 'department': '技术部'},
            {'name': '学生2', 'employee_id': 'TEST002', 'department': '产品部'},
            {'name': '学生3', 'employee_id': 'TEST003', 'department': '运营部'},
        ]

        reg_ids = []
        for s in students:
            reg_id = RegistrationService.register_student(course_id, s)
            reg_ids.append(reg_id)

        RegistrationDAO.update_status(reg_ids[1], 'cancelled')

        test_ids = reg_ids

        preview = BatchOperationService.get_preview(course_id, test_ids, 'cancel')
        print_test('批量取消预览', preview['count'] == 3, f'警告: {preview["warnings"]}')

        result = BatchOperationService.batch_cancel(course_id, test_ids)
        print_test('批量取消部分成功', result['success_count'] == 2 and result['failure_count'] == 1,
            f'成功{result["success_count"]}/失败{result["failure_count"]}')

        regs = RegistrationDAOExt.get_by_course_all_status(course_id)
        active = [r for r in regs if r['status'] == 'registered']
        cancelled = [r for r in regs if r['status'] == 'cancelled']
        status_detail = {r['name']: r['status'] for r in regs}
        print_test('成功记录状态更新', len(active) == 0 and len(cancelled) == 3,
            f'状态详情: {status_detail}')

        print('\n=== 测试撤销功能 ===')
        has_undo = UndoManager.has_undo_available()
        print_test('撤销可用', has_undo)

        undo_info = UndoManager.get_last_undo_info()
        print_test('撤销信息正确', undo_info and undo_info['operation_type'] == 'cancel',
            f'操作类型: {undo_info.get("operation_type") if undo_info else None}')

        undo_result = UndoManager.undo_last_operation()
        print_test('撤销执行成功', undo_result and undo_result['success_count'] == 2,
            f'恢复{undo_result["success_count"] if undo_result else 0}条')

        regs_after = RegistrationDAOExt.get_by_course_all_status(course_id)
        active_after = [r for r in regs_after if r['status'] == 'registered']
        cancelled_after = [r for r in regs_after if r['status'] == 'cancelled']
        print_test('撤销后状态恢复', len(active_after) == 2 and len(cancelled_after) == 1,
            f'已报名{len(active_after)}/已取消{len(cancelled_after)}')

        print('\n=== 测试批量改状态 ===')
        result = BatchOperationService.batch_change_status(course_id, reg_ids, 'attended')
        print_test('批量改状态成功', result['success_count'] == 2 and result['failure_count'] == 1,
            f'成功{result["success_count"]}/失败{result["failure_count"]}')

        regs = RegistrationDAOExt.get_by_course_all_status(course_id)
        status_map = {r['employee_id']: r['status'] for r in regs}
        print_test('状态更新正确', status_map['TEST001'] == 'attended' and status_map['TEST002'] == 'cancelled',
            f'状态映射: {status_map}')

        print('\n=== 测试批量调课 ===')
        course2_data = {
            'title': '批量调课目标课程',
            'theme': '测试主题',
            'instructor': '测试讲师',
            'venue': '测试场地B',
            'start_time': (datetime.now() + timedelta(days=14)).isoformat(),
            'end_time': (datetime.now() + timedelta(days=14, hours=3)).isoformat(),
            'capacity': 2,
            'registration_deadline': (datetime.now() + timedelta(days=13)).isoformat(),
            'status': 'published'
        }
        course2_id = CourseService.create_course(course2_data)

        RegistrationService.register_student(course2_id, {
            'name': '学生3', 'employee_id': 'TEST003', 'department': '运营部'
        })

        UndoManager.undo_last_operation()

        result = BatchOperationService.batch_transfer(course_id, reg_ids, course2_id)
        print_test('批量调课拦截正确', result['success_count'] == 1 and result['failure_count'] == 2,
            f'成功{result["success_count"]}/失败{result["failure_count"]}')

        failure_reasons = [row['failure_reason'] for row in result['rows'] if not row['success']]
        print_test('调课失败原因正确', any('已报名目标课程' in r for r in failure_reasons) and any('不能调课' in r for r in failure_reasons),
            f'原因: {failure_reasons}')

        course2_regs = RegistrationDAOExt.get_by_course_all_status(course2_id)
        course2_count = len([r for r in course2_regs if r['status'] == 'registered'])
        print_test('目标课程容量正确', course2_count == 2, f'目标课程人数: {course2_count}')

        print('\n=== 测试导出功能 ===')
        export_path = ExportService.export_batch_operation_result(result)
        print_test('导出成功', os.path.exists(export_path), f'文件: {export_path}')

        with open(export_path, 'r', encoding='utf-8-sig') as f:
            content = f.read()
            has_success = '成功' in content
            has_failure = '失败' in content
            has_course = '批量调课目标课程' in content
            print_test('导出内容正确', has_success and has_failure and has_course)

        print('\n=== 测试持久化 ===')
        logs_before = BatchOperationLogDAO.get_latest(limit=10)
        log_count_before = len(logs_before)

        from db.database import init_database as init_db2
        init_db2()

        logs_after = BatchOperationLogDAO.get_latest(limit=10)
        log_count_after = len(logs_after)
        print_test('重启后日志完整', log_count_before == log_count_after)

        items_after = BatchOperationItemDAO.get_successful_by_batch_log(result['batch_log_id'])
        print_test('重启后明细完整', len(items_after) >= 1)

        print('\n=== 测试会话边界 ===')
        old_start = UndoManager._session_start
        UndoManager._session_start = datetime.now() - timedelta(hours=2)
        UndoManager._last_batch_log_id = None

        has_undo = UndoManager.has_undo_available()
        print_test('重启后撤销不可用', not has_undo)

        UndoManager._session_start = old_start

        print('\n' + '='*50)
        print('所有核心测试完成！')
        print('='*50)

    finally:
        db_module.DB_PATH = original_path
        if os.path.exists('test_batch.db'):
            try:
                os.remove('test_batch.db')
            except:
                pass

if __name__ == '__main__':
    main()
