"""
monte_carlo.py — Monte Carlo симуляция финансовых сценариев (1000 прогонов).
Использует треугольное распределение (PERT) для рандомизации параметров.
"""

import logging
from typing import List, Optional

import numpy as np

from benchmarks import get_adjusted_cac, get_benchmark, get_country_modifier
from models import (
    AggregatedInterviewResults, BusinessInput,
    MonteCarloResults, MonteCarloRun, BusinessType, RevenueModel
)

logger = logging.getLogger(__name__)


def _triangular(rng: np.random.Generator, low: float, mode: float, high: float) -> float:
    """
    Треугольное распределение через numpy.random.Generator.triangular().
    """
    if low == mode == high:
        return low
    if low >= high:
        return mode
    return float(rng.triangular(low, mode, high))


# ═══════════════════════════════════════════════════════════════
#  7.1 Один прогон симуляции
# ═══════════════════════════════════════════════════════════════

def _run_single_simulation(
    business_input: BusinessInput,
    interview_results: AggregatedInterviewResults,
    num_months: int,
    rng: np.random.Generator,
    benchmark=None,  # необязательный IndustryBenchmark (реальный или статичный fallback)
) -> MonteCarloRun:
    """
    Один прогон Monte Carlo на num_months месяцев.
    Параметры рандомизируются один раз в начале прогона.
    """
    bench = benchmark if benchmark is not None else get_benchmark(business_input.business_type)
    adj_cac = get_adjusted_cac(business_input.business_type, business_input.country)
    country_mod = get_country_modifier(business_input.country)

    # ── Рандомизация параметров через треугольное распределение ──
    conversion = _triangular(
        rng,
        bench.conversion_trial_to_paid.low,
        bench.conversion_trial_to_paid.median,
        bench.conversion_trial_to_paid.high,
    )
    churn = _triangular(
        rng,
        bench.monthly_churn.low,
        bench.monthly_churn.median,
        bench.monthly_churn.high,
    )
    cac = _triangular(rng, adj_cac.low, adj_cac.median, adj_cac.high)

    # ── AI-коррекция на основе результатов интервью ───────────
    if interview_results.avg_solution_fit < 5:
        churn *= 1.3
    if interview_results.pct_would_buy > 0.5:
        conversion *= 1.2
    if interview_results.avg_willingness_to_pay < 4:
        conversion *= 0.7

    # ── Страновая коррекция конверсии оплат ───────────────────
    # payment_conversion_modifier учитывает инфраструктуру платежей в стране
    # (e-commerce проникновение, доступность платёжных систем)
    conversion *= country_mod.payment_conversion_modifier

    # ── TAM пользователя используется as-is ─────────────────
    # Пользователь вводит локальный TAM для своей страны:
    # домножение на market_size_multiplier было бы двойным счётом.
    effective_tam = float(business_input.market_size_estimate)

    # ── Особые случаи: E-Commerce и Gig Economy ────────────
    is_ecommerce = business_input.business_type == BusinessType.ECOMMERCE
    is_gig = business_input.business_type == BusinessType.GIG_ECONOMY
    repeat_rate_monthly = 0.025  # 30% годовой / 12 ≈ 2.5% повторных покупок/мес
    # Gig: churn отражает отток активных исполнителей — берём из бенчмарков (не обнуляем)
    if is_ecommerce:
        churn = 0.0  # e-commerce: нет подписочного churn

    # effective_price учитывает модель монетизации (подписка / pay-per-use / комиссия)
    price = business_input.get_effective_price()
    monthly_marketing_budget = business_input.monthly_marketing_budget
    monthly_operating_costs = business_input.monthly_operating_costs
    balance = float(business_input.initial_capital)

    # ── Массивы для записи истории ────────────────────────────
    months_list: List[int] = []
    mrr_list: List[float] = []
    users_list: List[float] = []
    balance_list: List[float] = []
    revenue_cumulative_list: List[float] = []
    costs_cumulative_list: List[float] = []

    users: float = 0.0
    revenue_cum: float = 0.0
    costs_cum: float = 0.0
    is_bankrupt = False
    bankruptcy_month: Optional[int] = None
    fractional_users: float = 0.0  # накопитель дробных пользователей

    cac_safe = max(cac, 1.0)

    for m in range(1, num_months + 1):
        # Маркетинговый охват → новые пользователи
        marketing_reach = monthly_marketing_budget / cac_safe
        raw_new_users = marketing_reach * conversion

        # Симуляция рыночного шума (Market Noise лог-нормальное распределение)
        # Отражает реальные колебания спроса: редкие большие отклонения, умеренная волатильность
        noise = rng.lognormal(mean=0.0, sigma=0.15)
        noise = max(0.5, min(2.0, noise))  # ограничить экстремальные значения
        raw_new_users = max(0.0, raw_new_users * noise)

        # Накопление дробных пользователей — избегает потери при int() округлении
        # (например, 0.3 + 0.3 + 0.3 = 0.9 → на 3-й месяц даёт 1 пользователя)
        fractional_users += raw_new_users
        new_users = int(fractional_users)
        fractional_users -= new_users  # оставляем остаток для следующего месяца

        # Финансы
        if is_ecommerce:
            # E-Commerce: доход = новые покупатели + повторные из кумулятивной базы
            # users здесь = кумулятивная база уникальных клиентов
            repeat_revenue = users * repeat_rate_monthly * price
            revenue = new_users * price + repeat_revenue
            users = min(effective_tam, users + new_users)  # кумулятивный рост
        else:
            churned = int(users * churn)
            users = min(effective_tam, max(0.0, users + new_users - churned))
            revenue = users * price

        costs = monthly_operating_costs + monthly_marketing_budget
        balance = balance + revenue - costs

        revenue_cum += revenue
        costs_cum += costs

        months_list.append(m)
        mrr_list.append(round(revenue, 2))
        users_list.append(round(users, 1))
        balance_list.append(round(balance, 2))
        revenue_cumulative_list.append(round(revenue_cum, 2))
        costs_cumulative_list.append(round(costs_cum, 2))

        # Банкротство
        if balance <= 0:
            is_bankrupt = True
            bankruptcy_month = m
            # Заполнить оставшиеся месяцы нулями
            for remaining_m in range(m + 1, num_months + 1):
                months_list.append(remaining_m)
                mrr_list.append(0.0)
                users_list.append(0.0)
                balance_list.append(0.0)
                revenue_cumulative_list.append(round(revenue_cum, 2))
                costs_cumulative_list.append(round(costs_cum, 2))  # компания мертва — расходы не растут
            break

    return MonteCarloRun(
        months=months_list,
        mrr=mrr_list,
        total_users=users_list,
        balance=balance_list,
        revenue_cumulative=revenue_cumulative_list,
        costs_cumulative=costs_cumulative_list,
        is_bankrupt=is_bankrupt,
        bankruptcy_month=bankruptcy_month,
        final_mrr=mrr_list[-1] if mrr_list else 0.0,
        final_balance=balance_list[-1] if balance_list else 0.0,
        final_users=int(users_list[-1]) if users_list else 0,
    )


