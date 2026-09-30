"""Send the weekly email over SMTP (defaults to Gmail with an app password)."""

import os
import smtplib
from email.message import EmailMessage

from vocab.models import WordList
from vocab.notify.message import email_html, email_subject, email_text


def send_email(word_list: WordList, site_url: str) -> None:
    user = os.environ["SMTP_USER"]
    msg = EmailMessage()
    msg["Subject"] = email_subject(word_list)
    msg["From"] = user
    msg["To"] = os.environ.get("EMAIL_TO", user)
    msg.set_content(email_text(word_list, site_url))
    msg.add_alternative(email_html(word_list, site_url), subtype="html")

    host = os.environ.get("SMTP_HOST", "smtp.gmail.com")
    port = int(os.environ.get("SMTP_PORT", "465"))
    with smtplib.SMTP_SSL(host, port) as smtp:
        smtp.login(user, os.environ["SMTP_APP_PASSWORD"])
        smtp.send_message(msg)
