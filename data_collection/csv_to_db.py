"""
CSV 파일을 SQLite 데이터베이스로 변환하는 스크립트

사용법:
    python csv_to_db.py <csv_file_path>
    
예시:
    python csv_to_db.py ../crawler/save/2025.csv
"""

import sqlite3
import pandas as pd
import sys
from pathlib import Path
from datetime import datetime

# 프로젝트 루트 경로
PROJECT_ROOT = Path(__file__).parent.parent
DB_PATH = PROJECT_ROOT / 'database' / 'kbo_stats.db'


def parse_game_id(game_id):
    """
    게임 ID에서 정보 추출
    예: 20250110LGKT0 -> 날짜: 2025-01-10, 홈팀: LG, 원정팀: KT
    """
    try:
        date_str = game_id[:8]  # YYYYMMDD
        teams = game_id[8:-1]   # 팀 코드들
        
        game_date = datetime.strptime(date_str, '%Y%m%d').date()
        
        # 팀 코드는 가변 길이이므로 실제 데이터 확인 후 조정 필요
        # 임시로 2자리씩 분리
        home_team = teams[:len(teams)//2] if len(teams) > 2 else teams[:2]
        away_team = teams[len(teams)//2:] if len(teams) > 2 else teams[2:]
        
        return game_date, home_team, away_team
    except Exception as e:
        print(f"게임 ID 파싱 오류: {game_id}, {e}")
        return None, None, None


def import_csv_to_db(csv_path, db_path=DB_PATH):
    """
    CSV 파일을 읽어 데이터베이스에 저장
    
    Args:
        csv_path: CSV 파일 경로
        db_path: 데이터베이스 파일 경로
    """
    csv_file = Path(csv_path)
    
    if not csv_file.exists():
        print(f"❌ CSV 파일을 찾을 수 없습니다: {csv_path}")
        return False
    
    print(f"📂 CSV 파일 읽기: {csv_file.name}")
    
    try:
        # CSV 파일 읽기 (인코딩 자동 감지)
        try:
            df = pd.read_csv(csv_file, encoding='utf-8')
        except UnicodeDecodeError:
            df = pd.read_csv(csv_file, encoding='cp949')
        
        print(f"✅ 총 {len(df):,}개 행 로드됨")
        print(f"📊 컬럼: {list(df.columns)}")
        
        # 데이터베이스 연결
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # 게임 정보 추출 및 저장
        print("\n🎮 경기 정보 처리 중...")
        games_data = []
        game_ids = df['game_id'].unique() if 'game_id' in df.columns else []
        
        for game_id in game_ids:
            game_date, home_team, away_team = parse_game_id(game_id)
            if game_date:
                game_data = df[df['game_id'] == game_id]
                
                # 최종 점수 계산 (마지막 행의 점수)
                last_row = game_data.iloc[-1]
                home_score = last_row.get('home_score', 0)
                away_score = last_row.get('away_score', 0)
                
                games_data.append({
                    'game_id': game_id,
                    'game_date': game_date,
                    'season': game_date.year,
                    'home_team_id': home_team,
                    'away_team_id': away_team,
                    'home_score': home_score,
                    'away_score': away_score
                })
        
        # 게임 정보 DB 저장
        if games_data:
            games_df = pd.DataFrame(games_data)
            games_df.to_sql('games', conn, if_exists='append', index=False)
            print(f"✅ {len(games_data):,}개 경기 정보 저장 완료")
        
        # Play-by-Play 데이터 저장
        print("\n⚾ Play-by-Play 데이터 저장 중...")
        
        # 사용자 요청 컬럼 목록
        target_columns = [
            'pitch_type', 'pitcher', 'batter', 'pitcher_ID', 'batter_ID', 'speed',
            'pitch_result', 'pa_result', 'pa_result_detail', 'description',
            'balls', 'strikes', 'outs', 'inning', 'inning_topbot', 'score_away',
            'score_home', 'outs_on_play', 'runs_scored', 'stands', 'throws',
            'on_1b', 'on_2b', 'on_3b', 'pos_1', 'pos_2', 'pos_3', 'pos_4', 'pos_5',
            'pos_6', 'pos_7', 'pos_8', 'pos_9', 'on_1b_id', 'on_2b_id', 'on_3b_id',
            'pos_1_id', 'pos_2_id', 'pos_3_id', 'pos_4_id', 'pos_5_id', 'pos_6_id',
            'pos_7_id', 'pos_8_id', 'pos_9_id', 'px', 'pz', 'pfx_x', 'pfx_z',
            'pfx_x_raw', 'pfx_z_raw', 'x0', 'z0', 'sz_top', 'sz_bot', 'y0',
            'vx0', 'vy0', 'vz0', 'ax', 'ay', 'az', 'game_date', 'home', 'away',
            'home_alias', 'away_alias', 'stadium', 'referee', 'pa_number',
            'pitch_number', 'pitchID', 'gameID'
        ]
        
        # 존재하는 컬럼만 선택
        available_columns = [col for col in target_columns if col in df.columns]
        df_pbp = df[available_columns].copy()
        
        # DB에 저장 (중복 방지를 위해 append 사용)
        df_pbp.to_sql('play_by_play', conn, if_exists='append', index=False)
        print(f"✅ {len(df_pbp):,}개 Play-by-Play 레코드 저장 완료")
        
        conn.commit()
        conn.close()
        
        print(f"\n🎉 데이터베이스 저장 완료: {db_path}")
        return True
        
    except Exception as e:
        print(f"❌ 오류 발생: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """메인 함수"""
    if len(sys.argv) < 2:
        print("사용법: python csv_to_db.py <csv_file_path>")
        print("예시: python csv_to_db.py ../crawler/save/2025.csv")
        sys.exit(1)
    
    csv_path = sys.argv[1]
    
    print("=" * 60)
    print("KBO 데이터 CSV → DB 변환")
    print("=" * 60)
    
    success = import_csv_to_db(csv_path)
    
    if success:
        print("\n✅ 변환 완료!")
    else:
        print("\n❌ 변환 실패")
        sys.exit(1)


if __name__ == '__main__':
    main()
