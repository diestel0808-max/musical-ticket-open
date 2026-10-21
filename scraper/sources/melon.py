"""멜론티켓: 티켓오픈 소식 목록('뮤지컬/연극' 탭) → 공지 상세 → 공연 상품 페이지 장르로 뮤지컬만 남긴다.

목록에는 연극·마술·쇼가 섞여 있고, 선예매/일반처럼 오픈 일정이 여러 개인 공지는 목록에 날짜가 없어서
공지마다 상세를 읽는다(하루 1회 수집이라 요청 수는 수십 건 수준).
"""
import html
import re
from datetime import datetime

from ..common import html_text, http, is_kids, iso_kst, make_item, parse_period, parse_round_period

BASE = "https://ticket.melon.com"
LIST_API = f"{BASE}/csoon/ajax/listTicketOpen.htm"
LIST_ITEM = re.compile(
    r'<a href="\./detail\.htm\?csoonId=(\d+)" class="tit">\s*(.*?)</a>.*?class="poster"><img src=\s*"([^"]*)"', re.S)
SCHEDULE_LI = re.compile(r'<li[^>]*>\s*<p class="tit_consert">(.*?)</p>(.*?)</li>', re.S)
SCHEDULE = re.compile(
    r'<dt class="tit_type">\s*([^<]*?)\s*</dt>\s*<dd class="txt_date">.*?(\d{4})년\s*(\d{1,2})월\s*(\d{1,2})일[^<]*?(\d{1,2}):(\d{2})',
    re.S)
PROD_ID = re.compile(r"bannerLanding\('TD',\s*'(\d+)'\)")
GENRE = re.compile(r'장르</dt>\s*<dd class="txt_info">([^<]+)</dd>')
PLACE = re.compile(r'id="performanceHallBtn"[^>]*title="([^"]+)"')


def clean(s):
    return re.sub(r"\s+", " ", html.unescape(s or "")).strip()


def genre_of(prod_id, cache={}):
    """공연 상품 페이지의 (장르, 공연장). 같은 상품이 여러 공지에 나오므로 실행 중에는 기억해 둔다."""
    if prod_id not in cache:
        page = http(f"{BASE}/performance/index.htm?prodId={prod_id}")
        g, p = GENRE.search(page), PLACE.search(page)
        cache[prod_id] = (clean(g.group(1)) if g else "", clean(p.group(1)) if p else "")
    return cache[prod_id]


def fetch(pages=3):
    items = []
    for page in range(pages):
        # pageIndex는 페이지 번호가 아니라 시작 행(1, 11, 21 …)
        s = http(LIST_API, data={"orderType": "0", "pageIndex": page * 10 + 1, "schGcode": "GENRE_ART_ALL",
                                 "schText": "", "schDt": ""})
        for cid, title, img in LIST_ITEM.findall(s):
            title = clean(title)
            if is_kids(title) or re.match(r"(대학로\s*)?(코믹\s*)?연극", title):
                continue
            items.extend(fetch_notice(cid, title, re.sub(r"/melon/resize/\d+x\d+", "/melon/resize/180x254", img)))
    return items


def fetch_notice(cid, title, image):
    raw = http(f"{BASE}/csoon/detail.htm?csoonId={cid}")
    text = html_text(raw)
    blocks = SCHEDULE_LI.findall(raw) or [("", raw)]
    multi = sum(len(SCHEDULE.findall(b)) for _, b in blocks) > 1
    out = []
    for bi, (name, block) in enumerate(blocks):
        prod = PROD_ID.search(block)
        genre, place = genre_of(prod.group(1)) if prod else ("", "")
        # 상품 장르가 뮤지컬인 것만. 상품 링크가 없으면 제목으로 판단
        if (genre and genre != "뮤지컬") or (not genre and "뮤지컬" not in title):
            continue
        url = f"{BASE}/performance/index.htm?prodId={prod.group(1)}" if prod else f"{BASE}/csoon/detail.htm?csoonId={cid}"
        for si, (label, y, mo, d, hh, mm) in enumerate(SCHEDULE.findall(block)):
            open_at = iso_kst(datetime(int(y), int(mo), int(d), int(hh), int(mm)))
            ref_year = int(y)
            round_, round_period = parse_round_period(text, ref_year)
            out.append(make_item(
                "melon", f"{cid}-{bi}-{si}" if multi else cid,
                # 공지 하나에 여러 공연이 묶여 있으면 공연별 이름을 쓰고, 회차 표시는 공지 제목에서
                title if len(blocks) == 1 else f"{clean(name)} {title}",
                open_at, url, place=place, image=image,
                label="" if label in ("티켓오픈", "일반예매") else label,
                period=parse_period(text, ref_year), round_=round_, round_period=round_period,
            ))
    return out
