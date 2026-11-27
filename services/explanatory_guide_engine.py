"""
Module de génération de Guides Visuels Explicatifs & Présentations Pédagogiques PDF (Style NotebookLM).
Spécialement optimisé pour les Mathématiques, la Physique-Chimie, les SVT, la Géographie et les matières logiques.
Découpe les cours en diapositives 16:9 ultra-claires, colorées et didactiques (concepts, formules mises en valeur,
méthodes pas-à-pas, exemples d'examens résolus, pièges fréquents et astuces), génère les illustrations et infographies
par IA, la narration vocale, et compile le tout en PDF haute résolution (1376x768) téléchargeable.
"""

import base64
import json
import logging
import os
import re
import subprocess
import time
import urllib.request
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from services.config_manager import get_openrouter_api_key
from services.voice_manager import clean_text_for_speech, get_server_tts_audio_base64

logger = logging.getLogger(__name__)


def detect_subject_theme(subject: str) -> Dict[str, str]:
    """
    Retourne la palette de couleurs et les attributs visuels adaptés à la matière.
    """
    s = (subject or "").lower()
    if any(k in s for k in ("math", "رياضيات", "géométrie", "algèbre", "calcul")):
        return {
            "type": "math",
            "primary": "#2563eb",       # Bleu Roi
            "primary_dark": "#1d4ed8",
            "secondary": "#4f46e5",     # Indigo
            "accent": "#0ea5e9",        # Cyan
            "bg_card": "#eff6ff",
            "border_card": "#bfdbfe",
            "icon": "📐",
            "badge_default": "MATHÉMATIQUES 3AC",
        }
    elif any(k in s for k in ("physique", "chimie", "فيزياء", "كيمياء", "pc")):
        return {
            "type": "physics_chemistry",
            "primary": "#059669",       # Émeraude
            "primary_dark": "#047857",
            "secondary": "#0891b2",     # Cyan foncé
            "accent": "#10b981",
            "bg_card": "#ecfdf5",
            "border_card": "#a7f3d0",
            "icon": "🧪",
            "badge_default": "PHYSIQUE - CHIMIE 3AC",
        }
    elif any(k in s for k in ("svt", "vie", "terre", "علوم الحياة", "biologie")):
        return {
            "type": "biology",
            "primary": "#16a34a",       # Vert forêt
            "primary_dark": "#15803d",
            "secondary": "#65a30d",     # Tilleul
            "accent": "#84cc16",
            "bg_card": "#f0fdf4",
            "border_card": "#bbf7d0",
            "icon": "🌱",
            "badge_default": "SCIENCES DE LA VIE & TERRE",
        }
    elif any(k in s for k in ("géo", "جغرافيا", "géographie", "société", "espace")):
        return {
            "type": "geography",
            "primary": "#d97706",       # Ambre / Ocre
            "primary_dark": "#b45309",
            "secondary": "#ea580c",     # Terracotta
            "accent": "#f59e0b",
            "bg_card": "#fffbeb",
            "border_card": "#fde68a",
            "icon": "🌍",
            "badge_default": "GÉOGRAPHIE & ESPACE",
        }
    else:
        return {
            "type": "general",
            "primary": "#7c3aed",       # Violet électrique
            "primary_dark": "#6d28d9",
            "secondary": "#db2777",     # Rose dynamique
            "accent": "#a855f7",
            "bg_card": "#faf5ff",
            "border_card": "#e9d5ff",
            "icon": "💡",
            "badge_default": "GUIDE PÉDAGOGIQUE",
        }


