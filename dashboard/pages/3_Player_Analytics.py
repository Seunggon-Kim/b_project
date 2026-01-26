import streamlit as st
import sqlite3
import pandas as pd
from pathlib import Path

# 페이지 설정
st.set_page_config(
    page_title="선수 분석",
    page_icon="👤",
    layout="wide"
)

# DB 경로
PROJECT_ROOT = Path(__file__).parent.parent.parent
DB_PATH = PROJECT_ROOT / 'database' / 'kbo_stats.db'


@st.cache_data(ttl=600)
def search_players(query):
    """선수 검색"""
    conn = sqlite3.connect(DB_PATH)
    sql = """
        SELECT 
            player_id,
            player_name,
            team_id,
            back_number,
            position
        FROM players
        WHERE player_name LIKE ?
        ORDER BY player_name
    """
    df = pd.read_sql_query(sql, conn, params=(f'%{query}%',))
    conn.close()
    return df


@st.cache_data(ttl=600)
def get_player_info(player_id):
    """선수 상세 정보"""
    conn = sqlite3.connect(DB_PATH)
    
    # 기본 정보
    player_query = """
        SELECT 
            player_id,
            player_name,
            team_id,
            back_number,
            position,
            throw,
            bat,
            birthday,
            height,
            weight,
            career,
            draft_year,
            draft_order,
            signing_bonus,
            salary,
            image_url
        FROM players
        WHERE player_id = ?
    """
    player_df = pd.read_sql_query(player_query, conn, params=(player_id,))
    
    # 타자 성적 (2025 시즌)
    batter_query = """
        SELECT 
            plate_appearance,
            at_bat,
            run,
            single,
            double,
            triple,
            home_run,
            batting_average,
            on_base_percentage,
            slugging_percentage,
            on_base_plus_slugging as ops
        FROM kbo_official_batter_stats
        WHERE player_id = ? AND season = 2025
    """
    batter_df = pd.read_sql_query(batter_query, conn, params=(player_id,))
    
    # 안타 합계 계산
    if not batter_df.empty:
        batter_df['hits'] = (
            batter_df['single'].fillna(0) + 
            batter_df['double'].fillna(0) + 
            batter_df['triple'].fillna(0) + 
            batter_df['home_run'].fillna(0)
        )
    
    # 투수 성적 (2025 시즌)
    pitcher_query = """
        SELECT 
            wins,
            losses,
            earned_run_average,
            games,
            games_started,
            save,
            innings_pitched,
            strikeout,
            walks_plus_hits_per_inning_pitched as whip
        FROM kbo_official_pitcher_stats
        WHERE player_id = ? AND season = 2025
    """
    pitcher_df = pd.read_sql_query(pitcher_query, conn, params=(player_id,))
    
    conn.close()
    
    return player_df, batter_df, pitcher_df


def format_money(amount):
    """금액 포맷팅"""
    if pd.isna(amount) or amount is None:
        return "-"
    return f"{int(amount):,}원"


def format_throw_bat(throw, bat):
    """투타 포맷팅"""
    throw_map = {'R': '우투', 'L': '좌투', 'S': '양투'}
    bat_map = {'R': '우타', 'L': '좌타', 'S': '양타'}
    
    throw_text = throw_map.get(throw, '-')
    bat_text = bat_map.get(bat, '-')
    
    return f"{throw_text}/{bat_text}"


def format_birthday(birthday):
    """생년월일 포맷팅"""
    if pd.isna(birthday) or not birthday:
        return "-"
    try:
        year = birthday[:4]
        month = birthday[4:6]
        day = birthday[6:8]
        return f"{year}년 {month}월 {day}일"
    except:
        return birthday


# 메인 페이지
st.title("👤 선수 분석")

# 선수 검색
st.header("🔎 선수 검색")
search_query = st.text_input("선수 이름을 입력하세요", placeholder="예: 김현수")

