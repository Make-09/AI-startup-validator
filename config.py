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
import time
import threading

# Глобальная блокировка для распределения запросов между потоками
_GLOBAL_API_LOCK = threading.Lock()
_last_api_time = 0.0
_MIN_API_INTERVAL = 4.5  # минимум 4.5 секунды между любыми запросами

def rate_limit_sleep():
    """Синхронизированный ограничитель: гарантирует, что между любыми запросами пройдет не менее 4.5 сек."""
    global _last_api_time
    with _GLOBAL_API_LOCK:
        elapsed = time.time() - _last_api_time
        if elapsed < _MIN_API_INTERVAL:
            time.sleep(_MIN_API_INTERVAL - elapsed)
        _last_api_time = time.time()


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
