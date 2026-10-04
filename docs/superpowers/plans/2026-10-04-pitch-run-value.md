# 구종 가치(Pitch Run Value) 구현 계획

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 시즌별 기대 득점 표로 공 하나의 가치를 계산해 MySQL 미리 계산 표에 넣고, `GET /players/{id}/pitch_values` 로 읽게 합니다.

**Architecture:** 계산은 Python 순수 함수 모듈(`pitch_value_calc.py`)이 맡고, 스크립트(`pitch_run_value.py`)가 MySQL 에서 한 시즌 PBP 를 읽어 계산한 뒤 두 표(`run_expectancy`, `pitch_run_value`)를 시즌 단위로 바꿉니다. Worker 는 표를 읽기만 합니다(무료 CPU 10ms).

**Tech Stack:** Python 3.13 + PyMySQL(migration.mysql.conn), pytest / Cloudflare Workers JS + node:test, MySQL 8.4(Cloud SQL), GitHub Actions daily.yml.

설계: `docs/superpowers/specs/2026-10-04-pitch-run-value-design.md` (evan 승인, D1~D5 권장안).

## Global Constraints

- 정규시즌만: 경기 ID 가 `3333`·`4444`·`5555`·`7777`·`9999` 로 시작하면 뺍니다(`6666` 은 정규시즌).
- 범위: 2016~현재.
- 순서: 한 경기 안은 `pbp_id` 순. 반이닝 = (`gameID`, `inning`, `inning_topbot`).
- 공 하나 가치 = RE(바로 다음 행 상태) − RE(이 공 직전 상태) + 이 공 `runs_scored`. 반이닝 마지막 공 다음은 0. 투수 쪽 부호(− 를 붙임).
- 투구 행 = `pitch_result IS NOT NULL`. 사건 행(도루·견제·폭투·포일·보크·교체)은 가치에 넣지 않음(D1).
- 상태 = 주자(1루=1, 2루=2, 3루=4 의 합) × `outs` × `min(balls,3)` × `strikes`.
- 기대 득점 표는 각 경기의 마지막 반이닝을 빼고 만듦. 표에 없는 상태는 전체 반이닝으로 만든 값으로 메움.
- 센터링 안 함(D2). 시즌별 표(D3). MySQL 에만(D4). 기대 득점 표도 저장(D5).
- 스위치 타자(`양`): 우투수 상대 L, 좌투수 상대 R. `좌`=L, `우`=R, 그 밖은 R.
- 구종이 비었거나 `'' '-' 'null'` 인 공은 기대 득점 표에만 쓰고 가치 표에는 넣지 않음.
- D1 은 읽지도 쓰지도 않음. 새 표는 `migration/mysql/schema_types.json` 에 넣지 않음(D1↔MySQL 대조 대상 아님).
- 커밋은 자기 파일만 경로를 붙여(`git commit -m … -- <파일>`). `git add -A`·stash·reset·restore·브랜치 변경 금지.
- push·Worker 배포·DB 쓰기(새 표 만들기 포함)는 evan 허락 뒤에만. daily·DB 구조를 고치기 전 DB 세션(dk-analytics-28)에 알림.
- 사용자에게 보이는 글은 습니다체, 이모지 금지.

## 파일

| 파일 | 할 일 |
|---|---|
| `data_collection/pitch_value_calc.py` (새) | 순수 계산: 상태, 반이닝 묶기, 기대 득점 표, 공 가치, 타자 손 |
| `tests/test_pitch_value_calc.py` (새) | 위 함수 시험 |
| `data_collection/pitch_run_value.py` (새) | 시즌 고르기, MySQL 읽기, 표 쓰기(--dry-run), 요약 출력 |
| `tests/test_pitch_run_value.py` (새) | 시즌 고르기·행 만들기·쓰기 SQL 시험(가짜 커서) |
| `migration/mysql/pitch_value_schema.sql` (새) | 두 표 CREATE TABLE |
| `src/routes/pitchValues.js` (새) | API |
| `src/index.js` | 라우트 등록 한 줄 |
| `test/pitchvalues.test.js` (새) | API 시험 |
| `.github/workflows/daily.yml` | 계산 단계 + 실행 기록 단계 |
| `data_collection/record_job_run.py` | KNOWN_JOBS 에 `pitch_values` |
| `database/lineage_writes.json` | 스크립트 항목 |
| `database/column_descriptions.json` | 두 표 열 설명 |

---

### Task 1: 순수 계산 모듈

**Files:**
- Create: `data_collection/pitch_value_calc.py`
- Test: `tests/test_pitch_value_calc.py`

**Interfaces:**
- Produces:
  - 행 = dict, 키: `gameID, pbp_id, inning, inning_topbot, outs, balls, strikes, on_1b, on_2b, on_3b`(참/거짓), `pitch_result, runs_scored, pitcher_ID, pitch_type, stands, throws`
  - `state_of(row) -> tuple[int,int,int,int]` (bases, outs, balls, strikes)
  - `split_halves(rows) -> list[list[dict]]` (입력은 gameID·pbp_id 순 정렬)
  - `last_half_index(halves) -> set[int]` 각 경기 마지막 반이닝의 번호
  - `build_re(halves, skip=frozenset()) -> tuple[dict, dict]` (re, n)
  - `expectancy_table(halves) -> tuple[dict, dict]` 마지막 반이닝을 뺀 표 + 빈 상태를 전체 표로 메움
  - `bat_side(stands, throws) -> 'L'|'R'`
  - `is_pitch(row) -> bool`, `has_type(row) -> bool`
  - `pitch_values(halves, re) -> dict[(pitcher_ID, pitch_type, side), [n, rv]]` rv 는 투수 쪽 부호

