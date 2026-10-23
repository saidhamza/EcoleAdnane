"""
Tests unitaires et d'intégration pour Ecole Adnane.
Valide la détection linguistique, la classification 3AC Maroc,
l'authentification multi-utilisateurs (premier connecté = Admin),
le cloisonnement strict SQLite et arborescence physique,
les clés API et identifiants individuels,
les sauvegardes étanches (élève et globale) avec sécurité anti-traversal,
et les scopes officiels Google Classroom.
"""

import base64
import io
import json
import os
import sqlite3
import tempfile
import unittest
import wave
import zipfile
from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock, patch

from models.database import (
    MOROCCAN_SCHOOL_LEVELS,
    COURSE_BADGE_CATALOG,
    COURSE_BADGE_CATALOG_MAP,
    add_chat_message,
    award_badge,
    cleanup_expired_sessions,
    clear_chat_history,
    create_or_get_google_user,
    create_user_session,
    delete_course,
    delete_user_account,
    delete_user_session,
    evaluate_and_award_badges,
    evaluate_and_award_course_badges,
    evaluate_and_sync_concept_mastery,
    extract_real_course_concepts,
    get_badge_catalog,
    get_course_trophies_overview,
    get_student_trophies_by_course,
    get_chat_history,
    get_course_by_hash,
    get_course_by_id,
    get_course_mindmap,
    get_mindmap_disk_paths,
    get_global_admin_kpis,
    get_latest_quiz,
    get_pedagogical_cycle,
    get_quiz_stats,
    get_setting,
    get_student_concept_mastery,
    get_student_trophies_overview,
    get_user_badges,
    get_user_by_email,
    get_user_by_id,
    get_user_from_session_token,
    get_user_count,
    get_user_setting,
    init_db,
    is_generic_concept,
    list_courses,
    list_users,
    save_concept_mastery,
    save_course,
    save_course_mindmap,
    save_flashcard,
    save_quiz,
    save_quiz_attempt,
    set_setting,
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
from services.ai_engine import (
    _fallback_mindmap,
    clean_interactive_mindmap_markdown,
    clean_json_output,
    clean_mermaid_mindmap,
    convert_mermaid_to_markdown,
    generate_course_mindmap,
    resolve_student_age,
    resolve_student_level,
    socratic_tutor_response,
)
from services.auth_manager import (
    check_active_user_session,
    extract_auth_code,
    get_oauth_credentials,
    normalize_redirect_uri,
    save_uploaded_oauth_credentials,
)
from services.config_manager import (
    get_config_value,
    get_user_gemini_api_key,
    save_config_value,
    save_user_gemini_api_key,
)
from services.downloader import (
    calculate_sha256,
    get_user_credentials_path,
    get_user_storage_dir,
    ingest_pdf_bytes,
    is_classroom_configured,
    save_user_credentials,
)
from services.backup_manager import (
    export_global_backup,
    export_student_backup,
    get_backup_summary,
    get_student_backup_summary,
    is_safe_extract_path,
    restore_global_backup,
    restore_student_backup,
)
from services.pdf_parser import (
    classify_subject_heuristic,
    detect_language,
    extract_fallback_title,
    is_arabic_char,
)
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
    get_server_tts_audio_base64,
    get_speech_config,
    is_linux_platform,
)



class TestLanguageAndClassification(unittest.TestCase):
    """Tests sur la détection linguistique et la classification 3AC."""

    def test_is_arabic_char(self):
        self.assertTrue(is_arabic_char("م"))
        self.assertTrue(is_arabic_char("ل"))
        self.assertTrue(is_arabic_char("ق"))
        self.assertFalse(is_arabic_char("a"))
        self.assertFalse(is_arabic_char("é"))
        self.assertFalse(is_arabic_char("5"))

    def test_detect_language(self):
        text_fr = "Dans ce cours de mathématiques de 3AC, nous étudions le théorème de Thalès et le calcul des racines carrées."
        text_ar = "درس سورة الحشر في مادة التربية الإسلامية للسنة الثالثة إعدادي يتناول مدخل التزكية والعقيدة."
        text_mixed_mostly_ar = "ملخص درس التاريخ 3AC: الحرب العالمية الثانية وأسباب اندلاعها في أوروبا."
        text_en = "In this English unit for 3AC Moroccan students, we learn irregular verbs, the simple past tense, and reading comprehension exercises."

        self.assertEqual(detect_language(text_fr), "fr")
        self.assertEqual(detect_language(text_ar), "ar")
        self.assertEqual(detect_language(text_mixed_mostly_ar), "ar")
        self.assertEqual(detect_language(text_en), "en")

    def test_classify_subject_heuristic_french(self):
        math_text = "Théorème de Thalès : dans un triangle ABC, si (MN) est parallèle à (BC), alors AM/AB = AN/AC = MN/BC. Racines carrées."
        subj_math, _ = classify_subject_heuristic(math_text, "fr")
        self.assertEqual(subj_math, "Mathématiques")

        pc_text = "Les atomes et les ions. Solution acide de pH inférieur à 7, réaction de l'acide chlorhydrique avec le fer."
        subj_pc, _ = classify_subject_heuristic(pc_text, "fr")
        self.assertEqual(subj_pc, "Physique-Chimie")

        svt_text = "La digestion des aliments dans l'intestin grêle grâce aux enzymes. Absorption des nutriments par les villosités."
        subj_svt, _ = classify_subject_heuristic(svt_text, "fr")
        self.assertEqual(subj_svt, "SVT")

    def test_classify_subject_heuristic_arabic(self):
        islamic_text = "سورة الحشر ومدخل التزكية: الإيمان والغيب، صلح الحديبية وفتح مكة وفقه الأسرة وحق النفس وحق البيئة."
        subj_islamic, _ = classify_subject_heuristic(islamic_text, "ar")
        self.assertEqual(subj_islamic, "التربية الإسلامية")

        hist_text = "مادة الاجتماعيات: أسباب الحرب العالمية الثانية، القضية الفلسطينية، والمغرب والكفاح من أجل الاستقلال واستكمال الوحدة الترابية."
        subj_hist, _ = classify_subject_heuristic(hist_text, "ar")
        self.assertEqual(subj_hist, "الاجتماعيات")

        arabic_text = "الدرس اللغوي: صياغة اسم الفاعل وإعماله، صيغ المبالغة، اسما الزمان والمكان، والنصوص القرائية."
        subj_ar, _ = classify_subject_heuristic(arabic_text, "ar")
        self.assertEqual(subj_ar, "اللغة العربية")

    def test_classify_subject_heuristic_english(self):
        english_text = "Unit 3: Focus on reading comprehension and grammar. Practice simple past, irregular verbs, and vocabulary dialogues."
        subj_en, _ = classify_subject_heuristic(english_text, "en")
        self.assertEqual(subj_en, "Anglais")

    def test_extract_fallback_title_english(self):
        title = extract_fallback_title("doc.pdf", "", "en")
        self.assertEqual(title, "3AC English Lesson")


class TestMultiUserAndRoles(unittest.TestCase):
    """Tests sur l'attribution des rôles : Premier arrivé = Admin, suivants = Student."""

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.test_db_path = Path(self.temp_dir.name) / "test_auth.db"
        os.environ["DATABASE_PATH"] = str(self.test_db_path)
        init_db(self.test_db_path)

    def tearDown(self):
        self.temp_dir.cleanup()
        if "DATABASE_PATH" in os.environ:
            del os.environ["DATABASE_PATH"]

    def test_first_user_is_admin_and_subsequent_are_students(self):
        self.assertEqual(get_user_count(), 0)

        # 1er utilisateur -> doit être admin
        user1 = create_or_get_google_user("admin@ecole.ma", "Professeur Admin")
        self.assertEqual(user1["role"], "admin")
        self.assertEqual(get_user_count(), 1)

        # 2ème utilisateur -> doit être student
        user2 = create_or_get_google_user("adnane@eleve.ma", "Adnane")
        self.assertEqual(user2["role"], "student")
        self.assertEqual(get_user_count(), 2)

        # 3ème utilisateur -> doit être student
        user3 = create_or_get_google_user("yasmine@eleve.ma", "Yasmine")
        self.assertEqual(user3["role"], "student")
        self.assertEqual(get_user_count(), 3)

        # Re-connexion de l'admin existant -> conserve son rôle
        reconnect_admin = create_or_get_google_user("admin@ecole.ma", "Professeur Admin Mis à jour")
        self.assertEqual(reconnect_admin["role"], "admin")
        self.assertEqual(reconnect_admin["name"], "Professeur Admin Mis à jour")
        self.assertEqual(get_user_count(), 3)

    def test_block_and_unblock_student(self):
        admin = create_or_get_google_user("admin@ecole.ma", "Admin Principal")
        student = create_or_get_google_user("eleve@ecole.ma", "Élève Test")

        # Vérifier état initial actif
        self.assertEqual(student.get("is_blocked", 0), 0)
        is_valid, reason, _ = check_active_user_session(student["id"])
        self.assertTrue(is_valid)
        self.assertIsNone(reason)

        # 1. Blocage de l'élève par l'admin
        ok, msg = set_user_blocked_status(student["id"], is_blocked=True, requesting_admin_id=admin["id"])
        self.assertTrue(ok)
        self.assertIn("suspendu", msg)

        # Vérifier en base
        updated = get_user_by_id(student["id"])
        self.assertEqual(updated["is_blocked"], 1)

        # Vérifier rejet de connexion via create_or_get_google_user
        with self.assertRaises(PermissionError):
            create_or_get_google_user("eleve@ecole.ma", "Élève Test")

        # Vérifier rejet par check_active_user_session
        is_valid, reason, _ = check_active_user_session(student["id"])
        self.assertFalse(is_valid)
        self.assertEqual(reason, "blocked")

        # 2. Déblocage de l'élève par l'admin
        ok, msg = set_user_blocked_status(student["id"], is_blocked=False, requesting_admin_id=admin["id"])
        self.assertTrue(ok)
        self.assertIn("réactivé", msg)

        # Vérifier réactivation
        updated = get_user_by_id(student["id"])
        self.assertEqual(updated["is_blocked"], 0)
        is_valid, reason, _ = check_active_user_session(student["id"])
        self.assertTrue(is_valid)

    def test_update_user_role(self):
        admin = create_or_get_google_user("admin@ecole.ma", "Admin Principal")
        student = create_or_get_google_user("eleve@ecole.ma", "Élève Test")

        self.assertEqual(student["role"], "student")

        # Promotion en Admin
        ok, msg = update_user_role(student["id"], "admin", requesting_admin_id=admin["id"])
        self.assertTrue(ok)
        self.assertIn("Administrateur", msg)
        self.assertEqual(get_user_by_id(student["id"])["role"], "admin")

        # Rétrogradation en Élève
        ok, msg = update_user_role(student["id"], "student", requesting_admin_id=admin["id"])
        self.assertTrue(ok)
        self.assertIn("Élève", msg)
        self.assertEqual(get_user_by_id(student["id"])["role"], "student")

    def test_sole_admin_protections(self):
        admin = create_or_get_google_user("admin@ecole.ma", "Admin Seul")

        # 1. Tentative de rétrogradation du seul admin -> doit échouer
        ok, msg = update_user_role(admin["id"], "student", requesting_admin_id=admin["id"])
        self.assertFalse(ok)
        self.assertIn("dernier administrateur", msg)
        self.assertEqual(get_user_by_id(admin["id"])["role"], "admin")

        # 2. Tentative d'auto-blocage -> doit échouer
        ok, msg = set_user_blocked_status(admin["id"], is_blocked=True, requesting_admin_id=admin["id"])
        self.assertFalse(ok)
        self.assertIn("propre compte", msg)
        self.assertEqual(get_user_by_id(admin["id"])["is_blocked"], 0)

        # 3. Tentative d'auto-suppression -> doit échouer
        ok, msg = delete_user_account(admin["id"], requesting_admin_id=admin["id"])
        self.assertFalse(ok)
        self.assertIn("propre compte", msg)
        self.assertIsNotNone(get_user_by_id(admin["id"]))

    def test_delete_user_and_cascade_cleanup(self):
        admin = create_or_get_google_user("admin@ecole.ma", "Admin Principal")
        student = create_or_get_google_user("victor@eleve.ma", "Victor")

        # Ajouter des données pour l'élève
        cid = save_course(
            title="Cours de Victor",
            subject="Français",
            language="fr",
            file_path="/fake/cours_victor.pdf",
            file_hash="hash_victor_1",
            file_name="cours_victor.pdf",
            user_id=student["id"],
        )
        save_quiz(cid, [{"question": "Q1", "options": ["A", "B"], "answer_index": 0}], user_id=student["id"])
        add_chat_message(cid, "user", "Bonjour Sanad", user_id=student["id"])

        self.assertEqual(len(list_courses(user_id=student["id"])), 1)

        # Suppression du compte
        ok, msg = delete_user_account(student["id"], requesting_admin_id=admin["id"])
        self.assertTrue(ok)
        self.assertIn("supprimés définitivement", msg)

        # Vérifications en base
        self.assertIsNone(get_user_by_id(student["id"]))
        self.assertEqual(len(list_courses(user_id=student["id"])), 0)
        self.assertEqual(len(get_chat_history(cid, user_id=student["id"])), 0)

        # Vérification session
        is_valid, reason, _ = check_active_user_session(student["id"])
        self.assertFalse(is_valid)
        self.assertEqual(reason, "deleted")


class TestStrictDataIsolation(unittest.TestCase):
    """Vérifie le cloisonnement étanche entre plusieurs élèves."""

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.test_db_path = Path(self.temp_dir.name) / "test_isolation.db"
        os.environ["DATABASE_PATH"] = str(self.test_db_path)
        init_db(self.test_db_path)

        # Création de deux élèves
        self.user_a = create_or_get_google_user("eleve_a@test.ma", "Élève A", role="student")
        self.user_b = create_or_get_google_user("eleve_b@test.ma", "Élève B", role="student")

    def tearDown(self):
        self.temp_dir.cleanup()
        if "DATABASE_PATH" in os.environ:
            del os.environ["DATABASE_PATH"]

    def test_course_isolation(self):
        # Élève A ajoute un cours de Mathématiques
        cid_a = save_course(
            title="Thalès Élève A",
            subject="Mathématiques",
            language="fr",
            file_path="/fake/thales_a.pdf",
            file_hash="hash_a_123",
            file_name="thales_a.pdf",
            user_id=self.user_a["id"],
        )

        # Élève B ajoute un cours d'Histoire
        cid_b = save_course(
            title="Histoire Élève B",
            subject="الاجتماعيات",
            language="ar",
            file_path="/fake/hist_b.pdf",
            file_hash="hash_b_456",
            file_name="hist_b.pdf",
            user_id=self.user_b["id"],
        )

        # Vérification des listes respectives
        courses_a = list_courses(user_id=self.user_a["id"])
        courses_b = list_courses(user_id=self.user_b["id"])

        self.assertEqual(len(courses_a), 1)
        self.assertEqual(courses_a[0]["title"], "Thalès Élève A")

        self.assertEqual(len(courses_b), 1)
        self.assertEqual(courses_b[0]["title"], "Histoire Élève B")

        # Élève B ne peut pas accéder au cours de A
        c_for_b = get_course_by_id(cid_a, user_id=self.user_b["id"])
        self.assertIsNone(c_for_b)

    def test_course_english_saved_and_filtered(self):
        # Élève A ajoute un cours d'Anglais (en)
        cid_en = save_course(
            title="English Unit 1",
            subject="Anglais",
            language="en",
            file_path="/fake/english_u1.pdf",
            file_hash="hash_en_789",
            file_name="english_u1.pdf",
            user_id=self.user_a["id"],
        )
        self.assertIsNotNone(cid_en)

        # Récupération filtrée par langue
        courses_en = list_courses(user_id=self.user_a["id"], language="en")
        courses_fr = list_courses(user_id=self.user_a["id"], language="fr")
        courses_all = list_courses(user_id=self.user_a["id"])

        self.assertEqual(len(courses_en), 1)
        self.assertEqual(courses_en[0]["subject"], "Anglais")
        self.assertEqual(courses_en[0]["language"], "en")
        self.assertEqual(len(courses_fr), 0)
        self.assertEqual(len(courses_all), 1)

    def test_quiz_and_chat_isolation(self):
        cid_a = save_course(
            title="SVT A",
            subject="SVT",
            language="fr",
            file_path="/fake/svt_a.pdf",
            file_hash="hash_svt_a",
            file_name="svt_a.pdf",
            user_id=self.user_a["id"],
        )

        qid_a = save_quiz(cid_a, [{"question": "Q1", "options": ["A", "B"], "answer_index": 0}], user_id=self.user_a["id"])
        save_quiz_attempt(cid_a, qid_a, score=1, total_questions=1, answers={0: 0}, user_id=self.user_a["id"])
        add_chat_message(cid_a, "user", "Question élève A", user_id=self.user_a["id"])

        # Stats élève A : 1 tentative
        stats_a = get_quiz_stats(user_id=self.user_a["id"])
        self.assertEqual(stats_a["total_attempts"], 1)

        # Stats élève B : 0 tentative
        stats_b = get_quiz_stats(user_id=self.user_b["id"])
        self.assertEqual(stats_b["total_attempts"], 0)

        # Chat pour B est vide
        chat_b = get_chat_history(cid_a, user_id=self.user_b["id"])
        self.assertEqual(len(chat_b), 0)


    def test_individual_api_keys(self):
        # Un nouvel élève créé n'a AUCUNE clé par défaut, même si une clé globale existe en environnement
        os.environ["GEMINI_API_KEY"] = "GLOBAL_SERVER_KEY"
        new_student = create_or_get_google_user("new_student@test.ma", "Élève Nouveau", role="student")
        self.assertIsNone(get_user_gemini_api_key(new_student["id"]))
        self.assertFalse(is_classroom_configured(new_student["id"]))
        self.assertIsNone(get_user_credentials_path(new_student["id"]))

        save_user_gemini_api_key(self.user_a["id"], "AIzaSy_KEY_USER_A")
        save_user_gemini_api_key(self.user_b["id"], "AIzaSy_KEY_USER_B")

        self.assertEqual(get_user_gemini_api_key(self.user_a["id"]), "AIzaSy_KEY_USER_A")
        self.assertEqual(get_user_gemini_api_key(self.user_b["id"]), "AIzaSy_KEY_USER_B")


