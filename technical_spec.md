# ТЕХНИЧЕСКАЯ СПЕЦИФИКАЦИЯ — AI Customer Discovery Validator

> **Для кого этот документ:** для модели, которая будет писать код. Здесь описана вся логика — каждый файл, каждая функция, каждая формула. Код НЕ включён — только поведение.

---

## 1. ОБЩАЯ АРХИТЕКТУРА

**Стек:** Python 3.11+, Streamlit, Pydantic v2, numpy, plotly, google-generativeai

**Зависимости (requirements.txt):**
- streamlit>=1.28.0
- google-generativeai>=0.8.0
- pandas>=2.0.0
- pydantic>=2.0.0
- numpy>=1.24.0
- plotly>=5.15.0
- duckduckgo-search>=4.0.0

**Структура файлов (9 файлов):**

```
startup_simulator/
├── models.py              — все Pydantic-модели данных
├── benchmarks.py          — база отраслевых бенчмарков + страновые модификаторы
├── personas.py            — генерация синтетических клиентских персон (без LLM)
├── interview_engine.py    — проведение AI-интервью через LLM
├── aggregator.py          — количественная агрегация результатов интервью
├── monte_carlo.py         — Monte Carlo симуляция (1000 прогонов)
├── unit_economics.py      — расчёт юнит-экономики
├── insights.py            — генерация рекомендаций
├── main.py                — Streamlit UI (4 вкладки)
└── requirements.txt
```

**Порядок разработки:** Строго последовательно. Каждый следующий файл зависит от предыдущих.

```
models.py → benchmarks.py → personas.py → interview_engine.py → aggregator.py → monte_carlo.py → unit_economics.py → insights.py → main.py
```

**Файлы, которые нужно УДАЛИТЬ из старого проекта:**
- agents.py
- simulator.py
- Modelfile

---

## 2. ФАЙЛ: models.py — Модели данных

Этот файл содержит ТОЛЬКО Pydantic-модели. Никакой логики. Все остальные файлы импортируют модели отсюда.

### 2.1 BusinessType (Enum)

Перечисление из 8 типов бизнеса:
- saas_b2b, saas_b2c, marketplace, ecommerce, mobile_app, edtech, fintech, agency

Наследуется от `str, Enum` — чтобы корректно сериализовалось.

### 2.2 BusinessInput

Ввод пользователя. Все поля с дефолтными значениями:

| Поле | Тип | Default | Описание |
|------|-----|---------|----------|
| name | str | "" | Название продукта |
| description | str | "" | Описание идеи |
| business_type | BusinessType | SAAS_B2C | Тип бизнеса |
| target_audience | str | "" | Целевая аудитория |
| price | float | 10.0 | Цена $/мес |
| initial_capital | float | 10000.0 | Стартовый капитал $ |
| monthly_marketing_budget | float | 500.0 | Маркетинг $/мес |
| monthly_operating_costs | float | 300.0 | Операционные расходы $/мес |
| market_size_estimate | int | 100000 | TAM (кол-во потенциальных клиентов) |
| country | str | "kazakhstan" | Страна |

### 2.3 BenchmarkRange

Диапазон из трёх значений:
- low (float) — пессимистичный, P10
- median (float) — типичный, P50
- high (float) — оптимистичный, P90

### 2.4 IndustryBenchmark

Бенчмарк для одного типа бизнеса:

| Поле | Тип | Описание |
|------|-----|----------|
| business_type | BusinessType | Тип |
| display_name | str | "SaaS B2C" и т.д. |
| conversion_trial_to_paid | BenchmarkRange | % конверсия free→paid |
| monthly_churn | BenchmarkRange | % месячный churn |
| cac | BenchmarkRange | $ стоимость привлечения клиента |
| gross_margin | BenchmarkRange | % валовая маржа |
| avg_months_to_first_revenue | int | Месяцев до первого дохода |
| failure_rate_12_months | float | Доля провалов за 12 мес (0.0–1.0) |
| typical_ltv_cac_ratio | BenchmarkRange | Типичный LTV/CAC |
| source | str | Источник данных |

### 2.5 CountryModifier

Страновые коэффициенты:
- country (str)
- price_sensitivity_multiplier (float) — насколько ниже покупательная способность vs USA
- cac_multiplier (float) — во сколько раз дешевле маркетинг
- market_size_multiplier (float) — относительный размер рынка
- payment_conversion_modifier (float) — насколько хуже конвертятся оплаты

### 2.6 Persona

Синтетический клиент:

| Поле | Тип | Описание |
|------|-----|----------|
| id | str | UUID[:8], автогенерируемый |
| name | str | "Айгерим" (не "Айгерим, 28 лет" — возраст отдельно) |
| age | int | 18–55 |
| occupation | str | Профессия |
| monthly_income | float | Доход $/мес |
| tech_savviness | str | "low" / "medium" / "high" |
| pain_points | List[str] | 2–3 боли |
| current_solution | str | Чем сейчас пользуется |
| personality_trait | str | "early_adopter" / "pragmatist" / "skeptic" / "conservative" |
| segment | str | "primary" / "secondary" / "edge_case" |

