# 🎓 Ecole Adnane — Révision & Préparation au Brevet 3AC (Maroc)

Application web 100% Python propulsée par **Streamlit**, **SQLite** et **Google Gemini (Free Tier)**, spécialement conçue pour un collégien de 14 ans préparant ses examens normalisés (local et régional) de **3ème Année de Collège au Maroc (3AC)**.

---

## 🌟 Points Forts & Spécificités 3AC Maroc

- **Parité linguistique stricte & Rendu RTL (Droite à Gauche) :**
  - **Matières Biof (Français) :** Mathématiques, Physique-Chimie, SVT, Français, Anglais.
  - **Matières en Arabe :** التربية الإسلامية، الاجتماعيات، اللغة العربية.
  - Détection automatique de la langue : les résumés, quiz et tuteurs sont générés **strictement dans la langue du cours**, sans aucun mélange, avec alignement RTL fluide pour l'arabe.
- **Espace de Révision en 4 Onglets par Cours :**
  1. 📄 **Le Document :** Téléchargement du PDF original et consultation du texte extrait balisé.
  2. ⚡ **Fiche Express :** Synthèse ultra-visuelle (Définitions incontournables, Formules/Dates clés, *Pièges fréquents à l'examen normalisé*, Astuce rédaction).
  3. 🎯 **Entraînement Examen :** Quiz interactifs (QCM) avec calcul instantané du score, explications pas à pas et alertes pièges.
  4. 🤖 **Tuteur Virtuel Socratique (Sanad) :** Assistant bienveillant qui guide l'élève étape par étape sans jamais donner les réponses toutes faites des devoirs.
- **Ingestion & Déduplication :**
  - Glisser-déposer de plusieurs PDFs simultanément.
  - Détection automatique des doublons par hachage cryptographique **SHA-256**.
  - Module prêt pour la synchronisation Google Classroom.
- **Configuration sans terminal & Guide 2 minutes :**
  - Formulaire intégré avec masquage de clé et bouton de test de ping immédiat (vert/rouge).
  - Guide interactif pas à pas pour obtenir une clé Gemini 100% gratuite sans carte bancaire sur Google AI Studio.

---

## 🏗️ Architecture du Projet

```
EcoleAdnane/
│
├── app.py                      # Application Streamlit principale avec support RTL et navigation
├── requirements.txt            # Dépendances Python légères
├── .env.example                # Modèle des variables d'environnement
├── README.md                   # Documentation complète
│
├── models/
│   ├── __init__.py
│   └── database.py             # Gestion SQLite (cours, quiz, fiches, scores, messages, réglages)
│
├── services/
│   ├── __init__.py
│   ├── config_manager.py       # Gestion sécurisée des clés API (.env & SQLite) et ping de test
│   ├── pdf_parser.py           # Extraction pypdf, détection linguistique (FR/AR) et heuristiques 3AC
│   ├── downloader.py           # Stockage persistant, SHA-256 déduplication, Classroom API
│   └── ai_engine.py            # Couche LLM unifiée (Gemini / OpenAI), prompts 3AC bilingues
│
└── storage/                    # Stockage local sécurisé
    ├── ecole_adnane.db         # Base de données SQLite
    └── cours/                  # Fichiers PDF originaux
```

---

## 🚀 Installation & Démarrage Rapide

### 1. Cloner ou ouvrir le dossier du projet
```bash
cd /home/syfodias/Projects/EcoleAdnane
```

### 2. Créer et activer un environnement virtuel Python
```bash
python3 -m venv .venv
source .venv/bin/activate
```

### 3. Installer les dépendances
```bash
pip install -r requirements.txt
```

### 4. Lancer l'application Streamlit
```bash
streamlit run app.py
```
L'application s'ouvrira automatiquement dans votre navigateur à l'adresse : `http://localhost:8501`.

---

## 🔑 Configuration de la Clé API (En 2 Minutes)

1. Ouvrez l'application et allez dans l'onglet **⚙️ Configuration & Guide**.
2. Suivez le lien direct vers [Google AI Studio](https://aistudio.google.com/) pour générer une clé d'API gratuite (aucune carte bancaire requise).
3. Collez la clé dans le champ prévu et cliquez sur **💾 Enregistrer la clé**.
4. Cliquez sur **🔍 Tester la connexion** : un badge vert vous confirmera immédiatement que l'IA est prête !

---

## 🧪 Tests Automatisés

Un ensemble complet de tests unitaires et d'intégration est fourni :
```bash
python -m unittest tests/test_core.py
```
Ce test valide la détection linguistique (Arabe / Français), la classification des matières du collège marocain, la déduplication SHA-256, la persistance SQLite et la structure des données.
