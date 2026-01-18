import sqlite3

conn = sqlite3.connect('database/kbo_stats.db')
cur = conn.cursor()

print("=" * 60)
print("📊 데이터베이스 테이블 목록")
print("=" * 60)

cur.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name;")
tables = cur.fetchall()

for i, (table_name,) in enumerate(tables, 1):
    cur.execute(f"SELECT COUNT(*) FROM {table_name}")
    count = cur.fetchone()[0]
    print(f"{i}. {table_name:30s} - {count:,}개 행")

print("\n" + "=" * 60)
print("📋 2025 시즌 주요 데이터")
print("=" * 60)

cur.execute("SELECT COUNT(*) FROM games WHERE season = 2025")
games_count = cur.fetchone()[0]
print(f"✅ 2025 경기 수: {games_count}개")

cur.execute("SELECT COUNT(*) FROM play_by_play WHERE gameID LIKE '2025%'")
plays_count = cur.fetchone()[0]
print(f"✅ 2025 플레이 수: {plays_count:,}개")

cur.execute("SELECT COUNT(*) FROM kbo_official_batter_stats WHERE season = 2025")
batters_count = cur.fetchone()[0]
print(f"✅ 2025 타자 통계: {batters_count}명")

cur.execute("SELECT COUNT(*) FROM kbo_official_pitcher_stats WHERE season = 2025")
pitchers_count = cur.fetchone()[0]
print(f"✅ 2025 투수 통계: {pitchers_count}명")

conn.close()
