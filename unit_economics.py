"""
unit_economics.py — Расчёт юнит-экономики стартапа.
LTV, CAC, LTV/CAC, Payback, Runway, Break-even.
"""

from typing import Optional

from benchmarks import get_adjusted_cac, get_benchmark, get_country_modifier
from models import BusinessInput, UnitEconomicsReport, BusinessType, RevenueModel


def calculate_unit_economics(
    business_input: BusinessInput,
    ai_conversion_rate: float,
    ai_churn_modifier: float,
    benchmark=None,  # необязательный IndustryBenchmark (реальный или статичный fallback)
) -> UnitEconomicsReport:
    """
    Рассчитывает юнит-экономику.

    Параметры:
        ai_conversion_rate  — pct_would_buy из aggregator (0.0–1.0)
        ai_churn_modifier   — 1 - (avg_solution_fit / 5) из main.py (fit=5→0, fit=10→-1, fit=1→+0.8)
    """
    # effective_price учитывает все три модели монетизации
    price = business_input.get_effective_price()
    monthly_marketing_budget = business_input.monthly_marketing_budget
    monthly_operating_costs = business_input.monthly_operating_costs
    initial_capital = business_input.initial_capital

    bench = benchmark if benchmark is not None else get_benchmark(business_input.business_type)
    adjusted_cac_range = get_adjusted_cac(business_input.business_type, business_input.country)
    country_mod = get_country_modifier(business_input.country)

    # ПРИМЕЧАНИЕ: price используется as-is (пользователь сам устанавливает цену
    # для своей страны). country_mod.price_sensitivity_multiplier применяется
    # только к бенчмарк-значениям, а не к пользовательскому вводу.

    # ── 1. adjusted_churn ────────────────────────────
    # E-Commerce: churn = 0 — особый случай (не подписка)
    # Gig Economy: churn есть, но LTV считается иначе (see below)
    is_ecommerce = business_input.business_type == BusinessType.ECOMMERCE
    is_gig = business_input.business_type == BusinessType.GIG_ECONOMY

    if is_ecommerce:
        adjusted_churn = 0.0
    else:
        adjusted_churn = bench.monthly_churn.median * (1 + ai_churn_modifier)
        adjusted_churn = max(0.01, min(0.5, adjusted_churn))

    # ── 2. LTV ───────────────────────────────────────────
    if is_ecommerce:
        # Разовые покупки: LTV = AOV × avg_purchases_per_customer
        # (Harvard Business Review, 2014: LTV = AOV × F × T)
        # 30% клиентов совершают в среднем 2 повторные покупки
        repeat_rate = 0.3
        avg_repeat_purchases = 2.0
        ltv = price * (1 + repeat_rate * avg_repeat_purchases)
    elif is_gig:
        # Gig: исполнитель активен в среднем ~8 мес, потом уходит или снижает активность
        # LTV = доход_платформы_в_месяц / churn; churn из бенчмарков (~9%/мес → 11 мес avg)
        ltv = price / adjusted_churn
    else:
        ltv = price / adjusted_churn

    # ── 3. CAC ────────────────────────────────────────────────
    cac = adjusted_cac_range.median

    # AI-коррекция: высокий pct_would_buy → дешевле привлекать
    if ai_conversion_rate > bench.conversion_trial_to_paid.median:
        cac *= 0.8
    elif ai_conversion_rate < bench.conversion_trial_to_paid.median:
        cac *= 1.3

    cac = max(cac, 0.01)  # защита от нуля

    # ── 4. LTV/CAC ────────────────────────────────────────────
    ltv_cac_ratio = ltv / cac if cac > 0 else 999.0

    # ── 5. Gross margin ───────────────────────────────────────
    gross_margin = bench.gross_margin.median

    # ── 6. CAC Payback ────────────────────────────────────────
    denominator = price * gross_margin
    cac_payback_months = cac / denominator if denominator > 0 else 999.0

    # ── 7. Burn rate & Runway ─────────────────────────────────
    burn_rate = monthly_operating_costs + monthly_marketing_budget
    runway_months = int(initial_capital / burn_rate) if burn_rate > 0 else 999

    # ── 8. Операционный break-even (итеративно, до 36 мес) ───
    # Определяем месяц, в котором MRR ≥ burn_rate
    # (операционная самоокупаемость — стартап больше не сжигает деньги)
    # payment_conversion_modifier учитывает инфраструктуру платежей страны
    effective_conversion = bench.conversion_trial_to_paid.median * country_mod.payment_conversion_modifier
    new_users_per_month = (
        monthly_marketing_budget / max(cac, 1.0)
    ) * effective_conversion

    break_even_month: Optional[int] = None
    users_estimate: float = 0.0

    for m in range(1, 37):
        users_estimate = users_estimate * (1 - adjusted_churn) + new_users_per_month
        month_revenue = users_estimate * price
        if month_revenue >= burn_rate:
            break_even_month = m
            break

    return UnitEconomicsReport(
        ltv=round(ltv, 2),
        cac=round(cac, 2),
        ltv_cac_ratio=round(ltv_cac_ratio, 2),
        cac_payback_months=round(cac_payback_months, 1),
        adjusted_churn=round(adjusted_churn, 4),
        gross_margin=round(gross_margin, 4),
        monthly_burn_rate=round(burn_rate, 2),
        runway_months=runway_months,
        break_even_month=break_even_month,
        benchmark_ltv_cac=bench.typical_ltv_cac_ratio,
        benchmark_churn=bench.monthly_churn,
        benchmark_conversion=bench.conversion_trial_to_paid,
    )
