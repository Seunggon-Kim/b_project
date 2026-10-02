# 2A 수집기 버그·안정화 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 포스트시즌 날짜 버그를 고치고, 날짜가 틀린 행이 D1 에 들어가지 못하게 막고, 끝난 백필 단계와 roster 작업의 연쇄 실패를 정리합니다.

**Architecture:** 날짜 계산은 의존성이 없는 `crawler/gameid.py` 에 함수 하나로 모으고 파서가 그것을 씁니다. 적재 스크립트는 넣기 전에 날짜를 검사합니다. 워크플로는 단계 조건만 고칩니다. D1 에 쓰는 SQL 은 바꾸지 않습니다(Task 4 의 건너뛰기만 예외).

**Tech Stack:** Python 3.11+, pytest, GitHub Actions YAML

## Global Constraints

- 저장소 `Seunggon-Kim/b_project` 는 **공개**입니다. 서버 IP·비밀번호·키·`~/.bstats/` 내용을 코드·문서·커밋에 넣지 않습니다.
- 회사 계정(evan@delivered.co.kr)·회사 GCP 를 쓰지 않습니다.
- push·병합·배포는 건마다 evan 허락을 받습니다. 이 계획서는 로컬 브랜치 커밋까지입니다.
- D1 쓰기는 evan 승인 없이 하지 않습니다. 이 계획서의 작업은 D1 에 직접 쓰지 않습니다(코드만 바꿉니다).
- Python 은 `py` 로 부릅니다(`python` 은 고장 난 스토어 바로가기입니다). 테스트: `PYTHONUTF8=1 py -m pytest <경로> -p no:cacheprovider -q`.
- 전체 테스트의 알려진 실패 2개는 이 계획과 무관합니다: `tests/test_cron_table_parity.py`, `tests/test_workflow_deps.py`. 새 실패가 0 이어야 합니다.
- 커밋 메시지 끝: `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`
- 사용자에게 보이는 한국어는 `습니다/합니다` 체, 이모지 금지. 코드 주석은 저장소 문체(짧은 문장, 왜를 적음)를 따릅니다.
- 작업 위치: `git -C C:/Users/김승곤/Desktop/b_project worktree add C:/tmp/b_project_2a -b fix/phase2a-collectors main` 로 만든 worktree. 원래 폴더(페이지 세션이 씀)에서 작업하지 않습니다.

---

### Task 1: 포스트시즌 game_date 계산 고치기

13자 포스트시즌 gameID(2015년까지, 예 `33330929LTOB0`)에서 파서가 뒤 네 자리 `TOB0` 를 연도로 써서 `game_date='TOB00929'` 를 만듭니다. 연도는 크롤러가 이미 `gid_year` 로 알고 있지만 파서에 안 넘깁니다.

**Files:**
- Modify: `crawler/gameid.py` (끝에 함수 추가)
- Modify: `crawler/game_parse.py:3` (import), `crawler/game_parse.py:281-289` (`load`)
- Modify: `crawler/download.py:1355`
- Test: `tests/test_postseason_gameid.py` (끝에 클래스 추가, import 줄 수정)

**Interfaces:**
- Produces: `gameid.game_date_of(game_id, year=None) -> str | None` — `'YYYYMMDD'` 또는 모르면 `None`.
- Produces: `game_status.load(self, game_id, pdf, bdf, rdf, log_file=None, year=None)` — 날짜를 모르면 `ValueError`.

- [ ] **Step 1: 실패하는 테스트 쓰기**

`tests/test_postseason_gameid.py` 의 import 줄을 바꿉니다.

```python
from gameid import game_date_of, game_id_year, save_stem  # noqa: E402
```

파일 끝에 붙입니다.

