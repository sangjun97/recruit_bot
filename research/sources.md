# 수집 대상 조사 기록

기업을 추가하기 전에 robots.txt, 이용약관, 공고 제공 방식을 조사한 결과를 여기에 남긴다.
마지막 전체 조사: 2026-11-22 (한국 가정용 IP에서 확인. 해외 IP 동작은 따로 적은 곳 외에는 미확인).

## 판단 기준

1. **robots.txt**: 공고 목록 경로가 `User-agent: *` 에 대해 금지돼 있으면 추가하지 않는다.
   데이터가 다른 호스트(API)에서 오면 그 호스트의 robots.txt 도 본다. 금지된 호스트는 직접 호출하지 않는다.
2. **이용약관**: 자동 수집을 금지하는 조항이 있으면 추가하지 않는다. 약관이 있는데 읽지 못했으면 보류한다.
3. **저장 범위**: 제목, 접수 기간, 신입·경력 구분, 원문 링크, 직무명, 근무지 문장만 저장한다.
   본문, 연락처, 지원자 수, 담당자 정보는 응답에 섞여 와도 읽지 않는다. 로그인하지 않는다.
4. **요청 빈도**: 같은 호스트에 1.5초 간격. 응답이 큰 사이트는 수집 간격을 따로 둔다(HD현대 3시간).

### 약관 유형

삼성커리어스를 추가할 때(2026-10-28) 사용자가 검토하고 수락한 조항과 같은 유형이면 같은 조건(메타데이터만, 비영리, 로그인 없음)으로 추가했다.
아래 표의 "약관" 칸에 유형을 적었다.

| 유형 | 뜻 | 처리 |
|---|---|---|
| 없음 | 이용약관 페이지가 없거나 수집·재이용 조항이 없다 | 추가 |
| 허용 | 개인적 이용·저장·링크를 명시적으로 허용한다 | 추가 |
| A | 회원 대상 약관. "서비스에서 얻은 정보를 승낙 없이 상업적으로 이용하거나 제3자에게 노출·제공 금지" | 추가 (삼성과 같은 유형) |
| B | A 와 같은 문구가 회원이 아닌 "이용자" 전체에 적용된다. 영리 목적 이용과 제3자 이용에 한정 | 수집기만 만들고 **승인 대기** |
| C | "이용자" 전체에게 복제·사용 자체를 금지하거나 개인적 용도 외 사용을 금지한다 | **보류** |

## 수집 중 (17곳)

카드사는 전체 공고, 그 밖의 회사는 AI·데이터 직무 공고만 남긴다(`radar/categories.py`).
그룹 통합 사이트에서 남기는 계열사는 `radar/companies.py` 에 있다.

