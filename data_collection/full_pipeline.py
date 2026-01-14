"""
전체 파이프라인 자동 실행 스크립트
크롤링 → DB 저장 → 통계 계산을 한 번에 실행

사용법:
    python full_pipeline.py
"""
import subprocess
import sys
from pathlib import Path
import time

PROJECT_ROOT = Path(__file__).parent.parent
CRAWLER_DIR = PROJECT_ROOT / 'crawler'
DATA_COLLECTION_DIR = PROJECT_ROOT / 'data_collection'

def run_step(step_name, command, cwd=None):
    """단계별 실행"""
    print("\n" + "=" * 60)
    print(f"📌 {step_name}")
    print("=" * 60)
    
    try:
        result = subprocess.run(
            command,
            cwd=cwd or PROJECT_ROOT,
            shell=True,
            capture_output=True,
            text=True
        )
        
        if result.returncode == 0:
            print(f"✅ {step_name} 완료")
            if result.stdout:
                print(result.stdout)
            return True
        else:
            print(f"❌ {step_name} 실패")
            if result.stderr:
                print(result.stderr)
            return False
            
    except Exception as e:
        print(f"❌ {step_name} 오류: {e}")
        return False

def main():
    start_time = time.time()
    
    print("=" * 60)
    print("KBO 데이터 전체 파이프라인 실행")
    print("=" * 60)
    print("\n⚠️ 이 작업은 시간이 오래 걸릴 수 있습니다 (약 30분~1시간)")
    print("진행 중에는 중단하지 마세요.\n")
    
    # 1. 크롤링
    if not run_step(
        "1단계: 데이터 크롤링 (2025년 전체)",
        f'python pbp.py -f 20250101 -t 20251231 -j',
        cwd=CRAWLER_DIR
    ):
        print("\n❌ 파이프라인 실패: 크롤링 단계")
        return False
    
    # 2. CSV 병합 확인
    csv_file = CRAWLER_DIR / 'save' / '2025.csv'
    if not csv_file.exists():
        print(f"\n⚠️ 통합 CSV 파일이 없습니다: {csv_file}")
        print("개별 CSV 파일을 병합합니다...")
        
        if not run_step(
            "CSV 병합",
            f'python merge_csv.py',
            cwd=DATA_COLLECTION_DIR
        ):
            print("\n❌ CSV 병합 실패")
            return False
    
    # 3. DB 저장
    if not run_step(
        "2단계: 데이터베이스 저장",
        f'python csv_to_db.py "{csv_file}"',
        cwd=DATA_COLLECTION_DIR
    ):
        print("\n❌ 파이프라인 실패: DB 저장 단계")
        return False
    
    # 4. 통계 계산
    if not run_step(
        "3단계: 선수 통계 계산",
        f'python calculate_stats.py',
        cwd=DATA_COLLECTION_DIR
    ):
        print("\n❌ 파이프라인 실패: 통계 계산 단계")
        return False
    
    # 완료
    elapsed_time = time.time() - start_time
    minutes = int(elapsed_time // 60)
    seconds = int(elapsed_time % 60)
    
    print("\n" + "=" * 60)
    print("✅ 전체 파이프라인 완료!")
    print("=" * 60)
    print(f"⏱️ 소요 시간: {minutes}분 {seconds}초")
    print("\n다음 단계:")
    print("  - 대시보드 실행: cd dashboard && streamlit run Home.py")
    print("  - 데이터 확인: python show_data.py")
    
    return True

if __name__ == '__main__':
    success = main()
    sys.exit(0 if success else 1)
