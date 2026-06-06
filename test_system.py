import sys
import os
import glob
import csv
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from datetime import datetime, timedelta
from db import init_database
from services import (
    CourseService, RegistrationService, AttendanceService,
    ExportService, ExceptionService, ValidationError
)

try:
    from PySide6.QtWidgets import QApplication, QPushButton, QTableWidget, QFileDialog, QDialog
    from PySide6.QtCore import Qt
    from ui.widgets import CourseDetailWidget
    from ui.dialogs import BatchImportResultDialog
    PYSIDE_AVAILABLE = True
except ImportError:
    PYSIDE_AVAILABLE = False

def print_test(name, passed, detail=''):
    status = '[PASS]' if passed else '[FAIL]'
    print(f'{status} - {name}')
    if detail:
        print(f'  详情: {detail}')

def test_course_validation():
    print('\n=== 测试课程校验 ===')

    valid_course = {
        'title': '测试课程',
        'theme': '测试主题',
        'instructor': '测试讲师',
        'venue': '测试场地',
        'start_time': (datetime.now() + timedelta(days=7)).isoformat(),
        'end_time': (datetime.now() + timedelta(days=7, hours=3)).isoformat(),
        'capacity': 30,
        'registration_deadline': (datetime.now() + timedelta(days=6)).isoformat(),
        'status': 'draft'
    }

    try:
        CourseService.validate_course_data(valid_course)
        print_test('正常课程数据校验', True)
    except ValidationError as e:
        print_test('正常课程数据校验', False, str(e))

    invalid_course = valid_course.copy()
    invalid_course['end_time'] = invalid_course['start_time']
    try:
        CourseService.validate_course_data(invalid_course)
        print_test('结束时间早于开始时间拦截', False, '应该抛出异常')
    except ValidationError as e:
        print_test('结束时间早于开始时间拦截', True, str(e))

    invalid_course = valid_course.copy()
    invalid_course['registration_deadline'] = invalid_course['start_time']
    try:
        CourseService.validate_course_data(invalid_course)
        print_test('截止时间晚于开始时间拦截', False, '应该抛出异常')
    except ValidationError as e:
        print_test('截止时间晚于开始时间拦截', True, str(e))

    invalid_course = valid_course.copy()
    invalid_course['capacity'] = 0
    try:
        CourseService.validate_course_data(invalid_course)
        print_test('容量为0拦截', False, '应该抛出异常')
    except ValidationError as e:
        print_test('容量为0拦截', True, str(e))

    invalid_course = valid_course.copy()
    invalid_course['title'] = ''
    try:
        CourseService.validate_course_data(invalid_course)
        print_test('空标题拦截', False, '应该抛出异常')
    except ValidationError as e:
        print_test('空标题拦截', True, str(e))

def test_course_crud():
    print('\n=== 测试课程 CRUD ===')

    course_data = {
        'title': '自动化测试课程',
        'theme': '自动化测试',
        'description': '这是一个测试课程',
        'instructor': '测试讲师',
        'venue': '测试场地',
        'start_time': (datetime.now() + timedelta(days=7)).isoformat(),
        'end_time': (datetime.now() + timedelta(days=7, hours=3)).isoformat(),
        'capacity': 2,
        'registration_deadline': (datetime.now() + timedelta(days=6)).isoformat(),
        'status': 'draft'
    }

    try:
        course_id = CourseService.create_course(course_data)
        print_test('创建课程', True, f'课程ID: {course_id}')
    except Exception as e:
        print_test('创建课程', False, str(e))
        return

    try:
        course = CourseService.get_course(course_id)
        assert course is not None
        assert course['title'] == '自动化测试课程'
        print_test('查询课程', True)
    except Exception as e:
        print_test('查询课程', False, str(e))

    try:
        CourseService.publish_course(course_id)
        course = CourseService.get_course(course_id)
        assert course['status'] == 'published'
        print_test('发布课程', True)
    except Exception as e:
        print_test('发布课程', False, str(e))

    return course_id

def test_registration(course_id):
    print('\n=== 测试报名与调课 ===')

    student1 = {'name': '测试学生1', 'employee_id': 'TEST001', 'department': '测试部'}
    student2 = {'name': '测试学生2', 'employee_id': 'TEST002', 'department': '测试部'}
    student3 = {'name': '测试学生3', 'employee_id': 'TEST003', 'department': '测试部'}

    try:
        reg_id1 = RegistrationService.register_student(course_id, student1)
        print_test('学生1报名成功', True, f'报名ID: {reg_id1}')
    except Exception as e:
        print_test('学生1报名成功', False, str(e))

    try:
        reg_id2 = RegistrationService.register_student(course_id, student2)
        print_test('学生2报名成功', True, f'报名ID: {reg_id2}')
    except Exception as e:
        print_test('学生2报名成功', False, str(e))

    try:
        RegistrationService.register_student(course_id, student3)
        print_test('超容量报名拦截', False, '应该抛出异常')
    except ValidationError as e:
        print_test('超容量报名拦截', True, str(e))

    try:
        RegistrationService.register_student(course_id, student1)
        print_test('重复报名拦截', False, '应该抛出异常')
    except ValidationError as e:
        print_test('重复报名拦截', True, str(e))

    course2_data = {
        'title': '自动化测试课程（第二场）',
        'theme': '自动化测试',
        'instructor': '测试讲师',
        'venue': '测试场地B',
        'start_time': (datetime.now() + timedelta(days=14)).isoformat(),
        'end_time': (datetime.now() + timedelta(days=14, hours=3)).isoformat(),
        'capacity': 10,
        'registration_deadline': (datetime.now() + timedelta(days=13)).isoformat(),
        'status': 'published'
    }
    course2_id = CourseService.create_course(course2_data)

    reg = RegistrationService.get_by_id(reg_id1)

    try:
        transfer_id = RegistrationService.request_transfer(reg_id1, course2_id, '时间冲突')
        print_test('调课申请提交', True, f'申请ID: {transfer_id}')
    except Exception as e:
        print_test('调课申请提交', False, str(e))

    try:
        requests = RegistrationService.get_transfer_requests('pending')
        assert len(requests) > 0
        print_test('查询待审核调课', True)
    except Exception as e:
        print_test('查询待审核调课', False, str(e))

    try:
        RegistrationService.review_transfer(transfer_id, True, '同意调课')
        print_test('调课审核通过', True)
    except Exception as e:
        print_test('调课审核通过', False, str(e))

    return course2_id

