"""
Ecole Adnane - Application Web Multi-Utilisateurs de Révision & Préparation aux Examens 3AC (Maroc)
100% Python propulsée par Streamlit, SQLite et Google Gemini.
Supporte Google OAuth, premier connecté = Admin, cloisonnement strict par élève,
sauvegardes étanches et intégration Google Classroom.
"""

import base64
import html
import json
import logging
import os
import re
import shutil
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

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
        or not hasattr(models.database, "get_student_ranks")
        or not hasattr(models.database, "has_user_completed_quiz")
        or not hasattr(models.database, "mark_concept_mastered_by_sanad")
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
        get_db_path,
        get_global_admin_kpis,
        get_latest_quiz,
        has_user_completed_quiz,
        get_pedagogical_cycle,
        get_quiz_stats,
        get_student_concept_mastery,
        get_student_rank,
        get_student_ranks,
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
        mark_concept_mastered_by_sanad,
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
        get_course_animation,
        save_course_animation,
        get_course_story_scenario,
        save_course_story_scenario,
        get_course_story_pdf,
        save_course_story_pdf,
        get_course_explanatory_guide,
        save_course_explanatory_guide,
        get_course_explanatory_guide_pdf,
        save_course_explanatory_guide_pdf,
        ensure_course_pdf_on_disk,
        is_user_openrouter_allowed,
        set_user_openrouter_access,
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
        get_db_path,
        get_global_admin_kpis,
        get_latest_quiz,
        has_user_completed_quiz,
        get_pedagogical_cycle,
        get_quiz_stats,
        get_student_concept_mastery,
        get_student_rank,
        get_student_ranks,
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
        mark_concept_mastered_by_sanad,
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
        get_course_animation,
        save_course_animation,
        get_course_story_scenario,
        save_course_story_scenario,
        get_course_story_pdf,
        save_course_story_pdf,
        get_course_explanatory_guide,
        save_course_explanatory_guide,
        get_course_explanatory_guide_pdf,
        save_course_explanatory_guide_pdf,
        ensure_course_pdf_on_disk,
        is_user_openrouter_allowed,
        set_user_openrouter_access,
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
        diacritize_arabic_text,
        generate_course_mindmap,
        generate_quiz,
        generate_revision_sheet,
        get_arabic_tashkeel_ratio,
        socratic_tutor_response,
        transcribe_audio_with_ai,
        generate_course_animation_simulation,
    )
except ImportError:
    import services.ai_engine
    services.ai_engine = importlib.reload(services.ai_engine)
    from services.ai_engine import (
        classify_and_extract_metadata,
        clean_interactive_mindmap_markdown,
        clean_mermaid_mindmap,
        convert_mermaid_to_markdown,
        diacritize_arabic_text,
        generate_course_mindmap,
        generate_quiz,
        generate_revision_sheet,
        get_arabic_tashkeel_ratio,
        socratic_tutor_response,
        transcribe_audio_with_ai,
        generate_course_animation_simulation,
    )
