# -*- coding: utf-8 -*-
"""SQLite 스냅샷을 보고 MySQL 스키마를 만듭니다.

    py -m migration.mysql.ddl --snapshot ~/.bstats/snapshots/d1_20261002.db

만드는 파일(사람이 검토하고 커밋합니다):
    migration/mysql/schema.sql         표 만들기(기본키만)
    migration/mysql/schema_post.sql    인덱스·외래키(데이터를 넣은 뒤 적용)
    migration/mysql/schema_types.json  열마다 값 종류(적재·검증이 씁니다)
    docs/mysql-migration/schema-report.md  고른 타입과 값 처리 메모

인덱스와 외래키를 따로 두는 이유: 400만 행을 넣을 때 인덱스가 있으면
줄마다 인덱스를 고칩니다. 다 넣고 한 번에 만드는 편이 빠릅니다.
"""
import argparse
import json
import sqlite3
import sys
from pathlib import Path

from migration.mysql import typemap as tm
from migration.mysql.tables import is_migrated

ROOT = Path(__file__).resolve().parents[2]
OUT_DIR = ROOT / "migration" / "mysql"
REPORT = ROOT / "docs" / "mysql-migration" / "schema-report.md"

# 새로 번호를 매기는 표입니다. 샤드마다 따로 붙인 pbp_id 가 겹칠 수
# 있습니다. 시즌 순 → 샤드 안 원래 번호 순으로 넣어 경기 안 순서를 지킵니다.
RENUMBER = {"play_by_play": "pbp_id"}
NAME_MAX = 64
NOW_DEFAULTS = {"CURRENT_TIMESTAMP", "(CURRENT_TIMESTAMP)",
                "DATETIME('NOW')", "(DATETIME('NOW'))"}


def q(name):
    """MySQL 식별자로 감쌉니다."""
    return "`%s`" % name.replace("`", "``")


def split_sql(text):
    """이 생성기가 만든 파일을 문장으로 나눕니다(문자열 안 ';\\n' 은 없다고 봅니다)."""
    return [s.strip().rstrip(";").strip() for s in text.split(";\n") if s.strip()]


def read_table(con, table):
    """표 하나의 열·기본키·외래키·인덱스를 PRAGMA 로 읽습니다."""
    cols = [{"name": r[1], "decl": r[2] or "", "notnull": bool(r[3]),
             "default": r[4], "pk": r[5]}
            for r in con.execute('PRAGMA table_info("%s")' % table)]
    pk = [c["name"] for c in sorted((c for c in cols if c["pk"]),
                                    key=lambda c: c["pk"])]
    groups = {}
    for r in con.execute('PRAGMA foreign_key_list("%s")' % table):
        groups.setdefault(r[0], []).append(r)
    fks = []
    for rows in groups.values():
        if len(rows) == 1:
            fks.append({"column": rows[0][3], "ref_table": rows[0][2],
                        "ref_column": rows[0][4]})
    indexes = []
    for r in con.execute('PRAGMA index_list("%s")' % table):
        name, unique, origin = r[1], bool(r[2]), r[3]
        if origin == "pk":
            continue
        icols = [x[2] for x in con.execute('PRAGMA index_info("%s")' % name)]
        indexes.append({"name": name, "unique": unique, "columns": icols})
    return {"name": table, "columns": cols, "pk": pk, "fks": fks,
            "indexes": indexes, "multi_fk": [k for k, v in groups.items() if len(v) > 1]}


def key_columns(tables):
    """기본키·외래키(양쪽)·인덱스에 쓰이는 (표, 열) 입니다."""
    keys = set()
    for t in tables.values():
        keys.update((t["name"], c) for c in t["pk"])
        for fk in t["fks"]:
            keys.add((t["name"], fk["column"]))
            keys.add((fk["ref_table"], fk["ref_column"]))
        for ix in t["indexes"]:
            keys.update((t["name"], c) for c in ix["columns"])
    return keys


def default_clause(default, kind, mtype):
    """SQLite 기본값을 MySQL 로 옮깁니다. (절, 뺀 이유 또는 None)."""
    if default is None:
        return "", None
    d = default.strip()
    u = d.upper().replace(" ", "")
    if u in NOW_DEFAULTS:
        if kind == "datetime":
            return " DEFAULT CURRENT_TIMESTAMP", None
        return "", "현재 시각 기본값은 DATETIME 열에만 둘 수 있어 뺐습니다"
    if u == "NULL":
        return " DEFAULT NULL", None
    if kind in ("int", "double") and tm.NUM_LIKE.match(d):
        return " DEFAULT %s" % d, None
    if len(d) >= 2 and d[0] == d[-1] == "'":
        if kind in ("int", "double", "blob"):
            return "", "글자 기본값 %s 가 이 열에 맞지 않아 뺐습니다" % d
        return (" DEFAULT (%s)" if "TEXT" in mtype else " DEFAULT %s") % d, None
    return "", "알 수 없는 기본값 %s 를 뺐습니다" % d


def _category(decl):
    d = (decl or "").upper()
    if "INT" in d:
        return "int"
    if any(k in d for k in ("REAL", "FLOA", "DOUB", "NUMERIC", "DECIMAL")):
        return "double"
    if "BLOB" in d:
        return "blob"
    if "DATE" in d or "TIME" in d:
        return "date"
    return "text" if d else None


def _type_changed(decl, kind):
    cat = _category(decl)
    if cat is None:
        return True
    if cat == "date":
        return kind not in ("date", "datetime")
    return cat != kind


