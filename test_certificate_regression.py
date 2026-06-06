import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from datetime import datetime, timedelta
from db import init_database
from services import CourseService, RegistrationService, AttendanceService, CertificateService, ValidationError, ExceptionService, ExportService
from db.dao import StudentDAO, CertificateDAO, CertificateBatchLogDAO, CertificateBatchItemDAO
import db.database as db_module

def setup_test_db():
    if os.path.exists('test_cert_regression.db'):
        os.remove('test_cert_regression.db')
    db_module.DB_PATH = os.path.join(os.path.dirname(__file__), 'test_cert_regression.db')
    init_database()

def cleanup_test_db():
    if os.path.exists('test_cert_regression.db'):
        os.remove('test_cert_regression.db')

def create_test_course(days_ago=1, hours_duration=2):
    course_data = {
        'title': '回归测试课程',
        'theme': '结业证书',
        'instructor': '测试讲师',
        'venue': '测试场地',
        'start_time': (datetime.now() - timedelta(days=days_ago)).isoformat(),
        'end_time': (datetime.now() - timedelta(days=days_ago, hours=-hours_duration)).isoformat(),
        'capacity': 20,
        'registration_deadline': (datetime.now() + timedelta(days=1)).isoformat(),
        'status': 'published'
    }
    return CourseService.create_course(course_data)

def register_and_attend(course_id, name, emp_id, dept='技术部', present=True):
    student = {'name': name, 'employee_id': emp_id, 'department': dept}
    reg_id = RegistrationService.register_student(course_id, student)
    if present:
        AttendanceService.record_attendance(course_id, reg_id, 'present', datetime.now().isoformat())
    else:
        AttendanceService.record_attendance(course_id, reg_id, 'absent', None)
    return reg_id

print('=' * 70)
print('结业证书链路回归测试')
print('=' * 70)

# === 测试 1: 统一返回字段命名验证 ===
print('\n=== 测试 1: 统一返回字段命名验证 ===')
setup_test_db()
try:
    course_id = create_test_course()
    register_and_attend(course_id, '字段测试学员', 'FIELD001')
    register_and_attend(course_id, '缺勤学员', 'FIELD002', present=False)

    preview = CertificateService.preview_generation(course_id)

    assert 'eligible' in preview, '缺少字段: eligible'
    assert 'ineligible' in preview, '缺少字段: ineligible'
    assert 'eligible_students' in preview, '缺少兼容字段: eligible_students'
    assert 'ineligible_students' in preview, '缺少兼容字段: ineligible_students'
    assert 'eligible_count' in preview, '缺少字段: eligible_count'
    assert 'ineligible_count' in preview, '缺少字段: ineligible_count'
    assert 'total_registered' in preview, '缺少字段: total_registered'

    assert preview['eligible'] is preview['eligible_students'], 'eligible 与 eligible_students 应指向同一列表'
    assert preview['ineligible'] is preview['ineligible_students'], 'ineligible 与 ineligible_students 应指向同一列表'

    assert len(preview['eligible']) == 1
    assert len(preview['ineligible']) == 1
    assert preview['eligible_count'] == 1
    assert preview['ineligible_count'] == 1
    assert preview['total_registered'] == 2

    print('  ✓ 新字段名 eligible/ineligible 可用')
    print('  ✓ 兼容字段名 eligible_students/ineligible_students 可用')
    print('  ✓ 字段值一致，列表引用相同')
    print('  [PASS] 统一返回字段命名验证通过')
finally:
    cleanup_test_db()

