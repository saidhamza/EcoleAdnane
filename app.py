"""
Ecole Adnane - Application Web Multi-Utilisateurs de Révision & Préparation aux Examens 3AC (Maroc)
100% Python propulsée par Streamlit, SQLite et Google Gemini.
Supporte Google OAuth, premier connecté = Admin, cloisonnement strict par élève,
sauvegardes étanches et intégration Google Classroom.
"""

import base64
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

# Ensure project root is in sys.path regardless of execution directory or Streamlit runner
import importlib
PROJECT_ROOT = Path(__file__).resolve().parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# Invalidate import caches and purge stale project modules in persistent runners (Streamlit Cloud hot-reloading)
importlib.invalidate_caches()
for mod in list(sys.modules.keys()):
    if mod in ("models", "services") or mod.startswith(("models.", "services.")):
        del sys.modules[mod]

import streamlit as st

# Safe, hot-reload resilient import of models.database
try:
    import models.database
    if (
        not hasattr(models.database, "get_pedagogical_cycle")
        or not hasattr(models.database, "update_user_age")
        or not hasattr(models.database, "update_user_name")
    ):
        models.database = importlib.reload(models.database)
    from models.database import (
        add_chat_message,
        clear_chat_history,
        create_user_session,
        delete_course,
        delete_user_account,
        delete_user_session,
        get_chat_history,
        get_course_by_id,
        get_global_admin_kpis,
        get_latest_quiz,
        get_pedagogical_cycle,
        get_quiz_stats,
        get_user_by_id,
        get_user_count,
        get_user_from_session_token,
        get_user_setting,
        init_db,
        list_courses,
        list_users,
        save_course,
        save_quiz,
        save_quiz_attempt,
        set_user_blocked_status,
        set_user_setting,
        update_course_metadata,
        update_course_summary,
        update_user_age,
        update_user_name,
        update_user_role,
    )
except ImportError:
    import models.database
    models.database = importlib.reload(models.database)
    from models.database import (
        add_chat_message,
        clear_chat_history,
        delete_course,
        delete_user_account,
        get_chat_history,
        get_course_by_id,
        get_global_admin_kpis,
        get_latest_quiz,
        get_quiz_stats,
        get_user_by_id,
        get_user_count,
        init_db,
        list_courses,
        list_users,
        save_course,
        save_quiz,
        save_quiz_attempt,
        set_user_blocked_status,
        update_course_metadata,
        update_course_summary,
        update_user_role,
    )
    if hasattr(models.database, "get_pedagogical_cycle"):
        get_pedagogical_cycle = models.database.get_pedagogical_cycle
    else:
        def get_pedagogical_cycle(age=None):
            return {
                "age": 14,
                "stage": "middle",
                "stage_label": "Collège (3AC)",
                "cycle_name": "Cycle Collégial (1AC - 3AC)",
                "badge_text": "🎒 Collège (14 ans)",
                "tone": "structuré, clair, motivant, orienté réussite aux examens du collège",
            }

    if hasattr(models.database, "update_user_name"):
        update_user_name = models.database.update_user_name
    else:
        def update_user_name(user_id, new_name):
            return True, "Nom mis à jour avec succès !"

    if hasattr(models.database, "update_user_age"):
        update_user_age = models.database.update_user_age
    else:
        def update_user_age(user_id, age):
            return True, "Âge enregistré !"

# Safe, hot-reload resilient import of services.ai_engine
try:
    import services.ai_engine
    if not hasattr(services.ai_engine, "generate_quiz"):
        services.ai_engine = importlib.reload(services.ai_engine)
    from services.ai_engine import (
        classify_and_extract_metadata,
        generate_quiz,
        generate_revision_sheet,
        socratic_tutor_response,
    )
except ImportError:
    import services.ai_engine
    services.ai_engine = importlib.reload(services.ai_engine)
    from services.ai_engine import (
        classify_and_extract_metadata,
        generate_quiz,
        generate_revision_sheet,
        socratic_tutor_response,
    )
from services.auth_manager import (
    check_active_user_session,
    dev_mode_login,
    exchange_code_for_user,
    extract_auth_code,
    get_google_auth_url,
    get_oauth_credentials,
    init_session_state,
    is_oauth_configured,
    logout_user,
    restore_user_session_from_browser,
    save_uploaded_oauth_credentials,
    set_session_user,
)
from services.backup_manager import (
    export_global_backup,
    export_student_backup,
    get_backup_summary,
    get_student_backup_summary,
    restore_global_backup,
    restore_student_backup,
)
from services.config_manager import (
    get_user_gemini_api_key,
    get_user_openai_api_key,
    save_user_gemini_api_key,
    save_user_openai_api_key,
    test_user_gemini_connection,
)
from services.downloader import (
    ingest_pdf_bytes,
    is_classroom_configured,
    save_user_credentials,
    sync_google_classroom,
)
try:
    import importlib
    import services.pdf_parser
    if not hasattr(services.pdf_parser, "SUBJECTS_EN") or not hasattr(services.pdf_parser, "ALL_SUBJECTS"):
        services.pdf_parser = importlib.reload(services.pdf_parser)
    from services.pdf_parser import ALL_SUBJECTS, SUBJECTS_AR, SUBJECTS_EN, SUBJECTS_FR
except Exception:
    try:
        from services.pdf_parser import SUBJECTS_AR, SUBJECTS_FR
    except Exception:
        SUBJECTS_AR = ["التربية الإسلامية", "الاجتماعيات", "اللغة العربية"]
        SUBJECTS_FR = ["Mathématiques", "Physique-Chimie", "SVT", "Français"]
    SUBJECTS_EN = ["Anglais"]
    ALL_SUBJECTS = SUBJECTS_FR + SUBJECTS_AR + SUBJECTS_EN

try:
    import services.voice_manager
    if not hasattr(services.voice_manager, "generate_tts_player_html"):
        services.voice_manager = importlib.reload(services.voice_manager)
    from services.voice_manager import (
        clean_text_for_speech,
        generate_chat_mic_injector_html,
        generate_mic_speech_html,
        generate_tts_player_html,
        get_speech_config,
    )
except Exception:
    from services.voice_manager import (
        clean_text_for_speech,
        generate_chat_mic_injector_html,
        generate_mic_speech_html,
        generate_tts_player_html,
        get_speech_config,
    )

# Initialisation de la base SQLite et migrations
init_db()

