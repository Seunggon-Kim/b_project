# -*- coding: utf-8 -*-
"""Cloud SQL(MySQL) 접속 정보를 읽어 연결을 만듭니다.

접속 정보는 저장소 밖 `~/.bstats/mysql.json` 에 둡니다. 환경 변수
BSTATS_MYSQL_SETTINGS 로 다른 파일(예: Auth Proxy 용 `~/.bstats/mysql_proxy.json`)을
고를 수 있습니다. 비밀번호는 그 파일이 가리키는 별도 파일에서 읽습니다. 둘 다
커밋하지 않습니다.

ssl_ca 가 null 이면 TLS 없이 붙습니다. 로컬 Cloud SQL Auth Proxy(127.0.0.1)로만
허용하며, 프록시가 Cloud SQL 까지 암호화합니다.
선택 항목 server_public_key_file(PEM 경로)은 이 프록시 경로에서만 서버 공개키로
넘깁니다(MySQL 8.4 caching_sha2_password 첫 인증에 필요합니다).

서버 인증서는 Cloud SQL 서버 CA 로 검증합니다. 공인 IP 로 붙으므로
호스트 이름 검증(ssl_verify_identity)은 끕니다. 인증서의 이름은 IP 가
아니라 인스턴스 이름입니다.

    py -m migration.mysql.conn --ping
"""
import argparse
import json
import os
import sys
from pathlib import Path

import pymysql

SETTINGS_PATH = Path(os.environ.get("BSTATS_MYSQL_SETTINGS")
                     or (Path.home() / ".bstats" / "mysql.json"))
LOCAL_HOSTS = ("127.0.0.1", "localhost")
REQUIRED = ("host", "port", "database", "user", "password_file", "ssl_ca")


def settings_path():
    """환경 변수 BSTATS_MYSQL_SETTINGS 가 있으면 그 경로, 없으면 기본 경로입니다."""
    return Path(os.environ.get("BSTATS_MYSQL_SETTINGS")
                or (Path.home() / ".bstats" / "mysql.json"))


def uses_tls(settings):
    return settings.get("ssl_ca") is not None


def load_settings(path=None):
    """접속 정보를 읽습니다. 빠진 항목이 있으면 이름을 적어 ValueError."""
    path = path or settings_path()
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    missing = [k for k in REQUIRED if k not in data]
    if missing:
        raise ValueError("mysql.json 에 없는 항목: %s" % ", ".join(missing))
    return data


def connect(settings=None, database=True):
    """연결을 엽니다. 기본은 TLS 이고, ssl_ca 가 null 이면 로컬 Auth Proxy 로만
    TLS 없이 붙습니다. autocommit 은 꺼져 있습니다."""
    s = settings or load_settings()
    if not uses_tls(s) and s["host"] not in LOCAL_HOSTS:
        raise ValueError("ssl_ca 가 없으면 로컬 Auth Proxy(127.0.0.1)로만 접속할 수 있습니다")
    password = Path(s["password_file"]).read_text(encoding="ascii").strip()
    kwargs = dict(
        host=s["host"], port=int(s["port"]), user=s["user"],
        password=password,
        database=s["database"] if database else None,
        charset="utf8mb4", autocommit=False,
        connect_timeout=20, read_timeout=900, write_timeout=900)
    if uses_tls(s):
        kwargs.update(ssl_ca=s["ssl_ca"], ssl_verify_cert=True,
                      ssl_verify_identity=False)
    elif s.get("server_public_key_file"):
        kwargs["server_public_key"] = Path(s["server_public_key_file"]).read_bytes()
    return pymysql.connect(**kwargs)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ping", action="store_true", help="버전과 암호화 여부를 봅니다")
    ap.parse_args()
    settings = load_settings()
    con = connect(settings)
    with con.cursor() as cur:
        cur.execute("SELECT VERSION(), DATABASE()")
        version, db = cur.fetchone()
        cur.execute("SHOW SESSION STATUS LIKE 'Ssl_cipher'")
        cipher = cur.fetchone()[1]
    con.close()
    if not uses_tls(settings):
        print("MySQL %s / DB %s / 암호화 Auth Proxy 경유" % (version, db))
        return 0
    print("MySQL %s / DB %s / 암호화 %s" % (version, db, cipher or "없음"))
    return 0 if cipher else 1


if __name__ == "__main__":
    sys.exit(main())
