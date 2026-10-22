"""
Module de persistance SQLite pour Ecole Adnane.
Gère les utilisateurs, rôles (Admin/Student), paramètres individuels,
cours cloisonnés, fiches de révision, quiz, tentatives et tuteur socratique.
"""

import json
import logging
import os
import re
import secrets
import shutil
import sqlite3
import unicodedata
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

__all__ = [
    "get_db_path",
    "get_connection",
    "init_db",
    "get_user_count",
    "get_user_by_id",
    "get_user_by_email",
    "create_or_get_google_user",
    "list_users",
    "set_user_blocked_status",
    "update_user_role",
    "delete_user_account",
    "update_user_name",
    "MOROCCAN_SCHOOL_LEVELS",
    "get_pedagogical_cycle",
    "update_user_age",
    "update_user_level",
    "create_user_session",
    "get_user_from_session_token",
    "delete_user_session",
    "cleanup_expired_sessions",
    "get_global_admin_kpis",
    "save_course",
    "list_courses",
    "get_course_by_id",
    "get_course_by_hash",
    "update_course_metadata",
    "update_course_summary",
    "delete_course",
    "save_flashcard",
    "save_quiz",
    "get_latest_quiz",
    "save_quiz_attempt",
    "get_quiz_stats",
    "add_chat_message",
    "get_chat_history",
    "clear_chat_history",
    "get_course_mindmap",
    "save_course_mindmap",
    "get_mindmap_disk_paths",
    "get_student_concept_mastery",
    "save_concept_mastery",
    "evaluate_and_sync_concept_mastery",
    "is_generic_concept",
    "extract_real_course_concepts",
    "get_setting",
    "set_setting",
    "get_user_setting",
    "set_user_setting",
    "BADGE_CATALOG",
    "COURSE_BADGE_CATALOG",
    "COURSE_BADGE_CATALOG_MAP",
    "get_badge_catalog",
    "get_user_badges",
    "award_badge",
    "evaluate_and_award_badges",
    "evaluate_and_award_course_badges",
    "get_student_trophies_overview",
    "get_course_trophies_overview",
    "get_student_trophies_by_course",
]

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
    """
    Initialise le schéma de base de données SQLite et applique les migrations
    pour supporter l'architecture multi-utilisateurs et le cloisonnement strict.
    """
    conn = get_connection(db_path)
    try:
        with conn:
            # 1. Tables fondamentales
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    email TEXT UNIQUE NOT NULL,
                    name TEXT NOT NULL,
                    avatar_url TEXT,
                    role TEXT NOT NULL CHECK(role IN ('admin', 'student')),
                    is_blocked INTEGER NOT NULL DEFAULT 0,
                    has_custom_name INTEGER NOT NULL DEFAULT 0,
                    age INTEGER DEFAULT 14,
                    level TEXT DEFAULT '3AC',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );

                CREATE TABLE IF NOT EXISTS user_settings (
                    user_id INTEGER NOT NULL,
                    key TEXT NOT NULL,
                    value TEXT NOT NULL,
                    PRIMARY KEY (user_id, key),
                    FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS courses (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    title TEXT NOT NULL,
                    subject TEXT NOT NULL,
                    language TEXT NOT NULL, -- 'fr' ou 'ar'
                    file_path TEXT NOT NULL,
                    file_hash TEXT NOT NULL,
                    file_name TEXT NOT NULL,
                    raw_text TEXT,
                    summary_markdown TEXT,
                    key_concepts_json TEXT,
                    mindmap_code TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS quizzes (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    course_id INTEGER NOT NULL,
                    quiz_data_json TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE,
                    FOREIGN KEY (course_id) REFERENCES courses (id) ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS quiz_attempts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    course_id INTEGER NOT NULL,
                    quiz_id INTEGER NOT NULL,
                    score INTEGER NOT NULL,
                    total_questions INTEGER NOT NULL,
                    answers_json TEXT,
                    completed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE,
                    FOREIGN KEY (course_id) REFERENCES courses (id) ON DELETE CASCADE,
                    FOREIGN KEY (quiz_id) REFERENCES quizzes (id) ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS chat_messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    course_id INTEGER NOT NULL,
                    role TEXT NOT NULL, -- 'user' ou 'assistant'
                    content TEXT NOT NULL,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE,
                    FOREIGN KEY (course_id) REFERENCES courses (id) ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS flashcards (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    course_id INTEGER NOT NULL,
                    front TEXT NOT NULL,
                    back TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE,
                    FOREIGN KEY (course_id) REFERENCES courses (id) ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS settings (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS user_sessions (
                    token TEXT PRIMARY KEY,
                    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    expires_at TIMESTAMP NOT NULL
                );

                CREATE TABLE IF NOT EXISTS concept_mastery (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    course_id INTEGER NOT NULL,
                    concept_title TEXT NOT NULL,
                    status TEXT NOT NULL CHECK(status IN ('mastered', 'in_progress', 'to_review', 'untested')),
                    success_rate REAL DEFAULT 0.0,
                    attempts_count INTEGER DEFAULT 0,
                    last_context TEXT,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE,
                    FOREIGN KEY (course_id) REFERENCES courses (id) ON DELETE CASCADE,
                    UNIQUE(user_id, course_id, concept_title)
                );

                CREATE TABLE IF NOT EXISTS user_badges (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    course_id INTEGER,
                    badge_key TEXT NOT NULL,
                    unlocked_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    metadata_json TEXT,
                    FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE,
                    FOREIGN KEY (course_id) REFERENCES courses (id) ON DELETE CASCADE
                );

                CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);
                CREATE INDEX IF NOT EXISTS idx_users_role ON users(role);
                CREATE INDEX IF NOT EXISTS idx_courses_hash ON courses(file_hash);
                CREATE INDEX IF NOT EXISTS idx_courses_subject ON courses(subject);
                CREATE INDEX IF NOT EXISTS idx_courses_lang ON courses(language);
                CREATE INDEX IF NOT EXISTS idx_quizzes_course ON quizzes(course_id);
                CREATE INDEX IF NOT EXISTS idx_chat_course ON chat_messages(course_id);
                CREATE INDEX IF NOT EXISTS idx_sessions_user ON user_sessions(user_id);
                CREATE INDEX IF NOT EXISTS idx_concept_mastery_user_course ON concept_mastery(user_id, course_id);
                CREATE INDEX IF NOT EXISTS idx_user_badges_user ON user_badges(user_id);
                CREATE INDEX IF NOT EXISTS idx_user_badges_course ON user_badges(user_id, course_id);
            """)

            # 2. Migrations dynamiques pour bases existantes
            cur = conn.cursor()
            cur.execute("PRAGMA table_info(users)")
            user_cols = [row["name"] for row in cur.fetchall()]
            if "is_blocked" not in user_cols:
                cur.execute("ALTER TABLE users ADD COLUMN is_blocked INTEGER NOT NULL DEFAULT 0")
            cur.execute("CREATE INDEX IF NOT EXISTS idx_users_blocked ON users(is_blocked)")
            if "has_custom_name" not in user_cols:
                cur.execute("ALTER TABLE users ADD COLUMN has_custom_name INTEGER NOT NULL DEFAULT 0")
            if "age" not in user_cols:
                cur.execute("ALTER TABLE users ADD COLUMN age INTEGER DEFAULT 14")
            if "level" not in user_cols:
                cur.execute("ALTER TABLE users ADD COLUMN level TEXT DEFAULT '3AC'")

            cur.execute("""
                CREATE TABLE IF NOT EXISTS user_badges (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    course_id INTEGER,
                    badge_key TEXT NOT NULL,
                    unlocked_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    metadata_json TEXT,
                    FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE,
                    FOREIGN KEY (course_id) REFERENCES courses (id) ON DELETE CASCADE
                )
            """)
            cur.execute("PRAGMA table_info(user_badges)")
            badge_cols = [row["name"] for row in cur.fetchall()]
            if "course_id" not in badge_cols:
                try:
                    cur.execute("ALTER TABLE user_badges ADD COLUMN course_id INTEGER REFERENCES courses(id) ON DELETE CASCADE")
                except Exception:
                    pass
            cur.execute("CREATE INDEX IF NOT EXISTS idx_user_badges_user ON user_badges(user_id)")
            cur.execute("CREATE INDEX IF NOT EXISTS idx_user_badges_course ON user_badges(user_id, course_id)")

            cur.execute("PRAGMA table_info(courses)")
            course_cols = [row["name"] for row in cur.fetchall()]
            if "mindmap_code" not in course_cols:
                cur.execute("ALTER TABLE courses ADD COLUMN mindmap_code TEXT")

            for tbl in ["courses", "quizzes", "quiz_attempts", "chat_messages"]:
                cur.execute(f"PRAGMA table_info({tbl})")
                cols = [row["name"] for row in cur.fetchall()]
                if "user_id" not in cols:
                    cur.execute(f"ALTER TABLE {tbl} ADD COLUMN user_id INTEGER REFERENCES users(id) ON DELETE CASCADE")

            # 2b. Migration courses : suppression de la contrainte UNIQUE globale sur file_hash
            cur.execute("PRAGMA index_list(courses)")
            indexes = cur.fetchall()
            has_unique_hash = False
            for idx in indexes:
                if (
                    idx["unique"] == 1
                    and not idx["partial"]
                    and idx["name"] not in ("idx_courses_null_user_hash", "idx_courses_user_hash")
                ):
                    idx_name = idx["name"]
                    cur.execute(f"PRAGMA index_info({idx_name})")
                    cols = [c["name"] for c in cur.fetchall()]
                    if cols == ["file_hash"]:
                        has_unique_hash = True
                        break

            if has_unique_hash:
                logger.info("Migration courses : suppression de la contrainte UNIQUE globale sur file_hash...")
                conn.execute("PRAGMA foreign_keys = OFF")
                conn.execute("DROP TABLE IF EXISTS courses_temp_migration")
                conn.execute("""
                    CREATE TABLE courses_temp_migration (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        user_id INTEGER,
                        title TEXT NOT NULL,
                        subject TEXT NOT NULL,
                        language TEXT NOT NULL,
                        file_path TEXT NOT NULL,
                        file_hash TEXT NOT NULL,
                        file_name TEXT NOT NULL,
                        raw_text TEXT,
                        summary_markdown TEXT,
                        key_concepts_json TEXT,
                        mindmap_code TEXT,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
                    )
                """)
                cur.execute("PRAGMA table_info(courses)")
                source_cols = [c["name"] for c in cur.fetchall()]
                if "mindmap_code" in source_cols:
                    conn.execute("""
                        INSERT INTO courses_temp_migration (id, user_id, title, subject, language, file_path, file_hash, file_name, raw_text, summary_markdown, key_concepts_json, mindmap_code, created_at, updated_at)
                        SELECT id, user_id, title, subject, language, file_path, file_hash, file_name, raw_text, summary_markdown, key_concepts_json, mindmap_code, created_at, updated_at FROM courses
                    """)
                else:
                    conn.execute("""
                        INSERT INTO courses_temp_migration (id, user_id, title, subject, language, file_path, file_hash, file_name, raw_text, summary_markdown, key_concepts_json, created_at, updated_at)
                        SELECT id, user_id, title, subject, language, file_path, file_hash, file_name, raw_text, summary_markdown, key_concepts_json, created_at, updated_at FROM courses
                    """)
                conn.execute("DROP TABLE courses")
                conn.execute("ALTER TABLE courses_temp_migration RENAME TO courses")
                conn.execute("PRAGMA foreign_keys = ON")

            # Vérification finale post-migration : garantir la présence de mindmap_code
            cur.execute("PRAGMA table_info(courses)")
            final_course_cols = [row["name"] for row in cur.fetchall()]
            if "mindmap_code" not in final_course_cols:
                cur.execute("ALTER TABLE courses ADD COLUMN mindmap_code TEXT")

            # 3. Index et vues dépendant de user_id
            conn.executescript("""
                CREATE INDEX IF NOT EXISTS idx_courses_hash ON courses(file_hash);
                CREATE INDEX IF NOT EXISTS idx_courses_subject ON courses(subject);
                CREATE INDEX IF NOT EXISTS idx_courses_lang ON courses(language);
                CREATE INDEX IF NOT EXISTS idx_courses_user ON courses(user_id);
                CREATE UNIQUE INDEX IF NOT EXISTS idx_courses_user_hash ON courses(user_id, file_hash) WHERE user_id IS NOT NULL;
                CREATE UNIQUE INDEX IF NOT EXISTS idx_courses_null_user_hash ON courses(file_hash) WHERE user_id IS NULL;
                CREATE INDEX IF NOT EXISTS idx_quizzes_user ON quizzes(user_id);
                CREATE INDEX IF NOT EXISTS idx_attempts_user ON quiz_attempts(user_id);
                CREATE INDEX IF NOT EXISTS idx_chat_user ON chat_messages(user_id);

                CREATE VIEW IF NOT EXISTS quiz_results AS SELECT * FROM quiz_attempts;
                CREATE VIEW IF NOT EXISTS chat_history AS SELECT * FROM chat_messages;
            """)

            # 4. Rétablir les cours indûment rattachés à des administrateurs comme cours partagés de l'établissement
            cur.execute("""
                UPDATE courses 
                SET user_id = NULL 
                WHERE user_id IN (SELECT id FROM users WHERE role = 'admin')
            """)
    finally:
        conn.close()


# ===========================================================================
# GESTION DES UTILISATEURS & RÔLES (PREMIER CONNECTÉ = ADMIN)
# ===========================================================================

def get_user_count() -> int:
    """Retourne le nombre total d'utilisateurs enregistrés."""
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM users")
        return cur.fetchone()[0]
    finally:
        conn.close()


def get_user_by_id(user_id: int) -> Optional[Dict[str, Any]]:
    """Récupère un utilisateur par son ID."""
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("SELECT * FROM users WHERE id = ?", (user_id,))
        row = cur.fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def get_user_by_email(email: str) -> Optional[Dict[str, Any]]:
    """Récupère un utilisateur par son adresse email."""
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("SELECT * FROM users WHERE email = ?", (email.strip().lower(),))
        row = cur.fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def create_or_get_google_user(
    email: str,
    name: str,
    avatar_url: Optional[str] = None,
    role: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Connecte ou enregistre un utilisateur Google OAuth selon la règle stricte :
    - Si aucun utilisateur n'existe en base : le tout premier reçoit le rôle 'admin'.
    - Tous les utilisateurs suivants reçoivent automatiquement le rôle 'student'.
    - Si l'utilisateur existe déjà : conserve son rôle existant et met à jour nom/avatar.
    """
    clean_email = email.strip().lower()
    conn = get_connection()
    try:
        with conn:
            cur = conn.cursor()
            cur.execute("SELECT * FROM users WHERE email = ?", (clean_email,))
            existing = cur.fetchone()

            if existing:
                user_dict = dict(existing)
                # Vérification de suspension de compte
                if user_dict.get("is_blocked", 0) == 1:
                    raise PermissionError("⛔ Ce compte a été suspendu par l'administrateur. Veuillez contacter votre établissement.")

                # Mise à jour des informations si elles ont changé
                # Si l'utilisateur a personnalisé son nom (has_custom_name == 1), on ne l'écrase pas avec le nom Google
                custom_name_flag = user_dict.get("has_custom_name", 0)
                update_name = user_dict["name"] if custom_name_flag == 1 else (name or user_dict["name"])
                if (update_name != user_dict["name"]) or avatar_url:
                    cur.execute(
                        """
                        UPDATE users 
                        SET name = ?, avatar_url = COALESCE(?, avatar_url)
                        WHERE id = ?
                        """,
                        (update_name, avatar_url, user_dict["id"]),
                    )
                    user_dict["name"] = update_name
                    user_dict["avatar_url"] = avatar_url or user_dict.get("avatar_url")
                return user_dict

            # Détermination automatique du rôle si non spécifié
            if not role:
                cur.execute("SELECT COUNT(*) FROM users")
                total_users = cur.fetchone()[0]
                role = "admin" if total_users == 0 else "student"

            default_age = 14
            default_level = "3AC"
            cur.execute(
                """
                INSERT INTO users (email, name, avatar_url, role, is_blocked, has_custom_name, age, level)
                VALUES (?, ?, ?, ?, 0, 0, ?, ?)
                """,
                (clean_email, name, avatar_url, role, default_age, default_level),
            )
            new_id = cur.lastrowid

            return {
                "id": new_id,
                "email": clean_email,
                "name": name,
                "avatar_url": avatar_url,
                "role": role,
                "is_blocked": 0,
                "has_custom_name": 0,
                "age": default_age,
                "level": default_level,
                "created_at": datetime.now().isoformat(),
            }
    finally:
        conn.close()


def list_users(
    role: Optional[str] = None,
    is_blocked: Optional[bool] = None,
) -> List[Dict[str, Any]]:
    """Liste les utilisateurs de la plateforme (filtrable par rôle et statut)."""
    conn = get_connection()
    try:
        cur = conn.cursor()
        query = "SELECT * FROM users WHERE 1=1"
        params: List[Any] = []
        if role:
            query += " AND role = ?"
            params.append(role)
        if is_blocked is not None:
            query += " AND is_blocked = ?"
            params.append(1 if is_blocked else 0)
        query += " ORDER BY id ASC"
        cur.execute(query, params)
        return [dict(r) for r in cur.fetchall()]
    finally:
        conn.close()


def set_user_blocked_status(
    target_user_id: int,
    is_blocked: bool,
    requesting_admin_id: Optional[int] = None,
) -> Tuple[bool, str]:
    """
    Suspend ou réactive un compte utilisateur.
    Sécurités :
    - Un administrateur ne peut pas modifier le statut de blocage de son propre compte.
    - Impossible de suspendre le dernier administrateur actif.
    """
    if requesting_admin_id is not None and target_user_id == requesting_admin_id:
        return False, "Vous ne pouvez pas modifier le statut de blocage de votre propre compte."

    conn = get_connection()
    try:
        with conn:
            cur = conn.cursor()
            cur.execute("SELECT * FROM users WHERE id = ?", (target_user_id,))
            target = cur.fetchone()
            if not target:
                return False, "Utilisateur introuvable."

            target_dict = dict(target)
            # Si on veut bloquer un administrateur, vérifier qu'il reste au moins un autre admin actif
            if is_blocked and target_dict["role"] == "admin":
                cur.execute("SELECT COUNT(*) FROM users WHERE role = 'admin' AND (is_blocked = 0 OR is_blocked IS NULL) AND id != ?", (target_user_id,))
                active_admins_left = cur.fetchone()[0]
                if active_admins_left < 1:
                    return False, "Impossible de suspendre le dernier administrateur actif de la plateforme."

            new_val = 1 if is_blocked else 0
            cur.execute("UPDATE users SET is_blocked = ? WHERE id = ?", (new_val, target_user_id))
            if is_blocked:
                cur.execute("DELETE FROM user_sessions WHERE user_id = ?", (target_user_id,))
            status_text = "suspendu" if is_blocked else "réactivé"
            return True, f"Le compte de {target_dict['name']} a été {status_text} avec succès."
    finally:
        conn.close()


def update_user_role(
    target_user_id: int,
    new_role: str,
    requesting_admin_id: Optional[int] = None,
) -> Tuple[bool, str]:
    """
    Modifie le rôle d'un utilisateur ('admin' ou 'student').
    Sécurités :
    - Interdiction de rétrograder le dernier administrateur de la plateforme.
    """
    if new_role not in ("admin", "student"):
        return False, f"Rôle invalide : {new_role}. Rôles autorisés : 'admin', 'student'."

    conn = get_connection()
    try:
        with conn:
            cur = conn.cursor()
            cur.execute("SELECT * FROM users WHERE id = ?", (target_user_id,))
            target = cur.fetchone()
            if not target:
                return False, "Utilisateur introuvable."

            target_dict = dict(target)
            if target_dict["role"] == new_role:
                return True, f"L'utilisateur a déjà le rôle '{new_role}'."

            # Si on rétrograde un admin en student, vérifier qu'il reste au moins un autre admin
            if target_dict["role"] == "admin" and new_role == "student":
                cur.execute("SELECT COUNT(*) FROM users WHERE role = 'admin' AND id != ?", (target_user_id,))
                other_admins = cur.fetchone()[0]
                if other_admins < 1:
                    return False, "Impossible de rétrograder le dernier administrateur de la plateforme."

            cur.execute("UPDATE users SET role = ? WHERE id = ?", (new_role, target_user_id))
            role_label = "Administrateur" if new_role == "admin" else "Élève"
            return True, f"Le rôle de {target_dict['name']} a été mis à jour vers '{role_label}' avec succès."
    finally:
        conn.close()


def delete_user_account(
    target_user_id: int,
    requesting_admin_id: Optional[int] = None,
) -> Tuple[bool, str]:
    """
    Supprime définitivement un compte utilisateur, toutes ses données SQLite associées
    (cours, quiz, fiches, chats, paramètres) et son dossier physique sur disque.
    Sécurités :
    - Un administrateur ne peut pas supprimer son propre compte connecté.
    - Impossible de supprimer le dernier administrateur.
    """
    if requesting_admin_id is not None and target_user_id == requesting_admin_id:
        return False, "Vous ne pouvez pas supprimer votre propre compte administrateur actif."

    conn = get_connection()
    try:
        with conn:
            cur = conn.cursor()
            cur.execute("SELECT * FROM users WHERE id = ?", (target_user_id,))
            target = cur.fetchone()
            if not target:
                return False, "Utilisateur introuvable."

            target_dict = dict(target)
            if target_dict["role"] == "admin":
                cur.execute("SELECT COUNT(*) FROM users WHERE role = 'admin' AND id != ?", (target_user_id,))
                other_admins = cur.fetchone()[0]
                if other_admins < 1:
                    return False, "Impossible de supprimer le dernier administrateur de la plateforme."

            # 1. Nettoyage explicite des tables liées
            cur.execute("DELETE FROM chat_messages WHERE user_id = ?", (target_user_id,))
            cur.execute("DELETE FROM quiz_attempts WHERE user_id = ?", (target_user_id,))
            cur.execute("DELETE FROM quizzes WHERE user_id = ?", (target_user_id,))
            cur.execute("DELETE FROM courses WHERE user_id = ?", (target_user_id,))
            cur.execute("DELETE FROM flashcards WHERE user_id = ?", (target_user_id,))
            cur.execute("DELETE FROM user_settings WHERE user_id = ?", (target_user_id,))
            cur.execute("DELETE FROM user_sessions WHERE user_id = ?", (target_user_id,))
            cur.execute("DELETE FROM users WHERE id = ?", (target_user_id,))

        # 2. Nettoyage physique du dossier de l'utilisateur
        storage_base = Path(__file__).parent.parent / "storage" / "users" / str(target_user_id)
        if storage_base.exists() and storage_base.is_dir():
            shutil.rmtree(storage_base, ignore_errors=True)

        return True, f"Le compte de {target_dict['name']} ({target_dict['email']}) et l'ensemble de ses données ont été supprimés définitivement."
    finally:
        conn.close()


def update_user_name(user_id: int, new_name: str) -> Tuple[bool, str]:
    """Met à jour le nom d'affichage d'un utilisateur et verrouille sa personnalisation face à OAuth."""
    clean_name = new_name.strip()
    if not clean_name:
        return False, "Le nom ne peut pas être vide."
    if len(clean_name) < 2 or len(clean_name) > 60:
        return False, "Le nom doit comporter entre 2 et 60 caractères."

    conn = get_connection()
    try:
        with conn:
            cur = conn.cursor()
            cur.execute("UPDATE users SET name = ?, has_custom_name = 1 WHERE id = ?", (clean_name, user_id))
            if cur.rowcount == 0:
                return False, "Utilisateur introuvable."
            return True, "Nom d'affichage mis à jour avec succès !"
    finally:
        conn.close()


MOROCCAN_SCHOOL_LEVELS: List[str] = [
    # Primaire
    "1AEP",
    "2AEP",
    "3AEP",
    "4AEP",
    "5AEP",
    "6AEP",
    # Collège
    "1AC",
    "2AC",
    "3AC",
    # Lycée
    "Tronc Commun",
    "1BAC",
    "2BAC",
    # Supérieur
    "Supérieur",
]


def get_pedagogical_cycle(age: Optional[int] = None, level: Optional[str] = None) -> Dict[str, Any]:
    """
    Détermine le cycle scolaire et le profil pédagogique.
    Prend en compte le niveau scolaire explicite (s'il est spécifié) ou l'infère de l'âge.
    - Primaire : 1AEP à 6AEP (5 à 10 ans)
    - Collège : 1AC, 2AC, 3AC (11 à 14 ans) [Défaut 14 ans / 3AC]
    - Lycée : Tronc Commun, 1BAC, 2BAC (15 à 18 ans)
    - Supérieur : Enseignement Supérieur / Formation Adulte (19 ans et +)
    """
    safe_age = 14
    if age is not None:
        try:
            safe_age = int(age)
        except (ValueError, TypeError):
            safe_age = 14

    if safe_age < 5:
        safe_age = 5
    elif safe_age > 100:
        safe_age = 100

    clean_level = (level.strip() if isinstance(level, str) else "") or None

    # Si un niveau explicite est fourni, il prime sur l'inférence d'âge
    if clean_level:
        lvl_upper = clean_level.upper()
        if any(lvl_upper.startswith(p) for p in ["1AEP", "2AEP", "3AEP", "4AEP", "5AEP", "6AEP"]) or "PRIMAIRE" in lvl_upper:
            return {
                "age": safe_age,
                "level": clean_level,
                "stage": "primary",
                "stage_label": f"Primaire ({clean_level})" if "AEP" in clean_level else "Primaire",
                "cycle_name": f"Cycle Primaire ({clean_level})",
                "badge_text": f"🎒 {clean_level} ({safe_age} ans)",
                "tone": "simple, ludique, visuel, très encourageant",
            }
        elif "1AC" in lvl_upper:
            return {
                "age": safe_age,
                "level": "1AC",
                "stage": "middle",
                "stage_label": "Collège (1AC)",
                "cycle_name": "Cycle Collégial (1AC)",
                "badge_text": f"🎒 1AC ({safe_age} ans)",
                "tone": "structuré, clair, motivant, orienté découverte et méthodologie du collège",
            }
        elif "2AC" in lvl_upper:
            return {
                "age": safe_age,
                "level": "2AC",
                "stage": "middle",
                "stage_label": "Collège (2AC)",
                "cycle_name": "Cycle Collégial (2AC)",
                "badge_text": f"🎒 2AC ({safe_age} ans)",
                "tone": "structuré, clair, motivant, consolidation des acquis du collège",
            }
        elif "3AC" in lvl_upper:
            return {
                "age": safe_age,
                "level": "3AC",
                "stage": "middle",
                "stage_label": "Collège (3AC)",
                "cycle_name": "Cycle Collégial (1AC - 3AC)",
                "badge_text": f"🎒 3AC ({safe_age} ans)",
                "tone": "structuré, clair, motivant, orienté réussite aux examens du collège",
            }
        elif "TRONC" in lvl_upper or "TC" in lvl_upper:
            return {
                "age": safe_age,
                "level": "Tronc Commun",
                "stage": "high",
                "stage_label": "Lycée (Tronc Commun)",
                "cycle_name": "Cycle Secondaire Qualifiant (Lycée - Tronc Commun)",
                "badge_text": f"🏛️ Tronc Commun ({safe_age} ans)",
                "tone": "académique, rigoureux, méthodologique, orientation",
            }
        elif "1BAC" in lvl_upper:
            return {
                "age": safe_age,
                "level": "1BAC",
                "stage": "high",
                "stage_label": "Lycée (1BAC)",
                "cycle_name": "Cycle Secondaire Qualifiant (1BAC - Examen Régional)",
                "badge_text": f"🏛️ 1BAC ({safe_age} ans)",
                "tone": "académique, rigoureux, analytique, préparation à l'examen régional",
            }
        elif "2BAC" in lvl_upper or "BAC" in lvl_upper:
            return {
                "age": safe_age,
                "level": "2BAC",
                "stage": "high",
                "stage_label": "Lycée (2BAC - Baccalauréat)",
                "cycle_name": "Cycle Secondaire Qualifiant (2BAC - Baccalauréat)",
                "badge_text": f"🏛️ 2BAC ({safe_age} ans)",
                "tone": "académique, rigoureux, analytique, préparation aux épreuves du Baccalauréat",
            }
        elif "SUP" in lvl_upper:
            return {
                "age": safe_age,
                "level": "Supérieur",
                "stage": "higher",
                "stage_label": "Supérieur / Adulte",
                "cycle_name": "Enseignement Supérieur & Formation Continue",
                "badge_text": f"🎓 Supérieur ({safe_age} ans)",
                "tone": "universitaire, professionnel, critique, approfondissement conceptuel",
            }

    # Inférence automatique selon l'âge lorsque le niveau n'est pas précisé
    if safe_age <= 10:
        level_inferred = "1AEP" if safe_age <= 6 else f"{safe_age - 5}AEP"
        return {
            "age": safe_age,
            "level": level_inferred,
            "stage": "primary",
            "stage_label": "Primaire",
            "cycle_name": "Cycle Primaire (CP - CM2)",
            "badge_text": f"🎒 Primaire ({safe_age} ans)",
            "tone": "simple, ludique, visuel, très encourageant",
        }
    elif safe_age <= 14:
        if safe_age in (11, 12):
            inferred_lvl = "1AC"
            stage_lbl = "Collège (1AC)"
        elif safe_age == 13:
            inferred_lvl = "2AC"
            stage_lbl = "Collège (2AC)"
        else:
            inferred_lvl = "3AC"
            stage_lbl = "Collège (3AC)"
        return {
            "age": safe_age,
            "level": inferred_lvl,
            "stage": "middle",
            "stage_label": stage_lbl,
            "cycle_name": "Cycle Collégial (1AC - 3AC)",
            "badge_text": f"🎒 Collège ({safe_age} ans)",
            "tone": "structuré, clair, motivant, orienté réussite aux examens du collège",
        }
    elif safe_age <= 18:
        if safe_age == 15:
            inferred_lvl = "Tronc Commun"
        elif safe_age == 16:
            inferred_lvl = "1BAC"
        else:
            inferred_lvl = "2BAC"
        return {
            "age": safe_age,
            "level": inferred_lvl,
            "stage": "high",
            "stage_label": "Lycée (Baccalauréat)",
            "cycle_name": "Cycle Secondaire Qualifiant (Lycée)",
            "badge_text": f"🏛️ Lycée ({safe_age} ans)",
            "tone": "académique, rigoureux, analytique, préparation aux épreuves du Baccalauréat",
        }
    else:
        return {
            "age": safe_age,
            "level": "Supérieur",
            "stage": "higher",
            "stage_label": "Supérieur / Adulte",
            "cycle_name": "Enseignement Supérieur & Formation Continue",
            "badge_text": f"🎓 Supérieur ({safe_age} ans)",
            "tone": "universitaire, professionnel, critique, approfondissement conceptuel",
        }


def update_user_age(user_id: int, age: int) -> Tuple[bool, str]:
    """Met à jour l'âge de l'élève pour adapter les contenus générés par l'IA."""
    try:
        val = int(age)
    except (ValueError, TypeError):
        return False, "L'âge doit être un nombre entier valide."

    if val < 5 or val > 100:
        return False, "L'âge doit être compris entre 5 et 100 ans."

    conn = get_connection()
    try:
        with conn:
            cur = conn.cursor()
            cur.execute("UPDATE users SET age = ? WHERE id = ?", (val, user_id))
            if cur.rowcount == 0:
                return False, "Utilisateur introuvable."
            cycle = get_pedagogical_cycle(val)
            return True, f"Âge enregistré ({val} ans — {cycle['cycle_name']}) !"
    finally:
        conn.close()


def update_user_level(user_id: int, level: str) -> Tuple[bool, str]:
    """Met à jour le niveau scolaire de l'élève (ex: 1AC, 2AC, 3AC, Tronc Commun, 1BAC, 2BAC...)."""
    clean_lvl = (level or "").strip()
    if not clean_lvl:
        return False, "Le niveau scolaire ne peut pas être vide."

    conn = get_connection()
    try:
        with conn:
            cur = conn.cursor()
            cur.execute("UPDATE users SET level = ? WHERE id = ?", (clean_lvl, user_id))
            if cur.rowcount == 0:
                return False, "Utilisateur introuvable."
            return True, f"Niveau scolaire mis à jour ({clean_lvl}) !"
    finally:
        conn.close()


# ===========================================================================
# SESSIONS UTILISATEURS PERSISTANTES (RÉSISTANCE AU RAFRAÎCHISSEMENT F5)
# ===========================================================================

def create_user_session(user_id: int, days_valid: int = 30) -> str:
    """Génère un jeton de session sécurisé pour l'utilisateur, persistant à travers les rechargements de page."""
    token = secrets.token_urlsafe(32)
    expires_at = (datetime.now() + timedelta(days=days_valid)).isoformat()
    conn = get_connection()
    try:
        with conn:
            cur = conn.cursor()
            cur.execute(
                """
                INSERT INTO user_sessions (token, user_id, expires_at)
                VALUES (?, ?, ?)
                """,
                (token, user_id, expires_at),
            )
            return token
    finally:
        conn.close()


def get_user_from_session_token(token: Optional[str]) -> Optional[Dict[str, Any]]:
    """
    Vérifie la validité d'un jeton de session :
    - Token existant et non expiré
    - Utilisateur existant et non suspendu
    Retourne le dictionnaire de l'utilisateur ou None.
    """
    if not token or not isinstance(token, str):
        return None

    clean_token = token.strip()
    if not clean_token:
        return None

    now_iso = datetime.now().isoformat()
    conn = get_connection()
    try:
        with conn:
            cur = conn.cursor()
            cur.execute(
                """
                SELECT s.token, s.user_id, s.expires_at, u.*
                FROM user_sessions s
                JOIN users u ON s.user_id = u.id
                WHERE s.token = ?
                """,
                (clean_token,),
            )
            row = cur.fetchone()
            if not row:
                return None

            row_dict = dict(row)
            expires_at = row_dict.get("expires_at")
            if expires_at and expires_at < now_iso:
                cur.execute("DELETE FROM user_sessions WHERE token = ?", (clean_token,))
                return None

            if row_dict.get("is_blocked", 0) == 1:
                cur.execute("DELETE FROM user_sessions WHERE token = ?", (clean_token,))
                return None

            return {
                "id": row_dict["id"],
                "email": row_dict["email"],
                "name": row_dict["name"],
                "avatar_url": row_dict.get("avatar_url"),
                "role": row_dict["role"],
                "is_blocked": row_dict.get("is_blocked", 0),
                "has_custom_name": row_dict.get("has_custom_name", 0),
                "age": row_dict.get("age", 14),
                "level": row_dict.get("level"),
                "created_at": row_dict.get("created_at"),
            }
    finally:
        conn.close()


def delete_user_session(token: Optional[str]) -> None:
    """Supprime un jeton de session lors de la déconnexion explicite."""
    if not token or not isinstance(token, str):
        return
    conn = get_connection()
    try:
        with conn:
            cur = conn.cursor()
            cur.execute("DELETE FROM user_sessions WHERE token = ?", (token.strip(),))
    finally:
        conn.close()


def cleanup_expired_sessions() -> int:
    """Nettoie les sessions expirées en base."""
    now_iso = datetime.now().isoformat()
    conn = get_connection()
    try:
        with conn:
            cur = conn.cursor()
            cur.execute("DELETE FROM user_sessions WHERE expires_at < ?", (now_iso,))
            return cur.rowcount
    finally:
        conn.close()


def get_global_admin_kpis() -> Dict[str, Any]:
    """Calcule les indicateurs globaux de supervision pour le tableau de bord administrateur."""
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM users WHERE role = 'student'")
        total_students = cur.fetchone()[0]

        cur.execute("SELECT COUNT(*) FROM users WHERE role = 'student' AND (is_blocked = 0 OR is_blocked IS NULL)")
        active_students = cur.fetchone()[0]

        cur.execute("SELECT COUNT(*) FROM users WHERE role = 'student' AND is_blocked = 1")
        blocked_students = cur.fetchone()[0]

        cur.execute("SELECT COUNT(*) FROM users WHERE role = 'admin'")
        total_admins = cur.fetchone()[0]

        cur.execute("SELECT COUNT(DISTINCT file_hash) FROM courses")
        total_courses = cur.fetchone()[0]

        cur.execute("SELECT COUNT(*) FROM quizzes")
        total_quizzes = cur.fetchone()[0]

        cur.execute("""
            SELECT 
                COUNT(*) as total_attempts,
                COALESCE(SUM(score), 0) as total_score,
                COALESCE(SUM(total_questions), 0) as total_questions
            FROM quiz_attempts
        """)
        row = cur.fetchone()
        attempts = row["total_attempts"]
        t_score = row["total_score"]
        t_q = row["total_questions"]
        avg_success = round((t_score / t_q * 100), 1) if t_q > 0 else 0.0

        # Résumé par élève (requêtes indépendantes sans produit cartésien)
        cur.execute("""
            SELECT 
                u.id as user_id,
                u.name,
                u.email,
                u.role,
                COALESCE(u.is_blocked, 0) as is_blocked,
                u.created_at,
                COALESCE(u.age, 14) as age,
                u.level,
                (
                    SELECT COUNT(DISTINCT file_hash) 
                    FROM courses 
                    WHERE user_id = u.id OR user_id IS NULL
                ) as course_count,
                COALESCE(q_agg.attempt_count, 0) as attempt_count,
                COALESCE(q_agg.student_score, 0) as student_score,
                COALESCE(q_agg.student_questions, 0) as student_questions
            FROM users u
            LEFT JOIN (
                SELECT 
                    user_id,
                    COUNT(id) as attempt_count,
                    SUM(score) as student_score,
                    SUM(total_questions) as student_questions
                FROM quiz_attempts
                GROUP BY user_id
            ) q_agg ON u.id = q_agg.user_id
            WHERE u.role = 'student'
            ORDER BY u.created_at DESC
        """)
        students_summary = []
        for r in cur.fetchall():
            d = dict(r)
            sq = d.get("student_questions", 0)
            ss = d.get("student_score", 0)
            d["average_rate"] = round((ss / sq * 100), 1) if sq > 0 else 0.0
            cycle = get_pedagogical_cycle(d.get("age", 14), level=d.get("level"))
            d["cycle"] = cycle
            d["level"] = d.get("level") or cycle.get("level", "3AC")
            students_summary.append(d)

        return {
            "total_students": total_students,
            "active_students": active_students,
            "blocked_students": blocked_students,
            "total_admins": total_admins,
            "total_courses": total_courses,
            "total_quizzes": total_quizzes,
            "total_attempts": attempts,
            "average_success_rate": avg_success,
            "students_summary": students_summary,
        }
    finally:
        conn.close()


# ===========================================================================
# PARAMÈTRES INDIVIDUELS PAR UTILISATEUR (CLÉS API, ETC.)
# ===========================================================================

def get_user_setting(user_id: int, key: str, default: Optional[str] = None) -> Optional[str]:
    """Récupère un paramètre isolé propre à un utilisateur."""
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("SELECT value FROM user_settings WHERE user_id = ? AND key = ?", (user_id, key))
        row = cur.fetchone()
        return row["value"] if row else default
    finally:
        conn.close()


def set_user_setting(user_id: int, key: str, value: str) -> None:
    """Enregistre un paramètre isolé propre à un utilisateur."""
    conn = get_connection()
    try:
        with conn:
            cur = conn.cursor()
            cur.execute(
                """
                INSERT INTO user_settings (user_id, key, value)
                VALUES (?, ?, ?)
                ON CONFLICT(user_id, key) DO UPDATE SET value = excluded.value
                """,
                (user_id, key, value),
            )
    finally:
        conn.close()


# ===========================================================================
# EXTRACTION ET VALIDATION DES NOTIONS DU COURS (ANTI-GÉNÉRIQUE)
# ===========================================================================

def normalize_text_for_concept_check(text: str) -> str:
    """
    Normalise le texte pour la détection fiable de notions génériques :
    retire les diacritiques arabes (tashkeel/harakat), unifie les lettres arabes (alif, taa marbuta, yaa),
    retire les accents latins et la ponctuation superflue.
    """
    if not text:
        return ""
    t = text.strip().lower()
    t = re.sub(r"^[0-9\W_]+|[0-9\W_]+$", "", t).strip()
    t = re.sub(r"[*#_`]+", "", t).strip()

    # 1. Normalisation Arabe : retirer le tashkeel (fatha, damma, kasra, sukun, shadda, tanween, dagger alif, tatweel)
    t = re.sub(r"[\u064b-\u065f\u0670\u0640]", "", t)
    # Normaliser alef
    t = re.sub(r"[إأآٱ]", "ا", t)
    # Normaliser taa marbuta
    t = re.sub(r"ة", "ه", t)
    # Normaliser yaa / alef maqsura
    t = re.sub(r"[ىي]", "ي", t)

    # 2. Normalisation Latin (Français / Anglais) : retirer les accents
    t = "".join(
        c for c in unicodedata.normalize("NFD", t)
        if unicodedata.category(c) != "Mn"
    )
    return t


GENERIC_KEYWORDS_NORMALIZED = [
    # Arabe - Pièges, erreurs, examens
    "فخ", "فخاخ", "مزلق", "مزالق", "خطا", "اخطاء", "يقع فيها", "انتبه يا بطل",
    "الامتحان الموحد", "الامتحان الجهوي", "الامتحان الوطني", "الامتحانات الاشهاديه",
    "تتكرر في الامتحان", "يجب ان اعرفها", "لضمان النقطه الكامله", "لضمان الامتياز",
    # Arabe - Méta-catégories de sections de fiches express
    "المفاهيم والتعاريف", "المفاهيم والمصطلحات", "المفاهيم المحوريه",
    "الكلمات والمفاهيم", "المفاهيم الاساسيه", "المفاهيم المركزيه",
    "القواعد الذهبيه", "القواعد والبرهنات", "النماذج والقواعد", "القواعد والصيغ",
    "طريقه التطبيق", "منهجيه التطبيق", "منهجيه الحل", "خطوات التطبيق",
    "نصيحه التحرير", "توجيهات منهجيه", "رويه نقديه", "سر التفوق", "سر النجاح",
    "العناصر المفتاحيه", "التواريخ والعناصر المفتاحيه", "التواريخ والعناصر",
    # Arabe - Anciennes formules génériques fabriquées
    "مفهوم وتعريف", "الخاصيات والقواعد", "الخاصيات والقواعد الاساسيه",
    "تطبيقات وتمارين", "تطبيقات وتمارين نموذجيه", "حالات خاصه وملاحظات", "حالات خاصه وملاحظات هامه",
    # Français - Pièges, erreurs
    "piege", "erreur frequente", "erreurs frequentes", "erreur classique", "erreurs classiques",
    "ecueil", "ecueils", "attention au petit piege",
    # Français - Méta-catégories de sections de fiches express
    "methode d'application", "methode d application", "demarche de resolution", "methodologie",
    "definitions & principes", "definition & principe", "definitions fondamentales",
    "proprietes, theoremes et formules", "proprietes & formules",
    "notions fondamentales", "notion fondamentale", "notions cles", "notion cle",
    "formules, regles & proprietes", "vocabulaire & les idees", "super words & key ideas",
    "l'idee cle", "idee cle en 1 minute",
    "astuce redaction", "astuce de champion", "conseil methodologique", "astuces pour les points",
    "gagner des points", "note maximale",
    "examen normalise", "examen blanc", "baccalaureat",
    # Français - Anciennes formules génériques fabriquées
    "definition et principes", "proprietes et formules", "applications et demarches types",
    "cas particuliers et verifications",
    # Anglais - Traps, pitfalls, templates
    "trap", "pitfall", "frequent error", "common mistake",
    "application method", "core concept", "rules and formulas", "golden rules",
    "star tip", "top marks", "writing strategy", "maximum marks",
    "definition and core principles", "essential formulas and properties",
    "practical worked examples", "special cases and applications",
]

LONE_GENERIC_WORDS_NORMALIZED = {
    "propriete", "proprietes", "formule", "formules", "definition", "definitions",
    "generalite", "generalites", "introduction", "conclusion", "fiche", "resume",
    "cours", "lecon", "notion", "notions", "methode", "methodes",
    "الخاصيات", "التعاريف", "القواعد", "الدرس", "ملخص", "مقدمه", "مفاهيم", "مصطلحات",
    "properties", "rules", "definitions", "summary", "lesson", "notes",
}


def is_generic_concept(text: str) -> bool:
    """
    Vérifie si un intitulé est une méta-catégorie générique (ex: Pièges d'examen,
    Méthode d'application, Définitions fondamentales, Formules, فخاخ الامتحان)
    plutôt qu'une notion réelle du cours.
    Gère la normalisation totale du texte (y compris le Tashkeel arabe et les accents français).
    """
    if not text or not text.strip():
        return True

    norm = normalize_text_for_concept_check(text)
    if not norm:
        return True

    if norm in LONE_GENERIC_WORDS_NORMALIZED:
        return True

    for kw in GENERIC_KEYWORDS_NORMALIZED:
        if kw in norm:
            return True

    return False


def extract_real_course_concepts(course: Dict[str, Any]) -> List[str]:
    """
    Extrait les notions pédagogiques réelles et concrètes d'un cours à partir de sa fiche/résumé
    ou de son texte brut, en éliminant strictement les méta-catégories génériques.
    Ne fabrique JAMAIS de fausses notions passe-partout.
    """
    # 1. Vérifier si des notions non génériques existent déjà dans key_concepts
    raw_concepts = course.get("key_concepts") or []
    valid_concepts = [c.strip() for c in raw_concepts if c and not is_generic_concept(c)]
    if len(valid_concepts) >= 2:
        return valid_concepts

    # 2. Extraire depuis le résumé markdown ou le texte brut
    summary = course.get("summary_markdown") or ""
    raw_text = course.get("raw_text") or ""
    extracted: List[str] = []

    # 2.A Extraction depuis le résumé markdown (Fiche Express)
    if summary:
        # a) Puces en gras : "- **Notion réelle :** explication..." ou "- **Notion réelle** : explication..."
        # Accepte le deux-points à l'intérieur ou à l'extérieur des astérisques
        bold_bullets = re.findall(r"^[\s\-*•\d\.]*\*\*([^*]{3,70})\*\*", summary, flags=re.MULTILINE)
        for b in bold_bullets:
            b_clean = re.sub(r"[:\s]+$", "", b.strip())
            b_clean = re.sub(r"^[0-9\.\)\-\s:]+", "", b_clean).strip()
            b_clean = re.sub(r"[()\[\]{}]+", "", b_clean).strip()
            if len(b_clean) >= 3 and not is_generic_concept(b_clean) and b_clean not in extracted:
                extracted.append(b_clean)

        # b) Sous-titres markdown non génériques (## ou ###)
        if len(extracted) < 2:
            headings = re.findall(r"^#{2,3}\s+(?:[0-9]+[.\-)]\s*)?([^\n#]{3,70})", summary, flags=re.MULTILINE)
            for h in headings:
                h_clean = re.sub(r"^[^\w\s]+", "", h.strip())  # retire emojis
                h_clean = re.sub(r"^[0-9\.\)\-\s:]+", "", h_clean).strip()
                h_clean = re.sub(r"[:\s]+$", "", h_clean).strip()
                if len(h_clean) >= 3 and not is_generic_concept(h_clean) and h_clean not in extracted:
                    extracted.append(h_clean)

    # 2.B Si le résumé n'a pas suffi (< 2 notions), extraire depuis le texte brut du cours (raw_text)
    if len(extracted) < 2 and raw_text:
        for line in raw_text.splitlines():
            line_str = line.strip()
            if not line_str:
                continue
            # Pattern A: Axes / Sections (ex: المحور الأول: مفهوم العبادة / I - Définition / 1- Notion)
            m = re.match(
                r"^(?:المحور|المطلب|الفقرة|النشاط|المفهوم|أولا|ثانيا|ثالثا|رابعا|خامسا|axe|partie|chapitre|[IVX]+|\d+)[\s\.\-:\)]+([^\n:]{3,65})",
                line_str,
                flags=re.IGNORECASE,
            )
            if m:
                c_clean = m.group(1).strip()
                c_clean = re.sub(r"^[0-9\.\)\-\s:]+", "", c_clean).strip()
                c_clean = re.sub(r"[()\[\]{}]+", "", c_clean).strip()
                if len(c_clean) >= 3 and not is_generic_concept(c_clean) and c_clean not in extracted:
                    extracted.append(c_clean)
            # Pattern B: Lignes courtes se terminant par un deux-points ":" (ex: "مفهوم العبادة:", "غايات العبادة:")
            elif line_str.endswith(":") and 4 <= len(line_str[:-1].strip()) <= 60:
                c_clean = line_str[:-1].strip()
                c_clean = re.sub(r"^[0-9\.\)\-\sIIVVXXa-zA-Z]+", "", c_clean).strip()
                c_clean = re.sub(r"[()\[\]{}]+", "", c_clean).strip()
                if len(c_clean) >= 3 and not is_generic_concept(c_clean) and c_clean not in extracted:
                    extracted.append(c_clean)

            if len(extracted) >= 6:
                break

    # 2.C Décomposition propre du titre si le cours a un titre composé (ex: "العبادة صفة إيمان ودليل خضوع")
    if len(extracted) < 2:
        title = (course.get("title") or "").strip()
        if title:
            # Séparateurs de notions dans un titre : ':', ' - ', ' / ', et en arabe ' و ' ou ' و'
            parts = re.split(r"[:\-/|]|(?:\s+و(?=\w))", title)
            for p in parts:
                p_clean = p.strip()
                p_clean = re.sub(r"^[0-9\.\)\-\s:]+", "", p_clean).strip()
                p_clean = re.sub(r"[()\[\]{}]+", "", p_clean).strip()
                if len(p_clean) >= 4 and not is_generic_concept(p_clean) and p_clean not in extracted:
                    extracted.append(p_clean)

    # Note : Si aucune notion réelle n'est trouvée, on retourne la liste telle quelle (qui peut être vide).
    # Il est STRICTEMENT INTERDIT d'inventer des fausses notions passe-partout.
    return extracted[:6]


# ===========================================================================
# OPÉRATIONS CRUD SUR LES COURS (CLOISONNÉES PAR USER_ID)
# ===========================================================================

def get_mindmap_disk_paths(
    course_id: Optional[int] = None,
    file_path: Optional[str] = None,
    user_id: Optional[int] = None,
) -> List[Path]:
    """Retourne la liste ordonnée des chemins potentiels de fichier disque pour la carte mentale d'un cours."""
    paths: List[Path] = []
    if file_path:
        fp = Path(file_path)
        if fp.parent.exists():
            # 1. <file_path>.mindmap.md (ex: .../cours/doc.pdf.mindmap.md)
            paths.append(fp.with_name(f"{fp.name}.mindmap.md"))
            # 2. <file_stem>.mindmap.md (ex: .../cours/doc.mindmap.md)
            paths.append(fp.with_suffix(".mindmap.md"))
            # 3. <parent>/<course_id>_mindmap.md
            if course_id is not None:
                paths.append(fp.parent / f"{course_id}_mindmap.md")

    try:
        storage_root = get_db_path().parent
    except Exception:
        storage_root = Path(DEFAULT_DB_DIR)

    if course_id is not None:
        if user_id is not None:
            user_cours_dir = storage_root / "users" / str(user_id) / "cours"
            paths.append(user_cours_dir / f"{course_id}_mindmap.md")
        legacy_dir = storage_root / "cours"
        paths.append(legacy_dir / f"{course_id}_mindmap.md")

    # Éliminer les doublons tout en préservant l'ordre
    seen = set()
    unique_paths: List[Path] = []
    for p in paths:
        p_str = str(p)
        if p_str not in seen:
            seen.add(p_str)
            unique_paths.append(p)
    return unique_paths


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
    user_id: Optional[int] = None,
    mindmap_code: Optional[str] = None,
) -> int:
    """Enregistre ou met à jour un cours cloisonné par son hash et son user_id avec double persistance de la carte mentale."""
    conn = get_connection()
    try:
        with conn:
            cur = conn.cursor()
            clean_kc = [c.strip() for c in (key_concepts or []) if c and isinstance(c, str) and not is_generic_concept(c)]
            concepts_json = json.dumps(clean_kc, ensure_ascii=False)

            # Si mindmap_code n'est pas fourni, chercher un fichier existant sur disque
            if not mindmap_code:
                disk_paths = get_mindmap_disk_paths(None, file_path, user_id)
                for dp in disk_paths:
                    if dp.exists() and dp.is_file():
                        try:
                            content = dp.read_text(encoding="utf-8").strip()
                            if content:
                                mindmap_code = content
                                break
                        except Exception:
                            pass

            if user_id is not None:
                cur.execute("SELECT id FROM courses WHERE file_hash = ? AND user_id = ?", (file_hash, user_id))
            else:
                cur.execute("SELECT id FROM courses WHERE file_hash = ? AND user_id IS NULL", (file_hash,))
            existing = cur.fetchone()

            if existing:
                course_id = existing["id"]
                cur.execute(
                    """
                    UPDATE courses
                    SET title = ?, subject = ?, language = ?, file_path = ?,
                        file_name = ?, raw_text = ?, summary_markdown = COALESCE(?, summary_markdown),
                        key_concepts_json = ?, mindmap_code = COALESCE(?, mindmap_code), updated_at = CURRENT_TIMESTAMP
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
                        mindmap_code,
                        course_id,
                    ),
                )
                if mindmap_code:
                    for dp in get_mindmap_disk_paths(course_id, file_path, user_id):
                        try:
                            dp.parent.mkdir(parents=True, exist_ok=True)
                            dp.write_text(mindmap_code, encoding="utf-8")
                        except Exception:
                            pass
                return course_id
            else:
                try:
                    cur.execute(
                        """
                        INSERT INTO courses (user_id, title, subject, language, file_path, file_hash, file_name, raw_text, summary_markdown, key_concepts_json, mindmap_code)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            user_id,
                            title,
                            subject,
                            language,
                            file_path,
                            file_hash,
                            file_name,
                            raw_text,
                            summary_markdown,
                            concepts_json,
                            mindmap_code,
                        ),
                    )
                    course_id = cur.lastrowid
                    if mindmap_code:
                        for dp in get_mindmap_disk_paths(course_id, file_path, user_id):
                            try:
                                dp.parent.mkdir(parents=True, exist_ok=True)
                                dp.write_text(mindmap_code, encoding="utf-8")
                            except Exception:
                                pass
                    return course_id
                except sqlite3.IntegrityError:
                    if user_id is not None:
                        cur.execute("SELECT id FROM courses WHERE file_hash = ? AND user_id = ?", (file_hash, user_id))
                    else:
                        cur.execute("SELECT id FROM courses WHERE file_hash = ? AND user_id IS NULL", (file_hash,))
                    row = cur.fetchone()
                    if not row:
                        cur.execute("SELECT id FROM courses WHERE file_hash = ?", (file_hash,))
                        row = cur.fetchone()
                    if row:
                        cid = row["id"]
                        cur.execute(
                            """
                            UPDATE courses
                            SET title = ?, subject = ?, language = ?, file_path = ?,
                                file_name = ?, raw_text = ?, summary_markdown = COALESCE(?, summary_markdown),
                                key_concepts_json = ?, mindmap_code = COALESCE(?, mindmap_code), updated_at = CURRENT_TIMESTAMP
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
                                mindmap_code,
                                cid,
                            ),
                        )
                        if mindmap_code:
                            for dp in get_mindmap_disk_paths(cid, file_path, user_id):
                                try:
                                    dp.parent.mkdir(parents=True, exist_ok=True)
                                    dp.write_text(mindmap_code, encoding="utf-8")
                                except Exception:
                                    pass
                        return cid
                    raise
    finally:
        conn.close()


def get_course_by_id(course_id: int, user_id: Optional[int] = None) -> Optional[Dict[str, Any]]:
    """Récupère un cours par son ID, vérifiant l'isolation si user_id est fourni."""
    conn = get_connection()
    try:
        cur = conn.cursor()
        if user_id is not None:
            cur.execute("SELECT * FROM courses WHERE id = ? AND (user_id = ? OR user_id IS NULL)", (course_id, user_id))
        else:
            cur.execute("SELECT * FROM courses WHERE id = ?", (course_id,))
        row = cur.fetchone()
        if not row:
            return None
        res = dict(row)
        try:
            raw_kc = json.loads(res.get("key_concepts_json") or "[]")
            if not isinstance(raw_kc, list):
                raw_kc = []
        except Exception:
            raw_kc = []

        clean_kc = [c.strip() for c in raw_kc if c and isinstance(c, str) and not is_generic_concept(c)]

        # Auto-réparation si les notions sont absentes, polluées ou insuffisantes (< 2)
        if len(clean_kc) < 2 and (res.get("summary_markdown") or res.get("raw_text") or res.get("title")):
            real_kc = extract_real_course_concepts(res)
            if real_kc != raw_kc:
                try:
                    cur.execute(
                        "UPDATE courses SET key_concepts_json = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                        (json.dumps(real_kc, ensure_ascii=False), course_id),
                    )
                    conn.commit()
                except Exception:
                    pass
                clean_kc = real_kc
        elif len(clean_kc) != len(raw_kc):
            try:
                cur.execute(
                    "UPDATE courses SET key_concepts_json = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                    (json.dumps(clean_kc, ensure_ascii=False), course_id),
                )
                conn.commit()
            except Exception:
                pass

        res["key_concepts"] = clean_kc
        if not res.get("mindmap_code"):
            m = get_course_mindmap(course_id)
            if m:
                res["mindmap_code"] = m
        return res
    finally:
        conn.close()


def get_course_by_hash(file_hash: str, user_id: Optional[int] = None, include_global: bool = True) -> Optional[Dict[str, Any]]:
    """Récupère un cours par son hash SHA-256 (cloisonné par utilisateur)."""
    conn = get_connection()
    try:
        cur = conn.cursor()
        if user_id is not None:
            if include_global:
                cur.execute("SELECT * FROM courses WHERE file_hash = ? AND (user_id = ? OR user_id IS NULL)", (file_hash, user_id))
            else:
                cur.execute("SELECT * FROM courses WHERE file_hash = ? AND user_id = ?", (file_hash, user_id))
        else:
            cur.execute("SELECT * FROM courses WHERE file_hash = ?", (file_hash,))
        row = cur.fetchone()
        if not row:
            return None
        res = dict(row)
        try:
            raw_kc = json.loads(res.get("key_concepts_json") or "[]")
            if not isinstance(raw_kc, list):
                raw_kc = []
        except Exception:
            raw_kc = []

        clean_kc = [c.strip() for c in raw_kc if c and isinstance(c, str) and not is_generic_concept(c)]
        if len(clean_kc) < 2 and (res.get("summary_markdown") or res.get("raw_text") or res.get("title")):
            real_kc = extract_real_course_concepts(res)
            if real_kc != raw_kc:
                try:
                    cur.execute(
                        "UPDATE courses SET key_concepts_json = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                        (json.dumps(real_kc, ensure_ascii=False), res["id"]),
                    )
                    conn.commit()
                except Exception:
                    pass
                clean_kc = real_kc
        elif len(clean_kc) != len(raw_kc):
            try:
                cur.execute(
                    "UPDATE courses SET key_concepts_json = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                    (json.dumps(clean_kc, ensure_ascii=False), res["id"]),
                )
                conn.commit()
            except Exception:
                pass

        res["key_concepts"] = clean_kc
        if not res.get("mindmap_code"):
            m = get_course_mindmap(res["id"])
            if m:
                res["mindmap_code"] = m
        return res
    finally:
        conn.close()


def list_courses(
    user_id: Optional[int] = None,
    subject: Optional[str] = None,
    language: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """Liste les cours cloisonnés par utilisateur avec filtres optionnels et déduplication par hash."""
    conn = get_connection()
    try:
        cur = conn.cursor()
        params: List[Any] = []

        if user_id is not None:
            # Priorise le cours personnel de l'élève, et complète avec les cours partagés non encore dupliqués
            query = """
                SELECT c.* FROM (
                    SELECT * FROM courses WHERE user_id = ?
                    UNION ALL
                    SELECT * FROM courses WHERE user_id IS NULL AND file_hash NOT IN (
                        SELECT file_hash FROM courses WHERE user_id = ?
                    )
                ) c WHERE 1=1
            """
            params.extend([user_id, user_id])
        else:
            query = "SELECT c.* FROM courses c WHERE 1=1"

        if subject and subject != "Toutes":
            query += " AND c.subject = ?"
            params.append(subject)

        if language and language != "Toutes":
            query += " AND c.language = ?"
            params.append(language)

        query += " ORDER BY c.updated_at DESC, c.id DESC"
        cur.execute(query, params)
        rows = cur.fetchall()

        result = []
        for row in rows:
            d = dict(row)
            try:
                raw_kc = json.loads(d.get("key_concepts_json") or "[]")
                if not isinstance(raw_kc, list):
                    raw_kc = []
            except Exception:
                raw_kc = []
            d["key_concepts"] = [c.strip() for c in raw_kc if c and isinstance(c, str) and not is_generic_concept(c)]
            result.append(d)
        return result
    finally:
        conn.close()


def update_course_summary(
    course_id: int,
    summary_markdown: str,
    key_concepts: Optional[List[str]] = None,
    user_id: Optional[int] = None,
) -> None:
    """Met à jour la fiche express d'un cours."""
    conn = get_connection()
    try:
        with conn:
            cur = conn.cursor()
            where_clause = "WHERE id = ?"
            params: List[Any] = []

            if key_concepts is not None:
                clean_kc = [c.strip() for c in key_concepts if c and isinstance(c, str) and not is_generic_concept(c)]
            else:
                clean_kc = extract_real_course_concepts({"summary_markdown": summary_markdown})

            set_clause = "SET summary_markdown = ?, key_concepts_json = ?, updated_at = CURRENT_TIMESTAMP"
            params.extend([summary_markdown, json.dumps(clean_kc, ensure_ascii=False), course_id])

            if user_id is not None:
                where_clause += " AND user_id = ?"
                params.append(user_id)

            cur.execute(f"UPDATE courses {set_clause} {where_clause}", params)
    finally:
        conn.close()


def update_course_metadata(
    course_id: int,
    title: str,
    subject: str,
    language: str,
    user_id: Optional[int] = None,
) -> None:
    """Met à jour les métadonnées d'un cours."""
    conn = get_connection()
    try:
        with conn:
            cur = conn.cursor()
            query = "UPDATE courses SET title = ?, subject = ?, language = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?"
            params: List[Any] = [title, subject, language, course_id]
            if user_id is not None:
                query += " AND user_id = ?"
                params.append(user_id)
            cur.execute(query, params)
    finally:
        conn.close()


def delete_course(course_id: int, user_id: Optional[int] = None) -> bool:
    """Supprime un cours et son fichier local de manière sécurisée."""
    conn = get_connection()
    try:
        with conn:
            cur = conn.cursor()
            query_sel = "SELECT file_path, user_id FROM courses WHERE id = ?"
            params_sel: List[Any] = [course_id]
            if user_id is not None:
                query_sel += " AND user_id = ?"
                params_sel.append(user_id)

            cur.execute(query_sel, params_sel)
            row = cur.fetchone()
            if not row:
                return False

            if row["file_path"] and os.path.exists(row["file_path"]):
                try:
                    os.remove(row["file_path"])
                except Exception as e:
                    logger.warning(f"Impossible de supprimer le fichier {row['file_path']} : {e}")

            # Nettoyage des fichiers disque de la carte mentale
            for dp in get_mindmap_disk_paths(course_id, row["file_path"], row["user_id"]):
                if dp.exists() and dp.is_file():
                    try:
                        dp.unlink()
                    except Exception as e:
                        logger.warning(f"Impossible de supprimer la carte mentale {dp} : {e}")

            query_del = "DELETE FROM courses WHERE id = ?"
            params_del: List[Any] = [course_id]
            if user_id is not None:
                query_del += " AND user_id = ?"
                params_del.append(user_id)

            cur.execute(query_del, params_del)
            return cur.rowcount > 0
    finally:
        conn.close()


# ===========================================================================
# QUIZ, TENTATIVES ET STATISTIQUES (CLOISONNÉES)
# ===========================================================================

def save_quiz(course_id: int, quiz_data: List[Dict[str, Any]], user_id: Optional[int] = None) -> int:
    """Enregistre un quiz associé à un cours et à l'utilisateur."""
    conn = get_connection()
    try:
        with conn:
            cur = conn.cursor()
            data_json = json.dumps(quiz_data, ensure_ascii=False)
            if user_id is not None:
                cur.execute(
                    "SELECT id FROM quizzes WHERE course_id = ? AND user_id = ? AND quiz_data_json = ?",
                    (course_id, user_id, data_json),
                )
            else:
                cur.execute(
                    "SELECT id FROM quizzes WHERE course_id = ? AND user_id IS NULL AND quiz_data_json = ?",
                    (course_id, data_json),
                )
            existing = cur.fetchone()
            if existing:
                return existing["id"]

            cur.execute(
                "INSERT INTO quizzes (user_id, course_id, quiz_data_json) VALUES (?, ?, ?)",
                (user_id, course_id, data_json),
            )
            return cur.lastrowid
    finally:
        conn.close()


def get_latest_quiz(course_id: int, user_id: Optional[int] = None) -> Optional[Dict[str, Any]]:
    """Récupère le dernier quiz généré pour un cours."""
    conn = get_connection()
    try:
        cur = conn.cursor()
        query = "SELECT * FROM quizzes WHERE course_id = ?"
        params: List[Any] = [course_id]
        if user_id is not None:
            query += " AND (user_id = ? OR user_id IS NULL)"
            params.append(user_id)
        query += " ORDER BY id DESC LIMIT 1"
        cur.execute(query, params)
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
    user_id: Optional[int] = None,
) -> int:
    """Enregistre le résultat d'une tentative de quiz."""
    conn = get_connection()
    try:
        with conn:
            cur = conn.cursor()
            cur.execute(
                """
                INSERT INTO quiz_attempts (user_id, course_id, quiz_id, score, total_questions, answers_json)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (user_id, course_id, quiz_id, score, total_questions, json.dumps(answers, ensure_ascii=False)),
            )
            return cur.lastrowid
    finally:
        conn.close()


def get_quiz_stats(user_id: Optional[int] = None) -> Dict[str, Any]:
    """
    Calcule les statistiques de révision et progrès par matière.
    Si user_id est fourni, calcule pour cet élève exclusivement.
    Si user_id est None, calcule pour la plateforme entière (supervision admin).
    """
    conn = get_connection()
    try:
        cur = conn.cursor()
        where_user = "WHERE user_id = ?" if user_id is not None else ""
        params_user = [user_id] if user_id is not None else []

        # 1. Stats globales
        cur.execute(
            f"""
            SELECT 
                COUNT(*) as total_attempts,
                COALESCE(SUM(score), 0) as total_score,
                COALESCE(SUM(total_questions), 0) as total_questions
            FROM quiz_attempts
            {where_user}
            """,
            params_user,
        )
        global_row = dict(cur.fetchone() or {})
        total_questions = global_row.get("total_questions", 0)
        total_score = global_row.get("total_score", 0)
        avg_rate = (total_score / total_questions * 100) if total_questions > 0 else 0.0

        # 2. Stats par matière
        subj_query = """
            SELECT 
                c.subject,
                c.language,
                COUNT(qa.id) as attempts,
                COALESCE(SUM(qa.score), 0) as subject_score,
                COALESCE(SUM(qa.total_questions), 0) as subject_questions
            FROM courses c
            JOIN quiz_attempts qa ON c.id = qa.course_id
        """
        if user_id is not None:
            subj_query += " WHERE qa.user_id = ?"
        subj_query += " GROUP BY c.subject, c.language ORDER BY attempts DESC"

        cur.execute(subj_query, params_user)
        by_subject = []
        for r in cur.fetchall():
            d = dict(r)
            sq = d.get("subject_questions", 0)
            ss = d.get("subject_score", 0)
            d["success_rate"] = round((ss / sq * 100), 1) if sq > 0 else 0.0
            by_subject.append(d)

        # 3. Dernières tentatives
        recent_query = """
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
        """
        if user_id is not None:
            recent_query += " WHERE qa.user_id = ?"
        recent_query += " ORDER BY qa.completed_at DESC LIMIT 10"

        cur.execute(recent_query, params_user)
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


# ===========================================================================
# CHAT ET HISTORIQUE DU TUTEUR SANAD (CLOISONNÉ)
# ===========================================================================

def get_chat_history(
    course_id: int,
    limit: int = 50,
    user_id: Optional[int] = None,
) -> List[Dict[str, str]]:
    """Récupère l'historique de discussion avec le tuteur pour un cours."""
    conn = get_connection()
    try:
        cur = conn.cursor()
        query = "SELECT role, content, timestamp FROM chat_messages WHERE course_id = ?"
        params: List[Any] = [course_id]
        if user_id is not None:
            query += " AND (user_id = ? OR user_id IS NULL)"
            params.append(user_id)
        query += " ORDER BY id ASC LIMIT ?"
        params.append(limit)

        cur.execute(query, params)
        return [{"role": r["role"], "content": r["content"], "timestamp": r["timestamp"]} for r in cur.fetchall()]
    finally:
        conn.close()


def add_chat_message(
    course_id: int,
    role: str,
    content: str,
    user_id: Optional[int] = None,
) -> None:
    """Ajoute un message dans l'historique du tuteur."""
    conn = get_connection()
    try:
        with conn:
            cur = conn.cursor()
            cur.execute(
                "INSERT INTO chat_messages (user_id, course_id, role, content) VALUES (?, ?, ?, ?)",
                (user_id, course_id, role, content),
            )
    finally:
        conn.close()


def clear_chat_history(course_id: int, user_id: Optional[int] = None) -> None:
    """Efface l'historique de discussion d'un cours."""
    conn = get_connection()
    try:
        with conn:
            cur = conn.cursor()
            query = "DELETE FROM chat_messages WHERE course_id = ?"
            params: List[Any] = [course_id]
            if user_id is not None:
                query += " AND user_id = ?"
                params.append(user_id)
            cur.execute(query, params)
    finally:
        conn.close()


# ===========================================================================
# FLASHCARDS (FICHES DE RÉVISION INDIVIDUELLES)
# ===========================================================================

def save_flashcard(user_id: int, course_id: int, front: str, back: str) -> int:
    """Enregistre une flashcard pour un élève."""
    conn = get_connection()
    try:
        with conn:
            cur = conn.cursor()
            cur.execute(
                "SELECT id FROM flashcards WHERE user_id = ? AND course_id = ? AND front = ?",
                (user_id, course_id, front),
            )
            existing = cur.fetchone()
            if existing:
                cur.execute("UPDATE flashcards SET back = ? WHERE id = ?", (back, existing["id"]))
                return existing["id"]

            cur.execute(
                "INSERT INTO flashcards (user_id, course_id, front, back) VALUES (?, ?, ?, ?)",
                (user_id, course_id, front, back),
            )
            return cur.lastrowid
    finally:
        conn.close()


def list_flashcards(user_id: int, course_id: Optional[int] = None) -> List[Dict[str, Any]]:
    """Liste les flashcards d'un élève."""
    conn = get_connection()
    try:
        cur = conn.cursor()
        query = "SELECT * FROM flashcards WHERE user_id = ?"
        params: List[Any] = [user_id]
        if course_id is not None:
            query += " AND course_id = ?"
            params.append(course_id)
        query += " ORDER BY id DESC"
        cur.execute(query, params)
        return [dict(r) for r in cur.fetchall()]
    finally:
        conn.close()


# ===========================================================================
# PARAMÈTRES SYSTÈME GLOBAUX (RÉTRO-COMPATIBILITÉ)
# ===========================================================================

def get_setting(key: str, default: Optional[str] = None) -> Optional[str]:
    """Lit un paramètre global stocké dans la base."""
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("SELECT value FROM settings WHERE key = ?", (key,))
        row = cur.fetchone()
        return row["value"] if row else default
    finally:
        conn.close()


def set_setting(key: str, value: str) -> None:
    """Enregistre ou met à jour un paramètre global."""
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


# ===========================================================================
# 8. CARTES MENTALES (MIND MAPS) & SUIVI DE L'ASSIMILATION DES NOTIONS
# ===========================================================================

def _ensure_concept_mastery_table(conn: sqlite3.Connection) -> None:
    """Crée la table concept_mastery si elle n'existe pas encore."""
    conn.execute("""
        CREATE TABLE IF NOT EXISTS concept_mastery (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            course_id INTEGER NOT NULL,
            concept_title TEXT NOT NULL,
            status TEXT NOT NULL CHECK(status IN ('mastered', 'in_progress', 'to_review', 'untested')),
            success_rate REAL DEFAULT 0.0,
            attempts_count INTEGER DEFAULT 0,
            last_context TEXT,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE,
            FOREIGN KEY (course_id) REFERENCES courses (id) ON DELETE CASCADE,
            UNIQUE(user_id, course_id, concept_title)
        )
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_concept_mastery_user_course ON concept_mastery(user_id, course_id)")


def get_course_mindmap(course_id: int) -> Optional[str]:
    """Récupère le schéma mindmap associé à un cours (avec double persistance SQLite + disque et auto-réparation)."""
    conn = get_connection()
    try:
        cur = conn.cursor()
        try:
            cur.execute("SELECT mindmap_code, file_path, user_id FROM courses WHERE id = ?", (course_id,))
        except sqlite3.OperationalError:
            # Auto-réparation si la colonne mindmap_code n'existe pas encore sur la base SQLite distante
            try:
                with conn:
                    conn.execute("ALTER TABLE courses ADD COLUMN mindmap_code TEXT")
                cur.execute("SELECT mindmap_code, file_path, user_id FROM courses WHERE id = ?", (course_id,))
            except Exception:
                return None
        row = cur.fetchone()
        if not row:
            return None

        # 1. Vérifier si mindmap_code est présent dans SQLite
        if row["mindmap_code"] and row["mindmap_code"].strip():
            return row["mindmap_code"]

        # 2. Secours / Auto-réparation : chercher sur le disque
        paths = get_mindmap_disk_paths(course_id, row["file_path"], row["user_id"])
        for p in paths:
            if p.exists() and p.is_file():
                try:
                    content = p.read_text(encoding="utf-8").strip()
                    if content:
                        try:
                            with conn:
                                cur.execute(
                                    "UPDATE courses SET mindmap_code = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                                    (content, course_id),
                                )
                        except Exception:
                            pass
                        return content
                except Exception as e:
                    logger.warning(f"Erreur lecture carte mentale disque {p}: {e}")

        return None
    finally:
        conn.close()


def save_course_mindmap(course_id: int, mindmap_code: str) -> None:
    """Enregistre ou met à jour le schéma mindmap d'un cours en base SQLite et sur disque (double persistance)."""
    conn = get_connection()
    try:
        row = None
        with conn:
            cur = conn.cursor()
            try:
                cur.execute(
                    "UPDATE courses SET mindmap_code = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                    (mindmap_code, course_id),
                )
            except sqlite3.OperationalError:
                conn.execute("ALTER TABLE courses ADD COLUMN mindmap_code TEXT")
                cur.execute(
                    "UPDATE courses SET mindmap_code = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                    (mindmap_code, course_id),
                )
            cur.execute("SELECT file_path, user_id FROM courses WHERE id = ?", (course_id,))
            row = cur.fetchone()

        # Écriture physique sur disque (dual storage)
        if row and mindmap_code:
            paths = get_mindmap_disk_paths(course_id, row["file_path"], row["user_id"])
            for p in paths:
                try:
                    p.parent.mkdir(parents=True, exist_ok=True)
                    p.write_text(mindmap_code, encoding="utf-8")
                except Exception as e:
                    logger.warning(f"Impossible d'écrire la carte mentale sur disque à {p}: {e}")
    finally:
        conn.close()


def get_student_concept_mastery(user_id: int, course_id: int) -> List[Dict[str, Any]]:
    """Récupère les notions et leur statut d'assimilation pour un élève sur un cours (avec auto-réparation et purge des labels génériques)."""
    conn = get_connection()
    try:
        cur = conn.cursor()
        try:
            cur.execute(
                """
                SELECT id, user_id, course_id, concept_title, status, success_rate, attempts_count, last_context, updated_at
                FROM concept_mastery
                WHERE user_id = ? AND course_id = ?
                ORDER BY id ASC
                """,
                (user_id, course_id),
            )
            rows = [dict(r) for r in cur.fetchall()]
        except sqlite3.OperationalError:
            _ensure_concept_mastery_table(conn)
            cur.execute(
                """
                SELECT id, user_id, course_id, concept_title, status, success_rate, attempts_count, last_context, updated_at
                FROM concept_mastery
                WHERE user_id = ? AND course_id = ?
                ORDER BY id ASC
                """,
                (user_id, course_id),
            )
            rows = [dict(r) for r in cur.fetchall()]

        # Nettoyage et purge immédiate de toute méta-catégorie générique polluante résiduelle
        clean_rows: List[Dict[str, Any]] = []
        to_delete: List[int] = []
        for r in rows:
            if is_generic_concept(r["concept_title"]):
                to_delete.append(r["id"])
            else:
                clean_rows.append(r)

        if to_delete:
            try:
                with conn:
                    cur.execute(
                        f"DELETE FROM concept_mastery WHERE id IN ({','.join(['?'] * len(to_delete))})",
                        to_delete,
                    )
            except Exception:
                pass

        return clean_rows
    finally:
        conn.close()


def save_concept_mastery(
    user_id: int,
    course_id: int,
    concept_title: str,
    status: str,
    success_rate: float = 0.0,
    attempts_count: int = 0,
    last_context: Optional[str] = None,
) -> None:
    """Enregistre ou met à jour l'état d'assimilation d'une notion pour un élève (avec auto-réparation)."""
    conn = get_connection()
    try:
        with conn:
            cur = conn.cursor()
            query = """
                INSERT INTO concept_mastery (user_id, course_id, concept_title, status, success_rate, attempts_count, last_context, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(user_id, course_id, concept_title) DO UPDATE SET
                    status = excluded.status,
                    success_rate = excluded.success_rate,
                    attempts_count = excluded.attempts_count,
                    last_context = excluded.last_context,
                    updated_at = CURRENT_TIMESTAMP
            """
            try:
                cur.execute(
                    query,
                    (user_id, course_id, concept_title, status, success_rate, attempts_count, last_context),
                )
            except sqlite3.OperationalError:
                _ensure_concept_mastery_table(conn)
                cur.execute(
                    query,
                    (user_id, course_id, concept_title, status, success_rate, attempts_count, last_context),
                )
    finally:
        conn.close()




def evaluate_and_sync_concept_mastery(user_id: int, course_id: int) -> List[Dict[str, Any]]:
    """
    Évalue localement (0 appel API IA, 100% gratuit) le niveau d'assimilation de chaque notion clé
    RÉELLE d'un cours pour un élève donné en analysant ses quiz et son historique de chat avec Sanad.
    Nettoie et purge automatiquement les anciennes méta-catégories génériques obsolètes.
    """
    course = get_course_by_id(course_id)
    if not course:
        return []

    # 1. Extraction et garantie de notions concrètes et réelles du cours
    concepts = extract_real_course_concepts(course)

    conn = get_connection()
    try:
        with conn:
            cur = conn.cursor()
            _ensure_concept_mastery_table(conn)

            # Purger toute ancienne ligne contenant des notions génériques pour cet utilisateur et ce cours
            cur.execute("SELECT id, concept_title FROM concept_mastery WHERE user_id = ? AND course_id = ?", (user_id, course_id))
            for row in cur.fetchall():
                if is_generic_concept(row["concept_title"]):
                    cur.execute("DELETE FROM concept_mastery WHERE id = ?", (row["id"],))

            # Mettre à jour key_concepts_json du cours si nécessaire
            existing_kc = course.get("key_concepts") or []
            if not existing_kc or any(is_generic_concept(c) for c in existing_kc):
                cur.execute(
                    "UPDATE courses SET key_concepts_json = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                    (json.dumps(concepts, ensure_ascii=False), course_id),
                )

        # 2. Récupérer les quiz et tentatives de l'élève sur ce cours
        cur = conn.cursor()
        cur.execute(
            """
            SELECT score, total_questions, answers_json, completed_at
            FROM quiz_attempts
            WHERE course_id = ? AND user_id = ?
            ORDER BY completed_at DESC
            """,
            (course_id, user_id),
        )
        attempts = [dict(r) for r in cur.fetchall()]

        # 3. Récupérer l'historique du chat pour ce cours
        cur.execute(
            """
            SELECT role, content
            FROM chat_messages
            WHERE course_id = ? AND user_id = ?
            ORDER BY id DESC LIMIT 40
            """,
            (course_id, user_id),
        )
        chats = [dict(r) for r in cur.fetchall()]
    finally:
        conn.close()

    total_attempts = len(attempts)
    overall_rate = 0.0
    if total_attempts > 0:
        total_score = sum(a["score"] for a in attempts)
        total_q = sum(a["total_questions"] for a in attempts)
        overall_rate = round((total_score / total_q * 100), 1) if total_q > 0 else 0.0

    chat_text = " ".join([c["content"].lower() for c in chats])
    course_lang = course.get("language", "fr")
    results = []

    for concept in concepts:
        concept_words = [w.lower() for w in re.findall(r"\w+", concept) if len(w) > 3]

        concept_attempts = 0
        concept_scores = []

        if total_attempts > 0:
            for a in attempts:
                concept_attempts += 1
                if a.get("total_questions", 0) > 0:
                    concept_scores.append(a["score"] / a["total_questions"] * 100)

        in_chat = any(w in chat_text for w in concept_words) if concept_words else False

        if concept_attempts > 0:
            concept_rate = round(sum(concept_scores) / len(concept_scores), 1) if concept_scores else overall_rate
            if concept_rate >= 75.0:
                status = "mastered"
            elif concept_rate >= 50.0:
                status = "in_progress"
            else:
                status = "to_review"

            if course_lang == "ar":
                context = f"تم التقييم بناءً على {concept_attempts} اختبار(ات) (المعدل: {concept_rate}%)"
            elif course_lang == "en":
                context = f"Assessed across {concept_attempts} quiz attempt(s) (Average: {concept_rate}%)"
            else:
                context = f"Évalué sur {concept_attempts} entraînement(s) (Moyenne : {concept_rate}%)"
        else:
            concept_rate = 0.0
            if in_chat:
                status = "in_progress"
                if course_lang == "ar":
                    context = "تمت مناقشتها وتوضيحها خلال المحادثة مع الأستاذ سند"
                elif course_lang == "en":
                    context = "Discussed and reviewed in tutor conversations with Sanad"
                else:
                    context = "Abordé et discuté lors des échanges avec le tuteur Sanad"
            else:
                status = "untested"
                if course_lang == "ar":
                    context = "لم يتم تقييمها بعد في اختبار أو مناقشة"
                elif course_lang == "en":
                    context = "Not yet evaluated in quizzes or tutor chat"
                else:
                    context = "Pas encore évalué dans un quiz ou une discussion"

        save_concept_mastery(
            user_id=user_id,
            course_id=course_id,
            concept_title=concept,
            status=status,
            success_rate=concept_rate,
            attempts_count=concept_attempts,
            last_context=context,
        )
        results.append({
            "concept_title": concept,
            "status": status,
            "success_rate": concept_rate,
            "attempts_count": concept_attempts,
            "last_context": context,
        })

    return results


# ===========================================================================
# SYSTÈME DE RÉCOMPENSES & TROPHÉES PAR COURS (GAMIFICATION PÉDAGOGIQUE)
# ===========================================================================

# 1. Catalogue des 8 Trophées Dédiés à Chaque Leçon / Cours
COURSE_BADGE_CATALOG: List[Dict[str, Any]] = [
    {
        "key": "course_explored",
        "title": "📖 Explorateur du Cours",
        "category": "Fiche & Découverte",
        "description": "Consulter et étudier la fiche synthétique express de ce cours.",
        "target_value": 1,
        "unit": "fiche consultée",
        "icon": "📖",
    },
    {
        "key": "course_mindmap",
        "title": "🗺️ Cartographe Visuel",
        "category": "Schématisation",
        "description": "Générer ou explorer la carte mentale schématisée de cette leçon.",
        "target_value": 1,
        "unit": "carte mentale explorée",
        "icon": "🗺️",
    },
    {
        "key": "course_first_quiz",
        "title": "🎯 Premier Pas Validé",
        "category": "Évaluation",
        "description": "Compléter un premier quiz d'entraînement sur ce cours.",
        "target_value": 1,
        "unit": "quiz complété",
        "icon": "🎯",
    },
    {
        "key": "course_perfect_score",
        "title": "💯 Sans-Faute Magistral",
        "category": "Excellence",
        "description": "Obtenir un score parfait de 100% sans aucune faute à un quiz de ce cours.",
        "target_value": 1,
        "unit": "score parfait (100%)",
        "icon": "💯",
    },
    {
        "key": "course_three_quizzes",
        "title": "⚡ Guerrier de l'Entraînement",
        "category": "Assiduité",
        "description": "Passer au moins 3 quiz d'entraînement sur cette leçon pour ancrer la mémoire.",
        "target_value": 3,
        "unit": "quiz passés sur ce cours",
        "icon": "⚡",
    },
    {
        "key": "course_sanad_dialogue",
        "title": "💬 Disciple de Sanad",
        "category": "Dialogue Socratique",
        "description": "Poser au moins 2 questions d'approfondissement au tuteur Sanad sur ce cours.",
        "target_value": 2,
        "unit": "questions posées sur ce cours",
        "icon": "💬",
    },
    {
        "key": "course_concept_master",
        "title": "🧠 Maître des Notions",
        "category": "Maîtrise",
        "description": "Assimiler complètement au moins 2 notions clés de ce cours (statut assimilé).",
        "target_value": 2,
        "unit": "notions clés assimilées",
        "icon": "🧠",
    },
    {
        "key": "course_grand_master",
        "title": "👑 Grand Chelem de la Leçon",
        "category": "Couronne Suprême",
        "description": "Débloquer les 7 autres trophées de ce cours pour conquérir la couronne suprême !",
        "target_value": 7,
        "unit": "trophées du cours remportés",
        "icon": "👑",
    },
]

COURSE_BADGE_CATALOG_MAP: Dict[str, Dict[str, Any]] = {b["key"]: b for b in COURSE_BADGE_CATALOG}

# 2. Catalogue Global (compatibilité ascendante)
GLOBAL_BADGE_CATALOG: List[Dict[str, Any]] = [
    {
        "key": "first_quiz",
        "title": "🌟 Premier Pas",
        "category": "Quiz & Découverte",
        "description": "Compléter ton premier quiz d'évaluation pour tester tes connaissances.",
        "target_value": 1,
        "unit": "quiz complété",
        "icon": "🌟",
    },
    {
        "key": "perfect_score",
        "title": "🎯 Tir Parfait",
        "category": "Excellence",
        "description": "Obtenir un score parfait de 100% sans aucune erreur à un quiz.",
        "target_value": 1,
        "unit": "score parfait (100%)",
        "icon": "🎯",
    },
    {
        "key": "quiz_five",
        "title": "⚡ Assiduité",
        "category": "Entraînement",
        "description": "S'entraîner régulièrement en complétant au moins 5 quiz.",
        "target_value": 5,
        "unit": "quiz complétés",
        "icon": "⚡",
    },
    {
        "key": "quiz_ten",
        "title": "🏆 Champion des Quiz",
        "category": "Excellence",
        "description": "Atteindre le palier de 10 quiz terminés avec succès.",
        "target_value": 10,
        "unit": "quiz complétés",
        "icon": "🏆",
    },
    {
        "key": "course_explorer",
        "title": "📚 Explorateur",
        "category": "Curiosité",
        "description": "Consulter ou importer au moins 3 cours différents dans son espace.",
        "target_value": 3,
        "unit": "cours révisés",
        "icon": "📚",
    },
    {
        "key": "sanad_scholar",
        "title": "💬 Curieux avec Sanad",
        "category": "Dialogue Socratique",
        "description": "Poser au moins 5 questions au tuteur intelligent Sanad pour approfondir.",
        "target_value": 5,
        "unit": "questions posées",
        "icon": "💬",
    },
    {
        "key": "concept_master",
        "title": "🧠 Maître des Notions",
        "category": "Maîtrise",
        "description": "Assimiler complètement au moins 3 notions clés de cours.",
        "target_value": 3,
        "unit": "notions maîtrisées",
        "icon": "🧠",
    },
    {
        "key": "mindmap_pioneer",
        "title": "🗺️ Cartographe du Savoir",
        "category": "Schématisation",
        "description": "Consulter ou générer la carte mentale schématisée d'une leçon.",
        "target_value": 1,
        "unit": "carte mentale explorée",
        "icon": "🗺️",
    },
]

# Fusion complète pour consultation uniforme
BADGE_CATALOG: List[Dict[str, Any]] = COURSE_BADGE_CATALOG + GLOBAL_BADGE_CATALOG
BADGE_CATALOG_MAP: Dict[str, Dict[str, Any]] = {b["key"]: b for b in BADGE_CATALOG}
ALL_BADGES_MAP = BADGE_CATALOG_MAP


def get_badge_catalog(course_mode: Optional[bool] = None) -> List[Dict[str, Any]]:
    """Retourne la liste des trophées et badges disponibles dans le catalogue."""
    if course_mode is True:
        cat = COURSE_BADGE_CATALOG
    elif course_mode is False:
        cat = GLOBAL_BADGE_CATALOG
    else:
        cat = BADGE_CATALOG
    return [dict(b) for b in cat]


def get_user_badges(user_id: int, course_id: Optional[int] = None) -> List[Dict[str, Any]]:
    """Récupère les badges remportés par un utilisateur spécifique, avec filtre optionnel par cours."""
    conn = get_connection()
    try:
        cur = conn.cursor()
        if course_id is not None:
            cur.execute(
                """
                SELECT id, user_id, course_id, badge_key, unlocked_at, metadata_json
                FROM user_badges
                WHERE user_id = ? AND course_id = ?
                ORDER BY unlocked_at ASC
                """,
                (user_id, course_id),
            )
        else:
            cur.execute(
                """
                SELECT id, user_id, course_id, badge_key, unlocked_at, metadata_json
                FROM user_badges
                WHERE user_id = ?
                ORDER BY unlocked_at ASC
                """,
                (user_id,),
            )
        badges = []
        for r in cur.fetchall():
            d = dict(r)
            b_info = ALL_BADGES_MAP.get(d["badge_key"])
            if b_info:
                d.update({
                    "title": b_info["title"],
                    "category": b_info["category"],
                    "description": b_info["description"],
                    "icon": b_info["icon"],
                    "target_value": b_info["target_value"],
                    "unit": b_info["unit"],
                })
            badges.append(d)
        return badges
    finally:
        conn.close()


def award_badge(
    user_id: int,
    badge_key: str,
    metadata: Optional[Dict[str, Any]] = None,
    course_id: Optional[int] = None,
) -> bool:
    """
    Attribue un badge à un utilisateur (éventuellement rattaché à un cours) s'il ne l'a pas déjà débloqué.
    Retourne True si le badge est nouvellement attribué, False s'il était déjà débloqué.
    """
    conn = get_connection()
    try:
        with conn:
            cur = conn.cursor()
            if course_id is not None:
                cur.execute(
                    "SELECT 1 FROM user_badges WHERE user_id = ? AND course_id = ? AND badge_key = ?",
                    (user_id, course_id, badge_key),
                )
            else:
                cur.execute(
                    "SELECT 1 FROM user_badges WHERE user_id = ? AND (course_id IS NULL OR course_id = 0) AND badge_key = ?",
                    (user_id, badge_key),
                )
            if cur.fetchone():
                return False

            meta_json = json.dumps(metadata or {}, ensure_ascii=False)
            cur.execute(
                """
                INSERT INTO user_badges (user_id, course_id, badge_key, metadata_json)
                VALUES (?, ?, ?, ?)
                """,
                (user_id, course_id, badge_key, meta_json),
            )
            return cur.rowcount > 0
    finally:
        conn.close()


def evaluate_and_award_course_badges(user_id: int, course_id: int) -> List[Dict[str, Any]]:
    """
    Évalue et attribue en temps réel les trophées spécifiques à un cours pour un élève donné.
    Retourne la liste des nouveaux trophées débloqués sur ce cours.
    """
    course = get_course_by_id(course_id)
    if not course:
        return []

    conn = get_connection()
    try:
        cur = conn.cursor()
        # 1. Tentatives de quiz sur ce cours
        cur.execute("SELECT COUNT(id) as cnt FROM quiz_attempts WHERE user_id = ? AND course_id = ?", (user_id, course_id))
        course_quizzes = int(cur.fetchone()["cnt"])

        # 2. Quiz parfait sur ce cours (100%)
        cur.execute(
            """
            SELECT COUNT(id) as cnt 
            FROM quiz_attempts 
            WHERE user_id = ? AND course_id = ? AND score = total_questions AND total_questions > 0
            """,
            (user_id, course_id),
        )
        course_perfect = int(cur.fetchone()["cnt"])

        # 3. Questions posées à Sanad sur ce cours
        cur.execute(
            """
            SELECT COUNT(id) as cnt
            FROM chat_messages
            WHERE user_id = ? AND course_id = ? AND role = 'user'
            """,
            (user_id, course_id),
        )
        course_sanad_questions = int(cur.fetchone()["cnt"])

        # 4. Notions assimilées sur ce cours
        cur.execute(
            """
            SELECT COUNT(id) as cnt
            FROM concept_mastery
            WHERE user_id = ? AND course_id = ? AND status = 'mastered'
            """,
            (user_id, course_id),
        )
        course_mastered_concepts = int(cur.fetchone()["cnt"])
    finally:
        conn.close()

    has_summary = bool(course.get("summary_markdown") or course.get("raw_text"))
    has_mindmap = bool(course.get("mindmap_code") or get_course_mindmap(course_id))

    checks = [
        ("course_explored", has_summary, {"summary": True}),
        ("course_mindmap", has_mindmap, {"mindmap": True}),
        ("course_first_quiz", course_quizzes >= 1, {"attempts": course_quizzes}),
        ("course_perfect_score", course_perfect >= 1, {"perfect_quizzes": course_perfect}),
        ("course_three_quizzes", course_quizzes >= 3, {"attempts": course_quizzes}),
        ("course_sanad_dialogue", course_sanad_questions >= 2, {"sanad_questions": course_sanad_questions}),
        ("course_concept_master", course_mastered_concepts >= 2, {"mastered_concepts": course_mastered_concepts}),
    ]

    newly_awarded = []
    for badge_key, condition_met, meta in checks:
        if condition_met:
            if award_badge(user_id, badge_key, metadata=meta, course_id=course_id):
                info = COURSE_BADGE_CATALOG_MAP.get(badge_key, {})
                newly_awarded.append({
                    "key": badge_key,
                    "course_id": course_id,
                    "course_title": course.get("title", ""),
                    "title": info.get("title", badge_key),
                    "icon": info.get("icon", "🏆"),
                    "description": info.get("description", ""),
                })

    # Vérification du Grand Chelem du cours (les 7 autres trophées débloqués)
    current_badges = get_user_badges(user_id, course_id=course_id)
    unlocked_keys = {b["badge_key"] for b in current_badges}
    first_seven = [
        "course_explored", "course_mindmap", "course_first_quiz",
        "course_perfect_score", "course_three_quizzes", "course_sanad_dialogue",
        "course_concept_master"
    ]
    if all(k in unlocked_keys for k in first_seven):
        if award_badge(user_id, "course_grand_master", metadata={"grand_master": True}, course_id=course_id):
            info = COURSE_BADGE_CATALOG_MAP.get("course_grand_master", {})
            newly_awarded.append({
                "key": "course_grand_master",
                "course_id": course_id,
                "course_title": course.get("title", ""),
                "title": info.get("title", "Grand Chelem de la Leçon"),
                "icon": info.get("icon", "👑"),
                "description": info.get("description", ""),
            })

    return newly_awarded


def get_course_trophies_overview(user_id: int, course_id: int) -> Dict[str, Any]:
    """
    Construit l'état détaillé des trophées pour un cours spécifique :
    - Taux de complétion sur ce cours
    - Liste des 8 trophées avec statut (débloqué / en cours), progression et encouragement.
    """
    # 1. Évaluation dynamique préalable pour ce cours
    newly_awarded = evaluate_and_award_course_badges(user_id, course_id)

    course = get_course_by_id(course_id)
    if not course:
        return {
            "course_id": course_id,
            "course_title": "Cours introuvable",
            "subject": "",
            "total_trophies": len(COURSE_BADGE_CATALOG),
            "total_count": len(COURSE_BADGE_CATALOG),
            "unlocked_trophies": 0,
            "unlocked_count": 0,
            "completion_rate": 0.0,
            "badges": [],
            "newly_awarded": [],
        }

    unlocked_list = get_user_badges(user_id, course_id=course_id)
    unlocked_map = {b["badge_key"]: b for b in unlocked_list}

    # Métriques réelles sur ce cours
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("SELECT COUNT(id) as cnt FROM quiz_attempts WHERE user_id = ? AND course_id = ?", (user_id, course_id))
        course_quizzes = int(cur.fetchone()["cnt"])

        cur.execute(
            """
            SELECT COUNT(id) as cnt 
            FROM quiz_attempts 
            WHERE user_id = ? AND course_id = ? AND score = total_questions AND total_questions > 0
            """,
            (user_id, course_id),
        )
        course_perfect = int(cur.fetchone()["cnt"])

        cur.execute(
            """
            SELECT COUNT(id) as cnt
            FROM chat_messages
            WHERE user_id = ? AND course_id = ? AND role = 'user'
            """,
            (user_id, course_id),
        )
        course_sanad_questions = int(cur.fetchone()["cnt"])

        cur.execute(
            """
            SELECT COUNT(id) as cnt
            FROM concept_mastery
            WHERE user_id = ? AND course_id = ? AND status = 'mastered'
            """,
            (user_id, course_id),
        )
        course_mastered_concepts = int(cur.fetchone()["cnt"])
    finally:
        conn.close()

    has_summary = bool(course.get("summary_markdown") or course.get("raw_text"))
    has_mindmap = bool(course.get("mindmap_code") or get_course_mindmap(course_id))

    current_metrics = {
        "course_explored": 1 if has_summary else 0,
        "course_mindmap": 1 if has_mindmap else 0,
        "course_first_quiz": course_quizzes,
        "course_perfect_score": course_perfect,
        "course_three_quizzes": course_quizzes,
        "course_sanad_dialogue": course_sanad_questions,
        "course_concept_master": course_mastered_concepts,
        "course_grand_master": len(unlocked_list),
    }

    badges_detail = []
    for b in COURSE_BADGE_CATALOG:
        key = b["key"]
        target = b["target_value"]
        current_val = current_metrics.get(key, 0)
        is_unlocked = key in unlocked_map
        unlocked_at = unlocked_map[key]["unlocked_at"] if is_unlocked else None

        if is_unlocked:
            progress_ratio = 1.0
            progress_percent = 100
            status_text = "✨ Trophée Débloqué !"
            encouragement = f"Magnifique ! Objectif atteint ({target} {b['unit']})."
        else:
            progress_ratio = min(1.0, current_val / target) if target > 0 else 0.0
            progress_percent = int(progress_ratio * 100)
            remaining = max(0, target - current_val)
            status_text = f"🔒 En cours ({current_val} / {target})"
            encouragement = f"Plus que {remaining} {b['unit']} pour décrocher ce trophée !"

        badges_detail.append({
            "key": key,
            "title": b["title"],
            "category": b["category"],
            "description": b["description"],
            "icon": b["icon"],
            "target_value": target,
            "unit": b["unit"],
            "current_value": current_val,
            "is_unlocked": is_unlocked,
            "unlocked_at": unlocked_at,
            "progress_ratio": progress_ratio,
            "progress_percent": progress_percent,
            "status_text": status_text,
            "encouragement": encouragement,
        })

    unlocked_count = len(unlocked_list)
    total_count = len(COURSE_BADGE_CATALOG)
    rate = round((unlocked_count / total_count * 100), 1) if total_count > 0 else 0.0

    return {
        "course_id": course_id,
        "course_title": course.get("title", ""),
        "subject": course.get("subject", ""),
        "total_trophies": total_count,
        "total_count": total_count,
        "unlocked_trophies": unlocked_count,
        "unlocked_count": unlocked_count,
        "completion_rate": rate,
        "badges": badges_detail,
        "newly_awarded": newly_awarded,
    }


def get_student_trophies_by_course(user_id: int, subject: Optional[str] = None) -> Dict[str, Any]:
    """
    Calcule la vitrine globale de trophées de l'élève regroupée par cours :
    - Taux d'accomplissement général sur l'ensemble de ses cours
    - Titre honorifique / Rang d'apprentissage
    - Détail des trophées pour chaque cours individuel.
    """
    courses = list_courses(user_id=user_id, subject=subject)
    courses_trophies = []
    total_unlocked = 0

    for c in courses:
        cid = c["id"]
        c_ov = get_course_trophies_overview(user_id, cid)
        courses_trophies.append(c_ov)
        total_unlocked += c_ov["unlocked_trophies"]

    total_courses_cnt = len(courses)
    total_trophies_possible = total_courses_cnt * len(COURSE_BADGE_CATALOG)
    overall_rate = round((total_unlocked / total_trophies_possible * 100), 1) if total_trophies_possible > 0 else 0.0

    # Titre de rang honorifique
    if overall_rate >= 90 or (total_courses_cnt > 0 and total_unlocked >= total_courses_cnt * 7):
        rank = "👑 Légende Vivante d'Excellence"
        rank_color = "#eab308"
        rank_quote = "Sommet absolu ! Tous les cours sont maîtrisés avec brio !"
    elif overall_rate >= 65:
        rank = "💎 Grand Champion Académique"
        rank_color = "#a855f7"
        rank_quote = "Niveau d'excellence remarquable, continuez ainsi !"
    elif overall_rate >= 40:
        rank = "🥇 Maître des Épreuves"
        rank_color = "#fbbf24"
        rank_quote = "Une solide maîtrise des matières clés du programme !"
    elif overall_rate >= 15:
        rank = "🥈 Érudit des Révisions"
        rank_color = "#38bdf8"
        rank_quote = "Belle régularité dans l'effort et les entraînements !"
    else:
        rank = "🥉 Apprenti Explorateur"
        rank_color = "#f97316"
        rank_quote = "Chaque grande réussite commence par une première leçon !"

    return {
        "total_courses": total_courses_cnt,
        "total_trophies": total_trophies_possible,
        "total_count": total_trophies_possible,
        "unlocked_trophies": total_unlocked,
        "unlocked_count": total_unlocked,
        "completion_rate": overall_rate,
        "rank": rank,
        "rank_color": rank_color,
        "rank_quote": rank_quote,
        "courses_trophies": courses_trophies,
    }


def evaluate_and_award_badges(user_id: int, course_id: Optional[int] = None) -> List[Dict[str, Any]]:
    """
    Évalue et attribue les trophées d'un cours (si course_id fourni) ou de l'ensemble
    des cours de l'élève, ainsi que les trophées globaux pour rétrocompatibilité.
    """
    newly_awarded = []

    # 1. Évaluation spécifique par cours
    if course_id is not None:
        newly_awarded.extend(evaluate_and_award_course_badges(user_id, course_id))
    else:
        # Parcours de tous les cours de l'élève
        courses = list_courses(user_id=user_id)
        for c in courses:
            newly_awarded.extend(evaluate_and_award_course_badges(user_id, c["id"]))

    # 2. Évaluation des badges globaux (rétrocompatibilité)
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("SELECT COUNT(id) as cnt FROM quiz_attempts WHERE user_id = ?", (user_id,))
        total_quizzes = int(cur.fetchone()["cnt"])

        cur.execute(
            """
            SELECT COUNT(id) as cnt 
            FROM quiz_attempts 
            WHERE user_id = ? AND score = total_questions AND total_questions > 0
            """,
            (user_id,),
        )
        perfect_quizzes = int(cur.fetchone()["cnt"])

        cur.execute("SELECT COUNT(DISTINCT id) as cnt FROM courses WHERE user_id = ? OR user_id IS NULL", (user_id,))
        total_courses = int(cur.fetchone()["cnt"])

        cur.execute("SELECT COUNT(id) as cnt FROM chat_messages WHERE user_id = ? AND role = 'user'", (user_id,))
        sanad_questions = int(cur.fetchone()["cnt"])

        cur.execute("SELECT COUNT(id) as cnt FROM concept_mastery WHERE user_id = ? AND status = 'mastered'", (user_id,))
        mastered_concepts = int(cur.fetchone()["cnt"])

        cur.execute(
            """
            SELECT COUNT(id) as cnt
            FROM courses
            WHERE (user_id = ? OR user_id IS NULL) 
              AND mindmap_code IS NOT NULL 
              AND TRIM(mindmap_code) != ''
            """,
            (user_id,),
        )
        mindmaps_count = int(cur.fetchone()["cnt"])
    finally:
        conn.close()

    global_checks = [
        ("first_quiz", total_quizzes >= 1, {"total_quizzes": total_quizzes}),
        ("perfect_score", perfect_quizzes >= 1, {"perfect_quizzes": perfect_quizzes}),
        ("quiz_five", total_quizzes >= 5, {"total_quizzes": total_quizzes}),
        ("quiz_ten", total_quizzes >= 10, {"total_quizzes": total_quizzes}),
        ("course_explorer", total_courses >= 3, {"total_courses": total_courses}),
        ("sanad_scholar", sanad_questions >= 5, {"sanad_questions": sanad_questions}),
        ("concept_master", mastered_concepts >= 3, {"mastered_concepts": mastered_concepts}),
        ("mindmap_pioneer", mindmaps_count >= 1, {"mindmaps_count": mindmaps_count}),
    ]

    for key, condition, meta in global_checks:
        if condition:
            is_new = award_badge(user_id, key, metadata=meta)
            if is_new and key in BADGE_CATALOG_MAP:
                newly_awarded.append(BADGE_CATALOG_MAP[key])

    return newly_awarded


def get_student_trophies_overview(user_id: int, course_id: Optional[int] = None) -> Dict[str, Any]:
    """
    Construit la vue détaillée des trophées pour l'élève :
    - Si course_id spécifié : retourne l'overview spécifique à ce cours.
    - Si course_id None : retourne la vue globale multi-cours avec compatibilité ascendante.
    """
    if course_id is not None:
        return get_course_trophies_overview(user_id, course_id)

    # Évaluation générale préalable
    evaluate_and_award_badges(user_id)
    by_course = get_student_trophies_by_course(user_id)

    # Récupération de tous les badges de l'élève (cours + globaux)
    all_unlocked = get_user_badges(user_id)
    unlocked_map = {b["badge_key"]: b for b in all_unlocked}

    # Mesures réelles de progression pour les badges globaux
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("SELECT COUNT(id) as cnt FROM quiz_attempts WHERE user_id = ?", (user_id,))
        total_quizzes = int(cur.fetchone()["cnt"])

        cur.execute(
            """
            SELECT COUNT(id) as cnt 
            FROM quiz_attempts 
            WHERE user_id = ? AND score = total_questions AND total_questions > 0
            """,
            (user_id,),
        )
        perfect_quizzes = int(cur.fetchone()["cnt"])

        cur.execute(
            """
            SELECT COUNT(DISTINCT id) as cnt
            FROM courses
            WHERE user_id = ? OR user_id IS NULL
            """,
            (user_id,),
        )
        total_courses = int(cur.fetchone()["cnt"])

        cur.execute(
            """
            SELECT COUNT(id) as cnt
            FROM chat_messages
            WHERE user_id = ? AND role = 'user'
            """,
            (user_id,),
        )
        sanad_questions = int(cur.fetchone()["cnt"])

        cur.execute(
            """
            SELECT COUNT(id) as cnt
            FROM concept_mastery
            WHERE user_id = ? AND status = 'mastered'
            """,
            (user_id,),
        )
        mastered_concepts = int(cur.fetchone()["cnt"])

        cur.execute(
            """
            SELECT COUNT(id) as cnt
            FROM courses
            WHERE (user_id = ? OR user_id IS NULL) 
              AND mindmap_code IS NOT NULL 
              AND TRIM(mindmap_code) != ''
            """,
            (user_id,),
        )
        mindmaps_count = int(cur.fetchone()["cnt"])
    finally:
        conn.close()

    current_metrics = {
        "first_quiz": total_quizzes,
        "perfect_score": perfect_quizzes,
        "quiz_five": total_quizzes,
        "quiz_ten": total_quizzes,
        "course_explorer": total_courses,
        "sanad_scholar": sanad_questions,
        "concept_master": mastered_concepts,
        "mindmap_pioneer": mindmaps_count,
    }

    # Liste formatée des badges pour compatibilité ascendante
    badges_detail = []
    for b in GLOBAL_BADGE_CATALOG:
        key = b["key"]
        target = b["target_value"]
        current_val = current_metrics.get(key, 0)
        is_unlocked = key in unlocked_map
        unlocked_at = unlocked_map[key]["unlocked_at"] if is_unlocked else None

        if is_unlocked:
            progress_ratio = 1.0
            progress_percent = 100
            status_text = "✨ Trophée Remporté !"
            encouragement = f"Bravo ! Tu as atteint l'objectif ({target} {b['unit']})."
        else:
            progress_ratio = min(1.0, current_val / target) if target > 0 else 0.0
            progress_percent = int(progress_ratio * 100)
            remaining = max(0, target - current_val)
            status_text = f"🔒 En cours ({current_val} / {target})"
            encouragement = f"Plus que {remaining} {b['unit']} pour remporter ce trophée !"

        badges_detail.append({
            "key": key,
            "title": b["title"],
            "category": b["category"],
            "description": b["description"],
            "icon": b["icon"],
            "target_value": target,
            "unit": b["unit"],
            "current_value": current_val,
            "is_unlocked": is_unlocked,
            "unlocked_at": unlocked_at,
            "progress_ratio": progress_ratio,
            "progress_percent": progress_percent,
            "status_text": status_text,
            "encouragement": encouragement,
        })

    # Rétrocompatibilité : inclut toutes les métriques de cours et de rang
    res = dict(by_course)
    res["badges"] = badges_detail
    return res

