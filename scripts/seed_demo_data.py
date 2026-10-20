"""
Script de peuplement initial avec des données de démonstration réelles pour le Brevet 3AC Maroc.
Crée deux cours types (Mathématiques Biof en Français, et Éducation Islamique en Arabe),
avec leurs fiches express, quiz interactifs et messages du tuteur.
"""

import hashlib
import os
import sys
from pathlib import Path

BASE_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(BASE_DIR))

import pypdf

from models.database import (
    add_chat_message,
    init_db,
    save_course,
    save_quiz,
    save_quiz_attempt,
)

BASE_DIR = Path(__file__).parent.parent
STORAGE_DIR = BASE_DIR / "storage"
COURSES_DIR = STORAGE_DIR / "cours"


def create_sample_pdf(file_path: Path) -> str:
    """Crée un fichier PDF valide et retourne son empreinte SHA-256."""
    writer = pypdf.PdfWriter()
    writer.add_blank_page(width=595, height=842)
    with open(file_path, "wb") as f:
        writer.write(f)

    with open(file_path, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


def seed_data() -> None:
    init_db()
    COURSES_DIR.mkdir(parents=True, exist_ok=True)

    print("🚀 Initialisation des cours exemples 3AC Maroc...")

    # -----------------------------------------------------------------------
    # 1. COURS MATHÉMATIQUES BIOF (FRANÇAIS)
    # -----------------------------------------------------------------------
    math_pdf = COURSES_DIR / "Exemple_Maths_3AC_Theoreme_Thales.pdf"
    math_hash = create_sample_pdf(math_pdf)

    math_raw_text = """Royaume du Maroc - Ministère de l'Éducation Nationale
Collège - Troisième Année de Collège (3AC) - Section Internationale (Biof)
Matière : Mathématiques
Chapitre : Le Théorème de Thalès (Direct et Réciproque)

I. Théorème direct de Thalès :
Soient (d1) et (d2) deux droites sécantes en un point A.
Soient B et M deux points de la droite (d1), distincts de A.
Soient C et N deux points de la droite (d2), distincts de A.
Si la droite (MN) est strictement parallèle à la droite (BC), alors :
AM / AB = AN / AC = MN / BC.

Condition indispensable à l'examen normalisé :
Toujours vérifier et citer explicitement l'alignement des points dans le même ordre et le parallélisme des droites avant d'appliquer l'égalité des rapports.

II. Théorème réciproque de Thalès :
Soient (d1) et (d2) deux droites sécantes en A.
B et M appartiennent à (d1), C et N appartiennent à (d2).
Si les points A, M, B d'une part et les points A, N, C d'autre part sont alignés dans le même ordre,
et si AM / AB = AN / AC, alors les droites (MN) et (BC) sont parallèles.
Utilisation principale à l'examen : Démontrer que deux droites sont parallèles.
"""

    math_summary = """## 🎯 Définitions & Notions Incontournables
- **Théorème Direct de Thalès :** Utilisé pour **calculer des longueurs inconnues** dans une configuration de triangles emboîtés ou en forme de "papillon" (sablier) dès que deux droites sont parallèles.
- **Théorème Réciproque de Thalès :** Utilisé exclusivement pour **démontrer que deux droites sont parallèles** en comparant deux rapports de longueurs.

## 📌 Formules Clés à Retenir
Si $(MN) // (BC)$ avec $A, M, B$ et $A, N, C$ alignés :
$$\\frac{AM}{AB} = \\frac{AN}{AC} = \\frac{MN}{BC}$$
- **Règle du produit en croix :** Pour trouver $AN$, on utilise : $AN = \\frac{AM \\times AC}{AB}$.

## ⚠️ Les Pièges Fréquents à l'Examen Normalisé
1. **Oublier l'ordre des points :** Dans la réciproque de Thalès, le correcteur retire des points si tu n'écris pas : *"Les points A, M, B et A, N, C sont alignés dans le même ordre"*.
2. **Confondre direct et réciproque :** N'utilise JAMAIS la réciproque pour calculer une longueur !
3. **Erreur de rapport :** Attention à toujours mettre les longueurs du petit triangle au numérateur et celles du grand triangle au dénominateur (ne pas mélanger).

## 💡 L'Astuce Rédaction pour Gagner des Points
Commence toujours ta rédaction par les 3 conditions :
1. *"Dans le triangle ABC..."*
2. *"$M \\in [AB]$ et $N \\in [AC]$..."*
3. *"Puisque $(MN) // (BC)$, d'après le théorème direct de Thalès..."*
"""

    math_concepts = ["Théorème direct de Thalès", "Théorème réciproque", "Parallélisme", "Produit en croix", "Alignement"]

    math_course_id = save_course(
        title="Théorème de Thalès direct et réciproque",
        subject="Mathématiques",
        language="fr",
        file_path=str(math_pdf),
        file_hash=math_hash,
        file_name="Exemple_Maths_3AC_Theoreme_Thales.pdf",
        raw_text=math_raw_text,
        summary_markdown=math_summary,
        key_concepts=math_concepts,
    )

    math_quiz_data = [
        {
            "question": "À quoi sert principalement le théorème DIRECT de Thalès dans un problème d'examen ?",
            "options": [
                "À calculer des longueurs inconnues",
                "À démontrer que deux droites sont parallèles",
                "À calculer la mesure d'un angle aigu",
                "À démontrer qu'un triangle est rectangle"
            ],
            "answer_index": 0,
            "explanation": "Le théorème direct permet de déterminer des longueurs manquantes grâce à l'égalité des trois rapports.",
            "trap_alert": "Ne confonds pas avec la réciproque qui sert à prouver le parallélisme.",
            "difficulty": "Facile"
        },
        {
            "question": "Dans un triangle ABC, M est sur [AB] et N sur [AC] avec (MN) // (BC). Si AB = 6 cm, AM = 2 cm et AC = 9 cm, que vaut AN ?",
            "options": [
                "3 cm",
                "4,5 cm",
                "2 cm",
                "5 cm"
            ],
            "answer_index": 0,
            "explanation": "D'après Thalès, AM/AB = AN/AC soit 2/6 = AN/9. Par produit en croix : AN = (2 * 9) / 6 = 18 / 6 = 3 cm.",
            "trap_alert": "Attention à ne pas diviser par la mauvaise longueur !",
            "difficulty": "Moyen"
        },
        {
            "question": "Quelle condition essentielle doit être obligatoirement mentionnée pour appliquer la RÉCIPROQUE de Thalès ?",
            "options": [
                "L'alignement des points dans le même ordre",
                "Le triangle doit avoir un angle droit",
                "Les longueurs doivent être des entiers",
                "Les droites doivent être perpendiculaires"
            ],
            "answer_index": 0,
            "explanation": "La réciproque exige impérativement que les points soient alignés dans le même ordre sur les deux droites sécantes.",
            "trap_alert": "Les correcteurs de l'examen régional pénalisent sévèrement l'omission de cette phrase.",
            "difficulty": "Moyen"
        },
        {
            "question": "Si AM/AB = 0,4 et AN/AC = 0,4, que peut-on déduire si les points sont alignés dans le même ordre ?",
            "options": [
                "Les droites (MN) et (BC) sont parallèles",
                "Le triangle ABC est isocèle",
                "L'aire du triangle est doublée",
                "Les droites (MN) et (BC) sont sécantes"
            ],
            "answer_index": 0,
            "explanation": "Puisque les rapports sont égaux et les points alignés dans le même ordre, la réciproque de Thalès prouve que (MN) // (BC).",
            "trap_alert": "Pense bien à calculer séparément les deux rapports avant de conclure à leur égalité.",
            "difficulty": "Facile"
        },
        {
            "question": "Dans une configuration de Thalès en 'papillon' (ou sablier), où se trouve le sommet commun A ?",
            "options": [
                "Entre les deux droites parallèles, au point d'intersection",
                "À l'extérieur des deux sécantes",
                "Sur la droite (BC)",
                "Au milieu du segment [MN]"
            ],
            "answer_index": 0,
            "explanation": "Dans la configuration croisée en papillon, le point d'intersection A est situé entre les deux droites parallèles.",
            "trap_alert": "Attention au sens des vecteurs ou segments : le rapport part toujours du sommet commun A.",
            "difficulty": "Avancé"
        }
    ]
    math_qid = save_quiz(math_course_id, math_quiz_data)

    # Tentative d'exemple pour afficher les stats
    save_quiz_attempt(
        course_id=math_course_id,
        quiz_id=math_qid,
        score=4,
        total_questions=5,
        answers={0: 0, 1: 0, 2: 0, 3: 0, 4: 1},
    )

    add_chat_message(
        math_course_id,
        "assistant",
        "Bonjour ! Je suis Sanad, ton tuteur pour les maths de 3AC. As-tu une question sur le théorème de Thalès ou sur la méthode de rédaction pour l'examen normalisé ?",
    )

    # -----------------------------------------------------------------------
    # 2. COURS ÉDUCATION ISLAMIQUE (ARABE)
    # -----------------------------------------------------------------------
    islamic_pdf = COURSES_DIR / "Exemple_Islamique_3AC_Sourate_Al_Hachr.pdf"
    islamic_hash = create_sample_pdf(islamic_pdf)

    islamic_raw_text = """المملكة المغربية - وزارة التربية الوطنية والتعليم الأولي والرياضة
الثالثة ثانوي إعدادي (3AC)
المادة: التربية الإسلامية
مدخل التزكية: القرآن الكريم (سورة الحشر) والعقيدة (الإيمان والغيب)

أولاً: سورة الحشر (الآيات 1 إلى 7)
- سبب النزول: نزلت في إجلاء يهود بني النضير بعد نقضهم العهد مع رسول الله صلى الله عليه وسلم بالمدينة المنورة.
- تسمى سورة الحشر أيضاً "سورة بني النضير".
- القضايا الأساسية:
  1. تسبيح سائر المخلوقات لله عز وجل (العزيز الحكيم).
  2. قدرة الله تعالى على معاقبة المعتدين وإلقاء الرعب في قلوبهم: (فَأَتَاهُمُ اللَّهُ مِنْ حَيْثُ لَمْ يَحْتَسِبُوا وَقَذَفَ فِي قُلُوبِهِمُ الرُّعْبَ).
  3. الاعتبار بمصير الظالمين: (فَاعْتَبِرُوا يَا أُولِي الأَبْصَارِ).
  4. حكم الفيء وتوزيعه: ألا يكون دولة بين الأغنياء، بل يعطى للفقراء والمساكين وابن السبيل.
  5. مبدأ وجوب طاعة الرسول صلى الله عليه وسلم: (وَمَا آتَاكُمُ الرَّسُولُ فَخُذُوهُ وَمَا نَهَاكُمْ عَنْهُ فَانْتَهُوا).

ثانياً: الإيمان والغيب
- تعريف الغيب: كل ما غاب عن حواس الإنسان وإدراكه مما لا يعلمه إلا الله، أو ما أخبر به رسوله عبر الوحي الصادق.
- أثر الإيمان بالغيب: الشعور بالطمأنينة ومراقبة الله تعالى في السر والعلن والاستقامة على الأخلاق الفاضلة.
"""

    islamic_summary = """## 🎯 المفاهيم والتعاريف الأساسية (التي تتكرر في الامتحان)
- **سورة الحشر :** سورة مدنية، تسمى أيضاً "سورة بني النضير"، تعالج قضايا العقيدة وغزوة بني النضير وأحكام توزيع أموال الفيء.
- **الفيء :** هو كل مال أُخذ من الكفار دون قتال ولا إيجاف خيل ولا ركاب، ويوزع على مصالح المسلمين والفقراء.
- **الإيمان بالغيب :** التصديق الجازم بكل ما أخبر به الله ورسوله مما غاب عن إدراك الحواس كالملائكة واليوم الآخر والجنة والنار.

## 📌 القواعد الذهبية والآيات المفتاحية
- **قاعدة توزيع الفيء :** قال تعالى: ﴿كَيْ لَا يَكُونَ دُولَةً بَيْنَ الْأَغْنِيَاءِ مِنكُمْ﴾ (الحرص على التضامن الاجتماعي ومنع احتكار الثروة).
- **قاعدة وجوب الطاعة والاتباع :** قال تعالى: ﴿وَمَا آتَاكُمُ الرَّسُولُ فَخُذُوهُ وَمَا نَهَاكُمْ عَنْهُ فَانتَهُوا﴾.
- **أثر الإيمان بالغيب :** يولد في نفس المؤمن استشعار مراقبة الله في السر والعلن وتحقيق الاستقامة.

## ⚠️ فخاخ الامتحان الموحد (أخطاء شائعة)
1. **الخلط بين الغيب النسبي والغيب المطلق :** الغيب المطلق يستأثر الله بعلمه وحده (مثل موعد الساعة)، بينما الغيب النسبي يعلمه بعض الخلق ويغيب عن بعض.
2. **الخلط بين الغنيمة والفيء :** الغنيمة ما أُخذ بقتال وجهاد، والفيء ما أُخذ دون قتال.
3. **نسيان شكل الآيات القرآنية :** احرص على حفظ الآيات المقررة بالرسم العثماني المضبوط لتفادي ضياع نقط التزكية.

## 💡 نصيحة التحرير لضمان النقطة الكاملة
عند إجابتك عن أسئلة الوضعية التقويمية، ابدأ دائماً بذكر **المفهوم الشرعي**، ثم عززه بـ **الاستدلال الشرعي المناسب (آية من سورة الحشر أو حديث شريف)**.
"""

    islamic_concepts = ["سورة الحشر", "بنو النضير", "الفيء", "الإيمان بالغيب", "الاستدلال الشرعي"]

    islamic_course_id = save_course(
        title="سورة الحشر : مدخل التزكية والعقيدة",
        subject="التربية الإسلامية",
        language="ar",
        file_path=str(islamic_pdf),
        file_hash=islamic_hash,
        file_name="Exemple_Islamique_3AC_Sourate_Al_Hachr.pdf",
        raw_text=islamic_raw_text,
        summary_markdown=islamic_summary,
        key_concepts=islamic_concepts,
    )

    islamic_quiz_data = [
        {
            "question": "ما هو الاسم الآخر لسورة الحشر الذي كان يطلقه عليها الصحابي عبد الله بن عباس رضي الله عنه؟",
            "options": [
                "سورة بني النضير",
                "سورة القتال",
                "سورة الأحزاب",
                "سورة الفتح"
            ],
            "answer_index": 0,
            "explanation": "تسمى سورة بني النضير لأنها نزلت في شأن إجلاء يهود بني النضير بعد نقضهم العهد مع رسول الله.",
            "trap_alert": "سؤال كلاسيكي جداً في الامتحانات الموحدة للثالثة إعدادي.",
            "difficulty": "سهل"
        },
        {
            "question": "ما الفرق الشرعي الدقيق بين 'الفيء' و 'الغنيمة' المقررة في منهاج 3AC؟",
            "options": [
                "الفيء يؤخذ بدون قتال، بينما الغنيمة تؤخذ بقتال وجهاد",
                "الفيء خاص بالأغنياء فقط والغنيمة للفقراء",
                "لا يوجد أي فرق بينهما فهما مترادفان تماماً",
                "الغنيمة توزع بالتساوي بين الكفار والمسلمين"
            ],
            "answer_index": 0,
            "explanation": "الفيء هو المال الذي أفاءه الله على رسوله من غير قتال ولا إيجاف خيل، بخلاف الغنيمة.",
            "trap_alert": "انتبه لتحديد شرط 'بدون قتال' في إجابتك للحصول على النقطة كاملة.",
            "difficulty": "مقدمة ومتوسط"
        },
        {
            "question": "ما هي الحكمة الاجتماعية والاقتصادية لتوزيع الفيء كما بينها قوله تعالى: ﴿كَيْ لَا يَكُونَ دُولَةً بَيْنَ الْأَغْنِيَاءِ مِنكُمْ﴾؟",
            "options": [
                "منع احتكار الثروة وتحقيق العدالة والتكافل الاجتماعي",
                "تشجيع الادخار الفردي للأغنياء",
                "إلغاء التجارة بين الناس",
                "حرمان الفقراء من المساعدة"
            ],
            "answer_index": 0,
            "explanation": "المقصد هو تداول المال بين كافة طبقات المجتمع وخاصة المحتاجين لمنع تركز الثروة في فئة قليلة.",
            "trap_alert": "دائماً اربط الآية بمفهوم 'منع احتكار الثروة'.",
            "difficulty": "متوسط"
        },
        {
            "question": "ما نوع الغيب الذي يستأثر الله عز وجل بعلمه وحده ولا يُطلع عليه أحداً من خلقه؟",
            "options": [
                "الغيب المطلق (مثل وقت قيام الساعة)",
                "الغيب النسبي",
                "الغيب الحاضر المشاهد",
                "الغيب العلمي"
            ],
            "answer_index": 0,
            "explanation": "الغيب المطلق هو ما انفرد الله بعلمه ولم يظهره لأحد من خلقه كأجل الإنسان ووقت قيام الساعة.",
            "trap_alert": "لا تخلط بين الغيب النسبي (الذي يعلمه البعض دون البعض) والغيب المطلق.",
            "difficulty": "سهل"
        },
        {
            "question": "ما الآية القرآنية من سورة الحشر الدالة على وجوب طاعة النبي صلى الله عليه وسلم في كل ما أمر به ونهى عنه؟",
            "options": [
                "﴿وَمَا آتَاكُمُ الرَّسُولُ فَخُذُوهُ وَمَا نَهَاكُمْ عَنْهُ فَانتَهُوا﴾",
                "﴿هُوَ الَّذِي أَخْرَجَ الَّذِينَ كَفَرُوا مِنْ أَهْلِ الْكِتَابِ﴾",
                "﴿مَا قَطَعْتُم مِّن لِّينَةٍ أَوْ تَرَكْتُمُوهَا قَائِمَةً﴾",
                "﴿فَاعْتَبِرُوا يَا أُولِي الأَبْصَارِ﴾"
            ],
            "answer_index": 0,
            "explanation": "هذه الآية الكريمة (الآية 7) هي الأصل القرآني في حجية السنة النبوية ووجوب الامتثال لأوامر الرسول.",
            "trap_alert": "يطلب منك دائماً الاستدلال بهذه الآية في وضعيات الامتحان الموحد.",
            "difficulty": "متوسط"
        }
    ]
    islamic_qid = save_quiz(islamic_course_id, islamic_quiz_data)

    save_quiz_attempt(
        course_id=islamic_course_id,
        quiz_id=islamic_qid,
        score=5,
        total_questions=5,
        answers={0: 0, 1: 0, 2: 0, 3: 0, 4: 0},
    )

    add_chat_message(
        islamic_course_id,
        "assistant",
        "أهلاً بك يا بطل! أنا 'سند' مرافقك في مراجعة التربية الإسلامية للسنة الثالثة إعدادي. هل لديك أي استفسار حول معاني سورة الحشر أو فقه الأسرة أو كيفية الإجابة على الوضعية التقويمية في الامتحان الموحد؟",
    )

    print("✅ Cours exemples initialisés avec succès !")


if __name__ == "__main__":
    seed_data()
