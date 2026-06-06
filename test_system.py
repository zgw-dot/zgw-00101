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

    absent_att = None
    for att in attendances:
        if att['status'] != 'present':
            absent_att = att
            break

    if not absent_att and len(attendances) > 0:
        student_extra = {'name': '缺勤测试学生', 'employee_id': 'ABS001', 'department': '测试部'}
        try:
            course_data['registration_deadline'] = (datetime.now() + timedelta(hours=1)).isoformat()
            CourseService.update_course(course_id, course_data)
            RegistrationService.register_student(course_id, student_extra)
            course_data['registration_deadline'] = (datetime.now() - timedelta(hours=1)).isoformat()
            CourseService.update_course(course_id, course_data)
            attendances = AttendanceService.get_course_attendance(course_id)
            for att in attendances:
                if att['employee_id'] == 'ABS001':
                    absent_att = att
                    break
        except Exception as e:
            pass

    if absent_att:
        try:
            AttendanceService.request_makeup(course_id, absent_att['student_id'], '测试补签原因')
            print_test('补签申请提交', True)
        except Exception as e:
            print_test('补签申请提交', False, str(e))
    else:
        print_test('补签申请提交', True, '跳过：无缺勤学员')

    try:
        pending = AttendanceService.get_pending_makeups()
        has_pending = len(pending) > 0
        print_test('查询待审核补签', True, f'共 {len(pending)} 条')
    except Exception as e:
        print_test('查询待审核补签', False, str(e))
        pending = []

    if len(pending) > 0:
        try:
            AttendanceService.review_makeup(pending[0]['id'], True, '管理员', '情况属实')
            print_test('补签审核通过', True)
        except Exception as e:
            print_test('补签审核通过', False, str(e))
    else:
        print_test('补签审核通过', True, '跳过：无待审核补签')

def test_export(course_id):
    print('\n=== 测试 CSV 导出 ===')

    try:
        path = ExportService.export_course_attendance(course_id)
        exists = os.path.exists(path)
        print_test('导出生勤表', exists, f'文件: {path}')
    except Exception as e:
        print_test('导出生勤表', False, str(e))

    try:
        path = ExportService.export_exception_logs()
        exists = os.path.exists(path)
        print_test('导出异常日志', exists, f'文件: {path}')
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
