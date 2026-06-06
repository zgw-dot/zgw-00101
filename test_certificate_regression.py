import sys, os, csv
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import sqlite3
import uuid
from datetime import datetime, timedelta
from db import init_database
from services import CourseService, RegistrationService, AttendanceService, CertificateService, ValidationError, ExceptionService, ExportService
from db.dao import StudentDAO, RegistrationDAO, CertificateDAO, CertificateBatchLogDAO, CertificateBatchItemDAO
import db.database as db_module

test_counter = [0]
created_test_dbs = []

def setup_test_db():
    test_counter[0] += 1
    unique_id = f"{test_counter[0]}_{uuid.uuid4().hex[:8]}"
    db_name = f'test_cert_reg_{unique_id}.db'
    db_path = os.path.join(os.path.dirname(__file__), db_name)
    created_test_dbs.append(db_path)
    db_module.DB_PATH = db_path
    init_database()
    return db_path

def cleanup_test_db():
    import time
    try:
        db_module.get_connection().close()
    except:
        pass
    time.sleep(0.2)
    for f in os.listdir('.'):
        if f.startswith('test_cert_reg_') and f.endswith('.db'):
            try:
                os.remove(f)
            except:
                pass
        if f.startswith('结业证书列表_') and f.endswith('.csv'):
            try:
                os.remove(f)
            except:
                pass
        if f.startswith('批量生成结业证书结果_') and f.endswith('.csv'):
            try:
                os.remove(f)
            except:
                pass
    export_dir = os.path.join(os.path.dirname(__file__), 'exports')
    if os.path.exists(export_dir):
        for f in os.listdir(export_dir):
            if '结业证书' in f and f.endswith('.csv'):
                try:
                    os.remove(os.path.join(export_dir, f))
                except:
                    pass

def create_test_course():
    course_data = {
        'title': '回归测试课程',
        'theme': '结业证书',
        'instructor': '测试讲师',
        'venue': '测试场地',
        'start_time': (datetime.now() + timedelta(days=10)).isoformat(),
        'end_time': (datetime.now() + timedelta(days=10, hours=2)).isoformat(),
        'capacity': 50,
        'registration_deadline': (datetime.now() + timedelta(days=5)).isoformat(),
        'status': 'published'
    }
    return CourseService.create_course(course_data)

def mark_course_ended(course_id):
    course = CourseService.get_course(course_id)
    course_data = dict(course)
    course_data['start_time'] = (datetime.now() - timedelta(days=10)).isoformat()
    course_data['end_time'] = (datetime.now() - timedelta(days=10, hours=-2)).isoformat()
    course_data['registration_deadline'] = (datetime.now() - timedelta(days=11)).isoformat()
    CourseService.update_course(course_id, course_data)

def _record_attendance(course_id, student_id, status, check_in_time=None):
    from db.dao import AttendanceDAO
    attendance = AttendanceDAO.get_or_create(course_id, student_id)
    if status == 'present':
        AttendanceDAO.check_in(course_id, student_id)
    else:
        AttendanceDAO.mark_absent(course_id, student_id)
    return True

def register_and_attend(course_id, name, emp_id, dept='技术部', present=True):
    student = {'name': name, 'employee_id': emp_id, 'department': dept}
    reg_id = RegistrationService.register_student(course_id, student)
    student_id = StudentDAO.get_by_employee_id(emp_id)['id']
    if present:
        _record_attendance(course_id, student_id, 'present', datetime.now().isoformat())
    else:
        _record_attendance(course_id, student_id, 'absent', None)
    return reg_id

def hard_assert(condition, message):
    if not condition:
        raise AssertionError(f'HARD ASSERT FAILED: {message}')

print('=' * 80)
print('结业证书链路强化回归测试')
print('=' * 80)

