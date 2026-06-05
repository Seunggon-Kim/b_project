# -*- coding: utf-8 -*-
"""
COMPLETE builder for wrc_plus_comparison + weighted_pf_by_batter_season.
Rebuilds wOBA/wRAA (kbo_official_batter_stats + kbo_woba_weights_by_season) AND park-factor fields
(self_park_factor + play_by_play). Replaces the missing original builder so re-runs pick up new batting lines
AND new PBP. Formulas reverse-engineered exactly (wOBA verified to 1e-5).
  wOBA = (wBB*BB + wHBP*HBP + w1B*1B + w2B*2B + w3B*3B + wHR*HR)/(AB+BB+SF+HBP)   [BB incl IBB; 1B=H-2B-3B-HR]
  wRAA = (wOBA - lg_wOBA)/wOBA_scale * PA
  wRC  = K + (2 - PF)*100 ,  K = (wraa_per_pa / L[season])*100   (L = season run constant, derived from prior rows)
"""
import sqlite3, statistics
DB='/home/ubuntu/b_project/database/kbo_stats.db'
con=sqlite3.connect(DB); con.row_factory=sqlite3.Row; cur=con.cursor()
YEARS=list(range(2015,2027)); YSTR=[str(y) for y in YEARS]; WRC_MIN_PA=50

def stadium_full(short, season):
    if short in ('대전','한밭'): return '대전 한화생명 볼파크' if season>=2025 else '대전 한밭야구장'
    return {'잠실':'서울종합운동장 야구장','사직':'사직야구장','광주':'광주-KIA 챔피언스 필드',
            '문학':'인천 SSG 랜더스필드','수원':'케이티위즈파크',
            '고척':'고척스카이돔' if season>=2016 else '목동야구장','목동':'목동야구장',
            '대구':'대구 삼성 라이온즈파크' if season>=2016 else '대구시민운동장 야구장','시민':'대구시민운동장 야구장',
            '창원':'창원NC파크' if season>=2019 else '마산종합운동장 야구장','마산':'마산종합운동장 야구장',
            '울산':'울산문수야구장','청주':'청주야구장','포항':'포항야구장'}.get(short, None)

self_pf={}
for r in cur.execute("SELECT season,stadium,run_pf,hr_pf,slg_pf FROM self_park_factor"):
    self_pf[(r['season'],r['stadium'])]=(r['run_pf'],r['hr_pf'],r['slg_pf'])
def pf_of(season,full,idx):
    v=self_pf.get((season,full)); return float(v[idx]) if v else 1000.0

W={r['season']:r for r in cur.execute("SELECT season,wOBA_scale,fg_w1B,fg_w2B,fg_w3B,fg_wHR,fg_wBB,fg_wHBP FROM kbo_woba_weights_by_season")}

latest=max(YEARS)
src=cur.execute("SELECT MAX(season) FROM team_stadium_by_season WHERE season < ?", (latest,)).fetchone()[0]
cur.execute("DELETE FROM team_stadium_by_season WHERE season=?", (latest,))
cur.execute("INSERT INTO team_stadium_by_season (player_team,season,stadium) SELECT player_team,?,stadium FROM team_stadium_by_season WHERE season=?", (latest,src))
TEAM_PARK={(r['player_team'],r['season']):r['stadium'] for r in cur.execute("SELECT player_team,season,stadium FROM team_stadium_by_season")}

# season run constant L derived from existing rows (PF-invariant; L = wraa_per_pa*100/K)
tmp={}
for r in cur.execute("SELECT season,PA,wRAA_FG,wRC_home,pf_home FROM wrc_plus_comparison WHERE PA>=50"):
    K=r['wRC_home']-(2.0-r['pf_home']/1000.0)*100.0
    if abs(K)<10 or not r['PA']: continue   # |K|>=10 for numerical stability; median over many rows -> exact season L
    tmp.setdefault(r['season'],[]).append((r['wRAA_FG']/r['PA'])*100.0/K)
