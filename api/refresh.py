"""Vercel 함수: POST /api/refresh

배포에 들어 있는 data/items.json을 기준으로 지금 다시 수집해 결과를 돌려준다.
환경변수 GITHUB_TOKEN이 있으면 결과를 레포의 data/items.json에 커밋한다
(→ Vercel이 자동 재배포해서 다른 기기에도 반영).
"""
import base64
import json
import os
import sys
import urllib.error
import urllib.request
from datetime import datetime, timedelta
from http.server import BaseHTTPRequestHandler
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from scraper.main import DATA, collect, load  # noqa: E402

REPO = os.environ.get("GITHUB_REPO", "diestel0808-max/musical-ticket-open")
CONTENTS_API = f"https://api.github.com/repos/{REPO}/contents/data/items.json"
COOLDOWN = timedelta(minutes=10)


def github(method, url, body=None):
    req = urllib.request.Request(
        url,
        method=method,
        data=json.dumps(body).encode() if body is not None else None,
        headers={
            "Authorization": f"Bearer {os.environ['GITHUB_TOKEN']}",
            "Accept": "application/vnd.github+json",
            "User-Agent": "musical-ticket-open",
        },
    )
    with urllib.request.urlopen(req, timeout=20) as r:
        return json.loads(r.read())


def refresh():
    """(응답 dict) 수집하고, 가능하면 레포에 저장한다."""
    token = os.environ.get("GITHUB_TOKEN")
    base, sha = None, None
    if token:
        # 배포본보다 레포 최신본이 새로울 수 있으니(버튼을 연달아 누른 경우 등) 레포 것을 기준으로
        try:
            cur = github("GET", CONTENTS_API)
            sha = cur["sha"]
            base = json.loads(base64.b64decode(cur["content"]).decode("utf-8"))
        except Exception as e:
            print("레포 데이터 읽기 실패:", e)
    if base is None:
        base = load(DATA)

    prev_at = base.get("updatedAt")
    db, new_items = collect(base)
    result = {"newCount": len(new_items), "saved": False, "reason": "", "db": db}

    if not token:
        result["reason"] = "저장 설정 없음(GITHUB_TOKEN)"
    elif not sha:
        result["reason"] = "레포 데이터를 읽지 못함"
    elif prev_at and datetime.fromisoformat(db["updatedAt"]) - datetime.fromisoformat(prev_at) < COOLDOWN:
        result["reason"] = "10분 안에 이미 저장됨"
    else:
        body = json.dumps(db, ensure_ascii=False, indent=1)
        try:
            github("PUT", CONTENTS_API, {
                "message": f"데이터 갱신(수동) {db['updatedAt'][:16].replace('T', ' ')}",
                "content": base64.b64encode(body.encode("utf-8")).decode(),
                "sha": sha,
            })
            result["saved"] = True
        except urllib.error.HTTPError as e:
            result["reason"] = f"저장 실패({e.code})"
    return result


class handler(BaseHTTPRequestHandler):
    def do_POST(self):
        try:
            status, payload = 200, refresh()
        except Exception as e:
            status, payload = 500, {"error": str(e)[:300]}
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        self.send_response(405)
        self.send_header("Allow", "POST")
        self.end_headers()
