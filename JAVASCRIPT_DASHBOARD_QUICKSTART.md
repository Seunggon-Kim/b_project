# JavaScript 대시보드 빠른 시작 가이드

## ✅ 완료된 작업

b_project를 **Streamlit에서 JavaScript로 완전히 전환**했습니다!

### 📁 새로 생성된 파일들

```
b_project/
├── dashboard_js/                    # 새로운 JavaScript 대시보드
│   ├── index.html                  # 홈페이지
│   ├── css/style.css               # 프리미엄 디자인
│   ├── js/
│   │   ├── api.js                  # API 호출
│   │   └── components.js           # UI 컴포넌트
│   └── pages/
│       ├── team-stats.html         # 팀 통계
│       ├── player-stats.html       # 선수 통계
│       ├── player-analytics.html   # 선수 분석
│       └── database-explorer.html  # 데이터 탐색
├── api/
│   └── main.py                     # FastAPI 백엔드
├── start_api.bat                   # API 서버 실행
└── start_dashboard.bat             # 웹 서버 실행
```

## 🚀 실행 방법

### 방법 1: 배치 파일 사용 (추천)

1. **API 서버 실행**
   - `start_api.bat` 더블클릭
   - 서버가 <http://localhost:8000> 에서 실행됩니다

2. **대시보드 열기**
   - `start_dashboard.bat` 더블클릭
   - 브라우저에서 <http://localhost:8080> 접속

### 방법 2: 수동 실행

1. **터미널 1 - API 서버**

   ```bash
   cd c:\Users\USERNAME\Desktop\b_project
   py -3 api\main.py
   ```

2. **터미널 2 - 웹 서버**

   ```bash
   cd c:\Users\USERNAME\Desktop\b_project\dashboard_js
   py -3 -m http.server 8080
   ```

3. **브라우저에서 접속**
   - <http://localhost:8080>

### 방법 3: 파일 직접 열기 (간단하지만 CORS 제한 있을 수 있음)

1. API 서버만 실행:

   ```bash
   py -3 api\main.py
   ```

2. 파일 탐색기에서 `dashboard_js/index.html` 더블클릭

## 🎨 주요 기능

### ✨ 프리미엄 디자인

- 다크 모드 기본 적용
- Glassmorphism 효과
- 부드러운 애니메이션
- 반응형 레이아웃

### 📊 페이지 구성

1. **홈** - 프로젝트 소개 및 데이터 현황
2. **팀 통계** - KBO 팀 목록
3. **선수 통계** - 타자/투수 성적 순위
4. **선수 분석** - 선수 검색 및 상세 정보
5. **데이터 탐색** - 경기 목록

## 🔧 API 엔드포인트

API 문서: <http://localhost:8000/docs>

주요 엔드포인트:

- `GET /dashboard/stats` - 대시보드 통계
- `GET /teams` - 팀 목록
- `GET /players/search?q={name}` - 선수 검색
- `GET /players/{player_id}` - 선수 상세
- `GET /stats/batters` - 타자 통계
- `GET /stats/pitchers` - 투수 통계
- `GET /games` - 경기 목록

## 💡 기존 Streamlit vs 새로운 JavaScript

### JavaScript 버전의 장점

✅ **더 빠른 성능** - 정적 파일로 즉시 로딩
✅ **더 풍부한 디자인** - 완전한 CSS 커스터마이징
✅ **더 나은 UX** - 부드러운 애니메이션과 인터랙션
✅ **배포 용이** - 정적 호스팅 가능 (GitHub Pages, Netlify 등)
✅ **모바일 최적화** - 완벽한 반응형 디자인

### Streamlit은 언제 사용?

- 빠른 프로토타이핑이 필요할 때
- Python 데이터 과학 라이브러리와 직접 통합할 때
- 내부 팀용 간단한 대시보드

## 🎯 다음 단계 (선택사항)

### 추가 기능 구현

- [ ] Chart.js로 그래프 추가
- [ ] 팀별 상세 순위 테이블
- [ ] 선수 비교 기능
- [ ] 데이터 필터링/정렬
- [ ] 다크/라이트 모드 토글

### 배포

- GitHub Pages에 정적 호스팅
- Vercel/Netlify에 배포
- AWS EC2에 FastAPI 배포

## ⚠️ 문제 해결

### API 서버가 실행되지 않는 경우

```bash
py -3 -m pip install fastapi uvicorn
```

### 데이터가 로드되지 않는 경우

1. API 서버가 실행 중인지 확인 (<http://localhost:8000>)
2. 브라우저 콘솔(F12)에서 에러 확인
3. CORS 문제인 경우 웹 서버 사용 (start_dashboard.bat)

### 포트가 이미 사용 중인 경우

- API: api/main.py에서 포트 변경 (기본 8000)
- 웹: start_dashboard.bat에서 포트 변경 (기본 8080)

## 📞 지원

문제가 발생하면:

1. 브라우저 콘솔(F12) 확인
2. API 서버 로그 확인
3. dashboard_js/README.md 참고

---

**버전**: 3.0.0  
**생성일**: 2026-02-15  
**개발자**: USERNAME