def test_attendance(course_id):
    print('\n=== 测试签到与补签 ===')

    course = CourseService.get_course(course_id)
    course_data = dict(course)
    course_data['start_time'] = (datetime.now() - timedelta(minutes=30)).isoformat()
    course_data['end_time'] = (datetime.now() + timedelta(hours=2)).isoformat()
    course_data['registration_deadline'] = (datetime.now() - timedelta(hours=1)).isoformat()
    CourseService.update_course(course_id, course_data)

    try:
        success = AttendanceService.check_in(course_id, 'TEST002')
        print_test('正常签到', True)
    except Exception as e:
        print_test('正常签到', False, str(e))

    try:
        AttendanceService.check_in(course_id, 'TEST002')
        print_test('重复签到拦截', False, '应该抛出异常')
    except ValidationError as e:
        print_test('重复签到拦截', True, str(e))

    attendances = AttendanceService.get_course_attendance(course_id)
    print_test('查询出勤列表', len(attendances) > 0, f'共 {len(attendances)} 条记录')

    course_data['capacity'] = 10
    course_data['start_time'] = (datetime.now() + timedelta(hours=2)).isoformat()
    course_data['end_time'] = (datetime.now() + timedelta(hours=5)).isoformat()
    course_data['registration_deadline'] = (datetime.now() + timedelta(hours=1)).isoformat()
    CourseService.update_course(course_id, course_data)

    student_approved = {'name': '补签通过学生', 'employee_id': 'MAKEUP01', 'department': '测试部'}
    RegistrationService.register_student(course_id, student_approved)

    student_rejected = {'name': '补签驳回学生', 'employee_id': 'MAKEUP02', 'department': '测试部'}
    RegistrationService.register_student(course_id, student_rejected)

    course_data['start_time'] = (datetime.now() - timedelta(minutes=30)).isoformat()
    course_data['end_time'] = (datetime.now() + timedelta(hours=2)).isoformat()
    course_data['registration_deadline'] = (datetime.now() - timedelta(hours=1)).isoformat()
    CourseService.update_course(course_id, course_data)

    AttendanceService.mark_all_absent(course_id)

    attendances = AttendanceService.get_course_attendance(course_id)

    att_approved = None
    att_rejected = None
    for att in attendances:
        if att['employee_id'] == 'MAKEUP01':
            att_approved = att
        elif att['employee_id'] == 'MAKEUP02':
            att_rejected = att

    assert att_approved is not None, 'FAIL: 未找到补签通过学员的出勤记录'
    assert att_rejected is not None, 'FAIL: 未找到补签驳回学员的出勤记录'
    assert att_approved['status'] == 'absent', 'FAIL: 补签通过学员缺勤状态未正确设置'
    assert att_rejected['status'] == 'absent', 'FAIL: 补签驳回学员缺勤状态未正确设置'

    print_test('构造缺勤学员-通过', True)
    print_test('构造缺勤学员-驳回', True)

    AttendanceService.request_makeup(course_id, att_approved['student_id'], '测试补签原因-通过')
    AttendanceService.request_makeup(course_id, att_rejected['student_id'], '测试补签原因-驳回')
    print_test('提交补签申请', True, '共 2 条')

    pending = AttendanceService.get_pending_makeups()
    assert len(pending) >= 2, f'FAIL: 待审核补签数量不足，期望>=2，实际{len(pending)}'
    print_test('查询待审核补签', True, f'共 {len(pending)} 条')

    AttendanceService.review_makeup(att_approved['attendance_id'], True, '张管理员', '情况属实，予以通过')
    print_test('补签审核通过', True, '审核人: 张管理员')

    AttendanceService.review_makeup(att_rejected['attendance_id'], False, '李管理员', '无有效缺勤证明，予以驳回')
    print_test('补签审核驳回', True, '审核人: 李管理员')

    logs = ExceptionService.get_all_logs()
    makeup_approved_log = None
    makeup_rejected_log = None
    for log in logs:
        if log['type'] == 'makeup_approved':
            makeup_approved_log = log
        elif log['type'] == 'makeup_rejected':
            makeup_rejected_log = log

    assert makeup_approved_log is not None, 'FAIL: 异常日志中未找到补签审核通过记录'
    assert makeup_rejected_log is not None, 'FAIL: 异常日志中未找到补签审核驳回记录'
    assert '张管理员' in makeup_approved_log['description'], 'FAIL: 审核通过日志中缺少审核人信息'
    assert '李管理员' in makeup_rejected_log['description'], 'FAIL: 审核驳回日志中缺少审核人信息'
    assert '予以通过' in makeup_approved_log['description'], 'FAIL: 审核通过日志中缺少审核意见'
    assert '予以驳回' in makeup_rejected_log['description'], 'FAIL: 审核驳回日志中缺少审核意见'

    print_test('审核日志写入异常表-通过', True, f'日志ID: {makeup_approved_log["id"]}')
    print_test('审核日志写入异常表-驳回', True, f'日志ID: {makeup_rejected_log["id"]}')

    attendances_after = AttendanceService.get_course_attendance(course_id)
    att_approved_after = None
    att_rejected_after = None
    for att in attendances_after:
        if att['employee_id'] == 'MAKEUP01':
            att_approved_after = att
        elif att['employee_id'] == 'MAKEUP02':
            att_rejected_after = att

    assert att_approved_after['status'] == 'present', 'FAIL: 审核通过后出勤状态未更新'
    assert att_approved_after['makeup_status'] == 'approved', 'FAIL: 审核通过后补签状态未更新'
    assert att_rejected_after['status'] == 'absent', 'FAIL: 审核驳回后出勤状态不应更新'
    assert att_rejected_after['makeup_status'] == 'rejected', 'FAIL: 审核驳回后补签状态未更新'

    print_test('出勤表状态同步-通过', True, f'状态: {att_approved_after["status"]}')
    print_test('出勤表状态同步-驳回', True, f'状态: {att_rejected_after["status"]}')