```python
class TestGameDateOf:
    """경기 날짜(YYYYMMDD)입니다. play_by_play.game_date 에 그대로 들어갑니다."""

    def test_정규시즌은_앞_여덟_자리(self):
        assert game_date_of('20250315HHSS0') == '20250315'

    def test_2016년_이후_포스트시즌은_뒤_연도와_가운데_월일(self):
        assert game_date_of('44441006NCSS02026') == '20261006'
        # gameId 안의 연도가 넘겨받은 값보다 우선합니다.
        assert game_date_of('33331013LGWO02016', 2099) == '20161013'

    def test_2015년_이전_포스트시즌은_넘겨받은_연도(self):
        assert game_date_of('33330929LTOB0', 2009) == '20090929'
        assert game_date_of('77771026OBSK0', 2008) == '20081026'

    def test_팀_코드가_날짜에_섞이지_않습니다(self):
        # 예전 파서는 여기서 'TOB00929' 를 만들었습니다.
        d = game_date_of('33330929LTOB0', 2009)
        assert d.isdigit() and len(d) == 8

    def test_연도를_모르면_None(self):
        assert game_date_of('33330929LTOB0') is None

    def test_올스타는_None(self):
        assert game_date_of('99991012ABCD0', 2011) is None


class TestParserGetsYear:
    """파서가 날짜를 game_date_of 로 만들고, 크롤러가 연도를 넘기는지 봅니다."""

    def test_파서는_뒤_네_자리로_날짜를_만들지_않습니다(self):
        src = (ROOT / 'crawler' / 'game_parse.py').read_text(encoding='utf-8')
        assert "f'{game_id[-4:]}" not in src
        assert 'game_date_of(' in src

    def test_크롤러가_연도를_넘깁니다(self):
        src = (ROOT / 'crawler' / 'download.py').read_text(encoding='utf-8')
        assert 'log_file=logfile, year=gid_year)' in src
```

- [ ] **Step 2: 실패 확인**

Run: `PYTHONUTF8=1 py -m pytest tests/test_postseason_gameid.py -p no:cacheprovider -q`
Expected: `ImportError: cannot import name 'game_date_of'` 로 수집 단계에서 실패.

- [ ] **Step 3: `crawler/gameid.py` 끝에 함수 추가**

```python
def game_date_of(game_id, year=None):
    """경기 날짜(YYYYMMDD 글자)입니다. 알 수 없으면 None 입니다.

    gameId 의 5~8번째 자리는 형식과 상관없이 늘 MMDD 입니다. 연도만
    형식마다 자리가 다릅니다(game_id_year 참고).

        20250315HHSS0         -> 20250315
        44441006NCSS02026     -> 20261006
        33330929LTOB0, 2009   -> 20090929   (13자는 연도를 넘겨받아야 합니다)

    예전 파서는 포스트시즌이면 뒤 네 자리를 연도로 썼습니다. 13자에서는
    'TOB0' 같은 팀 코드가 나와 game_date 가 'TOB00929' 가 됐습니다.
    2008~2015 포스트시즌 26,450행이 그렇게 D1 에 들어갔습니다.
    """
    y = game_id_year(game_id, year)
    if y is None:
        return None
    mmdd = str(game_id)[4:8]
    if not mmdd.isdigit():
        return None
    return '%04d%s' % (y, mmdd)
```

- [ ] **Step 4: 파서가 그 함수를 쓰게 바꾸기**

`crawler/game_parse.py` 3번째 줄:

```python
from gameid import game_date_of, game_id_year, save_stem
```

`load` 머리와 날짜 세 줄(281~289행)을 바꿉니다.

```python
    def load(self, game_id, pdf, bdf, rdf, log_file=None, year=None):
        self.pitching_df = pdf
        self.batting_df = bdf
        self.game_id = game_id
        self.log_file = log_file

        # 13자 포스트시즌(2015년까지)은 gameId 에 연도가 없습니다. 크롤러가
        # 캘린더에서 알아 둔 연도를 year 로 받아야 날짜가 맞습니다.
        self.game_date = game_date_of(game_id, year)
        if self.game_date is None:
            raise ValueError('경기 날짜를 알 수 없습니다: %s (13자 포스트시즌은 year 를 넘기십시오)'
                             % game_id)
```

나머지(`self.away = game_id[8:10]` 부터)는 그대로 둡니다.

- [ ] **Step 5: 크롤러가 연도를 넘기게 바꾸기**

`crawler/download.py:1355`:

```python
                    gs.load(gid, game_data_dfs[0], game_data_dfs[1], game_data_dfs[2], log_file=logfile, year=gid_year)
```

