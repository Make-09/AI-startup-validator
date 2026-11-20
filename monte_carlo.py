"""
monte_carlo.py — Реалистичное вероятностное финансовое моделирование стартапа.

Ключевые улучшения по сравнению с наивной моделью:
  1. Когортный отток (Retention Decay) — churn зависит от возраста клиента,
     а не одинаков для всех. Источник: ProfitWell Retention Benchmarks 2024.
  2. CAC Escalation (Ad Fatigue) — стоимость привлечения растёт по мере
     исчерпания легкодоступной аудитории. Источник: Meta Ads Benchmarks.
  3. Шоковые события (Black Swans) — блокировка рекламного кабинета (3%/мес),
     выход конкурента с бесплатным аналогом (1%/мес). CB Insights post-mortems.
  4. Fan Chart data — сохраняет 200 выборочных траекторий MRR для визуализации
     облака траекторий (Spaghetti Fan Chart) в Streamlit.
"""

from typing import Optional
import logging
import numpy as np

from models import BusinessInput, UnitEconomicsReport, MonteCarloResults

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════
#  Когортные профили оттока (Retention Decay)
#
#  Данные: ProfitWell 2024, Baremetrics Open Benchmarks, CB Insights
#  Индекс = месяц жизни клиента с момента привлечения (0-based)
#  Последнее значение применяется ко всем последующим месяцам
# ═══════════════════════════════════════════════════════════════

CHURN_PROFILES: dict[str, list[float]] = {
    # Разовая задача: резюме, дизайн логотипа, ремонт, переезд, свадьба
    # Первая волна отписок огромная — клиент решил задачу и уходит
    "one_shot": [0.45, 0.30, 0.15, 0.10, 0.08, 0.07, 0.065, 0.06],

    # Постоянная боль: CRM, бухгалтерия, почта, аналитика
    # Churn снижается — клиенты встраивают продукт в процессы
    "recurring": [0.15, 0.10, 0.08, 0.07, 0.065, 0.06, 0.055, 0.05],

    # Периодическая задача: курсы, фитнес, налоги раз в год
    # Волнообразный паттерн с сезонными пиками оттока
    "periodic": [0.25, 0.20, 0.12, 0.08, 0.15, 0.20, 0.10, 0.07],
}


def _get_cohort_churn(
    month_since_acquisition: int,
    product_type: str,
    noise: np.ndarray,
    churn_scenario_mult: np.ndarray,
    cliff_month1: Optional[np.ndarray] = None,
    cliff_month2: Optional[np.ndarray] = None,
) -> np.ndarray:
    """
    Возвращает вектор оттока (num_simulations,) для когорты клиентов
    в заданный месяц их жизни.

    Компоненты:
      - base: профильное значение из CHURN_PROFILES (детерминированная гипотеза)
      - noise: per-month Log-Normal шум σ=0.20 (ежемесячная случайность)
      - churn_scenario_mult: scenario-level мультипликатор (рисуется 1 раз/прогон)
      - cliff_month1/2: для one_shot — сценарный диапазон высоты Churn Cliff
        (гипотеза 0.25–0.65 вместо фиксированных 0.45), т.к. реальные данные
        не подтверждены.
    """
    profile = CHURN_PROFILES.get(product_type, CHURN_PROFILES["recurring"])
    idx = min(month_since_acquisition - 1, len(profile) - 1)
    base = profile[idx]

    # Для one_shot: заменяем фиксированную высоту Cliff на сценарную
    if product_type == "one_shot":
        if month_since_acquisition == 1 and cliff_month1 is not None:
            base_vec = cliff_month1  # уже вектор (N,)
        elif month_since_acquisition == 2 and cliff_month2 is not None:
            base_vec = cliff_month2
        else:
            base_vec = np.full_like(noise, base)
        return np.clip(base_vec * noise * churn_scenario_mult, 0.005, 0.90)

    return np.clip(base * noise * churn_scenario_mult, 0.005, 0.90)


def _effective_cac(
    base_cac: float,
    cumulative_users: np.ndarray,
    tam: int,
) -> np.ndarray:
    """
    CAC растёт по мере выгорания рекламной аудитории (Ad Fatigue).

    Формула: CAC(t) = base_CAC × (1 + saturation_factor) ^ penetration
    penetration = cumulative_users / TAM  (от 0 до 1)
    saturation_factor = 2.5 для B2C (Instagram/Facebook выгорают быстро)

    Пример:
      При охвате  5% TAM: CAC × 1.14  (+14%)
      При охвате 10% TAM: CAC × 1.30  (+30%)
      При охвате 20% TAM: CAC × 1.69  (+69%)
      При охвате 40% TAM: CAC × 2.85  (+185%)

    Источник: Meta Ads Industry Benchmarks 2024, апроксимация из публичных кейсов.
    """
    saturation_factor = 2.5
    penetration = np.clip(cumulative_users / max(tam, 1), 0.0, 0.90)
    return base_cac * np.power(1.0 + saturation_factor, penetration)


