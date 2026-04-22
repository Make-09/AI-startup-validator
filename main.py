"""
main.py — Streamlit UI для AI Customer Discovery Validator.
3 вкладки: Ввод идеи → AI Интервью → Рекомендации.
"""

import logging
import os

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
from interview_engine import research_market_context, run_all_interviews, get_llm_name, QuotaExceededError
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

# ── Конфигурация страницы ────────────────────────────────────
st.set_page_config(
    page_title="AI Startup Validator — Валидатор бизнес-идей",
    page_icon="🔬",
    layout="wide",
)

st.title("🔬 AI Startup Validator")
st.caption("Валидация бизнес-идей через AI Customer Discovery")

# ═══════════════════════════════════════════════════════════════
# 🎓 Баннер для участников группы
# ═══════════════════════════════════════════════════════════════

with st.expander("📖 Для участников группы — читайте сюда!", expanded=True):
    st.markdown("""
## 👋 Привет! Это AI Startup Validator — инструмент для проверки бизнес-идей

Этот сайт создан специально для нашей группы, чтобы вы могли **протестировать свою бизнес-идею** с помощью искусственного интеллекта — за несколько минут, без опыта и вложений.

---

### 🚀 Что умеет этот инструмент?

| Функция | Что это значит |
|--------|---------------|
| 🧠 **AI-интервью (Mom Test)** | ИИ симулирует реальных людей и «интервьюирует» их по вашей идее |
| 💰 **Юнит-экономика** | Считает LTV, CAC, окупаемость, runway |
| 🏆 **Итоговый score 0–100** | Общая оценка жизнеспособности вашей идеи |

---

### 📝 Как пользоваться (5 шагов):

1. **Заполните форму** слева — название идеи, описание, целевая аудитория, цена
2. **Выберите тип монетизации** — подписка / разовая оплата / маркетплейс
3. **Укажите финансы** — бюджет на маркетинг, начальный капитал
4. **Нажмите «🚀 Запустить валидацию»**
5. **Изучите результаты** — AI проведёт интервью с 5–10 виртуальными клиентами

---

### 💡 Идеи для тестирования (если нет своей):
- Приложение для поиска репетиторов в Казахстане
- Сервис доставки домашней еды от бабушек
- Платформа для аренды вещей между соседями
- AI-помощник для написания резюме на казахском

---

### ⚠️ Важно знать:
- **Лимит:** максимум **{max_runs} запусков** в день на всю группу (используйте разумно!)
- **Сегодня использовано:** {used} из {max_runs}
- Рекомендуемое количество персон: **5–10** (быстрее и дешевле по токенам)
- Язык ответов: выбирайте **Русский** или **Казахский**
""".format(max_runs=MAX_DAILY_RUNS, used=current_count()))

# Счётчик запусков в шапке
_remaining = get_remaining_runs()
_limit_reached = _remaining == 0
if _limit_reached:
    _reset_time = next_reset_info()
    st.error(f"🚫 **Дневной лимит исчерпан** — {MAX_DAILY_RUNS}/{MAX_DAILY_RUNS} запусков использовано сегодня. Лимит сбросится через **{_reset_time}** ⏳")
elif _remaining <= 3:
    st.warning(f"⚠️ Осталось запусков сегодня: **{_remaining}** из {MAX_DAILY_RUNS} — используйте разумно!")
else:
    st.info(f"✅ Осталось запусков сегодня: **{_remaining}** из {MAX_DAILY_RUNS}")

# ═══════════════════════════════════════════════════════════════
# Боковая панель — только статус, без ввода ключей
# ═══════════════════════════════════════════════════════════════

