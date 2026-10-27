"""공연중 탭: KOPIS(공연예술통합전산망) 공개 API로 오늘 공연 중인 서울 뮤지컬을 모아 data/ongoing.json에 저장한다.

티켓오픈(data/items.json)과는 완전히 별개로 돈다.
공연중(items)과 1주 안에 개막하는 개막 예정(upcoming) 두 목록을 만든다.
제외: 오픈런, 종료일이 1년 넘게 남은 장기 공연, 서울 밖(지방 투어), 아동/가족 공연, 19세 이상 공연.

사용법: KOPIS_KEY=... python3 -m scraper.ongoing [--dry-run]
"""
import json
import os
import re
import sys
import traceback
import xml.etree.ElementTree as ET
from datetime import timedelta
from pathlib import Path
from urllib.parse import urlencode

from .common import NOT_MUSICAL, http, is_kids, now_kst

API = "http://www.kopis.or.kr/openApi/restful/pblprfr"
DATA = Path(__file__).resolve().parent.parent / "data" / "ongoing.json"
MUSICAL = "GGGA"  # KOPIS 장르 코드: 뮤지컬
SEOUL = "11"  # KOPIS 지역(시도) 코드: 서울
MAX_RUN_AHEAD = timedelta(days=365)  # 이보다 더 남은 공연은 장기 공연으로 보고 제외
KIDS_AGE = ("개월", "만 3세", "만 4세", "만 5세")  # 관람연령이 이렇게 낮으면 아동극
ADULT = re.compile(r"19세|청소년\s*관람\s*불가|성인")  # 19세 이상 쇼 공연 제외
UPCOMING_DAYS = 7  # 개막 예정 탭: 오늘 기준 이 날수 안에 개막


def kopis(path="", **params):
    root = ET.fromstring(http(f"{API}{path}?{urlencode(params)}"))
    err = root.find("./db/errmsg")
    if err is not None and (err.text or "").strip():
        raise RuntimeError(f"KOPIS 오류: {err.text.strip()}")
    return root


def text(el, tag):
    v = el.find(tag)
    return (v.text or "").strip() if v is not None and v.text else ""


def kdate(s):
    """'2026.11.24' → '2026-11-24'"""
    return s.replace(".", "-") if s else ""


def list_kopis(key, state, start, end):
    """서울 뮤지컬(아동 제외) 목록. state: '02' 공연중, '01' 공연예정. KOPIS는 페이지당 최대 100건."""
    out, page = [], 1
    while True:
        root = kopis(service=key, stdate=start.strftime("%Y%m%d"), eddate=end.strftime("%Y%m%d"), cpage=page,
                     rows=100, shcate=MUSICAL, prfstate=state, signgucode=SEOUL, kidstate="N")
        rows = root.findall("./db")
        out += rows
        if len(rows) < 100 or page >= 10:
            return out
        page += 1


# KOPIS 예매처 이름 → 이 사이트에서 쓰는 사이트 키. NOL은 옛 인터파크 주소를 NOL 상품 페이지로 바꾼다.
def booking_link(name, url):
    m = re.search(r"GoodsCode=(\d+)", url)
    if "놀유니버스" in name or "인터파크" in name or "interpark" in url:
        return {"source": "nol", "name": "NOL", "url": f"https://nol.yanolja.com/ticket/products/{m.group(1)}" if m else url}
    if "티켓링크" in name or "ticketlink" in url:
        return {"source": "ticketlink", "name": "티켓링크", "url": url.replace("http://", "https://")}
    if "예스24" in name or "yes24" in url:
        return {"source": "yes24", "name": "예스24", "url": url}
    return {"source": "", "name": re.sub(r"\s*(주식회사|\(주\)|㈜)\s*", "", name), "url": url}


def detail(key, pid):
    db = kopis(f"/{pid}", service=key).find("./db")
    links = []
    for r in db.findall("./relates/relate"):
        name, url = text(r, "relatenm"), text(r, "relateurl")
        if url:
            links.append(booking_link(name, url))
    # 4대 예매처를 앞에
    links.sort(key=lambda l: ["nol", "ticketlink", "yes24", ""].index(l["source"]))
    return {
        "age": text(db, "prfage"),
        "child": text(db, "child"),
        "cast": text(db, "prfcast"),
        "runtime": text(db, "prfruntime"),
        "links": links,
    }


