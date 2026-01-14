# ☁️ AWS 자동화 가이드 (24/7 수집 및 대시보드)

이 문서는 로컬 컴퓨터를 끄더라도 **24시간 중단 없이** KBO 데이터를 수집하고 대시보드를 서비스하기 위한 AWS 구축 가이드입니다.

---

## 1. AWS 서버 (EC2) 준비

### 인스턴스 사양

* **유형:** `t2.micro` (AWS 프리 티어 무료)
* **운영체제:** `Ubuntu 22.04 LTS`
* **스토리지:** 20GB ~ 30GB (기본 8GB보다 넉넉하게 설정 추천)

### 보안 그룹 (Security Group) 설정

다음 포트들을 열어주어야 합니다.

* **22 (SSH):** 서버 접속용
* **8502 (Custom TCP):** Streamlit 대시보드 접속용 (현재 설정값 기준)

---

## 2. 서버 환경 구축 (Linux)

서버 접속 후(SSH), 다음 명령어를 순서대로 실행하여 환경을 구축합니다.

### 시스템 업데이트 및 파이썬 설치

```bash
sudo apt-get update && sudo apt-get upgrade -y
sudo apt-get install python3-pip python3-venv git -y
```

### 리눅스용 Google Chrome 설치 (Selenium용)

```bash
wget https://dl.google.com/linux/direct/google-chrome-stable_current_amd64.deb
sudo apt install ./google-chrome-stable_current_amd64.deb -y
```

---

## 3. 프로젝트 배포

### 코드 가져오기

```bash
git clone https://github.com/사용자계정/b_project.git
cd b_project
```

### 가상환경 설정 및 패키지 설치

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

---

## 4. 자동화 설정 (선택)

### 방법 A: Crontab (추천 - 가볍고 안정적)

`t2.micro` 사양에서는 메모리 부족 위험이 적은 `crontab`을 권장합니다.

1. **편집기 열기:** `crontab -e`
2. **스케줄 추가 (매일 새벽 2시 실행):**

    ```bash
    0 2 * * * /home/ubuntu/b_project/venv/bin/python /home/ubuntu/b_project/data_collection/selenium_batter_scraper.py && /home/ubuntu/b_project/venv/bin/python /home/ubuntu/b_project/data_collection/kbo_to_db.py
    ```

### 방법 B: Airflow (복잡한 워크플로우용)

더 정교한 관리가 필요하다면 Airflow를 설치합니다. (메모리 swap 설정 필수)

1. Docker Desktop 없이 `pip install apache-airflow`로 설치 가능
2. `dags/` 폴더 내에 `kbo_collection_dag.py` 작성하여 작업 순서 정의

---

## 5. 대시보드 상시 가동

터미널을 종료해도 대시보드가 꺼지지 않게 하려면 `nohup`을 사용합니다.

```bash
nohup streamlit run dashboard/Home.py --server.port 8502 &
```

* 이제 브라우저에서 `http://서버공인IP:8502`로 접속 가능합니다.

---

## ⚠️ 주의사항 (Headless 모드)

리눅스 서버는 모니터가 없으므로 `selenium_batter_scraper.py` 내부의 브라우저 설정에 반드시 **Headless** 옵션이 포함되어야 합니다.

```python
options = webdriver.ChromeOptions()
options.add_argument('--headless')  # ← 필수
options.add_argument('--no-sandbox')
options.add_argument('--disable-dev-shm-usage')
```

---
**작성일:** 2026-01-12
**상태:** 가이드 완료
