# -*- coding: utf-8 -*-
"""오늘(UTC) D1 읽기 사용량을 봅니다.

D1 무료 요금제는 하루 500만 행을 읽으면 다음 00:00 UTC(09:00 KST)까지
모든 질의가 막힙니다. D1 을 통째로 읽는 작업 전에 이걸 먼저 돌립니다.
Cloudflare 통계(GraphQL)만 읽으므로 D1 한도를 쓰지 않습니다.

인증은 wrangler 로그인 토큰을 씁니다(`npx wrangler login` 이 만든 것).

    py -m migration.mysql.d1_usage
    py -m migration.mysql.d1_usage --max 1500000   # 넘으면 종료 코드 2
"""
import argparse
import datetime as dt
import json
import os
import re
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path

LIMIT = 5_000_000
API = "https://api.cloudflare.com/client/v4"
QUERY = """query($acc:String!,$d:Date!){viewer{accounts(filter:{accountTag:$acc}){
  d1AnalyticsAdaptiveGroups(limit:1000, filter:{date_geq:$d, date_leq:$d}){
    sum{ rowsRead } dimensions{ databaseId } } }}}"""


def token_paths():
    paths = []
    if os.environ.get("APPDATA"):
        paths.append(Path(os.environ["APPDATA"]) / "xdg.config" / ".wrangler"
                     / "config" / "default.toml")
    paths.append(Path.home() / ".config" / ".wrangler" / "config" / "default.toml")
    paths.append(Path.home() / ".wrangler" / "config" / "default.toml")
    return paths


def read_token():
    for p in token_paths():
        if p.exists():
            m = re.search(r'oauth_token\s*=\s*"([^"]+)"', p.read_text(encoding="utf-8"))
            if m:
                return m.group(1)
    raise SystemExit("wrangler 로그인 토큰이 없습니다. `npx wrangler login` 을 먼저 하십시오.")


def refresh_login():
    """만료된 OAuth 토큰은 wrangler 명령을 한 번 돌리면 새로 받습니다. D1 은 읽지 않습니다."""
    subprocess.run(["npx", "--yes", "wrangler@4", "whoami"],
                   capture_output=True, text=True, shell=(os.name == "nt"),
                   encoding="utf-8", errors="replace")


def summarize(groups, names):
    """GraphQL 결과 행을 (합계, {DB 이름: 행 수}) 로 줄입니다."""
    per = {}
    for g in groups:
        db = g["dimensions"]["databaseId"]
        name = names.get(db, db)
        per[name] = per.get(name, 0) + g["sum"]["rowsRead"]
    return sum(per.values()), per


def _call(tok, url, body=None):
    req = urllib.request.Request(
        url, data=json.dumps(body).encode() if body else None,
        headers={"Authorization": "Bearer " + tok,
                 "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.load(r)


def fetch_accounts(read=read_token, refresh=refresh_login, call=None):
    """(토큰, 계정 목록) 을 돌려줍니다.

    토큰이 만료돼 401·403 이 오면 로그인을 한 번 새로 받고 다시 시도합니다.
    두 번째도 실패하면 그대로 예외를 올립니다.
    """
    call = call or _call
    tok = read()
    try:
        return tok, call(tok, API + "/accounts")["result"]
    except urllib.error.HTTPError as e:
        if e.code not in (401, 403):
            raise
    refresh()
    tok = read()
    return tok, call(tok, API + "/accounts")["result"]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--max", type=int, default=None,
                    help="오늘 이보다 많이 읽었으면 종료 코드 2")
    args = ap.parse_args()
    tok, accounts = fetch_accounts()
    today = dt.datetime.now(dt.timezone.utc).date().isoformat()
    total, per_all = 0, {}
    for acc in accounts:
        names = {d["uuid"]: d["name"] for d in _call(
            tok, API + "/accounts/%s/d1/database?per_page=100" % acc["id"])["result"]}
        r = _call(tok, API + "/graphql",
                  {"query": QUERY, "variables": {"acc": acc["id"], "d": today}})
        if r.get("errors"):
            raise SystemExit("통계 조회 실패: %s" % r["errors"][0].get("message"))
        groups = r["data"]["viewer"]["accounts"][0]["d1AnalyticsAdaptiveGroups"]
        t, per = summarize(groups, names)
        total += t
        per_all.update(per)
    print("%s (UTC) D1 읽기 %s행 / 한도 %s행 (%.1f%%)"
          % (today, format(total, ","), format(LIMIT, ","), total * 100 / LIMIT))
    for name, n in sorted(per_all.items(), key=lambda kv: -kv[1]):
        print("   %-22s %s" % (name, format(n, ",")))
    if args.max is not None and total > args.max:
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
