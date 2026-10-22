"""
Module de sauvegarde, export et restauration étanche pour Ecole Adnane.
Supporte :
1. Sauvegarde / Restauration personnelle pour chaque élève (ZIP + data.json + PDFs isolés).
2. Sauvegarde / Restauration globale pour l'administrateur (Base complète + storage/users/).
3. Export / Restauration ciblée par élève pour l'administrateur.
4. Protection stricte contre les attaques par traversée de répertoire (path traversal).
"""

import io
import json
import logging
import os
import shutil
import sqlite3
import tempfile
import zipfile
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from models.database import (
    get_connection,
    get_db_path,
    get_user_by_id,
    get_user_count,
    list_users,
    init_db,
    save_course,
    save_course_mindmap,
    save_quiz,
    save_quiz_attempt,
    add_chat_message,
    save_flashcard,
)
from services.downloader import get_user_storage_dir, USERS_DIR, STORAGE_DIR

logger = logging.getLogger(__name__)

SQLITE_HEADER = b"SQLite format 3\x00"


def is_safe_extract_path(dest_dir: Path, target_path: Path) -> bool:
    """Vérifie qu'un chemin d'extraction ne sort pas du dossier de destination (anti-traversal)."""
    try:
        dest_resolved = dest_dir.resolve()
        target_resolved = target_path.resolve()
        return target_resolved.is_relative_to(dest_resolved)
    except Exception:
        return False


# ===========================================================================
# 1. SAUVEGARDE & RESTAURATION PERSONNELLE (ÉLÈVE)
# ===========================================================================

def get_student_backup_summary(user_id: int) -> Dict[str, int]:
    """Compte les données associées à un élève spécifique."""
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("SELECT count(*) FROM courses WHERE user_id = ?", (user_id,))
        courses = cur.fetchone()[0]

        cur.execute("SELECT count(*) FROM quizzes WHERE user_id = ?", (user_id,))
        quizzes = cur.fetchone()[0]

        cur.execute("SELECT count(*) FROM quiz_attempts WHERE user_id = ?", (user_id,))
        attempts = cur.fetchone()[0]

        cur.execute("SELECT count(*) FROM chat_messages WHERE user_id = ?", (user_id,))
        messages = cur.fetchone()[0]

        cur.execute("SELECT count(*) FROM flashcards WHERE user_id = ?", (user_id,))
        flashcards = cur.fetchone()[0]

        cur.execute("SELECT count(*) FROM user_badges WHERE user_id = ?", (user_id,))
        badges = cur.fetchone()[0]

        return {
            "courses": courses,
            "quizzes": quizzes,
            "attempts": attempts,
            "messages": messages,
            "flashcards": flashcards,
            "badges": badges,
            "badge_count": badges,
        }
    except Exception as e:
        logger.error(f"Erreur résumé élève {user_id}: {e}")
        return {"courses": 0, "quizzes": 0, "attempts": 0, "messages": 0, "flashcards": 0, "badges": 0, "badge_count": 0}
    finally:
        conn.close()


