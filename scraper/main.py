"""세 사이트를 수집해 data/items.json에 누적하고, 새 항목을 노션에 추가한다.

사용법: python3 -m scraper.main [--dry-run] [--no-notion]
"""
import json
import sys
import traceback
from datetime import timedelta
from pathlib import Path

from . import notion
from .common import now_kst
from .sources import nol, ticketlink, yes24

DATA = Path(__file__).resolve().parent.parent / "data" / "items.json"
SOURCES = {"nol": nol.fetch, "ticketlink": ticketlink.fetch, "yes24": yes24.fetch}
TRACKED = ("title", "label", "openAt", "place", "url", "image")


def load():
    if DATA.exists():
        return json.loads(DATA.read_text(encoding="utf-8"))
    return {"updatedAt": None, "sources": {}, "items": []}


def main(argv):
    dry = "--dry-run" in argv
    use_notion = notion.enabled() and "--no-notion" not in argv and not dry
    now = now_kst().isoformat(timespec="minutes")
    db = load()
    by_id = {it["id"]: it for it in db["items"]}
    new_items = []

    for name, fetch in SOURCES.items():
        try:
            fetched = fetch()
            db["sources"][name] = {"ok": True, "count": len(fetched), "at": now}
        except Exception as e:  # 한 사이트가 실패해도 나머지는 계속
            traceback.print_exc()
            db["sources"][name] = {"ok": False, "error": str(e)[:200], "at": now}
            continue
        print(f"[{name}] {len(fetched)}건")
        for it in fetched:
            old = by_id.get(it["id"])
            if old:
                old.update({k: it[k] for k in TRACKED})
                old["lastSeenAt"] = now
            else:
                it["firstSeenAt"] = it["lastSeenAt"] = now
                by_id[it["id"]] = it
                new_items.append(it)

    print(f"새 항목 {len(new_items)}건")
    for it in new_items:
        print(f"  + [{it['source']}] {it['openAt']} {it['title']}")

    if use_notion:
        sync_notion(by_id.values(), now_kst())

    db["items"] = sorted(by_id.values(), key=lambda x: (x["openAt"] or "9999", x["id"]))
    db["updatedAt"] = now
    if dry:
        print("(dry-run: 저장 안 함)")
        return
    DATA.parent.mkdir(exist_ok=True)
    DATA.write_text(json.dumps(db, ensure_ascii=False, indent=1), encoding="utf-8")


def sync_notion(items, now):
    """아직 노션에 안 올린 항목 중 오픈이 지나지 않은 것만 올린다(처음 연결 시 과거 항목 폭주 방지)."""
    today = (now - timedelta(days=1)).isoformat()
    for it in items:
        if it.get("notionPageId"):
            continue
        if it.get("openAt") and it["openAt"] < today:
            continue
        try:
            it["notionPageId"] = notion.add_page(it)
            print(f"  노션 추가: {it['title']}")
        except Exception as e:
            print(f"  노션 실패: {it['title']} — {e}")


if __name__ == "__main__":
    main(sys.argv[1:])
