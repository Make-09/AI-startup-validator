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
import logging
import threading

logger = logging.getLogger(__name__)

# ════════════════════════════════════════════════════════════════
#  Настройки провайдера
# ════════════════════════════════════════════════════════════════

BASE_URL = "https://api.groq.com/openai/v1"
MODEL    = "llama-3.3-70b-versatile"

# Groq free tier: 30 RPM на аккаунт, 6000 RPD
# С 7 ключами: эффективно ~210 RPM, но каждый ключ ≤ 30 RPM
# Интервал на ключ: 60 / 30 = 2.0 сек минимум, с запасом 2.5
_MIN_KEY_INTERVAL = 2.5   # секунд между запросами ОДНОГО ключа
_MIN_GLOBAL_INTERVAL = 0.3  # секунд между ЛЮБЫМИ запросами (защита от burst)

# ════════════════════════════════════════════════════════════════
#  Смарт-балансировщик пула ключей (KeyPoolScheduler)
#
#  Стратегия: Round-Robin с cooldown + penalty
#  - Каждый ключ отслеживает last_used timestamp
#  - Выбирается ключ с наибольшим "отдыхом" (max elapsed)
#  - При 429 ошибке ключ штрафуется на 60 сек
#  - При quota exhausted ключ помечается как dead до конца дня
# ════════════════════════════════════════════════════════════════

_pool_lock = threading.Lock()
_key_pool_initialized = False

# Состояние каждого ключа: {key: {"last_used": float, "errors": int, "dead": bool}}
_key_states = {}
_last_global_call = 0.0


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
    """Инициализирует пул ключей (один раз)."""
    global _key_pool_initialized, _key_states
    if _key_pool_initialized:
        return
    with _pool_lock:
        if _key_pool_initialized:
            return
        keys = _read_keys()
        if keys:
            # Стаггеруем начальные timestamps чтобы ключи не стартовали одновременно
            now = time.time()
            for i, k in enumerate(keys):
                _key_states[k] = {
                    "last_used": now - (len(keys) - i) * _MIN_KEY_INTERVAL,
                    "errors": 0,
                    "dead": False,
                }
            logger.info(f"[config] Инициализирован пул из {len(keys)} API ключей")
        _key_pool_initialized = True


def get_best_key_and_wait() -> str:
    """
    Выдает самый отдохнувший ЖИВОЙ ключ из пула.
    Если все ключи на cooldown — ждёт минимальное необходимое время.
    Если все ключи мертвы (quota exhausted) — возвращает пустую строку.

    ВАЖНО: sleep происходит ВНЕ lock, чтобы не блокировать другие потоки.
    Ключ резервируется сразу через projected_time — другие потоки
    увидят его как "занятый" и выберут следующий свободный.
    """
    global _last_global_call
    _init_pool()

    # ── Фаза 1: под lock — выбираем ключ и вычисляем wait (без sleep!) ──
    with _pool_lock:
        if not _key_states:
            return ""

        now = time.time()

        # Фильтруем живые ключи
        alive_keys = {k: v for k, v in _key_states.items() if not v["dead"]}
        if not alive_keys:
            logger.error("[config] Все API ключи исчерпали дневной лимит!")
            return ""

        # Выбираем ключ с наибольшим elapsed (самый отдохнувший)
        best_key = max(alive_keys, key=lambda k: now - alive_keys[k]["last_used"])
        elapsed = now - alive_keys[best_key]["last_used"]

        # Вычисляем необходимое время ожидания
        key_wait = max(0.0, _MIN_KEY_INTERVAL - elapsed)
        global_wait = max(0.0, _MIN_GLOBAL_INTERVAL - (now - _last_global_call))
        total_wait = max(key_wait, global_wait)

        # Резервируем ключ: ставим last_used на projected time
        # Другие потоки увидят этот ключ как "недавно использованный" и выберут другой
        projected_time = now + total_wait
        _key_states[best_key]["last_used"] = projected_time
        _last_global_call = projected_time

        alive_count = len(alive_keys)
        total_count = len(_key_states)

    # ── Фаза 2: ждём ВНЕ lock (другие потоки могут параллельно выбирать свои ключи) ──
    if total_wait > 0:
        logger.debug(f"[config] Ключ ...{best_key[-6:]} | ждём {total_wait:.1f}с")
        time.sleep(total_wait)

    if alive_count < total_count:
        logger.info(f"[config] Используем ключ ...{best_key[-6:]} ({alive_count}/{total_count} живых)")

    return best_key


def rotate_key(failed_key: str = "") -> str:
    """
    Штрафует ключ, получивший 429 ошибку (cooldown 60 сек).
    Возвращает следующий живой ключ.
    """
    _init_pool()
    with _pool_lock:
        if not _key_states:
            return ""

        # Штрафуем конкретный ключ если указан
        if failed_key and failed_key in _key_states:
            _key_states[failed_key]["last_used"] = time.time() + 60.0
            _key_states[failed_key]["errors"] += 1
            logger.warning(
                f"[config] Ключ ...{failed_key[-6:]} получил 429 — "
                f"штраф 60с (ошибок: {_key_states[failed_key]['errors']})"
            )
        else:
            # Fallback: штрафуем последний использованный (для совместимости)
            last_used_key = max(_key_states, key=lambda k: _key_states[k]["last_used"])
            _key_states[last_used_key]["last_used"] = time.time() + 60.0
            _key_states[last_used_key]["errors"] += 1

    # Возвращаем следующий лучший ключ
    return get_best_key_and_wait()


def mark_key_dead(dead_key: str):
    """Помечает ключ как мёртвый (исчерпана суточная квота)."""
    _init_pool()
    with _pool_lock:
        if dead_key in _key_states:
            _key_states[dead_key]["dead"] = True
            alive = sum(1 for v in _key_states.values() if not v["dead"])
            logger.error(
                f"[config] Ключ ...{dead_key[-6:]} МЁРТВ (квота исчерпана). "
                f"Осталось живых: {alive}/{len(_key_states)}"
            )


def rate_limit_sleep():
    """Оставлено для обратной совместимости, но теперь спит внутри get_best_key_and_wait."""
    pass


def get_current_key() -> str:
    return get_best_key_and_wait()


def get_keys_count() -> int:
    return len(_read_keys())


def get_pool_status() -> dict:
    """Возвращает статус пула ключей для диагностики."""
    _init_pool()
    with _pool_lock:
        total = len(_key_states)
        alive = sum(1 for v in _key_states.values() if not v["dead"])
        total_errors = sum(v["errors"] for v in _key_states.values())
        return {
            "total_keys": total,
            "alive_keys": alive,
            "dead_keys": total - alive,
            "total_errors": total_errors,
        }


def apply():
    pass