# === 测试 1: 证书编号靠 SQLite UNIQUE 与 DAO 重试避免重复 ===
print('\n=== 测试 1: SQLite UNIQUE 约束 + DAO 重试机制 ===')
setup_test_db()
try:
    course_id = create_test_course()
    register_and_attend(course_id, '并发测试学员', 'UNIQUE001')
    mark_course_ended(course_id)
    student_id = StudentDAO.get_by_employee_id('UNIQUE001')['id']

    conn = db_module.get_connection()
    cursor = conn.cursor()

    cursor.execute('SELECT sql FROM sqlite_master WHERE type="table" AND name="certificates"')
    table_sql = cursor.fetchone()['sql']
    hard_assert('UNIQUE' in table_sql and 'certificate_no' in table_sql,
                'certificates 表的 certificate_no 字段应有 UNIQUE 约束')
    print('  [OK] certificates 表 certificate_no 字段有 UNIQUE 约束')

    original_generate = CertificateDAO.generate_certificate_no
    call_count = [0]
    fixed_no = 'CERT-2024-TEST-000001'

    def mock_generate(cid):
        call_count[0] += 1
        if call_count[0] <= 3:
            return fixed_no
        return original_generate(cid)

    CertificateDAO.generate_certificate_no = mock_generate

    cursor.execute('''
    INSERT INTO certificates (
        certificate_no, course_id, student_id, status, issue_date, generated_at
    ) VALUES (?, ?, ?, 'issued', ?, ?)
    ''', (fixed_no, course_id, student_id, '2024-01-01', '2024-01-01T00:00:00'))
    conn.commit()
    conn.close()

    cert = CertificateDAO.create(course_id, student_id)

    hard_assert(call_count[0] >= 4, f'应至少重试 4 次（3 次冲突 + 1 次成功），实际 {call_count[0]} 次')
    hard_assert(cert['certificate_no'] != fixed_no, f'新证书编号不应与冲突编号相同')
    hard_assert(cert['status'] == 'issued', '新证书状态应为 issued')
    print(f'  [OK] 冲突重试: 尝试 {call_count[0]} 次后成功生成唯一编号')
    print(f'  [OK] 冲突编号: {fixed_no}, 最终编号: {cert["certificate_no"]}')

    CertificateDAO.generate_certificate_no = original_generate

    try:
        conn = db_module.get_connection()
        cursor = conn.cursor()
        cursor.execute('''
        INSERT INTO certificates (
            certificate_no, course_id, student_id, status, issue_date, generated_at
        ) VALUES (?, ?, ?, 'issued', ?, ?)
        ''', (cert['certificate_no'], course_id, student_id + 1, '2024-01-01', '2024-01-01T00:00:00'))
        conn.commit()
        conn.close()
        hard_assert(False, '直接插入重复编号应该抛出 sqlite3.IntegrityError')
    except sqlite3.IntegrityError as e:
        print(f'  [OK] SQLite UNIQUE 约束生效: {e}')

    print('  [PASS] SQLite UNIQUE + DAO 重试机制验证通过')
finally:
    cleanup_test_db()

