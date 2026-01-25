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
            
            # 1행 3열 레이아웃
            col1, col2, col3 = st.columns([1, 1, 1])
            
            # 1열: 선수 사진 + 프로필 + 시즌 성적
            with col1:
                # 선수 사진
                if player['image_url'] and not pd.isna(player['image_url']):
                    st.image(player['image_url'], use_container_width=True)
                else:
                    st.info("이미지 없음")
                
                # 프로필 정보
                st.markdown(f"### {player['player_name']}")
                st.markdown(f"**{player['team_id']}** | No.{int(player['back_number']) if not pd.isna(player['back_number']) else '?'}")
                
                st.markdown("---")
                st.markdown("#### 📋 기본 정보")
                st.write(f"**포지션**: {player['position']}")
                st.write(f"**투타**: {format_throw_bat(player['throw'], player['bat'])}")
                st.write(f"**생년월일**: {format_birthday(player['birthday'])}")
                st.write(f"**신장/체중**: {int(player['height']) if not pd.isna(player['height']) else '?'}cm / {int(player['weight']) if not pd.isna(player['weight']) else '?'}kg")
                
                st.markdown("---")
                st.markdown("#### 💼 계약 정보")
                st.write(f"**입단**: {player['draft_year']} ({player['draft_order']})")
                st.write(f"**계약금**: {format_money(player['signing_bonus'])}")
                st.write(f"**연봉**: {format_money(player['salary'])}")
                
                if player['career'] and not pd.isna(player['career']):
                    st.markdown("---")
                    st.markdown("#### 🏫 경력")
                    st.write(player['career'])
                
                # 시즌 성적
                st.markdown("---")
                st.markdown("#### 📊 2025 시즌 성적")
                
                if not batter_stats.empty:
                    # 타자 성적
                    stats = batter_stats.iloc[0]
                    
                    st.markdown("**타격 성적**")
                    
                    # 주요 지표
                    metric_cols = st.columns(3)
                    with metric_cols[0]:
                        st.metric("타율", f"{stats['batting_average']:.3f}" if not pd.isna(stats['batting_average']) else "-")
                    with metric_cols[1]:
                        st.metric("출루율", f"{stats['on_base_percentage']:.3f}" if not pd.isna(stats['on_base_percentage']) else "-")
                    with metric_cols[2]:
                        st.metric("장타율", f"{stats['slugging_percentage']:.3f}" if not pd.isna(stats['slugging_percentage']) else "-")
                    
                    # 상세 기록
                    st.write(f"**타석**: {int(stats['plate_appearance']) if not pd.isna(stats['plate_appearance']) else '-'}")
                    st.write(f"**타수**: {int(stats['at_bat']) if not pd.isna(stats['at_bat']) else '-'}")
                    st.write(f"**득점**: {int(stats['run']) if not pd.isna(stats['run']) else '-'}")
                    st.write(f"**안타**: {int(stats['hits']) if not pd.isna(stats['hits']) else '-'}")
                    st.write(f"**홈런**: {int(stats['home_run']) if not pd.isna(stats['home_run']) else '-'}")
                    st.write(f"**OPS**: {stats['ops']:.3f}" if not pd.isna(stats['ops']) else "**OPS**: -")
                
                elif not pitcher_stats.empty:
                    # 투수 성적
                    stats = pitcher_stats.iloc[0]
                    
                    st.markdown("**투구 성적**")
                    
                    # 주요 지표
                    metric_cols = st.columns(3)
                    with metric_cols[0]:
                        st.metric("ERA", f"{stats['earned_run_average']:.2f}" if not pd.isna(stats['earned_run_average']) else "-")
                    with metric_cols[1]:
                        st.metric("승", f"{int(stats['wins'])}" if not pd.isna(stats['wins']) else "-")
                    with metric_cols[2]:
                        st.metric("패", f"{int(stats['losses'])}" if not pd.isna(stats['losses']) else "-")
                    
                    # 상세 기록 (승, 패, ERA, G, GS, SV, IP, SO, WHIP)
                    st.write(f"**G (경기)**: {int(stats['games']) if not pd.isna(stats['games']) else '-'}")
                    st.write(f"**GS (선발)**: {int(stats['games_started']) if not pd.isna(stats['games_started']) else '-'}")
                    st.write(f"**SV (세이브)**: {int(stats['save']) if not pd.isna(stats['save']) else '-'}")
                    st.write(f"**IP (이닝)**: {stats['innings_pitched']:.1f}" if not pd.isna(stats['innings_pitched']) else "**IP (이닝)**: -")
                    st.write(f"**SO (탈삼진)**: {int(stats['strikeout']) if not pd.isna(stats['strikeout']) else '-'}")
                    st.write(f"**WHIP**: {stats['whip']:.2f}" if not pd.isna(stats['whip']) else "**WHIP**: -")
                
                else:
                    st.info("2025 시즌 성적이 없습니다.")
            
            # 2열: 비워둠 (추후 확장용)
            with col2:
                st.markdown("### 📈 추가 분석")
                st.info("추후 추가 예정")
            
            # 3열: 비워둠 (추후 확장용)
            with col3:
                st.markdown("### 📊 상세 통계")
                st.info("추후 추가 예정")

else:
    st.info("👆 선수 이름을 검색하세요.")
