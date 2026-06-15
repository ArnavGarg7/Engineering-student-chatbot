import random
import sqlite3
from pathlib import Path

from faker import Faker

from query_engine import DB_PATH


BASE_DIR = Path(__file__).resolve().parent
SCHEMA_PATH = BASE_DIR / "schema.sql"

DEPARTMENTS: list[tuple[str, str]] = [
    ("Computer Science", "CSE"),
    ("Mechanical Engineering", "ME"),
    ("Civil Engineering", "CE"),
    ("Electrical Engineering", "EEE"),
    ("Electronics & Communication Engineering", "ECE"),
    ("Chemical Engineering", "CHE"),
    ("Biotechnology", "BT"),
    ("Information Technology", "IT"),
    ("Automobile Engineering", "AE"),
    ("Aerospace Engineering", "ASE"),
]


# Semesters 1 and 2 are common to all departments (foundation courses).
COMMON_SUBJECTS: dict[int, list[str]] = {
    1: ["Engineering Mathematics I", "Engineering Physics", "Basic Electrical Engineering", "Programming Fundamentals"],
    2: ["Engineering Mathematics II", "Engineering Chemistry", "Engineering Mechanics", "Data Structures and Algorithms"],
}

# Semesters 3–8 are department-specific.
CURRICULUM: dict[str, dict[int, list[str]]] = {
    "Computer Science": {
        3: ["Object Oriented Programming", "Digital Logic Design", "Database Systems", "Problem Solving Laboratory"],
        4: ["Operating Systems", "Computer Networks", "Discrete Mathematics", "Software Engineering"],
        5: ["Web Technologies", "Microprocessors and Interfacing", "Theory of Computation", "DBMS Lab"],
        6: ["Machine Learning", "Distributed Systems", "Cloud Computing", "Artificial Intelligence"],
        7: ["Cyber Security", "Big Data Analytics", "Compiler Design", "Internet of Things"],
        8: ["Capstone Project", "DevOps", "Full Stack Development", "Data Engineering"],
    },
    "Mechanical Engineering": {
        3: ["Engineering Thermodynamics", "Strength of Materials", "Manufacturing Processes", "Mechanics of Solids"],
        4: ["Fluid Mechanics", "Material Science", "Machine Drawing", "Kinematics of Machinery"],
        5: ["Heat Transfer", "Machine Design", "Theory of Machines", "CAD/CAM"],
        6: ["Automobile Engineering", "Industrial Engineering", "Finite Element Analysis", "HVAC Systems"],
        7: ["CNC and Automation", "Mechatronics", "Energy Systems", "Robotics"],
        8: ["Capstone Project", "Renewable Energy Systems", "Advanced Manufacturing", "Maintenance Engineering"],
    },
    "Civil Engineering": {
        3: ["Surveying", "Engineering Geology", "Strength of Materials", "Building Materials"],
        4: ["Structural Analysis", "Fluid Mechanics", "Concrete Technology", "Geotechnical Engineering"],
        5: ["RCC Design", "Transportation Engineering", "Environmental Engineering", "Construction Planning"],
        6: ["Steel Structures", "Hydraulic Structures", "Soil Dynamics", "Project Management"],
        7: ["Earthquake Engineering", "Smart Cities", "Foundation Engineering", "Water Resources Engineering"],
        8: ["Capstone Project", "High Rise Structures", "Green Building Design", "Advanced Surveying"],
    },
    "Electrical Engineering": {
        3: ["Circuit Theory", "Electromagnetic Fields", "Electrical Machines I", "Analog Electronics"],
        4: ["Power Systems I", "Electrical Measurements", "Control Systems", "Signals and Systems"],
        5: ["Electrical Machines II", "Power Electronics", "Microprocessors", "Network Theory"],
        6: ["Power Systems II", "Renewable Energy Systems", "Instrumentation", "Digital Control"],
        7: ["High Voltage Engineering", "Smart Grids", "Electrical Drives", "Power Quality"],
        8: ["Capstone Project", "Protection Systems", "Industrial Automation", "Energy Management"],
    },
    "Electronics & Communication Engineering": {
        3: ["Network Theory", "Electronic Devices", "Digital Electronics", "Signals and Systems"],
        4: ["Analog Communication", "Microprocessors", "Electromagnetic Waves", "Linear Integrated Circuits"],
        5: ["Digital Communication", "VLSI Design", "Control Systems", "Embedded Systems"],
        6: ["Antenna Theory", "DSP", "Wireless Communication", "CMOS Design"],
        7: ["Microwave Engineering", "IoT Systems", "Optical Communication", "FPGA Design"],
        8: ["Capstone Project", "5G Systems", "Radar Engineering", "Advanced Embedded Applications"],
    },
    "Chemical Engineering": {
        3: ["Chemical Process Principles", "Thermodynamics", "Fluid Mechanics", "Material and Energy Balances"],
        4: ["Heat Transfer", "Mass Transfer", "Chemical Reaction Engineering", "Process Calculations"],
        5: ["Mechanical Operations", "Process Instrumentation", "Separation Processes", "Transport Phenomena"],
        6: ["Process Control", "Chemical Engineering Thermodynamics", "Reaction Kinetics", "Plant Design"],
        7: ["Environmental Engineering", "Petrochemical Processes", "Process Dynamics", "Safety Engineering"],
        8: ["Capstone Project", "Biochemical Engineering", "Process Simulation", "Industrial Pollution Control"],
    },
    "Biotechnology": {
        3: ["Cell Biology", "Biochemistry", "Microbiology", "Genetics"],
        4: ["Molecular Biology", "Immunology", "Biostatistics", "Bioinformatics"],
        5: ["Genetic Engineering", "Downstream Processing", "Bioprocess Engineering", "Enzyme Technology"],
        6: ["Plant Biotechnology", "Animal Cell Culture", "Fermentation Technology", "Bioinstrumentation"],
        7: ["Industrial Biotechnology", "Nanobiotechnology", "Computational Biology", "Systems Biology"],
        8: ["Capstone Project", "Clinical Biotechnology", "Regulatory Affairs", "Omics Technologies"],
    },
    "Information Technology": {
        3: ["Object Oriented Programming", "Database Systems", "Web Technologies", "Data Structures"],
        4: ["Operating Systems", "Computer Networks", "Software Engineering", "Algorithms"],
        5: ["Java Programming", "Mobile Computing", "Cloud Fundamentals", "DBMS Lab"],
        6: ["Machine Learning", "Cyber Security", "Distributed Systems", "Human Computer Interaction"],
        7: ["Big Data Analytics", "DevOps", "Internet of Things", "Blockchain Technology"],
        8: ["Capstone Project", "Full Stack Engineering", "API Development", "Data Visualization"],
    },
    "Automobile Engineering": {
        3: ["Automotive Engines", "Vehicle Dynamics", "Thermodynamics", "Manufacturing Technology"],
        4: ["Chassis Systems", "Transmission Systems", "Fluid Mechanics", "Material Science"],
        5: ["Automobile Electronics", "Alternate Fuels", "Vehicle Design", "Machine Tools"],
        6: ["EV Technology", "Suspension and Steering", "CAD/CAM", "Heat Transfer"],
        7: ["Vehicle Testing", "Hybrid Vehicles", "Automotive Control Systems", "Noise and Vibration"],
        8: ["Capstone Project", "Powertrain Engineering", "Advanced Vehicle Design", "Maintenance Practices"],
    },
    "Aerospace Engineering": {
        3: ["Aerodynamics", "Aircraft Materials", "Engineering Thermodynamics", "Fluid Mechanics"],
        4: ["Flight Mechanics", "Aircraft Propulsion", "Strength of Materials", "Aircraft Structures"],
        5: ["Aerospace Propulsion", "Avionics", "Computational Fluid Dynamics", "Rocketry Basics"],
        6: ["Space Mission Analysis", "Control Systems", "Gas Dynamics", "Composite Materials"],
        7: ["Flight Vehicle Design", "Satellite Systems", "Navigation and Guidance", "Aircraft Stability"],
        8: ["Capstone Project", "UAV Systems", "Advanced Propulsion", "Space Technology"],
    },
}

