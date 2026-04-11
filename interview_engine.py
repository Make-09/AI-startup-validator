"""
interview_engine.py — Проведение AI-интервью через Google Gemini API.
Mom Test методология с двухфазным интервью:
  Фаза 1 (Discovery): персона НЕ знает о продукте — отвечает из личного опыта.
  Фаза 2 (Exposure):  персоне представляют продукт — оценивает его полезность.
Интервью запускаются последовательно, без параллельных запросов к API.
"""

import json
import logging
import os
import random
import time
from typing import List, Optional

from openai import OpenAI
try:
    from ddgs import DDGS
except ImportError:
    from duckduckgo_search import DDGS

from models import BusinessInput, InterviewQuestion, InterviewResponse, Persona, RevenueModel

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════
#  Специальные исключения
# ═══════════════════════════════════════════════════════════════

class QuotaExceededError(Exception):
    """API ключ исчерпал лимит токенов/запросов."""
    pass


# ═══════════════════════════════════════════════════════════════
#  LLM — Google Gemini API (ленивая инициализация)
# ═══════════════════════════════════════════════════════════════

_LLM_MODEL = "llama-3.3-70b-versatile"
_LLM_NAME_VALUE = "Не инициализирован"

def get_llm() -> OpenAI:
    """Возвращает инициализированный клиент OpenAI с автовыбором наилучшего ключа из пула."""
    import config as _cfg
    best_key = _cfg.get_best_key_and_wait()
    base_url = os.environ.get("OPENAI_BASE_URL", _cfg.BASE_URL)
    model = os.environ.get("OPENAI_MODEL", _cfg.MODEL)
    
    global _LLM_MODEL, _LLM_NAME_VALUE
    _LLM_MODEL = model
    _LLM_NAME_VALUE = f"LLM ({model})"
    
    if not best_key:
        raise ValueError(
            "OPENAI_API_KEY не установлен. "
            "Добавьте ключи в Streamlit Secrets или переменные окружения."
        )
        
    if base_url:
        return OpenAI(api_key=best_key, base_url=base_url)
    return OpenAI(api_key=best_key)

def get_llm_name() -> str:
    """Возвращает название активной модели."""
    return _LLM_NAME_VALUE

def reset_llm():
    """Сбрасывает LLM для переинициализации (оставлено для совместимости; инициализация теперь динамическая)."""
    pass


# ═══════════════════════════════════════════════════════════════
#  Mom Test вопросы — ФАЗА 1: Discovery (без знания о продукте)
# ═══════════════════════════════════════════════════════════════

MOM_TEST_QUESTIONS_PHASE1: List[InterviewQuestion] = [
    InterviewQuestion(
        category="problem",
        question=(
            "Расскажите о последнем разе, когда вы столкнулись с этой ситуацией. "
            "Что конкретно произошло и как вы с этим справились?"
        ),
    ),
    InterviewQuestion(
        category="impact",
        question=(
            "Насколько серьёзной была эта проблема для вас? "
            "Сколько времени или денег вы на это потратили в последний раз?"
        ),
    ),
    InterviewQuestion(
        category="spending",
        question=(
            "Вы когда-либо платили за решение этой проблемы — инструмент, сервис, "
            "специалиста? Расскажите об этом опыте."
        ),
    ),
    InterviewQuestion(
        category="competition",
        question=(
            "Что вы пробовали раньше чтобы решить это? "
            "Что сработало, а что нет — и почему?"
        ),
    ),
]

# ═══════════════════════════════════════════════════════════════
#  Mom Test вопросы — ФАЗА 2: Exposure (после знакомства с продуктом)
# ═══════════════════════════════════════════════════════════════

MOM_TEST_QUESTIONS_PHASE2: List[InterviewQuestion] = [
    InterviewQuestion(
        category="fit",
        question=(
            "Если бы это существовало тогда, когда вы рассказывали мне о той ситуации — "
            "изменило бы это что-то для вас? Объясните."
        ),
    ),
    InterviewQuestion(
        category="pricing",
        question=(
            "Вы упоминали что тратили [время/деньги] на эту проблему. "
            "Стоимость этого решения — она соответствует тому, что вы уже тратите?"
        ),
    ),
    InterviewQuestion(
        category="behavior",
        question=(
            "Что должно было бы произойти, чтобы вы начали пользоваться этим на регулярной основе? "
            "Есть ли что-то, что могло бы вас остановить?"
        ),
    ),
]

