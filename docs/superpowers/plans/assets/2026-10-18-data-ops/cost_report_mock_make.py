# 비공개 비용 보고서 미리보기 목업 (숫자는 전부 예시 값)
import html, json, math, random, datetime as dt
from string import Template

random.seed(7)
END = dt.date(2026, 10, 18)
DAYS = [END - dt.timedelta(days=i) for i in range(29, -1, -1)]
WD = "월화수목금토일"
BUDGET = 30000

def won(v):
    return f"{v:,.0f}"

def attr(s):
    return html.escape(s, quote=True)

def dlabel(d):
    return f"{d.year}-{d.month:02d}-{d.day:02d} ({WD[d.weekday()]})"

def nice_ceil(v):
    """축 위쪽 끝: 값보다 조금 큰 1·2·5 단위 수."""
    if v <= 0:
        return 1
    e = 10 ** math.floor(math.log10(v))
    for m in (1, 2, 2.5, 5, 10):
        if m * e >= v:
            return m * e
    return 10 * e

# ---- 예시 데이터: 하루 단위 SKU ----
# 고정비: 인스턴스 시간 + 저장소 (매일 같음)
FIX_INST, FIX_DISK = 340, 77
VAR = ["백업·PITR 로그", "네트워크", "BigQuery", "기타"]
COLOR = {"백업·PITR 로그": "#3b82f6", "네트워크": "#0ea5e9", "BigQuery": "#8b5cf6", "기타": "#94a3b8"}
NOTE = {}
rows = []
for d in DAYS:
    backup = 26 + random.randint(-4, 6)
    net = 9 + random.randint(-3, 4)
    bq = 0
    etc = random.choice([0, 0, 3, 5])
    if d.weekday() == 0:  # 월요일 KST 새벽: 주간 빅쿼리 복사
        net += 18
        bq = random.choice([6, 9, 12])
        NOTE[d] = "주간 빅쿼리 복사가 돈 날이라 네트워크·BigQuery 가 조금 오릅니다."
    if d == dt.date(2026, 10, 1):
        backup += 40
        NOTE[d] = "매월 1일은 월 단위 백업 보관 요금이 함께 잡혀 조금 높습니다."
    if d == dt.date(2026, 10, 9):
        backup += 95
        net += 30
        NOTE[d] = "손 재적재가 있었던 날(예시)이라 변경 로그와 트래픽이 늘었습니다."
    rows.append({"d": d, "inst": FIX_INST, "disk": FIX_DISK,
                 "백업·PITR 로그": backup, "네트워크": net, "BigQuery": bq, "기타": etc})

def var_sum(r):
    return sum(r[k] for k in VAR)

def total(r):
    return r["inst"] + r["disk"] + var_sum(r)