# ═══════════════════════════════════════════════════════════════
#  7.2 Агрегация 1000 прогонов
# ═══════════════════════════════════════════════════════════════

def run_monte_carlo(
    business_input: BusinessInput,
    interview_results: AggregatedInterviewResults,
    num_simulations: int = 1000,
    num_months: int = 12,
    seed: Optional[int] = None,
    benchmark=None,  # необязательный IndustryBenchmark для реальных бенчмарков
) -> MonteCarloResults:
    """
    Запускает num_simulations прогонов Monte Carlo и агрегирует результаты.
    Возвращает MonteCarloResults с перцентильными кривыми и итоговыми вероятностями.
    """
    rng = np.random.default_rng(seed)

    runs: List[MonteCarloRun] = []
    for _ in range(num_simulations):
        run = _run_single_simulation(business_input, interview_results, num_months, rng, benchmark)
        runs.append(run)

    logger.info(f"Monte Carlo: {num_simulations} runs completed.")

    # ── Перцентильные кривые по месяцам ──────────────────────
    mrr_p10, mrr_p50, mrr_p90 = [], [], []
    users_p10, users_p50, users_p90 = [], [], []
    balance_p10, balance_p50, balance_p90 = [], [], []

    for month_idx in range(num_months):
        mrr_vals = [r.mrr[month_idx] for r in runs if month_idx < len(r.mrr)]
        users_vals = [r.total_users[month_idx] for r in runs if month_idx < len(r.total_users)]
        bal_vals = [r.balance[month_idx] for r in runs if month_idx < len(r.balance)]

        mrr_p10.append(float(np.percentile(mrr_vals, 10)))
        mrr_p50.append(float(np.percentile(mrr_vals, 50)))
        mrr_p90.append(float(np.percentile(mrr_vals, 90)))

        users_p10.append(float(np.percentile(users_vals, 10)))
        users_p50.append(float(np.percentile(users_vals, 50)))
        users_p90.append(float(np.percentile(users_vals, 90)))

        balance_p10.append(float(np.percentile(bal_vals, 10)))
        balance_p50.append(float(np.percentile(bal_vals, 50)))
        balance_p90.append(float(np.percentile(bal_vals, 90)))

    # ── Итоговые вероятности ──────────────────────────────────
    bankruptcy_probability = sum(1 for r in runs if r.is_bankrupt) / num_simulations
    prob_reach_10k_mrr = sum(1 for r in runs if r.final_mrr >= 10000) / num_simulations
    prob_reach_1k_users = sum(1 for r in runs if r.final_users >= 1000) / num_simulations

    # ── Медианный break-even месяц ────────────────────────────
    break_even_months: List[int] = []
    for run in runs:
        for idx, (rev_cum, cost_cum) in enumerate(
            zip(run.revenue_cumulative, run.costs_cumulative)
        ):
            if rev_cum >= cost_cum:
                break_even_months.append(idx + 1)  # 1-indexed
                break

    # Только если >50% прогонов достигли break-even
    if len(break_even_months) > num_simulations * 0.5:
        median_break_even: Optional[int] = int(np.median(break_even_months))
    else:
        median_break_even = None

    return MonteCarloResults(
        num_simulations=num_simulations,
        num_months=num_months,
        mrr_p10=mrr_p10,
        mrr_p50=mrr_p50,
        mrr_p90=mrr_p90,
        users_p10=users_p10,
        users_p50=users_p50,
        users_p90=users_p90,
        balance_p10=balance_p10,
        balance_p50=balance_p50,
        balance_p90=balance_p90,
        bankruptcy_probability=round(bankruptcy_probability, 4),
        prob_reach_10k_mrr=round(prob_reach_10k_mrr, 4),
        prob_reach_1k_users=round(prob_reach_1k_users, 4),
        median_break_even_month=median_break_even,
    )