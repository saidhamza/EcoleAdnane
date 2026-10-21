"""
Module d'extraction PDF et de détection de langue et matière pour le référentiel 3AC Maroc.
Détecte avec précision l'Arabe vs Français et classe selon le programme officiel du collège marocain.
"""

import os
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import pypdf

# Plages Unicode Arabes
ARABIC_RANGES = [
    (0x0600, 0x06FF),  # Arabic
    (0x0750, 0x077F),  # Arabic Supplement
    (0x08A0, 0x08FF),  # Arabic Extended-A
    (0xFB50, 0xFDFF),  # Arabic Presentation Forms-A
    (0xFE70, 0xFEFF),  # Arabic Presentation Forms-B
]

# Matières officielles 3AC Maroc
SUBJECTS_FR = [
    "Mathématiques",
    "Physique-Chimie",
    "SVT",
    "Français",
]

SUBJECTS_EN = [
    "Anglais",
]

SUBJECTS_AR = [
    "التربية الإسلامية",
    "الاجتماعيات",
    "اللغة العربية",
]

ALL_SUBJECTS = SUBJECTS_FR + SUBJECTS_AR + SUBJECTS_EN

# Mots-clés représentatifs du programme 3AC Maroc
KEYWORDS_3AC = {
    # Matières Biof (Français)
    "Mathématiques": [
        "théorème de thalès", "thales", "pythagore", "racine carrée", "racines carrées",
        "trigonométrie", "cosinus", "sinus", "tangente", "équation", "équations", "inéquation",
        "inéquations", "système", "vecteur", "vecteurs", "translation", "repère",
        "fonction linéaire", "fonction affine", "statistique", "statistiques", "médiane",
        "géométrie dans l'espace", "pyramide", "cône", "factorisation", "développement",
        "identités remarquables", "triangle rectangle", "cercle circonscrit", "angle inscrit"
    ],
    "Physique-Chimie": [
        "atome", "atomes", "ion", "ions", "électron", "électrons", "noyau", "oxydation",
        "combustion", "dioxygène", "fer", "aluminium", "cuivre", "rouille", "solution acide",
        "solution basique", "ph", "acide chlorhydrique", "hydroxyde de sodium", "ions chlorure",
        "vitesse moyenne", "mouvement", "trajectoire", "référentiel", "force", "forces",
        "équilibre d'un solide", "poids", "masse", "loi d'ohm", "résistance", "intensité",
        "tension", "puissance électrique", "énergie électrique", "joule", "watt"
    ],
    "SVT": [
        "digestion", "aliment", "aliments", "nutriment", "nutriments", "enzymes", "amylase",
        "intestin grêle", "absorption intestinale", "villosité", "carence alimentaire",
        "respiration", "échanges gazeux", "alvéoles pulmonaires", "sang", "hématies",
        "hémoglobine", "cœur", "artère", "veine", "circulation sanguine", "excrétion urinaire",
        "rein", "néphron", "urine", "système nerveux", "cerveau", "moelle épinière", "nerf",
        "neurone", "réflexe", "sensibilité consciente", "motricité volontaire", "muscle",
        "plaque motrice", "microbes", "bactéries", "virus", "immunité", "phagocytose",
        "lymphocyte", "anticorps", "antigène", "sida", "vaccin"
    ],
    "Français": [
        "texte argumentatif", "thèse", "arguments", "connecteurs logiques", "autobiographie",
        "récit de vie", "nouvelle réaliste", "maupassant", "champ lexical", "figures de style",
        "métaphore", "comparaison", "hyperbole", "discours direct", "discours indirect",
        "subordonnée", "cause", "conséquence", "but", "opposition", "concession", "condition"
    ],
    "Anglais": [
        "english", "grammar", "vocabulary", "simple present", "simple past", "present perfect",
        "past simple", "past continuous", "reading comprehension", "listening", "speaking", "writing",
        "adjective", "adverb", "pronoun", "preposition", "dialogue", "conversation",
        "irregular verbs", "modal verbs", "should", "must", "can", "could", "would",
        "comparative", "superlative", "passive voice", "reported speech", "conditional",
        "unit 1", "unit 2", "unit 3", "unit 4", "unit 5", "unit 6", "unit 7", "unit 8",
        "focus", "window on the world", "ticket to english", "student's book", "workbook"
    ],

    # Matières en Arabe
    "التربية الإسلامية": [
        "سورة الحشر", "التزكية", "الاقتداء", "الاستجابة", "القسط", "الحكمة", "العقيدة",
        "الإيمان والغيب", "صلح الحديبية", "فتح مكة", "فقه الأسرة", "الزواج", "الطلاق",
        "رعاية الأطفال", "حق الله", "حق النفس", "حق البيئة", "العفو والتسامح", "الإنفاق",
        "الاعتزاز بالإسلام", "الرسول صلى الله عليه وسلم", "الصحابة", "القرآن الكريم", "الحديث"
    ],
    "الاجتماعيات": [
        "الحرب العالمية الأولى", "الحرب العالمية الثانية", "القضية الفلسطينية", "الصراع العربي الإسرائيلي",
        "النازية", "أدولف هتلر", "الفاشية", "عصبة الأمم", "الأمم المتحدة", "المغرب",
        "الكفاح من أجل الاستقلال", "استكمال الوحدة الترابية", "معاهدة الحماية", "المقاومة المغربية",
        "محمد الخامس", "الحسن الثاني", "وثيقة المطالبة بالاستقلال", "ثورة الملك والشعب",
        "المسيرة الخضراء", "الولايات المتحدة الأمريكية", "قوة عظمى", "قوة اقتصادية", "اليابان",
        "قوة تكنولوجية", "روسيا", "مصر", "نموذج تنموي", "نيجيريا", "التربية على المواطنة",
        "التراث", "الموارد الطبيعية", "تخليق الحياة العامة", "الديمقراطية", "المواطنة"
    ],
    "اللغة العربية": [
        "النصوص القرائية", "مجال القيم الإسلامية", "القيم الوطنية", "المجال الحضاري",
        "المجال الاجتماعي", "المجال السكاني", "المجال الفني", "الدرس اللغوي", "اسم الفاعل",
        "إعمال اسم الفاعل", "صيغ المبالغة", "اسم المفعول", "اسما الزمان والمكان", "اسم الآلة",
        "النسبة", "المعاجم", "التعبير والإنشاء", "السيرة الذاتية", "السيرة الغيرية",
        "الرحلة", "النقد والحكم", "تخيل حكاية", "الطباق", "الجناس", "الاستعارة"
    ],
}


