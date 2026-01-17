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
    
    # KBO 공식 타자 데이터 로드 (전체 스키마, 최신 시즌만)
    try:
        # 최신 시즌 조회
        max_season_df = pd.read_sql_query("SELECT MAX(season) as max_season FROM kbo_official_batter_stats", conn)
        max_season = max_season_df['max_season'].iloc[0] if not max_season_df.empty else datetime.now().year
        
        df_batters = pd.read_sql_query(f"""
            SELECT 
                player_id,
                season AS 시즌,
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
            WHERE season = {max_season}
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
        
    # KBO 공식 투수 데이터 로드 (전체 스키마, 최신 시즌만)
    try:
        # 최신 시즌 조회
        max_season_df_p = pd.read_sql_query("SELECT MAX(season) as max_season FROM kbo_official_pitcher_stats", conn)
        max_season_p = max_season_df_p['max_season'].iloc[0] if not max_season_df_p.empty else datetime.now().year
        
        df_pitchers = pd.read_sql_query(f"""
            SELECT 
                player_id,
                season AS 시즌,
                player_name AS 선수명,
                player_team AS 팀,
                earned_run_average AS 평균자책점,
                games AS 경기수,
                wins AS 승,
                losses AS 패,
                save AS 세이브,
                hold AS 홀드,
                winning_percentage AS 승률,
                innings_pitched AS 이닝,
                hits AS 피안타,
                home_run AS 피홈런,
                base_on_balls AS 볼넷,
                hit_by_pitch AS 몸에맞는볼,
                strikeout AS 삼진,
                run AS 실점,
                earned_run AS 자책점,
                walks_plus_hits_per_inning_pitched AS WHIP,
                complete_game AS 완투,
                shutout AS 완봉,
                quality_start AS QS,
                blown_save AS 블론세이브,
                total_batters_faced AS 타자,
                number_of_pitchers AS 투구수,
                batting_average AS 피안타율,
                games_started AS 선발,
                wins_game_started AS 선발승,
                wins_game_relieved AS 구원승,
                games_finished AS 마무리,
                save_opportunity AS 세이브기회,
                total_saves AS 세이브홀드,
                k_9 AS K9,
                bb_9 AS BB9,
                on_base_percentage AS 피출루율,
                slugging_percentage AS 피장타율,
                on_base_plus_slugging AS 피OPS,
                created_at AS 등록일시,
                updated_at AS 업데이트일시
            FROM kbo_official_pitcher_stats 
            WHERE season = {max_season_p}
            ORDER BY 평균자책점 ASC
        """, conn)
    except Exception as e:
        st.error(f"투수 데이터 로드 실패: {e}")
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
    st.header("🎯 투수 통계 (KBO 공식)")
    
    if df_pitchers.empty:
        st.info("⚠️ 투수 통계가 없습니다. 크롤링을 먼저 실행하세요.")
        st.code("""
# 투수 크롤링 실행
py data_collection\\selenium_pitcher_scraper.py

# DB 저장
py data_collection\\pitcher_to_db.py
        """)
    else:
        # 필터
        col1, col2, col3 = st.columns(3)
        
        with col1:
            # 팀 필터
            teams = ['전체'] + sorted(df_pitchers['팀'].unique().tolist())
            selected_team = st.selectbox("팀 선택", teams)
        
        with col2:
            # 최소 이닝 필터
            min_ip = st.number_input("최소 이닝", min_value=0.0, value=10.0, step=5.0)
        
        with col3:
            # 선수 검색
            search_query = st.text_input("선수 이름 검색", placeholder="선수 이름을 입력하세요...")
        
        # 필터 적용
        df_display = df_pitchers.copy()
        
        if selected_team != '전체':
            df_display = df_display[df_display['팀'] == selected_team]
        
        # 이닝 문자열을 숫자로 변환 (예: "180 2/3" -> 180.67)
        def parse_innings(ip_str):
            if pd.isna(ip_str) or ip_str == '':
                return 0.0
            try:
                ip_str = str(ip_str).strip()
                if '/' in ip_str:
                    parts = ip_str.split()
                    whole = float(parts[0]) if parts[0] else 0
                    if len(parts) > 1 and '/' in parts[1]:
                        frac_parts = parts[1].split('/')
                        fraction = float(frac_parts[0]) / float(frac_parts[1])
                        return whole + fraction
                    return whole
                return float(ip_str)
            except:
                return 0.0
        
        df_display['이닝_숫자'] = df_display['이닝'].apply(parse_innings)
        
        if min_ip > 0:
            df_display = df_display[df_display['이닝_숫자'] >= min_ip]
        
        if search_query:
            df_display = df_display[df_display['선수명'].str.contains(search_query, case=False, na=False)]
        
        # 통계 요약
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("총 선수", f"{len(df_display)}명")
        with col2:
            if not df_display.empty:
                st.metric("평균 ERA", f"{df_display['평균자책점'].mean():.2f}")
        with col3:
            if not df_display.empty:
                st.metric("총 승", f"{df_display['승'].sum():.0f}승")
        with col4:
            if not df_display.empty:
                st.metric("총 세이브", f"{df_display['세이브'].sum():.0f}개")
        
        st.markdown("---")
        
        # 통계 테이블
        st.subheader("📊 투수 순위")
        
        # 표시할 컬럼 선택
        display_columns = ['선수명', '팀', '평균자책점', '경기수', '승', '패', '세이브', '홀드', '이닝', '삼진', 'WHIP', 'K9']
        
        st.dataframe(
            df_display[display_columns],
            use_container_width=True,
            hide_index=True,
            column_config={
                "평균자책점": st.column_config.NumberColumn(format="%.2f"),
                "WHIP": st.column_config.NumberColumn(format="%.2f"),
                "K9": st.column_config.NumberColumn(format="%.2f"),
            }
        )
        
        # 상세 정보 보기
        with st.expander("🔍 전체 컬럼 보기"):
            st.dataframe(df_display.drop(columns=['이닝_숫자']), use_container_width=True, hide_index=True)
        
        # 차트
        if not df_display.empty and len(df_display) > 0:
            st.markdown("---")
            st.subheader("📈 통계 차트")
            
            col1, col2 = st.columns(2)
            
            with col1:
                st.subheader("ERA 상위 10명 (낮은 순)")
                df_chart = df_display.sort_values('평균자책점', ascending=True).head(10)
                
                fig_era = px.bar(
                    df_chart,
                    x='선수명',
                    y='평균자책점',
                    color='팀',
                    title='평균자책점 순위',
                    text_auto='.2f',
                    color_discrete_sequence=px.colors.qualitative.Set3
                )
                fig_era.update_layout(showlegend=True)
                st.plotly_chart(fig_era, use_container_width=True)
            
            with col2:
                st.subheader("승수 상위 10명")
                df_wins = df_display.sort_values('승', ascending=False).head(10)
                fig_wins = px.bar(
                    df_wins,
                    x='선수명',
                    y='승',
                    color='팀',
                    title='승수 순위',
                    text_auto=True,
                    color_discrete_sequence=px.colors.qualitative.Set3
                )
                fig_wins.update_layout(showlegend=True)
                st.plotly_chart(fig_wins, use_container_width=True)
            
            col3, col4 = st.columns(2)
            
            with col3:
                st.subheader("세이브 상위 10명")
                df_saves = df_display.sort_values('세이브', ascending=False).head(10)
                fig_saves = px.bar(
                    df_saves,
                    x='선수명',
                    y='세이브',
                    color='팀',
                    title='세이브 순위',
                    text_auto=True,
                    color_discrete_sequence=px.colors.qualitative.Set3
                )
                fig_saves.update_layout(showlegend=True)
                st.plotly_chart(fig_saves, use_container_width=True)
            
            with col4:
                st.subheader("삼진 상위 10명")
                df_k = df_display.sort_values('삼진', ascending=False).head(10)
                fig_k = px.bar(
                    df_k,
                    x='선수명',
                    y='삼진',
                    color='팀',
                    title='삼진 순위',
                    text_auto=True,
                    color_discrete_sequence=px.colors.qualitative.Set3
                )
                fig_k.update_layout(showlegend=True)
                st.plotly_chart(fig_k, use_container_width=True)

# 데이터 정보
st.markdown("---")
if not is_sample:
    if player_type == "타자" and not df_batters.empty:
        st.success(f"✅ KBO 공식 통계 표시 중 (총 {len(df_batters)}명 타자)")
    elif player_type == "투수" and not df_pitchers.empty:
        st.success(f"✅ KBO 공식 통계 표시 중 (총 {len(df_pitchers)}명 투수)")
    if '업데이트일시' in df_batters.columns and not df_batters['업데이트일시'].isna().all():
        last_update = df_batters['업데이트일시'].iloc[0]
        st.caption(f"📅 마지막 업데이트: {last_update}")
st.caption("📊 데이터 출처: KBO 공식 웹사이트 (www.koreabaseball.com)")