# === 测试 2: 预览字段一致性（eligible/ineligible/兼容字段/计数字段）===
print('\n=== 测试 2: 预览返回字段一致性 ===')
setup_test_db()
try:
    course_id = create_test_course()
    emp_ids = ['FIELD001', 'FIELD002', 'FIELD003', 'FIELD004', 'FIELD005']
    names = ['合格1', '合格2', '缺勤1', '取消1', '已发证1']

    reg_ids = []
    student_ids_map = {}
    for i, (emp, name) in enumerate(zip(emp_ids, names)):
        if i < 2:
            reg_id = register_and_attend(course_id, name, emp, present=True)
        elif i == 2:
            reg_id = register_and_attend(course_id, name, emp, present=False)
        elif i == 3:
            reg_id = register_and_attend(course_id, name, emp, present=True)
            RegistrationDAO.update_status(reg_id, 'cancelled')
        else:
            reg_id = register_and_attend(course_id, name, emp, present=True)
        sid = StudentDAO.get_by_employee_id(emp)['id']
        student_ids_map[emp] = sid
        reg_ids.append(reg_id)

    mark_course_ended(course_id)

    sid_fifth = student_ids_map['FIELD005']
    CertificateService.issue_certificate(course_id, sid_fifth)

    preview = CertificateService.preview_generation(course_id)

    required_fields = [
        'eligible', 'ineligible', 'eligible_students', 'ineligible_students',
        'eligible_count', 'ineligible_count', 'total_registered',
        'course_id', 'course_title', 'course_ended'
    ]
    for field in required_fields:
        hard_assert(field in preview, f'缺少必要字段: {field}')
    print('  [OK] 所有必要字段存在')

    hard_assert(preview['eligible'] is preview['eligible_students'],
                'eligible 与 eligible_students 应指向同一列表对象')
    hard_assert(preview['ineligible'] is preview['ineligible_students'],
                'ineligible 与 ineligible_students 应指向同一列表对象')
    print('  [OK] 新旧字段名指向同一列表对象')

    hard_assert(len(preview['eligible']) == 2, f'eligible 应有 2 人，实际 {len(preview["eligible"])}')
    hard_assert(len(preview['ineligible']) == 3, f'ineligible 应有 3 人，实际 {len(preview["ineligible"])}')
    hard_assert(preview['eligible_count'] == 2, f'eligible_count 应为 2，实际 {preview["eligible_count"]}')
    hard_assert(preview['ineligible_count'] == 3, f'ineligible_count 应为 3，实际 {preview["ineligible_count"]}')
    hard_assert(preview['total_registered'] == 5, f'total_registered 应为 5，实际 {preview["total_registered"]}')
    hard_assert(preview['eligible_count'] == len(preview['eligible']), 'eligible_count 与列表长度不一致')
    hard_assert(preview['ineligible_count'] == len(preview['ineligible']), 'ineligible_count 与列表长度不一致')
    hard_assert(preview['total_registered'] == len(preview['eligible']) + len(preview['ineligible']),
                'total_registered 不等于 eligible + ineligible')
    print(f'  [OK] 计数一致: 总={preview["total_registered"]}, 合格={preview["eligible_count"]}, 不合格={preview["ineligible_count"]}')

    eligible_emps = {s['employee_id'] for s in preview['eligible']}
    hard_assert(eligible_emps == {'FIELD001', 'FIELD002'}, f'eligible 人员不正确: {eligible_emps}')

    ineligible_emps = {s['employee_id'] for s in preview['ineligible']}
    hard_assert(ineligible_emps == {'FIELD003', 'FIELD004', 'FIELD005'}, f'ineligible 人员不正确: {ineligible_emps}')

    for s in preview['eligible']:
        for f in ['student_id', 'name', 'employee_id', 'department', 'attendance_status', 'check_in_time']:
            hard_assert(f in s, f'eligible 学员缺少字段: {f}')
        hard_assert(s['attendance_status'] == 'present', 'eligible 学员出勤状态应为 present')

    for s in preview['ineligible']:
        for f in ['student_id', 'name', 'employee_id', 'department', 'registration_status', 'failure_reasons']:
            hard_assert(f in s, f'ineligible 学员缺少字段: {f}')
        hard_assert(isinstance(s['failure_reasons'], list), 'failure_reasons 应为列表')
        hard_assert(len(s['failure_reasons']) > 0, 'failure_reasons 不应为空')

    for s in preview['ineligible']:
        if s['employee_id'] == 'FIELD003':
            hard_assert(any('缺勤' in r or 'absent' in r for r in s['failure_reasons']),
                       '缺勤学员失败原因应包含缺勤')
        elif s['employee_id'] == 'FIELD004':
            hard_assert(any('取消' in r or 'cancelled' in r for r in s['failure_reasons']),
                       '取消报名学员失败原因应包含取消')
        elif s['employee_id'] == 'FIELD005':
            hard_assert(any('已有' in r or '证书' in r for r in s['failure_reasons']),
                       '已有证书学员失败原因应包含已有证书')
    print('  [OK] 失败原因正确对应各场景')

    print('  [PASS] 预览返回字段一致性验证通过')
finally:
    cleanup_test_db()

