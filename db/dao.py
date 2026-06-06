from datetime import datetime
from .database import get_connection

def row_to_dict(row):
    return dict(row) if row else None

def rows_to_dict_list(rows):
    return [dict(row) for row in rows] if rows else []

class CourseDAO:
    @staticmethod
    def create(course_data):
        now = datetime.now().isoformat()
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute('''
        INSERT INTO courses (title, theme, description, instructor, venue,
                           start_time, end_time, capacity, registration_deadline,
                           status, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (course_data['title'], course_data['theme'], course_data.get('description', ''),
              course_data['instructor'], course_data['venue'],
              course_data['start_time'], course_data['end_time'],
              course_data['capacity'], course_data['registration_deadline'],
              course_data.get('status', 'draft'), now, now))
        conn.commit()
        course_id = cursor.lastrowid
        conn.close()
        return course_id

    @staticmethod
    def update(course_id, course_data):
        now = datetime.now().isoformat()
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute('''
        UPDATE courses SET title=?, theme=?, description=?, instructor=?, venue=?,
                          start_time=?, end_time=?, capacity=?, registration_deadline=?,
                          status=?, updated_at=?
        WHERE id=?
        ''', (course_data['title'], course_data['theme'], course_data.get('description', ''),
              course_data['instructor'], course_data['venue'],
              course_data['start_time'], course_data['end_time'],
              course_data['capacity'], course_data['registration_deadline'],
              course_data.get('status', 'draft'), now, course_id))
        conn.commit()
        conn.close()
        return cursor.rowcount > 0

    @staticmethod
    def get_by_id(course_id):
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM courses WHERE id=?', (course_id,))
        row = cursor.fetchone()
        conn.close()
        return row_to_dict(row)

    @staticmethod
    def get_all(status=None):
        conn = get_connection()
        cursor = conn.cursor()
        if status:
            cursor.execute('SELECT * FROM courses WHERE status=? ORDER BY start_time DESC', (status,))
        else:
            cursor.execute('SELECT * FROM courses ORDER BY start_time DESC')
        rows = cursor.fetchall()
        conn.close()
        return rows_to_dict_list(rows)

    @staticmethod
    def get_by_date_range(start_date, end_date):
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute('''
        SELECT * FROM courses WHERE date(start_time) BETWEEN ? AND ?
        ORDER BY start_time
        ''', (start_date, end_date))
        rows = cursor.fetchall()
        conn.close()
        return rows_to_dict_list(rows)

    @staticmethod
    def get_by_theme(theme, exclude_course_id=None):
        conn = get_connection()
        cursor = conn.cursor()
        if exclude_course_id:
            cursor.execute('''
            SELECT * FROM courses WHERE theme=? AND id!=? AND status='published'
            ORDER BY start_time
            ''', (theme, exclude_course_id))
        else:
            cursor.execute('''
            SELECT * FROM courses WHERE theme=? AND status='published'
            ORDER BY start_time
            ''', (theme,))
        rows = cursor.fetchall()
        conn.close()
        return rows_to_dict_list(rows)

    @staticmethod
    def delete(course_id):
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute('DELETE FROM courses WHERE id=?', (course_id,))
        conn.commit()
        conn.close()
        return cursor.rowcount > 0

class StudentDAO:
    @staticmethod
    def create(student_data):
        now = datetime.now().isoformat()
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute('''
        INSERT INTO students (name, employee_id, department, phone, email, created_at)
        VALUES (?, ?, ?, ?, ?, ?)
        ''', (student_data['name'], student_data['employee_id'],
              student_data.get('department', ''), student_data.get('phone', ''),
              student_data.get('email', ''), now))
        conn.commit()
        student_id = cursor.lastrowid
        conn.close()
        return student_id

    @staticmethod
    def get_by_id(student_id):
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM students WHERE id=?', (student_id,))
        row = cursor.fetchone()
        conn.close()
        return row_to_dict(row)

    @staticmethod
    def get_by_employee_id(employee_id):
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM students WHERE employee_id=?', (employee_id,))
        row = cursor.fetchone()
        conn.close()
        return row_to_dict(row)

    @staticmethod
    def get_all():
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM students ORDER BY name')
        rows = cursor.fetchall()
        conn.close()
        return rows_to_dict_list(rows)

    @staticmethod
    def get_or_create(student_data):
        student = StudentDAO.get_by_employee_id(student_data['employee_id'])
        if student:
            return student['id']
        return StudentDAO.create(student_data)

class RegistrationDAO:
    @staticmethod
    def create(course_id, student_id):
        now = datetime.now().isoformat()
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute('''
        INSERT INTO registrations (course_id, student_id, status, registered_at)
        VALUES (?, ?, 'registered', ?)
        ''', (course_id, student_id, now))
        conn.commit()
        reg_id = cursor.lastrowid
        conn.close()
        return reg_id

    @staticmethod
    def get_by_id(reg_id):
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute('''
        SELECT r.*, c.title as course_title, c.theme as course_theme,
               c.start_time as course_start, c.end_time as course_end,
               s.name as student_name, s.employee_id
        FROM registrations r
        JOIN courses c ON r.course_id = c.id
        JOIN students s ON r.student_id = s.id
        WHERE r.id=?
        ''', (reg_id,))
        row = cursor.fetchone()
        conn.close()
        return row_to_dict(row)

    @staticmethod
    def get_by_course(course_id):
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute('''
        SELECT r.*, s.name, s.employee_id, s.department, s.phone, s.email
        FROM registrations r
        JOIN students s ON r.student_id = s.id
        WHERE r.course_id=? AND r.status='registered'
        ORDER BY s.name
        ''', (course_id,))
        rows = cursor.fetchall()
        conn.close()
        return rows_to_dict_list(rows)

    @staticmethod
    def get_by_student(student_id):
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute('''
        SELECT r.*, c.title, c.theme, c.instructor, c.venue,
               c.start_time, c.end_time, c.status as course_status
        FROM registrations r
        JOIN courses c ON r.course_id = c.id
        WHERE r.student_id=?
        ORDER BY c.start_time DESC
        ''', (student_id,))
        rows = cursor.fetchall()
        conn.close()
        return rows_to_dict_list(rows)

    @staticmethod
    def count_by_course(course_id):
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute('''
        SELECT COUNT(*) as count FROM registrations
        WHERE course_id=? AND status='registered'
        ''', (course_id,))
        row = cursor.fetchone()
        conn.close()
        return row['count'] if row else 0

    @staticmethod
    def exists(course_id, student_id):
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute('''
        SELECT id FROM registrations
        WHERE course_id=? AND student_id=? AND status='registered'
        ''', (course_id, student_id))
        row = cursor.fetchone()
        conn.close()
        return row is not None

    @staticmethod
    def update_status(reg_id, status):
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute('UPDATE registrations SET status=? WHERE id=?', (status, reg_id))
        conn.commit()
        conn.close()
        return cursor.rowcount > 0

    @staticmethod
    def transfer(reg_id, from_course_id, to_course_id):
        conn = get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute('UPDATE registrations SET status=? WHERE id=?', ('transferred_out', reg_id))
            now = datetime.now().isoformat()
            cursor.execute('''
            INSERT INTO registrations (course_id, student_id, status, registered_at)
            SELECT ?, student_id, 'registered', ?
            FROM registrations WHERE id=?
            ''', (to_course_id, now, reg_id))
            conn.commit()
            return True
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            conn.close()

class TransferRequestDAO:
    @staticmethod
    def create(registration_id, from_course_id, to_course_id, reason=''):
        now = datetime.now().isoformat()
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute('''
        INSERT INTO transfer_requests (registration_id, from_course_id, to_course_id,
                                       reason, status, requested_at)
        VALUES (?, ?, ?, ?, 'pending', ?)
        ''', (registration_id, from_course_id, to_course_id, reason, now))
        conn.commit()
        request_id = cursor.lastrowid
        conn.close()
        return request_id

    @staticmethod
    def get_all(status=None):
        conn = get_connection()
        cursor = conn.cursor()
        query = '''
        SELECT t.*, c1.title as from_course_title, c2.title as to_course_title,
               s.name as student_name, s.employee_id,
               c1.theme as course_theme
        FROM transfer_requests t
        JOIN courses c1 ON t.from_course_id = c1.id
        JOIN courses c2 ON t.to_course_id = c2.id
        JOIN registrations r ON t.registration_id = r.id
        JOIN students s ON r.student_id = s.id
        '''
        if status:
            query += ' WHERE t.status=?'
            query += ' ORDER BY t.requested_at DESC'
            cursor.execute(query, (status,))
        else:
            query += ' ORDER BY t.requested_at DESC'
            cursor.execute(query)
        rows = cursor.fetchall()
        conn.close()
        return rows_to_dict_list(rows)

    @staticmethod
    def review(request_id, status, review_note='', reviewer=''):
        now = datetime.now().isoformat()
        conn = get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute('''
            UPDATE transfer_requests
            SET status=?, review_note=?, reviewed_at=?
            WHERE id=?
            ''', (status, review_note, now, request_id))
            conn.commit()
            return True
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            conn.close()

    @staticmethod
    def get_by_id(request_id):
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM transfer_requests WHERE id=?', (request_id,))
        row = cursor.fetchone()
        conn.close()
        return row_to_dict(row)

class AttendanceDAO:
    @staticmethod
    def get_or_create(course_id, student_id):
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute('''
        SELECT * FROM attendances WHERE course_id=? AND student_id=?
        ''', (course_id, student_id))
        row = cursor.fetchone()
        if row:
            conn.close()
            return row_to_dict(row)
        now = datetime.now().isoformat()
        cursor.execute('''
        INSERT INTO attendances (course_id, student_id, status, created_at, updated_at)
        VALUES (?, ?, 'pending', ?, ?)
        ''', (course_id, student_id, now, now))
        conn.commit()
        att_id = cursor.lastrowid
        cursor.execute('SELECT * FROM attendances WHERE id=?', (att_id,))
        row = cursor.fetchone()
        conn.close()
        return row_to_dict(row)

    @staticmethod
    def check_in(course_id, student_id):
        now = datetime.now().isoformat()
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute('''
        UPDATE attendances
        SET check_in_time=?, status='present', updated_at=?
        WHERE course_id=? AND student_id=?
        ''', (now, now, course_id, student_id))
        conn.commit()
        updated = cursor.rowcount > 0
        conn.close()
        return updated

    @staticmethod
    def get_by_course(course_id):
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute('''
        SELECT a.*, s.name, s.employee_id, s.department
        FROM attendances a
        JOIN students s ON a.student_id = s.id
        WHERE a.course_id=?
        ORDER BY s.name
        ''', (course_id,))
        rows = cursor.fetchall()
        conn.close()
        return rows_to_dict_list(rows)

    @staticmethod
    def get_by_student(student_id):
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute('''
        SELECT a.*, c.title, c.theme, c.start_time, c.end_time, c.instructor
        FROM attendances a
        JOIN courses c ON a.course_id = c.id
        WHERE a.student_id=?
        ORDER BY c.start_time DESC
        ''', (student_id,))
        rows = cursor.fetchall()
        conn.close()
        return rows_to_dict_list(rows)

    @staticmethod
    def request_makeup(course_id, student_id, reason):
        now = datetime.now().isoformat()
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute('''
        UPDATE attendances
        SET makeup_reason=?, makeup_requested_at=?, makeup_status='pending', updated_at=?
        WHERE course_id=? AND student_id=?
        ''', (reason, now, now, course_id, student_id))
        conn.commit()
        updated = cursor.rowcount > 0
        conn.close()
        return updated

    @staticmethod
    def review_makeup(attendance_id, approved, reviewer='', note=''):
        now = datetime.now().isoformat()
        conn = get_connection()
        cursor = conn.cursor()
        try:
            if approved:
                cursor.execute('''
                UPDATE attendances
                SET is_makeup=1, status='present', makeup_status='approved',
                    makeup_reviewed_at=?, makeup_reviewer=?, updated_at=?
                WHERE id=?
                ''', (now, reviewer, now, attendance_id))
            else:
                cursor.execute('''
                UPDATE attendances
                SET makeup_status='rejected', makeup_reviewed_at=?,
                    makeup_reviewer=?, updated_at=?
                WHERE id=?
                ''', (now, reviewer, now, attendance_id))
            conn.commit()
            return True
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            conn.close()

    @staticmethod
    def get_pending_makeups():
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute('''
        SELECT a.*, c.title as course_title, c.start_time as course_time,
               s.name as student_name, s.employee_id
        FROM attendances a
        JOIN courses c ON a.course_id = c.id
        JOIN students s ON a.student_id = s.id
        WHERE a.makeup_status='pending'
        ORDER BY a.makeup_requested_at DESC
        ''')
        rows = cursor.fetchall()
        conn.close()
        return rows_to_dict_list(rows)

    @staticmethod
    def mark_absent(course_id, student_id):
        now = datetime.now().isoformat()
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute('''
        UPDATE attendances
        SET status='absent', updated_at=?
        WHERE course_id=? AND student_id=? AND status='pending'
        ''', (now, course_id, student_id))
        conn.commit()
        updated = cursor.rowcount > 0
        conn.close()
        return updated

class ExceptionLogDAO:
    @staticmethod
    def create(exc_type, description, course_id=None, student_id=None):
        now = datetime.now().isoformat()
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute('''
        INSERT INTO exception_logs (course_id, student_id, type, description, created_at)
        VALUES (?, ?, ?, ?, ?)
        ''', (course_id, student_id, exc_type, description, now))
        conn.commit()
        log_id = cursor.lastrowid
        conn.close()
        return log_id

    @staticmethod
    def get_all(handled=None):
        conn = get_connection()
        cursor = conn.cursor()
        query = '''
        SELECT e.*, c.title as course_title, s.name as student_name, s.employee_id
        FROM exception_logs e
        LEFT JOIN courses c ON e.course_id = c.id
        LEFT JOIN students s ON e.student_id = s.id
        '''
        if handled is not None:
            query += ' WHERE e.handled=?'
        query += ' ORDER BY e.created_at DESC'
        if handled is not None:
            cursor.execute(query, (1 if handled else 0,))
        else:
            cursor.execute(query)
        rows = cursor.fetchall()
        conn.close()
        return rows_to_dict_list(rows)

    @staticmethod
    def mark_handled(log_id, handled_by=''):
        now = datetime.now().isoformat()
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute('''
        UPDATE exception_logs
        SET handled=1, handled_at=?, handled_by=?
        WHERE id=?
        ''', (now, handled_by, log_id))
        conn.commit()
        conn.close()
        return cursor.rowcount > 0
