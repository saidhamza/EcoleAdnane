"""
Module d'authentification Google OAuth & Gestion de Session pour Ecole Adnane.
Applique la règle : le tout premier utilisateur connecté devient automatiquement Admin,
les utilisateurs suivants deviennent Élèves ('student').
"""

import json
import logging
import os
import urllib.parse
from pathlib import Path
from typing import Any, Dict, List, Optional
import requests
import streamlit as st

from models.database import (
    create_or_get_google_user,
    get_user_by_email,
    get_user_by_id,
    get_user_count,
)

logger = logging.getLogger(__name__)

CREDENTIALS_FILE = Path(__file__).parent.parent / "credentials.json"
STORAGE_CREDENTIALS = Path(__file__).parent.parent / "storage" / "credentials.json"

AUTH_SCOPES = [
    "openid",
    "https://www.googleapis.com/auth/userinfo.email",
    "https://www.googleapis.com/auth/userinfo.profile",
]


def get_oauth_credentials() -> Dict[str, Optional[str]]:
    """
    Récupère les identifiants OAuth Google depuis :
    1. Streamlit Secrets (st.secrets)
    2. Variables d'environnement (GOOGLE_CLIENT_ID / GOOGLE_CLIENT_SECRET)
    3. Fichier credentials.json à la racine ou dans storage/
    """
    client_id = os.getenv("GOOGLE_CLIENT_ID")
    client_secret = os.getenv("GOOGLE_CLIENT_SECRET")
    redirect_uri = os.getenv("GOOGLE_REDIRECT_URI")

    # Vérification dans Streamlit secrets
    try:
        if hasattr(st, "secrets") and "google_oauth" in st.secrets:
            cfg = st.secrets["google_oauth"]
            client_id = client_id or cfg.get("client_id")
            client_secret = client_secret or cfg.get("client_secret")
            redirect_uri = redirect_uri or cfg.get("redirect_uri")
    except Exception:
        pass

    # Vérification dans credentials.json
    cred_path = None
    if CREDENTIALS_FILE.exists():
        cred_path = CREDENTIALS_FILE
    elif STORAGE_CREDENTIALS.exists():
        cred_path = STORAGE_CREDENTIALS

    if cred_path and (not client_id or not client_secret):
        try:
            with open(cred_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                client_info = data.get("web") or data.get("installed") or {}
                client_id = client_id or client_info.get("client_id")
                client_secret = client_secret or client_info.get("client_secret")
                redirect_uris = client_info.get("redirect_uris", [])
                if not redirect_uri and redirect_uris:
                    redirect_uri = redirect_uris[0]
        except Exception as e:
            logger.warning(f"Impossible de lire le fichier {cred_path}: {e}")

    return {
        "client_id": client_id,
        "client_secret": client_secret,
        "redirect_uri": redirect_uri or "http://localhost:8501",
    }


def is_oauth_configured() -> bool:
    """Indique si les identifiants Google OAuth sont renseignés."""
    creds = get_oauth_credentials()
    return bool(creds.get("client_id") and creds.get("client_secret"))


def get_google_auth_url(redirect_uri: Optional[str] = None) -> str:
    """
    Génère l'URL d'autorisation Google OAuth2 avec les scopes d'identité.
    """
    creds = get_oauth_credentials()
    client_id = creds["client_id"]
    final_redirect = redirect_uri or creds["redirect_uri"]

    if not client_id:
        return ""

    params = {
        "client_id": client_id,
        "redirect_uri": final_redirect,
        "response_type": "code",
        "scope": " ".join(AUTH_SCOPES),
        "access_type": "offline",
        "prompt": "select_account consent",
    }
    return f"https://accounts.google.com/o/oauth2/v2/auth?{urllib.parse.urlencode(params)}"


def exchange_code_for_user(code: str, redirect_uri: Optional[str] = None) -> Dict[str, Any]:
    """
    Échange le code d'autorisation contre les jetons d'accès Google
    et récupère les informations de profil de l'utilisateur.
    """
    creds = get_oauth_credentials()
    client_id = creds["client_id"]
    client_secret = creds["client_secret"]
    final_redirect = redirect_uri or creds["redirect_uri"]

    if not client_id or not client_secret:
        raise ValueError("Identifiants OAuth (client_id / client_secret) introuvables.")

    token_url = "https://oauth2.googleapis.com/token"
    token_payload = {
        "code": code,
        "client_id": client_id,
        "client_secret": client_secret,
        "redirect_uri": final_redirect,
        "grant_type": "authorization_code",
    }

    resp = requests.post(token_url, data=token_payload, timeout=15)
    if resp.status_code != 200:
        logger.error(f"Échec de l'échange de token Google: {resp.text}")
        raise ValueError(f"Échec d'authentification Google ({resp.status_code}) : {resp.text}")

    token_data = resp.json()
    access_token = token_data.get("access_token")
    if not access_token:
        raise ValueError("Aucun access_token reçu de Google.")

    userinfo_url = "https://www.googleapis.com/oauth2/v2/userinfo"
    userinfo_resp = requests.get(
        userinfo_url,
        headers={"Authorization": f"Bearer {access_token}"},
        timeout=15,
    )
    if userinfo_resp.status_code != 200:
        raise ValueError("Impossible de récupérer les informations de profil Google.")

    profile = userinfo_resp.json()
    email = profile.get("email", "").strip().lower()
    name = profile.get("name") or email.split("@")[0]
    avatar_url = profile.get("picture")

    if not email:
        raise ValueError("L'adresse email Google est manquante.")

    # Attribution automatique : premier arrivé = admin, suivants = student
    user = create_or_get_google_user(email=email, name=name, avatar_url=avatar_url)
    return user


def init_session_state() -> None:
    """Initialise les clés de session Streamlit si elles n'existent pas."""
    if "is_authenticated" not in st.session_state:
        st.session_state["is_authenticated"] = False
    if "user" not in st.session_state:
        st.session_state["user"] = None
    if "user_id" not in st.session_state:
        st.session_state["user_id"] = None
    if "email" not in st.session_state:
        st.session_state["email"] = None
    if "name" not in st.session_state:
        st.session_state["name"] = None
    if "avatar" not in st.session_state:
        st.session_state["avatar"] = None
    if "role" not in st.session_state:
        st.session_state["role"] = None


def set_session_user(user: Dict[str, Any]) -> None:
    """Configure la session active de l'utilisateur."""
    st.session_state["user"] = user
    st.session_state["user_id"] = user["id"]
    st.session_state["email"] = user["email"]
    st.session_state["name"] = user["name"]
    st.session_state["avatar"] = user.get("avatar_url")
    st.session_state["role"] = user["role"]
    st.session_state["is_authenticated"] = True


def logout_user() -> None:
    """Détruit proprement la session utilisateur."""
    st.session_state["is_authenticated"] = False
    st.session_state["user"] = None
    st.session_state["user_id"] = None
    st.session_state["email"] = None
    st.session_state["name"] = None
    st.session_state["avatar"] = None
    st.session_state["role"] = None
    if "active_student_id" in st.session_state:
        del st.session_state["active_student_id"]


def dev_mode_login(email: str, name: str, role: Optional[str] = None) -> Dict[str, Any]:
    """
    Permet une connexion locale directe pour le développement,
    les tests unitaires ou le fonctionnement hors-ligne.
    Respecte la règle 'premier arrivé = admin' si role est None.
    """
    user = create_or_get_google_user(email=email, name=name, role=role)
    set_session_user(user)
    return user
