"""
Module de gestion vocale pour le tuteur socratique Sanad.
Fournit :
1. Nettoyage de texte pédagogique pour une élocution naturelle (suppression du Markdown, LaTeX, émojis).
2. Synthèse vocale trilingue (Français, Arabe, Anglais) basée sur la Web Speech API native du navigateur.
3. Bouton d'écoute minimaliste sans texte (icône circulaire design à côté du robot).
4. Bouton de dictée vocale (micro) injecté directement sur la barre de saisie à côté du bouton envoyer.
5. Prise en charge de la lecture automatique des réponses de Sanad.
6. Zéro consommation de quota ou de jetons Google Gemini (100% gratuit côté client).
"""

import base64
import hashlib
import html
import io
import json
import logging
import math
import os
import platform
import re
import struct
import sys
import time
import wave
from pathlib import Path
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

_TTS_MEMORY_CACHE: Dict[str, str] = {}
_TROPHY_SOUND_CACHE: Optional[str] = None


def clean_text_for_speech(text: str) -> str:
    """
    Nettoie le texte enrichi (Markdown, LaTeX, HTML, émojis décoratifs)
    pour produire un flux de texte oral fluide, naturel et intelligible pour la synthèse vocale.
    """
    if not text:
        return ""

    s = text

    # 1. Supprimer les blocs de code (``` ... ```)
    s = re.sub(r"```[\s\S]*?```", " ", s)

    # 2. Supprimer les balises HTML (<...>)
    s = re.sub(r"<[^>]+>", " ", s)

    # 3. Remplacer les formules LaTeX display $$ ... $$ par un espace
    s = re.sub(r"\$\$[\s\S]*?\$\$", " ", s)

    # 4. Remplacer les formules LaTeX inline $ ... $ par le texte intérieur
    s = re.sub(r"\$([^\$]+)\$", r"\1", s)

    # 5. Remplacer les liens Markdown [texte](url) par texte
    s = re.sub(r"\[([^\]]+)\]\([^\)]+\)", r"\1", s)

    # 6. Supprimer les marqueurs gras/italique (**texte**, *texte*, __texte__)
    s = re.sub(r"\*\*([^\*]+)\*\*", r"\1", s)
    s = re.sub(r"\*([^\*]+)\*", r"\1", s)
    s = re.sub(r"__([^_\n]+)__", r"\1", s)
    s = re.sub(r"_([^_\n]+)_", r"\1", s)
    s = re.sub(r"~~([^~]+)~~", r"\1", s)

    # 7. Nettoyer les titres Markdown (#, ##, ###) en assurant une ponctuation de fin naturelle
    def _clean_heading(m: re.Match) -> str:
        h = m.group(1).strip()
        if h and not h.endswith((".", "!", "?", ":", ";", "،", "؟", "؛")):
            return h + ". "
        return h + " "
    s = re.sub(r"^\s*#{1,6}\s*(.+)$", _clean_heading, s, flags=re.MULTILINE)

    # 8. Supprimer les listes à puces (- , * , 1. ) en début de ligne
    def _clean_bullet(m: re.Match) -> str:
        b = m.group(1).strip()
        if b and not b.endswith((".", "!", "?", ":", ";", "،", "؟", "؛")):
            return b + ". "
        return b + " "
    s = re.sub(r"^\s*[-*•]\s*(.+)$", _clean_bullet, s, flags=re.MULTILINE)
    s = re.sub(r"^\s*\d+\.\s*(.+)$", _clean_bullet, s, flags=re.MULTILINE)

    # 9. Supprimer les séparateurs horizontaux (--- ou ***)
    s = re.sub(r"^\s*[-*_]{3,}\s*$", "", s, flags=re.MULTILINE)

    # 10. Supprimer les citations Markdown (> ...)
    s = re.sub(r"^\s*>\s*", "", s, flags=re.MULTILINE)

    # 11. Nettoyer les symboles spéciaux et émojis décoratifs qui polluent la diction
    s = re.sub(
        r"[\U00010000-\U0010ffff]|[\u2600-\u26ff]|[\u2700-\u27bf]|[\u2300-\u23ff]",
        "",
        s,
    )

    # 12. Remplacer les sauts de lignes et espaces multiples par un espace unique
    s = re.sub(r"\s+", " ", s).strip()

    return s


def detect_arabic_content(text: str) -> bool:
    """
    Détecte avec certitude si le texte contient des caractères en alphabet arabe.
    Prise en charge des blocs Unicode arabes standard, étendus et présentations.
    """
    if not text:
        return False
    arabic_chars = len(re.findall(r"[\u0600-\u06FF\u0750-\u077F\u08A0-\u08FF\uFB50-\uFDFF\uFE70-\uFEFF]", text))
    latin_chars = len(re.findall(r"[a-zA-Z]", text))
    return arabic_chars >= 6 or arabic_chars > latin_chars


def get_speech_config(language: str) -> Dict[str, str]:
    """Retourne la configuration linguistique (code BCP 47, libellés) selon la matière."""
    lang = (language or "fr").lower().strip()
    if lang == "ar":
        return {
            "lang_code": "ar-SA",
            "play_label": "استمع للشرح",
            "stop_label": "إيقاف",
            "speaking_label": "جاري التحدث...",
            "tooltip_play": "استمع إلى إجابة الأستاذ سَنَد",
            "tooltip_stop": "إيقاف الصوت",
            "dir": "rtl",
            "mic_label": "تحدث بالصوت",
            "mic_tooltip": "تحدث إلى سند (تسجيل صوتي بالمايكروفون)",
            "mic_listening": "جاري الاستماع...",
            "fiche_play": "استمع للبطاقة",
            "fiche_pause": "إيقاف مؤقت",
            "fiche_stop": "إيقاف",
            "fiche_speed": "السرعة",
            "fiche_status_ready": "🎧 جاهز للاستماع الصوتي",
            "fiche_status_reading": "🔊 جاري القراءة",
            "fiche_status_paused": "⏸️ متوقف مؤقتاً",
            "fiche_status_done": "✅ اكتملت قراءة البطاقة",
        }
    elif lang == "en":
        return {
            "lang_code": "en-US",
            "play_label": "Listen to Sanad",
            "stop_label": "Stop",
            "speaking_label": "Speaking...",
            "tooltip_play": "Listen to Sanad's response",
            "tooltip_stop": "Stop speaking",
            "dir": "ltr",
            "mic_label": "Speak to Sanad",
            "mic_tooltip": "Speak to Sanad (Microphone dictation)",
            "mic_listening": "Listening...",
            "fiche_play": "Listen to Sheet",
            "fiche_pause": "Pause",
            "fiche_stop": "Stop",
            "fiche_speed": "Speed",
            "fiche_status_ready": "🎧 Ready for audio playback",
            "fiche_status_reading": "🔊 Reading aloud",
            "fiche_status_paused": "⏸️ Paused",
            "fiche_status_done": "✅ Reading completed",
        }
    else:
        return {
            "lang_code": "fr-FR",
            "play_label": "Écouter l'explication",
            "stop_label": "Arrêter",
            "speaking_label": "Sanad parle...",
            "tooltip_play": "Écouter la réponse de Sanad",
            "tooltip_stop": "Arrêter la voix",
            "dir": "ltr",
            "mic_label": "Parler à Sanad",
            "mic_tooltip": "Parler à Sanad (Dictée vocale au micro)",
            "mic_listening": "Écoute en cours...",
            "fiche_play": "Écouter la fiche",
            "fiche_pause": "Pause",
            "fiche_stop": "Arrêter",
            "fiche_speed": "Vitesse",
            "fiche_status_ready": "🎧 Prêt pour la lecture vocale",
            "fiche_status_reading": "🔊 Lecture en cours",
            "fiche_status_paused": "⏸️ En pause",
            "fiche_status_done": "✅ Lecture terminée",
        }


# SVG Icons
SVG_SPEAKER = """<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polygon points="11 5 6 9 2 9 2 15 6 15 11 19 11 5"></polygon><path d="M15.54 8.46a5 5 0 0 1 0 7.07"></path><path d="M19.07 4.93a10 10 0 0 1 0 14.14"></path></svg>"""
SVG_STOP = """<svg width="13" height="13" viewBox="0 0 24 24" fill="currentColor"><rect x="5" y="5" width="14" height="14" rx="2" ry="2"></rect></svg>"""
SVG_PLAY = """<svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor"><polygon points="6 3 20 12 6 21 6 3"></polygon></svg>"""
SVG_PAUSE = """<svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor"><rect x="6" y="4" width="4" height="16" rx="1"></rect><rect x="14" y="4" width="4" height="16" rx="1"></rect></svg>"""
SVG_MIC = """<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 1a3 3 0 0 0-3 3v8a3 3 0 0 0 6 0V4a3 3 0 0 0-3-3z"></path><path d="M19 10v2a7 7 0 0 1-14 0v-2"></path><line x1="12" y1="19" x2="12" y2="23"></line><line x1="8" y1="23" x2="16" y2="23"></line></svg>"""


def is_linux_platform() -> bool:
    """
    Vérifie si le serveur de l'application s'exécute sous un système d'exploitation Linux.
    Permet d'activer la génération audio côté serveur car les navigateurs sous Linux
    ne disposent généralement pas de voix Web Speech API intégrées.
    """
    return sys.platform.startswith("linux") or platform.system().lower() == "linux"


