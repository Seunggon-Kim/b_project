import streamlit as st
import sqlite3
import pandas as pd
from pathlib import Path

# 페이지 설정
st.set_page_config(page_title="데이터베이스 탐색기", page_icon="🔍", layout="wide")

st.title("🔍 KBO 데이터베이스 탐색기")
st.markdown("SQLite 데이터베이스에 저장된 원본 데이터를 직접 쿼리하거나 테이블별로 확인할 수 있습니다.")

# DB 연결 설정
DB_PATH = Path(__file__).parent.parent.parent / 'database' / 'kbo_stats.db'

def get_tables():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%';")
    tables = [row[0] for row in cur.fetchall()]
    conn.close()
    return tables

def run_query(query):
    conn = sqlite3.connect(DB_PATH)
    try:
        df = pd.read_sql_query(query, conn)
        return df, None
    except Exception as e:
        return None, str(e)
    finally:
        conn.close()

# 사이드바 설정
st.sidebar.header("설정")
view_mode = st.sidebar.radio("보기 모드", ["테이블 브라우저", "SQL 쿼리 실행기"])

if view_mode == "테이블 브라우저":
    tables = get_tables()
    selected_table = st.selectbox("조회할 테이블 선택", tables)
    
    if selected_table:
        st.subheader(f"📋 {selected_table} 테이블 데이터")
        
        # 행 제한 설정
        row_limit = st.slider("표시할 행 수", 10, 1000, 100)
        
        query = f"SELECT * FROM {selected_table} LIMIT {row_limit}"
        df, error = run_query(query)
        
        if error:
            st.error(f"오류 발생: {error}")
        else:
            st.write(f"표시 중인 행: {len(df)}개")
            st.dataframe(df, use_container_width=True)
            
            # CSV 다운로드 버튼
            csv = df.to_csv(index=False).encode('utf-8-sig')
            st.download_button(
                label=f"{selected_table} 데이터 CSV 다운로드",
                data=csv,
                file_name=f"kbo_{selected_table}.csv",
                mime='text/csv',
            )

else:  # SQL 쿼리 실행기
    st.subheader("⌨️ SQL 쿼리 직접 실행")
    st.info("SELECT 문을 사용하여 데이터를 조회할 수 있습니다.")
    
    query_input = st.text_area("SQL 쿼리 입력", value="SELECT * FROM games LIMIT 10;", height=150)
    
    if st.button("쿼리 실행"):
        if query_input.strip():
            df, error = run_query(query_input)
            if error:
                st.error(f"쿼리 오류: {error}")
            else:
                st.success("쿼리가 성공적으로 실행되었습니다.")
                st.write(f"결과 행: {len(df)}개")
                st.dataframe(df, use_container_width=True)
        else:
            st.warning("쿼리를 입력해주세요.")

# 데이터베이스 요약 정보
st.markdown("---")
st.subheader("📊 DB 요약 정보")
tables = get_tables()
cols = st.columns(len(tables))

conn = sqlite3.connect(DB_PATH)
for i, table in enumerate(tables):
    cur = conn.cursor()
    cur.execute(f"SELECT COUNT(*) FROM {table}")
    count = cur.fetchone()[0]
    with cols[i]:
        st.metric(label=f"{table} 행 수", value=f"{count:,}")
conn.close()