with st.sidebar:
    st.header("⚙️ Статус")

    _api_key = os.environ.get("OPENAI_API_KEY", "")
    _model   = os.environ.get("OPENAI_MODEL", config.MODEL)
    _base    = os.environ.get("OPENAI_BASE_URL", config.BASE_URL)

    if _api_key and _api_key != "your_api_key_here":
        st.success(f"✅ API ключ подключён")
        st.caption(f"🤖 Модель: `{_model}`")
        st.caption(f"🌐 Провайдер: `{_base}`")
        # Статус пула ключей
        try:
            _pool = config.get_pool_status()
            _pool_color = "🟢" if _pool["alive_keys"] == _pool["total_keys"] else "🟡" if _pool["alive_keys"] > 0 else "🔴"
            st.caption(f"{_pool_color} Ключей: {_pool['alive_keys']}/{_pool['total_keys']} живых | Ошибок: {_pool['total_errors']}")
        except Exception:
            pass
    else:
        st.error("❌ API ключ не настроен")
        st.markdown(
            "Откройте файл **`config.py`** и вставьте ваш API ключ:\n\n"
            "```python\nAPI_KEY = \"ваш_ключ_здесь\"\n```\n\n"
            "Получить бесплатный ключ Groq: [console.groq.com](https://console.groq.com/)"
        )

    st.divider()

    # ── Блок живых бенчмарков ──
    st.markdown("📊 **Бенчмарки** (World Bank API + авторитетные отчёты)")
    st.caption("🔄 Авто-обновление при каждом анализе | Кэш: 7 дней")

    _rt_info = st.session_state.get("rt_bench_info", "⏳ Будут загружены при запуске анализа")
    _bench_loaded = "realtime_benchmark" in st.session_state
    if _bench_loaded:
        st.success(_rt_info[:80] if len(_rt_info) > 80 else _rt_info)
    else:
        st.info(_rt_info)

    if st.button("🔄 Обновить бенчмарки вручную", use_container_width=True):
        if not _api_key or _api_key == "your_api_key_here":
            st.error("⚠️ Сначала настройте API ключ в config.py!")
        else:
            with st.spinner("🌐 Обновляем: World Bank GDP + парсинг отраслевых отчётов..."):
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

# ═══════════════════════════════════════════════════════════════
#  ВКЛАДКИ
# ═══════════════════════════════════════════════════════════════

tab1, tab2, tab3, tab4 = st.tabs([
    "📝 Ваша идея",
    "🧑‍🤝‍🧑 AI Customer Discovery",
    "💡 Рекомендации и оценка",
    "💬 Оставить отзыв",
])


# ═══════════════════════════════════════════════════════════════
#  TAB 1 — Ввод идеи
# ═══════════════════════════════════════════════════════════════