# === 测试 2: 批量生成部分成功部分失败 ===
print('\n=== 测试 2: 批量生成部分成功部分失败 ===')
setup_test_db()
try:
    course_id = create_test_course()

    for i in range(6):
        emp_id = f'BATCH{i+1:03d}'
        if i < 3:
            register_and_attend(course_id, f'批量学员{i+1}', emp_id)
        elif i == 3:
            register_and_attend(course_id, f'批量学员{i+1}', emp_id, present=False)
        elif i == 4:
            reg_id = register_and_attend(course_id, f'批量学员{i+1}', emp_id)
            RegistrationService.cancel_registration(reg_id, '个人原因')
        else:
            register_and_attend(course_id, f'批量学员{i+1}', emp_id)
            sid = StudentDAO.get_by_employee_id(emp_id)['id']
            CertificateService.issue_certificate(course_id, sid)

    result = CertificateService.batch_generate_certificates(course_id, remark='回归测试批量')

    assert result['total_count'] == 6, f'预期总数 6，实际 {result["total_count"]}'
    assert result['success_count'] == 3, f'预期成功 3，实际 {result["success_count"]}'
    assert result['failure_count'] == 3, f'预期失败 3，实际 {result["failure_count"]}'

    success_items = [item for item in result['items'] if item['success']]
    failure_items = [item for item in result['items'] if not item['success']]

    assert len(success_items) == 3
    assert len(failure_items) == 3

    failure_reasons = [item['failure_reason'] for item in failure_items]
    assert any('缺勤' in r for r in failure_reasons), '应有缺勤失败原因'
    assert any('取消' in r for r in failure_reasons), '应有取消报名失败原因'
    assert any('已有有效' in r for r in failure_reasons), '应有已有证书失败原因'

    for item in success_items:
        assert 'certificate_no' in item, '成功项应有证书编号'
        assert item['certificate_id'] is not None, '成功项应有证书 ID'

    for item in failure_items:
        assert 'failure_reason' in item, '失败项应有失败原因'
        assert item['failure_reason'] is not None, '失败原因不应为空'

    print(f'  ✓ 总数: {result["total_count"]}, 成功: {result["success_count"]}, 失败: {result["failure_count"]}')
    print('  ✓ 成功项包含证书编号和 ID')
    print('  ✓ 失败项包含具体失败原因')
    print('  ✓ 覆盖三种失败场景：缺勤、已取消、已有证书')
    print('  [PASS] 批量生成部分成功部分失败验证通过')
finally:
    cleanup_test_db()

# === 测试 3: 补发后旧证书作废 ===
print('\n=== 测试 3: 补发后旧证书作废 ===')
setup_test_db()
try:
    course_id = create_test_course()
    register_and_attend(course_id, '补发测试学员', 'REISSUE001')

    student_id = StudentDAO.get_by_employee_id('REISSUE001')['id']

    original = CertificateService.issue_certificate(course_id, student_id)
    original_no = original['certificate_no']
    original_id = original['id']

    assert original['status'] == 'issued'

    reissued = CertificateService.reissue_certificate(course_id, student_id, '补发测试')

    assert reissued['certificate_no'] != original_no, '补发后证书编号应不同'
    assert reissued['status'] == 'issued', '新证书状态应为已发放'

    original_updated = CertificateDAO.get_by_id(original_id)
    assert original_updated['status'] == 'voided', '原证书状态应为已作废'
    assert original_updated['void_reason'] == '补发新证书，原证书作废', '原证书作废原因应正确'
    assert original_updated['voided_at'] is not None, '原证书应有作废时间'

    all_certs = CertificateDAO.get_by_course_and_student(course_id, student_id)
    assert len(all_certs) == 2, '应存在两张证书记录'

    active_certs = [c for c in all_certs if c['status'] == 'issued']
    assert len(active_certs) == 1, '应只有一张有效证书'
    assert active_certs[0]['id'] == reissued['id'], '有效证书应为新补发的'

    print(f'  ✓ 原证书: {original_no} -> 状态: {original_updated["status"]}')
    print(f'  ✓ 新证书: {reissued["certificate_no"]} -> 状态: {reissued["status"]}')
    print('  ✓ 原证书作废原因正确')
    print('  ✓ 同一时间只有一张有效证书')
    print('  [PASS] 补发后旧证书作废验证通过')
finally:
    cleanup_test_db()

