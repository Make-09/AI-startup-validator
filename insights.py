"""
insights.py — Генерация рекомендаций на основе результатов AI-интервью.
Monte Carlo и юнит-экономика исключены.
"""

from typing import List

from models import (
    AggregatedInterviewResults, BusinessInput, Insight,
)


def generate_insights(
    business_input: BusinessInput,
    interview_results: AggregatedInterviewResults,
) -> List[Insight]:
    """
    Генерирует список рекомендаций на основе AI-интервью.
    """
    insights: List[Insight] = []

    pct_would_buy = interview_results.pct_would_buy
    pct_price_too_high = interview_results.pct_price_too_high
    avg_problem_severity = interview_results.avg_problem_severity
    avg_solution_fit = interview_results.avg_solution_fit

    # ── Правило 1: Низкий интерес к продукту ─────────────────
    if pct_would_buy < 0.3:
        insights.append(Insight(
            severity="critical",
            title="Низкий интерес к продукту",
            message=f"Только {pct_would_buy:.0%} респондентов готовы купить.",
            recommendation="Пересмотрите value proposition или целевую аудиторию",
        ))

    # ── Правило 2: Цена воспринимается как высокая ────────────
    if pct_price_too_high > 0.5:
        insights.append(Insight(
            severity="warning",
            title="Цена воспринимается как высокая",
            message=f"{pct_price_too_high:.0%} респондентов считают цену завышенной",
            recommendation="Снизьте цену или добавьте ограниченный бесплатный тариф",
        ))

    # ── Правило 3: Подозрительно позитивные ответы ──────────
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

    # ── Правило 4: Проблема недостаточно острая ───────────────
    if avg_problem_severity < 5.0:
        insights.append(Insight(
            severity="warning",
            title="Проблема недостаточно острая",
            message=(
                f"Средняя оценка: {avg_problem_severity:.1f}/10. "
                "Для product-market fit нужно 7+"
            ),
            recommendation="Найдите более острую боль или нишу, где проблема ощущается сильнее",
        ))

    # ── Правило 5: Продукт плохо решает проблему ─────────────
    if avg_solution_fit < 5.0:
        insights.append(Insight(
            severity="warning",
            title="Продукт плохо решает проблему",
            message=f"Solution fit: {avg_solution_fit:.1f}/10.",
            recommendation="Пересмотрите функционал продукта",
        ))

    # ── Правило 6: Сильный product-market fit ────────────────
    if avg_solution_fit >= 7.0 and pct_would_buy >= 0.5:
        insights.append(Insight(
            severity="success",
            title="Сильный product-market fit",
            message=(
                f"Solution fit: {avg_solution_fit:.1f}/10, "
                f"{pct_would_buy:.0%} готовы купить."
            ),
            recommendation="Фокусируйтесь на росте и удержании пользователей",
        ))

    return insights
