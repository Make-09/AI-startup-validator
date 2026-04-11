"""
personas.py — Генерация синтетических клиентских персон с богатым профилем.

Каждая персона — полноценный живой человек:
  - город и район, семейное положение, дети
  - распорядок дня, финансовое поведение
  - какими приложениями пользуется, рабочий контекст
  - backstory — история, которая объясняет его боли
  - стиль общения
"""

import json
import random
import logging
from typing import List, Optional, Dict, Any

from models import BusinessInput, BusinessType, Persona

AgeProfile = dict
logger = logging.getLogger(__name__)

NAMES_BY_COUNTRY: Dict[str, List[str]] = {
    "kazakhstan": [
        "Нурлан", "Дамир", "Арман", "Тимур", "Ерлан",
        "Бауыржан", "Данияр", "Асет", "Мирас", "Алихан",
        "Айгерим", "Мадина", "Жанна", "Камила", "Динара",
        "Аяулым", "Назерке", "Томирис", "Дана", "Айнур",
    ],
    "russia": [
        "Алексей", "Мария", "Иван", "Елена", "Дмитрий",
        "Ольга", "Сергей", "Анна", "Михаил", "Юлия",
        "Андрей", "Наталья", "Владимир", "Татьяна", "Павел",
    ],
    "usa": [
        "James", "Emily", "Michael", "Sarah", "David",
        "Jessica", "Robert", "Amanda", "William", "Ashley",
        "Daniel", "Sophia", "Matthew", "Olivia", "Andrew",
    ],
    "global": [
        "Alex", "Maria", "David", "Sophia", "James",
        "Elena", "Omar", "Yuki", "Carlos", "Priya",
        "Liam", "Fatima", "Chen", "Olga", "Marcus",
    ],
}

COUNTRY_CONTEXT = {
    "kazakhstan": (
        "Казахстан (средняя зарплата $500–$1500/мес, "
        "платёжные системы: Kaspi Pay, Halyk, "
        "города: Алматы, Астана, Шымкент, Атырау, Актобе)"
    ),
    "russia": (
        "Россия (средняя зарплата $600–$2000/мес, "
        "платёжные системы: СБП, Сбербанк, "
        "города: Москва, Санкт-Петербург, Новосибирск, Екатеринбург)"
    ),
    "usa": (
        "США (средняя зарплата $3000–$8000/мес, "
        "платёжные системы: Stripe, PayPal, Apple Pay)"
    ),
    "global": "Глобальный рынок (разный уровень доходов)",
}

TECH_LEVELS: Dict[str, List[str]] = {
    "early_adopter": ["medium", "high"],
    "pragmatist":    ["low", "medium", "high"],
    "skeptic":       ["low", "medium"],
    "conservative":  ["low", "medium"],
}