- [ ] **Step 1: 실패하는 시험 쓰기** — `tests/test_pitch_value_calc.py`

```python
# -*- coding: utf-8 -*-
import pytest

from data_collection import pitch_value_calc as pv


def row(pbp_id, *, game="G1", inning=1, tb="초", outs=0, balls=0, strikes=0,
        b1=False, b2=False, b3=False, result="볼", runs=0, pitcher=1,
        ptype="직구", stands="우", throws="우"):
    return {"gameID": game, "pbp_id": pbp_id, "inning": inning, "inning_topbot": tb,
            "outs": outs, "balls": balls, "strikes": strikes,
            "on_1b": b1, "on_2b": b2, "on_3b": b3, "pitch_result": result,
            "runs_scored": runs, "pitcher_ID": pitcher, "pitch_type": ptype,
            "stands": stands, "throws": throws}


def test_상태는_주자_합_아웃_볼_스트라이크입니다():
    assert pv.state_of(row(1, b1=True, b3=True, outs=2, balls=1, strikes=2)) == (5, 2, 1, 2)


def test_볼_4는_3으로_봅니다():
    assert pv.state_of(row(1, balls=4)) == (0, 0, 3, 0)


def test_반이닝은_경기_이닝_초말로_나눕니다():
    rows = [row(1), row(2), row(3, tb="말"), row(4, inning=2), row(5, game="G2")]
    assert [[r["pbp_id"] for r in h] for h in pv.split_halves(rows)] == [[1, 2], [3], [4], [5]]


def test_경기마다_마지막_반이닝을_찾습니다():
    halves = pv.split_halves([row(1), row(2, tb="말"), row(3, game="G2")])
    assert pv.last_half_index(halves) == {1, 2}


def test_기대_득점은_그_공부터_반이닝_끝까지_득점_평균입니다():
    # 반이닝 A: 0-0 에서 시작해 두 번째 공에 1점, 반이닝 B: 0-0 에서 무득점
    a = [row(1), row(2, balls=1, result="타격", runs=1)]
    b = [row(3, inning=2)]
    re, n = pv.build_re([a, b])
    assert n[(0, 0, 0, 0)] == 2
    assert re[(0, 0, 0, 0)] == pytest.approx(0.5)
    assert re[(0, 0, 1, 0)] == pytest.approx(1.0)


def test_사건_행은_기대_득점_표에_들지_않지만_득점은_셉니다():
    a = [row(1), row(2, result=None, runs=1), row(3, balls=1)]
    re, n = pv.build_re([a])
    assert (0, 0, 1, 0) in re and n[(0, 0, 0, 0)] == 1
    assert re[(0, 0, 0, 0)] == pytest.approx(1.0)  # 폭투 득점도 "그 뒤 득점"
    assert re[(0, 0, 1, 0)] == pytest.approx(0.0)


def test_표는_경기_마지막_반이닝을_빼고_빈_상태는_전체로_메웁니다():
    first = [row(1), row(2, balls=1)]
    last = [row(3, tb="말", runs=0), row(4, tb="말", strikes=2, runs=1)]
    re, n = pv.expectancy_table([first, last])
    assert re[(0, 0, 0, 0)] == pytest.approx(0.0)          # 마지막 반이닝 빠짐
    assert n[(0, 0, 0, 0)] == 1
    assert re[(0, 0, 0, 2)] == pytest.approx(1.0)          # 전체 표로 메움


def test_스위치_타자는_투수_반대쪽입니다():
    assert pv.bat_side("양", "우") == "L"
    assert pv.bat_side("양", "좌") == "R"
    assert pv.bat_side("좌", "우") == "L"
    assert pv.bat_side("우", "좌") == "R"
    assert pv.bat_side(None, None) == "R"


def test_공_가치는_다음_행_상태와_득점으로_재고_투수_쪽_부호입니다():
    re = {(0, 0, 0, 0): 0.5, (0, 0, 1, 0): 0.6, (1, 0, 0, 0): 0.9}
    h = [row(1, ptype="직구"),                      # 0-0 → 1-0 : +0.1 → 투수 −0.1
         row(2, balls=1, result="타격", ptype="커브", stands="좌", runs=1)]  # 반이닝 끝: 0 − 0.6 + 1
    vals = pv.pitch_values([h], re)
    assert vals[(1, "직구", "R")] == [1, pytest.approx(-0.1)]
    assert vals[(1, "커브", "L")] == [1, pytest.approx(-0.4)]


def test_사건_몫은_공에_붙지_않습니다():
    re = {(0, 0, 0, 0): 0.5, (2, 0, 0, 0): 0.7, (2, 0, 1, 0): 0.8, (1, 0, 0, 0): 0.6}
    # 1루 주자, 볼 → 0-0 직후 상태(1루)가 사건 행에 적힘 → 도루로 2루 → 다음 공 1-0
    h = [row(1, b1=True, ptype="직구"),
         row(2, b1=True, balls=1, result=None),     # 도루 행(직전 상태 = 볼 직후)
         row(3, b2=True, balls=1, ptype="커브")]
    re[(1, 0, 1, 0)] = 0.65
    vals = pv.pitch_values([h], re)
    assert vals[(1, "직구", "R")][1] == pytest.approx(-(0.65 - 0.6))


def test_구종_없는_공은_가치_표에_넣지_않습니다():
    re = {(0, 0, 0, 0): 0.5}
    vals = pv.pitch_values([[row(1, ptype=None)], [row(2, ptype="-")]], re)
    assert vals == {}
```

