"""
빠진 경기 파일 찾기 스크립트
"""

from pathlib import Path
import re

# 경로 설정
CSV_DIR = Path('C:/Users/USERNAME/Desktop/b_project/crawler/save/2025')

# 모든 CSV 파일 목록
csv_files = list(CSV_DIR.glob('*.csv'))
print(f"총 {len(csv_files)}개 CSV 파일 발견\n")

# 파일명에서 경기 정보 추출
game_info = []
for file in csv_files:
    # 파일명 패턴: YYYYMMDDTEAMTEAM0YYYY.csv
    # 예: 20250322HHKT02025.csv
    match = re.match(r'(\d{8})([A-Z]{2,4})([A-Z]{2,4})(\d)(\d{4})\.csv', file.name)
    if match:
        date = match.group(1)
        home = match.group(2)
        away = match.group(3)
        game_num = match.group(4)
        year = match.group(5)
        game_info.append({
            'date': date,
            'home': home,
            'away': away,
            'game_num': game_num,
            'filename': file.name
        })

# 날짜별로 정렬
game_info.sort(key=lambda x: (x['date'], x['home'], x['away']))

# 날짜별 경기 수 확인
from collections import Counter
dates = [g['date'] for g in game_info]
date_counts = Counter(dates)

print("날짜별 경기 수:")
print("=" * 60)

# 5경기 미만인 날짜 찾기 (보통 하루에 5경기)
unusual_dates = []
for date, count in sorted(date_counts.items()):
    if count < 5:
        print(f"{date}: {count}경기 ⚠️")
        unusual_dates.append(date)
    else:
        # 처음 10개와 마지막 10개만 출력
        if len(unusual_dates) < 10 or date in list(sorted(date_counts.keys()))[-10:]:
            print(f"{date}: {count}경기")

print("\n" + "=" * 60)
print(f"총 {len(date_counts)}일 동안 경기 진행")
print(f"총 {len(game_info)}개 경기 파일")
print(f"예상 경기 수: 720개")
print(f"빠진 경기: {720 - len(game_info)}개")

# 경기가 적은 날짜의 상세 정보
if unusual_dates:
    print("\n" + "=" * 60)
    print("경기가 적은 날짜 상세:")
    print("=" * 60)
    for date in unusual_dates[:20]:  # 처음 20개만
        games = [g for g in game_info if g['date'] == date]
        print(f"\n{date} ({len(games)}경기):")
        for g in games:
            print(f"  - {g['home']} vs {g['away']} ({g['filename']})")