fixed_day = FIX_INST + FIX_DISK
var_med = sorted(var_sum(r) for r in rows[:-1])[len(rows) // 2]

# ---- 1. 변동비 일별 막대 ----
def var_chart(w=1080, h=210):
    pad_l, pad_r, pad_t, pad_b = 48, 12, 12, 34
    iw, ih = w - pad_l - pad_r, h - pad_t - pad_b
    vmax = nice_ceil(max(var_sum(r) for r in rows) * 1.1)
    n = len(rows)
    bw = iw / n * 0.68
    out = [f'<svg viewBox="0 0 {w} {h}" width="100%" role="img" aria-label="GCP 일별 변동비">']
    for k in range(5):
        g = vmax * k / 4
        y = pad_t + ih - ih * g / vmax
        out.append(f'<line x1="{pad_l}" x2="{w-pad_r}" y1="{y:.1f}" y2="{y:.1f}" class="grid"/>')
        out.append(f'<text x="{pad_l-8}" y="{y+4:.1f}" class="ax" text-anchor="end">{g:,.0f}</text>')
    my = pad_t + ih - ih * var_med / vmax
    out.append(f'<line x1="{pad_l}" x2="{w-pad_r}" y1="{my:.1f}" y2="{my:.1f}" class="med"/>')
    hits = []
    for i, r in enumerate(rows):
        d = r["d"]
        x = pad_l + iw / n * i + (iw / n - bw) / 2
        y0 = pad_t + ih
        partial = d == END
        for key in VAR:
            v = r[key]
            if v <= 0:
                continue
            hh = ih * v / vmax
            y0 -= hh
            op = ' opacity="0.35"' if partial else ''
            out.append(f'<rect x="{x:.1f}" y="{y0:.1f}" width="{bw:.1f}" height="{hh:.1f}" fill="{COLOR[key]}"{op} rx="1.5"/>')
        if i % 3 == 0 or partial:
            out.append(f'<text x="{x+bw/2:.1f}" y="{h-14}" class="ax" text-anchor="middle">{d.month}/{d.day}</text>')
        vs = var_sum(r)
        lines = [dlabel(d),
                 "집계 중: 결제 데이터가 아직 다 들어오지 않았습니다." if partial
                 else f"변동비 {won(vs)}원 · 30일 중앙값의 {vs/var_med*100:.0f}%"]
        lines += [f"{k}\t{won(r[k])}원" for k in VAR]
        lines.append(f"=변동비 합계\t{won(vs)}원")
        lines.append(f"고정비\t{won(fixed_day)}원")
        lines.append(f"=그날 전체\t{won(total(r))}원")
        if d in NOTE:
            lines.append(NOTE[d])
        demo = ' data-demo="day"' if d == dt.date(2026, 10, 9) else ''
        hits.append(f'<rect class="hit" x="{pad_l + iw / n * i:.1f}" y="{pad_t}" width="{iw / n:.1f}" height="{ih}"{demo} data-tip="{attr(chr(10).join(lines))}"/>')
    lx = pad_l + iw / n * (n - 1) + (iw / n) / 2
    out.append(f'<text x="{lx:.1f}" y="{h-1}" class="ax note" text-anchor="middle">집계 중</text>')
    out += hits
    out.append('</svg>')
    return "".join(out)

# ---- 2·3. Cloudflare 일별 막대 (세로축 = 실제 값) ----
LIMIT_LINE_AT = 0.5  # 가장 많은 날이 한도의 50% 를 넘으면 한도 선을 그립니다.

def usage_chart(vals, limit, color, label, unit, demo=None, w=360, h=170, tipfn=None):
    pad_l, pad_r, pad_t, pad_b = 40, 8, 10, 24
    iw, ih = w - pad_l - pad_r, h - pad_t - pad_b
    peak = max(vals)
    show_limit = limit and peak >= limit * LIMIT_LINE_AT
    vmax = limit if show_limit else nice_ceil(peak * 1.1)
    if not show_limit and peak <= 40:
        vmax = math.ceil(peak * 1.1 / 4) * 4  # 건수가 작으면 눈금을 정수로
    n = len(vals)
    bw = iw / n * 0.66

    def fmt(v):
        return f"{v/1000:g}천" if v >= 1000 else f"{v:g}"
    out = [f'<svg viewBox="0 0 {w} {h}" width="100%" role="img" aria-label="{label}">']
    for k in range(5):
        g = vmax * k / 4
        y = pad_t + ih - ih * g / vmax
        out.append(f'<line x1="{pad_l}" x2="{w-pad_r}" y1="{y:.1f}" y2="{y:.1f}" class="grid"/>')
        out.append(f'<text x="{pad_l-6}" y="{y+4:.1f}" class="ax" text-anchor="end">{fmt(g)}</text>')
    if show_limit:
        out.append(f'<line x1="{pad_l}" x2="{w-pad_r}" y1="{pad_t}" y2="{pad_t}" class="limit"/>')
    imax = max(range(n), key=lambda i: vals[i])
    avg = sum(vals) / n
    hits = []
    for i, v in enumerate(vals):
        x = pad_l + iw / n * i + (iw / n - bw) / 2
        hh = ih * v / vmax
        op = "1" if i == imax else "0.72"
        out.append(f'<rect x="{x:.1f}" y="{pad_t+ih-hh:.1f}" width="{bw:.1f}" height="{max(hh, 0):.1f}" fill="{color}" opacity="{op}" rx="1.5"/>')
        d = DAYS[i]
        if tipfn:
            lines = tipfn(i, v, avg, i == imax)
        else:
            lines = [f"{d.year}-{d.month:02d}-{d.day:02d} (UTC, {WD[d.weekday()]})",
                     f"{v:,}{unit} · 무료 한도의 {v/limit*100:.1f}%",
                     f"30일 평균 {avg:,.0f}{unit}" + (" · 30일 중 가장 많은 날" if i == imax else ""),
                     f"남은 여유: {limit - v:,}{unit}"]
        dm = f' data-demo="{demo}"' if demo and i == imax else ''
        hits.append(f'<rect class="hit" x="{pad_l + iw / n * i:.1f}" y="{pad_t}" width="{iw / n:.1f}" height="{ih}"{dm} data-tip="{attr(chr(10).join(lines))}"/>')
    for i, anchor in ((0, "start"), (n // 2, "middle"), (n - 1, "end")):
        x = {"start": pad_l, "middle": pad_l + iw / n * i + iw / n / 2, "end": w - pad_r}[anchor]
        d = DAYS[i]
        out.append(f'<text x="{x:.1f}" y="{h-6}" class="ax" text-anchor="{anchor}">{d.month}/{d.day}</text>')
    out += hits
    out.append('</svg>')
    return "".join(out), imax

def gauge(peak, limit, unit):
    pct = peak / limit * 100
    tip = "\n".join([
        "무료 한도까지 거리",
        f"30일 중 가장 많은 날 {peak:,}{unit} = 한도 {limit:,}{unit} 의 {pct:.1f}%",
        "계산식: 가장 많은 날 값 ÷ 하루 무료 한도 × 100",
        f"이 비율이 {LIMIT_LINE_AT*100:.0f}% 를 넘으면 아래 차트 세로축을 한도까지 늘리고 빨간 한도 선을 그립니다.",
    ])
    return (f'<div class="lim" tabindex="0" data-tip="{attr(tip)}"><div class="limbar"><span style="width:{pct:.1f}%"></span></div>'
            f'<div class="limtxt"><b>최고 {pct:.1f}%</b><span>한도 {limit:,}/일</span></div></div>')

req = [random.randint(3200, 7800) + (4200 if d.weekday() in (5, 6) else 0) for d in DAYS]
req[-6] = 12480
hyp = [int(r * random.uniform(1.15, 1.35)) for r in req]
cut = [random.choice([0, 0, 1, 2, 3, 5]) for _ in DAYS]
cut[-6] = 9
p99 = [round(random.uniform(17, 24), 1) for _ in DAYS]

def cut_tip(i, v, avg, is_max):
    d = DAYS[i]
    return [f"{d.year}-{d.month:02d}-{d.day:02d} (UTC, {WD[d.weekday()]})",
            f"끊긴 요청 {v}건 · 그날 요청의 {v/req[i]*100:.3f}%",
            f"그날 요청 {req[i]:,}건 · CPU P99 {p99[i]}ms",
            f"30일 평균 {avg:.1f}건" + (" · 30일 중 가장 많은 날" if is_max else "")]

req_svg, req_i = usage_chart(req, 100000, "#f59e0b", "Workers 요청 수", "건", demo="req")
hyp_svg, hyp_i = usage_chart(hyp, 100000, "#0ea5e9", "Hyperdrive 질의 수", "건")
cut_svg, cut_i = usage_chart(cut, None, "#ef4444", "CPU 한도 초과로 끊긴 요청", "건", demo="cut", tipfn=cut_tip)

# ---- 월·SKU 표: 일별 값에서 계산 ----
oct_rows = [r for r in rows if r["d"].month == 10]
days_oct = len(oct_rows)
sql_parts = {
    "inst": sum(r["inst"] for r in oct_rows), "disk": sum(r["disk"] for r in oct_rows),
    "backup": sum(r["백업·PITR 로그"] for r in oct_rows), "net": sum(r["네트워크"] for r in oct_rows),
}
sql_oct = sum(sql_parts.values())
bq_oct = sum(r["BigQuery"] for r in oct_rows)
etc_oct = sum(r["기타"] for r in oct_rows)
oct_total = sql_oct + bq_oct + etc_oct
forecast = oct_total / days_oct * 31

MCOLOR = {"Cloud SQL": "#3b82f6", "BigQuery": "#8b5cf6", "Cloud Monitoring": "#10b981", "기타": "#94a3b8"}
months = [
    ("2026-08", 13980, 0, 0, 90),
    ("2026-09", 14410, 12, 0, 120),
    (f"2026-10 ({days_oct}일까지)", sql_oct, bq_oct, 0, etc_oct),
]

def month_row(m, a, b, c, e):
    tot = a + b + c + e
    lines = [f"{m}", f"합계 {won(tot)}원 · 예산의 {tot/BUDGET*100:.1f}%",
             f"Cloud SQL\t{won(a)}원", f"BigQuery\t{won(b)}원", f"Cloud Monitoring\t{won(c)}원", f"기타\t{won(e)}원",
             f"=합계\t{won(tot)}원"]
    if "까지" in m:
        lines.append("진행 중인 달입니다. 결제 데이터가 들어온 마지막 날까지의 값입니다.")
    return (f'<tr data-tip="{attr(chr(10).join(lines))}"><th scope="row">{m}</th><td>{won(a)}</td><td>{won(b)}</td>'
            f'<td>{won(c)}</td><td>{won(e)}</td><td class="sum">{won(tot)}</td></tr>')

month_rows = "".join(month_row(*m) for m in months)

sku = [
    ("인스턴스 시간 (db-f1-micro)", sql_parts["inst"], "고정", "DB 서버가 켜져 있는 시간만큼 붙습니다. 질의 양과 관계없이 매일 같습니다.", "사양을 올리거나 내리면 이 칸이 가장 크게 바뀝니다."),
    ("저장소 (SSD 10GB)", sql_parts["disk"], "고정", "잡아 둔 디스크 크기만큼 붙습니다. 실제로 쓴 양이 아니라 할당한 크기 기준입니다.", "디스크는 늘릴 수만 있고 줄일 수 없습니다."),
    ("백업·PITR 로그", sql_parts["backup"], "변동", "자동 백업과 시점 복구(7일)를 위한 변경 로그 보관 비용입니다.", "수집·재적재가 많은 날 로그가 늘어 오릅니다."),
    ("네트워크 나가는 트래픽", sql_parts["net"], "변동", "DB 에서 밖(Cloudflare Hyperdrive, 주간 빅쿼리 복사)으로 나간 데이터 양만큼 붙습니다.", "큰 CSV 내려받기나 전체 표 복사가 있으면 오릅니다."),
]

def sku_row(i, name, v, kind, d1, d2):
    p = v / sql_oct
    tip = [name, f"{won(v)}원 · Cloud SQL 의 {p*100:.1f}% · {kind}비", d1, d2, f"비중 = {won(v)} ÷ {won(sql_oct)} × 100"]
    demo = ' data-demo="sku"' if i == 0 else ''
    return (f'<tr><th scope="row">{name} <span class="kind {"fx" if kind == "고정" else "vr"}">{kind}</span></th><td>{won(v)}</td>'
            f'<td><div class="bar"><span style="width:{p*100:.1f}%"></span></div></td>'
            f'<td>{p*100:.1f}% <span class="info" tabindex="0"{demo} data-tip="{attr(chr(10).join(tip))}">i</span></td></tr>')

sku_rows = "".join(sku_row(i, *s) for i, s in enumerate(sku))
legend = "".join(f'<span class="lg"><i style="background:{c}"></i>{k}</span>' for k, c in COLOR.items())
legend += f'<span class="lg"><i class="dash"></i>점선: 지난 29일 변동비 중앙값 {var_med:,}원</span>'

cut_total = sum(cut)
cut_pct = cut_total / sum(req) * 100

tpl = Template(open(__file__.replace("make_mock.py", "tpl.html"), encoding="utf-8").read())
out = tpl.substitute(
    total=won(oct_total), forecast=won(forecast), avg=won(oct_total / days_oct), days=days_oct,
    ratio=f"{oct_total/BUDGET*100:.1f}", fratio=f"{forecast/BUDGET*100:.1f}",
    month_rows=month_rows, sku_rows=sku_rows, sql_oct=won(sql_oct),
    fixed_day=won(fixed_day), fixed_share=f"{fixed_day / (sum(total(r) for r in rows[:-1]) / (len(rows)-1)) * 100:.0f}",
    var_med=won(var_med), daily_svg=var_chart(), legend=legend,
    req_svg=req_svg, req_gauge=gauge(req[req_i], 100000, "건"),
    req_max=f"{req[req_i]:,}", req_day=f"{DAYS[req_i].month}/{DAYS[req_i].day}",
    hyp_svg=hyp_svg, hyp_gauge=gauge(hyp[hyp_i], 100000, "건"),
    hyp_max=f"{hyp[hyp_i]:,}", hyp_day=f"{DAYS[hyp_i].month}/{DAYS[hyp_i].day}",
    cut_svg=cut_svg, cut_total=cut_total, cut_pct=f"{cut_pct:.3f}",
    cut_max=cut[cut_i], cut_day=f"{DAYS[cut_i].month}/{DAYS[cut_i].day}",
    p99=f"{sorted(p99)[len(p99)//2]:.1f}", p99x=f"{sorted(p99)[len(p99)//2]/10:.1f}",
    colors_json=json.dumps({**MCOLOR, **COLOR}, ensure_ascii=False),
)
open(__file__.replace("make_mock.py", "report_mock.html"), "w", encoding="utf-8").write(out)
print("ok", oct_total, round(forecast), "var_med", var_med, "fixed", fixed_day)