# Объединённый список для совместимости (сохраняем для агрегатора)
MOM_TEST_QUESTIONS: List[InterviewQuestion] = (
    MOM_TEST_QUESTIONS_PHASE1 + MOM_TEST_QUESTIONS_PHASE2
)


# ═══════════════════════════════════════════════════════════════
#  Системный промпт
# ═══════════════════════════════════════════════════════════════

def _make_persona_system(persona: "Persona", country_name: str, personality_desc: str, language: str = "Русский") -> str:
    """
    Системный промпт — задаёт роль СИМУЛЯТОРА и описание персоны.
    Модель должна симулировать поведение этого человека, не будучи им.
    """
    # Собираем только непустые части профиля
    profile_parts = []

    if persona.city:
        profile_parts.append(f"Город: {persona.city}.")
    else:
        profile_parts.append(f"Страна: {country_name}.")

    if persona.family_status:
        profile_parts.append(f"Семья: {persona.family_status}.")

    profile_parts.append(f"Занятость: {persona.occupation}, доход ~${persona.monthly_income:.0f}/мес.")

    if persona.work_context:
        profile_parts.append(f"Рабочий контекст: {persona.work_context}.")

    if persona.daily_routine:
        profile_parts.append(f"Обычный день: {persona.daily_routine}.")

    if persona.financial_behavior:
        profile_parts.append(f"Финансы: {persona.financial_behavior}.")

    if persona.apps_used:
        profile_parts.append(f"Приложения: {persona.apps_used}.")

    if persona.backstory:
        profile_parts.append(f"О себе: {persona.backstory}.")

    if persona.communication_style:
        comm = persona.communication_style
    else:
        comm = personality_desc

    profile_text = " ".join(profile_parts)

    # Определяем грамматический род для согласованности
    # Используем имя из казахстанских/русских женских списков или LLM-сгенерированный gender
    gender_hint = ""
    name_lower = persona.name.lower()
    female_endings = ("а", "я", "м", "ль")
    known_female = {"айгерим", "мадина", "жанна", "камила", "динара", "аяулым", "назерке",
                    "томирис", "дана", "айнур", "мария", "елена", "ольга", "анна", "юлия",
                    "наталья", "татьяна", "emily", "sarah", "jessica", "amanda", "ashley",
                    "sophia", "olivia", "elena", "fatima", "olga", "priya", "yuki"}
    known_male = {"нурлан", "дамир", "арман", "тимур", "ерлан", "бауыржан", "данияр",
                  "асет", "мирас", "алихан", "алексей", "иван", "дмитрий", "сергей",
                  "михаил", "андрей", "владимир", "павел", "james", "michael", "david",
                  "robert", "william", "daniel", "matthew", "andrew", "alex", "omar",
                  "carlos", "liam", "chen", "marcus"}
    if name_lower in known_female:
        gender_hint = "Пол: женский. Используй женский род глаголов (сказала, пошла, хотела)."
    elif name_lower in known_male:
        gender_hint = "Пол: мужской. Используй мужской род глаголов (сказал, пошёл, хотел)."

    return (
        f"Ты — AI-симулятор исследовательских интервью.\n\n"
        f"ПРОФИЛЬ ПЕРСОНАЖА которого ты симулируешь:\n"
        f"Имя: {persona.name}, {persona.age} лет. {profile_text}\n"
        f"Характер: {personality_desc}. Стиль речи: {comm}.\n"
        f"{gender_hint}\n\n"
        f"ПРАВИЛА СИМУЛЯЦИИ:\n"
        f"1. Говори живым языком: паузы ('ну...', 'честно говоря'), конкретные цифры из жизни.\n"
        f"2. Отвечай ЧЕСТНО — и положительно, и отрицательно. Если продукт полезен — скажи. Если нет — тоже скажи прямо.\n"
        f"3. Ответы: 2-4 предложения, как в реальном разговоре.\n"
        f"4. Язык: СТРОГО {language}. Никакого code-switching.\n"
        f"5. Оценки ставь ОБЪЕКТИВНО по шкале 1-10 исходя из реального опыта персонажа. Не занижай и не завышай."
    )