def generate_course_explanatory_guide_deck(
    course_text: str,
    subject: str,
    course_title: str,
    language: str = "ar",
    user_id: Optional[int] = None,
) -> Dict[str, Any]:
    """
    Étape 1 : Conception didactique du guide visuel explicatif par l'IA.
    Découpe le cours en 4 à 5 diapositives 16:9 structurées :
    - Maths : concept intuitif, formule mathématique, méthode pas-à-pas, exemple résolu, pièges et astuce.
    - Sciences : phénomène réel, expérience de labo, explication microscopique, lois et calculs, synthèse d'examen.
    - Géographie : repères et carte, atouts, défis, étude de cas, schéma de synthèse.
    """
    from services.ai_engine import call_llm, call_openrouter_chat_completion, is_user_openrouter_allowed

    truncated_text = (course_text or "")[:6500].strip()
    is_ar = language == "ar"
    is_en = language == "en"
    theme = detect_subject_theme(subject)

    lang_instr = (
        "Tout le contenu ('title', 'overview', 'slides.badge', 'slides.title', 'slides.key_points', "
        "'slides.highlight_box', 'slides.example_or_trap') DOIT être en ARABE académique limpide "
        "avec TASHKEEL COMPLET (diacritiques voyellés sur chaque mot) pour faciliter la lecture et la prononciation."
        if is_ar
        else (
            "All content MUST be in clear, engaging, concise ENGLISH in a modern educational deck style."
            if is_en
            else "Tout le contenu ('title', 'overview', 'slides.badge', 'slides.title', 'slides.key_points', "
            "'slides.highlight_box', 'slides.example_or_trap') DOIT être en FRANÇAIS pédagogique clair, percutant et vivant."
        )
    )

    subject_guidelines = ""
    if theme["type"] == "math":
        subject_guidelines = """
SPÉCIFICITÉ MATHÉMATIQUES :
- Diapositive 1 : Le Concept dans la vraie vie & Intuition concrète (À quoi ça sert ? Carte d'identité du théorème/notion).
- Diapositive 2 : La Définition Formelle & Formule Magique (mise en valeur de la formule, signification de chaque variable, conditions requises comme triangle rectangle, etc.).
- Diapositive 3 : Méthode de Résolution Pas-à-Pas (Étape 1 : Données, Étape 2 : Propriété clé, Étape 3 : Calcul & Conclusion).
- Diapositive 4 : Exemple Type d'Examen Résolu (énoncé type brevet/collège, calcul détaillé étape par étape, rédaction parfaite).
- Diapositive 5 : Les 3 Pièges d'Examen Fréquents & Règle d'or mnémotechnique (ce qu'il ne faut JAMAIS confondre).
"""
    elif theme["type"] in ("physics_chemistry", "biology"):
        subject_guidelines = """
SPÉCIFICITÉ SCIENCES (PHYSIQUE-CHIMIE / SVT) :
- Diapositive 1 : Le Phénomène dans la Nature ou au Quotidien (problématique réelle, observation familière).
- Diapositive 2 : L'Expérience Fondamentale de Laboratoire (matériel, protocole simple, ce qu'on observe directement).
- Diapositive 3 : L'Explication Scientifique au niveau atomique/moléculaire ou cellulaire (lois, équation de réaction ou schéma biologique).
- Diapositive 4 : Lois Physiques / Équations & Calculs d'Application Concrets.
- Diapositive 5 : Ce qu'il faut absolument retenir pour le Contrôle & Pièges classiques à éviter.
"""
    elif theme["type"] == "geography":
        subject_guidelines = """
SPÉCIFICITÉ GÉOGRAPHIE & ÉCONOMIE :
- Diapositive 1 : Vue d'Ensemble, Définition des Notions Clés et Grands Chiffres Repères.
- Diapositive 2 : Les Atouts et Potentialités Majeures (ressources naturelles, position stratégique, dynamisme).
- Diapositive 3 : Les Défis et Contraintes Majeurs (climat, démographie, disparités régionales, dépendances).
- Diapositive 4 : Étude de Cas Concrète et Analyse Comparée (ex: Maroc, Maghreb, Union Européenne).
- Diapositive 5 : Schéma Bilan d'Examen : Synthèse Visuelle des Flux & Vocabulaire Clé.
"""
    else:
        subject_guidelines = """
SPÉCIFICITÉ GÉNÉRALE :
- Découpe la leçon en 4 à 5 diapositives de révision progressive : Le Concept Clé, La Règle / Théorie, La Méthode Pas-à-Pas, L'Exemple d'Application Pratique, Les Pièges et Bilan d'Examen.
"""

    prompt = f"""Tu es un concepteur pédagogique d'élite, expert dans la création de présentations visuelles ultra-claires, inspirées du style NotebookLM, pour collégiens (élèves de 14 ans / 3AC).

OBJECTIF :
Transformer le cours suivant en un GUIDE VISUEL EXPLICATIF de 4 à 5 diapositives 16:9 haute définition, très structuré, pédagogique et coloré :
- Matière : {subject}
- Titre du cours : {course_title}
- Langue : {language}

CONTENU DU COURS :
\"\"\"
{truncated_text}
\"\"\"

CONSIGNES PÉDAGOGIQUES :
1. {lang_instr}
{subject_guidelines}
2. Découpe impérativement le cours en exactement 4 à 5 diapositives progressives.
3. Pour chaque diapositive :
   - "slide_num" : entier (1, 2, 3...)
   - "badge" : étiquette de catégorie (ex: "📐 LE CONCEPT INTUITIF", "⚡ LA FORMULE CLÉ", "📝 MÉTHODE PAS-À-PAS", "🔬 L'EXPÉRIENCE DE LABO", "⚠️ PIÈGES D'EXAMEN", "💡 RÈGLE D'OR")
   - "title" : titre court, percutant et élégant de la diapositive
   - "key_points" : liste de 2 à 4 phrases claires avec des mots clés bien mis en valeur
   - "highlight_box" : objet contenant {{"title": "titre encadré", "content": "formule mathématique, loi physique, équation ou règle fondamentale"}}
   - "example_or_trap" : objet contenant {{"type": "example" ou "trap" ou "tip", "title": "Exemple type / Piège classique", "content": "explication concrète en 2-3 phrases"}}
   - "image_prompt" : prompt en ANGLAIS précis et descriptif pour générer une infographie didactique ou illustration éducative moderne (16:9 widescreen, clean educational infographics diagram, vibrant colors, clear scientific / mathematical visualization, high modern aesthetic, highly detailed).
4. RÈGLE CRITIQUE POUR LES PROMPTS D'IMAGES : Ne mentionne AUCUN nom de personne politique controversée ou de symbole sensible. Privilégie les schémas géométriques, infographies de laboratoire, diagrammes moléculaires, cartes thématiques 3D, cadrans scientifiques et illustrations éducatives modernes.
5. RÈGLE STRICTE SUR LES GUILLEMETS : Dans les chaînes de texte, n'utilise JAMAIS de guillemets doubles (") à l'intérieur du texte ! Utilise exclusivement des guillemets français « » ou des apostrophes '.

RÉPONDS STRICTEMENT SOUS FORME D'UN OBJET JSON VALIDE SANS TEXTE AVANT NI APRÈS :
{{
  "title": "titre du guide visuel explicatif",
  "subject_badge": "{theme['badge_default']}",
  "overview": "résumé percutant du cours en 2 phrases",
  "slides": [
    {{
      "slide_num": 1,
      "badge": "🎯 LE CONCEPT INTUITIF",
      "title": "titre de la slide 1",
      "key_points": [
        "point clé 1...",
        "point clé 2..."
      ],
      "highlight_box": {{
        "title": "LA FORMULE / RÈGLE CLÉ",
        "content": "formule ou définition indispensable..."
      }},
      "example_or_trap": {{
        "type": "tip",
        "title": "Astuce pour le contrôle",
        "content": "conseil pratique..."
      }},
      "image_prompt": "A modern colorful educational infographics illustration explaining ... 16:9 widescreen, clean scientific diagram, vibrant modern aesthetic, highly detailed."
    }}
  ]
}}
"""

    system_instruction = (
        "Tu es un professeur chevronné et un expert en vulgarisation pédagogique visuelle. "
        "Tu conçois des présentations claires, structurées et visuellement stimulantes pour aider les collégiens à exceller."
    )

    # 1. Tentative via OpenRouter si configuré
    is_allowed = True if user_id is None else is_user_openrouter_allowed(user_id)
    raw_response = None
    if is_allowed:
        try:
            messages = [
                {"role": "system", "content": system_instruction},
                {"role": "user", "content": prompt},
            ]
            raw_response = call_openrouter_chat_completion(
                messages=messages,
                model="google/gemini-2.5-flash",
                temperature=0.4,
                json_mode=True,
            )
        except Exception as e_or:
            logger.warning(f"Échec OpenRouter pour guide explicatif ({e_or}), repli sur le LLM par défaut...")

    # 2. Repli LLM par défaut
    if not raw_response or not raw_response.strip():
        raw_response = call_llm(
            prompt=prompt,
            system_instruction=system_instruction,
            temperature=0.4,
            user_id=user_id,
        )

    # 3. Extraction et nettoyage JSON
    try:
        clean = (raw_response or "").strip()
        if "```json" in clean:
            clean = clean.split("```json", 1)[1].split("```", 1)[0].strip()
        elif "```" in clean:
            clean = clean.split("```", 1)[1].split("```", 1)[0].strip()

        clean = re.sub(r'[\x00-\x1f\x7f-\x9f]', lambda m: ' ' if m.group(0) in ('\n', '\r', '\t') else '', clean)
        guide_deck = json.loads(clean)

        if "slides" in guide_deck and len(guide_deck["slides"]) > 0:
            logger.info(f"Deck explicatif généré avec succès ({len(guide_deck['slides'])} diapositives)")
            return guide_deck
    except Exception as e_json:
        logger.error(f"Erreur parsing JSON deck explicatif : {e_json}\nRéponse brute : {raw_response[:300]}")

    # Fallback par défaut robuste
    return {
        "title": course_title,
        "subject_badge": theme["badge_default"],
        "overview": f"دليل توضيحي شامل ومركز لدرس {course_title}" if is_ar else f"Guide visuel explicatif complet pour le cours : {course_title}",
        "slides": [
            {
                "slide_num": 1,
                "badge": "🎯 الفكرة الأساسية" if is_ar else "🎯 Le Concept Fondamental",
                "title": course_title,
                "key_points": [
                    "فهم المبادئ الأساسية وتطبيقها في الحياة اليومية." if is_ar else "Comprendre les principes fondamentaux et leurs applications.",
                    "استيعاب القواعد الرياضية والفيزيائية المعتمدة." if is_ar else "Maîtriser les propriétés mathématiques et scientifiques clés."
                ],
                "highlight_box": {
                    "title": "القاعدة الأساسية" if is_ar else "La Règle Fondamentale",
                    "content": "التركيز على المعطيات والبرهان المنهجي الدقيق." if is_ar else "Bien identifier les hypothèses et rédiger avec rigueur."
                },
                "example_or_trap": {
                    "type": "tip",
                    "title": "نصيحة للامتحان" if is_ar else "Conseil d'Examen",
                    "content": "تأكد دائماً من صحة الوحدات والرموز قبل الإجابة." if is_ar else "Vérifiez toujours les unités et la cohérence de vos résultats."
                },
                "image_prompt": f"A clean vibrant educational infographics illustration for {course_title}, modern scientific diagram, 16:9 widescreen, highly detailed."
            }
        ],
    }