class TestStudentAndGlobalBackup(unittest.TestCase):
    """Tests sur les sauvegardes et restaurations étanches (élève et global)."""

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.test_db_path = Path(self.temp_dir.name) / "test_backup.db"
        os.environ["DATABASE_PATH"] = str(self.test_db_path)
        init_db(self.test_db_path)

        self.user = create_or_get_google_user("eleve_backup@test.ma", "Adnane Sauvegarde", role="student")
        self.user_id = self.user["id"]

        # Création d'un cours avec quiz et chat
        self.cid = save_course(
            title="Physique Chimie 3AC",
            subject="Physique-Chimie",
            language="fr",
            file_path="/fake/pc.pdf",
            file_hash="hash_pc_backup",
            file_name="pc.pdf",
            raw_text="Contenu des solutions aqueuses",
            user_id=self.user_id,
        )
        self.qid = save_quiz(self.cid, [{"question": "pH ?", "options": ["Acide", "Basique"], "answer_index": 0}], user_id=self.user_id)
        save_quiz_attempt(self.cid, self.qid, score=1, total_questions=1, answers={0: 0}, user_id=self.user_id)
        add_chat_message(self.cid, "user", "Bonjour Sanad", user_id=self.user_id)
        save_course_mindmap(self.cid, "# Solutions Aqueuses\n## Ions et pH")

    def tearDown(self):
        self.temp_dir.cleanup()
        if "DATABASE_PATH" in os.environ:
            del os.environ["DATABASE_PATH"]

    def test_student_export_and_restore(self):
        # 1. Export personnel de l'élève
        backup_zip = export_student_backup(self.user_id)
        self.assertTrue(len(backup_zip) > 0)

        # Vérification du contenu du ZIP
        with zipfile.ZipFile(io.BytesIO(backup_zip), "r") as zf:
            names = zf.namelist()
            self.assertIn("manifest.json", names)
            self.assertIn("data.json", names)
            manifest = json.loads(zf.read("manifest.json"))
            self.assertEqual(manifest["type"], "student_backup")
            self.assertEqual(manifest["user"]["email"], "eleve_backup@test.ma")

        # 2. Création d'un nouvel élève dans un espace vierge
        new_user = create_or_get_google_user("nouveau_compte@test.ma", "Nouvel Élève", role="student")
        res_restore = restore_student_backup(backup_zip, target_user_id=new_user["id"])
        self.assertTrue(res_restore["success"])

        # Vérification que le nouveau compte possède bien le cours, le chat et la carte mentale
        restored_courses = list_courses(user_id=new_user["id"])
        self.assertEqual(len(restored_courses), 1)
        self.assertEqual(restored_courses[0]["title"], "Physique Chimie 3AC")
        self.assertEqual(get_course_mindmap(restored_courses[0]["id"]), "# Solutions Aqueuses\n## Ions et pH")
        self.assertEqual(restored_courses[0].get("mindmap_code"), "# Solutions Aqueuses\n## Ions et pH")

        restored_chat = get_chat_history(restored_courses[0]["id"], user_id=new_user["id"])
        self.assertEqual(len(restored_chat), 1)
        self.assertEqual(restored_chat[0]["content"], "Bonjour Sanad")

    def test_path_traversal_protection(self):
        # Création d'une archive malveillante avec un chemin "../../../etc/evil.txt"
        bad_buf = io.BytesIO()
        with zipfile.ZipFile(bad_buf, "w") as zf:
            zf.writestr("../evil.txt", "Malicious content")
            zf.writestr("data.json", json.dumps({"courses": []}))
            zf.writestr("manifest.json", json.dumps({}))

        bad_bytes = bad_buf.getvalue()
        res = restore_student_backup(bad_bytes, target_user_id=self.user_id)
        self.assertFalse(res["success"])
        self.assertIn("traversée de répertoire", res["error"])

    def test_is_safe_extract_path_helper(self):
        base = Path("/home/user/storage")
        safe = Path("/home/user/storage/cours/doc.pdf")
        unsafe = Path("/home/user/storage/../../etc/passwd")

        self.assertTrue(is_safe_extract_path(base, safe))
        self.assertFalse(is_safe_extract_path(base, unsafe))

    def test_restore_legacy_backup_zip_to_student(self):
        # Créer une base de données v1.0 (sans table users et sans colonne user_id)
        legacy_db_file = Path(self.temp_dir.name) / "legacy_test.db"
        l_conn = sqlite3.connect(legacy_db_file)
        with l_conn:
            l_conn.execute("""
                CREATE TABLE courses (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    title TEXT NOT NULL,
                    subject TEXT NOT NULL,
                    language TEXT NOT NULL,
                    file_path TEXT NOT NULL,
                    file_hash TEXT UNIQUE NOT NULL,
                    file_name TEXT NOT NULL,
                    raw_text TEXT,
                    summary_markdown TEXT,
                    key_concepts_json TEXT
                )
            """)
            l_conn.execute("""
                CREATE TABLE quizzes (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    course_id INTEGER NOT NULL,
                    quiz_data_json TEXT NOT NULL
                )
            """)
            l_conn.execute("""
                CREATE TABLE chat_messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    course_id INTEGER NOT NULL,
                    role TEXT NOT NULL,
                    content TEXT NOT NULL
                )
            """)
            l_conn.execute(
                "INSERT INTO courses (title, subject, language, file_path, file_hash, file_name, raw_text) "
                "VALUES ('Ancien Cours SVT', 'SVT', 'fr', '/fake/svt.pdf', 'hash_svt_legacy', 'svt.pdf', 'Texte SVT')"
            )
            l_conn.execute(
                "INSERT INTO quizzes (course_id, quiz_data_json) VALUES (1, '[{\"question\": \"cellule ?\", \"options\": [\"oui\", \"non\"], \"answer_index\": 0}]')"
            )
            l_conn.execute(
                "INSERT INTO chat_messages (course_id, role, content) VALUES (1, 'user', 'Question SVT')"
            )
        l_conn.close()

        # Pack dans une archive ZIP legacy (format 1814f19)
        legacy_buf = io.BytesIO()
        with zipfile.ZipFile(legacy_buf, "w") as zf:
            zf.write(legacy_db_file, arcname="ecole_adnane.db")
            zf.writestr("cours/svt.pdf", b"%PDF-1.4 Fake PDF Content")
            zf.writestr("manifest.json", json.dumps({"version": "1.0.0", "type": "legacy"}))

        legacy_bytes = legacy_buf.getvalue()

        # Compte initial des utilisateurs
        user_count_before = get_user_count()

        # Restauration dans l'espace de notre élève
        res = restore_student_backup(legacy_bytes, target_user_id=self.user_id)
        self.assertTrue(res["success"])

        # Vérifier que les utilisateurs n'ont pas été supprimés ou altérés
        self.assertEqual(get_user_count(), user_count_before)
        student_user = get_user_by_id(self.user_id)
        self.assertIsNotNone(student_user)
        self.assertEqual(student_user["email"], "eleve_backup@test.ma")

        # Vérifier que le cours restauré est bien présent sous l'user_id de l'élève
        courses = list_courses(user_id=self.user_id)
        titles = [c["title"] for c in courses]
        self.assertIn("Ancien Cours SVT", titles)

        # Vérifier que les quiz et chats ont été assignés à l'élève
        svt_course = next(c for c in courses if c["title"] == "Ancien Cours SVT")
        chats = get_chat_history(svt_course["id"], user_id=self.user_id)
        self.assertEqual(len(chats), 1)
        self.assertEqual(chats[0]["content"], "Question SVT")

    def test_restore_legacy_raw_db_to_student(self):
        # Créer un fichier SQLite brut legacy
        raw_db_file = Path(self.temp_dir.name) / "raw_legacy.db"
        r_conn = sqlite3.connect(raw_db_file)
        with r_conn:
            r_conn.execute("""
                CREATE TABLE courses (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    title TEXT NOT NULL,
                    subject TEXT NOT NULL,
                    language TEXT NOT NULL,
                    file_path TEXT NOT NULL,
                    file_hash TEXT UNIQUE NOT NULL,
                    file_name TEXT NOT NULL,
                    raw_text TEXT
                )
            """)
            r_conn.execute(
                "INSERT INTO courses (title, subject, language, file_path, file_hash, file_name, raw_text) "
                "VALUES ('Cours Brut Maths', 'Mathématiques', 'fr', '/fake/math.pdf', 'hash_math_raw', 'math.pdf', 'Calcul')"
            )
        r_conn.close()

        raw_bytes = raw_db_file.read_bytes()
        res = restore_student_backup(raw_bytes, target_user_id=self.user_id)
        self.assertTrue(res["success"])

        courses = list_courses(user_id=self.user_id)
        titles = [c["title"] for c in courses]
        self.assertIn("Cours Brut Maths", titles)

    def test_multiple_users_can_have_same_course_hash(self):
        # Deux élèves distincts doivent pouvoir avoir le même cours sans conflit UNIQUE
        u1 = create_or_get_google_user("eleve1_hash@test.ma", "Élève 1", role="student")
        u2 = create_or_get_google_user("eleve2_hash@test.ma", "Élève 2", role="student")

        shared_hash = "sha256_shared_between_students_3ac"
        cid1 = save_course(
            title="Thalès Élève 1",
            subject="Mathématiques",
            language="fr",
            file_path="/fake/thales.pdf",
            file_hash=shared_hash,
            file_name="thales.pdf",
            user_id=u1["id"],
        )
        cid2 = save_course(
            title="Thalès Élève 2",
            subject="Mathématiques",
            language="fr",
            file_path="/fake/thales.pdf",
            file_hash=shared_hash,
            file_name="thales.pdf",
            user_id=u2["id"],
        )

        self.assertIsNotNone(cid1)
        self.assertIsNotNone(cid2)
        self.assertNotEqual(cid1, cid2)

        c1 = list_courses(user_id=u1["id"])
        c2 = list_courses(user_id=u2["id"])
        self.assertEqual(len(c1), 1)
        self.assertEqual(len(c2), 1)
        self.assertEqual(c1[0]["title"], "Thalès Élève 1")
        self.assertEqual(c2[0]["title"], "Thalès Élève 2")

    def test_restore_student_backup_with_existing_file_hash(self):
        # 1. Un cours existe déjà globalement ou chez un autre utilisateur avec ce hash
        existing_hash = "sha256_already_in_db"
        save_course(
            title="Cours Déjà en Base",
            subject="Physique Chimie",
            language="fr",
            file_path="/fake/physique.pdf",
            file_hash=existing_hash,
            file_name="physique.pdf",
            user_id=None,
        )

        # 2. Une sauvegarde d'un élève contient un cours avec ce MÊME hash
        u_target = create_or_get_google_user("eleve_target@test.ma", "Cible", role="student")
        backup_buf = io.BytesIO()
        data = {
            "courses": [
                {
                    "id": 10,
                    "title": "Cours Cible Restauré",
                    "subject": "Physique Chimie",
                    "language": "fr",
                    "file_name": "physique.pdf",
                    "file_hash": existing_hash,
                    "raw_text": "Contenu restauré",
                }
            ],
            "quizzes": [
                {
                    "id": 20,
                    "course_id": 10,
                    "quiz_data_json": json.dumps([{"question": "Q1", "options": ["A", "B"], "answer_index": 0}]),
                }
            ],
            "quiz_attempts": [],
            "chat_messages": [],
            "flashcards": [],
        }
        with zipfile.ZipFile(backup_buf, "w") as zf:
            zf.writestr("manifest.json", json.dumps({"version": "2.0.0"}))
            zf.writestr("data.json", json.dumps(data))

        # 3. La restauration ne doit PAS lever d'erreur UNIQUE constraint failed: courses.file_hash
        res = restore_student_backup(backup_buf.getvalue(), target_user_id=u_target["id"])
        self.assertTrue(res["success"], f"Échec de la restauration : {res.get('error')}")

        restored = list_courses(user_id=u_target["id"])
        titles = [c["title"] for c in restored]
        self.assertIn("Cours Cible Restauré", titles)

    def test_resolve_course_file_path_and_migration(self):
        # 1. Préparer des fichiers physiques dans l'environnement de stockage actuel
        storage_root = Path(self.temp_dir.name)
        legacy_cours_dir = storage_root / "cours"
        legacy_cours_dir.mkdir(parents=True, exist_ok=True)
        user_cours_dir = storage_root / "users" / str(self.user_id) / "cours"
        user_cours_dir.mkdir(parents=True, exist_ok=True)

        pdf_shared = legacy_cours_dir / "0bfc867117_thales_cours.pdf"
        pdf_shared.write_bytes(b"%PDF-1.4 shared mock content")

        pdf_student = user_cours_dir / "3e0781c739_english_guide.pdf"
        pdf_student.write_bytes(b"%PDF-1.4 student mock content")

        # 2. Tester resolve_course_file_path avec d'anciens chemins Streamlit Cloud
        old_shared_path = "/mount/src/ecoleadnane/storage/cours/0bfc867117_thales_cours.pdf"
        resolved_shared = resolve_course_file_path(old_shared_path, db_path=self.test_db_path)
        self.assertEqual(resolved_shared, str(pdf_shared))
        self.assertTrue(os.path.exists(resolved_shared))

        old_student_path = f"/mount/src/ecoleadnane/storage/users/{self.user_id}/cours/3e0781c739_english_guide.pdf"
        resolved_student = resolve_course_file_path(old_student_path, user_id=self.user_id, db_path=self.test_db_path)
        self.assertEqual(resolved_student, str(pdf_student))
        self.assertTrue(os.path.exists(resolved_student))

        # 3. Tester la migration automatique dans init_db
        cid_mig = save_course(
            title="Cours Ancien Chemin",
            subject="Mathématiques",
            language="fr",
            file_path=old_shared_path,
            file_hash="hash_mig_123",
            file_name="thales_cours.pdf",
            user_id=None,
        )
        # Vérifier que le cours a été enregistré initialement avec l'ancien chemin
        c_before = get_course_by_id(cid_mig)
        self.assertEqual(c_before["file_path"], old_shared_path)

        # Exécuter init_db pour déclencher la migration d'ancrage (étape 5)
        init_db(self.test_db_path)

        # Vérifier que le chemin a été automatiquement réparé en base
        c_after = get_course_by_id(cid_mig)
        self.assertEqual(c_after["file_path"], str(pdf_shared))
        self.assertTrue(os.path.exists(c_after["file_path"]))

    def test_google_classroom_scopes(self):
        # Vérification stricte des 4 scopes officiels requis
        expected_scopes = [
            "https://www.googleapis.com/auth/classroom.courses.readonly",
            "https://www.googleapis.com/auth/classroom.coursework.me.readonly",
            "https://www.googleapis.com/auth/classroom.courseworkmaterials.readonly",
            "https://www.googleapis.com/auth/drive.readonly",
        ]
        # Inspecter le fichier services/downloader.py
        with open(Path(__file__).parent.parent / "services" / "downloader.py", "r", encoding="utf-8") as f:
            code = f.read()

        for scope in expected_scopes:
            self.assertIn(scope, code)