- [ ] **Step 2: 실패 확인**

Run: `PYTHONUTF8=1 py -m pytest tests/test_pitch_value_calc.py -q`
Expected: FAIL (`ModuleNotFoundError` 또는 import 오류)

- [ ] **Step 3: 구현** — `data_collection/pitch_value_calc.py`

```python
# -*- coding: utf-8 -*-
"""구종 가치 계산(순수 함수). DB 를 모릅니다.

설계: docs/superpowers/specs/2026-10-04-pitch-run-value-design.md

공 하나의 가치 = RE(바로 다음 행 상태) − RE(이 공 직전 상태) + 이 공 득점.
투수 쪽 부호로 바꿉니다(실점을 막으면 +). 행은 경기 안에서 pbp_id 순이어야 합니다.
"""
from collections import defaultdict

NO_TYPE = (None, "", "-", "null")


def is_pitch(r):
    return r.get("pitch_result") is not None


def has_type(r):
    return r.get("pitch_type") not in NO_TYPE


def state_of(r):
    bases = (1 if r["on_1b"] else 0) + (2 if r["on_2b"] else 0) + (4 if r["on_3b"] else 0)
    return (bases, int(r["outs"]), min(int(r["balls"]), 3), int(r["strikes"]))


def split_halves(rows):
    halves, cur, key = [], None, None
    for r in rows:
        k = (r["gameID"], r["inning"], r["inning_topbot"])
        if k != key:
            cur = []
            halves.append(cur)
            key = k
        cur.append(r)
    return halves


def last_half_index(halves):
    last = {}
    for i, h in enumerate(halves):
        last[h[0]["gameID"]] = i
    return set(last.values())


def build_re(halves, skip=frozenset()):
    sums, n = defaultdict(float), defaultdict(int)
    for i, h in enumerate(halves):
        if i in skip:
            continue
        rem = 0
        for r in reversed(h):
            rem += int(r.get("runs_scored") or 0)
            if is_pitch(r):
                s = state_of(r)
                sums[s] += rem
                n[s] += 1
    return {s: sums[s] / n[s] for s in n}, dict(n)


def expectancy_table(halves):
    re, n = build_re(halves, skip=last_half_index(halves))
    full, full_n = build_re(halves)
    for s, v in full.items():
        if s not in re:
            re[s] = v
            n[s] = full_n[s]
    return re, n


def bat_side(stands, throws):
    if stands == "양":
        return "L" if throws == "우" else "R"
    return "L" if stands == "좌" else "R"


def pitch_values(halves, re):
    out = {}
    for h in halves:
        for i, r in enumerate(h):
            if not is_pitch(r) or not has_type(r):
                continue
            nxt = h[i + 1] if i + 1 < len(h) else None
            after = re.get(state_of(nxt), 0.0) if nxt is not None else 0.0
            delta = after - re[state_of(r)] + int(r.get("runs_scored") or 0)
            key = (r["pitcher_ID"], r["pitch_type"], bat_side(r.get("stands"), r.get("throws")))
            acc = out.setdefault(key, [0, 0.0])
            acc[0] += 1
            acc[1] -= delta
    return out
```

- [ ] **Step 4: 통과 확인**

Run: `PYTHONUTF8=1 py -m pytest tests/test_pitch_value_calc.py -q`
Expected: PASS (11 passed)

- [ ] **Step 5: 커밋**

```bash
git add -- data_collection/pitch_value_calc.py tests/test_pitch_value_calc.py
git commit -m "feat(pitch-value): 기대 득점 표·공 가치 순수 계산" -- data_collection/pitch_value_calc.py tests/test_pitch_value_calc.py
```

### Task 2: 계산 스크립트(쓰기 없이 돌려 보기까지)

**Files:**
- Create: `data_collection/pitch_run_value.py`
- Create: `migration/mysql/pitch_value_schema.sql`
- Test: `tests/test_pitch_run_value.py`

