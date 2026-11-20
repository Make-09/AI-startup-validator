"""
market_research.py — 3-уровневый модуль анализа конкурентной среды стартапа.
Уровень 1: Курируемый каталог лидеров рынка (0 мс, гарантированный fallback)
Уровень 2: Веб-поиск живых конкурентов через DuckDuckGo (тексты + сниппеты с ценами)
Уровень 3: LLM-синтез структурированного отчёта по собранным данным

АРХИТЕКТУРА ЭКОНОМИИ ТОКЕНОВ:
- Веб-поиск выполняется БЕСПЛАТНО через DuckDuckGo (нет API ключа)
- LLM вызывается ОДИН РАЗ с богатым контекстом (≈ 800 токенов промпт + 700 ответ)
- Fallback на курируемую базу если DuckDuckGo недоступен (нет ни одного токена)
"""

import json
import logging
import os
import re
import time
from typing import List, Optional, Tuple

import requests
from models import BusinessInput, Competitor, MarketResearchReport

logger = logging.getLogger(__name__)

# ═══════════════════════════════════════════════════════════════
#  УРОВЕНЬ 1: Курируемый справочник лидеров и категорий
# ═══════════════════════════════════════════════════════════════

CURATED_MARKET_DATABASE = [
    {
        "keywords": ["резюме", "cv", "resume", "ваканси", "карьер", "найм", "job", "career"],
        "competition_level": "Высокая",
        "competitors": [
            Competitor(
                name="HeadHunter (hh.ru / hh.kz)",
                category="Прямой конкурент / Монополист поиска работы",
                strengths="Огромная база вакансий и работодателей в СНГ, стандарт отрасли",
                weaknesses="Устаревший конструктор резюме, нет умной AI-адаптации под требования вакансий",
                price_point="Бесплатно для соискателя / платные отклики и видимость",
            ),
            Competitor(
                name="Kickresume / Zety",
                category="Глобальные онлайн-конструкторы",
                strengths="Стильные шаблоны, экспорт в ATS-форматы, базовый AI",
                weaknesses="Дорогая долларовая подписка ($15-25/мес), слабая локализация под рынок СНГ",
                price_point="Подписка $10–$25 / месяц",
            ),
            Competitor(
                name="LinkedIn",
                category="Косвенный конкурент / Профессиональная сеть",
                strengths="Прямой контакт с рекрутерами, социальное подтверждение навыков",
                weaknesses="Сложно выделяться новичкам, блокировки в некоторых регионах",
                price_point="Freemium / Premium $30+/мес",
            ),
        ],
        "differentiation": "Фокус на глубокой AI-кастомизации резюме под специфику конкретной вакансии и местный менталитет рекрутеров.",
        "barriers": ["Высокая лояльность к HeadHunter", "Нежелание соискателей платить за разовую услугу"],
    },
    {
        "keywords": ["такси", "поездк", "водител", "транспорт", "ride", "drive", "авто"],
        "competition_level": "Олигополия / Доминирование гигантов",
        "competitors": [
            Competitor(
                name="inDrive",
                category="Прямой конкурент",
                strengths="Модель договорной цены, высокая популярность в регионах и междугородних поездках",
                weaknesses="Меньше контроля безопасности, волатильность подачи",
                price_point="Комиссия платформы ~10%",
            ),
            Competitor(
                name="Яндекс Go",
                category="Прямой конкурент",
                strengths="Огромный автопарк, экосистема (карты, еда, подписка Плюс), быстрая подача",
                weaknesses="Высокие динамические цены в пиковые часы, высокая комиссия с водителей (до 20-25%)",
                price_point="Динамическое ценообразование",
            ),
        ],
        "differentiation": "Нишевые перевозки (женское такси, детские поездки, фиксированные абонементы или корпоративный трансфер).",
        "barriers": ["Гигантские затраты на субсидирование поездок (CAC)", "Двусторонний сетевой эффект водитель-пассажир"],
    },
    {
        "keywords": ["еда", "ресторан", "доставк", "food", "кухн", "обед", "ужин"],
        "competition_level": "Высокая",
        "competitors": [
            Competitor(
                name="Glovo / Wolt",
                category="Прямой агрегатор доставки",
                strengths="Широкий выбор ресторанов, отлаженная курьерская логистика, удобные трекеры",
                weaknesses="Высокие комиссии для ресторанов (25-35%), плата за доставку и сервисный сбор",
                price_point="Комиссия + доставка 500-1500 ₸",
            ),
            Competitor(
                name="Яндекс Еда / Chocofood",
                category="Прямой агрегатор доставки",
                strengths="Экосистема, акции, интеграция с финтехом",
                weaknesses="Зависимость от курьеров, падение качества в непогоду",
                price_point="Сервисный сбор + доставка",
            ),
        ],
        "differentiation": "Прямая подписка на регулярные рационы, фермерские поставки или доставка без грабительской комиссии для заведений.",
        "barriers": ["Сложная логистика последней мили", "Низкая маржинальность заказов"],
    },
    {
        "keywords": ["фриланс", "freelanc", "подработк", "заказ", "услуг", "мастер", "gig"],
        "competition_level": "Умеренная / Высокая",
        "competitors": [
            Competitor(
                name="Naimi.kz / Profi.ru / YouDo",
                category="Прямой локальный сервис бытовых и профильных услуг",
                strengths="Локальная база мастеров, доверие, отзывы, рейтинги",
                weaknesses="Платные отклики для специалистов, непрозрачные комиссии, утечка в прямой контакт",
                price_point="Плата за отклик / комиссия со сделки",
            ),
            Competitor(
                name="Kwork / FL.ru / Upwork",
                category="Онлайн-биржи цифровых услуг",
                strengths="Безопасная сделка, тысячи исполнителей по дизайну, разработке и текстам",
                weaknesses="Высокая комиссия (до 20%), жесткая конкуренция демпингующих исполнителей",
                price_point="Комиссия 10–20%",
            ),
        ],
        "differentiation": "Умный матчинг без аукциона откликов, гарантия оплаты и автоматизация типовых договоров/актов.",
        "barriers": ["Проблема 'курицы и яйца' (нужно одновременно привлечь и заказчиков, и исполнителей)", "Уход клиентов мимо платформы"],
    },
    {
        "keywords": ["курс", "обучен", "образован", "school", "edtech", "урок", "репетитор"],
        "competition_level": "Умеренная",
        "competitors": [
            Competitor(
                name="Daryn.online / Bilimland",
                category="Школьный EdTech (Казахстан)",
                strengths="Интеграция со школьной программой, охват регионов, казахский язык",
                weaknesses="Низкая интерактивность, контент часто монологичный",
                price_point="Подписка 2000–5000 ₸/мес",
            ),
            Competitor(
                name="Skillbox / GeekBrains / Coursera",
                category="Профессиональное онлайн-образование",
                strengths="Сильные бренды, глубокие курсы, помощь в трудоустройстве",
                weaknesses="Низкий процент доходимости (<15%), высокая цена курсов",
                price_point="Рассрочка от $50/мес или курсы от $300–$1500",
            ),
        ],
        "differentiation": "Микро-обучение с AI-наставником, мгновенная обратная связь по домашним заданиям и персонализация темпа.",
        "barriers": ["Низкая доходимость студентов до конца", "Высокая стоимость привлечения (CAC)"],
    },
]