def test_export(course_id):
    print('\n=== 测试 CSV 导出 ===')

    try:
        path = ExportService.export_course_attendance(course_id)
        exists = os.path.exists(path)
        print_test('导出生勤表', exists, f'文件: {path}')

        with open(path, 'r', encoding='utf-8-sig') as f:
            content = f.read()
            has_makeup01 = '补签通过学生' in content or 'MAKEUP01' in content
            has_makeup02 = '补签驳回学生' in content or 'MAKEUP02' in content
            has_approved = '已出勤' in content or 'approved' in content
            has_rejected = '缺勤' in content or 'rejected' in content
            print_test('生勤表含补签学员', has_makeup01 and has_makeup02)
            print_test('生勤表含审核状态', has_approved and has_rejected)
    except Exception as e:
        print_test('导出生勤表', False, str(e))

    try:
        path = ExportService.export_exception_logs()
        exists = os.path.exists(path)
        print_test('导出异常日志', exists, f'文件: {path}')

        with open(path, 'r', encoding='utf-8-sig') as f:
            content = f.read()
            has_approved_log = '补签审核通过' in content or 'makeup_approved' in content
            has_rejected_log = '补签审核驳回' in content or 'makeup_rejected' in content
            has_admin_zhang = '张管理员' in content
            has_admin_li = '李管理员' in content
            has_note_approved = '予以通过' in content
            has_note_rejected = '予以驳回' in content
            assert has_approved_log, 'FAIL: 异常日志CSV中缺少补签审核通过记录'
            assert has_rejected_log, 'FAIL: 异常日志CSV中缺少补签审核驳回记录'
            assert has_admin_zhang, 'FAIL: 异常日志CSV中缺少审核人张管理员'
            assert has_admin_li, 'FAIL: 异常日志CSV中缺少审核人李管理员'
            assert has_note_approved, 'FAIL: 异常日志CSV中缺少审核意见-予以通过'
            assert has_note_rejected, 'FAIL: 异常日志CSV中缺少审核意见-予以驳回'
            print_test('异常日志含补签审核记录', has_approved_log and has_rejected_log)
            print_test('异常日志含审核人信息', has_admin_zhang and has_admin_li)
            print_test('异常日志含审核意见', has_note_approved and has_note_rejected)
    except Exception as e:
        print_test('导出异常日志', False, str(e))

    try:
        path = ExportService.export_all_history()
        exists = os.path.exists(path)
        print_test('导出历史记录', exists, f'文件: {path}')
    except Exception as e:
        print_test('导出历史记录', False, str(e))

def test_exception_logs():
    print('\n=== 测试异常日志 ===')

    try:
        logs = ExceptionService.get_all_logs()
        print_test('查询所有异常日志', True, f'共 {len(logs)} 条')
    except Exception as e:
        print_test('查询所有异常日志', False, str(e))

    unhandled = ExceptionService.get_unhandled_count()
    print_test('未处理异常计数', True, f'共 {unhandled} 条')

def test_deadline_transfer():
    print('\n=== 测试报名截止后调课拦截 ===')

    course_data = {
        'title': '截止测试课程',
        'theme': '截止测试',
        'instructor': '测试讲师',
        'venue': '测试场地',
        'start_time': (datetime.now() + timedelta(hours=2)).isoformat(),
        'end_time': (datetime.now() + timedelta(hours=5)).isoformat(),
        'capacity': 10,
        'registration_deadline': (datetime.now() + timedelta(minutes=30)).isoformat(),
        'status': 'published'
    }

    course_id = CourseService.create_course(course_data)

    student = {'name': '截止测试学生', 'employee_id': 'DEAD001', 'department': '测试部'}
    reg_id = RegistrationService.register_student(course_id, student)

    course = CourseService.get_course(course_id)
    course_data = dict(course)
    course_data['registration_deadline'] = (datetime.now() - timedelta(hours=1)).isoformat()
    CourseService.update_course(course_id, course_data)

    course2_data = {
        'title': '截止测试课程2',
        'theme': '截止测试',
        'instructor': '测试讲师',
        'venue': '测试场地',
        'start_time': (datetime.now() + timedelta(days=2)).isoformat(),
        'end_time': (datetime.now() + timedelta(days=2, hours=3)).isoformat(),
        'capacity': 10,
        'registration_deadline': (datetime.now() + timedelta(days=1)).isoformat(),
        'status': 'published'
    }
    course2_id = CourseService.create_course(course2_data)

    try:
        RegistrationService.request_transfer(reg_id, course2_id, '测试')
        print_test('截止后调课拦截', False, '应该抛出异常')
    except ValidationError as e:
        print_test('截止后调课拦截', True, str(e))

def test_persistence():
    print('\n=== 测试数据持久化（模拟关闭重启） ===')

    import db.database as db_module
    db_path = db_module.DB_PATH
    assert os.path.exists(db_path), 'FAIL: 数据库文件不存在'

    from db.database import get_connection
    conn = get_connection()
    try:
        cursor = conn.cursor()

        cursor.execute('SELECT COUNT(*) as cnt FROM exception_logs WHERE type IN (?, ?)',
                       ('makeup_approved', 'makeup_rejected'))
        row = cursor.fetchone()
        count = row['cnt'] if row else 0
        assert count >= 2, f'FAIL: 重启前异常日志表中应至少有2条补签审核记录，实际有 {count} 条'
        print_test('重启前审核日志持久化', True, f'共 {count} 条补签审核记录')

        cursor.execute('SELECT description FROM exception_logs WHERE type=? ORDER BY id DESC LIMIT 1',
                       ('makeup_approved',))
        row = cursor.fetchone()
        desc = row['description'] if row else ''
        assert '张管理员' in desc, 'FAIL: 持久化的通过日志中缺少审核人'
        assert '予以通过' in desc, 'FAIL: 持久化的通过日志中缺少审核意见'
        print_test('重启前审核信息完整-通过', True, '审核人、审核意见均已写入')

        cursor.execute('SELECT description FROM exception_logs WHERE type=? ORDER BY id DESC LIMIT 1',
                       ('makeup_rejected',))
        row = cursor.fetchone()
        desc = row['description'] if row else ''
        assert '李管理员' in desc, 'FAIL: 持久化的驳回日志中缺少审核人'
        assert '予以驳回' in desc, 'FAIL: 持久化的驳回日志中缺少审核意见'
        print_test('重启前审核信息完整-驳回', True, '审核人、审核意见均已写入')
    finally:
        conn.close()

    print('--- 模拟程序关闭后重启 ---')
    from db.database import init_database
    init_database()

    logs = ExceptionService.get_all_logs()
    makeup_approved_log = None
    makeup_rejected_log = None
    for log in logs:
        if log['type'] == 'makeup_approved':
            makeup_approved_log = log
        elif log['type'] == 'makeup_rejected':
            makeup_rejected_log = log

    assert makeup_approved_log is not None, 'FAIL: 重启后异常日志中未找到补签审核通过记录'
    assert makeup_rejected_log is not None, 'FAIL: 重启后异常日志中未找到补签审核驳回记录'
    assert '张管理员' in makeup_approved_log['description'], 'FAIL: 重启后审核通过日志中缺少审核人信息'
    assert '李管理员' in makeup_rejected_log['description'], 'FAIL: 重启后审核驳回日志中缺少审核人信息'

    print_test('重启后审核日志恢复-通过', True, f'日志ID: {makeup_approved_log["id"]}')
    print_test('重启后审核日志恢复-驳回', True, f'日志ID: {makeup_rejected_log["id"]}')
    print_test('重启后审核人信息完整', True, '张管理员、李管理员信息均恢复')

