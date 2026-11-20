"""
main.py — Streamlit UI для AI Customer Discovery Validator.
3 вкладки: Ввод идеи → AI Интервью → Рекомендации.
"""

import logging
import os
import tempfile
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

# ── Загружаем настройки из config.py ──────────────────────────
try:
    import config  # noqa: F401  (config.py применяет os.environ автоматически)
except ImportError:
    pass

# ── Загрузка .env как запасной вариант ─────────────────────────
if os.path.exists(".env"):
    with open(".env", "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip())

from aggregator import aggregate_interviews
from benchmarks import BENCHMARKS, get_benchmark, fetch_realtime_benchmarks
from insights import generate_insights
from interview_engine import run_all_interviews, get_llm_name, QuotaExceededError
from economics import calculate_unit_economics, calculate_overall_viability_score, detect_product_type
from monte_carlo import run_monte_carlo_simulation
from market_research import analyze_market_competitors
from models import (
    BusinessInput, BusinessType, ValidationReport, RevenueModel,
)
from personas import generate_personas
from usage_counter import consume_run, get_remaining_runs, current_count, MAX_DAILY_RUNS, next_reset_info
from feedback import send_feedback, is_email_configured

# ── Логирование ──────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
)
for _lib in ("ddgs", "duckduckgo_search", "httpx", "httpcore", "urllib3"):
    logging.getLogger(_lib).setLevel(logging.ERROR)

# ── Конфигурация страницы ────────────────────────────────────
st.set_page_config(
    page_title="AI Startup Validator",
    page_icon="🔬",
    layout="wide",
)

# ── Глобальный CSS — чистый академический стиль ──────────────
st.markdown("""
<style>
/* Убираем padding сверху */
.block-container { padding-top: 1.5rem; max-width: 1200px; }

/* Стильный Hero-блок */
.hero-card {
    background: linear-gradient(135deg, #f8fafc 0%, #edf2f7 100%);
    border: 1px solid #cbd5e1;
    border-radius: 12px;
    padding: 22px 26px;
    margin-bottom: 20px;
    box-shadow: 0 4px 15px rgba(0, 0, 0, 0.03);
}
.hero-badge {
    display: inline-block;
    background: #e0f2fe;
    color: #0369a1;
    font-size: 0.72rem;
    font-weight: 700;
    letter-spacing: 0.8px;
    text-transform: uppercase;
    padding: 3px 10px;
    border-radius: 9999px;
    margin-bottom: 8px;
    border: 1px solid #bae6fd;
}
.hero-title {
    font-size: 1.35rem;
    font-weight: 800;
    color: #0f172a;
    margin: 0 0 6px 0;
    letter-spacing: -0.3px;
}
.hero-desc {
    font-size: 0.88rem;
    color: #475569;
    line-height: 1.55;
    margin-bottom: 16px;
}
.hero-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
    gap: 12px;
}
.hero-pill {
    background: #ffffff;
    border: 1px solid #e2e8f0;
    border-radius: 8px;
    padding: 12px 14px;
    box-shadow: 0 1px 3px rgba(0,0,0,0.02);
}
.hero-pill-num {
    font-weight: 800;
    color: #2563eb;
    font-size: 0.85rem;
    margin-bottom: 4px;
}
.hero-pill-title {
    font-weight: 700;
    color: #1e293b;
    font-size: 0.82rem;
    margin-bottom: 2px;
}
.hero-pill-sub {
    font-size: 0.74rem;
    color: #64748b;
    line-height: 1.35;
}

/* Баннер "Анализ завершён" */
.done-banner {
    background: linear-gradient(135deg, #ecfdf5 0%, #d1fae5 100%);
    border: 1.5px solid #34d399;
    border-radius: 10px;
    padding: 14px 20px;
    margin-bottom: 1.25rem;
    display: flex;
    align-items: center;
    gap: 14px;
    box-shadow: 0 4px 12px rgba(16, 185, 129, 0.08);
}
.done-banner-icon {
    font-size: 1.3rem;
    background: #10b981;
    color: white;
    width: 28px;
    height: 28px;
    border-radius: 50%;
    display: flex;
    align-items: center;
    justify-content: center;
    font-weight: bold;
}
.done-banner-text { font-size: 0.95rem; font-weight: 700; color: #065f46; }
.done-banner-sub  { font-size: 0.8rem; color: #047857; font-weight: 500; }

/* Пресеты */
.preset-box {
    background: #ffffff;
    border: 1px solid #e2e8f0;
    border-radius: 8px;
    padding: 10px 14px;
    margin-bottom: 16px;
}

/* Прогресс-шаги */
.step-row { display:flex; align-items:center; gap:10px; margin:7px 0; }
.step-dot-done    { width:10px;height:10px;border-radius:50%;background:#10b981;flex-shrink:0; }
.step-dot-active  { width:10px;height:10px;border-radius:50%;background:#2563eb;flex-shrink:0;animation:pulse 1s infinite; }
.step-dot-pending { width:10px;height:10px;border-radius:50%;background:#cbd5e1;flex-shrink:0; }
.step-text-done    { font-size:0.85rem;color:#065f46;font-weight:500; }
.step-text-active  { font-size:0.85rem;color:#1d4ed8;font-weight:700; }
.step-text-pending { font-size:0.85rem;color:#94a3b8; }
@keyframes pulse { 0%,100%{opacity:1} 50%{opacity:0.35} }

/* Шапка */
.app-header {
    border-bottom: 2px solid #e0e0e0;
    padding-bottom: 0.75rem;
    margin-bottom: 1rem;
}
.app-title {
    font-size: 1.6rem;
    font-weight: 700;
    color: #1a1a2e;
    letter-spacing: -0.5px;
    margin: 0;
}
.app-subtitle {
    font-size: 0.85rem;
    color: #6b7280;
    margin: 0;
}

/* Метки секций */
.section-label {
    font-size: 0.7rem;
    font-weight: 600;
    letter-spacing: 1px;
    text-transform: uppercase;
    color: #9ca3af;
    margin-bottom: 4px;
}

/* Карточка скоринга */
.score-card {
    background: #f8f9fa;
    border: 1px solid #e9ecef;
    border-radius: 8px;
    padding: 1.25rem 1.5rem;
    margin-bottom: 1rem;
}
.score-number {
    font-size: 3.5rem;
    font-weight: 800;
    line-height: 1;
    color: #1a1a2e;
}
.score-denom {
    font-size: 1.2rem;
    color: #9ca3af;
    font-weight: 400;
}

/* Вердикт-бейдж */
.verdict-critical { background:#fee2e2; color:#991b1b; padding:6px 14px; border-radius:20px; font-weight:600; font-size:0.85rem; display:inline-block; }
.verdict-warning  { background:#fef3c7; color:#92400e; padding:6px 14px; border-radius:20px; font-weight:600; font-size:0.85rem; display:inline-block; }
.verdict-moderate { background:#dbeafe; color:#1e40af; padding:6px 14px; border-radius:20px; font-weight:600; font-size:0.85rem; display:inline-block; }
.verdict-good     { background:#d1fae5; color:#065f46; padding:6px 14px; border-radius:20px; font-weight:600; font-size:0.85rem; display:inline-block; }

/* Метрика-карточка */
.metric-row { display:flex; gap:12px; flex-wrap:wrap; margin-bottom:1rem; }
.metric-box {
    flex:1; min-width:120px;
    background:#fff; border:1px solid #e5e7eb;
    border-radius:8px; padding:12px 16px;
}
.metric-box-label { font-size:0.7rem; color:#6b7280; text-transform:uppercase; letter-spacing:0.5px; }
.metric-box-value { font-size:1.4rem; font-weight:700; color:#111827; }

/* Диалог интервью */
.phase-header {
    font-size:0.72rem; font-weight:600; letter-spacing:0.8px;
    text-transform:uppercase; color:#6b7280;
    border-top: 1px solid #e5e7eb;
    padding-top: 10px; margin: 14px 0 8px 0;
}
.chat-q { color:#374151; font-size:0.88rem; margin:4px 0 2px 16px; font-style:italic; }
.chat-a {
    background:#f9fafb; border-left:3px solid #d1d5db;
    padding:8px 14px; border-radius:0 6px 6px 0;
    margin:2px 0 10px 16px; font-size:0.9rem; color:#111827;
}

/* Убираем стандартные иконки streamlit-метрик */
[data-testid="stMetricDelta"] svg { display:none; }
</style>
""", unsafe_allow_html=True)

