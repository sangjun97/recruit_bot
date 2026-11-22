# 수집 대상 조사 기록

기업을 추가하기 전에 robots.txt, 이용약관, 공고 제공 방식을 조사한 결과를 여기에 남긴다.
마지막 전체 조사: 2026-11-22 (한국 가정용 IP에서 확인. 해외 IP 동작은 따로 적은 곳 외에는 미확인).

## 판단 기준

1. **robots.txt**: 공고 목록 페이지가 `User-agent: *` 에 대해 금지돼 있으면 추가하지 않는다.
2. **데이터가 다른 경로에서 오는 사이트**: 공고 페이지는 허용돼 있는데 데이터를 내려주는 호스트나 경로가 robots.txt 로 금지된 경우,
   금지된 경로를 직접 호출하지 않는다. 허용된 공고 페이지를 브라우저로 열어 화면에 나온 것을 읽는다
   (2026-11-22 사용자 결정: "공고 페이지에서 가져올 수 있는 사이트면 그렇게 진행").
3. **공고 페이지 자체가 자동 접근을 막는 회사**: 그 회사가 쓰는 채용 솔루션에 문서화된 공개 API 가 있으면 그것으로 받는다
   (2026-11-22 사용자 결정: "공개 API로 받는 것도 추가"). 막아 둔 페이지를 우회해서 열지는 않는다.
4. **이용약관** (2026-11-22 사용자 결정): 개인적인 이용까지 금지하는 약관이 있는 회사는 제외한다.
   영리 목적 이용이나 제3자 제공만 금지하는 약관은 추가한다. 약관이 있는데 읽지 못한 곳은 보류한다.
5. **저장 범위**: 제목, 접수 기간, 신입·경력 구분, 원문 링크, 직무명, 근무지 문장만 저장한다.
   본문, 연락처, 지원자 수, 담당자 정보는 응답에 섞여 와도 읽지 않는다. 로그인하지 않는다.
6. **요청 빈도**: 같은 호스트에 1.5초 간격. 응답이 크거나 브라우저를 띄워야 하는 사이트는 수집 간격을 따로 둔다
   (HD현대 3시간, 신한은행·현대글로비스·쿠팡 2시간, 신한카드·크래프톤 1시간).

### 약관 유형

| 유형 | 뜻 | 처리 |
|---|---|---|
| 없음 | 이용약관 페이지가 없거나 수집·재이용 조항이 없다 | 추가 |
| 허용 | 개인적 이용·저장·링크를 명시적으로 허용한다 | 추가 |
| A | 회원 대상 약관. "서비스에서 얻은 정보를 승낙 없이 상업적으로 이용하거나 제3자에게 노출·제공 금지" | 추가 (삼성커리어스, 2026-10-28 사용자 수락) |
| B | A 와 같은 문구가 회원이 아닌 "이용자" 전체에 적용된다. 영리 목적 이용과 제3자 이용만 금지 | 추가 (2026-11-22 사용자 결정) |
| C | 개인적인 이용만 허용하고, 그 밖의 목적의 복제와 제3자 제공을 금지한다 | 추가 (2026-11-22 사용자 결정. 개인 이용은 허용되므로) |
| D | 방문자 전체에게 얻은 정보의 복제·사용 자체를 금지한다. 개인적인 이용도 예외가 아니다 | **제외** |

유형 A·B·C 에 남는 위험: 이 프로젝트는 비영리이고 제목과 링크만 보여주지만, 웹 페이지를 주변에 공유하면
"제3자에게 이용하게 하는 것"으로 읽힐 여지가 있다. 혼자 보는 용도라면 문제가 되지 않는다.

## 수집 중 (28곳)

카드사는 전체 공고, 그 밖의 회사는 AI·데이터 직무 공고만 남긴다(`radar/categories.py`).
그룹 통합 사이트에서 남기는 계열사는 `radar/companies.py` 에 있다.

