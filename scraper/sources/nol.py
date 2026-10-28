"""NOL 티켓(구 인터파크): 오픈예정 페이지가 쓰는 JSON API. 장르 코드로 뮤지컬만 요청하고 아동/가족극은 뺀다."""
import json
import urllib.request
from datetime import datetime

from ..common import http, is_kids, iso_kst, make_item, norm_round

API = "https://nol.yanolja.com/ticket/display/api/upcoming"
MUSICAL_GENRE = "01011"


def exists(url):
    try:
        req = urllib.request.Request(url, method="HEAD", headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=5) as r:
            return r.status == 200
    except Exception:
        return False


def poster(n):
    """상품 포스터를 쓰되, 막 등록된 공연은 상품 포스터가 아직 없어(404) 공지용 포스터로 대신한다."""
    goods, notice = n.get("goods_poster_image_url") or "", n.get("open_notice_poster_image_url") or ""
    if goods and (not notice or exists(goods)):
        return goods
    return notice or goods


def fetch(max_pages=10):
    items, cursor = [], None
    for _ in range(max_pages):
        body = {"sort": "open", "goods_genre_codes": [MUSICAL_GENRE]}
        if cursor:
            body["cursor"] = cursor
        d = json.loads(http(API, json_body=body))
        for n in d["notices"]:
            # NOL은 아동/가족극도 장르가 '뮤지컬'이라 하위 장르로 거른다(NOL 화면에서는 '가족' 탭에 나옴)
            if "아동" in (n.get("goods_sub_genre_name") or "") or is_kids(n.get("title")):
                continue
            url = (f"https://nol.yanolja.com/ticket/products/{n['goods_code']}"
                   if n.get("goods_code") else "https://nol.yanolja.com/ticket/display/upcoming")
            period = ({"start": n["goods_start_date"], "end": n.get("goods_end_date") or n["goods_start_date"]}
                      if n.get("goods_start_date") else None)
            image = poster(n)
            # 선예매/일반예매처럼 오픈 일정이 여러 개면 각각 따로 표시
            for t in n.get("ticket_dates") or [{}]:
                open_at = t.get("ticket_open_date")
                sid = f"{n['id']}-{t['ticket_date_id']}" if t.get("ticket_date_id") else n["id"]
                label = t.get("ticket_other_open_name") or t.get("ticket_open_type_name") or ""
                items.append(make_item(
                    "nol", sid, n["title"] or n.get("goods_name", ""),
                    iso_kst(datetime.fromisoformat(open_at)) if open_at else None,
                    url, place=n.get("venue_name", ""), image=image, label=label, period=period,
                    # NOL은 공지 상세가 없어 회차별 기간을 알 수 없음 → 회차 이름만
                    round_=norm_round(n.get("open_name") or "") or norm_round(n.get("open_type_name") or ""),
                ))
        cursor = d["summary"].get("next_cursor")
        if not cursor or not d["notices"]:
            break
    return items