**Interfaces:**
- Consumes: Task 1 의 `split_halves`, `expectancy_table`, `pitch_values`
- Produces:
  - `seasons_from_args(args, today) -> list[int]`
  - `fetch_sql() -> str` (파라미터 2개: from, to)
  - `re_rows(season, re, n) -> list[tuple]` (season, bases, outs, balls, strikes, re, n)
  - `value_rows(season, vals) -> list[tuple]` (season, pitcher_ID, pitch_type, stands, n, rv)
  - `write_season(con, season, re_rows, value_rows) -> None` (DELETE 두 번 + INSERT, 한 트랜잭션)
  - CLI: `--season Y` | `--current` | `--from A --to B`, `--dry-run`

- [ ] **Step 1: 실패하는 시험** — `tests/test_pitch_run_value.py`

```python
# -*- coding: utf-8 -*-
import argparse
import datetime

import pytest

from data_collection import pitch_run_value as prv


def ns(**kw):
    base = dict(season=None, current=False, from_=None, to=None, dry_run=False)
    base.update(kw)
    return argparse.Namespace(**base)


TODAY = datetime.date(2026, 10, 4)


def test_시즌_하나():
    assert prv.seasons_from_args(ns(season=2024), TODAY) == [2024]


def test_올해():
    assert prv.seasons_from_args(ns(current=True), TODAY) == [2026]


def test_범위():
    assert prv.seasons_from_args(ns(from_=2016, to=2018), TODAY) == [2016, 2017, 2018]


def test_2016_전은_거절합니다():
    with pytest.raises(SystemExit):
        prv.seasons_from_args(ns(season=2015), TODAY)


def test_읽기_질의는_정규시즌만_pbp_id_순입니다():
    sql = prv.fetch_sql()
    for p in ("3333", "4444", "5555", "7777", "9999"):
        assert "gameID NOT LIKE '%s%%%%'" % p in sql
    assert "ORDER BY gameID, pbp_id" in sql
    assert sql.count("%s") == 2


def test_행_만들기():
    assert prv.re_rows(2024, {(1, 0, 2, 1): 0.5}, {(1, 0, 2, 1): 7}) == [(2024, 1, 0, 2, 1, 0.5, 7)]
    assert prv.value_rows(2024, {(65933, "직구", "L"): [3, 1.25]}) == [(2024, 65933, "직구", "L", 3, 1.25)]


class FakeCur:
    def __init__(self):
        self.calls = []

    def execute(self, sql, params=None):
        self.calls.append(("execute", sql, params))

    def executemany(self, sql, rows):
        self.calls.append(("executemany", sql, list(rows)))


class FakeCon:
    def __init__(self):
        self.cur = FakeCur()
        self.committed = False
        self.rolled = False

    def cursor(self):
        return self.cur

    def begin(self):
        pass

    def commit(self):
        self.committed = True

    def rollback(self):
        self.rolled = True


def test_시즌을_지우고_넣고_커밋합니다():
    con = FakeCon()
    prv.write_season(con, 2024, [(2024, 0, 0, 0, 0, 0.6, 10)], [(2024, 1, "직구", "R", 3, 0.2)])
    kinds = [(c[0], c[1].split()[0], c[1].split()[2] if c[0] == "execute" else c[1].split()[2]) for c in con.cur.calls]
    assert kinds == [("execute", "DELETE", "run_expectancy"), ("execute", "DELETE", "pitch_run_value"),
                     ("executemany", "INSERT", "run_expectancy"), ("executemany", "INSERT", "pitch_run_value")]
    assert con.committed and not con.rolled


def test_실패하면_되돌립니다():
    con = FakeCon()

    def boom(sql, rows):
        raise RuntimeError("x")
    con.cur.executemany = boom
    with pytest.raises(RuntimeError):
        prv.write_season(con, 2024, [(2024, 0, 0, 0, 0, 0.6, 10)], [])
    assert con.rolled and not con.committed
```

- [ ] **Step 2: 실패 확인**

Run: `PYTHONUTF8=1 py -m pytest tests/test_pitch_run_value.py -q`
Expected: FAIL (import 오류)

- [ ] **Step 3: 구현** — `data_collection/pitch_run_value.py`

