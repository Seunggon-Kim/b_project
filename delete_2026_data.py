"""
2026 시즌으로 잘못 저장된 KBO 공식 통계 데이터를 삭제하는 스크립트
"""
import sqlite3
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent
DB_PATH = PROJECT_ROOT / 'database' / 'kbo_stats.db'

def main():
    print("=" * 60)
    print("🗑️  2026 시즌 데이터 삭제")
    print("=" * 60)
    
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    
    # 현재 상태 확인
    print("\n📊 현재 DB 상태:")
    
    cur.execute("SELECT COUNT(*) FROM kbo_official_batter_stats WHERE season = 2026")
    batter_2026 = cur.fetchone()[0]
    print(f"  타자 통계 (2026): {batter_2026}명")
    
    cur.execute("SELECT COUNT(*) FROM kbo_official_pitcher_stats WHERE season = 2026")
    pitcher_2026 = cur.fetchone()[0]
    print(f"  투수 통계 (2026): {pitcher_2026}명")
    
    cur.execute("SELECT COUNT(*) FROM kbo_official_batter_stats WHERE season = 2025")
    batter_2025 = cur.fetchone()[0]
    print(f"  타자 통계 (2025): {batter_2025}명")
    
    cur.execute("SELECT COUNT(*) FROM kbo_official_pitcher_stats WHERE season = 2025")
    pitcher_2025 = cur.fetchone()[0]
    print(f"  투수 통계 (2025): {pitcher_2025}명")
    
    if batter_2026 == 0 and pitcher_2026 == 0:
        print("\n✅ 2026 시즌 데이터가 없습니다. 삭제할 필요 없음.")
        conn.close()
        return
    
    # 삭제 확인
    print(f"\n⚠️  2026 시즌 데이터를 삭제하시겠습니까?")
    print(f"   타자: {batter_2026}명, 투수: {pitcher_2026}명")
    response = input("   삭제하려면 'yes'를 입력하세요: ")
    
    if response.lower() != 'yes':
        print("\n❌ 취소되었습니다.")
        conn.close()
        return
    
    # 삭제 실행
    print("\n🗑️  삭제 중...")
    
    cur.execute("DELETE FROM kbo_official_batter_stats WHERE season = 2026")
    deleted_batters = cur.rowcount
    
    cur.execute("DELETE FROM kbo_official_pitcher_stats WHERE season = 2026")
    deleted_pitchers = cur.rowcount
    
    conn.commit()
    
    print(f"\n✅ 삭제 완료!")
    print(f"   타자: {deleted_batters}명 삭제")
    print(f"   투수: {deleted_pitchers}명 삭제")
    
    # 최종 상태 확인
    print("\n📊 최종 DB 상태:")
    
    cur.execute("SELECT COUNT(*) FROM kbo_official_batter_stats WHERE season = 2025")
    batter_2025 = cur.fetchone()[0]
    print(f"  타자 통계 (2025): {batter_2025}명")
    
    cur.execute("SELECT COUNT(*) FROM kbo_official_pitcher_stats WHERE season = 2025")
    pitcher_2025 = cur.fetchone()[0]
    print(f"  투수 통계 (2025): {pitcher_2025}명")
    
    conn.close()
    
    print("\n" + "=" * 60)
    print("💡 다음 단계:")
    print("   1. py data_collection\\selenium_batter_scraper.py")
    print("   2. py data_collection\\kbo_to_db.py")
    print("   3. py data_collection\\selenium_pitcher_scraper.py")
    print("   4. py data_collection\\pitcher_to_db.py")
    print("=" * 60)

if __name__ == "__main__":
    main()
