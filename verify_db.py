import sqlite3

db_path = r'c:\Users\김승곤\Desktop\b_project\database\kbo_stats.db'

def check_db():
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # 1. games 테이블의 2025 시즌 경기 수 확인
        query_games = "SELECT COUNT(*) FROM games WHERE season = 2025"
        cursor.execute(query_games)
        game_count = cursor.fetchone()[0]
        print(f"Total games in 2025: {game_count}")
        
        # 2. game_team_stats 테이블에 각 경기당 2개의 팀 데이터가 있는지 확인
        query_stats = """
            SELECT g.game_id, COUNT(s.team_id) as team_stat_count
            FROM games g
            LEFT JOIN game_team_stats s ON g.game_id = s.game_id
            WHERE g.season = 2025
            GROUP BY g.game_id
            HAVING team_stat_count != 2
        """
        cursor.execute(query_stats)
        stats_rows = cursor.fetchall()
        if not stats_rows:
            print("All games have 2 team stats entries.")
        else:
            print(f"Games with missing team stats ({len(stats_rows)}):")
            for row in stats_rows:
                print(f"  Game ID: {row[0]}, Stats Count: {row[1]}")

        # 3. play_by_play 데이터가 있는지 확인 (경기당 최소 몇 개 이상의 pbp가 있어야 함)
        query_pbp = """
            SELECT g.game_id, COUNT(p.pbp_id) as pbp_count
            FROM games g
            LEFT JOIN play_by_play p ON g.game_id = p.game_id
            WHERE g.season = 2025
            GROUP BY g.game_id
            HAVING pbp_count < 10
        """
        cursor.execute(query_pbp)
        pbp_rows = cursor.fetchall()
        if not pbp_rows:
            print("All games have pbp entries (>= 10).")
        else:
            print(f"Games with little or no pbp data ({len(pbp_rows)}):")
            for row in pbp_rows:
                print(f"  Game ID: {row[0]}, PBP Count: {row[1]}")

        # 4. 720개 경기 목록 출력 (검증용)
        if game_count == 720:
             print("\nFinal Check: Exactly 720 games found for 2025 season.")
        else:
             print(f"\nFinal Check: Found {game_count}/720 games.")

        conn.close()
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    check_db()
