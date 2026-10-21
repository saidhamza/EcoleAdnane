"""
Module de gestion sécurisée de la configuration et des clés API.
Gère la lecture/écriture dans .env et la base de données, ainsi que les tests de connectivité avec découverte dynamique des modèles.
"""

import logging
import os
import time
from pathlib import Path
from typing import Any, Dict, List, Optional
from dotenv import dotenv_values, set_key

from models.database import get_setting, get_user_setting, set_setting, set_user_setting

logger = logging.getLogger(__name__)
ENV_FILE_PATH = Path(__file__).parent.parent / ".env"


def get_env_path() -> Path:
    """Retourne le chemin vers le fichier .env."""
    return ENV_FILE_PATH


def get_config_value(key: str, default: Optional[str] = None) -> Optional[str]:
    """
    Récupère une valeur de configuration dans l'ordre de priorité :
    1. Variable d'environnement active (os.environ)
    2. Streamlit Cloud Secrets (st.secrets)
    3. Fichier .env local
    4. Table SQLite settings
    5. Valeur par défaut
    """
    val = os.getenv(key)
    if val:
        return val

    try:
        import streamlit as st
        if hasattr(st, "secrets") and key in st.secrets:
            return str(st.secrets[key])
    except Exception:
        pass

    env_path = get_env_path()
    if env_path.exists():
        env_dict = dotenv_values(str(env_path))
        val = env_dict.get(key)
        if val:
            return val

    db_val = get_setting(key)
    if db_val:
        return db_val

    return default


def save_config_value(key: str, value: str) -> None:
    """Sauvegarde une valeur dans .env et dans SQLite."""
    value = value.strip()
    os.environ[key] = value
    set_setting(key, value)

    env_path = get_env_path()
    if not env_path.exists():
        env_path.touch(mode=0o600)
    set_key(str(env_path), key, value)


def get_gemini_api_key() -> Optional[str]:
    """Récupère la clé API Gemini globale."""
    return get_config_value("GEMINI_API_KEY")


def get_user_gemini_api_key(user_id: Optional[int] = None) -> Optional[str]:
    """
    Récupère la clé API Gemini de l'utilisateur actif.
    Stricte étanchéité : si user_id est fourni, cherche EXCLUSIVEMENT
    dans les paramètres individuels de cet utilisateur (aucun fallback système
    pour garantir que chaque élève utilise sa propre clé personnelle).
    """
    if user_id is not None:
        user_key = get_user_setting(user_id, "GEMINI_API_KEY")
        if user_key and user_key.strip():
            return user_key.strip()
        return None
    return get_gemini_api_key()


def save_user_gemini_api_key(user_id: int, api_key: str) -> None:
    """Enregistre la clé API Gemini individuelle d'un utilisateur."""
    set_user_setting(user_id, "GEMINI_API_KEY", api_key.strip())


def get_openai_api_key() -> Optional[str]:
    """Récupère la clé API OpenAI globale facultative."""
    return get_config_value("OPENAI_API_KEY")


def get_user_openai_api_key(user_id: Optional[int] = None) -> Optional[str]:
    """
    Récupère la clé API OpenAI de l'utilisateur actif.
    Stricte étanchéité : si user_id est fourni, cherche EXCLUSIVEMENT
    dans les paramètres individuels de cet utilisateur.
    """
    if user_id is not None:
        user_key = get_user_setting(user_id, "OPENAI_API_KEY")
        if user_key and user_key.strip():
            return user_key.strip()
        return None
    return get_openai_api_key()


def save_user_openai_api_key(user_id: int, api_key: str) -> None:
    """Enregistre la clé API OpenAI individuelle d'un utilisateur."""
    set_user_setting(user_id, "OPENAI_API_KEY", api_key.strip())


def test_user_gemini_connection(user_id: Optional[int] = None, api_key: Optional[str] = None) -> Dict[str, Any]:
    """Teste la connexion avec la clé API Gemini spécifique d'un utilisateur."""
    key = api_key or get_user_gemini_api_key(user_id)
    return test_gemini_connection(key)


