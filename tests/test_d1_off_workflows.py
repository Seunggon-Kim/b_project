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


def test_daily_실패_판정은_MySQL_을_늘_보고_대조는_켰을_때만_봅니다():
    _, ss = steps("daily")
    judge = next(s for s in ss if s.get("name") == "실패 판정")
    run = judge["run"]
    assert "MYSQL_MIRROR" not in run
    m = re.search(r'for s in "\$\{\{ steps\.mysql\.outcome \}\}" '
                  r'"\$\{\{ steps\.mirror_check\.outcome \}\}"; do', run)
    assert m, run


@pytest.mark.parametrize("name", ["roster", "weekly", "monthly"])
def test_MySQL_판정은_조건_없이_늘_돕니다(name):
    _, ss = steps(name)
    judge = next(s for s in ss if s.get("name") == "MySQL 이중 적재 판정")
    cond = judge["if"]
    assert cond.startswith("${{ always() && (steps.mysql.outcome != 'success'"), cond
    assert "steps.mirror_check.outcome != 'success'" in cond


def test_monthly_는_늘_MySQL_에서_내려받습니다():
    """D1_WRITE 와 상관없이 MySQL 이 원본입니다.

    되돌리기(D1_WRITE=on) 때 낡은 D1 players 를 받으면 sqlite_to_d1 의 mirror
    (DELETE 후 INSERT)가 그것으로 MySQL players(사이트가 읽는 값)를 덮습니다.
    """
    _, ss = steps("monthly")
    pull = next(s for s in ss if s.get("id") == "pull")
    run = pull["run"]
    assert "python -m migration.mysql.mysql_to_sqlite" in run
    assert "players,kbo_official_batter_stats,kbo_official_pitcher_stats" in run
    assert "BSTATS_D1" not in run and "if" not in pull


def test_monthly_는_d1_to_sqlite_를_부르지_않습니다():
    import sys
    sys.path.insert(0, str(ROOT / "scripts"))
    import lineage_extract as lx

    text = (WF / "monthly.yml").read_text(encoding="utf-8")
    scripts = {s["script"] for s in lx.parse_workflow(text)["steps"]}
    assert "migration/d1_to_sqlite.py" not in scripts, scripts
    assert "migration/mysql/mysql_to_sqlite.py" in scripts
    _, ss = steps("monthly")
    assert not any("d1_to_sqlite" in (s.get("run") or "") for s in ss)


def test_monthly_내려받기가_bash_에서_D1_스위치와_상관없이_MySQL_을_부릅니다(tmp_path):
    import shutil
    import subprocess

    bash = shutil.which("bash")
    if not bash:
        pytest.skip("bash 없음")
    _, ss = steps("monthly")
    run = next(s for s in ss if s.get("id") == "pull")["run"]
    script = "python() { echo \"python $*\"; }\n" + run
    for mode in ("off", "on"):
        res = subprocess.run([bash, "-c", script], text=True, capture_output=True,
                             encoding="utf-8",
                             env=dict(os.environ, BSTATS_D1=mode,
                                      KBO_DB=str(tmp_path / "x.db")))
        assert res.returncode == 0, res.stderr
        assert "mysql_to_sqlite" in res.stdout and "d1_to_sqlite" not in res.stdout, (
            mode, res.stdout)


@pytest.mark.parametrize("name", ["daily", "roster", "monthly"])
def test_MySQL_준비_단계는_D1_이_꺼져_있으면_바로_실패합니다(name):
    """off 이면 MySQL 이 유일한 저장소라 붙지 못하면 뒤 수집을 돌릴 이유가 없습니다.

    continue-on-error 는 되돌리기(D1_WRITE=on) 때만 켭니다.
    """
    _, ss = steps(name)
    gcp = next(s for s in ss if "google-github-actions/auth" in (s.get("uses") or ""))
    proxy = next(s for s in ss if "migration/mysql/ci_proxy.sh" in (s.get("run") or ""))
    for s in (gcp, proxy):
        assert s.get("continue-on-error") == "${{ vars.D1_WRITE == 'on' }}", (name, s.get("name"))
    # 프록시는 GCP 인증이 된 때만, 실패 확인은 프록시가 된 때만 돕니다.
    assert proxy["if"] == "${{ steps.gcp.outcome == 'success' }}"
    check = next(s for s in ss if s.get("id") == "mirror_check")
    assert "steps.mysql.outcome == 'success'" in check["if"]


def test_weekly_MySQL_준비_단계는_예전처럼_늘_실패를_올립니다():
    _, ss = steps("weekly")
    gcp = next(s for s in ss if "google-github-actions/auth" in (s.get("uses") or ""))
    proxy = next(s for s in ss if "migration/mysql/ci_proxy.sh" in (s.get("run") or ""))
    assert "continue-on-error" not in gcp and "continue-on-error" not in proxy


@pytest.mark.parametrize("name", NAMES)
def test_되돌리기_주의를_머리_주석에_적었습니다(name):
    text = (WF / (name + ".yml")).read_text(encoding="utf-8")
    head = text.split("\non:", 1)[0]
    assert "D1·MySQL 대조가 빨갛습니다" in head, name
    assert "roster_to_d1 은 낡은 D1 players" in head, name


def test_weekly_는_MYSQL_MIRROR_확인_단계를_뺐습니다():
    _, ss = steps("weekly")
    assert not any(s.get("id") == "guard" for s in ss)
    assert not any("steps.guard" in str(s.get("if", "")) for s in ss)
