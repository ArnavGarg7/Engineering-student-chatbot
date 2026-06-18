# Engineering Student Database + AI Query Chatbot

> A project demonstrating database design, FastAPI backend development,
> AI-assisted natural-language querying with Google Gemini, and realistic synthetic
> data generation using the Faker library.

## Overview

This project models a fictional Indian engineering college with **1,280 students**
across **10 departments** and **8 semesters** of academic history.  A chatbot
interface allows users to query the database in plain English — using a robust
**4-layer query resolution pipeline** (AI Intent → Rule-based → Semantic Search → Text-to-SQL).

The project was built as an internship exercise covering:
- Relational database design with SQLite
- RESTful API development with FastAPI
- React + Vite single-page application frontend
- Advanced AI integrations: Multi-turn contextual memory, Provider Failover, and RAG Schema Indexing
- Synthetic data generation with the Faker library (Indian locale)

---

## Features

| Category | Details |
|---|---|
| **Database** | SQLite with 4 normalised tables, indexes, and foreign-key constraints |
| **Students** | 1,280 synthetic student records across 10 departments, 4 academic years |
| **Departments** | 10 engineering branches with unique codes |
| **Subjects** | 32 subjects per department (common foundation + department-specific) |
| **Marks** | Gaussian-modelled marks for all completed semesters; pass/fail status |
| **Academic history** | Full semester-wise marks for any student by roll number |
| **Topper analysis** | Top 10 students per department ranked by average marks |
| **Pass/fail analysis** | Pass and fail counts by department and year |
| **Average analysis** | Average marks by department and by individual subject |
| **4-Layer Query Engine** | Intent Extraction → Keyword Rules → Semantic Similarity → Text-to-SQL |
| **Semantic Search** | Vector embeddings (models/embedding-001) for fuzzy intent matching |
| **Multi-turn Context** | Tracks filters (department, city, gender) across follow-up queries |
| **Multilingual Support** | Automatic translation and routing for Hindi and Spanish queries |
| **Provider Failover** | Auto-fallback between Gemini, Groq, and OpenRouter during outages |
| **RAG Schema Indexing** | Ingests SQL schema into ChromaDB for dynamic context retrieval |
| **Text-to-SQL Guardrail** | Dedicated LLM-based verification to prevent hallucinated WHERE clauses |
| **Abbreviation support** | CSE, ECE, ME, IT, EEE, BT, and more are all recognised |
| **Synthetic data** | Faker (en\_IN locale) generates realistic Indian names and cities |

---

## Technology Stack

### Backend
| Tool | Version | Purpose |
|---|---|---|
| Python | 3.13+ | Application runtime |
| FastAPI | ≥ 0.100 | REST API framework |
| Uvicorn | ≥ 0.22 | ASGI server |
| SQLite | (stdlib) | Embedded relational database |
| python-dotenv | ≥ 1.0 | Load `.env` environment variables |

### Frontend
| Tool | Version | Purpose |
|---|---|---|
| React | 18.2 | UI component library |
| Vite | 5.1 | Build tool and dev server |

### AI & Data
| Tool | Version | Purpose |
|---|---|---|
| Google Gemini API | gemini-1.5-flash | Natural-language intent extraction & primary Text-to-SQL |
| Groq / OpenRouter | - | High-availability fallback LLM providers |
| ChromaDB | ≥ 0.4 | Vector database for RAG schema injection and semantic routing |
| google-genai | ≥ 0.5 | Official Python SDK |

### Data Generation
| Tool | Purpose |
|---|---|
| Faker ≥ 22 (en\_IN locale) | Realistic Indian student names and home cities |

---

## Database Design

### Schema Overview

```
departments
  department_id  PK
  department_name  UNIQUE
  department_code  UNIQUE

students
  roll_no  PK  (format: YYYY-DEPT-NNN)
  student_name
  age
  gender
  home_city
  department_id  FK → departments
  current_year   (1–4)
  current_semester  (1–8)
  batch_year

subjects
  subject_id  PK
  department_id  FK → departments
  semester  (1–8)
  subject_code  UNIQUE
  subject_name

marks
  mark_id  PK
  roll_no  FK → students
  subject_id  FK → subjects
  semester  (1–8)
  marks  (18–100)
  result  ('Pass' | 'Fail')
```

