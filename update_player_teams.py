"""
선수 테이블에 소속팀 정보 업데이트
타자/투수 통계 테이블에서 2025 시즌 팀 정보를 가져옴
"""
import sqlite3
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent
DB_PATH = PROJECT_ROOT / 'database' / 'kbo_stats.db'

def update_team_info():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    
    print("=" * 60)
    print("🔄 선수 소속팀 정보 업데이트 시작")
    print("=" * 60)
    
    # 현재 team_id가 NULL인 선수 수 확인
    cur.execute("SELECT COUNT(*) FROM players WHERE team_id IS NULL")
    null_count = cur.fetchone()[0]
    print(f"📋 팀 정보 없는 선수: {null_count}명")
    
    # 타자 통계에서 팀 정보 업데이트
    print("\n🏏 타자 통계에서 팀 정보 가져오는 중...")
    cur.execute("""
        UPDATE players 
        SET team_id = (
            SELECT player_team 
            FROM kbo_official_batter_stats 
            WHERE kbo_official_batter_stats.player_id = players.player_id 
            AND season = 2025 
            LIMIT 1
        )
        WHERE player_id IN (
            SELECT player_id 
            FROM kbo_official_batter_stats 
            WHERE season = 2025
        )
        AND team_id IS NULL
    """)
    batter_updated = cur.rowcount
    print(f"✅ 타자 {batter_updated}명 업데이트 완료")
    
    # 투수 통계에서 팀 정보 업데이트
    print("\n⚾ 투수 통계에서 팀 정보 가져오는 중...")
    cur.execute("""
        UPDATE players 
        SET team_id = (
            SELECT player_team 
            FROM kbo_official_pitcher_stats 
            WHERE kbo_official_pitcher_stats.player_id = players.player_id 
            AND season = 2025 
            LIMIT 1
        )
        WHERE player_id IN (
            SELECT player_id 
            FROM kbo_official_pitcher_stats 
            WHERE season = 2025
        )
        AND team_id IS NULL
    """)
    pitcher_updated = cur.rowcount
    print(f"✅ 투수 {pitcher_updated}명 업데이트 완료")
    
    conn.commit()
    
    # 결과 확인
    cur.execute("SELECT COUNT(*) FROM players WHERE team_id IS NOT NULL")
    with_team = cur.fetchone()[0]
    
    cur.execute("SELECT COUNT(*) FROM players WHERE team_id IS NULL")
    without_team = cur.fetchone()[0]
    
    print("\n" + "=" * 60)
    print("📊 업데이트 결과")
    print("=" * 60)
    print(f"✅ 팀 정보 있음: {with_team}명")
    print(f"⚠️  팀 정보 없음: {without_team}명")
    print(f"📝 총 업데이트: {batter_updated + pitcher_updated}명")
    
    # 팀별 선수 수 확인
    print("\n📋 팀별 선수 수:")
    cur.execute("""
        SELECT team_id, COUNT(*) as count 
        FROM players 
        WHERE team_id IS NOT NULL 
        GROUP BY team_id 
        ORDER BY count DESC
    """)
    
    for team, count in cur.fetchall():
        print(f"  {team}: {count}명")
    
    conn.close()
    print("\n" + "=" * 60)
    print("✅ 완료!")
    print("=" * 60)

if __name__ == '__main__':
    update_team_info()
