"""비용 보고서 시험이 함께 쓰는 예시 데이터입니다(실제 결제·사용량 아님)."""
import datetime as dt

SQL = "Cloud SQL"
INST = "Cloud SQL for MySQL: Zonal - Micro instance in Seoul"
DISK = "Cloud SQL for MySQL: Zonal - Standard storage in Seoul"
BACK = "Cloud SQL for MySQL: Backups in Seoul"
EGR = "Network Internet Egress from Seoul to Americas"
ODD = "Cloud SQL for MySQL: Something new in Seoul"
DAYS = [dt.date(2026, 9, 19) + dt.timedelta(days=i) for i in range(30)]


def row(day, service, sku, net, month=None, currency="KRW"):
    return {"month": month or day[:4] + day[5:7], "service": service, "sku": sku,
            "day": dt.date.fromisoformat(day), "currency": currency, "net": net}


def month_rows():
    rows = []
    for d in range(1, 19):
        day = "2026-10-%02d" % d
        rows += [row(day, SQL, INST, 340), row(day, SQL, DISK, 77),
                 row(day, SQL, BACK, 26), row(day, SQL, EGR, 9)]
    rows.append(row("2026-10-09", SQL, BACK, 95))
    rows.append(row("2026-10-12", "BigQuery", "Analysis", 12))
    rows.append(row("2026-10-05", SQL, ODD, 3))
    rows.append(row("2026-09-30", SQL, INST, 340, month="202609"))
    return rows


def cf_resp(req_by_day, cut_by_day=None, q_by_day=None, p50=4800, p99=21600):
    """Cloudflare GraphQL 응답 모양(cost_cloudflare.graphql_query 의 별칭 inv·cpuDaily·cpuAll·hyd)."""
    cut_by_day = cut_by_day or {}
    q_by_day = q_by_day or {}
    inv = []
    for d, n in req_by_day.items():
        cut = cut_by_day.get(d, 0)
        inv.append({"dimensions": {"date": d.isoformat(), "status": "success"}, "sum": {"requests": n - cut}})
        if cut:
            inv.append({"dimensions": {"date": d.isoformat(), "status": "exceededResources"},
                        "sum": {"requests": cut}})
    daily_cpu = [{"dimensions": {"date": d.isoformat()}, "quantiles": {"cpuTimeP99": 20000}}
                 for d in req_by_day]
    return {"data": {"viewer": {"accounts": [{
        "inv": inv, "cpuDaily": daily_cpu,
        "cpuAll": [{"quantiles": {"cpuTimeP50": p50, "cpuTimeP99": p99}}],
        "hyd": [{"dimensions": {"date": d.isoformat()}, "count": n} for d, n in q_by_day.items()],
    }]}}, "errors": None}
