# -*- coding: utf-8 -*-
"""테이블 계보의 재료를 코드에서 뽑습니다.

설계: docs/superpowers/specs/2026-10-04-table-lineage-design.md

뽑기 쉬운 것만 여기서 뽑습니다. 수집 스크립트가 어떤 표에 쓰는지는 SQL 을
조립해 만드는 곳이 많아 기계로 뽑으면 틀리기 쉽습니다. 그건 손 파일
(database/lineage_writes.json)에 적고, 테스트가 실제 코드와 맞는지 봅니다.
"""
import re

DOW = ["일", "월", "화", "수", "목", "금", "토"]

CRON = re.compile(r"""cron:\s*(['"])(.+?)\1""")
# YAML 목록 항목 줄(`- name:`, `- run:`, `- id:` …)마다 단계가 바뀝니다.
ITEM = re.compile(r"^\s*-\s+")
NAME = re.compile(r"^(\s*)(-\s+)?name:\s*(.+?)\s*$")
# 해석기를 어떻게 부르든(python -u, python3.12, python -X utf8, 줄 이음 `\`)
# 줄에 있는 `<경로>.py`·`-m <모듈>`·`bash <경로>.sh` 를 모두 잡습니다.
PY_FILE = re.compile(r"(?<![\w./-])([A-Za-z0-9_./-]+\.py)(?![\w.-])")
PY_MOD = re.compile(r"(?<!\S)-m\s+([A-Za-z_][\w.]*)")
SH_FILE = re.compile(r"\b(?:ba)?sh\s+([A-Za-z0-9_./-]+\.sh)(?![\w.-])")
TRAILING_COMMENT = re.compile(r"(?:^|\s)#.*$")
JOB_KEY = re.compile(r"record_job_run\.py\s+--job\s+([a-z_]+)")
TABLE = re.compile(r"CREATE TABLE `([A-Za-z0-9_]+)`")


def cron_to_kst(cron):
    """UTC cron 다섯 칸을 한국 시각 문구로 바꿉니다. 모르는 꼴이면 원문 그대로입니다.

    한국은 UTC+9 이고 서머타임이 없습니다. 9시간을 더해 날을 넘기면 요일·날짜도
    하루 밉니다(weekly 의 월 20:47 UTC 는 한국 화 05:47).
    """
    parts = cron.split()
    if len(parts) != 5:
        return cron
    mi, hr, dom, mon, dow = parts
    if not (mi.isdigit() and hr.isdigit()) or mon != "*":
        return cron
    h = int(hr) + 9
    next_day = h >= 24
    hm = "%02d:%02d" % (h % 24, int(mi))
    if dom == "*" and dow == "*":
        return "매일 " + hm
    if dom == "*" and dow.isdigit():
        return "매주 %s %s" % (DOW[(int(dow) + (1 if next_day else 0)) % 7], hm)
    if dow == "*" and dom.isdigit():
        if next_day and int(dom) >= 28:
            # 다음 날이 그달에 없을 수 있습니다(31일 → "32일"). 원문을 둡니다.
            return cron
        return "매월 %d일 %s" % (int(dom) + (1 if next_day else 0), hm)
    return cron


def parse_workflow(text):
    """워크플로 YAML 글자에서 실행 시각과 (단계 이름, 스크립트) 목록을 뽑습니다.

    주석이 아닌 줄의 `<경로>.py`, `-m <모듈>`(모듈은 경로로 바꿈, `pip` 은 뺌),
    `bash <경로>.sh` 를 모두 스크립트로 봅니다. 해석기를 어떻게 부르든
    (`python -u`, `python3.12`, `python -X utf8`, `python \\` 다음 줄의 경로)
    빠지지 않게 하려는 것입니다. 단계 이름은 목록 항목 줄(`- …`)마다 비우고
    그 항목의 `name:` 으로 채웁니다. 이름 없는 단계가 앞 단계의 이름을
    물려받지 않습니다. 같은 (단계, 스크립트)는 한 번만 넣습니다.
    """
    m = CRON.search(text)
    steps, seen, name, key_indent = [], set(), None, None
    for line in text.splitlines():
        if line.lstrip().startswith("#"):
            continue
        line = TRAILING_COMMENT.sub("", line)
        item = ITEM.match(line)
        if item:
            name, key_indent = None, item.end()
        n = NAME.match(line)
        # `- name:` 이거나 그 항목의 키 자리에 있는 `name:` 만 단계 이름입니다
        # (`with:` 아래 `name:` 같은 더 깊은 키는 아님).
        if n and (n.group(2) or len(n.group(1)) == key_indent):
            name = n.group(3).strip().strip("'\"")
            continue
        found = [(f.start(), f.group(1)) for f in PY_FILE.finditer(line)]
        found += [(f.start(), f.group(1).replace(".", "/") + ".py")
                  for f in PY_MOD.finditer(line) if f.group(1) != "pip"]
        found += [(f.start(), f.group(1)) for f in SH_FILE.finditer(line)]
        for _, script in sorted(found):
            while script.startswith("./"):
                script = script[2:]
            if (name, script) not in seen:
                seen.add((name, script))
                steps.append({"name": name, "script": script})
    return {"cron_utc": m.group(2) if m else None, "steps": steps}


def job_keys(text):
    """워크플로가 `record_job_run.py --job <키>` 로 남기는 실행 기록 키입니다."""
    return set(JOB_KEY.findall(text))


def schema_tables(schema_sql):
    """MySQL 스키마(migration/mysql/schema.sql)의 표 이름입니다."""
    return set(TABLE.findall(schema_sql))


