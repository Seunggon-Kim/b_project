"""
이메일 알림 내용 미리보기
실제 발송 없이 이메일 내용만 확인
"""

import sys
from pathlib import Path
from datetime import datetime

# 프로젝트 루트 경로 추가
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT / 'data_collection'))

from email_notifier import get_data_counts

def preview_email():
    """이메일 내용 미리보기"""
    print("=" * 60)
    print("📧 이메일 알림 내용 미리보기")
    print("=" * 60)
    
    # 데이터 개수 자동 계산
    batter_count, pitcher_count, team_count = get_data_counts()
    
    # 이메일 제목
    subject = f"✅ KBO 공식 통계 수집 완료 - {datetime.now().strftime('%Y-%m-%d')}"
    
    # 이메일 본문
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
    
    print("\n📧 제목:")
    print(f"  {subject}")
    print("\n📄 본문:")
    print(body)
    print("=" * 60)
    print(f"\n✅ 타자 {batter_count}명 + 투수 {pitcher_count}명 = 총 {batter_count + pitcher_count}명")
    print("=" * 60)

if __name__ == '__main__':
    preview_email()