# ── Шапка ────────────────────────────────────────────────────
st.markdown("""
<div class="app-header">
  <p class="app-title">AI Startup Validator</p>
  <p class="app-subtitle">Инструмент предварительной валидации бизнес-идей · Mom Test · Lean Startup</p>
</div>
""", unsafe_allow_html=True)

# Счётчик запусков
_remaining = get_remaining_runs()
_limit_reached = _remaining == 0
if _limit_reached:
    _reset_time = next_reset_info()
    st.error(f"Дневной лимит исчерпан — {MAX_DAILY_RUNS}/{MAX_DAILY_RUNS} запусков использовано. Лимит сбросится через **{_reset_time}**")
elif _remaining <= 3:
    st.warning(f"Осталось запусков сегодня: **{_remaining}** из {MAX_DAILY_RUNS}")
else:
    st.caption(f"Осталось запусков сегодня: {_remaining} из {MAX_DAILY_RUNS}")

# ═══════════════════════════════════════════════════════════════
# Боковая панель
# ═══════════════════════════════════════════════════════════════

with st.sidebar:
    st.markdown("### О методологии")
    st.markdown("""
**Трехконтурная валидация:**
1. **The Mom Test (Роб Фитцпатрик)**:  
   Двухфазные интервью. Вопросы о прошлом опыте и фактических расходах, исключающие ложную вежливость.
2. **Юнит-экономика и когорты**:  
   Расчёт метрик LTV, CAC, Runway, точки безубыточности и риска Churn Cliff.
3. **Симуляция Монте-Карло**:  
   10 000 итераций вероятностной траектории роста MRR и оценка риска кассовой ямы на 24 месяца.
    """)

    st.divider()

    st.markdown("### Шкала жизнеспособности")
    st.markdown("""
- **65 – 100 б.** · Перспективная идея (низкий риск, целесообразен запуск MVP)
- **50 – 64 б.** · Умеренный риск (требуются доработки гипотез)
- **0 – 49 б.** · Критический риск (рекомендован Pivot модели)
    """)

    st.divider()

    st.markdown("### О проекте")
    st.caption(
        "Научно-исследовательский проект.\n\n"
        "Конкурс научных соревнований «Дарын».\n\n"
        "Секция: Прикладная информатика и экономика."
    )

    with st.expander("Отраслевые бенчмарки"):
        st.caption("Источники: World Bank API, отраслевые медианы 2025–2026.")
        _rt_info = st.session_state.get("rt_bench_info", "Синхронизируются при запуске валидации.")
        st.caption(_rt_info)
        if st.button("Синхронизировать бенчмарки", use_container_width=True):
            _api_key = os.environ.get("OPENAI_API_KEY", "")
            if _api_key and _api_key != "your_api_key_here":
                with st.spinner("Синхронизация с макроэкономическими базами..."):
                    _bt = st.session_state.get("_last_bt", BusinessType.MARKETPLACE)
                    _ct = st.session_state.get("_last_country", "kazakhstan")
                    _desc = st.session_state.get("_last_desc", "")
                    bench_rt, rt_info = fetch_realtime_benchmarks(_bt, _ct, _desc)
                    st.session_state["realtime_benchmark"] = bench_rt
                    st.session_state["rt_bench_info"] = rt_info
                st.rerun()

# ═══════════════════════════════════════════════════════════════
# Инициализация session_state
# ═══════════════════════════════════════════════════════════════
if "report" not in st.session_state:
    st.session_state.report = None

# ── Авто-переключение на вкладку "Результаты" после анализа ──
if st.session_state.get("_go_to_results"):
    st.session_state["_go_to_results"] = False
    # JS: находим кнопку вкладки по тексту и кликаем на неё
    import streamlit.components.v1 as _components
    _components.html("""
    <script>
    setTimeout(function() {
        var tabs = window.parent.document.querySelectorAll('button[role="tab"]');
        for (var i = 0; i < tabs.length; i++) {
            if (tabs[i].innerText.includes('Результаты')) {
                tabs[i].click();
                break;
            }
        }
    }, 300);
    </script>
    """, height=0)

# ── Баннер "Анализ завершён" ──────────────────────────────────
if st.session_state.get("_show_done_banner") and st.session_state.report is not None:
    _score = int(st.session_state.report.overall_score)
    st.markdown(f"""
    <div class="done-banner">
        <div class="done-banner-icon">✓</div>
        <div>
            <div class="done-banner-text">Анализ завершён — Overall Score: {_score}/100</div>
            <div class="done-banner-sub">Результаты доступны на вкладке «Результаты и оценка»</div>
        </div>
    </div>
    """, unsafe_allow_html=True)

# ═══════════════════════════════════════════════════════════════
#  ВКЛАДКИ
# ═══════════════════════════════════════════════════════════════

tab1, tab2, tab3, tab4 = st.tabs([
    "Ваша идея",
    "Customer Discovery",
    "Результаты и оценка",
    "Оставить отзыв",
])


# ═══════════════════════════════════════════════════════════════
#  TAB 1 — Ввод идеи
# ═══════════════════════════════════════════════════════════════

