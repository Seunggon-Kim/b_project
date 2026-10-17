# 공개 '데이터 관리' 페이지 미리보기 목업.
# 표 이름·행 수·분류·수집 상태·출처 = 실제 값(/db/tables, /jobs/status, 계보 파일)
# MySQL 용량·빅쿼리 값·이력 날짜 일부 = 예시 값
import html, json, datetime as dt
from pathlib import Path

M = Path(__file__).parent
tables = json.loads((M / "tables.json").read_text(encoding="utf-8"))["tables"]
jobs = json.loads((M / "jobs.json").read_text(encoding="utf-8"))["details"]
lin = json.loads((M / "lineage.json").read_text(encoding="utf-8"))
NOW = dt.datetime(2026, 10, 18, 1, 0)


def a(s):
    return html.escape(str(s), quote=True)


def size(b):
    if b >= 1e9:
        return f"{b/1e9:.2f} GB"
    if b >= 1e6:
        return f"{b/1e6:.1f} MB"
    return f"{b/1e3:.0f} KB"


def tipattr(*lines):
    return f' tabindex="0" data-tip="{a(chr(10).join(lines))}"'


def info(*lines):
    return f'<span class="info"{tipattr(*lines)}>i</span>'


# ---- 저장소: 예시 용량 ----
ROWB = {"play_by_play": 470, "games": 300, "kbo_official_batter_stats": 520, "kbo_official_pitcher_stats": 560,
        "futures_season_stats": 420, "pitch_run_value": 260, "pitch_run_value_zone": 240}
GROW = {"play_by_play": 1184, "games": 4, "pitch_run_value": 36, "pitch_run_value_zone": 18,
        "batter_run_value": 0, "kbo_official_batter_stats": 0}
rows = []
for t in tables:
    n = t["rows"] or 0
    rb = ROWB.get(t["name"], 180)
    data = max(16384, int(n * rb))
    idx = max(0, int(data * (0.32 if n > 50000 else 0.12)))
    bq_rows = n - GROW.get(t["name"], 0)
    bq_bytes = int(bq_rows * rb * 0.82)
    rows.append(dict(name=t["name"], cat=t["category"] or "-", rows=n, data=data, idx=idx,
                     bq_rows=bq_rows, bq_bytes=max(bq_bytes, 2048), status="ok"))
rows.sort(key=lambda r: -(r["data"] + r["idx"]))
tot_rows = sum(r["rows"] for r in rows)
tot_my = sum(r["data"] + r["idx"] for r in rows)
tot_bq = sum(r["bq_bytes"] for r in rows)
max_b = max(r["data"] + r["idx"] for r in rows)
BQ_LAST = jobs["bq_copy"]["last_run_at"]


def cmp_cell(r):
    d = r["rows"] - r["bq_rows"]
    if r["status"] == "fail":
        return '<span class="chip bad">복사 실패</span>'
    if d == 0:
        return '<span class="chip same">같음</span>'
    return f'<span class="chip diff">차이 {d:+,}행</span>'


trs = []
for i, r in enumerate(rows):
    my = r["data"] + r["idx"]
    tip = tipattr(
        r["name"],
        f"{r['cat']} · MySQL {r['rows']:,}행 · 빅쿼리 {r['bq_rows']:,}행",
        f"MySQL 용량 {size(my)} = 데이터 {size(r['data'])} + 인덱스 {size(r['idx'])}",
        f"빅쿼리 용량 {size(r['bq_bytes'])} · 마지막 복사 {BQ_LAST}",
        "차이 = MySQL 행 수 − 빅쿼리 행 수. 빅쿼리는 주 1회 사본이라 그 사이 들어온 행만큼 차이가 납니다.",
    )
    trs.append(
        f'<tr{tip}{" class=\"fold\"" if i >= 10 else ""}><th scope="row"><code>{r["name"]}</code></th><td class="cat">{a(r["cat"])}</td>'
        f'<td>{r["rows"]:,}</td>'
        f'<td class="szc"><span class="sz">{size(my)}</span><span class="szbar"><span style="width:{max(my/max_b*100, 0.6):.1f}%"></span></span></td>'
        f'<td>{r["bq_rows"]:,}</td><td>{size(r["bq_bytes"])}</td><td>{cmp_cell(r)}</td></tr>')
same_n = sum(1 for r in rows if r["rows"] == r["bq_rows"])

# ---- 수집 작업 ----
STATE = {"ok": ("정상", "ok"), "stale": ("오래됨", "warn"), "fail": ("실패", "bad"), "none": ("기록 없음", "none"),
         "stopped": ("멈춤", "stop")}