| 소스 키 | 회사 | 사이트 | robots.txt | 약관 | 제공 방식 | 수집기 |
|---|---|---|---|---|---|---|
| hyundaicard | 현대카드·현대커머셜 | careerhyundai.recruiter.co.kr | 페이지 허용. **API 호스트는 전체 금지** (아래 "확인 필요 1") | 없음 | jobflex. 허용된 페이지를 브라우저로 열어 읽음 | `recruiter_co_kr.py` |
| kbcard | KB국민카드 | kbcard.careerlink.kr | /jobs 허용. API 호스트(api.inhr.co.kr)는 robots.txt 없음(404) | 없음 (개인정보처리방침만 있음) | careerlink. 대기열 입장표 → 목록 JSON | `careerlink.py` |
| wooricard | 우리카드 (수시) | wooricard.career.greetinghr.com | 허용. 지원·로그인 경로만 금지. `ai-train=no` | 없음 | Greeting. 페이지 HTML 안 JSON | `greeting.py` |
| wooricard_open | 우리카드 (공채) | wooricard.careerlink.kr | /jobs 허용 | 없음 | careerlink | `careerlink.py` |
| samsung | 삼성 계열사 + 삼성카드 | samsungcareers.com | 없음(302) | A | 목록 HTML 조각 + 상세 JSON, 같은 호스트 | `samsung_careers.py` |
| lg | LG 계열사 | careers.lg.com | 없음(앱 페이지). API 호스트도 없음 | 없음 (지원자 개인정보 동의문만) | JSON API | `lg_careers.py` |
| sk | SK 계열사 | skcareers.com | `Allow: /Recruit`. `/*?searchText=` 만 금지 | A | 목록 JSON + 상세 HTML, 같은 호스트 | `sk_careers.py` |
| autoever | 현대오토에버 | career.hyundai-autoever.com | 허용. `ai-train=no`, AI 학습 수집기는 이름으로 금지 | 없음 | Greeting | `greeting.py` |
| naver | 네이버·주요 자회사 | recruit.navercorp.com | 없음(404) | 없음 | JSON, 같은 호스트 | `naver.py` |
| kakao | 카카오·계열사 | careers.kakao.com | 없음(401 빈 응답. 없는 경로는 모두 401) | A | JSON API, 같은 호스트 | `kakao.py` |
| kt | KT 그룹사 + BC카드 | recruit.kt.com | `Allow: /` | 없음 | JSON API, 같은 호스트 | `kt.py` |
| lotte | 롯데 계열사 | recruit.lotte.co.kr | 없음(307 → 오류 페이지) | 없음 (회원 가입 계약, 관련 조항 없음) | 서버 렌더링 HTML | `lotte.py` |
| cj | CJ 계열사 | recruit.cj.net | `Allow: /` | A | JSON API, 같은 호스트 | `cj.py` |
| shinsegae | 신세계 계열사 | job.shinsegae.com | 없음(404) | A | JSON API, 같은 호스트 | `shinsegae.py` |
| hd | HD현대 계열사 | recruit.hd.com | `Disallow: /hdcareerAdministrator/` + `Allow: /` | 허용 | JSON, 같은 호스트. 전체 이력 1.5MB라 3시간 간격 | `hd_hyundai.py` |
| kbstar | KB국민은행 | kbstar.careerlink.kr | /jobs 허용 | 없음 | careerlink | `careerlink.py` |
| hyundaicapital | 현대캐피탈 | career.hyundaicapital.com | /jobs 허용 | 없음 | careerlink | `careerlink.py` |

삼성카드는 삼성커리어스에, BC카드는 KT그룹 채용에 함께 올라온다. 두 회사는 카드사라 직무와 상관없이 전부 남긴다.

## 승인 대기 (수집기 완성, 실행 목록에서 제외)

수집기를 만들어 실제 수집까지 확인했다. `radar/sources/__init__.py` 의 `PENDING_SOURCES` 에 있고 기본 실행에는 들어가지 않는다.
승인하면 해당 항목을 `SOURCES` 로 옮기면 된다. 2026-11-22 시험 수집 결과: 현대자동차 99건 중 AI·데이터 8건, 기아 8건 중 0건, 한화 94건 중 8건.

| 소스 키 | 회사 | 사이트 | robots.txt | 약관 | 제공 방식 | 수집기 |
|---|---|---|---|---|---|---|
| hyundai | 현대자동차 | talent.hyundai.com | `Allow: /` | **B** | JSON API, 같은 호스트 | `hmg.py` |
| kia | 기아 | career.kia.com | `Allow: /` (무관한 26개 페이지만 금지) | **B** | 현대자동차와 같은 시스템 | `hmg.py` |
| hanwha | 한화 계열사 | hanwhain.com | 페이지 호스트 없음. **API 호스트는 403 차단 페이지** (아래 "확인 필요 2") | **B** | JSON API, 다른 호스트(hwadm.hanwhain.com) | `hanwha.py` |

### 약관 조항 원문

