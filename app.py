"""
Ecole Adnane - Application Web Multi-Utilisateurs de Révision & Préparation aux Examens 3AC (Maroc)
100% Python propulsée par Streamlit, SQLite et Google Gemini.
Supporte Google OAuth, premier connecté = Admin, cloisonnement strict par élève,
sauvegardes étanches et intégration Google Classroom.
"""

import base64
import html
import os
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

# Ensure project root is in sys.path regardless of execution directory or Streamlit runner
import importlib
PROJECT_ROOT = Path(__file__).resolve().parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import streamlit as st

# Safe, hot-reload resilient import of models.database
try:
    import models.database
    if (
        not hasattr(models.database, "get_pedagogical_cycle")
        or not hasattr(models.database, "update_user_age")
        or not hasattr(models.database, "update_user_name")
        or not hasattr(models.database, "update_user_level")
        or not hasattr(models.database, "get_course_mindmap")
        or not hasattr(models.database, "evaluate_and_sync_concept_mastery")
        or not hasattr(models.database, "get_course_trophies_overview")
        or not hasattr(models.database, "evaluate_and_award_course_badges")
        or not hasattr(models.database, "get_student_trophies_by_course")
    ):
        models.database = importlib.reload(models.database)
    from models.database import (
        COURSE_BADGE_CATALOG,
        COURSE_BADGE_CATALOG_MAP,
        MOROCCAN_SCHOOL_LEVELS,
        add_chat_message,
        award_badge,
        clear_chat_history,
        create_user_session,
        delete_course,
        delete_user_account,
        delete_user_session,
        evaluate_and_award_badges,
        evaluate_and_award_course_badges,
        evaluate_and_sync_concept_mastery,
        get_badge_catalog,
        get_chat_history,
        get_course_by_id,
        get_course_mindmap,
        get_course_trophies_overview,
        get_global_admin_kpis,
        get_latest_quiz,
        get_pedagogical_cycle,
        get_quiz_stats,
        get_student_concept_mastery,
        get_student_trophies_by_course,
        get_student_trophies_overview,
        get_user_badges,
        get_user_by_id,
        get_user_count,
        get_user_from_session_token,
        get_user_setting,
        get_setting,
        set_setting,
        init_db,
        is_generic_concept,
        list_courses,
        list_users,
        save_concept_mastery,
        save_course,
        save_course_mindmap,
        save_quiz,
        save_quiz_attempt,
        set_user_blocked_status,
        set_user_setting,
        update_course_metadata,
        update_course_summary,
        update_user_age,
        update_user_level,
        update_user_name,
        update_user_role,
        resolve_course_file_path,
    )
