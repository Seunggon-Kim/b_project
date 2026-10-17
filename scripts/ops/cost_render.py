# -*- coding: utf-8 -*-
"""비용 보고서 HTML 을 그립니다(인라인 SVG, 툴팁).

모양과 툴팁 문구는 미리보기 3차안(docs/superpowers/plans/assets/2026-10-18-data-ops/)
그대로입니다. 숫자는 cost_billing.summarize·cost_cloudflare.summarize 의 dict 입니다.
둘 중 하나가 None 이면 그 칸만 안내 글로 바꿉니다.
"""
import datetime as dt
import html
import json
import math
from pathlib import Path
from string import Template

from scripts.ops import cost_cloudflare as cfm
from scripts.ops.cost_billing import VAR_KEYS

TEMPLATE = Path(__file__).with_name("cost_report_template.html")
WD = "월화수목금토일"
MCOLOR = {"Cloud SQL": "#3b82f6", "BigQuery": "#8b5cf6", "Cloud Monitoring": "#10b981", "기타": "#94a3b8"}
VCOLOR = {"백업·PITR 로그": "#3b82f6", "네트워크": "#0ea5e9", "BigQuery": "#8b5cf6", "기타": "#94a3b8"}


def _e(s):
    return html.escape(str(s), quote=True)


def _won(v):
    return f"{v:,.0f}"


def _tip(*lines):
    return f' tabindex="0" data-tip="{_e(chr(10).join(lines))}"'


def _info(*lines):
    return f'<span class="info"{_tip(*lines)}>i</span>'


def _nice_ceil(v):
    if v <= 0:
        return 1
    e = 10 ** math.floor(math.log10(v))
    for m in (1, 2, 2.5, 5, 10):
        if m * e >= v:
            return m * e
    return 10 * e


def _dlabel(day):
    d = dt.date.fromisoformat(day) if isinstance(day, str) else day
    return f"{d.isoformat()} ({WD[d.weekday()]})"


# ---- GCP ----------------------------------------------------------------

def _summary(b):
    return (
        '<section><h2>이번 달 요약 '
        + _info("이번 달 요약", "GCP 에서 이번 달에 나간 돈을 세 가지로 봅니다.",
                "모든 금액은 크레딧을 뺀 순액(원)입니다.",
                "순액 = 비용 + 크레딧 합계(크레딧은 음수로 들어옵니다).")
        + '</h2><p class="h2sub">GCP 금액은 크레딧을 뺀 순액(원)입니다.</p><div class="tiles">'
        + '<div class="tile"><div class="k">이번 달 누적 '
        + _info("이번 달 누적", "1일부터 결제 데이터가 들어온 마지막 시각까지 GCP 순액을 더한 값입니다.",
                "계산식: 1일부터 마지막 반영 시각까지 (비용 + 크레딧) 합계",
                "결제 데이터는 몇 시간에서 하루 늦게 들어오므로 오늘 쓴 돈은 아직 덜 잡혀 있습니다.")
        + f'</div><div class="v">{_won(b["total"])}<small>원</small></div>'
        + f'<div class="f">{b["month"]} 1일 ~ {b["days_elapsed"]}일 · 하루 평균 {_won(b["avg_per_day"])}원</div></div>'
        + '<div class="tile"><div class="k">월말 예상 (단순 추정) '
        + _info("월말 예상 (단순 추정)", "지금까지의 하루 평균이 월말까지 이어진다고 보고 곱한 값입니다.",
                f"계산식: 누적 ÷ 지난 날 수({b['days_elapsed']}) × 그 달 일수({b['days_in_month']})",
                "학습 기간: 이번 달 1일 ~ 마지막 반영일. 예측 범위: 이번 달 말일까지.",
                "DB 사양 변경, 새 서비스 추가, 백업 증가처럼 쓰임이 바뀌면 맞지 않습니다. 오차 범위는 따로 계산하지 않습니다.")
        + f'</div><div class="v">{_won(b["forecast"])}<small>원</small></div>'
        + f'<div class="f">누적 ÷ 지난 날 수({b["days_elapsed"]}) × 그 달 일수({b["days_in_month"]})</div></div>'
        + '<div class="tile"><div class="k">예산 대비 '
        + _info("예산 대비", "이번 달 누적이 월 예산의 몇 % 인지 봅니다.",
                f"계산식: 누적 ÷ {_won(b['budget'])}원 × 100 (월말 예상 기준: 월말 예상 ÷ {_won(b['budget'])}원 × 100)",
                "GCP 예산 알림은 이와 별도로 50·90·100% 에서 메일로 옵니다.")
        + f'</div><div class="v">{b["ratio_pct"]}<small>%</small></div>'
        + f'<div class="gauge"><span style="width:{min(b["ratio_pct"], 100)}%"></span></div>'
        + f'<div class="f">누적 ÷ 월 예산 {_won(b["budget"])}원 · 월말 예상 기준 {b["forecast_ratio_pct"]}%</div></div>'
        + '</div></section>')


