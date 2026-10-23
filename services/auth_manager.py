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
from typing import Any, Dict, List, Optional, Tuple
import requests
import streamlit as st

from models.database import (
    create_or_get_google_user,
    create_user_session,
    delete_user_session,
    get_setting,
    get_user_by_email,
    get_user_by_id,
    get_user_count,
    get_user_from_session_token,
    get_user_setting,
    set_setting,
    set_user_setting,
)

logger = logging.getLogger(__name__)

CREDENTIALS_FILE = Path(__file__).parent.parent / "credentials.json"
STORAGE_CREDENTIALS = Path(__file__).parent.parent / "storage" / "credentials.json"

AUTH_SCOPES = [
    "openid",
    "https://www.googleapis.com/auth/userinfo.email",
    "https://www.googleapis.com/auth/userinfo.profile",
    "https://www.googleapis.com/auth/drive.file",
]


def normalize_redirect_uri(uri: Optional[str]) -> str:
    """
    Normalise le redirect URI en retirant les espaces superflus tout en conservant
    scrupuleusement la présence ou l'absence de slash final pour correspondre exactement
    aux autorisations de Google Cloud Console.
    """
    if not uri:
        return "http://localhost"
    return uri.strip()



def get_current_base_url() -> Optional[str]:
    """
    Tente de détecter l'URL publique de l'application depuis la session Streamlit
    (ex: https://xxx.streamlit.app sur Streamlit Cloud ou http://localhost:8501 en local).
    """
    try:
        if hasattr(st, "context") and hasattr(st.context, "headers"):
            headers = st.context.headers
            if headers:
                host = headers.get("x-forwarded-host") or headers.get("host")
                if host:
                    proto = headers.get("x-forwarded-proto")
                    if not proto:
                        proto = "https" if ("streamlit.app" in host or not host.startswith("localhost")) else "http"
                    return f"{proto}://{host}".rstrip("/")
    except Exception:
        pass
    return None


def extract_auth_code(input_str: str) -> str:
    """
    Extrait proprement le code d'autorisation OAuth si l'utilisateur colle une URL
    complète (ex: http://localhost/?code=4/0A...) ou directement un code brut.
    """
    val = input_str.strip()
    if "code=" in val:
        try:
            parsed = urllib.parse.urlparse(val)
            qs = urllib.parse.parse_qs(parsed.query)
            if "code" in qs and qs["code"]:
                return qs["code"][0].strip()
        except Exception:
            pass
    return val


def get_oauth_credentials() -> Dict[str, Optional[str]]:
    """
    Récupère les identifiants OAuth Google depuis :
    1. Streamlit Secrets (st.secrets["google_oauth"])
    2. Variables d'environnement (GOOGLE_CLIENT_ID / GOOGLE_CLIENT_SECRET / GOOGLE_REDIRECT_URI)
    3. Fichier credentials.json à la racine ou dans storage/
    4. Détection dynamique de l'hôte Streamlit
    """
    client_id = os.getenv("GOOGLE_CLIENT_ID")
    client_secret = os.getenv("GOOGLE_CLIENT_SECRET")
    redirect_uri = os.getenv("GOOGLE_REDIRECT_URI")

    # 1. Vérification dans Streamlit secrets
    try:
        if hasattr(st, "secrets") and "google_oauth" in st.secrets:
            cfg = st.secrets["google_oauth"]
            client_id = client_id or cfg.get("client_id")
            client_secret = client_secret or cfg.get("client_secret")
            redirect_uri = redirect_uri or cfg.get("redirect_uri")
    except Exception:
        pass

def get_best_redirect_uri(redirect_uris: List[str]) -> str:
    """
    Choisit intelligemment l'URI de redirection :
    1. Si un URI correspond à l'hôte Streamlit détecté
    2. Priorité absolue aux URL web https:// (notamment streamlit.app) par rapport à http://localhost
    3. Priorité à localhost:8501 en local
    4. Premier URI disponible
    """
    if not redirect_uris:
        detected = get_current_base_url()
        return detected or "http://localhost"

    detected = get_current_base_url() or ""

    # 1. Correspondance avec l'hôte détecté
    if detected:
        for u in redirect_uris:
            if detected in u or u.rstrip("/") == detected.rstrip("/"):
                return u

    # 2. Priorité absolue aux domaines web https:// (ex: *.streamlit.app)
    for u in redirect_uris:
        if "streamlit.app" in u:
            return u
    for u in redirect_uris:
        if u.startswith("https://"):
            return u

    # 3. Priorité à localhost:8501 si disponible en local
    for u in redirect_uris:
        if "8501" in u:
            return u

    # 4. Premier URI
    return redirect_uris[0]


