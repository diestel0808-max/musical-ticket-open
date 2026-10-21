"""공통 유틸: HTTP 요청, 표준 Item 형식, 시간 처리."""
import html
import json
import re
import urllib.parse
import urllib.request
from datetime import date, datetime, timedelta, timezone

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


def html_text(s):
    """HTML 조각을 한 줄짜리 일반 텍스트로."""
    s = re.sub(r"<br\s*/?>|</p>|</div>|</li>", "\n", s or "", flags=re.I)
    s = html.unescape(re.sub(r"<[^>]+>", " ", s))
    return re.sub(r"[ \t\u00a0\u200b]+", " ", s)


PERIOD_KEY = re.compile(r"공연\s*(?:기간|일시|일자|날짜|일정)\s*[:：]?|(?<![가-힣])(?:일\s*시|기\s*간)\s*[:：]")
DATE_IN_TEXT = re.compile(
    r"(?:(\d{4})\s*년\s*)?(\d{1,2})\s*월\s*(\d{1,2})\s*일"  # 2026년 11월 13일 / 11월 13일
    r"|(\d{4})\s*[.\-/]\s*(\d{1,2})\s*[.\-/]\s*(\d{1,2})"  # 2026.11.13
)


def parse_period(text, ref_year=None):
    """'공연 기간 : 2026년 10월 09일(금) ~ 2027년 01월 03일(일)' 같은 문구에서 기간을 뽑는다.

    반환: {"start": "YYYY-MM-DD", "end": "YYYY-MM-DD"} 또는 None
    """
    m = PERIOD_KEY.search(text or "")
    if not m:
        return None
    # 같은 줄에서 '※'·'시간' 안내가 나오기 전까지만 본다
    window = re.split(r"[\r\n※]|공연\s*시간|관람", text[m.end(): m.end() + 120])[0]
    dates = []
    for d in DATE_IN_TEXT.finditer(window):
        y, mo, da = (d.group(1), d.group(2), d.group(3)) if d.group(2) else (d.group(4), d.group(5), d.group(6))
        dates.append([int(y) if y else None, int(mo), int(da)])
    if not dates:
        return None
    start, end = dates[0], dates[-1]
    if end[0] is None:
        end[0] = start[0] or ref_year
    if start[0] is None:
        start[0] = end[0] - 1 if end[0] and (start[1], start[2]) > (end[1], end[2]) else end[0]
    if not start[0]:
        return None
    try:
        s, e = date(*start), date(*end)
    except ValueError:
        return None
    if e < s:
        e = s
    return {"start": s.isoformat(), "end": e.isoformat()}


def make_item(source, source_id, title, open_at, url, place="", image="", label="", period=None):
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
        "period": period,  # {"start","end"} 또는 None
    }