이 호출은 바깥 `try … except Exception` 안에 있어(1371행), 날짜를 모르는 경기는 `FAILED gameID …` 로 로그에 남고 다음 경기로 넘어갑니다. 조용히 틀린 날짜로 저장되던 것보다 낫습니다.

`crawler/debug_broken.py:41` 은 손으로 돌리는 디버그 스크립트라 그대로 둡니다(정규시즌·17자는 연도 없이도 됩니다).

- [ ] **Step 6: 통과 확인**

Run: `PYTHONUTF8=1 py -m pytest tests/test_postseason_gameid.py -p no:cacheprovider -q`
Expected: 모두 PASS.

- [ ] **Step 7: 커밋**

```bash
git add crawler/gameid.py crawler/game_parse.py crawler/download.py tests/test_postseason_gameid.py
git commit -m "fix(crawler): 13자 포스트시즌 game_date 에 팀 코드가 들어가던 문제를 고침

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 2: 날짜가 틀린 행은 D1 에 넣지 않기

`daily_pbp_to_d1.py` 는 `DELETE … WHERE game_date = 그날` 후 넣습니다. 날짜가 틀린 행이 들어가면 다음 재실행이 그 행을 못 지워 **같은 경기가 두 번** 쌓입니다. 넣기 전에 막습니다.

**Files:**
- Modify: `data_collection/daily_pbp_to_d1.py` (`import re` 추가, 함수 추가, `main` 에 검사 추가)
- Test: `tests/test_daily_pbp_guard.py` (새 파일)

**Interfaces:**
- Produces: `daily_pbp_to_d1.wrong_dates(rows, day) -> list[str]` — 그날이 아닌 `game_date` 값(정렬, 중복 없음). 2B Task 3 도 이 검사를 그대로 씁니다.

- [ ] **Step 1: 실패하는 테스트 쓰기**

`tests/test_daily_pbp_guard.py`:

```python
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "data_collection"))

import daily_pbp_to_d1 as m  # noqa: E402


def test_모두_그날이면_빈_목록():
    rows = [{"game_date": "20261003"}, {"game_date": "20261003"}]
    assert m.wrong_dates(rows, "20261003") == []


def test_소수점_표기는_같은_날로_봅니다():
    # D1 은 INTEGER 친화성으로 20261003.0 을 20261003 으로 받습니다.
    assert m.wrong_dates([{"game_date": "20261003.0"}], "20261003") == []


def test_다른_날짜와_글자_날짜를_돌려줍니다():
    rows = [{"game_date": "20261003"}, {"game_date": "TOB00929"},
            {"game_date": "20261002"}, {"game_date": "TOB00929"}]
    assert m.wrong_dates(rows, "20261003") == ["20261002", "TOB00929"]


def test_비었거나_없으면_잘못입니다():
    assert m.wrong_dates([{"game_date": ""}, {}], "20261003") == [""]
```

- [ ] **Step 2: 실패 확인**

Run: `PYTHONUTF8=1 py -m pytest tests/test_daily_pbp_guard.py -p no:cacheprovider -q`
Expected: `AttributeError: module 'daily_pbp_to_d1' has no attribute 'wrong_dates'`

- [ ] **Step 3: 함수 추가**

`data_collection/daily_pbp_to_d1.py` 의 import 에 `import re` 를 넣고(`import os` 다음), `read_csv_rows` 아래에 둡니다.

```python
DATE_LIKE = re.compile(r"\d{8}(\.0+)?")


def wrong_dates(rows, day):
    """그날(day)이 아닌 game_date 값들입니다(정렬, 중복 없음).

    날짜가 틀린 행이 들어가면 다음 재실행의 `DELETE … WHERE game_date =
    그날` 이 그 행을 못 지워 같은 경기가 두 번 쌓입니다. 포스트시즌 날짜
    버그(game_date='TOB00929')가 실제로 그런 행을 만들었습니다.
    """
    bad = set()
    for r in rows:
        s = str(r.get("game_date") or "").strip()
        if not (DATE_LIKE.fullmatch(s) and s[:8] == day):
            bad.add(s)
    return sorted(bad)
