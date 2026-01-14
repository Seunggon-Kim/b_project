"""
선수 통계 페이지
KBO 공식 통계 표시
"""
import streamlit as st
import pandas as pd
import plotly.express as px
import sqlite3
from pathlib import Path

st.set_page_config(page_title="선수 통계", page_icon="👤", layout="wide")

st.title("👤 선수 통계")
st.markdown("---")

# 데이터베이스에서 데이터 로드
@st.cache_data
def load_player_data():
    db_path = Path(__file__).parent.parent.parent / 'database' / 'kbo_stats.db'
    if not db_path.exists():
        raise FileNotFoundError(f"데이터베이스 파일을 찾을 수 없습니다: {db_path}")
        
    conn = sqlite3.connect(db_path)
    
    # KBO 공식 타자 데이터 로드 (전체 스키마)
    try:
        df_batters = pd.read_sql_query("""
            SELECT 
                player_id,
                player_name AS 선수명,
                player_team AS 팀,
                batting_average AS 타율,
                games AS 경기수,
                plate_appearance AS 타석,
                at_bat AS 타수,
                run AS 득점,
                single AS 안타,
                double AS _2루타,
                triple AS _3루타,
                home_run AS 홈런,
                total_bases AS 루타,
                run_batted_in AS 타점,
                sacrifice_bunts AS 희생번트,
                sacrifice_fly AS 희생플라이,
                base_on_balls AS 볼넷,
                intentional_base_on_balls AS 고의4구,
                hit_by_pitch AS 몸에맞는볼,
                strikeout AS 삼진,
                ground_into_double_play AS 병살타,
                slugging_percentage AS 장타율,
                on_base_percentage AS 출루율,
                on_base_plus_slugging AS OPS,
                multi_hits AS 멀티히트,
                runners_in_scoring_position AS 득점권타율,
                pinch_hit_batting_average AS 대타타율,
                extra_base_hits AS 장타,
                ground_outs AS 땅볼아웃,
                air_outs AS 뜬공아웃,
                go_ao AS 땅뜬비율,
                gw_rbi AS 결승타,
                bb_k AS 볼삼비율,
                p_pa AS 타석당_투구_수,
                isop AS ISOP,
                extended_runs AS XR,
                gross_production_average AS GPA,
                created_at AS 등록일시,
                updated_at AS 업데이트일시
            FROM kbo_official_batter_stats 
            ORDER BY 타율 DESC
        """, conn)
        
        # UI 표시를 위해 컬럼명 변경 (언더바 제거)
        df_batters = df_batters.rename(columns={
            "_2루타": "2루타",
            "_3루타": "3루타",
            "타석당_투구_수": "타석당 투구 수"
        })
    except Exception as e:
        st.error(f"타자 데이터 로드 실패: {e}")
        df_batters = pd.DataFrame()
        
    # 투수 데이터는 아직 없음
    df_pitchers = pd.DataFrame()
    
    conn.close()
    return df_batters, df_pitchers

try:
    df_batters, df_pitchers = load_player_data()
    if df_batters.empty and df_pitchers.empty:
        is_sample = True
    else:
        is_sample = False
except Exception as e:
    st.error(f"데이터를 불러오는 중 오류가 발생했습니다: {e}")
    is_sample = True

if is_sample:
    st.warning("⚠️ 데이터베이스에 데이터가 없습니다. 크롤링을 먼저 실행하세요.")
    st.code("""
# 크롤링 실행
python data_collection\\selenium_batter_scraper.py

# DB 저장
python data_collection\\kbo_to_db.py
    """)
    st.stop()

# 사이드바 - 선수 타입 선택
st.sidebar.header("선수 타입")
player_type = st.sidebar.radio(
    "선택하세요",
    options=["타자", "투수"]
)

