"""
models.py — Все Pydantic-модели данных для AI Customer Discovery Validator.
Никакой логики — только структуры данных.
"""

from enum import Enum
from typing import List, Optional
from pydantic import BaseModel, Field
import uuid


# ═══════════════════════════════════════════════════════════════
#  2.0 RevenueModel — модель монетизации
# ═══════════════════════════════════════════════════════════════

class RevenueModel(str, Enum):
    SUBSCRIPTION = "subscription"   # Ежемесячная подписка
    PAY_PER_USE  = "pay_per_use"    # Оплата за одно использование
    COMMISSION   = "commission"      # Комиссия со сделок на платформе


# ═══════════════════════════════════════════════════════════════
#  2.1 BusinessType
# ═══════════════════════════════════════════════════════════════

class BusinessType(str, Enum):
    SAAS_B2B = "saas_b2b"
    SAAS_B2C = "saas_b2c"
    MARKETPLACE = "marketplace"
    ECOMMERCE = "ecommerce"
    MOBILE_APP = "mobile_app"
    EDTECH = "edtech"
    FINTECH = "fintech"
    AGENCY = "agency"
    GIG_ECONOMY = "gig_economy"


# ═══════════════════════════════════════════════════════════════
#  2.2 BusinessInput
# ═══════════════════════════════════════════════════════════════

class BusinessInput(BaseModel):
    name: str = ""
    description: str = ""
    business_type: BusinessType = BusinessType.SAAS_B2C
    target_audience: str = ""
    language: str = "Русский"
    country: str = "kazakhstan"
    num_personas: int = 10

    # ── Модель монетизации ────────────────────────────────────
    revenue_model: RevenueModel = RevenueModel.SUBSCRIPTION

    # Подписка (SUBSCRIPTION)
    price: float = 10.0  # $/мес

    # Pay-per-use (PAY_PER_USE)
    price_per_use: float = 5.0           # $ за одно использование
    avg_uses_per_month: float = 5.0      # среднее кол-во использований в мес

    # Комиссия (COMMISSION)
    avg_deal_value: float = 1500.0       # средний чек сделки (в местной валюте)
    commission_rate: float = 0.10        # 10% = 0.10
    avg_deals_per_month: float = 4.0    # среднее кол-во сделок/мес на пользователя
    currency_to_usd: float = 0.0022     # 1 ₸ ≈ $0.0022 (для KZ)

    # ── Финансы ───────────────────────────────────────────────
    initial_capital: float = 10000.0
    monthly_marketing_budget: float = 500.0
    monthly_operating_costs: float = 300.0
    market_size_estimate: int = 100000

    def get_effective_price(self) -> float:
        """
        Возвращает эффективный доход с 1 активного пользователя в месяц (в USD).
        Единая метрика для всех расчётов: LTV, MRR, Monte Carlo, юнит-экономика.

        SUBSCRIPTION : price ($/мес)
        PAY_PER_USE  : price_per_use × avg_uses_per_month
        COMMISSION   : avg_deal_value × currency_to_usd × commission_rate × avg_deals_per_month
        """
        if self.revenue_model == RevenueModel.SUBSCRIPTION:
            return max(self.price, 0.01)
        elif self.revenue_model == RevenueModel.PAY_PER_USE:
            return max(self.price_per_use * self.avg_uses_per_month, 0.01)
        else:  # COMMISSION
            deal_usd = self.avg_deal_value * self.currency_to_usd
            return max(deal_usd * self.commission_rate * self.avg_deals_per_month, 0.01)


# ═══════════════════════════════════════════════════════════════
#  2.3 BenchmarkRange
# ═══════════════════════════════════════════════════════════════

class BenchmarkRange(BaseModel):
    low: float
    median: float
    high: float


# ═══════════════════════════════════════════════════════════════
#  2.4 IndustryBenchmark
# ═══════════════════════════════════════════════════════════════

class IndustryBenchmark(BaseModel):
    business_type: BusinessType
    display_name: str
    conversion_trial_to_paid: BenchmarkRange
    monthly_churn: BenchmarkRange
    cac: BenchmarkRange
    gross_margin: BenchmarkRange
    avg_months_to_first_revenue: int
    failure_rate_12_months: float
    typical_ltv_cac_ratio: BenchmarkRange
    source: str


# ═══════════════════════════════════════════════════════════════
#  2.5 CountryModifier
# ═══════════════════════════════════════════════════════════════

class CountryModifier(BaseModel):
    country: str
    price_sensitivity_multiplier: float
    cac_multiplier: float
    market_size_multiplier: float
    payment_conversion_modifier: float


# ═══════════════════════════════════════════════════════════════
#  2.6 Persona
# ═══════════════════════════════════════════════════════════════