with tab1:
    st.subheader("Опишите вашу бизнес-идею")

    col_left, col_right = st.columns([3, 2])

    with col_left:
        name = st.text_input(
            "Название продукта",
            value="",
            placeholder="Например: QuickCV — AI для резюме",
        )
        description = st.text_area(
            "Описание идеи",
            height=100,
            placeholder="Что делает продукт? Какую проблему решает?",
        )
        target_audience = st.text_input(
            "Целевая аудитория",
            value="",
            placeholder="Кто ваш клиент?",
        )

        # Выбор типа бизнеса (показываем display_name)
        bt_options = list(BusinessType)
        bt_display = [BENCHMARKS[bt].display_name for bt in bt_options]
        bt_index = st.selectbox(
            "Тип бизнеса",
            options=range(len(bt_options)),
            format_func=lambda i: bt_display[i],
            help="Gig Economy / Freelance Platform — платформа комиссионного типа (как Upwork, Fiverr, YouDo)",
        )
        business_type = bt_options[bt_index]
        # Для Gig Economy рекомендуем модель комиссии
        _gig_selected = business_type == BusinessType.GIG_ECONOMY
        if _gig_selected:
            st.info("💡 **Gig Economy** — рекомендуемая модель монетизации: **Комиссия со сделок**. Платформа берёт % от каждой транзакции между заказчиком и исполнителем.")

        country = st.selectbox(
            "Страна",
            options=["kazakhstan", "russia", "usa", "global"],
            format_func=lambda c: {
                "kazakhstan": "🇰🇿 Казахстан",
                "russia": "🇷🇺 Россия",
                "usa": "🇺🇸 США",
                "global": "🌍 Глобальный",
            }.get(c, c),
        )
        
        language = st.selectbox(
            "Язык интервью",
            options=["Русский", "Қазақша"],
        )

        # Сохраняем для кнопки бенчмарков в сайдбаре
        st.session_state["_last_bt"] = business_type
        st.session_state["_last_country"] = country
        st.session_state["_last_desc"] = description

    with col_right:
        # ── Модель монетизации ────────────────────────────────
        st.markdown("**💰 Модель монетизации**")
        _default_rm_index = 2 if _gig_selected else 0  # Gig → COMMISSION по умолчанию
        revenue_model_choice = st.radio(
            "Как платит пользователь?",
            options=list(RevenueModel),
            format_func=lambda m: {
                RevenueModel.SUBSCRIPTION: "📅 Ежемесячная подписка",
                RevenueModel.PAY_PER_USE:  "🎫 Оплата за использование",
                RevenueModel.COMMISSION:   "💸 Комиссия со сделок (Gig / Marketplace)",
            }[m],
            index=_default_rm_index,
        )

        # ── Динамические поля в зависимости от модели ──
        price = 10.0
        price_per_use = 5.0
        avg_uses_per_month = 5.0
        avg_deal_value = 1500.0
        commission_rate = 0.10
        avg_deals_per_month = 4.0
        currency_to_usd = 0.0022

        if revenue_model_choice == RevenueModel.SUBSCRIPTION:
            price = st.number_input(
                "💳 Цена подписки ($/мес)",
                min_value=0.1, step=1.0, value=10.0,
            )
            st.info(f"ℹ️ Доход/пользователь/мес: **${price:.2f}**")

        elif revenue_model_choice == RevenueModel.PAY_PER_USE:
            price_per_use = st.number_input(
                "🎫 Цена за одно использование ($)",
                min_value=0.01, step=0.5, value=5.0,
            )
            avg_uses_per_month = st.number_input(
                "🔄 Средн. использований в мес (1 пользов.)",
                min_value=1.0, step=1.0, value=5.0,
            )
            eff = price_per_use * avg_uses_per_month
            price = price_per_use  # храним price_per_use в price
            st.info(f"ℹ️ Доход/пользователь/мес: **${eff:.2f}** ({avg_uses_per_month:.0f}×${price_per_use:.2f})")

        else:  # COMMISSION / GIG
            if _gig_selected:
                st.caption("💡 Gig: укажите среднюю стоимость заказа, % платформы и типичную активность исполнителя")
            col_c1, col_c2 = st.columns(2)
            with col_c1:
                _deal_label = "💵 Сред. стоимость заказа (₸)" if _gig_selected else "💵 Сред. чек сделки (₸)"
                avg_deal_value = st.number_input(
                    _deal_label,
                    min_value=100.0, step=100.0, value=5000.0 if _gig_selected else 1500.0,
                    help="Gig: сколько заказчик платит за один выполненный заказ",
                )
                _deals_label = "🔁 Заказов/мес (на 1 исполнителя)" if _gig_selected else "🔁 Сделок/мес/пользов."
                avg_deals_per_month = st.number_input(
                    _deals_label,
                    min_value=1.0, step=1.0, value=6.0 if _gig_selected else 4.0,
                    help="Gig: среднее число завершённых заказов в месяц на активного исполнителя",
                )
            with col_c2:
                _comm_label = "% комиссии платформы (take rate)" if _gig_selected else "% комиссии платформы"
                _comm_default = 15 if _gig_selected else 10
                commission_pct = st.slider(
                    _comm_label,
                    min_value=1, max_value=35, value=_comm_default, step=1,
                    help="Gig: Upwork берёт 20%, Fiverr ~31%, YouDo ~15%",
                )
                commission_rate = commission_pct / 100.0
                currency_to_usd = st.number_input(
                    "💱 Курс (1 ₸ = ? $)",
                    min_value=0.0001, step=0.0001,
                    value=0.0022, format="%.4f",
                )

            earn_platform = avg_deal_value * commission_rate
            earn_worker = avg_deal_value - earn_platform
            eff_usd = avg_deal_value * currency_to_usd * commission_rate * avg_deals_per_month
            _actor = "исполнитель" if _gig_selected else "продавец/получатель"
            st.success(
                f"📊 **Пример:** Заказ {avg_deal_value:.0f}₸ → "
                f"{_actor} **{earn_worker:.0f}₸**, платформа **{earn_platform:.0f}₸** ({commission_pct}%)\n\n"
                f"💰 **Доход платформы/исполнитель/мес:** ≈ **${eff_usd:.2f}** "
                f"({avg_deals_per_month:.0f} заказов × {earn_platform:.0f}₸)"
            )

        st.markdown("---")
        st.markdown("**💼 Финансовые параметры**")
        initial_capital = st.number_input(
            "💼 Стартовый капитал ($)",
            min_value=0.0,
            step=1000.0,
            value=10000.0,
        )
        monthly_marketing_budget = st.number_input(
            "📢 Маркетинговый бюджет ($/мес)",
            min_value=0.0,
            step=100.0,
            value=500.0,
        )
        monthly_operating_costs = st.number_input(
            "🖥️ Операционные расходы ($/мес)",
            min_value=0.0,
            step=100.0,
            value=300.0,
        )
        market_size_estimate = st.number_input(
            "🎯 TAM (кол-во потенциальных клиентов)",
            min_value=1000,
            step=10000,
            value=100000,
        )
        
        num_personas = st.number_input(
            "👥 Количество респондентов",
            min_value=1,
            max_value=10,
            value=5,
            step=1,
            help="Максимум 10 персон. Рекомендуем 5–7 для быстрого теста.",
        )
        st.caption(f"🔁 Будет сделано примерно **{int(num_personas) + 1}** API-вызовов (1 генерация персон + {int(num_personas)} интервью)")

        # Информация о бенчмарке (реальные если есть, статичные иначе)
        active_bench = st.session_state.get("realtime_benchmark") or get_benchmark(business_type)
        bench_is_rt = "realtime_benchmark" in st.session_state

        st.markdown("---")
        st.markdown(
            f"**📊 Бенчмарк: {active_bench.display_name}** "
            + ("🟢 актуальный" if bench_is_rt else "🟡 статичный (2025)")
        )
        st.caption(f"Провал: {active_bench.failure_rate_12_months:.0%}")
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
        # Блокируем кнопку если дневной лимит исчерпан
        _btn_disabled = _limit_reached
        _btn_label = "🔬 Запустить валидацию" if not _btn_disabled else f"🚫 Лимит исчерпан — обновится через {next_reset_info()}"
        start_btn = st.button(
            _btn_label,
            type="primary",
            use_container_width=True,
            disabled=_btn_disabled,
        )
    with col2:
        if st.button("🗑 Очистить / Отменить", type="secondary", use_container_width=True):
            st.session_state.clear()
            st.rerun()

    if start_btn:
        # ── Проверка дневного лимита ──────────────────────────
        if get_remaining_runs() == 0:
            st.error(
                f"🚫 **Дневной лимит исчерпан!**\n\n"
                f"Сегодня уже было запущено **{MAX_DAILY_RUNS}** симуляций — это максимум для нашей группы.\n\n"
                f"Приходите завтра — лимит сбросится автоматически в полночь. 🕛"
            )
            st.stop()

        # ── Проверка API ключа ────────────────────────────────
        _api_key_check = os.environ.get("OPENAI_API_KEY", "")
        if not _api_key_check or _api_key_check in ("вставьте_ваш_ключ_здесь", "your_api_key_here", ""):
            st.error(
                "❌ **API ключ не настроен!**\n\n"
                "Без ключа симуляция невозможна. Обратитесь к организатору."
            )
            st.stop()

        errors = []

        def _is_gibberish(text: str) -> bool:
            """Определяет мусорный ввод: повторяющиеся символы, слишком мало уникальных, нет пробелов."""
            t = text.strip()
            if not t:
                return True
            unique_chars = len(set(t.lower()))
            # Менее 5 уникальных символов в тексте длиннее 10 — явный мусор (ffffffff, 111111 и т.п.)
            if unique_chars < 5 and len(t) > 10:
                return True
            # Нет ни одного пробела и длина > 15 — скорее всего непрерывный мусор
            if " " not in t and len(t) > 15:
                return True
            # Один символ повторяется более 40% текста
            most_common_ratio = max(t.lower().count(c) for c in set(t.lower())) / len(t)
            if most_common_ratio > 0.4 and len(t) > 10:
                return True
            return False

        if not description.strip() or len(description.strip()) < 20:
            errors.append("📝 **Описание идеи** — опишите подробнее (минимум 20 символов). Без этого интервью не даст смысловых результатов.")
        elif _is_gibberish(description):
            errors.append("📝 **Описание идеи** — похоже на случайный ввод. Опишите реальную бизнес-идею: что это, для кого, какую проблему решает.")

        if not target_audience.strip() or len(target_audience.strip()) < 5:
            errors.append("👥 **Целевая аудитория** — укажите кто ваш клиент (например: «фрилансеры 25–40 лет» или «малый бизнес»).")
        elif _is_gibberish(target_audience):
            errors.append("👥 **Целевая аудитория** — похоже на случайный ввод. Укажите реальную аудиторию.")

        if not name.strip() or len(name.strip()) < 2:
            errors.append("🏷 **Название продукта** — введите название.")
        elif _is_gibberish(name):
            errors.append("🏷 **Название продукта** — похоже на случайный ввод.")

        if errors:
            for e in errors:
                st.error(e)
            st.stop()

        # ── Занимаем слот запуска ─────────────────────────────
        if not consume_run():
            st.error(
                f"🚫 **Дневной лимит исчерпан!**\n\n"
                f"Пока вы заполняли форму, кто-то использовал последний слот. "
                f"Сегодня было запущено **{MAX_DAILY_RUNS}** симуляций.\n\n"
                f"Приходите завтра — лимит сбросится в полночь. 🕛"
            )
            st.stop()

        st.info(f"🎫 Запуск {current_count()}/{MAX_DAILY_RUNS} на сегодня")

        business_input = BusinessInput(
            name=name,
            description=description,
            business_type=business_type,
            target_audience=target_audience,
            country=country,
            num_personas=num_personas,
            language=language,
            # ── Модель монетизации ──
            revenue_model=revenue_model_choice,
            price=price,
            price_per_use=price_per_use,
            avg_uses_per_month=avg_uses_per_month,
            avg_deal_value=avg_deal_value,
            commission_rate=commission_rate,
            avg_deals_per_month=avg_deals_per_month,
            currency_to_usd=currency_to_usd,
            # ── Финансы ──
            initial_capital=initial_capital,
            monthly_marketing_budget=monthly_marketing_budget,
            monthly_operating_costs=monthly_operating_costs,
            market_size_estimate=int(market_size_estimate),
        )

        try:
            # 0. Автоматический fetch реальных бенчмарков из сети
            _api_ready = bool(os.environ.get("OPENAI_API_KEY", ""))
            if _api_ready:
                with st.spinner("🌐 Получаем данные: World Bank API + авторитетные отчёты..."):
                    _bench_rt, _bench_src = fetch_realtime_benchmarks(
                        business_input.business_type,
                        business_input.country,
                        business_input.description,
                    )
                    st.session_state["realtime_benchmark"] = _bench_rt
                    st.session_state["rt_bench_info"] = _bench_src
                st.success(f"✅ Бенчмарки обновлены: {_bench_rt.source}")
            else:
                st.warning("⚠️ API ключ не установлен — используются статичные бенчмарки 2025")

            # 1. Генерация персон (с определением возрастного профиля ЦА)
            from personas import _detect_age_profile
            _age_profile = _detect_age_profile(business_input)
            _age_label_map = {"youth": "школьники 12–17 лет", "student": "студенты 17–25 лет", "adult": "взрослые 18–55 лет"}
            st.info(f"👥 Возрастной профиль ЦА: **{_age_label_map.get(_age_profile['label'], '?')}**")
            with st.spinner("⚙️ Генерация синтетических персон..."):
                personas = generate_personas(business_input, count=business_input.num_personas)
            st.success(f"✅ Сгенерировано {len(personas)} персон")

            # 1.5 Поиск конкурентов
            with st.spinner("🌍 Исследование конкурентов и рынка..."):
                market_context = research_market_context(business_input)
            if market_context:
                st.success("✅ Рыночный контекст собран")
            else:
                st.info("ℹ️ Рыночный контекст не найден, интервью пройдут по базовому сценарию")

            # 2. AI-интервью (двухфазный Mom Test, последовательно)
            # Проверяем наличие живых ключей БЕЗ потребления cooldown-слота
            _pool_check = config.get_pool_status()
            if _pool_check["total_keys"] == 0:
                st.error(
                    "**❌ API ключи не настроены!**\n\n"
                    "Добавьте ключи через `OPENAI_API_KEY` в Streamlit Secrets или переменные окружения.\n\n"
                    "Получить бесплатные ключи Groq: [console.groq.com](https://console.groq.com/)"
                )
                st.stop()
            if _pool_check["alive_keys"] == 0:
                st.error(
                    "**❌ Все API ключи исчерпали дневной лимит!**\n\n"
                    "Попробуйте завтра — лимиты Groq сбрасываются в полночь."
                )
                st.stop()

            with st.spinner(
                f"🤖 AI Customer Interviews (Mom Test, 2 фазы)... "
                f"Опрашиваем {business_input.num_personas} персон последовательно — "
                f"ориентировочно {business_input.num_personas * 8}–{business_input.num_personas * 15} сек."
            ):
                responses = run_all_interviews(
                    personas, business_input, market_context=market_context,
                    age_profile=_age_profile
                )

            # 3. Агрегация
            aggregated = aggregate_interviews(responses)
            st.success(f"✅ Интервью завершены: {aggregated.total_personas} ответов")
            if aggregated.fallback_count > 0:
                valid_count = aggregated.total_personas - aggregated.fallback_count
                st.warning(
                    f"⚠️ **{aggregated.fallback_count} из {len(personas)} интервью завершились ошибкой LLM.** "
                    f"Итоговые метрики рассчитаны только по {valid_count} валидным ответам. "
                    f"Проверьте API ключ и название модели в настройках."
                )

            # 4. Инсайты
            insights = generate_insights(business_input, aggregated)

            # 5. Overall Score (только интервью)
            score = 0.0
            score += min(50.0, (aggregated.pct_would_buy / 0.5) * 50.0)
            score += min(50.0, aggregated.avg_solution_fit / 10.0 * 50.0)

            # 6. Сохранить отчёт
            st.session_state.report = ValidationReport(
                business_input=business_input,
                interview_results=aggregated,
                insights=insights,
                overall_score=round(score),
            )

            st.rerun()

        except QuotaExceededError as qe:
            st.error(
                f"🚫 **API ключ исчерпал лимит!**\n\n"
                f"{qe}\n\n"
                f"**Что делать:**\n"
                f"- Попробуйте запустить завтра (лимиты сбрасываются в полночь)\n"
                f"- Или обратитесь к организатору для замены ключа"
            )
            st.stop()

        except Exception as e:
            err_str = str(e)
            # Дополнительная защита — ловим quota-ошибки которые не стали QuotaExceededError
            quota_kw = ("quota", "exceeded", "billing", "resource_exhausted", "insufficient_quota")
            if any(kw in err_str.lower() for kw in quota_kw):
                st.error(
                    f"🚫 **API ключ исчерпал лимит токенов/запросов!**\n\n"
                    f"Симуляция остановлена. Попробуйте завтра или смените ключ.\n\n"
                    f"_Детали: {err_str[:200]}_"
                )
            else:
                st.error(f"❌ Ошибка во время валидации: {e}")
                st.exception(e)


