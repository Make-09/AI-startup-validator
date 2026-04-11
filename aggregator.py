"""
aggregator.py — Количественная агрегация результатов AI-интервью.
Чистая математика, без LLM.
"""

from collections import Counter
from typing import List

from models import AggregatedInterviewResults, InterviewResponse


def aggregate_interviews(responses: List[InterviewResponse]) -> AggregatedInterviewResults:
    """
    Агрегирует список ответов интервью в сводные метрики.

    Если список пуст — возвращает объект с нулями.
    Ответы с is_error=True исключаются из числовых средних,
    чтобы нулевые оценки ошибочных интервью не занижали результаты.
    """
    total = len(responses)

    if total == 0:
        return AggregatedInterviewResults(
            total_personas=0,
            avg_problem_severity=0.0,
            avg_solution_fit=0.0,
            avg_willingness_to_pay=0.0,
            avg_switching_likelihood=0.0,
            avg_nps_score=0.0,
            pct_would_buy=0.0,
            pct_price_too_high=0.0,
            pct_price_ok=0.0,
            pct_price_too_low=0.0,
            top_concerns=[],
            top_desired_features=[],
            responses=[],
            fallback_count=0,
        )

    # ── Отделяем валидные ответы от ошибок ────────────────────
    valid = [r for r in responses if not r.is_error]
    valid_count = len(valid) if valid else 1  # защита от деления на 0

    # ── Средние числовые оценки (только валидные!) ────────────
    avg_problem_severity = sum(r.problem_severity for r in valid) / valid_count
    avg_solution_fit = sum(r.solution_fit for r in valid) / valid_count
    avg_willingness_to_pay = sum(r.willingness_to_pay for r in valid) / valid_count
    avg_switching_likelihood = sum(r.switching_likelihood for r in valid) / valid_count
    avg_nps_score = sum(r.recommend_likelihood for r in valid) / valid_count

    # ── Доля would_buy (только валидные) ─────────────────────
    pct_would_buy = sum(1 for r in valid if r.would_buy) / valid_count

    # ── Ценовое восприятие (только валидные) ──────────────────
    pct_price_too_high = sum(1 for r in valid if r.price_feedback == "дорого") / valid_count
    pct_price_ok = sum(1 for r in valid if r.price_feedback == "нормально") / valid_count
    pct_price_too_low = sum(1 for r in valid if r.price_feedback == "дёшево") / valid_count

    # ── Топ-3 опасения по частоте (только валидные) ───────────
    concerns_counter = Counter(r.main_concern for r in valid if r.main_concern)
    top_concerns = [item for item, _ in concerns_counter.most_common(3)]

    # ── Топ-3 желаемые фичи по частоте (только валидные) ─────
    features_counter = Counter(r.desired_feature for r in valid if r.desired_feature)
    top_desired_features = [item for item, _ in features_counter.most_common(3)]

    # ── Подсчет ошибок (is_error=True) ────────────────────────
    fallback_count = sum(1 for r in responses if r.is_error)

    return AggregatedInterviewResults(
        total_personas=total,
        avg_problem_severity=round(avg_problem_severity, 2),
        avg_solution_fit=round(avg_solution_fit, 2),
        avg_willingness_to_pay=round(avg_willingness_to_pay, 2),
        avg_switching_likelihood=round(avg_switching_likelihood, 2),
        avg_nps_score=round(avg_nps_score, 2),
        pct_would_buy=round(pct_would_buy, 3),
        pct_price_too_high=round(pct_price_too_high, 3),
        pct_price_ok=round(pct_price_ok, 3),
        pct_price_too_low=round(pct_price_too_low, 3),
        top_concerns=top_concerns,
        top_desired_features=top_desired_features,
        responses=responses,
        fallback_count=fallback_count,
    )
