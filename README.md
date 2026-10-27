# 🎭 뮤지컬 티켓오픈 모아보기

NOL(구 인터파크), 티켓링크, 예스24, 멜론티켓의 **뮤지컬 티켓오픈 공지**를 매일 아침 모아 한 페이지(목록/캘린더)로 보여줍니다. 각 소식에는 **몇 차 티켓오픈인지와 이번 회차로 열리는 공연 기간**(예: `2차 티켓오픈 26.11.17 ~ 26.12.06`, 복사 버튼 포함)이 함께 나옵니다. 회차 기간이 공지에 없으면(NOL은 공지 상세가 없어 항상) 전체 공연기간으로 대신합니다.

| 사이트 | 수집 위치 | 뮤지컬 판별 | 회차 / 기간 |
|---|---|---|---|
| NOL | `POST nol.yanolja.com/ticket/display/api/upcoming` | 장르 코드 `01011` | 회차는 `open_name`, 기간은 전체 공연기간만 |
| 티켓링크 | `GET ticketlink.co.kr/help/getNoticeList?noticeCategoryCode=TICKET_OPEN` | `subCategoryId == 16` 또는 제목에 "뮤지컬" | 공지 본문의 "N차 티켓 오픈 (공연) 기간" 파싱 |
| 예스24 | `POST ticket.yes24.com/New/Notice/Ajax/axList.aspx` | 장르 `15457` | 상세(`axRead.aspx`) 본문 파싱, 공지당 1회 |
| 멜론티켓 | `POST ticket.melon.com/csoon/ajax/listTicketOpen.htm` (뮤지컬/연극 탭) | 공연 상품 페이지의 장르가 "뮤지컬" | 공지 상세 본문 파싱 |

외부 패키지 없이 Python 3.9+ 표준 라이브러리만 씁니다.

## 구성
- `scraper/` — 수집기. `python3 -m scraper.main`이 `data/items.json`을 갱신
- `site/index.html` — 정적 페이지(빌드 단계 없음)
- `api/refresh.py` — Vercel 함수. 사이트의 「↻ 지금 업데이트」 버튼이 호출
- `.github/workflows/update.yml` — 매일 10:00 KST(실제로는 1~3시간 늦게 시작되기도 함) 수집 후 커밋 → Vercel 자동 재배포
- `vercel.json` — `site/` + `data/`를 `public/`으로 복사해 서빙

## 로컬 실행
```bash
python3 -m scraper.main --dry-run   # 저장 없이 결과만 보기
python3 -m scraper.main             # data/items.json 갱신
python3 -m http.server 8787         # http://localhost:8787/site/ (업데이트 버튼은 Vercel에서만 동작)
```

## Vercel 배포
1. https://vercel.com/new 에서 이 레포를 Import → Framework Preset **Other** → Deploy
2. (업데이트 버튼 결과를 저장하려면) GitHub fine-grained 토큰을 만들기 — 대상: 이 레포만, 권한: **Contents: Read and write**
3. Vercel 프로젝트 → Settings → Environment Variables에 `GITHUB_TOKEN` 추가 → Deployments에서 Redeploy
4. Vercel이 GitHub 푸시를 놓치는 경우가 있어 Deploy Hook을 씁니다. Vercel Settings → Git → Deploy Hooks의 `daily`(main) 주소를
   - GitHub 레포 Settings → Secrets and variables → Actions에 `VERCEL_DEPLOY_HOOK`으로
   - Vercel Settings → Environment Variables에도 `VERCEL_DEPLOY_HOOK`으로 등록

토큰이 없으면 버튼을 누른 사람 화면에만 최신 결과가 반영되고, 저장은 매일 아침 자동 수집 때 됩니다.
토큰이 있으면 버튼 결과가 레포에 커밋되고, Vercel이 1~2분 뒤 재배포해 모든 기기에 반영됩니다(10분 안에 다시 누르면 저장은 건너뜀).
