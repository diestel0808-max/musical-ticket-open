"""NOL 티켓(구 인터파크): 오픈예정 페이지가 쓰는 JSON API. 장르 코드로 뮤지컬만 요청."""
import json
from datetime import datetime

from ..common import http, iso_kst, make_item

API = "https://nol.yanolja.com/ticket/display/api/upcoming"
MUSICAL_GENRE = "01011"


def fetch(max_pages=10):
    items, cursor = [], None
    for _ in range(max_pages):
        body = {"sort": "open", "goods_genre_codes": [MUSICAL_GENRE]}
        if cursor:
            body["cursor"] = cursor
        d = json.loads(http(API, json_body=body))
        for n in d["notices"]:
            url = (f"https://nol.yanolja.com/ticket/products/{n['goods_code']}"
                   if n.get("goods_code") else "https://nol.yanolja.com/ticket/display/upcoming")
            image = n.get("goods_poster_image_url") or n.get("open_notice_poster_image_url") or ""
            # 선예매/일반예매처럼 오픈 일정이 여러 개면 각각 따로 표시
            for t in n.get("ticket_dates") or [{}]:
                open_at = t.get("ticket_open_date")
                sid = f"{n['id']}-{t['ticket_date_id']}" if t.get("ticket_date_id") else n["id"]
                label = t.get("ticket_other_open_name") or t.get("ticket_open_type_name") or ""
                items.append(make_item(
                    "nol", sid, n["title"] or n.get("goods_name", ""),
                    iso_kst(datetime.fromisoformat(open_at)) if open_at else None,
                    url, place=n.get("venue_name", ""), image=image, label=label,
                ))
        cursor = d["summary"].get("next_cursor")
        if not cursor or not d["notices"]:
            break
    return items