```

- [ ] **Step 4: `main` 에서 검사**

`print("행 %s개" % format(len(rows), ","))` 바로 다음에 넣습니다.

```python
    bad = wrong_dates(rows, day)
    if bad:
        # 넣으면 재실행 때 지워지지 않는 행이 생깁니다. 아무것도 쓰지 않고 멈춥니다.
        print("game_date 가 %s 이 아닌 행이 있습니다: %s" % (day, ", ".join(bad[:5])))
        print("crawler/gameid.py 의 game_date_of 와 CSV 를 확인하십시오.")
        return 1
```

- [ ] **Step 5: 통과 확인**

Run: `PYTHONUTF8=1 py -m pytest tests/test_daily_pbp_guard.py tests/test_shard_routing.py -p no:cacheprovider -q`
Expected: 모두 PASS(`test_shard_routing` 은 이 파일의 `db_of`·`db_name=` 사용을 소스로 검사합니다. 깨지지 않아야 합니다).

- [ ] **Step 6: 커밋**

```bash
git add data_collection/daily_pbp_to_d1.py tests/test_daily_pbp_guard.py
git commit -m "fix(daily-pbp): 그날이 아닌 game_date 행이 있으면 적재하지 않음

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 3: 끝난 백필 단계를 daily 에서 빼기

2008~2014 백필은 2026-08-29 에 끝났습니다(커서 `pbp_2008_2014`=20111031, `pbp_2012_2014`=20141111, 남은 경기 0). 두 단계는 매일 "모두 끝났습니다" 만 찍으면서 D1 `games` 를 몇 번씩 셉니다.

**Files:**
- Modify: `.github/workflows/daily.yml` (216~266행 "4. 옛 시즌 PBP 되채우기" 구간, 요약 표 두 줄)
- Modify: `migration/shard_backfill.py` (docstring 첫 단락 뒤에 한 단락)
- Modify: `data_collection/record_job_run.py` (`KNOWN_JOBS` 주석)

- [ ] **Step 1: daily.yml 에서 구간 지우기**

`# --- 4. 옛 시즌 PBP 되채우기 (2008~2014) ---` 줄부터 `되채우기 결과 기록` 단계 끝(`--note "2008-2011 … / 2012-2014 …"` 줄)까지를 아래 주석으로 바꿉니다.

```yaml
      # --- 4. 옛 시즌 PBP 되채우기 (2008~2014): 끝남 ---------------------
      # 2026-08-29 에 두 커서 모두 마지막 경기까지 넣었습니다. 매일 "모두
      # 끝났습니다" 만 찍으며 D1 을 읽어서 단계를 뺐습니다. 다시 돌릴 일이
      # 생기면 migration/shard_backfill.py 를 손으로 부르십시오.
```

`요약` 단계에서 다음 두 줄을 지웁니다.

```yaml
            echo "| 옛 시즌 PBP 되채우기 2008-2011 | ${{ steps.backfill.outcome }} |"
            echo "| 옛 시즌 PBP 되채우기 2012-2014 | ${{ steps.backfill2.outcome }} |"
```

- [ ] **Step 2: 남은 참조가 없는지 확인**

Run: `grep -n "backfill" .github/workflows/daily.yml`
Expected: 방금 넣은 주석 줄만 나옵니다(`steps.backfill` 이 없어야 합니다).

- [ ] **Step 3: 스크립트·작업 이름에 사정 적기**

`migration/shard_backfill.py` docstring 첫 단락(`2008~2014 PBP 를 하루 예산만큼씩 D1 에 밀어 넣습니다.`) 바로 다음 줄에 넣습니다.

```python
**2026-08-29 에 끝났습니다.** daily 워크플로에서 단계를 뺐습니다(2026-10).
이 파일은 다시 돌릴 일에 대비해 남겨 둡니다.
```

`data_collection/record_job_run.py` 의 `KNOWN_JOBS` 안 주석을 바꿉니다.

```python
    # 2008~2014 PBP 되채우기입니다. 2026-08-29 에 끝나 daily 에서 뺐습니다.
    # 화면(database-explorer.html)에서 항목을 지울 때 여기서도 지웁니다.
    "pbp_backfill",
```

- [ ] **Step 4: 테스트**

Run: `PYTHONUTF8=1 py -m pytest tests -p no:cacheprovider -q`
Expected: 실패는 알려진 2개(`test_cron_table_parity.py`, `test_workflow_deps.py`)뿐입니다. 백필 helper 테스트(`test_backfill_*.py`)는 스크립트를 남겼으므로 통과합니다.

