"""
usage_counter.py — Счётчик дневных запусков симуляции.
Максимум MAX_DAILY_RUNS запусков в сутки (сбрасывается в полночь).

Работает и локально, и на Streamlit Cloud:
- Основной файл: рядом со скриптом (.usage_counter.json)
- Резервный:     /tmp/startup_sim_counter.json (если нет прав на запись)
"""

import json
import os
import datetime

MAX_DAILY_RUNS = 20

_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
_PRIMARY_FILE = os.path.join(_SCRIPT_DIR, ".usage_counter.json")
_FALLBACK_FILE = "/tmp/startup_sim_counter.json"


def _counter_path() -> str:
    """Возвращает путь к файлу счётчика — основной или резервный."""
    try:
        with open(_PRIMARY_FILE, "a", encoding="utf-8"):
            pass
        return _PRIMARY_FILE
    except OSError:
        return _FALLBACK_FILE


def _load() -> dict:
    for path in (_PRIMARY_FILE, _FALLBACK_FILE):
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, dict):
                    return data
        except Exception:
            continue
    return {}


def _save(data: dict) -> bool:
    """Атомарная запись через временный файл → rename."""
    path = _counter_path()
    tmp = path + ".tmp"
    try:
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f)
        os.replace(tmp, path)
        return True
    except Exception:
        try:
            os.unlink(tmp)
        except Exception:
            pass
        return False


def _today() -> str:
    return str(datetime.date.today())


def get_remaining_runs() -> int:
    """Возвращает количество оставшихся запусков на сегодня."""
    data = _load()
    if data.get("date") != _today():
        return MAX_DAILY_RUNS
    return max(0, MAX_DAILY_RUNS - data.get("count", 0))


def current_count() -> int:
    """Возвращает количество запусков, совершённых сегодня."""
    data = _load()
    if data.get("date") != _today():
        return 0
    return data.get("count", 0)


def consume_run() -> bool:
    """
    Пытается занять один слот.
    Возвращает True если запуск разрешён, False если лимит исчерпан.
    """
    data = _load()
    today = _today()
    if data.get("date") != today:
        data = {"date": today, "count": 0}
    if data["count"] >= MAX_DAILY_RUNS:
        return False
    data["count"] += 1
    _save(data)
    return True


def is_limit_reached() -> bool:
    return get_remaining_runs() == 0