| 소스 키 | 회사 | 사이트 | robots.txt | 약관 | 제공 방식 | 수집기 |
|---|---|---|---|---|---|---|
| hyundaicard | 현대카드·현대커머셜 | careerhyundai.recruiter.co.kr | 페이지 허용. API 호스트는 전체 금지 | 없음 | jobflex. **브라우저로 페이지를 열어 읽음** | `recruiter_co_kr.py` |
| kbcard | KB국민카드 | kbcard.careerlink.kr | /jobs 허용. API 호스트(api.inhr.co.kr)는 robots.txt 없음(404) | 없음 (개인정보처리방침만 있음) | careerlink. 대기열 입장표 → 목록 JSON | `careerlink.py` |
| shinhancard | 신한카드 | shinhancard.com `/mob/MOBFMCOMN/MOBFMCOM01.shc`, `03.shc` | 두 페이지는 명시적으로 허용. 페이지가 부르는 `.ajax` 는 `Disallow: /mob/` | A (온라인 회원 약관 제11조·제17조) | **브라우저로 페이지를 열어 표를 읽음** | `shinhancard.py` |
| wooricard | 우리카드 (수시) | wooricard.career.greetinghr.com | 허용. 지원·로그인 경로만 금지. `ai-train=no` | 없음 | Greeting. 페이지 HTML 안 JSON | `greeting.py` |
| wooricard_open | 우리카드 (공채) | wooricard.careerlink.kr | /jobs 허용 | 없음 | careerlink | `careerlink.py` |
| nhcard | NH농협카드 (NH농협은행 카드 부문) | with.nonghyup.com | 없음(오류 페이지) | C | 서버 렌더링 HTML. 법인=농협은행, 제목 '카드'로 좁혀 읽음 | `nonghyup.py` |
| samsung | 삼성 계열사 + 삼성카드 | samsungcareers.com | 없음(302) | A | 목록 HTML 조각 + 상세 JSON, 같은 호스트 | `samsung_careers.py` |
| lg | LG 계열사 | careers.lg.com | 없음(앱 페이지). API 호스트도 없음 | 없음 (지원자 개인정보 동의문만) | JSON API | `lg_careers.py` |
| sk | SK 계열사 | skcareers.com | `Allow: /Recruit`. `/*?searchText=` 만 금지 | A | 목록 JSON + 상세 HTML, 같은 호스트 | `sk_careers.py` |
| hyundai | 현대자동차 | talent.hyundai.com | `Allow: /` | B | JSON API, 같은 호스트 | `hmg.py` |
| kia | 기아 | career.kia.com | `Allow: /` (무관한 26개 페이지만 금지) | B | 현대자동차와 같은 시스템 | `hmg.py` |
| autoever | 현대오토에버 | career.hyundai-autoever.com | 허용. `ai-train=no`, AI 학습 수집기는 이름으로 금지 | 없음 | Greeting | `greeting.py` |
| hyundaicapital | 현대캐피탈 | career.hyundaicapital.com | /jobs 허용 | 없음 | careerlink | `careerlink.py` |
| glovis | 현대글로비스 | glovis.recruiter.co.kr `/career/apply` | 페이지 허용. API 호스트는 전체 금지 | 없음 (개인정보 처리방침만 있음) | jobflex. **브라우저로 페이지를 열어 읽음** | `recruiter_co_kr.py` |
| naver | 네이버·주요 자회사 | recruit.navercorp.com | 없음(404) | 없음 | JSON, 같은 호스트 | `naver.py` |
| kakao | 카카오·계열사 | careers.kakao.com | 없음(401 빈 응답. 없는 경로는 모두 401) | A | JSON API, 같은 호스트 | `kakao.py` |
| coupang | 쿠팡 | coupang.jobs (자체 사이트는 봇 확인으로 막힘) | API 호스트 boards-api.greenhouse.io 는 `/embed/` 만 금지 | 자체 사이트 약관은 읽지 못함. Greenhouse 는 Job Board API 를 인증 없이 쓰는 공개 API 로 문서화 | Greenhouse 공개 API. 전 세계 공고 중 한국 근무만 남김 | `greenhouse.py` |
| krafton | 크래프톤 | krafton.com/careers (자체 사이트는 403) | 위와 같음 | 위와 같음 | Greenhouse 공개 API | `greenhouse.py` |
| kt | KT 그룹사 + BC카드 | recruit.kt.com | `Allow: /` | 없음 | JSON API, 같은 호스트 | `kt.py` |
| lotte | 롯데 계열사 | recruit.lotte.co.kr | 없음(307 → 오류 페이지) | 없음 (회원 가입 계약, 관련 조항 없음) | 서버 렌더링 HTML | `lotte.py` |
| hanwha | 한화 계열사 | hanwhain.com | 페이지 호스트 없음. API 호스트(hwadm.hanwhain.com)는 robots.txt 요청에 403 차단 페이지(규칙 없음) | B | JSON API, 다른 호스트 | `hanwha.py` |
| cj | CJ 계열사 | recruit.cj.net | `Allow: /` | A | JSON API, 같은 호스트 | `cj.py` |
| shinsegae | 신세계 계열사 | job.shinsegae.com | 없음(404) | A | JSON API, 같은 호스트 | `shinsegae.py` |
| hd | HD현대 계열사 | recruit.hd.com | `Disallow: /hdcareerAdministrator/` + `Allow: /` | 허용 | JSON, 같은 호스트. 전체 이력 1.5MB라 3시간 간격 | `hd_hyundai.py` |
| doosan | 두산 계열사 | career.doosan.com `/dsp/sa/RecList.jsp` | 없음(404) | 없음 (개인정보처리방침·이메일무단수집거부만 있음) | 서버 렌더링 HTML. 공고별 주소가 없어 링크는 목록으로 감 | `doosan.py` |
| kbstar | KB국민은행 | kbstar.careerlink.kr | /jobs 허용 | 없음 | careerlink | `careerlink.py` |
| shinhanbank | 신한은행 | shinhan.recruiter.co.kr `/career/jobs` | 페이지 허용. API 호스트는 전체 금지 | 없음 (개인정보 처리방침·이메일무단수집거부만 있음) | jobflex. **브라우저로 페이지를 열어 읽음** | `recruiter_co_kr.py` |
| shinhanbank_ict | 신한은행 디지털/ICT | shinhandigital.recruiter.co.kr `/career/jobs` | 위와 같음 | 위와 같음 | 위와 같음 | `recruiter_co_kr.py` |