- [ ] **Step 5: 커밋**

```bash
git add .github/workflows/daily.yml migration/shard_backfill.py data_collection/record_job_run.py
git commit -m "chore(daily): 끝난 2008~2014 백필 단계를 뺌

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 4: 0-3 소속 갱신이 teams 에 없는 팀을 건너뛰기 (evan 승인 필요)

퓨처스 명단에 상무·울산이 있습니다. `players.team_id` 는 `teams` 를 가리키는 외래키라, 그 선수 한 명 때문에 파일 전체가 실패합니다. 실패하면 뒤 단계(새 선수, 퓨처스 기록, 캐시 비우기)도 기본 조건 때문에 건너뜁니다. 2026-08-29 이후 roster 작업이 계속 빨간 원인입니다.

**Files:**
- Modify: `data_collection/sync_players_from_roster.py` (`split_known` 추가, `main` 수정)
- Modify: `.github/workflows/roster.yml` (`newp`·`futures`·`캐시 비우기` 단계 조건)
- Test: `tests/test_sync_players_known_teams.py` (새 파일)

**Interfaces:**
- Produces: `sync_players_from_roster.split_known(rows, known) -> (list, list)` — `rows` 는 `diffs()` 결과(`rt` 키에 새 소속). 2B Task 5 가 MySQL 쪽에서 같은 함수를 씁니다.

- [ ] **Step 1: 실패하는 테스트 쓰기**

`tests/test_sync_players_known_teams.py`:

```python
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "data_collection"))

import sync_players_from_roster as m  # noqa: E402


def test_teams_에_없는_소속은_건너뜁니다():
    rows = [{"pid": 1, "nm": "가", "rt": "LG"},
            {"pid": 2, "nm": "나", "rt": "상무"},
            {"pid": 3, "nm": "다", "rt": "KIA"}]
    keep, skip = m.split_known(rows, {"LG", "KIA"})
    assert [r["pid"] for r in keep] == [1, 3]
    assert [r["pid"] for r in skip] == [2]


def _step(text, marker):
    """워크플로에서 marker 가 있는 단계 하나의 글자입니다."""
    start = text.index(marker)
    end = text.find("\n      - ", start)
    return text[start:end if end != -1 else None]


def test_roster_뒤_단계는_소속_갱신이_실패해도_돕니다():
    text = (ROOT / ".github" / "workflows" / "roster.yml").read_text(encoding="utf-8")
    for marker in ("id: newp", "id: futures", "name: 캐시 비우기"):
        assert "!cancelled()" in _step(text, marker), marker
```

- [ ] **Step 2: 실패 확인**

Run: `PYTHONUTF8=1 py -m pytest tests/test_sync_players_known_teams.py -p no:cacheprovider -q`
Expected: 두 테스트 모두 FAIL(`split_known` 없음, `!cancelled()` 없음).

- [ ] **Step 3: `split_known` 추가**

`data_collection/sync_players_from_roster.py` 의 `diffs()` 아래에 둡니다.

```python
def split_known(rows, known):
    """teams 에 있는 소속만 남깁니다. (반영할 것, 건너뛴 것) 입니다.

    퓨처스 명단에는 상무·울산처럼 teams 에 없는 팀이 있습니다.
    players.team_id 는 teams 를 가리키는 외래키라, 그런 행이 하나라도
    섞이면 파일 전체가 실패합니다. 2026-08-29 부터 roster 작업이 매번
    빨간 이유였습니다.
    """
    keep = [r for r in rows if r["rt"] in known]
    skip = [r for r in rows if r["rt"] not in known]
    return keep, skip
```

- [ ] **Step 4: `main` 에서 쓰기**

`rows = diffs()` 와 `if not rows:` 블록 다음, `team = sum(...)` 앞에 넣습니다.

```python
    known = {r["team_id"] for r in query("SELECT team_id FROM teams;")}
    rows, skipped = split_known(rows, known)
    if skipped:
        print("teams 에 없는 소속이라 건너뛴 선수 %d명: %s"
              % (len(skipped), ", ".join("%s(%s)" % (r["nm"], r["rt"])
                                         for r in skipped[:10])))
    if not rows:
        print("반영할 것이 없습니다.")
        return 0