def is_arabic_char(char: str) -> bool:
    """Vérifie si un caractère appartient à l'alphabet arabe."""
    cp = ord(char)
    for start, end in ARABIC_RANGES:
        if start <= cp <= end:
            return True
    return False


FRENCH_STOPWORDS = {
    "le", "la", "les", "un", "une", "des", "du", "de", "dans", "pour", "avec",
    "est", "sont", "et", "qui", "que", "ce", "cette", "ces", "sur", "au", "aux",
    "par", "nous", "vous", "ils", "elles", "pas", "plus", "cours", "matière", "matiere",
    "théorème", "theoreme", "calcul", "exercices", "exercice", "partie", "chapitre"
}

ENGLISH_STOPWORDS = {
    "the", "is", "are", "was", "were", "of", "in", "on", "at", "with", "for",
    "from", "this", "that", "these", "those", "have", "has", "had", "they", "their",
    "them", "what", "when", "where", "which", "why", "how", "and", "but", "not",
    "english", "grammar", "vocabulary", "lesson", "unit", "exercise", "exercises",
    "reading", "writing", "speaking", "listening", "verb", "verbs", "tense", "tenses",
    "present", "past", "future", "simple", "continuous", "perfect"
}


def detect_language(text: str) -> str:
    """
    Détecte rigoureusement la langue dominante du texte.
    Retourne 'ar' pour l'Arabe, 'en' pour l'Anglais ou 'fr' pour le Français.
    """
    if not text or not text.strip():
        return "fr"

    arabic_chars = sum(1 for c in text if is_arabic_char(c))
    latin_chars = sum(1 for c in text if ("a" <= c.lower() <= "z") or c in "éèêëàâäôöûüîïçÉÈÊËÀÂÄÔÖÛÜÎÏÇ")

    total_alpha = arabic_chars + latin_chars
    if total_alpha == 0:
        return "fr"

    arabic_ratio = arabic_chars / total_alpha

    # Si plus de 30% des caractères alphabétiques sont arabes, ou majorité arabe
    if arabic_ratio >= 0.30 or arabic_chars > latin_chars:
        return "ar"

    # Distinction entre Anglais et Français pour les textes en alphabet latin
    all_words = re.findall(r"\b[a-zA-Zà-ÿ]+\b", text.lower())
    french_accents = sum(1 for c in text if c in "éèêëàâäôöûüîïçÉÈÊËÀÂÄÔÖÛÜÎÏÇ")
    fr_score = sum(1 for w in all_words if w in FRENCH_STOPWORDS) + french_accents
    en_score = sum(1 for w in all_words if w in ENGLISH_STOPWORDS)

    if en_score > fr_score and en_score >= 2:
        return "en"
    return "fr"


