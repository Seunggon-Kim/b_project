"""
선수 통계 페이지
KBO 공식 통계 표시
"""
import streamlit as st
import pandas as pd
import sqlite3
from pathlib import Path

st.set_page_config(page_title="선수 통계", page_icon="👤", layout="wide")

# CSS: multiselect의 선택된 항목 태그 숨기기
st.markdown("""
<style>
    /* multiselect 선택된 항목 숨기기 */
    [data-baseweb="tag"] {
        display: none !important;
    }
    /* multiselect 컨테이너 높이 조정 */
    div[data-baseweb="select"] > div {
        min-height: 38px !important;
    }
</style>
""", unsafe_allow_html=True)

st.title("👤 선수 통계")
st.markdown("---")

# DB 경로
DB_PATH = Path(__file__).parent.parent.parent / 'database' / 'kbo_stats.db'

# 기본 선수 타입 (세션 상태로 관리)
if 'player_type' not in st.session_state:
    st.session_state['player_type'] = '타자'

player_type = st.session_state['player_type']

# 데이터 로드
@st.cache_data
def load_batter_data():
    """타자 데이터 로드"""
    if not DB_PATH.exists():
        return pd.DataFrame()
    
    conn = sqlite3.connect(DB_PATH)
    
    try:
        df = pd.read_sql_query("""
            SELECT 
                player_id,
                season,
                player_name,
                player_team,
                games,
                plate_appearance,
                at_bat,
                run,
                single,
                double,
                triple,
                home_run,
                total_bases,
                run_batted_in,
                sacrifice_bunts,
                sacrifice_fly,
                base_on_balls,
                intentional_base_on_balls,
                hit_by_pitch,
                strikeout,
                ground_into_double_play,
                batting_average,
                slugging_percentage,
                on_base_percentage,
                on_base_plus_slugging,
                multi_hits,
                runners_in_scoring_position,
                pinch_hit_batting_average,
                extra_base_hits,
                ground_outs,
                air_outs,
                go_ao,
                gw_rbi,
                strikeout_per_pa,
                base_on_balls_per_pa,
                bb_k,
                p_pa,
                isop,
                extended_runs,
                gross_production_average
            FROM kbo_official_batter_stats
            ORDER BY season DESC, batting_average DESC
        """, conn)
        conn.close()
        return df
    except Exception as e:
        conn.close()
        st.error(f"타자 데이터 로드 실패: {e}")
        return pd.DataFrame()

@st.cache_data
def load_pitcher_data():
    """투수 데이터 로드"""
    if not DB_PATH.exists():
        return pd.DataFrame()
    
    conn = sqlite3.connect(DB_PATH)
    
    try:
        df = pd.read_sql_query("""
            SELECT 
                player_id,
                season,
                player_name,
                player_team,
                games,
                wins,
                losses,
                save,
                hold,
                winning_percentage,
                innings_pitched,
                hits,
                home_run,
                base_on_balls,
                hit_by_pitch,
                strikeout,
                run,
                earned_run,
                earned_run_average,
                walks_plus_hits_per_inning_pitched,
                complete_game,
                shutout,
                quality_start,
                blown_save,
                total_batters_faced,
                number_of_pitchers,
                batting_average,
                games_started,
                wins_game_started,
                wins_game_relieved,
                games_finished,
                save_opportunity,
                total_saves,
                k_9,
                bb_9,
                strikeout_per_pa,
                base_on_balls_per_pa,
                on_base_percentage,
                slugging_percentage,
                on_base_plus_slugging
            FROM kbo_official_pitcher_stats
            ORDER BY season DESC, earned_run_average ASC
        """, conn)
        conn.close()
        return df
    except Exception as e:
        conn.close()
        st.error(f"투수 데이터 로드 실패: {e}")
        return pd.DataFrame()

