PRAGMA foreign_keys = ON;

CREATE TABLE departments (
    department_id INTEGER PRIMARY KEY AUTOINCREMENT,
    department_name TEXT NOT NULL UNIQUE,
    department_code TEXT NOT NULL UNIQUE
);

CREATE TABLE students (
    roll_no TEXT PRIMARY KEY,
    student_name TEXT NOT NULL,
    age INTEGER NOT NULL,
    gender TEXT NOT NULL,
    home_city TEXT NOT NULL,
    department_id INTEGER NOT NULL,
    current_year INTEGER NOT NULL CHECK (current_year BETWEEN 1 AND 4),
    current_semester INTEGER NOT NULL CHECK (current_semester BETWEEN 1 AND 8),
    batch_year INTEGER NOT NULL,
    FOREIGN KEY (department_id) REFERENCES departments(department_id)
);

CREATE TABLE subjects (
    subject_id INTEGER PRIMARY KEY AUTOINCREMENT,
    department_id INTEGER NOT NULL,
    semester INTEGER NOT NULL CHECK (semester BETWEEN 1 AND 8),
    subject_code TEXT NOT NULL UNIQUE,
    subject_name TEXT NOT NULL,
    FOREIGN KEY (department_id) REFERENCES departments(department_id)
);

CREATE TABLE marks (
    mark_id INTEGER PRIMARY KEY AUTOINCREMENT,
    roll_no TEXT NOT NULL,
    subject_id INTEGER NOT NULL,
    semester INTEGER NOT NULL CHECK (semester BETWEEN 1 AND 8),
    marks INTEGER NOT NULL CHECK (marks BETWEEN 0 AND 100),
    result TEXT NOT NULL CHECK (result IN ('Pass', 'Fail')),
    FOREIGN KEY (roll_no) REFERENCES students(roll_no),
    FOREIGN KEY (subject_id) REFERENCES subjects(subject_id)
);

CREATE INDEX idx_students_department_year ON students(department_id, current_year);
CREATE INDEX idx_subjects_department_semester ON subjects(department_id, semester);
CREATE INDEX idx_marks_roll_no ON marks(roll_no);
CREATE INDEX idx_marks_subject ON marks(subject_id);
CREATE INDEX idx_marks_semester ON marks(semester);

CREATE TABLE chat_sessions (
    session_id TEXT PRIMARY KEY,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    conversation_summary TEXT
);

CREATE TABLE chat_messages (
    message_id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL,
    role TEXT NOT NULL,
    content TEXT,
    structured_data TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (session_id) REFERENCES chat_sessions(session_id)
);

CREATE INDEX idx_chat_messages_session ON chat_messages(session_id);
