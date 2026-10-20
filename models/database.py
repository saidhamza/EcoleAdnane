"""
Module de persistance SQLite pour Ecole Adnane.
Gère les cours, métadonnées, fiches de révision, quiz, tentatives et tuteur socratique.
"""

import json
import os
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

DEFAULT_DB_DIR = Path(__file__).parent.parent / "storage"
DEFAULT_DB_PATH = DEFAULT_DB_DIR / "ecole_adnane.db"


def get_db_path() -> Path:
    """Retourne le chemin de la base de données et crée le dossier parent si besoin."""
    db_path_env = os.getenv("DATABASE_PATH")
    path = Path(db_path_env) if db_path_env else DEFAULT_DB_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def get_connection(db_path: Optional[Path] = None) -> sqlite3.Connection:
    """Établit une connexion SQLite avec support pour les dictionnaires de lignes."""
    path = db_path or get_db_path()
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db(db_path: Optional[Path] = None) -> None:
    """Initialise le schéma de base de données SQLite."""
    conn = get_connection(db_path)
    try:
        with conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS courses (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    title TEXT NOT NULL,
                    subject TEXT NOT NULL,
                    language TEXT NOT NULL, -- 'fr' ou 'ar'
                    file_path TEXT NOT NULL,
                    file_hash TEXT UNIQUE NOT NULL,
                    file_name TEXT NOT NULL,
                    raw_text TEXT,
                    summary_markdown TEXT,
                    key_concepts_json TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );

                CREATE TABLE IF NOT EXISTS quizzes (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    course_id INTEGER NOT NULL,
                    quiz_data_json TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (course_id) REFERENCES courses (id) ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS quiz_attempts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    course_id INTEGER NOT NULL,
                    quiz_id INTEGER NOT NULL,
                    score INTEGER NOT NULL,
                    total_questions INTEGER NOT NULL,
                    answers_json TEXT,
                    completed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (course_id) REFERENCES courses (id) ON DELETE CASCADE,
                    FOREIGN KEY (quiz_id) REFERENCES quizzes (id) ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS chat_messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    course_id INTEGER NOT NULL,
                    role TEXT NOT NULL, -- 'user' ou 'assistant'
                    content TEXT NOT NULL,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (course_id) REFERENCES courses (id) ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS settings (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                );

                CREATE INDEX IF NOT EXISTS idx_courses_hash ON courses(file_hash);
                CREATE INDEX IF NOT EXISTS idx_courses_subject ON courses(subject);
                CREATE INDEX IF NOT EXISTS idx_courses_lang ON courses(language);
                CREATE INDEX IF NOT EXISTS idx_quizzes_course ON quizzes(course_id);
                CREATE INDEX IF NOT EXISTS idx_chat_course ON chat_messages(course_id);
            """)
    finally:
        conn.close()


def save_course(
    title: str,
    subject: str,
    language: str,
    file_path: str,
    file_hash: str,
    file_name: str,
    raw_text: str = "",
    summary_markdown: Optional[str] = None,
    key_concepts: Optional[List[str]] = None,
) -> int:
    """Enregistre un nouveau cours ou met à jour un cours existant par son hash."""
    conn = get_connection()
    try:
        with conn:
            cur = conn.cursor()
            cur.execute("SELECT id FROM courses WHERE file_hash = ?", (file_hash,))
            existing = cur.fetchone()

            concepts_json = json.dumps(key_concepts or [], ensure_ascii=False)

            if existing:
                course_id = existing["id"]
                cur.execute(
                    """
                    UPDATE courses
                    SET title = ?, subject = ?, language = ?, file_path = ?,
                        file_name = ?, raw_text = ?, summary_markdown = COALESCE(?, summary_markdown),
                        key_concepts_json = ?, updated_at = CURRENT_TIMESTAMP
                    WHERE id = ?
                    """,
                    (
                        title,
                        subject,
                        language,
                        file_path,
                        file_name,
                        raw_text,
                        summary_markdown,
                        concepts_json,
                        course_id,
                    ),
                )
                return course_id
            else:
                cur.execute(
                    """
                    INSERT INTO courses (title, subject, language, file_path, file_hash, file_name, raw_text, summary_markdown, key_concepts_json)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        title,
                        subject,
                        language,
                        file_path,
                        file_hash,
                        file_name,
                        raw_text,
                        summary_markdown,
                        concepts_json,
                    ),
                )
                return cur.lastrowid
    finally:
        conn.close()