# 타자 통계
if player_type == "타자":
    st.header("⚾ 타자 통계")
    
    df_batters = load_batter_data()
    
    if df_batters.empty:
        st.warning("⚠️ 타자 데이터가 없습니다. 크롤링을 먼저 실행하세요.")
        st.code("""
# 타자 크롤링
python data_collection/selenium_batter_scraper.py
python data_collection/kbo_to_db.py
        """)
        st.stop()
    
    # 드롭다운 4개 (선수 타입 + 연도 + 타석 + 컬럼)
    col0, col1, col2, col3 = st.columns(4)
    
    with col0:
        # 0. 선수 타입 선택
        def update_player_type_batter():
            st.session_state['player_type'] = st.session_state['player_type_batter'].replace("⚾ ", "").replace("🎯 ", "")

        st.selectbox(
            "👤 선수 타입",
            options=["⚾ 타자", "🎯 투수"],
            index=0 if player_type == "타자" else 1,
            key="player_type_batter",
            on_change=update_player_type_batter
        )
    
    with col1:
        # 1. 연도 선택
        available_seasons = sorted(df_batters['season'].unique(), reverse=True)
        selected_season = st.selectbox(
            "📅 시즌 선택",
            options=available_seasons,
            index=0
        )
    
    with col2:
        # 2. 타석 선택
        pa_options = {
            "규정타석 (446+ 이상)": 446,
            "10타석 이상": 10,
            "25타석 이상": 25,
            "50타석 이상": 50,
            "75타석 이상": 75,
            "100타석 이상": 100,
            "150타석 이상": 150,
            "200타석 이상": 200,
            "250타석 이상": 250,
            "300타석 이상": 300,
            "350타석 이상": 350,
            "400타석 이상": 400,
            "500타석 이상": 500
        }
        selected_pa_label = st.selectbox(
            "🎯 타석 기준",
            options=list(pa_options.keys()),
            index=0
        )
        selected_pa = pa_options[selected_pa_label]
    
    with col3:
        # 3. 컬럼 선택
        all_columns = {
            'player_name': '선수명',
            'player_team': '팀',
            'games': '경기',
            'plate_appearance': '타석',
            'at_bat': '타수',
            'run': '득점',
            'single': '안타',
            'double': '2루타',
            'triple': '3루타',
            'home_run': '홈런',
            'total_bases': '루타',
            'run_batted_in': '타점',
            'sacrifice_bunts': '희생번트',
            'sacrifice_fly': '희생플라이',
            'base_on_balls': '볼넷',
            'intentional_base_on_balls': '고의4구',
            'hit_by_pitch': '몸에맞는볼',
            'strikeout': '삼진',
            'ground_into_double_play': '병살타',
            'batting_average': '타율',
            'slugging_percentage': '장타율',
            'on_base_percentage': '출루율',
            'on_base_plus_slugging': 'OPS',
            'multi_hits': '멀티히트',
            'runners_in_scoring_position': '득점권타율',
            'pinch_hit_batting_average': '대타타율',
            'extra_base_hits': '장타',
            'ground_outs': '땅볼아웃',
            'air_outs': '뜬공아웃',
            'go_ao': '땅뜬비율',
            'gw_rbi': '결승타',
            'strikeout_per_pa': 'K%',
            'base_on_balls_per_pa': 'BB%',
            'bb_k': '볼삼비율',
            'p_pa': '타석당투구수',
            'isop': 'ISOP',
            'extended_runs': 'XR',
            'gross_production_average': 'GPA'
        }
        
        # 기본 표시 컬럼
        default_columns = [
            'player_name', 'player_team', 'games', 'plate_appearance', 
            'home_run', 'run', 'run_batted_in', 'isop', 
            'batting_average', 'on_base_percentage', 'strikeout_per_pa', 'base_on_balls_per_pa',
            'slugging_percentage', 'on_base_plus_slugging'
        ]
        
        # 컬럼 선택 개수 반영
        num_selected = len(st.session_state.get('batter_cols', default_columns))
        
        # 컬럼 선택
        selected_columns = st.multiselect(
            f"📊 표시 컬럼 ({num_selected}개)",
            options=list(all_columns.keys()),
            default=default_columns,
            format_func=lambda x: all_columns[x],
            key="batter_cols"
        )
    
    # 필터 적용
    df_filtered = df_batters[df_batters['season'] == selected_season].copy()
    df_filtered = df_filtered[df_filtered['plate_appearance'] >= selected_pa]
    
    # 기본 정렬 (타율 내림차순)
    df_filtered = df_filtered.sort_values(by='batting_average', ascending=False).reset_index(drop=True)
    
    # 선수명은 항상 첫 번째 컬럼
    if 'player_name' not in selected_columns:
        selected_columns = ['player_name'] + selected_columns
    

    st.markdown("---")
    
    # 테이블 표시
    st.subheader(f"📊 {selected_season} 시즌 타자 통계 - {selected_pa_label}")
    
    if df_filtered.empty:
        st.info(f"⚠️ {selected_pa_label} 기준을 충족하는 선수가 없습니다.")
    else:
        # 시즌 컬럼 추가
        display_cols = selected_columns.copy()
            
        # 선수명 바로 다음에 season 추가
        if 'player_name' in display_cols and 'season' not in display_cols:
            name_idx = display_cols.index('player_name')
            display_cols.insert(name_idx + 1, 'season')
        
        # 컬럼명 변경
        df_display = df_filtered[display_cols].copy()
        col_names = []
        for col in display_cols:
            if col == 'season':
                col_names.append('시즌')
            elif col == 'rank':
                col_names.append('순위')
            else:
                col_names.append(all_columns.get(col, col))
        df_display.columns = col_names
        
        # 숫자 포맷 설정
        column_config = {}
        for col in df_display.columns:
            if col in ['타율', '장타율', '출루율', 'OPS', 'ISOP', 'GPA', '득점권타율', '대타타율']:
                column_config[col] = st.column_config.NumberColumn(format="%.3f")
            elif col in ['K%', 'BB%']:
                column_config[col] = st.column_config.NumberColumn(format="%.1f%%")
            elif col in ['타석당투구수']:
                column_config[col] = st.column_config.NumberColumn(format="%.2f")
        
        st.dataframe(
            df_display,
            use_container_width=True,
            hide_index=True,
            column_config=column_config,
            height=600
        )