삼성카드는 삼성커리어스에, BC카드는 KT그룹 채용에 함께 올라온다. 두 회사는 카드사라 직무와 상관없이 전부 남긴다.

### 브라우저로 페이지를 열어 읽는 사이트

현대카드, 신한카드, 신한은행(2곳), 현대글로비스. 나머지 23곳은 브라우저 없이 사이트가 내려주는 목록을 바로 받는다.

- recruiter.co.kr(jobflex): `<기업>.recruiter.co.kr/robots.txt` 는 공고 페이지를 허용하고, 데이터가 오는
  `api-recruiter.recruiter.co.kr/robots.txt` 는 `User-agent: * / Disallow: /` 다.
- 신한카드: 채용 페이지는 robots.txt 에 한 줄씩 허용돼 있고, 페이지가 부르는 `.ajax` 는 `Disallow: /mob/` 에 걸린다.
- 그래서 금지된 경로를 수집기가 직접 호출하지 않는다. 사람이 보는 공고 페이지를 브라우저로 열고 화면에 나온 내용을 읽는다.
  사이트에는 사람이 브라우저로 공고 페이지를 볼 때와 같은 요청만 나간다.
- 엄격하게 보면 회색지대다(검색엔진의 렌더러는 금지된 하위 요청을 보내지 않는다). 사용자가 2026-11-22 에 이 방식을 승인했다.

### 약관 조항 원문

- **삼성커리어스** (A): 제12조·제15조 "서비스에서 취득한 정보를 회사 사전 승낙 없이 복제·제3자 제공·영리 이용 금지".
- **SK Careers** (A, 2021-01-13 시행): 제13조(5) "약관의 적용은 회원에 한하며". 제10조(3)2 "서비스 이용 중 습득한 정보를 상업적 목적으로 이용하거나 올린 이 또는 본사의 허가 없이 출판, 방송 등 제3자에게 노출시키는 행위".
- **CJ** (A): 제12조(5) "약관의 적용은 회원에 한하며". 제10조(3)2 는 SK 와 같은 문구.
- **카카오** (A): 제10조(3)2 "서비스 이용 중 습득한 정보를 상업적 목적으로 이용하거나 올린 이 또는 회사의 허가 없이 출판, 방송 등 제3자에게 노출시키는 행위".
- **신세계** (A): 제2조 회원 = "채용 홈페이지에 접속하여 이용약관에 동의한 자". 제11조 9호 "서비스를 이용하여 얻은 정보를 회사의 사전 승낙없이 복제 또는 유통시키거나 상업적으로 이용하거나 배포하는 행위".
- **신한카드** (A, 온라인 회원 약관 2026-04-14 시행): 제11조 ① "신한카드의 서비스 정보를 이용하여 얻은 정보를 신한카드의 승낙 없이 복제 또는 유통하거나 상업적으로 이용하는 행위". 제17조 ⑥ "회원은 서비스를 이용하여 얻은 정보를 가공, 판매하는 행위 등으로 … 영리목적으로 이용하거나 제3자가 이용하게 할 수 없습니다."
- **현대자동차·기아** (B, 2022-06-23 / 2025-06-24 시행): 제13조 3 (회원) "서비스를 이용하여 얻은 정보를 회사의 사전승낙 없이 복사, 복제, 변경, 번역, 출판/방송 기타의 방법으로 사용하거나 이를 타인에게 제공할 수 없습니다."
  제17조 2 (이용자) "이용자는 서비스를 이용함으로써 얻은 정보를 회사의 사전승낙 없이 복제, 송신, 출판, 배포, 방송, 기타 방법에 의하여 영리목적으로 이용하거나 제 3자에게 이용하게 하여서는 안됩니다."
