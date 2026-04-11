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

# ════════════════════════════════════════════════════════════════
#  Настройки провайдера
# ════════════════════════════════════════════════════════════════

BASE_URL = "https://api.groq.com/openai/v1"
MODEL    = "llama-3.3-70b-versatile"
_MIN_API_INTERVAL = 2.1  # Groq: 30 RPM = интервал ~2.01 сек на каждый ключ

# ════════════════════════════════════════════════════════════════
#  Смарт-балансировщик пула ключей (KeyPoolScheduler)
# ════════════════════════════════════════════════════════════════

_pool_lock = threading.Lock()
_key_states = {}

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

def _init_pool():
    global _key_states
    with _pool_lock:
        if not _key_states:
            keys = _read_keys()
            if keys:
                _key_states = {k: 0.0 for k in keys}

def get_best_key_and_wait() -> str:
    """Выдает самый отдохнувший ключ из пула и организует очередь ожидания."""
    _init_pool()
    with _pool_lock:
        if not _key_states:
            return ""
        # Находим ключ, который отдыхал дольше всех
        best_key = min(_key_states, key=_key_states.get)
        elapsed = time.time() - _key_states[best_key]
        if elapsed < _MIN_API_INTERVAL:
            time.sleep(_MIN_API_INTERVAL - elapsed)
        _key_states[best_key] = time.time()
        return best_key

def rotate_key() -> str:
    """Штрафует текущий перегруженный ключ (429 ошибка) и выдает следующий."""
    _init_pool()
    with _pool_lock:
        if not _key_states: return ""
        # Если вызвали эту функцию, значит ключ словил 429. Штрафуем его на 60 секунд.
        best_key = min(_key_states, key=_key_states.get)
        _key_states[best_key] = time.time() + 60.0
        return best_key
        
def rate_limit_sleep():
    """Оставлено для обратной совместимости, но теперь спит внутри get_best_key_and_wait."""
    pass

def get_current_key() -> str:
    return get_best_key_and_wait()

def get_keys_count() -> int:
    return len(_read_keys())

def apply():
    pass
