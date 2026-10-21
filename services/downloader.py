"""
Module d'ingestion et de téléchargement de documents pour Ecole Adnane.
Gère le stockage local strictement isolé par utilisateur (storage/users/<user_id>/cours/),
la déduplication par hachage SHA-256, l'import par glisser-déposer
et la synchronisation Google Classroom individuelle avec scopes stricts.
"""

import hashlib
import io
import logging
import os
import shutil
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from models.database import get_course_by_hash, save_course
try:
    import importlib
    import services.pdf_parser
    if not hasattr(services.pdf_parser, "SUBJECTS_EN"):
        services.pdf_parser = importlib.reload(services.pdf_parser)
    from services.pdf_parser import (
        SUBJECTS_AR,
        SUBJECTS_EN,
        SUBJECTS_FR,
        classify_subject_heuristic,
        extract_fallback_title,
        extract_text_from_pdf,
    )
except Exception:
    from services.pdf_parser import (
        classify_subject_heuristic,
        extract_fallback_title,
        extract_text_from_pdf,
    )
    SUBJECTS_FR = getattr(services.pdf_parser, "SUBJECTS_FR", ["Mathématiques", "Physique-Chimie", "SVT", "Français"])
    SUBJECTS_AR = getattr(services.pdf_parser, "SUBJECTS_AR", ["التربية الإسلامية", "الاجتماعيات", "اللغة العربية"])
    SUBJECTS_EN = getattr(services.pdf_parser, "SUBJECTS_EN", ["Anglais"])

logger = logging.getLogger(__name__)

STORAGE_DIR = Path(__file__).parent.parent / "storage"
USERS_DIR = STORAGE_DIR / "users"
LEGACY_COURSES_DIR = STORAGE_DIR / "cours"
ROOT_CREDENTIALS_PATH = Path(__file__).parent.parent / "credentials.json"
CREDENTIALS_PATH = ROOT_CREDENTIALS_PATH  # Compatibilité


def get_user_base_dir(user_id: Optional[int] = None) -> Path:
    """Retourne le répertoire racine d'un utilisateur."""
    if user_id is not None:
        p = USERS_DIR / str(user_id)
    else:
        p = STORAGE_DIR
    p.mkdir(parents=True, exist_ok=True)
    return p


def get_user_storage_dir(user_id: Optional[int] = None) -> Path:
    """Retourne le dossier des PDF de cours de l'utilisateur."""
    if user_id is not None:
        p = USERS_DIR / str(user_id) / "cours"
    else:
        p = LEGACY_COURSES_DIR
    p.mkdir(parents=True, exist_ok=True)
    return p


def get_user_credentials_path(user_id: Optional[int] = None) -> Optional[Path]:
    """
    Retourne le chemin vers le fichier credentials.json propre à l'utilisateur.
    Stricte étanchéité : si user_id est fourni, cherche EXCLUSIVEMENT
    dans le dossier de cet utilisateur (aucun partage du fichier racine).
    """
    if user_id is not None:
        user_cred = USERS_DIR / str(user_id) / "credentials.json"
        if user_cred.exists():
            return user_cred
        return None
    if ROOT_CREDENTIALS_PATH.exists():
        return ROOT_CREDENTIALS_PATH
    return None


def get_user_token_path(user_id: Optional[int] = None) -> Path:
    """Retourne le chemin vers le token.json de l'utilisateur."""
    if user_id is not None:
        return USERS_DIR / str(user_id) / "token.json"
    return STORAGE_DIR / "token.json"


def save_user_credentials(user_id: int, file_bytes: bytes) -> Path:
    """Enregistre le credentials.json personnel d'un utilisateur dans son espace."""
    base_dir = get_user_base_dir(user_id)
    target_path = base_dir / "credentials.json"
    with open(target_path, "wb") as f:
        f.write(file_bytes)
    return target_path


