"""
Module de sauvegarde et restauration automatique sur Google Drive pour Ecole Adnane.
Immunise la plateforme contre les pertes de données causées par la réinitialisation
des conteneurs éphémères de Streamlit Cloud.
Utilise le scope restreint et sécurisé https://www.googleapis.com/auth/drive.file
pour stocker les archives ZIP chiffrées dans un dossier dédié 'EcoleAdnane_Backups'.
"""

import io
import json
import logging
import os
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload, MediaIoBaseUpload

from models.database import get_setting, get_user_count, list_courses, set_setting
from services.auth_manager import get_admin_google_tokens, get_oauth_credentials
from services.backup_manager import export_global_backup, restore_global_backup

logger = logging.getLogger(__name__)

BACKUP_FOLDER_NAME = "EcoleAdnane_Backups"
DRIVE_SCOPES = ["https://www.googleapis.com/auth/drive.file"]


def get_drive_credentials(user_id: Optional[int] = None) -> Optional[Credentials]:
    """
    Construit et rafraîchit automatiquement les identifiants Google Drive de l'administrateur.
    Supporte :
    1. Jetons de session ou base SQLite (issu du login Google OAuth admin).
    2. Streamlit Secrets (st.secrets["google_drive"]).
    """
    oauth_creds = get_oauth_credentials()
    client_id = oauth_creds.get("client_id")
    client_secret = oauth_creds.get("client_secret")

    # 1. Vérification Streamlit Secrets (idéal pour persistance multi-reboot)
    try:
        import streamlit as st
        if hasattr(st, "secrets") and "google_drive" in st.secrets:
            sec = dict(st.secrets["google_drive"])
            c_id = sec.get("client_id") or client_id
            c_secret = sec.get("client_secret") or client_secret
            r_token = sec.get("refresh_token")
            if c_id and c_secret and r_token:
                creds = Credentials(
                    token=sec.get("access_token"),
                    refresh_token=r_token,
                    token_uri="https://oauth2.googleapis.com/token",
                    client_id=c_id,
                    client_secret=c_secret,
                    scopes=DRIVE_SCOPES,
                )
                if not creds.valid or creds.expired:
                    creds.refresh(Request())
                return creds
    except Exception as e:
        logger.debug(f"Erreur vérification secrets google_drive: {e}")

    # 2. Vérification tokens admin enregistrés (Session / Base de données)
    tokens = get_admin_google_tokens(user_id)
    if not tokens:
        return None

    access_token = tokens.get("access_token")
    refresh_token = tokens.get("refresh_token")

    if not client_id or not client_secret:
        # Tenter d'extraire depuis les tokens stockés si présents
        client_id = tokens.get("client_id", client_id)
        client_secret = tokens.get("client_secret", client_secret)

    if not refresh_token and not access_token:
        return None

    try:
        creds = Credentials(
            token=access_token,
            refresh_token=refresh_token,
            token_uri="https://oauth2.googleapis.com/token",
            client_id=client_id,
            client_secret=client_secret,
            scopes=DRIVE_SCOPES,
        )

        # Si expiré ou sur le point d'expirer, rafraîchir
        if (not creds.valid or creds.expired) and refresh_token:
            creds.refresh(Request())
            # Mettre à jour le nouveau access_token en session/base
            try:
                tokens["access_token"] = creds.token
                set_setting("google_drive_oauth_tokens", json.dumps(tokens))
            except Exception:
                pass

        return creds
    except Exception as e:
        logger.warning(f"Échec d'initialisation des identifiants Google Drive : {e}")
        return None


def is_drive_connected(user_id: Optional[int] = None) -> bool:
    """Indique si un accès actif et valide à Google Drive est disponible."""
    creds = get_drive_credentials(user_id)
    return creds is not None and (creds.valid or bool(creds.refresh_token))


def get_drive_service(user_id: Optional[int] = None) -> Optional[Any]:
    """Retourne une instance du client Drive v3 authentifié."""
    creds = get_drive_credentials(user_id)
    if not creds:
        return None
    try:
        return build("drive", "v3", credentials=creds, cache_discovery=False)
    except Exception as e:
        logger.error(f"Erreur création du service Google Drive v3 : {e}")
        return None


def ensure_backup_folder(drive_service: Any) -> str:
    """
    Recherche ou crée le dossier dédié 'EcoleAdnane_Backups' sur le Google Drive de l'utilisateur.
    Retourne l'ID Google Drive du dossier.
    """
    query = (
        f"name = '{BACKUP_FOLDER_NAME}' and "
        "mimeType = 'application/vnd.google-apps.folder' and "
        "trashed = false"
    )
    results = drive_service.files().list(
        q=query,
        spaces="drive",
        fields="files(id, name)",
        pageSize=5,
    ).execute()

    files = results.get("files", [])
    if files:
        return files[0]["id"]

    # Création du dossier
    folder_metadata = {
        "name": BACKUP_FOLDER_NAME,
        "mimeType": "application/vnd.google-apps.folder",
        "description": "Dossier de sauvegardes automatiques pour l'application Ecole Adnane",
    }
    folder = drive_service.files().create(body=folder_metadata, fields="id").execute()
    return folder.get("id")


