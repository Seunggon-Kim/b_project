# KBO Park Factors (self-computed) & wRC+ pipeline

Self-computed park factors + full wRC+ rebuild from `play_by_play` and official stats, independent of Statiz.

## Run
```bash
cd ~/b_project
bash park_factors/run_pipeline.sh
# or: python3 park_factors/compute_self_park_factors.py && python3 park_factors/build_wrc_plus.py
```
Re-run whenever new PBP / official batter stats are scraped (e.g. weekly during the 2026 season). Idempotent:
same data in → same output (the season run-constant L is a fixed point); new data in → 2026 PF and wRC+ update.

## What it does
1. **compute_self_park_factors.py** → rebuilds `self_park_factor` (2015-2026, 9 parks/yr).
   - PF = `1000 * 10H/(9R+H)` (T=10, un-halved). run_pf per game; 1B/2B/3B/HR/SLG per in-play PA.
   - 3-year trailing window (forward-filled earliest cohort; park-opening years use 1-2y).
   - Smoothing toward 1000 with frozen `X` (run 1.0 / 1B .44 / 2B .60 / 3B .62 / HR .72 / SLG .40). No Statiz at runtime.
2. **build_wrc_plus.py** → rebuilds `wrc_plus_comparison` + `weighted_pf_by_batter_season` from scratch.
   - wOBA = `(wBB*BB + wHBP*HBP + w1B*1B + w2B*2B + w3B*3B + wHR*HR)/(AB+BB+SF+HBP)` using `kbo_woba_weights_by_season`
     (BB incl IBB; 1B = single(H) - 2B - 3B - HR). wRAA = `(wOBA - lg_wOBA)/wOBA_scale * PA`.
   - `wRC = K + (2 - PF)*100`, `K = (wRAA/PA / L[season])*100`. `L[season]` (league run constant) is derived from the
     existing rows (PF-invariant) so the wRC scale matches the original builder without its (unpublished) lgR/PA.
   - PF fields from `self_park_factor` + per-batter PA distribution (`play_by_play`, distinct gameID+pa_number).
   - Carries `team_stadium_by_season` to the latest season; repoints views `v_stadium_pf` / `v_batter_wrc_plus`.
   - Rolling backup `<table>_bak` before each run (1-step rollback).

## Scope / notes
- Statiz tables (`statiz_park_factor`, `statiz_yearly_constants`) are left untouched (reference only; not used at runtime).
- `play_by_play.batter_ID` is TEXT, the wpf table is INTEGER — the build normalizes to INT (do not remove).
- 2026 is a partial season: with the page default `min_pa=300` the 2026 leaderboard is empty until batters qualify
  (~mid-season). Lower the endpoint `min_pa` if in-season 2026 viewing is desired (frontend/API config, not this pipeline).
- Population: wrc_plus_comparison includes PA>=50; weighted_pf_by_batter_season includes all batters with >=1 PA.

## Rollback
```sql
DELETE FROM wrc_plus_comparison; INSERT INTO wrc_plus_comparison SELECT * FROM wrc_plus_comparison_bak;
DELETE FROM weighted_pf_by_batter_season; INSERT INTO weighted_pf_by_batter_season SELECT * FROM weighted_pf_by_batter_season_bak;
```
A dated snapshot from the initial migration also exists: `*_bak_20260605`.