job_cards = []
cnt = {k: 0 for k in STATE}
for j in lin["jobs"]:
    keys = []
    for s in j["steps"]:
        if s["status_key"] and s["status_key"] not in [k for k, _ in keys]:
            keys.append((s["status_key"], s["name"]))
    lis = []
    for k, step in keys:
        d = jobs.get(k)
        if j.get("stopped"):
            st = "stopped"
        elif not d:
            st = "none"
        elif d["status"] != "ok":
            st = "fail"
        else:
            age = (NOW - dt.datetime.strptime(d["last_run_at"], "%Y-%m-%d %H:%M")).total_seconds() / 3600
            st = "stale" if age > j["stale_hours"] else "ok"
        cnt[st] += 1
        label, cls = STATE[st]
        when = d["last_run_at"] if d else "-"
        note = (d or {}).get("note") or ""
        t = tipattr(f"{step} · {k}", f"{label} · 마지막 실행 {when}",
                    *( [f"메모: {note}"] if note else [] ),
                    f"오래됨 기준: 마지막 실행 뒤 {j['stale_hours']}시간이 지나면 오래됨으로 봅니다." if not j.get("stopped")
                    else "KBO 이용약관(2026-10-14 시행)에 따라 이 작업의 예약 실행을 멈췄습니다.")
        lis.append(f'<li{t}><span class="dot {cls}"></span><span class="sn">{a(step)}</span><span class="sw">{when[5:] if d else "-"}</span></li>')
    head = f'{a(j["schedule_kst"])}'
    badge = '<span class="chip stop">예약 멈춤</span>' if j.get("stopped") else ''
    job_cards.append(f'<div class="job{" stopped" if j.get("stopped") else ""}"><div class="jh"><b>{j["id"]}</b>{badge}<span class="js">{head}</span></div><ul>{"".join(lis)}</ul></div>')
run_total = sum(v for k, v in cnt.items() if k != "stopped")

# ---- 출처 ----
use = {}
for sc in lin["scripts"]:
    for s in sc.get("sources", []):
        use.setdefault(s, []).append(sc)
src_cards = []
n_on = n_off = 0
for s in lin["sources"]:
    scs = use.get(s["id"], [])
    stopped = bool(scs) and all(sc.get("stopped") for sc in scs)
    n_off += stopped
    n_on += not stopped
    host = "네이버 스포츠" if "naver" in s["url"] else "KBO 공식 사이트"
    st = '<span class="chip stop">수집 중단</span>' if stopped else '<span class="chip ok">사용 중</span>'
    used = ", ".join(sorted({Path(sc["path"]).name for sc in scs})) or "API 가 그때그때 읽음"
    t = tipattr(s["name"], f"{'수집 중단' if stopped else '사용 중'} · {host}",
                f"이 출처를 쓰는 수집 스크립트: {used}",
                "상태 규칙: 이 출처를 쓰는 수집 스크립트가 모두 멈췄으면 '수집 중단'입니다(계보 파일 기준).")
    src_cards.append(f'<div class="src{" off" if stopped else ""}"{t}><div class="sh"><b>{a(s["name"])}</b>{st}</div>'
                     f'<div class="sm">{host} · 스크립트 {len(scs)}개</div></div>')

# ---- 이력 (source_history.json 예시) ----
HIST = [
    ("2026-10-18", "대체", "팀 순위", "팀 순위(/standings)를 KBO 기록실 대신 네이버 스포츠에서 읽도록 바꿨습니다.", "KBO 이용약관 제14조"),
    ("2026-10-18", "중단", "퓨처스·1군 등록 명단 화면", "네이버에 같은 자료가 없어 화면을 내렸습니다. 대체하지 않습니다.", "KBO 이용약관 제14조"),
    ("2026-10-17", "중단", "KBO 공식 사이트 수집 전부", "공식 기록·팀 순위·퓨처스·등록 명단·새 선수 단계와 roster·monthly 예약 실행을 멈췄습니다.", "KBO 이용약관 제14조(자동 수집·재배포 금지)"),
    ("2026-10-14", "알림", "KBO 이용약관 개정 시행", "크롤러·스크래퍼 등 자동 수집과 재배포·2차 가공을 금지하는 조항이 시행됐습니다.", "2026-09-15 공고"),
]
KIND = {"중단": "bad", "대체": "ok", "재개": "ok", "알림": "none"}
hist = "".join(
    f'<li><span class="hd">{d}</span><span class="chip {KIND[k]}">{k}</span><div class="hb"><b>{a(w)}</b><p>{a(x)}</p><p class="why">이유: {a(y)}</p></div></li>'
    for d, k, w, x, y in HIST)

page = (M / "tpl_ops.html").read_text(encoding="utf-8")
for k, v in {
    "%TRS%": "".join(trs), "%TOT_ROWS%": f"{tot_rows:,}", "%TOT_MY%": size(tot_my), "%TOT_BQ%": size(tot_bq),
    "%NT%": str(len(rows)), "%REST%": str(len(rows) - 10), "%SAME%": str(same_n), "%BQ_LAST%": BQ_LAST, "%JOBS%": "".join(job_cards),
    "%OK%": str(cnt["ok"]), "%RUN%": str(run_total), "%STOP%": str(cnt["stopped"]),
    "%WARN%": str(cnt["stale"] + cnt["fail"] + cnt["none"]),
    "%SRC%": "".join(src_cards), "%ON%": str(n_on), "%OFF%": str(n_off), "%HIST%": hist,
}.items():
    page = page.replace(k, v)
(M / "pages" / "data-ops.html").write_text(page, encoding="utf-8")
print("ok", len(rows), cnt, n_on, n_off)
