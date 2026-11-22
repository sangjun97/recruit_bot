"""시크릿 값 정리와 텔레그램 호출 오류 처리. 2026-11-22: GitHub Secrets 에 줄바꿈이 섞인 토큰 때문에 실행이 중단됐다."""
import httpx
import pytest

from radar import notify
from radar.config import load_settings


@pytest.mark.parametrize("raw", ["123:ABC\n", " 123:ABC ", "123:ABC\r\n", '"123:ABC"', "'123:ABC'\n"])
def test_secrets_are_stripped(monkeypatch, raw):
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", raw)
    monkeypatch.setenv("TELEGRAM_CHAT_ID", " 42\n")
    s = load_settings()
    assert s.telegram_token == "123:ABC" and s.telegram_chat_id == "42"


def test_blank_secret_counts_as_missing(monkeypatch):
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", " \n")
    assert load_settings().telegram_token is None


def test_unbuildable_request_is_reported_not_raised(monkeypatch):
    def boom(*args, **kwargs):
        raise httpx.InvalidURL("Invalid non-printable ASCII character in URL")

    monkeypatch.setattr(notify.httpx, "post", boom)
    problem = notify.check_telegram("123:ABC\n", "42")
    assert problem and "InvalidURL" in problem and "123:ABC" not in problem
    with pytest.raises(notify.TelegramError):
        notify.send_telegram("123:ABC\n", "42", "hi")


def test_network_error_is_reported_without_the_token(monkeypatch):
    def down(*args, **kwargs):
        raise httpx.ConnectTimeout("timed out")

    monkeypatch.setattr(notify.httpx, "post", down)
    assert notify.check_telegram("123:SECRET", "42") == "텔레그램 연결 실패: ConnectTimeout"
