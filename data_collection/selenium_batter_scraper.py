"""
KBO 공식 타자 통계 크롤러 (정확한 요구사항 반영)
- Basic1 (기본기록 1페이지) + Basic2 (기본기록 2페이지) + Detail (세부기록)
- 팀별 페이지네이션 지원
- player_id 추출
- 시즌 선택 지원 (--year, default=현재 연도)

사용법:
    python selenium_batter_scraper.py                  # 현재 연도
    python selenium_batter_scraper.py --year 2020      # 특정 시즌 백필
"""

import argparse
import time
import logging
from datetime import datetime
from pathlib import Path
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import Select
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager
import os
import pandas as pd

# 프로젝트 루트 경로
PROJECT_ROOT = Path(__file__).parent.parent

SAVE_DIR = PROJECT_ROOT / 'crawler' / 'save' / 'official_stats'
SAVE_DIR.mkdir(parents=True, exist_ok=True)

# 로그 설정
LOG_DIR = PROJECT_ROOT / 'logs'
LOG_DIR.mkdir(exist_ok=True)
log_file = LOG_DIR / f'selenium_batter_{datetime.now().strftime("%Y%m%d_%H%M%S")}.log'

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(log_file, encoding='utf-8'),
        logging.StreamHandler()
    ]
)

# KBO 팀 코드 (순서대로)
TEAM_CODES = ['LG', 'HH', 'SK', 'SS', 'NC', 'KT', 'LT', 'HT', 'OB', 'WO']

# 컬럼 매핑 (KBO 웹사이트 -> DB 스키마)
COLUMN_MAPPING = {
    '선수명': 'player_name',
    '팀명': 'player_team',
    'AVG': 'batting_average',
    'G': 'games',
    'PA': 'plate_appearance',
    'AB': 'at_bat',
    'R': 'run',
    'H': 'single',
    '2B': 'double',
    '3B': 'triple',
    'HR': 'home_run',
    'TB': 'total_bases',
    'RBI': 'run_batted_in',
    'SAC': 'sacrifice_bunts',
    'SF': 'sacrifice_fly',
    'BB': 'base_on_balls',
    'IBB': 'intentional_base_on_balls',
    'HBP': 'hit_by_pitch',
    'SO': 'strikeout',
    'GDP': 'ground_into_double_play',
    'SLG': 'slugging_percentage',
    'OBP': 'on_base_percentage',
    'OPS': 'on_base_plus_slugging',
    'MH': 'multi_hits',
    'RISP': 'runners_in_scoring_position',
    'PH-BA': 'pinch_hit_batting_average',
    'XBH': 'extra_base_hits',
    'GO': 'ground_outs',
    'AO': 'air_outs',
    'GO/AO': 'go_ao',
    'GW RBI': 'gw_rbi',
    'BB/K': 'bb_k',
    'P/PA': 'p_pa',
    'ISOP': 'isop',
    'XR': 'extended_runs',
    'GPA': 'gross_production_average'
}


def setup_driver():
    """Chrome 드라이버 설정"""
    options = Options()
    options.add_argument('--headless')
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    options.add_argument('--disable-gpu')
    options.add_argument('--window-size=1920,1080')
    
    # 서버(ARM 등)에서는 시스템 chromedriver를 사용합니다.
    # Google이 ARM64용 chromedriver를 배포하지 않아 ChromeDriverManager가 실패합니다.
    _drv = os.environ.get("CHROMEDRIVER_PATH")
    _bin = os.environ.get("CHROME_BINARY")
    if _bin:
        options.binary_location = _bin
    service = Service(_drv) if _drv else Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=options)
    return driver


def extract_player_id(link_element):
    """선수 링크에서 player_id 추출"""
    try:
        href = link_element.get_attribute('href')
        if 'playerId=' in href:
            return href.split('playerId=')[1].split('&')[0]
    except:
        pass
    return ''


def select_season(driver, year):
    """KBO ddlSeason 드롭다운에서 시즌 선택 (ASPX postback 발생)"""
    try:
        season_select = Select(driver.find_element(
            By.ID,
            "cphContents_cphContents_cphContents_ddlSeason_ddlSeason"
        ))
        season_select.select_by_value(str(year))
        time.sleep(3)
        logging.info(f"✅ 시즌 선택 완료: {year}")
        return True
    except Exception as e:
        logging.error(f"❌ 시즌 선택 실패 ({year}): {e}")
        return False


