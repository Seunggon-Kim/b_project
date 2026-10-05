# -*- coding: utf-8 -*-
"""테이블 계보의 재료를 코드에서 뽑습니다.

설계: docs/superpowers/specs/2026-10-04-table-lineage-design.md

뽑기 쉬운 것만 여기서 뽑습니다. 수집 스크립트가 어떤 표에 쓰는지는 SQL 을
조립해 만드는 곳이 많아 기계로 뽑으면 틀리기 쉽습니다. 그건 손 파일
(database/lineage_writes.json)에 적고, 테스트가 실제 코드와 맞는지 봅니다.
"""
import re
from pathlib import Path

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


def schedule_kst(crons):
    """예약 시각 여럿을 한 줄로 씁니다. 모두 매일이면 "매일 16:07·19:07" 처럼 묶습니다."""
    texts = [cron_to_kst(c) for c in crons]
    if not texts:
        return None
    if len(texts) > 1 and all(x.startswith("매일 ") for x in texts):
        return "매일 " + "·".join(x[len("매일 "):] for x in texts)
    return " · ".join(texts)


def parse_workflow(text):
    """워크플로 YAML 글자에서 실행 시각과 (단계 이름, 스크립트) 목록을 뽑습니다.

    주석이 아닌 줄의 `<경로>.py`, `-m <모듈>`(모듈은 경로로 바꿈, `pip` 은 뺌),
    `bash <경로>.sh` 를 모두 스크립트로 봅니다. 해석기를 어떻게 부르든
    (`python -u`, `python3.12`, `python -X utf8`, `python \\` 다음 줄의 경로)
    빠지지 않게 하려는 것입니다. 단계 이름은 목록 항목 줄(`- …`)마다 비우고
    그 항목의 `name:` 으로 채웁니다. 이름 없는 단계가 앞 단계의 이름을
    물려받지 않습니다. 같은 (단계, 스크립트)는 한 번만 넣습니다.
    """
    # 예약 시각은 주석이 아닌 줄의 `cron:` 을 모두 읽습니다(roster 는 하루 두 번).
    crons = [m.group(2) for line in text.splitlines()
             if not line.lstrip().startswith("#")
             for m in [CRON.search(line)] if m]
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
    return {"cron_utc": crons[0] if crons else None, "crons": crons, "steps": steps}


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


def source_routes(text, patterns, methods=None):
    """소스 글자가 부르는 라우트 패턴들입니다(주소 틀 + API.<메서드> 호출).

    methods(api_methods 의 결과)를 주면 `API.<메서드>(` 호출도 주소로 셉니다.
    build_lineage 는 이것 대신 page_texts 로 페이지가 부르는 라이브러리 멤버의
    글자를 넣어 씁니다.
    """
    methods = methods or {}
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


# --- 여러 페이지가 같이 싣는 JS(라이브러리) ---------------------------------
#
# 라이브러리를 싣기만 해도 그 안의 주소가 모두 페이지에 붙으면 안 됩니다.
# 라이브러리 글자를 이름 있는 멤버(함수·메서드·객체 상수)로 나누고, 페이지가
# 부르는 멤버(와 그 멤버가 쓰는 멤버)의 글자와 맨 위 코드(실을 때 도는 코드)만
# 페이지 글자에 넣습니다. 정규식으로 하는 대략의 읽기입니다. 문법을 다 읽지는
# 않지만 주석·따옴표·백틱·정규식 글자 속은 건너뛰어 괄호 짝을 맞춥니다.

JS_KEYWORDS = {"if", "for", "while", "switch", "catch", "function", "with", "return",
               "typeof", "new", "await", "else", "do", "try", "in", "of", "delete",
               "void", "throw", "case", "yield", "super", "import", "export"}
JS_FUNC = re.compile(r"\b(?:async\s+)?function\s*\*?\s*([A-Za-z_$][\w$]*)\s*\(")
JS_ASSIGN_FUNC = re.compile(
    r"(?<![\w$.])([A-Za-z_$][\w$]*)\s*[:=]\s*(?:async\s+)?function\b[^(]*\(")
