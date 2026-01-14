import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import sqlite3
from pathlib import Path

st.set_page_config(page_title="팀 통계", page_icon="📊", layout="wide")

st.title("📊 팀 통계 (2025 시즌)")
st.markdown("---")

# DB 경로 설정
DB_PATH = Path(__file__).parent.parent.parent / 'database' / 'kbo_stats.db'

def get_team_stats(season=2025):
    conn = sqlite3.connect(DB_PATH)
    
    # 경기 데이터 가져오기
    query = f"SELECT home_team_id, away_team_id, home_score, away_score FROM games WHERE season = {season}"
    df_games = pd.read_sql_query(query, conn)
    
    # 팀 목록 가져오기
    cur = conn.cursor()
    cur.execute("SELECT team_id, team_name FROM teams")
    team_map = {row[0]: row[1] for row in cur.fetchall()}
    
    # ID 정규화 (SK -> SSG, HH -> 한화)
    def normalize_team(tid):
        if tid == 'SK': return 'SSG'
        if tid == 'HH': return '한화'
        return tid

    df_games['home_team_id'] = df_games['home_team_id'].apply(normalize_team)
    df_games['away_team_id'] = df_games['away_team_id'].apply(normalize_team)
    
    unique_teams = sorted(list(set(df_games['home_team_id'].unique()) | set(df_games['away_team_id'].unique())))
    
    stats = []
    for team in unique_teams:
        # 해당 팀이 참여한 경기 필터링
        home_games = df_games[df_games['home_team_id'] == team]
        away_games = df_games[df_games['away_team_id'] == team]
        
        wins = 0
        losses = 0
        draws = 0
        runs_for = 0
        runs_against = 0
        
        # 홈 경기 결과
        for _, row in home_games.iterrows():
            runs_for += row['home_score']
            runs_against += row['away_score']
            if row['home_score'] > row['away_score']: wins += 1
            elif row['home_score'] < row['away_score']: losses += 1
            else: draws += 1
            
        # 원정 경기 결과
        for _, row in away_games.iterrows():
            runs_for += row['away_score']
            runs_against += row['home_score']
            if row['away_score'] > row['home_score']: wins += 1
            elif row['away_score'] < row['home_score']: losses += 1
            else: draws += 1
            
        games_played = wins + losses + draws
        win_rate = wins / (wins + losses) if (wins + losses) > 0 else 0
        
        stats.append({
            '팀명': team_map.get(team, team),
            '경기': games_played,
            '승': wins,
            '패': losses,
            '무': draws,
            '승률': win_rate,
            '득점': runs_for,
            '실점': runs_against,
            '득실차': runs_for - runs_against
        })
    
    conn.close()
    return pd.DataFrame(stats).sort_values(by=['승률', '승'], ascending=False)

# 데이터 로드
try:
    df_teams = get_team_stats(2025)
    
    # 팀 순위 테이블
    st.header(f"2025 시즌 팀 순위 (실시간 집계)")
    st.dataframe(
        df_teams.style.format({'승률': '{:.3f}'}),
        use_container_width=True,
        hide_index=True
    )

    # 차트 영역
    col1, col2 = st.columns(2)

    with col1:
        st.subheader("팀별 승률")
        fig_winrate = px.bar(
            df_teams,
            x='팀명',
            y='승률',
            title='팀별 승률 순위',
            color='승률',
            color_continuous_scale='Blues',
            text_auto='.3f'
        )
        st.plotly_chart(fig_winrate, use_container_width=True)

    with col2:
        st.subheader("득실점 비교")
        fig_runs = go.Figure()
        fig_runs.add_trace(go.Bar(name='득점', x=df_teams['팀명'], y=df_teams['득점'], marker_color='blue'))
        fig_runs.add_trace(go.Bar(name='실점', x=df_teams['팀명'], y=df_teams['실점'], marker_color='red'))
        fig_runs.update_layout(barmode='group', title='팀별 득실점 합계')
        st.plotly_chart(fig_runs, use_container_width=True)

    # 상세 선택
    st.markdown("---")
    selected_team = st.selectbox("상세 보고 싶은 팀 선택", df_teams['팀명'].tolist())
    
    t_data = df_teams[df_teams['팀명'] == selected_team].iloc[0]
    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("승", f"{t_data['승']}승")
    c2.metric("패", f"{t_data['패']}패")
    c3.metric("무", f"{t_data['무']}무")
    c4.metric("승률", f"{t_data['승률']:.3f}")
    c5.metric("득실차", f"{t_data['득실차']:+d}")

except Exception as e:
    st.error(f"데이터를 불러오는 중 오류가 발생했습니다: {e}")
    st.info("데이터베이스가 올바른 위치에 있는지 확인해 주세요.")
