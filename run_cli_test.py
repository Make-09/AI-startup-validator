"""
run_cli_test.py — Автономный пробный прогон AI Startup Validator без Streamlit.
Позволяет протестировать весь пайплайн валидации в терминале:
- Получение бенчмарков (World Bank API)
- Анализ конкурентов (3 уровня: база, веб, LLM)
- Генерацию синтетических персон
- Двухфазное AI Customer Discovery интервью
- Агрегацию числовых оценок
- Расчёт юнит-экономики (LTV, CAC, LTV:CAC, Payback, Runway, Break-even)
- Вероятностную симуляцию Монте-Карло (500 сценариев на 24 месяца)
- Генерацию экспертных инсайтов и рисков
- Расчёт итогового скоринга жизнеспособности (Overall Viability Score)
"""

import os
import sys
import json
import logging
from pprint import pprint

# Принудительная кодировка UTF-8 для консоли Windows
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

# Настройка логирования для терминала
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("CLI_TEST")

# Подавляем шумные внутренние логи сторонних библиотек
# DDGS (duckduckgo_search) пишет INFO о каждом DNS-сбое — это ожидаемо в офлайн-режиме
for _noisy_lib in ("ddgs", "duckduckgo_search", "httpx", "httpcore", "urllib3"):
    logging.getLogger(_noisy_lib).setLevel(logging.ERROR)

