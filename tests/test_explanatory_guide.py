import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))
import json
import os
import shutil
import tempfile
import unittest
from pathlib import Path

from models.database import (
    create_or_get_google_user,
    get_course_explanatory_guide,
    get_course_explanatory_guide_pdf,
    init_db,
    save_course,
    save_course_explanatory_guide,
    save_course_explanatory_guide_pdf,
)
from services.explanatory_guide_engine import (
    build_explanatory_guide_pdf_and_viewer,
    detect_subject_theme,
    generate_guide_slide_image,
)


class TestExplanatoryGuideEngine(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.db_path = Path(self.temp_dir) / "test_guide.db"
        os.environ["DATABASE_PATH"] = str(self.db_path)
        init_db(self.db_path)

        self.user = create_or_get_google_user("student_guide@ecole.test", "Élève Guide", role="student")

        # Create a mock math course
        self.course_id = save_course(
            title="Théorème de Thalès",
            subject="Mathématiques",
            language="fr",
            file_path="/tmp/test_thales.pdf",
            file_hash="thales_hash_1234",
            file_name="thales.pdf",
            raw_text="Dans un triangle ABC, si M est un point de (AB) et N un point de (AC)... AM/AB = AN/AC = MN/BC.",
            summary_markdown="# Théorème de Thalès\nPropriété fondamentale des proportions.",
            user_id=self.user["id"],
        )

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)
        # Cleanup generated test guide files in static and storage
        base_dir = Path(__file__).parent.parent / "static" / "guides"
        for ext in ["pdf", "html"]:
            f = base_dir / f"guide_course_{self.course_id}.{ext}"
            if f.exists():
                f.unlink(missing_ok=True)
        try:
            from services.downloader import STORAGE_DIR, get_user_storage_dir
            st_g = STORAGE_DIR / "guides" / f"guide_course_{self.course_id}.pdf"
            if st_g.exists():
                st_g.unlink(missing_ok=True)
            u_g = get_user_storage_dir(self.user["id"]) / f"guide_course_{self.course_id}.pdf"
            if u_g.exists():
                u_g.unlink(missing_ok=True)
        except Exception:
            pass

    def test_detect_subject_theme(self):
        """Vérifie la détection thématique des matières (couleurs, icônes, badges)."""
        math_theme = detect_subject_theme("Mathématiques")
        self.assertEqual(math_theme["type"], "math")
        self.assertEqual(math_theme["icon"], "📐")
        self.assertEqual(math_theme["primary"], "#2563eb")

        pc_theme = detect_subject_theme("Physique - Chimie")
        self.assertEqual(pc_theme["type"], "physics_chemistry")
        self.assertEqual(pc_theme["icon"], "🧪")

        svt_theme = detect_subject_theme("Sciences de la Vie et de la Terre")
        self.assertEqual(svt_theme["type"], "biology")
        self.assertEqual(svt_theme["icon"], "🌱")

        geo_theme = detect_subject_theme("Géographie")
        self.assertEqual(geo_theme["type"], "geography")
        self.assertEqual(geo_theme["icon"], "🌍")

    def test_database_persistence_explanatory_guide(self):
        """Vérifie la sauvegarde et la récupération du deck et du PDF en base de données."""
        deck_sample = {
            "title": "Théorème de Thalès - Guide Visuel",
            "subject_badge": "MATHÉMATIQUES 3AC",
            "overview": "Maîtriser les rapports de proportionnalité dans le triangle.",
            "slides": [
                {
                    "slide_num": 1,
                    "badge": "📐 LE CONCEPT INTUITIF",
                    "title": "Agrandir et Réduire les Triangles",
                    "key_points": ["Thalès permet de calculer des distances inaccessibles."],
                    "highlight_box": {
                        "title": "FORMULE CLÉ",
                        "content": "AM / AB = AN / AC = MN / BC",
                    },
                    "example_or_trap": {
                        "type": "tip",
                        "title": "Astuce Brevet",
                        "content": "Vérifiez toujours l'alignement des points dans le même ordre.",
                    },
                    "image_prompt": "Clean geometry diagram of Thales theorem, vibrant blue colors",
                }
            ],
        }

        # Sauvegarde deck
        save_course_explanatory_guide(self.course_id, deck_sample)
        retrieved_deck = get_course_explanatory_guide(self.course_id)
        self.assertIsNotNone(retrieved_deck)
        self.assertEqual(retrieved_deck["title"], "Théorème de Thalès - Guide Visuel")
        self.assertEqual(len(retrieved_deck["slides"]), 1)

        # Sauvegarde PDF URL
        pdf_url = f"/static/guides/guide_course_{self.course_id}.pdf"
        save_course_explanatory_guide_pdf(self.course_id, pdf_url)
        retrieved_pdf = get_course_explanatory_guide_pdf(self.course_id)
        self.assertEqual(retrieved_pdf, pdf_url)

    def test_build_explanatory_guide_files(self):
        """Vérifie la génération des fichiers HTML interactif et PDF via Pillow/Chromium."""
        deck_sample = {
            "title": "Guide Test Thalès",
            "subject_badge": "MATHÉMATIQUES",
            "overview": "Résumé de test.",
            "slides": [
                {
                    "slide_num": 1,
                    "badge": "🎯 CONCEPT",
                    "title": "Calcul de Distances",
                    "key_points": ["Premier point didactique", "Deuxième point de calcul"],
                    "highlight_box": {"title": "RÈGLE", "content": "AM/AB = AN/AC"},
                    "example_or_trap": {"type": "trap", "title": "Piège", "content": "Attention aux droites sécantes"},
                    "image_prompt": "Geometry triangle diagram with blue accents",
                }
            ],
        }

        pdf_url, html_url = build_explanatory_guide_pdf_and_viewer(
            guide_deck=deck_sample,
            course_id=self.course_id,
            subject="Mathématiques",
            course_title="Théorème de Thalès",
            language="fr",
            user_id=self.user["id"],
        )

        self.assertTrue(pdf_url.endswith(f"guide_course_{self.course_id}.pdf"))
        self.assertTrue(html_url.endswith(f"guide_course_{self.course_id}.html"))

        # Vérification sur disque (static/guides)
        base_dir = Path(__file__).parent.parent / "static" / "guides"
        html_file = base_dir / f"guide_course_{self.course_id}.html"
        pdf_file = base_dir / f"guide_course_{self.course_id}.pdf"

        self.assertTrue(html_file.exists(), "Le fichier HTML de la visionneuse doit être créé.")
        self.assertTrue(pdf_file.exists(), "Le fichier PDF compilé doit être créé.")
        self.assertGreater(html_file.stat().st_size, 500, "Le fichier HTML doit avoir un contenu substantiel.")
        self.assertGreater(pdf_file.stat().st_size, 500, "Le fichier PDF doit avoir un contenu substantiel.")

        # Vérification sauvegarde persistante dans storage/ (sécurité anti-perte)
        from services.downloader import STORAGE_DIR, get_user_storage_dir
        storage_pdf = STORAGE_DIR / "guides" / f"guide_course_{self.course_id}.pdf"
        user_pdf = get_user_storage_dir(self.user["id"]) / f"guide_course_{self.course_id}.pdf"
        self.assertTrue(storage_pdf.exists(), "Le PDF doit être dupliqué dans storage/guides.")
        self.assertTrue(user_pdf.exists(), "Le PDF doit être dupliqué dans le dossier de cours de l'élève.")

        # Vérification intégration dans la sauvegarde élève (ZIP)
        from services.backup_manager import export_student_backup, export_global_backup
        import zipfile, io
        student_zip = export_student_backup(self.user["id"])
        with zipfile.ZipFile(io.BytesIO(student_zip)) as z:
            names = z.namelist()
            self.assertTrue(
                any(f"guide_course_{self.course_id}.pdf" in n for n in names),
                f"Le PDF généré doit être inclus dans l'archive de sauvegarde de l'élève (contenu: {names})",
            )

        # Vérification intégration dans la sauvegarde globale (ZIP)
        global_zip = export_global_backup()
        with zipfile.ZipFile(io.BytesIO(global_zip)) as z:
            names = z.namelist()
            self.assertTrue(
                any(f"guide_course_{self.course_id}.pdf" in n for n in names),
                f"Le PDF généré doit être inclus dans l'archive globale (contenu: {names})",
            )


if __name__ == "__main__":
    unittest.main()