def get_server_tts_audio_base64(text: str, language: str = "fr") -> Optional[str]:
    """
    Génère un flux audio MP3 encodé en base64 via gTTS côté serveur.
    Coût : 0 token / 0 quota Gemini (utilise l'API publique Google Translate TTS).
    Met en cache les résultats en mémoire vive (hash SHA256) pour une latence quasi-nulle lors des réécoutes.
    """
    if not text or not text.strip():
        return None

    cleaned = clean_text_for_speech(text)
    if not cleaned:
        return None

    if detect_arabic_content(cleaned):
        gtts_lang = "ar"
    else:
        lang = (language or "fr").lower().strip()
        gtts_lang = "ar" if lang.startswith("ar") else ("en" if lang.startswith("en") else "fr")

    cache_key = hashlib.sha256(f"{gtts_lang}:{cleaned}".encode("utf-8")).hexdigest()
    if cache_key in _TTS_MEMORY_CACHE:
        return _TTS_MEMORY_CACHE[cache_key]

    try:
        from gtts import gTTS
    except ImportError:
        logger.warning("gTTS n'est pas installé dans l'environnement Python.")
        return None

    try:
        mp3_fp = io.BytesIO()
        tts = gTTS(text=cleaned, lang=gtts_lang, slow=False)
        tts.write_to_fp(mp3_fp)
        mp3_fp.seek(0)
        b64_audio = base64.b64encode(mp3_fp.read()).decode("ascii")
        data_uri = f"data:audio/mp3;base64,{b64_audio}"

        if len(_TTS_MEMORY_CACHE) > 200:
            first_key = next(iter(_TTS_MEMORY_CACHE))
            _TTS_MEMORY_CACHE.pop(first_key, None)

        _TTS_MEMORY_CACHE[cache_key] = data_uri
        return data_uri
    except Exception as e:
        logger.warning(f"Échec de la génération audio serveur gTTS : {e}")
        return None


def _generate_server_audio_player_html(
    data_uri: str,
    language: str = "fr",
    player_id: str = "sanad_voice",
    rate: float = 1.0,
    compact: bool = True,
    auto_play: bool = False,
) -> str:
    """
    Génère le lecteur audio HTML5 autonome pour la lecture des flux audio MP3 générés côté serveur.
    Offre une interface et des animations strictement identiques au lecteur Web Speech API client.
    """
    cfg = get_speech_config(language)
    tooltip_play = cfg["tooltip_play"]
    tooltip_stop = cfg["tooltip_stop"]
    direction = cfg["dir"]
    clean_id = re.sub(r"[^a-zA-Z0-9_]", "_", player_id)

    if compact:
        btn_content = SVG_SPEAKER
        btn_style = (
            "display: inline-flex; align-items: center; justify-content: center; "
            "width: 32px; height: 32px; border-radius: 8px; "
            "color: #2563eb; background: #eff6ff; border: 1px solid #bfdbfe; "
            "cursor: pointer; transition: all 0.2s ease; padding: 0; box-shadow: 0 1px 2px rgba(0,0,0,0.05);"
        )
    else:
        btn_content = f"{SVG_SPEAKER} <span id='label_{clean_id}' style='margin-left: 6px; margin-right: 6px;'>{cfg['play_label']}</span>"
        btn_style = (
            "display: inline-flex; align-items: center; justify-content: center; gap: 6px; "
            "padding: 5px 14px; height: 32px; font-size: 12.5px; font-weight: 500; "
            "color: #1e40af; background: #eff6ff; border: 1px solid #bfdbfe; "
            "border-radius: 16px; cursor: pointer; transition: all 0.2s cubic-bezier(0.4, 0, 0.2, 1); "
            "box-shadow: 0 1px 2px rgba(37, 99, 235, 0.08); -webkit-tap-highlight-color: transparent;"
        )

    justify_style = "flex-end" if direction == "rtl" else "flex-start"

    html_code = f"""
    <div id="wrapper_{clean_id}" style="display: flex; align-items: center; justify-content: {justify_style}; margin: 3px 0 0 0; padding: 0; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; direction: {direction};">
      <style>
        #btn_{clean_id}:hover {{
          transform: translateY(-1px);
          background: #dbeafe !important;
          border-color: #93c5fd !important;
        }}
        @keyframes pulseAudio_{clean_id} {{
          0% {{ box-shadow: 0 0 0 0 rgba(220, 38, 38, 0.35); }}
          70% {{ box-shadow: 0 0 0 6px rgba(220, 38, 38, 0); }}
          100% {{ box-shadow: 0 0 0 0 rgba(220, 38, 38, 0); }}
        }}
        .speaking-active_{clean_id} {{
          animation: pulseAudio_{clean_id} 1.6s infinite;
        }}
        @keyframes soundWave_{clean_id} {{
          0% {{ height: 3px; }}
          100% {{ height: 12px; }}
        }}
        .wave-bars_{clean_id} {{
          display: inline-flex;
          align-items: center;
          gap: 2px;
          height: 12px;
          margin: 0 4px;
        }}
        .wave-bar_{clean_id} {{
          width: 2px;
          background: #dc2626;
          border-radius: 1px;
          height: 3px;
          animation: soundWave_{clean_id} 0.6s ease-in-out infinite alternate;
        }}
        .wave-bar_{clean_id}:nth-child(1) {{ animation-delay: 0.1s; }}
        .wave-bar_{clean_id}:nth-child(2) {{ animation-delay: 0.3s; }}
        .wave-bar_{clean_id}:nth-child(3) {{ animation-delay: 0.15s; }}
        .wave-bar_{clean_id}:nth-child(4) {{ animation-delay: 0.35s; }}
      </style>

      <audio id="audio_{clean_id}" preload="auto" src="{data_uri}"></audio>

      <button id="btn_{clean_id}" 
              onclick="toggleAudio_{clean_id}()" 
              title="{html.escape(tooltip_play)}"
              style="{btn_style}">
        <span id="icon_container_{clean_id}" style="display: flex; align-items: center; justify-content: center;">
          {btn_content}
        </span>
      </button>

      <script>
        (function() {{
          const audio = document.getElementById("audio_{clean_id}");
          const isCompact = {'true' if compact else 'false'};
          const shouldAutoPlay = {'true' if auto_play else 'false'};
          const rateVal = {rate};

          const svgSpeaker = `{SVG_SPEAKER}`;
          const svgStop = `{SVG_STOP}`;

          if (audio) {{
            try {{ audio.playbackRate = rateVal; }} catch(e) {{}}
          }}

          function setIdleUI() {{
            const btn = document.getElementById("btn_{clean_id}");
            const icn = document.getElementById("icon_container_{clean_id}");
            if (btn) {{
              btn.title = "{html.escape(tooltip_play)}";
              btn.classList.remove("speaking-active_{clean_id}");
              btn.style.background = "#eff6ff";
              btn.style.borderColor = "#bfdbfe";
              btn.style.color = "#2563eb";
              if (isCompact) {{
                btn.style.borderRadius = "8px";
              }} else {{
                btn.style.borderRadius = "16px";
              }}
            }}
            if (icn) {{
              if (isCompact) {{
                icn.innerHTML = svgSpeaker;
              }} else {{
                icn.innerHTML = svgSpeaker + " <span id='label_{clean_id}' style='margin-left:6px; margin-right:6px;'>{cfg['play_label']}</span>";
              }}
            }}
          }}

          function setSpeakingUI() {{
            const btn = document.getElementById("btn_{clean_id}");
            const icn = document.getElementById("icon_container_{clean_id}");
            if (btn) {{
              btn.title = "{html.escape(tooltip_stop)}";
              btn.classList.add("speaking-active_{clean_id}");
              btn.style.background = "#fee2e2";
              btn.style.borderColor = "#fca5a5";
              btn.style.color = "#dc2626";
              if (isCompact) {{
                btn.style.borderRadius = "8px";
              }} else {{
                btn.style.borderRadius = "16px";
              }}
            }}
            if (icn) {{
              if (isCompact) {{
                icn.innerHTML = svgStop;
              }} else {{
                icn.innerHTML = svgStop + " <span id='label_{clean_id}' style='margin-left:6px; margin-right:6px;'>{cfg['stop_label']}</span><span class='wave-bars_{clean_id}'><span class='wave-bar_{clean_id}'></span><span class='wave-bar_{clean_id}'></span><span class='wave-bar_{clean_id}'></span><span class='wave-bar_{clean_id}'></span></span>";
              }}
            }}
          }}

          if (audio) {{
            audio.onplay = setSpeakingUI;
            audio.onpause = setIdleUI;
            audio.onended = setIdleUI;
            audio.onerror = setIdleUI;
          }}

          window.toggleAudio_{clean_id} = function() {{
            if (!audio) return;
            if (!audio.paused && !audio.ended) {{
              audio.pause();
              audio.currentTime = 0;
              setIdleUI();
            }} else {{
              try {{
                document.querySelectorAll('audio').forEach(function(a) {{
                  if (a !== audio && !a.paused) {{
                    a.pause();
                    a.currentTime = 0;
                  }}
                }});
              }} catch(e) {{}}
              try {{ audio.playbackRate = rateVal; }} catch(e) {{}}
              audio.play().catch(function(err) {{
                console.warn("Lecture audio bloquée ou échouée:", err);
                setIdleUI();
              }});
            }}
          }};

          if (shouldAutoPlay && audio) {{
            setTimeout(function() {{
              if (audio.paused) {{
                window.toggleAudio_{clean_id}();
              }}
            }}, 350);
          }}

          window.addEventListener('beforeunload', function() {{
            if (audio && !audio.paused) audio.pause();
          }});
        }})();
      </script>
    </div>
    """
    return html_code