- **한화** (B): 제13조(회원)와 제16조(이용자)가 현대자동차의 두 조항과 같은 문구.
- **범농협 채용시스템** (C): 제10조 "서비스에서 얻은 정보를 회사의 사전승낙 없이 이용자의 이용이외의 목적으로 복제하거나 이를 출판 및 방송 등에 사용하거나 제 3자에게 제공하는 행위" 금지.
  제12조 "이용자는 개인적인 용도가 아닌 어떠한 경우에도 이 사이트 서비스를 사용할 수 없습니다."
- **HD현대** (허용, 법적고지): "사이트 내의 정보를 개인적인 용도로 사용하시거나 고객님의 컴퓨터에 저장하실 수 있습니다. 고객님의 개인적인 홈페이지나 문서로부터 본 서버로의 링크 등은 가능합니다."
- **롯데**: 수집·재이용 조항 없음. "이메일 무단수집거부" 고지가 있어 본문의 연락처는 읽지 않는다.
- **현대모비스** (D, 제외): 제10조 3 "이용자는 서비스를 이용하여 얻은 정보를 회사의 사전승낙 없이 복사, 복제, 변경, 번역, 출판/방송 기타의 방법으로 사용하거나 이를 타인에게 양도할 수 없습니다."

## 보류 (사용자 결정 필요)

| 회사 | 사이트 | 보류 이유 | 추가하면 얻는 것 |
|---|---|---|---|
| 넥슨 | careers.nexon.com | **권장: 추가하지 않음.** 목록 첫 쪽(`/recruit`)만 허용이고 쪽 넘김·필터 주소(`/recruit?…`)는 금지다. 121건 중 15건만 읽을 수 있어 목록에서 빠진 공고를 마감으로 잘못 볼 수 있다. API 호스트는 브라우저가 아니면 차단하고, 해외 IP에서는 브라우저도 막힐 가능성이 높다 | 최신 15건 안의 AI·데이터 공고 |
| KB금융그룹 | careers.kbfg.com | 사이트와 robots.txt 가 503 | - |

## 제외

| 회사 | 사이트 | 이유 |
|---|---|---|
| 현대모비스 | careers.mobis.com | 약관 유형 D. 방문자 전체에게 얻은 정보의 복제·사용 자체를 금지한다(개인 이용 예외 없음). robots.txt 는 허용 |
| 하나카드 | hanacard.incruit.com | robots.txt 가 공고 목록 경로(`/Hire/`)를 금지. `hanacard.recruiter.co.kr` 도 `Disallow: /`. 하나금융그룹 사이트에는 통합 목록이 없다 |
| 롯데카드 | lottecard.co.kr | 공고가 이미지 한 장으로만 올라온다(목록·상세·근무지 없음). robots.txt 를 받을 수 없고 방화벽이 요청을 끊는다. 경력 공고는 포털에만 있다 |
| 신한카드 (다른 경로) | shcard.incruit.com, shinhancard.recruiter.co.kr | robots.txt 가 목록 경로 또는 전체를 금지 |
| KB국민카드 (다른 경로) | kbcard.incruit.com, kbcard.saramin.co.kr | robots.txt 가 목록 경로 또는 전체를 금지 |
| BC카드·우리카드 (다른 경로) | bccard.recruiter.co.kr, wooricard.recruiter.co.kr | `Disallow: /` |
| SK하이닉스 | talent.skhynix.com | `Disallow: /`. SK Careers 에 회사명으로 올라오는 공고로 대신한다 |
| SK이노베이션 계열 | recruit.skinnovation.com | `Disallow: /`. SK Careers 로 대신한다 |
| SK텔레콤 | careers.sktelecom.com | 목록이 없고 SK Careers 로 연결된다 |
| 현대캐피탈 (다른 경로) | hcs.recruiter.co.kr | `Disallow: /`. 공식 사이트 career.hyundaicapital.com 을 쓴다 |
| 신한DS | shinhands.recruiter.co.kr | `/career/` 가 `*` 에 대해 금지 |
| 포스코 | recruit.posco.com | 전체 금지(Yeti 만 허용) |
| 세메스 | semes.recruiter.co.kr | `Disallow: /` |
| GS | gs.co.kr | 그룹 통합 공고 목록이 없다 |

