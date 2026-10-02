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
import re
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

INDEX_MAX_BYTES = 3072
ROW_MAX_BYTES = 65535
_FIXED_BYTES = {"INT": 4, "INT UNSIGNED": 4, "BIGINT": 8, "BIGINT UNSIGNED": 8,
                "DOUBLE": 8, "DATE": 3, "DATETIME": 5}


def q(name):
    """MySQL 식별자로 감쌉니다."""
    if name is None:
        raise ValueError("None cannot be quoted as identifier")
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
    expr_indexes = []
    for r in con.execute('PRAGMA index_list("%s")' % table):
        name, unique, origin = r[1], bool(r[2]), r[3]
        if origin == "pk":
            continue
        icols = [x[2] for x in con.execute('PRAGMA index_info("%s")' % name)]
        if any(c is None for c in icols):
            expr_indexes.append(name)
        else:
            indexes.append({"name": name, "unique": unique, "columns": icols})
    return {"name": table, "columns": cols, "pk": pk, "fks": fks,
            "indexes": indexes, "expr_indexes": expr_indexes,
            "multi_fk": [k for k, v in groups.items() if len(v) > 1]}


def key_columns(tables):
    """기본키·외래키(양쪽)·인덱스에 쓰이는 (표, 열) 입니다."""
    keys = set()
    for t in tables.values():
        keys.update((t["name"], c) for c in t["pk"])
        for fk in t["fks"]:
            keys.add((t["name"], fk["column"]))
            if fk["ref_column"] is not None:
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


def index_bytes(mtype):
    """인덱스에 쓰이는 바이트 수입니다."""
    m = re.match(r"VARCHAR\((\d+)\)", mtype)
    if m:
        return 4 * int(m.group(1))
    if mtype in _FIXED_BYTES:
        return _FIXED_BYTES[mtype]
    return 8


def row_bytes(mtype):
    """행에 쓰이는 바이트 수입니다."""
    m = re.match(r"VARCHAR\((\d+)\)", mtype)
    if m:
        return 4 * int(m.group(1)) + 2
    if mtype in _FIXED_BYTES:
        return _FIXED_BYTES[mtype]
    if mtype in ("TEXT", "MEDIUMTEXT", "MEDIUMBLOB", "LONGBLOB"):
        return 12
    return 12


def check_widths(tables, all_mtypes):
    """인덱스·행 크기 한도를 검사합니다."""
    problems = []
    for name, t in tables.items():
        mtypes = all_mtypes[name]
        renumber = RENUMBER.get(name)
        pk = [renumber] if renumber else t["pk"]

        # 기본키 크기 확인
        if pk:
            pk_bytes = sum(index_bytes(mtypes[c]) for c in pk)
            if pk_bytes > INDEX_MAX_BYTES:
                problems.append("%s PRIMARY KEY: 인덱스 %d바이트가 한도 %d바이트를 넘습니다(%s)"
                               % (name, pk_bytes, INDEX_MAX_BYTES, ", ".join(pk)))

        # 다른 인덱스 크기 확인
        for ix in t["indexes"]:
            ix_bytes = sum(index_bytes(mtypes[c]) for c in ix["columns"])
            if ix_bytes > INDEX_MAX_BYTES:
                problems.append("%s %s: 인덱스 %d바이트가 한도 %d바이트를 넘습니다(%s)"
                               % (name, ix["name"], ix_bytes, INDEX_MAX_BYTES,
                                  ", ".join(ix["columns"])))

        # 행 크기 확인
        row_size = sum(row_bytes(mtypes[c]) for c in mtypes.keys())
        if row_size > ROW_MAX_BYTES:
            problems.append("%s: 행 %d바이트가 한도 %d바이트를 넘습니다"
                           % (name, row_size, ROW_MAX_BYTES))

    if problems:
        raise ValueError("MySQL 크기 한도를 넘는 정의가 있습니다:\n" + "\n".join(problems))


