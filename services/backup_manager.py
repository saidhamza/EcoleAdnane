"""
Module de sauvegarde, export et restauration pour Ecole Adnane.
Permet d'exporter l'intégralité des données (cours, fiches, quiz, discussions avec l'IA Sanad et PDFs)
dans un fichier ZIP ou SQLite autonome pour garantir la persistance même sur le cloud.
"""

import io
import json
import logging
import os
import shutil
import sqlite3
import zipfile
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

from models.database import get_connection, get_db_path, init_db

logger = logging.getLogger(__name__)

STORAGE_DIR = Path(__file__).parent.parent / "storage"
COURSES_DIR = STORAGE_DIR / "cours"
SQLITE_HEADER = b"SQLite format 3\x00"


def get_backup_summary() -> Dict[str, int]:
    """Compte le nombre d'éléments actuellement présents dans la base."""
    db_path = get_db_path()
    if not db_path.exists():
        return {"courses": 0, "quizzes": 0, "attempts": 0, "messages": 0}

    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("SELECT count(*) FROM courses")
        courses = cur.fetchone()[0]

        cur.execute("SELECT count(*) FROM quizzes")
        quizzes = cur.fetchone()[0]

        cur.execute("SELECT count(*) FROM quiz_attempts")
        attempts = cur.fetchone()[0]

        cur.execute("SELECT count(*) FROM chat_messages")
        messages = cur.fetchone()[0]

        return {
            "courses": courses,
            "quizzes": quizzes,
            "attempts": attempts,
            "messages": messages,
        }
    except Exception as e:
        logger.error(f"Erreur lors du calcul du résumé de sauvegarde : {e}")
        return {"courses": 0, "quizzes": 0, "attempts": 0, "messages": 0}
    finally:
        conn.close()


def export_backup_zip() -> bytes:
    """
    Génère une archive ZIP complète contenant :
    - La base SQLite ecole_adnane.db (cours, quiz, fiches, chats IA)
    - Tous les documents PDF originaux dans cours/
    - Un fichier manifest.json
    """
    db_path = get_db_path()
    init_db(db_path)

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        # 1. Base de données SQLite
        if db_path.exists():
            zf.write(db_path, arcname="ecole_adnane.db")

        # 2. Fichiers PDF de cours
        if COURSES_DIR.exists():
            for pdf_file in COURSES_DIR.glob("*.pdf"):
                zf.write(pdf_file, arcname=f"cours/{pdf_file.name}")

        # 3. Manifeste
        stats = get_backup_summary()
        manifest = {
            "app": "Ecole Adnane",
            "version": "1.0.0",
            "exported_at": datetime.now().isoformat(),
            "stats": stats,
        }
        zf.writestr("manifest.json", json.dumps(manifest, indent=2, ensure_ascii=False))

    buf.seek(0)
    return buf.getvalue()


def export_database_file() -> bytes:
    """Retourne directement les octets du fichier SQLite ecole_adnane.db."""
    db_path = get_db_path()
    init_db(db_path)
    with open(db_path, "rb") as f:
        return f.read()


def restore_backup(file_bytes: bytes, filename: str) -> Dict[str, Any]:
    """
    Restaure une sauvegarde à partir d'un fichier ZIP ou SQLite (.db).
    Garantit la sécurité contre le path traversal et vérifie l'intégrité SQLite.
    """
    if not file_bytes:
        return {"success": False, "error": "Le fichier téléversé est vide."}

    db_path = get_db_path()
    db_path.parent.mkdir(parents=True, exist_ok=True)
    COURSES_DIR.mkdir(parents=True, exist_ok=True)

    filename_lower = filename.lower()

    try:
        # Cas 1 : Archive ZIP
        if filename_lower.endswith(".zip") or file_bytes[:4] == b"PK\x03\x04":
            buf = io.BytesIO(file_bytes)
            with zipfile.ZipFile(buf, "r") as zf:
                # Vérifier la présence de la base
                names = zf.namelist()
                db_name = None
                for n in names:
                    if n == "ecole_adnane.db" or n.endswith(".db") or n.endswith(".sqlite"):
                        db_name = n
                        break

                if not db_name:
                    return {"success": False, "error": "L'archive ZIP ne contient aucune base de données SQLite valide."}

                # Extraire la base
                db_content = zf.read(db_name)
                if not db_content.startswith(SQLITE_HEADER):
                    return {"success": False, "error": "Le fichier de base dans le ZIP n'est pas un fichier SQLite valide."}

                # Écrire la base
                with open(db_path, "wb") as f:
                    f.write(db_content)

                # Extraire les PDFs en évitant tout path traversal
                extracted_pdfs = 0
                for member in zf.infolist():
                    if member.filename.lower().endswith(".pdf"):
                        # Nom sécurisé sans sous-dossier malveillant
                        safe_name = Path(member.filename).name
                        if safe_name:
                            dest_path = COURSES_DIR / safe_name
                            with zf.open(member) as source, open(dest_path, "wb") as target:
                                shutil.copyfileobj(source, target)
                            extracted_pdfs += 1

            init_db(db_path)
            stats = get_backup_summary()
            return {
                "success": True,
                "message": (
                    f"Restauration réussie ! {stats['courses']} cours, {stats['messages']} messages de chat IA, "
                    f"{stats['quizzes']} quiz et {extracted_pdfs} fichiers PDF restaurés."
                ),
                "stats": stats,
            }

        # Cas 2 : Fichier SQLite brut (.db ou .sqlite)
        elif filename_lower.endswith((".db", ".sqlite")) or file_bytes.startswith(SQLITE_HEADER):
            if not file_bytes.startswith(SQLITE_HEADER):
                return {"success": False, "error": "Ce fichier n'est pas une base de données SQLite valide."}

            with open(db_path, "wb") as f:
                f.write(file_bytes)

            init_db(db_path)
            stats = get_backup_summary()
            return {
                "success": True,
                "message": (
                    f"Base de données restaurée avec succès ! {stats['courses']} cours, "
                    f"{stats['messages']} échanges avec l'IA Sanad et {stats['quizzes']} quiz récupérés."
                ),
                "stats": stats,
            }

        else:
            return {"success": False, "error": "Format non supporté. Veuillez téléverser un fichier .zip ou .db"}

    except Exception as e:
        logger.error(f"Erreur lors de la restauration de la sauvegarde : {e}", exc_info=True)
        return {"success": False, "error": f"Erreur lors de la restauration : {str(e)}"}