# 타자 통계
if player_type == "타자":
    st.header("⚾ 타자 통계 (KBO 공식)")
    
    # 필터
    col1, col2, col3 = st.columns(3)
    
    with col1:
        # 팀 필터
        teams = ['전체'] + sorted(df_batters['팀'].unique().tolist())
        selected_team = st.selectbox("팀 선택", teams)
    
    with col2:
        # 최소 타석 필터
        min_pa = st.number_input("최소 타석", min_value=0, value=50, step=10)
    
    with col3:
        # 선수 검색
        search_query = st.text_input("선수 이름 검색", placeholder="선수 이름을 입력하세요...")
    
    # 필터 적용
    df_display = df_batters.copy()
    
    if selected_team != '전체':
        df_display = df_display[df_display['팀'] == selected_team]
    
    if min_pa > 0:
        df_display = df_display[df_display['타석'] >= min_pa]
    
    if search_query:
        df_display = df_display[df_display['선수명'].str.contains(search_query, case=False, na=False)]
    
    # 통계 요약
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("총 선수", f"{len(df_display)}명")
    with col2:
        if not df_display.empty:
            st.metric("평균 타율", f"{df_display['타율'].mean():.3f}")
    with col3:
        if not df_display.empty:
            st.metric("총 홈런", f"{df_display['홈런'].sum():.0f}개")
    with col4:
        if not df_display.empty:
            st.metric("총 타점", f"{df_display['타점'].sum():.0f}점")
    
    st.markdown("---")
    
    # 통계 테이블
    st.subheader("📊 타자 순위")
    
    # 표시할 컬럼 선택
    display_columns = ['선수명', '팀', '타율', '경기수', '타석', '타수', '안타', '홈런', '타점', '득점', 'GPA']
    
    st.dataframe(
        df_display[display_columns],
        use_container_width=True,
        hide_index=True,
        column_config={
            "타율": st.column_config.NumberColumn(format="%.3f"),
            "GPA": st.column_config.NumberColumn(format="%.3f"),
        }
    )
    
    # 상세 정보 보기
    with st.expander("🔍 전체 컬럼 보기"):
        st.dataframe(df_display, use_container_width=True, hide_index=True)
    
    # 차트
    if not df_display.empty and len(df_display) > 0:
        st.markdown("---")
        st.subheader("📈 통계 차트")
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.subheader("타율 상위 10명")
            df_chart = df_display.sort_values('타율', ascending=False).head(10)
            
            fig_avg = px.bar(
                df_chart,
                x='선수명',
                y='타율',
                color='팀',
                title='타율 순위',
                text_auto='.3f',
                color_discrete_sequence=px.colors.qualitative.Set3
            )
            fig_avg.update_layout(showlegend=True)
            st.plotly_chart(fig_avg, use_container_width=True)
        
        with col2:
            st.subheader("홈런 상위 10명")
            df_hr = df_display.sort_values('홈런', ascending=False).head(10)
            fig_hr = px.bar(
                df_hr,
                x='선수명',
                y='홈런',
                color='팀',
                title='홈런 순위',
                text_auto=True,
                color_discrete_sequence=px.colors.qualitative.Set3
            )
            fig_hr.update_layout(showlegend=True)
            st.plotly_chart(fig_hr, use_container_width=True)
        
        col3, col4 = st.columns(2)
        
        with col3:
            st.subheader("타점 상위 10명")
            df_rbi = df_display.sort_values('타점', ascending=False).head(10)
            fig_rbi = px.bar(
                df_rbi,
                x='선수명',
                y='타점',
                color='팀',
                title='타점 순위',
                text_auto=True,
                color_discrete_sequence=px.colors.qualitative.Set3
            )
            fig_rbi.update_layout(showlegend=True)
            st.plotly_chart(fig_rbi, use_container_width=True)
        
        with col4:
            st.subheader("GPA 상위 10명")
            df_gpa = df_display.sort_values('GPA', ascending=False).head(10)
            fig_gpa = px.bar(
                df_gpa,
                x='선수명',
                y='GPA',
                color='팀',
                title='GPA 순위',
                text_auto='.3f',
                color_discrete_sequence=px.colors.qualitative.Set3
            )
            fig_gpa.update_layout(showlegend=True)
            st.plotly_chart(fig_gpa, use_container_width=True)

# 투수 통계
else:
    st.header("🎯 투수 통계")
    st.info("⚠️ 투수 통계는 아직 수집되지 않았습니다. 타자 통계만 사용 가능합니다.")

# 데이터 정보
st.markdown("---")
if not is_sample and not df_batters.empty:
    st.success(f"✅ KBO 공식 통계 표시 중 (총 {len(df_batters)}명 타자)")
    if '업데이트일시' in df_batters.columns and not df_batters['업데이트일시'].isna().all():
        last_update = df_batters['업데이트일시'].iloc[0]
        st.caption(f"📅 마지막 업데이트: {last_update}")
st.caption("📊 데이터 출처: KBO 공식 웹사이트 (www.koreabaseball.com)")
