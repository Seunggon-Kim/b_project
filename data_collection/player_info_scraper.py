"""
KBO 선수 상세 정보 크롤러 (테스트 버전 - 처음 5명만)
기존 player_id를 사용하여 선수 상세 정보 수집
"""
import time
import re
import logging
from pathlib import Path
from datetime import datetime
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager
import pandas as pd
import sqlite3

# 로깅 설정
PROJECT_ROOT = Path(__file__).parent.parent
LOG_DIR = PROJECT_ROOT / 'logs'
LOG_DIR.mkdir(exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(LOG_DIR / f'player_info_test_{datetime.now():%Y%m%d}.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# DB 경로
DB_PATH = PROJECT_ROOT / 'database' / 'kbo_stats.db'


def setup_driver():
    """Selenium WebDriver 설정"""
    chrome_options = Options()
    chrome_options.add_argument('--headless')
    chrome_options.add_argument('--no-sandbox')
    chrome_options.add_argument('--disable-dev-shm-usage')
    chrome_options.add_argument('--disable-gpu')
    chrome_options.add_argument('--window-size=1920,1080')
    chrome_options.add_argument('user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36')
    
    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=chrome_options)
    return driver


def parse_number(text):
    """숫자 추출 (예: 'No.51' -> 51, '15000만원' -> 150000000)"""
    if not text or text == '-':
        return None
    
    # 등번호 (No.51)
    if 'No.' in text:
        match = re.search(r'No\.(\d+)', text)
        return int(match.group(1)) if match else None
    
    # 금액 (15000만원)
    if '만원' in text:
        match = re.search(r'([\d,]+)만원', text)
        if match:
            return int(match.group(1).replace(',', '')) * 10000
    
    # 일반 숫자
    match = re.search(r'[\d,]+', text)
    if match:
        return int(match.group(0).replace(',', ''))
    
    return None


def parse_birthday(text):
    """생년월일 파싱 (예: '2024년 04월 20일' -> '20040420')"""
    if not text or text == '-':
        return None
    
    match = re.search(r'(\d{4})년\s*(\d{1,2})월\s*(\d{1,2})일', text)
    if match:
        year, month, day = match.groups()
        return f"{year}{month.zfill(2)}{day.zfill(2)}"
    return None


def parse_position(text):
    """포지션 파싱 (예: '내야수(우투좌타)' -> position='내야수', throw='R', bat='L')"""
    if not text or text == '-':
        return None, None, None
    
    # 포지션 추출
    position_match = re.match(r'([^(]+)', text)
    position = position_match.group(1).strip() if position_match else None
    
    # 투타 정보 추출
    throw_bat_match = re.search(r'\(([^)]+)\)', text)
    throw, bat = None, None
    
    if throw_bat_match:
        throw_bat = throw_bat_match.group(1)
        
        # 투 (우투/좌투/양투)
        if '우투' in throw_bat:
            throw = 'R'
        elif '좌투' in throw_bat:
            throw = 'L'
        elif '양투' in throw_bat:
            throw = 'S'
        
        # 타 (우타/좌타/양타)
        if '우타' in throw_bat:
            bat = 'R'
        elif '좌타' in throw_bat:
            bat = 'L'
        elif '양타' in throw_bat:
            bat = 'S'
    
    return position, throw, bat


def parse_height_weight(text):
    """신장/체중 파싱 (예: '174cm/82kg' -> height=174, weight=82)"""
    if not text or text == '-':
        return None, None
    
    height_match = re.search(r'(\d+)cm', text)
    weight_match = re.search(r'(\d+)kg', text)
    
    height = int(height_match.group(1)) if height_match else None
    weight = int(weight_match.group(1)) if weight_match else None
    
    return height, weight


def parse_draft_info(text):
    """지명순위 파싱 (예: '23 한화 2라운드 11순위' -> draft_year='23한화', draft_order='2라운드 11순위')"""
    if not text or text == '-':
        return None, None
    
    # 입단년도 (예: '23 한화')
    year_team_match = re.match(r'(\d{2})\s*([^\s]+)', text)
    draft_year = f"{year_team_match.group(1)}{year_team_match.group(2)}" if year_team_match else None
    
    # 지명순위 (예: '2라운드 11순위')
    order_match = re.search(r'(\d+라운드\s*\d+순위)', text)
    draft_order = order_match.group(1) if order_match else text
    
    return draft_year, draft_order


def scrape_player_info(driver, player_id):
    """선수 상세 정보 크롤링 (타자/투수 자동 감지)"""
    
    # 먼저 타자 페이지 시도
    hitter_url = f"https://www.koreabaseball.com/Record/Player/HitterDetail/Basic.aspx?playerId={player_id}"
    pitcher_url = f"https://www.koreabaseball.com/Record/Player/PitcherDetail/Basic.aspx?playerId={player_id}"
    
    for url, player_type in [(hitter_url, '타자'), (pitcher_url, '투수')]:
        try:
            driver.get(url)
            time.sleep(2)
            
            # 선수 이름 (ID로 직접 찾기)
            try:
                player_name = driver.find_element(By.ID, 'cphContents_cphContents_cphContents_playerProfile_lblName').text.strip()
                if player_name:  # 이름이 있으면 성공
                    logger.info(f"선수 ID {player_id}: {player_type} 페이지 발견 - {player_name}")
                    break  # 성공하면 루프 종료
            except:
                continue  # 다음 URL 시도
        except:
            continue
    else:
        # 두 페이지 모두 실패
        logger.warning(f"선수 ID {player_id}: 타자/투수 페이지를 모두 찾을 수 없습니다")
        return None
    
    try:
        player_info = {
            'player_id': player_id,
            'player_name': player_name
        }
        
        # 선수 이미지 URL 추출
        try:
            img_element = driver.find_element(By.ID, 'cphContents_cphContents_cphContents_playerProfile_imgProgile')
            image_url = img_element.get_attribute('src')
            # no-Image.png가 아닌 경우만 저장
            if image_url and 'no-Image.png' not in image_url:
                # 상대 URL을 절대 URL로 변환
                if image_url.startswith('//'):
                    image_url = 'https:' + image_url
                player_info['image_url'] = image_url
            else:
                player_info['image_url'] = None
        except:
            player_info['image_url'] = None
        
        # 상세 정보 추출 (span ID 사용)
        try:
            # 등번호
            try:
                back_no = driver.find_element(By.ID, 'cphContents_cphContents_cphContents_playerProfile_lblBackNo').text
                player_info['back_number'] = int(back_no) if back_no else None
            except:
                player_info['back_number'] = None
            
            # 생년월일
            try:
                birthday = driver.find_element(By.ID, 'cphContents_cphContents_cphContents_playerProfile_lblBirthday').text
                player_info['birthday'] = parse_birthday(birthday)
            except:
                player_info['birthday'] = None
            
            # 포지션 (투타 포함)
            try:
                position_text = driver.find_element(By.ID, 'cphContents_cphContents_cphContents_playerProfile_lblPosition').text
                position, throw, bat = parse_position(position_text)
                player_info['position'] = position
                player_info['throw'] = throw
                player_info['bat'] = bat
            except:
                player_info['position'] = None
                player_info['throw'] = None
                player_info['bat'] = None
            
            # 신장/체중
            try:
                height_weight = driver.find_element(By.ID, 'cphContents_cphContents_cphContents_playerProfile_lblHeightWeight').text
                height, weight = parse_height_weight(height_weight)
                player_info['height'] = height
                player_info['weight'] = weight
            except:
                player_info['height'] = None
                player_info['weight'] = None
            
            # 경력
            try:
                career = driver.find_element(By.ID, 'cphContents_cphContents_cphContents_playerProfile_lblCareer').text
                player_info['career'] = career if career and career != '-' else None
            except:
                player_info['career'] = None
            
            # 계약금
            try:
                payment = driver.find_element(By.ID, 'cphContents_cphContents_cphContents_playerProfile_lblPayment').text
                player_info['signing_bonus'] = parse_number(payment)
            except:
                player_info['signing_bonus'] = None
            
            # 연봉
            try:
                salary = driver.find_element(By.ID, 'cphContents_cphContents_cphContents_playerProfile_lblSalary').text
                player_info['salary'] = parse_number(salary)
            except:
                player_info['salary'] = None
            
            # 지명순위
            try:
                draft = driver.find_element(By.ID, 'cphContents_cphContents_cphContents_playerProfile_lblDraft').text
                draft_year, draft_order = parse_draft_info(draft)
                player_info['draft_year'] = draft_year
                player_info['draft_order'] = draft_order
            except:
                player_info['draft_year'] = None
                player_info['draft_order'] = None
        
        except Exception as e:
            logger.error(f"선수 ID {player_id} 정보 파싱 오류: {e}")
        
        logger.info(f"선수: {player_name} ({player_id}) 정보 수집 완료")
        logger.info(f"   이미지: {player_info.get('image_url', 'None')}")
        return player_info
    
    except Exception as e:
        logger.error(f"선수 ID {player_id} 크롤링 오류: {e}")
        return None


def get_existing_player_ids():
    """DB에서 기존 player_id 목록 가져오기 (2025 시즌만)"""
    conn = sqlite3.connect(DB_PATH)
    
    # 2025 시즌 타자 통계에서 player_id 가져오기
    query_batter = "SELECT DISTINCT player_id FROM kbo_official_batter_stats WHERE season = 2025"
    df_batter = pd.read_sql_query(query_batter, conn)
    
    # 2025 시즌 투수 통계에서 player_id 가져오기
    query_pitcher = "SELECT DISTINCT player_id FROM kbo_official_pitcher_stats WHERE season = 2025"
    df_pitcher = pd.read_sql_query(query_pitcher, conn)
    
    conn.close()
    
    # 중복 제거하여 합치기
    all_ids = set(df_batter['player_id'].tolist() + df_pitcher['player_id'].tolist())
    return sorted(list(all_ids))


def save_to_db(player_data_list):
    """선수 정보를 DB에 저장 (UPSERT)"""
    if not player_data_list:
        logger.warning("저장할 데이터가 없습니다")
        return
    
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    
    for player in player_data_list:
        try:
            cur.execute("""
                INSERT OR REPLACE INTO players (
                    player_id, player_name, back_number, position, throw, bat,
                    birthday, height, weight, career, draft_year, draft_order,
                    signing_bonus, salary, image_url, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            """, (
                player.get('player_id'),
                player.get('player_name'),
                player.get('back_number'),
                player.get('position'),
                player.get('throw'),
                player.get('bat'),
                player.get('birthday'),
                player.get('height'),
                player.get('weight'),
                player.get('career'),
                player.get('draft_year'),
                player.get('draft_order'),
                player.get('signing_bonus'),
                player.get('salary'),
                player.get('image_url')
            ))
        except Exception as e:
            logger.error(f"DB 저장 오류 ({player.get('player_id')}): {e}")
    
    conn.commit()
    conn.close()
    logger.info(f"💾 {len(player_data_list)}명의 선수 정보 저장 완료")


def main():
    """메인 실행 함수"""
    logger.info("=" * 60)
    logger.info("🏃 KBO 선수 상세 정보 크롤링 시작")
    logger.info("=" * 60)
    
    # 기존 player_id 목록 가져오기 (2025 시즌)
    all_player_ids = get_existing_player_ids()
    
    logger.info(f"📋 전체 선수: {len(all_player_ids)}명 (2025 시즌)")
    
    if not all_player_ids:
        logger.warning("⚠️ player_id가 없습니다. 먼저 타자/투수 통계를 수집하세요.")
        return
    
    # 이미 수집된 선수 제외
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("SELECT player_id FROM players")
    existing_ids = set(row[0] for row in cur.fetchall())
    conn.close()
    
    remaining_ids = [pid for pid in all_player_ids if pid not in existing_ids]
    
    if not remaining_ids:
        logger.info("✅ 모든 선수 정보가 이미 수집되었습니다!")
        return
    
    logger.info(f"📝 이미 수집: {len(existing_ids)}명")
    logger.info(f"🔄 수집 대상: {len(remaining_ids)}명")
    
    # WebDriver 설정
    driver = setup_driver()
    
    try:
        player_data_list = []
        success_count = 0
        fail_count = 0
        
        for idx, player_id in enumerate(remaining_ids, 1):
            logger.info(f"[{idx}/{len(remaining_ids)}] 선수 ID: {player_id}")
            
            # 재시도 로직 (최대 3번)
            player_info = None
            for attempt in range(3):
                try:
                    player_info = scrape_player_info(driver, player_id)
                    if player_info:
                        success_count += 1
                        break
                    else:
                        if attempt < 2:
                            logger.warning(f"재시도 {attempt + 1}/3...")
                            time.sleep(2)
                except Exception as e:
                    logger.error(f"크롤링 오류 (시도 {attempt + 1}/3): {e}")
                    if attempt < 2:
                        time.sleep(3)
                    else:
                        fail_count += 1
            
            if player_info:
                player_data_list.append(player_info)
            
            # 10명마다 DB 저장
            if len(player_data_list) >= 10:
                save_to_db(player_data_list)
                logger.info(f"💾 진행상황: {success_count}명 성공, {fail_count}명 실패")
                player_data_list = []
            
            # 요청 간격 (서버 부하 방지)
            time.sleep(1)
            
            # 100명마다 진행상황 로그
            if idx % 100 == 0:
                logger.info(f"📊 진행률: {idx}/{len(remaining_ids)} ({idx/len(remaining_ids)*100:.1f}%)")
        
        # 남은 데이터 저장
        if player_data_list:
            save_to_db(player_data_list)
    
    except KeyboardInterrupt:
        logger.warning("⚠️ 사용자가 중단했습니다. 수집된 데이터를 저장합니다...")
        if player_data_list:
            save_to_db(player_data_list)
    
    except Exception as e:
        logger.error(f"❌ 예상치 못한 오류: {e}")
        if player_data_list:
            logger.info("수집된 데이터를 저장합니다...")
            save_to_db(player_data_list)
    
    finally:
        driver.quit()
    
    logger.info("=" * 60)
    logger.info(f"✅ 크롤링 완료 - 성공: {success_count}명, 실패: {fail_count}명")
    logger.info("=" * 60)


if __name__ == '__main__':
    main()