```

끝의 남은 불일치 계산을 바꿉니다(건너뛴 선수는 늘 남으므로 세지 않습니다).

```python
    left = [r for r in diffs() if r["rt"] in known]
    print("남은 불일치 %d명" % len(left))
```

- [ ] **Step 5: roster.yml 조건 고치기**

`if:` 에 상태 함수가 없으면 GitHub 가 `success() &&` 를 앞에 붙입니다. 그래서 `sync` 가 실패하면 뒤 단계가 모두 건너뜁니다.

`새 선수 추가`(id: newp):

```yaml
        if: ${{ !cancelled() && steps.roster.outcome == 'success' }}
```

`퓨처스 올 시즌 기록 갱신`(id: futures) 에 조건을 새로 넣습니다(`id: futures` 다음 줄).

```yaml
        if: ${{ !cancelled() }}
```

`캐시 비우기`:

```yaml
        if: ${{ !cancelled() && steps.roster.outcome == 'success' }}
```

- [ ] **Step 6: 통과 확인**

Run: `PYTHONUTF8=1 py -m pytest tests/test_sync_players_known_teams.py -p no:cacheprovider -q`
Expected: 모두 PASS.

- [ ] **Step 7: 미리보기로 실제 동작 확인(D1 읽기만)**

Run: `PYTHONUTF8=1 py data_collection/sync_players_from_roster.py --dry-run`
Expected: `바뀐 선수 N명` 과 함께(상무·울산이 있으면) `teams 에 없는 소속이라 건너뛴 선수 …` 가 나오고, `[미리보기] 반영하지 않았습니다.` 로 끝납니다. D1 읽기는 `kbo_roster`·`players`·`teams` 몇천 행입니다.

- [ ] **Step 8: 커밋**

```bash
git add data_collection/sync_players_from_roster.py .github/workflows/roster.yml tests/test_sync_players_known_teams.py
git commit -m "fix(roster): teams 에 없는 소속은 건너뛰고 뒤 단계는 계속 돌게 함 (0-3)

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 5: 0-5 주간 작업 일정 끄기 (evan 이 "커밋으로 꺼 주세요" 라고 한 경우만)

evan 이 GitHub 화면(Actions → weekly → ··· → Disable workflow)에서 이미 껐다면 이 Task 는 건너뜁니다. 화면에서 끈 것은 2B Task 7 끝에 화면에서 다시 켭니다.

**Files:**
- Modify: `.github/workflows/weekly.yml` (`on:` 블록)

- [ ] **Step 1: 일정만 끄고 손으로 돌리는 길은 남기기**

```yaml
on:
  # 일정은 꺼 두었습니다(2026-10, D1 무료 한도 보호). D1 에서 400만 행을
  # 내려받아 한 번에 하루 한도의 대부분을 씁니다. MySQL 에서 내려받도록
  # 바꾼 뒤(2단계 2B Task 7) 다시 켭니다.
  #   schedule:
  #     - cron: '47 20 * * 1'
  workflow_dispatch:
```

- [ ] **Step 2: 테스트**

Run: `PYTHONUTF8=1 py -m pytest tests/test_woba_weights.py tests/test_pipeline_tables.py -p no:cacheprovider -q`
Expected: PASS(이 둘이 weekly.yml 단계를 읽습니다).

- [ ] **Step 3: 커밋**

```bash
git add .github/workflows/weekly.yml
git commit -m "chore(weekly): MySQL 전환 전까지 주간 일정을 끔 (0-5)

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

## 마무리

- [ ] 전체 테스트: `PYTHONUTF8=1 py -m pytest tests -p no:cacheprovider -q` — 알려진 2개 외 실패 0. `npm test` — 324개 통과(이 계획은 `src/` 를 건드리지 않습니다).
- [ ] 로드맵(`docs/superpowers/plans/2026-10-01-mysql-migration-roadmap.md`) 0단계 표에서 0-3·0-5 상태를 "완료(브랜치 이름)" 로 고칩니다.
- [ ] evan 에게 push·병합 여부를 묻습니다. 병합 뒤 첫 daily·roster 실행 결과를 확인합니다(roster 가 초록이 되어야 합니다).
