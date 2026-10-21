"""노션 DB에 새 티켓오픈 항목을 추가한다. NOTION_TOKEN / NOTION_DB_ID 환경변수 필요."""
import json
import os
import urllib.request

API = "https://api.notion.com/v1/pages"
SOURCE_NAMES = {"nol": "NOL", "ticketlink": "티켓링크", "yes24": "예스24"}


def enabled():
    return bool(os.environ.get("NOTION_TOKEN") and os.environ.get("NOTION_DB_ID"))


def add_page(item):
    props = {
        "제목": {"title": [{"text": {"content": item["title"][:200]}}]},
        "사이트": {"select": {"name": SOURCE_NAMES.get(item["source"], item["source"])}},
        "공지링크": {"url": item["url"]},
        "장소": {"rich_text": [{"text": {"content": item.get("place", "")[:200]}}]},
        "구분": {"rich_text": [{"text": {"content": item.get("label", "")[:100]}}]},
        "수집ID": {"rich_text": [{"text": {"content": item["id"]}}]},
    }
    if item.get("openAt"):
        props["오픈일시"] = {"date": {"start": item["openAt"]}}
    body = {"parent": {"database_id": os.environ["NOTION_DB_ID"]}, "properties": props}
    if item.get("image"):
        body["cover"] = {"type": "external", "external": {"url": item["image"]}}
    req = urllib.request.Request(
        API,
        data=json.dumps(body).encode(),
        headers={
            "Authorization": f"Bearer {os.environ['NOTION_TOKEN']}",
            "Notion-Version": "2022-06-28",
            "Content-Type": "application/json",
        },
    )
    with urllib.request.urlopen(req, timeout=20) as r:
        return json.loads(r.read())["id"]