# ═══════════════════════════════════════════════════════════════
#  TAB 2 — AI Customer Discovery
# ═══════════════════════════════════════════════════════════════

with tab2:
    st.header("🧠 AI Customer Discovery")
    st.caption(f"🤖 **Активная модель:** {get_llm_name()}")

    report: ValidationReport = st.session_state.report

    if report is None or report.interview_results is None:
        st.info("👈 Сначала заполните данные и нажмите 'Запустить симуляцию' на первой вкладке.")
        st.stop()

    ir = report.interview_results
        
    if ir.fallback_count > 0:
        valid_count = ir.total_personas - ir.fallback_count
        st.warning(
            f"⚠️ **Внимание:** {ir.fallback_count} из {ir.total_personas} интервью завершились ошибкой LLM. "
            f"Метрики рассчитаны по {valid_count} валидным ответам. "
            f"Персоны с ошибкой отмечены 🔴 ниже."
        )

    # ── Секция A: Сводка ──────────────────────────────────────
    st.subheader("📋 Сводка AI Customer Discovery")
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("🎯 Острота проблемы", f"{ir.avg_problem_severity:.1f} / 10")
    with col2:
        st.metric("💳 Готовы купить", f"{ir.pct_would_buy * 100:.0f}%")
    with col3:
        st.metric("⭐ Рекомендация (ср.)", f"{ir.avg_nps_score:.1f} / 10")
    with col4:
        st.metric("📊 Solution Fit", f"{ir.avg_solution_fit:.1f} / 10")

    st.divider()

    col_pie, col_concerns = st.columns([1, 1])

    # ── Секция B: Ценовое восприятие (Pie chart) ──────────────
    with col_pie:
        st.subheader("💰 Ценовое восприятие")
        fig_pie = go.Figure(data=[go.Pie(
            labels=["Дорого", "Нормально", "Дёшево"],
            values=[
                ir.pct_price_too_high,
                ir.pct_price_ok,
                ir.pct_price_too_low,
            ],
            marker_colors=["#e74c3c", "#2ecc71", "#3498db"],
            hole=0.35,
        )])
        fig_pie.update_layout(
            height=300,
            margin=dict(t=10, b=10, l=10, r=10),
            showlegend=True,
        )
        st.plotly_chart(fig_pie, use_container_width=True)

    # ── Секция C: Топ-3 опасения ──────────────────────────────
    with col_concerns:
        st.subheader("⚠️ Топ-3 опасения")
        if ir.top_concerns:
            for concern in ir.top_concerns:
                st.warning(concern)
        else:
            st.info("Нет данных")

        st.subheader("✨ Топ-3 желаемых фичи")
        if ir.top_desired_features:
            for feature in ir.top_desired_features:
                st.info(feature)
        else:
            st.info("Нет данных")

    # ── Секция E: Детальные ответы персон ────────────────────
    st.divider()
    st.subheader("👥 Детальные ответы персон")

    _phase_labels = {1: "🔍 До знакомства с продуктом", 2: "💡 После знакомства с продуктом"}
    _phase_colors = {1: "#1e3a5f", 2: "#1a3a1e"}

    for resp in ir.responses:
        buy_icon = '✅' if resp.would_buy else '❌'
        error_icon = '🔴' if getattr(resp, 'is_error', False) else ''
        with st.expander(f"{error_icon}**{resp.persona_name}** — {resp.persona_occupation} {buy_icon}"):

            # ── Ошибка API — показываем красный баннер, скрываем метрики ──
            if getattr(resp, 'is_error', False):
                st.error(
                    f"**❌ Ответ не получен от LLM**\n\n"
                    f"{resp.main_concern}\n\n"
                    f"Метрики для этой персоны **недостоверны** и не отображаются. "
                    f"Проверьте:\n"
                    f"- Правильность API ключа\n"
                    f"- Название модели (например: `openai/gpt-4o-mini`, `llama3-8b-8192`)\n"
                    f"- Лимиты запросов у провайдера"
                )
                continue

            # ── Диалог интервью ──────────────────────────────
            if resp.conversation:
                current_phase = None
                for turn in resp.conversation:
                    phase = turn.get("phase", 1)
                    q     = turn.get("question", "")
                    a     = turn.get("answer", "")

                    # Разделитель фаз
                    if phase != current_phase:
                        current_phase = phase
                        label = _phase_labels.get(phase, f"Фаза {phase}")
                        st.markdown(
                            f"<div style='background:{_phase_colors.get(phase,'#1a1a2e')};"
                            f"border-radius:6px;padding:6px 12px;margin:10px 0 6px 0;"
                            f"font-size:0.8em;font-weight:600;color:#aaa'>{label}</div>",
                            unsafe_allow_html=True,
                        )

                    if q:
                        st.markdown(
                            f"<div style='color:#7eb8f7;font-size:0.85em;"
                            f"margin:6px 0 2px 0'>🎤 {q}</div>",
                            unsafe_allow_html=True,
                        )
                    if a:
                        st.markdown(
                            f"<div style='background:#1e1e2e;border-left:3px solid #555;"
                            f"padding:8px 12px;border-radius:0 6px 6px 0;"
                            f"margin:2px 0 8px 0;font-size:0.9em'>💬 {a}</div>",
                            unsafe_allow_html=True,
                        )
                st.divider()
            elif resp.raw_opinion:
                # Fallback: если диалога нет — показываем raw_opinion как раньше
                st.markdown(f"*«{resp.raw_opinion}»*")
                st.divider()

            # ── Итоговые метрики ─────────────────────────────
            st.caption("📊 Итоговые оценки")
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
                f"**Купит:** {'✅' if resp.would_buy else '❌'}"
            )
            if resp.main_concern:
                st.markdown(f"**⚠️ Опасение:** {resp.main_concern}")
            if resp.desired_feature:
                st.markdown(f"**💡 Хочет фичу:** {resp.desired_feature}")