JS_ASSIGN_ARROW = re.compile(
    r"(?<![\w$.])([A-Za-z_$][\w$]*)\s*[:=]\s*(?:async\s*)?"
    r"(?:\((?:[^()]|\([^()]*\))*\)|[A-Za-z_$][\w$]*)\s*=>")
JS_METHOD = re.compile(
    r"(?<![\w$.])(?:static\s+)?(?:async\s+)?(?:[gs]et\s+)?([A-Za-z_$][\w$]*)\s*"
    r"\((?:[^()]|\([^()]*\))*\)\s*\{")
JS_DATA = re.compile(r"\b(?:const|let|var)\s+([A-Za-z_$][\w$]*)\s*=\s*([\[{])")
JS_IDENT = re.compile(r"(?<![\w$])([A-Za-z_$][\w$]*)")
JS_CALL = re.compile(r"(?<![\w$])([A-Za-z_$][\w$]*)\s*\(")
REGEX_PREV = set("(,=:[!&|?{};+-*%<>~^")
REGEX_KEYWORD = re.compile(
    r"\b(?:return|typeof|case|void|delete|throw|in|of|new|else|do|yield|await)\s*$")


def _blank(buf, a, b):
    for k in range(a, b):
        if buf[k] != "\n":
            buf[k] = " "


def _quoted_end(js, i):
    """js[i] 가 ' 또는 " 일 때 닫는 따옴표 다음 위치입니다(줄이 끝나면 거기서 멈춤)."""
    q, j, n = js[i], i + 1, len(js)
    while j < n and js[j] != q and js[j] != "\n":
        j += 2 if js[j] == "\\" else 1
    return min(j + 1, n)


def _regex_end(js, i):
    """js[i] 가 정규식 글자의 / 일 때 닫는 / 와 플래그 다음 위치입니다."""
    j, n, in_class = i + 1, len(js), False
    while j < n and js[j] != "\n":
        c = js[j]
        if c == "\\":
            j += 2
            continue
        if c == "[":
            in_class = True
        elif c == "]":
            in_class = False
        elif c == "/" and not in_class:
            j += 1
            while j < n and (js[j].isalnum() or js[j] == "_"):
                j += 1
            return j
        j += 1
    return j


def _lex(js, i, code, plain, in_expr=False):
    """주석은 code·plain 둘 다에서, 글자 속은 code 에서만 지웁니다.

    in_expr 면 백틱 안 `${ … }` 의 식이라 짝 맞는 `}` 다음 위치를 돌려줍니다.
    """
    n, depth, prev = len(js), 0, ""
    while i < n:
        c, nx = js[i], js[i + 1:i + 2]
        if c == "/" and nx in ("/", "*"):
            if nx == "/":
                j = js.find("\n", i)
                j = n if j < 0 else j
            else:
                j = js.find("*/", i + 2)
                j = n if j < 0 else j + 2
            _blank(code, i, j)
            _blank(plain, i, j)
            i = j
            continue
        if c in "'\"":
            j = _quoted_end(js, i)
            _blank(code, i + 1, j - 1)
            i, prev = j, "a"
            continue
        if c == "`":
            i, prev = _template(js, i, code, plain), "a"
            continue
        if c == "/" and (prev == "" or prev in REGEX_PREV
                         or (prev == "w" and REGEX_KEYWORD.search(js[max(0, i - 12):i]))):
            j = _regex_end(js, i)
            _blank(code, i + 1, j - 1)
            i, prev = j, "a"
            continue
        if in_expr:
            if c == "{":
                depth += 1
            elif c == "}":
                if depth == 0:
                    return i + 1
                depth -= 1
        if not c.isspace():
            prev = "w" if (c.isalnum() or c in "_$") else c
        i += 1
    return n


def _template(js, i, code, plain):
    """js[i] 가 백틱일 때 닫는 백틱 다음 위치입니다. `${ … }` 안은 코드로 읽습니다."""
    j, n = i + 1, len(js)
    while j < n:
        c = js[j]
        if c == "\\":
            _blank(code, j, min(j + 2, n))
            j += 2
            continue
        if c == "`":
            return j + 1
        if c == "$" and js[j + 1:j + 2] == "{":
            j = _lex(js, j + 2, code, plain, in_expr=True)
            continue
        if c != "\n":
            code[j] = " "
        j += 1
    return n


