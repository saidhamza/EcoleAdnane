"""
Ecole Adnane - Application Web de Révision & Préparation aux Examens 3AC (Maroc)
100% Python propulsée par Streamlit, SQLite et Google Gemini.
"""

import base64
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

import streamlit as st

from models.database import (
    add_chat_message,
    clear_chat_history,
    delete_course,
    get_chat_history,
    get_course_by_id,
    get_latest_quiz,
    get_quiz_stats,
    init_db,
    list_courses,
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
from services.config_manager import (
    get_gemini_api_key,
    get_openai_api_key,
    save_config_value,
    test_active_connection,
    test_gemini_connection,
)
from services.downloader import (
    CREDENTIALS_PATH,
    ingest_pdf_bytes,
    is_classroom_configured,
    sync_google_classroom,
)
from services.pdf_parser import SUBJECTS_AR, SUBJECTS_FR

# Initialisation de la base SQLite
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

/* Import polices calligraphiques complémentaires si réseau actif */
@import url('https://fonts.googleapis.com/css2?family=Amiri:wght@400;700&family=Cairo:wght@500;600;700&family=Tajawal:wght@500;700&display=swap');

/* Règle globale pour tous les conteneurs Streamlit */
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

/* Titres, onglets et boutons en Arabe */
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

/* Badges de matières */
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

/* Badge de langue adaptatif */
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

/* En-tête de cours adaptatif - Contraste parfait en Mode Sombre & Clair */
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

/* RTL Container pour l'Arabe - Naskh fluide, clair et aéré */
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

.rtl-question {{
    direction: rtl !important;
    text-align: right !important;
    font-family: 'AdnaneSans', 'Noto Sans Arabic', serif !important;
    font-size: 1.25rem !important;
    font-weight: 700 !important;
    color: var(--text-color, #ffffff) !important;
    line-height: 1.9 !important;
    margin-top: 18px;
    margin-bottom: 8px;
}}

/* Boîte piège examen - Lisible en clair comme en sombre */
.trap-card {{
    background-color: rgba(245, 158, 11, 0.12) !important;
    border-left: 5px solid #f59e0b !important;
    border-top: 1px solid rgba(245, 158, 11, 0.3) !important;
    border-right: 1px solid rgba(245, 158, 11, 0.3) !important;
    border-bottom: 1px solid rgba(245, 158, 11, 0.3) !important;
    color: var(--text-color, #fef3c7) !important;
    padding: 14px 18px;
    border-radius: 8px;
    margin: 12px 0;
}}

.trap-card-rtl {{
    background-color: rgba(245, 158, 11, 0.12) !important;
    border-right: 5px solid #f59e0b !important;
    border-top: 1px solid rgba(245, 158, 11, 0.3) !important;
    border-left: 1px solid rgba(245, 158, 11, 0.3) !important;
    border-bottom: 1px solid rgba(245, 158, 11, 0.3) !important;
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

.trap-card strong, .trap-card-rtl strong {{
    color: #f59e0b !important;
}}

/* Boîte explication - Lisible en clair comme en sombre */
.explanation-card {{
    background-color: rgba(34, 197, 94, 0.12) !important;
    border-left: 5px solid #22c55e !important;
    border-top: 1px solid rgba(34, 197, 94, 0.3) !important;
    border-right: 1px solid rgba(34, 197, 94, 0.3) !important;
    border-bottom: 1px solid rgba(34, 197, 94, 0.3) !important;
    color: var(--text-color, #dcfce7) !important;
    padding: 14px 18px;
    border-radius: 8px;
    margin: 12px 0;
}}

.explanation-card-rtl {{
    background-color: rgba(34, 197, 94, 0.12) !important;
    border-right: 5px solid #22c55e !important;
    border-top: 1px solid rgba(34, 197, 94, 0.3) !important;
    border-left: 1px solid rgba(34, 197, 94, 0.3) !important;
    border-bottom: 1px solid rgba(34, 197, 94, 0.3) !important;
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

.explanation-card strong, .explanation-card-rtl strong {{
    color: #22c55e !important;
}}

/* Puces de notions clés */
.concept-tag {{
    display: inline-block;
    background-color: rgba(14, 165, 233, 0.2) !important;
    color: #38bdf8 !important;
    border: 1px solid rgba(14, 165, 233, 0.45) !important;
    padding: 4px 12px;
    border-radius: 6px;
    font-size: 0.95rem;
    font-weight: 600;
    margin-right: 6px;
    margin-bottom: 6px;
    font-family: 'AdnaneSans', 'Noto Sans Arabic', serif !important;
}}

/* Onglets Streamlit */
div[role="tablist"] button p {{
    font-family: 'AdnaneSans', 'Noto Sans Arabic', serif !important;
    font-size: 1.05rem !important;
    font-weight: 600 !important;
}}

/* Boutons principaux */
button[kind="primary"], button[kind="secondary"] {{
    font-family: 'AdnaneSans', 'Noto Sans Arabic', serif !important;
    font-size: 1.05rem !important;
}}

/* Choix QCM radio */
[data-testid="stRadio"] label {{
    font-family: 'AdnaneNaskh', 'Noto Naskh Arabic', serif !important;
    font-size: 1.12rem !important;
    line-height: 1.8 !important;
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


# ---------------------------------------------------------------------------
# Barre Latérale & Navigation Principale
# ---------------------------------------------------------------------------

st.sidebar.markdown("## 🎓 **Ecole Adnane**")
st.sidebar.markdown(
    "<span style='font-size:0.9rem; color:var(--text-color, inherit); opacity:0.8;'>Préparation Brevet 3AC Maroc (Local & Régional)</span>",
    unsafe_allow_html=True,
)
st.sidebar.divider()

menu = st.sidebar.radio(
    "Navigation",
    ["📚 Mes Cours (Révisions)", "➕ Ajouter un Cours", "📊 Mes Progrès", "⚙️ Configuration & Guide"],
    index=0,
)

# Indication visuelle du statut IA dans la sidebar
api_key = get_gemini_api_key() or get_openai_api_key()
if api_key:
    st.sidebar.success("🟢 IA active & prête", icon="✅")
else:
    st.sidebar.warning("⚠️ Clé IA non configurée", icon="🔑")
    st.sidebar.caption("Rendez-vous dans ⚙️ Configuration pour activer l'IA gratuitement.")

st.sidebar.divider()
st.sidebar.caption("🇲🇦 Conçu spécialement pour un collégien de 14 ans (3AC Biof / Général).")


# ===========================================================================
# 1. ÉCRAN : MES COURS & ESPACE DE RÉVISION (4 ONGLETS PAR COURS)
# ===========================================================================

if menu == "📚 Mes Cours (Révisions)":
    st.title("📚 Mon Espace de Révision 3AC")

    # Filtres
    col_f1, col_f2, col_f3 = st.columns([2, 2, 2])
    with col_f1:
        all_subjects = ["Toutes"] + SUBJECTS_FR + SUBJECTS_AR
        selected_subject = st.selectbox("Filtrer par matière :", all_subjects)
    with col_f2:
        selected_lang = st.selectbox("Langue :", ["Toutes", "Français", "العربية"])
        lang_filter = "fr" if selected_lang == "Français" else ("ar" if selected_lang == "العربية" else None)
    with col_f3:
        courses_list = list_courses(
            subject=selected_subject if selected_subject != "Toutes" else None,
            language=lang_filter,
        )
        st.write(f"**{len(courses_list)} cours disponible(s)**")

    if not courses_list:
        st.info(
            "👋 Aucun cours enregistré pour le moment. Allez dans l'onglet **➕ Ajouter un Cours** pour glisser vos premiers documents PDF !"
        )
        st.stop()

    # Sélection du cours actif
    course_options = {c["id"]: f"{'🇲🇦 [AR]' if c['language'] == 'ar' else '🇫🇷 [FR]'} {c['subject']} - {c['title']}" for c in courses_list}
    selected_course_id = st.selectbox(
        "Sélectionnez le cours à réviser :",
        options=list(course_options.keys()),
        format_func=lambda x: course_options[x],
    )

    current_course = get_course_by_id(selected_course_id)
    if not current_course:
        st.error("Cours introuvable.")
        st.stop()

    is_ar = current_course["language"] == "ar"
    badge_cls = get_subject_badge_class(current_course["subject"])

    # En-tête du cours actif (adaptatif mode sombre et clair)
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

    # Affichage des notions clés si présentes
    if current_course.get("key_concepts"):
        if is_ar:
            chips = " ".join([f"<span class='concept-tag'>{c}</span>" for c in current_course["key_concepts"]])
            st.markdown(f"<div dir='rtl' style='text-align:right; margin-top:8px; margin-bottom:12px;'><strong>المفاهيم الأساسية :</strong> {chips}</div>", unsafe_allow_html=True)
        else:
            chips = " ".join([f"<span class='concept-tag'>#{c}</span>" for c in current_course["key_concepts"]])
            st.markdown(f"**Notions clés :** {chips}", unsafe_allow_html=True)

    st.write("")

    # Les 4 Onglets Pédagogiques (bilingues et adaptés à la langue du cours, sans bidi conflict)
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

    # -----------------------------------------------------------------------
    # ONGLET 1 : LE DOCUMENT ORIGINAL / TEXTE EXTRAIT
    # -----------------------------------------------------------------------
    with tab_doc:
        if is_ar:
            st.markdown("<div class='rtl-section-title'>📄 وثيقة الدرس الأصلية</div>", unsafe_allow_html=True)
        else:
            st.markdown("### 📄 Support de cours original")
        doc_col1, doc_col2 = st.columns([1, 1])

        file_path = current_course.get("file_path")
        if file_path and os.path.exists(file_path):
            with open(file_path, "rb") as f:
                pdf_data = f.read()

            with doc_col1:
                st.download_button(
                    label="📥 تحميل ملف PDF الأصلي" if is_ar else "📥 Télécharger le PDF original",
                    data=pdf_data,
                    file_name=current_course["file_name"],
                    mime="application/pdf",
                    use_container_width=True,
                )

            with doc_col2:
                # Option pour affiner le titre ou la matière
                edit_exp_label = "✏️ تعديل عنوان الدرس أو المادة" if is_ar else "✏️ Modifier le titre ou la matière"
                with st.expander(edit_exp_label):
                    new_title = st.text_input("عنوان الدرس" if is_ar else "Titre du cours", value=current_course["title"])
                    current_subj_list = SUBJECTS_AR if is_ar else SUBJECTS_FR
                    subj_idx = current_subj_list.index(current_course["subject"]) if current_course["subject"] in current_subj_list else 0
                    new_subject = st.selectbox("المادة" if is_ar else "Matière", current_subj_list, index=subj_idx)
                    if st.button("حفظ التعديلات" if is_ar else "Enregistrer les modifications", key="save_meta_btn"):
                        update_course_metadata(current_course["id"], new_title, new_subject, current_course["language"])
                        st.success("تم حفظ التعديلات بنجاح !" if is_ar else "Modifications enregistrées !")
                        st.rerun()

                # Option de suppression définitive du cours
                del_exp_label = "🗑️ حذف هذا الدرس من التطبيق" if is_ar else "🗑️ Supprimer ce cours"
                with st.expander(del_exp_label):
                    if is_ar:
                        st.warning("⚠️ تنبيه : هذا الإجراء نهائي وسيؤدي إلى حذف هذا الدرس وبطاقة مراجعته واختباراته ومحادثات الأستاذ المساعد سند.")
                        confirm_del = st.checkbox("أؤكد رغبتي في حذف هذا الدرس نهائياً", key=f"del_chk_{current_course['id']}")
                        if st.button("🗑️ تأكيد الحذف الآن", type="primary", disabled=not confirm_del, key=f"del_btn_{current_course['id']}", use_container_width=True):
                            delete_course(current_course["id"])
                            st.session_state.pop("selected_course_id", None)
                            st.success("تم حذف الدرس بنجاح !")
                            st.rerun()
                    else:
                        st.warning("⚠️ Attention : La suppression est définitive et effacera ce document, sa fiche express, ses quiz et l'historique du tuteur.")
                        confirm_del = st.checkbox("Je confirme vouloir supprimer définitivement ce cours", key=f"del_chk_{current_course['id']}")
                        if st.button("🗑️ Confirmer la suppression", type="primary", disabled=not confirm_del, key=f"del_btn_{current_course['id']}", use_container_width=True):
                            delete_course(current_course["id"])
                            st.session_state.pop("selected_course_id", None)
                            st.success("Le cours a été supprimé avec succès !")
                            st.rerun()

            # Aperçu du texte extrait
            st.divider()
            if is_ar:
                st.markdown("<div class='rtl-section-title' style='font-size:1.3rem;'>📖 النص المستخرج من الدرس</div>", unsafe_allow_html=True)
            else:
                st.markdown("#### 📖 Texte extrait du cours")
            raw_text = current_course.get("raw_text") or ""
            if raw_text.strip():
                if is_ar:
                    st.markdown(f"<div class='rtl-box'>{raw_text}</div>", unsafe_allow_html=True)
                else:
                    st.text_area("Contenu textuel du cours", value=raw_text, height=350, disabled=True)
            else:
                st.warning("لم يتم استخراج أي نص (قد يحتوي الملف على صور ممسوحة ضوئياً فقط)." if is_ar else "Aucun texte brut extrait (le PDF contient peut-être uniquement des images numérisées).")
        else:
            st.error("ملف PDF الأصلي غير موجود على القرص." if is_ar else "Le fichier PDF source n'a pas été trouvé sur le disque local.")
            if st.button("🗑️ حذف هذا السجل من القاعدة" if is_ar else "🗑️ Supprimer cette entrée de la base", type="primary"):
                delete_course(current_course["id"])
                st.success("تم حذف السجل بنجاح !" if is_ar else "Entrée supprimée avec succès !")
                st.rerun()

    # -----------------------------------------------------------------------
    # ONGLET 2 : FICHE EXPRESS (RÉSUMÉ EXAMEN & PIÈGES FRÉQUENTS)
    # -----------------------------------------------------------------------
    with tab_fiche:
        if is_ar:
            st.markdown(f"<div class='rtl-section-title'>⚡ بطاقة المراجعة المركزة وفخاخ الامتحان ({current_course['subject']})</div>", unsafe_allow_html=True)
        else:
            st.markdown(f"### ⚡ Fiche Express & Pièges d'Examen ({current_course['subject']})")

        existing_summary = current_course.get("summary_markdown")
        col_btn, col_info = st.columns([2, 3])

        with col_btn:
            if is_ar:
                btn_label = "🔄 إعادة توليد بطاقة المراجعة" if existing_summary else "✨ توليد بطاقة المراجعة بالذكاء الاصطناعي"
            else:
                btn_label = "🔄 Régénérer la Fiche Express" if existing_summary else "✨ Générer la Fiche Express avec l'IA"

            if st.button(btn_label, type="primary", use_container_width=True):
                if not api_key:
                    st.error("يرجى أولاً ضبط مفتاح Gemini في خانة الإعدادات." if is_ar else "Veuillez d'abord configurer votre clé API Gemini dans l'onglet ⚙️ Configuration.")
                else:
                    spinner_msg = "جاري إعداد بطاقة المراجعة المركزة باللغة العربية..." if is_ar else "Génération de votre fiche ultra-visuelle en cours..."
                    with st.spinner(spinner_msg):
                        try:
                            # 1. Générer le résumé
                            summary = generate_revision_sheet(
                                current_course.get("raw_text") or "",
                                current_course["subject"],
                                current_course["language"],
                            )
                            # 2. Classifier / extraire concepts clés si manquants
                            meta = classify_and_extract_metadata(
                                current_course.get("raw_text") or "",
                                current_course["language"],
                                current_course["title"],
                                current_course["subject"],
                            )
                            update_course_summary(current_course["id"], summary, meta.get("key_concepts"))
                            st.success("تم إعداد بطاقة المراجعة بنجاح !" if is_ar else "Fiche Express générée avec succès !")
                            st.rerun()
                        except Exception as e:
                            st.error(f"خطأ أثناء التوليد : {str(e)}" if is_ar else f"Erreur lors de la génération : {str(e)}")

        if existing_summary:
            st.divider()
            if is_ar:
                st.markdown(f"<div class='rtl-box'>{existing_summary}</div>", unsafe_allow_html=True)
            else:
                st.markdown(existing_summary)
        else:
            if is_ar:
                st.info("💡 انقر على الزر أعلاه لتوليد ملخص مركز يتضمن المفاهيم الأساسية وفخاخ الامتحان الموحد لهذا الدرس.")
            else:
                st.info("💡 Cliquez sur le bouton ci-dessus pour synthétiser les points clés et pièges de ce cours.")

    # -----------------------------------------------------------------------
    # ONGLET 3 : ENTRAÎNEMENT EXAMEN (QUIZ INTERACTIF & SCORE INSTANTANÉ)
    # -----------------------------------------------------------------------
    with tab_quiz:
        if is_ar:
            st.markdown(f"<div class='rtl-section-title'>🎯 تدريب على أسئلة الامتحان الموحد ({current_course['subject']})</div>", unsafe_allow_html=True)
        else:
            st.markdown(f"### 🎯 Entraînement Examen Normalisé ({current_course['subject']})")

        latest_quiz = get_latest_quiz(current_course["id"])
        q_col1, q_col2 = st.columns([2, 3])

        with q_col1:
            if is_ar:
                q_btn_label = "🔄 إعداد اختبار تدريبي جديد" if latest_quiz else "🚀 بدء اختبار تدريبي موحد (5 أسئلة)"
            else:
                q_btn_label = "🔄 Générer un Nouveau Quiz" if latest_quiz else "🚀 Créer un Quiz Examen (5 questions)"

            if st.button(q_btn_label, type="primary", use_container_width=True):
                if not api_key:
                    st.error("يرجى ضبط مفتاح الذكاء الاصطناعي في خانة الإعدادات." if is_ar else "Veuillez d'abord configurer votre clé API Gemini dans l'onglet ⚙️ Configuration.")
                else:
                    spinner_quiz = "جاري صياغة أسئلة مطابقة للامتحان الموحد..." if is_ar else "Conception de questions types examen normalisé..."
                    with st.spinner(spinner_quiz):
                        try:
                            new_quiz_questions = generate_quiz(
                                current_course.get("raw_text") or "",
                                current_course["subject"],
                                current_course["language"],
                                num_questions=5,
                            )
                            quiz_id = save_quiz(current_course["id"], new_quiz_questions)
                            # Réinitialiser la session de réponse pour ce cours
                            st.session_state[f"quiz_submitted_{current_course['id']}_{quiz_id}"] = False
                            st.success("الاختبار جاهز بالكامل ! انطلق يا بطل." if is_ar else "Nouveau quiz prêt ! À vous de jouer.")
                            st.rerun()
                        except Exception as e:
                            st.error(f"خطأ أثناء إعداد الاختبار : {str(e)}" if is_ar else f"Erreur lors de la création du quiz : {str(e)}")

        if latest_quiz and latest_quiz.get("questions"):
            questions = latest_quiz["questions"]
            quiz_id = latest_quiz["id"]
            st.divider()

            # Formulaire de réponse au Quiz
            submission_key = f"quiz_submitted_{current_course['id']}_{quiz_id}"
            is_submitted = st.session_state.get(submission_key, False)

            answers_chosen: Dict[int, int] = {}

            for idx, q in enumerate(questions):
                q_num = idx + 1
                q_title = q.get("question", "")
                options = q.get("options", [])
                ans_idx = q.get("answer_index", 0)
                explanation = q.get("explanation", "")
                trap_alert = q.get("trap_alert", "")

                if is_ar:
                    st.markdown(
                        f"<div class='rtl-question'>السؤال {q_num} : {q_title}</div>",
                        unsafe_allow_html=True,
                    )
                else:
                    st.markdown(
                        f"<div style='margin-top:15px; font-weight:700; font-size:1.1rem;'>Question {q_num} : {q_title}</div>",
                        unsafe_allow_html=True,
                    )

                selected_opt = st.radio(
                    f"خيارات السؤال {q_num}" if is_ar else f"Options pour Q{q_num}",
                    options=range(len(options)),
                    format_func=lambda i: options[i] if i < len(options) else "",
                    key=f"q_{quiz_id}_{idx}",
                    disabled=is_submitted,
                    label_visibility="collapsed",
                )
                answers_chosen[idx] = selected_opt

                # Affichage des résultats après soumission
                if is_submitted:
                    user_ans = answers_chosen[idx]
                    if user_ans == ans_idx:
                        if is_ar:
                            st.success(f"✅ إجابة صحيحة وممتازة ! ({options[ans_idx]})")
                        else:
                            st.success(f"✅ Excellente réponse ! ({options[ans_idx]})")
                    else:
                        if is_ar:
                            st.error(f"❌ إجابة غير موفقة ! اختيارك: '{options[user_ans]}'. الإجابة الصحيحة هي: **{options[ans_idx]}**")
                        else:
                            st.error(f"❌ Oups ! Votre choix : '{options[user_ans]}'. La bonne réponse était : **{options[ans_idx]}**")

                    # Carte Explication
                    if is_ar:
                        st.markdown(
                            f"<div class='explanation-card-rtl'><strong>💡 الشرح والتوضيح خطوة بخطوة :</strong><br>{explanation}</div>",
                            unsafe_allow_html=True,
                        )
                    else:
                        st.markdown(
                            f"<div class='explanation-card'><strong>💡 Explication pas à pas :</strong><br>{explanation}</div>",
                            unsafe_allow_html=True,
                        )

                    # Carte Piège d'examen
                    if trap_alert:
                        if is_ar:
                            st.markdown(
                                f"<div class='trap-card-rtl'><strong>⚠️ فخ شائع في الامتحان الموحد :</strong><br>{trap_alert}</div>",
                                unsafe_allow_html=True,
                            )
                        else:
                            st.markdown(
                                f"<div class='trap-card'><strong>⚠️ Piège fréquent à l'examen :</strong><br>{trap_alert}</div>",
                                unsafe_allow_html=True,
                            )

                st.write("")

            # Bouton de validation
            if not is_submitted:
                btn_validate = "🏆 تأكيد الإجابات واحتساب النقطة" if is_ar else "🏆 Valider mes réponses & voir mon score"
                if st.button(btn_validate, type="primary", use_container_width=True):
                    score = sum(1 for idx, q in enumerate(questions) if answers_chosen.get(idx) == q.get("answer_index", 0))
                    total = len(questions)

                    # Sauvegarde en SQLite
                    save_quiz_attempt(
                        course_id=current_course["id"],
                        quiz_id=quiz_id,
                        score=score,
                        total_questions=total,
                        answers=answers_chosen,
                    )
                    st.session_state[submission_key] = True

                    # Célébration si bon score
                    if score >= total * 0.8:
                        st.balloons()
                    st.rerun()
            else:
                score = sum(1 for idx, q in enumerate(questions) if answers_chosen.get(idx) == q.get("answer_index", 0))
                total = len(questions)
                rate = round((score / total) * 100)

                if is_ar:
                    st.markdown(f"<div class='rtl-section-title' style='font-size:1.35rem;'>📊 النتيجة المحصل عليها : {score} / {total} ({rate}%)</div>", unsafe_allow_html=True)
                    if rate >= 80:
                        st.success("🌟 هنيئاً لك يا بطل ! لقد أتقنت مهارات هذا الدرس وتجنبت كل الفخاخ بنجاح !")
                    elif rate >= 50:
                        st.info("👍 عمل جيد ! راجع الشروحات للأسئلة المتبقية لضمان النقطة الكاملة 20/20.")
                    else:
                        st.warning("💪 لا تستسلم ! أعد قراءة بطاقة المراجعة المركزة ثم أعد المحاولة.")
                else:
                    st.markdown(f"### 📊 Résultat : **{score} / {total}** ({rate}%)")
                    if rate >= 80:
                        st.success("🌟 Félicitations ! Tu maîtrises parfaitement les pièges de cette leçon !")
                    elif rate >= 50:
                        st.info("👍 Bon travail ! Relis les explications des questions manquées pour viser le 20/20.")
                    else:
                        st.warning("💪 Ne te décourage pas ! Relis la Fiche Express et réessaie le quiz.")

                btn_retry = "🔁 إعادة هذا الاختبار" if is_ar else "🔁 Recommencer ce quiz"
                if st.button(btn_retry):
                    st.session_state[submission_key] = False
                    st.rerun()

        else:
            if is_ar:
                st.info("لا يوجد اختبار منشأ بعد لهذا الدرس. انقر على الزر أعلاه لتوليد 5 أسئلة تدريبية للامتحان الموحد !")
            else:
                st.info("Aucun quiz n'a encore été créé pour ce cours. Cliquez sur le bouton ci-dessus pour vous tester !")

    # -----------------------------------------------------------------------
    # ONGLET 4 : TUTEUR VIRTUEL SOCRATIQUE (SANAD)
    # -----------------------------------------------------------------------
    with tab_tuteur:
        if is_ar:
            st.markdown("<div class='rtl-section-title'>🤖 الأستاذ المساعد : سَنَد</div>", unsafe_allow_html=True)
            st.caption("مرافقك الذكي والأخ الأكبر لامتحانات الثالثة إعدادي — يرشدك خطوة بخطوة بالمنهج السقراطي دون إعطاء الحلول الجاهزة!")
        else:
            st.markdown("### 🤖 Tuteur Virtuel : Sanad")
            st.caption("Ton Grand Frère & Mentor pour le Brevet 3AC — Méthode socratique : il te guide sans faire les exercices à ta place !")

        # Boutons de questions rapides adaptés à la langue
        st.write("**أسئلة سريعة بنقرة واحدة :**" if is_ar else "**Questions rapides en un clic :**")
        sug_cols = st.columns(3)
        suggested_prompt = None

        if is_ar:
            if sug_cols[0].button("💡 اشرح لي هذا الدرس ببساطة", use_container_width=True):
                suggested_prompt = "اشرح لي فكرة هذا الدرس ببساطة كما لو كان عمري 12 سنة."
            if sug_cols[1].button("⚠️ ما هي أهم فخاخ الامتحان هنا؟", use_container_width=True):
                suggested_prompt = "ما هي الفخاخ والأسئلة المفخخة التي يضعها الأساتذة عادة في الامتحان الموحد لهذا الدرس؟"
            if sug_cols[2].button("❓ اختبر فهمي بسؤال توجيهي", use_container_width=True):
                suggested_prompt = "اطرح علي سؤالاً لاختبار فهمي وساعدني في الإجابة عليه خطوة بخطوة."
        else:
            if sug_cols[0].button("💡 Explique-moi simplement", use_container_width=True):
                suggested_prompt = "Peux-tu m'expliquer l'idée générale de ce cours avec une analogie simple de la vie courante ?"
            if sug_cols[1].button("⚠️ Quels pièges éviter au brevet ?", use_container_width=True):
                suggested_prompt = "Quels sont les pièges classiques posés à l'examen normalisé sur ce sujet et comment les éviter ?"
            if sug_cols[2].button("❓ Pose-moi une question", use_container_width=True):
                suggested_prompt = "Pose-moi une petite question pour tester si j'ai bien compris, et guide-moi pour répondre."

        # Historique des messages
        history = get_chat_history(current_course["id"])

        for msg in history:
            role = msg["role"]
            content = msg["content"]
            with st.chat_message("user" if role == "user" else "assistant", avatar="🧑‍🎓" if role == "user" else "🤖"):
                if is_ar:
                    st.markdown(f"<div class='rtl-box'>{content}</div>", unsafe_allow_html=True)
                else:
                    st.markdown(content)

        # Gestion de l'entrée du chat
        input_placeholder = "اطرح سؤالك على الأستاذ المساعد سند..." if is_ar else "Pose ta question au tuteur..."
        user_input = st.chat_input(input_placeholder)
        prompt_to_send = user_input or suggested_prompt

        if prompt_to_send:
            if not api_key:
                st.error("يرجى أولاً ضبط مفتاح Gemini في خانة الإعدادات." if is_ar else "Veuillez d'abord configurer votre clé API Gemini dans l'onglet ⚙️ Configuration.")
            else:
                # Ajouter message utilisateur
                add_chat_message(current_course["id"], "user", prompt_to_send)
                with st.chat_message("user", avatar="🧑‍🎓"):
                    if is_ar:
                        st.markdown(f"<div class='rtl-box'>{prompt_to_send}</div>", unsafe_allow_html=True)
                    else:
                        st.markdown(prompt_to_send)

                # Réponse socratique
                with st.chat_message("assistant", avatar="🤖"):
                    spinner_chat = "الأستاذ سند يفكر في توجيهك بأفضل طريقة..." if is_ar else "Sanad réfléchit à la meilleure façon de te guider..."
                    with st.spinner(spinner_chat):
                        updated_history = get_chat_history(current_course["id"])
                        reply = socratic_tutor_response(
                            messages=updated_history,
                            course_context=current_course.get("raw_text") or "",
                            subject=current_course["subject"],
                            language=current_course["language"],
                        )
                        add_chat_message(current_course["id"], "assistant", reply)
                        if is_ar:
                            st.markdown(f"<div class='rtl-box'>{reply}</div>", unsafe_allow_html=True)
                        else:
                            st.markdown(reply)
                st.rerun()

        # Bouton effacer l'historique
        if history:
            st.write("")
            btn_clear_chat = "🗑️ مسح المحادثة والبدء من جديد" if is_ar else "🗑️ Effacer la conversation avec le tuteur"
            if st.button(btn_clear_chat, key="clear_chat_btn"):
                clear_chat_history(current_course["id"])
                st.success("تم مسح المحادثة بنجاح." if is_ar else "Discussion réinitialisée.")
                st.rerun()


# ===========================================================================
# 2. ÉCRAN : AJOUTER UN COURS (IMPORT PDF & GOOGLE CLASSROOM)
# ===========================================================================

elif menu == "➕ Ajouter un Cours":
    st.title("➕ Ajouter de Nouveaux Supports de Cours")
    st.markdown("Importez vos cours en format PDF pour générer automatiquement les fiches de révision et les quiz.")

    mode = st.radio(
        "Mode d'importation :",
        ["📁 Import Manuel (Glisser-Déposer de PDFs)", "🏫 Synchronisation Google Classroom"],
        horizontal=True,
    )

    if mode == "📁 Import Manuel (Glisser-Déposer de PDFs)":
        st.write("")
        uploaded_files = st.file_uploader(
            "Sélectionnez un ou plusieurs fichiers PDF :",
            type=["pdf"],
            accept_multiple_files=True,
            help="Détection automatique de la langue (Français/Arabe) et de la matière selon le programme officiel 3AC.",
        )

        if uploaded_files:
            st.info(f"📄 {len(uploaded_files)} fichier(s) sélectionné(s).")
            if st.button("🚀 Lancer l'ingestion & l'analyse automatique", type="primary"):
                progress_bar = st.progress(0)
                status_text = st.empty()

                success_count = 0
                duplicate_count = 0

                for i, uploaded_file in enumerate(uploaded_files):
                    status_text.text(f"Traitement de {uploaded_file.name}...")
                    file_bytes = uploaded_file.read()

                    res = ingest_pdf_bytes(file_bytes, uploaded_file.name)

                    if res["status"] == "success":
                        success_count += 1
                        st.success(f"✅ **{uploaded_file.name}** : Enregistré en tant que **{res['subject']}** ({res['language'].upper()}) - {res['page_count']} pages.")
                    elif res["status"] == "duplicate":
                        duplicate_count += 1
                        st.warning(f"ℹ️ **{uploaded_file.name}** : Déjà présent dans votre base (doublon ignoré).")

                    progress_bar.progress((i + 1) / len(uploaded_files))

                status_text.text("Ingestion terminée !")
                st.write("---")
                st.success(f"🎉 Bilan : {success_count} cours ajouté(s), {duplicate_count} doublon(s) évité(s).")
                st.info("Rendez-vous dans l'onglet **📚 Mes Cours** pour commencer les révisions !")

    else:
        st.markdown("### 🏫 Synchronisation Google Classroom")
        st.write(
            "Récupérez automatiquement les devoirs et supports PDF postés par vos professeurs sur Google Classroom."
        )

        has_creds = is_classroom_configured()
        if not has_creds:
            st.warning("⚠️ Le fichier `credentials.json` n'est pas encore téléversé.")
            st.markdown(
                "Pour activer Classroom, téléversez votre fichier d'identifiants client OAuth 2.0 ci-dessous "
                "ou suivez le guide dans l'onglet **⚙️ Configuration & Guide**."
            )
            uploaded_cred = st.file_uploader("Téléverser `credentials.json` :", type=["json"])
            if uploaded_cred:
                with open(CREDENTIALS_PATH, "wb") as f:
                    f.write(uploaded_cred.read())
                st.success("Fichier credentials.json enregistré avec succès !")
                st.rerun()
        else:
            st.success("🟢 Identifiants Google Classroom configurés !")
            if st.button("🔄 Synchroniser mes cours Classroom maintenant", type="primary"):
                with st.spinner("Connexion à Google Classroom et téléchargement des documents..."):
                    sync_res = sync_google_classroom()
                    if sync_res["success"]:
                        st.success(sync_res["message"])
                    else:
                        st.error(sync_res["error"])


# ===========================================================================
# 3. ÉCRAN : MES PROGRÈS & TABLEAU DE BORD EXAMEN
# ===========================================================================

elif menu == "📊 Mes Progrès":
    st.title("📊 Tableau de Bord & Progression 3AC")
    st.markdown("Suivez votre assiduité et vos taux de réussite par matière pour arriver serein(e) au brevet !")

    stats = get_quiz_stats()

    m_col1, m_col2, m_col3, m_col4 = st.columns(4)
    with m_col1:
        st.metric("Total Quiz passés", stats["total_attempts"])
    with m_col2:
        st.metric("Questions répondues", stats["total_questions"])
    with m_col3:
        st.metric("Bonnes réponses", stats["total_score"])
    with m_col4:
        st.metric("Moyenne générale", f"{stats['average_success_rate']}%")

    st.divider()

    col_sub, col_hist = st.columns([1, 1])

    with col_sub:
        st.markdown("### 🎯 Maîtrise par matière")
        by_subj = stats.get("by_subject", [])
        if by_subj:
            for s in by_subj:
                subj_name = s["subject"]
                rate = s["success_rate"]
                attempts = s["attempts"]
                badge_cls = get_subject_badge_class(subj_name)

                st.markdown(
                    f"<div><span class='badge-subject {badge_cls}'>{subj_name}</span> "
                    f"<strong>{rate}%</strong> ({attempts} session(s))</div>",
                    unsafe_allow_html=True,
                )
                st.progress(rate / 100.0)
                st.write("")
        else:
            st.info("Aucune tentative de quiz enregistrée. Faites un quiz dans un cours pour afficher vos statistiques !")

    with col_hist:
        st.markdown("### 🕒 Derniers entraînements")
        recent = stats.get("recent_attempts", [])
        if recent:
            for a in recent:
                date_str = str(a.get("completed_at", ""))[:16]
                score_str = f"{a['score']}/{a['total_questions']}"
                st.markdown(
                    f"- **{a['course_title']}** ({a['subject']}) : `{score_str}` — <span style='color:var(--text-color, inherit); opacity:0.75; font-size:0.8rem;'>{date_str}</span>",
                    unsafe_allow_html=True,
                )
        else:
            st.caption("L'historique des 10 derniers quiz s'affichera ici.")


# ===========================================================================
# 4. ÉCRAN : CONFIGURATION SÉCURISÉE & GUIDE INTERACTIF 2 MINUTES
# ===========================================================================

elif menu == "⚙️ Configuration & Guide":
    st.title("⚙️ Paramètres & Configuration")
    st.markdown("Configurez vos clés d'accès sans toucher au terminal et profitez de l'IA gratuite.")

    # -----------------------------------------------------------------------
    # Guide interactif pas à pas repliable
    # -----------------------------------------------------------------------
    with st.expander("📖 **Guide : Obtenir vos accès gratuits en 2 minutes (100% Sans Carte Bancaire)**", expanded=True):
        st.markdown("""
        ### 🚀 Pourquoi Google Gemini ?
        Google propose un **palier gratuit très généreux (Free Tier)** pour ses modèles de pointe **Gemini 2.0 Flash / 1.5 Flash**. 
        Vous n'avez **besoin d'aucune carte de crédit** pour l'utiliser.

        #### ⚡ Étape par étape pour créer votre clé en 2 minutes :
        1. Rendez-vous directement sur [**Google AI Studio (Lien direct)**](https://aistudio.google.com/).
        2. Connectez-vous avec n'importe quel compte Google (Gmail standard).
        3. Cliquez sur le bouton bleu **"Get API key"** (en haut à gauche).
        4. Cliquez sur **"Create API key"** -> Sélectionnez ou créez un projet (1 clic).
        5. Copiez la clé générée (elle commence par `AIzaSy...`).
        6. Collez-la dans le formulaire ci-dessous et cliquez sur **"Enregistrer la clé"**, puis testez la connexion !
        
        ---
        #### 🏫 Et pour Google Classroom ?
        - **Option 1 (Recommandée & Simple) :** Utilisez le **glisser-déposer de PDF** dans l'onglet *➕ Ajouter un Cours*. Pas besoin de configurer Google Cloud !
        - **Option 2 (Automatique) :** Si vous souhaitez synchroniser automatiquement votre Google Classroom, téléchargez votre fichier `credentials.json` depuis Google Cloud Console (API Classroom & Drive activées) et téléversez-le ci-dessous.
        """)

    st.write("")

    # Formulaire de configuration des clés API
    st.markdown("### 🔑 Clés API de l'Intelligence Artificielle")

    current_gemini = get_gemini_api_key() or ""
    current_openai = get_openai_api_key() or ""

    col_cfg1, col_cfg2 = st.columns([3, 1])

    with col_cfg1:
        new_gemini = st.text_input(
            "Clé API Google Gemini (Prioritaire - Gratuite) :",
            value=current_gemini,
            type="password",
            placeholder="Ex: AIzaSyD...",
            help="Obtenue gratuitement sur https://aistudio.google.com/ sans carte bancaire.",
        )
        new_openai = st.text_input(
            "Clé API OpenAI (Optionnelle - Fallback) :",
            value=current_openai,
            type="password",
            placeholder="Ex: sk-proj-...",
            help="Utilisée uniquement si vous le souhaitez en cas de secours.",
        )

    with col_cfg2:
        st.write("")
        st.write("")
        if st.button("💾 Enregistrer la clé", type="primary", use_container_width=True):
            if new_gemini:
                save_config_value("GEMINI_API_KEY", new_gemini)
            if new_openai:
                save_config_value("OPENAI_API_KEY", new_openai)
            st.success("Clé enregistrée avec succès !")
            st.rerun()

        if st.button("🔍 Tester la connexion", use_container_width=True):
            with st.spinner("Test de connectivité avec l'IA en cours..."):
                key_to_test = new_gemini.strip() if new_gemini else None
                res = test_gemini_connection(key_to_test)
                if res["success"]:
                    if key_to_test:
                        save_config_value("GEMINI_API_KEY", key_to_test)
                    st.success(f"✅ {res['message']}")
                    st.info("🎉 Clé validée et sauvegardée avec succès ! Vous pouvez réviser vos cours.")
                else:
                    st.error(f"❌ {res['error']}")
                    if "tip" in res:
                        st.info(f"💡 {res['tip']}")

    st.divider()

    # Section Google Classroom
    st.markdown("### 🏫 Identifiants Google Classroom")
    cred_file = st.file_uploader("Fichier client OAuth2 (`credentials.json`) :", type=["json"])
    if cred_file:
        with open(CREDENTIALS_PATH, "wb") as f:
            f.write(cred_file.read())
        st.success("Fichier credentials.json mis à jour avec succès !")
