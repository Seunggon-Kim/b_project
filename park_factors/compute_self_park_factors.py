# -*- coding: utf-8 -*-
"""
Compute self KBO park factors (2015-2026) from play_by_play and load into self_park_factor.
- Engine: FanGraphs operational form PF = 1000 * 10H/(9R+H)  (T=10, un-halved), Statiz convention.
- run_pf: per-game runs (home vs road). Components (1B/2B/3B/HR/SLG): per IN-PLAY PA.
- 3-year trailing window per season (forward-filled for earliest cohort; park-opening years use 1-2y).
- Smoothing X frozen (calibrated once vs Statiz 2025; the pipeline does NOT read Statiz at runtime).
Re-run safe: rebuilds self_park_factor from scratch each run (latest PBP -> updated 2026).
"""
import sqlite3, datetime
import os
from pathlib import Path
# DB 경로: 환경변수 KBO_DB 우선, 없으면 저장소 기준 상대경로.
# EC2 절대경로는 Windows 와 GitHub Actions 러너에서 동작하지 않습니다.
DB = os.environ.get("KBO_DB") or str(
    Path(__file__).resolve().parent.parent / "database" / "kbo_stats.db"
)
con = sqlite3.connect(DB); con.row_factory = sqlite3.Row; cur = con.cursor()

VALID_YEARS = list(range(2015, 2027))
SECONDARY = {'청주','울산','포항'}
# smoothing toward neutral 1000: Final = 1000 - (1000-raw)*X.  Calibrated once vs Statiz 2025 (run MAE~19).
X = {'run': 1.0, 'b1': 0.44, 'b2': 0.60, 'b3': 0.62, 'hr': 0.72, 'slg': 0.40}
COL = {'run':'run_pf','b1':'single_pf','b2':'double_pf','b3':'triple_pf','hr':'hr_pf','slg':'slg_pf'}
METRICS = ['run','b1','b2','b3','hr','slg']
ALL_TEAMS = ['LG','OB','HT','KT','LT','SK','WO','NC','SS','HH']

def team_park(team, season):
    if team in ('LG','OB'): return '서울종합운동장 야구장'
    if team == 'HT': return '광주-KIA 챔피언스 필드'
    if team == 'KT': return '케이티위즈파크'
    if team == 'LT': return '사직야구장'
    if team == 'SK': return '인천 SSG 랜더스필드'
    if team == 'WO': return '고척스카이돔' if season >= 2016 else '목동야구장'
    if team == 'NC': return '창원NC파크' if season >= 2019 else '마산종합운동장 야구장'
    if team == 'SS': return '대구 삼성 라이온즈파크' if season >= 2016 else '대구시민운동장 야구장'
    if team == 'HH': return '대전 한화생명 볼파크' if season >= 2025 else '대전 한밭야구장'
    return None

def park_full(home_team, stadium_short, season):
    return None if stadium_short in SECONDARY else team_park(home_team, season)

def load_games(years):
    ylist = ",".join("'%d'" % y for y in years)
    q = f"""SELECT gameID, MAX(home) home, MAX(away) away, MAX(stadium) stadium,
            CAST(substr(gameID,1,4) AS INT) season, SUM(runs_scored) total_runs,
            SUM(CASE WHEN pa_result IN ('안타','내야안타','번트 안타') THEN 1 ELSE 0 END) b1,
            SUM(CASE WHEN pa_result='2루타' THEN 1 ELSE 0 END) b2,
            SUM(CASE WHEN pa_result='3루타' THEN 1 ELSE 0 END) b3,
            SUM(CASE WHEN pa_result='홈런' THEN 1 ELSE 0 END) hr,
            SUM(CASE WHEN pa_result IS NOT NULL AND pa_result NOT IN
                ('삼진','볼넷','몸에 맞는 볼','자동 고의4구','고의4구','낫아웃 출루') THEN 1 ELSE 0 END) inplay
            FROM play_by_play WHERE substr(gameID,1,4) IN ({ylist}) GROUP BY gameID"""
    games = []
    for r in cur.execute(q):
        g = dict(r); g['stadium_full'] = park_full(g['home'], g['stadium'], g['season'])
        g['tb'] = g['b1'] + 2*g['b2'] + 3*g['b3'] + 4*g['hr']; games.append(g)
    return games