def create_test_csv(filepath, rows, headers=None):
    import csv
    if headers is None:
        headers = ['姓名', '工号', '部门', '联系方式']
    with open(filepath, 'w', newline='', encoding='utf-8-sig') as f:
        writer = csv.writer(f)
        writer.writerow(headers)
        for row in rows:
            writer.writerow(row)

def test_batch_import_normal():
    print('\n=== 测试批量报名导入（正常场景） ===')

    course_data = {
        'title': '批量导入测试课程',
        'theme': '批量导入',
        'instructor': '测试讲师',
        'venue': '测试场地',
        'start_time': (datetime.now() + timedelta(days=7)).isoformat(),
        'end_time': (datetime.now() + timedelta(days=7, hours=3)).isoformat(),
        'capacity': 10,
        'registration_deadline': (datetime.now() + timedelta(days=6)).isoformat(),
        'status': 'published'
    }
    course_id = CourseService.create_course(course_data)

    csv_path = os.path.join(os.path.dirname(__file__), 'test_import_normal.csv')
    create_test_csv(csv_path, [
        ['批量学生1', 'BATCH001', '技术部', '13800000001'],
        ['批量学生2', 'BATCH002', '产品部', '13800000002'],
        ['批量学生3', 'BATCH003', '运营部', '13800000003'],
    ])

    try:
        result = RegistrationService.batch_import_students(course_id, csv_path)
        assert result['total'] == 3, f'期望3条记录，实际{result["total"]}'
        assert result['success_count'] == 3, f'期望成功3条，实际{result["success_count"]}'
        assert result['failure_count'] == 0, f'期望失败0条，实际{result["failure_count"]}'
        print_test('批量导入全部成功', True, f'成功{result["success_count"]}/失败{result["failure_count"]}')

        regs = RegistrationService.get_course_registrations(course_id)
        assert len(regs) == 3, f'期望3条报名记录，实际{len(regs)}'
        employee_ids = {r['employee_id'] for r in regs}
        assert 'BATCH001' in employee_ids
        assert 'BATCH002' in employee_ids
        assert 'BATCH003' in employee_ids
        print_test('导入后报名记录完整', True)
    finally:
        if os.path.exists(csv_path):
            os.remove(csv_path)

    return course_id

def test_batch_import_partial_failure():
    print('\n=== 测试批量报名导入（部分失败） ===')

    course_data = {
        'title': '批量导入部分失败测试',
        'theme': '批量导入',
        'instructor': '测试讲师',
        'venue': '测试场地',
        'start_time': (datetime.now() + timedelta(days=7)).isoformat(),
        'end_time': (datetime.now() + timedelta(days=7, hours=3)).isoformat(),
        'capacity': 10,
        'registration_deadline': (datetime.now() + timedelta(days=6)).isoformat(),
        'status': 'published'
    }
    course_id = CourseService.create_course(course_data)

    csv_path = os.path.join(os.path.dirname(__file__), 'test_import_partial.csv')
    create_test_csv(csv_path, [
        ['有效学生1', 'PARTIAL001', '技术部', '13800000001'],
        ['', 'PARTIAL002', '产品部', '13800000002'],
        ['有效学生2', '', '运营部', '13800000003'],
        ['有效学生3', 'PARTIAL004', '市场部', '13800000004'],
    ])

    try:
        result = RegistrationService.batch_import_students(course_id, csv_path)
        assert result['total'] == 4, f'期望4条记录，实际{result["total"]}'
        assert result['success_count'] == 2, f'期望成功2条，实际{result["success_count"]}'
        assert result['failure_count'] == 2, f'期望失败2条，实际{result["failure_count"]}'
        print_test('批量导入部分成功', True, f'成功{result["success_count"]}/失败{result["failure_count"]}')

        failure_reasons = [r['failure_reason'] for r in result['rows'] if not r['success']]
        assert all('缺少必填字段' in r for r in failure_reasons)
        print_test('失败原因正确', True, f'原因: {failure_reasons}')

        success_rows = [r for r in result['rows'] if r['success']]
        assert success_rows[0]['row_number'] == 2
        assert success_rows[1]['row_number'] == 5
        print_test('行号记录正确', True)

        regs = RegistrationService.get_course_registrations(course_id)
        assert len(regs) == 2, f'期望2条报名记录，实际{len(regs)}'
        print_test('仅成功记录写入数据库', True)

        logs = ExceptionService.get_all_logs()
        import_errors = [l for l in logs if l['type'] == 'import_validation_error']
        assert len(import_errors) >= 2, f'期望至少2条导入异常日志，实际{len(import_errors)}'
        print_test('失败记录写入异常日志', True, f'共{len(import_errors)}条')
    finally:
        if os.path.exists(csv_path):
            os.remove(csv_path)

def test_batch_import_duplicate():
    print('\n=== 测试批量报名导入（重复导入） ===')

    course_data = {
        'title': '批量导入重复测试',
        'theme': '批量导入',
        'instructor': '测试讲师',
        'venue': '测试场地',
        'start_time': (datetime.now() + timedelta(days=7)).isoformat(),
        'end_time': (datetime.now() + timedelta(days=7, hours=3)).isoformat(),
        'capacity': 10,
        'registration_deadline': (datetime.now() + timedelta(days=6)).isoformat(),
        'status': 'published'
    }
    course_id = CourseService.create_course(course_data)

    csv_path = os.path.join(os.path.dirname(__file__), 'test_import_duplicate.csv')
    create_test_csv(csv_path, [
        ['重复学生1', 'DUP001', '技术部', '13800000001'],
        ['重复学生2', 'DUP002', '产品部', '13800000002'],
    ])

    try:
        result1 = RegistrationService.batch_import_students(course_id, csv_path)
        assert result1['success_count'] == 2
        print_test('首次导入成功', True)

        result2 = RegistrationService.batch_import_students(course_id, csv_path)
        assert result2['total'] == 2
        assert result2['success_count'] == 0, f'期望成功0条，实际{result2["success_count"]}'
        assert result2['failure_count'] == 2, f'期望失败2条，实际{result2["failure_count"]}'
        print_test('重复导入全部拦截', True, f'成功{result2["success_count"]}/失败{result2["failure_count"]}')

        failure_reasons = [r['failure_reason'] for r in result2['rows']]
        assert all('该学员已报名此课程' in r for r in failure_reasons)
        print_test('重复导入失败原因正确', True)

        regs = RegistrationService.get_course_registrations(course_id)
        assert len(regs) == 2, f'重复导入后报名数不应增加，期望2条，实际{len(regs)}'
        print_test('重复导入不产生新报名', True)
    finally:
        if os.path.exists(csv_path):
            os.remove(csv_path)