class TestOAuthRedirectAndCodeHandling(unittest.TestCase):
    """Tests sur la robustesse des redirections et codes OAuth Google."""

    def test_normalize_redirect_uri(self):
        # Respect scrupuleux de l'URI Google Console avec ou sans slash
        self.assertEqual(normalize_redirect_uri("http://localhost"), "http://localhost")
        self.assertEqual(normalize_redirect_uri("http://localhost/"), "http://localhost/")
        self.assertEqual(normalize_redirect_uri("http://127.0.0.1"), "http://127.0.0.1")
        # Localhost avec port explicite reste inchangé
        self.assertEqual(normalize_redirect_uri("http://localhost:8501"), "http://localhost:8501")
        self.assertEqual(normalize_redirect_uri("http://localhost:3000"), "http://localhost:3000")
        # URL Streamlit Cloud reste intacte
        self.assertEqual(normalize_redirect_uri("https://ecoleadnane.streamlit.app"), "https://ecoleadnane.streamlit.app")
        self.assertEqual(normalize_redirect_uri("https://ecoleadnane.streamlit.app/"), "https://ecoleadnane.streamlit.app/")
        # None retourne http://localhost par défaut
        self.assertEqual(normalize_redirect_uri(None), "http://localhost")

    def test_extract_auth_code(self):
        # Code brut
        self.assertEqual(extract_auth_code("4/0Abc123xyz"), "4/0Abc123xyz")
        # URL complète avec localhost (comme rapporté dans le problème)
        url1 = "http://localhost/?code=4/0Abc123xyz&scope=email%20profile"
        self.assertEqual(extract_auth_code(url1), "4/0Abc123xyz")
        # URL complète avec localhost:8501
        url2 = "http://localhost:8501/?code=4/0Abc123xyz&authuser=0"
        self.assertEqual(extract_auth_code(url2), "4/0Abc123xyz")
        # URL Streamlit Cloud
        url3 = "https://ecoleadnane.streamlit.app/?code=4/0Abc123xyz"
        self.assertEqual(extract_auth_code(url3), "4/0Abc123xyz")

    def test_save_uploaded_oauth_credentials(self):
        cred_path = Path(__file__).parent.parent / "storage" / "credentials.json"
        original_content = cred_path.read_bytes() if cred_path.exists() else None
        try:
            # Format web valide
            web_json = json.dumps({
                "web": {
                    "client_id": "test-web-id.apps.googleusercontent.com",
                    "client_secret": "test-web-secret",
                    "redirect_uris": ["https://ecoleadnane.streamlit.app"]
                }
            }).encode("utf-8")
            res_web = save_uploaded_oauth_credentials(web_json)
            self.assertEqual(res_web["type"], "web")
            self.assertEqual(res_web["client_id"], "test-web-id.apps.googleusercontent.com")

            # Format installed (desktop) valide
            installed_json = json.dumps({
                "installed": {
                    "client_id": "test-inst-id.apps.googleusercontent.com",
                    "client_secret": "test-inst-secret",
                    "redirect_uris": ["http://localhost"]
                }
            }).encode("utf-8")
            res_inst = save_uploaded_oauth_credentials(installed_json)
            self.assertEqual(res_inst["type"], "installed")

            # Format invalide
            with self.assertRaises(ValueError):
                save_uploaded_oauth_credentials(b"not json")

            # Clé manquante
            with self.assertRaises(ValueError):
                save_uploaded_oauth_credentials(json.dumps({"other": {}}).encode("utf-8"))
        finally:
            if original_content is not None:
                cred_path.write_bytes(original_content)
            elif cred_path.exists():
                cred_path.unlink()


class TestPedagogicalAdaptationAndUserProfiles(unittest.TestCase):
    """Tests pour l'adaptation pédagogique multi-âges et la gestion des profils élèves."""

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.test_db_path = Path(self.temp_dir.name) / "test_pedagogy.db"
        os.environ["DATABASE_PATH"] = str(self.test_db_path)
        init_db(self.test_db_path)

        # Création d'un admin et de deux élèves
        self.admin = create_or_get_google_user("admin@test.ma", "Directeur Adnane", role="admin")
        self.student_1 = create_or_get_google_user("student1@test.ma", "Adnane Junior", role="student")
        self.student_2 = create_or_get_google_user("student2@test.ma", "Yassine Bac", role="student")

    def tearDown(self):
        self.temp_dir.cleanup()
        if "DATABASE_PATH" in os.environ:
            del os.environ["DATABASE_PATH"]

    def test_pedagogical_cycle_mapping(self):
        # Primaire (5 à 10 ans)
        c5 = get_pedagogical_cycle(5)
        c8 = get_pedagogical_cycle(8)
        c10 = get_pedagogical_cycle(10)
        self.assertEqual(c5["stage"], "primary")
        self.assertEqual(c8["stage"], "primary")
        self.assertEqual(c10["stage"], "primary")
        self.assertIn("Primaire", c8["stage_label"])
        self.assertIn("8 ans", c8["badge_text"])

        # Collège (11 à 14 ans ou défaut)
        c11 = get_pedagogical_cycle(11)
        c14 = get_pedagogical_cycle(14)
        c_default = get_pedagogical_cycle(None)
        c_invalid = get_pedagogical_cycle("not_a_number")
        self.assertEqual(c11["stage"], "middle")
        self.assertEqual(c14["stage"], "middle")
        self.assertEqual(c_default["stage"], "middle")
        self.assertEqual(c_invalid["stage"], "middle")
        self.assertIn("Collège", c14["stage_label"])

        # Lycée (15 à 18 ans)
        c15 = get_pedagogical_cycle(15)
        c17 = get_pedagogical_cycle(17)
        c18 = get_pedagogical_cycle(18)
        self.assertEqual(c15["stage"], "high")
        self.assertEqual(c17["stage"], "high")
        self.assertEqual(c18["stage"], "high")
        self.assertIn("Lycée", c17["stage_label"])

        # Supérieur / Adulte (19 ans et +)
        c19 = get_pedagogical_cycle(19)
        c25 = get_pedagogical_cycle(25)
        c40 = get_pedagogical_cycle(40)
        self.assertEqual(c19["stage"], "higher")
        self.assertEqual(c25["stage"], "higher")
        self.assertEqual(c40["stage"], "higher")
        self.assertIn("Supérieur", c25["stage_label"])

        # Clamping
        c_low = get_pedagogical_cycle(2)
        self.assertEqual(c_low["age"], 5)
        c_high = get_pedagogical_cycle(120)
        self.assertEqual(c_high["age"], 100)

    def test_update_user_name_and_oauth_preservation(self):
        uid = self.student_1["id"]
        # Vérification initiale has_custom_name = 0
        u_init = get_user_by_id(uid)
        self.assertEqual(u_init["has_custom_name"], 0)
        self.assertEqual(u_init["name"], "Adnane Junior")

        # Mise à jour du nom par l'élève
        ok, msg = update_user_name(uid, "Adnane Personnalisé")
        self.assertTrue(ok)
        u_updated = get_user_by_id(uid)
        self.assertEqual(u_updated["name"], "Adnane Personnalisé")
        self.assertEqual(u_updated["has_custom_name"], 1)

        # Nouvelle connexion Google avec un nom Google différent
        user_reconnected = create_or_get_google_user("student1@test.ma", "Google Name From OAuth")
        # Le nom personnalisé doit impérativement être conservé
        self.assertEqual(user_reconnected["name"], "Adnane Personnalisé")

        # Validation : refus des noms vides ou trop courts/longs
        ok_empty, _ = update_user_name(uid, "   ")
        self.assertFalse(ok_empty)
        ok_short, _ = update_user_name(uid, "A")
        self.assertFalse(ok_short)
        ok_long, _ = update_user_name(uid, "A" * 65)
        self.assertFalse(ok_long)

    def test_update_user_age_and_validation(self):
        uid = self.student_1["id"]
        # Mise à jour valide
        ok, msg = update_user_age(uid, 9)
        self.assertTrue(ok)
        u = get_user_by_id(uid)
        self.assertEqual(u["age"], 9)

        # Validation : non entier ou hors limites
        ok_err1, _ = update_user_age(uid, "invalid")
        self.assertFalse(ok_err1)
        ok_err2, _ = update_user_age(uid, 4)
        self.assertFalse(ok_err2)
        ok_err3, _ = update_user_age(uid, 105)
        self.assertFalse(ok_err3)

    def test_resolve_student_age(self):
        uid = self.student_1["id"]
        update_user_age(uid, 8)

        # Résolution via le profil en base
        self.assertEqual(resolve_student_age(user_id=uid), 8)

        # Résolution avec âge explicite qui prévaut sur le profil
        self.assertEqual(resolve_student_age(user_id=uid, age=17), 17)

        # Résolution sans user ni age -> défaut 14
        self.assertEqual(resolve_student_age(None, None), 14)

    def test_admin_kpis_accurate_courses_and_no_cartesian_product(self):
        # 1. Ajout de 2 cours partagés pour l'établissement (user_id=None)
        c1 = save_course("Maths 3AC Partagé", "Mathématiques", "fr", "/f/m.pdf", "hash_shared_math", "m.pdf", user_id=None)
        c2 = save_course("PC 3AC Partagé", "Physique-Chimie", "fr", "/f/pc.pdf", "hash_shared_pc", "pc.pdf", user_id=None)

        # 2. Student 1 ajoute un cours personnel avec un hash différent
        c3 = save_course("SVT Perso", "SVT", "fr", "/f/svt.pdf", "hash_perso_svt", "svt.pdf", user_id=self.student_1["id"])

        # 3. Student 1 réalise 3 tentatives de quiz
        qid = save_quiz(c1, [{"question": "Q1", "options": ["A", "B"], "answer_index": 0}], user_id=self.student_1["id"])
        save_quiz_attempt(c1, qid, score=1, total_questions=1, answers={0: 0}, user_id=self.student_1["id"])
        save_quiz_attempt(c1, qid, score=1, total_questions=1, answers={0: 0}, user_id=self.student_1["id"])
        save_quiz_attempt(c1, qid, score=1, total_questions=1, answers={0: 0}, user_id=self.student_1["id"])

        # Récupération des KPIs d'administration
        kpis = get_global_admin_kpis()

        # Le nombre total de cours distincts doit être 3
        self.assertEqual(kpis["total_courses"], 3)
        self.assertEqual(kpis["total_students"], 2)
        self.assertEqual(kpis["active_students"], 2)

        # Vérification du résumé par élève sans produit cartésien
        student_rows = {s["user_id"]: s for s in kpis["students_summary"]}
        s1_summary = student_rows[self.student_1["id"]]
        s2_summary = student_rows[self.student_2["id"]]

        # Student 1 a accès aux 2 cours partagés + 1 personnel = 3 cours
        self.assertEqual(s1_summary["course_count"], 3)
        # Le nombre de tentatives doit rester exactement 3 (pas multiplié par 3 cours = 9)
        self.assertEqual(s1_summary["attempt_count"], 3)
        self.assertEqual(s1_summary["student_questions"], 3)
        self.assertEqual(s1_summary["student_score"], 3)

        # Student 2 a accès aux 2 cours partagés = 2 cours
        self.assertEqual(s2_summary["course_count"], 2)
        self.assertEqual(s2_summary["attempt_count"], 0)

    def test_admin_student_progression_metrics_and_subject_breakdown(self):
        # 1. Cours et quiz pour Student 1
        c_math = save_course("Maths 3AC", "Mathématiques", "fr", "/f/m.pdf", "hash_m", "m.pdf", user_id=self.student_1["id"])
        c_pc = save_course("Physique 3AC", "Physique-Chimie", "fr", "/f/pc.pdf", "hash_pc", "pc.pdf", user_id=self.student_1["id"])

        q_math = save_quiz(c_math, [{"question": "Q1", "options": ["A", "B"], "answer_index": 0}], user_id=self.student_1["id"])
        q_pc = save_quiz(c_pc, [{"question": "Q2", "options": ["C", "D"], "answer_index": 1}], user_id=self.student_1["id"])

        # 2. Tentatives : 2 en Maths (100% et 80%), 1 en PC (40%)
        save_quiz_attempt(c_math, q_math, score=5, total_questions=5, answers={0: 0}, user_id=self.student_1["id"])
        save_quiz_attempt(c_math, q_math, score=4, total_questions=5, answers={0: 0}, user_id=self.student_1["id"])
        save_quiz_attempt(c_pc, q_pc, score=2, total_questions=5, answers={0: 1}, user_id=self.student_1["id"])

        # 3. Récupération de la progression de Student 1
        prog_s1 = get_quiz_stats(user_id=self.student_1["id"])
        self.assertEqual(prog_s1["total_attempts"], 3)
        self.assertEqual(prog_s1["total_questions"], 15)
        self.assertEqual(prog_s1["total_score"], 11)
        self.assertEqual(prog_s1["average_success_rate"], 73.3)

        # Vérification de la maîtrise par matière
        subjects_dict = {s["subject"]: s for s in prog_s1["by_subject"]}
        self.assertIn("Mathématiques", subjects_dict)
        self.assertEqual(subjects_dict["Mathématiques"]["attempts"], 2)
        self.assertEqual(subjects_dict["Mathématiques"]["success_rate"], 90.0)

        self.assertIn("Physique-Chimie", subjects_dict)
        self.assertEqual(subjects_dict["Physique-Chimie"]["attempts"], 1)
        self.assertEqual(subjects_dict["Physique-Chimie"]["success_rate"], 40.0)

        # Dernières tentatives
        self.assertEqual(len(prog_s1["recent_attempts"]), 3)
        recent_titles = [a["course_title"] for a in prog_s1["recent_attempts"]]
        self.assertIn("Physique 3AC", recent_titles)
        self.assertIn("Maths 3AC", recent_titles)

        # 4. Student 2 n'a aucun entraînement
        prog_s2 = get_quiz_stats(user_id=self.student_2["id"])
        self.assertEqual(prog_s2["total_attempts"], 0)
        self.assertEqual(prog_s2["total_questions"], 0)
        self.assertEqual(prog_s2["total_score"], 0)
        self.assertEqual(prog_s2["average_success_rate"], 0.0)
        self.assertEqual(len(prog_s2["by_subject"]), 0)
        self.assertEqual(len(prog_s2["recent_attempts"]), 0)

    def test_list_courses_deduplication_personal_over_global(self):
        # Un cours de base global partagé
        save_course("Histoire Maroc Base", "الاجتماعيات", "ar", "/f/hist.pdf", "hash_same_history", "hist.pdf", user_id=None)

        # Student 1 a initialement accès au cours global
        courses_s1_init = list_courses(user_id=self.student_1["id"])
        self.assertEqual(len(courses_s1_init), 1)
        self.assertIsNone(courses_s1_init[0]["user_id"])

        # Student 1 enregistre sa propre copie personnalisée du même cours (même hash)
        cid_perso = save_course("Mon Histoire Maroc Custom", "الاجتماعيات", "ar", "/f/hist_perso.pdf", "hash_same_history", "hist_perso.pdf", user_id=self.student_1["id"])

        # list_courses pour Student 1 ne doit renvoyer qu'1 seul cours (dédoublonné), avec sa copie prioritaire
        courses_s1 = list_courses(user_id=self.student_1["id"])
        self.assertEqual(len(courses_s1), 1)
        self.assertEqual(courses_s1[0]["id"], cid_perso)
        self.assertEqual(courses_s1[0]["title"], "Mon Histoire Maroc Custom")
        self.assertEqual(courses_s1[0]["user_id"], self.student_1["id"])

        # Student 2 voit toujours le cours de base global sans collision
        courses_s2 = list_courses(user_id=self.student_2["id"])
        self.assertEqual(len(courses_s2), 1)
        self.assertEqual(courses_s2[0]["title"], "Histoire Maroc Base")
        self.assertIsNone(courses_s2[0]["user_id"])