# === 测试 3: 批量生成统计和明细不串（已发证/缺勤/取消报名）===
print('\n=== 测试 3: 批量生成统计与明细严格一致 ===')
setup_test_db()
try:
    course_id = create_test_course()

    scenarios = [
        ('BATCH001', '合格-已发证', True, True, False),
        ('BATCH002', '合格-未发证1', True, False, False),
        ('BATCH003', '合格-未发证2', True, False, False),
        ('BATCH004', '合格-未发证3', True, False, False),
        ('BATCH005', '缺勤学员', False, False, False),
        ('BATCH006', '取消报名学员', True, False, True),
    ]

    student_ids = {}
    reg_ids_map = {}
    for emp, name, present, already_issued, cancel in scenarios:
        reg_id = register_and_attend(course_id, name, emp, present=present)
        sid = StudentDAO.get_by_employee_id(emp)['id']
        student_ids[emp] = sid
        reg_ids_map[emp] = reg_id
        if cancel:
            RegistrationDAO.update_status(reg_id, 'cancelled')

    mark_course_ended(course_id)

    for emp, name, present, already_issued, cancel in scenarios:
        if already_issued:
            CertificateService.issue_certificate(course_id, student_ids[emp])

    result = CertificateService.batch_generate_certificates(course_id, remark='强化回归测试')

    expected_total = 6
    expected_success = 3
    expected_failure = 3

    hard_assert(result['total_count'] == expected_total,
                f'total_count 应为 {expected_total}，实际 {result["total_count"]}')
    hard_assert(result['success_count'] == expected_success,
                f'success_count 应为 {expected_success}，实际 {result["success_count"]}')
    hard_assert(result['failure_count'] == expected_failure,
                f'failure_count 应为 {expected_failure}，实际 {result["failure_count"]}')
    hard_assert(result['success_count'] + result['failure_count'] == result['total_count'],
                'success_count + failure_count != total_count')
    print(f'  [OK] 顶层统计一致: 总={result["total_count"]}, 成={result["success_count"]}, 败={result["failure_count"]}')

    hard_assert(len(result['items']) == result['total_count'],
                f'items 长度 {len(result["items"])} != total_count {result["total_count"]}')

    success_items = [item for item in result['items'] if item['success']]
    failure_items = [item for item in result['items'] if not item['success']]

    hard_assert(len(success_items) == result['success_count'],
                f'成功明细数 {len(success_items)} != success_count {result["success_count"]}')
    hard_assert(len(failure_items) == result['failure_count'],
                f'失败明细数 {len(failure_items)} != failure_count {result["failure_count"]}')
    print(f'  [OK] 明细计数与顶层一致: 成功明细={len(success_items)}, 失败明细={len(failure_items)}')

    for item in success_items:
        hard_assert(item['certificate_id'] is not None, '成功项 certificate_id 不应为 None')
        hard_assert(item['certificate_no'] is not None, '成功项 certificate_no 不应为 None')
        hard_assert(len(item['certificate_no']) > 0, '成功项 certificate_no 不应为空')
        hard_assert(item['failure_reason'] is None, '成功项 failure_reason 应为 None')

    success_emps = {item['employee_id'] for item in success_items}
    hard_assert(success_emps == {'BATCH002', 'BATCH003', 'BATCH004'},
                f'成功学员不正确: {success_emps}')

    for item in failure_items:
        hard_assert(item['certificate_id'] is None, '失败项 certificate_id 应为 None')
        hard_assert(item['failure_reason'] is not None, '失败项 failure_reason 不应为 None')
        hard_assert(len(item['failure_reason']) > 0, '失败项 failure_reason 不应为空')

    failure_map = {item['employee_id']: item['failure_reason'] for item in failure_items}
    hard_assert('BATCH001' in failure_map, '已有证书的学员应在失败列表')
    hard_assert('BATCH005' in failure_map, '缺勤学员应在失败列表')
    hard_assert('BATCH006' in failure_map, '取消报名学员应在失败列表')

    hard_assert('已有' in failure_map['BATCH001'] or '证书' in failure_map['BATCH001'],
                f'已有证书失败原因不正确: {failure_map["BATCH001"]}')
    hard_assert('缺勤' in failure_map['BATCH005'] or '出勤' in failure_map['BATCH005'],
                f'缺勤失败原因不正确: {failure_map["BATCH005"]}')
    hard_assert('取消' in failure_map['BATCH006'],
                f'取消报名失败原因不正确: {failure_map["BATCH006"]}')
    print('  [OK] 各场景失败原因正确，不串不混')

    batch_log = CertificateBatchLogDAO.get_by_id(result['batch_log_id'])
    hard_assert(batch_log is not None, '批量日志应存在')
    hard_assert(batch_log['total_count'] == result['total_count'], '批量日志 total_count 不一致')
    hard_assert(batch_log['success_count'] == result['success_count'], '批量日志 success_count 不一致')
    hard_assert(batch_log['failure_count'] == result['failure_count'], '批量日志 failure_count 不一致')
    print('  [OK] 数据库批量日志与返回结果一致')

    db_items = CertificateBatchItemDAO.get_by_batch_log(result['batch_log_id'])
    hard_assert(len(db_items) == len(result['items']), '数据库明细数与返回不一致')
    db_success = sum(1 for i in db_items if i['success'])
    db_failure = sum(1 for i in db_items if not i['success'])
    hard_assert(db_success == result['success_count'], '数据库成功数与返回不一致')
    hard_assert(db_failure == result['failure_count'], '数据库失败数与返回不一致')
    print('  [OK] 数据库明细与返回结果完全一致')

    print('  [PASS] 批量生成统计与明细一致性验证通过')
