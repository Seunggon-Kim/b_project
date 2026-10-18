# -*- coding: utf-8 -*-
"""bstats 비공개 비용 보고서를 만듭니다(evan PC 에서 손으로 실행).

    py -m scripts.ops.cost_report --month 2026-10

- GCP: 결제 빅쿼리 내보내기(표준 사용 비용). 표 이름은 ~/.bstats/billing_export_table.txt.
  인증은 개인 gcloud 설정(bstats)의 액세스 토큰입니다. application-default login 은 쓰지 않습니다.
- Cloudflare: GraphQL 분석 API. 토큰·계정 ID 는 ~/.bstats/cf_analytics_token.txt·cf_account_id.txt.
- 출력: 바탕화면/bstats_비용보고/<날짜>/report.html·report.png·fonts/

비밀값은 코드와 출력에 넣지 않습니다. 부분마다 따로 실패합니다(그 칸만 안내 글).
첫 실제 실행 때 눈으로 볼 것: Cloudflare CPU 중앙값이 몇 ms(운영 4~25ms)인지,
`date` 차원이 없으면 `datetime` 으로 바꿉니다.
설계: docs/superpowers/specs/2026-10-18-data-ops-tab-design.md §6
"""
import argparse
import datetime as dt
import json
import shutil
import subprocess
import sys
import tempfile
import urllib.request
from pathlib import Path

from scripts.ops import cost_billing, cost_cloudflare, cost_render

ROOT = Path(__file__).resolve().parents[2]
SECRET_DIR = Path.home() / ".bstats"
FONT_SRC = ROOT / "dashboard_js" / "assets" / "fonts"
MAX_BYTES = 50 * 1024 * 1024
CF_URL = "https://api.cloudflare.com/client/v4/graphql"
EDGE = Path("C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe")
KST = dt.timezone(dt.timedelta(hours=9))


def read_secret(name):
    p = SECRET_DIR / name
    if not p.is_file():
        return None
    v = p.read_text(encoding="utf-8").strip()
    return v or None


def out_dir(base, today):
    return Path(base) / "bstats_비용보고" / today.isoformat()


def gcloud_token():
    exe = shutil.which("gcloud") or shutil.which("gcloud.cmd")
    if not exe:
        raise RuntimeError("gcloud 를 찾지 못했습니다")
    r = subprocess.run([exe, "--configuration=bstats", "auth", "print-access-token"],
                       capture_output=True, text=True, timeout=60)
    if r.returncode != 0 or not r.stdout.strip():
        raise RuntimeError("gcloud 토큰을 받지 못했습니다(bstats 설정 로그인 확인)")
    return r.stdout.strip()


def bq_client():
    from google.cloud import bigquery
    from google.oauth2.credentials import Credentials
    return bigquery.Client(project="bstats-kbo", credentials=Credentials(gcloud_token()))


