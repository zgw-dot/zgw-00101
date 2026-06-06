import sys
import os
import csv
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from datetime import datetime, timedelta
from db import init_database
from services import (
    CourseService, RegistrationService, WaitingListService,
    ExportService, ExceptionService, BatchOperationService, ValidationError
)

def print_test(name, passed, detail=''):
    status = '[PASS]' if passed else '[FAIL]'
    print(f'{status} - {name}')
    if detail:
        print(f'  详情: {detail}')

if __name__ == '__main__':
    print('候补名单模块快速验证测试')
    print('='*50)

    if os.path.exists('test_waiting.db'):
        os.remove('test_waiting.db')

    import db.database as db_module
    original_path = db_module.DB_PATH
    db_module.DB_PATH = os.path.join(os.path.dirname(__file__), 'test_waiting.db')
    init_database()

    try:
        print('\n1. 测试手动添加候补')
        print('-' * 40)

        course_data = {
            'title': '测试课程',
            'theme': '测试主题',
            'instructor': '测试讲师',
            'venue': '测试场地',
            'start_time': (datetime.now() + timedelta(days=7)).isoformat(),
            'end_time': (datetime.now() + timedelta(days=7, hours=3)).isoformat(),
            'capacity': 2,
            'registration_deadline': (datetime.now() + timedelta(days=6)).isoformat(),
            'status': 'published'
        }
        course_id = CourseService.create_course(course_data)

        student1 = {'name': '学生1', 'employee_id': 'TEST001', 'department': '技术部'}
        RegistrationService.register_student(course_id, student1)
        student2 = {'name': '学生2', 'employee_id': 'TEST002', 'department': '产品部'}
        RegistrationService.register_student(course_id, student2)

        waiting_student = {
            'name': '候补学生1',
            'employee_id': 'TESTWAIT001',
            'department': '运营部',
            'phone': '13900000001'
        }
        waiting_id = WaitingListService.add_to_waiting_list(
            course_id, waiting_student, priority=5, source='manual', note='测试'
        )
        print_test('添加候补成功', True, f'候补ID: {waiting_id}')

        waiting_count = WaitingListService.get_waiting_count(course_id)
        print_test('候补人数统计正确', waiting_count == 1, f'{waiting_count} 人')

        waiting_list = WaitingListService.get_waiting_list(course_id)
        print_test('候补队列排序正确', waiting_list[0]['position'] == 1 and waiting_list[0]['priority'] == 5)

        available = WaitingListService.get_available_slots(course_id)
        print_test('课程满员时可用名额为0', available == 0)

        try:
            WaitingListService.add_to_waiting_list(course_id, waiting_student, 0, 'manual')
            print_test('重复候补拦截', False)
        except ValidationError as e:
            print_test('重复候补拦截成功', True, str(e))

        print('\n2. 测试候补导入部分成功部分失败')
        print('-' * 40)

        csv_path = os.path.join(os.path.dirname(__file__), 'test_import.csv')
        with open(csv_path, 'w', newline='', encoding='utf-8-sig') as f:
            writer = csv.writer(f)
            writer.writerow(['姓名', '工号', '部门', '联系方式', '优先级', '备注'])
            writer.writerow(['导入1', 'IMP001', '技术部', '13900000001', '10', 'VIP'])
            writer.writerow(['', 'IMP002', '产品部', '13900000002', '0', '缺少姓名'])
            writer.writerow(['导入2', 'IMP003', '运营部', '13900000003', '5', ''])
            writer.writerow(['导入3', '', '设计部', '13900000004', '0', '缺少工号'])
            writer.writerow(['导入4', 'IMP005', '市场部', '13900000005', '0', ''])

        result = WaitingListService.batch_import_waiting_list(course_id, csv_path)
        print_test('导入执行成功', True)
        print_test('导入统计正确', result['total'] == 5 and result['success_count'] == 3 and result['failure_count'] == 2,
                   f'成功{result["success_count"]}/失败{result["failure_count"]}')

        export_path = ExportService.export_waiting_list_import_result(result)
        print_test('导入结果导出成功', os.path.exists(export_path))
        with open(export_path, 'r', encoding='utf-8-sig') as f:
            content = f.read()
            has_waiting = '候补' in content
            has_imp = 'IMP001' in content
            print(f'   导出内容检查: 包含候补={has_waiting}, 包含IMP001={has_imp}')
            print(f'   完整内容:\n{content[:300]}')
            print_test('导出文件可读', has_waiting and has_imp)

        if os.path.exists(export_path):
            os.remove(export_path)
        if os.path.exists(csv_path):
            os.remove(csv_path)

        print('\n3. 测试自动补位预览与执行')
        print('-' * 40)

        BatchOperationService.batch_cancel(course_id, [1])

        available = WaitingListService.get_available_slots(course_id)
        print_test('释放名额后可用名额正确', available == 1)

        preview = WaitingListService.preview_auto_fill(course_id)
        print_test('补位预览成功', len(preview['items']) == 1 and preview['available_slots'] == 1)

        result = WaitingListService.execute_auto_fill(course_id)
        print_test('自动补位执行成功', True)
        print_test('补位统计正确', result['total'] == 1 and result['success_count'] == 1,
                   f'成功{result["success_count"]}/失败{result["failure_count"]}')
        print_test('生成正式报名', result['items'][0]['registration_id'] is not None)

        export_path = ExportService.export_auto_fill_result(result)
        print_test('补位结果导出成功', os.path.exists(export_path))
        with open(export_path, 'r', encoding='utf-8-sig') as f:
            content = f.read()
            has_fill = '补位' in content
            has_imp = 'IMP001' in content
            print(f'   导出内容检查: 包含补位={has_fill}, 包含IMP001={has_imp}')
            print(f'   完整内容:\n{content[:300]}')
            print_test('导出文件可读', has_fill and has_imp)

        if os.path.exists(export_path):
            os.remove(export_path)

        print('\n4. 测试补位拦截规则')
        print('-' * 40)

        from db.dao import StudentDAO, WaitingListDAO, RegistrationDAO

        student2 = StudentDAO.get_by_employee_id('TEST002')
        WaitingListDAO.create(course_id, student2['id'], priority=100, source='manual', note='测试重复报名拦截')

        WaitingListService.add_to_waiting_list(
            course_id,
            {'name': '正常生', 'employee_id': 'TESTWAIT002', 'department': '技术部', 'phone': '13900000003'},
            0, 'manual'
        )

        regs = RegistrationService.get_course_registrations(course_id)
        imp_reg = [r for r in regs if r['employee_id'] == 'IMP001'][0]
        BatchOperationService.batch_cancel(course_id, [imp_reg['id']])

        result = WaitingListService.execute_auto_fill(course_id)
        print_test('重复报名拦截', result['failure_count'] == 1 and result['success_count'] == 1,
                   f'成功{result["success_count"]}/失败{result["failure_count"]}')
        failure_items = [i for i in result['items'] if i['result'] != 'success']
        print_test('失败原因正确', len(failure_items) == 1 and '已在报名名单中' in failure_items[0]['failure_reason'],
                   failure_items[0]['failure_reason'])

        exceptions = ExceptionService.get_all_logs()
        waiting_exceptions = [e for e in exceptions if 'waiting_list' in e.get('type', '')]
        print_test('异常日志已记录', len(waiting_exceptions) > 0, f'{len(waiting_exceptions)} 条')

        print('\n5. 测试跨重启持久化')
        print('-' * 40)

        waiting_before = WaitingListService.get_waiting_list(course_id)
        order_before = [w['employee_id'] for w in waiting_before]

        import importlib
        importlib.reload(db_module)
        init_database()

        waiting_after = WaitingListService.get_waiting_list(course_id)
        order_after = [w['employee_id'] for w in waiting_after]

        print_test('重启后候补顺序一致', order_before == order_after,
                   f'前: {order_before}, 后: {order_after}')

        history_after = WaitingListService.get_fill_results(course_id)
        print_test('重启后补位历史完整', len(history_after) >= 2)

        print('\n6. 测试报名截止和状态拦截')
        print('-' * 40)

        course_data['registration_deadline'] = (datetime.now() - timedelta(days=1)).isoformat()
        course_data['status'] = 'published'
        CourseService.update_course(course_id, course_data)

        try:
            WaitingListService.add_to_waiting_list(
                course_id,
                {'name': '测试生', 'employee_id': 'DEAD001', 'department': '技术部'},
                0, 'manual'
            )
            print_test('报名截止后添加候补拦截', False)
        except ValidationError as e:
            print_test('报名截止后添加候补拦截成功', True, str(e))

        print('\n' + '='*50)
        print('候补名单模块核心功能验证完成！')
        print('='*50)

    except Exception as e:
        print(f'[ERROR] 测试执行异常: {e}')
        import traceback
        traceback.print_exc()
    finally:
        db_module.DB_PATH = original_path
        if os.path.exists('test_waiting.db'):
            try:
                os.remove('test_waiting.db')
            except:
                pass