def test_batch_import_capacity():
    print('\n=== 测试批量报名导入（容量边界） ===')

    course_data = {
        'title': '批量导入容量测试',
        'theme': '批量导入',
        'instructor': '测试讲师',
        'venue': '测试场地',
        'start_time': (datetime.now() + timedelta(days=7)).isoformat(),
        'end_time': (datetime.now() + timedelta(days=7, hours=3)).isoformat(),
        'capacity': 3,
        'registration_deadline': (datetime.now() + timedelta(days=6)).isoformat(),
        'status': 'published'
    }
    course_id = CourseService.create_course(course_data)

    csv_path = os.path.join(os.path.dirname(__file__), 'test_import_capacity.csv')
    create_test_csv(csv_path, [
        ['容量学生1', 'CAP001', '技术部', '13800000001'],
        ['容量学生2', 'CAP002', '产品部', '13800000002'],
        ['容量学生3', 'CAP003', '运营部', '13800000003'],
        ['容量学生4', 'CAP004', '市场部', '13800000004'],
        ['容量学生5', 'CAP005', '财务部', '13800000005'],
    ])

    try:
        result = RegistrationService.batch_import_students(course_id, csv_path)
        assert result['total'] == 5, f'期望5条记录，实际{result["total"]}'
        assert result['success_count'] == 3, f'期望成功3条（容量），实际{result["success_count"]}'
        assert result['failure_count'] == 2, f'期望失败2条（超容），实际{result["failure_count"]}'
        print_test('容量边界正确拦截', True, f'成功{result["success_count"]}/失败{result["failure_count"]}')

        success_ids = [r['employee_id'] for r in result['rows'] if r['success']]
        failure_ids = [r['employee_id'] for r in result['rows'] if not r['success']]
        assert success_ids == ['CAP001', 'CAP002', 'CAP003']
        assert failure_ids == ['CAP004', 'CAP005']
        print_test('按顺序处理，前3条成功后2条超容', True)

        failure_reasons = [r['failure_reason'] for r in result['rows'] if not r['success']]
        assert all('容量已满' in r for r in failure_reasons)
        print_test('超容失败原因正确', True)

        regs = RegistrationService.get_course_registrations(course_id)
        assert len(regs) == 3, f'期望3条报名，实际{len(regs)}'
        course = CourseService.get_course(course_id)
        assert course['capacity'] == 3
        print_test('容量被占满但未超限', True)

        logs = ExceptionService.get_all_logs()
        over_cap_logs = [l for l in logs if l['type'] == 'over_capacity']
        assert len(over_cap_logs) >= 2, f'期望至少2条超容日志，实际{len(over_cap_logs)}'
        print_test('超容异常日志已记录', True, f'共{len(over_cap_logs)}条')
    finally:
        if os.path.exists(csv_path):
            os.remove(csv_path)

def test_batch_import_unpublished():
    print('\n=== 测试批量报名导入（未发布课程） ===')

    course_data = {
        'title': '未发布课程导入测试',
        'theme': '批量导入',
        'instructor': '测试讲师',
        'venue': '测试场地',
        'start_time': (datetime.now() + timedelta(days=7)).isoformat(),
        'end_time': (datetime.now() + timedelta(days=7, hours=3)).isoformat(),
        'capacity': 10,
        'registration_deadline': (datetime.now() + timedelta(days=6)).isoformat(),
        'status': 'draft'
    }
    course_id = CourseService.create_course(course_data)

    csv_path = os.path.join(os.path.dirname(__file__), 'test_import_unpublished.csv')
    create_test_csv(csv_path, [
        ['测试学生', 'UNPUB001', '技术部', '13800000001'],
    ])

    try:
        result = RegistrationService.batch_import_students(course_id, csv_path)
        assert result['total'] == 1
        assert result['success_count'] == 0
        assert result['failure_count'] == 1
        assert '课程未发布' in result['rows'][0]['failure_reason']
        print_test('未发布课程导入被拦截', True, result['rows'][0]['failure_reason'])

        regs = RegistrationService.get_course_registrations(course_id)
        assert len(regs) == 0, '未发布课程不应有报名记录'
        print_test('未发布课程无报名写入', True)
    finally:
        if os.path.exists(csv_path):
            os.remove(csv_path)

def test_batch_import_persistence(course_id_for_persistence):
    print('\n=== 测试批量导入数据持久化（重启后查询） ===')

    regs_before = RegistrationService.get_course_registrations(course_id_for_persistence)
    count_before = len(regs_before)
    assert count_before > 0, '重启前应有报名记录'
    print_test('重启前报名记录存在', True, f'共{count_before}条')

    logs_before = ExceptionService.get_all_logs()
    import_logs_before = [l for l in logs_before if l['type'] in ('import_validation_error', 'import_system_error', 'over_capacity')]
    import_log_count_before = len(import_logs_before)

    course_before = CourseService.get_course(course_id_for_persistence)
    capacity_before = course_before['capacity']
    registered_count_before = len(regs_before)

    print('--- 模拟程序关闭后重启 ---')
    from db.database import init_database
    init_database()

    regs_after = RegistrationService.get_course_registrations(course_id_for_persistence)
    count_after = len(regs_after)
    assert count_after == count_before, f'重启后报名记录数不一致，期望{count_before}，实际{count_after}'
    print_test('重启后报名记录完整', True, f'共{count_after}条')

    employee_ids_before = {r['employee_id'] for r in regs_before}
    employee_ids_after = {r['employee_id'] for r in regs_after}
    assert employee_ids_before == employee_ids_after, '重启后学员信息不一致'
    print_test('重启后学员信息一致', True, f'工号: {employee_ids_after}')

    logs_after = ExceptionService.get_all_logs()
    import_logs_after = [l for l in logs_after if l['type'] in ('import_validation_error', 'import_system_error', 'over_capacity')]
    import_log_count_after = len(import_logs_after)
    assert import_log_count_after == import_log_count_before, '重启后异常日志数不一致'
    print_test('重启后异常日志完整', True, f'共{import_log_count_after}条')

    course_after = CourseService.get_course(course_id_for_persistence)
    capacity_after = course_after['capacity']
    registered_count_after = RegistrationDAO.count_by_course(course_id_for_persistence)
    assert capacity_after == capacity_before, '重启后课程容量不一致'
    assert registered_count_after == registered_count_before, '重启后容量占用不一致'
    print_test('重启后课程容量占用一致', True, f'{registered_count_after}/{capacity_after}')

