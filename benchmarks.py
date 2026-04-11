"""
benchmarks.py — База отраслевых бенчмарков + страновые модификаторы.
Статические данные (фаллбак): OpenView 2025, Bessemer Cloud Index, Baremetrics, ProfitWell,
           World Bank 2025, DataReportal 2025, Meta Ads Benchmarks 2025.
Динамические данные: DuckDuckGo поиск + Google Gemini синтез (2025–2026).
"""

import json
import logging
import os


from models import (
    BusinessType, IndustryBenchmark, BenchmarkRange,
    CountryModifier
)

logger = logging.getLogger(__name__)

# ═══════════════════════════════════════════════════════════════
#  3.1 BENCHMARKS — словарь BusinessType → IndustryBenchmark
# ═══════════════════════════════════════════════════════════════

BENCHMARKS: dict[BusinessType, IndustryBenchmark] = {

    BusinessType.SAAS_B2B: IndustryBenchmark(
        business_type=BusinessType.SAAS_B2B,
        display_name="SaaS B2B",
        conversion_trial_to_paid=BenchmarkRange(low=0.03, median=0.07, high=0.15),
        monthly_churn=BenchmarkRange(low=0.02, median=0.05, high=0.08),
        cac=BenchmarkRange(low=200.0, median=400.0, high=800.0),
        gross_margin=BenchmarkRange(low=0.65, median=0.75, high=0.85),
        avg_months_to_first_revenue=3,
        failure_rate_12_months=0.60,
        typical_ltv_cac_ratio=BenchmarkRange(low=1.5, median=3.5, high=6.0),
        source="OpenView 2024 SaaS Benchmarks, Bessemer Cloud Index",
    ),

    BusinessType.SAAS_B2C: IndustryBenchmark(
        business_type=BusinessType.SAAS_B2C,
        display_name="SaaS B2C",
        conversion_trial_to_paid=BenchmarkRange(low=0.02, median=0.04, high=0.08),
        monthly_churn=BenchmarkRange(low=0.04, median=0.067, high=0.12),
        cac=BenchmarkRange(low=20.0, median=50.0, high=120.0),
        gross_margin=BenchmarkRange(low=0.55, median=0.68, high=0.80),
        avg_months_to_first_revenue=2,
        failure_rate_12_months=0.68,
        typical_ltv_cac_ratio=BenchmarkRange(low=1.0, median=2.5, high=5.0),
        source="Baremetrics Open Benchmarks, ProfitWell 2024",
    ),

    BusinessType.MARKETPLACE: IndustryBenchmark(
        business_type=BusinessType.MARKETPLACE,
        display_name="Marketplace",
        conversion_trial_to_paid=BenchmarkRange(low=0.01, median=0.025, high=0.05),
        monthly_churn=BenchmarkRange(low=0.03, median=0.06, high=0.10),
        cac=BenchmarkRange(low=30.0, median=70.0, high=150.0),
        gross_margin=BenchmarkRange(low=0.12, median=0.20, high=0.30),
        avg_months_to_first_revenue=4,
        failure_rate_12_months=0.72,
        typical_ltv_cac_ratio=BenchmarkRange(low=0.8, median=2.0, high=4.0),
        source="a16z Marketplace 100, CB Insights 2024",
    ),

    BusinessType.ECOMMERCE: IndustryBenchmark(
        business_type=BusinessType.ECOMMERCE,
        display_name="E-Commerce",
        conversion_trial_to_paid=BenchmarkRange(low=0.015, median=0.03, high=0.06),
        monthly_churn=BenchmarkRange(low=0.0, median=0.0, high=0.0),  # не подписка
        cac=BenchmarkRange(low=10.0, median=35.0, high=80.0),
        gross_margin=BenchmarkRange(low=0.25, median=0.40, high=0.55),
        avg_months_to_first_revenue=1,
        failure_rate_12_months=0.65,
        typical_ltv_cac_ratio=BenchmarkRange(low=1.0, median=2.5, high=5.0),
        source="Shopify Commerce Report 2024, Statista E-Commerce",
    ),

    BusinessType.MOBILE_APP: IndustryBenchmark(
        business_type=BusinessType.MOBILE_APP,
        display_name="Mobile App (Freemium)",
        conversion_trial_to_paid=BenchmarkRange(low=0.01, median=0.025, high=0.05),
        monthly_churn=BenchmarkRange(low=0.06, median=0.10, high=0.20),
        cac=BenchmarkRange(low=2.0, median=5.0, high=15.0),
        gross_margin=BenchmarkRange(low=0.55, median=0.70, high=0.85),
        avg_months_to_first_revenue=2,
        failure_rate_12_months=0.75,
        typical_ltv_cac_ratio=BenchmarkRange(low=0.8, median=2.0, high=4.5),
        source="AppsFlyer Mobile Index 2024, Sensor Tower",
    ),

    BusinessType.EDTECH: IndustryBenchmark(
        business_type=BusinessType.EDTECH,
        display_name="EdTech",
        conversion_trial_to_paid=BenchmarkRange(low=0.03, median=0.06, high=0.12),
        monthly_churn=BenchmarkRange(low=0.05, median=0.08, high=0.14),
        cac=BenchmarkRange(low=30.0, median=80.0, high=200.0),
        gross_margin=BenchmarkRange(low=0.60, median=0.75, high=0.90),
        avg_months_to_first_revenue=3,
        failure_rate_12_months=0.62,
        typical_ltv_cac_ratio=BenchmarkRange(low=1.5, median=3.0, high=6.0),
        source="HolonIQ EdTech Report 2024, Class Central",
    ),

    BusinessType.FINTECH: IndustryBenchmark(
        business_type=BusinessType.FINTECH,
        display_name="FinTech",
        conversion_trial_to_paid=BenchmarkRange(low=0.02, median=0.04, high=0.08),
        monthly_churn=BenchmarkRange(low=0.02, median=0.05, high=0.09),
        cac=BenchmarkRange(low=50.0, median=120.0, high=300.0),
        gross_margin=BenchmarkRange(low=0.45, median=0.60, high=0.75),
        avg_months_to_first_revenue=4,
        failure_rate_12_months=0.70,
        typical_ltv_cac_ratio=BenchmarkRange(low=1.0, median=2.5, high=5.0),
        source="CB Insights FinTech Report 2024, Plaid",
    ),

    BusinessType.AGENCY: IndustryBenchmark(
        business_type=BusinessType.AGENCY,
        display_name="Agency / Services",
        conversion_trial_to_paid=BenchmarkRange(low=0.08, median=0.15, high=0.25),
        monthly_churn=BenchmarkRange(low=0.04, median=0.07, high=0.12),
        cac=BenchmarkRange(low=100.0, median=250.0, high=600.0),
        gross_margin=BenchmarkRange(low=0.35, median=0.50, high=0.65),
        avg_months_to_first_revenue=2,
        failure_rate_12_months=0.55,
        typical_ltv_cac_ratio=BenchmarkRange(low=1.5, median=3.0, high=6.0),
        source="Agency Analytics Report 2024, Clutch.co",
    ),

    BusinessType.GIG_ECONOMY: IndustryBenchmark(
        business_type=BusinessType.GIG_ECONOMY,
        display_name="Gig Economy / Freelance Platform",
        conversion_trial_to_paid=BenchmarkRange(low=0.04, median=0.10, high=0.22),
        monthly_churn=BenchmarkRange(low=0.05, median=0.09, high=0.16),
        cac=BenchmarkRange(low=15.0, median=40.0, high=100.0),
        gross_margin=BenchmarkRange(low=0.55, median=0.70, high=0.82),
        avg_months_to_first_revenue=1,
        failure_rate_12_months=0.68,
        typical_ltv_cac_ratio=BenchmarkRange(low=1.2, median=2.5, high=5.0),
        source="Upwork 2024 Annual Report, Fiverr 2024 Investor Presentation, Freelancer.com",
    ),
}


