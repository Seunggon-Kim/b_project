import sqlite3
import os

def calculate_stats():
    db_path = 'database/kbo_stats.db'
    if not os.path.exists(db_path):
        print(f"Error: Database not found at {db_path}")
        return

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    print("Calculating Batter Stats...")
    
    # 1. Create temporary tables for stats if they don't exist
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS batter_stats_temp (
        선수명 TEXT,
        팀 TEXT,
        경기수 INTEGER,
        타석 INTEGER,
        타수 INTEGER,
        안타 INTEGER,
        "2루타" INTEGER,
        "3루타" INTEGER,
        홈런 INTEGER,
        타점 INTEGER,
        득점 INTEGER,
        도루 INTEGER,
        볼넷 INTEGER,
        삼진 INTEGER,
        타율 REAL,
        출루율 REAL,
        장타율 REAL,
        OPS REAL
    )
    """)
    
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS pitcher_stats_temp (
        선수명 TEXT,
        팀 TEXT,
        방어율 REAL,
        경기수 INTEGER,
        승 INTEGER,
        패 INTEGER,
        세이브 INTEGER,
        홀드 INTEGER,
        이닝 TEXT,
        피안타 INTEGER,
        피홈런 INTEGER,
        볼넷 INTEGER,
        탈삼진 INTEGER,
        실점 INTEGER,
        자책점 INTEGER,
        WHIP REAL
    )
    """)
    
    # Clear existing data in temp tables
    cursor.execute("DELETE FROM batter_stats_temp")
    cursor.execute("DELETE FROM pitcher_stats_temp")

    # 2. Aggregate Batter Stats
    # Note: This is a simplified aggregation based on available PBP data
    cursor.execute("""
    SELECT 
        batter as 선수명,
        home as 팀, -- Simplified: uses the 'home' team from the last record found
        COUNT(*) as 타석,
        SUM(CASE WHEN pa_result IN ('안타', '2루타', '3루타', '홈런', '내야안타', '번트 안타', '우익수 앞 1루타', '좌익수 앞 1루타', '중견수 앞 1루타') THEN 1 ELSE 0 END) as 안타,
        SUM(CASE WHEN pa_result = '2루타' THEN 1 ELSE 0 END) as "2루타",
        SUM(CASE WHEN pa_result = '3루타' THEN 1 ELSE 0 END) as "3루타",
        SUM(CASE WHEN pa_result = '홈런' THEN 1 ELSE 0 END) as 홈런,
        SUM(CASE WHEN pa_result IN ('볼넷', '자동 고의4구') THEN 1 ELSE 0 END) as 볼넷,
        SUM(CASE WHEN pa_result LIKE '%삼진%' THEN 1 ELSE 0 END) as 삼진,
        SUM(runs_scored) as 타점
    FROM play_by_play
    WHERE batter IS NOT NULL AND batter != ''
    GROUP BY batter_ID
    """)
    
    batters = cursor.fetchall()
    
    for b in batters:
        name, team, pa, h, h2, h3, hr, bb, so, rbi = b
        # Simplified AB calculation: PA - BB (ignoring HBP/SF/SH for now)
        ab = pa - bb
        avg = h / ab if ab > 0 else 0
        obp = (h + bb) / pa if pa > 0 else 0
        slg = (h + h2 + 2*h3 + 3*hr) / ab if ab > 0 else 0 # (1h + 2*2h + 3*3h + 4*hr) / ab simplified
        # Actually SLG = (1B + 2*2B + 3*3B + 4*HR) / AB
        # Let's do it properly:
        h1 = h - h2 - h3 - hr
        slg = (h1 + 2*h2 + 3*h3 + 4*hr) / ab if ab > 0 else 0
        ops = obp + slg
        
        cursor.execute("""
        INSERT INTO batter_stats_temp (선수명, 팀, 타석, 타수, 안타, "2루타", "3루타", 홈런, 타점, 볼넷, 삼진, 타율, 출루율, 장타율, OPS)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (name, team, pa, ab, h, h2, h3, hr, rbi, bb, so, round(avg, 3), round(obp, 3), round(slg, 3), round(ops, 3)))

    # 3. Aggregate Pitcher Stats
    cursor.execute("""
    SELECT 
        pitcher as 선수명,
        away as 팀,
        COUNT(*) as 타석, -- TBF
        SUM(CASE WHEN pa_result IN ('안타', '2루타', '3루타', '홈런', '내야안타', '번트 안타') THEN 1 ELSE 0 END) as 피안타,
        SUM(CASE WHEN pa_result = '홈런' THEN 1 ELSE 0 END) as 피홈런,
        SUM(CASE WHEN pa_result IN ('볼넷', '자동 고의4구') THEN 1 ELSE 0 END) as 볼넷,
        SUM(CASE WHEN pa_result LIKE '%삼진%' THEN 1 ELSE 0 END) as 탈삼진,
        SUM(runs_scored) as 실점,
        SUM(outs_on_play) as 아웃수
    FROM play_by_play
    WHERE pitcher IS NOT NULL AND pitcher != ''
    GROUP BY pitcher_ID
    """)
    
    pitchers = cursor.fetchall()
    
    for p in pitchers:
        name, team, tbf, h, hr, bb, so, r, outs = p
        innings = outs / 3.0
        era = (r * 9) / innings if innings > 0 else 0
        whip = (h + bb) / innings if innings > 0 else 0
        
        # Format innings as "123.1"
        full_innings = outs // 3
        rem_outs = outs % 3
        inning_str = f"{full_innings}.{rem_outs}"
        
        cursor.execute("""
        INSERT INTO pitcher_stats_temp (선수명, 팀, 방어율, 승, 패, 이닝, 피안타, 피홈런, 볼넷, 탈삼진, 실점, WHIP)
        VALUES (?, ?, ?, 0, 0, ?, ?, ?, ?, ?, ?, ?)
        """, (name, team, round(era, 2), inning_str, h, hr, bb, so, r, round(whip, 2)))

    conn.commit()
    conn.close()
    print("Stats calculation and DB update complete.")

if __name__ == "__main__":
    calculate_stats()