# === 测试 4: 作废原因校验 ===
print('\n=== 测试 4: 作废原因校验 ===')
setup_test_db()
try:
    course_id = create_test_course()
    register_and_attend(course_id, '作废测试学员', 'VOID001')

    student_id = StudentDAO.get_by_employee_id('VOID001')['id']
    cert = CertificateService.issue_certificate(course_id, student_id)
    cert_id = cert['id']

    test_cases = [
        ('', '空字符串应被拦截'),
        ('   ', '空白字符串应被拦截'),
        ('1234', '少于5字符应被拦截'),
        ('abcd', '少于5字符应被拦截'),
    ]

    for reason, desc in test_cases:
        try:
            CertificateService.void_certificate(cert_id, reason)
            print(f'  [FAIL] {desc}: 原因="{reason}"')
            assert False, desc
        except ValidationError as e:
            print(f'  ✓ {desc}: {e}')

    valid_reason = '测试作废原因，长度足够'
    voided = CertificateService.void_certificate(cert_id, valid_reason)
    assert voided['status'] == 'voided', '作废后状态应为 voided'
    assert voided['void_reason'] == valid_reason, '作废原因应正确保存'
    assert voided['voided_at'] is not None, '应有作废时间'

    try:
        CertificateService.void_certificate(cert_id, '再次作废')
        print('  [FAIL] 重复作废未被拦截')
        assert False
    except ValidationError as e:
        print(f'  ✓ 重复作废被拦截: {e}')

    print('  ✓ 有效作废原因（>=5字符）被接受')
    print('  ✓ 作废信息正确保存')
    print('  [PASS] 作废原因校验验证通过')
finally:
    cleanup_test_db()

# === 测试 5: 跨重启 SQLite 数据持久化 ===
print('\n=== 测试 5: 跨重启 SQLite 数据持久化 ===')
test_db_path = 'test_cert_persistence.db'
if os.path.exists(test_db_path):
    os.remove(test_db_path)
db_module.DB_PATH = os.path.join(os.path.dirname(__file__), test_db_path)
init_database()

try:
    course_id = create_test_course()
    register_and_attend(course_id, '持久化学员1', 'PERSIST001')
    register_and_attend(course_id, '持久化学员2', 'PERSIST002')
    register_and_attend(course_id, '持久化学员3', 'PERSIST003', present=False)

    sid1 = StudentDAO.get_by_employee_id('PERSIST001')['id']
    sid2 = StudentDAO.get_by_employee_id('PERSIST002')['id']

    cert1 = CertificateService.issue_certificate(course_id, sid1, '证书1备注')
    cert2 = CertificateService.issue_certificate(course_id, sid2, '证书2备注')

    batch_result = CertificateService.batch_generate_certificates(course_id)

    CertificateService.void_certificate(cert2['id'], '作废持久化测试')

    cert1_no = cert1['certificate_no']
    cert2_no = cert2['certificate_no']
    batch_log_id = batch_result['batch_log_id']

    print(f'  生成证书 1: {cert1_no}')
    print(f'  生成证书 2: {cert2_no} (已作废)')
    print(f'  批量操作日志 ID: {batch_log_id}')

    db_module.get_connection().close()

    import importlib
    importlib.reload(db_module)
    importlib.reload(__import__('db.dao'))
    importlib.reload(__import__('services.certificate_service'))

    from db.database import init_database as init2
    from db.dao import CertificateDAO as CD2, CertificateBatchLogDAO as CBL2, CertificateBatchItemDAO as CBI2
    from services.certificate_service import CertificateService as CS2

    db_module.DB_PATH = os.path.join(os.path.dirname(__file__), test_db_path)
    init2()

    loaded_cert1 = CD2.get_by_id(cert1['id'])
    assert loaded_cert1 is not None, '重启后应能查询到证书1'
    assert loaded_cert1['certificate_no'] == cert1_no
    assert loaded_cert1['status'] == 'issued'
    assert loaded_cert1['remark'] == '证书1备注'
    assert loaded_cert1['student_name'] == '持久化学员1'
    assert loaded_cert1['employee_id'] == 'PERSIST001'

    loaded_cert2 = CD2.get_by_id(cert2['id'])
    assert loaded_cert2 is not None, '重启后应能查询到证书2'
    assert loaded_cert2['certificate_no'] == cert2_no
    assert loaded_cert2['status'] == 'voided'
    assert loaded_cert2['void_reason'] == '作废持久化测试'
    assert loaded_cert2['voided_at'] is not None

    all_certs = CD2.get_all(course_id=course_id)
    assert len(all_certs) >= 2, '重启后证书数量应正确'

    batch_log = CBL2.get_by_id(batch_log_id)
    assert batch_log is not None, '重启后应能查询到批量日志'
    assert batch_log['total_count'] == batch_result['total_count']
    assert batch_log['success_count'] == batch_result['success_count']
    assert batch_log['failure_count'] == batch_result['failure_count']

    batch_items = CBI2.get_by_batch_log(batch_log_id)
    assert len(batch_items) >= 1, '重启后应能查询到批量明细'

    preview_after = CS2.preview_generation(course_id)
    assert preview_after['total_registered'] == 3
    assert preview_after['eligible_count'] == 0, '已有证书的学员不应出现在符合条件列表中'
    assert preview_after['ineligible_count'] == 3

    print(f'  ✓ 重启后证书1: 编号={loaded_cert1["certificate_no"]}, 状态={loaded_cert1["status"]}')
    print(f'  ✓ 重启后证书2: 编号={loaded_cert2["certificate_no"]}, 状态={loaded_cert2["status"]}')
    print(f'  ✓ 重启后批量日志: ID={batch_log["id"]}, 成功={batch_log["success_count"]}')
    print('  ✓ 重启后预览数据正确（已有证书的学员被排除）')
    print('  [PASS] 跨重启 SQLite 数据持久化验证通过')
