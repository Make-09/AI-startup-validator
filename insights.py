"""
insights.py — Комплексная аналитическая система инсайтов и рекомендаций стартапу.
Объединяет качественные сигналы CustDev (Mom Test), объективную юнит-экономику,
вероятностное моделирование Монте-Карло и конкурентную среду.
"""

from typing import List, Optional

from models import (
    AggregatedInterviewResults,
    BusinessInput,
    Insight,
    UnitEconomicsReport,
    MonteCarloResults,
    MarketResearchReport,
)


def generate_insights(
    business_input: BusinessInput,
    interview_results: AggregatedInterviewResults,
    unit_economics: Optional[UnitEconomicsReport] = None,
    monte_carlo_results: Optional[MonteCarloResults] = None,
    market_research: Optional[MarketResearchReport] = None,
) -> List[Insight]:
    """
    Генерирует список рекомендаций и рисков стартапа по 5 ключевым измерениям:
    1. Валидация проблемы и спроса (Problem & Demand)
    2. Ценообразование и готовность платить (Pricing & WTP)
    3. Юнит-экономика и окупаемость (LTV/CAC & Payback)
    4. Запас прочности и финансовая устойчивость (Runway & Cash Risk)
    5. Конкурентная стратегия и вероятность масштабирования (Scale & Competition)
    """
    insights: List[Insight] = []

    # ═══════════════════════════════════════════════════════════════
    #  БЛОК 1: Валидация проблемы и соответствия (Problem & Fit)
    # ═══════════════════════════════════════════════════════════════

    pct_would_buy = interview_results.pct_would_buy
    pct_price_too_high = interview_results.pct_price_too_high
    pct_price_too_low = interview_results.pct_price_too_low
    avg_problem_severity = interview_results.avg_problem_severity
    avg_solution_fit = interview_results.avg_solution_fit
    avg_wtp = interview_results.avg_willingness_to_pay

    # R1: Острота проблемы (Problem Severity)
    if avg_problem_severity < 4.0:
        insights.append(
            Insight(
                severity="critical",
                title="🔴 Проблема не является острой (Витамин, а не Обезболивающее)",
                message=(
                    f"Средняя острота проблемы составляет всего {avg_problem_severity:.1f}/10. "
                    "Пользователи не страдают от текущей ситуации и решают задачу бесплатными или привычными способами."
                ),
                recommendation="Сделайте pivot: найдите сегмент клиентов, для которых эта проблема является критической потерей денег или времени.",
                benchmark_ref="По методологии Y Combinator: стартап должен решать 'hair on fire' проблему (оценка 7+)",
            )
        )
    elif avg_problem_severity >= 7.5:
        insights.append(
            Insight(
                severity="success",
                title="🟢 Острая рыночная боль подтверждена",
                message=f"Респонденты подтверждают высокий уровень боли ({avg_problem_severity:.1f}/10). Проблема действительно беспокоит целевую аудиторию.",
                recommendation="В маркетинговых сообщениях делайте главный акцент именно на избавлении от этой конкретной боли.",
            )
        )

    # R2: Первичный спрос (% готовых купить)
    if pct_would_buy < 0.30:
        insights.append(
            Insight(
                severity="critical",
                title="🔴 Низкий покупательский интерес (<30%)",
                message=f"Только {pct_would_buy:.0%} опрошенных персон выразили твердую готовность приобрести продукт по предложенной цене.",
                recommendation="Пересмотрите ценностное предложение (Value Proposition) либо скорректируйте целевую аудиторию под более платежеспособный сегмент.",
            )
        )
    elif pct_would_buy >= 0.50 and avg_solution_fit >= 7.0:
        insights.append(
            Insight(
                severity="success",
                title="🟢 Сильный сигнал Product-Market Fit",
                message=(
                    f"Solution Fit составляет {avg_solution_fit:.1f}/10, при этом {pct_would_buy:.0%} респондентов готовы купить продукт."
                ),
                recommendation="Базовая концепция сильна. Приступайте к созданию кликабельного прототипа или MVP.",
                benchmark_ref="Тест Шона Эллиса (Sean Ellis PMF Test): порог достижения PMF — от 40% лояльных пользователей",
            )
        )

    # R3: Слабый Solution Fit
    if avg_solution_fit < 5.0 and avg_problem_severity >= 5.0:
        insights.append(
            Insight(
                severity="warning",
                title="🟠 Продукт недостаточно хорошо решает заявленную проблему",
                message=f"Боль у людей есть ({avg_problem_severity:.1f}/10), но предложенное решение получило средний фит всего {avg_solution_fit:.1f}/10.",
                recommendation="Внимательно изучите топ-3 опасений и пожеланий по фичам в ответах персон и переработайте функционал.",
            )
        )

    # ═══════════════════════════════════════════════════════════════
    #  БЛОК 2: Ценообразование (Pricing & WTP)
    # ═══════════════════════════════════════════════════════════════

    if pct_price_too_high > 0.50:
        insights.append(
            Insight(
                severity="warning",
                title="🟠 Высокий барьер стоимости",
                message=f"{pct_price_too_high:.0%} респондентов считают заявленную цену завышенной для предлагаемой ценности.",
                recommendation="Внедрите freemium-тариф, триал или снизьте цену на старте для снижения стоимости первой пробы.",
            )
        )
    elif pct_price_too_low > 0.35 and pct_would_buy >= 0.40:
        insights.append(
            Insight(
                severity="info",
                title="ℹ️ Возможность для повышения монетизации",
                message=f"{pct_price_too_low:.0%} опрошенных находят цену подозрительно низкой. Вы рискуете недополучать выручку.",
                recommendation="Протестируйте повышение базовой цены на 20–30% или сформируйте Pro/Business тарифный план.",
            )
        )

    # ═══════════════════════════════════════════════════════════════
    #  БЛОК 3: Юнит-экономика (Unit Economics & Payback)
    # ═══════════════════════════════════════════════════════════════

    if unit_economics:
        # ── Анализ окупаемости привлечения (CAC Payback) и ликвидности ────────
        _payback = unit_economics.cac_payback_months
        _runway  = unit_economics.runway_months

        # Рассчитываем необходимый капитал для стресс-сценария (P10 Монте-Карло)
        stress_capital_rec = ""
        if monte_carlo_results and getattr(monte_carlo_results, "stress_capital_p10", 0) > 0:
            sc_val = monte_carlo_results.stress_capital_p10
            stress_capital_rec = (
                f"Для устойчивости к 90% рыночных сценариев (траекторный P10 стресс-тест из "
                f"{monte_carlo_results.num_simulations:,} прогонов) совокупный капитал должен составлять ~${sc_val:,.0f}. "
            )

        if 0 < _payback < 999.0 and _payback > _runway:
            # Внимание: разграничиваем юнит-окупаемость и общий денежный поток стартапа
            if unit_economics.peak_capital_deficit <= 0:
                insights.append(
                    Insight(
                        severity="warning",
                        title="🟠 Замедленная оборачиваемость: CAC Payback > статического Runway",
                        message=(
                            f"Когортный возврат затрат на привлечение клиента занимает {_payback:.1f} мес., "
                            f"что превышает статический runway без выручки ({_runway} мес.). "
                            f"В базовом сценарии стартового капитала ${unit_economics.initial_capital:,.0f} хватает: "
                            f"пиковое расходование кэша до безубыточности (месяц {unit_economics.break_even_month}) "
                            f"составляет ${unit_economics.peak_cash_drag:,.0f}, оставляя подушку ${unit_economics.min_cash_balance:,.0f}. "
                            f"Однако из-за медленного возврата маркетинговых вложений модель крайне уязвима к шокам "
                            f"(вероятность банкротства в Монте-Карло: {monte_carlo_results.bankruptcy_probability if monte_carlo_results else 47:.1f}%)."
                        ),
                        recommendation=(
                            f"{stress_capital_rec}"
                            "Для ускорения оборачиваемости: (A) введите годовую подписку со скидкой (предоплата сокращает кассовый разрыв); "
                            "(B) подключите B2B/реферальные каналы со сниженным CAC; "
                            "(C) внедрите платные разовые допродажи (upsell)."
                        ),
                        benchmark_ref="По венчурным стандартам B2C: оптимальный CAC Payback — до 12 месяцев.",
                    )
                )
            else:
                insights.append(
                    Insight(
                        severity="critical",
                        title="🔴 Кассовый разрыв: капитала не хватает до точки безубыточности",
                        message=(
                            f"При текущем темпе привлечения стартап исчерпает средства "
                            f"с дефицитом ~${unit_economics.peak_capital_deficit:,.0f}. "
                            f"Окупаемость привлечения ({_payback:.1f} мес.) не позволяет реинвестировать выручку вовремя."
                        ),
                        recommendation=(
                            f"Необходимо привлечь дополнительно минимум ${unit_economics.peak_capital_deficit:,.0f} "
                            "в качестве предпосевного раунда либо снизить ежемесячные расходы."
                        ),
                        benchmark_ref="Правило ликвидности: Runway с учётом выручки должен превышать Break-even минимум на 3–6 месяцев.",
                    )
                )
        elif 0 < _payback > 18.0 and _payback < 999.0:
            insights.append(
                Insight(
                    severity="warning",
                    title="🟠 Слишком долгий CAC Payback (>18 месяцев)",
                    message=(
                        f"Возврат затрат на привлечение клиента занимает {_payback:.1f} мес. — "
                        "это замедляет оборачиваемость оборотного капитала."
                    ),
                    recommendation="Внедрите годовые тарифы со скидкой 20–30% или снизьте CAC через SEO.",
                    benchmark_ref="B2C payback ≤ 12 мес, B2B ≤ 18 мес (a16z SaaS Benchmarks 2024).",
                )
            )

        # LTV:CAC отношение
        if unit_economics.ltv_cac_ratio < 1.0:
            insights.append(
                Insight(
                    severity="critical",
                    title="🔴 Экономика привлекает клиентов в убыток (LTV < CAC)",
                    message=(
                        f"LTV (${unit_economics.ltv:.2f}) ниже стоимости привлечения клиента CAC (${unit_economics.cac:.2f}). "
                        f"Отношение LTV:CAC = {unit_economics.ltv_cac_ratio:.2f}x. При масштабировании проект будет сжигать капитал пропорционально росту."
                    ),
                    recommendation="Срочно увеличьте удержание (LTV) за счет снижения оттока либо перейдите на более органические и дешевые каналы привлечения.",
                    benchmark_ref=f"Отраслевой ориентир LTV:CAC: {unit_economics.benchmark_ltv_cac.median}x (диапазон {unit_economics.benchmark_ltv_cac.low}x–{unit_economics.benchmark_ltv_cac.high}x)",
                )
            )
        elif unit_economics.ltv_cac_ratio < 2.5:
            insights.append(
                Insight(
                    severity="warning",
                    title="🟠 Пограничная маржинальность привлечения (LTV:CAC < 2.5x)",
                    message=(
                        f"Отношение LTV к CAC составляет {unit_economics.ltv_cac_ratio:.2f}x. "
                        "В реальных условиях с учетом непредвиденных расходов запас прочности мал."
                    ),
                    recommendation="Оптимизируйте конверсию посадочной страницы и поработайте над допродажами (upsell), чтобы поднять средний чек.",
                )
            )
        else:
            insights.append(
                Insight(
                    severity="success",
                    title="🟢 Эффективная юнит-экономика (LTV:CAC ≥ 3.0x)",
                    message=(
                        f"Отношение LTV:CAC составляет {unit_economics.ltv_cac_ratio:.2f}x (LTV: ${unit_economics.ltv:.2f}, CAC: ${unit_economics.cac:.2f}). "
                        "Каждый вложенный в маркетинг доллар генерирует здоровую отдачу."
                    ),
                    recommendation="Канал привлечения жизнеспособен, можно планировать постепенное масштабирование рекламного бюджета.",
                    benchmark_ref=f"Медиана отрасли: {unit_economics.benchmark_ltv_cac.median}x",
                )
            )

        # Срок окупаемости CAC
        if unit_economics.cac_payback_months > 18.0:
            insights.append(
                Insight(
                    severity="critical",
                    title="🔴 Слишком долгий срок окупаемости привлечения (>18 месяцев)",
                    message=(
                        f"Возврат затрат на привлечение одного клиента занимает {unit_economics.cac_payback_months:.1f} мес. "
                        "Это создает огромную нагрузку на оборотный капитал стартапа."
                    ),
                    recommendation="Внедрите годовые предоплатные тарифы со скидкой или сократите стоимость рекламы.",
                    benchmark_ref="Золотой венчурный стандарт окупаемости CAC для B2C — до 12 месяцев, для B2B — до 18 месяцев.",
                )
            )
        elif unit_economics.cac_payback_months <= 6.0 and unit_economics.cac > 0:
            insights.append(
                Insight(
                    severity="success",
                    title="🟢 Быстрая окупаемость CAC (до 6 месяцев)",
                    message=f"Клиент окупает затраты на маркетинг всего за {unit_economics.cac_payback_months:.1f} мес. Это ускоряет реинвестирование выручки.",
                    recommendation="Отличный показатель оборачиваемости капитала.",
                )
            )

        # Запас прочности (Runway)
        if unit_economics.runway_months < 6:
            insights.append(
                Insight(
                    severity="critical",
                    title="🔴 Критический дефицит ликвидности (Runway < 6 месяцев)",
                    message=(
                        f"При стартовом капитале ${business_input.initial_capital:,.0f} и ежемесячном сжигании ${unit_economics.monthly_burn_rate:,.0f} "
                        f"денег хватит всего на {unit_economics.runway_months} мес. Стартап рискует закрыться до достижения первой выручки."
                    ),
                    recommendation="Сократите фиксированные операционные издержки или найдите предпосевные инвестиции (Angel / FFF).",
                )
            )
        elif 6 <= unit_economics.runway_months < 12:
            insights.append(
                Insight(
                    severity="warning",
                    title="🟠 Умеренный финансовый запас (Runway 6–12 месяцев)",
                    message=f"Текущего бюджета хватит на {unit_economics.runway_months} месяцев работы. Времени на ошибки мало.",
                    recommendation="Сфокусируйтесь на получении первых платящих клиентов уже в первые 60 дней.",
                )
            )

    # ═══════════════════════════════════════════════════════════════
    #  БЛОК 4: Моделирование Монте-Карло (Probabilistic Risks)
    # ═══════════════════════════════════════════════════════════════

    if monte_carlo_results:
        bankrupt_p = monte_carlo_results.bankruptcy_probability
        if bankrupt_p >= 60.0:
            insights.append(
                Insight(
                    severity="critical",
                    title="🔴 Высокая вероятность исчерпания средств по Монте-Карло",
                    message=(
                        f"По результатам {monte_carlo_results.num_simulations} вероятностных сценариев "
                        f"вероятность банкротства в течение 24 месяцев составляет {bankrupt_p:.1f}%. "
                        "Волатильность оттока и расходов с высокой вероятностью исчерпает баланс."
                    ),
                    recommendation="Требуется пересмотр структуры затрат либо привлечение более солидного посевного раунда.",
                    benchmark_ref="Статистика Startup Genome: до 70% стартапов терпят неудачу из-за преждевременного исчерпания денежного запаса",
                )
            )
        elif bankrupt_p <= 20.0:
            insights.append(
                Insight(
                    severity="success",
                    title="🟢 Высокая вероятность финансовой выживаемости (>80%)",
                    message=(
                        f"Вероятность сохранения платежеспособности в течение 24 месяцев составляет {100.0 - bankrupt_p:.1f}%. "
                        "Бизнес-модель демонстрирует устойчивость к рыночным колебаниям."
                    ),
                    recommendation="У модели хороший фундамент для перехода к этапу масштабирования.",
                )
            )

        # Инсайт: Subscription для разовой задачи — структурный риск Churn Cliff
        if getattr(monte_carlo_results, "product_type", "recurring") in ("one_shot",):
            insights.append(
                Insight(
                    severity="warning",
                    title="⚠️ Subscription для разовой задачи — Churn Cliff",
                    message=(
                        "Продукт решает разовую задачу (найти работу, создать резюме), "
                        "но монетизируется через ежемесячную подписку. "
                        "Когортный LTV значительно ниже классического SaaS-расчёта: "
                        "40–45% клиентов уйдут уже в 1-й месяц после решения своей задачи."
                    ),
                    recommendation=(
                        "Рассмотрите upsell-стратегию: добавьте функции для постоянной занятости "
                        "(LinkedIn-профиль, отслеживание откликов, карьерный коучинг). "
                        "Это переведёт продукт из one_shot в recurring и структурно снизит отток."
                    ),
                    benchmark_ref=(
                        "ProfitWell: job-search SaaS median churn Month1=42%, Month3 cumulative=68%. "
                        "Выживают продукты с «post-hire» функционалом (LinkedIn Premium модель)."
                    ),
                )
            )

        if monte_carlo_results.prob_reach_10k_mrr >= 40.0:
            insights.append(
                Insight(
                    severity="success",
                    title="🟢 Достижимая цель роста ($10K+ MRR)",
                    message=f"В {monte_carlo_results.prob_reach_10k_mrr:.1f}% симуляций проект выходит на выручку свыше $10,000 в месяц к концу 2-го года.",
                    recommendation="Потенциал коммерческой масштабируемости подтвержден математическим моделированием.",
                )
            )

    # ═══════════════════════════════════════════════════════════════
    #  БЛОК 5: Конкурентная среда (Market & Competition)
    # ═══════════════════════════════════════════════════════════════

    if market_research:
        if market_research.competition_level in ("Высокая", "Олигополия / Доминирование гигантов"):
            insights.append(
                Insight(
                    severity="warning",
                    title=f"⚠️ Плотная конкурентная среда ({market_research.competition_level})",
                    message=(
                        f"На рынке действуют сильные альтернативы: {', '.join(c.name for c in market_research.competitors[:3])}. "
                        "Прямая лобовая конкуренция приведет к высокому CAC."
                    ),
                    recommendation=f"Сделайте ставку на дифференциацию: {market_research.differentiation_strategy}",
                )
            )

    # ═══════════════════════════════════════════════════════════════
    #  БЛОК 6: Защита от предвзятости симуляции (Bias Detection)
    # ═══════════════════════════════════════════════════════════════

    all_avg = (
        avg_problem_severity
        + avg_solution_fit
        + interview_results.avg_willingness_to_pay
        + interview_results.avg_switching_likelihood
        + interview_results.avg_nps_score
    ) / 5.0
    if all_avg > 7.5 and pct_would_buy > 0.80:
        insights.append(
            Insight(
                severity="info",
                title="⚠️ Калибровочное предупреждение: Подозрительно позитивные ответы",
                message=(
                    f"Средний балл симуляции {all_avg:.1f}/10 и {pct_would_buy:.0%} готовности купить — это аномально высокий результат. "
                    "В реальных условиях клиенты более инертны и скептичны."
                ),
                recommendation="Обязательно подтвердите результаты 5–7 живыми интервью по методологии Mom Test в полевых условиях.",
            )
        )

    return insights