fake: Faker = Faker("en_IN")
fake.seed_instance(20260603)



def read_schema() -> str:
    """Read and return the SQL schema file contents."""
    return SCHEMA_PATH.read_text(encoding="utf-8")


def build_subject_plan(
    department_name: str,
    department_code: str,
) -> list[tuple[str, int, str, str]]:
    """
    Build the full list of (department_name, semester, subject_code, subject_name)
    rows for a single department across all 8 semesters.
    """
    rows: list[tuple[str, int, str, str]] = []
    counter = 1

    # Semesters 1–2: common foundation subjects
    for semester, subjects in COMMON_SUBJECTS.items():
        for subject_name in subjects:
            subject_code = f"{department_code}-S{semester}-{counter:02d}"
            rows.append((department_name, semester, subject_code, subject_name))
            counter += 1

    # Semesters 3–8: department-specific subjects
    for semester in range(3, 9):
        for subject_name in CURRICULUM[department_name][semester]:
            subject_code = f"{department_code}-S{semester}-{counter:02d}"
            rows.append((department_name, semester, subject_code, subject_name))
            counter += 1

    return rows


def generate_name() -> str:
    """
    Generate a realistic full student name using Faker (en_IN locale).
    Faker is seeded globally so repeated calls produce a deterministic sequence.
    """
    return fake.name()