def get_course_by_id(course_id: int) -> Optional[Dict[str, Any]]:
    """Récupère un cours par son ID."""
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("SELECT * FROM courses WHERE id = ?", (course_id,))
        row = cur.fetchone()
        if not row:
            return None
        res = dict(row)
        try:
            res["key_concepts"] = json.loads(res.get("key_concepts_json") or "[]")
        except Exception:
            res["key_concepts"] = []
        return res
    finally:
        conn.close()


def get_course_by_hash(file_hash: str) -> Optional[Dict[str, Any]]:
    """Récupère un cours par son hash SHA-256."""
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("SELECT * FROM courses WHERE file_hash = ?", (file_hash,))
        row = cur.fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def list_courses(subject: Optional[str] = None, language: Optional[str] = None) -> List[Dict[str, Any]]:
    """Liste tous les cours avec filtrage facultatif par matière et/ou langue."""
    conn = get_connection()
    try:
        cur = conn.cursor()
        query = "SELECT * FROM courses WHERE 1=1"
        params: List[Any] = []

        if subject and subject != "Toutes":
            query += " AND subject = ?"
            params.append(subject)

        if language and language != "Toutes":
            query += " AND language = ?"
            params.append(language)

        query += " ORDER BY updated_at DESC, id DESC"
        cur.execute(query, params)
        rows = cur.fetchall()

        result = []
        for row in rows:
            d = dict(row)
            try:
                d["key_concepts"] = json.loads(d.get("key_concepts_json") or "[]")
            except Exception:
                d["key_concepts"] = []
            result.append(d)
        return result
    finally:
        conn.close()


def update_course_summary(course_id: int, summary_markdown: str, key_concepts: Optional[List[str]] = None) -> None:
    """Met à jour la fiche express d'un cours."""
    conn = get_connection()
    try:
        with conn:
            cur = conn.cursor()
            if key_concepts is not None:
                cur.execute(
                    """
                    UPDATE courses
                    SET summary_markdown = ?, key_concepts_json = ?, updated_at = CURRENT_TIMESTAMP
                    WHERE id = ?
                    """,
                    (summary_markdown, json.dumps(key_concepts, ensure_ascii=False), course_id),
                )
            else:
                cur.execute(
                    """
                    UPDATE courses
                    SET summary_markdown = ?, updated_at = CURRENT_TIMESTAMP
                    WHERE id = ?
                    """,
                    (summary_markdown, course_id),
                )
    finally:
        conn.close()