def _generate_client_tts_player_html(
    cleaned: str,
    language: str = "fr",
    player_id: str = "sanad_voice",
    rate: float = 1.0,
    pitch: float = 1.0,
    compact: bool = True,
    auto_play: bool = False,
) -> str:
    """
    Génère le composant HTML/JavaScript autonome basé sur la Web Speech API native du navigateur client.
    """
    cfg = get_speech_config(language)
    lang_code = cfg["lang_code"]
    tooltip_play = cfg["tooltip_play"]
    tooltip_stop = cfg["tooltip_stop"]
    direction = cfg["dir"]

    # Sérialisation JSON pour échapper proprement tous les caractères
    json_text = json.dumps(cleaned)
    clean_id = re.sub(r"[^a-zA-Z0-9_]", "_", player_id)

    # Styles du bouton selon mode compact ou pilule
    if compact:
        btn_content = SVG_SPEAKER
        btn_style = (
            "display: inline-flex; align-items: center; justify-content: center; "
            "width: 32px; height: 32px; border-radius: 8px; "
            "color: #2563eb; background: #eff6ff; border: 1px solid #bfdbfe; "
            "cursor: pointer; transition: all 0.2s ease; padding: 0; box-shadow: 0 1px 2px rgba(0,0,0,0.05);"
        )
    else:
        btn_content = f"{SVG_SPEAKER} <span id='label_{clean_id}' style='margin-left: 6px; margin-right: 6px;'>{cfg['play_label']}</span>"
        btn_style = (
            "display: inline-flex; align-items: center; justify-content: center; gap: 6px; "
            "padding: 5px 14px; height: 32px; font-size: 12.5px; font-weight: 500; "
            "color: #1e40af; background: #eff6ff; border: 1px solid #bfdbfe; "
            "border-radius: 16px; cursor: pointer; transition: all 0.2s cubic-bezier(0.4, 0, 0.2, 1); "
            "box-shadow: 0 1px 2px rgba(37, 99, 235, 0.08); -webkit-tap-highlight-color: transparent;"
        )

    justify_style = "flex-end" if direction == "rtl" else "flex-start"

    html_code = f"""
    <div id="wrapper_{clean_id}" style="display: flex; align-items: center; justify-content: {justify_style}; margin: 3px 0 0 0; padding: 0; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; direction: {direction};">
      <style>
        #btn_{clean_id}:hover {{
          transform: translateY(-1px);
          background: #dbeafe !important;
          border-color: #93c5fd !important;
        }}
        @keyframes pulseAudio_{clean_id} {{
          0% {{ box-shadow: 0 0 0 0 rgba(220, 38, 38, 0.35); }}
          70% {{ box-shadow: 0 0 0 6px rgba(220, 38, 38, 0); }}
          100% {{ box-shadow: 0 0 0 0 rgba(220, 38, 38, 0); }}
        }}
        .speaking-active_{clean_id} {{
          animation: pulseAudio_{clean_id} 1.6s infinite;
        }}
        @keyframes soundWave_{clean_id} {{
          0% {{ height: 3px; }}
          100% {{ height: 12px; }}
        }}
        .wave-bars_{clean_id} {{
          display: inline-flex;
          align-items: center;
          gap: 2px;
          height: 12px;
          margin: 0 4px;
        }}
        .wave-bar_{clean_id} {{
          width: 2px;
          background: #dc2626;
          border-radius: 1px;
          height: 3px;
          animation: soundWave_{clean_id} 0.6s ease-in-out infinite alternate;
        }}
        .wave-bar_{clean_id}:nth-child(1) {{ animation-delay: 0.1s; }}
        .wave-bar_{clean_id}:nth-child(2) {{ animation-delay: 0.3s; }}
        .wave-bar_{clean_id}:nth-child(3) {{ animation-delay: 0.15s; }}
        .wave-bar_{clean_id}:nth-child(4) {{ animation-delay: 0.35s; }}
      </style>

      <button id="btn_{clean_id}" 
              onclick="toggleSpeech_{clean_id}()" 
              title="{html.escape(tooltip_play)}"
              style="{btn_style}">
        <span id="icon_container_{clean_id}" style="display: flex; align-items: center; justify-content: center;">
          {btn_content}
        </span>
      </button>

      <script>
        (function() {{
          const cleanText = {json_text};
          const langCode = '{lang_code}';
          const rateVal = {rate};
          const pitchVal = {pitch};
          const isCompact = {'true' if compact else 'false'};
          const shouldAutoPlay = {'true' if auto_play else 'false'};

          const svgSpeaker = `{SVG_SPEAKER}`;
          const svgStop = `{SVG_STOP}`;

          function getSynth() {{
            try {{
              if (window.speechSynthesis) return window.speechSynthesis;
              if (window.parent && window.parent.speechSynthesis) return window.parent.speechSynthesis;
              if (window.top && window.top.speechSynthesis) return window.top.speechSynthesis;
            }} catch(e) {{}}
            return null;
          }}

          let currentUtterance = null;
          let isSpeaking = false;

          function setIdleUI() {{
            isSpeaking = false;
            const btn = document.getElementById("btn_{clean_id}");
            const icn = document.getElementById("icon_container_{clean_id}");
            if (btn) {{
              btn.title = "{html.escape(tooltip_play)}";
              btn.classList.remove("speaking-active_{clean_id}");
              btn.style.background = "#eff6ff";
              btn.style.borderColor = "#bfdbfe";
              btn.style.color = "#2563eb";
              if (isCompact) {{
                btn.style.borderRadius = "8px";
              }} else {{
                btn.style.borderRadius = "16px";
              }}
            }}
            if (icn) {{
              if (isCompact) {{
                icn.innerHTML = svgSpeaker;
              }} else {{
                icn.innerHTML = svgSpeaker + " <span id='label_{clean_id}' style='margin-left:6px; margin-right:6px;'>{cfg['play_label']}</span>";
              }}
            }}
          }}

          function setSpeakingUI() {{
            isSpeaking = true;
            const btn = document.getElementById("btn_{clean_id}");
            const icn = document.getElementById("icon_container_{clean_id}");
            if (btn) {{
              btn.title = "{html.escape(tooltip_stop)}";
              btn.classList.add("speaking-active_{clean_id}");
              btn.style.background = "#fee2e2";
              btn.style.borderColor = "#fca5a5";
              btn.style.color = "#dc2626";
              if (isCompact) {{
                btn.style.borderRadius = "8px";
              }} else {{
                btn.style.borderRadius = "16px";
              }}
            }}
            if (icn) {{
              if (isCompact) {{
                icn.innerHTML = svgStop;
              }} else {{
                icn.innerHTML = svgStop + " <span id='label_{clean_id}' style='margin-left:6px; margin-right:6px;'>{cfg['stop_label']}</span><span class='wave-bars_{clean_id}'><span class='wave-bar_{clean_id}'></span><span class='wave-bar_{clean_id}'></span><span class='wave-bar_{clean_id}'></span><span class='wave-bar_{clean_id}'></span></span>";
              }}
            }}
          }}

          window.toggleSpeech_{clean_id} = function() {{
            const synth = getSynth();
            if (!synth) {{
              alert("La synthèse vocale n'est pas prise en charge par ce navigateur.");
              return;
            }}

            if (isSpeaking) {{
              synth.cancel();
              setIdleUI();
              return;
            }}

            // Arrêter toute lecture en cours pour éviter les superpositions
            synth.cancel();

            const utter = new SpeechSynthesisUtterance(cleanText);
            utter.lang = langCode;
            utter.rate = rateVal;
            utter.pitch = pitchVal;

            try {{
              const voices = synth.getVoices();
              if (voices && voices.length > 0) {{
                const prefix = langCode.split('-')[0].toLowerCase();
                const matched = voices.filter(v => v.lang && v.lang.toLowerCase().startsWith(prefix));
                if (matched.length > 0) {{
                  const natural = matched.find(v => 
                    v.name.includes("Google") || 
                    v.name.includes("Natural") || 
                    v.name.includes("Online") ||
                    v.name.includes("Tarik") ||
                    v.name.includes("Maged") ||
                    v.name.includes("Laila") ||
                    v.name.includes("Salma") ||
                    v.name.includes("Mehdi") ||
                    v.name.includes("Zeina")
                  );
                  utter.voice = natural || matched[0];
                }}
              }}
            }} catch(e) {{}}

            utter.onstart = function() {{
              setSpeakingUI();
            }};

            utter.onend = function() {{
              setIdleUI();
            }};

            utter.onerror = function(e) {{
              setIdleUI();
            }};

            currentUtterance = utter;
            synth.speak(utter);
          }};

          // Lecture automatique si activée
          if (shouldAutoPlay) {{
            setTimeout(function() {{
              if (!isSpeaking) {{
                window.toggleSpeech_{clean_id}();
              }}
            }}, 350);
          }}

          window.addEventListener('beforeunload', function() {{
            const synth = getSynth();
            if (synth) synth.cancel();
          }});
        }})();
      </script>
    </div>
    """
    return html_code


