"""
Moteur IA pour Ecole Adnane.
Couche d'abstraction unifiée supportant Google Gemini (priorité Free Tier) et OpenAI.
Garantit la stricte parité linguistique (Arabe / Français) et la pédagogie socratique pour 3AC.
"""

import json
import logging
import re
from typing import Any, Dict, List, Optional

from models.database import get_setting, set_setting
from services.config_manager import (
    get_gemini_api_key,
    get_openai_api_key,
    get_user_gemini_api_key,
    get_user_openai_api_key,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Appel LLM unifié (Gemini en priorité, OpenAI en fallback)
# ---------------------------------------------------------------------------

def call_llm(
    prompt: str,
    system_instruction: Optional[str] = None,
    json_mode: bool = False,
    temperature: float = 0.4,
    user_id: Optional[int] = None,
    api_key: Optional[str] = None,
) -> str:
    """
    Exécute un appel au LLM configuré (Google Gemini d'abord, puis OpenAI).
    Utilise en priorité la clé individuelle de l'utilisateur actif.
    """
    gemini_key = api_key or get_user_gemini_api_key(user_id)
    openai_key = get_user_openai_api_key(user_id)

    if not gemini_key and not openai_key:
        raise ValueError(
            "Aucune clé API configurée pour votre compte. Veuillez ajouter votre clé Google Gemini gratuite dans vos Paramètres."
        )

    # 1. Priorité Google Gemini
    if gemini_key:
        active_model = get_setting("GEMINI_ACTIVE_MODEL") or "gemini-3.5-flash"
        candidates = [
            active_model,
            "gemini-3.5-flash",
            "gemini-3.5-flash-lite",
            "gemini-3.1-flash-lite",
            "gemini-3-flash-preview",
            "gemini-3.8-flash",
            "gemini-flash-latest",
        ]
        # Filtrer None et dédupliquer
        candidates = [m for m in candidates if m]
        seen = set()
        unique_candidates = [m for m in candidates if not (m in seen or seen.add(m))]

        # Tentative avec le SDK moderne google-genai
        try:
            from google import genai
            from google.genai import types

            client = genai.Client(
                api_key=gemini_key,
                http_options=types.HttpOptions(timeout=30000),
            )
            config = types.GenerateContentConfig(
                temperature=temperature,
                system_instruction=system_instruction,
                response_mime_type="application/json" if json_mode else "text/plain",
            )

            for model_name in unique_candidates:
                try:
                    response = client.models.generate_content(
                        model=model_name,
                        contents=prompt,
                        config=config,
                    )
                    if response.text:
                        set_setting("GEMINI_ACTIVE_MODEL", model_name)
                        return response.text.strip()
                except Exception as e_m:
                    logger.warning(f"Modèle {model_name} non disponible ({e_m}), essai du suivant...")
                    continue
        except Exception as e_genai:
            logger.warning(f"Erreur client google-genai ({e_genai})")
            if not openai_key:
                raise RuntimeError(f"Erreur avec Google Gemini : {str(e_genai)}")

    # 2. Fallback OpenAI
    if openai_key:
        try:
            from openai import OpenAI
            client = OpenAI(api_key=openai_key)
            messages = []
            if system_instruction:
                messages.append({"role": "system", "content": system_instruction})
            messages.append({"role": "user", "content": prompt})

            kwargs: Dict[str, Any] = {
                "model": "gpt-4o-mini",
                "messages": messages,
                "temperature": temperature,
            }
            if json_mode:
                kwargs["response_format"] = {"type": "json_object"}

            resp = client.chat.completions.create(**kwargs)
            content = resp.choices[0].message.content
            if content:
                return content.strip()
        except Exception as e_openai:
            raise RuntimeError(f"Erreur avec OpenAI : {str(e_openai)}")

    raise RuntimeError("Impossible de générer une réponse de l'IA.")


def clean_json_output(raw_text: str) -> str:
    """Extrait la charge utile JSON même si le modèle a inclus des blocs markdown ```json."""
    text = raw_text.strip()
    match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", text)
    if match:
        return match.group(1).strip()
    return text


# ---------------------------------------------------------------------------
# 1. Classification & Extraction de Métadonnées (Bilingue)
# ---------------------------------------------------------------------------

def classify_and_extract_metadata(
    raw_text: str,
    detected_lang: str,
    fallback_title: str,
    fallback_subject: str,
    user_id: Optional[int] = None,
) -> Dict[str, Any]:
    """
    Affine le titre du cours, la matière 3AC exacte, les notions clés et le niveau estimé.
    Respecte scrupuleusement la langue d'origine.
    """
    excerpt = raw_text[:3500]

    if detected_lang == "ar":
        sys_prompt = (
            "أنت خبير تربوي مغربي متخصص في منهاج السنة الثالثة إعدادي (3AC).\n"
            "مهمتك تحليل النص المستخرج من وثيقة دراسية وتحديد المادة الدقيقة، عنوان الدرس، والمفاهيم الأساسية.\n"
            "المواد الممكنة في الشعبة العامة/العربية: 'التربية الإسلامية'، 'الاجتماعيات'، 'اللغة العربية'.\n"
            "اكتب مخرجاتك بدقة متناهية وباللغة العربية الفصحى فقط وبصيغة JSON."
        )
        user_prompt = f"""
حلل النص التالي المستخرج من درس للسنة الثالثة إعدادي:
---
{excerpt}
---
أرجع كائن JSON فقط بالبنية التالية:
{{
  "title": "عنوان الدرس الدقيق والواضح",
  "subject": "التربية الإسلامية أو الاجتماعيات أو اللغة العربية",
  "key_concepts": ["مفهوم 1", "مفهوم 2", "مفهوم 3", "مفهوم 4"],
  "estimated_level": "السنة الثالثة إعدادي (3AC)"
}}
"""
    elif detected_lang == "en":
        sys_prompt = (
            "You are a Moroccan pedagogical expert specializing in the official 3rd Year Middle School (3AC) curriculum.\n"
            "Your task is to analyze text from a 3AC English lesson and determine the exact lesson title, subject ('Anglais'), and key vocabulary/grammar concepts.\n"
            "Output strictly valid JSON with all fields in English."
        )
        user_prompt = f"""
Analyze the following text extracted from a 3AC English course:
---
{excerpt}
---
Return ONLY a valid JSON object with this exact structure:
{{
  "title": "Clear and precise title of the English lesson",
  "subject": "Anglais",
  "key_concepts": ["concept 1", "concept 2", "concept 3", "concept 4"],
  "estimated_level": "3AC Middle School"
}}
"""
    else:
        sys_prompt = (
            "Tu es un expert pédagogique marocain spécialisé dans le programme officiel de 3ème Année Collège (3AC / Biof).\n"
            "Ta mission est d'analyser le texte extrait d'un cours pour déterminer la matière exacte, le titre précis et les concepts clés.\n"
            "Matières possibles (Biof/Français) : 'Mathématiques', 'Physique-Chimie', 'SVT', 'Français', 'Anglais'.\n"
            "Fournis impérativement ta réponse au format JSON strict et uniquement en français."
        )
        user_prompt = f"""
Analyse l'extrait suivant d'un cours de 3ème Année Collège (3AC) :
---
{excerpt}
---
Renvoie uniquement un objet JSON respectant exactement cette structure :
{{
  "title": "Titre clair et précis du cours",
  "subject": "Mathématiques ou Physique-Chimie ou SVT ou Français ou Anglais",
  "key_concepts": ["concept 1", "concept 2", "concept 3", "concept 4"],
  "estimated_level": "3ème Année Collège (3AC)"
}}
"""

    try:
        raw_res = call_llm(user_prompt, system_instruction=sys_prompt, json_mode=True, temperature=0.2, user_id=user_id)
        cleaned = clean_json_output(raw_res)
        data = json.loads(cleaned)
        return {
            "title": data.get("title") or fallback_title,
            "subject": data.get("subject") or fallback_subject,
            "key_concepts": data.get("key_concepts") or [],
            "estimated_level": data.get("estimated_level") or "3AC Collège",
        }
    except Exception as e:
        logger.warning(f"Erreur classification IA ({e}), utilisation des valeurs par défaut")
        return {
            "title": fallback_title,
            "subject": fallback_subject,
            "key_concepts": [],
            "estimated_level": "3AC Collège",
        }


# ---------------------------------------------------------------------------
# 2. Génération de Fiche Express (Bilinguisme strict)
# ---------------------------------------------------------------------------

def generate_revision_sheet(
    raw_text: str,
    subject: str,
    language: str,
    user_id: Optional[int] = None,
) -> str:
    """
    Génère une 'Fiche Express' adaptée à un élève de 14 ans (3AC Maroc).
    Structure : Définitions incontournables, Formules/Dates, Pièges d'examen normalisé, Astuce de rédaction.
    """
    excerpt = raw_text[:5000]

    if language == "ar":
        sys_prompt = (
            "أنت أستاذ مغربي متميز ومحبوب من تلاميذ السنة الثالثة إعدادي (3AC).\n"
            "أسلوبك واضح، محفز، دقيق وخالٍ من التعقيد الأكاديمي.\n"
            "أنت تكتب بطاقة مراجعة مركزة للامتحان الموحد (المحلي أو الجهوي).\n"
            "قاعدة صارمة: اكتب حصرياً وبالكامل باللغة العربية الفصحى السلسة والمتقنة مع تشكيل الكلمات الضرورية."
        )
        user_prompt = f"""
قم بإعداد "بطاقة مراجعة سريعة" (Fiche Express) لدرس من مادة: {subject}.
محتوى الدرس:
---
{excerpt}
---

قم بتنسيق البطاقة بتنسيق Markdown الجميل مستخدماً العناوين والأيقونات التالية حصراً:

## 🎯 المفاهيم والتعاريف الأساسية (التي تتكرر في الامتحان)
(قدم 3 إلى 5 تعاريف أو مفاهيم لا بد منها بأسلوب مبسط ومباشر يفهمه تلميذ عمره 14 سنة)

## 📌 القواعد الذهبية / التواريخ والعناصر المفتاحية
(قدم الصيغ أو الخطوات المنهجية أو التواريخ الأساسية حسب المادة بنقاط واضحة)

## ⚠️ فخاخ الامتحان الموحد (أخطاء يقع فيها أغلب التلاميذ)
(وضح 2 إلى 3 فخاخ نموذجية يضعها الأساتذة في الامتحانات المحلية والجهوية وكيفية تجنبها بذكاء)

## 💡 نصيحة التحرير لضمان النقطة الكاملة
(نصيحة عملية لكتابة الإجابة بشكل يرضي المصحح)
"""
    elif language == "en":
        sys_prompt = (
            "You are an inspiring and supportive English teacher in Morocco for 14-year-old students in 3rd Year Middle School (3AC).\n"
            "Your style is clear, motivating, encouraging, and focused on exam success.\n"
            "Strict rule: Write entirely in clear, simple and correct English."
        )
        user_prompt = f"""
Prepare a concise and high-impact 'Revision Sheet' (Fiche Express) for this 3AC English lesson.
Course content:
---
{excerpt}
---

Format the sheet in clean Markdown using EXACTLY these section headers and icons:

## 🎯 Essential Vocabulary & Key Terms
(3 to 5 must-know words and expressions with clear, simple definitions or examples for a 14-year-old student)

## 📌 Grammar Rules & Sentence Patterns
(Key tenses, sentence structures, or grammar rules with easy examples)

## ⚠️ Common Exam Traps & Mistakes to Avoid
(2 to 3 typical mistakes students make in Moroccan 3AC English exams, and how to avoid them)

## 💡 Top Writing & Reading Tip
(A practical tip to write a great paragraph or ace reading comprehension on the exam)
"""
    else:
        sys_prompt = (
            "Tu es un professeur de collège au Maroc, réputé pour ta pédagogie claire et motivante auprès des élèves de 14 ans (3AC Biof).\n"
            "Tu rédiges une 'Fiche Express' spéciale pour réussir les examens normalisés (local et régional).\n"
            "Règle absolue : Rédige STRICTEMENT en français avec un ton direct, bienveillant, clair et sans jargon inutile."
        )
        user_prompt = f"""
Rédige une "Fiche Express" percutante pour ce cours de la matière : {subject}.
Contenu du cours :
---
{excerpt}
---

Structure la fiche en Markdown clair et aéré en utilisant ces sections précises :

## 🎯 Définitions & Notions Incontournables
(3 à 5 définitions indispensables pour le contrôle et l'examen normalisé, formulées simplement)

## 📌 Formules Clés / Propriétés à Retenir
(Les formules mathématiques/scientifiques, règles ou repères essentiels sous forme de puces percutantes)

## ⚠️ Les Pièges Fréquents à l'Examen Normalisé
(2 ou 3 pièges classiques tendus lors des épreuves locales ou régionales du brevet 3AC, et comment les déjouer)

## 💡 L'Astuce Rédaction pour Gagner des Points
(Le conseil méthodologique ultime pour soigner sa copie et obtenir la note maximale)
"""

    return call_llm(user_prompt, system_instruction=sys_prompt, temperature=0.3, user_id=user_id)


# ---------------------------------------------------------------------------
# 3. Génération de Quiz d'Entraînement Examen (QCM Interactif)
# ---------------------------------------------------------------------------

def generate_quiz(
    raw_text: str,
    subject: str,
    language: str,
    num_questions: int = 5,
    user_id: Optional[int] = None,
) -> List[Dict[str, Any]]:
    """
    Génère un quiz interactif au format JSON strict.
    Questions adaptées au format d'examen normalisé 3AC Maroc.
    """
    excerpt = raw_text[:4500]

    if language == "ar":
        sys_prompt = (
            "أنت خبير في إعداد الامتحانات الموحدة للسنة الثالثة إعدادي في المغرب (3AC).\n"
            "مهمتك إعداد كويز تدريبي تفاعلي ممتع وتعليمي لتلميذ عمره 14 سنة.\n"
            "قاعدة مطلقة: اكتب الأسئلة والخيارات والشروحات باللغة العربية الفصحى حصراً وبصيغة JSON صالحة."
        )
        user_prompt = f"""
انطلاقاً من درس مادة: {subject}
المحتوى:
---
{excerpt}
---

قم بإنشاء {num_questions} أسئلة اختيار من متعدد (QCM) مناسبة للامتحان الموحد.
أرجع فقط مصفوفة JSON صالحة تحتوي على قائمة من الأسئلة بهذه البنية الدقيقة:
[
  {{
    "question": "نص السؤال الواضح والمحدد؟",
    "options": [
      "الخيار أ",
      "الخيار ب",
      "الخيار ج",
      "الخيار د"
    ],
    "answer_index": 0,
    "explanation": "شرح مبسط خطوة بخطوة يبين لماذا هذا الخيار هو الصحيح ويشجع التلميذ.",
    "trap_alert": "تنبيه ذكي من فخ الامتحان الشائع المتعلق بهذا السؤال.",
    "difficulty": "سهل أو متوسط أو متقدم"
  }}
]
"""
    elif language == "en":
        sys_prompt = (
            "You are an expert exam designer for 3rd Year Middle School (3AC) English in Morocco.\n"
            "You create a fun, stimulating, and reassuring interactive training quiz for a 14-year-old learner.\n"
            "Strict rule: Write questions, options, and explanations in clear English as valid JSON."
        )
        user_prompt = f"""
Based on this 3AC English lesson content:
---
{excerpt}
---

Generate {num_questions} multiple-choice questions (QCM) typical of 3AC English exams (reading comprehension, grammar, vocabulary).
Return ONLY a valid JSON array containing this exact structure:
[
  {{
    "question": "Clear and focused question in English?",
    "options": [
      "Option A",
      "Option B",
      "Option C",
      "Option D"
    ],
    "answer_index": 0,
    "explanation": "Step-by-step, encouraging explanation in simple English showing why this option is correct.",
    "trap_alert": "A smart tip warning about a common exam mistake related to this question.",
    "difficulty": "Easy or Medium or Advanced"
  }}
]
"""
    else:
        sys_prompt = (
            "Tu es un concepteur d'épreuves d'examens normalisés de 3ème Année Collège au Maroc (3AC Biof).\n"
            "Tu crées un quiz d'entraînement interactif stimulant et rassurant pour un élève de 14 ans.\n"
            "Règle absolue : Rédige STRICTEMENT en français au format JSON valide."
        )
        user_prompt = f"""
À partir de ce cours de la matière : {subject}
Contenu :
---
{excerpt}
---

Génère {num_questions} questions à choix multiples (QCM) types de l'examen normalisé.
Renvoie UNIQUEMENT un tableau JSON valide contenant cette structure exacte :
[
  {{
    "question": "Énoncé clair et ciblé de la question ?",
    "options": [
      "Choix A",
      "Choix B",
      "Choix C",
      "Choix D"
    ],
    "answer_index": 0,
    "explanation": "Explication pas à pas, claire et encourageante pour un élève de 14 ans.",
    "trap_alert": "Le piège d'examen classique lié à cette question.",
    "difficulty": "Facile ou Moyen ou Avancé"
  }}
]
"""

    raw_res = call_llm(user_prompt, system_instruction=sys_prompt, json_mode=True, temperature=0.3, user_id=user_id)
    cleaned = clean_json_output(raw_res)

    try:
        data = json.loads(cleaned)
        # Si le modèle a encapsulé dans un dict {"questions": [...]}
        if isinstance(data, dict):
            for k in ["questions", "quiz", "data"]:
                if k in data and isinstance(data[k], list):
                    data = data[k]
                    break
        if isinstance(data, list) and len(data) > 0:
            return data
    except Exception as e:
        logger.error(f"Erreur parsing JSON du quiz: {e}")

    # Fallback si le format JSON a échoué
    if language == "ar":
        return [{
            "question": f"ما هو المحور الأساسي لدرس {subject}؟",
            "options": ["المفهوم الرئيسي للدرس", "عنصر غير ذي صلة", "موضوع خارجي", "تطبيق عام"],
            "answer_index": 0,
            "explanation": "المحور الأساسي يركز على التطبيقات والقواعد الجوهرية المقررة في منهاج 3AC.",
            "trap_alert": "انتبه دائماً لقراءة السؤال كاملاً قبل التسرع في الإجابة.",
            "difficulty": "سهل"
        }]
    elif language == "en":
        return [{
            "question": f"What is the main learning objective of this {subject} lesson?",
            "options": ["Mastering the key grammar and vocabulary of the unit", "An unrelated topic", "General knowledge", "Outside material"],
            "answer_index": 0,
            "explanation": "This lesson focuses on essential 3AC English curriculum competencies.",
            "trap_alert": "Always read the full sentence and context before choosing your answer.",
            "difficulty": "Easy"
        }]
    else:
        return [{
            "question": f"Quel est l'objectif principal abordé dans ce cours de {subject} ?",
            "options": ["Maîtriser les notions clés du programme 3AC", "Un sujet hors-programme", "Une simple introduction", "Une généralité"],
            "answer_index": 0,
            "explanation": "Cet objectif est fondamental pour les épreuves de l'examen normalisé.",
            "trap_alert": "Lis attentivement toutes les données de l'énoncé avant de répondre.",
            "difficulty": "Facile"
        }]


# ---------------------------------------------------------------------------
# 4. Tuteur Virtuel Socratique (Bilingue et Pédagogique)
# ---------------------------------------------------------------------------

def socratic_tutor_response(
    messages: List[Dict[str, str]],
    course_context: str,
    subject: str,
    language: str,
    user_id: Optional[int] = None,
) -> str:
    """
    Répond à l'élève en adoptant la méthode socratique :
    - Ton bienveillant, encourageant, accessible pour un ado de 14 ans.
    - NE DONNE JAMAIS LA RÉPONSE DIRECTE d'un exercice ou d'un devoir.
    - Pose des questions guidées, donne des indices, félicite l'effort de réflexion.
    - Respecte strictement la langue du document (Arabe, Anglais ou Français).
    """
    context_excerpt = course_context[:4000]

    if language == "ar":
        system_instruction = f"""
أنت "سند"، الرفيق الذكي والأخ الأكبر الموجه لتلميذ عمره 14 سنة في السنة الثالثة إعدادي بالمغرب (3AC).
أنت ترافقه في مراجعة مادة: {subject}.
سياق الدرس النشط الذي يدرسه التلميذ حالياً:
---
{context_excerpt}
---

قواعدك التربوية الذهبية:
1. المنهج السقراطي: لا تعطِ الإجابة المباشرة أو الجاهزة أبداً لواجبات التلميذ أو تمارينه! بدلاً من ذلك، وجهه بخطوات بسيطة واطرح عليه سؤالاً يقوده لاكتشاف الحل بنفسه.
2. التبسيط والود: تحدث بلغة عربية فصحى دافئة ومحفزة جداً (مثل: "ممتاز يا بطل"، "فكرة ذكية، لنفكر معاً...", "أنت قريب جداً!").
3. التوجيه نحو الامتحان الموحد: ذكر التلميذ إذا لزم الأمر بالصيغ المنهجية التي تطلب في الامتحان الجهوي والمحلي.
4. الالتزام اللغوي المطلق: تحدث باللغة العربية فقط وبشكل كامل.
"""
    elif language == "en":
        system_instruction = f"""
You are "Sanad", the kind, supportive virtual tutor and mentor for a 14-year-old student in 3rd Year Middle School (3AC) in Morocco.
You are helping the student study: {subject} (English).
Here is the active lesson content they are currently studying:
---
{context_excerpt}
---

Your golden pedagogical rules:
1. Socratic Method: NEVER give the direct answer to exercises or homework! Instead, guide the student step by step with a leading question or hint so they discover the answer themselves.
2. Tone & Warmth: Be warm, enthusiastic, and very encouraging (e.g. "Great try champion!", "Awesome question, let's look at the clue...", "You are almost there!").
3. Moroccan 3AC Focus: Mention practical tips for the 3AC English exam when relevant.
4. Language Rule: Speak entirely in clear, simple, accessible English suited for a 14-year-old 3AC student.
"""
    else:
        system_instruction = f"""
Tu es "Sanad", le tuteur virtuel bienveillant et grand frère d'un élève de 14 ans en 3ème Année Collège au Maroc (3AC Biof).
Tu l'accompagnes pour réviser la matière : {subject}.
Voici le contenu du cours actif qu'il étudie :
---
{context_excerpt}
---

Tes règles d'or pédagogiques :
1. Méthode Socratique : Ne donne JAMAIS directement la réponse aux devoirs ou exercices ! Guide l'élève pas à pas en lui posant une question intermédiaire ou en lui donnant un indice ciblé pour qu'il trouve par lui-même.
2. Ton & Motivation : Sois chaleureux, enthousiaste et très encourageant (ex: "Bien joué champion !", "Très bonne question !", "Tu y es presque, regarde cette étape...").
3. Astuces Brevet 3AC : Donne des repères pratiques pour les examens normalisés (local et régional).
4. Langue stricte : Réponds STRICTEMENT en français.
"""

    # Construire la conversation pour le prompt
    conv_history = ""
    for m in messages[-8:]:  # Garder les 8 derniers échanges
        role_label = "L'élève" if m["role"] == "user" else "Tuteur Sanad"
        conv_history += f"\n{role_label}: {m['content']}"

    prompt = f"Historique de l'échange :\n{conv_history}\n\nRéponds maintenant à l'élève en tant que tuteur socratique :"

    return call_llm(prompt, system_instruction=system_instruction, temperature=0.6, user_id=user_id)
