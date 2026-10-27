"""티켓오픈 장르 검증: 예매처가 붙인 '뮤지컬' 분류를 그대로 믿지 않고 한 번 더 확인한다.

예매처는 가끔 콘서트·연극을 뮤지컬 분류에 올린다(예: 티켓링크의 「청춘사운드콘서트 - 대구」는 밴드 공연인데
뮤지컬 분류). 그래서 새 소식마다 두 단계로 확인한다.

1. KOPIS(공연예술통합전산망) 대조: 같은 이름·기간으로 등록된 공연의 장르를 본다.
   - 뮤지컬로 등록돼 있으면 통과
   - 등록돼 있는데 뮤지컬이 아니면(대중음악·연극 등) 제외
   - 아직 등록 전이면(공연 직전에 등록되는 경우가 많음) 2단계로 판단하고, 오픈 시각 전까지 매일 다시 대조
2. 제목 규칙: 콘서트·갈라·팬미팅·토크 공연은 제외(낭독공연은 포함)

판정 결과는 항목의 genreCheck에 남기고, 제외한 소식은 items.json의 excluded에 사유와 함께 옮겨
다음 수집 때 다시 들어오지 않게 한다.
"""
import os
import re
from datetime import date, timedelta

from .common import NOT_MUSICAL, now_kst
from .ongoing import kdate, kopis, text

# 제목에서 작품 이름만 남기기: [단독]/[지역] 머리말, '뮤지컬', 회차, ' - 지역' 꼬리 등을 뗀다
BRACKET = re.compile(r"[<〈《「\[]\s*([^>〉》」\]]+?)\s*[>〉》」\]]")


def work_name(title):
    t = re.sub(r"^(\s*\[[^\]]*\]\s*)+", "", title)
    m = BRACKET.search(t)
    if m:
        t = m.group(1)
    else:
        t = re.sub(r"\s+-\s+\S+(\s*공연)?$", "", t)  # '… - 대구', '… - 부산 공연'
        t = re.sub(r"\d+\s*차|마지막|프리뷰|티켓\s*오픈", " ", t)
    t = re.sub(r"뮤지컬|^\s*20\d\d\s+", " ", t)  # '뮤지컬', 앞의 연도
    return re.sub(r"\s+", " ", t).strip()


def norm(s):
    return re.sub(r"[\s\W_]+", "", s or "").lower()


def kopis_genres(key, name, around):
    """KOPIS에서 이름이 같은 공연들의 장르 집합. KOPIS 검색 기간은 한 번에 31일까지라 공연 시작일 앞뒤로 찾는다."""
    want = norm(name)
    if len(want) < 2:
        return set()
    genres = set()
    for start in (around - timedelta(days=30), around):
        root = kopis(service=key, stdate=start.strftime("%Y%m%d"), eddate=(start + timedelta(days=30)).strftime("%Y%m%d"),
                     cpage=1, rows=100, shprfnm=name)
        for row in root.findall("./db"):
            got = norm(re.sub(r"\s*\[[^\]]+\]\s*$", "", text(row, "prfnm")))
            if got and (want in got or got in want):
                genres.add(text(row, "genrenm"))
    return genres


def check(item, key):
    """→ ('ok' | 'reject' | 'unknown', 이유)"""
    if NOT_MUSICAL.search(item["title"]):
        return "reject", "제목상 콘서트·갈라·팬미팅·토크"
    if not key:
        return "unknown", "KOPIS 키 없음"
    p = item.get("period") or item.get("roundPeriod") or {}
    around = date.fromisoformat(p["start"]) if p.get("start") else date.fromisoformat(item["openAt"][:10]) + timedelta(days=14)
    genres = kopis_genres(key, work_name(item["title"]), around)
    if not genres:
        return "unknown", "KOPIS 미등록"
    if "뮤지컬" in genres:
        return "ok", "KOPIS 장르: 뮤지컬"
    return "reject", f"KOPIS 장르: {', '.join(sorted(genres))}"


def verify(db, by_id, log=print):
    """확인이 필요한 항목(새 소식, 아직 KOPIS 미등록인 오픈 전 소식)을 검증하고 제외 대상은 excluded로 옮긴다."""
    key = os.environ.get("KOPIS_KEY")
    now = now_kst().isoformat(timespec="minutes")
    excluded = db.setdefault("excluded", [])
    checked = rejected = 0
    for it in list(by_id.values()):
        g = it.get("genreCheck") or {}
        recheck = g.get("status") == "unknown" and key and (it.get("openAt") or "") >= now and g.get("at", "")[:10] < now[:10]
        if g and not recheck:
            continue
        try:
            status, reason = check(it, key)
        except Exception as e:  # KOPIS가 잠깐 안 되면 그대로 두고 다음 수집 때 다시
            log(f"  장르 확인 실패 {it['title']}: {e}")
            continue
        checked += 1
        it["genreCheck"] = {"status": status, "reason": reason, "at": now}
        if status == "reject":
            rejected += 1
            del by_id[it["id"]]
            excluded.append({"id": it["id"], "source": it["source"], "title": it["title"], "openAt": it.get("openAt"),
                             "reason": reason, "at": now})
            log(f"  제외: {it['title']} ({reason})")
    if checked:
        log(f"[장르 확인] {checked}건 확인, {rejected}건 제외")