def generate_tts_player_html(
    text: str,
    language: str = "fr",
    player_id: str = "sanad_voice",
    rate: float = 1.0,
    pitch: float = 1.0,
    compact: bool = True,
    auto_play: bool = False,
    force_server_tts: Optional[bool] = None,
) -> str:
    """
    Génère un composant HTML/JavaScript autonome et réactif pour la synthèse vocale.
    - Sous Linux : génère le flux audio MP3 côté serveur via gTTS (100% gratuit, 0 quota Gemini,
      compatibilité parfaite avec tous les navigateurs Linux qui ne disposent pas de Web Speech API native).
    - Hors Linux (Windows, macOS, iOS, Android) : utilise la Web Speech API native du navigateur client.
    - Mode pilule (compact=False) : design moderne sous le message avec égaliseur animé.
    - Mode icône (compact=True) : bouton carré 32x32px.
    Supporte la lecture automatique (auto_play=True) et le paramètre force_server_tts.
    Coût : 0 token Gemini, 100% gratuit.
    """
    cleaned = clean_text_for_speech(text)
    if not cleaned:
        return ""

    use_server = force_server_tts if force_server_tts is not None else True

    if use_server:
        data_uri = get_server_tts_audio_base64(cleaned, language=language)
        if data_uri:
            return _generate_server_audio_player_html(
                data_uri=data_uri,
                language=language,
                player_id=player_id,
                rate=rate,
                compact=compact,
                auto_play=auto_play,
            )
        logger.info("Repli sur le lecteur Web Speech API client suite à une indisponibilité audio serveur.")

    return _generate_client_tts_player_html(
        cleaned=cleaned,
        language=language,
        player_id=player_id,
        rate=rate,
        pitch=pitch,
        compact=compact,
        auto_play=auto_play,
    )


def generate_fiche_audio_player_html(
    text: str,
    language: str = "fr",
    player_id: str = "fiche_audio_player",
    rate: float = 1.0,
    audio_data_uri: Optional[str] = None,
    force_server_tts: Optional[bool] = None,
) -> str:
    """
    Génère un composant HTML5 discret et élégant pour la Fiche Express (style pilule Sanad).
    - Design compact et sobre identique à Sanad (hauteur 32px, pilule bleue au repos, rouge animé en lecture).
    - Génération audio MP3 côté serveur via gTTS par défaut (100% fiable sur tous les appareils : Android, iOS, Windows, Mac, Linux).
    - Détection automatique et infaillible du texte en Arabe (orientation RTL, prononciation authentique avec tashkeel).
    - Mode de repli Web Speech API si le serveur ou la génération MP3 est indisponible.
    - Zéro consommation de quota d'API Gemini (100% gratuit).
    """
    cleaned = clean_text_for_speech(text)
    if not cleaned:
        return ""

    # Détection automatique de la langue réelle du texte
    is_ar = detect_arabic_content(cleaned) or bool(language and language.lower().startswith("ar"))
    eff_lang = "ar" if is_ar else (language or "fr")

    # Si aucun flux MP3 fourni et mode serveur activé par défaut, générer le MP3 côté serveur via gTTS
    use_server = force_server_tts if force_server_tts is not None else True
    if not audio_data_uri and use_server:
        audio_data_uri = get_server_tts_audio_base64(cleaned, language=eff_lang)

    cfg = get_speech_config(eff_lang)
    lang_code = cfg["lang_code"]
    direction = cfg["dir"]
    clean_id = re.sub(r"[^a-zA-Z0-9_]", "_", player_id)
    play_label = cfg.get("fiche_play", cfg.get("play_label", "Écouter la fiche"))
    stop_label = cfg.get("fiche_stop", cfg.get("stop_label", "Arrêter"))
    tooltip_play = cfg.get("tooltip_play", play_label)
    tooltip_stop = cfg.get("tooltip_stop", stop_label)

    justify_style = "flex-end" if direction == "rtl" else "flex-start"

    # Style pilule identique à Sanad
    btn_style = (
        "display: inline-flex; align-items: center; justify-content: center; gap: 6px; "
        "padding: 5px 14px; height: 32px; font-size: 12.5px; font-weight: 500; "
        "color: #1e40af; background: #eff6ff; border: 1px solid #bfdbfe; "
        "border-radius: 16px; cursor: pointer; transition: all 0.2s cubic-bezier(0.4, 0, 0.2, 1); "
        "box-shadow: 0 1px 2px rgba(37, 99, 235, 0.08); -webkit-tap-highlight-color: transparent; outline: none;"
    )

    common_styles = f"""
      <style>
        #btn_{clean_id}:hover {{
          transform: translateY(-1px);
          background: #dbeafe !important;
          border-color: #93c5fd !important;
        }}
        @keyframes pulseAudio_{clean_id} {{
          0% {{ box-shadow: 0 0 0 0 rgba(220, 38, 38, 0.35); }}
          70% {{ box-shadow: 0 0 0 6px rgba(220, 38, 38, 0); }}
          100% {{ box-shadow: 0 0 0 0 rgba(220, 38, 38, 0); }}
        }}
        .speaking-active_{clean_id} {{
          animation: pulseAudio_{clean_id} 1.6s infinite;
          background: #fee2e2 !important;
          border-color: #fca5a5 !important;
          color: #dc2626 !important;
        }}
        @keyframes soundWave_{clean_id} {{
          0% {{ height: 3px; }}
          100% {{ height: 12px; }}
        }}
        .wave-bars_{clean_id} {{
          display: inline-flex;
          align-items: center;
          gap: 2px;
          height: 12px;
          margin: 0 4px;
        }}
        .wave-bar_{clean_id} {{
          width: 2px;
          background: #dc2626;
          border-radius: 1px;
          height: 3px;
          animation: soundWave_{clean_id} 0.6s ease-in-out infinite alternate;
        }}
        .wave-bar_{clean_id}:nth-child(1) {{ animation-delay: 0.1s; }}
        .wave-bar_{clean_id}:nth-child(2) {{ animation-delay: 0.3s; }}
        .wave-bar_{clean_id}:nth-child(3) {{ animation-delay: 0.15s; }}
        .wave-bar_{clean_id}:nth-child(4) {{ animation-delay: 0.35s; }}
      </style>
    """

    # 1. Si un flux audio MP3 est disponible (recommandé et garanti 100% fonctionnel sur Linux et en Arabe)
    if audio_data_uri:
        html_code = f"""
        <div id="wrapper_{clean_id}" style="display: flex; align-items: center; justify-content: {justify_style}; margin: 2px 0 6px 0; padding: 0; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; direction: {direction};">
          {common_styles}

          <audio id="audio_{clean_id}" preload="auto" src="{audio_data_uri}"></audio>

          <button id="btn_{clean_id}" 
                  onclick="toggleFicheAudio_{clean_id}()" 
                  title="{html.escape(tooltip_play)}"
                  style="{btn_style}">
            <span id="icon_container_{clean_id}" style="display: flex; align-items: center; justify-content: center; gap: 6px;">
              {SVG_SPEAKER} <span id="label_{clean_id}">{play_label}</span>
            </span>
          </button>

          <script>
            (function() {{
              const audio = document.getElementById("audio_{clean_id}");
              const svgSpeaker = `{SVG_SPEAKER}`;
              const svgStop = `{SVG_STOP}`;
              const rateVal = {rate};

              if (audio) {{
                try {{ audio.playbackRate = rateVal; }} catch(e) {{}}
              }}

              function setIdleUI() {{
                const btn = document.getElementById("btn_{clean_id}");
                const icn = document.getElementById("icon_container_{clean_id}");
                if (btn) {{
                  btn.title = "{html.escape(tooltip_play)}";
                  btn.classList.remove("speaking-active_{clean_id}");
                }}
                if (icn) {{
                  icn.innerHTML = svgSpeaker + " <span id='label_{clean_id}'>{play_label}</span>";
                }}
              }}

              function setSpeakingUI() {{
                const btn = document.getElementById("btn_{clean_id}");
                const icn = document.getElementById("icon_container_{clean_id}");
                if (btn) {{
                  btn.title = "{html.escape(tooltip_stop)}";
                  btn.classList.add("speaking-active_{clean_id}");
                }}
                if (icn) {{
                  icn.innerHTML = svgStop + " <span id='label_{clean_id}'>{stop_label}</span> <span class='wave-bars_{clean_id}'><span class='wave-bar_{clean_id}'></span><span class='wave-bar_{clean_id}'></span><span class='wave-bar_{clean_id}'></span><span class='wave-bar_{clean_id}'></span></span>";
                }}
              }}

              if (audio) {{
                audio.onplay = setSpeakingUI;
                audio.onpause = setIdleUI;
                audio.onended = setIdleUI;
                audio.onerror = setIdleUI;
              }}

              window.toggleFicheAudio_{clean_id} = function() {{
                if (!audio) return;
                if (!audio.paused && !audio.ended) {{
                  audio.pause();
                  audio.currentTime = 0;
                  setIdleUI();
                }} else {{
                  try {{
                    document.querySelectorAll('audio').forEach(function(a) {{
                      if (a !== audio && !a.paused) {{
                        a.pause();
                        a.currentTime = 0;
                      }}
                    }});
                  }} catch(e) {{}}
                  try {{ audio.playbackRate = rateVal; }} catch(e) {{}}
                  audio.play().catch(function(err) {{
                    console.warn("Lecture audio bloquée ou échouée:", err);
                    setIdleUI();
                  }});
                }}
              }};

              window.addEventListener('beforeunload', function() {{
                if (audio && !audio.paused) audio.pause();
              }});
            }})();
          </script>
        </div>
        """
        return html_code

    # 2. Repli Web Speech API (avec style pilule discret Sanad)
    json_text = json.dumps(cleaned, ensure_ascii=False)
    no_ar_voice_msg = "لا يتوفر صوت عربي مثبت في متصفحك. يرجى استخدام زر تحميل البودكاست بالأسفل للاستماع بصوت عالي الجودة." if is_ar else "Aucune voix arabe locale trouvée dans le navigateur."

    html_code = f"""
    <div id="wrapper_{clean_id}" style="display: flex; align-items: center; justify-content: {justify_style}; margin: 2px 0 6px 0; padding: 0; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; direction: {direction};">
      {common_styles}

      <button id="btn_{clean_id}" 
              onclick="toggleFicheSpeech_{clean_id}()" 
              title="{html.escape(tooltip_play)}"
              style="{btn_style}">
        <span id="icon_container_{clean_id}" style="display: flex; align-items: center; justify-content: center; gap: 6px;">
          {SVG_SPEAKER} <span id="label_{clean_id}">{play_label}</span>
        </span>
      </button>

      <script>
        (function() {{
          const fullText = {json_text};
          const langCode = '{lang_code}';
          const cleanId = '{clean_id}';
          const svgSpeaker = `{SVG_SPEAKER}`;
          const svgStop = `{SVG_STOP}`;
          let currentRate = {rate};

          function splitIntoSentences(text) {{
            if (!text) return [];
            const rawMatches = text.match(/[^.!?؛؟\\n]+[.!?؛؟\\n]*/g);
            if (!rawMatches) return [text];
            const result = [];
            for (let i = 0; i < rawMatches.length; i++) {{
              const s = rawMatches[i].trim();
              if (s.length > 0) result.push(s);
            }}
            return result.length > 0 ? result : [text];
          }}

          const sentences = splitIntoSentences(fullText);
          let currentIndex = 0;
          let isSpeaking = false;
          let naturalVoice = null;

          function getSynth() {{
            try {{
              if (window.speechSynthesis) return window.speechSynthesis;
              if (window.parent && window.parent.speechSynthesis) return window.parent.speechSynthesis;
              if (window.top && window.top.speechSynthesis) return window.top.speechSynthesis;
            }} catch(e) {{}}
            return null;
          }}

          function findBestVoice(synth) {{
            if (!synth) return null;
            try {{
              const voices = synth.getVoices();
              if (!voices || voices.length === 0) return null;
              const prefix = langCode.split('-')[0].toLowerCase();
              const matched = voices.filter(function(v) {{
                const l = (v.lang || "").toLowerCase().replace('_', '-');
                const n = (v.name || "").toLowerCase();
                return l.startsWith(prefix) || (prefix === 'ar' && (l.includes('ar') || n.includes('arabic') || n.includes('arabe')));
              }});
              if (matched.length > 0) {{
                const natural = matched.find(function(v) {{
                  const n = (v.name || "").toLowerCase();
                  return n.includes("google") || n.includes("natural") || n.includes("online") ||
                         n.includes("paul") || n.includes("julie") || n.includes("hortense") ||
                         n.includes("tarik") || n.includes("laila") || n.includes("salma") ||
                         n.includes("mehdi") || n.includes("zeina") || n.includes("maged");
                }});
                return natural || matched[0];
              }}
            }} catch(e) {{}}
            return null;
          }}

          function setIdleUI() {{
            const btn = document.getElementById("btn_" + cleanId);
            const icn = document.getElementById("icon_container_" + cleanId);
            if (btn) {{
              btn.title = "{html.escape(tooltip_play)}";
              btn.classList.remove("speaking-active_" + cleanId);
            }}
            if (icn) {{
              icn.innerHTML = svgSpeaker + " <span id='label_" + cleanId + "'>{play_label}</span>";
            }}
          }}

          function setSpeakingUI() {{
            const btn = document.getElementById("btn_" + cleanId);
            const icn = document.getElementById("icon_container_" + cleanId);
            if (btn) {{
              btn.title = "{html.escape(tooltip_stop)}";
              btn.classList.add("speaking-active_" + cleanId);
            }}
            if (icn) {{
              icn.innerHTML = svgStop + " <span id='label_" + cleanId + "'>{stop_label}</span> <span class='wave-bars_" + cleanId + "'><span class='wave-bar_" + cleanId + "'></span><span class='wave-bar_" + cleanId + "'></span><span class='wave-bar_" + cleanId + "'></span><span class='wave-bar_" + cleanId + "'></span></span>";
            }}
          }}

          function speakSentence(index) {{
            const synth = getSynth();
            if (!synth || !isSpeaking) return;

            if (index >= sentences.length) {{
              stopSpeech();
              return;
            }}

            currentIndex = index;
            const utter = new SpeechSynthesisUtterance(sentences[currentIndex]);
            utter.lang = langCode;
            utter.rate = currentRate;
            if (!naturalVoice) naturalVoice = findBestVoice(synth);
            if (naturalVoice) utter.voice = naturalVoice;

            utter.onend = function() {{
              if (isSpeaking) {{
                speakSentence(currentIndex + 1);
              }}
            }};

            utter.onerror = function(e) {{
              if (isSpeaking) {{
                speakSentence(currentIndex + 1);
              }}
            }};

            synth.speak(utter);
          }}

          function stopSpeech() {{
            const synth = getSynth();
            if (synth) synth.cancel();
            isSpeaking = false;
            currentIndex = 0;
            setIdleUI();
          }}

          window['toggleFicheSpeech_' + cleanId] = function() {{
            const synth = getSynth();
            if (!synth) {{
              alert("Synthèse vocale non disponible sur ce navigateur.");
              return;
            }}

            if (isSpeaking) {{
              stopSpeech();
              return;
            }}

            if (langCode.startsWith('ar')) {{
              const v = findBestVoice(synth);
              if (!v) {{
                console.warn("{html.escape(no_ar_voice_msg)}");
              }}
            }}

            synth.cancel();
            isSpeaking = true;
            currentIndex = 0;
            setSpeakingUI();
            speakSentence(0);
          }};

          window.addEventListener('beforeunload', function() {{
            if (synth) synth.cancel();
          }});
        }})();
      </script>
    </div>
    """
    return html_code


