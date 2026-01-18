import sqlite3
import pandas as pd
from pathlib import Path
from datetime import datetime

# 프로젝트 루트 경로
PROJECT_ROOT = Path(__file__).parent
DB_PATH = PROJECT_ROOT / 'database' / 'kbo_stats.db'

def migrate():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    print("🚀 DB 마이그레이션 시작: K% 및 BB% 추가")
    
    # 1. 타자 통계 마이그레이션
    print("📊 타자 통계 마이그레이션 중...")
    try:
        df_batters = pd.read_sql("SELECT * FROM kbo_official_batter_stats", conn)
        
        # 신규 컬럼 계산
        def calc_k_percent(row):
            pa = row['plate_appearance']
            ibb = row['intentional_base_on_balls']
            so = row['strikeout']
            if pa and ibb is not None and pa > ibb and so is not None:
                return round(so / (pa - ibb) * 100, 1)
            return None

        def calc_bb_percent(row):
            pa = row['plate_appearance']
            ibb = row['intentional_base_on_balls']
            bb = row['base_on_balls']
            if pa and ibb is not None and pa > ibb and bb is not None:
                return round((bb - ibb) / (pa - ibb) * 100, 1)
            return None

        df_batters['strikeout_per_pa'] = df_batters.apply(calc_k_percent, axis=1)
        df_batters['base_on_balls_per_pa'] = df_batters.apply(calc_bb_percent, axis=1)
        
        # 테이블 재생성
        cursor.execute("DROP TABLE IF EXISTS kbo_official_batter_stats_old")
        cursor.execute("ALTER TABLE kbo_official_batter_stats RENAME TO kbo_official_batter_stats_old")
        
        # 새 테이블 생성 (가장 좋은 방법은 kbo_to_db.py의 SQL을 따르는 것)
        cursor.execute("""
        CREATE TABLE kbo_official_batter_stats (
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
            strikeout_per_pa REAL,
            base_on_balls_per_pa REAL,
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
        
        # 데이터 삽입 (순서 주의 - gw_rbi 뒤에 삽입)
        cols_ordered = [
            'player_id', 'season', 'player_name', 'player_team', 'batting_average',
            'games', 'plate_appearance', 'at_bat', 'run', 'single', 'double', 'triple',
            'home_run', 'total_bases', 'run_batted_in', 'sacrifice_bunts',
            'sacrifice_fly', 'base_on_balls', 'intentional_base_on_balls',
            'hit_by_pitch', 'strikeout', 'ground_into_double_play',
            'slugging_percentage', 'on_base_percentage', 'on_base_plus_slugging',
            'multi_hits', 'runners_in_scoring_position', 'pinch_hit_batting_average',
            'extra_base_hits', 'ground_outs', 'air_outs', 'go_ao', 'gw_rbi',
            'strikeout_per_pa', 'base_on_balls_per_pa',
            'bb_k', 'p_pa', 'isop', 'extended_runs', 'gross_production_average',
            'created_at', 'updated_at'
        ]
        df_batters[cols_ordered].to_sql('kbo_official_batter_stats', conn, if_exists='append', index=False)
        cursor.execute("DROP TABLE kbo_official_batter_stats_old")
        print("  ✅ 타자 통계 마이그레이션 완료")
    except Exception as e:
        print(f"  ❌ 타자 통계 실패: {e}")
        conn.rollback()

    # 2. 투수 통계 마이그레이션
    print("📊 투수 통계 마이그레이션 중...")
    try:
        df_pitchers = pd.read_sql("SELECT * FROM kbo_official_pitcher_stats", conn)
        
        # 신규 컬럼 계산 (투수는 total_batters_faced 사용)
        def calc_k_percent_p(row):
            tbf = row['total_batters_faced']
            ibb = row['intentional_base_on_balls']
            so = row['strikeout']
            if tbf and ibb is not None and tbf > ibb and so is not None:
                return round(so / (tbf - ibb) * 100, 1)
            return None

        def calc_bb_percent_p(row):
            tbf = row['total_batters_faced']
            ibb = row['intentional_base_on_balls']
            bb = row['base_on_balls']
            if tbf and ibb is not None and tbf > ibb and bb is not None:
                return round((bb - ibb) / (tbf - ibb) * 100, 1)
            return None

        df_pitchers['strikeout_per_pa'] = df_pitchers.apply(calc_k_percent_p, axis=1)
        df_pitchers['base_on_balls_per_pa'] = df_pitchers.apply(calc_bb_percent_p, axis=1)
        
        # 테이블 재생성
        cursor.execute("DROP TABLE IF EXISTS kbo_official_pitcher_stats_old")
        cursor.execute("ALTER TABLE kbo_official_pitcher_stats RENAME TO kbo_official_pitcher_stats_old")
        
        cursor.execute("""
        CREATE TABLE kbo_official_pitcher_stats (
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
        
        cols_ordered_p = [
            'player_id', 'season', 'player_name', 'player_team', 'earned_run_average',
            'games', 'wins', 'losses', 'save', 'hold', 'winning_percentage',
            'innings_pitched', 'hits', 'home_run', 'base_on_balls', 'hit_by_pitch',
            'strikeout', 'run', 'earned_run', 'walks_plus_hits_per_inning_pitched',
            'complete_game', 'shutout', 'quality_start', 'blown_save',
            'total_batters_faced', 'number_of_pitchers', 'batting_average',
            'double', 'triple', 'sacrifice_bunts', 'sacrifice_fly',
            'intentional_base_on_balls', 'wild_pitch', 'balk', 'games_started',
            'wins_game_started', 'wins_game_relieved', 'games_finished',
            'save_opportunity', 'total_saves', 'ground_into_double_play',
            'ground_outs', 'air_outs', 'go_ao', 'batting_average_on_balls_in_play',
            'p_g', 'p_ip', 'k_9', 'bb_9', 
            'strikeout_per_pa', 'base_on_balls_per_pa',
            'k_bb', 'on_base_percentage', 'slugging_percentage', 'on_base_plus_slugging',
            'created_at', 'updated_at'
        ]
        df_pitchers[cols_ordered_p].to_sql('kbo_official_pitcher_stats', conn, if_exists='append', index=False)
        cursor.execute("DROP TABLE kbo_official_pitcher_stats_old")
        print("  ✅ 투수 통계 마이그레이션 완료")
    except Exception as e:
        print(f"  ❌ 투수 통계 실패: {e}")
        conn.rollback()

    conn.commit()
    conn.close()
    print("✨ 마이그레이션 종료")

if __name__ == '__main__':
    migrate()