def _match_curated(business_input: BusinessInput) -> Optional[dict]:
    """Сопоставляет идею с курируемой базой по ключевым словам."""
    text = f"{business_input.name} {business_input.description} {business_input.target_audience}".lower()
    for item in CURATED_MARKET_DATABASE:
        for kw in item["keywords"]:
            if kw in text:
                return item
    return None


# ═══════════════════════════════════════════════════════════════
#  УРОВЕНЬ 2: Веб-поиск конкурентов (DuckDuckGo + fetch ценовых страниц)
# ═══════════════════════════════════════════════════════════════

# Домены агрегаторов-обзоров — не делаем fetch их страниц (цен там нет)
_NO_FETCH_DOMAINS = (
    "g2.com", "capterra.com", "alternativeto.net", "producthunt.com",
    "wikipedia.org", "habr.com", "vc.ru", "tjournal.ru", "medium.com",
    "forbes.com", "techcrunch.com",
)


def _extract_price_from_text(text: str) -> str:
    """Вытаскивает ценовое упоминание из текста (regex). Без API."""
    t = text.lower()
    patterns = [
        # $9.99/month, $ 10 / mo, $15 per month
        r"[$]\s*\d+[\d\.,]*\s*(?:/|per)?\s*(?:mo\.?|month|мес\.?|месяц)?",
        # 10 USD / month, USD 29
        r"\d+[\d\.,]*\s*usd\s*(?:/|per)?\s*(?:mo\.?|month)?",
        # €10/mo, £15 per month
        r"[€£₽]\s*\d+[\d\.,]*\s*(?:/|per)?\s*(?:mo\.?|month|мес\.?)?",
        # от 2 500 тенге в месяц / 1990 тг/мес
        r"от\s+\d[\d\s]*(?:₸|руб\.?|тг\.?|тенге)",
        r"\d[\d\s]*\s*(?:₸|руб\.?|тг\.?|тенге)\s*/?\s*(?:мес\.?|месяц)?",
        # freemium / free plan / бесплатно
        r"\bfreemium\b",
        r"\bfree(?:\s+plan|mium)?\b",
        r"\bбесплатно(?:\s+базов\w*)?\b",
        # Pricing mentioned
        r"\bfrom\s+[$€£]\s*\d+",
        r"\bstarting\s+at\s+[$€£]?\s*\d+",
    ]
    for p in patterns:
        m = re.search(p, t)
        if m:
            return m.group(0).strip()
    return ""