def generate_or_get_course_fiche_mp3(
    course_id: int,
    text: str,
    language: str = "fr",
    user_id: Optional[int] = None,
) -> Optional[Path]:
    """
    Retourne le chemin du fichier audio MP3 de la fiche express.
    S'il n'existe pas encore sur le disque, le génère via gTTS et le sauvegarde.
    Détecte automatiquement l'arabe pour assurer une prononciation authentique.
    Permet l'écoute offline et le téléchargement direct en format podcast.
    """
    try:
        from models.database import get_db_path
        storage_root = get_db_path().parent
    except Exception:
        storage_root = Path(__file__).resolve().parent.parent / "storage"

    if user_id is not None:
        target_dir = storage_root / "users" / str(user_id) / "cours"
    else:
        target_dir = storage_root / "cours"

    target_dir.mkdir(parents=True, exist_ok=True)
    mp3_path = target_dir / f"fiche_{course_id}.mp3"

    if mp3_path.exists() and mp3_path.stat().st_size > 500:
        return mp3_path

    # Détection automatique de la langue réelle du texte
    if detect_arabic_content(text):
        eff_lang = "ar"
    else:
        eff_lang = (language or "fr").lower().strip()

    # Génération du flux audio
    data_uri = get_server_tts_audio_base64(text, language=eff_lang)
    if not data_uri:
        return None

    try:
        b64_part = data_uri.split(",", 1)[1]
        raw_bytes = base64.b64decode(b64_part)
        with open(mp3_path, "wb") as f:
            f.write(raw_bytes)
        return mp3_path
    except Exception as e:
        logger.error(f"Erreur lors de la sauvegarde du fichier MP3 de la fiche {course_id}: {e}")
        return None


