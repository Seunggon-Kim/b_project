# tests/test_cost_render.py
import datetime as dt
import re

from scripts.ops import cost_billing as b
from scripts.ops import cost_cloudflare as c
from scripts.ops import cost_render as r
from ops_cost_fixtures import DAYS, ODD, month_rows
from ops_cost_fixtures import cf_resp as resp

META = {"made_at": "2026-10-18 21:40 KST", "billing_note": "", "cf_note": "", "font_dir": "fonts"}


def billing():
    return b.summarize(month_rows(), "2026-10", dt.date(2026, 10, 18), 30000)


def cf():
    return c.summarize(resp({d: 5000 for d in DAYS}, {DAYS[3]: 4}, {d: 6000 for d in DAYS}), DAYS)


def test_모든_칸이_나옵니다():
    html = r.render(billing(), cf(), META)
    for h in ("이번 달 요약", "GCP 서비스별 월 비용", "Cloud SQL 세부", "GCP 일별 변동비",
              "Cloudflare 무료 한도 대비 사용량", "CPU 한도 초과로 끊긴 요청", "기준과 주의"):
        assert h in html
    assert "2026-10-18 21:40 KST" in html
    assert "미리보기 목업" not in html and "#demo" not in html


def test_자리_표시자가_남지_않습니다():
    html = r.render(billing(), cf(), META)
    assert not re.search(r"\$[a-z_]+", html.split("<script>")[0])


def test_모르는_SKU_를_주의에_적습니다():
    html = r.render(billing(), cf(), META)
    assert ODD in html and "변동비로 넣은" in html


def test_Cloudflare_가_없으면_그_칸만_안내합니다():
    html = r.render(billing(), None, dict(META, cf_note="토큰 없음: ~/.bstats/cf_analytics_token.txt"))
    assert "토큰 없음" in html and "GCP 서비스별 월 비용" in html
    assert "Workers 요청 수" not in html


def test_결제가_없으면_그_칸만_안내합니다():
    html = r.render(None, cf(), dict(META, billing_note="내보내기 데이터 없음"))
    assert "내보내기 데이터 없음" in html and "Workers 요청 수" in html


def test_글자를_이스케이프합니다():
    rows = month_rows() + [{"month": "202610", "service": "Cloud SQL", "sku": "<b>x</b>",
                            "day": dt.date(2026, 10, 2), "currency": "KRW", "net": 1}]
    s = b.summarize(rows, "2026-10", dt.date(2026, 10, 18), 30000)
    html = r.render(s, None, META)
    assert "<b>x</b>" not in html and "&lt;b&gt;x&lt;/b&gt;" in html


def test_한도선은_규칙대로만_그립니다():
    html = r.render(None, cf(), META)
    assert 'class="limit"' not in html
    big = {d: 1000 for d in DAYS}
    big[DAYS[1]] = 70_000
    html2 = r.render(None, c.summarize(resp(big), DAYS), META)
    assert 'class="limit"' in html2
