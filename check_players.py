import sqlite3
import pandas as pd

conn = sqlite3.connect('database/kbo_stats.db')

# 전체 컬럼 조회
df = pd.read_sql_query("SELECT * FROM players", conn)
conn.close()

print("=" * 120)
print(f"저장된 선수 정보: {len(df)}명")
print("=" * 120)

# 각 선수별로 모든 정보 출력
for idx, row in df.iterrows():
    print(f"\n[{idx+1}] {row['player_name']} (ID: {row['player_id']})")
    print(f"  - 등번호: {row['back_number']}")
    print(f"  - 포지션: {row['position']}")
    print(f"  - 투타: {row['throw']}/{row['bat']}")
    print(f"  - 생년월일: {row['birthday']}")
    print(f"  - 신장/체중: {row['height']}cm / {row['weight']}kg")
    print(f"  - 경력: {row['career']}")
    print(f"  - 입단년도: {row['draft_year']}")
    print(f"  - 지명순위: {row['draft_order']}")
    print(f"  - 계약금: {row['signing_bonus']:,}원" if row['signing_bonus'] else "  - 계약금: None")
    print(f"  - 연봉: {row['salary']:,}원" if row['salary'] else "  - 연봉: None")
    print(f"  - 이미지 URL: {row['image_url']}" if row['image_url'] else "  - 이미지 URL: None")
    print(f"  - 생성일: {row['created_at']}")
    print(f"  - 수정일: {row['updated_at']}")

print("\n" + "=" * 120)
print("전체 컬럼 목록:")
print(df.columns.tolist())
print("=" * 120)