def generate_chat_mic_injector_html(language: str = "fr", widget_id: str = "chat_mic") -> str:
    """
    Génère un script discret qui injecte l'icône de dictée vocale (micro) directement
    à l'intérieur du champ de saisie de texte st.chat_input, juste à côté du bouton d'envoi.
    Fournit une expérience utilisateur fluide type WhatsApp / ChatGPT :
    - Icône micro discrète et élégante
    - Dictée en temps réel avec insertion directe dans le textarea
    - Animation rouge pulsante pendant l'écoute
    Coût : 0 token Gemini, 100% exécuté localement par SpeechRecognition.
    """
    cfg = get_speech_config(language)
    lang_code = cfg["lang_code"]
    mic_tooltip = cfg["mic_tooltip"]
    clean_id = re.sub(r"[^a-zA-Z0-9_]", "_", widget_id)

    html_code = f"""
    <div id="mic_injector_container_{clean_id}" style="display:none; height:0; width:0; overflow:hidden;">
      <script>
        (function() {{
          const langCode = '{lang_code}';
          const micTooltip = "{html.escape(mic_tooltip)}";

          function getParentDoc() {{
            try {{
              if (window.parent && window.parent.document) return window.parent.document;
            }} catch(e) {{}}
            return document;
          }}

          function getSpeechRecClass() {{
            try {{
              if (window.parent) {{
                if (window.parent.SpeechRecognition) return window.parent.SpeechRecognition;
                if (window.parent.webkitSpeechRecognition) return window.parent.webkitSpeechRecognition;
              }}
              if (window.top) {{
                if (window.top.SpeechRecognition) return window.top.SpeechRecognition;
                if (window.top.webkitSpeechRecognition) return window.top.webkitSpeechRecognition;
              }}
              if (window.SpeechRecognition) return window.SpeechRecognition;
              if (window.webkitSpeechRecognition) return window.webkitSpeechRecognition;
            }} catch(e) {{}}
            return null;
          }}

          // Autoriser les permissions audio sur l'iframe du composant Streamlit
          try {{
            if (window.frameElement) {{
              window.frameElement.setAttribute("allow", "microphone *; speech-recognition *");
            }}
          }} catch(e) {{}}

          function showToast(msg, isError) {{
            try {{
              const pDoc = getParentDoc();
              if (!pDoc) return;
              let toast = pDoc.getElementById("sanad_voice_toast");
              if (!toast) {{
                toast = pDoc.createElement("div");
                toast.id = "sanad_voice_toast";
                toast.style.cssText = "position:fixed;bottom:90px;left:50%;transform:translateX(-50%);background:#1f2937;color:#fff;padding:10px 18px;border-radius:10px;font-size:13px;z-index:9999999;box-shadow:0 4px 16px rgba(0,0,0,0.3);transition:opacity 0.3s ease;pointer-events:none;max-width:90%;text-align:center;display:flex;align-items:center;gap:8px;";
                pDoc.body.appendChild(toast);
              }}
              toast.innerHTML = (isError ? "⚠️ " : "ℹ️ ") + msg;
              toast.style.opacity = "1";
              toast.style.display = "flex";
              if (toast._timer) clearTimeout(toast._timer);
              toast._timer = setTimeout(function() {{
                toast.style.opacity = "0";
                setTimeout(function() {{ toast.style.display = "none"; }}, 350);
              }}, 5000);
            }} catch(e) {{}}
          }}

          let recognition = null;
          let isListening = false;
          let hasDictated = false;
          let micBtn = null;

          function scrollToChatBottom() {{
            try {{
              const pDoc = getParentDoc();
              if (!pDoc) return;
              const pWin = window.parent || window;

              // 1. Défilement ciblé vers l'ancre basse de la conversation
              const anchor = pDoc.getElementById("sanad_chat_bottom_anchor");
              if (anchor) {{
                try {{
                  anchor.scrollIntoView({{ behavior: 'smooth', block: 'end' }});
                }} catch(e) {{
                  anchor.scrollIntoView(false);
                }}
              }}

              // 2. Défilement des conteneurs scrollables Streamlit
              const scrollers = pDoc.querySelectorAll('[data-testid="stAppViewContainer"], section.main');
              scrollers.forEach(function(el) {{
                if (el && el.scrollHeight > el.clientHeight) {{
                  el.scrollTo({{ top: el.scrollHeight, behavior: 'smooth' }});
                }}
              }});

              if (pWin && pWin.scrollTo) {{
                pWin.scrollTo({{ top: pDoc.body.scrollHeight, behavior: 'smooth' }});
              }}
            }} catch(e) {{}}
          }}

          function submitChatInput() {{
            const pDoc = getParentDoc();
            if (!pDoc) return;
            const pWin = window.parent || window;
            const textarea = pDoc.querySelector('textarea[data-testid="stChatInputTextArea"]');
            const submitBtn = pDoc.querySelector('button[data-testid="stChatInputSubmitButton"]');
            if (!textarea || !textarea.value || textarea.value.trim().length === 0) return;

            if (submitBtn) {{
              submitBtn.disabled = false;
              submitBtn.removeAttribute('disabled');
              submitBtn.style.pointerEvents = 'auto';
            }}

            // 1. Déclencher l'événement Enter sur le textarea
            try {{
              const KeyboardEventClass = pWin.KeyboardEvent || KeyboardEvent;
              const enterDown = new KeyboardEventClass('keydown', {{
                key: 'Enter',
                code: 'Enter',
                keyCode: 13,
                which: 13,
                bubbles: true,
                cancelable: true
              }});
              textarea.dispatchEvent(enterDown);
            }} catch(e) {{}}

            // 2. Déclencher le clic sur le bouton submit
            if (submitBtn) {{
              try {{
                submitBtn.click();
              }} catch(e) {{}}
            }}

            // Scroller vers le bas après soumission
            setTimeout(scrollToChatBottom, 120);
          }}

          function setupMic() {{
            const pDoc = getParentDoc();
            if (!pDoc) return;

            // Trouver le bouton d'envoi st.chat_input
            const submitBtn = pDoc.querySelector('button[data-testid="stChatInputSubmitButton"]');
            if (!submitBtn) return;

            // Vérifier s'il est déjà injecté
            let existingMic = pDoc.getElementById("sanad_chat_input_mic_btn");
            if (existingMic) {{
              // Mettre à jour la langue active
              existingMic.dataset.langCode = langCode;
              return;
            }}

            micBtn = pDoc.createElement("button");
            micBtn.id = "sanad_chat_input_mic_btn";
            micBtn.type = "button";
            micBtn.title = micTooltip;
            micBtn.dataset.langCode = langCode;
            micBtn.innerHTML = `{SVG_MIC}`;
            micBtn.style.cssText = `
              display: inline-flex;
              align-items: center;
              justify-content: center;
              width: 32px;
              height: 32px;
              border-radius: 50%;
              background: transparent;
              border: none;
              color: #6b7280;
              cursor: pointer;
              transition: all 0.2s ease;
              margin-right: 4px;
              margin-left: 2px;
              padding: 0;
              flex-shrink: 0;
            `;

            micBtn.onmouseenter = function() {{
              if (!isListening) {{
                micBtn.style.color = "#2563eb";
                micBtn.style.background = "#eff6ff";
              }}
            }};

            micBtn.onmouseleave = function() {{
              if (!isListening) {{
                micBtn.style.color = "#6b7280";
                micBtn.style.background = "transparent";
              }}
            }};

            // Injecter juste avant le bouton d'envoi
            submitBtn.parentNode.insertBefore(micBtn, submitBtn);

            micBtn.onclick = function(e) {{
              e.preventDefault();
              e.stopPropagation();

              if (isListening && recognition) {{
                recognition.stop();
                setMicListeningState(false);
                return;
              }}

              const RecClass = getSpeechRecClass();
              if (!RecClass) {{
                showToast("La reconnaissance vocale instantanée du navigateur n'est pas supportée. Utilisez l'enregistreur vocal universel juste au-dessus.", true);
                return;
              }}

              const pWin = window.parent || window;
              const nav = (pWin.navigator && pWin.navigator.mediaDevices) ? pWin.navigator : navigator;

              function startActualRecognition() {{
                try {{
                  recognition = new RecClass();
                  recognition.lang = micBtn.dataset.langCode || langCode;
                  recognition.continuous = false;
                  recognition.interimResults = true;

                  recognition.onstart = function() {{
                    hasDictated = false;
                    setMicListeningState(true);
                  }};

                  recognition.onresult = function(event) {{
                    let interim = '';
                    let finalTranscript = '';
                    for (let i = event.resultIndex; i < event.results.length; ++i) {{
                      if (event.results[i].isFinal) {{
                        finalTranscript += event.results[i][0].transcript;
                      }} else {{
                        interim += event.results[i][0].transcript;
                      }}
                    }}
                    const txt = finalTranscript || interim;
                    if (txt && txt.trim().length > 0) {{
                      hasDictated = true;
                      insertTextIntoChatInput(txt);
                    }}
                  }};

                  recognition.onerror = function(event) {{
                    setMicListeningState(false);
                    hasDictated = false;
                    const err = event && event.error ? event.error : "inconnue";
                    if (err === "no-speech") {{
                      return;
                    }}
                    if (err === "not-allowed" || err === "permission-denied") {{
                      showToast("Microphone bloqué : autorisez le micro dans Chrome (icône cadenas à gauche de l'URL), ou utilisez l'enregistreur vocal juste au-dessus.", true);
                    }} else if (err === "network") {{
                      showToast("Reconnaissance vocale Google indisponible (courant sous Linux Chromium). Utilisez l'enregistreur vocal juste au-dessus.", true);
                    }} else if (err === "audio-capture") {{
                      showToast("Aucun microphone actif détecté sous Linux. Vérifiez votre micro dans les paramètres audio.", true);
                    }} else {{
                      showToast("Erreur reconnaissance vocale (" + err + "). Utilisez l'enregistreur vocal au-dessus si besoin.", true);
                    }}
                  }};

                  recognition.onend = function() {{
                    setMicListeningState(false);
                    const pDoc = getParentDoc();
                    if (pDoc) {{
                      const textarea = pDoc.querySelector('textarea[data-testid="stChatInputTextArea"]');
                      const submitBtn = pDoc.querySelector('button[data-testid="stChatInputSubmitButton"]');
                      if (textarea && textarea.value && textarea.value.trim().length > 0 && submitBtn) {{
                        submitBtn.disabled = false;
                        submitBtn.removeAttribute('disabled');
                      }}
                    }}

                    // Envoi automatique après dictée vocale
                    if (hasDictated) {{
                      hasDictated = false;
                      setTimeout(function() {{
                        submitChatInput();
                      }}, 250);
                    }}
                  }};

                  recognition.start();
                }} catch(err) {{
                  setMicListeningState(false);
                  hasDictated = false;
                  showToast("Impossible de démarrer le micro : " + (err.message || err), true);
                }}
              }}

              // Vérifier/demander l'accès au micro via getUserMedia (débloque PulseAudio/PipeWire et déclenche le prompt Chrome)
              if (nav && nav.mediaDevices && nav.mediaDevices.getUserMedia) {{
                nav.mediaDevices.getUserMedia({{ audio: true }}).then(function(stream) {{
                  try {{
                    stream.getTracks().forEach(function(t) {{ t.stop(); }});
                  }} catch(e) {{}}
                  startActualRecognition();
                }}).catch(function(err) {{
                  setMicListeningState(false);
                  showToast("Accès au microphone refusé ou non disponible sous Linux : " + (err.message || err.name || "Refusé"), true);
                }});
              }} else {{
                startActualRecognition();
              }}
            }};
          }}

          function setMicListeningState(listening) {{
            isListening = listening;
            if (!micBtn) return;
            if (listening) {{
              micBtn.style.color = "#dc2626";
              micBtn.style.background = "#fee2e2";
              micBtn.style.transform = "scale(1.15)";
              micBtn.title = "🔴 Écoute en cours... Parlez puis le message s'enverra automatiquement";
            }} else {{
              micBtn.style.color = "#6b7280";
              micBtn.style.background = "transparent";
              micBtn.style.transform = "scale(1.0)";
              micBtn.title = micTooltip;
            }}
          }}

          function insertTextIntoChatInput(text) {{
            const pDoc = getParentDoc();
            if (!pDoc) return;
            const pWin = window.parent || window;
            const textarea = pDoc.querySelector('textarea[data-testid="stChatInputTextArea"]');
            if (!textarea) return;

            // Utiliser le setter natif du prototype HTMLTextAreaElement de la fenêtre parent
            try {{
              const proto = (pWin.HTMLTextAreaElement && pWin.HTMLTextAreaElement.prototype)
                            || window.HTMLTextAreaElement.prototype;
              const desc = Object.getOwnPropertyDescriptor(proto, 'value');
              if (desc && desc.set) {{
                desc.set.call(textarea, text);
              }} else {{
                textarea.value = text;
              }}
            }} catch(e) {{
              textarea.value = text;
            }}

            // Mettre à jour le valueTracker interne de React si présent
            if (textarea._valueTracker) {{
              textarea._valueTracker.setValue('');
            }}

            // Événements dans le contexte parent pour notifier le state React
            const EventClass = pWin.Event || Event;
            textarea.dispatchEvent(new EventClass('input', {{ bubbles: true, cancelable: true }}));
            textarea.dispatchEvent(new EventClass('change', {{ bubbles: true, cancelable: true }}));

            // Activer directement le bouton envoyer
            const submitBtn = pDoc.querySelector('button[data-testid="stChatInputSubmitButton"]');
            if (submitBtn) {{
              submitBtn.disabled = false;
              submitBtn.removeAttribute('disabled');
              submitBtn.style.pointerEvents = 'auto';
            }}

            textarea.focus();
          }}

          // Observer les mutations du chat pour déclencher l'auto-scroll fluide
          function setupChatObserver() {{
            const pDoc = getParentDoc();
            if (!pDoc) return;
            const chatBox = pDoc.querySelector('[data-testid="stChatInput"]')?.closest('[data-testid="stVerticalBlock"]');
            if (chatBox && !chatBox.dataset.sanadScrollObserved) {{
              chatBox.dataset.sanadScrollObserved = "true";
              const obs = new MutationObserver(function() {{
                scrollToChatBottom();
              }});
              obs.observe(chatBox, {{ childList: true, subtree: true }});
            }}
          }}

          // Tenter d'injecter immédiatement et avec un observateur
          setupMic();
          setupChatObserver();
          const timer = setInterval(function() {{
            setupMic();
            setupChatObserver();
          }}, 400);
          setTimeout(() => clearInterval(timer), 6000);

          // Défilement automatique fluide vers le bas de la conversation
          setTimeout(scrollToChatBottom, 80);
          setTimeout(scrollToChatBottom, 300);
          setTimeout(scrollToChatBottom, 750);
          setTimeout(scrollToChatBottom, 1500);
        }})();
      </script>
    </div>
    """
    return html_code