# Загрузка .env если есть
if os.path.exists(".env"):
    with open(".env", "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip())

import config
from models import (
    BusinessInput,
    BusinessType,
    RevenueModel,
    ValidationReport,
    InterviewResponse,
)
from benchmarks import fetch_realtime_benchmarks, get_benchmark
from market_research import analyze_market_competitors
from personas import generate_personas, _detect_age_profile
from interview_engine import run_all_interviews
from aggregator import aggregate_interviews
from economics import calculate_unit_economics, calculate_overall_viability_score, detect_product_type
from monte_carlo import run_monte_carlo_simulation
from insights import generate_insights


def main():
    print("\n" + "═" * 70)
    print("   🔬 AI STARTUP VALIDATOR — АВТОНОМНЫЙ ПРОГОН ПАЙПЛАЙНА (CLI)")
    print("═" * 70 + "\n")

    # 1. Задаем тестовую бизнес-идею
    business_input = BusinessInput(
        name="QuickCV AI",
        description=(
            "Сервис мгновенной адаптации резюме под конкретные требования вакансий "
            "на HeadHunter и LinkedIn с генерацией персонального сопроводительного письма."
        ),
        target_audience="IT-специалисты, маркетологи и офисные сотрудники 22–35 лет в поиске работы",
        business_type=BusinessType.SAAS_B2C,
        country="kazakhstan",
        language="Русский",
        num_personas=3,  # Для быстрого теста 3 персоны
        revenue_model=RevenueModel.SUBSCRIPTION,
        price=7.0,  # $7/месяц
        initial_capital=5000.0,
        monthly_marketing_budget=400.0,
        monthly_operating_costs=150.0,
        market_size_estimate=150000,
    )

    print(f"📌 Проект: {business_input.name}")
    print(f"📝 Описание: {business_input.description}")
    print(f"🎯 Аудитория: {business_input.target_audience}")
    print(f"🌍 Рынок: {business_input.country.upper()} | Модель: {business_input.revenue_model.value} (${business_input.price}/мес)")
    print(f"💼 Стартовый капитал: ${business_input.initial_capital:,.0f} | Burn Rate план: ${business_input.monthly_marketing_budget + business_input.monthly_operating_costs:,.0f}/мес\n")

    # 2. Макроданные и бенчмарки
    print("⏳ [1/7] Получение бенчмарков (World Bank API + отраслевые данные)...")
    bench, bench_info = fetch_realtime_benchmarks(
        business_input.business_type,
        business_input.country,
        business_input.description,
    )
    print(f"   ✅ {bench_info}")
    print(f"   📊 Отрасль: {bench.display_name} | Медианный Churn: {bench.monthly_churn.median*100:.1f}% | Базовый CAC: ${bench.cac.median}\n")

    # 3. Анализ конкурентной среды
    print("⏳ [2/7] Анализ конкурентов и позиционирования (каталог + live search + LLM)...")
    market_rep = analyze_market_competitors(business_input)
    print(f"   ✅ Уровень конкуренции: {market_rep.competition_level}")
    print(f"   💡 Рекомендуемое УТП: {market_rep.differentiation_strategy}")
    print("   🏢 Идентифицированные игроки:")
    for comp in market_rep.competitors:
        print(f"      • {comp.name} [{comp.category}] — Слабость: {comp.weaknesses}")
    print()

    # 4. Генерация синтетических персон
    print("⏳ [3/7] Генерация клиентских персон (Mom Test)...")
    age_prof = _detect_age_profile(business_input)
    personas = generate_personas(business_input, count=business_input.num_personas)
    print(f"   ✅ Создано {len(personas)} детальных персон:")
    for p in personas:
        print(f"      • {p.name}, {p.age} лет, {p.occupation} ({p.city}) — Доход: ${p.monthly_income}/мес, Характер: {p.personality_trait}")
    print()

    # 5. Проведение AI-интервью
    print("⏳ [4/7] Запуск симуляции глубинных Mom Test интервью (2 фазы)...")
    api_key = os.environ.get("OPENAI_API_KEY", "")
    
    # Проверяем, есть ли реальный рабочий ключ в пуле
    has_live_key = bool(api_key and api_key not in ("your_api_key_here", "вставьте_ваш_ключ_здесь"))
    
    responses = []
    if has_live_key:
        try:
            responses = run_all_interviews(
                personas,
                business_input,
                market_context=market_rep.summary,
                age_profile=age_prof,
            )
        except Exception as e:
            logger.warning(f"Ошибка вызова LLM: {e}. Применяем калиброванный фоллбэк для теста.")
            responses = []

    # Если API-ключ не настроен или исчерпан лимит, эмулируем реалистичные ответы Mom Test
    if not responses or all(r.is_error for r in responses):
        print("   ℹ️ [Демо-режим] API ключ не подключён или квота исчерпана — используем калиброванные ответы:")
        responses = [
            InterviewResponse(
                persona_id=personas[0].id,
                persona_name=personas[0].name,
                persona_occupation=personas[0].occupation,
                problem_severity=8,
                solution_fit=8,
                willingness_to_pay=7,
                switching_likelihood=8,
                recommend_likelihood=9,
                main_concern="Будет ли резюме проходить строгие ATS-фильтры крупных работодателей?",
                desired_feature="Прямой экспорт в формат HeadHunter и PDF с ATS-разметкой",
                price_feedback="нормально",
                would_buy=True,
                raw_opinion="Трачу кучу времени на переделку резюме под каждую вакансию, за $7/мес готов брать.",
            ),
            InterviewResponse(
                persona_id=personas[1].id,
                persona_name=personas[1].name,
                persona_occupation=personas[1].occupation,
                problem_severity=6,
                solution_fit=7,
                willingness_to_pay=5,
                switching_likelihood=6,
                recommend_likelihood=7,
                main_concern="Боюсь, что сопроводительные письма будут звучать слишком шаблонно.",
                desired_feature="Тонкая настройка тональности письма (официальный, дружелюбный)",
                price_feedback="нормально",
                would_buy=True,
                raw_opinion="Интересно, если действительно экономит время перед собеседованиями.",
            ),
            InterviewResponse(
                persona_id=personas[2].id,
                persona_name=personas[2].name,
                persona_occupation=personas[2].occupation,
                problem_severity=4,
                solution_fit=4,
                willingness_to_pay=3,
                switching_likelihood=3,
                recommend_likelihood=4,
                main_concern="Ищу работу раз в 2 года, подписка мне не нужна.",
                desired_feature="Разовая оплата за 1 отклик вместо ежемесячной подписки",
                price_feedback="дорого",
                would_buy=False,
                raw_opinion="Мне проще один раз руками написать в Word.",
            ),
        ]

    for r in responses:
        status = "✅ Купит" if r.would_buy else "❌ Не купит"
        print(f"      • {r.persona_name}: Боль={r.problem_severity}/10, Fit={r.solution_fit}/10, WTP={r.willingness_to_pay}/10 | {status} ({r.price_feedback})")
    print()

    # 6. Агрегация CustDev
    aggregated = aggregate_interviews(responses)
    print("⏳ [5/7] Агрегация результатов Customer Discovery...")
    print(f"   • Готовность купить: {aggregated.pct_would_buy * 100:.0f}%")
    print(f"   • Средняя острота боли: {aggregated.avg_problem_severity:.1f} / 10")
    print(f"   • Средний Solution Fit: {aggregated.avg_solution_fit:.1f} / 10")
    print(f"   • Средняя готовность платить: {aggregated.avg_willingness_to_pay:.1f} / 10")
    print(f"   • Топ опасение: {aggregated.top_concerns[0] if aggregated.top_concerns else 'Нет'}\n")

    # 7. Юнит-экономика и Монте-Карло
    print("⏳ [6/7] Расчёт юнит-экономики и симуляция Монте-Карло (10 000 прогонов)...")
    product_type = detect_product_type(business_input)
    ue = calculate_unit_economics(business_input, bench, aggregated, product_type=product_type)
    mc = run_monte_carlo_simulation(business_input, ue, num_simulations=10000, num_months=24, product_type=product_type)
    print(f"   • Тип спроса продукта: '{mc.product_type}' (определяет когортный профиль оттока)")
    print(f"   • LTV: ${ue.ltv:.2f} | CAC (калиброванный): ${ue.cac:.2f}")
    print(f"   • LTV / CAC: {ue.ltv_cac_ratio:.2f}x (Отраслевая медиана: {ue.benchmark_ltv_cac.median}x)")
    print(f"   • Окупаемость CAC: {ue.cac_payback_months:.1f} мес.")
    print(f"   • Месячный Burn Rate: ${ue.monthly_burn_rate:,.0f} | Статический Runway: {ue.runway_months} мес.")
    print(f"   • Дно «кассовой ямы» (детерм.): ${ue.min_cash_balance:,.0f} (расход капитала: ${ue.peak_cash_drag:,.0f})")
    print(f"   • Точка безубыточности (детерм.): Месяц {ue.break_even_month if ue.break_even_month else 'Не достигнута'}")
    print(f"   • Вероятность банкротства за 24 мес (Монте-Карло, 10 000 прогонов): {mc.bankruptcy_probability:.1f}%")
    print(f"   • Траекторное дно кассовой ямы (P10 / P50 / P90): ${mc.pathwise_min_balance_p10:,.0f} / ${mc.pathwise_min_balance_p50:,.0f} / ${mc.pathwise_min_balance_p90:,.0f}")
    print(f"   • Капитал для 90% выживаемости (P10 стресс-тест): ${mc.stress_capital_p10:,.0f}")
    print(f"   • Медианная безубыточность (MC): Месяц {mc.median_break_even_month if mc.median_break_even_month else 'Не достигнута'}")
    print(f"   • Медианный MRR 24 мес: P10=${mc.mrr_p10[-1]:,.0f} | P50=${mc.mrr_p50[-1]:,.0f} | P90=${mc.mrr_p90[-1]:,.0f}\n")

    # 8. Инсайты и итоговый Score
    print("⏳ [7/7] Генерация аналитических рекомендаций и итоговый скоринг...")
    insights = generate_insights(business_input, aggregated, ue, mc, market_rep)
    score, subscores = calculate_overall_viability_score(aggregated, ue, mc)

    print("\n" + "═" * 70)
    print(f"   🏆 ИТОГОВЫЙ СКОРИНГ ЖИЗНЕСПОСОБНОСТИ: {score} / 100")
    print("═" * 70)
    print(f"   🎯 Валидация проблемы:    {subscores['problem_validation']:5.1f} / 40.0")
    print(f"   💡 Solution Fit & Спрос:  {subscores['solution_fit']:5.1f} / 35.0")
    print(f"   💰 Экономика и Cash Flow: {subscores['financial_viability']:5.1f} / 25.0")
    print(f"      └ Качество Unit Econ:  {subscores['_debug_s_unit_econ']:5.1f} / 10.0")
    print(f"      └ Достаточность кэша:  {subscores['_debug_s_cash_flow']:5.1f} /  8.0")
    print(f"      └ MC выживаемость:     {subscores['_debug_s_mc']:5.1f} /  7.0")
    if subscores['penalties'] > 0:
        print(f"   ⚠️  Структурные штрафы:   -{subscores['penalties']:.1f} б.")
    print()
    # Явное предупреждение о демо-режиме
    if not os.environ.get("OPENAI_API_KEY") or os.environ.get("OPENAI_API_KEY") in ("your_api_key_here", ""):
        print("   ⚠️  [ДЕМО] Данные интервью — синтетические (API ключ не подключён).")
        print("        Скоринг по блокам 1 и 2 отражает заложенные демо-веса,")
        print("        а не реальный рыночный спрос. Финансовый блок (3) — честный.")
    print()

    print("📋 КЛЮЧЕВЫЕ ЭКСПЕРТНЫЕ ИНСАЙТЫ:")
    for ins in insights:
        icon = "🔴" if ins.severity == "critical" else "🟠" if ins.severity == "warning" else "🟢" if ins.severity == "success" else "ℹ️"
        print(f"   {icon} [{ins.title}]")
        print(f"      {ins.message}")
        if ins.recommendation:
            print(f"      👉 Рекомендация: {ins.recommendation}")
        print()

    print("═" * 70)
    print("   🎉 ПРОБНЫЙ ПРОГОН УСПЕШНО ЗАВЕРШЕН БЕЗ ОШИБОК!")
    print("═" * 70 + "\n")


if __name__ == "__main__":
    main()