# ═══════════════════════════════════════════════════════════════
#  3.2 COUNTRY_MODIFIERS
# ═══════════════════════════════════════════════════════════════
#
# Методология:
# price_sensitivity = GDP per capita страны / GDP per capita USA (World Bank 2024)
#   KZ: $14 155 / $84 534 = 0.167 ≈ 0.17
#   RU: $14 889 / $84 534 = 0.176 ≈ 0.18
# cac_multiplier = CPM страны / CPM USA (Meta Ads Benchmarks 2024)
#   KZ: ~$0.75 CPM / $12.5 CPM ≈ 0.08
#   RU: ~$2.25 CPM / $12.5 CPM ≈ 0.15
# market_size = internet users страны / internet users USA
#   KZ: 18.19M / 331M ≈ 0.055 (DataReportal 2024)
#   RU: 116M / 331M ≈ 0.35
# payment_conversion: e-commerce penetration + платёжные системы

COUNTRY_MODIFIERS: dict[str, CountryModifier] = {
    "usa": CountryModifier(
        country="usa",
        price_sensitivity_multiplier=1.0,
        cac_multiplier=1.0,
        market_size_multiplier=1.0,
        payment_conversion_modifier=1.0,
    ),
    "kazakhstan": CountryModifier(
        country="kazakhstan",
        price_sensitivity_multiplier=0.17,
        cac_multiplier=0.08,
        market_size_multiplier=0.055,
        payment_conversion_modifier=0.72,
    ),
    "russia": CountryModifier(
        country="russia",
        price_sensitivity_multiplier=0.18,
        cac_multiplier=0.15,
        market_size_multiplier=0.35,
        payment_conversion_modifier=0.70,
    ),
    "global": CountryModifier(
        country="global",
        price_sensitivity_multiplier=1.0,
        cac_multiplier=1.0,
        market_size_multiplier=1.0,
        payment_conversion_modifier=1.0,
    ),
}