def format_bytes_human(size_in_bytes: int) -> str:
    """Convertit un nombre d'octets en chaîne lisible (Ko, Mo)."""
    if size_in_bytes < 1024:
        return f"{size_in_bytes} o"
    elif size_in_bytes < 1024 * 1024:
        return f"{size_in_bytes / 1024:.1f} Ko"
    else:
        return f"{size_in_bytes / (1024 * 1024):.1f} Mo"


def upload_backup_to_drive(
    file_bytes: Optional[bytes] = None,
    user_id: Optional[int] = None,
    note: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Génère l'archive complète de l'application et la téléverse sur Google Drive
    dans le dossier dédié 'EcoleAdnane_Backups'.
    Applique la rotation pour conserver les 10 sauvegardes les plus récentes.
    """
    service = get_drive_service(user_id)
    if not service:
        return {
            "success": False,
            "error": "Google Drive n'est pas connecté. Veuillez connecter votre compte Google depuis l'administration.",
        }

    try:
        # 1. Génération de l'archive si non fournie
        data = file_bytes if file_bytes is not None else export_global_backup()
        if not data:
            return {"success": False, "error": "L'archive générée est vide."}

        # 2. Localisation / création du dossier Drive
        folder_id = ensure_backup_folder(service)

        # 3. Métadonnées du fichier
        timestamp_str = datetime.now().strftime("%Y%m%d_%H%M%S")
        file_name = f"ecole_adnane_backup_{timestamp_str}.zip"
        desc = note or f"Sauvegarde système Ecole Adnane du {datetime.now().strftime('%d/%m/%Y à %H:%M')}"

        file_metadata = {
            "name": file_name,
            "parents": [folder_id],
            "description": desc,
            "properties": {
                "app": "EcoleAdnane",
                "type": "global_system_backup",
                "created_at": datetime.now().isoformat(),
            },
        }

        media = MediaIoBaseUpload(
            io.BytesIO(data),
            mimetype="application/zip",
            resumable=True,
        )

        uploaded = service.files().create(
            body=file_metadata,
            media_body=media,
            fields="id, name, size, webViewLink, createdTime",
        ).execute()

        file_id = uploaded.get("id")
        web_link = uploaded.get("webViewLink", "")
        file_size = len(data)

        # Mémoriser la date de dernière sauvegarde
        now_iso = datetime.now().isoformat()
        set_setting("last_gdrive_backup_at", now_iso)
        set_setting("last_gdrive_backup_file_id", str(file_id))

        # 4. Rotation : nettoyage des anciennes sauvegardes
        cleanup_old_drive_backups(service, folder_id, keep_count=10)

        logger.info(f"Sauvegarde Google Drive réussie : {file_name} ({format_bytes_human(file_size)})")
        return {
            "success": True,
            "file_id": file_id,
            "file_name": file_name,
            "web_link": web_link,
            "size_bytes": file_size,
            "size_formatted": format_bytes_human(file_size),
            "timestamp": now_iso,
        }
    except Exception as e:
        logger.error(f"Erreur téléversement Google Drive : {e}")
        return {"success": False, "error": str(e)}


def cleanup_old_drive_backups(drive_service: Any, folder_id: str, keep_count: int = 10) -> int:
    """Conserve les N sauvegardes les plus récentes et supprime les plus anciennes."""
    try:
        query = f"'{folder_id}' in parents and trashed = false and mimeType = 'application/zip'"
        results = drive_service.files().list(
            q=query,
            spaces="drive",
            fields="files(id, name, createdTime)",
            orderBy="createdTime desc",
            pageSize=50,
        ).execute()

        files = results.get("files", [])
        if len(files) <= keep_count:
            return 0

        deleted_count = 0
        for old_file in files[keep_count:]:
            try:
                drive_service.files().delete(fileId=old_file["id"]).execute()
                deleted_count += 1
            except Exception as e:
                logger.warning(f"Impossible de supprimer l'ancienne sauvegarde {old_file.get('name')}: {e}")

        return deleted_count
    except Exception as e:
        logger.warning(f"Erreur rotation sauvegardes Drive : {e}")
        return 0


def list_drive_backups(user_id: Optional[int] = None) -> List[Dict[str, Any]]:
    """
    Récupère la liste ordonnée des sauvegardes disponibles sur Google Drive (de la plus récente à la plus ancienne).
    """
    service = get_drive_service(user_id)
    if not service:
        return []

    try:
        folder_id = ensure_backup_folder(service)
        query = f"'{folder_id}' in parents and trashed = false"
        results = service.files().list(
            q=query,
            spaces="drive",
            fields="files(id, name, size, createdTime, webViewLink, description)",
            orderBy="createdTime desc",
            pageSize=30,
        ).execute()

        backups = []
        for f in results.get("files", []):
            raw_size = int(f.get("size", 0))
            raw_time = f.get("createdTime", "")
            formatted_date = raw_time
            if raw_time:
                try:
                    dt = datetime.fromisoformat(raw_time.replace("Z", "+00:00"))
                    formatted_date = dt.strftime("%d/%m/%Y à %H:%M")
                except Exception:
                    pass

            backups.append({
                "id": f.get("id"),
                "name": f.get("name"),
                "size_bytes": raw_size,
                "size_formatted": format_bytes_human(raw_size),
                "created_time": raw_time,
                "date_formatted": formatted_date,
                "web_link": f.get("webViewLink", ""),
                "description": f.get("description", ""),
            })
        return backups
    except Exception as e:
        logger.error(f"Erreur listing sauvegardes Drive : {e}")
        return []


def download_backup_from_drive(file_id: str, user_id: Optional[int] = None) -> Optional[bytes]:
    """Télécharge le contenu binaire d'un fichier ZIP depuis Google Drive."""
    service = get_drive_service(user_id)
    if not service:
        return None

    try:
        request = service.files().get_media(fileId=file_id)
        fh = io.BytesIO()
        downloader = MediaIoBaseDownload(fh, request)
        done = False
        while not done:
            _, done = downloader.next_chunk()
        return fh.getvalue()
    except Exception as e:
        logger.error(f"Erreur téléchargement Drive du fichier {file_id}: {e}")
        return None


def restore_backup_from_drive(file_id: str, user_id: Optional[int] = None) -> Dict[str, Any]:
    """Télécharge et restaure l'archive spécifiée depuis Google Drive."""
    data = download_backup_from_drive(file_id, user_id)
    if not data:
        return {"success": False, "error": "Impossible de télécharger l'archive depuis Google Drive."}
    return restore_global_backup(data)


def restore_latest_drive_backup(user_id: Optional[int] = None) -> Dict[str, Any]:
    """Recherche la sauvegarde la plus récente sur Google Drive et la restaure."""
    backups = list_drive_backups(user_id)
    if not backups:
        return {"success": False, "error": "Aucune sauvegarde trouvée sur Google Drive dans le dossier EcoleAdnane_Backups."}
    latest = backups[0]
    res = restore_backup_from_drive(latest["id"], user_id)
    if res.get("success"):
        res["restored_backup_name"] = latest["name"]
        res["restored_backup_date"] = latest["date_formatted"]
    return res


def auto_backup_on_change(user_id: Optional[int] = None, min_interval_minutes: int = 15) -> Dict[str, Any]:
    """
    Déclencheur intelligent de sauvegarde automatique.
    Vérifie le temps écoulé depuis la dernière sauvegarde pour ne pas saturer
    les quotas de requêtes Google Drive lors d'éditions fréquentes.
    """
    if not is_drive_connected(user_id):
        return {"success": False, "skipped": True, "reason": "Drive non connecté"}

    last_backup_str = get_setting("last_gdrive_backup_at")
    if last_backup_str:
        try:
            last_dt = datetime.fromisoformat(last_backup_str)
            elapsed_sec = (datetime.now() - last_dt).total_seconds()
            if elapsed_sec < (min_interval_minutes * 60):
                return {
                    "success": False,
                    "skipped": True,
                    "reason": f"Sauvegarde récente il y a {int(elapsed_sec / 60)} minutes (intervalle min: {min_interval_minutes}m).",
                }
        except Exception:
            pass

    return upload_backup_to_drive(user_id=user_id, note="Sauvegarde automatique après modification")


def check_and_auto_heal_on_startup(user_id: Optional[int] = None) -> Optional[Dict[str, Any]]:
    """
    Vérifie si le conteneur Streamlit Cloud démarre avec une base SQLite vide
    alors qu'une sauvegarde existe sur Google Drive. Si oui, applique la restauration automatique.
    """
    try:
        user_count = get_user_count()
        course_count = len(list_courses())
        if (user_count == 0 or (user_count <= 1 and course_count == 0)) and is_drive_connected(user_id):
            logger.info("Base locale vide ou réinitialisée détectée avec Google Drive connecté : tentative d'auto-guérison...")
            return restore_latest_drive_backup(user_id)
    except Exception as e:
        logger.warning(f"Erreur lors du contrôle d'auto-guérison : {e}")
    return None