L={s:statistics.median(v) for s,v in tmp.items()}
print("season L:", {s:round(L[s],5) for s in sorted(L)})

LGW={}
for r in cur.execute("""SELECT season, SUM(base_on_balls) bb, SUM(hit_by_pitch) hbp,
        SUM(single-double-triple-home_run) one, SUM(double) d2, SUM(triple) d3, SUM(home_run) hr,
        SUM(at_bat+base_on_balls+sacrifice_fly+hit_by_pitch) den FROM kbo_official_batter_stats GROUP BY season"""):
    w=W.get(r['season'])
    if w and r['den']:
        LGW[r['season']]=(w['fg_wBB']*r['bb']+w['fg_wHBP']*r['hbp']+w['fg_w1B']*r['one']+w['fg_w2B']*r['d2']+w['fg_w3B']*r['d3']+w['fg_wHR']*r['hr'])/r['den']

PA={}
q=f"""SELECT batter_ID bid, CAST(substr(gameID,1,4) AS INT) season, stadium,
       COUNT(DISTINCT gameID||'_'||pa_number) pa FROM play_by_play
       WHERE substr(gameID,1,4) IN ({",".join("'%s'"%y for y in YSTR)}) GROUP BY batter_ID, season, stadium"""
for r in cur.execute(q):
    try: PA.setdefault((int(r['bid']),r['season']),[]).append((r['stadium'],r['pa']))
    except (TypeError,ValueError): continue

for t in ('wrc_plus_comparison','weighted_pf_by_batter_season'):
    cur.execute(f"DROP TABLE IF EXISTS {t}_bak"); cur.execute(f"CREATE TABLE {t}_bak AS SELECT * FROM {t}")
print("rolling backup -> *_bak")
cur.execute("DELETE FROM wrc_plus_comparison"); cur.execute("DELETE FROM weighted_pf_by_batter_season")

wrc_rows=[]; wpf_rows=[]
for b in cur.execute("""SELECT player_id,season,player_team,plate_appearance pa,at_bat ab,single h,double d2,triple d3,
        home_run hr,base_on_balls bb,intentional_base_on_balls ibb,hit_by_pitch hbp,sacrifice_fly sf
        FROM kbo_official_batter_stats WHERE plate_appearance>=1""").fetchall():
    season=b['season']; w=W.get(season); Ls=L.get(season); lgw=LGW.get(season)
    if not w or Ls is None or lgw is None: continue
    try: bid=int(b['player_id'])
    except (TypeError,ValueError): continue
    home=TEAM_PARK.get((b['player_team'],season)); dist=PA.get((bid,season),[])
    def wpf(idx):
        num=den=0
        for short,pa in dist: num+=pa*pf_of(season,stadium_full(short,season),idx); den+=pa
        return num/den if den else 1000.0
    wrun,whr,wslg=wpf(0),wpf(1),wpf(2)
    hrun=pf_of(season,home,0) if home else 1000.0; hhr=pf_of(season,home,1) if home else 1000.0; hslg=pf_of(season,home,2) if home else 1000.0
    home_pa=sum(pa for short,pa in dist if stadium_full(short,season)==home) if home else 0
    n_pa=b['pa']; rdiff=wrun-hrun
    wpf_rows.append((bid,season,n_pa,wrun,whr,wslg,home,home_pa,hrun,hhr,hslg,
                     round(home_pa/n_pa*100,1) if n_pa else 0, rdiff,
                     round(rdiff/hrun*100,2) if hrun else None, round((whr-hhr)/hhr*100,2) if hhr else None))
    if b['pa']<WRC_MIN_PA: continue
    one=b['h']-b['d2']-b['d3']-b['hr']; obp_den=b['ab']+b['bb']+b['sf']+b['hbp']
    if obp_den<=0: continue
    woba=(w['fg_wBB']*b['bb']+w['fg_wHBP']*b['hbp']+w['fg_w1B']*one+w['fg_w2B']*b['d2']+w['fg_w3B']*b['d3']+w['fg_wHR']*b['hr'])/obp_den
    wraa=(woba-lgw)/w['wOBA_scale']*b['pa']
    K=(wraa/b['pa'])/Ls*100.0
    pf_home=hrun; pf_half=(hrun+1000.0)/2.0; pf_weighted=wrun
    wrc_rows.append((bid,season,b['pa'],obp_den,woba,lgw,w['wOBA_scale'],wraa,hrun,wrun,pf_home,pf_half,pf_weighted,
                     K+(2.0-pf_home/1000.0)*100.0,K+(2.0-pf_half/1000.0)*100.0,K+(2.0-pf_weighted/1000.0)*100.0))