# ═══════════════════════════════════════════════════════════════
#  3.3 Функции доступа к данным
# ═══════════════════════════════════════════════════════════════

def get_benchmark(business_type: BusinessType) -> IndustryBenchmark:
    """Возвращает бенчмарк для указанного типа бизнеса."""
    return BENCHMARKS[business_type]


def get_country_modifier(country: str) -> CountryModifier:
    """
    Возвращает страновой модификатор.
    Если страна не найдена — возвращает 'global'.
    """
    return COUNTRY_MODIFIERS.get(country.lower(), COUNTRY_MODIFIERS["global"])


def get_adjusted_cac(business_type: BusinessType, country: str) -> BenchmarkRange:
    """
    Возвращает CAC, скорректированный на страновой cac_multiplier.
    Умножает low / median / high на cac_multiplier страны.
    """
    bench = get_benchmark(business_type)
    modifier = get_country_modifier(country)
    m = modifier.cac_multiplier
    return BenchmarkRange(
        low=bench.cac.low * m,
        median=bench.cac.median * m,
        high=bench.cac.high * m,
    )



# ═══════════════════════════════════════════════════════════════
#  3.4  Надёжное обновление бенчмарков
#  Источники (без LLM, без поисковиков, без галлюцинаций):
#    1. World Bank API  — ВВП на душу населения → страновая калибровка
#    2. Прямой fetch известных URL публичных отчётов → regex-парсинг чисел
#    3. Файловый кэш 7 дней (TTL_SECONDS)
#    4. Curated-статика как гарантированный fallback
# ═══════════════════════════════════════════════════════════════

import time
import hashlib
import re
import tempfile
from pathlib import Path
from typing import Optional

try:
    import requests as _requests
    _REQUESTS_OK = True
except ImportError:
    _REQUESTS_OK = False

# ── Кэш ─────────────────────────────────────────────────────────
_CACHE_TTL = 7 * 24 * 3600          # 7 дней в секундах
_CACHE_DIR = Path(tempfile.gettempdir()) / "startup_sim_bench_cache"

def _cache_load(key: str) -> Optional[dict]:
    """Возвращает данные из кэша если они свежее TTL, иначе None."""
    _CACHE_DIR.mkdir(parents=True, exist_ok=True)
    f = _CACHE_DIR / f"{hashlib.md5(key.encode()).hexdigest()}.json"
    if f.exists():
        try:
            blob = json.loads(f.read_text())
            if time.time() - blob.get("ts", 0) < _CACHE_TTL:
                return blob.get("data")
        except Exception:
            pass
    return None

