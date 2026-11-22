"""회사 이름 → 브랜드(로고·묶음). 웹 페이지에서 카드의 로고와 '회사 모아보기' 묶음에 쓴다.

- 로고는 각 회사가 자기 사이트에 공개해 둔 아이콘(파비콘·애플 터치 아이콘)이다. `python -m radar logos` 로 한 번 받아
  docs/logos/ 에 두고 페이지는 그 파일을 쓴다(볼 때마다 회사 서버에 요청하지 않게). 로고는 각 회사의 상표이며
  어느 회사 공고인지 알아보게 하는 용도로만 쓴다.
- 쓸 만한 크기의 아이콘이 없는 회사는 icon_url 을 비워 둔다. 그러면 회사 색 바탕에 글자를 넣은 타일이 대신 나온다.
- 회사명은 접두(prefix)로 맞춘다. 위에서부터 처음 맞는 규칙을 쓰므로 더 구체적인 이름을 먼저 둔다
  ('삼성카드' 가 '삼성' 보다 앞, 'LG유플러스' 가 'LG' 보다 앞).
"""
from __future__ import annotations

import re
import zlib
from dataclasses import dataclass


@dataclass(frozen=True)
class Brand:
    key: str                  # 로고 파일 이름(docs/logos/<key>.<확장자>)
    name: str                 # 모아보기 띠에 보이는 이름
    prefixes: tuple[str, ...]  # 회사명이 이 가운데 하나로 시작하면 이 브랜드
    icon_url: str | None = None
    color: str = "#64748b"    # 글자 타일 바탕색(로고가 없거나 못 불러올 때)
    mono: str = ""            # 글자 타일에 넣을 글자. 비우면 이름 앞 두 글자
    group: str = ""           # 모아보기에서 합칠 브랜드 키. 비우면 자기 자신


