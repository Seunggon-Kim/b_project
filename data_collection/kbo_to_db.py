"""
KBO 공식 통계를 DB에 저장 (전체 스키마)
UPSERT 방식 (created_at, updated_at 관리)

사용법:
    python kbo_to_db.py
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


def create_tables(conn):
    """KBO 공식 통계 테이블 생성 (복합 PRIMARY KEY)"""
    cursor = conn.cursor()
    
    # 타자 통계 테이블 (season 컬럼 추가, 복합 PRIMARY KEY)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS kbo_official_batter_stats (
        player_id TEXT,
        season INTEGER,
        player_name TEXT,
        player_team TEXT,
        batting_average REAL,
        games INTEGER,
        plate_appearance INTEGER,
        at_bat INTEGER,
        run INTEGER,
        single INTEGER,
        double INTEGER,
        triple INTEGER,
        home_run INTEGER,
        total_bases INTEGER,
        run_batted_in INTEGER,
        sacrifice_bunts INTEGER,
        sacrifice_fly INTEGER,
        base_on_balls INTEGER,
        intentional_base_on_balls INTEGER,
        hit_by_pitch INTEGER,
        strikeout INTEGER,
        ground_into_double_play INTEGER,
        slugging_percentage REAL,
        on_base_percentage REAL,
        on_base_plus_slugging REAL,
        multi_hits INTEGER,
        runners_in_scoring_position REAL,
        pinch_hit_batting_average REAL,
        extra_base_hits INTEGER,
        ground_outs INTEGER,
        air_outs INTEGER,
        go_ao TEXT,
        gw_rbi INTEGER,
        bb_k TEXT,
        p_pa REAL,
        isop REAL,
        extended_runs REAL,
        gross_production_average REAL,
        created_at TEXT,
        updated_at TEXT,
        PRIMARY KEY (player_id, season)
    )
    """)
    
    logging.info("✅ 테이블 생성 완료 (복합 PRIMARY KEY: player_id, season)")
    conn.commit()