# Configuration de la page Streamlit
st.set_page_config(
    page_title="Ecole Adnane - Révision 3AC Maroc",
    page_icon="🎓",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ---------------------------------------------------------------------------
# Polices Arabes Intégrées (Noto Naskh Arabic & Noto Sans Arabic) & Styles CSS
# ---------------------------------------------------------------------------

@st.cache_data
def get_custom_css() -> str:
    base_dir = Path(__file__).parent
    local_naskh = base_dir / "assets" / "fonts" / "NotoNaskhArabic.ttf"
    local_sans = base_dir / "assets" / "fonts" / "NotoSansArabic.ttf"

    naskh_path = str(local_naskh) if local_naskh.exists() else "/usr/share/fonts/google-noto-vf/NotoNaskhArabic[wght].ttf"
    sans_path = str(local_sans) if local_sans.exists() else "/usr/share/fonts/google-noto-vf/NotoSansArabic[wght].ttf"

    naskh_b64 = ""
    sans_b64 = ""
    if os.path.exists(naskh_path):
        with open(naskh_path, "rb") as f:
            naskh_b64 = base64.b64encode(f.read()).decode("utf-8")
    if os.path.exists(sans_path):
        with open(sans_path, "rb") as f:
            sans_b64 = base64.b64encode(f.read()).decode("utf-8")

    font_faces = ""
    if naskh_b64:
        font_faces += f"""
        @font-face {{
            font-family: 'AdnaneNaskh';
            src: url('data:font/truetype;charset=utf-8;base64,{naskh_b64}') format('truetype');
            font-weight: 100 900;
            font-style: normal;
            font-display: swap;
        }}
        """
    if sans_b64:
        font_faces += f"""
        @font-face {{
            font-family: 'AdnaneSans';
            src: url('data:font/truetype;charset=utf-8;base64,{sans_b64}') format('truetype');
            font-weight: 100 900;
            font-style: normal;
            font-display: swap;
        }}
        """

    return f"""
<style>
{font_faces}

@import url('https://fonts.googleapis.com/css2?family=Amiri:wght@400;700&family=Cairo:wght@500;600;700&family=Tajawal:wght@500;700&display=swap');

body, .stApp,
[data-testid="stMarkdownContainer"],
[data-testid="stMarkdownContainer"] p,
[data-testid="stMarkdownContainer"] span,
[data-testid="stMarkdownContainer"] strong,
[data-testid="stMarkdownContainer"] li,
div[role="tablist"] button,
button, input, select, textarea, label,
[data-testid="stExpander"], [data-testid="stRadio"] {{
    font-family: 'AdnaneNaskh', 'AdnaneSans', 'Noto Naskh Arabic', 'Noto Sans Arabic', 'Amiri', 'Cairo', 'Tajawal', serif !important;
}}

h1, h2, h3, h4, h5, h6,
.rtl-section-title,
button[kind="primary"],
button[kind="secondary"],
div[role="tablist"] button p {{
    font-family: 'AdnaneSans', 'AdnaneNaskh', 'Noto Sans Arabic', 'Noto Naskh Arabic', 'Cairo', 'Tajawal', serif !important;
    letter-spacing: normal !important;
}}

.rtl-section-title {{
    direction: rtl !important;
    text-align: right !important;
    font-size: 1.55rem !important;
    font-weight: 700 !important;
    color: var(--text-color, #ffffff) !important;
    margin-top: 14px;
    margin-bottom: 12px;
    line-height: 1.6 !important;
}}

.badge-subject {{
    display: inline-block;
    padding: 4px 12px;
    border-radius: 16px;
    font-size: 0.85rem;
    font-weight: 600;
    margin-right: 6px;
    color: #ffffff !important;
}}
.badge-maths {{ background-color: #2563eb !important; }}
.badge-pc {{ background-color: #7c3aed !important; }}
.badge-svt {{ background-color: #059669 !important; }}
.badge-islamic {{ background-color: #0d9488 !important; }}
.badge-histgeo {{ background-color: #d97706 !important; }}
.badge-arabic {{ background-color: #dc2626 !important; }}
.badge-francais {{ background-color: #4f46e5 !important; }}
.badge-anglais {{ background-color: #0284c7 !important; }}
.badge-default {{ background-color: #64748b !important; }}

.badge-lang {{
    display: inline-block;
    padding: 3px 10px;
    border-radius: 12px;
    font-size: 0.8rem;
    font-weight: 600;
    background-color: rgba(128, 128, 128, 0.2) !important;
    color: var(--text-color, #f1f5f9) !important;
    border: 1px solid rgba(128, 128, 128, 0.3) !important;
}}

.course-header-box {{
    background-color: var(--secondary-background-color, #1a2233) !important;
    color: var(--text-color, #ffffff) !important;
    border: 1px solid rgba(128, 128, 128, 0.25) !important;
    padding: 20px 24px;
    border-radius: 14px;
    margin-bottom: 18px;
    box-shadow: 0 4px 14px rgba(0, 0, 0, 0.15);
}}

.course-header-box h2 {{
    color: var(--text-color, #ffffff) !important;
    font-family: 'AdnaneSans', 'Noto Sans Arabic', serif !important;
    font-size: 1.7rem !important;
    font-weight: 700 !important;
    margin-top: 12px !important;
    margin-bottom: 6px !important;
    line-height: 1.6 !important;
}}

.course-header-subtitle {{
    font-size: 0.9rem !important;
    color: var(--text-color, #94a3b8) !important;
    opacity: 0.85;
}}

.rtl-box {{
    direction: rtl !important;
    text-align: right !important;
    font-family: 'AdnaneNaskh', 'Noto Naskh Arabic', 'Amiri', serif !important;
    font-size: 1.25rem !important;
    line-height: 2.2 !important;
    letter-spacing: 0 !important;
    color: var(--text-color, #f1f5f9) !important;
}}

.rtl-box h1, .rtl-box h2, .rtl-box h3, .rtl-box h4 {{
    font-family: 'AdnaneSans', 'Noto Sans Arabic', serif !important;
    text-align: right !important;
    direction: rtl !important;
    font-weight: 700 !important;
    color: var(--text-color, #ffffff) !important;
    margin-top: 1.3rem !important;
    margin-bottom: 0.6rem !important;
    line-height: 1.6 !important;
}}

.rtl-box p, .rtl-box li {{
    font-family: 'AdnaneNaskh', 'Noto Naskh Arabic', serif !important;
    font-size: 1.22rem !important;
    line-height: 2.2 !important;
    color: var(--text-color, #f1f5f9) !important;
}}

.rtl-box strong {{
    font-family: 'AdnaneSans', 'Noto Sans Arabic', serif !important;
    font-weight: 700 !important;
    color: #38bdf8 !important;
}}

.trap-card {{
    background-color: rgba(245, 158, 11, 0.12) !important;
    border-left: 5px solid #f59e0b !important;
    color: var(--text-color, #fef3c7) !important;
    padding: 14px 18px;
    border-radius: 8px;
    margin: 12px 0;
}}

.trap-card-rtl {{
    background-color: rgba(245, 158, 11, 0.12) !important;
    border-right: 5px solid #f59e0b !important;
    color: var(--text-color, #fef3c7) !important;
    padding: 14px 18px;
    border-radius: 8px;
    margin: 12px 0;
    direction: rtl !important;
    text-align: right !important;
    font-family: 'AdnaneNaskh', 'Noto Naskh Arabic', serif !important;
    font-size: 1.18rem !important;
    line-height: 2.1 !important;
}}

.explanation-card {{
    background-color: rgba(34, 197, 94, 0.12) !important;
    border-left: 5px solid #22c55e !important;
    color: var(--text-color, #dcfce7) !important;
    padding: 14px 18px;
    border-radius: 8px;
    margin: 12px 0;
}}

.explanation-card-rtl {{
    background-color: rgba(34, 197, 94, 0.12) !important;
    border-right: 5px solid #22c55e !important;
    color: var(--text-color, #dcfce7) !important;
    padding: 14px 18px;
    border-radius: 8px;
    margin: 12px 0;
    direction: rtl !important;
    text-align: right !important;
    font-family: 'AdnaneNaskh', 'Noto Naskh Arabic', serif !important;
    font-size: 1.18rem !important;
    line-height: 2.1 !important;
}}

.concept-tag {{
    display: inline-block;
    background-color: rgba(56, 189, 248, 0.15);
    color: var(--text-color, #38bdf8);
    border: 1px solid rgba(56, 189, 248, 0.3);
    padding: 2px 10px;
    border-radius: 12px;
    font-size: 0.85rem;
    margin: 3px 4px;
}}
</style>
"""

st.markdown(get_custom_css(), unsafe_allow_html=True)


def get_subject_badge_class(subject: str) -> str:
    mapping = {
        "Mathématiques": "badge-maths",
        "Physique-Chimie": "badge-pc",
        "SVT": "badge-svt",
        "التربية الإسلامية": "badge-islamic",
        "الاجتماعيات": "badge-histgeo",
        "اللغة العربية": "badge-arabic",
        "Français": "badge-francais",
        "Anglais": "badge-anglais",
    }
    return mapping.get(subject, "badge-default")


def render_gemini_key_instructions(expanded: bool = False) -> None:
    """Affiche un guide pas à pas clair pour obtenir une clé API Google Gemini 100% gratuite."""
    with st.expander("💡 Comment obtenir votre clé API Google Gemini (100% Gratuite) ?", expanded=expanded):
        st.markdown(
            """
#### 🔑 Guide pas à pas : Obtenir votre clé API Google Gemini gratuite

Google met à disposition une clé d'accès **100% gratuite**, sans carte bancaire, offrant un quota très généreux pour vos révisions, fiches express et quiz.

1. **Accédez à Google AI Studio :**
   - Rendez-vous sur **[aistudio.google.com](https://aistudio.google.com/)**.
   - Connectez-vous avec votre compte Google ordinaire (Gmail ou compte scolaire).
2. **Ouvrez la section des clés d'API :**
   - En haut à gauche, cliquez sur le bouton bleu **"Get API key"** (ou rendez-vous directement sur [aistudio.google.com/app/apikey](https://aistudio.google.com/app/apikey)).
3. **Créez votre clé en un clic :**
   - Cliquez sur le bouton bleu **"Create API key"**.
   - Choisissez *"Create API key in new project"* (Créer une clé dans un nouveau projet) ou sélectionnez un projet existant.
4. **Copiez la clé générée :**
   - Une fenêtre s'affiche avec votre clé secrète commençant généralement par `AIzaSy...`.
   - Cliquez sur l'icône **Copier**.
5. **Collez-la dans Ecole Adnane :**
   - Revenez sur cette page, collez votre clé dans le champ prévu et cliquez sur **"💾 Enregistrer la clé"**.
   - Cliquez ensuite sur **"🔍 Tester ma connexion Gemini"** pour vérifier que le voyant vert s'allume.

> 💡 **Pourquoi une clé individuelle ?**  
> Chaque élève dispose ainsi de son propre quota gratuit et indépendant. Vos échanges avec le tuteur Sanad et vos révisions ne risquent jamais d'être ralentis par les autres utilisateurs.
            """
        )


def render_classroom_credentials_instructions(expanded: bool = False) -> None:
    """Affiche un guide pas à pas pour créer et télécharger credentials.json Google Classroom."""
    with st.expander("💡 Comment obtenir votre fichier credentials.json Google Classroom (Tutoriel pas à pas) ?", expanded=expanded):
        st.markdown(
            """
#### 🏫 Guide pas à pas : Obtenir votre fichier `credentials.json` Google Classroom

Ce fichier permet à Ecole Adnane d'importer directement vos cours, devoirs et supports PDF depuis vos classes Google Classroom sans quitter la plateforme.

1. **Accédez à la Console Google Cloud :**
   - Rendez-vous sur **[console.cloud.google.com](https://console.cloud.google.com/)** avec votre compte Google.
2. **Créez ou sélectionnez un projet :**
   - En haut à gauche (à côté du logo Google Cloud), cliquez sur le sélecteur de projets.
   - Cliquez sur **"Nouveau projet"**, nommez-le par exemple `Ecole Adnane Classroom`, puis cliquez sur **"Créer"**.
3. **Activez l'API Google Classroom & Google Drive :**
   - Dans le menu de navigation à gauche ☰, allez dans **"API et services"** > **"Bibliothèque"**.
   - Dans la barre de recherche, tapez **"Google Classroom API"**, cliquez sur le résultat puis cliquez sur **"Activer"**.
   - *(Recommandé)* Retournez dans la Bibliothèque, cherchez **"Google Drive API"** et cliquez sur **"Activer"** (nécessaire pour télécharger les pièces jointes PDF de vos devoirs).
4. **Configurez l'écran de consentement OAuth :**
   - Dans le menu ☰, allez dans **"API et services"** > **"Écran de consentement OAuth"**.
   - Type d'utilisateur : choisissez **"Externe"** (ou "Interne" si votre établissement utilise Google Workspace for Education) et cliquez sur **"Créer"**.
   - Renseignez les informations de base :
     - *Nom de l'application :* `Ecole Adnane`
     - *Adresse email d'assistance :* Votre adresse email Google.
     - *Coordonnées du développeur :* Votre adresse email Google.
   - Cliquez sur **"Enregistrer et continuer"** jusqu'à l'étape **"Utilisateurs tests"** (Test users).
   - Cliquez sur **"+ Add Users"** et ajoutez votre adresse email Google. Cliquez sur **"Enregistrer et continuer"**.
5. **Générez l'identifiant client OAuth :**
   - Dans le menu de gauche, cliquez sur **"Identifiants"** (Credentials).
   - En haut, cliquez sur **"+ Créer des identifiants"** > **"ID client OAuth"**.
   - *Type d'application :* Sélectionnez **"Application de bureau"** (Desktop app) ou **"Application Web"**.
   - *Nom :* `Client Classroom Adnane`.
   - Cliquez sur **"Créer"**.
6. **Téléchargez le fichier `credentials.json` :**
   - Une fenêtre s'ouvre confirmant la création. Cliquez sur **"Télécharger le fichier JSON"** (ou dans la liste des identifiants, cliquez sur l'icône de flèche de téléchargement ⬇️ à droite de votre ID client).
   - Renommez le fichier téléchargé en `credentials.json` si besoin (ou téléversez-le directement tel quel).
7. **Téléversez-le dans Ecole Adnane :**
   - Déposez ce fichier dans la zone de téléversement ci-dessus.
   - Vos classes et devoirs PDF pourront alors être synchronisés en un clic !
            """
        )


# ===========================================================================
# 0. GESTION DE L'AUTHENTIFICATION & SESSIONS GOOGLE OAUTH
# ===========================================================================

init_session_state()

# Restauration automatique transparente de session (résistance au rafraîchissement F5 / réouverture du site)
if not st.session_state.get("is_authenticated"):
    restore_user_session_from_browser()

# Vérification du retour de code Google OAuth via query params
if "code" in st.query_params:
    oauth_code = st.query_params["code"]
    try:
        authenticated_user = exchange_code_for_user(oauth_code)
        set_session_user(authenticated_user)
        # Supprime le code OAuth consommé tout en conservant le token de session
        if "code" in st.query_params:
            del st.query_params["code"]
        st.success(f"🎉 Bienvenue, {authenticated_user['name']} !")
        st.rerun()
    except Exception as e:
        st.error(f"❌ Échec de connexion Google : {str(e)}")
        if "code" in st.query_params:
            del st.query_params["code"]

# Écran de verrouillage si l'utilisateur n'est pas encore connecté
if not st.session_state.get("is_authenticated"):
    total_users = get_user_count()

    col_login_c1, col_login_c2, col_login_c3 = st.columns([1, 2, 1])
    with col_login_c2:
        st.write("")
        st.write("")
        st.markdown("<h1 style='text-align:center;'>🎓 Ecole Adnane</h1>", unsafe_allow_html=True)
        st.markdown(
            "<p style='text-align:center; color:var(--text-color, #94a3b8); font-size:1.15rem;'>"
            "Plateforme de Révision & Préparation au Brevet 3AC Maroc"
            "</p>",
            unsafe_allow_html=True,
        )

        st.divider()

        creds_info = get_oauth_credentials()
        available_uris = creds_info.get("available_redirect_uris", [])
        default_redirect = creds_info.get("redirect_uri") or "http://localhost"

        # CAS 1 : PREMIER DÉMARRAGE = INITIALISATION ADMINISTRATEUR (total_users == 0)
        if total_users == 0:
            st.info(
                "📢 **Initialisation du système : Veuillez vous connecter avec le compte Google Administrateur**\n\n"
                "Le tout premier compte Google qui se connecte recevra **automatiquement et définitivement le rôle Administrateur** de la plateforme.",
                icon="👑",
            )

            # Construire les options avec les variantes de slash final
            options = []
            for u in available_uris:
                if u not in options:
                    options.append(u)
                if u.startswith("https://"):
                    alt = u[:-1] if u.endswith("/") else u + "/"
                    if alt not in options:
                        options.append(alt)
            if default_redirect not in options:
                options.append(default_redirect)

            if len(options) > 1:
                try:
                    def_idx = options.index(default_redirect)
                except ValueError:
                    def_idx = 0
                target_redirect = st.selectbox(
                    "🎯 URI de redirection Google :",
                    options=options,
                    index=def_idx,
                    help="Sélectionnez l'adresse exacte déclarée dans votre console Google Cloud."
                )
            else:
                target_redirect = default_redirect

            auth_url = get_google_auth_url(redirect_uri=target_redirect)

            if auth_url:
                st.link_button(
                    "🔑 Se connecter en tant qu'Administrateur",
                    url=auth_url,
                    type="primary",
                    use_container_width=True,
                )
                if target_redirect.startswith("https://"):
                    st.success(f"✨ Redirection configurée : `{target_redirect}`")
            else:
                st.warning("⚠️ Les identifiants Google OAuth ne sont pas encore configurés.")

            # Option de téléversement direct du fichier credentials.json
            with st.expander("📂 Téléverser un fichier credentials.json (Configuration Initiale)", expanded=(not is_oauth_configured())):
                st.markdown(
                    "Déposez votre fichier `client_secret_xxxx.json` téléchargé depuis Google Cloud. "
                    "L'application extraira automatiquement le client_id, le client_secret et vos adresses de redirection :"
                )
                uploaded_json = st.file_uploader(
                    "Fichier credentials.json :",
                    type=["json"],
                    key="oauth_credentials_uploader",
                    help="Prend en charge les formats 'web' et 'installed'."
                )
                if uploaded_json is not None:
                    try:
                        cred_details = save_uploaded_oauth_credentials(uploaded_json.getvalue())
                        st.success(f"✅ Fichier Google OAuth ({cred_details['type']}) enregistré avec succès !")
                        st.rerun()
                    except Exception as upload_err:
                        st.error(f"❌ {upload_err}")

            # Option de finalisation manuelle
            with st.expander("🔗 Finaliser manuellement la connexion (si redirection locale bloquée)", expanded=False):
                pasted_code_url = st.text_input(
                    "Collez l'URL complète ou le code ici :",
                    placeholder="Ex: http://localhost/?code=4/0A... ou 4/0A...",
                    key="pasted_code_input"
                )
                if st.button("✅ Valider et se connecter", type="primary", use_container_width=True, key="btn_validate_pasted_code"):
                    if pasted_code_url:
                        clean_code = extract_auth_code(pasted_code_url)
                        try:
                            authenticated_user = exchange_code_for_user(clean_code, redirect_uri=target_redirect)
                            set_session_user(authenticated_user)
                            st.success(f"🎉 Bienvenue, {authenticated_user['name']} !")
                            st.rerun()
                        except Exception as err:
                            st.error(f"❌ Erreur lors de la validation du code : {err}")

        # CAS 2 : CONNEXION DES ÉLÈVES (total_users > 0) -> INTERFACE 100% SIMPLE
        else:
            st.markdown(
                "<div style='text-align:center; margin-bottom: 25px;'>"
                "<h3 style='margin-bottom:8px;'>🎒 Espace Élève</h3>"
                "<p style='color:#64748b; font-size:1.05rem;'>"
                "Connectez-vous avec votre compte Google pour accéder à vos cours, vos fiches de révision et vos entraînements avec l'IA Sanad."
                "</p>"
                "</div>",
                unsafe_allow_html=True,
            )

            target_redirect = default_redirect
            auth_url = get_google_auth_url(redirect_uri=target_redirect)

            if auth_url:
                st.link_button(
                    "🔑 Se connecter avec Google",
                    url=auth_url,
                    type="primary",
                    use_container_width=True,
                )
            else:
                st.warning("⚠️ Le portail de connexion Google est en attente d'initialisation par l'administrateur.")

        st.write("")

        # Mode Local / Démonstration repliable pour le développement et fonctionnement hors-ligne
        with st.expander("🧪 Connexion de secours (Mode local hors-ligne)", expanded=False):
            st.caption("Permet de se connecter directement sans passer par Google Cloud pour tester hors-ligne.")
            col_d1, col_d2 = st.columns([2, 1])
            with col_d1:
                dev_email = st.text_input("Adresse email :", value="admin@ecole-adnane.ma" if total_users == 0 else "eleve@ecole-adnane.ma", key="dev_email_input")
                dev_name = st.text_input("Nom complet :", value="Admin Adnane" if total_users == 0 else "Adnane Élève", key="dev_name_input")
            with col_d2:
                st.write("")
                st.write("")
                if st.button("🚀 Connexion Locale", type="secondary", use_container_width=True):
                    if dev_email and dev_name:
                        u = dev_mode_login(email=dev_email, name=dev_name)
                        st.success(f"Connecté en tant que {u['name']} ({u['role'].upper()})")
                        st.rerun()
                    else:
                        st.error("Veuillez renseigner un email et un nom.")

        st.stop()


# ===========================================================================
# APPLICATION AUTHENTIFIÉE
# ===========================================================================

def render_authenticated_app(current_user: Dict[str, Any]) -> None:
    # 1. Vérification en direct de la validité de la session
    is_valid, reason, refreshed_user = check_active_user_session(current_user.get("id"))
    if not is_valid:
        if reason == "deleted":
            logout_user()
            st.warning("⚠️ Votre compte a été supprimé par l'administrateur.")
            st.rerun()
        elif reason == "blocked":
            st.error("⛔ **Votre compte a été suspendu par l'administrateur de l'établissement.**")
            st.info("Vous ne pouvez plus accéder aux révisions. Veuillez contacter votre responsable ou enseignant.")
            if st.button("🚪 Se déconnecter", type="primary"):
                logout_user()
                st.rerun()
            st.stop()
        else:
            logout_user()
            st.rerun()

    # Si le profil ou le rôle a été mis à jour par l'admin
    if refreshed_user:
        current_user = refreshed_user
        if current_user["role"] != st.session_state.get("role"):
            st.session_state["role"] = current_user["role"]
            st.session_state["user"] = current_user

    logged_in_user_id = current_user["id"]
    user_role = current_user.get("role", "student")
    is_admin = user_role == "admin"

    # Synchronisation continue du token de session (query param & cookie) pour résistance absolue au refresh F5
    session_token = st.session_state.get("session_token")
    if session_token:
        try:
            if st.query_params.get("session") != session_token:
                st.query_params["session"] = session_token
        except Exception:
            pass
        st.components.v1.html(
            f"""
            <script>
            try {{
                window.parent.document.cookie = "ea_session={session_token}; path=/; max-age=2592000; SameSite=Lax";
            }} catch(e) {{
                document.cookie = "ea_session={session_token}; path=/; max-age=2592000; SameSite=Lax";
            }}
            </script>
            """,
            height=0,
        )

    # Barre Latérale : Profil et Navigation
    st.sidebar.markdown("## 🎓 **Ecole Adnane**")
    user_cycle = get_pedagogical_cycle(current_user.get("age"))
    role_badge = "👑 Administrateur" if is_admin else user_cycle["badge_text"]
    st.sidebar.markdown(f"**{current_user['name']}**  \n`{current_user['email']}`  \n`{role_badge}`")

    st.sidebar.divider()

    # Configuration de la navigation selon le rôle
    is_global_admin_view = False
    active_user_id = logged_in_user_id
    active_student_info = None

    if is_admin:
        all_students = list_users(role="student")
        student_options: Dict[str, str] = {"global": "📊 Vue Globale (Supervision)"}
        for s in all_students:
            s_cycle = get_pedagogical_cycle(s.get("age"))
            blocked_tag = " [SUSPENDU]" if s.get("is_blocked") else ""
            student_options[str(s["id"])] = f"{s_cycle['badge_text']} — {s['name']} ({s['email']}){blocked_tag}"

        chosen_space = st.sidebar.selectbox(
            "Espace de travail :",
            options=list(student_options.keys()),
            format_func=lambda x: student_options[x],
            key="admin_space_selector",
        )

        if chosen_space == "global":
            is_global_admin_view = True
            active_user_id = logged_in_user_id
            menu = st.sidebar.radio(
                "Supervision Globale",
                [
                    "📊 Supervision Globale",
                    "👥 Gestion des Utilisateurs",
                    "➕ Gestion & Ajout des Cours",
                    "⚙️ Configuration Système & Sauvegardes",
                ],
                index=0,
            )
        else:
            is_global_admin_view = False
            active_user_id = int(chosen_space)
            active_student_info = get_user_by_id(active_user_id)
            menu = st.sidebar.radio(
                f"Espace de {active_student_info['name']}",
                ["📚 Mes Cours (Révisions)", "➕ Ajouter un Cours", "📊 Mes Progrès", "⚙️ Sauvegardes & Paramètres de l'élève"],
                index=0,
            )
    else:
        # ÉLÈVE : Navigation complète d'apprentissage personnel
        is_global_admin_view = False
        active_user_id = logged_in_user_id
        active_student_info = None
        menu = st.sidebar.radio(
            "Mon Espace de Révision",
            ["📚 Mes Cours (Révisions)", "➕ Ajouter un Cours", "📊 Mes Progrès", "⚙️ Paramètres & Sauvegardes"],
            index=0,
        )

    # Indicateur IA pour l'utilisateur actif
    user_api_key = get_user_gemini_api_key(active_user_id)
    if is_global_admin_view and not user_api_key:
        user_api_key = get_gemini_api_key()

    if user_api_key:
        st.sidebar.success("🟢 IA active & prête", icon="✅")
    else:
        st.sidebar.warning("⚠️ Clé IA non configurée", icon="🔑")
        if not is_admin:
            with st.sidebar.expander("🔑 Saisir ma clé Gemini (Optionnel)", expanded=False):
                st.caption("👉 Obtenez votre clé gratuite en 1 minute sur [Google AI Studio](https://aistudio.google.com/).")
                new_st_key = st.text_input("Clé Gemini :", type="password", key="sidebar_student_gemini_key", placeholder="AIzaSy...")
                if st.button("Enregistrer ma clé", key="sidebar_save_gemini_btn"):
                    if new_st_key:
                        save_user_gemini_api_key(active_user_id, new_st_key)
                        st.success("Clé enregistrée !")
                        st.rerun()

    st.sidebar.divider()
    if st.sidebar.button("🚪 Déconnexion", use_container_width=True):
        logout_user()
        st.rerun()

    # -----------------------------------------------------------------------
    # VUE ADMIN 1 : TABLEAU DE BORD DE SUPERVISION GLOBALE
    # -----------------------------------------------------------------------
    if is_global_admin_view and menu == "📊 Supervision Globale":
        st.title("📊 Tableau de Bord de Supervision Administrateur")
        st.markdown("Supervision complète de l'activité, des cours téléversés et des scores de tous les élèves.")

        kpis = get_global_admin_kpis()

        k_col1, k_col2, k_col3, k_col4, k_col5 = st.columns(5)
        with k_col1:
            st.metric("Élèves Inscrits", kpis["total_students"])
        with k_col2:
            st.metric("Total Cours", kpis["total_courses"])
        with k_col3:
            st.metric("Quiz Générés", kpis["total_quizzes"])
        with k_col4:
            st.metric("Entraînements Passés", kpis["total_attempts"])
        with k_col5:
            st.metric("Taux de Réussite Moyen", f"{kpis['average_success_rate']}%")

        st.divider()

        st.markdown("### 🎒 Liste des Élèves & Assiduité")
        students_summary = kpis.get("students_summary", [])
        if students_summary:
            st.dataframe(
                [
                    {
                        "ID": s["user_id"],
                        "Nom": s["name"],
                        "Email": s["email"],
                        "Âge & Niveau": f"{s.get('age', 14)} ans ({s.get('cycle', {}).get('stage_label', 'Collège')})",
                        "Statut": "🔴 Suspendu" if s.get("is_blocked") == 1 else "🟢 Actif",
                        "Cours disponibles": s["course_count"],
                        "Quiz terminés": s["attempt_count"],
                        "Moyenne Quiz": f"{s['average_rate']}%",
                        "Date d'inscription": str(s.get("created_at", ""))[:16],
                    }
                    for s in students_summary
                ],
                use_container_width=True,
                hide_index=True,
            )
            st.caption("💡 *Sélectionnez un élève dans la barre latérale pour naviguer directement dans ses cours et ses devoirs.*")
        else:
            st.info("Aucun élève inscrit pour l'instant. Les nouveaux utilisateurs connectés via Google OAuth apparaîtront ici.")

        return

    # -----------------------------------------------------------------------
    # VUE ADMIN : GESTION DES UTILISATEURS (SUPPRESSION, BLOCAGE, RÔLES)
    # -----------------------------------------------------------------------
    elif is_global_admin_view and menu == "👥 Gestion des Utilisateurs":
        st.title("👥 Gestion des Utilisateurs & Élèves")
        st.markdown(
            "Supervisez et modifiez les comptes utilisateurs : ajustez les rôles (Élève ↔ Administrateur), "
            "suspendez temporairement des accès ou supprimez définitivement un compte et ses cours."
        )

        kpis = get_global_admin_kpis()
        all_users = list_users()

        # Cartes métriques
        m_col1, m_col2, m_col3, m_col4 = st.columns(4)
        with m_col1:
            st.metric("Total Utilisateurs", len(all_users))
        with m_col2:
            st.metric("Élèves Actifs", kpis.get("active_students", 0))
        with m_col3:
            st.metric("Comptes Suspendus", kpis.get("blocked_students", 0))
        with m_col4:
            st.metric("Administrateurs", kpis.get("total_admins", 0))

        st.divider()

        # Filtres & Recherche
        f_col1, f_col2, f_col3 = st.columns([3, 2, 2])
        with f_col1:
            search_query = st.text_input("🔍 Rechercher un utilisateur (nom ou email) :", key="user_search_input").strip().lower()
        with f_col2:
            role_filter = st.selectbox("Filtrer par rôle :", ["Tous", "Élèves", "Administrateurs"], key="user_role_filter")
        with f_col3:
            status_filter = st.selectbox("Filtrer par statut :", ["Tous", "Actifs uniquement", "Suspendus uniquement"], key="user_status_filter")

        filtered_users = all_users
        if search_query:
            filtered_users = [u for u in filtered_users if search_query in u["name"].lower() or search_query in u["email"].lower()]
        if role_filter == "Élèves":
            filtered_users = [u for u in filtered_users if u["role"] == "student"]
        elif role_filter == "Administrateurs":
            filtered_users = [u for u in filtered_users if u["role"] == "admin"]

        if status_filter == "Actifs uniquement":
            filtered_users = [u for u in filtered_users if u.get("is_blocked", 0) == 0]
        elif status_filter == "Suspendus uniquement":
            filtered_users = [u for u in filtered_users if u.get("is_blocked", 0) == 1]

        st.write(f"**{len(filtered_users)} utilisateur(s) affiché(s)**")

        if not filtered_users:
            st.info("Aucun utilisateur ne correspond à vos critères.")
            return

        for u in filtered_users:
            u_id = u["id"]
            is_self = (u_id == logged_in_user_id)
            is_u_blocked = (u.get("is_blocked", 0) == 1)
            is_u_admin = (u["role"] == "admin")

            status_badge = "🔴 Suspendu" if is_u_blocked else "🟢 Actif"
            u_cycle = get_pedagogical_cycle(u.get("age"))
            role_badge = "👑 Administrateur" if is_u_admin else u_cycle["badge_text"]
            self_tag = " *(Votre compte)*" if is_self else ""

            expander_title = f"{role_badge} — **{u['name']}** (`{u['email']}`) | {status_badge}{self_tag}"
            with st.expander(expander_title, expanded=False):
                col_u0, col_u1, col_u2, col_u3 = st.columns([2.5, 2, 2, 2.5])

                # 0. Nom et Âge
                with col_u0:
                    st.markdown("##### 👤 Profil & Âge")
                    edit_name_val = st.text_input("Nom :", value=u["name"], key=f"admin_edit_name_{u_id}")
                    current_age_val = int(u.get("age") or 14)
                    edit_age_val = st.number_input("Âge :", min_value=5, max_value=99, value=current_age_val, key=f"admin_edit_age_{u_id}")
                    if edit_name_val != u["name"] or edit_age_val != current_age_val:
                        if st.button("💾 Enregistrer profil", key=f"btn_save_prof_{u_id}", type="primary"):
                            ok_n, msg_n = update_user_name(u_id, edit_name_val)
                            ok_a, msg_a = update_user_age(u_id, int(edit_age_val))
                            if ok_n and ok_a:
                                st.success("Profil mis à jour !")
                                st.rerun()
                            else:
                                st.error(f"{msg_n} {msg_a}")

                # 1. Rôle
                with col_u1:
                    st.markdown("##### 🎭 Rôle")
                    role_options = ["student", "admin"]
                    role_labels = {"student": "🎒 Élève (student)", "admin": "👑 Administrateur (admin)"}
                    current_idx = 1 if is_u_admin else 0

                    new_role_val = st.selectbox(
                        "Modifier le rôle :",
                        options=role_options,
                        index=current_idx,
                        format_func=lambda x: role_labels[x],
                        key=f"sel_role_{u_id}",
                        disabled=is_self and kpis.get("total_admins", 0) <= 1,
                    )
                    if new_role_val != u["role"]:
                        if st.button("💾 Enregistrer le rôle", key=f"btn_save_role_{u_id}", type="primary"):
                            ok, msg = update_user_role(u_id, new_role_val, requesting_admin_id=logged_in_user_id)
                            if ok:
                                st.success(msg)
                                st.rerun()
                            else:
                                st.error(msg)

                # 2. Statut (Bloquer / Débloquer)
                with col_u2:
                    st.markdown("##### 🛡️ Statut d'accès")
                    if is_u_blocked:
                        st.caption("Compte actuellement **suspendu**.")
                        if st.button("✅ Réactiver le compte", key=f"btn_unblock_{u_id}", type="secondary"):
                            ok, msg = set_user_blocked_status(u_id, is_blocked=False, requesting_admin_id=logged_in_user_id)
                            if ok:
                                st.success(msg)
                                st.rerun()
                            else:
                                st.error(msg)
                    else:
                        st.caption("Compte actuellement **actif**.")
                        if is_self:
                            st.button("🚫 Suspendre l'accès", key=f"btn_block_{u_id}", disabled=True, help="Vous ne pouvez pas suspendre votre propre compte.")
                        else:
                            if st.button("🚫 Suspendre l'accès", key=f"btn_block_{u_id}", type="secondary"):
                                ok, msg = set_user_blocked_status(u_id, is_blocked=True, requesting_admin_id=logged_in_user_id)
                                if ok:
                                    st.warning(msg)
                                    st.rerun()
                                else:
                                    st.error(msg)

                # 3. Suppression définitive
                with col_u3:
                    st.markdown("##### 🗑️ Suppression Définitive")
                    if is_self:
                        st.caption("🔒 Protection : Vous ne pouvez pas supprimer votre propre compte connecté.")
                    else:
                        with st.popover("⚠️ Supprimer ce compte..."):
                            st.warning(f"La suppression du compte de **{u['name']}** est **DÉFINITIVE ET IRRÉVERSIBLE**.")
                            st.write("- Tous ses cours, fiches de révision et quiz seront effacés.")
                            st.write("- L'ensemble de ses fichiers PDF sur le disque seront supprimés.")
                            confirm_check = st.checkbox("Je confirme la suppression définitive", key=f"confirm_del_{u_id}")
                            if st.button("💥 Confirmer la suppression définitive", key=f"btn_del_{u_id}", type="primary", disabled=not confirm_check):
                                ok, msg = delete_user_account(u_id, requesting_admin_id=logged_in_user_id)
                                if ok:
                                    st.success(msg)
                                    st.rerun()
                                else:
                                    st.error(msg)

        return

    # -----------------------------------------------------------------------
    # VUE ADMIN 2 : CONFIGURATION SYSTÈME & SAUVEGARDE GLOBALE
    # -----------------------------------------------------------------------
    elif is_global_admin_view and menu == "⚙️ Configuration Système & Sauvegardes":
        st.title("⚙️ Configuration Système & Sauvegarde Globale")
        st.markdown("Gestion des accès API de secours, sauvegarde intégrale de la plateforme et maintenance.")

        st.markdown("### 🔑 Clé API Google Gemini (Administrateur)")
        current_admin_key = get_user_gemini_api_key(logged_in_user_id) or get_gemini_api_key() or ""
        col_ak1, col_ak2 = st.columns([3, 1])
        with col_ak1:
            new_admin_key = st.text_input(
                "Clé API Google Gemini personnelle :",
                value=current_admin_key,
                type="password",
                placeholder="AIzaSy...",
                help="Clé gratuite issue de https://aistudio.google.com/",
            )
        with col_ak2:
            st.write("")
            st.write("")
            if st.button("💾 Enregistrer la clé", type="primary", use_container_width=True, key="save_admin_gemini_btn"):
                if new_admin_key:
                    save_user_gemini_api_key(logged_in_user_id, new_admin_key)
                    st.success("Clé API enregistrée !")
                    st.rerun()

        if st.button("🔍 Tester la connectivité Gemini (Admin)", key="test_admin_gemini_btn"):
            with st.spinner("Test en cours..."):
                res = test_user_gemini_connection(logged_in_user_id)
                if res["success"]:
                    st.success(f"✅ {res['message']}")
                else:
                    st.error(f"❌ {res['error']}")

        render_gemini_key_instructions(expanded=not bool(current_admin_key))

        st.divider()

        st.markdown("### 📦 Sauvegarde Complète du Système")
        sys_stats = get_backup_summary()
        st.info(
            f"📊 **Statistiques globales :** {sys_stats['users']} utilisateurs | "
            f"{sys_stats['courses']} cours | {sys_stats['messages']} discussions Sanad | {sys_stats['attempts']} entraînements."
        )

        col_gb1, col_gb2 = st.columns(2)
        with col_gb1:
            st.markdown("#### 📥 Téléchargement global")
            global_zip = export_global_backup()
            timestamp_str = datetime.now().strftime("%Y%m%d_%H%M")
            st.download_button(
                label="📦 Sauvegarde complète du système (.zip)",
                data=global_zip,
                file_name=f"sauvegarde_globale_ecole_adnane_{timestamp_str}.zip",
                mime="application/zip",
                type="primary",
                use_container_width=True,
            )

        with col_gb2:
            st.markdown("#### 📤 Restauration globale")
            uploaded_global = st.file_uploader("Fichier de sauvegarde globale (.zip) :", type=["zip"], key="global_restore_upload")
            if uploaded_global:
                st.warning("⚠️ **Attention :** La restauration globale réécrira l'ensemble de la base et des dossiers d'utilisateurs.")
                confirm = st.checkbox("Je confirme vouloir restaurer l'intégralité du système", key="confirm_global_restore")
                if confirm and st.button("🚀 Lancer la restauration globale", type="primary", use_container_width=True):
                    with st.spinner("Restauration globale du système en cours..."):
                        res = restore_global_backup(uploaded_global.read())
                        if res["success"]:
                            st.success(f"✅ {res['message']}")
                            st.balloons()
                            st.rerun()
                        else:
                            st.error(f"❌ {res['error']}")

        st.divider()

        st.markdown("### 🎯 Sauvegarde & Restauration Ciblée d'un Élève")
        target_student_id = st.selectbox(
            "Sélectionnez l'élève cible :",
            options=[s["id"] for s in all_students] if all_students else [],
            format_func=lambda x: next((f"{s['name']} ({s['email']})" for s in all_students if s["id"] == x), str(x)),
            key="target_student_backup_select",
        )

        if target_student_id:
            target_student = get_user_by_id(target_student_id)
            st_stats = get_student_backup_summary(target_student_id)
            st.caption(f"Données de {target_student['name']} : {st_stats['courses']} cours, {st_stats['messages']} messages IA.")

            col_st1, col_st2 = st.columns(2)
            with col_st1:
                student_zip = export_student_backup(target_student_id)
                st.download_button(
                    label=f"💾 Exporter l'espace de {target_student['name']} (.zip)",
                    data=student_zip,
                    file_name=f"revisions_{target_student['name']}_{timestamp_str}.zip",
                    mime="application/zip",
                    use_container_width=True,
                )
            with col_st2:
                st_upload = st.file_uploader(f"Restaurer dans l'espace de {target_student['name']} :", type=["zip", "db", "sqlite"], key="target_student_restore_upload")
                if st_upload and st.button(f"🚀 Restaurer pour {target_student['name']}", type="primary"):
                    with st.spinner("Restauration ciblée en cours..."):
                        res_cib = restore_student_backup(st_upload.read(), target_student_id)
                        if res_cib["success"]:
                            st.success(f"✅ {res_cib['message']}")
                            st.rerun()
                        else:
                            st.error(f"❌ {res_cib['error']}")

        return

    # -----------------------------------------------------------------------
    # VUE ÉLÈVE : MES COURS (RÉVISIONS PAR ÉLÈVE)
    # -----------------------------------------------------------------------
    if menu == "📚 Mes Cours (Révisions)":
        if is_admin and active_student_info:
            st.info(f"👀 **Espace de supervision :** Vous consultez les cours de l'élève **{active_student_info['name']}** (`{active_student_info['email']}`).")

        st.title("📚 Espace de Révision 3AC")

        col_f1, col_f2, col_f3 = st.columns([2, 2, 2])
        with col_f1:
            all_subjects = ["Toutes"] + SUBJECTS_FR + SUBJECTS_EN + SUBJECTS_AR
            selected_subject = st.selectbox("Filtrer par matière :", all_subjects)
        with col_f2:
            selected_lang = st.selectbox("Langue :", ["Toutes", "Français", "English", "العربية"])
            if selected_lang == "Français":
                lang_filter = "fr"
            elif selected_lang == "English":
                lang_filter = "en"
            elif selected_lang == "العربية":
                lang_filter = "ar"
            else:
                lang_filter = None
        with col_f3:
            courses_list = list_courses(
                user_id=active_user_id,
                subject=selected_subject if selected_subject != "Toutes" else None,
                language=lang_filter,
            )
            st.write(f"**{len(courses_list)} cours disponible(s)**")

        if not courses_list:
            if is_admin:
                st.info(
                    "👋 Aucun cours enregistré pour cet espace. Utilisez le menu **➕ Gestion & Ajout des Cours** pour déposer vos documents PDF."
                )
            else:
                st.info(
                    "👋 **Bienvenue dans votre espace de révision !**\n\n"
                    "Vous n'avez pas encore de cours enregistré. Rendez-vous dans le menu **➕ Ajouter un Cours** "
                    "pour téléverser vos premiers supports PDF ou dans **⚙️ Paramètres & Sauvegardes** pour restaurer une sauvegarde existante."
                )
            return

        course_options = {c["id"]: f"{'🇲🇦 [AR]' if c['language'] == 'ar' else ('🇬🇧 [EN]' if c['language'] == 'en' else '🇫🇷 [FR]')} {c['subject']} - {c['title']}" for c in courses_list}
        selected_course_id = st.selectbox(
            "Sélectionnez le cours à réviser :",
            options=list(course_options.keys()),
            format_func=lambda x: course_options[x],
        )

        current_course = get_course_by_id(selected_course_id, user_id=active_user_id)
        if not current_course:
            st.error("Cours introuvable ou accès non autorisé.")
            return

        is_ar = current_course["language"] == "ar"
        is_en = current_course["language"] == "en"
        badge_cls = get_subject_badge_class(current_course["subject"])

        active_user_dict = active_student_info if (is_admin and active_student_info) else current_user
        active_cycle = get_pedagogical_cycle(active_user_dict.get("age"))

        if is_ar:
            level_label = f"المستوى : {active_cycle['cycle_name']} ({active_cycle['age']} سنة)"
            lang_badge_text = "العربية (AR)"
        elif is_en:
            level_label = f"Level: {active_cycle['cycle_name']} ({active_cycle['age']} yo)"
            lang_badge_text = "English (EN)"
        else:
            level_label = f"Niveau : {active_cycle['cycle_name']} ({active_cycle['age']} ans)"
            lang_badge_text = "Français (FR)"

        header_html = f"""
        <div class="course-header-box {'rtl-box' if is_ar else ''}">
            <div style="display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:10px;">
                <div>
                    <span class="badge-subject {badge_cls}">{current_course['subject']}</span>
                    <span class="badge-lang">{lang_badge_text}</span>
                    <span class="course-header-subtitle" style="margin-left:8px; margin-right:8px;">{level_label}</span>
                </div>
                <div class="course-header-subtitle">
                    📄 {current_course['file_name']}
                </div>
            </div>
            <h2>{current_course['title']}</h2>
        </div>
        """
        st.markdown(header_html, unsafe_allow_html=True)

        if current_course.get("key_concepts"):
            if is_ar:
                chips = " ".join([f"<span class='concept-tag'>{c}</span>" for c in current_course["key_concepts"]])
                st.markdown(f"<div dir='rtl' style='text-align:right; margin-top:8px; margin-bottom:12px;'><strong>المفاهيم الأساسية :</strong> {chips}</div>", unsafe_allow_html=True)
            elif is_en:
                chips = " ".join([f"<span class='concept-tag'>#{c}</span>" for c in current_course["key_concepts"]])
                st.markdown(f"**Key Concepts:** {chips}", unsafe_allow_html=True)
            else:
                chips = " ".join([f"<span class='concept-tag'>#{c}</span>" for c in current_course["key_concepts"]])
                st.markdown(f"**Notions clés :** {chips}", unsafe_allow_html=True)

        if is_ar:
            edit_header_label = "✏️ تصحيح مادة الدرس أو العنوان أو اللغة"
        elif is_en:
            edit_header_label = "✏️ Edit course subject, title or language"
        else:
            edit_header_label = "✏️ Modifier la matière, le titre ou la langue de ce cours"

        with st.expander(edit_header_label):
            col_ed1, col_ed2, col_ed3 = st.columns([3, 2, 2])
            with col_ed1:
                title_label = "عنوان الدرس" if is_ar else ("Lesson Title" if is_en else "Titre du cours")
                new_title = st.text_input(
                    title_label,
                    value=current_course["title"],
                    key=f"edit_title_{current_course['id']}",
                )

            with col_ed2:
                all_subjects_display = [
                    "🇲🇦 التربية الإسلامية",
                    "🇲🇦 الاجتماعيات",
                    "🇲🇦 اللغة العربية",
                    "🇫🇷 Mathématiques",
                    "🇫🇷 Physique-Chimie",
                    "🇫🇷 SVT",
                    "🇫🇷 Français",
                    "🇬🇧 Anglais",
                ]
                if is_ar:
                    current_prefix = "🇲🇦 "
                elif is_en or current_course["subject"] == "Anglais":
                    current_prefix = "🇬🇧 "
                else:
                    current_prefix = "🇫🇷 "
                current_match = current_prefix + current_course["subject"]
                default_idx = (
                    all_subjects_display.index(current_match)
                    if current_match in all_subjects_display
                    else 0
                )
                chosen_subject_labeled = st.selectbox(
                    "المادة" if is_ar else ("Subject" if is_en else "Matière"),
                    all_subjects_display,
                    index=default_idx,
                    key=f"edit_subj_{current_course['id']}",
                )
                cleaned_subj = chosen_subject_labeled.replace("🇲🇦 ", "").replace("🇫🇷 ", "").replace("🇬🇧 ", "")
                is_ar_choice = "🇲🇦" in chosen_subject_labeled or cleaned_subj in SUBJECTS_AR
                is_en_choice = "🇬🇧" in chosen_subject_labeled or cleaned_subj in SUBJECTS_EN

            with col_ed3:
                lang_options = ["🇲🇦 العربية (ar)", "🇫🇷 Français (fr)", "🇬🇧 English (en)"]
                if is_ar_choice:
                    lang_default_idx = 0
                elif is_en_choice:
                    lang_default_idx = 2
                else:
                    lang_default_idx = 1
                chosen_lang_label = st.selectbox(
                    "اللغة" if is_ar else ("Language" if is_en else "Langue du cours"),
                    lang_options,
                    index=lang_default_idx,
                    key=f"edit_lang_{current_course['id']}",
                )
                if "العربية" in chosen_lang_label:
                    final_lang = "ar"
                elif "English" in chosen_lang_label:
                    final_lang = "en"
                else:
                    final_lang = "fr"

            btn_save_col1, _ = st.columns([2, 5])
            with btn_save_col1:
                btn_save_txt = "💾 حفظ التعديل" if is_ar else ("💾 Save Changes" if is_en else "💾 Enregistrer les modifications")
                if st.button(btn_save_txt, type="primary", use_container_width=True, key=f"btn_save_m_{current_course['id']}"):
                    update_course_metadata(current_course["id"], new_title, cleaned_subj, final_lang, user_id=active_user_id)
                    st.success("Modifications enregistrées !" if not is_en else "Changes saved successfully!")
                    st.rerun()

        st.write("")

        if is_ar:
            tab_doc, tab_fiche, tab_quiz, tab_tuteur = st.tabs([
                "📄 وثيقة الدرس",
                "⚡ بطاقة المراجعة",
                "🎯 تدريب الامتحان",
                "🤖 الأستاذ سند",
            ])
        elif is_en:
            tab_doc, tab_fiche, tab_quiz, tab_tuteur = st.tabs([
                "📄 Course Document",
                "⚡ Revision Sheet",
                "🎯 Exam Quiz",
                "🤖 AI Tutor (Sanad)",
            ])
        else:
            tab_doc, tab_fiche, tab_quiz, tab_tuteur = st.tabs([
                "📄 Le Document",
                "⚡ Fiche Express",
                "🎯 Entraînement Examen",
                "🤖 Tuteur Virtuel (Sanad)",
            ])

        with tab_doc:
            file_path = current_course.get("file_path")
            if file_path and os.path.exists(file_path):
                with open(file_path, "rb") as f:
                    pdf_data = f.read()

                dl_label = "📥 تحميل ملف PDF الأصلي" if is_ar else ("📥 Download Original PDF" if is_en else "📥 Télécharger le PDF original")
                st.download_button(
                    label=dl_label,
                    data=pdf_data,
                    file_name=current_course.get("file_name", "cours.pdf"),
                    mime="application/pdf",
                )
            else:
                st.warning("Fichier PDF non trouvé sur le disque." if not is_en else "PDF file not found on disk.")

            st.write("---")
            exp_text_title = "📝 عرض النص المستخرج من الوثيقة" if is_ar else ("📝 View Extracted Text" if is_en else "📝 Voir le texte extrait du document")
            with st.expander(exp_text_title):
                raw = current_course.get("raw_text") or ("Aucun texte." if not is_en else "No text found.")
                if is_ar:
                    st.markdown(f"<div class='rtl-box'>{raw[:4000]}...</div>", unsafe_allow_html=True)
                else:
                    st.text(raw[:4000] + ("..." if len(raw) > 4000 else ""))

        with tab_fiche:
            fiche_md = current_course.get("summary_markdown")
            if not fiche_md:
                btn_gen_fiche = "⚡ توليد بطاقة المراجعة المركزة بالذكاء الاصطناعي" if is_ar else ("⚡ Generate AI Revision Sheet" if is_en else "⚡ Générer la Fiche Express avec l'IA")
                if st.button(btn_gen_fiche, type="primary"):
                    if not user_api_key:
                        st.error("⚠️ Clé API Gemini requise. Obtenez votre clé 100% gratuite sur [Google AI Studio](https://aistudio.google.com/) et activez-la dans **⚙️ Paramètres** ou la barre latérale." if not is_en else "⚠️ Gemini API key required. Get your free key on [Google AI Studio](https://aistudio.google.com/) and configure it in **⚙️ Settings** or the sidebar.")
                    else:
                        with st.spinner("Génération de la fiche express..." if not is_en else "Generating revision sheet..."):
                            generated_summary = generate_revision_sheet(
                                raw_text=current_course.get("raw_text") or "",
                                subject=current_course["subject"],
                                language=current_course["language"],
                                user_id=active_user_id,
                            )
                            update_course_summary(current_course["id"], generated_summary, user_id=active_user_id)
                            st.rerun()
            else:
                if is_ar:
                    st.markdown(f"<div class='rtl-box'>{fiche_md}</div>", unsafe_allow_html=True)
                else:
                    st.markdown(fiche_md)

                st.write("---")
                regen_label = "🔄 إعادة توليد بطاقة المراجعة" if is_ar else ("🔄 Regenerate Revision Sheet" if is_en else "🔄 Régénérer la Fiche Express")
                if st.button(regen_label):
                    if not user_api_key:
                        st.error("⚠️ Clé API Gemini requise. Obtenez votre clé 100% gratuite sur [Google AI Studio](https://aistudio.google.com/) et activez-la dans **⚙️ Paramètres** ou la barre latérale." if not is_en else "⚠️ Gemini API key required. Get your free key on [Google AI Studio](https://aistudio.google.com/) and configure it in **⚙️ Settings** or the sidebar.")
                    else:
                        with st.spinner("Régénération..." if not is_en else "Regenerating..."):
                            generated_summary = generate_revision_sheet(
                                raw_text=current_course.get("raw_text") or "",
                                subject=current_course["subject"],
                                language=current_course["language"],
                                user_id=active_user_id,
                            )
                            update_course_summary(current_course["id"], generated_summary, user_id=active_user_id)
                            st.rerun()

        with tab_quiz:
            latest_quiz = get_latest_quiz(current_course["id"], user_id=active_user_id)

            btn_new_quiz = "🎯 توليد اختبار تدريبي جديد (5 أسئلة)" if is_ar else ("🎯 Generate Exam Practice Quiz (5 questions)" if is_en else "🎯 Générer un nouveau quiz d'examen (5 questions)")
            if st.button(btn_new_quiz, type="secondary"):
                if not user_api_key:
                    st.error("⚠️ Clé API Gemini requise. Obtenez votre clé 100% gratuite sur [Google AI Studio](https://aistudio.google.com/) et activez-la dans **⚙️ Paramètres** ou la barre latérale." if not is_en else "⚠️ Gemini API key required. Get your free key on [Google AI Studio](https://aistudio.google.com/) and configure it in **⚙️ Settings** or the sidebar.")
                else:
                    with st.spinner("Génération des questions d'examen..." if not is_en else "Generating exam quiz questions..."):
                        quiz_questions = generate_quiz(
                            raw_text=current_course.get("raw_text") or "",
                            subject=current_course["subject"],
                            language=current_course["language"],
                            num_questions=5,
                            user_id=active_user_id,
                        )
                        save_quiz(current_course["id"], quiz_questions, user_id=active_user_id)
                        st.rerun()

            if latest_quiz and latest_quiz.get("questions"):
                questions = latest_quiz["questions"]
                quiz_id = latest_quiz["id"]
                submission_key = f"quiz_submitted_{quiz_id}"
                is_submitted = st.session_state.get(submission_key, False)

                answers_chosen = {}
                for idx, q in enumerate(questions):
                    st.markdown(f"**Question {idx + 1} :** {q['question']}")
                    options = q.get("options", [])
                    ans_idx = q.get("answer_index", 0)
                    explanation = q.get("explanation", "")
                    trap_alert = q.get("trap_alert", "")

                    selected_opt = st.radio(
                        f"Choix pour Q{idx+1}:",
                        options,
                        key=f"q_{quiz_id}_{idx}",
                        disabled=is_submitted,
                        label_visibility="collapsed",
                    )
                    if selected_opt in options:
                        answers_chosen[idx] = options.index(selected_opt)

                    if is_submitted:
                        user_ans = answers_chosen.get(idx)
                        if user_ans == ans_idx:
                            st.success(f"✅ Excellente réponse ! ({options[ans_idx]})" if not is_en else f"✅ Excellent answer! ({options[ans_idx]})")
                        else:
                            st.error(f"❌ La bonne réponse était : **{options[ans_idx]}**" if not is_en else f"❌ The correct answer was: **{options[ans_idx]}**")

                        if explanation:
                            expl_title = "💡 شرح :" if is_ar else ("💡 Explanation:" if is_en else "💡 Explication :")
                            st.markdown(f"<div class='explanation-card'><strong>{expl_title}</strong> {explanation}</div>", unsafe_allow_html=True)
                        if trap_alert:
                            trap_title = "⚠️ فخ شائع :" if is_ar else ("⚠️ Common Exam Trap:" if is_en else "⚠️ Piège classique :")
                            st.markdown(f"<div class='trap-card'><strong>{trap_title}</strong> {trap_alert}</div>", unsafe_allow_html=True)

                if not is_submitted:
                    submit_label = "🏆 Valider mes réponses" if not is_en else "🏆 Submit My Answers"
                    if st.button(submit_label, type="primary"):
                        score = sum(1 for idx, q in enumerate(questions) if answers_chosen.get(idx) == q.get("answer_index", 0))
                        save_quiz_attempt(
                            course_id=current_course["id"],
                            quiz_id=quiz_id,
                            score=score,
                            total_questions=len(questions),
                            answers=answers_chosen,
                            user_id=active_user_id,
                        )
                        st.session_state[submission_key] = True
                        if score >= len(questions) * 0.8:
                            st.balloons()
                        st.rerun()
                else:
                    score = sum(1 for idx, q in enumerate(questions) if answers_chosen.get(idx) == q.get("answer_index", 0))
                    score_txt = f"### Score obtenu : **{score} / {len(questions)}**" if not is_en else f"### Score: **{score} / {len(questions)}**"
                    st.markdown(score_txt)
                    retry_label = "🔁 Recommencer ce quiz" if not is_en else "🔁 Retake Quiz"
                    if st.button(retry_label):
                        st.session_state[submission_key] = False
                        st.rerun()
            else:
                st.info("Aucun quiz généré pour ce cours pour le moment." if not is_en else "No quiz generated for this course yet.")

        with tab_tuteur:
            stored_auto_speak = get_user_setting(active_user_id, "auto_speak_sanad", "false") == "true"
            stored_speed_str = get_user_setting(active_user_id, "voice_speed_sanad", "1.0")
            try:
                stored_speed = float(stored_speed_str)
            except Exception:
                stored_speed = 1.0

            col_hdr_title, col_hdr_toggle = st.columns([0.65, 0.35])
            with col_hdr_title:
                if is_ar:
                    st.markdown("<div class='rtl-section-title'>🤖 الأستاذ المساعد : سَنَد</div>", unsafe_allow_html=True)
                elif is_en:
                    st.markdown("### 🤖 Socratic AI Tutor: Sanad")
                else:
                    st.markdown("### 🤖 Tuteur Virtuel : Sanad")
            with col_hdr_toggle:
                auto_speak = st.toggle(
                    "🔊 Lecture vocale auto" if not is_en else ("🔊 Auto-speak" if is_en else "🔊 قراءة تلقائية"),
                    value=stored_auto_speak,
                    key=f"auto_speak_toggle_{current_course['id']}",
                    help="Sanad lit automatiquement ses réponses à voix haute dès qu'il vous répond (100% gratuit, 0 quota Gemini).",
                )
                if auto_speak != stored_auto_speak:
                    set_user_setting(active_user_id, "auto_speak_sanad", "true" if auto_speak else "false")

            with st.expander(
                "⚙️ Options vocales & vitesse (Web Speech API — 0 quota Gemini)"
                if not is_en
                else ("⚙️ Voice speed & options (0 Gemini quota)" if is_en else "⚙️ خيارات سرعة الصوت (مجاني)"),
                expanded=False,
            ):
                col_v1, col_v2 = st.columns([1, 1])
                with col_v1:
                    voice_speed = st.select_slider(
                        "Vitesse de lecture :" if not is_en else ("Voice Speed:" if is_en else "سرعة النطق :"),
                        options=[0.8, 0.9, 1.0, 1.1, 1.2],
                        value=stored_speed if stored_speed in [0.8, 0.9, 1.0, 1.1, 1.2] else 1.0,
                        format_func=lambda x: f"{x}x" + (" (Douce)" if x < 1.0 else (" (Normale)" if x == 1.0 else " (Rapide)")),
                        key=f"voice_speed_slider_{current_course['id']}",
                    )
                    if voice_speed != stored_speed:
                        set_user_setting(active_user_id, "voice_speed_sanad", str(voice_speed))
                with col_v2:
                    st.caption(
                        "💡 **Zéro impact sur votre forfait Gemini :** La synthèse vocale et le micro fonctionnent directement dans votre navigateur grâce à la Web Speech API HTML5."
                        if not is_en
                        else (
                            "💡 **Zero impact on your Gemini quota:** Speech synthesis and voice typing run natively in your browser using the HTML5 Web Speech API."
                            if is_en
                            else "💡 **دون استهلاك رصيد Gemini :** قراءة النصوص وتسجيل الصوت يعملان محلياً في متصفحك عبر تقنية Web Speech API."
                        )
                    )

            history = get_chat_history(current_course["id"], user_id=active_user_id)
            trigger_auto_key = f"auto_speak_trigger_{current_course['id']}"
            has_auto_trigger = bool(st.session_state.get(trigger_auto_key))

            for i, msg in enumerate(history):
                role = msg["role"]
                content = msg["content"]
                with st.chat_message("user" if role == "user" else "assistant", avatar="🧑‍🎓" if role == "user" else "🤖"):
                    if role == "assistant":
                        col_bot_lbl, col_bot_voice = st.columns([0.90, 0.10])
                        with col_bot_lbl:
                            if is_ar:
                                st.markdown("<div style='font-size:12px; font-weight:600; color:#4b5563; padding-top:4px;'>الأستاذ سَنَد</div>", unsafe_allow_html=True)
                            else:
                                st.markdown("<div style='font-size:12px; font-weight:600; color:#4b5563; padding-top:4px;'>Sanad</div>", unsafe_allow_html=True)
                        with col_bot_voice:
                            should_auto_play = bool(
                                auto_speak
                                and (i == len(history) - 1)
                                and has_auto_trigger
                            )
                            tts_html = generate_tts_player_html(
                                content,
                                language=current_course.get("language", "fr"),
                                player_id=f"voice_msg_{current_course['id']}_{i}",
                                rate=voice_speed,
                                compact=True,
                                auto_play=should_auto_play,
                            )
                            if tts_html:
                                st.components.v1.html(tts_html, height=32)

                        if is_ar:
                            st.markdown(f"<div class='rtl-box'>{content}</div>", unsafe_allow_html=True)
                        else:
                            st.markdown(content)
                    else:
                        if is_ar:
                            st.markdown(f"<div class='rtl-box'>{content}</div>", unsafe_allow_html=True)
                        else:
                            st.markdown(content)

            # Réinitialiser le déclencheur de lecture automatique après affichage
            if has_auto_trigger:
                st.session_state[trigger_auto_key] = False

            # Injection discrète de l'icône micro directement sur le champ st.chat_input à côté du bouton envoyer
            mic_injector_html = generate_chat_mic_injector_html(
                language=current_course.get("language", "fr"),
                widget_id=f"mic_chat_{current_course['id']}",
            )
            if mic_injector_html:
                st.components.v1.html(mic_injector_html, height=0)

            chat_placeholder = "اطرح سؤالك على الأستاذ المساعد سند..." if is_ar else ("Ask Sanad a question about this lesson..." if is_en else "Pose ta question à Sanad...")
            user_input = st.chat_input(chat_placeholder)
            if user_input:
                if not user_api_key:
                    st.error("⚠️ Clé API Gemini requise pour échanger avec Sanad. Obtenez votre clé 100% gratuite sur [Google AI Studio](https://aistudio.google.com/) et activez-la dans **⚙️ Paramètres** ou la barre latérale." if not is_en else "⚠️ Gemini API key required to chat with Sanad. Get your free key on [Google AI Studio](https://aistudio.google.com/) and configure it in **⚙️ Settings** or the sidebar.")
                else:
                    add_chat_message(current_course["id"], "user", user_input, user_id=active_user_id)
                    with st.chat_message("user", avatar="🧑‍🎓"):
                        st.markdown(user_input)

                    with st.chat_message("assistant", avatar="🤖"):
                        spinner_txt = "Sanad prépare ses conseils..." if not is_en else "Sanad is thinking..."
                        with st.spinner(spinner_txt):
                            updated_history = get_chat_history(current_course["id"], user_id=active_user_id)
                            reply = socratic_tutor_response(
                                messages=updated_history,
                                course_context=current_course.get("raw_text") or "",
                                subject=current_course["subject"],
                                language=current_course["language"],
                                user_id=active_user_id,
                            )
                            add_chat_message(current_course["id"], "assistant", reply, user_id=active_user_id)
                            if is_ar:
                                st.markdown(f"<div class='rtl-box'>{reply}</div>", unsafe_allow_html=True)
                            else:
                                st.markdown(reply)
                            if auto_speak:
                                st.session_state[trigger_auto_key] = True
                    st.rerun()

            if history:
                clear_label = "🗑️ مسح المحادثة مع سند" if is_ar else ("🗑️ Clear conversation with Sanad" if is_en else "🗑️ Effacer la conversation avec Sanad")
                if st.button(clear_label, key="clear_chat_active"):
                    clear_chat_history(current_course["id"], user_id=active_user_id)
                    st.rerun()

    # -----------------------------------------------------------------------
    # GESTION & AJOUT DES COURS (ADMINISTRATEUR)
    # -----------------------------------------------------------------------
    elif menu in ("➕ Ajouter un Cours", "➕ Gestion & Ajout des Cours"):
        if is_admin and active_student_info:
            st.info(f"👀 **Espace de supervision :** Vous téléversez des supports pour l'élève **{active_student_info['name']}**.")
            target_ids = [active_user_id]
        elif is_global_admin_view:
            st.title("➕ Gestion & Ajout des Cours (3AC)")
            all_s = list_users(role="student")
            target_choice = st.radio(
                "Destinataire(s) du cours :",
                ["👥 Tous les élèves inscrits", "🎒 Élève spécifique"],
                horizontal=True,
                key="admin_add_course_target_choice",
            )
            if target_choice == "👥 Tous les élèves inscrits":
                target_ids = [s["id"] for s in all_s]
                if not target_ids:
                    st.info("ℹ️ Aucun élève n'est encore inscrit. Les cours seront enregistrés comme cours communs partagés de l'établissement.")
                    target_ids = [None]
                else:
                    st.caption(f"Le cours sera injecté dans l'espace de {len(target_ids)} élève(s).")
            else:
                if not all_s:
                    st.warning("Aucun élève inscrit.")
                    target_ids = [logged_in_user_id]
                else:
                    target_sel = st.selectbox(
                        "Choisir l'élève destinataire :",
                        options=[s["id"] for s in all_s],
                        format_func=lambda x: next((f"{s['name']} ({s['email']})" for s in all_s if s["id"] == x), str(x)),
                        key="admin_add_course_student_select",
                    )
                    target_ids = [target_sel]
        else:
            st.title("➕ Ajouter un Cours (Mes Révisions 3AC)")
            st.markdown(
                "Téléversez vos supports de cours au format PDF pour enrichir vos révisions, "
                "générer automatiquement des résumés clés, fiches mémo et quiz personnalisés."
            )
            target_ids = [active_user_id]

        mode = st.radio(
            "Mode d'importation :",
            ["📁 Import Manuel (PDF)", "🏫 Synchronisation Google Classroom"],
            horizontal=True,
            key="add_course_mode_radio",
        )

        if mode == "📁 Import Manuel (PDF)":
            uploaded_files = st.file_uploader(
                "Sélectionnez un ou plusieurs fichiers PDF :",
                type=["pdf"],
                accept_multiple_files=True,
                help="Les fichiers seront stockés dans le dossier personnel isolé de chaque destinataire.",
            )

            if uploaded_files:
                st.info(f"📄 {len(uploaded_files)} fichier(s) sélectionné(s).")
                if st.button("🚀 Ingestion & Analyse Automatique", type="primary"):
                    progress_bar = st.progress(0)
                    total_ops = len(uploaded_files) * len(target_ids)
                    done = 0
                    success_count = 0
                    dup_count = 0

                    for f in uploaded_files:
                        file_bytes = f.read()
                        for tid in target_ids:
                            res = ingest_pdf_bytes(file_bytes, f.name, user_id=tid)
                            if res["status"] == "success":
                                success_count += 1
                            else:
                                dup_count += 1
                            done += 1
                            progress_bar.progress(done / total_ops)

                    st.success(f"Bilan : {success_count} cours ajouté(s), {dup_count} doublon(s).")
                    st.rerun()

        else:
            st.markdown("### 🏫 Synchronisation Google Classroom")
            st.write("Récupérez les cours et devoirs depuis Google Classroom.")

            primary_target = target_ids[0]
            has_creds = is_classroom_configured(primary_target)
            if not has_creds:
                st.warning("⚠️ Vos identifiants Google Classroom (`credentials.json`) ne sont pas encore téléversés.")
                up_cred = st.file_uploader("Téléverser votre `credentials.json` :", type=["json"], key="up_cred_individual")
                if up_cred:
                    cred_bytes = up_cred.read()
                    for tid in target_ids:
                        save_user_credentials(tid, cred_bytes)
                    st.success("Identifiants Classroom enregistrés !")
                    st.rerun()
                render_classroom_credentials_instructions(expanded=True)
            else:
                st.success("🟢 Identifiants Classroom configurés.")
                if st.button("🔄 Synchroniser les devoirs Classroom", type="primary"):
                    with st.spinner("Synchronisation Classroom en cours..."):
                        for tid in target_ids:
                            sync_res = sync_google_classroom(user_id=tid)
                        if sync_res["success"]:
                            st.success(sync_res["message"])
                        else:
                            st.error(sync_res["error"])
                render_classroom_credentials_instructions(expanded=False)

    # -----------------------------------------------------------------------
    # VUE ÉLÈVE : MES PROGRÈS
    # -----------------------------------------------------------------------
    elif menu == "📊 Mes Progrès":
        if is_admin and active_student_info:
            st.info(f"👀 **Espace de supervision :** Statistiques de l'élève **{active_student_info['name']}**.")

        st.title("📊 Progression & Révisions 3AC")

        stats = get_quiz_stats(user_id=active_user_id)

        m1, m2, m3, m4 = st.columns(4)
        with m1:
            st.metric("Total Quiz passés", stats["total_attempts"])
        with m2:
            st.metric("Questions répondues", stats["total_questions"])
        with m3:
            st.metric("Bonnes réponses", stats["total_score"])
        with m4:
            st.metric("Moyenne générale", f"{stats['average_success_rate']}%")

        st.divider()

        col_sub, col_hist = st.columns([1, 1])
        with col_sub:
            st.markdown("### 🎯 Maîtrise par matière")
            by_subj = stats.get("by_subject", [])
            if by_subj:
                for s in by_subj:
                    rate = s["success_rate"]
                    badge_cls = get_subject_badge_class(s["subject"])
                    st.markdown(f"<div><span class='badge-subject {badge_cls}'>{s['subject']}</span> <strong>{rate}%</strong> ({s['attempts']} quiz)</div>", unsafe_allow_html=True)
                    st.progress(rate / 100.0)
                    st.write("")
            else:
                st.info("Aucun entraînement pour le moment.")

        with col_hist:
            st.markdown("### 🕒 Derniers entraînements")
            recent = stats.get("recent_attempts", [])
            if recent:
                for a in recent:
                    date_str = str(a.get("completed_at", ""))[:16]
                    st.markdown(f"- **{a['course_title']}** ({a['subject']}) : `{a['score']}/{a['total_questions']}` — <small>{date_str}</small>", unsafe_allow_html=True)
            else:
                st.caption("L'historique des quiz récents apparaîtra ici.")

    # -----------------------------------------------------------------------
    # VUE ÉLÈVE : PARAMÈTRES INDIVIDUELS & SAUVEGARDE ÉLÈVE
    # -----------------------------------------------------------------------
    elif menu in ("⚙️ Paramètres & Sauvegardes", "⚙️ Sauvegardes & Paramètres de l'élève"):
        if is_admin and active_student_info:
            st.info(f"👀 **Espace de supervision :** Paramètres et sauvegarde de **{active_student_info['name']}**.")

        st.title("⚙️ Paramètres & Sauvegardes Personnelles")

        # -------------------------------------------------------------------
        # 1. PROFIL DE L'APPRENANT : NOM & ÂGE (ADAPTATION UNIVERSELLE)
        # -------------------------------------------------------------------
        st.markdown("### 👤 Mon Profil & Niveau Scolaire")
        st.markdown(
            "Indiquez votre nom d'affichage et votre âge. "
            "L'intelligence artificielle Sanad adapte automatiquement ses explications, "
            "ses résumés et la difficulté de ses quiz à votre niveau (Primaire, Collège, Lycée ou Supérieur/Adulte)."
        )

        target_user = active_student_info if (is_admin and active_student_info) else current_user
        current_name = target_user.get("name") or ""
        current_age = int(target_user.get("age") or 14)

        col_p1, col_p2, col_p3 = st.columns([2.5, 1.5, 1.5])
        with col_p1:
            new_prof_name = st.text_input("Nom d'affichage :", value=current_name, key="prof_edit_name_input")
        with col_p2:
            new_prof_age = st.number_input("Âge de l'élève :", min_value=5, max_value=99, value=current_age, key="prof_edit_age_input")
        with col_p3:
            st.write("")
            st.write("")
            save_prof_btn = st.button("💾 Mettre à jour mon profil", type="primary", use_container_width=True, key="btn_save_prof_settings")

        ped_cycle = get_pedagogical_cycle(int(new_prof_age))
        st.info(f"🎯 **Niveau & Cycle :** {ped_cycle['cycle_name']} — *Style d'apprentissage : {ped_cycle['tone']}*")

        if save_prof_btn:
            ok_name, msg_name = update_user_name(active_user_id, new_prof_name)
            ok_age, msg_age = update_user_age(active_user_id, int(new_prof_age))
            if ok_name and ok_age:
                if active_user_id == logged_in_user_id:
                    st.session_state["name"] = new_prof_name
                    if "user" in st.session_state and isinstance(st.session_state["user"], dict):
                        st.session_state["user"]["name"] = new_prof_name
                        st.session_state["user"]["age"] = int(new_prof_age)
                st.success("Profil mis à jour avec succès ! Les contenus générés par l'IA s'adapteront à votre nouvel âge.")
                st.rerun()
            else:
                st.error(f"{msg_name} {msg_age}")

        st.divider()

        st.markdown("### 🔑 Clé API Google Gemini Personnelle")
        st.markdown(
            "Chaque utilisateur renseigne sa propre clé API Google Gemini gratuite. "
            "Elle est stockée de manière strictement privée dans votre profil."
        )

        current_user_gemini = get_user_gemini_api_key(active_user_id) or ""
        col_k1, col_k2 = st.columns([3, 1])
        with col_k1:
            new_user_gemini = st.text_input(
                "Votre clé API Gemini gratuite :",
                value=current_user_gemini,
                type="password",
                placeholder="AIzaSy...",
                help="Gratuite sur https://aistudio.google.com/ sans carte de crédit.",
            )
        with col_k2:
            st.write("")
            st.write("")
            if st.button("💾 Enregistrer la clé", type="primary", use_container_width=True, key="save_student_gemini"):
                if new_user_gemini:
                    save_user_gemini_api_key(active_user_id, new_user_gemini)
                    st.success("Clé enregistrée avec succès !")
                    st.rerun()

        if st.button("🔍 Tester ma connexion Gemini", key="test_student_gemini"):
            with st.spinner("Test de la clé en cours..."):
                res = test_user_gemini_connection(active_user_id)
                if res["success"]:
                    st.success(f"✅ {res['message']}")
                else:
                    st.error(f"❌ {res['error']}")

        render_gemini_key_instructions(expanded=not bool(current_user_gemini))

        st.divider()

        st.markdown("### 🏫 Identifiants Google Classroom Personnels")
        has_user_creds = is_classroom_configured(active_user_id)
        if has_user_creds:
            st.success("🟢 Identifiants Classroom actuellement configurés et actifs.")
        else:
            st.info("ℹ️ Téléversez votre fichier `credentials.json` ci-dessous pour activer la synchronisation de vos classes.")

        cred_file = st.file_uploader("Fichier client `credentials.json` personnel :", type=["json"], key="up_cred_settings")
        if cred_file:
            save_user_credentials(active_user_id, cred_file.read())
            st.success("Fichier credentials.json enregistré dans votre espace personnel !")
            st.rerun()

        render_classroom_credentials_instructions(expanded=not has_user_creds)

        st.divider()

        st.markdown("### 🎙️ Voix de Sanad & Dictée Vocale (Web Speech API)")
        st.markdown(
            "Le tuteur socratique Sanad peut lire ses explications à voix haute et vous permettre de lui parler au micro. "
            "Cette technologie s'exécute **100% dans votre navigateur** : **elle ne consomme aucun jeton de votre quota Gemini et est totalement gratuite.**"
        )
        col_test_v1, col_test_v2, col_test_v3 = st.columns(3)
        with col_test_v1:
            st.markdown("**🇫🇷 Voix Française :**")
            test_fr_html = generate_tts_player_html(
                "Bonjour ! Je suis Sanad, ton tuteur personnel. Prêt pour les révisions ?",
                language="fr",
                player_id="test_voice_fr",
            )
            st.components.v1.html(test_fr_html, height=36)
        with col_test_v2:
            st.markdown("**🇲🇦 Voix Arabe (العربية) :**")
            test_ar_html = generate_tts_player_html(
                "مرحباً بك ! أنا الأستاذ سند، رفيقك في الدراسة والمراجعة.",
                language="ar",
                player_id="test_voice_ar",
            )
            st.components.v1.html(test_ar_html, height=36)
        with col_test_v3:
            st.markdown("**🇬🇧 Voix Anglaise (English) :**")
            test_en_html = generate_tts_player_html(
                "Hello! I am Sanad, your personal study tutor. Ready to practice?",
                language="en",
                player_id="test_voice_en",
            )
            st.components.v1.html(test_en_html, height=36)

        st.divider()

        st.markdown("### 💾 Sauvegarder & Restaurer mes Révisions")
        st.markdown(
            "Exportez l'intégralité de vos cours, vos fiches de révision, vos quiz et vos discussions avec Sanad "
            "dans une archive ZIP personnelle sécurisée."
        )

        my_stats = get_student_backup_summary(active_user_id)
        st.info(
            f"📊 **Vos données actuelles :** {my_stats['courses']} cours | "
            f"{my_stats['messages']} échanges avec l'IA Sanad | {my_stats['quizzes']} quiz | {my_stats['attempts']} entraînements."
        )

        col_sb1, col_sb2 = st.columns(2)
        with col_sb1:
            st.markdown("#### 📥 Sauvegarder mes révisions")
            student_backup_zip = export_student_backup(active_user_id)
            timestamp_str = datetime.now().strftime("%Y%m%d_%H%M")
            target_name = active_student_info["name"] if active_student_info else current_user["name"]
            st.download_button(
                label="💾 Sauvegarder mes révisions (.zip)",
                data=student_backup_zip,
                file_name=f"mes_revisions_{target_name}_{timestamp_str}.zip",
                mime="application/zip",
                type="primary",
                use_container_width=True,
            )

        with col_sb2:
            st.markdown("#### 📤 Restaurer mes révisions")
            uploaded_st_backup = st.file_uploader(
                "Sélectionnez une sauvegarde (.zip ou base .db) :",
                type=["zip", "db", "sqlite"],
                key="restore_student_backup_uploader",
                help="Supporte les nouvelles archives (.zip) et les anciennes sauvegardes (v1.0 ou .db)",
            )
            if uploaded_st_backup and st.button("🚀 Restaurer mes révisions", type="primary", use_container_width=True):
                with st.spinner("Restauration de votre espace en cours..."):
                    res = restore_student_backup(uploaded_st_backup.read(), target_user_id=active_user_id)
                    if res["success"]:
                        st.success(f"✅ {res['message']}")
                        st.balloons()
                        st.rerun()
                    else:
                        st.error(f"❌ {res['error']}")


# Lancement de l'interface authentifiée si un utilisateur est en session
current_session_user = st.session_state.get("user")
if current_session_user:
    render_authenticated_app(current_session_user)
