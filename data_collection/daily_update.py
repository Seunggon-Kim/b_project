"""
일일 자동 업데이트 스크립트
매일 전날 경기 데이터를 크롤링하고 DB에 저장

사용법:
    python daily_update.py
    
Windows Task Scheduler 설정:
    - 매일 오전 6시 실행 (전날 경기 종료 후)
    - 작업: python C:\Users\김승곤\Desktop\b_project\data_collection\daily_update.py
"""

import subprocess
import sys
from pathlib import Path
from datetime import datetime, timedelta
import logging

# 프로젝트 루트 경로
PROJECT_ROOT = Path(__file__).parent.parent
CRAWLER_DIR = PROJECT_ROOT / 'crawler'
LOG_DIR = PROJECT_ROOT / 'logs'

# 로그 디렉토리 생성
LOG_DIR.mkdir(exist_ok=True)

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(LOG_DIR / f'daily_update_{datetime.now():%Y%m%d}.log'),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)


def get_yesterday_date():
    """어제 날짜를 YYYYMMDD 형식으로 반환"""
    yesterday = datetime.now() - timedelta(days=1)
    return yesterday.strftime('%Y%m%d')


def run_crawler(start_date, end_date):
    """
    크롤러 실행
    
    Args:
        start_date: 시작일 (YYYYMMDD)
        end_date: 종료일 (YYYYMMDD)
    
    Returns:
        bool: 성공 여부
    """
    try:
        logger.info(f"크롤러 실행: {start_date} ~ {end_date}")
        
        # pbp.py 실행
        cmd = [
            sys.executable,  # 현재 Python 인터프리터
            str(CRAWLER_DIR / 'pbp.py'),
            '-f', start_date,
            '-t', end_date,
            '-s', str(CRAWLER_DIR / 'save')
        ]
        
        logger.info(f"명령어: {' '.join(cmd)}")
        
        result = subprocess.run(
            cmd,
            cwd=str(CRAWLER_DIR),
            capture_output=True,
            text=True,
            timeout=3600  # 1시간 타임아웃
        )
        
        if result.returncode == 0:
            logger.info("✅ 크롤러 실행 성공")
            logger.debug(f"출력: {result.stdout}")
            return True
        else:
            logger.error(f"❌ 크롤러 실행 실패: {result.stderr}")
            return False
            
    except subprocess.TimeoutExpired:
        logger.error("❌ 크롤러 실행 타임아웃 (1시간 초과)")
        return False
    except Exception as e:
        logger.error(f"❌ 크롤러 실행 오류: {e}")
        return False


def import_to_db(date_str):
    """
    수집한 CSV 파일을 DB로 임포트
    
    Args:
        date_str: 날짜 (YYYYMMDD)
    
    Returns:
        bool: 성공 여부
    """
    try:
        logger.info(f"DB 임포트 시작: {date_str}")
        
        # CSV 파일 경로 찾기
        year = date_str[:4]
        csv_files = list((CRAWLER_DIR / 'save' / year).glob(f'{date_str}*.csv'))
        
        if not csv_files:
            logger.warning(f"⚠️ CSV 파일을 찾을 수 없습니다: {date_str}")
            return False
        
        # csv_to_db.py 실행
        from csv_to_db import import_csv_to_db
        
        success_count = 0
        for csv_file in csv_files:
            logger.info(f"파일 처리: {csv_file.name}")
            if import_csv_to_db(csv_file):
                success_count += 1
        
        logger.info(f"✅ DB 임포트 완료: {success_count}/{len(csv_files)} 파일")
        return success_count > 0
        
    except Exception as e:
        logger.error(f"❌ DB 임포트 오류: {e}")
        return False


def send_notification(success, message):
    """
    알림 전송 (선택사항)
    
    Args:
        success: 성공 여부
        message: 메시지
    """
    # 이메일, Slack, Discord 등으로 알림 전송 가능
    # 현재는 로그만 기록
    if success:
        logger.info(f"📧 알림: {message}")
    else:
        logger.error(f"📧 알림: {message}")


def main():
    """메인 함수"""
    logger.info("=" * 60)
    logger.info("KBO 일일 자동 업데이트 시작")
    logger.info("=" * 60)
    
    # 어제 날짜
    yesterday = get_yesterday_date()
    logger.info(f"📅 대상 날짜: {yesterday}")
    
    # 1. 크롤러 실행
    crawler_success = run_crawler(yesterday, yesterday)
    
    if not crawler_success:
        message = f"크롤러 실행 실패: {yesterday}"
        send_notification(False, message)
        logger.error(message)
        sys.exit(1)
    
    # 2. DB 임포트
    import_success = import_to_db(yesterday)
    
    if not import_success:
        message = f"DB 임포트 실패: {yesterday}"
        send_notification(False, message)
        logger.error(message)
        sys.exit(1)
    
    # 3. 선수 통계 계산 업데이트
    try:
        logger.info("선수 통계 업데이트 시작...")
        from calculate_stats import calculate_stats
        calculate_stats()
        logger.info("✅ 선수 통계 업데이트 완료")
    except Exception as e:
        logger.error(f"❌ 선수 통계 업데이트 오류: {e}")
    
    # 4. 완료
    message = f"일일 업데이트 완료: {yesterday}"
    send_notification(True, message)
    logger.info("=" * 60)
    logger.info("✅ 일일 업데이트 성공!")
    logger.info("=" * 60)


if __name__ == '__main__':
    main()
