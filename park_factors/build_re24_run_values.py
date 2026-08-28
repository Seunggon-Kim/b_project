# -*- coding: utf-8 -*-
"""
Rebuild re24_matrix_by_season + kbo_run_values_by_season from play_by_play.

Method: standard RE24 run expectancy + delta-RE linear weights.
  RE24[base_state,outs] = mean runs scored by batting team from that state to
    end of half-inning (empirical run expectancy).
  run value(PA)  = RE_after - RE_before + runs_on_play
    RE_after = RE24 of the next PA's starting state in the half-inning (0 if the
               PA ends the inning); runs_on_play = batting-team runs in the gap.
  rv_mean(event) = mean run value over PAs of that event_type.

base_state encoding (matches the existing table): 1B=100, 2B=10, 3B=1 (occupancy bits).
Seasons: 2015..2026 rebuilt from current PBP. 2026 is partial (in-progress) — included
as its own row set but EXCLUDED from the season=0 pooled baseline.
season=0 = pooled run values over all COMPLETE seasons (2015..2025).
Per real season we store the 12 canonical events; season=0 stores all event types.

Run with --write to back up and overwrite; without it, dry-run prints a summary only.
"""
import sqlite3, sys, numpy as np, pandas as pd
import os
from pathlib import Path
from collections import defaultdict

# DB 경로: 환경변수 KBO_DB 우선, 없으면 저장소 기준 상대경로.
# EC2 절대경로는 Windows 와 GitHub Actions 러너에서 동작하지 않습니다.
DB = os.environ.get("KBO_DB") or str(
    Path(__file__).resolve().parent.parent / "database" / "kbo_stats.db"
)
# Rolling 1-step backup (matches build_wrc_plus convention). The immutable
# pre-rebuild snapshot is preserved separately as *_bak_20260606.
BACKUP_SUFFIX='_bak'
COMPLETE=list(range(2015,2026))   # 2015..2025 pooled into season=0
ALLYEARS=list(range(2015,2027))   # 2015..2026 rebuilt

MAP={
 '안타':'1B','내야안타':'1B','번트 안타':'1B','2루타':'2B','3루타':'3B','홈런':'HR',
 '볼넷':'uBB','자동 고의4구':'IBB','고의4구':'IBB','고의 4구':'IBB','자동 고의 4구':'IBB',
 '몸에 맞는 볼':'HBP','몸에 맞는 공':'HBP','삼진':'SO',
 '필드 아웃':'OutInPlay','포스 아웃':'OutInPlay','병살타':'OutInPlay','삼중살':'OutInPlay','타구맞음 아웃':'OutInPlay',
 '실책':'ROE','희생번트 실책':'ROE','희생플라이 실책':'ROE',
 '희생번트':'SacBunt','희생번트 야수선택':'SacBunt','희생플라이':'SacFly',
 '야수 선택':'FC','타격방해':'INT','낫아웃 출루':'UNKNOWN','낫아웃 다른 주자 수비':'UNKNOWN',
}
CANON12=['1B','2B','3B','HBP','HR','IBB','OutInPlay','ROE','SO','SacBunt','SacFly','uBB']

def isval(s): return s.notna() & (s.astype(str)!='None') & (s.astype(str)!='')

