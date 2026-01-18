"""
KBO 공식 투수 통계를 DB에 저장
UPSERT 방식 (created_at, updated_at 관리)

사용법:
    python pitcher_to_db.py
"""

import sqlite3
import pandas as pd
from pathlib import Path
from datetime import datetime
import logging

# 프로젝트 루트 경로
PROJECT_ROOT = Path(__file__).parent.parent
DB_PATH = PROJECT_ROOT / 'database' / 'kbo_stats.db'
CSV_DIR = PROJECT_ROOT / 'crawler' / 'save' / 'official_stats'

# 로그 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)


def create_pitcher_table(conn):
    """KBO 공식 투수 통계 테이블 생성 (복합 PRIMARY KEY)"""
    cursor = conn.cursor()
    
    # 투수 통계 테이블 (season 컬럼 추가, 복합 PRIMARY KEY)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS kbo_official_pitcher_stats (
        player_id TEXT,
        season INTEGER,
        player_name TEXT,
        player_team TEXT,
        earned_run_average REAL,
        games INTEGER,
        wins INTEGER,
        losses INTEGER,
        save INTEGER,
        hold INTEGER,
        winning_percentage REAL,
        innings_pitched TEXT,
        hits INTEGER,
        home_run INTEGER,
        base_on_balls INTEGER,
        hit_by_pitch INTEGER,
        strikeout INTEGER,
        run INTEGER,
        earned_run INTEGER,
        walks_plus_hits_per_inning_pitched REAL,
        complete_game INTEGER,
        shutout INTEGER,
        quality_start INTEGER,
        blown_save INTEGER,
        total_batters_faced INTEGER,
        number_of_pitchers INTEGER,
        batting_average REAL,
        double INTEGER,
        triple INTEGER,
        sacrifice_bunts INTEGER,
        sacrifice_fly INTEGER,
        intentional_base_on_balls INTEGER,
        wild_pitch INTEGER,
        balk INTEGER,
        games_started INTEGER,
        wins_game_started INTEGER,
        wins_game_relieved INTEGER,
        games_finished INTEGER,
        save_opportunity INTEGER,
        total_saves INTEGER,
        ground_into_double_play INTEGER,
        ground_outs INTEGER,
        air_outs INTEGER,
        go_ao TEXT,
        batting_average_on_balls_in_play REAL,
        p_g REAL,
        p_ip REAL,
        k_9 REAL,
        bb_9 REAL,
        strikeout_per_pa REAL,
        base_on_balls_per_pa REAL,
        k_bb TEXT,
        on_base_percentage REAL,
        slugging_percentage REAL,
        on_base_plus_slugging REAL,
        created_at TEXT,
        updated_at TEXT,
        PRIMARY KEY (player_id, season)
    )
    """)
    
    logging.info("✅ 투수 테이블 생성 완료 (복합 PRIMARY KEY: player_id, season)")
    conn.commit()


def save_pitcher_stats(conn, csv_path):
    """투수 통계 저장 (복합 PRIMARY KEY UPSERT)"""
    logging.info(f"📊 투수 통계 저장 중: {csv_path}")
    
    try:
        # CSV 파일명에서 시즌 추출 (예: pitcher_stats_2026.csv → 2026)
        import re
        season_match = re.search(r'_(\d{4})\.csv$', str(csv_path))
        if not season_match:
            logging.error(f"  ❌ 파일명에서 시즌을 추출할 수 없습니다: {csv_path}")
            return False, 0
        season = int(season_match.group(1))
        logging.info(f"  📅 시즌: {season}")
        
        # CSV 읽기
        df = pd.read_csv(csv_path, encoding='utf-8-sig')
        
        logging.info(f"  📋 CSV 컬럼: {list(df.columns)}")
        logging.info(f"  📊 총 행: {len(df)}")
        
        current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        cursor = conn.cursor()
        
        # 기존 (player_id, season) 조합 조회
        cursor.execute("SELECT player_id, season FROM kbo_official_pitcher_stats WHERE season = ?", (season,))
        existing_keys = set((str(row[0]), int(row[1])) for row in cursor.fetchall())
        
        logging.info(f"  📂 기존 DB 선수 ({season}년): {len(existing_keys)}명")
        
        new_count = 0
        update_count = 0
        skip_count = 0
        
        # 데이터 준비 (None 처리)
        def safe_value(val):
            if pd.isna(val) or val == '' or val == '-':
                return None
            return val
        
        # 각 행을 UPSERT
        for idx, row in df.iterrows():
            player_id = str(row.get('player_id', ''))  # 문자열로 명시적 변환
            
            # player_id가 비어있으면 건너뛰기
            if pd.isna(player_id) or player_id == '' or player_id == 'nan':
                skip_count += 1
                continue
            
            # 기존 선수인지 확인 (player_id + season 조합)
            is_new = (player_id, season) not in existing_keys
            
            if is_new:
                # 새 선수: INSERT
                cursor.execute("""
                    INSERT INTO kbo_official_pitcher_stats (
                        player_id, season, player_name, player_team, earned_run_average,
                        games, wins, losses, save, hold, winning_percentage,
                        innings_pitched, hits, home_run, base_on_balls, hit_by_pitch,
                        strikeout, run, earned_run, walks_plus_hits_per_inning_pitched,
                        complete_game, shutout, quality_start, blown_save,
                        total_batters_faced, number_of_pitchers, batting_average,
                        double, triple, sacrifice_bunts, sacrifice_fly,
                        intentional_base_on_balls, wild_pitch, balk, games_started,
                        wins_game_started, wins_game_relieved, games_finished,
                        save_opportunity, total_saves, ground_into_double_play,
                        ground_outs, air_outs, go_ao, batting_average_on_balls_in_play,
                        p_g, p_ip, k_9, bb_9,
                        strikeout_per_pa, base_on_balls_per_pa,
                        k_bb, on_base_percentage,
                        slugging_percentage, on_base_plus_slugging,
                        created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    player_id,
                    season,
                    safe_value(row.get('player_name')),
                    safe_value(row.get('player_team')),
                    safe_value(row.get('earned_run_average')),
                    safe_value(row.get('games')),
                    safe_value(row.get('wins')),
                    safe_value(row.get('losses')),
                    safe_value(row.get('save')),
                    safe_value(row.get('hold')),
                    safe_value(row.get('winning_percentage')),
                    safe_value(row.get('innings_pitched')),
                    safe_value(row.get('hits')),
                    safe_value(row.get('home_run')),
                    safe_value(row.get('base_on_balls')),
                    safe_value(row.get('hit_by_pitch')),
                    safe_value(row.get('strikeout')),
                    safe_value(row.get('run')),
                    safe_value(row.get('earned_run')),
                    safe_value(row.get('walks_plus_hits_per_inning_pitched')),
                    safe_value(row.get('complete_game')),
                    safe_value(row.get('shutout')),
                    safe_value(row.get('quality_start')),
                    safe_value(row.get('blown_save')),
                    safe_value(row.get('total_batters_faced')),
                    safe_value(row.get('number_of_pitchers')),
                    safe_value(row.get('batting_average')),
                    safe_value(row.get('double')),
                    safe_value(row.get('triple')),
                    safe_value(row.get('sacrifice_bunts')),
                    safe_value(row.get('sacrifice_fly')),
                    safe_value(row.get('intentional_base_on_balls')),
                    safe_value(row.get('wild_pitch')),
                    safe_value(row.get('balk')),
                    safe_value(row.get('games_started')),
                    safe_value(row.get('wins_game_started')),
                    safe_value(row.get('wins_game_relieved')),
                    safe_value(row.get('games_finished')),
                    safe_value(row.get('save_opportunity')),
                    safe_value(row.get('total_saves')),
                    safe_value(row.get('ground_into_double_play')),
                    safe_value(row.get('ground_outs')),
                    safe_value(row.get('air_outs')),
                    safe_value(row.get('go_ao')),
                    safe_value(row.get('batting_average_on_balls_in_play')),
                    safe_value(row.get('p_g')),
                    safe_value(row.get('p_ip')),
                    safe_value(row.get('k_9')),
                    safe_value(row.get('bb_9')),
                    # K% & BB% 계산 (투수는 total_batters_faced 사용)
                    (lambda tbf, ibb, so: round(so / (tbf - ibb) * 100, 1) if (tbf and ibb is not None and tbf > ibb and so is not None) else None)(
                        safe_value(row.get('total_batters_faced')), 
                        safe_value(row.get('intentional_base_on_balls')), 
                        safe_value(row.get('strikeout'))
                    ),
                    (lambda tbf, ibb, bb: round((bb - ibb) / (tbf - ibb) * 100, 1) if (tbf and ibb is not None and tbf > ibb and bb is not None) else None)(
                        safe_value(row.get('total_batters_faced')), 
                        safe_value(row.get('intentional_base_on_balls')), 
                        safe_value(row.get('base_on_balls'))
                    ),
                    safe_value(row.get('k_bb')),
                    safe_value(row.get('on_base_percentage')),
                    safe_value(row.get('slugging_percentage')),
                    safe_value(row.get('on_base_plus_slugging')),
                    current_time,
                    current_time
                ))
                new_count += 1
                existing_keys.add((player_id, season))
            else:
                # 기존 선수: UPDATE만 실행 (created_at 유지)
                cursor.execute("""
                    UPDATE kbo_official_pitcher_stats SET
                        player_name = ?, player_team = ?, earned_run_average = ?,
                        games = ?, wins = ?, losses = ?, save = ?, hold = ?,
                        winning_percentage = ?, innings_pitched = ?, hits = ?,
                        home_run = ?, base_on_balls = ?, hit_by_pitch = ?,
                        strikeout = ?, run = ?, earned_run = ?,
                        walks_plus_hits_per_inning_pitched = ?, complete_game = ?,
                        shutout = ?, quality_start = ?, blown_save = ?,
                        total_batters_faced = ?, number_of_pitchers = ?,
                        batting_average = ?, double = ?, triple = ?,
                        sacrifice_bunts = ?, sacrifice_fly = ?,
                        intentional_base_on_balls = ?, wild_pitch = ?, balk = ?,
                        games_started = ?, wins_game_started = ?,
                        wins_game_relieved = ?, games_finished = ?,
                        save_opportunity = ?, total_saves = ?,
                        ground_into_double_play = ?, ground_outs = ?,
                        air_outs = ?, go_ao = ?,
                        batting_average_on_balls_in_play = ?, p_g = ?,
                        p_ip = ?, k_9 = ?, bb_9 = ?, 
                        strikeout_per_pa = ?, base_on_balls_per_pa = ?,
                        k_bb = ?,
                        on_base_percentage = ?, slugging_percentage = ?,
                        on_base_plus_slugging = ?, updated_at = ?
                    WHERE player_id = ? AND season = ?
                """, (
                    safe_value(row.get('player_name')),
                    safe_value(row.get('player_team')),
                    safe_value(row.get('earned_run_average')),
                    safe_value(row.get('games')),
                    safe_value(row.get('wins')),
                    safe_value(row.get('losses')),
                    safe_value(row.get('save')),
                    safe_value(row.get('hold')),
                    safe_value(row.get('winning_percentage')),
                    safe_value(row.get('innings_pitched')),
                    safe_value(row.get('hits')),
                    safe_value(row.get('home_run')),
                    safe_value(row.get('base_on_balls')),
                    safe_value(row.get('hit_by_pitch')),
                    safe_value(row.get('strikeout')),
                    safe_value(row.get('run')),
                    safe_value(row.get('earned_run')),
                    safe_value(row.get('walks_plus_hits_per_inning_pitched')),
                    safe_value(row.get('complete_game')),
                    safe_value(row.get('shutout')),
                    safe_value(row.get('quality_start')),
                    safe_value(row.get('blown_save')),
                    safe_value(row.get('total_batters_faced')),
                    safe_value(row.get('number_of_pitchers')),
                    safe_value(row.get('batting_average')),
                    safe_value(row.get('double')),
                    safe_value(row.get('triple')),
                    safe_value(row.get('sacrifice_bunts')),
                    safe_value(row.get('sacrifice_fly')),
                    safe_value(row.get('intentional_base_on_balls')),
                    safe_value(row.get('wild_pitch')),
                    safe_value(row.get('balk')),
                    safe_value(row.get('games_started')),
                    safe_value(row.get('wins_game_started')),
                    safe_value(row.get('wins_game_relieved')),
                    safe_value(row.get('games_finished')),
                    safe_value(row.get('save_opportunity')),
                    safe_value(row.get('total_saves')),
                    safe_value(row.get('ground_into_double_play')),
                    safe_value(row.get('ground_outs')),
                    safe_value(row.get('air_outs')),
                    safe_value(row.get('go_ao')),
                    safe_value(row.get('batting_average_on_balls_in_play')),
                    safe_value(row.get('p_g')),
                    safe_value(row.get('p_ip')),
                    safe_value(row.get('k_9')),
                    safe_value(row.get('bb_9')),
                    # K% & BB% 계산
                    (lambda tbf, ibb, so: round(so / (tbf - ibb) * 100, 1) if (tbf and ibb is not None and tbf > ibb and so is not None) else None)(
                        safe_value(row.get('total_batters_faced')), 
                        safe_value(row.get('intentional_base_on_balls')), 
                        safe_value(row.get('strikeout'))
                    ),
                    (lambda tbf, ibb, bb: round((bb - ibb) / (tbf - ibb) * 100, 1) if (tbf and ibb is not None and tbf > ibb and bb is not None) else None)(
                        safe_value(row.get('total_batters_faced')), 
                        safe_value(row.get('intentional_base_on_balls')), 
                        safe_value(row.get('base_on_balls'))
                    ),
                    safe_value(row.get('k_bb')),
                    safe_value(row.get('on_base_percentage')),
                    safe_value(row.get('slugging_percentage')),
                    safe_value(row.get('on_base_plus_slugging')),
                    current_time,
                    player_id,
                    season
                ))
                update_count += 1
        
        conn.commit()
        
        logging.info(f"  ✅ 신규 선수: {new_count}명")
        logging.info(f"  🔄 업데이트: {update_count}명")
        logging.info(f"  ⏭️  건너뛴 행: {skip_count}개 (player_id 없음)")
        logging.info(f"  📊 총: {new_count + update_count}명")
        
        return True, new_count + update_count
        
    except Exception as e:
        logging.error(f"  ❌ 투수 통계 저장 실패: {e}")
        import traceback
        logging.error(traceback.format_exc())
        return False, 0


