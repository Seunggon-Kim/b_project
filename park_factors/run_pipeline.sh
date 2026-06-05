#!/usr/bin/env bash
# KBO self park-factor + wRC+ pipeline. Re-run whenever new PBP / official stats are scraped
# (e.g. weekly during the 2026 season) to refresh 2026 park factors AND batter wOBA/wRC+.
set -euo pipefail
cd /home/ubuntu/b_project
PY=python3
[ -x venv/bin/python3 ] && PY=venv/bin/python3
echo "=== KBO park-factor + wRC+ pipeline $(date '+%Y-%m-%d %H:%M:%S') ==="
$PY park_factors/compute_self_park_factors.py   # PBP -> self_park_factor (2015-2026)
$PY park_factors/build_wrc_plus.py              # self_park_factor + stats + PBP -> wrc_plus_comparison / weighted_pf
echo "=== pipeline done ==="