def load_year(con, yr):
    # **정규시즌만 씁니다.** 득점기대값은 정규시즌 기준 지표인데, 날짜로만
    # 거르면 10~11월 포스트시즌 타석이 그대로 섞입니다.
    #
    # gameID 앞 네 자리로 거르는 방법은 쓰지 않습니다. 포스트시즌은 그
    # 자리에 연도 대신 시리즈 코드가 들어가고(3333·4444·5555·7777),
    # 6666(순위결정전)은 코드처럼 생겼지만 정규시즌입니다. games.game_type
    # 이 이미 그 판정을 담고 있으니 그것을 씁니다(data_collection/game_type.py).
    q=("SELECT p.pbp_id,p.game_date,p.away,p.home,p.inning,p.inning_topbot,p.outs,"
       "p.score_home,p.score_away,p.pa_result,p.on_1b,p.on_2b,p.on_3b "
       "FROM play_by_play p JOIN games g ON g.game_id = p.gameID "
       "WHERE g.game_type='정규시즌' "
       "AND p.game_date>=%d0101 AND p.game_date<=%d1231 ORDER BY p.pbp_id" % (yr,yr))
    df=pd.read_sql_query(q,con)
    for c in ['outs','inning','score_home','score_away','pbp_id']:
        df[c]=pd.to_numeric(df[c],errors='coerce')
    return df

def compute_season(df):
    """Return (re_df, pa_df). pa_df has event_type + rv per PA."""
    t=df.loc[df.outs<3].copy()
    pa=t.loc[isval(t.pa_result)].copy()
    # occupancy bits matching stored encoding: 1B=100, 2B=10, 3B=1
    pa['base_state']=(np.where(isval(pa.on_1b),100,0)
                      +np.where(isval(pa.on_2b),10,0)
                      +np.where(isval(pa.on_3b),1,0))
    pa['outs_before']=pa.outs.astype(int)
    pa['batruns']=np.where(pa.inning_topbot=='초',pa.score_away,pa.score_home)
    hi=['game_date','home','away','inning','inning_topbot']
    pa=pa.sort_values(hi+['pbp_id'])
    g=pa.groupby(hi)
    pa['runs_after']=g.batruns.transform('max')-pa.batruns
    pa=pa.loc[pa.runs_after.notna()].copy()
    # RE24 (run expectancy per base-out)
    re=pa.groupby(['base_state','outs_before']).runs_after.agg(re_value='mean',n_obs='count').reset_index()
    RE={(int(r.base_state),int(r.outs_before)):r.re_value for r in re.itertuples()}
    # delta-RE run value per PA
    g=pa.groupby(hi)
    pa['next_base']=g.base_state.shift(-1)
    pa['next_outs']=g.outs_before.shift(-1)
    pa['next_batruns']=g.batruns.shift(-1)
    is_last=pa.next_base.isna()
    re_after=np.where(is_last,0.0,
        [RE.get((int(b),int(o)),np.nan) for b,o in zip(pa.next_base.fillna(-1),pa.next_outs.fillna(-1))])
    runs_on_play=np.where(is_last, pa.runs_after, pa.next_batruns-pa.batruns)
    re_before=np.array([RE[(int(b),int(o))] for b,o in zip(pa.base_state,pa.outs_before)])
    pa['rv']=re_after-re_before+runs_on_play
    pa['event_type']=pa.pa_result.map(MAP).fillna('UNKNOWN')
    return re, pa

