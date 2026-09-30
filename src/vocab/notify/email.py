"""Send the weekly email over SMTP (defaults to Gmail with an app password)."""

import os
import smtplib
import ssl
from email.message import EmailMessage

from vocab.models import WordList
from vocab.notify.message import email_html, email_subject, email_text

GMAIL_HINT = (
    "Gmail rejected the login. Check that: (1) the EMAIL secret is exactly the Gmail address "
    "that created the app password; (2) APP_PW is the 16-letter app password from "
    "https://myaccount.google.com/apppasswords (not your normal password); (3) 2-Step "
    "Verification is on for that account."
)


def load_credentials() -> tuple[str, str]:
    """Read SMTP credentials, forgiving the whitespace that creeps in when pasting secrets."""
    user = os.environ["SMTP_USER"].strip()
    # Google shows app passwords as "abcd efgh ijkl mnop"; the spaces are only for display.
    password = "".join(os.environ["SMTP_APP_PASSWORD"].split())
    if "@" not in user:
        raise RuntimeError("SMTP_USER (the EMAIL secret) doesn't look like an email address.")
    if not password:
        raise RuntimeError("SMTP_APP_PASSWORD (the APP_PW secret) is empty.")
    return user, password


def _password_diagnosis(host: str, password: str) -> str:
    if "gmail" in host and (len(password) != 16 or not password.isalpha()):
        return (
            f" The app password has {len(password)} characters after removing spaces; "
            "a Gmail app password is 16 letters."
        )
    return ""


def _send(host: str, port: int, user: str, password: str, msg: EmailMessage) -> None:
    context = ssl.create_default_context()
    if port == 465:
        with smtplib.SMTP_SSL(host, port, context=context, timeout=60) as smtp:
            smtp.login(user, password)
            smtp.send_message(msg)
    else:
        with smtplib.SMTP(host, port, timeout=60) as smtp:
            smtp.starttls(context=context)
            smtp.login(user, password)
            smtp.send_message(msg)


def send_email(word_list: WordList, site_url: str, has_writing: bool = False) -> None:
    send_html_email(
        email_subject(word_list),
        email_html(word_list, site_url, has_writing),
        email_text(word_list, site_url),
    )


def send_html_email(subject: str, html: str, text: str) -> None:
    user, password = load_credentials()
    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = user
    msg["To"] = os.environ.get("EMAIL_TO", "").strip() or user
    msg.set_content(text)
    msg.add_alternative(html, subtype="html")

    host = os.environ.get("SMTP_HOST", "smtp.gmail.com")
    port = int(os.environ.get("SMTP_PORT", "465"))
    try:
        try:
            _send(host, port, user, password, msg)
        except smtplib.SMTPServerDisconnected:
            if port != 465:
                raise
            print("SMTP over SSL (465) disconnected; retrying with STARTTLS on 587")
            _send(host, 587, user, password, msg)
    except (smtplib.SMTPAuthenticationError, smtplib.SMTPServerDisconnected) as e:
        hint = GMAIL_HINT if "gmail" in host else "The SMTP server rejected the login."
        raise RuntimeError(f"{hint}{_password_diagnosis(host, password)} ({e})") from e