### Relationships

- One **department** has many **students** and many **subjects**.
- One **student** has many **marks** records (one per completed subject).
- One **subject** has many **marks** records (one per student who completed it).
- **Marks** are only inserted for *completed* semesters — the current semester
  is treated as ongoing and has no marks yet.

### Academic Year → Completed Semesters Logic

| Current Year | Current Semester | Completed Semesters |
|:---:|:---:|:---:|
| 1 | 2 | 1 |
| 2 | 4 | 1, 2, 3 |
| 3 | 6 | 1 – 5 |
| 4 | 8 | 1 – 7 |

---

## System Architecture

```
User (browser)
      │
      ▼
React Frontend (Vite, port 5173)
      │  POST /api/query
      ▼
FastAPI Backend (Uvicorn, port 8000)
      │
      ├── query_engine.py (The Orchestrator)
      │   │
      │   ├── 1. ai_service.py (Gemini Intent Extraction)
      │   │      → Matches to 13 predefined intents using LLM prompt.
      │   │
      │   ├── 2. Rule-based Fallback
      │   │      → Matches exact keywords & abbreviations.
      │   │
      │   ├── 3. semantic_engine.py (Vector Embeddings via ChromaDB)
      │   │      → Cosine similarity against pre-embedded example questions.
      │   │
      │   └── 4. text_to_sql.py (RAG-enhanced SQL Generation)
      │          → Retrieves relevant schema chunks from ChromaDB.
      │          → Generates raw SELECT query from DB schema.
      │          → Runs output through an LLM Verification Guardrail to prevent hallucinated filters.
      │          → Validates safety (no DROP/DELETE, adds LIMIT 200).
      │
      ▼
SQLite Database (engineering_college.db)
```

**Resilience**: The system supports automatic provider failover. If the Gemini API rate limits or goes offline, `llm_provider.py` automatically routes requests to Groq or OpenRouter seamlessly.

**Security**: The system is designed to be safe by default. Layers 1-3 never generate SQL; they only map to pre-written, parameterized queries. Layer 4 generates SQL but is strictly validated (must start with SELECT, no mutating keywords, and verified by an independent LLM check) and executed against a read-only database connection.

---

## Synthetic Data Generation

Student demographic data is generated using **Faker (en\_IN locale)** to create
realistic synthetic student records appropriate for an Indian engineering college.

```python
from faker import Faker
fake = Faker("en_IN")
fake.seed_instance(20260603)   # Deterministic — same output every run

name      = fake.name()        # e.g. "Priya Sharma", "Arjun Nair"
home_city = fake.city()        # e.g. "Bengaluru", "Coimbatore"
gender    = fake.random_element(elements=["Male", "Female"])
```

### Why Faker?

| Reason | Detail |
|---|---|
| **Privacy** | Real student data must never be used in demo projects |
| **Locale accuracy** | en\_IN locale produces authentic Indian names and cities |
| **Maintainability** | No hard-coded static lists to update or de-bias |
| **Reproducibility** | Fixed seed → identical database on every run |

### Marks Generation Model

Marks are generated using a Gaussian model to simulate realistic academic performance:

- Each student has a latent *ability* score ~ N(68 + year × 1.5, σ=9)
- Individual subject marks ~ N(ability, σ=11), clamped to [18, 100]
- 8% chance of an academic difficulty event per subject (illness, exam upset)
- Marks ≥ 40 → **Pass**; Marks < 40 → **Fail**

---

## Supported Queries

The chatbot understands a wide range of natural-language questions and abbreviations.