with tab1:
    # ── Стильный презентационный Hero-блок ──
    st.markdown("""
    <div class="hero-card">
      <div class="hero-badge">Lean Startup & Mom Test Framework</div>
      <div class="hero-title">AI-симуляция предварительной валидации бизнес-идей</div>
      <div class="hero-desc">
        Комплексная проверка гипотез через глубинное интервьюирование синтетических клиентов, 
        стресс-тестирование юнит-экономики и 10 000 симуляций Монте-Карло на горизонте 24 месяцев.
      </div>
      <div class="hero-grid">
        <div class="hero-pill">
          <div class="hero-pill-num">01 · CustDev без лести</div>
          <div class="hero-pill-title">Методология Mom Test</div>
          <div class="hero-pill-sub">Исследование реального прошлого опыта и трат респондентов до презентации решения.</div>
        </div>
        <div class="hero-pill">
          <div class="hero-pill-num">02 · Рыночные реалии</div>
          <div class="hero-pill-title">Адаптация под рынок РК</div>
          <div class="hero-pill-sub">Интеграция макроданных World Bank и локальных платежных моделей (тенге / доллар).</div>
        </div>
        <div class="hero-pill">
          <div class="hero-pill-num">03 · Риск-менеджмент</div>
          <div class="hero-pill-title">10 000 сценариев Монте-Карло</div>
          <div class="hero-pill-sub">Прогнозирование кассовых ям, выживаемости и динамики ежемесячной выручки (MRR).</div>
        </div>
      </div>
    </div>
    """, unsafe_allow_html=True)

    # ── Демо-кейсы для быстрой демонстрации (в 1 клик для жюри/гостей) ──
    if "_demo_preset" in st.session_state:
        _d = st.session_state.pop("_demo_preset")
        if _d == "tutornow":
            st.session_state["_f_name"] = "TutorNow"
            st.session_state["_f_desc"] = "Маркетплейс проверенных онлайн-репетиторов по школьным предметам и подготовке к ЕНТ/IELTS с гарантией возврата средств за первое занятие."
            st.session_state["_f_aud"] = "Родители школьников 8-11 классов и абитуриенты в Казахстане"
            st.session_state["_f_bt"] = BusinessType.EDTECH
            st.session_state["_f_rm"] = RevenueModel.COMMISSION
            st.session_state["_f_deal"] = 4500.0
            st.session_state["_f_deals_m"] = 5.0
            st.session_state["_f_comm"] = 15
            st.session_state["_f_cap"] = 8000.0
            st.session_state["_f_mkt"] = 400.0
            st.session_state["_f_ops"] = 250.0
            st.session_state["_f_tam"] = 120000
        elif _d == "qazaqcraft":
            st.session_state["_f_name"] = "QazaqCraft"
            st.session_state["_f_desc"] = "Маркетплейс изделий ручной работы, национальной сувенирной продукции и ремесленных товаров Казахстана с быстрой доставкой по СНГ."
            st.session_state["_f_aud"] = "Туристы, корпоративные клиенты и ценители аутентичных изделий"
            st.session_state["_f_bt"] = BusinessType.MARKETPLACE
            st.session_state["_f_rm"] = RevenueModel.COMMISSION
            st.session_state["_f_deal"] = 8500.0
            st.session_state["_f_deals_m"] = 4.0
            st.session_state["_f_comm"] = 12
            st.session_state["_f_cap"] = 10000.0
            st.session_state["_f_mkt"] = 500.0
            st.session_state["_f_ops"] = 350.0
            st.session_state["_f_tam"] = 90000
        elif _d == "docflow":
            st.session_state["_f_name"] = "DocFlow AI"
            st.session_state["_f_desc"] = "SaaS платформа автоматической проверки договоров на юридические риски и соответствие законодательству РК с помощью ИИ."
            st.session_state["_f_aud"] = "Юристы, бухгалтеры и руководители малого и среднего бизнеса"
            st.session_state["_f_bt"] = BusinessType.SAAS_B2B
            st.session_state["_f_rm"] = RevenueModel.SUBSCRIPTION
            st.session_state["_f_price"] = 25.0
            st.session_state["_f_cap"] = 7000.0
            st.session_state["_f_mkt"] = 350.0
            st.session_state["_f_ops"] = 200.0
            st.session_state["_f_tam"] = 65000

    st.markdown("**Демонстрационные сценарии:**")
    d_col1, d_col2, d_col3 = st.columns(3)
    if d_col1.button("TutorNow · EdTech маркетплейс", use_container_width=True):
        st.session_state["_demo_preset"] = "tutornow"
        st.rerun()
    if d_col2.button("QazaqCraft · Маркетплейс РК", use_container_width=True):
        st.session_state["_demo_preset"] = "qazaqcraft"
        st.rerun()
    if d_col3.button("DocFlow AI · B2B SaaS", use_container_width=True):
        st.session_state["_demo_preset"] = "docflow"
        st.rerun()

    st.markdown("<div style='height: 10px'></div>", unsafe_allow_html=True)
    st.subheader("Параметры бизнес-идеи")

    col_left, col_right = st.columns([3, 2])

    with col_left:
        name = st.text_input(
            "Название продукта",
            value=st.session_state.get("_f_name", ""),
            placeholder="Например: QuickCV — AI для резюме",
        )
        description = st.text_area(
            "Описание идеи",
            value=st.session_state.get("_f_desc", ""),
            height=100,
            placeholder="Что делает продукт? Какую проблему решает?",
        )
        target_audience = st.text_input(
            "Целевая аудитория",
            value=st.session_state.get("_f_aud", ""),
            placeholder="Кто ваш клиент?",
        )

        bt_options = list(BusinessType)
        bt_display = [BENCHMARKS[bt].display_name for bt in bt_options]
        default_bt = st.session_state.get("_f_bt", BusinessType.MARKETPLACE)
        default_bt_idx = bt_options.index(default_bt) if default_bt in bt_options else 0
        bt_index = st.selectbox(
            "Тип бизнеса",
            options=range(len(bt_options)),
            index=default_bt_idx,
            format_func=lambda i: bt_display[i],
            help="Gig Economy / Freelance Platform — платформа комиссионного типа (как Upwork, Fiverr, YouDo)",
        )
        business_type = bt_options[bt_index]
        _gig_selected = business_type == BusinessType.GIG_ECONOMY
        if _gig_selected:
            st.info("Gig Economy — рекомендуемая модель монетизации: **Комиссия со сделок**.")

        country = st.selectbox(
            "Страна",
            options=["kazakhstan", "russia", "usa", "global"],
            format_func=lambda c: {
                "kazakhstan": "Казахстан",
                "russia": "Россия",
                "usa": "США",
                "global": "Глобальный рынок",
            }.get(c, c),
        )

        language = st.selectbox(
            "Язык интервью",
            options=["Русский", "Қазақша"],
        )

        st.session_state["_last_bt"] = business_type
        st.session_state["_last_country"] = country
        st.session_state["_last_desc"] = description

    with col_right:
        st.markdown("**Модель монетизации**")
        rm_options = list(RevenueModel)
        default_rm = st.session_state.get("_f_rm", RevenueModel.COMMISSION if _gig_selected else RevenueModel.SUBSCRIPTION)
        default_rm_idx = rm_options.index(default_rm) if default_rm in rm_options else (2 if _gig_selected else 0)
        revenue_model_choice = st.radio(
            "Как платит пользователь?",
            options=rm_options,
            format_func=lambda m: {
                RevenueModel.SUBSCRIPTION: "Ежемесячная подписка",
                RevenueModel.PAY_PER_USE:  "Оплата за использование",
                RevenueModel.COMMISSION:   "Комиссия со сделок (Gig / Marketplace)",
            }[m],
            index=default_rm_idx,
        )

        price = 10.0
        price_per_use = 5.0
        avg_uses_per_month = 5.0
        avg_deal_value = 1500.0
        commission_rate = 0.10
        avg_deals_per_month = 4.0
        currency_to_usd = 0.0022

        if revenue_model_choice == RevenueModel.SUBSCRIPTION:
            price = st.number_input(
                "Цена подписки ($/мес)",
                min_value=0.1, step=1.0, value=float(st.session_state.get("_f_price", 10.0)),
            )
            st.caption(f"Доход на пользователя в месяц: **${price:.2f}**")

        elif revenue_model_choice == RevenueModel.PAY_PER_USE:
            price_per_use = st.number_input(
                "Цена за одно использование ($)",
                min_value=0.01, step=0.5, value=float(st.session_state.get("_f_price_use", 5.0)),
            )
            avg_uses_per_month = st.number_input(
                "Среднее использований в месяц (1 пользователь)",
                min_value=1.0, step=1.0, value=float(st.session_state.get("_f_uses_m", 5.0)),
            )
            eff = price_per_use * avg_uses_per_month
            price = price_per_use
            st.caption(f"Доход на пользователя в месяц: **${eff:.2f}** ({avg_uses_per_month:.0f} × ${price_per_use:.2f})")

        else:
            if _gig_selected:
                st.caption("Укажите среднюю стоимость заказа, % платформы и активность исполнителя")
            col_c1, col_c2 = st.columns(2)
            with col_c1:
                _deal_label = "Средняя стоимость заказа (₸)" if _gig_selected else "Средний чек сделки (₸)"
                avg_deal_value = st.number_input(
                    _deal_label,
                    min_value=100.0, step=100.0, value=float(st.session_state.get("_f_deal", 5000.0 if _gig_selected else 1500.0)),
                )
                _deals_label = "Заказов/мес (на 1 исполнителя)" if _gig_selected else "Сделок/мес/пользователь"
                avg_deals_per_month = st.number_input(
                    _deals_label,
                    min_value=1.0, step=1.0, value=float(st.session_state.get("_f_deals_m", 6.0 if _gig_selected else 4.0)),
                )
            with col_c2:
                commission_pct = st.slider(
                    "% комиссии платформы",
                    min_value=1, max_value=35, value=int(st.session_state.get("_f_comm", 15 if _gig_selected else 10)), step=1,
                    help="Upwork берёт 20%, Fiverr ~31%, YouDo ~15%",
                )
                commission_rate = commission_pct / 100.0
                currency_to_usd = st.number_input(
                    "Курс (1 ₸ = ? $)",
                    min_value=0.0001, step=0.0001,
                    value=0.0022, format="%.4f",
                )

            earn_platform = avg_deal_value * commission_rate
            earn_worker = avg_deal_value - earn_platform
            eff_usd = avg_deal_value * currency_to_usd * commission_rate * avg_deals_per_month
            _actor = "исполнитель" if _gig_selected else "продавец"
            st.info(
                f"Пример: заказ {avg_deal_value:.0f}₸ → "
                f"{_actor} **{earn_worker:.0f}₸**, платформа **{earn_platform:.0f}₸** ({commission_pct}%)  \n"
                f"Доход платформы на исполнителя в месяц: ≈ **${eff_usd:.2f}**"
            )

        st.markdown("---")
        st.markdown("**Финансовые параметры**")
        initial_capital = st.number_input(
            "Стартовый капитал ($)",
            min_value=0.0, step=1000.0, value=float(st.session_state.get("_f_cap", 10000.0)),
        )
        monthly_marketing_budget = st.number_input(
            "Маркетинговый бюджет ($/мес)",
            min_value=0.0, step=100.0, value=float(st.session_state.get("_f_mkt", 500.0)),
        )
        monthly_operating_costs = st.number_input(
            "Операционные расходы ($/мес)",
            min_value=0.0, step=100.0, value=float(st.session_state.get("_f_ops", 300.0)),
        )
        market_size_estimate = st.number_input(
            "TAM (потенциальных клиентов)",
            min_value=1000, step=10000, value=int(st.session_state.get("_f_tam", 100000)),
        )

        num_personas = st.number_input(
            "Количество респондентов",
            min_value=1, max_value=10, value=5, step=1,
            help="Рекомендуем 5–7 для быстрого теста.",
        )
        st.caption(f"Будет выполнено ~{int(num_personas) + 1} API-запросов")

        active_bench = st.session_state.get("realtime_benchmark") or get_benchmark(business_type)
        bench_is_rt = "realtime_benchmark" in st.session_state

        st.markdown("---")
        st.markdown(
            f"**Бенчмарк: {active_bench.display_name}** "
            + ("· актуальный" if bench_is_rt else "· статичный (2025)")
        )
        st.caption(f"Провал за 12 мес: {active_bench.failure_rate_12_months:.0%}")
        st.caption(
            f"Конверсия: {active_bench.conversion_trial_to_paid.low:.0%} – "
            f"{active_bench.conversion_trial_to_paid.high:.0%}"
        )
        st.caption(
            f"Churn: {active_bench.monthly_churn.low:.0%} – "
            f"{active_bench.monthly_churn.high:.0%} / мес"
        )
        st.caption(f"Источник: {active_bench.source}")

    st.divider()

    col1, col2 = st.columns([3, 1])
    with col1:
        _btn_disabled = _limit_reached
        _btn_label = "Запустить валидацию" if not _btn_disabled else f"Лимит исчерпан — обновится через {next_reset_info()}"
        start_btn = st.button(
            _btn_label,
            type="primary",
            use_container_width=True,
            disabled=_btn_disabled,
        )
    with col2:
        if st.button("Очистить", type="secondary", use_container_width=True):
            st.session_state.clear()
            st.rerun()

    if start_btn:
        if get_remaining_runs() == 0:
            st.error(
                f"Дневной лимит исчерпан — сегодня запущено **{MAX_DAILY_RUNS}** симуляций.  \n"
                f"Лимит сбросится автоматически в полночь."
            )
            st.stop()

        _api_key_check = os.environ.get("OPENAI_API_KEY", "")
        if not _api_key_check or _api_key_check in ("вставьте_ваш_ключ_здесь", "your_api_key_here", ""):
            st.error("API ключ не настроен. Без ключа симуляция невозможна.")
            st.stop()

        errors = []

        def _is_gibberish(text: str) -> bool:
            t = text.strip()
            if not t:
                return True
            unique_chars = len(set(t.lower()))
            if unique_chars < 5 and len(t) > 10:
                return True
            if " " not in t and len(t) > 15:
                return True
            most_common_ratio = max(t.lower().count(c) for c in set(t.lower())) / len(t)
            if most_common_ratio > 0.4 and len(t) > 10:
                return True
            return False

        if not description.strip() or len(description.strip()) < 20:
            errors.append("**Описание идеи** — опишите подробнее (минимум 20 символов).")
        elif _is_gibberish(description):
            errors.append("**Описание идеи** — похоже на случайный ввод.")

        if not target_audience.strip() or len(target_audience.strip()) < 5:
            errors.append("**Целевая аудитория** — укажите кто ваш клиент.")
        elif _is_gibberish(target_audience):
            errors.append("**Целевая аудитория** — похоже на случайный ввод.")

        if not name.strip() or len(name.strip()) < 2:
            errors.append("**Название продукта** — введите название.")
        elif _is_gibberish(name):
            errors.append("**Название продукта** — похоже на случайный ввод.")

        if errors:
            for e in errors:
                st.error(e)
            st.stop()

        if not consume_run():
            st.error(
                f"Дневной лимит исчерпан — использовано **{MAX_DAILY_RUNS}** симуляций.  \n"
                f"Лимит сбросится в полночь."
            )
            st.stop()

        st.caption(f"Запуск {current_count()}/{MAX_DAILY_RUNS} на сегодня")

        business_input = BusinessInput(
            name=name,
            description=description,
            business_type=business_type,
            target_audience=target_audience,
            country=country,
            num_personas=num_personas,
            language=language,
            revenue_model=revenue_model_choice,
            price=price,
            price_per_use=price_per_use,
            avg_uses_per_month=avg_uses_per_month,
            avg_deal_value=avg_deal_value,
            commission_rate=commission_rate,
            avg_deals_per_month=avg_deals_per_month,
            currency_to_usd=currency_to_usd,
            initial_capital=initial_capital,
            monthly_marketing_budget=monthly_marketing_budget,
            monthly_operating_costs=monthly_operating_costs,
            market_size_estimate=int(market_size_estimate),
        )

        try:
            # ── Прогресс-шаги ─────────────────────────────────────
            STEPS = [
                "Загрузка актуальных бенчмарков",
                "Генерация персон",
                "Анализ конкурентов",
                "AI-интервью (Mom Test)",
                "Расчёт экономики и Монте-Карло",
            ]

            def _progress_ui(current: int):
                """Показывает прогресс-шаги (current = индекс активного шага)."""
                html = "<div style='margin:12px 0 16px 0'>"
                for i, label in enumerate(STEPS):
                    if i < current:
                        html += f"<div class='step-row'><div class='step-dot-done'></div><div class='step-text-done'>✓ {label}</div></div>"
                    elif i == current:
                        html += f"<div class='step-row'><div class='step-dot-active'></div><div class='step-text-active'>{label}...</div></div>"
                    else:
                        html += f"<div class='step-row'><div class='step-dot-pending'></div><div class='step-text-pending'>{label}</div></div>"
                html += "</div>"
                return html

            _progress_placeholder = st.empty()

            # Шаг 0: Бенчмарки
            _progress_placeholder.markdown(_progress_ui(0), unsafe_allow_html=True)
            _api_ready = bool(os.environ.get("OPENAI_API_KEY", ""))
            if _api_ready:
                _bench_rt, _bench_src = fetch_realtime_benchmarks(
                    business_input.business_type,
                    business_input.country,
                    business_input.description,
                )
                st.session_state["realtime_benchmark"] = _bench_rt
                st.session_state["rt_bench_info"] = _bench_src

            # Шаг 1: Персоны
            _progress_placeholder.markdown(_progress_ui(1), unsafe_allow_html=True)
            from personas import _detect_age_profile
            _age_profile = _detect_age_profile(business_input)
            personas = generate_personas(business_input, count=business_input.num_personas)

            # Шаг 2: Конкуренты
            _progress_placeholder.markdown(_progress_ui(2), unsafe_allow_html=True)
            market_research_report = analyze_market_competitors(business_input)

            # Шаг 3: Интервью
            _pool_check = config.get_pool_status()
            if _pool_check["total_keys"] == 0:
                st.error("API ключи не настроены. Добавьте ключи через Streamlit Secrets.")
                st.stop()
            if _pool_check["alive_keys"] == 0:
                st.error("Все API ключи исчерпали дневной лимит. Попробуйте завтра.")
                st.stop()

            _age_label_map = {"youth": "школьники 12–17 лет", "student": "студенты 17–25 лет", "adult": "взрослые 18–55 лет"}
            _progress_placeholder.markdown(
                _progress_ui(3) +
                f"<div style='font-size:0.8rem;color:#6b7280;margin-top:4px'>"
                f"Опрашиваем {business_input.num_personas} персон · "
                f"~{business_input.num_personas * 8}–{business_input.num_personas * 15} сек · "
                f"Аудитория: {_age_label_map.get(_age_profile['label'], '?')}</div>",
                unsafe_allow_html=True,
            )
            responses = run_all_interviews(
                personas, business_input, market_context=market_research_report.summary,
                age_profile=_age_profile
            )
            aggregated = aggregate_interviews(responses)

            # Шаг 4: Экономика
            _progress_placeholder.markdown(_progress_ui(4), unsafe_allow_html=True)
            active_bench = st.session_state.get("realtime_benchmark") or get_benchmark(business_input.business_type)
            _product_type = detect_product_type(business_input)
            unit_economics = calculate_unit_economics(
                business_input, active_bench, aggregated, product_type=_product_type
            )
            monte_carlo_res = run_monte_carlo_simulation(
                business_input, unit_economics, product_type=_product_type
            )

            insights = generate_insights(
                business_input=business_input,
                interview_results=aggregated,
                unit_economics=unit_economics,
                monte_carlo_results=monte_carlo_res,
                market_research=market_research_report,
            )

            score, subscores = calculate_overall_viability_score(
                interview_results=aggregated,
                unit_economics=unit_economics,
                monte_carlo_results=monte_carlo_res,
            )
            st.session_state["subscores"] = subscores

            # Скрываем прогресс-шаги — показываем "готово"
            _progress_placeholder.empty()

            if aggregated.fallback_count > 0:
                valid_count = aggregated.total_personas - aggregated.fallback_count
                st.warning(
                    f"{aggregated.fallback_count} из {len(personas)} интервью завершились ошибкой LLM. "
                    f"Метрики рассчитаны по {valid_count} валидным ответам."
                )

            st.session_state.report = ValidationReport(
                business_input=business_input,
                interview_results=aggregated,
                monte_carlo_results=monte_carlo_res,
                unit_economics=unit_economics,
                market_research=market_research_report,
                insights=insights,
                overall_score=score,
            )

            # Флаги для авто-перехода и баннера
            st.session_state["_go_to_results"] = True
            st.session_state["_show_done_banner"] = True

            st.rerun()

        except QuotaExceededError as qe:
            st.error(
                f"API ключ исчерпал лимит.  \n{qe}  \n"
                f"Попробуйте завтра или обратитесь к организатору."
            )
            st.stop()

        except Exception as e:
            err_str = str(e)
            quota_kw = ("quota", "exceeded", "billing", "resource_exhausted", "insufficient_quota")
            if any(kw in err_str.lower() for kw in quota_kw):
                st.error(f"API ключ исчерпал лимит токенов. Попробуйте завтра.  \n_{err_str[:200]}_")
            else:
                st.error(f"Ошибка во время валидации: {e}")
                st.exception(e)