def get_oauth_credentials() -> Dict[str, Any]:
    """
    Récupère les identifiants OAuth Google depuis :
    1. Streamlit Secrets (st.secrets["google_oauth"])
    2. Variables d'environnement (GOOGLE_CLIENT_ID / GOOGLE_CLIENT_SECRET / GOOGLE_REDIRECT_URI)
    3. Fichier storage/credentials.json (téléversé par l'admin, PRIORITAIRE) puis racine
    4. Détection dynamique de l'hôte Streamlit
    """
    client_id = os.getenv("GOOGLE_CLIENT_ID")
    client_secret = os.getenv("GOOGLE_CLIENT_SECRET")
    redirect_uri = os.getenv("GOOGLE_REDIRECT_URI")
    available_redirect_uris: List[str] = []

    # 1. Vérification dans Streamlit secrets
    try:
        if hasattr(st, "secrets") and "google_oauth" in st.secrets:
            cfg = st.secrets["google_oauth"]
            client_id = client_id or cfg.get("client_id")
            client_secret = client_secret or cfg.get("client_secret")
            redirect_uri = redirect_uri or cfg.get("redirect_uri")
    except Exception:
        pass

    # 2. Vérification dans storage/credentials.json (PRIORITAIRE car téléversé via l'UI)
    # puis credentials.json à la racine
    cred_path = None
    if STORAGE_CREDENTIALS.exists():
        cred_path = STORAGE_CREDENTIALS
    elif CREDENTIALS_FILE.exists():
        cred_path = CREDENTIALS_FILE

    if cred_path:
        try:
            with open(cred_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                client_info = data.get("web") or data.get("installed") or {}
                client_id = client_id or client_info.get("client_id")
                client_secret = client_secret or client_info.get("client_secret")
                available_redirect_uris = client_info.get("redirect_uris", [])
                if not redirect_uri and available_redirect_uris:
                    redirect_uri = get_best_redirect_uri(available_redirect_uris)
        except Exception as e:
            logger.warning(f"Impossible de lire le fichier {cred_path}: {e}")

    # 3. Détection dynamique de l'hôte si Streamlit Cloud ou reverse proxy
    if not redirect_uri:
        detected_base_url = get_current_base_url()
        if detected_base_url and "streamlit.app" in detected_base_url:
            redirect_uri = detected_base_url
        else:
            redirect_uri = "http://localhost"

    return {
        "client_id": client_id,
        "client_secret": client_secret,
        "redirect_uri": normalize_redirect_uri(redirect_uri),
        "available_redirect_uris": available_redirect_uris,
    }


def save_uploaded_oauth_credentials(file_bytes: bytes) -> Dict[str, Any]:
    """
    Valide et enregistre un fichier credentials.json Google Cloud téléversé via l'UI.
    Supporte les formats 'web' (Application Web) et 'installed' (Application de bureau).
    Sauvegarde le fichier dans storage/credentials.json et à la racine.
    """
    try:
        data = json.loads(file_bytes.decode("utf-8"))
    except Exception as e:
        raise ValueError(f"Fichier JSON non valide : {e}")

    client_info = data.get("web") or data.get("installed")
    if not client_info:
        raise ValueError("Structure Google OAuth non reconnue (clé 'web' ou 'installed' introuvable).")

    client_id = client_info.get("client_id")
    client_secret = client_info.get("client_secret")
    if not client_id or not client_secret:
        raise ValueError("Identifiants (client_id ou client_secret) manquants dans le fichier.")

    # 1. Sauvegarde dans storage/credentials.json (prioritaire)
    STORAGE_CREDENTIALS.parent.mkdir(parents=True, exist_ok=True)
    with open(STORAGE_CREDENTIALS, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)

    # 2. Écrase également CREDENTIALS_FILE pour qu'aucun vieux fichier desktop ne persiste
    try:
        with open(CREDENTIALS_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
    except Exception:
        pass

    redirect_uris = client_info.get("redirect_uris", [])
    best_uri = get_best_redirect_uri(redirect_uris)

    return {
        "type": "web" if "web" in data else "installed",
        "client_id": client_id,
        "client_secret": client_secret,
        "redirect_uris": redirect_uris,
        "best_redirect_uri": best_uri,
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
    final_redirect = normalize_redirect_uri(redirect_uri or creds["redirect_uri"])

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
    Gère la résilience des redirections (localhost vs localhost:8501 vs Streamlit Cloud).
    """
    cleaned_code = extract_auth_code(code)
    creds = get_oauth_credentials()
    client_id = creds["client_id"]
    client_secret = creds["client_secret"]
    primary_redirect = normalize_redirect_uri(redirect_uri or creds["redirect_uri"])

    if not client_id or not client_secret:
        raise ValueError("Identifiants OAuth (client_id / client_secret) introuvables.")

    token_url = "https://oauth2.googleapis.com/token"

    # Liste ordonnée de redirect_uris à tester en cas de mismatch (ex: avec/sans slash final, localhost)
    candidate_uris = [primary_redirect]
    alt_slash = primary_redirect[:-1] if primary_redirect.endswith("/") else primary_redirect + "/"
    if alt_slash not in candidate_uris:
        candidate_uris.append(alt_slash)

    for alt in [
        "https://ecoleadnane.streamlit.app",
        "https://ecoleadnane.streamlit.app/",
        "http://localhost:8501",
        "http://localhost",
        "http://127.0.0.1:8501",
        "http://127.0.0.1",
        creds.get("redirect_uri"),
    ]:
        if alt and alt not in candidate_uris:
            candidate_uris.append(alt)

    last_error_text = ""
    token_data = None

    for target_redirect in candidate_uris:
        token_payload = {
            "code": cleaned_code,
            "client_id": client_id,
            "client_secret": client_secret,
            "redirect_uri": target_redirect,
            "grant_type": "authorization_code",
        }
        try:
            resp = requests.post(token_url, data=token_payload, timeout=15)
            if resp.status_code == 200:
                token_data = resp.json()
                logger.info(f"Échange OAuth réussi avec redirect_uri: {target_redirect}")
                break
            else:
                last_error_text = resp.text
                # Si l'erreur est distincte d'un redirect_uri_mismatch, inutile de continuer
                if "redirect_uri_mismatch" not in last_error_text:
                    break
        except Exception as e:
            last_error_text = str(e)

    if not token_data or not token_data.get("access_token"):
        logger.error(f"Échec de l'échange de token Google: {last_error_text}")
        raise ValueError(f"Échec d'authentification Google : {last_error_text}")

    access_token = token_data.get("access_token")

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
    try:
        user = create_or_get_google_user(email=email, name=name, avatar_url=avatar_url)
    except PermissionError as pe:
        raise ValueError(str(pe))

    # Enregistrement des tokens Google OAuth pour la sauvegarde Google Drive
    if user:
        try:
            if hasattr(st, "session_state"):
                st.session_state["google_oauth_tokens"] = token_data
            if user.get("role") == "admin":
                set_setting("google_drive_oauth_tokens", json.dumps(token_data))
                set_user_setting(user["id"], "google_oauth_tokens", json.dumps(token_data))
                if token_data.get("refresh_token"):
                    set_setting("google_drive_refresh_token", token_data["refresh_token"])
                    set_user_setting(user["id"], "google_drive_refresh_token", token_data["refresh_token"])
        except Exception as e:
            logger.warning(f"Impossible d'enregistrer les jetons Google Drive de l'administrateur : {e}")

    return user


def get_admin_google_tokens(user_id: Optional[int] = None) -> Optional[Dict[str, Any]]:
    """
    Récupère les jetons Google OAuth de l'administrateur pour l'accès API Google Drive.
    Cherche successivement :
    1. Session active (st.session_state)
    2. Paramètres individuels admin (user_settings)
    3. Paramètres globaux (settings)
    4. Fichier de token local (storage/token.json ou token.json)
    5. Streamlit Secrets (st.secrets)
    """
    try:
        if hasattr(st, "session_state") and "google_oauth_tokens" in st.session_state:
            tok = st.session_state["google_oauth_tokens"]
            if isinstance(tok, dict) and (tok.get("access_token") or tok.get("refresh_token")):
                return tok
    except Exception:
        pass

    if user_id:
        try:
            val = get_user_setting(user_id, "google_oauth_tokens")
            if val:
                return json.loads(val)
        except Exception:
            pass
        try:
            rt = get_user_setting(user_id, "google_drive_refresh_token")
            if rt:
                return {"refresh_token": rt}
        except Exception:
            pass

    try:
        val = get_setting("google_drive_oauth_tokens")
        if val:
            return json.loads(val)
    except Exception:
        pass

    try:
        rt = get_setting("google_drive_refresh_token")
        if rt:
            return {"refresh_token": rt}
    except Exception:
        pass

    # Vérification fichier token.json local
    for p in [Path("storage/token.json"), Path("token.json")]:
        if p.exists():
            try:
                return json.loads(p.read_text(encoding="utf-8"))
            except Exception:
                pass

    # Vérification Streamlit Secrets
    try:
        if hasattr(st, "secrets") and "google_drive" in st.secrets:
            sec = dict(st.secrets["google_drive"])
            if sec.get("refresh_token"):
                return sec
    except Exception:
        pass

    return None


def get_google_drive_connect_url(redirect_uri: Optional[str] = None) -> str:
    """Génère l'URL d'autorisation Google OAuth spécifique avec force consent pour Google Drive."""
    creds = get_oauth_credentials()
    client_id = creds["client_id"]
    final_redirect = normalize_redirect_uri(redirect_uri or creds["redirect_uri"])

    if not client_id:
        return ""

    params = {
        "client_id": client_id,
        "redirect_uri": final_redirect,
        "response_type": "code",
        "scope": " ".join(AUTH_SCOPES),
        "access_type": "offline",
        "prompt": "consent",
    }
    return f"https://accounts.google.com/o/oauth2/v2/auth?{urllib.parse.urlencode(params)}"



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
    if "session_token" not in st.session_state:
        st.session_state["session_token"] = None


def set_session_user(user: Dict[str, Any], token: Optional[str] = None) -> None:
    """Configure la session active de l'utilisateur et initialise son jeton persistant."""
    st.session_state["user"] = user
    st.session_state["user_id"] = user["id"]
    st.session_state["email"] = user["email"]
    st.session_state["name"] = user["name"]
    st.session_state["avatar"] = user.get("avatar_url")
    st.session_state["role"] = user["role"]
    st.session_state["is_authenticated"] = True

    # Création / association automatique d'un jeton de session persistant
    actual_token = token or st.session_state.get("session_token")
    if not actual_token and user.get("id"):
        try:
            actual_token = create_user_session(user["id"])
        except Exception:
            pass

    if actual_token:
        st.session_state["session_token"] = actual_token
        try:
            st.query_params["session"] = actual_token
        except Exception:
            pass


def restore_user_session_from_browser() -> Optional[Dict[str, Any]]:
    """
    Tente de restaurer la session utilisateur lors d'un rafraîchissement (F5) ou retour sur le site :
    1. Vérifie st.query_params['session']
    2. Vérifie le cookie de session st.context.cookies['ea_session']
    Si le jeton est valide en base, restaure immédiatement st.session_state.
    """
    if st.session_state.get("is_authenticated") and st.session_state.get("user"):
        return st.session_state["user"]

    token: Optional[str] = None
    try:
        token = st.query_params.get("session")
    except Exception:
        pass

    if not token:
        try:
            if hasattr(st, "context") and hasattr(st.context, "cookies"):
                token = st.context.cookies.get("ea_session")
        except Exception:
            pass

    if token:
        user = get_user_from_session_token(token)
        if user:
            set_session_user(user, token=token)
            return user
        else:
            # Token expiré ou révoqué
            try:
                if "session" in st.query_params:
                    del st.query_params["session"]
            except Exception:
                pass

    return None


def logout_user() -> None:
    """Détruit proprement la session utilisateur et révoque son jeton persistant."""
    current_token = st.session_state.get("session_token")
    try:
        if not current_token and "session" in st.query_params:
            current_token = st.query_params.get("session")
    except Exception:
        pass

    if current_token:
        try:
            delete_user_session(current_token)
        except Exception:
            pass

    st.session_state["is_authenticated"] = False
    st.session_state["user"] = None
    st.session_state["user_id"] = None
    st.session_state["email"] = None
    st.session_state["name"] = None
    st.session_state["avatar"] = None
    st.session_state["role"] = None
    if "session_token" in st.session_state:
        del st.session_state["session_token"]
    if "active_student_id" in st.session_state:
        del st.session_state["active_student_id"]
    try:
        if "session" in st.query_params:
            del st.query_params["session"]
    except Exception:
        pass


def dev_mode_login(email: str, name: str, role: Optional[str] = None) -> Dict[str, Any]:
    """
    Permet une connexion locale directe pour le développement,
    les tests unitaires ou le fonctionnement hors-ligne.
    Respecte la règle 'premier arrivé = admin' si role est None.
    """
    user = create_or_get_google_user(email=email, name=name, role=role)
    set_session_user(user)
    return user


def check_active_user_session(user_id: Optional[int]) -> Tuple[bool, Optional[str], Optional[Dict[str, Any]]]:
    """
    Vérifie en direct la validité de la session d'un utilisateur :
    - S'il n'existe plus en base (supprimé) -> (False, "deleted", None)
    - S'il est suspendu/bloqué -> (False, "blocked", user)
    - S'il est actif -> (True, None, user)
    """
    if not user_id:
        return False, "no_user", None

    user = get_user_by_id(user_id)
    if not user:
        return False, "deleted", None

    if user.get("is_blocked", 0) == 1:
        return False, "blocked", user

    return True, None, user


def is_running_on_streamlit_cloud() -> bool:
    """Détecte si l'application s'exécute sur l'infrastructure éphémère de Streamlit Cloud."""
    if os.getenv("IS_DEDICATED_SERVER") == "true":
        return False

    try:
        if hasattr(st, "context") and hasattr(st.context, "headers"):
            headers = st.context.headers or {}
            host = headers.get("x-forwarded-host") or headers.get("host") or ""
            if "streamlit.app" in host:
                return True
    except Exception:
        pass

    if any(k.startswith("STREAMLIT_SHARING") or k == "STREAMLIT_COMMUNITY_CLOUD" for k in os.environ):
        return True
    if os.path.exists("/mount/src/ecoleadnane"):
        return True

    return False


def check_and_handle_cloud_redirect() -> bool:
    """
    Si l'application est exécutée sur Streamlit Cloud (*.streamlit.app),
    affiche un écran de transition officiel et redirige automatiquement
    vers la nouvelle adresse permanente officielle : https://ecole.code-xpert.net
    Retourne True si la redirection a été traitée (pour appeler st.stop()).
    """
    if os.getenv("IS_DEDICATED_SERVER") == "true":
        return False

    # Injection du script client passif qui ne redirige que si le hostname client contient streamlit.app
    st.components.v1.html(
        """
        <script>
        (function() {
            try {
                var curHost = (window.top && window.top.location && window.top.location.hostname) ? window.top.location.hostname : window.location.hostname;
                if (curHost && curHost.indexOf("streamlit.app") !== -1) {
                    var targetUrl = "https://ecole.code-xpert.net" + (window.top.location.search || window.location.search || "");
                    window.top.location.replace(targetUrl);
                }
            } catch(e) {
                if (window.location.hostname && window.location.hostname.indexOf("streamlit.app") !== -1) {
                    window.location.replace("https://ecole.code-xpert.net" + (window.location.search || ""));
                }
            }
        })();
        </script>
        """,
        height=0,
    )

    if not is_running_on_streamlit_cloud():
        return False

    st.markdown(
        """
        <div style="max-width: 680px; margin: 40px auto; padding: 35px; background: linear-gradient(135deg, #1e293b 0%, #0f172a 100%); border: 2px solid #38bdf8; border-radius: 16px; text-align: center; color: #f8fafc; box-shadow: 0 10px 30px rgba(0,0,0,0.4);">
            <div style="font-size: 3.5rem; margin-bottom: 10px;">🎓</div>
            <h1 style="color: #38bdf8; font-size: 2rem; margin-bottom: 12px; font-weight: 700;">Ecole Adnane a déménagé !</h1>
            <p style="font-size: 1.15rem; line-height: 1.6; color: #cbd5e1; margin-bottom: 24px;">
                Afin de vous offrir une plateforme plus rapide, plus stable et sans interruption, l'école est désormais accessible sur son serveur officiel permanent :
            </p>
            <div style="background: rgba(56, 189, 248, 0.1); border: 1px dashed #38bdf8; border-radius: 10px; padding: 15px; margin-bottom: 25px;">
                <span style="font-size: 1.3rem; font-weight: 700; color: #38bdf8; font-family: monospace;">https://ecole.code-xpert.net</span>
            </div>
            <p style="font-size: 0.95rem; color: #94a3b8; margin-bottom: 25px;">
                🔄 Redirection automatique en cours vers le nouveau site...
            </p>
            <a href="https://ecole.code-xpert.net" target="_top" style="display: inline-block; background: #0284c7; color: #ffffff; text-decoration: none; font-weight: 600; padding: 14px 28px; border-radius: 10px; font-size: 1.1rem; box-shadow: 0 4px 12px rgba(2, 132, 199, 0.4);">
                🚀 Accéder directement à ecole.code-xpert.net
            </a>
        </div>
        """,
        unsafe_allow_html=True,
    )
    return True

