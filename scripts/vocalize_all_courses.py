#!/usr/bin/env python3
"""
Script de mise à niveau pédagogique :
Vocalise intégralement tous les cours en langue arabe existants dans la base SQLite
(ajout de toutes les Harakat / Tashkeel : Fatha, Damma, Kasra, Sukun, Shadda, Tanwin)
et régénère les fichiers audio MP3 correspondants pour une prononciation 100% authentique.
"""

import logging
import sqlite3
import sys
import time
from pathlib import Path

# Configurer le logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("vocalize_all_courses")

# Assurer le chemin d'import
ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))

from models.database import get_db_path
from services.ai_engine import diacritize_arabic_text, get_arabic_tashkeel_ratio
from services.voice_manager import detect_arabic_content, generate_or_get_course_fiche_mp3


def main():
    try:
        db_path = get_db_path()
    except Exception:
        db_path = ROOT_DIR / "storage" / "ecole_adnane.db"

    if not db_path.exists():
        logger.error(f"Base de données introuvable : {db_path}")
        sys.exit(1)

    logger.info(f"Connexion à la base SQLite : {db_path}")
    conn = sqlite3.connect(str(db_path))
    cursor = conn.cursor()

    rows = cursor.execute(
        "SELECT id, title, language, summary_markdown, user_id FROM courses WHERE summary_markdown IS NOT NULL"
    ).fetchall()

    logger.info(f"Total cours avec fiche express trouvés : {len(rows)}")

    courses_to_vocalize = []
    for cid, title, lang, summary, uid in rows:
        if not summary:
            continue
        is_ar = (lang == "ar") or detect_arabic_content(summary)
        if not is_ar:
            continue
        ratio = get_arabic_tashkeel_ratio(summary)
        if ratio < 0.40:
            courses_to_vocalize.append((cid, title, summary, uid, ratio))
            logger.info(f"-> Cours {cid} '{title[:35]}' : ratio harakat = {ratio:.2f} (< 0.40) -> À VOCALISER")
        else:
            logger.info(f"== Cours {cid} '{title[:35]}' : ratio harakat = {ratio:.2f} (>= 0.40) -> DÉJÀ VOCALISÉ")

    logger.info(f"Nombre de cours arabes à vocaliser : {len(courses_to_vocalize)}")

    success_count = 0
    for cid, title, summary, uid, old_ratio in courses_to_vocalize:
        t0 = time.time()
        logger.info(f"Vocalisation du cours {cid} ({title[:30]})...")
        try:
            vocalized_summary = diacritize_arabic_text(summary)
            new_ratio = get_arabic_tashkeel_ratio(vocalized_summary)
            logger.info(f"Cours {cid} vocalisé : ratio {old_ratio:.2f} -> {new_ratio:.2f} en {time.time()-t0:.2f}s")

            # Mise à jour en base de données
            cursor.execute(
                "UPDATE courses SET summary_markdown = ? WHERE id = ?",
                (vocalized_summary, cid),
            )
            conn.commit()

            # Supprimer l'ancien MP3 s'il existe pour forcer la régénération
            storage_root = db_path.parent
            cand_mp3 = (storage_root / "users" / str(uid) / "cours" / f"fiche_{cid}.mp3") if uid else (storage_root / "cours" / f"fiche_{cid}.mp3")
            if cand_mp3.exists():
                try:
                    cand_mp3.unlink()
                    logger.info(f"Ancien MP3 supprimé pour régénération : {cand_mp3}")
                except Exception:
                    pass

            # Régénérer le fichier MP3 haute fidélité avec le texte vocalisé
            t_audio = time.time()
            mp3_path = generate_or_get_course_fiche_mp3(cid, vocalized_summary, language="ar", user_id=uid)
            logger.info(f"Audio MP3 régénéré : {mp3_path} en {time.time()-t_audio:.2f}s")

            success_count += 1
        except Exception as e:
            logger.error(f"Échec de la vocalisation du cours {cid} : {e}")

    conn.close()
    logger.info(f"Opération terminée avec succès : {success_count}/{len(courses_to_vocalize)} cours vocalisés et régénérés.")


if __name__ == "__main__":
    main()