# ═══════════════════════════════════════════════════════════════
#  TAB 2 — AI Customer Discovery
# ═══════════════════════════════════════════════════════════════

with tab2:
    st.header("Customer Discovery — результаты интервью")
    st.caption("Глубинные двухфазные интервью с репрезентативной выборкой синтетических клиентов")

    report: ValidationReport = st.session_state.report

    if report is None or report.interview_results is None:
        st.info("Заполните данные и нажмите «Запустить валидацию» на первой вкладке.")
        st.stop()

    ir = report.interview_results

    if ir.fallback_count > 0:
        valid_count = ir.total_personas - ir.fallback_count
        st.warning(
            f"Внимание: {ir.fallback_count} из {ir.total_personas} интервью завершились ошибкой LLM. "
            f"Метрики рассчитаны по {valid_count} валидным ответам."
        )

    # ── Сводные метрики ───────────────────────────────────────
    st.subheader("Сводка")
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Острота проблемы", f"{ir.avg_problem_severity:.1f} / 10")
    with col2:
        st.metric("Готовы купить", f"{ir.pct_would_buy * 100:.0f}%")
    with col3:
        st.metric("Рекомендация (ср.)", f"{ir.avg_nps_score:.1f} / 10")
    with col4:
        st.metric("Solution Fit", f"{ir.avg_solution_fit:.1f} / 10")

    st.divider()

    col_pie, col_concerns = st.columns([1, 1])

    with col_pie:
        st.markdown("**Ценовое восприятие**")
        fig_pie = go.Figure(data=[go.Pie(
            labels=["Дорого", "Нормально", "Дёшево"],
            values=[ir.pct_price_too_high, ir.pct_price_ok, ir.pct_price_too_low],
            marker_colors=["#e74c3c", "#2ecc71", "#3498db"],
            hole=0.4,
        )])
        fig_pie.update_layout(
            height=280,
            margin=dict(t=10, b=10, l=10, r=10),
            showlegend=True,
            font=dict(family="sans-serif"),
        )
        st.plotly_chart(fig_pie, use_container_width=True)

    with col_concerns:
        st.markdown("**Топ-3 опасения**")
        if ir.top_concerns:
            for concern in ir.top_concerns:
                st.warning(concern)
        else:
            st.caption("Нет данных")

        st.markdown("**Топ-3 желаемые функции**")
        if ir.top_desired_features:
            for feature in ir.top_desired_features:
                st.info(feature)
        else:
            st.caption("Нет данных")

    # ── Детальные ответы персон ───────────────────────────────
    st.divider()
    st.subheader("Ответы персон")

    _phase_labels = {1: "Фаза 1 — До знакомства с продуктом", 2: "Фаза 2 — После знакомства с продуктом"}

    for resp in ir.responses:
        buy_label = "купит" if resp.would_buy else "не купит"
        err_label = " · ошибка API" if getattr(resp, "is_error", False) else ""
        with st.expander(f"{resp.persona_name} · {resp.persona_occupation} · {buy_label}{err_label}"):

            if getattr(resp, "is_error", False):
                st.error(
                    f"Ответ не получен от LLM.  \n{resp.main_concern}  \n"
                    f"Метрики для этой персоны недостоверны."
                )
                continue

            if resp.conversation:
                current_phase = None
                for turn in resp.conversation:
                    phase = turn.get("phase", 1)
                    q     = turn.get("question", "")
                    a     = turn.get("answer", "")

                    if phase != current_phase:
                        current_phase = phase
                        label = _phase_labels.get(phase, f"Фаза {phase}")
                        st.markdown(
                            f"<div class='phase-header'>{label}</div>",
                            unsafe_allow_html=True,
                        )

                    if q:
                        st.markdown(
                            f"<div class='chat-q'>— {q}</div>",
                            unsafe_allow_html=True,
                        )
                    if a:
                        st.markdown(
                            f"<div class='chat-a'>{a}</div>",
                            unsafe_allow_html=True,
                        )
                st.divider()
            elif resp.raw_opinion:
                st.markdown(f"*«{resp.raw_opinion}»*")
                st.divider()

            st.caption("Итоговые оценки")
            cols = st.columns(5)
            metrics = [
                ("Острота проблемы", resp.problem_severity),
                ("Solution Fit",     resp.solution_fit),
                ("Готовность платить", resp.willingness_to_pay),
                ("Вероятность перехода", resp.switching_likelihood),
                ("Рекомендует",      resp.recommend_likelihood),
            ]
            for col, (label, val) in zip(cols, metrics):
                with col:
                    st.metric(label, f"{val}/10")
                    st.progress(val / 10)

            st.markdown(
                f"**Цена:** {resp.price_feedback} &nbsp;&nbsp; "
                f"**Купит:** {'да' if resp.would_buy else 'нет'}"
            )
            if resp.main_concern:
                st.markdown(f"**Опасение:** {resp.main_concern}")
            if resp.desired_feature:
                st.markdown(f"**Желаемая функция:** {resp.desired_feature}")


