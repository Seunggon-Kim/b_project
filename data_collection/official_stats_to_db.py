"""
공식 기록 데이터를 데이터베이스에 저장하는 스크립트

사용법:
    python official_stats_to_db.py --year 2025
"""

import sqlite3
import pandas as pd
import argparse
from pathlib import Path

# 프로젝트 루트 경로
PROJECT_ROOT = Path(__file__).parent.parent
DB_PATH = PROJECT_ROOT / 'database' / 'kbo_stats.db'
STATS_DIR = PROJECT_ROOT / 'crawler' / 'save' / 'official_stats'


def import_team_rankings(year, db_path=DB_PATH):
    """
    팀 순위 데이터를 DB에 저장
    
    Args:
        year: 시즌 연도
        db_path: 데이터베이스 경로
    """
    csv_file = STATS_DIR / f'team_rankings_{year}.csv'
    
    if not csv_file.exists():
        print(f"⚠️ 파일을 찾을 수 없습니다: {csv_file}")
        return False
    
    print(f"\n📊 팀 순위 데이터 로드 중: {csv_file.name}")
    
    try:
        df = pd.read_csv(csv_file, encoding='utf-8-sig')
        
        conn = sqlite3.connect(db_path)
        
        # 팀 순위 데이터 저장 (임시 테이블)
        df.to_sql('team_rankings_temp', conn, if_exists='replace', index=False)
        
        print(f"✅ {len(df)}개 팀 순위 데이터 저장 완료")
        
        conn.close()
        return True
        
    except Exception as e:
        print(f"❌ 팀 순위 저장 실패: {e}")
        return False


def import_player_stats(year, db_path=DB_PATH):
    """
    선수 기록 데이터를 DB에 저장
    
    Args:
        year: 시즌 연도
        db_path: 데이터베이스 경로
    """
    batter_file = STATS_DIR / f'batter_stats_{year}.csv'
    pitcher_file = STATS_DIR / f'pitcher_stats_{year}.csv'
    
    conn = sqlite3.connect(db_path)
    success_count = 0
    
    # 타자 기록
    if batter_file.exists():
        print(f"\n⚾ 타자 기록 데이터 로드 중: {batter_file.name}")
        try:
            df = pd.read_csv(batter_file, encoding='utf-8-sig')
            df.to_sql('batter_stats_temp', conn, if_exists='replace', index=False)
            print(f"✅ {len(df)}명 타자 기록 저장 완료")
            success_count += 1
        except Exception as e:
            print(f"❌ 타자 기록 저장 실패: {e}")
    else:
        print(f"⚠️ 파일을 찾을 수 없습니다: {batter_file}")
    
    # 투수 기록
    if pitcher_file.exists():
        print(f"\n🎯 투수 기록 데이터 로드 중: {pitcher_file.name}")
        try:
            df = pd.read_csv(pitcher_file, encoding='utf-8-sig')
            df.to_sql('pitcher_stats_temp', conn, if_exists='replace', index=False)
            print(f"✅ {len(df)}명 투수 기록 저장 완료")
            success_count += 1
        except Exception as e:
            print(f"❌ 투수 기록 저장 실패: {e}")
    else:
        print(f"⚠️ 파일을 찾을 수 없습니다: {pitcher_file}")
    
    conn.close()
    return success_count > 0


def main():
    """메인 함수"""
    parser = argparse.ArgumentParser(description='KBO 공식 기록 DB 저장')
    parser.add_argument('--year', type=int, default=2025, help='시즌 연도')
    
    args = parser.parse_args()
    
    print("=" * 60)
    print(f"KBO 공식 기록 → DB 저장 - {args.year}년")
    print("=" * 60)
    
    # 팀 순위 저장
    team_success = import_team_rankings(args.year)
    
    # 선수 기록 저장
    player_success = import_player_stats(args.year)
    
    print("\n" + "=" * 60)
    if team_success or player_success:
        print("✅ DB 저장 완료")
        print(f"📁 데이터베이스: {DB_PATH}")
    else:
        print("❌ DB 저장 실패")
    print("=" * 60)


if __name__ == '__main__':
    main()
