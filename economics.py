"""
economics.py — Модуль расчёта юнит-экономики стартапа.
Связывает качественные данные CustDev (интервью) с отраслевыми бенчмарками
и финансовыми параметрами основателя.
"""

import re
from typing import Optional
import logging

from models import (
    BusinessInput,
    BusinessType,
    RevenueModel,
    IndustryBenchmark,
    AggregatedInterviewResults,
    UnitEconomicsReport,
    BenchmarkRange,
)
from benchmarks import get_benchmark

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════
#  Классификатор типа спроса продукта
#  Определяет форму когортной кривой оттока клиентов.
#
#  one_shot   — задача решается один раз (резюме, дизайн, ремонт, свадьба)
#               → Churn Cliff: 45% в месяц 1, 30% в месяц 2
#  recurring  — постоянная боль (CRM, бухгалтерия, почта, analytics)
#               → Churn снижается со временем (клиенты привыкают)
#  periodic   — задача возникает периодически (курсы, налоги, фитнес)
#               → Волнообразный отток с сезонными пиками
# ═══════════════════════════════════════════════════════════════

_ONE_SHOT_KEYWORDS = [
    "резюме", "resume", "портфолио", "portfolio",
    "дизайн логотип", "логотип", "дизайн лого", "визитк",
    "ремонт", "переезд", "relocation", "свадьб", "wedding",
    "меропри", "мероприят",
    "налог декларац", "tax return",
]
_PERIODIC_KEYWORDS = [
    "курс", "course", "обучени", "учёба", "тренинг",
    "фитнес", "fitness", "спорт", "тренажёр",
    "бухгалтерия сезон", "деклараци",
    "подписка раз в год", "annual",
]
_RECURRING_KEYWORDS = [
    "crm", "erp", "аналитик", "analytics", "мониторинг",
    "бухгалтери", "accounting", "invoic",
    "email", "рассылк", "newsletter",
    "управлени", "management", "проектами",
    "автоматизаци", "automation", "workflow",
    "хранилищ", "storage", "backup",
    "поддержк", "support", "helpdesk",
    "smm", "постинг", "планировщик", "соцсет", "social media", "публикац",
]


# ═══════════════════════════════════════════════════════════════
#  Когортные профили оттока — локальная копия из monte_carlo.py
#  (дублирование намеренно: избегаем циклических импортов)
# ═══════════════════════════════════════════════════════════════

_CHURN_PROFILES_FOR_LTV: dict[str, list[float]] = {
    "one_shot":  [0.45, 0.30, 0.15, 0.10, 0.08, 0.07, 0.065, 0.06],
    "recurring": [0.15, 0.10, 0.08, 0.07, 0.065, 0.06, 0.055, 0.05],
    "periodic":  [0.25, 0.20, 0.12, 0.08, 0.15,  0.20, 0.10,  0.07],
}


def calculate_cohort_ltv(
    arpa: float,
    gross_margin: float,
    product_type: str,
    max_months: int = 60,
) -> float:
    """
    Когортный LTV через накопленную выживаемость (корректно для one_shot/periodic).

    Алгоритм: для каждого месяца жизни когорты умножаем долю выживших
    на ARPA × Gross Margin и суммируем. Останавливаемся когда выживаемость
    падает ниже 0.5% (клиентов статистически нет).

    Для 'recurring' можно использовать классическую формулу ARPA×GM/churn,
    но когортный метод тоже корректен и единообразен.
    """
    profile = _CHURN_PROFILES_FOR_LTV.get(product_type, _CHURN_PROFILES_FOR_LTV["recurring"])
    survival = 1.0
    total = 0.0
    for m in range(1, max_months + 1):
        idx = min(m - 1, len(profile) - 1)
        survival *= (1.0 - profile[idx])
        total += survival * arpa * gross_margin
        if survival < 0.005:
            break
    return round(total, 2)


