"""
Module de génération de Contes et Histoires Illustrées Pédagogiques pour enfants (Livre Jeunesse & PDF).
Découpe les cours en récits captivants façon albums jeunesse (comme 'The Brave Travelers and the City of Fez'
et 'L'Enquête du Feu'), génère les illustrations artistiques à l'aquarelle par IA, la narration vocale
avec Tashkeel complet, et compile le livre complet en PDF téléchargeable (1376x768).
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


def generate_course_story_scenario(
    course_text: str,
    subject: str,
    course_title: str,
    language: str = "ar",
    user_id: Optional[int] = None,
) -> Dict[str, Any]:
    """
    Étape 1 : Demande à l'IA de concevoir un scénario de conte pédagogique pour enfants.
    Transforme la leçon en une histoire vivante, découpée en 4 à 5 scènes captivantes,
    avec narration adaptée aux enfants, Tashkeel complet pour l'arabe, et prompts d'illustrations.
    """
    from services.ai_engine import call_llm, call_openrouter_chat_completion, is_user_openrouter_allowed

    truncated_text = (course_text or "")[:6000].strip()
    is_ar = language == "ar"
    is_en = language == "en"

    lang_instr = (
        "Tout le récit ('title', 'synopsis', 'scenes.title', 'scenes.narration', 'scenes.did_you_know') "
        "DOIT être en ARABE de haute tenue littéraire avec TASHKEEL COMPLET (diacritiques voyellés sur chaque mot) "
        "pour permettre une diction orale impeccable et une lecture captivante pour un enfant."
        if is_ar
        else (
            "All story content MUST be in ENGLISH written in an engaging, warm children's book style."
            if is_en
            else "Tout le récit ('title', 'synopsis', 'scenes.title', 'scenes.narration', 'scenes.did_you_know') "
            "DOIT être en FRANÇAIS chaleureux, captivant et poétique, rédigé comme un livre de conte jeunesse."
        )
    )

    prompt = f"""Tu es un auteur d'élite de littérature jeunesse et d'albums illustrés pour enfants (dans l'esprit de "The Brave Travelers and the City of Fez" et "L'Enquête du Feu").

MISSION :
Transforme la leçon suivante en un CONTE NARRATIF CAPTIVANT pour des collégiens de 14 ans / enfants :
- Matière : {subject}
- Titre du cours : {course_title}
- Langue : {language}

CONTENU DU COURS :
\"\"\"
{truncated_text}
\"\"\"

CONSIGNES PÉDAGOGIQUES :
1. {lang_instr}
2. Si le cours est d'Histoire ou Géographie : Raconte les événements comme une épopée humaine et une aventure vivante, avec des métaphores simples, des décors immersifs et des personnages marquants (sans jargon rébarbatif).
3. Si le cours est de Sciences : Raconte une enquête policière ou une quête imaginaire où les éléments sont personnifiés (ex: les atomes, le feu, les électrons).
4. Découpe l'histoire en exactement 4 à 5 scènes chronologiques progressives.
5. Pour chaque scène :
   - "scene_num" : entier (1, 2, 3...)
   - "title" : titre court et évocateur de la scène
   - "narration" : texte du conte (3 à 5 phrases riches, immersives et imagées, racontées à l'enfant avec Tashkeel complet si arabe)
   - "did_you_know" : une leçon clé à retenir ou morale historique/scientifique simplifiée (1 phrase percutante)
   - "image_prompt" : prompt en ANGLAIS ultra-détaillé pour générer une illustration féerique à l'aquarelle pour livre jeunesse (16:9 widescreen, fairytale storybook watercolor style, warm lighting, soft detailed watercolor art, cinematic composition, highly detailed).

RÉPONDS STRICTEMENT SOUS FORME D'UN OBJET JSON VALIDE SANS TEXTE AVANT NI APRÈS :
{{
  "title": "titre du livre de conte",
  "synopsis": "résumé captivant de l'histoire en 2 phrases",
  "scenes": [
    {{
      "scene_num": 1,
      "title": "titre de la scène 1",
      "narration": "récit de la scène 1...",
      "did_you_know": "l'essentiel à retenir...",
      "image_prompt": "A stunning fairytale children storybook watercolor illustration for a lesson: ... 16:9 widescreen, soft warm watercolor style, highly detailed."
    }}
  ]
}}
"""

    system_instruction = (
        "Tu es un auteur international de livres de contes et d'albums illustrés pour enfants. "
        "Tu réponds EXCLUSIVEMENT en JSON valide rigoureusement formaté."
    )

    is_or_allowed = is_user_openrouter_allowed(user_id)
    openrouter_key = get_openrouter_api_key() if is_or_allowed else None

    raw_json = ""
    if openrouter_key:
        try:
            messages = [
                {"role": "system", "content": system_instruction},
                {"role": "user", "content": prompt},
            ]
            raw_json = call_openrouter_chat_completion(
                messages=messages,
                api_key=openrouter_key,
                temperature=0.3,
                max_tokens=4000,
            )
        except Exception as e_or:
            logger.warning(f"Échec OpenRouter scénario ({e_or}), repli sur LLM standard...")

    if not raw_json:
        raw_json = call_llm(
            prompt=prompt,
            system_instruction=system_instruction,
            temperature=0.3,
            user_id=user_id,
        )

    # Nettoyage Markdown ```json ... ```
    cleaned = raw_json.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r"\s*```$", "", cleaned)

    try:
        data = json.loads(cleaned)
        if isinstance(data, dict) and "scenes" in data and len(data["scenes"]) > 0:
            return data
    except Exception as e_parse:
        logger.error(f"Erreur parsing JSON scénario ({e_parse}). Tentative extraction par regex...")
        match = re.search(r"\{[\s\S]*\}", cleaned)
        if match:
            try:
                data = json.loads(match.group(0))
                if isinstance(data, dict) and "scenes" in data:
                    return data
            except Exception:
                pass

    # Fallback scénario minimaliste si échec parsing
    return {
        "title": course_title,
        "synopsis": f"حكاية تعليمية مشوقة لشرح درس {course_title} بأسلوب مبسط وممتع للأطفال." if is_ar else f"Une histoire captivante pour comprendre la leçon : {course_title}.",
        "scenes": [
            {
                "scene_num": 1,
                "title": "البداية" if is_ar else "Le Début de l'Aventure",
                "narration": f"في يوم من الأيام، بدأت أحداث درس {course_title} لتكشف لنا أسراراً وتفاصيل مدهشة..." if is_ar else f"Il était une fois, l'histoire de {course_title} commença pour nous révéler des secrets fascinants...",
                "did_you_know": "كل درس في التاريخ أو العلوم يحمل قصة شيقة وراءه." if is_ar else "Chaque leçon d'histoire ou de science cache une formidable histoire.",
                "image_prompt": f"A beautiful fairytale children storybook watercolor illustration for: {course_title}, warm watercolor tones, 16:9 widescreen.",
            }
        ],
    }


def generate_scene_illustration(image_prompt: str, output_path: str, user_id: Optional[int] = None) -> bool:
    """
    Génère l'illustration d'une scène à l'aquarelle via OpenRouter (google/gemini-2.5-flash-image)
    ou produit une carte visuelle élégante de secours en cas d'indisponibilité.
    """
    from services.ai_engine import is_user_openrouter_allowed

    is_allowed = is_user_openrouter_allowed(user_id)
    key = get_openrouter_api_key() if is_allowed else None

    target = Path(output_path)
    target.parent.mkdir(parents=True, exist_ok=True)

    if key:
        try:
            payload = {
                "model": "google/gemini-2.5-flash-image",
                "messages": [{"role": "user", "content": image_prompt}],
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
            if images and isinstance(images[0], dict):
                url = images[0].get("image_url", {}).get("url", "")
                if url:
                    raw_b64 = url.split(",")[1] if "," in url else url
                    target.write_bytes(base64.b64decode(raw_b64))
                    logger.info(f"Illustration IA générée avec succès : {output_path}")
                    return True
        except Exception as e_gen:
            logger.warning(f"Échec génération image IA OpenRouter ({e_gen}), utilisation de l'illustration graphique...")

    # Fallback Pillow élégant avec textures aquarelle
    try:
        from PIL import Image, ImageDraw

        w, h = 1376, 768
        img = Image.new("RGB", (w, h), color="#fbf8f2")
        draw = ImageDraw.Draw(img)

        # Fond dégradé doux façon aquarelle
        for y in range(h):
            r = int(251 - (y / h) * 12)
            g = int(248 - (y / h) * 16)
            b = int(242 - (y / h) * 20)
            draw.line([(0, y), (w, y)], fill=(r, g, b))

        margin = 40
        draw.rounded_rectangle(
            [(margin, margin), (w - margin, h - margin)],
            radius=24,
            outline="#e2d9cc",
            width=3,
        )

        draw.rounded_rectangle(
            [(margin + 30, margin + 30), (w - margin - 30, h - margin - 30)],
            radius=18,
            fill="#f5efe6",
            outline="#d5c8b5",
            width=2,
        )

        img.save(str(target), format="PNG")
        return True
    except Exception as e_pil:
        logger.error(f"Erreur fallback image PIL: {e_pil}")
        return False


def build_story_pdf_and_viewer(
    scenario: Dict[str, Any],
    course_id: int,
    subject: str,
    course_title: str,
    language: str = "ar",
    user_id: Optional[int] = None,
) -> Tuple[str, str]:
    """
    Étape 2 : Compile le livre de conte complet :
    1. Génère les illustrations artistiques pour chaque scène.
    2. Génère les pistes audio TTS avec Tashkeel complet.
    3. Compile le livre au format PDF haute résolution (1376x768).
    4. Compile le lecteur interactif HTML avec tournage de page et son.
    Retourne (pdf_web_url, html_web_url).
    """
    base_static_dir = Path(__file__).parent.parent / "static" / "stories"
    story_dir = base_static_dir / f"course_{course_id}"
    story_dir.mkdir(parents=True, exist_ok=True)

    scenes = scenario.get("scenes", [])
    story_title = scenario.get("title", course_title)
    is_ar = language == "ar"

    scene_data: List[Dict[str, Any]] = []

    # 1. Génération des assets (Images + Audio) par scène
    for sc in scenes:
        s_num = sc.get("scene_num", len(scene_data) + 1)
        s_title = sc.get("title", f"Scène {s_num}")
        s_narr = sc.get("narration", "")
        s_dyk = sc.get("did_you_know", "")
        s_prompt = sc.get("image_prompt", f"Watercolor illustration for {s_title}")

        img_path = story_dir / f"scene_{s_num}.png"
        if not img_path.exists():
            generate_scene_illustration(s_prompt, str(img_path), user_id=user_id)

        clean_narr = clean_text_for_speech(s_narr)
        audio_uri = get_server_tts_audio_base64(clean_narr, language=language) or ""

        scene_data.append({
            "num": s_num,
            "title": s_title,
            "narration": s_narr,
            "did_you_know": s_dyk,
            "img_rel_url": f"/static/stories/course_{course_id}/scene_{s_num}.png",
            "img_local_path": str(img_path),
            "audio_uri": audio_uri,
        })

    pages_html = []
    for sc in scene_data:
        moral_html = ""
        if sc.get("did_you_know"):
            m_label = "العبرة من القصة :" if is_ar else "À retenir :"
            m_text = html_escape(sc["did_you_know"])
            moral_html = f'<div class="takeaway-box"><span class="takeaway-icon">💡</span><div class="takeaway-text"><strong>{m_label}</strong> {m_text}</div></div>'

        pages_html.append(f"""
<div class="page" dir="{'rtl' if is_ar else 'ltr'}">
    <div class="page-header">
        <span class="book-badge">📖 {html_escape(subject)} • #3AC</span>
        <span class="page-num">{sc['num']:02d} / {len(scene_data):02d}</span>
    </div>

    <div class="story-content">
        <h2 class="chapter-title">✦ {html_escape(sc['title'])} ✦</h2>
        <p class="story-narration">{html_escape(sc['narration'])}</p>
    </div>

    <div class="illustration-container">
        <img class="story-image" src="{sc['img_rel_url']}" alt="{html_escape(sc['title'])}">
    </div>

    {moral_html}
</div>
""")

    print_html_content = f"""<!DOCTYPE html>
<html lang="{language}" dir="{'rtl' if is_ar else 'ltr'}">
<head>
<meta charset="utf-8">
<title>{html_escape(story_title)}</title>
<link href="https://fonts.googleapis.com/css2?family=Cairo:wght@400;600;700;800&family=Playfair+Display:ital,wght@0,600;1,600&display=swap" rel="stylesheet">
<style>
@page {{
    size: 1376px 768px;
    margin: 0;
}}
* {{
    box-sizing: border-box;
}}
body {{
    margin: 0;
    padding: 0;
    background: #fdfbf7;
    font-family: 'Cairo', 'Playfair Display', system-ui, sans-serif;
    color: #1e293b;
    -webkit-print-color-adjust: exact;
    print-color-adjust: exact;
}}
.page {{
    width: 1376px;
    height: 768px;
    page-break-after: always;
    padding: 30px 48px;
    display: flex;
    flex-direction: column;
    justify-content: space-between;
    background: #fbf8f2;
    border: 1px solid #e8e0d4;
    position: relative;
    overflow: hidden;
}}
.page-header {{
    display: flex;
    justify-content: space-between;
    align-items: center;
    border-bottom: 2px solid #ecd8c2;
    padding-bottom: 8px;
}}
.book-badge {{
    background: #e28743;
    color: #ffffff;
    font-size: 14px;
    font-weight: 700;
    padding: 4px 14px;
    border-radius: 20px;
    letter-spacing: 0.5px;
}}
.page-num {{
    font-size: 15px;
    font-weight: 700;
    color: #8c7862;
}}
.story-content {{
    text-align: center;
    margin: 8px 0;
}}
.chapter-title {{
    font-size: 26px;
    font-weight: 800;
    color: #1e293b;
    margin: 0 0 8px 0;
}}
.story-narration {{
    font-size: 20px;
    line-height: 1.6;
    color: #334155;
    max-width: 1100px;
    margin: 0 auto;
    font-weight: 600;
}}
.illustration-container {{
    flex: 1;
    display: flex;
    justify-content: center;
    align-items: center;
    margin: 6px 0;
    overflow: hidden;
}}
.story-image {{
    max-height: 420px;
    max-width: 900px;
    border-radius: 16px;
    box-shadow: 0 8px 24px rgba(0,0,0,0.12);
    object-fit: cover;
    border: 3px solid #ffffff;
}}
.takeaway-box {{
    background: #f0fdf4;
    border: 1px solid #bbf7d0;
    border-radius: 12px;
    padding: 8px 16px;
    display: flex;
    align-items: center;
    gap: 10px;
    font-size: 15px;
    color: #166534;
    max-width: 1100px;
    margin: 0 auto;
}}
.takeaway-icon {{
    font-size: 20px;
}}
</style>
</head>
<body>
{"".join(pages_html)}
</body>
</html>"""

    html_file_path = base_static_dir / f"story_course_{course_id}.html"
    html_file_path.write_text(print_html_content, encoding="utf-8")

    pdf_file_path = base_static_dir / f"story_course_{course_id}.pdf"
    compiled_pdf = False

    try:
        cmd = [
            "chromium-browser",
            "--headless",
            "--disable-gpu",
            "--no-sandbox",
            "--print-to-pdf-no-header",
            f"--print-to-pdf=/root/story_course_{course_id}.pdf",
            f"https://ecole.code-xpert.net/static/stories/story_course_{course_id}.html",
        ]
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        if res.returncode == 0 and os.path.exists(f"/root/story_course_{course_id}.pdf"):
            os.system(f"cp /root/story_course_{course_id}.pdf {pdf_file_path} && rm -f /root/story_course_{course_id}.pdf")
            compiled_pdf = True
            logger.info("PDF histoire généré avec succès via Chromium headless !")
    except Exception as e_chrom:
        logger.warning(f"Échec compilation PDF via Chromium ({e_chrom})")

    if not compiled_pdf:
        try:
            from PIL import Image

            pil_images = []
            for sc in scene_data:
                lp = sc.get("img_local_path")
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
                logger.info("PDF histoire généré avec succès via Pillow Image compilation !")
        except Exception as e_pil_pdf:
            logger.error(f"Échec compilation PDF Pillow: {e_pil_pdf}")

    interactive_html = build_interactive_story_reader_html(
        scenario=scenario,
        scene_data=scene_data,
        course_id=course_id,
        subject=subject,
        course_title=course_title,
        language=language,
    )
    html_file_path.write_text(interactive_html, encoding="utf-8")

    pdf_url = f"/static/stories/story_course_{course_id}.pdf"
    html_url = f"/static/stories/story_course_{course_id}.html"

    return pdf_url, html_url


def build_interactive_story_reader_html(
    scenario: Dict[str, Any],
    scene_data: List[Dict[str, Any]],
    course_id: int,
    subject: str,
    course_title: str,
    language: str = "ar",
) -> str:
    """Génère l'application Web autonome de lecture de l'album illustré avec audio et téléchargement PDF."""
    is_ar = language == "ar"
    story_title = scenario.get("title", course_title)

    slides_divs = []
    audio_tags = []

    for idx, sc in enumerate(scene_data):
        active_cls = " active" if idx == 0 else ""
        moral_box = ""
        if sc.get("did_you_know"):
            m_label = "العبرة من القصة :" if is_ar else "À retenir :"
            m_val = html_escape(sc["did_you_know"])
            moral_box = f'<div class="moral-box"><span class="moral-icon">💡</span><div class="moral-content"><strong>{m_label}</strong> {m_val}</div></div>'

        listen_btn_text = "استمع للحكاية بصوت المعلم" if is_ar else "Écouter le récit"

        slides_divs.append(f"""
        <div class="story-slide{active_cls}" data-index="{idx}">
            <div class="slide-header">
                <span class="chapter-badge">✦ {'الفصل' if is_ar else 'Chapitre'} {sc['num']} : {html_escape(sc['title'])} ✦</span>
                <span class="slide-counter">{idx + 1} / {len(scene_data)}</span>
            </div>

            <div class="slide-body">
                <div class="image-frame">
                    <img src="{sc['img_rel_url']}" alt="{html_escape(sc['title'])}" class="story-art">
                </div>

                <div class="text-panel">
                    <p class="narration-text">{html_escape(sc['narration'])}</p>
                    {moral_box}
                    <div class="narration-action">
                        <button class="listen-btn" onclick="playSceneAudio({idx})" id="listen-btn-{idx}">
                            🔊 {listen_btn_text}
                        </button>
                    </div>
                </div>
            </div>
        </div>
""")
        if sc.get("audio_uri"):
            audio_tags.append(
                f'<audio id="story_audio_{idx}" class="story-audio-track" preload="auto" src="{sc["audio_uri"]}"></audio>'
            )

    return f"""<!DOCTYPE html>
<html lang="{language}" dir="{'rtl' if is_ar else 'ltr'}">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{html_escape(story_title)}</title>
<link href="https://fonts.googleapis.com/css2?family=Cairo:wght@400;600;700;800;900&family=Playfair+Display:ital,wght@0,600;1,600&display=swap" rel="stylesheet">
<style>
* {{
    box-sizing: border-box;
    margin: 0;
    padding: 0;
}}
body {{
    background: #0f172a;
    font-family: 'Cairo', system-ui, sans-serif;
    color: #f8fafc;
    min-height: 100vh;
    display: flex;
    flex-direction: column;
    justify-content: space-between;
}}
.top-nav {{
    background: rgba(15, 23, 42, 0.9);
    backdrop-filter: blur(12px);
    border-bottom: 1px solid rgba(255, 255, 255, 0.1);
    padding: 14px 28px;
    display: flex;
    justify-content: space-between;
    align-items: center;
    position: sticky;
    top: 0;
    z-index: 100;
}}
.nav-title-group {{
    display: flex;
    align-items: center;
    gap: 12px;
}}
.badge-tag {{
    background: #2563eb;
    color: #ffffff;
    font-size: 13px;
    font-weight: 700;
    padding: 4px 12px;
    border-radius: 14px;
}}
.story-main-title {{
    font-size: 18px;
    font-weight: 800;
    color: #f1f5f9;
}}
.nav-actions {{
    display: flex;
    gap: 10px;
}}
.action-btn {{
    background: rgba(255, 255, 255, 0.1);
    color: #f8fafc;
    border: 1px solid rgba(255, 255, 255, 0.2);
    padding: 8px 16px;
    border-radius: 20px;
    font-size: 13px;
    font-weight: 700;
    cursor: pointer;
    text-decoration: none;
    display: flex;
    align-items: center;
    gap: 6px;
    transition: all 0.2s ease;
}}
.action-btn:hover {{
    background: #2563eb;
    color: #ffffff;
    border-color: #2563eb;
    transform: translateY(-2px);
}}
.btn-pdf {{
    background: #059669;
    border-color: #059669;
}}
.btn-pdf:hover {{
    background: #10b981;
    border-color: #10b981;
}}
.storybook-stage {{
    flex: 1;
    display: flex;
    align-items: center;
    justify-content: center;
    padding: 24px 20px;
}}
.stage-container {{
    width: 100%;
    max-width: 1300px;
    background: #fdfbf7;
    color: #1e293b;
    border-radius: 24px;
    box-shadow: 0 20px 50px rgba(0, 0, 0, 0.5);
    overflow: hidden;
    position: relative;
    border: 3px solid #e2d9cc;
}}
.story-slide {{
    display: none;
    padding: 32px 40px;
    animation: fadeIn 0.4s ease-out;
}}
.story-slide.active {{
    display: block;
}}
@keyframes fadeIn {{
    from {{ opacity: 0; transform: scale(0.98); }}
    to {{ opacity: 1; transform: scale(1); }}
}}
.slide-header {{
    display: flex;
    justify-content: space-between;
    align-items: center;
    border-bottom: 2px solid #ecd8c2;
    padding-bottom: 12px;
    margin-bottom: 24px;
}}
.chapter-badge {{
    font-size: 22px;
    font-weight: 800;
    color: #b45309;
}}
.slide-counter {{
    font-size: 15px;
    font-weight: 700;
    color: #8c7862;
    background: #f3ece1;
    padding: 4px 12px;
    border-radius: 12px;
}}
.slide-body {{
    display: flex;
    gap: 36px;
    align-items: center;
}}
.image-frame {{
    flex: 1.1;
    border-radius: 18px;
    overflow: hidden;
    box-shadow: 0 10px 25px rgba(0, 0, 0, 0.15);
    border: 4px solid #ffffff;
    background: #f3ece1;
    display: flex;
    justify-content: center;
    align-items: center;
}}
.story-art {{
    width: 100%;
    height: 420px;
    object-fit: cover;
    display: block;
}}
.text-panel {{
    flex: 1;
    display: flex;
    flex-direction: column;
    justify-content: space-between;
    gap: 20px;
}}
.narration-text {{
    font-size: 22px;
    line-height: 1.7;
    font-weight: 600;
    color: #1e293b;
}}
.moral-box {{
    background: #f0fdf4;
    border: 1px solid #86efac;
    border-radius: 14px;
    padding: 12px 18px;
    display: flex;
    gap: 10px;
    align-items: flex-start;
    font-size: 15px;
    color: #166534;
}}
.moral-icon {{
    font-size: 22px;
}}
.listen-btn {{
    background: #2563eb;
    color: #ffffff;
    border: none;
    padding: 12px 24px;
    border-radius: 16px;
    font-size: 16px;
    font-weight: 700;
    cursor: pointer;
    display: inline-flex;
    align-items: center;
    gap: 10px;
    box-shadow: 0 4px 14px rgba(37, 99, 235, 0.35);
    transition: all 0.2s ease;
}}
.listen-btn:hover {{
    background: #1d4ed8;
    transform: translateY(-2px);
}}
.listen-btn.is-playing {{
    background: #dc2626;
    animation: pulse 1.5s infinite;
}}
@keyframes pulse {{
    0% {{ box-shadow: 0 0 0 0 rgba(220, 38, 38, 0.6); }}
    70% {{ box-shadow: 0 0 0 14px rgba(220, 38, 38, 0); }}
    100% {{ box-shadow: 0 0 0 0 rgba(220, 38, 38, 0); }}
}}
.bottom-controls {{
    background: rgba(15, 23, 42, 0.95);
    border-top: 1px solid rgba(255, 255, 255, 0.1);
    padding: 16px 28px;
    display: flex;
    justify-content: space-between;
    align-items: center;
}}
.nav-arrow-btn {{
    background: #334155;
    color: #f8fafc;
    border: none;
    padding: 10px 22px;
    border-radius: 20px;
    font-size: 15px;
    font-weight: 700;
    cursor: pointer;
    transition: all 0.2s;
}}
.nav-arrow-btn:hover:not(:disabled) {{
    background: #2563eb;
}}
.nav-arrow-btn:disabled {{
    opacity: 0.4;
    cursor: not-allowed;
}}
.dots-container {{
    display: flex;
    gap: 8px;
}}
.dot-btn {{
    width: 14px;
    height: 14px;
    border-radius: 50%;
    border: none;
    background: #475569;
    cursor: pointer;
    transition: all 0.2s;
}}
.dot-btn.active {{
    background: #38bdf8;
    transform: scale(1.3);
}}
</style>
</head>
<body>

<div class="top-nav">
    <div class="nav-title-group">
        <span class="badge-tag">📖 {html_escape(subject)}</span>
        <h1 class="story-main-title">{html_escape(story_title)}</h1>
    </div>
    <div class="nav-actions">
        <a href="/static/stories/story_course_{course_id}.pdf" target="_blank" class="action-btn btn-pdf" download>
            📥 {'تحميل كتاب القصة PDF' if is_ar else 'Télécharger le Livre PDF'}
        </a>
        <button class="action-btn" onclick="toggleFullscreen()">
            ⛶ {'ملء الشاشة' if is_ar else 'Plein écran'}
        </button>
    </div>
</div>

<div class="storybook-stage">
    <div class="stage-container">
        {"".join(slides_divs)}
    </div>
</div>

<div class="bottom-controls">
    <button class="nav-arrow-btn" id="prev-btn" onclick="changeSlide(-1)">
        {'▶ الشريحة السابقة' if is_ar else '◀ Précédent'}
    </button>
    <div class="dots-container" id="dots-box"></div>
    <button class="nav-arrow-btn" id="next-btn" onclick="changeSlide(1)">
        {'الشريحة التالية ◀' if is_ar else 'Suivant ▶'}
    </button>
</div>

<div style="display:none;" id="audio-vault">
    {"".join(audio_tags)}
</div>

<script>
var currentSlide = 0;
var totalSlides = {len(scene_data)};
var activeAudio = null;

function showSlide(n) {{
    if (n < 0) n = 0;
    if (n >= totalSlides) n = totalSlides - 1;
    currentSlide = n;

    document.querySelectorAll('.story-slide').forEach(function(s, idx) {{
        if (idx === n) s.classList.add('active');
        else s.classList.remove('active');
    }});

    document.querySelectorAll('.dot-btn').forEach(function(d, idx) {{
        if (idx === n) d.classList.add('active');
        else d.classList.remove('active');
    }});

    var prevBtn = document.getElementById('prev-btn');
    var nextBtn = document.getElementById('next-btn');
    if (prevBtn) prevBtn.disabled = (n === 0);
    if (nextBtn) nextBtn.disabled = (n === totalSlides - 1);

    stopAudio();
}}

function changeSlide(step) {{
    var isRTL = document.documentElement.getAttribute('dir') === 'rtl';
    showSlide(currentSlide + step);
}}

function playSceneAudio(idx) {{
    var aud = document.getElementById('story_audio_' + idx);
    var btn = document.getElementById('listen-btn-' + idx);
    if (!aud) return;

    if (activeAudio && !activeAudio.paused && activeAudio === aud) {{
        stopAudio();
        return;
    }}

    stopAudio();
    activeAudio = aud;
    aud.currentTime = 0;
    if (btn) btn.classList.add('is-playing');
    aud.play().catch(function(e){{ console.warn(e); }});

    aud.onended = function() {{
        if (btn) btn.classList.remove('is-playing');
        activeAudio = null;
    }};
}}

function stopAudio() {{
    if (activeAudio) {{
        try {{ activeAudio.pause(); }} catch(e){{}}
        activeAudio = null;
    }}
    document.querySelectorAll('.listen-btn').forEach(function(b){{
        b.classList.remove('is-playing');
    }});
}}

function initDots() {{
    var box = document.getElementById('dots-box');
    if (!box) return;
    box.innerHTML = '';
    for (var i = 0; i < totalSlides; i++) {{
        (function(idx) {{
            var dot = document.createElement('button');
            dot.className = 'dot-btn' + (idx === 0 ? ' active' : '');
            dot.onclick = function() {{ showSlide(idx); }};
            box.appendChild(dot);
        }})(i);
    }}
}}

function toggleFullscreen() {{
    if (!document.fullscreenElement) {{
        document.documentElement.requestFullscreen().catch(function(e){{ console.warn(e); }});
    }} else {{
        if (document.exitFullscreen) document.exitFullscreen();
    }}
}}

document.addEventListener('keydown', function(e) {{
    if (e.key === 'ArrowRight') {{
        var isRTL = document.documentElement.getAttribute('dir') === 'rtl';
        changeSlide(isRTL ? -1 : 1);
    }} else if (e.key === 'ArrowLeft') {{
        var isRTL = document.documentElement.getAttribute('dir') === 'rtl';
        changeSlide(isRTL ? 1 : -1);
    }} else if (e.key === ' ') {{
        e.preventDefault();
        playSceneAudio(currentSlide);
    }}
}});

window.addEventListener('DOMContentLoaded', function() {{
    initDots();
    showSlide(0);
}});
</script>
</body>
</html>"""


def html_escape(text: str) -> str:
    """Échappe le texte pour injection HTML sécurisée."""
    if not text:
        return ""
    return (
        str(text)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&#039;")
    )
