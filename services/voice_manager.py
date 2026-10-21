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
            "tooltip_play": "استمع إلى إجابة الأستاذ سَنَد",
            "tooltip_stop": "إيقاف الصوت",
            "dir": "rtl",
            "mic_label": "🎙️ تحدث بالصوت",
            "mic_tooltip": "تحدث إلى سند (تسجيل صوتي بالمايكروفون)",
            "mic_listening": "🔴 جاري الاستماع...",
        }
    elif lang == "en":
        return {
            "lang_code": "en-US",
            "play_label": "🔊 Listen to Sanad",
            "stop_label": "⏹️ Stop Audio",
            "speaking_label": "🔊 Speaking...",
            "tooltip_play": "Listen to Sanad's response",
            "tooltip_stop": "Stop speaking",
            "dir": "ltr",
            "mic_label": "🎙️ Speak to Sanad",
            "mic_tooltip": "Speak to Sanad (Microphone dictation)",
            "mic_listening": "🔴 Listening...",
        }
    else:
        return {
            "lang_code": "fr-FR",
            "play_label": "🔊 Écouter Sanad",
            "stop_label": "⏹️ Arrêter",
            "speaking_label": "🔊 Sanad parle...",
            "tooltip_play": "Écouter la réponse de Sanad",
            "tooltip_stop": "Arrêter la voix",
            "dir": "ltr",
            "mic_label": "🎙️ Parler à Sanad",
            "mic_tooltip": "Parler à Sanad (Dictée vocale au micro)",
            "mic_listening": "🔴 Écoute en cours...",
        }


# SVG Icons
SVG_SPEAKER = """<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polygon points="11 5 6 9 2 9 2 15 6 15 11 19 11 5"></polygon><path d="M15.54 8.46a5 5 0 0 1 0 7.07"></path><path d="M19.07 4.93a10 10 0 0 1 0 14.14"></path></svg>"""
SVG_STOP = """<svg width="13" height="13" viewBox="0 0 24 24" fill="currentColor"><rect x="5" y="5" width="14" height="14" rx="2" ry="2"></rect></svg>"""
SVG_MIC = """<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 1a3 3 0 0 0-3 3v8a3 3 0 0 0 6 0V4a3 3 0 0 0-3-3z"></path><path d="M19 10v2a7 7 0 0 1-14 0v-2"></path><line x1="12" y1="19" x2="12" y2="23"></line><line x1="8" y1="23" x2="16" y2="23"></line></svg>"""


