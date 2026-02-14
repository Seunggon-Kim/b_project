import streamlit as st
import sqlite3
import pandas as pd
from pathlib import Path

# 페이지 설정
st.set_page_config(
    page_title="선수 분석",
    page_icon="??",
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


def parse_innings(innings_str):
    """이닝 문자열을 숫자로 변환 (예: '52 1/3' -> 52.333)"""
    if pd.isna(innings_str):
        return 0.0
    
    innings_str = str(innings_str).strip()
    
    # 이미 숫자면 그대로 반환
    try:
        return float(innings_str)
    except ValueError:
        pass
    
    # "52 1/3" 형식 처리
    if ' ' in innings_str:
        parts = innings_str.split()
        whole = float(parts[0])
        
        if len(parts) > 1 and '/' in parts[1]:
            frac_parts = parts[1].split('/')
            fraction = float(frac_parts[0]) / float(frac_parts[1])
            return whole + fraction
    
    return 0.0


# 메인 페이지
st.title("?? 선수 분석")

# 선수 검색
st.header("?? 선수 검색")
search_query = st.text_input("선수 이름을 입력하세요", placeholder="예: 김현수")

if search_query:
    # 검색 결과
    search_results = search_players(search_query)
    
    if search_results.empty:
        st.warning(f"'{search_query}' 검색 결과가 없습니다.")
    else:
        # 동명이인 처리
        if len(search_results) > 1:
            st.info(f"?? {len(search_results)}명의 선수가 검색되었습니다. 선택해주세요.")
            
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
            
            # 상단: 사진 + 이름 + 기본 정보
            col1, col2 = st.columns([1, 4])
            
            with col1:
                # 선수 사진 (고정 크기로 해상도 유지)
                if player['image_url'] and not pd.isna(player['image_url']):
                    st.image(player['image_url'], width=200)
                else:
                    st.info("이미지 없음")
            
            with col2:
                # 왼쪽 열: 선수 기본 정보
                left_col, right_col = st.columns(2)
                
                with left_col:
                    st.markdown(f"**선수명:** {player['player_name']}")
                    
                    # 생년월일
                    birth_display = format_birthday(player['birthday'])
                    st.markdown(f"**생년월일:** {birth_display}")
                    
                    # 신장/체중
                    height = f"{int(player['height'])}cm" if not pd.isna(player['height']) else "?"
                    weight = f"{int(player['weight'])}kg" if not pd.isna(player['weight']) else "?"
                    st.markdown(f"**신장/체중:** {height}/{weight}")
                    
                    # 입단 계약금
                    signing = format_money(player['signing_bonus'])
                    st.markdown(f"**입단 계약금:** {signing}")
                    
                    # 지명순위
                    draft_info = "-"
                    if not pd.isna(player['draft_year']) and not pd.isna(player['draft_order']):
                        try:
                            year = int(player['draft_year'])
                            order = int(player['draft_order'])
                            draft_info = f"{year} KIA {order}라운드 {order}순위"
                        except (ValueError, TypeError):
                            # 숫자가 아닌 경우 그대로 표시
                            draft_info = f"{player['draft_year']} {player['draft_order']}"
                    st.markdown(f"**지명순위:** {draft_info}")
                
                with right_col:
                    st.markdown(f"**등번호:** No.{player['back_number'] if not pd.isna(player['back_number']) else '?'}")
                    
                    # 포지션
                    st.markdown(f"**포지션:** {player['position']}")
                    
                    # 경력
                    career_display = player['career'] if not pd.isna(player['career']) else "-"
                    st.markdown(f"**경력:** {career_display}")
                    
                    # 연봉
                    salary_display = format_money(player['salary'])
                    st.markdown(f"**연봉:** {salary_display}")
                    
                    # 입단연도
                    draft_year = "-"
                    if not pd.isna(player['draft_year']):
                        try:
                            draft_year = f"{int(player['draft_year'])}KIA"
                        except (ValueError, TypeError):
                            # 이미 팀명이 포함된 경우 (예: "24SSG")
                            draft_year = str(player['draft_year'])
                    st.markdown(f"**입단연도:** {draft_year}")
            
            st.divider()
            
            # 하단: 3열 레이아웃
            col1, col2, col3 = st.columns([1, 1, 1])
            
            # 1열: 2025 성적
            with col1:
                st.markdown("### ?? Quick Look")
                
                # 포지션이 투수면 투수 성적 우선 표시
                is_pitcher = player['position'] == '투수'
                
                if is_pitcher and not pitcher_stats.empty:
                    # 투수 성적 테이블
                    stats = pitcher_stats.iloc[0]
                    
                    pitcher_data = {
                        '항목': ['ERA', '승', '패', 'G', 'GS', 'SV', 'IP', 'SO', 'WHIP'],
                        '2025': [
                            f"{stats['earned_run_average']:.2f}" if not pd.isna(stats['earned_run_average']) else "-",
                            f"{int(stats['wins'])}" if not pd.isna(stats['wins']) else "-",
                            f"{int(stats['losses'])}" if not pd.isna(stats['losses']) else "-",
                            f"{int(stats['games'])}" if not pd.isna(stats['games']) else "-",
                            f"{int(stats['games_started'])}" if not pd.isna(stats['games_started']) else "-",
                            f"{int(stats['save'])}" if not pd.isna(stats['save']) else "-",
                            f"{parse_innings(stats['innings_pitched']):.1f}" if not pd.isna(stats['innings_pitched']) else "-",
                            f"{int(stats['strikeout'])}" if not pd.isna(stats['strikeout']) else "-",
                            f"{stats['whip']:.2f}" if not pd.isna(stats['whip']) else "-"
                        ]
                    }
                    
                    df_pitcher = pd.DataFrame(pitcher_data)
                    st.dataframe(df_pitcher, hide_index=True, use_container_width=True)
                
                elif not batter_stats.empty:
                    # 타자 성적 테이블
                    stats = batter_stats.iloc[0]
                    
                    batter_data = {
                        '항목': ['AVG', 'OBP', 'SLG', 'OPS', 'PA', 'AB', 'R', 'H', 'HR'],
                        '2025': [
                            f"{stats['batting_average']:.3f}" if not pd.isna(stats['batting_average']) else "-",
                            f"{stats['on_base_percentage']:.3f}" if not pd.isna(stats['on_base_percentage']) else "-",
                            f"{stats['slugging_percentage']:.3f}" if not pd.isna(stats['slugging_percentage']) else "-",
                            f"{stats['ops']:.3f}" if not pd.isna(stats['ops']) else "-",
                            f"{int(stats['plate_appearance'])}" if not pd.isna(stats['plate_appearance']) else "-",
                            f"{int(stats['at_bat'])}" if not pd.isna(stats['at_bat']) else "-",
                            f"{int(stats['run'])}" if not pd.isna(stats['run']) else "-",
                            f"{int(stats['hits'])}" if not pd.isna(stats['hits']) else "-",
                            f"{int(stats['home_run'])}" if not pd.isna(stats['home_run']) else "-"
                        ]
                    }
                    
                    df_batter = pd.DataFrame(batter_data)
                    st.dataframe(df_batter, hide_index=True, use_container_width=True)
                
                else:
                    st.info("2025 시즌 성적이 없습니다.")
            
            # 2열: 경력 정보
            with col2:
                st.markdown("### ?? Roster Resource")
                
                st.markdown(f"**입단**: {player['draft_year']}")
                st.markdown(f"**지명**: {player['draft_order']}")
                
                if player['career'] and not pd.isna(player['career']):
                    st.markdown(f"**경력**: {player['career']}")
                
                st.markdown("---")
                st.markdown(f"**계약금**: {format_money(player['signing_bonus'])}")
                st.markdown(f"**연봉**: {format_money(player['salary'])}")
            
            # 3열: 비어있음
            with col3:
                st.markdown("### ?? News")
                st.info("추후 추가 예정")
            
            st.divider()
            
            # 시즌별 성적 테이블
            st.markdown("## ?? 시즌별 성적")
            
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
                    df_pitcher_seasons.columns = ['Season', 'W', 'L', 'ERA', 'G', 'GS', 'SV', 'IP', 'SO', 'WHIP']
                    
                    # 포맷팅
                    df_pitcher_seasons['ERA'] = df_pitcher_seasons['ERA'].apply(lambda x: f"{x:.2f}" if not pd.isna(x) else "-")
                    df_pitcher_seasons['IP'] = df_pitcher_seasons['IP'].apply(lambda x: f"{float(x):.1f}" if not pd.isna(x) else "-")
                    df_pitcher_seasons['WHIP'] = df_pitcher_seasons['WHIP'].apply(lambda x: f"{x:.2f}" if not pd.isna(x) else "-")
                    
                    # 정수형 컬럼
                    for col in ['W', 'L', 'G', 'GS', 'SV', 'SO']:
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
                    df_batter_seasons.columns = ['Season', 'PA', 'AB', 'R', 'H', 'HR', 'AVG', 'OBP', 'SLG', 'OPS']
                    
                    # 포맷팅
                    for col in ['AVG', 'OBP', 'SLG', 'OPS']:
                        df_batter_seasons[col] = df_batter_seasons[col].apply(lambda x: f"{x:.3f}" if not pd.isna(x) else "-")
                    
                    # 정수형 컬럼
                    for col in ['PA', 'AB', 'R', 'H', 'HR']:
                        df_batter_seasons[col] = df_batter_seasons[col].apply(lambda x: int(x) if not pd.isna(x) else "-")
                    
                    st.dataframe(df_batter_seasons, hide_index=True, use_container_width=True)
                else:
                    st.info("타자 성적이 없습니다.")

else:
    st.info("?? 선수 이름을 검색하세요.")
