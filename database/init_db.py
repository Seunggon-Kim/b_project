"""
KBO 데이터베이스 초기화 스크립트
"""
import sqlite3
from pathlib import Path

def init_database(db_path='database/kbo_stats.db', schema_path='database/schema.sql'):
    """
    데이터베이스를 초기화하고 스키마를 생성합니다.
    
    Args:
        db_path: 데이터베이스 파일 경로
        schema_path: SQL 스키마 파일 경로
    """
    # 경로 객체 생성
    db_file = Path(db_path)
    schema_file = Path(schema_path)
    
    # 데이터베이스 디렉토리 생성
    db_file.parent.mkdir(parents=True, exist_ok=True)
    
    # 스키마 파일 읽기
    if not schema_file.exists():
        raise FileNotFoundError(f"스키마 파일을 찾을 수 없습니다: {schema_path}")
    
    with open(schema_file, 'r', encoding='utf-8') as f:
        schema_sql = f.read()
    
    # 데이터베이스 연결 및 스키마 실행
    conn = sqlite3.connect(db_file)
    cursor = conn.cursor()
    
    try:
        # 스키마 실행
        cursor.executescript(schema_sql)
        conn.commit()
        print(f"Database successfully initialized: {db_path}")
        
        # 테이블 목록 확인
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = cursor.fetchall()
        print(f"\nCreated tables ({len(tables)}):")
        for table in tables:
            print(f"  - {table[0]}")
            
    except Exception as e:
        print(f"Database initialization failed: {e}")
        conn.rollback()
        raise
    finally:
        conn.close()

if __name__ == '__main__':
    init_database()
