# tests/test_cost_cloudflare.py
import pytest

from scripts.ops import cost_cloudflare as c
from ops_cost_fixtures import DAYS
from ops_cost_fixtures import cf_resp as resp


def test_날마다_요청_질의_끊긴_수를_30칸으로_맞춥니다():
    s = c.summarize(resp({DAYS[0]: 100, DAYS[5]: 300}, {DAYS[5]: 2}, {DAYS[5]: 400}), DAYS)
    assert len(s["requests"]) == 30 and s["requests"][0] == 100 and s["requests"][1] == 0
    assert s["requests"][5] == 300 and s["cut"][5] == 2 and s["queries"][5] == 400
    assert s["cut_total"] == 2 and s["cut_pct"] == round(2 / 400 * 100, 3)


def test_CPU_는_밀리초입니다():
    s = c.summarize(resp({DAYS[0]: 1}), DAYS)
    assert s["cpu_p50_ms"] == 4.8 and s["cpu_p99_ms"] == 21.6 and s["p99_by_day"][0] == 20.0


def test_가장_많은_날과_한도선_규칙():
    big = {d: 1000 for d in DAYS}
    big[DAYS[10]] = 60_000
    s = c.summarize(resp(big), DAYS)
    assert s["req_peak"] == 60_000 and s["req_peak_day"] == DAYS[10]
    assert s["show_limit_line"]["requests"] is True
    s2 = c.summarize(resp({DAYS[0]: 12_480}), DAYS)
    assert s2["show_limit_line"]["requests"] is False


def test_칸이_없으면_스키마가_다르다고_알립니다():
    with pytest.raises(c.SchemaMismatch):
        c.summarize({"data": {"viewer": {"accounts": [{}]}}, "errors": None}, DAYS)


def test_GraphQL_오류는_스키마가_다르다고_알립니다():
    with pytest.raises(c.SchemaMismatch):
        c.summarize({"data": None, "errors": [{"message": "unknown field hyd"}]}, DAYS)


def test_질의는_kbo_api_만_봅니다():
    q = c.graphql_query()
    assert '"kbo-api"' in q and "$acct" in q and "$start" in q and "$end" in q