def _fetch_pricing_page(base_url_str: str, timeout: int = 4) -> str:
    """
    Пробует получить /pricing страницу продукта и вернуть текст для поиска цены.
    Не использует API ключи — только HTTP GET.
    """
    try:
        from bs4 import BeautifulSoup
        pricing_url = base_url_str.rstrip("/") + "/pricing"
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            ),
            "Accept-Language": "ru-RU,ru;q=0.9,en;q=0.8",
        }
        resp = requests.get(pricing_url, headers=headers, timeout=timeout, allow_redirects=True)
        if resp.status_code != 200:
            return ""
        soup = BeautifulSoup(resp.text[:25000], "lxml")
        for tag in soup(["script", "style", "nav", "footer"]):
            tag.decompose()
        # Мета + заголовки + первые параграфы
        parts = []
        meta = soup.find("meta", attrs={"name": "description"})
        if meta and meta.get("content"):
            parts.append(meta["content"][:200])
        for tag in soup.find_all(["h1", "h2", "h3", "p", "span"], limit=25):
            t = tag.get_text(separator=" ", strip=True)
            if t and len(t) > 5:
                parts.append(t[:150])
        return " ".join(parts)[:2000]
    except Exception as e:
        logger.debug(f"[market] fetch_pricing_page error {base_url_str}: {e}")
        return ""


