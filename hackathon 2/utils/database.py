import sqlite3
from pathlib import Path
from flask import current_app, g

REQUIRED_TABLES = {
    "users",
    "profiles",
    "questions",
    "assessment_attempts",
    "assessment_questions",
    "assessment_answers",
    "spoken_attempts",
    "hr_interviews",
    "hr_answers",
    "recommendations",
    "settings",
}


def _question_type_migration_needed(db):
    row = db.execute(
        "SELECT sql FROM sqlite_master WHERE type='table' AND name='questions'"
    ).fetchone()
    return bool(row and "'hr'" not in (row[0] or "").lower())


def migrate_question_types(db):
    """Expand the existing question type check while retaining every question ID."""
    if not _question_type_migration_needed(db):
        return

    db.execute("PRAGMA foreign_keys = OFF")
    try:
        db.executescript(
            """
            CREATE TABLE questions_new (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                type TEXT NOT NULL CHECK(type IN ('aptitude', 'technical', 'hr', 'spoken')),
                category TEXT NOT NULL,
                topic TEXT NOT NULL,
                difficulty TEXT NOT NULL CHECK(difficulty IN ('easy', 'medium', 'hard')),
                question TEXT NOT NULL UNIQUE,
                option_a TEXT NOT NULL,
                option_b TEXT NOT NULL,
                option_c TEXT NOT NULL,
                option_d TEXT NOT NULL,
                correct_answer TEXT NOT NULL CHECK(correct_answer IN ('A', 'B', 'C', 'D')),
                explanation TEXT,
                marks INTEGER NOT NULL DEFAULT 1,
                time_limit INTEGER NOT NULL DEFAULT 60,
                status TEXT NOT NULL DEFAULT 'draft' CHECK(status IN ('draft', 'published')),
                is_active INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );
            INSERT INTO questions_new
                (id, type, category, topic, difficulty, question, option_a, option_b,
                 option_c, option_d, correct_answer, explanation, marks, time_limit,
                 status, is_active, created_at, updated_at)
            SELECT id, type, category, topic, difficulty, question, option_a, option_b,
                   option_c, option_d, correct_answer, explanation, marks, time_limit,
                   status, is_active, created_at, updated_at
            FROM questions;
            DROP TABLE questions;
            ALTER TABLE questions_new RENAME TO questions;
            """
        )
        db.commit()
    finally:
        db.execute("PRAGMA foreign_keys = ON")


def get_db():
    if "db" not in g:
        db_path = Path(current_app.config["DATABASE"])
        db_path.parent.mkdir(parents=True, exist_ok=True)
        g.db = sqlite3.connect(db_path)
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON")
    return g.db


def close_db(_=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db():
    db_path = Path(current_app.config["DATABASE"])
    schema_path = Path(current_app.root_path) / "database" / "schema.sql"

    db_path.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(db_path)
    try:
        existing_tables = {
            row[0]
            for row in db.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
            ).fetchall()
        }
        if not REQUIRED_TABLES.issubset(existing_tables):
            db.executescript(schema_path.read_text(encoding="utf-8"))
            db.commit()
        migrate_question_types(db)
    finally:
        db.close()


def query(sql, params=(), one=False):
    cur = get_db().execute(sql, params)
    rows = cur.fetchall()
    cur.close()
    return (rows[0] if rows else None) if one else rows


def execute(sql, params=()):
    db = get_db()
    cur = db.execute(sql, params)
    db.commit()
    return cur.lastrowid


def execute_many(sql, seq):
    db = get_db()
    db.executemany(sql, seq)
    db.commit()