finally:
    cleanup_test_db()

# === 测试 4: 补发会作废旧证且只保留一个有效证 ===
print('\n=== 测试 4: 补发严格作废旧证且单有效证 ===')
setup_test_db()
try:
    course_id = create_test_course()
    register_and_attend(course_id, '补发测试学员', 'REISSUE001')
    mark_course_ended(course_id)
    student_id = StudentDAO.get_by_employee_id('REISSUE001')['id']

    original = CertificateService.issue_certificate(course_id, student_id, '原始证书备注')
    original_no = original['certificate_no']
    original_id = original['id']

    hard_assert(original['status'] == 'issued', '原始证书状态应为 issued')
    hard_assert(original['voided_at'] is None, '原始证书作废时间应为 None')
    hard_assert(original['void_reason'] is None, '原始证书作废原因应为 None')

    all_before = CertificateDAO.get_by_course_and_student(course_id, student_id)
    hard_assert(len(all_before) == 1, '补发前应有 1 张证书')
    hard_assert(all_before[0]['status'] == 'issued', '补发前证书状态应为 issued')

    reissued = CertificateService.reissue_certificate(course_id, student_id, '补发证书备注')

    hard_assert(reissued['certificate_no'] != original_no, '补发后证书编号必须不同')
    hard_assert(reissued['status'] == 'issued', '新证书状态应为 issued')
    hard_assert(reissued['remark'] == '补发证书备注', '新证书备注应正确')

    original_updated = CertificateDAO.get_by_id(original_id)
    hard_assert(original_updated['status'] == 'voided', '原证书状态应为 voided')
    hard_assert(original_updated['void_reason'] == '补发新证书，原证书作废',
                '原证书作废原因不正确')
    hard_assert(original_updated['voided_at'] is not None, '原证书应有作废时间')
    hard_assert(len(original_updated['voided_at']) > 0, '原证书作废时间不应为空')
    print(f'  [OK] 原证书 {original_no} 已作废: status={original_updated["status"]}, reason={original_updated["void_reason"]}')

    all_after = CertificateDAO.get_by_course_and_student(course_id, student_id)
    hard_assert(len(all_after) == 2, '补发后应有 2 张证书记录')

    active_certs = [c for c in all_after if c['status'] == 'issued']
    voided_certs = [c for c in all_after if c['status'] == 'voided']
    hard_assert(len(active_certs) == 1, f'有效证书应为 1 张，实际 {len(active_certs)} 张')
    hard_assert(len(voided_certs) == 1, f'作废证书应为 1 张，实际 {len(voided_certs)} 张')
    hard_assert(active_certs[0]['id'] == reissued['id'], '有效证书应为新补发的')
    hard_assert(voided_certs[0]['id'] == original_id, '作废证书应为原始的')
    print(f'  [OK] 有效证书数: {len(active_certs)}, 作废证书数: {len(voided_certs)}')

    exists_active = CertificateDAO.exists_active(course_id, student_id)
    hard_assert(exists_active == True, 'exists_active 应返回 True')

    hard_assert(CertificateDAO.exists_active(course_id, student_id + 999) == False,
                '其他学员不应有有效证书')

    reissued2 = CertificateService.reissue_certificate(course_id, student_id, '第二次补发')
    all_final = CertificateDAO.get_by_course_and_student(course_id, student_id)
    hard_assert(len(all_final) == 3, '第二次补发后应有 3 张证书记录')
    active_final = [c for c in all_final if c['status'] == 'issued']
    hard_assert(len(active_final) == 1, '多次补发后仍应只有 1 张有效证书')
    hard_assert(active_final[0]['id'] == reissued2['id'], '有效证书应为最新的')
    print(f'  [OK] 多次补发后仍单有效证: 总数={len(all_final)}, 有效={len(active_final)}')

    print('  [PASS] 补发作废旧证且单有效证验证通过')
finally:
    cleanup_test_db()