### 2.7 InterviewQuestion

- category (str): "problem" / "solution" / "pricing" / "competition" / "behavior"
- question (str): текст вопроса

### 2.8 InterviewResponse

Ответ одной персоны на интервью:

| Поле | Тип | Описание |
|------|-----|----------|
| persona_id | str | ID персоны |
| persona_name | str | Имя |
| problem_severity | int | 1–10 |
| solution_fit | int | 1–10 |
| willingness_to_pay | int | 1–10 |
| switching_likelihood | int | 1–10 |
| recommend_likelihood | int | 1–10 |
| main_concern | str | Главное опасение |
| desired_feature | str | Чего не хватает |
| price_feedback | str | "дорого" / "нормально" / "дёшево" |
| would_buy | bool | Купил бы? |
| raw_opinion | str | Развёрнутое мнение |

### 2.9 AggregatedInterviewResults

Агрегация всех интервью:

| Поле | Тип | Описание |
|------|-----|----------|
| total_personas | int | Сколько персон |
| avg_problem_severity | float | Среднее 1–10 |
| avg_solution_fit | float | Среднее 1–10 |
| avg_willingness_to_pay | float | Среднее 1–10 |
| avg_switching_likelihood | float | Среднее 1–10 |
| avg_nps_score | float | Среднее recommend_likelihood |
| pct_would_buy | float | Доля would_buy=True (0.0–1.0) |
| pct_price_too_high | float | Доля "дорого" |
| pct_price_ok | float | Доля "нормально" |
| pct_price_too_low | float | Доля "дёшево" |
| top_concerns | List[str] | Топ-3 опасения по частоте |
| top_desired_features | List[str] | Топ-3 фичи по частоте |
| responses | List[InterviewResponse] | Все сырые ответы |

### 2.10 MonteCarloRun

Один прогон симуляции:
- months (List[int]) — номера месяцев [1, 2, ..., 12]
- mrr (List[float]) — MRR на каждый месяц
- total_users (List[float]) — пользователей на каждый месяц
- balance (List[float]) — баланс на каждый месяц
- revenue_cumulative (List[float])
- costs_cumulative (List[float])
- is_bankrupt (bool)
- bankruptcy_month (Optional[int])
- final_mrr (float)
- final_balance (float)
- final_users (int)

### 2.11 MonteCarloResults

Агрегация 1000 прогонов:
- num_simulations, num_months
- mrr_p10, mrr_p50, mrr_p90 (List[float]) — percentile curves
- users_p10, users_p50, users_p90 (List[float])
- balance_p10, balance_p50, balance_p90 (List[float])
- bankruptcy_probability (float) — доля обанкротившихся
- prob_reach_10k_mrr (float)
- prob_reach_1k_users (float)
- median_break_even_month (Optional[int])

### 2.12 UnitEconomicsReport

- ltv, cac, ltv_cac_ratio (float)
- cac_payback_months (float)
- gross_margin (float, 0–1)
- monthly_burn_rate (float)
- runway_months (int)
- break_even_month (Optional[int])
- benchmark_ltv_cac, benchmark_churn, benchmark_conversion (BenchmarkRange) — для сравнения

### 2.13 Insight

Одна рекомендация:
- severity: "critical" / "warning" / "success" / "info"
- title: короткий заголовок
- message: подробное описание
- recommendation: что делать
- benchmark_ref: ссылка на бенчмарк

### 2.14 ValidationReport

Финальный объект, хранящийся в session_state:
- business_input (BusinessInput)
- interview_results (Optional[AggregatedInterviewResults])
- monte_carlo_results (Optional[MonteCarloResults])
- unit_economics (Optional[UnitEconomicsReport])
- insights (List[Insight])
- overall_score (float, 0–100)

---

## 3. ФАЙЛ: benchmarks.py — Отраслевые данные

### 3.1 Константа BENCHMARKS

Словарь `BusinessType → IndustryBenchmark`. Содержит данные для всех 8 типов бизнеса.

Конкретные значения:

**SaaS B2B:**
- conversion: low=3%, median=7%, high=15%
- churn: low=2%, median=5%, high=8%
- CAC: $200 / $400 / $800
- gross margin: 65% / 75% / 85%
- failure rate 12 мес: 60%
- Источник: OpenView 2024, Bessemer Cloud Index

**SaaS B2C:**
- conversion: 2% / 4% / 8%
- churn: 4% / 6.7% / 12%
- CAC: $20 / $50 / $120
- gross margin: 55% / 68% / 80%
- failure rate: 68%
- Источник: Baremetrics, ProfitWell

**Marketplace:**
- conversion: 1% / 2.5% / 5%
- churn: 3% / 6% / 10%
- CAC: $30 / $70 / $150
- gross margin: 12% / 20% / 30%
- failure rate: 72%

