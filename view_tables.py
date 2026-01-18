"""
데이터베이스 테이블 뷰어
"""
import sqlite3
import pandas as pd
from pathlib import Path

DB_PATH = Path('database/kbo_stats.db')

def show_tables():
    """모든 테이블 목록 표시"""
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    
    print("=" * 80)
    print("📊 데이터베이스 테이블 목록")
    print("=" * 80)
    
    cur.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name;")
    tables = cur.fetchall()
    
    print(f"\n총 {len(tables)}개 테이블:\n")
    for i, (table_name,) in enumerate(tables, 1):
        print(f"{i}. {table_name}")
    
    conn.close()
    return [t[0] for t in tables]

def show_table_info(table_name):
    """특정 테이블의 정보 표시"""
    conn = sqlite3.connect(DB_PATH)
    
    print(f"\n{'=' * 80}")
    print(f"📋 테이블: {table_name}")
    print("=" * 80)
    
    # 컬럼 정보
    df_schema = pd.read_sql_query(f"PRAGMA table_info({table_name})", conn)
    print(f"\n📌 컬럼 정보 ({len(df_schema)}개 컬럼):")
    print(df_schema[['name', 'type', 'notnull', 'pk']].to_string(index=False))
    
    # 행 개수
    cur = conn.cursor()
    cur.execute(f"SELECT COUNT(*) FROM {table_name}")
    row_count = cur.fetchone()[0]
    print(f"\n📊 총 행 수: {row_count:,}개")
    
    # 샘플 데이터 (처음 5개)
    if row_count > 0:
        print(f"\n📄 샘플 데이터 (처음 5개):")
        df_sample = pd.read_sql_query(f"SELECT * FROM {table_name} LIMIT 5", conn)
        print(df_sample.to_string(index=False))
    else:
        print("\n⚠️ 데이터가 없습니다.")
    
    conn.close()

def main():
    print("\n🗄️ KBO 데이터베이스 뷰어\n")
    
    # 모든 테이블 목록
    tables = show_tables()
    
    # 주요 테이블 상세 정보
    main_tables = ['games', 'play_by_play', 'teams', 'kbo_official_batter_stats', 'kbo_official_pitcher_stats']
    
    print(f"\n\n{'=' * 80}")
    print("📊 주요 테이블 상세 정보")
    print("=" * 80)
    
    for table in main_tables:
        if table in tables:
            show_table_info(table)
    
    # 사용자 선택
    print(f"\n\n{'=' * 80}")
    print("💡 다른 테이블을 보려면:")
    print("=" * 80)
    print("\nPython에서 다음 코드를 실행하세요:")
    print(f"  import sqlite3, pandas as pd")
    print(f"  conn = sqlite3.connect('database/kbo_stats.db')")
    print(f"  df = pd.read_sql_query('SELECT * FROM 테이블명 LIMIT 10', conn)")
    print(f"  print(df)")
    print(f"  conn.close()")

if __name__ == "__main__":
    main()
