"""일회성 진단: 장르 확인에서 KOPIS가 실제로 무엇을 돌려주는지 data/kopis_debug.json에 남긴다."""
import json
import os
import traceback
from datetime import date, timedelta
from urllib.parse import urlencode

from .common import http
from .ongoing import API

key = os.environ["KOPIS_KEY"]
out = []
for name, around in [("우리의 마지막 순간들", "2026-11-13"), ("스위니토드", "2026-12-01"), ("오페라의 유령", "2026-12-22"),
                     ("해밀턴", "2027-01-01"), ("아나키스트", "2026-10-07"), ("청춘사운드콘서트", "2026-12-05")]:
    a = date.fromisoformat(around)
    for st in (a - timedelta(days=30), a):
        q = dict(service=key, stdate=st.strftime("%Y%m%d"), eddate=(st + timedelta(days=30)).strftime("%Y%m%d"),
                 cpage=1, rows=100, shprfnm=name)
        try:
            body = http(f"{API}?{urlencode(q)}")
            out.append({"name": name, "from": str(st), "len": len(body), "head": body[:700]})
        except Exception as e:
            out.append({"name": name, "from": str(st), "error": repr(e), "tb": traceback.format_exc()[-500:]})
json.dump(out, open("data/kopis_debug.json", "w"), ensure_ascii=False, indent=1)