def main(write):
    con=sqlite3.connect(DB)
    re24_rows=[]      # (season,outs_before,base_state,re_value,n_obs)
    rv_rows=[]        # (season,event_type,rv_mean,n_obs)
    pool_sum=defaultdict(float); pool_cnt=defaultdict(int)
    summary=[]
    for yr in ALLYEARS:
        df=load_year(con,yr)
        if len(df)==0:
            summary.append((yr,0,'no data')); continue
        re,pa=compute_season(df)
        for r in re.itertuples():
            re24_rows.append((yr,int(r.outs_before),int(r.base_state),float(r.re_value),int(r.n_obs)))
        ev=pa.groupby('event_type').rv.agg(rv_mean='mean',n_obs='count')
        # per-season: 12 canonical events only (matches existing table shape)
        for e in CANON12:
            if e in ev.index:
                rv_rows.append((yr,e,float(ev.loc[e,'rv_mean']),int(ev.loc[e,'n_obs'])))
        # accumulate season=0 pool over COMPLETE seasons, all events
        if yr in COMPLETE:
            grp=pa.groupby('event_type').rv.agg(['sum','count'])
            for e,row in grp.iterrows():
                pool_sum[e]+=float(row['sum']); pool_cnt[e]+=int(row['count'])
        summary.append((yr,len(pa),'%d events'%ev.shape[0]))
    # season=0 pooled rows (all events)
    for e in sorted(pool_cnt, key=lambda x:-pool_cnt[x]):
        rv_rows.append((0,e,pool_sum[e]/pool_cnt[e],pool_cnt[e]))

    # ---- summary ----
    print("=== per-season PA counts ===")
    for yr,n,note in summary: print(f"  {yr}: PA={n:7d}  {note}")
    print("\n=== run_values rows to write: %d (re24 rows: %d) ===" % (len(rv_rows),len(re24_rows)))
    def show(season):
        rows=[r for r in rv_rows if r[0]==season]
        print(f"  season={season}:")
        for s,e,m,n in sorted(rows,key=lambda x:x[1]):
            print(f"     {e:10} rv_mean={m:+.4f}  n_obs={n}")
    show(2025); show(2026); show(0)

    if not write:
        print("\n[DRY RUN] no DB changes. Re-run with --write to back up + overwrite.")
        con.close(); return

    cur=con.cursor()
    print("\n=== WRITING ===")
    # 표가 없으면 만듭니다. 없는 상태에서 바로 백업을 뜨면
    # `no such table` 로 죽습니다. 주간 워크플로가 실제로 그렇게
    # 실패했습니다. 러너는 D1 에서 받은 표만 갖고 있는데, 이 두 개가
    # 내려받기 목록에 없었습니다. 목록에도 넣었지만, 처음 도는
    # 환경에서도 되도록 여기서도 만듭니다.
    cur.execute("""CREATE TABLE IF NOT EXISTS kbo_run_values_by_season (
        season INTEGER, event_type TEXT, rv_mean REAL, n_obs INTEGER,
        PRIMARY KEY(season, event_type))""")
    cur.execute("""CREATE TABLE IF NOT EXISTS re24_matrix_by_season (
        season INTEGER, outs_before INTEGER, base_state INTEGER,
        re_value REAL, n_obs INTEGER,
        PRIMARY KEY(season, outs_before, base_state))""")
    for t in ['kbo_run_values_by_season','re24_matrix_by_season']:
        cur.execute('DROP TABLE IF EXISTS "%s%s"'%(t,BACKUP_SUFFIX))
        cur.execute('CREATE TABLE "%s%s" AS SELECT * FROM "%s"'%(t,BACKUP_SUFFIX,t))
        print("  backed up %s -> %s%s (%d rows)"%(t,t,BACKUP_SUFFIX,
              cur.execute('SELECT COUNT(*) FROM "%s%s"'%(t,BACKUP_SUFFIX)).fetchone()[0]))
    cur.execute("DELETE FROM kbo_run_values_by_season")
    cur.executemany("INSERT INTO kbo_run_values_by_season(season,event_type,rv_mean,n_obs) VALUES(?,?,?,?)",rv_rows)
    cur.execute("DELETE FROM re24_matrix_by_season")
    cur.executemany("INSERT INTO re24_matrix_by_season(season,outs_before,base_state,re_value,n_obs) VALUES(?,?,?,?,?)",re24_rows)
    con.commit()
    rv_n=cur.execute("SELECT COUNT(*) FROM kbo_run_values_by_season").fetchone()[0]
    re_n=cur.execute("SELECT COUNT(*) FROM re24_matrix_by_season").fetchone()[0]
    seasons=[r[0] for r in cur.execute("SELECT DISTINCT season FROM kbo_run_values_by_season ORDER BY season")]
    print("  kbo_run_values_by_season rows=%d  seasons=%s"%(rv_n,seasons))
    print("  re24_matrix_by_season rows=%d"%re_n)
    con.close()
    print("DONE.")

if __name__=='__main__':
    main('--write' in sys.argv)