def export_student_backup(user_id: int) -> bytes:
    """
    Exporte toutes les révisions d'un élève dans un fichier ZIP en mémoire :
    - Les fichiers PDF originaux de l'élève (storage/users/<user_id>/cours/)
    - data.json : cours, fiches, quiz, résultats et historique tuteur liés à son user_id
    - manifest.json : métadonnées de l'élève et horodatage
    """
    user = get_user_by_id(user_id)
    if not user:
        raise ValueError(f"Utilisateur introuvable avec l'ID {user_id}")

    conn = get_connection()
    try:
        cur = conn.cursor()

        # 1. Cours de l'élève
        cur.execute("SELECT * FROM courses WHERE user_id = ?", (user_id,))
        courses = [dict(r) for r in cur.fetchall()]

        # 2. Quiz de l'élève
        cur.execute("SELECT * FROM quizzes WHERE user_id = ?", (user_id,))
        quizzes = [dict(r) for r in cur.fetchall()]

        # 3. Tentatives / Résultats de l'élève
        cur.execute("SELECT * FROM quiz_attempts WHERE user_id = ?", (user_id,))
        attempts = [dict(r) for r in cur.fetchall()]

        # 4. Historique de discussion avec Sanad
        cur.execute("SELECT * FROM chat_messages WHERE user_id = ?", (user_id,))
        messages = [dict(r) for r in cur.fetchall()]

        # 5. Flashcards
        cur.execute("SELECT * FROM flashcards WHERE user_id = ?", (user_id,))
        flashcards = [dict(r) for r in cur.fetchall()]

        # 6. Badges & Trophées
        cur.execute("SELECT * FROM user_badges WHERE user_id = ?", (user_id,))
        badges = [dict(r) for r in cur.fetchall()]

    finally:
        conn.close()

    data_payload = {
        "user_email": user["email"],
        "user_name": user["name"],
        "courses": courses,
        "quizzes": quizzes,
        "quiz_attempts": attempts,
        "chat_messages": messages,
        "flashcards": flashcards,
        "badges": badges,
    }

    stats = get_student_backup_summary(user_id)
    manifest = {
        "app": "Ecole Adnane",
        "type": "student_backup",
        "version": "2.0.0",
        "exported_at": datetime.now().isoformat(),
        "user": {"email": user["email"], "name": user["name"], "role": user["role"]},
        "stats": stats,
    }

    user_storage_dir = get_user_storage_dir(user_id)

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        # Fichiers JSON
        zf.writestr("manifest.json", json.dumps(manifest, indent=2, ensure_ascii=False))
        zf.writestr("data.json", json.dumps(data_payload, indent=2, ensure_ascii=False))

        # Fichiers PDF et cartes mentales originaux de l'élève
        if user_storage_dir.exists():
            for pdf_file in user_storage_dir.glob("*.pdf"):
                zf.write(pdf_file, arcname=f"cours/{pdf_file.name}")
            for map_file in user_storage_dir.glob("*.mindmap.md"):
                zf.write(map_file, arcname=f"cours/{map_file.name}")

    buf.seek(0)
    return buf.getvalue()