# === 测试 5: 作废原因长度、重复作废、跨重启按编号查询 ===
print('\n=== 测试 5: 作废校验 + 跨重启查询 ===')
current_db_path = setup_test_db()
try:
    course_id = create_test_course()
    register_and_attend(course_id, '作废测试学员', 'VOID001')
    register_and_attend(course_id, '跨重启学员', 'PERSIST001')
    mark_course_ended(course_id)
    student_id = StudentDAO.get_by_employee_id('VOID001')['id']
    cert = CertificateService.issue_certificate(course_id, student_id)
    cert_id = cert['id']
    cert_no = cert['certificate_no']

    invalid_reasons = [
        ('', '空字符串'),
        ('   ', '纯空白字符串'),
        ('\t\n', '空白字符'),
        ('1234', '4字符'),
        ('abcd', '4字符英文'),
        ('测试1', '4字符中文'),
    ]
    for reason, desc in invalid_reasons:
        try:
            CertificateService.void_certificate(cert_id, reason)
            hard_assert(False, f'应拦截: {desc}, 原因="{reason}"')
        except ValidationError as e:
            print(f'  [OK] 拦截 {desc}: {e}')

    valid_reason = '测试作废原因，长度超过五个字符'
    voided = CertificateService.void_certificate(cert_id, valid_reason, operated_by='测试管理员')
    hard_assert(voided['status'] == 'voided', '作废后状态应为 voided')
    hard_assert(voided['void_reason'] == valid_reason, '作废原因保存不正确')
    hard_assert(voided['voided_at'] is not None, '作废时间不应为 None')
    hard_assert(voided['operated_by'] == '测试管理员', '操作人保存不正确')
    print(f'  [OK] 有效作废原因通过，状态更新正确')

    try:
        CertificateService.void_certificate(cert_id, '再次作废尝试')
        hard_assert(False, '重复作废应被拦截')
    except ValidationError as e:
        print(f'  [OK] 重复作废拦截: {e}')

    sid2 = StudentDAO.get_by_employee_id('PERSIST001')['id']
    cert2 = CertificateService.issue_certificate(course_id, sid2, '持久化测试备注')
    cert2_no = cert2['certificate_no']
    cert2_id = cert2['id']

    print(f'  证书1(已作废): {cert_no}')
    print(f'  证书2(有效): {cert2_no}')

    db_module.get_connection().close()

    import importlib
    importlib.reload(db_module)
    importlib.reload(__import__('db.dao'))
    importlib.reload(__import__('services.certificate_service'))

    from db.database import init_database as init2
    from db.dao import CertificateDAO as CD2
    from services.certificate_service import CertificateService as CS2

    db_module.DB_PATH = current_db_path
    init2()

    loaded_by_no1 = CD2.get_by_certificate_no(cert_no)
    hard_assert(loaded_by_no1 is not None, f'按编号查询作废证书失败: {cert_no}')
    hard_assert(loaded_by_no1['certificate_no'] == cert_no, '证书编号不匹配')
    hard_assert(loaded_by_no1['status'] == 'voided', '跨重启后作废状态丢失')
    hard_assert(loaded_by_no1['void_reason'] == valid_reason, '跨重启后作废原因丢失')
    hard_assert(loaded_by_no1['student_name'] == '作废测试学员', '学员姓名不匹配')
    hard_assert(loaded_by_no1['employee_id'] == 'VOID001', '学员工号不匹配')
    print(f'  [OK] 跨重启按编号查作废证书: {cert_no} -> {loaded_by_no1["status"]}')

    loaded_by_no2 = CS2.get_certificate_by_no(cert2_no)
    hard_assert(loaded_by_no2 is not None, f'按编号查询有效证书失败: {cert2_no}')
    hard_assert(loaded_by_no2['certificate_no'] == cert2_no, '证书编号不匹配')
    hard_assert(loaded_by_no2['status'] == 'issued', '跨重启后有效状态丢失')
    hard_assert(loaded_by_no2['remark'] == '持久化测试备注', '跨重启后备注丢失')
    hard_assert(loaded_by_no2['course_title'] == '回归测试课程', '课程名称不匹配')
    print(f'  [OK] 跨重启按编号查有效证书: {cert2_no} -> {loaded_by_no2["status"]}')

    loaded_by_id = CD2.get_by_id(cert2_id)
    hard_assert(loaded_by_id is not None, '按ID查询失败')
    hard_assert(loaded_by_id['certificate_no'] == cert2_no, '按ID查询结果不匹配')

    nonexistent = CD2.get_by_certificate_no('CERT-NOT-EXIST-000000')
    hard_assert(nonexistent is None, '不存在的编号应返回 None')
    print('  [OK] 不存在的编号返回 None')

    all_certs = CD2.get_all(course_id=course_id)
    hard_assert(len(all_certs) == 2, '跨重启后证书总数不正确')
    print(f'  [OK] 跨重启后课程证书总数: {len(all_certs)}')

    print('  [PASS] 作废校验 + 跨重启查询验证通过')
