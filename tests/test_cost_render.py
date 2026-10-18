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


def test_맨_위에_한눈에_보기와_읽는_법이_나옵니다():
    html = r.render(billing(), cf(), META)
    top = html.index("한눈에 보기")
    assert top < html.index("이번 달 요약") and top < html.index("Cloudflare 무료 한도 대비 사용량")
    assert "읽는 법" in html
    assert "돈이 아니라 무료 한도" in html


def test_요점은_숫자에서_만듭니다():
    bb, cc = billing(), cf()
    html = r.render(bb, cc, META)
    assert f"월말 예상 {r._won(bb['forecast'])}원" in html
    assert f"Workers 최고 {cc['req_peak'] / c.WORKERS_FREE_PER_DAY * 100:.1f}%" in html
    assert f"끊긴 요청 {cc['cut_total']}건" in html


def test_요점은_빠진_칸을_말합니다():
    html = r.render(None, None, META)
    assert "GCP 비용은 아직 볼 수 없습니다" in html
    assert "Cloudflare 사용량은 아직 볼 수 없습니다" in html


def test_CPU_중앙값이_한도에_가까우면_요점에_적습니다():
    cc = cf()
    cc["cpu_p50_ms"] = 10.3
    assert "여유가 거의 없습니다" in r.render(None, cc, META)
    cc["cpu_p50_ms"] = 3.0
    assert "여유가 거의 없습니다" not in r.render(None, cc, META)


def test_결제가_없으면_부제_끝에_가운뎃점이_남지_않습니다():
    html = r.render(None, cf(), META)
    assert "무료 플랜 ·</div>" not in html and "무료 플랜 · </div>" not in html
    assert "무료 플랜 · 2026년 10월" in r.render(billing(), cf(), META)
