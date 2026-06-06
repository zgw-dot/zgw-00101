from datetime import datetime
from db.dao import CourseDAO, RegistrationDAO, ExceptionLogDAO

class ValidationError(Exception):
    pass

class CourseService:
    @staticmethod
    def validate_course_data(course_data):
        if not course_data.get('title'):
            raise ValidationError('课程标题不能为空')
        if not course_data.get('theme'):
            raise ValidationError('课程主题不能为空')
        if not course_data.get('instructor'):
            raise ValidationError('讲师不能为空')
        if not course_data.get('venue'):
            raise ValidationError('场地不能为空')

        try:
            start_time = datetime.fromisoformat(course_data['start_time'])
            end_time = datetime.fromisoformat(course_data['end_time'])
            deadline = datetime.fromisoformat(course_data['registration_deadline'])
        except (ValueError, KeyError) as e:
            raise ValidationError(f'日期时间格式错误: {e}')

        if end_time <= start_time:
            raise ValidationError('课程结束时间必须晚于开始时间')

        if deadline >= start_time:
            raise ValidationError('报名截止时间必须早于课程开始时间')

        capacity = course_data.get('capacity', 30)
        if not isinstance(capacity, int) or capacity <= 0:
            raise ValidationError('课程容量必须是正整数')

        return True

    @staticmethod
    def create_course(course_data):
        CourseService.validate_course_data(course_data)
        course_id = CourseDAO.create(course_data)
        return course_id

    @staticmethod
    def update_course(course_id, course_data):
        CourseService.validate_course_data(course_data)

        current = CourseDAO.get_by_id(course_id)
        if not current:
            raise ValidationError('课程不存在')

        if current['status'] == 'published':
            registered_count = RegistrationDAO.count_by_course(course_id)
            if course_data['capacity'] < registered_count:
                raise ValidationError(
                    f'已报名 {registered_count} 人，容量不能小于已报名人数'
                )

        success = CourseDAO.update(course_id, course_data)
        return success

    @staticmethod
    def publish_course(course_id):
        course = CourseDAO.get_by_id(course_id)
        if not course:
            raise ValidationError('课程不存在')

        if course['status'] == 'published':
            raise ValidationError('课程已发布')

        course_data = dict(course)
        course_data['status'] = 'published'
        success = CourseDAO.update(course_id, course_data)
        return success

    @staticmethod
    def get_course(course_id):
        return CourseDAO.get_by_id(course_id)

    @staticmethod
    def get_all_courses(status=None):
        return CourseDAO.get_all(status)

    @staticmethod
    def get_courses_by_date(start_date, end_date):
        return CourseDAO.get_by_date_range(start_date, end_date)

    @staticmethod
    def get_courses_by_theme(theme, exclude_course_id=None):
        return CourseDAO.get_by_theme(theme, exclude_course_id)

    @staticmethod
    def get_course_attendance_summary(course_id):
        course = CourseDAO.get_by_id(course_id)
        if not course:
            raise ValidationError('课程不存在')

        registrations = RegistrationDAO.get_by_course(course_id)
        total = len(registrations)

        from db.dao import AttendanceDAO
        attendances = AttendanceDAO.get_by_course(course_id)

        present = sum(1 for a in attendances if a['status'] == 'present')
        absent = sum(1 for a in attendances if a['status'] == 'absent')
        pending = sum(1 for a in attendances if a['status'] == 'pending')
        makeup = sum(1 for a in attendances if a['is_makeup'] == 1)

        return {
            'course': course,
            'total_registered': total,
            'capacity': course['capacity'],
            'present': present,
            'absent': absent,
            'pending': pending,
            'makeup': makeup,
            'attendance_rate': (present / total * 100) if total > 0 else 0
        }

    @staticmethod
    def delete_course(course_id):
        course = CourseDAO.get_by_id(course_id)
        if not course:
            raise ValidationError('课程不存在')

        registered_count = RegistrationDAO.count_by_course(course_id)
        if registered_count > 0:
            raise ValidationError('已有学员报名，无法删除课程')

        success = CourseDAO.delete(course_id)
        return success
