"""
KBO 야구 데이터 대시보드 - 메인 페이지
"""
import streamlit as st
from pathlib import Path

# 페이지 설정
st.set_page_config(
    page_title="KBO 야구 데이터 대시보드",
    page_icon="⚾",
    layout="wide",
    initial_sidebar_state="expanded"
)

# 메인 타이틀
st.title("⚾ KBO 야구 데이터 대시보드")
st.markdown("---")

# 프로젝트 소개
st.header("📊 프로젝트 소개")
st.markdown("""
이 대시보드는 KBO(한국야구위원회) 문자중계 데이터를 수집하여 분석하고 시각화하는 플랫폼입니다.

**주요 기능:**
- 📈 팀별 통계 및 순위
- 👤 선수별 성적 분석
- 🎯 경기 상세 분석
- 📊 문자중계 기반 인사이트
""")

# 데이터 현황
st.header("📁 데이터 현황")

col1, col2, col3 = st.columns(3)

with col1:
    import sqlite3
    db_path = Path(__file__).parent.parent / 'database' / 'kbo_stats.db'
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM games WHERE season = 2025")
    game_count = cur.fetchone()[0]
    conn.close()
    
    st.metric(
        label="총 경기 수 (2025)",
        value=f"{game_count}",
        delta="수집 완료" if game_count == 720 else f"{game_count}/720 수집됨"
    )

with col2:
    st.metric(
        label="등록된 팀",
        value="10",
        delta="KBO 리그"
    )

with col3:
    import datetime
    st.metric(
        label="마지막 업데이트",
        value=datetime.date.today().strftime("%Y-%m-%d"),
        delta="데이터 병합 완료"
    )

st.markdown("---")

# 사용 방법
st.header("🚀 사용 방법")
st.markdown("""
1. **데이터 수집**: 크롤러를 실행하여 KBO 문자중계 데이터 수집
2. **데이터 저장**: 수집한 데이터를 SQLite 데이터베이스에 저장
3. **대시보드 확인**: 좌측 사이드바에서 원하는 페이지 선택
   - 📊 **팀 통계**: 팀별 승률, 득실점 등 통계 확인
   - 👤 **선수 통계**: 선수별 타율, 방어율 등 성적 분석
   - 🎯 **경기 분석**: 경기별 상세 분석 및 문자중계 확인
""")

# 다음 단계
st.header("📝 다음 단계")
st.info("""
**데이터 수집이 필요합니다!**

1. Python 환경 설정
2. 크롤러 실행하여 데이터 수집
3. 데이터베이스에 저장
4. 대시보드에서 분석 시작
""")

# 푸터
st.markdown("---")
st.caption("KBO 야구 데이터 대시보드 v1.0 | 데이터 출처: Naver 문자중계")