# SYSTEM_PROMPTS и get_system_prompt() удалены — не использовались
# (системный промпт формируется в _make_persona_system())


# ═══════════════════════════════════════════════════════════════
#  Рыночное исследование (поиск конкурентов)
# ═══════════════════════════════════════════════════════════════

def research_market_context(business_input: BusinessInput) -> str:
    """Отключено — внешний контекст влияет на ответы персон и создаёт галлюцинации."""
    return ""


# ═══════════════════════════════════════════════════════════════
#  Построение двухфазного промпта
# ═══════════════════════════════════════════════════════════════

def _extract_domain_topic(business_input: BusinessInput) -> str:
    """
    Извлекает ключевую ТЕМУ/ДОМЕН из описания бизнеса.
    Например: inDrive → 'городской транспорт и поездки на такси',
              Choco.kz → 'заказ и доставка еды',
              Notion → 'организация заметок и рабочих задач'.
    """
    desc = (business_input.description or "").lower()
    name = (business_input.name or "").lower()
    btype = business_input.business_type.value.lower() if business_input.business_type else ""

    # Ключевые слова → домен
    domain_map = [
        (["такси", "поезд", "водител", "маршрут", "транспорт", "ride", "drive", "поездк"],
         "городской транспорт и поездки (такси, автобусы, личный автомобиль)"),
        (["еда", "ресторан", "доставк", "food", "кухн", "обед", "ужин", "заказ еды", "меню"],
         "питание и заказ еды (готовка дома, рестораны, доставка)"),
        (["заметк", "задач", "документ", "wiki", "note", "notion", "workspace", "рабоч"],
         "организация работы, заметок и задач"),
        (["видео", "контент", "стрим", "stream", "фильм", "сериал", "смотр"],
         "просмотр видео и развлекательного контента"),
        (["фриланс", "freelanc", "gig", "подработк", "заказ", "услуг"],
         "поиск подработки и фриланс-услуг"),
        (["магазин", "покупк", "товар", "shop", "e-commerce", "маркетплейс"],
         "онлайн-покупки и шопинг"),
        (["здоров", "медицин", "врач", "health", "фитнес"],
         "здоровье и медицинские услуги"),
        (["обучен", "курс", "образован", "learn", "edu"],
         "обучение и образование"),
    ]
    
    for keywords, domain in domain_map:
        if any(kw in desc or kw in name for kw in keywords):
            return domain
    
    # Fallback: общий домен из типа бизнеса
    return "повседневные привычки и расходы, связанные с этой сферой"


