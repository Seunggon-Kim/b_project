# -*- coding: utf-8 -*-
"""네 수집 워크플로가 MySQL 에만 쓰는 모양인지 봅니다.

D1 은 2026-10-04 에 수집 쪽에서 걷어냈습니다(그 전 하루는 BSTATS_D1 스위치와
저장소 변수 D1_WRITE 로 꺼 두었습니다). 지금 지켜져야 하는 것은 다음과 같습니다.

- D1 스위치·wrangler 인증 확인·Cloudflare 토큰·node 설치가 없습니다.
- MySQL 연결(GCP 인증·프록시)은 조건 없이 늘 붙고, 실패하면 그 자리에서
  멈춥니다(continue-on-error 없음).
- 마지막 판정이 MySQL 연결·적재 실패를 늘 빨갛게 봅니다.
"""
import os
import re
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parent.parent
WF = ROOT / ".github" / "workflows"
NAMES = ["daily", "roster", "weekly", "monthly"]


def load(name):
    return yaml.safe_load((WF / (name + ".yml")).read_text(encoding="utf-8"))


def steps(name):
    doc = load(name)
    (job,) = doc["jobs"].values()
    return job, job["steps"]


@pytest.mark.parametrize("name", NAMES)
def test_D1_스위치와_Cloudflare_토큰이_없습니다(name):
    doc = load(name)
    job, ss = steps(name)
    for env in (doc.get("env") or {}, job.get("env") or {}):
        assert "BSTATS_D1" not in env, name
        assert not any(k.startswith("CLOUDFLARE_") for k in env), name
    for s in ss:
        text = "%s\n%s\n%s" % (s.get("run") or "", s.get("if") or "", s.get("env") or "")
        assert "wrangler" not in text and "CLOUDFLARE_" not in text, (name, s.get("name"))
        assert "D1_WRITE" not in text and "BSTATS_D1" not in text, (name, s.get("name"))
        # node 는 wrangler 에만 썼습니다.
        assert "actions/setup-node" not in (s.get("uses") or ""), (name, s.get("name"))


@pytest.mark.parametrize("name", NAMES)
def test_MySQL_연결은_조건_없이_늘_붙고_실패하면_멈춥니다(name):
    _, ss = steps(name)
    gcp = [s for s in ss if "google-github-actions/auth" in (s.get("uses") or "")]
    proxy = [s for s in ss if "migration/mysql/ci_proxy.sh" in (s.get("run") or "")]
    assert len(gcp) == 1 and len(proxy) == 1, name
    for s in (gcp[0], proxy[0]):
        assert "if" not in s, (name, s.get("name"))
        assert "continue-on-error" not in s, (name, s.get("name"))
    assert proxy[0].get("id") == "mysql"
    # 이중 적재 모드(shadow·off)는 없습니다. MySQL 이 유일한 저장소입니다.
    assert "MIRROR_MODE" not in (proxy[0].get("env") or {}), name


@pytest.mark.parametrize("name", NAMES)
def test_실패_확인은_MySQL_이_붙었을_때_돕니다(name):
    _, ss = steps(name)
    check = next(s for s in ss if s.get("id") == "mirror_check")
    assert check["name"] == "MySQL 적재 실패 확인"
    assert "steps.mysql.outcome == 'success'" in check["if"]
    assert "always()" in check["if"]
    assert '"$BSTATS_MYSQL_FAIL_LOG"' in check["run"]


@pytest.mark.parametrize("name", NAMES)
def test_요약에_D1_줄이_없습니다(name):
    _, ss = steps(name)
    summary = next(s for s in ss if s.get("name") == "요약")["run"]
    assert "D1" not in summary
    assert "| MySQL 적재 | ${{ steps.mirror_check.outcome }} |" in summary


def test_daily_실패_판정은_수집과_MySQL_을_봅니다():
    _, ss = steps("daily")
    judge = next(s for s in ss if s.get("name") == "실패 판정")
    assert judge["if"] == "always()"
    run = judge["run"]
    for sid in ("pbp", "load_batter", "load_pitcher", "purge", "team_ranks"):
        assert "steps.%s.outcome" % sid in run, sid
    assert '"${{ steps.games.outcome }}" = "failure"' in run
    m = re.search(r'for s in "\$\{\{ steps\.mysql\.outcome \}\}" '
                  r'"\$\{\{ steps\.mirror_check\.outcome \}\}"; do', run)
    assert m, run
    # 대조(D1·MySQL)는 D1 과 함께 지웠습니다.
    assert "reconcile" not in run
    assert not any("reconcile" in (s.get("run") or "") for s in ss)


@pytest.mark.parametrize("name", ["roster", "weekly", "monthly"])
def test_MySQL_판정은_조건_없이_늘_돕니다(name):
    _, ss = steps(name)
    judge = next(s for s in ss if s.get("name") == "MySQL 적재 판정")
    cond = judge["if"]
    assert cond.startswith("${{ always() && (steps.mysql.outcome != 'success'"), cond
    assert "steps.mirror_check.outcome != 'success'" in cond


def test_monthly_는_MySQL_에서_내려받습니다():
    _, ss = steps("monthly")
    pull = next(s for s in ss if s.get("id") == "pull")
    run = pull["run"]
    assert "python -m migration.mysql.mysql_to_sqlite" in run
    assert "players,kbo_official_batter_stats,kbo_official_pitcher_stats" in run
    assert "if" not in pull


def test_monthly_내려받기가_bash_에서_MySQL_을_부릅니다(tmp_path):
    import shutil
    import subprocess

    bash = shutil.which("bash")
    if not bash:
        pytest.skip("bash 없음")
    _, ss = steps("monthly")
    run = next(s for s in ss if s.get("id") == "pull")["run"]
    script = "python() { echo \"python $*\"; }\n" + run
    res = subprocess.run([bash, "-c", script], text=True, capture_output=True,
                         encoding="utf-8",
                         env=dict(os.environ, KBO_DB=str(tmp_path / "x.db")))
    assert res.returncode == 0, res.stderr
    assert "mysql_to_sqlite" in res.stdout and "d1_to_sqlite" not in res.stdout, res.stdout


@pytest.mark.parametrize("name", NAMES)
def test_머리_주석에_D1_을_걷어냈다고_적었습니다(name):
    text = (WF / (name + ".yml")).read_text(encoding="utf-8")
    head = text.split("\non:", 1)[0]
    assert "D1 은 2026-10-04 에 걷어냈습니다" in head, name
    # 되돌리기 안내(D1_WRITE=on)는 더 없습니다.
    assert "되돌린 뒤" not in head and "D1_WRITE" not in head, name
