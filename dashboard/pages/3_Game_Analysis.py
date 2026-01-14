import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import sqlite3
from pathlib import Path
from datetime import datetime

st.set_page_config(page_title="경기 분석", page_icon="🎯", layout="wide")

st.title("🎯 경기 분석")
st.markdown("---")

DB_PATH = Path(__file__).parent.parent.parent / 'database' / 'kbo_stats.db'

def get_recent_games(limit=50):
    conn = sqlite3.connect(DB_PATH)
    query = f"""
        SELECT g.game_id, g.game_date, 
               t1.team_name as home_team, t2.team_name as away_team, 
               g.home_score, g.away_score, g.stadium
        FROM games g
        JOIN teams t1 ON g.home_team_id = t1.team_id
        JOIN teams t2 ON g.away_team_id = t2.team_id
        ORDER BY g.game_date DESC, g.game_id DESC
        LIMIT {limit}
    """
    df = pd.read_sql_query(query, conn)
    conn.close()
    return df

def get_game_pbp(game_id):
    conn = sqlite3.connect(DB_PATH)
    query = """
        SELECT inning, top_bottom, outs, batter_id, pitcher_id, play_result, play_description, home_score, away_score
        FROM play_by_play
        WHERE game_id = ?
        ORDER BY pbp_id ASC
    """
    df = pd.read_sql_query(query, [game_id], conn)
    conn.close()
    return df

# 데이터 로드
df_recent = get_recent_games()

if df_recent.empty:
    st.warning("데이터베이스에 경기 정보가 없습니다. 먼저 데이터를 수집하고 병합해 주세요.")
else:
    # 경기 선택
    game_options = {f"{row['game_date']} | {row['home_team']} {row['home_score']}:{row['away_score']} {row['away_team']}": row['game_id'] 
                    for _, row in df_recent.iterrows()}
    
    selected_label = st.selectbox("최근 경기 선택", list(game_options.keys()))
    game_id = game_options[selected_label]
    
    # 선택된 경기 정보 상세
    game_info = df_recent[df_recent['game_id'] == game_id].iloc[0]
    
    st.subheader(f"📊 경기 정보: {game_info['game_date']} at {game_info['stadium']}")
    c1, c2, c3 = st.columns(3)
    c1.metric(game_info['home_team'], f"{game_info['home_score']}점")
    c2.metric("vs", "RESULT")
    c3.metric(game_info['away_team'], f"{game_info['away_score']}점")
    
    # 문자중계 로드
    df_pbp = get_game_pbp(game_id)
    
    if not df_pbp.empty:
        # 이닝별 득점 전광판
        st.write("### 🏟️ 스코어보드")
        
        # 간단한 스코어보드 집계
        scoreboard = []
        for inn in sorted(df_pbp['inning'].unique()):
             h_inn_score_max = df_pbp[(df_pbp['inning'] == inn) & (df_pbp['top_bottom'] == '말')]['home_score'].max()
             a_inn_score_max = df_pbp[(df_pbp['inning'] == inn) & (df_pbp['top_bottom'] == '초')]['away_score'].max()
             # 실제로는 이전 이닝 점수와의 차를 구해야 함... 하지만 여기서는 간단히 누적 점수 추이로 표시
        
        st.info("문자중계 데이터를 기반으로 상세 타임라인을 확인하세요.")

        # 문자중계 타임라인
        st.write("### 📝 문자중계 타임라인")
        # 보기 좋게 포맷팅
        df_display = df_pbp.copy()
        df_display['이닝'] = df_display['inning'].astype(str) + "회" + df_display['top_bottom']
        df_display = df_display[['이닝', 'outs', 'play_result', 'play_description', 'home_score', 'away_score']]
        df_display.columns = ['이닝', '아웃', '결과', '상세설명', '홈', '원정']
        
        st.dataframe(df_display, use_container_width=True, hide_index=True)
    else:
        st.info("이 경기에 대한 문자중계 데이터가 없습니다.")

st.caption("데이터 출처: KBO 문자중계")
