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

# ── Глобальный CSS — B2B SaaS Дизайн-система ──────────────
st.markdown("""
<meta name="color-scheme" content="light only">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&family=JetBrains+Mono:wght@400;500;600;700&display=swap" rel="stylesheet">

<style>
/* ── Переменные ── */
:root {
    --primary-color: #2563EB;
    --background-color: #F8FAFC;
    --secondary-background-color: #FFFFFF;
    --text-color: #334155;
}

/* ── Прозрачный фон — метаболлы видны сквозь него ── */
html, body {
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif !important;
    background: transparent !important;
    color: #334155 !important;
}

[class*="st-"], .stApp {
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif !important;
    background: transparent !important;
    color: #334155 !important;
}

[data-testid="stAppViewContainer"] {
    background: transparent !important;
}

/* ── Скрываем верхнюю шторку / toolbar Streamlit ── */
[data-testid="stToolbar"],
[data-testid="stDecoration"],
#MainMenu {
    display: none !important;
    visibility: hidden !important;
}

[data-testid="stHeader"] {
    background: rgba(248, 250, 252, 0.80) !important;
    backdrop-filter: blur(14px) !important;
    -webkit-backdrop-filter: blur(14px) !important;
    border-bottom: 1px solid rgba(226, 232, 240, 0.7) !important;
}

/* Принудительная читаемость заголовков и текста */
[data-testid="stMarkdownContainer"] p,
[data-testid="stMarkdownContainer"] span,
[data-testid="stMarkdownContainer"] li {
    color: #334155 !important;
}

[data-testid="stMarkdownContainer"] h1,
[data-testid="stMarkdownContainer"] h2,
[data-testid="stMarkdownContainer"] h3,
[data-testid="stMarkdownContainer"] h4 {
    color: #0F172A !important;
}

/* Вкладки (Tabs) */
button[data-baseweb="tab"] {
    background-color: transparent !important;
}
button[data-baseweb="tab"][aria-selected="true"] {
    color: #2563EB !important;
    border-bottom: 2px solid #2563EB !important;
}
button[data-baseweb="tab"][aria-selected="false"] {
    color: #64748B !important;
}

/* Поля ввода */
div[data-testid="stTextInput"] input,
div[data-testid="stTextArea"] textarea,
div[data-testid="stNumberInput"] input {
    background-color: #FFFFFF !important;
    color: #0F172A !important;
    border: 1px solid #CBD5E1 !important;
    border-radius: 8px !important;
}
div[data-testid="stTextInput"] input:focus,
div[data-testid="stTextArea"] textarea:focus,
div[data-testid="stNumberInput"] input:focus {
    border-color: #2563EB !important;
    box-shadow: 0 0 0 1px #2563EB !important;
}

/* ── Контейнер приложения ── */
.block-container {
    padding-top: 1.25rem !important;
    padding-bottom: 3.5rem !important;
    max-width: 1140px !important;
    background: transparent !important;
}


/* ── Dropdown (selectbox) ── белый список, видимый на любом фоне ── */
[data-baseweb="select"] > div {
    background-color: rgba(255,255,255,0.95) !important;
    color: #0F172A !important;
}
[data-baseweb="popover"] [role="listbox"],
[data-baseweb="menu"],
ul[data-baseweb="menu"] {
    background-color: #FFFFFF !important;
    color: #0F172A !important;
    border: 1px solid #E2E8F0 !important;
    border-radius: 8px !important;
    box-shadow: 0 4px 16px rgba(15,23,42,0.10) !important;
}
[data-baseweb="option"] {
    background-color: #FFFFFF !important;
    color: #0F172A !important;
}
[data-baseweb="option"]:hover {
    background-color: #EFF6FF !important;
    color: #2563EB !important;
}

/* Поля ввода — полупрозрачные */
div[data-testid="stTextInput"] input,
div[data-testid="stTextArea"] textarea,
div[data-testid="stNumberInput"] input {
    background-color: rgba(255,255,255,0.90) !important;
}

/* ── Шапка ── */
.app-header {
    border-bottom: 1px solid #E2E8F0;
    padding-bottom: 1.25rem;
    margin-bottom: 1.5rem;
}
.app-title {
    font-size: 1.75rem;
    font-weight: 800;
    color: #0F172A !important;
    letter-spacing: -0.5px;
    margin: 0 0 4px 0;
}
.app-subtitle {
    font-size: 0.9rem;
    color: #64748B !important;
    margin: 0;
}

/* ── Заголовки ── */
h1, h2, h3, h4 {
    color: #0F172A !important;
    letter-spacing: -0.3px;
    font-weight: 700 !important;
}

/* ── Hero-карточка ── */
.hero-card {
    background: rgba(255, 255, 255, 0.88);
    backdrop-filter: blur(12px);
    -webkit-backdrop-filter: blur(12px);
    border: 1px solid rgba(226, 232, 240, 0.8);
    border-radius: 12px;
    padding: 24px 28px;
    box-shadow: 0 1px 3px rgba(15, 23, 42, 0.06);
    margin-bottom: 1.75rem;
}
.hero-badge {
    display: inline-block;
    background: #EFF6FF;
    color: #2563EB;
    font-size: 0.72rem;
    font-weight: 700;
    letter-spacing: 0.6px;
    text-transform: uppercase;
    padding: 4px 10px;
    border-radius: 6px;
    margin-bottom: 10px;
}
.hero-title {
    font-size: 1.35rem;
    font-weight: 800;
    color: #0F172A;
    margin: 0 0 8px 0;
    letter-spacing: -0.3px;
}
.hero-desc {
    font-size: 0.9rem;
    color: #334155;
    line-height: 1.6;
    margin-bottom: 18px;
}
.hero-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(240px, 1fr));
    gap: 12px;
}
.hero-pill {
    background: #F8FAFC;
    border: 1px solid #E2E8F0;
    border-radius: 8px;
    padding: 14px 16px;
}
.hero-pill-num {
    font-family: 'JetBrains Mono', monospace;
    font-weight: 700;
    color: #2563EB;
    font-size: 0.8rem;
    margin-bottom: 4px;
}
.hero-pill-title {
    font-weight: 700;
    color: #0F172A;
    font-size: 0.85rem;
    margin-bottom: 4px;
}
.hero-pill-sub {
    font-size: 0.78rem;
    color: #64748B;
    line-height: 1.45;
}

/* ── Баннер завершения анализа ── */
.done-banner {
    background: #F0FDFA;
    border: 1px solid #CCFBF1;
    border-radius: 10px;
    padding: 14px 20px;
    margin-bottom: 1.5rem;
    display: flex;
    align-items: center;
    gap: 14px;
}
.done-banner-icon {
    font-family: 'JetBrains Mono', monospace;
    font-size: 1rem;
    background: #0D9488;
    color: white;
    width: 26px;
    height: 26px;
    border-radius: 50%;
    display: flex;
    align-items: center;
    justify-content: center;
    font-weight: 700;
}
.done-banner-text { font-size: 0.95rem; font-weight: 700; color: #0F172A; }
.done-banner-sub  { font-size: 0.82rem; color: #0D9488; font-weight: 500; }

/* ── Empty State Card ── */
.empty-state-card {
    background: rgba(255, 255, 255, 0.88);
    backdrop-filter: blur(10px);
    -webkit-backdrop-filter: blur(10px);
    border: 1px solid rgba(226, 232, 240, 0.8);
    border-radius: 12px;
    padding: 48px 24px;
    text-align: center;
    margin: 2rem 0;
    box-shadow: 0 1px 3px rgba(15, 23, 42, 0.06);
}
.empty-state-title {
    font-size: 1.15rem;
    font-weight: 700;
    color: #0F172A;
    margin-bottom: 8px;
}
.empty-state-desc {
    font-size: 0.9rem;
    color: #64748B;
    max-width: 540px;
    margin: 0 auto;
    line-height: 1.6;
}

/* ── Метрики Streamlit ── */
[data-testid="stMetric"] {
    background: rgba(255, 255, 255, 0.85) !important;
    backdrop-filter: blur(10px) !important;
    -webkit-backdrop-filter: blur(10px) !important;
    border: 1px solid rgba(226, 232, 240, 0.8) !important;
    border-radius: 12px !important;
    padding: 16px 20px !important;
    box-shadow: 0 1px 3px rgba(15, 23, 42, 0.06) !important;
}
[data-testid="stMetricLabel"] {
    font-size: 0.72rem !important;
    font-weight: 600 !important;
    text-transform: uppercase !important;
    letter-spacing: 0.5px !important;
    color: #64748B !important;
}
[data-testid="stMetricValue"] {
    font-family: 'JetBrains Mono', monospace !important;
    font-size: 1.55rem !important;
    font-weight: 700 !important;
    color: #0F172A !important;
}

/* ── Карточка скоринга ── */
.score-card {
    background: rgba(255, 255, 255, 0.88);
    backdrop-filter: blur(12px);
    -webkit-backdrop-filter: blur(12px);
    border: 1px solid rgba(226, 232, 240, 0.8);
    border-radius: 12px;
    padding: 24px;
    box-shadow: 0 1px 3px rgba(15, 23, 42, 0.06);
}
.score-number {
    font-family: 'JetBrains Mono', monospace;
    font-size: 3.5rem;
    font-weight: 800;
    line-height: 1;
    color: #0F172A;
}
.score-denom {
    font-family: 'JetBrains Mono', monospace;
    font-size: 1.3rem;
    color: #64748B;
    font-weight: 500;
}

/* ── Семантические бейджи ── */
.badge-success {
    background: #F0FDFA;
    color: #0D9488;
    border: 1px solid #CCFBF1;
    padding: 5px 12px;
    border-radius: 20px;
    font-weight: 600;
    font-size: 0.82rem;
    display: inline-block;
}
.badge-warning {
    background: #FFFBEB;
    color: #D97706;
    border: 1px solid #FEF3C7;
    padding: 5px 12px;
    border-radius: 20px;
    font-weight: 600;
    font-size: 0.82rem;
    display: inline-block;
}
.badge-danger {
    background: #FFF1F2;
    color: #E11D48;
    border: 1px solid #FFE4E6;
    padding: 5px 12px;
    border-radius: 20px;
    font-weight: 600;
    font-size: 0.82rem;
    display: inline-block;
}

/* ── Карточки конкурентного анализа ── */
.comp-card {
    background: rgba(255, 255, 255, 0.88);
    backdrop-filter: blur(10px);
    -webkit-backdrop-filter: blur(10px);
    border: 1px solid rgba(226, 232, 240, 0.8);
    border-radius: 12px;
    padding: 18px 22px;
    box-shadow: 0 1px 3px rgba(15, 23, 42, 0.06);
    margin-bottom: 12px;
}
.comp-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    border-bottom: 1px solid #F1F5F9;
    padding-bottom: 10px;
    margin-bottom: 12px;
}
.comp-name {
    font-weight: 700;
    font-size: 1rem;
    color: #0F172A;
}
.comp-price {
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.8rem;
    font-weight: 600;
    color: #2563EB;
    background: #EFF6FF;
    padding: 4px 10px;
    border-radius: 6px;
    border: 1px solid #DBEAFE;
}
.comp-badge-direct {
    background: #FFF1F2;
    color: #E11D48;
    border: 1px solid #FFE4E6;
    font-size: 0.72rem;
    font-weight: 600;
    padding: 3px 8px;
    border-radius: 4px;
}
.comp-badge-indirect {
    background: #FFFBEB;
    color: #D97706;
    border: 1px solid #FEF3C7;
    font-size: 0.72rem;
    font-weight: 600;
    padding: 3px 8px;
    border-radius: 4px;
}
.comp-grid {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 16px;
}
.comp-section-title {
    font-size: 0.72rem;
    font-weight: 700;
    letter-spacing: 0.5px;
    text-transform: uppercase;
    color: #64748B;
    margin-bottom: 4px;
}
.comp-section-body {
    font-size: 0.85rem;
    color: #334155;
    line-height: 1.5;
}

/* ── Диалоги интервью ── */
.phase-tag {
    display: inline-block;
    background: #EFF6FF;
    color: #2563EB;
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.72rem;
    font-weight: 700;
    padding: 3px 8px;
    border-radius: 4px;
    margin: 10px 0 6px 0;
}
.chat-q {
    color: #475569;
    font-size: 0.88rem;
    font-style: italic;
    margin: 4px 0 4px 0;
}
.chat-a {
    background: #F8FAFC;
    border-left: 3px solid #2563EB;
    border-radius: 0 8px 8px 0;
    padding: 10px 14px;
    font-size: 0.88rem;
    color: #0F172A;
    margin: 4px 0 12px 0;
    line-height: 1.5;
}
.mono-val {
    font-family: 'JetBrains Mono', monospace;
    font-weight: 600;
}

/* ── Прогресс шаги ── */
.step-row { display:flex; align-items:center; gap:10px; margin:7px 0; }
.step-dot-done    { width:9px;height:9px;border-radius:50%;background:#0D9488;flex-shrink:0; }
.step-dot-active  { width:9px;height:9px;border-radius:50%;background:#2563EB;flex-shrink:0;animation:pulse 1s infinite; }
.step-dot-pending { width:9px;height:9px;border-radius:50%;background:#CBD5E1;flex-shrink:0; }
.step-text-done    { font-size:0.85rem;color:#0D9488;font-weight:500; }
.step-text-active  { font-size:0.85rem;color:#1D4ED8;font-weight:700; }
.step-text-pending { font-size:0.85rem;color:#94A3B8; }
@keyframes pulse { 0%,100%{opacity:1} 50%{opacity:0.35} }

/* ── Кнопки ── */
.stButton > button {
    border-radius: 8px !important;
    font-weight: 600 !important;
    font-size: 0.88rem !important;
    padding: 0.5rem 1rem !important;
    transition: all 0.15s ease !important;
}
.stButton > button[kind="primary"] {
    background-color: #2563EB !important;
    color: #FFFFFF !important;
    border: 1px solid #2563EB !important;
    box-shadow: 0 1px 2px rgba(37, 99, 235, 0.15) !important;
}
.stButton > button[kind="primary"]:hover {
    background-color: #1D4ED8 !important;
    border-color: #1D4ED8 !important;
}
.stButton > button[kind="secondary"] {
    background-color: #FFFFFF !important;
    color: #0F172A !important;
    border: 1px solid #CBD5E1 !important;
}
.stButton > button[kind="secondary"]:hover {
    background-color: #F8FAFC !important;
    border-color: #94A3B8 !important;
}

/* ── Скрываем сайдбар полностью ── */
[data-testid="stSidebarNav"] { display: none !important; }
button[data-testid="collapsedControl"] { display: none !important; }
section[data-testid="stSidebar"] { display: none !important; }
[data-testid="stSidebar"] { display: none !important; }

/* Убираем стрелочки delta у метрик */
[data-testid="stMetricDelta"] svg { display:none; }

/* ── Entrance animations ── */
@keyframes fadeUp {
    from { opacity: 0; transform: translateY(10px); }
    to   { opacity: 1; transform: translateY(0); }
}
.hero-card        { animation: fadeUp 0.4s ease-out both; }
.empty-state-card { animation: fadeUp 0.35s ease-out both; }
[data-testid="stMetric"] { animation: fadeUp 0.3s ease-out both; }
.comp-card        { animation: fadeUp 0.35s ease-out both; }
.score-card       { animation: fadeUp 0.4s ease-out both; }
.done-banner      { animation: fadeUp 0.3s ease-out both; }
[data-testid="stMetric"]:nth-child(1) { animation-delay: 0ms; }
[data-testid="stMetric"]:nth-child(2) { animation-delay: 60ms; }
[data-testid="stMetric"]:nth-child(3) { animation-delay: 120ms; }
[data-testid="stMetric"]:nth-child(4) { animation-delay: 180ms; }

/* ── Принудительная светлая тема при dark-mode ОС/браузера ── */
@media (prefers-color-scheme: dark) {
    html, body { background: transparent !important; color: #334155 !important; }
    .stApp, [data-testid="stAppViewContainer"], [data-testid="stMain"],
    section[data-testid="stMain"], .block-container {
        background: transparent !important;
        color: #334155 !important;
    }
    [data-testid="stHeader"] { background: rgba(248,250,252,0.85) !important; }
    [data-testid="stMetric"] { background: rgba(255,255,255,0.90) !important; border-color: #E2E8F0 !important; }
    [data-testid="stMetricLabel"] { color: #64748B !important; }
    [data-testid="stMetricValue"] { color: #0F172A !important; }
    .hero-card, .comp-card, .score-card, .empty-state-card {
        background: rgba(255,255,255,0.90) !important;
        border-color: #E2E8F0 !important;
    }
    .chat-a { background: rgba(248,250,252,0.90) !important; color: #0F172A !important; }
    button[data-baseweb="tab"] { background-color: transparent !important; color: #64748B !important; }
    button[data-baseweb="tab"][aria-selected="true"] { color: #2563EB !important; }
    div[data-testid="stTextInput"] input,
    div[data-testid="stTextArea"] textarea,
    div[data-testid="stNumberInput"] input {
        background-color: rgba(255,255,255,0.92) !important;
        color: #0F172A !important;
        border-color: #CBD5E1 !important;
    }
    [data-baseweb="select"] > div { background-color: rgba(255,255,255,0.95) !important; color: #0F172A !important; }
    [data-baseweb="option"],
    [data-baseweb="menu"],
    ul[data-baseweb="menu"] { background-color: #FFFFFF !important; color: #0F172A !important; }
    [data-testid="stMarkdownContainer"] p,
    [data-testid="stMarkdownContainer"] span,
    [data-testid="stMarkdownContainer"] li { color: #334155 !important; }
    [data-testid="stMarkdownContainer"] h1,
    [data-testid="stMarkdownContainer"] h2,
    [data-testid="stMarkdownContainer"] h3 { color: #0F172A !important; }
    .hero-title, .comp-name, .score-number, .empty-state-title, .done-banner-text { color: #0F172A !important; }
    .app-title { color: #0F172A !important; }
    h1, h2, h3, h4 { color: #0F172A !important; }
}
</style>
""", unsafe_allow_html=True)