IMPORT = re.compile(r"import\s*\{([^}]*)\}\s*from\s*'\./routes/([\w-]+)\.js'", re.S)
ADD = re.compile(r"router\.add\(\s*'GET'\s*,\s*'([^']+)'\s*,\s*([A-Za-z_]\w*)?")
SQL_TABLE = re.compile(r"\b(?:FROM|JOIN)\s+[`\"\\]*([A-Za-z_]\w*)")
TEMPLATE = re.compile(r"\$\{[A-Za-z_][\w.]*\}(/[^`?'\"\s]*)")
API_CALL = re.compile(r"\bAPI\.([A-Za-z_]\w*)\(")
METHOD = re.compile(r"static\s+(?:async\s+)?([A-Za-z_]\w*)\s*\(")
SCRIPT_SRC = re.compile(r"<script[^>]+src=\"([^\"]+)\"")
QUOTED = re.compile(r"['\"]([a-z][a-z0-9_]*)['\"]")
TITLE = re.compile(r"<title>\s*(.*?)\s*</title>", re.S)
# 화면의 `ep: 'schedule'` 같은 속성 값(나중에 `${API_BASE_URL}/${ep}` 로 붙는 주소)
EP = re.compile(r"\bep:\s*'([a-z][a-z0-9_/-]*)'")
VAR = re.compile(r"\$\{[^}]*\}")
LITERAL = re.compile(r"[`'\"](/[^`'\"?#\s]+)")


def route_files(index_js):
    """GET 경로 → 그 핸들러가 있는 라우트 파일입니다. 인라인 핸들러는 뺍니다."""
    owner = {}
    for names, mod in IMPORT.findall(index_js):
        for n in names.split(","):
            n = n.strip().split(" as ")[-1].strip()
            if n:
                owner[n] = "src/routes/%s.js" % mod
    return {path: owner[h] for path, h in ADD.findall(index_js) if h in owner}


def route_patterns(index_js):
    """등록된 GET 경로 전부(등록 순서)입니다."""
    return [path for path, _ in ADD.findall(index_js)]


def sql_tables(js_text, known):
    """SQL 글자의 FROM·JOIN 뒤 표 이름 가운데 실제 표만 돌려줍니다.

    대문자 FROM·JOIN 만 봅니다. JS 의 `import … from` 과 주석의 소문자 from 을
    피하려는 것입니다. 이 저장소의 SQL 은 키워드를 대문자로 씁니다.
    """
    return {t for t in SQL_TABLE.findall(js_text) if t in known}


def match_route(template_path, patterns):
    """`/players/${id}/arsenal` 같은 화면 쪽 주소 틀을 라우트 패턴에 맞춥니다."""
    # 첫 번째로 맞는 패턴이 이깁니다. src/index.js 가 /players/search 같은 글자 경로를
    # /players/:id 같은 변수 경로보다 먼저 등록한다는 점에 기댑니다.
    # `/teams${q}` 처럼 글자에 바로 붙은 끝 변수(쿼리 문자열)는 버립니다.
    path = re.sub(r"(?<=[^/])"+VAR.pattern+"$", "", template_path)
    path = VAR.sub(":v", path).rstrip("/")
    segs = path.split("/")
    for p in patterns:
        ps = p.rstrip("/").split("/")
        if len(ps) != len(segs):
            continue
        if all(a == b or (b.startswith(":") and a) for a, b in zip(segs, ps)):
            if all(not (a == ":v" and not b.startswith(":")) for a, b in zip(segs, ps)):
                return p
    return None


def api_methods(api_js):
    """api.js 의 `static async <이름>(` 마다 그 몸통에서 처음 부르는 주소 틀입니다."""
    out = {}
    starts = [(m.group(1), m.start()) for m in METHOD.finditer(api_js)]
    for i, (name, start) in enumerate(starts):
        end = starts[i + 1][1] if i + 1 < len(starts) else len(api_js)
        t = TEMPLATE.search(api_js, start, end)
        if t:
            out[name] = t.group(1)
    return out


def page_sources(page_path, html):
    """페이지가 `<script src>` 로 싣는 로컬 JS 파일(있는 것만, 순서대로)입니다."""
    out = []
    for src in SCRIPT_SRC.findall(html):
        if "://" in src:
            continue
        f = (page_path.parent / src.split("?")[0].split("#")[0]).resolve()
        if f.exists():
            out.append(f)
    return out


def source_routes(text, patterns, methods):
    """소스 글자가 부르는 라우트 패턴들입니다(주소 틀 + API.<메서드> 호출)."""
    found = set()
    for tpl in TEMPLATE.findall(text):
        r = match_route(tpl, patterns)
        if r:
            found.add(r)
    # 따옴표·백틱으로 시작하는 글자 경로('/wrc/seasons', `/wrc/by-stadium?…`).
    # 라우트에 맞는 것만 남기므로 '/pages/x'·'/assets/x.png' 같은 링크는 걸러집니다.
    for lit in LITERAL.findall(text):
        r = match_route(lit, patterns)
        if r:
            found.add(r)
    for ep in EP.findall(text):
        r = match_route("/" + ep, patterns)
        if r:
            found.add(r)
    for name in API_CALL.findall(text):
        if name in methods:
            r = match_route(methods[name], patterns)
            if r:
                found.add(r)
    return found


def quoted_tables(text, known):
    """따옴표로 적힌 실제 표 이름들입니다(`/db/table/<이름>` 으로 읽는 화면용)."""
    return {t for t in QUOTED.findall(text) if t in known}


def page_title(html):
    m = TITLE.search(html)
    return m.group(1).strip() if m else ""