cur.executemany("""INSERT INTO weighted_pf_by_batter_season
    (batter_ID,season,n_PA,wpf_run,wpf_hr,wpf_slg,home_stadium,home_pa_n,home_run_pf,home_hr_pf,home_slg_pf,
     home_share,run_pf_diff,run_pf_diff_pct,hr_pf_diff_pct) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""", wpf_rows)
cur.executemany("""INSERT INTO wrc_plus_comparison
    (batter_ID,season,PA,OBP_denom,wOBA,lg_wOBA,wOBA_scale,wRAA_FG,home_run_pf,wpf_run,pf_home,pf_half,pf_weighted,
     wRC_home,wRC_half,wRC_weighted) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""", wrc_rows)

cur.execute("DROP VIEW IF EXISTS v_stadium_pf")
cur.execute("""CREATE VIEW v_stadium_pf AS SELECT spf.season, spf.stadium AS stadium_full, sd.stadium_id, sd.primary_team,
    spf.run_pf, spf.single_pf, spf.double_pf, spf.triple_pf, spf.hr_pf, spf.slg_pf
    FROM self_park_factor spf LEFT JOIN stadium_dim sd ON spf.stadium = sd.full_name""")
vb=cur.execute("SELECT sql FROM sqlite_master WHERE name='v_batter_wrc_plus'").fetchone()[0]
cur.execute("DROP VIEW IF EXISTS v_batter_wrc_plus"); cur.execute(vb.replace("JOIN statiz_park_factor pf","JOIN self_park_factor pf"))
con.commit()
print(f"built wrc={len(wrc_rows)}, weighted_pf={len(wpf_rows)}; team_stadium {latest}<-{src}")

print("\n=== validation NEW vs OLD(backup): mean wRC_half, mean wOBA delta, counts ===")
for r in cur.execute("""SELECT a.season, COUNT(*) n_new, ROUND(AVG(a.wRC_half),2) wrc_new,
    (SELECT ROUND(AVG(wRC_half),2) FROM wrc_plus_comparison_bak z WHERE z.season=a.season) wrc_old,
    (SELECT COUNT(*) FROM wrc_plus_comparison_bak z WHERE z.season=a.season) n_old,
    ROUND(AVG(a.wOBA-(SELECT b.wOBA FROM wrc_plus_comparison_bak b WHERE b.batter_ID=a.batter_ID AND b.season=a.season)),5) dwoba
    FROM wrc_plus_comparison a GROUP BY a.season ORDER BY a.season"""):
    print("  ", dict(r))
print("nulls:", cur.execute("SELECT COUNT(*) FROM wrc_plus_comparison WHERE wRC_half IS NULL").fetchone()[0])
print("2026 sample (top wRC_half):")
for r in cur.execute("SELECT batter_ID, ROUND(wOBA,3) woba, PA, home_run_pf, ROUND(wRC_half,1) wrc FROM wrc_plus_comparison WHERE season=2026 ORDER BY wRC_half DESC LIMIT 5"):
    print("   ", dict(r))
con.close()
