"""
개별 CSV 파일들을 하나로 병합하는 스크립트

사용법:
    python merge_csv.py
"""

import pandas as pd
from pathlib import Path
import sys

# 경로 설정
PROJECT_ROOT = Path(__file__).parent.parent
CSV_DIR = PROJECT_ROOT / 'crawler' / 'save' / '2025'
OUTPUT_FILE = PROJECT_ROOT / 'crawler' / 'save' / 'kbo_2025_regular_season.csv'

def merge_csv_files():
    """모든 CSV 파일을 하나로 병합"""
    
    print("=" * 60)
    print("KBO 2025 CSV 파일 병합")
    print("=" * 60)
    
    # CSV 파일 찾기
    csv_files = list(CSV_DIR.glob('*.csv'))
    print(f"\n📂 총 {len(csv_files)}개 CSV 파일 발견")
    
    if len(csv_files) == 0:
        print("❌ CSV 파일을 찾을 수 없습니다!")
        return False
    
    # 파일 병합
    dfs = []
    success_count = 0
    error_count = 0
    error_files = []
    
    print("\n📊 파일 읽기 중...")
    for i, file in enumerate(csv_files, 1):
        try:
            # CP949 인코딩으로 읽기 (Windows 한글)
            df = pd.read_csv(file, encoding='cp949')
            dfs.append(df)
            success_count += 1
            
            if i % 100 == 0:
                print(f"  진행: {i}/{len(csv_files)} ({i/len(csv_files)*100:.1f}%)")
                
        except Exception as e:
            error_count += 1
            error_files.append(file.name)
            print(f"  ⚠️ 스킵: {file.name} - {str(e)[:50]}")
    
    print(f"\n✅ 성공: {success_count}개 파일")
    print(f"⚠️ 실패: {error_count}개 파일")
    
    if error_files:
        print("\n실패한 파일 목록:")
        for f in error_files:
            print(f"  - {f}")
    
    if len(dfs) == 0:
        print("\n❌ 읽을 수 있는 파일이 없습니다!")
        return False
    
    # 데이터 병합
    print("\n🔄 데이터 병합 중...")
    combined_df = pd.concat(dfs, ignore_index=True)
    
    print(f"✅ 총 {len(combined_df):,}개 행 병합 완료")
    print(f"📊 컬럼 수: {len(combined_df.columns)}개")
    
    # 파일 저장
    print(f"\n💾 저장 중: {OUTPUT_FILE.name}")
    combined_df.to_csv(OUTPUT_FILE, index=False, encoding='utf-8-sig')
    
    file_size_mb = OUTPUT_FILE.stat().st_size / (1024 * 1024)
    print(f"✅ 저장 완료! (파일 크기: {file_size_mb:.2f} MB)")
    
    # 데이터 미리보기
    print("\n" + "=" * 60)
    print("데이터 미리보기 (첫 5행)")
    print("=" * 60)
    print(combined_df.head())
    
    print("\n" + "=" * 60)
    print("컬럼 정보")
    print("=" * 60)
    print(combined_df.info())
    
    return True

if __name__ == '__main__':
    try:
        success = merge_csv_files()
        if success:
            print("\n" + "=" * 60)
            print("🎉 병합 완료!")
            print(f"📁 파일 위치: {OUTPUT_FILE}")
            print("=" * 60)
        else:
            print("\n❌ 병합 실패")
            sys.exit(1)
    except Exception as e:
        print(f"\n❌ 오류 발생: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
