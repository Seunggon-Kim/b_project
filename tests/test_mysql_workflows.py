import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
WF = ROOT / ".github" / "workflows"


def test_ci_proxy_pins_version_and_checksum():
    s = (ROOT / "migration" / "mysql" / "ci_proxy.sh").read_text(encoding="utf-8")
    assert "VERSION=2.26.0" in s
    assert re.search(r"SHA256=[0-9a-f]{64}", s)
    assert "sha256sum -c" in s


def test_collect_workflows_have_mirror_steps():
    for name in ("daily.yml", "roster.yml", "monthly.yml"):
        t = (WF / name).read_text(encoding="utf-8")
        assert "id-token: write" in t, name
        # MySQL 은 늘 붙습니다(예전 MYSQL_MIRROR 변수를 보지 않음).
        assert "vars.MYSQL_MIRROR" not in t, name
        assert "bash migration/mysql/ci_proxy.sh" in t, name
        assert "pymysql" in t, name
        assert "cryptography" in t, name
        assert "id: mirror_check" in t, name


def test_no_secret_values_in_workflows():
    for p in WF.glob("*.yml"):
        t = p.read_text(encoding="utf-8")
        assert "BEGIN PUBLIC KEY" not in t, p.name
        assert "iam.gserviceaccount.com" not in t, p.name


def test_workflow_run_scripts_have_valid_bash_syntax():
    import shutil
    import subprocess

    import pytest
    import yaml

    bash = shutil.which("bash")
    if not bash:
        pytest.skip("bash 없음")
    for name in ("daily.yml", "roster.yml", "monthly.yml", "weekly.yml"):
        doc = yaml.safe_load((WF / name).read_text(encoding="utf-8"))
        for job in doc["jobs"].values():
            for step in job.get("steps", []):
                run = step.get("run")
                if not run:
                    continue
                script = re.sub(r"\$\{\{.*?\}\}", "X", run)
                res = subprocess.run([bash, "-n"], input=script, text=True,
                                     capture_output=True, encoding="utf-8")
                assert res.returncode == 0, "%s / %s: %s" % (name, step.get("name"), res.stderr)


def test_weekly_pulls_from_mysql():
    t = (WF / "weekly.yml").read_text(encoding="utf-8")
    assert "python -m migration.mysql.mysql_to_sqlite" in t
    assert "migration/d1_to_sqlite.py" not in t
    assert "id-token: write" in t and "id: mirror_check" in t
    assert "cryptography" in t
    assert "name: MySQL 적재 판정" in t
    assert "steps.mirror_check.outcome != 'success'" in t

def test_weekly_builds_truncated_games_before_calculations():
    import yaml

    doc = yaml.safe_load((WF / "weekly.yml").read_text(encoding="utf-8"))
    runs = [s.get("run", "") for s in doc["jobs"]["park-factors"]["steps"]]
    a = [i for i, r in enumerate(runs) if "park_factors/truncated.py" in r]
    b = [i for i, r in enumerate(runs) if "compute_self_park_factors.py" in r]
    assert a and b
    assert a[0] < b[0]