## 사이트별 메모

수집기 파일 머리말에 요청 형식과 주의점을 적어 두었다. 여기에는 여러 사이트에 걸친 것만 적는다.

- **여러 직무를 묶은 공고**: 삼성('경력사원 채용(AI, IT, …)'), LG, HD현대, KT 는 공고 하나에 직무가 여럿이다.
  직무명을 `job_text` 로 저장해 AI·데이터 직무가 하나라도 있으면 남긴다. 화면에는 해당 직무명만 보여준다.
- **마감 시각**: 삼성·SK·롯데·두산·신한카드·NH농협카드는 목록에 날짜만 있다. 삼성과 SK 는 상세에서 실제 마감 시각(17:00 등)을 받는다.
  나머지는 23:59 로 둔다.
- **마감된 공고가 목록에 남는 사이트**: jobflex, CJ, careerlink, KT(`isInProgress`), 범농협, 신한카드. 접수 상태나 기간으로 가린다.
  HD현대는 상태 필드가 전부 true 라 접수 기간으로 가린다.
- **직무 분류를 요청으로만 알 수 있는 사이트**: 롯데(`jobcd=0101,0102`), 네이버(`subJobCdArr`). 전체 목록과 AI 직무 목록을 한 번씩 받는다.
- **공고별 주소가 없는 사이트**: 두산(목록 페이지로 링크), 신한카드 경력채용(목록 페이지로 링크).
- **확인하지 못한 것**: 신한카드 경력채용 표는 조사 때 비어 있어 실제 행 모양을 보지 못했다. 수집기는 제목 칸 표시가 없어도
  날짜·단추가 아닌 가장 긴 칸을 제목으로 읽고, 행이 있는데 하나도 해석하지 못하면 0건으로 넘기지 않고 '수집 실패'로 드러낸다.
- **언어**: SK Careers 는 `Accept-Language: ko-KR` 이 없으면 영어로 답한다.
- **차단 가능성**: 롯데(Imperva), 기아·현대오토에버·우리카드·두산(Cloudflare), 현대자동차(F5), 한화(API 호스트의 네트워크 제한).
  GitHub Actions 실행 결과는 웹 페이지 아래 "수집 대상"과 `python -m radar sources` 로 확인한다.

## 재사용할 수 있는 수집기

| 솔루션 | 수집기 | 추가 방법 | 주의 |
|---|---|---|---|
| careerlink (inHR) | `careerlink.py` | 사이트 주소와 기업번호(`__NEXT_DATA__` 의 `coInf.coNo`) | 등록되지 않은 하위 도메인은 `Disallow: /` 로 답한다. 도메인마다 robots.txt 확인 |
| Greeting | `greeting.py` | 사이트 주소와 목록 경로 | robots.txt 가 기업마다 다르다(`lottecard.career.greetinghr.com` 은 전체 금지) |
| 현대차그룹 시스템 | `hmg.py` | 사이트 주소와 회사 코드 | `X-HKMC-*` 헤더가 없으면 400 |
| jobflex (recruiter.co.kr) | `recruiter_co_kr.py` | 하위 도메인과 목록 경로(`/career/recruit`, `/career/jobs`, `/career/apply` 중 하나) | 브라우저 필요. 카드사 하위 도메인 대부분은 `Disallow: /` |
| Greenhouse | `greenhouse.py` | 게시판 이름(`boards-api.greenhouse.io/v1/boards/<이름>/jobs`) | 전 세계 공고가 섞인 게시판은 근무지로 거른다. 마감일이 거의 없다 |

## 회사 로고

웹 페이지의 로고는 각 회사가 자기 사이트에 공개한 아이콘(파비콘·애플 터치 아이콘)이다. 주소는 `radar/brands.py` 에 있고
`python -m radar logos` 로 한 번 받아 `docs/logos/` 에 둔다. 로고는 각 회사의 상표이며 어느 회사 공고인지 알아보게 하는 용도로만 쓴다.

- 쓸 만한 크기의 아이콘이 없는 회사(우리카드, NH농협카드, 현대글로비스)는 회사 색 바탕의 글자 타일로 표시한다.
- 쿠팡·크래프톤 사이트는 아이콘 요청도 거절한다. 받지 않고 글자 타일로 둔다.
