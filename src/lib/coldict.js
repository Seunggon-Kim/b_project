// 컬럼 설명 사전입니다.
//
// 원본 api/main.py:631-643 의 load_col_dict 는 database/column_descriptions.json
// 을 읽어 한 번 캐시합니다. Worker 에는 파일 시스템이 없어 번들에 넣습니다.
// wrangler 가 JSON import 를 정적으로 묶어 주므로 import 자체가 캐시입니다.
//
// D1 표로 옮기는 방법도 있으나 조회마다 쿼리가 늘고, 이 사전은 손으로 관리하는
// 문서라 git 에 두는 편이 낫습니다. 내용이 바뀌면 재배포가 필요합니다.
import raw from '../../database/column_descriptions.json';

/** 원본 load_col_dict 와 같은 것을 돌려줍니다. 실패 시 빈 뼈대입니다. */
export function columnDict() {
  return raw && typeof raw === 'object'
    ? raw
    : { categories: [], tables: {} };
}

/** 표 하나의 메타(category, table_desc, update_freq, columns)입니다. */
export function tableMeta(table) {
  return (columnDict().tables || {})[table] || {};
}

/** 표의 컬럼 설명 map 입니다. 없으면 빈 객체입니다. */
export function tableColumns(table) {
  return tableMeta(table).columns || {};
}
