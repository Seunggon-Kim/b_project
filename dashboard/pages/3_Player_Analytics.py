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
def load_players():
    """선수 정보 로드"""
    conn = sqlite3.connect(DB_PATH)
    query = """
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
        ORDER BY team_id, player_name
    """
    df = pd.read_sql_query(query, conn)
    conn.close()
    return df


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
        # YYYYMMDD -> YYYY년 MM월 DD일
        year = birthday[:4]
        month = birthday[4:6]
        day = birthday[6:8]
        return f"{year}년 {month}월 {day}일"
    except:
        return birthday


# 메인 페이지
st.title("👤 선수 분석")

# 선수 데이터 로드
df_players = load_players()

if df_players.empty:
    st.warning("⚠️ 선수 정보가 없습니다. 먼저 선수 정보를 수집하세요.")
    st.stop()

# 사이드바 필터
st.sidebar.header("🔍 필터")

# 팀 선택
teams = ['전체'] + sorted(df_players['team_id'].dropna().unique().tolist())
selected_team = st.sidebar.selectbox("팀 선택", teams)

# 포지션 선택
positions = ['전체'] + sorted(df_players['position'].dropna().unique().tolist())
selected_position = st.sidebar.selectbox("포지션 선택", positions)

# 필터 적용
filtered_df = df_players.copy()

if selected_team != '전체':
    filtered_df = filtered_df[filtered_df['team_id'] == selected_team]

if selected_position != '전체':
    filtered_df = filtered_df[filtered_df['position'] == selected_position]

# 통계 요약
st.header("📊 통계 요약")

col1, col2, col3, col4 = st.columns(4)

with col1:
    st.metric("전체 선수", f"{len(filtered_df)}명")

with col2:
    avg_height = filtered_df['height'].mean()
    st.metric("평균 신장", f"{avg_height:.1f}cm" if not pd.isna(avg_height) else "-")

with col3:
    avg_weight = filtered_df['weight'].mean()
    st.metric("평균 체중", f"{avg_weight:.1f}kg" if not pd.isna(avg_weight) else "-")

with col4:
    avg_salary = filtered_df['salary'].mean()
    st.metric("평균 연봉", f"{int(avg_salary/10000):,}만원" if not pd.isna(avg_salary) else "-")

st.divider()

# 선수 검색
st.header("🔎 선수 검색")
search_query = st.text_input("선수 이름 검색", placeholder="선수 이름을 입력하세요...")

if search_query:
    filtered_df = filtered_df[filtered_df['player_name'].str.contains(search_query, na=False)]

st.divider()

# 선수 목록 (카드 형식)
st.header(f"👥 선수 목록 ({len(filtered_df)}명)")

# 정렬 옵션
sort_options = {
    "이름순": "player_name",
    "등번호순": "back_number",
    "신장순": "height",
    "연봉순": "salary"
}
sort_by = st.selectbox("정렬", list(sort_options.keys()))

# 정렬 적용
sort_column = sort_options[sort_by]
filtered_df = filtered_df.sort_values(sort_column, ascending=(sort_by != "연봉순"))

# 선수 카드 표시 (3열)
cols_per_row = 3
for idx in range(0, len(filtered_df), cols_per_row):
    cols = st.columns(cols_per_row)
    
    for col_idx, col in enumerate(cols):
        if idx + col_idx < len(filtered_df):
            player = filtered_df.iloc[idx + col_idx]
            
            with col:
                with st.container():
                    # 카드 스타일
                    st.markdown(f"""
                    <div style="
                        border: 2px solid #e0e0e0;
                        border-radius: 10px;
                        padding: 15px;
                        margin-bottom: 15px;
                        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                        color: white;
                    ">
                        <h3 style="margin: 0; color: white;">{player['player_name']}</h3>
                        <p style="margin: 5px 0; color: #f0f0f0;">{player['team_id']} | No.{int(player['back_number']) if not pd.isna(player['back_number']) else '?'}</p>
                    </div>
                    """, unsafe_allow_html=True)
                    
                    # 이미지
                    if player['image_url'] and not pd.isna(player['image_url']):
                        st.image(player['image_url'], use_container_width=True)
                    else:
                        st.info("이미지 없음")
                    
                    # 상세 정보
                    with st.expander("📋 상세 정보"):
                        st.write(f"**포지션**: {player['position']}")
                        st.write(f"**투타**: {format_throw_bat(player['throw'], player['bat'])}")
                        st.write(f"**생년월일**: {format_birthday(player['birthday'])}")
                        st.write(f"**신장/체중**: {int(player['height']) if not pd.isna(player['height']) else '?'}cm / {int(player['weight']) if not pd.isna(player['weight']) else '?'}kg")
                        st.write(f"**경력**: {player['career'] if not pd.isna(player['career']) else '-'}")
                        st.write(f"**입단**: {player['draft_year']} ({player['draft_order']})")
                        st.write(f"**계약금**: {format_money(player['signing_bonus'])}")
                        st.write(f"**연봉**: {format_money(player['salary'])}")

st.divider()

# 팀별 통계
st.header("📊 팀별 통계")

team_stats = df_players.groupby('team_id').agg({
    'player_id': 'count',
    'height': 'mean',
    'weight': 'mean',
    'salary': 'mean'
}).round(1)

team_stats.columns = ['선수 수', '평균 신장(cm)', '평균 체중(kg)', '평균 연봉']
team_stats['평균 연봉'] = team_stats['평균 연봉'].apply(lambda x: f"{int(x/10000):,}만원" if not pd.isna(x) else "-")

st.dataframe(
    team_stats,
    use_container_width=True,
    height=400
)