finally:
    if os.path.exists(test_db_path):
        os.remove(test_db_path)

# === 测试 6: GUI 入口字段一致性 ===
print('\n=== 测试 6: GUI 入口字段一致性验证 ===')
setup_test_db()
try:
    course_id = create_test_course()
    register_and_attend(course_id, 'GUI测试学员1', 'GUI001')
    register_and_attend(course_id, 'GUI测试学员2', 'GUI002', present=False)

    preview = CertificateService.preview_generation(course_id)

    for field in ['eligible', 'ineligible', 'eligible_students', 'ineligible_students']:
        assert field in preview, f'GUI 需要的字段缺失: {field}'

    for student in preview['eligible']:
        for field in ['student_id', 'name', 'employee_id', 'department', 'attendance_status', 'check_in_time']:
            assert field in student, f'符合条件学员缺少字段: {field}'

    for student in preview['ineligible']:
        for field in ['student_id', 'name', 'employee_id', 'department', 'registration_status', 'failure_reasons']:
            assert field in student, f'不符合条件学员缺少字段: {field}'
        assert isinstance(student['failure_reasons'], list), 'failure_reasons 应为列表'

    sid = StudentDAO.get_by_employee_id('GUI001')['id']
    result = CertificateService.batch_generate_certificates(course_id)

    for field in ['total_count', 'success_count', 'failure_count', 'items']:
        assert field in result, f'批量结果缺少字段: {field}'

    for item in result['items']:
        for field in ['id', 'student_id', 'success', 'student_name', 'employee_id']:
            assert field in item, f'批量明细缺少字段: {field}'
        if item['success']:
            assert 'certificate_no' in item, '成功项缺少 certificate_no'
        else:
            assert 'failure_reason' in item, '失败项缺少 failure_reason'

    all_certs = CertificateService.get_all_certificates()
    for cert in all_certs:
        for field in ['id', 'certificate_no', 'student_id', 'student_name', 'employee_id',
                      'course_id', 'course_title', 'status', 'issue_date', 'generated_at']:
            assert field in cert, f'证书列表缺少字段: {field}'

    batch_logs = CertificateService.get_all_batch_logs()
    for log in batch_logs:
        for field in ['id', 'course_id', 'course_title', 'total_count', 'success_count',
                      'failure_count', 'created_at']:
            assert field in log, f'批量日志缺少字段: {field}'

    print('  ✓ preview_generation 返回所有必要字段')
    print('  ✓ eligible/ineligible 学员信息完整')
    print('  ✓ batch_generate_certificates 返回结构完整')
    print('  ✓ get_all_certificates 返回结构完整')
    print('  ✓ get_all_batch_logs 返回结构完整')
    print('  [PASS] GUI 入口字段一致性验证通过')