def update_course_metadata(course_id: int, title: str, subject: str, language: str) -> None:
    """Met à jour les métadonnées d'un cours."""
    conn = get_connection()
    try:
        with conn:
            cur = conn.cursor()
            cur.execute(
                """
                UPDATE courses
                SET title = ?, subject = ?, language = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (title, subject, language, course_id),
            )
    finally:
        conn.close()


def delete_course(course_id: int) -> bool:
    """Supprime un cours et ses dépendances en cascade."""
    conn = get_connection()
    try:
        with conn:
            cur = conn.cursor()
            cur.execute("SELECT file_path FROM courses WHERE id = ?", (course_id,))
            row = cur.fetchone()
            if row and row["file_path"] and os.path.exists(row["file_path"]):
                try:
                    os.remove(row["file_path"])
                except Exception:
                    pass
            cur.execute("DELETE FROM courses WHERE id = ?", (course_id,))
            return cur.rowcount > 0
    finally:
        conn.close()


def save_quiz(course_id: int, quiz_data: List[Dict[str, Any]]) -> int:
    """Enregistre un quiz associé à un cours."""
    conn = get_connection()
    try:
        with conn:
            cur = conn.cursor()
            cur.execute(
                "INSERT INTO quizzes (course_id, quiz_data_json) VALUES (?, ?)",
                (course_id, json.dumps(quiz_data, ensure_ascii=False)),
            )
            return cur.lastrowid
    finally:
        conn.close()


def get_latest_quiz(course_id: int) -> Optional[Dict[str, Any]]:
    """Récupère le dernier quiz généré pour un cours."""
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT * FROM quizzes WHERE course_id = ? ORDER BY id DESC LIMIT 1",
            (course_id,),
        )
        row = cur.fetchone()
        if not row:
            return None
        res = dict(row)
        try:
            res["questions"] = json.loads(res.get("quiz_data_json") or "[]")
        except Exception:
            res["questions"] = []
        return res
    finally:
        conn.close()


def save_quiz_attempt(
    course_id: int,
    quiz_id: int,
    score: int,
    total_questions: int,
    answers: Dict[str, Any],
) -> int:
    """Enregistre le résultat d'une tentative de quiz de l'élève."""
    conn = get_connection()
    try:
        with conn:
            cur = conn.cursor()
            cur.execute(
                """
                INSERT INTO quiz_attempts (course_id, quiz_id, score, total_questions, answers_json)
                VALUES (?, ?, ?, ?, ?)
                """,
                (course_id, quiz_id, score, total_questions, json.dumps(answers, ensure_ascii=False)),
            )
            return cur.lastrowid
    finally:
        conn.close()


def get_quiz_stats() -> Dict[str, Any]:
    """Calcule les statistiques globales de révision et progrès par matière."""
    conn = get_connection()
    try:
        cur = conn.cursor()
        # Stats globales
        cur.execute("""
            SELECT 
                COUNT(*) as total_attempts,
                COALESCE(SUM(score), 0) as total_score,
                COALESCE(SUM(total_questions), 0) as total_questions
            FROM quiz_attempts
        """)
        global_row = dict(cur.fetchone() or {})
        total_questions = global_row.get("total_questions", 0)
        total_score = global_row.get("total_score", 0)
        avg_rate = (total_score / total_questions * 100) if total_questions > 0 else 0

        # Stats par matière
        cur.execute("""
            SELECT 
                c.subject,
                c.language,
                COUNT(qa.id) as attempts,
                COALESCE(SUM(qa.score), 0) as subject_score,
                COALESCE(SUM(qa.total_questions), 0) as subject_questions
            FROM courses c
            JOIN quiz_attempts qa ON c.id = qa.course_id
            GROUP BY c.subject, c.language
            ORDER BY attempts DESC
        """)
        by_subject = []
        for r in cur.fetchall():
            d = dict(r)
            sq = d.get("subject_questions", 0)
            ss = d.get("subject_score", 0)
            d["success_rate"] = round((ss / sq * 100), 1) if sq > 0 else 0
            by_subject.append(d)

        # Dernières tentatives
        cur.execute("""
            SELECT 
                qa.id,
                qa.score,
                qa.total_questions,
                qa.completed_at,
                c.title as course_title,
                c.subject,
                c.language
            FROM quiz_attempts qa
            JOIN courses c ON qa.course_id = c.id
            ORDER BY qa.completed_at DESC
            LIMIT 10
        """)
        recent_attempts = [dict(r) for r in cur.fetchall()]

        return {
            "total_attempts": global_row.get("total_attempts", 0),
            "total_score": total_score,
            "total_questions": total_questions,
            "average_success_rate": round(avg_rate, 1),
            "by_subject": by_subject,
            "recent_attempts": recent_attempts,
        }
    finally:
        conn.close()


def get_chat_history(course_id: int, limit: int = 50) -> List[Dict[str, str]]:
    """Récupère l'historique de discussion avec le tuteur pour un cours."""
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT role, content, timestamp
            FROM chat_messages
            WHERE course_id = ?
            ORDER BY id ASC
            LIMIT ?
            """,
            (course_id, limit),
        )
        return [{"role": r["role"], "content": r["content"], "timestamp": r["timestamp"]} for r in cur.fetchall()]
    finally:
        conn.close()


def add_chat_message(course_id: int, role: str, content: str) -> None:
    """Ajoute un message dans l'historique du tuteur."""
    conn = get_connection()
    try:
        with conn:
            cur = conn.cursor()
            cur.execute(
                "INSERT INTO chat_messages (course_id, role, content) VALUES (?, ?, ?)",
                (course_id, role, content),
            )
    finally:
        conn.close()


def clear_chat_history(course_id: int) -> None:
    """Efface l'historique de discussion d'un cours."""
    conn = get_connection()
    try:
        with conn:
            cur = conn.cursor()
            cur.execute("DELETE FROM chat_messages WHERE course_id = ?", (course_id,))
    finally:
        conn.close()


def get_setting(key: str, default: Optional[str] = None) -> Optional[str]:
    """Lit un paramètre stocké dans la base."""
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("SELECT value FROM settings WHERE key = ?", (key,))
        row = cur.fetchone()
        return row["value"] if row else default
    finally:
        conn.close()


def set_setting(key: str, value: str) -> None:
    """Enregistre ou met à jour un paramètre."""
    conn = get_connection()
    try:
        with conn:
            cur = conn.cursor()
            cur.execute(
                """
                INSERT INTO settings (key, value) VALUES (?, ?)
                ON CONFLICT(key) DO UPDATE SET value = excluded.value
                """,
                (key, value),
            )
    finally:
        conn.close()