def generate_guide_slide_image(image_prompt: str, output_path: str, user_id: Optional[int] = None) -> bool:
    """
    Génère l'illustration / infographie de la diapositive via OpenRouter (google/gemini-2.5-flash-image)
    ou produit un visuel infographique élégant de secours.
    """
    from services.ai_engine import is_user_openrouter_allowed

    is_allowed = True if user_id is None else is_user_openrouter_allowed(user_id)
    key = get_openrouter_api_key() if is_allowed else None

    target = Path(output_path)
    target.parent.mkdir(parents=True, exist_ok=True)

    if key:
        try:
            safe_prompt = re.sub(r"\b(Adolf\s+Hitler|Hitler|Führer|Fuhrer)\b", "a historic leader", image_prompt, flags=re.IGNORECASE)
            safe_prompt = re.sub(r"\b(Nazi|Nazism)\b", "historical European", safe_prompt, flags=re.IGNORECASE)
            safe_prompt = re.sub(r"\b(Swastika)\b", "vintage geometric emblem", safe_prompt, flags=re.IGNORECASE)
            safe_prompt = re.sub(r"\b(weapons|guns|bombs)\b", "scientific instruments", safe_prompt, flags=re.IGNORECASE)

            payload = {
                "model": "google/gemini-2.5-flash-image",
                "messages": [{"role": "user", "content": safe_prompt}],
            }
            req = urllib.request.Request(
                "https://openrouter.ai/api/v1/chat/completions",
                headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
                data=json.dumps(payload).encode("utf-8"),
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=65) as resp:
                res_data = json.loads(resp.read().decode("utf-8"))

            msg = res_data.get("choices", [{}])[0].get("message", {})
            images = msg.get("images", [])

            if not images:
                clean_scenic = "A crisp, clean modern educational infographics illustration showing scientific equipment, geometric shapes and bright modern colors, 16:9 widescreen, highly detailed."
                payload["messages"] = [{"role": "user", "content": clean_scenic}]
                req_alt = urllib.request.Request(
                    "https://openrouter.ai/api/v1/chat/completions",
                    headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
                    data=json.dumps(payload).encode("utf-8"),
                    method="POST",
                )
                with urllib.request.urlopen(req_alt, timeout=65) as resp_alt:
                    res_alt = json.loads(resp_alt.read().decode("utf-8"))
                msg = res_alt.get("choices", [{}])[0].get("message", {})
                images = msg.get("images", [])

            if images and isinstance(images[0], dict):
                url = images[0].get("image_url", {}).get("url", "")
                if url:
                    raw_b64 = url.split(",")[1] if "," in url else url
                    target.write_bytes(base64.b64decode(raw_b64))
                    logger.info(f"Infographie IA diapositive générée avec succès : {output_path}")
                    return True
        except Exception as e_gen:
            logger.warning(f"Échec génération image IA OpenRouter guide ({e_gen}), utilisation du fallback graphique...")

    # Fallback visuel élégant avec carte d'infographie
    try:
        from PIL import Image, ImageDraw

        w, h = 1376, 768
        img = Image.new("RGB", (w, h), color="#0f172a")
        draw = ImageDraw.Draw(img)

        # Fond dégradé high-tech
        for y in range(h):
            r = int(15 + (y / h) * 15)
            g = int(23 + (y / h) * 25)
            b = int(42 + (y / h) * 40)
            draw.line([(0, y), (w, y)], fill=(r, g, b))

        margin = 40
        draw.rounded_rectangle(
            [(margin, margin), (w - margin, h - margin)],
            radius=20,
            outline="#334155",
            width=2,
        )

        draw.rounded_rectangle(
            [(margin + 20, margin + 20), (w - margin - 20, h - margin - 20)],
            radius=16,
            fill="#1e293b",
            outline="#38bdf8",
            width=2,
        )

        img.save(str(target), format="PNG")
        return True
    except Exception as e_pil:
        logger.error(f"Erreur fallback infographie PIL: {e_pil}")
        return False