def _month_row(m, budget):
    tot = m["total"]
    label = m["month"] + (" (진행 중)" if m["partial"] else "")
    lines = [label, f"합계 {_won(tot)}원 · 예산의 {tot / budget * 100:.1f}%"]
    lines += [f"{k}\t{_won(m[k])}원" for k in MCOLOR]
    lines.append(f"=합계\t{_won(tot)}원")
    if m["partial"]:
        lines.append("진행 중인 달입니다. 결제 데이터가 들어온 마지막 날까지의 값입니다.")
    cells = "".join(f"<td>{_won(m[k])}</td>" for k in MCOLOR)
    return f'<tr{_tip(*lines)}><th scope="row">{_e(label)}</th>{cells}<td class="sum">{_won(tot)}</td></tr>'


HEAD_TIPS = {
    "Cloud SQL": ("Cloud SQL", "bstats 의 MySQL 데이터베이스 비용입니다.",
                  "서버가 켜져 있는 시간, 디스크, 백업, 나가는 트래픽이 모두 이 칸에 들어갑니다. 오른쪽 '세부' 표에서 나눠 봅니다."),
    "BigQuery": ("BigQuery", "주간 복사본과 결제 내보내기 표의 저장·조회 비용입니다.",
                 "무료 한도(저장 10GB, 조회 월 1TB) 안이면 0원입니다.", "0원이 아니면 큰 조회가 있었는지 확인할 대상입니다."),
    "Cloud Monitoring": ("Cloud Monitoring", "가동 확인과 경보의 비용입니다.", "무료 한도 안이면 0원입니다."),
    "기타": ("기타", "위 세 서비스 밖의 비용입니다.", "꾸준히 0원이 아니면 무엇이 붙는지 확인할 대상입니다."),
}


def _months(b):
    th = "".join("<th>%s%s</th>" % ("Monitoring" if k == "Cloud Monitoring" else k, _info(*HEAD_TIPS[k]))
                 for k in MCOLOR)
    rows = "".join(_month_row(m, b["budget"]) for m in b["months"])
    return (
        '<section><h2>GCP 서비스별 월 비용 '
        + _info("GCP 서비스별 월 비용", "달마다 서비스별 순액을 원 단위로 더한 표입니다.",
                "결제 내보내기를 켠 뒤 들어온 달만 나옵니다. 그 전 달은 결제 콘솔에서 확인하십시오.")
        + '</h2><p class="h2sub">단위: 원 · 결제 내보내기를 켠 뒤 들어온 달만 나옵니다.</p>'
        + f'<table><thead><tr><th>월</th>{th}<th>합계'
        + _info("합계", "그 달 네 칸을 더한 순액입니다.", "계산식: Cloud SQL + BigQuery + Monitoring + 기타")
        + f'</th></tr></thead><tbody>{rows}</tbody></table></section>')


def _skus(b):
    total = sum(x["amount"] for x in b["sql_skus"])
    rows = []
    for x in b["sql_skus"]:
        tip = _info(x["sku"], f"{_won(x['amount'])}원 · Cloud SQL 의 {x['share_pct']}% · {x['kind']}비",
                    "고정비는 매일 같은 금액이 붙는 항목, 변동비는 쓰임에 따라 달라지는 항목입니다.",
                    f"비중 = {_won(x['amount'])} ÷ {_won(total)} × 100")
        kcls = "fx" if x["kind"] == "고정" else "vr"
        rows.append(f'<tr><th scope="row">{_e(x["sku"])} <span class="kind {kcls}">{x["kind"]}</span></th>'
                    f'<td>{_won(x["amount"])}</td><td><div class="bar"><span style="width:{x["share_pct"]}%"></span></div></td>'
                    f'<td>{x["share_pct"]}% {tip}</td></tr>')
    return (
        '<section><h2>Cloud SQL 세부 '
        + _info("Cloud SQL 세부", "Cloud SQL 비용을 요금 항목(SKU)별로 나눈 표입니다.",
                "DB 사양을 바꿀지, 디스크를 줄일지 판단할 때 씁니다.")
        + f'</h2><p class="h2sub">합계 {_won(total)}원 · 비중 = 그 항목 금액 ÷ Cloud SQL 합계 × 100</p>'
        + '<table><thead><tr><th>항목</th><th>금액</th><th></th><th>비중</th></tr></thead>'
        + f'<tbody>{"".join(rows)}</tbody></table></section>')


