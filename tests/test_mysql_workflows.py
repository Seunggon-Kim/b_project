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
        assert "vars.MYSQL_MIRROR == 'on'" in t, name
        assert "bash migration/mysql/ci_proxy.sh" in t, name
        assert "pymysql" in t, name
        assert "id: mirror_check" in t, name


def test_daily_reconciles():
    t = (WF / "daily.yml").read_text(encoding="utf-8")
    assert "python -m migration.mysql.reconcile" in t


def test_no_secret_values_in_workflows():
    for p in WF.glob("*.yml"):
        t = p.read_text(encoding="utf-8")
        assert "BEGIN PUBLIC KEY" not in t, p.name
        assert "iam.gserviceaccount.com" not in t, p.name
