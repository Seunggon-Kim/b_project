# -*- coding: utf-8 -*-
"""팀 로고 보관 DB (team_logos) - 로고 이미지를 BLOB으로 DB에 저장.

배경:
  - 기존 로고는 dashboard_js/assets/logos/*.png 파일로만 존재(10개 프랜차이즈).
  - 퓨처스 독립/교류 팀(상무·울산·소프트뱅크)은 KBO 페이지에 엠블럼이 없어 로고 파일이 없음.
  - 로고를 DB에 보관하면 (1) 누락 팀 포함 전 팀 로고를 한 곳에서 관리하고
    (2) API가 코드만으로 로고를 서빙할 수 있다.

저장 방식:
  - 로컬 PNG 10종 -> 원본 바이트 그대로 BLOB 저장 (mime=image/png)
  - 로고 없는 팀(상무/울산/소프트뱅크) -> 팀 색상 원형 SVG 배지를 생성해 BLOB 저장 (mime=image/svg+xml)

사용:
  py -3 team_logos.py            # 테이블 생성 + 로컬PNG 적재 + 생성배지 적재
  py -3 team_logos.py --export DIR  # DB의 로고를 파일로 내보내 확인
"""
import os
import sys
import sqlite3
import datetime

from futures_schedule import DB_PATH, FUTURES_TEAMS

LOGO_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "dashboard_js", "assets", "logos",
)

# code -> display_name (팀 마스터에서)
_NAME = {t[0]: t[2] for t in FUTURES_TEAMS}

# 확장자 -> MIME
EXT_MIME = {".png": "image/png", ".svg": "image/svg+xml"}

# 로고 파일이 전혀 없는 팀의 fallback 생성 배지: code -> (라벨, 배경색, 글자색).
# 현재 전 팀이 실제 로고 파일을 가지므로 평소엔 쓰이지 않고, 신규 팀 등장 시에만 동작.
FALLBACK = {
    "SM": ("상무", "#1F5C34", "#FFFFFF"),
    "UL": ("울산", "#0B4DA2", "#FFFFFF"),
    "SO": ("소뱅", "#F6B600", "#1A1A1A"),
}


def make_svg(label, bg, fg):
    fs = 42 if len(label) <= 1 else (34 if len(label) == 2 else 26)
    svg = (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100" '
        'width="100" height="100" role="img">'
        '<circle cx="50" cy="50" r="48" fill="%s"/>'
        '<text x="50" y="51" text-anchor="middle" dominant-baseline="central" '
        'font-family="\'Apple SD Gothic Neo\',\'Malgun Gothic\',sans-serif" '
        'font-size="%d" font-weight="700" fill="%s">%s</text>'
        "</svg>" % (bg, fs, fg, label)
    )
    return svg.encode("utf-8")


def setup_db(conn):
    conn.execute("""
        CREATE TABLE IF NOT EXISTS team_logos (
            code       TEXT PRIMARY KEY,   -- 팀 코드 (HH, WO, SM, UL, SO ...)
            name       TEXT,              -- 표기명
            league     TEXT DEFAULT 'futures',
            mime       TEXT NOT NULL,      -- image/png | image/svg+xml
            source     TEXT,              -- local:<file> | generated
            image      BLOB NOT NULL,
            byte_size  INTEGER,
            updated_at TEXT
        )
    """)
    conn.commit()


def _upsert(conn, code, name, mime, source, blob):
    conn.execute("""
        INSERT INTO team_logos (code, name, league, mime, source, image, byte_size, updated_at)
        VALUES (?,?,?,?,?,?,?,?)
        ON CONFLICT(code) DO UPDATE SET
          name=excluded.name, mime=excluded.mime, source=excluded.source,
          image=excluded.image, byte_size=excluded.byte_size, updated_at=excluded.updated_at
    """, (code, name, "futures", mime, source, sqlite3.Binary(blob), len(blob),
          datetime.datetime.now(datetime.timezone.utc).isoformat()))


def load_local(conn):
    """logos 디렉토리의 실제 로고 파일(.png/.svg)을 BLOB으로 적재."""
    n = 0
    for fn in sorted(os.listdir(LOGO_DIR)):
        ext = os.path.splitext(fn)[1].lower()
        if ext not in EXT_MIME:
            continue
        code = os.path.splitext(fn)[0]
        with open(os.path.join(LOGO_DIR, fn), "rb") as f:
            blob = f.read()
        _upsert(conn, code, _NAME.get(code, code), EXT_MIME[ext], "local:" + fn, blob)
        n += 1
    conn.commit()
    return n


def load_fallback(conn):
    """로고 파일이 전혀 없는 팀에만 생성 배지를 채운다(신규 팀 안전망)."""
    have = {r[0] for r in conn.execute("SELECT code FROM team_logos")}
    n = 0
    for code in {t[0] for t in FUTURES_TEAMS} - have:
        label, bg, fg = FALLBACK.get(code, (_NAME.get(code, code)[:2], "#555555", "#FFFFFF"))
        _upsert(conn, code, _NAME.get(code, label), "image/svg+xml", "generated",
                make_svg(label, bg, fg))
        n += 1
    conn.commit()
    return n


def export(conn, out_dir):
    os.makedirs(out_dir, exist_ok=True)
    ext = {"image/png": ".png", "image/svg+xml": ".svg"}
    for code, mime, blob in conn.execute("SELECT code, mime, image FROM team_logos"):
        with open(os.path.join(out_dir, code + ext.get(mime, ".bin")), "wb") as f:
            f.write(blob)
    print("[export] %d logos -> %s" % (
        conn.execute("SELECT COUNT(*) FROM team_logos").fetchone()[0], out_dir))


def main(argv):
    conn = sqlite3.connect(DB_PATH)
    setup_db(conn)
    if argv[:1] == ["--export"]:
        export(conn, argv[1] if len(argv) > 1 else "C:/tmp/logos_export")
        conn.close()
        return
    nl = load_local(conn)
    ng = load_fallback(conn)
    print("[team_logos] real files=%d, fallback badges=%d, total=%d" % (
        nl, ng, conn.execute("SELECT COUNT(*) FROM team_logos").fetchone()[0]))
    print("%-5s %-8s %-16s %-18s %s" % ("code", "name", "mime", "source", "bytes"))
    for r in conn.execute("SELECT code,name,mime,source,byte_size FROM team_logos ORDER BY code"):
        print("%-5s %-8s %-16s %-18s %d" % (r[0], r[1], r[2], r[3], r[4]))
    conn.close()


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main(sys.argv[1:])
