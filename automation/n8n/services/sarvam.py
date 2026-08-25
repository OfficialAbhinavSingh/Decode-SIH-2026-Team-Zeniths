"""Sarvam AI Indic Language Translation Service.

Integrates with Sarvam AI's Mayura Translation API (https://api.sarvam.ai/translate)
for high-accuracy translation of 10+ Indian languages (Hindi, Tamil, Telugu,
Kannada, Marathi, Bengali, Gujarati, Malayalam, Punjabi, Odia) to English.

Includes an offline heuristic fallback so local testing & demos work without an active API key.
"""

import json
import logging
import os
import re
import urllib.request
import urllib.error
from dataclasses import dataclass

try:
    import httpx
except ImportError:
    httpx = None

logger = logging.getLogger(__name__)

SARVAM_API_KEY = os.environ.get("SARVAM_API_KEY", "")
SARVAM_TRANSLATE_URL = os.environ.get(
    "SARVAM_TRANSLATE_URL",
    "https://api.sarvam.ai/translate",
)

# Unicode script patterns for Indian languages
SCRIPT_PATTERNS = {
    "hi": re.compile(r"[\u0900-\u097F]"),  # Devanagari (Hindi, Marathi, Sanskrit)
    "bn": re.compile(r"[\u0980-\u09FF]"),  # Bengali / Assamese
    "pa": re.compile(r"[\u0A00-\u0A7F]"),  # Gurmukhi (Punjabi)
    "gu": re.compile(r"[\u0A80-\u0AFF]"),  # Gujarati
    "or": re.compile(r"[\u0B00-\u0B7F]"),  # Odia
    "ta": re.compile(r"[\u0B80-\u0BFF]"),  # Tamil
    "te": re.compile(r"[\u0C00-\u0C7F]"),  # Telugu
    "kn": re.compile(r"[\u0C80-\u0CFF]"),  # Kannada
    "ml": re.compile(r"[\u0D00-\u0D7F]"),  # Malayalam
}

# Sarvam AI BCP-47 language tag mapping
SARVAM_LANGUAGE_MAP = {
    "hi": "hi-IN",
    "ta": "ta-IN",
    "kn": "kn-IN",
    "te": "te-IN",
    "mr": "mr-IN",
    "bn": "bn-IN",
    "gu": "gu-IN",
    "ml": "ml-IN",
    "pa": "pa-IN",
    "or": "od-IN",
    "od": "od-IN",
}

# Domain dictionary for common water leak keywords in Indian languages
OFFLINE_DICTIONARY = {
    "पानी बह रहा है": "water is flowing",
    "पानी लीक हो रहा है": "water is leaking",
    "पाइप टूट गया है": "pipe is broken",
    "सड़क पर पानी": "water on the road",
    "स्कूल के पास": "near the school",
    "मेन रोड": "main road",
    "नल से गंदा पानी": "dirty water from tap",
    "पानी की बर्बादी": "water wastage",
    "कम दबाव": "low pressure",
    "सड़क धंस गई": "road subsided due to water",
    # Tamil
    "தண்ணீர் கசிகிறது": "water is leaking",
    "குழாய் உடைந்தது": "pipe is broken",
    "சாலையில் தண்ணீர்": "water on the road",
    "பள்ளி அருகில்": "near the school",
    # Kannada
    "ನೀರು ಸೋರುತ್ತಿದೆ": "water is leaking",
    "ಪೈಪ್ ಒಡೆದಿದೆ": "pipe is broken",
    "ರಸ್ತೆಯಲ್ಲಿ ನೀರು": "water on the road",
    # Telugu
    "నీరు లీక్ అవుతోంది": "water is leaking",
    "పైపు పగిలిపోయింది": "pipe is broken",
    "రోడ్డుపై నీరు": "water on the road",
    # Marathi
    "पाणी वाहत आहे": "water is overflowing",
    "पाईप फुटला आहे": "pipe is burst",
}


