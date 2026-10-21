"""
Module de gestion vocale pour le tuteur socratique Sanad.
Fournit :
1. Nettoyage de texte pédagogique pour une élocution naturelle (suppression du Markdown, LaTeX, émojis).
2. Synthèse vocale trilingue (Français, Arabe, Anglais) basée sur la Web Speech API native du navigateur.
3. Zéro consommation de quota ou de jetons Google Gemini (100% gratuit côté client).
"""

import html
import json
import re
from typing import Any, Dict


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

    # 3. Remplacer les formules LaTeX display $$ ... $$ par le contenu ou une pause
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

    # 7. Supprimer les titres Markdown (#, ##, ###)
    s = re.sub(r"^\s*#{1,6}\s*", "", s, flags=re.MULTILINE)

    # 8. Supprimer les listes à puces (- , * , 1. ) en début de ligne
    s = re.sub(r"^\s*[-*•]\s+", "", s, flags=re.MULTILINE)
    s = re.sub(r"^\s*\d+\.\s+", "", s, flags=re.MULTILINE)

    # 9. Supprimer les séparateurs horizontaux (--- ou ***)
    s = re.sub(r"^\s*[-*_]{3,}\s*$", "", s, flags=re.MULTILINE)

    # 10. Supprimer les citations Markdown (> ...)
    s = re.sub(r"^\s*>\s*", "", s, flags=re.MULTILINE)

    # 11. Nettoyer les symboles spéciaux et émojis décoratifs qui polluent la diction
    # On conserve la ponctuation essentielle : . , ! ? : ; ' " - ()
    # Les émojis unicode courants (plages \U00010000 à \U0010ffff et quelques symboles)
    s = re.sub(
        r"[\U00010000-\U0010ffff]|[\u2600-\u26ff]|[\u2700-\u27bf]|[\u2300-\u23ff]",
        "",
        s,
    )

    # 12. Remplacer les sauts de lignes et espaces multiples par un espace unique
    s = re.sub(r"\s+", " ", s).strip()

    return s


def get_speech_config(language: str) -> Dict[str, str]:
    """Retourne la configuration linguistique (code BCP 47, libellés) selon la matière."""
    lang = (language or "fr").lower().strip()
    if lang == "ar":
        return {
            "lang_code": "ar-SA",
            "play_label": "🔊 استمع إلى سَنَد",
            "stop_label": "⏹️ إيقاف الصوت",
            "speaking_label": "🔊 جاري التحدث...",
            "tooltip": "الاستماع إلى نصائح وتوجيهات الأستاذ سند",
            "dir": "rtl",
            "mic_label": "🎙️ تحدث بالصوت",
            "mic_listening": "🔴 جاري الاستماع...",
        }
    elif lang == "en":
        return {
            "lang_code": "en-US",
            "play_label": "🔊 Listen to Sanad",
            "stop_label": "⏹️ Stop Audio",
            "speaking_label": "🔊 Speaking...",
            "tooltip": "Listen to Sanad's guidance",
            "dir": "ltr",
            "mic_label": "🎙️ Speak to Sanad",
            "mic_listening": "🔴 Listening...",
        }
    else:
        return {
            "lang_code": "fr-FR",
            "play_label": "🔊 Écouter Sanad",
            "stop_label": "⏹️ Arrêter",
            "speaking_label": "🔊 Sanad parle...",
            "tooltip": "Écouter les conseils de Sanad à voix haute",
            "dir": "ltr",
            "mic_label": "🎙️ Parler à Sanad",
            "mic_listening": "🔴 Écoute en cours...",
        }