- **삼성커리어스** (A, 2026-10-28 사용자 수락): 제12조·제15조 "서비스에서 취득한 정보를 회사 사전 승낙 없이 복제·제3자 제공·영리 이용 금지".
- **SK Careers** (A, 2021-01-13 시행): 제13조(5) "약관의 적용은 회원에 한하며". 제10조(3)2 "서비스 이용 중 습득한 정보를 상업적 목적으로 이용하거나 올린 이 또는 본사의 허가 없이 출판, 방송 등 제3자에게 노출시키는 행위".
- **CJ** (A): 제12조(5) "약관의 적용은 회원에 한하며". 제10조(3)2 는 SK 와 같은 문구.
- **카카오** (A): 제10조(3)2 "서비스 이용 중 습득한 정보를 상업적 목적으로 이용하거나 올린 이 또는 회사의 허가 없이 출판, 방송 등 제3자에게 노출시키는 행위".
- **신세계** (A): 제2조 회원 = "채용 홈페이지에 접속하여 이용약관에 동의한 자". 제11조 9호 "서비스를 이용하여 얻은 정보를 회사의 사전 승낙없이 복제 또는 유통시키거나 상업적으로 이용하거나 배포하는 행위".
- **현대자동차·기아** (B, 2022-06-23 / 2025-06-24 시행): 제13조 3 (회원) "서비스를 이용하여 얻은 정보를 회사의 사전승낙 없이 복사, 복제, 변경, 번역, 출판/방송 기타의 방법으로 사용하거나 이를 타인에게 제공할 수 없습니다."
  제17조 2 (이용자) "이용자는 서비스를 이용함으로써 얻은 정보를 회사의 사전승낙 없이 복제, 송신, 출판, 배포, 방송, 기타 방법에 의하여 영리목적으로 이용하거나 제 3자에게 이용하게 하여서는 안됩니다."
- **한화** (B): 제13조(회원)와 제16조(이용자)가 현대자동차의 두 조항과 같은 문구.
- **HD현대** (허용, 법적고지): "사이트 내의 정보를 개인적인 용도로 사용하시거나 고객님의 컴퓨터에 저장하실 수 있습니다. 고객님의 개인적인 홈페이지나 문서로부터 본 서버로의 링크 등은 가능합니다."
- **롯데**: 수집·재이용 조항 없음. "이메일 무단수집거부" 고지가 있어 본문의 연락처는 읽지 않는다.

## 사용자 확인이 필요한 것

### 확인 필요 1. recruiter.co.kr(jobflex): 페이지는 허용, 데이터 호스트는 금지

- `careerhyundai.recruiter.co.kr/robots.txt`: `Allow: /`, 첨부파일·게시판만 금지. 공고 페이지는 허용.
- `api-recruiter.recruiter.co.kr/robots.txt`: `User-agent: * / Disallow: /`. 공고 데이터는 이 호스트에서 온다.
- 지금 방식(2026-10-28부터): API 를 직접 부르지 않고, 허용된 공고 목록 페이지를 브라우저로 연다. 페이지가 화면을 그리려고 스스로 받은 응답을 읽는다.
- 엄격하게 보면 회색지대다. 검색엔진의 렌더러는 robots.txt 로 금지된 하위 요청을 보내지 않는다.
- 2026-11-22 에 알게 된 사실이라 현대카드는 그대로 두었고, **같은 구조인 새 사이트는 추가하지 않았다**(아래 보류 표의 신한카드·신한은행·현대글로비스).
- 결정할 것: (가) 지금 방식을 인정하고 같은 구조의 사이트도 추가, (나) 현대카드만 유지, (다) 현대카드도 제외.

### 확인 필요 2. 한화: API 호스트의 robots.txt 가 403

- `www.hanwhain.com/robots.txt`: 앱 페이지가 돌아온다(robots.txt 없음). 페이지 안 주석에 검색 색인을 허용한다고 적혀 있다.
- `hwadm.hanwhain.com/robots.txt`: 403 차단 안내 페이지("접속 가능한 네트워크 환경이 아닙니다"). robots 규칙은 아니다.
- 공고 API(`/new-backend/portal/api/rcRecruit/*`)는 같은 호스트에서 로그인 없이 200 으로 답한다. 사이트를 여는 브라우저가 직접 부르는 경로다.
- 금지 규칙은 없다. robots.txt 표준(RFC 9309)도 4xx 를 "규칙 없음"으로 본다. 다만 차단 페이지를 "들어오지 말라"로 읽을 수도 있다.
- 약관 유형 B 이기도 해서 승인 대기로 두었다.

### 확인 필요 3. 약관 유형 B (현대자동차, 기아, 한화)

