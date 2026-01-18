"""
팀 통계 페이지 - 연도별 팀 순위 및 기록
"""
import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import sqlite3
from pathlib import Path

st.set_page_config(page_title="팀 통계", page_icon="📊", layout="wide")

# DB 경로 설정
DB_PATH = Path(__file__).parent.parent.parent / 'database' / 'kbo_stats.db'

# 타이틀
st.title("📊 팀 통계")
st.markdown("---")

# 시즌 선택
conn = sqlite3.connect(DB_PATH)
cur = conn.cursor()
cur.execute("SELECT DISTINCT season FROM games ORDER BY season DESC")
available_seasons = [row[0] for row in cur.fetchall()]
conn.close()

if not available_seasons:
    st.warning("⚠️ 데이터베이스에 경기 데이터가 없습니다.")
    st.info("먼저 데이터를 수집해주세요.")
    st.stop()

# 시즌 선택 드롭다운
selected_season = st.selectbox(
    "📅 시즌 선택",
    options=available_seasons,
    index=0,
    help="분석할 시즌을 선택하세요"
)

st.markdown(f"### {selected_season} 시즌 팀 통계")
st.markdown("---")


def get_team_stats(season):
    """선택한 시즌의 팀 통계 계산"""
    conn = sqlite3.connect(DB_PATH)
    
    # 경기 데이터 가져오기
    query = f"SELECT home_team_id, away_team_id, home_score, away_score FROM games WHERE season = {season}"
    df_games = pd.read_sql_query(query, conn)
    
    # 팀 목록 가져오기
    cur = conn.cursor()
    cur.execute("SELECT team_id, team_name FROM teams")
    team_map = {row[0]: row[1] for row in cur.fetchall()}
    
    conn.close()
    
    if df_games.empty:
        return None, team_map
    
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
        home_wins = 0
        away_wins = 0
        
        # 홈 경기 결과
        for _, row in home_games.iterrows():
            runs_for += row['home_score']
            runs_against += row['away_score']
            if row['home_score'] > row['away_score']:
                wins += 1
                home_wins += 1
            elif row['home_score'] < row['away_score']:
                losses += 1
            else:
                draws += 1
        
        # 원정 경기 결과
        for _, row in away_games.iterrows():
            runs_for += row['away_score']
            runs_against += row['home_score']
            if row['away_score'] > row['home_score']:
                wins += 1
                away_wins += 1
            elif row['away_score'] < row['home_score']:
                losses += 1
            else:
                draws += 1
        
        games_played = wins + losses + draws
        win_rate = wins / (wins + losses) if (wins + losses) > 0 else 0
        avg_runs_for = runs_for / games_played if games_played > 0 else 0
        avg_runs_against = runs_against / games_played if games_played > 0 else 0
        
        stats.append({
            '순위': 0,  # 나중에 계산
            '팀명': team_map.get(team, team),
            '경기': games_played,
            '승': wins,
            '패': losses,
            '무': draws,
            '승률': win_rate,
            '게임차': 0.0,  # 나중에 계산
            '득점': runs_for,
            '실점': runs_against,
            '득실차': runs_for - runs_against,
            '평균득점': avg_runs_for,
            '평균실점': avg_runs_against,
            '홈승': home_wins,
            '원정승': away_wins
        })
    
    df_stats = pd.DataFrame(stats).sort_values(by=['승률', '승'], ascending=False).reset_index(drop=True)
    
    # 순위 계산
    df_stats['순위'] = range(1, len(df_stats) + 1)
    
    # 게임차 계산 (1위 팀 기준)
    if len(df_stats) > 0:
        first_wins = df_stats.iloc[0]['승']
        first_losses = df_stats.iloc[0]['패']
        
        for idx, row in df_stats.iterrows():
            if idx == 0:
                df_stats.at[idx, '게임차'] = 0.0
            else:
                gb = ((first_wins - row['승']) + (row['패'] - first_losses)) / 2
                df_stats.at[idx, '게임차'] = gb
    
    return df_stats, team_map