# ═══════════════════════════════════════════════════════════════
#  TAB 3 — Рекомендации и итоговая оценка
# ═══════════════════════════════════════════════════════════════

with tab3:
    report = st.session_state.report

    if report is None:
        st.info("ℹ️ Сначала запустите валидацию на вкладке «📝 Ваша идея»")
        st.stop()

    # ── Секция A: Рекомендации ────────────────────────────────
    st.subheader("💡 Рекомендации")

    if report.insights:
        for insight in report.insights:
            msg = f"**{insight.title}**\n\n{insight.message}"
            if insight.recommendation:
                msg += f"\n\n*Рекомендация: {insight.recommendation}*"
            if insight.benchmark_ref:
                msg += f"\n\n_Бенчмарк: {insight.benchmark_ref}_"

            if insight.severity == "critical":
                st.error(msg)
            elif insight.severity == "warning":
                st.warning(msg)
            elif insight.severity == "success":
                st.success(msg)
            else:
                st.info(msg)
    else:
        st.info("Инсайты не сгенерированы")

    st.divider()

    st.subheader("💾 Экспорт данных")
    report_json = report.model_dump_json(indent=2)
    st.download_button(
        label="Скачать результаты (JSON)",
        data=report_json,
        file_name="validation_result.json",
        mime="application/json"
    )

    st.divider()

    # ── Секция D: Overall Score ───────────────────────────────
    st.subheader("🏆 Общая оценка жизнеспособности")

    score = int(report.overall_score)
    st.progress(score / 100)
    st.markdown(f"## {score}/100")

    if score <= 25:
        st.markdown("🔴 **Критический риск** — продукт требует кардинального пересмотра")
    elif score <= 50:
        st.markdown("🟠 **Высокий риск** — серьёзные проблемы требуют решения до запуска")
    elif score <= 75:
        st.markdown("🟡 **Умеренный риск** — есть потенциал, но нужна доработка")
    else:
        st.markdown("🟢 **Перспективный проект** — базовая валидация пройдена")