def _cache_save(key: str, data: dict) -> None:
    _CACHE_DIR.mkdir(parents=True, exist_ok=True)
    f = _CACHE_DIR / f"{hashlib.md5(key.encode()).hexdigest()}.json"
    f.write_text(json.dumps({"ts": time.time(), "data": data}))


# ── 1. World Bank GDP per capita ─────────────────────────────────
# Официальный REST API Всемирного банка. Бесплатно, без ключа.
# Документация: https://datahelpdesk.worldbank.org/knowledgebase/articles/898581

_WB_ISO2 = {
    "kazakhstan": "KZ",
    "russia":     "RU",
    "usa":        "US",
    "global":     "WLD",  # World average
}

# Статичные значения ВВП (World Bank 2023, актуализируются через API)
_GDP_FALLBACK = {
    "kazakhstan": 14155.0,
    "russia":     14889.0,
    "usa":        84534.0,
    "global":     13574.0,
}

def _fetch_world_bank_gdp(country: str) -> tuple[float, str]:
    """
    Получает ВВП на душу населения (USD) из World Bank API.
    Возвращает (gdp_value, source_label).
    При ошибке — статичное значение + пометка.
    Кэширует на 7 дней (данные меняются раз в год).
    """
    country_key = country.lower()
    iso2 = _WB_ISO2.get(country_key, "WLD")
    cache_key = f"wb_gdp_{iso2}"

    cached = _cache_load(cache_key)
    if cached:
        return cached["gdp"], cached["source"] + " [кэш]"

    fallback_gdp = _GDP_FALLBACK.get(country_key, _GDP_FALLBACK["global"])

    if not _REQUESTS_OK:
        return fallback_gdp, "World Bank 2023 (статика — пакет requests не установлен)"

    url = (
        f"https://api.worldbank.org/v2/country/{iso2}"
        f"/indicator/NY.GDP.PCAP.CD?format=json&mrv=1&per_page=1"
    )
    try:
        resp = _requests.get(url, timeout=8)
        resp.raise_for_status()
        data = resp.json()
        # Структура: [metadata, [{"value": 14155.0, "date": "2023"}, ...]]
        if (
            isinstance(data, list)
            and len(data) > 1
            and isinstance(data[1], list)
            and data[1]
            and data[1][0].get("value") is not None
        ):
            gdp = float(data[1][0]["value"])
            year = data[1][0].get("date", "?")
            source = f"World Bank API — ВВП/кап. {iso2} {year}: ${gdp:,.0f}"
            _cache_save(cache_key, {"gdp": gdp, "source": source})
            logger.info(f"World Bank GDP: {iso2} = ${gdp:,.0f} ({year})")
            return gdp, source
    except Exception as e:
        logger.warning(f"World Bank API недоступен ({e}). Используем статику.")

    return fallback_gdp, f"World Bank 2023 (статика, API временно недоступен): ${fallback_gdp:,.0f}"


# ── 2. Прямой fetch авторитетных страниц ─────────────────────────
# Парсим КОНКРЕТНЫЕ известные страницы с числовыми данными.
# regex-паттерны настроены под конкретную структуру страниц.
# Без LLM — только регулярные выражения.