FALLBACK_PERSONAS_BY_AGE = {
    "youth": [
        {
            "occupation": "Ученик 10-го класса",
            "monthly_income": 50,
            "city": "Алматы, Орбита",
            "family_status": "Живёт с родителями, есть младший брат",
            "daily_routine": "Школа с 8 до 14, потом уроки, вечером гуляю или играю",
            "financial_behavior": "Карманные деньги от родителей 10-20 тыс тенге, трачу на перекусы и игры",
            "apps_used": "TikTok, Instagram, Telegram, YouTube, Kaspi",
            "work_context": "Учёба в школе, иногда помогаю маме в магазине",
            "backstory": "Обычный школьник, увлекается футболом и видеоиграми",
            "communication_style": "говорит коротко, использует сленг, часто отвлекается",
            "pain_points": ["Не хватает карманных денег", "Скучно после школы"],
            "current_solution": "Прошу деньги у родителей",
            "gender": "male",
        },
        {
            "occupation": "Ученица 9-го класса",
            "monthly_income": 30,
            "city": "Шымкент, центр",
            "family_status": "Живёт с мамой и бабушкой",
            "daily_routine": "Школа до 13:00, потом репетитор, вечером TikTok",
            "financial_behavior": "Мама даёт 5-10 тыс тенге в неделю, копит на телефон",
            "apps_used": "TikTok, WhatsApp, Instagram, Pinterest",
            "work_context": "Учёба, кружок рисования",
            "backstory": "Мечтает стать дизайнером, рисует на заказ в Инстаграм",
            "communication_style": "эмоциональная, много деталей, использует эмодзи-стиль",
            "pain_points": ["Мало свободного времени", "Хочет свои деньги, не зависеть от мамы"],
            "current_solution": "Продаёт рисунки через Instagram знакомым",
            "gender": "female",
        },
    ],
    "student": [
        {
            "occupation": "Студент 2-го курса IT-факультета",
            "monthly_income": 200,
            "city": "Алматы, Саяхат",
            "family_status": "Живёт в общежитии, не женат",
            "daily_routine": "Пары с 9 до 15, вечером подрабатываю курьером",
            "financial_behavior": "Стипендия + подработка, хватает впритык",
            "apps_used": "Telegram, Kaspi, InDrive, Instagram, GitHub",
            "work_context": "Учёба в КазНУ, подрабатываю курьером в Glovo",
            "backstory": "Приехал из Тараза учиться, родители помогают частично",
            "communication_style": "спокойный, логичный, иногда скептичный",
            "pain_points": ["Не хватает времени на учёбу и подработку", "Курьерство физически тяжело"],
            "current_solution": "Glovo и разовые заказы от знакомых",
            "gender": "male",
        },
        {
            "occupation": "Студентка 3-го курса экономического факультета",
            "monthly_income": 150,
            "city": "Астана, Сарыарка",
            "family_status": "Живёт с подругой на съёмной квартире",
            "daily_routine": "Пары до обеда, после — подработка репетитором",
            "financial_behavior": "Стипендия 30 тыс +  репетиторство, экономит на еде",
            "apps_used": "WhatsApp, Kaspi, Instagram, Zoom, Telegram",
            "work_context": "Учусь в ЕНУ, даю уроки математики школьникам",
            "backstory": "Подрабатывает с 1-го курса, чтобы не просить у родителей",
            "communication_style": "вежливая но прямая, ценит своё время",
            "pain_points": ["Сложно найти новых учеников", "Нестабильный доход"],
            "current_solution": "Ищу учеников через сарафанное радио и OLX",
            "gender": "female",
        },
    ],
    "adult": [
        {
            "occupation": "Менеджер по продажам",
            "monthly_income": 1100,
            "city": "Алматы, Бостандык",
            "family_status": "Женат, один ребёнок 4 года",
            "daily_routine": "Встаю в 7:00, отвожу ребёнка в сад, работаю до 18:00",
            "financial_behavior": "Откладываю 10% в месяц, есть ипотека",
            "apps_used": "Kaspi, Telegram, WhatsApp, 2ГИС, Instagram",
            "work_context": "Дистрибьюторская компания, веду 20+ клиентов",
            "backstory": "3 года назад перешёл с госслужбы в частный бизнес",
            "communication_style": "говорит по делу, немногословен",
            "pain_points": ["Теряю время на рутинную отчётность", "CRM неудобная"],
            "current_solution": "Excel + самодельные таблицы",
            "gender": "male",
        },
        {
            "occupation": "Владелец малого бизнеса",
            "monthly_income": 2200,
            "city": "Астана, Есиль",
            "family_status": "Замужем, двое детей 9 и 13 лет",
            "daily_routine": "Работаю с 9 до 21, часть удалённо",
            "financial_behavior": "Всё вкладываю в бизнес, есть кредит на оборудование",
            "apps_used": "Instagram, Kaspi Business, WhatsApp Business, 1C",
            "work_context": "Небольшой салон красоты, 4 сотрудника",
            "backstory": "Открылась 5 лет назад, пережила пандемию",
            "communication_style": "прямая, не любит воду, хочет сразу суть",
            "pain_points": ["Теряю клиентов без автозаписи", "Непонятно откуда приходят клиенты"],
            "current_solution": "Журнал записей + WhatsApp вручную",
            "gender": "female",
        },
    ],
}