def test_batch_import_result_export(import_course_id):
    print('\n=== 测试批量导入结果导出 ===')

    csv_path = os.path.join(os.path.dirname(__file__), 'test_import_export.csv')
    create_test_csv(csv_path, [
        ['导出学生1', 'EXPORT001', '技术部', '13800000001'],
        ['', 'EXPORT002', '产品部', '13800000002'],
        ['导出学生3', 'EXPORT003', '', '13800000003'],
    ])

    try:
        result = RegistrationService.batch_import_students(import_course_id, csv_path)
        export_path = ExportService.export_import_result(result)

        assert os.path.exists(export_path), '导出文件不存在'
        print_test('导入结果CSV生成', True, f'文件: {export_path}')

        with open(export_path, 'r', encoding='utf-8-sig') as f:
            content = f.read()

        assert '批量导入结果' in content
        assert '导出学生1' in content
        assert 'EXPORT001' in content
        assert 'EXPORT002' in content
        assert 'EXPORT003' in content
        assert '成功' in content
        assert '失败' in content
        assert '缺少必填字段' in content
        print_test('导出CSV包含正确内容', True)

        assert '原始行号' in content
        assert '处理结果' in content
        assert '失败原因' in content
        print_test('导出CSV包含正确表头', True)

        success_count = content.count(',成功,') + content.count('"成功"')
        failure_count = content.count(',失败,') + content.count('"失败"')
        assert success_count >= 2, f'成功记录数不足，期望至少2条'
        assert failure_count >= 1, f'失败记录数不足，期望至少1条'
        print_test('导出CSV包含成功/失败标记', True, f'成功{success_count}条，失败{failure_count}条')

        return export_path
    finally:
        if os.path.exists(csv_path):
            os.remove(csv_path)

def test_batch_import_english_headers():
    print('\n=== 测试批量报名导入（英文列表头） ===')

    course_data = {
        'title': '英文表头导入测试',
        'theme': '批量导入',
        'instructor': '测试讲师',
        'venue': '测试场地',
        'start_time': (datetime.now() + timedelta(days=7)).isoformat(),
        'end_time': (datetime.now() + timedelta(days=7, hours=3)).isoformat(),
        'capacity': 10,
        'registration_deadline': (datetime.now() + timedelta(days=6)).isoformat(),
        'status': 'published'
    }
    course_id = CourseService.create_course(course_data)

    csv_path = os.path.join(os.path.dirname(__file__), 'test_import_english.csv')
    create_test_csv(csv_path, [
        ['English Student', 'ENG001', 'Tech Dept', '13800000001'],
    ], headers=['name', 'employee_id', 'department', 'phone'])

    try:
        result = RegistrationService.batch_import_students(course_id, csv_path)
        assert result['success_count'] == 1
        assert result['rows'][0]['name'] == 'English Student'
        assert result['rows'][0]['employee_id'] == 'ENG001'
        print_test('英文表头导入成功', True)
    finally:
        if os.path.exists(csv_path):
            os.remove(csv_path)

def test_gui_batch_import_button():
    print('\n=== 测试 GUI 批量导入入口 ===')

    if not PYSIDE_AVAILABLE:
        print_test('GUI 组件导入', False, 'PySide6 不可用，跳过 GUI 测试')
        return

    app = QApplication.instance() or QApplication(sys.argv)

    course_data = {
        'title': 'GUI 测试课程',
        'theme': 'GUI 测试',
        'instructor': '测试讲师',
        'venue': '测试场地',
        'start_time': (datetime.now() + timedelta(days=7)).isoformat(),
        'end_time': (datetime.now() + timedelta(days=7, hours=3)).isoformat(),
        'capacity': 10,
        'registration_deadline': (datetime.now() + timedelta(days=6)).isoformat(),
        'status': 'published'
    }
    course_id = CourseService.create_course(course_data)

    try:
        widget = CourseDetailWidget(course_id)
        widget.show()
        app.processEvents()

        batch_btn = None
        for child in widget.findChildren(QPushButton):
            if child.text() == '批量导入报名':
                batch_btn = child
                break

        assert batch_btn is not None, 'FAIL: 未找到「批量导入报名」按钮'
        assert batch_btn.isVisible(), 'FAIL: 按钮不可见'
        assert batch_btn.isEnabled(), 'FAIL: 按钮不可用'
        print_test('课程详情页有批量导入按钮', True)

        assert batch_btn.styleSheet() != '', 'FAIL: 按钮无样式'
        print_test('按钮有醒目的橙色样式', True)

        widget.close()
    finally:
        if app:
            app.processEvents()

def test_gui_import_result_dialog():
    print('\n=== 测试 GUI 导入结果对话框 ===')

    if not PYSIDE_AVAILABLE:
        print_test('GUI 组件导入', False, 'PySide6 不可用，跳过 GUI 测试')
        return

    app = QApplication.instance() or QApplication(sys.argv)

    mock_result = {
        'course_id': 1,
        'course_title': 'GUI 结果测试课程',
        'total': 5,
        'success_count': 3,
        'failure_count': 2,
        'rows': [
            {'row_number': 2, 'name': '成功学生1', 'employee_id': 'GUI001', 'department': '技术部', 'phone': '13800000001', 'success': True, 'registration_id': 1001, 'failure_reason': ''},
            {'row_number': 3, 'name': '', 'employee_id': 'GUI002', 'department': '产品部', 'phone': '13800000002', 'success': False, 'failure_reason': '缺少必填字段：姓名或工号不能为空'},
            {'row_number': 4, 'name': '成功学生2', 'employee_id': 'GUI003', 'department': '运营部', 'phone': '13800000003', 'success': True, 'registration_id': 1002, 'failure_reason': ''},
            {'row_number': 5, 'name': '重复学生', 'employee_id': 'GUI001', 'department': '技术部', 'phone': '13800000001', 'success': False, 'failure_reason': '该学员已报名此课程'},
            {'row_number': 6, 'name': '成功学生3', 'employee_id': 'GUI004', 'department': '市场部', 'phone': '13800000004', 'success': True, 'registration_id': 1003, 'failure_reason': ''},
        ]
    }

    try:
        dialog = BatchImportResultDialog(mock_result)
        dialog.show()
        app.processEvents()

        table = dialog.findChild(QTableWidget)
        assert table is not None, 'FAIL: 未找到结果表格'
        assert table.rowCount() == 5, f'FAIL: 表格行数应为5，实际{table.rowCount()}'
        assert table.columnCount() == 7, f'FAIL: 表格列数应为7，实际{table.columnCount()}'
        print_test('导入结果对话框含明细表格', True, f'{table.rowCount()}行x{table.columnCount()}列')

        headers = [table.horizontalHeaderItem(i).text() for i in range(table.columnCount())]
        expected_headers = ['行号', '姓名', '工号', '部门', '联系方式', '处理结果', '失败原因']
        assert headers == expected_headers, f'FAIL: 表头不正确，期望{expected_headers}，实际{headers}'
        print_test('表格表头正确', True)

        success_count = 0
        failure_count = 0
        for row in range(table.rowCount()):
            result_item = table.item(row, 5)
            if result_item:
                if '成功' in result_item.text():
                    success_count += 1
                    success_color = result_item.foreground().color()
                    assert success_color.green() > success_color.red() and success_color.green() > success_color.blue(), 'FAIL: 成功行颜色不是绿色系'
                elif '失败' in result_item.text():
                    failure_count += 1
                    fail_color = result_item.foreground().color()
                    assert fail_color.red() > fail_color.green() and fail_color.red() > fail_color.blue(), 'FAIL: 失败行颜色不是红色系'

        assert success_count == 3, f'FAIL: 成功标记数应为3，实际{success_count}'
        assert failure_count == 2, f'FAIL: 失败标记数应为2，实际{failure_count}'
        print_test('成功/失败行颜色区分正确', True, f'成功{success_count}，失败{failure_count}')

        failure_row = table.item(1, 6)
        assert failure_row is not None
        assert '缺少必填字段' in failure_row.text()
        print_test('失败原因显示正确', True, failure_row.text())

        duplicate_row = table.item(3, 6)
        assert duplicate_row is not None
        assert '该学员已报名此课程' in duplicate_row.text()
        print_test('重复报名失败原因显示正确', True)

        dialog.close()
    finally:
        if app:
            app.processEvents()

