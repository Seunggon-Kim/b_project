"""
수집된 경기와 예상 경기 비교 분석
"""

from pathlib import Path
from collections import Counter
import re

CSV_DIR = Path('C:/Users/김승곤/Desktop/b_project/crawler/save/2025')

# 모든 CSV 파일 목록
csv_files = list(CSV_DIR.glob('*.csv'))
print(f"총 {len(csv_files)}개 CSV 파일\n")

# 날짜별 경기 수 집계
dates = []
for file in csv_files:
    match = re.match(r'(\d{8})', file.name)
    if match:
        dates.append(match.group(1))

date_counts = Counter(dates)

# 통계
print("=" * 60)
print("날짜별 경기 수 통계")
print("=" * 60)

counts_summary = Counter(date_counts.values())
for count in sorted(counts_summary.keys()):
    print(f"{count}경기 날짜: {counts_summary[count]}일")

print(f"\n총 경기일: {len(date_counts)}일")
print(f"총 경기 수: {sum(date_counts.values())}경기")

# 예상 경기 수 계산
# 10팀 * 144경기 / 2 = 720경기
expected = 720
actual = len(csv_files)
print(f"\n예상 경기: {expected}경기")
print(f"실제 파일: {actual}개")
print(f"차이: {expected - actual}개")

# 경기가 적은 날짜 (5경기 미만)
print("\n" + "=" * 60)
print("경기가 5경기 미만인 날짜")
print("=" * 60)

unusual_dates = []
for date in sorted(date_counts.keys()):
    if date_counts[date] < 5:
        unusual_dates.append((date, date_counts[date]))

for date, count in unusual_dates[:30]:  # 처음 30개만
    year = date[:4]
    month = date[4:6]
    day = date[6:8]
    print(f"{year}-{month}-{day}: {count}경기")

# 3월 30일 확인
print("\n" + "=" * 60)
print("3월 30일 상세")
print("=" * 60)

march_30_files = [f.name for f in csv_files if f.name.startswith('20250330')]
print(f"3월 30일 경기: {len(march_30_files)}개")
for f in march_30_files:
    print(f"  - {f}")

print("\n예상: 5경기")
print(f"실제: {len(march_30_files)}경기")
print(f"누락: {5 - len(march_30_files)}경기")

# 9월 24일 확인
print("\n" + "=" * 60)
print("9월 24일 상세 (보충 경기 의심)")
print("=" * 60)

sept_24_files = [f.name for f in csv_files if f.name.startswith('20250924')]
print(f"9월 24일 경기: {len(sept_24_files)}개")
for f in sept_24_files:
    print(f"  - {f}")