def detect_product_type(business_input: BusinessInput) -> str:
    """
    Определяет тип потребности продукта по ключевым словам в описании.
    Используется для выбора когортного профиля оттока в Монте-Карло.

    Fallback: пытается вызвать LLM если ключевых слов недостаточно.
    Гарантированный fallback: "recurring" (консервативный, наиболее частый случай).

    Returns:
        "one_shot" | "recurring" | "periodic"
    """
    # PAY_PER_USE всегда one_shot по определению (оплата за каждый запрос)
    if business_input.revenue_model == RevenueModel.PAY_PER_USE:
        logger.info("[detect_product_type] revenue_model=PAY_PER_USE → 'one_shot'")
        return "one_shot"

    text = (
        (business_input.description or "") + " " +
        (business_input.name or "") + " " +
        (business_input.target_audience or "")
    ).lower()

    score = {"one_shot": 0, "recurring": 0, "periodic": 0}
    for kw in _ONE_SHOT_KEYWORDS:
        if kw in text:
            score["one_shot"] += 1
    # Проверка коротких аббревиатур по границам слов
    for kw in ["cv", "logo", "event"]:
        if re.search(r'\b' + kw + r'\b', text):
            score["one_shot"] += 1

    for kw in _PERIODIC_KEYWORDS:
        if kw in text:
            score["periodic"] += 1
    for kw in ["gym", "tax"]:
        if re.search(r'\b' + kw + r'\b', text):
            score["periodic"] += 1

    for kw in _RECURRING_KEYWORDS:
        if kw in text:
            score["recurring"] += 1
    for kw in ["crm", "erp"]:
        if re.search(r'\b' + kw + r'\b', text):
            score["recurring"] += 1

    best = max(score, key=lambda k: score[k])
    if score[best] > 0:
        logger.info(f"[detect_product_type] scores={score} → '{best}'")
        # Если продукт монетизируется подпиской, но потребность разовая — предупреждение
        if best == "one_shot" and business_input.revenue_model == RevenueModel.SUBSCRIPTION:
            logger.info(
                "[detect_product_type] ⚠️ Subscription для разовой задачи → "
                "ожидайте Churn Cliff: 40–45% клиентов уйдут в месяц 1"
            )
        return best

    # Вторая попытка: LLM-классификатор (1 дешёвый вызов)
    try:
        import os
        import config as _cfg
        from openai import OpenAI

        api_key = _cfg.get_best_key_and_wait()
        base_url = os.environ.get("OPENAI_BASE_URL", _cfg.BASE_URL)
        model = os.environ.get("OPENAI_MODEL", _cfg.MODEL)

        if api_key and api_key not in ("your_api_key_here", ""):
            client = OpenAI(api_key=api_key, base_url=base_url) if base_url else OpenAI(api_key=api_key)
            resp = client.chat.completions.create(
                model=model,
                messages=[{
                    "role": "user",
                    "content": (
                        "Classify the product demand type. Reply with EXACTLY one word:\n"
                        "  one_shot   — task solved once (resume, logo, renovation, wedding)\n"
                        "  recurring  — constant need (CRM, accounting, email, analytics)\n"
                        "  periodic   — periodic need (courses, fitness, annual tax)\n\n"
                        f"Product: {business_input.description[:200]}"
                    ),
                }],
                max_tokens=10,
                temperature=0.0,
            )
            answer = resp.choices[0].message.content.strip().lower()
            if answer in ("one_shot", "recurring", "periodic"):
                logger.info(f"[detect_product_type] LLM → '{answer}'")
                return answer
    except Exception as e:
        logger.debug(f"[detect_product_type] LLM fallback не доступен: {e}")

    # Гарантированный fallback
    logger.info("[detect_product_type] fallback → 'recurring'")
    return "recurring"


