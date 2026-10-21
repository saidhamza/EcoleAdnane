"""
Tests unitaires et d'intégration pour Ecole Adnane.
Valide la détection linguistique, la classification 3AC Maroc,
l'authentification multi-utilisateurs (premier connecté = Admin),
le cloisonnement strict SQLite et arborescence physique,
les clés API et identifiants individuels,
les sauvegardes étanches (élève et globale) avec sécurité anti-traversal,
et les scopes officiels Google Classroom.
"""

import io
import json
import os
import sqlite3
import tempfile
import unittest
import zipfile
from pathlib import Path

from models.database import (
    add_chat_message,
    clear_chat_history,
    create_or_get_google_user,
    delete_user_account,
    get_chat_history,
    get_course_by_hash,
    get_course_by_id,
    get_global_admin_kpis,
    get_latest_quiz,
    get_pedagogical_cycle,
    get_quiz_stats,
    get_setting,
    get_user_by_email,
    get_user_by_id,
    get_user_count,
    get_user_setting,
    init_db,
    list_courses,
    list_users,
    save_course,
    save_flashcard,
    save_quiz,
    save_quiz_attempt,
    set_setting,
    set_user_blocked_status,
    set_user_setting,
    update_course_metadata,
    update_course_summary,
    update_user_age,
    update_user_name,
    update_user_role,
)
from services.ai_engine import clean_json_output, resolve_student_age
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

        # Vérification que le nouveau compte possède bien le cours et le chat
        restored_courses = list_courses(user_id=new_user["id"])
        self.assertEqual(len(restored_courses), 1)
        self.assertEqual(restored_courses[0]["title"], "Physique Chimie 3AC")

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


if __name__ == "__main__":
    unittest.main()


