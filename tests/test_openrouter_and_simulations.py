"""
Tests unitaires pour la gestion de la clé OpenRouter globale par l'administrateur,
l'attribution granulaire d'accès aux élèves, la persistance des animations de cours,
et le générateur de simulations interactives et BD animées.
"""

import json
import os
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from models.database import (
    create_or_get_google_user,
    get_connection,
    get_course_animation,
    get_openrouter_authorized_user_ids,
    init_db,
    is_user_openrouter_allowed,
    save_course,
    save_course_animation,
    set_user_openrouter_access,
)
from services.ai_engine import (
    call_llm,
    call_openrouter_chat_completion,
    generate_course_animation_simulation,
    strip_html_code_blocks,
)
from services.config_manager import (
    get_openrouter_api_key,
    get_openrouter_model,
    save_openrouter_model,
    test_openrouter_connection,
)


class OpenRouterAndSimulationsTests(unittest.TestCase):
    def setUp(self):
        """Initialise une base temporaire pour chaque test."""
        self.temp_db_path = Path("/tmp") / f"test_db_{self._testMethodName}.db"
        if self.temp_db_path.exists():
            self.temp_db_path.unlink()
        self.orig_db_path_env = os.environ.get("DATABASE_PATH")
        os.environ["DATABASE_PATH"] = str(self.temp_db_path)
        init_db(self.temp_db_path)

        # Création d'utilisateurs test
        self.admin = create_or_get_google_user(
            email=f"admin_{self._testMethodName}@ecole.test",
            name="Admin Test",
            role="admin",
        )
        self.student = create_or_get_google_user(
            email=f"student_{self._testMethodName}@ecole.test",
            name="Student Test",
            role="student",
        )

    def tearDown(self):
        if self.orig_db_path_env is not None:
            os.environ["DATABASE_PATH"] = self.orig_db_path_env
        else:
            os.environ.pop("DATABASE_PATH", None)
        if self.temp_db_path.exists():
            self.temp_db_path.unlink()

    def test_openrouter_access_permissions(self):
        admin_id = self.admin["id"]
        student_id = self.student["id"]

        # L'admin a accès par défaut
        self.assertTrue(is_user_openrouter_allowed(admin_id))

        # L'élève n'a pas accès par défaut
        self.assertFalse(is_user_openrouter_allowed(student_id))
        self.assertNotIn(student_id, get_openrouter_authorized_user_ids())

        # L'administrateur accorde l'accès à l'élève
        set_user_openrouter_access(student_id, True)
        self.assertTrue(is_user_openrouter_allowed(student_id))
        self.assertIn(student_id, get_openrouter_authorized_user_ids())

        # L'administrateur révoque l'accès de l'élève
        set_user_openrouter_access(student_id, False)
        self.assertFalse(is_user_openrouter_allowed(student_id))
        self.assertNotIn(student_id, get_openrouter_authorized_user_ids())

    def test_course_animation_persistence(self):
        course_id = save_course(
            title="Les Atomes et la Matière",
            subject="Physique-Chimie",
            language="fr",
            file_path="/tmp/fake_atoms.pdf",
            file_hash="hash_atoms_12345",
            file_name="fake_atoms.pdf",
            raw_text="Contenu sur la structure de l'atome avec protons et électrons...",
            user_id=self.student["id"],
        )

        # Au départ, aucune animation enregistrée
        self.assertIsNone(get_course_animation(course_id))

        fake_html = """<!DOCTYPE html>
<html>
<head><title>Simulation Atomes</title></head>
<body><canvas id="atomCanvas"></canvas><script>console.log("Atom Running");</script></body>
</html>"""

        # Sauvegarde
        save_course_animation(course_id, fake_html)
        saved_html = get_course_animation(course_id)
        self.assertEqual(saved_html, fake_html)

        # Mise à jour
        updated_html = fake_html.replace("Simulation Atomes", "Simulation Atomes V2")
        save_course_animation(course_id, updated_html)
        self.assertEqual(get_course_animation(course_id), updated_html)

    def test_strip_html_code_blocks(self):
        raw = "```html\n<!DOCTYPE html><html><body>Test</body></html>\n```"
        self.assertEqual(strip_html_code_blocks(raw), "<!DOCTYPE html><html><body>Test</body></html>")

        raw_no_fence = "<!DOCTYPE html><html><body>Test 2</body></html>"
        self.assertEqual(strip_html_code_blocks(raw_no_fence), "<!DOCTYPE html><html><body>Test 2</body></html>")

    @patch("urllib.request.urlopen")
    def test_test_openrouter_connection_success(self, mock_urlopen):
        mock_resp = MagicMock()
        mock_resp.read.return_value = json.dumps({
            "choices": [{"message": {"content": "OK"}}]
        }).encode("utf-8")
        mock_resp.__enter__.return_value = mock_resp
        mock_urlopen.return_value = mock_resp

        res = test_openrouter_connection(api_key="sk-or-test-mock-key", model="meta-llama/llama-3.3-70b-instruct")
        self.assertTrue(res["success"])
        self.assertEqual(res["provider"], "openrouter")
        self.assertEqual(res["model"], "meta-llama/llama-3.3-70b-instruct")

    def test_openrouter_model_config(self):
        default_model = get_openrouter_model()
        self.assertTrue(bool(default_model))
        save_openrouter_model("openai/gpt-4o-mini")
        self.assertEqual(get_openrouter_model(), "openai/gpt-4o-mini")
        # Restauration du défaut
        save_openrouter_model(default_model)

    @patch("services.ai_engine.call_openrouter_chat_completion")
    def test_generate_course_animation_simulation_openrouter(self, mock_call_or):
        student_id = self.student["id"]

        # Accorder l'accès OpenRouter à l'élève
        set_user_openrouter_access(student_id, True)

        expected_html = "<!DOCTYPE html><html><body><canvas id='sim'></canvas></body></html>"
        mock_call_or.return_value = f"```html\n{expected_html}\n```"

        with patch("services.ai_engine.get_openrouter_api_key", return_value="sk-or-fake-test-key"):
            html = generate_course_animation_simulation(
                course_text="Les liaisons chimiques entre atomes d'hydrogène et d'oxygène.",
                subject="Physique-Chimie",
                course_title="La Molécule d'Eau",
                language="fr",
                user_id=student_id,
            )
            self.assertEqual(html, expected_html)
            self.assertTrue(mock_call_or.called)

    @patch("services.ai_engine.call_openrouter_chat_completion")
    def test_call_llm_routes_to_openrouter_for_authorized_student(self, mock_call_or):
        student_id = self.student["id"]

        # Élève autorisé OpenRouter par l'administrateur
        set_user_openrouter_access(student_id, True)
        mock_call_or.return_value = "Réponse générée via OpenRouter pour l'élève."

        with patch("services.ai_engine.get_user_gemini_api_key", return_value=None), \
             patch("services.ai_engine.get_user_openai_api_key", return_value=None), \
             patch("services.ai_engine.get_openrouter_api_key", return_value="sk-or-mock-key"):
            reply = call_llm(
                prompt="Explique-moi les fractions",
                user_id=student_id,
            )
            self.assertEqual(reply, "Réponse générée via OpenRouter pour l'élève.")
            self.assertTrue(mock_call_or.called)


if __name__ == "__main__":
    unittest.main()
