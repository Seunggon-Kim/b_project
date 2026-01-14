"""
KBO 공식 통계 DB 확인 스크립트
수집된 데이터 검증 및 샘플 조회

사용법:
    python check_kbo_stats.py
"""

import sqlite3
import pandas as pd
from pathlib import Path

# DB 경로
DB_PATH = Path(__file__).parent / 'database' / 'kbo_stats.db'

def check_database():
    """데이터베이스 확인"""
    print("=" * 80)
    print("📊 KBO 공식 통계 DB 확인")
    print("=" * 80)
    
    if not DB_PATH.exists():
        print(f"❌ 데이터베이스 파일이 없습니다: {DB_PATH}")
        return
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # 1. 테이블 존재 확인
    print("\n1️⃣ 테이블 확인")
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='kbo_official_batter_stats'")
    if cursor.fetchone():
        print("   ✅ kbo_official_batter_stats 테이블 존재")
    else:
        print("   ❌ kbo_official_batter_stats 테이블 없음")
        conn.close()
        return
    
    # 2. 총 선수 수
    print("\n2️⃣ 데이터 개수")
    cursor.execute("SELECT COUNT(*) FROM kbo_official_batter_stats")
    total_count = cursor.fetchone()[0]
    print(f"   📊 총 선수: {total_count}명")
    
    # 3. player_id 확인
    print("\n3️⃣ player_id 확인")
    cursor.execute("SELECT COUNT(*) FROM kbo_official_batter_stats WHERE player_id IS NOT NULL AND player_id != ''")
    valid_id_count = cursor.fetchone()[0]
    print(f"   ✅ 유효한 player_id: {valid_id_count}명")
    print(f"   ❌ 누락된 player_id: {total_count - valid_id_count}명")
    
    # 4. 팀별 선수 수
    print("\n4️⃣ 팀별 선수 수")
    df_teams = pd.read_sql_query("""
        SELECT player_team AS 팀, COUNT(*) AS 선수수
        FROM kbo_official_batter_stats
        GROUP BY player_team
        ORDER BY 선수수 DESC
    """, conn)
    print(df_teams.to_string(index=False))
    
    # 5. created_at, updated_at 확인
    print("\n5️⃣ 타임스탬프 확인")
    cursor.execute("SELECT MIN(created_at), MAX(created_at) FROM kbo_official_batter_stats")
    min_created, max_created = cursor.fetchone()
    print(f"   📅 최초 등록: {min_created} ~ {max_created}")
    
    cursor.execute("SELECT MIN(updated_at), MAX(updated_at) FROM kbo_official_batter_stats")
    min_updated, max_updated = cursor.fetchone()
    print(f"   🔄 마지막 업데이트: {min_updated} ~ {max_updated}")
    
    # 6. 샘플 데이터 (상위 5명)
    print("\n6️⃣ 타율 상위 5명 (샘플)")
    df_sample = pd.read_sql_query("""
        SELECT 
            player_id,
            player_name AS 선수명,
            player_team AS 팀,
            batting_average AS 타율,
            games AS 경기수,
            at_bat AS 타수,
            single AS 안타,
            home_run AS 홈런,
            run_batted_in AS 타점
        FROM kbo_official_batter_stats
        WHERE at_bat >= 50
        ORDER BY batting_average DESC
        LIMIT 5
    """, conn)
    print(df_sample.to_string(index=False))
    
    # 7. 첫 3행 전체 컬럼
    print("\n7️⃣ 첫 3행 (전체 컬럼)")
    df_first = pd.read_sql_query("""
        SELECT * FROM kbo_official_batter_stats LIMIT 3
    """, conn)
    print(df_first.T.to_string())  # 전치하여 세로로 표시
    
    # 8. 데이터 품질 체크
    print("\n8️⃣ 데이터 품질 체크")
    
    # NULL 값 확인
    cursor.execute("SELECT COUNT(*) FROM kbo_official_batter_stats WHERE player_name IS NULL")
    null_name = cursor.fetchone()[0]
    print(f"   선수명 NULL: {null_name}명")
    
    cursor.execute("SELECT COUNT(*) FROM kbo_official_batter_stats WHERE batting_average IS NULL")
    null_avg = cursor.fetchone()[0]
    print(f"   타율 NULL: {null_avg}명")
    
    # 이상치 확인
    cursor.execute("SELECT COUNT(*) FROM kbo_official_batter_stats WHERE batting_average > 1.0")
    invalid_avg = cursor.fetchone()[0]
    print(f"   타율 이상치 (>1.0): {invalid_avg}명")
    
    cursor.execute("SELECT COUNT(*) FROM kbo_official_batter_stats WHERE games < 0")
    invalid_games = cursor.fetchone()[0]
    print(f"   경기수 이상치 (<0): {invalid_games}명")
    
    # 9. 컬럼 정보
    print("\n9️⃣ 테이블 스키마")
    cursor.execute("PRAGMA table_info(kbo_official_batter_stats)")
    columns = cursor.fetchall()
    print(f"   총 컬럼 수: {len(columns)}")
    print("\n   컬럼 목록:")
    for col in columns:
        print(f"   - {col[1]} ({col[2]})")
    
    conn.close()
    
    print("\n" + "=" * 80)
    print("✅ 확인 완료")
    print("=" * 80)


if __name__ == '__main__':
    check_database()
