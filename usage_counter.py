"""
usage_counter.py — Счётчик дневных запусков симуляции.
Максимум MAX_DAILY_RUNS запусков в сутки (сбрасывается в полночь UTC+5).

Работает на Streamlit Cloud:
  - Основное хранилище: st.cache_resource (shared singleton в RAM, живёт пока жив процесс)
  - Резервное: файл /tmp/startup_sim_counter.json (пережиавет soft-restart)
  - Файл рядом со скриптом .usage_counter.json (для локальной разработки)

Гарантии потокобезопасности:
  - threading.Lock() защищает все read/write операции
  - Все Streamlit-сессии внутри одного воркера видят один счётчик
"""

import json
import os
import datetime
import threading
from typing import Optional

MAX_DAILY_RUNS = 20

# Таймзона Казахстана (UTC+5) — лимит сбрасывается в полночь по Алматы
_UTC_OFFSET_HOURS = 5

_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
_PRIMARY_FILE = os.path.join(_SCRIPT_DIR, ".usage_counter.json")
_FALLBACK_FILE = "/tmp/startup_sim_counter.json"


# ════════════════════════════════════════════════════════════════
#  In-memory singleton (shared между всеми Streamlit-сессиями)
# ════════════════════════════════════════════════════════════════

class _CounterStore:
    """Thread-safe синглтон-счётчик в RAM."""
    def __init__(self):
        self._lock = threading.Lock()
        self._date: str = ""
        self._count: int = 0
        # При старте — пробуем загрузить из файла (если воркер перезапустился)
        self._load_from_disk()

    def _today(self) -> str:
        """Текущая дата по UTC+5 (Казахстан)."""
        utc_now = datetime.datetime.utcnow()
        local_now = utc_now + datetime.timedelta(hours=_UTC_OFFSET_HOURS)
        return str(local_now.date())

    def _load_from_disk(self):
        """Восстанавливает счётчик из файла при запуске."""
        for path in (_PRIMARY_FILE, _FALLBACK_FILE):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    if isinstance(data, dict) and data.get("date") == self._today():
                        self._date = data["date"]
                        self._count = data.get("count", 0)
                        return
            except Exception:
                continue
        # Файлы не найдены или дата другая — начинаем с нуля
        self._date = self._today()
        self._count = 0

    def _save_to_disk(self):
        """Атомарный сброс на диск (best-effort, не блокирует при ошибке)."""
        data = {"date": self._date, "count": self._count}
        for path in (_PRIMARY_FILE, _FALLBACK_FILE):
            tmp = path + ".tmp"
            try:
                with open(tmp, "w", encoding="utf-8") as f:
                    json.dump(data, f)
                os.replace(tmp, path)
                return  # Успех — одного файла достаточно
            except Exception:
                try:
                    os.unlink(tmp)
                except Exception:
                    pass
                continue

    def _ensure_today(self):
        """Проверяет что дата актуальна. Если наступил новый день — сбрасывает."""
        today = self._today()
        if self._date != today:
            self._date = today
            self._count = 0
            self._save_to_disk()

    def get_remaining(self) -> int:
        with self._lock:
            self._ensure_today()
            return max(0, MAX_DAILY_RUNS - self._count)

    def get_count(self) -> int:
        with self._lock:
            self._ensure_today()
            return self._count

    def consume(self) -> bool:
        """Пытается занять слот. Возвращает True если разрешено."""
        with self._lock:
            self._ensure_today()
            if self._count >= MAX_DAILY_RUNS:
                return False
            self._count += 1
            self._save_to_disk()
            return True

    def is_limit(self) -> bool:
        return self.get_remaining() == 0

    def next_reset_info(self) -> str:
        """Возвращает строку с временем до следующего сброса."""
        utc_now = datetime.datetime.utcnow()
        local_now = utc_now + datetime.timedelta(hours=_UTC_OFFSET_HOURS)
        tomorrow = (local_now + datetime.timedelta(days=1)).replace(
            hour=0, minute=0, second=0, microsecond=0
        )
        delta = tomorrow - local_now
        hours = int(delta.total_seconds() // 3600)
        minutes = int((delta.total_seconds() % 3600) // 60)
        return f"{hours}ч {minutes}мин"


# ════════════════════════════════════════════════════════════════
#  Singleton через st.cache_resource (или fallback)
# ════════════════════════════════════════════════════════════════

_fallback_store: Optional[_CounterStore] = None

def _get_store() -> _CounterStore:
    """Получает глобальный синглтон счётчика."""
    global _fallback_store
    try:
        import streamlit as st

        @st.cache_resource
        def _create_counter():
            return _CounterStore()

        return _create_counter()
    except Exception:
        # Вне Streamlit (тесты, CLI)
        if _fallback_store is None:
            _fallback_store = _CounterStore()
        return _fallback_store


# ════════════════════════════════════════════════════════════════
#  Публичный API (обратная совместимость)
# ════════════════════════════════════════════════════════════════

def get_remaining_runs() -> int:
    """Возвращает количество оставшихся запусков на сегодня."""
    return _get_store().get_remaining()


def current_count() -> int:
    """Возвращает количество запусков, совершённых сегодня."""
    return _get_store().get_count()


def consume_run() -> bool:
    """
    Пытается занять один слот.
    Возвращает True если запуск разрешён, False если лимит исчерпан.
    """
    return _get_store().consume()


def is_limit_reached() -> bool:
    """True если сегодняшний лимит исчерпан."""
    return _get_store().is_limit()


def next_reset_info() -> str:
    """Сколько времени до сброса лимита (для UI)."""
    return _get_store().next_reset_info()