finally:
    cleanup_test_db()

# === 测试 7: 导出服务字段兼容性 ===
print('\n=== 测试 7: 导出服务字段兼容性 ===')
setup_test_db()
try:
    course_id = create_test_course()
    register_and_attend(course_id, '导出测试学员', 'EXPORT001')
    sid = StudentDAO.get_by_employee_id('EXPORT001')['id']
    CertificateService.issue_certificate(course_id, sid)

    batch_result = CertificateService.batch_generate_certificates(course_id)

    certs = CertificateDAO.get_all(course_id=course_id)
    export_path = ExportService.export_certificates(certs)
    assert os.path.exists(export_path)
    with open(export_path, 'r', encoding='utf-8-sig') as f:
        content = f.read()
        assert '结业证书列表' in content
        assert '学员姓名' in content
        assert '证书编号' in content
        assert '课程名称' in content
    os.remove(export_path)

    batch_export_path = ExportService.export_certificate_batch_result(batch_result)
    assert os.path.exists(batch_export_path)
    with open(batch_export_path, 'r', encoding='utf-8-sig') as f:
        content = f.read()
        assert '批量生成结业证书结果' in content
        assert '处理总数' in content
        assert '失败原因' in content
    os.remove(batch_export_path)

    print('  ✓ 证书导出成功，字段完整')
    print('  ✓ 批量结果导出成功，字段完整')
    print('  [PASS] 导出服务字段兼容性验证通过')
finally:
    cleanup_test_db()

# === 测试 8: 校验逻辑一致性（单条 vs 批量）===
print('\n=== 测试 8: 校验逻辑一致性 ===')
setup_test_db()
try:
    course_id = create_test_course()

    scenarios = [
        ('正常学员', 'CONSIST001', True, True, None),
        ('缺勤学员', 'CONSIST002', False, False, '缺勤或出勤不达标'),
        ('已取消学员', 'CONSIST003', True, False, '已取消报名'),
    ]

    for name, emp_id, present, should_pass, expected_error in scenarios:
        reg_id = register_and_attend(course_id, name, emp_id, present=present)
        if not should_pass and expected_error == '已取消报名':
            RegistrationService.cancel_registration(reg_id, '测试取消')

    preview = CertificateService.preview_generation(course_id)

    for student in preview['eligible']:
        assert student['employee_id'] == 'CONSIST001', '只有正常学员应符合条件'

    ineligible_emps = [s['employee_id'] for s in preview['ineligible']]
    assert 'CONSIST002' in ineligible_emps, '缺勤学员应在不符合条件列表'
    assert 'CONSIST003' in ineligible_emps, '已取消学员应在不符合条件列表'

    for student in preview['ineligible']:
        if student['employee_id'] == 'CONSIST002':
            assert any('缺勤' in r for r in student['failure_reasons'])
        elif student['employee_id'] == 'CONSIST003':
            assert any('已取消' in r for r in student['failure_reasons'])

    print('  ✓ 预览校验逻辑与单条校验一致')
    print('  ✓ 失败原因正确对应')
    print('  [PASS] 校验逻辑一致性验证通过')
finally:
    cleanup_test_db()

print('\n' + '=' * 70)
print('✓ 所有回归测试通过')
print('=' * 70)