# ── Метабольный фон (анимированные пузырьки) ─────────────────
import streamlit.components.v1 as _comp_meta
_comp_meta.html("""
<script>
(function() {
    var doc = window.parent.document;
    if (doc.getElementById('blue-metaballs-bg')) return;

    var bg = doc.createElement('div');
    bg.id = 'blue-metaballs-bg';
    bg.style.cssText = 'position:fixed;inset:0;z-index:0;pointer-events:none;background:linear-gradient(135deg,#F0F8FF 0%,#DBEAFE 55%,#EFF6FF 100%);overflow:hidden;';

    bg.innerHTML = '<svg style="position:absolute;width:0;height:0;"><defs><filter id="blue-goo"><feGaussianBlur in="SourceGraphic" stdDeviation="22" result="blur"/><feColorMatrix in="blur" mode="matrix" values="1 0 0 0 0  0 1 0 0 0  0 0 1 0 0  0 0 0 20 -8" result="goo"/></filter></defs></svg><canvas id="blue-mb-canvas" style="width:100%;height:100%;display:block;filter:url(#blue-goo);opacity:0.72;"></canvas>';

    doc.body.prepend(bg);

    var canvas = doc.getElementById('blue-mb-canvas');
    var ctx = canvas.getContext('2d');
    var w, h;
    function resize() {
        w = canvas.width  = window.parent.innerWidth;
        h = canvas.height = window.parent.innerHeight;
    }
    resize();
    window.parent.addEventListener('resize', resize);

    var colors = ['#93C5FD','#60A5FA','#BFDBFE','#7DD3FC','#A5B4FC','#BAE6FD'];
    var blobs = [];
    for (var i = 0; i < 11; i++) {
        blobs.push({
            x: Math.random() * w,
            y: Math.random() * h,
            vx: (Math.random() - 0.5) * 0.52,
            vy: (Math.random() - 0.5) * 0.52,
            r: 70 + Math.random() * 100,
            color: colors[i % colors.length]
        });
    }

    function animate() {
        ctx.clearRect(0, 0, w, h);
        for (var j = 0; j < blobs.length; j++) {
            var b = blobs[j];
            b.x += b.vx;
            b.y += b.vy;
            if (b.x < -b.r) b.x = w + b.r;
            if (b.x > w + b.r) b.x = -b.r;
            if (b.y < -b.r) b.y = h + b.r;
            if (b.y > h + b.r) b.y = -b.r;
            ctx.beginPath();
            ctx.arc(b.x, b.y, b.r, 0, Math.PI * 2);
            ctx.fillStyle = b.color;
            ctx.fill();
        }
        requestAnimationFrame(animate);
    }
    animate();
})();
</script>
""", height=0, width=0)