def restore_student_backup(file_bytes: bytes, target_user_id: int) -> Dict[str, Any]:
    """
    Restaure les cours et l'historique d'un élève dans son espace personnel.
    Garantit le cloisonnement : toutes les données insérées reçoivent strictement target_user_id.
    Supporte :
    1. Archives modernes v2.0 (ZIP avec data.json et PDFs).
    2. Archives héritées v1.0 (ZIP avec ecole_adnane.db et PDFs).
    3. Fichiers SQLite bruts (.db ou .sqlite).
    Ne remplace jamais la base active ecole_adnane.db, préservant la session utilisateur.
    Protège contre les attaques de traversée de répertoire (path traversal).
    """
    if not file_bytes:
        return {"success": False, "error": "Le fichier téléversé est vide."}

    user = get_user_by_id(target_user_id)
    if not user:
        return {"success": False, "error": f"Utilisateur cible introuvable (ID: {target_user_id})."}

    user_storage_dir = get_user_storage_dir(target_user_id)
    user_storage_dir.mkdir(parents=True, exist_ok=True)

    extracted_pdfs = 0
    data = None
    temp_db_path: Optional[Path] = None

    try:
        # Cas 1 : Fichier SQLite brut
        if file_bytes.startswith(SQLITE_HEADER):
            with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
                tmp.write(file_bytes)
                temp_db_path = Path(tmp.name)

        # Cas 2 : Archive ZIP (v2.0 ou v1.0 legacy)
        else:
            buf = io.BytesIO(file_bytes)
            with zipfile.ZipFile(buf, "r") as zf:
                # Vérifier que ce n'est pas un zip malveillant
                for member in zf.infolist():
                    filename = member.filename
                    if ".." in filename or filename.startswith("/") or filename.startswith("\\"):
                        return {"success": False, "error": "Tentative de traversée de répertoire détectée."}

                # 1. Extraire les PDFs et cartes mentales de manière sécurisée
                for member in zf.infolist():
                    name_lower = member.filename.lower()
                    if name_lower.endswith(".pdf") or name_lower.endswith(".mindmap.md"):
                        safe_name = Path(member.filename).name
                        if safe_name:
                            dest_file = user_storage_dir / safe_name
                            if is_safe_extract_path(user_storage_dir, dest_file):
                                with zf.open(member) as src, open(dest_file, "wb") as dst:
                                    shutil.copyfileobj(src, dst)
                                if name_lower.endswith(".pdf"):
                                    extracted_pdfs += 1

                # 2a. Archive moderne v2.0 avec data.json
                if "data.json" in zf.namelist():
                    raw_data = zf.read("data.json").decode("utf-8")
                    data = json.loads(raw_data)
                else:
                    # 2b. Archive legacy v1.0 avec base SQLite interne
                    db_entry = None
                    for name in zf.namelist():
                        if name == "ecole_adnane.db" or name.lower().endswith((".db", ".sqlite")):
                            db_entry = name
                            break

                    if not db_entry:
                        return {
                            "success": False,
                            "error": "Archive non reconnue : ni data.json ni fichier de base SQLite (.db) détectés."
                        }

                    db_content = zf.read(db_entry)
                    if not db_content.startswith(SQLITE_HEADER):
                        return {"success": False, "error": "Le fichier de base dans l'archive n'est pas une base de données SQLite valide."}

                    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
                        tmp.write(db_content)
                        temp_db_path = Path(tmp.name)

        # Si on a extrait une base SQLite temporaire (cas 1 ou 2b) :
        if temp_db_path is not None:
            legacy_conn = sqlite3.connect(temp_db_path)
            legacy_conn.row_factory = sqlite3.Row
            try:
                l_cur = legacy_conn.cursor()
                l_cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
                tables = {row["name"] for row in l_cur.fetchall()}

                courses = [dict(r) for r in l_cur.execute("SELECT * FROM courses").fetchall()] if "courses" in tables else []
                quizzes = [dict(r) for r in l_cur.execute("SELECT * FROM quizzes").fetchall()] if "quizzes" in tables else []
                attempts = [dict(r) for r in l_cur.execute("SELECT * FROM quiz_attempts").fetchall()] if "quiz_attempts" in tables else []
                messages = [dict(r) for r in l_cur.execute("SELECT * FROM chat_messages").fetchall()] if "chat_messages" in tables else []
                flashcards = [dict(r) for r in l_cur.execute("SELECT * FROM flashcards").fetchall()] if "flashcards" in tables else []

                data = {
                    "courses": courses,
                    "quizzes": quizzes,
                    "quiz_attempts": attempts,
                    "chat_messages": messages,
                    "flashcards": flashcards,
                }
            finally:
                legacy_conn.close()
                try:
                    temp_db_path.unlink()
                except Exception:
                    pass

        if not data:
            return {"success": False, "error": "Aucune donnée exploitable trouvée dans la sauvegarde."}

        # 3. Assurer que le schéma de la base est à jour et insérer les données sous target_user_id
        init_db()

        course_id_map: Dict[int, int] = {}
        restored_courses = 0
        restored_quizzes = 0
        restored_attempts = 0
        restored_chats = 0
        restored_cards = 0

        # Ingestion des cours
        for c in data.get("courses", []):
            old_id = c["id"]
            file_name = c["file_name"]
            file_hash = c["file_hash"]
            # Retrouver le PDF extrait correspondant
            matched_file = None
            for pdf_candidate in user_storage_dir.glob(f"*{file_hash[:8]}*"):
                matched_file = str(pdf_candidate)
                break
            if not matched_file:
                matched_file = str(user_storage_dir / file_name)

            try:
                key_concepts = json.loads(c.get("key_concepts_json") or "[]")
            except Exception:
                key_concepts = []

            mindmap_code = c.get("mindmap_code")
            new_cid = save_course(
                title=c["title"],
                subject=c["subject"],
                language=c["language"],
                file_path=matched_file,
                file_hash=file_hash,
                file_name=file_name,
                raw_text=c.get("raw_text") or "",
                summary_markdown=c.get("summary_markdown"),
                key_concepts=key_concepts,
                user_id=target_user_id,
                mindmap_code=mindmap_code,
            )
            if mindmap_code:
                try:
                    save_course_mindmap(new_cid, mindmap_code)
                except Exception:
                    pass
            course_id_map[old_id] = new_cid
            restored_courses += 1

        # Ingestion des quiz
        quiz_id_map: Dict[int, int] = {}
        for q in data.get("quizzes", []):
            old_cid = q["course_id"]
            new_cid = course_id_map.get(old_cid)
            if new_cid:
                try:
                    q_data = json.loads(q.get("quiz_data_json") or "[]")
                except Exception:
                    q_data = []
                new_qid = save_quiz(course_id=new_cid, quiz_data=q_data, user_id=target_user_id)
                quiz_id_map[q["id"]] = new_qid
                restored_quizzes += 1

        # Ingestion des tentatives de quiz
        for a in data.get("quiz_attempts", []):
            new_cid = course_id_map.get(a["course_id"])
            new_qid = quiz_id_map.get(a["quiz_id"])
            if new_cid and new_qid:
                try:
                    ans = json.loads(a.get("answers_json") or "{}")
                except Exception:
                    ans = {}
                save_quiz_attempt(
                    course_id=new_cid,
                    quiz_id=new_qid,
                    score=a["score"],
                    total_questions=a["total_questions"],
                    answers=ans,
                    user_id=target_user_id,
                )
                restored_attempts += 1

        # Ingestion de l'historique Sanad
        for m in data.get("chat_messages", []):
            new_cid = course_id_map.get(m["course_id"])
            if new_cid:
                add_chat_message(
                    course_id=new_cid,
                    role=m["role"],
                    content=m["content"],
                    user_id=target_user_id,
                )
                restored_chats += 1

        # Ingestion des flashcards
        for f in data.get("flashcards", []):
            new_cid = course_id_map.get(f["course_id"])
            if new_cid:
                save_flashcard(
                    user_id=target_user_id,
                    course_id=new_cid,
                    front=f["front"],
                    back=f["back"],
                )
                restored_cards += 1

        # Ingestion des badges
        restored_badges = 0
        for b in data.get("badges", []):
            try:
                b_key = b.get("badge_key")
                if b_key:
                    conn = get_connection()
                    with conn:
                        conn.execute(
                            """
                            INSERT OR IGNORE INTO user_badges (user_id, badge_key, unlocked_at, metadata_json)
                            VALUES (?, ?, COALESCE(?, CURRENT_TIMESTAMP), ?)
                            """,
                            (target_user_id, b_key, b.get("unlocked_at"), b.get("metadata_json")),
                        )
                    restored_badges += 1
            except Exception:
                pass

        return {
            "success": True,
            "message": (
                f"Restauration réussie pour {user['name']} ! {restored_courses} cours, "
                f"{restored_quizzes} quiz, {restored_attempts} entraînements et "
                f"{restored_chats} échanges avec l'IA Sanad restaurés."
            ),
            "stats": {
                "courses": restored_courses,
                "quizzes": restored_quizzes,
                "attempts": restored_attempts,
                "messages": restored_chats,
                "flashcards": restored_cards,
                "badges": restored_badges,
                "pdfs": extracted_pdfs,
            },
        }

    except Exception as e:
        logger.error(f"Erreur lors de la restauration élève: {e}", exc_info=True)
        return {"success": False, "error": f"Erreur lors de la restauration : {str(e)}"}