**E-Commerce:**
- conversion: 1.5% / 3% / 6%
- churn: 0% / 0% / 0% (не подписка — разовые покупки)
- CAC: $10 / $35 / $80
- gross margin: 25% / 40% / 55%
- failure rate: 65%

**Mobile App (Freemium):**
- conversion: 1% / 2.5% / 5%
- churn: 6% / 10% / 20%
- CAC: $2 / $5 / $15
- gross margin: 55% / 70% / 85%
- failure rate: 75%

**EdTech:**
- conversion: 3% / 6% / 12%
- churn: 5% / 8% / 14%
- CAC: $30 / $80 / $200
- gross margin: 60% / 75% / 90%
- failure rate: 62%

**FinTech:**
- conversion: 2% / 4% / 8%
- churn: 2% / 5% / 9%
- CAC: $50 / $120 / $300
- gross margin: 45% / 60% / 75%
- failure rate: 70%

**Agency/Services:**
- conversion: 8% / 15% / 25%
- churn: 4% / 7% / 12%
- CAC: $100 / $250 / $600
- gross margin: 35% / 50% / 65%
- failure rate: 55%

### 3.2 Константа COUNTRY_MODIFIERS

Словарь `str → CountryModifier`. Четыре страны.

Все значения рассчитаны на основе реальных данных (см. раздел 13 — Источники).

| Страна | price_sensitivity | cac_multiplier | market_size | payment_conversion |
|--------|------------------|----------------|-------------|-------------------|
| usa | 1.0 | 1.0 | 1.0 | 1.0 |
| kazakhstan | 0.17 | 0.08 | 0.055 | 0.72 |
| russia | 0.18 | 0.15 | 0.35 | 0.70 |
| global | 1.0 | 1.0 | 1.0 | 1.0 |

**Методология расчёта:**

**price_sensitivity_multiplier** — отношение ВВП на душу населения страны к США:
- Казахстан: $14 155 / $84 534 = 0.167 ≈ **0.17** (World Bank 2024, FRED)
- Россия: $14 889 / $84 534 = 0.176 ≈ **0.18** (World Bank 2024, Trading Economics)
- Экономический смысл: подписка за $10/мес — это ~0.2% зарплаты для американца ($5 000/мес) и ~1.4% для казахстанца ($700/мес). Относительная нагрузка в 7 раз выше.

**cac_multiplier** — отношение стоимости digital-рекламы к США:
- Казахстан: CPM в КЗ ≈ $0.5–1.0 vs CPM в США ≈ $10–15 (Meta Ads 2024) → 1.0 / 12.5 = **0.08** (WordStream Facebook Ads Benchmarks)
- Россия: CPM в РФ ≈ $1.5–3.0 (с учётом ухода западных платформ) → ~2.25 / 12.5 ≈ **0.15**

**market_size_multiplier** — отношение числа интернет-пользователей к США:
- Казахстан: 18.19 млн / 331 млн = **0.055** (DataReportal Digital 2024 Kazakhstan). Интернет-проникновение КЗ = 92.3% — ограничение не доступность, а размер населения (19.7 млн).
- Россия: 116 млн / 331 млн = **0.35** (DataReportal Digital 2024 Russia)

**payment_conversion_modifier** — конвертируемость онлайн-платежей:
- Казахстан: e-commerce penetration 28% (Statista 2024) vs США 78%; скорректировано до **0.72** с учётом Kaspi Pay (12+ млн активных пользователей, Kaspi Bank Annual Report 2023).
- Россия: **0.70** — уход Visa/Mastercard в 2022 снизил конверсию международных платежей; локальные платежи через Mir работают.

### 3.3 Функции

**get_benchmark(business_type) → IndustryBenchmark**
Просто возвращает BENCHMARKS[business_type].

**get_country_modifier(country) → CountryModifier**
Возвращает COUNTRY_MODIFIERS[country.lower()]. Если нет — возвращает "global".

**get_adjusted_cac(business_type, country) → BenchmarkRange**
Берёт CAC из бенчмарка, умножает каждый компонент (low, median, high) на cac_multiplier страны. Возвращает новый BenchmarkRange.

---

## 4. ФАЙЛ: personas.py — Генерация персон

### 4.1 Константы

**KAZAKH_NAMES** — список из 20 казахских имён:
Мужские: Нурлан, Дамир, Арман, Тимур, Ерлан, Бауыржан, Данияр, Асет, Мирас, Алихан
Женские: Айгерим, Мадина, Жанна, Камила, Динара, Аяулым, Назерке, Томирис, Дана, Айнур

**GENERIC_NAMES** — для других стран: Алексей, Мария, Иван, Елена, Дмитрий, Ольга и т.д. (20 имён)

**PAIN_POINTS** — словарь `BusinessType → List[str]`. По 6 болей на каждый тип бизнеса.

Для каждого из 8 типов бизнеса — 6 специфичных болей. Примеры уже есть в implementation_plan.md для SaaS B2B и SaaS B2C. Нужно дописать для остальных 6 типов. Боли должны быть конкретными и реалистичными, не абстрактными.

