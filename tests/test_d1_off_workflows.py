# -*- coding: utf-8 -*-
"""네 수집 워크플로의 D1 스위치입니다.

- 모든 job 이 `BSTATS_D1` 을 저장소 변수 D1_WRITE 로 정합니다(없으면 off).
- D1 에만 뜻이 있는 단계(wrangler 인증 확인, D1·MySQL 대조, D1 내려받기)는
  `vars.D1_WRITE == 'on'` 일 때만 돕니다.
- MySQL 연결은 늘 붙고, 마지막 판정이 MySQL 실패를 늘 빨갛게 봅니다.
"""
import os
import re
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parent.parent
WF = ROOT / ".github" / "workflows"
NAMES = ["daily", "roster", "weekly", "monthly"]
SWITCH = "${{ vars.D1_WRITE == 'on' && 'on' || 'off' }}"
GATE = "vars.D1_WRITE == 'on'"


def load(name):
    return yaml.safe_load((WF / (name + ".yml")).read_text(encoding="utf-8"))


def steps(name):
    doc = load(name)
    (job,) = doc["jobs"].values()
    return job, job["steps"]


def step_text(step):
    return "%s\n%s" % (step.get("run") or "", step.get("uses") or "")


@pytest.mark.parametrize("name", NAMES)
def test_모든_job_이_BSTATS_D1_을_D1_WRITE_로_정합니다(name):
    job, _ = steps(name)
    assert job.get("env", {}).get("BSTATS_D1") == SWITCH, name


@pytest.mark.parametrize("name", NAMES)
def test_wrangler_를_부르는_단계는_D1_WRITE_로_막혀_있습니다(name):
    _, ss = steps(name)
    for s in ss:
        run = s.get("run") or ""
        if "wrangler" in run or "CLOUDFLARE_API_TOKEN" in run:
            assert GATE in str(s.get("if", "")), "%s / %s" % (name, s.get("name"))


@pytest.mark.parametrize("name", NAMES)
def test_MySQL_연결은_늘_붙습니다(name):
    _, ss = steps(name)
    gcp = [s for s in ss if "google-github-actions/auth" in (s.get("uses") or "")]
    proxy = [s for s in ss if "migration/mysql/ci_proxy.sh" in (s.get("run") or "")]
    assert gcp and proxy, name
    assert "if" not in gcp[0], name
    # 프록시 단계는 GCP 인증이 됐을 때만 돕니다(그 밖의 조건은 없음).
    assert "MYSQL_MIRROR" not in str(proxy[0].get("if", "")), name
    assert "D1_WRITE" not in str(proxy[0].get("if", "")), name


@pytest.mark.parametrize("name", NAMES)
def test_예전_MYSQL_MIRROR_변수를_조건에_쓰지_않습니다(name):
    _, ss = steps(name)
    for s in ss:
        assert "MYSQL_MIRROR" not in str(s.get("if", "")), "%s / %s" % (name, s.get("name"))
        assert "vars.MYSQL_MIRROR" not in (s.get("run") or ""), "%s / %s" % (name, s.get("name"))


def test_daily_대조는_D1_을_켰을_때만_돌고_기록은_늘_남깁니다():
    _, ss = steps("daily")
    rec = next(s for s in ss if "migration.mysql.reconcile" in (s.get("run") or ""))
    assert rec.get("id") == "reconcile"
    assert GATE in rec["if"]
    log = next(s for s in ss if "--job reconcile" in (s.get("run") or ""))
    assert log["if"] == "always()"
    # 건너뛰면 skip 으로 남깁니다. /jobs/status 칸이 비지 않게 합니다.
    assert "steps.reconcile.outcome == 'skipped' && 'skip'" in log["run"]


def test_daily_실패_판정은_MySQL_을_늘_보고_대조는_켰을_때만_봅니다():
    _, ss = steps("daily")
    judge = next(s for s in ss if s.get("name") == "실패 판정")
    run = judge["run"]
    assert "MYSQL_MIRROR" not in run
    m = re.search(r'for s in "\$\{\{ steps\.mysql\.outcome \}\}" '
                  r'"\$\{\{ steps\.mirror_check\.outcome \}\}"; do', run)
    assert m, run
    # 대조 결과는 D1_WRITE 조건 안에서만 봅니다.
    i = run.index("steps.reconcile.outcome")
    assert GATE in run[max(0, i - 200):i]


@pytest.mark.parametrize("name", ["roster", "weekly", "monthly"])
def test_MySQL_판정은_조건_없이_늘_돕니다(name):
    _, ss = steps(name)
    judge = next(s for s in ss if s.get("name") == "MySQL 이중 적재 판정")
    cond = judge["if"]
    assert cond.startswith("${{ always() && (steps.mysql.outcome != 'success'"), cond
    assert "steps.mirror_check.outcome != 'success'" in cond


def test_monthly_는_꺼져_있으면_MySQL_에서_내려받습니다():
    _, ss = steps("monthly")
    pull = next(s for s in ss if s.get("id") == "pull")
    run = pull["run"]
    assert 'if [ "$BSTATS_D1" = "on" ]; then' in run
    on_part, off_part = run.split("else", 1)
    assert "migration/d1_to_sqlite.py" in on_part
    assert "python -m migration.mysql.mysql_to_sqlite" in off_part
    assert "d1_to_sqlite" not in off_part
    assert "players,kbo_official_batter_stats,kbo_official_pitcher_stats" in run


def test_monthly_내려받기_분기가_bash_에서_실제로_갈립니다(tmp_path):
    import shutil
    import subprocess

    bash = shutil.which("bash")
    if not bash:
        pytest.skip("bash 없음")
    _, ss = steps("monthly")
    run = next(s for s in ss if s.get("id") == "pull")["run"]
    script = "python() { echo \"python $*\"; }\n" + run
    for mode, want, not_want in (("off", "mysql_to_sqlite", "d1_to_sqlite"),
                                 ("on", "d1_to_sqlite", "mysql_to_sqlite")):
        res = subprocess.run([bash, "-c", script], text=True, capture_output=True,
                             encoding="utf-8",
                             env=dict(os.environ, BSTATS_D1=mode,
                                      KBO_DB=str(tmp_path / "x.db")))
        assert res.returncode == 0, res.stderr
        assert want in res.stdout and not_want not in res.stdout, (mode, res.stdout)


def test_weekly_는_MYSQL_MIRROR_확인_단계를_뺐습니다():
    _, ss = steps("weekly")
    assert not any(s.get("id") == "guard" for s in ss)
    assert not any("steps.guard" in str(s.get("if", "")) for s in ss)
