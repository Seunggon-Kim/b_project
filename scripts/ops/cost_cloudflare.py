# -*- coding: utf-8 -*-
"""Cloudflare GraphQL 분석 API 응답을 무료 한도 대비 일별 값으로 바꿉니다.

날짜는 Cloudflare 집계 기준인 UTC 하루입니다. CPU 시간은 마이크로초로 온다고
보고 밀리초로 바꿉니다(단위는 아래처럼 미확인). 호출은 cost_report.py 가 합니다.

확인한 항목은 상수 옆에 날짜를, 확인하지 못한 항목은 '미확인'을 적었습니다.

문서 확인 결과(2026-10-18):
- workersInvocationsAdaptive 데이터셋, dimensions scriptName·status, sum requests,
  quantiles cpuTimeP50·cpuTimeP99: 확인(Querying Workers Metrics with GraphQL).
- dimensions date(두 데이터셋): 미확인(문서에는 datetime 만 나옴) — 없는 칸이면
  GraphQL 이 오류를 돌려주므로 첫 실제 실행에서 SchemaMismatch 로 드러납니다.
- CPU 시간 단위(마이크로초): 미확인(문서에서 찾지 못함). 단위가 달라도 응답 모양은
  같아 SchemaMismatch 가 나지 않고 값만 1000배 어긋납니다. 첫 실제 실행에서
  CPU 중앙값이 수 ms 범위(운영 기록상 대략 4~25ms)인지 눈으로 확인합니다.
- hyperdriveQueriesAdaptiveGroups 와 count: 확인(Hyperdrive Metrics). dimensions date 는 미확인.
"""

WORKER = "kbo-api"
# 확인: 2026-10-18, Workers 'Platform limits' 문서(Free: 하루 100,000 요청, UTC 자정 초기화)
WORKERS_FREE_PER_DAY = 100_000
# 확인: 2026-10-18, Hyperdrive 'Pricing' 문서(Free: 100,000 / day)
HYPERDRIVE_FREE_PER_DAY = 100_000
CPU_LIMIT_MS = 10                   # 확인: 2026-10-18, Workers 'Platform limits'(Free: HTTP 요청당 CPU 10ms)
LIMIT_LINE_AT = 0.5                 # 가장 많은 날이 한도의 50% 를 넘으면 한도선을 그립니다
# 확인: 2026-10-18, Workers 'Metrics and analytics' 문서의 상태 표(exceededResources 는 주로 CPU 초과).
# 단 CPU 초과 전용 값인지는 미확인(문서에서 찾지 못함). 뜻이 달라도 SchemaMismatch 는 나지 않으므로
# 첫 실제 실행에서 끊긴 요청 수가 운영 기록과 맞는지 눈으로 확인합니다
CUT_STATUS = "exceededResources"


class SchemaMismatch(Exception):
    """응답에 기대한 칸이 없습니다(데이터셋·칸 이름이 바뀌었을 수 있음)."""


def graphql_query():
    w = '{scriptName: "%s", date_geq: $start, date_leq: $end}' % WORKER
    return (
        "query($acct: String!, $start: Date!, $end: Date!) { viewer { accounts(filter: {accountTag: $acct}) {"
        " inv: workersInvocationsAdaptive(limit: 10000, filter: %s) { dimensions { date status } sum { requests } }"
        " cpuDaily: workersInvocationsAdaptive(limit: 100, filter: %s) { dimensions { date } quantiles { cpuTimeP99 } }"
        " cpuAll: workersInvocationsAdaptive(limit: 1, filter: %s) { quantiles { cpuTimeP50 cpuTimeP99 } }"
        " hyd: hyperdriveQueriesAdaptiveGroups(limit: 100, filter: {date_geq: $start, date_leq: $end})"
        " { dimensions { date } count }"
        " } } }" % (w, w, w))


def _get(acc, key):
    if key not in acc or acc[key] is None:
        raise SchemaMismatch("응답에 %s 가 없습니다" % key)
    return acc[key]


def summarize(resp, days):
    if resp.get("errors"):
        raise SchemaMismatch("; ".join(e.get("message", "") for e in resp["errors"]))
    try:
        acc = resp["data"]["viewer"]["accounts"][0]
    except (TypeError, KeyError, IndexError):
        raise SchemaMismatch("응답에 accounts 가 없습니다") from None
    idx = {d.isoformat(): i for i, d in enumerate(days)}
    n = len(days)
    req, cut, qs, p99d = [0] * n, [0] * n, [0] * n, [0.0] * n
    for g in _get(acc, "inv"):
        i = idx.get(g["dimensions"]["date"])
        if i is None:
            continue
        v = int(g["sum"]["requests"])
        req[i] += v
        if g["dimensions"]["status"] == CUT_STATUS:
            cut[i] += v
    for g in _get(acc, "cpuDaily"):
        i = idx.get(g["dimensions"]["date"])
        if i is not None:
            p99d[i] = round(g["quantiles"]["cpuTimeP99"] / 1000, 1)
    for g in _get(acc, "hyd"):
        i = idx.get(g["dimensions"]["date"])
        if i is not None:
            qs[i] += int(g["count"])
    all_q = _get(acc, "cpuAll")
    if not all_q:
        raise SchemaMismatch("cpuAll 이 비었습니다")
    q = all_q[0]["quantiles"]
    ri = max(range(n), key=lambda i: req[i])
    hi = max(range(n), key=lambda i: qs[i])
    total = sum(req)
    return {
        "days": days, "requests": req, "queries": qs, "cut": cut, "p99_by_day": p99d,
        "cpu_p50_ms": round(q["cpuTimeP50"] / 1000, 1), "cpu_p99_ms": round(q["cpuTimeP99"] / 1000, 1),
        "cut_total": sum(cut), "cut_pct": round(sum(cut) / total * 100, 3) if total else 0.0,
        "req_peak": req[ri], "req_peak_day": days[ri], "hyd_peak": qs[hi], "hyd_peak_day": days[hi],
        "show_limit_line": {"requests": req[ri] >= WORKERS_FREE_PER_DAY * LIMIT_LINE_AT,
                            "queries": qs[hi] >= HYPERDRIVE_FREE_PER_DAY * LIMIT_LINE_AT},
    }