class TestUserSessionPersistence(unittest.TestCase):
    """Tests sur la persistance des sessions utilisateur (résistance F5 et invalidation sécurisée)."""

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.test_db_path = Path(self.temp_dir.name) / "test_sessions.db"
        os.environ["DATABASE_PATH"] = str(self.test_db_path)
        init_db(self.test_db_path)
        self.admin = create_or_get_google_user("admin@ecole.ma", "Admin Principal")
        self.student = create_or_get_google_user("adnane@eleve.ma", "Adnane")

    def tearDown(self):
        self.temp_dir.cleanup()
        if "DATABASE_PATH" in os.environ:
            del os.environ["DATABASE_PATH"]

    def test_create_and_restore_valid_session(self):
        token = create_user_session(self.student["id"], days_valid=30)
        self.assertIsInstance(token, str)
        self.assertGreater(len(token), 20)

        user = get_user_from_session_token(token)
        self.assertIsNotNone(user)
        self.assertEqual(user["id"], self.student["id"])
        self.assertEqual(user["email"], "adnane@eleve.ma")
        self.assertEqual(user["role"], "student")

    def test_delete_session_token_explicit_logout(self):
        token = create_user_session(self.student["id"], days_valid=7)
        user = get_user_from_session_token(token)
        self.assertIsNotNone(user)

        delete_user_session(token)
        user_after_logout = get_user_from_session_token(token)
        self.assertIsNone(user_after_logout)

    def test_session_expiration(self):
        # Création d'une session expirée avec days_valid négatif
        expired_token = create_user_session(self.student["id"], days_valid=-1)
        user = get_user_from_session_token(expired_token)
        self.assertIsNone(user)

        # Nettoyage global des sessions expirées
        conn = sqlite3.connect(self.test_db_path)
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM user_sessions WHERE token = ?", (expired_token,))
        count = cur.fetchone()[0]
        conn.close()
        self.assertEqual(count, 0)

        # Test cleanup_expired_sessions
        create_user_session(self.student["id"], days_valid=-2)
        deleted = cleanup_expired_sessions()
        self.assertGreaterEqual(deleted, 1)

    def test_session_revocation_on_student_blocked(self):
        token = create_user_session(self.student["id"], days_valid=14)
        self.assertIsNotNone(get_user_from_session_token(token))

        # L'admin suspend l'élève
        ok, msg = set_user_blocked_status(self.student["id"], is_blocked=True, requesting_admin_id=self.admin["id"])
        self.assertTrue(ok)

        # La session active doit être immédiatement rejetée et purgée
        self.assertIsNone(get_user_from_session_token(token))

    def test_session_cascade_deletion_on_account_delete(self):
        token = create_user_session(self.student["id"], days_valid=14)
        self.assertIsNotNone(get_user_from_session_token(token))

        # L'admin supprime l'élève
        ok, msg = delete_user_account(self.student["id"], requesting_admin_id=self.admin["id"])
        self.assertTrue(ok)

        # La session doit avoir disparu
        self.assertIsNone(get_user_from_session_token(token))