ALLG = load_games(VALID_YEARS)

def window_for(Y):
    base = [y for y in (Y-2, Y-1, Y) if 2015 <= y <= 2026]
    while len(base) < 3 and max(base) + 1 <= 2026: base.append(max(base) + 1)
    return sorted(set(base))

def rawpf(hn, hd, rn, rd):
    if hd == 0 or rd == 0: return None
    H = hn/hd; R = rn/rd
    return None if (9*R + H) == 0 else 1000.0*(10.0*H)/(9.0*R + H)

def regress(raw, m): return None if raw is None else 1000.0 - (1000.0 - raw)*X[m]

def compute_year(Y):
    win = set(window_for(Y)); wg = [g for g in ALLG if g['season'] in win]
    parks = sorted({g['stadium_full'] for g in wg if g['stadium_full']})
    out = {}
    for p in parks:
        teams = {t for t in ALL_TEAMS for s in win if team_park(t, s) == p}
        home = [g for g in wg if g['stadium_full'] == p]
        S = {g['season'] for g in home}
        if Y not in S: continue
        road = [g for g in wg if g['away'] in teams and g['stadium_full'] != p and g['season'] in S]
        if not home or not road: continue
        run = rawpf(sum(g['total_runs'] for g in home), len(home), sum(g['total_runs'] for g in road), len(road))
        hin = sum(g['inplay'] for g in home); rin = sum(g['inplay'] for g in road)
        comp = {k: rawpf(sum(g[k] for g in home), hin, sum(g[k] for g in road), rin) for k in ('b1','b2','b3','hr','tb')}
        out[p] = {'yrs': len(S), 'win': sorted(S), 'games_Y': sum(1 for g in home if g['season']==Y),
                  'run': run, 'b1': comp['b1'], 'b2': comp['b2'], 'b3': comp['b3'], 'hr': comp['hr'], 'slg': comp['tb']}
    return out

now = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
cur.execute("DROP TABLE IF EXISTS self_park_factor")
cur.execute("""CREATE TABLE self_park_factor (
  season INTEGER, stadium TEXT, games INTEGER,
  run_pf INTEGER, single_pf INTEGER, double_pf INTEGER, triple_pf INTEGER, hr_pf INTEGER, slg_pf INTEGER,
  source TEXT DEFAULT 'self_pbp_3y', captured_at TEXT, yrs INTEGER, window TEXT,
  PRIMARY KEY (season, stadium) )""")
rows = []
for Y in VALID_YEARS:
    for p, d in sorted(compute_year(Y).items()):
        fin = {COL[m]: (None if d[m] is None else int(round(regress(d[m], m)))) for m in METRICS}
        rows.append((Y, p, d['games_Y'], fin['run_pf'], fin['single_pf'], fin['double_pf'], fin['triple_pf'],
                     fin['hr_pf'], fin['slg_pf'], 'self_pbp_3y', now, d['yrs'], ",".join(map(str, d['win']))))
cur.executemany("""INSERT INTO self_park_factor
  (season,stadium,games,run_pf,single_pf,double_pf,triple_pf,hr_pf,slg_pf,source,captured_at,yrs,window)
  VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""", rows)
con.commit()
print(f"[compute_self_park_factors] inserted {len(rows)} rows ({now})")
for r in cur.execute("SELECT season, COUNT(*) n FROM self_park_factor GROUP BY season ORDER BY season"):
    print(f"  {r['season']}: {r['n']} parks")
print("  2026:", [(r['stadium'], r['run_pf']) for r in cur.execute("SELECT stadium, run_pf FROM self_park_factor WHERE season=2026 ORDER BY run_pf")])
con.close()