# Известные авторитетные источники (публичные страницы, без paywall)
_AUTHORITATIVE_URLS: dict[BusinessType, list[str]] = {
    BusinessType.SAAS_B2B: [
        "https://openviewpartners.com/saas-benchmarks/",
        "https://chartmogul.com/reports/saas-growth-report/",
    ],
    BusinessType.SAAS_B2C: [
        "https://baremetrics.com/saas-metrics-benchmarks",
        "https://chartmogul.com/reports/saas-growth-report/",
    ],
    BusinessType.MARKETPLACE: [
        "https://a16z.com/marketplace-100/",
    ],
    BusinessType.GIG_ECONOMY: [
        # Upwork — публичная компания (NASDAQ: UPWK), публикует метрики
        "https://investors.upwork.com/news-releases/news-release-details/",
        "https://www.fiverr.com/press",
    ],
    BusinessType.FINTECH: [
        "https://www.cbinsights.com/research/fintech-trends/",
    ],
    BusinessType.EDTECH: [
        "https://www.holoniq.com/notes/global-edtech-2024-facts-figures/",
    ],
    BusinessType.MOBILE_APP: [
        "https://www.appsflyer.com/resources/reports/mobile-benchmark/",
    ],
    BusinessType.ECOMMERCE: [
        "https://www.shopify.com/research",
    ],
    BusinessType.AGENCY: [
        "https://agencyanalytics.com/blog/agency-benchmarks",
    ],
}

# Паттерны для извлечения числовых метрик из HTML текста
_CHURN_PATTERNS = [
    re.compile(r"(\d+(?:\.\d+)?)\s*%\s*(?:monthly|ежемесячный)?\s*churn", re.I),
    re.compile(r"churn\s*(?:rate)?\s*(?:of|:)?\s*(\d+(?:\.\d+)?)\s*%", re.I),
    re.compile(r"(\d+(?:\.\d+)?)\s*%\s*(?:customer|subscriber)\s*churn", re.I),
]
_CONVERSION_PATTERNS = [
    re.compile(r"(\d+(?:\.\d+)?)\s*%\s*(?:trial.to.paid|free.to.paid|conversion)", re.I),
    re.compile(r"conversion\s*rate\s*(?:of|:)?\s*(\d+(?:\.\d+)?)\s*%", re.I),
]

def _extract_pct(text: str, patterns: list) -> Optional[float]:
    """Извлекает первое процентное значение из текста по паттернам."""
    for pat in patterns:
        m = pat.search(text)
        if m:
            try:
                val = float(m.group(1)) / 100.0
                if 0.001 < val < 0.99:  # санитарная проверка
                    return val
            except ValueError:
                continue
    return None

def _fetch_page_metrics(business_type: BusinessType) -> Optional[dict]:
    """
    Пытается извлечь числовые метрики с авторитетных страниц.
    Возвращает частичный словарь {churn, conversion, source} или None.
    """
    if not _REQUESTS_OK:
        return None

    urls = _AUTHORITATIVE_URLS.get(business_type, [])
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (compatible; StartupValidator/1.0; "
            "+https://github.com/startup-validator)"
        )
    }

    for url in urls[:2]:  # пробуем первые 2 URL
        cache_key = f"page_{hashlib.md5(url.encode()).hexdigest()}"
        cached = _cache_load(cache_key)
        if cached:
            logger.info(f"Page metrics from cache: {url}")
            return cached

        try:
            resp = _requests.get(url, timeout=10, headers=headers)
            if resp.status_code != 200:
                continue

            # Используем только текстовый контент (без HTML-тегов)
            try:
                from bs4 import BeautifulSoup
                text = BeautifulSoup(resp.text, "html.parser").get_text(" ", strip=True)
            except ImportError:
                # Простое удаление HTML-тегов без bs4
                text = re.sub(r"<[^>]+>", " ", resp.text)

            churn = _extract_pct(text, _CHURN_PATTERNS)
            conversion = _extract_pct(text, _CONVERSION_PATTERNS)

            if churn or conversion:
                result = {
                    "churn": churn,
                    "conversion": conversion,
                    "source": url,
                }
                _cache_save(cache_key, result)
                logger.info(f"Page metrics parsed: {url} → churn={churn}, conv={conversion}")
                return result

        except Exception as e:
            logger.warning(f"Не удалось получить {url}: {e}")
            continue

    return None


# ── 3. Главная функция — заменяет fetch_realtime_benchmarks ──────

