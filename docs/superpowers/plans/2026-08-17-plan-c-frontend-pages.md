# 계획 C: 프론트엔드를 Cloudflare Pages 로 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** `dashboard_js/` 를 Cloudflare Pages 에 올리고, API 호출을 이식한 Worker 로 돌려 화면을 되살립니다.

**Architecture:** 정적 파일을 그대로 Pages 에 배포합니다. 코드 변경은 API 주소 한 곳뿐입니다. 지금은 EC2 의 nginx 가 `/api` 를 FastAPI 로 넘겨 주는 구조인데, 그 nginx 가 없어졌으므로 절대 주소로 Worker 를 직접 부릅니다. Worker 는 이미 `access-control-allow-origin: *` 를 내보내고 있어 CORS 설정이 따로 필요 없습니다.

**Tech Stack:** Cloudflare Pages, Wrangler, 순수 HTML/CSS/JS (빌드 도구 없음)

## Global Constraints

- 예산 0원. 유료 플랜 전환, 도메인 구입은 금지합니다.
- Pages 무료 한도: 대역폭 무제한, 빌드 월 500회, 사이트당 파일 20,000개·파일당 25MB.
- **빌드 도구를 도입하지 않습니다.** 지금 프론트엔드는 번들러 없이 `<script src>` 로 굴러갑니다. 그 구조를 유지합니다. npm 의존성이 생기면 Pages 빌드가 필요해지고 관리 대상이 늘어납니다.
- 사용자 노출 한국어는 `습니다/합니다/입니다` 정중체를 씁니다.
- 명령은 Windows PowerShell 기준입니다. 저장소 루트에서 실행합니다.
- Worker 주소: `https://kbo-api.bstats-baseball.workers.dev`
- **화면 동작을 바꾸지 않습니다.** 이 계획은 배포 위치와 API 주소만 옮깁니다. 디자인·기능 개선은 범위 밖입니다.

---

## 현재 상태 실측

```
dashboard_js/   파일 38개, 1.7MB
  HTML 7개      index.html + pages/ 6개
  JS 4개        api.js, js/api.js, js/components.js, js/nav.js
  CSS 2개       css/style.css, css/analysis.css
  폰트 3개      KBO-Dia-Gothic (woff)
  로고 13개     assets/logos/*.png (SO 만 svg)
  기타          favicon 5개, player_no_image.png
```

**API 주소가 박힌 곳은 세 군데뿐입니다.**

| 파일 | 줄 | 내용 |
|---|---|---|
| `dashboard_js/js/api.js` | 4 | `const API_BASE_URL = isLocal ? 'http://localhost:8000' : '/api';` |
| `dashboard_js/pages/article.html` | 273 | `const API = isLocal ? 'http://localhost:8000' : '/api';` |
| `dashboard_js/pages/factor-stats.html` | 148 | 같은 형태 |

나머지 페이지는 `js/api.js` 를 `<script src>` 로 불러 쓰므로 그 파일만 고치면 따라옵니다.

`dashboard_js/api.js`(루트)와 `dashboard_js/js/api.js.backup` 은 쓰이지 않는 잔재로 보입니다. Task 1 에서 확인하고 정리합니다.

### 화면이 부르는 API 17개

```
/dashboard/stats   /teams          /players/search   /players/{id}
/players/{id}/news /standings      /games            /leaders
/stats/seasons     /stats/regulation /stats/batters  /stats/pitchers
/stats/team_range  /db/tables      /db/table/{name}  /db/table/{name}/csv
/logo/{code}
```

**전부 이식이 끝난 것들입니다**(계획 B·B2). `/db/table/{name}/csv` 만 계획 B2 Task 8 에 남아 있으니, 이 계획을 시작하기 전에 그것이 끝났는지 확인하십시오.

### 로고가 두 벌입니다

같은 로고가 두 경로로 서빙됩니다. 화면이 둘 다 씁니다.

| 경로 | 쓰는 곳 |
|---|---|
| `assets/logos/{code}.png` (정적) | 1군 경기 카드, 순위표, 리더보드 |
| `{API}/logo/{code}` (D1 BLOB) | **퓨처스 경기 카드만** |

