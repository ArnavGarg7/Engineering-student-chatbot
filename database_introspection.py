import sqlite3
import logging
from pathlib import Path

logger = logging.getLogger("database_introspection")

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "engineering_college.db"

_FULL_SCHEMA_CACHE = None

def build_schema_text() -> str:
    """Introspects the SQLite database to build a complete text description of the schema."""
    if not DB_PATH.exists():
        logger.warning(f"Database not found at {DB_PATH}")
        return "Database not found."

    db_uri = DB_PATH.as_uri() + "?mode=ro"
    try:
        conn = sqlite3.connect(db_uri, uri=True)
        cursor = conn.cursor()
        
        # Get all table names
        cursor.execute("SELECT name, sql FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")
        tables = cursor.fetchall()
        
        schema_lines = []
        for table_name, table_sql in tables:
            schema_lines.append(f"Table: {table_name}")
            
            # Pragma table_info
            cursor.execute(f"PRAGMA table_info({table_name})")
            columns = cursor.fetchall()
            col_strings = []
            for col in columns:
                # col = (cid, name, type, notnull, dflt_value, pk)
                col_name = col[1]
                col_type = col[2]
                is_pk = "PRIMARY KEY" if col[5] else ""
                
                parts = [col_name, col_type]
                if is_pk:
                    parts.append(is_pk)
                col_strings.append(" ".join(parts))
            
            schema_lines.append("Columns: " + ", ".join(col_strings))
            
            # Pragma foreign_key_list
            cursor.execute(f"PRAGMA foreign_key_list({table_name})")
            fks = cursor.fetchall()
            for fk in fks:
                # fk = (id, seq, table, from, to, on_update, on_delete, match)
                fk_from = fk[3]
                fk_table = fk[2]
                fk_to = fk[4]
                schema_lines.append(f"Foreign Key: {fk_from} references {fk_table}({fk_to})")
                
            schema_lines.append("") # Empty line between tables
            
        conn.close()
        return "\n".join(schema_lines).strip()
    except Exception as e:
        logger.error(f"Failed to introspect database: {e}")
        return f"Error reading database schema: {e}"

def get_full_schema() -> str:
    """Returns the cached full database schema."""
    global _FULL_SCHEMA_CACHE
    if _FULL_SCHEMA_CACHE is None:
        _FULL_SCHEMA_CACHE = build_schema_text()
    return _FULL_SCHEMA_CACHE
