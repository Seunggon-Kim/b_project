# -*- coding: utf-8 -*-
"""Cloud SQL(MySQL) 접속 정보를 읽어 연결을 만듭니다.

접속 정보는 저장소 밖 `~/.bstats/mysql.json` 에 둡니다. 비밀번호는 그
파일이 가리키는 별도 파일에서 읽습니다. 둘 다 커밋하지 않습니다.

서버 인증서는 Cloud SQL 서버 CA 로 검증합니다. 공인 IP 로 붙으므로
호스트 이름 검증(ssl_verify_identity)은 끕니다. 인증서의 이름은 IP 가
아니라 인스턴스 이름입니다.

    py -m migration.mysql.conn --ping
"""
import argparse
import json
import sys
from pathlib import Path

import pymysql

SETTINGS_PATH = Path.home() / ".bstats" / "mysql.json"
REQUIRED = ("host", "port", "database", "user", "password_file", "ssl_ca")


def load_settings(path=SETTINGS_PATH):
    """접속 정보를 읽습니다. 빠진 항목이 있으면 이름을 적어 ValueError."""
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    missing = [k for k in REQUIRED if k not in data]
    if missing:
        raise ValueError("mysql.json 에 없는 항목: %s" % ", ".join(missing))
    return data


def connect(settings=None, database=True):
    """TLS 연결을 엽니다. autocommit 은 꺼져 있습니다."""
    s = settings or load_settings()
    password = Path(s["password_file"]).read_text(encoding="ascii").strip()
    return pymysql.connect(
        host=s["host"], port=int(s["port"]), user=s["user"],
        password=password,
        database=s["database"] if database else None,
        charset="utf8mb4", autocommit=False,
        ssl_ca=s["ssl_ca"], ssl_verify_cert=True, ssl_verify_identity=False,
        connect_timeout=20, read_timeout=900, write_timeout=900)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ping", action="store_true", help="버전과 암호화 여부를 봅니다")
    ap.parse_args()
    con = connect()
    with con.cursor() as cur:
        cur.execute("SELECT VERSION(), DATABASE()")
        version, db = cur.fetchone()
        cur.execute("SHOW SESSION STATUS LIKE 'Ssl_cipher'")
        cipher = cur.fetchone()[1]
    con.close()
    print("MySQL %s / DB %s / 암호화 %s" % (version, db, cipher or "없음"))
    return 0 if cipher else 1


if __name__ == "__main__":
    sys.exit(main())