# ===========================================================================
# 2. SAUVEGARDE & RESTAURATION GLOBALE (ADMINISTRATEUR)
# ===========================================================================

def get_backup_summary() -> Dict[str, int]:
    """Compte global pour toute la base SQLite."""
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("SELECT count(*) FROM users")
        users = cur.fetchone()[0]

        cur.execute("SELECT count(*) FROM courses")
        courses = cur.fetchone()[0]

        cur.execute("SELECT count(*) FROM quizzes")
        quizzes = cur.fetchone()[0]

        cur.execute("SELECT count(*) FROM quiz_attempts")
        attempts = cur.fetchone()[0]

        cur.execute("SELECT count(*) FROM chat_messages")
        messages = cur.fetchone()[0]

        return {
            "users": users,
            "courses": courses,
            "quizzes": quizzes,
            "attempts": attempts,
            "messages": messages,
        }
    except Exception as e:
        logger.error(f"Erreur résumé global: {e}")
        return {"users": 0, "courses": 0, "quizzes": 0, "attempts": 0, "messages": 0}
    finally:
        conn.close()


def export_global_backup() -> bytes:
    """
    Génère une archive ZIP complète intégrant :
    - La base SQLite ecole_adnane.db complète (utilisateurs, cours, quiz, chats, paramètres)
    - L'intégralité du dossier storage/users/ (tous les dossiers et PDFs de chaque élève)
    - manifest.json
    """
    db_path = get_db_path()
    init_db(db_path)

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        # 1. Base SQLite complète
        if db_path.exists():
            zf.write(db_path, arcname="ecole_adnane.db")

        # 2. Dossiers des utilisateurs (storage/users/)
        if USERS_DIR.exists():
            for root, _, files in os.walk(USERS_DIR):
                for f in files:
                    full_p = Path(root) / f
                    rel_p = full_p.relative_to(STORAGE_DIR)
                    zf.write(full_p, arcname=str(rel_p))

        # 3. Dossier cours legacy si présent
        legacy_dir = STORAGE_DIR / "cours"
        if legacy_dir.exists():
            for f in legacy_dir.iterdir():
                if f.is_file() and (f.suffix.lower() == ".pdf" or f.name.endswith(".mindmap.md")):
                    zf.write(f, arcname=f"cours/{f.name}")

        # 4. Manifeste système
        stats = get_backup_summary()
        manifest = {
            "app": "Ecole Adnane",
            "type": "global_system_backup",
            "version": "2.0.0",
            "exported_at": datetime.now().isoformat(),
            "stats": stats,
        }
        zf.writestr("manifest.json", json.dumps(manifest, indent=2, ensure_ascii=False))

    buf.seek(0)
    return buf.getvalue()


