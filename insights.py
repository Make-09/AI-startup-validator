"""
insights.py — Генерация рекомендаций на основе результатов анализа.
10 правил строго по спецификации.
"""

from typing import List

from benchmarks import get_benchmark
from models import (
    AggregatedInterviewResults, BusinessInput,
    Insight, MonteCarloResults, UnitEconomicsReport,
)


def generate_insights(
    business_input: BusinessInput,
    interview_results: AggregatedInterviewResults,
    unit_economics: UnitEconomicsReport,
    monte_carlo: MonteCarloResults,
) -> List[Insight]:
    """
    Проходит по 10 правилам и генерирует список рекомендаций.
    Порядок строго фиксирован.
    """
    insights: List[Insight] = []
    bench = get_benchmark(business_input.business_type)

    ratio = unit_economics.ltv_cac_ratio
    runway = unit_economics.runway_months
    break_even = unit_economics.break_even_month
    bankruptcy_prob = monte_carlo.bankruptcy_probability
    num_months = monte_carlo.num_months
    pct_would_buy = interview_results.pct_would_buy
    pct_price_too_high = interview_results.pct_price_too_high
    avg_problem_severity = interview_results.avg_problem_severity
    avg_solution_fit = interview_results.avg_solution_fit

    # ── Правило 1: LTV/CAC < 1.0 ─────────────────────────────
    if ratio < 1.0:
        insights.append(Insight(
            severity="critical",
            title="Юнит-экономика отрицательная",
            message=f"LTV/CAC = {ratio:.1f}. Каждый новый клиент приносит убыток.",
            recommendation="Увеличьте цену или снизьте CAC. Целевой LTV/CAC: 3.0+",
            benchmark_ref=(
                f"{business_input.business_type.value} benchmark LTV/CAC: "
                f"{bench.typical_ltv_cac_ratio.median}"
            ),
        ))

    # ── Правило 2: 1.0 ≤ LTV/CAC < 3.0 ──────────────────────
    elif ratio < 3.0:
        insights.append(Insight(
            severity="warning",
            title="Юнит-экономика слабая",
            message=f"LTV/CAC = {ratio:.1f}. Стандарт для инвестиций: 3.0+",
            recommendation="Снизьте churn или повысьте цену",
            benchmark_ref=(
                f"{business_input.business_type.value} benchmark LTV/CAC: "
                f"{bench.typical_ltv_cac_ratio.median}"
            ),
        ))

    # ── Правило 3: LTV/CAC ≥ 3.0 ─────────────────────────────
    else:
        insights.append(Insight(
            severity="success",
            title="Юнит-экономика здоровая",
            message=f"LTV/CAC = {ratio:.1f}. Это превышает отраслевой стандарт.",
            recommendation="Продолжайте масштабировать маркетинг",
            benchmark_ref=(
                f"{business_input.business_type.value} benchmark LTV/CAC: "
                f"{bench.typical_ltv_cac_ratio.median}"
            ),
        ))

    # ── Правило 4: Runway < 6 мес ─────────────────────────────
    if runway < 6:
        insights.append(Insight(
            severity="critical",
            title="Критически низкий runway",
            message=f"Денег хватит на {runway} мес. Цикл привлечения инвестиций: 3–6 мес.",
            recommendation=(
                "Немедленно сократите burn rate или начните поиск инвестиций — "
                "времени крайне мало."
            ),
        ))

    # ── Правило 5: Вероятность банкротства > 70% ─────────────
    if bankruptcy_prob > 0.7:
        insights.append(Insight(
            severity="critical",
            title="Высокая вероятность банкротства",
            message=(
                f"В {bankruptcy_prob:.0%} сценариев стартап обанкротится "
                f"за {num_months} мес."
            ),
            recommendation=(
                "Пересмотрите модель монетизации, снизьте операционные расходы "
                "или привлеките финансирование."
            ),
        ))

    # ── Правило 6: Низкий интерес к продукту ─────────────────
    if pct_would_buy < 0.3:
        insights.append(Insight(
            severity="critical",
            title="AI-интервью: низкий интерес к продукту",
            message=f"Только {pct_would_buy:.0%} респондентов готовы купить.",
            recommendation="Пересмотрите value proposition или целевую аудиторию",
        ))

    # ── Правило 7: Цена воспринимается как высокая ────────────
    if pct_price_too_high > 0.5:
        insights.append(Insight(
            severity="warning",
            title="Цена воспринимается как высокая",
            message=f"{pct_price_too_high:.0%} респондентов считают цену завышенной",
            recommendation="Снизьте цену или добавьте ограниченный бесплатный тариф",
        ))

    # ── Правило 7.5: Подозрительно позитивные ответы ──────────
    all_avg = (avg_problem_severity + avg_solution_fit +
               interview_results.avg_willingness_to_pay +
               interview_results.avg_switching_likelihood +
               interview_results.avg_nps_score) / 5
    if all_avg > 7.0 and pct_would_buy > 0.8:
        insights.append(Insight(
            severity="warning",
            title="⚠️ Подозрительно позитивные ответы",
            message=(
                f"Средняя оценка {all_avg:.1f}/10, {pct_would_buy:.0%} готовы купить. "
                "В реальных опросах такого не бывает — возможна предвзятость симуляции."
            ),
            recommendation=(
                "Рекомендуем провести реальные интервью для проверки. "
                "AI-симуляция может завышать оценки."
            ),
        ))

    # ── Правило 8: Проблема недостаточно острая ───────────────
    if avg_problem_severity < 5.0:
        insights.append(Insight(
            severity="warning",
            title="Проблема недостаточно острая",
            message=(
                f"Средняя оценка: {avg_problem_severity:.1f}/10. "
                "Для product-market fit нужно 7+"
            ),
            recommendation=(
                "Найдите более острую боль или нишу, где проблема ощущается сильнее"
            ),
        ))

    # ── Правило 9: Продукт плохо решает проблему ─────────────
    if avg_solution_fit < 5.0:
        insights.append(Insight(
            severity="warning",
            title="Продукт плохо решает проблему",
            message=f"Solution fit: {avg_solution_fit:.1f}/10.",
            recommendation="Пересмотрите функционал продукта",
        ))

    # ── Правило 10: Не доживёте до безубыточности ────────────
    # break_even = None → стартап ВООБЩЕ не выходит на окупаемость за 36 мес
    if break_even is None or break_even > runway:
        msg = (
            f"Break-even: {'не достигнут за 36 мес' if break_even is None else f'месяц {break_even}'}. "
            f"Runway: {runway} мес."
        )
        insights.append(Insight(
            severity="critical",
            title="Не доживёте до безубыточности",
            message=msg,
            recommendation=(
                "Либо сократите расходы, либо найдите дополнительное финансирование"
            ),
        ))

    return insights
