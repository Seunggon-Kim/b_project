# 선수 분석 무브먼트 카드 설계 (Savant Movement Profile 참고)

- 작성: 2026-10-04, bstats 선수 분석 세션
- 대상: `dashboard_js/pages/player-analytics.html` 머리 카드 줄
- 참고: Baseball Savant 선수 페이지 `#pitch-distribution-mini-container`(Movement Profile (Induced Break), 연도 고르기)
- 앞선 작업: `2026-10-04-player-analytics-fangraphs-header-design.md`(헤더·Quick Look·프로필·시즌 타일)
- 상태: 설계 승인됨(evan).

## 1. 범위

- 1군 투수 화면의 카드 줄에 **무브먼트 카드**를 더합니다. 순서는 Quick Look · 프로필(+시즌 타일) · 무브먼트이고, 세 칸 폭이 같습니다.
- 타자와 퓨처스(투구 추적 데이터 없음) 화면은 지금처럼 두 칸입니다.
- 빼는 것: 팔 각도, 리그 평균 원(리그 평균을 주는 API 가 없음).
- 그대로 두는 것: 아래쪽 기존 Movement Profile(직사각 캔버스) 카드, Pitch Usage 카드.

## 2. 카드

- 제목줄: `무브먼트 (Induced Break)` 와 오른쪽 연도 고르기(select).
  - 연도 목록: 그 선수의 1군 투수 기록 시즌(`pitcher_seasons`) 중 **2016년 이후**, 최신순. 처음 값은 가장 최근 시즌입니다.
    - 근거(2026-10-04 확인, evan 결정): 투구 추적(무브먼트)은 2015년 이전 0구, 2016년 일부(양현종 59%·구창모 76%), 2017년부터 93% 이상.
- 그림(SVG, 400×400 viewBox)
  - 원형 배경에 15·30·45·60cm 고리(30·60 은 실선, 15·45 는 점선), 가로·세로 축, 고리 눈금 `30`·`60`.
  - 공 하나하나를 구종 색 작은 점으로 찍습니다(반투명). 원 밖은 잘립니다.
  - 구종별 평균 위치에 테두리 있는 큰 원. 마우스를 올리면 `구종 비율 · 수직 · 수평` 이 보입니다(SVG title).
- 그림 아래 두 줄:
  - `포수 시점 · 수평 +는 1루 쪽 · 수직 +는 위`
  - 추적 비율(임시 문구): `공 2,558개 추적 (정규시즌 2,536구 대비 100%)` 아래에 보조 줄 `추적 공에는 시범경기·포스트시즌이 섞일 수 있습니다.` 를 둡니다. DB 세션이 arsenal 을 정규시즌만 주게 고치면 보조 줄을 뺍니다. 전체 투구는 그 시즌 `pitcher_seasons` 의 `number_of_pitchers` 합. 모르면 `공 N개 추적`. 100% 를 넘으면 100% 로 씁니다(evan 결정: 모든 연도에 표시).
- 구종 표: 색 점 · 구종 · 비율 · 구속(km/h) · 수직(cm) · 수평(cm). 많이 던진 순.
- 그 시즌 데이터가 없으면 `이 시즌은 투구 추적 데이터가 없습니다.`
- 단위는 cm(아래 기존 카드와 같음). 응답 `pfx_x`·`pfx_z` 는 인치라 2.54 를 곱합니다. 시점은 포수 시점(기존 카드와 같은 방향).
- 구종 색은 기존 카드의 표(`PITCH_COLORS`)와 같습니다. 표에 없는 구종은 `#3b82f6`.

## 3. 데이터

- 기존 API `/players/{id}/arsenal` 에 `?season=YYYY` 를 붙입니다(서버는 이미 받음, 기본값 2026). `js/api.js` 의 `getPitchArsenal(playerId, season)` 에 선택 인자를 덧붙입니다. 인자가 없으면 지금과 같습니다.
- 페이지 안에서 `선수:시즌` 별로 결과를 저장해 같은 시즌을 다시 부르지 않습니다. 빈 결과(오류 포함)는 저장하지 않습니다.
- 선수·시즌을 빨리 바꿔도 늦게 온 응답이 화면을 덮지 않게 순번(token)으로 막습니다.
- 서버는 `play_by_play` 를 `pitcher_ID` 인덱스와 날짜 범위로 읽습니다. 한 번에 선수 한 명의 한 시즌(수백~2,500구)입니다.
- 계보: 페이지가 부르는 주소가 바뀌므로 `py scripts/build_lineage.py` → `py -m pytest tests` 를 다시 돌립니다. 계보 JSON 내용이 바뀌면 함께 커밋하고 화면 세션에 알립니다.

## 4. 배치

- 3칸 배치는 1281px 이상에서만 씁니다. 1025~1280px 은 Quick Look 2칸·프로필 1칸, 무브먼트는 아래 줄 전폭입니다(표가 잘려서). 1024px 이하는 모두 한 칸씩 쌓습니다.
- 3칸일 때 그리드에 `pa-3col` 클래스를 붙여 Quick Look 을 1칸으로 줄입니다. 세 카드 높이는 같습니다(stretch).
- 1,024px 이하에서는 세 카드가 모두 전체 폭으로 위아래로 쌓입니다.

## 5. 파일

| 파일 | 할 일 |
|---|---|
| `dashboard_js/js/player-analytics/movement.js` (새) | 순수 함수: `summarize`, `seasonsFor`, `svgHtml`, `legendHtml`, `bodyHtml`. 전역 `PlayerAnalytics.movement` |
| `dashboard_js/css/player-analytics.css` | 3칸 배치·카드·SVG·표 규칙 덧붙임 |
| `dashboard_js/pages/player-analytics.html` | 카드 마크업, 스크립트 1개, 카드 켜기·끄기·불러오기 |
| `dashboard_js/js/api.js` | `getPitchArsenal` 에 선택 인자 `season` 덧붙임(기존 동작 그대로) |

공용 `js/stats/*`·`css/stats.css`·`css/style.css` 는 고치지 않습니다.

## 6. 검증

- Node 시험(`C:/tmp/bstats-player-analytics-check/tests`): 요약(평균·비율·구속 0/빈 값 제외·무브먼트 빈 공 제외·순서·색), 연도 목록, SVG 점·평균 원 수·좌표·이스케이프, 표 글자, 빈 데이터.
- 화면 PNG: 구창모(65933) 올해·과거 시즌, 타자(76232) 2칸 그대로, 퓨처스 2칸, 다크 모드, 휴대폰.
- push·배포는 evan 허락 뒤. 배포 전 `git status --short dashboard_js`·`git log origin/main..main` 에 남의 작업이 있으면 화면 세션에 먼저 알립니다.