_YOUTH_KEYWORDS = {
    "школьник", "школьники", "подросток", "подростки", "дети", "ребёнок",
    "ребенок", "тинейджер", "teen", "teenager", "kid", "kids", "youth",
    "молодёжь", "молодежь",
}
_STUDENT_KEYWORDS = {
    "студент", "студенты", "student", "university", "университет",
    "колледж", "college", "абитуриент",
}


def _detect_age_profile(business_input: BusinessInput) -> AgeProfile:
    text = (
        (business_input.target_audience or "") + " " +
        (business_input.description or "") + " " +
        (business_input.name or "")
    ).lower()
    for kw in _YOUTH_KEYWORDS:
        if kw in text:
            return {"mean": 15, "std": 1.5, "min": 12, "max": 17, "label": "youth"}
    for kw in _STUDENT_KEYWORDS:
        if kw in text:
            return {"mean": 20, "std": 2, "min": 17, "max": 25, "label": "student"}
    return {"mean": 32, "std": 8, "min": 18, "max": 55, "label": "adult"}


def _generate_personas_with_llm(
    business_input: BusinessInput,
    count: int,
    age_profile: AgeProfile,
) -> Optional[List[Dict]]:
    from interview_engine import get_llm
    import os

    model = os.environ.get("OPENAI_MODEL", "gpt-4o-mini")
    country_info = COUNTRY_CONTEXT.get(business_input.country.lower(), COUNTRY_CONTEXT["global"])
    target_aud = business_input.target_audience or "широкая аудитория"

    personality_pool = (
        ["early_adopter"] * max(1, int(count * 0.25)) +
        ["pragmatist"]    * max(1, int(count * 0.40)) +
        ["skeptic"]       * max(1, int(count * 0.25)) +
        ["conservative"]  * max(1, int(count * 0.10))
    )
    random.shuffle(personality_pool)
    personalities = (personality_pool + ["pragmatist"] * count)[:count]

    personality_desc = {
        "early_adopter": "любит пробовать новое, быстро принимает решения",
        "pragmatist":    "прагматик, хочет конкретную пользу, сравнивает цены",
        "skeptic":       "скептик, задаёт острые вопросы, доверяет с трудом",
        "conservative":  "консерватор, доверяет проверенному, не любит риск",
    }

    age_note = ""
    if age_profile["label"] == "youth":
        age_note = f"\n⚠️ ВОЗРАСТ: школьники {age_profile['min']}–{age_profile['max']} лет. Доход = карманные деньги 20–150 USD."
    elif age_profile["label"] == "student":
        age_note = f"\n⚠️ ВОЗРАСТ: студенты {age_profile['min']}–{age_profile['max']} лет. Доход 150–500 USD."

    personas_spec = "\n".join(
        f"{i+1}. personality: \"{personalities[i]}\" — {personality_desc[personalities[i]]}"
        for i in range(count)
    )

    prompt = f"""Ты — социолог-исследователь. Создай {count} РЕАЛИСТИЧНЫХ профилей людей из целевой аудитории.

ЦЕЛЕВАЯ АУДИТОРИЯ: {target_aud}
СТРАНА: {country_info}{age_note}

СПИСОК ПЕРСОН (создай ровно {count} штук, в том же порядке):
{personas_spec}

⚠️ ГЛАВНОЕ ПРАВИЛО: ты создаёшь ОБЫЧНЫХ ЛЮДЕЙ из этой аудитории, а НЕ «идеальных клиентов».
У каждого человека свои повседневные заботы — пробки, учёба, дети, нехватка денег, здоровье, отношения.
Ты НЕ знаешь, какой продукт им будет предложен. Не пытайся угадать.

ТРЕБОВАНИЯ — каждая персона это ЖИВОЙ ЧЕЛОВЕК с реальной историей:

occupation     — конкретная должность/роль из ЦА «{target_aud}» (не абстрактная)
monthly_income — реалистичный доход в USD для этой профессии и страны
city           — реальный город И район: «Алматы, Бостандык» или «Москва, Выхино»
family_status  — конкретно: «Женат, двое детей 3 и 9 лет» или «Живёт с родителями»
daily_routine  — 1-2 предложения: когда встаёт, чем занимается днём, что делает вечером
financial_behavior — как относится к деньгам: копит/тратит, откуда доход, на что тратит
apps_used      — 4-6 конкретных приложений которыми пользуется каждый день (популярных в стране)
work_context   — где учится/работает, окружение, какие инструменты использует
backstory      — 1-2 предложения об увлечениях и повседневности. ⛔ НЕ придумывай боли и «нерешённые задачи» — просто опиши жизнь
communication_style — как говорит: «краткий и по делу», «эмоциональный с деталями», «осторожный»
pain_points    — МАССИВ из 2-3 ОБЫЧНЫХ повседневных трудностей (пробки, нехватка денег, усталость, скучная работа, проблемы с ЖКХ, сложные отношения, здоровье, давление родителей — РЕАЛЬНЫЕ БЫТОВЫЕ проблемы конкретного человека, а НЕ «боли» из учебника по маркетингу)
current_solution — как сейчас справляется с этими трудностями (конкретно)
gender         — "male" или "female" (определяется по имени и occupation)

КРИТИЧЕСКИЕ ПРАВИЛА:
- occupation СТРОГО из ЦА «{target_aud}» — НЕ выдумывай людей другого возраста/профессии
- Все {count} персон РАЗНЫЕ: разные города, семьи, ситуации, характеры
- ⛔ ЗАПРЕЩЕНО в backstory и pain_points:
  • Слова «ищет способ заработка», «нужен сервис для...», «хочет автоматизировать...»
  • Любые формулировки, которые звучат как маркетинговое описание потребности
  • Боли, содержащие решение в формулировке (например «нет удобного приложения для X»)
- ✅ ПРАВИЛЬНЫЕ боли: «Устаёт от дороги на работу», «Не хватает на новый телефон», «Поссорился с другом», «Скучно после школы», «Болит спина от сидячей работы»
- Не используй слова «домохозяйка» — пиши «человек ведущий хозяйство»
- Тексты на русском языке

Верни СТРОГО JSON массив из {count} объектов без пояснений:
[{{"occupation":"...","monthly_income":1200,"city":"...","family_status":"...","daily_routine":"...","financial_behavior":"...","apps_used":"...","work_context":"...","backstory":"...","communication_style":"...","pain_points":["...","..."],"current_solution":"...","gender":"male"}}]"""

    try:
        client = get_llm()
        resp = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.85,
            max_tokens=4000,
        )
        raw = resp.choices[0].message.content.strip()
        
        # Надежный поиск начала и конца JSON массива/объекта
        start_idx = raw.find("[")
        if start_idx == -1: start_idx = raw.find("{")
        end_idx = raw.rfind("]")
        if end_idx == -1: end_idx = raw.rfind("}")
        
        if start_idx != -1 and end_idx != -1 and end_idx > start_idx:
            raw = raw[start_idx:end_idx+1]

        data = json.loads(raw)
        if isinstance(data, list) and len(data) >= max(1, count // 2):
            logger.info(f"LLM сгенерировал {len(data)} богатых профилей персон")
            return data
        logger.warning(f"LLM вернул неверный формат: {type(data)}")
        return None
    except Exception as e:
        err = str(e)
        # Пробуем ротацию ключей при исчерпании квоты
        quota_keywords = ("quota", "exceeded", "resource_exhausted", "RESOURCE_EXHAUSTED", "billing", "429")
        if any(kw.lower() in err.lower() for kw in quota_keywords):
            try:
                import config as _cfg
                from interview_engine import reset_llm
                new_key = _cfg.rotate_key()
                if new_key:
                    logger.warning(f"Квота персон исчерпана — пробуем следующий ключ")
                    reset_llm()
                    import time
                    time.sleep(2.0)
                    # Повторная попытка с новым ключом
                    try:
                        client2 = get_llm()
                        resp2 = client2.chat.completions.create(
                            model=model,
                            messages=[{"role": "user", "content": prompt}],
                            temperature=0.85,
                            max_tokens=4000,
                        )
                        raw2 = resp2.choices[0].message.content.strip()
                        s = raw2.find("["); e2 = raw2.rfind("]")
                        if s != -1 and e2 != -1: raw2 = raw2[s:e2+1]
                        data2 = json.loads(raw2)
                        if isinstance(data2, list) and len(data2) >= max(1, count // 2):
                            return data2
                    except Exception as e3:
                        logger.warning(f"Повторная попытка с новым ключом тоже не удалась: {e3}")
            except Exception:
                pass
        logger.warning(f"Ошибка генерации персон через LLM: {e}")
        return None


def generate_personas(business_input: BusinessInput, count: int = 10) -> List[Persona]:
    """
    Генерирует список реалистичных персон с полными профилями.
    LLM создаёт живых людей с историями. При ошибке — fallback.
    """
    age_profile = _detect_age_profile(business_input)
    logger.info(f"Возрастной профиль: {age_profile['label']} ({age_profile['min']}–{age_profile['max']} лет)")

    country_key = business_input.country.lower()
    names = NAMES_BY_COUNTRY.get(country_key, NAMES_BY_COUNTRY["global"]).copy()
    random.shuffle(names)

    llm_profiles = _generate_personas_with_llm(business_input, count, age_profile)

    primary_count   = max(1, int(count * 0.50))
    secondary_count = max(1, int(count * 0.30))
    edge_count      = count - primary_count - secondary_count
    segments = (
        ["primary"]   * primary_count +
        ["secondary"] * secondary_count +
        ["edge_case"] * max(0, edge_count)
    )
    random.shuffle(segments)

    weights_map = {
        "primary":   [0.35, 0.40, 0.15, 0.10],  # early_adopter, pragmatist, skeptic, conservative
        "secondary": [0.25, 0.40, 0.20, 0.15],
        "edge_case": [0.15, 0.35, 0.30, 0.20],
    }

    personas: List[Persona] = []
    for i in range(count):
        name = names[i % len(names)]
        age = int(random.gauss(age_profile["mean"], age_profile["std"]))
        age = max(age_profile["min"], min(age_profile["max"], age))
        segment = segments[i] if i < len(segments) else "primary"
        w = weights_map.get(segment, [0.25, 0.40, 0.25, 0.10])
        personality = random.choices(
            ["early_adopter", "pragmatist", "skeptic", "conservative"],
            weights=w, k=1
        )[0]
        tech_savviness = random.choice(TECH_LEVELS[personality])

        if llm_profiles and i < len(llm_profiles):
            p = llm_profiles[i]
            pain_points = p.get("pain_points", ["Нет данных"])
            if isinstance(pain_points, str):
                pain_points = [pain_points]
            personas.append(Persona(
                name=name, age=age,
                occupation=str(p.get("occupation", "Специалист")),
                monthly_income=float(p.get("monthly_income", 800)),
                tech_savviness=tech_savviness,
                pain_points=pain_points[:3],
                current_solution=str(p.get("current_solution", "Excel")),
                personality_trait=personality,
                segment=segment,
                city=str(p.get("city", "")),
                family_status=str(p.get("family_status", "")),
                daily_routine=str(p.get("daily_routine", "")),
                financial_behavior=str(p.get("financial_behavior", "")),
                apps_used=str(p.get("apps_used", "")),
                work_context=str(p.get("work_context", "")),
                backstory=str(p.get("backstory", "")),
                communication_style=str(p.get("communication_style", "")),
            ))
        else:
            fallback_list = FALLBACK_PERSONAS_BY_AGE.get(age_profile["label"], FALLBACK_PERSONAS_BY_AGE["adult"])
            fb = fallback_list[i % len(fallback_list)]
            personas.append(Persona(
                name=name, age=age,
                occupation=fb["occupation"],
                monthly_income=float(fb["monthly_income"]),
                tech_savviness=tech_savviness,
                pain_points=fb["pain_points"],
                current_solution=fb["current_solution"],
                personality_trait=personality,
                segment=segment,
                city=fb.get("city", ""),
                family_status=fb.get("family_status", ""),
                daily_routine=fb.get("daily_routine", ""),
                financial_behavior=fb.get("financial_behavior", ""),
                apps_used=fb.get("apps_used", ""),
                work_context=fb.get("work_context", ""),
                backstory=fb.get("backstory", ""),
                communication_style=fb.get("communication_style", ""),
            ))

    return personas