**OCCUPATIONS** — словарь `BusinessType → List[Tuple[str, int]]`. По 6 профессий на тип бизнеса. Каждый элемент — (название профессии, базовый доход в $).

Доходы уже в масштабе Казахстана (300–2500$). При генерации для других стран — НЕ умножать на модификатор.

**CURRENT_SOLUTIONS** — словарь `BusinessType → List[str]`. По 4–6 текущих решений, которые люди используют. Например, для SaaS B2C: "бесплатные приложения", "Excel", "делаю вручную", "пользуюсь конкурентом X".

**TECH_LEVELS** — словарь `str → List[str]` для маппинга personality → допустимые tech_savviness. Early adopters: ["medium", "high"]. Conservative: ["low", "medium"]. И т.д.

### 4.2 Функция generate_personas

**generate_personas(business_input: BusinessInput, count: int = 10) → List[Persona]**

Логика:

1. Определить набор имён по стране (KAZAKH_NAMES или GENERIC_NAMES).
2. Перемешать имена (random.shuffle).
3. Определить распределение сегментов: первые 50% персон — "primary", следующие 30% — "secondary", остальные 20% — "edge_case".
4. Определить распределение personality: для каждой персоны выбрать из ["early_adopter", "pragmatist", "skeptic", "conservative"] с весами [0.20, 0.40, 0.25, 0.15] — через random.choices.
5. Для каждой персоны:
   - Взять имя из списка (по кругу если персон больше имён).
   - Возраст: random.gauss(mean=32, std=8), обрезать до 18–55.
   - Профессию и доход: random.choice из OCCUPATIONS[business_type].
   - tech_savviness: random.choice на основе personality_trait.
   - pain_points: random.sample из PAIN_POINTS[business_type], взять 2–3 штуки.
   - current_solution: random.choice из CURRENT_SOLUTIONS[business_type].
   - segment и personality_trait — по рассчитанному распределению.
6. Собрать объект Persona и вернуть список.

**ВАЖНО:** LLM НЕ используется. Всё детерминированно из шаблонов. Это осознанное решение — чтобы контролировать распределение и не тратить вызовы LLM.

---

## 5. ФАЙЛ: interview_engine.py — AI-интервью через LLM

### 5.1 Константы

**LLM** — экземпляр `google.generativeai.GenerativeModel("gemini-2.5-flash")` с JSON-режимом.

**MOM_TEST_QUESTIONS** — список из 5 фиксированных InterviewQuestion:
1. category="problem": "Расскажите, как вы сейчас решаете эту проблему? Что вас больше всего раздражает?"
2. category="solution": "Если бы такой продукт существовал, насколько он бы облегчил вашу жизнь?"
3. category="pricing": "Сколько вы сейчас тратите на решение этой проблемы? Сколько готовы заплатить?"
4. category="competition": "Какие альтернативы вы пробовали? Почему они не устроили?"
5. category="behavior": "Как часто вы сталкиваетесь с этой проблемой? Когда последний раз это было?"

Эти вопросы ЗАХАРДКОЖЕНЫ. Не генерируются LLM.

**INTERVIEW_SYSTEM_PROMPT** — системный промпт:
"Ты — синтетический респондент в маркетинговом исследовании. Отвечай СТРОГО от лица персонажа. Отвечай ТОЛЬКО валидным JSON на русском языке. НЕ добавляй markdown или пояснения."

**INTERVIEW_USER_PROMPT** — шаблон пользовательского промпта. Содержит:
- Блок "ТВОЙ ПРОФИЛЬ" с подстановкой всех полей персоны
- Блок "ПРОДУКТ" с подстановкой полей из BusinessInput
- Блок "ВОПРОСЫ ИНТЕРВЬЮ" с 5 вопросами
- Инструкцию отвечать в характере persona (скептики критикуют, early adopters энтузиастичны)
- Пример JSON-ответа с описанием всех полей и допустимых значений
- Явное указание что числа от 1 до 10

### 5.2 Функция _build_interview_prompt

**_build_interview_prompt(persona: Persona, business_input: BusinessInput) → str**

Подставляет поля персоны и BusinessInput в INTERVIEW_USER_PROMPT. Возвращает готовый промпт.

### 5.3 Функция _parse_interview_response

**_parse_interview_response(content: str, persona: Persona) → InterviewResponse**

1. Убрать markdown-обёртку если есть (```json ... ```).
2. Распарсить JSON через json.loads.
3. Валидировать числовые поля — clamp к диапазону 1–10.
4. Валидировать price_feedback — если не "дорого"/"нормально"/"дёшево" → подставить "нормально".
5. Валидировать would_buy — если не bool → False.
6. Обрезать текстовые поля: main_concern до 500 символов, desired_feature до 300, raw_opinion до 500.
7. Собрать и вернуть InterviewResponse.

### 5.4 Функция _run_single_interview

**_run_single_interview(persona: Persona, business_input: BusinessInput, retries: int = 2) → InterviewResponse**