def _var_chart(b, w=1080, h=210):
    days = b["daily"]
    pad_l, pad_r, pad_t, pad_b = 48, 12, 12, 34
    iw, ih = w - pad_l - pad_r, h - pad_t - pad_b
    vsum = [sum(d[k] for k in VAR_KEYS) for d in days]
    vmax = _nice_ceil(max(vsum + [1]) * 1.1)
    n = len(days)
    bw = iw / n * 0.68
    out = [f'<svg viewBox="0 0 {w} {h}" width="100%" role="img" aria-label="GCP 일별 변동비">']
    for k in range(5):
        g = vmax * k / 4
        y = pad_t + ih - ih * g / vmax
        out.append(f'<line x1="{pad_l}" x2="{w - pad_r}" y1="{y:.1f}" y2="{y:.1f}" class="grid"/>')
        out.append(f'<text x="{pad_l - 8}" y="{y + 4:.1f}" class="ax" text-anchor="end">{g:,.0f}</text>')
    my = pad_t + ih - ih * b["var_median"] / vmax
    out.append(f'<line x1="{pad_l}" x2="{w - pad_r}" y1="{my:.1f}" y2="{my:.1f}" class="med"/>')
    hits = []
    for i, d in enumerate(days):
        x = pad_l + iw / n * i + (iw / n - bw) / 2
        y0 = pad_t + ih
        for key in VAR_KEYS:
            v = d[key]
            if v <= 0:
                continue
            hh = ih * v / vmax
            y0 -= hh
            op = ' opacity="0.35"' if d["partial"] else ''
            out.append(f'<rect x="{x:.1f}" y="{y0:.1f}" width="{bw:.1f}" height="{hh:.1f}" fill="{VCOLOR[key]}"{op} rx="1.5"/>')
        if i % 3 == 0 or d["partial"]:
            out.append(f'<text x="{x + bw / 2:.1f}" y="{h - 14}" class="ax" text-anchor="middle">'
                       f'{int(d["day"][5:7])}/{int(d["day"][8:])}</text>')
        vs = vsum[i]
        if d["partial"]:
            second = "집계 중: 결제 데이터가 아직 다 들어오지 않았습니다."
        elif b["var_median"]:
            second = f"변동비 {_won(vs)}원 · 지난 29일 중앙값의 {vs / b['var_median'] * 100:.0f}%"
        else:
            second = f"변동비 {_won(vs)}원"
        lines = [_dlabel(d["day"]), second]
        lines += [f"{k}\t{_won(d[k])}원" for k in VAR_KEYS]
        lines += [f"=변동비 합계\t{_won(vs)}원", f"고정비\t{_won(d['fixed'])}원",
                  f"=그날 전체\t{_won(vs + d['fixed'])}원"]
        hits.append(f'<rect class="hit" x="{pad_l + iw / n * i:.1f}" y="{pad_t}" width="{iw / n:.1f}" '
                    f'height="{ih}" data-tip="{_e(chr(10).join(lines))}"/>')
    out.append(f'<text x="{w - pad_r}" y="{h - 1}" class="ax note" text-anchor="end">집계 중</text>')
    out += hits
    out.append('</svg>')
    return "".join(out)


