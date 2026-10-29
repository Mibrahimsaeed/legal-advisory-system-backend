"""
Sends emails (currently: password reset codes).

Real sending uses SMTP settings from .env, e.g. a Gmail account with an
App Password:

    SMTP_HOST=smtp.gmail.com
    SMTP_PORT=587
    SMTP_USER=yourproject@gmail.com
    SMTP_PASSWORD=your-16-char-app-password
    EMAIL_FROM=Smart Legal Advisory <yourproject@gmail.com>

If SMTP isn't configured (the default in development), the email is printed
to the backend terminal instead, so the reset flow can be tested without
any email account.
"""

import asyncio
import smtplib
from email.message import EmailMessage

from config.logging import get_logger
from config.settings import get_settings

logger = get_logger("email")


def _send_sync(to: str, subject: str, body: str) -> None:
    settings = get_settings()
    msg = EmailMessage()
    msg["From"] = settings.email_from or settings.smtp_user
    msg["To"] = to
    msg["Subject"] = subject
    msg.set_content(body)

    with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=20) as server:
        server.starttls()
        server.login(settings.smtp_user, settings.smtp_password)
        server.send_message(msg)


async def send_email(to: str, subject: str, body: str) -> None:
    settings = get_settings()
    if not (settings.smtp_host and settings.smtp_user and settings.smtp_password):
        # Development fallback: show the email in the terminal.
        print(
            "\n" + "=" * 60
            + f"\nEMAIL (not sent, SMTP not configured)\nTo: {to}\nSubject: {subject}\n\n{body}\n"
            + "=" * 60 + "\n",
            flush=True,
        )
        return
    # smtplib is blocking, so run it off the event loop.
    await asyncio.to_thread(_send_sync, to, subject, body)
    logger.info("email_sent", to=to, subject=subject)