if search_query:
    # 검색 결과
    search_results = search_players(search_query)
    
    if search_results.empty:
        st.warning(f"'{search_query}' 검색 결과가 없습니다.")
    else:
        # 동명이인 처리
        if len(search_results) > 1:
            st.info(f"🔍 {len(search_results)}명의 선수가 검색되었습니다. 선택해주세요.")
            
            # 선수 선택 옵션
            player_options = []
            for _, row in search_results.iterrows():
                option = f"{row['player_name']} ({row['team_id']}) - No.{int(row['back_number']) if not pd.isna(row['back_number']) else '?'} {row['position']}"
                player_options.append(option)
            
            selected_option = st.selectbox("선수 선택", player_options)
            selected_idx = player_options.index(selected_option)
            selected_player_id = search_results.iloc[selected_idx]['player_id']
        else:
            # 단일 결과
            selected_player_id = search_results.iloc[0]['player_id']
        
        # 선수 정보 표시
        st.divider()
        
        player_info, batter_stats, pitcher_stats = get_player_info(selected_player_id)
        
        if not player_info.empty:
            player = player_info.iloc[0]
            
            # 1행: 선수 정보 카드 (전체 너비)
            st.markdown("## 📋 선수 정보")
            
            # 프로필 카드
            col1, col2 = st.columns([1, 3])
            
            with col1:
                # 선수 사진
                if player['image_url'] and not pd.isna(player['image_url']):
                    st.image(player['image_url'], use_container_width=True)
                else:
                    st.info("이미지 없음")
            
            with col2:
                # 선수 이름 및 기본 정보
                st.markdown(f"# {player['player_name']}")
                st.markdown(f"### {player['position']} | {player['team_id']} 🏟️")
                
                # 한 줄 정보
                info_line = f"**투타**: {format_throw_bat(player['throw'], player['bat'])} | **생년월일**: {format_birthday(player['birthday'])} | **신장/체중**: {int(player['height']) if not pd.isna(player['height']) else '?'}cm / {int(player['weight']) if not pd.isna(player['weight']) else '?'}kg | **나이**: "
                
                # 나이 계산
                if player['birthday'] and not pd.isna(player['birthday']):
                    try:
                        birth_year = int(player['birthday'][:4])
                        age = 2025 - birth_year
                        info_line += f"{age}"
                    except:
                        info_line += "?"
                else:
                    info_line += "?"
                
                st.markdown(info_line)
                
                # 입단 및 계약 정보
                draft_info = f"**입단**: {player['draft_year']} | {player['draft_order']}"
                if player['career'] and not pd.isna(player['career']):
                    draft_info += f" | {player['career']}"
                
                st.markdown(draft_info)
                
                # 계약 정보
                contract_info = f"**계약금**: {format_money(player['signing_bonus'])} | **연봉**: {format_money(player['salary'])}"
                st.markdown(contract_info)
            
            st.divider()
            
            # 2행: 시즌별 성적 테이블
            st.markdown("## 📊 시즌별 성적")
            
            # 포지션이 투수면 투수 성적 우선 표시
            is_pitcher = player['position'] == '투수'
            
            if is_pitcher:
                # 투수 성적 - 여러 시즌 조회
                conn = sqlite3.connect(DB_PATH)
                pitcher_query = """
                    SELECT 
                        season,
                        wins,
                        losses,
                        earned_run_average,
                        games,
                        games_started,
                        save,
                        innings_pitched,
                        strikeout,
                        walks_plus_hits_per_inning_pitched as whip
                    FROM kbo_official_pitcher_stats
                    WHERE player_id = ?
                    ORDER BY season DESC
                """
                df_pitcher_seasons = pd.read_sql_query(pitcher_query, conn, params=(player['player_id'],))
                conn.close()
                
                if not df_pitcher_seasons.empty:
                    # 컬럼명 변경
                    df_pitcher_seasons.columns = ['시즌', '승', '패', 'ERA', 'G', 'GS', 'SV', 'IP', 'SO', 'WHIP']
                    
                    # 포맷팅
                    df_pitcher_seasons['ERA'] = df_pitcher_seasons['ERA'].apply(lambda x: f"{x:.2f}" if not pd.isna(x) else "-")
                    df_pitcher_seasons['IP'] = df_pitcher_seasons['IP'].apply(lambda x: f"{float(x):.1f}" if not pd.isna(x) else "-")
                    df_pitcher_seasons['WHIP'] = df_pitcher_seasons['WHIP'].apply(lambda x: f"{x:.2f}" if not pd.isna(x) else "-")
                    
                    # 정수형 컬럼
                    for col in ['승', '패', 'G', 'GS', 'SV', 'SO']:
                        df_pitcher_seasons[col] = df_pitcher_seasons[col].apply(lambda x: int(x) if not pd.isna(x) else "-")
                    
                    st.dataframe(df_pitcher_seasons, hide_index=True, use_container_width=True)
                else:
                    st.info("투수 성적이 없습니다.")
            
            else:
                # 타자 성적 - 여러 시즌 조회
                conn = sqlite3.connect(DB_PATH)
                batter_query = """
                    SELECT 
                        season,
                        plate_appearance,
                        at_bat,
                        run,
                        single + double + triple + home_run as hits,
                        home_run,
                        batting_average,
                        on_base_percentage,
                        slugging_percentage,
                        on_base_plus_slugging as ops
                    FROM kbo_official_batter_stats
                    WHERE player_id = ?
                    ORDER BY season DESC
                """
                df_batter_seasons = pd.read_sql_query(batter_query, conn, params=(player['player_id'],))
                conn.close()
                
                if not df_batter_seasons.empty:
                    # 컬럼명 변경
                    df_batter_seasons.columns = ['시즌', 'PA', 'AB', 'R', 'H', 'HR', 'AVG', 'OBP', 'SLG', 'OPS']
                    
                    # 포맷팅
                    for col in ['AVG', 'OBP', 'SLG', 'OPS']:
                        df_batter_seasons[col] = df_batter_seasons[col].apply(lambda x: f"{x:.3f}" if not pd.isna(x) else "-")
                    
                    # 정수형 컬럼
                    for col in ['PA', 'AB', 'R', 'H', 'HR']:
                        df_batter_seasons[col] = df_batter_seasons[col].apply(lambda x: int(x) if not pd.isna(x) else "-")
                    
                    st.dataframe(df_batter_seasons, hide_index=True, use_container_width=True)
                else:
                    st.info("타자 성적이 없습니다.")
            
            st.divider()
            
            # 3행: 추가 분석
            st.markdown("## 📈 추가 분석")
            st.info("추후 추가 예정")
            
            st.divider()
            
            # 4행: 상세 통계
            st.markdown("## 📊 상세 통계")
            st.info("추후 추가 예정")

else:
    st.info("👆 선수 이름을 검색하세요.")