def test_gui_import_result_export():
    print('\n=== 测试 GUI 导入结果导出 ===')

    if not PYSIDE_AVAILABLE:
        print_test('GUI 组件导入', False, 'PySide6 不可用，跳过 GUI 测试')
        return

    app = QApplication.instance() or QApplication(sys.argv)

    mock_result = {
        'course_id': 1,
        'course_title': 'GUI 导出测试课程',
        'total': 3,
        'success_count': 2,
        'failure_count': 1,
        'rows': [
            {'row_number': 2, 'name': '导出学生1', 'employee_id': 'EXPGUI001', 'department': '技术部', 'phone': '13800000001', 'success': True, 'registration_id': 2001, 'failure_reason': ''},
            {'row_number': 3, 'name': '', 'employee_id': 'EXPGUI002', 'department': '产品部', 'phone': '13800000002', 'success': False, 'failure_reason': '缺少必填字段：姓名或工号不能为空'},
            {'row_number': 4, 'name': '导出学生2', 'employee_id': 'EXPGUI003', 'department': '运营部', 'phone': '13800000003', 'success': True, 'registration_id': 2002, 'failure_reason': ''},
        ]
    }

    try:
        dialog = BatchImportResultDialog(mock_result)
        dialog.show()
        app.processEvents()

        export_path = None
        original_export = ExportService.export_import_result
        def mock_export(result, output_path=None):
            nonlocal export_path
            export_path = original_export(result, output_path)
            return export_path

        ExportService.export_import_result = mock_export

        try:
            dialog.export_result()

            assert export_path is not None, 'FAIL: 未调用导出方法'
            assert os.path.exists(export_path), f'FAIL: 导出文件不存在: {export_path}'
            print_test('导出功能可从对话框触发', True, f'文件: {export_path}')

            with open(export_path, 'r', encoding='utf-8-sig') as f:
                content = f.read()

            assert '批量导入结果' in content
            assert 'EXPGUI001' in content
            assert 'EXPGUI002' in content
            assert 'EXPGUI003' in content
            assert '缺少必填字段' in content
            assert '成功' in content
            assert '失败' in content
            print_test('导出CSV内容完整', True)

            assert '原始行号' in content
            assert '处理结果' in content
            assert '失败原因' in content
            print_test('导出CSV含正确表头', True)
        finally:
            ExportService.export_import_result = original_export
            if export_path and os.path.exists(export_path):
                try:
                    os.remove(export_path)
                except:
                    pass

        dialog.close()
    finally:
        if app:
            app.processEvents()

def test_gui_import_trigger_end_to_end():
    print('\n=== 测试 GUI 端到端导入触发 ===')

    if not PYSIDE_AVAILABLE:
        print_test('GUI 组件导入', False, 'PySide6 不可用，跳过 GUI 测试')
        return

    app = QApplication.instance() or QApplication(sys.argv)

    course_data = {
        'title': 'GUI 端到端测试课程',
        'theme': 'GUI 测试',
        'instructor': '测试讲师',
        'venue': '测试场地',
        'start_time': (datetime.now() + timedelta(days=7)).isoformat(),
        'end_time': (datetime.now() + timedelta(days=7, hours=3)).isoformat(),
        'capacity': 5,
        'registration_deadline': (datetime.now() + timedelta(days=6)).isoformat(),
        'status': 'published'
    }
    course_id = CourseService.create_course(course_data)

    csv_path = os.path.join(os.path.dirname(__file__), 'test_gui_import.csv')
    create_test_csv(csv_path, [
        ['GUI学生1', 'GUIE2E001', '技术部', '13800000001'],
        ['', 'GUIE2E002', '产品部', '13800000002'],
        ['GUI学生2', 'GUIE2E003', '运营部', '13800000003'],
    ])

    original_get_open = QFileDialog.getOpenFileName
    def mock_get_open(parent, title, default_dir, filter_str):
        return (csv_path, filter_str)
    QFileDialog.getOpenFileName = staticmethod(mock_get_open)

    import_result_ref = [None]
    original_batch_import = RegistrationService.batch_import_students
    def mock_batch_import(course_id, csv_path):
        result = original_batch_import(course_id, csv_path)
        import_result_ref[0] = result
        return result

    RegistrationService.batch_import_students = staticmethod(mock_batch_import)

    original_dialog_exec = BatchImportResultDialog.exec
    def mock_dialog_exec(self):
        return QDialog.Accepted
    BatchImportResultDialog.exec = mock_dialog_exec

    try:
        widget = CourseDetailWidget(course_id)
        widget.show()
        app.processEvents()

        batch_btn = None
        for child in widget.findChildren(QPushButton):
            if child.text() == '批量导入报名':
                batch_btn = child
                break

        assert batch_btn is not None, 'FAIL: 未找到批量导入按钮'
        assert batch_btn.isVisible(), 'FAIL: 按钮不可见'
        assert batch_btn.isEnabled(), 'FAIL: 按钮不可用'
        print_test('课程详情页有可用的批量导入按钮', True)

        batch_btn.click()
        app.processEvents()

        assert import_result_ref[0] is not None, 'FAIL: 导入服务未被调用'
        print_test('点击按钮触发导入流程', True)

        result = import_result_ref[0]
        assert result['total'] == 3
        assert result['success_count'] == 2
        assert result['failure_count'] == 1
        print_test('导入结果正确返回', True, f'成功{result["success_count"]}/失败{result["failure_count"]}')

        failure_rows = [r for r in result['rows'] if not r['success']]
        assert len(failure_rows) == 1
        assert '缺少必填字段' in failure_rows[0]['failure_reason']
        print_test('失败行明细可见（含原因）', True, failure_rows[0]['failure_reason'])

        success_rows = [r for r in result['rows'] if r['success']]
        assert len(success_rows) == 2
        assert success_rows[0]['row_number'] == 2
        assert success_rows[1]['row_number'] == 4
        print_test('成功行记录正确行号', True, f'行号: {[r["row_number"] for r in success_rows]}')

        regs = RegistrationService.get_course_registrations(course_id)
        assert len(regs) == 2, f'期望2条报名记录，实际{len(regs)}'
        emp_ids = {r['employee_id'] for r in regs}
        assert 'GUIE2E001' in emp_ids
        assert 'GUIE2E003' in emp_ids
        print_test('成功的报名已写入数据库', True)

        course = CourseService.get_course(course_id)
        current_count = len(regs)
        assert current_count <= course['capacity'], 'FAIL: 容量占用超过限制'
        print_test('课程容量占用正确', True, f'{current_count}/{course["capacity"]}')

        widget.close()
    finally:
        QFileDialog.getOpenFileName = staticmethod(original_get_open)
        RegistrationService.batch_import_students = staticmethod(original_batch_import)
        BatchImportResultDialog.exec = original_dialog_exec
        if os.path.exists(csv_path):
            os.remove(csv_path)
        if app:
            app.processEvents()