1. Собрать messages: system + user (через _build_interview_prompt).
2. Цикл до retries+1 попыток:
   - Вызвать llm.invoke(messages)
   - Попробовать _parse_interview_response
   - Если успешно — вернуть результат
   - Если JSONDecodeError — залогировать warning, подождать 0.5 сек, retry
   - Если другая ошибка — залогировать error, подождать 1 сек, retry
3. Если все попытки провалились — вернуть fallback InterviewResponse:
   - Все числа = 5
   - would_buy = False
   - main_concern = "Нет ответа (ошибка LLM)"
   - raw_opinion = "Ошибка обработки интервью"

### 5.5 Функция run_all_interviews

**run_all_interviews(personas: List[Persona], business_input: BusinessInput, max_workers: int = 5) → List[InterviewResponse]**

1. Если список персон пуст — вернуть пустой список.
2. Создать ThreadPoolExecutor(max_workers=min(max_workers, len(personas))).
3. Сабмитить _run_single_interview для каждой персоны.
4. Собрать результаты через as_completed.
5. При ошибке future — добавить fallback InterviewResponse.
6. Вернуть список InterviewResponse.

Паттерн параллельности — ТОЧНАЯ КОПИЯ текущего agents.py, просто с другими функциями.

---

## 6. ФАЙЛ: aggregator.py — Агрегация результатов

### 6.1 Функция aggregate_interviews

**aggregate_interviews(responses: List[InterviewResponse]) → AggregatedInterviewResults**

Логика (чистая математика, без LLM):

1. total = len(responses). Если 0 — вернуть объект с нулями.
2. **Средние оценки** — для каждого числового поля: сумма / total.
   - avg_problem_severity = sum(r.problem_severity for r in responses) / total
   - avg_solution_fit = sum(r.solution_fit) / total
   - avg_willingness_to_pay = sum(r.willingness_to_pay) / total
   - avg_switching_likelihood = sum(r.switching_likelihood) / total
   - avg_nps_score = sum(r.recommend_likelihood) / total
3. **Процент would_buy** — count(r.would_buy == True) / total.
4. **Ценовое восприятие:**
   - pct_price_too_high = count(r.price_feedback == "дорого") / total
   - pct_price_ok = count(r.price_feedback == "нормально") / total
   - pct_price_too_low = count(r.price_feedback == "дёшево") / total
5. **Топ-3 опасения:** Counter([r.main_concern for r in responses]).most_common(3) → взять только строки.
6. **Топ-3 фичи:** Counter([r.desired_feature for r in responses if r.desired_feature]).most_common(3) → взять только строки.
7. Собрать и вернуть AggregatedInterviewResults.

---

## 7. ФАЙЛ: monte_carlo.py — Monte Carlo симуляция

### 7.1 Функция _run_single_simulation

**_run_single_simulation(business_input, interview_results, num_months, rng) → MonteCarloRun**

Один прогон на num_months месяцев. Параметры:
- rng: numpy Random Generator (для воспроизводимости)

Логика:

1. **Получить бенчмарки:**
   - bench = get_benchmark(business_input.business_type)
   - adj_cac = get_adjusted_cac(business_input.business_type, business_input.country)

2. **Рандомизировать параметры один раз В НАЧАЛЕ прогона** (не каждый месяц):
   - conversion = rng.triangular(bench.conversion.low, bench.conversion.median, bench.conversion.high)
   - churn = rng.triangular(bench.churn.low, bench.churn.median, bench.churn.high)
   - cac = rng.triangular(adj_cac.low, adj_cac.median, adj_cac.high)

3. **Применить AI-коррекцию:**
   - Если avg_solution_fit < 5: churn *= 1.3
   - Если pct_would_buy > 0.5: conversion *= 1.2
   - Если avg_willingness_to_pay < 4: conversion *= 0.7

4. **Особый случай E-Commerce** (churn=0 в бенчмарках):
   - Если bench.monthly_churn.median == 0: churn = 0. Модель считает повторные покупки как: repeat_rate = 0.3 (30% клиентов покупают повторно).

5. **Помесячный цикл (m = 1..num_months):**
   - marketing_reach = monthly_marketing_budget / max(cac, 1)
   - new_users = int(marketing_reach * conversion)
   - noise = rng.uniform(0.7, 1.3) — случайный шум ±30%
   - new_users = max(0, int(new_users * noise))
   - churned = int(users * churn)
   - users = max(0, users + new_users - churned)
   - revenue = users * price
   - costs = monthly_operating_costs + monthly_marketing_budget
   - balance = balance + revenue - costs
   - mrr = revenue
   - Записать mrr, users, balance в массивы
   - Если balance <= 0: is_bankrupt = True, bankruptcy_month = m, заполнить оставшиеся месяцы нулями, break

6. **Собрать MonteCarloRun** из массивов.

### 7.2 Функция run_monte_carlo

**run_monte_carlo(business_input, interview_results, num_simulations=1000, num_months=12, seed=None) → MonteCarloResults**