def _make_simulation_user_message(persona: Persona, business_input: BusinessInput, price_desc: str, language: str):
    """
    Формирует единый промпт для симуляции двухфазного интервью в один запрос.
    Нейросеть выступает в роли симулятора, разыгрывающего диалог.
    """
    desc = business_input.description or ""
    audience = business_input.target_audience or ""
    domain_topic = _extract_domain_topic(business_input)
    
    return (
        f"Проведи интервью по методу Mom Test (Роб Фитцпатрик) с клиентом {persona.name}.\n\n"
        
        f"ПРОДУКТ (клиент узнаёт ТОЛЬКО в Акте 2):\n"
        f"- Название: {business_input.name or 'Стартап'}\n"
        f"- Что делает: {desc}\n"
        f"- Для кого: {audience}\n"
        f"- Цена: {price_desc}\n\n"
        
        f"══ АКТ 1 (Discovery) — 3 вопроса ══\n"
        f"Тема: {domain_topic}\n"
        f"Спрашивай о РЕАЛЬНОМ ОПЫТЕ клиента в этой области. Не упоминай продукт!\n"
        f"Примеры вопросов:\n"
        f"  • Как ты обычно решаешь [задачу]? Расскажи про последний раз.\n"
        f"  • Сколько тратишь на это в месяц? Устраивает ли тебя это?\n"
        f"  • Что не устраивает в том, чем пользуешься сейчас?\n"
        f"Клиент отвечает честно. Может быть доволен — это нормально.\n\n"
        
        f"══ АКТ 2 (Exposure) — 3 вопроса ══\n"
        f"Интервьюер КОРОТКО (1-2 предложения) описывает продукт, затем спрашивает:\n"
        f"  1. Использовал бы ты такое? Почему?\n"
        f"  2. Как тебе цена: {price_desc}?\n"
        f"  3. Переключился бы с {persona.current_solution}?\n\n"
        
        f"══ ПРАВИЛА ОЦЕНКИ ══\n"
        f"Оценки должны ТОЧНО отражать ответы клиента в диалоге.\n\n"
        f"ШКАЛА ОЦЕНОК (применяй ко ВСЕМ числовым полям):\n"
        f"  1-2 = вообще не актуально для этого человека\n"
        f"  3-4 = слабо актуально, может обойтись без этого\n"
        f"  5-6 = умеренно актуально, есть неудобства, но терпимо\n"
        f"  7-8 = сильно актуально, тратит время/деньги на решение\n"
        f"  9-10 = критически актуально, активно ищет решение\n\n"
        f"ХАРАКТЕР: {persona.personality_trait}\n"
        f"- skeptic: сомневается, но если продукт реально полезен — признает это\n"
        f"- conservative: осторожен с новым, но хорошо знакомые решения оценивает справедливо\n"
        f"- pragmatist: считает выгоду, если экономия очевидна — оценит высоко\n"
        f"- early_adopter: открыт к новому, готов пробовать\n\n"
        f"relevance:\n"
        f"- 'none' = ТОЛЬКО если клиент вообще НЕ пользуется услугами в этом домене (редкость для ЦА)\n"
        f"- 'low' = пользуется, но всем доволен\n"
        f"- 'medium' = пользуется, есть неудобства (это НОРМА для большинства)\n"
        f"- 'high' = активно тратит деньги/время на решение проблемы\n\n"
        f"would_buy = true если: клиент в диалоге выразил готовность платить, цена приемлема, wtp ≥ 6.\n"
        f"would_buy = false если: цена высокая, нет боли, или продукт не нужен.\n\n"
        f"Язык: СТРОГО {language}. Верни СТРОГО JSON (без markdown):\n"
        "{\n"
        "  \"conversation\": [\n"
        "    {\"phase\": 1, \"category\": \"routine\", \"question\": \"...\", \"answer\": \"...\"},\n"
        "    {\"phase\": 1, \"category\": \"activities\", \"question\": \"...\", \"answer\": \"...\"},\n"
        "    {\"phase\": 1, \"category\": \"spending\", \"question\": \"...\", \"answer\": \"...\"},\n"
        "    {\"phase\": 2, \"category\": \"reaction\", \"question\": \"...\", \"answer\": \"...\"},\n"
        "    {\"phase\": 2, \"category\": \"pricing\", \"question\": \"...\", \"answer\": \"...\"},\n"
        "    {\"phase\": 2, \"category\": \"switching\", \"question\": \"...\", \"answer\": \"...\"}\n"
        "  ],\n"
        "  \"scores\": {\n"
        "    \"relevance\": \"<none|low|medium|high>\",\n"
        "    \"problem_severity\": <1-10>,\n"
        "    \"solution_fit\": <1-10>,\n"
        "    \"willingness_to_pay\": <1-10>,\n"
        "    \"switching_likelihood\": <1-10>,\n"
        "    \"recommend_likelihood\": <1-10>,\n"
        "    \"main_concern\": \"...\",\n"
        "    \"desired_feature\": \"...\",\n"
        "    \"price_feedback\": \"дорого | нормально | дёшево\",\n"
        "    \"would_buy\": <true|false>,\n"
        "    \"phase1_summary\": \"...\",\n"
        "    \"phase2_summary\": \"...\"\n"
        "  }\n"
        "}"
    )