```python
# -*- coding: utf-8 -*-
"""구종 가치 표(pitch_run_value)와 기대 득점 표(run_expectancy)를 만듭니다.

MySQL 에서 한 시즌 정규시즌 PBP 를 읽어 계산하고, 그 시즌 행을 한 트랜잭션에서
바꿉니다. D1 은 읽지도 쓰지도 않습니다. 계산 규칙은 pitch_value_calc.py 와
docs/superpowers/specs/2026-10-04-pitch-run-value-design.md 에 있습니다.

    py data_collection/pitch_run_value.py --season 2024 --dry-run
    py data_collection/pitch_run_value.py --current          # daily
    py data_collection/pitch_run_value.py --from 2016 --to 2025
"""
import argparse
import datetime
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from data_collection import pitch_value_calc as pv  # noqa: E402

FIRST_SEASON = 2016
NON_REGULAR = ("3333", "4444", "5555", "7777", "9999")
KST = datetime.timezone(datetime.timedelta(hours=9))
COLS = ("gameID", "pbp_id", "inning", "inning_topbot", "outs", "balls", "strikes",
        "on_1b", "on_2b", "on_3b", "pitch_result", "runs_scored",
        "pitcher_ID", "pitch_type", "stands", "throws")


def seasons_from_args(args, today):
    if args.season is not None:
        seasons = [args.season]
    elif args.current:
        seasons = [today.year]
    elif args.from_ is not None and args.to is not None:
        seasons = list(range(args.from_, args.to + 1))
    else:
        raise SystemExit("--season, --current, --from/--to 중 하나가 필요합니다")
    if min(seasons) < FIRST_SEASON:
        raise SystemExit("%d 년부터만 만듭니다" % FIRST_SEASON)
    return seasons


def fetch_sql():
    reg = " AND ".join("gameID NOT LIKE '%s%%%%'" % p for p in NON_REGULAR)
    return ("SELECT gameID, pbp_id, inning, inning_topbot, outs, balls, strikes, "
            "on_1b_id IS NOT NULL AS on_1b, "
            "on_2b_id IS NOT NULL AS on_2b, "
            "on_3b_id IS NOT NULL AS on_3b, "
            "pitch_result, runs_scored, pitcher_ID, pitch_type, stands, throws "
            "FROM play_by_play WHERE game_date >= %s AND game_date < %s AND " + reg +
            " ORDER BY gameID, pbp_id")


def re_rows(season, re, n):
    return [(season, s[0], s[1], s[2], s[3], re[s], n[s]) for s in sorted(re)]


def value_rows(season, vals):
    return [(season, k[0], k[1], k[2], v[0], v[1]) for k, v in sorted(vals.items(), key=lambda kv: (kv[0][0], kv[0][1], kv[0][2]))]


def write_season(con, season, re_list, value_list):
    cur = con.cursor()
    try:
        con.begin()
        cur.execute("DELETE FROM run_expectancy WHERE season = %s", (season,))
        cur.execute("DELETE FROM pitch_run_value WHERE season = %s", (season,))
        cur.executemany("INSERT INTO run_expectancy (season, bases, outs, balls, strikes, re, n) "
                        "VALUES (%s, %s, %s, %s, %s, %s, %s)", re_list)
        cur.executemany("INSERT INTO pitch_run_value (season, pitcher_ID, pitch_type, stands, n, rv) "
                        "VALUES (%s, %s, %s, %s, %s, %s)", value_list)
        con.commit()
    except Exception:
        con.rollback()
        raise


def compute(con, season):
    cur = con.cursor()
    cur.execute(fetch_sql(), (season * 10000, (season + 1) * 10000))
    rows = [dict(zip(COLS, r)) for r in cur.fetchall()]
    halves = pv.split_halves(rows)
    re, n = pv.expectancy_table(halves)
    vals = pv.pitch_values(halves, re)
    return rows, re, n, vals


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--season", type=int)
    ap.add_argument("--current", action="store_true")
    ap.add_argument("--from", dest="from_", type=int)
    ap.add_argument("--to", type=int)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args(argv)
    seasons = seasons_from_args(args, datetime.datetime.now(KST).date())

    from migration.mysql import conn as myconn
    con = myconn.connect()
    try:
        for season in seasons:
            t = time.time()
            rows, re, n, vals = compute(con, season)
            if not rows:
                print("%d: 정규시즌 PBP 가 없어 건너뜁니다" % season)
                continue
            total = sum(v[1] for v in vals.values())
            print("%d: PBP %d행, 상태 %d칸(최소 %d공), 가치 %d줄, 리그 합 %+.1f점, %.1f초"
                  % (season, len(rows), len(re), min(n.values()), len(vals), total, time.time() - t))
            if not args.dry_run:
                write_season(con, season, re_rows(season, re, n), value_rows(season, vals))
                print("%d: 썼습니다" % season)
    finally:
        con.close()


if __name__ == "__main__":
    main()
```

`migration/mysql/pitch_value_schema.sql`:

```sql
-- 구종 가치(설계 docs/superpowers/specs/2026-10-04-pitch-run-value-design.md).
-- MySQL 에만 둡니다. schema_types.json 에 넣지 않습니다(D1 대조 대상 아님).
-- 만들기는 migrator 계정으로 한 번(evan 허락). 쓰기는 bstats_loader, 읽기는 bstats_api.
CREATE TABLE IF NOT EXISTS `run_expectancy` (
  `season` SMALLINT NOT NULL,
  `bases` TINYINT NOT NULL,
  `outs` TINYINT NOT NULL,
  `balls` TINYINT NOT NULL,
  `strikes` TINYINT NOT NULL,
  `re` DOUBLE NOT NULL,
  `n` INT NOT NULL,
  PRIMARY KEY (`season`, `bases`, `outs`, `balls`, `strikes`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE IF NOT EXISTS `pitch_run_value` (
  `season` SMALLINT NOT NULL,
  `pitcher_ID` INT NOT NULL,
  `pitch_type` VARCHAR(20) NOT NULL,
  `stands` CHAR(1) NOT NULL,
  `n` INT NOT NULL,
  `rv` DOUBLE NOT NULL,
  PRIMARY KEY (`season`, `pitcher_ID`, `pitch_type`, `stands`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
```

(작업 전 `SHOW CREATE TABLE play_by_play` 로 기본 문자셋·정렬이 같은지 보고 맞춥니다.)

- [ ] **Step 4: 통과 확인**