finally:
    cleanup_test_db()

# === 测试 6: 导出 CSV 内容严格验证 ===
print('\n=== 测试 6: 导出 CSV 内容严格验证 ===')
setup_test_db()
try:
    course_id = create_test_course()

    scenarios = [
        ('EXPORT001', '导出学员1', True, False, False, 'issued', None),
        ('EXPORT002', '导出学员2', True, False, False, 'issued', None),
        ('EXPORT003', '导出学员3', True, False, False, 'issued', None),
        ('EXPORT004', '导出学员4', True, True, False, 'voided', '测试作废原因1'),
        ('EXPORT005', '导出学员5', True, True, False, 'voided', '测试作废原因2'),
    ]

    student_ids_map = {}
    for emp, name, present, pre_void, cancel, expected_status, void_reason in scenarios:
        reg_id = register_and_attend(course_id, name, emp, present=present)
        sid = StudentDAO.get_by_employee_id(emp)['id']
        student_ids_map[emp] = sid

    mark_course_ended(course_id)

    created_certs = []
    for emp, name, present, pre_void, cancel, expected_status, void_reason in scenarios:
        sid = student_ids_map[emp]
        cert = CertificateService.issue_certificate(course_id, sid, f'{name}的备注')
        if pre_void:
            CertificateService.void_certificate(cert['id'], void_reason, operated_by='导出测试员')
        created_certs.append(cert)

    all_certs = CertificateDAO.get_all(course_id=course_id)
    hard_assert(len(all_certs) == 5, f'应有 5 张证书，实际 {len(all_certs)}')

    export_path = ExportService.export_certificates(all_certs)
    hard_assert(os.path.exists(export_path), f'导出文件不存在: {export_path}')
    print(f'  [OK] 导出文件生成: {os.path.basename(export_path)}')

    with open(export_path, 'r', encoding='utf-8-sig') as f:
        reader = csv.reader(f)
        rows = list(reader)

    hard_assert(len(rows) >= 8, 'CSV 行数不足，至少需要标题、元信息、空行、表头、5条数据')
    hard_assert(rows[0][0] == '结业证书列表', 'CSV 标题不正确')
    print(f'  [OK] CSV 标题行正确: {rows[0][0]}')

    data_start = None
    for i, row in enumerate(rows):
        if len(row) > 0 and row[0] == '编号':
            data_start = i
            break
    hard_assert(data_start is not None, '未找到表头行')

    header = rows[data_start]
    expected_headers = [
        '编号', '证书编号', '学员姓名', '学员工号', '部门',
        '课程名称', '课程主题', '状态',
        '发放日期', '生成时间', '作废时间',
        '作废原因', '备注', '操作人'
    ]
    hard_assert(len(header) == len(expected_headers),
                f'表头列数不匹配: 期望 {len(expected_headers)}, 实际 {len(header)}')
    for i, (exp, act) in enumerate(zip(expected_headers, header)):
        hard_assert(exp == act, f'表头第 {i} 列不匹配: 期望 "{exp}", 实际 "{act}"')
    print('  [OK] CSV 表头完全正确')

    data_rows = rows[data_start + 1:]
    data_rows = [r for r in data_rows if len(r) > 0 and r[0].strip()]
    hard_assert(len(data_rows) == 5, f'数据行数应为 5，实际 {len(data_rows)}')
    print(f'  [OK] CSV 数据行数正确: {len(data_rows)} 行')

    cert_nos_in_csv = {row[1] for row in data_rows}
    expected_nos = {c['certificate_no'] for c in all_certs}
    hard_assert(cert_nos_in_csv == expected_nos,
                f'CSV 证书编号集合不匹配: 缺失 {expected_nos - cert_nos_in_csv}, 多余 {cert_nos_in_csv - expected_nos}')

    status_map = {'issued': '已发放', 'voided': '已作废'}
    for row in data_rows:
        cert_no = row[1]
        cert = next((c for c in all_certs if c['certificate_no'] == cert_no), None)
        hard_assert(cert is not None, f'CSV 中存在未知证书: {cert_no}')

        hard_assert(row[2] == cert['student_name'], f'{cert_no}: 学员姓名不匹配')
        hard_assert(row[3] == cert['employee_id'], f'{cert_no}: 学员工号不匹配')
        hard_assert(row[4] == cert.get('department', ''), f'{cert_no}: 部门不匹配')
        hard_assert(row[5] == cert['course_title'], f'{cert_no}: 课程名称不匹配')
        hard_assert(row[6] == cert['course_theme'], f'{cert_no}: 课程主题不匹配')
        hard_assert(row[7] == status_map.get(cert['status'], cert['status']),
                    f'{cert_no}: 状态不匹配')
        hard_assert(row[8] == cert['issue_date'], f'{cert_no}: 发放日期不匹配')
        hard_assert(row[9] == cert['generated_at'], f'{cert_no}: 生成时间不匹配')

        if cert['status'] == 'voided':
            hard_assert(row[10] == cert['voided_at'], f'{cert_no}: 作废时间不匹配')
            hard_assert(row[11] == cert['void_reason'], f'{cert_no}: 作废原因不匹配')
        else:
            hard_assert(row[10] == '', f'{cert_no}: 有效证书作废时间应为空')
            hard_assert(row[11] == '', f'{cert_no}: 有效证书作废原因应为空')

        hard_assert(row[12] == cert.get('remark', ''), f'{cert_no}: 备注不匹配')
        hard_assert(row[13] == cert.get('operated_by', ''), f'{cert_no}: 操作人不匹配')

    print('  [OK] CSV 每行数据与数据库完全一致')

    batch_result = CertificateService.batch_generate_certificates(course_id)
    batch_export_path = ExportService.export_certificate_batch_result(batch_result)
    hard_assert(os.path.exists(batch_export_path), '批量导出文件不存在')

    with open(batch_export_path, 'r', encoding='utf-8-sig') as f:
        batch_content = f.read()
    hard_assert('批量生成结业证书结果' in batch_content, '批量导出标题缺失')
    hard_assert('处理总数' in batch_content, '处理总数缺失')
    hard_assert('成功数' in batch_content, '成功数缺失')
    hard_assert('失败数' in batch_content, '失败数缺失')
    hard_assert(str(batch_result['total_count']) in batch_content, '总数数值缺失')
    hard_assert(str(batch_result['success_count']) in batch_content, '成功数数值缺失')
    hard_assert(str(batch_result['failure_count']) in batch_content, '失败数数值缺失')
    hard_assert('失败原因' in batch_content, '失败原因列缺失')
    print('  [OK] 批量导出 CSV 内容完整')

    os.remove(export_path)
    os.remove(batch_export_path)

    print('  [PASS] 导出 CSV 内容严格验证通过')
