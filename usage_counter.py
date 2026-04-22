"""
usage_counter.py — Глобальный счётчик запусков, общий для ВСЕХ пользователей сервиса.

Принцип работы:
  - st.cache_resource создаёт ОДИН объект на весь Streamlit-процесс.
    Все пользователи (сессии) видят один и тот же счётчик в RAM.
  - Файл /tmp/startup_sim_counter.json — резервное хранилище на случай
    мягкого перезапуска воркера (данные пережигают soft-restart).
  - threading.Lock() гарантирует корректность при одновременных запросах.

Итог: если пользователь A использовал 3 запуска, у пользователя B
останется уже 17, а не снова 20.
"""

import json
import os
import datetime
import threading
from typing import Optional

MAX_DAILY_RUNS = 20
_UTC_OFFSET_HOURS = 5  # UTC+5 (Казахстан) — сброс в полночь по Алматы
_COUNTER_FILE = "/tmp/startup_sim_counter.json"


class _GlobalCounter:
    """
    Единственный экземпляр на весь процесс Streamlit.
    Все пользовательские сессии обращаются к одному объекту.
    """
    def __init__(self):
        self._lock = threading.Lock()
        self._date: str = ""
        self._count: int = 0
        self._load()

    def _today(self) -> str:
        utc_now = datetime.datetime.utcnow()
        local_now = utc_now + datetime.timedelta(hours=_UTC_OFFSET_HOURS)
        return str(local_now.date())

    def _load(self):
        """Восстанавливает счётчик из файла при старте воркера."""
        try:
            with open(_COUNTER_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            if data.get("date") == self._today():
                self._date = data["date"]
                self._count = data.get("count", 0)
                return
        except Exception:
            pass
        self._date = self._today()
        self._count = 0

    def _save(self):
        """Сохраняет текущий счётчик на диск (best-effort)."""
        try:
            tmp = _COUNTER_FILE + ".tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump({"date": self._date, "count": self._count}, f)
            os.replace(tmp, _COUNTER_FILE)
        except Exception:
            pass

    def _check_day(self):
        """Сбрасывает счётчик если наступил новый день."""
        today = self._today()
        if self._date != today:
            self._date = today
            self._count = 0
            self._save()

    def get_remaining(self) -> int:
        with self._lock:
            self._check_day()
            return max(0, MAX_DAILY_RUNS - self._count)

    def get_count(self) -> int:
        with self._lock:
            self._check_day()
            return self._count

    def consume(self) -> bool:
        """Занимает один слот. Возвращает True если разрешено, False если лимит."""
        with self._lock:
            self._check_day()
            if self._count >= MAX_DAILY_RUNS:
                return False
            self._count += 1
            self._save()
            return True

    def next_reset_info(self) -> str:
        utc_now = datetime.datetime.utcnow()
        local_now = utc_now + datetime.timedelta(hours=_UTC_OFFSET_HOURS)
        tomorrow = (local_now + datetime.timedelta(days=1)).replace(
            hour=0, minute=0, second=0, microsecond=0
        )
        delta = tomorrow - local_now
        hours = int(delta.total_seconds() // 3600)
        minutes = int((delta.total_seconds() % 3600) // 60)
        return f"{hours}ч {minutes}мин"


# ── Глобальный синглтон через st.cache_resource ───────────────
# Создаётся ОДИН РАЗ при первом обращении и живёт весь срок жизни процесса.
# Все пользователи получают один и тот же объект _GlobalCounter.

_fallback: Optional[_GlobalCounter] = None

def _get() -> _GlobalCounter:
    global _fallback
    try:
        import streamlit as st

        @st.cache_resource
        def _make():
            return _GlobalCounter()

        return _make()
    except Exception:
        if _fallback is None:
            _fallback = _GlobalCounter()
        return _fallback


# ── Публичный API ─────────────────────────────────────────────

def get_remaining_runs() -> int:
    return _get().get_remaining()

def current_count() -> int:
    return _get().get_count()

def consume_run() -> bool:
    return _get().consume()

def is_limit_reached() -> bool:
    return _get().get_remaining() == 0

def next_reset_info() -> str:
    return _get().next_reset_info()