def _validate_consistency(persona: Persona, response: "InterviewResponse") -> "InterviewResponse":
    """
    Минимальная постобработка: исправляет только ЯВНЫЕ логические противоречия.
    НЕ занижает и НЕ завышает оценки — доверяем LLM.
    """
    # ── 1. would_buy + willingness_to_pay < 4 → would_buy = false ─
    if response.would_buy and response.willingness_to_pay < 4:
        response.would_buy = False
        logger.info(f"[{persona.name}] КОРРЕКЦИЯ: would_buy=false (wtp={response.willingness_to_pay} < 4)")

    # ── 2. would_buy + price_feedback == "дорого" → would_buy = false ─
    if response.would_buy and response.price_feedback == "дорого":
        response.would_buy = False
        logger.info(f"[{persona.name}] КОРРЕКЦИЯ: would_buy=false (дорого)")

    # ── 3. problem_severity=1 но solution_fit>7 — нелогично ─
    if response.problem_severity <= 2 and response.solution_fit > response.problem_severity + 5:
        old_fit = response.solution_fit
        response.solution_fit = response.problem_severity + 4
        logger.info(f"[{persona.name}] КОРРЕКЦИЯ: fit {old_fit}→{response.solution_fit} (pain={response.problem_severity})")

    return response


def _parse_interview_response(content: str, persona: Persona, raw_opinion: str = "") -> InterviewResponse:
    """
    Парсит ответ LLM в новом формате {conversation, scores}.
    Поддерживает также старый формат (плоский JSON) для совместимости.
    Выполняет постобработку: валидация консистентности оценок.
    """
    content = content.strip()
    if content.startswith("```"):
        lines = content.split("\n")
        end_idx = next(
            (i for i, line in enumerate(lines[1:], 1) if line.strip() == "```"),
            len(lines)
        )
        content = "\n".join(lines[1:end_idx])

    data = json.loads(content)

    def clamp_int(val, lo=1, hi=10) -> int:
        try:
            return max(lo, min(hi, int(val)))
        except (TypeError, ValueError):
            return 3  # Дефолт 3, не 5 — избегаем anchoring на середину

    # ── Поддержка нового формата {conversation, scores} ──────
    scores = data.get("scores", data)  # fallback на плоский формат
    conversation = data.get("conversation", [])

    # Очищаем заглушки "<твой ответ>" если LLM их не заполнил
    clean_conv = []
    for item in conversation:
        if isinstance(item, dict) and item.get("answer", "").strip() not in ("", "<твой ответ>"):
            clean_conv.append({
                "phase":    int(item.get("phase", 1)),
                "category": str(item.get("category", "")),
                "question": str(item.get("question", "")),
                "answer":   str(item.get("answer", ""))[:600],
            })

    # raw_opinion передаётся снаружи (из двухфазного диалога)
    # Если не передан — пробуем вытащить из scores или conversation
    if not raw_opinion:
        p1_answers = [c["answer"] for c in clean_conv if c["phase"] == 1]
        p2_answers = [c["answer"] for c in clean_conv if c["phase"] == 2]
        if clean_conv:
            raw_opinion = " | ".join((p1_answers + p2_answers)[:3])
        else:
            raw_opinion = str(scores.get("phase1_summary", "")) + " " + str(scores.get("phase2_summary", ""))
    raw_opinion = raw_opinion[:1200]

    price_feedback = str(scores.get("price_feedback", "нормально")).lower().strip()
    if price_feedback not in ("дорого", "нормально", "дёшево"):
        price_feedback = "нормально"

    raw_would_buy = scores.get("would_buy", False)
    if isinstance(raw_would_buy, bool):
        would_buy = raw_would_buy
    elif isinstance(raw_would_buy, str):
        would_buy = raw_would_buy.lower() in ("true", "да", "yes", "1")
    else:
        would_buy = False

    # ── Relevance: если LLM указал "none" → все оценки ≤ 3 ────
    relevance = str(scores.get("relevance", "medium")).lower().strip()
    if relevance == "none":
        # Продукт вообще не нужен этому человеку
        would_buy = False
        logger.info(f"[{persona.name}] relevance=none → оценки понижены, would_buy=false")

    response = InterviewResponse(
        persona_id=persona.id,
        persona_name=persona.name,
        persona_occupation=persona.occupation,
        problem_severity=clamp_int(scores.get("problem_severity", 3)),
        solution_fit=clamp_int(scores.get("solution_fit", 3)),
        willingness_to_pay=clamp_int(scores.get("willingness_to_pay", 3)),
        switching_likelihood=clamp_int(scores.get("switching_likelihood", 3)),
        recommend_likelihood=clamp_int(scores.get("recommend_likelihood", 3)),
        main_concern=str(scores.get("main_concern", ""))[:500],
        desired_feature=str(scores.get("desired_feature", ""))[:300],
        price_feedback=price_feedback,
        would_buy=would_buy,
        raw_opinion=raw_opinion[:600],
        conversation=clean_conv,
    )

    # ── Если relevance == none → cap 3 ────────────────────────
    if relevance == "none":
        response.problem_severity = min(response.problem_severity, 3)
        response.solution_fit = min(response.solution_fit, 3)
        response.willingness_to_pay = min(response.willingness_to_pay, 2)
        response.switching_likelihood = min(response.switching_likelihood, 2)
        response.recommend_likelihood = min(response.recommend_likelihood, 3)
    # relevance="low" — НЕ cap'аем, LLM уже учёл это в оценках

    # ── Постобработка: валидация консистентности ──────────────
    response = _validate_consistency(persona, response)

    return response


