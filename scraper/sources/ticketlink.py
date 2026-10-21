"""티켓링크: 공지사항 > 티켓오픈 카테고리 JSON API."""
import json
from datetime import datetime

from ..common import html_text, http, iso_kst, make_item, parse_period, parse_round_period

API = "https://www.ticketlink.co.kr/help/getNoticeList?page={page}&noticeCategoryCode=TICKET_OPEN"
MUSICAL_SUBCATEGORY = 16  # 공연 > 뮤지컬


def is_musical(r):
    return r.get("subCategoryId") == MUSICAL_SUBCATEGORY or "뮤지컬" in (r.get("title") or "")


def fetch(max_pages=4):
    items = []
    for page in range(1, max_pages + 1):
        d = json.loads(http(API.format(page=page)))["result"]
        for r in d["result"]:
            if not is_musical(r):
                continue
            open_at = r.get("ticketOpenDatetime")
            ref_year = int(open_at[:4]) if open_at else None
            text = html_text(r.get("content"))
            round_, round_period = parse_round_period(text, ref_year)
            items.append(make_item(
                "ticketlink", r["noticeId"], r["title"],
                iso_kst(datetime.fromisoformat(open_at)) if open_at else None,
                f"https://www.ticketlink.co.kr/help/notice/{r['noticeId']}",
                place=r.get("placeName") or "",
                period=parse_period(text, ref_year),
                round_=round_, round_period=round_period,
                image=(r.get("imagePath") or r.get("noticeImagePath") or "").replace("http://", "https://"),
            ))
        if page >= d["paging"]["pageCount"]:
            break
    return items
