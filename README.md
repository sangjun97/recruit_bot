# 채용 레이더

기업 공식 채용 홈페이지를 주기적으로 확인해 새 공고를 텔레그램으로 알리고,
근무지(시·군·구)로 필터링할 수 있는 정적 웹 페이지를 만드는 개인용 도구.

## 로컬 실행

```powershell
python -m venv .venv
.venv\Scripts\python -m pip install -e . pytest
.venv\Scripts\python -m playwright install chromium
copy .env.example .env   # 토큰 입력
.venv\Scripts\python -m radar run --bootstrap   # 첫 실행: 기존 공고를 알림 없이 저장
.venv\Scripts\python -m radar run               # 이후: 새 공고만 텔레그램 알림
.venv\Scripts\python -m radar notify-test       # 텔레그램 연결 확인
.venv\Scripts\python -m pytest
```

생성물: `data/radar.sqlite`(상태), `docs/index.html`(웹 페이지).

## GitHub 배포

1. 저장소 Settings → Secrets and variables → Actions 에 `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`
   (선택) `ANTHROPIC_API_KEY` 등록.
2. Settings → Pages → Source: Deploy from a branch, Branch: `main` / `/docs`.
3. `.github/workflows/radar.yml` 이 30분마다 수집하고 `data/`, `docs/` 변경을 커밋한다.

## 기업 추가

`radar/sources/__init__.py` 의 `SOURCES` 에 추가한다. recruiter.co.kr 솔루션을 쓰는 기업은
`RecruiterCoKrSource(key=..., company=..., subdomain=...)` 한 줄로 끝난다.
추가 전에 robots.txt·이용약관·공고 제공 방식을 확인하고 CLAUDE.md 조사 기록에 남긴다.

## 근무지 추출

`data/regions.json` 의 시·군·구 사전과 별칭(사업장·역 이름)으로 먼저 추출하고,
실패하면 `ANTHROPIC_API_KEY` 가 있을 때만 Claude 로 추출한 뒤 사전으로 검증한다.
모델은 `RADAR_LLM_MODEL` 로 바꿀 수 있다.