회원이 아닌 방문자에게도 "영리 목적 이용, 제3자에게 이용하게 하는 것"을 금지한다. 삼성 때 수락한 조항과 문구는 거의 같지만 적용 대상이 넓다.
이 프로젝트는 비영리이고 제목·링크만 보여주지만, 웹 페이지를 주변에 공유하므로 "제3자 이용"과 완전히 무관하지는 않다.
그래서 세 곳은 실행 목록에서 빼 두었다. 승인하면 `PENDING_SOURCES` 에서 `SOURCES` 로 옮긴다.

## 보류 (사용자 결정 전까지 추가하지 않음)

| 회사 | 사이트 | 보류 이유 | 추가하면 얻는 것 |
|---|---|---|---|
| 신한카드 | shinhancard.com `/mob/MOBFMCOMN/MOBFMCOM01.shc`, `03.shc` | 목록 페이지는 robots.txt 에 명시적으로 허용돼 있으나, 페이지가 부르는 `.ajax` 는 `Disallow: /mob/` 에 걸린다. "확인 필요 1"과 같은 구조. 약관(온라인 회원 약관 제11조·제17조)은 유형 A | 현재 공채 공지 1건(접수 종료), 경력채용 0건. 경력 공고는 원티드 등 포털에만 올라온다 |
| 신한은행 | shinhan.recruiter.co.kr, shinhandigital.recruiter.co.kr | jobflex. "확인 필요 1"과 같은 구조. 목록 경로는 `/career/jobs` | 디지털/ICT 채용(현재 접수 중 0건) |
| 현대글로비스 | glovis.recruiter.co.kr | jobflex. "확인 필요 1"과 같은 구조. 목록 경로는 `/career/apply` | 현재 접수 중 2건(계약직 물류), AI 직무 0건 |
| NH농협카드(NH농협은행) | with.nonghyup.com | 약관 유형 C: 제12조 "이용자는 개인적인 용도가 아닌 어떠한 경우에도 이 사이트 서비스를 사용할 수 없습니다", 제10조 "얻은 정보를 … 제3자에게 제공하는 행위" 금지. robots.txt 는 없음 | NH카드분사 공고(현재 0건). 대부분 계약직·파트타임 |
| 현대모비스 | careers.mobis.com | 약관 유형 C: 제10조 3 "이용자는 서비스를 이용하여 얻은 정보를 회사의 사전승낙 없이 복사, 복제, 변경, 번역, 출판/방송 기타의 방법으로 사용하거나 이를 타인에게 양도할 수 없습니다". robots.txt 는 허용 | 현재 2건, AI 직무 0건. 직무 분류에 'IT/데이터사이언스', '알고리즘(AI/제어)'가 있어 공채 철에는 많을 수 있다 |
| 쿠팡 | coupang.jobs | 자체 사이트가 봇 확인(Cloudflare)으로 막혀 약관을 읽지 못했다. 공고는 Greenhouse 공개 API(boards-api.greenhouse.io, robots 허용)로 받을 수 있다 | 한국 공고 360건 중 AI·데이터 약 27건 |
| 크래프톤 | krafton.com/careers | 자체 사이트가 robots.txt 까지 403. 공고는 Greenhouse 공개 API 로 받을 수 있다 | 65건 중 AI·데이터 약 24건 |
| 넥슨 | careers.nexon.com | `/recruit?` (필터·페이지 지정)가 금지. API 호스트는 브라우저가 아니면 차단. 브라우저 수집만 가능하고 해외 IP 차단 가능성이 높다 | 121건(테크·분석 직군 건수 미확인) |
| 두산 | career.doosan.com | 약관과 상세 링크를 확인하지 못했다. Cloudflare 뒤 | 34건 |
| KB금융그룹 | careers.kbfg.com | 사이트와 robots.txt 가 503 | - |

## 제외