def is_classroom_configured(user_id: Optional[int] = None) -> bool:
    """
    Vérifie si credentials.json est présent pour cet utilisateur.
    Stricte étanchéité : si user_id est fourni, vérifie EXCLUSIVEMENT
    dans le dossier personnel de cet utilisateur.
    """
    if user_id is not None:
        user_cred = USERS_DIR / str(user_id) / "credentials.json"
        return user_cred.exists()
    return ROOT_CREDENTIALS_PATH.exists() or (STORAGE_DIR / "credentials.json").exists()


def calculate_sha256(file_bytes: bytes) -> str:
    """Calcule l'empreinte SHA-256 d'un contenu binaire."""
    return hashlib.sha256(file_bytes).hexdigest()


def calculate_file_sha256(file_path: str) -> str:
    """Calcule l'empreinte SHA-256 d'un fichier sur disque."""
    sha256_hash = hashlib.sha256()
    with open(file_path, "rb") as f:
        for byte_block in iter(lambda: f.read(65536), b""):
            sha256_hash.update(byte_block)
    return sha256_hash.hexdigest()


def ingest_pdf_bytes(
    file_bytes: bytes,
    original_filename: str,
    user_id: Optional[int] = None,
    custom_title: Optional[str] = None,
    custom_subject: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Ingère un document PDF à partir de ses octets pour un utilisateur spécifique :
    1. Calcule le hash SHA-256.
    2. Vérifie la présence d'un doublon dans l'espace de cet utilisateur.
    3. Enregistre dans storage/users/<user_id>/cours/.
    4. Extrait le texte et détecte la langue (FR / AR) et la matière 3AC.
    5. Sauvegarde les métadonnées dans SQLite avec user_id.
    """
    target_dir = get_user_storage_dir(user_id)

    file_hash = calculate_sha256(file_bytes)

    # 1. Vérification des doublons dans l'espace de cet utilisateur
    existing_course = get_course_by_hash(file_hash, user_id=user_id, include_global=(user_id is None))
    if existing_course:
        return {
            "status": "duplicate",
            "message": f"Le document '{existing_course['title']}' est déjà enregistré dans votre espace !",
            "course": existing_course,
            "course_id": existing_course["id"],
        }

    # 2. Sauvegarde sur disque cloisonné
    safe_filename = "".join(c for c in original_filename if c.isalnum() or c in ("-", "_", ".", " ")).strip()
    if not safe_filename:
        safe_filename = f"cours_{file_hash[:8]}.pdf"

    target_path = target_dir / f"{file_hash[:10]}_{safe_filename}"
    with open(target_path, "wb") as f:
        f.write(file_bytes)

    # 3. Extraction de texte & Analyse linguistique
    pdf_info = extract_text_from_pdf(str(target_path))
    raw_text = pdf_info["full_text"]
    language = pdf_info["language"]  # 'fr', 'ar', ou 'en'

    # 4. Détection ou validation de la matière
    heuristic_subj, confidence = classify_subject_heuristic(raw_text, language)
    subject = custom_subject or heuristic_subj

    # Si la matière est l'anglais ou si la langue détectée est l'anglais
    if subject == "Anglais" or language == "en":
        subject = "Anglais"
        language = "en"
    elif custom_subject:
        if custom_subject in SUBJECTS_AR:
            language = "ar"
        elif custom_subject in SUBJECTS_FR:
            language = "fr"

    # Titre lisible
    title = custom_title or extract_fallback_title(original_filename, raw_text, language)

    # 5. Enregistrement en base de données avec user_id
    course_id = save_course(
        title=title,
        subject=subject,
        language=language,
        file_path=str(target_path),
        file_hash=file_hash,
        file_name=original_filename,
        raw_text=raw_text,
        user_id=user_id,
    )

    return {
        "status": "success",
        "message": f"Document '{title}' ajouté avec succès ({language.upper()} - {subject}) !",
        "course_id": course_id,
        "language": language,
        "subject": subject,
        "title": title,
        "page_count": pdf_info["page_count"],
        "confidence": confidence,
    }


def ingest_local_file(file_path: str, user_id: Optional[int] = None) -> Dict[str, Any]:
    """Ingère un fichier PDF existant sur le disque local."""
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"Fichier introuvable : {file_path}")

    with open(path, "rb") as f:
        content = f.read()

    return ingest_pdf_bytes(content, path.name, user_id=user_id)


# ---------------------------------------------------------------------------
# Module d'intégration Google Classroom Individuel
# ---------------------------------------------------------------------------

def sync_google_classroom(user_id: Optional[int] = None) -> Dict[str, Any]:
    """
    Synchronise les devoirs et supports PDF depuis Google Classroom pour l'utilisateur.
    Utilise strictement les scopes exacts prescrits.
    """
    cred_path = get_user_credentials_path(user_id)
    if not cred_path or not cred_path.exists():
        return {
            "success": False,
            "error": "Fichier credentials.json introuvable pour votre compte. Veuillez le téléverser dans vos Paramètres.",
        }

    token_path = get_user_token_path(user_id)

    try:
        from google.auth.transport.requests import Request
        from google.oauth2.credentials import Credentials
        from google_auth_oauthlib.flow import InstalledAppFlow
        from googleapiclient.discovery import build
        from googleapiclient.http import MediaIoBaseDownload

        # Nomenclature exacte des 4 scopes requis
        SCOPES = [
            "https://www.googleapis.com/auth/classroom.courses.readonly",
            "https://www.googleapis.com/auth/classroom.coursework.me.readonly",
            "https://www.googleapis.com/auth/classroom.courseworkmaterials.readonly",
            "https://www.googleapis.com/auth/drive.readonly",
        ]

        creds = None
        if token_path.exists():
            creds = Credentials.from_authorized_user_file(str(token_path), SCOPES)

        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                flow = InstalledAppFlow.from_client_secrets_file(str(cred_path), SCOPES)
                creds = flow.run_local_server(port=0)
            token_path.parent.mkdir(parents=True, exist_ok=True)
            with open(token_path, "w") as token:
                token.write(creds.to_json())

        classroom_service = build("classroom", "v1", credentials=creds)
        drive_service = build("drive", "v3", credentials=creds)

        # Récupérer les cours Classroom
        results = classroom_service.courses().list(pageSize=15).execute()
        courses = results.get("courses", [])

        imported_count = 0
        skipped_count = 0

        for c in courses:
            c_id = c["id"]
            # Documents / Supports de cours
            materials = classroom_service.courses().courseWorkMaterials().list(courseId=c_id).execute()
            for mat in materials.get("courseWorkMaterial", []):
                for item in mat.get("materials", []):
                    drive_file = item.get("driveFile", {}).get("driveFile", {})
                    title = drive_file.get("title", "")
                    file_id = drive_file.get("id")

                    if file_id and title.lower().endswith(".pdf"):
                        request = drive_service.files().get_media(fileId=file_id)
                        fh = io.BytesIO()
                        downloader = MediaIoBaseDownload(fh, request)
                        done = False
                        while not done:
                            _, done = downloader.next_chunk()

                        pdf_bytes = fh.getvalue()
                        res = ingest_pdf_bytes(pdf_bytes, title, user_id=user_id)
                        if res["status"] == "success":
                            imported_count += 1
                        else:
                            skipped_count += 1

        return {
            "success": True,
            "message": f"Synchronisation Classroom réussie : {imported_count} nouveau(x) cours importé(s), {skipped_count} déjà présent(s).",
            "imported": imported_count,
            "skipped": skipped_count,
        }

    except Exception as e:
        logger.error(f"Erreur de synchronisation Classroom: {e}")
        return {
            "success": False,
            "error": f"Erreur lors de la synchronisation Google Classroom : {str(e)}",
        }