class Persona(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4())[:8])
    name: str
    age: int
    occupation: str
    monthly_income: float
    tech_savviness: str  # "low" / "medium" / "high"
    pain_points: List[str]
    current_solution: str
    personality_trait: str  # "early_adopter" / "pragmatist" / "skeptic" / "conservative"
    segment: str  # "primary" / "secondary" / "edge_case"

    # ── Расширенный профиль для человечных ответов ───────────
    city: str = ""                    # Город: "Алматы, район Бостандык"
    family_status: str = ""           # "Женат, двое детей (3 и 7 лет)"
    daily_routine: str = ""           # "Встаю в 7:30, еду в офис, работаю до 18..."
    financial_behavior: str = ""      # "Коплю на квартиру, трачу осознанно..."
    apps_used: str = ""               # "Kaspi, Instagram, Telegram, 2ГИС"
    work_context: str = ""            # "Работаю в найме в среднем B2B, 3 чел в команде"
    backstory: str = ""               # "2 года назад открыл ИП, столкнулся с..."
    communication_style: str = ""     # "говорит коротко, по делу, иногда с юмором"


# ═══════════════════════════════════════════════════════════════
#  2.7 InterviewQuestion
# ═══════════════════════════════════════════════════════════════

class InterviewQuestion(BaseModel):
    category: str  # "problem" / "solution" / "pricing" / "competition" / "behavior"
    question: str


# ═══════════════════════════════════════════════════════════════
#  2.8 InterviewResponse
# ═══════════════════════════════════════════════════════════════

class InterviewResponse(BaseModel):
    persona_id: str
    persona_name: str
    persona_occupation: str = ""
    problem_severity: int  # 1–10
    solution_fit: int  # 1–10
    willingness_to_pay: int  # 1–10
    switching_likelihood: int  # 1–10
    recommend_likelihood: int  # 1–10
    main_concern: str
    desired_feature: str
    price_feedback: str  # "дорого" / "нормально" / "дёшево"
    would_buy: bool
    raw_opinion: str
    # Флаг ошибки — True если LLM не ответил, метрики невалидны
    is_error: bool = False
    # Диалог интервью по вопросам (фаза 1 + фаза 2)
    conversation: List[dict] = Field(default_factory=list)
    # Каждый элемент: {"phase": 1|2, "category": str, "question": str, "answer": str}


# ═══════════════════════════════════════════════════════════════
#  2.9 AggregatedInterviewResults
# ═══════════════════════════════════════════════════════════════

class AggregatedInterviewResults(BaseModel):
    total_personas: int
    avg_problem_severity: float
    avg_solution_fit: float
    avg_willingness_to_pay: float
    avg_switching_likelihood: float
    avg_nps_score: float
    pct_would_buy: float  # 0.0–1.0
    pct_price_too_high: float
    pct_price_ok: float
    pct_price_too_low: float
    top_concerns: List[str]
    top_desired_features: List[str]
    responses: List[InterviewResponse]
    fallback_count: int = 0


# ═══════════════════════════════════════════════════════════════
#  2.10 MonteCarloRun
# ═══════════════════════════════════════════════════════════════

class MonteCarloRun(BaseModel):
    months: List[int]
    mrr: List[float]
    total_users: List[float]
    balance: List[float]
    revenue_cumulative: List[float]
    costs_cumulative: List[float]
    is_bankrupt: bool
    bankruptcy_month: Optional[int] = None
    final_mrr: float
    final_balance: float
    final_users: int


# ═══════════════════════════════════════════════════════════════
#  2.11 MonteCarloResults
# ═══════════════════════════════════════════════════════════════

class MonteCarloResults(BaseModel):
    num_simulations: int
    num_months: int
    mrr_p10: List[float]
    mrr_p50: List[float]
    mrr_p90: List[float]
    users_p10: List[float]
    users_p50: List[float]
    users_p90: List[float]
    balance_p10: List[float]
    balance_p50: List[float]
    balance_p90: List[float]
    bankruptcy_probability: float
    prob_reach_10k_mrr: float
    prob_reach_1k_users: float
    median_break_even_month: Optional[int] = None


# ═══════════════════════════════════════════════════════════════
#  2.12 UnitEconomicsReport
# ═══════════════════════════════════════════════════════════════

class UnitEconomicsReport(BaseModel):
    ltv: float
    cac: float
    ltv_cac_ratio: float
    cac_payback_months: float
    adjusted_churn: float  # фактический месячный churn, использованный в расчётах
    gross_margin: float  # 0–1
    monthly_burn_rate: float
    runway_months: int
    break_even_month: Optional[int] = None
    benchmark_ltv_cac: BenchmarkRange
    benchmark_churn: BenchmarkRange
    benchmark_conversion: BenchmarkRange


# ═══════════════════════════════════════════════════════════════
#  2.13 Insight
# ═══════════════════════════════════════════════════════════════

class Insight(BaseModel):
    severity: str  # "critical" / "warning" / "success" / "info"
    title: str
    message: str
    recommendation: str = ""
    benchmark_ref: str = ""


# ═══════════════════════════════════════════════════════════════
#  2.14 ValidationReport
# ═══════════════════════════════════════════════════════════════

class ValidationReport(BaseModel):
    business_input: BusinessInput
    interview_results: Optional[AggregatedInterviewResults] = None
    monte_carlo_results: Optional[MonteCarloResults] = None
    unit_economics: Optional[UnitEconomicsReport] = None
    insights: List[Insight] = Field(default_factory=list)
    overall_score: float = 0.0