BRANDS: list[Brand] = [
    # --- 카드사 ---
    Brand("hyundaicard", "현대카드", ("현대카드",), "https://www.hyundaicard.com/apple-touch-icon.png", "#111111", "현대"),
    Brand("samsungcard", "삼성카드", ("삼성카드",), "https://www.samsung.com/sec/static/_images/favicon.ico", "#1428a0", "삼성"),
    Brand("kbcard", "KB국민카드", ("KB국민카드",), "https://www.kbstar.com/openimg/favi_iphone4_n201512.png", "#60584c", "KB"),
    Brand("shinhancard", "신한카드", ("신한카드",), "https://www.shinhancard.com/pconts/static/favicons/icon_196.png", "#0046ff", "신한"),
    Brand("wooricard", "우리카드", ("우리카드",), None, "#0067ac", "우리"),
    Brand("nhcard", "NH농협카드", ("NH농협카드",), None, "#00843d", "NH"),
    Brand("bccard", "BC카드", ("BC카드", "비씨카드"), "https://www.bccard.com/favicon.ico", "#e8384f", "BC"),
    # --- 그룹·대기업 ---
    Brand("samsung", "삼성", ("삼성", "에스원", "호텔신라", "제일기획"), "https://www.samsung.com/sec/static/_images/favicon.ico", "#1428a0"),
    Brand("lguplus", "LG유플러스", ("LG유플러스",), "https://www.lguplus.com/static/pc-static/icon_512_lgu.png", "#e6007e", "U+", group="lg"),
    Brand("lg", "LG", ("LG",), "https://www.lg.com/favicon.ico", "#a50034"),
    Brand("tmap", "티맵모빌리티", ("티맵",), "https://www.tmapmobility.com/favicon.ico", "#3b6cff", "T", group="sk"),
    Brand("sk", "SK", ("SK", "11번가"), "https://www.sk.com/apple-touch-icon.png", "#ea002c"),
    Brand("hyundai", "현대자동차", ("현대자동차",), "https://www.hyundai.com/static/images/common/favicon/apple-touch-icon.png", "#002c5f", "현대"),
    Brand("kia", "기아", ("기아",), "https://www.kia.com/apple-touch-icon.png", "#05141f", "KIA"),
    Brand("autoever", "현대오토에버", ("현대오토에버",), "https://www.hyundai-autoever.com/common/images/favicon.ico", "#002c5f", "오토"),
    Brand("hyundaicapital", "현대캐피탈", ("현대캐피탈",), "https://www.hyundaicapital.com/favicon.ico", "#2a6fdb", "캐피"),
    Brand("glovis", "현대글로비스", ("현대글로비스",), None, "#003a8c", "글로"),
    Brand("hyundaicommercial", "현대커머셜", ("현대커머셜",), None, "#111111", "커머"),
    Brand("naver", "네이버", ("네이버", "스노우"), "https://www.navercorp.com/img/favicon.ico", "#03c75a", "N"),
    Brand("kakaomobility", "카카오모빌리티", ("카카오모빌리티",), "https://www.kakaomobility.com/favicon-32x32.png", "#1c2340", "T", group="kakao"),
    Brand("kakao", "카카오", ("카카오",), "https://www.kakaocorp.com/page/favicon.ico", "#fae100", "k"),
    Brand("kt", "KT", ("KT", "kt ", "케이뱅크", "나스미디어", "지니뮤직"), "https://corp.kt.com/apple-touch-icon.png", "#e4002b"),
    # 쿠팡·크래프톤 사이트는 이 수집기의 요청을 거절한다(아이콘 포함). 로고를 받지 않고 글자 타일로 둔다
    Brand("coupang", "쿠팡", ("쿠팡",), None, "#e52528"),
    Brand("krafton", "크래프톤", ("크래프톤",), None, "#111111", "KR"),
    Brand("lotte", "롯데", ("롯데", "코리아세븐", "호텔롯데"), "https://www.lotte.co.kr/common/favicon/rd_72.png", "#da291c"),
    Brand("hanwha", "한화", ("한화", "(주)한화"), "https://www.hanwha.co.kr/assets/img/favicon/apple-touch-icon.ico", "#f37321"),
    Brand("cj", "CJ", ("CJ", "TVING", "티빙", "스튜디오드래곤"), "https://www.cj.net/assets/favicon-wh.svg", "#00a3e0"),
    Brand("shinsegae", "신세계", ("신세계", "이마트", "SSG", "스타벅스", "조선호텔"), "https://job.shinsegae.com/favicon.svg", "#b12536"),
    Brand("hd", "HD현대", ("HD",), "https://www.hd.com/common/images/bookmark_logo.png", "#00ad1d", "HD"),
    Brand("doosan", "두산", ("두산", "(주)두산"), "https://www.doosan.com/images/common/favicon-152.png", "#005eb8"),
    Brand("kbstar", "KB국민은행", ("KB국민은행", "KB"), "https://www.kbstar.com/openimg/favi_iphone4_n201512.png", "#60584c", "KB"),
    Brand("shinhanbank", "신한은행", ("신한",), "https://www.shinhangroup.com/resources/publish/kr/images/common/favicon_192_192.png", "#0046ff"),
]

# 규칙에 없는 회사의 글자 타일에 돌려 쓰는 색
FALLBACK_COLORS = ["#475569", "#0f766e", "#7c3aed", "#b45309", "#be123c", "#1d4ed8", "#4d7c0f"]
_CORP_MARK_RE = re.compile(r"\(주\)|㈜|주식회사")


def _fold(s: str) -> str:
    return re.sub(r"\s+", " ", s).strip().casefold()


def brand_for(company: str | None) -> Brand:
    """회사명에 맞는 브랜드. 규칙에 없으면 회사명 앞 두 글자로 만든 임시 브랜드를 돌려준다."""
    raw = (company or "").strip()
    names = {_fold(raw), _fold(_CORP_MARK_RE.sub(" ", raw))}
    for b in BRANDS:
        if any(n.startswith(_fold(p)) for p in b.prefixes for n in names if n):
            return b
    clean = _CORP_MARK_RE.sub("", raw).strip() or "?"
    color = FALLBACK_COLORS[zlib.crc32(clean.encode("utf-8")) % len(FALLBACK_COLORS)]
    return Brand(key="", name=clean, prefixes=(), color=color, mono=clean[:2])


def brand_table(logo_files: dict[str, str]) -> dict[str, dict]:
    """페이지에 싣는 브랜드 표. logo_files 는 브랜드 키 → 로고 파일 상대 경로(없으면 글자 타일)."""
    by_key = {b.key: b for b in BRANDS}
    table = {}
    for b in BRANDS:
        group = by_key.get(b.group or b.key, b)
        table[b.key] = {
            "name": b.name, "logo": logo_files.get(b.key), "mono": b.mono or b.name[:2], "color": b.color,
            "group": group.key, "groupName": group.name,
        }
    return table