# ═══════════════════════════════════════════════════════════════
#  TAB 3 — Результаты и оценка
# ═══════════════════════════════════════════════════════════════

with tab3:
    report = st.session_state.report

    if report is None:
        st.info("Сначала запустите валидацию на вкладке «Ваша идея»")
        st.stop()

    # ── Overall Viability Score ───────────────────────────────
    st.subheader("Общая оценка жизнеспособности (Overall Viability Score)")

    score = int(report.overall_score)
    col_score1, col_score2 = st.columns([1, 2])

    with col_score1:
        # Определяем вердикт
        if score <= 25:
            verdict_class = "verdict-critical"
            verdict_text  = "Критический риск — требуется пересмотр"
        elif score <= 50:
            verdict_class = "verdict-warning"
            verdict_text  = "Высокий риск — значительные доработки"
        elif score <= 65:
            verdict_class = "verdict-moderate"
            verdict_text  = "Умеренный риск — необходима проверка"
        else:
            verdict_class = "verdict-good"
            verdict_text  = "Перспективная идея — рекомендуется пилот"

        st.markdown(
            f"<div class='score-card'>"
            f"<div class='score-number'>{score}<span class='score-denom'>/100</span></div>"
            f"<br><span class='{verdict_class}'>{verdict_text}</span>"
            f"</div>",
            unsafe_allow_html=True,
        )
        st.progress(min(max(score / 100.0, 0.0), 1.0))

    with col_score2:
        subscores = st.session_state.get("subscores", {})
        if subscores:
            s_prob = subscores.get("problem_validation", 0.0)
            s_fit  = subscores.get("solution_demand", 0.0)
            s_fin  = subscores.get("financial_viability", 0.0)
            penalties = subscores.get("penalties", 0.0)

            st.markdown("**Компоненты скоринга**")
            st.caption(f"Валидация проблемы: **{s_prob:.1f} / 40.0**")
            st.progress(min(max(s_prob / 40.0, 0.0), 1.0))

            st.caption(f"Solution Fit и спрос: **{s_fit:.1f} / 35.0**")
            st.progress(min(max(s_fit / 35.0, 0.0), 1.0))

            st.caption(f"Экономическая устойчивость: **{s_fin:.1f} / 25.0**")
            st.progress(min(max(s_fin / 25.0, 0.0), 1.0))

            if penalties > 0:
                st.caption(f"Применены штрафы за критические риски: −{penalties:.1f} б.")

    st.divider()

    # ── Юнит-экономика ───────────────────────────────────────
    if report.unit_economics:
        ue = report.unit_economics
        st.subheader("Юнит-экономика")
        st.caption("Расчёт на основе эффективного дохода, страновых коэффициентов и отраслевых бенчмарков")

        c1, c2, c3, c4 = st.columns(4)
        with c1:
            st.metric("LTV (пожизненная ценность)", f"${ue.ltv:.2f}")
        with c2:
            st.metric("CAC (стоимость привлечения)", f"${ue.cac:.2f}")
        with c3:
            ratio_delta = "Отлично (≥3.0x)" if ue.ltv_cac_ratio >= 3.0 else "Норма (1.5–3.0x)" if ue.ltv_cac_ratio >= 1.5 else "Убыточно (<1.0x)"
            st.metric("LTV : CAC", f"{ue.ltv_cac_ratio:.2f}x", delta=ratio_delta)
        with c4:
            st.metric("Окупаемость CAC", f"{ue.cac_payback_months:.1f} мес.")

        c5, c6, c7, c8 = st.columns(4)
        with c5:
            st.metric("Monthly Burn Rate", f"${ue.monthly_burn_rate:,.0f} / мес")
        with c6:
            r_label = f"{ue.runway_months} мес." if ue.runway_months < 900 else "∞"
            st.metric("Runway (статический)", r_label)
        with c7:
            be_label = f"Месяц {ue.break_even_month}" if ue.break_even_month else "Не достигнута"
            st.metric("Break-even", be_label)
        with c8:
            st.metric("Базовый отток (Churn)", f"{ue.adjusted_churn * 100:.1f}%")

        cf1, cf2, cf3 = st.columns(3)
        with cf1:
            st.metric("Дно кассовой ямы", f"${ue.min_cash_balance:,.0f}", help="Минимальный остаток денег до выхода на самоокупаемость")
        with cf2:
            st.metric("Расход капитала до безубытка", f"${ue.peak_cash_drag:,.0f}", help="Сколько сожжёт бизнес из стартового капитала")
        with cf3:
            deficit_str = f"${ue.peak_capital_deficit:,.0f}" if ue.peak_capital_deficit > 0 else "$0 (капитала хватает)"
            st.metric("Дефицит капитала", deficit_str, help="Дополнительный капитал для преодоления кассовой ямы")

        with st.expander("Детали бенчмарков"):
            st.markdown(
                f"- **Отраслевой LTV:CAC:** медиана `{ue.benchmark_ltv_cac.median}x` (диапазон `{ue.benchmark_ltv_cac.low}x` – `{ue.benchmark_ltv_cac.high}x`)\n"
                f"- **Отраслевой Churn:** `{ue.benchmark_churn.median * 100:.1f}%` в месяц\n"
                f"- **Валовая маржа (Gross Margin):** `{ue.gross_margin * 100:.0f}%`\n"
                f"- **Конверсия Trial-to-Paid:** `{ue.benchmark_conversion.low * 100:.1f}%` – `{ue.benchmark_conversion.high * 100:.1f}%`"
            )

        st.divider()

    # ── Монте-Карло Fan Chart ─────────────────────────────────
    if report.monte_carlo_results:
        mc = report.monte_carlo_results
        pt_label = {
            "one_shot":  "Разовая задача (Churn Cliff ожидается на 2–3 месяце)",
            "recurring": "Постоянная потребность (отток снижается со временем)",
            "periodic":  "Периодический спрос (сезонные пики оттока)",
        }.get(mc.product_type, mc.product_type)

        st.subheader("Вероятностный прогноз роста MRR — Fan Chart")
        st.caption(
            f"Тип спроса: {pt_label} · "
            f"{mc.num_simulations} симуляций · {mc.num_months} месяцев"
        )

        months_x = list(range(mc.num_months + 1))
        fig_mc = go.Figure()

        if mc.sample_trajectories:
            for traj in mc.sample_trajectories:
                is_bankrupt = traj[-1] < (report.unit_economics.monthly_burn_rate * 0.1
                                           if report.unit_economics else 50.0)
                color = "rgba(220,53,69,0.04)" if is_bankrupt else "rgba(99,110,250,0.04)"
                fig_mc.add_trace(go.Scatter(
                    x=months_x, y=traj,
                    mode="lines",
                    line=dict(width=0.7, color=color),
                    showlegend=False,
                    hoverinfo="skip",
                ))

        fig_mc.add_trace(go.Scatter(
            x=months_x + months_x[::-1],
            y=mc.mrr_p90 + mc.mrr_p10[::-1],
            fill="toself",
            fillcolor="rgba(99,110,250,0.08)",
            line=dict(width=0),
            showlegend=True,
            name="Коридор вероятности (P10–P90)",
            hoverinfo="skip",
        ))
        fig_mc.add_trace(go.Scatter(
            x=months_x, y=mc.mrr_p90,
            mode="lines",
            line=dict(color="rgba(46,204,113,0.9)", width=1.8, dash="dot"),
            name=f"Оптимистичный P90 (${mc.mrr_p90[-1]:,.0f})",
        ))
        fig_mc.add_trace(go.Scatter(
            x=months_x, y=mc.mrr_p10,
            mode="lines",
            line=dict(color="rgba(231,76,60,0.9)", width=1.8, dash="dot"),
            name=f"Пессимистичный P10 (${mc.mrr_p10[-1]:,.0f})",
        ))
        fig_mc.add_trace(go.Scatter(
            x=months_x, y=mc.mrr_p50,
            mode="lines",
            line=dict(color="#3498db", width=3),
            name=f"Медианный прогноз P50 (${mc.mrr_p50[-1]:,.0f})",
        ))

        if report.unit_economics:
            br = report.unit_economics.monthly_burn_rate
            fig_mc.add_hline(
                y=br,
                line_dash="dot", line_color="#f39c12", line_width=1.5,
                annotation_text=f"Burn Rate ${br:,.0f}/мес",
                annotation_position="bottom right",
                annotation_font_color="#f39c12",
            )

        fig_mc.update_layout(
            title=dict(
                text="Динамика Monthly Recurring Revenue — 24 месяца<br>"
                     "<sup>Гуще = вероятнее | Красные линии = сценарии банкротства</sup>",
                font=dict(size=14),
            ),
            xaxis_title="Месяц",
            yaxis_title="MRR (USD)",
            height=420,
            margin=dict(l=20, r=20, t=60, b=20),
            hovermode="x unified",
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        )
        st.plotly_chart(fig_mc, use_container_width=True)

        mc1, mc2, mc3, mc4 = st.columns(4)
        with mc1:
            bk_color = "inverse" if mc.bankruptcy_probability > 50 else "off"
            st.metric("Риск банкротства (24 мес)", f"{mc.bankruptcy_probability:.1f}%",
                      delta="Высокий риск" if mc.bankruptcy_probability > 50 else "Умеренный",
                      delta_color=bk_color)
        with mc2:
            be_label = f"Месяц {mc.median_break_even_month}" if mc.median_break_even_month else "Не достигнута"
            st.metric("Медианная безубыточность", be_label)
        with mc3:
            st.metric("Вероятность $10K+ MRR", f"{mc.prob_reach_10k_mrr:.1f}%")
        with mc4:
            st.metric("Вероятность 1 000+ клиентов", f"{mc.prob_reach_1k_users:.1f}%")

        if getattr(mc, "stress_capital_p10", 0) > 0:
            st.markdown("**Стресс-тест ликвидности (10 000 сценариев)**")
            sc1, sc2, sc3 = st.columns(3)
            with sc1:
                st.metric("Дно кассовой ямы P10 (стресс)", f"${mc.pathwise_min_balance_p10:,.0f}",
                          help="Худшие 10% сценариев")
            with sc2:
                st.metric("Дно кассовой ямы P50 (медиана)", f"${mc.pathwise_min_balance_p50:,.0f}")
            with sc3:
                st.metric("Капитал для 90% выживаемости", f"${mc.stress_capital_p10:,.0f}")

        st.divider()

    # ── Конкурентный анализ ───────────────────────────────────
    if report.market_research:
        mr = report.market_research
        st.subheader("Анализ конкурентной среды")

        competition_map = {
            "Высокая": "высокая",
            "Олигополия / Доминирование гигантов": "олигополия",
            "Умеренная": "умеренная",
        }
        c_level = competition_map.get(mr.competition_level, mr.competition_level.lower())
        st.markdown(f"**Плотность рынка:** `{c_level}`")
        if mr.summary:
            st.info(mr.summary)

        if getattr(mr, "web_sources", None):
            with st.expander("Источники (интернет-поиск)"):
                for src_url in mr.web_sources:
                    st.markdown(f"- [{src_url}]({src_url})")

        if mr.competitors:
            comp_rows = []
            for c in mr.competitors:
                comp_rows.append({
                    "Конкурент": c.name,
                    "Категория": c.category,
                    "Преимущества": c.strengths,
                    "Уязвимости": c.weaknesses,
                    "Ценовая модель": c.price_point,
                })
            df_comp = pd.DataFrame(comp_rows)
            st.dataframe(df_comp, use_container_width=True, hide_index=True)

            st.markdown("**Ценовое сравнение конкурентов**")
            price_cols = st.columns(min(len(mr.competitors), 4))
            for i, (col, comp) in enumerate(zip(price_cols, mr.competitors)):
                with col:
                    price_str = comp.price_point or "н/д"
                    cat_label = "Прямой" if "Прямой" in comp.category else "Косвенный" if "Косвенный" in comp.category else "Иной"
                    st.metric(
                        label=f"{comp.name[:25]} · {cat_label}",
                        value=price_str[:40],
                        help=f"{comp.category}\n\n+ {comp.strengths}\n\n− {comp.weaknesses}",
                    )

        if mr.differentiation_strategy:
            st.success(f"**Рекомендуемая стратегия дифференциации (УТП):**  \n{mr.differentiation_strategy}")

        if mr.entry_barriers:
            st.markdown("**Барьеры входа на рынок:**")
            for b in mr.entry_barriers:
                st.markdown(f"- {b}")

        st.divider()

    # ── Инсайты и рекомендации ────────────────────────────────
    st.subheader("Экспертные инсайты и рекомендации")

    if report.insights:
        for insight in report.insights:
            msg = f"**{insight.title}**  \n{insight.message}"
            if insight.recommendation:
                msg += f"  \n*Рекомендация: {insight.recommendation}*"
            if insight.benchmark_ref:
                msg += f"  \n_Бенчмарк: {insight.benchmark_ref}_"

            if insight.severity == "critical":
                st.error(msg)
            elif insight.severity == "warning":
                st.warning(msg)
            elif insight.severity == "success":
                st.success(msg)
            else:
                st.info(msg)
    else:
        st.caption("Инсайты не сгенерированы")

    st.divider()

    # ── Экспорт ───────────────────────────────────────────────
    st.subheader("Экспорт отчёта")
    report_json = report.model_dump_json(indent=2)
    st.download_button(
        label="Скачать полный отчёт (JSON)",
        data=report_json,
        file_name=f"startup_validation_{report.business_input.name or 'report'}.json",
        mime="application/json",
        type="primary",
    )