def _daily(b):
    past = b["daily"][:-1]
    avg_all = sum(d["fixed"] + sum(d[k] for k in VAR_KEYS) for d in past) / len(past)
    share = round(b["fixed_per_day"] / avg_all * 100) if avg_all else 0
    legend = "".join(f'<span class="lg"><i style="background:{c}"></i>{k}</span>' for k, c in VCOLOR.items())
    legend += f'<span class="lg"><i class="dash"></i>점선: 지난 29일 변동비 중앙값 {_won(b["var_median"])}원</span>'
    return (
        '<section><h2>GCP 일별 변동비 (최근 30일) '
        + _info("GCP 일별 변동비",
                "날마다 달라지는 비용만 쌓은 막대입니다. 매일 같은 고정비는 위 회색 줄에 따로 적었습니다.",
                "변동비 = 백업·PITR 로그 + 네트워크 + BigQuery + 기타",
                "점선은 지난 29일 변동비의 중앙값입니다. 막대가 점선보다 훨씬 높은 날은 재적재·큰 복사·큰 조회가 있었는지 확인할 날입니다.",
                "날짜는 결제 데이터의 사용 시작 시각을 KST 로 바꾼 날 기준입니다. 오늘 칸은 결제 데이터가 아직 다 들어오지 않아 흐리게 그립니다.")
        + '</h2><p class="h2sub">단위: 원/일 · 막대에 마우스를 올리면 그날 고정비를 더한 전체 금액도 나옵니다.</p>'
        + '<div class="fixline"><span class="kind fx">고정</span><span>Cloud SQL 고정 항목 '
        + f'<b>하루 {_won(b["fixed_per_day"])}원</b> · 지난 29일 평균 · 하루 비용의 약 {share}% '
        + _info("고정비", "Cloud SQL 인스턴스 시간과 디스크 저장소처럼 매일 같은 금액이 붙는 항목입니다. 막대에서 뺐습니다.",
                "비율 계산식: 고정비 ÷ 지난 29일 하루 평균 전체 비용 × 100",
                "이 줄이 바뀌면 DB 사양이나 디스크 크기가 바뀐 것입니다.")
        + f'</span></div><div class="legend">{legend}</div>{_var_chart(b)}</section>')


def _billing_html(b, note):
    if b is None:
        return f'<section><h2>GCP 비용</h2><p class="h2sub">{_e(note)}</p></section>'
    return _summary(b) + f'<div class="two">{_months(b)}{_skus(b)}</div>' + _daily(b)


# ---- Cloudflare -----------------------------------------------------------