def restore_global_backup(file_bytes: bytes) -> Dict[str, Any]:
    """
    Restaure l'intégralité du système à partir d'une sauvegarde globale ZIP.
    Valide l'en-tête SQLite et applique la protection anti-traversal.
    Préserve les comptes utilisateurs existants pour ne jamais couper la session administrateur.
    """
    if not file_bytes:
        return {"success": False, "error": "Le fichier téléversé est vide."}

    db_path = get_db_path()
    db_path.parent.mkdir(parents=True, exist_ok=True)
    STORAGE_DIR.mkdir(parents=True, exist_ok=True)

    # 1. Sauvegarder en mémoire les utilisateurs actuels au cas où la base restaurée n'a pas de table users
    existing_users = []
    existing_settings = []
    if db_path.exists():
        try:
            conn_curr = get_connection()
            cur_curr = conn_curr.cursor()
            cur_curr.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='users'")
            if cur_curr.fetchone():
                cur_curr.execute("SELECT * FROM users")
                existing_users = [dict(r) for r in cur_curr.fetchall()]
            cur_curr.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='user_settings'")
            if cur_curr.fetchone():
                cur_curr.execute("SELECT * FROM user_settings")
                existing_settings = [dict(r) for r in cur_curr.fetchall()]
            conn_curr.close()
        except Exception as e_curr:
            logger.warning(f"Impossible de lire les utilisateurs actuels avant restauration : {e_curr}")

    try:
        buf = io.BytesIO(file_bytes)
        with zipfile.ZipFile(buf, "r") as zf:
            # Vérifier la présence d'une base SQLite valide
            db_entry = None
            for name in zf.namelist():
                if name == "ecole_adnane.db" or name.endswith(".db"):
                    db_entry = name
                    break

            if not db_entry:
                return {"success": False, "error": "L'archive ne contient aucune base de données SQLite valide."}

            db_content = zf.read(db_entry)
            if not db_content.startswith(SQLITE_HEADER):
                return {"success": False, "error": "Le fichier de base n'est pas une base de données SQLite valide."}

            # Restaurer la base
            with open(db_path, "wb") as f:
                f.write(db_content)

            # Restaurer les fichiers utilisateurs
            extracted_files = 0
            for member in zf.infolist():
                if member.filename in (db_entry, "manifest.json") or member.is_dir():
                    continue

                # Vérification anti-traversal
                dest_file = STORAGE_DIR / member.filename
                if is_safe_extract_path(STORAGE_DIR, dest_file):
                    dest_file.parent.mkdir(parents=True, exist_ok=True)
                    with zf.open(member) as src, open(dest_file, "wb") as dst:
                        shutil.copyfileobj(src, dst)
                    extracted_files += 1

        init_db(db_path)

        # Si la base restaurée était une version legacy sans table users, réinsérer les comptes actifs
        if get_user_count() == 0 and existing_users:
            conn_re = get_connection()
            try:
                with conn_re:
                    cur_re = conn_re.cursor()
                    for u in existing_users:
                        cur_re.execute(
                            "INSERT OR REPLACE INTO users (id, email, name, avatar_url, role, created_at) VALUES (?, ?, ?, ?, ?, ?)",
                            (u["id"], u["email"], u["name"], u.get("avatar_url"), u["role"], u.get("created_at")),
                        )
                    for s in existing_settings:
                        cur_re.execute(
                            "INSERT OR REPLACE INTO user_settings (user_id, key, value) VALUES (?, ?, ?)",
                            (s["user_id"], s["key"], s["value"]),
                        )
            finally:
                conn_re.close()

        stats = get_backup_summary()
        return {
            "success": True,
            "message": (
                f"Restauration globale réussie ! {stats['users']} utilisateurs, {stats['courses']} cours, "
                f"{stats['quizzes']} quiz et {stats['messages']} discussions IA restaurés."
            ),
            "stats": stats,
        }

    except Exception as e:
        logger.error(f"Erreur restauration globale: {e}", exc_info=True)
        return {"success": False, "error": f"Erreur lors de la restauration : {str(e)}"}


# ===========================================================================
# FONCTIONS DE COMPATIBILITÉ
# ===========================================================================

def export_backup_zip() -> bytes:
    """Compatibilité : redirige vers export_global_backup()."""
    return export_global_backup()


def export_database_file() -> bytes:
    """Retourne directement les octets du fichier SQLite ecole_adnane.db."""
    db_path = get_db_path()
    init_db(db_path)
    with open(db_path, "rb") as f:
        return f.read()


def restore_backup(file_bytes: bytes, filename: str) -> Dict[str, Any]:
    """Compatibilité : restauration globale par défaut si appelé directement."""
    if filename.lower().endswith((".db", ".sqlite")) or file_bytes.startswith(SQLITE_HEADER):
        db_path = get_db_path()
        with open(db_path, "wb") as f:
            f.write(file_bytes)
        init_db(db_path)
        stats = get_backup_summary()
        return {"success": True, "message": "Base SQLite restaurée avec succès !", "stats": stats}
    return restore_global_backup(file_bytes)
