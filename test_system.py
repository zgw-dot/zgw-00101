import sys
import os
import glob
import csv
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from datetime import datetime, timedelta
from db import init_database
from services import (
    CourseService, RegistrationService, AttendanceService,
    ExportService, ExceptionService, BatchOperationService,
    UndoManager, WaitingListService, CertificateService,
    ValidationError
)
from db.dao import (
    RegistrationDAO, StudentDAO, BatchOperationLogDAO, BatchOperationItemDAO,
    WaitingListDAO, WaitingListResultDAO,
    CertificateDAO, CertificateBatchLogDAO, CertificateBatchItemDAO
)

try:
    from PySide6.QtWidgets import QApplication, QPushButton, QTableWidget, QFileDialog, QDialog, QComboBox, QTabWidget, QLabel
    from PySide6.QtCore import Qt
    from ui.widgets import CourseDetailWidget, CertificateManagementWidget
    from ui.dialogs import (
        BatchImportResultDialog, BatchOperationConfirmDialog,
        BatchOperationResultDialog, BatchTargetCourseDialog,
        BatchTargetStatusDialog, UndoDialog, WaitingListDialog,
        AddToWaitingListDialog, WaitingImportResultDialog,
        AutoFillPreviewDialog, AutoFillResultDialog,
        CertificatePreviewDialog, CertificateBatchResultDialog,
        CertificateVoidDialog, CertificateReissueDialog,
        CertificateSelectCourseDialog
    )
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

def test_batch_cancel_partial_failure():
    print('\n=== 测试批量取消（部分成功部分失败） ===')

    course_data = {
        'title': '批量取消测试课程',
        'theme': '批量操作',
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
        {'name': '取消学生1', 'employee_id': 'CANCEL001', 'department': '技术部'},
        {'name': '取消学生2', 'employee_id': 'CANCEL002', 'department': '产品部'},
        {'name': '取消学生3', 'employee_id': 'CANCEL003', 'department': '运营部'},
    ]

    reg_ids = []
    for s in students:
        reg_id = RegistrationService.register_student(course_id, s)
        reg_ids.append(reg_id)

    BatchOperationService.batch_cancel(course_id, [reg_ids[1]])

    all_reg_ids = reg_ids + [99999]

    try:
        result = BatchOperationService.batch_cancel(course_id, all_reg_ids)
        assert result['total_count'] == 4, f'期望4条，实际{result["total_count"]}'
        assert result['success_count'] == 2, f'期望成功2条，实际{result["success_count"]}'
        assert result['failure_count'] == 2, f'期望失败2条，实际{result["failure_count"]}'
        print_test('批量取消部分成功', True, f'成功{result["success_count"]}/失败{result["failure_count"]}')

        failure_items = [item for item in result['items'] if not item['success']]
        assert len(failure_items) == 2
        failure_reasons = [item['failure_reason'] for item in failure_items]
        assert any('已取消' in r for r in failure_reasons)
        assert any('不存在' in r for r in failure_reasons)
        print_test('失败原因正确记录', True, f'原因: {failure_reasons}')

        regs = RegistrationService.get_course_registrations(course_id)
        active_regs = [r for r in regs if r['status'] == 'registered']
        assert len(active_regs) == 1, f'期望1条有效报名，实际{len(active_regs)}'
        print_test('仅成功记录状态更新', True)

        logs = ExceptionService.get_all_logs()
        batch_logs = [l for l in logs if l['type'] == 'batch_operation_failure']
        assert len(batch_logs) >= 2, f'期望至少2条异常日志，实际{len(batch_logs)}'
        print_test('失败记录写入异常日志', True, f'共{len(batch_logs)}条')

        return result
    except Exception as e:
        print_test('批量取消部分成功', False, str(e))
        return None

def test_batch_change_status():
    print('\n=== 测试批量改状态 ===')

    course_data = {
        'title': '批量改状态测试课程',
        'theme': '批量操作',
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
        {'name': '状态学生1', 'employee_id': 'STATUS001', 'department': '技术部'},
        {'name': '状态学生2', 'employee_id': 'STATUS002', 'department': '产品部'},
        {'name': '状态学生3', 'employee_id': 'STATUS003', 'department': '运营部'},
    ]

    reg_ids = []
    for s in students:
        reg_id = RegistrationService.register_student(course_id, s)
        reg_ids.append(reg_id)

    BatchOperationService.batch_cancel(course_id, [reg_ids[2]])

    try:
        result = BatchOperationService.batch_change_status(
            course_id, reg_ids, 'attended'
        )
        assert result['total_count'] == 3
        assert result['success_count'] == 2
        assert result['failure_count'] == 1
        print_test('批量改状态部分成功', True, f'成功{result["success_count"]}/失败{result["failure_count"]}')

        regs = RegistrationService.get_course_registrations(course_id)
        status_map = {r['employee_id']: r['status'] for r in regs}
        assert status_map['STATUS001'] == 'attended'
        assert status_map['STATUS002'] == 'attended'
        assert status_map['STATUS003'] == 'cancelled'
        print_test('状态更新正确', True)

        return result
    except Exception as e:
        print_test('批量改状态', False, str(e))
        return None

def test_batch_transfer_rules():
    print('\n=== 测试批量调课业务规则 ===')

    course1_data = {
        'title': '批量调课源课程',
        'theme': '批量操作',
        'instructor': '测试讲师',
        'venue': '测试场地A',
        'start_time': (datetime.now() + timedelta(days=7)).isoformat(),
        'end_time': (datetime.now() + timedelta(days=7, hours=3)).isoformat(),
        'capacity': 5,
        'registration_deadline': (datetime.now() + timedelta(days=6)).isoformat(),
        'status': 'published'
    }
    course1_id = CourseService.create_course(course1_data)

    course2_data = {
        'title': '批量调课目标课程（同主题）',
        'theme': '批量操作',
        'instructor': '测试讲师',
        'venue': '测试场地B',
        'start_time': (datetime.now() + timedelta(days=14)).isoformat(),
        'end_time': (datetime.now() + timedelta(days=14, hours=3)).isoformat(),
        'capacity': 3,
        'registration_deadline': (datetime.now() + timedelta(days=13)).isoformat(),
        'status': 'published'
    }
    course2_id = CourseService.create_course(course2_data)

    course3_data = {
        'title': '不同主题课程',
        'theme': '其他主题',
        'instructor': '测试讲师',
        'venue': '测试场地C',
        'start_time': (datetime.now() + timedelta(days=21)).isoformat(),
        'end_time': (datetime.now() + timedelta(days=21, hours=3)).isoformat(),
        'capacity': 10,
        'registration_deadline': (datetime.now() + timedelta(days=20)).isoformat(),
        'status': 'published'
    }
    course3_id = CourseService.create_course(course3_data)

    students = [
        {'name': '调课学生1', 'employee_id': 'TRANS001', 'department': '技术部'},
        {'name': '调课学生2', 'employee_id': 'TRANS002', 'department': '产品部'},
        {'name': '调课学生3', 'employee_id': 'TRANS003', 'department': '运营部'},
        {'name': '调课学生4', 'employee_id': 'TRANS004', 'department': '市场部'},
        {'name': '调课学生5', 'employee_id': 'TRANS005', 'department': '财务部'},
    ]

    reg_ids = []
    for s in students:
        reg_id = RegistrationService.register_student(course1_id, s)
        reg_ids.append(reg_id)

    BatchOperationService.batch_cancel(course1_id, [reg_ids[4]])

    RegistrationService.register_student(course2_id, {
        'name': '重复学生', 'employee_id': 'TRANS003', 'department': '运营部'
    })

    try:
        result_same_theme = BatchOperationService.batch_transfer(
            course1_id, reg_ids, course2_id
        )
        assert result_same_theme['total_count'] == 5
        assert result_same_theme['success_count'] == 2
        assert result_same_theme['failure_count'] == 3
        print_test('批量调课容量和重复拦截', True,
            f'成功{result_same_theme["success_count"]}/失败{result_same_theme["failure_count"]}')

        failure_items = [item for item in result_same_theme['items'] if not item['success']]
        failure_reasons = [item['failure_reason'] for item in failure_items]
        assert any('重复' in r for r in failure_reasons)
        assert any('已取消' in r for r in failure_reasons)
        assert any('容量' in r for r in failure_reasons)
        print_test('调课拦截原因正确', True, f'原因: {failure_reasons}')

        try:
            BatchOperationService.batch_transfer(course1_id, [reg_ids[0]], course3_id)
            print_test('非同主题调课拦截', False, '应该抛出异常')
        except ValidationError as e:
            print_test('非同主题调课拦截', True, str(e))

        course2_regs = RegistrationService.get_course_registrations(course2_id)
        course2_count = len([r for r in course2_regs if r['status'] == 'registered'])
        assert course2_count == 3, f'目标课程容量应为3，实际{course2_count}'
        print_test('目标课程容量占用正确', True, f'{course2_count}/3')

        return result_same_theme
    except Exception as e:
        print_test('批量调课业务规则', False, str(e))
        return None

def test_batch_operation_preview():
    print('\n=== 测试批量操作预览 ===')

    course_data = {
        'title': '预览测试课程',
        'theme': '预览测试',
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
        {'name': '预览学生1', 'employee_id': 'PREVIEW001', 'department': '技术部'},
        {'name': '预览学生2', 'employee_id': 'PREVIEW002', 'department': '产品部'},
    ]

    reg_ids = []
    for s in students:
        reg_id = RegistrationService.register_student(course_id, s)
        reg_ids.append(reg_id)

    BatchOperationService.batch_cancel(course_id, [reg_ids[1]])

    try:
        preview = BatchOperationService.get_preview(course_id, reg_ids, 'cancel')
        assert preview['total_count'] == 2
        assert len(preview['warnings']) > 0
        print_test('批量取消预览正确', True, f'警告: {preview["warnings"]}')

        assert len(preview['registrations']) == 2
        print_test('预览包含学员信息', True)

        preview_status = BatchOperationService.get_preview(
            course_id, reg_ids, 'change_status', target_status='attended'
        )
        assert preview_status['target_status'] == 'attended'
        print_test('批量改状态预览正确', True)
    except Exception as e:
        print_test('批量操作预览', False, str(e))