# Rétrocompatibilité pour les anciens appels
def generate_mic_speech_html(language: str = "fr", widget_id: str = "sanad_mic") -> str:
    """Conservé pour rétrocompatibilité : délègue à l'injecteur moderne."""
    return generate_chat_mic_injector_html(language=language, widget_id=widget_id)


def generate_trophy_sound_wav_base64() -> str:
    """
    Génère un flux audio WAV (16 bits, 44.1 kHz) contenant une fanfare royale triomphante
    synthétisée via les fonctions harmoniques pures (accord C5 -> E5 -> G5 -> C6 avec overtones et carillon).
    Mise en cache mémoire pour une restitution instantanée sans latence ni dépendance réseau.
    """
    global _TROPHY_SOUND_CACHE
    if _TROPHY_SOUND_CACHE:
        return _TROPHY_SOUND_CACHE

    sample_rate = 44100
    # Séquence triomphante : Arpège C5, E5, G5 vers accord majestueux C6 soutenu avec harmoniques de carillon
    notes = [
        # (fréquence en Hz, début en s, durée en s, amplitude relative)
        (523.25, 0.00, 0.16, 0.45),   # C5 (Do)
        (659.25, 0.12, 0.16, 0.45),   # E5 (Mi)
        (783.99, 0.24, 0.20, 0.55),   # G5 (Sol)
        (1046.50, 0.38, 0.95, 0.70),  # C6 (Do aigu - fondation de l'accord victorieux)
        (783.99,  0.38, 0.85, 0.35),  # G5 (Sol - plénitude harmonique)
        (1318.51, 0.38, 0.80, 0.40),  # E6 (Mi aigu - éclat royal)
        (2093.00, 0.40, 0.65, 0.25),  # C7 (Carillon scintillant)
    ]
    total_dur = 1.35
    total_samples = int(sample_rate * total_dur)
    buffer = [0.0] * total_samples

    for freq, start, dur, amp in notes:
        start_idx = int(start * sample_rate)
        n_samples = int(dur * sample_rate)
        for i in range(n_samples):
            idx = start_idx + i
            if idx >= total_samples:
                break
            t = i / sample_rate
            # Attaque rapide (12 ms) et déclin exponentiel de type cloche/cuivre
            attack = min(1.0, t / 0.012)
            decay = math.exp(-3.2 * (t / dur))
            env = attack * decay

            # Modélisation harmonique (fondamentale + harmonique 2 + harmonique 3)
            val = amp * env * (
                0.65 * math.sin(2 * math.pi * freq * t) +
                0.25 * math.sin(2 * math.pi * (freq * 2) * t) +
                0.10 * math.sin(2 * math.pi * (freq * 3) * t)
            )
            buffer[idx] += val

    # Normalisation propre sans saturation (0.92 crête)
    peak = max(abs(x) for x in buffer) if buffer else 1.0
    scale = (0.92 / peak) if peak > 0.92 else 1.0
    buffer = [x * scale for x in buffer]

    out = io.BytesIO()
    with wave.open(out, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        raw = b"".join(struct.pack("<h", int(s * 32767)) for s in buffer)
        wf.writeframes(raw)

    _TROPHY_SOUND_CACHE = "data:audio/wav;base64," + base64.b64encode(out.getvalue()).decode("ascii")
    return _TROPHY_SOUND_CACHE


_ROYAL_FANFARE_MP3_CACHE: Optional[str] = None


def get_royal_fanfare_mp3_base64() -> str:
    """
    Retourne la fanfare royale MP3 officielle sous forme d'URI data base64 (data:audio/mp3;base64,...).
    Mise en cache en mémoire pour une performance instantanée.
    Repli automatique vers le générateur WAV si le fichier venait à manquer.
    """
    global _ROYAL_FANFARE_MP3_CACHE
    if _ROYAL_FANFARE_MP3_CACHE is not None:
        return _ROYAL_FANFARE_MP3_CACHE

    candidate_paths = [
        os.path.join(os.path.dirname(os.path.dirname(__file__)), "assets", "audio", "fanfare_royale.mp3"),
        os.path.join(os.path.dirname(__file__), "..", "assets", "audio", "fanfare_royale.mp3"),
        os.path.abspath("assets/audio/fanfare_royale.mp3"),
    ]

    for p in candidate_paths:
        if os.path.exists(p):
            try:
                with open(p, "rb") as f:
                    data = f.read()
                if len(data) > 0:
                    _ROYAL_FANFARE_MP3_CACHE = "data:audio/mp3;base64," + base64.b64encode(data).decode("ascii")
                    return _ROYAL_FANFARE_MP3_CACHE
            except Exception as e:
                logger.warning(f"Impossible de charger fanfare_royale.mp3 depuis {p}: {e}")

    # Repli de secours vers la synthèse WAV
    return generate_trophy_sound_wav_base64()


def generate_trophy_celebration_html(
    auto_play: bool = True,
    widget_id: str = "trophy_celebration",
    show_button: bool = False,
    button_label: str = "🎺 Fanfare Royale",
) -> str:
    """
    Génère le composant HTML5 / Web Audio pour jouer la fanfare royale MP3 lors de la remise d'un trophée,
    accompagnée d'une animation grandiose de couronnement : double canon héraldique projetant
    des étincelles dorées, des étoiles scintillantes et des couronnes royales (Canvas).
    - Audio MP3 officiel embarqué en base64 pour un déclenchement instantané.
    - Animation de particules Canvas plein écran, fluide, sans dépendance externe et auto-nettoyante.
    """
    audio_uri = get_royal_fanfare_mp3_base64()
    clean_id = re.sub(r"[^a-zA-Z0-9_]", "_", widget_id)
    auto_play_js = "true" if auto_play else "false"

    btn_html = ""
    if show_button:
        btn_html = f"""
        <button id="btn_{clean_id}" onclick="playRoyalCelebration_{clean_id}()" 
          title="Écouter la fanfare royale des trophées"
          style="background: linear-gradient(135deg, #d97706 0%, #b45309 100%); color: #ffffff; border: 1.2px solid #fbbf24; border-radius: 20px; padding: 6px 14px; font-size: 0.82rem; font-weight: 700; cursor: pointer; box-shadow: 0 4px 12px rgba(245, 158, 11, 0.35); display: inline-flex; align-items: center; gap: 6px; transition: transform 0.15s ease;">
          <span>{html.escape(button_label)}</span>
        </button>
        """

    return f"""
    <div id="container_{clean_id}" style="display: {'inline-block' if show_button else 'none'}; margin: 0; padding: 0;">
      <audio id="audio_{clean_id}" preload="auto" src="{audio_uri}"></audio>
      {btn_html}
      <script>
        (function() {{
          function launchRoyalAnimation_{clean_id}() {{
            let targetDoc = document;
            try {{
              if (window.parent && window.parent.document && window.parent.document.body) {{
                targetDoc = window.parent.document;
              }}
            }} catch (e) {{
              targetDoc = document;
            }}

            const oldCanvases = targetDoc.querySelectorAll("canvas[id^='royal_fanfare_canvas']");
            for (let k = 0; k < oldCanvases.length; k++) {{
              try {{ oldCanvases[k].remove(); }} catch (e) {{}}
            }}

            const canvas = targetDoc.createElement("canvas");
            canvas.id = "royal_fanfare_canvas_{clean_id}";
            canvas.style.position = "fixed";
            canvas.style.top = "0";
            canvas.style.left = "0";
            canvas.style.width = "100vw";
            canvas.style.height = "100vh";
            canvas.style.pointerEvents = "none";
            canvas.style.zIndex = "9999999";
            targetDoc.body.appendChild(canvas);

            const targetWin = targetDoc.defaultView || window;
            const w = targetWin.innerWidth || 1280;
            const h = targetWin.innerHeight || 720;
            canvas.width = w;
            canvas.height = h;
            const ctx = canvas.getContext("2d");
            if (!ctx) return;

            const particles = [];
            const goldPalette = ["#FFD700", "#F59E0B", "#FBBF24", "#FEF08A", "#D97706", "#FFFBEB", "#FFFFFF"];
            const starSymbols = ["✨", "⭐", "★", "✦"];

            // 1. Canons héraldiques latéraux (gauche et droite)
            const cannonCount = 70;
            for (let i = 0; i < cannonCount; i++) {{
              // Canon gauche
              particles.push({{
                x: w * 0.12,
                y: h * 0.88,
                vx: 3 + Math.random() * 11,
                vy: -(12 + Math.random() * 14),
                gravity: 0.38,
                friction: 0.985,
                angle: Math.random() * Math.PI * 2,
                vRot: (Math.random() - 0.5) * 0.18,
                size: 14 + Math.random() * 16,
                color: goldPalette[Math.floor(Math.random() * goldPalette.length)],
                shape: Math.random() < 0.22 ? "crown" : (Math.random() < 0.55 ? "star" : "diamond"),
                symbol: starSymbols[Math.floor(Math.random() * starSymbols.length)],
                alpha: 1.0,
              }});
              // Canon droit
              particles.push({{
                x: w * 0.88,
                y: h * 0.88,
                vx: -(3 + Math.random() * 11),
                vy: -(12 + Math.random() * 14),
                gravity: 0.38,
                friction: 0.985,
                angle: Math.random() * Math.PI * 2,
                vRot: (Math.random() - 0.5) * 0.18,
                size: 14 + Math.random() * 16,
                color: goldPalette[Math.floor(Math.random() * goldPalette.length)],
                shape: Math.random() < 0.22 ? "crown" : (Math.random() < 0.55 ? "star" : "diamond"),
                symbol: starSymbols[Math.floor(Math.random() * starSymbols.length)],
                alpha: 1.0,
              }});
            }}

            // 2. Pluie centrale scintillante
            const showerCount = 35;
            for (let i = 0; i < showerCount; i++) {{
              particles.push({{
                x: w * (0.25 + 0.5 * Math.random()),
                y: h * (0.15 + 0.2 * Math.random()),
                vx: (Math.random() - 0.5) * 5,
                vy: -(3 + Math.random() * 6),
                gravity: 0.22,
                friction: 0.99,
                angle: Math.random() * Math.PI * 2,
                vRot: (Math.random() - 0.5) * 0.12,
                size: 12 + Math.random() * 14,
                color: goldPalette[Math.floor(Math.random() * goldPalette.length)],
                shape: Math.random() < 0.3 ? "crown" : "star",
                symbol: starSymbols[Math.floor(Math.random() * starSymbols.length)],
                alpha: 1.0,
              }});
            }}

            const startTime = performance.now();
            const duration = 2600; // ms synchronisé avec la fanfare MP3

            function renderFrame(now) {{
              const elapsed = now - startTime;
              if (elapsed >= duration || !canvas.parentNode) {{
                try {{ canvas.remove(); }} catch (e) {{}}
                return;
              }}

              ctx.clearRect(0, 0, canvas.width, canvas.height);
              const progress = elapsed / duration;
              const globalFade = progress > 0.65 ? Math.max(0, 1 - (progress - 0.65) / 0.35) : 1;

              for (let i = 0; i < particles.length; i++) {{
                const p = particles[i];
                p.x += p.vx;
                p.y += p.vy;
                p.vy += p.gravity;
                p.vx *= p.friction;
                p.vy *= p.friction;
                p.angle += p.vRot;

                ctx.save();
                ctx.translate(p.x, p.y);
                ctx.rotate(p.angle);
                ctx.globalAlpha = Math.max(0, p.alpha * globalFade);

                if (p.shape === "crown") {{
                  ctx.font = Math.round(p.size) + "px serif";
                  ctx.textAlign = "center";
                  ctx.textBaseline = "middle";
                  ctx.fillText("👑", 0, 0);
                }} else if (p.shape === "star") {{
                  ctx.font = Math.round(p.size) + "px serif";
                  ctx.textAlign = "center";
                  ctx.textBaseline = "middle";
                  ctx.fillText(p.symbol || "✨", 0, 0);
                }} else if (p.shape === "diamond") {{
                  ctx.fillStyle = p.color;
                  ctx.shadowColor = "#FBBF24";
                  ctx.shadowBlur = 8;
                  const s = p.size * 0.45;
                  ctx.beginPath();
                  ctx.moveTo(0, -s);
                  ctx.lineTo(s * 0.8, 0);
                  ctx.lineTo(0, s);
                  ctx.lineTo(-s * 0.8, 0);
                  ctx.closePath();
                  ctx.fill();
                }} else {{
                  ctx.fillStyle = p.color;
                  ctx.shadowColor = "#FFD700";
                  ctx.shadowBlur = 6;
                  ctx.beginPath();
                  ctx.arc(0, 0, p.size * 0.3, 0, Math.PI * 2);
                  ctx.fill();
                }}

                ctx.restore();
              }}

              requestAnimationFrame(renderFrame);
            }}

            requestAnimationFrame(renderFrame);
          }}

          function playRoyalCelebration_{clean_id}() {{
            // 1. Déclenchement de l'animation royale Canvas
            try {{
              launchRoyalAnimation_{clean_id}();
            }} catch (e) {{
              console.log("Animation royale:", e);
            }}

            // 2. Déclenchement du son MP3 royal
            const a = document.getElementById("audio_{clean_id}");
            if (a) {{
              try {{
                a.currentTime = 0;
                const prom = a.play();
                if (prom && prom.catch) {{
                  prom.catch(function(e) {{
                    console.log("Lecture audio HTML5 différée, essai direct Audio() :", e);
                    try {{
                      const snd = new Audio("{audio_uri}");
                      snd.play().catch(function() {{}});
                    }} catch(err) {{}}
                  }});
                }}
              }} catch (e) {{
                try {{
                  const snd = new Audio("{audio_uri}");
                  snd.play().catch(function() {{}});
                }} catch(err) {{}}
              }}
            }}
          }}

          window.playRoyalCelebration_{clean_id} = playRoyalCelebration_{clean_id};
          window.playTrophySound_{clean_id} = playRoyalCelebration_{clean_id};

          if ({auto_play_js}) {{
            setTimeout(playRoyalCelebration_{clean_id}, 120);
          }}
        }})();
      </script>
      <!-- stream_nonce_{int(time.time() * 1000)} -->
    </div>
    """