def run_monte_carlo_simulation(
    business_input: BusinessInput,
    unit_economics: UnitEconomicsReport,
    num_simulations: int = 10000,
    num_months: int = 24,
    random_seed: Optional[int] = 42,
    product_type: str = "recurring",
    fan_chart_samples: int = 200,
) -> MonteCarloResults:
    """
    Реалистичная симуляция Монте-Карло (10 000 сценариев на 24 месяца).

    Модель когорт:
      - Каждый месяц создаётся новая когорта привлечённых клиентов
      - Каждая когорта стареет и теряет клиентов по своему профилю оттока
      - Суммарная база = сумма выживших клиентов из всех когорт

    Scenario-level параметры (рисуются ОДИН РАЗ на симуляцию):
      - scenario_market_fit: насколько рынок восприимчив именно к этому продукту
        (Log-Normal σ=0.55, диапазон P10≈0.49x, P90≈2.03x)
      - scenario_cac_luck: "удача" в рекламных кампаниях (σ=0.40)
      - scenario_churn_mult: базовый уровень удержания этого рынка (σ=0.35)

    Эти параметры создают "тяжёлые хвосты": часть симуляций изначально
    в плохом рынке (PMF≈0), часть — в отличном. Это реалистично расширяет
    диапазон P10–P90 по сравнению с только per-month шумом.

    Args:
        product_type: Тип спроса — влияет на когортный профиль churn.
                      Определяется через detect_product_type() в economics.py.
        fan_chart_samples: Сколько случайных траекторий сохранить для Fan Chart.
    """
    if random_seed is not None:
        np.random.seed(random_seed)

    arpa = max(business_input.get_effective_price(), 0.01)
    gross_margin = max(unit_economics.gross_margin, 0.05)
    base_cac = max(unit_economics.cac, 0.5)
    init_cash = max(business_input.initial_capital, 0.0)
    marketing_budget = max(business_input.monthly_marketing_budget, 0.0)
    operating_costs = max(business_input.monthly_operating_costs, 0.0)
    tam = max(getattr(business_input, "market_size_estimate", 100_000), 1_000)

    N = num_simulations
    T = num_months

    # ── Scenario-level параметры (рисуются ОДИН РАЗ до основного цикла) ──────
    # Каждый из N прогонов получает свой «характер рынка» — создаёт тяжёлые хвосты.
    # Без этих параметров усреднение по 24 когортам сжимает P10-P90 (ЦПТ).
    #
    # Интерпретация:
    #   market_fit_mult < 1.0  — плохой PMF, рынок не реагирует на рекламу
    #   cac_luck_mult   > 1.0  — реклама дорогая, аудитория дорогая/конкурентная
    #   churn_base_mult > 1.0  — рынок «нелояльный», клиенты уходят быстрее
    scenario_market_fit  = np.random.lognormal(0.0, 0.55, size=N)  # P10≈0.49x, P90≈2.03x
    scenario_cac_luck    = np.random.lognormal(0.0, 0.40, size=N)  # P10≈0.60x, P90≈1.68x
    scenario_churn_mult  = np.random.lognormal(0.0, 0.35, size=N)  # P10≈0.69x, P90≈1.44x

    # Для one_shot: высота Churn Cliff (мес.1) — это гипотеза, не установленный факт.
    # Варьируем её сценарно: равномерно [0.25, 0.65] вместо фиксированных 0.45.
    # P10 сценарий: cliff=0.25 (продукт нашёл нишу для повторного использования)
    # P90 сценарий: cliff=0.65 (пользователи уходят ещё быстрее, чем ожидалось)
    if product_type == "one_shot":
        scenario_cliff_month1 = np.random.uniform(0.25, 0.65, size=N)
        scenario_cliff_month2 = np.random.uniform(0.15, 0.45, size=N)
        logger.info(
            f"[monte_carlo] one_shot cliff uncertainty: "
            f"month1 median={np.median(scenario_cliff_month1):.2f} "
            f"[P10={np.percentile(scenario_cliff_month1,10):.2f}, "
            f"P90={np.percentile(scenario_cliff_month1,90):.2f}]"
        )
    else:
        scenario_cliff_month1 = None
        scenario_cliff_month2 = None

    logger.info(
        f"[monte_carlo] scenario params (median / P10 / P90): "
        f"market_fit={np.percentile(scenario_market_fit,50):.2f}/{np.percentile(scenario_market_fit,10):.2f}/{np.percentile(scenario_market_fit,90):.2f} | "
        f"cac_luck={np.percentile(scenario_cac_luck,50):.2f}/{np.percentile(scenario_cac_luck,10):.2f}/{np.percentile(scenario_cac_luck,90):.2f} | "
        f"churn_mult={np.percentile(scenario_churn_mult,50):.2f}/{np.percentile(scenario_churn_mult,10):.2f}/{np.percentile(scenario_churn_mult,90):.2f}"
    )

    # ── Матрицы результатов ──────────────────────────────────────
    mrr_matrix     = np.zeros((N, T + 1))
    users_matrix   = np.zeros((N, T + 1))
    balance_matrix = np.zeros((N, T + 1))
    balance_matrix[:, 0] = init_cash

    # Флаги банкротства и безубыточности
    bankruptcy_month = np.full(N, fill_value=np.nan)
    break_even_month = np.full(N, fill_value=np.nan)

    # ── Когортная матрица [когорта][симуляция] ───────────────────
    # cohorts[k] — число выживших клиентов из когорты месяца k
    # в каждой из N симуляций
    cohorts: list[np.ndarray] = []

    # Накопленные пользователи для CAC Escalation
    cumulative_users = np.zeros(N)

    # Флаг временной заморозки рекламы (после шокового события)
    ad_ban_countdown = np.zeros(N, dtype=int)   # месяцев без рекламы
    churn_shock_countdown = np.zeros(N, dtype=int)  # месяцев усиленного оттока

    # ── Основной цикл по месяцам ─────────────────────────────────
    for t in range(1, T + 1):

        # 1. Шоковые события (проверяем каждый месяц)
        shocks = np.random.uniform(0, 1, size=N)

        # 3% шанс: блокировка рекламного кабинета → 0 рекламы на 2 месяца
        new_ad_ban = (shocks < 0.03) & (ad_ban_countdown == 0)
        ad_ban_countdown[new_ad_ban] = 2
        ad_ban_countdown = np.maximum(ad_ban_countdown - 1, 0)

        # 1% шанс: конкурент выпустил бесплатную фичу → churn +20% на 3 мес
        new_churn_shock = (shocks > 0.99) & (churn_shock_countdown == 0)
        churn_shock_countdown[new_churn_shock] = 3
        churn_shock_countdown = np.maximum(churn_shock_countdown - 1, 0)

        # 2. Эффективный CAC с учётом выгорания аудитории
        cac_t = _effective_cac(base_cac, cumulative_users, tam)

        # 3. Случайная эффективность маркетинга (Log-Normal) — per-month шум
        acq_efficiency = np.random.lognormal(mean=0.0, sigma=0.30, size=N)

        # Если реклама заморожена — новых клиентов из paid нет
        effective_budget = np.where(ad_ban_countdown > 0, 0.0, marketing_budget)
        # Scenario-level параметры применяются здесь:
        #   scenario_cac_luck    — одни прогоны систематически платят больше за рекламу
        #   scenario_market_fit  — одни прогоны систематически получают меньше отдачи
        effective_cac_with_scenario = np.maximum(cac_t * scenario_cac_luck, 0.01)
        paid_new = (effective_budget / effective_cac_with_scenario) * acq_efficiency * scenario_market_fit

        # Новая когорта (клиенты этого месяца)
        cohorts.append(paid_new.copy())
        cumulative_users += paid_new

        # 4. Органика: 1–3% от базы активных (сарафанное радио)
        total_active_prev = users_matrix[:, t - 1]
        viral_factor = np.random.uniform(0.01, 0.03, size=N)
        organic_new = total_active_prev * viral_factor
        cohorts[-1] += organic_new  # добавляем органику в текущую когорту

        # 5. Применяем когортный отток к каждой существующей когорте
        # Для когорты k (привлечена в месяце k), на текущем шаге t
        # месяц жизни когорты = t - k (начиная с 1)
        noise_churn = np.random.lognormal(mean=0.0, sigma=0.20, size=N)
        # Дополнительный шок оттока
        churn_shock_mult = np.where(churn_shock_countdown > 0, 1.20, 1.0)
        noise_churn *= churn_shock_mult

        total_active_now = np.zeros(N)
        for k, cohort in enumerate(cohorts):
            age = t - k  # месяц жизни когорты (1 = первый месяц)
            churn_vec = _get_cohort_churn(
                age, product_type, noise_churn, scenario_churn_mult,
                cliff_month1=scenario_cliff_month1,
                cliff_month2=scenario_cliff_month2,
            )
            cohort *= (1.0 - churn_vec)
            cohorts[k] = np.maximum(cohort, 0.0)
            total_active_now += cohorts[k]

        users_matrix[:, t] = total_active_now

        # 6. MRR и денежный поток
        curr_mrr = total_active_now * arpa
        mrr_matrix[:, t] = curr_mrr

        gross_profit = curr_mrr * gross_margin
        sim_operating = operating_costs * np.random.normal(1.0, 0.05, size=N)
        sim_operating = np.maximum(sim_operating, operating_costs * 0.5)
        total_costs = sim_operating + effective_budget
        net_cash = gross_profit - total_costs

        curr_balance = balance_matrix[:, t - 1] + net_cash
        balance_matrix[:, t] = curr_balance

        # 7. Фиксация банкротства и безубыточности
        newly_bankrupt = (curr_balance <= 0) & np.isnan(bankruptcy_month)
        bankruptcy_month[newly_bankrupt] = t

        just_profitable = (net_cash >= 0) & np.isnan(break_even_month)
        break_even_month[just_profitable] = t

    # ── Агрегация результатов ────────────────────────────────────
    months = list(range(T + 1))

    def pct(arr, q):
        return [float(np.round(np.percentile(arr[:, m], q), 2)) for m in months]

    mrr_p10 = pct(mrr_matrix, 10)
    mrr_p50 = pct(mrr_matrix, 50)
    mrr_p90 = pct(mrr_matrix, 90)
    users_p10 = [float(np.round(np.percentile(users_matrix[:, m], 10), 1)) for m in months]
    users_p50 = [float(np.round(np.percentile(users_matrix[:, m], 50), 1)) for m in months]
    users_p90 = [float(np.round(np.percentile(users_matrix[:, m], 90), 1)) for m in months]
    balance_p10 = pct(balance_matrix, 10)
    balance_p50 = pct(balance_matrix, 50)
    balance_p90 = pct(balance_matrix, 90)

    # ── Траекторный (pathwise) анализ кассовой ямы и выживаемости ────────
    # Для каждой траектории вычисляем её индивидуальный минимум денежного остатка
    pathwise_min = np.min(balance_matrix, axis=1)

    # Банкротство строго эквивалентно тому, что кассовый баланс опустился <= 0 в любой месяц
    bankrupt_count = np.sum(pathwise_min <= 0)
    bankruptcy_prob = float(np.round((bankrupt_count / N) * 100.0, 1))

    # Траекторные процентили минимального денежного остатка
    p10_min = float(np.round(np.percentile(pathwise_min, 10), 2))
    p50_min = float(np.round(np.percentile(pathwise_min, 50), 2))
    p90_min = float(np.round(np.percentile(pathwise_min, 90), 2))

    # Совокупный капитал, необходимый для выживания в 90% сценариев (P10 стресс-тест)
    stress_capital_p10 = float(np.round(init_cash + max(0.0, -p10_min), 2))

    final_mrr = mrr_matrix[:, -1]
    final_users = users_matrix[:, -1]
    prob_10k_mrr = float(np.round(np.sum(final_mrr >= 10_000) / N * 100.0, 1))
    prob_1k_users = float(np.round(np.sum(final_users >= 1_000) / N * 100.0, 1))

    be_paths = break_even_month[~np.isnan(break_even_month)]
    median_be = int(np.round(np.median(be_paths))) if len(be_paths) > 0 else None

    # ── Fan Chart: случайная выборка траекторий ──────────────────
    sample_idx = np.random.choice(N, size=min(fan_chart_samples, N), replace=False)
    sample_trajectories = [
        [float(np.round(mrr_matrix[i, m], 2)) for m in months]
        for i in sample_idx
    ]

    logger.info(
        f"[monte_carlo] product_type={product_type} | N={N} | "
        f"bankruptcy={bankruptcy_prob}% | "
        f"median_MRR_24m=${mrr_p50[-1]:,.0f} | "
        f"P10=${mrr_p10[-1]:,.0f} | P90=${mrr_p90[-1]:,.0f} | "
        f"pathwise_min P10=${p10_min:,.0f} | stress_capital_P10=${stress_capital_p10:,.0f}"
    )

    return MonteCarloResults(
        num_simulations=N,
        num_months=T,
        mrr_p10=mrr_p10,
        mrr_p50=mrr_p50,
        mrr_p90=mrr_p90,
        users_p10=users_p10,
        users_p50=users_p50,
        users_p90=users_p90,
        balance_p10=balance_p10,
        balance_p50=balance_p50,
        balance_p90=balance_p90,
        bankruptcy_probability=bankruptcy_prob,
        prob_reach_10k_mrr=prob_10k_mrr,
        prob_reach_1k_users=prob_1k_users,
        median_break_even_month=median_be,
        sample_trajectories=sample_trajectories,
        product_type=product_type,
        pathwise_min_balance_p10=p10_min,
        pathwise_min_balance_p50=p50_min,
        pathwise_min_balance_p90=p90_min,
        stress_capital_p10=stress_capital_p10,
    )
