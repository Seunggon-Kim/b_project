"""
2025 시즌 CSV 파일들을 DB에 삽입하는 스크립트
"""
import sqlite3
import csv
from pathlib import Path

PROJECT_ROOT = Path(r'c:\Users\김승곤\Desktop\b_project')
DB_PATH = PROJECT_ROOT / 'database' / 'kbo_stats.db'
CSV_DIR = PROJECT_ROOT / 'crawler' / 'save' / '2025'

def import_csv_to_db(csv_path, existing_game_ids):
    """CSV 파일을 DB에 삽입"""
    game_id_stem = Path(csv_path).stem
    
    # 이미 처리된 경기는 스킵
    if game_id_stem in existing_game_ids:
        return True, "skipped"
    
    conn = None
    try:
        conn = sqlite3.connect(DB_PATH)
        cur = conn.cursor()
        
        # CSV 파일 읽기
        rows = []
        for encoding in ["cp949", "utf-8-sig", "utf-8"]:
            try:
                with open(csv_path, "r", encoding=encoding) as f:
                    reader = csv.DictReader(f)
                    rows = list(reader)
                    if rows:
                        break
            except Exception:
                continue
        
        if not rows:
            return False, "Failed to read file"
        
        # play_by_play 테이블에 삽입
        # 스키마에 있는 모든 컬럼을 사용
        columns = [
            'pitch_type', 'pitcher', 'batter', 'pitcher_ID', 'batter_ID',
            'speed', 'pitch_result', 'pa_result', 'pa_result_detail', 'description',
            'balls', 'strikes', 'outs', 'inning', 'inning_topbot',
            'score_away', 'score_home', 'outs_on_play', 'runs_scored',
            'stands', 'throws', 'on_1b', 'on_2b', 'on_3b',
            'pos_1', 'pos_2', 'pos_3', 'pos_4', 'pos_5', 'pos_6', 'pos_7', 'pos_8', 'pos_9',
            'on_1b_id', 'on_2b_id', 'on_3b_id',
            'pos_1_id', 'pos_2_id', 'pos_3_id', 'pos_4_id', 'pos_5_id', 
            'pos_6_id', 'pos_7_id', 'pos_8_id', 'pos_9_id',
            'px', 'pz', 'pfx_x', 'pfx_z', 'pfx_x_raw', 'pfx_z_raw',
            'x0', 'z0', 'sz_top', 'sz_bot', 'y0',
            'vx0', 'vy0', 'vz0', 'ax', 'ay', 'az',
            'game_date', 'home', 'away', 'home_alias', 'away_alias',
            'stadium', 'referee', 'pa_number', 'pitch_number', 'pitchID', 'gameID'
        ]
        
        rows_added = 0
        for row in rows:
            # 각 컬럼의 값을 가져오기 (없으면 None)
            values = [row.get(col) for col in columns]
            
            # SQL 생성
            placeholders = ', '.join(['?' for _ in columns])
            col_names = ', '.join(columns)
            
            cur.execute(f"""
                INSERT INTO play_by_play ({col_names})
                VALUES ({placeholders})
            """, values)
            rows_added += 1
        
        # games 테이블에 경기 정보 삽입
        if rows:
            last_row = rows[-1]
            game_id = last_row.get("gameID")
            game_date = last_row.get("game_date")
            season = game_date[:4] if game_date else "2025"
            home_id = last_row.get("home_alias")
            away_id = last_row.get("away_alias")
            h_score = int(last_row.get("score_home", 0)) if last_row.get("score_home") else 0
            a_score = int(last_row.get("score_away", 0)) if last_row.get("score_away") else 0
            stadium = last_row.get("stadium")
            
            cur.execute("""
                INSERT OR REPLACE INTO games (
                    game_id, game_date, season, game_type, home_team_id, 
                    away_team_id, home_score, away_score, stadium
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (game_id, game_date, season, "정규시즌", home_id, away_id, h_score, a_score, stadium))
        
        conn.commit()
        return True, f"Success ({rows_added} rows)"
        
    except Exception as e:
        if conn:
            conn.rollback()
        return False, str(e)
    finally:
        if conn:
            conn.close()

def main():
    print("=" * 60)
    print("2025 시즌 CSV 파일을 DB에 삽입")
    print("=" * 60)
    
    # 기존 게임 ID 가져오기
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("SELECT game_id FROM games WHERE season = 2025")
    existing_game_ids = set(row[0] for row in cur.fetchall())
    conn.close()
    
    print(f"\n📊 기존 DB에 있는 2025 시즌 경기: {len(existing_game_ids)}개")
    
    # CSV 파일 목록
    csv_files = sorted(list(CSV_DIR.glob("*.csv")))
    # ~$로 시작하는 임시 파일 제외
    csv_files = [f for f in csv_files if not f.name.startswith("~$")]
    
    print(f"📂 처리할 CSV 파일: {len(csv_files)}개")
    
    success_count = 0
    skip_count = 0
    fail_count = 0
    
    print("\n🔄 파일 처리 중...")
    for i, csv_file in enumerate(csv_files, 1):
        success, message = import_csv_to_db(str(csv_file), existing_game_ids)
        
        if success:
            if message == "skipped":
                skip_count += 1
            else:
                success_count += 1
                existing_game_ids.add(csv_file.stem)
        else:
            fail_count += 1
            print(f"  ❌ FAILED: {csv_file.name} - {message[:100]}")
        
        # 진행 상황 출력
        if i % 100 == 0:
            print(f"  진행: {i}/{len(csv_files)} ({i/len(csv_files)*100:.1f}%)")
    
    print(f"\n{'='*60}")
    print(f"✅ 완료!")
    print(f"  성공: {success_count}개")
    print(f"  스킵: {skip_count}개")
    print(f"  실패: {fail_count}개")
    print(f"{'='*60}")
    
    # 최종 확인
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM games WHERE season = 2025")
    total_games = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM play_by_play WHERE gameID LIKE '2025%'")
    total_plays = cur.fetchone()[0]
    conn.close()
    
    print(f"\n📊 DB 최종 상태:")
    print(f"  2025 시즌 경기 수: {total_games}개")
    print(f"  2025 시즌 플레이 수: {total_plays:,}개")

if __name__ == "__main__":
    main()
