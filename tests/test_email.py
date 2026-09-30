import smtplib
from datetime import UTC, datetime

import pytest

from vocab.models import Card, WordList
from vocab.notify import email as email_mod

WL = WordList(id="2026-W40", created=datetime(2026, 9, 28, tzinfo=UTC),
              cards=[Card(id="kenyér", front_en="bread", back_hu="kenyér", word_ids=["kenyér"])])


@pytest.fixture
def env(monkeypatch):
    monkeypatch.setenv("SMTP_USER", " me@gmail.com\n")
    monkeypatch.setenv("SMTP_APP_PASSWORD", "abcd efgh ijkl mnop\n")
    monkeypatch.delenv("EMAIL_TO", raising=False)


def test_credentials_strip_whitespace(env):
    assert email_mod.load_credentials() == ("me@gmail.com", "abcdefghijklmnop")


def test_falls_back_to_starttls_on_disconnect(env, monkeypatch):
    calls = []

    def fake_send(host, port, user, password, msg):
        calls.append(port)
        if port == 465:
            raise smtplib.SMTPServerDisconnected("closed")
        assert msg["To"] == "me@gmail.com"

    monkeypatch.setattr(email_mod, "_send", fake_send)
    email_mod.send_email(WL, "https://x.github.io/hv/")
    assert calls == [465, 587]


def test_auth_failure_gives_hint_without_leaking_password(env, monkeypatch):
    monkeypatch.setenv("SMTP_APP_PASSWORD", "myNormalPassword1")

    def fake_send(*args):
        raise smtplib.SMTPServerDisconnected("closed")

    monkeypatch.setattr(email_mod, "_send", fake_send)
    with pytest.raises(RuntimeError) as exc:
        email_mod.send_email(WL, "https://x.github.io/hv/")
    message = str(exc.value)
    assert "16 letters" in message and "myNormalPassword1" not in message
