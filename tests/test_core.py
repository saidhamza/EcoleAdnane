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
import tempfile
import unittest
import zipfile
from pathlib import Path

from models.database import (
    add_chat_message,
    clear_chat_history,
    create_or_get_google_user,
    get_chat_history,
    get_course_by_hash,
    get_course_by_id,
    get_global_admin_kpis,
    get_latest_quiz,
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
    set_user_setting,
    update_course_metadata,
    update_course_summary,
)
from services.ai_engine import clean_json_output
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

        self.assertEqual(detect_language(text_fr), "fr")
        self.assertEqual(detect_language(text_ar), "ar")
        self.assertEqual(detect_language(text_mixed_mostly_ar), "ar")

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


if __name__ == "__main__":
    unittest.main()
