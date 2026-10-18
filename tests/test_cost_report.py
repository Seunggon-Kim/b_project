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
        self.nbytes, self.calls = nbytes, []

    def query(self, sql, job_config=None):
        self.calls.append(bool(job_config and job_config.dry_run))
        return FakeJob(self.nbytes, [] if job_config and job_config.dry_run else [{"month": "202610"}])


def test_시험_실행이_50MB_를_넘으면_멈춥니다():
    with pytest.raises(RuntimeError):
        cr.bq_rows(FakeBQ(60 * 1024 * 1024), "p.d.t", dt.date(2026, 7, 1))


def test_시험_실행_뒤에_진짜_질의를_합니다():
    q = FakeBQ(400_000)
    rows = cr.bq_rows(q, "p.d.t", dt.date(2026, 7, 1))
    assert q.calls == [True, False] and rows == [{"month": "202610"}]


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
    for f in Path("scripts/ops").glob("*.py"):
        text = f.read_text(encoding="utf-8")
        assert "gcp_billing_export_v1_" not in text
        assert "Bearer " not in text or "token" in text
