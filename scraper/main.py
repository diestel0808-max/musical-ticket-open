"""세 사이트를 수집해 data/items.json에 누적한다.

사용법: python3 -m scraper.main [--dry-run]
"""
import json
import sys
import traceback
from pathlib import Path

from .common import is_kids, now_kst
from .sources import nol, ticketlink, yes24
from .verify import verify

DATA = Path(__file__).resolve().parent.parent / "data" / "items.json"
SOURCES = {"nol": nol.fetch, "ticketlink": ticketlink.fetch, "yes24": yes24.fetch}
# 다시 수집될 때 최신 값으로 덮어쓸 필드. 나머지(기간·회차·이미지 등)는 비어 있지 않을 때만 덮어쓴다.
TRACKED = ("title", "label", "openAt")


def load(path=DATA):
    if Path(path).exists():
        return json.loads(Path(path).read_text(encoding="utf-8"))
    return {"updatedAt": None, "sources": {}, "items": []}


def collect(db, log=print):
    """db(items.json 내용)를 최신 수집 결과로 갱신해 (db, 새 항목 목록)을 돌려준다."""
    now = now_kst().isoformat(timespec="minutes")
    # 더 이상 수집하지 않는 사이트(예: 멜론티켓)의 소식과 상태는 정리
    by_id = {it["id"]: it for it in db.get("items", []) if it["source"] in SOURCES}
    db["sources"] = {k: v for k, v in db.get("sources", {}).items() if k in SOURCES}
    new_items = []
    rejected = {e["id"] for e in db.get("excluded", [])}  # 장르 확인에서 뺀 소식은 다시 넣지 않음

    for name, fetch in SOURCES.items():
        try:
            fetched = fetch()
            db["sources"][name] = {"ok": True, "count": len(fetched), "at": now}
        except Exception as e:  # 한 사이트가 실패해도 나머지는 계속
            traceback.print_exc()
            db["sources"][name] = {"ok": False, "error": str(e)[:200], "at": now}
            continue
        log(f"[{name}] {len(fetched)}건")
        for it in fetched:
            if it["id"] in rejected:
                continue
            old = by_id.get(it["id"])
            if old:
                old.update({k: it[k] for k in TRACKED})
                if it.get("place"):
                    old["place"] = it["place"]
                for k in ("period", "round", "roundPeriod", "image"):  # 상세에서 채운 값은 비어 있는 값으로 덮지 않음
                    if it.get(k):
                        old[k] = it[k]
                if not old.get("perfId"):  # 예스24는 상세에서 상품 페이지 주소로 바꿔 둔 링크를 유지
                    old["url"] = it["url"]
                old["lastSeenAt"] = now
            else:
                it["firstSeenAt"] = it["lastSeenAt"] = now
                by_id[it["id"]] = it
                new_items.append(it)

    # 수집 기준에서 빠진 항목 정리: 어린이·가족 제목, 그리고 NOL 오픈예정 목록에서 사라진 앞으로의 오픈
    # (NOL 목록은 앞으로 열릴 오픈을 모두 보여주므로, 없으면 아동/가족극으로 걸렀거나 취소된 것)
    fetched_nol = {it["id"] for it in by_id.values() if it.get("lastSeenAt") == now and it["source"] == "nol"}
    nol_ok = db["sources"].get("nol", {}).get("ok")
    for it in list(by_id.values()):
        stale_nol = nol_ok and it["source"] == "nol" and it["id"] not in fetched_nol and (it.get("openAt") or "") >= now
        if is_kids(it["title"]) or stale_nol:
            del by_id[it["id"]]

    fill_yes24_details(by_id.values(), log)
    verify(db, by_id, log)  # 예매처 분류를 KOPIS 장르와 제목 규칙으로 한 번 더 확인
    db["items"] = sorted(by_id.values(), key=lambda x: (x["openAt"] or "9999", x["id"]))
    db["updatedAt"] = now
    return db, new_items


DETAIL_VERSION = 3  # 상세에서 읽는 항목이 늘면 올려서 기존 항목도 다시 읽게 함


def fill_yes24_details(items, log):
    """예스24는 목록에 공연기간·회차 기간이 없어서 상세를 한 번씩만 조회한다(같은 공지의 선예매 항목과 공유)."""
    cache = {}
    today = now_kst().date().isoformat()
    # 상품 페이지가 공지보다 늦게 생기기도 해서, 링크를 못 찾은 공지는 오픈 전까지 매일 다시 본다
    todo = [it for it in items if it["source"] == "yes24" and (
        it.get("detailV") != DETAIL_VERSION or (not it.get("perfId") and (it.get("openAt") or "") >= today))]
    for it in todo:
        nid = it["id"].split(":")[1].split("-")[0]
        if nid not in cache:
            try:
                cache[nid] = yes24.fetch_detail(nid, int(it["openAt"][:4]) if it.get("openAt") else None)
            except Exception as e:
                log(f"  예스24 상세 실패 {nid}: {e}")
                continue
        d = cache[nid]
        it["period"] = d["period"]
        it["roundPeriod"] = d["roundPeriod"]
        it["round"] = d["round"] or it.get("round", "")
        it["detailV"] = DETAIL_VERSION
        it.pop("periodChecked", None)
        if d["place"] and not it.get("place"):
            it["place"] = d["place"]
        if d["perfId"]:  # 공지는 지난 회차가 되면 지워지므로 공연 상품 페이지로 연결
            it["perfId"] = d["perfId"]
            it["url"] = f"https://ticket.yes24.com/Perf/{d['perfId']}"
        if d["image"]:
            it["image"] = d["image"]
    if cache:
        log(f"[yes24 상세] {len(cache)}건 조회")


def main(argv):
    dry = "--dry-run" in argv
    db, new_items = collect(load())
    print(f"새 항목 {len(new_items)}건")
    for it in new_items:
        print(f"  + [{it['source']}] {it['openAt']} {it['title']}")
    for src in SOURCES:
        rows = [it for it in db["items"] if it["source"] == src]
        print(f"  {src}: 공연기간 {sum(1 for it in rows if it.get('period'))}/{len(rows)}, "
              f"회차 {sum(1 for it in rows if it.get('round'))}, 회차기간 {sum(1 for it in rows if it.get('roundPeriod'))}")
    if dry:
        print("(dry-run: 저장 안 함)")
        return
    DATA.parent.mkdir(exist_ok=True)
    DATA.write_text(json.dumps(db, ensure_ascii=False, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main(sys.argv[1:])