def _usage_chart(vals, days, limit, show_limit, color, label, unit, tipfn=None, w=360, h=170):
    pad_l, pad_r, pad_t, pad_b = 40, 8, 10, 24
    iw, ih = w - pad_l - pad_r, h - pad_t - pad_b
    peak = max(vals + [0])
    vmax = limit if show_limit else _nice_ceil(peak * 1.1)
    if not show_limit and peak <= 40:
        vmax = max(4, math.ceil(peak * 1.1 / 4) * 4)  # 건수가 작으면 눈금을 정수로
    n = len(vals)
    bw = iw / n * 0.66

    def fmt(v):
        return f"{v / 1000:g}천" if v >= 1000 else f"{v:g}"
    out = [f'<svg viewBox="0 0 {w} {h}" width="100%" role="img" aria-label="{_e(label)}">']
    for k in range(5):
        g = vmax * k / 4
        y = pad_t + ih - ih * g / vmax
        out.append(f'<line x1="{pad_l}" x2="{w - pad_r}" y1="{y:.1f}" y2="{y:.1f}" class="grid"/>')
        out.append(f'<text x="{pad_l - 6}" y="{y + 4:.1f}" class="ax" text-anchor="end">{fmt(g)}</text>')
    if show_limit:
        out.append(f'<line x1="{pad_l}" x2="{w - pad_r}" y1="{pad_t}" y2="{pad_t}" class="limit"/>')
    imax = max(range(n), key=lambda i: vals[i])
    avg = sum(vals) / n
    hits = []
    for i, v in enumerate(vals):
        x = pad_l + iw / n * i + (iw / n - bw) / 2
        hh = ih * v / vmax
        out.append(f'<rect x="{x:.1f}" y="{pad_t + ih - hh:.1f}" width="{bw:.1f}" height="{hh:.1f}" '
                   f'fill="{color}" opacity="{1 if i == imax else 0.72}" rx="1.5"/>')
        d = days[i]
        if tipfn:
            lines = tipfn(i, v, avg, i == imax)
        else:
            lines = [f"{d.isoformat()} (UTC, {WD[d.weekday()]})", f"{v:,}{unit} · 무료 한도의 {v / limit * 100:.1f}%",
                     f"30일 평균 {avg:,.0f}{unit}" + (" · 30일 중 가장 많은 날" if i == imax else ""),
                     f"남은 여유: {limit - v:,}{unit}"]
        hits.append(f'<rect class="hit" x="{pad_l + iw / n * i:.1f}" y="{pad_t}" width="{iw / n:.1f}" '
                    f'height="{ih}" data-tip="{_e(chr(10).join(lines))}"/>')
    for i, anchor in ((0, "start"), (n // 2, "middle"), (n - 1, "end")):
        x = {"start": pad_l, "middle": pad_l + iw / n * i + iw / n / 2, "end": w - pad_r}[anchor]
        out.append(f'<text x="{x:.1f}" y="{h - 6}" class="ax" text-anchor="{anchor}">{days[i].month}/{days[i].day}</text>')
    out += hits
    out.append('</svg>')
    return "".join(out)


def _gauge(peak, limit, unit):
    pct = peak / limit * 100
    tip = _tip("무료 한도까지 거리", f"30일 중 가장 많은 날 {peak:,}{unit} = 한도 {limit:,}{unit} 의 {pct:.1f}%",
               "계산식: 가장 많은 날 값 ÷ 하루 무료 한도 × 100",
               f"이 비율이 {cfm.LIMIT_LINE_AT * 100:.0f}% 를 넘으면 아래 차트 세로축을 한도까지 늘리고 빨간 한도 선을 그립니다.")
    return (f'<div class="lim"{tip}><div class="limbar"><span style="width:{min(pct, 100):.1f}%"></span></div>'
            f'<div class="limtxt"><b>최고 {pct:.1f}%</b><span>한도 {limit:,}/일</span></div></div>')


def _cf_html(c, note):
    if c is None:
        return f'<section><h2>Cloudflare 무료 한도 대비 사용량</h2><p class="h2sub">{_e(note)}</p></section>'
    days = c["days"]

    def cut_tip(i, v, avg, is_max):
        d = days[i]
        req = c["requests"][i]
        return [f"{d.isoformat()} (UTC, {WD[d.weekday()]})",
                f"끊긴 요청 {v}건 · 그날 요청의 {v / req * 100:.3f}%" if req else f"끊긴 요청 {v}건",
                f"그날 요청 {req:,}건 · CPU P99 {c['p99_by_day'][i]}ms",
                f"30일 평균 {avg:.1f}건" + (" · 30일 중 가장 많은 날" if is_max else "")]
    req_svg = _usage_chart(c["requests"], days, cfm.WORKERS_FREE_PER_DAY, c["show_limit_line"]["requests"],
                           "#f59e0b", "Workers 요청 수", "건")
    hyd_svg = _usage_chart(c["queries"], days, cfm.HYPERDRIVE_FREE_PER_DAY, c["show_limit_line"]["queries"],
                           "#0ea5e9", "Hyperdrive 질의 수", "건")
    cut_svg = _usage_chart(c["cut"], days, None, False, "#ef4444", "CPU 한도 초과로 끊긴 요청", "건", tipfn=cut_tip)
    ci = max(range(len(days)), key=lambda i: c["cut"][i])
    times = c["cpu_p99_ms"] / cfm.CPU_LIMIT_MS
    rp, hp = c["req_peak_day"], c["hyd_peak_day"]
    return (
        '<section><h2>Cloudflare 무료 한도 대비 사용량 (최근 30일) '
        + _info("Cloudflare 무료 한도 대비 사용량",
                "bstats API 는 Cloudflare 무료 플랜이라 금액은 0원입니다. 대신 하루 한도를 넘으면 그날 남은 요청이 오류가 되므로 한도까지 얼마나 남았는지 봅니다.",
                "회색 게이지가 30일 중 가장 많은 날이 한도의 몇 % 였는지 보여 줍니다. 가운데 점선이 50% 입니다.",
                "차트 세로축은 실제 값에 맞춰 날마다의 차이가 보이게 했습니다. 가장 많은 날이 한도의 50% 를 넘으면 세로축을 한도까지 늘리고 빨간 한도 선을 그립니다.",
                "날짜는 Cloudflare 집계 기준인 UTC 하루입니다(KST 오전 9시에 바뀝니다).")
        + '</h2><p class="h2sub">금액은 0원(무료 플랜)입니다. 게이지 = 한도까지 거리, 차트 = 날마다의 변화(세로축은 실제 값). 날짜 기준 UTC 하루.</p>'
        + '<div class="cf">'
        + f'<div class="cfbox"><h3>Workers 요청 수 · {cfm.WORKER} '
        + _info("Workers 요청 수", f"bstats API Worker({cfm.WORKER})가 처리한 요청 수입니다.",
                "화면 한 번 열 때 보통 여러 건이 나갑니다.",
                f"무료 플랜 한도: 하루 {cfm.WORKERS_FREE_PER_DAY:,}건. 넘으면 그날 남은 요청이 오류로 돌아갑니다.")
        + f'</h3><div class="peak">가장 많은 날 <b>{rp.month}/{rp.day} · {c["req_peak"]:,}건</b><br>막대에 마우스를 올리면 그날 값이 나옵니다.</div>'
        + _gauge(c["req_peak"], cfm.WORKERS_FREE_PER_DAY, "건") + req_svg + '</div>'
        + '<div class="cfbox"><h3>Hyperdrive 질의 수 '
        + _info("Hyperdrive 질의 수", "Worker 가 Hyperdrive 를 거쳐 MySQL 에 보낸 질의 수입니다. Hyperdrive 캐시에서 바로 답한 질의도 포함합니다.",
                "무료 플랜 하루 한도 기준입니다. 한도 값은 Cloudflare 안내에 따라 바뀔 수 있습니다.")
        + f'</h3><div class="peak">가장 많은 날 <b>{hp.month}/{hp.day} · {c["hyd_peak"]:,}건</b><br>요청 1건이 질의 여러 건을 부르기도 합니다.</div>'
        + _gauge(c["hyd_peak"], cfm.HYPERDRIVE_FREE_PER_DAY, "건") + hyd_svg + '</div>'
        + '<div class="cfbox"><h3>CPU 한도 초과로 끊긴 요청 '
        + _info("CPU 한도 초과로 끊긴 요청",
                f"CPU 한도(요청당 {cfm.CPU_LIMIT_MS}ms)를 넘어 Cloudflare 가 중간에 멈춘 요청 수입니다. 이 요청은 사용자 화면에 오류나 빈칸으로 보입니다.",
                "끊긴 비율 = 30일 끊긴 요청 ÷ 30일 전체 요청 × 100",
                "CPU 중앙값·P99 는 요청 하나가 Worker 에서 쓴 CPU 시간입니다(MySQL 응답을 기다린 시간은 빠짐). P99 는 가장 무거운 1% 의 경계입니다.",
                "무료 플랜은 가끔 넘는 요청을 봐주기도 해서, P99 가 한도를 넘어도 끊긴 요청은 적게 나올 수 있습니다.")
        + f'</h3><div class="stats"><span>30일 <b class="hot">{c["cut_total"]}건</b></span>'
        + f'<span>전체의 <b>{c["cut_pct"]}%</b></span><span>CPU 중앙값 <b>{c["cpu_p50_ms"]}ms</b></span>'
        + f'<span>P99 <b>{c["cpu_p99_ms"]}ms</b> (한도의 {times:.1f}배)</span></div>'
        + f'<div class="limnone">한도 없음: 0건이 목표입니다 · 가장 많은 날 {days[ci].month}/{days[ci].day} {c["cut"][ci]}건</div>'
        + cut_svg + '</div></div></section>')


def _notes_html(b, c):
    notes = ["GCP: 결제 빅쿼리 내보내기(표준 사용 비용) 기준입니다. 결제 데이터는 몇 시간에서 하루 늦게 들어옵니다.",
             "내보내기를 켜기 전 기간은 비어 있을 수 있습니다. 그 기간은 결제 콘솔에서 확인하십시오.",
             "Cloudflare: GraphQL 분석 API 기준입니다. 무료 한도 값은 코드 상수(확인 날짜 주석)를 따르며 바뀔 수 있습니다."]
    if b:
        if b["unknown_sql_skus"]:
            notes.append("고정비 목록에 없어 변동비로 넣은 Cloud SQL 항목: " + ", ".join(b["unknown_sql_skus"]))
        if b["currencies"]:
            notes.append("원 말고 다른 통화가 있습니다: " + ", ".join(b["currencies"]))
        notes.append("이번 달 Cloud SQL 항목 분류: " + "; ".join(f"{x['sku']} = {x['kind']}" for x in b["sql_skus"]))
    return "".join(f"<li>{_e(n)}</li>" for n in notes)


def render(billing, cf, meta):
    month = billing["month"] if billing else ""
    tpl = Template(TEMPLATE.read_text(encoding="utf-8"))
    return tpl.substitute(
        month_label=_e(f"{month[:4]}년 {int(month[5:7])}월" if month else ""),
        made_at=_e(meta["made_at"]),
        billing_html=_billing_html(billing, meta.get("billing_note", "")),
        cf_html=_cf_html(cf, meta.get("cf_note", "")),
        notes_html=_notes_html(billing, cf),
        colors_json=json.dumps({**MCOLOR, **VCOLOR, "고정비": "#475569"}, ensure_ascii=False),
    )