# ═══════════════════════════════════════════════════════════════
#  Интервью одной персоны (с retry)
# ═══════════════════════════════════════════════════════════════

def _run_single_interview(
    persona: Persona,
    business_input: BusinessInput,
    market_context: str = "",
    retries: int = 3,
    age_profile: Optional[dict] = None,
) -> InterviewResponse:
    """
    Симуляция интервью в ОДИН API-вызов.
    Нейросеть разыгрывает две фазы Mom Test и возвращает результат в JSON.
    """
    countries_map = {
        "kazakhstan": "Казахстан", "russia": "Россия",
        "usa": "США", "global": "Глобальный рынок"
    }
    country_name = countries_map.get(business_input.country.lower(), "Глобальный рынок")

    personality_desc = {
        "early_adopter": "любящий пробовать новое и открытый к инновациям человек",
        "pragmatist": "прагматик, ценящий реальную пользу и не спешащий с покупкой",
        "skeptic": "скептик, сомневающийся и задающий острые вопросы",
        "conservative": "консерватор, верный привычкам и доверяющий проверенному",
    }.get(persona.personality_trait, "обычный человек")

    rm = business_input.revenue_model
    if rm.value == "subscription":
        price_desc = f"подписка {business_input.price:.0f}$/месяц"
    elif rm.value == "pay_per_use":
        price_desc = f"{business_input.price_per_use:.0f}$ за каждое использование"
    else:
        # Commission — описываем с точки зрения КЛИЕНТА (пользователя), не бизнеса
        avg_deal = business_input.avg_deal_value
        price_desc = (
            f"бесплатно для пользователя, средний чек услуги ~{avg_deal:.0f} (местная валюта). "
            f"Платформа берёт {business_input.commission_rate*100:.0f}% комиссии с исполнителя."
        )

    system_msg = _make_persona_system(persona, country_name, personality_desc, business_input.language)
    sim_prompt = _make_simulation_user_message(persona, business_input, price_desc, business_input.language)

    def _call(messages, json_mode=False, attempt_label=""):
        kwargs = dict(
            model=_LLM_MODEL,
            messages=messages,
            temperature=0.85,
            max_tokens=2500,
        )
        if json_mode:
            kwargs["response_format"] = {"type": "json_object"}
            
        for attempt in range(retries + 1):
            try:
                client = get_llm()
                import config as _cfg
                _cfg.rate_limit_sleep()
                resp = client.chat.completions.create(**kwargs)
                return resp.choices[0].message.content
            except Exception as e:
                err = str(e)
                logger.error(f"[{persona.name}] Simulation error (attempt {attempt+1}): {err}")
                # Проверяем — исчерпана ли квота (суточный лимит)
                quota_keywords = (
                    "quota", "rate_limit_exceeded", "insufficient_quota",
                    "exceeded", "billing", "perday", "daily", "limit reached",
                    "resource_exhausted", "RESOURCE_EXHAUSTED",
                )
                is_quota = any(kw.lower() in err.lower() for kw in quota_keywords)
                if is_quota:
                    # Пробуем следующий ключ из пула
                    try:
                        import config as _cfg
                        new_key = _cfg.rotate_key()
                        if new_key:
                            logger.warning(f"[{persona.name}] Квота исчерпана — переключаемся на следующий ключ")
                            reset_llm()
                            time.sleep(2.0)
                            continue
                    except Exception:
                        pass
                    raise QuotaExceededError(
                        "🚫 Все API ключи исчерпали дневной лимит. "
                        "Добавьте новые ключи через запятую в Streamlit Secrets или попробуйте завтра."
                    )
                if attempt < retries:
                    if "429" in err:
                        logger.warning(f"[{persona.name}] Rate limit, ждём 15 сек...")
                        time.sleep(15.0)
                    else:
                        time.sleep(3.0)
        return None

    messages = [
        {"role": "system", "content": system_msg},
        {"role": "user",   "content": sim_prompt},
    ]

    raw_result = _call(messages, json_mode=True, attempt_label="[simulation]")

    if raw_result:
        try:
            return _parse_interview_response(raw_result, persona)
        except Exception as e:
            logger.error(f"[{persona.name}] JSON parse error: {e} | Content: {raw_result[:200]}")
            # Пытаемся вернуть хотя бы пустой объект с ошибкой вместо краша
            raise RuntimeError(f"Не удалось обработать ответ от симуляции: {e}")

    # Ошибка
    model_name = os.environ.get("OPENAI_MODEL", "неизвестна")
    raise RuntimeError(
        f"❌ Симуляция для {persona.name} не удалась. Модель {model_name} не ответила или лимиты исчерпаны."
    )