def build_explanatory_guide_pdf_and_viewer(
    guide_deck: Dict[str, Any],
    course_id: int,
    subject: str,
    course_title: str,
    language: str = "ar",
    user_id: Optional[int] = None,
) -> Tuple[str, str]:
    """
    Étape 2 : Compile le Guide Visuel Explicatif complet :
    1. Génère les infographies pour chaque diapositive.
    2. Génère les pistes audio TTS avec Tashkeel complet.
    3. Compile le PDF haute résolution 16:9 (1376x768).
    4. Compile le lecteur interactif HTML moderne (style NotebookLM / Slideshow plein écran).
    Retourne (pdf_web_url, html_web_url).
    """
    base_static_dir = Path(__file__).parent.parent / "static" / "guides"
    guide_dir = base_static_dir / f"course_{course_id}"
    guide_dir.mkdir(parents=True, exist_ok=True)

    slides = guide_deck.get("slides", [])
    deck_title = guide_deck.get("title", course_title)
    is_ar = language == "ar"
    theme = detect_subject_theme(subject)

    slide_data: List[Dict[str, Any]] = []

    # 1. Génération des assets (Images + Audio) par diapositive
    for sl in slides:
        s_num = sl.get("slide_num", len(slide_data) + 1)
        s_badge = sl.get("badge", theme["badge_default"])
        s_title = sl.get("title", f"Diapositive {s_num}")
        s_kp = sl.get("key_points", [])
        s_hl = sl.get("highlight_box", {})
        s_ex = sl.get("example_or_trap", {})
        s_prompt = sl.get("image_prompt", f"Educational diagram explaining {s_title}")

        img_path = guide_dir / f"slide_{s_num}.png"
        if not img_path.exists() or img_path.stat().st_size < 10000:
            generate_guide_slide_image(s_prompt, str(img_path), user_id=user_id)

        # Synthèse vocale de la slide
        narration_text = f"{s_title}. " + " ".join(s_kp)
        if s_hl and s_hl.get("content"):
            narration_text += f" {s_hl.get('title', '')} : {s_hl.get('content', '')}"
        clean_text = clean_text_for_speech(narration_text)
        audio_uri = get_server_tts_audio_base64(clean_text, language=language) or ""

        slide_data.append({
            "num": s_num,
            "badge": s_badge,
            "title": s_title,
            "key_points": s_kp,
            "highlight_box": s_hl,
            "example_or_trap": s_ex,
            "img_rel_url": f"/static/guides/course_{course_id}/slide_{s_num}.png",
            "img_local_path": str(img_path),
            "audio_uri": audio_uri,
        })

    # 2. Construction du HTML imprimable pour Chromium (1376x768 paysage)
    pages_html = []
    total_slides = len(slide_data)

    for idx, sl in enumerate(slide_data):
        page_num = idx + 1
        points_list_html = "".join([f"<li>{pt}</li>" for pt in sl["key_points"]])

        # Encadré Formule / Règle d'or
        hl_html = ""
        if sl["highlight_box"] and sl["highlight_box"].get("content"):
            hl = sl["highlight_box"]
            hl_html = f"""
            <div class="formula-box">
                <div class="box-tag">⚡ {hl.get('title', 'LA RÈGLE CLÉ')}</div>
                <div class="box-body">{hl.get('content', '')}</div>
            </div>
            """

        # Encadré Exemple ou Piège
        ex_html = ""
        if sl["example_or_trap"] and sl["example_or_trap"].get("content"):
            ex = sl["example_or_trap"]
            ex_type = ex.get("type", "tip")
            is_trap = ex_type == "trap"
            tag_icon = "⚠️" if is_trap else "💡"
            tag_class = "trap-box" if is_trap else "example-box"
            fallback_title = "Attention au Piège" if is_trap else "Exemple d'examen"
            box_title = ex.get("title") or fallback_title
            ex_html = f"""
            <div class="{tag_class}">
                <div class="box-tag">{tag_icon} {box_title}</div>
                <div class="box-body">{ex.get('content', '')}</div>
            </div>
            """

        page_str = f"""
        <div class="page" id="page-{page_num}">
            <div class="page-topbar">
                <div class="top-badge">{theme['icon']} {sl['badge']}</div>
                <div class="top-title">{deck_title}</div>
                <div class="top-page-num">{page_num} / {total_slides}</div>
            </div>

            <div class="slide-body">
                <!-- Colonne Gauche : Explications et Cartes Pédagogiques -->
                <div class="slide-left">
                    <h2 class="slide-heading">{sl['title']}</h2>
                    
                    <div class="keypoints-card">
                        <ul class="points-list">
                            {points_list_html}
                        </ul>
                    </div>

                    {hl_html}

                    {ex_html}
                </div>

                <!-- Colonne Droite : Schéma & Illustration Visuelle -->
                <div class="slide-right">
                    <div class="image-wrapper">
                        <img src="{sl['img_rel_url']}" class="slide-img" alt="{sl['title']}">
                    </div>
                </div>
            </div>

            <div class="page-footer">
                <span>🏫 Plateforme Éducative École Adnane • {subject}</span>
                <span>💡 Guide Visuel & Présentation Pédagogique (Style NotebookLM)</span>
            </div>
        </div>
        """
        pages_html.append(page_str)

    # Style CSS moderne et percutant
    print_html_content = f"""<!DOCTYPE html>
<html lang="{language}" dir="{'rtl' if is_ar else 'ltr'}">
<head>
<meta charset="utf-8">
<title>{deck_title}</title>
<link href="https://fonts.googleapis.com/css2?family=Cairo:wght@600;700;800;900&family=Outfit:wght@500;600;700;800&family=Amiri:wght@400;700&display=swap" rel="stylesheet">
<style>
@page {{
    size: 1376px 768px;
    margin: 0;
}}
* {{
    box-sizing: border-box;
    -webkit-print-color-adjust: exact !important;
    print-color-adjust: exact !important;
}}
body {{
    margin: 0;
    padding: 0;
    background: #0f172a;
    font-family: {'"Cairo", "Amiri", serif' if is_ar else '"Outfit", sans-serif'};
}}
.page {{
    width: 1376px;
    height: 768px;
    page-break-after: always;
    padding: 24px 36px;
    display: flex;
    flex-direction: column;
    justify-content: space-between;
    background: #ffffff;
    border: 1px solid #e2e8f0;
    position: relative;
    overflow: hidden;
}}
.page-topbar {{
    display: flex;
    justify-content: space-between;
    align-items: center;
    border-bottom: 2px solid #f1f5f9;
    padding-bottom: 12px;
}}
.top-badge {{
    background: {theme['primary']};
    color: #ffffff;
    font-size: 13px;
    font-weight: 800;
    padding: 4px 16px;
    border-radius: 20px;
    letter-spacing: 0.5px;
    text-transform: uppercase;
}}
.top-title {{
    font-size: 15px;
    font-weight: 700;
    color: #475569;
}}
.top-page-num {{
    font-size: 14px;
    font-weight: 800;
    color: #94a3b8;
    background: #f8fafc;
    padding: 3px 12px;
    border-radius: 12px;
    border: 1px solid #e2e8f0;
}}
.slide-body {{
    flex: 1;
    display: grid;
    grid-template-columns: 1.15fr 0.85fr;
    gap: 32px;
    align-items: center;
    margin: 14px 0;
}}
.slide-left {{
    display: flex;
    flex-direction: column;
    gap: 12px;
}}
.slide-heading {{
    font-size: 25px;
    font-weight: 900;
    color: #0f172a;
    margin: 0 0 4px 0;
    line-height: 1.3;
}}
.keypoints-card {{
    background: #f8fafc;
    border: 1px solid #e2e8f0;
    border-left: 4px solid {theme['primary']};
    border-radius: 12px;
    padding: 12px 18px;
}}
html[dir="rtl"] .keypoints-card {{
    border-left: 1px solid #e2e8f0;
    border-right: 4px solid {theme['primary']};
}}
.points-list {{
    margin: 0;
    padding-{('right' if is_ar else 'left')}: 20px;
    font-size: 16.5px;
    line-height: 1.6;
    color: #334155;
    font-weight: 600;
}}
.points-list li {{
    margin-bottom: 6px;
}}
.points-list li:last-child {{
    margin-bottom: 0;
}}
.formula-box {{
    background: {theme['bg_card']};
    border: 2px solid {theme['border_card']};
    border-radius: 12px;
    padding: 12px 16px;
    box-shadow: 0 2px 8px rgba(0,0,0,0.03);
}}
.formula-box .box-tag {{
    font-size: 12px;
    font-weight: 800;
    color: {theme['primary']};
    margin-bottom: 4px;
    text-transform: uppercase;
    letter-spacing: 0.5px;
}}
.formula-box .box-body {{
    font-size: 18px;
    font-weight: 800;
    color: {theme['primary_dark']};
    line-height: 1.4;
}}
.example-box {{
    background: #f0fdf4;
    border: 1px solid #bbf7d0;
    border-radius: 10px;
    padding: 10px 14px;
}}
.example-box .box-tag {{
    font-size: 12px;
    font-weight: 800;
    color: #166534;
    margin-bottom: 3px;
}}
.example-box .box-body {{
    font-size: 15px;
    color: #15803d;
    line-height: 1.45;
    font-weight: 600;
}}
.trap-box {{
    background: #fef2f2;
    border: 1px solid #fecaca;
    border-radius: 10px;
    padding: 10px 14px;
}}
.trap-box .box-tag {{
    font-size: 12px;
    font-weight: 800;
    color: #991b1b;
    margin-bottom: 3px;
}}
.trap-box .box-body {{
    font-size: 15px;
    color: #b91c1c;
    line-height: 1.45;
    font-weight: 600;
}}
.slide-right {{
    display: flex;
    justify-content: center;
    align-items: center;
    height: 100%;
}}
.image-wrapper {{
    width: 100%;
    max-height: 520px;
    border-radius: 16px;
    overflow: hidden;
    box-shadow: 0 10px 30px rgba(0,0,0,0.12);
    border: 3px solid #ffffff;
    background: #f8fafc;
}}
.slide-img {{
    width: 100%;
    height: 100%;
    max-height: 520px;
    object-fit: cover;
    display: block;
}}
.page-footer {{
    display: flex;
    justify-content: space-between;
    align-items: center;
    border-top: 1px solid #f1f5f9;
    padding-top: 8px;
    font-size: 12.5px;
    color: #94a3b8;
    font-weight: 600;
}}
</style>
</head>
<body>
{"".join(pages_html)}
</body>
</html>"""

    html_file_path = base_static_dir / f"guide_course_{course_id}.html"
    html_file_path.write_text(print_html_content, encoding="utf-8")

    pdf_file_path = base_static_dir / f"guide_course_{course_id}.pdf"
    compiled_pdf = False

    # 3. Compilation en PDF haute résolution via Chromium Headless
    try:
        cmd = [
            "chromium-browser",
            "--headless",
            "--disable-gpu",
            "--no-sandbox",
            "--print-to-pdf-no-header",
            f"--print-to-pdf=/root/guide_course_{course_id}.pdf",
            f"https://ecole.code-xpert.net/static/guides/guide_course_{course_id}.html",
        ]
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        if res.returncode == 0 and os.path.exists(f"/root/guide_course_{course_id}.pdf"):
            os.system(f"cp /root/guide_course_{course_id}.pdf {pdf_file_path} && rm -f /root/guide_course_{course_id}.pdf")
            compiled_pdf = True
            logger.info("PDF guide explicatif généré avec succès via Chromium headless !")
    except Exception as e_chrom:
        logger.warning(f"Échec compilation PDF via Chromium ({e_chrom})")

    # Fallback Pillow si Chromium n'est pas dispo
    if not compiled_pdf:
        try:
            from PIL import Image

            pil_images = []
            for sl in slide_data:
                lp = sl.get("img_local_path")
                if lp and os.path.exists(lp):
                    im = Image.open(lp).convert("RGB")
                    pil_images.append(im)
            if pil_images:
                pil_images[0].save(
                    str(pdf_file_path),
                    save_all=True,
                    append_images=pil_images[1:],
                    resolution=100.0,
                )
                compiled_pdf = True
                logger.info("PDF guide explicatif généré via Pillow Image fallback !")
        except Exception as e_pil_pdf:
            logger.error(f"Échec compilation PDF Pillow: {e_pil_pdf}")

    # Sauvegarde persistante dans storage/ (sécurité anti-perte, archivage et sauvegardes ZIP)
    if pdf_file_path.exists():
        try:
            from services.downloader import get_user_storage_dir, STORAGE_DIR, LEGACY_COURSES_DIR
            storage_guides_dir = STORAGE_DIR / "guides"
            storage_guides_dir.mkdir(parents=True, exist_ok=True)
            shutil.copy2(pdf_file_path, storage_guides_dir / pdf_file_path.name)

            # Copie dans le dossier de cours de l'élève pour visibilité et sauvegarde personnelle
            if user_id is not None:
                u_dir = get_user_storage_dir(user_id)
                u_dir.mkdir(parents=True, exist_ok=True)
                shutil.copy2(pdf_file_path, u_dir / pdf_file_path.name)
            else:
                LEGACY_COURSES_DIR.mkdir(parents=True, exist_ok=True)
                shutil.copy2(pdf_file_path, LEGACY_COURSES_DIR / pdf_file_path.name)
            logger.info(f"PDF guide explicatif copié dans le stockage persistant ({storage_guides_dir})")
        except Exception as e_pers:
            logger.warning(f"Impossible de dupliquer le PDF guide vers storage: {e_pers}")

    # 4. Construction de la visionneuse interactive HTML plein écran (Slideshow moderne)
    interactive_html = build_interactive_guide_reader_html(
        guide_deck=guide_deck,
        slide_data=slide_data,
        course_id=course_id,
        subject=subject,
        course_title=course_title,
        language=language,
        theme=theme,
    )
    html_file_path.write_text(interactive_html, encoding="utf-8")

    pdf_url = f"/static/guides/guide_course_{course_id}.pdf"
    html_url = f"/static/guides/guide_course_{course_id}.html"

    return pdf_url, html_url


