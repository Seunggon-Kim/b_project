"""
KBO 야구 데이터 대시보드 - 메인 페이지
"""
import streamlit as st
import sqlite3
from pathlib import Path
import datetime

# 페이지 설정
st.set_page_config(
    page_title="KBO 야구 데이터 대시보드",
    page_icon="⚾",
    layout="wide",
    initial_sidebar_state="expanded"
)

# DB 경로
DB_PATH = Path(__file__).parent.parent / 'database' / 'kbo_stats.db'

# 메인 타이틀
st.title("⚾ KBO 야구 데이터 대시보드")
st.markdown("---")

# 프로젝트 소개
st.header("📊 프로젝트 소개")
st.markdown("""
이 대시보드는 **KBO(한국야구위원회)** 경기 데이터를 수집하여 분석하고 시각화하는 플랫폼입니다.

**주요 기능:**
- 📈 **팀별 통계 및 순위** - 시즌별 팀 성적 분석
- 👤 **선수별 성적 분석** - 타자/투수 개인 기록
- 🎯 **경기 상세 분석** - Play-by-Play 데이터 기반 인사이트
- 📊 **문자중계 데이터** - 투구별, 타석별 상세 기록
""")

st.markdown("---")

# 데이터 수집 로직
st.header("🔄 데이터 수집 로직")

col1, col2 = st.columns(2)

with col1:
    st.subheader("📥 Play-by-Play 데이터")
    st.markdown("""
    **출처:** Naver 스포츠 문자중계
    
    **수집 항목:**
    - 투구별 상세 기록 (구종, 구속, 코스)
    - 타석 결과 (안타, 삼진, 볼넷 등)
    - 주루 상황 (주자, 득점)
    - PITCHf/x 트래킹 데이터
    
    **수집 주기:** 시즌 종료 후 일괄 수집
    """)

with col2:
    st.subheader("📊 공식 통계 데이터")
    st.markdown("""
    **출처:** KBO 공식 홈페이지
    
    **수집 항목:**
    - 타자 통계 (타율, OPS, 홈런 등)
    - 투수 통계 (평균자책점, WHIP, 탈삼진 등)
    - 팀별 집계 통계
    
    **수집 주기:** 매일 새벽 1:30 자동 수집 (AWS EC2)
    """)

st.info("""
💡 **자동화 시스템**  
AWS EC2 서버에서 cron job을 통해 매일 자동으로 최신 데이터를 수집하고 이메일로 알림을 발송합니다.
""")

st.markdown("---")

# 데이터 보유 현황
st.header("📁 데이터 보유 현황")

