"""Send the finished note by email (any SMTP account) and/or Telegram. Free, settings from env vars.

Email:    SMTP_HOST, SMTP_PORT (465 = SSL, otherwise STARTTLS), SMTP_USER, SMTP_PASSWORD, EMAIL_TO
          (comma separated). Use an app password, never your normal password.
Telegram: TELEGRAM_BOT_TOKEN (from @BotFather), TELEGRAM_CHAT_ID (comma separated).
Never raises: returns a list of what was sent.
"""
import os
import smtplib
import ssl
import sys
from email.message import EmailMessage
from pathlib import Path

import requests


def _warn(msg):
    print(f"[warn] {msg}", file=sys.stderr)


def send_email(subject, text, attachment):
    host, user, pwd, to = (os.environ.get(k, "") for k in ("SMTP_HOST", "SMTP_USER", "SMTP_PASSWORD", "EMAIL_TO"))
    if not (host and user and pwd and to):
        return False
    port = int(os.environ.get("SMTP_PORT") or 465)
    msg = EmailMessage()
    msg["Subject"], msg["From"], msg["To"] = subject, user, to
    msg.set_content(text)
    p = Path(attachment)
    sub = "pdf" if p.suffix == ".pdf" else "html"
    msg.add_attachment(p.read_bytes(), maintype="application" if sub == "pdf" else "text", subtype=sub, filename=p.name)
    try:
        ctx = ssl.create_default_context()
        if port == 465:
            with smtplib.SMTP_SSL(host, port, context=ctx, timeout=60) as s:
                s.login(user, pwd); s.send_message(msg)
        else:
            with smtplib.SMTP(host, port, timeout=60) as s:
                s.starttls(context=ctx); s.login(user, pwd); s.send_message(msg)
        print("Email sent to", to)
        return True
    except Exception as ex:
        _warn(f"email failed: {ex}")
        return False


def telegram_chat_ids(token):
    """Helper: after you send any message to your bot, this lists the chat ids it can see."""
    r = requests.get(f"https://api.telegram.org/bot{token}/getUpdates", timeout=30).json()
    return sorted({(u.get("message") or u.get("channel_post") or {}).get("chat", {}).get("id") for u in r.get("result", [])} - {None})


def send_telegram(caption, attachment):
    token, chats = os.environ.get("TELEGRAM_BOT_TOKEN", ""), os.environ.get("TELEGRAM_CHAT_ID", "")
    if not token:
        return False
    if not chats:
        try:
            ids = telegram_chat_ids(token)
            _warn(f"TELEGRAM_CHAT_ID not set. Chats seen by your bot: {ids or 'none, send the bot a message first'}")
        except Exception as ex:
            _warn(f"telegram lookup failed: {ex}")
        return False
    ok = True
    for chat in [c.strip() for c in chats.split(",") if c.strip()]:
        try:
            with open(attachment, "rb") as f:
                r = requests.post(f"https://api.telegram.org/bot{token}/sendDocument",
                                  data={"chat_id": chat, "caption": caption[:1000]}, files={"document": f}, timeout=60)
            r.raise_for_status()
            print("Telegram sent to", chat)
        except Exception as ex:
            ok = False
            _warn(f"telegram to {chat} failed: {ex}")
    return ok


def deliver(subject, text, attachment):
    sent = []
    if send_email(subject, text, attachment):
        sent.append("email")
    if send_telegram(subject + "\n\n" + text, attachment):
        sent.append("telegram")
    if not sent:
        print("Nothing sent: no email or Telegram settings found.")
    return sent
