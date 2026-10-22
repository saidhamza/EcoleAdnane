"""
Moteur IA pour Ecole Adnane.
Couche d'abstraction unifiée supportant Google Gemini (priorité Free Tier) et OpenAI.
Garantit la stricte parité linguistique (Arabe / Français) et la pédagogie socratique pour 3AC.
"""

import json
import logging
import re
from typing import Any, Dict, List, Optional, Tuple

from models.database import (
    get_pedagogical_cycle,
    get_setting,
    get_user_by_id,
    is_generic_concept,
    set_setting,
)
from services.config_manager import (
    get_gemini_api_key,
    get_openai_api_key,
    get_user_gemini_api_key,
    get_user_openai_api_key,
)

logger = logging.getLogger(__name__)


def resolve_student_age(user_id: Optional[int] = None, age: Optional[int] = None) -> int:
    """Résout l'âge de l'élève à partir de l'argument explicite ou du profil en base (défaut : 14)."""
    if age is not None:
        try:
            return max(5, min(100, int(age)))
        except (ValueError, TypeError):
            pass
    if user_id is not None:
        try:
            u = get_user_by_id(user_id)
            if u and u.get("age"):
                return max(5, min(100, int(u["age"])))
        except Exception:
            pass
    return 14


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
    age: Optional[int] = None,
) -> str:
    """
    Génère une 'Fiche Express' adaptée à l'âge de l'élève (Primaire, Collège, Lycée, Supérieur/Adulte).
    Structure adaptée au niveau cognitif et scolaire.
    """
    excerpt = raw_text[:5000]
    student_age = resolve_student_age(user_id=user_id, age=age)
    cycle = get_pedagogical_cycle(student_age)
    stage = cycle["stage"]

    if language == "ar":
        if stage == "primary":
            sys_prompt = (
                f"أنت معلم متميز ومحبوب جداً من تلاميذ المرحلة الابتدائية (عمر التلميذ: {student_age} سنوات).\n"
                "أسلوبك لطيف للغاية، واضح، مشجع، مبسط وخالٍ تماماً من التعقيدات الأكاديمية.\n"
                "قاعدة صارمة وإلزامية للقراءة الصوتية والفهم: اكتب حصرياً وبالكامل باللغة العربية الفصحى السلسة مع التشكيل والحركات التامة على كافة الكلمات لتسهيل القراءة والنطق الصوتي السليم."
            )
            user_prompt = f"""
قم بإعداد "بطاقة مراجعة مبسطة وممتعة" (Fiche Express) مشكولة بالحركات التامة تناسب تلميذاً عمره {student_age} سنوات لدرس من مادة: {subject}.
محتوى الدرس:
---
{excerpt}
---

قم بتنسيق البطاقة بتنسيق Markdown الجميل مستخدماً العناوين والأيقونات التالية حصراً مع ضبط النص بالحركات والتشكيل:

## 🎯 الكلمات والمفاهيم المهمة (التي يجب أن أعرفها)
(قدم 3 إلى 4 مفاهيم بأسلوب مبسط جداً وأمثلة ممتعة تناسب طفلاً عمره {student_age} سنوات مضبوطة بالشكل التام)

## 📌 القواعد الذهبية البسيطة
(أهم نقطتين أو 3 نقاط بأسلوب ممتع ومباشر لتسهيل التذكر مع التشكيل)

## ⚠️ انتبه يا بطل ولا تقع في هذا الخطأ
(خطأ شائع يقع فيه الأطفال يتم توضيحه بلطف وتشجيع)

## 💡 سر التفوق والنجاح
(نصيحة جميلة وتشجيع حار للطفل للتألق في القسم)
"""
        elif stage == "high":
            sys_prompt = (
                f"أنت أستاذ خبير ومتميز في المرحلة الثانوية التأهيلية لمواكبة تلميذ في سلك البكالوريا (عمره {student_age} سنة).\n"
                "أسلوبك دقيق، أكاديمي، منهجي، يركز على الرقي المعرفي والاستعداد للامتحانات الإشهادية (الجهوي والوطني).\n"
                "قاعدة صارمة: اكتب حصرياً وبالكامل باللغة العربية الفصحى الأكاديمية والمنهجية مع التشكيل والحركات لتسهيل القراءة والنطق الصوتي السليم."
            )
            user_prompt = f"""
قم بإعداد "بطاقة مراجعة مركزة" (Fiche Express) مضبوطة بالحركات لسلك البكالوريا (تلميذ عمره {student_age} سنة) لدرس من مادة: {subject}.
محتوى الدرس:
---
{excerpt}
---

قم بتنسيق البطاقة بتنسيق Markdown الجميل مستخدماً العناوين والأيقونات التالية حصراً مع التشكيل:

## 🎯 المفاهيم والمصطلحات المركزية والمحددات النظرية
(3 إلى 5 تعريفات ومفاهيم دقيقة بمصطلحات المادة والمقرر التأهيلي)

## 📌 القواعد والبرهنات والمنهجيات الأساسية
(الصيغ الرياضية والعلمية أو الخطوات المنهجية المعتمدة في إطار الامتحان الوطني/الجهوي)

## ⚠️ فخاخ ومزالق الامتحانات الإشهادية (البكالوريا)
(2 إلى 3 فخاخ نموذجية في أسئلة الامتحان وطرق تفاديها بالبرهان والدقة)

## 💡 توجيهات منهجية لضمان الامتياز في التحرير
(نصيحة لتحرير إجابة نموذجية تستوفي عناصر سلم التنقيط والتميز)
"""
        elif stage == "higher":
            sys_prompt = (
                f"أنت موجه أكاديمي وأستاذ جامعي يواكب متعلماً راشداً أو طالباً في التعليم العالي (عمره {student_age} سنة).\n"
                "أسلوبك رفيع، تحليلي، نقدي، يركز على الأسس النظرية والتطبيقات العملية والمهنية.\n"
                "قاعدة صارمة: اكتب حصرياً باللغة العربية الفصحى الرصينة والمتقنة مع ضبط الكلمات بالحركات لتيسير القراءة السليمة."
            )
            user_prompt = f"""
قم بإعداد "بطاقة مراجعة وتلخيص تحليلي" (Fiche Express) لمتعلم في التعليم العالي/المستوى المتقدم (عمره {student_age} سنة) لموضوع: {subject}.
محتوى المادة:
---
{excerpt}
---

قم بتنسيق البطاقة بتنسيق Markdown مستخدماً العناوين التالية حصراً:

## 🎯 المفاهيم المحورية والأسس النظرية
(3 إلى 5 مفاهيم مركزية محددة بدقة فلسفية وعلمية)

## 📌 النماذج والقواعد التحليلية والتطبيقية
(المناهج، الصيغ أو الأطر التحليلية ذات الصلة)

## ⚠️ الأخطاء التحليلية والمنهجية الشائعة
(الانزلاقات المنهجية التي يجب الحذر منها في هذا التخصص)

## 💡 رؤية نقدية وتوجيهات للتعمق والامتياز
(توجيهات لتعميق الفهم وربطه بالسياقات المهنية أو الأكاديمية)
"""
        else:  # middle (défaut 11-14 ans)
            sys_prompt = (
                f"أنت أستاذ مغربي متميز ومحبوب من تلاميذ المرحلة الإعدادية (عمر التلميذ: {student_age} سنة).\n"
                "أسلوبك واضح، محفز، دقيق وخالٍ من التعقيد الأكاديمي.\n"
                "أنت تكتب بطاقة مراجعة مركزة للامتحان الموحد (المحلي أو الجهوي).\n"
                "قاعدة صارمة وإلزامية للقراءة الصوتية: اكتب حصرياً وبالكامل باللغة العربية الفصحى السلسة والمتقنة مع التشكيل والحركات التامة على كافة الكلمات لتسهيل القراءة والنطق الصوتي السليم."
            )
            user_prompt = f"""
قم بإعداد "بطاقة مراجعة سريعة" (Fiche Express) لدرس من مادة: {subject}.
محتوى الدرس:
---
{excerpt}
---

قم بتنسيق البطاقة بتنسيق Markdown الجميل مستخدماً العناوين والأيقونات التالية حصراً:

## 🎯 المفاهيم والتعاريف الأساسية (التي تتكرر في الامتحان)
(قدم 3 إلى 5 تعاريف أو مفاهيم لا بد منها بأسلوب مبسط ومباشر يفهمه تلميذ عمره {student_age} سنة)

## 📌 القواعد الذهبية / التواريخ والعناصر المفتاحية
(قدم الصيغ أو الخطوات المنهجية أو التواريخ الأساسية حسب المادة بنقاط واضحة)

## ⚠️ فخاخ الامتحان الموحد (أخطاء يقع فيها أغلب التلاميذ)
(وضح 2 إلى 3 فخاخ نموذجية يضعها الأساتذة في الامتحانات المحلية والجهوية وكيفية تجنبها بذكاء)

## 💡 نصيحة التحرير لضمان النقطة الكاملة
(نصيحة عملية لكتابة الإجابة بشكل يرضي المصحح)
"""

    elif language == "en":
        if stage == "primary":
            sys_prompt = (
                f"You are an inspiring, warm, and highly supportive primary school teacher for a {student_age}-year-old child.\n"
                "Your style is playful, simple, clear, encouraging, and easy to understand.\n"
                f"Strict rule: Write entirely in clear, simple English suited for a {student_age}-year-old learner."
            )
            user_prompt = f"""
Prepare a fun and clear 'Revision Sheet' (Fiche Express) for a {student_age}-year-old child studying: {subject}.
Course content:
---
{excerpt}
---

Format the sheet in clean Markdown using EXACTLY these section headers and icons:

## 🎯 Super Words & Key Ideas to Remember
(3 to 4 easy words or concepts with friendly examples for a {student_age}-year-old learner)

## 📌 Golden Rules Made Easy
(The 2 or 3 essential points explained simply and clearly)

## ⚠️ Watch Out for This Little Trap!
(A common mistake to avoid with gentle, cheerful guidance)

## 💡 Star Tip to Do Great
(A positive, encouraging tip for success in class)
"""
        elif stage == "high":
            sys_prompt = (
                f"You are a dedicated high school educator preparing a {student_age}-year-old student for secondary exams and the Baccalaureate.\n"
                "Your style is rigorous, conceptually precise, analytical, and focused on exam mastery.\n"
                "Strict rule: Write entirely in clear, correct, and academically rigorous English."
            )
            user_prompt = f"""
Prepare an advanced 'Revision Sheet' (Fiche Express) for a {student_age}-year-old high school student studying: {subject}.
Course content:
---
{excerpt}
---

Format the sheet in clean Markdown using EXACTLY these section headers and icons:

## 🎯 Core Academic Vocabulary & Conceptual Foundations
(3 to 5 precise terms and definitions required for secondary / Baccalaureate mastery)

## 📌 Analytical Rules & Methodological Patterns
(Formulas, grammatical rules, or analytical structures in clear bullet points)

## ⚠️ Critical Exam Traps & Pitfalls to Avoid
(2 to 3 sophisticated mistakes to avoid on standardized secondary exams)

## 💡 Advanced Strategy for Top Marks
(A methodological tip to craft high-scoring responses and excel on the exam)
"""
        elif stage == "higher":
            sys_prompt = (
                f"You are an academic mentor and expert educator assisting a university student or adult learner ({student_age} years old).\n"
                "Your style is professional, intellectually thorough, concise, and focused on conceptual synthesis.\n"
                "Strict rule: Write entirely in advanced, clear, and professional English."
            )
            user_prompt = f"""
Prepare a thorough 'Conceptual Synthesis' (Fiche Express) for a higher education learner ({student_age} years old) on: {subject}.
Course content:
---
{excerpt}
---

Format the sheet in clean Markdown using EXACTLY these section headers and icons:

## 🎯 Theoretical Frameworks & Key Concepts
(3 to 5 primary concepts defined with precision)

## 📌 Methodologies & Applied Principles
(Key models, frameworks, and practical applications)

## ⚠️ Analytical Pitfalls & Nuances to Master
(Subtle distinctions and methodological errors to avoid)

## 💡 Synthesis & Critical Insights
(Actionable takeaways and higher-order perspective)
"""
        else:  # middle (défaut 11-14 ans)
            sys_prompt = (
                f"You are an inspiring and supportive English teacher for {student_age}-year-old students in Middle School (3AC).\n"
                "Your style is clear, motivating, encouraging, and focused on exam success.\n"
                "Strict rule: Write entirely in clear, simple and correct English."
            )
            user_prompt = f"""
Prepare a concise and high-impact 'Revision Sheet' (Fiche Express) for this lesson ({subject}).
Course content:
---
{excerpt}
---

Format the sheet in clean Markdown using EXACTLY these section headers and icons:

## 🎯 Essential Vocabulary & Key Terms
(3 to 5 must-know words and expressions with clear, simple definitions or examples for a {student_age}-year-old student)

## 📌 Grammar Rules & Sentence Patterns
(Key tenses, sentence structures, or grammar rules with easy examples)

## ⚠️ Common Exam Traps & Mistakes to Avoid
(2 to 3 typical mistakes students make on exams, and how to avoid them)

## 💡 Top Writing & Reading Tip
(A practical tip to write a great paragraph or ace reading comprehension on the exam)
"""

    else:  # français
        if stage == "primary":
            sys_prompt = (
                f"Tu es un enseignant bienveillant, chaleureux et très pédagogue pour des enfants de l'école primaire (l'élève a {student_age} ans).\n"
                "Ton style est simple, imagé, doux, enthousiaste et très encourageant.\n"
                f"Règle absolue : Rédige STRICTEMENT en français avec un vocabulaire accessible à un enfant de {student_age} ans, sans jargon abstrait."
            )
            user_prompt = f"""
Rédige une "Fiche Express" adaptée et captivante pour un enfant de {student_age} ans pour ce cours de la matière : {subject}.
Contenu du cours :
---
{excerpt}
---

Structure la fiche en Markdown clair et aéré en utilisant ces sections précises :

## 🎯 Les Notions & Mots Magiques à Retenir
(3 à 4 définitions très simples et illustrées avec des exemples du quotidien pour un enfant de {student_age} ans)

## 📌 Les Règles d'Or Faciles
(Les 2 ou 3 règles ou étapes clés expliquées pas à pas avec clarté)

## ⚠️ Attention au Petit Piège !
(Une erreur fréquente expliquée gentiment pour ne pas tomber dedans)

## 💡 L'Astuce du Champion pour Réussir
(Un conseil simple et très encourageant pour briller en classe)
"""
        elif stage == "high":
            sys_prompt = (
                f"Tu es un professeur de lycée d'excellence préparant un élève de {student_age} ans aux épreuves du Baccalauréat.\n"
                "Ton ton est rigoureux, précis, stimulant, valorisant la démonstration, la synthèse et la rigueur conceptuelle.\n"
                "Règle absolue : Rédige STRICTEMENT en français académique, clair et soigné."
            )
            user_prompt = f"""
Rédige une "Fiche Express" approfondie pour un élève de lycée ({student_age} ans) pour ce cours de la matière : {subject}.
Contenu du cours :
---
{excerpt}
---

Structure la fiche en Markdown clair et aéré en utilisant ces sections précises :

## 🎯 Définitions & Notions Fondamentales du Bac
(3 à 5 notions incontournables formulées avec précision académique et rigueur conceptuelle)

## 📌 Formules, Démonstrations & Repères Méthodologiques
(Les théorèmes, formules, repères ou mécanismes clés sous forme de synthèse claire)

## ⚠️ Pièges Classiques des Épreuves du Baccalauréat
(2 ou 3 pièges fréquents dans les sujets d'examen et la méthode rigoureuse pour les déjouer)

## 💡 La Méthode de Rédaction pour Décrocher la Mention
(Le conseil méthodologique pour structurer sa copie et satisfaire aux exigences du barème)
"""
        elif stage == "higher":
            sys_prompt = (
                f"Tu es un tuteur académique et expert pédagogique pour un étudiant de l'enseignement supérieur ou adulte apprenant ({student_age} ans).\n"
                "Ton ton est professionnel, rigoureux, concis, orienté vers la maîtrise conceptuelle approfondie et l'application pratique.\n"
                "Règle absolue : Rédige STRICTEMENT en français soigné, précis et analytique."
            )
            user_prompt = f"""
Rédige une "Fiche Express" de synthèse analytique pour un apprenant du supérieur ({student_age} ans) sur le thème : {subject}.
Contenu du cours :
---
{excerpt}
---

Structure la fiche en Markdown clair et aéré en utilisant ces sections précises :

## 🎯 Notions Clés & Fondements Théoriques
(3 à 5 notions centrales définies avec rigueur conceptuelle)

## 📌 Modèles, Méthodes & Principes d'Application
(Les méthodes, théorèmes ou frameworks clés avec leur logique de mise en œuvre)

## ⚠️ Pièges Méthodologiques & Nuances Cruciales
(Les confusions conceptuelles et erreurs d'application à éviter)

## 💡 Synthèse Stratégique & Clés d'Excellence
(Recommandations d'approfondissement et mise en perspective professionnelle ou académique)
"""
        else:  # middle (défaut 11-14 ans)
            sys_prompt = (
                f"Tu es un professeur de collège au Maroc, réputé pour ta pédagogie claire et motivante auprès des élèves de {student_age} ans (Collège Biof).\n"
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
(2 ou 3 pièges classiques tendus lors des épreuves de collège, et comment les déjouer)

## 💡 L'Astuce Rédaction pour Gagner des Points
(Le conseil méthodologique ultime pour soigner sa copie et obtenir la note maximale)
"""

    return call_llm(user_prompt, system_instruction=sys_prompt, temperature=0.3, user_id=user_id)


# ---------------------------------------------------------------------------
# 2b. Génération de Schéma Mindmap / Brainstorming (Mermaid.js)
# ---------------------------------------------------------------------------

def convert_mermaid_to_markdown(mermaid_code: str, default_title: str = "Cours") -> str:
    """
    Convertit un ancien schéma Mermaid mindmap en structure Markdown Markmap réactive.
    Permet la rétrocompatibilité immédiate avec les cartes créées précédemment.
    """
    lines = mermaid_code.strip().splitlines()
    md_lines: List[str] = []
    root_title = default_title

    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.lower() == "mindmap":
            continue

        if "root((" in stripped:
            m = re.search(r"root\(\((.*?)\)\)", stripped)
            if m:
                root_title = m.group(1).strip()
            md_lines.append(f"# {root_title}")
            continue

        indent = len(line) - len(line.lstrip(" "))
        clean_text = re.sub(r"^[-*+]\s*", "", stripped)
        clean_text = re.sub(r'[()\[\]{}"\':;]', ' ', clean_text)
        clean_text = re.sub(r"\s+", " ", clean_text).strip()
        if not clean_text:
            continue

        if indent <= 4:
            md_lines.append(f"## {clean_text}")
        elif indent <= 6:
            md_lines.append(f"### {clean_text}")
        else:
            md_lines.append(f"- {clean_text}")

    if not md_lines:
        return f"# {root_title}\n## Notions Clés\n- Contenu du cours"

    if not md_lines[0].startswith("# "):
        md_lines.insert(0, f"# {root_title}")

    return "\n".join(md_lines)


def _fallback_mindmap(title: str, subject: str = "", summary_text: str = "") -> str:
    """
    Génère une carte mentale Markdown Markmap hiérarchique, riche et auto-suffisante pour l'apprentissage.
    Exclut rigoureusement tout placeholder générique ('Pièges d'examen', 'Méthode d'application').
    """
    safe_title = re.sub(r'[#*`]', '', title).strip() or "Leçon"
    safe_subject = re.sub(r'[#*`]', '', subject).strip()

    # Si un texte de synthèse ou de cours est disponible, tenter d'extraire des sous-parties réelles
    sections: List[Tuple[str, List[str]]] = []
    if summary_text:
        raw_bullets = re.findall(r"^[-*•]\s*\*\*([^*:\n]{3,65})\*\*\s*:\s*([^\n]+)", summary_text, flags=re.MULTILINE)
        if raw_bullets:
            grouped_bullets: List[str] = []
            for b_name, b_desc in raw_bullets[:6]:
                clean_name = re.sub(r"^[0-9\.\)\-\s]+", "", b_name.strip())
                if not is_generic_concept(clean_name):
                    grouped_bullets.append(f"- **{clean_name}** : {b_desc.strip()[:140]}")
            if grouped_bullets:
                sections.append((f"Notions Clés de {safe_title}", grouped_bullets))

    if not sections:
        header = f"# {safe_title}" + (f" ({safe_subject})" if safe_subject else "")
        return f"""{header}
## 1. Définition & Notions Fondamentales
- **Cadre & Objet d'étude** : Définition formelle, notations et vocabulaire de {safe_title}
- **Concepts centraux** : Notions indispensables pour comprendre et manipuler {safe_title}
## 2. Propriétés Majeures & Formules
- **Règles fondamentales** : Énoncé précis des propriétés et théorèmes directeurs
- **Conditions de validité** : Hypothèses obligatoires avant d'appliquer les relations
## 3. Démarche de Résolution & Exemples Pratiques
- **Méthode pas-à-pas** : 1. Analyser les données ; 2. Citer la propriété ; 3. Calculer avec rigueur
- **Cas d'application type** : Modèle résolu avec formulation des étapes intermédiaires
## 4. Vérifications & Points de Vigilance
- **Contrôle de vraisemblance** : Vérification des unités, du signe et de l'ordre de grandeur
- **Raisonnement & Rédaction** : Justifications complètes attendues lors des examens"""

    header = f"# {safe_title}" + (f" ({safe_subject})" if safe_subject else "")
    lines = [header]
    for sec_title, sec_bullets in sections:
        lines.append(f"## {sec_title}")
        lines.extend(sec_bullets)
    return "\n".join(lines)


def clean_interactive_mindmap_markdown(
    raw_output: str,
    default_title: str = "Cours",
    default_subject: str = "",
    summary_text: str = "",
) -> str:
    """
    Nettoie et valide la sortie brute LLM pour garantir une carte mentale Markdown hiérarchique
    riche, interactive et compatible Markmap (D3.js).
    """
    if not raw_output:
        return _fallback_mindmap(default_title, default_subject, summary_text)

    cleaned = raw_output.strip()

    # Si le texte renvoyé est au format Mermaid mindmap, le convertir automatiquement
    if cleaned.startswith("mindmap") or "root((" in cleaned:
        return convert_mermaid_to_markdown(cleaned, default_title=default_title)

    # Retirer les blocs markdown ```markdown ou ```
    cleaned = re.sub(r"^```(?:markdown|markmap)?\s*", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\s*```$", "", cleaned)
    cleaned = cleaned.strip()

    lines = [l.rstrip() for l in cleaned.splitlines() if l.strip()]
    if not lines:
        return _fallback_mindmap(default_title, default_subject, summary_text)

    sanitized: List[str] = []
    has_h1 = False

    for line in lines:
        # Filtrer toute méta-catégorie générique (Français, Arabe, Anglais, Tashkeel inclus)
        if is_generic_concept(line):
            continue

        if line.startswith("# "):
            has_h1 = True
            sanitized.append(line)
        elif line.startswith("## ") or line.startswith("### ") or line.startswith("#### "):
            sanitized.append(line)
        elif line.strip().startswith("- ") or line.strip().startswith("* ") or line.strip().startswith("+ "):
            sanitized.append(line)
        else:
            sanitized.append(f"- {line.strip()}")

    if not has_h1:
        sanitized.insert(0, f"# {default_title}")

    if len(sanitized) <= 2:
        return _fallback_mindmap(default_title, default_subject, summary_text)

    return "\n".join(sanitized)


def clean_mermaid_mindmap(raw_output: str, default_title: str = "Cours", default_subject: str = "") -> str:
    """
    Nettoie et valide la sortie brute LLM pour garantir une syntaxe Mermaid mindmap valide (legacy).
    """
    if not raw_output:
        safe_title = re.sub(r'[()\[\]{}"\':;]', ' ', default_title).strip() or "Cours"
        return f"mindmap\n  root(({safe_title}))\n    Notions Clés\n      Concepts essentiels\n    Propriétés\n      Règles et Formules"

    cleaned = raw_output.strip()
    cleaned = re.sub(r"^```(?:mermaid|mindmap)?\s*", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\s*```$", "", cleaned)
    cleaned = cleaned.strip()

    idx = cleaned.find("mindmap")
    if idx != -1:
        cleaned = cleaned[idx:]
    else:
        cleaned = "mindmap\n" + cleaned

    lines = cleaned.splitlines()
    if not lines or lines[0].strip() != "mindmap":
        safe_title = re.sub(r'[()\[\]{}"\':;]', ' ', default_title).strip() or "Cours"
        return f"mindmap\n  root(({safe_title}))\n    Notions Clés\n      Concepts essentiels\n    Propriétés\n      Règles et Formules"

    sanitized_lines = ["mindmap"]
    for line in lines[1:]:
        stripped = line.strip()
        if not stripped:
            continue
        indent = len(line) - len(line.lstrip(" "))
        indent_str = " " * max(2, indent)

        if "root((" in stripped:
            m = re.search(r"root\(\((.*?)\)\)", stripped)
            root_text = m.group(1).strip() if m else default_title
            root_text = re.sub(r'[()\[\]{}"\':;]', ' ', root_text).strip()[:40]
            sanitized_lines.append(f"  root(({root_text or default_title}))")
            continue

        node_text = stripped
        node_text = re.sub(r"^[-*+]\s*", "", node_text)
        node_text = re.sub(r'[()\[\]{}"\':;]', ' ', node_text)
        node_text = re.sub(r"\s+", " ", node_text).strip()
        if node_text:
            sanitized_lines.append(f"{indent_str}{node_text[:50]}")

    if len(sanitized_lines) <= 2:
        safe_title = re.sub(r'[()\[\]{}"\':;]', ' ', default_title).strip() or "Cours"
        return f"mindmap\n  root(({safe_title}))\n    Notions Clés\n      Concepts essentiels\n    Propriétés\n      Règles et Formules"

    return "\n".join(sanitized_lines)


def generate_course_mindmap(
    course_text_or_summary: str,
    course_title: str,
    subject: str,
    language: str = "fr",
    user_id: Optional[int] = None,
) -> str:
    """
    Génère une carte mentale interactive Markmap (D3.js) hiérarchique, riche et auto-suffisante
    pour l'apprentissage autonome de la leçon.
    Exclut rigoureusement les méta-catégories génériques au profit des notions réelles et concrètes.
    """
    excerpt = course_text_or_summary[:4500] if course_text_or_summary else course_title

    if language == "ar":
        sys_prompt = (
            "أنت أستاذ خبير ومصمم خرائط ذهنية وبيداغوجية تفاعلية لمساعدة التلاميذ على الفهم والحفظ الذاتي الشامل.\n"
            "مهمتك تحويل الدرس إلى خريطة ذهنية تفاعلية متكاملة ومستقلة بذاتها (Auto-suffisante) بصيغة Markdown Markmap.\n"
            "يجب أن يتمكن التلميذ من استيعاب وفهم كامل تفاصيل الدرس بمجرد تصفح هذه الخريطة.\n"
            "قواعد صارمة وإلزامية:\n"
            "1. هيكلة Markdown دقيقة ومكتملة:\n"
            "   - العنوان الرئيسي (# عنوان الدرس)\n"
            "   - 3 إلى 5 محاور دراسية حقيقية للدرس (## 1. المفهوم الحقيقي الأول، ## 2. الخاصية أو المبرهنة، إلخ)\n"
            "   - تفرعات فرعية (### التعريف والقاعدة، ### مثال تطبيقي مفصل، ### الحساب والبرهان)\n"
            "   - عناصر مشروحة بالتفصيل (- **العنصر الأساسي**: شرح مفصل وكافٍ لتعلم الخاصية وتطبيقها)\n"
            "2. منع التصنيفات العامة الجوفاء: يمنع منعاً باتاً وضع عناوين عامة فارغة مثل 'فخاخ الامتحانات' أو 'طريقة التطبيق' أو 'المفاهيم الأساسية' مجردة. يجب أن تكون جميع الفروع مبنية على مضامين ومفاهيم الدرس الحقيقية.\n"
            "3. محتوى غني وتوضيحي: كتابة القواعد والصيغ بدقة، مع خطوات التطبيق وأمثلة عددية واضحة.\n"
            "4. أخرج فقط نص Markdown للخريطة الذهنية بدون أي مقدمات أو علامات كود زائدة."
        )
        user_prompt = f"""
قم بإنشاء خريطة ذهنية بيداغوجية تفاعلية ومفصلة بصيغة Markdown Markmap لدرس: {course_title} (مادة: {subject}).
محتوى الدرس أو ملخصه:
---
{excerpt}
---
نص Markdown للخريطة الذهنية التفاعلية:
"""
    elif language == "en":
        sys_prompt = (
            "You are an expert educator and visual learning designer specialized in interactive mind maps (Markmap).\n"
            "Your mission is to transform the lesson into a COMPREHENSIVE, SELF-CONTAINED interactive mind map in Markdown format.\n"
            "A student must be able to LEARN AND MASTER the entire lesson autonomously simply by exploring this diagram.\n"
            "Strict rules:\n"
            "1. Strict Markdown hierarchical outline:\n"
            "   - Root node (# Course Title)\n"
            "   - 3 to 5 real lesson topics (## 1. Real Concept A, ## 2. Core Theorem / Rule B, etc.)\n"
            "   - Sub-sections (### Definition & Rule, ### Worked Example, ### Calculation Steps)\n"
            "   - Detailed bullets (- **Key term** : Clear, self-contained explanation with formulas and context)\n"
            "2. NO GENERIC PLACEHOLDERS: Do NOT use empty meta-labels like 'Exam Pitfalls', 'Application Method', or 'Core Concepts' in isolation. Every branch must name a specific subject topic.\n"
            "3. Deep pedagogical value: Provide exact definitions, conditions, formulas, step-by-step procedures, and concrete examples.\n"
            "4. Return ONLY the Markdown outline, without intro/outro commentary, and without code fences."
        )
        user_prompt = f"""
Generate a comprehensive, self-contained interactive Markmap Markdown mind map for the course: {course_title} (Subject: {subject}).
Content / Summary:
---
{excerpt}
---
Markmap Markdown code:
"""
    else:  # fr
        sys_prompt = (
            "Tu es un professeur pédagogue d'élite, expert en schématisation visuelle et cartes mentales interactives (Markmap/Mind Mapping).\n"
            "Ta mission est de structurer le cours sous la forme d'une CARTE MENTALE PÉDAGOGIQUE COMPLÈTE ET AUTO-SUFFISANTE au format Markdown.\n"
            "L'élève doit pouvoir APPRENDRE ET COMPRENDRE L'INTÉGRALITÉ DE SA LEÇON directement en explorant ce diagramme.\n"
            "Règles impératives :\n"
            "1. STRUCTURE HIÉRARCHIQUE STRICTE EN MARKDOWN :\n"
            "   - Titre principal (# Titre du cours)\n"
            "   - 3 à 5 branches thématiques réelles du cours (## 1. Notion réelle A, ## 2. Propriété réelle B, etc.)\n"
            "   - Sous-branches (### Définition & Règle, ### Exemple d'application concret, ### Formule ou Démonstration)\n"
            "   - Puces détaillées (- **Nom du point clé** : Explication complète, claire et autosuffisante)\n"
            "2. INTERDICTION DES LABELS GÉNÉRIQUES : N'utilise JAMAIS d'intitulés méta vagues comme 'Pièges d'examen', 'Méthode d'application', 'Notions fondamentales' seuls. Chaque branche doit porter le nom d'une notion réelle du cours (ex: 'Théorème direct de Pythagore', 'Calcul de l'hypoténuse', 'Réciproque pour démontrer un angle droit').\n"
            "3. RICHESSE PÉDAGOGIQUE & CONTENU AUTO-SUFFISANT :\n"
            "   - Donne les définitions exactes, les formules complètes, les conditions d'application et les étapes de calcul.\n"
            "   - Inclus des exemples numériques ou cas types concrets pour chaque notion.\n"
            "4. FORMAT DE SORTIE : Renvoie UNIQUEMENT le texte Markdown de la carte mentale, sans aucun texte d'introduction ni de conclusion, sans bloc ```markdown."
        )
        user_prompt = f"""
Génère la carte mentale Markdown Markmap complète et auto-suffisante pour le cours : {course_title} (Matière : {subject}).
Contenu ou résumé du cours :
---
{excerpt}
---
Texte Markdown de la carte mentale :
"""

    raw = call_llm(user_prompt, system_instruction=sys_prompt, temperature=0.2, user_id=user_id)
    return clean_interactive_mindmap_markdown(
        raw,
        default_title=course_title,
        default_subject=subject,
        summary_text=course_text_or_summary,
    )


# ---------------------------------------------------------------------------
# 3. Génération de Quiz d'Entraînement Examen (QCM Interactif)
# ---------------------------------------------------------------------------

def generate_quiz(
    raw_text: str,
    subject: str,
    language: str,
    num_questions: int = 5,
    user_id: Optional[int] = None,
    age: Optional[int] = None,
) -> List[Dict[str, Any]]:
    """
    Génère un quiz interactif au format JSON strict adapté à l'âge de l'élève.
    Questions et explications calées sur le cycle pédagogique (Primaire, Collège, Lycée, Supérieur).
    """
    excerpt = raw_text[:4500]
    student_age = resolve_student_age(user_id=user_id, age=age)
    cycle = get_pedagogical_cycle(student_age)
    stage = cycle["stage"]

    if language == "ar":
        if stage == "primary":
            sys_prompt = (
                f"أنت معلم صبور ومحبوب للأطفال في المرحلة الابتدائية (عمر التلميذ: {student_age} سنوات).\n"
                "مهمتك إعداد كويز تدريبي تفاعلي ممتع وبسيط ومحفز جداً للطفل.\n"
                "قاعدة مطلقة: اكتب الأسئلة والخيارات والشروحات باللغة العربية الفصحى المبسطة مع الحركات والتشكيل التام لتسهيل النطق الصوتي وشروحات مشجعة ('أحسنت يا بطل') وبصيغة JSON صالحة."
            )
        elif stage == "high":
            sys_prompt = (
                f"أنت خبير في إعداد امتحانات البكالوريا والامتحانات الإشهادية في المغرب لتلميذ في سلك التأهيلي (عمره {student_age} سنة).\n"
                "مهمتك إعداد كويز تدريبي تفاعلي ذي عمق تحليلي ومنهجي يختبر الفهم الدقيق والقدرة على البرهنة والتركيب.\n"
                "قاعدة مطلقة: اكتب الأسئلة والخيارات والشروحات باللغة العربية الفصحى الأكاديمية الدقيقة مع التشكيل والحركات وبصيغة JSON صالحة."
            )
        elif stage == "higher":
            sys_prompt = (
                f"أنت ممتحن وأستاذ في التعليم العالي لمستوى متقدم (عمر المتعلم: {student_age} سنة).\n"
                "مهمتك إعداد تقييم تفاعلي يركز على التطبيقات النقدية والتحليل المفاهيمي وحل المشكلات المعقدة.\n"
                "قاعدة مطلقة: اكتب باللغة العربية الفصحى الرصينة مع التشكيل والحركات وبصيغة JSON صالحة."
            )
        else:  # middle (défaut 11-14 ans)
            sys_prompt = (
                f"أنت خبير في إعداد الامتحانات الموحدة للسنة الثالثة إعدادي في المغرب (3AC) لتلميذ عمره {student_age} سنة.\n"
                "مهمتك إعداد كويز تدريبي تفاعلي ممتع وتعليمي يختبر المفاهيم الأساسية وفخاخ الامتحانات.\n"
                "قاعدة مطلقة وإلزامية للقراءة الصوتية السليمة: اكتب الأسئلة والخيارات والشروحات باللغة العربية الفصحى مضبوطة بالحركات والتشكيل التام وبصيغة JSON صالحة."
            )

        user_prompt = f"""
انطلاقاً من درس مادة: {subject}
المحتوى:
---
{excerpt}
---

قم بإنشاء {num_questions} أسئلة اختيار من متعدد (QCM) مناسبة لمستوى تلميذ عمره {student_age} سنة ({cycle['stage_label']}) مضبوطة بالحركات والتشكيل التام.
أرجع فقط مصفوفة JSON صالحة تحتوي على قائمة من الأسئلة بهذه البنية الدقيقة:
[
  {{
    "question": "نص السؤال الواضح والمحدد مشكولاً بالحركات التامة؟",
    "options": [
      "الخيار أ مشكولاً",
      "الخيار ب مشكولاً",
      "الخيار ج مشكولاً",
      "الخيار د مشكولاً"
    ],
    "answer_index": 0,
    "explanation": "شرح مبسط خطوة بخطوة مشكول بالحركات يبين لماذا هذا الخيار هو الصحيح ويشجع التلميذ.",
    "trap_alert": "تنبيه ذكي من فخ شائع متعلق بهذا السؤال مع التشكيل.",
    "difficulty": "سهل أو متوسط أو متقدم"
  }}
]
"""
    elif language == "en":
        if stage == "primary":
            sys_prompt = (
                f"You are a cheerful and caring primary school teacher creating a fun quiz for a {student_age}-year-old child.\n"
                "You create an easy, encouraging, and friendly multiple-choice quiz.\n"
                "Strict rule: Write questions, options, and explanations in simple, encouraging English as valid JSON."
            )
        elif stage == "high":
            sys_prompt = (
                f"You are a secondary school exam designer preparing a {student_age}-year-old student for advanced high school and Baccalaureate exams.\n"
                "You create an intellectually stimulating, rigorous training quiz testing deep comprehension and analytical skills.\n"
                "Strict rule: Write questions, options, and explanations in academically precise English as valid JSON."
            )
        elif stage == "higher":
            sys_prompt = (
                f"You are a university examiner assessing a higher education learner ({student_age} years old).\n"
                "You design an advanced assessment testing critical reasoning, conceptual models, and practical application.\n"
                "Strict rule: Write in clear, professional English as valid JSON."
            )
        else:  # middle (défaut 11-14 ans)
            sys_prompt = (
                f"You are an expert exam designer for middle school English ({student_age}-year-old learner).\n"
                "You create a fun, stimulating, and reassuring interactive training quiz.\n"
                "Strict rule: Write questions, options, and explanations in clear English as valid JSON."
            )

        user_prompt = f"""
Based on this lesson content ({subject}) for a {student_age}-year-old student ({cycle['stage_label']}):
---
{excerpt}
---

Generate {num_questions} multiple-choice questions (QCM) appropriate for this age and level.
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
    else:  # français
        if stage == "primary":
            sys_prompt = (
                f"Tu es un enseignant patient et bienveillant pour un enfant de {student_age} ans à l'école primaire.\n"
                "Tu crées un quiz interactif simple, ludique et encourageant avec des phrases courtes et faciles.\n"
                "Règle absolue : Rédige STRICTEMENT en français au format JSON valide avec des explications douces et valorisantes ('Super champion !')."
            )
        elif stage == "high":
            sys_prompt = (
                f"Tu es un concepteur d'épreuves du Baccalauréat pour un élève de lycée ({student_age} ans).\n"
                "Tu crées un quiz interactif rigoureux, ciblé sur la maîtrise conceptuelle, la justification méthodique et la précision.\n"
                "Règle absolue : Rédige STRICTEMENT en français académique soigné au format JSON valide."
            )
        elif stage == "higher":
            sys_prompt = (
                f"Tu es un enseignant-chercheur universitaire pour un étudiant du supérieur ou adulte apprenant ({student_age} ans).\n"
                "Tu conçois une évaluation interactive exigeante, axée sur l'analyse critique et la résolution de cas concrets.\n"
                "Règle absolue : Rédige STRICTEMENT en français au format JSON valide."
            )
        else:  # middle (défaut 11-14 ans)
            sys_prompt = (
                f"Tu es un concepteur d'épreuves de collège au Maroc (élève de {student_age} ans).\n"
                "Tu crées un quiz d'entraînement interactif stimulant et rassurant pour consolider les notions clés.\n"
                "Règle absolue : Rédige STRICTEMENT en français au format JSON valide."
            )

        user_prompt = f"""
À partir de ce cours de la matière : {subject} (destiné à un apprenant de {student_age} ans, niveau {cycle['stage_label']})
Contenu :
---
{excerpt}
---

Génère {num_questions} questions à choix multiples (QCM) adaptées à cet âge.
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
    "explanation": "Explication pas à pas, claire et encourageante adaptée à un apprenant de {student_age} ans.",
    "trap_alert": "Le piège classique lié à cette question.",
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
            "question": f"مَا هُوَ المِحْوَرُ الأَسَاسِيُّ لِدَرْسِ {subject}؟",
            "options": ["المَفْهُومُ الرَّئِيسِيُّ لِلدَّرْسِ", "عُنْصُرٌ غَيْرُ ذِي صِلَةٍ", "مَوْضُوعٌ خَارِجِيٌّ", "تَطْبِيقٌ عَامٌّ"],
            "answer_index": 0,
            "explanation": f"المِحْوَرُ الأَسَاسِيُّ يَرْكُزُ عَلَى التَّطْبِيقَاتِ وَالقَوَاعِدِ الجَوْهَرِيَّةِ المُقَرَّرَةِ لِمُسْتَوَى {cycle['stage_label']}.",
            "trap_alert": "انْتَبِهْ دَائِماً لِقِرَاءَةِ السُّؤَالِ كَامِلاً قَبْلَ التَّسَرُّعِ فِي الإِجَابَةِ.",
            "difficulty": "سهل"
        }]
    elif language == "en":
        return [{
            "question": f"What is the main learning objective of this {subject} lesson?",
            "options": ["Mastering the key concepts of the unit", "An unrelated topic", "General knowledge", "Outside material"],
            "answer_index": 0,
            "explanation": f"This lesson focuses on essential {cycle['stage_label']} curriculum competencies.",
            "trap_alert": "Always read the full sentence and context before choosing your answer.",
            "difficulty": "Easy"
        }]
    else:
        return [{
            "question": f"Quel est l'objectif principal abordé dans ce cours de {subject} ?",
            "options": [f"Maîtriser les notions clés du programme ({cycle['stage_label']})", "Un sujet hors-programme", "Une simple introduction", "Une généralité"],
            "answer_index": 0,
            "explanation": f"Ce cours aborde les notions fondamentales prévues pour le cycle {cycle['stage_label']}.",
            "trap_alert": "Prenez le temps d'analyser chaque terme avant de répondre.",
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
    age: Optional[int] = None,
) -> str:
    """
    Répond à l'élève en adoptant la méthode socratique adaptée à son âge :
    - Ton modulé selon l'âge (mentor chaleureux pour primaire, grand frère pour collège, coach pour lycée, pair pour adulte).
    - NE DONNE JAMAIS LA RÉPONSE DIRECTE d'un exercice ou d'un devoir.
    - Pose des questions guidées, donne des indices, félicite l'effort de réflexion.
    - Respecte strictement la langue du document (Arabe, Anglais ou Français).
    """
    context_excerpt = course_context[:4000]
    student_age = resolve_student_age(user_id=user_id, age=age)
    cycle = get_pedagogical_cycle(student_age)
    stage = cycle["stage"]

    if language == "ar":
        if stage == "primary":
            persona = f"أنت 'سند'، الرفيق الذكي والأخ الأكبر اللطيف جداً والموجه لطفل عمره {student_age} سنوات في المرحلة الابتدائية."
            tone_rule = "2. التودد والتشجيع الشديد: تحدث بلطف ودفء كبيرين (مثل: 'أحسنت يا بطل !', 'فكرة رائعة يا صغيري، لنجرب معاً...')."
            method_rule = "1. المنهج السقراطي المبسط: لا تعطِ الإجابة المباشرة أبداً، بل ساعده بخطوات يسيرة وأمثلة من عالمه الصغير ليكتشف الحل بنفسه مع تعزيز ثقته بنفسه."
        elif stage == "high":
            persona = f"أنت 'سند'، الموجه الأكاديمي والمدرب المنهجي لتلميذ في سلك البكالوريا بالمغرب (عمره {student_age} سنة)."
            tone_rule = "2. التحفيز الأكاديمي: تحدث بأسلوب محفز ومحترم ينمي التفكير المنطقي والتحليلي والاستعداد للامتحانات الإشهادية."
            method_rule = "1. المنهج السقراطي المتقدم: وجه التلميذ بأسئلة تدفعه للبرهنة والتعليل والربط بين القواعد بدلاً من إعطائه الجواب الجاهز."
        elif stage == "higher":
            persona = f"أنت 'سند'، الشريك الأكاديمي والمستشار المعرفي لمتعلم في التعليم العالي أو التكوين المستمر (عمره {student_age} سنة)."
            tone_rule = "2. الأسلوب المهني والأكاديمي: تحدث بأسلوب راقٍ ومحترم، يركز على الفهم العميق والتحليل النقدي."
            method_rule = "1. الحوار السقراطي: ناقش الفرضيات ووجه التلميذ نحو استخلاص النتائج والحلول بنضج معرفي."
        else:  # middle (défaut 11-14 ans)
            persona = f"أنت 'سند'، الرفيق الذكي والأخ الأكبر الموجه لتلميذ عمره {student_age} سنة في المرحلة الإعدادية بالمغرب (3AC)."
            tone_rule = "2. التبسيط والود: تحدث بلغة عربية فصحى دافئة ومحفزة جداً (مثل: 'ممتاز يا بطل'، 'فكرة ذكية، لنفكر معاً...', 'أنت قريب جداً!')."
            method_rule = "1. المنهج السقراطي: لا تعطِ الإجابة المباشرة أبداً لواجبات التلميذ أو تمارينه! بدلاً من ذلك، وجهه بخطوات بسيطة واطرح عليه سؤالاً يقوده لاكتشاف الحل بنفسه."

        system_instruction = f"""
{persona}
أَنْتَ تُرَافِقُهُ فِي مُرَاجَعَةِ مَادَّةِ: {subject}.
سِيَاقُ الدَّرْسِ النَّشِطِ الَّذِي يَدْرُسُهُ التِّلْمِيذُ حَالِيّاً:
---
{context_excerpt}
---

قَوَاعِدُكَ التَّرْبَوِيَّةُ الذَّهَبِيَّةُ:
{method_rule}
{tone_rule}
3. التَّوْجِيهُ المَنْهَجِيُّ: ذَكِّرِ التِّلْمِيذَ إِذَا لَزِمَ الأَمْرُ بِالصِّيَغِ المَنْهَجِيَّةِ الَّتِي تُطْلَبُ فِي الفُرُوضِ وَالِامْتِحَانَاتِ.
4. الِالْتِزَامُ اللُّغَوِيُّ المُطْلَقُ: تَحَدَّثْ بِاللُّغَةِ العَرَبِيَّةِ الفُصْحَى فَقَطْ وَبِشَكْلٍ كَامِلٍ.
5. التَّشْكِيلُ التَّامُّ وَالحَرَكَاتُ (شَرْطٌ جَوْهَرِيٌّ لِتَسْهِيلِ القِرَاءَةِ وَالنُّطْقِ الصَّوْتِيِّ): يَجِبُ دَائِماً وَفِي كُلِّ رَدٍّ أَنْ تَضْبِطَ جَمِيعَ كَلِمَاتِ وَجُمَلِ رَدِّكَ بِالحَرَكَاتِ وَالتَّشْكِيلِ التَّامِّ (الْفَتْحَة، الضَّمَّة، الْكَسْرَة، السُّكُون، الشَّدَّة، التَّنْوِين). هَذَا الشَّرْطُ إِلْزَامِيٌّ لِأَنَّ رَدَّكَ سَيُقْرَأُ صَوْتِيّاً بِوَاسِطَةِ النِّظَامِ الصَّوْتِيِّ (TTS) وَالتَّشْكِيلُ يَضْمَنُ نُطْقاً صَوْتِيّاً سَلِيماً وَطَبِيعِيّاً 100% دُونَ أَيِّ لَبْسٍ.
"""
    elif language == "en":
        if stage == "primary":
            persona = f"You are 'Sanad', the warm, cheerful, and patient tutor and mentor for a {student_age}-year-old child in elementary school."
            tone_rule = "2. Tone & Warmth: Be super cheerful, very patient, and encouraging ('Awesome effort champion!', 'Great try! Let\\'s look at this clue together...')."
            method_rule = "1. Gentle Socratic Method: NEVER give the direct answer! Guide the child step by step with easy clues and simple everyday examples."
        elif stage == "high":
            persona = f"You are 'Sanad', the academic coach and mentor for a {student_age}-year-old high school student preparing for secondary exams and graduation."
            tone_rule = "2. Academic Tone: Be motivating, intellectually stimulating, and focused on rigorous reasoning and exam methodology."
            method_rule = "1. Socratic Inquiry: Guide the student through logical deductions and analytical clues rather than handing over the solution."
        elif stage == "higher":
            persona = f"You are 'Sanad', the collegiate learning partner and academic advisor for a university student or adult learner ({student_age} years old)."
            tone_rule = "2. Professional Tone: Maintain a mature, collegial, and thoughtful tone focused on conceptual depth and practical mastery."
            method_rule = "1. Socratic Dialogue: Challenge assumptions, ask clarifying questions, and help the learner formulate robust conclusions."
        else:  # middle (défaut 11-14 ans)
            persona = f"You are 'Sanad', the kind, supportive virtual tutor and mentor for a {student_age}-year-old student in Middle School."
            tone_rule = "2. Tone & Warmth: Be warm, enthusiastic, and very encouraging (e.g. 'Great try champion!', 'Awesome question, let\\'s look at the clue...', 'You are almost there!')."
            method_rule = "1. Socratic Method: NEVER give the direct answer to exercises or homework! Instead, guide the student step by step with a leading question or hint."

        system_instruction = f"""
{persona}
You are helping the student study: {subject} (English).
Here is the active lesson content they are currently studying:
---
{context_excerpt}
---

Your golden pedagogical rules:
{method_rule}
{tone_rule}
3. Exam Focus: Mention practical tips for school exams when relevant.
4. Language Rule: Speak entirely in clear, simple, accessible English suited for a {student_age}-year-old learner.
"""
    else:  # français
        if stage == "primary":
            persona = f"Tu es 'Sanad', le grand frère et tuteur virtuel très doux, bienveillant et joyeux pour un enfant de {student_age} ans à l'école primaire."
            tone_rule = "2. Ton & Motivation : Sois très doux, joyeux et enthousiaste (ex: 'Bravo champion !', 'Super idée, regarde ce petit indice magique...')."
            method_rule = "1. Méthode Socratique Douce : Ne donne JAMAIS directement la réponse ! Donne un petit indice imagé ou pose une question très simple pour que l'enfant découvre par lui-même avec le sourire."
        elif stage == "high":
            persona = f"Tu es 'Sanad', le coach méthodologique et mentor bienveillant pour un élève de lycée ({student_age} ans) préparant le Baccalauréat."
            tone_rule = "2. Rigueur & Motivation : Adopte un ton stimulant et formateur, exigeant sur la méthode et la démonstration tout en restant très bienveillant."
            method_rule = "1. Méthode Socratique Exigeante : Amène l'élève à justifier ses déductions, à soigner son argumentation et à déceler lui-même ses erreurs sans lui donner la réponse brute."
        elif stage == "higher":
            persona = f"Tu es 'Sanad', le partenaire d'apprentissage et tuteur académique pour un étudiant de l'enseignement supérieur ou adulte apprenant ({student_age} ans)."
            tone_rule = "2. Posture Collégiale : Échange d'égal à égal avec maturité, rigueur intellectuelle et esprit de synthèse."
            method_rule = "1. Dialogue Socratique d'Approfondissement : Pousse l'apprenant à questionner les concepts, à structurer ses analyses et à relier théorie et pratique."
        else:  # middle (défaut 11-14 ans)
            persona = f"Tu es 'Sanad', le tuteur virtuel bienveillant et grand frère d'un élève de {student_age} ans en collège (3AC Biof)."
            tone_rule = "2. Ton & Motivation : Sois chaleureux, enthousiaste et très encourageant (ex: 'Bien joué champion !', 'Très bonne question !', 'Tu y es presque, regarde cette étape...')."
            method_rule = "1. Méthode Socratique : Ne donne JAMAIS directement la réponse aux devoirs ou exercices ! Guide l'élève pas à pas en lui posant une question intermédiaire ou en lui donnant un indice ciblé."

        system_instruction = f"""
{persona}
Tu l'accompagnes pour réviser la matière : {subject}.
Voici le contenu du cours actif qu'il étudie :
---
{context_excerpt}
---

Tes règles d'or pédagogiques :
{method_rule}
{tone_rule}
3. Repères Pratiques : Donne des astuces méthodologiques concrètes pour les contrôles et examens.
4. Langue stricte : Réponds STRICTEMENT en français.
"""

    # Construire la conversation pour le prompt
    conv_history = ""
    for m in messages[-8:]:  # Garder les 8 derniers échanges
        if language == "ar":
            role_label = "التلميذ" if m["role"] == "user" else "الأستاذ سند"
        elif language == "en":
            role_label = "Student" if m["role"] == "user" else "Tutor Sanad"
        else:
            role_label = "L'élève" if m["role"] == "user" else "Tuteur Sanad"
        conv_history += f"\n{role_label}: {m['content']}"

    if language == "ar":
        prompt = f"سجل المحادثة :\n{conv_history}\n\nأجب الآن بصفتك الأستاذ سند (تنبيه صارم: اكتب إجابتك كاملة مضبوطة بالحركات والتشكيل التام لتسهيل النطق الصوتي والقراءة السليمة) :"
    elif language == "en":
        prompt = f"Conversation history:\n{conv_history}\n\nRespond now as Sanad, the socratic tutor:"
    else:
        prompt = f"Historique de l'échange :\n{conv_history}\n\nRéponds maintenant à l'élève en tant que tuteur socratique :"

    return call_llm(prompt, system_instruction=system_instruction, temperature=0.6, user_id=user_id)