def bq_rows(client, table, start):
    """시험 실행으로 읽을 바이트를 보고 MAX_BYTES 안이면 질의합니다."""
    from google.cloud import bigquery
    params = [bigquery.ScalarQueryParameter("start", "DATE", start)]
    sql = cost_billing.billing_sql(table)
    dry = client.query(sql, job_config=bigquery.QueryJobConfig(
        dry_run=True, use_query_cache=False, query_parameters=params))
    if dry.total_bytes_processed > MAX_BYTES:
        raise RuntimeError("읽을 데이터가 %.1fMB 로 한도 %dMB 를 넘어 멈췄습니다"
                           % (dry.total_bytes_processed / 1e6, MAX_BYTES // (1024 * 1024)))
    job = client.query(sql, job_config=bigquery.QueryJobConfig(query_parameters=params))
    out = []
    for r in job.result():
        d = dict(r)
        if "net" in d:
            d["net"] = float(d["net"] or 0)
        out.append(d)
    return out


def cf_fetch(token, acct, days):
    body = json.dumps({"query": cost_cloudflare.graphql_query(),
                       "variables": {"acct": acct, "start": days[0].isoformat(),
                                     "end": days[-1].isoformat()}}).encode("utf-8")
    req = urllib.request.Request(CF_URL, data=body, method="POST", headers={
        "Authorization": "Bearer " + token, "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=60) as res:
        return json.loads(res.read().decode("utf-8"))


def make_billing(month, today, budget):
    table = read_secret("billing_export_table.txt")
    if not table:
        return None, "결제 내보내기 표 이름이 없습니다(~/.bstats/billing_export_table.txt)"
    first = dt.date(int(month[:4]), int(month[5:7]), 1)
    start = min(first, today - dt.timedelta(days=29))
    start = dt.date(start.year - (start.month <= 3), (start.month - 4) % 12 + 1, 1)  # 세 달 전 1일
    try:
        rows = bq_rows(bq_client(), table, start)
    except Exception as e:  # noqa: BLE001  칸 하나만 안내로 바꿉니다
        return None, "결제 데이터를 읽지 못했습니다: %s" % str(e)[:200]
    if not rows:
        return None, "결제 내보내기 데이터가 아직 없습니다. 켠 뒤 몇 시간에서 하루가 걸립니다"
    return cost_billing.summarize(rows, month, today, budget), ""


def make_cf(utc_today):
    token, acct = read_secret("cf_analytics_token.txt"), read_secret("cf_account_id.txt")
    if not token or not acct:
        return None, "토큰 없음: ~/.bstats/cf_analytics_token.txt·cf_account_id.txt 를 만드십시오", 0
    days = [utc_today - dt.timedelta(days=i) for i in range(29, -1, -1)]
    try:
        return cost_cloudflare.summarize(cf_fetch(token, acct, days), days), "", 0
    except cost_cloudflare.SchemaMismatch as e:
        return None, "Cloudflare 응답 모양이 예상과 다릅니다: %s" % str(e)[:200], 1
    except Exception as e:  # noqa: BLE001
        return None, "Cloudflare 를 읽지 못했습니다: %s" % str(e)[:200], 1


def screenshot(html_path, png_path):
    if not EDGE.exists():
        print("경고: Edge 가 없어 PNG 를 만들지 않았습니다")
        return
    work = Path(tempfile.mkdtemp(prefix="bstats_cost_"))
    try:
        src = work / "report.html"
        shutil.copy(html_path, src)
        shutil.copytree(Path(html_path).parent / "fonts", work / "fonts")
        shot = work / "report.png"
        subprocess.run([str(EDGE), "--headless=new", "--no-sandbox", "--disable-gpu", "--hide-scrollbars",
                        "--force-device-scale-factor=1", "--virtual-time-budget=7000",
                        "--window-size=1200,1900", "--user-data-dir=%s" % (work / "ud").as_posix(),
                        "--screenshot=%s" % shot, src.as_uri()],
                       capture_output=True, timeout=120)
        if shot.exists():
            shutil.copy(shot, png_path)
        else:
            print("경고: PNG 를 만들지 못했습니다")
    finally:
        shutil.rmtree(work, ignore_errors=True)


def main(argv=None):
    ap = argparse.ArgumentParser(description="bstats 비공개 비용 보고서")
    ap.add_argument("--month", required=True, help="YYYY-MM")
    ap.add_argument("--budget", type=int, default=30000)
    ap.add_argument("--out", default=None, help="출력 폴더(기본: 바탕화면/bstats_비용보고/<오늘>)")
    ap.add_argument("--no-png", action="store_true")
    ap.add_argument("--today", default=None, help="시험용 KST 오늘(YYYY-MM-DD)")
    args = ap.parse_args(argv)

    now = dt.datetime.now(KST)
    today = dt.date.fromisoformat(args.today) if args.today else now.date()
    utc_today = dt.datetime.now(dt.timezone.utc).date() if not args.today else today
    out = Path(args.out) if args.out else out_dir(Path.home() / "Desktop", today)
    out.mkdir(parents=True, exist_ok=True)

    billing, bnote = make_billing(args.month, today, args.budget)
    cf, cnote, code = make_cf(utc_today)
    html = cost_render.render(billing, cf, {"made_at": now.strftime("%Y-%m-%d %H:%M KST"),
                                            "billing_note": bnote, "cf_note": cnote})
    (out / "report.html").write_text(html, encoding="utf-8")
    (out / "fonts").mkdir(exist_ok=True)
    for f in FONT_SRC.glob("KBO-Dia-Gothic_*.woff"):
        shutil.copy(f, out / "fonts" / f.name)
    if not args.no_png:
        screenshot(out / "report.html", out / "report.png")
    print("비용 보고서: %s" % out)
    return code


if __name__ == "__main__":
    sys.exit(main())