# ═══════════════════════════════════════════════════════════════
#  TAB 4 — Отзыв
# ═══════════════════════════════════════════════════════════════

with tab4:
    st.header("💬 Оставить отзыв")
    st.caption("Ваш отзыв поможет улучшить инструмент — он придёт напрямую автору")

    # Получаем данные об идее из отчёта если есть
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
            format_func=lambda x: {1: "1 ⭐", 2: "2 ⭐⭐", 3: "3 ⭐⭐⭐", 4: "4 ⭐⭐⭐⭐", 5: "5 ⭐⭐⭐⭐⭐"}[x],
        )

        _text = st.text_area(
            "Ваш отзыв",
            placeholder="Что понравилось? Что можно улучшить? Был ли результат полезен для вашей идеи?",
            height=150,
            max_chars=1000,
        )

        _submitted = st.form_submit_button("📨 Отправить отзыв", type="primary", use_container_width=True)

    if _submitted:
        if not _text.strip():
            st.warning("✏️ Напишите текст отзыва перед отправкой")
        elif len(_text.strip()) < 5:
            st.warning("✏️ Отзыв слишком короткий — напишите хотя бы пару слов")
        else:
            with st.spinner("Отправляем..."):
                _ok = send_feedback(
                    text=_text,
                    rating=_rating,
                    idea_name=_idea_name_fb,
                    idea_score=_idea_score_fb,
                )
            if _ok:
                st.success("✅ Спасибо за отзыв! Он уже у автора 🙏")
                st.balloons()
            else:
                # Telegram не настроен или ошибка — сохраняем локально
                import datetime as _dt
                _fb_entry = {
                    "time":    str(_dt.datetime.now()),
                    "rating":  _rating,
                    "idea":    _idea_name_fb,
                    "score":   _idea_score_fb,
                    "text":    _text,
                }
                _fb_log = "/tmp/feedbacks.jsonl"
                try:
                    with open(_fb_log, "a", encoding="utf-8") as _f:
                        import json as _json
                        _f.write(_json.dumps(_fb_entry, ensure_ascii=False) + "\n")
                    st.success("✅ Отзыв сохранён! (Telegram не настроен — отзыв записан локально)")
                except Exception:
                    st.info("✅ Отзыв получен! Спасибо.")

    st.divider()

    # Подсказка для организатора
    if not is_email_configured():
        with st.expander("⚙️ Для организатора: как настроить получение отзывов на email"):
            st.markdown("""
**Шаг 1.** Включите двухфакторную аутентификацию на Gmail:

[myaccount.google.com/security](https://myaccount.google.com/security) → «Двухэтапная аутентификация» → Включить

**Шаг 2.** Создайте «Пароль приложения»:

[myaccount.google.com/apppasswords](https://myaccount.google.com/apppasswords)
→ Введите название «Startup Validator» → нажмите «Создать»
→ Скопируйте **16-значный пароль** (вида `xxxx xxxx xxxx xxxx`)

**Шаг 3.** В Streamlit Cloud → Settings → Secrets добавьте:
```toml
EMAIL_APP_PASSWORD = "xxxx xxxx xxxx xxxx"
```

После этого все отзывы будут приходить на **mbahetzan@gmail.com** 📧
""")
