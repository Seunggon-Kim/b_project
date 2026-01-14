"""
테이블 삭제 스크립트
"""
import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).parent / 'database' / 'kbo_stats.db'

conn = sqlite3.connect(DB_PATH)
conn.execute('DROP TABLE IF EXISTS kbo_official_batter_stats')
conn.commit()
conn.close()

print('✅ kbo_official_batter_stats 테이블 삭제 완료')
