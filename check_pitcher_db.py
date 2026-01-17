import sqlite3
import pandas as pd

conn = sqlite3.connect('database/kbo_stats.db')
cursor = conn.cursor()

print("=" * 60)
print("투수 통계 DB 확인")
print("=" * 60)

# 총 투수 수
cursor.execute('SELECT COUNT(*) FROM kbo_official_pitcher_stats')
total = cursor.fetchone()[0]
print(f"\n총 투수: {total}명")

# 팀별 분포
cursor.execute('SELECT player_team, COUNT(*) FROM kbo_official_pitcher_stats GROUP BY player_team ORDER BY player_team')
print("\n팀별 분포:")
for row in cursor.fetchall():
    print(f"  {row[0]}: {row[1]}명")

# 샘플 데이터
print("\n샘플 데이터 (상위 5명):")
df = pd.read_sql_query('''
    SELECT player_id, player_name, player_team, 
           earned_run_average as ERA, games as G, 
           wins as W, save as SV
    FROM kbo_official_pitcher_stats 
    LIMIT 5
''', conn)
print(df.to_string(index=False))

# 컬럼 확인
cursor.execute('PRAGMA table_info(kbo_official_pitcher_stats)')
columns = cursor.fetchall()
print(f"\n총 컬럼 수: {len(columns)}개")

conn.close()
print("\n" + "=" * 60)
