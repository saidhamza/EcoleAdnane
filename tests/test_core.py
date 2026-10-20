"""
Tests unitaires et d'intégration pour Ecole Adnane.
Valide la détection linguistique, la classification 3AC Maroc,
la déduplication SHA-256, SQLite et les services IA.
"""

import os
import tempfile
import unittest
from pathlib import Path

from models.database import (
    add_chat_message,
    clear_chat_history,
    get_chat_history,
    get_course_by_hash,
    get_course_by_id,
    get_latest_quiz,
    get_quiz_stats,
    get_setting,
    init_db,
    list_courses,
    save_course,
    save_quiz,
    save_quiz_attempt,
    set_setting,
    update_course_metadata,
    update_course_summary,
)
from services.ai_engine import clean_json_output
from services.config_manager import get_config_value, save_config_value
from services.downloader import calculate_sha256, ingest_pdf_bytes
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


class TestDatabaseAndIngestion(unittest.TestCase):
    """Tests sur SQLite, le hachage et la déduplication."""

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.test_db_path = Path(self.temp_dir.name) / "test_ecole.db"
        os.environ["DATABASE_PATH"] = str(self.test_db_path)
        init_db(self.test_db_path)

    def tearDown(self):
        self.temp_dir.cleanup()
        if "DATABASE_PATH" in os.environ:
            del os.environ["DATABASE_PATH"]

    def test_sha256_calculation(self):
        data = b"Exemple de document PDF pour le Brevet 3AC"
        h1 = calculate_sha256(data)
        h2 = calculate_sha256(data)
        self.assertEqual(h1, h2)
        self.assertEqual(len(h1), 64)

    def test_course_crud(self):
        cid = save_course(
            title="Théorème de Thalès",
            subject="Mathématiques",
            language="fr",
            file_path="/fake/path.pdf",
            file_hash="fakehash123",
            file_name="thales.pdf",
            raw_text="Contenu du théorème de Thalès...",
            summary_markdown="## Définitions clés\nThalès permet de calculer des longueurs.",
            key_concepts=["Thalès", "Parallélisme", "Proportionnalité"],
        )
        self.assertIsNotNone(cid)

        # Lecture par ID
        c = get_course_by_id(cid)
        self.assertIsNotNone(c)
        self.assertEqual(c["title"], "Théorème de Thalès")
        self.assertEqual(c["language"], "fr")
        self.assertEqual(len(c["key_concepts"]), 3)

        # Lecture par Hash
        c_by_hash = get_course_by_hash("fakehash123")
        self.assertIsNotNone(c_by_hash)
        self.assertEqual(c_by_hash["id"], cid)

        # Mise à jour du résumé
        update_course_summary(cid, "## Nouveau Résumé", ["Thalès", "Révision"])
        updated = get_course_by_id(cid)
        self.assertEqual(updated["summary_markdown"], "## Nouveau Résumé")
        self.assertEqual(len(updated["key_concepts"]), 2)

        # Filtrage
        all_courses = list_courses(subject="Mathématiques", language="fr")
        self.assertEqual(len(all_courses), 1)

    def test_quizzes_and_attempts(self):
        cid = save_course(
            title="درس الحرب العالمية الثانية",
            subject="الاجتماعيات",
            language="ar",
            file_path="/fake/hist.pdf",
            file_hash="hashhist456",
            file_name="hist.pdf",
            raw_text="أسباب الحرب العالمية الثانية...",
        )

        quiz_data = [
            {
                "question": "متى اندلعت الحرب العالمية الثانية؟",
                "options": ["1939", "1914", "1945", "1918"],
                "answer_index": 0,
                "explanation": "اندلعت الحرب في سبتمبر 1939 بغزو بولندا.",
                "trap_alert": "لا تخلط بين تاريخ الحرب العالمية الأولى (1914) والثانية (1939).",
                "difficulty": "سهل",
            }
        ]
        qid = save_quiz(cid, quiz_data)
        self.assertIsNotNone(qid)

        latest_q = get_latest_quiz(cid)
        self.assertIsNotNone(latest_q)
        self.assertEqual(len(latest_q["questions"]), 1)
        self.assertEqual(latest_q["questions"][0]["options"][0], "1939")

        # Sauvegarde d'une tentative
        attempt_id = save_quiz_attempt(
            course_id=cid,
            quiz_id=qid,
            score=1,
            total_questions=1,
            answers={0: 0},
        )
        self.assertIsNotNone(attempt_id)

        stats = get_quiz_stats()
        self.assertEqual(stats["total_attempts"], 1)
        self.assertEqual(stats["total_score"], 1)
        self.assertEqual(stats["average_success_rate"], 100.0)

    def test_update_course_metadata(self):
        cid = save_course(
            title="Leçon Inconnue",
            subject="Mathématiques",
            language="fr",
            file_path="/fake/test.pdf",
            file_hash="hashmeta123",
            file_name="test.pdf",
            raw_text="Texte quelconque",
        )
        # Corriger la matière vers Histoire-Géo (الاجتماعيات) en Arabe
        update_course_metadata(cid, "المغرب العربي", "الاجتماعيات", "ar")
        updated = get_course_by_id(cid)
        self.assertEqual(updated["title"], "المغرب العربي")
        self.assertEqual(updated["subject"], "الاجتماعيات")
        self.assertEqual(updated["language"], "ar")

    def test_chat_messages(self):
        cid = save_course(
            title="Système Nerveux",
            subject="SVT",
            language="fr",
            file_path="/fake/svt.pdf",
            file_hash="hashsvt789",
            file_name="svt.pdf",
            raw_text="Le système nerveux comprend les centres nerveux et les nerfs...",
        )

        add_chat_message(cid, "user", "C'est quoi un réflexe ?")
        add_chat_message(cid, "assistant", "Un réflexe est une réaction motrice involontaire. Peux-tu me donner un exemple ?")

        history = get_chat_history(cid)
        self.assertEqual(len(history), 2)
        self.assertEqual(history[0]["role"], "user")
        self.assertEqual(history[1]["role"], "assistant")

        clear_chat_history(cid)
        self.assertEqual(len(get_chat_history(cid)), 0)

    def test_settings_storage(self):
        set_setting("ACTIVE_THEME", "morocco_clean")
        val = get_setting("ACTIVE_THEME")
        self.assertEqual(val, "morocco_clean")

    def test_clean_json_output(self):
        raw_markdown = """```json
[
  {"title": "Test"}
]
```"""
        cleaned = clean_json_output(raw_markdown)
        self.assertEqual(cleaned, '[\n  {"title": "Test"}\n]')

    def test_backup_and_restore(self):
        from services.backup_manager import (
            export_backup_zip,
            export_database_file,
            get_backup_summary,
            restore_backup,
        )
        # Vérifier que les fonctions d'export génèrent des octets valides
        db_bytes = export_database_file()
        self.assertTrue(len(db_bytes) > 0)
        self.assertTrue(db_bytes.startswith(b"SQLite format 3\x00"))

        zip_bytes = export_backup_zip()
        self.assertTrue(len(zip_bytes) > 0)

        # Tester la restauration avec le zip
        res_zip = restore_backup(zip_bytes, "test_backup.zip")
        self.assertTrue(res_zip["success"])

        # Tester la restauration avec le fichier .db brut
        res_db = restore_backup(db_bytes, "ecole_adnane.db")
        self.assertTrue(res_db["success"])


if __name__ == "__main__":
    unittest.main()

