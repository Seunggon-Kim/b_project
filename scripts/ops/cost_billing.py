# -*- coding: utf-8 -*-
"""GCP 결제 빅쿼리 내보내기(표준 사용 비용)를 보고서 숫자로 바꿉니다.

질의 글자와 순수 계산만 둡니다. 빅쿼리 호출은 cost_report.py 가 합니다.
순액 = 비용 + 크레딧 합(크레딧은 음수). 날짜는 사용 시작 시각의 KST 날짜,
월은 청구 월(invoice.month)입니다.
"""
import calendar
import datetime as dt
import re
import statistics

SERVICES = ("Cloud SQL", "BigQuery", "Cloud Monitoring")
VAR_KEYS = ("백업·PITR 로그", "네트워크", "BigQuery", "기타")

# 매일 같은 금액이 붙는 Cloud SQL SKU 입니다. 첫 실제 실행에서 '기준과 주의'의
# SKU 목록을 보고 evan 이 확인합니다. 목록에 없으면 짐작하지 않고 변동비로 둡니다.
FIXED_SKU_PATTERNS = [r"\bmicro instance\b", r"\bsmall instance\b", r"\bvcpu\b", r"\bram\b",
                      r"\bstandard storage\b", r"\bssd storage\b"]


def billing_sql(table):
    """결제 내보내기에서 일 단위 순액을 뽑는 질의입니다.

    계약: `@start` 는 반드시 달의 1일이어야 합니다. 청구 월(invoice.month)은 미국
    태평양 시간 기준이라, 날짜(KST)로만 거르면 start 달 앞의 반나절치가 이른 달 줄로
    들어옵니다. 그래서 invoice.month 로도 함께 거릅니다(summarize 는 그 달을 partial 로
    표시하지 않습니다).
    GROUP BY 는 위치 번호를 씁니다(별칭이 최상위 열 이름과 겹치기 때문입니다).
    """
    return (
        "SELECT invoice.month AS month, service.description AS service, sku.description AS sku, "
        "DATE(usage_start_time, 'Asia/Seoul') AS day, currency, "
        "SUM(cost) + SUM(IFNULL((SELECT SUM(c.amount) FROM UNNEST(credits) c), 0)) AS net "
        "FROM `%s` "
        "WHERE project.id = 'bstats-kbo' AND DATE(usage_start_time, 'Asia/Seoul') >= @start "
        "AND invoice.month >= FORMAT_DATE('%%Y%%m', @start) "
        "GROUP BY 1, 2, 3, 4, 5" % table)


def is_fixed(sku):
    s = (sku or "").lower()
    return any(re.search(p, s) for p in FIXED_SKU_PATTERNS)


def service_group(service):
    return service if service in SERVICES else "기타"


def var_key(service, sku):
    s = (sku or "").lower()
    if service == "Cloud SQL" and ("backup" in s or "log" in s):
        return "백업·PITR 로그"
    if "egress" in s or "network" in s:
        return "네트워크"
    if service == "BigQuery":
        return "BigQuery"
    return "기타"


def _ym(month):
    return "%s-%s" % (month[:4], month[4:6])


def summarize(rows, month, today, budget):
    y, m = int(month[:4]), int(month[5:7])
    days_in_month = calendar.monthrange(y, m)[1]
    days_elapsed = today.day if (today.year, today.month) == (y, m) else days_in_month

    months = {}
    for r in rows:
        k = _ym(r["month"])
        mm = months.setdefault(k, {"month": k, **{s: 0 for s in SERVICES}, "기타": 0})
        mm[service_group(r["service"])] += r["net"]
    month_list = []
    for k in sorted(months):
        mm = months[k]
        mm["total"] = sum(mm[s] for s in (*SERVICES, "기타"))
        mm["partial"] = k == month and days_elapsed < days_in_month
        month_list.append(mm)
    total = months.get(month, {}).get("total", 0)

    sku_sum, unknown = {}, set()
    for r in rows:
        if _ym(r["month"]) == month and r["service"] == "Cloud SQL":
            sku_sum[r["sku"]] = sku_sum.get(r["sku"], 0) + r["net"]
            if not is_fixed(r["sku"]) and var_key("Cloud SQL", r["sku"]) == "기타":
                unknown.add(r["sku"])
    sql_total = sum(sku_sum.values()) or 1
    sql_skus = [{"sku": k, "amount": v, "kind": "고정" if is_fixed(k) else "변동",
                 "share_pct": round(v / sql_total * 100, 1)}
                for k, v in sorted(sku_sum.items(), key=lambda kv: -kv[1])]

    days = [today - dt.timedelta(days=i) for i in range(29, -1, -1)]
    daily = {d: {"day": d.isoformat(), "fixed": 0, **{k: 0 for k in VAR_KEYS}, "partial": d == today}
             for d in days}
    for r in rows:
        d = r["day"]
        if d not in daily:
            continue
        if r["service"] == "Cloud SQL" and is_fixed(r["sku"]):
            daily[d]["fixed"] += r["net"]
        else:
            daily[d][var_key(r["service"], r["sku"])] += r["net"]
    daily_list = [daily[d] for d in days]
    past = daily_list[:-1]
    fixed_per_day = round(sum(x["fixed"] for x in past) / len(past))
    var_median = statistics.median(sum(x[k] for k in VAR_KEYS) for x in past)

    forecast = round(total / days_elapsed * days_in_month) if days_elapsed else 0
    return {
        "month": month, "days_elapsed": days_elapsed, "days_in_month": days_in_month,
        "total": total, "avg_per_day": round(total / days_elapsed) if days_elapsed else 0,
        "forecast": forecast, "budget": budget,
        "ratio_pct": round(total / budget * 100, 1),
        "forecast_ratio_pct": round(forecast / budget * 100, 1),
        "months": month_list, "sql_skus": sql_skus, "daily": daily_list,
        "fixed_per_day": fixed_per_day, "var_median": var_median,
        "unknown_sql_skus": sorted(unknown),
        "currencies": sorted({r["currency"] for r in rows} - {"KRW"}),
    }
