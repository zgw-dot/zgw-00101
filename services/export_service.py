import csv
import os
from datetime import datetime
from db.dao import AttendanceDAO, ExceptionLogDAO, CourseDAO, StudentDAO, RegistrationDAO

class ExportService:
    @staticmethod
    def export_course_attendance(course_id, output_path=None):
        course = CourseDAO.get_by_id(course_id)
        if not course:
            raise ValueError('课程不存在')

        from services.attendance_service import AttendanceService
        attendances = AttendanceService.get_course_attendance(course_id)

        if output_path is None:
            output_dir = os.path.join(
                os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                'exports'
            )
            os.makedirs(output_dir, exist_ok=True)
            safe_title = course['title'].replace('/', '_').replace('\\', '_')
            output_path = os.path.join(
                output_dir,
                f'出勤表_{safe_title}_{datetime.now().strftime("%Y%m%d_%H%M%S")}.csv'
            )

        status_map = {
            'present': '已出勤',
            'absent': '缺勤',
            'pending': '未签到'
        }

        makeup_map = {
            'none': '无',
            'pending': '待审核',
            'approved': '已通过',
            'rejected': '已驳回'
        }

        with open(output_path, 'w', newline='', encoding='utf-8-sig') as f:
            writer = csv.writer(f)

            writer.writerow(['课程出勤表'])
            writer.writerow(['课程名称', course['title']])
            writer.writerow(['课程主题', course['theme']])
            writer.writerow(['讲师', course['instructor']])
            writer.writerow(['场地', course['venue']])
            writer.writerow(['开始时间', course['start_time']])
            writer.writerow(['结束时间', course['end_time']])
            writer.writerow(['课程容量', course['capacity']])
            writer.writerow([])

            writer.writerow([
                '序号', '工号', '姓名', '部门', '签到状态',
                '签到时间', '是否补签', '补签状态', '补签原因'
            ])

            for idx, att in enumerate(attendances, 1):
                writer.writerow([
                    idx,
                    att['employee_id'],
                    att['name'],
                    att.get('department', ''),
                    status_map.get(att['status'], att['status']),
                    att.get('check_in_time') or '',
                    '是' if att['is_makeup'] else '否',
                    makeup_map.get(att.get('makeup_status', 'none'), '无'),
                    att.get('makeup_reason') or ''
                ])

            writer.writerow([])
            present = sum(1 for a in attendances if a['status'] == 'present')
            absent = sum(1 for a in attendances if a['status'] == 'absent')
            pending = sum(1 for a in attendances if a['status'] == 'pending')
            writer.writerow(['统计', '', '', '', f'出勤: {present}',
                           f'缺勤: {absent}', f'未签到: {pending}', '', ''])

        return output_path

    @staticmethod
    def export_exception_logs(output_path=None, handled=None):
        logs = ExceptionLogDAO.get_all(handled=handled)

        if output_path is None:
            output_dir = os.path.join(
                os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                'exports'
            )
            os.makedirs(output_dir, exist_ok=True)
            output_path = os.path.join(
                output_dir,
                f'异常处理日志_{datetime.now().strftime("%Y%m%d_%H%M%S")}.csv'
            )

        type_map = {
            'over_capacity': '超容量报名',
            'transfer_after_deadline': '截止后调课',
            'duplicate_checkin': '重复签到',
            'unapproved_makeup': '未审核补签生效'
        }

        with open(output_path, 'w', newline='', encoding='utf-8-sig') as f:
            writer = csv.writer(f)

            writer.writerow(['异常处理日志'])
            writer.writerow(['导出时间', datetime.now().strftime('%Y-%m-%d %H:%M:%S')])
            writer.writerow([])

            writer.writerow([
                '序号', '异常类型', '描述', '关联课程', '关联学员',
                '发生时间', '处理状态', '处理时间', '处理人'
            ])

            for idx, log in enumerate(logs, 1):
                writer.writerow([
                    idx,
                    type_map.get(log['type'], log['type']),
                    log['description'],
                    log.get('course_title') or '',
                    f'{log.get("student_name", "")}({log.get("employee_id", "")})' if log.get('student_name') else '',
                    log['created_at'],
                    '已处理' if log['handled'] else '未处理',
                    log.get('handled_at') or '',
                    log.get('handled_by') or ''
                ])

        return output_path

    @staticmethod
    def export_all_history(output_path=None):
        if output_path is None:
            output_dir = os.path.join(
                os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                'exports'
            )
            os.makedirs(output_dir, exist_ok=True)
            output_path = os.path.join(
                output_dir,
                f'历史记录汇总_{datetime.now().strftime("%Y%m%d_%H%M%S")}.csv'
            )

        courses = CourseDAO.get_all()

        with open(output_path, 'w', newline='', encoding='utf-8-sig') as f:
            writer = csv.writer(f)

            writer.writerow(['培训历史记录汇总'])
            writer.writerow(['导出时间', datetime.now().strftime('%Y-%m-%d %H:%M:%S')])
            writer.writerow([])

            status_map = {'draft': '草稿', 'published': '已发布'}
            att_status_map = {'present': '已出勤', 'absent': '缺勤', 'pending': '未签到'}

            for course in courses:
                writer.writerow([f'=== {course["title"]} ==='])
                writer.writerow(['主题', course['theme']])
                writer.writerow(['状态', status_map.get(course['status'], course['status'])])
                writer.writerow(['讲师', course['instructor']])
                writer.writerow(['场地', course['venue']])
                writer.writerow(['时间', f'{course["start_time"]} ~ {course["end_time"]}'])
                writer.writerow(['容量', course['capacity']])

                regs = RegistrationDAO.get_by_course(course['id'])
                writer.writerow(['报名人数', len(regs)])

                from services.attendance_service import AttendanceService
                try:
                    attendances = AttendanceService.get_course_attendance(course['id'])
                    writer.writerow([
                        '出勤情况',
                        f'出勤{sum(1 for a in attendances if a["status"] == "present")}/'
                        f'缺勤{sum(1 for a in attendances if a["status"] == "absent")}/'
                        f'未签{sum(1 for a in attendances if a["status"] == "pending")}'
                    ])
                except:
                    pass

                writer.writerow(['--- 学员名单 ---'])
                writer.writerow(['工号', '姓名', '部门', '状态', '签到时间'])

                try:
                    for att in attendances:
                        writer.writerow([
                            att['employee_id'],
                            att['name'],
                            att.get('department', ''),
                            att_status_map.get(att['status'], att['status']),
                            att.get('check_in_time') or ''
                        ])
                except:
                    for reg in regs:
                        writer.writerow([
                            reg['employee_id'],
                            reg['name'],
                            reg.get('department', ''),
                            '已报名',
                            ''
                        ])

                writer.writerow([])
                writer.writerow([])

        return output_path