# ═══════════════════════════════════════════════════════════════
#  Последовательный запуск всех интервью (без параллелизма)
# ═══════════════════════════════════════════════════════════════

def run_all_interviews(
    personas: List[Persona],
    business_input: BusinessInput,
    market_context: str = "",
    max_workers: int = 1,
    age_profile: Optional[dict] = None,
) -> List[InterviewResponse]:
    """
    Запускает интервью для каждой персоны ПОСЛЕДОВАТЕЛЬНО (по одному за раз).
    age_profile — профиль аудитории (youth/student/adult), влияет на Phase 2 промпт.
    """
    if not personas:
        return []

    results: List[InterviewResponse] = []

    for idx, persona in enumerate(personas, 1):
        logger.info(
            f"Интервью {idx}/{len(personas)}: {persona.name} ({persona.occupation})"
        )
        try:
            result = _run_single_interview(
                persona, business_input, market_context, age_profile=age_profile
            )
            results.append(result)
        except Exception as e:
            logger.error(f"Критическая ошибка интервью {persona.name}: {e}")
            # Показываем реальную ошибку — не прячем за фейковыми метриками
            results.append(InterviewResponse(
                persona_id=persona.id,
                persona_name=persona.name,
                persona_occupation=persona.occupation,
                problem_severity=0,
                solution_fit=0,
                willingness_to_pay=0,
                switching_likelihood=0,
                recommend_likelihood=0,
                main_concern=f"⚠️ ОШИБКА API: {str(e)[:300]}",
                desired_feature="",
                price_feedback="нормально",
                would_buy=False,
                raw_opinion=f"[ОШИБКА — результат не получен: {str(e)[:400]}]",
                is_error=True,
                conversation=(
                    [{"phase": 1, "category": q.category, "question": q.question, "answer": ""} for q in MOM_TEST_QUESTIONS_PHASE1] +
                    [{"phase": 2, "category": q.category, "question": q.question, "answer": ""} for q in MOM_TEST_QUESTIONS_PHASE2]
                )
            ))

        # Локальная пауза больше не нужна, так как работает глобальный rate_limit_sleep()

    return results