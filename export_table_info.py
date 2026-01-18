import sqlite3
import pandas as pd

conn = sqlite3.connect('database/kbo_stats.db')

# 테이블 목록
tables_df = pd.read_sql_query(
    "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name",
    conn
)

output = []
output.append("=" * 80)
output.append("📊 KBO 데이터베이스 테이블 목록")
output.append("=" * 80)
output.append("")

for table_name in tables_df['name']:
    count_df = pd.read_sql_query(f"SELECT COUNT(*) as count FROM {table_name}", conn)
    count = count_df['count'][0]
    output.append(f"{table_name:35s} {count:>15,}개 행")

output.append("")
output.append("=" * 80)
output.append("📋 2025 시즌 데이터 현황")
output.append("=" * 80)
output.append("")

# 2025 시즌 데이터
queries = [
    ("2025 경기 수", "SELECT COUNT(*) as count FROM games WHERE season = 2025"),
    ("2025 플레이 수", "SELECT COUNT(*) as count FROM play_by_play WHERE gameID LIKE '2025%'"),
    ("2025 타자 통계", "SELECT COUNT(*) as count FROM kbo_official_batter_stats WHERE season = 2025"),
    ("2025 투수 통계", "SELECT COUNT(*) as count FROM kbo_official_pitcher_stats WHERE season = 2025"),
]

for label, query in queries:
    df = pd.read_sql_query(query, conn)
    count = df['count'][0]
    output.append(f"✅ {label:20s} {count:>15,}개")

output.append("")
output.append("=" * 80)
output.append("📊 각 테이블 상세 정보")
output.append("=" * 80)

# 주요 테이블 스키마
main_tables = ['teams', 'games', 'play_by_play', 'kbo_official_batter_stats', 'kbo_official_pitcher_stats']

for table in main_tables:
    output.append("")
    output.append(f"\n{'─' * 80}")
    output.append(f"테이블: {table}")
    output.append('─' * 80)
    
    # 스키마
    schema_df = pd.read_sql_query(f"PRAGMA table_info({table})", conn)
    output.append("\n컬럼 정보:")
    for _, row in schema_df.iterrows():
        pk = " (PK)" if row['pk'] else ""
        notnull = " NOT NULL" if row['notnull'] else ""
        output.append(f"  - {row['name']:30s} {row['type']:15s}{pk}{notnull}")
    
    # 샘플 데이터
    sample_df = pd.read_sql_query(f"SELECT * FROM {table} LIMIT 3", conn)
    if len(sample_df) > 0:
        output.append(f"\n샘플 데이터 (처음 3개):")
        output.append(sample_df.to_string(index=False, max_colwidth=30))

conn.close()

# 파일로 저장
result = "\n".join(output)
with open('database_tables_info.txt', 'w', encoding='utf-8') as f:
    f.write(result)

print(result)
print("\n\n✅ 상세 정보가 'database_tables_info.txt' 파일에 저장되었습니다.")
