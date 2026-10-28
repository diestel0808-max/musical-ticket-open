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


# 요청 하나의 최대 대기(초). 매일 수집은 넉넉히, 사이트의 「지금 업데이트」(60초 제한)는 api/refresh.py에서 줄인다
TIMEOUT = 20


def http(url, data=None, json_body=None, headers=None, timeout=None):
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
    with urllib.request.urlopen(req, timeout=timeout or TIMEOUT) as r:
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


def _dates_to_period(window, ref_year):
    """window 안의 날짜들을 처음~마지막 범위로 묶는다. 연도가 빠진 날짜는 앞뒤 날짜·ref_year로 채운다."""
    dates = []
    for d in DATE_IN_TEXT.finditer(window):
        y, mo, da = (d.group(1), d.group(2), d.group(3)) if d.group(2) else (d.group(4), d.group(5), d.group(6))
        dates.append([int(y) if y else None, int(mo), int(da)])
    if not dates:
        return None
    start, end = dates[0], dates[-1]
    later = lambda a, b: (a[1], a[2]) > (b[1], b[2])  # noqa: E731  월/일만 비교
    if start[0] is None and end[0] is not None:
        start[0] = end[0] - 1 if later(start, end) else end[0]
    if start[0] is None:
        start[0] = ref_year
    if end[0] is None and start[0]:
        end[0] = start[0] + 1 if later(start, end) else start[0]
    if not start[0]:
        return None
    try:
        s, e = date(*start), date(*end)
    except ValueError:
        return None
    return {"start": s.isoformat(), "end": max(s, e).isoformat()}


def _line_after(text, pos, look=120):
    """pos부터 같은 줄에서 '※'·'공연시간'·'관람' 안내가 나오기 전까지."""
    return re.split(r"[\r\n※]|공연\s*시간|관람", text[pos: pos + look])[0]


def parse_period(text, ref_year=None):
    """'공연 기간 : 2026년 10월 09일(금) ~ 2027년 01월 03일(일)' 같은 문구에서 전체 공연기간을 뽑는다.

    반환: {"start": "YYYY-MM-DD", "end": "YYYY-MM-DD"} 또는 None
    """
    m = PERIOD_KEY.search(text or "")
    return _dates_to_period(_line_after(text, m.end()), ref_year) if m else None


# 회차: 2차 / 마지막 / 프리뷰 / 첫. 낱말 회차는 '우리의 마지막 순간들'처럼 작품명에도 쓰이므로
# 뒤에 '티켓/오픈'이 오거나 문자열 끝일 때만 회차로 본다.
ROUND = re.compile(r"(\d{1,2})\s*차(?!\s*[가-힣])|(\d{1,2})\s*차(?=\s*(?:티켓|오픈))|(마지막|프리뷰|첫)(?=\s*(?:티켓|오픈|$))")
# '2차 티켓 오픈 공연 기간 :', '프리뷰 오픈 기간 :', '티켓오픈 공연 기간:' (※ '티켓오픈 일정'은 판매 시각이라 제외)
ROUND_PERIOD_KEY = re.compile(
    r"(?:((?:\d{1,2})\s*차|마지막|프리뷰|첫)\s*)?(티켓\s*)?오픈\s*(?:공연\s*)?기간\s*[:：]?"
)


def norm_round(s):
    m = ROUND.search(s or "")
    if not m:
        return ""
    num = m.group(1) or m.group(2)
    return f"{int(num)}차" if num else m.group(3)


def parse_round_period(text, ref_year=None):
    """공지 본문에서 (회차, 이번 회차로 열리는 공연 기간)을 찾는다. 없으면 ("", None)."""
    for m in ROUND_PERIOD_KEY.finditer(text or ""):
        if not (m.group(1) or m.group(2)):  # '오픈 기간'만 있는 건 회차/티켓 단서가 없어 건너뜀
            continue
        line = _line_after(text, m.end())
        period = _dates_to_period(line, ref_year)
        if not period:  # 제목만 있고 날짜는 다음 줄에 있는 경우
            nxt = text[m.end():].split("\n", 2)
            period = _dates_to_period(nxt[1], ref_year) if len(nxt) > 1 else None
        if period:
            return norm_round(m.group(1) or ""), period
    return "", None


# 어린이·가족 뮤지컬은 제외한다(NOL 화면의 '뮤지컬' 탭 기준에 맞춤)
KIDS = re.compile(
    r"어린이|가족|아동|키즈|유아|아기|베이비"
    r"|베베핀|핑크퐁|뽀로로|타요|티니핑|호기심딱지|브레드이발소|신비아파트"  # 제목에 '어린이'가 없는 아동 브랜드
)


def is_kids(title):
    return bool(KIDS.search(title or ""))


def make_item(source, source_id, title, open_at, url, place="", image="", label="", period=None,
              round_="", round_period=None):
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
        "period": period,  # 전체 공연기간 {"start","end"} 또는 None
        "round": round_ or norm_round(title),  # 2차/마지막/프리뷰/첫 또는 ""
        "roundPeriod": round_period,  # 이번 회차로 열리는 공연 기간 또는 None
    }