def scrape_table_page(driver, extract_player_id_flag=False, exclude_columns=None):
    """현재 페이지의 테이블 크롤링"""
    if exclude_columns is None:
        exclude_columns = []
    
    try:
        time.sleep(2)
        table = driver.find_element(By.CSS_SELECTOR, "table.tData01.tt")
        
        # 헤더 추출
        headers = []
        if extract_player_id_flag:
            headers.append('player_id')
        
        thead = table.find_element(By.TAG_NAME, "thead")
        header_cells = thead.find_elements(By.TAG_NAME, "th")
        
        for th in header_cells:
            header_text = th.text.strip()
            if header_text and header_text not in exclude_columns:
                # 컬럼 매핑 적용
                mapped_name = COLUMN_MAPPING.get(header_text, header_text.lower())
                headers.append(mapped_name)
        
        # 데이터 추출
        rows = []
        tbody = table.find_element(By.TAG_NAME, "tbody")
        for tr in tbody.find_elements(By.TAG_NAME, "tr"):
            row_data = []
            cells = tr.find_elements(By.TAG_NAME, "td")
            
            # player_id 추출
            if extract_player_id_flag:
                try:
                    player_link = tr.find_element(By.CSS_SELECTOR, "td a")
                    player_id = extract_player_id(player_link)
                    row_data.append(player_id)
                except:
                    row_data.append('')
            
            # 제외할 컬럼의 인덱스 찾기
            skip_indices = []
            for i, th in enumerate(header_cells):
                if th.text.strip() in exclude_columns:
                    skip_indices.append(i)
            
            # 데이터 추출
            for i, td in enumerate(cells):
                if i not in skip_indices:
                    row_data.append(td.text.strip())
            
            if row_data:
                rows.append(row_data)
        
        return pd.DataFrame(rows, columns=headers)
        
    except Exception as e:
        logging.error(f"  ❌ 테이블 크롤링 실패: {e}")
        return None


def get_page_count(driver):
    """전체 페이지 수 확인"""
    try:
        pager = driver.find_element(By.CSS_SELECTOR, "div.paging")
        page_links = pager.find_elements(By.TAG_NAME, "a")
        
        max_page = 1
        for link in page_links:
            text = link.text.strip()
            if text.isdigit():
                max_page = max(max_page, int(text))
        
        return max_page
    except:
        return 1


def click_next_page(driver, page_num):
    """다음 페이지 클릭"""
    try:
        page_link = driver.find_element(
            By.CSS_SELECTOR, 
            f"a[id*='btnNo{page_num}']"
        )
        page_link.click()
        time.sleep(2)
        return True
    except:
        logging.warning(f"  ⚠️ {page_num}페이지 이동 실패")
        return False


def scrape_basic1_all_pages(driver, team_code):
    """기본기록1 (Basic1) 전체 페이지 크롤링"""
    logging.info(f"  📊 기본기록1 (Basic1) 크롤링 시작")
    
    all_data = []
    page_count = get_page_count(driver)
    logging.info(f"    총 {page_count}페이지")
    
    for page in range(1, page_count + 1):
        logging.info(f"    📄 {page}/{page_count} 페이지 크롤링 중...")
        
        # player_id, player_name, team_name, AVG 등 모두 수집
        df = scrape_table_page(driver, extract_player_id_flag=True, exclude_columns=['순위'])
        if df is not None and not df.empty:
            all_data.append(df)
            logging.info(f"      ✅ {len(df)}명 수집")
        
        if page < page_count:
            if not click_next_page(driver, page + 1):
                break
    
    if all_data:
        final_df = pd.concat(all_data, ignore_index=True)
        logging.info(f"  ✅ 기본기록1 완료: 총 {len(final_df)}명")
        return final_df
    
    return pd.DataFrame()