`index.html:211` 에 그 이유가 주석으로 적혀 있습니다. 퓨처스는 로고를 DB 에서 서빙한다고 되어 있습니다.

**이 계획에서는 통일하지 않습니다.** 동작을 바꾸지 않는 것이 원칙이고, 둘 다 정상 동작합니다. 다만 Task 4 에서 두 경로가 모두 살아 있는지 확인합니다.

---

## File Structure

| 파일 | 책임 |
|---|---|
| `dashboard_js/js/config.js` | **신규.** API 주소를 한 곳에서 정합니다 |
| `dashboard_js/js/api.js` | 수정. `config.js` 의 값을 씁니다 |
| `dashboard_js/pages/article.html` | 수정. 같은 값을 씁니다 |
| `dashboard_js/pages/factor-stats.html` | 수정. 같은 값을 씁니다 |
| `dashboard_js/index.html` | 수정. `config.js` 를 먼저 불러옵니다 |
| `dashboard_js/pages/*.html` (나머지 5개) | 수정. 같은 이유 |
| `migration/check_pages.py` | **신규.** 배포된 화면이 실제로 데이터를 받는지 확인 |

`config.js` 를 새로 두는 이유는, 주소가 세 곳에 흩어져 있으면 다음에 또 바뀔 때 하나를 빠뜨리기 때문입니다. 실제로 지금 세 곳의 값이 이미 제각각입니다.

---

## Task 1: API 주소를 한 곳으로 모읍니다

**Files:**
- Create: `dashboard_js/js/config.js`
- Modify: `dashboard_js/js/api.js`, `dashboard_js/pages/article.html`, `dashboard_js/pages/factor-stats.html`
- Modify: `dashboard_js/index.html`, `dashboard_js/pages/*.html` (script 태그 추가)

**Interfaces:**
- Produces: 전역 `window.KBO_API_BASE` — 모든 화면이 이 값을 씁니다

- [ ] **Step 1: 쓰이지 않는 파일을 확인합니다**

```powershell
Select-String -Path dashboard_js\*.html, dashboard_js\pages\*.html -Pattern "api\.js" | ForEach-Object { $_.Line.Trim() }
```

기대: 전부 `js/api.js` 또는 `../js/api.js` 를 가리킵니다. 루트의 `dashboard_js/api.js` 를
가리키는 곳이 없으면 그 파일과 `js/api.js.backup` 은 쓰이지 않는 잔재입니다.

쓰이지 않는다면 지웁니다. 남겨 두면 다음 사람이 어느 쪽을 고쳐야 할지 헷갈립니다.

```powershell
git rm dashboard_js/api.js dashboard_js/js/api.js.backup
```

**주의**: 위 확인에서 참조가 하나라도 나오면 지우지 마십시오.

- [ ] **Step 2: config.js 를 만듭니다**

```javascript
// API 주소를 여기 한 곳에서 정합니다.
//
// 예전에는 EC2 의 nginx 가 /api 를 FastAPI 로 넘겨 주어 상대 경로면 됐습니다.
// 그 서버가 없어져 이제는 Worker 를 절대 주소로 직접 부릅니다.
//
// 주소가 여러 파일에 흩어져 있으면 다음에 바뀔 때 하나를 빠뜨립니다.
// 실제로 이 값이 js/api.js, pages/article.html, pages/factor-stats.html
// 세 곳에 따로 적혀 있었습니다.
(function () {
  var host = window.location.hostname;
  var isLocal = host === 'localhost' || host === '127.0.0.1';

  // 로컬에서 `py -m uvicorn api.main:app --port 8000` 을 띄워 두고
  // 화면을 열면 그쪽을 봅니다. 그 외에는 배포된 Worker 를 봅니다.
  window.KBO_API_BASE = isLocal
    ? 'http://localhost:8000'
    : 'https://kbo-api.bstats-baseball.workers.dev';
})();
```

- [ ] **Step 3: js/api.js 를 고칩니다**

4행을 바꿉니다.

```javascript
// 기존
const isLocal = window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1';
const API_BASE_URL = isLocal ? 'http://localhost:8000' : '/api';

// 바꿀 것
// 주소는 js/config.js 가 정합니다. 이 파일보다 먼저 로드되어야 합니다.
const API_BASE_URL = window.KBO_API_BASE;
```