def calculate_cohort_payback(
    cac: float,
    arpa: float,
    gross_margin: float,
    product_type: str,
    max_months: int = 60,
) -> Optional[float]:
    """
    Когортный CAC Payback — за сколько месяцев накопленная валовая прибыль
    с одного привлечённого клиента покрывает CAC, с учётом оттока.

    Почему это важно: формула CAC / (ARPA × GM) игнорирует тот факт, что
    в month_1 при one_shot churn 45% фактически «живых» платящих клиентов
    из когорты уже 55% — и они генерируют только 55% ожидаемой выручки.
    Когортный метод даёт честный результат, который может быть в 3–5× длиннее.

    Returns:
        Месяц окупаемости (float) или None если не достигается за max_months.
    """
    profile = _CHURN_PROFILES_FOR_LTV.get(product_type, _CHURN_PROFILES_FOR_LTV["recurring"])
    survival = 1.0
    cumulative_gp = 0.0
    for m in range(1, max_months + 1):
        idx = min(m - 1, len(profile) - 1)
        survival *= (1.0 - profile[idx])
        cumulative_gp += survival * arpa * gross_margin
        if cumulative_gp >= cac:
            # Линейная интерполяция для дробной части месяца
            prev_gp = cumulative_gp - survival * arpa * gross_margin
            frac = (cac - prev_gp) / max(survival * arpa * gross_margin, 0.001)
            return round(m - 1 + frac, 1)
        if survival < 0.005:
            break
    return None  # Не окупается за max_months (LTV < CAC)


