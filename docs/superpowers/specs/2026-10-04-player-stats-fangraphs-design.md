# 선수 통계 페이지 개편 설계 (팬그래프 리더보드 방식)

- 작성: 2026-10-04, bstats 화면 세션
- 대상 화면: `dashboard_js/pages/player-stats.html` (https://bstats.pages.dev/pages/player-stats)
- 참고 화면: FanGraphs Major League Leaders → Player Stats
- 앞선 작업: 팀 통계 개편(`2026-10-03-team-stats-fangraphs-design.md`, 운영 배포 7717e86). 그 부품을 같이 씁니다.
- 상태: 설계 승인됨(evan).

## 1. 목적과 범위

선수 통계 페이지를 팀 통계와 같은 틀(묶음 탭·고급 지표·지수 색·설명 창·CSV·주소 저장)로 바꿉니다. 팀 통계·선수 통계는 따로 둡니다(한 페이지로 합치지 않음).

- 지금 데이터만 씁니다. 새 API 는 없습니다.
- 기간 조회(선수별 기간 기록)는 이번 범위에서 뺍니다. API 가 생기면 붙입니다.

## 2. 화면 구성

- 머리: 제목 "선수 통계", 설명 한 줄(점선 밑줄 안내는 팀 통계와 같음).
- 위쪽 탭(밑줄형): **타격 | 투구**
- 묶음 버튼(사각형): 타격 **대시보드 | 표준 | 고급 | 상황 | 사용자 지정**, 투구 **대시보드 | 표준 | 고급 | 사용자 지정**
- 고르개 한 줄: 시즌, 팀, 포지션(타격만), 최소
  - 최소(타격): 규정 이상(기본) · 전체 · 50 · 100 · 200 · 300타석
  - 최소(투구): 규정 이상(기본) · 전체 · 10 · 30 · 50 · 100이닝
  - 포지션: 받은 선수 기록의 `position` 값(포수·내야수·외야수 등)으로 채웁니다.
- 표 카드
  - 제목: "타자 (2026, 규정 이상 62명)" 처럼 시즌·조건·인원
  - 제목 줄 오른쪽: CSV · 링크 복사(마우스를 올리면 "지금 보는 화면 그대로 열리는 주소를 복사합니다.")
  - 칸: # · 이름(선수 분석으로 가는 링크) · 팀 · 지표. #·이름은 가로 스크롤해도 고정.
  - 맨 아래 리그 평균 행(리그 전체 기준, 고른 조건과 무관). 정렬해도 맨 아래.
  - 50명씩 쪽 넘기기. 한 쪽 인원 50 · 100 · 전체.
- 팀 통계와 같은 것: 지수 칸만 색(좋을수록 빨강, 나쁠수록 파랑), 머리글 점선 밑줄 = 올리면 설명·누르면 정렬, 링크 복사 = 주소에 탭·묶음·시즌·팀·포지션·최소·정렬·쪽·칸 저장, CSV = 고른 조건의 전체 선수(쪽과 무관)·지금 보이는 칸·정렬 순서.

### 2.1 묶음별 칸

| 묶음 | 칸 |
|---|---|
| 타격 대시보드 | G PA HR R RBI BB% K% ISO BABIP AVG OBP SLG wOBA wRC+ |
| 타격 표준 | G PA AB H 1B 2B 3B HR R RBI BB IBB SO HBP SF SH GDP AVG |
| 타격 고급 | PA BB% K% BB/K AVG OBP SLG OPS ISO BABIP wOBA wRAA wRC wRC+ OPS+ |
| 타격 상황 | PA 득점권 대타 결승타 멀티히트 XR GPA P/PA |
| 투구 대시보드 | W L SV G GS IP K/9 BB/9 HR/9 BABIP LOB% ERA FIP |
| 투구 표준 | W L ERA G GS CG SHO SV HLD BS IP TBF H R ER HR BB IBB HBP WP BK SO |
| 투구 고급 | K/9 BB/9 K/BB HR/9 K% BB% K−BB% AVG WHIP BABIP LOB% ERA- FIP- FIP E−F |

선수 G 는 선수 본인의 출장 경기 수입니다(팀 통계의 G 와 뜻이 다름 — 설명 문구로 구분).

## 3. 지표와 계산

팀 통계와 같은 식(`js/stats/metrics.js`)에 "팀 합계" 대신 "선수 한 명의 기록"을 넣습니다.

| 지표 | 계산 | 시작 |
|---|---|---|
| AVG·OBP·SLG·OPS·ISO·BABIP·K%·BB%·BB/K | 성분에서 다시 계산 | 1982 |
| wOBA·wRAA·wRC·wRC+ | 화면에서 모든 선수 계산(선수 wRC+ 와 같은 식: 반 구장 보정, L = 리그 득점/PA). 서버 값은 50타석 이상만 있지만 같은 식이라 같은 값 | 2008 |
| OPS+·ERA-·FIP- | 선수 소속팀(`player_team`) 홈구장의 반 구장 보정. 2007 이전은 보정 없음 | 1982 |
| FIP·LOB%·피안타율·BABIP(투수)·K−BB%·E−F | 성분에서 계산. FIP 상수는 그해 리그 합 | 1982 |
| 득점권·대타·결승타·멀티히트·XR·GPA·P/PA | 공식 기록 값 그대로(`runners_in_scoring_position`, `pinch_hit_batting_average`, `gw_rbi`, `multi_hits`, `extended_runs`, `gross_production_average`, `p_pa`) | 공식 기록 |

리그 기준값(리그 wOBA·L·리그 OBP/SLG·리그 ERA·cFIP)은 그 시즌 **리그 전체 선수**의 합으로 셉니다(팀 통계와 같은 값).

### 3.1 규정 이상

- KBO 규정: 타석 ≥ 소속팀 경기 수 × 3.1(파이썬식 반올림 — 서버 `pyRound` 와 같게), 이닝 ≥ 소속팀 경기 수 × 1.
- 소속팀 경기 수: 순위표(`team_season_rank`, 올해는 `/standings` 실시간). 팀 통계와 같은 순위 자료입니다.
- 순위표를 못 받으면 `/stats/regulation` 의 시즌 하나짜리 규정(`qual_pa`, `qual_ip`)을 쓰고 표 위에 알립니다.

### 3.2 리그 평균 행

- 비율 지표: 리그 전체 합으로 계산.
- 누적 숫자(G·PA·HR 등): '-' (선수마다 출장이 달라 선수 평균은 뜻이 없음).
- 상황 묶음의 비율(득점권·대타·GPA·P/PA): 성분이 없어 '-'. 결승타·멀티히트·XR 도 '-'.
- 지수 칸: 100.

### 3.3 알려진 한계

- 트레이드된 선수는 공식 기록이 한 줄이라 마지막 팀으로만 보이고, 구장 보정도 마지막 팀 홈구장 기준입니다(서버 선수 wRC+ 와 같은 방식).

## 4. 데이터 받기

새 API 없음. 팀 통계와 같은 주소·모양이라 엣지 캐시를 같이 씁니다.

| 언제 | 주소 |
|---|---|
| 페이지를 열 때 | `/stats/seasons`, `/db/table/{kbo_woba_weights_by_season, self_park_factor, team_stadium_by_season, team_season_rank}?limit=500`(세션 저장) |
| 시즌을 바꿀 때 | `/stats/batters?season=Y&limit=2000&min_pa=0`, `/stats/pitchers?season=Y&limit=2000&min_ip=0` |
| 올해일 때 | `/standings` |
| 순위표 실패 때만 | `/stats/regulation` |

- 거르기·정렬·쪽 넘기기는 화면에서 합니다(서버를 다시 부르지 않음).
- 지금 페이지가 부르는 `/teams` 는 빼고, 팀 목록은 받은 기록에서 만듭니다.

## 5. 예외

- 2007 이전: wOBA·wRC+ '-', OPS+·ERA-·FIP- 보정 없이. 타격 대시보드에 OPS+ 를 wRC+ 뒤에 붙이고 기본 정렬 OPS+(팀 통계와 같음).
- 조건에 맞는 선수가 없으면 "조건에 맞는 선수가 없습니다" 와 리그 평균 행.
- 응답 이상(오류·빈 목록)은 표 위 알림(팀 통계와 같음).
- 기본 정렬: 타격 wRC+ 높은 순(옛 시즌 OPS+), 투구 ERA 낮은 순, 상황 묶음은 득점권 높은 순.

## 6. 파일 구조

| 파일 | 하는 일 |
|---|---|
| `dashboard_js/js/stats/metrics.js` | 공용 계산(팀 통계에서 옮김) + 선수용 함수(선수 행 만들기·규정 판정) |
| `dashboard_js/js/stats/columns.js` | 공용 칸 정의(옮김) + 선수 전용 칸(이름·포지션·상황 묶음)·선수 묶음 |
| `dashboard_js/js/stats/data.js` | 공용 데이터 받기(옮김) + `/stats/regulation` |
| `dashboard_js/js/stats/table.js` | 공용 표(옮김). 앞 칸 구성을 받게 넓힘(팀: #·팀 / 선수: #·이름·팀), 쪽 나누기 |
| `dashboard_js/js/team-stats/record.js`, `page.js` | 팀 전용 그대로(공용 경로만 바꿈) |
| `dashboard_js/js/player-stats/page.js` | 선수 페이지 조립(고르개·규정·쪽·주소) |
| `dashboard_js/pages/player-stats.html` | 새로 씀 |
| `dashboard_js/pages/team-stats.html` | `<script>` 경로만 바꿈 |

모듈 틀은 팀 통계와 같습니다(전역 `window.TeamStats.<이름>`, Node 는 vm 으로 불러옴). 전역 이름은 그대로 `TeamStats` 를 씁니다(옮기면서 이름까지 바꾸면 팀 통계 위험이 커짐).

## 7. 검증

- Node(저장소 밖 `C:/tmp/bstats-team-stats-check/tests/`): 팀 통계 78개를 옮긴 경로로 그대로 통과. 추가:
  1. 50타석 이상 선수의 화면 wOBA·wRC+ = 서버 값(반올림 오차 안)
  2. 2025 최종 규정타석 이상 인원(팀별 144 × 3.1 = 446타석)이 공식 기준과 맞음
  3. 규정 판정의 파이썬식 반올림(.5 짝수)
  4. 쪽 나누기·CSV 가 쪽과 무관하게 전체 선수
- 화면 캡처(헤드리스 Edge, 휴대폰은 CDP 390px 흉내): 타격 대시보드·상황·투구 고급·1985·한 팀 고르기·휴대폰. 팀 통계도 옮긴 뒤 다시 캡처해 그대로인지 확인.

## 8. 커밋 순서

1. 공용 폴더로 옮기기(팀 통계 동작 그대로, 테스트 78개 통과, 캡처로 확인)
2. 선수용 계산·칸·표 넓히기
3. 선수 페이지
4. 캡처 확인·수정

push·배포는 매번 evan 허락 뒤에 합니다.