| # | Example Question | Intent |
|---|---|---|
| 1 | "List all engineering departments." | List departments |
| 2 | "What branches are available?" | List departments |
| 3 | "What engineering streams exist?" | List departments |
| 4 | "List all years available." | List academic years |
| 5 | "List all students in Computer Science." | Students by department |
| 6 | "Who studies in CSE?" | Students by department |
| 7 | "Show students enrolled in IT." | Students by department |
| 8 | "Show all 3rd year Mechanical Engineering students." | Students by dept + year |
| 9 | "Show all 2nd year ECE students." | Students by dept + year |
| 10 | "Show 1st year Aerospace Engineering students." | Students by dept + year |
| 11 | "How many students passed in Computer Science, 2nd year?" | Pass/fail counts |
| 12 | "How many students failed in Civil Engineering, 3rd year?" | Pass/fail counts |
| 13 | "Show the list of students with roll numbers in EEE." | Roll number list |
| 14 | "Show full academic history of roll number 2025-CSE-001." | Academic history |
| 15 | "Show subject-wise marks of roll number 2025-CSE-001." | Subject-wise marks |
| 16 | "Show semester-wise performance of roll number 2025-CSE-001." | Semester performance |
| 17 | "Show toppers in Information Technology." | Department toppers |
| 18 | "Who are the top performers in ECE?" | Department toppers |
| 19 | "Best students in Biotechnology?" | Department toppers |
| 20 | "Highest scorers in ME?" | Department toppers |
| 21 | "Show students who failed in more than 2 subjects." | Multi-failure list |
| 22 | "Show backlog students." | Multi-failure list |
| 23 | "Show average marks by department." | Department averages |
| 24 | "Which department has the best academic performance?" | Department averages |
| 25 | "Show average marks by subject." | Subject averages |

*(Plus infinite other possibilities via Text-to-SQL, e.g., "How many students are from Junagadh?")*

### Recognised Abbreviations

| Abbreviation | Resolves To |
|---|---|
| CSE, CS | Computer Science |
| ME, Mech | Mechanical Engineering |
| CE, Civil | Civil Engineering |
| EEE, EE | Electrical Engineering |
| ECE, EC | Electronics & Communication Engineering |
| CHE, Chem | Chemical Engineering |
| BT, Biotech | Biotechnology |
| IT | Information Technology |
| AE, Auto | Automobile Engineering |
| ASE, Aero | Aerospace Engineering |

---

## Installation

### Prerequisites

- Python 3.13+
- Node.js 18+ and npm
- A Google Gemini API key (optional — the chatbot works without it)

### 1. Clone the repository

```bash
git clone <repository-url>
cd "Speed Project"
```

### 2. Install Python dependencies

```bash
py -3.13 -m pip install -r requirements.txt
```

### 3. Configure environment variables

```bash
# Copy the template
copy .env.example .env

# Edit .env and paste your Gemini API key
# GEMINI_API_KEY=AIza...
```

> The `.env` file is listed in `.gitignore` and will never be committed.
> The chatbot works in rule-based-only mode if the key is not set.

### 4. Generate the database

```bash
py -3.13 generate_db.py
```

Output:
```
Created database at ...\engineering_college.db
Students : 1280
Subjects : 320
```

### 5. Install frontend dependencies

```bash
cd frontend
npm install
cd ..
```

---

## Environment Variables