# 투수 통계
else:
    st.header("🎯 투수 통계")
    
    df_pitchers = load_pitcher_data()
    
    if df_pitchers.empty:
        st.warning("⚠️ 투수 데이터가 없습니다. 크롤링을 먼저 실행하세요.")
        st.code("""
# 투수 크롤링
python data_collection/selenium_pitcher_scraper.py
python data_collection/pitcher_to_db.py
        """)
        st.stop()
    
    # 드롭다운 4개 (선수 타입 + 연도 + 이닝 + 컬럼)
    col0, col1, col2, col3 = st.columns(4)
    
    with col0:
        # 0. 선수 타입 선택
        def update_player_type_pitcher():
            st.session_state['player_type'] = st.session_state['player_type_pitcher'].replace("⚾ ", "").replace("🎯 ", "")

        st.selectbox(
            "👤 선수 타입",
            options=["⚾ 타자", "🎯 투수"],
            index=0 if player_type == "타자" else 1,
            key="player_type_pitcher",
            on_change=update_player_type_pitcher
        )
    
    with col1:
        # 1. 연도 선택
        available_seasons = sorted(df_pitchers['season'].unique(), reverse=True)
        selected_season = st.selectbox(
            "📅 시즌 선택",
            options=available_seasons,
            index=0
        )
    
    with col2:
        # 2. 이닝 선택 (투수는 이닝 기준)
        ip_options = {
            "규정이닝 (144+ 이상)": 144,
            "10이닝 이상": 10,
            "25이닝 이상": 25,
            "50이닝 이상": 50,
            "75이닝 이상": 75,
            "100이닝 이상": 100,
            "150이닝 이상": 150
        }
        selected_ip_label = st.selectbox(
            "🎯 이닝 기준",
            options=list(ip_options.keys()),
            index=0
        )
        selected_ip = ip_options[selected_ip_label]
    
    with col3:
        # 3. 컬럼 선택
        all_columns = {
            'player_name': '선수명',
            'player_team': '팀',
            'games': '경기',
            'wins': '승',
            'losses': '패',
            'save': '세이브',
            'hold': '홀드',
            'winning_percentage': '승률',
            'innings_pitched': '이닝',
            'hits': '피안타',
            'home_run': '피홈런',
            'base_on_balls': '볼넷',
            'hit_by_pitch': '몸에맞는볼',
            'strikeout': '삼진',
            'run': '실점',
            'earned_run': '자책점',
            'earned_run_average': '평균자책점',
            'walks_plus_hits_per_inning_pitched': 'WHIP',
            'complete_game': '완투',
            'shutout': '완봉',
            'quality_start': 'QS',
            'blown_save': '블론세이브',
            'total_batters_faced': '타자',
            'number_of_pitchers': '투구수',
            'batting_average': '피안타율',
            'games_started': '선발',
            'wins_game_started': '선발승',
            'wins_game_relieved': '구원승',
            'games_finished': '마무리',
            'save_opportunity': '세이브기회',
            'total_saves': '세이브홀드',
            'k_9': 'K/9',
            'bb_9': 'BB/9',
            'strikeout_per_pa': 'K%',
            'base_on_balls_per_pa': 'BB%',
            'on_base_percentage': '피출루율',
            'slugging_percentage': '피장타율',
            'on_base_plus_slugging': '피OPS'
        }
        
        # 기본 표시 컬럼
        default_columns = [
            'player_name', 'player_team', 'games', 'innings_pitched',
            'wins', 'losses', 'save', 'earned_run_average',
            'walks_plus_hits_per_inning_pitched', 'strikeout', 'k_9', 'strikeout_per_pa', 'base_on_balls_per_pa'
        ]
        
        # 컬럼 선택 개수 반영
        num_selected = len(st.session_state.get('pitcher_cols', default_columns))
        
        # 컬럼 선택
        selected_columns = st.multiselect(
            f"📊 표시 컬럼 ({num_selected}개)",
            options=list(all_columns.keys()),
            default=default_columns,
            format_func=lambda x: all_columns[x],
            key="pitcher_cols"
        )
    
    # 이닝 파싱 함수
    def parse_innings(ip_str):
        """이닝 문자열을 숫자로 변환 (예: '180 2/3' -> 180.67)"""
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
    
    # 필터 적용
    df_filtered = df_pitchers[df_pitchers['season'] == selected_season].copy()
    df_filtered['innings_numeric'] = df_filtered['innings_pitched'].apply(parse_innings)
    df_filtered = df_filtered[df_filtered['innings_numeric'] >= selected_ip]
    
    # 기본 정렬 (ERA 오름차순)
    df_filtered = df_filtered.sort_values(by='earned_run_average', ascending=True).reset_index(drop=True)
    
    # 선수명은 항상 첫 번째 컬럼
    if 'player_name' not in selected_columns:
        selected_columns = ['player_name'] + selected_columns
    
    st.markdown("---")
    
    # 테이블 표시
    st.subheader(f"📊 {selected_season} 시즌 투수 통계 - {selected_ip_label}")
    
    if df_filtered.empty:
        st.info(f"⚠️ {selected_ip_label} 기준을 충족하는 선수가 없습니다.")
    else:
        # 시즌 컬럼 추가
        display_cols = selected_columns.copy()
            
        # 선수명 바로 다음에 season 추가
        if 'player_name' in display_cols and 'season' not in display_cols:
            name_idx = display_cols.index('player_name')
            display_cols.insert(name_idx + 1, 'season')
        
        # 컬럼명 변경
        df_display = df_filtered[display_cols].copy()
        col_names = []
        for col in display_cols:
            if col == 'season':
                col_names.append('시즌')
            else:
                col_names.append(all_columns.get(col, col))
        df_display.columns = col_names
        
        # 숫자 포맷 설정
        column_config = {}
        for col in df_display.columns:
            if col in ['평균자책점', 'WHIP', 'K/9', 'BB/9', '승률', '피안타율', '피출루율', '피장타율', '피OPS']:
                column_config[col] = st.column_config.NumberColumn(format="%.2f")
            elif col in ['K%', 'BB%']:
                column_config[col] = st.column_config.NumberColumn(format="%.1f%%")
        
        st.dataframe(
            df_display,
            use_container_width=True,
            hide_index=True,
            column_config=column_config,
            height=600
        )

# 푸터
st.markdown("---")
st.caption("📊 데이터 출처: KBO 공식 웹사이트 (www.koreabaseball.com)")
