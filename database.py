import json
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
import sqlite3

# SQLite-database lagres i en fil
DATABASE_URL = "sqlite:///./database.db"

# Oppretter en database-motor
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})

# Oppretter en session factory, der autocommit er valget om endringer i
# databasen skal lagres automatisk eller ikke etter en session
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Deklarativ baseklasse for modeller
Base = declarative_base()

def setup_database():
    """
    Oppretter database-tabeller dersom de ikke eksisterer.
    """
    Base.metadata.create_all(bind=engine)


def backup_database_to_json(db_path: str, json_path: str):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Finn alle tabellnavn
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
    tables = cursor.fetchall()

    backup = {}

    for (table_name,) in tables:
        cursor.execute(f"PRAGMA table_info({table_name});")
        columns = [col[1] for col in cursor.fetchall()]

        cursor.execute(f"SELECT * FROM {table_name};")
        rows = cursor.fetchall()

        backup[table_name] = {
            "columns": columns,
            "rows": rows
        }

    with open(json_path, 'w', encoding='utf-8') as f:
        json.dump(backup, f, ensure_ascii=False, indent=4)

    conn.close()


def restore_database_from_json(db_path: str, json_path: str):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    with open(json_path, 'r', encoding='utf-8') as f:
        backup = json.load(f)

    for table_name, data in backup.items():
        columns = data["columns"]
        rows = data["rows"]

        # Slett eksisterende data
        cursor.execute(f"DELETE FROM {table_name}")

        # Sett inn backup-data
        placeholders = ', '.join(['?' for _ in columns])
        cursor.executemany(
            f"INSERT INTO {table_name} ({', '.join(columns)}) VALUES ({placeholders})",
            rows
        )

    conn.commit()
    conn.close()