| 회사 | 사이트 | 이유 |
|---|---|---|
| 하나카드 | hanacard.incruit.com | robots.txt 가 공고 목록 경로(`/Hire/`)를 금지. `hanacard.recruiter.co.kr` 도 `Disallow: /`. 하나금융그룹 사이트에는 통합 목록이 없다 |
| 롯데카드 | lottecard.co.kr | 공고가 이미지 한 장으로만 올라온다(목록·상세·근무지 없음). robots.txt 를 받을 수 없고 방화벽이 요청을 끊는다. 경력 공고는 포털에만 있다 |
| 신한카드 (다른 경로) | shcard.incruit.com, shinhancard.recruiter.co.kr | robots.txt 가 목록 경로 또는 전체를 금지 |
| KB국민카드 (다른 경로) | kbcard.incruit.com, kbcard.saramin.co.kr | robots.txt 가 목록 경로 또는 전체를 금지 |
| BC카드·우리카드 (다른 경로) | bccard.recruiter.co.kr, wooricard.recruiter.co.kr | `Disallow: /` |
| SK하이닉스 | talent.skhynix.com | `Disallow: /`. SK Careers 에 회사명으로 올라오는 공고로 대신한다 |
| SK이노베이션 계열 | recruit.skinnovation.com | `Disallow: /`. SK Careers 로 대신한다 |
| SK텔레콤 | careers.sktelecom.com | 목록이 없고 SK Careers 로 연결된다 |
| 현대캐피탈 (다른 경로) | hcs.recruiter.co.kr | `Disallow: /`. 공식 사이트 career.hyundaicapital.com 을 쓴다 |
| 포스코 | recruit.posco.com | 전체 금지(Yeti 만 허용) |
| 세메스 | semes.recruiter.co.kr | `Disallow: /` |
| GS | gs.co.kr | 그룹 통합 공고 목록이 없다 |

## 사이트별 메모

수집기 파일 머리말에 요청 형식과 주의점을 적어 두었다. 여기에는 여러 사이트에 걸친 것만 적는다.

- **여러 직무를 묶은 공고**: 삼성('경력사원 채용(AI, IT, …)'), LG, HD현대, KT 는 공고 하나에 직무가 여럿이다.
  직무명을 `job_text` 로 저장해 AI·데이터 직무가 하나라도 있으면 남긴다. 화면에는 해당 직무명만 보여준다.
- **마감 시각**: 삼성·SK·롯데는 목록에 날짜만 있다. 삼성과 SK 는 상세에서 실제 마감 시각(17:00 등)을 받는다.
  롯데는 본문에만 시각이 있어 23:59 로 둔다.
- **마감된 공고가 목록에 남는 사이트**: jobflex, CJ, careerlink, KT(`isInProgress`). 접수 상태 필드로 가린다.
  HD현대는 상태 필드가 전부 true 라 접수 기간으로 가린다.
- **직무 분류를 요청으로만 알 수 있는 사이트**: 롯데(`jobcd=0101,0102`), 네이버(`subJobCdArr`). 전체 목록과 AI 직무 목록을 한 번씩 받는다.
- **언어**: SK Careers 는 `Accept-Language: ko-KR` 이 없으면 영어로 답한다.
- **차단 가능성(해외 IP 미확인)**: 롯데(Imperva), 기아·현대오토에버·우리카드(Cloudflare), 현대자동차(F5), 한화(API 호스트의 네트워크 제한).
  GitHub Actions 첫 실행 결과는 웹 페이지 아래 "수집 대상"과 `python -m radar sources` 로 확인한다.

## 재사용할 수 있는 수집기

| 솔루션 | 수집기 | 추가 방법 | 주의 |
|---|---|---|---|
| careerlink (inHR) | `careerlink.py` | 사이트 주소와 기업번호(`__NEXT_DATA__` 의 `coInf.coNo`) | 등록되지 않은 하위 도메인은 `Disallow: /` 로 답한다. 도메인마다 robots.txt 확인 |
| Greeting | `greeting.py` | 사이트 주소와 목록 경로 | robots.txt 가 기업마다 다르다(`lottecard.career.greetinghr.com` 은 전체 금지) |
| 현대차그룹 시스템 | `hmg.py` | 사이트 주소와 회사 코드 | `X-HKMC-*` 헤더가 없으면 400 |
| jobflex (recruiter.co.kr) | `recruiter_co_kr.py` | 하위 도메인과 목록 경로 | "확인 필요 1" 참고. 카드사 하위 도메인 대부분은 `Disallow: /` |
| Greenhouse | (없음) | `boards-api.greenhouse.io/v1/boards/<이름>/jobs` | 쿠팡·크래프톤 보류 참고 |