def calculate_unit_economics(
    business_input: BusinessInput,
    benchmark: Optional[IndustryBenchmark] = None,
    interview_results: Optional[AggregatedInterviewResults] = None,
    product_type: str = "recurring",
) -> UnitEconomicsReport:
    """
    Рассчитывает юнит-экономику проекта:
    - CAC (калиброванный с учетом страны и бенчмарка)
    - LTV: когортный (one_shot/periodic) или классический SaaS (recurring)
    - LTV / CAC отношение
    - Срок окупаемости CAC (Payback period)
    - Ежемесячный Burn Rate и Runway (запас прочности в месяцах)
    - Прогнозируемый месяц выхода в безубыточность (Break-even)
    """
    if benchmark is None:
        benchmark = get_benchmark(business_input.business_type)

    # 1. ARPA — средний доход с активного пользователя в месяц (USD)
    arpa = business_input.get_effective_price()

    # 2. Валовая маржинальность (Gross Margin) из бенчмарка
    gross_margin = benchmark.gross_margin.median

    # 3. Базовый CAC
    # ВАЖНО: benchmark.cac.median уже содержит страновую калибровку (GDP-ratio),
    # применённую в fetch_calibrated_benchmarks(). Второй раз country_mod.cac_multiplier
    # НЕ применяем — это привело бы к двойной калибровке и нереалистично низкому CAC.
    # Используем benchmark.cac.median как есть (например: SaaS B2C KZ ≈ $17).
    cac = max(round(benchmark.cac.median, 2), 1.0)

    # 4. Отток (Churn Rate) с калибровкой на данные CustDev
    base_churn = benchmark.monthly_churn.median

    # Если у бизнеса нет подписки (например e-commerce), churn в моделях может быть 0
    if base_churn <= 0:
        base_churn = 0.08  # Дефолтный эквивалент для неподписных моделей (~12 мес цикл)

    adjusted_churn = base_churn

    if interview_results and interview_results.total_personas > 0:
        # Если >50% считают цену завышенной -> отток возрастает
        if interview_results.pct_price_too_high > 0.5:
            adjusted_churn *= 1.25
        elif interview_results.pct_price_too_low > 0.3:
            adjusted_churn *= 0.90

        # Если слабый Solution Fit (<5) -> отток высокий
        if interview_results.avg_solution_fit < 5.0:
            adjusted_churn *= 1.30
        elif interview_results.avg_solution_fit >= 7.5 and interview_results.pct_would_buy >= 0.5:
            # Высокий fit и готовность покупать -> удержание лучше
            adjusted_churn *= 0.85

    # Ограничиваем churn разумным коридором (от 1.5% до 40% в месяц)
    adjusted_churn = max(0.015, min(0.40, adjusted_churn))

    # 5. LTV — метод зависит от типа спроса продукта
    monthly_gross_profit_per_user = arpa * gross_margin
    if product_type in ("one_shot", "periodic"):
        # Когортный LTV через кривую выживаемости:
        # честно учитывает Churn Cliff (45% в мес.1 для one_shot).
        # Результат значительно ниже классической SaaS-формулы — это правильно.
        ltv = calculate_cohort_ltv(arpa, gross_margin, product_type)
        logger.info(
            f"[unit_economics] product_type='{product_type}' → когортный LTV=${ltv:.2f} "
            f"(классическая формула дала бы ${monthly_gross_profit_per_user / adjusted_churn:.2f})"
        )
    else:
        # Классическая SaaS-формула: ARPA × Gross Margin / Churn
        # Корректна только при стабильном churn (recurring продукты)
        ltv = monthly_gross_profit_per_user / adjusted_churn

    # 6. Отношение LTV к CAC
    ltv_cac_ratio = ltv / cac

    # 7. CAC Payback Period (в месяцах)
    # Для one_shot/periodic: когортный метод (учитывает Churn Cliff).
    # Для recurring: классическая формула CAC / (ARPA × GM), т.к. churn стабилен.
    # Разница принципиальная: при one_shot churn=45% в мес.1 реальный payback
    # в 3–5× длиннее, чем наивная формула (пример: 3.6 мес → ~14 мес).
    if product_type in ("one_shot", "periodic"):
        cohort_payback = calculate_cohort_payback(cac, arpa, gross_margin, product_type)
        if cohort_payback is not None:
            cac_payback_months = cohort_payback
            logger.info(
                f"[unit_economics] когортный payback={cac_payback_months:.1f} мес "
                f"(наивная формула дала бы {cac / max(monthly_gross_profit_per_user, 0.01):.1f} мес)"
            )
        else:
            # LTV < CAC → ставим «бесконечность» (клиент никогда не окупается)
            cac_payback_months = 999.0
            logger.warning("[unit_economics] LTV < CAC: CAC Payback не достигается за 60 мес")
    else:
        cac_payback_months = cac / max(monthly_gross_profit_per_user, 0.01)

    # 8. Финансовые параметры основателя
    monthly_burn_rate = (
        business_input.monthly_operating_costs + business_input.monthly_marketing_budget
    )
    if monthly_burn_rate > 0:
        runway_months = int(business_input.initial_capital / monthly_burn_rate)
    else:
        runway_months = 999  # Условная бесконечность, если нет расходов

    # 9. Помесячный когортный Cash Flow и точка безубыточности (Break-even)
    # Моделируем 36 месяцев с учётом когортного профиля оттока и поступающей выручки:
    break_even_month = None
    init_cash = float(business_input.initial_capital)
    min_cash_balance = init_cash
    dynamic_runway_months = None
    current_cash = init_cash

    profile = _CHURN_PROFILES_FOR_LTV.get(product_type, _CHURN_PROFILES_FOR_LTV["recurring"])
    cohorts: list[float] = []

    if business_input.monthly_marketing_budget > 0 and cac > 0:
        new_users_per_month = business_input.monthly_marketing_budget / cac
    else:
        new_users_per_month = 0.0

    for m in range(1, 37):
        active_users = 0.0
        # Старение существующих когорт по когортному профилю
        for k in range(len(cohorts)):
            age = m - k  # 1-based age
            idx = min(age - 1, len(profile) - 1)
            cohorts[k] *= (1.0 - profile[idx])
            active_users += cohorts[k]

        # Новая когорта текущего месяца
        if new_users_per_month > 0:
            cohorts.append(new_users_per_month)
            active_users += new_users_per_month

        monthly_mrr = active_users * arpa
        monthly_gross_total = monthly_mrr * gross_margin
        monthly_net_cash_flow = monthly_gross_total - monthly_burn_rate

        current_cash += monthly_net_cash_flow
        if current_cash < min_cash_balance:
            min_cash_balance = current_cash

        # Фиксация исчерпания средств с учётом выручки
        if current_cash <= 0 and dynamic_runway_months is None:
            dynamic_runway_months = m

        # Точка безубыточности: валовая прибыль покрывает операционные расходы и маркетинг
        if monthly_gross_total >= monthly_burn_rate and break_even_month is None:
            break_even_month = m

    peak_cash_drag = round(max(0.0, init_cash - min_cash_balance), 2)
    peak_capital_deficit = round(max(0.0, -min_cash_balance), 2)
    min_cash_balance = round(min_cash_balance, 2)

    return UnitEconomicsReport(
        ltv=round(ltv, 2),
        cac=round(cac, 2),
        ltv_cac_ratio=round(ltv_cac_ratio, 2),
        cac_payback_months=round(cac_payback_months, 1),
        adjusted_churn=round(adjusted_churn, 4),
        gross_margin=round(gross_margin, 2),
        monthly_burn_rate=round(monthly_burn_rate, 2),
        runway_months=runway_months,
        break_even_month=break_even_month,
        benchmark_ltv_cac=benchmark.typical_ltv_cac_ratio,
        benchmark_churn=benchmark.monthly_churn,
        benchmark_conversion=benchmark.conversion_trial_to_paid,
        initial_capital=init_cash,
        min_cash_balance=min_cash_balance,
        peak_cash_drag=peak_cash_drag,
        peak_capital_deficit=peak_capital_deficit,
        dynamic_runway_months=dynamic_runway_months,
    )