Run: `PYTHONUTF8=1 py -m pytest tests/test_pitch_run_value.py tests/test_pitch_value_calc.py -q`
Expected: PASS

- [ ] **Step 5: 2024 를 쓰기 없이 돌려 보기**

Run: `PYTHONUTF8=1 BSTATS_MYSQL_SETTINGS=~/.bstats/mysql_proxy.json py data_collection/pitch_run_value.py --season 2024 --dry-run`
Expected: `2024: PBP 234741행, 상태 288칸(최소 6공), …, 리그 합 +3xx점` (설계 문서 시험 계산과 같은 크기). 결과를 evan 에게 보여 드림.

- [ ] **Step 6: 커밋**

```bash
git add -- data_collection/pitch_run_value.py tests/test_pitch_run_value.py migration/mysql/pitch_value_schema.sql
git commit -m "feat(pitch-value): 시즌 계산 스크립트·표 정의" -- data_collection/pitch_run_value.py tests/test_pitch_run_value.py migration/mysql/pitch_value_schema.sql
```

### Task 3: 표 만들기·채우기(evan 허락 필요)

- [ ] **Step 1:** DB 세션에 "MySQL 에 run_expectancy·pitch_run_value 두 표를 만든다"고 알리고 겹치는지 확인합니다.
- [ ] **Step 2:** evan 허락을 받습니다(새 표 만들기 + 2016~2026 채우기).
- [ ] **Step 3:** migrator 계정으로 `pitch_value_schema.sql` 을 실행합니다. 그 뒤 `SHOW GRANTS FOR 'bstats_loader'@'%'`, `SHOW GRANTS FOR 'bstats_api'@'%'` 로 새 표에 쓰기·읽기 권한이 닿는지 봅니다(DB 단위 권한이면 그대로 됨). 안 닿으면 evan 에게 알리고 GRANT 문을 받습니다.
- [ ] **Step 4:** `py data_collection/pitch_run_value.py --from 2016 --to 2026` (loader 계정 설정 `~/.bstats/mysql_loader_proxy.json`). 시즌마다 출력 줄을 남깁니다.
- [ ] **Step 5:** 확인 질의: 시즌별 `run_expectancy` 288행, `pitch_run_value` 행 수, 2024 리그 합이 dry-run 과 같은지.

### Task 4: API

**Files:**
- Create: `src/routes/pitchValues.js`
- Modify: `src/index.js` (import 한 줄, `router.add('GET', '/players/:id/pitch_values', pitchValues);` 를 `/players/:id/usage` 아래)
- Test: `test/pitchvalues.test.js`

**Interfaces:**
- Consumes: 표 `pitch_run_value`(Task 3), `robustPlayerLookup`(src/routes/players.js), `movementCacheControl`(src/routes/movementAvg.js), `hasSeason`(src/lib/shard.js)
- Produces: `shapePitchValues(rows) -> [{pitch_type, n_l, rv_l, n_r, rv_r, n, rv}]`, 핸들러 `pitchValues(request, env, ctx, params)`

- [ ] **Step 1: 실패하는 시험** — `test/pitchvalues.test.js`

```js
import { test } from 'node:test';
import assert from 'node:assert/strict';

import { pitchValues, shapePitchValues, PITCH_VALUES_SQL } from '../src/routes/pitchValues.js';

function fakeDb(handler) {
  const calls = [];
  return {
    calls,
    prepare(sql) {
      return {
        params: [],
        bind(...p) { this.params = p; return this; },
        async all() { calls.push({ sql, params: this.params }); return { results: handler(sql, this.params) || [] }; },
        async first() { calls.push({ sql, params: this.params }); return (handler(sql, this.params) || [])[0] || null; },
      };
    },
  };
}

const req = (path) => new Request(`https://x.test${path}`);
const PLAYER = { player_id: '65933' };

test('L/R 를 한 줄로 합치고 소수 첫째 자리로 맞춥니다', () => {
  const out = shapePitchValues([
    { pitch_type: '직구', stands: 'L', n: 512, rv: 3.14 },
    { pitch_type: '직구', stands: 'R', n: 940, rv: -1.26 },
    { pitch_type: '커브', stands: 'R', n: 30, rv: 0.04 },
  ]);
  assert.deepEqual(out, [
    { pitch_type: '직구', n_l: 512, rv_l: 3.1, n_r: 940, rv_r: -1.3, n: 1452, rv: 1.9 },
    { pitch_type: '커브', n_l: 0, rv_l: 0, n_r: 30, rv_r: 0, n: 30, rv: 0 },
  ]);
});

test('공이 많은 구종부터, 같으면 이름 순입니다', () => {
  const out = shapePitchValues([
    { pitch_type: '커브', stands: 'R', n: 10, rv: 0 },
    { pitch_type: '슬라이더', stands: 'R', n: 10, rv: 0 },
    { pitch_type: '직구', stands: 'L', n: 50, rv: 0 },
  ]);
  assert.deepEqual(out.map((r) => r.pitch_type), ['직구', '슬라이더', '커브']);
});