def js_mask(js):
    """(code, plain): code 는 주석과 글자 속을, plain 은 주석만 공백으로 바꾼 글자입니다.

    길이와 줄바꿈 위치는 원문과 같습니다.
    """
    code, plain = list(js), list(js)
    _lex(js, 0, code, plain)
    return "".join(code), "".join(plain)


def _close(code, i):
    """code[i] 의 여는 괄호와 짝인 닫는 괄호 다음 위치입니다."""
    depth = 0
    for k in range(i, len(code)):
        ch = code[k]
        if ch in "([{":
            depth += 1
        elif ch in ")]}":
            depth -= 1
            if depth == 0:
                return k + 1
    return len(code)


def _expr_end(code, i):
    """화살표 함수의 식 몸통이 끝나는 곳(같은 깊이의 ; , 또는 바깥 닫는 괄호)입니다."""
    depth = 0
    for k in range(i, len(code)):
        ch = code[k]
        if ch in "([{":
            depth += 1
        elif ch in ")]}":
            if depth == 0:
                return k
            depth -= 1
        elif ch in ";," and depth == 0:
            return k
    return len(code)


def _body_after(code, j):
    """j 뒤 공백을 건너 `{` 이면 그 짝까지, 아니면 식 끝까지입니다."""
    while j < len(code) and code[j].isspace():
        j += 1
    if j < len(code) and code[j] == "{":
        return _close(code, j)
    return _expr_end(code, j)


def js_members(code):
    """이름 있는 멤버 목록 [(이름, 시작, 끝)]입니다(시작 순).

    code 는 js_mask 의 첫 번째 값입니다. 알아보는 꼴: `function NAME(`,
    `async function NAME(`, 메서드 `NAME(…) {`, `NAME: function`, `NAME = function`,
    `NAME: (…) =>`, `NAME = async (…) =>`, `NAME = x =>`, 객체·배열 상수
    `const NAME = {` / `[`.
    """
    found = {}

    def add(m, end):
        if m.group(1) not in JS_KEYWORDS and m.start(1) not in found:
            found[m.start(1)] = (m.group(1), m.start(), end)

    for m in JS_FUNC.finditer(code):
        add(m, _body_after(code, _close(code, m.end() - 1)))
    for m in JS_ASSIGN_FUNC.finditer(code):
        add(m, _body_after(code, _close(code, m.end() - 1)))
    for m in JS_ASSIGN_ARROW.finditer(code):
        add(m, _body_after(code, m.end()))
    for m in JS_METHOD.finditer(code):
        add(m, _close(code, m.end() - 1))
    for m in JS_DATA.finditer(code):
        add(m, _close(code, m.end() - 1))
    return sorted(found.values(), key=lambda x: (x[1], -x[2]))


def js_library(js):
    """라이브러리 글자를 (맨 위 코드, 멤버들)로 나눕니다.

    맨 위 코드는 어느 멤버에도 들지 않는 코드(실을 때 돎)로 {"text", "seeds"},
    멤버들은 이름 → [{"text", "refs"}] 입니다(같은 이름이 여럿이면 모두).
    text 는 주석만 지운 글자(주소·따옴표 표 이름을 찾는 데 씀), refs 는 그
    코드에 나오는 이름들, seeds 는 맨 위 코드가 부르거나 콜백으로 넘기는
    이름들입니다. 멤버 안에 든 멤버의 글자는 안쪽 멤버 몫입니다.
    """
    code, plain = js_mask(js)
    members = js_members(code)
    owner = [-1] * len(js)
    for idx, (_, start, end) in enumerate(members):
        owner[start:end] = [idx] * (end - start)
    texts, codes = {}, {}
    k = 0
    while k < len(js):
        j = k
        while j < len(js) and owner[j] == owner[k]:
            j += 1
        texts.setdefault(owner[k], []).append(plain[k:j])
        codes.setdefault(owner[k], []).append(code[k:j])
        k = j

    def text(o):
        return "\n".join(texts.get(o, []))

    out = {}
    for idx, (name, _, _) in enumerate(members):
        refs = set(JS_IDENT.findall("\n".join(codes.get(idx, []))))
        out.setdefault(name, []).append({"text": text(idx), "refs": refs})
    top_code = "\n".join(codes.get(-1, []))
    return {"text": text(-1), "seeds": js_calls(top_code) | _callback_args(top_code)}, out


