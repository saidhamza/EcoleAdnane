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
PROJECT_ROOT = Path(__file__).resolve().parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import streamlit as st

from models.database import (
    add_chat_message,
    clear_chat_history,
    delete_course,
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
    update_course_metadata,
    update_course_summary,
)
from services.ai_engine import (
    classify_and_extract_metadata,
    generate_quiz,
    generate_revision_sheet,
    socratic_tutor_response,
)
from services.auth_manager import (
    dev_mode_login,
    exchange_code_for_user,
    extract_auth_code,
    get_google_auth_url,
    get_oauth_credentials,
    init_session_state,
    is_oauth_configured,
    logout_user,
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
from services.pdf_parser import SUBJECTS_AR, SUBJECTS_FR

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


# ===========================================================================
# 0. GESTION DE L'AUTHENTIFICATION & SESSIONS GOOGLE OAUTH
# ===========================================================================

init_session_state()

# Vérification du retour de code Google OAuth via query params
if "code" in st.query_params:
    oauth_code = st.query_params["code"]
    try:
        authenticated_user = exchange_code_for_user(oauth_code)
        set_session_user(authenticated_user)
        st.query_params.clear()
        st.success(f"🎉 Bienvenue, {authenticated_user['name']} !")
        st.rerun()
    except Exception as e:
        st.error(f"❌ Échec de connexion Google : {str(e)}")
        st.query_params.clear()

# Écran de verrouillage si l'utilisateur n'est pas encore connecté
if not st.session_state.get("is_authenticated"):
    total_users = get_user_count()

    col_login_c1, col_login_c2, col_login_c3 = st.columns([1, 2, 1])
    with col_login_c2:
        st.write("")
        st.write("")
        st.markdown("<h1 style='text-align:center;'>🎓 Ecole Adnane</h1>", unsafe_allow_html=True)
        st.markdown(
            "<p style='text-align:center; color:var(--text-color, #94a3b8); font-size:1.1rem;'>"
            "Plateforme Multi-Utilisateurs de Révision & Préparation au Brevet 3AC Maroc"
            "</p>",
            unsafe_allow_html=True,
        )

        st.divider()

        # Règle : Initialisation administrateur si table vide
        if total_users == 0:
            st.info(
                "📢 **Initialisation du système : Veuillez vous connecter avec le compte Google Administrateur**\n\n"
                "Le tout premier compte Google qui se connecte recevra **automatiquement et définitivement le rôle Administrateur** de la plateforme.",
                icon="👑",
            )
        else:
            st.markdown(
                "### 🔐 Connexion à votre espace personnel\n"
                "Connectez-vous pour accéder à vos cours, vos quiz d'entraînement et votre tuteur virtuel Sanad."
            )

        # Configuration de l'URI de redirection
        creds_info = get_oauth_credentials()
        default_redirect = creds_info.get("redirect_uri") or "http://localhost"

        col_opt1, col_opt2 = st.columns([1, 1])
        with col_opt1:
            use_direct_8501 = st.checkbox(
                "Redirection directe vers :8501",
                value=False,
                help="Activez uniquement si vous avez ajouté http://localhost:8501 dans les 'URI de redirection autorisés' de votre console Google Cloud.",
            )

        target_redirect = "http://localhost:8501" if use_direct_8501 else default_redirect
        auth_url = get_google_auth_url(redirect_uri=target_redirect)

        if auth_url:
            st.link_button(
                "🔑 1. Se connecter avec Google",
                url=auth_url,
                type="primary",
                use_container_width=True,
            )
            st.caption(f"🎯 URI envoyée à Google : `{target_redirect}`")
        else:
            st.warning("⚠️ Les identifiants Google OAuth ne sont pas encore configurés dans `credentials.json` ou dans les Secrets Streamlit.")

        # Option de finalisation : Collage direct d'URL ou de code de redirection
        with st.expander("🔗 2. Finaliser la connexion Google (si redirection locale bloquée)", expanded=True):
            st.markdown(
                "Après avoir cliqué sur **Se connecter avec Google** et validé votre compte :\n\n"
                "1. Votre navigateur affiche *« La connexion a échoué à l'adresse localhost »* (comportement normal avec un identifiant de bureau Google).\n"
                "2. **Copiez l'URL complète** affichée dans votre barre d'adresse Firefox (elle contient `code=4/...`).\n"
                "3. **Collez-la ci-dessous** et cliquez sur **Valider** :"
            )
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
                        st.success(f"🎉 Bienvenue, {authenticated_user['name']} ({authenticated_user['role'].upper()}) !")
                        st.rerun()
                    except Exception as err:
                        st.error(f"❌ Erreur lors de la validation du code : {err}")
                else:
                    st.warning("Veuillez d'abord coller l'URL de votre navigateur.")

        # Option de téléversement direct du fichier credentials.json
        with st.expander("📂 Téléverser votre fichier credentials.json (Google Cloud)", expanded=(not is_oauth_configured())):
            st.markdown(
                "Vous pouvez glisser-déposer directement le fichier JSON téléchargé depuis Google Cloud Console "
                "(*Application Web* ou *Application de bureau*) :"
            )
            uploaded_json = st.file_uploader(
                "Fichier credentials.json ou client_secret_xxxx.json :",
                type=["json"],
                key="oauth_credentials_uploader",
                help="Prend en charge les formats 'web' et 'installed'."
            )
            if uploaded_json is not None:
                try:
                    cred_details = save_uploaded_oauth_credentials(uploaded_json.getvalue())
                    st.success(f"✅ Fichier Google OAuth ({cred_details['type']}) enregistré avec succès !")
                    if cred_details["type"] == "web" and cred_details["redirect_uris"]:
                        st.info(f"🎯 URI de redirection détectée : `{cred_details['redirect_uris'][0]}`")
                    st.rerun()
                except Exception as upload_err:
                    st.error(f"❌ {upload_err}")

        st.write("")

        # Mode Local / Démonstration repliable pour le développement
        with st.expander("🧪 Mode Local / Démonstration (Développement & Hors-ligne)", expanded=(not is_oauth_configured())):
            st.caption(
                "Permet de se connecter directement sans passer par Google Cloud. "
                "Si la base est vide, le premier utilisateur créé sera nommé Administrateur."
            )
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
    logged_in_user_id = current_user["id"]
    user_role = current_user.get("role", "student")
    is_admin = user_role == "admin"

    # Barre Latérale : Profil et Navigation
    st.sidebar.markdown("## 🎓 **Ecole Adnane**")
    role_badge = "👑 Administrateur" if is_admin else "🎒 Élève (3AC)"
    st.sidebar.markdown(f"**{current_user['name']}**  \n`{current_user['email']}`  \n`{role_badge}`")

    st.sidebar.divider()

    # Sélecteur d'espace pour l'administrateur
    is_global_admin_view = False
    active_user_id = logged_in_user_id
    active_student_info = None

    if is_admin:
        all_students = list_users(role="student")
        student_options: Dict[str, str] = {"global": "📊 Vue Globale (Supervision)"}
        for s in all_students:
            student_options[str(s["id"])] = f"🎒 {s['name']} ({s['email']})"

        chosen_space = st.sidebar.selectbox(
            "Espace de travail :",
            options=list(student_options.keys()),
            format_func=lambda x: student_options[x],
            key="admin_space_selector",
        )

        if chosen_space == "global":
            is_global_admin_view = True
            active_user_id = logged_in_user_id
        else:
            is_global_admin_view = False
            active_user_id = int(chosen_space)
            active_student_info = get_user_by_id(active_user_id)

    # Choix de la navigation selon la vue
    if is_global_admin_view:
        menu = st.sidebar.radio(
            "Supervision",
            ["📊 Supervision Globale", "⚙️ Configuration Système & Sauvegardes"],
            index=0,
        )
    else:
        menu = st.sidebar.radio(
            "Navigation",
            ["📚 Mes Cours (Révisions)", "➕ Ajouter un Cours", "📊 Mes Progrès", "⚙️ Paramètres & Sauvegardes"],
            index=0,
        )

    # Indicateur IA pour l'utilisateur actif
    user_api_key = get_user_gemini_api_key(active_user_id)
    if user_api_key:
        st.sidebar.success("🟢 IA active & prête", icon="✅")
    else:
        st.sidebar.warning("⚠️ Clé IA personnelle requise", icon="🔑")
        st.sidebar.caption("Rendez-vous dans ⚙️ Paramètres pour activer votre clé Gemini gratuite.")

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
                        "Cours ajoutés": s["course_count"],
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
    # VUE ADMIN 2 : CONFIGURATION SYSTÈME & SAUVEGARDE GLOBALE
    # -----------------------------------------------------------------------
    elif is_global_admin_view and menu == "⚙️ Configuration Système & Sauvegardes":
        st.title("⚙️ Configuration Système & Sauvegarde Globale")
        st.markdown("Gestion des accès API de secours, sauvegarde intégrale de la plateforme et maintenance.")

        st.markdown("### 🔑 Clé API Google Gemini (Administrateur)")
        current_admin_key = get_user_gemini_api_key(logged_in_user_id) or ""
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
                st_upload = st.file_uploader(f"Restaurer dans l'espace de {target_student['name']} :", type=["zip"], key="target_student_restore_upload")
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
            all_subjects = ["Toutes"] + SUBJECTS_FR + SUBJECTS_AR
            selected_subject = st.selectbox("Filtrer par matière :", all_subjects)
        with col_f2:
            selected_lang = st.selectbox("Langue :", ["Toutes", "Français", "العربية"])
            lang_filter = "fr" if selected_lang == "Français" else ("ar" if selected_lang == "العربية" else None)
        with col_f3:
            courses_list = list_courses(
                user_id=active_user_id,
                subject=selected_subject if selected_subject != "Toutes" else None,
                language=lang_filter,
            )
            st.write(f"**{len(courses_list)} cours disponible(s)**")

        if not courses_list:
            st.info(
                "👋 Aucun cours enregistré pour cet espace. Allez dans l'onglet **➕ Ajouter un Cours** pour déposer vos premiers documents PDF !"
            )
            return

        course_options = {c["id"]: f"{'🇲🇦 [AR]' if c['language'] == 'ar' else '🇫🇷 [FR]'} {c['subject']} - {c['title']}" for c in courses_list}
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
        badge_cls = get_subject_badge_class(current_course["subject"])

        level_label = "المستوى : السنة الثالثة إعدادي (3AC)" if is_ar else "Niveau : 3AC Collège"
        lang_badge_text = "العربية (AR)" if is_ar else "Français (FR)"

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
            else:
                chips = " ".join([f"<span class='concept-tag'>#{c}</span>" for c in current_course["key_concepts"]])
                st.markdown(f"**Notions clés :** {chips}", unsafe_allow_html=True)

        edit_header_label = "✏️ تصحيح مادة الدرس أو العنوان أو اللغة" if is_ar else "✏️ Modifier la matière, le titre ou la langue de ce cours"
        with st.expander(edit_header_label):
            col_ed1, col_ed2, col_ed3 = st.columns([3, 2, 2])
            with col_ed1:
                new_title = st.text_input(
                    "عنوان الدرس" if is_ar else "Titre du cours",
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
                    "🇫🇷 Anglais",
                ]
                current_prefix = "🇲🇦 " if is_ar else "🇫🇷 "
                current_match = current_prefix + current_course["subject"]
                default_idx = (
                    all_subjects_display.index(current_match)
                    if current_match in all_subjects_display
                    else 0
                )
                chosen_subject_labeled = st.selectbox(
                    "المادة" if is_ar else "Matière",
                    all_subjects_display,
                    index=default_idx,
                    key=f"edit_subj_{current_course['id']}",
                )
                cleaned_subj = chosen_subject_labeled.replace("🇲🇦 ", "").replace("🇫🇷 ", "")
                is_ar_choice = "🇲🇦" in chosen_subject_labeled or cleaned_subj in SUBJECTS_AR

            with col_ed3:
                lang_options = ["🇲🇦 العربية (ar)", "🇫🇷 Français (fr)"]
                lang_default_idx = 0 if is_ar_choice else 1
                chosen_lang_label = st.selectbox(
                    "اللغة" if is_ar else "Langue du cours",
                    lang_options,
                    index=lang_default_idx,
                    key=f"edit_lang_{current_course['id']}",
                )
                final_lang = "ar" if "العربية" in chosen_lang_label else "fr"

            btn_save_col1, _ = st.columns([2, 5])
            with btn_save_col1:
                btn_save_txt = "💾 حفظ التعديل" if is_ar else "💾 Enregistrer les modifications"
                if st.button(btn_save_txt, type="primary", use_container_width=True, key=f"btn_save_m_{current_course['id']}"):
                    update_course_metadata(current_course["id"], new_title, cleaned_subj, final_lang, user_id=active_user_id)
                    st.success("Modifications enregistrées !")
                    st.rerun()

        st.write("")

        if is_ar:
            tab_doc, tab_fiche, tab_quiz, tab_tuteur = st.tabs([
                "📄 وثيقة الدرس",
                "⚡ بطاقة المراجعة",
                "🎯 تدريب الامتحان",
                "🤖 الأستاذ سند",
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

                st.download_button(
                    label="📥 تحميل ملف PDF الأصلي" if is_ar else "📥 Télécharger le PDF original",
                    data=pdf_data,
                    file_name=current_course.get("file_name", "cours.pdf"),
                    mime="application/pdf",
                )
            else:
                st.warning("Fichier PDF non trouvé sur le disque.")

            st.write("---")
            with st.expander("📝 عرض النص المستخرج من الوثيقة" if is_ar else "📝 Voir le texte extrait du document"):
                raw = current_course.get("raw_text") or "Aucun texte."
                if is_ar:
                    st.markdown(f"<div class='rtl-box'>{raw[:4000]}...</div>", unsafe_allow_html=True)
                else:
                    st.text(raw[:4000] + ("..." if len(raw) > 4000 else ""))

        with tab_fiche:
            fiche_md = current_course.get("summary_markdown")
            if not fiche_md:
                btn_gen_fiche = "⚡ توليد بطاقة المراجعة المركزة بالذكاء الاصطناعي" if is_ar else "⚡ Générer la Fiche Express avec l'IA"
                if st.button(btn_gen_fiche, type="primary"):
                    if not user_api_key:
                        st.error("Veuillez d'abord configurer votre clé API Gemini dans l'onglet Paramètres.")
                    else:
                        with st.spinner("Génération de la fiche express..."):
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
                if st.button("🔄 Régénérer la Fiche Express"):
                    if not user_api_key:
                        st.error("Veuillez d'abord configurer votre clé API Gemini.")
                    else:
                        with st.spinner("Régénération..."):
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

            btn_new_quiz = "🎯 توليد اختبار تدريبي جديد (5 أسئلة)" if is_ar else "🎯 Générer un nouveau quiz d'examen (5 questions)"
            if st.button(btn_new_quiz, type="secondary"):
                if not user_api_key:
                    st.error("Veuillez d'abord configurer votre clé API Gemini dans l'onglet Paramètres.")
                else:
                    with st.spinner("Génération des questions d'examen..."):
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
                            st.success(f"✅ Excellente réponse ! ({options[ans_idx]})")
                        else:
                            st.error(f"❌ La bonne réponse était : **{options[ans_idx]}**")

                        if explanation:
                            st.markdown(f"<div class='explanation-card'><strong>💡 Explication :</strong> {explanation}</div>", unsafe_allow_html=True)
                        if trap_alert:
                            st.markdown(f"<div class='trap-card'><strong>⚠️ Piège classique :</strong> {trap_alert}</div>", unsafe_allow_html=True)

                if not is_submitted:
                    if st.button("🏆 Valider mes réponses", type="primary"):
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
                    st.markdown(f"### Score obtenu : **{score} / {len(questions)}**")
                    if st.button("🔁 Recommencer ce quiz"):
                        st.session_state[submission_key] = False
                        st.rerun()
            else:
                st.info("Aucun quiz généré pour ce cours pour le moment.")

        with tab_tuteur:
            st.markdown("### 🤖 Tuteur Virtuel : Sanad" if not is_ar else "<div class='rtl-section-title'>🤖 الأستاذ المساعد : سَنَد</div>", unsafe_allow_html=True)

            history = get_chat_history(current_course["id"], user_id=active_user_id)
            for msg in history:
                role = msg["role"]
                content = msg["content"]
                with st.chat_message("user" if role == "user" else "assistant", avatar="🧑‍🎓" if role == "user" else "🤖"):
                    if is_ar:
                        st.markdown(f"<div class='rtl-box'>{content}</div>", unsafe_allow_html=True)
                    else:
                        st.markdown(content)

            user_input = st.chat_input("Pose ta question à Sanad..." if not is_ar else "اطرح سؤالك على الأستاذ المساعد سند...")
            if user_input:
                if not user_api_key:
                    st.error("Veuillez d'abord configurer votre clé API Gemini dans l'onglet Paramètres.")
                else:
                    add_chat_message(current_course["id"], "user", user_input, user_id=active_user_id)
                    with st.chat_message("user", avatar="🧑‍🎓"):
                        st.markdown(user_input)

                    with st.chat_message("assistant", avatar="🤖"):
                        with st.spinner("Sanad prépare ses conseils..."):
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
                    st.rerun()

            if history:
                if st.button("🗑️ Effacer la conversation avec Sanad", key="clear_chat_active"):
                    clear_chat_history(current_course["id"], user_id=active_user_id)
                    st.rerun()

    # -----------------------------------------------------------------------
    # VUE ÉLÈVE : AJOUTER UN COURS
    # -----------------------------------------------------------------------
    elif menu == "➕ Ajouter un Cours":
        if is_admin and active_student_info:
            st.info(f"👀 **Espace de supervision :** Vous téléversez pour l'élève **{active_student_info['name']}**.")

        st.title("➕ Ajouter des Cours (3AC)")

        mode = st.radio(
            "Mode d'importation :",
            ["📁 Import Manuel (PDF)", "🏫 Synchronisation Google Classroom"],
            horizontal=True,
        )

        if mode == "📁 Import Manuel (PDF)":
            uploaded_files = st.file_uploader(
                "Sélectionnez un ou plusieurs fichiers PDF :",
                type=["pdf"],
                accept_multiple_files=True,
                help="Les fichiers seront stockés dans votre dossier personnel isolé.",
            )

            if uploaded_files:
                st.info(f"📄 {len(uploaded_files)} fichier(s) sélectionné(s).")
                if st.button("🚀 Ingestion & Analyse Automatique", type="primary"):
                    progress_bar = st.progress(0)
                    success_count = 0
                    dup_count = 0

                    for i, f in enumerate(uploaded_files):
                        file_bytes = f.read()
                        res = ingest_pdf_bytes(file_bytes, f.name, user_id=active_user_id)
                        if res["status"] == "success":
                            success_count += 1
                            st.success(f"✅ {f.name} ajouté ({res['subject']} - {res['language'].upper()})")
                        else:
                            dup_count += 1
                            st.warning(f"ℹ️ {f.name} : Déjà présent dans votre espace.")
                        progress_bar.progress((i + 1) / len(uploaded_files))

                    st.success(f"Bilan : {success_count} cours ajouté(s), {dup_count} doublon(s).")

        else:
            st.markdown("### 🏫 Synchronisation Google Classroom Individuelle")
            st.write("Récupérez vos cours et devoirs depuis votre propre compte Classroom.")

            has_creds = is_classroom_configured(active_user_id)
            if not has_creds:
                st.warning("⚠️ Vos identifiants Google Classroom (`credentials.json`) ne sont pas encore téléversés.")
                up_cred = st.file_uploader("Téléverser votre `credentials.json` :", type=["json"], key="up_cred_individual")
                if up_cred:
                    save_user_credentials(active_user_id, up_cred.read())
                    st.success("Identifiants enregistrés dans votre espace !")
                    st.rerun()
            else:
                st.success("🟢 Identifiants Classroom configurés pour votre compte.")
                if st.button("🔄 Synchroniser mes devoirs Classroom", type="primary"):
                    with st.spinner("Synchronisation Classroom en cours..."):
                        sync_res = sync_google_classroom(user_id=active_user_id)
                        if sync_res["success"]:
                            st.success(sync_res["message"])
                        else:
                            st.error(sync_res["error"])

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
    elif menu == "⚙️ Paramètres & Sauvegardes":
        if is_admin and active_student_info:
            st.info(f"👀 **Espace de supervision :** Paramètres et sauvegarde de **{active_student_info['name']}**.")

        st.title("⚙️ Paramètres & Sauvegardes Personnelles")

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

        st.divider()

        st.markdown("### 🏫 Identifiants Google Classroom Personnels")
        cred_file = st.file_uploader("Fichier client `credentials.json` personnel :", type=["json"], key="up_cred_settings")
        if cred_file:
            save_user_credentials(active_user_id, cred_file.read())
            st.success("Fichier credentials.json enregistré dans votre espace personnel !")

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
                "Sélectionnez votre archive personnelle (.zip) :",
                type=["zip"],
                key="restore_student_backup_uploader",
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