# ── Шапка ────────────────────────────────────────────────────
st.markdown("""
<div class="app-header">
  <p class="app-title">AI Startup Validator</p>
  <p class="app-subtitle">Инструмент предварительной валидации бизнес-идей · Mom Test · Lean Startup</p>
</div>
""", unsafe_allow_html=True)

# Счётчик запусков (только критическое — лимит)
_remaining = get_remaining_runs()
_limit_reached = _remaining == 0
if _limit_reached:
    _reset_time = next_reset_info()
    st.error(f"Дневной лимит исчерпан — {MAX_DAILY_RUNS}/{MAX_DAILY_RUNS} запусков использовано. Лимит сбросится через **{_reset_time}**")
elif _remaining <= 3:
    st.warning(f"Осталось запусков сегодня: **{_remaining}** из {MAX_DAILY_RUNS}")

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
    st.caption("Глубинные двухфазные интервью по методологии Mom Test с репрезентативной выборкой клиентов")

    _ir_report: "ValidationReport" = st.session_state.report
    _ir = _ir_report.interview_results if _ir_report else None

    if _ir is None:
        # ── Skeleton: показываем структуру без данных ──
        st.markdown("""
        <div class="empty-state-card">
          <div class="empty-state-title">Customer Discovery ещё не проводился</div>
          <div class="empty-state-desc">
            Перейдите на вкладку <strong>«Ваша идея»</strong>, заполните параметры и нажмите
            «Запустить валидацию». После анализа здесь появятся результаты двухфазных интервью,
            профили персон, ценовое восприятие и скоринг готовности к покупке.
          </div>
        </div>
        """, unsafe_allow_html=True)

        st.subheader("Сводка")
        _sc1, _sc2, _sc3, _sc4 = st.columns(4)
        _sc1.metric("Острота проблемы", "— / 10")
        _sc2.metric("Готовы купить", "—%")
        _sc3.metric("Рекомендация (ср.)", "— / 10")
        _sc4.metric("Solution Fit", "— / 10")

        st.divider()
        _col_pie, _col_con = st.columns([1, 1])
        with _col_pie:
            st.markdown("**Ценовое восприятие**")
            _fig_sk = go.Figure(data=[go.Pie(
                labels=["Дорого", "Нормально", "Дёшево"],
                values=[1, 1, 1],
                marker_colors=["#E2E8F0", "#CBD5E1", "#F1F5F9"],
                hole=0.55,
                textinfo="none",
                hoverinfo="skip",
            )])
            _fig_sk.update_layout(
                height=220,
                margin=dict(t=10, b=10, l=10, r=10),
                showlegend=False,
                paper_bgcolor="#FFFFFF",
                plot_bgcolor="#FFFFFF",
                annotations=[dict(
                    text="<b>Ожидание<br>данных</b>",
                    x=0.5, y=0.5, font_size=13,
                    showarrow=False, font_color="#94A3B8"
                )],
            )
            st.plotly_chart(_fig_sk, use_container_width=True)
        with _col_con:
            st.markdown("**Топ-3 опасения**")
            for _t in ["— Ключевые барьеры перехода", "— Скрытые риски и недоверие", "— Ценовые возражения"]:
                st.markdown(f'<div style="color:#94A3B8;font-size:0.88rem;padding:4px 0">{_t}</div>', unsafe_allow_html=True)
            st.markdown("**Топ-3 желаемые функции**")
            for _t in ["— MVP-требования", "— Функционал с WTP", "— Формат интеграции"]:
                st.markdown(f'<div style="color:#94A3B8;font-size:0.88rem;padding:4px 0">{_t}</div>', unsafe_allow_html=True)

    else:
        _ir = _ir_report.interview_results

        if _ir.fallback_count > 0:
            valid_count = _ir.total_personas - _ir.fallback_count
            st.warning(
                f"Внимание: {_ir.fallback_count} из {_ir.total_personas} интервью завершились ошибкой LLM. "
                f"Метрики рассчитаны по {valid_count} валидным ответам."
            )

        # ── Сводные метрики ───────────────────────────────────────
        st.subheader("Сводка")
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("Острота проблемы", f"{_ir.avg_problem_severity:.1f} / 10")
        with col2:
            st.metric("Готовы купить", f"{_ir.pct_would_buy * 100:.0f}%")
        with col3:
            st.metric("Рекомендация (ср.)", f"{_ir.avg_nps_score:.1f} / 10")
        with col4:
            st.metric("Solution Fit", f"{_ir.avg_solution_fit:.1f} / 10")

        st.divider()

        col_pie, col_concerns = st.columns([1, 1])

        with col_pie:
            st.markdown("**Ценовое восприятие**")
            labels = ["Дорого", "Нормально", "Дёшево"]
            values = [_ir.pct_price_too_high, _ir.pct_price_ok, _ir.pct_price_too_low]
            marker_colors = ["#0F172A", "#2563EB", "#64748B"]
            fig_pie = go.Figure(data=[go.Pie(
                labels=labels,
                values=values,
                marker_colors=marker_colors,
                hole=0.55,
                textinfo="percent+label",
                textposition="auto",
                insidetextfont=dict(family="JetBrains Mono, monospace", size=12, color="#FFFFFF"),
                outsidetextfont=dict(family="Inter, sans-serif", size=12, color="#0F172A"),
                hoverinfo="label+percent",
            )])
            fig_pie.update_layout(
                height=260,
                margin=dict(t=15, b=15, l=15, r=15),
                showlegend=True,
                paper_bgcolor="#FFFFFF",
                plot_bgcolor="#FFFFFF",
                font=dict(family="Inter, sans-serif", color="#334155", size=12),
                legend=dict(
                    orientation="h",
                    yanchor="bottom",
                    y=-0.25,
                    xanchor="center",
                    x=0.5,
                    font=dict(family="Inter, sans-serif", size=12, color="#475569")
                ),
            )
            st.plotly_chart(fig_pie, use_container_width=True)

        with col_concerns:
            st.markdown("**Топ-3 опасения**")
            if _ir.top_concerns:
                for concern in _ir.top_concerns:
                    st.warning(concern)
            else:
                st.caption("Нет данных")

            st.markdown("**Топ-3 желаемые функции**")
            if _ir.top_desired_features:
                for feature in _ir.top_desired_features:
                    st.info(feature)
            else:
                st.caption("Нет данных")

        # ── Детальные ответы персон ───────────────────────────────
        st.divider()
        st.subheader("Ответы персон")

        for resp in _ir.responses:
            buy_status = "Купит" if resp.would_buy else "Не купит"
            err_status = " · Ошибка API" if getattr(resp, "is_error", False) else ""
            header_title = f"{resp.persona_name} · {resp.persona_occupation} · {buy_status}{err_status}"

            with st.expander(header_title):
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
                            p_label = "Фаза 1 · Прошлый опыт (без знания о продукте)" if phase == 1 else "Фаза 2 · Презентация продукта и цена"
                            st.markdown(f"<div class='phase-tag'>{p_label}</div>", unsafe_allow_html=True)

                        if q:
                            st.markdown(f"<div class='chat-q'>— {q}</div>", unsafe_allow_html=True)
                        if a:
                            st.markdown(f"<div class='chat-a'>{a}</div>", unsafe_allow_html=True)
                    st.divider()
                elif resp.raw_opinion:
                    st.markdown(f"*«{resp.raw_opinion}»*")
                    st.divider()

                st.caption("Оценки респондента")
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

                st.markdown(f"**Цена:** `{resp.price_feedback}` &nbsp;&nbsp; **Купит:** {'да' if resp.would_buy else 'нет'}")
                if resp.main_concern:
                    st.markdown(f"**Ключевое опасение:** {resp.main_concern}")
                if resp.desired_feature:
                    st.markdown(f"**Желаемая функция:** {resp.desired_feature}")




