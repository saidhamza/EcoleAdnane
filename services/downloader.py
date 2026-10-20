"""
Module d'ingestion et de téléchargement de documents pour Ecole Adnane.
Gère le stockage local sécurisé, la déduplication par hachage SHA-256,
l'import par glisser-déposer et la synchronisation Google Classroom.
"""

import hashlib
import os
import shutil
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from models.database import get_course_by_hash, save_course
from services.pdf_parser import (
    classify_subject_heuristic,
    extract_fallback_title,
    extract_text_from_pdf,
)

STORAGE_DIR = Path(__file__).parent.parent / "storage"
COURSES_DIR = STORAGE_DIR / "cours"
CREDENTIALS_PATH = Path(__file__).parent.parent / "credentials.json"
TOKEN_PATH = STORAGE_DIR / "token.json"


def ensure_storage_dirs() -> None:
    """Crée les répertoires nécessaires au stockage."""
    COURSES_DIR.mkdir(parents=True, exist_ok=True)


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
    custom_title: Optional[str] = None,
    custom_subject: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Ingère un document PDF à partir de ses octets :
    1. Calcule le hash SHA-256.
    2. Vérifie la présence d'un doublon en base.
    3. Enregistre dans storage/cours/.
    4. Extrait le texte et détecte la langue (FR / AR) et la matière 3AC.
    5. Sauvegarde les métadonnées dans SQLite.
    """
    ensure_storage_dirs()

    file_hash = calculate_sha256(file_bytes)

    # 1. Vérification des doublons
    existing_course = get_course_by_hash(file_hash)
    if existing_course:
        return {
            "status": "duplicate",
            "message": f"Le document '{existing_course['title']}' est déjà enregistré dans votre espace !",
            "course": existing_course,
            "course_id": existing_course["id"],
        }

    # 2. Sauvegarde sur disque
    safe_filename = "".join(c for c in original_filename if c.isalnum() or c in ("-", "_", ".", " ")).strip()
    if not safe_filename:
        safe_filename = f"cours_{file_hash[:8]}.pdf"

    target_path = COURSES_DIR / f"{file_hash[:10]}_{safe_filename}"
    with open(target_path, "wb") as f:
        f.write(file_bytes)

    # 3. Extraction de texte & Analyse linguistique
    pdf_info = extract_text_from_pdf(str(target_path))
    raw_text = pdf_info["full_text"]
    language = pdf_info["language"]  # 'fr' ou 'ar'

    # 4. Détection ou validation de la matière
    heuristic_subj, confidence = classify_subject_heuristic(raw_text, language)
    subject = custom_subject or heuristic_subj

    # Titre lisible
    title = custom_title or extract_fallback_title(original_filename, raw_text, language)

    # 5. Enregistrement en base de données
    course_id = save_course(
        title=title,
        subject=subject,
        language=language,
        file_path=str(target_path),
        file_hash=file_hash,
        file_name=original_filename,
        raw_text=raw_text,
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


def ingest_local_file(file_path: str) -> Dict[str, Any]:
    """Ingère un fichier PDF existant sur le disque local."""
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"Fichier introuvable : {file_path}")

    with open(path, "rb") as f:
        content = f.read()

    return ingest_pdf_bytes(content, path.name)


# ---------------------------------------------------------------------------
# Module d'intégration Google Classroom
# ---------------------------------------------------------------------------

def is_classroom_configured() -> bool:
    """Vérifie si les identifiants Google Classroom sont configurés."""
    return CREDENTIALS_PATH.exists() or Path("credentials.json").exists()


def get_classroom_credentials_path() -> Optional[Path]:
    """Retourne le chemin vers credentials.json s'il existe."""
    if CREDENTIALS_PATH.exists():
        return CREDENTIALS_PATH
    if Path("credentials.json").exists():
        return Path("credentials.json")
    return None


def sync_google_classroom() -> Dict[str, Any]:
    """
    Synchronise les devoirs et supports PDF depuis Google Classroom.
    Nécessite credentials.json configuré via Google Cloud Console.
    """
    cred_path = get_classroom_credentials_path()
    if not cred_path:
        return {
            "success": False,
            "error": "Fichier credentials.json introuvable. Veuillez le téléverser dans l'onglet Paramètres.",
        }

    try:
        from google.auth.transport.requests import Request
        from google.oauth2.credentials import Credentials
        from google_auth_oauthlib.flow import InstalledAppFlow
        from googleapiclient.discovery import build
        from googleapiclient.http import MediaIoBaseDownload
        import io

        SCOPES = [
            "https://www.googleapis.com/auth/classroom.courses.readonly",
            "https://www.googleapis.com/auth/classroom.coursework.me.readonly",
            "https://www.googleapis.com/auth/classroom.courseworkmaterials.readonly",
            "https://www.googleapis.com/auth/drive.readonly",
        ]

        creds = None
        if TOKEN_PATH.exists():
            creds = Credentials.from_authorized_user_file(str(TOKEN_PATH), SCOPES)

        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                flow = InstalledAppFlow.from_client_secrets_file(str(cred_path), SCOPES)
                creds = flow.run_local_server(port=0)
            with open(TOKEN_PATH, "w") as token:
                token.write(creds.to_json())

        classroom_service = build("classroom", "v1", credentials=creds)
        drive_service = build("drive", "v3", credentials=creds)

        # Récupérer les cours
        results = classroom_service.courses().list(pageSize=10).execute()
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
                        # Télécharger le fichier
                        request = drive_service.files().get_media(fileId=file_id)
                        fh = io.BytesIO()
                        downloader = MediaIoBaseDownload(fh, request)
                        done = False
                        while not done:
                            _, done = downloader.next_chunk()

                        pdf_bytes = fh.getvalue()
                        res = ingest_pdf_bytes(pdf_bytes, title)
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
        return {
            "success": False,
            "error": f"Erreur lors de la synchronisation Google Classroom : {str(e)}",
        }
