"""공통 유틸: HTTP 요청, 표준 Item 형식, 시간 처리."""
import html
import json
import re
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone

KST = timezone(timedelta(hours=9))
UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/130.0 Safari/537.36"
)


def http(url, data=None, json_body=None, headers=None, timeout=20):
    """GET/POST 요청 후 응답 본문(str)을 돌려준다."""
    h = {"User-Agent": UA, "Accept-Language": "ko-KR,ko;q=0.9"}
    if headers:
        h.update(headers)
    body = None
    if json_body is not None:
        body = json.dumps(json_body).encode()
        h["Content-Type"] = "application/json"
    elif data is not None:
        body = urllib.parse.urlencode(data).encode()
        h["Content-Type"] = "application/x-www-form-urlencoded; charset=UTF-8"
    req = urllib.request.Request(url, data=body, headers=h)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read().decode("utf-8", errors="replace")


def clean_title(s):
    """<b>[단독판매]</b> 같은 강조 태그와 공백을 정리한다. (<겨울왕국> 같은 작품명 괄호는 유지)"""
    s = re.sub(r"</?(b|em|span|strong|br)\s*/?>", " ", s or "", flags=re.I)
    s = html.unescape(s)
    return re.sub(r"\s+", " ", s).strip()


def now_kst():
    return datetime.now(KST)


def iso_kst(dt):
    return dt.replace(tzinfo=KST).isoformat(timespec="minutes") if dt else None


EXCLUSIVE = re.compile(r"^\[?\s*단독판매\s*\]?\s*")
SUFFIX = re.compile(r"\s*(티켓\s*오픈|오픈)\s*(안내|공지)?\s*$")


def make_item(source, source_id, title, open_at, url, place="", image="", label=""):
    title = clean_title(title)
    exclusive = bool(EXCLUSIVE.match(title))
    title = SUFFIX.sub("", EXCLUSIVE.sub("", title)) or title
    return {
        "id": f"{source}:{source_id}",
        "source": source,
        "title": title,
        "exclusive": exclusive,
        "label": label,  # 예: 일반예매, 선예매
        "openAt": open_at,  # ISO 문자열(KST) 또는 None
        "place": place or "",
        "url": url,
        "image": image or "",
    }