def fetch_calibrated_benchmarks(
    business_type: BusinessType,
    country: str,
    description: str = "",
) -> tuple[IndustryBenchmark, str]:
    """
    Получает откалиброванные бенчмарки из авторитетных источников.

    Алгоритм (без LLM, без поисковиков):
      1. World Bank API  → актуальный ВВП → пересчитывает CAC и price_sensitivity
      2. Прямой fetch известных страниц → regex → churn/conversion если нашли
      3. Curated-статика (BENCHMARKS) как база и гарантированный fallback

    Данные кэшируются на 7 дней → нет rate limit, нет повторных запросов.

    Returns:
        (IndustryBenchmark, source_description)
    """
    base = BENCHMARKS[business_type]
    sources_used: list[str] = []

    # ── Шаг 1: World Bank GDP → страновая калибровка CAC ─────────
    gdp, wb_source = _fetch_world_bank_gdp(country)
    us_gdp = _GDP_FALLBACK["usa"]  # baseline
    gdp_ratio = min(max(gdp / us_gdp, 0.03), 1.0)  # от 3% до 100% от US
    sources_used.append(wb_source)

    # CAC пропорционален CPM рекламы — а CPM коррелирует с ВВП
    # Используем gdp_ratio для более точной страновой калибровки
    cac_multiplier = gdp_ratio ** 0.6  # степень < 1: нелинейная зависимость
    calibrated_cac = BenchmarkRange(
        low=round(base.cac.low * cac_multiplier, 2),
        median=round(base.cac.median * cac_multiplier, 2),
        high=round(base.cac.high * cac_multiplier, 2),
    )

    # price_sensitivity тоже от ВВП (линейно)
    price_sens = round(gdp_ratio, 3)

    # ── Шаг 2: Прямой fetch авторитетных страниц ─────────────────
    page_data = _fetch_page_metrics(business_type)

    # Берём из страниц только если нашли; иначе — статика из отчётов
    if page_data and page_data.get("churn"):
        raw_churn = page_data["churn"]
        # Медиана из страницы; low/high ±50% от неё (широкий диапазон надёжнее)
        calibrated_churn = BenchmarkRange(
            low=round(raw_churn * 0.6, 4),
            median=round(raw_churn, 4),
            high=round(raw_churn * 1.5, 4),
        )
        sources_used.append(f"Прямой парсинг: {page_data['source']}")
    else:
        calibrated_churn = base.monthly_churn
        sources_used.append(base.source)

    if page_data and page_data.get("conversion"):
        raw_conv = page_data["conversion"]
        calibrated_conv = BenchmarkRange(
            low=round(raw_conv * 0.5, 4),
            median=round(raw_conv, 4),
            high=round(raw_conv * 2.0, 4),
        )
    else:
        calibrated_conv = base.conversion_trial_to_paid

    # ── Шаг 3: Сборка итогового бенчмарка ────────────────────────
    result = IndustryBenchmark(
        business_type=business_type,
        display_name=base.display_name,
        conversion_trial_to_paid=calibrated_conv,
        monthly_churn=calibrated_churn,
        cac=calibrated_cac,
        gross_margin=base.gross_margin,          # маржа из curated-отчётов
        avg_months_to_first_revenue=base.avg_months_to_first_revenue,
        failure_rate_12_months=base.failure_rate_12_months,
        typical_ltv_cac_ratio=base.typical_ltv_cac_ratio,
        source=" | ".join(dict.fromkeys(sources_used)),  # дедупликация
    )

    source_info = (
        f"✅ World Bank GDP {country.upper()}: ${gdp:,.0f}/кап. "
        f"(CAC-калибровка: ×{cac_multiplier:.2f})"
    )
    if page_data:
        source_info += f" | Парсинг: {page_data['source']}"
    else:
        source_info += f" | База: {base.source[:60]}"

    logger.info(f"fetch_calibrated_benchmarks: {business_type.value}/{country} — {source_info}")
    return result, source_info


# ── Обратная совместимость ────────────────────────────────────────
# Старое имя → новая функция (чтобы не переписывать main.py)
def fetch_realtime_benchmarks(
    business_type: BusinessType,
    country: str,
    description: str = "",
) -> tuple[IndustryBenchmark, str]:
    """Алиас для обратной совместимости. Делегирует в fetch_calibrated_benchmarks."""
    return fetch_calibrated_benchmarks(business_type, country, description)
