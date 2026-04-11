# 🔬 AI Customer Discovery Validator

AI-симуляция customer development интервью по методологии Mom Test для предварительной валидации бизнес-идей.

## Возможности

- **3 Модели монетизации** — поддержка Ежемесячной подписки (SaaS), Разовой оплаты (Pay-per-use) и Комиссии со сделок (Marketplace). Все метрики LTV/MRR пересчитываются автоматически.
- **AI Customer Discovery** — динамическая генерация персон и интервью по методологии Mom Test через Google Gemini с защитой от искажений (Randomized Fallback).
- **Живые бенчмарки (2025–2026)** — система ищет актуальные отраслевые и страновые бенчмарки через DuckDuckGo Search и синтезирует их через LLM.
- **Monte Carlo симуляция** — 1000 финансовых сценариев с треугольным распределением (PERT) и AI-коррекцией.
- **Юнит-экономика** — LTV, CAC, LTV/CAC, Runway, Break-even с адаптацией под динамические бенчмарки.
- **Локализация** — поддержка русского и казахского языков, адаптация под страну (Казахстан, Россия, США, Global).

## Технический стек

- **Python 3.11+**, Streamlit, Pydantic v2
- **LLM**: Google Gemini 2.0 Flash (бесплатный API)
- **Визуализация**: Plotly, Pandas
- **Симуляция**: NumPy (Monte Carlo)
- **Поиск конкурентов**: DuckDuckGo Search

## Установка и запуск

```bash
# 1. Установить зависимости
pip install -r requirements.txt

# 2. Получить бесплатный API ключ Google Gemini
# Перейти на https://aistudio.google.com/ → Create API Key

# 3. Запустить приложение
streamlit run main.py

# 4. Ввести API ключ в боковой панели приложения
```

## Структура проекта

```
startup_simulator/
├── models.py              — Pydantic-модели (включая RevenueModel)
├── benchmarks.py          — живые бенчмарки (DuckDuckGo + Gemini) и статические (fallback)
├── personas.py            — динамическая генерация персон через LLM
├── interview_engine.py    — AI-интервью через Google Gemini (Mom Test)
├── aggregator.py          — количественная агрегация результатов
├── monte_carlo.py         — Monte Carlo симуляция (1000 прогонов)
├── unit_economics.py      — расчёт юнит-экономики
├── insights.py            — генерация рекомендаций (10 правил)
├── main.py                — Streamlit UI (4 вкладки)
├── .env.example           — пример файла с API ключом
└── requirements.txt
```

## Использование

1. Заполните описание бизнес-идеи, целевую аудиторию, ценовую политику
2. Введите API ключ Google Gemini в боковой панели
3. Нажмите «Запустить валидацию»
4. Просмотрите результаты AI-интервью, Monte Carlo прогноз и юнит-экономику
5. Получите рекомендации и общую оценку жизнеспособности (0–100)

## Автор

**make-09** — проект для конкурса научных проектов «Дарын»
