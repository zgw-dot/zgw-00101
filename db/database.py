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

    conn.commit()
    conn.close()