def scrape_basic2_all_pages(driver, team_code):
    """기본기록2 (Basic2) 전체 페이지 크롤링 - "다음" 클릭 후"""
    logging.info(f"  📊 기본기록2 (Basic2) 크롤링 시작")
    
    # "다음" 링크 클릭
    try:
        next_link = driver.find_element(By.LINK_TEXT, "다음")
        next_link.click()
        time.sleep(2)
        logging.info(f"    ✅ '다음' 클릭 완료 (Basic2로 이동)")
    except Exception as e:
        logging.error(f"  ❌ '다음' 클릭 실패: {e}")
        return pd.DataFrame()
    
    all_data = []
    page_count = get_page_count(driver)
    logging.info(f"    총 {page_count}페이지")
    
    for page in range(1, page_count + 1):
        logging.info(f"    📄 {page}/{page_count} 페이지 크롤링 중...")
        
        # player_id, player_name, team_name, AVG 제외
        df = scrape_table_page(
            driver, 
            extract_player_id_flag=False, 
            exclude_columns=['순위', '선수명', '팀명', 'AVG']
        )
        if df is not None and not df.empty:
            all_data.append(df)
            logging.info(f"      ✅ {len(df)}명 수집")
        
        if page < page_count:
            if not click_next_page(driver, page + 1):
                break
    
    if all_data:
        final_df = pd.concat(all_data, ignore_index=True)
        logging.info(f"  ✅ 기본기록2 완료: 총 {len(final_df)}명")
        return final_df
    
    return pd.DataFrame()


def scrape_detail_all_pages(driver, team_code):
    """세부기록 (Detail) 전체 페이지 크롤링"""
    logging.info(f"  📊 세부기록 (Detail) 크롤링 시작")
    
    # 세부기록 탭 클릭
    try:
        detail_link = driver.find_element(By.LINK_TEXT, "세부기록")
        detail_link.click()
        time.sleep(2)
        logging.info(f"    ✅ '세부기록' 클릭 완료")
    except Exception as e:
        logging.error(f"  ❌ '세부기록' 클릭 실패: {e}")
        return pd.DataFrame()
    
    all_data = []
    page_count = get_page_count(driver)
    logging.info(f"    총 {page_count}페이지")
    
    for page in range(1, page_count + 1):
        logging.info(f"    📄 {page}/{page_count} 페이지 크롤링 중...")
        
        # 순위, 선수명, 팀명, AVG 제외
        df = scrape_table_page(
            driver, 
            extract_player_id_flag=False, 
            exclude_columns=['순위', '선수명', '팀명', 'AVG']
        )
        if df is not None and not df.empty:
            all_data.append(df)
            logging.info(f"      ✅ {len(df)}명 수집")
        
        if page < page_count:
            if not click_next_page(driver, page + 1):
                break
    
    if all_data:
        final_df = pd.concat(all_data, ignore_index=True)
        logging.info(f"  ✅ 세부기록 완료: 총 {len(final_df)}명")
        return final_df
    
    return pd.DataFrame()