except ImportError:
    import models.database
    models.database = importlib.reload(models.database)
    from models.database import (
        COURSE_BADGE_CATALOG,
        COURSE_BADGE_CATALOG_MAP,
        MOROCCAN_SCHOOL_LEVELS,
        add_chat_message,
        award_badge,
        clear_chat_history,
        create_user_session,
        delete_course,
        delete_user_account,
        delete_user_session,
        evaluate_and_award_badges,
        evaluate_and_award_course_badges,
        evaluate_and_sync_concept_mastery,
        get_badge_catalog,
        get_chat_history,
        get_course_by_id,
        get_course_mindmap,
        get_course_trophies_overview,
        get_global_admin_kpis,
        get_latest_quiz,
        get_pedagogical_cycle,
        get_quiz_stats,
        get_student_concept_mastery,
        get_student_trophies_by_course,
        get_student_trophies_overview,
        get_user_badges,
        get_user_by_id,
        get_user_count,
        get_user_from_session_token,
        get_user_setting,
        get_setting,
        set_setting,
        init_db,
        is_generic_concept,
        list_courses,
        list_users,
        save_concept_mastery,
        save_course,
        save_course_mindmap,
        save_quiz,
        save_quiz_attempt,
        set_user_blocked_status,
        set_user_setting,
        update_course_metadata,
        update_course_summary,
        update_user_age,
        update_user_level,
        update_user_name,
        update_user_role,
        resolve_course_file_path,
    )
    if hasattr(models.database, "get_pedagogical_cycle"):
        get_pedagogical_cycle = models.database.get_pedagogical_cycle
    else:
        def get_pedagogical_cycle(age=None, level=None):
            return {
                "age": 14,
                "level": level or "3AC",
                "stage": "middle",
                "stage_label": f"Collège ({level or '3AC'})",
                "cycle_name": "Cycle Collégial (1AC - 3AC)",
                "badge_text": f"🎒 {level or 'Collège'} (14 ans)",
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

    if hasattr(models.database, "update_user_level"):
        update_user_level = models.database.update_user_level
    else:
        def update_user_level(user_id, level):
            return True, "Niveau enregistré !"

# Safe, hot-reload resilient import of services.ai_engine
try:
    import services.ai_engine
    if (
        not hasattr(services.ai_engine, "generate_quiz")
        or not hasattr(services.ai_engine, "generate_course_mindmap")
    ):
        services.ai_engine = importlib.reload(services.ai_engine)
    from services.ai_engine import (
        classify_and_extract_metadata,
        clean_interactive_mindmap_markdown,
        clean_mermaid_mindmap,
        convert_mermaid_to_markdown,
        generate_course_mindmap,
        generate_quiz,
        generate_revision_sheet,
        socratic_tutor_response,
    )
except ImportError:
    import services.ai_engine
    services.ai_engine = importlib.reload(services.ai_engine)
    from services.ai_engine import (
        classify_and_extract_metadata,
        clean_interactive_mindmap_markdown,
        clean_mermaid_mindmap,
        convert_mermaid_to_markdown,
        generate_course_mindmap,
        generate_quiz,
        generate_revision_sheet,
        socratic_tutor_response,
    )
from services.auth_manager import (
    check_active_user_session,
    check_and_handle_cloud_redirect,
    dev_mode_login,
    exchange_code_for_user,
    extract_auth_code,
    get_google_auth_url,
    get_google_drive_connect_url,
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
from services.google_drive_manager import (
    auto_backup_on_change,
    check_and_auto_heal_on_startup,
    download_backup_from_drive,
    is_drive_connected,
    list_drive_backups,
    restore_backup_from_drive,
    restore_latest_drive_backup,
    upload_backup_to_drive,
)
from services.config_manager import (
    get_gemini_api_key,
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
    if not hasattr(services.voice_manager, "generate_trophy_celebration_html"):
        services.voice_manager = importlib.reload(services.voice_manager)
    from services.voice_manager import (
        clean_text_for_speech,
        generate_chat_mic_injector_html,
        generate_mic_speech_html,
        generate_trophy_celebration_html,
        generate_trophy_sound_wav_base64,
        generate_tts_player_html,
        get_royal_fanfare_mp3_base64,
        get_speech_config,
    )
except Exception:
    from services.voice_manager import (
        clean_text_for_speech,
        generate_chat_mic_injector_html,
        generate_mic_speech_html,
        generate_trophy_celebration_html,
        generate_trophy_sound_wav_base64,
        generate_tts_player_html,
        get_royal_fanfare_mp3_base64,
        get_speech_config,
    )

# Initialisation de la base SQLite et migrations
init_db()
try:
    check_and_auto_heal_on_startup()
except Exception as _e_init_heal:
    logger.debug(f"Auto-heal initial check: {_e_init_heal}")

# Configuration de la page Streamlit
st.set_page_config(
    page_title="Ecole Adnane - Soutien & Révision Scolaire Maroc",
    page_icon="🎓",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Redirection automatique si l'application s'exécute sur Streamlit Cloud vers le serveur dédié officiel
if check_and_handle_cloud_redirect():
    st.stop()

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


def render_interactive_mindmap(content: str, is_ar: bool = False) -> str:
    """
    Génère le composant HTML5 pour afficher une carte mentale interactive ultra-réactive
    avec Markmap (D3.js), zoom/pan fluide, pliage/dépliage dynamique et mode plein écran.
    Prend en charge la rétrocompatibilité si un ancien code Mermaid est fourni.
    """
    if not content:
        content = "# Cours\n## Notions Clés\n- Contenu en cours de préparation"

    stripped = content.strip()
    if stripped.startswith("mindmap") or "root((" in stripped:
        content = convert_mermaid_to_markdown(content)

    escaped_content = html.escape(content)
    lang_attr = "ar" if is_ar else "fr"
    dir_attr = "rtl" if is_ar else "ltr"

    hint_text = (
        "💡 انقر على الدوائر لطي أو فتح المفاهيم • اسحب بالماوس للتحريك • استخدم العجلة للتكبير"
        if is_ar
        else "💡 Cliquez sur les cercles pour replier/déplier les notions • Glissez pour déplacer la carte • Molette pour zoomer"
    )
    fullscreen_label = "⛶ الشاشة الكاملة" if is_ar else "⛶ Plein écran"

    return f"""
    <!DOCTYPE html>
    <html lang="{lang_attr}" dir="{dir_attr}">
    <head>
      <meta charset="utf-8">
      <meta name="viewport" content="width=device-width, initial-scale=1.0">
      <style>
        * {{
          box-sizing: border-box;
          margin: 0;
          padding: 0;
        }}
        html, body {{
          width: 100%;
          height: 100%;
          overflow: hidden;
          background: #ffffff;
          font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
        }}
        #mindmap-card {{
          position: relative;
          width: 100%;
          height: 100%;
          display: flex;
          flex-direction: column;
          background: #ffffff;
          border-radius: 12px;
          border: 1px solid rgba(0, 0, 0, 0.08);
          box-shadow: 0 4px 16px rgba(0, 0, 0, 0.04);
          overflow: hidden;
        }}
        .mindmap-topbar {{
          display: flex;
          align-items: center;
          justify-content: space-between;
          padding: 8px 14px;
          background: #f8fafc;
          border-bottom: 1px solid rgba(0, 0, 0, 0.06);
          font-size: 12px;
          color: #64748b;
          z-index: 10;
        }}
        .mindmap-hint {{
          font-weight: 500;
          overflow: hidden;
          text-overflow: ellipsis;
          white-space: nowrap;
        }}
        .fullscreen-btn {{
          background: #ffffff;
          border: 1px solid #cbd5e1;
          color: #1e293b;
          padding: 4px 10px;
          border-radius: 6px;
          font-size: 12px;
          font-weight: 600;
          cursor: pointer;
          transition: all 0.2s ease;
          display: inline-flex;
          align-items: center;
          gap: 4px;
        }}
        .fullscreen-btn:hover {{
          background: #f1f5f9;
          border-color: #94a3b8;
          transform: translateY(-1px);
        }}
        .markmap-container {{
          flex: 1;
          width: 100%;
          height: calc(100% - 37px);
          position: relative;
        }}
        .markmap {{
          width: 100%;
          height: 100%;
        }}
        .markmap > svg {{
          width: 100%;
          height: 100%;
          display: block;
        }}
        .mm-toolbar {{
          background: rgba(255, 255, 255, 0.95) !important;
          border-radius: 8px !important;
          border: 1px solid rgba(0, 0, 0, 0.1) !important;
          box-shadow: 0 2px 8px rgba(0, 0, 0, 0.08) !important;
        }}
      </style>
      <script>
        window.markmap = {{
          autoLoader: {{
            toolbar: true,
            manual: false
          }}
        }};
      </script>
      <script src="https://cdn.jsdelivr.net/npm/markmap-autoloader@0.17.2"></script>
    </head>
    <body>
      <div id="mindmap-card">
        <div class="mindmap-topbar">
          <span class="mindmap-hint">{hint_text}</span>
          <button class="fullscreen-btn" onclick="toggleFullscreen()">{fullscreen_label}</button>
        </div>
        <div class="markmap-container">
          <div class="markmap">
{escaped_content}
          </div>
        </div>
      </div>
      <script>
        function toggleFullscreen() {{
          const el = document.getElementById("mindmap-card");
          if (!document.fullscreenElement) {{
            if (el.requestFullscreen) {{
              el.requestFullscreen();
            }} else if (el.webkitRequestFullscreen) {{
              el.webkitRequestFullscreen();
            }}
          }} else {{
            if (document.exitFullscreen) {{
              document.exitFullscreen();
            }}
          }}
        }}
      </script>
    </body>
    </html>
    """


def render_mermaid_mindmap(mermaid_code: str, is_ar: bool = False) -> str:
    """Rétrocompatibilité : redirige vers le moteur de carte mentale interactive Markmap."""
    return render_interactive_mindmap(mermaid_code, is_ar=is_ar)


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


def render_student_progress_details(
    student_id: int,
    student_name: str,
    student_email: Optional[str] = None,
    student_age: Optional[int] = None,
    student_cycle: Optional[Dict[str, Any]] = None,
    is_blocked: bool = False,
    created_at: Optional[Any] = None,
    show_nav_buttons: bool = True,
) -> None:
    """Affiche la progression détaillée et les résultats de quiz d'un élève."""
    stats = get_quiz_stats(user_id=student_id)
    u_level = None
    if student_age is None or not student_email:
        u_info = get_user_by_id(student_id)
        if u_info:
            student_age = u_info.get("age", 14)
            u_level = u_info.get("level")
            student_email = student_email or u_info.get("email", "")
            if created_at is None:
                created_at = u_info.get("created_at", "")
            is_blocked = (u_info.get("is_blocked", 0) == 1)
        else:
            student_age = 14
    else:
        u_info = get_user_by_id(student_id)
        if u_info:
            u_level = u_info.get("level")

    if student_cycle is None:
        student_cycle = get_pedagogical_cycle(int(student_age or 14), level=u_level)

    with st.container(border=True):
        head_col1, head_col2 = st.columns([3, 1.4])
        with head_col1:
            st.markdown(f"### 📊 Progression de l'Élève : **{student_name}**")
            status_text = "🔴 Compte Suspendu" if is_blocked else "🟢 Compte Actif"
            level_name = student_cycle.get("level") or student_cycle["stage_label"]
            meta_info = f"📧 `{student_email}` | 🎯 Niveau : **{level_name}** ({student_age} ans - {student_cycle['stage_label']}) | {status_text}"
            if created_at:
                meta_info += f" | 📅 Inscrit le {str(created_at)[:10]}"
            st.caption(meta_info)

        with head_col2:
            if show_nav_buttons:
                b_c1, b_c2 = st.columns([1.2, 0.8])
                with b_c1:
                    if st.button("🚀 Ouvrir son espace", key=f"btn_open_space_{student_id}", use_container_width=True, help="Basculer vers l'espace complet de cet élève"):
                        st.session_state["pending_admin_space"] = str(student_id)
                        st.session_state["admin_student_menu_choice"] = "📊 Mes Progrès"
                        st.rerun()
                with b_c2:
                    if st.button("✖️ Fermer", key=f"btn_close_prog_{student_id}", use_container_width=True, help="Masquer cette fiche"):
                        st.session_state["view_student_progress_id"] = None
                        st.session_state["clear_students_summary_table_selection"] = True
                        st.rerun()

        st.divider()

        # Cartes métriques
        m1, m2, m3, m4 = st.columns(4)
        with m1:
            st.metric("Total Quiz passés", stats.get("total_attempts", 0))
        with m2:
            st.metric("Questions répondues", stats.get("total_questions", 0))
        with m3:
            st.metric("Bonnes réponses", stats.get("total_score", 0))
        with m4:
            st.metric("Moyenne générale", f"{stats.get('average_success_rate', 0.0)}%")

        st.divider()

        # Trophées & Badges remportés
        trophies_info = get_student_trophies_overview(student_id)
        unlocked_trophies = [b for b in trophies_info.get("badges", []) if b["is_unlocked"]]
        st.markdown(f"**🏆 Trophées & Badges ({len(unlocked_trophies)} / {trophies_info['total_trophies']} remportés) :**")
        if unlocked_trophies:
            t_cols = st.columns(min(len(unlocked_trophies), 4))
            for t_idx, t in enumerate(unlocked_trophies):
                with t_cols[t_idx % min(len(unlocked_trophies), 4)]:
                    st.caption(f"{t['icon']} **{t['title']}**")
        else:
            st.caption("🔒 *Aucun trophée débloqué pour le moment.*")

        st.divider()

        col_sub, col_hist = st.columns([1, 1])
        with col_sub:
            st.markdown("#### 🎯 Maîtrise par matière")
            by_subj = stats.get("by_subject", [])
            if by_subj:
                for s in by_subj:
                    rate = s["success_rate"]
                    badge_cls = get_subject_badge_class(s["subject"])
                    st.markdown(
                        f"<div><span class='badge-subject {badge_cls}'>{s['subject']}</span> "
                        f"<strong>{rate}%</strong> ({s['attempts']} quiz)</div>",
                        unsafe_allow_html=True,
                    )
                    st.progress(rate / 100.0)
                    st.write("")
            else:
                st.info("ℹ️ Aucun quiz passé pour le moment par cet élève.")

        with col_hist:
            st.markdown("#### 🕒 Derniers entraînements")
            recent = stats.get("recent_attempts", [])
            if recent:
                for a in recent:
                    date_str = str(a.get("completed_at", ""))[:16]
                    st.markdown(
                        f"- **{a['course_title']}** ({a['subject']}) : `{a['score']}/{a['total_questions']}` — <small>{date_str}</small>",
                        unsafe_allow_html=True,
                    )
            else:
                st.caption("L'historique des quiz récents apparaîtra ici dès ses premiers entraînements.")


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

        if authenticated_user.get("role") == "admin":
            try:
                heal_res = check_and_auto_heal_on_startup(authenticated_user.get("id"))
                if heal_res and heal_res.get("success"):
                    st.toast("☁️ Données restaurées avec succès depuis Google Drive !", icon="✅")
            except Exception as e_heal:
                logger.warning(f"Erreur auto-guérison post-connexion : {e_heal}")

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
            "Plateforme d'Apprentissage & Révision Scolaire (Maroc)"
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


def render_magnificent_trophy_grid(badges: List[Dict[str, Any]], cols_count: int = 2) -> None:
    """Affiche une grille de trophées avec un design somptueux, immersif et stimulant."""
    if not badges:
        st.info("Aucun trophée à afficher dans cette catégorie.")
        return

    cols = st.columns(cols_count)
    for idx, badge in enumerate(badges):
        col = cols[idx % cols_count]
        with col:
            is_unlocked = badge.get("is_unlocked", False)
            unlocked_at = badge.get("unlocked_at")

            if is_unlocked:
                bg_style = "linear-gradient(135deg, rgba(30, 41, 59, 0.95) 0%, rgba(15, 23, 42, 0.98) 100%)"
                border_color = "#f59e0b"
                shadow_style = "0 8px 20px -4px rgba(245, 158, 11, 0.35), inset 0 1px 1px rgba(255, 255, 255, 0.15)"
                title_color = "#fef08a"
                desc_color = "#e2e8f0"
                glow_aura = "radial-gradient(circle, rgba(245, 158, 11, 0.3) 0%, transparent 70%)"
                badge_tag = (
                    "<span style='background: linear-gradient(135deg, #10b981 0%, #059669 100%); "
                    "color: #ffffff; padding: 4px 12px; border-radius: 20px; font-size: 0.75rem; "
                    "font-weight: 800; letter-spacing: 0.5px; box-shadow: 0 2px 6px rgba(16, 185, 129, 0.4);'>"
                    "✨ DÉBLOQUÉ</span>"
                )
                icon_filter = "drop-shadow(0 0 10px rgba(251, 191, 36, 0.65))"
                pct = 100
                prog_val = 1.0
            else:
                bg_style = "linear-gradient(135deg, rgba(15, 23, 42, 0.75) 0%, rgba(2, 6, 23, 0.85) 100%)"
                border_color = "#334155"
                shadow_style = "0 4px 12px rgba(0, 0, 0, 0.3)"
                title_color = "#cbd5e1"
                desc_color = "#94a3b8"
                glow_aura = "none"
                badge_tag = (
                    "<span style='background: rgba(51, 65, 85, 0.8); color: #94a3b8; padding: 4px 12px; "
                    "border-radius: 20px; font-size: 0.75rem; font-weight: 700; letter-spacing: 0.5px; "
                    "border: 1px solid #475569;'>🔒 EN COURS</span>"
                )
                icon_filter = "grayscale(100%) opacity(0.38)"
                pct = badge.get("progress_percent", 0)
                prog_val = badge.get("progress_ratio", 0.0)

            card_html = f"""
            <div style="background: {bg_style}; border: 1.5px solid {border_color}; border-radius: 16px; padding: 18px 20px; margin-bottom: 14px; box-shadow: {shadow_style}; backdrop-filter: blur(12px); position: relative; overflow: hidden;">
                <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px;">
                    <div style="width: 52px; height: 52px; display: flex; align-items: center; justify-content: center; background: {glow_aura}; border-radius: 50%;">
                        <span style="font-size: 2.2rem; filter: {icon_filter}; line-height: 1;">{badge['icon']}</span>
                    </div>
                    <div>{badge_tag}</div>
                </div>
                <div style="font-size: 1.15rem; font-weight: 800; color: {title_color}; margin-bottom: 4px; letter-spacing: -0.2px;">
                    {badge['title']}
                </div>
                <div style="display: inline-block; background: rgba(59, 130, 246, 0.15); color: #93c5fd; padding: 2px 8px; border-radius: 6px; font-size: 0.72rem; font-weight: 600; margin-bottom: 8px;">
                    {badge.get('category', 'Trophée')}
                </div>
                <div style="font-size: 0.85rem; color: {desc_color}; line-height: 1.45; margin-bottom: 12px; min-height: 38px;">
                    🎯 <strong>Mission :</strong> {badge['description']}
                </div>
                <div style="display: flex; justify-content: space-between; align-items: center; font-size: 0.8rem; color: #94a3b8; margin-bottom: 6px;">
                    <span>Objectif : <strong>{badge['current_value']} / {badge['target_value']} {badge['unit']}</strong></span>
                    <span style="font-weight: 700; color: {'#34d399' if is_unlocked else '#60a5fa'};">{pct}%</span>
                </div>
            </div>
            """
            st.markdown(card_html, unsafe_allow_html=True)
            st.progress(prog_val)
            if is_unlocked and unlocked_at:
                date_str = str(unlocked_at)[:16]
                st.caption(f"🎖️ Décroché le {date_str} • *{badge['encouragement']}*")
            else:
                st.caption(f"💡 *{badge['encouragement']}*")
            st.write("")


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
    user_cycle = get_pedagogical_cycle(current_user.get("age"), level=current_user.get("level"))
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
            s_cycle = get_pedagogical_cycle(s.get("age"), level=s.get("level"))
            blocked_tag = " [SUSPENDU]" if s.get("is_blocked") else ""
            student_options[str(s["id"])] = f"{s_cycle['badge_text']} — {s['name']} ({s['email']}){blocked_tag}"

        if "pending_admin_space" in st.session_state:
            pending_space = str(st.session_state.pop("pending_admin_space"))
            if pending_space in student_options:
                st.session_state["admin_space_selector"] = pending_space

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
            student_menu_items = [
                "📚 Mes Cours (Révisions)",
                "➕ Ajouter un Cours",
                "📊 Mes Progrès",
                "🏆 Trophées & Badges",
                "⚙️ Sauvegardes & Paramètres de l'élève",
            ]
            default_menu_idx = 0
            if "admin_student_menu_choice" in st.session_state:
                choice = st.session_state.pop("admin_student_menu_choice")
                if choice in student_menu_items:
                    default_menu_idx = student_menu_items.index(choice)

            menu = st.sidebar.radio(
                f"Espace de {active_student_info['name']}",
                student_menu_items,
                index=default_menu_idx,
                key=f"admin_student_menu_{active_user_id}",
            )
    else:
        # ÉLÈVE : Navigation complète d'apprentissage personnel
        is_global_admin_view = False
        active_user_id = logged_in_user_id
        active_student_info = None
        menu = st.sidebar.radio(
            "Mon Espace d'Apprentissage",
            ["📚 Mes Cours (Révisions)", "➕ Ajouter un Cours", "📊 Mes Progrès", "🏆 Mes Trophées", "⚙️ Paramètres & Sauvegardes"],
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
            st.caption("💡 *Cliquez sur la ligne d'un élève dans le tableau ou sur son nom ci-dessous pour afficher sa progression.*")

            # Table interactive avec sélection de ligne unique
            df_rows = [
                {
                    "ID": s["user_id"],
                    "Nom": s["name"],
                    "Email": s["email"],
                    "Niveau & Âge": f"{s.get('level') or s.get('cycle', {}).get('level', '3AC')} • {s.get('age', 14)} ans ({s.get('cycle', {}).get('stage_label', 'Collège')})",
                    "Statut": "🔴 Suspendu" if s.get("is_blocked") == 1 else "🟢 Actif",
                    "Cours disponibles": s["course_count"],
                    "Quiz terminés": s["attempt_count"],
                    "Moyenne Quiz": f"{s['average_rate']}%",
                    "Date d'inscription": str(s.get("created_at", ""))[:16],
                }
                for s in students_summary
            ]

            if st.session_state.get("clear_students_summary_table_selection"):
                st.session_state.pop("clear_students_summary_table_selection", None)
                if "admin_students_summary_table" in st.session_state:
                    st.session_state["admin_students_summary_table"] = {"selection": {"rows": []}}

            df_selection = st.dataframe(
                df_rows,
                use_container_width=True,
                hide_index=True,
                on_select="rerun",
                selection_mode="single-row",
                key="admin_students_summary_table",
            )

            # Prise en compte du clic sur une ligne du tableau
            if df_selection and hasattr(df_selection, "selection") and df_selection.selection:
                selected_rows = getattr(df_selection.selection, "rows", [])
                if selected_rows:
                    sel_idx = selected_rows[0]
                    if 0 <= sel_idx < len(students_summary):
                        st.session_state["view_student_progress_id"] = students_summary[sel_idx]["user_id"]

            # Boutons cliquables avec les noms de chaque élève pour un accès direct
            st.markdown("**👤 Cliquez sur le nom d'un élève pour voir sa progression :**")
            cols_per_row = min(max(len(students_summary), 1), 4)
            st_cols = st.columns(cols_per_row)
            for idx, s in enumerate(students_summary):
                col = st_cols[idx % cols_per_row]
                is_selected = (st.session_state.get("view_student_progress_id") == s["user_id"])
                status_emoji = "🔴" if s.get("is_blocked") == 1 else "🎒"
                student_lvl = s.get("level") or s.get("cycle", {}).get("level", "3AC")
                if col.button(
                    f"{status_emoji} {s['name']} ({student_lvl})",
                    key=f"btn_st_click_name_{s['user_id']}",
                    type="primary" if is_selected else "secondary",
                    use_container_width=True,
                    help=f"Consulter la progression de {s['name']} ({s['email']})",
                ):
                    st.session_state["view_student_progress_id"] = s["user_id"]
                    st.rerun()

            # Affichage de la progression de l'élève sélectionné
            active_prog_id = st.session_state.get("view_student_progress_id")
            if active_prog_id:
                target_st = next((s for s in students_summary if s["user_id"] == active_prog_id), None)
                if not target_st:
                    target_st = get_user_by_id(active_prog_id)
                if target_st:
                    st.write("")
                    render_student_progress_details(
                        student_id=target_st.get("user_id") or target_st.get("id"),
                        student_name=target_st.get("name", "Élève"),
                        student_email=target_st.get("email"),
                        student_age=target_st.get("age"),
                        student_cycle=target_st.get("cycle"),
                        is_blocked=(target_st.get("is_blocked", 0) == 1),
                        created_at=target_st.get("created_at"),
                        show_nav_buttons=True,
                    )
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
            u_cycle = get_pedagogical_cycle(u.get("age"), level=u.get("level"))
            role_badge = "👑 Administrateur" if is_u_admin else u_cycle["badge_text"]
            self_tag = " *(Votre compte)*" if is_self else ""

            expander_title = f"{role_badge} — **{u['name']}** (`{u['email']}`) | {status_badge}{self_tag}"
            with st.expander(expander_title, expanded=False):
                col_u0, col_u1, col_u2, col_u3 = st.columns([2.5, 2, 2, 2.5])

                # 0. Nom, Âge et Niveau
                with col_u0:
                    st.markdown("##### 👤 Profil, Âge & Niveau")
                    edit_name_val = st.text_input("Nom :", value=u["name"], key=f"admin_edit_name_{u_id}")
                    current_age_val = int(u.get("age") or 14)
                    edit_age_val = st.number_input("Âge :", min_value=5, max_value=99, value=current_age_val, key=f"admin_edit_age_{u_id}")
                    current_lvl_val = u.get("level") or u_cycle.get("level", "3AC")
                    lvl_options = MOROCCAN_SCHOOL_LEVELS
                    lvl_idx = lvl_options.index(current_lvl_val) if current_lvl_val in lvl_options else (lvl_options.index("3AC") if "3AC" in lvl_options else 0)
                    edit_lvl_val = st.selectbox("Niveau scolaire :", options=lvl_options, index=lvl_idx, key=f"admin_edit_lvl_{u_id}")
                    if edit_name_val != u["name"] or edit_age_val != current_age_val or edit_lvl_val != u.get("level"):
                        if st.button("💾 Enregistrer profil", key=f"btn_save_prof_{u_id}", type="primary"):
                            ok_n, msg_n = update_user_name(u_id, edit_name_val)
                            ok_a, msg_a = update_user_age(u_id, int(edit_age_val))
                            ok_l, msg_l = update_user_level(u_id, edit_lvl_val)
                            if ok_n and ok_a and ok_l:
                                st.success("Profil mis à jour !")
                                st.rerun()
                            else:
                                st.error(f"{msg_n} {msg_a} {msg_l}")

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

                if not is_u_admin:
                    st.divider()
                    st.markdown("##### 📊 Suivi & Progression Pédagogique")
                    show_manage_prog = st.checkbox("Afficher la progression détaillée de cet élève", key=f"chk_manage_prog_{u_id}")
                    if show_manage_prog:
                        render_student_progress_details(
                            student_id=u_id,
                            student_name=u["name"],
                            student_email=u["email"],
                            student_age=u.get("age"),
                            is_blocked=is_u_blocked,
                            created_at=u.get("created_at"),
                            show_nav_buttons=True,
                        )

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

        st.markdown("### ☁️ Sauvegarde Automatique & Restauration Google Drive")
        st.markdown(
            "Immunise l'application contre les pertes de données causées par les redémarrages de Streamlit Cloud. "
            "Les sauvegardes sont envoyées dans votre dossier Google Drive dédié **`EcoleAdnane_Backups`**."
        )

        drive_ok = is_drive_connected(logged_in_user_id)
        if drive_ok:
            st.success("🟢 **Google Drive connecté :** Le dossier `EcoleAdnane_Backups` est actif et sécurisé.", icon="☁️")
            col_gd1, col_gd2 = st.columns([1.5, 2])
            with col_gd1:
                if st.button("☁️ Sauvegarder sur Google Drive maintenant", type="primary", use_container_width=True, key="admin_backup_gdrive_now_btn"):
                    with st.spinner("Téléversement de la sauvegarde vers Google Drive..."):
                        up_res = upload_backup_to_drive(user_id=logged_in_user_id)
                        if up_res["success"]:
                            st.success(f"✅ Sauvegarde réussie : **{up_res['file_name']}** ({up_res['size_formatted']})")
                            st.balloons()
                            st.rerun()
                        else:
                            st.error(f"❌ Erreur lors de la sauvegarde : {up_res.get('error')}")

            with col_gd2:
                last_bk = get_setting("last_gdrive_backup_at")
                if last_bk:
                    try:
                        dt_bk = datetime.fromisoformat(last_bk)
                        st.caption(f"🕒 **Dernière sauvegarde Drive :** {dt_bk.strftime('%d/%m/%Y à %H:%M')}")
                    except Exception:
                        pass
                else:
                    st.caption("ℹ️ Aucune sauvegarde Drive effectuée pour l'instant.")

            # Liste des sauvegardes disponibles sur Google Drive
            with st.expander("📂 Consulter les sauvegardes sur Google Drive & Restaurer", expanded=False):
                with st.spinner("Récupération des sauvegardes depuis Google Drive..."):
                    drive_backups = list_drive_backups(user_id=logged_in_user_id)
                if not drive_backups:
                    st.info("Aucune archive ZIP trouvée dans le dossier `EcoleAdnane_Backups`.")
                else:
                    st.markdown(f"**{len(drive_backups)} sauvegarde(s) disponible(s) :**")
                    for bk in drive_backups:
                        c_bk1, c_bk2, c_bk3 = st.columns([3, 1.2, 1.5])
                        with c_bk1:
                            st.markdown(f"📦 **{bk['name']}**<br><span style='color:#94a3b8;font-size:0.8rem;'>{bk['date_formatted']} • {bk['size_formatted']}</span>", unsafe_allow_html=True)
                        with c_bk2:
                            if bk.get("web_link"):
                                st.markdown(f"[Ouvrir Drive ↗]({bk['web_link']})")
                        with c_bk3:
                            if st.button("📥 Restaurer", key=f"btn_restore_drive_{bk['id']}", use_container_width=True):
                                with st.spinner(f"Restauration de {bk['name']} depuis Google Drive..."):
                                    res_drive = restore_backup_from_drive(bk['id'], user_id=logged_in_user_id)
                                    if res_drive["success"]:
                                        st.success(f"✅ Restauration réussie : {res_drive['message']}")
                                        st.balloons()
                                        st.rerun()
                                    else:
                                        st.error(f"❌ Erreur : {res_drive.get('error')}")
        else:
            st.warning("⚠️ **Google Drive non connecté :** Connectez votre compte Google pour activer les sauvegardes automatiques dans votre Drive.", icon="🔑")
            drive_auth_url = get_google_drive_connect_url()
            col_con1, col_con2 = st.columns([1.5, 2.5])
            with col_con1:
                if drive_auth_url:
                    st.link_button("🔗 Connecter mon Google Drive", drive_auth_url, type="primary", use_container_width=True)
                else:
                    st.info("Configurez vos identifiants Google OAuth pour connecter Drive.")
            with col_con2:
                st.caption(
                    "👉 Utilise le scope sécurisé `drive.file` : l'application n'accède qu'au dossier `EcoleAdnane_Backups` "
                    "qu'elle crée elle-même pour vos sauvegardes."
                )

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

        st.divider()
        st.markdown("### 🎺 Test de la Fanfare Royale & Célébration des Trophées")
        st.markdown(
            "Testez en conditions réelles la fanfare royale MP3 officielle ainsi que la pluie d'étoiles dorées et de couronnes "
            "qui retentissent lorsqu'un élève débloque un trophée d'excellence. *(Outil réservé exclusivement à l'administrateur)*"
        )
        col_tst1, col_tst2 = st.columns([1.5, 2.5])
        with col_tst1:
            if st.button("🎺 Tester la célébration royale (MP3 + Pluie d'or)", type="primary", use_container_width=True, key="admin_test_trophy_btn"):
                st.session_state["admin_trophy_test_nonce"] = int(time.time() * 1000)

        test_nonce = st.session_state.pop("admin_trophy_test_nonce", None)
        if test_nonce:
            st.components.v1.html(
                generate_trophy_celebration_html(
                    auto_play=True,
                    widget_id=f"admin_test_{test_nonce}",
                    show_button=False,
                ),
                height=0,
            )
            st.balloons()
            st.success("👑 **Célébration royale déclenchée avec succès !** La fanfare MP3 retentit et les particules d'or et couronnes s'animent.")

        return

    # -----------------------------------------------------------------------
    # VUE ÉLÈVE : MES COURS (RÉVISIONS PAR ÉLÈVE)
    # -----------------------------------------------------------------------
    if menu == "📚 Mes Cours (Révisions)":
        if is_admin and active_student_info:
            st.info(f"👀 **Espace de supervision :** Vous consultez les cours de l'élève **{active_student_info['name']}** (`{active_student_info['email']}`).")

        active_u_dict = active_student_info if (is_admin and active_student_info) else current_user
        active_u_cycle = get_pedagogical_cycle(active_u_dict.get("age"), level=active_u_dict.get("level"))
        st.title(f"📚 Espace de Révision — {active_u_cycle.get('level', 'Collège')}")

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
            key="student_selected_course_id",
        )

        current_course = get_course_by_id(selected_course_id, user_id=active_user_id)
        if not current_course:
            st.error("Cours introuvable ou accès non autorisé.")
            return

        is_ar = current_course["language"] == "ar"
        is_en = current_course["language"] == "en"
        badge_cls = get_subject_badge_class(current_course["subject"])

        # La suppression d'un cours est autorisée pour l'admin ou pour l'élève propriétaire de son cours
        can_delete = is_admin or (current_course.get("user_id") == active_user_id)

        del_warn_text = (
            "⚠️ تنبيه : هذا الإجراء نهائي وسيؤدي إلى حذف هذا الدرس وبطاقة مراجعته واختباراته ومحادثات الأستاذ المساعد سند."
            if is_ar
            else (
                "⚠️ Warning: Deletion is permanent and removes the document, summaries, quizzes, and tutor history."
                if is_en
                else "⚠️ Attention : La suppression est définitive et effacera ce document, sa fiche express, ses quiz et l'historique du tuteur."
            )
        )
        del_chk_text = (
            "أؤكد رغبتي في حذف هذا الدرس نهائياً"
            if is_ar
            else ("I confirm I want to permanently delete this course" if is_en else "Je confirme vouloir supprimer définitivement ce cours")
        )
        del_btn_text = "🗑️ تأكيد الحذف الآن" if is_ar else ("🗑️ Delete Now" if is_en else "🗑️ Confirmer la suppression")

        active_user_dict = active_student_info if (is_admin and active_student_info) else current_user
        active_cycle = get_pedagogical_cycle(active_user_dict.get("age"), level=active_user_dict.get("level"))

        if is_ar:
            level_label = f"المستوى : {active_cycle['stage_label']} ({active_cycle['age']} سنة)"
            lang_badge_text = "العربية (AR)"
        elif is_en:
            level_label = f"Level: {active_cycle['stage_label']} ({active_cycle['age']} yo)"
            lang_badge_text = "English (EN)"
        else:
            level_label = f"Niveau : {active_cycle['stage_label']} ({active_cycle['age']} ans)"
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

        valid_concepts = [c for c in (current_course.get("key_concepts") or []) if not is_generic_concept(c)]
        if valid_concepts:
            if is_ar:
                chips = " ".join([f"<span class='concept-tag'>{c}</span>" for c in valid_concepts])
                st.markdown(f"<div dir='rtl' style='text-align:right; margin-top:8px; margin-bottom:12px;'><strong>المفاهيم الأساسية :</strong> {chips}</div>", unsafe_allow_html=True)
            elif is_en:
                chips = " ".join([f"<span class='concept-tag'>#{c}</span>" for c in valid_concepts])
                st.markdown(f"**Key Concepts:** {chips}", unsafe_allow_html=True)
            else:
                chips = " ".join([f"<span class='concept-tag'>#{c}</span>" for c in valid_concepts])
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

            btn_save_txt = "💾 حفظ التعديل" if is_ar else ("💾 Save Changes" if is_en else "💾 Enregistrer les modifications")
            btn_del_txt = "🗑️ حذف الدرس" if is_ar else ("🗑️ Delete Course" if is_en else "🗑️ Supprimer ce cours")
            btn_save_col1, btn_del_col2 = st.columns([1, 1])
            with btn_save_col1:
                if st.button(btn_save_txt, type="primary", use_container_width=True, key=f"btn_save_m_{current_course['id']}"):
                    update_course_metadata(current_course["id"], new_title, cleaned_subj, final_lang, user_id=active_user_id)
                    st.success("Modifications enregistrées !" if not is_en else "Changes saved successfully!")
                    st.rerun()

            with btn_del_col2:
                with st.popover(btn_del_txt, use_container_width=True):
                    st.markdown(f"**{'🗑️ حذف هذا الدرس' if is_ar else ('🗑️ Delete this course' if is_en else '🗑️ Supprimer ce cours')}**")
                    st.caption(current_course["title"])
                    if can_delete:
                        st.warning(del_warn_text)
                        confirm_meta_del = st.checkbox(del_chk_text, key=f"meta_del_chk_{current_course['id']}")
                        if st.button(del_btn_text, type="primary", disabled=not confirm_meta_del, key=f"meta_del_btn_{current_course['id']}", use_container_width=True):
                            delete_course(current_course["id"], user_id=None if is_admin else active_user_id)
                            st.session_state.pop("student_selected_course_id", None)
                            st.success("تم حذف الدرس بنجاح !" if is_ar else ("Course deleted successfully!" if is_en else "Le cours a été supprimé avec succès !"))
                            st.rerun()
                    else:
                        st.info(
                            "ℹ️ هذا الدرس مشترك من المؤسسة ولا يمكن حذفه من حساب تلميذ."
                            if is_ar
                            else (
                                "ℹ️ This is a shared school course and cannot be deleted by a student account."
                                if is_en
                                else "ℹ️ Ce cours fait partie du tronc commun de l'établissement et ne peut pas être supprimé par un compte élève."
                            )
                        )

        st.write("")

        if is_ar:
            tab_doc, tab_fiche, tab_schema, tab_notions, tab_quiz, tab_tuteur, tab_trophies = st.tabs([
                "📄 وثيقة الدرس",
                "⚡ بطاقة المراجعة",
                "🧠 خريطة ذهنية",
                "🎯 المفاهيم والمكتسبات",
                "📝 تدريب الامتحان",
                "🤖 الأستاذ سند",
                "🏆 شارات وكؤوس الدرس",
            ])
        elif is_en:
            tab_doc, tab_fiche, tab_schema, tab_notions, tab_quiz, tab_tuteur, tab_trophies = st.tabs([
                "📄 Course Document",
                "⚡ Revision Sheet",
                "🧠 Mind Map",
                "🎯 Key Concepts",
                "📝 Exam Quiz",
                "🤖 AI Tutor (Sanad)",
                "🏆 Course Trophies",
            ])
        else:
            tab_doc, tab_fiche, tab_schema, tab_notions, tab_quiz, tab_tuteur, tab_trophies = st.tabs([
                "📄 Le Document",
                "⚡ Fiche Express",
                "🧠 Carte Mentale",
                "🎯 Notions & Acquis",
                "📝 Entraînement Examen",
                "🤖 Tuteur Virtuel (Sanad)",
                "🏆 Trophées du Cours",
            ])

        with tab_doc:
            raw_fp = current_course.get("file_path")
            file_path = resolve_course_file_path(
                raw_fp,
                file_name=current_course.get("file_name"),
                file_hash=current_course.get("file_hash"),
                user_id=current_course.get("user_id"),
            )
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

        with tab_schema:
            if is_ar:
                st.markdown("<div class='rtl-section-title'>🧠 خريطة ذهنية ومخطط الدرس التفاعلي</div>", unsafe_allow_html=True)
                st.caption("خريطة ذهنية تفاعلية بالذكاء الاصطناعي، شاملة ومستقلة بذاتها لتعلم وفهم الدرس كاملاً، مع إمكانية التكبير والتصغير وتوسيع المفاهيم ووضع الشاشة الكاملة.")
            elif is_en:
                st.markdown("### 🧠 Interactive Course Mind Map")
                st.caption("Rich, self-contained interactive mind map for autonomous lesson study. Features expandable nodes, smooth zoom/pan, and fullscreen mode.")
            else:
                st.markdown("### 🧠 Carte Mentale & Schéma Visuel du Cours")
                st.caption("Carte mentale interactive et auto-suffisante pour apprendre l'intégralité du cours. Nœuds dépliables, zoom/pan fluide et mode plein écran.")

            cached_mindmap = get_course_mindmap(current_course["id"]) or current_course.get("mindmap_code")

            if not cached_mindmap:
                btn_gen_map = "🧠 توليد الخريطة الذهنية بالذكاء الاصطناعي" if is_ar else ("🧠 Generate AI Mind Map" if is_en else "🧠 Générer la Carte Mentale avec l'IA")
                st.info(
                    "💡 Ce cours ne possède pas encore de carte mentale interactive. Cliquez sur le bouton ci-dessous pour la générer en quelques secondes."
                    if not is_en and not is_ar else
                    ("💡 لم يتم إنشاء خريطة ذهنية لهذا الدرس بعد. انقر على الزر أدناه لتوليدها فوراً." if is_ar else "💡 No mind map generated for this course yet. Click below to generate it instantly.")
                )
                if st.button(btn_gen_map, type="primary", key=f"btn_gen_mindmap_{current_course['id']}"):
                    if not user_api_key:
                        st.error("⚠️ Clé API Gemini requise. Obtenez votre clé 100% gratuite sur [Google AI Studio](https://aistudio.google.com/) et activez-la dans **⚙️ Paramètres** ou la barre latérale." if not is_en else "⚠️ Gemini API key required. Get your free key on [Google AI Studio](https://aistudio.google.com/) and configure it in **⚙️ Settings** or the sidebar.")
                    else:
                        spin_msg = "Génération de la carte mentale..." if not is_en else ("Generating mind map..." if not is_ar else "جاري إنشاء الخريطة الذهنية...")
                        with st.spinner(spin_msg):
                            course_content = current_course.get("summary_markdown") or current_course.get("raw_text") or ""
                            generated_mindmap = generate_course_mindmap(
                                course_text_or_summary=course_content,
                                course_title=current_course["title"],
                                subject=current_course["subject"],
                                language=current_course.get("language", "fr"),
                                user_id=active_user_id,
                            )
                            save_course_mindmap(current_course["id"], generated_mindmap)
                            current_course["mindmap_code"] = generated_mindmap
                            st.success("Carte mentale générée avec succès !" if not is_en else "Mind map generated successfully!")
                            st.rerun()
            else:
                if cached_mindmap.strip().startswith("mindmap"):
                    legacy_hint = (
                        "💡 هذا الدرس يستخدم مخططاً سابقاً. انقر على **🔄 إعادة توليد الخريطة الذهنية** للترقية إلى الخريطة التفاعلية الشاملة الجديدة."
                        if is_ar
                        else (
                            "💡 This course uses an earlier diagram format. Click **🔄 Regenerate Mind Map** to upgrade to the new rich interactive mind map."
                            if is_en
                            else "💡 Ce cours dispose d'un schéma Mermaid antérieur. Cliquez sur **🔄 Régénérer la Carte Mentale** pour générer la nouvelle carte interactive enrichie et auto-suffisante."
                        )
                    )
                    st.info(legacy_hint)

                # Affichage de la carte interactive Markmap (D3.js)
                html_component = render_interactive_mindmap(cached_mindmap, is_ar=is_ar)
                st.components.v1.html(html_component, height=580, scrolling=False)

                col_map_actions1, col_map_actions2 = st.columns([0.5, 0.5])
                with col_map_actions1:
                    regen_map_label = "🔄 إعادة توليد الخريطة الذهنية" if is_ar else ("🔄 Regenerate Mind Map" if is_en else "🔄 Régénérer la Carte Mentale")
                    if st.button(regen_map_label, key=f"btn_regen_mindmap_{current_course['id']}"):
                        if not user_api_key:
                            st.error("⚠️ Clé API Gemini requise." if not is_en else "⚠️ Gemini API key required.")
                        else:
                            with st.spinner("Régénération de la carte mentale..." if not is_en else "Regenerating..."):
                                course_content = current_course.get("summary_markdown") or current_course.get("raw_text") or ""
                                generated_mindmap = generate_course_mindmap(
                                    course_text_or_summary=course_content,
                                    course_title=current_course["title"],
                                    subject=current_course["subject"],
                                    language=current_course.get("language", "fr"),
                                    user_id=active_user_id,
                                )
                                save_course_mindmap(current_course["id"], generated_mindmap)
                                current_course["mindmap_code"] = generated_mindmap
                                st.rerun()

                with col_map_actions2:
                    exp_title = "📋 عرض هيكل المخطط (Markdown)" if is_ar else ("📋 View Mind Map Outline" if is_en else "📋 Voir la structure de la carte")
                    with st.expander(exp_title):
                        code_lang = "mermaid" if cached_mindmap.strip().startswith("mindmap") else "markdown"
                        st.code(cached_mindmap, language=code_lang)

        with tab_notions:
            if is_ar:
                st.markdown("<div class='rtl-section-title'>🎯 تتبع استيعاب المفاهيم والمكتسبات</div>", unsafe_allow_html=True)
                st.caption("تقييم ذاتي ذكي ومحلي (0 استهلاك لرصيد الذكاء الاصطناعي) مبني على نتائج الاختبارات وأسئلتك للأستاذ سند.")
            elif is_en:
                st.markdown("### 🎯 Key Concepts & Mastery Tracking")
                st.caption("Automatic local diagnostic (0 AI quota used) tracking your understanding based on quiz attempts and tutor chats.")
            else:
                st.markdown("### 🎯 Suivi de l'Assimilation des Notions Clés")
                st.caption("Diagnostic pédagogique automatique (100% local, 0 jeton Gemini consommé) mesurant la maîtrise de chaque notion grâce aux quiz et échanges avec Sanad.")

            # Évaluation locale synchronisée
            mastery_data = evaluate_and_sync_concept_mastery(active_user_id, current_course["id"])
            if not mastery_data:
                mastery_data = get_student_concept_mastery(active_user_id, current_course["id"])

            # Filtrage défensif absolu contre toute méta-catégorie générique
            mastery_data = [c for c in (mastery_data or []) if not is_generic_concept(c.get("concept_title", ""))]

            total_concepts = len(mastery_data)
            mastered_count = sum(1 for c in mastery_data if c["status"] == "mastered")
            in_prog_count = sum(1 for c in mastery_data if c["status"] == "in_progress")
            to_rev_count = sum(1 for c in mastery_data if c["status"] == "to_review")
            untested_count = sum(1 for c in mastery_data if c["status"] == "untested")

            # Synthèse & Jauge de progression
            m_pct = round(mastered_count / total_concepts * 100) if total_concepts > 0 else 0
            st.write("")
            col_kpi1, col_kpi2, col_kpi3, col_kpi4 = st.columns(4)
            col_kpi1.metric("📚 Notions Clés" if not is_ar else "📚 مجموع المفاهيم", total_concepts)
            col_kpi2.metric("🟢 Assimilées" if not is_ar else "🟢 تم استيعابها", mastered_count)
            col_kpi3.metric("🟡 En cours" if not is_ar else "🟡 في طور التثبيت", in_prog_count)
            col_kpi4.metric("🔴 À réviser" if not is_ar else "🔴 تحتاج مراجعة", to_rev_count)

            st.progress(mastered_count / total_concepts if total_concepts > 0 else 0.0)
            progress_caption = (
                f"**Progression globale :** {mastered_count} sur {total_concepts} notion(s) maîtrisée(s) ({m_pct}%)"
                if not is_en and not is_ar else
                (f"**التقدم العام :** {mastered_count} من أصل {total_concepts} مفهوم مستوعب ({m_pct}%)" if is_ar else f"**Overall Progress:** {mastered_count} of {total_concepts} concepts mastered ({m_pct}%)")
            )
            st.caption(progress_caption)
            st.write("---")

            status_labels = {
                "mastered": ("🟢 Assimilé", "🟢 تم الاستيعاب", "🟢 Mastered"),
                "in_progress": ("🟡 En consolidation", "🟡 قيد التثبيت", "🟡 In Progress"),
                "to_review": ("🔴 À réviser", "🔴 بحاجة لمراجعة", "🔴 Needs Review"),
                "untested": ("⚪ Non évalué", "⚪ لم يُقيّم بعد", "⚪ Untested"),
            }

            for idx, item in enumerate(mastery_data):
                c_title = item.get("concept_title", "Notion")
                c_status = item.get("status", "untested")
                c_rate = item.get("success_rate", 0.0)
                c_attempts = item.get("attempts_count", 0)
                c_ctx = item.get("last_context", "")

                label_tuple = status_labels.get(c_status, ("⚪ Non évalué", "⚪ لم يُقيّم", "⚪ Untested"))
                badge_str = label_tuple[1] if is_ar else (label_tuple[2] if is_en else label_tuple[0])

                with st.container(border=True):
                    col_title, col_badge = st.columns([0.72, 0.28], vertical_alignment="center")
                    with col_title:
                        st.markdown(f"**{idx + 1}. {c_title}**")
                        if c_ctx:
                            st.caption(c_ctx)
                    with col_badge:
                        st.markdown(f"<div style='text-align: right; font-weight: 600;'>{badge_str}</div>", unsafe_allow_html=True)
                        if c_attempts > 0:
                            st.caption(f"Score : {c_rate}% ({c_attempts} test{'s' if c_attempts > 1 else ''})")

                    # Bouton d'action directe vers Sanad
                    col_act1, col_act2 = st.columns([0.5, 0.5])
                    with col_act1:
                        btn_ask_sanad = "💬 Réviser avec Sanad" if not is_ar else "💬 راجع مع سند"
                        if st.button(btn_act_label := (btn_ask_sanad if not is_en else "💬 Study with Sanad"), key=f"btn_sanad_concept_{idx}_{current_course['id']}", use_container_width=True):
                            if is_ar:
                                prompt_text = f"اشرح لي من فضلك مفهوم '{c_title}' في درس {current_course['title']} واطرح علي سؤالاً بسيطاً لأتأكد من فهمي له."
                            elif is_en:
                                prompt_text = f"Please explain the concept '{c_title}' from the lesson {current_course['title']} and give me a concrete example or guiding question."
                            else:
                                prompt_text = f"Peux-tu m'expliquer clairement la notion '{c_title}' du cours {current_course['title']} et me donner un exemple concret avec une petite question d'entraînement ?"
                            st.session_state[f"sanad_quick_prompt_{current_course['id']}"] = prompt_text
                            st.success("Question envoyée à Sanad ! Rendez-vous sur l'onglet 🤖 Tuteur Virtuel pour voir sa réponse." if not is_en else "Sent to Sanad! Switch to the 🤖 Tutor tab to see his guidance.")

                    with col_act2:
                        btn_quiz_link = "🎯 S'entraîner (Quiz)" if not is_ar else "🎯 تدرب على الأسئلة"
                        if st.button(btn_quiz_link if not is_en else "🎯 Practice Quiz", key=f"btn_quiz_concept_{idx}_{current_course['id']}", use_container_width=True):
                            st.info("Rendez-vous sur l'onglet 📝 Entraînement Examen pour tester vos connaissances !" if not is_en else "Go to the 📝 Exam Quiz tab to practice!")

            st.write("")
            refresh_label = "🔄 Actualiser le diagnostic d'assimilation" if not is_ar else ("🔄 تحديث تشخيص الاستيعاب" if is_ar else "🔄 Refresh Mastery Diagnostic")
            if st.button(refresh_label, key=f"btn_sync_mastery_{current_course['id']}"):
                evaluate_and_sync_concept_mastery(active_user_id, current_course["id"])
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
                        evaluate_and_sync_concept_mastery(active_user_id, current_course["id"])
                        new_badges = evaluate_and_award_course_badges(active_user_id, current_course["id"])
                        try:
                            auto_backup_on_change(logged_in_user_id)
                        except Exception as _e_bk_q:
                            logger.debug(f"Auto-backup post quiz error: {_e_bk_q}")
                        if new_badges:
                            st.session_state["pending_trophy_celebration"] = {
                                "course_title": current_course["title"],
                                "badges": new_badges,
                            }
                        st.session_state[submission_key] = True
                        st.rerun()
                else:
                    celebration = st.session_state.pop("pending_trophy_celebration", None)
                    if celebration:
                        c_badges = celebration.get("badges", [])
                        c_title = celebration.get("course_title", "")
                        st.balloons()
                        # Lecture de la fanfare royale triomphante
                        st.components.v1.html(
                            generate_trophy_celebration_html(
                                auto_play=True,
                                widget_id=f"quiz_cel_{current_course['id']}_{int(time.time() * 1000)}",
                            ),
                            height=0,
                        )
                        for nb in c_badges:
                            st.toast(f"🎉 Nouveau trophée débloqué sur {c_title} : {nb['icon']} {nb['title']} !", icon="🏆")

                        badges_str = " &bull; ".join([f"{b['icon']} <strong>{b['title']}</strong>" for b in c_badges])
                        st.markdown(
                            f"""
                            <div style="background: linear-gradient(135deg, rgba(245, 158, 11, 0.22) 0%, rgba(180, 83, 9, 0.18) 100%); border: 1.5px solid #f59e0b; border-radius: 12px; padding: 14px 18px; margin-bottom: 16px; box-shadow: 0 4px 15px rgba(245, 158, 11, 0.25);">
                                <div style="font-size: 1.05rem; font-weight: 800; color: #fbbf24;">
                                    🏆 Félicitations ! Nouveau(x) trophée(s) conquis :
                                </div>
                                <div style="margin-top: 4px; color: #fef08a; font-size: 0.95rem;">
                                    {badges_str}
                                </div>
                            </div>
                            """,
                            unsafe_allow_html=True,
                        )

                    score = sum(1 for idx, q in enumerate(questions) if answers_chosen.get(idx) == q.get("answer_index", 0))
                    score_txt = f"### Score obtenu : **{score} / {len(questions)}**" if not is_en else f"### Score: **{score} / {len(questions)}**"
                    st.markdown(score_txt)
                    if score >= len(questions) * 0.8 and not celebration:
                        st.balloons()

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

            if is_ar:
                st.markdown("<div class='rtl-section-title'>🤖 الأستاذ المساعد : سَنَد</div>", unsafe_allow_html=True)
                st.caption(f"مرافقك الذكي بالمنهج السقراطي لمستوى {active_cycle['cycle_name']} ({active_cycle['age']} سنة) — يرشدك خطوة بخطوة دون إعطاء الحلول الجاهزة!")
            elif is_en:
                st.markdown("### 🤖 Socratic AI Tutor: Sanad")
                st.caption(f"Your mentor for {active_cycle['cycle_name']} ({active_cycle['age']} yo) — Socratic guidance step-by-step!")
            else:
                st.markdown("### 🤖 Tuteur Virtuel : Sanad")
                st.caption(f"Ton Grand Frère & Mentor pour le niveau {active_cycle['cycle_name']} ({active_cycle['age']} ans) — Méthode socratique : il te guide sans faire les exercices à ta place !")

            # Barre de contrôle audio ergonomique (Desktop & Mobile)
            col_v_toggle, col_v_speed = st.columns([0.62, 0.38], vertical_alignment="center")
            with col_v_toggle:
                auto_speak = st.toggle(
                    "🔊 Lecture vocale automatique des réponses" if not is_en else ("🔊 Auto-speak Sanad answers" if is_en else "🔊 قراءة صوتية تلقائية للردود"),
                    value=stored_auto_speak,
                    key=f"auto_speak_toggle_{current_course['id']}",
                    help="Sanad lit automatiquement ses réponses à voix haute dès qu'il vous répond (100% gratuit, 0 quota Gemini).",
                )
                if auto_speak != stored_auto_speak:
                    set_user_setting(active_user_id, "auto_speak_sanad", "true" if auto_speak else "false")

            with col_v_speed:
                with st.popover("⚙️ Vitesse & Réglages vocaux" if not is_en else ("⚙️ Voice Settings" if is_en else "⚙️ إعدادات الصوت"), use_container_width=True):
                    voice_speed = st.select_slider(
                        "Vitesse de lecture :" if not is_en else ("Voice Speed:" if is_en else "سرعة النطق :"),
                        options=[0.8, 0.9, 1.0, 1.1, 1.2],
                        value=stored_speed if stored_speed in [0.8, 0.9, 1.0, 1.1, 1.2] else 1.0,
                        format_func=lambda x: f"{x}x" + (" (Douce)" if x < 1.0 else (" (Normale)" if x == 1.0 else " (Rapide)")),
                        key=f"voice_speed_slider_{current_course['id']}",
                    )
                    if voice_speed != stored_speed:
                        set_user_setting(active_user_id, "voice_speed_sanad", str(voice_speed))
                    st.caption(
                        "💡 **Zéro impact sur votre forfait Gemini :** La synthèse vocale et le micro fonctionnent directement dans votre navigateur grâce à la Web Speech API HTML5."
                        if not is_en
                        else (
                            "💡 **Zero impact on your Gemini quota:** Speech synthesis and voice typing run natively in your browser using the HTML5 Web Speech API."
                            if is_en
                            else "💡 **دون استهلاك رصيد Gemini :** قراءة النصوص وتسجيل الصوت يعملان محلياً في متصفحك عبر تقنية Web Speech API."
                        )
                    )

            # Suggestions de questions rapides en 1 clic adaptées à la langue et à l'âge
            sug_header = "**أسئلة سريعة بنقرة واحدة :**" if is_ar else ("**Quick 1-click questions:**" if is_en else "**Questions rapides en un clic :**")
            st.write(sug_header)
            sug_cols = st.columns(3)
            suggested_prompt = None
            quick_concept_prompt = st.session_state.pop(f"sanad_quick_prompt_{current_course['id']}", None)
            if quick_concept_prompt:
                suggested_prompt = quick_concept_prompt
            student_age = active_cycle.get("age", 14)

            if is_ar:
                if sug_cols[0].button("💡 اشرح لي ببساطة", key=f"sug_btn_1_{current_course['id']}", use_container_width=True):
                    suggested_prompt = f"اشْرَحْ لِي فِكْرَةَ هَذَا الدَّرْسِ بِبَسَاطَةٍ كَمَا لَوْ كَانَ عُمْرِي {student_age} سَنَةً."
                if sug_cols[1].button("⚠️ فخاخ الامتحان", key=f"sug_btn_2_{current_course['id']}", use_container_width=True):
                    suggested_prompt = "مَا هِيَ أَهَمُّ الفِخَاخِ وَالأَسْئِلَةِ المُفَخَّخَةِ الَّتِي يَضَعُهَا الأَسَاتِذَةُ فِي الامْتِحَانِ لِهَذَا الدَّرْسِ وَكَيْفَ أَتَجَنَّبُهَا؟"
                if sug_cols[2].button("❓ اختبر فهمي", key=f"sug_btn_3_{current_course['id']}", use_container_width=True):
                    suggested_prompt = "اطْرَحْ عَلَيَّ سُؤَالاً تَوْجِيهِياً لِاخْتِبَارِ فَهْمِي لِهَذَا الدَّرْسِ وَسَاعِدْنِي فِي الإِجَابَةِ عَنْهُ خُطْوَةً بِخُطْوَةٍ."
            elif is_en:
                if sug_cols[0].button("💡 Explain simply", key=f"sug_btn_1_{current_course['id']}", use_container_width=True):
                    suggested_prompt = f"Can you explain the main idea of this lesson using a simple real-life analogy adapted to a {student_age}-year-old student?"
                if sug_cols[1].button("⚠️ Exam pitfalls", key=f"sug_btn_2_{current_course['id']}", use_container_width=True):
                    suggested_prompt = "What are the common exam pitfalls and tricky questions on this topic, and how can I avoid them?"
                if sug_cols[2].button("❓ Ask me a question", key=f"sug_btn_3_{current_course['id']}", use_container_width=True):
                    suggested_prompt = "Ask me a guiding question to test my understanding, and guide me step-by-step."
            else:
                exam_term = "au brevet" if student_age <= 15 else "au bac"
                if sug_cols[0].button("💡 Explique-moi simplement", key=f"sug_btn_1_{current_course['id']}", use_container_width=True):
                    suggested_prompt = f"Peux-tu m'expliquer l'idée générale de ce cours avec une analogie simple de la vie courante adaptée à un élève de {student_age} ans ?"
                if sug_cols[1].button(f"⚠️ Pièges {exam_term}", key=f"sug_btn_2_{current_course['id']}", use_container_width=True):
                    suggested_prompt = f"Quels sont les pièges classiques posés à l'examen sur ce sujet et comment les éviter ?"
                if sug_cols[2].button("❓ Pose-moi une question", key=f"sug_btn_3_{current_course['id']}", use_container_width=True):
                    suggested_prompt = "Pose-moi une petite question pour tester si j'ai bien compris, et guide-moi pour répondre."

            history = get_chat_history(current_course["id"], user_id=active_user_id)
            trigger_auto_key = f"auto_speak_trigger_{current_course['id']}"
            has_auto_trigger = bool(st.session_state.get(trigger_auto_key))

            for i, msg in enumerate(history):
                role = msg["role"]
                content = msg["content"]
                with st.chat_message("user" if role == "user" else "assistant", avatar="🧑‍🎓" if role == "user" else "🤖"):
                    if role == "assistant":
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
                            compact=False,
                            auto_play=should_auto_play,
                        )

                        if is_ar:
                            st.markdown(f"<div class='rtl-box'>{content}</div>", unsafe_allow_html=True)
                        else:
                            st.markdown(content)

                        if tts_html:
                            st.components.v1.html(tts_html, height=42)
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
            prompt_to_send = user_input or suggested_prompt
            if prompt_to_send:
                if not user_api_key:
                    st.error("⚠️ Clé API Gemini requise pour échanger avec Sanad. Obtenez votre clé 100% gratuite sur [Google AI Studio](https://aistudio.google.com/) et activez-la dans **⚙️ Paramètres** ou la barre latérale." if not is_en else "⚠️ Gemini API key required to chat with Sanad. Get your free key on [Google AI Studio](https://aistudio.google.com/) and configure it in **⚙️ Settings** or the sidebar.")
                else:
                    add_chat_message(current_course["id"], "user", prompt_to_send, user_id=active_user_id)
                    with st.chat_message("user", avatar="🧑‍🎓"):
                        st.markdown(prompt_to_send)

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

        with tab_trophies:
            c_overview = get_course_trophies_overview(active_user_id, current_course["id"])
            c_unlocked = c_overview["unlocked_trophies"]
            c_total = c_overview["total_trophies"]
            c_rate = c_overview["completion_rate"]
            just_unlocked = c_overview.get("newly_awarded", [])

            # Célébration sonore et visuelle si un ou plusieurs trophées viennent d'être remportés
            if just_unlocked:
                st.balloons()
                st.components.v1.html(
                    generate_trophy_celebration_html(
                        auto_play=True,
                        widget_id=f"tab_trophies_cel_{current_course['id']}_{int(time.time() * 1000)}",
                    ),
                    height=0,
                )
                for nb in just_unlocked:
                    st.toast(f"🎉 Nouveau trophée débloqué : {nb['icon']} {nb['title']} !", icon="🏆")

            t_header_txt = (
                f"### 🏆 شارات وكؤوس الدرس — {current_course['title']}"
                if is_ar
                else (
                    f"### 🏆 Course Trophies — {current_course['title']}"
                    if is_en
                    else f"### 🏆 Trophées de la Leçon — {current_course['title']}"
                )
            )
            st.markdown(t_header_txt)
            banner_title = "لوحة تميز الدرس" if is_ar else ("Course Trophy Showcase" if is_en else "Vitrine d'Excellence du Cours")
            banner_sub = (
                f"حصلت على <strong>{c_unlocked} من أصل {c_total}</strong> شارات في هذا الدرس ({c_rate}%)."
                if is_ar
                else (
                    f"You have conquered <strong>{c_unlocked} out of {c_total}</strong> trophies on this lesson ({c_rate}%)."
                    if is_en
                    else f"Vous avez conquis <strong>{c_unlocked} sur {c_total}</strong> trophées sur cette leçon ({c_rate}%)."
                )
            )
            st.markdown(
                f"""
                <div style="background: linear-gradient(135deg, rgba(30, 41, 59, 0.95) 0%, rgba(15, 23, 42, 0.98) 100%); border: 1.5px solid #f59e0b; border-radius: 14px; padding: 16px 20px; margin-bottom: 20px; box-shadow: 0 4px 14px rgba(245, 158, 11, 0.2);">
                    <div style="display: flex; justify-content: space-between; align-items: center;">
                        <div>
                            <span style="font-size: 1.15rem; font-weight: 800; color: #fef08a;">{banner_title}</span>
                            <div style="color: #cbd5e1; font-size: 0.85rem; margin-top: 4px;">{banner_sub}</div>
                        </div>
                        <div style="font-size: 1.6rem; font-weight: 900; color: #fbbf24;">
                            {c_unlocked}/{c_total} 🎖️
                        </div>
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )
            st.progress(c_rate / 100.0)

            st.write("")
            render_magnificent_trophy_grid(c_overview.get("badges", []), cols_count=2)

    # -----------------------------------------------------------------------
    # GESTION & AJOUT DES COURS (ADMINISTRATEUR)
    # -----------------------------------------------------------------------
    elif menu in ("➕ Ajouter un Cours", "➕ Gestion & Ajout des Cours"):
        if is_admin and active_student_info:
            st.info(f"👀 **Espace de supervision :** Vous téléversez des supports pour l'élève **{active_student_info['name']}**.")
            target_ids = [active_user_id]
        elif is_global_admin_view:
            st.title("➕ Gestion & Ajout des Cours")
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
            active_u_dict = active_student_info if (is_admin and active_student_info) else current_user
            active_u_cycle = get_pedagogical_cycle(active_u_dict.get("age"), level=active_u_dict.get("level"))
            st.title(f"➕ Ajouter un Cours ({active_u_cycle.get('level', 'Mes Révisions')})")
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
                    if success_count > 0:
                        try:
                            auto_backup_on_change(logged_in_user_id)
                        except Exception as _e_bk_up:
                            logger.warning(f"Auto-backup post PDF ingest failed: {_e_bk_up}")
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
                            try:
                                auto_backup_on_change(logged_in_user_id)
                            except Exception as _e_bk_sync:
                                logger.warning(f"Auto-backup post Classroom sync failed: {_e_bk_sync}")
                        else:
                            st.error(sync_res["error"])
                render_classroom_credentials_instructions(expanded=False)

    # -----------------------------------------------------------------------
    # VUE ÉLÈVE : MES PROGRÈS
    # -----------------------------------------------------------------------
    elif menu == "📊 Mes Progrès":
        if is_admin and active_student_info:
            st.info(f"👀 **Espace de supervision :** Statistiques de l'élève **{active_student_info['name']}**.")

        active_u_dict = active_student_info if (is_admin and active_student_info) else current_user
        active_u_cycle = get_pedagogical_cycle(active_u_dict.get("age"), level=active_u_dict.get("level"))
        st.title(f"📊 Progression & Révisions — {active_u_cycle.get('level', 'Collège')}")

        trophies_ov = get_student_trophies_by_course(active_user_id)
        u_trophies = trophies_ov.get("unlocked_trophies", 0)
        tot_trophies = trophies_ov.get("total_trophies", 0)
        rate_trophies = trophies_ov.get("completion_rate", 0.0)
        rank_tag = trophies_ov.get("rank", "🥉 Apprenti")

        t_col1, t_col2 = st.columns([3, 1])
        with t_col1:
            st.markdown(f"### 🏆 Trophées par Cours : **{rank_tag}** ({u_trophies}/{tot_trophies} conquis — {rate_trophies}%)")
            st.progress(rate_trophies / 100.0)
        with t_col2:
            st.write("")
            st.caption("Consultez l'onglet **🏆 Mes Trophées** pour voir vos trophées leçon par leçon !")

        st.divider()

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
    # VUE ÉLÈVE : MES TROPHÉES PAR COURS & OBJECTIFS
    # -----------------------------------------------------------------------
    elif menu in ("🏆 Mes Trophées", "🏆 Trophées & Badges"):
        if is_admin and active_student_info:
            st.info(f"👀 **Espace de supervision :** Trophées et accomplissements de **{active_student_info['name']}**.")

        active_u_dict = active_student_info if (is_admin and active_student_info) else current_user
        active_u_cycle = get_pedagogical_cycle(active_u_dict.get("age"), level=active_u_dict.get("level"))
        st.title(f"🏆 Salle des Trophées par Cours — {active_u_cycle.get('level', 'Collège')}")
        st.markdown(
            "Chaque cours dispose de ses propres **8 défis d'excellence**. "
            "Explorez vos leçons, maîtrisez les notions et réussissez vos quiz pour débloquer toutes les couronnes !"
        )

        trophies_data = get_student_trophies_by_course(active_user_id)
        tot_c = trophies_data.get("total_courses", 0)
        tot_t = trophies_data.get("total_trophies", 0)
        unlocked_t = trophies_data.get("unlocked_trophies", 0)
        overall_rate = trophies_data.get("completion_rate", 0.0)
        rank_title = trophies_data.get("rank", "🥉 Apprenti Explorateur")
        rank_color = trophies_data.get("rank_color", "#f97316")
        rank_quote = trophies_data.get("rank_quote", "Chaque grand voyage commence par une première leçon !")

        # -------------------------------------------------------------------
        # HERO BANNER SOMPTUEUX & RANG D'EXCELLENCE
        # -------------------------------------------------------------------
        st.markdown(
            f"""
            <div style="background: linear-gradient(135deg, #090d16 0%, #1e1b4b 50%, #0f172a 100%); border: 1.8px solid #f59e0b; border-radius: 18px; padding: 22px 26px; margin-bottom: 24px; box-shadow: 0 10px 30px -5px rgba(245, 158, 11, 0.25); position: relative; overflow: hidden;">
                <div style="display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 14px;">
                    <div>
                        <div style="display: inline-block; background: rgba(245, 158, 11, 0.15); border: 1px solid {rank_color}; color: {rank_color}; padding: 4px 14px; border-radius: 20px; font-size: 0.82rem; font-weight: 800; margin-bottom: 8px; letter-spacing: 0.5px;">
                            {rank_title}
                        </div>
                        <div style="font-size: 1.55rem; font-weight: 900; color: #ffffff; letter-spacing: -0.5px;">
                            Salle Royale des Trophées
                        </div>
                        <div style="color: #cbd5e1; font-size: 0.9rem; margin-top: 4px;">
                            <em>"{rank_quote}"</em>
                        </div>
                    </div>
                    <div style="text-align: right;">
                        <div style="font-size: 2.2rem; font-weight: 900; color: #fbbf24; text-shadow: 0 0 12px rgba(251, 191, 36, 0.4);">
                            {unlocked_t} <span style="font-size: 1.2rem; color: #94a3b8; font-weight: 600;">/ {tot_t}</span> 🎖️
                        </div>
                        <div style="color: #94a3b8; font-size: 0.82rem; font-weight: 600;">
                            {tot_c} cours en apprentissage • {overall_rate}% accompli
                        </div>
                    </div>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        st.progress(overall_rate / 100.0)

        st.divider()

        if tot_c == 0:
            st.info("ℹ️ Aucun cours n'est actuellement disponible dans votre espace. Ajoutez ou synchronisez vos premiers cours pour commencer à débloquer vos trophées !")
        else:
            courses_list = trophies_data.get("courses_trophies", [])
            subjects = sorted(list({c["subject"] for c in courses_list if c.get("subject")}))

            # Filtres ergonomiques
            f_col1, f_col2, f_col3 = st.columns([1.5, 2.5, 1.5])
            with f_col1:
                subj_opts = ["Toutes les matières"] + subjects
                selected_subj = st.selectbox("Filtrer par matière :", options=subj_opts, key="trophy_subj_filter")
            with f_col2:
                filtered_by_subj = [c for c in courses_list if selected_subj == "Toutes les matières" or c["subject"] == selected_subj]
                course_opts = ["all"] + [c["course_id"] for c in filtered_by_subj]
                def _fmt_course(cid):
                    if cid == "all":
                        return f"📚 Tous les cours ({len(filtered_by_subj)} leçons)"
                    c_item = next((c for c in filtered_by_subj if c["course_id"] == cid), None)
                    if c_item:
                        return f"📘 {c_item['course_title']} ({c_item['unlocked_trophies']}/8 🏆)"
                    return str(cid)
                selected_cid = st.selectbox("Sélectionner la leçon :", options=course_opts, format_func=_fmt_course, key="trophy_course_filter")
            with f_col3:
                status_filter = st.selectbox("Affichage :", ["Tous les trophées", "✨ Débloqués uniquement", "🔒 En cours d'obtention"], key="trophy_status_filter")

            st.write("")

            if selected_cid != "all":
                target_course = next((c for c in filtered_by_subj if c["course_id"] == selected_cid), None)
                if target_course:
                    b_list = target_course.get("badges", [])
                    if status_filter == "✨ Débloqués uniquement":
                        b_list = [b for b in b_list if b["is_unlocked"]]
                    elif status_filter == "🔒 En cours d'obtention":
                        b_list = [b for b in b_list if not b["is_unlocked"]]

                    badge_cls = get_subject_badge_class(target_course["subject"])
                    st.markdown(
                        f"<div><span class='badge-subject {badge_cls}'>{target_course['subject']}</span> "
                        f"<span style='font-size: 1.35rem; font-weight: 800; color: #f8fafc; margin-left: 8px;'>{target_course['course_title']}</span> "
                        f"— <strong>{target_course['unlocked_trophies']}/8 trophées débloqués</strong> ({target_course['completion_rate']}%)</div>",
                        unsafe_allow_html=True,
                    )
                    st.progress(target_course["completion_rate"] / 100.0)
                    st.write("")
                    render_magnificent_trophy_grid(b_list, cols_count=2)
            else:
                for idx, c in enumerate(filtered_by_subj):
                    b_list = c.get("badges", [])
                    if status_filter == "✨ Débloqués uniquement":
                        b_list = [b for b in b_list if b["is_unlocked"]]
                    elif status_filter == "🔒 En cours d'obtention":
                        b_list = [b for b in b_list if not b["is_unlocked"]]

                    expander_title = (
                        f"📘 {c['course_title']} ({c['subject']}) — "
                        f"{c['unlocked_trophies']}/8 🏆 Débloqués ({c['completion_rate']}%)"
                    )
                    with st.expander(expander_title, expanded=(idx < 2)):
                        st.progress(c["completion_rate"] / 100.0)
                        st.write("")
                        render_magnificent_trophy_grid(b_list, cols_count=2)

    # -----------------------------------------------------------------------
    # VUE ÉLÈVE : PARAMÈTRES INDIVIDUELS & SAUVEGARDE ÉLÈVE
    # -----------------------------------------------------------------------
    elif menu in ("⚙️ Paramètres & Sauvegardes", "⚙️ Sauvegardes & Paramètres de l'élève"):
        if is_admin and active_student_info:
            st.info(f"👀 **Espace de supervision :** Paramètres et sauvegarde de **{active_student_info['name']}**.")

        st.title("⚙️ Paramètres & Sauvegardes Personnelles")

        # -------------------------------------------------------------------
        # 1. PROFIL DE L'APPRENANT : NOM, ÂGE & NIVEAU SCOLAIRE
        # -------------------------------------------------------------------
        st.markdown("### 👤 Mon Profil & Niveau Scolaire")
        st.markdown(
            "Indiquez votre nom d'affichage, votre âge et votre niveau scolaire marocain. "
            "L'intelligence artificielle Sanad adapte automatiquement ses explications, "
            "ses résumés et la difficulté de ses quiz à votre niveau (Primaire, Collège, Lycée ou Supérieur/Adulte)."
        )

        target_user = active_student_info if (is_admin and active_student_info) else current_user
        current_name = target_user.get("name") or ""
        current_age = int(target_user.get("age") or 14)
        current_level = target_user.get("level") or "3AC"

        col_p1, col_p2, col_p3, col_p4 = st.columns([2.5, 1.2, 1.8, 1.5])
        with col_p1:
            new_prof_name = st.text_input("Nom d'affichage :", value=current_name, key="prof_edit_name_input")
        with col_p2:
            new_prof_age = st.number_input("Âge de l'élève :", min_value=5, max_value=99, value=current_age, key="prof_edit_age_input")
        with col_p3:
            lvl_opts = MOROCCAN_SCHOOL_LEVELS
            cur_lvl_idx = lvl_opts.index(current_level) if current_level in lvl_opts else (lvl_opts.index("3AC") if "3AC" in lvl_opts else 0)
            new_prof_level = st.selectbox("Niveau scolaire :", options=lvl_opts, index=cur_lvl_idx, key="prof_edit_level_input")
        with col_p4:
            st.write("")
            st.write("")
            save_prof_btn = st.button("💾 Mettre à jour mon profil", type="primary", use_container_width=True, key="btn_save_prof_settings")

        ped_cycle = get_pedagogical_cycle(int(new_prof_age), level=new_prof_level)
        st.info(f"🎯 **Niveau & Cycle :** {ped_cycle['cycle_name']} ({ped_cycle['level']}) — *Style d'apprentissage : {ped_cycle['tone']}*")

        if save_prof_btn:
            ok_name, msg_name = update_user_name(active_user_id, new_prof_name)
            ok_age, msg_age = update_user_age(active_user_id, int(new_prof_age))
            ok_lvl, msg_lvl = update_user_level(active_user_id, new_prof_level)
            if ok_name and ok_age and ok_lvl:
                if active_user_id == logged_in_user_id:
                    st.session_state["name"] = new_prof_name
                    if "user" in st.session_state and isinstance(st.session_state["user"], dict):
                        st.session_state["user"]["name"] = new_prof_name
                        st.session_state["user"]["age"] = int(new_prof_age)
                        st.session_state["user"]["level"] = new_prof_level
                st.success("Profil mis à jour avec succès ! Les contenus générés par l'IA s'adapteront à votre niveau scolaire.")
                st.rerun()
            else:
                st.error(f"{msg_name} {msg_age} {msg_lvl}")

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

        st.markdown("### 🎙️ Voix de Sanad & Dictée Vocale")
        st.markdown(
            "Le tuteur socratique Sanad peut lire ses explications à voix haute et vous permettre de lui parler au micro. "
            "Cette technologie s'exécute avec **0 jeton consommé sur votre quota Gemini (100% gratuit)** : "
            "synthèse audio haute qualité générée côté serveur sous Linux via gTTS, et via la Web Speech API native sur les autres appareils (Windows, Mac, smartphones)."
        )
        col_test_v1, col_test_v2, col_test_v3 = st.columns(3)
        with col_test_v1:
            st.markdown("**🇫🇷 Voix Française :**")
            test_fr_html = generate_tts_player_html(
                "Bonjour ! Je suis Sanad, ton tuteur personnel. Prêt pour les révisions ?",
                language="fr",
                player_id="test_voice_fr",
                compact=False,
            )
            st.components.v1.html(test_fr_html, height=42)
        with col_test_v2:
            st.markdown("**🇲🇦 Voix Arabe (العربية مع الحركات) :**")
            test_ar_html = generate_tts_player_html(
                "مَرْحَباً بِكَ ! أَنَا الأُسْتَاذُ سَنَد، رَفِيقُكَ فِي الدِّرَاسَةِ وَالمُرَاجَعَةِ.",
                language="ar",
                player_id="test_voice_ar",
                compact=False,
            )
            st.components.v1.html(test_ar_html, height=42)
        with col_test_v3:
            st.markdown("**🇬🇧 Voix Anglaise (English) :**")
            test_en_html = generate_tts_player_html(
                "Hello! I am Sanad, your personal study tutor. Ready to practice?",
                language="en",
                player_id="test_voice_en",
                compact=False,
            )
            st.components.v1.html(test_en_html, height=42)

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
