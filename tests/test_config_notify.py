"""시크릿 값 정리와 텔레그램 호출 오류 처리.

2026-11-22: GitHub Secrets 에 공백·줄바꿈이 섞인 토큰이 들어가 한 달 가까이 알림이 실패했고, 한 번은 실행이 중단됐다.
"""
import httpx
import pytest

from radar import notify
from radar.config import load_settings, telegram_chat_id, telegram_token

TOKEN = "1234567890:" + "Ab3_-" * 7   # 실제 토큰과 같은 모양(숫자:35자)의 가짜 값


@pytest.mark.parametrize("raw", [
    TOKEN + "\n", f" {TOKEN} ", TOKEN + "\r\n", f'"{TOKEN}"', f"'{TOKEN}'\n",
    f"TELEGRAM_BOT_TOKEN={TOKEN}",                              # 변수 이름까지 붙여넣음
    f"TELEGRAM_BOT_TOKEN={TOKEN}\nTELEGRAM_CHAT_ID=987654321",   # .env 내용을 통째로 붙여넣음
    f"token : {TOKEN}",
    TOKEN[:30] + "\n" + TOKEN[30:],                             # 줄바꿈으로 끊긴 토큰
])
def test_token_is_recovered_from_messy_secret(monkeypatch, raw):
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", raw)
    assert load_settings().telegram_token == TOKEN


@pytest.mark.parametrize("raw, expected", [
    (" 987654321\n", "987654321"),
    ("-1001234567890", "-1001234567890"),
    ("TELEGRAM_CHAT_ID=987654321", "987654321"),
    ("id : 987654321", "987654321"),
    (f"TELEGRAM_BOT_TOKEN={TOKEN}\nTELEGRAM_CHAT_ID=987654321", "987654321"),   # 토큰 안의 숫자를 채팅 ID 로 착각하지 않는다
])
def test_chat_id_is_recovered_from_messy_secret(monkeypatch, raw, expected):
    monkeypatch.setenv("TELEGRAM_CHAT_ID", raw)
    assert load_settings().telegram_chat_id == expected


def test_blank_secret_counts_as_missing(monkeypatch):
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", " \n")
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "")
    s = load_settings()
    assert s.telegram_token is None and s.telegram_chat_id is None
    assert telegram_token(None) is None and telegram_chat_id(None) is None


def test_malformed_token_is_reported_by_shape_only():
    problem = notify.check_telegram("이건 토큰이 아님\n둘째 줄", "987654321")
    assert problem and "형식이 아닙니다" in problem and "2줄" in problem and "토큰이 아님" not in problem
    assert "채팅 ID 형식" in notify.check_telegram(TOKEN, "abc")


def test_unbuildable_request_is_reported_not_raised(monkeypatch):
    def boom(*args, **kwargs):
        raise httpx.InvalidURL("Invalid non-printable ASCII character in URL")

    monkeypatch.setattr(notify.httpx, "post", boom)
    problem = notify.check_telegram(TOKEN, "987654321")
    assert problem and "InvalidURL" in problem and TOKEN not in problem
    with pytest.raises(notify.TelegramError):
        notify.send_telegram(TOKEN, "987654321", "hi")


def test_network_error_is_reported_without_the_token(monkeypatch):
    def down(*args, **kwargs):
        raise httpx.ConnectTimeout("timed out")

    monkeypatch.setattr(notify.httpx, "post", down)
    assert notify.check_telegram(TOKEN, "987654321") == "텔레그램 연결 실패: ConnectTimeout"