test('질의는 표에서 투수·시즌으로 읽기만 합니다', () => {
  assert.match(PITCH_VALUES_SQL, /FROM pitch_run_value/);
  assert.match(PITCH_VALUES_SQL, /WHERE pitcher_ID = \? AND season = \?/);
});

test('응답 모양과 캐시', async () => {
  const db = fakeDb((sql) => (sql.includes('FROM players') ? [PLAYER]
    : [{ pitch_type: '직구', stands: 'R', n: 3, rv: 0.25 }]));
  const res = await pitchValues(req('/players/65933/pitch_values?season=2025'), { DB: db, DB_BACKEND: 'mysql' }, {}, { id: '65933' });
  assert.equal(res.status, 200);
  assert.deepEqual(await res.json(), {
    player_id: '65933', season: 2025,
    rows: [{ pitch_type: '직구', n_l: 0, rv_l: 0, n_r: 3, rv_r: 0.3, n: 3, rv: 0.3 }],
  });
  assert.match(res.headers.get('cache-control'), /s-maxage=/);
});

test('season 형식 오류 400, 2016 전 404, 선수 없음 404', async () => {
  const db = fakeDb((sql) => (sql.includes('FROM players') ? [PLAYER] : []));
  const env = { DB: db, DB_BACKEND: 'mysql' };
  assert.equal((await pitchValues(req('/players/65933/pitch_values?season=x'), env, {}, { id: '65933' })).status, 400);
  assert.equal((await pitchValues(req('/players/65933/pitch_values'), env, {}, { id: '65933' })).status, 400);
  assert.equal((await pitchValues(req('/players/65933/pitch_values?season=2015'), env, {}, { id: '65933' })).status, 404);
  const none = fakeDb(() => []);
  assert.equal((await pitchValues(req('/players/1/pitch_values?season=2025'), { DB: none, DB_BACKEND: 'mysql' }, {}, { id: '1' })).status, 404);
});

test('그 시즌 공이 없으면 빈 rows', async () => {
  const db = fakeDb((sql) => (sql.includes('FROM players') ? [PLAYER] : []));
  const res = await pitchValues(req('/players/65933/pitch_values?season=2025'), { DB: db, DB_BACKEND: 'mysql' }, {}, { id: '65933' });
  assert.deepEqual((await res.json()).rows, []);
});

test('DB 오류는 503·no-store', async () => {
  const db = fakeDb((sql) => { if (sql.includes('pitch_run_value')) throw new Error('boom'); return [PLAYER]; });
  const res = await pitchValues(req('/players/65933/pitch_values?season=2025'), { DB: db, DB_BACKEND: 'mysql' }, {}, { id: '65933' });
  assert.equal(res.status, 503);
  assert.equal(res.headers.get('cache-control'), 'no-store');
});
```

- [ ] **Step 2: 실패 확인** — Run: `node --test test/pitchvalues.test.js` → FAIL(모듈 없음)

- [ ] **Step 3: 구현** — `src/routes/pitchValues.js`

```js
// 투수의 구종 가치입니다(2026-10-04).
//
// 공 하나의 가치 = (던진 뒤 기대 득점 − 던지기 전 기대 득점) + 그 공의 득점,
// 투수 쪽 부호(실점을 막으면 +). 매일 data_collection/pitch_run_value.py 가
// MySQL pitch_run_value 표에 미리 계산해 둡니다. 여기서는 읽기만 합니다
// (Workers 무료 CPU 10ms). 설계: docs/superpowers/specs/2026-10-04-pitch-run-value-design.md
//
//     GET /players/65933/pitch_values?season=2025
//     → { player_id, season, rows: [ { pitch_type, n_l, rv_l, n_r, rv_r, n, rv } ] }
//
// 표는 MySQL 에만 있습니다. D1 으로 되돌리면 표가 없어 503 입니다.
import { json, dbError } from '../lib/respond.js';
import { hasSeason } from '../lib/shard.js';
import { robustPlayerLookup } from './players.js';
import { movementCacheControl } from './movementAvg.js';

export const PITCH_VALUE_FIRST_SEASON = 2016;

export const PITCH_VALUES_SQL = `
  SELECT pitch_type, stands, n, rv
  FROM pitch_run_value
  WHERE pitcher_ID = ? AND season = ?
`;

function round1(v) {
  const r = Math.round(Number(v) * 10) / 10;
  return Object.is(r, -0) ? 0 : r;
}

/** 구종마다 L/R 를 한 줄로 합칩니다. 공이 많은 구종부터, 같으면 이름 순입니다. */
export function shapePitchValues(rows) {
  const by = new Map();
  for (const r of rows || []) {
    if (!by.has(r.pitch_type)) by.set(r.pitch_type, { n_l: 0, rv_l: 0, n_r: 0, rv_r: 0 });
    const acc = by.get(r.pitch_type);
    if (r.stands === 'L') { acc.n_l += Number(r.n); acc.rv_l += Number(r.rv); }
    else { acc.n_r += Number(r.n); acc.rv_r += Number(r.rv); }
  }
  const out = [...by].map(([pitch_type, a]) => ({
    pitch_type,
    n_l: a.n_l, rv_l: round1(a.rv_l),
    n_r: a.n_r, rv_r: round1(a.rv_r),
    n: a.n_l + a.n_r, rv: round1(a.rv_l + a.rv_r),
  }));
  out.sort((a, b) => (b.n - a.n)
    || (a.pitch_type < b.pitch_type ? -1 : a.pitch_type > b.pitch_type ? 1 : 0));
  return out;
}