def generate_tts_player_html(
    text: str,
    language: str = "fr",
    player_id: str = "sanad_voice",
    rate: float = 1.0,
    pitch: float = 1.0,
    compact: bool = True,
    auto_play: bool = False,
) -> str:
    """
    Génère un composant HTML/JavaScript autonome et réactif pour la synthèse vocale.
    En mode compact (par défaut) : affiche uniquement une icône circulaire élégante sans texte,
    parfaitement adaptée pour être logée à côté de l'icône du robot Sanad.
    Supporte la lecture automatique (auto_play=True).
    Coût : 0 token Gemini, latence 0ms, 100% gratuit.
    """
    cleaned = clean_text_for_speech(text)
    if not cleaned:
        return ""

    cfg = get_speech_config(language)
    lang_code = cfg["lang_code"]
    tooltip_play = cfg["tooltip_play"]
    tooltip_stop = cfg["tooltip_stop"]
    direction = cfg["dir"]

    # Sérialisation JSON pour échapper proprement tous les caractères
    json_text = json.dumps(cleaned)
    clean_id = re.sub(r"[^a-zA-Z0-9_]", "_", player_id)

    # Styles du bouton selon mode compact ou texte
    if compact:
        btn_content = SVG_SPEAKER
        btn_style = (
            "display: inline-flex; align-items: center; justify-content: center; "
            "width: 28px; height: 28px; border-radius: 50%; "
            "color: #2563eb; background: #eff6ff; border: 1px solid #bfdbfe; "
            "cursor: pointer; transition: all 0.2s ease; padding: 0; box-shadow: 0 1px 2px rgba(0,0,0,0.04);"
        )
    else:
        btn_content = f"{SVG_SPEAKER} <span id='label_{clean_id}' style='margin-left: 5px;'>{cfg['play_label']}</span>"
        btn_style = (
            "display: inline-flex; align-items: center; gap: 6px; padding: 4px 10px; "
            "font-size: 12px; font-weight: 500; color: #1e3a8a; background: #eff6ff; "
            "border: 1px solid #bfdbfe; border-radius: 16px; cursor: pointer; transition: all 0.2s ease;"
        )

    html_code = f"""
    <div id="wrapper_{clean_id}" style="display: inline-block; margin: 0; padding: 0; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; direction: {direction};">
      <style>
        #btn_{clean_id}:hover {{
          transform: scale(1.08);
          background: #dbeafe !important;
          border-color: #93c5fd !important;
        }}
        @keyframes pulseAudio_{clean_id} {{
          0% {{ box-shadow: 0 0 0 0 rgba(220, 38, 38, 0.4); }}
          70% {{ box-shadow: 0 0 0 6px rgba(220, 38, 38, 0); }}
          100% {{ box-shadow: 0 0 0 0 rgba(220, 38, 38, 0); }}
        }}
        .speaking-active_{clean_id} {{
          animation: pulseAudio_{clean_id} 1.5s infinite;
        }}
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
            }}
            if (icn) {{
              if (isCompact) {{
                icn.innerHTML = svgSpeaker;
              }} else {{
                icn.innerHTML = svgSpeaker + " <span id='label_{clean_id}' style='margin-left:5px;'>{cfg['play_label']}</span>";
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
            }}
            if (icn) {{
              if (isCompact) {{
                icn.innerHTML = svgStop;
              }} else {{
                icn.innerHTML = svgStop + " <span id='label_{clean_id}' style='margin-left:5px;'>{cfg['stop_label']}</span>";
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
                  const natural = matched.find(v => v.name.includes("Google") || v.name.includes("Natural") || v.name.includes("Online"));
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
              if (window.SpeechRecognition) return window.SpeechRecognition;
              if (window.webkitSpeechRecognition) return window.webkitSpeechRecognition;
              if (window.parent) {{
                if (window.parent.SpeechRecognition) return window.parent.SpeechRecognition;
                if (window.parent.webkitSpeechRecognition) return window.parent.webkitSpeechRecognition;
              }}
            }} catch(e) {{}}
            return null;
          }}

          let recognition = null;
          let isListening = false;
          let micBtn = null;

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
                alert("La reconnaissance vocale par micro nécessite un navigateur compatible (Chrome, Edge, Safari).");
                return;
              }}

              try {{
                recognition = new RecClass();
                recognition.lang = micBtn.dataset.langCode || langCode;
                recognition.continuous = false;
                recognition.interimResults = true;

                recognition.onstart = function() {{
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
                  if (txt) {{
                    insertTextIntoChatInput(txt);
                  }}
                }};

                recognition.onerror = function() {{
                  setMicListeningState(false);
                }};

                recognition.onend = function() {{
                  setMicListeningState(false);
                }};

                recognition.start();
              }} catch(err) {{
                setMicListeningState(false);
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
              micBtn.title = "🔴 Écoute en cours... Cliquez pour terminer";
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
            const textarea = pDoc.querySelector('textarea[data-testid="stChatInputTextArea"]');
            if (textarea) {{
              textarea.value = text;
              textarea.dispatchEvent(new Event('input', {{ bubbles: true }}));
              textarea.focus();
            }}
          }}

          // Tenter d'injecter immédiatement et avec un observateur
          setupMic();
          const timer = setInterval(setupMic, 400);
          setTimeout(() => clearInterval(timer), 6000);
        }})();
      </script>
    </div>
    """
    return html_code


# Rétrocompatibilité pour les anciens appels
def generate_mic_speech_html(language: str = "fr", widget_id: str = "sanad_mic") -> str:
    """Conservé pour rétrocompatibilité : délègue à l'injecteur moderne."""
    return generate_chat_mic_injector_html(language=language, widget_id=widget_id)