JS_TOKEN = re.compile(r"[A-Za-z_$][\w$.]*|[()\[\]{},]|\S")


def _callback_args(code):
    """괄호 안에 이름 하나만 홀로 넘기는 인자입니다(`on('load', init)` 의 init).

    맨 위 코드가 넘기는 콜백은 실을 때 걸어 두는 것이라 부른 것으로 봅니다.
    `module.exports = { a, b }` 같은 객체 안의 이름은 넘기는 인자가 아니라 뺍니다.
    """
    toks = [m.group(0) for m in JS_TOKEN.finditer(code)]
    out, stack = set(), []
    for i, t in enumerate(toks):
        if t in "([{":
            stack.append(t)
        elif t in ")]}":
            if stack:
                stack.pop()
        elif (stack and stack[-1] == "(" and (t[0].isalpha() or t[0] in "_$")
              and i > 0 and toks[i - 1] in ("(", ",")
              and i + 1 < len(toks) and toks[i + 1] in (",", ")")):
            out.add(t.rsplit(".", 1)[-1])
    return out


def js_calls(text):
    """글자에서 부르는 이름들입니다(`NAME(`·`.NAME(`). 정의(`function NAME(`, `NAME(…) {`)는 뺍니다."""
    defs = {m.start(1) for m in JS_FUNC.finditer(text)}
    defs |= {m.start(1) for m in JS_METHOD.finditer(text)}
    return {m.group(1) for m in JS_CALL.finditer(text)
            if m.start(1) not in defs and m.group(1) not in JS_KEYWORDS}


def used_text(page_code, libraries):
    """페이지가 실제로 쓰는 글자입니다.

    page_code 는 페이지 자신의 글자(HTML + 그 페이지만 싣는 JS), libraries 는
    페이지가 싣는 라이브러리 글자들입니다. 페이지 글자 + 라이브러리의 맨 위
    코드 + 페이지가 부르는 멤버와, 그 멤버가 쓰는 멤버(끝까지 따라감)의 글자를
    이어 붙입니다. 맨 위 코드는 부르거나 콜백으로 넘기는 멤버만 따라갑니다.
    `TS.data = api`·`module.exports = { … }` 같은 내보내기 하나로 모든 멤버가
    붙는 것을 막으려는 것입니다.
    """
    tops, members = [], {}
    for js in libraries:
        top, ms = js_library(js)
        tops.append(top)
        for name, parts in ms.items():
            members.setdefault(name, []).extend(parts)
    todo = list(js_calls(page_code).union(*[t["seeds"] for t in tops]))
    reached = set()
    while todo:
        name = todo.pop()
        if name in reached or name not in members:
            continue
        reached.add(name)
        todo += [r for p in members[name] for r in p["refs"]]
    texts = [page_code] + [t["text"] for t in tops]
    texts += [p["text"] for n in sorted(reached) for p in members[n]]
    return "\n".join(texts)


def page_texts(pages, always=()):
    """페이지(HTML 경로)마다 그 페이지가 쓰는 글자입니다.

    두 페이지 이상이 싣는 로컬 JS 와 always 에 든 파일(js/api.js)은
    라이브러리로 보고 used_text 로 부르는 멤버만 넣습니다. 나머지 JS 는
    그 페이지의 글자로 통째로 넣습니다.
    """
    html, srcs, count = {}, {}, {}
    for p in pages:
        html[p] = Path(p).read_text(encoding="utf-8")
        srcs[p] = [f.resolve() for f in page_sources(Path(p).resolve(), html[p])]
        for f in set(srcs[p]):
            count[f] = count.get(f, 0) + 1
    always = {Path(a).resolve() for a in always}
    libs = {f for f, c in count.items() if c >= 2} | always
    read = {f: f.read_text(encoding="utf-8") for f in count}
    out = {}
    for p in pages:
        own = html[p] + "".join("\n" + read[f] for f in srcs[p] if f not in libs)
        out[p] = used_text(own, [read[f] for f in srcs[p] if f in libs])
    return out