@dataclass
class TranslationResult:
    original_text: str
    detected_language: str
    translated_text: str
    is_translated: bool
    confidence: float
    source: str  # "sarvam-ai" or "offline-fallback"


class SarvamService:
    """Indic language detection and translation engine powered by Sarvam AI."""

    def __init__(
        self,
        api_key: str = SARVAM_API_KEY,
        translate_url: str = SARVAM_TRANSLATE_URL,
    ) -> None:
        self.api_key = api_key
        self.translate_url = translate_url

    def detect_language(self, text: str) -> str:
        """Detect language from script heuristics or defaults."""
        if not text or text.strip() == "":
            return "en"

        for lang, pattern in SCRIPT_PATTERNS.items():
            if pattern.search(text):
                return lang

        return "en"

    def translate_offline(self, text: str, source_lang: str) -> str:
        """Heuristic offline translation for local testing & demos."""
        if source_lang == "en":
            return text

        result = text
        for phrase, translation in OFFLINE_DICTIONARY.items():
            if phrase in result:
                result = result.replace(phrase, translation)

        if result == text:
            lang_names = {
                "hi": "Hindi",
                "ta": "Tamil",
                "kn": "Kannada",
                "te": "Telugu",
                "mr": "Marathi",
                "bn": "Bengali",
                "gu": "Gujarati",
            }
            lang_name = lang_names.get(source_lang, source_lang)
            return f"[Citizen report in {lang_name}]: {text}"

        return result

    def translate_sync(self, text: str, target_lang: str = "en") -> TranslationResult:
        """Synchronously detect and translate text to target language."""
        if not text or not text.strip():
            return TranslationResult(
                original_text="",
                detected_language="en",
                translated_text="",
                is_translated=False,
                confidence=1.0,
                source="offline-fallback",
            )

        detected_lang = self.detect_language(text)
        if detected_lang == target_lang:
            return TranslationResult(
                original_text=text,
                detected_language=detected_lang,
                translated_text=text,
                is_translated=False,
                confidence=0.98,
                source="offline-fallback",
            )

        source_code = SARVAM_LANGUAGE_MAP.get(detected_lang, "hi-IN")
        target_code = "en-IN"

        # If Sarvam AI API Key is provided, call Sarvam Mayura Translation API
        if self.api_key:
            try:
                headers = {
                    "api-subscription-key": self.api_key,
                    "Content-Type": "application/json",
                }
                payload = {
                    "input": text,
                    "source_language_code": source_code,
                    "target_language_code": target_code,
                    "speaker_gender": "Female",
                    "mode": "formal",
                    "model": "mayura:v1",
                }
                if httpx is not None:
                    with httpx.Client(timeout=5.0) as client:
                        resp = client.post(self.translate_url, json=payload, headers=headers)
                        if resp.status_code == 200:
                            data = resp.json()
                            out_text = data.get("translated_text", text)
                            return TranslationResult(
                                original_text=text,
                                detected_language=detected_lang,
                                translated_text=out_text,
                                is_translated=True,
                                confidence=0.96,
                                source="sarvam-ai",
                            )
                else:
                    req = urllib.request.Request(
                        self.translate_url,
                        data=json.dumps(payload).encode("utf-8"),
                        headers=headers,
                    )
                    with urllib.request.urlopen(req, timeout=5.0) as resp:
                        if resp.status == 200:
                            data = json.loads(resp.read().decode("utf-8"))
                            out_text = data.get("translated_text", text)
                            return TranslationResult(
                                original_text=text,
                                detected_language=detected_lang,
                                translated_text=out_text,
                                is_translated=True,
                                confidence=0.96,
                                source="sarvam-ai",
                            )
            except Exception as e:
                logger.warning(f"Sarvam AI API call failed, falling back to offline NLP: {e}")

        # Fallback offline translation
        offline_translation = self.translate_offline(text, detected_lang)
        return TranslationResult(
            original_text=text,
            detected_language=detected_lang,
            translated_text=offline_translation,
            is_translated=True,
            confidence=0.88,
            source="offline-fallback",
        )
