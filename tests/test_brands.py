"""회사 이름 → 브랜드(로고·묶음) 규칙과 로고 파일 처리."""
import json
import re

from radar.brands import BRANDS, brand_for, brand_table
from radar.db import Database
from radar.logos import existing_logos, sniff
from radar.models import Posting
from radar.site import build_site


def test_brand_rules_prefer_the_more_specific_name():
    assert brand_for("삼성전자 DX부문").key == "samsung" and brand_for("삼성카드").key == "samsungcard"
    assert brand_for("LG유플러스").key == "lguplus" and brand_for("LG CNS").key == "lg"
    assert brand_for("카카오모빌리티").key == "kakaomobility" and brand_for("카카오페이").key == "kakao"
    assert brand_for("KB국민카드").key == "kbcard" and brand_for("KB국민은행").key == "kbstar"
    assert brand_for("신한카드").key == "shinhancard" and brand_for("신한은행").key == "shinhanbank"
    assert brand_for("현대카드/현대커머셜").key == "hyundaicard" and brand_for("현대커머셜").key == "hyundaicommercial"
    assert brand_for("현대자동차").key == "hyundai" and brand_for("현대오토에버").key == "autoever"


def test_brand_rules_ignore_case_and_corporate_marks():
    assert brand_for("kt cloud").key == "kt" and brand_for("KT").key == "kt"
    assert brand_for("(주)한화 글로벌부문").key == "hanwha" and brand_for("한화시스템/ICT").key == "hanwha"
    assert brand_for("(주)두산-전자").key == "doosan" and brand_for("HD한국조선해양").key == "hd"
    assert brand_for("SK주식회사(AX)").key == "sk" and brand_for("티맵모빌리티").key == "tmap"


def test_unknown_company_gets_a_letter_tile():
    b = brand_for("(주)어떤회사")
    assert b.key == "" and b.mono == "어떤" and b.name == "어떤회사" and b.color.startswith("#")
    assert brand_for("어떤회사").color == b.color   # 같은 회사는 늘 같은 색
    assert brand_for(None).mono == "?"


def test_brand_table_groups_sub_brands_under_the_parent():
    table = brand_table({"lg": "logos/lg.ico", "sk": "logos/sk.png"})
    assert table["lguplus"]["group"] == "lg" and table["lguplus"]["groupName"] == "LG" and table["lguplus"]["logo"] is None
    assert table["tmap"]["group"] == "sk" and table["sk"]["logo"] == "logos/sk.png"
    assert table["wooricard"]["mono"] == "우리" and table["kia"]["groupName"] == "기아"
    keys = [b.key for b in BRANDS]
    assert len(keys) == len(set(keys))
    assert all((b.group or b.key) in keys for b in BRANDS)


def test_sniff_accepts_images_only():
    assert sniff(b"\x89PNG\r\n\x1a\n" + b"0" * 20) == "png"
    assert sniff(b"\x00\x00\x01\x00\x01\x00") == "ico"
    assert sniff(b'<?xml version="1.0"?><svg xmlns="http://www.w3.org/2000/svg"></svg>') == "svg"
    assert sniff(b"  <svg viewBox='0 0 1 1'></svg>") == "svg"
    assert sniff(b"<!doctype html><html><body>Access Denied</body></html>") is None   # 차단 페이지를 로고로 저장하지 않는다


def test_site_uses_only_logo_files_that_exist(tmp_path):
    site = tmp_path / "site"
    (site / "logos").mkdir(parents=True)
    (site / "logos" / "sk.png").write_bytes(b"\x89PNG\r\n\x1a\n")
    (site / "logos" / "notes.txt").write_text("로고 아님", encoding="utf-8")
    assert existing_logos(site) == {"sk": "logos/sk.png"}

    db = Database(tmp_path / "t.sqlite")
    far = __import__("datetime").datetime(2999, 1, 1)
    db.upsert(Posting(source="t", external_id="1", company="SK주식회사(AX)", title="AI Engineer", url="u1", end_at=far))
    db.upsert(Posting(source="t", external_id="2", company="어떤회사", title="Data Scientist", url="u2", end_at=far))
    html = build_site(db, site, 7, []).read_text(encoding="utf-8")
    data = {d["id"]: d for d in json.loads(re.search(r'<script id="data" type="application/json">(.*?)</script>', html, re.S).group(1))}
    assert data["t:1"]["b"] == "sk" and "bm" not in data["t:1"]
    assert data["t:2"]["b"] == "" and data["t:2"]["bm"] == "어떤" and data["t:2"]["bc"].startswith("#")
    brands = json.loads(re.search(r"var BRANDS = (\{.*?\});\n", html, re.S).group(1))
    assert brands["sk"]["logo"] == "logos/sk.png" and brands["lg"]["logo"] is None   # 파일이 없으면 글자 타일
