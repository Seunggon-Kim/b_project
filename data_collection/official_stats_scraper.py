"""
KBO 공식 기록 크롤러
KBO 공식 웹사이트(www.koreabaseball.com)에서 팀 순위, 선수 기록 등을 수집

사용법:
    python official_stats_scraper.py --year 2025
    python official_stats_scraper.py --year 2025 --type team
    python official_stats_scraper.py --year 2025 --type player
"""

import requests
from bs4 import BeautifulSoup
import pandas as pd
import argparse
import sys
from pathlib import Path
from datetime import datetime
import time

# 프로젝트 루트 경로
PROJECT_ROOT = Path(__file__).parent.parent
SAVE_DIR = PROJECT_ROOT / 'crawler' / 'save' / 'official_stats'

# KBO 공식 웹사이트 URL
KBO_BASE_URL = "https://www.koreabaseball.com"
TEAM_RANKING_URL = f"{KBO_BASE_URL}/Record/TeamRank/TeamRankDaily.aspx"
BATTER_STATS_URL = f"{KBO_BASE_URL}/Record/Player/HitterBasic/Basic1.aspx"
PITCHER_STATS_URL = f"{KBO_BASE_URL}/Record/Player/PitcherBasic/Basic1.aspx"

# User-Agent 설정 (크롤링 차단 방지)
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
}


def get_team_rankings(year=2025):
    """
    팀 순위 정보 수집
    
    Args:
        year: 시즌 연도
    
    Returns:
        DataFrame: 팀 순위 데이터
    """
    print(f"\n📊 {year}년 팀 순위 수집 중...")
    
    try:
        params = {
            'gyear': year
        }
        
        response = requests.get(TEAM_RANKING_URL, params=params, headers=HEADERS)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # 테이블 찾기
        table = soup.find('table', class_='tData')
        
        if not table:
            print("⚠️ 팀 순위 테이블을 찾을 수 없습니다.")
            return None
        
        # 테이블 파싱
        headers = []
        header_row = table.find('thead').find('tr')
        for th in header_row.find_all('th'):
            headers.append(th.text.strip())
        
        rows = []
        tbody = table.find('tbody')
        for tr in tbody.find_all('tr'):
            row = []
            for td in tr.find_all('td'):
                row.append(td.text.strip())
            if row:
                rows.append(row)
        
        # DataFrame 생성
        df = pd.DataFrame(rows, columns=headers)
        
        print(f"✅ {len(df)}개 팀 순위 수집 완료")
        return df
        
    except Exception as e:
        print(f"❌ 팀 순위 수집 실패: {e}")
        return None


def get_batter_stats(year=2025):
    """
    타자 기록 수집
    
    Args:
        year: 시즌 연도
    
    Returns:
        DataFrame: 타자 기록 데이터
    """
    print(f"\n⚾ {year}년 타자 기록 수집 중...")
    
    try:
        params = {
            'gyear': year
        }
        
        response = requests.get(BATTER_STATS_URL, params=params, headers=HEADERS)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # 테이블 찾기
        table = soup.find('table', class_='tData')
        
        if not table:
            print("⚠️ 타자 기록 테이블을 찾을 수 없습니다.")
            return None
        
        # 테이블 파싱
        headers = []
        header_row = table.find('thead').find('tr')
        for th in header_row.find_all('th'):
            headers.append(th.text.strip())
        
        rows = []
        tbody = table.find('tbody')
        for tr in tbody.find_all('tr'):
            row = []
            for td in tr.find_all('td'):
                row.append(td.text.strip())
            if row:
                rows.append(row)
        
        # DataFrame 생성
        df = pd.DataFrame(rows, columns=headers)
        
        print(f"✅ {len(df)}명 타자 기록 수집 완료")
        return df
        
    except Exception as e:
        print(f"❌ 타자 기록 수집 실패: {e}")
        return None


def get_pitcher_stats(year=2025):
    """
    투수 기록 수집
    
    Args:
        year: 시즌 연도
    
    Returns:
        DataFrame: 투수 기록 데이터
    """
    print(f"\n🎯 {year}년 투수 기록 수집 중...")
    
    try:
        params = {
            'gyear': year
        }
        
        response = requests.get(PITCHER_STATS_URL, params=params, headers=HEADERS)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # 테이블 찾기
        table = soup.find('table', class_='tData')
        
        if not table:
            print("⚠️ 투수 기록 테이블을 찾을 수 없습니다.")
            return None
        
        # 테이블 파싱
        headers = []
        header_row = table.find('thead').find('tr')
        for th in header_row.find_all('th'):
            headers.append(th.text.strip())
        
        rows = []
        tbody = table.find('tbody')
        for tr in tbody.find_all('tr'):
            row = []
            for td in tr.find_all('td'):
                row.append(td.text.strip())
            if row:
                rows.append(row)
        
        # DataFrame 생성
        df = pd.DataFrame(rows, columns=headers)
        
        print(f"✅ {len(df)}명 투수 기록 수집 완료")
        return df
        
    except Exception as e:
        print(f"❌ 투수 기록 수집 실패: {e}")
        return None


def save_to_csv(df, filename):
    """
    DataFrame을 CSV 파일로 저장
    
    Args:
        df: DataFrame
        filename: 파일명
    """
    if df is None or df.empty:
        print(f"⚠️ 저장할 데이터가 없습니다: {filename}")
        return False
    
    # 저장 디렉토리 생성
    SAVE_DIR.mkdir(parents=True, exist_ok=True)
    
    filepath = SAVE_DIR / filename
    
    try:
        df.to_csv(filepath, index=False, encoding='utf-8-sig')
        print(f"💾 저장 완료: {filepath}")
        return True
    except Exception as e:
        print(f"❌ 저장 실패: {e}")
        return False


def main():
    """메인 함수"""
    parser = argparse.ArgumentParser(description='KBO 공식 기록 크롤러')
    parser.add_argument('--year', type=int, default=2025, help='시즌 연도 (기본값: 2025)')
    parser.add_argument('--type', type=str, choices=['team', 'player', 'all'], 
                       default='all', help='수집할 데이터 타입')
    
    args = parser.parse_args()
    
    print("=" * 60)
    print(f"KBO 공식 기록 크롤러 - {args.year}년")
    print("=" * 60)
    
    success_count = 0
    
    # 팀 순위 수집
    if args.type in ['team', 'all']:
        df_team = get_team_rankings(args.year)
        if save_to_csv(df_team, f'team_rankings_{args.year}.csv'):
            success_count += 1
        time.sleep(1)  # 서버 부하 방지
    
    # 선수 기록 수집
    if args.type in ['player', 'all']:
        # 타자 기록
        df_batter = get_batter_stats(args.year)
        if save_to_csv(df_batter, f'batter_stats_{args.year}.csv'):
            success_count += 1
        time.sleep(1)
        
        # 투수 기록
        df_pitcher = get_pitcher_stats(args.year)
        if save_to_csv(df_pitcher, f'pitcher_stats_{args.year}.csv'):
            success_count += 1
    
    print("\n" + "=" * 60)
    print(f"✅ 수집 완료: {success_count}개 파일 저장")
    print(f"📁 저장 위치: {SAVE_DIR}")
    print("=" * 60)


if __name__ == '__main__':
    main()
