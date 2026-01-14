"""
이메일 알림 발송
KBO 통계 수집 결과를 이메일로 전송

사용법:
    python email_notifier.py --success --batter 450
    python email_notifier.py --fail --error "크롤링 실패"
"""

import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime
import argparse
import json
import logging
from pathlib import Path
import os

# 프로젝트 루트 경로
PROJECT_ROOT = Path(__file__).parent.parent
CONFIG_FILE = PROJECT_ROOT / 'config' / 'email_config.json'

# 로그 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

# 수신자 이메일 (고정)
RECIPIENT_EMAIL = "your-email@gmail.com"


def load_email_config():
    """이메일 설정 로드"""
    if not CONFIG_FILE.exists():
        logging.error(f"❌ 설정 파일 없음: {CONFIG_FILE}")
        logging.info("📝 config/email_config.json 파일을 생성하고 다음 내용을 입력하세요:")
        logging.info("""
{
    "smtp_server": "smtp.gmail.com",
    "smtp_port": 587,
    "sender_email": "your_email@gmail.com",
    "sender_password": "your_app_password"
}
        """)
        return None
    
    try:
        with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
            config = json.load(f)
        return config
    except Exception as e:
        logging.error(f"❌ 설정 파일 로드 실패: {e}")
        return None


def send_success_email(batter_count, pitcher_count=0, team_count=0):
    """성공 알림 이메일 발송"""
    config = load_email_config()
    if not config:
        return False
    
    # 이메일 내용
    subject = f"✅ KBO 공식 통계 수집 완료 - {datetime.now().strftime('%Y-%m-%d')}"
    
    body = f"""
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📊 KBO 공식 통계 수집 완료
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

📅 수집 일시: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

📈 수집 결과:
  ⚾ 타자: {batter_count}명
  🎯 투수: {pitcher_count}명
  🏆 팀 순위: {team_count}개 팀

💾 저장 위치:
  - DB: database/kbo_stats.db
  - CSV: crawler/save/official_stats/

✅ 모든 데이터가 정상적으로 저장되었습니다.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
KBO Stats Auto Collector
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""
    
    return send_email(config, subject, body)


def send_failure_email(error_message):
    """실패 알림 이메일 발송"""
    config = load_email_config()
    if not config:
        return False
    
    # 이메일 내용
    subject = f"❌ KBO 통계 수집 실패 - {datetime.now().strftime('%Y-%m-%d')}"
    
    body = f"""
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
⚠️ KBO 공식 통계 수집 실패
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

📅 시도 일시: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

❌ 오류 내용:
{error_message}

📋 로그 파일: logs/selenium_batter_{datetime.now().strftime('%Y%m%d')}.log

🔧 조치 필요:
  - 로그 파일 확인
  - 수동으로 재실행 권장

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
KBO Stats Auto Collector
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""
    
    return send_email(config, subject, body)


def send_email(config, subject, body):
    """이메일 발송"""
    try:
        # 이메일 메시지 생성
        msg = MIMEMultipart()
        msg['From'] = config['sender_email']
        msg['To'] = RECIPIENT_EMAIL
        msg['Subject'] = subject
        
        msg.attach(MIMEText(body, 'plain', 'utf-8'))
        
        # SMTP 서버 연결 및 발송
        logging.info(f"📧 이메일 발송 중: {RECIPIENT_EMAIL}")
        
        with smtplib.SMTP(config['smtp_server'], config['smtp_port']) as server:
            server.starttls()
            server.login(config['sender_email'], config['sender_password'])
            server.send_message(msg)
        
        logging.info("✅ 이메일 발송 완료")
        return True
        
    except Exception as e:
        logging.error(f"❌ 이메일 발송 실패: {e}")
        return False


def main():
    """메인 함수"""
    parser = argparse.ArgumentParser(description='KBO 통계 수집 이메일 알림')
    parser.add_argument('--success', action='store_true', help='성공 알림')
    parser.add_argument('--fail', action='store_true', help='실패 알림')
    parser.add_argument('--batter', type=int, default=0, help='타자 수')
    parser.add_argument('--pitcher', type=int, default=0, help='투수 수')
    parser.add_argument('--team', type=int, default=0, help='팀 수')
    parser.add_argument('--error', type=str, default='알 수 없는 오류', help='오류 메시지')
    
    args = parser.parse_args()
    
    if args.success:
        return send_success_email(args.batter, args.pitcher, args.team)
    elif args.fail:
        return send_failure_email(args.error)
    else:
        logging.error("❌ --success 또는 --fail 옵션 필요")
        return False


if __name__ == '__main__':
    success = main()
    
    import sys
    sys.exit(0 if success else 1)