# 데이터 로드
try:
    df_teams, team_map = get_team_stats(selected_season)
    
    if df_teams is None or df_teams.empty:
        st.warning(f"⚠️ {selected_season} 시즌 데이터가 없습니다.")
        st.stop()
    
    # 팀 순위 테이블
    st.header(f"🏆 {selected_season} 시즌 팀 순위")
    
    # 스타일링된 데이터프레임
    st.dataframe(
        df_teams[['순위', '팀명', '경기', '승', '패', '무', '승률', '게임차', '득점', '실점', '득실차']].style.format({
            '승률': '{:.3f}',
            '게임차': '{:.1f}',
            '득실차': '{:+d}'
        }).background_gradient(subset=['승률'], cmap='RdYlGn'),
        use_container_width=True,
        hide_index=True,
        height=400
    )
    
    st.markdown("---")
    
    # 시각화 섹션
    st.header("📈 시각화 분석")
    
    # 차트 영역 1
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("팀별 승률")
        fig_winrate = px.bar(
            df_teams,
            x='팀명',
            y='승률',
            title=f'{selected_season} 시즌 팀별 승률',
            color='승률',
            color_continuous_scale='RdYlGn',
            text_auto='.3f',
            labels={'승률': '승률', '팀명': '팀'}
        )
        fig_winrate.update_traces(textposition='outside')
        fig_winrate.update_layout(showlegend=False, height=400)
        st.plotly_chart(fig_winrate, use_container_width=True)
    
    with col2:
        st.subheader("득실점 비교")
        fig_runs = go.Figure()
        fig_runs.add_trace(go.Bar(
            name='득점',
            x=df_teams['팀명'],
            y=df_teams['득점'],
            marker_color='#1f77b4',
            text=df_teams['득점'],
            textposition='outside'
        ))
        fig_runs.add_trace(go.Bar(
            name='실점',
            x=df_teams['팀명'],
            y=df_teams['실점'],
            marker_color='#ff7f0e',
            text=df_teams['실점'],
            textposition='outside'
        ))
        fig_runs.update_layout(
            barmode='group',
            title=f'{selected_season} 시즌 팀별 득실점',
            xaxis_title='팀',
            yaxis_title='점수',
            height=400
        )
        st.plotly_chart(fig_runs, use_container_width=True)
    
    # 차트 영역 2
    col3, col4 = st.columns(2)
    
    with col3:
        st.subheader("승-패-무 분포")
        fig_record = go.Figure()
        for idx, row in df_teams.iterrows():
            fig_record.add_trace(go.Bar(
                name=row['팀명'],
                x=['승', '패', '무'],
                y=[row['승'], row['패'], row['무']],
                text=[row['승'], row['패'], row['무']],
                textposition='auto'
            ))
        fig_record.update_layout(
            title=f'{selected_season} 시즌 팀별 승-패-무',
            barmode='group',
            height=400,
            showlegend=True
        )
        st.plotly_chart(fig_record, use_container_width=True)
    
    with col4:
        st.subheader("평균 득실점")
        fig_avg = go.Figure()
        fig_avg.add_trace(go.Scatter(
            x=df_teams['평균득점'],
            y=df_teams['평균실점'],
            mode='markers+text',
            text=df_teams['팀명'],
            textposition='top center',
            marker=dict(
                size=df_teams['승률'] * 50,
                color=df_teams['승률'],
                colorscale='RdYlGn',
                showscale=True,
                colorbar=dict(title="승률")
            ),
            hovertemplate='<b>%{text}</b><br>평균득점: %{x:.2f}<br>평균실점: %{y:.2f}<extra></extra>'
        ))
        fig_avg.update_layout(
            title=f'{selected_season} 시즌 평균 득실점 분포',
            xaxis_title='평균 득점',
            yaxis_title='평균 실점',
            height=400
        )
        # 대각선 추가 (득점 = 실점)
        max_val = max(df_teams['평균득점'].max(), df_teams['평균실점'].max())
        fig_avg.add_trace(go.Scatter(
            x=[0, max_val],
            y=[0, max_val],
            mode='lines',
            line=dict(dash='dash', color='gray'),
            showlegend=False,
            hoverinfo='skip'
        ))
        st.plotly_chart(fig_avg, use_container_width=True)
    
    st.markdown("---")
    
    # 팀 상세 정보
    st.header("🔍 팀 상세 정보")
    
    selected_team = st.selectbox(
        "팀 선택",
        df_teams['팀명'].tolist(),
        help="상세 정보를 볼 팀을 선택하세요"
    )
    
    team_data = df_teams[df_teams['팀명'] == selected_team].iloc[0]
    
    # 메트릭 표시
    col1, col2, col3, col4, col5 = st.columns(5)
    
    with col1:
        st.metric("순위", f"{team_data['순위']}위")
    
    with col2:
        st.metric("승", f"{team_data['승']}승")
    
    with col3:
        st.metric("패", f"{team_data['패']}패")
    
    with col4:
        st.metric("승률", f"{team_data['승률']:.3f}")
    
    with col5:
        st.metric("게임차", f"{team_data['게임차']:.1f}")
    
    col6, col7, col8, col9, col10 = st.columns(5)
    
    with col6:
        st.metric("득점", f"{team_data['득점']}")
    
    with col7:
        st.metric("실점", f"{team_data['실점']}")
    
    with col8:
        st.metric("득실차", f"{team_data['득실차']:+d}")
    
    with col9:
        st.metric("홈 승수", f"{team_data['홈승']}승")
    
    with col10:
        st.metric("원정 승수", f"{team_data['원정승']}승")
    
    # 추가 분석
    with st.expander("📊 상세 분석"):
        st.markdown(f"""
        **{selected_team} 팀 분석**
        
        - **평균 득점**: {team_data['평균득점']:.2f}점/경기
        - **평균 실점**: {team_data['평균실점']:.2f}점/경기
        - **홈 승률**: {team_data['홈승'] / (team_data['경기'] / 2):.3f} (홈 경기 기준)
        - **원정 승률**: {team_data['원정승'] / (team_data['경기'] / 2):.3f} (원정 경기 기준)
        - **무승부율**: {team_data['무'] / team_data['경기']:.3f}
        """)

except Exception as e:
    st.error(f"⚠️ 데이터를 불러오는 중 오류가 발생했습니다: {e}")
    st.info("데이터베이스가 올바른 위치에 있는지 확인해 주세요.")
    import traceback
    with st.expander("오류 상세 정보"):
        st.code(traceback.format_exc())