def plan_table(con, t, keys):
    """표 하나의 CREATE TABLE 과 열 종류, 보고 메모를 만듭니다."""
    name = t["name"]
    renumber = RENUMBER.get(name)
    lines, columns, notes = [], [], []
    for c in t["columns"]:
        col = c["name"]
        p = tm.profile_column(con, name, col)
        if col == renumber:
            kind = "int"
            lines.append("  %s BIGINT UNSIGNED NOT NULL AUTO_INCREMENT" % q(col))
            columns.append([col, kind])
            continue
        kind = tm.column_kind(col, c["decl"], p)
        mtype = tm.mysql_type(kind, p, is_key=(name, col) in keys, column=col)
        notnull = c["notnull"] or col in t["pk"]
        dflt, why = default_clause(c["default"], kind, mtype)
        if why:
            notes.append("%s.%s: %s" % (name, col, why))
        auto = ""
        if t["pk"] == [col] and c["decl"].upper() == "INTEGER":
            auto = " AUTO_INCREMENT"   # SQLite rowid 처럼 번호를 이어 붙입니다
        lines.append("  %s %s%s%s%s" % (q(col), mtype,
                                        " NOT NULL" if notnull else "", dflt, auto))
        columns.append([col, kind])
        if _type_changed(c["decl"], kind):
            notes.append("%s.%s: 선언 %s → %s" % (name, col, c["decl"] or "(없음)", mtype))
        if kind == "int" and p["dotzero"]:
            notes.append("%s.%s: 소수점 표기 %s개 → 정수"
                         % (name, col, format(p["dotzero"], ",")))
        if kind not in ("text", "blob") and p["empties"]:
            notes.append("%s.%s: 빈 값 %s개 → NULL"
                         % (name, col, format(p["empties"], ",")))
    pk = [renumber] if renumber else t["pk"]
    if pk:
        lines.append("  PRIMARY KEY (%s)" % ", ".join(q(c) for c in pk))
    else:
        notes.append("%s: 기본키가 없습니다(원본과 같음)" % name)
    for fid in t["multi_fk"]:
        notes.append("%s: 여러 열 외래키(%s)는 옮기지 않았습니다" % (name, fid))
    create = ("CREATE TABLE %s (\n%s\n) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 "
              "COLLATE=utf8mb4_0900_ai_ci;" % (q(name), ",\n".join(lines)))
    return {"create": create, "columns": columns, "renumber": renumber, "notes": notes}


def post_statements(t):
    """데이터를 넣은 뒤 만들 인덱스와 외래키입니다."""
    name = t["name"]
    out = []
    for i, ix in enumerate(t["indexes"], start=1):
        if name in RENUMBER and ix["columns"] == [RENUMBER[name]]:
            continue
        ixname = ix["name"]
        if ixname.startswith("sqlite_autoindex_"):
            ixname = "uq_%s_%d" % (name, i)
        out.append("CREATE %s %s ON %s (%s);" % (
            "UNIQUE INDEX" if ix["unique"] else "INDEX", q(ixname[:NAME_MAX]),
            q(name), ", ".join(q(c) for c in ix["columns"])))
    for fk in t["fks"]:
        fname = ("fk_%s_%s" % (name, fk["column"]))[:NAME_MAX]
        out.append("ALTER TABLE %s ADD CONSTRAINT %s FOREIGN KEY (%s) "
                   "REFERENCES %s (%s);" % (q(name), q(fname), q(fk["column"]),
                                            q(fk["ref_table"]), q(fk["ref_column"])))
    return out


def build(snapshot):
    """스냅샷 하나에서 (CREATE 목록, 후처리 목록, 열 종류, 메모) 를 만듭니다."""
    con = sqlite3.connect(Path(snapshot).resolve().as_uri() + "?mode=ro", uri=True)
    names = [r[0] for r in con.execute(
        "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
        if is_migrated(r[0])]
    tables = {n: read_table(con, n) for n in names}
    notes = []
    for n in names:
        kept = []
        for fk in tables[n]["fks"]:
            if fk["ref_table"] in tables:
                kept.append(fk)
            else:
                notes.append("%s.%s: 참조 표 %s 를 옮기지 않아 외래키를 뺐습니다"
                             % (n, fk["column"], fk["ref_table"]))
        tables[n]["fks"] = kept
    keys = key_columns(tables)
    creates, posts, types = [], [], {}
    for n in names:
        print("   스키마: %s" % n, flush=True)
        plan = plan_table(con, tables[n], keys)
        creates.append(plan["create"])
        types[n] = {"columns": plan["columns"], "renumber": plan["renumber"]}
        notes.extend(plan["notes"])
        posts.extend(post_statements(tables[n]))
    con.close()
    return creates, posts, types, notes


def render_report(snapshot, types, notes):
    lines = ["# MySQL 스키마 보고", "",
             "스냅샷: `%s`" % Path(snapshot).name, "",
             "| 표 | 열 수 | 새 번호 |", "|---|---|---|"]
    for n, spec in types.items():
        lines.append("| %s | %d | %s |" % (n, len(spec["columns"]),
                                           spec["renumber"] or ""))
    lines += ["", "## 타입·값 처리 메모", ""] + ["- " + x for x in notes] + [""]
    return "\n".join(lines)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--snapshot", required=True)
    args = ap.parse_args()
    creates, posts, types, notes = build(args.snapshot)
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUT_DIR / "schema.sql").write_text(
        "\n\n".join(creates) + "\n", encoding="utf-8", newline="\n")
    (OUT_DIR / "schema_post.sql").write_text(
        "\n".join(posts) + "\n", encoding="utf-8", newline="\n")
    (OUT_DIR / "schema_types.json").write_text(
        json.dumps(types, ensure_ascii=False, indent=1) + "\n",
        encoding="utf-8", newline="\n")
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(render_report(args.snapshot, types, notes),
                      encoding="utf-8", newline="\n")
    print("표 %d개, 후처리 %d문, 메모 %d줄" % (len(creates), len(posts), len(notes)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