1. Создать numpy Generator (с seed если указан).
2. Запустить _run_single_simulation num_simulations раз. Собрать список MonteCarloRun.
3. **Для каждого месяца** — собрать массивы mrr/users/balance всех прогонов и вычислить:
   - P10 = numpy.percentile(values, 10)
   - P50 = numpy.percentile(values, 50)
   - P90 = numpy.percentile(values, 90)
4. **Итоговые метрики:**
   - bankruptcy_probability = count(is_bankrupt) / num_simulations
   - prob_reach_10k_mrr = count(final_mrr >= 10000) / num_simulations
   - prob_reach_1k_users = count(final_users >= 1000) / num_simulations
   - median_break_even_month: для каждого прогона найти первый месяц где cumulative_revenue >= cumulative_costs. Взять медиану. Если >50% не достигли — None.
5. Собрать и вернуть MonteCarloResults.

---

## 8. ФАЙЛ: unit_economics.py — Юнит-экономика

### 8.1 Функция calculate_unit_economics

**calculate_unit_economics(business_input, ai_conversion_rate, ai_churn_modifier) → UnitEconomicsReport**

Параметры:
- ai_conversion_rate = pct_would_buy из aggregator
- ai_churn_modifier = 1 - (avg_solution_fit / 10) из aggregator

Логика:

1. **benchmark** = get_benchmark(business_input.business_type)
2. **country_mod** = get_country_modifier(business_input.country)
3. **adjusted_churn** = benchmark.monthly_churn.median × (1 + ai_churn_modifier)
   - Clamp: min 0.01, max 0.5
4. **LTV:**
   - Если adjusted_churn > 0: LTV = price / adjusted_churn
   - Если adjusted_churn == 0 (e-commerce): LTV = price × 24
5. **CAC:**
   - adjusted_cac = get_adjusted_cac(business_type, country)
   - CAC = adjusted_cac.median
   - Если ai_conversion_rate > benchmark.conversion.median: CAC *= 0.8 (лучше конвертится → дешевле привлекать)
   - Если ai_conversion_rate < benchmark.conversion.median: CAC *= 1.3 (хуже → дороже)
6. **ltv_cac_ratio** = LTV / CAC (если CAC > 0, иначе 999)
7. **gross_margin** = benchmark.gross_margin.median
8. **cac_payback_months** = CAC / (price × gross_margin). Если знаменатель 0 → 999.
9. **burn_rate** = monthly_operating_costs + monthly_marketing_budget
10. **runway_months** = int(initial_capital / burn_rate) если burn_rate > 0, иначе 999.
11. **break_even_month:** Итеративно считаем месяц 1..36:
    - new_users_per_month = monthly_marketing_budget / max(CAC, 1) × benchmark.conversion.median
    - users[m] = users[m-1] × (1 - adjusted_churn) + new_users_per_month
    - cumulative_revenue += users[m] × price
    - cumulative_costs += burn_rate
    - Если cumulative_revenue >= cumulative_costs → break_even = m, break
    - Если не достигнут за 36 мес → None
12. Собрать UnitEconomicsReport.

---

## 9. ФАЙЛ: insights.py — Генерация рекомендаций

### 9.1 Функция generate_insights

**generate_insights(business_input, interview_results, unit_economics, monte_carlo) → List[Insight]**

Проходит по 10 правилам СТРОГО В ЭТОМ ПОРЯДКЕ. Каждое правило проверяет условие — если истинно, добавляет Insight в список.

**Правило 1.** ltv_cac_ratio < 1.0 →
- severity: "critical"
- title: "Юнит-экономика отрицательная"
- message: "LTV/CAC = {ratio:.1f}. Каждый новый клиент приносит убыток."
- recommendation: "Увеличьте цену или снизьте CAC. Целевой LTV/CAC: 3.0+"
- benchmark_ref: "{business_type} benchmark LTV/CAC: {bench.typical_ltv_cac_ratio.median}"

**Правило 2.** ltv_cac_ratio >= 1.0 и < 3.0 →
- severity: "warning"
- title: "Юнит-экономика слабая"
- message: "LTV/CAC = {ratio:.1f}. Стандарт для инвестиций: 3.0+"
- recommendation: "Снизьте churn или повысьте цену"

**Правило 3.** ltv_cac_ratio >= 3.0 →
- severity: "success"
- title: "Юнит-экономика здоровая"
- message: "LTV/CAC = {ratio:.1f}. Это превышает отраслевой стандарт."

**Правило 4.** runway_months < 6 →
- severity: "critical"
- title: "Критически низкий runway"
- message: "Денег хватит на {runway} мес. Цикл привлечения инвестиций: 3–6 мес."

**Правило 5.** bankruptcy_probability > 0.7 →
- severity: "critical"
- title: "Высокая вероятность банкротства"
- message: "В {pct:.0%} сценариев стартап обанкротится за {num_months} мес."

**Правило 6.** pct_would_buy < 0.3 →
- severity: "critical"
- title: "AI-интервью: низкий интерес к продукту"
- message: "Только {pct:.0%} респондентов готовы купить."
- recommendation: "Пересмотрите value proposition или целевую аудиторию"