finally:
    cleanup_test_db()

# === 测试 7: 临时数据库不污染现有数据 ===
print('\n=== 测试 7: 测试使用临时数据库，不污染现有数据 ===')
prod_db_path = os.path.join(os.path.dirname(__file__), 'training.db')
prod_db_existed = os.path.exists(prod_db_path)

current_test_db = setup_test_db()
try:
    hard_assert(os.path.exists(current_test_db), '测试数据库应存在')
    hard_assert(db_module.DB_PATH == current_test_db, 'DB_PATH 应指向测试数据库')

    course_id = create_test_course()
    register_and_attend(course_id, '隔离测试学员', 'ISOLATE001')
    mark_course_ended(course_id)
    sid = StudentDAO.get_by_employee_id('ISOLATE001')['id']
    cert = CertificateService.issue_certificate(course_id, sid)

    test_db_certs = CertificateDAO.get_all()
    hard_assert(len(test_db_certs) >= 1, '测试数据库应有证书数据')

    if prod_db_existed:
        original_db_path = db_module.DB_PATH
        db_module.DB_PATH = prod_db_path
        prod_certs = CertificateDAO.get_all()
        prod_emp_ids = {c['employee_id'] for c in prod_certs} if prod_certs else set()
        hard_assert('ISOLATE001' not in prod_emp_ids, '测试数据不应出现在生产数据库中')
        db_module.DB_PATH = original_db_path
        print('  [OK] 生产数据库未被污染')

    print('  [PASS] 测试数据库隔离验证通过')
finally:
    cleanup_test_db()
    hard_assert(not os.path.exists(current_test_db), '测试数据库应被清理')
    print('  [OK] 测试数据库已清理')

print('\n' + '=' * 80)
print('[OK] 所有强化回归测试通过')
print('=' * 80)