def _search_web_competitors(business_input: BusinessInput) -> tuple:
    """
    Многозапросный бесплатный поиск конкурентов через DuckDuckGo.

    Выполняет 2-3 целевых запроса:
      1. «<название> <описание> конкуренты аналоги цена»
      2. «best <описание> alternatives pricing» (агрегаторы G2, Capterra)
      3. «<описание краткое> сервис тарифы подписка» (ценовые страницы)

    Для топ-3 нагрегаторных ссылок — пробует fetch /pricing страницы.

    Возвращает (raw_results_list, web_summary_text_for_llm).
    Токены НЕ тратятся — всё бесплатно.
    """
    results: List[dict] = []
    seen_domains: set = set()

    desc_short = (business_input.description or "")[:60]
    name = business_input.name or "стартап"

    queries = [
        f"{name} {desc_short} конкуренты аналоги цена",
        f"best {desc_short} alternatives pricing",
        f"{desc_short} сервис подписка тарифы стоимость",
    ]

    try:
        try:
            from ddgs import DDGS
        except ImportError:
            from duckduckgo_search import DDGS

        with DDGS() as ddgs:
            for q_idx, query in enumerate(queries):
                try:
                    hits = list(ddgs.text(query, max_results=4))
                    for h in hits:
                        url = h.get("href", "") or h.get("url", "")
                        title = (h.get("title", "") or "").strip()
                        body = (h.get("body", "") or "").strip()

                        if not title or not url:
                            continue

                        # Дедупликация по домену
                        try:
                            domain = re.sub(r"https?://(?:www\.)?", "", url).split("/")[0]
                        except Exception:
                            domain = url[:40]
                        if domain in seen_domains:
                            continue
                        seen_domains.add(domain)

                        price_hint = _extract_price_from_text(body)
                        results.append({
                            "title": title[:120],
                            "url": url,
                            "domain": domain,
                            "snippet": body[:350],
                            "price_hint": price_hint,
                        })

                    # Пауза между запросами — DDG rate limit
                    if q_idx < len(queries) - 1:
                        time.sleep(1.2)

                except Exception as eq:
                    logger.debug(f"[market] DDG query {q_idx} error: {eq}")
                    continue

    except Exception as e:
        logger.warning(f"[market] DuckDuckGo полностью недоступен: {e}")

    # Для первых 3 нагрегаторных результатов — fetch /pricing страницы
    fetch_count = 0
    for item in results:
        if fetch_count >= 3:
            break
        if any(nd in item["domain"] for nd in _NO_FETCH_DOMAINS):
            continue  # Агрегаторы — пропускаем
        if item["price_hint"]:
            fetch_count += 1
            continue  # Цена уже есть в сниппете

        # Строим базовый URL из домена
        base = f"https://{item['domain']}"
        page_text = _fetch_pricing_page(base, timeout=4)
        if page_text:
            found = _extract_price_from_text(page_text)
            if found:
                item["price_hint"] = found
                # Добавляем ценовой контекст в сниппет для LLM
                item["snippet"] = (item["snippet"] + " [pricing page]: " + page_text[:200])[:550]
        fetch_count += 1

    # Формируем компактный текст для LLM промпта (не более ~600 токенов)
    summary_lines = []
    for r in results[:6]:
        price_str = f" | Цена в интернете: {r['price_hint']}" if r["price_hint"] else ""
        summary_lines.append(
            f"• [{r['title']}]({r['url']}){price_str}\n  {r['snippet'][:200]}"
        )
    summary_text = "\n".join(summary_lines) if summary_lines else ""
    return results, summary_text


# ═══════════════════════════════════════════════════════════════
#  УРОВЕНЬ 3: LLM-синтез структурированного отчёта
# ═══════════════════════════════════════════════════════════════