try:
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    
    # 2025 시즌 데이터
    cur.execute("SELECT COUNT(*) FROM games WHERE season = 2025")
    games_2025 = cur.fetchone()[0]
    
    cur.execute("SELECT COUNT(*) FROM play_by_play WHERE gameID LIKE '2025%'")
    plays_2025 = cur.fetchone()[0]
    
    cur.execute("SELECT COUNT(*) FROM kbo_official_batter_stats WHERE season = 2025")
    batters_2025 = cur.fetchone()[0]
    
    cur.execute("SELECT COUNT(*) FROM kbo_official_pitcher_stats WHERE season = 2025")
    pitchers_2025 = cur.fetchone()[0]
    
    # 팀 정보
    cur.execute("SELECT COUNT(*) FROM teams")
    teams_count = cur.fetchone()[0]
    
    conn.close()
    
    # 메트릭 표시
    st.subheader("2025 시즌 데이터")
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric(
            label="📅 경기 수",
            value=f"{games_2025:,}",
            delta="정규시즌" if games_2025 > 0 else "수집 대기"
        )
    
    with col2:
        st.metric(
            label="⚾ 플레이 수",
            value=f"{plays_2025:,}",
            delta="투구/타석 기록"
        )
    
    with col3:
        st.metric(
            label="🏏 타자 통계",
            value=f"{batters_2025}명",
            delta="KBO 공식"
        )
    
    with col4:
        st.metric(
            label="⚡ 투수 통계",
            value=f"{pitchers_2025}명",
            delta="KBO 공식"
        )
    
    # 추가 정보
    col5, col6, col7 = st.columns(3)
    
    with col5:
        st.metric(
            label="🏟️ 등록 팀",
            value=f"{teams_count}개 팀",
            delta="KBO 리그"
        )
    
    with col6:
        completion_rate = (games_2025 / 720 * 100) if games_2025 > 0 else 0
        st.metric(
            label="📊 수집 완료율",
            value=f"{completion_rate:.1f}%",
            delta=f"{games_2025}/720 경기"
        )
    
    with col7:
        st.metric(
            label="🔄 마지막 업데이트",
            value=datetime.date.today().strftime("%Y-%m-%d"),
            delta="자동 갱신"
        )
    
    # 데이터 상세 현황
    st.markdown("---")
    st.subheader("📋 데이터 상세 현황")
    
    with st.expander("🗄️ 데이터베이스 테이블 구조"):
        st.markdown("""
        **주요 테이블:**
        
        1. **`games`** - 경기 기본 정보
           - game_id, 날짜, 홈/원정팀, 점수, 구장 등
        
        2. **`play_by_play`** - 플레이별 상세 기록 (73개 컬럼)
           - 투구 정보, 타격 결과, 주루 상황, PITCHf/x 데이터
        
        3. **`kbo_official_batter_stats`** - 타자 공식 통계
           - 타율, OPS, 홈런, 타점, 도루 등 (복합 PK: player_id, season)
        
        4. **`kbo_official_pitcher_stats`** - 투수 공식 통계
           - 평균자책점, WHIP, 승패, 세이브 등 (복합 PK: player_id, season)
        
        5. **`teams`** - 팀 정보
           - 10개 KBO 구단 기본 정보
        """)
    
    with st.expander("📈 데이터 품질 지표"):
        if games_2025 > 0:
            avg_plays_per_game = plays_2025 / games_2025 if games_2025 > 0 else 0
            st.markdown(f"""
            - **경기당 평균 플레이 수**: {avg_plays_per_game:.0f}개
            - **데이터 무결성**: ✅ 정상
            - **중복 제거**: ✅ 완료
            - **인코딩**: UTF-8 / CP949 호환
            """)
        else:
            st.info("경기 데이터 수집 후 품질 지표가 표시됩니다.")

except Exception as e:
    st.error(f"⚠️ 데이터베이스 연결 오류: {e}")
    st.info("데이터베이스 파일이 올바른 위치에 있는지 확인해주세요.")

st.markdown("---")

# 사용 방법
st.header("🚀 사용 방법")

tab1, tab2, tab3 = st.tabs(["📊 대시보드 탐색", "🔧 데이터 수집", "⚙️ 자동화 설정"])

with tab1:
    st.markdown("""
    ### 대시보드 페이지 안내
    
    좌측 사이드바에서 원하는 페이지를 선택하세요:
    
    1. **📊 Team Stats** - 팀별 순위, 승률, 득실점 분석
    2. **👤 Player Stats** - 선수별 타격/투구 성적
    3. **🎯 Game Analysis** - 경기별 상세 분석
    4. **🗄️ Database Explorer** - 원시 데이터 탐색
    """)

with tab2:
    st.markdown("""
    ### 데이터 수집 방법
    
    **Play-by-Play 데이터:**
    ```bash
    cd crawler
    python pbp.py -f 20250101 -t 20251231 -j
    ```
    
    **공식 통계 데이터:**
    ```bash
    # 타자 통계
    python data_collection/selenium_batter_scraper.py
    python data_collection/kbo_to_db.py
    
    # 투수 통계
    python data_collection/selenium_pitcher_scraper.py
    python data_collection/pitcher_to_db.py
    ```
    """)

with tab3:
    st.markdown("""
    ### AWS EC2 자동화
    
    **Cron 설정 (매일 새벽 1:30):**
    ```bash
    30 1 * * * /home/ubuntu/b_project/run_daily_update.sh
    ```
    
    **자동 수행 작업:**
    1. 최신 공식 통계 크롤링
    2. 데이터베이스 업데이트 (UPSERT)
    3. 이메일 알림 발송
    
    자세한 내용은 `AWS_AUTOMATION_GUIDE.md` 참고
    """)

# 푸터
st.markdown("---")
st.caption("⚾ KBO 야구 데이터 대시보드 v2.1 | 데이터 출처: Naver 문자중계, KBO 공식 홈페이지 | 2026-01-18 업데이트")