def build(rows, key, cache, limit, excluded, log):
    """KOPIS 목록 행 → 화면용 항목. 오픈런·장기·아동·19세 이상·콘서트는 빼고, 뺀 이유를 excluded에 남긴다."""
    items = []
    for row in rows:
        pid = text(row, "mt20id")
        title, start, end = text(row, "prfnm"), kdate(text(row, "prfpdfrom")), kdate(text(row, "prfpdto"))

        def skip(reason, age=""):
            excluded.append({"id": pid, "title": title, "reason": reason, "start": start, "end": end,
                             "place": text(row, "fcltynm"), "age": age})

        if text(row, "openrun").upper() == "Y":
            skip("오픈런")
            continue
        if not end or end > limit:
            skip("장기 공연(종료일 1년 이상 남음)")
            continue
        if is_kids(title):
            skip("아동·가족(제목)")
            continue
        if NOT_MUSICAL.search(title):
            skip("콘서트·갈라")
            continue
        m = re.search(r"\s*\[([^\]]+)\]\s*$", title)
        it = {
            "id": pid,
            "title": title[: m.start()] if m else title,
            "area": m.group(1) if m else "",  # 예: 대학로, 서울, 서울 광진
            "start": kdate(text(row, "prfpdfrom")),
            "end": end,
            "place": text(row, "fcltynm"),
            # www.kopis.or.kr은 https에서 다른 주소로 넘겨서, 바로 https://kopis.or.kr 로
            "image": re.sub(r"^https?://(www\.)?kopis\.or\.kr", "https://kopis.or.kr", text(row, "poster")),
            "url": f"https://www.kopis.or.kr/por/db/pblprfr/pblprfrView.do?menuId=MNU_00020&mt20Id={pid}",
        }
        d = cache.get(pid, {}).get("detail")
        if not d or any("source" not in l for l in d.get("links", [])):
            try:
                d = detail(key, pid)
            except Exception as e:
                # 상세(관람연령·아동 표시)를 못 보면 아동극·19세 이상을 거를 수 없으니 이번엔 뺐다가 다음 수집 때 다시 본다
                log(f"  상세 실패 {pid}: {e}")
                skip("상세 조회 실패(다음 수집 때 다시 확인)")
                continue
        age = d.get("age", "")
        if d.get("child", "").upper() == "Y":
            skip("아동(KOPIS 아동공연 표시)", age)
            continue
        if any(k in age for k in KIDS_AGE):
            skip("아동(관람연령)", age)
            continue
        if ADULT.search(age):
            skip("19세 이상", age)
            continue
        it["detail"] = d
        items.append(it)
    return items


def collect(key, prev, log=print):
    today = now_kst().date()
    limit = (today + MAX_RUN_AHEAD).isoformat()
    # 상세는 공연당 한 번만(개막 예정이던 공연이 공연중으로 넘어와도 재사용)
    cache = {it["id"]: it for it in prev.get("items", []) + prev.get("upcoming", [])}
    excluded = []

    items = build(list_kopis(key, "02", today, today), key, cache, limit, excluded, log)
    items.sort(key=lambda x: (x["end"], x["title"]))

    # 개막 예정: 내일~7일 뒤에 첫 공연이 있는 작품
    soon = today + timedelta(days=UPCOMING_DAYS)
    rows = [r for r in list_kopis(key, "01", today, soon)
            if today.isoformat() < kdate(text(r, "prfpdfrom")) <= soon.isoformat()]
    upcoming = build(rows, key, cache, limit, excluded, log)
    upcoming.sort(key=lambda x: (x["start"], x["title"]))

    log(f"[공연중] {len(items)}건, [개막 예정] {len(upcoming)}건, 제외 {len(excluded)}건")
    for e in excluded:
        log(f"  - {e['reason']}: {e['title']} ({e['start']}~{e['end']}, {e['age']})")
    # excluded는 화면에 쓰지 않지만, 제외 기준이 맞게 걸렀는지 점검할 수 있게 함께 저장
    return {"updatedAt": now_kst().isoformat(timespec="minutes"), "ok": True,
            "items": items, "upcoming": upcoming, "excluded": excluded}


def main(argv):
    key = os.environ.get("KOPIS_KEY")
    if not key:
        print("KOPIS_KEY가 없어 공연중 수집을 건너뜀")
        return
    prev = json.loads(DATA.read_text(encoding="utf-8")) if DATA.exists() else {}
    try:
        db = collect(key, prev)
    except Exception as e:
        traceback.print_exc()
        # 실패해도 어제 목록은 유지하고, 화면에 실패 표시만
        db = dict(prev or {"items": []}, ok=False, error=str(e)[:300])
    if "--dry-run" in argv:
        print(json.dumps(db, ensure_ascii=False)[:2000])
        return
    DATA.write_text(json.dumps(db, ensure_ascii=False, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main(sys.argv[1:])
