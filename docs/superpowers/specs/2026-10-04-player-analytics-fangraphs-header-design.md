# 선수 분석 머리 부분 개편 설계 (팬그래프 선수 페이지 방식)

- 작성: 2026-10-04, bstats 선수 분석 세션
- 대상 화면: `dashboard_js/pages/player-analytics.html` (https://bstats.pages.dev/pages/player-analytics?id=65933)
- 참고 화면: FanGraphs 선수 페이지(https://www.fangraphs.com/players/jacob-misiorowski/31623/stats/pitching)
  - 레퍼런스 1: 헤더 `header__player-info`(이름·팀 / Age·Bats/Throws·키몸무게 / DOB(나이) / 포지션)
  - 레퍼런스 2: 헤더 아래 카드 줄 `module-card`(Quick Look 세로 표: Season·Team·Level·지표 × 예측·올해·통산)
- 상태: 설계 승인됨(evan).

## 1. 목적과 범위

선수 분석 페이지의 **헤더와 그 아래 카드 줄(상세 프로필·시즌별 성적)** 만 팬그래프 모양으로 바꿉니다.

- 뉴스 카드는 만들지 않습니다(수집 안 함).
- 예측치(팬그래프 Steamer·FGDC) 칸은 없습니다.
- 새 API 는 없습니다. 페이지가 부르는 주소가 그대로라 계보 파일 작업이 없습니다.
- 아래쪽 Standard·Advanced·구종 카드는 손대지 않습니다.

## 2. 헤더 (레퍼런스 1)

사진 오른쪽에 정보를 한 덩어리로 왼쪽 정렬합니다. 포지션만 오른쪽 끝입니다.

```
[사진] 구창모  No.59   NC [1군 등록]                          [투수]
       나이: 29세   투타: 좌투/좌타   183cm / 85kg
       생년월일: 1997.02.17 (만 29세 7개월)
```

- 첫째 줄: 이름(크게), 등번호(작게, 현역만), 팀 이름과 1군 등록 배지.
- 둘째 줄: 항목 셋을 간격으로 띄웁니다(세로 막대 구분자 없음).
- 셋째 줄: 생년월일과 만 나이(년·개월). 생일이 없으면 줄을 감춥니다.
- 팀 색 배경(`applyTeamTheme`)·은퇴/미등록이면 소속 '-'·등번호와 팀 색 감추기는 그대로입니다.
- 1군·퓨처스가 같은 함수(`renderHeaderBar`)를 씁니다. 이 원칙도 그대로입니다.

## 3. 카드 줄 (레퍼런스 2)

2칸입니다. 왼쪽 **Quick Look**(2/3), 오른쪽 **프로필**(1/3).

- 카드 모양: 맨 위 탭 모양 제목줄(활성 탭 하나), 그 아래 촘촘한 세로 표. 글씨 약 0.85rem, 줄 간격 촘촘.
- 지금 카드의 최소 높이 500px 를 없앱니다. 두 카드는 서로 높이를 같게 합니다. 프로필은 줄이 넷뿐이라 줄을 카드 높이에 맞춰 고르게 벌립니다. 아래에 큰 빈칸(약 300px)이 남지 않게 하려는 것입니다(evan 결정, 2026-10-04. 한때 내용 높이로 줄였다가 되돌림).
- 1,024px 이하에서는 위아래로 쌓습니다(Quick Look 먼저).
- 다크 모드는 사이트 색 변수(`--card-bg`·`--border-color`·`--text-*`)를 따릅니다.

### 3.1 Quick Look 표 (1군)

- 칸: 최근 3시즌 + **통산**. 3시즌 기준은 지금과 같습니다(현역은 올해, 은퇴는 마지막 활동 시즌까지 3년).
- 통산 칸은 굵은 글씨·옅은 배경으로 구분합니다.
- 줄:

| 구분 | 줄 |
|---|---|
| 공통 머리 | 시즌 · 팀 (리그 줄은 두지 않음. 1군·퓨처스 전환이 이미 알려 줌, evan 결정) |
| 투수 | W · L · SV · HLD · G · GS · IP · K% · BB% · ERA · WHIP |
| 타자 | G · PA · HR · R · RBI · BB% · K% · AVG · OBP · SLG · OPS |

- 기록이 없는 시즌은 칸 전체가 '-' 입니다. 통산의 팀 칸은 '-' 입니다.

### 3.2 프로필 카드

- 1군: 연봉 · 입단 계약금 · 입단년도 / 지명순위 · 경력 (통화 규칙은 지금과 같음: 외국인 USD, 국내 KRW)
- 퓨처스: 연봉 · 지명순위 · 출신교
- 프로필 아래 **시즌 타일 2×2**(evan 결정, 2026-10-04): 기록이 있는 가장 최근 시즌의 핵심 숫자 넷을 큰 글씨로 둡니다. 두 카드 높이를 맞출 때 남는 자리를 타일이 채웁니다.
  - 1군 투수 ERA · IP · K% · WHIP, 1군 타자 AVG · OPS · HR · RBI (Quick Look 과 같은 계산)
  - 퓨처스 투수 ERA · IP · SO · G, 퓨처스 타자 AVG · OBP · SLG · HR (응답에 OPS 가 없음). 연도별 기록이 없으면 타일 없음

### 3.3 퓨처스 화면

같은 카드 틀입니다. Quick Look 에 지금의 퓨처스 지표(`FUT_SEASON_METRICS`)를 최근 3시즌으로 넣습니다(리그 줄 없음, 위 안내 배지가 퓨처스임을 알림). 퓨처스 응답은 값 모양이 달라 **통산 칸은 없습니다.** 연도별 기록이 없으면 지금처럼 올 시즌 요약 표를 카드 안에 넣습니다. "2010년부터의 기록입니다" 안내도 카드 안에 둡니다.

## 4. 계산

원칙은 `js/stats/metrics.js` 와 같습니다. 비율을 평균 내지 않고 합계에서 다시 셉니다. 셀 수 없으면 null → '-'.

- 시즌 칸과 통산 칸 모두 같은 함수로 셉니다. 한 시즌에 행이 둘 이상(이적)이면 더하고, 팀 칸은 `A/B` 로 씁니다.
- 공용 함수를 가져다 씁니다(고치지 않음): `ipOuts`, `sumPitching`·`pitchingRates`, `sumBatting`·`battingRates`.
  - 이 함수들은 `player_team` 별로 묶습니다. 선수 한 명을 한 덩어리로 더하려고 행의 `player_team` 을 같은 값으로 바꾼 사본을 넘깁니다.
  - 타자 `single` 칸의 실제 값은 안타(H)입니다(공용 `BAT_SUM` 주석). 그대로 따릅니다.
- 지표:
  - ERA = 자책 × 27 ÷ 아웃, WHIP = (피안타 + 볼넷) × 3 ÷ 아웃, K% = 삼진 ÷ 상대 타자, BB% = 볼넷 ÷ 상대 타자
  - AVG = 안타 ÷ 타수, OBP = (안타 + 볼넷 + 사구) ÷ (타수 + 볼넷 + 사구 + 희생플라이), SLG = 루타 ÷ 타수, OPS = OBP + SLG
  - 타자 K% = 삼진 ÷ 타석, BB% = 볼넷 ÷ 타석
  - W·L·SV·HLD·G·GS·HR·R·RBI·PA 는 합계. G 는 공용 합계 키에 없어 `games` 를 따로 더합니다.
- 표시는 팀·선수 통계와 같은 공용 `TeamStats.columns.fmt` 를 씁니다(가져다 쓰기만).
  - IP: `ip` 형식(`14 1/3`). 지금 화면의 `formatIP` 는 `14 1/3` 을 `14.0` 으로 잘라 보이므로 Quick Look 에서는 쓰지 않습니다.
  - ERA·WHIP: `f2`. AVG·OBP·SLG·OPS: `avg3`(`.251`). K%·BB%: `f1` 뒤에 `%`. 합계: 정수.

## 5. 파일

| 파일 | 할 일 |
|---|---|
| `dashboard_js/js/player-analytics/quicklook.js` (새) | 순수 함수. 시즌 행 → Quick Look 표 데이터(머리글·줄). DOM 안 씀. `window.PlayerAnalytics.quicklook` 과 `module.exports` 둘 다 |
| `dashboard_js/css/player-analytics.css` (새) | 새 클래스(`pa-hdr-*`, `pa-card*`, `pa-ql*`)만. `style.css` 뒤에 불러옵니다 |
| `dashboard_js/pages/player-analytics.html` | 헤더·카드 마크업과 렌더 함수 교체, 스크립트 3개(`js/stats/metrics.js`, `js/stats/columns.js`, `js/player-analytics/quicklook.js`)와 CSS 1개 추가 |

- `css/style.css` 는 화면 세션과 같이 고치는 파일이라 건드리지 않습니다. 옛 클래스 규칙(`.header-bar-*` 등)은 남지만 이 페이지가 더는 쓰지 않습니다. 정리는 나중에 따로 합니다.
- 공용 `js/stats/*`·`css/stats.css` 는 불러 쓰기만 합니다.
- `?id=<선수 ID>`·`&mode=futures` 주소 동작은 그대로입니다.

## 6. 검증

- Node 시험(저장소 밖 `C:/tmp/bstats-player-analytics-check/tests`): 통산 합산, 이닝 분수(`14 1/3`), 이적 시즌 합치기, 기록 없는 시즌 '-', 분모 0 → '-'.
- 화면 PNG(바탕화면): 투수(구창모 65933), 타자 1명, 퓨처스 선수, 은퇴 선수, 다크 모드, 휴대폰 폭.
- 미리보기는 화면 세션의 127.0.0.2:8765 를 그대로 씁니다(새로 띄우지 않음).
- push·배포는 evan 허락 뒤에만 합니다.