def analyze_market_competitors(business_input: BusinessInput) -> MarketResearchReport:
    """
    3-уровневый анализ конкурентов:
    1. Курируемая база (мгновенно, 0 токенов)
    2. DuckDuckGo + fetch /pricing (бесплатно, 0 токенов)
    3. Один LLM-вызов с богатым контекстом из веба (~700 токенов ответ)

    Деградация: если LLM недоступен → курируемая база → дефолт.
    """
    curated = _match_curated(business_input)
    web_results, web_summary = _search_web_competitors(business_input)

    # ── Уровень 3: LLM синтез ────────────────────────────────────────
    import config as _cfg
    from openai import OpenAI

    best_key = _cfg.get_best_key_and_wait()
    base_url = os.environ.get("OPENAI_BASE_URL", _cfg.BASE_URL)
    model = os.environ.get("OPENAI_MODEL", _cfg.MODEL)

    if best_key and best_key != "your_api_key_here":
        try:
            client = OpenAI(api_key=best_key, base_url=base_url) if base_url else OpenAI(api_key=best_key)

            # Компактный контекст из курируемой базы
            curated_context = ""
            if curated:
                names = ", ".join(c.name for c in curated["competitors"])
                curated_context = f"Известные игроки в этой категории: {names}.\n"

            # Веб-контекст из DuckDuckGo (с реальными ценами если нашли)
            web_context = ""
            if web_summary:
                web_context = (
                    "Данные из интернета (реальный поиск, сегодня):\n"
                    + web_summary
                )
            elif curated:
                web_context = ""  # Используем только куратуру

            user_prompt = f"""ПРОЕКТ ДЛЯ АНАЛИЗА:
Название: {business_input.name}
Описание: {business_input.description}
Целевая аудитория: {business_input.target_audience}
Страна: {business_input.country}
Монетизация: {business_input.revenue_model.value}, ~${business_input.get_effective_price():.2f}/мес

{curated_context}{web_context}

ЗАДАЧА: На основе данных выше определи 3-4 реальных конкурента с их актуальными ценами.
Используй данные из интернета приоритетно. Если цена найдена в веб-данных — укажи её точно.
Если цены нет — укажи модель («freemium», «по запросу», «$X/мес» с диапазоном).

Верни СТРОГО JSON (без markdown):
{{
  "competition_level": "Низкая|Умеренная|Высокая|Олигополия",
  "summary": "2-3 предложения о конкурентной среде",
  "differentiation_strategy": "Как стартап может выиграть у конкурентов",
  "entry_barriers": ["Барьер 1", "Барьер 2"],
  "competitors": [
    {{
      "name": "Реальное название",
      "category": "Прямой|Косвенный|Заменитель",
      "strengths": "Сильные стороны",
      "weaknesses": "Слабые стороны / уязвимости",
      "price_point": "Точная цена из данных или диапазон"
    }}
  ]
}}
Ответ строго на русском языке."""

            resp = client.chat.completions.create(
                model=model,
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "Ты — венчурный аналитик. Называй ТОЛЬКО реальные компании. "
                            "Цены бери из предоставленных веб-данных, не придумывай. "
                            "Если веб-данные содержат цену — используй её дословно."
                        ),
                    },
                    {"role": "user", "content": user_prompt},
                ],
                temperature=0.2,
                max_tokens=900,
                response_format={"type": "json_object"},
            )

            raw = resp.choices[0].message.content.strip()
            data = json.loads(raw)

            competitor_objs = []
            for item in data.get("competitors", []):
                competitor_objs.append(
                    Competitor(
                        name=item.get("name", "Конкурент"),
                        category=item.get("category", "Прямой конкурент"),
                        strengths=item.get("strengths", ""),
                        weaknesses=item.get("weaknesses", ""),
                        price_point=item.get("price_point", ""),
                    )
                )

            return MarketResearchReport(
                competition_level=data.get("competition_level", "Умеренная"),
                competitors=competitor_objs,
                differentiation_strategy=data.get("differentiation_strategy", ""),
                entry_barriers=data.get("entry_barriers", []),
                summary=data.get("summary", ""),
                web_sources=[r["url"] for r in web_results[:4]] if web_results else [],
            )

        except Exception as e:
            logger.warning(f"[market] LLM анализ рынка ошибка: {e}. Fallback.")

    # ── Fallback: курируемая база ─────────────────────────────────────
    if curated:
        return MarketResearchReport(
            competition_level=curated["competition_level"],
            competitors=curated["competitors"],
            differentiation_strategy=curated["differentiation"],
            entry_barriers=curated["barriers"],
            summary="На рынке присутствуют устоявшиеся игроки. Ключевой вызов — дифференциация и преодоление привычек пользователей.",
            web_sources=[],
        )

    # ── Дефолтный fallback ────────────────────────────────────────────
    return MarketResearchReport(
        competition_level="Умеренная",
        competitors=[
            Competitor(
                name="Excel / Ручной труд / Самодельные решения",
                category="Привычный заменитель (Status Quo)",
                strengths="Бесплатно, привычно, не требует обучения",
                weaknesses="Медленно, ошибки человеческого фактора, нет автоматизации",
                price_point="0 $ (время пользователя)",
            ),
            Competitor(
                name="Крупные игроки смежных рынков",
                category="Косвенные конкуренты",
                strengths="Репутация, доверие, готовая аудитория",
                weaknesses="Перегруженный интерфейс, медленная адаптация под узкие ниши",
                price_point="Высокий ценовой сегмент",
            ),
        ],
        differentiation_strategy="Фокус на специализированном решении конкретной боли ЦА с простым UX.",
        entry_barriers=["Инертность аудитории и привычка решать проблему старыми методами"],
        summary="Прямых монополистов в узкой нише не обнаружено. Основной конкурент — текущий статус-кво пользователей.",
        web_sources=[],
    )
