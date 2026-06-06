import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from datetime import datetime, timedelta
from db import init_database
from services import (
    CourseService, RegistrationService, AttendanceService,
    ExportService, ExceptionService, ValidationError
)

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
        test_summary()
    finally:
        db_module.DB_PATH = original_path

        if os.path.exists('test_training.db'):
            try:
                os.remove('test_training.db')
            except:
                pass