def test_gui_import_persistence_after_restart():
    print('\n=== 测试 GUI 导入数据持久化（重启验证） ===')

    if not PYSIDE_AVAILABLE:
        print_test('GUI 组件导入', False, 'PySide6 不可用，跳过 GUI 测试')
        return

    app = QApplication.instance() or QApplication(sys.argv)

    course_data = {
        'title': 'GUI 持久化测试课程',
        'theme': 'GUI 测试',
        'instructor': '测试讲师',
        'venue': '测试场地',
        'start_time': (datetime.now() + timedelta(days=7)).isoformat(),
        'end_time': (datetime.now() + timedelta(days=7, hours=3)).isoformat(),
        'capacity': 10,
        'registration_deadline': (datetime.now() + timedelta(days=6)).isoformat(),
        'status': 'published'
    }
    course_id = CourseService.create_course(course_data)

    csv_path = os.path.join(os.path.dirname(__file__), 'test_gui_persistence.csv')
    create_test_csv(csv_path, [
        ['持久学生1', 'GUIPER001', '技术部', '13800000001'],
        ['持久学生2', 'GUIPER002', '产品部', '13800000002'],
    ])

    try:
        result = RegistrationService.batch_import_students(course_id, csv_path)
        assert result['success_count'] == 2

        regs_before = RegistrationService.get_course_registrations(course_id)
        count_before = len(regs_before)
        ids_before = {r['employee_id'] for r in regs_before}
        course_before = CourseService.get_course(course_id)

        print('--- 模拟程序关闭后重启 ---')
        from db.database import init_database
        init_database()

        widget = CourseDetailWidget(course_id)
        widget.show()
        app.processEvents()
        reg_table = widget.reg_table
        visible_rows = reg_table.rowCount()

        assert visible_rows == count_before, f'重启后GUI显示报名数不一致，期望{count_before}，实际{visible_rows}'
        print_test('重启后 GUI 显示报名记录一致', True, f'共{visible_rows}条')

        regs_after = RegistrationService.get_course_registrations(course_id)
        ids_after = {r['employee_id'] for r in regs_after}
        assert ids_before == ids_after, '重启后学员信息不一致'
        print_test('重启后学员信息完整', True, f'工号: {ids_after}')

        course_after = CourseService.get_course(course_id)
        assert course_after['capacity'] == course_before['capacity']
        count_after = RegistrationDAO.count_by_course(course_id)
        assert count_after == count_before, '重启后容量占用不一致'
        print_test('重启后课程容量占用一致', True, f'{count_after}/{course_after["capacity"]}')

        logs_after = ExceptionService.get_all_logs()
        import_logs = [l for l in logs_after if l['type'] in ('import_validation_error', 'import_system_error')]
        print_test('重启后异常日志完整', True, f'共{len(import_logs)}条导入相关日志')

        widget.close()
    finally:
        if os.path.exists(csv_path):
            os.remove(csv_path)
        if app:
            app.processEvents()

def test_summary():
    print('\n' + '='*50)
    print('所有测试用例执行完成')
    print('请检查上面的测试结果，确保所有 PASS')
    print('='*50)

if __name__ == '__main__':
    print('培训排课系统自动化测试')
    print('='*50)

    if os.path.exists('test_training.db'):
        os.remove('test_training.db')

    import db.database as db_module
    original_path = db_module.DB_PATH
    db_module.DB_PATH = os.path.join(os.path.dirname(__file__), 'test_training.db')
    init_database()

    from db.dao import RegistrationDAO

    try:
        test_course_validation()
        course_id = test_course_crud()
        if course_id:
            course2_id = test_registration(course_id)
            test_attendance(course_id)
            test_export(course_id)
            test_persistence()
        test_exception_logs()
        test_deadline_transfer()

        print('\n' + '='*50)
        print('批量导入专项测试')
        print('='*50)

        batch_course_id = test_batch_import_normal()
        test_batch_import_partial_failure()
        test_batch_import_duplicate()
        test_batch_import_capacity()
        test_batch_import_unpublished()
        test_batch_import_english_headers()

        export_course_data = {
            'title': '导入结果导出测试课程',
            'theme': '批量导入',
            'instructor': '测试讲师',
            'venue': '测试场地',
            'start_time': (datetime.now() + timedelta(days=7)).isoformat(),
            'end_time': (datetime.now() + timedelta(days=7, hours=3)).isoformat(),
            'capacity': 10,
            'registration_deadline': (datetime.now() + timedelta(days=6)).isoformat(),
            'status': 'published'
        }
        export_course_id = CourseService.create_course(export_course_data)
        test_batch_import_result_export(export_course_id)

        test_batch_import_persistence(batch_course_id)

        print('\n' + '='*50)
        print('GUI 集成专项测试')
        print('='*50)

        test_gui_batch_import_button()
        test_gui_import_result_dialog()
        test_gui_import_result_export()
        test_gui_import_trigger_end_to_end()
        test_gui_import_persistence_after_restart()

        test_summary()
    finally:
        db_module.DB_PATH = original_path

        export_files = glob.glob(os.path.join(os.path.dirname(__file__), 'exports', '批量导入结果_*.csv'))
        for f in export_files:
            try:
                os.remove(f)
            except:
                pass

        if os.path.exists('test_training.db'):
            try:
                os.remove('test_training.db')
            except:
                pass
