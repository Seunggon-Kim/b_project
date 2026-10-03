#!/usr/bin/env bash
# GitHub Actions 러너에서 Cloud SQL Auth Proxy 를 띄우고, 수집용 접속 파일을 만듭니다.
#
# GCP 인증은 앞 단계(google-github-actions/auth)가 만든 키 없는 자격(ADC)을 씁니다.
# 아래 값은 워크플로가 시크릿에서 넘깁니다. 화면에 찍지 않습니다.
#
#   CLOUDSQL_INSTANCE       프로젝트:지역:인스턴스
#   MYSQL_LOADER_PASSWORD   bstats_loader 비밀번호
#   MYSQL_SERVER_PUBKEY     서버 RSA 공개키(PEM). 프록시 경유 첫 로그인(caching_sha2)에 필요합니다
#   MIRROR_MODE             이중 적재 모드(shadow·off). 기본 shadow
set -euo pipefail

VERSION=2.26.0
# 공식 릴리스 노트의 cloud-sql-proxy.linux.amd64 체크섬입니다.
SHA256=a38fe97690a27490e60a7945a8a178186ff9464abb81fe2bc652a3f773443387

DIR="${RUNNER_TEMP:-/tmp}/bstats-mysql"
mkdir -p "$DIR"
BIN="$DIR/cloud-sql-proxy"
curl -fsSL -o "$BIN" \
  "https://storage.googleapis.com/cloud-sql-connectors/cloud-sql-proxy/v${VERSION}/cloud-sql-proxy.linux.amd64"
echo "${SHA256}  ${BIN}" | sha256sum -c -
chmod +x "$BIN"

"$BIN" --address 127.0.0.1 --port 3307 "$CLOUDSQL_INSTANCE" > "$DIR/proxy.log" 2>&1 &
PROXY_PID=$!
for _ in $(seq 1 30); do
  if (echo > /dev/tcp/127.0.0.1/3307) 2>/dev/null; then break; fi
  kill -0 "$PROXY_PID" 2>/dev/null || break
  sleep 1
done
if ! (echo > /dev/tcp/127.0.0.1/3307) 2>/dev/null; then
  echo "프록시가 30초 안에 뜨지 않았습니다."
  tail -20 "$DIR/proxy.log"
  exit 1
fi

umask 077
printf '%s' "$MYSQL_LOADER_PASSWORD" > "$DIR/password.txt"
printf '%s\n' "$MYSQL_SERVER_PUBKEY" > "$DIR/server_pub.pem"
python - "$DIR" <<'EOF'
import json, pathlib, sys
d = pathlib.Path(sys.argv[1])
(d / "mysql_ci.json").write_text(json.dumps({
    "host": "127.0.0.1", "port": 3307, "database": "bstats", "user": "bstats_loader",
    "password_file": str(d / "password.txt"), "ssl_ca": None,
    "server_public_key_file": str(d / "server_pub.pem")}), encoding="utf-8")
EOF

export BSTATS_MYSQL_SETTINGS="$DIR/mysql_ci.json"
python -m migration.mysql.conn --ping
{
  echo "BSTATS_MYSQL_SETTINGS=$DIR/mysql_ci.json"
  echo "BSTATS_MYSQL_MIRROR=${MIRROR_MODE:-shadow}"
  echo "BSTATS_MYSQL_FAIL_LOG=$DIR/failures.jsonl"
} >> "$GITHUB_ENV"