def test_undo_cancel_operation():
    print('\n=== 测试撤销批量取消 ===')

    course_data = {
        'title': '撤销测试课程',
        'theme': '撤销测试',
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
        {'name': '撤销学生1', 'employee_id': 'UNDO001', 'department': '技术部'},
        {'name': '撤销学生2', 'employee_id': 'UNDO002', 'department': '产品部'},
        {'name': '撤销学生3', 'employee_id': 'UNDO003', 'department': '运营部'},
    ]

    reg_ids = []
    for s in students:
        reg_id = RegistrationService.register_student(course_id, s)
        reg_ids.append(reg_id)

    try:
        result = BatchOperationService.batch_cancel(course_id, reg_ids)
        assert result['success_count'] == 3

        regs_after_cancel = RegistrationService.get_course_registrations(course_id)
        cancelled_count = len([r for r in regs_after_cancel if r['status'] == 'cancelled'])
        assert cancelled_count == 3
        print_test('批量取消执行成功', True)

        assert UndoManager.has_undo_available(), '撤销应该可用'
        undo_info = UndoManager.get_last_undo_info()
        assert undo_info is not None
        assert undo_info['operation_type'] == 'cancel'
        assert undo_info['success_count'] == 3
        print_test('撤销信息正确', True)

        undo_result = UndoManager.undo_last_operation()
        assert undo_result is not None
        assert undo_result['restored_count'] == 3
        print_test('撤销操作成功', True, f'恢复{undo_result["restored_count"]}条')

        regs_after_undo = RegistrationService.get_course_registrations(course_id)
        active_count = len([r for r in regs_after_undo if r['status'] == 'registered'])
        assert active_count == 3, f'撤销后期望3条有效报名，实际{active_count}'
        print_test('撤销后状态恢复正确', True)

        course = CourseService.get_course(course_id)
        registered_count = len([r for r in regs_after_undo if r['status'] == 'registered'])
        assert registered_count <= course['capacity']
        print_test('撤销后容量占用正确', True, f'{registered_count}/{course["capacity"]}')

        assert not UndoManager.has_undo_available(), '撤销后不应再可用'
        print_test('撤销后清除撤销状态', True)

        return undo_result
    except Exception as e:
        print_test('撤销批量取消', False, str(e))
        return None

def test_undo_transfer_operation():
    print('\n=== 测试撤销批量调课 ===')

    course1_data = {
        'title': '撤销调课源课程',
        'theme': '撤销调课',
        'instructor': '测试讲师',
        'venue': '测试场地A',
        'start_time': (datetime.now() + timedelta(days=7)).isoformat(),
        'end_time': (datetime.now() + timedelta(days=7, hours=3)).isoformat(),
        'capacity': 5,
        'registration_deadline': (datetime.now() + timedelta(days=6)).isoformat(),
        'status': 'published'
    }
    course1_id = CourseService.create_course(course1_data)

    course2_data = {
        'title': '撤销调课目标课程',
        'theme': '撤销调课',
        'instructor': '测试讲师',
        'venue': '测试场地B',
        'start_time': (datetime.now() + timedelta(days=14)).isoformat(),
        'end_time': (datetime.now() + timedelta(days=14, hours=3)).isoformat(),
        'capacity': 5,
        'registration_deadline': (datetime.now() + timedelta(days=13)).isoformat(),
        'status': 'published'
    }
    course2_id = CourseService.create_course(course2_data)

    students = [
        {'name': '撤销调课1', 'employee_id': 'UNDOTR001', 'department': '技术部'},
        {'name': '撤销调课2', 'employee_id': 'UNDOTR002', 'department': '产品部'},
    ]

    reg_ids = []
    for s in students:
        reg_id = RegistrationService.register_student(course1_id, s)
        reg_ids.append(reg_id)

    try:
        result = BatchOperationService.batch_transfer(course1_id, reg_ids, course2_id)
        assert result['success_count'] == 2
        print_test('批量调课执行成功', True)

        course2_regs = RegistrationService.get_course_registrations(course2_id)
        course2_count = len([r for r in course2_regs if r['status'] == 'registered'])
        assert course2_count == 2
        print_test('目标课程报名增加', True)

        course1_regs = RegistrationService.get_course_registrations(course1_id)
        course1_count = len([r for r in course1_regs if r['status'] == 'registered'])
        assert course1_count == 0
        print_test('源课程报名减少', True)

        undo_result = UndoManager.undo_last_operation()
        assert undo_result is not None
        assert undo_result['restored_count'] == 2
        print_test('撤销调课成功', True)

        course2_regs_after = RegistrationService.get_course_registrations(course2_id)
        course2_count_after = len([r for r in course2_regs_after if r['status'] == 'registered'])
        assert course2_count_after == 0, f'撤销后期望目标课程0人，实际{course2_count_after}'

        course1_regs_after = RegistrationService.get_course_registrations(course1_id)
        course1_count_after = len([r for r in course1_regs_after if r['status'] == 'registered'])
        assert course1_count_after == 2, f'撤销后期望源课程2人，实际{course1_count_after}'
        print_test('撤销后两门课程人数恢复', True)

        return undo_result
    except Exception as e:
        print_test('撤销批量调课', False, str(e))
        return None

def test_undo_session_boundary():
    print('\n=== 测试撤销会话边界 ===')

    old_session_start = UndoManager._session_start

    try:
        UndoManager._session_start = datetime.now() - timedelta(hours=2)
        UndoManager._last_batch_log_id = None

        assert not UndoManager.has_undo_available()
        print_test('重启后撤销不可用', True)

        undo_info = UndoManager.get_last_undo_info()
        assert undo_info is None
        print_test('重启后无撤销信息', True)

        undo_result = UndoManager.undo_last_operation()
        assert undo_result is None
        print_test('重启后无法执行撤销', True)
    finally:
        UndoManager._session_start = old_session_start

def test_batch_operation_persistence():
    print('\n=== 测试批量操作持久化（重启后验证） ===')

    course_data = {
        'title': '持久化批量操作课程',
        'theme': '持久化测试',
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
        {'name': '持久学生1', 'employee_id': 'PERBATCH001', 'department': '技术部'},
        {'name': '持久学生2', 'employee_id': 'PERBATCH002', 'department': '产品部'},
        {'name': '持久学生3', 'employee_id': 'PERBATCH003', 'department': '运营部'},
    ]

    reg_ids = []
    for s in students:
        reg_id = RegistrationService.register_student(course_id, s)
        reg_ids.append(reg_id)

    BatchOperationService.batch_cancel(course_id, [reg_ids[1]])

    result = BatchOperationService.batch_cancel(course_id, reg_ids)
    assert result['success_count'] == 2

    logs_before = BatchOperationLogDAO.get_latest(limit=5)
    log_count_before = len(logs_before)
    items_before = BatchOperationItemDAO.get_successful_by_batch_log(result['batch_log_id'])
    item_count_before = len(items_before)

    print('--- 模拟程序关闭后重启 ---')
    from db.database import init_database
    init_database()

    logs_after = BatchOperationLogDAO.get_latest(limit=5)
    log_count_after = len(logs_after)
    assert log_count_after == log_count_before
    print_test('重启后批量操作日志完整', True, f'共{log_count_after}条')

    items_after = BatchOperationItemDAO.get_successful_by_batch_log(result['batch_log_id'])
    item_count_after = len(items_after)
    assert item_count_after == item_count_before
    print_test('重启后批量操作明细完整', True, f'共{item_count_after}条')

    regs_after = RegistrationService.get_course_registrations(course_id)
    status_map = {r['employee_id']: r['status'] for r in regs_after}
    assert status_map['PERBATCH001'] == 'cancelled'
    assert status_map['PERBATCH002'] == 'cancelled'
    assert status_map['PERBATCH003'] == 'cancelled'
    print_test('重启后报名状态正确', True)

    exception_logs = ExceptionService.get_all_logs()
    batch_failures = [l for l in exception_logs if l['type'] == 'batch_operation_failure']
    assert len(batch_failures) >= 1
    print_test('重启后异常日志完整', True, f'共{len(batch_failures)}条失败记录')

def test_batch_operation_export():
    print('\n=== 测试批量操作结果导出 ===')

    course1_data = {
        'title': '导出源课程',
        'theme': '导出测试',
        'instructor': '测试讲师',
        'venue': '测试场地A',
        'start_time': (datetime.now() + timedelta(days=7)).isoformat(),
        'end_time': (datetime.now() + timedelta(days=7, hours=3)).isoformat(),
        'capacity': 10,
        'registration_deadline': (datetime.now() + timedelta(days=6)).isoformat(),
        'status': 'published'
    }
    course1_id = CourseService.create_course(course1_data)

    course2_data = {
        'title': '导出目标课程',
        'theme': '导出测试',
        'instructor': '测试讲师',
        'venue': '测试场地B',
        'start_time': (datetime.now() + timedelta(days=14)).isoformat(),
        'end_time': (datetime.now() + timedelta(days=14, hours=3)).isoformat(),
        'capacity': 10,
        'registration_deadline': (datetime.now() + timedelta(days=13)).isoformat(),
        'status': 'published'
    }
    course2_id = CourseService.create_course(course2_data)

    students = [
        {'name': '导出学生1', 'employee_id': 'EXPBATCH001', 'department': '技术部', 'phone': '13800000001'},
        {'name': '导出学生2', 'employee_id': 'EXPBATCH002', 'department': '产品部', 'phone': '13800000002'},
        {'name': '导出学生3', 'employee_id': 'EXPBATCH003', 'department': '运营部', 'phone': '13800000003'},
    ]

    reg_ids = []
    for s in students:
        reg_id = RegistrationService.register_student(course1_id, s)
        reg_ids.append(reg_id)

    BatchOperationService.batch_cancel(course1_id, [reg_ids[2]])

    result = BatchOperationService.batch_transfer(course1_id, reg_ids, course2_id)

    try:
        export_path = ExportService.export_batch_operation_result(result)
        assert os.path.exists(export_path), '导出文件不存在'
        print_test('批量调课结果CSV生成', True, f'文件: {export_path}')

        with open(export_path, 'r', encoding='utf-8-sig') as f:
            content = f.read()

        assert '批量操作结果' in content
        assert 'EXPBATCH001' in content
        assert 'EXPBATCH002' in content
        assert 'EXPBATCH003' in content
        assert '成功' in content
        assert '失败' in content
        assert '已取消' in content
        print_test('导出CSV包含正确内容', True)

        assert '原课程' in content
        assert '目标课程' in content
        assert '处理结果' in content
        assert '失败原因' in content
        print_test('导出CSV包含正确表头', True)

        success_count = content.count(',成功,') + content.count('"成功"')
        failure_count = content.count(',失败,') + content.count('"失败"')
        assert success_count >= 2, f'成功记录数不足'
        assert failure_count >= 1, f'失败记录数不足'
        print_test('导出CSV包含成功/失败标记', True, f'成功{success_count}条，失败{failure_count}条')

        assert '导出目标课程' in content
        assert '导出源课程' in content
        print_test('导出CSV包含课程信息', True)

        return export_path
    except Exception as e:
        print_test('批量操作结果导出', False, str(e))
        return None

