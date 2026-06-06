import sqlite3
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
                SET status='absent', makeup_status='rejected', makeup_reviewed_at=?,
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

import json

class BatchOperationLogDAO:
    @staticmethod
    def create(operation_type, from_course_id=None, to_course_id=None,
               target_status=None, total_count=0, success_count=0,
               failure_count=0, operated_by='管理员'):
        now = datetime.now().isoformat()
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute('''
        INSERT INTO batch_operation_logs (
            operation_type, from_course_id, to_course_id, target_status,
            total_count, success_count, failure_count, operated_by, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (operation_type, from_course_id, to_course_id, target_status,
              total_count, success_count, failure_count, operated_by, now))
        conn.commit()
        log_id = cursor.lastrowid
        conn.close()
        return log_id

    @staticmethod
    def update_counts(log_id, success_count, failure_count):
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute('''
        UPDATE batch_operation_logs
        SET success_count=?, failure_count=?
        WHERE id=?
        ''', (success_count, failure_count, log_id))
        conn.commit()
        conn.close()
        return cursor.rowcount > 0

    @staticmethod
    def get_by_id(log_id):
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM batch_operation_logs WHERE id=?', (log_id,))
        row = cursor.fetchone()
        conn.close()
        return row_to_dict(row)

    @staticmethod
    def get_latest(limit=1):
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute('''
        SELECT * FROM batch_operation_logs
        WHERE undone=0 AND success_count > 0
        ORDER BY created_at DESC
        LIMIT ?
        ''', (limit,))
        rows = cursor.fetchall()
        conn.close()
        return rows_to_dict_list(rows)

    @staticmethod
    def mark_undone(log_id):
        now = datetime.now().isoformat()
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute('''
        UPDATE batch_operation_logs
        SET undone=1, undone_at=?
        WHERE id=?
        ''', (now, log_id))
        conn.commit()
        conn.close()
        return cursor.rowcount > 0

class BatchOperationItemDAO:
    @staticmethod
    def create(batch_log_id, registration_id, student_id, from_course_id,
               to_course_id, old_status, new_status, success,
               failure_reason=None, undo_data=None):
        now = datetime.now().isoformat()
        conn = get_connection()
        cursor = conn.cursor()
        undo_json = json.dumps(undo_data) if undo_data else None
        cursor.execute('''
        INSERT INTO batch_operation_items (
            batch_log_id, registration_id, student_id, from_course_id,
            to_course_id, old_status, new_status, success,
            failure_reason, undo_data, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (batch_log_id, registration_id, student_id, from_course_id,
              to_course_id, old_status, new_status, 1 if success else 0,
              failure_reason, undo_json, now))
        conn.commit()
        item_id = cursor.lastrowid
        conn.close()
        return item_id

    @staticmethod
    def get_by_batch_log(batch_log_id):
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute('''
        SELECT bi.*, s.name as student_name, s.employee_id,
               c1.title as from_course_title, c2.title as to_course_title
        FROM batch_operation_items bi
        JOIN students s ON bi.student_id = s.id
        LEFT JOIN courses c1 ON bi.from_course_id = c1.id
        LEFT JOIN courses c2 ON bi.to_course_id = c2.id
        WHERE bi.batch_log_id=?
        ORDER BY bi.id
        ''', (batch_log_id,))
        rows = cursor.fetchall()
        conn.close()
        items = rows_to_dict_list(rows)
        for item in items:
            if item.get('undo_data'):
                try:
                    item['undo_data'] = json.loads(item['undo_data'])
                except:
                    pass
        return items

    @staticmethod
    def get_successful_by_batch_log(batch_log_id):
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute('''
        SELECT bi.*, s.name as student_name, s.employee_id,
               c1.title as from_course_title, c2.title as to_course_title
        FROM batch_operation_items bi
        JOIN students s ON bi.student_id = s.id
        LEFT JOIN courses c1 ON bi.from_course_id = c1.id
        LEFT JOIN courses c2 ON bi.to_course_id = c2.id
        WHERE bi.batch_log_id=? AND bi.success=1
        ORDER BY bi.id
        ''', (batch_log_id,))
        rows = cursor.fetchall()
        conn.close()
        items = rows_to_dict_list(rows)
        for item in items:
            if item.get('undo_data'):
                try:
                    item['undo_data'] = json.loads(item['undo_data'])
                except:
                    pass
        return items

class RegistrationDAOExt:
    @staticmethod
    def get_registrations_by_ids(registration_ids):
        if not registration_ids:
            return []
        conn = get_connection()
        cursor = conn.cursor()
        placeholders = ','.join(['?'] * len(registration_ids))
        cursor.execute(f'''
        SELECT r.*, c.title as course_title, c.theme as course_theme,
               c.start_time as course_start, c.end_time as course_end,
               s.name as student_name, s.employee_id, s.department, s.phone, s.email
        FROM registrations r
        JOIN courses c ON r.course_id = c.id
        JOIN students s ON r.student_id = s.id
        WHERE r.id IN ({placeholders})
        ''', registration_ids)
        rows = cursor.fetchall()
        conn.close()
        return rows_to_dict_list(rows)

    @staticmethod
    def batch_update_status(registration_ids, new_status):
        if not registration_ids:
            return 0
        now = datetime.now().isoformat()
        conn = get_connection()
        cursor = conn.cursor()
        placeholders = ','.join(['?'] * len(registration_ids))
        cursor.execute(f'''
        UPDATE registrations SET status=? WHERE id IN ({placeholders})
        ''', [new_status] + registration_ids)
        conn.commit()
        count = cursor.rowcount
        conn.close()
        return count

    @staticmethod
    def batch_transfer(transfer_items):
        if not transfer_items:
            return []
        conn = get_connection()
        cursor = conn.cursor()
        results = []
        try:
            for item in transfer_items:
                reg_id = item['registration_id']
                to_course_id = item['to_course_id']
                student_id = item['student_id']

                cursor.execute('UPDATE registrations SET status=? WHERE id=?',
                              ('transferred_out', reg_id))

                now = datetime.now().isoformat()
                cursor.execute('''
                INSERT INTO registrations (course_id, student_id, status, registered_at)
                VALUES (?, ?, 'registered', ?)
                ''', (to_course_id, student_id, now))
                new_reg_id = cursor.lastrowid
                results.append({
                    'registration_id': reg_id,
                    'new_registration_id': new_reg_id,
                    'student_id': student_id,
                    'from_course_id': item['from_course_id'],
                    'to_course_id': to_course_id,
                    'success': True
                })
            conn.commit()
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            conn.close()
        return results

    @staticmethod
    def get_by_course_all_status(course_id):
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute('''
        SELECT r.*, s.name, s.employee_id, s.department, s.phone, s.email
        FROM registrations r
        JOIN students s ON r.student_id = s.id
        WHERE r.course_id=?
        ORDER BY s.name
        ''', (course_id,))
        rows = cursor.fetchall()
        conn.close()
        return rows_to_dict_list(rows)


class WaitingListDAO:
    @staticmethod
    def create(course_id, student_id, priority=0, source='manual', note=''):
        now = datetime.now().isoformat()
        conn = get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute('''
            INSERT INTO waiting_list (
                course_id, student_id, priority, source, status, added_at, note
            ) VALUES (?, ?, ?, ?, 'waiting', ?, ?)
            ''', (course_id, student_id, priority, source, now, note))
            conn.commit()
            return cursor.lastrowid
        except sqlite3.IntegrityError:
            conn.rollback()
            return None
        finally:
            conn.close()

    @staticmethod
    def get_by_id(waiting_id):
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute('''
        SELECT w.*, s.name, s.employee_id, s.department, s.phone,
               c.title as course_title
        FROM waiting_list w
        JOIN students s ON w.student_id = s.id
        JOIN courses c ON w.course_id = c.id
        WHERE w.id=?
        ''', (waiting_id,))
        row = cursor.fetchone()
        conn.close()
        return row_to_dict(row)

    @staticmethod
    def get_by_course(course_id, status='waiting'):
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute('''
        SELECT w.*, s.name, s.employee_id, s.department, s.phone
        FROM waiting_list w
        JOIN students s ON w.student_id = s.id
        WHERE w.course_id=? AND w.status=?
        ORDER BY w.priority DESC, w.added_at ASC
        ''', (course_id, status))
        rows = cursor.fetchall()
        conn.close()
        return rows_to_dict_list(rows)

    @staticmethod
    def get_all(status='waiting'):
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute('''
        SELECT w.*, s.name, s.employee_id, s.department, s.phone,
               c.title as course_title
        FROM waiting_list w
        JOIN students s ON w.student_id = s.id
        JOIN courses c ON w.course_id = c.id
        WHERE w.status=?
        ORDER BY c.title, w.priority DESC, w.added_at ASC
        ''', (status,))
        rows = cursor.fetchall()
        conn.close()
        return rows_to_dict_list(rows)

    @staticmethod
    def count_by_course(course_id, status='waiting'):
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute('''
        SELECT COUNT(*) as count FROM waiting_list
        WHERE course_id=? AND status=?
        ''', (course_id, status))
        row = cursor.fetchone()
        conn.close()
        return row['count'] if row else 0

    @staticmethod
    def exists(course_id, student_id, status='waiting'):
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute('''
        SELECT id FROM waiting_list
        WHERE course_id=? AND student_id=? AND status=?
        ''', (course_id, student_id, status))
        row = cursor.fetchone()
        conn.close()
        return row is not None

    @staticmethod
    def update_status(waiting_id, status, note=''):
        now = datetime.now().isoformat()
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute('''
        UPDATE waiting_list
        SET status=?, processed_at=?, note=?
        WHERE id=?
        ''', (status, now, note, waiting_id))
        conn.commit()
        updated = cursor.rowcount > 0
        conn.close()
        return updated

    @staticmethod
    def delete(waiting_id):
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute('DELETE FROM waiting_list WHERE id=?', (waiting_id,))
        conn.commit()
        deleted = cursor.rowcount > 0
        conn.close()
        return deleted

    @staticmethod
    def get_position(waiting_id):
        waiting = WaitingListDAO.get_by_id(waiting_id)
        if not waiting:
            return None
        course_id = waiting['course_id']
        all_waiting = WaitingListDAO.get_by_course(course_id, 'waiting')
        for idx, w in enumerate(all_waiting, 1):
            if w['id'] == waiting_id:
                return idx
        return None


class WaitingListResultDAO:
    @staticmethod
    def create(course_id, waiting_list_id, student_id, original_position,
               priority, source, result, failure_reason=None, registration_id=None):
        now = datetime.now().isoformat()
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute('''
        INSERT INTO waiting_list_results (
            course_id, waiting_list_id, student_id, original_position,
            priority, source, result, failure_reason, registration_id, processed_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (course_id, waiting_list_id, student_id, original_position,
              priority, source, result, failure_reason, registration_id, now))
        conn.commit()
        result_id = cursor.lastrowid
        conn.close()
        return result_id

    @staticmethod
    def get_by_course(course_id):
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute('''
        SELECT wr.*, s.name, s.employee_id, s.department, s.phone,
               c.title as course_title
        FROM waiting_list_results wr
        JOIN students s ON wr.student_id = s.id
        JOIN courses c ON wr.course_id = c.id
        WHERE wr.course_id=?
        ORDER BY wr.processed_at DESC
        ''', (course_id,))
        rows = cursor.fetchall()
        conn.close()
        return rows_to_dict_list(rows)

    @staticmethod
    def get_latest_by_course(course_id, limit=100):
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute('''
        SELECT wr.*, s.name, s.employee_id, s.department, s.phone,
               c.title as course_title
        FROM waiting_list_results wr
        JOIN students s ON wr.student_id = s.id
        JOIN courses c ON wr.course_id = c.id
        WHERE wr.course_id=?
        ORDER BY wr.processed_at DESC
        LIMIT ?
        ''', (course_id, limit))
        rows = cursor.fetchall()
        conn.close()
        return rows_to_dict_list(rows)

    @staticmethod
    def get_all(limit=1000):
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute('''
        SELECT wr.*, s.name, s.employee_id, s.department, s.phone,
               c.title as course_title
        FROM waiting_list_results wr
        JOIN students s ON wr.student_id = s.id
        JOIN courses c ON wr.course_id = c.id
        ORDER BY wr.processed_at DESC
        LIMIT ?
        ''', (limit,))
        rows = cursor.fetchall()
        conn.close()
        return rows_to_dict_list(rows)


class CertificateDAO:
    @staticmethod
    def generate_certificate_no(course_id):
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT title, start_time FROM courses WHERE id=?', (course_id,))
        course = cursor.fetchone()
        conn.close()

        if not course:
            return None

        title = course['title']
        start_time = course['start_time']
        year = start_time[:4]
        title_short = ''.join([c for c in title if c.isalnum()])[:8].upper()

        import random
        random_part = ''.join([str(random.randint(0, 9)) for _ in range(6)])
        return f'CERT-{year}-{title_short}-{random_part}'

    @staticmethod
    def create(course_id, student_id, registration_id=None, status='issued', remark='', operated_by='管理员'):
        now = datetime.now().isoformat()
        conn = get_connection()
        cursor = conn.cursor()
        try:
            certificate_no = None
            for _ in range(5):
                candidate = CertificateDAO.generate_certificate_no(course_id)
                cursor.execute('SELECT id FROM certificates WHERE certificate_no=?', (candidate,))
                if not cursor.fetchone():
                    certificate_no = candidate
                    break

            if not certificate_no:
                raise Exception('无法生成唯一证书编号')

            issue_date = now[:10]
            cursor.execute('''
            INSERT INTO certificates (
                certificate_no, course_id, student_id, registration_id,
                status, issue_date, generated_at, remark, operated_by
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (certificate_no, course_id, student_id, registration_id,
                  status, issue_date, now, remark, operated_by))
            conn.commit()
            cert_id = cursor.lastrowid
            cursor.execute('SELECT * FROM certificates WHERE id=?', (cert_id,))
            row = cursor.fetchone()
            return row_to_dict(row)
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            conn.close()

    @staticmethod
    def get_by_id(cert_id):
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute('''
        SELECT c.*, co.title as course_title, co.theme as course_theme,
               co.start_time as course_start, co.end_time as course_end,
               s.name as student_name, s.employee_id, s.department
        FROM certificates c
        JOIN courses co ON c.course_id = co.id
        JOIN students s ON c.student_id = s.id
        WHERE c.id=?
        ''', (cert_id,))
        row = cursor.fetchone()
        conn.close()
        return row_to_dict(row)

    @staticmethod
    def get_by_certificate_no(certificate_no):
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute('''
        SELECT c.*, co.title as course_title, co.theme as course_theme,
               co.start_time as course_start, co.end_time as course_end,
               s.name as student_name, s.employee_id, s.department
        FROM certificates c
        JOIN courses co ON c.course_id = co.id
        JOIN students s ON c.student_id = s.id
        WHERE c.certificate_no=?
        ''', (certificate_no,))
        row = cursor.fetchone()
        conn.close()
        return row_to_dict(row)

    @staticmethod
    def get_by_course_and_student(course_id, student_id):
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute('''
        SELECT c.*, co.title as course_title, s.name as student_name, s.employee_id
        FROM certificates c
        JOIN courses co ON c.course_id = co.id
        JOIN students s ON c.student_id = s.id
        WHERE c.course_id=? AND c.student_id=?
        ORDER BY c.generated_at DESC
        ''', (course_id, student_id))
        rows = cursor.fetchall()
        conn.close()
        return rows_to_dict_list(rows)

    @staticmethod
    def get_all(course_id=None, student_id=None, status=None):
        conn = get_connection()
        cursor = conn.cursor()
        query = '''
        SELECT c.*, co.title as course_title, co.theme as course_theme,
               co.start_time as course_start, co.end_time as course_end,
               s.name as student_name, s.employee_id, s.department
        FROM certificates c
        JOIN courses co ON c.course_id = co.id
        JOIN students s ON c.student_id = s.id
        '''
        conditions = []
        params = []
        if course_id:
            conditions.append('c.course_id=?')
            params.append(course_id)
        if student_id:
            conditions.append('c.student_id=?')
            params.append(student_id)
        if status:
            conditions.append('c.status=?')
            params.append(status)
        if conditions:
            query += ' WHERE ' + ' AND '.join(conditions)
        query += ' ORDER BY c.generated_at DESC'
        cursor.execute(query, params)
        rows = cursor.fetchall()
        conn.close()
        return rows_to_dict_list(rows)

    @staticmethod
    def void_certificate(cert_id, void_reason, operated_by='管理员'):
        now = datetime.now().isoformat()
        conn = get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute('''
            UPDATE certificates
            SET status='voided', voided_at=?, void_reason=?, operated_by=?
            WHERE id=? AND status='issued'
            ''', (now, void_reason, operated_by, cert_id))
            conn.commit()
            updated = cursor.rowcount > 0
            return updated
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            conn.close()

    @staticmethod
    def exists_active(course_id, student_id):
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute('''
        SELECT id FROM certificates
        WHERE course_id=? AND student_id=? AND status='issued'
        ''', (course_id, student_id))
        row = cursor.fetchone()
        conn.close()
        return row is not None


class CertificateBatchLogDAO:
    @staticmethod
    def create(course_id, operation_type, total_count=0, success_count=0,
               failure_count=0, operated_by='管理员'):
        now = datetime.now().isoformat()
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute('''
        INSERT INTO certificate_batch_logs (
            course_id, operation_type, total_count, success_count,
            failure_count, operated_by, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (course_id, operation_type, total_count, success_count,
              failure_count, operated_by, now))
        conn.commit()
        log_id = cursor.lastrowid
        conn.close()
        return log_id

    @staticmethod
    def update_counts(log_id, success_count, failure_count):
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute('''
        UPDATE certificate_batch_logs
        SET success_count=?, failure_count=?
        WHERE id=?
        ''', (success_count, failure_count, log_id))
        conn.commit()
        conn.close()
        return cursor.rowcount > 0

    @staticmethod
    def get_by_id(log_id):
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute('''
        SELECT bl.*, c.title as course_title
        FROM certificate_batch_logs bl
        JOIN courses c ON bl.course_id = c.id
        WHERE bl.id=?
        ''', (log_id,))
        row = cursor.fetchone()
        conn.close()
        return row_to_dict(row)

    @staticmethod
    def get_all():
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute('''
        SELECT bl.*, c.title as course_title
        FROM certificate_batch_logs bl
        JOIN courses c ON bl.course_id = c.id
        ORDER BY bl.created_at DESC
        ''')
        rows = cursor.fetchall()
        conn.close()
        return rows_to_dict_list(rows)


class CertificateBatchItemDAO:
    @staticmethod
    def create(batch_log_id, student_id, success, certificate_id=None,
               failure_reason=None):
        now = datetime.now().isoformat()
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute('''
        INSERT INTO certificate_batch_items (
            batch_log_id, student_id, certificate_id, success,
            failure_reason, created_at
        ) VALUES (?, ?, ?, ?, ?, ?)
        ''', (batch_log_id, student_id, certificate_id, 1 if success else 0,
              failure_reason, now))
        conn.commit()
        item_id = cursor.lastrowid
        conn.close()
        return item_id

    @staticmethod
    def get_by_batch_log(batch_log_id):
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute('''
        SELECT bi.*, s.name as student_name, s.employee_id,
               c.certificate_no
        FROM certificate_batch_items bi
        JOIN students s ON bi.student_id = s.id
        LEFT JOIN certificates c ON bi.certificate_id = c.id
        WHERE bi.batch_log_id=?
        ORDER BY bi.id
        ''', (batch_log_id,))
        rows = cursor.fetchall()
        conn.close()
        return rows_to_dict_list(rows)
