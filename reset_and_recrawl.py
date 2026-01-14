"""
데이터베이스 초기화 및 재크롤링 스크립트

사용법:
    python reset_and_recrawl.py
"""
import sqlite3
import os
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent
DB_PATH = PROJECT_ROOT / 'database' / 'kbo_stats.db'

def backup_database():
    """데이터베이스 백업"""
    if DB_PATH.exists():
        backup_path = DB_PATH.with_suffix('.db.backup')
        import shutil
        shutil.copy2(DB_PATH, backup_path)
        print(f"데이터베이스 백업 완료: {backup_path}")
        return backup_path
    return None

def clear_database():
    """데이터베이스의 play_by_play 및 games 테이블 데이터 삭제"""
    if not DB_PATH.exists():
        print("[경고] 데이터베이스 파일이 없습니다.")
        return False
    
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        # 테이블 데이터 삭제 (테이블 구조는 유지)
        print("\n데이터 삭제 중...")
        
        cursor.execute("DELETE FROM play_by_play")
        deleted_pbp = cursor.rowcount
        print(f"  - play_by_play: {deleted_pbp:,}개 레코드 삭제")
        
        cursor.execute("DELETE FROM games")
        deleted_games = cursor.rowcount
        print(f"  - games: {deleted_games:,}개 레코드 삭제")
        
        cursor.execute("DELETE FROM game_team_stats")
        deleted_stats = cursor.rowcount
        print(f"  - game_team_stats: {deleted_stats:,}개 레코드 삭제")
        
        # 선수 통계 임시 테이블도 삭제
        try:
            cursor.execute("DELETE FROM batter_stats_temp")
            print(f"  - batter_stats_temp: 삭제 완료")
        except:
            pass
            
        try:
            cursor.execute("DELETE FROM pitcher_stats_temp")
            print(f"  - pitcher_stats_temp: 삭제 완료")
        except:
            pass
        
        conn.commit()
        conn.close()
        
        print("데이터베이스 초기화 완료\n")
        return True
        
    except Exception as e:
        print(f"[오류] 데이터베이스 초기화 실패: {e}")
        return False

def main():
    print("=" * 60)
    print("KBO 데이터베이스 초기화 및 재크롤링")
    print("=" * 60)
    
    # 1. 백업
    print("\n[1단계] 데이터베이스 백업")
    backup_path = backup_database()
    
    # 2. 데이터 삭제
    print("\n[2단계] 기존 데이터 삭제")
    if not clear_database():
        print("\n초기화 실패")
        return
    
    print("\n데이터베이스가 초기화되었습니다.")
    print("\n다음 단계:")
    print("1. 크롤러 실행: run_crawler.bat 또는")
    print("   cd crawler && python pbp.py -f 20250101 -t 20251231 -j")
    print("2. DB 저장: python data_collection/csv_to_db.py crawler/save/2025.csv")
    print("3. 통계 계산: python data_collection/calculate_stats.py")
    print("\n또는 한 번에 실행:")
    print("   python data_collection/full_pipeline.py")

if __name__ == '__main__':
    main()