**`isLocal` 을 지우기 전에 다른 곳에서 쓰는지 확인하십시오.**

```powershell
Select-String -Path dashboard_js\js\api.js -Pattern "isLocal"
```

- [ ] **Step 4: article.html 과 factor-stats.html 을 고칩니다**

두 파일이 각자 `const API = isLocal ? ... : '/api';` 를 갖고 있습니다.

```javascript
// 바꿀 것
const API = window.KBO_API_BASE;
```

- [ ] **Step 5: 모든 HTML 에 config.js 를 먼저 넣습니다**

`api.js` 를 부르는 곳보다 **위**에 있어야 합니다. 순서가 뒤바뀌면 `window.KBO_API_BASE`
가 `undefined` 인 채로 읽혀 요청이 `undefined/teams` 로 나갑니다.

```html
<!-- index.html -->
<script src="js/config.js"></script>
<script src="js/api.js"></script>

<!-- pages/*.html -->
<script src="../js/config.js"></script>
<script src="../js/api.js"></script>
```

`article.html` 과 `factor-stats.html` 은 `api.js` 를 안 부를 수도 있습니다. 그래도
`config.js` 는 넣어야 합니다.

- [ ] **Step 6: 주소가 남아 있지 않은지 확인합니다**

```powershell
Select-String -Path dashboard_js -Include *.js,*.html -Pattern "localhost:8000|'/api'" -Recurse
```

기대: `js/config.js` 한 곳에서만 나옵니다.

- [ ] **Step 7: 커밋합니다**

```powershell
git add dashboard_js/
git commit -m "refactor(frontend): API 주소를 config.js 한 곳으로 모으고 Worker 주소로 교체"
```

---

## Task 2: Pages 에 배포합니다

**Files:**
- Modify: `package.json` (배포 스크립트 추가)

- [ ] **Step 1: Pages 프로젝트를 만듭니다**

```powershell
npx wrangler pages project create kbo-dashboard --production-branch main
```

이름은 주소가 됩니다. `https://kbo-dashboard-a0g.pages.dev` 가 됩니다.
Worker 와 달리 **계정 서브도메인이 아니라 프로젝트 이름이 그대로 주소**입니다.
전 세계에서 유일해야 하므로 이미 쓰는 이름이면 다른 것을 고르십시오.

- [ ] **Step 2: 배포합니다**

```powershell
npx wrangler pages deploy dashboard_js --project-name kbo-dashboard
```

빌드 과정이 없습니다. 정적 파일을 그대로 올립니다.

- [ ] **Step 3: package.json 에 스크립트를 더합니다**

```json
"deploy:pages": "wrangler pages deploy dashboard_js --project-name kbo-dashboard"
```

- [ ] **Step 4: 주소가 응답하는지 봅니다**

```powershell
curl.exe -s -o NUL -w "%{http_code}`n" https://kbo-dashboard-a0g.pages.dev/
```

기대: `200`. 새 주소는 퍼지는 데 몇 분 걸릴 수 있습니다.

- [ ] **Step 5: 커밋합니다**

```powershell
git add package.json
git commit -m "chore(pages): 프론트엔드 배포 스크립트 추가"
```

---

## Task 3: 화면이 데이터를 받는지 기계적으로 확인합니다

**Files:**
- Create: `migration/check_pages.py`

**Interfaces:**
- Produces: 페이지별 로딩 성공 여부. 눈으로 보기 전에 명백한 실패를 먼저 걸러 냅니다.

화면 검증은 결국 눈으로 봐야 하지만, **그 전에 기계가 잡을 수 있는 것은 기계가 잡는
편이 빠릅니다.** 정적 파일이 200 인지, 그 안에서 참조하는 자원이 살아 있는지,
API 가 CORS 헤더를 제대로 주는지는 자동으로 확인됩니다.

- [ ] **Step 1: 확인 스크립트를 만듭니다**

```python
# -*- coding: utf-8 -*-
"""배포된 Pages 와 Worker 가 짝을 이뤄 동작하는지 확인합니다.

브라우저로 열어 보기 전에 명백한 실패를 걸러 냅니다. 페이지가 404 인지,
참조하는 자원이 빠졌는지, API 가 CORS 를 막는지 같은 것들입니다.
화면이 예쁘게 그려지는지는 사람이 봐야 합니다.
"""
import argparse
import re
import sys
import urllib.error
import urllib.parse
import urllib.request

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/125.0 Safari/537.36")