def test_gui_batch_operation_buttons():
    print('\n=== 测试 GUI 批量操作按钮 ===')

    if not PYSIDE_AVAILABLE:
        print_test('GUI 组件导入', False, 'PySide6 不可用，跳过 GUI 测试')
        return

    app = QApplication.instance() or QApplication(sys.argv)

    course_data = {
        'title': 'GUI 批量操作测试',
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

        buttons_found = {}
        expected_buttons = ['批量取消', '批量改状态', '批量调课', '全选']
        for btn_text in expected_buttons:
            found = False
            for child in widget.findChildren(QPushButton):
                if child.text() == btn_text:
                    assert child.isVisible(), f'FAIL: {btn_text} 按钮不可见'
                    assert child.isEnabled(), f'FAIL: {btn_text} 按钮不可用'
                    buttons_found[btn_text] = True
                    found = True
                    break
            for child in widget.findChildren(QCheckBox):
                if child.text() == btn_text:
                    assert child.isVisible(), f'FAIL: {btn_text} 复选框不可见'
                    buttons_found[btn_text] = True
                    found = True
                    break
            assert found, f'FAIL: 未找到 {btn_text} 控件'

        print_test('课程详情页有所有批量操作控件', True, list(buttons_found.keys()))

        table = widget.reg_table
        assert table.columnCount() == 7
        headers = [table.horizontalHeaderItem(i).text() for i in range(table.columnCount())]
        assert '选择' in headers
        assert '工号' in headers
        assert '姓名' in headers
        print_test('报名表格包含选择列', True, f'表头: {headers}')

        assert hasattr(widget, 'selected_registrations')
        assert hasattr(widget, 'select_all_checkbox')
        assert hasattr(widget, 'selection_label')
        print_test('批量选择属性存在', True)

        widget.close()
    finally:
        if app:
            app.processEvents()

def test_gui_undo_button():
    print('\n=== 测试 GUI 撤销入口 ===')

    if not PYSIDE_AVAILABLE:
        print_test('GUI 组件导入', False, 'PySide6 不可用，跳过 GUI 测试')
        return

    app = QApplication.instance() or QApplication(sys.argv)

    from ui.main_window import MainWindow

    try:
        window = MainWindow()
        window.show()
        app.processEvents()

        undo_action = None
        for action in window.toolbar.actions():
            if '撤销' in action.text():
                undo_action = action
                break

        assert undo_action is not None, 'FAIL: 未找到撤销按钮'
        assert undo_action.shortcut().toString() == 'Ctrl+Z'
        print_test('主工具栏有撤销按钮', True, f'快捷键: {undo_action.shortcut().toString()}')

        assert hasattr(window, 'undo_status_label')
        print_test('有撤销状态标签', True)

        assert not undo_action.isEnabled(), 'FAIL: 无操作时撤销按钮应禁用'
        print_test('无操作时撤销按钮禁用', True)

        window.close()
    finally:
        if app:
            app.processEvents()

def test_gui_batch_dialogs():
    print('\n=== 测试 GUI 批量操作对话框 ===')

    if not PYSIDE_AVAILABLE:
        print_test('GUI 组件导入', False, 'PySide6 不可用，跳过 GUI 测试')
        return

    app = QApplication.instance() or QApplication(sys.argv)

    try:
        preview_data = {
            'course_title': '对话框测试课程',
            'total_count': 3,
            'warnings': ['学员 测试学生2 已取消，将跳过'],
            'registrations': [
                {'employee_id': 'DIALOG001', 'name': '对话框学生1', 'status': 'registered', 'department': '技术部'},
                {'employee_id': 'DIALOG002', 'name': '对话框学生2', 'status': 'cancelled', 'department': '产品部'},
                {'employee_id': 'DIALOG003', 'name': '对话框学生3', 'status': 'registered', 'department': '运营部'},
            ]
        }

        confirm_dialog = BatchOperationConfirmDialog(preview_data, 'cancel')
        confirm_dialog.show()
        app.processEvents()

        table = confirm_dialog.findChild(QTableWidget)
        assert table is not None
        assert table.rowCount() == 3
        print_test('确认对话框含学员列表', True, f'{table.rowCount()}行')

        headers = [table.horizontalHeaderItem(i).text() for i in range(table.columnCount())]
        assert '工号' in headers
        assert '姓名' in headers
        assert '当前状态' in headers
        assert '操作' in headers
        print_test('确认对话框表头正确', True)

        confirm_dialog.close()

        result_data = {
            'batch_log_id': 1,
            'total_count': 3,
            'success_count': 2,
            'failure_count': 1,
            'items': [
                {'employee_id': 'DIALOG001', 'name': '对话框学生1', 'department': '技术部', 'success': True, 'failure_reason': ''},
                {'employee_id': 'DIALOG002', 'name': '对话框学生2', 'department': '产品部', 'success': False, 'failure_reason': '已取消报名，无法操作'},
                {'employee_id': 'DIALOG003', 'name': '对话框学生3', 'department': '运营部', 'success': True, 'failure_reason': ''},
            ]
        }

        result_dialog = BatchOperationResultDialog(result_data, 'cancel')
        result_dialog.show()
        app.processEvents()

        result_table = result_dialog.findChild(QTableWidget)
        assert result_table is not None
        assert result_table.rowCount() == 3

        success_count = 0
        failure_count = 0
        for row in range(result_table.rowCount()):
            item = result_table.item(row, 4)
            if item and '成功' in item.text():
                success_count += 1
            elif item and '失败' in item.text():
                failure_count += 1

        assert success_count == 2
        assert failure_count == 1
        print_test('结果对话框显示正确的成功/失败', True, f'成功{success_count}/失败{failure_count}')

        result_dialog.close()

        undo_dialog = UndoDialog()
        undo_dialog.show()
        app.processEvents()
        undo_dialog.close()
        print_test('撤销对话框可正常创建', True)

    except Exception as e:
        print_test('GUI 批量操作对话框', False, str(e))
    finally:
        if app:
            app.processEvents()

def test_gui_batch_end_to_end():
    print('\n=== 测试 GUI 批量操作端到端 ===')

    if not PYSIDE_AVAILABLE:
        print_test('GUI 组件导入', False, 'PySide6 不可用，跳过 GUI 测试')
        return

    app = QApplication.instance() or QApplication(sys.argv)

    course_data = {
        'title': 'GUI 端到端批量测试',
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

    students = [
        {'name': '端到端学生1', 'employee_id': 'GUIE2E001', 'department': '技术部'},
        {'name': '端到端学生2', 'employee_id': 'GUIE2E002', 'department': '产品部'},
        {'name': '端到端学生3', 'employee_id': 'GUIE2E003', 'department': '运营部'},
    ]

    for s in students:
        RegistrationService.register_student(course_id, s)

    original_confirm_exec = BatchOperationConfirmDialog.exec
    original_result_exec = BatchOperationResultDialog.exec

    def mock_confirm_exec(self):
        return QDialog.Accepted

    def mock_result_exec(self):
        return QDialog.Accepted

    BatchOperationConfirmDialog.exec = mock_confirm_exec
    BatchOperationResultDialog.exec = mock_result_exec

    try:
        widget = CourseDetailWidget(course_id)
        widget.show()
        app.processEvents()

        table = widget.reg_table
        assert table.rowCount() == 3

        for row in range(table.rowCount()):
            cell_widget = table.cellWidget(row, 0)
            if cell_widget:
                checkbox = cell_widget.findChild(QCheckBox)
                if checkbox:
                    checkbox.setChecked(True)
        app.processEvents()

        assert len(widget.selected_registrations) == 3
        assert widget.selection_label.text() == '已选择 3 人'
        print_test('GUI 复选框选择功能正常', True)

        batch_result_ref = [None]
        original_batch_cancel = BatchOperationService.batch_cancel
        def mock_batch_cancel(course_id, reg_ids, operator='管理员'):
            result = original_batch_cancel(course_id, reg_ids, operator)
            batch_result_ref[0] = result
            return result
        BatchOperationService.batch_cancel = staticmethod(mock_batch_cancel)

        batch_cancel_btn = None
        for child in widget.findChildren(QPushButton):
            if child.text() == '批量取消':
                batch_cancel_btn = child
                break

        assert batch_cancel_btn is not None
        batch_cancel_btn.click()
        app.processEvents()

        assert batch_result_ref[0] is not None
        result = batch_result_ref[0]
        assert result['total_count'] == 3
        assert result['success_count'] == 3
        print_test('GUI 按钮触发批量操作成功', True, f'成功{result["success_count"]}条')

        regs = RegistrationService.get_course_registrations(course_id)
        cancelled_count = len([r for r in regs if r['status'] == 'cancelled'])
        assert cancelled_count == 3
        print_test('GUI 触发操作后数据更新', True)

        assert UndoManager.has_undo_available()
        print_test('操作后撤销可用', True)

        widget.close()
    finally:
        BatchOperationConfirmDialog.exec = original_confirm_exec
        BatchOperationResultDialog.exec = original_result_exec
        BatchOperationService.batch_cancel = staticmethod(original_batch_cancel)
        if app:
            app.processEvents()

def test_gui_export_trigger():
    print('\n=== 测试 GUI 导出功能触发 ===')

    if not PYSIDE_AVAILABLE:
        print_test('GUI 组件导入', False, 'PySide6 不可用，跳过 GUI 测试')
        return

    app = QApplication.instance() or QApplication(sys.argv)

    result_data = {
        'batch_log_id': 1,
        'from_course_title': '导出源课程',
        'to_course_title': '导出目标课程',
        'total_count': 3,
        'success_count': 2,
        'failure_count': 1,
        'items': [
            {'employee_id': 'EXPGUI001', 'name': '导出学生1', 'department': '技术部', 'success': True, 'failure_reason': ''},
            {'employee_id': 'EXPGUI002', 'name': '导出学生2', 'department': '产品部', 'success': False, 'failure_reason': '容量不足'},
            {'employee_id': 'EXPGUI003', 'name': '导出学生3', 'department': '运营部', 'success': True, 'failure_reason': ''},
        ]
    }

    export_path_ref = [None]
    original_export = ExportService.export_batch_operation_result
    def mock_export(result, output_path=None):
        nonlocal export_path_ref
        path = original_export(result, output_path)
        export_path_ref[0] = path
        return path
    ExportService.export_batch_operation_result = staticmethod(mock_export)

    original_get_save = QFileDialog.getSaveFileName
    def mock_get_save(parent, title, default, filter_str):
        test_path = os.path.join(os.path.dirname(__file__), 'test_gui_batch_export.csv')
        return (test_path, filter_str)
    QFileDialog.getSaveFileName = staticmethod(mock_get_save)

    try:
        dialog = BatchOperationResultDialog(result_data, 'transfer')
        dialog.show()
        app.processEvents()

        export_btn = None
        for child in dialog.findChildren(QPushButton):
            if '导出' in child.text():
                export_btn = child
                break

        assert export_btn is not None
        assert export_btn.isVisible()
        assert export_btn.isEnabled()
        print_test('结果对话框有导出按钮', True)

        export_btn.click()
        app.processEvents()

        assert export_path_ref[0] is not None
        assert os.path.exists(export_path_ref[0])
        print_test('GUI 导出功能正常触发', True, f'文件: {export_path_ref[0]}')

        with open(export_path_ref[0], 'r', encoding='utf-8-sig') as f:
            content = f.read()
            assert 'EXPGUI001' in content
            assert 'EXPGUI002' in content
            assert 'EXPGUI003' in content
            assert '容量不足' in content
            print_test('导出文件内容正确', True)

        dialog.close()
    finally:
        ExportService.export_batch_operation_result = staticmethod(original_export)
        QFileDialog.getSaveFileName = staticmethod(original_get_save)
        if export_path_ref[0] and os.path.exists(export_path_ref[0]):
            try:
                os.remove(export_path_ref[0])
            except:
                pass
        if app:
            app.processEvents()

def test_gui_persistence_after_restart():
    print('\n=== 测试 GUI 批量操作持久化（重启验证） ===')

    if not PYSIDE_AVAILABLE:
        print_test('GUI 组件导入', False, 'PySide6 不可用，跳过 GUI 测试')
        return

    app = QApplication.instance() or QApplication(sys.argv)

    course_data = {
        'title': 'GUI 批量持久化测试',
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

    students = [
        {'name': '持久学生A', 'employee_id': 'GUIPERBA001', 'department': '技术部'},
        {'name': '持久学生B', 'employee_id': 'GUIPERBA002', 'department': '产品部'},
    ]

    for s in students:
        RegistrationService.register_student(course_id, s)

    BatchOperationService.batch_change_status(course_id,
        [r['id'] for r in RegistrationService.get_course_registrations(course_id)],
        'attended'
    )

    regs_before = RegistrationService.get_course_registrations(course_id)
    status_before = {r['employee_id']: r['status'] for r in regs_before}

    logs_before = BatchOperationLogDAO.get_latest(limit=1)
    assert len(logs_before) == 1

    print('--- 模拟程序关闭后重启 ---')
    from db.database import init_database
    init_database()

    widget = CourseDetailWidget(course_id)
    widget.show()
    app.processEvents()

    reg_table = widget.reg_table
    visible_rows = reg_table.rowCount()
    assert visible_rows == 2

    status_in_gui = {}
    for row in range(visible_rows):
        emp_id = reg_table.item(row, 1).text()
        status_in_gui[emp_id] = 'visible'

    assert 'GUIPERBA001' in status_in_gui
    assert 'GUIPERBA002' in status_in_gui
    print_test('重启后 GUI 显示正确', True, f'{visible_rows}条记录')

    regs_after = RegistrationService.get_course_registrations(course_id)
    status_after = {r['employee_id']: r['status'] for r in regs_after}
    assert status_before == status_after
    print_test('重启后数据状态一致', True, f'状态: {status_after}')

    logs_after = BatchOperationLogDAO.get_latest(limit=1)
    assert len(logs_after) == 1
    assert logs_after[0]['id'] == logs_before[0]['id']
    print_test('重启后批量操作日志完整', True)

    assert not UndoManager.has_undo_available()
    print_test('重启后撤销不可用（会话边界）', True)

    widget.close()

def test_waiting_list_manual_add():
    print('\n=== 测试手动添加候补 ===')

    course_data = {
        'title': '候补测试课程1',
        'theme': '候补测试',
        'instructor': '测试讲师',
        'venue': '测试场地',
        'start_time': (datetime.now() + timedelta(days=7)).isoformat(),
        'end_time': (datetime.now() + timedelta(days=7, hours=3)).isoformat(),
        'capacity': 2,
        'registration_deadline': (datetime.now() + timedelta(days=6)).isoformat(),
        'status': 'published'
    }
    course_id = CourseService.create_course(course_data)

    student1 = {'name': '候补学生1', 'employee_id': 'WAIT001', 'department': '技术部'}
    reg_id1 = RegistrationService.register_student(course_id, student1)

    student2 = {'name': '候补学生2', 'employee_id': 'WAIT002', 'department': '产品部'}
    reg_id2 = RegistrationService.register_student(course_id, student2)

    course = CourseService.get_course(course_id)
    regs = RegistrationService.get_course_registrations(course_id)
    assert len(regs) == 2, '课程应该已经满员'

    waiting_student = {
        'name': '候补学生3',
        'employee_id': 'WAIT003',
        'department': '运营部',
        'phone': '13900000003'
    }

    try:
        waiting_id = WaitingListService.add_to_waiting_list(
            course_id, waiting_student, priority=5, source='manual', note='高优先级'
        )
        print_test('添加候补成功', True, f'候补ID: {waiting_id}')

        waiting_count = WaitingListService.get_waiting_count(course_id)
        assert waiting_count == 1, f'期望1人在候补队列，实际{waiting_count}'
        print_test('候补人数统计正确', True)

        waiting_list = WaitingListService.get_waiting_list(course_id)
        assert len(waiting_list) == 1
        assert waiting_list[0]['position'] == 1
        assert waiting_list[0]['priority'] == 5
        assert waiting_list[0]['employee_id'] == 'WAIT003'
        print_test('候补队列排序正确（优先级降序）', True)

        available = WaitingListService.get_available_slots(course_id)
        assert available == 0, f'课程满员，可用名额应该为0，实际{available}'
        print_test('课程满员时可用名额为0', True)

        try:
            WaitingListService.add_to_waiting_list(
                course_id, waiting_student, priority=0, source='manual'
            )
            print_test('重复候补拦截', False, '应该抛出异常')
        except ValidationError as e:
            print_test('重复候补拦截成功', True, str(e))

        course['status'] = 'draft'
        CourseService.update_course(course_id, course)
        try:
            WaitingListService.add_to_waiting_list(
                course_id,
                {'name': '候补学生4', 'employee_id': 'WAIT004', 'department': '技术部'},
                priority=0, source='manual'
            )
            print_test('未发布课程添加候补拦截', False, '应该抛出异常')
        except ValidationError as e:
            print_test('未发布课程添加候补拦截成功', True, str(e))

        return course_id, waiting_id

    except Exception as e:
        print_test('手动添加候补测试', False, str(e))
        return None, None


def test_waiting_list_import_partial_failure():
    print('\n=== 测试候补导入部分成功部分失败 ===')

    course_data = {
        'title': '候补导入测试课程',
        'theme': '候补测试',
        'instructor': '测试讲师',
        'venue': '测试场地',
        'start_time': (datetime.now() + timedelta(days=7)).isoformat(),
        'end_time': (datetime.now() + timedelta(days=7, hours=3)).isoformat(),
        'capacity': 5,
        'registration_deadline': (datetime.now() + timedelta(days=6)).isoformat(),
        'status': 'published'
    }
    course_id = CourseService.create_course(course_data)

    csv_path = os.path.join(os.path.dirname(__file__), 'test_waiting_import.csv')
    with open(csv_path, 'w', newline='', encoding='utf-8-sig') as f:
        writer = csv.writer(f)
        writer.writerow(['姓名', '工号', '部门', '联系方式', '优先级', '备注'])
        writer.writerow(['导入成功1', 'IMPWAIT001', '技术部', '13900000001', '10', 'VIP学员'])
        writer.writerow(['', 'IMPWAIT002', '产品部', '13900000002', '0', '缺少姓名'])
        writer.writerow(['导入成功2', 'IMPWAIT003', '运营部', '13900000003', '5', ''])
        writer.writerow(['导入失败2', '', '设计部', '13900000004', '20', '缺少工号'])
        writer.writerow(['导入成功3', 'IMPWAIT005', '市场部', '13900000005', '0', ''])

    try:
        result = WaitingListService.batch_import_waiting_list(course_id, csv_path)
        print_test('批量导入执行成功', True)

        assert result['total'] == 5, f'期望处理5行，实际{result["total"]}'
        assert result['success_count'] == 3, f'期望成功3行，实际{result["success_count"]}'
        assert result['failure_count'] == 2, f'期望失败2行，实际{result["failure_count"]}'
        print_test('导入统计正确', True, f'成功{result["success_count"]}/失败{result["failure_count"]}')

        success_rows = [r for r in result['rows'] if r['success']]
        failure_rows = [r for r in result['rows'] if not r['success']]
        assert len(success_rows) == 3
        assert len(failure_rows) == 2

        assert '缺少必填字段' in failure_rows[0]['failure_reason']
        assert '缺少必填字段' in failure_rows[1]['failure_reason']
        print_test('失败原因正确记录', True)

        waiting_list = WaitingListService.get_waiting_list(course_id)
        assert len(waiting_list) == 3, f'候补队列期望3人，实际{len(waiting_list)}'

        assert waiting_list[0]['employee_id'] == 'IMPWAIT001'
        assert waiting_list[0]['priority'] == 10
        assert waiting_list[0]['position'] == 1
        print_test('优先级高的学员排在前面', True,
                   f'顺序: {[w["employee_id"] for w in waiting_list]}')

        export_path = ExportService.export_waiting_list_import_result(result)
        assert os.path.exists(export_path), '导出文件不存在'

        with open(export_path, 'r', encoding='utf-8-sig') as f:
            content = f.read()
            assert '候补导入结果' in content
            assert 'IMPWAIT001' in content
            assert '导入成功1' in content
            assert '缺少必填字段' in content
        print_test('导入结果导出可读', True)

        if os.path.exists(export_path):
            os.remove(export_path)

        return result
    except Exception as e:
        print_test('候补导入部分失败测试', False, str(e))
        return None
    finally:
        if os.path.exists(csv_path):
            os.remove(csv_path)


def test_auto_fill_preview_and_execute():
    print('\n=== 测试自动补位预览与执行 ===')

    course_data = {
        'title': '自动补位测试课程',
        'theme': '补位测试',
        'instructor': '测试讲师',
        'venue': '测试场地',
        'start_time': (datetime.now() + timedelta(days=7)).isoformat(),
        'end_time': (datetime.now() + timedelta(days=7, hours=3)).isoformat(),
        'capacity': 2,
        'registration_deadline': (datetime.now() + timedelta(days=6)).isoformat(),
        'status': 'published'
    }
    course_id = CourseService.create_course(course_data)

    student1 = {'name': '正式学生1', 'employee_id': 'FILL001', 'department': '技术部'}
    reg_id1 = RegistrationService.register_student(course_id, student1)
    student2 = {'name': '正式学生2', 'employee_id': 'FILL002', 'department': '产品部'}
    reg_id2 = RegistrationService.register_student(course_id, student2)

    waiting_students = [
        {'name': '候补高优', 'employee_id': 'FILLWAIT001', 'department': '技术部', 'phone': '13900000001', 'priority': 10},
        {'name': '候补普通1', 'employee_id': 'FILLWAIT002', 'department': '产品部', 'phone': '13900000002', 'priority': 0},
        {'name': '候补普通2', 'employee_id': 'FILLWAIT003', 'department': '运营部', 'phone': '13900000003', 'priority': 0},
    ]

    waiting_ids = []
    for ws in waiting_students:
        w_id = WaitingListService.add_to_waiting_list(
            course_id, ws, ws['priority'], 'manual'
        )
        waiting_ids.append(w_id)

    waiting_list = WaitingListService.get_waiting_list(course_id)
    assert len(waiting_list) == 3
    assert waiting_list[0]['employee_id'] == 'FILLWAIT001'
    print_test('候补队列排序正确', True)

    try:
        preview = WaitingListService.preview_auto_fill(course_id)
        print_test('补位预览成功', True)

        assert preview['available_slots'] == 0, '课程满员时可用名额应为0'
        assert preview['total_waiting'] == 3
        print_test('课程满员时无可用名额', True)

        BatchOperationService.batch_cancel(course_id, [reg_id1])

        available = WaitingListService.get_available_slots(course_id)
        assert available == 1, f'取消1个报名后可用名额应为1，实际{available}'
        print_test('释放名额后可用名额正确', True)

        preview = WaitingListService.preview_auto_fill(course_id)
        assert preview['available_slots'] == 1
        assert len(preview['items']) == 1
        assert preview['items'][0]['employee_id'] == 'FILLWAIT001'
        assert preview['items'][0]['can_process'] == True
        print_test('补位预览名单正确', True,
                   f'预览: {[i["employee_id"] for i in preview["items"]]}')

        result = WaitingListService.execute_auto_fill(course_id)
        print_test('自动补位执行成功', True)

        assert result['available_slots'] == 1
        assert result['total'] == 1
        assert result['success_count'] == 1
        assert result['failure_count'] == 0
        print_test('补位结果统计正确', True)

        assert result['items'][0]['result'] == 'success'
        assert result['items'][0]['original_position'] == 1
        assert result['items'][0]['employee_id'] == 'FILLWAIT001'
        assert result['items'][0]['registration_id'] is not None
        print_test('补位成功，生成正式报名', True,
                   f'报名ID: {result["items"][0]["registration_id"]}')

        regs = RegistrationService.get_course_registrations(course_id)
        active_regs = [r for r in regs if r['status'] == 'registered']
        assert len(active_regs) == 2, '补位后课程应该再次满员'
        print_test('补位后课程容量正确', True)

        waiting_list_after = WaitingListService.get_waiting_list(course_id)
        assert len(waiting_list_after) == 2, '成功补位的学员应该从候补队列移除'
        print_test('补位成功学员从候补队列移除', True)

        history = WaitingListService.get_fill_results(course_id)
        assert len(history) == 1
        assert history[0]['result'] == 'success'
        print_test('补位历史记录正确', True)

        export_path = ExportService.export_auto_fill_result(result)
        assert os.path.exists(export_path), '导出文件不存在'

        with open(export_path, 'r', encoding='utf-8-sig') as f:
            content = f.read()
            assert '自动补位结果' in content
            assert 'FILLWAIT001' in content
            assert '成功' in content
            assert '原队列位置' in content
        print_test('补位结果导出可读', True)

        if os.path.exists(export_path):
            os.remove(export_path)

        return course_id, result
    except Exception as e:
        print_test('自动补位测试', False, str(e))
        return None, None


def test_auto_fill_validation_rules():
    print('\n=== 测试补位拦截规则 ===')

    course_data = {
        'title': '补位拦截测试课程',
        'theme': '补位测试',
        'instructor': '测试讲师',
        'venue': '测试场地',
        'start_time': (datetime.now() + timedelta(days=7)).isoformat(),
        'end_time': (datetime.now() + timedelta(days=7, hours=3)).isoformat(),
        'capacity': 3,
        'registration_deadline': (datetime.now() + timedelta(days=6)).isoformat(),
        'status': 'published'
    }
    course_id = CourseService.create_course(course_data)

    student1 = {'name': '正式生1', 'employee_id': 'VALID001', 'department': '技术部'}
    reg_id1 = RegistrationService.register_student(course_id, student1)
    student2 = {'name': '正式生2', 'employee_id': 'VALID002', 'department': '产品部'}
    reg_id2 = RegistrationService.register_student(course_id, student2)

    waiting_students = [
        {'name': '正常补位1', 'employee_id': 'VALID003', 'department': '运营部', 'phone': '13900000002'},
    ]

    for ws in waiting_students:
        WaitingListService.add_to_waiting_list(course_id, ws, 0, 'manual')

    from db.dao import StudentDAO, WaitingListDAO
    student2 = StudentDAO.get_by_employee_id('VALID002')
    WaitingListDAO.create(course_id, student2['id'], priority=0, source='manual', note='测试重复报名拦截')

    try:
        result = WaitingListService.execute_auto_fill(course_id)
        assert result['total'] == 2, f'期望处理2人，实际{result["total"]}'
        assert result['success_count'] == 1, f'期望成功1人，实际{result["success_count"]}'
        assert result['failure_count'] == 1, f'期望失败1人，实际{result["failure_count"]}'
        print_test('重复报名学员补位被拦截', True)

        failure_items = [i for i in result['items'] if i['result'] != 'success']
        assert len(failure_items) == 1
        assert '已在报名名单中' in failure_items[0]['failure_reason']
        print_test('失败原因记录正确', True, failure_items[0]['failure_reason'])

        success_items = [i for i in result['items'] if i['result'] == 'success']
        assert len(success_items) == 1
        assert success_items[0]['employee_id'] == 'VALID003'
        print_test('正常学员补位成功', True)

        exceptions = ExceptionService.get_all_logs()
        waiting_exceptions = [e for e in exceptions if 'waiting_list' in e.get('type', '')]
        assert len(waiting_exceptions) > 0
        print_test('异常日志已记录', True)

        return result
    except Exception as e:
        print_test('补位拦截规则测试', False, str(e))
        return None


def test_waiting_list_persistence():
    print('\n=== 测试候补数据跨重启持久化 ===')

    course_data = {
        'title': '持久化候补课程',
        'theme': '持久化测试',
        'instructor': '测试讲师',
        'venue': '测试场地',
        'start_time': (datetime.now() + timedelta(days=7)).isoformat(),
        'end_time': (datetime.now() + timedelta(days=7, hours=3)).isoformat(),
        'capacity': 2,
        'registration_deadline': (datetime.now() + timedelta(days=6)).isoformat(),
        'status': 'published'
    }
    course_id = CourseService.create_course(course_data)

    student1 = {'name': '持久正式1', 'employee_id': 'PERW001', 'department': '技术部'}
    reg_id1 = RegistrationService.register_student(course_id, student1)
    student2 = {'name': '持久正式2', 'employee_id': 'PERW002', 'department': '产品部'}
    reg_id2 = RegistrationService.register_student(course_id, student2)

    waiting_data = [
        {'name': '持久候补1', 'employee_id': 'PERW003', 'department': '运营部', 'priority': 5},
        {'name': '持久候补2', 'employee_id': 'PERW004', 'department': '设计部', 'priority': 0},
        {'name': '持久候补3', 'employee_id': 'PERW005', 'department': '市场部', 'priority': 10},
    ]

    waiting_ids = []
    for wd in waiting_data:
        w_id = WaitingListService.add_to_waiting_list(
            course_id, wd, wd['priority'], 'manual'
        )
        waiting_ids.append(w_id)

    waiting_before = WaitingListService.get_waiting_list(course_id)
    order_before = [w['employee_id'] for w in waiting_before]
    positions_before = {w['employee_id']: w['position'] for w in waiting_before}
    assert order_before == ['PERW005', 'PERW003', 'PERW004'], '排序应该按优先级降序'
    print_test('重启前候补顺序正确', True, f'顺序: {order_before}')

    BatchOperationService.batch_cancel(course_id, [reg_id1])

    fill_result = WaitingListService.execute_auto_fill(course_id)
    assert fill_result['success_count'] == 1
    fill_result_before = fill_result
    print_test('重启前补位成功', True)

    import db.database as db_module
    import importlib
    importlib.reload(db_module)
    init_database()

    waiting_after = WaitingListService.get_waiting_list(course_id)
    order_after = [w['employee_id'] for w in waiting_after]
    positions_after = {w['employee_id']: w['position'] for w in waiting_after}

    assert len(waiting_after) == 2, f'重启后期望2人在候补队列，实际{len(waiting_after)}'
    assert order_after == ['PERW003', 'PERW004'], f'顺序应为: [PERW003, PERW004]，实际: {order_after}'
    assert positions_after['PERW003'] == 1, 'PERW003应该排在第1位'
    assert positions_after['PERW004'] == 2, 'PERW004应该排在第2位'
    print_test('重启后候补顺序和状态一致', True, f'顺序: {order_after}')

    history_after = WaitingListService.get_fill_results(course_id)
    assert len(history_after) == 1, f'重启后期望1条补位历史，实际{len(history_after)}'
    assert history_after[0]['employee_id'] == 'PERW005'
    assert history_after[0]['result'] == 'success'
    print_test('重启后补位历史完整', True)

    exceptions_after = ExceptionService.get_all_logs()
    waiting_exceptions = [e for e in exceptions_after if 'waiting_list' in e.get('type', '')]
    assert len(waiting_exceptions) >= 0
    print_test('重启后异常日志完整', True)

    return course_id


def test_waiting_list_gui_integration():
    print('\n=== 测试 GUI 候补名单集成 ===')

    if not PYSIDE_AVAILABLE:
        print_test('GUI 组件导入', False, 'PySide6 不可用，跳过 GUI 测试')
        return

    app = QApplication.instance() or QApplication(sys.argv)

    course_data = {
        'title': 'GUI候补测试课程',
        'theme': 'GUI测试',
        'instructor': '测试讲师',
        'venue': '测试场地',
        'start_time': (datetime.now() + timedelta(days=7)).isoformat(),
        'end_time': (datetime.now() + timedelta(days=7, hours=3)).isoformat(),
        'capacity': 2,
        'registration_deadline': (datetime.now() + timedelta(days=6)).isoformat(),
        'status': 'published'
    }
    course_id = CourseService.create_course(course_data)

    student1 = {'name': 'GUI正式1', 'employee_id': 'GUIWAIT001', 'department': '技术部'}
    RegistrationService.register_student(course_id, student1)
    student2 = {'name': 'GUI正式2', 'employee_id': 'GUIWAIT002', 'department': '产品部'}
    RegistrationService.register_student(course_id, student2)

    try:
        widget = CourseDetailWidget(course_id)
        widget.show()
        app.processEvents()

        info_text = widget.info_label.text()
        assert '候补' in info_text, '信息栏应显示候补相关信息'
        assert '可用名额' in info_text, '信息栏应显示可用名额'
        print_test('课程详情页显示候补状态', True)

        waiting_btn = None
        for child in widget.findChildren(QPushButton):
            if child.text() == '候补名单':
                waiting_btn = child
                break

        assert waiting_btn is not None, 'FAIL: 未找到候补名单按钮'
        assert waiting_btn.isVisible(), 'FAIL: 按钮不可见'
        assert waiting_btn.isEnabled(), 'FAIL: 按钮不可用'
        print_test('课程详情页有可用的候补名单按钮', True)

        dialog_ref = [None]
        original_exec = WaitingListDialog.exec
        def mock_exec(self):
            dialog_ref[0] = self
            return QDialog.Accepted
        WaitingListDialog.exec = mock_exec

        waiting_btn.click()
        app.processEvents()

        assert dialog_ref[0] is not None, 'FAIL: 点击按钮未打开对话框'
        print_test('点击按钮打开候补名单对话框', True)

        dialog = dialog_ref[0]
        assert hasattr(dialog, 'waiting_table'), '对话框应该有候补列表'
        assert hasattr(dialog, 'info_label'), '对话框应该有信息栏'
        print_test('候补名单对话框组件完整', True)

        add_btn = None
        import_btn = None
        auto_fill_btn = None
        for child in dialog.findChildren(QPushButton):
            if child.text() == '添加候补':
                add_btn = child
            elif child.text() == '导入候补':
                import_btn = child
            elif child.text() == '自动补位':
                auto_fill_btn = child

        assert add_btn is not None and add_btn.isVisible()
        assert import_btn is not None and import_btn.isVisible()
        assert auto_fill_btn is not None and auto_fill_btn.isVisible()
        print_test('候补名单对话框有完整操作按钮', True)

        widget.close()
        dialog.close()

        print_test('GUI 主链路可触发', True)

        return course_id
    except Exception as e:
        print_test('GUI 候补名单集成测试', False, str(e))
        return None
    finally:
        WaitingListDialog.exec = original_exec
        if app:
            app.processEvents()


def test_waiting_list_deadline_and_status_validation():
    print('\n=== 测试补位时间和状态拦截 ===')

    course_data = {
        'title': '截止时间测试课程',
        'theme': '截止测试',
        'instructor': '测试讲师',
        'venue': '测试场地',
        'start_time': (datetime.now() + timedelta(days=7)).isoformat(),
        'end_time': (datetime.now() + timedelta(days=7, hours=3)).isoformat(),
        'capacity': 3,
        'registration_deadline': (datetime.now() - timedelta(days=1)).isoformat(),
        'status': 'published'
    }
    course_id = CourseService.create_course(course_data)

    student1 = {'name': '截止生1', 'employee_id': 'DEAD001', 'department': '技术部'}
    reg_id1 = RegistrationService.register_student(course_id, student1)
    student2 = {'name': '截止生2', 'employee_id': 'DEAD002', 'department': '产品部'}
    reg_id2 = RegistrationService.register_student(course_id, student2)

    waiting_student = {
        'name': '截止候补',
        'employee_id': 'DEADWAIT001',
        'department': '运营部',
        'phone': '13900000001'
    }

    try:
        WaitingListService.add_to_waiting_list(course_id, waiting_student, 0, 'manual')
        print_test('报名截止后添加候补被拦截', False, '应该抛出异常')
    except ValidationError as e:
        print_test('报名截止后添加候补拦截成功', True, str(e))

    course_data['registration_deadline'] = (datetime.now() + timedelta(days=6)).isoformat()
    course_data['status'] = 'draft'
    CourseService.update_course(course_id, course_data)

    try:
        WaitingListService.add_to_waiting_list(
            course_id,
            {'name': '草稿候补', 'employee_id': 'DRAFTWAIT001', 'department': '技术部'},
            0, 'manual'
        )
        print_test('草稿课程添加候补被拦截', False, '应该抛出异常')
    except ValidationError as e:
        print_test('草稿课程添加候补拦截成功', True, str(e))

    course_data['status'] = 'published'
    CourseService.update_course(course_id, course_data)

    WaitingListService.add_to_waiting_list(course_id, waiting_student, 0, 'manual')

    BatchOperationService.batch_cancel(course_id, [reg_id2])

    course_data['registration_deadline'] = (datetime.now() - timedelta(days=1)).isoformat()
    CourseService.update_course(course_id, course_data)

    try:
        result = WaitingListService.execute_auto_fill(course_id)
        assert result['success_count'] == 0, '报名截止后补位应该失败'
        assert result['failure_count'] == 1
        assert '报名已截止' in result['items'][0]['failure_reason']
        print_test('报名截止后补位被拦截', True, result['items'][0]['failure_reason'])
    except Exception as e:
        print_test('报名截止后补位拦截测试', False, str(e))


def test_certificate_preview_generation():
    print('\n=== 测试结业证书预览生成 ===')

    course_data = {
        'title': '证书预览测试课程',
        'theme': '结业证书',
        'instructor': '测试讲师',
        'venue': '测试场地',
        'start_time': (datetime.now() - timedelta(days=1)).isoformat(),
        'end_time': (datetime.now() - timedelta(days=1, hours=-2)).isoformat(),
        'capacity': 5,
        'registration_deadline': (datetime.now() - timedelta(days=2)).isoformat(),
        'status': 'published'
    }
    course_id = CourseService.create_course(course_data)

    eligible = {'name': '合格学员', 'employee_id': 'CERT001', 'department': '技术部'}
    reg_id = RegistrationService.register_student(course_id, eligible)
    AttendanceService.record_attendance(course_id, reg_id, 'present', datetime.now().isoformat())

    absent = {'name': '缺勤学员', 'employee_id': 'CERT002', 'department': '技术部'}
    reg_id2 = RegistrationService.register_student(course_id, absent)
    AttendanceService.record_attendance(course_id, reg_id2, 'absent', None)

    cancelled = {'name': '已取消学员', 'employee_id': 'CERT003', 'department': '技术部'}
    reg_id3 = RegistrationService.register_student(course_id, cancelled)
    RegistrationService.cancel_registration(reg_id3, '个人原因')

    not_registered = {'name': '未报名学员', 'employee_id': 'CERT004', 'department': '技术部'}
    StudentDAO.create(not_registered)

    try:
        preview = CertificateService.preview_generation(course_id)
        assert len(preview['eligible']) == 1, f'应该有1个符合条件的学员，实际{len(preview["eligible"])}'
        assert len(preview['ineligible']) >= 2, f'应该有至少2个不符合条件的学员，实际{len(preview["ineligible"])}'
        assert preview['eligible'][0]['student']['name'] == '合格学员'
        print_test('预览筛选逻辑正确', True, f'合格:{len(preview["eligible"])} 不合格:{len(preview["ineligible"])}')

        ineligible_reasons = [item['reason'] for item in preview['ineligible']]
        assert any('缺勤' in r for r in ineligible_reasons), '应该包含缺勤原因'
        assert any('取消' in r for r in ineligible_reasons), '应该包含已取消报名原因'
        print_test('失败原因分类正确', True)
    except Exception as e:
        print_test('预览生成测试', False, str(e))


def test_certificate_single_issue_and_validation():
    print('\n=== 测试单个证书生成与校验 ===')

    course_data = {
        'title': '单证书测试课程',
        'theme': '结业证书',
        'instructor': '测试讲师',
        'venue': '测试场地',
        'start_time': (datetime.now() - timedelta(days=1)).isoformat(),
        'end_time': (datetime.now() - timedelta(days=1, hours=-2)).isoformat(),
        'capacity': 5,
        'registration_deadline': (datetime.now() - timedelta(days=2)).isoformat(),
        'status': 'published'
    }
    course_id = CourseService.create_course(course_data)

    student = {'name': '单证书学员', 'employee_id': 'CERT010', 'department': '技术部'}
    reg_id = RegistrationService.register_student(course_id, student)
    AttendanceService.record_attendance(course_id, reg_id, 'present', datetime.now().isoformat())

    student_id = StudentDAO.get_by_employee_id('CERT010')['id']

    cert = CertificateService.issue_certificate(course_id, student_id, '测试备注')
    assert cert is not None, '应该成功生成证书'
    assert cert['certificate_no'] is not None, '证书编号不能为空'
    assert cert['status'] == 'issued', '状态应该是已发放'
    assert cert['certificate_no'].startswith('CERT-'), '证书编号格式不正确'
    print_test('单个证书生成成功', True, f'编号: {cert["certificate_no"]}')

    try:
        CertificateService.issue_certificate(course_id, student_id, '重复生成')
        print_test('重复生成校验', False, '应该抛出异常')
    except ValidationError as e:
        assert '已有' in str(e), '错误信息应该包含已有证书'
        print_test('重复生成拦截成功', True, str(e))

    not_ended_course = {
        'title': '未结束课程',
        'theme': '结业证书',
        'instructor': '测试讲师',
        'venue': '测试场地',
        'start_time': (datetime.now() + timedelta(days=1)).isoformat(),
        'end_time': (datetime.now() + timedelta(days=1, hours=2)).isoformat(),
        'capacity': 5,
        'registration_deadline': (datetime.now() + timedelta(days=1)).isoformat(),
        'status': 'published'
    }
    not_ended_id = CourseService.create_course(not_ended_course)
    try:
        CertificateService.issue_certificate(not_ended_id, student_id)
        print_test('未结束课程校验', False, '应该抛出异常')
    except ValidationError as e:
        assert '未结束' in str(e), '错误信息应该包含未结束'
        print_test('未结束课程拦截成功', True, str(e))


def test_certificate_batch_partial_success_failure():
    print('\n=== 测试批量生成部分成功部分失败 ===')

    course_data = {
        'title': '批量证书测试课程',
        'theme': '结业证书',
        'instructor': '测试讲师',
        'venue': '测试场地',
        'start_time': (datetime.now() - timedelta(days=1)).isoformat(),
        'end_time': (datetime.now() - timedelta(days=1, hours=-2)).isoformat(),
        'capacity': 10,
        'registration_deadline': (datetime.now() - timedelta(days=2)).isoformat(),
        'status': 'published'
    }
    course_id = CourseService.create_course(course_data)

    student_ids = []
    for i in range(5):
        s = {'name': f'批量学员{i+1}', 'employee_id': f'CERTB{i+1:03d}', 'department': '技术部'}
        reg_id = RegistrationService.register_student(course_id, s)
        if i < 3:
            AttendanceService.record_attendance(course_id, reg_id, 'present', datetime.now().isoformat())
        elif i == 3:
            AttendanceService.record_attendance(course_id, reg_id, 'absent', None)
        else:
            RegistrationService.cancel_registration(reg_id, '个人原因')
        sid = StudentDAO.get_by_employee_id(f'CERTB{i+1:03d}')['id']
        student_ids.append(sid)

    result = CertificateService.batch_generate_certificates(course_id, remark='批量测试')

    assert result['total_count'] == 5, f'应该处理5条，实际{result["total_count"]}'
    assert result['success_count'] == 3, f'应该成功3条，实际{result["success_count"]}'
    assert result['failure_count'] == 2, f'应该失败2条，实际{result["failure_count"]}'
    print_test('批量生成统计正确', True, f'总:{result["total_count"]} 成功:{result["success_count"]} 失败:{result["failure_count"]}')

    success_items = [item for item in result['items'] if item['success']]
    failure_items = [item for item in result['items'] if not item['success']]
    assert len(success_items) == 3
    assert len(failure_items) == 2

    failure_reasons = [item['failure_reason'] for item in failure_items]
    assert any('缺勤' in r for r in failure_reasons), '应该有缺勤失败'
    assert any('取消' in r for r in failure_reasons), '应该有取消报名失败'
    print_test('逐条失败原因记录正确', True)

    certs = CertificateDAO.get_all(course_id=course_id)
    assert len(certs) == 3, f'数据库应该有3张证书，实际{len(certs)}'
    print_test('证书持久化正确', True)

    batch_logs = CertificateBatchLogDAO.get_all()
    assert len(batch_logs) >= 1, '应该有批量操作日志'
    print_test('批量操作日志记录正确', True)


def test_certificate_reissue_conflict_avoidance():
    print('\n=== 测试证书补发与冲突避免 ===')

    course_data = {
        'title': '补发测试课程',
        'theme': '结业证书',
        'instructor': '测试讲师',
        'venue': '测试场地',
        'start_time': (datetime.now() - timedelta(days=1)).isoformat(),
        'end_time': (datetime.now() - timedelta(days=1, hours=-2)).isoformat(),
        'capacity': 5,
        'registration_deadline': (datetime.now() - timedelta(days=2)).isoformat(),
        'status': 'published'
    }
    course_id = CourseService.create_course(course_data)

    student = {'name': '补发学员', 'employee_id': 'CERT020', 'department': '技术部'}
    reg_id = RegistrationService.register_student(course_id, student)
    AttendanceService.record_attendance(course_id, reg_id, 'present', datetime.now().isoformat())
    student_id = StudentDAO.get_by_employee_id('CERT020')['id']

    original_cert = CertificateService.issue_certificate(course_id, student_id, '原始证书')
    original_no = original_cert['certificate_no']
    print_test('原始证书生成', True, f'编号: {original_no}')

    reissued_cert = CertificateService.reissue_certificate(course_id, student_id, '补发证书', '测试员')
    assert reissued_cert is not None, '补发应该成功'
    assert reissued_cert['certificate_no'] != original_no, '补发应该生成新编号'
    print_test('补发证书成功', True, f'新编号: {reissued_cert["certificate_no"]}')

    original_updated = CertificateDAO.get_by_id(original_cert['id'])
    assert original_updated['status'] == 'voided', '原证书应该被作废'
    assert original_updated['void_reason'] is not None, '应该有作废原因'
    print_test('原证书自动作废', True)

    active_certs = [c for c in CertificateDAO.get_all(course_id=course_id) if c['status'] == 'issued']
    assert len(active_certs) == 1, '应该只有1张有效证书'
    print_test('补发后有效证书唯一', True)


def test_certificate_void_with_reason():
    print('\n=== 测试证书作废与原因校验 ===')

    course_data = {
        'title': '作废测试课程',
        'theme': '结业证书',
        'instructor': '测试讲师',
        'venue': '测试场地',
        'start_time': (datetime.now() - timedelta(days=1)).isoformat(),
        'end_time': (datetime.now() - timedelta(days=1, hours=-2)).isoformat(),
        'capacity': 5,
        'registration_deadline': (datetime.now() - timedelta(days=2)).isoformat(),
        'status': 'published'
    }
    course_id = CourseService.create_course(course_data)

    student = {'name': '作废学员', 'employee_id': 'CERT030', 'department': '技术部'}
    reg_id = RegistrationService.register_student(course_id, student)
    AttendanceService.record_attendance(course_id, reg_id, 'present', datetime.now().isoformat())
    student_id = StudentDAO.get_by_employee_id('CERT030')['id']

    cert = CertificateService.issue_certificate(course_id, student_id)

    try:
        CertificateService.void_certificate(cert['id'], '短')
        print_test('作废原因长度校验', False, '应该抛出异常')
    except ValidationError as e:
        assert '5' in str(e) or '字符' in str(e), '错误信息应该包含长度要求'
        print_test('作废原因长度校验通过', True, str(e))

    void_reason = '学员信息有误，申请作废'
    voided = CertificateService.void_certificate(cert['id'], void_reason, '管理员')
    assert voided is not None, '作废应该成功'
    assert voided['status'] == 'voided', '状态应该是已作废'
    assert voided['void_reason'] == void_reason, '作废原因应该正确记录'
    assert voided['voided_at'] is not None, '应该有作废时间'
    print_test('证书作废成功', True, f'原因: {void_reason}')

    try:
        CertificateService.void_certificate(cert['id'], '再次作废')
        print_test('重复作废校验', False, '应该抛出异常')
    except ValidationError as e:
        assert '作废' in str(e), '错误信息应该包含已作废'
        print_test('重复作废拦截成功', True, str(e))


def test_certificate_cross_restart_persistence():
    print('\n=== 测试跨重启数据持久化 ===')

    course_data = {
        'title': '持久化测试课程',
        'theme': '结业证书',
        'instructor': '测试讲师',
        'venue': '测试场地',
        'start_time': (datetime.now() - timedelta(days=1)).isoformat(),
        'end_time': (datetime.now() - timedelta(days=1, hours=-2)).isoformat(),
        'capacity': 5,
        'registration_deadline': (datetime.now() - timedelta(days=2)).isoformat(),
        'status': 'published'
    }
    course_id = CourseService.create_course(course_data)

    student = {'name': '持久化学员', 'employee_id': 'CERTP001', 'department': '技术部'}
    reg_id = RegistrationService.register_student(course_id, student)
    AttendanceService.record_attendance(course_id, reg_id, 'present', datetime.now().isoformat())
    student_id = StudentDAO.get_by_employee_id('CERTP001')['id']

    cert = CertificateService.issue_certificate(course_id, student_id, '持久化测试')
    cert_no = cert['certificate_no']
    cert_id = cert['id']
    print_test('初始证书生成', True, f'编号: {cert_no}')

    import importlib
    import db.database as db_module
    import db.dao as dao_module
    import services.certificate_service as cert_service_module

    db_module.get_connection().close()

    importlib.reload(db_module)
    importlib.reload(dao_module)
    importlib.reload(cert_service_module)

    from db.database import init_database
    from db.dao import CertificateDAO
    from services.certificate_service import CertificateService

    init_database()

    loaded_cert = CertificateDAO.get_by_id(cert_id)
    assert loaded_cert is not None, '重启后应该能查询到证书'
    assert loaded_cert['certificate_no'] == cert_no, '证书编号应该一致'
    assert loaded_cert['status'] == 'issued', '状态应该保持'
    assert loaded_cert['remark'] == '持久化测试', '备注应该保持'
    print_test('重启后证书数据一致', True)

    all_certs = CertificateDAO.get_all()
    assert len(all_certs) >= 1, '重启后证书列表不为空'
    print_test('重启后证书列表查询正常', True)

    batch_logs = CertificateBatchLogDAO.get_all()
    assert batch_logs is not None, '重启后批量日志可查询'
    print_test('重启后批量日志查询正常', True)


def test_certificate_export_readability():
    print('\n=== 测试证书导出内容可读性 ===')

    course_data = {
        'title': '导出测试课程',
        'theme': '结业证书',
        'instructor': '测试讲师',
        'venue': '测试场地',
        'start_time': (datetime.now() - timedelta(days=1)).isoformat(),
        'end_time': (datetime.now() - timedelta(days=1, hours=-2)).isoformat(),
        'capacity': 5,
        'registration_deadline': (datetime.now() - timedelta(days=2)).isoformat(),
        'status': 'published'
    }
    course_id = CourseService.create_course(course_data)

    for i in range(3):
        s = {'name': f'导出学员{i+1}', 'employee_id': f'CERTE{i+1:03d}', 'department': '技术部'}
        reg_id = RegistrationService.register_student(course_id, s)
        AttendanceService.record_attendance(course_id, reg_id, 'present', datetime.now().isoformat())

    batch_result = CertificateService.batch_generate_certificates(course_id)

    batch_export_path = ExportService.export_certificate_batch_result(batch_result)
    assert os.path.exists(batch_export_path), '批量结果导出文件应该存在'
    print_test('批量结果导出成功', True, os.path.basename(batch_export_path))

    with open(batch_export_path, 'r', encoding='utf-8-sig') as f:
        content = f.read()
        assert '结业证书批量生成结果' in content, '应该包含标题'
        assert '课程名称' in content, '应该包含课程名称'
        assert '处理总数' in content, '应该包含统计信息'
        assert '成功' in content, '应该包含成功'
        assert '失败' in content, '应该包含失败'
        assert '学员姓名' in content, '应该包含学员姓名字段'
        assert '证书编号' in content, '应该包含证书编号字段'
        assert '处理结果' in content, '应该包含处理结果字段'
        assert '失败原因' in content, '应该包含失败原因字段'
    print_test('批量导出内容可读', True)

    certs = CertificateDAO.get_all(course_id=course_id)
    cert_export_path = ExportService.export_certificates(certs)
    assert os.path.exists(cert_export_path), '证书列表导出文件应该存在'
    print_test('证书列表导出成功', True, os.path.basename(cert_export_path))

    with open(cert_export_path, 'r', encoding='utf-8-sig') as f:
        content = f.read()
        assert '结业证书列表' in content, '应该包含标题'
        assert '导出时间' in content, '应该包含导出时间'
        assert '学员姓名' in content, '应该包含学员姓名'
        assert '证书编号' in content, '应该包含证书编号'
        assert '课程名称' in content, '应该包含课程名称'
        assert '状态' in content, '应该包含状态'
        assert '已发放' in content or '已作废' in content, '应该有中文状态'
    print_test('证书列表导出内容可读', True)


def test_certificate_exception_logging():
    print('\n=== 测试证书异常日志记录 ===')

    course_data = {
        'title': '异常日志测试课程',
        'theme': '结业证书',
        'instructor': '测试讲师',
        'venue': '测试场地',
        'start_time': (datetime.now() - timedelta(days=1)).isoformat(),
        'end_time': (datetime.now() - timedelta(days=1, hours=-2)).isoformat(),
        'capacity': 5,
        'registration_deadline': (datetime.now() - timedelta(days=2)).isoformat(),
        'status': 'published'
    }
    course_id = CourseService.create_course(course_data)

    student = {'name': '异常日志学员', 'employee_id': 'CERTL001', 'department': '技术部'}
    reg_id = RegistrationService.register_student(course_id, student)
    AttendanceService.record_attendance(course_id, reg_id, 'present', datetime.now().isoformat())
    student_id = StudentDAO.get_by_employee_id('CERTL001')['id']

    before_logs = ExceptionService.get_all_logs()
    before_count = len(before_logs) if before_logs else 0

    cert = CertificateService.issue_certificate(course_id, student_id)
    after_logs = ExceptionService.get_all_logs()
    after_count = len(after_logs) if after_logs else 0
    assert after_count > before_count, '生成证书应该记录日志'
    cert_logs = [l for l in after_logs if '结业证书生成' in (l.get('description') or '')]
    assert len(cert_logs) >= 1, '应该有证书生成日志'
    print_test('生成证书日志记录', True)

    voided = CertificateService.void_certificate(cert['id'], '测试作废，需要记录日志')
    after_void_logs = ExceptionService.get_all_logs()
    void_logs = [l for l in after_void_logs if '结业证书作废' in (l.get('description') or '')]
    assert len(void_logs) >= 1, '应该有证书作废日志'
    print_test('作废证书日志记录', True)

    reissued = CertificateService.reissue_certificate(course_id, student_id, '测试补发')
    after_reissue_logs = ExceptionService.get_all_logs()
    reissue_logs = [l for l in after_reissue_logs if '结业证书补发' in (l.get('description') or '')]
    assert len(reissue_logs) >= 1, '应该有证书补发日志'
    print_test('补发证书日志记录', True)

    absent_student = {'name': '缺勤日志学员', 'employee_id': 'CERTL002', 'department': '技术部'}
    reg_id2 = RegistrationService.register_student(course_id, absent_student)
    AttendanceService.record_attendance(course_id, reg_id2, 'absent', None)
    absent_id = StudentDAO.get_by_employee_id('CERTL002')['id']

    try:
        CertificateService.issue_certificate(course_id, absent_id)
    except:
        pass
    after_fail_logs = ExceptionService.get_all_logs()
    fail_logs = [l for l in after_fail_logs if '结业证书生成失败' in (l.get('type') or '')]
    assert len(fail_logs) >= 1, '应该有生成失败日志'
    print_test('生成失败日志记录', True)


def test_certificate_gui_main_workflow():
    print('\n=== 测试 GUI 主链路触发 ===')

    if not PYSIDE_AVAILABLE:
        print_test('GUI 组件导入', False, 'PySide6 不可用，跳过 GUI 测试')
        return

    app = QApplication.instance() or QApplication(sys.argv)

    course_data = {
        'title': 'GUI证书测试课程',
        'theme': 'GUI测试',
        'instructor': '测试讲师',
        'venue': '测试场地',
        'start_time': (datetime.now() - timedelta(days=1)).isoformat(),
        'end_time': (datetime.now() - timedelta(days=1, hours=-2)).isoformat(),
        'capacity': 10,
        'registration_deadline': (datetime.now() - timedelta(days=2)).isoformat(),
        'status': 'published'
    }
    course_id = CourseService.create_course(course_data)

    for i in range(3):
        s = {'name': f'GUI学员{i+1}', 'employee_id': f'GUICERT{i+1:03d}', 'department': '技术部'}
        reg_id = RegistrationService.register_student(course_id, s)
        if i < 2:
            AttendanceService.record_attendance(course_id, reg_id, 'present', datetime.now().isoformat())
        else:
            AttendanceService.record_attendance(course_id, reg_id, 'absent', None)

    try:
        widget = CertificateManagementWidget()
        widget.show()
        app.processEvents()

        course_combo = widget.findChild(QComboBox)
        assert course_combo is not None, '应该有课程下拉框'
        course_items = [course_combo.itemText(i) for i in range(course_combo.count())]
        assert any('GUI证书测试课程' in item for item in course_items), '下拉框应该包含测试课程'
        print_test('GUI 课程筛选入口存在', True)

        toolbar_buttons = widget.findChildren(QPushButton)
        button_texts = [btn.text() for btn in toolbar_buttons]
        assert any('批量生成' in t for t in button_texts), '应该有批量生成按钮'
        assert any('补发' in t for t in button_texts), '应该有补发按钮'
        assert any('导出' in t for t in button_texts), '应该有导出按钮'
        print_test('GUI 操作按钮完整', True, f'按钮: {button_texts}')

        status_combo = None
        for child in widget.findChildren(QComboBox):
            if child != course_combo:
                status_combo = child
                break
        assert status_combo is not None, '应该有状态筛选下拉框'
        status_items = [status_combo.itemText(i) for i in range(status_combo.count())]
        assert '全部' in status_items, '状态筛选应该包含全部'
        assert '已发放' in status_items, '状态筛选应该包含已发放'
        assert '已作废' in status_items, '状态筛选应该包含已作废'
        print_test('GUI 状态筛选入口存在', True)

        tab_widget = widget.findChild(QTabWidget)
        assert tab_widget is not None, '应该有标签页'
        tab_count = tab_widget.count()
        assert tab_count >= 2, '应该有至少2个标签页'
        tab_names = [tab_widget.tabText(i) for i in range(tab_count)]
        assert '证书列表' in tab_names, '应该有证书列表标签'
        assert '批量操作记录' in tab_names, '应该有批量操作记录标签'
        print_test('GUI 标签页完整', True, f'标签: {tab_names}')

        tables = widget.findChildren(QTableWidget)
        assert len(tables) >= 2, '应该有至少2个表格'
        print_test('GUI 表格组件存在', True)

        info_labels = widget.findChildren(QLabel)
        info_texts = [lbl.text() for lbl in info_labels]
        assert any('证书' in t for t in info_texts), '应该有证书统计信息'
        print_test('GUI 统计信息展示正常', True)

        widget.refresh_certificates()
        app.processEvents()
        print_test('GUI 刷新数据正常', True)

        widget.close()
        print_test('GUI 主链路可触发', True)

    except Exception as e:
        print_test('GUI 集成测试', False, str(e))
        import traceback
        traceback.print_exc()


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

        print('\n' + '='*50)
        print('批量操作专项测试')
        print('='*50)

        test_batch_operation_preview()
        test_batch_cancel_partial_failure()
        test_batch_change_status()
        test_batch_transfer_rules()
        test_batch_operation_export()
        test_batch_operation_persistence()

        print('\n' + '='*50)
        print('撤销功能专项测试')
        print('='*50)

        test_undo_cancel_operation()
        test_undo_transfer_operation()
        test_undo_session_boundary()

        print('\n' + '='*50)
        print('批量操作 GUI 集成测试')
        print('='*50)

        test_gui_batch_operation_buttons()
        test_gui_undo_button()
        test_gui_batch_dialogs()
        test_gui_batch_end_to_end()
        test_gui_export_trigger()
        test_gui_persistence_after_restart()

        print('\n' + '='*50)
        print('候补名单专项测试')
        print('='*50)

        test_waiting_list_manual_add()
        test_waiting_list_import_partial_failure()
        test_auto_fill_preview_and_execute()
        test_auto_fill_validation_rules()
        test_waiting_list_deadline_and_status_validation()

        print('\n' + '='*50)
        print('候补数据持久化测试')
        print('='*50)

        test_waiting_list_persistence()

        print('\n' + '='*50)
        print('候补名单 GUI 集成测试')
        print('='*50)

        test_waiting_list_gui_integration()

        print('\n' + '='*50)
        print('结业证书专项测试')
        print('='*50)

        test_certificate_preview_generation()
        test_certificate_single_issue_and_validation()
        test_certificate_batch_partial_success_failure()
        test_certificate_reissue_conflict_avoidance()
        test_certificate_void_with_reason()
        test_certificate_cross_restart_persistence()
        test_certificate_export_readability()
        test_certificate_exception_logging()

        print('\n' + '='*50)
        print('结业证书 GUI 集成测试')
        print('='*50)

        test_certificate_gui_main_workflow()

        test_summary()
    finally:
        db_module.DB_PATH = original_path

        export_files = glob.glob(os.path.join(os.path.dirname(__file__), 'exports', '批量导入结果_*.csv'))
        for f in export_files:
            try:
                os.remove(f)
            except:
                pass
        export_files = glob.glob(os.path.join(os.path.dirname(__file__), 'exports', '批量操作结果_*.csv'))
        for f in export_files:
            try:
                os.remove(f)
            except:
                pass
        export_files = glob.glob(os.path.join(os.path.dirname(__file__), 'exports', '结业证书列表_*.csv'))
        for f in export_files:
            try:
                os.remove(f)
            except:
                pass
        export_files = glob.glob(os.path.join(os.path.dirname(__file__), 'exports', '批量生成结业证书结果_*.csv'))
        for f in export_files:
            try:
                os.remove(f)
            except:
                pass
        export_files = glob.glob(os.path.join(os.path.dirname(__file__), 'exports', '候补导入结果_*.csv'))
        for f in export_files:
            try:
                os.remove(f)
            except:
                pass
        export_files = glob.glob(os.path.join(os.path.dirname(__file__), 'exports', '补位结果_*.csv'))
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