**Правило 7.** pct_price_too_high > 0.5 →
- severity: "warning"
- title: "Цена воспринимается как высокая"
- message: "{pct:.0%} респондентов считают цену завышенной"
- recommendation: "Снизьте цену или добавьте ограниченный бесплатный тариф"

**Правило 8.** avg_problem_severity < 5.0 →
- severity: "warning"
- title: "Проблема недостаточно острая"
- message: "Средняя оценка: {score:.1f}/10. Для product-market fit нужно 7+"

**Правило 9.** avg_solution_fit < 5.0 →
- severity: "warning"
- title: "Продукт плохо решает проблему"
- message: "Solution fit: {score:.1f}/10."
- recommendation: "Пересмотрите функционал продукта"

**Правило 10.** break_even_month не None и break_even_month > runway_months →
- severity: "critical"
- title: "Не доживёте до безубыточности"
- message: "Break-even: месяц {be}. Runway: {rw} мес."
- recommendation: "Либо сократите расходы, либо найдите дополнительное финансирование"

---

## 10. ФАЙЛ: main.py — Streamlit UI

### 10.1 Конфигурация

- page_title: "AI Startup Validator — Валидатор бизнес-идей"
- page_icon: "🔬"
- layout: "wide"
- Заголовок: "🔬 AI Startup Validator"
- Подзаголовок: "Валидация бизнес-идей через AI Customer Discovery + Monte Carlo"

### 10.2 Четыре вкладки

**Tab 1: "📝 Ваша идея"**

Содержит форму ввода. Все виджеты:
- text_input для name
- text_area (height=100) для description
- selectbox для business_type — отобразить display_name из бенчмарков
- text_input для target_audience
- number_input для price (min=0.5, step=1.0, default=10.0)
- number_input для initial_capital (min=0, step=1000, default=10000)
- number_input для marketing (min=0, step=100, default=500)
- number_input для operating_costs (min=0, step=100, default=300)
- number_input для market_size (min=1000, step=10000, default=100000)
- selectbox для country: ["kazakhstan", "russia", "usa", "global"]

Кнопка "🔬 Запустить валидацию" (type="primary", use_container_width=True).

При нажатии — последовательно:
1. Собрать BusinessInput из виджетов
2. st.spinner("Генерация персон...") → generate_personas(input, 10)
3. st.spinner("AI Customer Interviews... Это займёт 1–2 минуты") → run_all_interviews(personas, input)
4. aggregate_interviews(responses)
5. st.spinner("Monte Carlo симуляция (1000 сценариев)...") → run_monte_carlo(input, aggregated, 1000, 12)
6. calculate_unit_economics(input, aggregated.pct_would_buy, 1 - aggregated.avg_solution_fit / 10)
7. generate_insights(input, aggregated, ue, mc)
8. Рассчитать overall_score (формула ниже)
9. Сохранить всё в st.session_state.report = ValidationReport(...)
10. st.rerun()

**Формула overall_score:**
- +min(25, ltv_cac_ratio / 3.0 × 25)
- +min(25, pct_would_buy × 25)
- +min(25, (1 - bankruptcy_probability) × 25)
- +min(25, avg_solution_fit / 10 × 25)
- Итого: round(score), диапазон 0–100

---

**Tab 2: "🧑‍🤝‍🧑 AI Customer Discovery"**

Показывать ТОЛЬКО если st.session_state.report существует. Иначе — st.info("Сначала запустите валидацию").

**Секция A: Сводка (4 колонки st.metric)**
- col1: "🎯 Острота проблемы" → avg_problem_severity с форматом "X.X / 10"
- col2: "💳 Готовы купить" → pct_would_buy × 100 с форматом "XX%"
- col3: "⭐ NPS Score" → avg_nps_score с форматом "X.X / 10"
- col4: "📊 Solution Fit" → avg_solution_fit с форматом "X.X / 10"

**Секция B: Ценовое восприятие**
Pie chart (plotly): три сегмента — "Дорого", "Нормально", "Дёшево" с цветами красный/зелёный/синий.

**Секция C: Топ-3 опасения**
Для каждого concern из top_concerns → st.warning(concern)

**Секция D: Топ-3 желаемые фичи**
Для каждой feature из top_desired_features → st.info(feature)

**Секция E: Детальные ответы персон**
st.expander для каждой InterviewResponse:
- Заголовок: "{persona_name} — {вывести occupation из персоны}"
- Внутри: все оценки в виде горизонтальных прогресс-баров (st.progress), мнение (raw_opinion), would_buy (✅ / ❌).

---

**Tab 3: "📊 Monte Carlo Прогноз"**

**Секция A: 4 ключевые вероятности (st.metric в 4 колонках)**
- Вероятность банкротства: XX% (если >50% — delta="Высокий риск!", delta_color="inverse")
- Вероятность $10K MRR: XX%
- Вероятность 1000 пользователей: XX%
- Медианный break-even: месяц X (или "Не достигнут")

**Секция B: 3 графика Plotly**