PAGES = [
    "/",
    "/pages/player-stats.html",
    "/pages/team-stats.html",
    "/pages/player-analytics.html",
    "/pages/factor-stats.html",
    "/pages/database-explorer.html",
    "/pages/article.html",
]


def fetch(url, timeout=30):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, r.read(), dict(r.headers)
    except urllib.error.HTTPError as e:
        return e.code, e.read(), dict(e.headers)
    except Exception as exc:
        return 0, str(exc).encode(), {}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pages", default="https://kbo-dashboard-a0g.pages.dev")
    ap.add_argument("--api", default="https://kbo-api.bstats-baseball.workers.dev")
    args = ap.parse_args()

    bad = []

    print("=== 페이지 ===")
    assets = set()
    for path in PAGES:
        status, body, _ = fetch(args.pages.rstrip("/") + path)
        text = body.decode("utf-8", "replace")
        ok = status == 200 and len(text) > 500
        if not ok:
            bad.append(("페이지", path, status))
        print("  %-34s %s  %d바이트" % (path, status, len(body)))
        # 이 페이지가 참조하는 로컬 자원을 모읍니다.
        for m in re.finditer(r'(?:src|href)="([^"]+)"', text):
            u = m.group(1)
            if u.startswith(("http://", "https://", "//", "data:", "#")):
                continue
            base = path.rsplit("/", 1)[0] or ""
            assets.add(urllib.parse.urljoin(args.pages + base + "/", u))

    print()
    print("=== 참조 자원 %d개 ===" % len(assets))
    for u in sorted(assets):
        status, body, _ = fetch(u)
        if status != 200:
            bad.append(("자원", u, status))
            print("  %s  %s" % (status, u))
    print("  (200 인 것은 생략했습니다)")

    print()
    print("=== API CORS ===")
    for path in ["/teams", "/dashboard/stats", "/standings"]:
        status, _, headers = fetch(args.api + path)
        acao = headers.get("Access-Control-Allow-Origin", "")
        ok = status == 200 and acao == "*"
        if not ok:
            bad.append(("API", path, "%s / ACAO=%r" % (status, acao)))
        print("  %-20s %s  ACAO=%s" % (path, status, acao or "(없음)"))

    print()
    if bad:
        print("문제 %d건" % len(bad))
        for kind, what, why in bad:
            print("  [%s] %s -> %s" % (kind, what, why))
        return 1
    print("모두 정상입니다. 이제 브라우저로 열어 확인하십시오.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 2: 실행합니다**

```powershell
py migration/check_pages.py
```

기대: `모두 정상입니다`.

`자원` 항목에서 404 가 나오면 경로가 틀린 것입니다. Pages 는 파일을 올린 구조
그대로 서빙하므로, EC2 의 nginx 가 하던 경로 재작성이 없습니다.

- [ ] **Step 3: 커밋합니다**

```powershell
git add migration/check_pages.py
git commit -m "feat(migration): Pages 배포 확인 도구 추가"
```

---

## Task 4: 브라우저로 일곱 페이지를 확인합니다

**Files:** 없음 (확인만 합니다)

여기부터는 사람이 봐야 합니다. **골든 비교로 대신할 수 없는 유일한 단계입니다.**

- [ ] **Step 1: 각 페이지를 열어 아래를 확인합니다**

| 페이지 | 확인할 것 |
|---|---|
| `/` (홈) | 오늘 경기 카드, 팀 순위표, 개인 순위 Top5, 대시보드 숫자 |
| `/pages/player-stats.html` | 타자·투수 기록표, 팀 필터, 시즌 선택 |
| `/pages/team-stats.html` | 기간 선택 후 팀 타격·투구 표 |
| `/pages/player-analytics.html` | 선수 검색, 구종 구사율, 아스널 산점도 |
| `/pages/factor-stats.html` | wRC+ 비교표, 시즌 셀렉터, 구장별 파크팩터 |
| `/pages/database-explorer.html` | 표 목록, 표 하나 열기, CSV 내려받기 |
| `/pages/article.html` | 글 목록과 본문 |

- [ ] **Step 2: 개발자 도구 콘솔을 함께 봅니다**

`F12` 를 눌러 `Console` 과 `Network` 를 확인하십시오. 화면이 그려져도 일부 요청이
실패하고 있을 수 있습니다.

특히 볼 것입니다.

- `undefined/teams` 같은 주소로 나가는 요청 — `config.js` 로드 순서 문제입니다
- CORS 오류 — Worker 의 `access-control-allow-origin` 이 빠진 엔드포인트가 있는지
- 404 로 실패하는 자원

- [ ] **Step 3: 로고 두 경로를 모두 확인합니다**

1군 경기 카드는 `assets/logos/{code}.png` 를, **퓨처스 경기 카드는 `/logo/{code}` API**
를 씁니다(`index.html:211`). 두 곳 다 로고가 보이는지 확인하십시오. 한쪽만 깨지면
어느 경로가 문제인지 바로 알 수 있습니다.

- [ ] **Step 4: 시즌 셀렉터를 확인합니다**

`/wrc/seasons` 가 시즌 목록을 `play_by_play` 에서 뽑아 파생 테이블과 조인합니다
(`api/main.py:834`). 적재가 끝나면 2015~2026 이 다 나와야 정상입니다. 2025 만
나오면 적재가 덜 됐거나 다른 문제입니다.

- [ ] **Step 5: 확인 결과를 기록합니다**

문제가 없으면 이 파일 아래 "확인 결과" 절에 적습니다. 문제가 있으면 무엇이
어떻게 깨졌는지 적고 고친 뒤 다시 확인합니다.

---

## Task 5: 설계 문서 갱신과 마무리

- [ ] **Step 1: 설계 문서 §11 마일스톤 M5 를 채웁니다**

Pages 주소와 확인 결과를 적습니다.

- [ ] **Step 2: 두 주소를 한곳에 정리합니다**

`README.md` 나 설계 문서에 아래를 남깁니다. 다음에 접속할 때 찾기 쉽도록.

```
화면   https://kbo-dashboard-a0g.pages.dev
API    https://kbo-api.bstats-baseball.workers.dev
```

- [ ] **Step 3: 커밋하고 push 합니다**

---

## 완료 기준

- [ ] `py migration/check_pages.py` 가 `모두 정상입니다` 를 출력합니다
- [ ] 일곱 페이지가 브라우저에서 데이터와 함께 그려집니다
- [ ] 개발자 도구 콘솔에 오류가 없습니다
- [ ] 1군과 퓨처스 로고가 둘 다 보입니다
- [ ] API 주소가 `js/config.js` 한 곳에만 있습니다
- [ ] 설계 문서 §11 M5 에 결과가 적혀 있습니다

## 계획 C 에서 하지 않는 것

- **디자인·기능 개선**: 이 계획은 배포 위치와 API 주소만 옮깁니다. 화면 동작을 바꾸면 무엇이 이전 때문에 깨졌는지 가려집니다.
- **로고 경로 통일**: 정적 파일과 D1 두 벌이 공존하지만 둘 다 동작합니다. 손대지 않습니다.
- **커스텀 도메인 연결**: `pages.dev` 무료 주소를 씁니다. 도메인 구입은 예산 조건에 어긋납니다.
- **재크롤링과 정기 실행**: 계획 D 입니다.

## 선행 조건

- 계획 B2 Task 8 (`/db/table/{name}/csv`) 이 끝나 있어야 합니다. DB 탐색기 페이지가 그것을 씁니다.
- D1 적재가 끝나 있어야 화면 숫자가 맞습니다. 적재 중에는 경기 수와 타석 수가 실제보다 적게 보입니다.

## 확인 결과 (2026-08-17)

주소가 계획과 다릅니다. `kbo-dashboard` 는 이미 쓰이는 이름이라 Cloudflare
가 접미사를 붙였습니다.

```
화면   https://kbo-dashboard-a0g.pages.dev
API    https://kbo-api.bstats-baseball.workers.dev
```

헤드리스 Chrome 으로 일곱 페이지를 열고, 콘솔 오류와 실패한 요청을 걷어
확인했습니다(`migration/check_pages_browser.py`). 눌러야 나오는 것들은
따로 눌러 봤습니다(`migration/check_pages_interact.py`).

| 페이지 | 결과 | 비고 |
|---|---|---|
| `/` | 정상 | 경기 카드·팀 순위·개인 순위 모두 데이터가 들어옵니다 |
| `/pages/player-stats.html` | 정상 | |
| `/pages/team-stats.html` | 정상 | 팀 타격 표에 10개 구단이 나옵니다 |
| `/pages/player-analytics.html` | 정상 | 검색해야 나오는 화면입니다. "김도영" 검색 확인 |
| `/pages/factor-stats.html` | **깨짐** | 아래 참조 |
| `/pages/database-explorer.html` | 정상 | 표 18개, `play_by_play` 열기 확인 |
| `/pages/article.html` | 정상 | 목록·본문 열기 확인 (296자 → 3,191자) |

로고 두 경로 모두 정상입니다. 1군 카드의 정적 파일과, 퓨처스 카드가 쓰는
`/logo` API(D1 BLOB) 둘 다 확인했습니다. 퓨처스 탭에서 로고 이미지 50개 중
깨진 것이 0개입니다. `naturalWidth` 로 봤습니다. `src` 만 보면 404 여도
붙어 있는 것처럼 보입니다.

### factor-stats 가 깨진 이유는 이전 때문이 아닙니다

`re24_matrix_by_season` 표가 D1 에 없어 404 가 납니다. 그런데 이 표는
**로컬 DB 에도, 백업 덤프에도 없습니다.** 적재에서 빠뜨린 것이 아니라
원천에 처음부터 없었습니다. `migration/export_to_d1.py` 의 `TABLE_ORDER`
주석에 "아직 없는 테이블"로 이미 적혀 있습니다.

EC2 에서는 있었을 것입니다. 화면이 그것을 부르고 있으니까요. 로컬 DB 가
2025 시즌만 담은 축소본이라 이 파생 표가 함께 오지 않았습니다.

**재생성해서 넣지 않기로 했습니다.** `park_factors/build_re24_run_values.py`
로 만들 수는 있지만, dry-run 결과 `season=0` 의 값이 `season=2025` 와
n_obs 까지 완전히 같습니다. 이 표의 `season=0` 은 "2015~2025 열한 시즌을
모은 기준선"이라는 뜻인데 지금 넣으면 실제로는 한 시즌입니다. 화면은
열한 시즌으로 표시합니다. **틀린 라벨을 붙인 값이라 없는 것보다 나쁩니다.**
계획 D 에서 나머지 시즌을 다시 모은 뒤 만들어야 맞습니다.

곁들여 드러난 것이 있습니다. 이 화면은 파크 팩터와 RE24 를 `Promise.all`
로 함께 부르므로, **RE24 하나가 404 면 파크 팩터 탭까지 같이 죽습니다.**
파크 팩터 데이터(`statiz_park_factor`)는 D1 에 멀쩡히 있는데도 못 봅니다.
원본에서는 두 표가 다 있어 드러나지 않던 결함입니다.

고치려면 화면 코드를 손대야 하는데, 이 계획은 "화면 동작을 바꾸지
않습니다"가 원칙입니다. 여기서 고치면 무엇이 이전 때문에 깨졌고 무엇이
원래 그랬는지 경계가 흐려집니다. **판단을 남겨 둡니다.**

### 데이터 탐색의 Cron 표는 이제 사실이 아닙니다

`database-explorer.html` 의 "자동 수집 스케줄(Cron)" 표가 EC2 crontab 을
기준으로 하드코딩되어 있습니다. 그 서버는 없습니다. 표에 적힌 아홉 개
작업(`auto_deploy_poll.sh` 의 "GitHub main 감지 후 서버 자동 반영" 포함)은
지금 아무것도 돌지 않습니다. "마지막 업데이트 시간"도 전부 `-` 입니다.

계획 D 에서 Actions 와 Worker Cron 으로 정기 실행을 세운 뒤, 그 내용으로
바꿔야 합니다. 지금 고치면 아직 없는 것을 있다고 적게 됩니다.
