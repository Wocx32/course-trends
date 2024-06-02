import sqlite3


def create_db():
    conn = sqlite3.connect('db/seats.db')
    c = conn.cursor()

    c.execute('pragma foreign_keys=ON')

    c.execute('''
        CREATE TABLE IF NOT EXISTS course (
            term TEXT NOT NULL,
            course_code TEXT NOT NULL,
            course_section TEXT NOT NULL,
            total_seats INTEGER NOT NULL,
            PRIMARY KEY(term, course_code, course_section)
        )
    ''')

    c.execute('''
        CREATE TABLE IF NOT EXISTS seat (
            term TEXT NOT NULL,
            course_code TEXT NOT NULL,
            course_section TEXT NOT NULL,
            ts TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            available_seats INTEGER NOT NULL,
            PRIMARY KEY(term, course_code, course_section, ts),
            FOREIGN KEY(term, course_code, course_section) REFERENCES course(term, course_code, course_section)
        )
    ''')

    c.execute('''
        CREATE TABLE IF NOT EXISTS course_update (
            term TEXT NOT NULL,
            course_code TEXT NOT NULL,
            course_section TEXT NOT NULL,
            ts TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY(term, course_code, course_section),
            FOREIGN KEY(term, course_code, course_section) REFERENCES course(term, course_code, course_section)
        )
    ''')

    c.execute('''
        CREATE INDEX IF NOT EXISTS idx_course ON course(course_code, course_section)
    ''')

    conn.commit()
    conn.close()

create_db()