def discover_gemini_model(client: Any) -> str:
    """
    Découvre dynamiquement le modèle Gemini le plus adapté disponible pour cette clé API.
    Privilégie les modèles Flash (2.0 ou 1.5) supportant generateContent.
    """
    try:
        available_models: List[str] = []
        for m in client.models.list():
            actions = getattr(m, "supported_actions", None) or []
            if not actions or "generateContent" in actions:
                available_models.append(m.name)

        if available_models:
            preferred_order = [
                "gemini-3.5-flash",
                "gemini-3.5-flash-lite",
                "gemini-3.1-flash-lite",
                "gemini-3-flash-preview",
                "gemini-3.8-flash",
                "gemini-flash-latest",
                "gemini-2.0-flash",
                "gemini-1.5-flash",
            ]
            for pref in preferred_order:
                for m_name in available_models:
                    clean = m_name.replace("models/", "")
                    if pref == clean:
                        return clean

            # Tout modèle Gemini flash disponible
            for m_name in available_models:
                clean = m_name.replace("models/", "")
                if "gemini" in clean.lower() and "flash" in clean.lower():
                    return clean
    except Exception as e:
        logger.warning(f"Impossible de lister les modèles Gemini ({e})")

    # Modèle par défaut standard
    return "gemini-3.5-flash"


def test_gemini_connection(api_key: Optional[str] = None) -> Dict[str, Any]:
    """
    Effectue un test de connexion ("ping") robuste vers l'API Google Gemini.
    Teste les modèles disponibles et enregistre automatiquement le modèle fonctionnel.
    """
    key = api_key or get_gemini_api_key()
    if not key:
        return {
            "success": False,
            "error": "Aucune clé API Gemini renseignée. Veuillez saisir votre clé.",
            "provider": "gemini",
        }

    start_time = time.time()
    last_err = ""

    # Utilisation du SDK officiel moderne google-genai
    try:
        from google import genai
        from google.genai import types

        client = genai.Client(api_key=key, http_options=types.HttpOptions(timeout=10000))

        # Découverte du modèle
        discovered_model = discover_gemini_model(client)
        candidates = [
            discovered_model,
            "gemini-3.5-flash",
            "gemini-3.5-flash-lite",
            "gemini-3.1-flash-lite",
            "gemini-3-flash-preview",
            "gemini-3.8-flash",
            "gemini-flash-latest",
        ]
        # Déduplication
        seen = set()
        unique_candidates = [m for m in candidates if not (m in seen or seen.add(m))]

        for model_name in unique_candidates:
            try:
                response = client.models.generate_content(
                    model=model_name,
                    contents="Réponds uniquement par: OK",
                )
                elapsed = round(time.time() - start_time, 2)
                reply = (response.text or "").strip()
                # Sauvegarde du modèle fonctionnel en base
                set_setting("GEMINI_ACTIVE_MODEL", model_name)
                return {
                    "success": True,
                    "provider": "gemini",
                    "sdk": "google-genai",
                    "model": model_name,
                    "latency": elapsed,
                    "message": f"Connexion Gemini établie avec succès en {elapsed}s (modèle : '{model_name}') ! Réponse : {reply}",
                }
            except Exception as e_model:
                last_err = str(e_model)
                continue
    except Exception as e_genai:
        last_err = str(e_genai)

    return {
        "success": False,
        "provider": "gemini",
        "error": f"Échec de connexion à Gemini : {last_err}",
        "tip": "Vérifiez que votre clé est bien issue de https://aistudio.google.com/ et que le projet est actif.",
    }


def test_openai_connection(api_key: Optional[str] = None) -> Dict[str, Any]:
    """Effectue un test de connexion rapide vers OpenAI."""
    key = api_key or get_openai_api_key()
    if not key:
        return {
            "success": False,
            "error": "Aucune clé API OpenAI renseignée.",
            "provider": "openai",
        }

    start_time = time.time()
    try:
        from openai import OpenAI
        client = OpenAI(api_key=key)
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": "Ping"}],
            max_tokens=5,
        )
        elapsed = round(time.time() - start_time, 2)
        return {
            "success": True,
            "provider": "openai",
            "model": "gpt-4o-mini",
            "latency": elapsed,
            "message": f"Connexion OpenAI établie avec succès en {elapsed}s !",
        }
    except Exception as e:
        return {
            "success": False,
            "provider": "openai",
            "error": f"Échec OpenAI : {str(e)}",
        }


def test_active_connection() -> Dict[str, Any]:
    """Teste la connexion active."""
    if get_gemini_api_key():
        return test_gemini_connection()
    elif get_openai_api_key():
        return test_openai_connection()
    return {
        "success": False,
        "error": "Aucune clé API configurée. Veuillez ajouter votre clé Gemini gratuite dans l'onglet Configuration.",
    }
