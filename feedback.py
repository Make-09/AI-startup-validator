"""
feedback.py — Отправка отзывов пользователей на email через Gmail SMTP.

Настройка (один раз):
  1. Включите двухфакторную аутентификацию на вашем Gmail аккаунте:
     https://myaccount.google.com/security → «Двухэтапная аутентификация»

  2. Создайте «Пароль приложения»:
     https://myaccount.google.com/apppasswords
     → Выберите «Другое» → введите «Startup Validator» → скопируйте 16-значный пароль

  3. Добавьте в Streamlit Cloud Secrets (Settings → Secrets):
       EMAIL_APP_PASSWORD = "xxxx xxxx xxxx xxxx"

  Письма будут приходить на mbahetzan@gmail.com
"""

import os
import smtplib
import logging
import datetime
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

logger = logging.getLogger(__name__)

RECIPIENT_EMAIL = "mbahetzan@gmail.com"
SENDER_EMAIL    = "mbahetzan@gmail.com"  # отправляем сами себе


def _get_app_password() -> str:
    """Читает пароль приложения из Streamlit secrets или env."""
    try:
        import streamlit as st
        pw = st.secrets.get("EMAIL_APP_PASSWORD", "")
        if pw:
            return pw
    except Exception:
        pass
    return os.environ.get("EMAIL_APP_PASSWORD", "")


def is_email_configured() -> bool:
    return bool(_get_app_password())


def send_feedback(
    text: str,
    rating: int,
    idea_name: str = "",
    idea_score: int | None = None,
) -> bool:
    """
    Отправляет отзыв на email через Gmail SMTP.
    Возвращает True при успехе, False при ошибке.
    """
    password = _get_app_password()
    if not password:
        logger.warning("EMAIL_APP_PASSWORD не настроен")
        return False

    stars = "⭐" * rating + "☆" * (5 - rating)
    now   = datetime.datetime.now().strftime("%d.%m.%Y %H:%M")

    subject = f"[AI Startup Validator] Новый отзыв {stars} — {now}"

    # HTML-тело письма
    idea_line  = f"<tr><td style='color:#666;padding:6px 0'>💡 Идея</td><td><b>{idea_name}</b></td></tr>" if idea_name else ""
    score_line = f"<tr><td style='color:#666;padding:6px 0'>🏆 Score</td><td><b>{idea_score}/100</b></td></tr>" if idea_score is not None else ""

    html = f"""
<html><body style="font-family:Arial,sans-serif;max-width:600px;margin:0 auto;padding:20px">
  <div style="background:#f8f9fa;border-radius:12px;padding:24px;border:1px solid #e0e0e0">
    <h2 style="margin:0 0 16px;color:#1a1a1a">📬 Новый отзыв — AI Startup Validator</h2>
    <table style="width:100%;border-collapse:collapse;margin-bottom:16px">
      <tr><td style="color:#666;padding:6px 0">🕐 Время</td><td>{now}</td></tr>
      <tr><td style="color:#666;padding:6px 0">⭐ Оценка</td><td><b>{stars} ({rating}/5)</b></td></tr>
      {idea_line}
      {score_line}
    </table>
    <div style="background:#fff;border-radius:8px;padding:16px;border:1px solid #e0e0e0">
      <p style="margin:0 0 8px;color:#666;font-size:13px">💬 Отзыв:</p>
      <p style="margin:0;font-size:15px;line-height:1.6;color:#1a1a1a">{text.strip()}</p>
    </div>
  </div>
</body></html>
"""

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"]    = SENDER_EMAIL
    msg["To"]      = RECIPIENT_EMAIL
    msg.attach(MIMEText(html, "html", "utf-8"))

    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=15) as server:
            server.login(SENDER_EMAIL, password)
            server.sendmail(SENDER_EMAIL, RECIPIENT_EMAIL, msg.as_string())
        logger.info(f"Отзыв отправлен на {RECIPIENT_EMAIL}")
        return True
    except smtplib.SMTPAuthenticationError:
        logger.error("Ошибка аутентификации Gmail — проверьте EMAIL_APP_PASSWORD")
        return False
    except Exception as e:
        logger.error(f"Ошибка отправки email: {e}")
        return False
