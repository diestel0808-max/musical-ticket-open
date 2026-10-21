"""예스24 티켓: 공지사항 목록 ajax(HTML 조각). 장르=뮤지컬(15457)."""
import re
from datetime import datetime

from ..common import html_text, http, is_kids, iso_kst, make_item, parse_period, parse_round_period

API = "https://ticket.yes24.com/New/Notice/Ajax/axList.aspx"
DETAIL_API = "https://ticket.yes24.com/New/Notice/Ajax/axRead.aspx"
PERF_ID = re.compile(r"GetSiteDetailURL\((\d+)\)")
OG_IMAGE = re.compile(r'og:image"\s+content="([^"]+)"')
PLACE = re.compile(r"(?:공연\s*장\s*소?|(?<![가-힣])장\s*소)\s*[:：]\s*([^\r\n※]+)")
MUSICAL_GENRE = "15457"
LINK = re.compile(r'<a href="#id=(\d+)">(.*?)</a>', re.S)
DATE = re.compile(r"(\d{4})\.(\d{2})\.(\d{2})\([^)]*\)\s*(\d{2}):(\d{2})")
PRESALE = re.compile(r"presaleTit(\d)='([^']*)'.*?presaleTime\1='([^']*)'", re.S)


def parse_date(s):
    m = DATE.search(s or "")
    return iso_kst(datetime(*map(int, m.groups()))) if m else None


def fetch(pages=2, size=20):
    items = []
    for page in range(1, pages + 1):
        s = http(API, data={"page": page, "size": size, "genre": MUSICAL_GENRE, "province": "",
                            "order": "1", "searchType": "All", "searchText": ""})
        for row in s.split("<tr>")[1:]:
            m = LINK.search(row)
            if not m or "오픈" not in row[: m.start()]:
                continue
            nid, title = m.groups()
            if is_kids(title):
                continue
            rest = row[m.end():]
            url = f"https://ticket.yes24.com/New/Notice/NoticeMain.aspx#id={nid}"
            items.append(make_item("yes24", nid, title, parse_date(rest), url))
            # 선예매 등 추가 오픈 일정
            for no, name, when in PRESALE.findall(rest):
                if name and parse_date(when):
                    items.append(make_item("yes24", f"{nid}-p{no}", title, parse_date(when), url, label=name))
    return items


def fetch_detail(source_id, ref_year=None):
    """공지 상세에서 공연기간·공연장·회차·회차 기간, 그리고 공연 상품 페이지 주소와 포스터를 읽는다.

    source_id는 '18708' 또는 '18708-p1'. 공지는 지난 회차가 되면 지워지므로 링크는 상품 페이지로 바꾼다.
    """
    nid = str(source_id).split("-")[0]
    raw = http(DETAIL_API, data={"bId": nid, "genre": MUSICAL_GENRE, "province": "", "order": "1"})
    text = html_text(raw)
    m = PLACE.search(text)
    round_, round_period = parse_round_period(text, ref_year)
    detail = {
        "period": parse_period(text, ref_year),
        "place": re.sub(r"\s+", " ", m.group(1)).strip()[:60] if m else "",
        "round": round_,
        "roundPeriod": round_period,
        "perfId": None,
        "image": "",
    }
    p = PERF_ID.search(raw)
    if p:
        detail["perfId"] = p.group(1)
        try:
            og = OG_IMAGE.search(http(f"https://ticket.yes24.com/Perf/{p.group(1)}"))
            if og:
                detail["image"] = "https:" + og.group(1) if og.group(1).startswith("//") else og.group(1)
        except Exception:
            pass
    return detail