# ═══════════════════════════════════════════════════════════════
#  TAB 4 — Отзыв
# ═══════════════════════════════════════════════════════════════

with tab4:
    st.header("Оставить отзыв")
    st.caption("Ваш отзыв поможет улучшить инструмент")

    _report_for_fb: "ValidationReport" = st.session_state.get("report")
    _idea_name_fb  = ""
    _idea_score_fb = None
    if _report_for_fb is not None:
        _idea_name_fb  = _report_for_fb.business_input.name if _report_for_fb.business_input else ""
        _idea_score_fb = int(_report_for_fb.overall_score) if _report_for_fb.overall_score else None

    with st.form("feedback_form", clear_on_submit=True):
        st.markdown("#### Оцените инструмент")

        _rating = st.select_slider(
            "Ваша оценка",
            options=[1, 2, 3, 4, 5],
            value=5,
            format_func=lambda x: {1: "1 — плохо", 2: "2 — ниже среднего", 3: "3 — нормально", 4: "4 — хорошо", 5: "5 — отлично"}[x],
        )

        _text = st.text_area(
            "Ваш отзыв",
            placeholder="Что понравилось? Что можно улучшить? Был ли результат полезен?",
            height=150,
            max_chars=1000,
        )

        _submitted = st.form_submit_button("Отправить отзыв", type="primary", use_container_width=True)

    if _submitted:
        if not _text.strip():
            st.warning("Напишите текст отзыва перед отправкой")
        elif len(_text.strip()) < 5:
            st.warning("Отзыв слишком короткий")
        else:
            with st.spinner("Отправляем..."):
                _ok = send_feedback(
                    text=_text,
                    rating=_rating,
                    idea_name=_idea_name_fb,
                    idea_score=_idea_score_fb,
                )
            if _ok:
                st.success("Спасибо за отзыв!")
                st.balloons()
            else:
                import datetime as _dt
                _fb_entry = {
                    "time":    str(_dt.datetime.now()),
                    "rating":  _rating,
                    "idea":    _idea_name_fb,
                    "score":   _idea_score_fb,
                    "text":    _text,
                }
                _fb_log = str(Path(tempfile.gettempdir()) / "feedbacks.jsonl")
                try:
                    with open(_fb_log, "a", encoding="utf-8") as _f:
                        import json as _json
                        _f.write(_json.dumps(_fb_entry, ensure_ascii=False) + "\n")
                    st.success("Отзыв сохранён локально")
                except Exception:
                    st.info("Отзыв получен. Спасибо.")

    st.divider()

    if not is_email_configured():
        with st.expander("Для организатора: настройка получения отзывов"):
            st.markdown("""
**Шаг 1.** Включите двухфакторную аутентификацию на Gmail:
[myaccount.google.com/security](https://myaccount.google.com/security)

**Шаг 2.** Создайте «Пароль приложения»:
[myaccount.google.com/apppasswords](https://myaccount.google.com/apppasswords)
Введите название «Startup Validator» → нажмите «Создать» → скопируйте 16-значный пароль.

**Шаг 3.** В Streamlit Cloud → Settings → Secrets добавьте:
```toml
EMAIL_APP_PASSWORD = "xxxx xxxx xxxx xxxx"
```
""")