export async function pitchValues(request, env, ctx, params) {
  const raw = new URL(request.url).searchParams.get('season');
  const season = /^\d{4}$/.test(raw || '') ? Number(raw) : null;
  if (season === null) return json({ detail: 'season=YYYY 가 필요합니다' }, 400);
  if (season < PITCH_VALUE_FIRST_SEASON || !hasSeason(season)) {
    return json({ detail: `구종 가치는 ${PITCH_VALUE_FIRST_SEASON}년부터 수집한 시즌까지만 있습니다` }, 404);
  }
  try {
    const player = await robustPlayerLookup(env.DB, params.id);
    if (!player) return json({ detail: 'Player not found' }, 404);
    const { results } = await env.DB.prepare(PITCH_VALUES_SQL)
      .bind(Number(player.player_id), season).all();
    const res = json({ player_id: params.id, season, rows: shapePitchValues(results) });
    res.headers.set('cache-control', movementCacheControl(season));
    return res;
  } catch (err) {
    return dbError(err);
  }
}
```

- [ ] **Step 4: 통과 확인** — Run: `node --test test/pitchvalues.test.js test/sqlportable.test.js && npm test` → 모두 PASS

- [ ] **Step 5: 커밋**

```bash
git add -- src/routes/pitchValues.js test/pitchvalues.test.js
git commit -m "feat(api): 투수 구종 가치 /players/:id/pitch_values" -- src/routes/pitchValues.js test/pitchvalues.test.js src/index.js
```

### Task 5: 매일 다시 만들기·계보·열 설명

**Files:**
- Modify: `.github/workflows/daily.yml` (팀 순위 결과 기록 단계 뒤)
- Modify: `data_collection/record_job_run.py` (KNOWN_JOBS)
- Modify: `database/lineage_writes.json`, `database/column_descriptions.json`

- [ ] **Step 1:** DB 세션(dk-analytics-28)에 daily 단계 추가를 알리고 겹치는지 확인합니다.
- [ ] **Step 2:** daily.yml 에 두 단계를 넣습니다.

```yaml
      # 구종 가치(투수 × 구종 × 타자 손)와 기대 득점 표를 올해만 다시 만듭니다.
      # MySQL 에서 읽고 MySQL 에만 씁니다. 설계 docs/superpowers/specs/2026-10-04-pitch-run-value-design.md
      - name: 구종 가치 계산
        id: pitch_values
        continue-on-error: true
        run: python data_collection/pitch_run_value.py --current

      - name: 구종 가치 결과 기록
        if: always()
        continue-on-error: true
        run: |
          python data_collection/record_job_run.py --job pitch_values \
            --status ${{ steps.pitch_values.outcome == 'success' && 'ok' || (steps.pitch_values.outcome == 'skipped' && 'skip' || 'fail') }}
```

- [ ] **Step 3:** `record_job_run.py` KNOWN_JOBS 에 `"pitch_values"` 를 더합니다(주석: 구종 가치, MySQL 전용).
- [ ] **Step 4:** `lineage_writes.json` 에 항목을 더합니다.

```json
    "data_collection/pitch_run_value.py": {
      "sources": [],
      "writes": ["pitch_run_value", "run_expectancy"],
      "reads": ["play_by_play"],
      "status_keys": {"daily": "pitch_values"},
      "note": "MySQL 전용 파생 표입니다. 시즌 단위로 다시 만듭니다."
    },
```

- [ ] **Step 5:** `column_descriptions.json` 에 두 표 열 설명을 더합니다(DB 용어 대신 쉬운 말).
- [ ] **Step 6:** 화면 세션(dk-analytics-6e / 페이지 담당)에 데이터 탐색 페이지 수집 일정 표에 한 줄(`data-job="pitch_values"`, "구종 가치 계산, 매일") 추가를 부탁합니다(`test_cron_table_parity`).
- [ ] **Step 7:** `PYTHONUTF8=1 py scripts/build_lineage.py` → `PYTHONUTF8=1 py -m pytest tests -q` → `npm test`. 페이지 줄이 들어오기 전 cron parity 실패는 화면 세션 몫으로 기록.
- [ ] **Step 8:** 경로를 붙여 커밋합니다.

### Task 6: push·배포·알림(evan 허락 필요)

- [ ] **Step 1:** push 직전 `git log --oneline origin/main..main` 으로 목록을 다시 보고, evan 에게 올라갈 커밋을 알려 허락받습니다.
- [ ] **Step 2:** push → `npx wrangler@4 deploy`(Desktop/b_project, `src/` 에 남의 미커밋 변경이 없는지 먼저 확인).
- [ ] **Step 3:** 운영에서 `/players/65933/pitch_values?season=2025`·`?season=2015`(404) 확인, wrangler tail 로 CPU 확인.
- [ ] **Step 4:** 선수 분석 세션(dk-analytics-6e)에 주소와 예시 응답을 알립니다.
