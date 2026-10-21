# 🎭 뮤지컬 티켓오픈 모아보기

NOL(구 인터파크), 티켓링크, 예스24의 **뮤지컬 티켓오픈 공지**를 매일 아침 모아 한 페이지(목록/캘린더)로 보여주고, 새 소식은 노션 DB에 자동으로 추가합니다.

| 사이트 | 수집 위치 | 뮤지컬 판별 |
|---|---|---|
| NOL | `POST nol.yanolja.com/ticket/display/api/upcoming` | 장르 코드 `01011` |
| 티켓링크 | `GET ticketlink.co.kr/help/getNoticeList?noticeCategoryCode=TICKET_OPEN` | `subCategoryId == 16` 또는 제목에 "뮤지컬" |
| 예스24 | `POST ticket.yes24.com/New/Notice/Ajax/axList.aspx` | 장르 `15457` |

외부 패키지 없이 Python 3.9+ 표준 라이브러리만 씁니다.

## 로컬 실행

```bash
python3 -m scraper.main --dry-run     # 저장 없이 결과만 보기
python3 -m scraper.main --no-notion   # data/items.json 갱신 (노션 제외)
python3 -m http.server 8787           # http://localhost:8787/site/ 에서 확인
```

## 자동 실행 (GitHub Actions + Pages)

`.github/workflows/update.yml`이 **매일 08:00 KST**에 수집 → `data/items.json` 커밋 → 노션 추가 → Pages 배포를 합니다.

1. 레포 Settings → Pages → Source를 **GitHub Actions**로 설정
2. 레포 Settings → Secrets and variables → Actions에 추가
   - `NOTION_TOKEN`: https://www.notion.so/profile/integrations 에서 만든 내부 통합의 시크릿
   - `NOTION_DB_ID`: `a1943851769c477da6df614bfb540cd7` (🎭 뮤지컬 티켓오픈 DB)
3. 노션에서 DB 페이지 우측 상단 `···` → **연결(Connections)** → 만든 통합 추가
4. Actions 탭에서 「수집 및 배포」를 한 번 수동 실행해 확인

노션 시크릿이 없으면 노션 단계만 건너뜁니다. 노션을 처음 연결하면 **오픈일이 지나지 않은 항목만** 올라갑니다.

### 노션 알림 받기
- DB 우측 상단 ⚡ 자동화 → 트리거 「페이지 추가됨」 → 동작 「알림 보내기」(플랜에 따라 유료일 수 있음)
- 또는 `오픈일시` 기준 캘린더 보기를 만들어 Notion Calendar에서 함께 보기

## Vercel로 배포하려면
수집은 그대로 GitHub Actions가 하고, Vercel은 정적 사이트만 호스팅합니다(`vercel.json` 포함).
Vercel에서 이 레포를 Import하면 끝입니다. Actions가 매일 데이터를 커밋할 때마다 Vercel이 자동으로 다시 배포합니다.
(이 경우 Pages는 꺼도 됩니다.)
