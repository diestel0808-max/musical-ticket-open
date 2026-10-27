"""공연중 탭: KOPIS(공연예술통합전산망) 공개 API로 오늘 공연 중인 서울 뮤지컬을 모아 data/ongoing.json에 저장한다.

티켓오픈(data/items.json)과는 완전히 별개로 돈다.
제외: 오픈런, 종료일이 1년 넘게 남은 장기 공연, 서울 밖(지방 투어), 아동/가족 공연.

사용법: KOPIS_KEY=... python3 -m scraper.ongoing [--dry-run]
"""
import json
import os
import sys
import traceback
import xml.etree.ElementTree as ET
from datetime import timedelta
from pathlib import Path
from urllib.parse import urlencode

from .common import http, is_kids, now_kst

API = "http://www.kopis.or.kr/openApi/restful/pblprfr"
DATA = Path(__file__).resolve().parent.parent / "data" / "ongoing.json"
MUSICAL = "GGGA"  # KOPIS 장르 코드: 뮤지컬
SEOUL = "11"  # KOPIS 지역(시도) 코드: 서울
MAX_RUN_AHEAD = timedelta(days=365)  # 이보다 더 남은 공연은 장기 공연으로 보고 제외
KIDS_AGE = ("개월", "만 3세", "만 4세", "만 5세")  # 관람연령이 이렇게 낮으면 아동극


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


def list_ongoing(key, today):
    """오늘 공연 중인 서울 뮤지컬(아동 제외) 목록. KOPIS는 페이지당 최대 100건."""
    day = today.strftime("%Y%m%d")
    out, page = [], 1
    while True:
        root = kopis(service=key, stdate=day, eddate=day, cpage=page, rows=100,
                     shcate=MUSICAL, prfstate="02", signgucode=SEOUL, kidstate="N")
        rows = root.findall("./db")
        out += rows
        if len(rows) < 100 or page >= 10:
            return out
        page += 1


def detail(key, pid):
    db = kopis(f"/{pid}", service=key).find("./db")
    links = []
    for r in db.findall("./relates/relate"):
        name, url = text(r, "relatenm"), text(r, "relateurl")
        if url:
            links.append({"name": name, "url": url})
    return {
        "age": text(db, "prfage"),
        "child": text(db, "child"),
        "cast": text(db, "prfcast"),
        "runtime": text(db, "prfruntime"),
        "links": links,
    }


def collect(key, prev, log=print):
    today = now_kst().date()
    limit = (today + MAX_RUN_AHEAD).isoformat()
    cache = {it["id"]: it for it in prev.get("items", [])}  # 상세는 공연당 한 번만
    items, skipped = [], {"openrun": 0, "long": 0, "kids": 0}
    for row in list_ongoing(key, today):
        pid = text(row, "mt20id")
        title, end = text(row, "prfnm"), kdate(text(row, "prfpdto"))
        if text(row, "openrun").upper() == "Y":
            skipped["openrun"] += 1
            continue
        if not end or end > limit:
            skipped["long"] += 1
            continue
        if is_kids(title):
            skipped["kids"] += 1
            continue
        it = {
            "id": pid,
            "title": title,
            "start": kdate(text(row, "prfpdfrom")),
            "end": end,
            "place": text(row, "fcltynm"),
            "image": text(row, "poster").replace("http://", "https://"),
            "url": f"https://www.kopis.or.kr/por/db/pblprfr/pblprfrView.do?menuId=MNU_00020&mt20Id={pid}",
        }
        d = cache.get(pid, {}).get("detail")
        if d is None:
            try:
                d = detail(key, pid)
            except Exception as e:
                log(f"  상세 실패 {pid}: {e}")
                d = {}
        if d.get("child", "").upper() == "Y" or any(k in d.get("age", "") for k in KIDS_AGE):
            skipped["kids"] += 1
            continue
        it["detail"] = d
        items.append(it)
    items.sort(key=lambda x: (x["end"], x["title"]))
    log(f"[공연중] {len(items)}건 (제외: 오픈런 {skipped['openrun']}, 장기 {skipped['long']}, 아동 {skipped['kids']})")
    return {"updatedAt": now_kst().isoformat(timespec="minutes"), "ok": True, "items": items}


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