def build_interactive_guide_reader_html(
    guide_deck: Dict[str, Any],
    slide_data: List[Dict[str, Any]],
    course_id: int,
    subject: str,
    course_title: str,
    language: str,
    theme: Dict[str, str],
) -> str:
    """
    Construit l'application web de visionnage de diapositives autonome (style NotebookLM).
    Supporte la navigation plein écran, les touches du clavier (←/→), la lecture audio TTS,
    et le bouton direct de téléchargement du PDF.
    """
    is_ar = language == "ar"
    total_slides = len(slide_data)
    slides_json = json.dumps(slide_data, ensure_ascii=False)

    audio_btn_text = "استمع للشرح" if is_ar else "Écouter l'explication"
    pause_text = "إيقاف مؤقت" if is_ar else "Pause"
    fs_text = "ملء الشاشة" if is_ar else "Plein Écran"
    dl_pdf_text = "تحميل الـ PDF" if is_ar else "Télécharger le Guide PDF"
    prev_text = "السابق ❯" if is_ar else "❮ Précédent"
    next_text = "❮ التالي" if is_ar else "Suivant ❯"
    default_trap_title = "انتبه للخطأ" if is_ar else "Attention au Piège"
    default_ex_title = "نموذج امتحان" if is_ar else "Exemple d'Examen"
    deck_title = guide_deck.get("title", course_title)

    return f"""<!DOCTYPE html>
<html lang="{language}" dir="{'rtl' if is_ar else 'ltr'}">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{course_title} - Guide Visuel Explicatif</title>
<link href="https://fonts.googleapis.com/css2?family=Cairo:wght@600;700;800;900&family=Outfit:wght@500;600;700;800&family=Amiri:wght@400;700&display=swap" rel="stylesheet">
<style>
* {{
    box-sizing: border-box;
    margin: 0;
    padding: 0;
}}
body {{
    background: #090d16;
    color: #f8fafc;
    font-family: {'"Cairo", "Amiri", serif' if is_ar else '"Outfit", sans-serif'};
    min-height: 100vh;
    display: flex;
    flex-direction: column;
    overflow-x: hidden;
}}
.top-nav {{
    background: rgba(15, 23, 42, 0.9);
    backdrop-filter: blur(12px);
    border-bottom: 1px solid #1e293b;
    padding: 12px 24px;
    display: flex;
    justify-content: space-between;
    align-items: center;
    position: sticky;
    top: 0;
    z-index: 50;
}}
.brand-group {{
    display: flex;
    align-items: center;
    gap: 12px;
}}
.subject-pill {{
    background: {theme['primary']};
    color: #ffffff;
    font-size: 12px;
    font-weight: 800;
    padding: 4px 14px;
    border-radius: 20px;
    text-transform: uppercase;
    letter-spacing: 0.5px;
}}
.deck-title-nav {{
    font-size: 16px;
    font-weight: 700;
    color: #e2e8f0;
}}
.actions-group {{
    display: flex;
    align-items: center;
    gap: 10px;
}}
.btn-nav {{
    background: #1e293b;
    color: #f1f5f9;
    border: 1px solid #334155;
    padding: 8px 16px;
    border-radius: 10px;
    font-size: 13.5px;
    font-weight: 700;
    cursor: pointer;
    text-decoration: none;
    display: inline-flex;
    align-items: center;
    gap: 6px;
    transition: all 0.2s ease;
}}
.btn-nav:hover {{
    background: #334155;
    border-color: {theme['primary']};
    transform: translateY(-1px);
}}
.btn-primary-nav {{
    background: {theme['primary']};
    border-color: {theme['primary']};
    color: #ffffff;
}}
.btn-primary-nav:hover {{
    background: {theme['primary_dark']};
}}

.main-stage {{
    flex: 1;
    display: flex;
    justify-content: center;
    align-items: center;
    padding: 24px;
}}
.slide-frame {{
    width: 100%;
    max-width: 1280px;
    aspect-ratio: 16 / 9;
    background: #ffffff;
    color: #0f172a;
    border-radius: 20px;
    box-shadow: 0 25px 60px rgba(0,0,0,0.45);
    display: flex;
    flex-direction: column;
    justify-content: space-between;
    padding: 28px 40px;
    position: relative;
    overflow: hidden;
    animation: fadeIn 0.3s ease-in-out;
}}
@keyframes fadeIn {{
    from {{ opacity: 0; transform: scale(0.985); }}
    to {{ opacity: 1; transform: scale(1); }}
}}
.slide-header {{
    display: flex;
    justify-content: space-between;
    align-items: center;
    border-bottom: 2px solid #f1f5f9;
    padding-bottom: 12px;
}}
.slide-badge {{
    background: {theme['primary']};
    color: #ffffff;
    font-size: 13px;
    font-weight: 800;
    padding: 4px 16px;
    border-radius: 20px;
}}
.slide-counter {{
    font-size: 14px;
    font-weight: 800;
    color: #64748b;
    background: #f8fafc;
    padding: 4px 12px;
    border-radius: 12px;
    border: 1px solid #e2e8f0;
}}
.slide-content-grid {{
    flex: 1;
    display: grid;
    grid-template-columns: 1.15fr 0.85fr;
    gap: 32px;
    align-items: center;
    margin: 16px 0;
}}
.slide-left-col {{
    display: flex;
    flex-direction: column;
    gap: 14px;
}}
.slide-main-title {{
    font-size: 27px;
    font-weight: 900;
    color: #0f172a;
    line-height: 1.3;
}}
.keypoints-box {{
    background: #f8fafc;
    border: 1px solid #e2e8f0;
    border-left: 4px solid {theme['primary']};
    border-radius: 14px;
    padding: 14px 20px;
}}
html[dir="rtl"] .keypoints-box {{
    border-left: 1px solid #e2e8f0;
    border-right: 4px solid {theme['primary']};
}}
.keypoints-box ul {{
    margin: 0;
    padding-{('right' if is_ar else 'left')}: 20px;
    font-size: 17px;
    line-height: 1.6;
    color: #334155;
    font-weight: 600;
}}
.keypoints-box li {{
    margin-bottom: 6px;
}}
.highlight-card {{
    background: {theme['bg_card']};
    border: 2px solid {theme['border_card']};
    border-radius: 14px;
    padding: 14px 18px;
}}
.highlight-card .h-tag {{
    font-size: 12px;
    font-weight: 800;
    color: {theme['primary']};
    margin-bottom: 4px;
    text-transform: uppercase;
}}
.highlight-card .h-body {{
    font-size: 19px;
    font-weight: 800;
    color: {theme['primary_dark']};
    line-height: 1.4;
}}
.example-card {{
    background: #f0fdf4;
    border: 1px solid #bbf7d0;
    border-radius: 12px;
    padding: 12px 16px;
}}
.example-card .e-tag {{
    font-size: 12px;
    font-weight: 800;
    color: #166534;
    margin-bottom: 3px;
}}
.example-card .e-body {{
    font-size: 15.5px;
    color: #15803d;
    font-weight: 600;
    line-height: 1.45;
}}
.trap-card {{
    background: #fef2f2;
    border: 1px solid #fecaca;
    border-radius: 12px;
    padding: 12px 16px;
}}
.trap-card .t-tag {{
    font-size: 12px;
    font-weight: 800;
    color: #991b1b;
    margin-bottom: 3px;
}}
.trap-card .t-body {{
    font-size: 15.5px;
    color: #b91c1c;
    font-weight: 600;
    line-height: 1.45;
}}
.slide-right-col {{
    display: flex;
    justify-content: center;
    align-items: center;
    height: 100%;
}}
.img-container {{
    width: 100%;
    max-height: 480px;
    border-radius: 18px;
    overflow: hidden;
    box-shadow: 0 12px 32px rgba(0,0,0,0.14);
    border: 3px solid #ffffff;
    background: #f1f5f9;
}}
.img-container img {{
    width: 100%;
    height: 100%;
    max-height: 480px;
    object-fit: cover;
    display: block;
}}
.slide-footer {{
    display: flex;
    justify-content: space-between;
    align-items: center;
    border-top: 1px solid #f1f5f9;
    padding-top: 10px;
    font-size: 13px;
    color: #94a3b8;
    font-weight: 600;
}}

.bottom-controls {{
    background: rgba(15, 23, 42, 0.95);
    backdrop-filter: blur(12px);
    border-top: 1px solid #1e293b;
    padding: 14px 24px;
    display: flex;
    justify-content: center;
    align-items: center;
    gap: 16px;
    position: sticky;
    bottom: 0;
    z-index: 50;
}}
.btn-ctrl {{
    background: #1e293b;
    color: #f8fafc;
    border: 1px solid #334155;
    padding: 10px 22px;
    border-radius: 12px;
    font-size: 15px;
    font-weight: 700;
    cursor: pointer;
    display: inline-flex;
    align-items: center;
    gap: 8px;
    transition: all 0.2s ease;
}}
.btn-ctrl:hover:not(:disabled) {{
    background: {theme['primary']};
    border-color: {theme['primary']};
    transform: translateY(-2px);
}}
.btn-ctrl:disabled {{
    opacity: 0.4;
    cursor: not-allowed;
}}
.dots-indicator {{
    display: flex;
    gap: 8px;
    margin: 0 12px;
}}
.dot {{
    width: 10px;
    height: 10px;
    border-radius: 50%;
    background: #334155;
    cursor: pointer;
    transition: all 0.2s ease;
}}
.dot.active {{
    background: {theme['primary']};
    width: 24px;
    border-radius: 12px;
}}
</style>
</head>
<body>

<div class="top-nav">
    <div class="brand-group">
        <span class="subject-pill">{theme['icon']} {theme['badge_default']}</span>
        <span class="deck-title-nav">{deck_title}</span>
    </div>
    <div class="actions-group">
        <button class="btn-nav" id="btn-audio" onclick="toggleAudio()">🔊 {audio_btn_text}</button>
        <button class="btn-nav" onclick="toggleFullScreen()">⛶ {fs_text}</button>
        <a href="/static/guides/guide_course_{course_id}.pdf" class="btn-nav btn-primary-nav" download>📥 {dl_pdf_text}</a>
    </div>
</div>

<div class="main-stage">
    <div class="slide-frame" id="slide-container">
        <!-- Rendu dynamique par JavaScript -->
    </div>
</div>

<div class="bottom-controls">
    <button class="btn-ctrl" id="btn-prev" onclick="changeSlide(-1)">{prev_text}</button>
    <div class="dots-indicator" id="dots-container"></div>
    <button class="btn-ctrl" id="btn-next" onclick="changeSlide(1)">{next_text}</button>
</div>

<audio id="audio-player"></audio>

<script>
const slides = {slides_json};
let currentIndex = 0;
let isAudioPlaying = false;
const audioPlayer = document.getElementById("audio-player");

function renderSlide(index) {{
    const sl = slides[index];
    const total = slides.length;
    const container = document.getElementById("slide-container");

    let pointsHtml = "";
    if (sl.key_points) {{
        pointsHtml = sl.key_points.map(p => `<li>${{p}}</li>`).join("");
    }}

    let hlHtml = "";
    if (sl.highlight_box && sl.highlight_box.content) {{
        hlHtml = `
        <div class="highlight-card">
            <div class="h-tag">⚡ ${{sl.highlight_box.title || 'LA RÈGLE FONDAMENTALE'}}</div>
            <div class="h-body">${{sl.highlight_box.content}}</div>
        </div>
        `;
    }}

    let exHtml = "";
    if (sl.example_or_trap && sl.example_or_trap.content) {{
        const isTrap = sl.example_or_trap.type === "trap";
        const cardClass = isTrap ? "trap-card" : "example-card";
        const tagClass = isTrap ? "t-tag" : "e-tag";
        const bodyClass = isTrap ? "t-body" : "e-body";
        const icon = isTrap ? "⚠️" : "💡";
        const defaultBoxTitle = isTrap ? "{default_trap_title}" : "{default_ex_title}";
        exHtml = `
        <div class="${{cardClass}}">
            <div class="${{tagClass}}">${{icon}} ${{sl.example_or_trap.title || defaultBoxTitle}}</div>
            <div class="${{bodyClass}}">${{sl.example_or_trap.content}}</div>
        </div>
        `;
    }}

    container.innerHTML = `
        <div class="slide-header">
            <div class="slide-badge">${{sl.badge || '{theme['badge_default']}'}}</div>
            <div class="slide-counter">${{index + 1}} / ${{total}}</div>
        </div>

        <div class="slide-content-grid">
            <div class="slide-left-col">
                <h2 class="slide-main-title">${{sl.title}}</h2>
                <div class="keypoints-box">
                    <ul>${{pointsHtml}}</ul>
                </div>
                ${{hlHtml}}
                ${{exHtml}}
            </div>

            <div class="slide-right-col">
                <div class="img-container">
                    <img src="${{sl.img_rel_url}}" alt="${{sl.title}}">
                </div>
            </div>
        </div>

        <div class="slide-footer">
            <span>🏫 Plateforme Éducative École Adnane • {subject}</span>
            <span>💡 Guide Visuel & Présentation Pédagogique (Style NotebookLM)</span>
        </div>
    `;

    document.getElementById("btn-prev").disabled = (index === 0);
    document.getElementById("btn-next").disabled = (index === total - 1);

    updateDots();

    // Arrête l'audio précédent
    audioPlayer.pause();
    isAudioPlaying = false;
    document.getElementById("btn-audio").innerText = "🔊 " + "{audio_btn_text}";
}}

function updateDots() {{
    const container = document.getElementById("dots-container");
    container.innerHTML = "";
    slides.forEach((_, idx) => {{
        const d = document.createElement("div");
        d.className = "dot" + (idx === currentIndex ? " active" : "");
        d.onclick = () => goToSlide(idx);
        container.appendChild(d);
    }});
}}

function changeSlide(direction) {{
    const nextIdx = currentIndex + direction;
    if (nextIdx >= 0 && nextIdx < slides.length) {{
        currentIndex = nextIdx;
        renderSlide(currentIndex);
    }}
}}

function goToSlide(index) {{
    currentIndex = index;
    renderSlide(currentIndex);
}}

function toggleAudio() {{
    const sl = slides[currentIndex];
    const btn = document.getElementById("btn-audio");
    if (!sl.audio_uri) return;

    if (isAudioPlaying) {{
        audioPlayer.pause();
        isAudioPlaying = false;
        btn.innerText = "🔊 " + "{audio_btn_text}";
    }} else {{
        audioPlayer.src = sl.audio_uri;
        audioPlayer.play();
        isAudioPlaying = true;
        btn.innerText = "⏸️ " + "{pause_text}";
    }}
}}

audioPlayer.onended = () => {{
    isAudioPlaying = false;
    document.getElementById("btn-audio").innerText = "🔊 " + "{audio_btn_text}";
}};

function toggleFullScreen() {{
    if (!document.fullscreenElement) {{
        document.documentElement.requestFullscreen();
    }} else {{
        if (document.exitFullscreen) {{
            document.exitFullscreen();
        }}
    }}
}}

// Navigation clavier (Flèches gauche et droite)
document.addEventListener("keydown", (e) => {{
    if (e.key === "ArrowRight") {{
        {"changeSlide(-1)" if is_ar else "changeSlide(1)"};
    }} else if (e.key === "ArrowLeft") {{
        {"changeSlide(1)" if is_ar else "changeSlide(-1)"};
    }}
}});

// Initialisation
renderSlide(0);
</script>

</body>
</html>"""


