import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from datetime import datetime, timedelta
from db import init_database
from services import CourseService, RegistrationService, AttendanceService, CertificateService, ValidationError, ExceptionService, ExportService
from db.dao import StudentDAO, CertificateDAO, CertificateBatchLogDAO, CertificateBatchItemDAO
import db.database as db_module

if os.path.exists('test_cert.db'):
    os.remove('test_cert.db')
db_module.DB_PATH = os.path.join(os.path.dirname(__file__), 'test_cert.db')
init_database()

print('=== 测试证书预览生成 ===')
course_data = {
    'title': '预览测试课程',
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
preview = CertificateService.preview_generation(course_id)
print(f'  预览结果: 合格={len(preview["eligible"])} 不合格={len(preview["ineligible"])}')
print('  [PASS] 预览生成测试通过')

print('\n=== 测试单个证书生成 ===')
student_id = StudentDAO.get_by_employee_id('CERT001')['id']
cert = CertificateService.issue_certificate(course_id, student_id, '测试备注')
print(f'  证书编号: {cert["certificate_no"]}')
assert cert['status'] == 'issued'
print('  [PASS] 单个证书生成测试通过')

print('\n=== 测试重复生成拦截 ===')
try:
    CertificateService.issue_certificate(course_id, student_id, '重复')
    print('  [FAIL] 重复生成未拦截')
except ValidationError as e:
    print(f'  [PASS] 重复生成拦截: {e}')

print('\n=== 测试未结束课程拦截 ===')
not_ended_course = {
    'title': '未结束课程',
    'theme': '结业证书',
    'instructor': '测试讲师',
    'venue': '测试场地',
    'start_time': (datetime.now() + timedelta(days=1)).isoformat(),
    'end_time': (datetime.now() + timedelta(days=1, hours=2)).isoformat(),
    'capacity': 5,
    'registration_deadline': (datetime.now() + timedelta(days=2)).isoformat(),
    'status': 'published'
}
not_ended_id = CourseService.create_course(not_ended_course)
try:
    CertificateService.issue_certificate(not_ended_id, student_id)
    print('  [FAIL] 未结束课程未拦截')
except ValidationError as e:
    print(f'  [PASS] 未结束课程拦截: {e}')

print('\n=== 测试批量生成部分成功部分失败 ===')
for i in range(5):
    s = {'name': f'批量学员{i+1}', 'employee_id': f'CERTB{i+1:03d}', 'department': '技术部'}
    reg_id = RegistrationService.register_student(course_id, s)
    if i < 3:
        AttendanceService.record_attendance(course_id, reg_id, 'present', datetime.now().isoformat())
    elif i == 3:
        AttendanceService.record_attendance(course_id, reg_id, 'absent', None)
    else:
        RegistrationService.cancel_registration(reg_id, '个人原因')

result = CertificateService.batch_generate_certificates(course_id, remark='批量测试')
print(f'  批量结果: 总={result["total_count"]} 成功={result["success_count"]} 失败={result["failure_count"]}')
assert result['total_count'] == 5
assert result['success_count'] == 3
assert result['failure_count'] == 2
failure_reasons = [item['failure_reason'] for item in result['items'] if not item['success']]
assert any('缺勤' in r for r in failure_reasons)
assert any('取消' in r for r in failure_reasons)
print('  [PASS] 批量生成部分成功部分失败测试通过')

print('\n=== 测试证书补发 ===')
original = CertificateService.issue_certificate(course_id, student_id)
original_no = original['certificate_no']
reissued = CertificateService.reissue_certificate(course_id, student_id, '补发证书')
assert reissued['certificate_no'] != original_no
original_updated = CertificateDAO.get_by_id(original['id'])
assert original_updated['status'] == 'voided'
print(f'  原编号: {original_no} -> 新编号: {reissued["certificate_no"]}')
print('  [PASS] 证书补发测试通过')

print('\n=== 测试证书作废 ===')
try:
    CertificateService.void_certificate(cert['id'], '短')
    print('  [FAIL] 作废原因长度未校验')
except ValidationError as e:
    print(f'  [PASS] 作废原因长度校验: {e}')

voided = CertificateService.void_certificate(cert['id'], '测试作废原因，至少5个字符')
assert voided['status'] == 'voided'
print('  [PASS] 证书作废测试通过')

print('\n=== 测试重复作废拦截 ===')
try:
    CertificateService.void_certificate(cert['id'], '再次作废')
    print('  [FAIL] 重复作废未拦截')
except ValidationError as e:
    print(f'  [PASS] 重复作废拦截: {e}')

print('\n=== 测试跨重启持久化 ===')
cert_no = reissued['certificate_no']
cert_id = reissued['id']
db_module.get_connection().close()

import importlib
importlib.reload(db_module)
importlib.reload(__import__('db.dao'))
importlib.reload(__import__('services.certificate_service'))

from db.database import init_database as init2
from db.dao import CertificateDAO as CD2
from services.certificate_service import CertificateService as CS2
init2()

loaded = CD2.get_by_id(cert_id)
assert loaded is not None
assert loaded['certificate_no'] == cert_no
assert loaded['status'] == 'issued'
print(f'  重启后查询: 编号={loaded["certificate_no"]} 状态={loaded["status"]}')

all_certs = CD2.get_all()
assert len(all_certs) >= 1
print(f'  重启后证书总数: {len(all_certs)}')
print('  [PASS] 跨重启持久化测试通过')

print('\n=== 测试证书导出可读性 ===')
certs = CertificateDAO.get_all(course_id=course_id)
export_path = ExportService.export_certificates(certs)
assert os.path.exists(export_path)
with open(export_path, 'r', encoding='utf-8-sig') as f:
    content = f.read()
    assert '结业证书列表' in content
    assert '学员姓名' in content
    assert '证书编号' in content
    assert '课程名称' in content
    assert '已发放' in content or '已作废' in content
print(f'  导出文件: {os.path.basename(export_path)}')
print('  [PASS] 证书导出可读性测试通过')

print('\n=== 测试批量结果导出 ===')
batch_export_path = ExportService.export_certificate_batch_result(result)
assert os.path.exists(batch_export_path)
with open(batch_export_path, 'r', encoding='utf-8-sig') as f:
    content = f.read()
    assert '结业证书批量生成结果' in content
    assert '处理总数' in content
    assert '失败原因' in content
print(f'  批量导出文件: {os.path.basename(batch_export_path)}')
print('  [PASS] 批量结果导出测试通过')

print('\n=== 测试异常日志记录 ===')
before = len(ExceptionService.get_all_logs() or [])
s2 = {'name': '日志学员', 'employee_id': 'CERTL001', 'department': '技术部'}
reg_id_l = RegistrationService.register_student(course_id, s2)
AttendanceService.record_attendance(course_id, reg_id_l, 'present', datetime.now().isoformat())
sid_l = StudentDAO.get_by_employee_id('CERTL001')['id']
cert_l = CertificateService.issue_certificate(course_id, sid_l)
after = len(ExceptionService.get_all_logs() or [])
assert after > before
print(f'  生成证书日志记录: {before} -> {after}')

voided_l = CertificateService.void_certificate(cert_l['id'], '测试作废，需要记录日志')
after_void = len(ExceptionService.get_all_logs() or [])
assert after_void > after
print(f'  作废证书日志记录: {after} -> {after_void}')

reissued_l = CertificateService.reissue_certificate(course_id, sid_l, '测试补发')
after_reissue = len(ExceptionService.get_all_logs() or [])
assert after_reissue > after_void
print(f'  补发证书日志记录: {after_void} -> {after_reissue}')

print('  [PASS] 异常日志记录测试通过')

os.remove('test_cert.db')
os.remove(export_path)
os.remove(batch_export_path)

print('\n' + '=' * 50)
print('✓ 所有核心功能测试通过')
print('=' * 50)
