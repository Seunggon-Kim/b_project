import datetime as dt

import pytest

from scripts.ops import cost_report as cr


def test_비밀값_파일이_없으면_None(tmp_path, monkeypatch):
    monkeypatch.setattr(cr, "SECRET_DIR", tmp_path)
    assert cr.read_secret("cf_analytics_token.txt") is None
    (tmp_path / "cf_analytics_token.txt").write_text("  abc \n", encoding="utf-8")
    assert cr.read_secret("cf_analytics_token.txt") == "abc"


def test_출력_폴더는_바탕화면_날짜_폴더입니다(tmp_path):
    assert cr.out_dir(tmp_path, dt.date(2026, 10, 18)) == tmp_path / "bstats_비용보고" / "2026-10-18"


class FakeJob:
    def __init__(self, nbytes, rows=()):
        self.total_bytes_processed = nbytes
        self._rows = rows

    def result(self):
        return list(self._rows)


class FakeBQ:
    def __init__(self, nbytes):
        self.nbytes, self.calls, self.params = nbytes, [], []

    def query(self, sql, job_config=None):
        self.calls.append(bool(job_config and job_config.dry_run))
        self.params.append(list(job_config.query_parameters) if job_config else [])
        return FakeJob(self.nbytes, [] if job_config and job_config.dry_run else [{"month": "202610"}])


def test_시험_실행이_50MB_를_넘으면_멈춥니다():
    with pytest.raises(RuntimeError):
        cr.bq_rows(FakeBQ(60 * 1024 * 1024), "p.d.t", dt.date(2026, 7, 1))


def test_시험_실행_뒤에_진짜_질의를_합니다():
    q = FakeBQ(400_000)
    rows = cr.bq_rows(q, "p.d.t", dt.date(2026, 7, 1))
    assert q.calls == [True, False] and rows == [{"month": "202610"}]
    for params in q.params:
        assert [(p.name, p.value) for p in params] == [("start", dt.date(2026, 7, 1))]


@pytest.mark.parametrize("month,today,want", [
    # 이른 날 = today-29일(9/19, 2/9, 12/7)이 달 1일보다 앞서므로 그 달의 세 달 전 1일입니다
    ("2026-10", dt.date(2026, 10, 18), dt.date(2026, 6, 1)),
    ("2026-03", dt.date(2026, 3, 10), dt.date(2025, 11, 1)),
    ("2026-01", dt.date(2026, 1, 5), dt.date(2025, 9, 1)),
    # 달 1일이 더 이른 경우
    ("2026-10", dt.date(2026, 10, 30), dt.date(2026, 7, 1)),
    ("2026-04", dt.date(2026, 4, 2), dt.date(2025, 12, 1)),
])
def test_질의_시작일은_세_달_전_1일입니다(month, today, want):
    got = cr.query_start(month, today)
    assert got == want and got.day == 1


def _cf_secrets(tmp_path, monkeypatch):
    sd = tmp_path / "s"
    sd.mkdir()
    (sd / "cf_analytics_token.txt").write_text("TOKEN_TESTONLY", encoding="utf-8")
    (sd / "cf_account_id.txt").write_text("ACCT_TESTONLY", encoding="utf-8")
    monkeypatch.setattr(cr, "SECRET_DIR", sd)


def test_Cloudflare_오류_글에_계정_ID_가_남지_않습니다(tmp_path, monkeypatch):
    _cf_secrets(tmp_path, monkeypatch)

    def boom(*a, **k):
        raise RuntimeError("HTTP 403 /accounts/ACCT_TESTONLY/ Bearer TOKEN_TESTONLY")

    monkeypatch.setattr(cr, "cf_fetch", boom)
    data, note, code = cr.make_cf(dt.date(2026, 10, 18))
    assert data is None and code == 1
    assert "ACCT_TESTONLY" not in note and "TOKEN_TESTONLY" not in note and "<계정>" in note


def test_Cloudflare_모양_오류_글에도_계정_ID_가_남지_않습니다(tmp_path, monkeypatch):
    _cf_secrets(tmp_path, monkeypatch)
    monkeypatch.setattr(cr, "cf_fetch", lambda *a, **k: {})

    def bad(*a, **k):
        raise cr.cost_cloudflare.SchemaMismatch("키 없음 ACCT_TESTONLY")

    monkeypatch.setattr(cr.cost_cloudflare, "summarize", bad)
    _, note, _ = cr.make_cf(dt.date(2026, 10, 18))
    assert "ACCT_TESTONLY" not in note and "<계정>" in note


def test_토큰이_없어도_보고서를_만듭니다(tmp_path, monkeypatch):
    monkeypatch.setattr(cr, "SECRET_DIR", tmp_path / "secrets")
    code = cr.main(["--month", "2026-10", "--out", str(tmp_path / "o"), "--no-png",
                    "--today", "2026-10-18"])
    html = (tmp_path / "o" / "report.html").read_text(encoding="utf-8")
    assert code == 0
    assert "결제 내보내기 표 이름이 없습니다" in html and "토큰 없음" in html
    assert (tmp_path / "o" / "fonts" / "KBO-Dia-Gothic_bold.woff").exists()


def test_코드에_결제_계정_ID_나_토큰을_넣지_않습니다():
    from pathlib import Path
    files = list(Path(cr.__file__).parent.glob("*.py"))
    assert files
    for f in files:
        text = f.read_text(encoding="utf-8")
        assert "gcp_billing_export_v1_" not in text
        assert "Bearer " not in text or "token" in text


def test_결제_오류_글에_표_이름이_남지_않습니다(tmp_path, monkeypatch):
    sd = tmp_path / "s"
    sd.mkdir()
    (sd / "billing_export_table.txt").write_text("proj.ds.gcp_billing_export_v1_TESTONLY", encoding="utf-8")
    monkeypatch.setattr(cr, "SECRET_DIR", sd)

    def boom(*a, **k):
        raise RuntimeError("Not found: Table proj.ds.gcp_billing_export_v1_TESTONLY (gcp_billing_export_v1_TESTONLY)")

    monkeypatch.setattr(cr, "bq_client", lambda: object())
    monkeypatch.setattr(cr, "bq_rows", boom)
    b, note = cr.make_billing("2026-10", dt.date(2026, 10, 18), 30000)
    assert b is None
    assert "TESTONLY" not in note and "<결제 표>" in note


def test_Edge_가_멈춰도_경고만_하고_끝납니다(tmp_path, monkeypatch, capsys):
    import subprocess
    fake_edge = tmp_path / "msedge.exe"
    fake_edge.write_text("x")
    html = tmp_path / "o" / "report.html"
    (tmp_path / "o" / "fonts").mkdir(parents=True)
    html.write_text("<html></html>", encoding="utf-8")

    def hang(*a, **k):
        raise subprocess.TimeoutExpired("edge", 120)

    monkeypatch.setattr(cr, "EDGE", fake_edge)
    monkeypatch.setattr(cr.subprocess, "run", hang)
    cr.screenshot(html, tmp_path / "o" / "report.png")
    assert not (tmp_path / "o" / "report.png").exists()
    assert "경고" in capsys.readouterr().out