Каждый график — go.Figure с:
- go.Scatter для P10 (прозрачная линия)
- go.Scatter для P90 (с fill='tonexty' — закрашенная область)
- go.Scatter для P50 (жирная линия, width=3)
- x-axis = месяцы 1..12
- layout: title, xaxis_title="Месяц", yaxis_title по метрике

**График 1: "MRR — 1000 сценариев"**
- Зелёные тона: rgba(0, 200, 100, 0.2) для fill, rgb(0, 180, 80) для P50.

**График 2: "Пользователи"**
- Синие тона: rgba(60, 120, 255, 0.2) для fill, rgb(40, 100, 220) для P50.

**График 3: "Баланс"**
- Оранжевые тона: rgba(255, 150, 0, 0.2) для fill, rgb(230, 130, 0) для P50.
- Дополнительная горизонтальная линия на y=0 красного цвета, dash="dash" — порог банкротства.

---

**Tab 4: "💡 Юнит-экономика и рекомендации"**

**Секция A: 6 метрик в 2 ряда по 3 колонки (st.metric)**

Ряд 1:
- LTV: "${ltv:,.0f}"
- CAC: "${cac:,.0f}"
- LTV/CAC: "{ratio:.1f}x"

Ряд 2:
- CAC Payback: "{months:.0f} мес"
- Runway: "{months} мес"
- Break-even: "Месяц {m}" или "Не достигнут"

**Секция B: Таблица сравнения с бенчмарками**

DataFrame из 4 строк:
| Метрика | Ваше значение | Индустрия (P10) | Индустрия (P50) | Индустрия (P90) |
- LTV/CAC ratio
- Monthly Churn
- Conversion Rate
- Gross Margin

Отображается через st.dataframe.

**Секция C: Рекомендации**

Для каждого Insight из report.insights:
- severity "critical" → st.error(f"**{title}**\n\n{message}\n\n*{recommendation}*")
- severity "warning" → st.warning(...)
- severity "success" → st.success(...)
- severity "info" → st.info(...)

**Секция D: Overall Score**

- st.markdown("### 🏆 Общая оценка жизнеспособности")
- st.progress(overall_score / 100)
- Большой текст: st.markdown(f"## {overall_score}/100")
- Цветовая подсказка:
  - 0–25: "🔴 Критический риск"
  - 26–50: "🟠 Высокий риск"
  - 51–75: "🟡 Умеренный риск"
  - 76–100: "🟢 Перспективный проект"

---

## 11. ЧЕГО НЕ ДЕЛАТЬ

- ❌ Не добавлять базу данных (SQLite, PostgreSQL) — всё в памяти
- ❌ Не делать FastAPI — это Streamlit проект
- ❌ Не добавлять авторизацию
- ❌ Не менять модель LLM (Google Gemini 2.5 Flash)
- ✅ Персоны генерируются динамически через LLM (профессии, боли, решения)
- ❌ Не менять названия моделей и функций
- ❌ Не объединять файлы
- ❌ Не добавлять тесты (отдельная задача)
- ❌ Не добавлять fancy CSS/анимации — фокус на данные
- ❌ Не использовать st.cache_data для LLM-вызовов (они должны быть fresh каждый раз)

---

## 12. ПРОВЕРКА ПОСЛЕ РЕАЛИЗАЦИИ

После написания каждого файла — проверить что импорты работают:

```
python -c "from models import *"
python -c "from benchmarks import *"
python -c "from personas import generate_personas"
python -c "from interview_engine import run_all_interviews"
python -c "from aggregator import aggregate_interviews"
python -c "from monte_carlo import run_monte_carlo"
python -c "from unit_economics import calculate_unit_economics"
python -c "from insights import generate_insights"
```

Финальная проверка — запустить `streamlit run main.py` и пройти полный цикл.

---

## 13. ИСТОЧНИКИ ДЛЯ COUNTRY_MODIFIERS

Данные, на которых основаны значения в разделе 3.2:

1. World Bank / FRED. GDP per capita, Kazakhstan, 2024. —
   URL: https://fred.stlouisfed.org/series/PCAGDPKZA646NWDB

2. World Bank. GDP per capita, United States, 2024. —
   URL: https://data.worldbank.org/country/united-states

3. World Bank / Trading Economics. GDP per capita, Russia, 2024. —
   URL: https://tradingeconomics.com/russia/gdp-per-capita-us-dollar-wb-data.html

4. DataReportal. Digital 2024: Kazakhstan. Kepios Analysis, January 2024. —
   URL: https://datareportal.com/reports/digital-2024-kazakhstan

5. WordStream. Facebook Ads Benchmarks by Industry, 2024. —
   URL: https://www.wordstream.com/blog/ws/2021/08/24/facebook-ad-benchmarks

6. Kaspi.kz. Annual Report 2023, Active Users Data. —
   URL: https://kaspi.kz/investor-relations/

7. Statista. E-commerce penetration rate Kazakhstan, 2024. —
   URL: https://www.statista.com/topics/11604/internet-usage-in-kazakhstan/