def scrape_team_data(driver, team_code):
    """팀별 데이터 크롤링 (Basic1 + Basic2 + Detail 병합)"""
    logging.info(f"\n{'='*60}")
    logging.info(f"🏟️  팀: {team_code} 크롤링 시작")
    logging.info(f"{'='*60}")
    
    # 팀 선택
    try:
        team_select = Select(driver.find_element(
            By.ID, 
            "cphContents_cphContents_cphContents_ddlTeam_ddlTeam"
        ))
        team_select.select_by_value(team_code)
        time.sleep(3)
        logging.info(f"✅ 팀 선택 완료: {team_code}")
    except Exception as e:
        logging.error(f"❌ 팀 선택 실패: {e}")
        return pd.DataFrame()
    
    # 1. 기본기록1 크롤링
    basic1_df = scrape_basic1_all_pages(driver, team_code)
    
    # 2. 기본기록2 크롤링 ("다음" 클릭)
    basic2_df = scrape_basic2_all_pages(driver, team_code)
    
    # 3. 세부기록 크롤링
    detail_df = scrape_detail_all_pages(driver, team_code)
    
    # 데이터 병합
    if not basic1_df.empty:
        # Basic1 + Basic2 병합
        if not basic2_df.empty:
            if len(basic1_df) != len(basic2_df):
                logging.warning(f"  ⚠️ 행 수 불일치: Basic1({len(basic1_df)}) vs Basic2({len(basic2_df)})")
                min_rows = min(len(basic1_df), len(basic2_df))
                basic1_df = basic1_df.iloc[:min_rows]
                basic2_df = basic2_df.iloc[:min_rows]
            
            merged_df = pd.concat([basic1_df, basic2_df], axis=1)
            merged_df = merged_df.loc[:, ~merged_df.columns.duplicated()]
        else:
            merged_df = basic1_df
        
        # + Detail 병합
        if not detail_df.empty:
            if len(merged_df) != len(detail_df):
                logging.warning(f"  ⚠️ 행 수 불일치: Basic({len(merged_df)}) vs Detail({len(detail_df)})")
                min_rows = min(len(merged_df), len(detail_df))
                merged_df = merged_df.iloc[:min_rows]
                detail_df = detail_df.iloc[:min_rows]
            
            merged_df = pd.concat([merged_df, detail_df], axis=1)
            merged_df = merged_df.loc[:, ~merged_df.columns.duplicated()]
        
        logging.info(f"✅ 팀 {team_code} 완료: {len(merged_df)}명, {len(merged_df.columns)}개 컬럼")
        
        # 디버그: 첫 3행 출력
        logging.info(f"\n📋 샘플 데이터 (첫 3행):\n{merged_df.head(3).to_string()}\n")
        
        return merged_df
    
    logging.warning(f"⚠️ 팀 {team_code} 데이터 없음")
    return pd.DataFrame()


def main(year=None):
    """메인 함수"""
    if year is None:
        parser = argparse.ArgumentParser(description='KBO 공식 타자 통계 크롤러')
        parser.add_argument('--year', type=int, default=datetime.now().year,
                            help='시즌 연도 (default: 현재 연도)')
        args = parser.parse_args()
        year = args.year

    logging.info("=" * 80)
    logging.info(f"🏟️  KBO 공식 타자 통계 크롤링 시작 — {year} 시즌 (Basic1 + Basic2 + Detail)")
    logging.info("=" * 80)

    driver = setup_driver()

    try:
        # 타자 기본기록 페이지 접속
        url = "https://www.koreabaseball.com/Record/Player/HitterBasic/Basic1.aspx"
        driver.get(url)
        time.sleep(3)
        logging.info(f"✅ 페이지 접속: {url}")

        # 시즌 선택 (default가 현재 연도가 아닐 수 있으므로 명시 선택)
        if not select_season(driver, year):
            logging.error("❌ 시즌 선택 실패로 중단")
            return False

        all_teams_data = []

        # 팀별 크롤링
        for team_code in TEAM_CODES:
            team_df = scrape_team_data(driver, team_code)
            if not team_df.empty:
                all_teams_data.append(team_df)

            # 다음 팀을 위해 Basic1 페이지로 돌아가기 + 시즌 재선택
            driver.get(url)
            time.sleep(2)
            select_season(driver, year)

        # 전체 데이터 병합
        if all_teams_data:
            final_df = pd.concat(all_teams_data, ignore_index=True)

            # CSV 저장 (시즌별)
            csv_path = SAVE_DIR / f'batter_stats_{year}.csv'
            final_df.to_csv(csv_path, index=False, encoding='utf-8-sig')
            
            logging.info("\n" + "=" * 80)
            logging.info(f"✅ 크롤링 완료!")
            logging.info(f"📊 총 선수: {len(final_df)}명")
            logging.info(f"📊 총 컬럼: {len(final_df.columns)}개")
            logging.info(f"💾 저장 경로: {csv_path}")
            logging.info(f"📋 컬럼 목록:\n{list(final_df.columns)}")
            logging.info("=" * 80)
            
            return True
        else:
            logging.error("❌ 수집된 데이터 없음")
            return False
            
    except Exception as e:
        logging.error(f"❌ 크롤링 실패: {e}")
        import traceback
        logging.error(traceback.format_exc())
        return False
        
    finally:
        driver.quit()
        logging.info("🔚 브라우저 종료")


if __name__ == '__main__':
    success = main()
    
    import sys
    sys.exit(0 if success else 1)
