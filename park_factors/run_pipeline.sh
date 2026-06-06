#!/usr/bin/env bash
# KBO self park-factor + wRC+ + run-value pipeline. Re-run whenever new PBP / official
# stats are scraped (e.g. weekly during the 2026 season) to refresh 2026 park factors,
# batter wOBA/wRC+, AND RE24 / run values (incl. accumulating partial 2026).
set -euo pipefail
cd /home/ubuntu/b_project
PY=python3
[ -x venv/bin/python3 ] && PY=venv/bin/python3
echo "=== KBO park-factor + wRC+ + run-value pipeline $(date '+%Y-%m-%d %H:%M:%S') ==="
$PY park_factors/compute_self_park_factors.py     # PBP -> self_park_factor (2015-2026)
$PY park_factors/build_wrc_plus.py                # self_park_factor + stats + PBP -> wrc_plus_comparison / weighted_pf
$PY park_factors/build_re24_run_values.py --write # PBP -> re24_matrix_by_season + kbo_run_values_by_season (2015-2026; season0 = pooled 2015-2025)
echo "=== pipeline done ==="