def plan_table(con, t, keys):
    """표 하나의 CREATE TABLE 과 열 종류, 보고 메모를 만듭니다."""
    name = t["name"]
    renumber = RENUMBER.get(name)
    lines, columns, notes, mtypes = [], [], [], {}
    for c in t["columns"]:
        col = c["name"]

        # 새로 매기는 열은 프로필을 만들지 않습니다.
        if col == renumber:
            kind = "int"
            mtype = "BIGINT UNSIGNED"
            lines.append("  %s BIGINT UNSIGNED NOT NULL AUTO_INCREMENT" % q(col))
            columns.append([col, kind])
            mtypes[col] = mtype
            continue

        p = tm.profile_column(con, name, col)
        kind = tm.column_kind(col, c["decl"], p)
        mtype = tm.mysql_type(kind, p, is_key=(name, col) in keys, column=col)
        mtypes[col] = mtype
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
    return {"create": create, "columns": columns, "renumber": renumber,
            "notes": notes, "mtypes": mtypes}


def post_statements(t):
    """데이터를 넣은 뒤 만들 인덱스와 외래키입니다. (인덱스 목록, 외래키 목록) 를 반환합니다."""
    name = t["name"]
    indexes, fks = [], []
    for i, ix in enumerate(t["indexes"], start=1):
        if name in RENUMBER and ix["columns"] == [RENUMBER[name]]:
            continue
        ixname = ix["name"]
        if ixname.startswith("sqlite_autoindex_"):
            ixname = "uq_%s_%d" % (name, i)
        indexes.append("CREATE %s %s ON %s (%s);" % (
            "UNIQUE INDEX" if ix["unique"] else "INDEX", q(ixname[:NAME_MAX]),
            q(name), ", ".join(q(c) for c in ix["columns"])))
    for fk in t["fks"]:
        fname = ("fk_%s_%s" % (name, fk["column"]))[:NAME_MAX]
        fks.append("ALTER TABLE %s ADD CONSTRAINT %s FOREIGN KEY (%s) "
                   "REFERENCES %s (%s);" % (q(name), q(fname), q(fk["column"]),
                                            q(fk["ref_table"]), q(fk["ref_column"])))
    return indexes, fks


def build(snapshot):
    """스냅샷 하나에서 (CREATE 목록, 후처리 목록, 열 종류, 메모) 를 만듭니다."""
    con = sqlite3.connect(Path(snapshot).resolve().as_uri() + "?mode=ro", uri=True)
    names = [r[0] for r in con.execute(
        "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
        if is_migrated(r[0])]
    tables = {n: read_table(con, n) for n in names}
    notes = []

    # 식 인덱스 메모
    for n in names:
        for expr_ix in tables[n]["expr_indexes"]:
            notes.append("%s: 식 인덱스 %s 는 옮기지 않았습니다" % (n, expr_ix))

    # 외래키 정리
    for n in names:
        kept = []
        for fk in tables[n]["fks"]:
            if fk["ref_table"] not in tables:
                notes.append("%s.%s: 참조 표 %s 를 옮기지 않아 외래키를 뺐습니다"
                             % (n, fk["column"], fk["ref_table"]))
            elif fk["ref_column"] is None:
                # 참조 열이 명시되지 않으면 부모의 기본키를 사용합니다.
                parent = tables[fk["ref_table"]]
                if len(parent["pk"]) == 1:
                    fk["ref_column"] = parent["pk"][0]
                    kept.append(fk)
                else:
                    notes.append("%s.%s: 참조 열을 알 수 없어 외래키를 뺐습니다"
                                 % (n, fk["column"]))
            else:
                kept.append(fk)
        tables[n]["fks"] = kept

    keys = key_columns(tables)
    creates, posts_ix, posts_fk, types, all_mtypes = [], [], [], {}, {}
    for n in names:
        print("   스키마: %s" % n, flush=True)
        plan = plan_table(con, tables[n], keys)
        creates.append(plan["create"])
        types[n] = {"columns": plan["columns"], "renumber": plan["renumber"]}
        all_mtypes[n] = plan["mtypes"]
        notes.extend(plan["notes"])
        ix_stmts, fk_stmts = post_statements(tables[n])
        posts_ix.extend(ix_stmts)
        posts_fk.extend(fk_stmts)

    # 크기 검사
    check_widths(tables, all_mtypes)

    # 후처리: 인덱스 전부 → 외래키 전부
    posts = posts_ix + posts_fk

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