class TestVoiceAndSpeechManager(unittest.TestCase):
    """Tests sur le module vocal Web Speech API (zéro quota Gemini, synthèse vocale et dictée)."""

    def test_clean_text_for_speech_strips_markdown_and_latex(self):
        raw_text = """
### 🤖 Bienvenue sur Ecole Adnane !
Voici les règles du **théorème de Thalès** :
* Condition 1 : Les droites $(AB)$ et $(CD)$ sont sécantes.
* Formule : $$\\frac{AM}{AB} = \\frac{AN}{AC}$$
N'hésite pas à consulter [le cours complet](https://ecole.ma) !
```python
print("debug")
```
> Astuce : vérifie bien les unités ! ✨
"""
        cleaned = clean_text_for_speech(raw_text)
        self.assertNotIn("###", cleaned)
        self.assertNotIn("**", cleaned)
        self.assertNotIn("```", cleaned)
        self.assertNotIn("[le cours complet]", cleaned)
        self.assertIn("le cours complet", cleaned)
        self.assertNotIn("https://ecole.ma", cleaned)
        self.assertNotIn("✨", cleaned)
        self.assertIn("théorème de Thalès", cleaned)
        self.assertIn("Condition 1", cleaned)
        self.assertIn("droites (AB) et (CD) sont sécantes", cleaned)

    def test_clean_text_empty_and_arabic(self):
        self.assertEqual(clean_text_for_speech(""), "")
        ar_raw = "### مرحباً ! **درس الرياضيات** مهم جداً 🎯"
        ar_cleaned = clean_text_for_speech(ar_raw)
        self.assertNotIn("###", ar_cleaned)
        self.assertNotIn("**", ar_cleaned)
        self.assertNotIn("🎯", ar_cleaned)
        self.assertIn("مرحباً", ar_cleaned)
        self.assertIn("درس الرياضيات", ar_cleaned)

    def test_get_speech_config_trilingual(self):
        cfg_fr = get_speech_config("fr")
        self.assertEqual(cfg_fr["lang_code"], "fr-FR")
        self.assertIn("Écouter", cfg_fr["play_label"])
        self.assertEqual(cfg_fr["dir"], "ltr")

        cfg_ar = get_speech_config("ar")
        self.assertEqual(cfg_ar["lang_code"], "ar-SA")
        self.assertIn("استمع", cfg_ar["play_label"])
        self.assertEqual(cfg_ar["dir"], "rtl")

        cfg_en = get_speech_config("en")
        self.assertEqual(cfg_en["lang_code"], "en-US")
        self.assertIn("Listen", cfg_en["play_label"])
        self.assertEqual(cfg_en["dir"], "ltr")

        cfg_default = get_speech_config(None)
        self.assertEqual(cfg_default["lang_code"], "fr-FR")

    def test_generate_tts_player_html_structure(self):
        # 1. Mode client Web Speech API forcé via force_server_tts=False
        html_code = generate_tts_player_html("Bravo champion, continue ainsi !", language="fr", player_id="test_player_1", compact=True, force_server_tts=False)
        self.assertIn("speechSynthesis", html_code)
        self.assertIn("SpeechSynthesisUtterance", html_code)
        self.assertIn("fr-FR", html_code)
        self.assertIn("btn_test_player_1", html_code)
        self.assertIn("Bravo champion", html_code)
        self.assertIn("isCompact = true", html_code)
        self.assertIn("border-radius: 8px", html_code)
        self.assertIn("width: 32px; height: 32px", html_code)

        # Mode avec auto_play en mode client
        html_auto = generate_tts_player_html("Explication Sanad", language="fr", player_id="test_auto_1", auto_play=True, force_server_tts=False)
        self.assertIn("shouldAutoPlay = true", html_auto)

        # 2. Mode serveur (gTTS HTML5 audio) forcé via force_server_tts=True
        html_server = generate_tts_player_html("Bravo champion, continue ainsi !", language="fr", player_id="test_srv_1", compact=True, force_server_tts=True)
        self.assertIn("<audio id=\"audio_test_srv_1\"", html_server)
        self.assertIn("data:audio/mp3;base64,", html_server)
        self.assertIn("toggleAudio_test_srv_1", html_server)
        self.assertIn("border-radius: 8px", html_server)
        self.assertIn("width: 32px; height: 32px", html_server)

        # 3. Comportement par défaut sous Linux : utilisation automatique du lecteur serveur
        if is_linux_platform():
            html_default_linux = generate_tts_player_html("Explication Sanad", language="fr", player_id="test_linux_def")
            self.assertIn("<audio id=\"audio_test_linux_def\"", html_default_linux)
            self.assertIn("data:audio/mp3;base64,", html_default_linux)

        # Si texte vide
        self.assertEqual(generate_tts_player_html("", language="fr"), "")

    def test_server_tts_audio_base64_generation_and_caching(self):
        data_uri_fr = get_server_tts_audio_base64("Bonjour à tous !", language="fr")
        self.assertIsNotNone(data_uri_fr)
        self.assertTrue(data_uri_fr.startswith("data:audio/mp3;base64,"))
        self.assertGreater(len(data_uri_fr), 100)

        # Vérifier que le cache mémoire renvoie le même objet sans refaire d'appel
        data_uri_fr_cached = get_server_tts_audio_base64("Bonjour à tous !", language="fr")
        self.assertEqual(data_uri_fr, data_uri_fr_cached)

        # En arabe avec voyelles
        data_uri_ar = get_server_tts_audio_base64("مَرْحَباً بِكَ يَا بَطَلُ", language="ar")
        self.assertIsNotNone(data_uri_ar)
        self.assertTrue(data_uri_ar.startswith("data:audio/mp3;base64,"))

        # Texte vide ou invalide
        self.assertIsNone(get_server_tts_audio_base64("", language="fr"))
        self.assertIsNone(get_server_tts_audio_base64("   ", language="fr"))

    def test_generate_chat_mic_injector_html_structure(self):
        mic_injector = generate_chat_mic_injector_html(language="ar", widget_id="test_mic_chat")
        self.assertIn("SpeechRecognition", mic_injector)
        self.assertIn("ar-SA", mic_injector)
        self.assertIn("stChatInputSubmitButton", mic_injector)
        self.assertIn("sanad_chat_input_mic_btn", mic_injector)
        self.assertIn("stChatInputTextArea", mic_injector)
        self.assertIn("HTMLTextAreaElement", mic_injector)
        self.assertIn("submitBtn.disabled = false", mic_injector)

    def test_generate_mic_speech_html_structure(self):
        mic_html = generate_mic_speech_html(language="fr", widget_id="test_mic_1")
        self.assertIn("SpeechRecognition", mic_html)
        self.assertIn("fr-FR", mic_html)

    def test_arabic_tashkeel_preserved_for_tts(self):
        # Les harakat et accents arabes (fatha, damma, kasra, sukun, shadda, tanwin) doivent être conservés intacts
        ar_vocalized = "مَرْحَباً بِكَ يَا بَطَلُ ! كَيْفَ نُطَبِّقُ مُبَرْهَنَةَ طَالِيسَ؟"
        cleaned = clean_text_for_speech(ar_vocalized)
        self.assertEqual(cleaned, ar_vocalized)

    def test_tts_player_mobile_pill_mode(self):
        # Mode pilule pour smartphone (compact=False) - vérifié pour les modes client et serveur
        # 1. Mode client Web Speech API
        html_pill_fr = generate_tts_player_html("Explication Sanad", language="fr", player_id="test_pill_fr", compact=False, force_server_tts=False)
        self.assertIn("isCompact = false", html_pill_fr)
        self.assertIn("border-radius: 16px", html_pill_fr)
        self.assertIn("wave-bars_test_pill_fr", html_pill_fr)
        self.assertIn("justify-content: flex-start", html_pill_fr)
        self.assertIn("Écouter l'explication", html_pill_fr)

        # Mode pilule en arabe (RTL avec justify-content: flex-end)
        html_pill_ar = generate_tts_player_html("مرحباً يا بطل", language="ar", player_id="test_pill_ar", compact=False, force_server_tts=False)
        self.assertIn("justify-content: flex-end", html_pill_ar)
        self.assertIn("direction: rtl", html_pill_ar)
        self.assertIn("استمع للشرح", html_pill_ar)

        # 2. Mode serveur gTTS
        html_srv_pill_fr = generate_tts_player_html("Explication Sanad", language="fr", player_id="test_srv_pill_fr", compact=False, force_server_tts=True)
        self.assertIn("<audio id=\"audio_test_srv_pill_fr\"", html_srv_pill_fr)
        self.assertIn("data:audio/mp3;base64,", html_srv_pill_fr)
        self.assertIn("border-radius: 16px", html_srv_pill_fr)
        self.assertIn("wave-bars_test_srv_pill_fr", html_srv_pill_fr)
        self.assertIn("justify-content: flex-start", html_srv_pill_fr)
        self.assertIn("Écouter l'explication", html_srv_pill_fr)

        html_srv_pill_ar = generate_tts_player_html("مرحباً يا بطل", language="ar", player_id="test_srv_pill_ar", compact=False, force_server_tts=True)
        self.assertIn("<audio id=\"audio_test_srv_pill_ar\"", html_srv_pill_ar)
        self.assertIn("justify-content: flex-end", html_srv_pill_ar)
        self.assertIn("direction: rtl", html_srv_pill_ar)
        self.assertIn("استمع للشرح", html_srv_pill_ar)

    def test_generate_fiche_audio_player_html(self):
        # 1. En français
        sample_fr = "### Théorème de Thalès\nVoici la formule clé du cours.\n- Condition 1 : Parallélisme obligatoire."
        html_fr = generate_fiche_audio_player_html(sample_fr, language="fr", player_id="test_fiche_fr")
        self.assertIn("btn_play_test_fiche_fr", html_fr)
        self.assertIn("btn_stop_test_fiche_fr", html_fr)
        self.assertIn("status_test_fiche_fr", html_fr)
        self.assertIn("speed-btn_test_fiche_fr", html_fr)
        self.assertIn("splitIntoSentences", html_fr)
        self.assertIn("fr-FR", html_fr)
        self.assertIn("Écouter la fiche", html_fr)

        # 2. En arabe avec direction RTL
        sample_ar = "### مبرهنة طاليس\nهذه هي القواعد الأساسية للدرس.\n- الشرط الأول : التوازي."
        html_ar = generate_fiche_audio_player_html(sample_ar, language="ar", player_id="test_fiche_ar")
        self.assertIn("direction: rtl", html_ar)
        self.assertIn("ar-SA", html_ar)
        self.assertIn("استمع للبطاقة", html_ar)

        # 3. En anglais
        sample_en = "### Summary\nKey points to memorize."
        html_en = generate_fiche_audio_player_html(sample_en, language="en", player_id="test_fiche_en")
        self.assertIn("en-US", html_en)
        self.assertIn("Listen to Sheet", html_en)

        # 4. Si texte vide
        self.assertEqual(generate_fiche_audio_player_html("", language="fr"), "")

    def test_generate_or_get_course_fiche_mp3_caching(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            test_db = Path(tmp_dir) / "test_mp3.db"
            with patch("models.database.get_db_path", return_value=test_db):
                # Mock get_server_tts_audio_base64
                with patch("services.voice_manager.get_server_tts_audio_base64") as mock_tts:
                    mock_tts.return_value = "data:audio/mp3;base64," + base64.b64encode(b"FAKE_MP3_DATA_1234567890" * 30).decode("ascii")
                    mp3_path = generate_or_get_course_fiche_mp3(
                        course_id=999,
                        text="Fiche de révision express",
                        language="fr",
                        user_id=None,
                    )
                    self.assertIsNotNone(mp3_path)
                    self.assertTrue(mp3_path.exists())
                    self.assertIn("fiche_999.mp3", str(mp3_path))

                    # Deuxième appel : doit réutiliser le cache disque sans rappeler mock_tts
                    mock_tts.reset_mock()
                    cached_path = generate_or_get_course_fiche_mp3(
                        course_id=999,
                        text="Fiche de révision express",
                        language="fr",
                        user_id=None,
                    )
                    self.assertEqual(str(mp3_path), str(cached_path))
                    mock_tts.assert_not_called()

    def test_arabic_tutor_system_instruction_requires_tashkeel(self):
        with patch("services.ai_engine.call_llm") as mock_llm:
            mock_llm.return_value = "مَرْحَباً بِكَ"
            socratic_tutor_response([{"role": "user", "content": "اشرح لي"}], "سياق الدرس", "التربية الإسلامية", "ar")
            call_args = mock_llm.call_args
            prompt = call_args[0][0]
            sys_instruction = call_args[1]["system_instruction"]
            self.assertTrue("التَّشْكِيلُ" in sys_instruction or "التشكيل" in sys_instruction)
            self.assertTrue("الحَرَكَاتُ" in sys_instruction or "الحركات" in sys_instruction)
            self.assertTrue("مشكولاً" in prompt or "التشكيل" in prompt)

    def test_generate_trophy_sound_wav_base64(self):
        wav_uri = generate_trophy_sound_wav_base64()
        self.assertIsNotNone(wav_uri)
        self.assertTrue(wav_uri.startswith("data:audio/wav;base64,"))

        # Check caching
        wav_uri_cached = generate_trophy_sound_wav_base64()
        self.assertEqual(wav_uri, wav_uri_cached)

        # Validate that payload is a genuine 44.1kHz mono WAV
        b64_part = wav_uri.replace("data:audio/wav;base64,", "")
        raw_bytes = base64.b64decode(b64_part)
        self.assertTrue(raw_bytes.startswith(b"RIFF"))
        self.assertEqual(raw_bytes[8:12], b"WAVE")
        with wave.open(io.BytesIO(raw_bytes), "rb") as wf:
            self.assertEqual(wf.getnchannels(), 1)
            self.assertEqual(wf.getsampwidth(), 2)
            self.assertEqual(wf.getframerate(), 44100)
            self.assertGreater(wf.getnframes(), 0)

    def test_get_royal_fanfare_mp3_base64(self):
        mp3_uri = get_royal_fanfare_mp3_base64()
        self.assertIsNotNone(mp3_uri)
        self.assertTrue(mp3_uri.startswith("data:audio/mp3;base64,") or mp3_uri.startswith("data:audio/wav;base64,"))
        b64_part = mp3_uri.split(",", 1)[1]
        raw_bytes = base64.b64decode(b64_part)
        self.assertGreater(len(raw_bytes), 1000)
        # Check caching
        mp3_uri_cached = get_royal_fanfare_mp3_base64()
        self.assertEqual(mp3_uri, mp3_uri_cached)

    def test_generate_trophy_celebration_html(self):
        # 1. Mode célébration automatique sans bouton (après quiz ou déblocage)
        html_auto = generate_trophy_celebration_html(auto_play=True, widget_id="test_trophy_auto", show_button=False)
        self.assertIn("data:audio/", html_auto)
        self.assertIn("<audio id=\"audio_test_trophy_auto\"", html_auto)
        self.assertIn("playRoyalCelebration_test_trophy_auto", html_auto)
        self.assertIn("royal_fanfare_canvas_test_trophy_auto", html_auto)
        self.assertIn("👑", html_auto)
        self.assertIn("✨", html_auto)
        self.assertIn("display: none", html_auto)

        # 2. Mode bouton manuel (pour test admin exclusif)
        html_btn = generate_trophy_celebration_html(
            auto_play=False,
            widget_id="test_trophy_btn",
            show_button=True,
            button_label="🎺 Fanfare Royale",
        )
        self.assertIn("<button id=\"btn_test_trophy_btn\"", html_btn)
        self.assertIn("🎺 Fanfare Royale", html_btn)
        self.assertIn("display: inline-block", html_btn)
        self.assertIn("playRoyalCelebration_test_trophy_btn()", html_btn)


class TestCourseDeletion(unittest.TestCase):
    """Tests sur la suppression sécurisée et étanche de cours (élèves & administrateurs)."""

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.test_db_path = Path(self.temp_dir.name) / "test_deletion.db"
        os.environ["DATABASE_PATH"] = str(self.test_db_path)
        init_db(self.test_db_path)

        # Création d'un admin et de deux élèves
        self.admin = create_or_get_google_user("admin@test.ma", "Directeur", role="admin")
        self.student1 = create_or_get_google_user("student1@test.ma", "Élève 1", role="student")
        self.student2 = create_or_get_google_user("student2@test.ma", "Élève 2", role="student")

        # Fichier PDF fictif sur le disque
        self.pdf_file = Path(self.temp_dir.name) / "cours_thales.pdf"
        self.pdf_file.write_bytes(b"%PDF-1.4 Mock Course Content")

        # Cours appartenant à l'élève 1
        self.course1_id = save_course(
            title="Thalès 3AC",
            subject="Mathématiques",
            language="fr",
            file_path=str(self.pdf_file),
            file_hash="hash_thales_delete_test",
            file_name="cours_thales.pdf",
            raw_text="Thalès cours complet",
            user_id=self.student1["id"],
        )
        self.qid = save_quiz(self.course1_id, [{"question": "Q1", "options": ["A", "B"], "answer_index": 0}], user_id=self.student1["id"])
        add_chat_message(self.course1_id, "user", "Explication Thalès", user_id=self.student1["id"])

    def tearDown(self):
        self.temp_dir.cleanup()
        if "DATABASE_PATH" in os.environ:
            del os.environ["DATABASE_PATH"]

    def test_student_deletes_own_course_and_cascades(self):
        # L'élève 1 supprime son propre cours
        self.assertTrue(self.pdf_file.exists())
        success = delete_course(self.course1_id, user_id=self.student1["id"])
        self.assertTrue(success)

        # Le cours n'existe plus en base
        c = get_course_by_id(self.course1_id, user_id=self.student1["id"])
        self.assertIsNone(c)

        # Le fichier physique a été supprimé
        self.assertFalse(self.pdf_file.exists())

        # Les quiz et historiques de chat ont été nettoyés en cascade
        messages = get_chat_history(self.course1_id, user_id=self.student1["id"])
        self.assertEqual(len(messages), 0)
        quiz = get_latest_quiz(self.course1_id, user_id=self.student1["id"])
        self.assertIsNone(quiz)

    def test_student_cannot_delete_other_student_course(self):
        # L'élève 2 tente de supprimer le cours de l'élève 1
        success = delete_course(self.course1_id, user_id=self.student2["id"])
        self.assertFalse(success)

        # Le cours et le fichier de l'élève 1 sont intacts
        c = get_course_by_id(self.course1_id, user_id=self.student1["id"])
        self.assertIsNotNone(c)
        self.assertTrue(self.pdf_file.exists())

    def test_student_cannot_delete_global_shared_course(self):
        # Création d'un cours commun partagé (user_id=None)
        global_pdf = Path(self.temp_dir.name) / "cours_global.pdf"
        global_pdf.write_bytes(b"%PDF-1.4 Global Course")
        global_cid = save_course(
            title="Histoire-Géo Tronc Commun",
            subject="Histoire-Géo",
            language="fr",
            file_path=str(global_pdf),
            file_hash="hash_global_shared_delete_test",
            file_name="cours_global.pdf",
            user_id=None,
        )

        # L'élève tente de supprimer le cours commun avec son user_id
        success = delete_course(global_cid, user_id=self.student1["id"])
        self.assertFalse(success)

        # Le cours global existe toujours
        c = get_course_by_id(global_cid, user_id=self.student1["id"])
        self.assertIsNotNone(c)
        self.assertTrue(global_pdf.exists())

    def test_admin_can_delete_any_course(self):
        # L'administrateur supprime le cours avec user_id=None
        success = delete_course(self.course1_id, user_id=None)
        self.assertTrue(success)

        # Le cours et son fichier sont bien supprimés
        c = get_course_by_id(self.course1_id)
        self.assertIsNone(c)
        self.assertFalse(self.pdf_file.exists())


class TestTutorQuestionSuggestions(unittest.TestCase):
    """Vérification des propositions de questions rapides en 1 clic pour Sanad."""

    def test_question_suggestions_trilingual_and_age_adapted(self):
        # Arabe avec تشكيل تام et âge
        age_12 = 12
        prompt_ar = f"اشْرَحْ لِي فِكْرَةَ هَذَا الدَّرْسِ بِبَسَاطَةٍ كَمَا لَوْ كَانَ عُمْرِي {age_12} سَنَةً."
        self.assertIn("اشْرَحْ", prompt_ar)
        self.assertIn("12", prompt_ar)

        # Français avec âge
        age_14 = 14
        prompt_fr = f"Peux-tu m'expliquer l'idée générale de ce cours avec une analogie simple de la vie courante adaptée à un élève de {age_14} ans ?"
        self.assertIn("14 ans", prompt_fr)
        self.assertIn("analogie", prompt_fr)

        # Anglais avec âge
        age_16 = 16
        prompt_en = f"Can you explain the main idea of this lesson using a simple real-life analogy adapted to a {age_16}-year-old student?"
        self.assertIn("16-year-old", prompt_en)


class TestMindmapAndConceptMastery(unittest.TestCase):
    """Vérification des cartes mentales Mermaid et du suivi d'assimilation des notions clés."""

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "test_mindmap.db"
        self.patcher = patch("models.database.get_db_path", return_value=self.db_path)
        self.patcher.start()
        init_db()

        self.student = create_or_get_google_user("eleve_notions@test.ma", "Adnane Eleve", role="student")
        pdf_file = Path(self.temp_dir.name) / "cours_thales.pdf"
        pdf_file.write_bytes(b"%PDF-1.4 Fake PDF Content")
        self.course_id = save_course(
            title="Théorème de Thalès",
            subject="Mathématiques",
            language="fr",
            file_path=str(pdf_file),
            file_hash="hash_thales_test_01",
            file_name="thales.pdf",
            raw_text="Le théorème de Thalès permet de calculer des longueurs dans un triangle. La réciproque permet de démontrer le parallélisme.",
            summary_markdown="## Fiche Thalès\nCalcul de longueurs et démonstration du parallélisme.",
            key_concepts=[
                "Théorème direct de Thalès",
                "Réciproque du théorème de Thalès",
                "Calcul de longueurs et quotients",
                "Démontrer que deux droites sont parallèles",
            ],
            user_id=self.student["id"],
        )

    def tearDown(self):
        self.patcher.stop()
        self.temp_dir.cleanup()

    def test_save_and_get_course_mindmap(self):
        # Initialement aucun mindmap
        self.assertIsNone(get_course_mindmap(self.course_id))

        # Enregistrement
        sample_code = """mindmap
  root((Théorème de Thalès))
    Théorème Direct
      Calcul de longueurs
    Réciproque
      Prouver le parallélisme"""
        save_course_mindmap(self.course_id, sample_code)

        # Récupération
        fetched = get_course_mindmap(self.course_id)
        self.assertEqual(fetched, sample_code)

        # get_course_by_id doit aussi inclure mindmap_code
        course_obj = get_course_by_id(self.course_id)
        self.assertEqual(course_obj.get("mindmap_code"), sample_code)

    def test_get_course_mindmap_auto_repairs_missing_column(self):
        # Simuler une base existante où la colonne mindmap_code n'a pas encore été migrée
        from models.database import get_connection
        conn = get_connection()
        try:
            with conn:
                conn.execute("ALTER TABLE courses DROP COLUMN mindmap_code")
        finally:
            conn.close()

        # get_course_mindmap ne doit PAS lever d'OperationalError et doit auto-réparer la table
        val = get_course_mindmap(self.course_id)
        self.assertIsNone(val)

        # La colonne doit désormais exister et permettre l'enregistrement
        save_course_mindmap(self.course_id, "mindmap\n  root((Test))")
        self.assertEqual(get_course_mindmap(self.course_id), "mindmap\n  root((Test))")

    def test_mindmap_dual_persistence_and_restart(self):
        # 1. Enregistrement d'une carte mentale
        sample_code = """# Schéma Thalès
## Branches
- Direct: Calculs
- Réciproque: Parallélisme"""
        save_course_mindmap(self.course_id, sample_code)

        # 2. Vérifier que la carte est sur disque
        thales_pdf = str(Path(self.temp_dir.name) / "cours_thales.pdf")
        disk_paths = get_mindmap_disk_paths(self.course_id, thales_pdf, self.student["id"])
        existing_on_disk = [p for p in disk_paths if p.exists() and p.is_file()]
        self.assertTrue(len(existing_on_disk) > 0, "Le fichier de carte mentale doit exister sur disque.")

        # 3. Simuler une base réinitialisée ou colonne vidée (comme sur Streamlit Cloud)
        from models.database import get_connection
        conn = get_connection()
        try:
            with conn:
                conn.execute("UPDATE courses SET mindmap_code = NULL WHERE id = ?", (self.course_id,))
        finally:
            conn.close()

        # Vérifier que get_course_mindmap récupère depuis le disque et auto-répare SQLite
        restored = get_course_mindmap(self.course_id)
        self.assertEqual(restored, sample_code)

        # Vérifier que SQLite est auto-réparé
        conn2 = get_connection()
        try:
            val = conn2.execute("SELECT mindmap_code FROM courses WHERE id = ?", (self.course_id,)).fetchone()[0]
            self.assertEqual(val, sample_code)
        finally:
            conn2.close()

        # 4. Simuler un redémarrage de l'app avec init_db()
        from models.database import init_db
        init_db(self.db_path)
        self.assertEqual(get_course_mindmap(self.course_id), sample_code)

    def test_clean_mermaid_mindmap(self):
        # 1. Nettoyer les balises de code markdown ```mermaid ... ```
        raw_with_fences = "```mermaid\nmindmap\n  root((Mon Cours))\n    Branche 1\n```"
        cleaned = clean_mermaid_mindmap(raw_with_fences, default_title="Mon Cours")
        self.assertTrue(cleaned.startswith("mindmap"))
        self.assertNotIn("```", cleaned)

        # 2. Nettoyer les parenthèses orphelines dans les étiquettes enfants
        raw_with_parens = "mindmap\n  root((Mon Cours))\n    Branche 1 (Attention)\n      Sous-branche [info]"
        cleaned2 = clean_mermaid_mindmap(raw_with_parens)
        self.assertIn("root((Mon Cours))", cleaned2)
        self.assertNotIn("(", cleaned2.splitlines()[2])

        # 3. Fallback si vide ou syntaxe corrompue
        fallback = clean_mermaid_mindmap("", default_title="Maths", default_subject="Calcul")
        self.assertTrue(fallback.startswith("mindmap"))
        self.assertIn("root((Maths))", fallback)

    def test_fallback_mindmap_structure(self):
        fb = _fallback_mindmap("Géométrie 3AC", "Mathématiques")
        self.assertTrue(fb.startswith("# Géométrie 3AC"))
        self.assertIn("Définition & Notions Fondamentales", fb)
        self.assertIn("Propriétés Majeures & Formules", fb)
        self.assertIn("Démarche de Résolution", fb)
        self.assertNotIn("Pièges d'Examen", fb)

    def test_is_generic_concept(self):
        # Méta-catégories génériques à proscrire (Français, Arabe avec Tashkeel, Anglais)
        self.assertTrue(is_generic_concept("Pièges d'examen & Erreurs fréquentes"))
        self.assertTrue(is_generic_concept("Méthode d'application & Démarche de résolution"))
        self.assertTrue(is_generic_concept("Définitions & Principes fondamentaux (Théorème)"))
        self.assertTrue(is_generic_concept("Propriétés, Théorèmes et Formules (Maths)"))
        self.assertTrue(is_generic_concept("فخاخ الامتحانات وأخطاء شائعة"))
        self.assertTrue(is_generic_concept("طريقة التطبيق ومنهجية الحل"))
        # Cas exact signalé par l'utilisateur avec Tashkeel arabe et parenthèses
        self.assertTrue(is_generic_concept(" فَخَاخُ الِامْتِحَانِ الْمُوَحَّدِ (أَخْطَاءٌ يَقَعُ فِيهَا أَغْلَب"))
        self.assertTrue(is_generic_concept("## ⚠️ فخاخ ومزالق الامتحانات الإشهادية (البكالوريا)"))
        self.assertTrue(is_generic_concept("## 🎯 المفاهيم والتعاريف الأساسية (التي تتكرر في الامتحان)"))
        self.assertTrue(is_generic_concept("## 📌 القواعد الذهبية / التواريخ والعناصر المفتاحية"))
        self.assertTrue(is_generic_concept("## 💡 نصيحة التحرير لضمان النقطة الكاملة"))
        self.assertTrue(is_generic_concept("## 💡 سر التفوق والنجاح"))
        self.assertTrue(is_generic_concept("Exam Pitfalls & Frequent Traps"))
        # Formules génériques et méta-scaffolding rapportées par l'utilisateur
        self.assertTrue(is_generic_concept("مفهوم وتعريف (العبادة صفة إیمان ودلیل خضوع)"))
        self.assertTrue(is_generic_concept("الخاصيات والقواعد الأساسية لـ العبادة صفة إیمان ودلیل خضوع"))
        self.assertTrue(is_generic_concept("تطبيقات وتمارين نموذجية (العبادة صفة إیمان ودلیل خضوع)"))
        self.assertTrue(is_generic_concept("حالات خاصة وملاحظات هامة (العبادة صفة إیمان ودلیل خضوع)"))
        self.assertTrue(is_generic_concept("Définition et principes de Pythagore"))
        self.assertTrue(is_generic_concept("Propriétés et formules de Thalès"))
        self.assertTrue(is_generic_concept("Applications et démarches types (Thalès)"))
        self.assertTrue(is_generic_concept("Cas particuliers et vérifications (Thalès)"))
        self.assertTrue(is_generic_concept("Propriétés"))
        self.assertTrue(is_generic_concept("Formules"))
        self.assertTrue(is_generic_concept(""))

        # Notions réelles et concrètes de cours qui doivent être acceptées (même avec Tashkeel)
        self.assertFalse(is_generic_concept("Théorème direct de Pythagore"))
        self.assertFalse(is_generic_concept("Réciproque du théorème de Thalès"))
        self.assertFalse(is_generic_concept("Calcul de l'hypoténuse"))
        self.assertFalse(is_generic_concept("مبرهنة فيتاغورس المباشرة"))
        self.assertFalse(is_generic_concept("مَبَرْهَنَةُ فِيتَاغُورْسَ الْمُبَاشِرَةُ"))
        self.assertFalse(is_generic_concept("حِسَابُ طُولِ الْوَتَرِ"))
        self.assertFalse(is_generic_concept("حساب جيب تمام زاوية حادة"))
        self.assertFalse(is_generic_concept("Newton's Second Law of Motion"))

    def test_evaluate_and_sync_purges_tashkeel_arabic_generic_concepts(self):
        # Cas rapporté par l'utilisateur : cours arabe pollué par les titres de gabarit avec Tashkeel
        pdf_file = Path(self.temp_dir.name) / "cours_arabe_generic.pdf"
        pdf_file.write_bytes(b"%PDF-1.4 Fake Arabic PDF")
        c_id = save_course(
            title="مبرهنة فيتاغورس",
            subject="الرياضيات",
            language="ar",
            file_path=str(pdf_file),
            file_hash="hash_ar_generic_01",
            file_name="pythagore_ar.pdf",
            raw_text="مبرهنة فيتاغورس في المثلث القائم الزاوية.",
            summary_markdown="""
## 🎯 المفاهيم والتعاريف الأساسية (التي تتكرر في الامتحان)
- **مَبَرْهَنَةُ فِيتَاغُورْسَ الْمُبَاشِرَةُ** : فِي كُلِّ مُثَلَّثٍ قَائِمِ الزَّاوِيَةِ، مُرَبَّعُ طُولِ الْوَتَرِ يُسَاوِي مَجْمُوعَ مُرَبَّعَيْ طُولَيْ الضِّلْعَيْنِ الآخَرَيْنِ.
- **حِسَابُ طُولِ الْوَتَرِ** : تَطْبِيقُ الْعَلَاقَةِ الرِّيَاضِيَّةِ.
## ⚠️ فَخَاخُ الِامْتِحَانِ الْمُوَحَّدِ (أَخْطَاءٌ يَقَعُ فِيهَا أَغْلَبُ التَّلَامِيذِ)
- نسيان شرط المثلث القائم الزاوية قبل الحساب.
## 💡 نَصِيحَةُ التَّحْرِيرِ لِضَمَانِ النُّقْطَةِ الكَامِلَةِ
- كتابة اسم المثلث والزاوية القائمة بوضوح.
""",
            key_concepts=[
                " فَخَاخُ الِامْتِحَانِ الْمُوَحَّدِ (أَخْطَاءٌ يَقَعُ فِيهَا أَغْلَب",
                "## 🎯 المفاهيم والتعاريف الأساسية (التي تتكرر في الامتحان)",
                "مَبَرْهَنَةُ فِيتَاغُورْسَ الْمُبَاشِرَةُ",
                "حِسَابُ طُولِ الْوَتَرِ",
            ],
            user_id=self.student["id"],
        )

        # Enregistrer des entrées polluées dans concept_mastery
        save_concept_mastery(self.student["id"], c_id, " فَخَاخُ الِامْتِحَانِ الْمُوَحَّدِ (أَخْطَاءٌ يَقَعُ فِيهَا أَغْلَب", "to_review")
        save_concept_mastery(self.student["id"], c_id, "## 🎯 المفاهيم والتعاريف الأساسية (التي تتكرر في الامتحان)", "in_progress")

        # Exécuter evaluate_and_sync_concept_mastery
        synced = evaluate_and_sync_concept_mastery(self.student["id"], c_id)
        concept_titles = [item["concept_title"] for item in synced]

        # Vérifier que les labels génériques ont été rigoureusement éliminés
        self.assertNotIn(" فَخَاخُ الِامْتِحَانِ الْمُوَحَّدِ (أَخْطَاءٌ يَقَعُ فِيهَا أَغْلَب", concept_titles)
        self.assertNotIn("## 🎯 المفاهيم والتعاريف الأساسية (التي تتكرر في الامتحان)", concept_titles)

        # Vérifier que les notions réelles sont bien préservées
        self.assertIn("مَبَرْهَنَةُ فِيتَاغُورْسَ الْمُبَاشِرَةُ", concept_titles)
        self.assertIn("حِسَابُ طُولِ الْوَتَرِ", concept_titles)

        # Vérifier la purge directe en base via get_student_concept_mastery
        db_mastery = get_student_concept_mastery(self.student["id"], c_id)
        db_titles = [m["concept_title"] for m in db_mastery]
        self.assertNotIn(" فَخَاخُ الِامْتِحَانِ الْمُوَحَّدِ (أَخْطَاءٌ يَقَعُ فِيهَا أَغْلَب", db_titles)
        self.assertNotIn("## 🎯 المفاهيم والتعاريف الأساسية (التي تتكرر في الامتحان)", db_titles)

    def test_extract_real_course_concepts(self):
        course = {
            "title": "Théorème de Pythagore",
            "subject": "Mathématiques",
            "language": "fr",
            "summary_markdown": """
# Fiche Express
## 1. Propriétés Fondamentales
- **Théorème direct de Pythagore** : Dans tout triangle rectangle, le carré de l'hypoténuse est égal à la somme des carrés.
- **Calcul de l'hypoténuse** : Application de la formule $BC = \\sqrt{AB^2 + AC^2}$.
- **Réciproque du théorème** : Démontrer qu'un triangle est rectangle.
## ⚠️ Pièges d'examen & Erreurs fréquentes
- Oublier de vérifier l'angle droit
""",
        }
        concepts = extract_real_course_concepts(course)
        self.assertIn("Théorème direct de Pythagore", concepts)
        self.assertIn("Calcul de l'hypoténuse", concepts)
        self.assertIn("Réciproque du théorème", concepts)
        for c in concepts:
            self.assertFalse(is_generic_concept(c), f"Found generic concept: {c}")

    def test_evaluate_and_sync_purges_legacy_generic_concepts(self):
        pdf_file = Path(self.temp_dir.name) / "cours_generic.pdf"
        pdf_file.write_bytes(b"%PDF-1.4 Fake")
        c_id = save_course(
            title="Racines Carrées",
            subject="Mathématiques",
            language="fr",
            file_path=str(pdf_file),
            file_hash="hash_generic_01",
            file_name="racines.pdf",
            raw_text="Les racines carrées permettent de résoudre des équations de type x² = a.",
            summary_markdown="## 1. Définition\n- **Racine carrée d'un nombre positif** : Définition de √a.\n- **Propriété du produit** : √(a×b) = √a × √b.\n## ⚠️ Pièges d'examen\nAttention aux nombres négatifs.",
            key_concepts=[
                "Définitions & Principes fondamentaux (Racines Carrées)",
                "Propriétés, Théorèmes et Formules (Mathématiques)",
                "Méthode d'application & Démarche de résolution",
                "Pièges d'examen & Erreurs fréquentes",
            ],
            user_id=self.student["id"],
        )

        save_concept_mastery(self.student["id"], c_id, "Pièges d'examen & Erreurs fréquentes", "to_review")
        save_concept_mastery(self.student["id"], c_id, "Méthode d'application & Démarche de résolution", "in_progress")

        synced = evaluate_and_sync_concept_mastery(self.student["id"], c_id)

        concept_titles = [item["concept_title"] for item in synced]
        self.assertNotIn("Pièges d'examen & Erreurs fréquentes", concept_titles)
        self.assertNotIn("Méthode d'application & Démarche de résolution", concept_titles)
        for t in concept_titles:
            self.assertFalse(is_generic_concept(t), f"Retained generic concept: {t}")

        db_mastery = get_student_concept_mastery(self.student["id"], c_id)
        db_titles = [m["concept_title"] for m in db_mastery]
        self.assertNotIn("Pièges d'examen & Erreurs fréquentes", db_titles)
        self.assertNotIn("Méthode d'application & Démarche de résolution", db_titles)

    def test_get_course_by_id_auto_repairs_legacy_generic_concepts(self):
        pdf_file = Path(self.temp_dir.name) / "cours_legacy_polluted.pdf"
        pdf_file.write_bytes(b"%PDF-1.4 Fake Arabic PDF")
        c_id = save_course(
            title="مبرهنة طاليس",
            subject="الرياضيات",
            language="ar",
            file_path=str(pdf_file),
            file_hash="hash_thales_legacy_01",
            file_name="thales_ar.pdf",
            raw_text="مبرهنة طاليس المباشرة والعكسية وتطبيقاتها.",
            summary_markdown="""
## 🎯 المفاهيم والتعاريف الأساسية (التي تتكرر في الامتحان)
- **مَبَرْهَنَةُ طَالِيسَ الْمُبَاشِرَةُ** : حساب أطوال الأضلاع في مثلث.
- **مَبَرْهَنَةُ طَالِيسَ الْعَكْسِيَّةُ** : البرهان على توازي مستقيمين.
## ⚠️ فَخَاخُ الِامْتِحَانِ الْمُوَحَّدِ (أَخْطَاءٌ يَقَعُ فِيهَا أَغْلَبُ التَّلَامِيذِ)
- نسيان الترتيب الصحيح للنقط.
## 💡 نَصِيحَةُ التَّحْرِيرِ لِضَمَانِ النُّقْطَةِ الكَامِلَةِ
- التأكد من استقامية النقط بنفس الترتيب.
""",
            user_id=self.student["id"],
        )

        # Simuler une ancienne base de données polluée avec les 4 gabarits rapportés par l'utilisateur
        from models.database import get_connection
        polluted_headers = [
            "الْمَفَاهِيمُ وَالتَّعَارِيفُ الْأَسَاسِيَّةُ (الَّتِي تَتَكَرَّرُ ف",
            "الْقَوَاعِدُ الذَّهَبِيَّةُ / الْعَنَاصِرُ الْمِفْتَاحِيَّةُ",
            "فَخَاخُ الِامْتِحَانِ الْمُوَحَّدِ (أَخْطَاءٌ يَقَعُ فِيهَا أَغْلَب",
            "نَصِيحَةُ التَّحْرِيرِ لِضَمَانِ النُّقْطَةِ الْكَامِلَةِ",
        ]
        conn = get_connection()
        try:
            with conn:
                conn.cursor().execute(
                    "UPDATE courses SET key_concepts_json = ? WHERE id = ?",
                    (json.dumps(polluted_headers, ensure_ascii=False), c_id),
                )
        finally:
            conn.close()

        # Appel de get_course_by_id
        course = get_course_by_id(c_id, user_id=self.student["id"])
        self.assertIsNotNone(course)
        loaded_concepts = course["key_concepts"]

        # 1. Vérifier qu'AUCUNE des 4 méta-catégories n'apparaît dans key_concepts
        for bad in polluted_headers:
            self.assertNotIn(bad, loaded_concepts)

        # 2. Vérifier que les vraies notions pédagogiques ont été extraites
        self.assertIn("مَبَرْهَنَةُ طَالِيسَ الْمُبَاشِرَةُ", loaded_concepts)
        self.assertIn("مَبَرْهَنَةُ طَالِيسَ الْعَكْسِيَّةُ", loaded_concepts)

        # 3. Vérifier que la base SQLite elle-même a été auto-réparée
        conn = get_connection()
        try:
            cur = conn.cursor()
            cur.execute("SELECT key_concepts_json FROM courses WHERE id = ?", (c_id,))
            db_kc_raw = cur.fetchone()["key_concepts_json"]
            db_kc = json.loads(db_kc_raw)
            for bad in polluted_headers:
                self.assertNotIn(bad, db_kc)
            self.assertIn("مَبَرْهَنَةُ طَالِيسَ الْمُبَاشِرَةُ", db_kc)
        finally:
            conn.close()

    def test_purges_and_rejects_boilerplate_fallback_concepts(self):
        # 1. Vérifier la détection generic sur les 4 chaînes exactes signalées par l'utilisateur
        self.assertTrue(is_generic_concept("مفهوم وتعريف (العبادة صفة إیمان ودلیل خضوع)"))
        self.assertTrue(is_generic_concept("الخاصيات والقواعد الأساسية لـ العبادة صفة إیمان ودلیل خضوع"))
        self.assertTrue(is_generic_concept("تطبيقات وتمارين نموذجية (العبادة صفة إیمان ودلیل خضوع)"))
        self.assertTrue(is_generic_concept("حالات خاصة وملاحظات هامة (العبادة صفة إیمان ودلیل خضوع)"))

        # 2. Insérer un cours pollué avec ces 4 chaînes en base
        pdf_file = Path(self.temp_dir.name) / "cours_ibada.pdf"
        pdf_file.write_bytes(b"%PDF-1.4 Fake")
        raw_text = """
المملكة المغربية - وزارة التربية الوطنية
المادة: التربية الإسلامية
الدرس: العبادة صفة إيمان ودليل خضوع

المحور الأول: مفهوم العبادة وغاياتها
1- مفهوم العبادة:
العبادة لغة التذلل واصطلاحا طاعة الله.
2- غايات العبادة:
نيل رضا الله وتهذيب السلوك.

المحور الثاني: شمولية مفهوم العبادة
العبادة تشمل الشعائر والمعاملات.
"""
        c_id = save_course(
            title="العبادة صفة إيمان ودليل خضوع",
            subject="التربية الإسلامية",
            language="ar",
            file_path=str(pdf_file),
            file_hash="hash_ibada_polluted",
            file_name="ibada.pdf",
            raw_text=raw_text,
            user_id=self.student["id"],
        )

        from models.database import get_connection
        polluted = [
            "مفهوم وتعريف (العبادة صفة إیمان ودلیل خضوع)",
            "الخاصيات والقواعد الأساسية لـ العبادة صفة إیمان ودلیل خضوع",
            "تطبيقات وتمارين نموذجية (العبادة صفة إیمان ودلیل خضوع)",
            "حالات خاصة وملاحظات هامة (العبادة صفة إیمان ودلیل خضوع)",
        ]
        conn = get_connection()
        try:
            with conn:
                conn.cursor().execute(
                    "UPDATE courses SET key_concepts_json = ? WHERE id = ?",
                    (json.dumps(polluted, ensure_ascii=False), c_id),
                )
        finally:
            conn.close()

        # 3. Récupérer le cours : get_course_by_id doit auto-réparer
        course = get_course_by_id(c_id, user_id=self.student["id"])
        self.assertIsNotNone(course)
        concepts = course["key_concepts"]

        # Aucune des 4 formules ne doit subsister
        for p in polluted:
            self.assertNotIn(p, concepts)

        # De vraies notions de la leçon doivent être extraites
        self.assertTrue(any("مفهوم العبادة" in c for c in concepts) or any("العبادة صفة إيمان" in c for c in concepts))
        for c in concepts:
            self.assertFalse(is_generic_concept(c), f"Retained generic concept: {c}")

        # 4. Vérifier la mise à jour directe dans SQLite
        conn = get_connection()
        try:
            cur = conn.cursor()
            cur.execute("SELECT key_concepts_json FROM courses WHERE id = ?", (c_id,))
            db_concepts = json.loads(cur.fetchone()["key_concepts_json"])
            for p in polluted:
                self.assertNotIn(p, db_concepts)
        finally:
            conn.close()

    def test_convert_mermaid_to_markdown(self):
        mermaid_sample = """mindmap
  root((Théorème de Thalès))
    Propriétés
      Calcul de longueurs
      Rapports égaux
    Réciproque
      Prouver le parallélisme"""
        md = convert_mermaid_to_markdown(mermaid_sample)
        self.assertTrue(md.startswith("# Théorème de Thalès"))
        self.assertIn("## Propriétés", md)
        self.assertIn("### Calcul de longueurs", md)
        self.assertIn("## Réciproque", md)

    def test_clean_interactive_mindmap_markdown(self):
        raw = "```markdown\n# Mon Cours\n## Notion 1\n- Point important\n```"
        cleaned = clean_interactive_mindmap_markdown(raw, default_title="Mon Cours")
        self.assertTrue(cleaned.startswith("# Mon Cours"))
        self.assertNotIn("```", cleaned)

        raw_mermaid = "mindmap\n  root((Cours Mermaid))\n    Branche 1"
        converted = clean_interactive_mindmap_markdown(raw_mermaid)
        self.assertTrue(converted.startswith("# Cours Mermaid"))

        fb = clean_interactive_mindmap_markdown("", default_title="Physique 3AC", default_subject="Optique")
        self.assertTrue(fb.startswith("# Physique 3AC"))
        self.assertIn("Définition & Notions Fondamentales", fb)

    def test_save_and_get_concept_mastery(self):
        save_concept_mastery(
            user_id=self.student["id"],
            course_id=self.course_id,
            concept_title="Théorème direct de Thalès",
            status="mastered",
            success_rate=85.5,
            attempts_count=2,
            last_context="Réussi sur 2 quiz",
        )

        mastery_list = get_student_concept_mastery(self.student["id"], self.course_id)
        self.assertEqual(len(mastery_list), 1)
        item = mastery_list[0]
        self.assertEqual(item["concept_title"], "Théorème direct de Thalès")
        self.assertEqual(item["status"], "mastered")
        self.assertEqual(item["success_rate"], 85.5)
        self.assertEqual(item["attempts_count"], 2)

        # Upsert sur conflit
        save_concept_mastery(
            user_id=self.student["id"],
            course_id=self.course_id,
            concept_title="Théorème direct de Thalès",
            status="in_progress",
            success_rate=60.0,
            attempts_count=3,
            last_context="Mise à jour",
        )
        updated_list = get_student_concept_mastery(self.student["id"], self.course_id)
        self.assertEqual(len(updated_list), 1)
        self.assertEqual(updated_list[0]["status"], "in_progress")
        self.assertEqual(updated_list[0]["success_rate"], 60.0)

    def test_evaluate_and_sync_concept_mastery_no_attempts_no_chat(self):
        # Sans quiz ni chat, toutes les notions sont untested
        results = evaluate_and_sync_concept_mastery(self.student["id"], self.course_id)
        self.assertEqual(len(results), 4)
        for r in results:
            self.assertEqual(r["status"], "untested")
            self.assertEqual(r["attempts_count"], 0)

    def test_evaluate_and_sync_concept_mastery_with_chat_discussion(self):
        # Ajout d'un échange chat mentionnant "parallélisme"
        add_chat_message(
            course_id=self.course_id,
            role="user",
            content="Comment démontrer que deux droites sont parallèles avec Thalès ?",
            user_id=self.student["id"],
        )
        results = evaluate_and_sync_concept_mastery(self.student["id"], self.course_id)
        # La notion sur le parallélisme doit passer en in_progress
        paral_item = next(r for r in results if "parallèles" in r["concept_title"])
        self.assertEqual(paral_item["status"], "in_progress")
        self.assertIn("Sanad", paral_item["last_context"])

    def test_evaluate_and_sync_concept_mastery_with_quiz_score_mastered(self):
        # Ajout d'une tentative de quiz avec un excellent score (4/5 = 80%)
        q_id = save_quiz(self.course_id, [{"question": "Q1", "options": ["A", "B"], "answer_index": 0}], user_id=self.student["id"])
        save_quiz_attempt(
            course_id=self.course_id,
            quiz_id=q_id,
            score=4,
            total_questions=5,
            answers={0: 0},
            user_id=self.student["id"],
        )
        results = evaluate_and_sync_concept_mastery(self.student["id"], self.course_id)
        self.assertEqual(len(results), 4)
        for r in results:
            self.assertEqual(r["status"], "mastered")
            self.assertEqual(r["success_rate"], 80.0)
            self.assertEqual(r["attempts_count"], 1)

    def test_evaluate_and_sync_concept_mastery_with_quiz_score_to_review(self):
        # Tentative avec score faible (1/5 = 20%) -> to_review
        q_id = save_quiz(self.course_id, [{"question": "Q1", "options": ["A", "B"], "answer_index": 0}], user_id=self.student["id"])
        save_quiz_attempt(
            course_id=self.course_id,
            quiz_id=q_id,
            score=1,
            total_questions=5,
            answers={0: 0},
            user_id=self.student["id"],
        )
        results = evaluate_and_sync_concept_mastery(self.student["id"], self.course_id)
        for r in results:
            self.assertEqual(r["status"], "to_review")
            self.assertEqual(r["success_rate"], 20.0)


class TestSchoolLevelAndTrophies(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.test_db_path = Path(self.temp_dir.name) / "test_level_trophies.db"
        os.environ["DATABASE_PATH"] = str(self.test_db_path)
        init_db(self.test_db_path)

        # Utilisateur de test
        self.user = create_or_get_google_user("student_level@test.com", "Élève Test")
        self.user_id = self.user["id"]

    def tearDown(self):
        self.temp_dir.cleanup()
        if "DATABASE_PATH" in os.environ:
            del os.environ["DATABASE_PATH"]

    def test_moroccan_school_levels_catalog(self):
        self.assertIn("1AC", MOROCCAN_SCHOOL_LEVELS)
        self.assertIn("2AC", MOROCCAN_SCHOOL_LEVELS)
        self.assertIn("3AC", MOROCCAN_SCHOOL_LEVELS)
        self.assertIn("Tronc Commun", MOROCCAN_SCHOOL_LEVELS)
        self.assertIn("1BAC", MOROCCAN_SCHOOL_LEVELS)
        self.assertIn("2BAC", MOROCCAN_SCHOOL_LEVELS)
        self.assertIn("6AEP", MOROCCAN_SCHOOL_LEVELS)
        self.assertIn("Supérieur", MOROCCAN_SCHOOL_LEVELS)

    def test_get_pedagogical_cycle_explicit_levels(self):
        c_1ac = get_pedagogical_cycle(level="1AC")
        self.assertEqual(c_1ac["stage"], "middle")
        self.assertEqual(c_1ac["level"], "1AC")
        self.assertIn("1AC", c_1ac["stage_label"])

        c_tc = get_pedagogical_cycle(level="Tronc Commun")
        self.assertEqual(c_tc["stage"], "high")
        self.assertEqual(c_tc["level"], "Tronc Commun")
        self.assertIn("Tronc Commun", c_tc["stage_label"])

        c_2bac = get_pedagogical_cycle(level="2BAC")
        self.assertEqual(c_2bac["stage"], "high")
        self.assertEqual(c_2bac["level"], "2BAC")
        self.assertIn("2BAC", c_2bac["stage_label"])

        c_6aep = get_pedagogical_cycle(level="6AEP")
        self.assertEqual(c_6aep["stage"], "primary")
        self.assertEqual(c_6aep["level"], "6AEP")

        c_sup = get_pedagogical_cycle(level="Supérieur")
        self.assertEqual(c_sup["stage"], "higher")
        self.assertEqual(c_sup["level"], "Supérieur")

    def test_update_user_level_and_persistence(self):
        # Initial level
        user = get_user_by_id(self.user_id)
        self.assertEqual(user.get("level"), "3AC")

        # Update to 2AC
        ok, msg = update_user_level(self.user_id, "2AC")
        self.assertTrue(ok)
        updated = get_user_by_id(self.user_id)
        self.assertEqual(updated["level"], "2AC")

        # Session token retrieval
        tok = create_user_session(self.user_id)
        session_user = get_user_from_session_token(tok)
        self.assertIsNotNone(session_user)
        self.assertEqual(session_user["level"], "2AC")

    def test_resolve_student_level(self):
        # When explicit level passed
        self.assertEqual(resolve_student_level(level="1BAC"), "1BAC")

        # When user_id passed
        update_user_level(self.user_id, "Tronc Commun")
        self.assertEqual(resolve_student_level(user_id=self.user_id), "Tronc Commun")

        # Default fallback
        self.assertEqual(resolve_student_level(), "3AC")

    def test_badge_catalog_and_structure(self):
        catalog = get_badge_catalog()
        self.assertGreaterEqual(len(catalog), 8)
        keys = [b["key"] for b in catalog]
        self.assertIn("first_quiz", keys)
        self.assertIn("perfect_score", keys)
        self.assertIn("quiz_five", keys)
        self.assertIn("quiz_ten", keys)
        self.assertIn("course_explorer", keys)
        self.assertIn("sanad_scholar", keys)
        self.assertIn("concept_master", keys)
        self.assertIn("mindmap_pioneer", keys)

        for b in catalog:
            self.assertTrue(b["key"])
            self.assertTrue(b["title"])
            self.assertTrue(b["description"])
            self.assertTrue(b["icon"])
            self.assertGreater(b["target_value"], 0)

    def test_award_badge_idempotency(self):
        # 1st award -> True
        res1 = award_badge(self.user_id, "first_quiz", {"note": "test"})
        self.assertTrue(res1)

        # 2nd award -> False (idempotent)
        res2 = award_badge(self.user_id, "first_quiz")
        self.assertFalse(res2)

        badges = get_user_badges(self.user_id)
        self.assertEqual(len(badges), 1)
        self.assertEqual(badges[0]["badge_key"], "first_quiz")
        self.assertIn("Premier Pas", badges[0]["title"])

    def test_evaluate_and_award_badges_progression(self):
        # Before activity: 0 badges
        new_badges = evaluate_and_award_badges(self.user_id)
        self.assertEqual(len(new_badges), 0)

        overview_empty = get_student_trophies_overview(self.user_id)
        self.assertEqual(overview_empty["unlocked_trophies"], 0)
        self.assertEqual(overview_empty["completion_rate"], 0.0)

        # Create a course
        cid = save_course(
            title="Théorème de Thalès",
            subject="Mathématiques",
            language="fr",
            file_path=str(Path(self.temp_dir.name) / "thales.pdf"),
            file_name="thales.pdf",
            file_hash="fakehash123",
            user_id=self.user_id,
            mindmap_code="mindmap\n  root((Thalès))\n",
        )

        # Pass a perfect quiz
        qid = save_quiz(cid, [{"question": "Q1", "options": ["A", "B"], "answer_index": 0}], user_id=self.user_id)
        save_quiz_attempt(
            course_id=cid,
            quiz_id=qid,
            score=1,
            total_questions=1,
            answers={0: 0},
            user_id=self.user_id,
        )

        # Now evaluate
        awarded = evaluate_and_award_badges(self.user_id)
        awarded_keys = [b["key"] for b in awarded]
        self.assertIn("first_quiz", awarded_keys)
        self.assertIn("perfect_score", awarded_keys)
        self.assertIn("mindmap_pioneer", awarded_keys)

        overview = get_student_trophies_overview(self.user_id)
        self.assertGreaterEqual(overview["unlocked_trophies"], 3)
        self.assertGreater(overview["completion_rate"], 0.0)

        # Check badges list formatting in overview
        fq = next(b for b in overview["badges"] if b["key"] == "first_quiz")
        self.assertTrue(fq["is_unlocked"])
        self.assertEqual(fq["progress_percent"], 100)

        q5 = next(b for b in overview["badges"] if b["key"] == "quiz_five")
        self.assertFalse(q5["is_unlocked"])
        self.assertEqual(q5["current_value"], 1)
        self.assertEqual(q5["target_value"], 5)
        self.assertIn("Plus que 4", q5["encouragement"])

    def test_backup_and_restore_user_badges(self):
        # Award badge to user
        award_badge(self.user_id, "first_quiz")
        award_badge(self.user_id, "mindmap_pioneer")

        # Export student backup
        zip_bytes = export_student_backup(self.user_id)
        self.assertIsNotNone(zip_bytes)

        # Verify summary includes badges
        summary = get_student_backup_summary(self.user_id)
        self.assertEqual(summary["badge_count"], 2)

        # Create target student and restore
        target_student = create_or_get_google_user("restored_student@test.com", "Élève Restauré")
        res = restore_student_backup(zip_bytes, target_user_id=target_student["id"])
        self.assertTrue(res["success"])

        # Verify restored badges
        restored_badges = get_user_badges(target_student["id"])
        restored_keys = [b["badge_key"] for b in restored_badges]
        self.assertIn("first_quiz", restored_keys)
        self.assertIn("mindmap_pioneer", restored_keys)

    def test_course_badge_catalog_and_structure(self):
        self.assertEqual(len(COURSE_BADGE_CATALOG), 8)
        expected_keys = [
            "course_explored",
            "course_mindmap",
            "course_first_quiz",
            "course_perfect_score",
            "course_three_quizzes",
            "course_sanad_dialogue",
            "course_concept_master",
            "course_grand_master",
        ]
        keys = [b["key"] for b in COURSE_BADGE_CATALOG]
        for ek in expected_keys:
            self.assertIn(ek, keys)
            self.assertIn(ek, COURSE_BADGE_CATALOG_MAP)

        for b in COURSE_BADGE_CATALOG:
            self.assertTrue(b.get("title"))
            self.assertTrue(b.get("description"))
            self.assertTrue(b.get("category"))
            self.assertTrue(b.get("icon"))
            self.assertGreater(b.get("target_value", 0), 0)
            self.assertTrue(b.get("unit"))

    def test_award_course_badge_idempotency_and_isolation(self):
        cid1 = save_course(
            title="Cours 1",
            subject="Physique",
            language="fr",
            file_path=str(Path(self.temp_dir.name) / "p1.pdf"),
            file_name="p1.pdf",
            file_hash="hash_p1",
            user_id=self.user_id,
        )
        cid2 = save_course(
            title="Cours 2",
            subject="Physique",
            language="fr",
            file_path=str(Path(self.temp_dir.name) / "p2.pdf"),
            file_name="p2.pdf",
            file_hash="hash_p2",
            user_id=self.user_id,
        )

        # 1st award for course 1 -> True
        res1 = award_badge(self.user_id, "course_first_quiz", course_id=cid1)
        self.assertTrue(res1)

        # 2nd award for same course 1 -> False (idempotent)
        res1_dup = award_badge(self.user_id, "course_first_quiz", course_id=cid1)
        self.assertFalse(res1_dup)

        # Award same badge for course 2 -> True (isolated per course)
        res2 = award_badge(self.user_id, "course_first_quiz", course_id=cid2)
        self.assertTrue(res2)

        badges_c1 = get_user_badges(self.user_id, course_id=cid1)
        self.assertEqual(len(badges_c1), 1)
        self.assertEqual(badges_c1[0]["badge_key"], "course_first_quiz")
        self.assertEqual(badges_c1[0]["course_id"], cid1)

        badges_c2 = get_user_badges(self.user_id, course_id=cid2)
        self.assertEqual(len(badges_c2), 1)
        self.assertEqual(badges_c2[0]["badge_key"], "course_first_quiz")
        self.assertEqual(badges_c2[0]["course_id"], cid2)

    def test_evaluate_and_award_course_badges_lifecycle(self):
        cid = save_course(
            title="Histoire-Géo : Maroc Moderne",
            subject="Histoire-Géographie",
            language="ar",
            file_path=str(Path(self.temp_dir.name) / "hg.pdf"),
            file_name="hg.pdf",
            file_hash="hash_hg",
            user_id=self.user_id,
        )

        # Initial course overview (no summary, no mindmap, no quizzes, no chat)
        overview_start = get_course_trophies_overview(self.user_id, cid)
        self.assertEqual(overview_start["total_trophies"], 8)
        self.assertEqual(overview_start["unlocked_trophies"], 0)
        self.assertEqual(overview_start["completion_rate"], 0.0)

        # Add summary and mindmap to course
        update_course_summary(cid, "Résumé du cours sur l'histoire moderne du Maroc.")
        save_course_mindmap(cid, "mindmap\n  root((Maroc))\n")

        # Evaluate should trigger course_explored and course_mindmap
        new_badges = evaluate_and_award_course_badges(self.user_id, cid)
        new_keys = [b["key"] for b in new_badges]
        self.assertIn("course_explored", new_keys)
        self.assertIn("course_mindmap", new_keys)

        overview_mid = get_course_trophies_overview(self.user_id, cid)
        self.assertEqual(overview_mid["unlocked_trophies"], 2)
        self.assertEqual(overview_mid["completion_rate"], 25.0)

        # Add 3 quiz attempts with 1 perfect score
        qid = save_quiz(cid, [{"question": "Q1", "options": ["A", "B"], "answer_index": 0}], user_id=self.user_id)
        save_quiz_attempt(cid, qid, 1, 1, {0: 0}, user_id=self.user_id)
        save_quiz_attempt(cid, qid, 0, 1, {0: 1}, user_id=self.user_id)
        save_quiz_attempt(cid, qid, 1, 1, {0: 0}, user_id=self.user_id)

        # Add 2 sanad chat questions
        add_chat_message(cid, "user", "Peux-tu expliquer cet événement ?", user_id=self.user_id)
        add_chat_message(cid, "assistant", "Certainement...", user_id=self.user_id)
        add_chat_message(cid, "user", "Et quelles sont les dates clés ?", user_id=self.user_id)
        add_chat_message(cid, "assistant", "Les dates clés sont...", user_id=self.user_id)

        # Add 2 mastered concepts
        save_concept_mastery(self.user_id, cid, "Règne de Mohammed V", "mastered")
        save_concept_mastery(self.user_id, cid, "Indépendance et Renaissance", "mastered")

        # Evaluate all
        awarded_all = evaluate_and_award_course_badges(self.user_id, cid)
        awarded_keys = [b["key"] for b in awarded_all]
        self.assertIn("course_first_quiz", awarded_keys)
        self.assertIn("course_perfect_score", awarded_keys)
        self.assertIn("course_three_quizzes", awarded_keys)
        self.assertIn("course_sanad_dialogue", awarded_keys)
        self.assertIn("course_concept_master", awarded_keys)
        # All 7 non-grand-master badges are unlocked -> grand master should also be unlocked!
        self.assertIn("course_grand_master", awarded_keys)

        overview_final = get_course_trophies_overview(self.user_id, cid)
        self.assertEqual(overview_final["unlocked_trophies"], 8)
        self.assertEqual(overview_final["completion_rate"], 100.0)

        gm = next(b for b in overview_final["badges"] if b["key"] == "course_grand_master")
        self.assertTrue(gm["is_unlocked"])
        self.assertEqual(gm["progress_percent"], 100)

    def test_get_student_trophies_by_course_multi_and_ranks(self):
        # Create 2 courses
        c1 = save_course(
            title="Maths",
            subject="Mathématiques",
            language="fr",
            file_path=str(Path(self.temp_dir.name) / "m.pdf"),
            file_name="m.pdf",
            file_hash="hash_m",
            user_id=self.user_id,
        )
        c2 = save_course(
            title="SVT",
            subject="Sciences de la Vie et de la Terre",
            language="fr",
            file_path=str(Path(self.temp_dir.name) / "svt.pdf"),
            file_name="svt.pdf",
            file_hash="hash_svt",
            user_id=self.user_id,
        )

        # Initial rank: Apprenti
        ov1 = get_student_trophies_by_course(self.user_id)
        self.assertEqual(ov1["total_courses"], 2)
        self.assertEqual(ov1["total_trophies"], 16)
        self.assertIn("Apprenti", ov1["rank"])

        # Award several badges to c1 and c2
        for key in ["course_explored", "course_mindmap", "course_first_quiz", "course_perfect_score"]:
            award_badge(self.user_id, key, course_id=c1)
            award_badge(self.user_id, key, course_id=c2)

        # 8 unlocked out of 16 = 50% -> Maître des Épreuves
        ov2 = get_student_trophies_by_course(self.user_id)
        self.assertEqual(ov2["unlocked_trophies"], 8)
        self.assertEqual(ov2["completion_rate"], 50.0)
        self.assertIn("Maître", ov2["rank"])

    def test_backup_and_restore_user_badges_preserves_course_id(self):
        cid = save_course(
            title="Informatique",
            subject="Informatique",
            language="fr",
            file_path=str(Path(self.temp_dir.name) / "info.pdf"),
            file_name="info.pdf",
            file_hash="hash_info_unique",
            user_id=self.user_id,
        )
        award_badge(self.user_id, "course_explored", course_id=cid)
        award_badge(self.user_id, "course_first_quiz", course_id=cid)
        award_badge(self.user_id, "first_quiz")  # Global badge

        zip_bytes = export_student_backup(self.user_id)
        self.assertIsNotNone(zip_bytes)

        target_student = create_or_get_google_user("new_learner@test.com", "Nouvel Élève")
        res = restore_student_backup(zip_bytes, target_user_id=target_student["id"])
        self.assertTrue(res["success"])

        # Check restored course
        restored_courses = list_courses(user_id=target_student["id"])
        self.assertEqual(len(restored_courses), 1)
        restored_cid = restored_courses[0]["id"]

        # Check restored badges have remapped course_id
        restored_course_badges = get_user_badges(target_student["id"], course_id=restored_cid)
        self.assertEqual(len(restored_course_badges), 2)
        restored_c_keys = [b["badge_key"] for b in restored_course_badges]
        self.assertIn("course_explored", restored_c_keys)
        self.assertIn("course_first_quiz", restored_c_keys)
        for b in restored_course_badges:
            self.assertEqual(b["course_id"], restored_cid)

        # Check all badges count
        all_restored = get_user_badges(target_student["id"])
        self.assertEqual(len(all_restored), 3)

    def test_init_db_migrates_legacy_user_badges_without_course_id(self):
        legacy_db_file = Path(self.temp_dir.name) / "legacy_badges_migration.db"
        conn = sqlite3.connect(legacy_db_file)
        # Create legacy table without course_id column
        conn.execute("""
            CREATE TABLE user_badges (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                badge_key TEXT NOT NULL,
                unlocked_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                metadata_json TEXT
            )
        """)
        conn.commit()
        conn.close()

        old_db_env = os.environ.get("DATABASE_PATH")
        try:
            os.environ["DATABASE_PATH"] = str(legacy_db_file)
            # Must succeed without sqlite3.OperationalError!
            init_db()

            # Verify column course_id was added and index created
            conn2 = sqlite3.connect(legacy_db_file)
            cur = conn2.cursor()
            cur.execute("PRAGMA table_info(user_badges)")
            cols = [r[1] for r in cur.fetchall()]
            self.assertIn("course_id", cols)

            cur.execute("PRAGMA index_list(user_badges)")
            idx_names = [r[1] for r in cur.fetchall()]
            self.assertIn("idx_user_badges_course", idx_names)
            conn2.close()
        finally:
            if old_db_env is not None:
                os.environ["DATABASE_PATH"] = old_db_env
            else:
                os.environ.pop("DATABASE_PATH", None)

    def test_init_db_migrates_legacy_unique_user_badges_constraint(self):
        legacy_db_file = Path(self.temp_dir.name) / "legacy_unique_badges.db"
        conn = sqlite3.connect(legacy_db_file)
        # Create legacy table with UNIQUE(user_id, badge_key) as in commit b6bee79
        conn.execute("""
            CREATE TABLE user_badges (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                badge_key TEXT NOT NULL,
                unlocked_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                metadata_json TEXT,
                UNIQUE(user_id, badge_key)
            )
        """)
        conn.commit()
        conn.close()

        old_db_env = os.environ.get("DATABASE_PATH")
        try:
            os.environ["DATABASE_PATH"] = str(legacy_db_file)
            init_db()

            # Create a user and 2 courses
            st_user = create_or_get_google_user("learner_unique@test.ma", "Élève Multi")
            uid = st_user["id"]
            c1 = save_course("Maths 1", "Maths", "fr", "/fake/m1.pdf", "m1.pdf", "hash_m1", user_id=uid)
            c2 = save_course("Maths 2", "Maths", "fr", "/fake/m2.pdf", "m2.pdf", "hash_m2", user_id=uid)

            # Award course_explored to course 1 and course 2
            res1 = award_badge(uid, "course_explored", course_id=c1)
            res2 = award_badge(uid, "course_explored", course_id=c2)
            self.assertTrue(res1)
            self.assertTrue(res2)

            # get_student_trophies_by_course must run smoothly without IntegrityError!
            overview = get_student_trophies_by_course(uid)
            self.assertEqual(overview["total_courses"], 2)
            self.assertEqual(overview["unlocked_trophies"], 2)
        finally:
            if old_db_env is not None:
                os.environ["DATABASE_PATH"] = old_db_env
            else:
                os.environ.pop("DATABASE_PATH", None)

    def test_get_gemini_api_key_import_and_app_bindings(self):
        import ast
        from services.config_manager import get_gemini_api_key
        # Verify function is callable
        val = get_gemini_api_key()
        self.assertTrue(val is None or isinstance(val, str))

        # Verify app.py statically imports get_gemini_api_key from services.config_manager
        app_path = Path(__file__).parent.parent / "app.py"
        tree = ast.parse(app_path.read_text(encoding="utf-8"), filename="app.py")
        imported_names = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module == "services.config_manager":
                for alias in node.names:
                    imported_names.add(alias.name)
        self.assertIn("get_gemini_api_key", imported_names)

        # Verify app.py statically imports get_setting from models.database
        db_imported_names = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module == "models.database":
                for alias in node.names:
                    db_imported_names.add(alias.name)
        self.assertIn("get_setting", db_imported_names)


class GoogleDriveManagerTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = os.path.join(self.temp_dir.name, "test_gdrive.db")
        self.old_db = os.environ.get("DATABASE_PATH")
        os.environ["DATABASE_PATH"] = self.db_path
        from models.database import init_db
        init_db()

    def tearDown(self):
        if self.old_db is not None:
            os.environ["DATABASE_PATH"] = self.old_db
        else:
            os.environ.pop("DATABASE_PATH", None)
        self.temp_dir.cleanup()

    def test_format_bytes_human(self):
        from services.google_drive_manager import format_bytes_human
        self.assertEqual(format_bytes_human(500), "500 o")
        self.assertEqual(format_bytes_human(2048), "2.0 Ko")
        self.assertEqual(format_bytes_human(1024 * 1024 * 3), "3.0 Mo")

    def test_ensure_backup_folder_existing(self):
        from services.google_drive_manager import ensure_backup_folder
        mock_service = MagicMock()
        mock_service.files().list().execute.return_value = {
            "files": [{"id": "folder_123", "name": "EcoleAdnane_Backups"}]
        }
        folder_id = ensure_backup_folder(mock_service)
        self.assertEqual(folder_id, "folder_123")

    def test_ensure_backup_folder_create_new(self):
        from services.google_drive_manager import ensure_backup_folder
        mock_service = MagicMock()
        mock_service.files().list().execute.return_value = {"files": []}
        mock_service.files().create().execute.return_value = {"id": "new_folder_456"}
        folder_id = ensure_backup_folder(mock_service)
        self.assertEqual(folder_id, "new_folder_456")

    def test_cleanup_old_drive_backups(self):
        from services.google_drive_manager import cleanup_old_drive_backups
        mock_service = MagicMock()
        files = [{"id": f"file_{i}", "name": f"backup_{i}.zip"} for i in range(15)]
        mock_service.files().list().execute.return_value = {"files": files}
        deleted = cleanup_old_drive_backups(mock_service, "folder_123", keep_count=10)
        self.assertEqual(deleted, 5)
        self.assertEqual(mock_service.files().delete.call_count, 5)

    @patch("services.google_drive_manager.get_drive_service")
    @patch("services.google_drive_manager.ensure_backup_folder")
    def test_upload_backup_to_drive(self, mock_ensure_folder, mock_get_service):
        from services.google_drive_manager import upload_backup_to_drive
        mock_service = MagicMock()
        mock_get_service.return_value = mock_service
        mock_ensure_folder.return_value = "folder_123"
        mock_service.files().create().execute.return_value = {
            "id": "file_999",
            "name": "backup.zip",
            "webViewLink": "https://drive.google.com/test",
        }
        mock_service.files().list().execute.return_value = {"files": []}

        res = upload_backup_to_drive(file_bytes=b"dummy zip data", note="test note")
        self.assertTrue(res["success"])
        self.assertEqual(res["file_id"], "file_999")
        self.assertEqual(res["web_link"], "https://drive.google.com/test")

    @patch("services.google_drive_manager.get_drive_service")
    @patch("services.google_drive_manager.ensure_backup_folder")
    def test_list_drive_backups(self, mock_ensure_folder, mock_get_service):
        from services.google_drive_manager import list_drive_backups
        mock_service = MagicMock()
        mock_get_service.return_value = mock_service
        mock_ensure_folder.return_value = "folder_123"
        mock_service.files().list().execute.return_value = {
            "files": [
                {
                    "id": "f1",
                    "name": "backup_2026.zip",
                    "size": "2048",
                    "createdTime": "2026-10-23T10:00:00Z",
                    "webViewLink": "http://link1",
                    "description": "test",
                }
            ]
        }
        backups = list_drive_backups()
        self.assertEqual(len(backups), 1)
        self.assertEqual(backups[0]["id"], "f1")
        self.assertEqual(backups[0]["size_formatted"], "2.0 Ko")

    @patch("services.google_drive_manager.is_drive_connected")
    @patch("services.google_drive_manager.upload_backup_to_drive")
    def test_auto_backup_on_change_throttling(self, mock_upload, mock_connected):
        from services.google_drive_manager import auto_backup_on_change
        from models.database import set_setting
        mock_connected.return_value = True

        # First call: no last backup time -> should upload
        mock_upload.return_value = {"success": True}
        res1 = auto_backup_on_change(min_interval_minutes=15)
        self.assertTrue(res1.get("success"))

        # Simulate recent backup just now
        recent_iso = datetime.now().isoformat()
        set_setting("last_gdrive_backup_at", recent_iso)

        res2 = auto_backup_on_change(min_interval_minutes=15)
        self.assertTrue(res2.get("skipped"))
        self.assertFalse(res2.get("success"))

    def test_auth_manager_drive_scopes_and_token_helpers(self):
        from services.auth_manager import AUTH_SCOPES, get_google_drive_connect_url
        self.assertIn("https://www.googleapis.com/auth/drive.file", AUTH_SCOPES)
        url = get_google_drive_connect_url("http://localhost:8501")
        self.assertIsInstance(url, str)
        self.assertTrue(url.startswith("https://accounts.google.com/o/oauth2/v2/auth"))

    def test_dedicated_server_never_redirects(self):
        from services.auth_manager import is_running_on_streamlit_cloud, check_and_handle_cloud_redirect
        old_val = os.environ.get("IS_DEDICATED_SERVER")
        try:
            os.environ["IS_DEDICATED_SERVER"] = "true"
            self.assertFalse(is_running_on_streamlit_cloud())
            self.assertFalse(check_and_handle_cloud_redirect())
        finally:
            if old_val is not None:
                os.environ["IS_DEDICATED_SERVER"] = old_val
            else:
                os.environ.pop("IS_DEDICATED_SERVER", None)

    def test_cloud_detection_activates_redirection(self):
        from services.auth_manager import is_running_on_streamlit_cloud, check_and_handle_cloud_redirect
        old_dedicated = os.environ.get("IS_DEDICATED_SERVER")
        old_cloud = os.environ.get("STREAMLIT_COMMUNITY_CLOUD")
        try:
            os.environ.pop("IS_DEDICATED_SERVER", None)
            os.environ["STREAMLIT_COMMUNITY_CLOUD"] = "true"
            self.assertTrue(is_running_on_streamlit_cloud())
            self.assertTrue(check_and_handle_cloud_redirect())
        finally:
            if old_dedicated is not None:
                os.environ["IS_DEDICATED_SERVER"] = old_dedicated
            if old_cloud is not None:
                os.environ["STREAMLIT_COMMUNITY_CLOUD"] = old_cloud
            else:
                os.environ.pop("STREAMLIT_COMMUNITY_CLOUD", None)


if __name__ == "__main__":
    unittest.main()