def generate_tts_player_html(
    text: str,
    language: str = "fr",
    player_id: str = "sanad_voice",
    rate: float = 1.0,
    pitch: float = 1.0,
) -> str:
    """
    Génère un composant HTML/JavaScript autonome et réactif pour la synthèse vocale.
    Utilise la Web Speech API native du navigateur (SpeechSynthesis).
    Coût : 0 token Gemini, latence 0ms, 100% gratuit.
    """
    cleaned = clean_text_for_speech(text)
    if not cleaned:
        return ""

    cfg = get_speech_config(language)
    lang_code = cfg["lang_code"]
    play_label = cfg["play_label"]
    stop_label = cfg["stop_label"]
    direction = cfg["dir"]

    # Sérialisation JSON pour échapper proprement tous les caractères (guillemets, accents, retours)
    json_text = json.dumps(cleaned)
    clean_id = re.sub(r"[^a-zA-Z0-9_]", "_", player_id)

    html_code = f"""
    <div id="wrapper_{clean_id}" style="display: inline-block; margin: 4px 0 6px 0; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; direction: {direction};">
      <button id="btn_{clean_id}" 
              onclick="toggleSpeech_{clean_id}()" 
              title="{html.escape(cfg['tooltip'])}"
              style="display: inline-flex; align-items: center; gap: 6px; padding: 4px 10px; font-size: 12px; font-weight: 500; color: #1e3a8a; background: #eff6ff; border: 1px solid #bfdbfe; border-radius: 16px; cursor: pointer; transition: all 0.2s ease; box-shadow: 0 1px 2px rgba(0,0,0,0.05);">
        <span id="label_{clean_id}">{play_label}</span>
      </button>

      <script>
        (function() {{
          const cleanText = {json_text};
          const langCode = '{lang_code}';
          const rateVal = {rate};
          const pitchVal = {pitch};

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
            const lbl = document.getElementById("label_{clean_id}");
            if (lbl) lbl.textContent = "{play_label}";
            if (btn) {{
              btn.style.background = "#eff6ff";
              btn.style.borderColor = "#bfdbfe";
              btn.style.color = "#1e3a8a";
            }}
          }}

          function setSpeakingUI() {{
            isSpeaking = true;
            const btn = document.getElementById("btn_{clean_id}");
            const lbl = document.getElementById("label_{clean_id}");
            if (lbl) lbl.textContent = "{stop_label}";
            if (btn) {{
              btn.style.background = "#fee2e2";
              btn.style.borderColor = "#fca5a5";
              btn.style.color = "#991b1b";
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

            // Tentative de sélection d'une voix naturelle si disponible
            try {{
              const voices = synth.getVoices();
              if (voices && voices.length > 0) {{
                const prefix = langCode.split('-')[0].toLowerCase();
                const matched = voices.filter(v => v.lang && v.lang.toLowerCase().startsWith(prefix));
                if (matched.length > 0) {{
                  const natural = matched.find(v => v.name.includes("Google") || v.name.includes("Natural"));
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

          // Réinitialiser l'UI si la page se décharge
          window.addEventListener('beforeunload', function() {{
            const synth = getSynth();
            if (synth) synth.cancel();
          }});
        }})();
      </script>
    </div>
    """
    return html_code