def save_batter_stats(conn, csv_path):
    """타자 통계 저장 (복합 PRIMARY KEY UPSERT)"""
    logging.info(f"📊 타자 통계 저장 중: {csv_path}")
    
    try:
        # CSV 파일명에서 시즌 추출 (예: batter_stats_2026.csv → 2026)
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
        cursor.execute("SELECT player_id, season FROM kbo_official_batter_stats WHERE season = ?", (season,))
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
                    INSERT INTO kbo_official_batter_stats (
                        player_id, season, player_name, player_team, batting_average,
                        games, plate_appearance, at_bat, run, single, double, triple,
                        home_run, total_bases, run_batted_in, sacrifice_bunts,
                        sacrifice_fly, base_on_balls, intentional_base_on_balls,
                        hit_by_pitch, strikeout, ground_into_double_play,
                        slugging_percentage, on_base_percentage, on_base_plus_slugging,
                        multi_hits, runners_in_scoring_position, pinch_hit_batting_average,
                        extra_base_hits, ground_outs, air_outs, go_ao, gw_rbi,
                        bb_k, p_pa, isop, extended_runs, gross_production_average,
                        created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    player_id,
                    season,
                    safe_value(row.get('player_name')),
                    safe_value(row.get('player_team')),
                    safe_value(row.get('batting_average')),
                    safe_value(row.get('games')),
                    safe_value(row.get('plate_appearance')),
                    safe_value(row.get('at_bat')),
                    safe_value(row.get('run')),
                    safe_value(row.get('single')),
                    safe_value(row.get('double')),
                    safe_value(row.get('triple')),
                    safe_value(row.get('home_run')),
                    safe_value(row.get('total_bases')),
                    safe_value(row.get('run_batted_in')),
                    safe_value(row.get('sacrifice_bunts')),
                    safe_value(row.get('sacrifice_fly')),
                    safe_value(row.get('base_on_balls')),
                    safe_value(row.get('intentional_base_on_balls')),
                    safe_value(row.get('hit_by_pitch')),
                    safe_value(row.get('strikeout')),
                    safe_value(row.get('ground_into_double_play')),
                    safe_value(row.get('slugging_percentage')),
                    safe_value(row.get('on_base_percentage')),
                    safe_value(row.get('on_base_plus_slugging')),
                    safe_value(row.get('multi_hits')),
                    safe_value(row.get('runners_in_scoring_position')),
                    safe_value(row.get('pinch_hit_batting_average')),
                    safe_value(row.get('extra_base_hits')),
                    safe_value(row.get('ground_outs')),
                    safe_value(row.get('air_outs')),
                    safe_value(row.get('go_ao')),
                    safe_value(row.get('gw_rbi')),
                    safe_value(row.get('bb_k')),
                    safe_value(row.get('p_pa')),
                    safe_value(row.get('isop')),
                    safe_value(row.get('extended_runs')),
                    safe_value(row.get('gross_production_average')),
                    current_time,
                    current_time
                ))
                new_count += 1
                existing_keys.add((player_id, season))
            else:
                # 기존 선수: UPDATE만 실행 (created_at 유지)
                cursor.execute("""
                    UPDATE kbo_official_batter_stats SET
                        player_name = ?, player_team = ?, batting_average = ?,
                        games = ?, plate_appearance = ?, at_bat = ?, run = ?,
                        single = ?, double = ?, triple = ?, home_run = ?,
                        total_bases = ?, run_batted_in = ?, sacrifice_bunts = ?,
                        sacrifice_fly = ?, base_on_balls = ?, intentional_base_on_balls = ?,
                        hit_by_pitch = ?, strikeout = ?, ground_into_double_play = ?,
                        slugging_percentage = ?, on_base_percentage = ?, on_base_plus_slugging = ?,
                        multi_hits = ?, runners_in_scoring_position = ?, pinch_hit_batting_average = ?,
                        extra_base_hits = ?, ground_outs = ?, air_outs = ?, go_ao = ?,
                        gw_rbi = ?, bb_k = ?, p_pa = ?, isop = ?, extended_runs = ?,
                        gross_production_average = ?, updated_at = ?
                    WHERE player_id = ? AND season = ?
                """, (
                    safe_value(row.get('player_name')),
                    safe_value(row.get('player_team')),
                    safe_value(row.get('batting_average')),
                    safe_value(row.get('games')),
                    safe_value(row.get('plate_appearance')),
                    safe_value(row.get('at_bat')),
                    safe_value(row.get('run')),
                    safe_value(row.get('single')),
                    safe_value(row.get('double')),
                    safe_value(row.get('triple')),
                    safe_value(row.get('home_run')),
                    safe_value(row.get('total_bases')),
                    safe_value(row.get('run_batted_in')),
                    safe_value(row.get('sacrifice_bunts')),
                    safe_value(row.get('sacrifice_fly')),
                    safe_value(row.get('base_on_balls')),
                    safe_value(row.get('intentional_base_on_balls')),
                    safe_value(row.get('hit_by_pitch')),
                    safe_value(row.get('strikeout')),
                    safe_value(row.get('ground_into_double_play')),
                    safe_value(row.get('slugging_percentage')),
                    safe_value(row.get('on_base_percentage')),
                    safe_value(row.get('on_base_plus_slugging')),
                    safe_value(row.get('multi_hits')),
                    safe_value(row.get('runners_in_scoring_position')),
                    safe_value(row.get('pinch_hit_batting_average')),
                    safe_value(row.get('extra_base_hits')),
                    safe_value(row.get('ground_outs')),
                    safe_value(row.get('air_outs')),
                    safe_value(row.get('go_ao')),
                    safe_value(row.get('gw_rbi')),
                    safe_value(row.get('bb_k')),
                    safe_value(row.get('p_pa')),
                    safe_value(row.get('isop')),
                    safe_value(row.get('extended_runs')),
                    safe_value(row.get('gross_production_average')),
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
        logging.error(f"  ❌ 타자 통계 저장 실패: {e}")
        import traceback
        logging.error(traceback.format_exc())
        return False, 0


def main():
    """메인 함수"""
    logging.info("=" * 60)
    logging.info("💾 KBO 공식 통계 DB 저장 시작 (전체 스키마, UPSERT)")
    logging.info("=" * 60)
    
    try:
        # DB 연결
        conn = sqlite3.connect(DB_PATH)
        logging.info(f"📂 DB 연결: {DB_PATH}")
        
        # 테이블 생성
        create_tables(conn)
        
        # 타자 통계 저장
        batter_csv = CSV_DIR / f'batter_stats_{datetime.now().year}.csv'
        if batter_csv.exists():
            success, count = save_batter_stats(conn, batter_csv)
            if not success:
                return False, 0
        else:
            logging.warning(f"⚠️ 타자 통계 파일 없음: {batter_csv}")
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