def calculate_overall_viability_score(
    interview_results: AggregatedInterviewResults,
    unit_economics: UnitEconomicsReport,
    monte_carlo_results: Optional["MonteCarloResults"] = None,
) -> tuple[int, dict]:
    """
    Рассчитывает сбалансированный Overall Viability Score (0-100) по 3 блокам:
    1. Problem Validation (0-40)
    2. Solution Fit & Acceptance (0-35)
    3. Financial & Cash Flow Viability (0-25) — без задваивания штрафов!
    Возвращает (overall_score, subscores_dict).
    """
    # ── БЛОК 1: Валидация проблемы (0-40) ──
    # Острота боли: до 15 баллов
    s_problem = (min(10.0, max(0.0, interview_results.avg_problem_severity)) / 10.0) * 15.0
    # % готовых купить: до 15 баллов (при 50%+ конверсии даёт максимум)
    s_buy = (min(0.50, max(0.0, interview_results.pct_would_buy)) / 0.50) * 15.0
    # Готовность платить (WTP): до 10 баллов
    s_wtp = (min(10.0, max(0.0, interview_results.avg_willingness_to_pay)) / 10.0) * 10.0
    score_problem = s_problem + s_buy + s_wtp

    # ── БЛОК 2: Solution Fit & Acceptance (0-35) ──
    # Solution Fit: до 18 баллов
    s_fit = (min(10.0, max(0.0, interview_results.avg_solution_fit)) / 10.0) * 18.0
    # NPS / Рекомендация: до 10 баллов
    s_nps = (min(10.0, max(0.0, interview_results.avg_nps_score)) / 10.0) * 10.0
    # Ценовое согласие: до 7 баллов
    s_price = interview_results.pct_price_ok * 7.0
    score_solution = s_fit + s_nps + s_price

    # ── БЛОК 3: Финансовая жизнеспособность и Cash Flow (0-25) ──
    # Оценивается строго по трём ортогональным финансовым фундаментальным метрикам:

    # 3.1 Качество юнит-экономики (0–10 баллов):
    # Отношение LTV к CAC — показывает маржинальность привлечения 1 клиента.
    if unit_economics.ltv_cac_ratio >= 3.0:
        s_unit_econ = 10.0
    elif unit_economics.ltv_cac_ratio >= 2.0:
        s_unit_econ = 7.5
    elif unit_economics.ltv_cac_ratio >= 1.5:
        s_unit_econ = 5.0
    elif unit_economics.ltv_cac_ratio >= 1.0:
        s_unit_econ = 2.5
    else:
        s_unit_econ = 0.0

    # 3.2 Достаточность капитала и глубина кассовой ямы (0–8 баллов):
    # Анализирует дно остатка денежных средств (min_cash_balance) в когортной модели:
    init_cap = max(unit_economics.initial_capital, 1.0)
    if unit_economics.peak_capital_deficit <= 0.0:
        # Стартового капитала хватает для достижения безубыточности!
        # Оцениваем размер оставшейся подушки безопасности в точке максимальной просадки:
        cushion_ratio = unit_economics.min_cash_balance / init_cap
        if cushion_ratio >= 0.50:
            s_cash_flow = 8.0  # Подушка > 50% стартового капитала — очень надёжно
        elif cushion_ratio >= 0.20:
            s_cash_flow = 6.0  # Подушка 20–50% — нормальный рабочий буфер
        else:
            s_cash_flow = 4.0  # Подушка < 20% — рискованно близко к кассовому разрыву
    else:
        # Стартовый капитал исчерпывается до выхода в плюс:
        deficit_ratio = unit_economics.peak_capital_deficit / init_cap
        if deficit_ratio <= 0.50:
            s_cash_flow = 2.0  # Умеренный дефицит (требуется небольшой bridge-раунд)
        else:
            s_cash_flow = 0.0  # Глубокий кассовый разрыв

    # 3.3 Стохастическая устойчивость по Монте-Карло (0–7 баллов):
    # Учитывает 2000 симуляций со всеми факторами неопределенности:
    if monte_carlo_results:
        s_mc = max(0.0, (1.0 - monte_carlo_results.bankruptcy_probability / 100.0) * 7.0)
    else:
        s_mc = 4.0
    score_finance = s_unit_econ + s_cash_flow + s_mc

    raw_total = score_problem + score_solution + score_finance

    # ── Штрафы за критические несоответствия ──
    # Применяются ТОЛЬКО к фундаментальным качественным порокам идеи,
    # не дублируя риски, уже учтённые в финансовой модели (убраны задваивающие штрафы):
    penalties = 0.0

    # 1. Нет рыночной боли — витамин, а не обезболивающее
    if interview_results.avg_problem_severity < 4.0:
        penalties += 12.0

    # 2. Большинство считает цену завышенной (>50%)
    if interview_results.pct_price_too_high > 0.50:
        penalties += 6.0

    # 3. Экономика убыточна в принципе (LTV < CAC)
    if unit_economics.ltv_cac_ratio < 1.0:
        penalties += 15.0

    # 4. Нулевой стартовый капитал при наличии ежемесячных расходов
    if unit_economics.initial_capital <= 0.0 and unit_economics.monthly_burn_rate > 0:
        penalties += 10.0

    # 5. Новый неизвестный стартап: если никто не слышал о продукте,
    #    реальный CAC в 2–3x выше бенчмарка, а конверсия намного ниже.
    #    Штраф применяется только при ОДНОВРЕМЕННО плохой экономике И слабой боли:
    #    LTV:CAC < 2.0 (нет запаса прочности) И problem_severity < 6 (боль слабая).
    if unit_economics.ltv_cac_ratio < 2.0 and interview_results.avg_problem_severity < 6.0:
        penalties += 8.0

    # 6. Если интервью дали мало данных (мало валидных), снижаем уверенность
    total_valid = getattr(interview_results, "total_valid_responses", None)
    if total_valid is not None and total_valid == 0:
        # Нет ни одного валидного интервью — данных нет, максимальная неопределённость
        penalties += 20.0
    elif total_valid is not None and total_valid == 1:
        # Только 1 из 3 — ненадёжная выборка
        penalties += 8.0

    final_score = int(round(max(0.0, min(100.0, raw_total - penalties))))
    subscores = {
        "problem_validation": round(score_problem, 1),
        "solution_fit": round(score_solution, 1),
        "financial_viability": round(score_finance, 1),
        "penalties": round(penalties, 1),
        "_debug_s_unit_econ": round(s_unit_econ, 1),
        "_debug_s_cash_flow": round(s_cash_flow, 1),
        "_debug_s_mc": round(s_mc, 1),
    }
    return final_score, subscores