def generate_mic_speech_html(language: str = "fr", widget_id: str = "sanad_mic") -> str:
    """
    Génère un widget interactif de dictée vocale (Speech-to-Text) au micro.
    Permet à l'élève de dicter sa question à Sanad sans taper au clavier.
    Coût : 0 token Gemini, 100% exécuté localement par l'API SpeechRecognition.
    """
    cfg = get_speech_config(language)
    lang_code = cfg["lang_code"]
    mic_label = cfg["mic_label"]
    mic_listening = cfg["mic_listening"]
    direction = cfg["dir"]
    clean_id = re.sub(r"[^a-zA-Z0-9_]", "_", widget_id)

    html_code = f"""
    <div id="mic_wrapper_{clean_id}" style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; direction: {direction}; margin: 4px 0 8px 0;">
      <div style="display: flex; align-items: center; gap: 8px; flex-wrap: wrap;">
        <button id="mic_btn_{clean_id}" 
                onclick="toggleMic_{clean_id}()" 
                title="Cliquez pour parler à Sanad au micro"
                style="display: inline-flex; align-items: center; gap: 6px; padding: 5px 12px; font-size: 13px; font-weight: 500; color: #065f46; background: #ecfdf5; border: 1px solid #a7f3d0; border-radius: 18px; cursor: pointer; transition: all 0.2s ease;">
          <span id="mic_icon_{clean_id}">🎙️</span>
          <span id="mic_label_{clean_id}">{mic_label}</span>
        </button>
        <span id="mic_status_{clean_id}" style="font-size: 12px; color: #6b7280; font-style: italic;"></span>
      </div>

      <div id="mic_result_box_{clean_id}" style="display: none; margin-top: 6px; padding: 8px 12px; background: #f9fafb; border: 1px dashed #d1d5db; border-radius: 8px; font-size: 13px; color: #1f2937;">
        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 4px;">
          <span style="font-size: 11px; font-weight: 600; color: #4b5563;">Transcription de votre question :</span>
          <button id="mic_copy_btn_{clean_id}" onclick="copyMicText_{clean_id}()" style="padding: 2px 8px; font-size: 11px; background: #e0e7ff; color: #3730a3; border: none; border-radius: 4px; cursor: pointer;">
            📋 Copier dans ma question
          </button>
        </div>
        <div id="mic_text_{clean_id}" style="font-weight: 500; color: #111827;"></div>
      </div>

      <script>
        (function() {{
          const langCode = '{lang_code}';
          let recognition = null;
          let isListening = false;
          let finalTranscript = '';

          function getRecognition() {{
            try {{
              const SpeechRec = window.SpeechRecognition || window.webkitSpeechRecognition;
              if (SpeechRec) return new SpeechRec();
              if (window.parent) {{
                const pSpeechRec = window.parent.SpeechRecognition || window.parent.webkitSpeechRecognition;
                if (pSpeechRec) return new pSpeechRec();
              }}
            }} catch(e) {{}}
            return null;
          }}

          function setListeningUI(listening) {{
            isListening = listening;
            const btn = document.getElementById("mic_btn_{clean_id}");
            const lbl = document.getElementById("mic_label_{clean_id}");
            const st = document.getElementById("mic_status_{clean_id}");
            if (listening) {{
              if (lbl) lbl.textContent = "{mic_listening}";
              if (btn) {{
                btn.style.background = "#fee2e2";
                btn.style.borderColor = "#fca5a5";
                btn.style.color = "#991b1b";
              }}
              if (st) st.textContent = "Parlez maintenant distinctement...";
            }} else {{
              if (lbl) lbl.textContent = "{mic_label}";
              if (btn) {{
                btn.style.background = "#ecfdf5";
                btn.style.borderColor = "#a7f3d0";
                btn.style.color = "#065f46";
              }}
              if (st) st.textContent = "";
            }}
          }}

          window.toggleMic_{clean_id} = function() {{
            if (isListening && recognition) {{
              recognition.stop();
              setListeningUI(false);
              return;
            }}

            recognition = getRecognition();
            if (!recognition) {{
              alert("La reconnaissance vocale par micro n'est pas disponible dans ce contexte. Vous pouvez taper votre question directement.");
              return;
            }}

            recognition.lang = langCode;
            recognition.continuous = false;
            recognition.interimResults = true;
            finalTranscript = '';

            recognition.onstart = function() {{
              setListeningUI(true);
            }};

            recognition.onresult = function(event) {{
              let interim = '';
              for (let i = event.resultIndex; i < event.results.length; ++i) {{
                if (event.results[i].isFinal) {{
                  finalTranscript += event.results[i][0].transcript;
                }} else {{
                  interim += event.results[i][0].transcript;
                }}
              }}
              const current = finalTranscript || interim;
              const box = document.getElementById("mic_result_box_{clean_id}");
              const txt = document.getElementById("mic_text_{clean_id}");
              if (box && txt && current) {{
                box.style.display = "block";
                txt.textContent = current;
              }}
            }};

            recognition.onerror = function(event) {{
              setListeningUI(false);
            }};

            recognition.onend = function() {{
              setListeningUI(false);
              // Tenter d'injecter automatiquement le texte dans le chat Streamlit si accessible
              try {{
                if (finalTranscript && window.parent && window.parent.document) {{
                  const textarea = window.parent.document.querySelector('textarea[data-testid="stChatInputTextArea"]');
                  if (textarea) {{
                    textarea.value = finalTranscript;
                    textarea.dispatchEvent(new Event('input', {{ bubbles: true }}));
                  }}
                }}
              }} catch(e) {{}}
            }};

            try {{
              recognition.start();
            }} catch(err) {{
              setListeningUI(false);
            }}
          }};

          window.copyMicText_{clean_id} = function() {{
            const txt = document.getElementById("mic_text_{clean_id}");
            const btn = document.getElementById("mic_copy_btn_{clean_id}");
            if (txt && txt.textContent) {{
              navigator.clipboard.writeText(txt.textContent).then(function() {{
                if (btn) {{
                  btn.textContent = "✅ Copié !";
                  setTimeout(() => {{ btn.textContent = "📋 Copier dans ma question"; }}, 2000);
                }}
              }});
            }}
          }};
        }})();
      </script>
    </div>
    """
    return html_code
