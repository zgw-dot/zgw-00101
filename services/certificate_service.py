from datetime import datetime
from db.dao import (
    CertificateDAO, CertificateBatchLogDAO, CertificateBatchItemDAO,
    CourseDAO, RegistrationDAO, AttendanceDAO, StudentDAO, ExceptionLogDAO
)
from .course_service import ValidationError


class CertificateService:

    @staticmethod
    def _validate_course_ended(course):
        course_end = datetime.fromisoformat(course['end_time'])
        now = datetime.now()
        if now < course_end:
            raise ValidationError('课程尚未结束，不能生成结业证书')

    @staticmethod
    def _build_student_info(status_row):
        return {
            'student_id': status_row['student_id'],
            'name': status_row['name'],
            'employee_id': status_row['employee_id'],
            'department': status_row.get('department', ''),
            'registration_id': status_row['registration_id'],
            'registration_status': status_row['registration_status']
        }

    @staticmethod
    def _check_single_eligibility(course_id, status_row, course_ended=True):
        student_info = CertificateService._build_student_info(status_row)
        failure_reasons = []

        if not course_ended:
            failure_reasons.append('课程尚未结束')

        if status_row['registration_status'] == 'cancelled':
            failure_reasons.append('已取消报名')

        att_status = status_row.get('attendance_status')
        if not att_status or att_status != 'present':
            failure_reasons.append('缺勤或出勤不达标')
        else:
            student_info['attendance_status'] = att_status
            student_info['check_in_time'] = status_row.get('check_in_time', '')

        if status_row.get('certificate_id') is not None:
            failure_reasons.append('已有有效证书')

        eligible = len(failure_reasons) == 0
        if not eligible:
            student_info['failure_reasons'] = failure_reasons

        return {
            'student': student_info,
            'eligible': eligible,
            'failure_reasons': failure_reasons
        }

    @staticmethod
    def _build_preview_result(course_id, course, course_ended, ineligible_reason=None):
        status_rows = CertificateDAO.get_course_certificate_status(course_id)

        eligible_list = []
        ineligible_list = []

        for row in status_rows:
            check_result = CertificateService._check_single_eligibility(
                course_id, row, course_ended
            )
            if check_result['eligible']:
                eligible_list.append(check_result['student'])
            else:
                ineligible_list.append(check_result['student'])

        result = {
            'course_id': course_id,
            'course_title': course['title'],
            'course_ended': course_ended,
            'total_registered': len(status_rows),
            'eligible_count': len(eligible_list),
            'ineligible_count': len(ineligible_list),
            'eligible': eligible_list,
            'ineligible': ineligible_list,
            'eligible_students': eligible_list,
            'ineligible_students': ineligible_list
        }

        if ineligible_reason:
            result['ineligible_reason'] = ineligible_reason

        return result

    @staticmethod
    def get_eligible_students(course_id):
        course = CourseDAO.get_by_id(course_id)
        if not course:
            raise ValidationError('课程不存在')

        try:
            CertificateService._validate_course_ended(course)
        except ValidationError:
            return []

        status_rows = CertificateDAO.get_course_certificate_status(course_id)
        eligible = []
        for row in status_rows:
            if row['registration_status'] != 'cancelled':
                check_result = CertificateService._check_single_eligibility(
                    course_id, row, course_ended=True
                )
                if check_result['eligible']:
                    eligible.append(check_result['student'])

        return eligible

    @staticmethod
    def preview_generation(course_id):
        course = CourseDAO.get_by_id(course_id)
        if not course:
            raise ValidationError('课程不存在')

        course_ended = True
        ineligible_reason = None

        try:
            CertificateService._validate_course_ended(course)
        except ValidationError as e:
            course_ended = False
            ineligible_reason = str(e)

        return CertificateService._build_preview_result(
            course_id, course, course_ended, ineligible_reason
        )

    @staticmethod
    def _validate_issue(course_id, student_id):
        course = CourseDAO.get_by_id(course_id)
        if not course:
            raise ValidationError('课程不存在')

        student = StudentDAO.get_by_id(student_id)
        if not student:
            raise ValidationError('学员不存在')

        CertificateService._validate_course_ended(course)

        registrations = RegistrationDAO.get_by_course_all_status(course_id)
        reg = next((r for r in registrations if r['student_id'] == student_id), None)
        if not reg:
            raise ValidationError('该学员未报名此课程')
        if reg['status'] == 'cancelled':
            raise ValidationError('该学员已取消报名')

        attendances = AttendanceDAO.get_by_course(course_id)
        att = next((a for a in attendances if a['student_id'] == student_id), None)
        if not att or att['status'] != 'present':
            raise ValidationError('该学员未出勤或出勤不达标')

        if CertificateDAO.exists_active(course_id, student_id):
            raise ValidationError('该学员已有有效的结业证书')

        return course, student, reg

    @staticmethod
    def issue_certificate(course_id, student_id, remark='', operated_by='管理员'):
        course, student, reg = CertificateService._validate_issue(course_id, student_id)

        certificate = CertificateDAO.create(
            course_id=course_id,
            student_id=student_id,
            registration_id=reg['id'],
            status='issued',
            remark=remark,
            operated_by=operated_by
        )

        ExceptionLogDAO.create(
            'certificate_issued',
            f'结业证书已生成：学员 {student["name"]}({student["employee_id"]}) '
            f'在课程【{course["title"]}】获得结业证书，编号：{certificate["certificate_no"]}',
            course_id=course_id,
            student_id=student_id
        )

        return certificate

    @staticmethod
    def batch_generate_certificates(course_id, student_ids=None, remark='', operated_by='管理员'):
        course = CourseDAO.get_by_id(course_id)
        if not course:
            raise ValidationError('课程不存在')

        CertificateService._validate_course_ended(course)

        preview = CertificateService.preview_generation(course_id)

        if student_ids is None:
            eligible_ids = [s['student_id'] for s in preview['eligible']]
        else:
            eligible_ids = [s['student_id'] for s in preview['eligible']
                            if s['student_id'] in student_ids]

        total_count = len(eligible_ids) + len(preview['ineligible'])
        if student_ids is not None:
            total_count = len(student_ids)

        batch_log_id = CertificateBatchLogDAO.create(
            course_id=course_id,
            operation_type='batch_generate',
            total_count=total_count,
            operated_by=operated_by
        )

        success_count = 0
        failure_count = 0

        for student_id in (eligible_ids if student_ids is None else student_ids):
            try:
                cert = CertificateService.issue_certificate(
                    course_id=course_id,
                    student_id=student_id,
                    remark=remark,
                    operated_by=operated_by
                )
                CertificateBatchItemDAO.create(
                    batch_log_id=batch_log_id,
                    student_id=student_id,
                    success=True,
                    certificate_id=cert['id']
                )
                success_count += 1
            except ValidationError as e:
                student = StudentDAO.get_by_id(student_id)
                student_name = student['name'] if student else '未知'
                employee_id = student['employee_id'] if student else '未知'

                ExceptionLogDAO.create(
                    'certificate_generation_failed',
                    f'结业证书生成失败：学员 {student_name}({employee_id}) '
                    f'在课程【{course["title"]}】生成证书被拦截：{e}',
                    course_id=course_id,
                    student_id=student_id
                )

                CertificateBatchItemDAO.create(
                    batch_log_id=batch_log_id,
                    student_id=student_id,
                    success=False,
                    failure_reason=str(e)
                )
                failure_count += 1

        CertificateBatchLogDAO.update_counts(batch_log_id, success_count, failure_count)

        items = CertificateBatchItemDAO.get_by_batch_log(batch_log_id)
        return {
            'batch_log_id': batch_log_id,
            'course_id': course_id,
            'course_title': course['title'],
            'total_count': total_count,
            'success_count': success_count,
            'failure_count': failure_count,
            'items': items
        }

    @staticmethod
    def reissue_certificate(course_id, student_id, remark='', operated_by='管理员'):
        course = CourseDAO.get_by_id(course_id)
        if not course:
            raise ValidationError('课程不存在')

        student = StudentDAO.get_by_id(student_id)
        if not student:
            raise ValidationError('学员不存在')

        CertificateService._validate_course_ended(course)

        registrations = RegistrationDAO.get_by_course_all_status(course_id)
        reg = next((r for r in registrations if r['student_id'] == student_id), None)
        if not reg:
            raise ValidationError('该学员未报名此课程')
        if reg['status'] == 'cancelled':
            raise ValidationError('该学员已取消报名')

        attendances = AttendanceDAO.get_by_course(course_id)
        att = next((a for a in attendances if a['student_id'] == student_id), None)
        if not att or att['status'] != 'present':
            raise ValidationError('该学员未出勤或出勤不达标')

        existing_certs = CertificateDAO.get_by_course_and_student(course_id, student_id)
        issued_certs = [c for c in existing_certs if c['status'] == 'issued']

        if issued_certs:
            for cert in issued_certs:
                CertificateDAO.void_certificate(
                    cert['id'],
                    void_reason='补发新证书，原证书作废',
                    operated_by=operated_by
                )
                ExceptionLogDAO.create(
                    'certificate_voided',
                    f'结业证书作废：学员 {student["name"]}({student["employee_id"]}) '
                    f'在课程【{course["title"]}】的证书 {cert["certificate_no"]} 因补发作废',
                    course_id=course_id,
                    student_id=student_id
                )

        new_cert = CertificateDAO.create(
            course_id=course_id,
            student_id=student_id,
            registration_id=existing_certs[0]['registration_id'] if existing_certs else reg['id'],
            status='issued',
            remark=remark,
            operated_by=operated_by
        )

        ExceptionLogDAO.create(
            'certificate_reissued',
            f'结业证书已补发：学员 {student["name"]}({student["employee_id"]}) '
            f'在课程【{course["title"]}】补发结业证书，编号：{new_cert["certificate_no"]}',
            course_id=course_id,
            student_id=student_id
        )

        return new_cert

    @staticmethod
    def void_certificate(cert_id, void_reason, operated_by='管理员'):
        cert = CertificateDAO.get_by_id(cert_id)
        if not cert:
            raise ValidationError('证书不存在')

        if cert['status'] == 'voided':
            raise ValidationError('该证书已作废')

        if not void_reason or len(void_reason.strip()) < 5:
            raise ValidationError('请填写作废原因（至少5个字符）')

        success = CertificateDAO.void_certificate(cert_id, void_reason, operated_by)
        if not success:
            raise ValidationError('作废失败，证书可能已被修改')

        ExceptionLogDAO.create(
            'certificate_voided',
            f'结业证书作废：学员 {cert["student_name"]}({cert["employee_id"]}) '
            f'在课程【{cert["course_title"]}】的证书 {cert["certificate_no"]} 被作废，原因：{void_reason}',
            course_id=cert['course_id'],
            student_id=cert['student_id']
        )

        return CertificateDAO.get_by_id(cert_id)

    @staticmethod
    def get_certificate(cert_id):
        return CertificateDAO.get_by_id(cert_id)

    @staticmethod
    def get_certificate_by_no(certificate_no):
        return CertificateDAO.get_by_certificate_no(certificate_no)

    @staticmethod
    def get_all_certificates(course_id=None, student_id=None, status=None):
        return CertificateDAO.get_all(course_id, student_id, status)

    @staticmethod
    def get_certificates_by_course(course_id):
        return CertificateDAO.get_all(course_id=course_id)

    @staticmethod
    def get_certificates_by_student(student_id):
        return CertificateDAO.get_all(student_id=student_id)

    @staticmethod
    def get_batch_log(batch_log_id):
        return CertificateBatchLogDAO.get_by_id(batch_log_id)

    @staticmethod
    def get_batch_items(batch_log_id):
        return CertificateBatchItemDAO.get_by_batch_log(batch_log_id)

    @staticmethod
    def get_all_batch_logs():
        return CertificateBatchLogDAO.get_all()