# ═══════════════════════════════════════════════════════════════
#  TAB 3 — Результаты и оценка
# ═══════════════════════════════════════════════════════════════

with tab3:
    _r3 = st.session_state.report

    if _r3 is None:
        # ── Skeleton ──
        st.markdown("""
        <div class="empty-state-card">
          <div class="empty-state-title">Инвестиционный отчёт ещё не сформирован</div>
          <div class="empty-state-desc">
            Перейдите на вкладку <strong>«Ваша идея»</strong> и запустите валидацию — здесь появятся
            Overall Viability Score, юнит-экономика (LTV, CAC, Runway, Payback) и симуляция Монте-Карло на 24 месяца.
          </div>
        </div>
        """, unsafe_allow_html=True)

        st.subheader("Общая оценка жизнеспособности (Overall Viability Score)")
        _c1, _c2 = st.columns([1, 2])
        with _c1:
            st.markdown(
                "<div class='score-card'>"
                "<div class='score-number' style='color:#CBD5E1;font-size:1.8rem'>—<span class='score-denom' style='font-size:0.95rem'>/100</span></div>"
                "<div style='margin-top:14px'><span class='badge-warning'>Ожидание симуляции</span></div>"
                "</div>",
                unsafe_allow_html=True,
            )
            st.progress(0.0)
        with _c2:
            st.markdown("**Компоненты скоринга**")
            st.caption("Валидация проблемы: **— / 40.0**")
            st.progress(0.0)
            st.caption("Solution Fit и спрос: **— / 35.0**")
            st.progress(0.0)
            st.caption("Экономическая устойчивость: **— / 25.0**")
            st.progress(0.0)

        st.divider()
        st.subheader("Юнит-экономика")
        st.caption("Расчёт на основе эффективного дохода, страновых коэффициентов и отраслевых бенчмарков")
        _m1, _m2, _m3, _m4 = st.columns(4)
        _m1.metric("LTV (пожизненная ценность)", "—")
        _m2.metric("CAC (стоимость привлечения)", "—")
        _m3.metric("LTV : CAC", "—")
        _m4.metric("Окупаемость CAC", "—")
        _m5, _m6, _m7, _m8 = st.columns(4)
        _m5.metric("Monthly Burn Rate", "—")
        _m6.metric("Runway (статический)", "—")
        _m7.metric("Break-even", "—")
        _m8.metric("Базовый отток (Churn)", "—")
        _m9, _m10, _m11 = st.columns(3)
        _m9.metric("Дно кассовой ямы", "—")
        _m10.metric("Расход капитала до безубытка", "—")
        _m11.metric("Дефицит капитала", "—")

        st.divider()
        st.subheader("Вероятностный прогноз роста MRR — Fan Chart")
        st.caption("10 000 симуляций · 24 месяца · когортный отток · стресс-тест ликвидности")
        _fig_empty = go.Figure()
        _fig_empty.add_trace(go.Scatter(
            x=list(range(25)), y=[0]*25,
            mode="lines",
            line=dict(color="#E2E8F0", dash="dot", width=1.5),
            name="Базовая линия",
        ))
        _fig_empty.update_layout(
            title=dict(text="Коридор вероятности (P10–P90) сформируется после запуска анализа",
                       font=dict(size=13, color="#94A3B8")),
            xaxis=dict(title="Месяц", gridcolor="#F1F5F9"),
            yaxis=dict(title="MRR (USD)", gridcolor="#F1F5F9"),
            height=300,
            margin=dict(l=20, r=20, t=50, b=20),
            paper_bgcolor="#FFFFFF",
            plot_bgcolor="#FFFFFF",
        )
        st.plotly_chart(_fig_empty, use_container_width=True)
        _mc1, _mc2, _mc3, _mc4 = st.columns(4)
        _mc1.metric("Риск банкротства (24 мес)", "—")
        _mc2.metric("Медианная безубыточность", "—")
        _mc3.metric("Вероятность $10K+ MRR", "—")
        _mc4.metric("Вероятность 1 000+ клиентов", "—")

        st.divider()
        st.subheader("Анализ конкурентной среды")
        st.caption("Поиск прямых и косвенных конкурентов с оценкой сильных и слабых сторон.")
        for _cn, _ct, _cd in [
            ("Конкурент 1", "Прямой конкурент", "comp-badge-direct"),
            ("Конкурент 2", "Косвенный аналог", "comp-badge-indirect"),
        ]:
            st.markdown(f"""
            <div class="comp-card" style="opacity:0.45">
              <div class="comp-header">
                <div style="display:flex;align-items:center;gap:10px;">
                  <span class="comp-name" style="color:#94A3B8">{_cn}</span>
                  <span class="{_cd}">{_ct}</span>
                </div>
              </div>
              <div class="comp-grid">
                <div>
                  <div class="comp-section-title" style="color:#0D9488;">Ключевые преимущества</div>
                  <div class="comp-section-body" style="color:#CBD5E1;">Формируется после анализа...</div>
                </div>
                <div>
                  <div class="comp-section-title" style="color:#E11D48;">Слабые стороны</div>
                  <div class="comp-section-body" style="color:#CBD5E1;">Формируется после анализа...</div>
                </div>
              </div>
            </div>
            """, unsafe_allow_html=True)

        st.divider()
        st.subheader("Экспертные инсайты и рекомендации")
        st.markdown(
            '<div style="background:#F8FAFC;border:1px solid #E2E8F0;border-radius:10px;padding:16px 20px;'
            'color:#94A3B8;font-size:0.9rem;">Инсайты инвестиционного комитета появятся после симуляции.</div>',
            unsafe_allow_html=True,
        )

    else:
        report = _r3

        # ── Overall Viability Score ───────────────────────────────
        st.subheader("Общая оценка жизнеспособности (Overall Viability Score)")

        score = int(report.overall_score)
        col_score1, col_score2 = st.columns([1, 2])

        with col_score1:
            if score <= 25:
                verdict_class = "badge-danger"
                verdict_text  = "Критический риск — требуется пересмотр"
            elif score <= 50:
                verdict_class = "badge-danger"
                verdict_text  = "Высокий риск — значительные доработки"
            elif score <= 65:
                verdict_class = "badge-warning"
                verdict_text  = "Умеренный риск — необходима проверка"
            else:
                verdict_class = "badge-success"
                verdict_text  = "Перспективная идея — рекомендуется пилот"

            st.markdown(
                f"<div class='score-card'>"
                f"<div class='score-number'>{score}<span class='score-denom'>/100</span></div>"
                f"<div style='margin-top:14px'><span class='{verdict_class}'>{verdict_text}</span></div>"
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
                    color = "rgba(225,29,72,0.04)" if is_bankrupt else "rgba(37,99,235,0.04)"
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
                fillcolor="rgba(37, 99, 235, 0.08)",
                line=dict(width=0),
                showlegend=True,
                name="Коридор вероятности (P10–P90)",
                hoverinfo="skip",
            ))
            fig_mc.add_trace(go.Scatter(
                x=months_x, y=mc.mrr_p90,
                mode="lines",
                line=dict(color="#0D9488", width=1.8, dash="dot"),
                name=f"Оптимистичный P90 (${mc.mrr_p90[-1]:,.0f})",
            ))
            fig_mc.add_trace(go.Scatter(
                x=months_x, y=mc.mrr_p10,
                mode="lines",
                line=dict(color="#E11D48", width=1.8, dash="dot"),
                name=f"Пессимистичный P10 (${mc.mrr_p10[-1]:,.0f})",
            ))
            fig_mc.add_trace(go.Scatter(
                x=months_x, y=mc.mrr_p50,
                mode="lines",
                line=dict(color="#2563EB", width=3),
                name=f"Медианный прогноз P50 (${mc.mrr_p50[-1]:,.0f})",
            ))

            if report.unit_economics:
                br = report.unit_economics.monthly_burn_rate
                fig_mc.add_hline(
                    y=br,
                    line_dash="dot", line_color="#D97706", line_width=1.5,
                    annotation_text=f"Burn Rate ${br:,.0f}/мес",
                    annotation_position="bottom right",
                    annotation_font_color="#D97706",
                )

            fig_mc.update_layout(
                title=dict(
                    text="Динамика Monthly Recurring Revenue — 24 месяца",
                    font=dict(family="Inter, sans-serif", size=14, color="#0F172A"),
                ),
                xaxis=dict(title="Месяц", gridcolor="#E2E8F0",
                           tickfont=dict(family="JetBrains Mono, monospace", size=11, color="#64748B")),
                yaxis=dict(title="MRR (USD)", gridcolor="#E2E8F0",
                           tickfont=dict(family="JetBrains Mono, monospace", size=11, color="#64748B")),
                height=420,
                margin=dict(l=20, r=20, t=60, b=20),
                hovermode="x unified",
                legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1,
                            font=dict(family="Inter, sans-serif", size=11, color="#475569")),
                paper_bgcolor="#FFFFFF",
                plot_bgcolor="#FFFFFF",
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
                for comp in mr.competitors:
                    is_direct = "прямой" in comp.category.lower()
                    badge_class = "comp-badge-direct" if is_direct else "comp-badge-indirect"
                    badge_text = "Прямой конкурент" if is_direct else "Косвенный аналог"
                    price_html = f"<div class='comp-price'>{comp.price_point}</div>" if comp.price_point else ""

                    st.markdown(f"""
                    <div class="comp-card">
                      <div class="comp-header">
                        <div style="display:flex;align-items:center;gap:10px;">
                          <span class="comp-name">{comp.name}</span>
                          <span class="{badge_class}">{badge_text}</span>
                        </div>
                        {price_html}
                      </div>
                      <div class="comp-grid">
                        <div>
                          <div class="comp-section-title" style="color:#0D9488;">Ключевые преимущества</div>
                          <div class="comp-section-body">{comp.strengths}</div>
                        </div>
                        <div>
                          <div class="comp-section-title" style="color:#E11D48;">Слабые стороны и уязвимости</div>
                          <div class="comp-section-body">{comp.weaknesses}</div>
                        </div>
                      </div>
                    </div>
                    """, unsafe_allow_html=True)

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
