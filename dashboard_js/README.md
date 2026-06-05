# KBO Baseball Analytics - JavaScript Dashboard

프리미엄 디자인의 JavaScript 기반 KBO 야구 데이터 대시보드

## 🎨 특징

- ✨ **모던 디자인**: 다크모드, glassmorphism, 그라데이션 효과
- ⚡ **빠른 성능**: Vanilla JavaScript로 구현된 경량 대시보드
- 📱 **반응형**: 모바일, 태블릿, 데스크톱 모두 지원
- 🎯 **직관적 UI**: 사용자 친화적인 인터페이스
- 🔄 **실시간 데이터**: FastAPI 백엔드와 연동

## 📁 프로젝트 구조

```
dashboard_js/
├── index.html              # 메인 홈페이지
├── css/
│   └── style.css          # 프리미엄 스타일시트
├── js/
│   ├── api.js             # API 호출 함수
│   └── components.js      # UI 컴포넌트
└── pages/
    ├── team-stats.html           # 팀 통계
    ├── player-stats.html         # 선수 통계
    ├── player-analytics.html     # 선수 분석
    └── database-explorer.html    # 데이터 탐색

api/
└── main.py                # FastAPI 백엔드 서버
```

## 🚀 시작하기

### 1. 필수 패키지 설치

```bash
pip install fastapi uvicorn
```

### 2. API 서버 실행

```bash
# Windows
python api/main.py

# 또는 uvicorn 직접 실행
uvicorn api.main:app --reload --host 0.0.0.0 --port 8000
```

API 서버가 `http://localhost:8000`에서 실행됩니다.

### 3. 대시보드 열기

브라우저에서 `dashboard_js/index.html` 파일을 열거나, 로컬 서버를 실행하세요:

```bash
# Python 내장 서버 사용
cd dashboard_js
python -m http.server 8080
```

그 다음 브라우저에서 `http://localhost:8080` 접속

## 📊 페이지 구성

### 1. 홈 (index.html)

- 프로젝트 소개
- 데이터 현황 통계
- 주요 기능 안내
- 데이터 수집 로직 설명

### 2. 팀 통계 (team-stats.html)

- KBO 리그 팀 목록
- 팀별 기본 정보

### 3. 선수 통계 (player-stats.html)

- 타자 성적 순위
- 투수 성적 순위
- 탭으로 구분된 인터페이스

### 4. 선수 분석 (player-analytics.html)

- 선수 검색 기능
- 선수 상세 정보
- 시즌별 성적 테이블

### 5. 데이터 탐색 (database-explorer.html)

- 최근 경기 목록
- 데이터베이스 구조 정보

## 🎨 디자인 시스템

### 색상 팔레트

- **Primary**: #3b82f6 (파란색)
- **Secondary**: #8b5cf6 (보라색)
- **Accent**: #f59e0b (주황색)
- **Success**: #10b981 (초록색)

### 주요 디자인 요소

- **Glassmorphism**: 반투명 배경 + 블러 효과
- **Gradient**: 부드러운 그라데이션
- **Animations**: 페이드인, 호버 효과
- **Shadows**: 깊이감 있는 그림자

## 🔧 API 엔드포인트

### 대시보드 통계

```
GET /dashboard/stats
```

### 팀 목록

```
GET /teams
```

### 선수 검색

```
GET /players/search?q={query}
```

### 선수 상세 정보

```
GET /players/{player_id}
```

### 타자 통계

```
GET /stats/batters?season={year}&limit={count}
```

### 투수 통계

```
GET /stats/pitchers?season={year}&limit={count}
```

### 경기 목록

```
GET /games?season={year}&limit={count}
```

## 💡 기술 스택

### Frontend

- **HTML5**: 시맨틱 마크업
- **CSS3**: 커스텀 디자인 시스템
- **JavaScript (ES6+)**: Vanilla JS, async/await
- **Google Fonts**: Inter 폰트

### Backend

- **FastAPI**: 고성능 Python 웹 프레임워크
- **SQLite**: 데이터베이스
- **Uvicorn**: ASGI 서버

## 📱 반응형 디자인

- **Desktop**: 1400px 최대 너비
- **Tablet**: 1024px 이하 - 2열 그리드
- **Mobile**: 640px 이하 - 1열 그리드

## 🔄 기존 Streamlit 대시보드와 비교

### JavaScript 버전의 장점

✅ 더 빠른 로딩 속도  
✅ 더 풍부한 UI/UX 커스터마이징  
✅ 모던하고 프리미엄한 디자인  
✅ 정적 호스팅 가능 (GitHub Pages 등)  
✅ 더 나은 반응형 지원  

### Streamlit 버전의 장점

✅ Python만으로 빠른 프로토타이핑  
✅ 데이터 과학 라이브러리와 쉬운 통합  
✅ 내장 위젯 및 차트  

## 🚧 향후 개발 계획

- [ ] 차트 및 그래프 추가 (Chart.js)
- [ ] 팀별 상세 순위 테이블
- [ ] 경기별 상세 분석 페이지
- [ ] 선수 비교 기능
- [ ] 데이터 필터링 및 정렬
- [ ] 다크/라이트 모드 토글
- [ ] 데이터 내보내기 (CSV, Excel)

## 📝 라이선스

이 프로젝트는 개인 프로젝트입니다.

## 👤 개발자

USERNAME

---

**버전**: 3.0.0  
**마지막 업데이트**: 2026-02-15  
**기술**: JavaScript, FastAPI, SQLite