from services.story_engine import (
    generate_course_story_scenario,
    build_story_pdf_and_viewer,
    generate_complete_story_and_pdf,
)
from services.explanatory_guide_engine import (
    generate_course_explanatory_guide_deck,
    build_explanatory_guide_pdf_and_viewer,
    generate_complete_explanatory_guide,
    detect_subject_theme,
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
    get_openrouter_api_key,
    save_openrouter_api_key,
    get_openrouter_model,
    save_openrouter_model,
    test_openrouter_connection,
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
    if not hasattr(services.voice_manager, "generate_fiche_audio_player_html"):
        services.voice_manager = importlib.reload(services.voice_manager)
    from services.voice_manager import (
        clean_text_for_speech,
        generate_chat_mic_injector_html,
        generate_fiche_audio_player_html,
        generate_mic_speech_html,
        generate_or_get_course_fiche_mp3,
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
        generate_fiche_audio_player_html,
        generate_mic_speech_html,
        generate_or_get_course_fiche_mp3,
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

from models.database import get_student_study_overview

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
def get_custom_css(theme: str = "dark") -> str:
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

    is_dark = (theme != "light")

    if is_dark:
        palette_vars = """
    --ea-bg: #0d131c;
    --ea-bg-gradient: linear-gradient(180deg, #101824 0%, #0d131c 100%);
    --ea-surface: #151d2a;
    --ea-surface-hover: #1c2737;
    --ea-surface-card: #151d2a;
    --ea-border: rgba(200, 196, 180, 0.12);
    --ea-border-hover: rgba(91, 141, 239, 0.55);
    --ea-primary: #4f7fd9;
    --ea-primary-hover: #6290e6;
    --ea-primary-glow: rgba(79, 127, 217, 0.25);
    --ea-text: #cfcbbf;
    --ea-text-muted: #98978c;
    --ea-text-dim: #75756c;
    --ea-card-bg: #151d2a;
    --ea-card-shadow: 0 6px 20px -6px rgba(0, 0, 0, 0.45);
    --ea-input-bg: #182130;
    --ea-input-border: rgba(200, 196, 180, 0.18);
    --ea-tablist-bg: #131a26;
    --ea-tab-color: #98978c;
    --ea-sidebar-bg: #0a1018;
    --ea-sidebar-text: #cfcbbf;
    --ea-sidebar-border: rgba(200, 196, 180, 0.1);
    --ea-hero-bg: #151d2a;
    --ea-hero-title: #dcd6c4;
    --ea-hero-desc: #98978c;
    --ea-hero-badge-bg: rgba(79, 127, 217, 0.14);
    --ea-hero-badge-color: #93b8f7;
    --ea-hero-badge-border: rgba(79, 127, 217, 0.35);
    --ea-btn-sec-bg: #182130;
    --ea-btn-sec-border: rgba(200, 196, 180, 0.18);
    --ea-btn-sec-color: #cfcbbf;
    --ea-btn-sec-hover: #202c3d;
    --ea-trap-bg: rgba(184, 150, 80, 0.09);
    --ea-trap-color: #dccfa8;
    --ea-expl-bg: rgba(74, 140, 105, 0.10);
    --ea-expl-color: #b9d6c6;
    --ea-quiz-bg: #151d2a;
    --ea-quiz-badge: #93b8f7;
    --ea-emerald: #4a946e;
    --ea-amber: #6d96e0;
    --ea-rose: #c45c66;
    --ea-indigo: #6f86b8;
    --ea-purple: #8e7bb0;
    --ea-cyan: #5aa0b0;
    --ea-on-primary: #f1f5f9;
        """
    else:
        palette_vars = """
    --ea-bg: #f6f3eb;
    --ea-bg-gradient: linear-gradient(180deg, #f9f7f1 0%, #f3efe4 100%);
    --ea-surface: #fffefb;
    --ea-surface-hover: #f3ecda;
    --ea-surface-card: #fffefb;
    --ea-border: #e2d8bf;
    --ea-border-hover: #1e3a5f;
    --ea-primary: #1e3a5f;
    --ea-primary-hover: #162c48;
    --ea-primary-glow: rgba(30, 58, 95, 0.14);
    --ea-text: #1f2430;
    --ea-text-muted: #5b6070;
    --ea-text-dim: #8a8d98;
    --ea-card-bg: #fffefb;
    --ea-card-shadow: 0 2px 10px rgba(60, 48, 20, 0.07), 0 1px 2px rgba(60, 48, 20, 0.05);
    --ea-input-bg: #ffffff;
    --ea-input-border: #d6cba9;
    --ea-tablist-bg: #efe8d3;
    --ea-tab-color: #5b6070;
    --ea-sidebar-bg: #efeadc;
    --ea-sidebar-text: #1f2430;
    --ea-sidebar-border: #ddd2b4;
    --ea-hero-bg: #fffefb;
    --ea-hero-title: #1e3a5f;
    --ea-hero-desc: #5b6070;
    --ea-hero-badge-bg: rgba(30, 58, 95, 0.07);
    --ea-hero-badge-color: #1e3a5f;
    --ea-hero-badge-border: rgba(30, 58, 95, 0.22);
    --ea-btn-sec-bg: #fffefb;
    --ea-btn-sec-border: #cfc3a0;
    --ea-btn-sec-color: #1e3a5f;
    --ea-btn-sec-hover: #f3ecda;
    --ea-trap-bg: #fbf1d6;
    --ea-trap-color: #5c4310;
    --ea-expl-bg: #e8f2ea;
    --ea-expl-color: #1f4733;
    --ea-quiz-bg: #fffefb;
    --ea-quiz-badge: #1e3a5f;
    --ea-emerald: #2f7a54;
    --ea-amber: #a87a1c;
    --ea-rose: #a23b48;
    --ea-indigo: #3b5a94;
    --ea-purple: #6a4c93;
    --ea-cyan: #2f7f8f;
    --ea-on-primary: #ffffff;
        """

    dark_extra = ""
    if is_dark:
        dark_extra = """
/* Dark mode: native canvas widgets (dataframes) follow the dark palette */
[data-testid="stDataFrame"], [data-testid="stTable"] { filter: invert(0.90) saturate(0.15) brightness(0.92) contrast(1.02); border-radius: 10px; }
.st-emotion-cache-nnnnl0, .st-emotion-cache-nnnnl0 * { color: #e2e8f0 !important; -webkit-text-fill-color: #e2e8f0 !important; }
"""
    return f"""
<style>
{font_faces}

@import url('https://fonts.googleapis.com/css2?family=Source+Sans+3:wght@400;500;600;700&family=Source+Serif+4:wght@600;700&family=Cairo:wght@500;600;700;800;900&family=Amiri:wght@400;700&family=Tajawal:wght@500;700;800&display=swap');

:root {{
{palette_vars}
    --ea-radius-sm: 8px;
    --ea-radius-md: 14px;
    --ea-radius-lg: 20px;
    --ea-radius-full: 9999px;
}}

/* Streamlit Chrome Overhaul & Resets */
header[data-testid="stHeader"] {{
    background: transparent !important;
    backdrop-filter: none !important;
    -webkit-backdrop-filter: none !important;
    pointer-events: none !important;
}}

.block-container {{
    padding-top: 3.5rem !important;
    padding-bottom: 3.5rem !important;
    max-width: 1260px !important;
}}

/* Sidebar Toggle Controls (Re-open & Collapse) */
[data-testid="stExpandSidebarButton"],
[data-testid="stSidebarCollapseButton"],
[data-testid="collapsedControl"] {{
    display: inline-flex !important;
    visibility: visible !important;
    opacity: 1 !important;
    pointer-events: auto !important;
    cursor: pointer !important;
    z-index: 999999 !important;
}}

[data-testid="stExpandSidebarButton"],
[data-testid="collapsedControl"] {{
    position: fixed !important;
    top: 14px !important;
    left: 14px !important;
    background: var(--ea-surface) !important;
    border: 1.5px solid var(--ea-border) !important;
    border-radius: 10px !important;
    padding: 8px 12px !important;
    box-shadow: 0 4px 16px rgba(0, 0, 0, 0.3) !important;
    color: var(--ea-text) !important;
    transition: all 0.2s cubic-bezier(0.16, 1, 0.3, 1) !important;
}}

[data-testid="stExpandSidebarButton"]:hover,
[data-testid="collapsedControl"]:hover {{
    background: var(--ea-surface-hover) !important;
    border-color: var(--ea-primary) !important;
    transform: scale(1.08) !important;
    box-shadow: 0 6px 20px var(--ea-primary-glow) !important;
}}

[data-testid="stExpandSidebarButton"] svg,
[data-testid="collapsedControl"] svg {{
    color: var(--ea-primary) !important;
    fill: var(--ea-primary) !important;
}}

/* Keep Toolbar visible strictly for expand button, hide developer/deploy elements */
[data-testid="stToolbar"] {{
    background: transparent !important;
    visibility: visible !important;
    display: flex !important;
    pointer-events: none !important;
}}

[data-testid="stToolbar"] > * {{
    pointer-events: auto !important;
}}

#MainMenu, footer,
[data-testid="stToolbar"] [data-testid="manage-app-button"],
[data-testid="stToolbarActionButtons"] {{
    visibility: hidden !important;
    display: none !important;
}}

/* Base Typography & Antialiasing */
html, body, .stApp {{
    background: var(--ea-bg-gradient) !important;
    background-color: var(--ea-bg) !important;
    color: var(--ea-text) !important;
    font-family: 'Source Sans 3', system-ui, -apple-system, sans-serif;
    -webkit-font-smoothing: antialiased;
    -moz-osx-font-smoothing: grayscale;
}}

[data-testid="stMarkdownContainer"] p,
[data-testid="stMarkdownContainer"] span,
[data-testid="stMarkdownContainer"] li,
div[role="tablist"] button,
button, input, select, textarea, label,
[data-testid="stExpander"], [data-testid="stRadio"] {{
    font-family: 'Source Sans 3', 'AdnaneNaskh', 'Cairo', system-ui, sans-serif;
}}

/* Headings with Modern EdTech hierarchy */
h1, h2, h3, h4, h5, h6 {{
    font-family: 'Source Sans 3', 'AdnaneSans', 'Cairo', sans-serif !important;
    letter-spacing: -0.025em !important;
    font-weight: 800 !important;
    color: var(--ea-text) !important;
}}

/* Arabic RTL Typography */
.rtl-box {{
    direction: rtl !important;
    text-align: right !important;
    font-family: 'AdnaneNaskh', 'Noto Naskh Arabic', 'Amiri', serif !important;
    font-size: 1.25rem !important;
    line-height: 2.2 !important;
    letter-spacing: 0 !important;
    color: var(--ea-text) !important;
}}

.rtl-box h1, .rtl-box h2, .rtl-box h3, .rtl-box h4 {{
    font-family: 'Cairo', 'AdnaneSans', 'Tajawal', sans-serif !important;
    text-align: right !important;
    direction: rtl !important;
    font-weight: 800 !important;
    color: var(--ea-text) !important;
    margin-top: 1.3rem !important;
    margin-bottom: 0.6rem !important;
    line-height: 1.6 !important;
}}

.rtl-box p, .rtl-box li {{
    font-family: 'AdnaneNaskh', 'Noto Naskh Arabic', serif !important;
    font-size: 1.22rem !important;
    line-height: 2.2 !important;
    color: var(--ea-text) !important;
}}

.rtl-box strong {{
    font-family: 'Cairo', 'AdnaneSans', sans-serif !important;
    font-weight: 700 !important;
    color: var(--ea-primary) !important;
}}

.rtl-section-title {{
    direction: rtl !important;
    text-align: right !important;
    font-family: 'Cairo', 'AdnaneSans', sans-serif !important;
    font-size: 1.6rem !important;
    font-weight: 800 !important;
    color: var(--ea-text) !important;
    margin-top: 14px;
    margin-bottom: 12px;
    line-height: 1.5 !important;
}}

/* Modern Glassmorphic / Solid Sidebar */
[data-testid="stSidebar"] {{
    background-color: var(--ea-sidebar-bg) !important;
    border-right: 1px solid var(--ea-sidebar-border) !important;
}}

[data-testid="stSidebar"] [data-testid="stMarkdownContainer"] h2 {{
    color: var(--ea-sidebar-text) !important;
    font-size: 1.35rem !important;
    font-weight: 800 !important;
    letter-spacing: -0.02em !important;
    display: flex;
    align-items: center;
    gap: 8px;
}}

[data-testid="stSidebar"] label,
[data-testid="stSidebar"] p,
[data-testid="stSidebar"] span {{
    color: var(--ea-sidebar-text) !important;
}}

/* Sidebar Student Profile Card */
.sidebar-profile-card {{
    background: var(--ea-surface) !important;
    border: 1px solid var(--ea-border);
    border-radius: var(--ea-radius-md);
    padding: 16px;
    margin-bottom: 14px;
    box-shadow: var(--ea-card-shadow);
}}

.profile-avatar-row {{
    display: flex;
    align-items: center;
    gap: 12px;
    margin-bottom: 10px;
}}

.profile-avatar-circle {{
    width: 44px;
    height: 44px;
    border-radius: 50%;
    background: linear-gradient(135deg, #3b82f6 0%, #8b5cf6 100%);
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 1.3rem;
    font-weight: 800;
    color: #ffffff;
    box-shadow: 0 4px 14px rgba(59, 130, 246, 0.4);
}}

.profile-name-text {{
    font-size: 1.05rem;
    font-weight: 700;
    color: var(--ea-sidebar-text) !important;
    line-height: 1.2;
}}

.profile-email-text {{
    font-size: 0.78rem;
    color: var(--ea-text-muted);
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
    max-width: 175px;
}}

.profile-badges-row {{
    display: flex;
    flex-wrap: wrap;
    gap: 6px;
    align-items: center;
    margin-top: 8px;
}}

.profile-pill-cycle {{
    background: rgba(59, 130, 246, 0.15);
    color: #93c5fd;
    border: 1px solid rgba(59, 130, 246, 0.3);
    border-radius: 12px;
    font-size: 0.75rem;
    font-weight: 700;
    padding: 2px 10px;
}}

.profile-pill-rank {{
    background: rgba(245, 158, 11, 0.15);
    color: #fde047;
    border: 1px solid rgba(245, 158, 11, 0.3);
    border-radius: 12px;
    font-size: 0.75rem;
    font-weight: 700;
    padding: 2px 10px;
}}

/* Pulsing AI Online Indicator */
.ai-status-pill {{
    display: flex;
    align-items: center;
    gap: 8px;
    background: rgba(16, 185, 129, 0.12);
    border: 1px solid rgba(16, 185, 129, 0.28);
    border-radius: 20px;
    padding: 6px 14px;
    font-size: 0.82rem;
    font-weight: 600;
    color: #6ee7b7;
    margin-bottom: 12px;
}}

.ai-pulse-dot {{
    width: 8px;
    height: 8px;
    border-radius: 50%;
    background-color: #10b981;
    box-shadow: 0 0 0 rgba(16, 185, 129, 0.6);
    animation: pulseDot 2s infinite;
}}

@keyframes pulseDot {{
    0% {{ box-shadow: 0 0 0 0 rgba(16, 185, 129, 0.7); }}
    70% {{ box-shadow: 0 0 0 7px rgba(16, 185, 129, 0); }}
    100% {{ box-shadow: 0 0 0 0 rgba(16, 185, 129, 0); }}
}}

/* Sidebar Modern Navigation Menu (SaaS Nav list, zero radio appearance) */
[data-testid="stSidebar"] [data-testid="stRadio"] {{
    background: transparent !important;
    border: none !important;
    padding: 0 !important;
}}

[data-testid="stSidebar"] [data-testid="stRadio"] > label {{
    display: none !important;
}}

/* Radio Group Vertical Container */
[data-testid="stSidebar"] [data-testid="stRadioGroup"],
[data-testid="stSidebar"] [data-testid="stRadio"] div[role="radiogroup"] {{
    gap: 6px !important;
    display: flex !important;
    flex-direction: column !important;
    background: transparent !important;
    border: none !important;
    padding: 0 !important;
}}

/* Radio Option Field Wrappers */
[data-testid="stSidebar"] [data-testid="stRadioGroup"] > div,
[data-testid="stSidebar"] [data-testid="stRadioGroup"] [class*="e1dm8mpf1"] {{
    margin: 0 !important;
    padding: 0 !important;
    border: none !important;
    background: transparent !important;
}}

/* Hide native radio circle bullets COMPLETELY across all Streamlit versions (1.65+ and legacy) */
[data-testid="stSidebar"] [class*="e1dm8mpf4"],
[data-testid="stSidebar"] [class*="e1dm8mpf5"],
[data-testid="stSidebar"] [data-testid="stRadioOption"] [class*="e1dm8mpf4"],
[data-testid="stSidebar"] [data-testid="stRadioOption"] [class*="e1dm8mpf5"],
[data-testid="stSidebar"] [data-testid="stRadioOption"] > div > div:first-child,
[data-testid="stSidebar"] [data-testid="stRadioOption"] input[type="radio"],
[data-testid="stSidebar"] [data-testid="stRadio"] div[role="radiogroup"] label > div:first-child,
[data-testid="stSidebar"] [data-testid="stRadio"] input[type="radio"] {{
    display: none !important;
    visibility: hidden !important;
    width: 0 !important;
    height: 0 !important;
    margin: 0 !important;
    padding: 0 !important;
    border: none !important;
    opacity: 0 !important;
    pointer-events: none !important;
    position: absolute !important;
}}

/* Style options as sleek SaaS nav items */
[data-testid="stSidebar"] [data-testid="stRadioOption"],
[data-testid="stSidebar"] [data-testid="stRadioGroup"] label,
[data-testid="stSidebar"] [data-testid="stRadio"] div[role="radiogroup"] label {{
    background: var(--ea-surface) !important;
    border: 1px solid var(--ea-border) !important;
    border-radius: 12px !important;
    padding: 10px 14px !important;
    margin: 0 0 6px 0 !important;
    cursor: pointer !important;
    display: flex !important;
    align-items: center !important;
    box-shadow: 0 1px 3px rgba(0, 0, 0, 0.04) !important;
    transition: all 0.2s cubic-bezier(0.16, 1, 0.3, 1) !important;
    user-select: none !important;
    width: 100% !important;
    box-sizing: border-box !important;
}}

/* Options inner row flex */
[data-testid="stSidebar"] [data-testid="stRadioOption"] > div,
[data-testid="stSidebar"] [data-testid="stRadioOption"] [class*="e1dm8mpf3"] {{
    display: flex !important;
    align-items: center !important;
    width: 100% !important;
    gap: 10px !important;
    cursor: pointer !important;
}}

/* Hover state */
[data-testid="stSidebar"] [data-testid="stRadioOption"]:hover,
[data-testid="stSidebar"] [data-testid="stRadioGroup"] label:hover,
[data-testid="stSidebar"] [data-testid="stRadio"] div[role="radiogroup"] label:hover {{
    background: var(--ea-surface-hover) !important;
    border-color: var(--ea-border-hover) !important;
    transform: translateX(4px) !important;
}}

/* Active / Selected Navigation Item */
[data-testid="stSidebar"] [data-testid="stRadioOption"][data-selected="true"],
[data-testid="stSidebar"] [data-testid="stRadioOption"][aria-checked="true"],
[data-testid="stSidebar"] [data-testid="stRadioOption"]:has(input:checked),
[data-testid="stSidebar"] [data-testid="stRadioGroup"] > div:has([data-selected="true"]) [data-testid="stRadioOption"],
[data-testid="stSidebar"] [data-testid="stRadio"] div[role="radiogroup"] label:has(input:checked) {{
    background: rgba(37, 99, 235, 0.12) !important;
    border: 1.5px solid var(--ea-primary) !important;
    border-left: 4px solid var(--ea-primary) !important;
    box-shadow: 0 4px 14px var(--ea-primary-glow) !important;
    transform: translateX(4px) !important;
}}

/* Sidebar Nav item text (always protected from RTL/Arabic overrides) */
[data-testid="stSidebar"] [data-testid="stRadioOption"] p,
[data-testid="stSidebar"] [data-testid="stRadioOption"] span,
[data-testid="stSidebar"] [data-testid="stRadioOption"] div[data-testid="stMarkdownContainer"] p,
[data-testid="stSidebar"] [data-testid="stRadioGroup"] label p,
[data-testid="stSidebar"] [data-testid="stRadio"] label p,
[data-testid="stSidebar"] [data-testid="stRadio"] label span {{
    font-size: 0.94rem !important;
    font-weight: 600 !important;
    color: var(--ea-text-muted) !important;
    margin: 0 !important;
    line-height: 1.35 !important;
    font-family: 'Source Sans 3', system-ui, -apple-system, sans-serif !important;
    direction: ltr !important;
    text-align: left !important;
    cursor: pointer !important;
    user-select: none !important;
}}

/* Active text styling */
[data-testid="stSidebar"] [data-testid="stRadioOption"][data-selected="true"] p,
[data-testid="stSidebar"] [data-testid="stRadioOption"][data-selected="true"] span,
[data-testid="stSidebar"] [data-testid="stRadioOption"]:has(input:checked) p,
[data-testid="stSidebar"] [data-testid="stRadioGroup"] > div:has([data-selected="true"]) p,
[data-testid="stSidebar"] [data-testid="stRadio"] label:has(input:checked) p {{
    color: var(--ea-primary) !important;
    font-weight: 700 !important;
}}

/* Universal Cursor Pointer & No-Text-Select on all Interactive Elements (Prevents I-beam cursor) */
[data-testid="stSidebar"] [data-testid="stRadioOption"],
[data-testid="stSidebar"] [data-testid="stRadioOption"] *,
[data-testid="stSidebar"] [data-testid="stRadio"] label,
[data-testid="stSidebar"] [data-testid="stRadio"] label *,
div[data-testid="stRadio"] label,
div[data-testid="stRadio"] label *,
[data-testid="stSegmentedControl"] button,
[data-testid="stSegmentedControl"] button *,
[data-testid="stPills"] button,
[data-testid="stPills"] button *,
div[role="tablist"] button,
div[role="tablist"] button *,
div[data-testid="stExpander"] summary,
div[data-testid="stExpander"] summary *,
div[data-testid="stVerticalBlockBorderWrapper"],
div[data-testid="stVerticalBlockBorderWrapper"] p,
div[data-testid="stVerticalBlockBorderWrapper"] span,
.ea-course-card, .ea-course-card *,
.badge-subject, .badge-lang, .concept-tag,
.ea-hero-badge-pill,
button, button * {{
    cursor: pointer !important;
    user-select: none !important;
}}

/* Horizontal Radios (Theme Toggle & Pill Switches) */
div[data-testid="stRadio"] div[role="radiogroup"][aria-orientation="horizontal"],
div[data-testid="stRadio"] [data-testid="stRadioGroup"][aria-orientation="horizontal"],
[data-testid="stSidebar"] [data-testid="stRadioGroup"][aria-orientation="horizontal"] {{
    display: flex !important;
    flex-direction: row !important;
    background: var(--ea-surface) !important;
    border: 1px solid var(--ea-border) !important;
    border-radius: 9999px !important;
    padding: 4px !important;
    gap: 4px !important;
    box-shadow: var(--ea-card-shadow) !important;
    width: 100% !important;
}}

div[data-testid="stRadio"] div[role="radiogroup"][aria-orientation="horizontal"] [data-testid="stRadioOption"],
div[data-testid="stRadio"] [data-testid="stRadioGroup"][aria-orientation="horizontal"] [data-testid="stRadioOption"],
[data-testid="stSidebar"] [data-testid="stRadioGroup"][aria-orientation="horizontal"] [data-testid="stRadioOption"],
div[data-testid="stRadio"] div[role="radiogroup"][aria-orientation="horizontal"] > label {{
    flex: 1 1 0 !important;
    border-radius: 9999px !important;
    padding: 6px 14px !important;
    margin: 0 !important;
    border: 1px solid transparent !important;
    cursor: pointer !important;
    display: inline-flex !important;
    align-items: center !important;
    justify-content: center !important;
    transition: all 0.2s cubic-bezier(0.4, 0, 0.2, 1) !important;
    transform: none !important;
}}

div[data-testid="stRadio"] [data-testid="stRadioGroup"][aria-orientation="horizontal"] [data-testid="stRadioOption"] [class*="e1dm8mpf4"],
div[data-testid="stRadio"] [data-testid="stRadioGroup"][aria-orientation="horizontal"] [data-testid="stRadioOption"] [class*="e1dm8mpf5"],
div[data-testid="stRadio"] [data-testid="stRadioGroup"][aria-orientation="horizontal"] [data-testid="stRadioOption"] > div > div:first-child,
div[data-testid="stRadio"] div[role="radiogroup"][aria-orientation="horizontal"] > label > div:first-child {{
    display: none !important;
}}

div[data-testid="stRadio"] [data-testid="stRadioGroup"][aria-orientation="horizontal"] [data-testid="stRadioOption"] p,
div[data-testid="stRadio"] div[role="radiogroup"][aria-orientation="horizontal"] > label div[data-testid="stMarkdownContainer"] p {{
    font-size: 0.85rem !important;
    font-weight: 600 !important;
    color: var(--ea-text-muted) !important;
    margin: 0 !important;
    text-align: center !important;
}}

div[data-testid="stRadio"] [data-testid="stRadioGroup"][aria-orientation="horizontal"] [data-testid="stRadioOption"]:hover,
div[data-testid="stRadio"] div[role="radiogroup"][aria-orientation="horizontal"] > label:hover {{
    background: var(--ea-surface-hover) !important;
}}

div[data-testid="stRadio"] [data-testid="stRadioGroup"][aria-orientation="horizontal"] [data-testid="stRadioOption"][data-selected="true"],
div[data-testid="stRadio"] [data-testid="stRadioGroup"][aria-orientation="horizontal"] [data-testid="stRadioOption"]:has(input:checked),
div[data-testid="stRadio"] div[role="radiogroup"][aria-orientation="horizontal"] > label:has(input:checked) {{
    background: var(--ea-primary) !important;
    box-shadow: 0 2px 10px rgba(37, 99, 235, 0.4) !important;
    border-left: 1px solid transparent !important;
    transform: none !important;
}}

div[data-testid="stRadio"] [data-testid="stRadioGroup"][aria-orientation="horizontal"] [data-testid="stRadioOption"][data-selected="true"] p,
div[data-testid="stRadio"] [data-testid="stRadioGroup"][aria-orientation="horizontal"] [data-testid="stRadioOption"]:has(input:checked) p,
div[data-testid="stRadio"] div[role="radiogroup"][aria-orientation="horizontal"] > label:has(input:checked) div[data-testid="stMarkdownContainer"] p {{
    color: #ffffff !important;
    font-weight: 700 !important;
}}

/* Segmented Control / Modern Pill Tabs */
div[role="tablist"] {{
    background: var(--ea-tablist-bg) !important;
    border: 1px solid var(--ea-border) !important;
    border-radius: 18px !important;
    padding: 6px !important;
    gap: 6px !important;
    margin-bottom: 24px !important;
    backdrop-filter: blur(16px) !important;
    box-shadow: var(--ea-card-shadow) !important;
    display: flex !important;
    overflow-x: auto !important;
}}

div[role="tablist"] button {{
    background: transparent !important;
    color: var(--ea-tab-color) !important;
    border-radius: 12px !important;
    padding: 10px 20px !important;
    font-size: 0.94rem !important;
    font-weight: 600 !important;
    border: 1px solid transparent !important;
    transition: all 0.25s cubic-bezier(0.4, 0, 0.2, 1) !important;
    margin: 0 !important;
    white-space: nowrap !important;
}}

div[role="tablist"] button:hover {{
    background: var(--ea-surface-hover) !important;
    color: var(--ea-text) !important;
    transform: translateY(-1px) !important;
}}

div[role="tablist"] button[aria-selected="true"] {{
    background: linear-gradient(135deg, #2563eb 0%, #3b82f6 100%) !important;
    color: #ffffff !important;
    border: 1px solid rgba(255, 255, 255, 0.25) !important;
    box-shadow: 0 4px 16px rgba(37, 99, 235, 0.4) !important;
    font-weight: 700 !important;
    transform: translateY(-1px) !important;
}}

div[role="tablist"] button p {{
    font-size: 0.94rem !important;
    font-weight: inherit !important;
    margin: 0 !important;
}}

/* Modern Pills (st.pills) Styling */
[data-testid="stPills"] {{
    gap: 8px !important;
    margin-bottom: 12px !important;
}}

[data-testid="stPills"] button {{
    border-radius: 9999px !important;
    padding: 6px 16px !important;
    font-weight: 600 !important;
    font-size: 0.88rem !important;
    border: 1px solid var(--ea-border) !important;
    background: var(--ea-surface) !important;
    color: var(--ea-text-muted) !important;
    box-shadow: 0 2px 6px rgba(0, 0, 0, 0.04) !important;
    transition: all 0.2s cubic-bezier(0.4, 0, 0.2, 1) !important;
}}

[data-testid="stPills"] button:hover {{
    background: var(--ea-surface-hover) !important;
    border-color: var(--ea-border-hover) !important;
    color: var(--ea-text) !important;
    transform: translateY(-1px) !important;
}}

[data-testid="stPills"] button[aria-pressed="true"],
[data-testid="stPills"] button[data-checked="true"] {{
    background: linear-gradient(135deg, #2563eb 0%, #1d4ed8 100%) !important;
    color: #ffffff !important;
    border-color: transparent !important;
    box-shadow: 0 4px 12px rgba(37, 99, 235, 0.35) !important;
    font-weight: 700 !important;
}}

/* Modern Dashboard Hero & Catalog Styles */
.ea-dashboard-hero {{
    background: var(--ea-hero-bg);
    border: 1px solid var(--ea-border);
    border-radius: 20px;
    padding: 24px 28px;
    margin-bottom: 24px;
    box-shadow: var(--ea-card-shadow);
    display: flex;
    align-items: center;
    gap: 24px;
    position: relative;
    overflow: hidden;
    backdrop-filter: blur(16px);
}}

.ea-dashboard-hero::before {{
    content: '';
    position: absolute;
    top: 0;
    left: 0;
    right: 0;
    height: 4px;
    background: linear-gradient(90deg, #3b82f6 0%, #8b5cf6 50%, #10b981 100%);
}}

.ea-hero-icon-box {{
    width: 64px;
    height: 64px;
    border-radius: 18px;
    background: linear-gradient(135deg, #3b82f6 0%, #8b5cf6 100%);
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 2.2rem;
    box-shadow: 0 10px 24px rgba(59, 130, 246, 0.35);
    flex-shrink: 0;
}}

.ea-hero-content {{
    flex: 1;
}}

.ea-hero-title {{
    font-size: 1.6rem;
    font-weight: 800;
    color: var(--ea-hero-title);
    letter-spacing: -0.025em;
    margin-bottom: 6px;
    font-family: 'Cairo', 'Source Sans 3', sans-serif;
}}

.ea-hero-desc {{
    font-size: 0.94rem;
    color: var(--ea-hero-desc);
    line-height: 1.55;
    margin-bottom: 12px;
}}

.ea-hero-badges {{
    display: flex;
    flex-wrap: wrap;
    gap: 8px;
}}

.ea-hero-badge-pill {{
    display: inline-flex;
    align-items: center;
    gap: 6px;
    background: var(--ea-hero-badge-bg);
    color: var(--ea-hero-badge-color);
    border: 1px solid var(--ea-hero-badge-border);
    border-radius: var(--ea-radius-full);
    padding: 4px 14px;
    font-size: 0.8rem;
    font-weight: 700;
}}

/* Hero Course Header Box */
.course-header-box {{
    background: var(--ea-hero-bg) !important;
    color: var(--ea-hero-title) !important;
    border: 1px solid var(--ea-border) !important;
    padding: 24px 28px !important;
    border-radius: 18px !important;
    margin-bottom: 24px !important;
    box-shadow: var(--ea-card-shadow) !important;
    position: relative !important;
    overflow: hidden !important;
    backdrop-filter: blur(16px) !important;
}}

.course-header-box::before {{
    content: '';
    position: absolute;
    top: 0;
    left: 0;
    right: 0;
    height: 3px;
    background: linear-gradient(90deg, #3b82f6 0%, #8b5cf6 50%, #10b981 100%);
}}

.course-header-box h2 {{
    color: var(--ea-hero-title) !important;
    font-family: 'Cairo', 'AdnaneSans', 'Source Sans 3', sans-serif !important;
    font-size: 1.85rem !important;
    font-weight: 800 !important;
    margin-top: 14px !important;
    margin-bottom: 6px !important;
    line-height: 1.5 !important;
    letter-spacing: -0.01em !important;
}}

.course-header-subtitle {{
    font-size: 0.88rem !important;
    color: var(--ea-text-muted) !important;
    font-weight: 500 !important;
}}

/* Subject Badges with Harmonious Glow */
.badge-subject {{
    display: inline-flex;
    align-items: center;
    padding: 4px 14px;
    border-radius: var(--ea-radius-full);
    font-size: 0.85rem;
    font-weight: 700;
    margin-right: 6px;
    color: #ffffff !important;
    letter-spacing: 0.3px;
    box-shadow: 0 2px 8px rgba(0, 0, 0, 0.15);
}}
.badge-maths {{ background: linear-gradient(135deg, #2563eb 0%, #1d4ed8 100%) !important; }}
.badge-pc {{ background: linear-gradient(135deg, #7c3aed 0%, #6d28d9 100%) !important; }}
.badge-svt {{ background: linear-gradient(135deg, #059669 0%, #047857 100%) !important; }}
.badge-islamic {{ background: linear-gradient(135deg, #0d9488 0%, #0f766e 100%) !important; }}
.badge-histgeo {{ background: linear-gradient(135deg, #d97706 0%, #b45309 100%) !important; }}
.badge-arabic {{ background: linear-gradient(135deg, #dc2626 0%, #b91c1c 100%) !important; }}
.badge-francais {{ background: linear-gradient(135deg, #4f46e5 0%, #4338ca 100%) !important; }}
.badge-anglais {{ background: linear-gradient(135deg, #0284c7 0%, #0369a1 100%) !important; }}
.badge-default {{ background: linear-gradient(135deg, #64748b 0%, #475569 100%) !important; }}

.badge-lang {{
    display: inline-flex;
    align-items: center;
    padding: 4px 12px;
    border-radius: var(--ea-radius-full);
    font-size: 0.82rem;
    font-weight: 700;
    background-color: var(--ea-surface) !important;
    color: var(--ea-text) !important;
    border: 1px solid var(--ea-border) !important;
}}

/* Concept Chips */
.concept-tag {{
    display: inline-block;
    background: rgba(56, 189, 248, 0.12);
    color: #0284c7;
    border: 1px solid rgba(56, 189, 248, 0.28);
    padding: 4px 12px;
    border-radius: 12px;
    font-size: 0.84rem;
    font-weight: 600;
    margin: 3px 4px;
    transition: all 0.2s ease;
}}
.concept-tag:hover {{
    background: rgba(56, 189, 248, 0.2);
    border-color: rgba(56, 189, 248, 0.45);
    transform: translateY(-1px);
}}

/* Cards: Trap and Explanation */
.trap-card {{
    background-color: var(--ea-trap-bg) !important;
    border-left: 4px solid var(--ea-amber) !important;
    color: var(--ea-trap-color) !important;
    padding: 16px 20px;
    border-radius: var(--ea-radius-sm);
    margin: 14px 0;
    box-shadow: 0 4px 12px rgba(245, 158, 11, 0.08);
}}

.trap-card-rtl {{
    background-color: var(--ea-trap-bg) !important;
    border-right: 4px solid var(--ea-amber) !important;
    color: var(--ea-trap-color) !important;
    padding: 16px 20px;
    border-radius: var(--ea-radius-sm);
    margin: 14px 0;
    direction: rtl !important;
    text-align: right !important;
    font-family: 'AdnaneNaskh', 'Noto Naskh Arabic', serif !important;
    font-size: 1.18rem !important;
    line-height: 2.1 !important;
    box-shadow: 0 4px 12px rgba(245, 158, 11, 0.08);
}}

.explanation-card {{
    background-color: var(--ea-expl-bg) !important;
    border-left: 4px solid var(--ea-emerald) !important;
    color: var(--ea-expl-color) !important;
    padding: 16px 20px;
    border-radius: var(--ea-radius-sm);
    margin: 14px 0;
    box-shadow: 0 4px 12px rgba(16, 185, 129, 0.08);
}}

.explanation-card-rtl {{
    background-color: var(--ea-expl-bg) !important;
    border-right: 4px solid var(--ea-emerald) !important;
    color: var(--ea-expl-color) !important;
    padding: 16px 20px;
    border-radius: var(--ea-radius-sm);
    margin: 14px 0;
    direction: rtl !important;
    text-align: right !important;
    font-family: 'AdnaneNaskh', 'Noto Naskh Arabic', serif !important;
    font-size: 1.18rem !important;
    line-height: 2.1 !important;
    box-shadow: 0 4px 12px rgba(16, 185, 129, 0.08);
}}

/* Modern Buttons Override */
button[kind="primary"], [data-testid="stBaseButton-primary"] {{
    background: linear-gradient(135deg, #3b82f6 0%, #1d4ed8 100%) !important;
    border: 1px solid rgba(255, 255, 255, 0.18) !important;
    border-radius: 14px !important;
    font-weight: 700 !important;
    color: #ffffff !important;
    box-shadow: 0 4px 16px rgba(37, 99, 235, 0.35) !important;
    transition: all 0.25s cubic-bezier(0.4, 0, 0.2, 1) !important;
    letter-spacing: 0.2px !important;
}}

button[kind="primary"]:hover, [data-testid="stBaseButton-primary"]:hover {{
    transform: translateY(-2px) !important;
    box-shadow: 0 8px 24px rgba(37, 99, 235, 0.5) !important;
}}

button[kind="secondary"], [data-testid="stBaseButton-secondary"] {{
    background: var(--ea-btn-sec-bg) !important;
    border: 1px solid var(--ea-btn-sec-border) !important;
    border-radius: 14px !important;
    color: var(--ea-btn-sec-color) !important;
    font-weight: 600 !important;
    transition: all 0.25s ease !important;
}}

button[kind="secondary"]:hover, [data-testid="stBaseButton-secondary"]:hover {{
    background: var(--ea-btn-sec-hover) !important;
    border-color: var(--ea-border-hover) !important;
    transform: translateY(-2px) !important;
}}

/* Modern Metrics Styling */
[data-testid="stMetric"] {{
    background: var(--ea-card-bg) !important;
    border: 1px solid var(--ea-border) !important;
    border-radius: var(--ea-radius-md) !important;
    padding: 18px 22px !important;
    box-shadow: var(--ea-card-shadow) !important;
    transition: all 0.25s ease !important;
}}

[data-testid="stMetric"]:hover {{
    border-color: var(--ea-border-hover) !important;
    transform: translateY(-2px) !important;
}}

[data-testid="stMetricLabel"] {{
    color: var(--ea-text-muted) !important;
    font-size: 0.85rem !important;
    font-weight: 600 !important;
    letter-spacing: 0.3px !important;
}}

[data-testid="stMetricValue"] {{
    color: var(--ea-text) !important;
    font-weight: 800 !important;
    font-size: 1.85rem !important;
}}

/* Expanders */
[data-testid="stExpander"] {{
    background: var(--ea-surface-card) !important;
    border: 1px solid var(--ea-border) !important;
    border-radius: var(--ea-radius-md) !important;
    margin-bottom: 14px !important;
}}

[data-testid="stExpander"] summary {{
    font-weight: 700 !important;
    color: var(--ea-text) !important;
}}

/* Inputs, Selectboxes & Textareas */
div[data-baseweb="select"] > div,
div[data-baseweb="input"] > div,
div[data-baseweb="textarea"] > div {{
    background-color: var(--ea-input-bg) !important;
    border: 1px solid var(--ea-input-border) !important;
    border-radius: 14px !important;
    color: var(--ea-text) !important;
    transition: all 0.2s ease !important;
}}

div[data-baseweb="select"]:hover > div,
div[data-baseweb="input"]:hover > div {{
    border-color: var(--ea-border-hover) !important;
}}

/* Chat Messages Styling */
[data-testid="stChatMessage"] {{
    background: var(--ea-surface-card) !important;
    border: 1px solid var(--ea-border) !important;
    border-radius: 18px !important;
    padding: 18px 22px !important;
    margin-bottom: 14px !important;
    box-shadow: var(--ea-card-shadow) !important;
}}

[data-testid="stChatMessage"][data-test-is-user="true"] {{
    background: var(--ea-hero-badge-bg) !important;
    border: 1px solid var(--ea-hero-badge-border) !important;
}}

/* Modern Audio Player Container */
div[data-testid="stAudio"] {{
    background: var(--ea-surface) !important;
    border: 1px solid var(--ea-border) !important;
    border-radius: 16px !important;
    padding: 8px 12px !important;
    margin: 12px 0 !important;
    box-shadow: var(--ea-card-shadow) !important;
}}

div[data-testid="stAudio"] audio {{
    width: 100% !important;
    height: 42px !important;
}}

/* Quiz Question Card */
.quiz-question-card {{
    background: var(--ea-quiz-bg);
    border: 1px solid var(--ea-border);
    border-radius: 18px;
    padding: 22px 26px;
    margin-top: 18px;
    margin-bottom: 12px;
    box-shadow: var(--ea-card-shadow);
    backdrop-filter: blur(12px);
    transition: all 0.25s ease;
}}

.quiz-q-badge {{
    display: inline-flex;
    align-items: center;
    background: var(--ea-hero-badge-bg);
    color: var(--ea-quiz-badge);
    border: 1px solid var(--ea-hero-badge-border);
    border-radius: 10px;
    padding: 4px 14px;
    font-size: 0.82rem;
    font-weight: 700;
    margin-bottom: 12px;
    letter-spacing: 0.3px;
}}

/* Alert / Status Overrides */
div[data-testid="stAlert"] {{
    border-radius: var(--ea-radius-md) !important;
    border-width: 1px !important;
    box-shadow: var(--ea-card-shadow) !important;
}}

/* Google Sign-in Button with same-tab navigation */
.ea-google-signin-btn {{
    display: flex !important;
    align-items: center !important;
    justify-content: center !important;
    gap: 12px !important;
    width: 100% !important;
    padding: 13px 20px !important;
    background: #ffffff !important;
    color: #1e293b !important;
    border-radius: 12px !important;
    text-decoration: none !important;
    font-weight: 700 !important;
    font-size: 1rem !important;
    border: 1px solid rgba(226, 232, 240, 0.9) !important;
    box-shadow: 0 4px 12px rgba(0, 0, 0, 0.08), 0 1px 3px rgba(0, 0, 0, 0.05) !important;
    transition: all 0.22s cubic-bezier(0.16, 1, 0.3, 1) !important;
    cursor: pointer !important;
    box-sizing: border-box !important;
}}

.ea-google-signin-btn:hover {{
    background: #f8fafc !important;
    transform: translateY(-2px) !important;
    box-shadow: 0 8px 24px rgba(37, 99, 235, 0.18), 0 2px 6px rgba(0,0,0,0.08) !important;
    border-color: #3b82f6 !important;
    color: #0f172a !important;
    text-decoration: none !important;
}}

.ea-google-signin-btn:active {{
    transform: translateY(0) !important;
}}

/* Modern Card Container for st.container(border=True) */
div[data-testid="stVerticalBlockBorderWrapper"] {{
    border-radius: 18px !important;
    border: 1px solid var(--ea-border) !important;
    background: var(--ea-surface) !important;
    box-shadow: var(--ea-card-shadow) !important;
    transition: all 0.25s cubic-bezier(0.16, 1, 0.3, 1) !important;
}}

div[data-testid="stVerticalBlockBorderWrapper"]:hover {{
    border-color: var(--ea-border-hover) !important;
    box-shadow: 0 12px 28px -6px rgba(0, 0, 0, 0.25), 0 0 0 1px var(--ea-primary-glow) !important;
}}

/* Modern Segmented Control Pills */
div[data-testid="stSegmentedControl"] {{
    background: var(--ea-surface) !important;
    border: 1px solid var(--ea-border) !important;
    border-radius: 9999px !important;
    padding: 4px !important;
    box-shadow: var(--ea-card-shadow) !important;
}}

div[data-testid="stSegmentedControl"] button {{
    border-radius: 9999px !important;
    font-weight: 600 !important;
    font-size: 0.9rem !important;
    padding: 8px 18px !important;
    color: var(--ea-text-muted) !important;
    transition: all 0.2s ease !important;
}}

div[data-testid="stSegmentedControl"] button[aria-checked="true"],
div[data-testid="stSegmentedControl"] button[data-checked="true"] {{
    background: linear-gradient(135deg, #2563eb 0%, #1d4ed8 100%) !important;
    color: #ffffff !important;
    box-shadow: 0 2px 8px rgba(37, 99, 235, 0.35) !important;
    font-weight: 700 !important;
}}
/* =====================================================================
   ERGONOMIC OVERHAUL v2 — student-friendly layer (overrides above)
   ===================================================================== */
:root {{
    --ea-grad: linear-gradient(135deg, #1e3a5f 0%, #2c4f80 100%);
    --ea-grad-soft: linear-gradient(135deg, rgba(30,58,95,0.16) 0%, rgba(184,137,43,0.10) 100%);
    --ea-touch: 46px;
    --ea-focus: 0 0 0 3px rgba(184, 137, 43, 0.5);
}}

html {{ scroll-behavior: smooth; }}
.block-container {{ padding-top: 2.5rem !important; max-width: 1200px !important; }}
p, li {{ line-height: 1.7; }}

/* Visible keyboard focus everywhere */
button:focus-visible, a:focus-visible, input:focus-visible, textarea:focus-visible,
[role="tab"]:focus-visible, [data-baseweb="select"]:focus-within {{
    outline: none !important;
    box-shadow: var(--ea-focus) !important;
}}

/* Bigger, friendlier touch targets */
button[kind="primary"], button[kind="secondary"],
[data-testid="stBaseButton-primary"], [data-testid="stBaseButton-secondary"] {{
    min-height: var(--ea-touch) !important;
    padding: 0.55rem 1.1rem !important;
    font-size: 0.97rem !important;
}}
button[kind="primary"], [data-testid="stBaseButton-primary"] {{
    background: var(--ea-grad) !important;
    box-shadow: 0 6px 18px rgba(30, 58, 95, 0.40) !important;
}}
button[kind="primary"]:hover, [data-testid="stBaseButton-primary"]:hover {{
    box-shadow: 0 10px 26px rgba(30, 58, 95, 0.55) !important;
    filter: brightness(1.06);
}}
button:active {{ transform: scale(0.98) !important; }}
button:disabled {{ opacity: 0.45 !important; }}

div[data-baseweb="select"] > div, div[data-baseweb="input"] > div, div[data-baseweb="textarea"] > div {{
    min-height: var(--ea-touch) !important;
}}

/* Gradient brand accents replace flat blue */
div[role="tablist"] button[aria-selected="true"],
[data-testid="stPills"] button[aria-pressed="true"],
[data-testid="stPills"] button[data-checked="true"],
div[data-testid="stSegmentedControl"] button[aria-checked="true"],
div[data-testid="stSegmentedControl"] button[data-checked="true"],
div[data-testid="stRadio"] [data-testid="stRadioGroup"][aria-orientation="horizontal"] [data-testid="stRadioOption"][data-selected="true"],
div[data-testid="stRadio"] [data-testid="stRadioGroup"][aria-orientation="horizontal"] [data-testid="stRadioOption"]:has(input:checked) {{
    background: var(--ea-grad) !important;
    box-shadow: 0 4px 14px rgba(30, 58, 95, 0.40) !important;
    color: #fff !important;
}}
[data-testid="stSidebar"] [data-testid="stRadioOption"][data-selected="true"],
[data-testid="stSidebar"] [data-testid="stRadioOption"]:has(input:checked),
[data-testid="stSidebar"] [data-testid="stRadio"] div[role="radiogroup"] label:has(input:checked) {{
    background: var(--ea-grad-soft) !important;
    border-color: var(--ea-primary) !important;
}}
[data-testid="stSidebar"] [data-testid="stRadioOption"],
[data-testid="stSidebar"] [data-testid="stRadio"] div[role="radiogroup"] label {{
    min-height: var(--ea-touch) !important;
    border-radius: 14px !important;
}}
[data-testid="stSidebar"] [data-testid="stRadioOption"] p {{ font-size: 0.97rem !important; }}

/* Tabs: scrollable on small screens, bigger labels */
div[role="tablist"] {{ scrollbar-width: thin; -webkit-overflow-scrolling: touch; }}
div[role="tablist"] button {{ min-height: 44px !important; }}

/* Hero: more welcoming */
.ea-dashboard-hero {{
    background: var(--ea-grad-soft), var(--ea-hero-bg);
    border-radius: 24px;
    padding: 28px 32px;
}}
.ea-dashboard-hero::before {{ background: var(--ea-grad); height: 5px; }}
.ea-hero-icon-box {{ background: var(--ea-grad); box-shadow: 0 10px 26px rgba(30, 58, 95, 0.40); animation: eaFloat 4s ease-in-out infinite; }}
.ea-hero-title {{ font-size: 1.75rem; }}
.ea-hero-desc {{ font-size: 1rem; }}
.course-header-box::before {{ background: var(--ea-grad); }}
@keyframes eaFloat {{ 0%,100% {{ transform: translateY(0); }} 50% {{ transform: translateY(-5px); }} }}

/* Cards: clear affordance, lift on hover */
div[data-testid="stVerticalBlockBorderWrapper"] {{ border-radius: 20px !important; }}
div[data-testid="stVerticalBlockBorderWrapper"]:hover {{ transform: translateY(-3px); }}
[data-testid="stMetric"] {{ border-radius: 18px !important; border-top: 3px solid var(--ea-primary) !important; }}
[data-testid="stMetricValue"] {{ background: var(--ea-grad); -webkit-background-clip: text; background-clip: text; -webkit-text-fill-color: transparent; }}

.badge-subject, .badge-lang {{ font-size: 0.82rem; }}
.concept-tag {{ color: var(--ea-primary) !important; background: var(--ea-grad-soft) !important; border-color: var(--ea-hero-badge-border) !important; }}

/* Progress bars: motivating gradient */
[data-testid="stProgress"] > div > div {{ background-color: var(--ea-border) !important; border-radius: 9999px !important; height: 10px !important; }}
[data-testid="stProgress"] > div > div > div {{ background: linear-gradient(90deg, #1e3a5f, #b8892b) !important; border-radius: 9999px !important; }}

/* Quiz readability */
.quiz-question-card {{ border-left: 5px solid var(--ea-primary); font-size: 1.05rem; }}
div[data-testid="stRadio"] div[role="radiogroup"]:not([aria-orientation="horizontal"]) label {{
    border-radius: 14px !important;
    transition: all .18s ease !important;
}}
.trap-card, .explanation-card, .trap-card-rtl, .explanation-card-rtl {{ border-radius: 14px; font-size: 1.02rem; }}

/* Chat */
[data-testid="stChatInput"] {{ border-radius: 20px !important; }}
[data-testid="stChatMessage"] {{ border-radius: 20px !important; }}

/* Custom scrollbar */
::-webkit-scrollbar {{ width: 10px; height: 10px; }}
::-webkit-scrollbar-thumb {{ background: var(--ea-border-hover); border-radius: 9999px; }}

/* Mobile (phones: main student device) */
@media (max-width: 768px) {{
    .block-container {{ padding: 3.2rem 0.9rem 4rem !important; }}
    .ea-dashboard-hero {{ flex-direction: column; align-items: flex-start; padding: 20px; gap: 14px; }}
    .ea-hero-icon-box {{ width: 52px; height: 52px; font-size: 1.8rem; }}
    .ea-hero-title {{ font-size: 1.4rem; }}
    .course-header-box {{ padding: 18px !important; }}
    .course-header-box h2 {{ font-size: 1.45rem !important; }}
    div[role="tablist"] {{ border-radius: 14px !important; padding: 4px !important; }}
    div[role="tablist"] button {{ padding: 8px 14px !important; }}
    [data-testid="stMetricValue"] {{ font-size: 1.5rem !important; }}
    .rtl-box, .rtl-box p, .rtl-box li {{ font-size: 1.12rem !important; }}
}}

/* Respect reduced-motion preferences */
@media (prefers-reduced-motion: reduce) {{
    *, *::before, *::after {{ animation: none !important; transition: none !important; scroll-behavior: auto !important; }}
}}
/* ---- "Aujourd'hui" dashboard ---- */
.ea-today-card {{
    background: var(--ea-grad); color: #fff; border-radius: 24px; padding: 26px 28px 22px; margin-bottom: 10px;
    box-shadow: 0 16px 40px rgba(30,58,95,0.35); position: relative; overflow: hidden;
}}
.ea-today-card::after {{ content: '📚'; position: absolute; right: 18px; bottom: -14px; font-size: 7rem; opacity: 0.14; }}
.ea-today-hello {{ font-size: 0.95rem; font-weight: 600; opacity: 0.9; }}
.ea-today-kicker {{ margin-top: 10px; font-size: 0.78rem; font-weight: 800; letter-spacing: .08em; text-transform: uppercase; opacity: 0.85; }}
.ea-today-title {{ font-size: 1.55rem; font-weight: 800; line-height: 1.3; margin: 4px 0; color: #fff; }}
.ea-today-sub {{ font-size: 0.9rem; opacity: 0.9; margin-bottom: 14px; }}
.ea-today-card .ea-bar {{ background: rgba(255,255,255,0.25); }}
.ea-today-card .ea-bar span {{ background: #fff; }}
.ea-bar {{ height: 10px; border-radius: 9999px; background: var(--ea-border); overflow: hidden; }}
.ea-bar span {{ display: block; height: 100%; border-radius: 9999px; background: linear-gradient(90deg,#1e3a5f,#b8892b); transition: width .6s ease; }}
.ea-bar.small {{ height: 6px; margin: 4px 0 4px; }}
.ea-stats-card {{ background: var(--ea-surface); border: 1px solid var(--ea-border); border-radius: 24px; padding: 20px 22px; box-shadow: var(--ea-card-shadow); margin-bottom: 10px; }}
.ea-stat-row {{ display: flex; gap: 14px; margin-bottom: 14px; }}
.ea-stat {{ flex: 1; display: flex; align-items: center; gap: 10px; background: var(--ea-grad-soft); border-radius: 16px; padding: 10px 12px; }}
.ea-stat-ico {{ font-size: 1.7rem; }}
.ea-stat b {{ display: block; font-size: 1.05rem; color: var(--ea-text); }}
.ea-stat small {{ color: var(--ea-text-muted); font-size: 0.75rem; }}
.ea-stat-label {{ font-size: 0.8rem; color: var(--ea-text-muted); margin-bottom: 6px; font-weight: 600; }}
.ea-goal {{ margin-top: 14px; padding: 10px 14px; border-radius: 14px; font-size: 0.9rem; font-weight: 700; background: rgba(245,158,11,0.14); color: var(--ea-amber); }}
.ea-goal.done {{ background: rgba(16,185,129,0.14); color: var(--ea-emerald); }}

/* ---- Course cards: color by subject + status ---- */
.ea-card-stripe {{ height: 6px; border-radius: 9999px; margin: -4px 0 12px; }}
.ea-card-status {{ display: inline-block; font-size: 0.74rem; font-weight: 800; padding: 3px 10px; border-radius: 9999px; margin-bottom: 8px; }}
.ea-card-status.new {{ background: var(--ea-border); color: var(--ea-text-muted); }}
.ea-card-status.learning {{ background: rgba(245,158,11,0.16); color: var(--ea-amber); }}
.ea-card-status.mastered {{ background: rgba(16,185,129,0.16); color: var(--ea-emerald); }}
.ea-card-score {{ font-size: 0.78rem; color: var(--ea-text-muted); margin-bottom: 10px; }}
/* ---- Compact sidebar ---- */
[data-testid="stSidebar"][aria-expanded="true"] {{ min-width: 236px !important; max-width: 236px !important; width: 236px !important; }}
[data-testid="stSidebarUserContent"], [data-testid="stSidebar"] > div > div {{ padding-top: 0.6rem !important; }}
[data-testid="stSidebar"] [data-testid="stSidebarContent"] {{ padding: 0 0.7rem 0.8rem !important; }}
[data-testid="stSidebar"] [data-testid="stVerticalBlock"] {{ gap: 0.45rem !important; }}
[data-testid="stSidebar"] hr {{ margin: 0.4rem 0 !important; }}

.sb-brand {{ display: flex; align-items: center; gap: 9px; margin: 2px 0 10px; }}
.sb-logo {{ width: 32px; height: 32px; border-radius: 10px; background: var(--ea-grad); display: flex; align-items: center; justify-content: center; font-size: 1.1rem; box-shadow: 0 4px 12px rgba(30,58,95,0.4); }}
.sb-brand-name {{ font-size: 1.1rem; font-weight: 800; letter-spacing: -0.02em; color: var(--ea-sidebar-text); }}
.sb-profile {{ display: flex; align-items: center; gap: 10px; padding: 8px 10px; border-radius: 14px; background: var(--ea-surface); border: 1px solid var(--ea-border); }}
.sb-avatar {{ width: 34px; height: 34px; flex-shrink: 0; border-radius: 50%; background: var(--ea-grad); color: #fff; display: flex; align-items: center; justify-content: center; font-weight: 800; }}
.sb-profile-txt {{ min-width: 0; }}
.sb-name {{ font-size: 0.9rem; font-weight: 700; color: var(--ea-sidebar-text); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }}
.sb-meta {{ font-size: 0.72rem; color: var(--ea-text-muted); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }}
.sb-xp {{ display: flex; justify-content: space-between; margin: 8px 4px 2px; font-size: 0.78rem; font-weight: 700; color: var(--ea-sidebar-text); }}
.sb-spacer {{ height: 6px; }}

/* Flat compact nav list */
[data-testid="stSidebar"] [data-testid="stRadioOption"],
[data-testid="stSidebar"] [data-testid="stRadio"] div[role="radiogroup"] label {{
    min-height: 40px !important; padding: 6px 12px !important; margin: 0 0 2px 0 !important;
    background: transparent !important; border: 1px solid transparent !important; border-radius: 12px !important;
    box-shadow: none !important;
}}
[data-testid="stSidebar"] [data-testid="stRadioOption"]:hover,
[data-testid="stSidebar"] [data-testid="stRadio"] div[role="radiogroup"] label:hover {{
    background: var(--ea-surface-hover) !important; transform: none !important;
}}
[data-testid="stSidebar"] [data-testid="stRadioOption"][data-selected="true"],
[data-testid="stSidebar"] [data-testid="stRadioOption"]:has(input:checked),
[data-testid="stSidebar"] [data-testid="stRadio"] div[role="radiogroup"] label:has(input:checked) {{
    background: var(--ea-grad-soft) !important; border: 1px solid var(--ea-hero-badge-border) !important;
    border-left: 4px solid var(--ea-primary) !important; transform: none !important; box-shadow: none !important;
}}
[data-testid="stSidebar"] [data-testid="stRadioOption"] p {{ font-size: 0.92rem !important; }}

/* Compact status pill + small buttons */
.ai-status-pill {{ padding: 5px 10px; font-size: 0.74rem; margin-bottom: 6px; border-radius: 12px; }}
.ai-status-pill.warn {{ background: rgba(245,158,11,0.14); border-color: rgba(245,158,11,0.3); color: var(--ea-amber); }}
[data-testid="stSidebar"] .stButton button {{ min-height: 38px !important; padding: 0.3rem 0.5rem !important; font-size: 0.85rem !important; }}
/* ---- ACADEMIC THEME LAYER ---- */
h1, h2, h3, h4, .ea-hero-title, .ea-today-title, .sb-brand-name, .course-header-box h2 {{
    font-family: 'Source Serif 4', 'Cairo', 'AdnaneSans', Georgia, serif !important;
    letter-spacing: 0 !important;
    font-weight: 700 !important;
}}
h1 {{ font-size: 1.6rem !important; color: var(--ea-hero-title) !important; border-bottom: 2px solid var(--ea-amber); padding-bottom: 0.3rem !important; }}
h2, h3 {{ color: var(--ea-hero-title) !important; }}

/* Quiet, formal controls: no glow, no floating, no gradients */
.ea-hero-icon-box {{ animation: none !important; }}
div[data-testid="stVerticalBlockBorderWrapper"]:hover {{ transform: none !important; }}
button[kind="primary"], [data-testid="stBaseButton-primary"] {{
    background: var(--ea-primary) !important; color: var(--ea-on-primary) !important; border-radius: 8px !important; box-shadow: none !important;
    border: 1px solid var(--ea-primary) !important; letter-spacing: 0.01em !important;
}}
button[kind="primary"]:hover, [data-testid="stBaseButton-primary"]:hover {{
    background: var(--ea-primary-hover) !important; transform: none !important; box-shadow: 0 2px 8px var(--ea-primary-glow) !important; filter: none;
}}
button[kind="secondary"], [data-testid="stBaseButton-secondary"] {{ border-radius: 8px !important; }}
div[data-baseweb="select"] > div, div[data-baseweb="input"] > div, div[data-baseweb="textarea"] > div {{ border-radius: 8px !important; }}
div[role="tablist"] {{ border-radius: 10px !important; box-shadow: none !important; backdrop-filter: none !important; }}
div[role="tablist"] button {{ border-radius: 8px !important; }}
div[role="tablist"] button[aria-selected="true"],
[data-testid="stPills"] button[aria-pressed="true"], [data-testid="stPills"] button[data-checked="true"],
div[data-testid="stSegmentedControl"] button[aria-checked="true"], div[data-testid="stSegmentedControl"] button[data-checked="true"] {{
    background: var(--ea-primary) !important; box-shadow: none !important; color: var(--ea-on-primary) !important; border-color: var(--ea-primary) !important;
}}
[data-testid="stPills"] button, div[data-testid="stSegmentedControl"] {{ border-radius: 8px !important; }}
[data-testid="stMetric"] {{ border-radius: 10px !important; border-top: 3px solid var(--ea-amber) !important; }}
[data-testid="stMetricValue"] {{ background: none !important; -webkit-text-fill-color: var(--ea-hero-title) !important; color: var(--ea-hero-title) !important; font-family: 'Source Serif 4', serif !important; }}
div[data-testid="stVerticalBlockBorderWrapper"] {{ border-radius: 10px !important; }}
[data-testid="stExpander"], [data-testid="stChatMessage"], [data-testid="stChatInput"], .quiz-question-card, .trap-card, .explanation-card, .course-header-box, .ea-stats-card {{ border-radius: 10px !important; }}
.ea-dashboard-hero {{ border-radius: 12px; background: var(--ea-hero-bg); }}
.ea-dashboard-hero::before, .course-header-box::before {{ background: var(--ea-amber); height: 4px; }}
.quiz-question-card {{ border-left: 4px solid var(--ea-amber); }}
.badge-subject, .badge-lang, .ea-card-status {{ border-radius: 6px !important; }}

/* "Aujourd'hui" card: navy panel with gold accent */
.ea-today-card {{ border-radius: 12px; background: linear-gradient(135deg, #1e3a5f 0%, #26466f 100%); box-shadow: 0 4px 14px rgba(30,58,95,0.25); border-bottom: 4px solid #b8892b; }}
.ea-today-card::after {{ content: '🎓'; }}
.ea-today-kicker {{ color: #e6c274; }}
.ea-stat {{ border-radius: 10px; background: var(--ea-grad-soft); }}
.ea-stats-card {{ border-radius: 12px; }}
.ea-bar span {{ background: linear-gradient(90deg, #1e3a5f, #b8892b) !important; }}
.ea-today-card .ea-bar span {{ background: #e6c274 !important; }}
.ea-card-stripe {{ height: 4px; border-radius: 2px; }}

/* Slim sidebar = table of contents */
[data-testid="stSidebar"][aria-expanded="true"] {{ min-width: 210px !important; max-width: 210px !important; width: 210px !important; }}
[data-testid="stSidebar"] {{ background: var(--ea-sidebar-bg) !important; border-right: 1px solid var(--ea-sidebar-border) !important; }}
.sb-logo {{ background: var(--ea-primary) !important; box-shadow: none !important; border-radius: 8px !important; }}
.sb-brand-name {{ font-size: 1rem !important; }}
[data-testid="stSidebar"] [data-testid="stRadioOption"],
[data-testid="stSidebar"] [data-testid="stRadio"] div[role="radiogroup"] label {{
    min-height: 36px !important; padding: 4px 10px !important; border-radius: 4px !important; border: none !important;
    border-left: 3px solid transparent !important; background: transparent !important;
}}
[data-testid="stSidebar"] [data-testid="stRadioOption"]:hover,
[data-testid="stSidebar"] [data-testid="stRadio"] div[role="radiogroup"] label:hover {{ background: rgba(30,58,95,0.07) !important; }}
[data-testid="stSidebar"] [data-testid="stRadioOption"][data-selected="true"],
[data-testid="stSidebar"] [data-testid="stRadioOption"]:has(input:checked),
[data-testid="stSidebar"] [data-testid="stRadio"] div[role="radiogroup"] label:has(input:checked) {{
    background: rgba(184,137,43,0.14) !important; border: none !important; border-left: 3px solid var(--ea-amber) !important;
}}
[data-testid="stSidebar"] [data-testid="stRadioOption"][data-selected="true"] p,
[data-testid="stSidebar"] [data-testid="stRadioOption"]:has(input:checked) p {{ color: var(--ea-hero-title) !important; font-weight: 700 !important; }}
.sb-profile {{ border-radius: 10px; }}
.sb-avatar {{ background: var(--ea-primary) !important; }}
/* ---- THEME FIDELITY: native widgets must follow the active palette ---- */
[data-testid="stWidgetLabel"], [data-testid="stWidgetLabel"] p, [data-testid="stWidgetLabel"] span,
[data-testid="stCheckbox"] label, [data-testid="stCheckbox"] label p,
[data-testid="stRadio"] label p, [data-testid="stToggle"] label p,
[data-testid="stFileUploader"] label, [data-testid="stCaptionContainer"] {{
    color: var(--ea-text-muted) !important;
}}
div[data-baseweb="input"], div[data-baseweb="input"] > div, div[data-baseweb="base-input"],
div[data-baseweb="textarea"], div[data-baseweb="textarea"] > div,
input, textarea {{
    background-color: var(--ea-input-bg) !important;
    color: var(--ea-text) !important;
    -webkit-text-fill-color: var(--ea-text) !important;
    caret-color: var(--ea-primary) !important;
}}
input::placeholder, textarea::placeholder {{ color: var(--ea-text-dim) !important; -webkit-text-fill-color: var(--ea-text-dim) !important; opacity: 1; }}
div[data-baseweb="select"] > div {{ background-color: var(--ea-input-bg) !important; color: var(--ea-text) !important; }}
div[data-baseweb="select"] div, div[data-baseweb="select"] span, div[data-baseweb="select"] input {{
    color: var(--ea-text) !important; -webkit-text-fill-color: var(--ea-text) !important;
}}
div[data-baseweb="select"] svg, div[data-baseweb="input"] svg {{ fill: var(--ea-text-muted) !important; color: var(--ea-text-muted) !important; }}
div[data-baseweb="popover"] > div, div[data-baseweb="popover"] ul, ul[data-baseweb="menu"], [role="listbox"],
[data-testid="stPopoverBody"], [data-testid="stSelectboxVirtualDropdown"] {{
    background: var(--ea-surface) !important; color: var(--ea-text) !important; border: 1px solid var(--ea-border);
}}
li[role="option"], ul[data-baseweb="menu"] li {{ background: transparent !important; color: var(--ea-text) !important; }}
li[role="option"]:hover, li[role="option"][aria-selected="true"], ul[data-baseweb="menu"] li:hover {{ background: var(--ea-surface-hover) !important; }}
code, [data-testid="stMarkdownContainer"] code {{
    background: var(--ea-surface-hover) !important; color: var(--ea-hero-badge-color) !important;
    border: 1px solid var(--ea-border); border-radius: 5px; padding: 1px 6px; font-size: 0.85em;
}}
pre, [data-testid="stCode"], [data-testid="stCode"] pre {{ background: var(--ea-surface-hover) !important; color: var(--ea-text) !important; }}
div[data-testid="stAlert"] > div {{ background: var(--ea-surface-hover) !important; color: var(--ea-text) !important; border: 1px solid var(--ea-border); border-left: 4px solid var(--ea-amber); }}
div[data-testid="stAlert"] p, div[data-testid="stAlert"] span {{ color: var(--ea-text) !important; }}
[data-testid="stFileUploaderDropzone"] {{ background: var(--ea-input-bg) !important; border: 1px dashed var(--ea-border-hover) !important; color: var(--ea-text) !important; }}
[data-testid="stFileUploaderDropzone"] * {{ color: var(--ea-text-muted) !important; }}
[data-testid="stExpander"] details, [data-testid="stExpander"] summary {{ background: transparent !important; color: var(--ea-text) !important; }}
[data-testid="stChatInput"] > div, [data-testid="stChatInput"] textarea {{ background: var(--ea-input-bg) !important; color: var(--ea-text) !important; }}
[data-testid="stTooltipContent"], div[data-baseweb="tooltip"] > div {{ background: var(--ea-surface-hover) !important; color: var(--ea-text) !important; }}
[data-testid="stBaseButton-secondary"] p, [data-testid="stBaseButton-secondary"] span {{ color: var(--ea-btn-sec-color) !important; }}
[data-testid="stBaseButton-primary"] p, [data-testid="stBaseButton-primary"] span {{ color: var(--ea-on-primary) !important; }}
[data-testid="stSidebar"] div[data-baseweb="select"] > div {{ background-color: var(--ea-input-bg) !important; }}
{dark_extra}

/* ---- THEME FIDELITY 2: pills, segmented controls, selectboxes (Streamlit 1.65 test ids) ---- */
button[data-testid="stBaseButton-pills"], button[data-testid="stBaseButton-segmented_control"] {{
    background: var(--ea-surface) !important; color: var(--ea-text-muted) !important;
    border: 1px solid var(--ea-border) !important; box-shadow: none !important;
}}
button[data-testid="stBaseButton-pills"] *, button[data-testid="stBaseButton-segmented_control"] * {{ color: var(--ea-text-muted) !important; }}
button[data-testid="stBaseButton-pills"]:hover, button[data-testid="stBaseButton-segmented_control"]:hover {{
    background: var(--ea-surface-hover) !important; border-color: var(--ea-border-hover) !important;
}}
button[data-testid="stBaseButton-pillsActive"], button[data-testid="stBaseButton-segmented_controlActive"] {{
    background: var(--ea-primary) !important; color: var(--ea-on-primary) !important;
    border: 1px solid var(--ea-primary) !important; box-shadow: none !important; font-weight: 700 !important;
}}
button[data-testid="stBaseButton-pillsActive"] *, button[data-testid="stBaseButton-segmented_controlActive"] * {{ color: var(--ea-on-primary) !important; }}
div[data-testid="stSegmentedControl"], [data-testid="stButtonGroup"] {{ background: transparent !important; border: none !important; box-shadow: none !important; }}

[data-testid="stSelectbox"] div[data-baseweb="select"] div {{ background-color: transparent !important; }}
[data-testid="stSelectbox"] div[data-baseweb="select"] > div {{ background-color: var(--ea-input-bg) !important; border: 1px solid var(--ea-input-border) !important; }}
[data-testid="stSelectbox"] div[data-baseweb="select"] div, [data-testid="stSelectbox"] div[data-baseweb="select"] span {{ color: var(--ea-text) !important; }}

/* ---- THEME FIDELITY 3: force inactive pills/segmented_control & selectbox arrow ---- */
[data-testid="stButtonGroup"] button,
[data-testid="stPills"] button,
div[data-testid="stSegmentedControl"] button {{
    background-color: var(--ea-surface) !important;
    background: var(--ea-surface) !important;
    color: var(--ea-text-muted) !important;
    border: 1px solid var(--ea-border) !important;
    box-shadow: none !important;
}}
[data-testid="stButtonGroup"] button *,
[data-testid="stPills"] button *,
div[data-testid="stSegmentedControl"] button * {{
    color: var(--ea-text-muted) !important;
}}
[data-testid="stButtonGroup"] button:hover,
[data-testid="stPills"] button:hover,
div[data-testid="stSegmentedControl"] button:hover {{
    background-color: var(--ea-surface-hover) !important;
    background: var(--ea-surface-hover) !important;
    border-color: var(--ea-border-hover) !important;
    color: var(--ea-text) !important;
}}
[data-testid="stButtonGroup"] button[aria-pressed="true"],
[data-testid="stButtonGroup"] button[aria-checked="true"],
[data-testid="stButtonGroup"] button[data-checked="true"],
[data-testid="stButtonGroup"] button[data-testid="stBaseButton-pillsActive"],
[data-testid="stButtonGroup"] button[data-testid="stBaseButton-segmented_controlActive"],
[data-testid="stPills"] button[aria-pressed="true"],
[data-testid="stPills"] button[data-checked="true"],
div[data-testid="stSegmentedControl"] button[aria-checked="true"],
div[data-testid="stSegmentedControl"] button[data-checked="true"] {{
    background-color: var(--ea-primary) !important;
    background: var(--ea-primary) !important;
    color: var(--ea-on-primary) !important;
    border-color: var(--ea-primary) !important;
    font-weight: 700 !important;
}}
[data-testid="stButtonGroup"] button[aria-pressed="true"] *,
[data-testid="stButtonGroup"] button[aria-checked="true"] *,
[data-testid="stButtonGroup"] button[data-checked="true"] *,
[data-testid="stButtonGroup"] button[data-testid="stBaseButton-pillsActive"] *,
[data-testid="stButtonGroup"] button[data-testid="stBaseButton-segmented_controlActive"] *,
[data-testid="stPills"] button[aria-pressed="true"] *,
[data-testid="stPills"] button[data-checked="true"] *,
div[data-testid="stSegmentedControl"] button[aria-checked="true"] *,
div[data-testid="stSegmentedControl"] button[data-checked="true"] * {{
    color: var(--ea-on-primary) !important;
}}

/* Selectbox right arrow container */
[data-testid="stSelectbox"] div[data-baseweb="select"] > div > div {{
    background-color: transparent !important;
    background: transparent !important;
}}
[data-testid="stSelectbox"] div[data-baseweb="select"] > div {{
    background-color: var(--ea-input-bg) !important;
    background: var(--ea-input-bg) !important;
}}

/* ---- THEME FIDELITY 4: selectbox button & dropdown portal options ---- */
[data-testid="stSelectbox"] div[data-baseweb="select"],
[data-testid="stSelectbox"] div[data-baseweb="select"] > div,
[data-testid="stSelectbox"] div[data-baseweb="select"] > div > div,
div[data-baseweb="select"] > div {{
    background-color: var(--ea-input-bg) !important;
    background: var(--ea-input-bg) !important;
    color: var(--ea-text) !important;
    border-color: var(--ea-input-border) !important;
}}
[data-testid="stSelectbox"] div[data-baseweb="select"] svg,
div[data-baseweb="select"] svg {{
    fill: var(--ea-text-muted) !important;
    color: var(--ea-text-muted) !important;
    background: transparent !important;
}}
div[data-baseweb="popover"],
div[data-baseweb="popover"] > div,
div[data-baseweb="popover"] div[data-baseweb="menu"],
ul[data-baseweb="menu"],
[data-testid="stSelectboxVirtualDropdown"],
[data-testid="stSelectboxVirtualDropdown"] > div,
[role="listbox"] {{
    background-color: var(--ea-surface) !important;
    background: var(--ea-surface) !important;
    color: var(--ea-text) !important;
    border-color: var(--ea-border) !important;
}}
ul[data-baseweb="menu"] li,
ul[data-baseweb="menu"] li *,
[data-testid="stSelectboxVirtualDropdown"] li,
[data-testid="stSelectboxVirtualDropdown"] li *,
[role="listbox"] [role="option"],
[role="listbox"] [role="option"] * {{
    background-color: transparent !important;
    color: var(--ea-text) !important;
    -webkit-text-fill-color: var(--ea-text) !important;
}}
ul[data-baseweb="menu"] li:hover,
[data-testid="stSelectboxVirtualDropdown"] li:hover,
[role="listbox"] [role="option"]:hover,
[role="listbox"] [role="option"][aria-selected="true"] {{
    background-color: var(--ea-surface-hover) !important;
    background: var(--ea-surface-hover) !important;
}}

/* ---- THEME FIDELITY 5: course tabs text & scroll arrows ---- */
div[role="tablist"] button[role="tab"],
div[role="tablist"] button[role="tab"] * {{
    color: var(--ea-text-muted) !important;
    -webkit-text-fill-color: var(--ea-text-muted) !important;
}}
div[role="tablist"] button[role="tab"]:hover,
div[role="tablist"] button[role="tab"]:hover * {{
    color: var(--ea-text) !important;
    -webkit-text-fill-color: var(--ea-text) !important;
}}
div[role="tablist"] button[role="tab"][aria-selected="true"],
div[role="tablist"] button[role="tab"][aria-selected="true"] * {{
    background: var(--ea-primary) !important;
    color: var(--ea-on-primary) !important;
    -webkit-text-fill-color: var(--ea-on-primary) !important;
}}
div[role="tablist"] button:not([role="tab"]),
[data-testid="stTabs"] button:not([role="tab"]) {{
    background: var(--ea-surface-hover) !important;
    background-color: var(--ea-surface-hover) !important;
    color: var(--ea-text) !important;
    border-color: var(--ea-border) !important;
}}
div[role="tablist"] button:not([role="tab"]) svg,
[data-testid="stTabs"] button:not([role="tab"]) svg {{
    fill: var(--ea-text) !important;
    color: var(--ea-text) !important;
}}

/* ---- COMPACT + TYPOGRAPHY LAYER ---- */
html {{ font-size: 14.5px; }}
.stApp, [data-testid="stMarkdownContainer"] p, [data-testid="stMarkdownContainer"] li {{ font-size: 1rem; line-height: 1.55; }}
h1 {{ font-size: 1.55rem !important; margin: 0 0 0.6rem !important; }}
h2 {{ font-size: 1.3rem !important; }}
h3 {{ font-size: 1.12rem !important; }}
h4, h5 {{ font-size: 1rem !important; }}
h1, h2, h3, h4 {{ line-height: 1.3 !important; padding-top: 0.4rem !important; }}
[data-testid="stCaptionContainer"], small {{ font-size: 0.82rem !important; }}
.block-container {{ padding: 1.6rem 2rem 2.5rem !important; max-width: 1100px !important; }}
[data-testid="stVerticalBlock"] {{ gap: 0.65rem !important; }}
[data-testid="stHorizontalBlock"] {{ gap: 0.8rem !important; }}
hr {{ margin: 0.8rem 0 !important; }}
button[kind="primary"], button[kind="secondary"], [data-testid="stBaseButton-primary"], [data-testid="stBaseButton-secondary"] {{
    min-height: 38px !important; padding: 0.3rem 0.9rem !important; font-size: 0.92rem !important;
}}
div[data-baseweb="select"] > div, div[data-baseweb="input"] > div, div[data-baseweb="textarea"] > div {{ min-height: 38px !important; font-size: 0.95rem !important; }}
div[role="tablist"] {{ padding: 4px !important; margin-bottom: 14px !important; gap: 4px !important; }}
div[role="tablist"] button {{ min-height: 36px !important; padding: 6px 14px !important; }}
div[role="tablist"] button p, [data-testid="stPills"] button, div[data-testid="stSegmentedControl"] button {{ font-size: 0.88rem !important; }}
[data-testid="stMetric"] {{ padding: 12px 16px !important; }}
[data-testid="stMetricValue"] {{ font-size: 1.45rem !important; }}
[data-testid="stMetricLabel"] {{ font-size: 0.8rem !important; }}
[data-testid="stExpander"] {{ margin-bottom: 8px !important; }}
[data-testid="stExpander"] summary {{ padding: 0.5rem 0.8rem !important; font-size: 0.95rem !important; }}
div[data-testid="stVerticalBlockBorderWrapper"] {{ padding: 0.2rem !important; }}
[data-testid="stChatMessage"] {{ padding: 12px 16px !important; margin-bottom: 8px !important; }}
.ea-dashboard-hero {{ padding: 16px 20px; margin-bottom: 14px; }}
.course-header-box {{ padding: 16px 20px !important; margin-bottom: 14px !important; }}
.course-header-box h2 {{ font-size: 1.4rem !important; margin-top: 8px !important; }}
.ea-today-card {{ padding: 18px 22px 16px; }}
.ea-today-title {{ font-size: 1.3rem; }}
.ea-stats-card {{ padding: 14px 16px; }}
.quiz-question-card {{ padding: 14px 18px; margin-top: 10px; font-size: 1rem; }}
.trap-card, .explanation-card {{ padding: 12px 16px; margin: 10px 0; font-size: 0.97rem; }}
.rtl-box, .rtl-box p, .rtl-box li {{ font-size: 1.12rem !important; line-height: 2 !important; }}
.badge-subject {{ font-size: 0.76rem; padding: 3px 10px; }}
.badge-lang {{ font-size: 0.74rem; padding: 3px 9px; }}
.concept-tag {{ font-size: 0.78rem; padding: 2px 9px; }}
[data-testid="stSidebar"][aria-expanded="true"] {{ min-width: 200px !important; max-width: 200px !important; width: 200px !important; }}
[data-testid="stSidebar"] [data-testid="stRadioOption"], [data-testid="stSidebar"] [data-testid="stRadio"] div[role="radiogroup"] label {{ min-height: 34px !important; }}
[data-testid="stSidebar"] [data-testid="stRadioOption"] p {{ font-size: 0.9rem !important; }}
@media (max-width: 768px) {{ .block-container {{ padding: 2.8rem 0.8rem 3rem !important; }} }}
/* ---- THEME FIDELITY 6: high-specificity tabs text (Streamlit 1.65 BaseWeb) ---- */
div[data-testid="stTabs"] div[role="tablist"] button[data-baseweb="tab"],
div[data-testid="stTabs"] div[role="tablist"] button[data-baseweb="tab"] div,
div[data-testid="stTabs"] div[role="tablist"] button[data-baseweb="tab"] p,
div[data-testid="stTabs"] div[role="tablist"] button[data-baseweb="tab"] span {{
    color: var(--ea-text-muted) !important;
    -webkit-text-fill-color: var(--ea-text-muted) !important;
    opacity: 1 !important;
}}
div[data-testid="stTabs"] div[role="tablist"] button[data-baseweb="tab"]:hover,
div[data-testid="stTabs"] div[role="tablist"] button[data-baseweb="tab"]:hover p,
div[data-testid="stTabs"] div[role="tablist"] button[data-baseweb="tab"]:hover span {{
    color: var(--ea-text) !important;
    -webkit-text-fill-color: var(--ea-text) !important;
}}
div[data-testid="stTabs"] div[role="tablist"] button[data-baseweb="tab"][aria-selected="true"],
div[data-testid="stTabs"] div[role="tablist"] button[data-baseweb="tab"][aria-selected="true"] div,
div[data-testid="stTabs"] div[role="tablist"] button[data-baseweb="tab"][aria-selected="true"] p,
div[data-testid="stTabs"] div[role="tablist"] button[data-baseweb="tab"][aria-selected="true"] span {{
    background: var(--ea-primary) !important;
    background-color: var(--ea-primary) !important;
    color: var(--ea-on-primary) !important;
    -webkit-text-fill-color: var(--ea-on-primary) !important;
}}

/* ---- THEME FIDELITY 7: direct button[data-baseweb="tab"] ---- */
button[data-baseweb="tab"],
button[data-baseweb="tab"] * {{
    color: var(--ea-text-muted) !important;
    -webkit-text-fill-color: var(--ea-text-muted) !important;
    opacity: 1 !important;
}}
button[data-baseweb="tab"]:hover,
button[data-baseweb="tab"]:hover * {{
    color: var(--ea-text) !important;
    -webkit-text-fill-color: var(--ea-text) !important;
}}
button[data-baseweb="tab"][aria-selected="true"],
button[data-baseweb="tab"][aria-selected="true"] * {{
    background: var(--ea-primary) !important;
    background-color: var(--ea-primary) !important;
    color: var(--ea-on-primary) !important;
    -webkit-text-fill-color: var(--ea-on-primary) !important;
}}

/* ---- THEME FIDELITY 8: react-aria-ComboBox (Streamlit 1.65 selectbox) ---- */
.react-aria-ComboBox,
.react-aria-ComboBox [role="group"],
.st-emotion-cache-1dhx20m {{
    background-color: var(--ea-input-bg) !important;
    background: var(--ea-input-bg) !important;
    border-color: var(--ea-input-border) !important;
    color: var(--ea-text) !important;
}}
.react-aria-ComboBox input,
.st-emotion-cache-bezep1 {{
    background-color: transparent !important;
    background: transparent !important;
    color: var(--ea-text) !important;
    -webkit-text-fill-color: var(--ea-text) !important;
}}
.react-aria-ComboBox button,
.st-emotion-cache-1c009jo {{
    background-color: var(--ea-input-bg) !important;
    background: var(--ea-input-bg) !important;
    color: var(--ea-text-muted) !important;
    border: none !important;
}}
.react-aria-ComboBox button svg,
.st-emotion-cache-1c009jo svg {{
    fill: var(--ea-text-muted) !important;
    color: var(--ea-text-muted) !important;
}}
.react-aria-ListBox,
.react-aria-Popover {{
    background-color: var(--ea-surface) !important;
    background: var(--ea-surface) !important;
    color: var(--ea-text) !important;
    border: 1px solid var(--ea-border) !important;
}}
.react-aria-ListBoxItem,
.react-aria-ListBox [role="option"] {{
    background-color: transparent !important;
    color: var(--ea-text) !important;
    -webkit-text-fill-color: var(--ea-text) !important;
}}
.react-aria-ListBoxItem:hover,
.react-aria-ListBoxItem[data-focused="true"],
.react-aria-ListBoxItem[data-selected="true"],
.react-aria-ListBox [role="option"]:hover,
.react-aria-ListBox [role="option"][aria-selected="true"] {{
    background-color: var(--ea-surface-hover) !important;
    background: var(--ea-surface-hover) !important;
}}

/* ---- Background work indicator (stStatusWidget & stSpinner) ---- */
[data-testid="stStatusWidget"] {{
    visibility: visible !important;
    display: inline-flex !important;
    align-items: center !important;
    gap: 6px !important;
    background: var(--ea-surface) !important;
    color: var(--ea-text) !important;
    border: 1px solid var(--ea-border) !important;
    border-radius: 9999px !important;
    padding: 4px 12px !important;
    box-shadow: var(--ea-card-shadow) !important;
    font-size: 0.8rem !important;
    font-weight: 600 !important;
}}
[data-testid="stStatusWidget"] * {{
    color: var(--ea-text) !important;
}}
[data-testid="stStatusWidget"] svg {{
    color: var(--ea-primary) !important;
    fill: var(--ea-primary) !important;
}}
[data-testid="stSpinner"] {{
    background: var(--ea-surface) !important;
    border: 1px solid var(--ea-border) !important;
    border-radius: 10px !important;
    padding: 10px 14px !important;
    color: var(--ea-text) !important;
}}
[data-testid="stSpinner"] p {{
    color: var(--ea-text) !important;
    font-weight: 600 !important;
}}

/* ---- THEME FIDELITY 9: st.text (extracted PDF text) ---- */
[data-testid="stText"],
[data-testid="stText"] * {{
    color: var(--ea-text) !important;
    -webkit-text-fill-color: var(--ea-text) !important;
}}

</style>
"""

def _read_saved_theme() -> str:
    """Thème mémorisé : paramètre d'URL (survit au F5) puis cookie (survit aux sessions)."""
    for getter in (
        lambda: st.query_params.get("theme"),
        lambda: st.context.cookies.get("ea_theme"),
    ):
        try:
            val = getter()
        except Exception:
            val = None
        if val in ("dark", "light"):
            return val
    return "light"


def persist_theme(theme: str) -> None:
    """Applique le thème et le mémorise (URL + cookie 1 an)."""
    st.session_state["ea_theme"] = theme
    try:
        st.query_params["theme"] = theme
    except Exception:
        pass
    st.session_state["_ea_theme_cookie_pending"] = theme


if "ea_theme" not in st.session_state:
    st.session_state["ea_theme"] = _read_saved_theme()
current_theme = st.session_state.get("ea_theme", "light")
_pending_cookie = st.session_state.pop("_ea_theme_cookie_pending", None)
if _pending_cookie:
    st.components.v1.html(
        f"<script>try{{window.parent.document.cookie='ea_theme={_pending_cookie}; path=/; max-age=31536000; SameSite=Lax';}}catch(e){{}}</script>",
        height=0,
    )
st.markdown(get_custom_css(theme=current_theme), unsafe_allow_html=True)


NAV_SHORT_LABELS = {
    "📚 Mes Cours (Révisions)": "📚 Mes cours",
    "➕ Ajouter un Cours": "➕ Ajouter un cours",
    "📊 Mes Progrès": "📊 Progrès",
    "🏆 Mes Trophées": "🏆 Trophées",
    "🏆 Trophées & Badges": "🏆 Trophées",
    "⚙️ Paramètres & Sauvegardes": "⚙️ Réglages",
    "⚙️ Sauvegardes & Paramètres de l'élève": "⚙️ Réglages",
    "📊 Supervision Globale": "📊 Supervision",
    "👥 Gestion des Utilisateurs": "👥 Utilisateurs",
    "➕ Gestion & Ajout des Cours": "➕ Cours",
    "⚙️ Configuration Système & Sauvegardes": "⚙️ Système",
}


def nav_label(option: str) -> str:
    return NAV_SHORT_LABELS.get(option, option)


def render_html(html_str: str, sidebar: bool = False) -> None:
    """Affiche du HTML brut proprement sans passer par le parseur Markdown CommonMark."""
    target = st.sidebar if sidebar else st
    if hasattr(target, "html"):
        target.html(html_str)
    else:
        target.markdown(html_str, unsafe_allow_html=True)


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
    """Affiche un guide pas à pas clair et illustré pour obtenir une clé API Google Gemini 100% gratuite."""
    guide_dir = Path(__file__).parent / "assets" / "guide"
    step1_img = guide_dir / "gemini_step1_menu.png"
    step2_img = guide_dir / "gemini_step2_button.png"
    step3_img = guide_dir / "gemini_step3_table.png"

    with st.expander("💡 Comment obtenir votre clé API Google Gemini (100% Gratuite) ?", expanded=expanded):
        st.markdown(
            """
#### 🔑 Guide pas à pas illustré : Obtenir votre clé API Google Gemini gratuite

Google met à disposition une clé d'accès **100% gratuite** (mention officielle **"Niveau sans frais"**), sans carte bancaire, offrant un quota très généreux pour les cours, les révisions, les fiches express, la dictée vocale et les quiz avec Sanad.

---
##### 1️⃣ Étape 1 : Accéder à la page officielle des clés API
- Rendez-vous directement sur **[aistudio.google.com/api-keys](https://aistudio.google.com/api-keys)**.
- Connectez-vous avec votre compte Google (Gmail ordinaire ou compte scolaire).
- Dans le menu latéral de gauche sous **PROJET**, vérifiez que la section **"Clés API"** est bien sélectionnée :
            """
        )
        if step1_img.exists():
            st.image(str(step1_img), caption="Menu latéral gauche : PROJET > Clés API", width=240)

        st.markdown(
            """
---
##### 2️⃣ Étape 2 : Créer une nouvelle clé API
- En haut à droite de l'écran, cliquez sur le bouton :
            """
        )
        if step2_img.exists():
            st.image(str(step2_img), caption="Bouton en haut à droite : Créer une clé API", width=220)

        st.markdown(
            """
- Dans la boîte de dialogue qui s'affiche, choisissez **"Créer une clé API dans un nouveau projet"** (ou sélectionnez un projet existant).
- La clé sera créée instantanément en quelques secondes.

---
##### 3️⃣ Étape 3 : Copier votre clé API générée
- La fenêtre **"Détails de la clé API"** s'affiche avec votre nouvelle clé secrète.
- Cliquez directement sur le bouton **"Copier la clé"** en bas à droite (indiqué par la flèche rouge) ou sur l'icône de copie 📋 à côté de votre clé :
            """
        )
        if step3_img.exists():
            st.image(str(step3_img), caption="Fenêtre Détails de la clé API : cliquez sur 'Copier la clé' (flèche rouge) ou l'icône 📋", use_container_width=True)

        st.markdown(
            """
---
##### 4️⃣ Étape 4 : Activer votre clé dans Ecole Adnane
- Revenez sur cette page ci-dessous.
- Collez votre clé dans le champ prévu et cliquez sur **"💾 Enregistrer la clé"**.
- Cliquez ensuite sur **"🔍 Tester ma connexion Gemini"** pour valider : le badge vert s'allumera immédiatement !

> 💡 **Pourquoi une clé individuelle ?**  
> Chaque élève dispose ainsi de son propre quota gratuit et indépendant. Vos échanges avec le tuteur Sanad, la dictée vocale et vos révisions ne risquent jamais d'être ralentis par les autres utilisateurs.
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
            _hdr_rank = get_student_rank(student_id)
            st.markdown(f"### 📊 Progression de l'Élève : {_hdr_rank['emoji']} **{student_name}**")
            rank_desc = f"Rang {_hdr_rank['label']} {_hdr_rank['emoji']} • {_hdr_rank['badge_count']} trophée(s) débloqué(s)"
            if _hdr_rank.get("adjusted_for_failures"):
                rank_desc += f" • ⚠️ *{_hdr_rank.get('adjustment_reason')}*"
            st.caption(rank_desc)
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

        # Cartes métriques équitables (réussites & échecs)
        m1, m2, m3, m4, m5 = st.columns(5)
        with m1:
            st.metric("Total Quiz passés", stats.get("total_attempts", 0))
        with m2:
            st.metric("Questions répondues", stats.get("total_questions", 0))
        with m3:
            st.metric("Bonnes réponses", stats.get("total_score", 0))
        with m4:
            st.metric("❌ Erreurs commises", stats.get("total_errors", 0), help="Total des questions manquées nécessitant une consolidation")
        with m5:
            avg_rate = stats.get('average_success_rate', 0.0)
            fail_rate = stats.get('failure_rate', 0.0)
            st.metric("Moyenne générale", f"{avg_rate}%", delta=f"-{fail_rate}% échecs" if fail_rate > 0 else "0% échec", delta_color="inverse")

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

    top_c1, top_c2 = st.columns([7, 3])
    with top_c2:
        cur_t = st.session_state.get("ea_theme", "light")
        login_t = st.radio(
            "Thème",
            options=["🌙 Sombre", "☀️ Clair"],
            index=0 if cur_t == "dark" else 1,
            horizontal=True,
            label_visibility="collapsed",
            key="login_theme_toggle",
        )
        t_val = "dark" if "Sombre" in login_t else "light"
        if t_val != cur_t:
            persist_theme(t_val)
            st.rerun()

    col_login_c1, col_login_c2, col_login_c3 = st.columns([1, 2.2, 1])
    with col_login_c2:
        with st.container(border=True):
            brand_html = (
                '<div style="text-align: center; padding: 12px 10px 8px 10px;">'
                '<div style="width: 58px; height: 58px; border-radius: 16px; background: linear-gradient(135deg, #3b82f6 0%, #1d4ed8 100%); display: inline-flex; align-items: center; justify-content: center; font-size: 2rem; box-shadow: 0 8px 20px rgba(37,99,235,0.35); margin-bottom: 12px;">🎓</div>'
                '<h2 style="font-size: 1.8rem; font-weight: 800; margin-bottom: 4px; letter-spacing: -0.02em;">Ecole Adnane</h2>'
                '<p style="color: var(--ea-text-muted); font-size: 0.95rem; margin-bottom: 16px;">Plateforme d\'Apprentissage & Révision Scolaire (Maroc)</p>'
                '<div style="display: flex; justify-content: center; flex-wrap: wrap; gap: 6px; margin-bottom: 16px;">'
                '<span class="ea-hero-badge-pill" style="font-size: 0.72rem;">🤖 Tuteur IA Sanad</span>'
                '<span class="ea-hero-badge-pill" style="font-size: 0.72rem;">📚 Guides Visuels HD</span>'
                '<span class="ea-hero-badge-pill" style="font-size: 0.72rem;">🎧 Audio Neural</span>'
                '<span class="ea-hero-badge-pill" style="font-size: 0.72rem;">🏆 Trophées</span>'
                '</div>'
                '</div>'
            )
            render_html(brand_html)

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
                    admin_btn_html = (
                        f'<div style="margin: 14px 0 10px 0;">'
                        f'<a href="{auth_url}" target="_top" class="ea-google-signin-btn" onclick="if(window.top){{window.top.location.href=\'{auth_url}\'; return false;}}">'
                        f'<svg width="22" height="22" viewBox="0 0 24 24" style="flex-shrink:0;">'
                        f'<path fill="#4285F4" d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z"/>'
                        f'<path fill="#34A853" d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"/>'
                        f'<path fill="#FBBC05" d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.06H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.94l2.85-2.22.81-.63z"/>'
                        f'<path fill="#EA4335" d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.06l3.66 2.84c.87-2.6 3.3-4.52 6.16-4.52z"/>'
                        f'</svg>'
                        f'<span>Se connecter en tant qu\'Administrateur</span>'
                        f'</a>'
                        f'<div style="text-align: center; color: var(--ea-text-dim); font-size: 0.78rem; margin-top: 8px;">🔒 Connexion officielle sécurisée Google OAuth</div>'
                        f'</div>'
                    )
                    render_html(admin_btn_html)
                    if target_redirect.startswith("https://"):
                        st.caption(f"✨ Redirection configurée : `{target_redirect}`")
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
                target_redirect = default_redirect
                auth_url = get_google_auth_url(redirect_uri=target_redirect)

                if auth_url:
                    student_btn_html = (
                        f'<div style="margin: 14px 0 10px 0;">'
                        f'<a href="{auth_url}" target="_top" class="ea-google-signin-btn" onclick="if(window.top){{window.top.location.href=\'{auth_url}\'; return false;}}">'
                        f'<svg width="22" height="22" viewBox="0 0 24 24" style="flex-shrink:0;">'
                        f'<path fill="#4285F4" d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z"/>'
                        f'<path fill="#34A853" d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"/>'
                        f'<path fill="#FBBC05" d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.06H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.94l2.85-2.22.81-.63z"/>'
                        f'<path fill="#EA4335" d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.06l3.66 2.84c.87-2.6 3.3-4.52 6.16-4.52z"/>'
                        f'</svg>'
                        f'<span>Continuer avec Google</span>'
                        f'</a>'
                        f'<div style="text-align: center; color: var(--ea-text-dim); font-size: 0.78rem; margin-top: 10px;">🔒 Connexion officielle sécurisée Google OAuth</div>'
                        f'</div>'
                    )
                    render_html(student_btn_html)
                else:
                    st.warning("⚠️ Le portail de connexion Google est en attente d'initialisation par l'administrateur.")

        st.write("")

        # Mode Local / Démonstration repliable pour le développement et fonctionnement hors-ligne
        allow_dev_login = os.getenv("ALLOW_DEV_LOGIN", "").strip().lower() in ("true", "1", "yes")
        is_dedicated = os.getenv("IS_DEDICATED_SERVER", "").strip().lower() in ("true", "1", "yes")
        if allow_dev_login or (not is_dedicated and total_users == 0):
            with st.expander("🧪 Connexion de secours (Mode local hors-ligne)", expanded=False):
                st.caption("Permet de se connecter directement sans passer par Google Cloud pour tester hors-ligne.")
                col_d1, col_d2 = st.columns([2, 1])
                with col_d1:
                    dev_email = st.text_input("Adresse email :", value="", placeholder="nom@exemple.com", key="dev_email_input")
                    dev_name = st.text_input("Nom complet :", value="", placeholder="Votre nom", key="dev_name_input")
                with col_d2:
                    st.write("")
                    st.write("")
                    if st.button("🚀 Connexion Locale", type="secondary", use_container_width=True):
                        if dev_email.strip() and dev_name.strip():
                            u = dev_mode_login(email=dev_email.strip(), name=dev_name.strip())
                            st.success(f"Connecté en tant que {u['name']} ({u['role'].upper()})")
                            st.rerun()
                        else:
                            st.error("Veuillez renseigner un email et un nom.")

        st.stop()


def render_magnificent_trophy_grid(badges: List[Dict[str, Any]], cols_count: int = 2, is_ar: bool = False) -> None:
    """Affiche une grille de trophées avec un design somptueux, immersif et stimulant."""
    if not badges:
        st.info("لا توجد شارات لعرضها في هذه الفئة." if is_ar else "Aucun trophée à afficher dans cette catégorie.")
        return

    cols = st.columns(cols_count)
    for idx, badge in enumerate(badges):
        col = cols[idx % cols_count]
        with col:
            is_unlocked = badge.get("is_unlocked", False)
            unlocked_at = badge.get("unlocked_at")

            is_theme_dark = st.session_state.get("ea_theme", "dark") != "light"

            if is_unlocked:
                if is_theme_dark:
                    bg_style = "linear-gradient(135deg, rgba(30, 41, 59, 0.95) 0%, rgba(15, 23, 42, 0.98) 100%)"
                    border_color = "#f59e0b"
                    shadow_style = "0 8px 20px -4px rgba(245, 158, 11, 0.35), inset 0 1px 1px rgba(255, 255, 255, 0.15)"
                    title_color = "#fef08a"
                    desc_color = "#e2e8f0"
                    glow_aura = "radial-gradient(circle, rgba(245, 158, 11, 0.3) 0%, transparent 70%)"
                else:
                    bg_style = "linear-gradient(135deg, #ffffff 0%, #fffbeb 100%)"
                    border_color = "#f59e0b"
                    shadow_style = "0 6px 18px rgba(245, 158, 11, 0.18)"
                    title_color = "#92400e"
                    desc_color = "#334155"
                    glow_aura = "radial-gradient(circle, rgba(245, 158, 11, 0.15) 0%, transparent 70%)"
                badge_tag_text = "✨ تم الفوز به" if is_ar else "✨ DÉBLOQUÉ"
                badge_tag = (
                    f"<span style='background: linear-gradient(135deg, #10b981 0%, #059669 100%); "
                    f"color: #ffffff; padding: 4px 12px; border-radius: 20px; font-size: 0.75rem; "
                    f"font-weight: 800; letter-spacing: 0.5px; box-shadow: 0 2px 6px rgba(16, 185, 129, 0.4);'>"
                    f"{badge_tag_text}</span>"
                )
                icon_filter = "drop-shadow(0 0 10px rgba(251, 191, 36, 0.65))"
                pct = 100
                prog_val = 1.0
            else:
                badge_tag_text = "🔒 قيد الإنجاز" if is_ar else "🔒 EN COURS"
                if is_theme_dark:
                    bg_style = "linear-gradient(135deg, rgba(15, 23, 42, 0.75) 0%, rgba(2, 6, 23, 0.85) 100%)"
                    border_color = "#334155"
                    shadow_style = "0 4px 12px rgba(0, 0, 0, 0.3)"
                    title_color = "#cbd5e1"
                    desc_color = "#94a3b8"
                    badge_tag = (
                        f"<span style='background: rgba(51, 65, 85, 0.8); color: #94a3b8; padding: 4px 12px; "
                        f"border-radius: 20px; font-size: 0.75rem; font-weight: 700; letter-spacing: 0.5px; "
                        f"border: 1px solid #475569;'>{badge_tag_text}</span>"
                    )
                else:
                    bg_style = "#ffffff"
                    border_color = "#e2e8f0"
                    shadow_style = "0 2px 8px rgba(0, 0, 0, 0.05)"
                    title_color = "#475569"
                    desc_color = "#64748b"
                    badge_tag = (
                        f"<span style='background: #f1f5f9; color: #64748b; padding: 4px 12px; "
                        f"border-radius: 20px; font-size: 0.75rem; font-weight: 700; letter-spacing: 0.5px; "
                        f"border: 1px solid #cbd5e1;'>{badge_tag_text}</span>"
                    )
                glow_aura = "none"
                icon_filter = "grayscale(100%) opacity(0.38)"
                pct = badge.get("progress_percent", 0)
                prog_val = badge.get("progress_ratio", 0.0)

            card_dir = "direction: rtl !important; text-align: right !important;" if is_ar else ""
            mission_label = "🎯 <strong>المهمة :</strong>" if is_ar else "🎯 <strong>Mission :</strong>"
            target_label = f"الهدف : <strong>{badge['current_value']} / {badge['target_value']} {badge['unit']}</strong>" if is_ar else f"Objectif : <strong>{badge['current_value']} / {badge['target_value']} {badge['unit']}</strong>"

            card_html = f"""
            <div style="background: {bg_style}; border: 1.5px solid {border_color}; border-radius: 16px; padding: 18px 20px; margin-bottom: 14px; box-shadow: {shadow_style}; backdrop-filter: blur(12px); position: relative; overflow: hidden; {card_dir}">
                <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px; {card_dir}">
                    <div style="width: 52px; height: 52px; display: flex; align-items: center; justify-content: center; background: {glow_aura}; border-radius: 50%;">
                        <span style="font-size: 2.2rem; filter: {icon_filter}; line-height: 1;">{badge['icon']}</span>
                    </div>
                    <div>{badge_tag}</div>
                </div>
                <div style="font-size: 1.15rem; font-weight: 800; color: {title_color}; margin-bottom: 4px; letter-spacing: -0.2px;">
                    {badge['title']}
                </div>
                <div style="display: inline-block; background: rgba(59, 130, 246, 0.15); color: #93c5fd; padding: 2px 8px; border-radius: 6px; font-size: 0.72rem; font-weight: 600; margin-bottom: 8px;">
                    {badge.get('category', 'شارة' if is_ar else 'Trophée')}
                </div>
                <div style="font-size: 0.85rem; color: {desc_color}; line-height: 1.45; margin-bottom: 12px; min-height: 38px;">
                    {mission_label} {badge['description']}
                </div>
                <div style="display: flex; justify-content: space-between; align-items: center; font-size: 0.8rem; color: #94a3b8; margin-bottom: 6px; {card_dir}">
                    <span>{target_label}</span>
                    <span style="font-weight: 700; color: {'#34d399' if is_unlocked else '#60a5fa'};">{pct}%</span>
                </div>
            </div>
            """
            render_html(card_html)
            st.progress(prog_val)
            if is_unlocked and unlocked_at:
                date_str = str(unlocked_at)[:16]
                cap_txt = f"🎖️ تم الإنجاز بتاريخ {date_str} • *{badge['encouragement']}*" if is_ar else f"🎖️ Décroché le {date_str} • *{badge['encouragement']}*"
                st.caption(cap_txt)
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

    # ------------------------------------------------------------------
    # Barre de navigation supérieure (remplace le menu latéral)
    # ------------------------------------------------------------------
    user_cycle = get_pedagogical_cycle(current_user.get("age"), level=current_user.get("level"))
    _my_rank = None if is_admin else get_student_rank(logged_in_user_id)
    initial_letter = html.escape((current_user.get("name") or "A")[0].upper())
    user_name_esc = html.escape(str(current_user.get("name") or ""))
    user_email_esc = html.escape(str(current_user.get("email") or ""))
    role_txt = "👑 Admin" if is_admin else html.escape(str(user_cycle["badge_text"]))
    rank_txt = f"{_my_rank['emoji']} {html.escape(str(_my_rank['label']))} · " if _my_rank else ""
    current_theme = st.session_state.get("ea_theme", "dark")

    c_brand = st.sidebar.container()
    space_row = st.sidebar.container()
    c_nav = st.sidebar.container()
    st.sidebar.markdown('<div class="sb-spacer"></div>', unsafe_allow_html=True)
    c_user = st.sidebar.container()

    with c_brand:
        render_html('<div class="sb-brand"><span class="sb-logo">🎓</span><span class="sb-brand-name">Ecole Adnane</span></div>')

    is_global_admin_view = False
    active_user_id = logged_in_user_id
    active_student_info = None

    if is_admin:
        all_students = list_users(role="student")
        student_options: Dict[str, str] = {"global": "📊 Vue Globale (Supervision)"}
        _sel_ranks = get_student_ranks([s["id"] for s in all_students])
        for s in all_students:
            s_cycle = get_pedagogical_cycle(s.get("age"), level=s.get("level"))
            blocked_tag = " [SUSPENDU]" if s.get("is_blocked") else ""
            student_options[str(s["id"])] = f"{_sel_ranks[s['id']]['emoji']} {s_cycle['badge_text']} — {s['name']} ({s['email']}){blocked_tag}"

        if "pending_admin_space" in st.session_state:
            pending_space = str(st.session_state.pop("pending_admin_space"))
            if pending_space in student_options:
                st.session_state["admin_space_selector"] = pending_space

        with space_row:
            chosen_space = st.selectbox(
                "Espace de travail :",
                options=list(student_options.keys()),
                format_func=lambda x: "👁️ Espace : " + student_options[x],
                key="admin_space_selector",
                label_visibility="collapsed",
            )

        if chosen_space == "global":
            is_global_admin_view = True
            active_user_id = logged_in_user_id
            with c_nav:
                menu = st.radio(
                    "Supervision Globale",
                    [
                        "📊 Supervision Globale",
                        "👥 Gestion des Utilisateurs",
                        "➕ Gestion & Ajout des Cours",
                        "⚙️ Configuration Système & Sauvegardes",
                    ],
                    index=0,
                    format_func=nav_label,
                    label_visibility="collapsed",
                    key="topnav_admin",
                )
        else:
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

            with c_nav:
                menu = st.radio(
                    f"Espace de {active_student_info['name']}",
                    student_menu_items,
                    index=default_menu_idx,
                    key=f"admin_student_menu_{active_user_id}",
                    format_func=nav_label,
                    label_visibility="collapsed",
                )
    else:
        with c_nav:
            menu = st.radio(
                "Mon Espace d'Apprentissage",
                ["📚 Mes Cours (Révisions)", "➕ Ajouter un Cours", "📊 Mes Progrès", "🏆 Mes Trophées", "⚙️ Paramètres & Sauvegardes"],
                index=0,
                format_func=nav_label,
                label_visibility="collapsed",
                key="topnav_student",
            )

    # Indicateur IA pour l'utilisateur actif
    user_api_key = get_user_gemini_api_key(active_user_id)
    if is_global_admin_view and not user_api_key:
        user_api_key = get_gemini_api_key()
    has_openrouter_access = is_user_openrouter_allowed(active_user_id) and bool(get_openrouter_api_key())
    ai_ok = bool(user_api_key or has_openrouter_access)

    # Menu profil (popover) : tout le secondaire y est rangé
    with c_user:
        with st.popover(f"👤 {user_name_esc.split(' ')[0] if user_name_esc else 'Moi'}", use_container_width=True):
            render_html(
                f'<div class="sb-profile" title="{user_email_esc}">'
                f'<div class="sb-avatar">{initial_letter}</div>'
                '<div class="sb-profile-txt">'
                f'<div class="sb-name">{user_name_esc}</div>'
                f'<div class="sb-meta">{rank_txt}{role_txt}</div>'
                '</div></div>'
            )
            if not is_admin:
                try:
                    _sb_study = get_student_study_overview(logged_in_user_id)
                    _sb_pct = int(_sb_study["xp_in_level"] / _sb_study["xp_per_level"] * 100)
                    render_html(
                        '<div class="sb-xp">'
                        f'<span>🔥 {_sb_study["streak"]} j</span>'
                        f'<span>⭐ Niv. {_sb_study["level"]}</span>'
                        f'<span>🏆 {_my_rank["badge_count"]}</span>'
                        '</div>'
                        f'<div class="ea-bar small"><span style="width:{_sb_pct}%"></span></div>'
                    )
                except Exception:
                    pass

            if ai_ok:
                render_html(
                    '<div class="ai-status-pill"><span class="ai-pulse-dot"></span>'
                    f'<span>Tuteur IA actif · {"Gemini" if user_api_key else "OpenRouter"}</span></div>'
                )
            else:
                render_html('<div class="ai-status-pill warn"><span>🔑 Clé IA non configurée</span></div>')
                if not is_admin:
                    st.caption("👉 Clé gratuite sur [Google AI Studio](https://aistudio.google.com/api-keys).")
                    new_st_key = st.text_input("Clé Gemini :", type="password", key="sidebar_student_gemini_key", placeholder="AIzaSy...")
                    if st.button("Enregistrer ma clé", key="sidebar_save_gemini_btn", use_container_width=True):
                        if new_st_key:
                            save_user_gemini_api_key(active_user_id, new_st_key)
                            st.success("Clé enregistrée !")
                            st.rerun()

            _is_dark = current_theme == "dark"
            if st.button("☀️ Thème clair" if _is_dark else "🌙 Thème sombre", key="sidebar_theme_btn", use_container_width=True):
                persist_theme("light" if _is_dark else "dark")
                st.rerun()
            if st.button("🚪 Déconnexion", key="sidebar_logout_btn", use_container_width=True):
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

            _sum_ranks = get_student_ranks([s["user_id"] for s in students_summary])
            # Table interactive avec sélection de ligne unique
            df_rows = [
                {
                    "ID": s["user_id"],
                    "Nom": f"{_sum_ranks.get(s['user_id'], {}).get('emoji', '🌱')} {s['name']}",
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
                    f"{status_emoji} {_sum_ranks.get(s['user_id'], {}).get('emoji', '🌱')} {s['name']} ({student_lvl})",
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

        _ranks_map = get_student_ranks([u["id"] for u in filtered_users])
        for u in filtered_users:
            u_id = u["id"]
            is_self = (u_id == logged_in_user_id)
            is_u_blocked = (u.get("is_blocked", 0) == 1)
            is_u_admin = (u["role"] == "admin")

            is_u_or_allowed = is_user_openrouter_allowed(u_id)
            or_badge = " | 🌐 OpenRouter" if is_u_or_allowed else ""
            status_badge = "🔴 Suspendu" if is_u_blocked else "🟢 Actif"
            u_cycle = get_pedagogical_cycle(u.get("age"), level=u.get("level"))
            role_badge = "👑 Administrateur" if is_u_admin else u_cycle["badge_text"]
            self_tag = " *(Votre compte)*" if is_self else ""

            u_medal = "" if is_u_admin else f"{_ranks_map.get(u_id, {}).get('emoji', '🌱')} "
            expander_title = f"{role_badge} — {u_medal}**{u['name']}** (`{u['email']}`) | {status_badge}{or_badge}{self_tag}"
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

                # 4. Attribution de la clé OpenRouter globale
                st.markdown("---")
                col_u_or1, col_u_or2 = st.columns([3, 1])
                with col_u_or1:
                    st.markdown("##### 🌐 Accès à la Clé OpenRouter de l'École (Simulations & BD Animées)")
                    st.caption(
                        "Autorise cet utilisateur à bénéficier de la clé OpenRouter globale de l'administrateur sans qu'il ait besoin "
                        "de renseigner sa propre clé personnelle."
                    )
                with col_u_or2:
                    current_or_status = is_user_openrouter_allowed(u_id)
                    label_or = "🌐 Accès accordé" if current_or_status else "🔒 Accès refusé"
                    new_or_status = st.checkbox(
                        label_or,
                        value=current_or_status,
                        key=f"cb_or_access_{u_id}",
                        help="Cochez pour faire bénéficier cet élève de la clé OpenRouter de l'école.",
                    )
                    if new_or_status != current_or_status:
                        set_user_openrouter_access(u_id, new_or_status)
                        st.success(f"Accès OpenRouter mis à jour pour {u['name']} !")
                        st.rerun()

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
                help="Clé gratuite issue de https://aistudio.google.com/api-keys",
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

        st.markdown("### 🌐 Clé API OpenRouter Globale (Moteur Avancé & Simulations)")
        st.caption(
            "Cette clé est configurée exclusivement par l'administrateur. Vous pouvez l'affecter sélectivement aux élèves "
            "de votre choix depuis **'👥 Gestion Utilisateurs'** pour leur permettre de bénéficier des simulations animées sans clé personnelle."
        )

        current_or_key = get_openrouter_api_key() or ""
        current_or_model = get_openrouter_model()

        col_or1, col_or2 = st.columns([3, 1])
        with col_or1:
            new_or_key = st.text_input(
                "Clé API OpenRouter Globale :",
                value=current_or_key,
                type="password",
                placeholder="sk-or-v1-...",
                help="Clé OpenRouter globale d'administration.",
                key="input_admin_openrouter_key",
            )
        with col_or2:
            st.write("")
            st.write("")
            if st.button("💾 Enregistrer OpenRouter", type="primary", use_container_width=True, key="save_admin_or_btn"):
                if new_or_key.strip():
                    save_openrouter_api_key(new_or_key.strip())
                    st.success("Clé OpenRouter enregistrée avec succès !")
                    st.rerun()

        col_or_mod1, col_or_mod2 = st.columns([3, 1])
        with col_or_mod1:
            model_options = [
                "meta-llama/llama-3.3-70b-instruct",
                "openai/gpt-4o-mini",
                "google/gemini-2.5-flash",
                "anthropic/claude-3-haiku",
                "deepseek/deepseek-chat",
            ]
            default_mod_idx = model_options.index(current_or_model) if current_or_model in model_options else 0
            selected_or_model = st.selectbox(
                "Modèle OpenRouter par défaut :",
                options=model_options,
                index=default_mod_idx,
                help="Modèle utilisé pour générer les simulations interactives et bandes dessinées animées.",
                key="select_admin_or_model",
            )
            if selected_or_model != current_or_model:
                save_openrouter_model(selected_or_model)
        with col_or_mod2:
            st.write("")
            st.write("")
            if st.button("🔍 Tester OpenRouter", key="test_admin_or_btn", use_container_width=True):
                with st.spinner("Test OpenRouter en cours..."):
                    res_or = test_openrouter_connection(new_or_key or current_or_key, selected_or_model)
                    if res_or["success"]:
                        st.success(f"✅ {res_or['message']}")
                    else:
                        st.error(f"❌ {res_or['error']}")

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

        student_name_disp = html.escape(str(active_u_dict.get("name") or "Élève"))
        cycle_badge_disp = html.escape(str(active_u_cycle.get("badge_text", "Collège")))
        all_user_courses = list_courses(user_id=active_user_id)
        total_courses_count = len(all_user_courses)

        study = get_student_study_overview(active_user_id)
        _courses_by_id = {c["id"]: c for c in all_user_courses}
        _prog = study["courses"]

        def _cb_today_open(c_id: int) -> None:
            st.session_state["student_selected_course_id"] = c_id
            st.session_state["revision_view_segmented"] = "📖 Espace d'Étude Immergé"

        _in_catalog = st.session_state.get("revision_view_segmented", "🗂️ Catalogue des Cours") != "📖 Espace d'Étude Immergé"
        if _in_catalog:
            _hour = datetime.now().hour
            _greet = "Bonne soirée" if (_hour >= 18 or _hour < 5) else ("Bon après-midi" if _hour >= 12 else "Bonjour")
            _first_name = html.escape(str(active_u_dict.get("name") or "Élève").split()[0])
            _goal_done = study["today_attempts"] >= study["daily_goal"]
            _xp_pct = int(study["xp_in_level"] / study["xp_per_level"] * 100)

            # Prochaine action recommandée
            _next_id, _next_label, _next_cta = None, "", ""
            _weak = study["weak_course_id"]
            _last = study["last_course_id"]
            _untouched = next((c for c in all_user_courses if c["id"] not in _prog), None)
            if _weak in _courses_by_id:
                _next_id, _next_label, _next_cta = _weak, "À revoir pour progresser", "💪 Réviser maintenant"
            elif _untouched:
                _next_id, _next_label, _next_cta = _untouched["id"], "Nouveau cours à découvrir", "🚀 Commencer"
            elif _last in _courses_by_id:
                _next_id, _next_label, _next_cta = _last, "Continue où tu t'es arrêté", "▶️ Continuer"

            _streak_txt = f"{study['streak']} jour{'s' if study['streak'] > 1 else ''}" if study["streak"] else "à lancer !"
            tcol1, tcol2 = st.columns([1.6, 1])
            with tcol1:
                if _next_id:
                    _nc = _courses_by_id[_next_id]
                    _nbest = _prog.get(_next_id, {}).get("best", 0)
                    render_html(
                        '<div class="ea-today-card">'
                        f'<div class="ea-today-hello">{_greet} {_first_name} 👋</div>'
                        f'<div class="ea-today-kicker">{html.escape(_next_label)}</div>'
                        f'<div class="ea-today-title">{html.escape(_nc["title"])}</div>'
                        f'<div class="ea-today-sub">{html.escape(_nc["subject"])} · meilleur score {_nbest}%</div>'
                        f'<div class="ea-bar"><span style="width:{_nbest}%"></span></div>'
                        '</div>'
                    )
                    st.button(_next_cta, key="today_main_cta", type="primary", use_container_width=True,
                              on_click=_cb_today_open, args=(_next_id,))
                else:
                    render_html(
                        '<div class="ea-today-card">'
                        f'<div class="ea-today-hello">{_greet} {_first_name} 👋</div>'
                        '<div class="ea-today-title">Ajoute ton premier cours</div>'
                        '<div class="ea-today-sub">Va dans « ➕ Ajouter un Cours » pour téléverser un PDF.</div>'
                        '</div>'
                    )
            with tcol2:
                render_html(
                    '<div class="ea-stats-card">'
                    '<div class="ea-stat-row">'
                    f'<div class="ea-stat"><div class="ea-stat-ico">🔥</div><div><b>{_streak_txt}</b><small>Série</small></div></div>'
                    f'<div class="ea-stat"><div class="ea-stat-ico">⭐</div><div><b>{study["xp"]} XP</b><small>Niveau {study["level"]}</small></div></div>'
                    '</div>'
                    f'<div class="ea-stat-label">Vers le niveau {study["level"] + 1} · {study["xp_in_level"]}/{study["xp_per_level"]} XP</div>'
                    f'<div class="ea-bar"><span style="width:{_xp_pct}%"></span></div>'
                    f'<div class="ea-goal {"done" if _goal_done else ""}">'
                    f'{"✅ Objectif du jour atteint, bravo !" if _goal_done else "🎯 Objectif du jour : fais 1 quiz"}'
                    '</div>'
                    '</div>'
                )

        # Sujets rapides avec icônes
        pill_subject_map = {
            "✨ Toutes": None,
            "📐 Mathématiques": "Mathématiques",
            "🧪 Physique-Chimie": "Physique-Chimie",
            "🌱 SVT": "SVT",
            "🌍 Histoire-Géographie": "Histoire-Géographie",
            "📖 Langue Arabe": "اللغة العربية",
            "🇫🇷 Français": "Français",
            "🇬🇧 English": "English",
            "🕌 Éducation Islamique": "التربية الإسلامية",
            "💻 Informatique": "Informatique",
            "🧠 Philosophie": "الفلسفة",
        }

        # Obtenir les matières disponibles (inclut les équivalents AR/FR comme الاجتماعيات)
        available_subjects = {c.get("subject", "") for c in all_user_courses if c.get("subject")}
        subject_aliases = {
            "🌍 Histoire-Géographie": ["Histoire-Géographie", "الاجتماعيات"],
        }
        pill_options = ["✨ Toutes"]
        matched_subjects = set()
        for p_label, p_subj in pill_subject_map.items():
            if p_subj is None:
                continue
            candidates = subject_aliases.get(p_label, [p_subj])
            found = next((a for a in available_subjects if any(c in a for c in candidates)), None)
            if found:
                pill_subject_map[p_label] = found
                matched_subjects.add(found)
                if p_label not in pill_options:
                    pill_options.append(p_label)
        for extra_subj in sorted(available_subjects - matched_subjects):
            extra_label = f"📘 {extra_subj}"
            pill_subject_map[extra_label] = extra_subj
            if extra_label not in pill_options:
                pill_options.append(extra_label)

        selected_pill = st.pills(
            "Matières",
            options=pill_options,
            default="✨ Toutes",
            label_visibility="collapsed",
            key="revision_subject_pills",
        )
        selected_subject = pill_subject_map.get(selected_pill)

        col_s1, col_s2 = st.columns([3, 1])
        with col_s1:
            search_query = st.text_input("Rechercher un cours", placeholder="🔍 Rechercher un cours par titre ou notion...", label_visibility="collapsed")
        with col_s2:
            selected_lang = st.selectbox("Langue", ["Toutes", "Français", "English", "العربية"], label_visibility="collapsed")
            if selected_lang == "Français":
                lang_filter = "fr"
            elif selected_lang == "English":
                lang_filter = "en"
            elif selected_lang == "العربية":
                lang_filter = "ar"
            else:
                lang_filter = None

        raw_courses_list = list_courses(
            user_id=active_user_id,
            subject=selected_subject,
            language=lang_filter,
        )

        if search_query and search_query.strip():
            sq = search_query.strip().lower()
            courses_list = [c for c in raw_courses_list if sq in c.get("title", "").lower() or sq in c.get("subject", "").lower() or sq in (c.get("key_concepts") or "").lower()]
        else:
            courses_list = raw_courses_list

        if not courses_list:
            if is_admin:
                st.info(
                    "👋 Aucun cours ne correspond à ces critères. Utilisez le menu **➕ Gestion & Ajout des Cours** pour déposer vos documents PDF."
                )
            else:
                st.info(
                    "👋 **Aucun cours trouvé pour ce filtre.**\n\n"
                    "Essayez de réinitialiser le filtre ou rendez-vous dans le menu **➕ Ajouter un Cours** "
                    "pour téléverser vos premiers supports PDF."
                )
            return

        course_options = {c["id"]: f"{'🇲🇦 [AR]' if c['language'] == 'ar' else ('🇬🇧 [EN]' if c['language'] == 'en' else '🇫🇷 [FR]')} {c['subject']} — {c['title']}" for c in courses_list}

        # S'assurer qu'un cours actif valide existe
        saved_course_id = st.session_state.get("student_selected_course_id")
        if saved_course_id not in course_options:
            saved_course_id = list(course_options.keys())[0]
            st.session_state["student_selected_course_id"] = saved_course_id

        # Mode d'affichage : Catalogue visuel (Grille) vs Espace d'étude immersif (Workspace)
        CATALOG_VIEW = "🗂️ Catalogue des Cours"
        WORKSPACE_VIEW = "📖 Espace d'Étude Immergé"

        def _cb_open_course(c_id: int) -> None:
            st.session_state["student_selected_course_id"] = c_id
            st.session_state["revision_view_segmented"] = WORKSPACE_VIEW

        def _cb_back_to_catalog() -> None:
            st.session_state["revision_view_segmented"] = CATALOG_VIEW

        def _cb_switch_course(c_id: int) -> None:
            st.session_state["student_selected_course_id"] = c_id

        if "revision_view_segmented" not in st.session_state:
            st.session_state["revision_view_segmented"] = CATALOG_VIEW

        seg_col1, seg_col2 = st.columns([2, 1])
        with seg_col1:
            view_mode_choice = st.segmented_control(
                "Mode d'affichage",
                options=[CATALOG_VIEW, WORKSPACE_VIEW],
                key="revision_view_segmented",
                label_visibility="collapsed",
            )
            if not view_mode_choice:
                view_mode_choice = st.session_state.get("revision_view_segmented") or CATALOG_VIEW
                st.session_state["revision_view_segmented"] = view_mode_choice

        with seg_col2:
            st.caption(f"📚 **{len(courses_list)} cours** disponibles")

        st.write("")

        # -------------------------------------------------------------
        # VUE 1 : CATALOGUE DE COURS SOUS FORME DE GRILLE MODERNE
        # -------------------------------------------------------------
        if view_mode_choice == CATALOG_VIEW:
            num_cols = 3
            for i in range(0, len(courses_list), num_cols):
                row_courses = courses_list[i : i + num_cols]
                cols = st.columns(num_cols)
                for col, c in zip(cols, row_courses):
                    with col:
                        with st.container(border=True):
                            b_cls = get_subject_badge_class(c["subject"])
                            lang_flag = "🇲🇦 AR" if c["language"] == "ar" else ("🇬🇧 EN" if c["language"] == "en" else "🇫🇷 FR")
                            c_title = html.escape(c["title"])
                            c_subj = html.escape(c["subject"])

                            _cp = _prog.get(c["id"])
                            _best = _cp["best"] if _cp else 0
                            _stat_cls, _stat_txt = (
                                ("mastered", "✅ Maîtrisé") if _cp and _cp["status"] == "mastered"
                                else (("learning", "📈 En cours") if _cp else ("new", "🆕 À commencer"))
                            )
                            _raw_dt = str(c.get("created_at") or "")[:10]
                            _dt_disp = f"{_raw_dt[8:10]}/{_raw_dt[5:7]}/{_raw_dt[0:4]}" if len(_raw_dt) == 10 and _raw_dt[4] == "-" else _raw_dt
                            _dt_html = f'<span style="font-size:0.74rem; color:var(--ea-text-muted); font-weight:600;">📅 {_dt_disp}</span>' if _dt_disp else ""
                            st.markdown(
                                f'<div class="ea-card-stripe {b_cls}"></div>'
                                f'<div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:8px;">'
                                f'<span class="ea-card-status {_stat_cls}" style="margin-bottom:0;">{_stat_txt}</span>'
                                f'{_dt_html}'
                                f'</div>',
                                unsafe_allow_html=True,
                            )
                            st.markdown(
                                f'<div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:8px;">'
                                f'<span class="badge-subject {b_cls}">{c_subj}</span>'
                                f'<span class="badge-lang">{lang_flag}</span>'
                                f'</div>'
                                f'<div style="font-size:1.05rem; font-weight:800; line-height:1.35; margin-bottom:8px; min-height:48px; display:-webkit-box; -webkit-line-clamp:2; -webkit-box-orient:vertical; overflow:hidden;">'
                                f'{c_title}'
                                f'</div>',
                                unsafe_allow_html=True,
                            )

                            concepts = [k for k in (c.get("key_concepts") or []) if not is_generic_concept(k)][:3]
                            if concepts:
                                chips_html = " ".join([f'<span class="concept-tag" style="font-size:0.72rem; padding:2px 7px;">#{html.escape(k)}</span>' for k in concepts])
                                st.markdown(f'<div style="margin-bottom:10px; display:flex; flex-wrap:wrap; gap:4px; min-height:22px;">{chips_html}</div>', unsafe_allow_html=True)
                            else:
                                st.markdown('<div style="min-height:22px; margin-bottom:10px;"></div>', unsafe_allow_html=True)

                            # Badges des formats disponibles
                            has_guide = (Path(__file__).parent / "static" / "guides" / f"guide_course_{c['id']}.pdf").exists() or (Path(__file__).parent / "static" / "stories" / f"story_course_{c['id']}.pdf").exists()
                            ft_html = '<div style="display:flex; gap:6px; flex-wrap:wrap; margin-bottom:14px; font-size:0.75rem; color:#94a3b8;">'
                            ft_html += '<span style="background:rgba(255,255,255,0.06); padding:2px 6px; border-radius:4px;">📄 PDF</span>'
                            ft_html += '<span style="background:rgba(255,255,255,0.06); padding:2px 6px; border-radius:4px;">⚡ Fiche</span>'
                            if has_guide:
                                ft_html += '<span style="background:rgba(59,130,246,0.15); color:#60a5fa; padding:2px 6px; border-radius:4px; font-weight:600;">📚 Guide HD</span>'
                            ft_html += '<span style="background:rgba(16,185,129,0.15); color:#34d399; padding:2px 6px; border-radius:4px;">📝 Quiz</span>'
                            ft_html += '</div>'
                            st.markdown(ft_html, unsafe_allow_html=True)

                            st.markdown(
                                f'<div class="ea-bar small"><span style="width:{_best}%"></span></div>'
                                f'<div class="ea-card-score">{("Meilleur score : " + str(_best) + "%") if _cp else "Pas encore de quiz"}</div>',
                                unsafe_allow_html=True,
                            )
                            st.button(
                                "🚀 Étudier ce cours",
                                key=f"btn_open_card_{c['id']}",
                                type="primary",
                                use_container_width=True,
                                on_click=_cb_open_course,
                                args=(c["id"],),
                            )
            return

        # -------------------------------------------------------------
        # VUE 2 : ESPACE D'ÉTUDE IMMERSIF (WORKSPACE DÉDIÉ)
        # -------------------------------------------------------------
        active_course_id = st.session_state.get("student_selected_course_id")
        if active_course_id not in course_options:
            active_course_id = list(course_options.keys())[0]
            st.session_state["student_selected_course_id"] = active_course_id

        c_ids = list(course_options.keys())
        c_idx = c_ids.index(active_course_id) if active_course_id in c_ids else 0

        bar_col1, bar_col2, bar_col3 = st.columns([1.5, 2.5, 1.2])
        with bar_col1:
            st.button(
                "⬅️ Retour au Catalogue",
                key="ws_btn_back_catalog",
                use_container_width=True,
                on_click=_cb_back_to_catalog,
            )

        with bar_col2:
            new_selected_id = st.selectbox(
                "Changer de cours :",
                options=c_ids,
                index=c_idx,
                format_func=lambda x: course_options[x],
                label_visibility="collapsed",
                key="ws_fast_course_select",
            )
            if new_selected_id != active_course_id:
                st.session_state["student_selected_course_id"] = new_selected_id
                st.rerun()

        with bar_col3:
            p_col, n_col = st.columns(2)
            with p_col:
                st.button(
                    "◀️ Préc.",
                    disabled=(c_idx == 0),
                    key="ws_prev_course_btn",
                    help="Cours précédent",
                    use_container_width=True,
                    on_click=_cb_switch_course,
                    args=(c_ids[c_idx - 1] if c_idx > 0 else c_ids[0],),
                )
            with n_col:
                st.button(
                    "Suiv. ▶️",
                    disabled=(c_idx >= len(c_ids) - 1),
                    key="ws_next_course_btn",
                    help="Cours suivant",
                    use_container_width=True,
                    on_click=_cb_switch_course,
                    args=(c_ids[c_idx + 1] if c_idx < len(c_ids) - 1 else c_ids[-1],),
                )

        selected_course_id = active_course_id
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
            st.html(
                """
                <style>
                /* Support RTL complet pour le conteneur principal des onglets */
                .stTabs,
                div[data-testid="stTabs"],
                div.stTabs {
                    direction: rtl !important;
                }

                /* Barre des onglets (tablist) alignée à droite */
                .stTabs [role="tablist"],
                .stTabs div[role="tablist"],
                div[data-testid="stTabs"] [role="tablist"],
                div[data-testid="stTabs"] div[role="tablist"],
                div[role="tablist"],
                .stTabs [data-baseweb="tab-list"],
                div[data-testid="stTabs"] [data-baseweb="tab-list"] {
                    direction: rtl !important;
                    width: 100% !important;
                    display: flex !important;
                    flex-direction: row !important;
                    justify-content: flex-start !important;
                    text-align: right !important;
                }

                /* Boutons d'onglets individuels */
                .stTabs [data-testid="stTab"],
                .stTabs [role="tab"],
                .stTabs button[role="tab"],
                div[data-testid="stTabs"] [data-testid="stTab"],
                div[data-testid="stTabs"] [role="tab"],
                div[data-testid="stTabs"] button[role="tab"],
                button[data-testid="stTab"],
                button[role="tab"],
                .stTabs [data-baseweb="tab"],
                div[data-testid="stTabs"] [data-baseweb="tab"] {
                    direction: rtl !important;
                    text-align: right !important;
                    font-family: 'AdnaneSans', 'Noto Sans Arabic', 'Amiri', sans-serif !important;
                    font-size: 1.05rem !important;
                }

                .stTabs [data-testid="stTab"] p,
                .stTabs [role="tab"] p,
                .stTabs button[role="tab"] p,
                div[data-testid="stTabs"] [data-testid="stTab"] p,
                div[data-testid="stTabs"] [role="tab"] p,
                div[data-testid="stTabs"] button[role="tab"] p,
                button[role="tab"] p,
                .stTabs [data-baseweb="tab"] p,
                div[data-testid="stTabs"] [data-baseweb="tab"] p {
                    direction: rtl !important;
                    text-align: right !important;
                    font-family: 'AdnaneSans', 'Noto Sans Arabic', 'Amiri', sans-serif !important;
                }

                /* Panneaux de contenu des onglets */
                .stTabs [role="tabpanel"],
                div[data-testid="stTabs"] [role="tabpanel"],
                div[role="tabpanel"],
                .stTabs [data-baseweb="tab-panel"],
                div[data-testid="stTabs"] [data-baseweb="tab-panel"] {
                    direction: rtl !important;
                    text-align: right !important;
                }

                /* Boutons d'action dans les panneaux d'onglets (alignés à droite) */
                .stTabs [role="tabpanel"] div[data-testid="stButton"],
                div[data-testid="stTabs"] [role="tabpanel"] div[data-testid="stButton"] {
                    direction: rtl !important;
                    display: flex !important;
                    justify-content: flex-start !important;
                }
                .stTabs [role="tabpanel"] div[data-testid="stButton"] button,
                div[data-testid="stTabs"] [role="tabpanel"] div[data-testid="stButton"] button {
                    direction: rtl !important;
                    text-align: right !important;
                }

                /* Support RTL pour les boutons radio de quiz (strictement dans les onglets de cours) */
                .stTabs div[data-testid="stRadio"] {
                    direction: rtl !important;
                    text-align: right !important;
                }
                .stTabs div[data-testid="stRadio"] > div[role="radiogroup"] {
                    direction: rtl !important;
                    text-align: right !important;
                    display: flex !important;
                    flex-direction: column !important;
                    align-items: stretch !important;
                }
                .stTabs div[data-testid="stRadio"] label {
                    direction: rtl !important;
                    text-align: right !important;
                    display: flex !important;
                    flex-direction: row !important;
                    align-items: center !important;
                    justify-content: flex-start !important;
                    gap: 12px !important;
                    padding: 8px 12px !important;
                    border-radius: 8px !important;
                    transition: background 0.2s ease !important;
                    cursor: pointer !important;
                }
                .stTabs div[data-testid="stRadio"] label:hover {
                    background: rgba(255, 255, 255, 0.05) !important;
                }
                .stTabs div[data-testid="stRadio"] label > div:first-child {
                    margin-right: 0 !important;
                    margin-left: 10px !important;
                    flex-shrink: 0 !important;
                }
                .stTabs div[data-testid="stRadio"] label [data-testid="stMarkdownContainer"] {
                    direction: rtl !important;
                    text-align: right !important;
                    flex-grow: 1 !important;
                }
                .stTabs div[data-testid="stRadio"] label [data-testid="stMarkdownContainer"] p {
                    font-family: 'AdnaneNaskh', 'Noto Naskh Arabic', 'Amiri', serif !important;
                    font-size: 1.15rem !important;
                    line-height: 1.9 !important;
                    direction: rtl !important;
                    text-align: right !important;
                    margin: 0 !important;
                    cursor: pointer !important;
                }

                /* Blocs horizontaux et métriques RTL */
                .stTabs div[data-testid="stHorizontalBlock"] {
                    direction: rtl !important;
                }
                .stTabs div[data-testid="stMetric"] {
                    direction: rtl !important;
                    text-align: right !important;
                }
                .stTabs div[data-testid="stMetricLabel"] {
                    text-align: right !important;
                }
                .stTabs div[data-testid="stMetricValue"] {
                    text-align: right !important;
                }

                /* Alertes Streamlit RTL */
                .stTabs div[data-testid="stAlert"] {
                    direction: rtl !important;
                    text-align: right !important;
                }
                .stTabs div[data-testid="stAlert"] [data-testid="stMarkdownContainer"] {
                    direction: rtl !important;
                    text-align: right !important;
                }
                .stTabs div[data-testid="stAlert"] [data-testid="stMarkdownContainer"] p {
                    direction: rtl !important;
                    text-align: right !important;
                    font-family: 'AdnaneNaskh', 'Noto Naskh Arabic', serif !important;
                    font-size: 1.1rem !important;
                    line-height: 1.8 !important;
                }

                /* Expanders RTL */
                .stTabs div[data-testid="stExpander"] details summary {
                    direction: rtl !important;
                    text-align: right !important;
                    font-family: 'AdnaneSans', 'Noto Sans Arabic', sans-serif !important;
                    cursor: pointer !important;
                }
                .stTabs div[data-testid="stExpander"] details summary p {
                    direction: rtl !important;
                    text-align: right !important;
                    font-family: 'AdnaneSans', 'Noto Sans Arabic', sans-serif !important;
                    font-size: 1.05rem !important;
                    cursor: pointer !important;
                }
                </style>
                """
            )

        if is_ar:
            tab_doc, tab_fiche, tab_schema, tab_notions, tab_simulation, tab_quiz, tab_tuteur, tab_trophies = st.tabs([
                "📄 وثيقة الدرس",
                "⚡ بطاقة المراجعة",
                "🧠 خريطة ذهنية",
                "🎯 المفاهيم والمكتسبات",
                "📚 دليل مرئي وقصة مصورة (PDF)",
                "📝 تدريب الامتحان",
                "🤖 الأستاذ سند",
                "🏆 شارات وكؤوس الدرس",
            ])
        elif is_en:
            tab_doc, tab_fiche, tab_schema, tab_notions, tab_simulation, tab_quiz, tab_tuteur, tab_trophies = st.tabs([
                "📄 Course Document",
                "⚡ Revision Sheet",
                "🧠 Mind Map",
                "🎯 Key Concepts",
                "📚 Visual Guide & Storybook (PDF)",
                "📝 Exam Quiz",
                "🤖 AI Tutor (Sanad)",
                "🏆 Course Trophies",
            ])
        else:
            tab_doc, tab_fiche, tab_schema, tab_notions, tab_simulation, tab_quiz, tab_tuteur, tab_trophies = st.tabs([
                "📄 Le Document",
                "⚡ Fiche Express",
                "🧠 Carte Mentale",
                "🎯 Notions & Acquis",
                "📚 Guide Visuel & Album Illustré (PDF)",
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

            is_valid_pdf = bool(file_path and os.path.exists(file_path) and file_path.lower().endswith(".pdf"))

            if is_valid_pdf:
                static_pdf_dir = Path(__file__).parent / "static" / "pdf"
                static_pdf_dir.mkdir(parents=True, exist_ok=True)
                public_pdf = static_pdf_dir / f"course_{current_course['id']}.pdf"
                if not public_pdf.exists() or public_pdf.stat().st_size != os.path.getsize(file_path):
                    try:
                        shutil.copy2(file_path, public_pdf)
                    except Exception as e_cp:
                        logger.warning(f"Impossible de synchroniser static/pdf : {e_cp}")

                direct_url = f"/static/pdf/course_{current_course['id']}.pdf"

                with open(file_path, "rb") as f:
                    pdf_data = f.read()

                col_dl_link, col_dl_btn = st.columns([1.5, 1])
                with col_dl_link:
                    dl_main_label = "📥 Télécharger le PDF original (Lien direct)" if not is_ar else "📥 تحميل ملف PDF الأصلي (رابط مباشر)"
                    st.link_button(
                        label=dl_main_label,
                        url=direct_url,
                        type="primary",
                        use_container_width=True,
                    )
                with col_dl_btn:
                    dl_alt_label = "💾 Téléchargement alternatif" if not is_ar else "💾 تحميل بديل"
                    st.download_button(
                        label=dl_alt_label,
                        data=pdf_data,
                        file_name=current_course.get("file_name") or f"cours_{current_course['id']}.pdf",
                        mime="application/pdf",
                        key=f"dl_pdf_original_{current_course['id']}",
                        use_container_width=True,
                    )

                st.write("")
                render_html(
                    f'<iframe src="{direct_url}" width="100%" height="750px" style="border: 1px solid #cbd5e1; border-radius: 10px;"></iframe>'
                )
            else:
                guide_pdf = Path(__file__).parent / "static" / "guides" / f"guide_course_{current_course['id']}.pdf"
                story_pdf = Path(__file__).parent / "static" / "stories" / f"story_course_{current_course['id']}.pdf"

                alt_pdf_url = None
                alt_title = None
                if guide_pdf.exists() and guide_pdf.stat().st_size > 0:
                    alt_pdf_url = f"/static/guides/guide_course_{current_course['id']}.pdf"
                    alt_title = "Guide Visuel & Fiches de Révision PDF" if not is_ar else "دليل المراجعة البصري المصور (PDF)"
                elif story_pdf.exists() and story_pdf.stat().st_size > 0:
                    alt_pdf_url = f"/static/stories/story_course_{current_course['id']}.pdf"
                    alt_title = "Livre Illustré Didactique (PDF)" if not is_ar else "كتاب القصة التعليمية المصورة (PDF)"

                if alt_pdf_url:
                    st.info(
                        f"ℹ️ **Document PDF disponible :** Ce cours est consultable sous forme de **{alt_title}**."
                        if not is_ar else
                        f"ℹ️ **وثيقة PDF متوفرة :** هذا الدرس متوفر على شكل **{alt_title}**."
                    )
                    st.link_button(
                        label=f"📥 Télécharger le PDF ({alt_title})" if not is_ar else f"📥 تحميل وثيقة الـ PDF ({alt_title})",
                        url=alt_pdf_url,
                        type="primary",
                        use_container_width=True,
                    )
                    st.write("")
                    render_html(
                        f'<iframe src="{alt_pdf_url}" width="100%" height="750px" style="border: 1px solid #cbd5e1; border-radius: 10px;"></iframe>'
                    )
                else:
                    msg_warn = (
                        "⚠️ Fichier PDF original non trouvé sur le disque. Vous pouvez réimporter le document source dans **➕ Ajouter un Cours**."
                        if not is_ar else
                        "⚠️ لم يتم العثور على ملف الـ PDF الأصلي في القرص. يمكنك إعادة رفع الوثيقة الأصلية في **➕ إضافة درس**."
                    )
                    st.warning(msg_warn)

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
                        st.error("⚠️ Clé API Gemini requise. Obtenez votre clé 100% gratuite sur [Google AI Studio](https://aistudio.google.com/api-keys) et activez-la dans **⚙️ Paramètres** ou la barre latérale." if not is_en else "⚠️ Gemini API key required. Get your free key on [Google AI Studio](https://aistudio.google.com/api-keys) and configure it in **⚙️ Settings** or the sidebar.")
                    else:
                        with st.spinner("Génération de la fiche express..." if not is_en else "Generating revision sheet..."):
                            generated_summary = generate_revision_sheet(
                                raw_text=current_course.get("raw_text") or "",
                                subject=current_course["subject"],
                                language=current_course["language"],
                                user_id=active_user_id,
                            )
                            update_course_summary(current_course["id"], generated_summary, user_id=active_user_id)
                            try:
                                generate_or_get_course_fiche_mp3(
                                    course_id=current_course["id"],
                                    text=generated_summary,
                                    language=current_course.get("language", "fr"),
                                    user_id=active_user_id,
                                )
                            except Exception as e:
                                logger.warning(f"Pré-génération audio échouée : {e}")
                            st.rerun()
            else:
                # 1. Vérifier si le flux MP3 existe déjà en cache sur disque pour une lecture immédiate
                storage_root = get_db_path().parent
                c_uid = current_course.get("user_id")
                cand_mp3 = (storage_root / "users" / str(c_uid) / "cours" / f"fiche_{current_course['id']}.mp3") if c_uid else (storage_root / "cours" / f"fiche_{current_course['id']}.mp3")

                audio_data_uri = None
                if cand_mp3.exists() and cand_mp3.stat().st_size > 500:
                    try:
                        with open(cand_mp3, "rb") as f_mp3:
                            b64_audio = base64.b64encode(f_mp3.read()).decode("ascii")
                            audio_data_uri = f"data:audio/mp3;base64,{b64_audio}"
                    except Exception as e:
                        logger.warning(f"Impossible de lire le cache MP3 : {e}")
                else:
                    try:
                        mp3_path = generate_or_get_course_fiche_mp3(
                            course_id=current_course["id"],
                            text=fiche_md,
                            language=current_course.get("language", "fr"),
                            user_id=active_user_id,
                        )
                        if mp3_path and os.path.exists(mp3_path) and os.path.getsize(mp3_path) > 500:
                            with open(mp3_path, "rb") as f_mp3:
                                b64_audio = base64.b64encode(f_mp3.read()).decode("ascii")
                                audio_data_uri = f"data:audio/mp3;base64,{b64_audio}"
                    except Exception as e:
                        logger.warning(f"Erreur lors de la génération automatique du MP3 de la fiche: {e}")

                # 2. Barre de lecture vocale discrète type Sanad (hauteur 38px, pilule bleue/rouge)
                fiche_audio_html = generate_fiche_audio_player_html(
                    text=fiche_md,
                    language=current_course.get("language", "fr"),
                    player_id=f"fiche_audio_{current_course['id']}",
                    audio_data_uri=audio_data_uri,
                )
                if fiche_audio_html:
                    st.components.v1.html(fiche_audio_html, height=38)

                if is_ar:
                    st.markdown(f"<div class='rtl-box'>{fiche_md}</div>", unsafe_allow_html=True)
                    if get_arabic_tashkeel_ratio(fiche_md) < 0.40:
                        st.info("💡 بطاقة المراجعة غير مشكولة بالكامل بالحركات. يمكنك ضبطها بضغطة زر واحدة لتسهيل القراءة والنطق الصوتي السليم.")
                        if st.button("🔤 ضبط وتشكيل النص بالحركات التامة", key=f"btn_vocalize_{current_course['id']}", type="secondary"):
                            if not user_api_key:
                                st.error("⚠️ Clé API Gemini requise.")
                            else:
                                with st.spinner("جاري ضبط وتشكيل النص بالحركات التامة..."):
                                    vocalized = diacritize_arabic_text(fiche_md, user_id=active_user_id)
                                    update_course_summary(current_course["id"], vocalized, user_id=active_user_id)
                                    try:
                                        generate_or_get_course_fiche_mp3(
                                            course_id=current_course["id"],
                                            text=vocalized,
                                            language="ar",
                                            user_id=active_user_id,
                                        )
                                    except Exception as e:
                                        logger.warning(f"Régénération audio post-vocalisation échouée : {e}")
                                    st.rerun()
                else:
                    st.markdown(fiche_md)

                st.write("---")
                col_regen, col_mp3 = st.columns([0.45, 0.55], vertical_alignment="center")
                with col_regen:
                    regen_label = "🔄 إعادة توليد بطاقة المراجعة" if is_ar else ("🔄 Regenerate Revision Sheet" if is_en else "🔄 Régénérer la Fiche Express")
                    if st.button(regen_label, key=f"btn_regen_fiche_{current_course['id']}"):
                        if not user_api_key:
                            st.error("⚠️ Clé API Gemini requise. Obtenez votre clé 100% gratuite sur [Google AI Studio](https://aistudio.google.com/api-keys) et activez-la dans **⚙️ Paramètres** ou la barre latérale." if not is_en else "⚠️ Gemini API key required. Get your free key on [Google AI Studio](https://aistudio.google.com/api-keys) and configure it in **⚙️ Settings** or the sidebar.")
                        else:
                            with st.spinner("Régénération..." if not is_en else "Regenerating..."):
                                generated_summary = generate_revision_sheet(
                                    raw_text=current_course.get("raw_text") or "",
                                    subject=current_course["subject"],
                                    language=current_course["language"],
                                    user_id=active_user_id,
                                )
                                update_course_summary(current_course["id"], generated_summary, user_id=active_user_id)
                                try:
                                    generate_or_get_course_fiche_mp3(
                                        course_id=current_course["id"],
                                        text=generated_summary,
                                        language=current_course.get("language", "fr"),
                                        user_id=active_user_id,
                                    )
                                except Exception as e:
                                    logger.warning(f"Pré-génération audio échouée : {e}")
                                st.rerun()

                with col_mp3:
                    # Vérifier si le fichier MP3 hors-ligne existe déjà sur le disque
                    storage_root = get_db_path().parent
                    c_uid = current_course.get("user_id")
                    cand_mp3 = (storage_root / "users" / str(c_uid) / "cours" / f"fiche_{current_course['id']}.mp3") if c_uid else (storage_root / "cours" / f"fiche_{current_course['id']}.mp3")

                    if cand_mp3.exists() and cand_mp3.stat().st_size > 500:
                        dl_label = "📥 تحميل البودكاست الصوتي (MP3)" if is_ar else ("📥 Download Audio Podcast (MP3)" if is_en else "📥 Télécharger le podcast audio (MP3)")
                        with open(cand_mp3, "rb") as f_mp3:
                            st.download_button(
                                label=dl_label,
                                data=f_mp3.read(),
                                file_name=f"fiche_{current_course.get('file_name', 'cours').replace('.pdf', '')}.mp3",
                                mime="audio/mp3",
                                key=f"dl_mp3_fiche_{current_course['id']}",
                                use_container_width=True,
                            )
                    else:
                        gen_podcast_label = "🎙️ إنشاء بودكاست MP3 للتحميل" if is_ar else ("🎙️ Generate Offline MP3 Podcast" if is_en else "🎙️ Créer le podcast MP3 hors-ligne")
                        if st.button(gen_podcast_label, key=f"btn_gen_podcast_{current_course['id']}", use_container_width=True):
                            spin_pod = "جاري إنشاء البودكاست الصوتي..." if is_ar else ("Generating MP3 podcast..." if is_en else "Génération du podcast MP3...")
                            with st.spinner(spin_pod):
                                generate_or_get_course_fiche_mp3(
                                    course_id=current_course["id"],
                                    text=fiche_md,
                                    language=current_course.get("language", "fr"),
                                    user_id=current_course.get("user_id"),
                                    )
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
                    "💡 لم يتم إنشاء خريطة ذهنية لهذا الدرس بعد. انقر على الزر أدناه لتوليدها فوراً."
                    if is_ar
                    else ("💡 No mind map generated for this course yet. Click below to generate it instantly." if is_en else "💡 Ce cours ne possède pas encore de carte mentale interactive. Cliquez sur le bouton ci-dessous pour la générer en quelques secondes.")
                )
                if st.button(btn_gen_map, type="primary", key=f"btn_gen_mindmap_{current_course['id']}"):
                    if not user_api_key:
                        st.error("⚠️ Clé API Gemini requise." if not is_ar and not is_en else ("⚠️ يلزم مفتاح Gemini API." if is_ar else "⚠️ Gemini API key required."))
                    else:
                        spin_msg = "جاري إنشاء الخريطة الذهنية..." if is_ar else ("Generating mind map..." if is_en else "Génération de la carte mentale...")
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
                            st.success("تم توليد الخريطة الذهنية بنجاح !" if is_ar else ("Mind map generated successfully!" if is_en else "Carte mentale générée avec succès !"))
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
            if to_rev_count > 0:
                if is_ar:
                    st.warning(f"⚠️ تم تسجيل أخطاء في {to_rev_count} مفهوم(مفاهيم) في الاختبارات. راجعها مع الأستاذ سند لتدارك الصعوبات واستيعابها بنجاح !")
                elif is_en:
                    st.warning(f"⚠️ {to_rev_count} concept(s) have logged quiz errors. Review them with Sanad to reinforce your mastery!")
                else:
                    st.warning(f"⚠️ {to_rev_count} notion(s) ont enregistré des erreurs lors des quiz. Révisez-les avec Sanad pour combler vos lacunes !")
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
                        if is_ar:
                            st.markdown(f"<div class='rtl-box' style='font-size:1.15rem; font-weight:700;'>{idx + 1}. {c_title}</div>", unsafe_allow_html=True)
                        else:
                            st.markdown(f"**{idx + 1}. {c_title}**")
                        if c_ctx:
                            st.caption(c_ctx)
                    with col_badge:
                        badge_align = "left" if is_ar else "right"
                        st.markdown(f"<div style='text-align: {badge_align}; font-weight: 600;'>{badge_str}</div>", unsafe_allow_html=True)
                        if c_attempts > 0:
                            if is_ar:
                                st.caption(f"النتيجة : {c_rate}% ({c_attempts} اختبار)")
                            else:
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
                            sanad_sent_msg = "تم إرسال السؤال إلى سند ! توجه إلى تبويب 🤖 الأستاذ سند لقراءة إرشاداته." if is_ar else ("Sent to Sanad! Switch to the 🤖 Tutor tab to see his guidance." if is_en else "Question envoyée à Sanad ! Rendez-vous sur l'onglet 🤖 Tuteur Virtuel pour voir sa réponse.")
                            st.success(sanad_sent_msg)

                    with col_act2:
                        btn_quiz_link = "🎯 S'entraîner (Quiz)" if not is_ar else "🎯 تدرب على الأسئلة"
                        if st.button(btn_quiz_link if not is_en else "🎯 Practice Quiz", key=f"btn_quiz_concept_{idx}_{current_course['id']}", use_container_width=True):
                            quiz_hint_msg = "توجه إلى تبويب 📝 تدريب الامتحان لاختبار معلوماتك !" if is_ar else ("Go to the 📝 Exam Quiz tab to practice!" if is_en else "Rendez-vous sur l'onglet 📝 Entraînement Examen pour tester vos connaissances !")
                            st.info(quiz_hint_msg)

            st.write("")
            refresh_label = "🔄 Actualiser le diagnostic d'assimilation" if not is_ar else ("🔄 تحديث تشخيص الاستيعاب" if is_ar else "🔄 Refresh Mastery Diagnostic")
            if st.button(refresh_label, key=f"btn_sync_mastery_{current_course['id']}"):
                evaluate_and_sync_concept_mastery(active_user_id, current_course["id"])
                st.rerun()

        with tab_simulation:
            course_id = current_course["id"]
            course_subj = current_course.get("subject", "")
            course_tit = current_course.get("title", "")
            course_raw = f"{course_tit}\n\n{current_course.get('summary_markdown', '')}\n\n{current_course.get('raw_text', '')}".strip()
            course_lang = current_course.get("language") or ("ar" if is_ar else ("en" if is_en else "fr"))

            theme = detect_subject_theme(course_subj, course_tit)
            is_guide_recommended = theme["type"] in ("math", "physics_chemistry", "biology", "geography", "history")

            # Guide Explicatif Assets
            guide_deck = get_course_explanatory_guide(course_id)
            guide_pdf_url = get_course_explanatory_guide_pdf(course_id)
            guide_pdf_disk = Path(__file__).parent / "static" / "guides" / f"guide_course_{course_id}.pdf"
            guide_html_disk = Path(__file__).parent / "static" / "guides" / f"guide_course_{course_id}.html"
            has_guide = bool(guide_pdf_url or guide_pdf_disk.exists() or guide_html_disk.exists())

            # Storybook Assets
            story_scenario = get_course_story_scenario(course_id)
            story_pdf_url = get_course_story_pdf(course_id)
            anim_html = get_course_animation(course_id)
            pdf_path_disk = Path(__file__).parent / "static" / "stories" / f"story_course_{course_id}.pdf"
            html_path_disk = Path(__file__).parent / "static" / "stories" / f"story_course_{course_id}.html"
            has_story_pdf = bool(story_pdf_url or pdf_path_disk.exists())
            has_story_html = html_path_disk.exists()

            mode_options = ["guide", "story"]
            if is_ar:
                mode_labels = {
                    "guide": "📐 دليل مرئي وشرح تفاعلي (رياضيات، علوم، جغرافيا، تاريخ...)",
                    "story": "🎨 ألبوم قصة مصورة للأطفال (حكايات، تاريخ، أدب...)",
                }
            else:
                mode_labels = {
                    "guide": "📐 Guide Visuel Explicatif & PDF (Maths, Sciences, Géo, Histoire...)",
                    "story": "🎨 Album Histoire Illustré & PDF (Conte, Récit narratif)",
                }

            default_idx = 0 if is_guide_recommended else 1
            selected_mode = st.radio(
                "Format visuel :",
                options=mode_options,
                format_func=lambda x: mode_labels[x],
                label_visibility="collapsed",
                index=default_idx,
                key=f"sim_mode_selector_{course_id}",
            )
            st.write("")

            if selected_mode == "guide":
                if is_ar:
                    st.markdown("### 📐 الدليل المرئي التوضيحي وعرض الشرائح (PDF)")
                    st.caption("عرض توضيحي مركز على طريقة NotebookLM: مفاهيم أساسية، معادلات مبرزة، خطوات الحل، أمثلة امتحانات وفخاخ يجب تجنبها.")
                else:
                    st.markdown("### 📐 Guide Visuel Explicatif & Présentation Pédagogique (PDF)")
                    st.caption("Deck de diapositives 16:9 haute définition style NotebookLM : concepts clés, formules mises en valeur, méthodes pas-à-pas, exemples d'examen résolus et pièges à éviter.")

                if has_guide:
                    guide_viewer_url = f"/static/guides/guide_course_{course_id}.html"
                    guide_pdf_download = f"/static/guides/guide_course_{course_id}.pdf"

                    st.write("")
                    col_g_open, col_g_pdf, col_g_menu = st.columns([2.5, 2, 1.2])
                    with col_g_open:
                        st.link_button(
                            label="🚀 Ouvrir le Guide Explicatif dans un nouvel onglet" if not is_ar else "🚀 قراءة الدليل التفاعلي في نافذة جديدة ⛶",
                            url=guide_viewer_url,
                            type="primary",
                            use_container_width=True,
                        )
                    with col_g_pdf:
                        st.link_button(
                            label="📥 Télécharger le Guide PDF (Haute Résolution)" if not is_ar else "📥 تحميل دليل الدرس (PDF عالي الدقة)",
                            url=guide_pdf_download,
                            use_container_width=True,
                        )
                    with col_g_menu:
                        with st.popover("⚙️ Options" if not is_ar else "⚙️ خيارات"):
                            if st.button("🔄 Régénérer le Guide en 1 clic" if not is_ar else "🔄 إعادة إنشاء الدليل بالكامل", key=f"btn_regen_guide_all_{course_id}", type="primary"):
                                with st.status("Régénération du guide explicatif en cours..." if not is_ar else "جارٍ إعادة إنشاء الدليل...", expanded=True) as status_box:
                                    try:
                                        p_url, h_url = generate_complete_explanatory_guide(
                                            course_id=course_id,
                                            course_text=course_raw,
                                            subject=course_subj,
                                            course_title=course_tit,
                                            language=course_lang,
                                            user_id=active_user_id,
                                            force_images=True,
                                        )
                                        status_box.update(label="✅ Guide explicatif mis à jour !" if not is_ar else "✅ تم تحديث الدليل بنجاح!", state="complete", expanded=False)
                                        st.success("Guide mis à jour avec succès !" if not is_ar else "تم تحديث الدليل بنجاح!")
                                        st.rerun()
                                    except Exception as e_reg_g:
                                        status_box.update(label="❌ Erreur régénération" if not is_ar else "❌ حدث خطأ", state="error")
                                        st.error(f"Erreur : {e_reg_g}")

                    with st.expander("👁️ Aperçu intégré du guide explicatif" if not is_ar else "👁️ معاينة سريعة داخل الصفحة", expanded=False):
                        if guide_html_disk.exists():
                            st.components.v1.html(guide_html_disk.read_text(encoding="utf-8"), height=840, scrolling=True)

                    if guide_deck and guide_deck.get("slides"):
                        with st.expander("📋 Structure des diapositives explicatives" if not is_ar else "📋 هيكل الشرائح والمفاهيم", expanded=False):
                            st.markdown(f"#### ✦ {guide_deck.get('title', course_tit)} ✦")
                            ov_label = "نظرة عامة :" if is_ar else "Vue d'ensemble :"
                            if guide_deck.get("overview"):
                                st.info(f"**{ov_label}** {guide_deck.get('overview')}")
                            for sl in guide_deck.get("slides", []):
                                st.markdown(f"**{'الشريحة' if is_ar else 'Diapositive'} {sl.get('slide_num', '')} : {sl.get('title', '')}** ({sl.get('badge', '')})")
                                for pt in sl.get("key_points", []):
                                    st.markdown(f"- {pt}")
                                if sl.get("highlight_box", {}).get("content"):
                                    st.info(f"⚡ **{sl['highlight_box'].get('title', 'RÈGLE')}** : {sl['highlight_box'].get('content')}")
                                st.divider()
                else:
                    st.write("")
                    hero_title = "إنشاء الدليل المرئي التوضيحي والـ PDF" if is_ar else "Génération du Guide Visuel Explicatif & PDF"
                    hero_subtitle = "مثالي للرياضيات، الفيزياء والكيمياء، علوم الحياة والأرض والجغرافيا: شرح مرئي مركز بأسلوب NotebookLM." if is_ar else "Idéal pour les Mathématiques, la Physique-Chimie, les SVT et la Géographie : présentation ultra-claire style NotebookLM."
                    p1_title = "🎯 1. المفاهيم والقواعد" if is_ar else "🎯 1. Concepts & Formules"
                    p1_desc = "تعاريف بديهية، قواعد رياضية وقوانين فيزيائية مبرزة بشكل أنيق." if is_ar else "Définitions intuitives, formules mathématiques et lois physiques mises en valeur."
                    p2_title = "🔬 2. رسوم بيانية وتجارب" if is_ar else "🔬 2. Infographies & Schémas"
                    p2_desc = "مخططات هندسية وتجارب مخبرية وخرائط جغرافية ثلاثية الأبعاد." if is_ar else "Diagrammes géométriques, schémas de labo ou cartes géographiques par IA."
                    p3_title = "📝 3. أمثلة محلولة وPDF" if is_ar else "📝 3. Méthodes & Export PDF"
                    p3_desc = "خطوات الحل بالتفصيل، فخاخ الامتحانات وملف PDF عالي الدقة قابل للتحميل." if is_ar else "Exemples résolus pas-à-pas, pièges d'examen et compilation PDF 1376x768."

                    st.markdown(
                        f"""
                        <div style="background: linear-gradient(135deg, rgba(37, 99, 235, 0.12) 0%, rgba(14, 165, 233, 0.12) 100%); border: 1.5px solid {theme['primary']}; border-radius: 16px; padding: 22px; margin-bottom: 20px; box-shadow: 0 4px 18px rgba(0,0,0,0.25);">
                            <div style="display: flex; align-items: center; gap: 12px; margin-bottom: 12px;">
                                <span style="font-size: 32px;">{theme['icon']}</span>
                                <div>
                                    <h3 style="margin: 0; color: #ffffff; font-size: 19px; font-weight: 800;">{hero_title}</h3>
                                    <p style="margin: 3px 0 0 0; color: #94a3b8; font-size: 13.5px;">{hero_subtitle}</p>
                                </div>
                            </div>
                            <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 12px; margin-top: 14px;">
                                <div style="background: rgba(19, 27, 46, 0.85); border: 1px solid rgba(255, 255, 255, 0.1); border-radius: 12px; padding: 14px;">
                                    <strong style="color: {theme['primary']}; font-size: 14px;">{p1_title}</strong>
                                    <p style="font-size: 12.5px; color: #cbd5e1; margin: 4px 0 0 0; line-height: 1.4;">{p1_desc}</p>
                                </div>
                                <div style="background: rgba(19, 27, 46, 0.85); border: 1px solid rgba(255, 255, 255, 0.1); border-radius: 12px; padding: 14px;">
                                    <strong style="color: #34d399; font-size: 14px;">{p2_title}</strong>
                                    <p style="font-size: 12.5px; color: #cbd5e1; margin: 4px 0 0 0; line-height: 1.4;">{p2_desc}</p>
                                </div>
                                <div style="background: rgba(19, 27, 46, 0.85); border: 1px solid rgba(255, 255, 255, 0.1); border-radius: 12px; padding: 14px;">
                                    <strong style="color: #fbbf24; font-size: 14px;">{p3_title}</strong>
                                    <p style="font-size: 12.5px; color: #cbd5e1; margin: 4px 0 0 0; line-height: 1.4;">{p3_desc}</p>
                                </div>
                            </div>
                        </div>
                        """,
                        unsafe_allow_html=True,
                    )

                    btn_guide_label = "📐 Générer le Guide Visuel Explicatif & PDF (en 1 clic)" if not is_ar else "📐 إنشاء الدليل المرئي التوضيحي والـ PDF (بنقرة واحدة)"
                    if st.button(btn_guide_label, type="primary", use_container_width=True, key=f"btn_single_generate_guide_{course_id}"):
                        with st.status("Génération du Guide Visuel Explicatif en cours..." if not is_ar else "جارٍ إنشاء الدليل التوضيحي والـ PDF...", expanded=True) as status_box:
                            try:
                                st.write("📝 **Étape 1/2 :** Conception didactique des diapositives, formules et exemples par l'IA..." if not is_ar else "📝 **الخطوة 1/2 :** إعداد الشرائح التربوية والقواعد وأمثلة الحل...")
                                p_url, h_url = generate_complete_explanatory_guide(
                                    course_id=course_id,
                                    course_text=course_raw,
                                    subject=course_subj,
                                    course_title=course_tit,
                                    language=course_lang,
                                    user_id=active_user_id,
                                )
                                status_box.update(label="✅ Guide Visuel et PDF générés avec succès !" if not is_ar else "✅ تم إنشاء الدليل التوضيحي والـ PDF بنجاح!", state="complete", expanded=False)
                                st.success("Guide Visuel et PDF créés avec succès !" if not is_ar else "تم إنشاء الدليل التوضيحي والـ PDF بنجاح!")
                                st.rerun()
                            except Exception as e_guide_err:
                                status_box.update(label="❌ Erreur lors de la génération" if not is_ar else "❌ حدث خطأ أثناء الإنشاء", state="error")
                                st.error(f"Erreur : {e_guide_err}")

            else:
                # Mode Storybook
                if is_ar:
                    st.markdown("### 📚 كتاب القصة المصورة التفاعلي & PDF للأطفال")
                    st.caption("تحويل الدرس إلى قصة شيقة مصورة بالألوان المائية مع قراءة صوتية مشكولة بالكامل بصوت المعلم وتصدير بصيغة PDF عالية الجودة.")
                else:
                    st.markdown("### 📚 Livre d'Histoire Illustré & PDF Pédagogique")
                    st.caption("Transforme ce cours en un conte illustré à l'aquarelle avec narration vocale et téléchargement en album PDF haute définition (format 16:9).")

                if has_story_pdf or has_story_html or (anim_html and anim_html.strip()):
                    story_viewer_url = f"/static/stories/story_course_{course_id}.html" if has_story_html else f"/static/simulations/course_{course_id}.html"
                    pdf_download_url = f"/static/stories/story_course_{course_id}.pdf"

                    st.write("")
                    col_btn_open, col_btn_pdf, col_btn_menu = st.columns([2.5, 2, 1.2])
                    with col_btn_open:
                        st.link_button(
                            label="🚀 Ouvrir le Livre d'Histoire dans un nouvel onglet" if not is_ar else "🚀 قراءة كتاب القصة في نافذة جديدة ⛶",
                            url=story_viewer_url,
                            type="primary",
                            use_container_width=True,
                        )
                    with col_btn_pdf:
                        if has_story_pdf:
                            st.link_button(
                                label="📥 Télécharger le Livre PDF (Haute Résolution)" if not is_ar else "📥 تحميل كتاب القصة المصور (PDF)",
                                url=pdf_download_url,
                                use_container_width=True,
                            )
                        elif anim_html:
                            st.download_button(
                                label="📥 Télécharger (HTML)" if not is_ar else "📥 تحميل (HTML)",
                                data=anim_html,
                                file_name=f"histoire_cours_{course_id}.html",
                                mime="text/html",
                                key=f"dl_anim_{course_id}",
                                use_container_width=True,
                            )
                    with col_btn_menu:
                        with st.popover("⚙️ Options" if not is_ar else "⚙️ خيارات"):
                            if st.button("🔄 Tout Régénérer en 1 clic (Scénario + Peintures + PDF)" if not is_ar else "🔄 إعادة إنشاء الألبوم بالكامل (بنقرة واحدة)", key=f"btn_regen_all_{course_id}", type="primary"):
                                with st.status("Régénération complète de l'album..." if not is_ar else "جارٍ إعادة إنشاء الألبوم بالكامل...", expanded=True) as status_box:
                                    try:
                                        p_url, h_url = generate_complete_story_and_pdf(
                                            course_id=course_id,
                                            course_text=course_raw,
                                            subject=course_subj,
                                            course_title=course_tit,
                                            language=course_lang,
                                            user_id=active_user_id,
                                        )
                                        status_box.update(label="✅ Album régénéré avec succès !" if not is_ar else "✅ تم تحديث الألبوم بنجاح!", state="complete", expanded=False)
                                        st.success("Album régénéré avec succès !" if not is_ar else "تم تحديث الألبوم بنجاح!")
                                        st.rerun()
                                    except Exception as e_reg_all:
                                        status_box.update(label="❌ Erreur lors de la régénération" if not is_ar else "❌ حدث خطأ", state="error")
                                        st.error(f"Erreur : {e_reg_all}")

                    with st.expander("👁️ Aperçu intégré du livre d'histoire" if not is_ar else "👁️ معاينة سريعة داخل الصفحة", expanded=False):
                        if has_story_html:
                            story_content = html_path_disk.read_text(encoding="utf-8")
                            st.components.v1.html(story_content, height=840, scrolling=True)
                        elif anim_html:
                            st.components.v1.html(anim_html, height=840, scrolling=True)

                    if story_scenario and story_scenario.get("scenes"):
                        with st.expander("📖 Découpage scénaristique du conte pédagogique" if not is_ar else "📖 السيناريو التربوي وتفاصيل المشاهد", expanded=False):
                            st.markdown(f"#### ✦ {story_scenario.get('title', course_tit)} ✦")
                            if story_scenario.get("synopsis"):
                                st.info(f"**{'ملخص القصة :' if is_ar else 'Synopsis :'}** {story_scenario.get('synopsis')}")
                            for sc in story_scenario.get("scenes", []):
                                st.markdown(f"**{'المشهد' if is_ar else 'Scène'} {sc.get('scene_num', '')} : {sc.get('title', '')}**")
                                st.write(sc.get("narration", ""))
                                if sc.get("did_you_know"):
                                    st.caption(f"💡 *{'العبرة :' if is_ar else 'À retenir :'}* {sc.get('did_you_know')}")
                                st.divider()
                else:
                    st.write("")
                    st.markdown(
                        """
                        <div style="background: linear-gradient(135deg, rgba(37, 99, 235, 0.07) 0%, rgba(16, 185, 129, 0.07) 100%); border: 2px solid #3b82f6; border-radius: 16px; padding: 22px; margin-bottom: 20px;">
                            <div style="display: flex; align-items: center; gap: 12px; margin-bottom: 12px;">
                                <span style="font-size: 30px;">🎨</span>
                                <div>
                                    <h3 style="margin: 0; color: #1e3a8a; font-size: 19px;">Génération Complète de l'Album Histoire & PDF</h3>
                                    <p style="margin: 3px 0 0 0; color: #64748b; font-size: 13.5px;">Création automatique du conte jeunesse, des peintures aquarelle par IA, de l'audio et du livre PDF 16:9 haute résolution.</p>
                                </div>
                            </div>
                            <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 10px; margin-top: 14px;">
                                <div style="background: white; border: 1px solid #e2e8f0; border-radius: 10px; padding: 12px;">
                                    <strong style="color: #2563eb;">📝 1. Scénario Pédagogique</strong>
                                    <p style="font-size: 12.5px; color: #475569; margin: 4px 0 0 0;">Découpage en 4 à 5 scènes vivantes avec Tashkeel complet et morale éducative.</p>
                                </div>
                                <div style="background: white; border: 1px solid #e2e8f0; border-radius: 10px; padding: 12px;">
                                    <strong style="color: #059669;">🎨 2. Peintures Aquarelle IA</strong>
                                    <p style="font-size: 12.5px; color: #475569; margin: 4px 0 0 0;">Illustrations artistiques 16:9 widescreen captivantes pour chaque scène.</p>
                                </div>
                                <div style="background: white; border: 1px solid #e2e8f0; border-radius: 10px; padding: 12px;">
                                    <strong style="color: #d97706;">🔊 3. Audio & Export PDF</strong>
                                    <p style="font-size: 12.5px; color: #475569; margin: 4px 0 0 0;">Narration vocale intégrée et compilation en album PDF 1376x768 paysage.</p>
                                </div>
                            </div>
                        </div>
                        """ if not is_ar else """
                        <div style="background: linear-gradient(135deg, rgba(37, 99, 235, 0.07) 0%, rgba(16, 185, 129, 0.07) 100%); border: 2px solid #3b82f6; border-radius: 16px; padding: 22px; margin-bottom: 20px;">
                            <div style="display: flex; align-items: center; gap: 12px; margin-bottom: 12px;">
                                <span style="font-size: 30px;">🎨</span>
                                <div>
                                    <h3 style="margin: 0; color: #1e3a8a; font-size: 19px;">إنشاء ألبوم القصة المصور والـ PDF بنقرة واحدة</h3>
                                    <p style="margin: 3px 0 0 0; color: #64748b; font-size: 13.5px;">تأليف قصة للأطفال، رسم لوحات مائية بالذكاء الاصطناعي، تسجيل صوتي بالتشكيل وتصدير كتاب PDF عالي الدقة.</p>
                                </div>
                            </div>
                            <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 10px; margin-top: 14px;">
                                <div style="background: white; border: 1px solid #e2e8f0; border-radius: 10px; padding: 12px;">
                                    <strong style="color: #2563eb;">📝 1. سيناريو تربوي مشكول</strong>
                                    <p style="font-size: 12.5px; color: #475569; margin: 4px 0 0 0;">تقسيم الدرس إلى مشاهد شيقة مع تشكيل كامل وعبر تربوية مستفادة.</p>
                                </div>
                                <div style="background: white; border: 1px solid #e2e8f0; border-radius: 10px; padding: 12px;">
                                    <strong style="color: #059669;">🎨 2. لوحات مائية بالذكاء الاصطناعي</strong>
                                    <p style="font-size: 12.5px; color: #475569; margin: 4px 0 0 0;">لوحات فنية ساحرة 16:9 لكل مشهد تناسب الأطفال والناشئة.</p>
                                </div>
                                <div style="background: white; border: 1px solid #e2e8f0; border-radius: 10px; padding: 12px;">
                                    <strong style="color: #d97706;">🔊 3. قراءة صوتية وألبوم PDF</strong>
                                    <p style="font-size: 12.5px; color: #475569; margin: 4px 0 0 0;">تسجيل صوتي وتجميع ألبوم PDF عالي الدقة (1376x768) قابل للتحميل.</p>
                                </div>
                            </div>
                        </div>
                        """,
                        unsafe_allow_html=True,
                    )

                    btn_label = "🎨 Générer l'Album Histoire Illustré & PDF (en 1 clic)" if not is_ar else "🎨 إنشاء كتاب القصة المصور والـ PDF (بنقرة واحدة)"
                    if st.button(btn_label, type="primary", use_container_width=True, key=f"btn_single_generate_{course_id}"):
                        with st.status("Génération de l'Album d'Histoire en cours..." if not is_ar else "جارٍ إنشاء كتاب القصة والـ PDF...", expanded=True) as status_box:
                            try:
                                p_url, h_url = generate_complete_story_and_pdf(
                                    course_id=course_id,
                                    course_text=course_raw,
                                    subject=course_subj,
                                    course_title=course_tit,
                                    language=course_lang,
                                    user_id=active_user_id,
                                )
                                status_box.update(label="✅ Album Histoire et PDF générés avec succès !" if not is_ar else "✅ تم إنشاء كتاب القصة والـ PDF بنجاح!", state="complete", expanded=False)
                                st.success("Livre d'histoire et PDF créés avec succès !" if not is_ar else "تم إنشاء كتاب القصة والـ PDF بنجاح!")
                                st.rerun()
                            except Exception as e_oneclick:
                                status_box.update(label="❌ Erreur lors de la génération" if not is_ar else "❌ حدث خطأ أثناء الإنشاء", state="error")
                                st.error(f"Erreur : {e_oneclick}")

                if story_scenario and story_scenario.get("scenes"):
                    with st.expander("👁️ Voir les détails du scénario déjà rédigé" if not is_ar else "👁️ تفاصيل السيناريو المحفوظ", expanded=False):
                        st.json(story_scenario)

                with st.expander("🧪 Besoin d'une simulation scientifique interactive de laboratoire ?" if not is_ar else "🧪 هل تفضل تجربة محاكاة علمية تفاعلية؟", expanded=False):
                    st.caption("Convient particulièrement aux cours de Physique-Chimie, SVT ou Mathématiques complexes." if not is_ar else "مناسبة لدروس الفيزياء والكيمياء وعلوم الحياة والأرض.")
                    if st.button("✨ Générer une Simulation Scientifique" if not is_ar else "✨ توليد محاكاة علمية تفاعلية", key=f"btn_alt_sim_{course_id}"):
                        with st.spinner("Génération de la simulation de laboratoire..." if not is_ar else "جارٍ إنشاء المحاكاة..."):
                            try:
                                sim_code = generate_course_animation_simulation(
                                    course_text=course_raw,
                                    subject=course_subj,
                                    course_title=course_tit,
                                    language=course_lang,
                                    user_id=active_user_id,
                                    force_style="simulation",
                                )
                                if sim_code and "<html" in sim_code.lower():
                                    save_course_animation(course_id, sim_code)
                                    st.success("Simulation générée avec succès !" if not is_ar else "تم إنشاء المحاكاة بنجاح!")
                                    st.rerun()
                                else:
                                    st.error("Format inattendu.")
                            except Exception as e_alt:
                                st.error(f"Erreur : {e_alt}")

        with tab_quiz:

            latest_quiz = get_latest_quiz(current_course["id"], user_id=active_user_id)

            btn_new_quiz = "🎯 توليد اختبار تدريبي جديد (5 أسئلة)" if is_ar else ("🎯 Generate Exam Practice Quiz (5 questions)" if is_en else "🎯 Générer un nouveau quiz d'examen (5 questions)")
            if st.button(btn_new_quiz, type="secondary"):
                if not user_api_key:
                    st.error("⚠️ Clé API Gemini requise. Obtenez votre clé 100% gratuite sur [Google AI Studio](https://aistudio.google.com/api-keys) et activez-la dans **⚙️ Paramètres** ou la barre latérale." if not is_en else "⚠️ Gemini API key required. Get your free key on [Google AI Studio](https://aistudio.google.com/api-keys) and configure it in **⚙️ Settings** or the sidebar.")
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
                # Vérifier si le quiz a déjà été soumis dans la session ou en base de données (anti-triche)
                already_completed = has_user_completed_quiz(quiz_id, user_id=active_user_id)
                is_submitted = st.session_state.get(submission_key, False) or already_completed

                if already_completed and not st.session_state.get(submission_key, False):
                    # Alerte informative bienveillante indiquant que ce quiz a déjà été réalisé
                    if is_ar:
                        st.info("✅ لقد أكملت هذا الاختبار مسبقاً! للحصول على نقاط وتحديات جديدة وتثبيت مكتسباتك، اضغط على زر توليد اختبار جديد أعلاه أو بالأسفل.")
                    elif is_en:
                        st.info("✅ You have already completed this practice quiz! To practice further and earn new points, generate a new quiz below.")
                    else:
                        st.info("✅ Tu as déjà complété ce quiz d'entraînement ! Pour t'entraîner à nouveau et marquer de nouveaux points, génère un nouveau quiz.")

                answers_chosen = {}
                for idx, q in enumerate(questions):
                    if is_ar:
                        st.markdown(
                            f"""
                            <div class='quiz-question-card rtl-box'>
                                <div><span class='quiz-q-badge'>السؤال {idx + 1} من {len(questions)}</span></div>
                                <div style='font-size: 1.25rem; font-weight: 800; color: #ffffff; line-height: 1.6;'>{q['question']}</div>
                            </div>
                            """,
                            unsafe_allow_html=True,
                        )
                    else:
                        q_badge_txt = f"Question {idx + 1} of {len(questions)}" if is_en else f"Question {idx + 1} sur {len(questions)}"
                        st.markdown(
                            f"""
                            <div class='quiz-question-card'>
                                <div><span class='quiz-q-badge'>{q_badge_txt}</span></div>
                                <div style='font-size: 1.15rem; font-weight: 700; color: #ffffff; line-height: 1.5;'>{q['question']}</div>
                            </div>
                            """,
                            unsafe_allow_html=True,
                        )
                    options = q.get("options", [])
                    ans_idx = q.get("answer_index", 0)
                    explanation = q.get("explanation", "")
                    trap_alert = q.get("trap_alert", "")

                    selected_opt = st.radio(
                        f"اختيار السؤال {idx+1}:" if is_ar else (f"Choice for Q{idx+1}:" if is_en else f"Choix pour Q{idx+1}:"),
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
                            if is_ar:
                                st.success(f"✅ إجابة ممتازة وصحيحة ! ({options[ans_idx]})")
                            else:
                                st.success(f"✅ Excellente réponse ! ({options[ans_idx]})" if not is_en else f"✅ Excellent answer! ({options[ans_idx]})")
                        else:
                            if is_ar:
                                st.error(f"❌ الإجابة الصحيحة كانت : **{options[ans_idx]}**")
                            else:
                                st.error(f"❌ La bonne réponse était : **{options[ans_idx]}**" if not is_en else f"❌ The correct answer was: **{options[ans_idx]}**")

                        if explanation:
                            card_cls = "explanation-card-rtl" if is_ar else "explanation-card"
                            expl_title = "💡 شرح وتوضيح :" if is_ar else ("💡 Explanation:" if is_en else "💡 Explication :")
                            st.markdown(f"<div class='{card_cls}'><strong>{expl_title}</strong> {explanation}</div>", unsafe_allow_html=True)
                        if trap_alert:
                            trap_cls = "trap-card-rtl" if is_ar else "trap-card"
                            trap_title = "⚠️ فخ شائع في الامتحانات :" if is_ar else ("⚠️ Common Exam Trap:" if is_en else "⚠️ Piège classique :")
                            st.markdown(f"<div class='{trap_cls}'><strong>{trap_title}</strong> {trap_alert}</div>", unsafe_allow_html=True)

                if not is_submitted:
                    submit_label = "🏆 تأكيد إجاباتي وحساب النتيجة" if is_ar else ("🏆 Submit My Answers" if is_en else "🏆 Valider mes réponses")
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
                            cel_toast = f"🎉 تم فتح شارة جديدة في {c_title} : {nb['icon']} {nb['title']} !" if is_ar else f"🎉 Nouveau trophée débloqué sur {c_title} : {nb['icon']} {nb['title']} !"
                            st.toast(cel_toast, icon="🏆")

                        badges_str = " &bull; ".join([f"{b['icon']} <strong>{b['title']}</strong>" for b in c_badges])
                        if is_ar:
                            st.markdown(
                                f"""
                                <div class="rtl-box" style="background: linear-gradient(135deg, rgba(245, 158, 11, 0.22) 0%, rgba(180, 83, 9, 0.18) 100%); border: 1.5px solid #f59e0b; border-radius: 12px; padding: 14px 18px; margin-bottom: 16px; box-shadow: 0 4px 15px rgba(245, 158, 11, 0.25);">
                                    <div style="font-size: 1.15rem; font-weight: 800; color: #fbbf24; text-align: right; direction: rtl;">
                                        🏆 هنيئاً لك ! تم فتح شارات وكؤوس جديدة :
                                    </div>
                                    <div style="margin-top: 6px; color: #fef08a; font-size: 1.05rem; text-align: right; direction: rtl;">
                                        {badges_str}
                                    </div>
                                </div>
                                """,
                                unsafe_allow_html=True,
                            )
                        else:
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
                    if is_ar:
                        score_txt = f"<div class='rtl-box' style='font-size:1.35rem; font-weight:800; margin-top:12px; margin-bottom:12px;'>النتيجة المحصلة : <strong>{score} / {len(questions)}</strong></div>"
                        st.markdown(score_txt, unsafe_allow_html=True)
                    else:
                        score_txt = f"### Score obtenu : **{score} / {len(questions)}**" if not is_en else f"### Score: **{score} / {len(questions)}**"
                        st.markdown(score_txt)
                    if score >= len(questions) * 0.8 and not celebration:
                        st.balloons()

                    # Règle anti-triche : au lieu de recommencer le même quiz avec les réponses déjà connues,
                    # inviter l'élève à générer un tout nouveau quiz d'entraînement avec 5 nouvelles questions.
                    st.write("---")
                    btn_generate_next_quiz = (
                        "🎯 توليد اختبار تدريبي جديد (5 أسئلة جديدة)"
                        if is_ar else (
                            "🎯 Generate a New Practice Quiz (5 new questions)"
                            if is_en else
                            "🎯 Générer un nouveau quiz d'examen (5 nouvelles questions)"
                        )
                    )
                    st.caption(
                        "🔒 *Chaque quiz est à usage unique pour garantir un entraînement authentique. Pour retester tes compétences, génère un nouveau quiz !*"
                        if not is_ar and not is_en else (
                            "🔒 *كل اختبار صالح للاستخدام مرة واحدة لضمان تدريب حقيقي. لتجديد التحدي، قم بتوليد اختبار جديد!*"
                            if is_ar else
                            "🔒 *Each quiz is single-use for genuine practice. Generate a new quiz to practice again!*"
                        )
                    )
                    if st.button(btn_generate_next_quiz, type="primary", key=f"btn_next_quiz_{quiz_id}"):
                        if not user_api_key:
                            st.error("⚠️ Clé API Gemini requise.")
                        else:
                            with st.spinner("Génération de nouvelles questions..." if not is_en else "Generating new questions..."):
                                new_quiz_questions = generate_quiz(
                                    raw_text=current_course.get("raw_text") or "",
                                    subject=current_course["subject"],
                                    language=current_course["language"],
                                    num_questions=5,
                                    user_id=active_user_id,
                                )
                                save_quiz(current_course["id"], new_quiz_questions, user_id=active_user_id)
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
            toggle_label = (
                "قراءة صوتية تلقائية للردود 🔊"
                if is_ar
                else ("🔊 Auto-speak Sanad answers" if is_en else "🔊 Lecture vocale automatique des réponses")
            )
            popover_label = "⚙️ سرعة الصوت وإعداداته" if is_ar else ("⚙️ Voice Settings" if is_en else "⚙️ Vitesse & Réglages vocaux")
            slider_label = "سرعة النطق :" if is_ar else ("Voice Speed:" if is_en else "Vitesse de lecture :")
            speed_format = (
                (lambda x: f"{x}x" + (" (هادئة)" if x < 1.0 else (" (عادية)" if x == 1.0 else " (سريعة)")))
                if is_ar
                else (
                    (lambda x: f"{x}x" + (" (Slow)" if x < 1.0 else (" (Normal)" if x == 1.0 else " (Fast)")))
                    if is_en
                    else (lambda x: f"{x}x" + (" (Douce)" if x < 1.0 else (" (Normale)" if x == 1.0 else " (Rapide)")))
                )
            )
            voice_tech_caption = (
                "💡 **جودة استوديو بدون استهلاك رصيد :** أصوات مايكروسوفت العصبية فائقة الوضوح مع تشكيل عربي دقيق وتخزين فوري."
                if is_ar
                else (
                    "💡 **Studio quality with zero quota impact:** Microsoft Neural voices with instant caching."
                    if is_en
                    else "💡 **Qualité studio à zéro quota :** Voix neuronales Microsoft haute définition avec mise en cache instantanée."
                )
            )

            if is_ar:
                st.markdown(
                    """
                    <style>
                    div[data-testid="stToggle"] {
                        direction: rtl !important;
                        text-align: right !important;
                    }
                    div[data-testid="stToggle"] label {
                        flex-direction: row-reverse !important;
                        justify-content: flex-end !important;
                        gap: 12px !important;
                    }
                    div[data-testid="stToggle"] label p {
                        font-family: 'AdnaneSans', 'Cairo', sans-serif !important;
                        font-size: 0.95rem !important;
                        font-weight: 700 !important;
                        margin: 0 !important;
                    }
                    </style>
                    """,
                    unsafe_allow_html=True,
                )
                col_v_speed, col_v_toggle = st.columns([0.38, 0.62], vertical_alignment="center")
            else:
                col_v_toggle, col_v_speed = st.columns([0.62, 0.38], vertical_alignment="center")

            with col_v_toggle:
                auto_speak = st.toggle(
                    toggle_label,
                    value=stored_auto_speak,
                    key=f"auto_speak_toggle_{current_course['id']}",
                )
                if auto_speak != stored_auto_speak:
                    set_user_setting(active_user_id, "auto_speak_sanad", "true" if auto_speak else "false")

            with col_v_speed:
                with st.popover(popover_label, use_container_width=True):
                    voice_speed = st.select_slider(
                        slider_label,
                        options=[0.8, 0.9, 1.0, 1.1, 1.2],
                        value=stored_speed if stored_speed in [0.8, 0.9, 1.0, 1.1, 1.2] else 1.0,
                        format_func=speed_format,
                        key=f"voice_speed_slider_{current_course['id']}",
                    )
                    if voice_speed != stored_speed:
                        set_user_setting(active_user_id, "voice_speed_sanad", str(voice_speed))
                    st.caption(voice_tech_caption)

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

            # Ancre basse pour l'auto-scroll fluide de la conversation
            st.html("<div id='sanad_chat_bottom_anchor' style='height: 1px; width: 100%; margin: 8px 0;'></div>")

            # Réinitialiser le déclencheur de lecture automatique après affichage
            if has_auto_trigger:
                st.session_state[trigger_auto_key] = False

            # Injection discrète de l'icône micro directement sur le champ st.chat_input à côté du bouton envoyer
            effective_gemini_key = user_api_key or get_setting("GEMINI_API_KEY") or os.getenv("GEMINI_API_KEY") or ""
            mic_injector_html = generate_chat_mic_injector_html(
                language=current_course.get("language", "fr"),
                widget_id=f"mic_chat_{current_course['id']}",
                gemini_api_key=effective_gemini_key,
            )
            if mic_injector_html:
                st.components.v1.html(mic_injector_html, height=0)

            if st.session_state.pop("sanad_scroll_to_bottom", False):
                st.components.v1.html(
                    """<script>
                    (function(){
                        function go(){
                            try{
                                var doc = window.parent.document;
                                var el = doc.getElementById('sanad_chat_bottom_anchor');
                                if(el){ el.scrollIntoView({behavior:'auto', block:'end'}); }
                                var main = doc.querySelector('section[data-testid="stMain"]') || doc.querySelector('[data-testid="stAppViewContainer"]');
                                if(main){ main.scrollTop = main.scrollHeight; }
                            }catch(e){}
                        }
                        setTimeout(go, 120);
                        setTimeout(go, 450);
                        setTimeout(go, 900);
                    })();
                    </script>""",
                    height=0,
                )
            chat_placeholder = "اطرح سؤالك على الأستاذ المساعد سند..." if is_ar else ("Ask Sanad a question about this lesson..." if is_en else "Pose ta question à Sanad...")
            user_input = st.chat_input(chat_placeholder)
            prompt_to_send = user_input or suggested_prompt
            if prompt_to_send:
                if not user_api_key:
                    st.error("⚠️ Clé API Gemini requise pour échanger avec Sanad. Obtenez votre clé 100% gratuite sur [Google AI Studio](https://aistudio.google.com/api-keys) et activez-la dans **⚙️ Paramètres** ou la barre latérale." if not is_en else "⚠️ Gemini API key required to chat with Sanad. Get your free key on [Google AI Studio](https://aistudio.google.com/api-keys) and configure it in **⚙️ Settings** or the sidebar.")
                else:
                    add_chat_message(current_course["id"], "user", prompt_to_send, user_id=active_user_id)
                    with st.chat_message("user", avatar="🧑‍🎓"):
                        st.markdown(prompt_to_send)
                    st.html("<div id='sanad_chat_bottom_anchor' style='height: 1px; width: 100%; margin: 8px 0;'></div>")
                    st.session_state["sanad_scroll_to_bottom"] = True

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

                            # Détection de validation d'assimilation par Sanad ([CONCEPT_ACQUIS: ...])
                            found_concepts = re.findall(r"\[CONCEPT_ACQUIS:\s*([^\]]+)\]", reply, flags=re.IGNORECASE)
                            cleaned_reply = re.sub(r"\n*\[CONCEPT_ACQUIS:\s*[^\]]+\]", "", reply).strip()

                            if found_concepts:
                                for fc in found_concepts:
                                    fc_clean = fc.strip().strip('"').strip("'")
                                    if fc_clean:
                                        mark_concept_mastered_by_sanad(
                                            user_id=active_user_id,
                                            course_id=current_course["id"],
                                            concept_title=fc_clean,
                                        )
                                evaluate_and_sync_concept_mastery(active_user_id, current_course["id"])
                                new_tutor_badges = evaluate_and_award_course_badges(active_user_id, current_course["id"])
                                if new_tutor_badges:
                                    st.session_state["pending_trophy_celebration"] = {
                                        "course_title": current_course["title"],
                                        "badges": new_tutor_badges,
                                    }
                                for fc in found_concepts:
                                    if is_ar:
                                        st.toast(f"🎉 أحسنت! أثبتت استيعابك لمفهوم: {fc.strip()} خلال حوارك مع سند!", icon="🧠")
                                    elif is_en:
                                        st.toast(f"🎉 Great job! You proved your mastery of: {fc.strip()} with Sanad!", icon="🧠")
                                    else:
                                        st.toast(f"🎉 Bravo ! Sanad a validé ta maîtrise de la notion : {fc.strip()} !", icon="🧠")

                            add_chat_message(current_course["id"], "assistant", cleaned_reply, user_id=active_user_id)
                            if is_ar:
                                st.markdown(f"<div class='rtl-box'>{cleaned_reply}</div>", unsafe_allow_html=True)
                            else:
                                st.markdown(cleaned_reply)
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
            banner_dir = "direction: rtl !important;" if is_ar else ""
            st.markdown(
                f"""
                <div style="background: linear-gradient(135deg, rgba(30, 41, 59, 0.95) 0%, rgba(15, 23, 42, 0.98) 100%); border: 1.5px solid #f59e0b; border-radius: 14px; padding: 16px 20px; margin-bottom: 20px; box-shadow: 0 4px 14px rgba(245, 158, 11, 0.2); {banner_dir}">
                    <div style="display: flex; justify-content: space-between; align-items: center; {banner_dir}">
                        <div style="text-align: {'right' if is_ar else 'left'};">
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
            render_magnificent_trophy_grid(c_overview.get("badges", []), cols_count=2, is_ar=is_ar)

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
            if "last_ingest_summary" in st.session_state:
                st.success(st.session_state.pop("last_ingest_summary"))
            uploaded_files = st.file_uploader(
                "Sélectionnez un ou plusieurs fichiers PDF :",
                type=["pdf"],
                accept_multiple_files=True,
                key=f"course_pdf_uploader_{st.session_state.get('pdf_uploader_nonce', 0)}",
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

                    st.session_state["last_ingest_summary"] = f"✅ Bilan : {success_count} cours ajouté(s), {dup_count} doublon(s)."
                    st.session_state["pdf_uploader_nonce"] = st.session_state.get("pdf_uploader_nonce", 0) + 1
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

        m1, m2, m3, m4, m5 = st.columns(5)
        with m1:
            st.metric("Total Quiz passés", stats.get("total_attempts", 0))
        with m2:
            st.metric("Questions répondues", stats.get("total_questions", 0))
        with m3:
            st.metric("Bonnes réponses", stats.get("total_score", 0))
        with m4:
            st.metric("❌ Erreurs à corriger", stats.get("total_errors", 0), help="Nombre de questions où tu t'es trompé pour t'aider à progresser")
        with m5:
            avg_rate = stats.get('average_success_rate', 0.0)
            fail_rate = stats.get('failure_rate', 0.0)
            st.metric("Moyenne générale", f"{avg_rate}%", delta=f"-{fail_rate}% échecs" if fail_rate > 0 else "0% échec", delta_color="inverse")

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
                help="Gratuite sur https://aistudio.google.com/api-keys sans carte de crédit.",
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
