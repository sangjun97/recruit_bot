"""회사 로고(각 회사가 공개한 아이콘)를 받아 사이트 폴더에 둔다. `python -m radar logos` 로 필요할 때만 실행한다.

수집 실행(`radar run`)은 로고를 받지 않는다. 이미 받아 둔 파일만 쓴다.
"""
from __future__ import annotations

from pathlib import Path

from .brands import BRANDS
from .fetch import Fetcher

LOGO_DIR = "logos"
EXTENSIONS = ("png", "svg", "ico", "jpg", "webp")
MAX_BYTES = 300_000


def sniff(data: bytes) -> str | None:
    """파일 내용으로 이미지 종류를 가린다. 이미지가 아니면(차단 페이지 등) None."""
    if data[:8] == b"\x89PNG\r\n\x1a\n":
        return "png"
    if data[:4] == b"\x00\x00\x01\x00":
        return "ico"
    if data[:3] == b"\xff\xd8\xff":
        return "jpg"
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "webp"
    head = data[:1000].lstrip().lower()
    if head.startswith(b"<svg") or (head.startswith(b"<?xml") and b"<svg" in head):
        return "svg"
    return None


def existing_logos(site_dir: Path) -> dict[str, str]:
    """이미 받아 둔 로고. 브랜드 키 → 페이지에서 쓰는 상대 경로('logos/sk.png')."""
    folder = site_dir / LOGO_DIR
    found: dict[str, str] = {}
    if folder.is_dir():
        for path in sorted(folder.iterdir()):
            if path.suffix.lstrip(".") in EXTENSIONS:
                found[path.stem] = f"{LOGO_DIR}/{path.name}"
    return found


def fetch_logos(f: Fetcher, site_dir: Path, force: bool = False) -> tuple[list[str], list[str]]:
    """icon_url 이 있는 브랜드의 로고를 받는다. (받은 키, 실패한 키)를 돌려준다."""
    folder = site_dir / LOGO_DIR
    folder.mkdir(parents=True, exist_ok=True)
    have = existing_logos(site_dir)
    saved, failed = [], []
    for b in BRANDS:
        if not b.icon_url or (b.key in have and not force):
            continue
        try:
            data = f.get(b.icon_url, headers={"Accept": "image/*,*/*;q=0.8"}).content
        except Exception as e:
            print(f"  ! {b.key}: {type(e).__name__}")
            failed.append(b.key)
            continue
        kind = sniff(data)
        if kind is None or len(data) > MAX_BYTES:
            print(f"  ! {b.key}: 이미지가 아니거나 너무 큼 ({len(data)} bytes)")
            failed.append(b.key)
            continue
        for old in folder.glob(f"{b.key}.*"):
            old.unlink()
        (folder / f"{b.key}.{kind}").write_bytes(data)
        saved.append(b.key)
    return saved, failed