def build_student_records(
    department_name: str,
    department_code: str,
    department_id: int,
) -> list[tuple[str, str, int, str, str, int, int, int, int]]:
    """
    Generate 128 synthetic student records (32 per academic year) for a
    single department.

    Demographic fields are produced entirely by Faker:
      • Name      → fake.name()          (en_IN locale: realistic Indian names)
      • Home city → fake.city()          (en_IN locale: Indian city names)
      • Gender    → fake.random_element  (balanced Male / Female selection)

    Age is derived from year of study with a small variation for realism.
    """
    records: list[tuple[str, str, int, str, str, int, int, int, int]] = []
    students_per_year = 32
    sequence = 1

    for current_year in range(1, 5):
        batch_year = 2026 - current_year
        current_semester = current_year * 2

        for local_index in range(students_per_year):
            global_index = (department_id - 1) * 128 + (current_year - 1) * students_per_year + local_index
            roll_no = f"{batch_year}-{department_code}-{sequence:03d}"

            # All demographic data generated by Faker — no hard-coded lists needed.
            name = generate_name()
            age = 17 + current_year + (global_index % 2)  # 18–21 range with minor variation
            gender: str = fake.random_element(elements=["Male", "Female"])
            home_city: str = fake.city()

            records.append((
                roll_no, name, age, gender, home_city,
                department_id, current_year, current_semester, batch_year,
            ))
            sequence += 1

    return records

def create_database() -> None:
    """
    Create the SQLite database from scratch.

    Steps:
    1. Delete any existing database file.
    2. Apply the schema (tables + indexes).
    3. Insert departments.
    4. Insert subjects (common + department-specific).
    5. Insert students (Faker-generated demographics).
    6. Generate and insert marks using a Gaussian model:
         - Each student has a base ability score ~ N(68 + year*1.5, 9).
         - Subject scores ~ N(ability, 11), clamped to [18, 100].
         - 8% chance of a subject-level penalty (simulates academic difficulty).
         - Marks ≥ 40 → Pass; Marks < 40 → Fail.
    """
    # Seed Python's random module independently of Faker so that marks
    # generation is also deterministic and reproducible.
    random.seed(20260603)

    if DB_PATH.exists():
        DB_PATH.unlink()

    schema = read_schema()
    connection = sqlite3.connect(DB_PATH)
    connection.execute("PRAGMA foreign_keys = ON")
    connection.executescript(schema)

    # ── Departments ──────────────────────────────────────────────────────────
    connection.executemany(
        "INSERT INTO departments (department_name, department_code) VALUES (?, ?)",
        DEPARTMENTS,
    )
    connection.commit()

    department_lookup: dict[str, int] = {
        row[1]: row[0]
        for row in connection.execute("SELECT department_id, department_name FROM departments")
    }

    # ── Subjects ─────────────────────────────────────────────────────────────
    subject_rows: list[tuple[str, int, str, str]] = []
    for department_name, department_code in DEPARTMENTS:
        subject_rows.extend(build_subject_plan(department_name, department_code))

    connection.executemany(
        "INSERT INTO subjects (department_id, semester, subject_code, subject_name) VALUES (?, ?, ?, ?)",
        [
            (department_lookup[department_name], semester, subject_code, subject_name)
            for department_name, semester, subject_code, subject_name in subject_rows
        ],
    )
    connection.commit()

    # ── Students ─────────────────────────────────────────────────────────────
    student_rows: list[tuple[str, str, int, str, str, int, int, int, int]] = []
    for department_name, department_code in DEPARTMENTS:
        student_rows.extend(
            build_student_records(department_name, department_code, department_lookup[department_name])
        )

    connection.executemany(
        """
        INSERT INTO students (
            roll_no, student_name, age, gender, home_city,
            department_id, current_year, current_semester, batch_year
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        student_rows,
    )
    connection.commit()

    # ── Marks ────────────────────────────────────────────────────────────────
    # Build a lookup: department_id → {semester → [subject_ids]}
    subject_map: dict[int, tuple[int, int]] = {
        row[0]: (row[1], row[2])
        for row in connection.execute("SELECT subject_id, department_id, semester FROM subjects")
    }
    dept_subjects: dict[int, dict[int, list[int]]] = {}
    for subject_id, (department_id, semester) in subject_map.items():
        dept_subjects.setdefault(department_id, {}).setdefault(semester, []).append(subject_id)

    marks_rows: list[tuple[str, int, int, int, str]] = []
    student_rows_db = list(
        connection.execute("SELECT roll_no, department_id, current_year FROM students ORDER BY roll_no")
    )

    for student in student_rows_db:
        roll_no: str = student[0]
        department_id: int = student[1]
        current_year: int = student[2]

        # Only completed semesters have marks; the current semester is ongoing.
        completed_semesters = 2 * current_year - 1

        # Each student has a latent ability score that influences all subject marks.
        ability = random.gauss(68 + current_year * 1.5, 9)

        for semester in range(1, completed_semesters + 1):
            for subject_id in dept_subjects[department_id][semester]:
                score = random.gauss(ability, 11)
                # 8% chance of an academic difficulty event (illness, exam upset, etc.)
                if random.random() < 0.08:
                    score -= random.uniform(18, 34)
                score = max(18, min(100, int(round(score))))
                result = "Pass" if score >= 40 else "Fail"
                marks_rows.append((roll_no, subject_id, semester, score, result))

    connection.executemany(
        "INSERT INTO marks (roll_no, subject_id, semester, marks, result) VALUES (?, ?, ?, ?, ?)",
        marks_rows,
    )
    connection.commit()
    connection.close()


if __name__ == "__main__":
    create_database()
    print(f"Created database at {DB_PATH}")
    print("Students : 1280")
    print("Subjects : 320")
