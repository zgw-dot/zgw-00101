import sqlite3
import os
from datetime import datetime

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'training.db')

def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn

def init_database():
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute('''
    CREATE TABLE IF NOT EXISTS courses (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT NOT NULL,
        theme TEXT NOT NULL,
        description TEXT,
        instructor TEXT NOT NULL,
        venue TEXT NOT NULL,
        start_time TEXT NOT NULL,
        end_time TEXT NOT NULL,
        capacity INTEGER NOT NULL DEFAULT 30,
        registration_deadline TEXT NOT NULL,
        status TEXT NOT NULL DEFAULT 'draft',
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL
    )
    ''')

    cursor.execute('''
    CREATE TABLE IF NOT EXISTS students (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        employee_id TEXT UNIQUE NOT NULL,
        department TEXT,
        phone TEXT,
        email TEXT,
        created_at TEXT NOT NULL
    )
    ''')

    cursor.execute('''
    CREATE TABLE IF NOT EXISTS registrations (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        course_id INTEGER NOT NULL,
        student_id INTEGER NOT NULL,
        status TEXT NOT NULL DEFAULT 'registered',
        registered_at TEXT NOT NULL,
        FOREIGN KEY (course_id) REFERENCES courses(id) ON DELETE CASCADE,
        FOREIGN KEY (student_id) REFERENCES students(id) ON DELETE CASCADE,
        UNIQUE(course_id, student_id)
    )
    ''')

    cursor.execute('''
    CREATE TABLE IF NOT EXISTS transfer_requests (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        registration_id INTEGER NOT NULL,
        from_course_id INTEGER NOT NULL,
        to_course_id INTEGER NOT NULL,
        reason TEXT,
        status TEXT NOT NULL DEFAULT 'pending',
        requested_at TEXT NOT NULL,
        reviewed_at TEXT,
        review_note TEXT,
        FOREIGN KEY (registration_id) REFERENCES registrations(id) ON DELETE CASCADE,
        FOREIGN KEY (from_course_id) REFERENCES courses(id) ON DELETE CASCADE,
        FOREIGN KEY (to_course_id) REFERENCES courses(id) ON DELETE CASCADE
    )
    ''')

    cursor.execute('''
    CREATE TABLE IF NOT EXISTS attendances (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        course_id INTEGER NOT NULL,
        student_id INTEGER NOT NULL,
        check_in_time TEXT,
        status TEXT NOT NULL DEFAULT 'pending',
        is_makeup INTEGER NOT NULL DEFAULT 0,
        makeup_reason TEXT,
        makeup_requested_at TEXT,
        makeup_reviewed_at TEXT,
        makeup_reviewer TEXT,
        makeup_status TEXT DEFAULT 'none',
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL,
        FOREIGN KEY (course_id) REFERENCES courses(id) ON DELETE CASCADE,
        FOREIGN KEY (student_id) REFERENCES students(id) ON DELETE CASCADE,
        UNIQUE(course_id, student_id)
    )
    ''')

    cursor.execute('''
    CREATE TABLE IF NOT EXISTS exception_logs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        course_id INTEGER,
        student_id INTEGER,
        type TEXT NOT NULL,
        description TEXT NOT NULL,
        handled INTEGER NOT NULL DEFAULT 0,
        handled_at TEXT,
        handled_by TEXT,
        created_at TEXT NOT NULL,
        FOREIGN KEY (course_id) REFERENCES courses(id) ON DELETE SET NULL,
        FOREIGN KEY (student_id) REFERENCES students(id) ON DELETE SET NULL
    )
    ''')

    cursor.execute('''
    CREATE TABLE IF NOT EXISTS batch_operation_logs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        operation_type TEXT NOT NULL,
        from_course_id INTEGER,
        to_course_id INTEGER,
        target_status TEXT,
        total_count INTEGER NOT NULL,
        success_count INTEGER NOT NULL,
        failure_count INTEGER NOT NULL,
        operated_by TEXT DEFAULT '管理员',
        created_at TEXT NOT NULL,
        undone INTEGER NOT NULL DEFAULT 0,
        undone_at TEXT,
        FOREIGN KEY (from_course_id) REFERENCES courses(id) ON DELETE SET NULL,
        FOREIGN KEY (to_course_id) REFERENCES courses(id) ON DELETE SET NULL
    )
    ''')

    cursor.execute('''
    CREATE TABLE IF NOT EXISTS batch_operation_items (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        batch_log_id INTEGER NOT NULL,
        registration_id INTEGER,
        student_id INTEGER NOT NULL,
        from_course_id INTEGER,
        to_course_id INTEGER,
        old_status TEXT NOT NULL,
        new_status TEXT NOT NULL,
        success INTEGER NOT NULL,
        failure_reason TEXT,
        undo_data TEXT,
        created_at TEXT NOT NULL,
        FOREIGN KEY (batch_log_id) REFERENCES batch_operation_logs(id) ON DELETE CASCADE,
        FOREIGN KEY (registration_id) REFERENCES registrations(id) ON DELETE SET NULL,
        FOREIGN KEY (student_id) REFERENCES students(id) ON DELETE CASCADE
    )
    ''')

    cursor.execute('''
    CREATE TABLE IF NOT EXISTS waiting_list (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        course_id INTEGER NOT NULL,
        student_id INTEGER NOT NULL,
        priority INTEGER NOT NULL DEFAULT 0,
        source TEXT NOT NULL DEFAULT 'manual',
        status TEXT NOT NULL DEFAULT 'waiting',
        added_at TEXT NOT NULL,
        processed_at TEXT,
        note TEXT,
        FOREIGN KEY (course_id) REFERENCES courses(id) ON DELETE CASCADE,
        FOREIGN KEY (student_id) REFERENCES students(id) ON DELETE CASCADE,
        UNIQUE(course_id, student_id, status)
    )
    ''')

    cursor.execute('''
    CREATE TABLE IF NOT EXISTS waiting_list_results (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        course_id INTEGER NOT NULL,
        waiting_list_id INTEGER,
        student_id INTEGER NOT NULL,
        original_position INTEGER,
        priority INTEGER,
        source TEXT,
        result TEXT NOT NULL,
        failure_reason TEXT,
        registration_id INTEGER,
        processed_at TEXT NOT NULL,
        FOREIGN KEY (course_id) REFERENCES courses(id) ON DELETE CASCADE,
        FOREIGN KEY (waiting_list_id) REFERENCES waiting_list(id) ON DELETE SET NULL,
        FOREIGN KEY (student_id) REFERENCES students(id) ON DELETE CASCADE,
        FOREIGN KEY (registration_id) REFERENCES registrations(id) ON DELETE SET NULL
    )
    ''')

    cursor.execute('''
    CREATE TABLE IF NOT EXISTS certificates (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        certificate_no TEXT UNIQUE NOT NULL,
        course_id INTEGER NOT NULL,
        student_id INTEGER NOT NULL,
        registration_id INTEGER,
        status TEXT NOT NULL DEFAULT 'issued',
        issue_date TEXT NOT NULL,
        generated_at TEXT NOT NULL,
        voided_at TEXT,
        void_reason TEXT,
        remark TEXT,
        operated_by TEXT DEFAULT '管理员',
        FOREIGN KEY (course_id) REFERENCES courses(id) ON DELETE CASCADE,
        FOREIGN KEY (student_id) REFERENCES students(id) ON DELETE CASCADE,
        FOREIGN KEY (registration_id) REFERENCES registrations(id) ON DELETE SET NULL
    )
    ''')

    cursor.execute('''
    CREATE TABLE IF NOT EXISTS certificate_batch_logs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        course_id INTEGER NOT NULL,
        operation_type TEXT NOT NULL,
        total_count INTEGER NOT NULL,
        success_count INTEGER NOT NULL,
        failure_count INTEGER NOT NULL,
        operated_by TEXT DEFAULT '管理员',
        created_at TEXT NOT NULL,
        FOREIGN KEY (course_id) REFERENCES courses(id) ON DELETE CASCADE
    )
    ''')

    cursor.execute('''
    CREATE TABLE IF NOT EXISTS certificate_batch_items (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        batch_log_id INTEGER NOT NULL,
        student_id INTEGER NOT NULL,
        certificate_id INTEGER,
        success INTEGER NOT NULL,
        failure_reason TEXT,
        created_at TEXT NOT NULL,
        FOREIGN KEY (batch_log_id) REFERENCES certificate_batch_logs(id) ON DELETE CASCADE,
        FOREIGN KEY (student_id) REFERENCES students(id) ON DELETE CASCADE,
        FOREIGN KEY (certificate_id) REFERENCES certificates(id) ON DELETE SET NULL
    )
    ''')

    conn.commit()
    conn.close()
