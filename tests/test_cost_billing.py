import datetime as dt

from scripts.ops import cost_billing as b
from ops_cost_fixtures import BACK, DISK, EGR, INST, ODD, SQL, month_rows, row


def test_고정비_SKU_를_알아봅니다():
    assert b.is_fixed(INST) and b.is_fixed(DISK)
    assert not b.is_fixed(BACK) and not b.is_fixed(EGR)


def test_서비스_묶음():
    assert b.service_group("Cloud SQL") == "Cloud SQL"
    assert b.service_group("BigQuery") == "BigQuery"
    assert b.service_group("Cloud Monitoring") == "Cloud Monitoring"
    assert b.service_group("Secret Manager") == "기타"


def test_이번_달_요약():
    s = b.summarize(month_rows(), "2026-10", dt.date(2026, 10, 18), 30000)
    total = 18 * (340 + 77 + 26 + 9) + 95 + 12 + 3
    assert s["total"] == total
    assert s["days_elapsed"] == 18 and s["days_in_month"] == 31
    assert s["forecast"] == round(total / 18 * 31)
    assert s["ratio_pct"] == round(total / 30000 * 100, 1)


def test_월별_표는_오래된_달부터이고_진행_중인_달을_표시합니다():
    s = b.summarize(month_rows(), "2026-10", dt.date(2026, 10, 18), 30000)
    assert [m["month"] for m in s["months"]] == ["2026-09", "2026-10"]
    assert s["months"][0]["Cloud SQL"] == 340 and not s["months"][0]["partial"]
    assert s["months"][1]["BigQuery"] == 12 and s["months"][1]["partial"]


def test_Cloud_SQL_SKU_세부와_모르는_SKU():
    s = b.summarize(month_rows(), "2026-10", dt.date(2026, 10, 18), 30000)
    kinds = {x["sku"]: x["kind"] for x in s["sql_skus"]}
    assert kinds[INST] == "고정" and kinds[BACK] == "변동"
    assert s["sql_skus"][0]["sku"] == INST
    assert s["unknown_sql_skus"] == [ODD]


def test_일별은_30일이고_고정비와_변동비를_나눕니다():
    s = b.summarize(month_rows(), "2026-10", dt.date(2026, 10, 18), 30000)
    assert len(s["daily"]) == 30 and s["daily"][-1]["day"] == "2026-10-18"
    assert s["daily"][-1]["partial"] and not s["daily"][-2]["partial"]
    d9 = next(x for x in s["daily"] if x["day"] == "2026-10-09")
    assert d9["fixed"] == 417 and d9["백업·PITR 로그"] == 26 + 95 and d9["네트워크"] == 9
    d5 = next(x for x in s["daily"] if x["day"] == "2026-10-05")
    assert d5["기타"] == 3


def test_원이_아닌_통화가_있으면_알립니다():
    rows = [row("2026-10-01", SQL, INST, 1, currency="USD")]
    s = b.summarize(rows, "2026-10", dt.date(2026, 10, 1), 30000)
    assert s["currencies"] == ["USD"]


def test_질의는_크레딧을_더한_순액이고_한국_날짜입니다():
    sql = b.billing_sql("p.d.t")
    assert "UNNEST(credits)" in sql and "'Asia/Seoul'" in sql and "`p.d.t`" in sql
    assert "@start" in sql