| Variable | Required | Description |
| `GEMINI_API_KEY` | Optional | Google Gemini API key. Used as the primary LLM provider. Get a free key at [aistudio.google.com](https://aistudio.google.com/) |
| `GROQ_API_KEY` | Optional | Groq API key for ultra-fast Llama3 fallback. |
| `OPENROUTER_API_KEY` | Optional | OpenRouter API key for high-availability fallback. |

*Note: The app will work without these, but will gracefully degrade to rule-based queries only.*

---

## Running the Backend

```bash
py -3.13 -m uvicorn app_server:app --reload --port 8000
```

The API will be available at `http://127.0.0.1:8000`.

Interactive API documentation (Swagger UI): `http://127.0.0.1:8000/docs`

### Key endpoints

| Method | Path | Description |
|---|---|---|
| `POST` | `/api/query` | Submit a natural-language question |
| `GET` | `/api/sample_questions` | Fetch example questions for the UI |
| `GET` | `/api/health` | Health check; reports `ai_enabled` status |

---

## Running the Frontend

```bash
cd frontend
npm run dev
```

Open `http://localhost:5173` in your browser.

---

## Running Both Together (Windows)

The project includes a `start.bat` script that launches both servers:

```bash
start.bat
```

---

## Project Structure

```
Speed Project/
├── app_server.py        FastAPI backend — endpoints, logging, CORS
├── query_engine.py      Query routing orchestrator & hard-coded SQL functions
├── ai_service.py        Layer 1: Gemini intent extraction
├── semantic_engine.py   Layer 3: Vector embedding similarity search
├── text_to_sql.py       Layer 4: Gemini SQL generation & validation
├── generate_db.py       Synthetic database generator (Faker)
├── schema.sql           SQLite schema — tables and indexes
├── requirements.txt     Python dependencies
├── .env.example         Environment variable template
├── .gitignore           Excludes .env and generated DB from VCS
├── start.bat            Windows convenience launcher
│
└── frontend/
    ├── index.html       HTML shell
    ├── package.json     Node dependencies (React, Vite)
    └── src/
        ├── main.jsx     React entry point
        ├── App.jsx      Chat UI — input, results table, history
        ├── api.js       Fetch wrapper for backend API calls
        └── styles.css   Application styles
```

---

## Gemini Integration Details

### The 4-Layer Pipeline

1. **AI Intent (gemini-1.5-flash)**: A structured prompt asks Gemini to map the question to one of 13 supported intents.
2. **Rule-Based**: Regular expressions and keyword matching (e.g., `CSE`, `toppers`) route the question locally.
3. **Semantic Similarity (embedding-001)**: The question is embedded and compared via Cosine Similarity against 65 pre-embedded canonical questions. The closest match above `0.75` confidence wins.
4. **Text-to-SQL (gemini-1.5-flash)**: If all else fails, Gemini is given the SQLite schema and asked to write a custom `SELECT` query to answer the question. The SQL is sanitized, capped to 200 rows, and run against a read-only DB connection.

### Example Gemini interaction

**Prompt excerpt:**
```
User: "Which department has the best academic performance?"
Output:
```

**Gemini response:**
```json
{"intent": "average_marks_by_department"}
```

**System action:** calls `average_marks_by_department()` → runs SQL → returns table.

### Setting up the API key

```bash
# On Windows
set GEMINI_API_KEY=AIza...
set GROQ_API_KEY=gsk_...
set OPENROUTER_API_KEY=sk-or-v1-...

# Or add to .env file
GEMINI_API_KEY=AIza...
GROQ_API_KEY=gsk_...
OPENROUTER_API_KEY=sk-or-v1-...
```

---

## Limitations

- **Synthetic academic data** — marks are statistically modelled, not from real students.
- **Text-to-SQL Limitations** — custom generated queries are strictly limited to `SELECT` operations and capped at 200 rows for performance and safety.
- **No authentication** — the API is open; suitable for local development only.
- **No data mutation** — the API is read-only; there is no create/update/delete functionality.

---

## Future Improvements

| Improvement | Description |
|---|---|
| **Analytics dashboard** | Charts and graphs for marks distributions, department comparisons |
| **Export to CSV / PDF** | Download full reports in common office formats |
| **Secure role-based access** | Admin / student / faculty login with JWT authentication |
| **Real-time data entry** | UI for adding students and recording marks |

---

## Internship Objective Fulfillment

| Internship Requirement | How it is Addressed |
|---|---|
| Design a relational database | 4-table normalised SQLite schema with FK constraints and indexes |
| Generate realistic synthetic data | Faker (en\_IN) produces authentic Indian student records |
| Build a query interface | FastAPI REST API with 3 endpoints |
| Implement natural-language querying | Google Gemini intent extraction in `ai_service.py` |
| Ensure query reliability | Rule-based fallback engine guarantees responses even without AI |
| Frontend / full-stack development | React + Vite SPA with CSV export and pagination |
| Code quality | Type hints, docstrings, structured logging, clean architecture |
| Documentation | This README covers all aspects of the project |