def generate_complete_explanatory_guide(
    course_id: int,
    course_text: str,
    subject: str,
    course_title: str,
    language: str = "ar",
    user_id: Optional[int] = None,
) -> Tuple[str, str]:
    """
    Exécute en 1 clic le pipeline complet du Guide Visuel Explicatif :
    1. Conception didactique du deck (scénario pédagogique structuré en slides 16:9).
    2. Enregistrement en base de données.
    3. Génération des infographies IA et de l'audio.
    4. Compilation du PDF haute résolution (1376x768) et de la visionneuse interactive HTML.
    5. Sauvegarde de l'URL du PDF en base.
    Retourne (pdf_web_url, html_web_url).
    """
    from models.database import save_course_explanatory_guide, save_course_explanatory_guide_pdf

    deck = generate_course_explanatory_guide_deck(
        course_text=course_text,
        subject=subject,
        course_title=course_title,
        language=language,
        user_id=user_id,
    )
    save_course_explanatory_guide(course_id, deck)

    pdf_url, html_url = build_explanatory_guide_pdf_and_viewer(
        guide_deck=deck,
        course_id=course_id,
        subject=subject,
        course_title=course_title,
        language=language,
        user_id=user_id,
    )
    save_course_explanatory_guide_pdf(course_id, pdf_url)

    return pdf_url, html_url