def extract_text_from_pdf(pdf_path: str, max_pages: int = 50) -> Dict[str, Any]:
    """
    Extrait le texte brut, les métadonnées et le nombre de pages d'un PDF.
    """
    if not os.path.exists(pdf_path):
        raise FileNotFoundError(f"Le fichier PDF n'existe pas : {pdf_path}")

    text_pages: List[str] = []
    total_pages = 0

    try:
        reader = pypdf.PdfReader(pdf_path)
        total_pages = len(reader.pages)
        pages_to_read = min(total_pages, max_pages)

        for i in range(pages_to_read):
            page = reader.pages[i]
            page_text = page.extract_text() or ""
            text_pages.append(page_text.strip())
    except Exception as e:
        # Fallback pdfplumber si disponible
        try:
            import pdfplumber
            with pdfplumber.open(pdf_path) as pdf:
                total_pages = len(pdf.pages)
                pages_to_read = min(total_pages, max_pages)
                for i in range(pages_to_read):
                    pt = pdf.pages[i].extract_text() or ""
                    text_pages.append(pt.strip())
        except Exception:
            raise RuntimeError(f"Impossible de lire le fichier PDF ({e})")

    full_text = "\n\n".join(text_pages).strip()
    detected_lang = detect_language(full_text)

    return {
        "full_text": full_text,
        "page_count": total_pages,
        "language": detected_lang,
        "pages_extracted": len(text_pages),
    }


def classify_subject_heuristic(text: str, language: str) -> Tuple[str, float]:
    """
    Classe heuristiquement la matière 3AC selon les occurrences de mots-clés du programme.
    Retourne (nom_matière, score_confiance).
    """
    text_lower = text.lower()
    if language == "ar":
        subject_candidates = SUBJECTS_AR
    elif language == "en":
        subject_candidates = SUBJECTS_EN
    else:
        subject_candidates = SUBJECTS_FR + SUBJECTS_EN

    best_subject = subject_candidates[0]
    best_score = 0

    for subject in subject_candidates:
        keywords = KEYWORDS_3AC.get(subject, [])
        score = 0
        for kw in keywords:
            # Compter les occurrences
            matches = len(re.findall(re.escape(kw.lower()), text_lower))
            if matches > 0:
                score += matches * (3 if len(kw.split()) > 1 else 1)

        if score > best_score:
            best_score = score
            best_subject = subject

    confidence = min(1.0, best_score / 15.0) if best_score > 0 else 0.2
    return best_subject, confidence


def extract_fallback_title(filename: str, text: str, language: str) -> str:
    """
    Génère un titre lisible à partir du nom de fichier ou de la première ligne pertinente.
    """
    clean_fn = Path(filename).stem.replace("_", " ").replace("-", " ")
    clean_fn = re.sub(r"\s+", " ", clean_fn).strip()

    # Si le nom de fichier est significatif
    if len(clean_fn) >= 5 and not clean_fn.lower().startswith("document") and not clean_fn.isdigit():
        return clean_fn.title()

    # Sinon chercher dans les premières lignes du texte
    lines = [line.strip() for line in text.split("\n") if len(line.strip()) >= 5]
    if lines:
        first_line = lines[0]
        # Limiter à 60 caractères
        return first_line[:60].strip()

    if language == "en":
        return "3AC English Lesson"
    elif language == "ar":
        return "درس الثالثة إعدادي"
    return "Cours 3AC"