def main():
    """메인 함수"""
    logging.info("=" * 60)
    logging.info("💾 KBO 공식 투수 통계 DB 저장 시작 (UPSERT)")
    logging.info("=" * 60)
    
    try:
        # DB 연결
        conn = sqlite3.connect(DB_PATH)
        logging.info(f"📂 DB 연결: {DB_PATH}")
        
        # 테이블 생성
        create_pitcher_table(conn)
        
        # 투수 통계 저장 (2025 시즌 데이터 고정)
        target_year = 2025
        pitcher_csv = CSV_DIR / f'pitcher_stats_{target_year}.csv'
        if pitcher_csv.exists():
            success, count = save_pitcher_stats(conn, pitcher_csv)
            if not success:
                return False, 0
        else:
            logging.warning(f"⚠️ 투수 통계 파일 없음: {pitcher_csv}")
            return False, 0
        
        conn.close()
        
        logging.info("\n" + "=" * 60)
        logging.info("✅ DB 저장 완료")
        logging.info(f"📊 처리된 선수: {count}명")
        logging.info("=" * 60)
        
        return True, count
        
    except Exception as e:
        logging.error(f"❌ DB 저장 실패: {e}")
        import traceback
        logging.error(traceback.format_exc())
        return False, 0


if __name__ == '__main__':
    success, count = main()
    
    import sys
    sys.exit(0 if success else 1)
