"""
config.py — Настройки API ключей и модели.

ПОДДЕРЖИВАЕМЫЕ ПРОВАЙДЕРЫ:
─────────────────────────────────────────────────────────────────
  Google Gemini 2.0 Flash (РЕКОМЕНДУЕТСЯ — бесплатно 1M токенов/день!):
    API_KEY  → https://aistudio.google.com/ → Create API Key
    BASE_URL → https://generativelanguage.googleapis.com/v1beta/openai
    Модели   → gemini-2.0-flash | gemini-1.5-flash

  Groq (бесплатно, быстро, ~200K токенов/день):
    API_KEY  → https://console.groq.com/
    BASE_URL → https://api.groq.com/openai/v1
    Модели   → llama-3.3-70b-versatile | mixtral-8x7b-32768
─────────────────────────────────────────────────────────────────

КАК ВСТАВИТЬ КЛЮЧИ В STREAMLIT CLOUD (Settings → Secrets):

  Один ключ:
    OPENAI_API_KEY = "AIzaXXXXXX"
    EMAIL_APP_PASSWORD = "xxxx xxxx xxxx xxxx"

  Несколько ключей (ротация при исчерпании лимита):
    OPENAI_API_KEY = "AIzaКЛЮЧ1,AIzaКЛЮЧ2,AIzaКЛЮЧ3"
    EMAIL_APP_PASSWORD = "xxxx xxxx xxxx xxxx"
"""

import os

# ════════════════════════════════════════════════════════════════
#  Настройки провайдера
# ════════════════════════════════════════════════════════════════

BASE_URL = "https://generativelanguage.googleapis.com/v1beta/openai"
MODEL    = "gemini-2.0-flash"


# ════════════════════════════════════════════════════════════════
#  Ротация ключей — НЕ ТРОГАЙТЕ НИЖЕ
# ════════════════════════════════════════════════════════════════

_key_index = 0


def _read_keys() -> list:
    """Читает ключи из Streamlit secrets или env. Поддерживает список через запятую."""
    raw = ""
    try:
        import streamlit as st
        raw = st.secrets.get("OPENAI_API_KEY", "")
    except Exception:
        pass
    if not raw:
        raw = os.environ.get("OPENAI_API_KEY", "")
    return [k.strip() for k in raw.split(",") if k.strip()]


def get_current_key() -> str:
    keys = _read_keys()
    if not keys:
        return ""
    return keys[_key_index % len(keys)]


def rotate_key() -> str:
    """Переключается на следующий ключ при 429. Возвращает новый ключ."""
    global _key_index
    keys = _read_keys()
    if len(keys) <= 1:
        return keys[0] if keys else ""
    _key_index = (_key_index + 1) % len(keys)
    new_key = keys[_key_index]
    os.environ["OPENAI_API_KEY"] = new_key
    return new_key


def get_keys_count() -> int:
    return len(_read_keys())


def apply():
    """Применяет настройки в os.environ."""
    key = get_current_key()
    if key:
        os.environ["OPENAI_API_KEY"] = key
    if BASE_URL:
        os.environ["OPENAI_BASE_URL"] = BASE_URL
    elif "OPENAI_BASE_URL" in os.environ:
        del os.environ["OPENAI_BASE_URL"]
    if MODEL:
        os.environ["OPENAI_MODEL"] = MODEL


apply()
