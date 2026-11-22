# 채용 레이더

기업 공식 채용 홈페이지를 주기적으로 확인해 **대기업의 AI·데이터 직무 공고**와 **카드사 공고**를 한 화면에 모으고,
새 공고를 텔레그램으로 알리는 개인용 도구.

- 웹 페이지: 분야 전환(전체 / AI·데이터 / 카드사), 회사 로고와 회사 모아보기, 이번 주 마감 달력, 새 공고·마감 임박 빠른 필터, 신입경력·지역 필터
- 알림: 관심 분야의 새 공고만 텔레그램으로 전송
- 수집 대상과 조사 기록: [research/sources.md](research/sources.md)

## 로컬 실행

```powershell
python -m venv .venv
.venv\Scripts\python -m pip install -e . pytest
.venv\Scripts\python -m playwright install chromium
copy .env.example .env   # 토큰 입력
.venv\Scripts\python -m radar run               # 수집 → 분류 → 알림 → 사이트 생성
.venv\Scripts\python -m radar run --no-notify   # 알림 없이 수집과 사이트 생성만
.venv\Scripts\python -m radar run --sources sk,lg   # 일부 소스만
.venv\Scripts\python -m radar sources           # 등록된 소스와 최근 수집 결과
.venv\Scripts\python -m radar logos             # 회사 로고 받기(브랜드를 추가했을 때만)
.venv\Scripts\python -m radar notify-test       # 텔레그램 연결 확인
.venv\Scripts\python -m pytest
```

생성물: `data/radar.sqlite`(상태), `docs/index.html`(웹 페이지), `docs/postings.json`(같은 데이터).

## 동작 방식

1. **수집** (`radar/sources/`): 소스마다 현재 게시된 공고 목록을 읽는다. 대부분 httpx 로 받고,
   페이지를 열어야만 목록이 나오는 사이트만 Playwright 를 쓴다. 같은 호스트에는 1.5초 간격으로 요청한다.
2. **분류** (`radar/categories.py`): 공고가 관심 분야인지 가린다.
   - `card`: 회사명에 '카드'가 들어가는 회사(카드사)의 공고는 직무와 상관없이 전부.
   - `ai`: 제목이나 직무명에 AI·데이터 키워드가 있는 공고. 여러 직무를 한 공고로 묶는 사이트(삼성·LG)는 상세의 직무명까지 본다.
   - 어느 쪽도 아니면 저장하지 않는다. 처음 봤을 때 이미 마감된 공고도 저장하지 않는다.
3. **근무지 추출** (`radar/location.py`): 새로 저장하는 공고만 상세를 한 번 읽어 근무지 문장에서 시·도, 시·군·구를 뽑는다.
4. **알림** (`radar/notify.py`): 아직 알리지 않은 관심 공고를 텔레그램으로 보낸다. 새로 추가한 소스의 첫 수집분은
   알리지 않는다(이미 올라와 있던 공고가 한꺼번에 쏟아지지 않게). 알림이 실패해도 사이트는 다시 만든다.
5. **사이트 생성** (`radar/site.py`): 관심 공고만 담은 정적 HTML 한 장. 마감 여부는 페이지를 여는 시점에 브라우저가 다시 계산한다.

대기업 범위는 `radar/companies.py` 에 있다. 그룹 통합 채용 사이트(삼성·LG·SK 등)에서는 주력 계열사만 남긴다.

## 마감 공고

마감일이 지났거나 하루 넘게 목록에서 사라지면 "접수마감"으로 표시한다. 마감 후 7일이 지나면 사이트에서 숨기고,
90일이 지나면 DB에서 지운다 (`RADAR_HIDE_CLOSED_DAYS`, `RADAR_PURGE_DAYS`).

## GitHub 배포

1. 저장소 Settings → Secrets and variables → Actions 에 `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID` 등록.
   (선택) `ANTHROPIC_API_KEY`.
2. Settings → Pages → Source: Deploy from a branch, Branch: `main` / `/docs`.
3. `.github/workflows/radar.yml` 이 30분마다 수집하고 `data/`, `docs/` 변경을 커밋한다.
   `radar/` 아래 코드를 푸시하면 바로 한 번 더 돈다.

### 잘 돌고 있는지 확인하기

웹 페이지 맨 아래 **수집 대상** 을 펼치면 사이트별 게시 공고 수와 최근 수집 성공 시각이 나온다.
수집에 실패한 사이트는 "수집 실패"로 표시된다. 텔레그램 토큰이나 채팅 ID가 틀리면 같은 자리에 경고와 사유가 뜬다.
알림이나 일부 소스가 실패하면 Actions 실행은 실패로 표시되지만 사이트는 계속 갱신된다.

## 기업 추가

1. robots.txt, 이용약관, 공고 제공 방식을 조사해 `research/sources.md` 에 기록한다. 목록 경로가 robots.txt 로
   금지돼 있으면 추가하지 않는다. 데이터가 다른 호스트(API)에서 오면 그 호스트의 robots.txt 도 확인한다.
2. `radar/sources/` 에 수집기를 만들거나 기존 것을 재사용하고, `radar/sources/__init__.py` 의 `SOURCES` 에 등록한다.
   recruiter.co.kr 솔루션을 쓰는 기업은 `RecruiterCoKrSource(key=..., company=..., subdomain=...)` 한 줄이면 된다.
3. 그룹 통합 사이트면 `radar/companies.py` 에 수집할 계열사 목록을 추가한다.
4. `radar/brands.py` 에 회사명 규칙과 로고 주소를 추가하고 `python -m radar logos` 를 실행한다.
   로고가 없으면 회사 색 바탕의 글자 타일로 표시된다.

저장하는 것은 공고 제목·기간·전형 구분·원문 링크·직무명·근무지 문장뿐이다. 본문은 저장하지 않는다.

## 근무지 추출

`data/regions.json` 의 시·군·구 사전과 별칭(사업장·역 이름)으로 먼저 추출하고,
실패하면 `ANTHROPIC_API_KEY` 가 있을 때만 Claude 로 추출한 뒤 사전으로 검증한다.
모델은 `RADAR_LLM_MODEL` 로 바꿀 수 있다.
